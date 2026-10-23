#!/usr/bin/env python3
"""Compute the order in which Epics are architected and approved, from the matrix and beads alone.

No model is called and no ordering is assumed: neither WSJF nor any rank enters the edges. An
edge says that one Epic uses an architecture entry another Epic's own requirements define, so the
user is elaborated after the definer (the driver). Units are as fine as the matrix allows:

1. A feature. Its drivers are the Epics with a ``drives`` relationship to it, or to a document
   heading (or whole document) that ``describedBy`` names for it. With no such Epic, it has a
   driver only when it serves the requirements of exactly one Epic (``hasRequirement`` then
   ``servedBy``) and that Epic does not only rest on it; a feature serving several Epics with no
   ``drives`` has no driver and makes no edge. Its users are the other Epics it serves and the Epics with ``restsOn``
   to it.
2. A document heading, a whole document or any other entry an Epic ``drives``. Its drivers are
   those Epics; its users are the Epics whose requirements that exact heading ``covers``, and the
   Epics with ``restsOn`` to it or to an entry it describes.

Every driver of a unit gets an edge to every user of it. Users of one unit get no edge between
them, and co-drivers of one unit none either. An entry no Epic drives (a VPC, the chassis library,
a Cognito pool) makes no edge: the first Epic elaborated reviews and approves it. A unit whose
matrix ``approved`` flag is set makes no edge. Cycles are reported, never broken: their members
share a level. The rest is transitively reduced over the cycles taken as single nodes.

Two scenarios are computed: as the matrix stands (A), and as if every entry of a ``shared-*``
stack were approved (B). ``--report`` writes the Markdown report (``epicorderreport.py``), with
``--expect <waiter>:<driver>`` spot-checks; stdout carries one JSON summary. ``--apply`` writes
the chosen scenario's edges as the owned beads ``tracks`` edges through ``edgeset.apply_edges``
(the ``apply-edges`` path, every owned Epic edge at once); hand-made edges stay.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import portfolio_path  # ruff: ignore[unused-import] - puts the beads-contract and artifact-handoff scripts on sys.path.

# isort: split
import beadgraph
import edgeset
from contracts import json_object
from matrix_contract import (
    AUTHORITY_SIDE,
    KIND_FEATURE,
    KIND_STACK,
    REL_COVERS,
    REL_DESCRIBED_BY,
    REL_DRIVES,
    REL_HAS_REQUIREMENT,
    REL_REALIZED_BY,
    REL_RESTS_ON,
    REL_SERVED_BY,
    EntryId,
)
from matrixstore import Matrix, matrix_path, read_matrix
from matrixtraverse import Heading, epic_id, heading_index, stacks_of

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from contracts import JsonObject, JsonValue
    from matrixstore import Relationship

type Unit = str
"""A feature or other entry id, or ``<document id>#<heading>`` for one heading of a document."""
type Pair = tuple[str, str]
"""An edge: the driver, elaborated first, then the Epic that waits for it."""

SHARED_PREFIX: Final = "shared-"
HEADING_MARK: Final = "#"
EPIC_PREFIX: Final = "epic:"
RULE_DRIVES: Final = "drives"
RULE_DRIVES_HEADING: Final = "drives a heading describing it"
RULE_SERVED: Final = "servedBy"
SCENARIO_AS_IS: Final = "as-is"
SCENARIO_SHARED: Final = "shared-approved"


@dataclass(frozen=True, slots=True)
class Epic:
    """One open Epic."""

    id: str
    title: str


@dataclass(frozen=True, slots=True)
class Decision:
    """One unit, the Epics that define it, the evidence that made them its drivers, and its users."""

    unit: Unit
    label: str
    drivers: tuple[str, ...]
    rule: str
    users: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Cycle:
    """One strongly connected set of Epics and the edges inside it, each with the units that make it."""

    members: tuple[str, ...]
    edges: Mapping[Pair, tuple[Unit, ...]]


@dataclass(frozen=True, slots=True)
class Order:
    """One scenario's result: its edges before and after reduction, its cycles and its levels."""

    name: str
    excluded: int
    raw: Mapping[Pair, tuple[Unit, ...]]
    cycles: tuple[Cycle, ...]
    edges: Mapping[Pair, tuple[Unit, ...]]
    levels: Mapping[str, int]
    unlocks: Mapping[str, int]
    chain: tuple[tuple[str, ...], ...]
    """The longest chain, each step one Epic or the members of one cycle."""


