#!/usr/bin/env python3
"""The Epic edge set: parse it, prove it, and apply the DIFF against what the tracker holds.

An edge means `blocker` must be elaborated before `blocked`, and both ends are Epics. It is
stored as a beads `tracks` edge on the blocked Epic, written `bd dep add <blocked> <blocker>
--type tracks`. `tracks` is non-blocking, so the edge orders elaboration and never removes
the Epic, or any Story or Task beneath it, from `bd ready`. The reasoning pass proposes
edges; nothing here judges whether one is right. What it does judge is whether the set is
APPLICABLE — Epic to Epic, acyclic, over beads that exist, no self-edge, nothing pointed at
a closed item — because a wrong edge set applied is expensive to unpick.

The diff never removes an edge this system did not create. Ownership is recorded on the
BLOCKED bead as `seq_owned_blockers`, so an edge drawn by hand survives every pass,
and re-running a pass with an unchanged proposal writes nothing at all.

An owned edge stored as any type other than `tracks` is CONVERTED: `bd dep remove`, then
`bd dep add --type tracks`. Beads holds one edge per pair of beads and refuses to add a
second type onto an existing one, so the removal has to come first. The edge stays recorded
as owned throughout, so a conversion interrupted between its two writes leaves an owned
edge that is absent, and the next pass over the same proposal adds it.

A proposal has one of two scopes.

* The WHOLE PORTFOLIO: the proposal is every edge, so an owned edge it does not contain is
  withdrawn, and every open Epic records the content fingerprint the sequencer read it at.
* ONE EPIC: the proposal is every edge to or from that Epic and nothing else. An edge that
  does not touch the Epic is refused, only edges touching it are added, converted or
  withdrawn, and only that Epic records its fingerprint. Acyclicity is checked over the
  proposal together with every Epic edge that does not touch the Epic.

The fingerprint is recorded as `seq_content_hash`; an Epic whose fingerprint no longer
matches is one the sequencer has not assessed as it now stands.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import beadgraph
from beadgraph import join_ids, now_iso

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Graph, Writer


#: Metadata key on an Epic: the content fingerprint the sequencer last read it at.
SEEN_KEY = "seq_content_hash"


class SequencingError(RuntimeError):
    """The command cannot proceed and the caller must fix its input."""


@dataclass(frozen=True)
class Edge:
    """A proposed Epic edge: `blocker` must be elaborated before `blocked`."""

    blocker: str
    blocked: str
    reason: str = ""
    confidence: str = ""


#: The dependency type every Epic edge is stored as.
EDGE_TYPE = beadgraph.TRACKS


# ------------------------------------------------------------------------------------
# Input
# ------------------------------------------------------------------------------------


def read_edges(path: Path) -> list[Edge]:
    """Parse an edge file: `{"edges": [{"from", "to", "reason", "confidence"}]}`."""
    raw = json.loads(
        sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    )
    entries = raw.get("edges", []) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        msg = "the edge file must be a list, or an object carrying an `edges` list"
        raise SequencingError(msg)
    edges: list[Edge] = []
    for entry in entries:
        blocker = str(entry.get("from") or entry.get("blocker") or "").strip()
        blocked = str(entry.get("to") or entry.get("blocked") or "").strip()
        if not blocker or not blocked:
            msg = f"edge {entry!r} names no `from`/`to` pair"
            raise SequencingError(msg)
        edges.append(
            Edge(
                blocker=blocker,
                blocked=blocked,
                reason=str(entry.get("reason") or ""),
                confidence=str(entry.get("confidence") or ""),
            )
        )
    return edges


def owned_edges(graph: Graph) -> list[Edge]:
    """Every edge this system recorded as its own, as a proposal.

    Proposing the owned set back withdraws nothing, adds any owned edge that is absent,
    and converts any owned edge stored as the wrong type. Because it is read from the
    ownership records rather than from the edges present, rerunning it after an
    interrupted pass still names every edge that pass was converting.

    Args:
        graph: The tracker graph.

    Returns:
        One edge per owned blocker on every bead, in id order.
    """
    return [
        Edge(blocker=blocker, blocked=bead.id, reason="owned edge")
        for _, bead in sorted(graph.beads.items())
        for blocker in bead.owned_blockers
    ]


# ------------------------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------------------------


def find_cycle(edges: list[Edge]) -> list[str]:
    """Return one cycle as an id path, or an empty list when the edge set is acyclic."""
    successors: dict[str, list[str]] = {}
    for edge in edges:
        successors.setdefault(edge.blocker, []).append(edge.blocked)
    colour: dict[str, int] = {}
    path: list[str] = []

    def walk(node: str) -> list[str]:
        colour[node] = 1
        path.append(node)
        for nxt in successors.get(node, []):
            if colour.get(nxt) == 1:
                return path[path.index(nxt) :] + [nxt]
            if colour.get(nxt, 0) == 0:
                found = walk(nxt)
                if found:
                    return found
        path.pop()
        colour[node] = 2
        return []

    for node in list(successors):
        if colour.get(node, 0) == 0:
            found = walk(node)
            if found:
                return found
    return []


def _standing_epic_edges(graph: Graph, epic: str) -> list[Edge]:
    """Every Epic-to-Epic edge the tracker holds that does not touch one Epic.

    Args:
        graph: The tracker graph.
        epic: The Epic whose own edges are left out.

    Returns:
        The edges, whatever type each is stored as.
    """
    return [
        Edge(blocker=upstream, blocked=bead.id)
        for bead in graph.of_kind("epic")
        for upstream in sorted(set(bead.tracked) | set(bead.blockers))
        if epic not in (upstream, bead.id)
        and upstream in graph.beads
        and graph.beads[upstream].kind == "epic"
    ]


def validate(graph: Graph, edges: list[Edge], epic: str | None = None) -> dict:
    """Report every defect in a proposed edge set.

    The defects are: an edge that is not Epic to Epic, a cycle, a dangling id, a
    self-edge, an edge onto a closed bead, and — when the proposal is scoped to one Epic —
    an edge that does not touch that Epic, or a scope that is not an open Epic.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set.
        epic: The one Epic the proposal is scoped to, or None for the whole portfolio.

    Returns:
        The verdict and every defect found.
    """
    dangling = sorted(
        {e.blocker for e in edges if e.blocker not in graph.beads}
        | {e.blocked for e in edges if e.blocked not in graph.beads}
    )
    self_edges = sorted({e.blocker for e in edges if e.blocker == e.blocked})
    not_epic = sorted(
        {
            f"{e.blocker}->{e.blocked}"
            for e in edges
            if any(
                end in graph.beads and graph.beads[end].kind != "epic"
                for end in (e.blocker, e.blocked)
            )
        }
    )
    onto_closed = sorted(
        {
            f"{e.blocker}->{e.blocked}"
            for e in edges
            if e.blocked in graph.beads and graph.beads[e.blocked].closed
        }
    )
    from_closed = sorted(
        {
            f"{e.blocker}->{e.blocked}"
            for e in edges
            if e.blocker in graph.beads and graph.beads[e.blocker].closed
        }
    )
    outside: list[str] = []
    bad_scope = ""
    if epic is None:
        cycle = find_cycle(edges)
    else:
        scope = graph.beads.get(epic)
        if scope is None or scope.kind != "epic" or scope.closed:
            bad_scope = f"{epic} is not an open Epic"
        outside = sorted(
            {
                f"{e.blocker}->{e.blocked}"
                for e in edges
                if epic not in (e.blocker, e.blocked)
            }
        )
        cycle = find_cycle(edges + _standing_epic_edges(graph, epic))
    duplicates = sorted(
        {
            f"{e.blocker}->{e.blocked}"
            for e in edges
            if sum(
                1 for o in edges if o.blocker == e.blocker and o.blocked == e.blocked
            )
            > 1
        }
    )
    ok = not (
        dangling
        or self_edges
        or onto_closed
        or cycle
        or not_epic
        or outside
        or bad_scope
    )
    return {
        "ok": ok,
        "edgeCount": len(edges),
        "scope": epic or "portfolio",
        "badScope": bad_scope or None,
        "outsideScope": outside,
        "notEpicToEpic": not_epic,
        "cycle": cycle,
        "dangling": dangling,
        "selfEdges": self_edges,
        "ontoClosed": onto_closed,
        "fromClosed": from_closed,
        "duplicates": duplicates,
    }


# ------------------------------------------------------------------------------------
# Applying the edge diff
# ------------------------------------------------------------------------------------


def plan_edges(graph: Graph, edges: list[Edge], epic: str | None = None) -> dict:
    """Diff the proposed edge set against the tracker, respecting hand-made edges.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set: over the whole portfolio, or every edge to or
            from `epic`.
        epic: The one Epic the proposal is scoped to, or None for the whole portfolio.
            Scoped, an edge that does not touch it is neither added, converted,
            withdrawn nor re-recorded.

    Returns:
        The additions, the conversions of owned edges stored as the wrong type, the
        withdrawals, the hand-made edges left alone, and the ownership metadata the
        applied diff would write.
    """
    desired: dict[str, set[str]] = {}
    for edge in edges:
        desired.setdefault(edge.blocked, set()).add(edge.blocker)

    add: list[dict] = []
    convert: list[dict] = []
    remove: list[dict] = []
    keep = 0
    protected: list[str] = []
    metadata: dict[str, dict[str, str]] = {}

    def in_scope(blocker: str, blocked: str) -> bool:
        return epic is None or epic in (blocker, blocked)

    touched = set(desired) | {
        bead.id
        for bead in graph.beads.values()
        if bead.metadata.get(beadgraph.OWNED_KEY)
    }
    for blocked_id in sorted(touched):
        bead = graph.beads.get(blocked_id)
        if bead is None:
            continue
        want = desired.get(blocked_id, set())
        all_owned = set(bead.owned_blockers)
        owned = {b for b in all_owned if in_scope(b, blocked_id)}
        current = {b for b in bead.tracked if in_scope(b, blocked_id)}
        # Beads holds one edge per pair, so a pair is present as `tracks` or as another
        # type, never both.
        mistyped = {b for b in bead.blockers if in_scope(b, blocked_id)} - current
        present = current | mistyped
        for blocker in sorted(want - present):
            add.append({"blocker": blocker, "blocked": blocked_id})
        # ONLY an edge this system recorded as its own is ever converted or removed. An
        # edge that is present but unowned was made by hand and stays, whatever the
        # proposal says and whatever type it is stored as.
        for blocker in sorted(want & mistyped & owned):
            convert.append(
                {"blocker": blocker, "blocked": blocked_id, "from": beadgraph.BLOCKS}
            )
        for blocker in sorted((owned - want) & present):
            remove.append({"blocker": blocker, "blocked": blocked_id})
        hand_mistyped = (want & mistyped) - owned
        protected += [
            f"{b}->{blocked_id}"
            for b in sorted((present - owned - want) | hand_mistyped)
        ]
        keep += len(want & current)
        new_owned = join_ids((all_owned - owned) | (want - hand_mistyped))
        if new_owned != join_ids(all_owned):
            metadata[blocked_id] = {
                beadgraph.OWNED_KEY: new_owned,
                beadgraph.OWNED_AT_KEY: now_iso(),
            }
    return {
        "add": add,
        "convert": convert,
        "remove": remove,
        "unchanged": keep,
        "protectedHandMadeEdges": protected,
        "metadata": metadata,
    }


def _owned_after_adds(graph: Graph, plan: dict) -> dict[str, dict[str, str]]:
    """The ownership records that cover every edge the diff adds, before any is added.

    Each blocked bead that gains an edge is recorded as owning its CURRENT owned edges
    plus the ones about to be added. Written first, this guarantees an added edge is
    never present without its ownership: a failure after it leaves an owned record
    naming an edge that may not exist yet, which the next pass adds, never an unowned
    edge that no pass would ever withdraw.

    Args:
        graph: The tracker graph.
        plan: The diff, from `plan_edges`.

    Returns:
        Blocked bead id -> the ownership metadata to write ahead of the adds.
    """
    gaining: dict[str, set[str]] = {}
    for entry in plan["add"]:
        gaining.setdefault(entry["blocked"], set()).add(entry["blocker"])
    records: dict[str, dict[str, str]] = {}
    for blocked_id, blockers in sorted(gaining.items()):
        bead = graph.beads[blocked_id]
        records[blocked_id] = {
            beadgraph.OWNED_KEY: join_ids(set(bead.owned_blockers) | blockers),
            beadgraph.OWNED_AT_KEY: now_iso(),
        }
    return records


def apply_edges(
    graph: Graph,
    edges: list[Edge],
    writer: Writer,
    seen: dict[str, str],
    epic: str | None = None,
) -> dict:
    """Validate, diff and write an edge set. Idempotent by construction.

    An unchanged proposal adds nothing, converts nothing, withdraws nothing and writes no
    metadata. The writes run in an order that never leaves an edge unowned: ownership
    covering every edge to be added is written first, then the adds, then the
    conversions — each one's removal immediately followed by its `tracks` add — then the
    withdrawals, then the final ownership records, which drop the withdrawn edges.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set: over the whole portfolio, or every edge to or
            from `epic`.
        writer: The tracker writer; a dry-run writer records the writes instead.
        seen: Epic id -> the content fingerprint the sequencer read that Epic at. Empty
            when the proposal did not come from the sequencer, which records nothing.
        epic: The one Epic the proposal is scoped to, or None for the whole portfolio.
            Scoped, only that Epic records its fingerprint.

    Returns:
        The validation verdict, the counts, the plan, the Epics whose `seq_content_hash`
        is recorded, and — in a dry run — every write in order. A proposal that fails
        validation is refused whole — nothing is written.
    """
    report = validate(graph, edges, epic)
    if not report["ok"]:
        return {"applied": False, "dryRun": writer.dry_run, "validation": report}
    plan = plan_edges(graph, edges, epic)
    ahead = _owned_after_adds(graph, plan)
    for bead_id, pairs in ahead.items():
        writer.metadata(bead_id, pairs)
    for entry in plan["add"]:
        writer.bd(
            ["dep", "add", entry["blocked"], entry["blocker"], "--type", EDGE_TYPE]
        )
    for entry in plan["convert"]:
        writer.bd(["dep", "remove", entry["blocked"], entry["blocker"]])
        writer.bd(
            ["dep", "add", entry["blocked"], entry["blocker"], "--type", EDGE_TYPE]
        )
    for entry in plan["remove"]:
        writer.bd(["dep", "remove", entry["blocked"], entry["blocker"]])
    for bead_id, pairs in plan["metadata"].items():
        written = ahead.get(bead_id, {}).get(beadgraph.OWNED_KEY)
        if written != pairs[beadgraph.OWNED_KEY]:
            writer.metadata(bead_id, pairs)
    recorded = []
    for bead in graph.of_kind("epic"):
        current = seen.get(bead.id)
        if epic is not None and bead.id != epic:
            continue
        if bead.closed or not current or bead.metadata.get(SEEN_KEY) == current:
            continue
        writer.metadata(bead.id, {SEEN_KEY: current})
        recorded.append(bead.id)
    return {
        "applied": not writer.dry_run,
        "dryRun": writer.dry_run,
        "scope": epic or "portfolio",
        "planned": writer.planned,
        "sequencedRecorded": len(recorded),
        "validation": report,
        "added": len(plan["add"]),
        "converted": len(plan["convert"]),
        "removed": len(plan["remove"]),
        "unchanged": plan["unchanged"],
        "plan": plan,
    }
