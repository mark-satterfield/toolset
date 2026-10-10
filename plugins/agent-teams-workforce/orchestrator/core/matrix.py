"""Read the build pipeline's matrix once; elaboration never sets build state."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator.core.tools import CommandResult

import fcntl
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import archmatrix
from typeguard import CollectionCheckStrategy, check_type, typechecked

from .io import JsonValue, json_object, write_json
from .models import RunContext, StepError
from .tool_locks import LockTimeoutError, control_repo, file_lock, seconds
from .tools import Tools


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def element_id(name: str) -> str:
    """Normalize the architecture element identity.

    Returns:
        The canonical element key.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(name, str)):
        argument_error: str = "element_id: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    return check_type(Tools(Path()).portfolio("matrix", archmatrix.element_id, name), str)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_snapshot(path: Path) -> dict[str, JsonValue]:
    """Read a validated matrix snapshot.

    Returns:
        The matrix JSON object.

    Raises:
        TypeError: An argument violates the declared input contract.
        StepError: The snapshot cannot be read.

    """
    if not (isinstance(path, Path)):
        argument_error: str = "read_snapshot: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    stage: str = "matrix"
    try:
        value: dict[str, JsonValue] = json_object(json.loads(path.read_text(encoding="utf-8")))
        json_object(value.get("elements"))
    except (OSError, ValueError, TypeError) as exc:
        raise StepError(stage, "other", (str(path), str(exc))) from exc
    else:
        return value


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def row_for(snapshot: dict[str, JsonValue], name: str) -> dict[str, JsonValue]:
    """Resolve an element row using the matrix identity rules.

    Returns:
        The resolved matrix row.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(snapshot, dict)) or not (isinstance(name, str)):
        argument_error: str = "row_for: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    return json_object(
        Tools(Path()).portfolio("matrix", archmatrix.row_of, snapshot, name),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def satisfied(snapshot: dict[str, JsonValue], row: dict[str, JsonValue]) -> bool:
    """Evaluate whether the row satisfies its build requirement.

    Returns:
        The verified satisfaction flag.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(snapshot, dict)) or not (isinstance(row, dict)):
        argument_error: str = "satisfied: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    return check_type(
        Tools(Path()).portfolio("matrix", archmatrix.satisfied, snapshot, row),
        bool,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def snapshot(context: RunContext, tools: Tools) -> Path:
    """Capture the matrix under its shared publication lock.

    Returns:
        The saved dispatch snapshot path.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(context, RunContext)) or not (isinstance(tools, Tools)):
        argument_error: str = "snapshot: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    stage: str = "matrix"
    root: Path = control_repo()
    source: Path = Path(
        os.environ.get(
            "ATW_ELEMENT_MATRIX",
            str(root / "ops/sdlc-automation/element-matrix.json"),
        ),
    )
    lock: Path = root / "ops/sdlc-automation/state/element-matrix.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)

    def read() -> dict[str, JsonValue]:
        deadline: float = time.monotonic() + seconds("ATW_MATRIX_LOCK_WAIT", 120)
        with lock.open("a", encoding="utf-8") as handle:
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise StepError(stage, "contention", (str(lock),)) from exc
                    time.sleep(0.1)
            try:
                result: dict[str, JsonValue] = read_snapshot(source)
                blob: CommandResult = tools.command(
                    ["git", "hash-object", str(source)],
                    cwd=root,
                    stage="matrix",
                )
                result["gitBlob"] = blob.stdout.strip()
                return result
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    target: Path = context.work / "matrix-snapshot.json"
    write_json(target, tools.operation("matrix", read))
    return target


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_seed(
    path: Path,
    root: Path,
    build: Callable[[dict[str, JsonValue]], dict[str, JsonValue]],
    publish: Callable[[], None] | None = None,
) -> dict[str, JsonValue]:
    """Merge under the reader lock and retain it through optional publication.

    Returns:
        The merged matrix object.

    Raises:
        TypeError: An argument violates the declared input contract.
        StepError: The publication lock times out.

    """
    if (
        not (isinstance(path, Path))
        or not (isinstance(root, Path))
        or not (callable(build))
        or not (callable(publish) or publish is None)
    ):
        argument_error: str = "write_seed: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    stage: str = "matrix"
    lock: Path = root / "ops/sdlc-automation/state/element-matrix.lock"
    try:
        with file_lock(lock, seconds("ATW_MATRIX_LOCK_WAIT", 120)):
            result: dict[str, JsonValue] = build(read_snapshot(path) if path.exists() else {})
            write_json(path, result)
            if publish is not None:
                publish()
            return result
    except LockTimeoutError as exc:
        raise StepError(stage, "contention", (str(lock),)) from exc
