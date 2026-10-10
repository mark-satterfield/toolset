"""Bounded check of parallel registration, resumed UUIDs and dispatch separation."""

from __future__ import annotations

import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.checks.check_support import report, require
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.manifest import record_session
from orchestrator.core.models import RunContext, SessionRecord


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        store = ArtifactStore(ModuleType("unused"), root, root, "epic", "run-one")
        context = RunContext("epic", "prd-to-spec", {}, root, "run-one")
        rows: list[SessionRecord] = [
            {
                "sessionId": str(i),
                "agent": "writer",
                "phase": "architecture",
                "cwd": str(root),
                "step": "survey",
                "effort": "medium",
                "model": "fable",
            }
            for i in range(8)
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda row: record_session(context, store, row), rows))
        resumed: SessionRecord = {**rows[0], "model": "opus"}
        record_session(context, store, resumed)
        payload = json.loads((root / "run.json").read_text())
        require(len(payload["sessions"]) == len(rows), "len(payload['sessions']) == len(rows)")
        require(len(context.sessions) == len(rows), "len(context.sessions) == len(rows)")
        require(
            next(row for row in payload["sessions"] if row["sessionId"] == "0")["model"] == "opus",
            "next((row for row in payload['sessions'] if row['sessionId'] == '0'))['model'] == 'opus'",
        )
        context.run_id = "run-two"
        record_session(context, store, {**rows[0], "sessionId": "new"})
        require(
            [row["sessionId"] for row in context.sessions] == ["new"],
            "[row['sessionId'] for row in context.sessions] == ['new']",
        )
    report("PASS: parallel manifest writes, resumed UUID upsert and separate dispatch attribution")


if __name__ == "__main__":
    main()
