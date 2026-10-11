"""The Epic run record ``<work>/run.json``: its one contract, reader and writers.

Only plugin Python code writes and reads this file. ``record_session`` upserts one
session row before a direct agent process starts; ``record_run`` writes the final
record of a flow. Both hold ``_LOCK`` and keep the keys of an existing record of the
same run.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from .artifacts import ArtifactStore
from .handback_contract import OTHER_CAUSE, Session
from .io import JsonValue, write_json
from .models import RunContext, StepError

RUN_MANIFEST_FILE: Final = "run.json"

_LOCK: Final = threading.Lock()


class RunManifest(TypedDict):
    """The Epic run record: one run of one composite flow for one Epic."""

    runId: str
    epicId: str
    composite: str
    sessions: list[Session]
    prdId: NotRequired[str | None]
    result: NotRequired[dict[str, JsonValue]]
    phases: NotRequired[dict[str, JsonValue]]
    notes: NotRequired[list[JsonValue]]


def manifest_path(work: Path) -> Path:
    """Locate the run record in an Epic work directory.

    Returns:
        ``<work>/run.json``.

    """
    return work / RUN_MANIFEST_FILE


def parse_manifest(value: object) -> RunManifest:
    """Validate a decoded run record against the contract, every item included.

    Returns:
        The validated run record.

    Raises:
        ValueError: The value drifts from the contract (a missing, extra or mistyped key).

    """
    try:
        return check_type(value, RunManifest, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    except TypeCheckError as exc:
        message: str = f"run record does not match the RunManifest contract: {exc}"
        raise ValueError(message) from exc


def read_manifest(path: Path) -> RunManifest | None:
    """Read and validate a run record.

    Returns:
        The validated run record, or None when the file does not exist.

    Raises:
        OSError: The file exists but cannot be read.
        ValueError: The file is not JSON or drifts from the contract.

    """
    if not path.exists():
        return None
    try:
        text: str = path.read_text(encoding="utf-8")
    except OSError as exc:
        read_error: str = f"cannot read run record {path}: {exc}"
        raise OSError(read_error) from exc
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as exc:
        decode_error: str = f"run record {path} is not JSON: {exc}"
        raise ValueError(decode_error) from exc
    return parse_manifest(decoded)


def _current(context: RunContext, target: Path) -> RunManifest:
    existing: RunManifest | None = read_manifest(target)
    if existing is not None and existing["runId"] == context.run_id:
        return existing
    return {"runId": context.run_id, "epicId": context.bead, "composite": context.flow, "sessions": []}


def _write(target: Path, manifest: RunManifest) -> None:
    write_json(target, parse_manifest(manifest))


def _update_manifest(context: RunContext, target: Path, row: Session) -> None:
    manifest: RunManifest = _current(context, target)
    sessions: dict[str, Session] = {entry["sessionId"]: entry for entry in manifest["sessions"]}
    sessions[row["sessionId"]] = row.copy()
    manifest["sessions"] = list(sessions.values())
    _write(target, manifest)
    context.sessions[:] = sessions.values()


def _finalize(target: Path, final: RunManifest) -> None:
    existing: RunManifest | None = read_manifest(target)
    if existing is not None and existing["runId"] == final["runId"]:
        final["sessions"] = existing["sessions"]
    _write(target, final)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_session(context: RunContext, store: ArtifactStore, row: Session) -> None:
    """Upsert a session row by its id, validating every existing row before preserving it.

    Raises:
        StepError: A session record could not be persisted.

    """
    target: Path = manifest_path(store.work)
    with _LOCK:
        try:
            _update_manifest(context, target, row)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise StepError(context.stage, OTHER_CAUSE, (f"cannot record session in {target}: {exc}",)) from exc


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_run(
    context: RunContext,
    prd_id: str | None,
    result: dict[str, JsonValue],
    phases: dict[str, JsonValue],
    notes: list[JsonValue],
) -> Path:
    """Write the final run record, merged into an existing record of the same run.

    The session rows already recorded for this run are kept; a fresh record takes
    the context's sessions.

    Returns:
        The path of the written run record.

    Raises:
        StepError: The run record could not be read, validated or written.

    """
    target: Path = manifest_path(context.work)
    final: RunManifest = {
        "runId": context.run_id,
        "epicId": context.bead,
        "composite": context.flow,
        "sessions": list(context.sessions),
        "prdId": prd_id,
        "result": result,
        "phases": phases,
        "notes": notes,
    }
    with _LOCK:
        try:
            _finalize(target, final)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise StepError(context.stage, OTHER_CAUSE, (f"cannot record run in {target}: {exc}",)) from exc
    return target
