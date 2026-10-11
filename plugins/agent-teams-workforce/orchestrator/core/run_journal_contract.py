"""Workflow run journal: the one definition of the RUN-JOURNAL log-line contract.

A composite workflow (bug-fix, task-to-deploy, prd-to-spec) writes its run journal into the
harness workflow record's ``logs`` array as ``RUN-JOURNAL <json>`` or, for a body longer than
:data:`JOURNAL_CHUNK` characters, as ``RUN-JOURNAL-PART <i>/<n> <chunk>`` lines. The driver
(``ops/sdlc-automation/runjournal.py`` through ``runjournalcontract.py``) loads this module by
path from the installed plugin, reassembles the body, validates it with :func:`parse_payload`
and persists it as ``.claude/workflow-runs/<runId>.jsonl`` with the envelope built by
:func:`journal_envelope`.

This module imports only the standard library so the driver loads it without the orchestrator
package. Every prefix, key, allowed value and bound of the contract is defined here.
"""

import json
import re
import time
from collections.abc import Mapping, Sequence
from typing import Final, Literal, NotRequired, TypedDict, TypeIs

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type Composite = Literal["bug-fix", "task-to-deploy", "prd-to-spec"]
type PhaseStatus = Literal["running", "done", "failed"]

COMPOSITES: Final[tuple[Composite, ...]] = ("bug-fix", "task-to-deploy", "prd-to-spec")
PHASE_STATUSES: Final[tuple[PhaseStatus, ...]] = ("running", "done", "failed")
RUNNING_STATUS: Final[PhaseStatus] = "running"
RECORDED_STATUS: Final = "recorded"
"""The status a reader writes in place of a trailing ``running`` phase."""

JOURNAL_PREFIX: Final = "RUN-JOURNAL "
PART_PREFIX: Final = "RUN-JOURNAL-PART "
PART_PATTERN: Final[re.Pattern[str]] = re.compile(r"^RUN-JOURNAL-PART (\d+)/(\d+) ")
JOURNAL_CHUNK: Final = 4000
"""Largest JSON body, in UTF-16 code units, carried on one log line."""
TRUNCATION_MARKER: Final = "characters truncated]"
"""The text the harness leaves in a log line it truncated."""

OUTCOME_OK: Final = "ok"
OUTCOME_FAILED_PREFIX: Final = "failed:"
OUTCOME_UNKNOWN_STAGE: Final = "unknown"
DECISION_LIMIT: Final = 1200

WRITTEN_BY: Final = "host:runjournal"
RUN_DETAIL_KIND: Final = "run-detail"
TIMESTAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
JOURNAL_SUFFIX: Final = ".jsonl"
_UNSAFE_ID: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9_.-]+")


class JournalBead(TypedDict):
    """The bead a journal is about; either field may be unknown."""

    id: str | None
    title: str | None


class PhaseFailure(TypedDict):
    """Why a prd-to-spec phase failed."""

    stage: str
    reason: str


class RunPhase(TypedDict):
    """One prd-to-spec phase as the run block records it."""

    seq: int
    name: str
    status: PhaseStatus
    decision: str | None
    artifacts: list[str]
    failure: PhaseFailure | None
    skipReason: str | None


class RunBlock(TypedDict):
    """The prd-to-spec run block: the phases expected and the phases reached."""

    expectedPhases: list[str]
    phases: list[RunPhase]


class RunJournalPayload(TypedDict):
    """The JSON object a RUN-JOURNAL line carries."""

    composite: Composite
    bead: JournalBead | None
    outcome: str
    detail: JsonValue
    subject: NotRequired[str | None]
    runLedger: NotRequired[list[dict[str, JsonValue]]]
    carriedFlags: NotRequired[list[JsonValue]]
    run: NotRequired[RunBlock]


class JournalEnvelope(TypedDict):
    """The keys the host adds to every line of a persisted journal file."""

    runId: str
    composite: str
    beadId: str | None
    outcome: str | None
    ts: str
    writtenBy: Literal["host:runjournal"]


