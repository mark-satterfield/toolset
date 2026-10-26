#!/usr/bin/env python3
"""Compute every Epic-to-Epic dependency edge from the matrix alone, and replace the edges in beads with them.

The owner runs it once, for the whole portfolio, before ``keeper.py`` runs. The Epics and
everything that decides the edges are read from the matrix only. No model is called, no agent or
workflow is started and no ordering is assumed: neither WSJF nor any rank enters the edges. An
edge says that an architecture decision one Epic rests on should be designed from another Epic's
requirements first, and the matrix does not hold that decision approved. The chain is read by
the rule of reach (``matrixtraverse.rule_reach``): Epic, ``hasRequirement``, requirement,
``servedBy``, feature, ``realizedBy``, the entry that realizes it, and the far end of each
dependency one hop from such an entry or its stack.

1. Only shared foundations order Epics. A foundation is a stack whose name starts with
   ``shared-`` or ends with ``-lib`` or ``-infra``, together with every entry homed in it; and a
   layer or a package homed in no such stack, on its own. Product services, components, events
   and app stacks make no Epic edge: who builds them first is build order, settled among Tasks.
2. A foundation whose entry and every architecture-side entry homed in it carry the matrix
   ``approved`` flag is designed, and makes no edge.
3. The owner's driver decisions are read from the matrix: a ``drives`` relationship, on the
   architecture side, from an Epic to the foundation's entry names its driving Epic; the stack
   attribute ``epicDriver: none`` says no Epic drives it. A foundation no Epic drives makes no
   edge: no Epic waits on it. Two named drivers, or a named driver beside ``none``, is refused.
4. Otherwise the driving Epic is the one with strictly the most distinct features serving its
   requirements that are ``realizedBy`` anything in the foundation. A tie for most means no Epic
   drives it, and it makes no edge.
5. Every other Epic that realizes part of the foundation, or reaches one of its entries as the
   far end of a dependency one hop away (``imports``, ``calls``, ``publishes``, ``reads`` and the
   rest of the dependency family), waits for the driver: one edge from the driver to it. Only an
   entry some Epic realizes counts: one no serving feature is ``realizedBy`` (a VPC every Lambda
   runs in) is shaped by no Epic's requirements. The edges several foundations make between one
   pair are one edge.
6. While the edges hold a cycle, the edge inside a cycle whose driver has the fewest features in
   the foundations that make it is dropped (a tie goes to the lower bead id of the driver, then of
   the waiting Epic), and every dropped edge is reported. The rest is transitively reduced.

Two scenarios are computed: as the matrix stands (A), and as if every ``shared-*`` foundation were
approved (B). ``--report`` writes the Markdown report (``epicorderreport.py``), with
``--expect <waiter>:<driver>`` spot-checks; stdout carries one JSON summary. ``--apply`` makes
the Epic-to-Epic dependency edges in beads exactly the chosen scenario's edges: it removes every
standing ``tracks`` and ``blocks`` edge between two Epics, whoever made it, and writes each
computed edge as a ``tracks`` edge. It writes nothing else: no Task, Story, WSJF value or record.
It refuses, writing nothing, a scenario whose edges still close a cycle (every Epic in it would
wait for good) or name an Epic beads does not hold. ``--apply --dry-run`` prints the removals,
the additions and any such refusal, and writes nothing. Beads is read only to list the standing
Epic-to-Epic edges (``--apply``, and the report's comparison with them).
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
from matrix_contract import (
    AUTHORITY_SIDE,
    KIND_EPIC,
    KIND_LAYER,
    KIND_PACKAGE,
    KIND_STACK,
    REL_DRIVES,
    EntryId,
    EntryKind,
)
from matrixstore import Matrix, kind_of, matrix_path, read_matrix
from matrixtraverse import CODE_KINDS, RuleReach, epic_id, rule_reach, stacks_of

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from contracts import JsonObject, JsonValue
    from matrix_contract import Entry

type Unit = str
"""The id of a foundation: its stack, or a layer or package homed in no foundation stack."""
type Pair = tuple[str, str]
"""An edge: the driver, elaborated first, then the Epic that waits for it."""

SHARED_PREFIX: Final = "shared-"
FOUNDATION_SUFFIXES: Final = ("-lib", "-infra")
"""The endings of a foundation stack's name, beside the ``shared-`` prefix."""
LONE_FOUNDATION_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_LAYER, KIND_PACKAGE})
"""The kinds of entry that are a foundation of their own when no foundation stack holds them."""
ATTR_EPIC_DRIVER: Final = "epicDriver"
DRIVER_NONE: Final = "none"
"""The ``epicDriver`` value by which the owner says no Epic drives a stack."""
ATTR_REPOSITORY: Final = "repository"
SCENARIO_AS_IS: Final = "as-is"
SCENARIO_SHARED: Final = "shared-approved"
TITLE_PREFIX: Final = "Feature PRD: "
RULE_OWNER_NAMED: Final = "owner named it"
RULE_OWNER_NONE: Final = "owner: no Epic drives it"
RULE_MOST: Final = "most features"
RULE_TIE: Final = "tie for most features: no Epic drives it"
RULE_UNREALIZED: Final = "no Epic realizes it: no Epic drives it"
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
class Foundation:
    """One foundation: its members, who realizes and touches it, its approval and its driver."""

    unit: Unit
    label: str
    members: tuple[EntryId, ...]
    """The foundation's own entry, then every entry homed in it."""
    features: Mapping[str, int]
    """Each Epic with its number of distinct serving features ``realizedBy`` a member."""
    touching: tuple[str, ...]
    """Every Epic that realizes a member or reaches one as the far end of a dependency, one hop."""
    approved: bool
    driver: str | None
    rule: str
    """How the driver was decided: one of the ``RULE_*`` texts."""
    shared: bool
    """The foundation is a ``shared-*`` stack, which scenario B takes as approved."""


