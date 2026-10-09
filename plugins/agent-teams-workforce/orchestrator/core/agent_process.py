"""Bounded stream capture and process-group cleanup for direct agent sessions."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .agent_context import driver_module


class SessionProcesses:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._live: dict[int, subprocess.Popen] = {}
        self._stopped = False

    @staticmethod
    def kill(process: subprocess.Popen) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError:
            # macOS briefly reports EPERM while a signalled child is exiting.
            pass
        deadline = time.monotonic() + driver_module("childproc").TERMINATE_GRACE
        while time.monotonic() < deadline:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                pass  # Keep waiting; a persistent denial still fails SIGKILL below.
            time.sleep(0.05)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

    def stop_all(self) -> None:
        with self._lock:
            self._stopped = True
            live = list(self._live.values())
        for process in live:
            self.kill(process)

    def run(
        self,
        argv: list[str],
        prompt: str,
        directory: Path,
        env: dict[str, str],
        stream: Path,
        started: Callable[[int], None],
        heartbeat: Callable[[], None],
    ) -> dict[str, Any]:
        idle = float(env.get("ATW_SESSION_IDLE", "1800"))
        limit = float(env.get("ATW_SESSION_LIMIT", "7200"))
        beat = float(env.get("ATW_HEARTBEAT", "300"))
        stream.parent.mkdir(parents=True, exist_ok=True)
        facts: dict[str, Any] = {"result": None, "rate": None, "timeout": False}
        with (
            stream.open("wb") as capture,
            stream.with_suffix(".stderr").open("wb") as errors,
        ):
            with self._lock:
                if self._stopped:
                    raise InterruptedError("run sessions have been stopped")
                process = subprocess.Popen(
                    argv,
                    cwd=directory,
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=errors,
                    start_new_session=True,
                )
                self._live[process.pid] = process
            try:
                started(process.pid)
                # The fact-only brief is small; nonblocking IO also bounds a child that never reads it.
                with selectors.DefaultSelector() as selector:
                    os.set_blocking(process.stdin.fileno(), False)
                    os.set_blocking(process.stdout.fileno(), False)
                    selector.register(process.stdin, selectors.EVENT_WRITE)
                    selector.register(process.stdout, selectors.EVENT_READ)
                    pending = prompt.encode("utf-8")
                    buffer = b""
                    beginning = last_line = last_beat = time.monotonic()
                    streamed = False
                    done = False
                    while not done:
                        now = time.monotonic()
                        if now - beginning >= limit or now - last_line >= idle:
                            facts["timeout"] = True
                            break
                        if now - last_beat >= beat:
                            if streamed:
                                heartbeat()
                            streamed = False
                            last_beat = now
                        for key, _ in selector.select(timeout=min(0.2, idle, limit)):
                            if key.fileobj is process.stdin:
                                try:
                                    count = os.write(process.stdin.fileno(), pending)
                                    pending = pending[count:]
                                except BrokenPipeError:
                                    pending = b""
                                if not pending:
                                    selector.unregister(process.stdin)
                                    process.stdin.close()
                                continue
                            chunk = os.read(process.stdout.fileno(), 65536)
                            if not chunk:
                                if buffer:
                                    self._line(buffer, facts)
                                done = True
                                break
                            capture.write(chunk)
                            capture.flush()
                            buffer += chunk
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                last_line = time.monotonic()
                                streamed = True
                                self._line(line, facts)
                                if facts["rate"] is not None:
                                    done = True
                                    break
                            if done:
                                break
                    if facts["rate"] is not None or facts["timeout"]:
                        self.kill(process)
                    else:
                        # A child can close stdout and then hang; the wall-clock limit still applies.
                        try:
                            process.wait(
                                timeout=max(
                                    0.01,
                                    min(limit - (time.monotonic() - beginning), idle),
                                )
                            )
                        except subprocess.TimeoutExpired:
                            facts["timeout"] = True
                            self.kill(process)
                facts.update(exit=process.wait(), pid=process.pid)
                return facts
            finally:
                # Includes MCP descendants left behind after the main CLI exits.
                self.kill(process)
                with self._lock:
                    self._live.pop(process.pid, None)
                if not process.stdin.closed:
                    process.stdin.close()
                process.stdout.close()

    @staticmethod
    def _line(line: bytes, facts: dict[str, Any]) -> None:
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            return
        if not isinstance(event, dict):
            return
        if event.get("type") == "result":
            facts["result"] = event
        if event.get("type") == "rate_limit_event":
            info = event.get("rate_limit_info")
            if isinstance(info, dict) and info.get("status") == "rejected":
                facts["rate"] = info
