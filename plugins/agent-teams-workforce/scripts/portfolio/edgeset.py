#!/usr/bin/env python3
"""The dependency edge set: parse it, prove it, and apply the DIFF against what the tracker holds.

Edges are proposed at one of two levels, and both ends of an edge are of that level.

- An EPIC edge means `blocker` must be elaborated before `blocked`. It is stored as a beads
  `tracks` edge on the blocked Epic, written `bd dep add <blocked> <blocker> --type tracks`.
  `tracks` is non-blocking, so the edge orders elaboration and never removes the Epic, or
  any Story or Task beneath it, from `bd ready`.
- A TASK edge means `blocker` must be built before `blocked`. It is stored as a beads
  `blocks` edge on the blocked Task, which `bd ready` enforces. Only a Task created outside
  elaboration is assessed here: a Task elaboration wrote carries `elab_key`, and its edges
  are elaboration's.

The reasoning pass proposes edges; nothing here judges whether one is right. What it does
judge is whether the set is APPLICABLE — both ends of the level, acyclic, over beads that
exist, no self-edge, nothing pointed at a closed item — because a wrong edge set applied is
expensive to unpick.

The diff never removes an edge this system did not create. Ownership is recorded on the
BLOCKED bead as `seq_owned_blockers`, so an edge drawn by hand survives every pass,
and re-running a pass with an unchanged proposal writes nothing at all.

An owned edge stored as the other level's type is CONVERTED to its own level's type:
`bd dep remove`, then `bd dep add --type <type>`. Beads holds one edge per pair of beads and
refuses to add a second type onto an existing one, so the removal has to come first. The edge stays recorded
as owned throughout, so a conversion interrupted between its two writes leaves an owned
edge that is absent, and the next pass over the same proposal adds it.

A proposal covers ONE EPIC, or ONE TASK created outside elaboration: every edge to or from
that item, each with a reason, and a `withdrawn` entry, with a reason, for every owned edge
standing on that item that the proposal does not keep. An edge that does not touch the item
is refused, an owned standing edge the proposal neither keeps nor withdraws is refused, and
only edges touching the item are added, converted or withdrawn. Acyclicity is checked over
the proposal together with every edge of the level that does not touch the item.

Both levels carry the same records. The reason for each owned edge is stored on its BLOCKED
bead as `seq_edge_reasons`, with the item whose assessment set it, so a later assessment of
either end sees why the edge stands. The assessed item records the content fingerprint it
was assessed at as `seq_content_hash`, and when, as `seq_assessed_at`; an item whose
fingerprint no longer matches is one that has not been assessed as it now stands.

`--owned` is the one tracker-wide operation: it proposes every owned Epic edge back, which
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


#: Metadata key on an assessed item: the content fingerprint its assessment last read it at.
SEEN_KEY = "seq_content_hash"

#: Metadata key on a BLOCKED item: a JSON object keyed by blocker id, each value
#: `{"reason", "confidence", "setBy", "setAt"}`, covering only the owned edges onto it.
REASONS_KEY = "seq_edge_reasons"

#: Metadata key on a BLOCKED item: a JSON object keyed by blocker id, each value
#: `{"reason", "withdrawnBy", "withdrawnAt"}`, for every owned edge onto it that an
#: assessment withdrew. An edge a withdrawal covers is not set again until a later
#: proposal answers that recorded reason, so the outcome cannot depend on which Epic was
#: assessed last.
WITHDRAWN_KEY = "seq_edge_withdrawn"

#: Metadata key on an assessed item: when its dependency assessment was last applied.
ASSESSED_AT_KEY = "seq_assessed_at"

#: Metadata key elaboration writes on every Story and Task it creates. A Task carrying it
#: has its edges from elaboration and is never assessed here.
ELAB_IDENTITY_KEY = "elab_key"


class SequencingError(RuntimeError):
    """The command cannot proceed and the caller must fix its input."""


@dataclass(frozen=True)
class Edge:
    """A proposed edge: `blocker` must be elaborated (Epic) or built (Task) before `blocked`."""

    blocker: str
    blocked: str
    reason: str = ""
    confidence: str = ""
    #: What the SAD was checked for, and its verdict: why the decision this edge orders
    #: is not one the SAD already settles. Required on every kept edge.
    sad_check: str = ""
    #: The answer to the recorded reason an earlier assessment withdrew this edge for.
    #: Required only on an edge a withdrawal record covers.
    answers: str = ""


#: The dependency type each level's edges are stored as.
LEVEL_TYPES = {"epic": beadgraph.TRACKS, "task": beadgraph.BLOCKS}

#: The dependency type every Epic edge is stored as.
EDGE_TYPE = LEVEL_TYPES["epic"]

#: How each level is named in a message.
LEVEL_NAMES = {"epic": "Epic", "task": "Task"}


def _level(level: str) -> str:
    """A level, checked.

    Args:
        level: `epic` or `task`.

    Returns:
        The level.

    Raises:
        SequencingError: The level is neither.
    """
    if level not in LEVEL_TYPES:
        msg = f"level {level!r} is not one of {sorted(LEVEL_TYPES)}"
        raise SequencingError(msg)
    return level


def scope_defect(graph: Graph, item: str, level: str = "epic") -> str:
    """Why one item cannot be the scope of a proposal at a level, or empty when it can.

    Args:
        graph: The tracker graph.
        item: The Epic or Task the proposal covers.
        level: `epic` or `task`.

    Returns:
        The defect, or an empty string. At Task level a Task elaboration wrote is refused,
        because its edges are elaboration's.
    """
    bead = graph.beads.get(item)
    if bead is None or bead.kind != _level(level) or bead.closed:
        return f"{item} is not an open {LEVEL_NAMES[level]}"
    if level == "task" and bead.metadata.get(ELAB_IDENTITY_KEY):
        return (
            f"`{item}` was written by elaboration (`{ELAB_IDENTITY_KEY}`); "
            "its edges are elaboration's"
        )
    return ""


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
                sad_check=str(entry.get("sadCheck") or ""),
                answers=str(entry.get("answers") or ""),
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


def edge_withdrawals(bead: Bead) -> dict:
    """The recorded withdrawals of owned edges onto a bead.

    Args:
        bead: The blocked bead.

    Returns:
        Blocker id -> `{"reason", "withdrawnBy", "withdrawnAt"}`; empty when the bead
        records none or the value does not parse as a JSON object.
    """
    raw = bead.metadata.get(WITHDRAWN_KEY)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items() if isinstance(v, dict)}


def withdrawal_history(graph: Graph, item: str, level: str = "epic") -> list[dict]:
    """Every withdrawal an assessment recorded for an edge touching one item.

    Args:
        graph: The tracker graph.
        item: The Epic or Task.
        level: `epic` or `task`: the kind of bead at both ends.

    Returns:
        One `{from, to, reason, withdrawnBy, withdrawnAt}` per recorded withdrawal, in
        (from, to) order. An edge this lists is set again only by a proposal that
        answers the recorded reason.
    """
    open_items = {b.id for b in graph.of_kind(_level(level)) if not b.closed}
    out = []
    for blocked_id in sorted(open_items):
        bead = graph.beads[blocked_id]
        for blocker, entry in sorted(edge_withdrawals(bead).items()):
            if item not in (blocker, blocked_id) or blocker not in open_items:
                continue
            out.append(
                {
                    "from": blocker,
                    "to": blocked_id,
                    "reason": entry.get("reason"),
                    "withdrawnBy": entry.get("withdrawnBy"),
                    "withdrawnAt": entry.get("withdrawnAt"),
                }
            )
    return sorted(out, key=lambda e: (e["from"], e["to"]))


def standing_edges(graph: Graph, item: str, level: str = "epic") -> list[dict]:
    """Every edge the tracker holds between one item and another open bead of its level.

    Both directions and every dependency type except `parent-child`, which is hierarchy.

    Args:
        graph: The tracker graph.
        item: The Epic or Task.
        level: `epic` or `task`: the kind of bead at both ends.

    Returns:
        One `{from, to, type, owned, reason, confidence, setBy, setAt}` per edge, in
        (from, to) order. `owned` is whether the blocked bead's `seq_owned_blockers`
        names the blocker; the last four come from its `seq_edge_reasons` and are None
        when none is recorded.
    """
    open_items = {b.id for b in graph.of_kind(_level(level)) if not b.closed}
    found: dict[tuple[str, str], str] = {}
    for record in graph.records:
        blocked = str(record.get("id") or "")
        for dep in record.get("dependencies") or []:
            blocker = str(dep.get("depends_on_id") or "")
            kind = str(dep.get("type") or "")
            if kind == "parent-child" or blocker == blocked:
                continue
            if item not in (blocker, blocked):
                continue
            if blocker in open_items and blocked in open_items:
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
    """Every Epic edge this system recorded as its own, as a proposal.

    Proposing the owned set back withdraws nothing, adds any owned edge that is absent,
    and converts any owned edge stored as the wrong type. Because it is read from the
    ownership records rather than from the edges present, rerunning it after an
    interrupted pass still names every edge that pass was converting. Only Epics are
    read: an owned Task edge is never proposed as an Epic edge.

    Args:
        graph: The tracker graph.

    Returns:
        One edge per owned blocker on every Epic, in id order.
    """
    return [
        Edge(blocker=blocker, blocked=bead.id, reason="owned edge")
        for bead in graph.of_kind("epic")
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


def _standing_level_edges(graph: Graph, item: str, level: str) -> list[Edge]:
    """Every edge between two beads of a level that does not touch one item.

    Epic edges are read whether stored as `tracks` or `blocks`; Task edges are the
    `blocks` edges, the only type that orders a build.

    Args:
        graph: The tracker graph.
        item: The item whose own edges are left out.
        level: `epic` or `task`.

    Returns:
        The edges.
    """

    def upstreams(bead: Bead) -> set[str]:
        if level == "epic":
            return set(bead.tracked) | set(bead.blockers)
        return set(bead.blockers)

    return [
        Edge(blocker=upstream, blocked=bead.id)
        for bead in graph.of_kind(_level(level))
        for upstream in sorted(upstreams(bead))
        if item not in (upstream, bead.id)
        and upstream in graph.beads
        and graph.beads[upstream].kind == level
    ]


def _pair(edge: Edge) -> str:
    """An edge as `blocker->blocked`."""
    return f"{edge.blocker}->{edge.blocked}"


def validate(
    graph: Graph,
    edges: list[Edge],
    item: str | None = None,
    withdrawn: list[Edge] | tuple[Edge, ...] = (),
    level: str = "epic",
) -> dict:
    """Report every defect in a proposed edge set.

    The defects are: an edge whose ends are not both of the level (`notEpicToEpic` or
    `notTaskToTask`), a cycle, a dangling id, a self-edge, an edge onto a closed bead, an
    edge out of a closed bead, and — for a proposal covering one item — a scope that is
    not an open item of the level (at Task level, also one elaboration wrote), an edge
    that does not touch that item, an edge or withdrawal with an empty reason, an owned
    edge standing on that item that is neither kept nor withdrawn, a withdrawal that is
    not an owned edge standing on that item (every hand-made edge is one), and a pair
    both kept and withdrawn.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set.
        item: The one Epic or Task the proposal covers, or None for the owned-edge
            repair.
        withdrawn: The owned standing edges the proposal drops, each with its reason.
        level: `epic` or `task`.

    Returns:
        The verdict and every defect found.
    """
    _level(level)
    dangling = sorted(
        {e.blocker for e in edges if e.blocker not in graph.beads}
        | {e.blocked for e in edges if e.blocked not in graph.beads}
    )
    self_edges = sorted({e.blocker for e in edges if e.blocker == e.blocked})
    wrong_kind = sorted(
        {
            f"{e.blocker}->{e.blocked}"
            for e in edges
            if any(
                end in graph.beads and graph.beads[end].kind != level
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
    missing_sad_check: list[str] = []
    readds_withdrawn: list[str] = []
    unaccounted: list[str] = []
    withdrawn_not_owned: list[str] = []
    kept_and_withdrawn: list[str] = []
    bad_scope = ""
    if item is None:
        cycle = find_cycle(edges)
    else:
        bad_scope = scope_defect(graph, item, level)
        outside = sorted(
            {_pair(e) for e in edges if item not in (e.blocker, e.blocked)}
        )
        cycle = find_cycle(edges + _standing_level_edges(graph, item, level))
        missing_reason = sorted(
            {_pair(e) for e in [*edges, *withdrawn] if not e.reason.strip()}
        )
        owned_standing = {
            f"{s['from']}->{s['to']}"
            for s in standing_edges(graph, item, level)
            if s["owned"]
        }
        kept = {_pair(e) for e in edges}
        dropped = {_pair(e) for e in withdrawn}
        missing_sad_check = sorted({_pair(e) for e in edges if not e.sad_check.strip()})
        withdrawn_before = {
            f"{w['from']}->{w['to']}": w for w in withdrawal_history(graph, item, level)
        }
        readds_withdrawn = sorted(
            f"{_pair(e)} (withdrawn by {withdrawn_before[_pair(e)].get('withdrawnBy')}: "
            f"{withdrawn_before[_pair(e)].get('reason')})"
            for e in edges
            if _pair(e) in withdrawn_before and not e.answers.strip()
        )
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
        or wrong_kind
        or outside
        or bad_scope
        or missing_reason
        or missing_sad_check
        or readds_withdrawn
        or unaccounted
        or withdrawn_not_owned
        or kept_and_withdrawn
    )
    return {
        "ok": ok,
        "level": level,
        "edgeCount": len(edges),
        "withdrawnCount": len(withdrawn),
        "scope": item or "owned",
        "badScope": bad_scope or None,
        "outsideScope": outside,
        "missingReason": missing_reason,
        "missingSadCheck": missing_sad_check,
        "readdsWithdrawn": readds_withdrawn,
        "unaccounted": unaccounted,
        "withdrawnNotOwned": withdrawn_not_owned,
        "keptAndWithdrawn": kept_and_withdrawn,
        "notEpicToEpic" if level == "epic" else "notTaskToTask": wrong_kind,
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


def plan_edges(
    graph: Graph, edges: list[Edge], item: str | None = None, level: str = "epic"
) -> dict:
    """Diff the proposed edge set against the tracker, respecting hand-made edges.

    Only beads of the level are diffed, so an Epic pass never touches a Task's edges and
    a Task pass never touches an Epic's.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set: every edge to or from `item`, or, with `item`
            None, the owned edges proposed back by the `--owned` repair.
        item: The one Epic or Task the proposal covers, or None for the owned-edge
            repair. Scoped, an edge that does not touch it is neither added, converted,
            withdrawn nor re-recorded.
        level: `epic` or `task`.

    Returns:
        The additions, the conversions of owned edges stored as the other level's type
        (each naming the type it is converted `from`), the withdrawals, the hand-made
        edges left alone, and the ownership metadata the applied diff would write.
    """
    own_type = LEVEL_TYPES[_level(level)]
    other_type = next(t for t in LEVEL_TYPES.values() if t != own_type)
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
        return item is None or item in (blocker, blocked)

    def of_type(bead: Bead, kind: str) -> tuple[str, ...]:
        return bead.tracked if kind == beadgraph.TRACKS else bead.blockers

    touched = set(desired) | {
        bead.id
        for bead in graph.beads.values()
        if bead.metadata.get(beadgraph.OWNED_KEY)
    }
    for blocked_id in sorted(touched):
        bead = graph.beads.get(blocked_id)
        if bead is None or bead.kind != level:
            continue
        want = desired.get(blocked_id, set())
        all_owned = set(bead.owned_blockers)
        owned = {b for b in all_owned if in_scope(b, blocked_id)}
        current = {b for b in of_type(bead, own_type) if in_scope(b, blocked_id)}
        # Beads holds one edge per pair, so a pair is present as the level's type or as
        # the other, never both.
        mistyped = {
            b for b in of_type(bead, other_type) if in_scope(b, blocked_id)
        } - current
        present = current | mistyped
        for blocker in sorted(want - present):
            add.append({"blocker": blocker, "blocked": blocked_id})
        # ONLY an edge this system recorded as its own is ever converted or removed. An
        # edge that is present but unowned was made by hand and stays, whatever the
        # proposal says and whatever type it is stored as.
        for blocker in sorted(want & mistyped & owned):
            convert.append(
                {"blocker": blocker, "blocked": blocked_id, "from": other_type}
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
    graph: Graph, edges: list[Edge], plan: dict, item: str, level: str = "epic"
) -> dict[str, str]:
    """The `seq_edge_reasons` value each blocked bead must carry after a proposal applies.

    For every blocked bead an edge in scope touches, the recorded reasons keep every
    out-of-scope entry, drop every in-scope blocker that is no longer owned, and record
    each proposed edge that ends up owned as `{reason, confidence, setBy, setAt}`. An
    entry whose reason, confidence and setter are unchanged keeps its recorded `setAt`,
    so an unchanged proposal writes nothing.

    Args:
        graph: The tracker graph.
        edges: The proposed edges, every one touching `item`.
        plan: The diff, from `plan_edges`.
        item: The Epic or Task whose assessment made the proposal.
        level: `epic` or `task`.

    Returns:
        Blocked bead id -> the JSON value to write, for each bead whose value changes.
    """
    proposed: dict[str, dict[str, Edge]] = {}
    for edge in edges:
        proposed.setdefault(edge.blocked, {})[edge.blocker] = edge
    touched = (
        {item}
        | set(proposed)
        | {s["to"] for s in standing_edges(graph, item, level) if s["owned"]}
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
            if item not in (blocker, blocked_id) or blocker in owned_after
        }
        for blocker, edge in proposed.get(blocked_id, {}).items():
            if blocker not in owned_after:
                continue
            entry = {
                "reason": edge.reason,
                "confidence": edge.confidence,
                "setBy": item,
            }
            old = before.get(blocker, {})
            same = all(old.get(k) == v for k, v in entry.items())
            entry["setAt"] = old.get("setAt") if same and old.get("setAt") else stamp
            after[blocker] = entry
        if after != before:
            out[blocked_id] = json.dumps(after, sort_keys=True, separators=(",", ":"))
    return out


def _withdrawal_records(
    graph: Graph,
    edges: list[Edge],
    withdrawn: list[Edge] | tuple[Edge, ...],
    item: str,
) -> dict[str, str]:
    """The `seq_edge_withdrawn` value each blocked bead must carry after a proposal applies.

    A withdrawal is recorded on the bead it blocked, with the reason and who withdrew it,
    so a later assessment of either end cannot set that edge again without answering it.
    An edge this proposal sets again — which validation admits only when the proposal
    answers the recorded reason — has its record dropped.

    Args:
        graph: The tracker graph.
        edges: The proposed edges, every one touching `item`.
        withdrawn: The owned standing edges the proposal drops, each with its reason.
        item: The Epic or Task whose assessment made the proposal.

    Returns:
        Blocked bead id -> the JSON value to write, for each bead whose value changes.
    """
    stamp = now_iso()
    touched = {e.blocked for e in withdrawn} | {e.blocked for e in edges}
    out: dict[str, str] = {}
    for blocked_id in sorted(touched):
        bead = graph.beads.get(blocked_id)
        if bead is None:
            continue
        before = edge_withdrawals(bead)
        after = dict(before)
        for edge in withdrawn:
            if edge.blocked != blocked_id:
                continue
            after[edge.blocker] = {
                "reason": edge.reason,
                "withdrawnBy": item,
                "withdrawnAt": stamp,
            }
        for edge in edges:
            if edge.blocked == blocked_id:
                after.pop(edge.blocker, None)
        if after != before:
            out[blocked_id] = json.dumps(after, sort_keys=True, separators=(",", ":"))
    return out


def withdraw_edge(
    graph: Graph,
    blocker: str,
    blocked: str,
    reason: str,
    writer: Writer,
    withdrawn_by: str,
    level: str = "epic",
) -> dict:
    """Withdraw ONE standing owned edge, and record the withdrawal with its reason.

    The edge is removed, its ownership and recorded reason are dropped, and the
    withdrawal is recorded on the blocked bead, so no later assessment sets the edge
    again without answering this reason. Nothing else about either bead changes, and a
    hand-made edge is refused rather than removed.

    Args:
        graph: The tracker graph.
        blocker: The bead at the `from` end.
        blocked: The bead at the `to` end.
        reason: Why the edge does not exist. Recorded, and answered by any later
            proposal that sets the edge again.
        writer: The tracker writer; a dry-run writer records the writes instead.
        withdrawn_by: What withdrew it, recorded alongside the reason.
        level: `epic` or `task`.

    Returns:
        What was withdrawn and what was written.

    Raises:
        SequencingError: The edge does not stand between two open beads of the level,
            it was drawn by hand, or no reason was given.
    """
    if not reason.strip():
        msg = "a withdrawal states why the edge does not exist: pass --reason"
        raise SequencingError(msg)
    standing = {(s["from"], s["to"]): s for s in standing_edges(graph, blocked, level)}
    edge = standing.get((blocker, blocked))
    if edge is None:
        msg = f"no {LEVEL_NAMES[_level(level)]} edge {blocker}->{blocked} stands between two open beads"
        raise SequencingError(msg)
    if not edge["owned"]:
        msg = f"{blocker}->{blocked} was drawn by hand and is never withdrawn here"
        raise SequencingError(msg)
    bead = graph.beads[blocked]
    reasons = edge_reasons(bead)
    recorded = reasons.pop(blocker, {})
    withdrawals = edge_withdrawals(bead)
    withdrawals[blocker] = {
        "reason": reason,
        "withdrawnBy": withdrawn_by,
        "withdrawnAt": now_iso(),
    }
    writer.bd(["dep", "remove", blocked, blocker])
    writer.metadata(
        blocked,
        {
            beadgraph.OWNED_KEY: join_ids(set(bead.owned_blockers) - {blocker}),
            beadgraph.OWNED_AT_KEY: now_iso(),
            REASONS_KEY: json.dumps(reasons, sort_keys=True, separators=(",", ":")),
            WITHDRAWN_KEY: json.dumps(
                withdrawals, sort_keys=True, separators=(",", ":")
            ),
        },
    )
    return {
        "withdrawn": {"from": blocker, "to": blocked, "reason": reason},
        "replaced": recorded,
        "applied": not writer.dry_run,
        "dryRun": writer.dry_run,
        "level": level,
        "planned": writer.planned,
        "summary": {
            "withdrawn": f"{blocker}->{blocked}",
            "applied": not writer.dry_run,
        },
    }


def apply_edges(
    graph: Graph,
    edges: list[Edge],
    writer: Writer,
    seen: dict[str, str],
    item: str | None = None,
    withdrawn: list[Edge] | tuple[Edge, ...] = (),
    level: str = "epic",
) -> dict:
    """Validate, diff and write an edge set. Idempotent by construction.

    An unchanged proposal adds nothing, converts nothing, withdraws nothing and writes no
    edge metadata. The writes run in an order that never leaves an edge unowned:
    ownership covering every edge to be added is written first, then the adds, then the
    conversions — each one's removal immediately followed by its add as the level's type
    — then the withdrawals, then the final ownership records, which drop the withdrawn
    edges and carry the reasons for the owned edges onto that bead and the record of
    every edge withdrawn from it. A bead whose reasons
    change and whose ownership does not gets its reasons in a write of their own. Last,
    the assessed item records the fingerprint it was assessed at and when, on every call
    that applies.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set: every edge to or from `item`, or with `item`
            None, the owned edges proposed back.
        writer: The tracker writer; a dry-run writer records the writes instead.
        seen: Item id -> the content fingerprint the assessment read that item at. Empty
            when the proposal did not come from an assessment, which records nothing.
        item: The one Epic or Task the proposal covers, or None for the owned-edge
            repair, which records no reason and no assessment.
        withdrawn: The owned standing edges the proposal drops, each with its reason.
        level: `epic` (`tracks` edges) or `task` (`blocks` edges).

    Returns:
        The validation verdict, the counts, the plan, the withdrawals with their reasons,
        the beads whose reasons are recorded, and — in a dry run — every write in order.
        A proposal that fails validation is refused whole — nothing is written.
    """
    report = validate(graph, edges, item, withdrawn, level)
    if not report["ok"]:
        return {"applied": False, "dryRun": writer.dry_run, "validation": report}
    edge_type = LEVEL_TYPES[level]
    plan = plan_edges(graph, edges, item, level)
    reasons = (
        _reason_records(graph, edges, plan, item, level) if item is not None else {}
    )
    withdrawals = (
        _withdrawal_records(graph, edges, withdrawn, item) if item is not None else {}
    )
    pending: dict[str, dict[str, str]] = {}
    for bead_id, value in reasons.items():
        pending.setdefault(bead_id, {})[REASONS_KEY] = value
    for bead_id, value in withdrawals.items():
        pending.setdefault(bead_id, {})[WITHDRAWN_KEY] = value
    ahead = _owned_after_adds(graph, plan)
    for bead_id, pairs in ahead.items():
        writer.metadata(bead_id, pairs)
    for entry in plan["add"]:
        writer.bd(
            ["dep", "add", entry["blocked"], entry["blocker"], "--type", edge_type]
        )
    for entry in plan["convert"]:
        writer.bd(["dep", "remove", entry["blocked"], entry["blocker"]])
        writer.bd(
            ["dep", "add", entry["blocked"], entry["blocker"], "--type", edge_type]
        )
    for entry in plan["remove"]:
        writer.bd(["dep", "remove", entry["blocked"], entry["blocker"]])
    for bead_id, pairs in plan["metadata"].items():
        written = ahead.get(bead_id, {}).get(beadgraph.OWNED_KEY)
        if written != pairs[beadgraph.OWNED_KEY]:
            final = dict(pairs)
            final.update(pending.pop(bead_id, {}))
            writer.metadata(bead_id, final)
    for bead_id, values in sorted(pending.items()):
        writer.metadata(bead_id, values)
    recorded = []
    for bead in graph.of_kind(level):
        current = seen.get(bead.id)
        if item is not None and bead.id != item:
            continue
        if bead.closed or not current:
            continue
        if item is None and bead.metadata.get(SEEN_KEY) == current:
            continue
        pairs = {SEEN_KEY: current}
        if item is not None:
            pairs[ASSESSED_AT_KEY] = now_iso()
        writer.metadata(bead.id, pairs)
        recorded.append(bead.id)
    return {
        "applied": not writer.dry_run,
        "dryRun": writer.dry_run,
        "level": level,
        "scope": item or "owned",
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
        "withdrawalsRecorded": sorted(withdrawals),
        "plan": plan,
    }
