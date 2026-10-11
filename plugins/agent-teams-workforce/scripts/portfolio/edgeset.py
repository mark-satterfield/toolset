#!/usr/bin/env python3
"""The dependency edge set: parse it, prove it, and apply the DIFF against what the tracker holds.

Edges are proposed at one of two levels, and both ends of an edge are of that level.

- An EPIC edge means `blocker` must be elaborated before `blocked`. It is stored as a beads
  `tracks` edge on the blocked Epic, written `bd dep add <blocked> <blocker> --type tracks`.
  `tracks` is non-blocking, so the edge orders elaboration and never removes the Epic, or
  any Story or Task beneath it, from `bd ready`.
- A TASK edge means `blocker` must be built before `blocked`. It is stored as a beads
  `blocks` edge on the blocked Task, which `bd ready` enforces. Only a Task created outside
  elaboration is assessed here: a Task elaboration wrote carries `KEY_ELAB_KEY`, and its edges
  are elaboration's.

The reasoning pass proposes edges; nothing here judges whether one is right. What it does
judge is whether the set is APPLICABLE — both ends of the level, acyclic, over beads that
exist, no self-edge, nothing pointed at a closed item — because a wrong edge set applied is
expensive to unpick.

The diff never removes an edge this system did not create. Ownership is recorded on the
BLOCKED bead as `KEY_SEQ_OWNED_BLOCKERS`, so an edge drawn by hand survives every pass,
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
the proposal together with every edge of the level that does not touch the item and every
hand-made edge that does, because the diff leaves both standing.

Both levels carry the same records. The reason for each owned edge is stored on its BLOCKED
bead as `KEY_SEQ_EDGE_REASONS`, with the item whose assessment set it, so a later assessment of
either end sees why the edge stands. The assessed item records the content fingerprint it
was assessed at as `KEY_SEQ_CONTENT_HASH`, and when, as `KEY_SEQ_ASSESSED_AT`; an item whose
fingerprint no longer matches is one that has not been assessed as it now stands.

`--owned` is the one tracker-wide operation: it proposes every owned Epic edge back, which
repairs ownership and edge type, and proposes no edge of its own.
"""

from __future__ import annotations

import json
import operator
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NotRequired, TypedDict

import beadgraph
from bead_metadata import (
    KEY_ELAB_KEY,
    KEY_SEQ_ASSESSED_AT,
    KEY_SEQ_CONTENT_HASH,
    KEY_SEQ_EDGE_REASONS,
    KEY_SEQ_EDGE_WITHDRAWN,
    KEY_SEQ_OWNED_BLOCKERS,
    KEY_SEQ_OWNED_BLOCKERS_AT,
)
from beadcontracts import PlannedWrite
from beadgraph import join_ids, now_iso
from contracts import JsonObject, JsonValue, json_object

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Bead, Graph, Writer


class SequencingError(RuntimeError):
    """The command cannot proceed and the caller must fix its input."""


@dataclass(frozen=True)
class Edge:
    """A proposed edge: `blocker` must be elaborated (Epic) or built (Task) before `blocked`."""

    blocker: str
    blocked: str
    reason: str = ""
    confidence: str = ""
    #: What the architecture was checked for, and its verdict: why the decision this edge
    #: orders is not one an effective architecture file already settles. Required on every
    #: kept edge.
    arch_check: str = ""
    #: The answer to the recorded reason an earlier assessment withdrew this edge for.
    #: Required only on an edge a withdrawal record covers.
    answers: str = ""


#: One edge standing between an item and another open bead of its level, as
#: `standing_edges` reports it. The last four come from the blocked bead's recorded
#: reasons and are None when none is recorded.
StandingEdge = TypedDict(
    "StandingEdge",
    {
        "from": str,
        "to": str,
        "type": str,
        "owned": bool,
        "reason": JsonValue,
        "confidence": JsonValue,
        "setBy": JsonValue,
        "setAt": JsonValue,
    },
)

#: One recorded withdrawal of an edge, as `withdrawal_history` reports it.
EdgeWithdrawal = TypedDict(
    "EdgeWithdrawal",
    {
        "from": str,
        "to": str,
        "reason": JsonValue,
        "withdrawnBy": JsonValue,
        "withdrawnAt": JsonValue,
    },
)

#: One withdrawal a proposal or command made, as the apply and withdraw results report it.
WithdrawnEdge = TypedDict("WithdrawnEdge", {"from": str, "to": str, "reason": str})