@dataclass(frozen=True, slots=True)
class Check:
    """One spot-check: whether ``waiter`` waits for ``driver``, and through which Epics."""

    waiter: str
    driver: str
    path: tuple[str, ...]
    direct: tuple[Unit, ...]


@dataclass(frozen=True, slots=True)
class Analysis:
    """Everything the report shows."""

    epics: Mapping[str, Epic]
    decisions: Mapping[Unit, Decision]
    orders: tuple[Order, ...]
    current: Mapping[Pair, bool]
    """Each standing ``tracks`` edge between two open Epics, with whether this system owns it."""
    missing: tuple[str, ...]
    """Open Epics the matrix does not hold."""
    validation: Mapping[str, tuple[str, ...]]
    """Each scenario's name with the cycle ``apply-edges`` would refuse its edges for (empty: accepted)."""
    checks: Mapping[str, tuple[Check, ...]]
    """Each scenario's name with its spot-checks."""


def heading_unit(document: EntryId, heading: str) -> Unit:
    """Name one heading of a document, or the whole document when the heading is empty.

    Returns:
        The unit.

    """
    return f"{document}{HEADING_MARK}{heading}" if heading else document


def unit_entry(unit: Unit) -> EntryId:
    """Name the matrix entry a unit belongs to.

    Returns:
        The entry id (the document, for a heading).

    """
    return EntryId(unit.partition(HEADING_MARK)[0])


def _heading_of(rel: Relationship) -> str:
    value: object = rel.attributes.get("heading")
    return value if isinstance(value, str) else ""


def _target(rel: Relationship) -> Unit:
    return heading_unit(rel.end, _heading_of(rel))


@dataclass(slots=True)
class _Links:
    """The matrix relationships the rule reads, restricted to the open Epics the matrix holds."""

    drives: dict[Unit, set[str]]
    rests: dict[Unit, set[str]]
    served: dict[EntryId, set[str]]
    covered: dict[Unit, set[str]]
    describers: dict[EntryId, set[Unit]]


def _epics_of(matrix: Matrix, requirement: EntryId, epics: Collection[str]) -> set[str]:
    return {
        bead
        for rel in matrix.incoming(requirement, (REL_HAS_REQUIREMENT,))
        if (bead := rel.start.removeprefix(EPIC_PREFIX)) in epics
    }


def links(matrix: Matrix, epics: Collection[str]) -> _Links:
    """Read the ``drives``, ``restsOn``, ``servedBy``, ``covers`` and feature ``describedBy`` relationships.

    Returns:
        Each relationship family indexed by the unit it names.

    """
    found = _Links({}, {}, {}, {}, {})
    for rel in matrix.relationships((REL_DRIVES, REL_RESTS_ON)):
        bead: str = rel.start.removeprefix(EPIC_PREFIX)
        if rel.side == AUTHORITY_SIDE and bead in epics:
            family: dict[Unit, set[str]] = found.drives if rel.kind == REL_DRIVES else found.rests
            family.setdefault(_target(rel), set()).add(bead)
    for rel in matrix.relationships((REL_SERVED_BY,)):
        if rel.side == AUTHORITY_SIDE and (owners := _epics_of(matrix, rel.start, epics)):
            found.served.setdefault(rel.end, set()).update(owners)
    for rel in matrix.relationships((REL_COVERS,)):
        if rel.side == AUTHORITY_SIDE and (owners := _epics_of(matrix, rel.end, epics)):
            found.covered.setdefault(_target(rel), set()).update(owners)
    for rel in matrix.relationships((REL_DESCRIBED_BY,)):
        start = matrix.find(rel.start)
        if rel.side == AUTHORITY_SIDE and start is not None and start.kind == KIND_FEATURE:
            found.describers.setdefault(start.id, set()).add(_target(rel))
    return found


def _label(matrix: Matrix, unit: Unit) -> str:
    document, _, heading = unit.partition(HEADING_MARK)
    entry = matrix.find(EntryId(document))
    if heading:
        return f"{document.removeprefix('document:')} § {heading}"
    return entry.name if entry is not None and entry.kind == KIND_FEATURE else unit


