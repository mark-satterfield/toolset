"""The launcher: session-local definitions, explicitly selected context, and fact-only briefs.

One agent definition file is the single statement of an agent's model, effort, tools, skills and
MCP servers, of the role it plays (``role``), of the roles it may start (``startsRoles``) and of
whether it is given the Epic's expertise (``epicExpertise``). The launcher reads those and holds
no table of its own.

Claude Code does not put the text of an agent's front matter skills in a session started with
``--agent``; it does for an agent that session starts with the Agent tool. So the launcher appends
the skill text to the launched agent's prompt, and gives every agent that may be started its
``skills`` list.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, TypeIs, get_args

from typeguard import CollectionCheckStrategy, check_type, typechecked

from .driver_contracts import denied_tools
from .frontmatter import split_front_matter, string_list
from .io import JsonValue, json_object, write_json
from .models import AgentStep
from .skills import PLUGIN_NAME, Skill, SkillRoots, installed_plugin, load_skills, skill_plugin, skills_text

# isort: split
# driver_contracts puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from driver_surface_types import CONTROL_REPO_ENV

SAFETY_HOOKS = frozenset({
    "no-verify-blocker.sh",
    "pipeline-run-blocker.sh",
    "bd-init-blocker.sh",
    "aws-profile-required.sh",
})

type Effort = Literal["low", "medium", "high", "xhigh", "max"]
EFFORTS: Final[tuple[Effort, ...]] = get_args(Effort.__value__)
type ExpertiseDelivery = Literal["at-launch", "live"]
"""How an agent is given the Epic's expertise skills.

``at-launch``: the text of the skills known when its session is launched is in its context.
``live``: the same, and the session also accepts a skill a command prints while it works.
"""
EXPERTISE_DELIVERIES: Final[tuple[ExpertiseDelivery, ...]] = get_args(ExpertiseDelivery.__value__)
LIVE_EXPERTISE: Final[ExpertiseDelivery] = "live"

AGENT_PREFIX: Final = "atw-"
AGENT_TOOL: Final = "Agent"
SEND_MESSAGE_TOOL: Final = "SendMessage"
ASK_TOOL: Final = "AskUserQuestion"
SPAWN_DEPTH_ENV: Final = "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"
BACKGROUND_TASKS_ENV: Final = "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"
STARTER_ENV: Final[Mapping[str, str]] = MappingProxyType({SPAWN_DEPTH_ENV: "1", BACKGROUND_TASKS_ENV: "1"})
"""Settings of a session that may start agents: a started agent starts none, and every start blocks."""
BASH_OUTPUT_KEY: Final = "bashOutputMaxChars"
BASH_OUTPUT_LIMIT: Final = 128_000
"""Claude Code's largest inline command output, so a skill a command prints is not cut to a preview."""


class PipelineStoppedError(RuntimeError):
    """The supervisor requested cooperative shutdown between agent steps."""


class SessionCleanupError(RuntimeError):
    """Session finalization failed; original execution evidence remains attached."""


