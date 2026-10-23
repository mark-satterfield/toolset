"""One repository's Tasks, as steps of the Epic's journal.

The Story bead write plans one container per repository under the Tasks container with its first
step, the decomposition context. That step plans the decomposer session and the plan step. The
plan step reads the Tasks file the decomposer wrote and plans what the plan calls for: a correction
session and another plan step when an item is uncited or a Task is unsized, at most ``CORRECTIONS``
times before a gap that remains fails the repository's Tasks as an item; otherwise one step per
Task bead write, the step that retires the Task beads the plan no longer names, and the written
record. A Task bead write is its own step, so the journal says which Task beads are written.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The bead metadata keys are generated from the beads-contract schema, their one definition.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
import beadgraph
import beadwrite
import hierarchy
import strictschema
from bead_metadata import ARG_REQUIREMENT_IDS, KEY_ELAB_KEY, KEY_REQUIREMENT_IDS
from matrixstore import Matrix, matrix_path, read_matrix
from typeguard import CollectionCheckStrategy, check_type

from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_changes import create_child_journal
from orchestrator.core.journal_registry import agent_step, script_step
from orchestrator.core.journal_steps import (
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import OutputValidator, StepError
from orchestrator.flows.architecture_files import ARTIFACT_TRD
from orchestrator.flows.elaboration_files import (
    ARTIFACT_ELEMENTS,
    ARTIFACT_SPAN,
    CONTEXT,
    CRITERIA,
    DATA_MODEL,
    DECOMPOSER,
    REPOSITORY,
    SPEC,
    SPEC_PACK,
    STORY,
    STORY_DOCUMENT,
    TASK,
    TASK_CONTEXT,
    TASK_CONTEXT_FILE,
    TASK_CONTEXT_SCHEMA,
    TASK_CORRECTION,
    TASK_EDGE_COUNTS,
    TASK_GAPS,
    TASK_KEY,
    TASK_PLAN,
    TASK_PLAN_RECORD,
    TASK_RECORD,
    TASK_RETIRE,
    TASK_WRITE,
    TASKS_FILE,
    TASKS_RESULT,
    UI_SOURCES,
    WORK,
    Repository,
    control_repository,
    creating,
    handed_on,
    objects,
    project_root,
    repository,
    repository_of,
    span_files,
    story_files,
    strings,
    write_contract,
)
from orchestrator.flows.elaboration_support import TASK_DECOMPOSITION_PHASE, enter_phase
from orchestrator.flows.repo_scoping import BuildContext, build_context, item_stacks
from orchestrator.flows.spec_authoring import design_system, items_by_story

# isort: split
# The journal modules put the pipeline-contracts scripts directory on sys.path.
from step_journal_contract import BEAD_TYPE_TASK, BeadId

if TYPE_CHECKING:
    from beadcontracts import TaskPlan
    from matrix_contract import EntryId
    from step_journal_contract import Artifact, Step, StepPlan

WORK_DECOMPOSE: Final = "decompose"
WORK_GAPS: Final = "gaps"
"""What a step of the decomposer does: the decomposition, or the correction of its gaps."""
GAPS_BEFORE: Final = "gaps before the correction"
RETIRED: Final = "tasks retired"
TASK_WARNINGS: Final = "task warnings"
TASKS_WRITTEN: Final = "tasks written"
SCHEMAS: Final = "skills/artifact-handoff/schemas"
TASK_GAPS_SCHEMA: Final = "task-gaps.schema.json"
"""The contract of the gaps file the plan step hands the decomposer's correction."""
UNCITED_STAGE: Final = "uncited-items"
CORRECTIONS: Final = 2
"""How many corrections of a plan's gaps run before a gap that remains fails the repository's Tasks."""


def _packages(run: StepRun) -> str | None:
    """Read the packages directory a cited cds bundle must sit in.

    Returns:
        The directory the dispatch's design system names, or None.

    """
    return check_type(design_system(run).get(dispatch_arguments().DS_PACKAGES_DIR), str | None)