@dataclass(frozen=True, slots=True)
class Decision:
    """One foundation with a driver and users: the driver, its feature count and the Epics that wait for it."""

    unit: Unit
    label: str
    driver: str
    features: int
    """The number of distinct features of the driver that are ``realizedBy`` a member of the foundation."""
    users: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Dropped:
    """One edge the cycle break dropped, with the foundations that made it and the driver's feature count."""

    pair: Pair
    units: tuple[Unit, ...]
    features: int


@dataclass(frozen=True, slots=True)
class Cycle:
    """One strongly connected set of Epics and the edges inside it, each with the units that make it."""

    members: tuple[str, ...]
    edges: Mapping[Pair, tuple[Unit, ...]]


@dataclass(frozen=True, slots=True)
class Order:
    """One scenario's result: its edges before and after reduction, the dropped edges, cycles and levels."""

    name: str
    excluded: int
    raw: Mapping[Pair, tuple[Unit, ...]]
    """The edges left after the cycle break, before the reduction."""
    dropped: tuple[Dropped, ...]
    cycles: tuple[Cycle, ...]
    """The cycles left after the break: none, unless the break failed; ``--apply`` refuses any."""
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
    foundations: Mapping[Unit, Foundation]
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


def is_foundation_stack(stack: EntryId) -> bool:
    """Tell whether a stack is a foundation by its name: ``shared-*``, ``*-lib`` or ``*-infra``.

    Returns:
        True for a foundation stack.

    """
    name: str = stack.removeprefix(f"{KIND_STACK}:")
    return name.startswith(SHARED_PREFIX) or name.endswith(FOUNDATION_SUFFIXES)


def foundation_of(matrix: Matrix, entry: Entry) -> Unit | None:
    """Name the foundation an entry belongs to.

    Returns:
        The entry itself when it is a foundation stack; the foundation stack it is homed in; the
        entry itself when it is a layer or a package homed in no foundation stack; otherwise None.

    """
    if entry.kind == KIND_STACK:
        return entry.id if is_foundation_stack(entry.id) else None
    home: set[EntryId] = {stack for stack in stacks_of(matrix, entry.id) if is_foundation_stack(stack)}
    if home:
        return min(home)
    return entry.id if entry.kind in LONE_FOUNDATION_KINDS else None


