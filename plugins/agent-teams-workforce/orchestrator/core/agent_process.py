"""Bounded stream capture and process-group cleanup for direct agent sessions."""

from __future__ import annotations

import json
import math
import os
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

from .agent_context import driver_module
from .io import json_object
from .models import SessionFacts, StepError


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
        for key, default in (("ATW_SESSION_IDLE", "1800"), ("ATW_SESSION_LIMIT", "7200"), ("ATW_HEARTBEAT", "300")):
            _duration(self.env, key, default)


class _StreamCapture:
    def __init__(
        self,
        request: SessionRequest,
        process: subprocess.Popen[bytes],
        capture: IO[bytes],
        facts: SessionFacts,
        parse_line: Callable[[bytes, SessionFacts], None],
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
        self.idle = _duration(request.env, "ATW_SESSION_IDLE", "1800")
        self.limit = _duration(request.env, "ATW_SESSION_LIMIT", "7200")
        self.beat = _duration(request.env, "ATW_HEARTBEAT", "300")

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
                self.parse_line(self.buffer, self.facts)
            return True
        self.capture.write(chunk)
        self.capture.flush()
        self.buffer += chunk
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            self.last_line = time.monotonic()
            self.streamed = True
            self.parse_line(line, self.facts)
            if self.facts["rate"] is not None:
                return True
        return False

    def _tick(self) -> bool:
        now = time.monotonic()
        if now - self.beginning >= self.limit or now - self.last_line >= self.idle:
            self.facts["timeout"] = True
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
        self._stop_cause = "other"
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
        grace = check_type(driver_module("childproc").TERMINATE_GRACE, int | float)
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
    def stop_all(self, *, cause: str = "other", resume_at: float | None = None) -> None:
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
    def _line(line: bytes, facts: SessionFacts) -> None:
        try:
            event: object = json.loads(line)
        except ValueError, UnicodeError:
            return
        if not isinstance(event, dict):
            return
        value = json_object(event)
        if value.get("type") == "result":
            facts["result"] = value
        if value.get("type") == "rate_limit_event":
            info = value.get("rate_limit_info")
            if isinstance(info, dict) and info.get("status") == "rejected":
                facts["rate"] = info
