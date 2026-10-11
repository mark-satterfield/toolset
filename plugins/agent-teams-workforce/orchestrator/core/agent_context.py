"""Session-local definitions, explicitly selected context, and fact-only briefs."""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

import yaml
from typeguard import CollectionCheckStrategy, check_type, typechecked

from .driver_contracts import denied_tools
from .io import JsonValue, json_object, write_json
from .models import AgentStep

SAFETY_HOOKS = frozenset({
    "no-verify-blocker.sh",
    "pipeline-run-blocker.sh",
    "bd-init-blocker.sh",
    "aws-profile-required.sh",
})


class PipelineStoppedError(RuntimeError):
    """The supervisor requested cooperative shutdown between agent steps."""


class SessionCleanupError(RuntimeError):
    """Session finalization failed; original execution evidence remains attached."""


class SessionSetupError(RuntimeError):
    """Required session configuration or preparation failed before agent launch."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_json(path: Path) -> dict[str, JsonValue]:
    """Read and validate a JSON object, allowing absent optional configuration.

    Returns:
        The JSON object, or an empty object for an absent file.

    """
    return json_object(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else {}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def list_field(value: object) -> list[str]:
    """Read a string-list field from authored agent frontmatter.

    Returns:
        The validated string list, or comma-separated string entries.

    """
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return check_type(
        value if value is not None else [],
        list[str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def definition(plugin: Path, step: AgentStep, model: str) -> dict[str, JsonValue]:
    """Build a selected agent definition from validated frontmatter.

    Returns:
        A Claude agent definition.

    Raises:
        ValueError: Agent frontmatter or its turn limit is invalid.
        TypeError: Agent metadata does not match the Claude definition contract.

    """
    if not isinstance(plugin, Path) or not isinstance(step, AgentStep) or not isinstance(model, str):
        argument_error: str = "Agent definition requires a plugin Path, AgentStep, and model string"
        raise TypeError(argument_error)
    text: str = (plugin / "agents" / f"{step.agent}.md").read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        message: str = f"agent {step.agent} has no frontmatter"
        raise ValueError(message)
    front: str
    body: str
    front, body = text[4:].split("\n---", 1)
    metadata: dict[str, JsonValue] = json_object(yaml.safe_load(front))
    result: dict[str, JsonValue] = {}
    description: JsonValue = metadata.get("description")
    if not isinstance(description, str):
        message = f"agent {step.agent} description must be a string"
        raise TypeError(message)
    result["description"] = description
    if "maxTurns" in metadata:
        turns: JsonValue = metadata["maxTurns"]
        if not isinstance(turns, int) or isinstance(turns, bool):
            message = f"agent {step.agent} maxTurns must be an integer"
            raise TypeError(message)
        if turns <= 0:
            message = f"agent {step.agent} maxTurns must be positive"
            raise ValueError(message)
        result["maxTurns"] = turns
    key: str
    for key in ("tools", "disallowedTools", "skills", "mcpServers"):
        if key in metadata:
            result[key] = list(list_field(metadata[key]))
    result.update(prompt=body.strip(), model=model, effort=step.effort)
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def safety_settings(config: Path, plugin: Path) -> dict[str, JsonValue]:
    """Select safety hooks and add the mandatory Python edit checks.

    Returns:
        Session settings containing selected pre-tool and post-tool hooks.

    """
    hooks = json_object(read_json(config / "settings.json").get("hooks", {})).get("PreToolUse", [])
    selected: list[JsonValue] = []
    for group in check_type(
        hooks,
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        keep: list[JsonValue] = []
        for hook in check_type(
            group.get("hooks", []),
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ):
            command = check_type(hook.get("command", ""), str)
            if hook.get("type") == "command" and any(Path(word).name in SAFETY_HOOKS for word in shlex.split(command)):
                keep.append(hook)
        if keep:
            selected.append({**group, "hooks": keep})
    quality_hook = plugin.resolve() / "orchestrator" / "hooks" / "python-quality.py"
    return {
        "hooks": {
            "PreToolUse": selected,
            "PostToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{shlex.quote(sys.executable)} {shlex.quote(str(quality_hook))}",
                            "timeout": 400,
                        },
                    ],
                },
            ],
        },
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def plugin_paths(config: Path, plugin: Path, skills: list[str]) -> list[Path]:
    """Resolve the installed plugins required by a selected agent.

    Returns:
        The current plugin followed by required skill plugins.

    Raises:
        ValueError: A required skill plugin is absent.

    """
    wanted = {skill.split(":", 1)[0] for skill in skills if ":" in skill} - {"agent-teams-workforce"}
    installed = check_type(
        read_json(config / "plugins" / "installed_plugins.json").get("plugins", {}),
        dict[str, list[dict[str, JsonValue]]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
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
            message = f"required skill plugin is not installed: {name}"
            raise ValueError(message)
        paths.append(Path(check_type(matches[0]["installPath"], str)))
    return paths


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def mcp_servers(control: Path, config: Path, names: list[str]) -> dict[str, JsonValue]:
    """Select configured MCP servers required by the agent.

    Returns:
        Server definitions keyed by requested name.

    Raises:
        ValueError: Required servers are absent.

    """
    global_file = config / ".claude.json" if os.environ.get("CLAUDE_CONFIG_DIR") else Path.home() / ".claude.json"
    found: dict[str, JsonValue] = {}
    for source in (control / ".mcp.json", global_file):
        for name, value in json_object(read_json(source).get("mcpServers", {})).items():
            if name in names and name not in found:
                found[name] = value
    missing = set(names) - found.keys()
    if missing:
        message = f"required MCP servers are not configured: {sorted(missing)}"
        raise ValueError(message)
    return found


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def prepare(plugin: Path, config: Path, directory: Path, step: AgentStep, model: str) -> list[str]:
    """Write private session configuration and construct Claude CLI arguments.

    Returns:
        Explicit arguments selecting the agent, settings and MCP configuration.

    Raises:
        TypeError: Session inputs do not satisfy the preparation contract.

    """
    if not all(isinstance(path, Path) for path in (plugin, config, directory)):
        message: str = "Session plugin, config, and directory must be Paths"
        raise TypeError(message)
    if not isinstance(step, AgentStep) or not isinstance(model, str):
        message = "Session preparation requires an AgentStep and model string"
        raise TypeError(message)
    agent: dict[str, JsonValue] = definition(plugin, step, model)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json(directory / "agents.json", {f"atw-{step.agent}": agent})
    write_json(directory / "settings.json", safety_settings(config, plugin))
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
    names = list_field(agent.get("mcpServers", []))
    if names:
        path = directory / "mcp.json"
        write_json(
            path,
            {"mcpServers": mcp_servers(Path(os.environ["ATW_CONTROL_REPO"]), config, names)},
        )
        path.chmod(0o600)
        command.extend(["--mcp-config", str(path)])
    for path in plugin_paths(config, plugin, list_field(agent.get("skills", []))):
        command.extend(["--plugin-dir", str(path)])
    command.extend([
        "--permission-mode",
        "bypassPermissions",
        "--disallowedTools",
        *denied_tools(),
        "Agent",
        "AskUserQuestion",
    ])
    for path in step.add_dirs:
        command.extend(["--add-dir", str(path.resolve())])
    return command


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def brief(
    bead: str,
    step: AgentStep,
    inputs: list[tuple[str, Path]],
    *,
    corrective: bool = False,
) -> str:
    """Serialize the one-line outcome and selected inputs for an agent.

    Returns:
        A JSON brief containing paths and the expected outcome.

    Raises:
        ValueError: The outcome contains multiple lines.

    """
    outcome = "Correct the output named in the errors file." if corrective else step.outcome
    if "\n" in outcome:
        message = "an outcome must be one line"
        raise ValueError(message)
    return json.dumps(
        {
            "bead": bead,
            "inputs": [{"label": label, "path": str(path.resolve())} for label, path in inputs],
            "output": str(step.output.resolve()),
            "outcome": outcome,
        },
        ensure_ascii=False,
    )