class PlannedEdge(TypedDict):
    """One edge a plan adds or removes."""

    blocker: str
    blocked: str


#: One owned edge a plan converts from the other level's dependency type.
ConvertedEdge = TypedDict("ConvertedEdge", {"blocker": str, "blocked": str, "from": str})


class EdgePlan(TypedDict):
    """The diff `plan_edges` computes between a proposal and the tracker."""

    add: list[PlannedEdge]
    convert: list[ConvertedEdge]
    remove: list[PlannedEdge]
    unchanged: int
    protectedHandMadeEdges: list[str]
    metadata: dict[str, dict[str, str]]


class ValidationReport(TypedDict):
    """The verdict and every defect `validate` found in a proposal."""

    ok: bool
    level: str
    edgeCount: int
    withdrawnCount: int
    scope: str
    badScope: str | None
    outsideScope: list[str]
    missingReason: list[str]
    missingArchCheck: list[str]
    readdsWithdrawn: list[str]
    unaccounted: list[str]
    withdrawnNotOwned: list[str]
    keptAndWithdrawn: list[str]
    notEpicToEpic: NotRequired[list[str]]
    notTaskToTask: NotRequired[list[str]]
    cycle: list[str]
    dangling: list[str]
    selfEdges: list[str]
    ontoClosed: list[str]
    fromClosed: list[str]
    duplicates: list[str]


class ApplyRefused(TypedDict):
    """What `apply_edges` returns for a proposal that fails validation."""

    applied: bool
    dryRun: bool
    validation: ValidationReport


class ApplyResult(TypedDict):
    """What `apply_edges` returns for a proposal it applied (or planned, in a dry run)."""

    applied: bool
    dryRun: bool
    level: str
    scope: str
    planned: list[PlannedWrite]
    sequencedRecorded: int
    validation: ValidationReport
    added: int
    converted: int
    removed: int
    unchanged: int
    withdrawn: list[WithdrawnEdge]
    reasonsRecorded: list[str]
    withdrawalsRecorded: list[str]
    plan: EdgePlan


class WithdrawSummary(TypedDict):
    """The summary line of one withdrawal."""

    withdrawn: str
    applied: bool


class WithdrawResult(TypedDict):
    """What `withdraw_edge` returns."""

    withdrawn: WithdrawnEdge
    replaced: JsonObject
    applied: bool
    dryRun: bool
    level: str
    planned: list[PlannedWrite]
    summary: WithdrawSummary


#: The dependency type each level's edges are stored as.
LEVEL_TYPES = {"epic": beadgraph.TRACKS, "task": beadgraph.BLOCKS}

#: The dependency type every Epic edge is stored as.
EDGE_TYPE = LEVEL_TYPES["epic"]

#: How each level is named in a message.
LEVEL_NAMES = {"epic": "Epic", "task": "Task"}


def _level(level: str) -> str:
    """Return a level unchanged.

    Args:
        level: `epic` or `task`.

    Returns:
        The level.

    """
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
    if level == "task" and bead.metadata.get(KEY_ELAB_KEY):
        return f"`{item}` was written by elaboration (`{KEY_ELAB_KEY}`); its edges are elaboration's"
    return ""


# ------------------------------------------------------------------------------------
# Input
# ------------------------------------------------------------------------------------


#: Standard input, read once, because an edge file given as `-` is parsed for its edges
#: and for its withdrawals.
_STDIN: list[str] = []


def _edge_file(path: Path) -> object:
    """Parse an edge file, or standard input when `path` is `-`.

    Args:
        path: The edge file, or `-` for standard input.

    Returns:
        The parsed JSON content.

    """
    if str(path) != "-":
        return json.loads(path.read_text(encoding="utf-8"))
    if not _STDIN:
        _STDIN.append(sys.stdin.read())
    return json.loads(_STDIN[0])


def _parse(entries: object) -> list[Edge]:
    """Parse a list of `{"from", "to", "reason", "confidence"}` entries.

    Args:
        entries: The list, as the edge file holds it.

    Returns:
        The edges.

    Raises:
        SequencingError: `entries` is not a list of JSON objects.

    """
    if not isinstance(entries, list):
        msg: str = f"an edge file lists its edges as a JSON array, not {type(entries).__name__}"
        raise SequencingError(msg)
    edges: list[Edge] = []
    for member in entries:
        if not isinstance(member, dict):
            msg = f"an edge entry is a JSON object, not {type(member).__name__}"
            raise SequencingError(msg)
        entry: JsonObject = json_object(member)
        blocker = str(entry.get("from") or entry.get("blocker") or "").strip()
        blocked = str(entry.get("to") or entry.get("blocked") or "").strip()
        edges.append(
            Edge(
                blocker=blocker,
                blocked=blocked,
                reason=str(entry.get("reason") or ""),
                confidence=str(entry.get("confidence") or ""),
                arch_check=str(entry.get("archCheck") or ""),
                answers=str(entry.get("answers") or ""),
            ),
        )
    return edges


