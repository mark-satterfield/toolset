"""Read the build pipeline's matrix once; elaboration never sets build state."""

from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path

from .io import write_json
from .models import RunContext, StepError
from .tool_locks import control_repo, seconds
from .tools import Tools


def element_id(name: str) -> str:
    return Tools(Path(".")).portfolio("archmatrix", "element_id", name, stage="matrix")


def read_snapshot(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("elements"), dict):
            raise TypeError("matrix must contain an elements object")
        return value
    except (OSError, ValueError, TypeError) as exc:
        raise StepError("matrix", "other", (str(path), str(exc))) from exc


def row_for(snapshot: dict, name: str) -> dict:
    return snapshot["elements"].get(element_id(name), {})


def satisfied(snapshot: dict, row: dict) -> bool:
    return Tools(Path(".")).portfolio(
        "archmatrix", "satisfied", snapshot, row, stage="matrix"
    )


def snapshot(context: RunContext, tools: Tools) -> Path:
    root = control_repo()
    source = Path(
        os.environ.get(
            "ATW_ELEMENT_MATRIX", str(root / "ops/sdlc-automation/element-matrix.json")
        )
    )
    lock = root / "ops/sdlc-automation/state/element-matrix.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)

    def read() -> dict:
        deadline = time.monotonic() + seconds("ATW_MATRIX_LOCK_WAIT", 120)
        with lock.open("a", encoding="utf-8") as handle:
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise StepError("matrix", "contention", (str(lock),)) from exc
                    time.sleep(0.1)
            try:
                result = read_snapshot(source)
                blob = tools.command(
                    ["git", "hash-object", str(source)], cwd=root, stage="matrix"
                )
                result["gitBlob"] = blob.stdout.strip()
                return result
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    target = context.work / "matrix-snapshot.json"
    write_json(target, tools.operation("matrix", read))
    return target