def task_facts(bead: beadgraph.Bead) -> dict[str, JsonValue]:
    """Describe a Task bead that exists to the decomposer.

    Returns:
        Its id, title, elaboration key, status and the items it cites; ``bd show <id>`` prints
        its description.

    """
    raw: str | list[str] = bead.metadata.get(KEY_REQUIREMENT_IDS, [])
    decoded: object = json.loads(raw) if isinstance(raw, str) and raw else raw
    cited: list[JsonValue] = list(
        check_type(decoded, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS),
    )
    return {
        "id": bead.id,
        "title": bead.title,
        "elabKey": bead.metadata.get(KEY_ELAB_KEY),
        "status": bead.status,
        ARG_REQUIREMENT_IDS: cited,
    }


def _write_context(run: StepRun, held: Repository, existing: list[JsonValue]) -> Path:
    """Write the task context file of one repository's Story (``task-context.schema.json``).

    The file holds pointers, never a copy of what the matrix or the bead tracker holds: the
    Tasks that exist, by id and without their descriptions; each stack the Story builds in with
    the entries it builds there, for the decomposer's own ``atw-matrix work`` and ``atw-matrix
    uses``; and ``dependsOn`` (``repo_scoping.build_context``): what the Tasks depend on, never
    work.

    Returns:
        The file.

    """
    every: dict[str, JsonValue] = json_object(
        run.tools.portfolio(TASK_CONTEXT, hierarchy.story_builds, span_files(run.inputs)),
    )
    built: list[JsonValue] = [item for item in every.values() if json_object(item)["slug"] == held.slug]
    matrix: Matrix = run.tools.portfolio(TASK_CONTEXT, read_matrix, matrix_path(None, os.environ))
    stacks: dict[EntryId, list[EntryId]] = run.tools.portfolio(TASK_CONTEXT, item_stacks, matrix, built)
    depended: BuildContext = run.tools.portfolio(TASK_CONTEXT, build_context, matrix, built, items_by_story(every))
    return write_contract(
        run.context.work / f"tasks-{held.slug}.context.json",
        {
            "epic": str(run.bead),
            "repoPath": held.path,
            "slug": held.slug,
            "stacks": [{"stack": stack, "entries": list(entries)} for stack, entries in stacks.items()],
            "existingTasks": existing,
            "dependsOn": [json_object(dependency) for dependency in depended["dependsOn"]],
        },
        TASK_CONTEXT_SCHEMA,
    )


@script_step(TASK_CONTEXT)
def context(run: StepRun) -> Completion:
    """Gather what one repository's Tasks are decomposed from, and plan the decomposition.

    The Tasks that exist under the Story and that are started, or that elaboration did not
    write, are handed to the decomposer so it reuses them. The decomposer asks the matrix for the
    rest itself: for each stack the Story builds in, the open Tasks of other Epics that name the
    stack or an entry it holds (``atw-matrix work --id <stack> --not-epic <epic>``), and the
    shared capabilities the entries the Tasks build must use (``atw-matrix uses --ids``). What
    the Story builds is the ``items`` of the repository context. The decomposer writes those
    matrix ids into each Task. Nothing is recorded in the matrix.

    Returns:
        The repository and the task context file as artifacts, with the decomposer's step and
        the plan step planned after this one.

    """
    held: Repository = repository_of(dict(run.params()), TASK_CONTEXT)
    enter_phase(run.context, run.agents.emit, TASK_DECOMPOSITION_PHASE, TASK_CONTEXT, held.path)
    story: str = check_type(json_object(run.inputs.value(STORY))["id"], str)
    control: Path = control_repository()

    def read() -> beadgraph.Graph:
        return run.tools.portfolio(TASK_CONTEXT, beadgraph.load, control, with_description=True)

    graph: beadgraph.Graph = run.tools.operation(TASK_CONTEXT, read)
    existing: list[JsonValue] = [
        task_facts(bead)
        for bead in graph.beads.values()
        if bead.parent == story
        and bead.kind == "task"
        and (beadwrite.task_started(bead) or not str(bead.metadata.get(KEY_ELAB_KEY, "")).startswith("task:"))
    ]
    facts: Path = _write_context(run, held, existing)
    name: str = Path(held.path).name
    upstream: list[str] = list(run.step.get("inputs", []))
    decompose: StepPlan = {
        "ref": "decompose",
        "description": f"Decompose the Story of {name} into Tasks",
        "purpose": "Every thing the Story builds is cited by a sized Task",
        "agent": DECOMPOSER,
        "inputs": upstream,
    }
    planning: StepPlan = {
        "description": f"Plan the Task beads of {name}",
        "purpose": "The Tasks are in build order, every item is cited and every Task is sized",
        "script": TASK_PLAN,
        "inputs": ["decompose", *upstream],
    }
    return Completion(
        artifacts=(
            value_artifact(REPOSITORY, held.facts()),
            file_artifact(TASK_CONTEXT_FILE, facts),
        ),
        add=(StepGroup((NewStep(decompose, {WORK: WORK_DECOMPOSE}), NewStep(planning, {}))),),
    )


