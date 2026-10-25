#!/usr/bin/env python3
"""Compute every Epic-to-Epic dependency edge from the matrix alone, and replace the edges in beads with them.

The owner runs it once, for the whole portfolio, before ``keeper.py`` runs. The Epics and
everything that decides the edges are read from the matrix only. No model is called, no agent or
workflow is started and no ordering is assumed: neither WSJF nor any rank enters the edges. An
edge says that one Epic uses an architecture entry another Epic's own requirements define, so the
user is elaborated after the definer (the driver). Both are read from the chain alone
(``matrixtraverse.rule_reach``): Epic, ``hasRequirement``, requirement, ``servedBy``, feature,
``realizedBy``, the entry that realizes it, and ``homeIn``, its stack.

1. Each entry has exactly one defining Epic: among the Epics with a serving feature
   ``realizedBy`` the entry, the one with the most distinct such features; a tie goes to the
   lowest bead id. A stack is an entry like any other: it is defined only through the features
   ``realizedBy`` the stack itself, never through the entries homed in it.
2. Every other Epic that touches the entry is a user of it: it has a serving feature
   ``realizedBy`` the entry, or it reaches the entry as the far end of a dependency (one hop:
   ``imports``, ``calls``, ``publishes``, ``reads`` and the rest of the dependency family) from
   an entry it realizes or the stack such an entry is or has its home in.

A unit is an entry with a defining Epic and at least one user. The definer gets one edge to each
user; an Epic never gets an edge to itself, and the edges several units make between one pair
collapse into one. An entry no serving feature is ``realizedBy`` (a VPC, a Cognito pool) makes no
edge: the first Epic elaborated reviews and approves it. A unit whose matrix ``approved`` flag is
set makes no edge. Cycles are reported, never broken: their members share a level. The rest is
transitively reduced over the cycles taken as single nodes.

Two scenarios are computed: as the matrix stands (A), and as if every entry of a ``shared-*``
stack were approved (B). ``--report`` writes the Markdown report (``epicorderreport.py``), with
``--expect <waiter>:<driver>`` spot-checks; stdout carries one JSON summary. ``--apply`` makes
the Epic-to-Epic dependency edges in beads exactly the chosen scenario's edges: it removes every
standing ``tracks`` and ``blocks`` edge between two Epics, whoever made it, and writes each
computed edge as a ``tracks`` edge. It writes nothing else: no Task, Story, WSJF value or record.
It refuses, writing nothing, a scenario whose edges close a cycle (every Epic in it would wait
for good) or name an Epic beads does not hold. ``--apply --dry-run`` prints the removals, the
additions and any such refusal, and writes nothing. Beads is read only to
list the standing Epic-to-Epic edges (``--apply``, and the report's comparison with them).
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
from contracts import json_object
from matrix_contract import KIND_EPIC, KIND_STACK, EntryId
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
SCENARIO_AS_IS: Final = "as-is"
SCENARIO_SHARED: Final = "shared-approved"
TITLE_PREFIX: Final = "Feature PRD: "
EPIC_EDGE_TYPES: Final = (beadgraph.TRACKS, beadgraph.BLOCKS)
"""The dependency types the pipeline reads as an Epic's prerequisites; ``--apply`` removes both between Epics."""
LIST_EPICS: Final = ("list", "--type", "epic", "--all", "--json", "-n", "0", "--brief", "--readonly")


@dataclass(frozen=True, slots=True)
class Epic:
    """One Epic the matrix holds."""

    id: str
    title: str


@dataclass(frozen=True, slots=True)
class StandingEdge:
    """One dependency edge between two Epics in beads: ``blocked`` depends on ``blocker``."""

    blocker: str
    blocked: str
    kind: str


@dataclass(frozen=True, slots=True)
class Decision:
    """One unit, the one Epic that defines it, how many of its features the unit realizes, and its users."""

    unit: Unit
    label: str
    driver: str
    features: int
    """The number of distinct features of the driver that are ``realizedBy`` the unit."""
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
    standing: tuple[StandingEdge, ...] | None
    """Every dependency edge between two Epics in beads, or None when beads was not read."""
    checks: Mapping[str, tuple[Check, ...]]
    """Each scenario's name with its spot-checks."""


