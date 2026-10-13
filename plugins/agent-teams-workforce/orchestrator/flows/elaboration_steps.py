"""The steps of an elaboration after the TRD: specs and Stories, Tasks, edges, scoring and the Epic's mark.

Each step is one script step of the Epic's journal. A spec step and a Task step run the spec
authoring and the Task decomposition of one repository, handed that repository as parameters, and
record what they return in the journal. The dispatch result is assembled from those records.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final

import beadgraph
import elaboration
import storyedges
from typeguard import CollectionCheckStrategy, check_type

from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import ITEM_CLASS, OTHER_CAUSE, Failure, PrdToSpecPhase
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_changes import create_child_journal
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import (
    UNDER_CONTAINER,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.flows import spec_authoring, task_decomposition, task_edges
from orchestrator.flows.architecture_files import ARTIFACT_TRD
from orchestrator.flows.elaboration_support import (
    FINISH_PHASE,
    SPEC_AUTHORING_PHASE,
    TASK_DECOMPOSITION_PHASE,
    TASK_EDGES_PHASE,
    done_rule,
    enter_phase,
    lifecycle,
    repository_failure,
)
from orchestrator.flows.repo_scoping import ARTIFACT_ELEMENTS, ARTIFACT_REPOSITORIES, ARTIFACT_SPAN, SPECS

# isort: split
# The journal modules put the pipeline-contracts scripts directory on sys.path.
from step_journal_contract import BEAD_TYPE_STORY, BEAD_TYPE_TASK, BeadId

if TYPE_CHECKING:
    from collections.abc import Callable

    from elaborationcontracts import Finished
    from step_journal_contract import Artifact, StepPlan

    from orchestrator.core.artifacts import ArtifactStore
    from orchestrator.core.models import RunContext
    from orchestrator.core.tools import Tools

TASKS: Final = "task_decomposition.run"
EDGES: Final = "task_edges.run"
SCORE: Final = "elaboration.score"
STORY_EDGES: Final = "storyedges.story_edges"
MARK_DONE: Final = "elaboration.finish"
"""The script keys of the steps after the spec steps."""
TASKS_CONTAINER: Final = "Tasks"
TASKS_PURPOSE: Final = "The Story has Tasks that name what to build"
SPEC_RESULT: Final = "spec result"
TASKS_RESULT: Final = "tasks result"
EDGES_RESULT: Final = "edges result"
DONE_RULE: Final = "done rule"
STORY_EDGES_RESULT: Final = "story edges"
LIFECYCLE_DONE: Final = "lifecycle done"
TASK_SCORES_STAGE: Final = "task-scores"
SPEC_FILES: Final[tuple[str, ...]] = ("spec", "data model", "criteria")
"""The artifact names of one repository's three spec documents, in the order they are written."""

type Phase = Callable[[RunContext, ArtifactStore, AgentRunner, Tools], dict[str, JsonValue]]


def _phase(
    run: StepRun,
    phase: PrdToSpecPhase,
    function: Phase,
    additions: dict[str, JsonValue],
    repository: str | None = None,
) -> dict[str, JsonValue]:
    """Run one phase function with its own stage and arguments and the dispatch's services.

    Returns:
        What the phase function returns. What it raises is the step's failure.

    """
    enter_phase(run.context, run.agents.emit, phase, phase, repository)
    local: RunContext = replace(run.context, stage=phase, args={**run.context.args, **additions})
    child: AgentRunner = AgentRunner(
        local,
        run.agents.store,
        plugin=run.agents.plugin,
        emit=run.agents.emit,
        executable=run.agents.executable,
    )
    child.share_processes(run.agents)
    return function(local, run.agents.store, child, run.tools)


def _strings(value: JsonValue) -> list[str]:
    return check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _objects(value: JsonValue) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _handed_files(run: StepRun) -> list[Artifact]:
    """List the files the later steps of a Story or a Task are handed.

    Returns:
        The spec documents and the TRD the step itself is handed, as file artifacts.

    """
    names: tuple[str, ...] = (*SPEC_FILES, ARTIFACT_TRD)
    return [file_artifact(name, path) for name, path in run.inputs.labelled_files() if name in names]


def _creating(run: StepRun) -> StepPlan:
    """Describe a step as the first step of the journal of a bead it creates.

    Returns:
        The step plan: this step's description, purpose and script.

    """
    return {"description": run.step["description"], "purpose": run.step["purpose"], "script": run.inputs.stage}


