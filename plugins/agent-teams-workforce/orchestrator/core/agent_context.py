"""The launcher: a session run as a predefined agent, its settings, and fact-only briefs.

A session is launched as the predefined agent by its plain front-matter name. Claude Code loads
the agent's definition (the user-level copy of an agent with ``mcpServers`` wins by precedence),
preloads the skills its front matter lists, and applies its tools, effort and MCP servers. The
launcher passes no agent or skill text and computes no flag from them.
"""

from __future__ import annotations

import json
import shlex
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final

from typeguard import CollectionCheckStrategy, check_type, typechecked

from .driver_contracts import denied_tools
from .frontmatter import split_front_matter, string_list
from .io import JsonValue, json_object, write_json
from .models import AgentStep

SAFETY_HOOKS = frozenset({
    "no-verify-blocker.sh",
    "pipeline-run-blocker.sh",
    "bd-init-blocker.sh",
    "aws-profile-required.sh",
})

AGENT_TOOL: Final = "Agent"
SEND_MESSAGE_TOOL: Final = "SendMessage"
ASK_TOOL: Final = "AskUserQuestion"
SPAWN_DEPTH_ENV: Final = "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"
BACKGROUND_TASKS_ENV: Final = "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"
SESSION_ENV: Final[Mapping[str, str]] = MappingProxyType({SPAWN_DEPTH_ENV: "1", BACKGROUND_TASKS_ENV: "1"})
"""Every session's settings: an agent it starts starts none, and every start blocks."""
BASH_OUTPUT_KEY: Final = "bashOutputMaxChars"
BASH_OUTPUT_LIMIT: Final = 128_000
"""Claude Code's largest inline command output, so a command's output is not cut to a preview."""


class PipelineStoppedError(RuntimeError):
    """The supervisor requested cooperative shutdown between agent steps."""


class SessionCleanupError(RuntimeError):
    """Session finalization failed; original execution evidence remains attached."""


