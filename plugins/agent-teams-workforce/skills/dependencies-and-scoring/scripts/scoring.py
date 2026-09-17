#!/usr/bin/env python3
"""WSJF arithmetic over the tracker graph — no model call, no judgement, repeatable.

ONE loop, per Epic in scope, and it is one loop because the two directions are two halves
of the same fact:

* value and time criticality flow DOWN — a Task inherits User-Business Value and Time
  Criticality from the Epic above it (walking Story -> Epic), computes RR-OE from how many
  Tasks it transitively unblocks, and divides Cost of Delay by the job size the
  decomposition judged;
* size flows UP — the Epic's span estimate is REPLACED by the sum of its Tasks' job sizes,
  mapped onto the span scale, and the Epic's score is recomputed from that concrete number.

An Epic recalculated without its Tasks is half an answer, so there is no way to ask for
half. The rubrics are `agent-teams-workforce:task-wsjf` and `:epic-wsjf`; the bands here
are theirs and this module invents no second rubric.

Nothing here skips an item because it already carries a score. A score is a function of a
graph that moves, so an in-scope item is recomputed and overwritten every time. The only
thing the comparison below decides is whether an identical value is worth a tracker write.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from beadgraph import now_iso, write_metadata

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Bead, Graph

#: RR-OE bands for a Task, from `agent-teams-workforce:task-wsjf`. Read there, not here.
RROE_BANDS = ((0, 1), (1, 3), (3, 5), (6, 8), (9, 13))
RROE_TOP = 20

#: Developer-day sum -> Epic span rung, from `agent-teams-workforce:epic-wsjf`.
SIZE_RUNGS = ((2, 1), (5, 2), (10, 3), (20, 5), (40, 8), (80, 13), (160, 20))
SIZE_TOP = 40


def _int(value: str | None) -> int | None:
    """Parse a metadata integer, returning None when it is absent or unusable.

    Args:
        value: The raw metadata value.

    Returns:
        The integer, or None when there is not one.
    """
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def band(value: int, bands: tuple[tuple[int, int], ...], top: int) -> int:
    """Map a count onto a rubric's bands, falling through to its top rung.

    Args:
        value: The count to place.
        bands: Ceiling/rung pairs in ascending ceiling order.
        top: The rung for anything above the last ceiling.

    Returns:
        The rung the value lands on.
    """
    for ceiling, rung in bands:
        if value <= ceiling:
            return rung
    return top


def reachable_count(start: str, successors: dict[str, set[str]]) -> int:
    """How many DISTINCT beads are reachable forward from `start`, excluding itself.

    Args:
        start: The bead to walk from.
        successors: Blocker id -> the ids it blocks.

    Returns:
        The size of the forward reachable set.
    """
    seen: set[str] = set()
    pending = deque(successors.get(start, set()))
    while pending:
        node = pending.popleft()
        if node in seen or node == start:
            continue
        seen.add(node)
        pending.extend(successors.get(node, set()))
    return len(seen)


def task_successors(graph: Graph) -> dict[str, set[str]]:
    """The Task blocking graph, forward: blocker id -> the Task ids it blocks.

    Args:
        graph: The tracker graph.

    Returns:
        The forward adjacency over open Tasks. It is built over the WHOLE portfolio even
        when the scope is narrower, because RR-OE counts what a Task unblocks and that
        count does not stop at the edge of the scope.
    """
    tasks = [b for b in graph.of_kind("task") if not b.closed]
    ids = {t.id for t in tasks}
    successors: dict[str, set[str]] = {}
    for task in tasks:
        for blocker in task.blockers:
            if blocker in ids:
                successors.setdefault(blocker, set()).add(task.id)
    return successors


def _write(bead: Bead, pairs: dict[str, str], repo: Path | None) -> bool:
    """Write recomputed scoring metadata onto a bead unless it is already identical.

    Args:
        bead: The bead being scored.
        pairs: The metadata to store.
        repo: The repository to run `bd` from, or None for the working directory.

    Returns:
        True when the tracker was written.
    """
    changed = any(bead.metadata.get(k) != v for k, v in pairs.items() if k != "wsjf_calculated_at")
    if changed:
        write_metadata(bead.id, pairs, repo)
    return changed


def _score_task(
    task: Bead, epic: Bead, successors: dict[str, set[str]], repo: Path | None
) -> dict:
    """Recompute one Task's WSJF from its Epic's value and the Task graph.

    Args:
        task: The Task being scored.
        epic: The Epic above it, whose value and time criticality it inherits.
        successors: The forward Task blocking graph.
        repo: The repository to run `bd` from, or None for the working directory.

    Returns:
        The scored record, or a record carrying `reason` when an input is missing.
    """
    ubv = _int(epic.metadata.get("wsjf_ubv"))
    tc = _int(epic.metadata.get("wsjf_tc"))
    size = _int(task.metadata.get("wsjf_size"))
    if ubv is None or tc is None:
        return {"id": task.id, "reason": f"parent Epic {epic.id} carries no wsjf_ubv/wsjf_tc"}
    if size is None or size <= 0:
        return {"id": task.id, "reason": "no judged wsjf_size on the Task"}
    unblocks = reachable_count(task.id, successors)
    rroe = band(unblocks, RROE_BANDS, RROE_TOP)
    cod = ubv + tc + rroe
    wsjf = round(cod / size, 2)
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
    confidence = _int(epic.metadata.get("wsjf_confidence"))
    if confidence is not None:
        pairs["wsjf_confidence"] = str(confidence)
    return {"id": task.id, "wsjf": wsjf, "written": _write(task, pairs, repo), **pairs}


def _rollup_epic(epic: Bead, tasks: list[Bead], repo: Path | None) -> dict:
    """Replace an Epic's span estimate with the sum of its Tasks' sizes, and rescore it.

    Args:
        epic: The Epic being rescored.
        tasks: Its Tasks, at any depth.
        repo: The repository to run `bd` from, or None for the working directory.

    Returns:
        The rolled-up record, or a record carrying `reason` when an input is missing.
    """
    sizes = [_int(t.metadata.get("wsjf_size")) for t in tasks]
    if not tasks or any(s is None for s in sizes):
        return {
            "id": epic.id,
            "reason": "no Tasks beneath it" if not tasks else "a Task carries no wsjf_size",
        }
    days = sum(s for s in sizes if s is not None)
    rung = band(days, SIZE_RUNGS, SIZE_TOP)
    cod = _int(epic.metadata.get("wsjf_cod"))
    if cod is None:
        ubv = _int(epic.metadata.get("wsjf_ubv"))
        tc = _int(epic.metadata.get("wsjf_tc"))
        rroe = _int(epic.metadata.get("wsjf_rroe"))
        if None in (ubv, tc, rroe):
            return {"id": epic.id, "reason": "the Epic carries no wsjf_cod and no dimensions"}
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
    return {
        "id": epic.id,
        "taskDays": days,
        "jobSize": rung,
        "wsjf": wsjf,
        "written": _write(epic, pairs, repo),
    }


def score(graph: Graph, repo: Path | None, epic_ids: list[str]) -> dict:
    """Recalculate every Epic in scope together with its Tasks, in one pass.

    Value and time criticality flow down from the Epic to its Tasks; size flows back up
    from the Tasks and replaces the Epic's estimate, and the Epic is rescored on it. Both
    directions happen here because they are one recalculation, not two commands.

    Args:
        graph: The tracker graph.
        repo: The repository to run `bd` from, or None for the working directory.
        epic_ids: The Epics in scope.

    Returns:
        One record per Epic — its Tasks' scores, its rolled-up size and its own score —
        plus everything that could not be scored and why.
    """
    successors = task_successors(graph)
    epics: list[dict] = []
    incomplete: list[dict] = []
    for epic_id in epic_ids:
        epic = graph.beads.get(epic_id)
        if epic is None or epic.kind != "epic":
            incomplete.append({"id": epic_id, "reason": "not an Epic in the tracker"})
            continue
        tasks = [b for b in graph.descendants(epic.id) if b.kind == "task" and not b.closed]
        scored: list[dict] = []
        for task in sorted(tasks, key=lambda t: t.id):
            record = _score_task(task, epic, successors, repo)
            if "reason" in record:
                incomplete.append(record)
            else:
                scored.append(record)
        # Same loop, other direction: the sizes those Tasks carry become the Epic's.
        rollup = _rollup_epic(epic, tasks, repo)
        if "reason" in rollup:
            incomplete.append(rollup)
            rollup = {"id": epic.id}
        epics.append({**rollup, "tasks": scored, "taskCount": len(scored)})
    return {
        "epics": epics,
        "incomplete": incomplete,
        "counts": {
            "epics": len(epics),
            "tasks": sum(e["taskCount"] for e in epics),
            "incomplete": len(incomplete),
        },
    }
