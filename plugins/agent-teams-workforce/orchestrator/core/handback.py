"""The plugin-owned, validated wire contract for orchestrator handbacks."""

from __future__ import annotations

import json
import traceback
from collections.abc import Mapping
from pathlib import Path
from subprocess import TimeoutExpired  # ruff: ignore[suspicious-subprocess-import] - exception classification only; no process is launched
from typing import Literal, NotRequired, TypedDict

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError  # ruff: ignore[typing-only-third-party-import] - Typeguard validates annotated local assignments at runtime.
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from orchestrator.core.agent_context import PipelineStoppedError, SessionCleanupError, SessionSetupError
from orchestrator.core.models import RetryExhaustedError, StepError

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type PhaseStatus = Literal["passed", "reused"]
type FailureClass = Literal["setup", "transient", "item", "pipeline-code-defect"]


class Location(TypedDict):
    """Source location of an exception, independent of its rendered traceback."""

    file: str
    line: int


class Diagnostic(TypedDict):
    """A pipeline defect recorded beside the original step failure."""

    exceptionType: str
    message: str
    traceback: str
    location: Location
    agentStarted: bool


class RepositoryFailure(TypedDict):
    """A repository's failed phase and its original headline."""

    repository: str
    stage: str
    cause: str
    headline: str
    diagnostic: NotRequired[Diagnostic]
    classification: NotRequired[FailureClass]


class Failure(TypedDict):
    """Step failure evidence without replacing it with transport defects."""

    stage: str
    cause: str
    repositories: list[RepositoryFailure]
    resumeAt: NotRequired[float]
    evidence: NotRequired[list[str]]
    unscored: NotRequired[list[JsonValue]]
    classification: NotRequired[FailureClass]
    diagnostic: NotRequired[Diagnostic]
    handbackDefect: NotRequired[Diagnostic]
    originalFailure: NotRequired[JsonValue]


class ArtifactReport(TypedDict):
    """Accepted documents to file; detailed phase results live in run.json."""

    dir: str
    epicId: str
    phases: dict[str, PhaseStatus]
    filing: dict[str, str]


