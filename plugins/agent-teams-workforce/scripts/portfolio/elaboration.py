#!/usr/bin/env python3
"""The Epic elaboration lifecycle: whether an Epic may be elaborated now, and finishing it.

`prd-to-spec` is the one elaborator, and its one door, the driver's elaboration lane, arrives
here twice.

At the START, one Epic is judged, and the first condition that fails is the refusal:

* it is an open Epic;
* its `KEY_ELABORATION_STATE` is not `ELABORATION_PARKED`: a parked Epic waits for an owner or
  architecture decision (`KEY_ELABORATION_PARK` says which, and why), and only the owner unparks it;
* its `KEY_ELABORATION_STATE` is not `ELABORATION_DONE`: its Tasks are written and they are the workable items;
* it is not `ELABORATION_IN_PROGRESS` under another run's owner token (unless the caller reclaims).

Which Epic is elaborated next, and whether it is scored and its upstream Epics are elaborated,
is decided by keeper selection before any door arrives here, so it is not judged again. An
absent or unrecognised `KEY_ELABORATION_STATE` is taken as `ELABORATION_READY`, with a warning for the latter.

When the conditions hold, the Epic is marked `ELABORATION_IN_PROGRESS` and the run's owner token is
recorded on it as `KEY_ELABORATION_STATE_OWNER`. The token is the caller's, or a fresh one. An
`ELABORATION_IN_PROGRESS` Epic carrying a different token is owned by another run; the caller passes
`reclaim` only once it has established that run is not live.

At the FINISH, after the Tasks are written:

* `score_epic_tasks`, `prd-to-spec`'s score step, scores the Tasks beneath the Epic with value
  inherited from it and RR-OE counted over every Task edge, across Stories; the Epic's own score
  is the owner's `wsjf-scoring` run's;
* `record_buildability`, `prd-to-spec`'s buildability gate, records the gate's report on the Epic
  as `KEY_ELABORATION_BUILDABILITY`; a failed gate also sets the cause `CAUSE_BUILDABILITY` and the
  Epic stays `ELABORATION_IN_PROGRESS`;
* `mark_elaborated` sets the Epic's `KEY_ELABORATION_STATE` to `ELABORATION_DONE` with the cause
  `CAUSE_DECOMPOSED` and clears its owner token, scoring nothing again. Each Story of the Epic whose
  `KEY_RESPEC_STATE` is `RESPEC_RESTARTED` was written again in this elaboration, so its respec
  state and request are cleared; a Story still `RESPEC_REQUESTED` keeps its request, so the Epic is
  selected again. The Epic stays open; it closes only when its work is released.

A run that started an Epic and ends without setting its elaboration to `ELABORATION_DONE`
RELEASES it: its owner token is cleared and the Epic stays `ELABORATION_IN_PROGRESS`, so the
next run takes it up without a reclaim.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import beadgraph
from bead_metadata import (
    CAUSE_BUILDABILITY,
    CAUSE_DECOMPOSED,
    CAUSE_STARTED,
    ELABORATION_DONE,
    ELABORATION_IN_PROGRESS,
    ELABORATION_PARKED,
    ELABORATION_READY,
    KEY_ELABORATION_BUILDABILITY,
    KEY_ELABORATION_PARK,
    KEY_ELABORATION_STATE,
    KEY_ELABORATION_STATE_AT,
    KEY_ELABORATION_STATE_CAUSE,
    KEY_ELABORATION_STATE_OWNER,
    KEY_RESPEC_REQUESTED,
    KEY_RESPEC_STATE,
    KEY_RESPEC_STATE_AT,
    KEY_WSJF,
    KEY_WSJF_CONFIDENCE,
    KEY_WSJF_TC,
    KEY_WSJF_UBV,
    RESPEC_NONE,
    RESPEC_RESTARTED,
)
from beadgraph import Bead, Graph, Writer, now_iso
from contracts import JsonValue
from elaborationcontracts import EpicValue, Refusal, Refused, Released, Started
from scoring import score_tasks
from scoringcontracts import TaskScores
from typeguard import CollectionCheckStrategy, typechecked

#: The Epic's elaboration lifecycle and its companions.
_ARGUMENT_ERROR: str = "Arguments violate the elaboration input contract"


def _silent(_detail: str) -> None:
    """Take no notice of progress."""


class LifecycleError(RuntimeError):
    """The command cannot proceed and the caller must fix its input."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def _int(value: JsonValue) -> int | None:
    """Parse a metadata integer, returning None when it is absent or unusable.

    Args:
        value: The raw metadata value.

    Returns:
        The integer, or None when there is not one.

    """
    try:
        return int(float(str(value).strip()))
    except TypeError, ValueError:
        return None


