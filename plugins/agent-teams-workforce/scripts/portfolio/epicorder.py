#!/usr/bin/env python3
"""Compute every Epic-to-Epic dependency edge from the matrix alone, and replace the edges in beads with them.

The owner runs it once, for the whole portfolio, before ``keeper.py`` runs. The Epics and
everything that decides the edges are read from the matrix only. No model is called, no agent or
workflow is started and no ordering is assumed: neither WSJF nor any rank enters the edges. The
unit that orders Epics is the feature: no two Epics are elaborated at once on the unapproved
architecture of a feature they both need.

1. The Epics that need a feature are the Epics with a requirement ``servedBy`` it (Epic,
   ``hasRequirement``, requirement, ``servedBy``, feature).
2. A feature's architecture is approved when the feature is ``realizedBy`` at least one
   architecture-side entry and every architecture-side entry it is ``realizedBy`` carries the
   ``approved`` mark. A feature realized by nothing is not approved.
3. A feature needed by two or more Epics whose architecture is not approved makes edges. An
   approved feature makes none, and a feature needed by one Epic makes none.
4. The feature's driver is the Epic with the most of its requirements ``servedBy`` the feature, a
   tie to the lower bead id. The owner's decisions recorded in the matrix come first: an
   architecture-side ``drives`` relationship from an Epic to a stack makes that Epic the driver of
   every feature whose realizers are all in that stack, and the stack attribute
   ``epicDriver: none`` says that no feature whose realizers are all in that stack makes an edge
   (the stack is deployed in advance). Two named drivers, or a named driver beside ``none``, is
   refused.
5. The driver precedes every other Epic that needs the feature: one edge from the driver to each.
   The edges several features make between one pair are one edge.
6. While the edges hold a cycle, the edge inside a cycle whose driver has the fewest requirements
   served by the feature that made it is dropped (a tie to the lower bead id of the driver, then
   of the waiting Epic), and every dropped edge is reported. The rest is transitively reduced.

``--report`` writes the Markdown report (``epicorderreport.py``), with ``--expect
<waiter>:<driver>`` spot-checks; stdout carries one JSON summary. ``--apply`` makes the
Epic-to-Epic dependency edges in beads exactly the computed edges: it removes every standing
``tracks`` and ``blocks`` edge between two Epics, whoever made it, and writes each computed edge
as a ``tracks`` edge. It writes nothing else: no Task, Story, WSJF value or record. It refuses,
writing nothing, edges that name an Epic beads does not hold. Beads is read only to list the
standing Epic-to-Epic edges (``--apply``, and the report's comparison with them).
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
    REL_DRIVES,
    REL_HAS_REQUIREMENT,
    REL_REALIZED_BY,
    REL_SERVED_BY,
    EntryId,
)
from matrixstore import ATTR_EPIC_DRIVER, Matrix, kind_of, matrix_path, read_matrix
from matrixtraverse import authority_holder, epic_id

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from contracts import JsonObject, JsonValue

type Pair = tuple[str, str]
"""An edge: the driver, elaborated first, then the Epic that waits for it."""

DRIVER_NONE: Final = "none"
"""The ``epicDriver`` value by which the owner says no Epic drives a stack."""
TITLE_PREFIX: Final = "Feature PRD: "
RULE_OWNER_NAMED: Final = "owner named the driver of its stack"
RULE_OWNER_NONE: Final = "owner: no Epic drives its stack"
RULE_MOST: Final = "most requirements served"
RULE_TIE: Final = "tie for most requirements served: lower bead id"
EPIC_EDGE_TYPES: Final = (beadgraph.TRACKS, beadgraph.BLOCKS)
"""The dependency types the pipeline reads as an Epic's prerequisites; ``--apply`` removes both between Epics."""
MIN_SHARED: Final = 2
"""The number of Epics that must need a feature before it can order them."""
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
class Feature:
    """One feature two or more Epics need: who needs it, what realizes it, its approval and its driver."""

    id: EntryId
    label: str
    needs: Mapping[str, int]
    """Each Epic that needs the feature with its number of requirements ``servedBy`` it."""
    realizers: tuple[EntryId, ...]
    """The architecture-side entries the feature is ``realizedBy``."""
    approved: bool
    driver: str | None
    rule: str
    """How the driver was decided: one of the ``RULE_*`` texts."""


@dataclass(frozen=True, slots=True)
class Decision:
    """One feature that makes edges: its driver, the driver's requirement count and the Epics that wait."""

    feature: EntryId
    label: str
    driver: str
    requirements: int
    """The number of the driver's requirements ``servedBy`` the feature."""
    users: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Dropped:
    """One edge the cycle break dropped, with the features that made it and the driver's requirement count."""

    pair: Pair
    features: tuple[EntryId, ...]
    requirements: int


