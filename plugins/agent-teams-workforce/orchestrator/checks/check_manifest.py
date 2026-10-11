"""Bounded check of parallel registration, resumed UUIDs, final-record merge and dispatch separation."""

from __future__ import annotations

import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
# The composite contract is generated into its skill, its one definition.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from composites_contract import PRD_TO_SPEC
from orchestrator.checks.check_support import report, require
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.handback_contract import Session  # ruff: ignore[typing-only-third-party-import] - typeguard @typechecked resolves this at runtime.
from orchestrator.core.io import JsonValue  # ruff: ignore[typing-only-third-party-import] - typeguard @typechecked resolves this at runtime.
from orchestrator.core.manifest import RunManifest, manifest_path, read_manifest, record_run, record_session
from orchestrator.core.models import RunContext

# Any phase the prd-to-spec composite declares serves; the record does not interpret it.
from orchestrator.flows.architecture_support import ARCHITECTURE_PHASE


def _manifest(path: Path) -> RunManifest:
    """Read the run record the check just wrote.

    Returns:
        The validated run record.

    Raises:
        ValueError: The run record is absent.

    """
    manifest: RunManifest | None = read_manifest(path)
    if manifest is None:
        message: str = f"run record {path} was not written"
        raise ValueError(message)
    return manifest


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract."""
    with tempfile.TemporaryDirectory() as temporary:
        root: Path = Path(temporary)
        store: ArtifactStore = ArtifactStore(load_artifactio(), root, root, "epic", "run-one")
        context: RunContext = RunContext("epic", PRD_TO_SPEC, {}, root, "run-one")
        target: Path = manifest_path(root)
        rows: list[Session] = [
            {
                "sessionId": str(i),
                "agent": "writer",
                "phase": ARCHITECTURE_PHASE,
                "cwd": str(root),
                "step": "survey",
                "effort": "medium",
                "model": "fable",
            }
            for i in range(8)
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda row: record_session(context, store, row), rows))
        resumed: Session = {**rows[0], "model": "opus"}
        record_session(context, store, resumed)
        recorded: RunManifest = _manifest(target)
        require(len(recorded["sessions"]) == len(rows), "len(recorded['sessions']) == len(rows)")
        require(len(context.sessions) == len(rows), "len(context.sessions) == len(rows)")
        require(
            next(row for row in recorded["sessions"] if row["sessionId"] == "0")["model"] == "opus",
            "the resumed session row carries the resumed model",
        )
        result: dict[str, JsonValue] = {"ok": True}
        phases: dict[str, JsonValue] = {ARCHITECTURE_PHASE: "done"}
        notes: list[JsonValue] = ["final"]
        written: Path = record_run(context, "prd-one", result, phases, notes)
        require(written == target, "record_run writes the run record at manifest_path")
        record_session(context, store, {**rows[1], "model": "opus"})
        merged: RunManifest = _manifest(target)
        require(merged.get("prdId") == "prd-one", "prdId survives a later session upsert")
        require(merged.get("result") == result, "result survives a later session upsert")
        require(merged.get("phases") == phases, "phases survive a later session upsert")
        require(merged.get("notes") == notes, "notes survive a later session upsert")
        require(len(merged["sessions"]) == len(rows), "the final record keeps every session row")
        context.run_id = "run-two"
        record_session(context, store, {**rows[0], "sessionId": "new"})
        require(
            [row["sessionId"] for row in context.sessions] == ["new"],
            "[row['sessionId'] for row in context.sessions] == ['new']",
        )
    report("PASS: parallel manifest writes, resumed UUID upsert, final-record merge and separate dispatch attribution")


if __name__ == "__main__":
    main()
