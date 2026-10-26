#!/usr/bin/env python3
"""Compute every Epic-to-Epic edge from the judgments the matrix records, and replace the edges in beads with them.

The owner runs it once, for the whole portfolio, before ``keeper.py`` runs. The Epics and
everything that decides the edges are read from the matrix only. No model is called, no agent or
workflow is started, and no edge is inferred from counts or names: each comes from a judgment
recorded in the matrix (``matrixshared``).

An Epic has requirements; requirements are served by features; features are realized by
architecture entries, which depend on other entries. No Epic relates directly to another Epic.
An item is shared when two or more Epics need it: a feature that serves a requirement of each,
or an architecture entry each reaches by the rule of reach. Edges exist so that an Epic waits for
the Epic that builds and owns something it uses, and so that two Epics never work on the same
unapproved shared item at the same time.

1. For each shared item whose architecture is not approved, the record that decides it: an
   architecture-side ``drives`` from Epic F to the item, with ``basis`` ``owns`` (F builds and
   owns it; the others use it) or ``shared`` (the Epics share it independently; F merely goes
   first); else the owner's ``drives`` with no basis from F to the stack the item is realized or
   homed in (F owns it).
2. Every other Epic that needs the item waits for F: one edge from F to each. The edges several
   items make between one pair are one edge.
3. An item no record decides makes no edge and is listed as unjudged. An item realized or homed
   in a stack that says ``epicDriver: none`` makes no edge (the stack is deployed in advance).
4. While the edges hold a loop, one edge inside a loop is dropped: first an edge that only
   ``shared`` items made, then one that an ``owns`` item made, each time the one made by the
   fewest items, a tie to the lower bead ids; every dropped edge is reported with its items. The
   rest is transitively reduced.

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
from matrix_contract import KIND_EPIC, EntryId
from matrixshared import BASIS_SHARED, SOURCE_JUDGED, SharedItem, shared_items
from matrixstore import Matrix, matrix_path, read_matrix

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from contracts import JsonObject, JsonValue

type Pair = tuple[str, str]
"""An edge: the Epic that goes first, then the Epic that waits for it."""

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
class Dropped:
    """One edge the loop break dropped, with the items that made it."""

    pair: Pair
    items: tuple[EntryId, ...]
    shared_only: bool
    """Whether only items judged ``shared`` made it."""


@dataclass(frozen=True, slots=True)
class Order:
    """The result: the edges before and after reduction, the dropped edges, levels and the longest chain."""

    raw: Mapping[Pair, tuple[EntryId, ...]]
    """The edges left after the loop break, before the reduction, each with the items that make it."""
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
    items: Mapping[EntryId, SharedItem]
    """Every item two or more Epics need."""
    order: Order
    standing: tuple[StandingEdge, ...] | None
    """Every dependency edge between two Epics in beads, or None when beads was not read."""
    checks: tuple[Check, ...]


def deciding(items: Iterable[SharedItem]) -> list[SharedItem]:
    """List the unapproved shared items a record decides and no ``epicDriver: none`` stack holds.

    Returns:
        The items that make edges before the loop break, in the order given.

    """
    return [item for item in items if not item.approved and item.decision is not None and not item.in_advance]


def unjudged(items: Iterable[SharedItem]) -> list[SharedItem]:
    """List the unapproved shared items no record decides, outside every stack deployed in advance.

    Returns:
        The items, in the order given.

    """
    return [item for item in items if not item.approved and item.decision is None and not item.in_advance]


def label(analysis: Analysis, item: EntryId) -> str:
    """Name an item by its matrix name and id.

    Returns:
        ``<name> (<id>)``.

    """
    found: SharedItem | None = analysis.items.get(item)
    return item if found is None else f"{found.name} ({item})"


def raw_edges(decided: Iterable[SharedItem]) -> dict[Pair, tuple[EntryId, ...]]:
    """Draw an edge from each decided item's driver to every other Epic that needs it.

    Returns:
        Each edge with the items that make it, sorted.

    """
    found: dict[Pair, set[EntryId]] = {}
    item: SharedItem
    for item in decided:
        if item.decision is None:
            continue
        driver: str = item.decision.driver
        for waiter in item.needs:
            if waiter != driver:
                found.setdefault((driver, waiter), set()).add(item.id)
    return {pair: tuple(sorted(items)) for pair, items in sorted(found.items())}


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
    items: Mapping[EntryId, SharedItem],
    epics: Collection[str],
) -> tuple[dict[Pair, tuple[EntryId, ...]], tuple[Dropped, ...]]:
    """Drop edges until no loop is left, one edge inside a loop at a time.

    First an edge that only items judged ``shared`` made, then an edge an ``owns`` item made
    (the owner's decision for a stack counts as ``owns``); within each, the edge made by the
    fewest items, a tie to the lower bead id of the Epic that goes first, then of the Epic that
    waits. The loops are found again after each drop.

    Returns:
        The edges left, and the dropped edges in the order they were dropped.

    """
    kept: dict[Pair, tuple[EntryId, ...]] = dict(raw)

    def shared_only(pair: Pair) -> bool:
        return all(
            (decision := items[item].decision) is not None and decision.basis == BASIS_SHARED for item in kept[pair]
        )

    dropped: list[Dropped] = []
    inside: list[Pair] = _inside_cycles(epics, kept)
    while inside:
        weakest: Pair = min(inside, key=lambda pair: (not shared_only(pair), len(kept[pair]), pair))
        only: bool = shared_only(weakest)
        dropped.append(Dropped(weakest, kept.pop(weakest), only))
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


def order(items: Mapping[EntryId, SharedItem], decided: Iterable[SharedItem], epics: Collection[str]) -> Order:
    """Compute the edges, the loop break, the reduction, levels and the longest chain.

    Returns:
        The result.

    """
    raw, dropped = break_cycles(raw_edges(decided), items, epics)
    redundant: set[Pair] = _redundant(raw)
    edges: dict[Pair, tuple[EntryId, ...]] = {pair: f for pair, f in raw.items() if pair not in redundant}
    depth, _ = _depths(epics, raw)
    successors: dict[str, list[str]] = _successors(raw)
    unlocks: dict[str, int] = {bead: len(_descendants(successors, bead)) for bead in epics}
    return Order(raw, dropped, edges, {bead: depth[bead] for bead in epics}, unlocks, _chain(epics, raw))


def check(result: Order, waiter: str, driver: str) -> Check:
    """Tell whether ``waiter`` waits for ``driver``, directly or through other Epics.

    Returns:
        The spot-check, with the path of Epics (empty: it does not wait) and the items that make the direct edge.

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
        matrix: The matrix, the one source of the Epics, the shared items and the judgments.
        expected: The spot-checks to answer, each (waiter, driver).
        standing: The Epic-to-Epic edges in beads, or None when beads was not read.

    Returns:
        Everything the report shows.

    """
    epics: dict[str, Epic] = read_epics(matrix)
    items: dict[EntryId, SharedItem] = {item.id: item for item in shared_items(matrix)}
    result: Order = order(items, deciding(items.values()), epics)
    checks: tuple[Check, ...] = tuple(check(result, waiter, driver) for waiter, driver in expected)
    return Analysis(epics, items, result, standing, checks)


def _dropped_json(dropped: Iterable[Dropped]) -> list[JsonValue]:
    return [
        {"driver": d.pair[0], "waiter": d.pair[1], "sharedOnly": d.shared_only, "items": list(d.items)} for d in dropped
    ]


def edges_made(analysis: Analysis) -> dict[EntryId, int]:
    """Count the edges each item makes after the loop break, before the reduction.

    Returns:
        Each item that makes an edge with its count.

    """
    made: dict[EntryId, int] = {}
    for item in (f for items in analysis.order.raw.values() for f in items):
        made[item] = made.get(item, 0) + 1
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
    decided: list[SharedItem] = deciding(analysis.items.values())
    unapproved: list[SharedItem] = [item for item in analysis.items.values() if not item.approved]
    judged: int = sum(1 for item in decided if item.decision is not None and item.decision.source == SOURCE_JUDGED)
    top_items: list[JsonValue] = []
    for item_id in top[:10]:
        decision = analysis.items[item_id].decision
        top_items.append({
            "item": item_id,
            "edges": made[item_id],
            "driver": None if decision is None else decision.driver,
            "basis": None if decision is None else decision.basis,
        })
    return {
        "epics": len(analysis.epics),
        "sharedItems": len(analysis.items),
        "approved": len(analysis.items) - len(unapproved),
        "judged": judged,
        "ownerStack": len(decided) - judged,
        "deployedInAdvance": sum(1 for item in unapproved if item.in_advance),
        "unjudged": len(unjudged(analysis.items.values())),
        "itemsMakingEdges": len(made),
        "edges": len(result.edges),
        "edgesBeforeReduction": len(result.raw),
        "startNow": sizes[0],
        "levels": len(sizes),
        "maxConcurrency": max(sizes),
        "longestChain": len(result.chain),
        "topItems": top_items,
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
