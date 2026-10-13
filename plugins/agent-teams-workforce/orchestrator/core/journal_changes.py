"""The journal changes a step's result makes: one for a completed step, one for a new bead.

:func:`apply_completion` records the whole of one step's result in a journal, for the one write
the runner makes when a step's output is accepted. :func:`create_child_journal` creates the
journal of a Story or a Task in the step that creates the bead, with its first step already done.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal, assert_never

from typeguard import CollectionCheckStrategy, typechecked

from . import step_journal
from .journal_steps import (
    AFTER_THIS,
    UNDER_CONTAINER,
    UNDER_THIS,
    Completion,
    NewStep,
    StepGroup,
    value_artifact,
)

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import (
    BEAD_TYPE_STORY,
    BEAD_TYPE_TASK,
    PIPELINE_BUILD,
    PIPELINE_DEPLOY,
    STATUS_PLANNED,
    Artifact,
    BeadId,
    Journal,
    JsonValue,
    Pipeline,
    Step,
    StepId,
    StepPlan,
    ValueArtifact,
)

type ChildBeadType = Literal["story", "task"]


def _plan(new: NewStep, completing: StepId) -> StepPlan:
    """Turn one planned step into the step plan the journal takes.

    Returns:
        The plan with its child plans, and with the completing step among its inputs when the
        step is handed parameters.

    """
    plan: StepPlan = {"description": new.plan["description"], "purpose": new.plan["purpose"]}
    if "ref" in new.plan:
        plan["ref"] = new.plan["ref"]
    if "agent" in new.plan:
        plan["agent"] = new.plan["agent"]
    if "script" in new.plan:
        plan["script"] = new.plan["script"]
    inputs: list[str] = list(new.plan.get("inputs", []))
    if new.params is not None and completing not in inputs:
        inputs.append(completing)
    if inputs:
        plan["inputs"] = inputs
    children: list[StepPlan] = [_plan(child, completing) for child in new.children] or list(new.plan.get("steps", []))
    if children:
        plan["steps"] = children
    return plan


def _records(planned: Sequence[NewStep], added: Sequence[Step], *, outermost: bool) -> list[ValueArtifact]:
    """Build the record of each step a result planned.

    Returns:
        One ``for <step id>`` value artifact per step added at the place the group names, and per
        step below one of those that is handed parameters; its value is the parameters, or an
        empty object.

    """
    records: list[ValueArtifact] = []
    new: NewStep
    step: Step
    for new, step in zip(planned, added, strict=True):
        if outermost or new.params is not None:
            params: dict[str, JsonValue] = dict(new.params or {})
            records.append(value_artifact(step_journal.planned_for_name(step["id"]), params))
        if new.children:
            records.extend(_records(new.children, step["steps"], outermost=False))
    return records


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def apply_completion(journal: Journal, step_id: StepId, completion: Completion, moment: str) -> Step:
    """Record one step's result in a journal: the whole of it, for one journal write.

    The step's artifacts are recorded, every planned step is added, each added step is recorded
    on the completing step as the value artifact :func:`step_journal.planned_for_name` names, and
    the step is marked done unless it waits for child steps planned under it. A change the journal refuses raises
    ``StepRefusedError``, and nothing is written.

    Args:
        journal: The journal; changed in place.
        step_id: The running step whose result this is.
        completion: What the result records.
        moment: The present date-time, as ``step_journal.timestamp`` gives it.

    Returns:
        The step after the change.

    """
    artifact: Artifact
    for artifact in completion.artifacts:
        step_journal.record_artifact(journal, step_id, artifact)
    parent: Step | None = step_journal.parent_step(journal, step_id)
    follows: StepId = step_id
    group: StepGroup
    for group in completion.add:
        plans: list[StepPlan] = [_plan(new, step_id) for new in group.steps]
        added: list[Step]
        if group.where == AFTER_THIS:
            added = step_journal.add_steps(
                journal,
                plans,
                moment,
                parent=None if parent is None else parent["id"],
                after=follows,
            )
            follows = added[-1]["id"]
        elif group.where == UNDER_THIS:
            added = step_journal.add_steps(journal, plans, moment, parent=step_id)
        elif group.where == UNDER_CONTAINER:
            added = step_journal.add_steps(journal, plans, moment, parent=group.container)
        else:
            assert_never(group.where)
        record: ValueArtifact
        for record in _records(group.steps, added, outermost=True):
            step_journal.record_artifact(journal, step_id, record)
    if completion.stays_running:
        return step_journal.find_step(journal, step_id)
    return step_journal.finish_step(journal, step_id, moment)


def _child_pipeline(bead_type: ChildBeadType) -> Pipeline:
    """Name the pipeline that runs the steps of a Story or a Task.

    Returns:
        ``deploy`` for a Story, ``build`` for a Task.

    """
    if bead_type == BEAD_TYPE_STORY:
        return PIPELINE_DEPLOY
    if bead_type == BEAD_TYPE_TASK:
        return PIPELINE_BUILD
    assert_never(bead_type)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def create_child_journal(
    directory: Path,
    bead: BeadId,
    bead_type: ChildBeadType,
    steps: Sequence[StepPlan],
    artifacts: Sequence[Artifact],
) -> Path:
    """Create the journal of a Story or a Task in the step that creates the bead.

    The journal's first outermost step is the creating step itself, done and holding the files
    the bead's later steps are handed; it is started, given its artifacts and finished before the
    one file write. When the journal already exists (the creating step is running again) and no
    step after the first has been started, it is replaced; once a later step has been started it
    is left as it is.

    Args:
        directory: The directory that holds step journals (``step_journal.journals_directory``).
        bead: The Story or Task bead id.
        bead_type: ``story`` or ``task``; a Story's journal is for the deploy pipeline and a
            Task's for the build pipeline.
        steps: The journal's outermost steps: the creating step first, then the steps planned
            after it when the creating step knows them.
        artifacts: What the first step holds.

    Returns:
        The journal file.

    """
    moment: str = step_journal.timestamp()
    journal: Journal = step_journal.new_journal(bead, bead_type, _child_pipeline(bead_type), steps)
    opening: StepId = journal["steps"][0]["id"]
    step_journal.start_step(journal, opening, moment)
    artifact: Artifact
    for artifact in artifacts:
        step_journal.record_artifact(journal, opening, artifact)
    step_journal.finish_step(journal, opening, moment)
    path: Path = step_journal.journal_path(directory, bead)
    if not path.is_file():
        step_journal.create_journal(path, journal)
        return path

    def replace(existing: Journal) -> None:
        if any(step["status"] != STATUS_PLANNED for step in existing["steps"][1:]):
            return
        existing["beadType"] = journal["beadType"]
        existing["pipeline"] = journal["pipeline"]
        existing["steps"] = journal["steps"]
        existing.pop("started", None)
        existing.pop("finished", None)
        if "started" in journal:
            existing["started"] = journal["started"]
        if "finished" in journal:
            existing["finished"] = journal["finished"]

    step_journal.update_journal(path, replace)
    return path
