"""Declarations shared by flows, deterministic tools and the session runner."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, check_type, typechecked

from . import portfolio_bootstrap  # ruff: ignore[unused-import] - Imported for its sys.path setup.
from .handback_contract import OTHER_CAUSE, Session
from .io import JsonValue

# isort: split
from step_journal_contract import STEP_ID_PATTERN, StepId

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
        """Attach the step stage, classified cause and recorded evidence.

        The message is ``<stage>: <cause>`` followed by the evidence, so the category never
        stands in for what was found.
        """
        detail: str = "; ".join(evidence)
        super().__init__(f"{stage}: {cause}: {detail}" if detail else f"{stage}: {cause}")
        self.stage = stage
        self.cause = cause
        self.evidence = evidence
        self.resume_at = resume_at

    def __str__(self) -> str:
        """Return the message, with the chained original error when the message lacks it.

        Returns:
            The message; when the error was raised from another whose text it does not already
            contain, followed by ``caused by <Type>: <message>`` of that error.

        """
        message: str = super().__str__()
        origin: BaseException | None = self.__cause__
        if origin is None or (str(origin) and str(origin) in message):
            return message
        return f"{message}: caused by {type(origin).__name__}: {origin}"


class RetryExhaustedError(StepError):
    """A transient operation used its complete bounded retry allowance."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class StaleInputError(StepError):
    """A file an earlier step wrote does not satisfy the contract a step reads it by now.

    The contract changed after the file was written. The journal runner sets ``writer``, the
    step that wrote the file, and every step after it back to planned, so the file is written
    again to the current contract; the step is not failed.
    """

    def __init__(self, stage: str, writer: StepId, evidence: tuple[str, ...] = ()) -> None:
        """Attach the stage, the cause ``other``, the evidence and the step that wrote the file."""
        super().__init__(stage, OTHER_CAUSE, evidence)
        self.writer = writer


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class PipelineDefectError(StepError):
    """Pipeline code failed, not the item's work; it is classified ``pipeline-code-defect``.

    Its message names the stage and the original exception's type and text, so the handback
    headline says what broke: ``<stage>: pipeline defect: <Type>: <message>``.
    """

    def __init__(self, stage: str, error: BaseException, evidence: tuple[str, ...] = ()) -> None:
        """Attach the stage, the cause ``other`` and the failing exception's type and text."""
        super().__init__(stage, OTHER_CAUSE, evidence)
        self.error = error
        self.args = (f"{stage}: pipeline defect: {type(error).__name__}: {error}",)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class AgentStep:
    """A bounded agent request and its exact output validation contract.

    The session's model and effort are not part of a step: the agent's definition states them.
    ``request`` is the text of what is asked and ``journal_step`` is the id of the step in the
    bead's step journal; a step that has neither sends a brief without them.
    """

    stage: str
    agent: str
    inputs: tuple[str, ...]
    output: Path
    outcome: str
    validate: Path | OutputValidator
    add_dirs: tuple[Path, ...] = ()
    corrective: bool = True
    request: str | None = None
    journal_step: StepId | None = None

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries.

        Raises:
            ValueError: The request is empty, or the journal step id is not a step id.

        """
        check_type(self.request, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.journal_step, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        if self.request is not None and not self.request.strip():
            message: str = "an agent step's request must not be empty"
            raise ValueError(message)
        if self.journal_step is not None and STEP_ID_PATTERN.search(self.journal_step) is None:
            message = f"not a step journal id: {self.journal_step!r}"
            raise ValueError(message)
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
        check_type(self.add_dirs, tuple[Path, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.corrective, bool, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


class ModelPolicy(TypedDict, total=False):
    """Mutable model fallback state shared by concurrent steps."""

    fable_until: float
    fable_blocked: bool


class SessionFacts(TypedDict):
    """Validated process facts emitted by the bounded stream reader."""

    result: dict[str, JsonValue] | None
    rate: dict[str, JsonValue] | None
    timeout: bool
    exit: int
    pid: int
    cancelledCause: NotRequired[str]
    cancelledResumeAt: NotRequired[float | None]
    stalled: NotRequired[str]
    """The transcript of the subagent whose stall ended the session."""


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
    sessions: list[Session] = field(default_factory=list)
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
        check_type(self.sessions, list[Session], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.cleanup, list[Callable[[], None]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.model_policy, ModelPolicy, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(
            self.session_slots,
            threading.BoundedSemaphore,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
