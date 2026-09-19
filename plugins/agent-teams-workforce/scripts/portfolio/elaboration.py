#!/usr/bin/env python3
"""The Epic elaboration lifecycle: whether an Epic may be elaborated now, and finishing it.

`prd-to-spec` is the one elaborator, and every door into it — the headless lane, a person at
`/work-bead` or `/start-prd` — arrives here twice.

At the START, one Epic is judged against four conditions, in this order, and the first that
fails is the refusal:

* it is an open Epic;
* it is SCORED: it carries its judged User-Business Value and Time Criticality and its
  computed `wsjf`, because every Task it produces inherits the first two and an Epic's score
  is what orders elaboration;
* every Epic it depends on has `elaboration_state = done` or is closed, because an Epic
  edge is an architecture dependency: an architecture decision this Epic rests on is designed from
  the requirements of the Epics it depends on first. Its
  dependencies are its `tracks` edges, and its `blocks` edges too, so an Epic edge stored
  as either type holds it; a `blocks` edge onto anything other than an Epic holds it until
  that bead closes;
* its own `elaboration_state` is `ready`, or `in_progress` with no other owner. An absent
  state is a PRD still being authored and `done` is an Epic whose Tasks are the workable
  items.

When all four hold, the Epic is marked `in_progress` and the run's owner token is recorded
on it as `elaboration_state_owner`. The token is the caller's, or a fresh one. An
`in_progress` Epic carrying a different token is owned by another run; the caller passes
`reclaim` only once it has established that run is not live.

At the FINISH, after the Tasks are written:

* each Task whose size this run judged from the content it now carries gets that content's
  fingerprint as `wsjf_content_hash`, so the scoring pass reads the size as current;
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

from beadgraph import fingerprints, now_iso
from scoring import JUDGED_HASH_KEY, SIZE_JUDGED_KEYS, score

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

#: The judged Epic values a Task inherits, and the computed score that orders elaboration.
SCORE_KEYS = ("wsjf_ubv", "wsjf_tc", "wsjf")


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
    unscored = [k for k in SCORE_KEYS if epic.metadata.get(k) in (None, "")]
    if unscored:
        return _refusal(
            "epic-unscored",
            f"{epic_id} carries no {', '.join(unscored)}: an Epic is scored before it is "
            "elaborated, because its Tasks inherit its value and its score orders "
            "elaboration. Run dependency assessment and WSJF scoring for it first",
            epic,
            missing=unscored,
        )
    waiting = []
    for upstream in sorted(set(epic.tracked) | set(epic.blockers)):
        bead = graph.beads.get(upstream)
        state = bead.metadata.get(STATE_KEY) if bead else None
        if bead is None:
            satisfied = False
        elif bead.kind == "epic":
            satisfied = bead.closed or state == DONE
        else:
            satisfied = bead.closed
        if not satisfied:
            waiting.append(
                {
                    "id": upstream,
                    "title": bead.title if bead else None,
                    "elaborationState": state,
                }
            )
    if waiting:
        return _refusal(
            "upstream-not-elaborated",
            f"{epic_id} depends on {len(waiting)} item(s) not yet satisfied: "
            + ", ".join(
                f"{w['id']} ({w['elaborationState'] or 'no state'})" for w in waiting
            )
            + ". An Epic's architecture is designed after the architecture of the Epics "
            "it depends on",
            epic,
            upstream=waiting,
        )
    state = epic.metadata.get(STATE_KEY) or None
    recorded = epic.metadata.get(OWNER_KEY) or None
    if state is None:
        return _refusal(
            "epic-authoring",
            f"{epic_id} carries no {STATE_KEY}, which is how an Epic whose PRD is still being "
            f"authored looks. Set {STATE_KEY}={READY} when authoring is finished",
            epic,
        )
    if state == DONE:
        return _refusal(
            "epic-done",
            f"{epic_id} is {STATE_KEY}={DONE}: its Tasks are written and they are the "
            f"workable items. A person sets {STATE_KEY}={READY} to elaborate it again",
            epic,
        )
    if state not in (READY, IN_PROGRESS):
        return _refusal(
            "epic-state-unknown",
            f"{epic_id} carries {STATE_KEY}={state}, which is not a lifecycle state",
            epic,
        )
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
    judged: list[str],
    owner: str | None,
    done: bool,
) -> dict:
    """Fingerprint the judged Task sizes, score this Epic and its Tasks, and mark it done.

    Args:
        graph: The tracker graph, read with descriptions.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        judged: The Tasks whose size this run judged from the content they now carry.
        owner: The owner token `start` returned.
        done: Set the Epic's `elaboration_state` to `done`.

    Returns:
        The fingerprints written, the scoring result, and the lifecycle write.

    Raises:
        LifecycleError: The Epic is not an open Epic, a judged id is not a Task beneath
            it or carries no judged size, or the Epic is owned by another run.
    """
    epic = graph.beads.get(epic_id)
    if epic is None or epic.kind != "epic" or epic.closed:
        msg = f"{epic_id} is not an open Epic in this tracker"
        raise LifecycleError(msg)
    recorded = epic.metadata.get(OWNER_KEY) or None
    if recorded and owner and recorded != owner:
        msg = f"{epic_id} is owned by run {recorded}, not {owner}"
        raise LifecycleError(msg)
    under = _task_ids_under(graph, epic)
    stray = sorted(set(judged) - under)
    if stray:
        msg = f"not Tasks beneath {epic_id}: {', '.join(stray)}"
        raise LifecycleError(msg)
    unsized = sorted(
        t
        for t in judged
        if any(graph.beads[t].metadata.get(k) in (None, "") for k in SIZE_JUDGED_KEYS)
    )
    if unsized:
        msg = f"judged Tasks carrying no judged size: {', '.join(unsized)}"
        raise LifecycleError(msg)
    prints = fingerprints(graph.records)
    stamped = []
    for task_id in sorted(set(judged)):
        current = prints.get(task_id, "")
        if current and graph.beads[task_id].metadata.get(JUDGED_HASH_KEY) != current:
            writer.metadata(task_id, {JUDGED_HASH_KEY: current})
            stamped.append(task_id)
    scored = score(graph, writer, scope={epic.id} | under)
    lifecycle = None
    if done:
        if not under:
            msg = f"{epic_id} has no Tasks beneath it, so its elaboration is not done"
            raise LifecycleError(msg)
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
        "fingerprinted": stamped,
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
            "fingerprinted": len(stamped),
            "epicsWritten": scored["summary"]["epicsWritten"],
            "tasksScored": scored["summary"]["tasksScored"],
            "tasksWritten": scored["summary"]["tasksWritten"],
            "unscored": scored["summary"]["unscored"],
            "done": done,
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

    Raises:
        LifecycleError: The Epic is not in this tracker.
    """
    epic = graph.beads.get(epic_id)
    if epic is None or epic.kind != "epic":
        msg = f"{epic_id} is not an Epic in this tracker"
        raise LifecycleError(msg)
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
