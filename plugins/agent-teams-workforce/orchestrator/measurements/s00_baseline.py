"""S00 baseline: read-only analysis of prd-to-spec cost records for one day.

Usage: python3 s00_baseline.py [YYYYMMDD]
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.tools import env_path

MIN_SAMPLE_SESSIONS = 5
TOP_ROLES = 15
MAX_TRANSCRIPTS = 400


def _number(record: dict[str, JsonValue], key: str) -> int:
    return check_type(record.get(key) or 0, int)


def _roles(record: dict[str, JsonValue]) -> dict[str, dict[str, JsonValue]]:
    return check_type(
        record.get("roles") or {},
        dict[str, dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def emit(*parts: object) -> None:
    """Write one line to stdout.

    Args:
        *parts: Values joined by single spaces.

    """
    sys.stdout.write(" ".join(str(part) for part in parts) + "\n")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_records(day: str) -> list[dict[str, JsonValue]]:
    """Load the prd-to-spec cost records for one day.

    Args:
        day: The day as YYYYMMDD.

    Returns:
        The parsed cost records, in file name order.

    """
    records = []
    for path in sorted(
        (env_path("ATW_CONTROL_REPO") / "ops/sdlc-automation/state/runs").glob(f"*-prd-to-spec-{day}T*.cost.json"),
    ):
        with path.open(encoding="utf-8") as handle:
            records.append(json_object(json.load(handle)))
    return records


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def role_totals(records: list[dict[str, JsonValue]]) -> dict[str, dict[str, int]]:
    """Sum weighted tokens, sessions and requests per role.

    Args:
        records: The cost records.

    Returns:
        A mapping of role name to its summed figures.

    """
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"weighted": 0, "sessions": 0, "requests": 0})
    for record in records:
        for role, entry in _roles(record).items():
            for key in ("weighted", "sessions", "requests"):
                totals[role][key] += _number(entry, key)
    return totals


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def report_roles(records: list[dict[str, JsonValue]], total: int) -> None:
    """Print the role table, the command-runner share and the survey-redo split.

    Args:
        records: The cost records.
        total: The total weighted tokens of all records.

    """
    roles = role_totals(records)
    emit("\nROLES (weighted, sessions, share)")
    for role, entry in sorted(roles.items(), key=lambda item: -item[1]["weighted"])[:TOP_ROLES]:
        emit(f"  {role}: {entry['weighted']} {entry['sessions']} {entry['weighted'] / total if total else 0:.3%}")
    runner = [entry for role, entry in roles.items() if "workflow-command-runner" in role]
    runner_weighted = sum(entry["weighted"] for entry in runner)
    runner_sessions = sum(entry["sessions"] for entry in runner)
    all_sessions = sum(_number(record, "sessions") for record in records)
    emit(
        "\nRUNNER sessions",
        runner_sessions,
        "weighted",
        runner_weighted,
        "share",
        f"{runner_weighted / total if total else 0:.3%}",
        "per session",
        round(runner_weighted / runner_sessions) if runner_sessions else None,
    )
    emit("runner share of sessions", f"{runner_sessions / all_sessions if all_sessions else 0:.3%}")

    by_bead: dict[str, list[dict[str, JsonValue]]] = defaultdict(list)
    for record in records:
        by_bead[check_type(record["beadId"], str)].append(record)
    first = later = 0
    for runs in by_bead.values():
        runs.sort(key=lambda record: check_type(record.get("startedAt") or "", str))
        for index, record in enumerate(runs):
            reconciler = sum(
                _number(entry, "weighted") for role, entry in _roles(record).items() if "prd-reality-reconciler" in role
            )
            if index == 0:
                first += reconciler
            else:
                later += reconciler
    emit("\nreconciler weighted: first run per bead", first, "later runs", later)
    emit(
        "share of total: later",
        f"{later / total if total else 0:.3%}",
        "all",
        f"{(first + later) / total if total else 0:.3%}",
    )
    emit("beads", {bead: len(runs) for bead, runs in by_bead.items()})
    emit("stages", sorted({check_type(record.get("stage") or "unknown", str) for record in records}))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def report_startup(records: list[dict[str, JsonValue]]) -> None:
    """Print the first assistant turn usage of each agent transcript in one sample run.

    Args:
        records: The cost records.

    """
    sample = next(
        (r for r in records if (_number(r, "sessions")) > MIN_SAMPLE_SESSIONS and r.get("sessionId")),
        None,
    )
    emit("\nsample run", sample["runLog"] if sample else None)
    if not sample:
        return
    projects = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))) / "projects"
    found = list(projects.glob(f"*/{sample['sessionId']}"))
    emit("tree", found)
    if not found:
        return
    for transcript in sorted(found[0].rglob("agent-*.jsonl"))[:MAX_TRANSCRIPTS]:
        meta_path = transcript.with_name(transcript.name.removesuffix(".jsonl") + ".meta.json")
        try:
            meta = json_object(json.loads(meta_path.read_text(encoding="utf-8")))
        except OSError, ValueError:
            meta = {}
        with transcript.open(encoding="utf-8") as handle:
            for line in handle:
                if '"assistant"' not in line:
                    continue
                event = json_object(json.loads(line))
                if event.get("type") != "assistant":
                    continue
                usage = json_object(json_object(event["message"]).get("usage") or {})
                emit(
                    meta.get("agentType"),
                    usage.get("input_tokens"),
                    usage.get("cache_creation_input_tokens"),
                    usage.get("cache_read_input_tokens"),
                    json_object(event["message"]).get("model"),
                )
                break


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Print the baseline figures for the day named on the command line."""
    day = sys.argv[1] if len(sys.argv) > 1 else "20261009"
    records = load_records(day)
    weights = [check_type(r["weighted"], int) for r in records if r.get("weighted") is not None]
    total = sum(weights)
    emit("runs", len(records), "with weighted", len(weights))
    emit("total weighted", total)
    emit("median weighted", statistics.median(weights) if weights else None)
    emit("mean weighted", round(statistics.mean(weights)) if weights else None)
    emit("sessions total", sum(_number(r, "sessions") for r in records))
    report_roles(records, total)
    report_startup(records)


if __name__ == "__main__":
    main()