@script_step(SPECS)
def specs(run: StepRun) -> Completion:
    """Write the specs and the Story of one repository, and plan its Task step.

    Returns:
        The phase result, the spec documents and the UI file as artifacts; the Story's journal
        is created in the same step; the Task step is planned under the Tasks container.

    """
    params: dict[str, JsonValue] = dict(run.params())
    repository: str = check_type(params.get("repoPath"), str)
    result: dict[str, JsonValue] = _phase(run, SPEC_AUTHORING_PHASE, spec_authoring.run, params, repository)
    documents: list[Artifact] = [
        file_artifact(name, Path(path)) for name, path in zip(SPEC_FILES, _strings(result["specPaths"]), strict=True)
    ]
    interface: JsonValue = result.get("uiPath")
    if isinstance(interface, str):
        documents.append(file_artifact("ui", Path(interface)))
    trd: Path | None = run.inputs.optional_file(ARTIFACT_TRD)
    handed: list[Artifact] = [*documents, *([] if trd is None else [file_artifact(ARTIFACT_TRD, trd)])]
    story: str = check_type(json_object(result["story"])["id"], str)
    create_child_journal(run.journal_path.parent, BeadId(story), BEAD_TYPE_STORY, [_creating(run)], handed)
    plan: StepPlan = {
        "description": f"Decompose the Story of {Path(repository).name} into Tasks",
        "purpose": TASKS_PURPOSE,
        "script": TASKS,
        "inputs": [run.step["id"], *run.step.get("inputs", [])],
    }
    tasks: NewStep = NewStep(plan, {"repoPath": repository, "slug": params.get("slug")})
    return Completion(
        artifacts=(value_artifact(SPEC_RESULT, result), *handed),
        add=(StepGroup((tasks,), UNDER_CONTAINER, run.step_named(TASKS_CONTAINER)["id"]),),
    )


@script_step(TASKS)
def tasks(run: StepRun) -> Completion:
    """Decompose one repository's Story into Tasks.

    Returns:
        The phase result as an artifact; the journal of each Task is created in the same step.

    """
    dispatch: DispatchArguments = dispatch_arguments()
    spec: dict[str, JsonValue] = json_object(run.inputs.value(SPEC_RESULT))
    design: dict[str, JsonValue] = json_object(run.context.args.get(dispatch.KEY_DESIGN_SYSTEM) or {})
    additions: dict[str, JsonValue] = {
        **run.params(),
        "story": spec["story"],
        "specPaths": spec["specPaths"],
        "scopingPath": str(run.inputs.file(ARTIFACT_SPAN)),
        "itemsPath": str(run.inputs.file(ARTIFACT_ELEMENTS)),
        "uiPath": spec.get("uiPath"),
        "packagesDir": design.get(dispatch.DS_PACKAGES_DIR),
    }
    repository: str = check_type(additions.get("repoPath"), str)
    result: dict[str, JsonValue] = _phase(run, TASK_DECOMPOSITION_PHASE, task_decomposition.run, additions, repository)
    handed: list[Artifact] = _handed_files(run)
    for task in _objects(result.get("tasks", [])):
        identifier: JsonValue = task.get("id")
        if isinstance(identifier, str) and identifier:
            create_child_journal(run.journal_path.parent, BeadId(identifier), BEAD_TYPE_TASK, [_creating(run)], handed)
    return Completion(artifacts=(value_artifact(TASKS_RESULT, result),))


def repository_rows(run: StepRun) -> list[dict[str, JsonValue]]:
    """Join each repository's spec result and Task result, from the artifacts a step is handed.

    Returns:
        One row per repository with a spec result, in the order the spec steps ran: the
        repository, and its spec and Task results as the done rule reads them.

    """
    decomposed: dict[str, JsonValue] = {
        check_type(json_object(value).get("repoPath"), str): value for value in run.inputs.values(TASKS_RESULT)
    }
    rows: list[dict[str, JsonValue]] = []
    for value in run.inputs.values(SPEC_RESULT):
        spec: dict[str, JsonValue] = json_object(value)
        repository: str = check_type(json_object(spec["story"])["repoPath"], str)
        rows.append({"repository": repository, "spec": spec, "tasks": decomposed.get(repository, {})})
    return rows


@script_step(EDGES)
def edges(run: StepRun) -> Completion:
    """Write the dependency edges between the Tasks of the Epic's Stories.

    Returns:
        What the edge phase returns, as an artifact.

    """
    repos: list[str] = _strings(run.inputs.value(ARTIFACT_REPOSITORIES))

    def phase(context: RunContext, store: ArtifactStore, runner: AgentRunner, tools: Tools) -> dict[str, JsonValue]:
        return task_edges.run(context, store, runner, tools, repos)

    return Completion(artifacts=(value_artifact(EDGES_RESULT, _phase(run, TASK_EDGES_PHASE, phase, {})),))


def _owner(run: StepRun) -> str:
    """Read the owner of this dispatch's claim on the Epic.

    Returns:
        The owner the dispatch recorded in its arguments when it claimed the Epic.

    """
    return check_type(run.context.args[dispatch_arguments().KEY_OWNER], str)


@script_step(SCORE)
def score(run: StepRun) -> Completion:
    """Score the Epic's Tasks and apply the done rule.

    A repository that lacks its Story or its Tasks, and a Task left unscored, fail the step.

    Returns:
        The done rule's result.

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