class SessionSetupError(RuntimeError):
    """Required session configuration or preparation failed before agent launch."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class AgentDefinition:
    """One agent definition file, read and validated.

    ``tools`` and ``disallowed_tools`` are None when the file does not state them, which Claude
    Code reads differently from an empty list.
    """

    name: str
    description: str
    body: str
    model: str
    effort: Effort
    max_turns: int | None
    tools: tuple[str, ...] | None
    disallowed_tools: tuple[str, ...] | None
    skills: tuple[str, ...]
    mcp_servers: tuple[str, ...] | None
    role: str | None
    starts_roles: tuple[str, ...]
    epic_expertise: ExpertiseDelivery | None

    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        strategy: CollectionCheckStrategy = CollectionCheckStrategy.ALL_ITEMS
        check_type(self.name, str)
        check_type(self.description, str)
        check_type(self.body, str)
        check_type(self.model, str)
        check_type(self.effort, Effort)
        check_type(self.max_turns, int | None)
        check_type(self.tools, tuple[str, ...] | None, collection_check_strategy=strategy)
        check_type(self.disallowed_tools, tuple[str, ...] | None, collection_check_strategy=strategy)
        check_type(self.skills, tuple[str, ...], collection_check_strategy=strategy)
        check_type(self.mcp_servers, tuple[str, ...] | None, collection_check_strategy=strategy)
        check_type(self.role, str | None)
        check_type(self.starts_roles, tuple[str, ...], collection_check_strategy=strategy)
        check_type(self.epic_expertise, ExpertiseDelivery | None)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class Launch:
    """What one launch decides beyond the agent definitions.

    ``model_replacements`` maps a model a definition states to the model used in its place (the
    runner's fallback when a model's allowance is spent). ``expertise`` is the Epic's expertise
    list: the skills its domains need.
    """

    model_replacements: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    expertise: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        check_type(
            self.model_replacements,
            Mapping[str, str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        check_type(self.expertise, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_json(path: Path) -> dict[str, JsonValue]:
    """Read and validate a JSON object, allowing absent optional configuration.

    Returns:
        The JSON object, or an empty object for an absent file.

    """
    return json_object(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else {}


def _is_effort(value: object) -> TypeIs[Effort]:
    """Narrow a front matter value to a reasoning effort Claude Code accepts.

    Returns:
        True when the value is one of ``EFFORTS``.

    """
    return isinstance(value, str) and value in EFFORTS


def _is_delivery(value: object) -> TypeIs[ExpertiseDelivery]:
    """Narrow a front matter value to a way of delivering the Epic's expertise.

    Returns:
        True when the value is one of ``EXPERTISE_DELIVERIES``.

    """
    return isinstance(value, str) and value in EXPERTISE_DELIVERIES


def _optional_list(metadata: Mapping[str, JsonValue], key: str) -> tuple[str, ...] | None:
    """Read a list field that Claude Code treats differently when it is absent.

    Returns:
        The strings of the field, or None when the front matter does not hold the key.

    """
    return tuple(string_list(metadata[key])) if key in metadata else None


def _max_turns(metadata: Mapping[str, JsonValue], name: str) -> int | None:
    """Read an agent's turn limit.

    Returns:
        The limit, or None when the front matter states none.

    Raises:
        TypeError: The limit is not an integer.
        ValueError: The limit is not positive.

    """
    if "maxTurns" not in metadata:
        return None
    turns: JsonValue = metadata["maxTurns"]
    if not isinstance(turns, int) or isinstance(turns, bool):
        message: str = f"agent {name} maxTurns must be an integer"
        raise TypeError(message)
    if turns <= 0:
        message = f"agent {name} maxTurns must be positive"
        raise ValueError(message)
    return turns


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_agent(plugin: Path, name: str) -> AgentDefinition:
    """Read one agent definition file of the plugin.

    Returns:
        The validated definition.

    Raises:
        TypeError: An argument or a front matter field has the wrong type.
        ValueError: The front matter is missing, or states no model, no valid effort, a turn limit
            that is not positive, or an unknown way of delivering expertise.

    """
    if not isinstance(plugin, Path) or not isinstance(name, str):
        argument_error: str = "load_agent requires the plugin Path and an agent name"
        raise TypeError(argument_error)
    fields: dict[str, object]
    body: str
    fields, body = split_front_matter(
        (plugin / "agents" / f"{name}.md").read_text(encoding="utf-8"),
        f"agent {name}",
    )
    metadata: dict[str, JsonValue] = json_object(fields)
    description: JsonValue = metadata.get("description")
    if not isinstance(description, str):
        message: str = f"agent {name} description must be a string"
        raise TypeError(message)
    turns: int | None = _max_turns(metadata, name)
    model: JsonValue = metadata.get("model")
    if not isinstance(model, str) or not model.strip():
        message = f"agent {name} must state its model in front matter"
        raise ValueError(message)
    effort: JsonValue = metadata.get("effort")
    if not _is_effort(effort):
        message = f"agent {name} must state its effort in front matter as one of {list(EFFORTS)}, got {effort!r}"
        raise ValueError(message)
    role: JsonValue = metadata.get("role")
    if role is not None and (not isinstance(role, str) or not role.strip()):
        message = f"agent {name} role must be a non-empty string"
        raise TypeError(message)
    delivery: JsonValue = metadata.get("epicExpertise")
    if delivery is not None and not _is_delivery(delivery):
        message = f"agent {name} epicExpertise must be one of {list(EXPERTISE_DELIVERIES)}, got {delivery!r}"
        raise ValueError(message)
    return AgentDefinition(
        name=name,
        description=description,
        body=body,
        model=model.strip(),
        effort=effort,
        max_turns=turns,
        tools=_optional_list(metadata, "tools"),
        disallowed_tools=_optional_list(metadata, "disallowedTools"),
        skills=tuple(string_list(metadata.get("skills"))),
        mcp_servers=_optional_list(metadata, "mcpServers"),
        role=role,
        starts_roles=tuple(string_list(metadata.get("startsRoles"))),
        epic_expertise=delivery,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def started_agents(plugin: Path, launched: AgentDefinition) -> tuple[AgentDefinition, ...]:
    """Collect the agents a launched agent may start: those whose ``role`` is in its ``startsRoles``.

    Returns:
        The definitions, sorted by name; empty for an agent that starts none.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: A role the agent may start is played by no other agent.

    """
    if not isinstance(plugin, Path) or not isinstance(launched, AgentDefinition):
        argument_error: str = "started_agents requires the plugin Path and an AgentDefinition"
        raise TypeError(argument_error)
    if not launched.starts_roles:
        return ()
    wanted: frozenset[str] = frozenset(launched.starts_roles)
    found: list[AgentDefinition] = []
    path: Path
    for path in sorted((plugin / "agents").glob("*.md")):
        fields: dict[str, object]
        fields, _ = split_front_matter(path.read_text(encoding="utf-8"), f"agent {path.stem}")
        role: object = fields.get("role")
        if isinstance(role, str) and role in wanted and path.stem != launched.name:
            found.append(load_agent(plugin, path.stem))
    unplayed: list[str] = sorted(wanted - {agent.role for agent in found if agent.role is not None})
    if unplayed:
        message: str = f"agent {launched.name} may start roles no agent plays: {unplayed}"
        raise ValueError(message)
    return tuple(found)


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


def _skill_names(agent: AgentDefinition, launch: Launch) -> tuple[str, ...]:
    """List the skills an agent is given: its own, then the Epic's expertise when it takes it.

    Returns:
        The skill names in order, each once.

    """
    extra: tuple[str, ...] = launch.expertise if agent.epic_expertise is not None else ()
    return tuple(dict.fromkeys((*agent.skills, *extra)))


def _entry(agent: AgentDefinition, launch: Launch) -> dict[str, JsonValue]:
    """Build the fields of an ``agents.json`` entry that every agent's entry carries.

    Returns:
        The description, model, effort and, where its definition states them, the turn limit and
        the MCP server names.

    """
    entry: dict[str, JsonValue] = {"description": agent.description}
    if agent.max_turns is not None:
        entry["maxTurns"] = agent.max_turns
    if agent.mcp_servers is not None:
        entry["mcpServers"] = list(agent.mcp_servers)
    entry["model"] = launch_model(agent, launch)
    entry["effort"] = agent.effort
    return entry


def _qualified(name: str) -> str:
    """Name a skill the way a started agent's ``skills`` list must: with its plugin.

    Returns:
        The name unchanged when qualified, else qualified with this plugin.

    """
    return name if skill_plugin(name) is not None else f"{PLUGIN_NAME}:{name}"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def definitions(
    roots: SkillRoots,
    launched: AgentDefinition,
    started: tuple[AgentDefinition, ...],
    launch: Launch,
) -> dict[str, JsonValue]:
    """Build the ``agents.json`` of one session: the launched agent and every agent it may start.

    The launched agent's prompt ends with the full text of its skills and it has no ``skills``
    list, because Claude Code preloads none for the agent a session is launched as. An agent it
    may start keeps its ``skills`` list, which Claude Code does preload, and is denied the Agent
    tool. Both are given the Epic's expertise skills when their definition takes it.

    Returns:
        The definitions keyed by the name the session knows each agent by.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: The launched agent may start agents but does not list its own tools.

    """
    if (
        not isinstance(roots, SkillRoots)
        or not isinstance(launched, AgentDefinition)
        or not isinstance(launch, Launch)
        or not all(isinstance(agent, AgentDefinition) for agent in started)
    ):
        argument_error: str = "definitions requires SkillRoots, AgentDefinitions and a Launch"
        raise TypeError(argument_error)
    skills: list[Skill] = load_skills(roots, _skill_names(launched, launch))
    main: dict[str, JsonValue] = _entry(launched, launch)
    tools: list[str] | None = list(launched.tools) if launched.tools is not None else None
    if started:
        if tools is None:
            message: str = f"agent {launched.name} may start agents, so it must list its tools"
            raise ValueError(message)
        names: str = ", ".join(f"{AGENT_PREFIX}{agent.name}" for agent in started)
        tools = [tool for tool in tools if tool.split("(", 1)[0] != AGENT_TOOL]
        tools.append(f"{AGENT_TOOL}({names})")
    if tools is not None:
        main["tools"] = list(tools)
    if launched.disallowed_tools is not None:
        main["disallowedTools"] = list(launched.disallowed_tools)
    main["prompt"] = "\n\n".join(part for part in (launched.body, skills_text(skills)) if part)
    result: dict[str, JsonValue] = {f"{AGENT_PREFIX}{launched.name}": main}
    agent: AgentDefinition
    for agent in started:
        entry: dict[str, JsonValue] = _entry(agent, launch)
        if agent.tools is not None:
            entry["tools"] = list(agent.tools)
        entry["disallowedTools"] = list(dict.fromkeys((*(agent.disallowed_tools or ()), AGENT_TOOL)))
        helper_skills: list[str] = [_qualified(skill.name) for skill in load_skills(roots, _skill_names(agent, launch))]
        if helper_skills:
            entry["skills"] = list(helper_skills)
        entry["prompt"] = agent.body
        result[f"{AGENT_PREFIX}{agent.name}"] = entry
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
def session_settings(
    config: Path,
    plugin: Path,
    launched: AgentDefinition,
    *,
    starts_agents: bool,
) -> dict[str, JsonValue]:
    """Build the settings file of one session.

    Every session has the safety hooks. A session that may start agents is limited to one layer
    of started agents, each started in the foreground. A session that is given expertise while
    it works takes a whole skill as the output of one command.

    Returns:
        The session's settings.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not isinstance(config, Path)
        or not isinstance(plugin, Path)
        or not isinstance(launched, AgentDefinition)
        or not isinstance(starts_agents, bool)
    ):
        argument_error: str = "session_settings requires two Paths, an AgentDefinition and a flag"
        raise TypeError(argument_error)
    settings: dict[str, JsonValue] = safety_settings(config, plugin)
    if starts_agents:
        settings["env"] = dict(STARTER_ENV)
    if launched.epic_expertise == LIVE_EXPERTISE:
        settings[BASH_OUTPUT_KEY] = BASH_OUTPUT_LIMIT
    return settings


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def plugin_paths(config: Path, plugin: Path, skills: list[str]) -> list[Path]:
    """Resolve the installed plugins required by a session's skills.

    Returns:
        The current plugin followed by the other plugins the skills are qualified with.

    """
    wanted: set[str] = {owner for skill in skills if (owner := skill_plugin(skill)) is not None} - {PLUGIN_NAME}
    return [plugin, *(installed_plugin(config, name) for name in sorted(wanted))]


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


