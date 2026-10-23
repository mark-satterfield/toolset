#!/usr/bin/env python3
"""Compute the order in which Epics are architected and approved, from the matrix and beads alone.

No model is called. For every architecture entry the open Epics touch (a feature, a document
heading, a service, component, infrastructure, event, stack and so on, architecture side only)
the script names ONE driver, the Epic whose requirements the entry is designed from, and every
other Epic that touches the entry waits for it (driver -> user, never user -> user):

1. an explicit matrix ``drives`` relationship to the entry, or to a document heading that
   describes it;
2. else an Epic whose requirements the heading that states the entry ``covers``
   (``describedBy`` + ``covers`` + ``hasRequirement``);
3. else every Epic that touches it (first come, first elaborated).

Several candidates are settled by the keeper's selection order (``ops/sdlc-automation/
selection.py`` and ``ordering.py``): the highest WSJF first, an Epic with no WSJF last, then
the bead id. An Epic touches an entry by the rule of reach (``matrixtraverse.rule_reach``),
through the headings covering its requirements, or through its ``drives`` and ``restsOn``
relationships. An entry whose matrix ``approved`` flag is set makes no edge. Cycles are
broken by the same rank (an edge from a lower-ranked to a higher-ranked member of a cycle is
dropped), and the result is transitively reduced.

Four variants are computed: as the matrix stands (A), as if every entry of a ``shared-*``
stack were approved (B), and each without the over-broad entries (touched by more than
``--broad-share`` of the open Epics). ``--report`` writes the Markdown report
(``epicorderreport.py``); stdout carries one JSON summary. ``--apply`` writes the chosen
variant's edges as the owned beads ``tracks`` edges through ``edgeset.apply_edges`` (the
``apply-edges`` path, every owned Epic edge at once); hand-made edges stay.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Final

import portfolio_path  # ruff: ignore[unused-import] - puts the beads-contract and artifact-handoff scripts on sys.path.

# isort: split
import beadgraph
import edgeset
from contracts import json_object
from matrix_contract import (
    AUTHORITY_SIDE,
    KIND_DOCUMENT,
    KIND_STACK,
    REL_COVERS,
    REL_DESCRIBED_BY,
    REL_DRIVES,
    REL_HAS_REQUIREMENT,
    REL_REALIZED_BY,
    REL_RESTS_ON,
    EntryId,
)
from matrixstore import Matrix, matrix_path, read_matrix
from matrixtraverse import Heading, epic_id, heading_index, rule_reach_indexed, stacks_of

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from contracts import JsonObject, JsonValue

type Unit = str
"""An architecture entry id, or ``<document id>#<heading>`` for one heading of a document."""
type Pair = tuple[str, str]
"""An edge: the Epic elaborated first, then the Epic that waits for it."""

DECISION_KINDS: Final[frozenset[str]] = frozenset({
    "feature",
    "document",
    "service",
    "component",
    "infrastructure",
    "event",
    "stack",
    "package",
    "layer",
    "file",
})
SHARED_PREFIX: Final = "shared-"
HEADING_MARK: Final = "#"
RULE_DRIVES: Final = "drives"
RULE_COVERS: Final = "covers"
RULE_FIRST: Final = "first-come"
SCENARIO_AS_IS: Final = "as-is"
SCENARIO_SHARED: Final = "shared-approved"
DEFAULT_BROAD_SHARE: Final = 0.25
SENSITIVITY_LIMITS: Final[tuple[int, ...]] = (2, 3, 5, 10)


@dataclass(frozen=True, slots=True)
class Epic:
    """One open Epic with what ranks it."""

    id: str
    title: str
    wsjf: float | None


@dataclass(frozen=True, slots=True)
class Decision:
    """One architecture entry, the Epic that drives it, the rule that chose it, and its users."""

    unit: Unit
    driver: str
    rule: str
    users: tuple[str, ...]

    @property
    def epics(self) -> frozenset[str]:
        """Every Epic on the entry: the driver and its users."""
        return frozenset({self.driver, *self.users})


@dataclass(frozen=True, slots=True)
class Cycle:
    """One strongly connected set of Epics, the edges inside it, and the edges dropped to break it."""

    members: tuple[str, ...]
    edges: Mapping[Pair, tuple[Unit, ...]]
    dropped: tuple[Pair, ...]


