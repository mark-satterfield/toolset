"""Classified architecture prerequisites derived from the element matrix snapshot.

The flow walks effective architecture views, classifies each reached element in Python,
and supplies that result here. This module resolves item edges and writes the durable
closure; it never reads bead states or searches repository code for satisfaction.
"""

from __future__ import annotations

import json
from pathlib import Path

CLOSURE_FILE = "closure.json"
CLOSURE_VERSION = 1
STATES = ("unknown", "built", "deployed")


def _text(value: object) -> str:
    """A value as stripped text, empty when it is not a string.

    Args:
        value: The value.

    Returns:
        The text.
    """
    return value.strip() if isinstance(value, str) else ""


def _texts(value: object) -> list[str]:
    """A list of non-empty stripped strings, empty when the value is not a list.

    Args:
        value: The value.

    Returns:
        The strings.
    """
    return (
        [t for t in (_text(v) for v in value) if t] if isinstance(value, list) else []
    )


def _cyclic(requires: dict[str, list[str]]) -> list[str]:
    """Return the nodes left on a cycle of the `requires` graph, empty when it is acyclic.

    Args:
        requires: Node -> the nodes it requires.

    Returns:
        The nodes no topological order reaches.
    """
    indegree = dict.fromkeys(requires, 0)
    for needs in requires.values():
        for n in needs:
            indegree[n] = indegree.get(n, 0) + 1
    ready = [n for n, d in indegree.items() if d == 0]
    seen = 0
    while ready:
        node = ready.pop()
        seen += 1
        for n in requires.get(node, []):
            indegree[n] -= 1
            if indegree[n] == 0:
                ready.append(n)
    return (
        sorted(n for n, d in indegree.items() if d > 0) if seen < len(indegree) else []
    )


def closure_facts(
    closure: object,
    roots: list[dict],
) -> dict:
    """Resolve classified matrix prerequisites into an acyclic item dependency graph.

    Only the matrix classifier supplies states and repositories. No bead status or source
    inspection participates. Root aliases and prerequisite names resolve to stable nodes.
    """
    refusals: list[str] = []
    warnings: list[str] = []
    if not isinstance(closure, dict):
        return {"valid": False, "refusals": ["the closure is not a JSON object"]}
    root_of: dict[str, str] = {}
    for item in roots:
        root_of[str(item["id"]).casefold()] = item["id"]
        root_of[str(item["element"]).casefold()] = item["id"]
    entries = closure.get("prerequisites")
    if not isinstance(entries, list):
        return {
            "valid": False,
            "refusals": ["the closure holds no `prerequisites` list"],
        }
    prereqs: dict[str, dict] = {}
    for n, raw in enumerate(entries, start=1):
        if not isinstance(raw, dict) or not _text(raw.get("element")):
            warnings.append(f"prerequisite {n} names no element and was dropped")
            continue
        element = _text(raw["element"])
        key = element.casefold()
        if key in root_of:
            warnings.append(
                f"{element} is already delta item {root_of[key]}; its prerequisite entry was dropped"
            )
            continue
        if key in prereqs:
            warnings.append(f"{element} is listed twice; the first entry is kept")
            continue
        prereqs[key] = {"element": element, **raw}
    name_of = {k: p["element"] for k, p in prereqs.items()}

    def resolve(ref: str, owner: str, field: str) -> str | None:
        key = ref.casefold()
        if key in root_of:
            return root_of[key]
        if key in name_of:
            return name_of[key]
        warnings.append(
            f"{owner}: `{field}` names {ref}, which is no delta item or prerequisite; dropped"
        )
        return None

    requires: dict[str, list[str]] = {item["id"]: [] for item in roots}
    requires.update({p["element"]: [] for p in prereqs.values()})
    out: list[dict] = []
    for p in prereqs.values():
        element = p["element"]
        state = _text(p.get("state"))
        views = _texts(p.get("views"))
        evidence = _texts(p.get("evidence"))
        repository = _text(p.get("repository")) or None
        if state not in STATES:
            refusals.append(f"{element}: invalid matrix state {state!r}")
        if not repository:
            warnings.append(
                f"{element} has no matrix repository; repo scoping places it"
            )
        named_by = _texts(p.get("requiredBy"))
        required_by = [
            r for r in (resolve(x, element, "requiredBy") for x in named_by) if r
        ]
        if not required_by:
            if not named_by:
                warnings.append(
                    f"{element} names nothing in `requiredBy`; every root item requires it"
                )
            required_by = [item["id"] for item in roots]
        needs = [
            r
            for r in (
                resolve(x, element, "requires") for x in _texts(p.get("requires"))
            )
            if r
        ]
        if element in required_by or element in needs:
            warnings.append(f"{element} names itself; that reference was dropped")
            required_by = [r for r in required_by if r != element]
            needs = [r for r in needs if r != element]
        for r in required_by:
            requires.setdefault(r, []).append(element)
        requires[element].extend(needs)
        out.append(
            {
                "element": element,
                "state": state,
                "views": views,
                "evidence": evidence,
                "repository": repository,
                "requiredBy": sorted(set(required_by)),
                "reason": _text(p.get("reason")),
            }
        )
    edges = closure.get("rootEdges", [])
    if not isinstance(edges, list):
        warnings.append("`rootEdges` is not a list and was ignored")
        edges = []
    for n, edge in enumerate(edges, start=1):
        item = (
            root_of.get(_text(edge.get("item")).casefold())
            if isinstance(edge, dict)
            else None
        )
        if item is None:
            warnings.append(f"root edge {n} names no delta item in `item`; dropped")
            continue
        for ref in _texts(edge.get("requires")):
            target = resolve(ref, item, "rootEdges.requires")
            if target and target != item:
                requires[item].append(target)
    satisfied = closure.get("satisfied", [])
    if not isinstance(satisfied, list):
        warnings.append("`satisfied` is not a list and was ignored")
        satisfied = []
    satisfied = [
        s
        for s in satisfied
        if isinstance(s, dict)
        and _text(s.get("element"))
        and s.get("state") in {"built", "deployed"}
    ]
    requires = {k: sorted(set(v)) for k, v in requires.items()}
    cycle = _cyclic(requires)
    if cycle:
        refusals.append(
            f"the `requires` relations form a cycle through {', '.join(cycle)}"
        )
    for p in out:
        p["requires"] = requires[p["element"]]
    return {
        "valid": not refusals,
        "refusals": refusals,
        "warnings": warnings,
        "prerequisites": sorted(out, key=lambda p: p["element"].casefold()),
        "rootRequires": {item["id"]: requires[item["id"]] for item in roots},
        "satisfied": len(satisfied),
    }