def task_grouping_check(context_file: Path, schema_file: Path) -> OutputValidator:
    """Build the check of the decomposer's Tasks file: its schema, then how its Tasks group what the Story builds.

    Args:
        context_file: The repository context (``spec-context.schema.json``), whose ``items`` are
            what the Story builds.
        schema_file: The Tasks file's schema.

    Returns:
        A check that reads the Tasks file as strict JSON, validates it against the schema
        (``jsonschema.ValidationError``), and raises ``ValueError`` with every problem
        ``hierarchy.task_grouping_problems`` reports; both send the session to its one
        correction (``agents.CONTENT_FAILURES``).

    """

    def check(path: Path) -> dict[str, JsonValue]:
        document: dict[str, JsonValue] = strict_json(path)
        strictschema.validate(document, strict_json(schema_file), location=schema_file)
        items: list[JsonValue] = check_type(json_object(strict_json(context_file))["items"], list[JsonValue])
        tasks: list[JsonValue] = check_type(document["tasks"], list[JsonValue])
        problems: list[str] = hierarchy.task_grouping_problems(items, tasks)
        if problems:
            raise ValueError("; ".join(problems))
        return document

    return check


@agent_step(DECOMPOSER)
def decomposer(run: StepRun) -> AgentLaunch:
    """Build the session of a step the decomposer performs: the decomposition, or its correction.

    The correction continues the session of the decomposition, when the journal holds it.

    Returns:
        The launch: the Tasks file, or the correction file, as output, checked against its schema.

    """
    held: Repository = repository(run.inputs)
    correcting: bool = run.params().get(WORK) == WORK_GAPS
    enter_phase(
        run.context,
        run.agents.emit,
        TASK_DECOMPOSITION_PHASE,
        UNCITED_STAGE if correcting else WORK_DECOMPOSE,
        held.path,
    )
    labels: tuple[str, ...] = (SPEC, DATA_MODEL, CRITERIA, STORY_DOCUMENT, ARTIFACT_SPAN, ARTIFACT_ELEMENTS)
    files: list[tuple[str, Path]] = [(label, run.inputs.file(label)) for label in labels]
    sources: Path | None = run.inputs.optional_file(UI_SOURCES)
    if sources is not None:
        files.append((UI_SOURCES, sources))
    files.extend((label, run.inputs.file(label)) for label in (ARTIFACT_TRD, CONTEXT, SPEC_PACK, TASK_CONTEXT_FILE))
    if correcting:
        files.extend((label, run.inputs.file(label)) for label in (TASKS_FILE, TASK_GAPS))
    earlier: Step | None = run.earlier_sibling(DECOMPOSER) if correcting else None
    name: str = TASK_CORRECTION if correcting else TASKS_FILE
    turn: int = len(run.inputs.files(TASK_CORRECTION)) + 1

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(name, output),))

    return AgentLaunch(
        output=run.context.work
        / (f"tasks-{held.slug}.correction-{turn}.json" if correcting else f"tasks-{held.slug}.json"),
        validate=(
            run.tools.plugin / SCHEMAS / "tasks-correction.schema.json"
            if correcting
            else task_grouping_check(run.inputs.file(CONTEXT), run.tools.plugin / SCHEMAS / "tasks.schema.json")
        ),
        outcome=(
            "Task and size corrections for the recorded coverage gaps."
            if correcting
            else "Build activities, dependencies and sizes for what this repository's Story builds."
        ),
        accept=accept,
        add_dirs=(run.context.work, Path(held.path)),
        files=tuple(files),
        corrective=not correcting,
        resume_from=None if earlier is None or "session" not in earlier else earlier["id"],
        hand_inputs=False,
    )


