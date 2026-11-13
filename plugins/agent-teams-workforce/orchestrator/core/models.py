"""Declarations shared by flows, deterministic tools and the session runner."""

from __future__ import annotations

import atexit
import functools
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, check_type, typechecked

from . import portfolio_bootstrap  # ruff: ignore[unused-import] - Imported for its sys.path setup.
from .handback_contract import OTHER_CAUSE, Session
from .io import JsonValue, write_json

# isort: split
from step_journal_contract import STEP_ID_PATTERN, StepId, StepPlan

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
    again to the current contract; the step is not failed. With ``within``, only the steps after
    the writer inside that step are set back: the steps that read the file are all inside it.
    """

    def __init__(
        self,
        stage: str,
        writer: StepId,
        evidence: tuple[str, ...] = (),
        within: StepId | None = None,
    ) -> None:
        """Attach the stage, the cause ``other``, the evidence, the step that wrote the file and its scope."""
        super().__init__(stage, OTHER_CAUSE, evidence)
        self.writer = writer
        self.within = within


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class DesignGapError(StaleInputError):
    """A repository's spec documents hold an open design gap, so its specs wait for the architect's answer.

    ``writer`` is the repository's first spec step and ``within`` its container: only that
    repository's spec steps are set back to planned. The runner adds the gap round once for every
    repository that found a gap in the same round: ``plans``, the solutions architect's step that
    answers the filed gaps with the index and the check after it, as the last steps of
    ``container`` (the Architecture container), and plans each step of ``reconfirm`` (the TRD
    confirmation) again, so the TRD is confirmed against the answered architecture. Nothing else is
    set back. Unlike any other stale file, the runner sets the writer back however often it was set
    back in this dispatch: the gaps are bounded where they are read (``design_gaps.hold_open``),
    which fails the step instead of raising this error.
    """

    def __init__(  # ruff: ignore[too-many-arguments] - The parts of one gap round.
        self,
        stage: str,
        writer: StepId,
        evidence: tuple[str, ...],
        within: StepId,
        *,
        container: StepId,
        plans: tuple[StepPlan, ...],
        reconfirm: tuple[StepId, ...],
    ) -> None:
        """Attach the repository's steps to set back, and the gap round the runner adds once."""
        super().__init__(stage, writer, evidence, within)
        self.container = container
        self.plans = plans
        self.reconfirm = reconfirm


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class OwnershipChangedError(StaleInputError):
    """Another Epic came to own a matrix entry after the span step marked the Epic's items, or stopped owning one.

    ``writer`` is the span step: run again, it marks each item with the Tasks of the Epic that
    owns its entry now (``builtBy``), and every step after it plans from that. Two Epics
    elaborated at once can race more than once, so the journal runner sets the span back to
    planned up to ``OWNERSHIP_REPLANS`` times in one dispatch before it fails the step.
    """


OWNERSHIP_REPLANS: Final = 3
"""How many times one dispatch plans an Epic's span again because the ownership of an entry changed."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class ScopeChangedError(OwnershipChangedError):
    """The elements the architect's result names for the Epic's Stories differ from those the span step read.

    An answer to a design gap can add or remove an element the Epic builds. ``writer`` is the span
    step: run again, it reads the result as it stands, and every step after it plans from that.
    The journal runner treats it as an ownership change: the span step is planned again up to
    ``OWNERSHIP_REPLANS`` times in one dispatch.
    """


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class MalformedRequestError(StepError):
    """A request the step above a helper wrote does not satisfy the contract it was written under.

    The writer's session (``session``) runs under the same agent definition and contracts the
    request is read by, so the request is the writer's mistake and not an earlier contract: the
    writer corrects the request file (``request``) from the errors file (``errors``), and
    ``check`` judges the corrected file (``journal_run.JournalRunner``).
    """

    def __init__(  # ruff: ignore[too-many-arguments] - The writer, its session, the file, its errors and its check.
        self,
        stage: str,
        writer: StepId,
        *,
        session: str,
        request: Path,
        errors: Path,
        check: OutputValidator,
        evidence: tuple[str, ...] = (),
    ) -> None:
        """Attach the stage, the cause ``other``, the evidence, the writer and what corrects the request."""
        super().__init__(stage, OTHER_CAUSE, evidence)
        self.writer = writer
        self.session = session
        self.request = request
        self.errors = errors
        self.check = check


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
def session_cap() -> int:
    """Read the number of agent sessions a dispatch runs at once.

    Returns:
        ATW_ORCH_SESSIONS, 4 when it is unset.

    Raises:
        ValueError: The configured cap is not positive.

    """
    count = int(os.environ.get("ATW_ORCH_SESSIONS", "4"))
    if count < 1:
        message = "ATW_ORCH_SESSIONS must be positive"
        raise ValueError(message)
    return count


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def session_slots() -> threading.BoundedSemaphore:
    """Create the shared cap for all nested phase pools of this dispatch.

    Returns:
        A semaphore bounded by ATW_ORCH_SESSIONS (:func:`session_cap`).

    """
    return threading.BoundedSemaphore(session_cap())


type WaitKind = Literal["portfolio-lock", "job-queue", "session-slot"]
"""What a dispatch waited for: the portfolio mutation lock, a worker of a bounded job queue, a session slot."""

_LOG: Final = logging.getLogger(__name__)

WAIT_METRICS_FOLDER: Final = "wait-metrics"
"""The folder of a work directory holding one wait-metrics file per orchestrator process."""
WAIT_FLUSH_SECONDS: Final = 5.0
"""The least time between two writes of a wait-metrics file; the process's exit writes the last totals."""