def read_edges(path: Path) -> list[Edge]:
    """Read the edges of an edge file.

    The edge file is `{"edges": [{"from", "to", "reason", "confidence"}], "withdrawn":
    [{"from", "to", "reason"}]}`; a bare list is read as the edges.

    Args:
        path: The edge file, or `-` for standard input.

    Returns:
        The proposed edges.

    """
    raw: object = _edge_file(path)
    if isinstance(raw, dict):
        return _parse(json_object(raw).get("edges", []))
    return _parse(raw)


def read_withdrawn(path: Path) -> list[Edge]:
    """Read the withdrawals of an edge file: each owned standing edge the proposal drops.

    Args:
        path: The edge file, or `-` for standard input.

    Returns:
        The withdrawn edges, each with its reason; none when the file lists none.

    """
    raw: object = _edge_file(path)
    if isinstance(raw, dict):
        return _parse(json_object(raw).get("withdrawn", []))
    return []


def edge_reasons(bead: Bead) -> dict[str, JsonObject]:
    """Read the recorded reasons for the owned edges onto a bead.

    Args:
        bead: The blocked bead.

    Returns:
        Blocker id -> `{"reason", "confidence", "setBy", "setAt"}`; empty when the bead
        records none or the value does not parse as a JSON object.

    """
    raw: str | None = bead.metadata.get(KEY_SEQ_EDGE_REASONS)
    if not raw:
        return {}
    try:
        decoded: object = json.loads(raw)
    except TypeError, ValueError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    value: JsonObject = json_object(decoded)
    return {key: entry for key, entry in value.items() if isinstance(entry, dict)}


def edge_withdrawals(bead: Bead) -> dict[str, JsonObject]:
    """Read the recorded withdrawals of owned edges onto a bead.

    Args:
        bead: The blocked bead.

    Returns:
        Blocker id -> `{"reason", "withdrawnBy", "withdrawnAt"}`; empty when the bead
        records none or the value does not parse as a JSON object.

    """
    raw: str | None = bead.metadata.get(KEY_SEQ_EDGE_WITHDRAWN)
    if not raw:
        return {}
    try:
        decoded: object = json.loads(raw)
    except TypeError, ValueError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    value: JsonObject = json_object(decoded)
    return {key: entry for key, entry in value.items() if isinstance(entry, dict)}


def withdrawal_history(graph: Graph, item: str, level: str = "epic") -> list[EdgeWithdrawal]:
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
    open_items: set[str] = {b.id for b in graph.of_kind(_level(level)) if not b.closed}
    out: list[EdgeWithdrawal] = []
    for blocked_id in sorted(open_items):
        bead = graph.beads[blocked_id]
        for blocker, entry in sorted(edge_withdrawals(bead).items()):
            if item not in {blocker, blocked_id} or blocker not in open_items:
                continue
            out.append(
                {
                    "from": blocker,
                    "to": blocked_id,
                    "reason": entry.get("reason"),
                    "withdrawnBy": entry.get("withdrawnBy"),
                    "withdrawnAt": entry.get("withdrawnAt"),
                },
            )
    return sorted(out, key=operator.itemgetter("from", "to"))