def _correction_steps(run: StepRun, name: str) -> StepGroup:
    """Plan the correction of a plan's gaps and the plan step that follows it.

    Returns:
        The decomposer's correction step and a second plan step, after the plan step.

    """
    handed: list[str] = [*run.step.get("inputs", []), run.step["id"]]
    correct: StepPlan = {
        "ref": "correction",
        "description": f"Correct what {name} builds that no Task cites, and the unsized Tasks",
        "purpose": "Every thing the Story builds is cited by a sized Task",
        "agent": DECOMPOSER,
        "inputs": handed,
    }
    again: StepPlan = {
        "description": f"Plan the Task beads of {name} with the correction",
        "purpose": "The Tasks are in build order, every item is cited and every Task is sized",
        "script": TASK_PLAN,
        "inputs": [*handed, "correction"],
    }
    return StepGroup((NewStep(correct, {WORK: WORK_GAPS}), NewStep(again, {})))


def _write_steps(run: StepRun, name: str, planned: TaskPlan) -> StepGroup:
    """Plan one step per Task bead write, then the retiring step and the written record.

    Returns:
        The steps in build order, after the plan step.

    """
    handed: list[str] = list(run.step.get("inputs", []))
    steps: list[NewStep] = []
    written: list[str] = []
    for index, task in enumerate(planned["tasks"], 1):
        written.append(f"task-{index}")
        write: StepPlan = {
            "ref": written[-1],
            "description": f"Write the Task bead {task['key']} of {name}: {task['title']}",
            "purpose": "The Story has this Task as a bead",
            "script": TASK_WRITE,
            "inputs": handed,
        }
        steps.append(NewStep(write, {"key": task["key"]}))
    retire: StepPlan = {
        "ref": "retire",
        "description": f"Retire the Task beads of {name} the plan no longer names",
        "purpose": "The Story's unstarted Task beads are the plan's, and no edge points at a deleted one",
        "script": TASK_RETIRE,
        "inputs": [*handed, *written],
    }
    record: StepPlan = {
        "description": f"Record the Tasks written for {name}",
        "purpose": "The run can report the Story's Tasks",
        "script": TASK_RECORD,
        "inputs": [*handed, *written, "retire"],
    }
    return StepGroup((*steps, NewStep(retire, {}), NewStep(record, {})))


def _gap_detail(planned: TaskPlan, name: str) -> str:
    """Name the gaps a plan still has after its last correction.

    Returns:
        What no Task cites, the unsized Tasks, or that the plan has no Task.

    """
    gaps: list[str] = []
    if not planned["tasks"]:
        gaps.append("the plan has no Task")
    if planned["uncited"]:
        gaps.append(f"no Task cites {', '.join(planned['uncited'])}")
    if planned["unsized"]:
        gaps.append(f"unsized Tasks {', '.join(planned['unsized'])}")
    return f"{name} after {CORRECTIONS} corrections: {'; '.join(gaps)}"


