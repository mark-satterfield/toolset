"""Classify orchestrator exceptions into handback failures (orchestrator handback v1)."""

from __future__ import annotations

from subprocess import (  # ruff: ignore[suspicious-subprocess-import] - exception classification only; no process is launched
    TimeoutExpired,
)

from typeguard import CollectionCheckStrategy, TypeCheckError, typechecked

from orchestrator.core.agent_context import PipelineStoppedError, SessionCleanupError, SessionSetupError
from orchestrator.core.handback_contract import (
    DEFECT_CLASS,
    INTERRUPTED_STAGE,
    ITEM_CLASS,
    OTHER_CAUSE,
    SETUP_CLASS,
    SHUTDOWN_STAGE,
    TRANSIENT_CAUSES,
    TRANSIENT_CLASS,
    Failure,
    FailureClass,
    HandbackValidationError,
    StopStage,
    diagnostic,
    interrupted_failure,
)
from orchestrator.core.models import PipelineDefectError, RetryExhaustedError, StepError


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def stop_stage(exc: BaseException) -> StopStage | None:
    """Name the stop an exception chain records, if it records one.

    A supervisor stop (``PipelineStoppedError``) is the shutdown stage; an owner signal
    (``InterruptedError`` raised by the SIGTERM/SIGINT handler, or ``KeyboardInterrupt``) is the
    interrupted stage. A ``SessionCleanupError`` anywhere in the chain is a code defect, not a
    stop, and yields ``None``.

    Returns:
        The stop stage, or ``None`` when the chain is not a stop.

    Raises:
        TypeError: ``exc`` is not an exception.

    """
    if not isinstance(exc, BaseException):
        message: str = "stop_stage requires an exception"
        raise TypeError(message)
    chain: list[BaseException] = _exception_chain(exc)
    if any(isinstance(item, SessionCleanupError) for item in chain):
        return None
    if any(isinstance(item, PipelineStoppedError) for item in chain):
        return SHUTDOWN_STAGE
    if any(isinstance(item, (InterruptedError, KeyboardInterrupt)) for item in chain):
        return INTERRUPTED_STAGE
    return None


def _classification(
    chain: list[BaseException],
    step: StepError | None,
    *,
    agent_started: bool,
    setup: bool,
) -> tuple[FailureClass, str]:
    cause: str = step.cause if step else OTHER_CAUSE
    classification: FailureClass
    if any(isinstance(item, SessionCleanupError) for item in chain):
        classification, cause = DEFECT_CLASS, OTHER_CAUSE
    elif any(isinstance(item, (TypeCheckError, HandbackValidationError, PipelineDefectError)) for item in chain):
        classification = DEFECT_CLASS
    elif (
        setup
        or any(isinstance(item, SessionSetupError) for item in chain)
        or (step is not None and step.stage == "input")
    ):
        classification = SETUP_CLASS
    elif any(isinstance(item, ImportError) for item in chain):
        classification = DEFECT_CLASS if agent_started else SETUP_CLASS
    elif any(
        isinstance(item, (TypeError, ValueError, AttributeError, KeyError, NameError, IndexError)) for item in chain
    ):
        classification = DEFECT_CLASS
    elif any(isinstance(item, RetryExhaustedError) for item in chain):
        classification = ITEM_CLASS
    elif cause in TRANSIENT_CAUSES or any(
        isinstance(item, (TimeoutError, ConnectionError, TimeoutExpired)) for item in chain
    ):
        classification = TRANSIENT_CLASS
    elif step is not None:
        classification = ITEM_CLASS
    else:
        classification = DEFECT_CLASS
    return classification, cause


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def failure_for(stage: str, exc: BaseException, *, agent_started: bool, setup: bool = False) -> Failure:
    """Classify an exception without discarding its original diagnostic evidence.

    An owner or supervisor stop (``stop_stage``) is an interruption: its stage is the stop stage,
    its cause ``shutdown`` and its classification ``interrupted``, and the stage that was running
    is kept as ``interruptedStage``. It is never a failure of the item.

    Returns:
        The failure with its classification and original diagnostic.

    """
    chain: list[BaseException] = _exception_chain(exc)
    step: StepError | None = next((item for item in chain if isinstance(item, StepError)), None)
    running: str = step.stage if step else stage
    stopped: StopStage | None = stop_stage(exc)
    failure: Failure
    if stopped is not None:
        failure = interrupted_failure(
            stopped,
            diagnostic=diagnostic(exc, agent_started=agent_started),
            interrupted_stage=running,
        )
    else:
        classification: FailureClass
        cause: str
        classification, cause = _classification(chain, step, agent_started=agent_started, setup=setup)
        failure = {
            "stage": running,
            "cause": cause,
            "classification": classification,
            "repositories": [],
            "diagnostic": diagnostic(exc, agent_started=agent_started),
        }
    if step is not None:
        failure["evidence"] = list(step.evidence)
        if step.resume_at is not None:
            failure["resumeAt"] = step.resume_at
    return failure
