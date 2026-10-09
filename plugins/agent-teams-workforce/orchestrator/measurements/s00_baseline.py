"""S00 baseline: read-only analysis of prd-to-spec cost records for one day.

Usage: python3 s00_baseline.py [YYYYMMDD]
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RUNS = Path("/Users/msat1971/projects/SkillSpoke/apps/personal-agent/SkillSpoke/ops/sdlc-automation/state/runs")
PROJECTS = Path.home() / ".claude-skillspoke" / "projects"
MIN_SAMPLE_SESSIONS = 5
TOP_ROLES = 15
MAX_TRANSCRIPTS = 400


def emit(*parts: object) -> None:
    """Write one line to stdout.

    Args:
        *parts: Values joined by single spaces.

    """
    sys.stdout.write(" ".join(str(part) for part in parts) + "\n")


def load_records(day: str) -> list[dict]:
    """Load the prd-to-spec cost records for one day.

    Args:
        day: The day as YYYYMMDD.

    Returns:
        The parsed cost records, in file name order.

    """
    records = []
    for path in sorted(RUNS.glob(f"*-prd-to-spec-{day}T*.cost.json")):
        with path.open(encoding="utf-8") as handle:
            records.append(json.load(handle))
    return records


def role_totals(records: list[dict]) -> dict[str, dict[str, int]]:
    """Sum weighted tokens, sessions and requests per role.

    Args:
        records: The cost records.

    Returns:
        A mapping of role name to its summed figures.

    """
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"weighted": 0, "sessions": 0, "requests": 0})
    for record in records:
        for role, entry in (record.get("roles") or {}).items():
            for key in ("weighted", "sessions", "requests"):
                totals[role][key] += entry.get(key) or 0
    return totals


def report_roles(records: list[dict], total: int) -> None:
    """Print the role table, the command-runner share and the survey-redo split.

    Args:
        records: The cost records.
        total: The total weighted tokens of all records.

    """
    roles = role_totals(records)
    emit("\nROLES (weighted, sessions, share)")
    for role, entry in sorted(roles.items(), key=lambda item: -item[1]["weighted"])[:TOP_ROLES]:
        emit(f"  {role}: {entry['weighted']} {entry['sessions']} {entry['weighted'] / total:.3%}")
    runner = [entry for role, entry in roles.items() if "workflow-command-runner" in role]
    runner_weighted = sum(entry["weighted"] for entry in runner)
    runner_sessions = sum(entry["sessions"] for entry in runner)
    all_sessions = sum(record.get("sessions") or 0 for record in records)
    emit(
        "\nRUNNER sessions",
        runner_sessions,
        "weighted",
        runner_weighted,
        "share",
        f"{runner_weighted / total:.3%}",
        "per session",
        round(runner_weighted / runner_sessions) if runner_sessions else None,
    )
    emit("runner share of sessions", f"{runner_sessions / all_sessions:.3%}")

    by_bead: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_bead[record["beadId"]].append(record)
    first = later = 0
    for runs in by_bead.values():
        runs.sort(key=lambda record: record.get("startedAt") or "")
        for index, record in enumerate(runs):
            reconciler = sum(
                entry.get("weighted") or 0
                for role, entry in (record.get("roles") or {}).items()
                if "prd-reality-reconciler" in role
            )
            if index == 0:
                first += reconciler
            else:
                later += reconciler
    emit("\nreconciler weighted: first run per bead", first, "later runs", later)
    emit("share of total: later", f"{later / total:.3%}", "all", f"{(first + later) / total:.3%}")
    emit("beads", {bead: len(runs) for bead, runs in by_bead.items()})
    emit("stages", sorted({record.get("stage") for record in records}))


def report_startup(records: list[dict]) -> None:
    """Print the first assistant turn usage of each agent transcript in one sample run.

    Args:
        records: The cost records.

    """
    sample = next(
        (r for r in records if (r.get("sessions") or 0) > MIN_SAMPLE_SESSIONS and r.get("sessionId")),
        None,
    )
    emit("\nsample run", sample["runLog"] if sample else None)
    if not sample:
        return
    found = list(PROJECTS.glob(f"*/{sample['sessionId']}"))
    emit("tree", found)
    if not found:
        return
    for transcript in sorted(found[0].rglob("agent-*.jsonl"))[:MAX_TRANSCRIPTS]:
        meta_path = transcript.with_name(transcript.name.removesuffix(".jsonl") + ".meta.json")
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            meta = {}
        with transcript.open(encoding="utf-8") as handle:
            for line in handle:
                if '"assistant"' not in line:
                    continue
                event = json.loads(line)
                if event.get("type") != "assistant":
                    continue
                usage = event["message"].get("usage") or {}
                emit(
                    meta.get("agentType"),
                    usage.get("input_tokens"),
                    usage.get("cache_creation_input_tokens"),
                    usage.get("cache_read_input_tokens"),
                    event["message"].get("model"),
                )
                break


def main() -> None:
    """Print the baseline figures for the day named on the command line."""
    day = sys.argv[1] if len(sys.argv) > 1 else "20261009"
    records = load_records(day)
    weights = [r["weighted"] for r in records if r.get("weighted") is not None]
    total = sum(weights)
    emit("runs", len(records), "with weighted", len(weights))
    emit("total weighted", total)
    emit("median weighted", statistics.median(weights))
    emit("mean weighted", round(statistics.mean(weights)))
    emit("sessions total", sum(r.get("sessions") or 0 for r in records))
    report_roles(records, total)
    report_startup(records)


if __name__ == "__main__":
    main()