def standing_edges(graph: Graph, item: str, level: str = "epic") -> list[StandingEdge]:
    """Every edge the tracker holds between one item and another open bead of its level.

    Both directions and every dependency type except `parent-child`, which is hierarchy.

    Args:
        graph: The tracker graph.
        item: The Epic or Task.
        level: `epic` or `task`: the kind of bead at both ends.

    Returns:
        One `{from, to, type, owned, reason, confidence, setBy, setAt}` per edge, in
        (from, to) order. `owned` is whether the blocked bead's `KEY_SEQ_OWNED_BLOCKERS`
        names the blocker; the last four come from its `KEY_SEQ_EDGE_REASONS` and are None
        when none is recorded.

    Raises:
        SequencingError: A tracker record's `dependencies` is not a list of JSON objects.

    """
    open_items: set[str] = {b.id for b in graph.of_kind(_level(level)) if not b.closed}
    found: dict[tuple[str, str], str] = {}
    for record in graph.records:
        blocked: str = str(record.get("id") or "")
        dependencies: JsonValue = record.get("dependencies") or []
        if not isinstance(dependencies, list):
            msg: str = f"{blocked}: `dependencies` is not a list"
            raise SequencingError(msg)
        for dep in dependencies:
            if not isinstance(dep, dict):
                msg = f"{blocked}: a dependency is not a JSON object"
                raise SequencingError(msg)
            blocker: str = str(dep.get("depends_on_id") or "")
            kind: str = str(dep.get("type") or "")
            if kind == "parent-child" or blocker == blocked:
                continue
            if item not in {blocker, blocked}:
                continue
            if blocker in open_items and blocked in open_items:
                found[blocker, blocked] = kind
    edges: list[StandingEdge] = []
    for (blocker, blocked), kind in sorted(found.items()):
        bead: Bead = graph.beads[blocked]
        recorded: JsonObject = edge_reasons(bead).get(blocker, {})
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
            },
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
    """Find one cycle in an edge set.

    Args:
        edges: The edge set.

    Returns:
        One cycle as an id path, or an empty list when the edge set is acyclic.

    """
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
                return [*path[path.index(nxt) :], nxt]
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


def _standing_level_edges(graph: Graph, item: str | None, level: str) -> list[Edge]:
    """Every edge between two beads of a level that stays standing whatever the proposal says.

    That is every edge that does not touch the item, and every hand-made edge that does:
    a proposal never lists a hand-made edge and the diff never removes one, so a cycle
    through one is as real as a cycle through any other edge. With no item — the owned-edge
    repair, whose proposal is every owned edge — it is every hand-made edge.

    Epic edges are read whether stored as `tracks` or `blocks`; Task edges are the
    `blocks` edges, the only type that orders a build.

    Args:
        graph: The tracker graph.
        item: The item whose owned edges the proposal covers, or None.
        level: `epic` or `task`.

    Returns:
        The edges.

    """

    def upstreams(bead: Bead) -> set[str]:
        if level == "epic":
            return set(bead.tracked) | set(bead.blockers)
        return set(bead.blockers)

    def stands(upstream: str, bead: Bead) -> bool:
        covered = item is None or item in {upstream, bead.id}
        return not covered or upstream not in bead.owned_blockers

    return [
        Edge(blocker=upstream, blocked=bead.id)
        for bead in graph.of_kind(_level(level))
        for upstream in sorted(upstreams(bead))
        if stands(upstream, bead) and upstream in graph.beads and graph.beads[upstream].kind == level
    ]


def _pair(edge: Edge) -> str:
    """Spell an edge as `blocker->blocked`.

    Args:
        edge: The edge.

    Returns:
        The edge as `blocker->blocked`.

    """
    return f"{edge.blocker}->{edge.blocked}"


@dataclass(frozen=True)
class _ScopeDefects:
    """The defects a proposal covering one item can have beyond those of any edge set."""

    bad_scope: str = ""
    outside: list[str] = field(default_factory=list)
    missing_reason: list[str] = field(default_factory=list)
    missing_arch_check: list[str] = field(default_factory=list)
    readds_withdrawn: list[str] = field(default_factory=list)
    unaccounted: list[str] = field(default_factory=list)
    withdrawn_not_owned: list[str] = field(default_factory=list)
    kept_and_withdrawn: list[str] = field(default_factory=list)


