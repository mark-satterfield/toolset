"""Persist session attribution before a direct agent process starts."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .artifacts import ArtifactStore
from .models import RunContext, StepError

_LOCK = threading.Lock()


def record_session(
    context: RunContext, store: ArtifactStore, row: dict[str, Any]
) -> None:
    """Upsert one UUID, including model changes on a resumed session."""
    target = store.work / "run.json"
    with _LOCK:
        temporary: str | None = None
        try:
            payload = json.loads(target.read_text()) if target.exists() else {}
            if payload.get("runId") != context.run_id:
                payload = {
                    "runId": context.run_id,
                    "epicId": context.bead,
                    "composite": context.flow,
                }
            sessions = {
                entry["sessionId"]: entry for entry in payload.get("sessions", [])
            }
            sessions[row["sessionId"]] = dict(row)
            payload["sessions"] = list(sessions.values())
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", dir=target.parent, delete=False
            ) as handle:
                temporary = handle.name
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            os.replace(temporary, target)
            context.sessions[:] = payload["sessions"]
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise StepError(
                context.stage, "other", (f"cannot record session in {target}: {exc}",)
            ) from exc
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
