"""The prerequisite closure of an architecture delta: what the delta's work rests on.

A delta lists the elements a PRD's target changes (and the implementation gaps the baseline
assessment found). The work on those elements rests on other elements the effective
architecture shows: a table rests on its database cluster, the cluster on its network, a
handler on its event bus. The architecture step's Closure phase walks those relationships
from every delta item and records, in `closure.json`, each element the walk reaches that is
not built and current on `main`: absent, stale, or planned by an open bead.

`closure_facts` checks a closure against the delta's root items. `depscore.py arch-closure`
runs `write_closure`, which also confirms every planning bead is open and writes the checked
closure to `target/<subject>/closure.json`; `depscore.py arch-delta` then lists one
`prerequisite` item per closure entry and gives every item its `requires`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

CLOSURE_FILE = "closure.json"
CLOSURE_VERSION = 1
STATES = ("absent", "stale", "planned")
CLOSED_STATUSES = ("closed", "tombstone")


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


def closure_facts(closure: object, roots: list[dict]) -> dict:  # noqa: C901, PLR0912, PLR0915 - one validator, read top to bottom
    """Check a prerequisite closure against the delta's root items.

    Every prerequisite names an element no root item shows, a state (`absent`, `stale` or
    `planned`), the effective views that show it, and `requiredBy`: the root items (by id or
    element) or other prerequisites (by element) that need it. `requires` names what it needs
    in turn. `absent` and `stale` cite evidence; `stale` names the repository that deploys
    it; `planned` names the bead that plans it; `absent` with no deploying repository names
    the repository to create. `rootEdges` record that one root item needs another. The graph
    of `requires` must be acyclic.

    Args:
        closure: The parsed closure.
        roots: The delta's root items, each with `id` and `element`.

    Returns:
        `valid`, the refusals, the prerequisites with `requiredBy` and `requires` resolved to
        node names (a root's id, or a prerequisite's element), and each root's requirements.
    """
    refusals: list[str] = []
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
            refusals.append(f"prerequisite {n} names no element")
            continue
        element = _text(raw["element"])
        key = element.casefold()
        if key in root_of:
            refusals.append(f"{element} is already delta item {root_of[key]}")
            continue
        if key in prereqs:
            refusals.append(f"{element} is listed twice")
            continue
        prereqs[key] = {"element": element, **raw}
    name_of = {k: p["element"] for k, p in prereqs.items()}

    def resolve(ref: str, owner: str, field: str) -> str | None:
        key = ref.casefold()
        if key in root_of:
            return root_of[key]
        if key in name_of:
            return name_of[key]
        refusals.append(
            f"{owner}: `{field}` names {ref}, which is no delta item or prerequisite"
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
        deployed_by = _text(p.get("deployedBy")) or None
        planned_by = _text(p.get("plannedBy")) or None
        repository = (
            p.get("repository") if isinstance(p.get("repository"), dict) else None
        )
        if state not in STATES:
            refusals.append(
                f"{element}: state {state or 'none'} is not one of {', '.join(STATES)}"
            )
        if not views:
            refusals.append(f"{element} names no effective view that shows it")
        refusals.extend(
            f"{element}: view {v} does not exist"
            for v in views
            if not Path(v).is_file()
        )
        if state in ("absent", "stale") and not evidence:
            refusals.append(f"{element} is {state} and cites no evidence")
        if state == "stale" and not deployed_by:
            refusals.append(
                f"{element} is stale and names no repository that deploys it"
            )
        if state == "planned" and not planned_by:
            refusals.append(f"{element} is planned and names no bead that plans it")
        if (
            state == "absent"
            and not deployed_by
            and not (repository and _text(repository.get("name")))
        ):
            refusals.append(
                f"{element} is absent, no repository deploys it, and it names no repository to create"
            )
        required_by = [
            r
            for r in (
                resolve(x, element, "requiredBy") for x in _texts(p.get("requiredBy"))
            )
            if r
        ]
        if not _texts(p.get("requiredBy")):
            refusals.append(f"{element} names nothing in `requiredBy`")
        needs = [
            r
            for r in (
                resolve(x, element, "requires") for x in _texts(p.get("requires"))
            )
            if r
        ]
        if element in required_by or element in needs:
            refusals.append(f"{element} names itself")
        for r in required_by:
            if r != element:
                requires.setdefault(r, []).append(element)
        requires[element].extend(n for n in needs if n != element)
        out.append(
            {
                "element": element,
                "state": state,
                "views": views,
                "evidence": evidence,
                "deployedBy": deployed_by,
                "plannedBy": planned_by,
                "repository": {
                    "name": _text(repository.get("name")),
                    "template": _text(repository.get("template")),
                    "reason": _text(repository.get("reason")),
                }
                if repository and _text(repository.get("name"))
                else None,
                "requiredBy": sorted(set(required_by)),
                "reason": _text(p.get("reason")),
            }
        )
    edges = closure.get("rootEdges", [])
    if not isinstance(edges, list):
        refusals.append("`rootEdges` is not a list")
        edges = []
    for n, edge in enumerate(edges, start=1):
        item = (
            root_of.get(_text(edge.get("item")).casefold())
            if isinstance(edge, dict)
            else None
        )
        if item is None:
            refusals.append(f"root edge {n} names no delta item in `item`")
            continue
        for ref in _texts(edge.get("requires")):
            target = resolve(ref, item, "rootEdges.requires")
            if target and target != item:
                requires[item].append(target)
    satisfied = closure.get("satisfied", [])
    if not isinstance(satisfied, list):
        refusals.append("`satisfied` is not a list")
        satisfied = []
    for n, s in enumerate(satisfied, start=1):
        if (
            not isinstance(s, dict)
            or not _text(s.get("element"))
            or not _texts(s.get("evidence"))
        ):
            refusals.append(
                f"satisfied element {n} names no element or cites no evidence"
            )
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
        "prerequisites": sorted(out, key=lambda p: p["element"].casefold()),
        "rootRequires": {item["id"]: requires[item["id"]] for item in roots},
        "satisfied": len(satisfied),
    }


def bead_open(status_of: Callable[[str], str | None], bead_id: str) -> bool:
    """Whether a bead exists and is not closed.

    Args:
        status_of: Returns a bead's status, or None when it cannot be read.
        bead_id: The bead.

    Returns:
        True when it is open.
    """
    status = status_of(bead_id)
    return status is not None and status not in CLOSED_STATUSES


def write_closure(
    closure_path: str,
    delta_dir: str,
    *,
    status_of: Callable[[str], str | None],
    dry_run: bool = False,
) -> dict:
    """Check a prerequisite closure and write it beside the target's baseline as `closure.json`.

    The closure is checked against the delta's root items (`delta_items` without a closure),
    and every bead a `planned` prerequisite names must be open. The written file carries the
    closure as saved plus the root items it was computed for, so a later change to the delta
    invalidates it.

    Args:
        closure_path: The closure the Closure phase saved.
        delta_dir: The `target/<subject>/delta/` directory.
        status_of: Returns a bead's status, or None when it cannot be read.
        dry_run: Check only; write nothing.

    Returns:
        `ok`, the refusals, the written path, and the prerequisites by element and state.
    """
    from archstate import delta_items  # noqa: PLC0415 - archstate imports this module

    listed = delta_items(delta_dir, with_closure=False)
    refusals = list(listed["refusals"])
    try:
        closure = json.loads(Path(closure_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        closure = None
        refusals.append(f"{closure_path} could not be read: {exc}")
    roots = [{"id": i["id"], "element": i["element"]} for i in listed.get("items", [])]
    facts = closure_facts(closure, roots) if closure is not None else {"refusals": []}
    refusals += facts["refusals"]
    for p in facts.get("prerequisites", []):
        if (
            p["state"] == "planned"
            and p["plannedBy"]
            and not bead_open(status_of, p["plannedBy"])
        ):
            refusals.append(
                f"{p['element']} is planned by {p['plannedBy']}, which is not an open bead"
            )
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
        "closurePath": str(target) if ok and not dry_run else None,
        "prerequisites": prereqs,
        "summary": {
            "ok": ok,
            "refusals": refusals,
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
        path = delta_dir / CLOSURE_FILE
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
                "deployedBy": p["deployedBy"],
                "plannedBy": p["plannedBy"],
                "repository": p["repository"],
                "evidence": p["evidence"],
                "reason": p["reason"],
                "closure": str(path),
            }
        )
    return merged, [], len(facts["prerequisites"])