@script_step(TASK_PLAN)
def plan(run: StepRun) -> Completion:
    """Read the Tasks the decomposer wrote and plan what they call for.

    A correction the step is handed is merged into the Tasks file first.

    Returns:
        For a plan with an uncited item, an unsized Task or no Task, while fewer than
        ``CORRECTIONS`` corrections have run: the gaps file (``task-gaps.schema.json``), with
        a correction and another plan step planned. Otherwise the plan's record, with one step
        per Task bead write, the retiring step and the written record planned.

    Raises:
        StepError: The plan still has a gap after the last correction: an item failure whose
            message names the uncited items and the unsized Tasks.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, TASK_DECOMPOSITION_PHASE, TASK_PLAN, held.path)
    files: hierarchy.StoryFiles = story_files(run.inputs)
    correction: Path | None = run.inputs.optional_file(TASK_CORRECTION)
    merged: dict[str, JsonValue] = {}
    if correction is not None:
        merged = json_object(
            run.tools.portfolio(TASK_PLAN, beadwrite.add_corrective_tasks, files, correction=correction),
        )
    planned: TaskPlan = run.tools.portfolio(
        TASK_PLAN,
        beadwrite.plan_story_tasks,
        files,
        root=project_root(),
        packages_dir=_packages(run),
    )
    uncited: list[JsonValue] = list(planned["uncited"])
    unsized: list[JsonValue] = list(planned["unsized"])
    name: str = Path(held.path).name
    if not planned["tasks"] or uncited or unsized:
        if len(run.inputs.files(TASK_CORRECTION)) >= CORRECTIONS:
            stage: str = UNCITED_STAGE if planned["tasks"] else WORK_DECOMPOSE
            raise StepError(stage, OTHER_CAUSE, (_gap_detail(planned, name), str(files.tasks_file)))
        gaps: Path = write_contract(
            run.context.work / f"tasks-{held.slug}.gaps.json",
            {"uncited": uncited, "unsized": unsized, "empty": not planned["tasks"]},
            TASK_GAPS_SCHEMA,
        )
        return Completion(
            artifacts=(
                file_artifact(TASK_GAPS, gaps),
                value_artifact(GAPS_BEFORE, {"uncited": uncited, "unsized": unsized}),
            ),
            add=(_correction_steps(run, name),),
        )
    coverage: dict[str, JsonValue] = {}
    if correction is not None:
        before: dict[str, JsonValue] = json_object(run.inputs.values(GAPS_BEFORE)[0])
        coverage = {
            "uncitedBefore": before["uncited"],
            "uncitedAfter": uncited,
            "unsizedBefore": before["unsized"],
            "unsizedAfter": unsized,
            **merged,
        }
    warnings: list[JsonValue] = list(planned["warnings"])
    keys: list[JsonValue] = [task["key"] for task in planned["tasks"]]
    record: dict[str, JsonValue] = {"tasks": keys, "warnings": warnings, "coverage": coverage}
    return Completion(
        artifacts=(value_artifact(TASK_PLAN_RECORD, record),),
        add=(_write_steps(run, name, planned),),
    )


@script_step(TASK_WRITE)
def write_task(run: StepRun) -> Completion:
    """Write one Task bead of a Story and create its journal.

    The Task is found by its elaboration key under the Story, so a second run of this step
    refreshes the Task it wrote and creates no other.

    Returns:
        The Task as the dispatch reports it, the counts of its edges, and the write's warnings.

    """
    held: Repository = repository(run.inputs)
    key: str = check_type(run.params().get("key"), str)
    enter_phase(run.context, run.agents.emit, TASK_DECOMPOSITION_PHASE, TASK_WRITE, held.path)
    files: hierarchy.StoryFiles = story_files(run.inputs)
    control: Path = control_repository()

    def attempt() -> dict[str, JsonValue]:
        writer: beadgraph.Writer = run.tools.portfolio(TASK_WRITE, beadgraph.Writer, control)
        return json_object(
            run.tools.portfolio(
                TASK_WRITE,
                beadwrite.write_task,
                writer,
                run.bead,
                files,
                key=key,
                root=project_root(),
                packages_dir=_packages(run),
            ),
        )

    written: dict[str, JsonValue] = run.tools.operation(TASK_WRITE, attempt)
    task: dict[str, JsonValue] = json_object(written["task"])
    handed: list[Artifact] = [*handed_on(run.inputs, TASKS_FILE), value_artifact(TASK_KEY, key)]
    create_child_journal(
        run.journal_path.parent,
        BeadId(check_type(task["id"], str)),
        BEAD_TYPE_TASK,
        [creating(run)],
        handed,
    )
    return Completion(
        artifacts=(
            value_artifact(TASK, task),
            value_artifact(TASK_EDGE_COUNTS, written["edges"]),
            value_artifact(TASK_WARNINGS, written["warnings"]),
        ),
    )


@script_step(TASK_RETIRE)
def retire(run: StepRun) -> Completion:
    """Delete the Story's unstarted Task beads the plan no longer names, moving edges onto their replacements.

    Returns:
        What was deleted and which edges moved.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, TASK_DECOMPOSITION_PHASE, TASK_RETIRE, held.path)
    files: hierarchy.StoryFiles = story_files(run.inputs)
    control: Path = control_repository()

    def attempt() -> dict[str, JsonValue]:
        graph: beadgraph.Graph = run.tools.portfolio(TASK_RETIRE, beadgraph.load, control, with_description=True)
        writer: beadgraph.Writer = run.tools.portfolio(TASK_RETIRE, beadgraph.Writer, control)
        return json_object(
            run.tools.portfolio(
                TASK_RETIRE,
                beadwrite.retire_superseded_tasks,
                graph,
                writer,
                run.bead,
                files,
                root=project_root(),
                packages_dir=_packages(run),
            ),
        )

    retired: dict[str, JsonValue] = run.tools.operation(TASK_RETIRE, attempt)
    return Completion(artifacts=(value_artifact(RETIRED, retired), value_artifact(TASK_WARNINGS, retired["warnings"])))