@dataclass(frozen=True, slots=True)
class Order:
    """The result: the edges before and after reduction, the dropped edges, levels and the longest chain."""

    raw: Mapping[Pair, tuple[EntryId, ...]]
    """The edges left after the cycle break, before the reduction, each with the features that make it."""
    dropped: tuple[Dropped, ...]
    edges: Mapping[Pair, tuple[EntryId, ...]]
    levels: Mapping[str, int]
    unlocks: Mapping[str, int]
    chain: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Check:
    """One spot-check: whether ``waiter`` waits for ``driver``, and through which Epics."""

    waiter: str
    driver: str
    path: tuple[str, ...]
    direct: tuple[EntryId, ...]


@dataclass(frozen=True, slots=True)
class Analysis:
    """Everything the report shows."""

    epics: Mapping[str, Epic]
    needed: int
    """The number of features at least one Epic needs."""
    features: Mapping[EntryId, Feature]
    """Every feature two or more Epics need."""
    decisions: Mapping[EntryId, Decision]
    order: Order
    standing: tuple[StandingEdge, ...] | None
    """Every dependency edge between two Epics in beads, or None when beads was not read."""
    checks: tuple[Check, ...]


def _label(matrix: Matrix, entry_id: EntryId) -> str:
    entry = matrix.find(entry_id)
    return entry_id if entry is None else f"{entry.name} ({entry_id})"


def needs(matrix: Matrix, epics: Collection[str]) -> dict[EntryId, dict[str, int]]:
    """Count, for every feature, each Epic's requirements ``servedBy`` it.

    Returns:
        Each feature some Epic needs, in id order, with each Epic and its requirement count.

    """
    served: dict[EntryId, dict[str, set[EntryId]]] = {}
    found: Iterable[tuple[EntryId, str, EntryId]] = (
        (serving.end, bead, stated.end)
        for bead in sorted(epics)
        for stated in matrix.outgoing(epic_id(bead), (REL_HAS_REQUIREMENT,))
        for serving in matrix.outgoing(stated.end, (REL_SERVED_BY,))
    )
    for feature, bead, requirement in found:
        served.setdefault(feature, {}).setdefault(bead, set()).add(requirement)
    return {feature: {bead: len(r) for bead, r in by.items()} for feature, by in sorted(served.items())}


def realizers(matrix: Matrix, feature: EntryId) -> tuple[EntryId, ...]:
    """Name the architecture-side entries a feature is ``realizedBy`` on the architecture side.

    Returns:
        The entries, in id order.

    """
    return tuple(
        sorted({
            realizing.end
            for realizing in matrix.outgoing(feature, (REL_REALIZED_BY,))
            if realizing.side == AUTHORITY_SIDE and matrix.entry(realizing.end).side == AUTHORITY_SIDE
        }),
    )


def is_approved(matrix: Matrix, realized: Collection[EntryId]) -> bool:
    """Tell whether a feature's architecture is approved: it has realizers and each carries the mark.

    Returns:
        True when there is at least one realizer and every one is approved.

    """
    return bool(realized) and all(matrix.entry(entry_id).approved for entry_id in realized)


def owner_decision(matrix: Matrix, stack: EntryId) -> tuple[str | None, bool]:
    """Read the owner's driver decision for a stack from the matrix.

    Returns:
        The Epic an architecture-side ``drives`` relationship to the stack names (else None), and
        whether the stack says ``epicDriver: none``.

    Raises:
        ValueError: The matrix names two driving Epics, or a driving Epic beside ``none``.

    """
    named: list[str] = sorted({
        relationship.start.removeprefix(f"{KIND_EPIC}:")
        for relationship in matrix.incoming(stack, (REL_DRIVES,))
        if relationship.side == AUTHORITY_SIDE and kind_of(relationship.start) == KIND_EPIC
    })
    entry = matrix.find(stack)
    none: bool = entry is not None and entry.attributes.get(ATTR_EPIC_DRIVER) == DRIVER_NONE
    if len(named) > 1 or (named and none):
        message: str = f"the matrix holds conflicting driver decisions for {stack}: {', '.join(named)}"
        raise ValueError(message + (f" and {ATTR_EPIC_DRIVER}: {DRIVER_NONE}" if none else ""))
    return (named[0] if named else None), none


def realizing_stack(matrix: Matrix, realized: Collection[EntryId]) -> EntryId | None:
    """Name the one stack every realizer of a feature is in (the stack itself, or its home).

    Returns:
        The stack, or None when the feature has no realizer or its realizers are not all in one stack.

    """
    stacks: set[EntryId | None] = {authority_holder(matrix, entry_id) for entry_id in realized}
    only: EntryId | None = next(iter(stacks)) if len(stacks) == 1 else None
    return only