def _reaches(matrix: Matrix, epics: Collection[str]) -> dict[str, RuleReach]:
    """Walk every Epic the matrix holds by the rule of reach.

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


def _realizing(reaches: Mapping[str, RuleReach]) -> dict[Unit, dict[str, int]]:
    """Count, for every entry a serving feature is ``realizedBy``, each Epic's distinct such features.

    ``RuleReach.entries`` names one ``realizedBy <feature>`` way per feature that realizes the entry,
    so the number of ways is the number of distinct features.

    Returns:
        Each entry with each realizing Epic and its feature count.

    """
    counts: dict[Unit, dict[str, int]] = {}
    found: Iterable[tuple[Unit, str, int]] = (
        (unit, bead, len(ways)) for bead, reach in reaches.items() for unit, ways in reach.entries.items()
    )
    for unit, bead, count in found:
        counts.setdefault(unit, {})[bead] = count
    return counts


def definer(counts: Mapping[str, int]) -> str:
    """Name the one Epic that defines an entry: the most realizing features, a tie to the lowest bead id.

    Args:
        counts: Each realizing Epic with its number of distinct features ``realizedBy`` the entry.

    Returns:
        The defining Epic's bead id.

    Raises:
        ValueError: ``counts`` is empty.

    """
    if not counts:
        message: str = "an entry no Epic realizes has no definer"
        raise ValueError(message)
    return min(counts, key=lambda bead: (-counts[bead], bead))


def decide(matrix: Matrix, epics: Collection[str]) -> dict[Unit, Decision]:
    """Name the one definer and the users of every entry that has both.

    Returns:
        Each unit's decision, in unit order.

    """
    reaches: dict[str, RuleReach] = _reaches(matrix, epics)
    realized: dict[Unit, dict[str, int]] = _realizing(reaches)
    touched: dict[Unit, set[str]] = _by_unit(
        (bead, {*reach.entries, *reach.dependencies}) for bead, reach in reaches.items()
    )
    decisions: dict[Unit, Decision] = {}
    unit: Unit
    for unit in sorted(realized):
        driver: str = definer(realized[unit])
        users: set[str] = touched[unit] - {driver}
        if users:
            decisions[unit] = Decision(unit, _label(matrix, unit), driver, realized[unit][driver], tuple(sorted(users)))
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
    """Draw driver -> user for every user of every decision, each pair with its units.

    Returns:
        Each edge with the units that make it, sorted.

    """
    found: dict[Pair, set[Unit]] = {}
    pairs: Iterable[tuple[Pair, Unit]] = (
        ((decision.driver, user), decision.unit) for decision in decisions for user in decision.users
    )
    for pair, unit in pairs:
        found.setdefault(pair, set()).add(unit)
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


def read_epics(matrix: Matrix) -> dict[str, Epic]:
    """Read every Epic the matrix holds, with its title.

    Returns:
        Each Epic by its beads id.

    """
    prefix: str = f"{KIND_EPIC}:"
    epics: list[Epic] = [
        Epic(entry.id.removeprefix(prefix), entry.name.removeprefix(TITLE_PREFIX).strip())
        for entry in matrix.entries((KIND_EPIC,))
    ]
    return {epic.id: epic for epic in epics}


def _epic_beads(repo: Path | None) -> list[beadgraph.Bead]:
    """List every Epic bead, closed ones included, with its dependencies, in one read-only ``bd`` call.

    Returns:
        The Epic beads.

    Raises:
        beadgraph.GraphError: ``bd`` failed or did not return an array.

    """
    payload: object = json.loads(beadgraph.run_bd(list(LIST_EPICS), repo))
    if not isinstance(payload, list):
        message: str = "`bd list --type epic --json` did not return an array"
        raise beadgraph.GraphError(message)
    return [beadgraph.bead_of(json_object(record)) for record in payload]


def standing_edges(beads: Iterable[beadgraph.Bead]) -> tuple[StandingEdge, ...]:
    """Name every ``tracks`` and ``blocks`` edge whose two ends are Epics.

    Returns:
        Each edge, in (blocked, blocker) order.

    """
    listed: list[beadgraph.Bead] = list(beads)
    epic_ids: set[str] = {bead.id for bead in listed}
    found: list[StandingEdge] = [
        StandingEdge(blocker, bead.id, kind)
        for bead in listed
        for kind, blockers in ((beadgraph.TRACKS, bead.tracked), (beadgraph.BLOCKS, bead.blockers))
        for blocker in blockers
        if blocker in epic_ids
    ]
    return tuple(sorted(found, key=lambda edge: (edge.blocked, edge.blocker)))


def analyse(matrix: Matrix, expected: Iterable[Pair], standing: tuple[StandingEdge, ...] | None) -> Analysis:
    """Run the whole computation over one read of the matrix.

    Args:
        matrix: The matrix, the one source of the Epics and of the edges.
        expected: The spot-checks to answer, each (waiter, driver).
        standing: The Epic-to-Epic edges in beads, or None when beads was not read.

    Returns:
        Everything the report shows.

    """
    epics: dict[str, Epic] = read_epics(matrix)
    decisions: dict[Unit, Decision] = decide(matrix, epics)
    approved: set[Unit] = {unit for unit in decisions if is_approved(matrix, unit)}
    shared: set[Unit] = {unit for unit in decisions if is_shared(matrix, unit)}
    orders: tuple[Order, ...] = (
        order("A", decisions.values(), approved, epics),
        order("B", decisions.values(), approved | shared, epics),
    )
    pairs: list[Pair] = list(expected)
    checks: dict[str, tuple[Check, ...]] = {
        result.name: tuple(check(result, waiter, driver) for waiter, driver in pairs) for result in orders
    }
    return Analysis(epics, decisions, orders, standing, checks)


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
            "checks": [
                {"waiter": c.waiter, "driver": c.driver, "waits": bool(c.path), "path": list(c.path)}
                for c in analysis.checks[result.name]
            ],
        })
    return {"epics": len(analysis.epics), "units": len(analysis.decisions), "scenarios": scenarios}


def _refusal(chosen: Order, in_beads: Collection[str]) -> str:
    """Say why the scenario's edges cannot be written, or nothing when they can.

    A cycle would hold every Epic in it out of elaboration for good, and an edge onto an Epic beads
    does not hold cannot be written.

    Returns:
        The reason, or an empty string.

    """
    absent: list[str] = sorted({bead for pair in chosen.edges for bead in pair} - set(in_beads))
    cycles: list[str] = [", ".join(cycle.members) for cycle in chosen.cycles]
    reasons: list[str] = [
        *(f"the edges close a cycle among {members}" for members in cycles),
        *([f"the matrix holds Epics beads does not: {', '.join(absent)}"] if absent else []),
    ]
    return "; ".join(reasons) + ("; nothing is written" if reasons else "")


def replace_edges(
    chosen: Order,
    standing: tuple[StandingEdge, ...],
    in_beads: Collection[str],
    writer: beadgraph.Writer,
) -> JsonObject:
    """Remove every standing Epic-to-Epic edge, then write each of the scenario's edges as a ``tracks`` edge.

    Args:
        chosen: The scenario whose edges become the Epic-to-Epic edges.
        standing: Every Epic-to-Epic edge in beads.
        in_beads: The ids of the Epic beads.
        writer: The tracker writer; a dry-run writer records the writes and makes none.

    Returns:
        The removals and additions, each listed, and why a real run would refuse them (empty: it would not).

    Raises:
        ValueError: Outside a dry run, the edges close a cycle or name an Epic beads does not hold; nothing
            is written.

    """
    refusal: str = _refusal(chosen, in_beads)
    if refusal and not writer.dry_run:
        raise ValueError(refusal)
    for edge in standing:
        writer.bd(["dep", "remove", edge.blocked, edge.blocker])
    for blocker, blocked in chosen.edges:
        writer.bd(["dep", "add", blocked, blocker, "--type", beadgraph.TRACKS])
    return {
        "scenario": chosen.name,
        "dryRun": writer.dry_run,
        "refused": refusal,
        "removed": len(standing),
        "added": len(chosen.edges),
        "remove": [{"blocker": e.blocker, "blocked": e.blocked, "type": e.kind} for e in standing],
        "add": [
            {"blocker": blocker, "blocked": blocked, "type": beadgraph.TRACKS} for blocker, blocked in chosen.edges
        ],
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
    parser.add_argument("--repo", type=Path, default=None, help="the repository whose beads Epic edges to replace")
    parser.add_argument("--report", type=Path, default=None, help="write the Markdown report here")
    parser.add_argument("--expect", type=_pair, action="append", default=[], help="spot-check <waiter>:<driver>")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="replace every Epic-to-Epic edge in beads with the chosen scenario's edges",
    )
    parser.add_argument("--scenario", choices=(SCENARIO_AS_IS, SCENARIO_SHARED), default=SCENARIO_AS_IS)
    parser.add_argument("--dry-run", action="store_true", help="with --apply, list the removals and additions only")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Compute the edges, write the report, and replace the Epic-to-Epic edges when asked.

    Returns:
        The exit status.

    """
    args = _arguments(argv)
    matrix: Matrix = read_matrix(matrix_path(args.matrix, os.environ))
    beads: list[beadgraph.Bead] | None = _epic_beads(args.repo) if args.apply or args.report is not None else None
    standing: tuple[StandingEdge, ...] | None = None if beads is None else standing_edges(beads)
    analysis: Analysis = analyse(matrix, args.expect, standing)
    if args.report is not None:
        from epicorderreport import render  # ruff: ignore[import-outside-top-level] - the report module is needed only for --report.

        args.report.write_text(render(analysis), encoding="utf-8")
    out: JsonObject = summary(analysis)
    if args.apply and beads is not None and standing is not None:
        name: str = "A" if args.scenario == SCENARIO_AS_IS else "B"
        chosen: Order = next(result for result in analysis.orders if result.name == name)
        writer = beadgraph.Writer(args.repo, dry_run=args.dry_run)
        out["apply"] = replace_edges(chosen, standing, {bead.id for bead in beads}, writer)
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