def _membership(matrix: Matrix) -> dict[EntryId, Unit]:
    """Map every code entry that belongs to a foundation to that foundation.

    Returns:
        Each member's id with its foundation.

    """
    found: Iterable[tuple[EntryId, Unit | None]] = (
        (entry.id, foundation_of(matrix, entry)) for entry in matrix.entries(CODE_KINDS)
    )
    return {member: unit for member, unit in found if unit is not None}


def _realizing(reaches: Mapping[str, RuleReach], member_of: Mapping[EntryId, Unit]) -> dict[Unit, dict[str, int]]:
    """Count, for every foundation, each Epic's distinct serving features ``realizedBy`` one of its members.

    ``RuleReach.entries`` names one ``realizedBy <feature>`` way per feature that realizes an entry,
    so the distinct ways across the members are the distinct features.

    Returns:
        Each foundation with each realizing Epic and its feature count.

    """
    ways: dict[Unit, dict[str, set[str]]] = {}
    found: Iterable[tuple[Unit, str, frozenset[str]]] = (
        (member_of[entry_id], bead, how)
        for bead, reach in reaches.items()
        for entry_id, how in reach.entries.items()
        if entry_id in member_of
    )
    for unit, bead, how in found:
        ways.setdefault(unit, {}).setdefault(bead, set()).update(how)
    return {unit: {bead: len(how) for bead, how in by_epic.items()} for unit, by_epic in ways.items()}


def _touching(reaches: Mapping[str, RuleReach], member_of: Mapping[EntryId, Unit]) -> dict[Unit, set[str]]:
    """Name, for every foundation, the Epics that realize a member or reach one by a dependency, one hop.

    Only a member some Epic realizes counts: an entry no serving feature is ``realizedBy`` (a VPC
    every Lambda runs in, say) is used by everyone and shaped by no Epic's requirements.

    Returns:
        Each foundation with the Epics that touch it.

    """
    realized: set[EntryId] = {entry_id for reach in reaches.values() for entry_id in reach.entries}
    used: dict[EntryId, Unit] = {entry_id: unit for entry_id, unit in member_of.items() if entry_id in realized}
    touched: dict[Unit, set[str]] = {}
    found: Iterable[tuple[Unit, str]] = (
        (used[entry_id], bead)
        for bead, reach in reaches.items()
        for entry_id in {*reach.entries, *reach.dependencies}
        if entry_id in used
    )
    for unit, bead in found:
        touched.setdefault(unit, set()).add(bead)
    return touched


def most_features(counts: Mapping[str, int]) -> str | None:
    """Name the Epic with strictly the most features, or nobody on a tie for most or no count.

    Returns:
        The driving Epic's bead id, or None.

    """
    ranked: list[tuple[str, int]] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if not ranked or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
        return None
    return ranked[0][0]


def owner_decision(matrix: Matrix, unit: Unit) -> tuple[str | None, bool]:
    """Read the owner's driver decision for a foundation from the matrix.

    Returns:
        The Epic an architecture-side ``drives`` relationship from it names (else None), and whether
        the foundation's entry says ``epicDriver: none``.

    Raises:
        ValueError: The matrix names two driving Epics, or a driving Epic beside ``none``.

    """
    named: list[str] = sorted({
        relationship.start.removeprefix(f"{KIND_EPIC}:")
        for relationship in matrix.incoming(EntryId(unit), (REL_DRIVES,))
        if relationship.side == AUTHORITY_SIDE and kind_of(relationship.start) == KIND_EPIC
    })
    entry = matrix.find(EntryId(unit))
    none: bool = entry is not None and entry.attributes.get(ATTR_EPIC_DRIVER) == DRIVER_NONE
    if len(named) > 1 or (named and none):
        message: str = f"the matrix holds conflicting driver decisions for {unit}: {', '.join(named) or ''}"
        raise ValueError(message + (f" and {ATTR_EPIC_DRIVER}: {DRIVER_NONE}" if none else ""))
    return (named[0] if named else None), none