def driver_of(matrix: Matrix, realized: Collection[EntryId], counts: Mapping[str, int]) -> tuple[str | None, str]:
    """Decide a feature's driver and how it was decided.

    Returns:
        The driver (None: the owner said no Epic drives the stack its realizers are in) and the
        ``RULE_*`` text.

    """
    stack: EntryId | None = realizing_stack(matrix, realized)
    named, none = owner_decision(matrix, stack) if stack is not None else (None, False)
    if none:
        return None, RULE_OWNER_NONE
    if named is not None:
        return named, RULE_OWNER_NAMED
    ranked: list[tuple[str, int]] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    tied: bool = len(ranked) > 1 and ranked[0][1] == ranked[1][1]
    return ranked[0][0], (RULE_TIE if tied else RULE_MOST)


def shared_features(matrix: Matrix, needed: Mapping[EntryId, Mapping[str, int]]) -> dict[EntryId, Feature]:
    """Describe every feature two or more Epics need: realizers, approval and driver.

    Returns:
        Each such feature, in id order.

    """
    described: dict[EntryId, Feature] = {}
    for feature, counts in needed.items():
        if len(counts) < MIN_SHARED:
            continue
        realized: tuple[EntryId, ...] = realizers(matrix, feature)
        driver, rule = driver_of(matrix, realized, counts)
        described[feature] = Feature(
            feature,
            _label(matrix, feature),
            counts,
            realized,
            is_approved(matrix, realized),
            driver,
            rule,
        )
    return described


def decide(described: Mapping[EntryId, Feature]) -> dict[EntryId, Decision]:
    """Name the driver and the waiting Epics of every unapproved shared feature with a driver.

    Returns:
        Each feature's decision, in feature order.

    """
    return {
        feature.id: Decision(
            feature.id,
            feature.label,
            feature.driver,
            feature.needs.get(feature.driver, 0),
            tuple(sorted(bead for bead in feature.needs if bead != feature.driver)),
        )
        for feature in described.values()
        if feature.driver is not None and not feature.approved
    }


def raw_edges(decisions: Iterable[Decision]) -> dict[Pair, tuple[EntryId, ...]]:
    """Draw driver -> user for every user of every decision, each pair with its features.

    Returns:
        Each edge with the features that make it, sorted.

    """
    found: dict[Pair, set[EntryId]] = {}
    pairs: Iterable[tuple[Pair, EntryId]] = (
        ((decision.driver, user), decision.feature) for decision in decisions for user in decision.users
    )
    for pair, feature in pairs:
        found.setdefault(pair, set()).add(feature)
    return {pair: tuple(sorted(features)) for pair, features in sorted(found.items())}


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


def _inside_cycles(epics: Collection[str], edges: Collection[Pair]) -> list[Pair]:
    """List the edges that lie inside a cycle: their far end reaches back to their start.

    Returns:
        The edges, in the order given.

    """
    successors: dict[str, list[str]] = _successors(edges)
    reach: dict[str, set[str]] = {node: _descendants(successors, node) for node in epics}
    return [(a, b) for a, b in edges if a in reach.get(b, set())]


def break_cycles(
    raw: Mapping[Pair, tuple[EntryId, ...]],
    decisions: Mapping[EntryId, Decision],
    epics: Collection[str],
) -> tuple[dict[Pair, tuple[EntryId, ...]], tuple[Dropped, ...]]:
    """Drop edges until no cycle is left, the weakest edge inside a cycle first.

    An edge's weight is the most requirements its driver has served by any feature that makes it.
    The edge inside a cycle with the least weight is dropped, a tie to the lower driver bead id,
    then the lower waiting bead id, and the cycles are found again.

    Returns:
        The edges left, and the dropped edges in the order they were dropped.

    """
    kept: dict[Pair, tuple[EntryId, ...]] = dict(raw)
    weight: dict[Pair, int] = {pair: max(decisions[f].requirements for f in features) for pair, features in raw.items()}
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


def _chain(epics: Collection[str], between: Collection[Pair]) -> tuple[str, ...]:
    depth, predecessors = _depths(epics, between)
    head: str = min(depth, key=lambda h: (-depth[h], h))
    chain: list[str] = [head]
    while predecessors.get(head):
        head = min(p for p in predecessors[head] if depth[p] == depth[head] - 1)
        chain.append(head)
    return tuple(reversed(chain))


def order(decisions: Mapping[EntryId, Decision], epics: Collection[str]) -> Order:
    """Compute the edges, the cycle break, the reduction, levels and the longest chain.

    Returns:
        The result.

    """
    raw, dropped = break_cycles(raw_edges(decisions.values()), decisions, epics)
    redundant: set[Pair] = _redundant(raw)
    edges: dict[Pair, tuple[EntryId, ...]] = {pair: f for pair, f in raw.items() if pair not in redundant}
    depth, _ = _depths(epics, raw)
    successors: dict[str, list[str]] = _successors(raw)
    unlocks: dict[str, int] = {bead: len(_descendants(successors, bead)) for bead in epics}
    return Order(raw, dropped, edges, {bead: depth[bead] for bead in epics}, unlocks, _chain(epics, raw))


