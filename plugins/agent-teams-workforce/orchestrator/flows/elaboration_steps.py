"""The last steps of an elaboration: scoring, the done rule, Story edges and the Epic's mark.

Each is one script step of the Epic's journal, planned when the journal is created. What a step
needs from the repositories' steps it reads from the artifacts the steps its inputs name hold.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

import beadgraph
import elaboration
import storyedges
from typeguard import check_type

from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback_contract import ITEM_CLASS, OTHER_CAUSE, Failure
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, value_artifact
from orchestrator.flows.elaboration_files import (
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
    from elaborationcontracts import Finished

TASK_SCORES_STAGE: Final = "task-scores"


def repository_rows(run: StepRun) -> list[dict[str, JsonValue]]:
    """Join each repository's Story and its Tasks result, from the artifacts a step is handed.

    Returns:
        One row per repository with a Story, in the order the Stories were written: the
        repository, and its Story and Task results as the done rule reads them.

    """
    decomposed: dict[str, JsonValue] = {
        check_type(json_object(value).get("repoPath"), str): value for value in run.inputs.values(TASKS_RESULT)
    }
    rows: list[dict[str, JsonValue]] = []
    for value in run.inputs.values(STORY):
        story: dict[str, JsonValue] = json_object(value)
        repository: str = check_type(story["repoPath"], str)
        rows.append({
            "repository": repository,
            "spec": {"ok": True, "story": story},
            "tasks": decomposed.get(repository, {}),
        })
    return rows


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
    finish: Finished = lifecycle(
        run.context,
        run.tools,
        FINISH_PHASE,
        elaboration.finish,
        owner=_owner(run),
        done=False,
        scope="epic-tasks",
    )
    unscored: list[JsonValue] = check_type(json_object(finish["score"])["unscored"], list[JsonValue])
    return Completion(artifacts=(value_artifact(UNSCORED, unscored),))


@script_step(DONE_RULE_STEP)
def apply_done_rule(run: StepRun) -> Completion:
    """Apply the done rule: every repository has its Story and its Tasks, and every Task is scored.

    A repository that lacks its Story or its Tasks, and a Task left unscored, fail the step.

    Returns:
        The done rule's result.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, DONE_RULE_STEP)
    unscored: list[JsonValue] = check_type(run.inputs.value(UNSCORED), list[JsonValue])
    rows: list[dict[str, JsonValue]] = repository_rows(run)
    rule: dict[str, JsonValue] = done_rule(rows, True, unscored)
    if rule["repositories"]:
        incomplete: Failure = repository_failure(rows)
        raise run.tools.failure(incomplete["stage"], incomplete["cause"], {"doneRule": rule})
    if unscored:
        raise run.tools.failure(TASK_SCORES_STAGE, OTHER_CAUSE, {"classification": ITEM_CLASS, "unscored": unscored})
    return Completion(artifacts=(value_artifact(DONE_RULE, rule),))


@script_step(STORY_EDGES)
def story_edges(run: StepRun) -> Completion:
    """Write the dependency edges between the Epic's Stories.

    Story edges that could not be written fail the step.

    Returns:
        What the Story edge write returns, as an artifact.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, STORY_EDGES)
    repo: Path = Path(check_type(run.context.args[dispatch_arguments().KEY_BEADS_REPO_PATH], str))

    def write() -> storyedges.StoryEdges:
        graph: beadgraph.Graph = run.tools.portfolio(FINISH_PHASE, beadgraph.load, repo)
        writer: beadgraph.Writer = run.tools.portfolio(FINISH_PHASE, beadgraph.Writer, repo)
        return run.tools.portfolio(FINISH_PHASE, storyedges.story_edges, graph, writer)

    written: dict[str, JsonValue] = json_object(run.tools.operation(FINISH_PHASE, write))
    if written.get("ok") is False:
        raise run.tools.failure(FINISH_PHASE, OTHER_CAUSE, dict(written))
    return Completion(artifacts=(value_artifact(STORY_EDGES_RESULT, written),))


@script_step(MARK_DONE)
def mark_done(run: StepRun) -> Completion:
    """Mark the Epic elaborated.

    An Epic that could not be marked done fails the step.

    Returns:
        The record that the Epic's lifecycle is done.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, MARK_DONE)
    finish: Finished = lifecycle(
        run.context,
        run.tools,
        FINISH_PHASE,
        elaboration.finish,
        owner=_owner(run),
        done=True,
        scope="epic-tasks",
    )
    if not finish["summary"]["done"]:
        raise run.tools.failure(TASK_SCORES_STAGE, OTHER_CAUSE, json_object(finish))
    return Completion(artifacts=(value_artifact(LIFECYCLE_DONE, True),))
