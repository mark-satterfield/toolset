"""The last steps of an elaboration: scoring, the buildability gate, the done rule, Story edges and the Epic's mark.

Each is one script step of the Epic's journal, planned when the journal is created; the Story
edges step plans the impact assessment of the Epic's architecture change before the mark. What a step
needs from the repositories' steps it reads from the artifacts the steps its inputs name hold.

The buildability gate (``buildability.evaluate``) records its report on the Epic
(``elaboration_buildability``) and in the work folder; a failed gate leaves the Epic in progress
with the cause ``buildability`` and fails the step, so the done rule never passes an Epic whose
Tasks cannot be built as planned.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

import beadgraph
import elaboration
import matrixtasks
import storyedges
from matrixstore import Matrix, matrix_path, read_matrix
from typeguard import check_type

from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback_contract import BUILDABILITY_CAUSE, ITEM_CLASS, OTHER_CAUSE, Failure
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, value_artifact
from orchestrator.flows.architecture_impact import follow_steps
from orchestrator.flows.buildability import evaluate
from orchestrator.flows.elaboration_files import (
    ARTIFACT_REPOSITORIES,
    BUILDABILITY,
    BUILDABLE_STEP,
    DONE_RULE,
    DONE_RULE_STEP,
    LIFECYCLE_DONE,
    MARK_DONE,
    SCORE,
    STORY,
    STORY_EDGES,
    STORY_EDGES_RESULT,
    TASKS_RESULT,
    UNSCORED,
)
from orchestrator.flows.elaboration_support import (
    FINISH_PHASE,
    done_rule,
    enter_phase,
    lifecycle,
    repository_failure,
)

if TYPE_CHECKING:
    from bead_metadata import BuildabilityReport
    from scoringcontracts import TaskScores

TASK_SCORES_STAGE: Final = "task-scores"


def repository_rows(run: StepRun) -> list[dict[str, JsonValue]]:
    """Join each repository of the span with its Story and its Tasks result, from the artifacts a step is handed.

    The repositories are the ones the span step named (value ``repositories``), so a repository
    whose Story was never written still has a row, which the done rule reports as missing its Story.

    Returns:
        One row per repository of the span, in span order: the repository, and its Story and
        Task results as the done rule reads them (empty when none was written).

    """
    decomposed: dict[str, JsonValue] = {
        check_type(json_object(value).get("repoPath"), str): value for value in run.inputs.values(TASKS_RESULT)
    }
    stories: dict[str, dict[str, JsonValue]] = {
        check_type(json_object(value).get("repoPath"), str): json_object(value) for value in run.inputs.values(STORY)
    }
    repositories: list[str] = check_type(run.inputs.value(ARTIFACT_REPOSITORIES), list[str])
    return [
        {
            "repository": repository,
            "spec": {"ok": True, "story": stories[repository]} if repository in stories else {},
            "tasks": decomposed.get(repository, {}),
        }
        for repository in repositories
    ]


def _owner(run: StepRun) -> str:
    """Read the owner of this dispatch's claim on the Epic.

    Returns:
        The owner the dispatch recorded in its arguments when it claimed the Epic.

    """
    return check_type(run.context.args[dispatch_arguments().KEY_OWNER], str)


@script_step(SCORE)
def score(run: StepRun) -> Completion:
    """Score the Epic's Tasks.

    Returns:
        The Tasks the scoring left unscored.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, TASK_SCORES_STAGE)

    def progress(detail: str) -> None:
        enter_phase(run.context, run.agents.emit, FINISH_PHASE, f"{TASK_SCORES_STAGE}: {detail}")

    scores: TaskScores = lifecycle(
        run.context,
        run.tools,
        FINISH_PHASE,
        elaboration.score_epic_tasks,
        owner=_owner(run),
        progress=progress,
    )
    unscored: list[JsonValue] = [json_object(row) for row in scores["unscored"]]
    return Completion(artifacts=(value_artifact(UNSCORED, unscored),))


def _gate(run: StepRun, stage: str) -> BuildabilityReport:
    """Run the buildability gate over the Epic and record its report; a failed gate fails the step.

    The report is written to its file in the work folder and to the Epic's
    ``elaboration_buildability``; a failed gate also sets the Epic's cause ``buildability`` and
    leaves its state in progress, and fails the step with the cause ``buildability``, item
    class, and the report.

    Returns:
        The report of a gate that passed.

    """
    repo: Path = Path(check_type(run.context.args[dispatch_arguments().KEY_BEADS_REPO_PATH], str))
    graph: beadgraph.Graph = run.tools.portfolio_read(stage, beadgraph.load, repo)
    matrix: Matrix = run.tools.portfolio_read(stage, read_matrix, matrix_path(None, os.environ))
    tasks: list[matrixtasks.TaskBead] = run.tools.portfolio_read(stage, matrixtasks.tasks_of, graph)
    report: BuildabilityReport = run.tools.portfolio_read(
        stage,
        evaluate,
        str(run.bead),
        run.journal(),
        graph,
        matrix,
        tasks,
    )
    write_json(Path(report["reportPath"]), json_object(report))
    lifecycle(
        run.context,
        run.tools,
        FINISH_PHASE,
        elaboration.record_buildability,
        owner=_owner(run),
        report=json.dumps(report, sort_keys=True),
    )
    if not report["buildable"]:
        raise run.tools.failure(
            BUILDABLE_STEP,
            BUILDABILITY_CAUSE,
            {"classification": ITEM_CLASS, "buildability": json_object(report)},
        )
    return report


