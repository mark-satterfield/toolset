"""Direct reasoning sessions; files, never transcript prose, decide success."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed argv only; no shell execution.
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Final
from uuid import UUID

from . import portfolio_bootstrap  # ruff: ignore[unused-import] - Imported for its sys.path setup.

# isort: split
import jsonschema
import strictschema
from driver_surface_types import ARCH_PATH_ENV, EXECUTION_ID_ENV, SESSION_LIMIT_ENV, STOP_FILE_ENV
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
from .agent_process import SessionProcesses, SessionRequest, WallProbe, subagent_transcripts
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
    TIMEOUT_CAUSE,
    OrchestratorEvent,
    Session,
    SessionState,
    fable_wall_event,
    heartbeat_event,
    session_event,
)
from .io import JsonValue, json_object, safe_key, write_json
from .manifest import record_session
from .models import AgentStep, PipelineDefectError, RunContext, SessionFacts, StepError
from .tools import Tools

# isort: split
# The matrix contract is generated into the artifact-handoff skill, its one definition.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import ROLE_ENV, ROLES

PLUGIN_COMMANDS: Final = "bin"
"""The plugin folder whose commands (``atw-matrix``, ``atw-step-journal``) a session runs by name."""
SESSION_MARKS: Final = "sessions"
"""The folder of the work directory that records, per session id, the agent, the contract schemas
and the fingerprint (``agent_fingerprint``) the session was started under."""
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

    A failure of the output itself (unreadable, not strict JSON, or failing the schema) is the
    item's problem and goes to the corrective path; a schema failure is raised as
    ``strictschema.SchemaProblemsError`` stating every problem in full. Any other failure (the
    schema file cannot be read, the schema is invalid, a reference cannot be resolved, or the
    validation machinery raises) is a pipeline-code defect.

    Returns:
        The validated JSON object, or None for a Markdown document.

    Raises:
        ValueError: A document is empty.
        SchemaProblemsError: The output fails its schema.
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
            found: list[str] = strictschema.problems(result, schema, location=step.validate)
            raise strictschema.SchemaProblemsError(step.output.name, step.validate.name, found) from None
        except Exception as exc:
            raise PipelineDefectError(step.stage, exc, (str(step.output), str(step.validate))) from exc
        return result
    if not step.output.read_text(encoding="utf-8").strip():
        message = f"empty document: {step.output}"
        raise ValueError(message)
    step.validate(step.output)
    return None


_FILE_REF: Final = re.compile(r'"\$ref"\s*:\s*"([^"#][^"#]*)')
_SCHEMA_NAME: Final = re.compile(r"[A-Za-z0-9_.-]+\.schema\.json")


def _contract_files(schema: Path) -> list[Path]:
    """List a contract schema file and every schema file it references, directly or not.

    Returns:
        The schema and its referenced files, each once, in the order they are reached.

    """
    found: list[Path] = []
    pending: list[Path] = [schema.resolve()]
    while pending:
        path: Path = pending.pop()
        if path in found:
            continue
        found.append(path)
        if path.is_file():
            pending.extend((path.parent / ref).resolve() for ref in _FILE_REF.findall(path.read_text(encoding="utf-8")))
    return found


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def agent_fingerprint(plugin: Path, agent: str, contracts: Sequence[Path] = ()) -> str:
    """Fingerprint what a session of an agent was made under: its definition and its contracts.

    The contracts are every schema file the definition names (``<name>.schema.json``, found under
    the plugin's ``skills/*/schemas/``) and ``contracts``, each with every schema file it
    references. The digest covers the definition and those files by path and content; a file
    that does not exist counts as missing. A change elsewhere in the plugin leaves it equal, so a
    held session survives an unrelated release.

    Args:
        plugin: The plugin root.
        agent: The agent's plain name (``agents/<agent>.md``).
        contracts: Further contract schema files, such as the one the session's output is
            validated against, absolute or relative to the plugin root.

    Returns:
        The SHA-256 hex digest.

    """
    root: Path = plugin.resolve()
    definition: Path = (root / "agents" / f"{agent}.md").resolve()
    files: list[Path] = [definition]
    text: str = definition.read_text(encoding="utf-8") if definition.is_file() else ""
    named: set[str] = set(_SCHEMA_NAME.findall(text))
    schemas: list[Path] = sorted(path for path in root.glob("skills/*/schemas/*.schema.json") if path.name in named)
    for contract in [*schemas, *contracts]:
        files.extend(path for path in _contract_files(root / contract) if path not in files)
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root) if path.is_relative_to(root) else path).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"\0missing")
        digest.update(b"\0")
    return digest.hexdigest()


def _contracts_of(plugin: Path, step: AgentStep) -> list[str]:
    """Name the contract schema a step's output is validated against, relative to the plugin when inside it.

    Returns:
        The schema's path, or nothing for a Markdown document checked by a function.

    """
    if not isinstance(step.validate, Path):
        return []
    schema: Path = step.validate.resolve()
    root: Path = plugin.resolve()
    return [str(schema.relative_to(root) if schema.is_relative_to(root) else schema)]


CONTENT_FAILURES: tuple[type[Exception], ...] = (OSError, ValueError, UnicodeError, jsonschema.ValidationError)
"""Failures of an agent output itself; they take the corrective path, never the defect path."""
SESSION_DIRECTORY_PREFIX: Final = "atw-session-"


class SessionNotResumedError(StepError):
    """A session that was asked to resume ended without running a turn.

    The process ended with a failure status and no result event, no usage wall and no timeout, so
    the conversation it was to continue was not taken up. The caller may start the step in a
    new session.
    """


TERMINATED_EXITS: Final[frozenset[int]] = frozenset({-signal.SIGTERM, 128 + signal.SIGTERM})
"""The exit statuses of a session process ended by SIGTERM: the signal itself, or the CLI's own exit on it."""
WALL_PROBE_ARGUMENTS: Final[tuple[str, ...]] = (
    "--model",
    "haiku",
    "--tools",
    "",
    "--setting-sources",
    "",
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--no-session-persistence",
)
"""The probe's session: the smallest model, no tools, no settings, MCP servers, commands or saved transcript."""
WALL_PROBE_PROMPT: Final = "Reply with the single word OK."
WALL_PROBE_TIMEOUT: Final = 120.0
"""Seconds the account-wall probe may take."""


def _terminated_outside(facts: SessionFacts) -> bool:
    """Tell whether a session process was ended by a SIGTERM this orchestrator did not send.

    The orchestrator's own stops leave a usage wall, a timeout or a cancellation in the facts;
    a SIGTERM with none of them came from outside, as the driver sends when another dispatch
    reaches the account's usage wall.

    Returns:
        True when the process ended by SIGTERM with no result event, no usage wall, no timeout
        and no cancellation.

    """
    return (
        facts["result"] is None
        and facts["rate"] is None
        and not facts["timeout"]
        and not facts.get("cancelledCause")
        and facts["exit"] in TERMINATED_EXITS
    )


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


SCHEMA_CORRECTION: Final = (
    "Rewrite the output so it satisfies its contract: correct every error listed, at the path it names, "
    "using only the field names it allows there and the schema rule it quotes; keep everything else as it is."
)
"""What the errors file asks the corrective session to do for a JSON output checked against its schema."""
DOCUMENT_CORRECTION: Final = (
    "Edit the Markdown document so it passes its check: `headline` names the check that failed and each "
    "entry of `errors` names the lines and the item the check found wrong and what the item must state; "
    "change each item it names as that entry says; keep everything else as it is."
)
"""What the errors file asks the corrective session to do for a Markdown document."""


def _write_errors(step: AgentStep, exc: Exception) -> tuple[Path, dict[str, JsonValue]]:
    """Save the validation errors of ``step``'s output beside it for the corrective session.

    The file holds the error's first line as ``headline`` and every further line, one problem
    each, as ``errors``, in full; an error of one line is both.

    Returns:
        The errors file, and its content, which the corrective brief carries inline.

    """
    errors: Path = step.output.with_name(step.output.name + ".errors.json")
    lines: list[str] = [text.strip() for text in str(exc).splitlines() if text.strip()] or [type(exc).__name__]
    content: dict[str, JsonValue] = {
        "output": str(step.output),
        "correction": SCHEMA_CORRECTION if isinstance(step.validate, Path) else DOCUMENT_CORRECTION,
        "headline": lines[0],
        "errors": list(lines[1:] or lines),
    }
    write_json(errors, content)
    return errors, content


FIRST_ERROR_LIMIT: Final = 300
"""The most characters of a validation error a failure's message carries."""


def _first_error(exc: Exception) -> str:
    """Give the first line of a validation error, for a failure's evidence and headline.

    Returns:
        The error's first non-empty line, at most ``FIRST_ERROR_LIMIT`` characters, or its type
        when it has no message.

    """
    line: str = next((text.strip() for text in str(exc).splitlines() if text.strip()), type(exc).__name__)
    return line if len(line) <= FIRST_ERROR_LIMIT else line[: FIRST_ERROR_LIMIT - 1] + "…"


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
        *,
        plugin: Path | None = None,
        emit: EventSink | None = None,
        executable: str = "claude",
    ) -> None:
        """Bind dispatch state and the session executable."""
        self.context = context
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

    def _session_mark(self, session_id: str) -> Path:
        return self.context.work / SESSION_MARKS / f"{session_id}.json"

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def step_fingerprint(self, step: AgentStep) -> str:
        """Fingerprint the agent definition and contract a session of ``step`` runs under now.

        Returns:
            ``agent_fingerprint`` of the step's agent and output contract in this plugin.

        """
        return agent_fingerprint(self.plugin, step.agent, [Path(path) for path in _contracts_of(self.plugin, step)])

    def _mark_session(self, session_id: str, step: AgentStep) -> None:
        """Record the agent, contracts and fingerprint a new session starts under."""
        contracts: list[str] = _contracts_of(self.plugin, step)
        write_json(
            self._session_mark(session_id),
            {
                "sessionId": session_id,
                "agent": step.agent,
                "contracts": list(contracts),
                "fingerprint": agent_fingerprint(self.plugin, step.agent, [Path(path) for path in contracts]),
            },
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def resumable(self, session_id: str) -> bool:
        """Tell whether a session may be continued: it was made under the agent definition and contracts of now.

        The session's mark records the agent, its contract schemas and their fingerprint when the
        session started. A session whose agent definition or contracts have changed since, or one
        with no mark, is not continued; a change elsewhere in the plugin does not matter.

        Returns:
            True when the recorded fingerprint equals the fingerprint of the same files now.

        """
        mark: Path = self._session_mark(session_id)
        if not mark.is_file():
            return False
        fields: dict[str, JsonValue] = strict_json(mark)
        agent: JsonValue = fields.get("agent")
        contracts: JsonValue = fields.get("contracts")
        if not isinstance(agent, str) or not isinstance(contracts, list):
            return False
        paths: list[Path] = [Path(check_type(path, str)) for path in contracts]
        return fields.get("fingerprint") == agent_fingerprint(self.plugin, agent, paths)

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
        output: the session is launched, its output is validated with one
        corrective resume, a Fable refusal is resumed on the replacement model, the stream is
        logged and the session row is recorded in the run record. The validated output stays at
        ``step.output``. A session that was asked to resume and ended without running a turn
        raises ``SessionNotResumedError``, a ``StepError``. A session id that is not a UUID raises
        ``ValueError``.

        Args:
            step: The request.
            inputs: The files the brief names, each with its label, in order.
            session: The session id, a UUID. The session's working directory is named for it and
                kept after the session ends, so a later dispatch that resumes the id runs in the
                same directory with what the earlier run wrote there.
            resume: True continues the conversation ``session`` names; False starts it.
            fresh_output: True removes a file already at ``step.output`` before a session that
                starts; False keeps it for a session that updates the file in place. A resumed
                session always keeps it.

        Returns:
            ``step.output``.

        Raises:
            PipelineStoppedError: The supervisor requested a stop between sessions.
            SessionSetupError: Session configuration failed before launch.
            StepError: Execution or output validation failed.

        """
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
            evidence: Path = self.context.work / f"{safe_key(step.stage)}.runner-error.txt"
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

        The directory is kept when the session ends: a later dispatch that resumes the session
        runs in it and finds what the earlier run wrote there.

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
            return self._journal_session(step, inputs, directory, resume=resume, fresh_output=fresh_output)

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
        scratch: Path = self.context.work / "scratch" / safe_key(self.context.run_id)
        env: dict[str, str] = check_type(
            child_environment(scratch),
            dict[str, str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        agent: AgentDefinition = load_agent(self.plugin, step.agent)
        env["PATH"] = os.pathsep.join([str(self.plugin / PLUGIN_COMMANDS), env.get("PATH", os.defpath)])
        if agent.session_limit is not None:
            env[SESSION_LIMIT_ENV] = str(agent.session_limit)
        if agent.role in ROLES:
            env[ROLE_ENV] = agent.role
        else:
            env.pop(ROLE_ENV, None)
        fable_spent: bool = (
            self.context.model_policy["fable_blocked"] or self.context.model_policy["fable_until"] > time.time()
        )
        launch: Launch = Launch(model_replacements=FABLE_REPLACEMENT if fable_spent else MappingProxyType({}))
        row: Session = {
            "sessionId": session_id,
            "cwd": str(directory),
            "phase": self.context.stage,
            "step": step.stage,
            "agent": step.agent,
            "model": launch_model(agent, launch),
        }
        record_session(self.context, row)
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

        A new session's mark (``_mark_session``) is written once its process runs with a live
        pid, so a launch that fails leaves no mark and no later dispatch tries to continue a
        session that never ran.

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
        correction: dict[str, JsonValue] | None = None
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
            stream: Path = scratch / f"{safe_key(step.stage)}-{session_id}-{attempt}.stream.jsonl"
            facts: SessionFacts = self._session(
                command=command,
                prompt=brief(self.context.bead, step, inputs, correction=correction),
                env=env,
                stream=stream,
                row=row,
                live=None if resume else partial(self._mark_session, session_id, step),
            )
            info: dict[str, JsonValue] | None = facts["rate"]
            if info is not None and is_refusal(info) and row["model"] == FABLE:
                with self._lock:
                    self.context.model_policy["fable_until"] = reset_of(info) or exhausted_reset(info) or 0
                    self.context.model_policy["fable_blocked"] = not bool(self.context.model_policy["fable_until"])
                self._emit_fable_wall(info)
                launch, resume = replace(launch, model_replacements=FABLE_REPLACEMENT), True
                row["model"] = FABLE_REPLACEMENT[FABLE]
                record_session(self.context, row)
                continue
            if asked_to_resume and attempt == 1 and _never_ran(facts):
                raise SessionNotResumedError(step.stage, OTHER_CAUSE, (str(stream),))
            self._check_session(step, facts, stream)
            try:
                validate_output(step)
            except CONTENT_FAILURES as exc:
                errors: Path
                content: dict[str, JsonValue]
                errors, content = _write_errors(step, exc)
                if correction is not None or not step.corrective:
                    raise StepError(step.stage, OTHER_CAUSE, (_first_error(exc), str(errors), str(stream))) from None
                inputs.append(("validation errors", errors))
                correction = content
                resume = True
                continue
            return step.output

    def _session(  # ruff: ignore[too-many-arguments] - The process, its prompt, environment, stream, row and start hook.
        self,
        *,
        command: list[str],
        prompt: str,
        env: dict[str, str],
        stream: Path,
        row: Session,
        live: Callable[[], None] | None = None,
    ) -> SessionFacts:
        directory = Path(row["cwd"])
        pid = None
        facts = None
        failure_cause = None

        def started(value: int) -> None:
            nonlocal pid
            pid = value
            if live is not None:
                live()
            row.update({"pid": pid, "pgid": pid, "startedAt": time.time(), "endedAt": None})
            record_session(self.context, row)
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
                        subagent_transcripts(
                            Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser(),
                            directory,
                            row["sessionId"],
                        ),
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
            # Under the driver (its execution id is set) the driver records the wall it stopped the session for.
            if _terminated_outside(facts) and not os.environ.get(EXECUTION_ID_ENV):
                facts["rate"] = self.processes.account_wall(
                    WallProbe(
                        [self.executable, "-p", "--output-format", "stream-json", "--verbose", *WALL_PROBE_ARGUMENTS],
                        WALL_PROBE_PROMPT,
                        directory,
                        env,
                        stream.with_suffix(".wall-probe.jsonl"),
                        WALL_PROBE_TIMEOUT,
                    ),
                )
            return facts
        finally:
            with _finalization("persist session completion"):
                if pid is not None:
                    cause = failure_cause or (self._cause(facts) if facts else OTHER_CAUSE)
                    row.update({"endedAt": time.time(), "exit": facts["exit"] if facts else None, "cause": cause})
                    record_session(self.context, row)
                    emit_session(self.emit, row, SESSION_ENDED)

    @staticmethod
    def _cause(facts: SessionFacts) -> str | None:
        """Name the cause a session ended with, or None when it ended well.

        A session ended at its time limit, its idle limit or a stalled subagent is ``timeout``,
        a transient cause: the next dispatch continues the session.

        Returns:
            The failure cause, or None.

        """
        if facts["rate"] is not None:
            return None if is_refusal(facts["rate"]) else QUOTA_CAUSE
        if facts["timeout"]:
            return TIMEOUT_CAUSE
        result = facts["result"]
        api: bool = bool(
            result
            and (
                result.get("terminal_reason") == "api_error"
                or (result.get("is_error") and result.get("api_error_status") is not None)
            ),
        )
        if api or (result and result.get("is_error")):
            return API_CAUSE if api else OTHER_CAUSE
        if facts.get("cancelledCause"):
            return facts["cancelledCause"]
        if facts["exit"] != 0 or not result or result.get("is_error") or result.get("subtype") != "success":
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
            evidence: tuple[str, ...] = (str(stream), *([facts["stalled"]] if "stalled" in facts else []))
            raise StepError(step.stage, cause, evidence, resume_at=check_type(reset, float | None))
