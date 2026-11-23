"""The last steps of an elaboration: scoring, the done rule, Story edges and the Epic's mark.

Each is one script step of the Epic's journal, planned when the journal is created. What a step
needs from the repositories' steps it reads from the artifacts the steps its inputs name hold.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Final

import beadgraph
import beadwrite
import elaboration
import storyedges
from typeguard import check_type

from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_registry import removed, script_step
from orchestrator.core.journal_steps import Completion, StepRun, value_artifact
from orchestrator.core.step_findings import record_for_run, record_skipped_cycles
from orchestrator.flows.elaboration_files import (
    ARTIFACT_REPOSITORIES,
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
    from beadcontracts import StoriesClosed
    from scoringcontracts import TaskScores

    from orchestrator.core.handback_contract import Failure

TASK_SCORES_STAGE: Final = "task-scores"

removed("architecture-impact-analyst", "reelaborate.restart")


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
            "spec": {"ok": True, "story": _written_story(stories[repository], decomposed.get(repository))}
            if repository in stories
            else {},
            "tasks": decomposed.get(repository, {}),
        }
        for repository in repositories
    ]


def _written_story(story: dict[str, JsonValue], tasks: JsonValue) -> dict[str, JsonValue]:
    """Give a repository's Story with the id its Task write gave it.

    The Story step leaves the id empty for a Story that did not exist yet; the Task write creates
    it with its Tasks, and its result names it.

    Returns:
        The Story, with the Task write's id when that write named one.

    """
    written: JsonValue = json_object(json_object(tasks or {}).get("story") or {}).get("id")
    return {**story, "id": written} if isinstance(written, str) and written else story


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


@script_step(DONE_RULE_STEP)
def apply_done_rule(run: StepRun) -> Completion:
    """Apply the done rule: every repository has its Story and its Tasks, and every Task is scored.

    A repository that lacks its Story or its Tasks, and a Task left unscored, are recorded as
    ``done-rule-carried`` findings for the Epic, and the Epic is marked elaborated with what exists.
    Every open Story of the Epic that has no Task is closed with reason "no Tasks"
    (``beadwrite.close_stories_without_tasks``); each one that stays open is recorded as a
    ``done-rule-carried`` finding.

    Returns:
        The done rule's result, with the Stories closed for having no Task (``closedStories``), the
        edges moved off them (``movedStoryEdges``) and each one that stayed open (``unclosedStories``).

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, DONE_RULE_STEP)
    repo: Path = Path(check_type(run.context.args[dispatch_arguments().KEY_BEADS_REPO_PATH], str))

    def close() -> StoriesClosed:
        graph: beadgraph.Graph = run.tools.portfolio_read(FINISH_PHASE, beadgraph.load, repo)
        writer: beadgraph.Writer = run.tools.portfolio(FINISH_PHASE, beadgraph.Writer, repo)
        return run.tools.portfolio(FINISH_PHASE, beadwrite.close_stories_without_tasks, graph, writer, str(run.bead))

    stories: dict[str, JsonValue] = json_object(run.tools.operation(FINISH_PHASE, close))
    for failure in check_type(stories["failed"], list[JsonValue]):
        record_for_run(
            run,
            str(run.bead),
            kind="done-rule-carried",
            detail=f"a Story with no Task stayed open: {json.dumps(failure)}",
            evidence=(),
        )
    unscored: list[JsonValue] = check_type(run.inputs.value(UNSCORED), list[JsonValue])
    rows: list[dict[str, JsonValue]] = repository_rows(run)
    rule: dict[str, JsonValue] = {
        **done_rule(rows, True, unscored),
        "closedStories": stories["closed"],
        "movedStoryEdges": stories["moved"],
        "unclosedStories": stories["failed"],
    }
    lacking: list[JsonValue] = check_type(rule["repositories"], list[JsonValue])
    if lacking:
        incomplete: Failure = repository_failure(rows)
        record_for_run(
            run,
            str(run.bead),
            kind="done-rule-carried",
            detail=f"{incomplete['stage']}: repositories lack their Story or Tasks: {json.dumps(lacking)}",
            evidence=(),
        )
    if unscored:
        record_for_run(
            run,
            str(run.bead),
            kind="done-rule-carried",
            detail=f"{TASK_SCORES_STAGE}: Tasks left unscored: {json.dumps(unscored)}",
            evidence=(),
        )
    return Completion(artifacts=(value_artifact(DONE_RULE, rule),))


@script_step(STORY_EDGES)
def story_edges(run: StepRun) -> Completion:
    """Write the dependency edges between the Epic's Stories.

    The Story edges are written for every Story whose order is consistent; the Stories of this
    Epic whose order is contradictory are recorded as a ``done-rule-carried`` finding and the Epic
    goes on. Nothing is planned for any other Epic: an Epic never corrects another Epic, so every
    change this Epic's architecture needs in work other Epics built is a Task of this Epic's own
    Stories.

    Returns:
        What the Story edge write returns, as an artifact.

    """
    enter_phase(run.context, run.agents.emit, FINISH_PHASE, STORY_EDGES)
    repo: Path = Path(check_type(run.context.args[dispatch_arguments().KEY_BEADS_REPO_PATH], str))

    def progress(detail: str) -> None:
        enter_phase(run.context, run.agents.emit, FINISH_PHASE, f"{STORY_EDGES}: {detail}")

    writers: list[beadgraph.Writer] = []

    def write() -> storyedges.StoryEdges:
        graph: beadgraph.Graph = run.tools.portfolio_read(FINISH_PHASE, beadgraph.load, repo)
        progress(f"read {len(graph.beads)} beads")
        writer: beadgraph.Writer = run.tools.portfolio(FINISH_PHASE, beadgraph.Writer, repo, skip_cycles=True)
        writers.append(writer)
        return run.tools.portfolio(
            FINISH_PHASE,
            storyedges.story_edges,
            graph,
            writer,
            epic=str(run.bead),
            progress=progress,
        )

    written: dict[str, JsonValue] = json_object(run.tools.operation(FINISH_PHASE, write))
    record_skipped_cycles(run, writers[-1].skipped_cycles)
    if written.get("ok") is False:
        refused: list[JsonValue] = check_type(written.get("refusedStories", []), list[JsonValue])
        record_for_run(
            run,
            str(run.bead),
            kind="done-rule-carried",
            detail=f"{STORY_EDGES}: the Story order of {json.dumps(refused)} is contradictory, so their Story edges "
            "were not written; every other Story edge was written and the Epic goes on",
            evidence=tuple(str(story) for story in refused),
        )
    return Completion(artifacts=(value_artifact(STORY_EDGES_RESULT, written),))


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
