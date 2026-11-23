"""The Epic run record ``<work>/run.json``: its one contract, reader and writers.

Only plugin Python code writes and reads this file. ``record_session`` upserts one
session row before a direct agent process starts; ``record_run`` writes the final
record of a flow. Both hold ``_LOCK`` and keep the keys of an existing record of the
same run. The record names the format it is written in (``formatVersion``); a record in an
older format is brought to the current one on read through :data:`RUN_MIGRATIONS`, and a
record without it is format 0.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from .handback_contract import OTHER_CAUSE, Session
from .io import JsonValue, write_json
from .models import RunContext, StepError

RUN_MANIFEST_FILE: Final = "run.json"

RUN_FORMAT_VERSION: Final = 1
"""The format :func:`record_session` and :func:`record_run` write."""
FORMAT_KEY: Final = "formatVersion"

_LOCK: Final = threading.Lock()


class RunManifest(TypedDict):
    """The Epic run record: one run of one composite flow for one Epic."""

    formatVersion: int
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


def _without_effort(record: dict[str, object]) -> dict[str, object]:
    """Bring a format 0 run record to format 1: drop ``effort``, which ``Session`` no longer defines.

    Returns:
        The record with each session row that is an object rebuilt without ``effort``, and
        ``formatVersion`` 1.

    """
    sessions: object = record.get("sessions")
    rows: object = (
        [
            {key: held for key, held in row.items() if key != "effort"} if isinstance(row, dict) else row
            for row in sessions
        ]
        if isinstance(sessions, list)
        else sessions
    )
    return {**record, "sessions": rows, FORMAT_KEY: 1}


type RunMigration = Callable[[dict[str, object]], dict[str, object]]

RUN_MIGRATIONS: Final[dict[int, RunMigration]] = {0: _without_effort}
"""For each older format, the change that brings a decoded run record of it to the next format."""


def migrated_manifest(value: object, where: str) -> object:
    """Bring a decoded run record written in an older format to the current one.

    Returns:
        The record in the current format; a value that is not an object, unchanged.

    Raises:
        ValueError: The record names a format that is not a whole number from 0 to
            :data:`RUN_FORMAT_VERSION`.

    """
    if not isinstance(value, dict):
        return value
    record: dict[str, object] = {str(key): held for key, held in value.items()}
    stated: object = record.get(FORMAT_KEY, 0)
    if isinstance(stated, bool) or not isinstance(stated, int) or not 0 <= stated <= RUN_FORMAT_VERSION:
        message: str = (
            f"run record {where} names the format {stated!r}; this plugin reads formats 0 to "
            f"{RUN_FORMAT_VERSION}, so a newer plugin wrote it"
        )
        raise ValueError(message)
    held: int
    for held in range(stated, RUN_FORMAT_VERSION):
        record = RUN_MIGRATIONS[held](record)
    return record


def read_manifest(path: Path) -> RunManifest | None:
    """Read and validate a run record, brought to the current format (:func:`migrated_manifest`).

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
    return parse_manifest(migrated_manifest(decoded, str(path)))


def _current(context: RunContext, target: Path) -> RunManifest:
    existing: RunManifest | None = read_manifest(target)
    if existing is not None and existing["runId"] == context.run_id:
        return existing
    return {
        "formatVersion": RUN_FORMAT_VERSION,
        "runId": context.run_id,
        "epicId": context.bead,
        "composite": context.flow,
        "sessions": [],
    }


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
def record_session(context: RunContext, row: Session) -> None:
    """Upsert a session row by its id, validating every existing row before preserving it.

    Raises:
        StepError: A session record could not be persisted.

    """
    target: Path = manifest_path(context.work)
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
        "formatVersion": RUN_FORMAT_VERSION,
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
