"""Files an earlier form of the pipeline produced for a PRD's architecture, recorded in its journal.

An Epic whose architecture work was under way when the pipeline took its present form has files
that earlier form wrote: a survey, round plans, specialists' results, draft documents.
:func:`carry` records each as an artifact of a done step under the Architecture container, so the
journal holds what was done, and plans the architect's step after them. The architect is not
handed those files: they are unapproved copies and summaries of the architecture from a pipeline
that no longer runs, and the matrix and the arc42 documents are the architect's sources. The
architect's own step stays planned.

A step that records such files has a script key, so the runner has code for it. That code runs
only when the owner asks for a start at or before the step, which resets it: it then records
nothing, because nothing writes those files again, and the architect is handed none of them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, typechecked

from orchestrator.core import step_journal
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, directory_artifact, file_artifact
from orchestrator.flows.architecture import first_steps
from orchestrator.flows.architecture_files import ARCHITECTURE, EARLIER_PREFIX, EARLIER_WORK, OPEN_RUN

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import STATUS_PLANNED, Journal, PathArtifact, Step, StepJournalError, StepPlan

CONTAINER_DESCRIPTION: Final = "Earlier work on this PRD"
CONTAINER_PURPOSE: Final = (
    "The solutions architect starts from what an earlier form of the pipeline already produced for this PRD"
)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class EarlierWork:
    """One piece of work an earlier form of the pipeline did, with the files it left.

    ``files`` pairs what each file is, in plain words, with its path; a path that is a directory
    is recorded as a directory.
    """

    description: str
    purpose: str
    files: tuple[tuple[str, Path], ...]

    def artifacts(self) -> list[PathArtifact]:
        """Build the artifacts that record the files.

        Returns:
            One artifact per file, named ``EARLIER_PREFIX`` followed by what the file is.

        """
        return [
            (directory_artifact if path.is_dir() else file_artifact)(f"{EARLIER_PREFIX}{what}", path)
            for what, path in self.files
        ]


@script_step(EARLIER_WORK)
def earlier_work(_run: StepRun) -> Completion:
    """Run a step that recorded earlier work after it was reset.

    Returns:
        A completion with no artifact: no step of the pipeline writes those files again.

    """
    return Completion()


def _outermost(journal: Journal, description: str) -> Step:
    """Find the one outermost step of a journal with a description.

    Returns:
        The step.

    Raises:
        StepJournalError: No outermost step, or more than one, has the description.

    """
    found: list[Step] = [step for step in journal["steps"] if step["description"] == description]
    if len(found) != 1:
        message: str = f"the journal of {journal['bead']} has {len(found)} outermost steps described {description!r}"
        raise StepJournalError(message)
    return found[0]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def carry(journal: Journal, work: Sequence[EarlierWork], architect: str, moment: str) -> list[Step]:
    """Record earlier work in a new Epic journal and plan the architect's step after it.

    The steps go under the Architecture container: one step that contains a done step per piece
    of earlier work, each holding its files, then the architect's step, handed the open-run step,
    and the check after it. The open-run step stays planned and runs first.

    Args:
        journal: An Epic's elaboration journal as it is created, every step planned; changed in place.
        work: The pieces of earlier work, in the order they were done; at least one.
        architect: The agent that plays the solutions architect.
        moment: The present date-time, as ``step_journal.timestamp`` gives it.

    Returns:
        The done steps, one per piece of earlier work, in order.

    Raises:
        StepJournalError: ``work`` is empty, a piece of work names no file, a step of the
            journal is not planned, or the journal lacks the open-run step or the Architecture
            container.

    """
    message: str
    if not work or any(not piece.files for piece in work):
        message = f"the earlier work carried into the journal of {journal['bead']} names no file"
        raise StepJournalError(message)
    if any(step["status"] != STATUS_PLANNED for step in step_journal.steps_in_order(journal)):
        message = f"the journal of {journal['bead']} has a step that is not planned; earlier work goes in a new journal"
        raise StepJournalError(message)
    opened: list[Step] = [step for step in journal["steps"] if step.get("script") == OPEN_RUN]
    if len(opened) != 1:
        message = f"the journal of {journal['bead']} has {len(opened)} outermost steps with the script {OPEN_RUN!r}"
        raise StepJournalError(message)
    container: Step = _outermost(journal, ARCHITECTURE)
    plan: StepPlan = {
        "description": CONTAINER_DESCRIPTION,
        "purpose": CONTAINER_PURPOSE,
        "steps": [
            {"description": piece.description, "purpose": piece.purpose, "script": EARLIER_WORK} for piece in work
        ],
    }
    holder: Step = step_journal.add_step(journal, plan, moment, parent=container["id"])
    piece: EarlierWork
    step: Step
    for piece, step in zip(work, holder["steps"], strict=True):
        step_journal.start_step(journal, step["id"], moment)
        artifact: PathArtifact
        for artifact in piece.artifacts():
            step_journal.record_artifact(journal, step["id"], artifact)
        step_journal.finish_step(journal, step["id"], moment)
    planned: list[StepPlan] = [new.plan for new in first_steps(opened[0]["id"], container["id"], architect).steps]
    step_journal.add_steps(journal, planned, moment, parent=container["id"])
    step_journal.checked_journal(journal, f"the journal of {journal['bead']} with its earlier work")
    return list(holder["steps"])