@dataclass(frozen=True, slots=True)
class Order:
    """One variant's result: its edges before and after cycle breaking and reduction, and the levels."""

    name: str
    excluded: int
    raw: Mapping[Pair, tuple[Unit, ...]]
    cycles: tuple[Cycle, ...]
    edges: Mapping[Pair, tuple[Unit, ...]]
    levels: Mapping[str, int]
    unlocks: Mapping[str, int]
    chain: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Analysis:
    """Everything the report shows."""

    epics: Mapping[str, Epic]
    decisions: tuple[Decision, ...]
    broad: tuple[Decision, ...]
    broad_share: float
    orders: tuple[Order, ...]
    current: Mapping[Pair, bool]
    """Each standing ``tracks`` edge between two open Epics, with whether this system owns it."""
    missing: tuple[str, ...]
    """Open Epics the matrix does not hold."""
    validation: Mapping[str, tuple[str, ...]]
    """Each variant's name with the cycle ``apply-edges`` would refuse its edges for (empty: accepted)."""
    sensitivity: tuple[tuple[int, Order], ...]
    """Scenario A kept to the entries at most that many Epics touch, for each such limit."""


def rank_key(epic: Epic) -> tuple[int, float, str]:
    """Order Epics as the keeper selects them: highest WSJF first, unscored last, then id.

    Returns:
        The sort key.

    """
    return (0 if epic.wsjf is not None else 1, -(epic.wsjf or 0.0), epic.id)


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


def _heading_of(attributes: Mapping[str, object]) -> str:
    value: object = attributes.get("heading")
    return value if isinstance(value, str) else ""


def _epic_of_requirement(matrix: Matrix, requirement: EntryId) -> set[str]:
    return {rel.start.removeprefix("epic:") for rel in matrix.incoming(requirement, (REL_HAS_REQUIREMENT,))}


@dataclass(slots=True)
class _Touches:
    touchers: dict[Unit, set[str]]
    explicit: dict[Unit, set[str]]
    covered: dict[Unit, set[str]]


def _decision_unit(matrix: Matrix, unit: Unit) -> bool:
    entry = matrix.find(unit_entry(unit))
    return entry is not None and entry.side == AUTHORITY_SIDE and entry.kind in DECISION_KINDS


def _describing(matrix: Matrix) -> dict[EntryId, set[Unit]]:
    found: dict[EntryId, set[Unit]] = {}
    for rel in matrix.relationships((REL_DESCRIBED_BY,)):
        if rel.side == AUTHORITY_SIDE:
            found.setdefault(rel.start, set()).add(heading_unit(rel.end, _heading_of(rel.attributes)))
    return found


def _covering(matrix: Matrix, epics: Collection[str]) -> dict[Unit, set[str]]:
    found: dict[Unit, set[str]] = {}
    for rel in matrix.relationships((REL_COVERS,)):
        owners: set[str] = _epic_of_requirement(matrix, rel.end) & set(epics)
        if rel.side == AUTHORITY_SIDE and owners:
            found.setdefault(heading_unit(rel.start, _heading_of(rel.attributes)), set()).update(owners)
    return found


def _touch_epic(matrix: Matrix, bead: str, index: Mapping[Heading, list[EntryId]], touches: _Touches) -> None:
    reach = rule_reach_indexed(matrix, epic_id(bead), index)
    units: set[Unit] = set(chain(reach.features, reach.entries, reach.stacks, reach.dependencies))
    for requirement in reach.requirements:
        units.update(
            heading_unit(rel.start, _heading_of(rel.attributes)) for rel in matrix.incoming(requirement, (REL_COVERS,))
        )
    for rel in matrix.outgoing(epic_id(bead), (REL_DRIVES, REL_RESTS_ON)):
        heading: str = _heading_of(rel.attributes)
        unit: Unit = heading_unit(rel.end, heading) if rel.end.startswith(KIND_DOCUMENT) else rel.end
        units.add(unit)
        if rel.kind == REL_DRIVES:
            touches.explicit.setdefault(unit, set()).add(bead)
    for unit in units:
        touches.touchers.setdefault(unit, set()).add(bead)