def _driver(matrix: Matrix, unit: Unit, counts: Mapping[str, int]) -> tuple[str | None, str]:
    """Decide a foundation's driving Epic and how it was decided.

    Returns:
        The driver (None: no Epic drives it) and the ``RULE_*`` text.

    """
    named, none = owner_decision(matrix, unit)
    if none:
        return None, RULE_OWNER_NONE
    if named is not None:
        return named, RULE_OWNER_NAMED
    if not counts:
        return None, RULE_UNREALIZED
    driver: str | None = most_features(counts)
    return driver, (RULE_MOST if driver is not None else RULE_TIE)


def is_approved(matrix: Matrix, members: Iterable[EntryId]) -> bool:
    """Tell whether a foundation is approved: every architecture-side member carries the ``approved`` mark.

    The members are the foundation's own entry and the entries homed in it; repository-side
    entries are hints that are never approved and are left out.

    Returns:
        True when there is at least one architecture-side member and each carries the mark.

    """
    held: list[Entry] = [entry for entry in (matrix.find(member) for member in members) if entry is not None]
    stated: list[Entry] = [entry for entry in held if entry.side == AUTHORITY_SIDE]
    return bool(stated) and all(entry.approved for entry in stated)


def is_shared(matrix: Matrix, unit: Unit) -> bool:
    """Tell whether a foundation is a ``shared-*`` stack, by its name or its repository.

    Returns:
        True for a shared stack.

    """
    entry = matrix.find(EntryId(unit))
    if entry is None or entry.kind != KIND_STACK:
        return False
    repository: object = entry.attributes.get(ATTR_REPOSITORY)
    return unit.startswith(f"{KIND_STACK}:{SHARED_PREFIX}") or (
        isinstance(repository, str) and repository.startswith(SHARED_PREFIX)
    )


def foundations(matrix: Matrix, epics: Collection[str]) -> dict[Unit, Foundation]:
    """Describe every foundation some Epic touches: members, feature counts, approval and driver.

    Returns:
        Each foundation, in unit order.

    """
    reaches: dict[str, RuleReach] = _reaches(matrix, epics)
    member_of: dict[EntryId, Unit] = _membership(matrix)
    realized: dict[Unit, dict[str, int]] = _realizing(reaches, member_of)
    touched: dict[Unit, set[str]] = _touching(reaches, member_of)
    members: dict[Unit, list[EntryId]] = {}
    for member, unit in sorted(member_of.items(), key=lambda item: (item[0] != item[1], item[0])):
        members.setdefault(unit, []).append(member)
    described: dict[Unit, Foundation] = {}
    for unit in sorted(touched):
        driver, rule = _driver(matrix, unit, realized.get(unit, {}))
        described[unit] = Foundation(
            unit=unit,
            label=_label(matrix, unit),
            members=tuple(members[unit]),
            features=realized.get(unit, {}),
            touching=tuple(sorted(touched[unit])),
            approved=is_approved(matrix, members[unit]),
            driver=driver,
            rule=rule,
            shared=is_shared(matrix, unit),
        )
    return described


def decide(described: Mapping[Unit, Foundation]) -> dict[Unit, Decision]:
    """Name the driver and the users of every foundation that has both.

    Returns:
        Each unit's decision, in unit order.

    """
    found: Iterable[tuple[Foundation, str, tuple[str, ...]]] = (
        (foundation, foundation.driver, tuple(bead for bead in foundation.touching if bead != foundation.driver))
        for foundation in described.values()
        if foundation.driver is not None
    )
    return {
        foundation.unit: Decision(
            foundation.unit,
            foundation.label,
            driver,
            foundation.features.get(driver, 0),
            users,
        )
        for foundation, driver, users in found
        if users
    }


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


def _inside_cycles(epics: Collection[str], edges: Collection[Pair]) -> list[Pair]:
    group: dict[str, tuple[str, ...]] = groups(epics, edges)
    return [(a, b) for a, b in edges if len(group[a]) > 1 and group[a] == group[b]]


