"""Direct reasoning sessions; files and receipts, never transcript prose, decide success."""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import traceback
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from uuid import uuid4

import jsonschema

from .agent_context import brief, driver_module, prepare
from .agent_process import SessionProcesses
from .artifacts import ArtifactStore
from .constraints import Section2Guard
from .events import EventWriter
from .io import write_json
from .manifest import record_session
from .models import AgentStep, RunContext, StepError
from .tools import Tools


def strict_json(path: Path) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique,
        parse_constant=nonfinite,
    )


def validate_output(step: AgentStep) -> Any:
    if isinstance(step.validate, Path):
        result = strict_json(step.output)
        schema = strict_json(step.validate)
        jsonschema.validate(result, schema)
        return result
    if not step.output.read_text(encoding="utf-8").strip():
        raise ValueError(f"empty document: {step.output}")
    step.validate(step.output)
    return None


class AgentRunner:
    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        *,
        plugin: Path | None = None,
        emit: Callable[..., None] | None = None,
        executable: str = "claude",
    ) -> None:
        self.context = context
        self.store = store
        self.plugin = plugin or Path(__file__).resolve().parents[2]
        self.emit = emit or EventWriter()
        self.executable = executable
        self.processes = SessionProcesses()
        context.cleanup.append(self.processes.stop_all)
        self._lock = threading.Lock()
        self._version_checked = False
        self.context.model_policy.setdefault(
            "fable_until", float(context.args.get("fableUntil") or 0)
        )
        self.context.model_policy.setdefault("fable_blocked", False)

    def _version(self) -> None:
        with self._lock:
            if self._version_checked:
                return
            result = subprocess.run(
                [self.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", result.stdout)
            if (
                result.returncode
                or match is None
                or tuple(map(int, match.groups())) < (2, 1, 281)
            ):
                raise StepError(
                    "input", "other", ("Claude Code 2.1.281 or later is required",)
                )
            self._version_checked = True

    def _inputs(self, step: AgentStep) -> list[tuple[str, Path]]:
        facts = self.store.module.hashed_inputs(list(step.inputs), self.store.root)
        return [
            (
                Path(item["path"]).stem,
                self.store.module.from_record(item["path"], self.store.root),
            )
            for item in facts
            if item["kind"] not in {"value", "git-main"}
        ]

    def run(self, step: AgentStep) -> Path:
        """Reuse an accepted output, or run and accept one new result with bounded correction."""
        final = step.final or step.output
        try:
            if self.store.reusable(step.inputs, (final,)):
                self.emit("note", kind="reused", step=step.stage)
                return final
            self.store.invalidate((final,))
            self._version()
            with self.context.session_slots:
                return self._execute(step, final)
        except StepError as exc:
            if exc.cause in {"api", "quota"}:
                self.processes.stop_all(cause=exc.cause, resume_at=exc.resume_at)
            raise
        except Exception as exc:
            evidence = (
                self.context.work
                / f"{self.store.module.safe_key(step.stage)}.runner-error.txt"
            )
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(traceback.format_exc(), encoding="utf-8")
            raise StepError(step.stage, "other", (str(evidence),)) from exc

    def _execute(self, step: AgentStep, final: Path) -> Path:
        session_id = str(uuid4())
        key = self.store.module.safe_key(step.stage)
        config = Path(
            os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
        ).expanduser()
        root = Path(
            os.environ.get("ATW_SESSION_ROOT", str(config / "atw-sessions"))
        ).expanduser()
        directory = (
            root
            / self.store.module.safe_key(self.context.run_id)
            / f"{key}-{session_id}"
        )
        scratch = (
            self.context.work
            / "scratch"
            / self.store.module.safe_key(self.context.run_id)
        )
        env = driver_module("headlessenv").child_env(scratch)
        inputs = self._inputs(step)
        model = (
            "opus"
            if step.model == "fable"
            and (
                self.context.model_policy["fable_blocked"]
                or self.context.model_policy["fable_until"] > time.time()
            )
            else step.model
        )
        row = {
            "sessionId": session_id,
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
        resume = corrective = False
        attempt = 0
        while True:
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
            command.extend(prepare(self.plugin, config, directory, step, model))
            stream = scratch / f"{key}-{session_id}-{attempt}.stream.jsonl"
            facts = self._session(
                command,
                brief(self.context.bead, step, inputs, corrective=corrective),
                directory,
                env,
                stream,
                row,
                model,
            )
            info = facts["rate"]
            if (
                info is not None
                and driver_module("fablewall").is_refusal(info)
                and model == "fable"
            ):
                with self._lock:
                    self.context.model_policy["fable_until"] = (
                        driver_module("fablewall").reset_of(info)
                        or driver_module("breaker").exhausted_reset(info)
                        or 0
                    )
                    self.context.model_policy["fable_blocked"] = not bool(
                        self.context.model_policy["fable_until"]
                    )
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
                    raise StepError(
                        step.stage, "other", (str(errors), str(stream))
                    ) from exc
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
            if step.receipt_required:
                raise
            self.emit(
                "note",
                kind="warning",
                step=step.stage,
                detail=f"artifact receipt: {type(exc).__name__}: {exc}",
            )

    def _session(
        self,
        command: list[str],
        prompt: str,
        directory: Path,
        env: dict[str, str],
        stream: Path,
        row: dict,
        model: str,
    ) -> dict:
        details = {key: row[key] for key in ("sessionId", "agent", "step", "effort")}
        details["model"] = model
        pid = None
        facts = None
        failure_cause = None

        def started(value: int) -> None:
            nonlocal pid
            pid = value
            self.emit("session", state="started", pid=pid, pgid=pid, **details)

        try:
            arch = self.context.args.get("archPath") or os.environ.get("ATW_ARCH_PATH")
            guard = (
                Section2Guard(
                    Path(arch),
                    Tools(self.context.work / "evidence"),
                    self.processes.stop_all,
                ).session(row["sessionId"])
                if arch
                else nullcontext()
            )
            with guard:
                facts = self.processes.run(
                    command,
                    prompt,
                    directory,
                    env,
                    stream,
                    started,
                    lambda: self.emit(
                        "heartbeat", live=[row["sessionId"]], at=time.time()
                    ),
                )
            return facts
        except StepError as exc:
            failure_cause = exc.cause
            raise
        finally:
            if pid is not None:
                cause = failure_cause or (self._cause(facts) if facts else "other")
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
    def _cause(facts: dict) -> str | None:
        if facts["rate"] is not None:
            return (
                None
                if driver_module("fablewall").is_refusal(facts["rate"])
                else "quota"
            )
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
    def _check_session(cls, step: AgentStep, facts: dict, stream: Path) -> None:
        cause = cls._cause(facts)
        if facts["rate"] is not None and cause is None:
            cause = "other"  # A second Fable refusal on Opus is not another retry.
        if cause:
            reset = (
                driver_module("breaker").exhausted_reset(facts["rate"])
                if cause == "quota" and facts["rate"] is not None
                else facts.get("cancelledResumeAt")
            )
            raise StepError(step.stage, cause, (str(stream),), resume_at=reset)
