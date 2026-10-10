"""The driver's flock gate and the sync scripts' central mkdir lock."""

from __future__ import annotations

import fcntl
import logging
import os
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked

_LOG = logging.getLogger(__name__)


class LockTimeoutError(TimeoutError):
    """A measured lock wait expired, without interpreting a command's stderr."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def seconds(name: str, default: float) -> float:
    """Resolve a positive timeout from the process environment.

    Returns:
        The configured timeout in seconds.

    Raises:
        ValueError: The timeout is not positive and finite.

    """
    value = float(os.environ.get(name, default))
    message = f"{name} must be positive and finite"
    if not 0 < value < float("inf"):
        raise ValueError(message)
    return value


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def control_repo() -> Path:
    """Resolve the shared control repository for all lock clients.

    Returns:
        The configured repository path.

    Raises:
        ValueError: The control repository variable is missing.

    """
    value = os.environ.get("ATW_CONTROL_REPO", "").strip()
    message = "ATW_CONTROL_REPO is required"
    if not value:
        raise ValueError(message)
    return Path(value).expanduser().resolve()


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def file_lock(path: Path, wait: float) -> Generator[None]:
    """Acquire an exclusive flock with a bounded wait.

    Yields:
        Control while the exclusive lock is held.

    Raises:
        LockTimeoutError: The measured wait limit expires.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait
    with path.open("a", encoding="utf-8") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(str(path)) from exc
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def central_lock(wait: float) -> Generator[None]:
    """Use the sync scripts' mkdir/pid protocol, including dead-owner recovery.

    Yields:
        Control while the central lock is held.

    Raises:
        LockTimeoutError: The measured wait limit expires.

    """
    path = Path(
        os.environ.get("CENTRAL_BEADS_LOCK") or str(Path(tempfile.gettempdir()) / "skillspoke-central-beads.lock"),
    )
    deadline = time.monotonic() + wait
    while True:
        try:
            path.mkdir()
            break
        except FileExistsError as existing:
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
                    _LOG.debug("Another waiter removed expired lock %s", path)
                continue
            except (FileNotFoundError, ValueError, PermissionError) as exc:
                _LOG.debug("Lock owner remains unverified for %s: %s", path, exc)
            if time.monotonic() >= deadline:
                raise LockTimeoutError(str(path)) from existing
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    try:
        (path / "pid").write_text(str(os.getpid()), encoding="utf-8")
        yield
    finally:
        (path / "pid").unlink(missing_ok=True)
        path.rmdir()


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def bd_gate(*, write: bool) -> Generator[None]:
    """Take the driver gate before the central write lock, in one fixed order.

    Yields:
        Control while the requested gates are held.

    """
    wait = seconds("ATW_BD_LOCK_WAIT", 120)
    with file_lock(control_repo() / "ops/sdlc-automation/state/bd-gate.lock", wait):
        if write:
            with central_lock(wait):
                yield
        else:
            yield
