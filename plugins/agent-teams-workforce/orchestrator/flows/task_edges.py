"""The dependency edges between the Tasks of an Epic's Stories, as steps of the Epic's journal.

The Task edges container is created with its first step, which derives the edges the matrix's
``dependsOn`` links make between Tasks of different Stories. That step plans the rest: the
dependency listing, the mapper's session when the span has more than one repository, and the
edge write. Each step reads every repository's Story document and Tasks file from the artifacts
the Specs and Stories container and the Tasks container hold.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The Task dependency document is defined once, in the artifact-handoff skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import beadgraph
import beadwrite
from task_deps_contract import TaskDepsError, empty_task_deps, narrowed_task_deps_schema, parse_task_deps
from typeguard import CollectionCheckStrategy, check_type

from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
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
from orchestrator.flows.elaboration_files import (
    CLOSURE_EDGES,
    EDGE_CLOSURE,
    EDGE_LIST,
    EDGE_LISTING,
    EDGE_WRITE,
    EDGES_RESULT,
    MAPPER,
    MAPPER_SCHEMA,
    TASK_DEPS,
    TASKS_FILE,
    objects,
    span_stories,
)
from orchestrator.flows.elaboration_support import TASK_EDGES_PHASE, enter_phase

if TYPE_CHECKING:
    import hierarchy
    from step_journal_contract import StepPlan

TASK_EDGES: Final = "task edges written"
SEVERAL: Final = 2
"""The number of repositories from which Tasks of different Stories can depend on each other."""


@script_step(EDGE_CLOSURE)
def closure(run: StepRun) -> Completion:
    """Derive the edges the elements' requirements make between Tasks of different Stories.

    A requirement no Task builds fails the step.

    Returns:
        The closure edges file, with the listing, the mapper's step when the span has more than
        one repository, and the edge write planned after this step.

    """
    enter_phase(run.context, run.agents.emit, TASK_EDGES_PHASE, EDGE_CLOSURE)
    span: hierarchy.SpanStories = span_stories(run, None)
    found: dict[str, JsonValue] = json_object(run.tools.portfolio(EDGE_CLOSURE, beadwrite.closure_task_edges, span))
    path: Path = run.context.work / "closure-edges.json"
    write_json(path, found)
    if found.get("ok") is False or found.get("warnings") or json_object(found.get("summary", {})).get("warnings"):
        raise run.tools.failure(EDGE_CLOSURE, OTHER_CAUSE, found)
    handed: list[str] = list(run.step.get("inputs", []))
    listing: StepPlan = {
        "ref": "listing",
        "description": "List the Tasks of every Story for the dependency mapper",
        "purpose": "The Tasks and the edges already known are in one file",
        "script": EDGE_LISTING,
        "inputs": handed,
    }
    steps: list[NewStep] = [NewStep(listing, {})]
    written: list[str] = ["listing", *handed]
    if len(span.stories) >= SEVERAL:
        mapper: StepPlan = {
            "ref": "mapper",
            "description": "Map the dependencies between Tasks of different Stories",
            "purpose": "A Task that needs another Story's Task built first is known",
            "agent": MAPPER,
            "inputs": ["listing", *handed],
        }
        steps.append(NewStep(mapper, {}))
        written.insert(0, "mapper")
    write: StepPlan = {
        "description": "Write the edges between Tasks of different Stories",
        "purpose": "A Task that needs another Story's Task built first is blocked by it",
        "script": EDGE_WRITE,
        "inputs": written,
    }
    return Completion(artifacts=(file_artifact(CLOSURE_EDGES, path),), add=(StepGroup((*steps, NewStep(write, {}))),))


@script_step(EDGE_LISTING)
def listing(run: StepRun) -> Completion:
    """List every Story's Tasks with their edges, and narrow the mapper's schema to their names.

    Returns:
        The listing file; for a span of more than one repository, the mapper's schema too.

    """
    enter_phase(run.context, run.agents.emit, TASK_EDGES_PHASE, EDGE_LISTING)
    span: hierarchy.SpanStories = span_stories(run, None)
    rows: list[JsonValue] = []
    for index, files in enumerate(span.stories, 1):
        saved: dict[str, JsonValue] = strict_json(files.tasks_file)
        tasks: list[JsonValue] = [
            {name: task.get(name) for name in ("key", "title", "dependsOn")} for task in objects(saved.get("tasks", []))
        ]
        rows.append({"story": f"S{index}", "tasks": tasks, "edges": saved.get("edges", [])})
    path: Path = run.context.work / "task-deps-inputs.json"
    write_json(path, {"stories": rows, "closureEdgesPath": str(run.inputs.file(CLOSURE_EDGES))})
    artifacts = [file_artifact(EDGE_LIST, path)]
    if len(span.stories) >= SEVERAL:
        names: dict[str, str] = check_type(
            run.tools.portfolio(EDGE_LISTING, beadwrite.span_tasks, span),
            tuple[dict[str, str], list[tuple[str, str]], dict[str, str]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )[0]
        schema: Path = run.context.work / "task-deps.schema.json"
        write_json(schema, narrowed_task_deps_schema(list(names)))
        artifacts.append(file_artifact(MAPPER_SCHEMA, schema))
    return Completion(artifacts=tuple(artifacts))


@agent_step(MAPPER)
def mapper(run: StepRun) -> AgentLaunch:
    """Build the session that maps the dependencies between Tasks of different Stories.

    Returns:
        The launch: the dependency file as output, checked against the schema narrowed to the
        span's Task names.

    """
    enter_phase(run.context, run.agents.emit, TASK_EDGES_PHASE, MAPPER)
    span: hierarchy.SpanStories = span_stories(run, None)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(TASK_DEPS, output),))

    return AgentLaunch(
        output=run.context.work / "task-deps.json",
        validate=run.inputs.file(MAPPER_SCHEMA),
        outcome="Cross-Story Task dependencies for the supplied Stories.",
        accept=accept,
        add_dirs=(run.context.work,),
        files=(
            *((TASKS_FILE, files.tasks_file) for files in span.stories),
            (CLOSURE_EDGES, run.inputs.file(CLOSURE_EDGES)),
            (EDGE_LIST, run.inputs.file(EDGE_LIST)),
        ),
        hand_inputs=False,
    )


@script_step(EDGE_WRITE)
def write(run: StepRun) -> Completion:
    """Write every Task's edges to Tasks of the Epic's other Stories.

    Returns:
        The written record's file and the edges as the dispatch reports them.

    """
    enter_phase(run.context, run.agents.emit, TASK_EDGES_PHASE, EDGE_WRITE)
    mapped: Path | None = run.inputs.optional_file(TASK_DEPS)
    span: hierarchy.SpanStories = span_stories(run, mapped)
    accepted: dict[str, JsonValue] = json_object(empty_task_deps()) if mapped is None else strict_json(mapped)
    try:
        parse_task_deps(accepted)
    except TaskDepsError as exc:
        raise run.tools.failure(EDGE_WRITE, OTHER_CAUSE, {"taskDeps": str(mapped), "error": str(exc)}) from exc
    repo: Path = Path(check_type(run.context.args[dispatch_arguments().KEY_BEADS_REPO_PATH], str))

    def attempt() -> dict[str, JsonValue]:
        graph: beadgraph.Graph = run.tools.portfolio(EDGE_WRITE, beadgraph.load, repo)
        writer: beadgraph.Writer = run.tools.portfolio(EDGE_WRITE, beadgraph.Writer, repo)
        return json_object(
            run.tools.portfolio(EDGE_WRITE, beadwrite.write_all_task_edges, graph, writer, run.bead, span, also=[]),
        )

    written: dict[str, JsonValue] = run.tools.operation(EDGE_WRITE, attempt)
    path: Path = run.context.work / "task-edges" / "all.json"
    write_json(path, written)
    if written.get("ok") is False:
        raise run.tools.failure(EDGE_WRITE, OTHER_CAUSE, written)
    result: dict[str, JsonValue] = {
        "ok": True,
        "closureEdges": strict_json(run.inputs.file(CLOSURE_EDGES)),
        "crossStoryDependencies": accepted,
        "written": written,
    }
    return Completion(artifacts=(file_artifact(TASK_EDGES, path), value_artifact(EDGES_RESULT, result)))
