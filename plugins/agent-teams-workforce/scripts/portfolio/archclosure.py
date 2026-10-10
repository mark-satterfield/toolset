"""Classified architecture prerequisites derived from the element matrix snapshot.

The flow walks effective architecture views, classifies each reached element in Python,
and supplies that result here. This module resolves item edges and writes the durable
closure; it never reads bead states or searches repository code for satisfaction.
"""

from __future__ import annotations

import json
from pathlib import Path

import archstate
import contracts
from contracts import (
    ClosureFacts,
    ClosureResult,
    DeltaItem,
    JsonObject,
    JsonValue,
    Prerequisite,
    PrerequisiteState,
    RootItem,
    json_object,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

CLOSURE_FILE = "closure.json"
CLOSURE_VERSION = 1
STATES = ("unknown", "built", "deployed")


def _text(value: JsonValue) -> str:
    """Return stripped text, empty when the value is not a string.

    Args:
        value: The value.

    Returns:
        The text.

    """
    return value.strip() if isinstance(value, str) else ""


def _texts(value: JsonValue) -> list[str]:
    """Return non-empty stripped strings, empty when the value is not a list.

    Args:
        value: The value.

    Returns:
        The strings.

    """
    return [t for t in (_text(v) for v in value) if t] if isinstance(value, list) else []


def _cyclic(requires: dict[str, list[str]]) -> list[str]:
    """Return the nodes left on a cycle of the `requires` graph, empty when it is acyclic.

    Args:
        requires: Node -> the nodes it requires.

    Returns:
        The nodes no topological order reaches.

    """
    needs: list[str]
    n: str
    indegree: dict[str, int] = dict.fromkeys(requires, 0)
    for needs in requires.values():
        for n in needs:
            indegree[n] = indegree.get(n, 0) + 1
    ready: list[str] = [n for n, d in indegree.items() if d == 0]
    seen: int = 0
    while ready:
        node: str = ready.pop()
        seen += 1
        for n in requires.get(node, []):
            indegree[n] -= 1
            if indegree[n] == 0:
                ready.append(n)
    return sorted(n for n, d in indegree.items() if d > 0) if seen < len(indegree) else []


def _prerequisite_sort_key(row: Prerequisite) -> str:
    """Order prerequisite records by normalized element name.

    Returns:
        The case-folded element name.

    """
    return row["element"].casefold()


class _ClosureNodes:
    def __init__(self, roots: list[RootItem], entries: list[JsonValue], warnings: list[str]) -> None:
        number: int
        raw: int | float | str | list[JsonValue] | dict[str, JsonValue] | None
        self.warnings: list[str] = warnings
        self.roots: list[RootItem] = roots
        self.root_of: dict[str, str] = {
            alias.casefold(): item["id"] for item in roots for alias in (item["id"], item["element"])
        }
        self.prereqs: dict[str, JsonObject] = {}
        for number, raw in enumerate(entries, start=1):
            if not isinstance(raw, dict) or not _text(raw.get("element")):
                warnings.append(f"prerequisite {number} names no element and was dropped")
                continue
            element: str = _text(raw["element"])
            key: str = element.casefold()
            if key in self.root_of:
                warnings.append(
                    f"{element} is already delta item {self.root_of[key]}; its prerequisite entry was dropped",
                )
            elif key in self.prereqs:
                warnings.append(f"{element} is listed twice; the first entry is kept")
            else:
                self.prereqs[key] = {**raw, "element": element}
        self.name_of: dict[str, str] = {key: check_type(row["element"], str) for key, row in self.prereqs.items()}
        self.requires: dict[str, list[str]] = {item["id"]: [] for item in roots}
        self.requires.update({name: [] for name in self.name_of.values()})

    def _resolve(self, ref: str, owner: str, field: str) -> str | None:
        key: str = ref.casefold()
        if key in self.root_of:
            return self.root_of[key]
        if key in self.name_of:
            return self.name_of[key]
        self.warnings.append(f"{owner}: `{field}` names {ref}, which is no delta item or prerequisite; dropped")
        return None

    def _prerequisite(self, row: JsonObject, refusals: list[str]) -> Prerequisite:
        name: str
        element: str = check_type(row["element"], str)
        state: str = _text(row.get("state"))
        repository: str | None = _text(row.get("repository")) or None
        if state not in STATES:
            refusals.append(f"{element}: invalid matrix state {state!r}")
        if not repository:
            self.warnings.append(f"{element} has no matrix repository; repo scoping places it")
        named_by: list[str] = _texts(row.get("requiredBy"))
        required_by: list[str] = [
            resolved for name in named_by if (resolved := self._resolve(name, element, "requiredBy"))
        ]
        if not required_by:
            if not named_by:
                self.warnings.append(f"{element} names nothing in `requiredBy`; every root item requires it")
            required_by = [item["id"] for item in self.roots]
        needs: list[str] = [
            resolved for name in _texts(row.get("requires")) if (resolved := self._resolve(name, element, "requires"))
        ]
        if element in required_by or element in needs:
            self.warnings.append(f"{element} names itself; that reference was dropped")
            required_by = [name for name in required_by if name != element]
            needs = [name for name in needs if name != element]
        for name in required_by:
            self.requires.setdefault(name, []).append(element)
        self.requires[element].extend(needs)
        return {
            "element": element,
            "state": state,
            "views": _texts(row.get("views")),
            "evidence": _texts(row.get("evidence")),
            "repository": repository,
            "requiredBy": sorted(set(required_by)),
            "reason": _text(row.get("reason")),
            "requires": [],
        }

    def _edges(self, value: JsonValue) -> None:
        number: int
        edge: int | float | str | list[JsonValue] | dict[str, JsonValue] | None
        ref: str
        if not isinstance(value, list):
            self.warnings.append("`rootEdges` is not a list and was ignored")
            return
        for number, edge in enumerate(value, start=1):
            root_id: str | None = (
                self.root_of.get(_text(edge.get("item")).casefold()) if isinstance(edge, dict) else None
            )
            if root_id is None or not isinstance(edge, dict):
                self.warnings.append(f"root edge {number} names no delta item in `item`; dropped")
                continue
            for ref in _texts(edge.get("requires")):
                target: str | None = self._resolve(ref, root_id, "rootEdges.requires")
                if target and target != root_id:
                    self.requires[root_id].append(target)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def facts(self, closure: JsonObject, refusals: list[str]) -> ClosureFacts:
        """Resolve prerequisites and return their validated graph.

        Returns:
            The graph with resolution diagnostics.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        row: Prerequisite
        if not (isinstance(closure, dict)) or not (isinstance(refusals, list)):
            argument_error: str = "facts: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        out: list[contracts.Prerequisite] = [self._prerequisite(row, refusals) for row in self.prereqs.values()]
        self._edges(closure.get("rootEdges", []))
        satisfied: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = closure.get(
            "satisfied",
            [],
        )
        if not isinstance(satisfied, list):
            self.warnings.append("`satisfied` is not a list and was ignored")
            satisfied = []
        satisfied_rows: list[
            dict[str, bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None]
        ] = [
            row
            for row in satisfied
            if isinstance(row, dict) and _text(row.get("element")) and row.get("state") in {"built", "deployed"}
        ]
        self.requires = {key: sorted(set(value)) for key, value in self.requires.items()}
        cycle: list[str] = _cyclic(self.requires)
        if cycle:
            refusals.append(f"the `requires` relations form a cycle through {', '.join(cycle)}")
        for row in out:
            row["requires"] = self.requires[row["element"]]
        return {
            "valid": not refusals,
            "refusals": refusals,
            "warnings": self.warnings,
            "prerequisites": sorted(out, key=_prerequisite_sort_key),
            "rootRequires": {item["id"]: self.requires[item["id"]] for item in self.roots},
            "satisfied": len(satisfied_rows),
        }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def closure_facts(closure: JsonValue, roots: list[RootItem]) -> ClosureFacts:
    """Resolve classified matrix prerequisites into an acyclic item dependency graph.

    Returns:
        The resolved graph and diagnostics.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(roots, list)):
        argument_error: str = "closure_facts: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    if not isinstance(closure, dict):
        return {"valid": False, "refusals": ["the closure is not a JSON object"]}
    value: dict[str, contracts.JsonValue] = json_object(closure)
    entries: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = value.get(
        "prerequisites",
    )
    if not isinstance(entries, list):
        return {"valid": False, "refusals": ["the closure holds no `prerequisites` list"]}
    nodes: _ClosureNodes = _ClosureNodes(roots, entries, [])
    return nodes.facts(value, [])


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_closure(
    closure: JsonObject,
    delta_dir: str,
    *,
    dry_run: bool = False,
    matrix_snapshot: JsonObject | None = None,
) -> ClosureResult:
    """Write the Python-classified closure beside the target's baseline.

    Bind its roots to the same matrix snapshot used to classify the walk. The closure is
    build work and sits in the future set even when architecture has no delta directory.

    Returns:
        The saved closure path, prerequisite states and diagnostics.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(closure, dict))
        or not (isinstance(delta_dir, str))
        or not (isinstance(dry_run, bool))
        or not (isinstance(matrix_snapshot, dict) or matrix_snapshot is None)
    ):
        argument_error: str = "write_closure: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    listed: contracts.DeltaResult = archstate.delta_items(
        delta_dir,
        with_closure=False,
        matrix_snapshot=matrix_snapshot,
    )
    refusals: list[str] = list(listed["refusals"])
    roots: list[RootItem] = [{"id": i["id"], "element": i["element"]} for i in listed.get("items", [])]
    facts: contracts.ClosureFacts = closure_facts(closure, roots)
    refusals += facts["refusals"]
    warnings: list[str] = list(listed.get("warnings", [])) + list(facts.get("warnings", []))
    # The written closure carries the prerequisites as read, so a later reader sees the same
    # states and references without asking beads again.
    if facts.get("prerequisites") is not None and isinstance(closure, dict):
        closure = json_object({
            **closure,
            "prerequisites": [
                {k: v for k, v in p.items() if k != "requires"}
                | {"requires": [r for r in p["requires"] if r != p["element"]]}
                for p in facts["prerequisites"]
            ],
        })
    # The closure is build work, not architecture change: it sits with the future set, beside
    # its baseline handoff, so a target with no delta has one too.
    target: Path = Path(delta_dir).parent / CLOSURE_FILE
    ok: bool = not refusals
    if ok and not dry_run:
        content: dict[
            str,
            list[contracts.RootItem]
            | int
            | float
            | str
            | list[contracts.JsonValue]
            | dict[str, contracts.JsonValue]
            | None,
        ] = {**closure, "version": CLOSURE_VERSION, "roots": roots}
        target.write_text(
            json.dumps(content, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    prereqs: list[PrerequisiteState] = [
        {"element": p["element"], "state": p["state"]} for p in facts.get("prerequisites", [])
    ]
    return {
        "ok": ok,
        "refusals": refusals,
        "warnings": warnings,
        "closurePath": str(target) if ok and not dry_run else None,
        "prerequisites": prereqs,
        "summary": {
            "ok": ok,
            "refusals": list(refusals),
            "warnings": len(warnings),
            "prerequisites": len(prereqs),
            "satisfied": facts.get("satisfied", 0),
            "closurePath": str(target) if ok and not dry_run else None,
        },
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def merge_closure(
    delta_dir: Path,
    items: list[DeltaItem],
) -> tuple[list[DeltaItem], list[str], int]:
    """Append one `prerequisite` item per entry of the target's `closure.json`.

    Every item, root or prerequisite, then carries `requires`: the ids of the items it needs
    built first. A delta with no `closure.json` is returned unchanged.

    Args:
        delta_dir: The `target/<subject>/delta/` directory.
        items: The root items, numbered D1 ... in order.

    Returns:
        The items, the refusals, and the number of prerequisite items.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    n: int
    p: Prerequisite
    if not (isinstance(delta_dir, Path)) or not (isinstance(items, list)):
        argument_error: str = "merge_closure: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    path: Path = delta_dir.parent / CLOSURE_FILE
    if not path.is_file():
        return items, [], 0
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return items, [f"invalid closure {path}: {exc}"], 0
    roots: list[RootItem] = [{"id": i["id"], "element": i["element"]} for i in items]
    closure: JsonObject = json_object(raw) if isinstance(raw, dict) else {}
    if closure.get("roots") != roots:
        return (
            items,
            [f"{path} was computed for another delta; run the architecture step again"],
            0,
        )
    facts: contracts.ClosureFacts = closure_facts(closure, roots)
    if not facts["valid"]:
        return items, [f"invalid closure {path}: {r}" for r in facts["refusals"]], 0
    id_of: dict[str, str] = {i["id"]: i["id"] for i in items}
    for n, p in enumerate(facts["prerequisites"], start=len(items) + 1):
        id_of[p["element"]] = f"D{n}"
    merged: list[DeltaItem] = [{**i, "requires": [id_of[r] for r in facts["rootRequires"][i["id"]]]} for i in items]
    merged.extend(
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
        for p in facts["prerequisites"]
    )
    return merged, [], len(facts["prerequisites"])