def collect(matrix: Matrix, epics: Collection[str]) -> _Touches:
    """Find, for every architecture entry the open Epics touch, who touches it and who may drive it.

    Returns:
        The touching Epics, the explicit drivers and the covering-heading drivers of each unit.

    """
    touches = _Touches({}, {}, {})
    index: dict[Heading, list[EntryId]] = heading_index(matrix)
    for bead in sorted(epics):
        _touch_epic(matrix, bead, index, touches)
    describing: dict[EntryId, set[Unit]] = _describing(matrix)
    covering: dict[Unit, set[str]] = _covering(matrix, epics)
    for unit in list(touches.touchers):
        headings: set[Unit] = {unit} if HEADING_MARK in unit else describing.get(EntryId(unit), set())
        whole: set[Unit] = {unit_entry(h) for h in headings}
        drivers: set[str] = set().union(*(touches.explicit.get(h, set()) for h in headings | whole))
        if drivers:
            touches.explicit.setdefault(unit, set()).update(drivers)
        covers: set[str] = set().union(*(covering.get(h, set()) for h in headings))
        if covers:
            touches.covered[unit] = covers
    for unit in [u for u in touches.touchers if not _decision_unit(matrix, u)]:
        del touches.touchers[unit]
    return touches


def decide(touches: _Touches, epics: Mapping[str, Epic]) -> list[Decision]:
    """Name the one driver of every touched entry and its users.

    Returns:
        One decision per unit, in unit order.

    """

    def rank(bead: str) -> tuple[int, float, str]:
        return rank_key(epics[bead])

    decisions: list[Decision] = []
    for unit in sorted(touches.touchers):
        pools: tuple[tuple[str, set[str]], ...] = (
            (RULE_DRIVES, touches.explicit.get(unit, set())),
            (RULE_COVERS, touches.covered.get(unit, set())),
            (RULE_FIRST, touches.touchers[unit]),
        )
        rule, pool = next((name, found) for name, found in pools if found)
        driver: str = min(pool, key=rank)
        users: tuple[str, ...] = tuple(sorted(touches.touchers[unit] - {driver}))
        decisions.append(Decision(unit, driver, rule, users))
    return decisions


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
    if entry.kind == "feature":
        realizers: list[EntryId] = [rel.end for rel in matrix.outgoing(entry.id, (REL_REALIZED_BY,))]
        if realizers:
            return all(is_shared(matrix, realizer, index) for realizer in realizers)
        headings: list[Unit] = [
            heading_unit(rel.end, _heading_of(rel.attributes))
            for rel in matrix.outgoing(entry.id, (REL_DESCRIBED_BY,))
            if HEADING_MARK in heading_unit(rel.end, _heading_of(rel.attributes))
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
    """Draw driver -> user for every decision, each pair with the entries that make it.

    Returns:
        Each edge with its deciding entries, sorted.

    """
    found: dict[Pair, set[Unit]] = {}
    for decision in decisions:
        for user in decision.users:
            found.setdefault((decision.driver, user), set()).add(decision.unit)
    return {pair: tuple(sorted(units)) for pair, units in sorted(found.items())}


def components(nodes: Iterable[str], edges: Iterable[Pair]) -> list[tuple[str, ...]]:
    """Find the strongly connected sets of Epics with more than one member: Epics that reach each other.

    Returns:
        Each cycle's members, sorted, in member order.

    """
    successors: dict[str, list[str]] = {}
    for start, end in edges:
        successors.setdefault(start, []).append(end)
    reach: dict[str, set[str]] = {node: _descendants(successors, node) for node in nodes}
    found: set[tuple[str, ...]] = set()
    for node, beyond in reach.items():
        members: tuple[str, ...] = tuple(sorted({node} | {other for other in beyond if node in reach[other]}))
        if len(members) > 1:
            found.add(members)
    return sorted(found)


def break_cycles(
    edges: Mapping[Pair, tuple[Unit, ...]],
    epics: Mapping[str, Epic],
) -> tuple[dict[Pair, tuple[Unit, ...]], list[Cycle]]:
    """Break every cycle by the keeper's rank: drop each edge inside a cycle that runs from a lower to a higher rank.

    Returns:
        The acyclic edges, and each cycle with its inside edges and the edges dropped.

    """
    cycles: list[Cycle] = []
    kept: dict[Pair, tuple[Unit, ...]] = dict(edges)
    for members in components(epics, edges):
        inside: dict[Pair, tuple[Unit, ...]] = {
            pair: units for pair, units in edges.items() if pair[0] in members and pair[1] in members
        }
        dropped: list[Pair] = [pair for pair in inside if rank_key(epics[pair[0]]) > rank_key(epics[pair[1]])]
        for pair in dropped:
            del kept[pair]
        cycles.append(Cycle(members, inside, tuple(dropped)))
    return kept, cycles


def _descendants(successors: Mapping[str, list[str]], start: str) -> set[str]:
    seen: set[str] = set()
    todo: list[str] = list(successors.get(start, []))
    while todo:
        node: str = todo.pop()
        if node not in seen:
            seen.add(node)
            todo.extend(successors.get(node, []))
    return seen


def reduce(edges: Mapping[Pair, tuple[Unit, ...]]) -> dict[Pair, tuple[Unit, ...]]:
    """Drop A -> C wherever a longer path A -> ... -> C exists (the DAG's transitive reduction).

    Returns:
        The edges that remain.

    """
    successors: dict[str, list[str]] = {}
    for start, end in edges:
        successors.setdefault(start, []).append(end)
    redundant: set[Pair] = set()
    for start, ends in successors.items():
        beyond: set[str] = set().union(*(_descendants(successors, end) for end in ends))
        redundant.update((start, end) for end in ends if end in beyond)
    return {pair: units for pair, units in edges.items() if pair not in redundant}


def layer(
    epics: Mapping[str, Epic],
    edges: Iterable[Pair],
) -> tuple[dict[str, int], dict[str, int], tuple[str, ...]]:
    """Level every Epic (1 = can start now), count what each unlocks, and find the longest chain.

    Returns:
        Each Epic's level, each Epic's count of transitive dependents, and the longest chain.

    """
    successors: dict[str, list[str]] = {}
    predecessors: dict[str, list[str]] = {bead: [] for bead in epics}
    for start, end in edges:
        successors.setdefault(start, []).append(end)
        predecessors[end].append(start)
    levels: dict[str, int] = {}

    def level_of(bead: str) -> int:
        if bead not in levels:
            levels[bead] = 1 + max((level_of(p) for p in predecessors[bead]), default=0)
        return levels[bead]

    for bead in sorted(epics):
        level_of(bead)
    unlocks: dict[str, int] = {bead: len(_descendants(successors, bead)) for bead in epics}

    def by_rank(bead: str) -> tuple[int, int, float, str]:
        return (-levels[bead], *rank_key(epics[bead]))

    node: str = min(epics, key=by_rank)
    path: list[str] = [node]
    while predecessors[node]:
        node = min((p for p in predecessors[node] if levels[p] == levels[node] - 1), key=by_rank)
        path.append(node)
    return levels, unlocks, tuple(reversed(path))


def order(
    name: str,
    decisions: Iterable[Decision],
    excluded: Collection[Unit],
    epics: Mapping[str, Epic],
) -> Order:
    """Compute one variant: the edges of the entries it keeps, cycles broken, reduced and levelled.

    Returns:
        The variant's result.

    """
    every: list[Decision] = list(decisions)
    kept: list[Decision] = [decision for decision in every if decision.unit not in excluded]
    raw: dict[Pair, tuple[Unit, ...]] = raw_edges(kept)
    acyclic, cycles = break_cycles(raw, epics)
    edges: dict[Pair, tuple[Unit, ...]] = reduce(acyclic)
    levels, unlocks, longest = layer(epics, edges)
    return Order(name, len(every) - len(kept), raw, tuple(cycles), edges, levels, unlocks, longest)


def read_epics(graph: beadgraph.Graph) -> dict[str, Epic]:
    """Read the open Epics with their titles and WSJF from the tracker.

    Returns:
        Each open Epic by id.

    """
    found: dict[str, Epic] = {}
    for bead in graph.of_kind("epic"):
        if bead.closed:
            continue
        raw: str = bead.metadata.get("wsjf", "").strip()
        try:
            wsjf: float | None = float(raw) if raw else None
        except ValueError:
            wsjf = None
        found[bead.id] = Epic(bead.id, bead.title.removeprefix("Feature PRD: ").strip(), wsjf)
    return found


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
    """Turn a variant's edges into the edge proposal ``apply-edges`` takes.

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
                    f"{first.unit} is designed from {epics[blocker].title}'s requirements ({first.rule}); "
                    f"{epics[blocked].title} touches it{more}"
                ),
                confidence="low",
                arch_check=f"{', '.join(units)}: the matrix holds no approved flag on it (epicorder.py)",
            ),
        )
    return edges


def _refusal(report: edgeset.ValidationReport) -> tuple[str, ...]:
    if report["ok"]:
        return ()
    return tuple(report["cycle"]) or ("refused: " + json.dumps({k: v for k, v in report.items() if v}),)


def analyse(matrix: Matrix, graph: beadgraph.Graph, broad_share: float) -> Analysis:
    """Run the whole computation over one read of the matrix and the tracker.

    Returns:
        Everything the report shows.

    """
    epics: dict[str, Epic] = read_epics(graph)
    missing: tuple[str, ...] = tuple(sorted(bead for bead in epics if matrix.find(epic_id(bead)) is None))
    held: dict[str, Epic] = {bead: epic for bead, epic in epics.items() if bead not in missing}
    decisions: list[Decision] = decide(collect(matrix, held), epics)
    threshold: float = broad_share * len(epics)
    broad: list[Decision] = [d for d in decisions if len(d.epics) > threshold]
    broad_units: set[Unit] = {d.unit for d in broad}
    index: dict[Heading, list[EntryId]] = heading_index(matrix)
    shared: set[Unit] = {d.unit for d in decisions if is_shared(matrix, d.unit, index)}
    approved: set[Unit] = {d.unit for d in decisions if is_approved(matrix, d.unit)}
    variants: tuple[tuple[str, set[Unit]], ...] = (
        ("A", approved),
        ("A without over-broad entries", approved | broad_units),
        ("B", approved | shared),
        ("B without over-broad entries", approved | shared | broad_units),
    )
    orders: tuple[Order, ...] = tuple(order(name, decisions, out, epics) for name, out in variants)
    by_unit: dict[Unit, Decision] = {d.unit: d for d in decisions}
    validation: dict[str, tuple[str, ...]] = {
        result.name: _refusal(edgeset.validate(graph, proposal(result, by_unit, epics))) for result in orders
    }
    sensitivity: tuple[tuple[int, Order], ...] = tuple(
        (
            limit,
            order(
                f"A, at most {limit}",
                decisions,
                approved | {d.unit for d in decisions if len(d.epics) > limit},
                epics,
            ),
        )
        for limit in SENSITIVITY_LIMITS
    )
    return Analysis(
        epics,
        tuple(decisions),
        tuple(broad),
        broad_share,
        orders,
        current_edges(graph, epics),
        missing,
        validation,
        sensitivity,
    )


def summary(analysis: Analysis) -> JsonObject:
    """Summarise each variant for stdout.

    Returns:
        The summary.

    """
    variants: list[JsonValue] = []
    for result in analysis.orders:
        sizes: list[int] = [list(result.levels.values()).count(n) for n in range(1, max(result.levels.values()) + 1)]
        variants.append({
            "variant": result.name,
            "edges": len(result.edges),
            "startNow": sizes[0],
            "levels": len(sizes),
            "maxConcurrency": max(sizes),
            "longestChain": len(result.chain),
            "cycles": len(result.cycles),
            "cycleEdgesDropped": sum(len(c.dropped) for c in result.cycles),
            "applyValid": not analysis.validation[result.name],
        })
    return {
        "openEpics": len(analysis.epics),
        "entries": len(analysis.decisions),
        "overBroad": [d.unit for d in analysis.broad],
        "missingFromMatrix": list(analysis.missing),
        "variants": variants,
    }


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix", default=None, help="the matrix file (else ATW_MATRIX, else ATW_CONTROL_REPO)")
    parser.add_argument("--repo", type=Path, default=None, help="the repository whose beads to read")
    parser.add_argument("--broad-share", type=float, default=DEFAULT_BROAD_SHARE, help="over-broad share of Epics")
    parser.add_argument("--report", type=Path, default=None, help="write the Markdown report here")
    parser.add_argument("--apply", action="store_true", help="write the chosen variant's edges as beads tracks edges")
    parser.add_argument("--scenario", choices=(SCENARIO_AS_IS, SCENARIO_SHARED), default=SCENARIO_AS_IS)
    parser.add_argument("--without-broad", action="store_true", help="apply the variant without over-broad entries")
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
    analysis: Analysis = analyse(matrix, graph, args.broad_share)
    if args.report is not None:
        from epicorderreport import render  # ruff: ignore[import-outside-top-level] - the report module is needed only for --report.

        args.report.write_text(render(analysis), encoding="utf-8")
    out: JsonObject = summary(analysis)
    if args.apply:
        name: str = ("A" if args.scenario == SCENARIO_AS_IS else "B") + (
            " without over-broad entries" if args.without_broad else ""
        )
        chosen: Order = next(result for result in analysis.orders if result.name == name)
        by_unit: dict[Unit, Decision] = {d.unit: d for d in analysis.decisions}
        writer = beadgraph.Writer(args.repo, dry_run=args.dry_run)
        applied: JsonObject = json_object(
            edgeset.apply_edges(
                graph,
                proposal(chosen, by_unit, analysis.epics),
                writer,
                edgeset.ApplyScope(seen={}, level="epic"),
            ),
        )
        out["apply"] = {"variant": name, **{k: v for k, v in applied.items() if k != "plan"}}
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