@script_step(TASK_RECORD)
def record(run: StepRun) -> Completion:
    """Record what was written for one repository's Tasks, from the steps that wrote them.

    Returns:
        The written record's file and the repository's result as the done rule and the dispatch
        result read it.

    """
    held: Repository = repository(run.inputs)
    story: dict[str, JsonValue] = json_object(run.inputs.value(STORY))
    planned: dict[str, JsonValue] = json_object(run.inputs.value(TASK_PLAN_RECORD))
    tasks: list[dict[str, JsonValue]] = objects(run.inputs.values(TASK))
    counts: list[dict[str, JsonValue]] = objects(run.inputs.values(TASK_EDGE_COUNTS))
    warnings: list[JsonValue] = [
        *strings(planned["warnings"]),
        *(warning for held_warnings in run.inputs.values(TASK_WARNINGS) for warning in strings(held_warnings)),
    ]
    edges: dict[str, JsonValue] = {
        name: sum(check_type(count[name], int) for count in counts) for name in ("added", "removed", "standing")
    }
    summary: dict[str, JsonValue] = {
        action: sum(task["action"] == action for task in tasks) for action in ("created", "updated", "unchanged")
    }
    rows: list[JsonValue] = list(tasks)
    result: dict[str, JsonValue] = {
        "ok": True,
        "repoPath": held.path,
        "story": {"id": story["id"], "elabKey": story["elabKey"]},
        "tasks": rows,
        "edges": edges,
        "coverage": planned["coverage"],
        "warnings": warnings,
        "summary": summary,
    }
    path: Path = run.context.work / f"tasks-{held.slug}.written.json"
    write_json(path, result)
    return Completion(artifacts=(file_artifact(TASKS_WRITTEN, path), value_artifact(TASKS_RESULT, result)))
