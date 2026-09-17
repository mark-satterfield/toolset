#!/usr/bin/env python3
"""WSJF arithmetic over the tracker graph — no model call, no judgement, repeatable.

Two operations, and both are pure arithmetic over values somebody else judged:

* a TASK inherits User-Business Value and Time Criticality from the Epic above it (walking
  Story -> Epic), computes RR-OE from how many Tasks it transitively unblocks, and divides
  Cost of Delay by the job size the decomposition judged;
* an EPIC replaces its span estimate with the sum of its Tasks' job sizes, mapped onto the
  span scale, and is rescored on it — top-down value, bottom-up cost.

The rubrics are `agent-teams-workforce:task-wsjf` and `:epic-wsjf`. The bands here are
theirs; this module implements them and does not invent a second rubric.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from beadgraph import now_iso, write_metadata
from edgeset import Edge, find_cycle

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Graph

#: RR-OE bands for a Task, from `agent-teams-workforce:task-wsjf`. Read there, not here.
RROE_BANDS = ((0, 1), (1, 3), (3, 5), (6, 8), (9, 13))
RROE_TOP = 20

#: Developer-day sum -> Epic span rung, from `agent-teams-workforce:epic-wsjf`.
SIZE_RUNGS = ((2, 1), (5, 2), (10, 3), (20, 5), (40, 8), (80, 13), (160, 20))
SIZE_TOP = 40


def _int(value: str | None) -> int | None:
    """Parse a metadata integer, returning None when it is absent or unusable."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def band(value: int, bands: tuple[tuple[int, int], ...], top: int) -> int:
    """Map a count onto a rubric's bands, falling through to its top rung."""
    for ceiling, rung in bands:
        if value <= ceiling:
            return rung
    return top


def reachable_count(start: str, successors: dict[str, set[str]]) -> int:
    """How many DISTINCT beads are reachable forward from `start`, excluding itself."""
    seen: set[str] = set()
    queue = deque(successors.get(start, set()))
    while queue:
        node = queue.popleft()
        if node in seen or node == start:
            continue
        seen.add(node)
        queue.extend(successors.get(node, set()))
    return len(seen)


def score_tasks(graph: Graph, repo: Path | None, *, apply: bool) -> dict:
    """Inherit Task value from its Epic and recompute Task WSJF. Pure arithmetic."""
    tasks = [b for b in graph.of_kind("task") if not b.closed]
    ids = {t.id for t in tasks}
    successors: dict[str, set[str]] = {}
    for task in tasks:
        for blocker in task.blockers:
            if blocker in ids:
                successors.setdefault(blocker, set()).add(task.id)

    cycle = find_cycle(
        [Edge(blocker, blocked) for blocker, blockeds in successors.items() for blocked in blockeds]
    )
    scored: list[dict] = []
    unscored: list[dict] = []
    for task in tasks:
        epic = graph.epic_of(task.id)
        if epic is None:
            unscored.append({"id": task.id, "reason": "no Epic above it"})
            continue
        ubv = _int(epic.metadata.get("wsjf_ubv"))
        tc = _int(epic.metadata.get("wsjf_tc"))
        size = _int(task.metadata.get("wsjf_size"))
        if ubv is None or tc is None:
            unscored.append(
                {"id": task.id, "reason": f"parent Epic {epic.id} carries no wsjf_ubv/wsjf_tc"}
            )
            continue
        if size is None or size <= 0:
            unscored.append({"id": task.id, "reason": "no judged wsjf_size on the Task"})
            continue
        unblocks = reachable_count(task.id, successors)
        rroe = band(unblocks, RROE_BANDS, RROE_TOP)
        cod = ubv + tc + rroe
        wsjf = round(cod / size, 2)
        confidence = _int(epic.metadata.get("wsjf_confidence"))
        pairs = {
            "wsjf": f"{wsjf:.2f}",
            "wsjf_calculated_at": now_iso(),
            "wsjf_rubric": "task-wsjf",
            "wsjf_ubv": str(ubv),
            "wsjf_tc": str(tc),
            "wsjf_value_from": epic.id,
            "wsjf_rroe": str(rroe),
            "wsjf_unblocks": str(unblocks),
            "wsjf_cod": str(cod),
            "wsjf_size": str(size),
        }
        if confidence is not None:
            pairs["wsjf_confidence"] = str(confidence)
        changed = any(
            task.metadata.get(k) != v for k, v in pairs.items() if k != "wsjf_calculated_at"
        )
        if apply and changed:
            write_metadata(task.id, pairs, repo)
        scored.append({"id": task.id, "wsjf": wsjf, "changed": changed, **pairs})
    return {
        "applied": apply,
        "cycle": cycle,
        "scored": scored,
        "unscored": unscored,
        "counts": {"scored": len(scored), "unscored": len(unscored)},
    }


def rollup_epics(graph: Graph, repo: Path | None, *, apply: bool) -> dict:
    """Replace each Epic's span estimate with the sum of its Tasks' sizes, and rescore."""
    rolled: list[dict] = []
    skipped: list[dict] = []
    for epic in graph.of_kind("epic"):
        tasks = [b for b in graph.descendants(epic.id) if b.kind == "task"]
        sizes = [_int(t.metadata.get("wsjf_size")) for t in tasks]
        if not tasks or any(s is None for s in sizes):
            skipped.append(
                {
                    "id": epic.id,
                    "reason": "no Tasks beneath it" if not tasks else "a Task carries no wsjf_size",
                }
            )
            continue
        days = sum(s for s in sizes if s is not None)
        rung = band(days, SIZE_RUNGS, SIZE_TOP)
        cod = _int(epic.metadata.get("wsjf_cod"))
        if cod is None:
            ubv = _int(epic.metadata.get("wsjf_ubv"))
            tc = _int(epic.metadata.get("wsjf_tc"))
            rroe = _int(epic.metadata.get("wsjf_rroe"))
            if None in (ubv, tc, rroe):
                skipped.append(
                    {"id": epic.id, "reason": "the Epic carries no wsjf_cod and no dimensions"}
                )
                continue
            cod = (ubv or 0) + (tc or 0) + (rroe or 0)
        wsjf = round(cod / rung, 2)
        pairs = {
            "wsjf": f"{wsjf:.2f}",
            "wsjf_calculated_at": now_iso(),
            "wsjf_cod": str(cod),
            "wsjf_size": str(rung),
            "wsjf_size_source": "task-rollup",
            "wsjf_size_task_days": str(days),
        }
        changed = any(
            epic.metadata.get(k) != v for k, v in pairs.items() if k != "wsjf_calculated_at"
        )
        if apply and changed:
            write_metadata(epic.id, pairs, repo)
        rolled.append(
            {"id": epic.id, "taskDays": days, "jobSize": rung, "wsjf": wsjf, "changed": changed}
        )
    return {"applied": apply, "rolled": rolled, "skipped": skipped}