def _scope_defects(
    graph: Graph,
    edges: list[Edge],
    item: str,
    withdrawn: list[Edge] | tuple[Edge, ...],
    level: str,
) -> _ScopeDefects:
    """Report the defects of a proposal that covers one item.

    Args:
        graph: The tracker graph.
        edges: The proposed edge set.
        item: The one Epic or Task the proposal covers.
        withdrawn: The owned standing edges the proposal drops, each with its reason.
        level: `epic` or `task`.

    Returns:
        The scope, reason, accounting and withdrawal defects found.

    """
    owned_standing: set[str] = {f"{s['from']}->{s['to']}" for s in standing_edges(graph, item, level) if s["owned"]}
    kept: set[str] = {_pair(e) for e in edges}
    dropped: set[str] = {_pair(e) for e in withdrawn}
    withdrawn_before: dict[str, EdgeWithdrawal] = {
        f"{w['from']}->{w['to']}": w for w in withdrawal_history(graph, item, level)
    }
    return _ScopeDefects(
        bad_scope=scope_defect(graph, item, level),
        outside=sorted(
            {_pair(e) for e in edges if item not in {e.blocker, e.blocked}},
        ),
        missing_reason=sorted(
            {_pair(e) for e in [*edges, *withdrawn] if not e.reason.strip()},
        ),
        # An architecture check is the Epic edge test; a Task edge is a build dependency
        # and carries none.
        missing_arch_check=sorted({_pair(e) for e in edges if not e.arch_check.strip()}) if level == "epic" else [],
        readds_withdrawn=sorted(
            f"{_pair(e)} (withdrawn by {withdrawn_before[_pair(e)].get('withdrawnBy')}: "
            f"{withdrawn_before[_pair(e)].get('reason')})"
            for e in edges
            if _pair(e) in withdrawn_before and not e.answers.strip()
        ),
        unaccounted=sorted(owned_standing - kept - dropped),
        withdrawn_not_owned=sorted(dropped - owned_standing),
        kept_and_withdrawn=sorted(kept & dropped),
    )


def validate(
    graph: Graph,
    edges: list[Edge],
    item: str | None = None,
    withdrawn: list[Edge] | tuple[Edge, ...] = (),
    level: str = "epic",
) -> ValidationReport:
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
        | {e.blocked for e in edges if e.blocked not in graph.beads},
    )
    self_edges = sorted({e.blocker for e in edges if e.blocker == e.blocked})
    wrong_kind = sorted(
        {
            f"{e.blocker}->{e.blocked}"
            for e in edges
            if any(end in graph.beads and graph.beads[end].kind != level for end in (e.blocker, e.blocked))
        },
    )
    onto_closed = sorted(
        {f"{e.blocker}->{e.blocked}" for e in edges if e.blocked in graph.beads and graph.beads[e.blocked].closed},
    )
    from_closed = sorted(
        {f"{e.blocker}->{e.blocked}" for e in edges if e.blocker in graph.beads and graph.beads[e.blocker].closed},
    )
    cycle = find_cycle(edges + _standing_level_edges(graph, item, level))
    scoped: _ScopeDefects = _ScopeDefects() if item is None else _scope_defects(graph, edges, item, withdrawn, level)
    duplicates = sorted(
        {
            f"{e.blocker}->{e.blocked}"
            for e in edges
            if sum(1 for o in edges if o.blocker == e.blocker and o.blocked == e.blocked) > 1
        },
    )
    ok = not (
        dangling
        or self_edges
        or cycle
        or wrong_kind
        or scoped.outside
        or scoped.bad_scope
        or scoped.missing_reason
        or scoped.unaccounted
        or scoped.withdrawn_not_owned
        or scoped.kept_and_withdrawn
    )
    report: ValidationReport = {
        "ok": ok,
        "level": level,
        "edgeCount": len(edges),
        "withdrawnCount": len(withdrawn),
        "scope": item or "owned",
        "badScope": scoped.bad_scope or None,
        "outsideScope": scoped.outside,
        "missingReason": scoped.missing_reason,
        "missingArchCheck": scoped.missing_arch_check,
        "readdsWithdrawn": scoped.readds_withdrawn,
        "unaccounted": scoped.unaccounted,
        "withdrawnNotOwned": scoped.withdrawn_not_owned,
        "keptAndWithdrawn": scoped.kept_and_withdrawn,
        "cycle": cycle,
        "dangling": dangling,
        "selfEdges": self_edges,
        "ontoClosed": onto_closed,
        "fromClosed": from_closed,
        "duplicates": duplicates,
    }
    if level == "epic":
        report["notEpicToEpic"] = wrong_kind
    else:
        report["notTaskToTask"] = wrong_kind
    return report


# ------------------------------------------------------------------------------------
# Applying the edge diff
# ------------------------------------------------------------------------------------


def plan_edges(
    graph: Graph,
    edges: list[Edge],
    item: str | None = None,
    level: str = "epic",
) -> EdgePlan:
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
    own_type: str = LEVEL_TYPES[_level(level)]
    other_type: str = next(t for t in LEVEL_TYPES.values() if t != own_type)
    desired: dict[str, set[str]] = {}
    for edge in edges:
        desired.setdefault(edge.blocked, set()).add(edge.blocker)
    plan: EdgePlan = {
        "add": [],
        "convert": [],
        "remove": [],
        "unchanged": 0,
        "protectedHandMadeEdges": [],
        "metadata": {},
    }
    touched: set[str] = set(desired) | {
        bead.id for bead in graph.beads.values() if bead.metadata.get(KEY_SEQ_OWNED_BLOCKERS)
    }
    for blocked_id in sorted(touched):
        bead: Bead | None = graph.beads.get(blocked_id)
        if bead is None or bead.kind != level:
            continue
        _plan_bead(plan, bead, desired.get(blocked_id, set()), item, (own_type, other_type))
    return plan


