"""The driver's flock gate and the sync scripts' central mkdir lock."""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class LockTimeout(TimeoutError):
    """A measured lock wait expired, without interpreting a command's stderr."""


def seconds(name: str, default: float) -> float:
    """Resolve a positive timeout from the process environment."""
    value = float(os.environ.get(name, default))
    if not 0 < value < float("inf"):
        raise ValueError(f"{name} must be positive and finite")
    return value


def control_repo() -> Path:
    """Require the shared control repository rather than locking an arbitrary cwd."""
    value = os.environ.get("ATW_CONTROL_REPO", "").strip()
    if not value:
        raise ValueError("ATW_CONTROL_REPO is required")
    return Path(value).expanduser().resolve()


@contextmanager
def file_lock(path: Path, wait: float) -> Iterator[None]:
    """Acquire an exclusive flock with a bounded wait, releasing on every escape."""
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait
    with path.open("a", encoding="utf-8") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise LockTimeout(str(path)) from exc
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def central_lock(wait: float) -> Iterator[None]:
    """Use the sync scripts' mkdir/pid protocol, including dead-owner recovery."""
    path = Path(
        os.environ.get("CENTRAL_BEADS_LOCK")
        or str(Path(os.environ.get("TMPDIR", "/tmp")) / "skillspoke-central-beads.lock")
    )
    deadline = time.monotonic() + wait
    while True:
        try:
            path.mkdir()
            break
        except FileExistsError:
            try:
                pid = int((path / "pid").read_text(encoding="utf-8").strip())
                if pid > 0:
                    os.kill(pid, 0)
            except ProcessLookupError:
                # Another contender may have removed it first. Never recursively delete.
                try:
                    (path / "pid").unlink()
                    path.rmdir()
                except FileNotFoundError:
                    pass
                continue
            except (FileNotFoundError, ValueError, PermissionError):
                pass
            if time.monotonic() >= deadline:
                raise LockTimeout(str(path))
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    try:
        (path / "pid").write_text(str(os.getpid()), encoding="utf-8")
        yield
    finally:
        (path / "pid").unlink(missing_ok=True)
        path.rmdir()


@contextmanager
def bd_gate(*, write: bool) -> Iterator[None]:
    """Take the driver gate before the central write lock, in one fixed order."""
    wait = seconds("ATW_BD_LOCK_WAIT", 120)
    with file_lock(control_repo() / "ops/sdlc-automation/state/bd-gate.lock", wait):
        if write:
            with central_lock(wait):
                yield
        else:
            yield
