"""Session-local definitions, explicitly selected context, and fact-only briefs."""

from __future__ import annotations

import importlib
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

import yaml

from .io import write_json
from .models import AgentStep

SAFETY_HOOKS = frozenset(
    {
        "no-verify-blocker.sh",
        "pipeline-run-blocker.sh",
        "bd-init-blocker.sh",
        "aws-profile-required.sh",
    }
)


def driver_module(name: str) -> Any:
    directory = Path(os.environ["ATW_CONTROL_REPO"]) / "ops" / "sdlc-automation"
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    return importlib.import_module(name)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def list_field(value: Any) -> list:
    return (
        [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, str)
        else list(value or [])
    )


def definition(plugin: Path, step: AgentStep, model: str) -> dict:
    text = (plugin / "agents" / f"{step.agent}.md").read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"agent {step.agent} has no frontmatter")
    front, body = text[4:].split("\n---", 1)
    metadata = yaml.safe_load(front)
    result = {
        key: metadata[key] for key in ("description", "maxTurns") if key in metadata
    }
    for key in ("tools", "disallowedTools", "skills", "mcpServers"):
        if key in metadata:
            result[key] = list_field(metadata[key])
    result.update(prompt=body.strip(), model=model, effort=step.effort)
    return result


def safety_settings(config: Path) -> dict:
    hooks = read_json(config / "settings.json").get("hooks", {}).get("PreToolUse", [])
    selected = []
    for group in hooks:
        keep = []
        for hook in group.get("hooks", []):
            command = hook.get("command", "")
            if hook.get("type") == "command" and any(
                Path(word).name in SAFETY_HOOKS for word in shlex.split(command)
            ):
                keep.append(hook)
        if keep:
            selected.append({**group, "hooks": keep})
    return {"hooks": {"PreToolUse": selected}}


def plugin_paths(config: Path, plugin: Path, skills: list[str]) -> list[Path]:
    wanted = {skill.split(":", 1)[0] for skill in skills if ":" in skill} - {
        "agent-teams-workforce"
    }
    installed = read_json(config / "plugins" / "installed_plugins.json").get(
        "plugins", {}
    )
    paths = [plugin]
    for name in sorted(wanted):
        matches = [
            entry
            for key, entries in installed.items()
            if key.split("@", 1)[0] == name
            for entry in entries
            if entry.get("installPath")
        ]
        if not matches:
            raise ValueError(f"required skill plugin is not installed: {name}")
        paths.append(Path(matches[0]["installPath"]))
    return paths


def mcp_servers(control: Path, config: Path, names: list[str]) -> dict:
    global_file = (
        config / ".claude.json"
        if os.environ.get("CLAUDE_CONFIG_DIR")
        else Path.home() / ".claude.json"
    )
    found = {}
    for source in (control / ".mcp.json", global_file):
        for name, value in read_json(source).get("mcpServers", {}).items():
            if name in names and name not in found:
                found[name] = value
    missing = set(names) - found.keys()
    if missing:
        raise ValueError(f"required MCP servers are not configured: {sorted(missing)}")
    return found


def prepare(
    plugin: Path, config: Path, directory: Path, step: AgentStep, model: str
) -> list[str]:
    if any((parent / ".git").exists() for parent in (directory, *directory.parents)):
        raise ValueError(f"session directory must be outside repositories: {directory}")
    agent = definition(plugin, step, model)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json(directory / "agents.json", {f"atw-{step.agent}": agent})
    write_json(directory / "settings.json", safety_settings(config))
    command = [
        "--agents",
        str(directory / "agents.json"),
        "--agent",
        f"atw-{step.agent}",
        "--model",
        model,
        "--effort",
        step.effort,
        "--setting-sources",
        "project",
        "--settings",
        str(directory / "settings.json"),
        "--strict-mcp-config",
    ]
    names = agent.get("mcpServers", [])
    if names:
        path = directory / "mcp.json"
        write_json(
            path,
            {
                "mcpServers": mcp_servers(
                    Path(os.environ["ATW_CONTROL_REPO"]), config, names
                )
            },
        )
        path.chmod(0o600)
        command.extend(["--mcp-config", str(path)])
    for path in plugin_paths(config, plugin, agent.get("skills", [])):
        command.extend(["--plugin-dir", str(path)])
    command.extend(
        [
            "--permission-mode",
            "bypassPermissions",
            "--disallowedTools",
            *driver_module("headlessenv").DENIED_TOOLS,
            "Agent",
            "AskUserQuestion",
        ]
    )
    for path in step.add_dirs:
        command.extend(["--add-dir", str(path.resolve())])
    return command


def brief(
    bead: str,
    step: AgentStep,
    inputs: list[tuple[str, Path]],
    *,
    corrective: bool = False,
) -> str:
    outcome = (
        "Correct the output named in the errors file." if corrective else step.outcome
    )
    if "\n" in outcome:
        raise ValueError("an outcome must be one line")
    return json.dumps(
        {
            "bead": bead,
            "inputs": [
                {"label": label, "path": str(path.resolve())} for label, path in inputs
            ],
            "output": str(step.output.resolve()),
            "outcome": outcome,
        },
        ensure_ascii=False,
    )