def _plan_bead(plan: EdgePlan, bead: Bead, want: set[str], item: str | None, types: tuple[str, str]) -> None:
    """Add one blocked bead's part of the diff to the plan.

    Args:
        plan: The plan being built; its lists, count and metadata are extended in place.
        bead: The blocked bead of the level.
        want: The blockers the proposal wants on the bead.
        item: The one Epic or Task the proposal covers, or None for the owned-edge repair.
        types: The level's own dependency type and the other level's.

    """
    own_type, other_type = types
    blocked_id: str = bead.id

    def in_scope(blocker: str) -> bool:
        return item is None or item in {blocker, blocked_id}

    def of_type(kind: str) -> tuple[str, ...]:
        return bead.tracked if kind == beadgraph.TRACKS else bead.blockers

    all_owned: set[str] = set(bead.owned_blockers)
    owned: set[str] = {b for b in all_owned if in_scope(b)}
    current: set[str] = {b for b in of_type(own_type) if in_scope(b)}
    # Beads holds one edge per pair, so a pair is present as the level's type or as
    # the other, never both.
    mistyped: set[str] = {b for b in of_type(other_type) if in_scope(b)} - current
    present: set[str] = current | mistyped
    plan["add"].extend({"blocker": blocker, "blocked": blocked_id} for blocker in sorted(want - present))
    # ONLY an edge this system recorded as its own is ever converted or removed. An
    # edge that is present but unowned was made by hand and stays, whatever the
    # proposal says and whatever type it is stored as.
    plan["convert"].extend(
        {"blocker": blocker, "blocked": blocked_id, "from": other_type} for blocker in sorted(want & mistyped & owned)
    )
    plan["remove"].extend({"blocker": blocker, "blocked": blocked_id} for blocker in sorted((owned - want) & present))
    hand_mistyped: set[str] = (want & mistyped) - owned
    plan["protectedHandMadeEdges"] += [f"{b}->{blocked_id}" for b in sorted((present - owned - want) | hand_mistyped)]
    plan["unchanged"] += len(want & current)
    new_owned: str = join_ids((all_owned - owned) | (want - hand_mistyped))
    if new_owned != join_ids(all_owned):
        plan["metadata"][blocked_id] = {
            KEY_SEQ_OWNED_BLOCKERS: new_owned,
            KEY_SEQ_OWNED_BLOCKERS_AT: now_iso(),
        }


