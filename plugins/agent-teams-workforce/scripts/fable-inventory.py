#!/usr/bin/env python3
"""Read model declarations and conservatively classify workflow reachability.

No workflow is evaluated. Literal agent names include the existing dynamic-selection
rosters; computed dispatches remain uncertain and therefore select an Opus session.
"""

import argparse
import json
import re
from pathlib import Path

PREFIX = "agent-teams-workforce:"
QUOTED = re.compile(r"(['\"])([a-z][a-z0-9:-]*)\1")
AGENT_VALUE = re.compile(r"\bagentType\s*:\s*([^\n]+)")
CHILD_CALL = re.compile(
    r"(?<!function )\b(?:settleWorkflow|workflow|fableWorkflow)\s*\(\s*([^\n]+)"
)


def agent_models(root: Path) -> dict[str, str]:
    """Read scalar model fields only inside each agent's YAML frontmatter."""
    models = {}
    for path in sorted((root / "agents").glob("*.md")):
        text = path.read_text()
        front = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.DOTALL)
        if not front:
            raise ValueError(f"Missing frontmatter: {path}")
        model = re.search(
            r"^model:\s*['\"]?([\w.-]+)['\"]?\s*(?:#.*)?$", front[1], re.MULTILINE
        )
        if not model:
            raise ValueError(f"Missing scalar model declaration: {path}")
        models[path.stem] = model[1]
    if not models:
        raise ValueError(f"No agent definitions in {root / 'agents'}")
    return models


def workflow_facts(path: Path, models: dict[str, str]) -> dict:
    """Overapproximate literal domains, retaining uncertainty for computed calls."""
    source = re.sub(
        r"// ===== SHARED BLOCK fable .*?// ===== SHARED BLOCK fable — END =====",
        "",
        path.read_text(),
        flags=re.DOTALL,
    )
    literals = {match[2].removeprefix(PREFIX) for match in QUOTED.finditer(source)}
    agents = literals & models.keys()
    unknown = set()
    children = set()
    for match in AGENT_VALUE.finditer(source):
        value = match[1].strip()
        literal = QUOTED.match(value)
        if literal:
            name = literal[2].removeprefix(PREFIX)
            if name not in models:
                unknown.add(f"agent model unavailable: {literal[2]}")
        elif not value.startswith(
            ("o.agentType || null", "opts.agentType || null", "{ type:")
        ):
            unknown.add("computed agent dispatch")
    for match in CHILD_CALL.finditer(source):
        value = match[1].strip()
        literal = QUOTED.match(value)
        if literal:
            children.add(literal[2].removeprefix(PREFIX))
        elif value.startswith("name, "):
            # The standard forwarding wrapper delegates its named caller's input.
            continue
        elif not value.startswith(")"):
            unknown.add("computed child workflow")
    return {"agents": agents, "children": children, "unknown": unknown}


def inventory(root: Path) -> dict:
    models = agent_models(root)
    facts = {
        path.stem: workflow_facts(path, models)
        for path in sorted((root / "workflows").glob("*.js"))
    }
    if not facts:
        raise ValueError(f"No workflows in {root / 'workflows'}")
    results = {}
    for name in facts:
        seen, agents, unknown = set(), set(), set()
        pending = [name]
        while pending:
            child = pending.pop()
            if child in seen:
                continue
            seen.add(child)
            if child not in facts:
                unknown.add(f"workflow unavailable: {child}")
                continue
            item = facts[child]
            agents.update(item["agents"])
            unknown.update(f"{child}: {reason}" for reason in item["unknown"])
            pending.extend(item["children"])
        fable = sorted(PREFIX + agent for agent in agents if models[agent] == "fable")
        results[name] = {
            "fableAgentTypes": fable,
            "unknownReachability": bool(unknown),
            "uncertaintyReasons": sorted(unknown),
            "sessionModel": "opus" if fable or unknown else "sonnet",
            "children": sorted(facts[name]["children"]),
        }
    return {
        "schemaVersion": 1,
        "fableAgentTypes": sorted(
            PREFIX + name for name, model in models.items() if model == "fable"
        ),
        "workflows": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin-root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    options = parser.parse_args()
    print(json.dumps(inventory(options.plugin_root), sort_keys=True))


if __name__ == "__main__":
    main()