def _feature(matrix: Matrix, feature: EntryId, found: _Links) -> Decision | None:
    served: set[str] = found.served.get(feature, set())
    rests: set[str] = found.rests.get(feature, set())
    headings: set[Unit] = found.describers.get(feature, set())
    by_heading: set[str] = set().union(
        *(found.drives.get(h, set()) | found.drives.get(unit_entry(h), set()) for h in headings),
    )
    explicit: set[str] = found.drives.get(feature, set())
    rule: str = RULE_DRIVES if explicit else RULE_DRIVES_HEADING
    drivers: set[str] = explicit | by_heading
    if not drivers and len(served) == 1:
        rule, drivers = RULE_SERVED, served - rests
    users: set[str] = (served | rests) - drivers
    if not drivers or not users:
        return None
    return Decision(feature, _label(matrix, feature), tuple(sorted(drivers)), rule, tuple(sorted(users)))


def _driven(matrix: Matrix, unit: Unit, found: _Links, index: Mapping[Heading, list[EntryId]]) -> Decision | None:
    drivers: set[str] = found.drives[unit]
    document, _, heading = unit.partition(HEADING_MARK)
    described: list[EntryId] = index.get((EntryId(document), heading), []) if HEADING_MARK in unit else []
    users: set[str] = found.covered.get(unit, set()) | found.rests.get(unit, set())
    users.update(*(found.rests.get(entry, set()) for entry in described))
    users -= drivers
    if not users:
        return None
    return Decision(unit, _label(matrix, unit), tuple(sorted(drivers)), RULE_DRIVES, tuple(sorted(users)))


def decide(matrix: Matrix, epics: Collection[str]) -> dict[Unit, Decision]:
    """Name the drivers and users of every unit that has both.

    Returns:
        Each unit's decision, in unit order.

    """
    found: _Links = links(matrix, epics)
    index: dict[Heading, list[EntryId]] = heading_index(matrix)
    decisions: list[Decision | None] = [
        _feature(matrix, feature, found)
        for feature in sorted(set(found.served) | set(found.rests))
        if (entry := matrix.find(feature)) is not None and entry.kind == KIND_FEATURE
    ]
    decisions.extend(
        _driven(matrix, unit, found, index)
        for unit in sorted(found.drives)
        if (entry := matrix.find(unit_entry(unit))) is not None and entry.kind != KIND_FEATURE
    )
    return {decision.unit: decision for decision in decisions if decision is not None}


def is_shared(matrix: Matrix, unit: Unit, index: Mapping[Heading, list[EntryId]]) -> bool:
    """Tell whether an entry belongs to a ``shared-*`` stack (the central event API and bus included).

    A stack is shared when its name or repository starts with ``shared-``; an entry when every
    stack it is or has its home in is; a heading when every entry it describes is; a feature when
    every entry realizing it is, else when every heading describing it is.

    Returns:
        True for a shared entry.

    """
    if HEADING_MARK in unit:
        document, _, heading = unit.partition(HEADING_MARK)
        described: list[EntryId] = index.get((EntryId(document), heading), [])
        return bool(described) and all(is_shared(matrix, entry, index) for entry in described)
    entry = matrix.find(EntryId(unit))
    if entry is None:
        return False
    if entry.kind == KIND_STACK:
        repository: object = entry.attributes.get("repository")
        return unit.startswith(f"{KIND_STACK}:{SHARED_PREFIX}") or (
            isinstance(repository, str) and repository.startswith(SHARED_PREFIX)
        )
    if entry.kind == KIND_FEATURE:
        realizers: list[EntryId] = [rel.end for rel in matrix.outgoing(entry.id, (REL_REALIZED_BY,))]
        if realizers:
            return all(is_shared(matrix, realizer, index) for realizer in realizers)
        headings: list[Unit] = [
            unit for rel in matrix.outgoing(entry.id, (REL_DESCRIBED_BY,)) if HEADING_MARK in (unit := _target(rel))
        ]
        return bool(headings) and all(is_shared(matrix, heading, index) for heading in headings)
    stacks: set[EntryId] = stacks_of(matrix, entry.id)
    return bool(stacks) and all(is_shared(matrix, stack, index) for stack in stacks)


