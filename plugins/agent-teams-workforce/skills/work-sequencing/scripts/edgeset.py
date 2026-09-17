#!/usr/bin/env python3
"""The edge set: parse it, prove it, and apply the DIFF against what the tracker holds.

An edge means `blocker` must be elaborated before `blocked`. The reasoning pass proposes
edges; nothing here judges whether one is right. What it does judge is whether the set is
APPLICABLE — acyclic, over beads that exist, no self-edge, nothing pointed at a closed
item — because a wrong edge set applied is expensive to unpick.

The diff never removes an edge this system did not create. Ownership is recorded on the
BLOCKED bead as `seq_owned_blockers`, so an edge Mark drew by hand survives every pass,
and re-running a pass with an unchanged proposal writes nothing at all.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import beadgraph
from beadgraph import join_ids, now_iso, write_metadata

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Graph


class SequencingError(RuntimeError):
    """The command cannot proceed and the caller must fix its input."""


@dataclass(frozen=True)
class Edge:
    """A proposed blocking edge: `blocker` must be elaborated before `blocked`."""

    blocker: str
    blocked: str
    reason: str = ""
    confidence: str = ""


# ------------------------------------------------------------------------------------
# Input
# ------------------------------------------------------------------------------------


def read_edges(path: Path) -> list[Edge]:
    """Parse an edge file: `{"edges": [{"from", "to", "reason", "confidence"}]}`."""
    raw = json.loads(sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8"))
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


def validate(graph: Graph, edges: list[Edge]) -> dict:
    """Report every defect in a proposed edge set: cycles, dangling, self, closed."""
    dangling = sorted(
        {e.blocker for e in edges if e.blocker not in graph.beads}
        | {e.blocked for e in edges if e.blocked not in graph.beads}
    )
    self_edges = sorted({e.blocker for e in edges if e.blocker == e.blocked})
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
    cycle = find_cycle(edges)
    duplicates = sorted(
        {
            f"{e.blocker}->{e.blocked}"
            for e in edges
            if sum(1 for o in edges if o.blocker == e.blocker and o.blocked == e.blocked) > 1
        }
    )
    ok = not (dangling or self_edges or onto_closed or cycle)
    return {
        "ok": ok,
        "edgeCount": len(edges),
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


def plan_edges(graph: Graph, edges: list[Edge]) -> dict:
    """Diff the proposed edge set against the tracker, respecting hand-made edges."""
    desired: dict[str, set[str]] = {}
    for edge in edges:
        desired.setdefault(edge.blocked, set()).add(edge.blocker)

    add: list[dict] = []
    remove: list[dict] = []
    keep = 0
    protected: list[str] = []
    metadata: dict[str, dict[str, str]] = {}

    touched = set(desired) | {
        bead.id for bead in graph.beads.values() if bead.metadata.get(beadgraph.OWNED_KEY)
    }
    for blocked_id in sorted(touched):
        bead = graph.beads.get(blocked_id)
        if bead is None:
            continue
        want = desired.get(blocked_id, set())
        owned = set(bead.owned_blockers)
        current = set(bead.blockers)
        for blocker in sorted(want - current):
            add.append({"blocker": blocker, "blocked": blocked_id})
        # ONLY an edge this system recorded as its own is ever removed. An edge that is
        # present but unowned was made by hand and stays, whatever the proposal says.
        for blocker in sorted((owned - want) & current):
            remove.append({"blocker": blocker, "blocked": blocked_id})
        protected += [f"{b}->{blocked_id}" for b in sorted(current - owned - want)]
        keep += len(want & current)
        new_owned = join_ids(want)
        if new_owned != join_ids(owned):
            metadata[blocked_id] = {
                beadgraph.OWNED_KEY: new_owned,
                beadgraph.OWNED_AT_KEY: now_iso(),
            }
    return {
        "add": add,
        "remove": remove,
        "unchanged": keep,
        "protectedHandMadeEdges": protected,
        "metadata": metadata,
    }


def apply_edges(graph: Graph, edges: list[Edge], repo: Path | None, *, apply: bool) -> dict:
    """Validate, diff and (with `--apply`) write an edge set. Idempotent by construction."""
    report = validate(graph, edges)
    if not report["ok"]:
        return {"applied": False, "validation": report}
    plan = plan_edges(graph, edges)
    if apply:
        for entry in plan["add"]:
            beadgraph.bd_write(["dep", entry["blocker"], "--blocks", entry["blocked"]], repo)
        for entry in plan["remove"]:
            beadgraph.bd_write(["dep", "remove", entry["blocked"], entry["blocker"]], repo)
        for bead_id, pairs in plan["metadata"].items():
            write_metadata(bead_id, pairs, repo)
    return {
        "applied": apply,
        "validation": report,
        "added": len(plan["add"]),
        "removed": len(plan["remove"]),
        "unchanged": plan["unchanged"],
        "plan": plan,
    }
