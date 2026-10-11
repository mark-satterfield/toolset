#!/usr/bin/env python3
"""Read model declarations and conservatively classify workflow reachability.

No workflow is evaluated. Literal agent names include the existing dynamic-selection
rosters; computed dispatches remain uncertain and therefore select an Opus session.
The output is the fable inventory contract the artifact-handoff skill owns
(skills/artifact-handoff/schemas/fable-recovery.schema.json, generated into fable_contract.py).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# The fable inventory contract is generated into the artifact-handoff skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "artifact-handoff" / "scripts"))

# isort: split
from fable_contract import (
    AGENT_TYPE_PREFIX,
    FABLE_MODEL,
    REASON_AGENT_MODEL_UNAVAILABLE,
    REASON_COMPUTED_AGENT,
    REASON_COMPUTED_CHILD,
    REASON_WORKFLOW_UNAVAILABLE,
    SCHEMA_VERSION,
    SESSION_MODEL_OPUS,
    SESSION_MODEL_SONNET,
    ModelInventory,
    SessionModel,
    WorkflowInventory,
)

QUOTED: Final[re.Pattern[str]] = re.compile(r"(['\"])([a-z][a-z0-9:-]*)\1")
AGENT_VALUE: Final[re.Pattern[str]] = re.compile(r"\bagentType\s*:\s*([^\n]+)")
CHILD_CALL: Final[re.Pattern[str]] = re.compile(
    r"(?<!function )\b(?:settleWorkflow|workflow|fableWorkflow)\s*\(\s*([^\n]+)",
)
FRONTMATTER: Final[re.Pattern[str]] = re.compile(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", re.DOTALL)
MODEL_FIELD: Final[re.Pattern[str]] = re.compile(r"^model:\s*['\"]?([\w.-]+)['\"]?\s*(?:#.*)?$", re.MULTILINE)
FABLE_SHARED_BLOCK: Final[re.Pattern[str]] = re.compile(
    r"// ===== SHARED BLOCK fable .*?// ===== SHARED BLOCK fable — END =====",
    re.DOTALL,
)
FORWARDED_AGENT_VALUES: Final[tuple[str, ...]] = ("o.agentType || null", "opts.agentType || null", "{ type:")
FORWARDED_CHILD_PREFIX: Final[str] = "name, "
EMPTY_CALL_PREFIX: Final[str] = ")"


@dataclass(frozen=True)
class WorkflowFacts:
    """The literal agents and child workflows one workflow names, and why reachability is uncertain."""

    agents: frozenset[str]
    children: frozenset[str]
    unknown: frozenset[str]


def agent_models(root: Path) -> dict[str, str]:
    """Read the scalar model field inside each agent's YAML frontmatter.

    Args:
        root: The plugin root that holds the ``agents`` folder.

    Returns:
        Each agent's name (file stem) mapped to its declared model.

    Raises:
        ValueError: When an agent has no frontmatter or no scalar model, or no agent exists.

    """
    models: dict[str, str] = {}
    for path in sorted((root / "agents").glob("*.md")):
        text: str = path.read_text(encoding="utf-8")
        front: re.Match[str] | None = FRONTMATTER.match(text)
        if front is None:
            message: str = f"Missing frontmatter: {path}"
            raise ValueError(message)
        model: re.Match[str] | None = MODEL_FIELD.search(front[1])
        if model is None:
            message = f"Missing scalar model declaration: {path}"
            raise ValueError(message)
        models[path.stem] = model[1]
    if not models:
        message = f"No agent definitions in {root / 'agents'}"
        raise ValueError(message)
    return models


def workflow_facts(path: Path, models: dict[str, str]) -> WorkflowFacts:
    """Overapproximate one workflow's literal domains, retaining uncertainty for computed calls.

    Args:
        path: The workflow script.
        models: Each agent's declared model, from :func:`agent_models`.

    Returns:
        The agents and child workflows the script names literally, and the uncertainty reasons.

    """
    source: str = FABLE_SHARED_BLOCK.sub("", path.read_text(encoding="utf-8"))
    literals: set[str] = {match[2].removeprefix(AGENT_TYPE_PREFIX) for match in QUOTED.finditer(source)}
    agents: set[str] = literals & models.keys()
    unknown: set[str] = set()
    children: set[str] = set()
    for match in AGENT_VALUE.finditer(source):
        value: str = match[1].strip()
        literal: re.Match[str] | None = QUOTED.match(value)
        if literal is not None:
            if literal[2].removeprefix(AGENT_TYPE_PREFIX) not in models:
                unknown.add(REASON_AGENT_MODEL_UNAVAILABLE.format(agent=literal[2]))
        elif not value.startswith(FORWARDED_AGENT_VALUES):
            unknown.add(REASON_COMPUTED_AGENT)
    for match in CHILD_CALL.finditer(source):
        call: str = match[1].strip()
        child: re.Match[str] | None = QUOTED.match(call)
        if child is not None:
            children.add(child[2].removeprefix(AGENT_TYPE_PREFIX))
        elif call.startswith(FORWARDED_CHILD_PREFIX):
            continue
        elif not call.startswith(EMPTY_CALL_PREFIX):
            unknown.add(REASON_COMPUTED_CHILD)
    return WorkflowFacts(agents=frozenset(agents), children=frozenset(children), unknown=frozenset(unknown))


def workflow_inventory(name: str, facts: dict[str, WorkflowFacts], models: dict[str, str]) -> WorkflowInventory:
    """Walk one workflow's reachable children and classify the session model it needs.

    Args:
        name: The workflow (file stem) to classify.
        facts: Every workflow's facts, keyed by name.
        models: Each agent's declared model.

    Returns:
        The workflow's inventory entry.

    """
    seen: set[str] = set()
    agents: set[str] = set()
    unknown: set[str] = set()
    pending: list[str] = [name]
    while pending:
        child: str = pending.pop()
        if child in seen:
            continue
        seen.add(child)
        item: WorkflowFacts | None = facts.get(child)
        if item is None:
            unknown.add(REASON_WORKFLOW_UNAVAILABLE.format(workflow=child))
            continue
        agents.update(item.agents)
        unknown.update(f"{child}: {reason}" for reason in item.unknown)
        pending.extend(item.children)
    fable: list[str] = sorted(AGENT_TYPE_PREFIX + agent for agent in agents if models[agent] == FABLE_MODEL)
    session_model: SessionModel = SESSION_MODEL_OPUS if fable or unknown else SESSION_MODEL_SONNET
    return {
        "fableAgentTypes": fable,
        "unknownReachability": bool(unknown),
        "uncertaintyReasons": sorted(unknown),
        "sessionModel": session_model,
        "children": sorted(facts[name].children),
    }


def inventory(root: Path) -> ModelInventory:
    """Build the plugin's fable model inventory.

    Args:
        root: The plugin root that holds the ``agents`` and ``workflows`` folders.

    Returns:
        The inventory the fable contract defines.

    Raises:
        ValueError: When the plugin has no agents or no workflows, or an agent lacks a model.

    """
    models: dict[str, str] = agent_models(root)
    facts: dict[str, WorkflowFacts] = {
        path.stem: workflow_facts(path, models) for path in sorted((root / "workflows").glob("*.js"))
    }
    if not facts:
        message: str = f"No workflows in {root / 'workflows'}"
        raise ValueError(message)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "fableAgentTypes": sorted(AGENT_TYPE_PREFIX + name for name, model in models.items() if model == FABLE_MODEL),
        "workflows": {name: workflow_inventory(name, facts, models) for name in facts},
    }


def main() -> None:
    """Print the plugin's fable model inventory as JSON on stdout.

    Raises:
        TypeError: When the parsed plugin root is not a path.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=Path(__file__).resolve().parent.parent)
    options: argparse.Namespace = parser.parse_args()
    plugin_root: object = options.plugin_root
    if not isinstance(plugin_root, Path):
        message: str = f"--plugin-root must be a path, got {plugin_root!r}"
        raise TypeError(message)
    sys.stdout.write(json.dumps(inventory(plugin_root), sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
