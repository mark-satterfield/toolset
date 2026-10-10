"""Read the build pipeline's matrix once; elaboration never sets build state."""

from __future__ import annotations

import fcntl
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

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

    """
    return check_type(Tools(Path()).portfolio("archmatrix", "element_id", name, stage="matrix"), str)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_snapshot(path: Path) -> dict[str, JsonValue]:
    """Read a validated matrix snapshot.

    Returns:
        The matrix JSON object.

    Raises:
        StepError: The snapshot cannot be read.

    """
    stage = "matrix"
    try:
        value = json_object(json.loads(path.read_text(encoding="utf-8")))
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

    """
    return json_object(
        Tools(Path()).portfolio(
            "archmatrix",
            "row_of",
            snapshot,
            name,
            stage="matrix",
        ),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def satisfied(snapshot: dict[str, JsonValue], row: dict[str, JsonValue]) -> bool:
    """Evaluate whether the row satisfies its build requirement.

    Returns:
        The verified satisfaction flag.

    """
    return check_type(
        Tools(Path()).portfolio(
            "archmatrix",
            "satisfied",
            snapshot,
            row,
            stage="matrix",
        ),
        bool,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def snapshot(context: RunContext, tools: Tools) -> Path:
    """Capture the matrix under its shared publication lock.

    Returns:
        The saved dispatch snapshot path.

    """
    stage = "matrix"
    root = control_repo()
    source = Path(
        os.environ.get(
            "ATW_ELEMENT_MATRIX",
            str(root / "ops/sdlc-automation/element-matrix.json"),
        ),
    )
    lock = root / "ops/sdlc-automation/state/element-matrix.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)

    def read() -> dict[str, JsonValue]:
        deadline = time.monotonic() + seconds("ATW_MATRIX_LOCK_WAIT", 120)
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
                result = read_snapshot(source)
                blob = tools.command(
                    ["git", "hash-object", str(source)],
                    cwd=root,
                    stage="matrix",
                )
                result["gitBlob"] = blob.stdout.strip()
                return result
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    target = context.work / "matrix-snapshot.json"
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
        StepError: The publication lock times out.

    """
    stage = "matrix"
    lock = root / "ops/sdlc-automation/state/element-matrix.lock"
    try:
        with file_lock(lock, seconds("ATW_MATRIX_LOCK_WAIT", 120)):
            result = build(read_snapshot(path) if path.exists() else {})
            write_json(path, result)
            if publish is not None:
                publish()
            return result
    except LockTimeoutError as exc:
        raise StepError(stage, "contention", (str(lock),)) from exc