def break_cycles(
    raw: Mapping[Pair, tuple[Unit, ...]],
    decisions: Mapping[Unit, Decision],
    epics: Collection[str],
) -> tuple[dict[Pair, tuple[Unit, ...]], tuple[Dropped, ...]]:
    """Drop edges until no cycle is left, the weakest edge inside a cycle first.

    An edge's weight is the most features its driver has in any foundation that makes it. The
    edge inside a cycle with the least weight is dropped, a tie to the lower driver bead id, then
    the lower waiting bead id, and the cycles are found again.

    Returns:
        The edges left, and the dropped edges in the order they were dropped.

    """
    kept: dict[Pair, tuple[Unit, ...]] = dict(raw)
    weight: dict[Pair, int] = {pair: max(decisions[unit].features for unit in units) for pair, units in raw.items()}
    dropped: list[Dropped] = []
    inside: list[Pair] = _inside_cycles(epics, kept)
    while inside:
        weakest: Pair = min(inside, key=lambda pair: (weight[pair], pair))
        dropped.append(Dropped(weakest, kept.pop(weakest), weight[weakest]))
        inside = _inside_cycles(epics, kept)
    return kept, tuple(dropped)


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


def order(name: str, decisions: Mapping[Unit, Decision], excluded: Collection[Unit], epics: Collection[str]) -> Order:
    """Compute one scenario: its edges, the cycle break, the reduction, levels and the longest chain.

    A cycle the break leaves (none, unless it failed) is taken as one node, named by its first
    member, for the reduction and the levels.

    Returns:
        The scenario's result.

    """
    kept: list[Decision] = [d for d in decisions.values() if d.unit not in excluded]
    raw, dropped = break_cycles(raw_edges(kept), decisions, epics)
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
    excluded_count: int = len(decisions) - len(kept)
    return Order(name, excluded_count, raw, dropped, cycles, edges, levels, unlocks, _chain(group, between))


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
    described: dict[Unit, Foundation] = foundations(matrix, epics)
    decisions: dict[Unit, Decision] = decide(described)
    approved: set[Unit] = {unit for unit in decisions if described[unit].approved}
    shared: set[Unit] = {unit for unit in decisions if described[unit].shared}
    orders: tuple[Order, ...] = (
        order("A", decisions, approved, epics),
        order("B", decisions, approved | shared, epics),
    )
    pairs: list[Pair] = list(expected)
    checks: dict[str, tuple[Check, ...]] = {
        result.name: tuple(check(result, waiter, driver) for waiter, driver in pairs) for result in orders
    }
    return Analysis(epics, described, decisions, orders, standing, checks)


def _dropped_json(dropped: Iterable[Dropped]) -> list[JsonValue]:
    return [
        {"driver": d.pair[0], "waiter": d.pair[1], "features": d.features, "foundations": list(d.units)}
        for d in dropped
    ]


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
            "edgesBeforeReduction": len(result.raw),
            "startNow": sizes[0],
            "levels": len(sizes),
            "maxConcurrency": max(sizes),
            "longestChain": sum(len(step) for step in result.chain),
            "dropped": _dropped_json(result.dropped),
            "cycles": [list(cycle.members) for cycle in result.cycles],
            "checks": [
                {"waiter": c.waiter, "driver": c.driver, "waits": bool(c.path), "path": list(c.path)}
                for c in analysis.checks[result.name]
            ],
        })
    return {
        "epics": len(analysis.epics),
        "foundations": len(analysis.foundations),
        "units": len(analysis.decisions),
        "scenarios": scenarios,
    }


def _refusal(chosen: Order, in_beads: Collection[str]) -> str:
    """Say why the scenario's edges cannot be written, or nothing when they can.

    A cycle the break left would hold every Epic in it out of elaboration for good, and an edge
    onto an Epic beads does not hold cannot be written.

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
        "dropped": _dropped_json(chosen.dropped),
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