class SessionSetupError(RuntimeError):
    """Required session configuration or preparation failed before agent launch."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class AgentDefinition:
    """The fields of one agent definition file the runner still reads (held for the owner's ruling).

    ``model`` drives the Fable fallback, ``role`` the matrix role and ``tools`` with
    ``disallowed_tools`` whether the session keeps ``SendMessage``. ``tools`` and
    ``disallowed_tools`` are None when the file does not state them.
    """

    name: str
    model: str
    role: str | None
    tools: tuple[str, ...] | None
    disallowed_tools: tuple[str, ...] | None

    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        strategy: CollectionCheckStrategy = CollectionCheckStrategy.ALL_ITEMS
        check_type(self.name, str)
        check_type(self.model, str)
        check_type(self.role, str | None)
        check_type(self.tools, tuple[str, ...] | None, collection_check_strategy=strategy)
        check_type(self.disallowed_tools, tuple[str, ...] | None, collection_check_strategy=strategy)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class Launch:
    """What one launch decides beyond the agent definitions.

    ``model_replacements`` maps a model a definition states to the model used in its place (the
    runner's fallback when a model's allowance is spent).
    """

    model_replacements: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        check_type(
            self.model_replacements,
            Mapping[str, str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_json(path: Path) -> dict[str, JsonValue]:
    """Read and validate a JSON object, allowing absent optional configuration.

    Returns:
        The JSON object, or an empty object for an absent file.

    """
    return json_object(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else {}


def _optional_list(metadata: Mapping[str, JsonValue], key: str) -> tuple[str, ...] | None:
    """Read a list field that Claude Code treats differently when it is absent.

    Returns:
        The strings of the field, or None when the front matter does not hold the key.

    """
    return tuple(string_list(metadata[key])) if key in metadata else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_agent(plugin: Path, name: str) -> AgentDefinition:
    """Read the model, role and tools of one agent definition file of the plugin.

    Returns:
        The validated fields.

    Raises:
        TypeError: An argument or a front matter field has the wrong type.
        ValueError: The front matter is missing or states no model.

    """
    if not isinstance(plugin, Path) or not isinstance(name, str):
        argument_error: str = "load_agent requires the plugin Path and an agent name"
        raise TypeError(argument_error)
    fields: dict[str, object]
    fields, _ = split_front_matter((plugin / "agents" / f"{name}.md").read_text(encoding="utf-8"), f"agent {name}")
    metadata: dict[str, JsonValue] = json_object(fields)
    model: JsonValue = metadata.get("model")
    if not isinstance(model, str) or not model.strip():
        message: str = f"agent {name} must state its model in front matter"
        raise ValueError(message)
    role: JsonValue = metadata.get("role")
    if role is not None and (not isinstance(role, str) or not role.strip()):
        message = f"agent {name} role must be a non-empty string"
        raise TypeError(message)
    return AgentDefinition(
        name=name,
        model=model.strip(),
        role=role,
        tools=_optional_list(metadata, "tools"),
        disallowed_tools=_optional_list(metadata, "disallowedTools"),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def launch_model(agent: AgentDefinition, launch: Launch) -> str:
    """Name the model an agent runs on in this launch.

    Returns:
        The model its definition states, or the model this launch uses in its place.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(agent, AgentDefinition) or not isinstance(launch, Launch):
        argument_error: str = "launch_model requires an AgentDefinition and a Launch"
        raise TypeError(argument_error)
    return launch.model_replacements.get(agent.model, agent.model)


def may_start_agents(agent: AgentDefinition) -> bool:
    """Tell whether an agent's front matter gives it the Agent tool.

    Returns:
        True when its ``tools`` list names the Agent tool, or it lists no tools and does not
        disallow the Agent tool.

    """
    allowed: bool = agent.tools is None or any(tool.split("(", 1)[0] == AGENT_TOOL for tool in agent.tools)
    return allowed and AGENT_TOOL not in (agent.disallowed_tools or ())


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
def session_settings(config: Path, plugin: Path) -> dict[str, JsonValue]:
    """Build the settings file of one session.

    Every session has the safety hooks, is limited to one layer of started agents, each started
    in the foreground, and takes a command's output whole.

    Returns:
        The session's settings.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(config, Path) or not isinstance(plugin, Path):
        argument_error: str = "session_settings requires two Paths"
        raise TypeError(argument_error)
    settings: dict[str, JsonValue] = safety_settings(config, plugin)
    settings["env"] = dict(SESSION_ENV)
    settings[BASH_OUTPUT_KEY] = BASH_OUTPUT_LIMIT
    return settings


def _denied(launched: AgentDefinition) -> list[str]:
    """List the tools the command line denies one session.

    Every session is denied the driver's list and questions to the user. A session whose
    agent may start agents keeps SendMessage when its definition lists it, so it can continue an
    agent it started.

    Returns:
        The denied tool names, in the driver's order.

    """
    denied: list[str] = list(denied_tools())
    if may_start_agents(launched) and SEND_MESSAGE_TOOL in (launched.tools or ()):
        denied = [tool for tool in denied if tool != SEND_MESSAGE_TOOL]
    return [*denied, ASK_TOOL]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def prepare(plugin: Path, config: Path, directory: Path, step: AgentStep, launch: Launch) -> list[str]:
    """Write private session settings and construct Claude CLI arguments.

    Returns:
        Explicit arguments selecting the agent by its plain name, the model, the settings and
        the plugin.

    Raises:
        TypeError: Session inputs do not satisfy the preparation contract.

    """
    if not all(isinstance(path, Path) for path in (plugin, config, directory)):
        message: str = "Session plugin, config, and directory must be Paths"
        raise TypeError(message)
    if not isinstance(step, AgentStep) or not isinstance(launch, Launch):
        message = "Session preparation requires an AgentStep and a Launch"
        raise TypeError(message)
    launched: AgentDefinition = load_agent(plugin, step.agent)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json(directory / "settings.json", session_settings(config, plugin))
    command: list[str] = [
        "--agent",
        step.agent,
        "--model",
        launch_model(launched, launch),
        "--setting-sources",
        "project",
        "--settings",
        str(directory / "settings.json"),
        "--plugin-dir",
        str(plugin),
        "--permission-mode",
        "bypassPermissions",
        "--disallowedTools",
        *_denied(launched),
    ]
    command.extend(arg for path in step.add_dirs for arg in ("--add-dir", str(path.resolve())))
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

    A step that states what is asked sends it as ``request``, and a step of the bead's step
    journal sends its id as ``step``.

    Returns:
        A JSON brief containing paths and the expected outcome.

    Raises:
        ValueError: The outcome contains multiple lines.

    """
    outcome = "Correct the output named in the errors file." if corrective else step.outcome
    if "\n" in outcome:
        message = "an outcome must be one line"
        raise ValueError(message)
    facts: dict[str, JsonValue] = {
        "bead": bead,
        "inputs": [{"label": label, "path": str(path.resolve())} for label, path in inputs],
        "output": str(step.output.resolve()),
        "outcome": outcome,
    }
    if step.request is not None:
        facts["request"] = step.request
    if step.journal_step is not None:
        facts["step"] = step.journal_step
    return json.dumps(facts, ensure_ascii=False)
