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

A proposal covers ONE EPIC: every edge to or from that Epic, each with a reason, and a
`withdrawn` entry, with a reason, for every owned edge standing on that Epic that the
proposal does not keep. An edge that does not touch the Epic is refused, an owned standing
edge the proposal neither keeps nor withdraws is refused, and only edges touching the Epic
are added, converted or withdrawn. Acyclicity is checked over the proposal together with
every Epic edge that does not touch the Epic.

The reason for each owned edge is stored on its BLOCKED Epic as `seq_edge_reasons`, with
the Epic whose assessment set it, so a later assessment of either end sees why the edge
stands. The assessed Epic records the content fingerprint it was assessed at as
`seq_content_hash`, and when, as `seq_assessed_at`; an Epic whose fingerprint no longer
matches is one that has not been assessed as it now stands.

`--owned` is the one tracker-wide operation: it proposes every owned edge back, which
repairs ownership and edge type, and proposes no edge of its own.
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

    from beadgraph import Bead, Graph, Writer


#: Metadata key on an Epic: the content fingerprint the sequencer last read it at.
SEEN_KEY = "seq_content_hash"

#: Metadata key on a BLOCKED Epic: a JSON object keyed by blocker id, each value
#: `{"reason", "confidence", "setBy", "setAt"}`, covering only the owned edges onto it.
REASONS_KEY = "seq_edge_reasons"

#: Metadata key on an Epic: when its dependency assessment was last applied.
ASSESSED_AT_KEY = "seq_assessed_at"


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


#: Standard input, read once, because an edge file given as `-` is parsed for its edges
#: and for its withdrawals.
_STDIN: list[str] = []


def _edge_file(path: Path) -> object:
    """The parsed content of an edge file, or of standard input when `path` is `-`."""
    if str(path) != "-":
        return json.loads(path.read_text(encoding="utf-8"))
    if not _STDIN:
        _STDIN.append(sys.stdin.read())
    return json.loads(_STDIN[0])


def _parse(entries: object, field: str) -> list[Edge]:
    """Parse a list of `{"from", "to", "reason", "confidence"}` entries.

    Args:
        entries: The list.
        field: The list's name in the edge file, for the error message.

    Returns:
        The edges.

    Raises:
        SequencingError: The list is not a list, or an entry names no `from`/`to` pair.
    """
    if not isinstance(entries, list):
        msg = f"`{field}` in the edge file must be a list"
        raise SequencingError(msg)
    edges: list[Edge] = []
    for entry in entries:
        if not isinstance(entry, dict):
            msg = f"{field} entry {entry!r} is not an object"
            raise SequencingError(msg)
        blocker = str(entry.get("from") or entry.get("blocker") or "").strip()
        blocked = str(entry.get("to") or entry.get("blocked") or "").strip()
        if not blocker or not blocked:
            msg = f"{field} entry {entry!r} names no `from`/`to` pair"
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


def read_edges(path: Path) -> list[Edge]:
    """The edges of an edge file.

    The edge file is `{"edges": [{"from", "to", "reason", "confidence"}], "withdrawn":
    [{"from", "to", "reason"}]}`; a bare list is read as the edges.

    Args:
        path: The edge file, or `-` for standard input.

    Returns:
        The proposed edges.
    """
    raw = _edge_file(path)
    return _parse(raw.get("edges", []) if isinstance(raw, dict) else raw, "edges")


def read_withdrawn(path: Path) -> list[Edge]:
    """The withdrawals of an edge file: each owned standing edge the proposal drops.

    Args:
        path: The edge file, or `-` for standard input.

    Returns:
        The withdrawn edges, each with its reason; none when the file lists none.
    """
    raw = _edge_file(path)
    return _parse(
        raw.get("withdrawn", []) if isinstance(raw, dict) else [], "withdrawn"
    )


def edge_reasons(bead: Bead) -> dict:
    """The recorded reasons for the owned edges onto a bead.

    Args:
        bead: The blocked bead.

    Returns:
        Blocker id -> `{"reason", "confidence", "setBy", "setAt"}`; empty when the bead
        records none or the value does not parse as a JSON object.
    """
    raw = bead.metadata.get(REASONS_KEY)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items() if isinstance(v, dict)}


