"""Orchestrator handback v1: the one definition of the orchestrator-to-driver result document.

``orchestrator/run.py`` writes one document per dispatch to the ``--handback`` path. The driver
(``ops/sdlc-automation`` in the control repository) loads this file by path from the installed
plugin and validates every document with :func:`validate`. Driver-made failures are built with
:func:`failure`, :func:`interrupted_failure` and :func:`rejected` so they have the same shape.

This module imports only the standard library, so the driver loads it without the orchestrator
package. Every field, allowed value and rule of the contract is defined here and nowhere else.

Rules beyond the field types:

- ``failure.classification`` is always present. ``interrupted`` is used exactly when the item
  stopped because of an owner stop-execution of that item, a SIGTERM to it, or a supervisor
  shutdown or drain. An interrupted failure has cause ``shutdown`` and stage ``interrupted``
  (owner stop-execution or SIGTERM of that one item) or ``shutdown`` (supervisor shutdown or
  drain); a failure with either stop stage is classified ``interrupted``. A document whose
  ``stage`` is a stop stage carries an interrupted failure. A session-cleanup error raised while
  stopping is ``pipeline-code-defect``, not an interruption.
- ``beadsEmitted`` is not negative; every number is finite; integers are never booleans.
- ``artifacts.phases`` keys are ``trd`` or ``spec:<repository slug>``.
"""