def _owned_after_adds(graph: Graph, plan: EdgePlan) -> dict[str, dict[str, str]]:
    """Build the ownership records that cover every edge the diff adds, before any is added.

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
            KEY_SEQ_OWNED_BLOCKERS: join_ids(set(bead.owned_blockers) | blockers),
            KEY_SEQ_OWNED_BLOCKERS_AT: now_iso(),
        }
    return records


def _reason_records(
    graph: Graph,
    edges: list[Edge],
    plan: EdgePlan,
    item: str,
    level: str = "epic",
) -> dict[str, str]:
    """Build the `KEY_SEQ_EDGE_REASONS` value each blocked bead must carry after a proposal applies.

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
    touched: set[str] = {item} | set(proposed) | {s["to"] for s in standing_edges(graph, item, level) if s["owned"]}
    stamp: str = now_iso()
    out: dict[str, str] = {}
    for blocked_id in sorted(touched):
        bead: Bead | None = graph.beads.get(blocked_id)
        if bead is None:
            continue
        final: str | None = plan["metadata"].get(blocked_id, {}).get(KEY_SEQ_OWNED_BLOCKERS)
        owned_after: set[str] = set(beadgraph.split_ids(final)) if final is not None else set(bead.owned_blockers)
        before: dict[str, JsonObject] = edge_reasons(bead)
        after: dict[str, JsonObject] = {
            blocker: entry
            for blocker, entry in before.items()
            if item not in {blocker, blocked_id} or blocker in owned_after
        }
        for blocker, edge in proposed.get(blocked_id, {}).items():
            if blocker not in owned_after:
                continue
            entry: JsonObject = {
                "reason": edge.reason,
                "confidence": edge.confidence,
                "setBy": item,
            }
            old: JsonObject = before.get(blocker, {})
            same: bool = all(old.get(k) == v for k, v in entry.items())
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
    """Build the `KEY_SEQ_EDGE_WITHDRAWN` value each blocked bead must carry after a proposal applies.

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
    stamp: str = now_iso()
    touched: set[str] = {e.blocked for e in withdrawn} | {e.blocked for e in edges}
    out: dict[str, str] = {}
    for blocked_id in sorted(touched):
        bead: Bead | None = graph.beads.get(blocked_id)
        if bead is None:
            continue
        before: dict[str, JsonObject] = edge_withdrawals(bead)
        after: dict[str, JsonObject] = dict(before)
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
    withdrawal: Edge,
    writer: Writer,
    withdrawn_by: str,
    level: str = "epic",
) -> WithdrawResult:
    """Withdraw ONE standing owned edge, and record the withdrawal with its reason.

    The edge is removed, its ownership and recorded reason are dropped, and the
    withdrawal is recorded on the blocked bead, so no later assessment sets the edge
    again without answering this reason. Nothing else about either bead changes, and a
    hand-made edge is refused rather than removed.

    Args:
        graph: The tracker graph.
        withdrawal: The edge to withdraw: `blocker` (the `from` end), `blocked` (the `to`
            end) and `reason`, why the edge does not exist. The reason is recorded, and
            answered by any later proposal that sets the edge again.
        writer: The tracker writer; a dry-run writer records the writes instead.
        withdrawn_by: What withdrew it, recorded alongside the reason.
        level: `epic` or `task`.

    Returns:
        What was withdrawn and what was written.

    Raises:
        SequencingError: The edge does not stand between two open beads of the level,
            it was drawn by hand, or no reason was given.

    """
    blocker: str = withdrawal.blocker
    blocked: str = withdrawal.blocked
    reason: str = withdrawal.reason
    if not reason.strip():
        msg = "a withdrawal states why the edge does not exist: pass --reason"
        raise SequencingError(msg)
    standing: dict[tuple[str, str], StandingEdge] = {
        (s["from"], s["to"]): s for s in standing_edges(graph, blocked, level)
    }
    edge: StandingEdge | None = standing.get((blocker, blocked))
    if edge is None:
        msg = f"no {LEVEL_NAMES[_level(level)]} edge {blocker}->{blocked} stands between two open beads"
        raise SequencingError(msg)
    if not edge["owned"]:
        msg = f"{blocker}->{blocked} was drawn by hand and is never withdrawn here"
        raise SequencingError(msg)
    bead: Bead = graph.beads[blocked]
    reasons: dict[str, JsonObject] = edge_reasons(bead)
    recorded: JsonObject = reasons.pop(blocker, {})
    withdrawals: dict[str, JsonObject] = edge_withdrawals(bead)
    withdrawals[blocker] = {
        "reason": reason,
        "withdrawnBy": withdrawn_by,
        "withdrawnAt": now_iso(),
    }
    writer.bd(["dep", "remove", blocked, blocker])
    writer.metadata(
        blocked,
        {
            KEY_SEQ_OWNED_BLOCKERS: join_ids(set(bead.owned_blockers) - {blocker}),
            KEY_SEQ_OWNED_BLOCKERS_AT: now_iso(),
            KEY_SEQ_EDGE_REASONS: json.dumps(reasons, sort_keys=True, separators=(",", ":")),
            KEY_SEQ_EDGE_WITHDRAWN: json.dumps(
                withdrawals,
                sort_keys=True,
                separators=(",", ":"),
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


@dataclass(frozen=True)
class ApplyScope:
    """What one edge application covers, beyond the edges themselves.

    Attributes:
        seen: Item id -> the content fingerprint the assessment read that item at. Empty
            when the proposal did not come from an assessment, which records nothing.
        item: The one Epic or Task the proposal covers, or None for the owned-edge
            repair, which records no reason and no assessment.
        withdrawn: The owned standing edges the proposal drops, each with its reason.
        level: `epic` (`tracks` edges) or `task` (`blocks` edges).

    """

    seen: dict[str, str]
    item: str | None = None
    withdrawn: list[Edge] | tuple[Edge, ...] = ()
    level: str = "epic"


def _write_plan(writer: Writer, plan: EdgePlan, ahead: dict[str, dict[str, str]], edge_type: str) -> None:
    """Write the ownership-first records, then the adds, conversions and withdrawals of a plan.

    Args:
        writer: The tracker writer.
        plan: The diff `plan_edges` returned.
        ahead: The ownership records covering every edge about to be added.
        edge_type: The dependency type the level's edges are stored as.

    """
    for bead_id, pairs in ahead.items():
        writer.metadata(bead_id, pairs)
    for entry in plan["add"]:
        writer.bd(
            ["dep", "add", entry["blocked"], entry["blocker"], "--type", edge_type],
        )
    for entry in plan["convert"]:
        writer.bd(["dep", "remove", entry["blocked"], entry["blocker"]])
        writer.bd(
            ["dep", "add", entry["blocked"], entry["blocker"], "--type", edge_type],
        )
    for entry in plan["remove"]:
        writer.bd(["dep", "remove", entry["blocked"], entry["blocker"]])


def _record_assessed(graph: Graph, writer: Writer, scope: ApplyScope) -> list[str]:
    """Record the fingerprint each assessed item was assessed at, and when.

    Args:
        graph: The tracker graph.
        writer: The tracker writer.
        scope: The applied scope; its `seen` fingerprints are recorded.

    Returns:
        The ids of the items recorded.

    """
    recorded: list[str] = []
    for bead in graph.of_kind(scope.level):
        current: str | None = scope.seen.get(bead.id)
        if scope.item is not None and bead.id != scope.item:
            continue
        if bead.closed or not current:
            continue
        if scope.item is None and bead.metadata.get(KEY_SEQ_CONTENT_HASH) == current:
            continue
        pairs: dict[str, str] = {KEY_SEQ_CONTENT_HASH: current}
        if scope.item is not None:
            pairs[KEY_SEQ_ASSESSED_AT] = now_iso()
        writer.metadata(bead.id, pairs)
        recorded.append(bead.id)
    return recorded


def apply_edges(
    graph: Graph,
    edges: list[Edge],
    writer: Writer,
    scope: ApplyScope,
) -> ApplyRefused | ApplyResult:
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
        scope: The assessed fingerprints, the item covered, the withdrawals and the level.

    Returns:
        The validation verdict, the counts, the plan, the withdrawals with their reasons,
        the beads whose reasons are recorded, and — in a dry run — every write in order.
        A proposal that fails validation is refused whole — nothing is written.

    """
    item: str | None = scope.item
    withdrawn: list[Edge] | tuple[Edge, ...] = scope.withdrawn
    level: str = scope.level
    edges = [
        e for e in edges if not any(end in graph.beads and graph.beads[end].closed for end in (e.blocker, e.blocked))
    ]
    report: ValidationReport = validate(graph, edges, item, withdrawn, level)
    if not report["ok"]:
        return {"applied": False, "dryRun": writer.dry_run, "validation": report}
    plan: EdgePlan = plan_edges(graph, edges, item, level)
    reasons: dict[str, str] = _reason_records(graph, edges, plan, item, level) if item is not None else {}
    withdrawals: dict[str, str] = _withdrawal_records(graph, edges, withdrawn, item) if item is not None else {}
    pending: dict[str, dict[str, str]] = {}
    for bead_id, value in reasons.items():
        pending.setdefault(bead_id, {})[KEY_SEQ_EDGE_REASONS] = value
    for bead_id, value in withdrawals.items():
        pending.setdefault(bead_id, {})[KEY_SEQ_EDGE_WITHDRAWN] = value
    ahead: dict[str, dict[str, str]] = _owned_after_adds(graph, plan)
    _write_plan(writer, plan, ahead, LEVEL_TYPES[level])
    for bead_id, pairs in plan["metadata"].items():
        written: str | None = ahead.get(bead_id, {}).get(KEY_SEQ_OWNED_BLOCKERS)
        if written != pairs[KEY_SEQ_OWNED_BLOCKERS]:
            final: dict[str, str] = dict(pairs)
            final.update(pending.pop(bead_id, {}))
            writer.metadata(bead_id, final)
    for bead_id, values in sorted(pending.items()):
        writer.metadata(bead_id, values)
    recorded: list[str] = _record_assessed(graph, writer, scope)
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
        "withdrawn": [{"from": e.blocker, "to": e.blocked, "reason": e.reason} for e in withdrawn],
        "reasonsRecorded": sorted(reasons),
        "withdrawalsRecorded": sorted(withdrawals),
        "plan": plan,
    }
