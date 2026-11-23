"""Check, before an Epic's specs, decomposition or Task beads, that no other Epic came to own what it plans to build.

The span step records on each item the Tasks of the Epic that owns its entry, when that is another
Epic (``builtBy``, ``buildowner.mark_built_by``). Another Epic elaborated at the same time can
write a Task that owns one of those entries after that, or a build can start and change the owner.
A step that plans or writes from the items then works on a stale snapshot, so it reads beads
again, and on any change raises ``OwnershipChangedError`` naming the span step: the span alone
runs again, keeping the repository containers it planned, and sets back only the containers
whose placed items changed (``repo_scoping.span``). The same holds when the architect's result came to name other
elements for the Stories than the span read (an answer to a design gap can add one):
``ScopeChangedError``. A Task bead write makes the check and the write under one lock
(``tool_locks.ownership_lock``), so the second of two racing Epics sees the first one's claim.

Two Epics can keep racing. Once a dispatch has raised ``OWNERSHIP_REPLANS`` such changes for one
span step, a further change is recorded as an ``ownership-race`` finding for the Epic and the step
continues with the ownership as it stands (:func:`_race`).
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Final

import beadgraph
import buildowner
import hierarchy
from matrixstore import as_entry_id, matrix_path, read_matrix
from matrixtasks import TaskBead, tasks_of
from target_contract import KEY_MATRIX_ID
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import OWNERSHIP_REPLANS, OwnershipChangedError, ScopeChangedError, StepError
from orchestrator.core.step_findings import record_for_run
from orchestrator.core.tool_locks import ownership_lock
from orchestrator.flows.architecture_files import read_context, read_result
from orchestrator.flows.elaboration_files import ARTIFACT_ELEMENTS, control_repository, span_files
from orchestrator.flows.repo_scoping import can_build, story_build_entries

# isort: split
from step_journal_contract import KIND_VALUE

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from architecture_work_contract import ArchitectureResult
    from beadcontracts import StoryBuild
    from matrixstore import Matrix
    from step_journal_contract import StepId

    from orchestrator.core.journal_steps import StepRun


_RAISED: Final[dict[str, int]] = {}
"""How many ownership or scope changes this dispatch raised, by span step."""
_RAISED_LOCK: Final = threading.Lock()


def _race(run: StepRun, changed: OwnershipChangedError) -> None:
    """Raise an ownership or scope change, until this dispatch has raised enough of them for the span step.

    The change is raised while this dispatch raised fewer than ``OWNERSHIP_REPLANS`` for the span
    step; after that it is recorded as an ``ownership-race`` finding for the Epic and the step
    continues.
    """
    with _RAISED_LOCK:
        raised: int = _RAISED.get(changed.writer, 0)
        _RAISED[changed.writer] = raised + 1
    if raised < OWNERSHIP_REPLANS:
        raise changed
    record_for_run(
        run,
        str(run.bead),
        kind="ownership-race",
        detail="the ownership of the span's entries kept changing; the step continues with it as it stands",
        evidence=changed.evidence,
    )


def span_writer(run: StepRun) -> StepId:
    """Find the span step: the step of the journal that recorded the elements file the step reads.

    Returns:
        Its id.

    Raises:
        StepError: No step of the journal recorded that file.

    """
    elements: Path = span_files(run.inputs).elements
    for step in step_journal.steps_in_order(run.journal()):
        recorded: list[str] = [
            held["path"]
            for held in step["artifacts"]
            if held["name"] == ARTIFACT_ELEMENTS and held["kind"] != KIND_VALUE
        ]
        if str(elements) in recorded:
            return step["id"]
    raise StepError(
        run.inputs.stage,
        OTHER_CAUSE,
        (f"step {run.step['id']}: no step of the journal recorded the elements file {elements}",),
    )


def refuse_ownership_drift(run: StepRun, stage: str) -> None:
    """Check the span's ``builtBy`` against a fresh read of beads.

    An item whose owner Epic is no longer the one the span recorded is an ``OwnershipChangedError``
    naming the span step, so it runs again alone (:func:`_race`).

    Args:
        run: The step that reads the span's items.
        stage: The step's script key, for the reads' diagnostics.

    """
    items: dict[str, StoryBuild] = run.tools.portfolio_read(stage, hierarchy.story_builds, span_files(run.inputs))
    graph: beadgraph.Graph = run.tools.portfolio_read(stage, beadgraph.load, control_repository())
    tasks: list[TaskBead] = run.tools.portfolio_read(stage, tasks_of, graph)
    drifted: list[str] = buildowner.ownership_drift(list(items.values()), buildowner.builders(tasks), str(run.bead))
    if drifted:
        _race(run, OwnershipChangedError(stage, span_writer(run), tuple(drifted), within=None))


def refuse_scope_drift(run: StepRun, stage: str) -> None:
    """Check the elements the span step read against the architect's result as it stands.

    An answer to a design gap can add an element the Epic builds, or drop one; the span then no
    longer holds what the Stories build. Only entries a Story can build count
    (``repo_scoping.can_build``): the span records the others as findings and holds no item of them.

    A result whose ``addedOrChangedElements`` and ``unchangedWorkElements`` name other entries
    than the span's items is a ``ScopeChangedError`` naming the span step, so it runs again alone
    (:func:`_race`).

    Args:
        run: The step that reads the span's items.
        stage: The step's script key.

    """
    result: ArchitectureResult = read_result(run, read_context(run))
    matrix: Matrix = run.tools.portfolio_read(stage, read_matrix, matrix_path(None, os.environ))
    stated: set[str] = {
        entry
        for entry in story_build_entries([*result["addedOrChangedElements"], *result["unchangedWorkElements"]])
        if can_build(matrix, as_entry_id(entry))
    }
    items: list[JsonValue] = check_type(strict_json(span_files(run.inputs).elements)["items"], list[JsonValue])
    spanned: set[str] = {check_type(json_object(item)[KEY_MATRIX_ID], str) for item in items}
    if stated == spanned:
        return
    evidence: tuple[str, ...] = (
        *(f"the architect's result names {entry}, which the span does not hold" for entry in sorted(stated - spanned)),
        *(
            f"the span holds {entry}, which the architect's result no longer names"
            for entry in sorted(spanned - stated)
        ),
    )
    _race(run, ScopeChangedError(stage, span_writer(run), evidence, within=None))


@contextmanager
def owned_write(run: StepRun, stage: str) -> Generator[None]:
    """Hold the ownership lock, check the span's ``builtBy``, and let the caller write its Task bead under it.

    Args:
        run: The Task bead write step.
        stage: Its script key.

    Yields:
        Control while the lock is held and nothing drifted.

    """
    with ownership_lock(f"{stage} {run.bead} {run.step['id']}"):
        refuse_ownership_drift(run, stage)
        yield