def _denied(launched: AgentDefinition, *, starts_agents: bool) -> list[str]:
    """List the tools the command line denies one session.

    Every session is denied the driver's list, the Agent tool and questions to the user. A
    session that may start agents keeps the Agent tool, and keeps SendMessage when its
    definition lists it, so it can continue an agent it started.

    Returns:
        The denied tool names, in the driver's order.

    """
    denied: list[str] = list(denied_tools())
    if not starts_agents:
        return [*denied, AGENT_TOOL, ASK_TOOL]
    if SEND_MESSAGE_TOOL in (launched.tools or ()):
        denied = [tool for tool in denied if tool != SEND_MESSAGE_TOOL]
    return [*denied, ASK_TOOL]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def prepare(plugin: Path, config: Path, directory: Path, step: AgentStep, launch: Launch) -> list[str]:
    """Write private session configuration and construct Claude CLI arguments.

    Returns:
        Explicit arguments selecting the agent, settings and MCP configuration.

    Raises:
        TypeError: Session inputs do not satisfy the preparation contract.

    """
    if not all(isinstance(path, Path) for path in (plugin, config, directory)):
        message: str = "Session plugin, config, and directory must be Paths"
        raise TypeError(message)
    if not isinstance(step, AgentStep) or not isinstance(launch, Launch):
        message = "Session preparation requires an AgentStep and a Launch"
        raise TypeError(message)
    named: str = os.environ.get(CONTROL_REPO_ENV, "").strip()
    roots: SkillRoots = SkillRoots(plugin, config, Path(named) if named else None)
    launched: AgentDefinition = load_agent(plugin, step.agent)
    started: tuple[AgentDefinition, ...] = started_agents(plugin, launched)
    starts_agents: bool = bool(started)
    agents: dict[str, JsonValue] = definitions(roots, launched, started, launch)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json(directory / "agents.json", agents)
    write_json(directory / "settings.json", session_settings(config, plugin, launched, starts_agents=starts_agents))
    command = [
        "--agents",
        str(directory / "agents.json"),
        "--agent",
        f"{AGENT_PREFIX}{step.agent}",
        "--model",
        launch_model(launched, launch),
        "--effort",
        launched.effort,
        "--setting-sources",
        "project",
        "--settings",
        str(directory / "settings.json"),
        "--strict-mcp-config",
    ]
    everyone: tuple[AgentDefinition, ...] = (launched, *started)
    names: list[str] = list(dict.fromkeys(name for agent in everyone for name in (agent.mcp_servers or ())))
    if names:
        path = directory / "mcp.json"
        write_json(
            path,
            {"mcpServers": mcp_servers(Path(os.environ[CONTROL_REPO_ENV]), config, names)},
        )
        path.chmod(0o600)
        command.extend(["--mcp-config", str(path)])
    skills: list[str] = [skill for agent in everyone for skill in _skill_names(agent, launch)]
    for path in plugin_paths(config, plugin, skills):
        command.extend(["--plugin-dir", str(path)])
    command.extend([
        "--permission-mode",
        "bypassPermissions",
        "--disallowedTools",
        *_denied(launched, starts_agents=starts_agents),
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
