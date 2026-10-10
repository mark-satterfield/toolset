"""Persist validated session attribution before a direct agent process starts."""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

from typeguard import CollectionCheckStrategy, check_type, typechecked

from .artifacts import ArtifactStore
from .io import json_object, write_json
from .models import RunContext, SessionRecord, StepError

if TYPE_CHECKING:
    from pathlib import Path

_LOCK = threading.Lock()


def _update_manifest(context: RunContext, target: Path, row: SessionRecord) -> None:
    payload = json_object(json.loads(target.read_text(encoding="utf-8"))) if target.exists() else {}
    if payload.get("runId") != context.run_id:
        payload = {"runId": context.run_id, "epicId": context.bead, "composite": context.flow}
    previous = check_type(
        payload.get("sessions", []),
        list[SessionRecord],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    sessions = {entry["sessionId"]: entry for entry in previous}
    sessions[row["sessionId"]] = row.copy()
    payload["sessions"] = [json_object(dict(entry)) for entry in sessions.values()]
    write_json(target, payload)
    context.sessions[:] = sessions.values()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_session(context: RunContext, store: ArtifactStore, row: SessionRecord) -> None:
    """Upsert a UUID and validate all existing records before preserving them.

    Raises:
        StepError: A session record could not be persisted.

    """
    target = store.work / "run.json"
    with _LOCK:
        try:
            _update_manifest(context, target, row)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise StepError(context.stage, "other", (f"cannot record session in {target}: {exc}",)) from exc