class RunJournalError(ValueError):
    """A RUN-JOURNAL payload does not conform to the contract."""


def failed_outcome(stage: str | None) -> str:
    """Return the outcome of a run that failed in ``stage``.

    Args:
        stage: The stage the composite result names, or None when it names none.

    Returns:
        ``failed:<stage>``, or ``failed:unknown`` when the stage is missing or blank.

    """
    named: str = stage.strip() if isinstance(stage, str) else ""
    return OUTCOME_FAILED_PREFIX + (named or OUTCOME_UNKNOWN_STAGE)


def is_outcome(value: object) -> TypeIs[str]:
    """Tell whether ``value`` is an allowed outcome.

    Args:
        value: The candidate value.

    Returns:
        True for ``ok`` or ``failed:<non-empty stage>``.

    """
    if not isinstance(value, str):
        return False
    return value == OUTCOME_OK or (value.startswith(OUTCOME_FAILED_PREFIX) and len(value) > len(OUTCOME_FAILED_PREFIX))


def journal_bodies(logs: Sequence[object]) -> list[str]:
    """Reassemble every complete journal body from a workflow record's log lines.

    Args:
        logs: The record's decoded ``logs`` array in order. A harness record may hold
            non-string entries; they carry no journal and are skipped.

    Returns:
        The JSON bodies in order. A chunked body that is incomplete or out of order is dropped.

    Raises:
        TypeError: ``logs`` is a string rather than a sequence of lines.

    """
    if isinstance(logs, str):
        message: str = "run journal: logs must be a sequence of lines, not a str"
        raise TypeError(message)
    bodies: list[str] = []
    parts: list[str] = []
    for line in logs:
        if not isinstance(line, str):
            continue
        if line.startswith(JOURNAL_PREFIX):
            bodies.append(line[len(JOURNAL_PREFIX) :])
            continue
        match: re.Match[str] | None = PART_PATTERN.match(line)
        if match is None:
            continue
        index: int = int(match.group(1))
        total: int = int(match.group(2))
        if index == 1:
            parts = []
        if index != len(parts) + 1:
            parts = []
            continue
        parts.append(line[match.end() :])
        if index == total:
            bodies.append("".join(parts))
            parts = []
    return bodies