@script_step(BUILDABLE_STEP)
def buildable(run: StepRun) -> Completion:
    """Check the Epic is buildable (``buildability.evaluate``).

    No Task edge was dropped, no design gap was carried, and every consumed item has a producer
    ordered before it.

    Returns:
        The gate's report, as the value ``buildability``.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, BUILDABLE_STEP)
    report: BuildabilityReport = _gate(run, BUILDABLE_STEP)
    return Completion(artifacts=(value_artifact(BUILDABILITY, json_object(report)),))


@script_step(DONE_RULE_STEP)
def apply_done_rule(run: StepRun) -> Completion:
    """Apply the done rule: each repository has its Story and Tasks, each Task is scored, and the Epic is buildable.

    The gate's report is the ``buildability`` value the step is handed. A journal planned before
    the gate step existed hands none, so the gate runs here, with the same record and failure. A
    repository that lacks its Story or its Tasks, and a Task left unscored, fail the step.

    Returns:
        The done rule's result.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, DONE_RULE_STEP)
    unscored: list[JsonValue] = check_type(run.inputs.value(UNSCORED), list[JsonValue])
    rows: list[dict[str, JsonValue]] = repository_rows(run)
    held: JsonValue = run.inputs.optional_value(BUILDABILITY)
    gate: dict[str, JsonValue] = (
        json_object(held) if isinstance(held, dict) else json_object(_gate(run, DONE_RULE_STEP))
    )
    rule: dict[str, JsonValue] = done_rule(rows, gate.get("buildable") is True, unscored)
    if rule["repositories"]:
        incomplete: Failure = repository_failure(rows)
        raise run.tools.failure(incomplete["stage"], incomplete["cause"], {"doneRule": rule})
    if unscored:
        raise run.tools.failure(TASK_SCORES_STAGE, OTHER_CAUSE, {"classification": ITEM_CLASS, "unscored": unscored})
    return Completion(artifacts=(value_artifact(DONE_RULE, rule),))


@script_step(STORY_EDGES)
def story_edges(run: StepRun) -> Completion:
    """Write the dependency edges between the Epic's Stories, then plan the Epic's one impact assessment.

    Story edges that could not be written fail the step. The impact analyst and the step that
    applies its rulings follow, before the Epic is marked elaborated, when they are due
    (``architecture_impact.follow_steps``): this is the one place an elaboration assesses what
    its architecture change reaches.

    Returns:
        What the Story edge write returns, as an artifact, with the impact steps when due.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, STORY_EDGES)
    repo: Path = Path(check_type(run.context.args[dispatch_arguments().KEY_BEADS_REPO_PATH], str))

    def progress(detail: str) -> None:
        enter_phase(run.context, run.agents.emit, FINISH_PHASE, f"{STORY_EDGES}: {detail}")

    def write() -> storyedges.StoryEdges:
        graph: beadgraph.Graph = run.tools.portfolio_read(FINISH_PHASE, beadgraph.load, repo)
        progress(f"read {len(graph.beads)} beads")
        writer: beadgraph.Writer = run.tools.portfolio(FINISH_PHASE, beadgraph.Writer, repo)
        return run.tools.portfolio(
            FINISH_PHASE,
            storyedges.story_edges,
            graph,
            writer,
            epic=str(run.bead),
            progress=progress,
        )

    written: dict[str, JsonValue] = json_object(run.tools.operation(FINISH_PHASE, write))
    if written.get("ok") is False:
        raise run.tools.failure(FINISH_PHASE, OTHER_CAUSE, dict(written))
    return Completion(artifacts=(value_artifact(STORY_EDGES_RESULT, written),), add=follow_steps(run))


@script_step(MARK_DONE)
def mark_done(run: StepRun) -> Completion:
    """Mark the Epic elaborated.

    The score step scored the Tasks and the done rule checked them, so nothing is scored again
    here. An Epic another run owns fails the step.

    Returns:
        The record that the Epic's lifecycle is done.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, MARK_DONE)
    lifecycle(run.context, run.tools, FINISH_PHASE, elaboration.mark_elaborated, owner=_owner(run))
    return Completion(artifacts=(value_artifact(LIFECYCLE_DONE, True),))