def is_approved(matrix: Matrix, unit: Unit) -> bool:
    """Read the matrix ``approved`` flag of the entry a unit belongs to.

    Returns:
        True when the entry carries the flag.

    """
    entry = matrix.find(unit_entry(unit))
    return entry is not None and entry.approved is not None


def raw_edges(decisions: Iterable[Decision]) -> dict[Pair, tuple[Unit, ...]]:
    """Draw driver -> user for every driver and user of every decision, each pair with its units.

    Returns:
        Each edge with the units that make it, sorted.

    """
    found: dict[Pair, set[Unit]] = {}
    for decision in decisions:
        for driver in decision.drivers:
            for user in decision.users:
                found.setdefault((driver, user), set()).add(decision.unit)
    return {pair: tuple(sorted(units)) for pair, units in sorted(found.items())}


def _successors(edges: Iterable[Pair]) -> dict[str, list[str]]:
    successors: dict[str, list[str]] = {}
    for start, end in edges:
        successors.setdefault(start, []).append(end)
    return successors


def _descendants(successors: Mapping[str, list[str]], start: str) -> set[str]:
    seen: set[str] = set()
    todo: list[str] = list(successors.get(start, []))
    while todo:
        node: str = todo.pop()
        if node not in seen:
            seen.add(node)
            todo.extend(successors.get(node, []))
    return seen


def groups(nodes: Iterable[str], edges: Iterable[Pair]) -> dict[str, tuple[str, ...]]:
    """Put every Epic in its strongly connected set: itself alone, or the members of its cycle.

    Returns:
        Each Epic's set, sorted.

    """
    successors: dict[str, list[str]] = _successors(edges)
    reach: dict[str, set[str]] = {node: _descendants(successors, node) for node in nodes}
    return {node: tuple(sorted({node} | {o for o in beyond if node in reach[o]})) for node, beyond in reach.items()}


def _path(successors: Mapping[str, list[str]], start: str, goal: str) -> tuple[str, ...]:
    previous: dict[str, str] = {}
    todo: list[str] = [start]
    while todo:
        node: str = todo.pop(0)
        for nxt in successors.get(node, []):
            if nxt not in previous and nxt != start:
                previous[nxt] = node
                todo.append(nxt)
    if goal not in previous:
        return ()
    path: list[str] = [goal]
    while path[-1] != start:
        path.append(previous[path[-1]])
    return tuple(reversed(path))


def _redundant(between: Collection[Pair]) -> set[Pair]:
    successors: dict[str, list[str]] = _successors(between)
    redundant: set[Pair] = set()
    for start, ends in successors.items():
        beyond: set[str] = set().union(*(_descendants(successors, end) for end in ends))
        redundant.update((start, end) for end in ends if end in beyond)
    return redundant


def _depths(heads: Iterable[str], between: Collection[Pair]) -> tuple[dict[str, int], dict[str, list[str]]]:
    predecessors: dict[str, list[str]] = {}
    for start, end in between:
        predecessors.setdefault(end, []).append(start)
    depth: dict[str, int] = {}

    def level_of(head: str) -> int:
        if head not in depth:
            depth[head] = 1 + max((level_of(p) for p in predecessors.get(head, [])), default=0)
        return depth[head]

    for head in sorted(heads):
        level_of(head)
    return depth, predecessors


def _chain(group: Mapping[str, tuple[str, ...]], between: Collection[Pair]) -> tuple[tuple[str, ...], ...]:
    depth, predecessors = _depths({members[0] for members in group.values()}, between)
    head: str = min(depth, key=lambda h: (-depth[h], -len(group[h]), h))
    chain: list[tuple[str, ...]] = [group[head]]
    while predecessors.get(head):
        head = min((p for p in predecessors[head] if depth[p] == depth[head] - 1), key=lambda h: (-len(group[h]), h))
        chain.append(group[head])
    return tuple(reversed(chain))


