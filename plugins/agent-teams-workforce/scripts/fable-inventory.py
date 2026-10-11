#!/usr/bin/env python3
"""Read model declarations and conservatively classify workflow reachability.

No workflow is evaluated. Literal agent names include the existing dynamic-selection
rosters; computed dispatches remain uncertain and therefore select an Opus session.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from collections.abc import Mapping

PREFIX = "agent-teams-workforce:"
QUOTED = re.compile(r"(['\"])([a-z][a-z0-9:-]*)\1")
AGENT_VALUE = re.compile(r"\bagentType\s*:\s*([^\n]+)")
CHILD_CALL = re.compile(r"(?<!function )\b(?:settleWorkflow|workflow|fableWorkflow)\s*\(\s*([^\n]+)")


class WorkflowFacts(TypedDict):
    """Literal agents, child workflows and uncertainty reasons found in one workflow script."""

    agents: set[str]
    children: set[str]
    unknown: set[str]


class WorkflowResult(TypedDict):
    """The reachable Fable agents and the session model one workflow needs."""

    fableAgentTypes: list[str]
    unknownReachability: bool
    uncertaintyReasons: list[str]
    sessionModel: str
    children: list[str]


class Inventory(TypedDict):
    """The full inventory printed by this script."""

    schemaVersion: int
    fableAgentTypes: list[str]
    workflows: dict[str, WorkflowResult]


def agent_models(root: Path) -> dict[str, str]:
    """Read scalar model fields only inside each agent's YAML frontmatter.

    Returns:
        Each agent's file stem mapped to its declared model.

    Raises:
        ValueError: An agent has no frontmatter or no scalar model, or there are no agents.

    """
    models: dict[str, str] = {}
    for path in sorted((root / "agents").glob("*.md")):
        text: str = path.read_text(encoding="utf-8")
        front: re.Match[str] | None = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.DOTALL)
        if not front:
            message: str = f"Missing frontmatter: {path}"
            raise ValueError(message)
        model: re.Match[str] | None = re.search(
            r"^model:\s*['\"]?([\w.-]+)['\"]?\s*(?:#.*)?$",
            front[1],
            re.MULTILINE,
        )
        if not model:
            message = f"Missing scalar model declaration: {path}"
            raise ValueError(message)
        models[path.stem] = model[1]
    if not models:
        message = f"No agent definitions in {root / 'agents'}"
        raise ValueError(message)
    return models


def workflow_facts(path: Path, models: Mapping[str, str]) -> WorkflowFacts:
    """Overapproximate literal domains, retaining uncertainty for computed calls.

    Returns:
        The literal agents, child workflows and uncertainty reasons of the workflow.

    """
    source: str = re.sub(
        r"// ===== SHARED BLOCK fable .*?// ===== SHARED BLOCK fable — END =====",
        "",
        path.read_text(encoding="utf-8"),
        flags=re.DOTALL,
    )
    literals: set[str] = {match[2].removeprefix(PREFIX) for match in QUOTED.finditer(source)}
    agents: set[str] = literals & models.keys()
    unknown: set[str] = set()
    children: set[str] = set()
    for match in AGENT_VALUE.finditer(source):
        value: str = match[1].strip()
        literal: re.Match[str] | None = QUOTED.match(value)
        if literal:
            name: str = literal[2].removeprefix(PREFIX)
            if name not in models:
                unknown.add(f"agent model unavailable: {literal[2]}")
        elif not value.startswith(("o.agentType || null", "opts.agentType || null", "{ type:")):
            unknown.add("computed agent dispatch")
    for match in CHILD_CALL.finditer(source):
        value = match[1].strip()
        literal = QUOTED.match(value)
        if literal:
            children.add(literal[2].removeprefix(PREFIX))
        elif value.startswith("name, "):
            continue
        elif not value.startswith(")"):
            unknown.add("computed child workflow")
    return {"agents": agents, "children": children, "unknown": unknown}


def inventory(root: Path) -> Inventory:
    """Classify every workflow under the plugin root by the Fable agents it can reach.

    Returns:
        The inventory of Fable agent types and per-workflow results.

    Raises:
        ValueError: The plugin root has no workflows.

    """
    models: dict[str, str] = agent_models(root)
    facts: dict[str, WorkflowFacts] = {
        path.stem: workflow_facts(path, models) for path in sorted((root / "workflows").glob("*.js"))
    }
    if not facts:
        message: str = f"No workflows in {root / 'workflows'}"
        raise ValueError(message)
    results: dict[str, WorkflowResult] = {}
    for name in facts:
        seen: set[str] = set()
        agents: set[str] = set()
        unknown: set[str] = set()
        pending: list[str] = [name]
        while pending:
            child: str = pending.pop()
            if child in seen:
                continue
            seen.add(child)
            if child not in facts:
                unknown.add(f"workflow unavailable: {child}")
                continue
            item: WorkflowFacts = facts[child]
            agents.update(item["agents"])
            unknown.update(f"{child}: {reason}" for reason in item["unknown"])
            pending.extend(item["children"])
        fable: list[str] = sorted(PREFIX + agent for agent in agents if models[agent] == "fable")
        results[name] = {
            "fableAgentTypes": fable,
            "unknownReachability": bool(unknown),
            "uncertaintyReasons": sorted(unknown),
            "sessionModel": "opus" if fable or unknown else "sonnet",
            "children": sorted(facts[name]["children"]),
        }
    return {
        "schemaVersion": 1,
        "fableAgentTypes": sorted(PREFIX + name for name, model in models.items() if model == "fable"),
        "workflows": results,
    }


def main() -> None:
    """Print the inventory of the plugin root as sorted JSON.

    Raises:
        TypeError: ``--plugin-root`` did not parse to a path.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=Path(__file__).resolve().parent.parent)
    options: argparse.Namespace = parser.parse_args()
    plugin_root: object = options.plugin_root
    if not isinstance(plugin_root, Path):
        message: str = f"--plugin-root must be a path, got {type(plugin_root).__name__}"
        raise TypeError(message)
    sys.stdout.write(json.dumps(inventory(plugin_root), sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
