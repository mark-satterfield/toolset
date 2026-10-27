"""The launcher: a session run as a predefined agent, its settings, and fact-only briefs.

A session is launched as the predefined agent under the plugin's name,
``agent-teams-workforce:<name>``: it loads only project settings, so the user-level agent copies
are not registered, and Claude Code registers a plugin agent only under that prefix. Claude Code
loads the agent's definition, preloads the skills its front matter lists, and applies its tools
and effort; it ignores the ``mcpServers`` of a plugin agent, so the launcher passes the session's
MCP configuration, and no other MCP server loads. A session that cannot start another agent gets
only its own agent's servers, and a plugin directory that lists only the skills its agent's
definition names; a session that can start agents gets every server the plugin's agents declare
and the whole plugin, since the agents it starts run in it. The launcher passes no agent or
skill text.
"""

from __future__ import annotations

import functools
import json
import os
import shlex
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final

from typeguard import CollectionCheckStrategy, check_type, typechecked

from . import portfolio_bootstrap  # ruff: ignore[unused-import] - Imported for its sys.path setup.

# isort: split
import strictschema

from .frontmatter import split_front_matter
from .io import JsonValue, json_object, write_json
from .models import AgentStep
from .step_journal import AGENT_PREFIX
from .tool_locks import control_repo

SAFETY_HOOKS = frozenset({
    "no-verify-blocker.sh",
    "pipeline-run-blocker.sh",
    "bd-init-blocker.sh",
    "aws-profile-required.sh",
})

BACKGROUND_TASKS_ENV: Final = "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"
SESSION_ENV: Final[Mapping[str, str]] = MappingProxyType({BACKGROUND_TASKS_ENV: "1"})
"""Every session's settings: every start blocks."""
BASH_OUTPUT_KEY: Final = "bashOutputMaxChars"
BASH_OUTPUT_LIMIT: Final = 128_000
"""Claude Code's largest inline command output, so a command's output is not cut to a preview."""
SESSION_LIMIT_KEY: Final = "x-sessionLimit"
"""The agent front-matter key stating the hard limit of the agent's sessions, in seconds."""
MCP_SERVERS_KEY: Final = "mcpServers"
"""The agent front-matter key naming the MCP servers the agent's tools reach."""
TOOLS_KEY: Final = "tools"
"""The agent front-matter key holding the agent's tool allow-list; absent, the agent has every tool."""
DISALLOWED_TOOLS_KEY: Final = "disallowedTools"
"""The agent front-matter key holding the tools the agent is denied."""
STARTING_TOOLS: Final = frozenset({"Agent", "Workflow"})
"""The tools with which a session starts other agents in itself."""
PRELOADED_SKILLS_KEY: Final = "skills"
"""The agent front-matter key naming the skills preloaded into the agent's context."""
ON_DEMAND_SKILLS_KEY: Final = "x-onDemandSkills"
"""The agent front-matter key naming the skills the agent may load itself with the Skill tool."""
SKILL_FILE: Final = "SKILL.md"
"""The file by which Claude Code finds a skill in a plugin's skill folder."""
SKILLS_FOLDER: Final = "skills"
LISTED_FOLDERS: Final = frozenset({"commands", "workflows"})
"""The plugin folders whose files Claude Code lists to the model beside the skills, by file stem."""
SESSION_PLUGIN: Final = ".plugin"
"""The folder in a session's directory that holds the plugin as that session sees it."""
DISABLE_BUNDLED_SKILLS_KEY: Final = "disableBundledSkills"
CONFIG_DIR_ENV: Final = "CLAUDE_CONFIG_DIR"
GLOBAL_CONFIG_NAME: Final = ".claude.json"
"""Claude Code's global configuration file, which holds the user-scope MCP server definitions."""
BRIEF_SCHEMA: Final[Path] = (
    Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "schemas" / "agent-brief.schema.json"
)
"""The contract of the brief every session is sent, which :func:`brief` checks before a session starts."""


class PipelineStoppedError(RuntimeError):
    """The supervisor requested cooperative shutdown between agent steps."""


class SessionCleanupError(RuntimeError):
    """Session finalization failed; original execution evidence remains attached."""


