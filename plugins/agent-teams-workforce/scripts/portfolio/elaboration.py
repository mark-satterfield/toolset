#!/usr/bin/env python3
"""The Epic elaboration lifecycle: whether an Epic may be elaborated now, and finishing it.

`prd-to-spec` is the one elaborator, and every door into it — the headless lane, a person at
`/work-bead` or `/start-prd` — arrives here twice.

At the START, one Epic is judged, and the first condition that fails is the refusal:

* it is an open Epic;
* it is not `elaboration_state = done`: its Tasks are written and they are the workable items;
* it is not `in_progress` under another run's owner token (unless the caller reclaims).

Which Epic is elaborated next, and whether it is scored and its upstream Epics are elaborated,
is decided by keeper selection before any door arrives here, so it is not judged again. An
absent or unrecognised `elaboration_state` is taken as `ready`, with a warning for the latter.

When the conditions hold, the Epic is marked `in_progress` and the run's owner token is
recorded on it as `elaboration_state_owner`. The token is the caller's, or a fresh one. An
`in_progress` Epic carrying a different token is owned by another run; the caller passes
`reclaim` only once it has established that run is not live.

At the FINISH, after the Tasks are written:

* the WSJF arithmetic runs over the whole tracker and writes only this Epic and the Tasks
  beneath it: the Epic's size becomes the sum of its Tasks' sizes with its estimate kept, the
  Epic is rescored, and its Tasks are rescored with value inherited from it and RR-OE counted
  over every Task edge, across Stories;
* with `done`, the Epic's `elaboration_state` is set to `done` with the cause
  `decomposed-into-tasks` and its owner token is cleared. The Epic stays open; it closes
  only when its work is released.

A run that started an Epic and ends without setting its elaboration to `done` RELEASES it: its owner token is
cleared and the Epic stays `in_progress`, so the next run takes it up without a reclaim.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from beadgraph import now_iso
from scoring import score

if TYPE_CHECKING:
    from beadgraph import Bead, Graph, Writer

#: The Epic's elaboration lifecycle and its companions.
STATE_KEY = "elaboration_state"
STATE_AT_KEY = "elaboration_state_at"
CAUSE_KEY = "elaboration_state_cause"
OWNER_KEY = "elaboration_state_owner"

READY = "ready"
IN_PROGRESS = "in_progress"
DONE = "done"

#: The cause recorded when elaboration starts and when its Tasks are written.
CAUSE_STARTED = "elaboration-started"
CAUSE_DECOMPOSED = "decomposed-into-tasks"


class LifecycleError(RuntimeError):
    """The command cannot proceed and the caller must fix its input."""


def _int(value: object) -> int | None:
    """Parse a metadata integer, returning None when it is absent or unusable.

    Args:
        value: The raw metadata value.

    Returns:
        The integer, or None when there is not one.
    """
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _refusal(code: str, reason: str, epic: Bead | None, **extra: object) -> dict:
    """A refusal to start elaboration, named by code.

    Args:
        code: The condition that failed.
        reason: What a person reads.
        epic: The Epic, when it exists.
        **extra: Detail the caller may report.

    Returns:
        The payload.
    """
    return {
        "ok": False,
        "refusal": {"code": code, "reason": reason, **extra},
        "epic": {"id": epic.id, "title": epic.title} if epic else None,
        "summary": {"ok": False, "refusal": code},
    }


def _epic_value(epic: Bead) -> dict:
    """The Epic's scored values, as a Task inherits them.

    Args:
        epic: The Epic.

    Returns:
        Its id, title, value, criticality and value confidence.
    """
    return {
        "id": epic.id,
        "title": epic.title,
        "userBusinessValue": _int(epic.metadata.get("wsjf_ubv")),
        "timeCriticality": _int(epic.metadata.get("wsjf_tc")),
        "confidence": _int(epic.metadata.get("wsjf_confidence")),
        "wsjf": epic.metadata.get("wsjf"),
    }


def start(
    graph: Graph,
    writer: Writer,
    epic_id: str,
    *,
    owner: str | None,
    reclaim: bool,
) -> dict:
    """Judge whether an Epic may be elaborated now and, when it may, mark it in progress.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the write instead.
        epic_id: The Epic.
        owner: The caller's owner token, or None for a fresh one.
        reclaim: The caller established that the run owning an `in_progress` Epic is not
            live.

    Returns:
        `ok` with the Epic's inherited values and the owner token, or a named refusal.
    """
    epic = graph.beads.get(epic_id)
    if epic is None or epic.kind != "epic" or epic.closed:
        return _refusal(
            "not-an-open-epic",
            f"{epic_id} is not an open Epic in this tracker",
            epic,
        )
    state = epic.metadata.get(STATE_KEY) or None
    recorded = epic.metadata.get(OWNER_KEY) or None
    warnings = []
    if state == DONE:
        return _refusal(
            "epic-done",
            f"{epic_id} is {STATE_KEY}={DONE}: its Tasks are written and they are the "
            f"workable items. A person sets {STATE_KEY}={IN_PROGRESS} to elaborate it again, "
            "which resumes from its persisted artifacts",
            epic,
        )
    if state is not None and state not in (READY, IN_PROGRESS):
        warnings.append(
            f"{epic_id} carries {STATE_KEY}={state}, which is not a lifecycle state; "
            f"taken as {READY}"
        )
        state = READY
    if state == IN_PROGRESS and recorded and recorded != owner and not reclaim:
        return _refusal(
            "epic-owned",
            f"{epic_id} is {IN_PROGRESS} under run {recorded}, "
            f"since {epic.metadata.get(STATE_AT_KEY) or 'an unrecorded time'}. When that "
            "run is not live, start again with reclaim",
            epic,
            owner=recorded,
        )
    resumed = recorded if state == IN_PROGRESS and not reclaim else None
    token = owner or resumed or uuid.uuid4().hex
    writer.metadata(
        epic.id,
        {
            STATE_KEY: IN_PROGRESS,
            STATE_AT_KEY: now_iso(),
            CAUSE_KEY: CAUSE_STARTED,
            OWNER_KEY: token,
        },
    )
    return {
        "ok": True,
        "refusal": None,
        "epic": _epic_value(epic),
        "owner": token,
        "previousState": state,
        "warnings": warnings,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {"ok": True, "epic": epic.id, "previousState": state},
    }


def _task_ids_under(graph: Graph, epic: Bead) -> set[str]:
    """Every Task beneath an Epic, at any depth.

    Args:
        graph: The tracker graph.
        epic: The Epic.

    Returns:
        The Task ids.
    """
    return {b.id for b in graph.descendants(epic.id) if b.kind == "task"}


def finish(
    graph: Graph,
    writer: Writer,
    epic_id: str,
    *,
    owner: str | None,
    done: bool,
    scope: str = "epic-and-tasks",
) -> dict:
    """Score this Epic and its Tasks, and mark it done.

    Args:
        graph: The tracker graph, read with descriptions.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        owner: The owner token `start` returned.
        done: Set the Epic's `elaboration_state` to `done`.

    Returns:
        The scoring result and the lifecycle write.

    Raises:
        LifecycleError: The Epic is owned by another run.
    """
    epic = graph.beads[epic_id]
    recorded = epic.metadata.get(OWNER_KEY) or None
    if recorded and owner and recorded != owner:
        msg = f"{epic_id} is owned by run {recorded}, not {owner}"
        raise LifecycleError(msg)
    under = _task_ids_under(graph, epic)
    if scope not in {"epic-and-tasks", "epic-tasks"}:
        raise ValueError(f"unknown finish scope: {scope}")
    task_only = scope == "epic-tasks"
    finishing = done
    scored = score(
        graph,
        writer,
        scope=under if task_only else {epic.id} | under,
        rollup={epic.id} if finishing and not task_only else frozenset(),
    )
    if task_only:
        scored["unscored"] = [row for row in scored["unscored"] if row["id"] in under]
        scored["summary"]["unscored"] = len(scored["unscored"])
        finishing = finishing and bool(under) and not scored["unscored"]
    lifecycle = None
    if finishing:
        lifecycle = {
            STATE_KEY: DONE,
            STATE_AT_KEY: now_iso(),
            CAUSE_KEY: CAUSE_DECOMPOSED,
            OWNER_KEY: "",
        }
        writer.metadata(epic.id, lifecycle)
    return {
        "ok": True,
        "epic": epic.id,
        "score": {
            key: scored[key]
            for key in (
                "epics",
                "tasks",
                "unscored",
                "incomplete",
                "sizeFaults",
                "outsideRange",
                "cycles",
            )
        },
        "lifecycle": lifecycle,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "ok": True,
            "epic": epic.id,
            "epicsWritten": scored["summary"]["epicsWritten"],
            "tasksScored": scored["summary"]["tasksScored"],
            "tasksWritten": scored["summary"]["tasksWritten"],
            "unscored": scored["summary"]["unscored"],
            "done": lifecycle is not None,
        },
    }


def release(graph: Graph, writer: Writer, epic_id: str, *, owner: str) -> dict:
    """Clear a run's owner token from an Epic it started and did not finish.

    The Epic stays `in_progress`. A token that is not this run's is left alone.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the write instead.
        epic_id: The Epic.
        owner: The owner token `start` returned.

    Returns:
        Whether the token was cleared.
    """
    epic = graph.beads[epic_id]
    recorded = epic.metadata.get(OWNER_KEY) or None
    released = recorded == owner
    if released:
        writer.metadata(epic.id, {OWNER_KEY: ""})
    return {
        "ok": True,
        "epic": epic.id,
        "released": released,
        "owner": recorded,
        "state": epic.metadata.get(STATE_KEY) or None,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {"ok": True, "epic": epic.id, "released": released},
    }
