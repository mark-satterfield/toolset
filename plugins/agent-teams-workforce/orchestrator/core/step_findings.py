"""Record a finding a running step found: in the run's artifacts root, on the dispatch's event sink.

The finding record, its file and its I/O are :mod:`orchestrator.core.findings`; this module adds
what a step's code is given (:class:`~orchestrator.core.journal_steps.StepRun`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from finding_contract import Finding, FindingKind, owner_epic

from .findings import finding, record_finding

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from beadgraph import SkippedCycle

    from .journal_steps import StepRun


def record_for_run(
    run: StepRun,
    owner: str,
    *,
    kind: FindingKind,
    detail: str,
    evidence: Sequence[str],
) -> Path:
    """Record a finding the running step found, in the run's artifacts root, on the run's event sink.

    Args:
        run: The running step.
        owner: The bead the finding is addressed to.
        kind: What kind of problem it is.
        detail: One line.
        evidence: Paths or quoted text.

    Returns:
        The findings file written.

    """
    stage: str = run.step.get("script") or run.step.get("agent") or run.step["description"]
    entry: Finding = finding(owner, str(run.bead), stage=stage, kind=kind, detail=detail, evidence=evidence)
    return record_finding(run.context.work.parent, entry, run.agents.emit)


def record_skipped_cycles(run: StepRun, skipped: Sequence[SkippedCycle]) -> None:
    """Record, for the run's Epic, each ``blocks`` edge an edge write left out because it closes a cycle.

    Args:
        run: The running step that wrote the edges.
        skipped: The edges the step's writer left out, each with the loop it would close.

    """
    for edge in skipped:
        loop: str = " -> ".join(edge["cycle"])
        record_for_run(
            run,
            owner_epic(str(run.bead)),
            kind="dependency-cycle",
            detail=f"blocks edge {edge['dependent']} -> {edge['blocker']} was not written because it would close "
            f"the dependency cycle {loop}; every other edge was written",
            evidence=tuple(edge["cycle"]),
        )
