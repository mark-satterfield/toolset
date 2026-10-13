"""Direct reasoning sessions; files and receipts, never transcript prose, decide success."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed argv only; no shell execution.
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Generator, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Final
from uuid import UUID, uuid4

from . import portfolio_bootstrap  # ruff: ignore[unused-import] - Imported for its sys.path setup.

# isort: split
import jsonschema
import strictschema
from driver_surface_types import ARCH_PATH_ENV, STOP_FILE_ENV
from typeguard import CollectionCheckStrategy, check_type, typechecked

from .agent_context import (
    AgentDefinition,
    Launch,
    PipelineStoppedError,
    SessionCleanupError,
    SessionSetupError,
    brief,
    launch_model,
    load_agent,
    prepare,
)
from .agent_process import SessionProcesses, SessionRequest
from .artifacts import ArtifactStore
from .constraints import Section2Guard
from .driver_contracts import (
    DispatchArguments,
    child_environment,
    dispatch_arguments,
    exhausted_reset,
    is_refusal,
    reset_of,
)
from .events import EventSink, EventWriter
from .handback_contract import (
    ACCOUNT_CAUSES,
    API_CAUSE,
    EVENT_KEY,
    OTHER_CAUSE,
    QUOTA_CAUSE,
    SESSION_ENDED,
    SESSION_STARTED,
    SHUTDOWN_CAUSE,
    OrchestratorEvent,
    Session,
    SessionState,
    fable_wall_event,
    heartbeat_event,
    reused_note,
    session_event,
)
from .io import JsonValue, json_object, write_json
from .manifest import record_session
from .models import AgentStep, PipelineDefectError, RunContext, SessionFacts, StepError
from .skills import epic_expertise
from .tools import Tools

FABLE: Final = "fable"
FABLE_REPLACEMENT: Final = MappingProxyType({FABLE: "opus"})
"""The model every agent whose definition states Fable runs on while the Fable allowance is spent."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def strict_json(path: Path) -> dict[str, JsonValue]:
    """Read an object with unique keys and finite JSON numbers.

    A literal such as ``1e309`` overflows to infinity in Python's float parser; it is refused
    like ``NaN`` and ``Infinity``.

    Returns:
        The validated JSON object.

    """

    def unique(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        for key, value in pairs:
            if key in result:
                message = f"duplicate JSON key: {key}"
                raise ValueError(message)
            result[key] = value
        return result

    def nonfinite(value: str) -> None:
        message = f"non-finite JSON number: {value}"
        raise ValueError(message)

    def finite(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            nonfinite(value)
        return number

    return json_object(
        json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=nonfinite,
            parse_float=finite,
        ),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def validate_output(step: AgentStep) -> dict[str, JsonValue] | None:
    """Validate an agent output against its declared schema or document check.

    A failure of the output itself (unreadable, not strict JSON, or failing the schema with
    ``jsonschema.ValidationError``) is the item's problem and goes to the corrective path. Any
    other failure (the schema file cannot be read, the schema is invalid, a reference cannot be
    resolved, or the validation machinery raises) is a pipeline-code defect.

    Returns:
        The validated JSON object, or None for a Markdown document.

    Raises:
        ValueError: A document is empty.
        ValidationError: The output fails its schema.
        PipelineDefectError: The schema could not be loaded or applied.

    """
    if isinstance(step.validate, Path):
        try:
            schema: dict[str, JsonValue] = strict_json(step.validate)
        except Exception as exc:
            raise PipelineDefectError(step.stage, exc, (str(step.validate),)) from exc
        result: dict[str, JsonValue] = strict_json(step.output)
        try:
            strictschema.validate(result, schema, location=step.validate)
        except jsonschema.ValidationError:
            raise
        except Exception as exc:
            raise PipelineDefectError(step.stage, exc, (str(step.output), str(step.validate))) from exc
        return result
    if not step.output.read_text(encoding="utf-8").strip():
        message = f"empty document: {step.output}"
        raise ValueError(message)
    step.validate(step.output)
    return None


CONTENT_FAILURES: tuple[type[Exception], ...] = (OSError, ValueError, UnicodeError, jsonschema.ValidationError)
"""Failures of an agent output itself; they take the corrective path, never the defect path."""
SESSION_DIRECTORY_PREFIX: Final = "atw-session-"


class SessionNotResumedError(StepError):
    """A session that was asked to resume ended without running a turn.

    The process ended with a failure status and no result event, no usage wall and no timeout, so
    the conversation it was to continue was not taken up. The caller may start the step in a
    new session.
    """


def _never_ran(facts: SessionFacts) -> bool:
    """Tell whether a session process ended without running a turn.

    Returns:
        True when it exited with a failure status and left no result event, no usage wall, no
        timeout and no cancellation.

    """
    return (
        facts["result"] is None
        and facts["rate"] is None
        and not facts["timeout"]
        and facts["exit"] != 0
        and not facts.get("cancelledCause")
    )


def _write_errors(step: AgentStep, exc: Exception) -> Path:
    """Save the validation errors of ``step``'s output beside it for the corrective session.

    Returns:
        The errors file.

    """
    errors: Path = step.output.with_name(step.output.name + ".errors.json")
    write_json(errors, {"output": str(step.output), "errors": [str(exc)]})
    return errors


def _emit(emit: EventSink, event: OrchestratorEvent) -> None:
    """Send one contract-built event through a sink as its name and facts."""
    facts: dict[str, JsonValue] = json_object({key: value for key, value in event.items() if key != EVENT_KEY})
    emit(event[EVENT_KEY], **facts)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def emit_session(emit: EventSink, row: Session, state: SessionState) -> None:
    """Emit the session attribution persisted by the runner without starting a process.

    The event is built with ``session_event``, so a row without a positive, non-boolean ``pid``
    and ``pgid`` raises ``HandbackValidationError`` and nothing is emitted.
    """
    _emit(emit, session_event(row, state))


def _check_stop() -> None:
    stop_file = os.environ.get(STOP_FILE_ENV)
    if stop_file and Path(stop_file).exists():
        message = "supervisor stopped new agent steps"
        raise PipelineStoppedError(message)


@contextmanager
def _finalization(operation: str) -> Generator[None]:
    original = sys.exception()
    try:
        yield
    except Exception as cleanup:
        error = SessionCleanupError(f"{operation}: {type(cleanup).__name__}: {cleanup}")
        if original is not None:
            error.add_note("Original execution failure:\n" + "".join(traceback.format_exception(original)))
        raise error from cleanup


class AgentRunner:
    """Execute bounded reasoning sessions and accept only validated artifacts."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        *,
        plugin: Path | None = None,
        emit: EventSink | None = None,
        executable: str = "claude",
    ) -> None:
        """Bind dispatch state, artifact storage and the session executable."""
        self.context = context
        self.store = store
        self.plugin = plugin or Path(__file__).resolve().parents[2]
        self.emit = emit or EventWriter()
        self.executable = shutil.which(executable) or executable
        self.processes = SessionProcesses()
        context.cleanup.append(self.processes.stop_all)
        self._lock = threading.Lock()
        self._version_checked = False
        self.dispatch: DispatchArguments = dispatch_arguments()
        self.context.model_policy.setdefault(
            "fable_until",
            float(check_type(context.args.get(self.dispatch.KEY_FABLE_UNTIL) or 0, int | float)),
        )
        self.context.model_policy.setdefault("fable_blocked", False)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def share_processes(self, parent: AgentRunner) -> None:
        """Share the parent runner's process registry and model-policy lock."""
        self.processes = parent.processes
        self._lock = parent._lock

    def _version(self) -> None:
        with self._lock:
            if self._version_checked:
                return
            result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved argv; no shell.
                [self.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", result.stdout)
            stage = "input"
            if result.returncode or match is None or tuple(map(int, match.groups())) < (2, 1, 281):
                raise StepError(stage, OTHER_CAUSE, ("Claude Code 2.1.281 or later is required",))
            self._version_checked = True

    def _inputs(self, step: AgentStep) -> list[tuple[str, Path]]:
        facts = check_type(
            self.store.module.hashed_inputs(list(step.inputs), self.store.root),
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        return [
            (
                Path(check_type(item["path"], str)).stem,
                check_type(self.store.module.from_record(check_type(item["path"], str), self.store.root), Path),
            )
            for item in facts
            if item["kind"] not in {"value", "git-main"}
        ]

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self, step: AgentStep) -> Path:
        """Reuse an accepted output, or accept a new result with bounded correction.

        Returns:
            The accepted artifact path.

        Raises:
            PipelineStoppedError: The supervisor requested a stop between steps.
            SessionSetupError: Session configuration failed before launch.
            StepError: Execution or output validation failed.

        """
        final = step.final or step.output
        try:
            return self._run_step(step, final)
        except PipelineStoppedError, SessionSetupError:
            raise
        except StepError as exc:
            if exc.cause in ACCOUNT_CAUSES:
                self.processes.stop_all(cause=exc.cause, resume_at=exc.resume_at)
            raise
        except Exception as exc:
            evidence = self.context.work / f"{self.store.module.safe_key(step.stage)}.runner-error.txt"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(traceback.format_exc(), encoding="utf-8")
            raise StepError(step.stage, OTHER_CAUSE, (str(evidence),)) from exc

    def _run_step(self, step: AgentStep, final: Path) -> Path:
        if self.store.reusable(step.inputs, (final,)):
            _emit(self.emit, reused_note(step=step.stage))
            return final
        self.store.invalidate((final,))
        saved_errors: Path | None = None
        if self.store.fingerprint_matches(step.inputs, step.output):
            # A saved output from unchanged inputs is reused, never discarded and redone.
            try:
                result: dict[str, JsonValue] | None = validate_output(step)
            except CONTENT_FAILURES as exc:
                saved_errors = _write_errors(step, exc)
                if not step.corrective:
                    raise StepError(step.stage, OTHER_CAUSE, (str(saved_errors),)) from exc
            else:
                _emit(self.emit, reused_note(step=step.stage))
                return self._accept_result(step, final, result)
        try:
            self._version()
        except (OSError, ValueError, StepError) as exc:
            raise SessionSetupError(str(exc)) from exc
        with self.context.session_slots:
            return self._execute(step, final, saved_errors)

    def _execute(self, step: AgentStep, final: Path, saved_errors: Path | None) -> Path:
        try:
            directory = Path(tempfile.mkdtemp(prefix="atw-session-"))
        except OSError as exc:
            raise SessionSetupError(str(exc)) from exc
        try:
            return self._execute_in_directory(step, final, directory, saved_errors)
        finally:
            with _finalization("remove temporary session directory"):
                shutil.rmtree(directory)

    def _setup_request(
        self,
        step: AgentStep,
        session_id: str,
        directory: Path,
        *,
        keep_output: bool,
    ) -> tuple[Path, dict[str, str], list[tuple[str, Path]], Launch, Session]:
        scratch = self.context.work / "scratch" / self.store.module.safe_key(self.context.run_id)
        env = check_type(
            child_environment(scratch),
            dict[str, str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        inputs = self._inputs(step)
        agent: AgentDefinition = load_agent(self.plugin, step.agent)
        fable_spent: bool = (
            self.context.model_policy["fable_blocked"] or self.context.model_policy["fable_until"] > time.time()
        )
        launch: Launch = Launch(
            model_replacements=FABLE_REPLACEMENT if fable_spent else MappingProxyType({}),
            expertise=epic_expertise(self.context.bead, os.environ),
        )
        row: Session = {
            "sessionId": session_id,
            "cwd": str(directory),
            "phase": self.context.stage,
            "step": step.stage,
            "agent": step.agent,
            "model": launch_model(agent, launch),
            "effort": agent.effort,
        }
        record_session(self.context, self.store, row)
        step.output.parent.mkdir(parents=True, exist_ok=True)
        if not keep_output:
            # Reaching here without keep_output means the saved output's inputs changed or were
            # never recorded, so it cannot be attributed to this session's inputs.
            step.output.unlink(missing_ok=True)
        self.store.record_fingerprint(step.inputs, step.output)
        return scratch, env, inputs, launch, row

    def _execute_in_directory(
        self,
        step: AgentStep,
        final: Path,
        directory: Path,
        saved_errors: Path | None,
    ) -> Path:
        """Keep one private cwd through corrective and model-fallback resumes.

        Returns:
            The accepted artifact path.

        Raises:
            SessionSetupError: Agent configuration is invalid or unavailable.
            StepError: An output remains invalid after correction.

        """
        session_id = str(uuid4())
        try:
            scratch, env, inputs, launch, row = self._setup_request(
                step,
                session_id,
                directory,
                keep_output=saved_errors is not None,
            )
        except (OSError, ValueError, KeyError, ImportError) as exc:
            raise SessionSetupError(str(exc)) from exc
        resume = False
        # A saved output that failed validation is corrected once in a new session, as a
        # fresh output that failed validation is corrected once in its own session.
        corrective = saved_errors is not None
        if saved_errors is not None:
            inputs.append(("validation errors", saved_errors))
        attempt = 0
        while True:
            _check_stop()
            attempt += 1
            command = [
                self.executable,
                "-p",
                "--output-format",
                "stream-json",
                "--verbose",
                "--resume" if resume else "--session-id",
                session_id,
            ]
            try:
                command.extend(
                    prepare(
                        self.plugin,
                        Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser(),
                        directory,
                        step,
                        launch,
                    ),
                )
            except (OSError, ValueError, KeyError, ImportError) as exc:
                raise SessionSetupError(str(exc)) from exc
            stream = scratch / f"{self.store.module.safe_key(step.stage)}-{session_id}-{attempt}.stream.jsonl"
            facts = self._session(
                command=command,
                prompt=brief(self.context.bead, step, inputs, corrective=corrective),
                env=env,
                stream=stream,
                row=row,
            )
            info = facts["rate"]
            if info is not None and is_refusal(info) and row["model"] == FABLE:
                with self._lock:
                    self.context.model_policy["fable_until"] = reset_of(info) or exhausted_reset(info) or 0
                    self.context.model_policy["fable_blocked"] = not bool(self.context.model_policy["fable_until"])
                self._emit_fable_wall(info)
                launch, resume = replace(launch, model_replacements=FABLE_REPLACEMENT), True
                row["model"] = FABLE_REPLACEMENT[FABLE]
                record_session(self.context, self.store, row)
                continue
            self._check_session(step, facts, stream)
            try:
                result = validate_output(step)
            except CONTENT_FAILURES as exc:
                errors = _write_errors(step, exc)
                if corrective or not step.corrective:
                    raise StepError(step.stage, OTHER_CAUSE, (str(errors), str(stream))) from exc
                inputs.append(("validation errors", errors))
                corrective = resume = True
                continue
            return self._accept_result(step, final, result)
            return final

    def _emit_fable_wall(self, info: dict[str, JsonValue]) -> None:
        """Report the Fable refusal with the reset now in the model policy and its rate-limit window."""
        window: JsonValue = info.get("rateLimitType")
        _emit(
            self.emit,
            fable_wall_event(
                self.context.model_policy["fable_until"] or None,
                window if isinstance(window, str) else None,
            ),
        )

    def _accept_result(self, step: AgentStep, final: Path, result: dict[str, JsonValue] | None) -> Path:
        """Write a validated result to its final path and record its receipt.

        Returns:
            The accepted artifact path.

        """
        if step.final is not None:
            write_json(final, result)
        self._record_output(step, final)
        return final

    def _record_output(self, step: AgentStep, final: Path) -> None:
        """Record the validated output's receipt; a receipt failure is raised, never downgraded."""
        self.store.accept(step.stage, step.inputs, (final,), producer=step.agent)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run_session(
        self,
        step: AgentStep,
        inputs: Sequence[tuple[str, Path]],
        *,
        session: str,
        resume: bool = False,
        fresh_output: bool = True,
    ) -> Path:
        """Run one step of a step journal as one session, with the session id the caller chose.

        The step journal alone decides whether a step runs, so nothing here looks at an earlier
        output or at a receipt: the session is launched, its output is validated with one
        corrective resume, a Fable refusal is resumed on the replacement model, the stream is
        logged and the session row is recorded in the run record. The validated output stays at
        ``step.output``. A session that was asked to resume and ended without running a turn
        raises ``SessionNotResumedError``, a ``StepError``.

        Args:
            step: The request; ``final`` must be None.
            inputs: The files the brief names, each with its label, in order.
            session: The session id, a UUID. The session's working directory is named for it, so
                a later dispatch that resumes the id runs in the same directory.
            resume: True continues the conversation ``session`` names; False starts it.
            fresh_output: True removes a file already at ``step.output`` before a session that
                starts; False keeps it for a session that updates the file in place. A resumed
                session always keeps it.

        Returns:
            ``step.output``.

        Raises:
            ValueError: ``session`` is not a UUID, or ``step.final`` is set.
            PipelineStoppedError: The supervisor requested a stop between sessions.
            SessionSetupError: Session configuration failed before launch.
            StepError: Execution or output validation failed.

        """
        if step.final is not None:
            message: str = f"a journal step's output stays at its output path; {step.stage} names a final path"
            raise ValueError(message)
        identifier: str = str(UUID(session))
        try:
            return self._run_session(step, list(inputs), identifier, resume=resume, fresh_output=fresh_output)
        except PipelineStoppedError, SessionSetupError:
            raise
        except StepError as exc:
            if exc.cause in ACCOUNT_CAUSES:
                self.processes.stop_all(cause=exc.cause, resume_at=exc.resume_at)
            raise
        except Exception as exc:
            evidence: Path = self.context.work / f"{self.store.module.safe_key(step.stage)}.runner-error.txt"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(traceback.format_exc(), encoding="utf-8")
            raise StepError(step.stage, OTHER_CAUSE, (str(evidence),)) from exc

    def _run_session(
        self,
        step: AgentStep,
        inputs: list[tuple[str, Path]],
        session_id: str,
        *,
        resume: bool,
        fresh_output: bool,
    ) -> Path:
        """Hold a session slot and the session's own directory for one journal step.

        Returns:
            The validated output path.

        Raises:
            SessionSetupError: The executable is unusable or the directory cannot be made.

        """
        try:
            self._version()
        except (OSError, ValueError, StepError) as exc:
            raise SessionSetupError(str(exc)) from exc
        with self.context.session_slots:
            directory: Path = Path(tempfile.gettempdir()) / f"{SESSION_DIRECTORY_PREFIX}{session_id}"
            try:
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            except OSError as exc:
                raise SessionSetupError(str(exc)) from exc
            try:
                return self._journal_session(step, inputs, directory, resume=resume, fresh_output=fresh_output)
            finally:
                with _finalization("remove temporary session directory"):
                    shutil.rmtree(directory)

    def _journal_setup(
        self,
        step: AgentStep,
        session_id: str,
        directory: Path,
    ) -> tuple[Path, dict[str, str], Launch, Session]:
        """Prepare the scratch directory, environment and launch of a journal step's session.

        Returns:
            The scratch directory, the child environment, the launch and the session row, which
            is recorded in the run record.

        """
        scratch: Path = self.context.work / "scratch" / self.store.module.safe_key(self.context.run_id)
        env: dict[str, str] = check_type(
            child_environment(scratch),
            dict[str, str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        agent: AgentDefinition = load_agent(self.plugin, step.agent)
        fable_spent: bool = (
            self.context.model_policy["fable_blocked"] or self.context.model_policy["fable_until"] > time.time()
        )
        launch: Launch = Launch(
            model_replacements=FABLE_REPLACEMENT if fable_spent else MappingProxyType({}),
            expertise=epic_expertise(self.context.bead, os.environ),
        )
        row: Session = {
            "sessionId": session_id,
            "cwd": str(directory),
            "phase": self.context.stage,
            "step": step.stage,
            "agent": step.agent,
            "model": launch_model(agent, launch),
            "effort": agent.effort,
        }
        record_session(self.context, self.store, row)
        step.output.parent.mkdir(parents=True, exist_ok=True)
        return scratch, env, launch, row

    def _journal_session(
        self,
        step: AgentStep,
        inputs: list[tuple[str, Path]],
        directory: Path,
        *,
        resume: bool,
        fresh_output: bool,
    ) -> Path:
        """Run the session of one journal step through its corrective and model-fallback resumes.

        Returns:
            The validated output path.

        Raises:
            SessionSetupError: Agent configuration is invalid or unavailable.
            SessionNotResumedError: The resume the caller asked for ended without a turn.
            StepError: The session failed, or its output remains invalid after correction.

        """
        session_id: str = directory.name.removeprefix(SESSION_DIRECTORY_PREFIX)
        try:
            scratch, env, launch, row = self._journal_setup(step, session_id, directory)
            if fresh_output and not resume:
                step.output.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, ImportError) as exc:
            raise SessionSetupError(str(exc)) from exc
        asked_to_resume: bool = resume
        corrective: bool = False
        attempt: int = 0
        while True:
            _check_stop()
            attempt += 1
            command: list[str] = [
                self.executable,
                "-p",
                "--output-format",
                "stream-json",
                "--verbose",
                "--resume" if resume else "--session-id",
                session_id,
            ]
            try:
                command.extend(
                    prepare(
                        self.plugin,
                        Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser(),
                        directory,
                        step,
                        launch,
                    ),
                )
            except (OSError, ValueError, KeyError, ImportError) as exc:
                raise SessionSetupError(str(exc)) from exc
            stream: Path = scratch / f"{self.store.module.safe_key(step.stage)}-{session_id}-{attempt}.stream.jsonl"
            facts: SessionFacts = self._session(
                command=command,
                prompt=brief(self.context.bead, step, inputs, corrective=corrective),
                env=env,
                stream=stream,
                row=row,
            )
            info: dict[str, JsonValue] | None = facts["rate"]
            if info is not None and is_refusal(info) and row["model"] == FABLE:
                with self._lock:
                    self.context.model_policy["fable_until"] = reset_of(info) or exhausted_reset(info) or 0
                    self.context.model_policy["fable_blocked"] = not bool(self.context.model_policy["fable_until"])
                self._emit_fable_wall(info)
                launch, resume = replace(launch, model_replacements=FABLE_REPLACEMENT), True
                row["model"] = FABLE_REPLACEMENT[FABLE]
                record_session(self.context, self.store, row)
                continue
            if asked_to_resume and attempt == 1 and _never_ran(facts):
                raise SessionNotResumedError(step.stage, OTHER_CAUSE, (str(stream),))
            self._check_session(step, facts, stream)
            try:
                validate_output(step)
            except CONTENT_FAILURES as exc:
                errors: Path = _write_errors(step, exc)
                if corrective or not step.corrective:
                    raise StepError(step.stage, OTHER_CAUSE, (str(errors), str(stream))) from exc
                inputs.append(("validation errors", errors))
                corrective = resume = True
                continue
            return step.output

    def _session(
        self,
        *,
        command: list[str],
        prompt: str,
        env: dict[str, str],
        stream: Path,
        row: Session,
    ) -> SessionFacts:
        directory = Path(row["cwd"])
        pid = None
        facts = None
        failure_cause = None

        def started(value: int) -> None:
            nonlocal pid
            pid = value
            row.update({"pid": pid, "pgid": pid, "startedAt": time.time(), "endedAt": None})
            record_session(self.context, self.store, row)
            emit_session(self.emit, row, SESSION_STARTED)

        try:
            arch = self.context.args.get(self.dispatch.KEY_ARCH_PATH) or os.environ.get(ARCH_PATH_ENV)
            guard = (
                Section2Guard(
                    Path(check_type(arch, str)),
                    Tools(self.context.work / "evidence"),
                    self.processes.stop_all,
                ).session(row["sessionId"])
                if arch
                else nullcontext()
            )
            with guard:
                raw_facts = self.processes.run(
                    SessionRequest(
                        command,
                        prompt,
                        directory,
                        env,
                        stream,
                        started,
                        lambda: _emit(self.emit, heartbeat_event([row["sessionId"]], time.time())),
                    ),
                )

            facts = check_type(raw_facts, SessionFacts, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        except InterruptedError, KeyboardInterrupt, PipelineStoppedError:
            failure_cause = SHUTDOWN_CAUSE
            raise
        except (OSError, ValueError) as exc:
            if pid is None:
                raise SessionSetupError(str(exc)) from exc
            raise
        except StepError as exc:
            failure_cause = exc.cause
            raise
        else:
            return facts
        finally:
            with _finalization("persist session completion"):
                if pid is not None:
                    cause = failure_cause or (self._cause(facts) if facts else OTHER_CAUSE)
                    row.update({"endedAt": time.time(), "exit": facts["exit"] if facts else None, "cause": cause})
                    record_session(self.context, self.store, row)
                    emit_session(self.emit, row, SESSION_ENDED)

    @staticmethod
    def _cause(facts: SessionFacts) -> str | None:
        if facts["rate"] is not None:
            return None if is_refusal(facts["rate"]) else QUOTA_CAUSE
        result = facts["result"]
        if result and (
            result.get("terminal_reason") == "api_error"
            or (result.get("is_error") and result.get("api_error_status") is not None)
        ):
            return API_CAUSE
        if facts["timeout"] or (result and result.get("is_error")):
            return OTHER_CAUSE
        if facts.get("cancelledCause"):
            return facts["cancelledCause"]
        if (
            facts["timeout"]
            or facts["exit"] != 0
            or not result
            or result.get("is_error")
            or result.get("subtype") != "success"
        ):
            return OTHER_CAUSE
        return None

    @classmethod
    def _check_session(cls, step: AgentStep, facts: SessionFacts, stream: Path) -> None:
        cause = cls._cause(facts)
        if facts["rate"] is not None and cause is None:
            cause = OTHER_CAUSE  # A second Fable refusal on Opus is not another retry.
        if cause:
            reset = (
                exhausted_reset(facts["rate"])
                if cause == QUOTA_CAUSE and facts["rate"] is not None
                else facts.get("cancelledResumeAt")
            )
            raise StepError(step.stage, cause, (str(stream),), resume_at=check_type(reset, float | None))