import json
import math
import re
import traceback
import types
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import (
    Final,
    Literal,
    NoReturn,
    NotRequired,
    TypeAliasType,
    TypedDict,
    TypeIs,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type PhaseStatus = Literal["passed", "reused"]
type FailureClass = Literal["setup", "transient", "item", "pipeline-code-defect", "interrupted"]
type StopStage = Literal["interrupted", "shutdown"]

VERSION: Final = 1

SETUP_CLASS: Final[FailureClass] = "setup"
"""The run could not be configured or launched; new dispatch stops."""
TRANSIENT_CLASS: Final[FailureClass] = "transient"
"""A failure expected to clear with time (API, quota, contention, network)."""
ITEM_CLASS: Final[FailureClass] = "item"
"""A failure of this item's work; other items continue."""
DEFECT_CLASS: Final[FailureClass] = "pipeline-code-defect"
"""A defect in pipeline code; new dispatch stops."""
INTERRUPTED_CLASS: Final[FailureClass] = "interrupted"
"""An owner stop-execution, SIGTERM or supervisor shutdown; never a failure of the item."""

FAILURE_CLASSES: Final[frozenset[FailureClass]] = frozenset(get_args(FailureClass.__value__))
FATAL_CLASSES: Final[frozenset[FailureClass]] = frozenset({SETUP_CLASS, DEFECT_CLASS})
"""Classifications that stop new dispatch and drain current steps."""
CLASS_ORDER: Final[tuple[FailureClass, ...]] = (
    ITEM_CLASS,
    TRANSIENT_CLASS,
    SETUP_CLASS,
    DEFECT_CLASS,
    INTERRUPTED_CLASS,
)
"""Ascending severity: the primary error among concurrent failures is the last in this order."""

INTERRUPTED_STAGE: Final[StopStage] = "interrupted"
"""Stage of an owner stop-execution or SIGTERM of one item."""
SHUTDOWN_STAGE: Final[StopStage] = "shutdown"
"""Stage of a supervisor shutdown or drain."""
STOP_STAGES: Final[frozenset[StopStage]] = frozenset(get_args(StopStage.__value__))
VALIDATION_STAGE: Final = "handback-validation"
"""Stage of a replacement document when the rejected document named no usable stage."""

SHUTDOWN_CAUSE: Final = "shutdown"
OTHER_CAUSE: Final = "other"
API_CAUSE: Final = "api"
QUOTA_CAUSE: Final = "quota"
BD_TIMEOUT_CAUSE: Final = "bd-timeout"
CONTENTION_CAUSE: Final = "contention"
TIMEOUT_CAUSE: Final = "timeout"
TOOL_TIMEOUT_CAUSE: Final = "tool-timeout"
NETWORK_CAUSE: Final = "network"
ACCOUNT_CAUSES: Final[frozenset[str]] = frozenset({API_CAUSE, QUOTA_CAUSE})
"""Causes that come from the Anthropic account or API, not from the item."""
RETRYABLE_CAUSES: Final[tuple[str, ...]] = (QUOTA_CAUSE, API_CAUSE, BD_TIMEOUT_CAUSE, CONTENTION_CAUSE)
"""Causes retried after a backoff, in the precedence order used to combine several of them."""
TRANSIENT_CAUSES: Final[frozenset[str]] = frozenset({
    *RETRYABLE_CAUSES,
    TIMEOUT_CAUSE,
    TOOL_TIMEOUT_CAUSE,
    NETWORK_CAUSE,
})
"""Causes classified ``transient``."""

PHASE_STATUSES: Final[frozenset[PhaseStatus]] = frozenset(get_args(PhaseStatus.__value__))
PASSED_PHASE: Final[PhaseStatus] = "passed"
REUSED_PHASE: Final[PhaseStatus] = "reused"
TRD_PHASE: Final = "trd"
SPEC_PHASE_PREFIX: Final = "spec:"
PHASE_KEY: Final = re.compile(rf"^({TRD_PHASE}|{SPEC_PHASE_PREFIX}[a-zA-Z0-9._-]+)$")

type EventName = Literal["phase", "verdict", "session", "heartbeat", "note", "fable-wall"]
type SessionState = Literal["started", "ended"]
type NoteKind = Literal["reused", "rounds-warning", "invalidated", "integration-outside", "warning"]
type PrdToSpecPhase = Literal[
    "architecture",
    "trd-authoring",
    "repo-scoping",
    "spec-authoring",
    "task-decomposition",
    "task-edges",
    "finish",
]

EVENT_KEY: Final = "event"
"""The key every orchestrator stdout event line carries; its value is an ``EventName``."""
PHASE_EVENT: Final = "phase"
VERDICT_EVENT: Final = "verdict"
SESSION_EVENT: Final = "session"
HEARTBEAT_EVENT: Final = "heartbeat"
NOTE_EVENT: Final = "note"
FABLE_WALL_EVENT: Final = "fable-wall"
EVENT_NAMES: Final[frozenset[EventName]] = frozenset(get_args(EventName.__value__))

SESSION_STARTED: Final = "started"
SESSION_ENDED: Final = "ended"
SESSION_STATES: Final[frozenset[SessionState]] = frozenset(get_args(SessionState.__value__))

REUSED_NOTE: Final = "reused"
ROUNDS_WARNING_NOTE: Final = "rounds-warning"
INVALIDATED_NOTE: Final = "invalidated"
INTEGRATION_OUTSIDE_NOTE: Final = "integration-outside"
WARNING_NOTE: Final = "warning"
NOTE_KINDS: Final[frozenset[NoteKind]] = frozenset(get_args(NoteKind.__value__))

PRD_TO_SPEC_PHASES: Final[tuple[PrdToSpecPhase, ...]] = get_args(PrdToSpecPhase.__value__)
"""The prd-to-spec phases in run order; a ``phase`` event names one of them."""


class Location(TypedDict):
    """Source location of an exception, independent of its rendered traceback."""

    file: str
    line: int


class Diagnostic(TypedDict):
    """The original exception of a failure, kept beside its classification."""

    exceptionType: str
    message: str
    traceback: str
    location: Location
    agentStarted: bool


class RepositoryFailure(TypedDict):
    """One repository's failed phase and its original headline."""

    repository: str
    stage: str
    cause: str
    headline: str
    diagnostic: NotRequired[Diagnostic]
    classification: NotRequired[FailureClass]


class Failure(TypedDict):
    """Why a dispatch did not finish, with its original evidence."""

    stage: str
    cause: str
    classification: FailureClass
    repositories: list[RepositoryFailure]
    resumeAt: NotRequired[float]
    evidence: NotRequired[list[str]]
    unscored: NotRequired[list[JsonValue]]
    diagnostic: NotRequired[Diagnostic]
    handbackDefect: NotRequired[Diagnostic]
    originalFailure: NotRequired[JsonValue]
    interruptedStage: NotRequired[str]


class ArtifactReport(TypedDict):
    """Accepted documents to file; detailed phase results live in run.json."""

    dir: str
    epicId: str
    phases: dict[str, PhaseStatus]
    filing: dict[str, str]


class SessionIdentity(TypedDict):
    """Who and what one agent session is; shared by the session row and the session event."""

    sessionId: str
    cwd: str
    phase: str
    step: str
    agent: str
    model: str
    effort: str


class Session(SessionIdentity):
    """One agent session, written before launch and completed after it exits."""

    pid: NotRequired[int]
    pgid: NotRequired[int]
    startedAt: NotRequired[float]
    endedAt: NotRequired[float | None]
    exit: NotRequired[int | None]
    cause: NotRequired[str | None]


class Refusal(TypedDict):
    """A lifecycle refusal requiring explicit action before elaboration."""

    code: str
    reason: str
    owner: NotRequired[str]


class HandbackDocument(TypedDict):
    """The version one orchestrator-to-driver result."""

    version: Literal[1]
    ok: bool
    stage: str
    beadId: str
    headline: str
    detailPath: str
    sessions: list[Session]
    artifacts: NotRequired[ArtifactReport]
    failure: NotRequired[Failure]
    lifecycleDone: NotRequired[bool]
    beadsEmitted: NotRequired[int]
    requiredHumanActions: NotRequired[list[str]]
    refusal: NotRequired[Refusal]


class PhaseEvent(TypedDict):
    """A prd-to-spec phase or one of its steps started."""

    event: Literal["phase"]
    phase: PrdToSpecPhase
    step: str
    repository: NotRequired[str | None]


class VerdictEvent(TypedDict):
    """An accepted agent result carried a verdict; its vocabulary belongs to the agent result schemas."""

    event: Literal["verdict"]
    phase: str
    label: str
    verdict: str
    detail: str


class SessionEvent(SessionIdentity):
    """An agent session started or ended; ``exit`` and ``cause`` are present exactly on ``ended``."""

    event: Literal["session"]
    state: SessionState
    pid: int
    pgid: int
    exit: NotRequired[int | None]
    cause: NotRequired[str | None]


class HeartbeatEvent(TypedDict):
    """Progress only: the sessions that are streaming."""

    event: Literal["heartbeat"]
    live: list[str]
    at: float


class ReusedNote(TypedDict):
    """Saved work was reused; at least one of ``step`` and ``phase`` is present."""

    event: Literal["note"]
    kind: Literal["reused"]
    step: NotRequired[str]
    phase: NotRequired[str]
    repository: NotRequired[str | None]


class RoundsWarningNote(TypedDict):
    """Architecture review rounds are running long; ``drivers`` are the open findings."""

    event: Literal["note"]
    kind: Literal["rounds-warning"]
    phase: str
    rounds: int
    drivers: list[JsonValue]


class InvalidatedNote(TypedDict):
    """A saved step output was set aside and will be produced again."""

    event: Literal["note"]
    kind: Literal["invalidated"]
    step: str
    path: str


class IntegrationOutsideNote(TypedDict):
    """Architecture integration wrote files outside the allowed set."""

    event: Literal["note"]
    kind: Literal["integration-outside"]
    files: list[JsonValue]


class WarningNote(TypedDict):
    """A step finished, but a non-fatal problem in ``step`` is reported in ``detail``."""

    event: Literal["note"]
    kind: Literal["warning"]
    step: str
    detail: str


class FableWallEvent(TypedDict):
    """The Fable model hit its rate limit; ``resetsAt`` is epoch seconds or null."""

    event: Literal["fable-wall"]
    resetsAt: float | None
    window: str | None


type NoteEvent = ReusedNote | RoundsWarningNote | InvalidatedNote | IntegrationOutsideNote | WarningNote
type OrchestratorEvent = PhaseEvent | VerdictEvent | SessionEvent | HeartbeatEvent | NoteEvent | FableWallEvent

_EVENT_SHAPES: Final[Mapping[str, object]] = {
    PHASE_EVENT: PhaseEvent,
    VERDICT_EVENT: VerdictEvent,
    SESSION_EVENT: SessionEvent,
    HEARTBEAT_EVENT: HeartbeatEvent,
    FABLE_WALL_EVENT: FableWallEvent,
}
_NOTE_SHAPES: Final[Mapping[str, object]] = {
    REUSED_NOTE: ReusedNote,
    ROUNDS_WARNING_NOTE: RoundsWarningNote,
    INVALIDATED_NOTE: InvalidatedNote,
    INTEGRATION_OUTSIDE_NOTE: IntegrationOutsideNote,
    WARNING_NOTE: WarningNote,
}


@dataclass(frozen=True)
class Wire:
    """The contract's allowed values, gathered for consumers that load this module by path."""

    setup_class: FailureClass
    transient_class: FailureClass
    item_class: FailureClass
    defect_class: FailureClass
    interrupted_class: FailureClass
    failure_classes: frozenset[FailureClass]
    fatal_classes: frozenset[FailureClass]
    class_order: tuple[FailureClass, ...]
    interrupted_stage: StopStage
    shutdown_stage: StopStage
    stop_stages: frozenset[StopStage]
    validation_stage: str
    shutdown_cause: str
    other_cause: str
    api_cause: str
    quota_cause: str
    bd_timeout_cause: str
    contention_cause: str
    account_causes: frozenset[str]
    retryable_causes: tuple[str, ...]
    transient_causes: frozenset[str]
    phase_statuses: frozenset[PhaseStatus]
    event_key: str
    phase_event: EventName
    verdict_event: EventName
    session_event: EventName
    heartbeat_event: EventName
    note_event: EventName
    fable_wall_event: EventName
    event_names: frozenset[EventName]
    session_started: SessionState
    session_ended: SessionState
    session_states: frozenset[SessionState]
    note_kinds: frozenset[NoteKind]
    prd_to_spec_phases: tuple[PrdToSpecPhase, ...]


wire: Final[Wire] = Wire(
    setup_class=SETUP_CLASS,
    transient_class=TRANSIENT_CLASS,
    item_class=ITEM_CLASS,
    defect_class=DEFECT_CLASS,
    interrupted_class=INTERRUPTED_CLASS,
    failure_classes=FAILURE_CLASSES,
    fatal_classes=FATAL_CLASSES,
    class_order=CLASS_ORDER,
    interrupted_stage=INTERRUPTED_STAGE,
    shutdown_stage=SHUTDOWN_STAGE,
    stop_stages=STOP_STAGES,
    validation_stage=VALIDATION_STAGE,
    shutdown_cause=SHUTDOWN_CAUSE,
    other_cause=OTHER_CAUSE,
    api_cause=API_CAUSE,
    quota_cause=QUOTA_CAUSE,
    bd_timeout_cause=BD_TIMEOUT_CAUSE,
    contention_cause=CONTENTION_CAUSE,
    account_causes=ACCOUNT_CAUSES,
    retryable_causes=RETRYABLE_CAUSES,
    transient_causes=TRANSIENT_CAUSES,
    phase_statuses=PHASE_STATUSES,
    event_key=EVENT_KEY,
    phase_event=PHASE_EVENT,
    verdict_event=VERDICT_EVENT,
    session_event=SESSION_EVENT,
    heartbeat_event=HEARTBEAT_EVENT,
    note_event=NOTE_EVENT,
    fable_wall_event=FABLE_WALL_EVENT,
    event_names=EVENT_NAMES,
    session_started=SESSION_STARTED,
    session_ended=SESSION_ENDED,
    session_states=SESSION_STATES,
    note_kinds=NOTE_KINDS,
    prd_to_spec_phases=PRD_TO_SPEC_PHASES,
)


class HandbackValidationError(ValueError):
    """A document violates this contract; the rejected value is kept as evidence."""

    def __init__(self, message: str, payload: object) -> None:
        """Retain the rejected payload for separate failure evidence."""
        super().__init__(message)
        self.payload: object = payload


def _reject(path: str, expected: str, value: object, payload: object) -> NoReturn:
    message: str = f"{path}: expected {expected}, actual {type(value).__name__}"
    raise HandbackValidationError(message, payload)


def _is_text(value: object) -> bool:
    return isinstance(value, str)


def _is_boolean(value: object) -> bool:
    return isinstance(value, bool)


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _is_null(value: object) -> bool:
    return value is None


_SCALARS: Final[Mapping[object, tuple[str, Callable[[object], bool]]]] = {
    str: ("string", _is_text),
    bool: ("boolean", _is_boolean),
    int: ("integer", _is_integer),
    float: ("finite number", _is_number),
    types.NoneType: ("null", _is_null),
}


def _check_literal(value: object, annotation: object, path: str, payload: object) -> None:
    allowed: tuple[object, ...] = get_args(annotation)
    if not any(type(value) is type(option) and value == option for option in allowed):
        _reject(path, f"one of {list(allowed)}", value, payload)


def _check_union(value: object, annotation: object, path: str, payload: object) -> None:
    options: tuple[object, ...] = get_args(annotation)
    last: HandbackValidationError | None = None
    option: object
    for option in options:
        try:
            _conforms(value, option, path, payload)
        except HandbackValidationError as exc:
            last = exc
        else:
            return
    names: str = " | ".join(getattr(option, "__name__", str(option)) for option in options)
    message: str = f"{path}: expected {names}, actual {type(value).__name__}"
    raise HandbackValidationError(message, payload) from last


def _check_list(value: object, annotation: object, path: str, payload: object) -> None:
    if not isinstance(value, list):
        _reject(path, "array", value, payload)
    member: object = get_args(annotation)[0]
    index: int
    item: object
    for index, item in enumerate(value):
        _conforms(item, member, f"{path}.{index}", payload)


def _check_dict(value: object, annotation: object, path: str, payload: object) -> None:
    if not isinstance(value, dict):
        _reject(path, "object", value, payload)
    member: object = get_args(annotation)[1]
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            _reject(f"{path}.{key}", "string key", key, payload)
        _conforms(item, member, f"{path}.{key}", payload)


def _check_typeddict(value: object, annotation: object, path: str, payload: object) -> None:
    if not isinstance(value, dict):
        _reject(path, "object", value, payload)
    required: frozenset[str] = getattr(annotation, "__required_keys__", frozenset())
    optional: frozenset[str] = getattr(annotation, "__optional_keys__", frozenset())
    keys: frozenset[str] = frozenset(key for key in value if isinstance(key, str))
    if len(keys) != len(value):
        _reject(path, "string keys", value, payload)
    missing: frozenset[str] = required - keys
    extra: frozenset[str] = keys - required - optional
    if missing or extra:
        message: str = f"{path}: missing {sorted(missing)}, unexpected {sorted(extra)}"
        raise HandbackValidationError(message, payload)
    hints: dict[str, object] = get_type_hints(annotation)
    key: str
    for key in sorted(keys):
        _conforms(value[key], hints[key], f"{path}.{key}", payload)


def _conforms(value: object, annotation: object, path: str, payload: object) -> None:
    """Check one value against one annotation of this module, recursively.

    Raises:
        TypeError: The annotation is a form this contract does not use.

    """
    if isinstance(annotation, TypeAliasType):
        _conforms(value, annotation.__value__, path, payload)
        return
    scalar: tuple[str, Callable[[object], bool]] | None = _SCALARS.get(annotation)
    if scalar is not None:
        if not scalar[1](value):
            _reject(path, scalar[0], value, payload)
        return
    origin: object = get_origin(annotation)
    if origin is Literal:
        _check_literal(value, annotation, path, payload)
    elif isinstance(annotation, types.UnionType):
        _check_union(value, annotation, path, payload)
    elif origin is list:
        _check_list(value, annotation, path, payload)
    elif origin is dict:
        _check_dict(value, annotation, path, payload)
    elif is_typeddict(annotation):
        _check_typeddict(value, annotation, path, payload)
    else:
        message: str = f"{path}: unsupported contract annotation {annotation!r}"
        raise TypeError(message)


def _check_failure_rules(failure: Mapping[str, object], path: str, payload: object) -> None:
    stage: object = failure.get("stage")
    classification: object = failure.get("classification")
    cause: object = failure.get("cause")
    stopped: bool = isinstance(stage, str) and stage in STOP_STAGES
    message: str
    if classification == INTERRUPTED_CLASS and not stopped:
        message = f"{path}: an interrupted failure requires a stop stage {sorted(STOP_STAGES)}, not {stage!r}"
        raise HandbackValidationError(message, payload)
    if stopped and classification not in {None, INTERRUPTED_CLASS}:
        message = f"{path}: stop stage {stage!r} requires classification {INTERRUPTED_CLASS!r}, not {classification!r}"
        raise HandbackValidationError(message, payload)
    if classification == INTERRUPTED_CLASS and cause != SHUTDOWN_CAUSE:
        message = f"{path}: an interrupted failure requires cause {SHUTDOWN_CAUSE!r}, not {cause!r}"
        raise HandbackValidationError(message, payload)


def _is_failure(value: object, path: str, payload: object) -> TypeIs[Failure]:
    _conforms(value, Failure, path, payload)
    if not isinstance(value, dict):
        _reject(path, "object", value, payload)
    _check_failure_rules(value, path, payload)
    repositories: object = value.get("repositories")
    index: int
    row: object
    for index, row in enumerate(repositories if isinstance(repositories, list) else []):
        if isinstance(row, dict):
            _check_failure_rules(row, f"{path}.repositories.{index}", payload)
    return True


def _check_document_rules(value: Mapping[str, object]) -> None:
    message: str
    emitted: object = value.get("beadsEmitted")
    if isinstance(emitted, int) and emitted < 0:
        message = f"handback.beadsEmitted: expected a count of at least 0, actual {emitted}"
        raise HandbackValidationError(message, value)
    artifacts: object = value.get("artifacts")
    phases: object = artifacts.get("phases") if isinstance(artifacts, dict) else None
    key: object
    for key in phases if isinstance(phases, dict) else {}:
        if not isinstance(key, str) or PHASE_KEY.fullmatch(key) is None:
            message = f"handback.artifacts.phases: key {key!r} is not {TRD_PHASE!r} or {SPEC_PHASE_PREFIX}<slug>"
            raise HandbackValidationError(message, value)
    failure: object = value.get("failure")
    if failure is not None:
        _is_failure(failure, "handback.failure", value)
    stage: object = value.get("stage")
    stated: object = failure.get("classification") if isinstance(failure, dict) else None
    if isinstance(stage, str) and stage in STOP_STAGES and stated != INTERRUPTED_CLASS:
        message = f"handback: stop stage {stage!r} requires an interrupted failure"
        raise HandbackValidationError(message, value)


def _is_document(value: object) -> TypeIs[HandbackDocument]:
    _conforms(value, HandbackDocument, "handback", value)
    if not isinstance(value, dict):
        _reject("handback", "object", value, value)
    _check_document_rules(value)
    return True


def validate(payload: object) -> HandbackDocument:
    """Validate a document against this contract.

    Args:
        payload: The parsed JSON document.

    Returns:
        The same document, typed. A violation raises ``HandbackValidationError``.

    """
    if not _is_document(payload):
        _reject("handback", "document", payload, payload)
    return payload


def _is_json(value: object, path: str) -> TypeIs[JsonValue]:
    _conforms(value, JsonValue, path, value)
    return True


def _is_diagnostic(value: object, path: str) -> TypeIs[Diagnostic]:
    _conforms(value, Diagnostic, path, value)
    return True


def _is_failure_class(value: object, path: str) -> TypeIs[FailureClass]:
    _conforms(value, FailureClass, path, value)
    return True


def parse_failure_class(value: object) -> FailureClass:
    """Narrow a stored classification to the contract's ``FailureClass``.

    Args:
        value: A classification read back from JSON.

    Returns:
        The classification. A value outside ``FAILURE_CLASSES`` raises ``HandbackValidationError``.

    """
    if not _is_failure_class(value, "classification"):
        _reject("classification", "failure class", value, value)
    return value


def parse_diagnostic(value: object) -> Diagnostic:
    """Narrow a stored diagnostic to the contract's ``Diagnostic``.

    Args:
        value: A diagnostic read back from JSON.

    Returns:
        The diagnostic. A malformed value raises ``HandbackValidationError``.

    """
    if not _is_diagnostic(value, "diagnostic"):
        _reject("diagnostic", "diagnostic", value, value)
    return value


def diagnostic(exc: BaseException, *, agent_started: bool) -> Diagnostic:
    """Keep the full chained traceback and the underlying exception's location.

    Args:
        exc: The exception that ended the step.
        agent_started: Whether an agent session had started before it.

    Returns:
        The original exception facts.

    Raises:
        TypeError: An argument has the wrong type.

    """
    if not isinstance(exc, BaseException) or not isinstance(agent_started, bool):
        message: str = "diagnostic requires an exception and a boolean agent_started"
        raise TypeError(message)
    original: BaseException = exc
    while original.__cause__ is not None:
        original = original.__cause__
    frames: traceback.StackSummary = traceback.extract_tb(original.__traceback__)
    frame: traceback.FrameSummary | None = frames[-1] if frames else None
    return {
        "exceptionType": type(original).__name__,
        "message": str(original),
        "traceback": "".join(traceback.format_exception(exc)),
        "location": {"file": frame.filename if frame else "", "line": (frame.lineno or 0) if frame else 0},
        "agentStarted": agent_started,
    }


def _built(fields: dict[str, object], evidence: object, original: object) -> Failure:
    if evidence is not None and _is_diagnostic(evidence, "failure.diagnostic"):
        fields["diagnostic"] = evidence
    if original is not None and _is_json(original, "failure.originalFailure"):
        fields["originalFailure"] = original
    candidate: object = fields
    if not _is_failure(candidate, "failure", candidate):
        _reject("failure", "failure", candidate, candidate)
    return candidate


def failure(stage: str, cause: str, classification: str, *, diagnostic: object = None) -> Failure:
    """Build one failure of this contract for a producer outside the orchestrator flows.

    Args:
        stage: The stage that failed.
        cause: The failure cause.
        classification: One of ``FAILURE_CLASSES``.
        diagnostic: A ``Diagnostic`` of the original exception, if one exists.

    Returns:
        The validated failure. A contract violation raises ``HandbackValidationError``.

    Raises:
        TypeError: An identifier is not a string.

    """
    if not isinstance(stage, str) or not isinstance(cause, str) or not isinstance(classification, str):
        message: str = "failure requires string stage, cause and classification"
        raise TypeError(message)
    fields: dict[str, object] = {"stage": stage, "cause": cause, "classification": classification, "repositories": []}
    return _built(fields, diagnostic, None)


def interrupted_failure(
    stage: str,
    *,
    diagnostic: object = None,
    original: object = None,
    interrupted_stage: str | None = None,
) -> Failure:
    """Build the failure of an owner stop-execution, SIGTERM or supervisor shutdown.

    Args:
        stage: ``INTERRUPTED_STAGE`` for an owner stop-execution or SIGTERM of one item,
            ``SHUTDOWN_STAGE`` for a supervisor shutdown or drain.
        diagnostic: A ``Diagnostic`` of the stopping exception, if one exists.
        original: The failure the item reported before the stop, kept as evidence.
        interrupted_stage: The stage that was running when the stop arrived.

    Returns:
        The interrupted failure. A stage outside ``STOP_STAGES`` raises ``HandbackValidationError``.

    Raises:
        TypeError: A stage is not a string.

    """
    if not isinstance(stage, str) or not (interrupted_stage is None or isinstance(interrupted_stage, str)):
        message: str = "interrupted_failure requires string stages"
        raise TypeError(message)
    fields: dict[str, object] = {
        "stage": stage,
        "cause": SHUTDOWN_CAUSE,
        "classification": INTERRUPTED_CLASS,
        "repositories": [],
    }
    if interrupted_stage is not None and interrupted_stage != stage:
        fields["interruptedStage"] = interrupted_stage
    return _built(fields, diagnostic, original)


def wire_result(result: Mapping[str, JsonValue]) -> HandbackDocument:
    """Project a flow's detailed report to the contract's fields and validate it.

    Args:
        result: The flow report; fields outside this contract stay in run.json.

    Returns:
        The validated document.

    Raises:
        TypeError: The report is not a mapping.

    """
    if not isinstance(result, Mapping):
        message: str = "wire_result requires a JSON report mapping"
        raise TypeError(message)
    fields: frozenset[str] = HandbackDocument.__required_keys__ | HandbackDocument.__optional_keys__
    payload: dict[str, JsonValue] = {key: result[key] for key in fields if key in result}
    payload["version"] = VERSION
    return validate(payload)


def _json_or_text(value: object) -> JsonValue:
    try:
        if _is_json(value, "originalFailure"):
            return value
    except HandbackValidationError:
        pass
    # Non-finite numbers and other non-JSON values survive as evidence text.
    return json.dumps(value, default=repr)


def rejected(payload: object, exc: BaseException, bead: str, detail: str) -> HandbackDocument:
    """Replace a defective document, keeping its original failure and the defect separately.

    Args:
        payload: The rejected document as read.
        exc: Why it was rejected.
        bead: The dispatched bead.
        detail: The detail path to use when the rejected document names none.

    Returns:
        A failed, valid document classified ``pipeline-code-defect``.

    Raises:
        TypeError: Identifiers or the exception have the wrong type.

    """
    if not isinstance(exc, BaseException) or not isinstance(bead, str) or not isinstance(detail, str):
        message: str = "rejected requires an exception and string bead/detail identifiers"
        raise TypeError(message)
    raw: Mapping[object, object] = payload if isinstance(payload, dict) else {}
    original_stage: object = raw.get("stage")
    original_headline: object = raw.get("headline")
    original_detail: object = raw.get("detailPath")
    stage: str = (
        original_stage if isinstance(original_stage, str) and original_stage not in STOP_STAGES else VALIDATION_STAGE
    )
    defect: Failure = {
        "stage": stage,
        "cause": OTHER_CAUSE,
        "classification": DEFECT_CLASS,
        "repositories": [],
        "originalFailure": _json_or_text(raw.get("failure")),
        "handbackDefect": diagnostic(exc, agent_started=False),
    }
    return validate({
        "version": VERSION,
        "ok": False,
        "stage": stage,
        "beadId": bead,
        "headline": original_headline if isinstance(original_headline, str) else "Handback failed validation",
        "detailPath": original_detail if isinstance(original_detail, str) else detail,
        "sessions": [],
        "failure": defect,
    })


def _event_shape(payload: Mapping[object, object]) -> tuple[str, object]:
    name: object = payload.get(EVENT_KEY)
    if not isinstance(name, str) or name not in EVENT_NAMES:
        message: str = f"event.{EVENT_KEY}: expected one of {sorted(EVENT_NAMES)}, actual {name!r}"
        raise HandbackValidationError(message, payload)
    if name != NOTE_EVENT:
        return name, _EVENT_SHAPES[name]
    kind: object = payload.get("kind")
    shape: object = _NOTE_SHAPES.get(kind) if isinstance(kind, str) else None
    if shape is None:
        message = f"event.{name}.kind: expected one of {sorted(NOTE_KINDS)}, actual {kind!r}"
        raise HandbackValidationError(message, payload)
    return name, shape


def _check_event_rules(value: Mapping[str, object], path: str) -> None:
    message: str
    name: object = value.get(EVENT_KEY)
    if name == SESSION_EVENT:
        identity: str
        for identity in ("pid", "pgid"):
            number: object = value.get(identity)
            if not isinstance(number, int) or number <= 0:
                message = f"{path}.{identity}: expected a positive integer, actual {number!r}"
                raise HandbackValidationError(message, value)
        ended: bool = value.get("state") == SESSION_ENDED
        ended_keys: frozenset[str] = SessionEvent.__optional_keys__
        present: frozenset[str] = frozenset(key for key in ended_keys if key in value)
        if ended and present != ended_keys:
            message = f"{path}: an {SESSION_ENDED!r} session event requires exit and cause, has {sorted(present)}"
            raise HandbackValidationError(message, value)
        if not ended and present:
            message = f"{path}: a {SESSION_STARTED!r} session event carries no {sorted(present)}"
            raise HandbackValidationError(message, value)
    elif name == NOTE_EVENT and value.get("kind") == REUSED_NOTE and "step" not in value and "phase" not in value:
        message = f"{path}: a {REUSED_NOTE!r} note requires step or phase"
        raise HandbackValidationError(message, value)


def _is_event(payload: object) -> TypeIs[OrchestratorEvent]:
    if not isinstance(payload, dict):
        _reject("event", "object", payload, payload)
    name: str
    shape: object
    name, shape = _event_shape(payload)
    path: str = f"event.{name}"
    _conforms(payload, shape, path, payload)
    _check_event_rules(payload, path)
    return True


def validate_event(payload: object) -> OrchestratorEvent:
    """Validate one orchestrator stdout event line against this contract.

    Args:
        payload: The parsed JSON line.

    Returns:
        The same event, typed. A violation raises ``HandbackValidationError``, including an
        ``event`` value outside ``EVENT_NAMES`` and a note ``kind`` outside ``NOTE_KINDS``.

    """
    if not _is_event(payload):
        _reject("event", "orchestrator event", payload, payload)
    return payload


def phase_event(phase: PrdToSpecPhase, step: str, repository: str | None = None) -> PhaseEvent:
    """Build a validated ``phase`` event; ``repository`` is omitted when None.

    Returns:
        The event. A violation raises ``HandbackValidationError``.

    """
    event: PhaseEvent = {"event": PHASE_EVENT, "phase": phase, "step": step}
    if repository is not None:
        event["repository"] = repository
    validate_event(event)
    return event


def verdict_event(phase: str, label: str, verdict: str, detail: str) -> VerdictEvent:
    """Build a validated ``verdict`` event.

    Returns:
        The event. A violation raises ``HandbackValidationError``.

    """
    event: VerdictEvent = {"event": VERDICT_EVENT, "phase": phase, "label": label, "verdict": verdict, "detail": detail}
    validate_event(event)
    return event


def session_event(row: Session, state: SessionState) -> SessionEvent:
    """Build a validated ``session`` event from a session row.

    Args:
        row: The session row; it must carry positive ``pid`` and ``pgid``.
        state: ``SESSION_STARTED`` or ``SESSION_ENDED``; only an ended event carries exit and cause.

    Returns:
        The event.

    Raises:
        HandbackValidationError: The row has no positive ``pid`` or ``pgid``, or the event breaks
            this contract.

    """
    pid: int | None = row.get("pid")
    pgid: int | None = row.get("pgid")
    if pid is None or pgid is None:
        message: str = "session events require the row's pid and pgid"
        raise HandbackValidationError(message, row)
    event: SessionEvent = {
        "event": SESSION_EVENT,
        "state": state,
        "pid": pid,
        "pgid": pgid,
        "sessionId": row["sessionId"],
        "agent": row["agent"],
        "step": row["step"],
        "effort": row["effort"],
        "cwd": row["cwd"],
        "phase": row["phase"],
        "model": row["model"],
    }
    if state == SESSION_ENDED:
        event["exit"] = row.get("exit")
        event["cause"] = row.get("cause")
    validate_event(event)
    return event


def heartbeat_event(live: list[str], at: float) -> HeartbeatEvent:
    """Build a validated ``heartbeat`` event.

    Returns:
        The event. A violation raises ``HandbackValidationError``.

    """
    event: HeartbeatEvent = {"event": HEARTBEAT_EVENT, "live": list(live), "at": at}
    validate_event(event)
    return event


def reused_note(*, step: str | None = None, phase: str | None = None, repository: str | None = None) -> ReusedNote:
    """Build a validated ``reused`` note; absent facts are omitted, and step or phase is required.

    Returns:
        The note. A note with neither step nor phase raises ``HandbackValidationError``.

    """
    event: ReusedNote = {"event": NOTE_EVENT, "kind": REUSED_NOTE}
    if step is not None:
        event["step"] = step
    if phase is not None:
        event["phase"] = phase
    if repository is not None:
        event["repository"] = repository
    validate_event(event)
    return event


def rounds_warning_note(phase: str, rounds: int, drivers: list[JsonValue]) -> RoundsWarningNote:
    """Build a validated ``rounds-warning`` note.

    Returns:
        The note. A violation raises ``HandbackValidationError``.

    """
    event: RoundsWarningNote = {
        "event": NOTE_EVENT,
        "kind": ROUNDS_WARNING_NOTE,
        "phase": phase,
        "rounds": rounds,
        "drivers": list(drivers),
    }
    validate_event(event)
    return event


def invalidated_note(step: str, path: str) -> InvalidatedNote:
    """Build a validated ``invalidated`` note.

    Returns:
        The note. A violation raises ``HandbackValidationError``.

    """
    event: InvalidatedNote = {"event": NOTE_EVENT, "kind": INVALIDATED_NOTE, "step": step, "path": path}
    validate_event(event)
    return event


def integration_outside_note(files: list[JsonValue]) -> IntegrationOutsideNote:
    """Build a validated ``integration-outside`` note.

    Returns:
        The note. A violation raises ``HandbackValidationError``.

    """
    event: IntegrationOutsideNote = {"event": NOTE_EVENT, "kind": INTEGRATION_OUTSIDE_NOTE, "files": list(files)}
    validate_event(event)
    return event


def warning_note(step: str, detail: str) -> WarningNote:
    """Build a validated ``warning`` note.

    Returns:
        The note. A violation raises ``HandbackValidationError``.

    """
    event: WarningNote = {"event": NOTE_EVENT, "kind": WARNING_NOTE, "step": step, "detail": detail}
    validate_event(event)
    return event


def fable_wall_event(resets_at: float | None, window: str | None) -> FableWallEvent:
    """Build a validated ``fable-wall`` event.

    Args:
        resets_at: Finite epoch seconds when the limit resets, or None when unknown.
        window: The rate-limit type, or None when unknown.

    Returns:
        The event. A non-finite ``resets_at`` raises ``HandbackValidationError``.

    """
    event: FableWallEvent = {"event": FABLE_WALL_EVENT, "resetsAt": resets_at, "window": window}
    validate_event(event)
    return event


_CONSTANT_ERROR: str
if {PHASE_EVENT, VERDICT_EVENT, SESSION_EVENT, HEARTBEAT_EVENT, NOTE_EVENT, FABLE_WALL_EVENT} != EVENT_NAMES:
    _CONSTANT_ERROR = "the event constants must name every EventName exactly once"
    raise TypeError(_CONSTANT_ERROR)
if {SESSION_STARTED, SESSION_ENDED} != SESSION_STATES:
    _CONSTANT_ERROR = "the session state constants must name every SessionState"
    raise TypeError(_CONSTANT_ERROR)
if set(_NOTE_SHAPES) != NOTE_KINDS or set(_EVENT_SHAPES) | {NOTE_EVENT} != EVENT_NAMES:
    _CONSTANT_ERROR = "every EventName and NoteKind needs exactly one event shape"
    raise TypeError(_CONSTANT_ERROR)

if set(CLASS_ORDER) != FAILURE_CLASSES or len(CLASS_ORDER) != len(FAILURE_CLASSES):
    _ORDER_ERROR: Final = "CLASS_ORDER must list every FailureClass exactly once"
    raise TypeError(_ORDER_ERROR)
