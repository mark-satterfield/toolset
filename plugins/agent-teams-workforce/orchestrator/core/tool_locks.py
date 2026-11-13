"""The bounded file lock around the pipeline's blocking-edge write, and the timeouts its callers read."""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from . import portfolio_bootstrap  # ruff: ignore[unused-import] -- sets sys.path

# isort: split
from driver_surface_types import CONTROL_REPO_ENV
from typeguard import CollectionCheckStrategy, typechecked

#: The characters of a holder's command kept in the lock file.
HOLDER_KEPT = 200


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
    value: str = os.environ.get(CONTROL_REPO_ENV, "").strip()
    message: str = f"{CONTROL_REPO_ENV} is required"
    if not value:
        raise ValueError(message)
    return Path(value).expanduser().resolve()


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def file_lock(path: Path, wait: float, holder: str | None = None) -> Generator[None]:
    """Acquire an exclusive flock with a bounded wait.

    With ``holder``, the lock file names this process and what it runs (``<pid> <holder>``)
    while the lock is held, so a waiter that times out can name the holder.

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
            if holder is not None:
                handle.truncate(0)
                handle.write(f"{os.getpid()} {' '.join(holder.split())[:HOLDER_KEPT]}\n")
                handle.flush()
            yield
        finally:
            if holder is not None:
                handle.truncate(0)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


#: The lock file of the blocking-edge write, under the control repository.
EDGE_LOCK: Final[str] = "ops/sdlc-automation/state/bd-edges.lock"

#: Seconds an edge-lock waiter allows beyond the holder's two `bd` calls.
EDGE_LOCK_MARGIN: Final[float] = 30.0


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def edge_lock(command: str) -> Generator[None]:
    """Hold the one lock the pipeline's `bd` calls take: around a blocking-edge write.

    The holder reads every blocking edge, checks in Python that no new edge closes a cycle and
    adds the edges. Two processes doing that at once could each add an edge that is safe alone
    and close a cycle together, so that read, check and write run one process at a time. Every
    other `bd` call runs unlocked: the shared Dolt server takes concurrent writers itself. The
    holder makes two `bd` calls, each bounded by `ATW_BD_TIMEOUT`, so a waiter waits longer than
    both. The lock file names the holder (`<pid> <command>`) while it is held.

    Yields:
        Control while the lock is held.

    """
    wait: float = 2 * seconds("ATW_BD_TIMEOUT", 180) + EDGE_LOCK_MARGIN
    with file_lock(control_repo() / EDGE_LOCK, wait, command):
        yield


#: The lock file of a Task bead write that claims matrix entries for its Epic, under the control repository.
OWNERSHIP_LOCK: Final[str] = "ops/sdlc-automation/state/bd-ownership.lock"


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def ownership_lock(command: str) -> Generator[None]:
    """Hold the lock around a Task bead write that claims matrix entries (``builds_entries``).

    The holder reads every Task, checks that no other Epic came to own an entry its Epic planned
    to build, and writes the Task bead. Two Epics elaborated at once could each find an entry
    unowned and both claim it, so that read, check and write run one process at a time. The
    holder makes a read of every bead and the `bd` calls of one Task write, each bounded by
    `ATW_BD_TIMEOUT`; a waiter allows several of them. The lock file names the holder.

    Yields:
        Control while the lock is held.

    """
    wait: float = 4 * seconds("ATW_BD_TIMEOUT", 180) + EDGE_LOCK_MARGIN
    with file_lock(control_repo() / OWNERSHIP_LOCK, wait, command):
        yield