def standing_edges(graph: Graph, epic: str) -> list[dict]:
    """Every edge the tracker holds between one Epic and another open Epic.

    Both directions and every dependency type except `parent-child`, which is hierarchy.

    Args:
        graph: The tracker graph.
        epic: The Epic.

    Returns:
        One `{from, to, type, owned, reason, confidence, setBy, setAt}` per edge, in
        (from, to) order. `owned` is whether the blocked Epic's `seq_owned_blockers`
        names the blocker; the last four come from its `seq_edge_reasons` and are None
        when none is recorded.
    """
    open_epics = {b.id for b in graph.of_kind("epic") if not b.closed}
    found: dict[tuple[str, str], str] = {}
    for record in graph.records:
        blocked = str(record.get("id") or "")
        for dep in record.get("dependencies") or []:
            blocker = str(dep.get("depends_on_id") or "")
            kind = str(dep.get("type") or "")
            if kind == "parent-child" or blocker == blocked:
                continue
            if epic not in (blocker, blocked):
                continue
            if blocker in open_epics and blocked in open_epics:
                found[(blocker, blocked)] = kind
    edges = []
    for (blocker, blocked), kind in sorted(found.items()):
        bead = graph.beads[blocked]
        recorded = edge_reasons(bead).get(blocker, {})
        edges.append(
            {
                "from": blocker,
                "to": blocked,
                "type": kind,
                "owned": blocker in bead.owned_blockers,
                "reason": recorded.get("reason"),
                "confidence": recorded.get("confidence"),
                "setBy": recorded.get("setBy"),
                "setAt": recorded.get("setAt"),
            }
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


def _pair(edge: Edge) -> str:
    """An edge as `blocker->blocked`."""
    return f"{edge.blocker}->{edge.blocked}"


def validate(
    graph: Graph,
    edges: list[Edge],
    epic: str | None = None,
    withdrawn: list[Edge] | tuple[Edge, ...] = (),
) -> dict:
    """Report every defect in a proposed edge set.

    The defects are: an edge that is not Epic to Epic, a cycle, a dangling id, a
    self-edge, an edge onto a closed bead, an edge out of a closed bead, and — for a
    proposal covering one Epic — a scope that is not an open Epic, an edge that does not
    touch that Epic, an edge or withdrawal with an empty reason, an owned edge standing
    on that Epic that is neither kept nor withdrawn, a withdrawal that is not an owned
    edge standing on that Epic (every hand-made edge is one), and a pair both kept and
    withdrawn.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set.
        epic: The one Epic the proposal covers, or None for the owned-edge repair.
        withdrawn: The owned standing edges the proposal drops, each with its reason.

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
    missing_reason: list[str] = []
    unaccounted: list[str] = []
    withdrawn_not_owned: list[str] = []
    kept_and_withdrawn: list[str] = []
    bad_scope = ""
    if epic is None:
        cycle = find_cycle(edges)
    else:
        scope = graph.beads.get(epic)
        if scope is None or scope.kind != "epic" or scope.closed:
            bad_scope = f"{epic} is not an open Epic"
        outside = sorted(
            {_pair(e) for e in edges if epic not in (e.blocker, e.blocked)}
        )
        cycle = find_cycle(edges + _standing_epic_edges(graph, epic))
        missing_reason = sorted(
            {_pair(e) for e in [*edges, *withdrawn] if not e.reason.strip()}
        )
        owned_standing = {
            f"{s['from']}->{s['to']}" for s in standing_edges(graph, epic) if s["owned"]
        }
        kept = {_pair(e) for e in edges}
        dropped = {_pair(e) for e in withdrawn}
        unaccounted = sorted(owned_standing - kept - dropped)
        withdrawn_not_owned = sorted(dropped - owned_standing)
        kept_and_withdrawn = sorted(kept & dropped)
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
        or from_closed
        or cycle
        or not_epic
        or outside
        or bad_scope
        or missing_reason
        or unaccounted
        or withdrawn_not_owned
        or kept_and_withdrawn
    )
    return {
        "ok": ok,
        "edgeCount": len(edges),
        "withdrawnCount": len(withdrawn),
        "scope": epic or "owned",
        "badScope": bad_scope or None,
        "outsideScope": outside,
        "missingReason": missing_reason,
        "unaccounted": unaccounted,
        "withdrawnNotOwned": withdrawn_not_owned,
        "keptAndWithdrawn": kept_and_withdrawn,
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


def _reason_records(
    graph: Graph, edges: list[Edge], plan: dict, epic: str
) -> dict[str, str]:
    """The `seq_edge_reasons` value each blocked Epic must carry after a proposal applies.

    For every blocked Epic an edge in scope touches, the recorded reasons keep every
    out-of-scope entry, drop every in-scope blocker that is no longer owned, and record
    each proposed edge that ends up owned as `{reason, confidence, setBy, setAt}`. An
    entry whose reason, confidence and setter are unchanged keeps its recorded `setAt`,
    so an unchanged proposal writes nothing.

    Args:
        graph: The tracker graph.
        edges: The proposed edges, every one touching `epic`.
        plan: The diff, from `plan_edges`.
        epic: The Epic whose assessment made the proposal.

    Returns:
        Blocked Epic id -> the JSON value to write, for each Epic whose value changes.
    """
    proposed: dict[str, dict[str, Edge]] = {}
    for edge in edges:
        proposed.setdefault(edge.blocked, {})[edge.blocker] = edge
    touched = (
        {epic}
        | set(proposed)
        | {s["to"] for s in standing_edges(graph, epic) if s["owned"]}
    )
    stamp = now_iso()
    out: dict[str, str] = {}
    for blocked_id in sorted(touched):
        bead = graph.beads.get(blocked_id)
        if bead is None:
            continue
        final = plan["metadata"].get(blocked_id, {}).get(beadgraph.OWNED_KEY)
        owned_after = (
            set(beadgraph.split_ids(final))
            if final is not None
            else set(bead.owned_blockers)
        )
        before = edge_reasons(bead)
        after = {
            blocker: entry
            for blocker, entry in before.items()
            if epic not in (blocker, blocked_id) or blocker in owned_after
        }
        for blocker, edge in proposed.get(blocked_id, {}).items():
            if blocker not in owned_after:
                continue
            entry = {
                "reason": edge.reason,
                "confidence": edge.confidence,
                "setBy": epic,
            }
            old = before.get(blocker, {})
            same = all(old.get(k) == v for k, v in entry.items())
            entry["setAt"] = old.get("setAt") if same and old.get("setAt") else stamp
            after[blocker] = entry
        if after != before:
            out[blocked_id] = json.dumps(after, sort_keys=True, separators=(",", ":"))
    return out


def apply_edges(
    graph: Graph,
    edges: list[Edge],
    writer: Writer,
    seen: dict[str, str],
    epic: str | None = None,
    withdrawn: list[Edge] | tuple[Edge, ...] = (),
) -> dict:
    """Validate, diff and write an edge set. Idempotent by construction.

    An unchanged proposal adds nothing, converts nothing, withdraws nothing and writes no
    edge metadata. The writes run in an order that never leaves an edge unowned:
    ownership covering every edge to be added is written first, then the adds, then the
    conversions — each one's removal immediately followed by its `tracks` add — then the
    withdrawals, then the final ownership records, which drop the withdrawn edges and
    carry the reasons for the owned edges onto that bead. A bead whose reasons change and
    whose ownership does not gets its reasons in a write of their own. Last, the assessed
    Epic records the fingerprint it was assessed at and when, on every call that applies.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set: every edge to or from `epic`, or with `epic`
            None, the owned edges proposed back.
        writer: The tracker writer; a dry-run writer records the writes instead.
        seen: Epic id -> the content fingerprint the sequencer read that Epic at. Empty
            when the proposal did not come from the sequencer, which records nothing.
        epic: The one Epic the proposal covers, or None for the owned-edge repair, which
            records no reason and no assessment.
        withdrawn: The owned standing edges the proposal drops, each with its reason.

    Returns:
        The validation verdict, the counts, the plan, the withdrawals with their reasons,
        the Epics whose reasons are recorded, and — in a dry run — every write in order.
        A proposal that fails validation is refused whole — nothing is written.
    """
    report = validate(graph, edges, epic, withdrawn)
    if not report["ok"]:
        return {"applied": False, "dryRun": writer.dry_run, "validation": report}
    plan = plan_edges(graph, edges, epic)
    reasons = _reason_records(graph, edges, plan, epic) if epic is not None else {}
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
    pending_reasons = dict(reasons)
    for bead_id, pairs in plan["metadata"].items():
        written = ahead.get(bead_id, {}).get(beadgraph.OWNED_KEY)
        if written != pairs[beadgraph.OWNED_KEY]:
            final = dict(pairs)
            if bead_id in pending_reasons:
                final[REASONS_KEY] = pending_reasons.pop(bead_id)
            writer.metadata(bead_id, final)
    for bead_id, value in sorted(pending_reasons.items()):
        writer.metadata(bead_id, {REASONS_KEY: value})
    recorded = []
    for bead in graph.of_kind("epic"):
        current = seen.get(bead.id)
        if epic is not None and bead.id != epic:
            continue
        if bead.closed or not current:
            continue
        if epic is None and bead.metadata.get(SEEN_KEY) == current:
            continue
        pairs = {SEEN_KEY: current}
        if epic is not None:
            pairs[ASSESSED_AT_KEY] = now_iso()
        writer.metadata(bead.id, pairs)
        recorded.append(bead.id)
    return {
        "applied": not writer.dry_run,
        "dryRun": writer.dry_run,
        "scope": epic or "owned",
        "planned": writer.planned,
        "sequencedRecorded": len(recorded),
        "validation": report,
        "added": len(plan["add"]),
        "converted": len(plan["convert"]),
        "removed": len(plan["remove"]),
        "unchanged": plan["unchanged"],
        "withdrawn": [
            {"from": e.blocker, "to": e.blocked, "reason": e.reason} for e in withdrawn
        ],
        "reasonsRecorded": sorted(reasons),
        "plan": plan,
    }