@dataclass(slots=True)
class _WaitTotals:
    """The running totals of one kind of wait."""

    count: int = 0
    total_seconds: float = 0.0
    longest_seconds: float = 0.0


class WaitMeter:
    """Bounded wait totals of one orchestrator process for one work directory.

    The file ``<work>/wait-metrics/<pid>-<uuid>.json`` holds counts and seconds per wait kind,
    the dispatch's session cap and the most sessions it held at once, so the session slots of
    concurrently active dispatches can be added up. It holds identifiers and numbers only.
    """

    def __init__(self, work: Path) -> None:
        """Name the process's metrics file and start empty totals."""
        self._path: Path = work / WAIT_METRICS_FOLDER / f"{os.getpid()}-{uuid.uuid4().hex}.json"
        self._lock: threading.Lock = threading.Lock()
        self._waits: dict[WaitKind, _WaitTotals] = {}
        self._held: int = 0
        self._peak_held: int = 0
        self._started: float = time.time()
        self._flushed: float = 0.0

    def waited(self, kind: WaitKind, seconds: float) -> None:
        """Add one wait of ``kind`` that lasted ``seconds``."""
        with self._lock:
            totals: _WaitTotals = self._waits.setdefault(kind, _WaitTotals())
            totals.count += 1
            totals.total_seconds += seconds
            totals.longest_seconds = max(totals.longest_seconds, seconds)
            self._flush_due()

    @contextmanager
    def session_slot(self, slots: threading.BoundedSemaphore) -> Generator[None]:
        """Hold one session slot, recording how long it took to get and how many are held.

        Yields:
            Nothing; the slot is held for the body.

        """
        asked: float = time.monotonic()
        with slots:
            self.waited("session-slot", time.monotonic() - asked)
            with self._lock:
                self._held += 1
                self._peak_held = max(self._peak_held, self._held)
            try:
                yield
            finally:
                with self._lock:
                    self._held -= 1
                    self._flush_due()

    def _flush_due(self) -> None:
        """Write the totals when the last write is older than :data:`WAIT_FLUSH_SECONDS`; the caller holds the lock."""
        if time.monotonic() - self._flushed >= WAIT_FLUSH_SECONDS:
            self._write()

    def flush(self) -> None:
        """Write the totals now."""
        with self._lock:
            self._write()

    def _write(self) -> None:
        """Write the totals file; the caller holds the lock.

        A failed write is logged as a warning and never raised: the metrics never change the
        outcome of the wait they measure.
        """
        self._flushed = time.monotonic()
        try:
            self._write_totals()
        except OSError as error:
            _LOG.warning("wait metrics not written to %s: %s", self._path, error)

    def _write_totals(self) -> None:
        """Write the totals file; the caller holds the lock."""
        write_json(
            self._path,
            {
                "pid": os.getpid(),
                "startedAt": self._started,
                "updatedAt": time.time(),
                "sessionCap": session_cap(),
                "peakSessionsHeld": self._peak_held,
                "waits": {
                    kind: {
                        "count": totals.count,
                        "totalSeconds": round(totals.total_seconds, 6),
                        "longestSeconds": round(totals.longest_seconds, 6),
                    }
                    for kind, totals in self._waits.items()
                },
            },
        )


@functools.cache
def wait_meter(work: Path) -> WaitMeter:
    """Give the one wait meter of this process for a work directory; the process's exit writes its last totals.

    Returns:
        The meter.

    """
    meter: WaitMeter = WaitMeter(work.resolve())
    atexit.register(meter.flush)
    return meter


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