def order(name: str, decisions: Iterable[Decision], excluded: Collection[Unit], epics: Collection[str]) -> Order:
    """Compute one scenario: its edges, its cycles, the reduction over the cycles, levels and the longest chain.

    Each cycle is taken as one node (named by its first member) for the reduction and the levels.

    Returns:
        The scenario's result.

    """
    every: list[Decision] = list(decisions)
    kept: list[Decision] = [d for d in every if d.unit not in excluded]
    raw: dict[Pair, tuple[Unit, ...]] = raw_edges(kept)
    group: dict[str, tuple[str, ...]] = groups(epics, raw)
    cycles: tuple[Cycle, ...] = tuple(
        Cycle(members, {pair: units for pair, units in raw.items() if group[pair[0]] == members == group[pair[1]]})
        for members in sorted({g for g in group.values() if len(g) > 1})
    )
    between: set[Pair] = {(group[a][0], group[b][0]) for a, b in raw if group[a] != group[b]}
    redundant: set[Pair] = _redundant(between)
    edges: dict[Pair, tuple[Unit, ...]] = {
        (a, b): units for (a, b), units in raw.items() if (group[a][0], group[b][0]) not in redundant
    }
    depth, _ = _depths({members[0] for members in group.values()}, between)
    successors: dict[str, list[str]] = _successors(between)
    unlocks: dict[str, int] = {
        bead: len(set().union(*(group[h] for h in _descendants(successors, group[bead][0])))) for bead in epics
    }
    levels: dict[str, int] = {bead: depth[group[bead][0]] for bead in epics}
    return Order(name, len(every) - len(kept), raw, cycles, edges, levels, unlocks, _chain(group, between))


def check(result: Order, waiter: str, driver: str) -> Check:
    """Tell whether ``waiter`` waits for ``driver`` in a scenario, directly or through other Epics.

    Returns:
        The spot-check, with the path of Epics (empty: it does not wait) and the direct units.

    """
    path: tuple[str, ...] = _path(_successors(result.raw), driver, waiter)
    return Check(waiter, driver, path, result.raw.get((driver, waiter), ()))


def read_epics(graph: beadgraph.Graph) -> dict[str, Epic]:
    """Read the open Epics with their titles from the tracker.

    Returns:
        Each open Epic by id.

    """
    return {
        bead.id: Epic(bead.id, bead.title.removeprefix("Feature PRD: ").strip())
        for bead in graph.of_kind("epic")
        if not bead.closed
    }


def current_edges(graph: beadgraph.Graph, epics: Collection[str]) -> dict[Pair, bool]:
    """Read the standing ``tracks`` edges between open Epics, each with whether this system owns it.

    Returns:
        Each edge (blocker, blocked) with its ownership.

    """
    return {
        (blocker, bead.id): blocker in bead.owned_blockers
        for bead in graph.of_kind("epic")
        if bead.id in epics
        for blocker in bead.tracked
        if blocker in epics
    }


def proposal(result: Order, decisions: Mapping[Unit, Decision], epics: Mapping[str, Epic]) -> list[edgeset.Edge]:
    """Turn a scenario's edges into the edge proposal ``apply-edges`` takes.

    Returns:
        One edge per pair, with its reason and the matrix check that makes it.

    """
    edges: list[edgeset.Edge] = []
    for (blocker, blocked), units in result.edges.items():
        first: Decision = decisions[units[0]]
        more: str = f" (+{len(units) - 1} more entries)" if len(units) > 1 else ""
        edges.append(
            edgeset.Edge(
                blocker=blocker,
                blocked=blocked,
                reason=(
                    f"{epics[blocked].title} uses {first.label}, which {epics[blocker].title}'s requirements "
                    f"define ({first.rule}){more}"
                ),
                confidence="medium",
                arch_check=f"{', '.join(units)}: the matrix holds no approved flag on it (epicorder.py)",
            ),
        )
    return edges


def _refusal(report: edgeset.ValidationReport) -> tuple[str, ...]:
    if report["ok"]:
        return ()
    return tuple(report["cycle"]) or ("refused: " + json.dumps({k: v for k, v in report.items() if v}),)


