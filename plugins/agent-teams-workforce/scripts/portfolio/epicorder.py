#!/usr/bin/env python3
"""Compute the order in which Epics are architected and approved, from the matrix and beads alone.

No model is called and no ordering is assumed: neither WSJF nor any rank enters the edges. An
edge says that one Epic uses an architecture entry another Epic's own requirements define, so the
user is elaborated after the definer (the driver). Both are read from the chain alone
(``matrixtraverse.rule_reach``): Epic, ``hasRequirement``, requirement, ``servedBy``, feature,
``realizedBy``, the entry that realizes it, and ``homeIn``, its stack.

1. An Epic defines each entry a feature serving one of its requirements is ``realizedBy``, and
   the stack each such entry is or has its home in.
2. An Epic uses each entry that is the far end of a dependency (one hop: ``imports``, ``calls``,
   ``publishes``, ``reads`` and the rest of the dependency family) from an entry or stack it
   defines, and that it does not itself define.

A unit is an entry some Epic uses. Its drivers are the Epics that define it; its users are the
Epics that use it. Every driver of a unit gets an edge to every user of it. Co-drivers of one unit
get no edge between them: two Epics whose features are realized by one entry, or by entries of one
stack, do not wait for each other. A unit no Epic defines (a VPC, the chassis library, a Cognito
pool no feature is realized by) makes no edge: the first Epic elaborated reviews and approves it. A
unit whose matrix ``approved`` flag is set makes no edge. Cycles are reported, never broken: their
members share a level. The rest is transitively reduced over the cycles taken as single nodes.

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
from matrix_contract import KIND_STACK, EntryId
from matrixstore import Matrix, matrix_path, read_matrix
from matrixtraverse import RuleReach, epic_id, rule_reach, stacks_of

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from contracts import JsonObject, JsonValue

type Unit = str
"""The id of an entry some Epic uses: a service, component, infrastructure, layer, package or stack."""
type Pair = tuple[str, str]
"""An edge: the driver, elaborated first, then the Epic that waits for it."""

SHARED_PREFIX: Final = "shared-"
EPIC_PREFIX: Final = "epic:"
RULE_CHAIN: Final = "realizedBy and homeIn"
"""The evidence that makes an Epic a unit's driver: its features are realized by the unit or by an entry homed in it."""
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


def _reaches(matrix: Matrix, epics: Collection[str]) -> dict[str, RuleReach]:
    """Walk every open Epic the matrix holds by the rule of reach.

    Returns:
        Each Epic's beads id with what its chain reaches.

    """
    return {bead: rule_reach(matrix, epic_id(bead)) for bead in sorted(epics)}


def _label(matrix: Matrix, unit: Unit) -> str:
    entry = matrix.find(EntryId(unit))
    return unit if entry is None else f"{entry.name} ({unit})"


def _by_unit(found: Iterable[tuple[str, Iterable[EntryId]]]) -> dict[Unit, set[str]]:
    """Index Epics by the units each one names.

    Returns:
        Each unit with the Epics that name it.

    """
    indexed: dict[Unit, set[str]] = {}
    bead: str
    units: Iterable[EntryId]
    for bead, units in found:
        indexed.update({unit: {*indexed.get(unit, set()), bead} for unit in units})
    return indexed


def decide(matrix: Matrix, epics: Collection[str]) -> dict[Unit, Decision]:
    """Name the drivers and users of every unit that has both.

    Returns:
        Each unit's decision, in unit order.

    """
    reaches: dict[str, RuleReach] = _reaches(matrix, epics)
    defined: dict[Unit, set[str]] = _by_unit((bead, {*reach.entries, *reach.stacks}) for bead, reach in reaches.items())
    used: dict[Unit, set[str]] = _by_unit((bead, reach.dependencies) for bead, reach in reaches.items())
    decisions: dict[Unit, Decision] = {}
    unit: Unit
    for unit in sorted(set(used) & set(defined)):
        users: set[str] = used[unit] - defined[unit]
        if users:
            drivers: tuple[str, ...] = tuple(sorted(defined[unit]))
            decisions[unit] = Decision(unit, _label(matrix, unit), drivers, RULE_CHAIN, tuple(sorted(users)))
    return decisions


def is_shared(matrix: Matrix, unit: Unit) -> bool:
    """Tell whether an entry belongs to a ``shared-*`` stack (the central event API and bus included).

    A stack is shared when its name or repository starts with ``shared-``; any other entry when the
    stack it is homed in is.

    Returns:
        True for a shared entry.

    """
    entry = matrix.find(EntryId(unit))
    if entry is None:
        return False
    if entry.kind == KIND_STACK:
        repository: object = entry.attributes.get("repository")
        return unit.startswith(f"{KIND_STACK}:{SHARED_PREFIX}") or (
            isinstance(repository, str) and repository.startswith(SHARED_PREFIX)
        )
    stacks: set[EntryId] = stacks_of(matrix, entry.id)
    return bool(stacks) and all(is_shared(matrix, stack) for stack in stacks)


def is_approved(matrix: Matrix, unit: Unit) -> bool:
    """Read the matrix ``approved`` flag of the entry a unit belongs to.

    Returns:
        True when the entry carries the flag.

    """
    entry = matrix.find(EntryId(unit))
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
    approved: set[Unit] = {unit for unit in decisions if is_approved(matrix, unit)}
    shared: set[Unit] = {unit for unit in decisions if is_shared(matrix, unit)}
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