class Session(TypedDict):
    """Session attribution written before launch and completed after exit."""

    sessionId: str
    cwd: str
    phase: str
    step: str
    agent: str
    model: str
    effort: str
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
    """Version one orchestrator-to-driver result, validated before either use."""

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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class HandbackValidationError(ValueError):
    """A defective wire document, with its untouched original value available."""

    def __init__(self, message: str, payload: object) -> None:
        """Retain the rejected payload for separate failure evidence."""
        super().__init__(message)
        self.payload: object = payload


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def schema_path() -> Path:
    """Locate the schema in this exact installed plugin copy.

    Returns:
        The plugin-owned schema path.

    """
    return Path(__file__).resolve().parents[1] / "schemas" / "handback.schema.json"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def validate(payload: object, schema: Path | None = None) -> HandbackDocument:
    """Validate the exact wire shape and return its corresponding typed value.

    Returns:
        The validated document.

    Raises:
        HandbackValidationError: A field violates the plugin schema.
        TypeError: The schema argument is not a path.

    """
    if schema is not None and not isinstance(schema, Path):
        argument_error: str = "schema must be a Path or None"
        raise TypeError(argument_error)
    raw_definition: object = json.loads((schema or schema_path()).read_text(encoding="utf-8"))
    definition: dict[str, JsonValue] = check_type(
        raw_definition,
        dict[str, JsonValue],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    validator: Draft202012Validator = Draft202012Validator(definition)
    errors: list[ValidationError] = sorted(
        validator.iter_errors(payload),
        key=lambda error: str(list(error.absolute_path)),
    )
    if errors:
        error: ValidationError = errors[0]
        field: str = ".".join(map(str, error.absolute_path)) or "$"
        error_schema: object = error.schema
        expected: object = error.validator_value
        if isinstance(error_schema, dict):
            schema_fields: dict[str, JsonValue] = check_type(
                error_schema,
                dict[str, JsonValue],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
            expected = schema_fields.get("type", expected)
        actual: str = type(error.instance).__name__
        message: str = f"handback.{field}: expected {expected}, actual {actual}: {error.message}"
        raise HandbackValidationError(message, payload)
    try:
        return check_type(payload, HandbackDocument, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    except TypeCheckError as exc:
        raise HandbackValidationError(str(exc), payload) from exc


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def wire_result(result: Mapping[str, JsonValue]) -> HandbackDocument:
    """Project the internal run report to the sole supported handback shape.

    Returns:
        A validated wire document.

    Raises:
        TypeError: The report is not a mapping.

    """
    if not isinstance(result, Mapping):
        message: str = "wire_result requires a JSON report mapping"
        raise TypeError(message)
    fields: tuple[str, ...] = (
        "ok",
        "stage",
        "beadId",
        "headline",
        "detailPath",
        "sessions",
        "artifacts",
        "failure",
        "lifecycleDone",
        "beadsEmitted",
        "requiredHumanActions",
        "refusal",
    )
    payload: dict[str, JsonValue] = {key: result[key] for key in fields if key in result}
    payload["version"] = 1
    return validate(payload)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def diagnostic(exc: BaseException, *, agent_started: bool) -> Diagnostic:
    """Keep the full chained traceback and the underlying exception location.

    Returns:
        The original exception facts.

    """
    original: BaseException
    frames: traceback.StackSummary
    frame: traceback.FrameSummary | None
    original = exc
    while original.__cause__ is not None:
        original = original.__cause__
    frames = traceback.extract_tb(original.__traceback__)
    frame = frames[-1] if frames else None
    return {
        "exceptionType": type(original).__name__,
        "message": str(original),
        "traceback": "".join(traceback.format_exception(exc)),
        "location": {"file": frame.filename if frame else "", "line": (frame.lineno or 0) if frame else 0},
        "agentStarted": agent_started,
    }


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _classification(
    chain: list[BaseException],
    step: StepError | None,
    *,
    agent_started: bool,
    setup: bool,
) -> tuple[FailureClass, str]:
    cause: str
    cause = step.cause if step else "other"
    classification: FailureClass
    if any(isinstance(item, SessionCleanupError) for item in chain):
        classification, cause = "pipeline-code-defect", "other"
    elif any(isinstance(item, (PipelineStoppedError, InterruptedError)) for item in chain):
        classification, cause = "item", "shutdown"
    elif any(isinstance(item, (TypeCheckError, HandbackValidationError)) for item in chain):
        classification = "pipeline-code-defect"
    elif (
        setup
        or any(isinstance(item, SessionSetupError) for item in chain)
        or (step is not None and step.stage == "input")
    ):
        classification = "setup"
    elif any(isinstance(item, ImportError) for item in chain):
        classification = "pipeline-code-defect" if agent_started else "setup"
    elif any(
        isinstance(item, (TypeError, ValueError, AttributeError, KeyError, NameError, IndexError)) for item in chain
    ):
        classification = "pipeline-code-defect"
    elif any(isinstance(item, RetryExhaustedError) for item in chain):
        classification = "item"
    elif cause in {"api", "quota", "bd-timeout", "contention", "timeout", "tool-timeout", "network"} or any(
        isinstance(item, (TimeoutError, ConnectionError, TimeoutExpired)) for item in chain
    ):
        classification = "transient"
    elif step is not None:
        classification = "item"
    else:
        classification = "pipeline-code-defect"
    return classification, cause


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def failure_for(stage: str, exc: BaseException, *, agent_started: bool, setup: bool = False) -> Failure:
    """Classify an exception without discarding its original diagnostic evidence.

    Returns:
        The single failure class and original diagnostic.

    """
    chain: list[BaseException]
    step: StepError | None
    classification: FailureClass
    cause: str
    chain = _exception_chain(exc)
    step = next((item for item in chain if isinstance(item, StepError)), None)
    classification, cause = _classification(chain, step, agent_started=agent_started, setup=setup)
    failure: Failure = {
        "stage": step.stage if step else stage,
        "cause": cause,
        "repositories": [],
        "classification": classification,
        "diagnostic": diagnostic(exc, agent_started=agent_started),
    }
    if step is not None:
        failure["evidence"] = list(step.evidence)
        if step.resume_at is not None:
            failure["resumeAt"] = step.resume_at
    return failure


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def rejected(payload: object, exc: BaseException, bead: str, detail: str) -> HandbackDocument:
    """Report a contract defect beside untouched original failure evidence.

    Returns:
        A failed handback preserving the original step headline and evidence.

    Raises:
        TypeError: Identifiers or the exception do not match the input contract.

    """
    if not isinstance(exc, BaseException) or not isinstance(bead, str) or not isinstance(detail, str):
        argument_error: str = "rejected requires an exception and string bead/detail identifiers"
        raise TypeError(argument_error)
    checked: JsonValue = check_type(payload, JsonValue, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    raw: dict[str, JsonValue] = checked if isinstance(checked, dict) else {}
    original_stage: JsonValue = raw.get("stage")
    original_headline: JsonValue = raw.get("headline")
    stage: str = original_stage if isinstance(original_stage, str) else "handback-validation"
    headline: str = original_headline if isinstance(original_headline, str) else "Handback failed schema validation"
    failure: Failure = {
        "stage": stage,
        "cause": "other",
        "repositories": [],
        "classification": "pipeline-code-defect",
        "originalFailure": raw.get("failure"),
        "handbackDefect": diagnostic(exc, agent_started=False),
    }
    original_detail: JsonValue = raw.get("detailPath")
    return {
        "version": 1,
        "ok": False,
        "stage": stage,
        "beadId": bead,
        "headline": headline,
        "detailPath": original_detail if isinstance(original_detail, str) else detail,
        "sessions": [],
        "failure": failure,
    }
