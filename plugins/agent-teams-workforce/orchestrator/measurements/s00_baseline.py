"""S00 baseline: read-only analysis of prd-to-spec run cost sidecars for one day.

Each sidecar is read and validated by the control repository's ``costsidecar.read_sidecar``,
which owns the ``costsidecar.CostSidecar`` contract; this script only sums the validated records.

Usage: python3 s00_baseline.py [YYYYMMDD]
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from driver_surface_types import CONTROL_REPO_ENV, DRIVER_DIR_PARTS
from orchestrator.core.driver_contracts import dispatch_arguments, driver_module
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.tools import env_path

type CostRecord = dict[str, JsonValue]

MIN_SAMPLE_SESSIONS: Final[int] = 5
TOP_ROLES: Final[int] = 15
MAX_TRANSCRIPTS: Final[int] = 400
DEFAULT_DAY: Final[str] = "20261009"
RUNNER_AGENT: Final[str] = "workflow-command-runner"
RECONCILER_AGENT: Final[str] = "prd-reality-reconciler"
_DAY_RE: Final[re.Pattern[str]] = re.compile(r"\d{8}")
_COUNTS: Final[tuple[str, ...]] = ("weighted", "sessions", "requests")


def _count(entry: Mapping[str, JsonValue], key: str) -> int | None:
    value: JsonValue = entry.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        message: str = f"token count {key} must be an integer or null, not {type(value).__name__}"
        raise TypeError(message)
    return value


def _text(entry: Mapping[str, JsonValue], key: str) -> str | None:
    value: JsonValue = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        message: str = f"field {key} must be a string or null, not {type(value).__name__}"
        raise TypeError(message)
    return value


def _roles(record: Mapping[str, JsonValue]) -> dict[str, CostRecord]:
    value: JsonValue = record.get("roles")
    if value is None:
        return {}
    return {role: json_object(entry) for role, entry in json_object(value).items()}


def _sessions(records: Sequence[CostRecord]) -> int:
    return sum(_count(record, "sessions") or 0 for record in records)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def emit(*parts: object) -> None:
    """Write one line to stdout.

    Args:
        *parts: Values joined by single spaces.

    """
    sys.stdout.write(" ".join(str(part) for part in parts) + "\n")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_records(day: str) -> list[CostRecord]:
    """Load the prd-to-spec run cost sidecars for one day through ``costsidecar.read_sidecar``.

    Args:
        day: The day as YYYYMMDD.

    Returns:
        The validated cost sidecars, in file name order.

    Raises:
        ValueError: The day is not YYYYMMDD; ``costsidecar.read_sidecar`` also raises when a sidecar
            does not match the contract or cannot be read.

    """
    if _DAY_RE.fullmatch(day) is None:
        message: str = f"day must be YYYYMMDD, not {day!r}"
        raise ValueError(message)
    costsidecar = driver_module("costsidecar")
    read_sidecar: Callable[[Path], object] = check_type(costsidecar.read_sidecar, Callable[[Path], object])
    suffix: str = check_type(costsidecar.COST_SUFFIX, str)
    flow: str = dispatch_arguments().FLOW_PRD_TO_SPEC
    runs: Path = env_path(CONTROL_REPO_ENV).joinpath(*DRIVER_DIR_PARTS, "state", "runs")
    records: list[CostRecord] = []
    path: Path
    for path in sorted(runs.glob(f"*-{flow}-{day}T*{suffix}")):
        record: object = read_sidecar(path)
        if record is not None:
            records.append(json_object(record))
    return records


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def role_totals(records: Sequence[CostRecord]) -> dict[str, dict[str, int]]:
    """Sum weighted tokens, sessions and requests per role; a null count adds nothing.

    Args:
        records: The validated cost sidecars.

    Returns:
        A mapping of role name to its summed figures.

    """
    totals: defaultdict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(_COUNTS, 0))
    for record in records:
        for role, entry in _roles(record).items():
            for key in _COUNTS:
                totals[role][key] += _count(entry, key) or 0
    return dict(totals)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def report_roles(records: Sequence[CostRecord], total: int) -> None:
    """Print the role table, the command-runner share and the survey-redo split.

    Each Epic's runs are ordered by their ``startedAt``; a run with no ``startedAt`` sorts last.

    Args:
        records: The validated cost sidecars.
        total: The total weighted tokens of all records.

    Raises:
        ValueError: A validated cost sidecar has no ``beadId``.

    """
    roles: dict[str, dict[str, int]] = role_totals(records)
    emit("\nROLES (weighted, sessions, share)")
    for role, entry in sorted(roles.items(), key=lambda item: -item[1]["weighted"])[:TOP_ROLES]:
        emit(f"  {role}: {entry['weighted']} {entry['sessions']} {entry['weighted'] / total if total else 0:.3%}")
    runner: list[dict[str, int]] = [entry for role, entry in roles.items() if RUNNER_AGENT in role]
    runner_weighted: int = sum(entry["weighted"] for entry in runner)
    runner_sessions: int = sum(entry["sessions"] for entry in runner)
    all_sessions: int = _sessions(records)
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

    by_bead: defaultdict[str, list[CostRecord]] = defaultdict(list)
    for record in records:
        bead: str | None = _text(record, "beadId")
        if bead is None:
            message: str = "a validated cost sidecar has no beadId"
            raise ValueError(message)
        by_bead[bead].append(record)
    first: int = 0
    later: int = 0
    for runs in by_bead.values():
        runs.sort(key=lambda record: (_text(record, "startedAt") is None, _text(record, "startedAt") or ""))
        for index, record in enumerate(runs):
            reconciler: int = sum(
                _count(entry, "weighted") or 0 for role, entry in _roles(record).items() if RECONCILER_AGENT in role
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
    emit("stages", sorted({_text(record, "stage") or "unknown" for record in records}))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def report_startup(records: Sequence[CostRecord]) -> None:
    """Print the first assistant turn usage of each agent transcript in one sample run.

    Args:
        records: The validated cost sidecars.

    """
    sample: CostRecord | None = next(
        (r for r in records if (_count(r, "sessions") or 0) > MIN_SAMPLE_SESSIONS and _text(r, "sessionId")),
        None,
    )
    emit("\nsample run", _text(sample, "runLog") if sample else None)
    if sample is None:
        return
    projects: Path = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))) / "projects"
    found: list[Path] = list(projects.glob(f"*/{_text(sample, 'sessionId')}"))
    emit("tree", found)
    if not found:
        return
    for transcript in sorted(found[0].rglob("agent-*.jsonl"))[:MAX_TRANSCRIPTS]:
        meta_path: Path = transcript.with_name(transcript.name.removesuffix(".jsonl") + ".meta.json")
        meta: CostRecord
        try:
            meta = json_object(json.loads(meta_path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            emit("no metadata for", transcript.name, exc)
            meta = {}
        with transcript.open(encoding="utf-8") as handle:
            for line in handle:
                if '"assistant"' not in line:
                    continue
                event: CostRecord = json_object(json.loads(line))
                if event.get("type") != "assistant":
                    continue
                message: CostRecord = json_object(event["message"])
                usage: CostRecord = json_object(message.get("usage") or {})
                emit(
                    meta.get("agentType"),
                    usage.get("input_tokens"),
                    usage.get("cache_creation_input_tokens"),
                    usage.get("cache_read_input_tokens"),
                    message.get("model"),
                )
                break


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Print the baseline figures for the day named on the command line."""
    day: str = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DAY
    records: list[CostRecord] = load_records(day)
    weights: list[int] = [weighted for r in records if (weighted := _count(r, "weighted")) is not None]
    total: int = sum(weights)
    emit("runs", len(records), "with weighted", len(weights))
    emit("total weighted", total)
    emit("median weighted", statistics.median(weights) if weights else None)
    emit("mean weighted", round(statistics.mean(weights)) if weights else None)
    emit("sessions total", _sessions(records))
    report_roles(records, total)
    report_startup(records)


if __name__ == "__main__":
    main()
