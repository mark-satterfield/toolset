"""Direct reasoning sessions; files and receipts, never transcript prose, decide success."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed argv only; no shell execution.
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Callable, Generator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from uuid import uuid4

import jsonschema
from typeguard import CollectionCheckStrategy, check_type, typechecked

from .agent_context import PipelineStoppedError, SessionCleanupError, SessionSetupError, brief, driver_module, prepare
from .agent_process import SessionProcesses, SessionRequest
from .artifacts import ArtifactStore
from .constraints import Section2Guard
from .events import EventWriter
from .handback import failure_for
from .io import JsonValue, json_object, write_json
from .manifest import record_session
from .models import AgentStep, RunContext, SessionFacts, SessionRecord, StepError
from .tools import Tools


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def strict_json(path: Path) -> dict[str, JsonValue]:
    """Read an object with unique keys and finite JSON numbers.

    Returns:
        The validated JSON object.

    """

    def unique(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        result = {}
        for key, value in pairs:
            if key in result:
                message = f"duplicate JSON key: {key}"
                raise ValueError(message)
            result[key] = value
        return result

    def nonfinite(value: str) -> None:
        message = f"non-finite JSON number: {value}"
        raise ValueError(message)

    return json_object(
        json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=nonfinite,
        ),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def validate_output(step: AgentStep) -> dict[str, JsonValue] | None:
    """Validate an agent output against its declared schema or document check.

    Returns:
        The validated JSON object, or None for a Markdown document.

    Raises:
        ValueError: A document is empty.

    """
    if isinstance(step.validate, Path):
        result = strict_json(step.output)
        schema = strict_json(step.validate)
        jsonschema.validate(result, schema)
        return result
    if not step.output.read_text(encoding="utf-8").strip():
        message = f"empty document: {step.output}"
        raise ValueError(message)
    step.validate(step.output)
    return None


def _check_stop() -> None:
    stop_file = os.environ.get("ATW_STOP_FILE")
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
        emit: Callable[..., None] | None = None,
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
        self.context.model_policy.setdefault(
            "fable_until",
            float(check_type(context.args.get("fableUntil") or 0, int | float)),
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
                raise StepError(stage, "other", ("Claude Code 2.1.281 or later is required",))
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
                check_type(self.store.module.from_record(item["path"], self.store.root), Path),
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
            if exc.cause in {"api", "quota"}:
                self.processes.stop_all(cause=exc.cause, resume_at=exc.resume_at)
            raise
        except Exception as exc:
            evidence = self.context.work / f"{self.store.module.safe_key(step.stage)}.runner-error.txt"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(traceback.format_exc(), encoding="utf-8")
            raise StepError(step.stage, "other", (str(evidence),)) from exc

    def _run_step(self, step: AgentStep, final: Path) -> Path:
        if self.store.reusable(step.inputs, (final,)):
            self.emit("note", kind="reused", step=step.stage)
            return final
        self.store.invalidate((final,))
        try:
            self._version()
        except (OSError, ValueError, StepError) as exc:
            raise SessionSetupError(str(exc)) from exc
        with self.context.session_slots:
            return self._execute(step, final)

    def _execute(self, step: AgentStep, final: Path) -> Path:
        try:
            directory = Path(tempfile.mkdtemp(prefix="atw-session-"))
        except OSError as exc:
            raise SessionSetupError(str(exc)) from exc
        try:
            return self._execute_in_directory(step, final, directory)
        finally:
            with _finalization("remove temporary session directory"):
                shutil.rmtree(directory)

    def _setup_request(
        self,
        step: AgentStep,
        session_id: str,
        directory: Path,
    ) -> tuple[Path, dict[str, str], list[tuple[str, Path]], str, SessionRecord]:
        scratch = self.context.work / "scratch" / self.store.module.safe_key(self.context.run_id)
        env = check_type(
            driver_module("headlessenv").child_env(scratch),
            dict[str, str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        inputs = self._inputs(step)
        model = (
            "opus"
            if step.model == "fable"
            and (self.context.model_policy["fable_blocked"] or self.context.model_policy["fable_until"] > time.time())
            else step.model
        )
        row: SessionRecord = {
            "sessionId": session_id,
            "cwd": str(directory),
            "phase": self.context.stage,
            "step": step.stage,
            "agent": step.agent,
            "model": model,
            "effort": step.effort,
        }
        record_session(self.context, self.store, row)
        # Old, unaccepted candidates must never be attributed to this session.
        step.output.parent.mkdir(parents=True, exist_ok=True)
        step.output.unlink(missing_ok=True)
        return scratch, env, inputs, model, row

    def _execute_in_directory(self, step: AgentStep, final: Path, directory: Path) -> Path:
        """Keep one private cwd through corrective and model-fallback resumes.

        Returns:
            The accepted artifact path.

        Raises:
            SessionSetupError: Agent configuration is invalid or unavailable.
            StepError: An output remains invalid after correction.

        """
        session_id = str(uuid4())
        try:
            scratch, env, inputs, model, row = self._setup_request(step, session_id, directory)
        except (OSError, ValueError, KeyError, ImportError) as exc:
            raise SessionSetupError(str(exc)) from exc
        resume = corrective = False
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
                        model,
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
            if info is not None and driver_module("fablewall").is_refusal(info) and model == "fable":
                with self._lock:
                    self.context.model_policy["fable_until"] = (
                        driver_module("fablewall").reset_of(info) or driver_module("breaker").exhausted_reset(info) or 0
                    )
                    self.context.model_policy["fable_blocked"] = not bool(self.context.model_policy["fable_until"])
                self.emit(
                    "fable-wall",
                    resetsAt=self.context.model_policy["fable_until"] or None,
                    window=info.get("rateLimitType"),
                )
                model, resume = "opus", True
                row["model"] = model
                record_session(self.context, self.store, row)
                continue
            self._check_session(step, facts, stream)
            try:
                result = validate_output(step)
            except (
                OSError,
                ValueError,
                UnicodeError,
                jsonschema.ValidationError,
            ) as exc:
                errors = step.output.with_name(step.output.name + ".errors.json")
                write_json(errors, {"output": str(step.output), "errors": [str(exc)]})
                if corrective or not step.corrective:
                    raise StepError(step.stage, "other", (str(errors), str(stream))) from exc
                inputs.append(("validation errors", errors))
                corrective = resume = True
                continue
            if step.final is not None:
                write_json(final, result)
            self._record_output(step, final)
            return final

    def _record_output(self, step: AgentStep, final: Path) -> None:
        """Record validated output; selected flows treat missing receipts as warnings."""
        try:
            self.store.accept(step.stage, step.inputs, (final,), producer=step.agent)
        except Exception as exc:
            failure = failure_for(step.stage, exc, agent_started=True)
            if step.receipt_required or failure["classification"] in {"setup", "pipeline-code-defect"}:
                raise
            self.emit(
                "note",
                kind="warning",
                step=step.stage,
                detail=f"artifact receipt: {type(exc).__name__}: {exc}",
            )

    def _session(
        self,
        *,
        command: list[str],
        prompt: str,
        env: dict[str, str],
        stream: Path,
        row: SessionRecord,
    ) -> SessionFacts:
        directory = Path(row["cwd"])
        model = row["model"]
        details = {key: row[key] for key in ("sessionId", "agent", "step", "effort", "cwd", "phase")}
        details["model"] = model
        pid = None
        facts = None
        failure_cause = None

        def started(value: int) -> None:
            nonlocal pid
            pid = value
            row.update({"pid": pid, "pgid": pid, "startedAt": time.time(), "endedAt": None})
            record_session(self.context, self.store, row)
            self.emit("session", state="started", pid=pid, pgid=pid, **details)

        try:
            arch = self.context.args.get("archPath") or os.environ.get("ATW_ARCH_PATH")
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
                        lambda: self.emit("heartbeat", live=[row["sessionId"]], at=time.time()),
                    ),
                )

            facts = check_type(raw_facts, SessionFacts, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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
                    cause = failure_cause or (self._cause(facts) if facts else "other")
                    row.update({"endedAt": time.time(), "exit": facts["exit"] if facts else None, "cause": cause})
                    record_session(self.context, self.store, row)
                    self.emit(
                        "session",
                        state="ended",
                        pid=pid,
                        pgid=pid,
                        exit=facts["exit"] if facts else None,
                        cause=cause,
                        **details,
                    )

    @staticmethod
    def _cause(facts: SessionFacts) -> str | None:
        if facts["rate"] is not None:
            return None if driver_module("fablewall").is_refusal(facts["rate"]) else "quota"
        result = facts["result"]
        if result and (
            result.get("terminal_reason") == "api_error"
            or (result.get("is_error") and result.get("api_error_status") is not None)
        ):
            return "api"
        if facts["timeout"] or (result and result.get("is_error")):
            return "other"
        if facts.get("cancelledCause"):
            return facts["cancelledCause"]
        if (
            facts["timeout"]
            or facts["exit"] != 0
            or not result
            or result.get("is_error")
            or result.get("subtype") != "success"
        ):
            return "other"
        return None

    @classmethod
    def _check_session(cls, step: AgentStep, facts: SessionFacts, stream: Path) -> None:
        cause = cls._cause(facts)
        if facts["rate"] is not None and cause is None:
            cause = "other"  # A second Fable refusal on Opus is not another retry.
        if cause:
            reset = (
                driver_module("breaker").exhausted_reset(facts["rate"])
                if cause == "quota" and facts["rate"] is not None
                else facts.get("cancelledResumeAt")
            )
            raise StepError(step.stage, cause, (str(stream),), resume_at=check_type(reset, float | None))