def _refusal(code: str, reason: str, epic: Bead | None, *, owner: str | None = None) -> Refused:
    """Return a refusal to start elaboration, named by code.

    Args:
        code: The condition that failed.
        reason: What a person reads.
        epic: The Epic, when it exists.
        owner: The currently recorded owner token.

    Returns:
        The payload.

    """
    refusal: Refusal = {"code": code, "reason": reason}
    if owner is not None:
        refusal["owner"] = owner
    return {
        "ok": False,
        "refusal": refusal,
        "epic": {"id": epic.id, "title": epic.title} if epic else None,
        "summary": {"ok": False, "refusal": code},
    }


def _parked_reason(epic: Bead) -> str:
    """Say why a parked Epic is parked and who settles it, from its park record.

    Returns:
        The park record's cause and decision; what the record lacks is said to be unrecorded.

    """
    try:
        record: object = json.loads(epic.metadata.get(KEY_ELABORATION_PARK) or "{}")
    except ValueError:
        record = {}
    held: dict[str, object] = record if isinstance(record, dict) else {}
    cause: object = held.get("cause") or "an unrecorded cause"
    decision: object = held.get("decision") or "an unrecorded"
    return f"cause {cause}, waiting for {decision} decision"


def _epic_value(epic: Bead) -> EpicValue:
    """Return the Epic's scored values, as a Task inherits them.

    Args:
        epic: The Epic.

    Returns:
        Its id, title, value, criticality and value confidence.

    """
    return {
        "id": epic.id,
        "title": epic.title,
        "userBusinessValue": _int(epic.metadata.get(KEY_WSJF_UBV)),
        "timeCriticality": _int(epic.metadata.get(KEY_WSJF_TC)),
        "confidence": _int(epic.metadata.get(KEY_WSJF_CONFIDENCE)),
        "wsjf": epic.metadata.get(KEY_WSJF),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def start(
    graph: Graph,
    writer: Writer,
    epic_id: str,
    *,
    owner: str | None,
    reclaim: bool,
) -> Started | Refused:
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(graph, Graph))
        or not (isinstance(writer, Writer))
        or not (isinstance(epic_id, str))
        or not (isinstance(owner, str) or owner is None)
        or not (isinstance(reclaim, bool))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    epic: beadgraph.Bead | None = graph.beads.get(epic_id)
    if epic is None or epic.kind != "epic" or epic.closed:
        return _refusal(
            "not-an-open-epic",
            f"{epic_id} is not an open Epic in this tracker",
            epic,
        )
    state: str | None = epic.metadata.get(KEY_ELABORATION_STATE) or None
    recorded: str | None = epic.metadata.get(KEY_ELABORATION_STATE_OWNER) or None
    warnings: list[str] = []
    if state == ELABORATION_PARKED:
        return _refusal(
            "epic-parked",
            f"{epic_id} is parked: {_parked_reason(epic)}; the owner unparks it",
            epic,
        )
    if state == ELABORATION_DONE:
        return _refusal(
            "epic-done",
            f"{epic_id} is {KEY_ELABORATION_STATE}={ELABORATION_DONE}: its Tasks are written and they are the "
            f"workable items. A person sets {KEY_ELABORATION_STATE}={ELABORATION_IN_PROGRESS} to elaborate it again, "
            "which resumes from its persisted artifacts",
            epic,
        )
    if state is not None and state not in {ELABORATION_READY, ELABORATION_IN_PROGRESS}:
        warnings.append(
            f"{epic_id} carries {KEY_ELABORATION_STATE}={state}, which is not a lifecycle state; "
            f"taken as {ELABORATION_READY}",
        )
        state = ELABORATION_READY
    if state == ELABORATION_IN_PROGRESS and recorded and recorded != owner and not reclaim:
        return _refusal(
            "epic-owned",
            f"{epic_id} is {ELABORATION_IN_PROGRESS} under run {recorded}, "
            f"since {epic.metadata.get(KEY_ELABORATION_STATE_AT) or 'an unrecorded time'}. When that "
            "run is not live, start again with reclaim",
            epic,
            owner=recorded,
        )
    resumed: str | None = recorded if state == ELABORATION_IN_PROGRESS and not reclaim else None
    token: str = owner or resumed or uuid.uuid4().hex
    writer.metadata(
        epic.id,
        {
            KEY_ELABORATION_STATE: ELABORATION_IN_PROGRESS,
            KEY_ELABORATION_STATE_AT: now_iso(),
            KEY_ELABORATION_STATE_CAUSE: CAUSE_STARTED,
            KEY_ELABORATION_STATE_OWNER: token,
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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def score_epic_tasks(
    graph: Graph,
    writer: Writer,
    epic_id: str,
    *,
    owner: str | None,
    progress: Callable[[str], None] = _silent,
) -> TaskScores:
    """Score the Tasks of this Epic; the Epic itself is not scored here.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        owner: The run's owner token.
        progress: Told as each stage ends.

    Returns:
        The scoring result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(graph, Graph)) or not (isinstance(writer, Writer)) or not (isinstance(epic_id, str)):
        raise TypeError(_ARGUMENT_ERROR)
    epic: Bead = graph.beads[epic_id]
    _check_owner(epic, owner)
    return score_tasks(graph, writer, {b.id for b in graph.descendants(epic.id) if b.kind == "task"}, progress)


def _check_owner(epic: Bead, owner: str | None) -> None:
    """Refuse an Epic whose recorded owner token is another run's.

    Raises:
        LifecycleError: The Epic is owned by another run.

    """
    recorded: str | None = epic.metadata.get(KEY_ELABORATION_STATE_OWNER) or None
    if recorded and owner and recorded != owner:
        msg: str = f"{epic.id} is owned by run {recorded}, not {owner}"
        raise LifecycleError(msg)


def _write_done(writer: Writer, epic_id: str) -> dict[str, str]:
    """Set the Epic's elaboration to done, with the decomposed cause, and clear its owner token.

    Returns:
        The lifecycle metadata written.

    """
    lifecycle: dict[str, str] = {
        KEY_ELABORATION_STATE: ELABORATION_DONE,
        KEY_ELABORATION_STATE_AT: now_iso(),
        KEY_ELABORATION_STATE_CAUSE: CAUSE_DECOMPOSED,
        KEY_ELABORATION_STATE_OWNER: "",
    }
    writer.metadata(epic_id, lifecycle)
    return lifecycle


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_buildability(
    graph: Graph,
    writer: Writer,
    epic_id: str,
    *,
    owner: str | None,
    report: str,
) -> dict[str, str]:
    """Record the buildability gate's report on the Epic; a failed gate also sets its cause.

    The Epic's state is not changed: a failed gate leaves it `ELABORATION_IN_PROGRESS` with the
    cause `CAUSE_BUILDABILITY`, so the report's defects are where the next run can act on them.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the write instead.
        epic_id: The Epic.
        owner: The run's owner token.
        report: The gate's report (``BuildabilityReport``), as JSON; a report whose ``buildable``
            is not true is a failed gate.

    Returns:
        The metadata written.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(graph, Graph)) or not (isinstance(writer, Writer)) or not (isinstance(epic_id, str)):
        raise TypeError(_ARGUMENT_ERROR)
    _check_owner(graph.beads[epic_id], owner)
    written: dict[str, str] = {KEY_ELABORATION_BUILDABILITY: report}
    parsed: object = json.loads(report)
    if not isinstance(parsed, dict) or parsed.get("buildable") is not True:
        written |= {KEY_ELABORATION_STATE_CAUSE: CAUSE_BUILDABILITY, KEY_ELABORATION_STATE_AT: now_iso()}
    writer.metadata(epic_id, written)
    return written


def _clear_restarted(graph: Graph, writer: Writer, epic_id: str) -> list[str]:
    """Clear the respec state and request of each Story of the Epic whose specs and Tasks were restarted.

    Returns:
        The Stories cleared, in id order.

    """
    cleared: list[str] = []
    for story in graph.descendants(epic_id):
        if story.kind != "story" or story.metadata.get(KEY_RESPEC_STATE) != RESPEC_RESTARTED:
            continue
        writer.metadata(
            story.id,
            {KEY_RESPEC_STATE: RESPEC_NONE, KEY_RESPEC_REQUESTED: "", KEY_RESPEC_STATE_AT: now_iso()},
        )
        cleared.append(story.id)
    return cleared


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def mark_elaborated(graph: Graph, writer: Writer, epic_id: str, *, owner: str | None) -> dict[str, str]:
    """Mark the Epic elaborated without scoring it again.

    The pipeline's score step has scored the Epic's Tasks, its buildability gate has checked
    that they can be built, and its done rule has checked that every repository has its Story and
    Tasks and that no Task is unscored, so this only writes the lifecycle. Each Story whose
    respec state is `RESPEC_RESTARTED` was written again in this elaboration: its respec state,
    request and time are cleared. A Story still `RESPEC_REQUESTED` keeps its request.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        owner: The run's owner token.

    Returns:
        The lifecycle metadata written.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(graph, Graph)) or not (isinstance(writer, Writer)) or not (isinstance(epic_id, str)):
        raise TypeError(_ARGUMENT_ERROR)
    _check_owner(graph.beads[epic_id], owner)
    done: dict[str, str] = _write_done(writer, epic_id)
    _clear_restarted(graph, writer, epic_id)
    return done


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def release(graph: Graph, writer: Writer, epic_id: str, *, owner: str) -> Released:
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
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(graph, Graph))
        or not (isinstance(writer, Writer))
        or not (isinstance(epic_id, str))
        or not (isinstance(owner, str))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    epic: beadgraph.Bead = graph.beads[epic_id]
    recorded: str | None = epic.metadata.get(KEY_ELABORATION_STATE_OWNER) or None
    released: bool = recorded == owner
    if released:
        writer.metadata(epic.id, {KEY_ELABORATION_STATE_OWNER: ""})
    return {
        "ok": True,
        "epic": epic.id,
        "released": released,
        "owner": recorded,
        "state": epic.metadata.get(KEY_ELABORATION_STATE) or None,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {"ok": True, "epic": epic.id, "released": released},
    }
