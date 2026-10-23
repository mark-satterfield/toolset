"""Bounded stream capture and process-group cleanup for direct agent sessions."""

from __future__ import annotations

import json
import math
import os
import re
import selectors
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed argv without shell; owned session groups are terminated.
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from typeguard import CollectionCheckStrategy, check_type, typechecked

from .driver_contracts import terminate_grace
from .handback_contract import OTHER_CAUSE
from .io import JsonValue, json_object
from .models import SessionFacts, StepError

# isort: split
# driver_contracts puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from driver_surface_types import (
    HEARTBEAT_DEFAULT,
    HEARTBEAT_ENV,
    RATE_LIMIT_EVENT_TYPE,
    RATE_LIMIT_INFO_KEY,
    REJECTED_STATUS,
    SESSION_IDLE_DEFAULT,
    SESSION_IDLE_ENV,
    SESSION_LIMIT_DEFAULT,
    SESSION_LIMIT_ENV,
    SUBAGENT_IDLE_DEFAULT,
    SUBAGENT_IDLE_ENV,
)

_DURATIONS: tuple[tuple[str, str], ...] = (
    (SESSION_IDLE_ENV, SESSION_IDLE_DEFAULT),
    (SESSION_LIMIT_ENV, SESSION_LIMIT_DEFAULT),
    (SUBAGENT_IDLE_ENV, SUBAGENT_IDLE_DEFAULT),
    (HEARTBEAT_ENV, HEARTBEAT_DEFAULT),
)
AGENT_TOOLS: frozenset[str] = frozenset({"Agent", "Task"})
"""The Claude Code tool names that start a subagent; an open call of one is watched."""
SUBAGENT_CHECK_SECONDS: float = 15.0
"""How often the subagent transcripts of a session with an open Agent call are checked."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def subagent_transcripts(config: Path, directory: Path, session: str) -> Path:
    """Name the directory where Claude Code writes the transcripts of a session's subagents.

    Claude Code keeps a session's transcript under ``<config>/projects/<slug>/``, the slug being
    the session's resolved working directory with every character that is not a letter or a
    digit replaced by ``-``; the session's subagents write ``agent-<id>.jsonl`` with an
    ``agent-<id>.meta.json`` naming the parent's ``toolUseId`` in ``<session id>/subagents/``.

    Returns:
        The subagents directory, whether or not it exists yet.

    """
    slug: str = re.sub(r"[^A-Za-z0-9]", "-", str(directory.resolve()))
    return config / "projects" / slug / session / "subagents"


def _duration(env: dict[str, str], key: str, default: str) -> float:
    value = float(env.get(key, default))
    if value <= 0 or not math.isfinite(value):
        message = f"{key} must be positive and finite"
        raise ValueError(message)
    return value


@dataclass(frozen=True)
class SessionRequest:
    """Validated process inputs and callbacks for one direct agent session."""

    argv: list[str]
    prompt: str
    directory: Path
    env: dict[str, str]
    stream: Path
    started: Callable[[int], None]
    heartbeat: Callable[[], None]
    transcripts: Path | None = None
    """The session's subagent transcripts directory (``subagent_transcripts``); None watches none."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate all arguments and timing configuration before launching a process."""
        check_type(self.argv, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.prompt, str)
        check_type(self.directory, Path)
        check_type(self.env, dict[str, str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.stream, Path)
        check_type(self.started, Callable[[int], None])
        check_type(self.heartbeat, Callable[[], None])
        check_type(self.transcripts, Path | None)
        for key, default in _DURATIONS:
            _duration(self.env, key, default)


class _SubagentWatch:
    """Find a subagent that stopped writing while its parent's Agent call is still open.

    A parent waiting on an ``Agent`` call writes nothing to its own stream, so the session idle
    limit cannot see a stalled subagent. The watch keeps the parent's open ``Agent`` calls from
    its stream and, every ``SUBAGENT_CHECK_SECONDS``, the modification time of each open call's
    subagent transcript. A missing transcripts directory, or a call with no transcript, is not
    watched. A subagent's own subagents write into the same directory under calls the parent never
    made, so while any of them (``spawnDepth`` above 1) has written within the limit, no open call
    is stalled.
    """

    def __init__(self, transcripts: Path | None, idle: float) -> None:
        self.transcripts, self.idle = transcripts, idle
        self.open: dict[str, float] = {}
        self.files: dict[str, Path] = {}
        self.nested: set[Path] = set()
        self.checked = time.monotonic()

    def observe(self, event: dict[str, JsonValue]) -> None:
        """Open a call on the parent's ``Agent`` tool use and close it on its tool result."""
        message: JsonValue = event.get("message")
        if event.get("parent_tool_use_id") or not isinstance(message, dict):
            return
        content: JsonValue = message.get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            opens: bool = block.get("type") == "tool_use" and block.get("name") in AGENT_TOOLS
            if event.get("type") == "assistant" and opens:
                self.open[str(block.get("id"))] = time.time()
            elif event.get("type") == "user" and block.get("type") == "tool_result":
                self.open.pop(str(block.get("tool_use_id")), None)

    def _directory(self) -> Path | None:
        if self.transcripts is None or self.transcripts.is_dir():
            return self.transcripts
        session: str = self.transcripts.parent.name
        return next(iter(self.transcripts.parents[2].glob(f"*/{session}/subagents")), None)

    def _map(self, directory: Path) -> None:
        for meta in directory.glob("agent-*.meta.json"):
            try:
                fields: object = json.loads(meta.read_text(encoding="utf-8"))
            except OSError, ValueError:
                continue
            if not isinstance(fields, dict):
                continue
            transcript: Path = meta.with_name(meta.name.removesuffix(".meta.json") + ".jsonl")
            depth: object = fields.get("spawnDepth")
            if isinstance(depth, int) and depth > 1:
                self.nested.add(transcript)
            elif isinstance(fields.get("toolUseId"), str):
                self.files[str(fields["toolUseId"])] = transcript

    @staticmethod
    def _written(transcript: Path) -> float | None:
        try:
            return transcript.stat().st_mtime
        except OSError:
            return None

    def stalled(self) -> Path | None:
        """Check the open calls' transcripts at most every ``SUBAGENT_CHECK_SECONDS``.

        Returns:
            The transcript of an open call's subagent that has written nothing for the stall
            limit, or None.

        """
        now: float = time.monotonic()
        if not self.open or now - self.checked < SUBAGENT_CHECK_SECONDS:
            return None
        self.checked = now
        directory: Path | None = self._directory()
        if directory is None:
            return None
        self._map(directory)
        wall: float = time.time()
        if any(wall - (self._written(nested) or 0.0) < self.idle for nested in self.nested):
            return None
        for call, opened in self.open.items():
            transcript: Path | None = self.files.get(call)
            written: float | None = self._written(transcript) if transcript is not None else None
            if written is not None and wall - max(written, opened) >= self.idle:
                return transcript
        return None


class _StreamCapture:
    def __init__(
        self,
        request: SessionRequest,
        process: subprocess.Popen[bytes],
        capture: IO[bytes],
        facts: SessionFacts,
        parse_line: Callable[[bytes, SessionFacts], dict[str, JsonValue] | None],
    ) -> None:
        self.request, self.capture, self.facts, self.parse_line = request, capture, facts, parse_line
        if process.stdin is None or process.stdout is None:
            message = "agent process was launched without its required pipes"
            raise RuntimeError(message)
        self.stdin, self.stdout = process.stdin, process.stdout
        self.pending = request.prompt.encode("utf-8")
        self.buffer = b""
        self.beginning = self.last_line = self.last_beat = time.monotonic()
        self.streamed = False
        self.idle = _duration(request.env, SESSION_IDLE_ENV, SESSION_IDLE_DEFAULT)
        self.limit = _duration(request.env, SESSION_LIMIT_ENV, SESSION_LIMIT_DEFAULT)
        self.beat = _duration(request.env, HEARTBEAT_ENV, HEARTBEAT_DEFAULT)
        self.watch = _SubagentWatch(
            request.transcripts,
            _duration(request.env, SUBAGENT_IDLE_ENV, SUBAGENT_IDLE_DEFAULT),
        )

    def _write(self, selector: selectors.BaseSelector) -> None:
        try:
            count = os.write(self.stdin.fileno(), self.pending)
            self.pending = self.pending[count:]
        except BrokenPipeError:
            self.pending = b""
        if not self.pending:
            selector.unregister(self.stdin)
            self.stdin.close()

    def _read(self) -> bool:
        chunk = os.read(self.stdout.fileno(), 65536)
        if not chunk:
            if self.buffer:
                self._parse(self.buffer)
            return True
        self.capture.write(chunk)
        self.capture.flush()
        self.buffer += chunk
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            self.last_line = time.monotonic()
            self.streamed = True
            self._parse(line)
            if self.facts["rate"] is not None:
                return True
        return False

    def _parse(self, line: bytes) -> None:
        event: dict[str, JsonValue] | None = self.parse_line(line, self.facts)
        if event is not None:
            self.watch.observe(event)

    def _tick(self) -> bool:
        now = time.monotonic()
        if now - self.beginning >= self.limit or now - self.last_line >= self.idle:
            self.facts["timeout"] = True
            return True
        stalled: Path | None = self.watch.stalled()
        if stalled is not None:
            self.facts["timeout"] = True
            self.facts["stalled"] = str(stalled)
            return True
        if now - self.last_beat >= self.beat:
            if self.streamed:
                self.request.heartbeat()
            self.streamed = False
            self.last_beat = now
        return False

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def capture_stream(self) -> float:
        """Consume nonblocking output until EOF, a usage wall or a timeout.

        Returns:
            The remaining bounded time for waiting on a child that closed stdout.

        """
        with selectors.DefaultSelector() as selector:
            os.set_blocking(self.stdin.fileno(), False)
            os.set_blocking(self.stdout.fileno(), False)
            selector.register(self.stdin, selectors.EVENT_WRITE)
            selector.register(self.stdout, selectors.EVENT_READ)
            done = False
            while not done and not self._tick():
                for key, _ in selector.select(timeout=min(0.2, self.idle, self.limit)):
                    if key.fileobj is self.stdin:
                        self._write(selector)
                    elif self._read():
                        done = True
                        break
        return max(0.01, min(self.limit - (time.monotonic() - self.beginning), self.idle))


class SessionProcesses:
    """Own active session groups and their cancellation attribution."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self) -> None:
        """Create a synchronized process registry for one dispatch."""
        self._lock = threading.Lock()
        self._live: dict[int, subprocess.Popen[bytes]] = {}
        self._stopped = False
        self._stop_cause: str = OTHER_CAUSE
        self._stop_resume_at: float | None = None
        self._cancelled: set[int] = set()

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def kill(process: subprocess.Popen[bytes]) -> None:
        """Terminate an owned process group, preserving the existing grace period."""
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError:
            # macOS briefly reports EPERM while a signalled child is exiting.
            pass
        grace = terminate_grace()
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                pass  # A persistent denial still fails SIGKILL below.
            time.sleep(0.05)
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def stop_all(self, *, cause: str = OTHER_CAUSE, resume_at: float | None = None) -> None:
        """Stop all registered sessions and retain the first cancellation cause."""
        with self._lock:
            if not self._stopped:
                self._stop_cause, self._stop_resume_at = cause, resume_at
            self._stopped = True
            live = list(self._live.values())
            self._cancelled.update(p.pid for p in live if p.poll() is None)
        for process in live:
            self.kill(process)

    def _launch(self, request: SessionRequest, errors: IO[bytes]) -> subprocess.Popen[bytes]:
        with self._lock:
            if self._stopped:
                stage = "session"
                raise StepError(
                    stage,
                    self._stop_cause,
                    ("run sessions have been stopped",),
                    resume_at=self._stop_resume_at,
                )
            process = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - Validated argv and explicit environment; no shell.
                request.argv,
                cwd=request.directory,
                env=request.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=errors,
                start_new_session=True,
            )
            self._live[process.pid] = process
            return process

    def _finish(self, process: subprocess.Popen[bytes], facts: SessionFacts, remaining: float) -> None:
        if facts["rate"] is not None or facts["timeout"]:
            self.kill(process)
        else:
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                facts["timeout"] = True
                self.kill(process)
        facts["exit"] = process.wait()
        facts["pid"] = process.pid
        with self._lock:
            if process.pid in self._cancelled:
                facts["cancelledCause"] = self._stop_cause
                facts["cancelledResumeAt"] = self._stop_resume_at

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self, request: SessionRequest) -> SessionFacts:
        """Capture one session and always clean up its process group.

        Returns:
            Validated session output and process/cancellation attribution.

        """
        request.stream.parent.mkdir(parents=True, exist_ok=True)
        with request.stream.open("wb") as capture, request.stream.with_suffix(".stderr").open("wb") as errors:
            process = self._launch(request, errors)
            facts: SessionFacts = {"result": None, "rate": None, "timeout": False, "exit": 0, "pid": process.pid}
            try:
                request.started(process.pid)
                stream = _StreamCapture(request, process, capture, facts, self._line)
                self._finish(process, facts, stream.capture_stream())
                return facts
            finally:
                # Includes MCP descendants left behind after the main CLI exits.
                self.kill(process)
                with self._lock:
                    self._live.pop(process.pid, None)
                for pipe in (process.stdin, process.stdout):
                    if pipe is not None and not pipe.closed:
                        pipe.close()

    @staticmethod
    def _line(line: bytes, facts: SessionFacts) -> dict[str, JsonValue] | None:
        try:
            event: object = json.loads(line)
        except ValueError, UnicodeError:
            return None
        if not isinstance(event, dict):
            return None
        value = json_object(event)
        if value.get("type") == "result":
            facts["result"] = value
        if value.get("type") == RATE_LIMIT_EVENT_TYPE:
            info: object = value.get(RATE_LIMIT_INFO_KEY)
            if isinstance(info, dict):
                rate: dict[str, JsonValue] = json_object(info)
                if rate.get("status") == REJECTED_STATUS:
                    facts["rate"] = rate
        return value