def analyse(matrix: Matrix, graph: beadgraph.Graph, expected: Iterable[Pair]) -> Analysis:
    """Run the whole computation over one read of the matrix and the tracker.

    Returns:
        Everything the report shows.

    """
    epics: dict[str, Epic] = read_epics(graph)
    missing: tuple[str, ...] = tuple(sorted(bead for bead in epics if matrix.find(epic_id(bead)) is None))
    held: set[str] = set(epics) - set(missing)
    decisions: dict[Unit, Decision] = decide(matrix, held)
    index: dict[Heading, list[EntryId]] = heading_index(matrix)
    approved: set[Unit] = {unit for unit in decisions if is_approved(matrix, unit)}
    shared: set[Unit] = {unit for unit in decisions if is_shared(matrix, unit, index)}
    orders: tuple[Order, ...] = (
        order("A", decisions.values(), approved, epics),
        order("B", decisions.values(), approved | shared, epics),
    )
    validation: dict[str, tuple[str, ...]] = {
        result.name: _refusal(edgeset.validate(graph, proposal(result, decisions, epics))) for result in orders
    }
    pairs: list[Pair] = list(expected)
    checks: dict[str, tuple[Check, ...]] = {
        result.name: tuple(check(result, waiter, driver) for waiter, driver in pairs) for result in orders
    }
    return Analysis(epics, decisions, orders, current_edges(graph, epics), missing, validation, checks)


def summary(analysis: Analysis) -> JsonObject:
    """Summarise each scenario for stdout.

    Returns:
        The summary.

    """
    scenarios: list[JsonValue] = []
    for result in analysis.orders:
        sizes: list[int] = [list(result.levels.values()).count(n) for n in range(1, max(result.levels.values()) + 1)]
        scenarios.append({
            "scenario": result.name,
            "edges": len(result.edges),
            "startNow": sizes[0],
            "levels": len(sizes),
            "maxConcurrency": max(sizes),
            "longestChain": sum(len(step) for step in result.chain),
            "cycles": [list(cycle.members) for cycle in result.cycles],
            "applyValid": not analysis.validation[result.name],
            "checks": [
                {"waiter": c.waiter, "driver": c.driver, "waits": bool(c.path), "path": list(c.path)}
                for c in analysis.checks[result.name]
            ],
        })
    return {
        "openEpics": len(analysis.epics),
        "units": len(analysis.decisions),
        "missingFromMatrix": list(analysis.missing),
        "scenarios": scenarios,
    }


def _pair(text: str) -> Pair:
    waiter, sep, driver = text.partition(":")
    if not sep or not waiter or not driver:
        message: str = f"--expect takes <waiter bead>:<driver bead>, not {text!r}"
        raise argparse.ArgumentTypeError(message)
    return waiter, driver


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix", default=None, help="the matrix file (else ATW_MATRIX, else ATW_CONTROL_REPO)")
    parser.add_argument("--repo", type=Path, default=None, help="the repository whose beads to read")
    parser.add_argument("--report", type=Path, default=None, help="write the Markdown report here")
    parser.add_argument("--expect", type=_pair, action="append", default=[], help="spot-check <waiter>:<driver>")
    parser.add_argument("--apply", action="store_true", help="write the chosen scenario's edges as beads tracks edges")
    parser.add_argument("--scenario", choices=(SCENARIO_AS_IS, SCENARIO_SHARED), default=SCENARIO_AS_IS)
    parser.add_argument("--dry-run", action="store_true", help="with --apply, list the writes and make none")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Compute the order, write the report, and apply the chosen edges when asked.

    Returns:
        The exit status.

    """
    args = _arguments(argv)
    matrix: Matrix = read_matrix(matrix_path(args.matrix, os.environ))
    graph: beadgraph.Graph = beadgraph.load(args.repo)
    analysis: Analysis = analyse(matrix, graph, args.expect)
    if args.report is not None:
        from epicorderreport import render  # ruff: ignore[import-outside-top-level] - the report module is needed only for --report.

        args.report.write_text(render(analysis), encoding="utf-8")
    out: JsonObject = summary(analysis)
    if args.apply:
        name: str = "A" if args.scenario == SCENARIO_AS_IS else "B"
        chosen: Order = next(result for result in analysis.orders if result.name == name)
        writer = beadgraph.Writer(args.repo, dry_run=args.dry_run)
        applied: JsonObject = json_object(
            edgeset.apply_edges(
                graph,
                proposal(chosen, analysis.decisions, analysis.epics),
                writer,
                edgeset.ApplyScope(seen={}, level="epic"),
            ),
        )
        out["apply"] = {"scenario": name, **{k: v for k, v in applied.items() if k != "plan"}}
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
