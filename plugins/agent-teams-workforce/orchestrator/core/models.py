"""Declarations shared by flows, deterministic tools and the session runner."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, check_type, typechecked

from .io import JsonValue

type ValidationResult = dict[str, JsonValue] | tuple[list[str], list[str]] | None
type OutputValidator = Callable[[Path], ValidationResult]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class StepError(Exception):
    """A failure whose cause is known at its point of origin."""

    def __init__(
        self,
        stage: str,
        cause: str,
        evidence: tuple[str, ...] = (),
        *,
        resume_at: float | None = None,
    ) -> None:
        """Attach the step stage, classified cause and recorded evidence."""
        super().__init__(f"{stage}: {cause}")
        self.stage = stage
        self.cause = cause
        self.evidence = evidence
        self.resume_at = resume_at


class RetryExhaustedError(StepError):
    """A transient operation used its complete bounded retry allowance."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class DeterministicStep:
    """A deterministic action with explicitly declared input and output files."""

    stage: str
    inputs: tuple[str, ...]
    outputs: tuple[Path, ...]
    action: Callable[[], object]
    reusable: bool = True

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        check_type(self.stage, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.inputs, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.outputs, tuple[Path, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.action, Callable[[], object], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.reusable, bool, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class AgentStep:
    """A bounded agent request and its exact output validation contract."""

    stage: str
    agent: str
    inputs: tuple[str, ...]
    output: Path
    outcome: str
    validate: Path | OutputValidator
    final: Path | None
    model: str
    effort: str
    add_dirs: tuple[Path, ...] = ()
    corrective: bool = True
    receipt_required: bool = True

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        check_type(self.stage, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.agent, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.inputs, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.output, Path, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.outcome, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(
            self.validate,
            Path | OutputValidator,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        check_type(self.final, Path | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.model, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.effort, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.add_dirs, tuple[Path, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.corrective, bool, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.receipt_required, bool, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


class ModelPolicy(TypedDict, total=False):
    """Mutable model fallback state shared by concurrent steps."""

    fable_until: float
    fable_blocked: bool


class SessionRecord(TypedDict):
    """Attribution written before launch and updated when the process finishes."""

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


class SessionFacts(TypedDict):
    """Validated process facts emitted by the bounded stream reader."""

    result: dict[str, JsonValue] | None
    rate: dict[str, JsonValue] | None
    timeout: bool
    exit: int
    pid: int
    cancelledCause: NotRequired[str]
    cancelledResumeAt: NotRequired[float | None]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def session_slots() -> threading.BoundedSemaphore:
    """Create the shared cap for all nested phase pools of this dispatch.

    Returns:
        A semaphore bounded by ATW_ORCH_SESSIONS.

    Raises:
        ValueError: The configured cap is not positive.

    """
    count = int(os.environ.get("ATW_ORCH_SESSIONS", "4"))
    if count < 1:
        message = "ATW_ORCH_SESSIONS must be positive"
        raise ValueError(message)
    return threading.BoundedSemaphore(count)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass
class RunContext:
    """State shared by every phase of a single orchestration dispatch."""

    bead: str
    flow: str
    args: dict[str, JsonValue]
    work: Path
    run_id: str
    stage: str = "input"
    sessions: list[SessionRecord] = field(default_factory=list)
    cleanup: list[Callable[[], None]] = field(default_factory=list)
    model_policy: ModelPolicy = field(default_factory=ModelPolicy)
    session_slots: threading.BoundedSemaphore = field(
        default_factory=session_slots,
    )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        check_type(self.bead, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.flow, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.args, dict[str, JsonValue], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.work, Path, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.run_id, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.stage, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.sessions, list[SessionRecord], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.cleanup, list[Callable[[], None]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.model_policy, ModelPolicy, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(
            self.session_slots,
            threading.BoundedSemaphore,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