def write_closure(
    closure: dict,
    delta_dir: str,
    *,
    dry_run: bool = False,
    matrix_snapshot: dict | None = None,
) -> dict:
    """Write the Python-classified closure beside the target's baseline.

    Bind its roots to the same matrix snapshot used to classify the walk. The closure is
    build work and sits in the future set even when architecture has no delta directory.
    """
    from archstate import delta_items

    listed = delta_items(delta_dir, with_closure=False, matrix_snapshot=matrix_snapshot)
    refusals = list(listed["refusals"])
    roots = [{"id": i["id"], "element": i["element"]} for i in listed.get("items", [])]
    facts = closure_facts(closure, roots)
    refusals += facts["refusals"]
    warnings = list(listed.get("warnings", [])) + list(facts.get("warnings", []))
    # The written closure carries the prerequisites as read, so a later reader sees the same
    # states and references without asking beads again.
    if facts.get("prerequisites") is not None and isinstance(closure, dict):
        closure = {
            **closure,
            "prerequisites": [
                {k: v for k, v in p.items() if k != "requires"}
                | {"requires": [r for r in p["requires"] if r != p["element"]]}
                for p in facts["prerequisites"]
            ],
        }
    # The closure is build work, not architecture change: it sits with the future set, beside
    # its baseline handoff, so a target with no delta has one too.
    target = Path(delta_dir).parent / CLOSURE_FILE
    ok = not refusals
    if ok and not dry_run:
        content = {**closure, "version": CLOSURE_VERSION, "roots": roots}
        target.write_text(
            json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    prereqs = [
        {"element": p["element"], "state": p["state"]}
        for p in facts.get("prerequisites", [])
    ]
    return {
        "ok": ok,
        "refusals": refusals,
        "warnings": warnings,
        "closurePath": str(target) if ok and not dry_run else None,
        "prerequisites": prereqs,
        "summary": {
            "ok": ok,
            "refusals": refusals,
            "warnings": len(warnings),
            "prerequisites": len(prereqs),
            "satisfied": facts.get("satisfied", 0),
            "closurePath": str(target) if ok and not dry_run else None,
        },
    }


def merge_closure(
    delta_dir: Path, items: list[dict]
) -> tuple[list[dict], list[str], int]:
    """Append one `prerequisite` item per entry of the target's `closure.json`.

    Every item, root or prerequisite, then carries `requires`: the ids of the items it needs
    built first. A delta with no `closure.json` is returned unchanged.

    Args:
        delta_dir: The `target/<subject>/delta/` directory.
        items: The root items, numbered D1 ... in order.

    Returns:
        The items, the refusals, and the number of prerequisite items.
    """
    path = delta_dir.parent / CLOSURE_FILE
    if not path.is_file():
        return items, [], 0
    try:
        closure = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return items, [f"invalid closure {path}: {exc}"], 0
    roots = [{"id": i["id"], "element": i["element"]} for i in items]
    if not isinstance(closure, dict) or closure.get("roots") != roots:
        return (
            items,
            [f"{path} was computed for another delta; run the architecture step again"],
            0,
        )
    facts = closure_facts(closure, roots)
    if not facts["valid"]:
        return items, [f"invalid closure {path}: {r}" for r in facts["refusals"]], 0
    id_of = {i["id"]: i["id"] for i in items}
    for n, p in enumerate(facts["prerequisites"], start=len(items) + 1):
        id_of[p["element"]] = f"D{n}"
    merged = [
        {**i, "requires": [id_of[r] for r in facts["rootRequires"][i["id"]]]}
        for i in items
    ]
    for p in facts["prerequisites"]:
        merged.append(
            {
                "id": id_of[p["element"]],
                "element": p["element"],
                "kind": "prerequisite",
                "views": p["views"],
                "state": p["state"],
                "requiredBy": [id_of[r] for r in p["requiredBy"]],
                "requires": [id_of[r] for r in p["requires"]],
                "repository": p["repository"],
                "evidence": p["evidence"],
                "reason": p["reason"],
                "closure": str(path),
            }
        )
    return merged, [], len(facts["prerequisites"])