def _text_or_none(value: object, where: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    message: str = f"run journal: {where} must be a string or null"
    raise RunJournalError(message)


def _texts(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        message: str = f"run journal: {where} must be a list of strings"
        raise RunJournalError(message)
    return [item for item in value if isinstance(item, str)]


def _is_json(value: object) -> TypeIs[JsonValue]:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(_is_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json(item) for key, item in value.items())
    return False


def _json_object(value: object, where: str) -> dict[str, JsonValue]:
    message: str = f"run journal: {where} must be a JSON object"
    if not isinstance(value, dict):
        raise RunJournalError(message)
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not _is_json(item):
            raise RunJournalError(message)
        result[key] = item
    return result


def _json_list(value: object, where: str) -> list[JsonValue]:
    message: str = f"run journal: {where} must be a list of JSON values"
    if not isinstance(value, list):
        raise RunJournalError(message)
    result: list[JsonValue] = []
    for item in value:
        if not _is_json(item):
            raise RunJournalError(message)
        result.append(item)
    return result


def _bead(value: object) -> JournalBead | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        message: str = "run journal: bead must be an object or null"
        raise RunJournalError(message)
    return {"id": _text_or_none(value.get("id"), "bead.id"), "title": _text_or_none(value.get("title"), "bead.title")}


def _phase(value: object, where: str) -> RunPhase:
    if not isinstance(value, dict):
        message: str = f"run journal: {where} must be an object"
        raise RunJournalError(message)
    seq: object = value.get("seq")
    name: object = value.get("name")
    status: object = value.get("status")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
        message = f"run journal: {where}.seq must be an integer >= 1"
        raise RunJournalError(message)
    if not isinstance(name, str):
        message = f"run journal: {where}.name must be a string"
        raise RunJournalError(message)
    if status not in PHASE_STATUSES or not isinstance(status, str):
        message = f"run journal: {where}.status must be one of {PHASE_STATUSES}"
        raise RunJournalError(message)
    decision: str | None = _text_or_none(value.get("decision"), f"{where}.decision")
    if decision is not None and len(decision) > DECISION_LIMIT:
        message = f"run journal: {where}.decision exceeds {DECISION_LIMIT} characters"
        raise RunJournalError(message)
    raw_failure: object = value.get("failure")
    failure: PhaseFailure | None = None
    if raw_failure is not None:
        if not isinstance(raw_failure, dict):
            message = f"run journal: {where}.failure must be an object or null"
            raise RunJournalError(message)
        stage: object = raw_failure.get("stage")
        reason: object = raw_failure.get("reason")
        if not isinstance(stage, str) or not isinstance(reason, str):
            message = f"run journal: {where}.failure needs string stage and reason"
            raise RunJournalError(message)
        failure = {"stage": stage, "reason": reason}
    checked_status: PhaseStatus = next(item for item in PHASE_STATUSES if item == status)
    return {
        "seq": seq,
        "name": name,
        "status": checked_status,
        "decision": decision,
        "artifacts": _texts(value.get("artifacts"), f"{where}.artifacts"),
        "failure": failure,
        "skipReason": _text_or_none(value.get("skipReason"), f"{where}.skipReason"),
    }


def _run_block(value: object) -> RunBlock:
    if not isinstance(value, dict):
        message: str = "run journal: run must be an object"
        raise RunJournalError(message)
    phases: object = value.get("phases")
    if not isinstance(phases, list):
        message = "run journal: run.phases must be a list"
        raise RunJournalError(message)
    return {
        "expectedPhases": _texts(value.get("expectedPhases"), "run.expectedPhases"),
        "phases": [_phase(item, f"run.phases[{index}]") for index, item in enumerate(_json_list(phases, "run.phases"))],
    }


def parse_payload(value: object) -> RunJournalPayload:
    """Validate a decoded RUN-JOURNAL body and narrow it to the contract type.

    Args:
        value: The decoded JSON body.

    Returns:
        The validated payload.

    Raises:
        RunJournalError: The body does not conform; the message names the field.

    """
    if not isinstance(value, Mapping):
        message: str = "run journal: payload must be an object"
        raise RunJournalError(message)
    composite: object = value.get("composite")
    if composite not in COMPOSITES or not isinstance(composite, str):
        message = f"run journal: composite must be one of {COMPOSITES}"
        raise RunJournalError(message)
    outcome: object = value.get("outcome")
    if not is_outcome(outcome):
        message = "run journal: outcome must be 'ok' or 'failed:<stage>'"
        raise RunJournalError(message)
    if "bead" not in value or "detail" not in value:
        message = "run journal: bead and detail are required keys"
        raise RunJournalError(message)
    detail: object = value.get("detail")
    if not _is_json(detail):
        message = "run journal: detail must be a JSON value"
        raise RunJournalError(message)
    checked: Composite = next(item for item in COMPOSITES if item == composite)
    payload: RunJournalPayload = {
        "composite": checked,
        "bead": _bead(value.get("bead")),
        "outcome": outcome,
        "detail": detail,
    }
    _add_optional(value, payload)
    return payload


def _add_optional(value: Mapping[object, object], payload: RunJournalPayload) -> None:
    """Validate the optional payload keys present in ``value`` and copy them into ``payload``."""
    if "subject" in value:
        payload["subject"] = _text_or_none(value.get("subject"), "subject")
    if "runLedger" in value:
        entries: list[JsonValue] = _json_list(value.get("runLedger"), "runLedger")
        payload["runLedger"] = [_json_object(entry, f"runLedger[{index}]") for index, entry in enumerate(entries)]
    if "carriedFlags" in value:
        payload["carriedFlags"] = _json_list(value.get("carriedFlags"), "carriedFlags")
    if "run" in value:
        payload["run"] = _run_block(value.get("run"))


def decode_payload(body: str) -> RunJournalPayload:
    """Decode and validate one reassembled journal body.

    Args:
        body: The JSON text after the prefix.

    Returns:
        The validated payload.

    Raises:
        TypeError: ``body`` is not a string.
        RunJournalError: The body is not JSON, even with control characters allowed inside
            strings, or does not conform. The message says when the harness truncated the line.

    """
    if not isinstance(body, str):
        type_message: str = f"run journal: body is {type(body).__name__}, not str"
        raise TypeError(type_message)
    decoded: object
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        try:
            decoded = json.loads(body, strict=False)
        except json.JSONDecodeError as error:
            cause: str = (
                "the harness truncated this log line, so the payload is gone"
                if TRUNCATION_MARKER in body
                else f"malformed JSON: {error}"
            )
            message: str = f"run journal: body unreadable: {cause} ({len(body)} characters)"
            raise RunJournalError(message) from error
    return parse_payload(decoded)


def journal_run_id(composite: str, run_ref: str) -> str:
    """Return the persisted journal's run id.

    Args:
        composite: The composite short name.
        run_ref: The harness runId, or the workflow record's file stem.

    Returns:
        ``<composite>-<run_ref>`` with each run of unsafe characters replaced by ``-``.

    """
    return f"{_UNSAFE_ID.sub('-', composite)}-{_UNSAFE_ID.sub('-', run_ref)}"


def journal_timestamp(epoch_seconds: float) -> str:
    """Format a journal ``ts`` value.

    Args:
        epoch_seconds: Seconds since the epoch.

    Returns:
        The UTC time as ``YYYY-MM-DDTHH:MM:SSZ``.

    """
    return time.strftime(TIMESTAMP_FORMAT, time.gmtime(epoch_seconds))


def journal_envelope(payload: RunJournalPayload, run_ref: str, epoch_seconds: float) -> JournalEnvelope:
    """Build the envelope every persisted journal line carries.

    Args:
        payload: The validated payload.
        run_ref: The harness runId, or the workflow record's file stem.
        epoch_seconds: The run's start time.

    Returns:
        The envelope.

    """
    bead: JournalBead | None = payload["bead"]
    bead_id: str | None = (bead["id"] if bead is not None else None) or payload.get("subject")
    return {
        "runId": journal_run_id(payload["composite"], run_ref),
        "composite": payload["composite"],
        "beadId": bead_id,
        "outcome": payload["outcome"],
        "ts": journal_timestamp(epoch_seconds),
        "writtenBy": WRITTEN_BY,
    }


def journal_lines(payload: RunJournalPayload, envelope: JournalEnvelope, harness_record: str) -> list[str]:
    """Render the persisted journal file's lines.

    Args:
        payload: The validated payload.
        envelope: The envelope from :func:`journal_envelope`.
        harness_record: The path of the ``wf_*.json`` record the journal came from.

    Returns:
        One JSON line per runLedger entry, then the run-detail line.

    """
    envelope_json: dict[str, JsonValue] = {key: value for key, value in envelope.items() if _is_json(value)}
    ledger: list[dict[str, JsonValue]] = payload.get("runLedger", [])
    lines: list[str] = []
    for entry in ledger:
        merged: dict[str, JsonValue] = dict(entry)
        merged.update(envelope_json)
        lines.append(json.dumps(merged, sort_keys=True))
    run: RunBlock | None = payload.get("run")
    detail_line: dict[str, object] = {
        "kind": RUN_DETAIL_KIND,
        **envelope_json,
        "carriedFlags": payload.get("carriedFlags"),
        "run": run,
        "detail": payload["detail"],
        "harnessRecord": harness_record,
    }
    lines.append(json.dumps(detail_line, sort_keys=True))
    return lines
