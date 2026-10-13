"""Build the launch artifacts of real and made-up agents; never start an agent, workflow, or pipeline.

For every agent the flows name: its definition states a model and an effort, and the launched
agent's prompt holds the text of each of its front matter skills exactly once. For three real
agents of different kinds, the whole argument list is the one a session without started agents
has always been given. For a made-up agent that may start others: the allowlist, the dropped
Agent denial, the nesting settings, the started agents' skills and the Epic's expertise. For every
real definition that states a role, the roles it may start or how it takes expertise: the fields
are valid, and an agent that may start others is given exactly the agents that play those roles,
each with skills a session can find.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Final
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))

from driver_surface_types import CONTROL_REPO_ENV
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.core.agent_context import (
    AGENT_PREFIX,
    BACKGROUND_TASKS_ENV,
    BASH_OUTPUT_KEY,
    BASH_OUTPUT_LIMIT,
    SPAWN_DEPTH_ENV,
    AgentDefinition,
    Launch,
    brief,
    definitions,
    load_agent,
    prepare,
    started_agents,
)
from orchestrator.core.driver_contracts import denied_tools
from orchestrator.core.frontmatter import split_front_matter, string_list
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import AgentStep
from orchestrator.core.skills import (
    MATRIX_ENV,
    Skill,
    SkillRoots,
    epic_expertise,
    load_skills,
    matching_skills,
    skill_block,
    skill_location,
)
from step_journal_contract import StepId

PLUGIN: Final[Path] = Path(__file__).resolve().parents[2]
QUOTED: Final[re.Pattern[str]] = re.compile(r'"([a-z0-9][a-z0-9-]+)"')
MANY_SKILLS: Final = "event-schema-designer"
REVIEWER: Final = "architecture-boundary-guardian"
UNQUALIFIED_SKILLS_AGENT: Final = "polyrepo-steward"
ROLE_FIELDS: Final[frozenset[str]] = frozenset({"role", "startsRoles", "epicExpertise"})
STEP_ID: Final = "0f8fad5b-d9cb-469f-a165-70867728950e"
ALPHA: Final = "The alpha fixture sentence."
BETA: Final = "The beta fixture sentence."


def flow_agents() -> list[str]:
    """Name the agents the flows launch: every quoted agent file name in the flow sources.

    Returns:
        The agent names, sorted.

    """
    names: set[str] = {path.stem for path in (PLUGIN / "agents").glob("*.md")}
    quoted: set[str] = set()
    source: Path
    for source in sorted((PLUGIN / "orchestrator" / "flows").glob("*.py")):
        quoted.update(QUOTED.findall(source.read_text(encoding="utf-8")))
    return sorted(names & quoted)


def read_object(path: Path) -> dict[str, JsonValue]:
    """Read one generated JSON file.

    Returns:
        The file's JSON object.

    """
    return json_object(json.loads(path.read_text(encoding="utf-8")))


def step_for(agent: str, root: Path) -> AgentStep:
    """Build a step that launches ``agent`` and reads one extra directory.

    Returns:
        The step.

    """
    return AgentStep("probe", agent, (), root / "output.json", "Prepare only.", root / "schema.json", (root,))


def check_skill_text(roots: SkillRoots) -> None:
    """Check that every agent the flows name is launched with the text of each of its skills once."""
    names: list[str] = flow_agents()
    require(names, "the flows name no agent")
    sizes: dict[str, int] = {}
    name: str
    for name in names:
        agent: AgentDefinition = load_agent(PLUGIN, name)
        entry: dict[str, JsonValue] = json_object(definitions(roots, agent, (), Launch())[f"{AGENT_PREFIX}{name}"])
        prompt: str = string_list([entry["prompt"]])[0]
        require("skills" not in entry, f"{name}: a launched agent carries no skills list")
        require(prompt.startswith(agent.body), f"{name}: the prompt must open with the definition's own text")
        require(entry["model"] == agent.model, f"{name}: the model is the one its definition states")
        require(entry["effort"] == agent.effort, f"{name}: the effort is the one its definition states")
        skills: list[Skill] = load_skills(roots, agent.skills)
        require(len(skills) == len(agent.skills), f"{name}: two of its skills are the same skill")
        skill: Skill
        for skill in skills:
            require(prompt.count(skill_block(skill)) == 1, f"{name}: skill {skill.name} is not in its prompt once")
            require(
                prompt.count(f"Base directory for this skill: {skill.directory}\n") == 1,
                f"{name}: skill {skill.name} does not name its base directory once",
            )
        sizes[name] = len(prompt.encode("utf-8")) - len(agent.body.encode("utf-8"))
    ordered: list[int] = sorted(sizes.values())
    largest: str = max(sizes, key=lambda agent_name: sizes[agent_name])
    report(
        f"PASS: {len(names)} agents the flows name hold each front matter skill's text once; "
        f"skill text added per prompt: median {ordered[len(ordered) // 2]} bytes, "
        f"largest {sizes[largest]} bytes ({largest})",
    )


def check_arguments(config: Path, root: Path) -> None:
    """Check the whole argument list and settings of real agents that start no other agent."""
    name: str
    for name in (MANY_SKILLS, REVIEWER, UNQUALIFIED_SKILLS_AGENT):
        agent: AgentDefinition = load_agent(PLUGIN, name)
        session: Path = root / name
        arguments: list[str] = prepare(PLUGIN, config, session, step_for(name, root), Launch())
        servers: list[str] = ["--mcp-config", str(session / "mcp.json")] if agent.mcp_servers else []
        expected: list[str] = [
            "--agents",
            str(session / "agents.json"),
            "--agent",
            f"{AGENT_PREFIX}{name}",
            "--model",
            agent.model,
            "--effort",
            agent.effort,
            "--setting-sources",
            "project",
            "--settings",
            str(session / "settings.json"),
            "--strict-mcp-config",
            *servers,
            "--plugin-dir",
            str(PLUGIN),
            "--permission-mode",
            "bypassPermissions",
            "--disallowedTools",
            *denied_tools(),
            "Agent",
            "AskUserQuestion",
            "--add-dir",
            str(root.resolve()),
        ]
        require(arguments == expected, f"{name}: the argument list changed: {arguments}")
        require(list(read_object(session / "agents.json")) == [f"{AGENT_PREFIX}{name}"], f"{name}: one agent defined")
        settings: dict[str, JsonValue] = read_object(session / "settings.json")
        require(list(settings) == ["hooks"], f"{name}: a session that starts no agent has only its hooks")
        if agent.mcp_servers:
            configured: dict[str, JsonValue] = json_object(read_object(session / "mcp.json")["mcpServers"])
            require(sorted(configured) == sorted(agent.mcp_servers), f"{name}: its MCP servers are configured")
    report(f"PASS: argument list and settings unchanged for {MANY_SKILLS}, {REVIEWER} and {UNQUALIFIED_SKILLS_AGENT}")


def check_started(roots: SkillRoots, agent: AgentDefinition) -> int:
    """Check the session definitions of one real agent that may start others.

    Returns:
        The number of agents it may start.

    """
    started: tuple[AgentDefinition, ...] = started_agents(PLUGIN, agent)
    require(
        {helper.role for helper in started} == set(agent.starts_roles),
        f"{agent.name}: the agents it may start play exactly the roles it names",
    )
    entries: dict[str, JsonValue] = definitions(roots, agent, started, Launch())
    keys: list[str] = [f"{AGENT_PREFIX}{helper.name}" for helper in started]
    require(sorted(entries) == sorted([f"{AGENT_PREFIX}{agent.name}", *keys]), f"{agent.name}: defined agents")
    tools: list[str] = string_list(json_object(entries[f"{AGENT_PREFIX}{agent.name}"])["tools"])
    require(f"Agent({', '.join(keys)})" in tools, f"{agent.name}: the allowlist names exactly the agents it may start")
    require("Agent" not in tools, f"{agent.name}: the Agent tool is given only as the allowlist")
    helper: AgentDefinition
    for helper in started:
        entry: dict[str, JsonValue] = json_object(entries[f"{AGENT_PREFIX}{helper.name}"])
        require("Agent" in string_list(entry["disallowedTools"]), f"{helper.name}: a started agent starts no agent")
        listed: list[str] = string_list(entry.get("skills"))
        require(len(listed) == len(load_skills(roots, helper.skills)), f"{helper.name}: every skill is listed once")
        skill: str
        for skill in listed:
            require(
                (skill_location(roots, skill)[0] / "SKILL.md").is_file(),
                f"{helper.name}: skill {skill} is not one a session can find under that name",
            )
    return len(started)


def check_roles(roots: SkillRoots) -> None:
    """Check every real definition that states a role, the roles it may start or how it takes expertise."""
    stated: int = 0
    starters: dict[str, int] = {}
    path: Path
    for path in sorted((PLUGIN / "agents").glob("*.md")):
        fields: dict[str, object]
        fields, _ = split_front_matter(path.read_text(encoding="utf-8"), f"agent {path.stem}")
        if not ROLE_FIELDS & set(fields):
            continue
        agent: AgentDefinition = load_agent(PLUGIN, path.stem)
        stated += 1
        if agent.starts_roles:
            require(agent.role is not None, f"{agent.name}: an agent that may start others states its own role")
            starters[agent.name] = check_started(roots, agent)
    require(stated > 0, "no real definition states a role")
    summary: str = ", ".join(f"{name} may start {count}" for name, count in sorted(starters.items())) or "none"
    report(f"PASS: {stated} real definitions state valid role fields; agents that may start others: {summary}")


def write_fixture(plugin: Path, config: Path) -> None:
    """Write a made-up plugin: an agent that may start two helpers, an unrelated agent and two skills."""
    agents: Path = plugin / "agents"
    agents.mkdir(parents=True)
    common: str = "model: sonnet\neffort: low\n"
    (agents / "lead.md").write_text(
        "---\ndescription: Lead\ntools: Read, Agent, SendMessage\nstartsRoles: [helper]\nmcpServers: first\n"
        f"epicExpertise: live\n{common}---\nLead the work.\n",
        encoding="utf-8",
    )
    (agents / "helper-one.md").write_text(
        "---\ndescription: One\ntools: Read\nrole: helper\nskills: [agent-teams-workforce:alpha]\n"
        "mcpServers: second\nepicExpertise: at-launch\nmodel: fable\neffort: high\n---\nHelp once.\n",
        encoding="utf-8",
    )
    (agents / "helper-two.md").write_text(
        f"---\ndescription: Two\nrole: helper\ndisallowedTools: Write\n{common}---\nHelp twice.\n",
        encoding="utf-8",
    )
    (agents / "other.md").write_text(f"---\ndescription: Other\nrole: other\n{common}---\nOther.\n", encoding="utf-8")
    (agents / "plain.md").write_text(f"---\ndescription: Plain\ntools: Read\n{common}---\nPlain.\n", encoding="utf-8")
    text: str
    skill: str
    for skill, text in (("alpha", ALPHA), ("beta", BETA)):
        (plugin / "skills" / skill).mkdir(parents=True)
        (plugin / "skills" / skill / "SKILL.md").write_text(
            f"---\nname: {skill}\ndescription: Fixture.\nexpertiseFor:\n  resourceTypes: [{skill}-table]\n"
            f"  terms: [{skill} billing]\n---\n{text} It lives in ${{CLAUDE_PLUGIN_ROOT}}.\n",
            encoding="utf-8",
        )
    config.mkdir()
    (config / ".claude.json").write_text(
        '{"mcpServers":{"first":{"command":"never-executed"},"second":{"command":"never-executed"}}}',
        encoding="utf-8",
    )


def check_starter(root: Path) -> None:
    """Check a made-up agent that may start others, and one that may not, in a made-up plugin."""
    plugin: Path = root / "plugin"
    config: Path = root / "config"
    write_fixture(plugin, config)
    launch: Launch = Launch(model_replacements={"fable": "opus"}, expertise=("beta",))
    session: Path = root / "lead"
    with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}):
        arguments: list[str] = prepare(plugin, config, session, step_for("lead", root), launch)
        plain: list[str] = prepare(plugin, config, root / "plain", step_for("plain", root), launch)
    denied: list[str] = arguments[arguments.index("--disallowedTools") + 1 : arguments.index("--add-dir")]
    require("Agent" not in denied, "a session that may start agents is not denied the Agent tool")
    require("SendMessage" not in denied, "a session whose definition lists SendMessage is not denied it")
    require(denied[-1] == "AskUserQuestion", "every session is denied questions to the user")
    require(
        denied == [tool for tool in denied_tools() if tool != "SendMessage"] + ["AskUserQuestion"],
        "the other denied tools are unchanged",
    )
    require(plain[plain.index("--add-dir") - 2 : plain.index("--add-dir")] == ["Agent", "AskUserQuestion"], "plain")
    require("env" not in read_object(root / "plain" / "settings.json"), "a plain session sets no nesting settings")
    agents: dict[str, JsonValue] = read_object(session / "agents.json")
    require(sorted(agents) == ["atw-helper-one", "atw-helper-two", "atw-lead"], f"defined agents: {sorted(agents)}")
    lead: dict[str, JsonValue] = json_object(agents["atw-lead"])
    require(lead["tools"] == ["Read", "SendMessage", "Agent(atw-helper-one, atw-helper-two)"], f"{lead['tools']}")
    prompt: str = string_list([lead["prompt"]])[0]
    require(prompt.count(BETA) == 1, "the Epic's expertise skill text is in the lead's prompt once")
    require(ALPHA not in prompt, "a helper's skill is not in the lead's prompt")
    require(f"It lives in {plugin.resolve()}." in prompt, "the plugin root variable is replaced in skill text")
    one: dict[str, JsonValue] = json_object(agents["atw-helper-one"])
    require(one["skills"] == ["agent-teams-workforce:alpha", "agent-teams-workforce:beta"], f"{one['skills']}")
    require(one["disallowedTools"] == ["Agent"], "a started agent is denied the Agent tool")
    require(one["model"] == "opus", "a started agent's model follows the launch's model replacements")
    require(one["effort"] == "high", "a started agent's effort is its definition's")
    require(one["prompt"] == "Help once.", "a started agent's prompt is its definition's own text")
    two: dict[str, JsonValue] = json_object(agents["atw-helper-two"])
    require("skills" not in two, "an agent that takes no expertise and lists no skill has no skills list")
    require(two["disallowedTools"] == ["Write", "Agent"], f"{two['disallowedTools']}")
    settings: dict[str, JsonValue] = read_object(session / "settings.json")
    require(settings["env"] == {SPAWN_DEPTH_ENV: "1", BACKGROUND_TASKS_ENV: "1"}, f"{settings.get('env')}")
    require(settings[BASH_OUTPUT_KEY] == BASH_OUTPUT_LIMIT, "live expertise raises the inline command output limit")
    servers: dict[str, JsonValue] = json_object(read_object(session / "mcp.json")["mcpServers"])
    require(sorted(servers) == ["first", "second"], "the session has the servers of every agent it may start")
    (plugin / "agents" / "lead.md").write_text(
        "---\ndescription: Lead\ntools: Read\nstartsRoles: [absent]\nmodel: sonnet\neffort: low\n---\nLead.\n",
        encoding="utf-8",
    )
    with expected_error(ValueError):
        prepare(plugin, config, root / "unplayed", step_for("lead", root), launch)
    report("PASS: allowlist, kept Agent and SendMessage, nesting settings, started agents' skills and MCP servers")
    check_expertise(plugin, root)


def check_expertise(plugin: Path, root: Path) -> None:
    """Check the expertise declarations, the Epic's recorded list and the brief's two new fields."""
    require(matching_skills(plugin, ["alpha-table"], "") == ("alpha",), "a resource type selects its skill")
    require(matching_skills(plugin, [], "Monthly Beta  billing.") == (), "a term matches as written, spaces included")
    require(matching_skills(plugin, [], "The BETA billing run.") == ("beta",), "a term matches whatever its case")
    require(matching_skills(plugin, ["gamma-table"], "alphabet billing") == (), "nothing declared, nothing selected")
    matrix: Path = root / "matrix.json"
    matrix.write_text(
        json.dumps({"nodes": {"prd:epic-1": {"kind": "prd", "bead": "epic-1", "expertise": ["beta"]}}}),
        encoding="utf-8",
    )
    require(epic_expertise("epic-1", {MATRIX_ENV: str(matrix)}) == ("beta",), "the PRD row's expertise list is read")
    require(epic_expertise("epic-2", {MATRIX_ENV: str(matrix)}) == (), "an Epic with no PRD row has no expertise")
    require(epic_expertise("epic-1", {}) == (), "no matrix named, no expertise")
    plain: AgentStep = step_for("plain", root)
    require(
        set(json_object(json.loads(brief("epic-1", plain, [])))) == {"bead", "inputs", "output", "outcome"},
        "a step with no request and no journal step sends the brief it always sent",
    )
    asked: AgentStep = AgentStep(
        "probe",
        "plain",
        (),
        root / "output.json",
        "Prepare only.",
        root / "schema.json",
        request="State what the lead asked.",
        journal_step=StepId(STEP_ID),
    )
    sent: dict[str, JsonValue] = json_object(json.loads(brief("epic-1", asked, [])))
    require(sent["request"] == "State what the lead asked.", "the brief carries the request")
    require(sent["step"] == STEP_ID, "the brief carries the journal step id")
    with expected_error(ValueError):
        AgentStep("probe", "plain", (), root / "o", "Outcome.", root / "s", journal_step=StepId("not-a-step-id"))
    report("PASS: expertise declarations, the Epic's recorded expertise, and the request and step brief fields")


def main() -> None:
    """Run the launcher checks against the real plugin and a made-up one."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-repo", required=True, type=Path)
    options: argparse.Namespace = parser.parse_args()
    named: Path = options.control_repo
    control: Path = named.resolve()
    config: Path = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser()
    directory: str
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {CONTROL_REPO_ENV: str(control)}):
        root: Path = Path(directory).resolve()
        check_skill_text(SkillRoots(PLUGIN, config, control))
        check_roles(SkillRoots(PLUGIN, config, control))
        check_arguments(config, root)
        check_starter(root)


if __name__ == "__main__":
    main()