def check(result: Order, waiter: str, driver: str) -> Check:
    """Tell whether ``waiter`` waits for ``driver``, directly or through other Epics.

    Returns:
        The spot-check, with the path of Epics (empty: it does not wait) and the direct features.

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
    needed: dict[EntryId, dict[str, int]] = needs(matrix, epics)
    described: dict[EntryId, Feature] = shared_features(matrix, needed)
    decisions: dict[EntryId, Decision] = decide(described)
    result: Order = order(decisions, epics)
    checks: tuple[Check, ...] = tuple(check(result, waiter, driver) for waiter, driver in expected)
    return Analysis(epics, len(needed), described, decisions, result, standing, checks)


def _dropped_json(dropped: Iterable[Dropped]) -> list[JsonValue]:
    return [
        {"driver": d.pair[0], "waiter": d.pair[1], "requirements": d.requirements, "features": list(d.features)}
        for d in dropped
    ]


def edges_made(analysis: Analysis) -> dict[EntryId, int]:
    """Count the edges each feature makes after the cycle break, before the reduction.

    Returns:
        Each feature that makes an edge with its count.

    """
    made: dict[EntryId, int] = {}
    for feature in (f for features in analysis.order.raw.values() for f in features):
        made[feature] = made.get(feature, 0) + 1
    return made


def summary(analysis: Analysis) -> JsonObject:
    """Summarise the result for stdout.

    Returns:
        The summary.

    """
    result: Order = analysis.order
    sizes: list[int] = [list(result.levels.values()).count(n) for n in range(1, max(result.levels.values()) + 1)]
    made: dict[EntryId, int] = edges_made(analysis)
    top: list[EntryId] = sorted(made, key=lambda f: (-made[f], f))
    return {
        "epics": len(analysis.epics),
        "featuresNeeded": analysis.needed,
        "sharedFeatures": len(analysis.features),
        "featuresWithDriver": len(analysis.decisions),
        "featuresMakingEdges": len(made),
        "edges": len(result.edges),
        "edgesBeforeReduction": len(result.raw),
        "startNow": sizes[0],
        "levels": len(sizes),
        "maxConcurrency": max(sizes),
        "longestChain": len(result.chain),
        "topFeatures": [{"feature": f, "edges": made[f], "driver": analysis.decisions[f].driver} for f in top[:10]],
        "dropped": _dropped_json(result.dropped),
        "checks": [
            {"waiter": c.waiter, "driver": c.driver, "waits": bool(c.path), "path": list(c.path)}
            for c in analysis.checks
        ],
    }


def replace_edges(
    result: Order,
    standing: tuple[StandingEdge, ...],
    in_beads: Collection[str],
    writer: beadgraph.Writer,
) -> JsonObject:
    """Remove every standing Epic-to-Epic edge, then write each computed edge as a ``tracks`` edge.

    Args:
        result: The computed order whose edges become the Epic-to-Epic edges.
        standing: Every Epic-to-Epic edge in beads.
        in_beads: The ids of the Epic beads.
        writer: The tracker writer; a dry-run writer records the writes and makes none.

    Returns:
        The removals and additions, each listed, and why a real run would refuse them (empty: it would not).

    Raises:
        ValueError: Outside a dry run, the edges name an Epic beads does not hold; nothing is written.

    """
    absent: list[str] = sorted({bead for pair in result.edges for bead in pair} - set(in_beads))
    refusal: str = f"the matrix holds Epics beads does not: {', '.join(absent)}; nothing is written" if absent else ""
    if refusal and not writer.dry_run:
        raise ValueError(refusal)
    for edge in standing:
        writer.bd(["dep", "remove", edge.blocked, edge.blocker])
    for blocker, blocked in result.edges:
        writer.bd(["dep", "add", blocked, blocker, "--type", beadgraph.TRACKS])
    return {
        "dryRun": writer.dry_run,
        "refused": refusal,
        "removed": len(standing),
        "added": len(result.edges),
        "dropped": _dropped_json(result.dropped),
        "remove": [{"blocker": e.blocker, "blocked": e.blocked, "type": e.kind} for e in standing],
        "add": [
            {"blocker": blocker, "blocked": blocked, "type": beadgraph.TRACKS} for blocker, blocked in result.edges
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
        help="replace every Epic-to-Epic edge in beads with the computed edges",
    )
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
        writer = beadgraph.Writer(args.repo, dry_run=args.dry_run)
        out["apply"] = replace_edges(analysis.order, standing, {bead.id for bead in beads}, writer)
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