class SessionSetupError(RuntimeError):
    """Required session configuration or preparation failed before agent launch."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class AgentDefinition:
    """The fields of one agent definition file the launcher decides something with.

    ``model`` drives the Fable fallback, ``role`` the matrix role and ``session_limit`` (front
    matter ``x-sessionLimit``, seconds) the hard limit of the agent's sessions; an agent that states
    none runs under the driver surface's ``ATW_SESSION_LIMIT``. ``starts_agents`` tells whether the
    agent's tools include one that starts other agents (``Agent`` or ``Workflow``, or no
    ``tools`` allow-list at all); ``servers`` are its front matter ``mcpServers``; ``skills`` are
    the plain names of this plugin's skills its front matter ``skills`` and ``x-onDemandSkills``
    name. Claude Code applies the agent's tools; the launcher only reads them.
    """

    name: str
    model: str
    role: str | None
    starts_agents: bool
    servers: tuple[str, ...]
    skills: frozenset[str]
    session_limit: int | None = None

    def __post_init__(self) -> None:
        """Validate every constructed field."""
        check_type(self.name, str)
        check_type(self.model, str)
        check_type(self.role, str | None)
        check_type(self.starts_agents, bool)
        check_type(self.servers, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.skills, frozenset[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.session_limit, int | None)


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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def _names(metadata: Mapping[str, JsonValue], key: str, agent: str) -> tuple[str, ...]:
    """Read a front matter field that lists names.

    Returns:
        The names, in order; none when the field is absent.

    Raises:
        TypeError: The field is not a list of names.

    """
    value: JsonValue = metadata.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        message: str = f"agent {agent} {key} must be a list of names"
        raise TypeError(message)
    return tuple(check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def _tools(metadata: Mapping[str, JsonValue], key: str, agent: str) -> frozenset[str] | None:
    """Read a front matter tool field: a comma-separated line or a list of tool names.

    Returns:
        The tool names; None when the field is absent. A field that is neither text nor a list
        of names fails in :func:`_names`.

    """
    value: JsonValue = metadata.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return frozenset(word.strip() for word in value.split(",") if word.strip())
    return frozenset(_names(metadata, key, agent))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_agent(plugin: Path, name: str) -> AgentDefinition:
    """Read the fields of one agent definition file of the plugin the launcher decides with.

    Returns:
        The validated fields.

    Raises:
        TypeError: An argument or a front matter field has the wrong type.
        ValueError: The front matter is missing, states no model, or states a session limit that
            is not a positive number of seconds.

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
    limit: JsonValue = metadata.get(SESSION_LIMIT_KEY)
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0):
        message = f"agent {name} {SESSION_LIMIT_KEY} must be a positive whole number of seconds"
        raise ValueError(message)
    allowed: frozenset[str] = _tools(metadata, TOOLS_KEY, name) or STARTING_TOOLS
    denied: frozenset[str] = _tools(metadata, DISALLOWED_TOOLS_KEY, name) or frozenset()
    named: tuple[str, ...] = _names(metadata, PRELOADED_SKILLS_KEY, name) + _names(
        metadata,
        ON_DEMAND_SKILLS_KEY,
        name,
    )
    return AgentDefinition(
        name=name,
        model=model.strip(),
        role=role,
        starts_agents=bool((allowed - denied) & STARTING_TOOLS),
        servers=_names(metadata, MCP_SERVERS_KEY, name),
        skills=frozenset(skill.removeprefix(AGENT_PREFIX) for skill in named if skill.startswith(AGENT_PREFIX)),
        session_limit=limit,
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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def safety_settings(config: Path) -> dict[str, JsonValue]:
    """Select the owner's safety hooks and take the control repository's edit hooks.

    Returns:
        Session settings holding the selected pre-tool hooks of ``<config>/settings.json`` and
        every post-tool hook group ``<control>/.claude/settings.json`` declares.

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
    project_hooks = json_object(read_json(control_repo() / ".claude" / "settings.json").get("hooks", {}))
    edit_hooks: list[JsonValue] = list(
        check_type(
            project_hooks.get("PostToolUse", []),
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
    )
    return {"hooks": {"PreToolUse": selected, "PostToolUse": edit_hooks}}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def session_settings(config: Path) -> dict[str, JsonValue]:
    """Build the settings file of one session.

    Every session has the safety hooks and the control repository's edit hooks, starts every
    agent in the foreground, takes a command's output whole, and loads none of the skills
    bundled with Claude Code.

    Returns:
        The session's settings.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(config, Path):
        argument_error: str = "session_settings requires the config Path"
        raise TypeError(argument_error)
    settings: dict[str, JsonValue] = safety_settings(config)
    settings["env"] = dict(SESSION_ENV)
    settings[BASH_OUTPUT_KEY] = BASH_OUTPUT_LIMIT
    settings[DISABLE_BUNDLED_SKILLS_KEY] = True
    return settings


@functools.cache
def declared_servers(plugin: Path) -> tuple[str, ...]:
    """Name every MCP server some agent of the plugin declares in its front matter ``mcpServers``.

    An agent started in a session reaches only the servers of that session, and a session that can
    start agents may start any agent of the plugin, so such a session is given the union of all
    the agents' servers.

    Returns:
        The server names, sorted; an agent whose ``mcpServers`` is not a list of names fails the
        type check.

    """
    names: set[str] = set()
    for path in sorted((plugin / "agents").glob("*.md")):
        fields: dict[str, object]
        fields, _ = split_front_matter(path.read_text(encoding="utf-8"), f"agent {path.stem}")
        declared: object = fields.get(MCP_SERVERS_KEY, [])
        names.update(check_type(declared, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS))
    return tuple(sorted(names))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def global_config_file(config: Path) -> Path:
    """Locate Claude Code's global configuration file for ``config``, the configuration directory.

    Returns:
        ``<config>/.claude.json`` when ``CLAUDE_CONFIG_DIR`` is set, otherwise ``~/.claude.json``.

    """
    return config / GLOBAL_CONFIG_NAME if os.environ.get(CONFIG_DIR_ENV) else Path.home() / GLOBAL_CONFIG_NAME


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def session_servers(plugin: Path, config: Path, agent: AgentDefinition) -> dict[str, JsonValue]:
    """Build the MCP configuration of one session from the user-scope server definitions.

    A session loads only project settings, so the user-scope servers do not load by themselves.
    The session gets its agent's own ``mcpServers``, or, when its agent can start agents, every
    server the plugin's agents declare (:func:`declared_servers`). Each is taken from the global
    configuration file; a name it does not define is left out, as an interactive session would
    leave it out.

    Returns:
        ``{"mcpServers": {name: definition}}`` for every server of the session the user defines.

    """
    defined: dict[str, JsonValue] = json_object(read_json(global_config_file(config)).get(MCP_SERVERS_KEY, {}))
    names: tuple[str, ...] = declared_servers(plugin) if agent.starts_agents else agent.servers
    return {MCP_SERVERS_KEY: {name: defined[name] for name in names if name in defined}}


def _link(target: Path, link: Path) -> None:
    """Make ``link`` a symbolic link to ``target``."""
    link.symlink_to(target, target_is_directory=target.is_dir())


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def _skill_folder(source: Path, folder: Path, skills: frozenset[str]) -> None:
    """Build a session's skill folder: a named skill whole, any other without its ``SKILL.md``.

    A skill folder with no ``SKILL.md`` is not listed, while its scripts, schemas and references
    stay at their paths for the commands and skills that use them.
    """
    folder.mkdir()
    entry: Path
    for entry in sorted(source.iterdir()):
        if entry.name in skills or not entry.is_dir():
            _link(entry, folder / entry.name)
            continue
        (folder / entry.name).mkdir()
        part: Path
        for part in sorted(entry.iterdir()):
            if part.name != SKILL_FILE:
                _link(part, folder / entry.name / part.name)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def session_plugin(plugin: Path, directory: Path, agent: AgentDefinition) -> Path:
    """Name the plugin folder a session loads, building it when the session lists only some skills.

    A session whose agent can start agents loads the whole plugin, since the agents it starts run
    with their skills in it. Any other session loads ``<directory>/.plugin``, rebuilt for each
    launch: every entry of the plugin as a link, except that it lists only the skills, commands
    and workflows the agent's definition names (:func:`_skill_folder`; a command or workflow is
    named by its file stem).

    Returns:
        The plugin folder to pass with ``--plugin-dir``.

    """
    if agent.starts_agents:
        return plugin
    source: Path = plugin.resolve()
    built: Path = directory / SESSION_PLUGIN
    if built.exists():
        shutil.rmtree(built)
    built.mkdir(mode=0o700)
    entry: Path
    for entry in sorted(source.iterdir()):
        if entry.name == SKILLS_FOLDER:
            _skill_folder(entry, built / entry.name, agent.skills)
        elif entry.name in LISTED_FOLDERS:
            (built / entry.name).mkdir()
            listed: Path
            for listed in sorted(entry.iterdir()):
                if listed.stem in agent.skills:
                    _link(listed, built / entry.name / listed.name)
        else:
            _link(entry, built / entry.name)
    return built


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def prepare(plugin: Path, config: Path, directory: Path, step: AgentStep, launch: Launch) -> list[str]:
    """Write private session settings and construct Claude CLI arguments.

    Returns:
        Explicit arguments selecting the agent by its name under the plugin prefix, the model,
        the settings, the MCP servers (and no other) and the session's plugin folder.

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
    write_json(directory / "settings.json", session_settings(config))
    write_json(directory / "mcp.json", session_servers(plugin, config, launched))
    command: list[str] = [
        "--agent",
        f"{AGENT_PREFIX}{step.agent}",
        "--model",
        launch_model(launched, launch),
        "--setting-sources",
        "project",
        "--settings",
        str(directory / "settings.json"),
        "--mcp-config",
        str(directory / "mcp.json"),
        "--strict-mcp-config",
        "--plugin-dir",
        str(session_plugin(plugin, directory, launched)),
        "--permission-mode",
        "bypassPermissions",
    ]
    command.extend(arg for path in step.add_dirs for arg in ("--add-dir", str(path.resolve())))
    return command


@functools.cache
def _brief_contract() -> dict[str, JsonValue]:
    """Read the brief's contract file once per process.

    Returns:
        The schema of :data:`BRIEF_SCHEMA`.

    """
    return json_object(json.loads(BRIEF_SCHEMA.read_text(encoding="utf-8")))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def brief(
    bead: str,
    step: AgentStep,
    inputs: list[tuple[str, Path]],
    *,
    corrective: bool = False,
) -> str:
    """Serialize the one-line outcome and selected inputs for an agent.

    The brief is ``agent-brief.schema.json`` (:data:`BRIEF_SCHEMA`), and is checked against it.
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
    strictschema.validate(facts, _brief_contract(), location=BRIEF_SCHEMA)
    return json.dumps(facts, ensure_ascii=False)
