"""Findings: problems a check found that no longer stop the item that found them.

A check that has spent its bounded correction attempts, or that finds a problem another Epic owns,
records the problem as a finding and lets the step continue. One finding is one JSON line in
``<artifacts root>/<owner Epic>/findings.jsonl`` (the owner Epic is the owner bead id cut at its
first ``.``), appended under an exclusive lock on the file, with exactly the fields of
:data:`Finding`. The driver writes the same file with the same fields (``source`` ``driver``).

For each finding the dispatch's event sink receives a ``warning`` note,
``finding for <owner> (<kind>): <detail>``, which the driver records with the run's phase events.
"""

from __future__ import annotations

import fcntl
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

from .events import EventSink
from .handback_contract import NOTE_EVENT, WARNING_NOTE

type FindingKind = Literal[
    "matrix-problem",
    "architecture-check-carried",
    "output-schema-carried",
    "trd-carried",
    "span-problem",
    "task-decomposition-carried",
    "done-rule-carried",
    "ownership-race",
    "contract-finding",
    "producer-missing",
    "completion-cycle",
    "prerequisite-unscheduled",
    "regression-carried",
    "prerequisite-carried",
    "respec-request-converted",
    "producer-epic-unordered",
    "deploy-stopped",
    "commit-hook-rejected",
    "dependency-cycle",
]
"""What kind of problem a finding records."""

Finding = TypedDict(
    "Finding",
    {
        "at": str,
        "owner": str,
        "from": str,
        "source": Literal["plugin", "driver"],
        "stage": str,
        "kind": FindingKind,
        "detail": str,
        "evidence": list[str],
    },
)
"""One finding: when, whom it is addressed to, which bead's run found it, where, what and on what evidence."""

FINDINGS_FILE: Final = "findings.jsonl"
"""The file of one Epic's findings, in that Epic's work directory."""
SOURCE_PLUGIN: Final[Literal["plugin"]] = "plugin"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def owner_epic(owner: str) -> str:
    """Name the Epic a finding's owner belongs to.

    Returns:
        The owner bead id cut at its first ``.`` (``ssbd-fcund.2.1`` gives ``ssbd-fcund``).

    """
    return owner.split(".", 1)[0]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def findings_file(artifacts_root: Path, owner: str) -> Path:
    """Name the findings file of the Epic a finding's owner belongs to.

    Returns:
        ``<artifacts root>/<owner Epic>/findings.jsonl``.

    """
    return artifacts_root / owner_epic(owner) / FINDINGS_FILE


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def finding(  # ruff: ignore[too-many-arguments] - One finding names each of its fields.
    owner: str,
    origin: str,
    *,
    stage: str,
    kind: FindingKind,
    detail: str,
    evidence: Sequence[str],
) -> Finding:
    """Build one plugin finding stamped now.

    Args:
        owner: The bead the finding is addressed to.
        origin: The bead whose run found it.
        stage: The step script key or agent that found it.
        kind: What kind of problem it is.
        detail: One line; line breaks become spaces.
        evidence: Paths or quoted text.

    Returns:
        The finding.

    """
    return {
        "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "owner": owner,
        "from": origin,
        "source": SOURCE_PLUGIN,
        "stage": stage,
        "kind": kind,
        "detail": " ".join(detail.split()),
        "evidence": list(evidence),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_finding(artifacts_root: Path, entry: Finding, emit: EventSink | None) -> Path:
    """Append one finding to its owner Epic's findings file and announce it as a warning note.

    Args:
        artifacts_root: The directory that holds every Epic's work directory.
        entry: The finding.
        emit: The dispatch's event sink, or None when no dispatch listens.

    Returns:
        The findings file written.

    """
    path: Path = findings_file(artifacts_root, entry["owner"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
            stream.flush()
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    if emit is not None:
        emit(
            NOTE_EVENT,
            kind=WARNING_NOTE,
            step=entry["stage"],
            detail=f"finding for {entry['owner']} ({entry['kind']}): {entry['detail']}",
        )
    return path
