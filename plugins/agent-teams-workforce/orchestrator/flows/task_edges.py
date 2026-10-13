"""The dependency edges between the Tasks of an Epic's Stories, as steps of the Epic's journal.

The Task edges container is created with its first step, which derives the edges that the
matrix's dependency relationships between what the Tasks build make between Tasks of different
Stories; the span step wrote those relationships into the items as what each requires. That step
plans the rest: the dependency listing, the mapper's session when the span has more than one
repository, and the edge write. Each step reads every repository's Story document and Tasks file
from the artifacts the Specs and Stories container and the Tasks container hold.

A dependency the mapper finds between two stacks that the matrix does not hold is recorded in the
matrix when the mapper's result is accepted. The order of Tasks inside one stack is finer than
the matrix holds and is recorded on the beads only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The Task dependency document and the matrix contract are defined once, in the artifact-handoff skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
import beadgraph
import beadwrite
from bead_metadata import ARG_REQUIREMENT_IDS
from matrix_contract import (
    AUTHORITY_SIDE,
    REL_CALLS,
    REL_CONSUMES,
    REL_IMPORTS,
    REL_READS,
    REL_RUNS_IN,
    RELATIONSHIP_RULES,
    EntryId,
    RelationshipKind,
    RelationshipRule,
)
from matrixstore import Matrix, as_entry_id, matrix_path, update_matrix
from matrixtraverse import dependencies, holder
from matrixwrite import LinkResult, link
from task_deps_contract import (
    KIND_CONTRACT,
    KIND_DATA,
    KIND_EVENT_FLOW,
    KIND_INFRASTRUCTURE,
    TaskDeps,
    TaskDepsEdge,
    TaskDepsEdgeKind,
    TaskDepsError,
    empty_task_deps,
    narrowed_task_deps_schema,
    parse_task_deps,
)
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
    strings,
)
from orchestrator.flows.elaboration_support import TASK_EDGES_PHASE, enter_phase

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import hierarchy
    from step_journal_contract import StepPlan

TASK_EDGES: Final = "task edges written"
DEPENDENCIES_RECORDED: Final = "dependencies recorded in the matrix"
SEVERAL: Final = 2
"""The number of repositories from which Tasks of different Stories can depend on each other."""
DIRECT: Final = 1
"""The depth of a dependency relationship that starts at a stack or at an entry the stack holds."""
RELATIONSHIPS_OF: Final[dict[TaskDepsEdgeKind, tuple[RelationshipKind, ...]]] = {
    KIND_CONTRACT: (REL_IMPORTS, REL_CALLS),
    KIND_DATA: (REL_READS,),
    KIND_INFRASTRUCTURE: (REL_RUNS_IN,),
    KIND_EVENT_FLOW: (REL_CONSUMES,),
}
"""The matrix's dependency kinds that state what a mapper's edge kind says the dependent Task needs."""


def built_by_task(span: hierarchy.SpanStories) -> dict[str, list[EntryId]]:
    """Read which matrix entries each Task of the span builds, from the saved files.

    An id in the elements file that does not have the form of an entry id raises ``MatrixError``
    from ``as_entry_id``.

    Args:
        span: The Stories of the span, in span order, each with its Tasks file.

    Returns:
        Each Task by its ``S<i>-<key>`` name, with the entry of every item it cites.

    """
    entries: dict[str, EntryId] = {
        check_type(item["id"], str): as_entry_id(check_type(item["matrixId"], str))
        for item in objects(strict_json(span.scope.elements).get("items", []))
        if "matrixId" in item
    }
    built: dict[str, list[EntryId]] = {}
    for index, files in enumerate(span.stories, 1):
        for task in objects(strict_json(files.tasks_file).get("tasks", [])):
            cited: list[str] = strings(task.get(ARG_REQUIREMENT_IDS, []))
            built[f"S{index}-{task['key']}"] = [entries[item] for item in cited if item in entries]
    return built


def _by_stack(matrix: Matrix, entries: Sequence[EntryId]) -> dict[EntryId, list[EntryId]]:
    """Group entries by the stack that holds each.

    Returns:
        Each stack with the entries given that it holds, the stack first when it is among them;
        an entry with no stack is left out.

    """
    grouped: dict[EntryId, list[EntryId]] = {}
    entry_id: EntryId
    for entry_id in entries:
        home: EntryId | None = holder(matrix, entry_id)
        if home is not None:
            grouped.setdefault(home, [home])
            if entry_id != home:
                grouped[home].append(entry_id)
    return grouped


def _stated(
    matrix: Matrix,
    edge: TaskDepsEdge,
    starts: Sequence[EntryId],
    ends: Sequence[EntryId],
) -> LinkResult | None:
    """Record one mapper edge as the first dependency relationship the registry allows between its ends.

    The kinds tried are those of the edge's kind, in order; the ends tried are the stack before
    the entries the Task builds in it, so a dependency found at stack level is recorded with the
    stacks as its ends wherever the kind may join two stacks.

    Returns:
        What ``link`` recorded, on the architecture side; None when no kind of the edge's kind
        may join any of the starts to any of the ends.

    """
    kind: RelationshipKind
    for kind in RELATIONSHIPS_OF[edge["kind"]]:
        rule: RelationshipRule = RELATIONSHIP_RULES[kind]
        if rule.required:
            continue
        start: EntryId
        for start in starts:
            if matrix.entry(start).kind not in rule.sources:
                continue
            end: EntryId
            for end in ends:
                if matrix.entry(end).kind in rule.targets:
                    return link(matrix, kind, start, end, AUTHORITY_SIDE)
    return None


def record_dependencies(deps: TaskDeps, built: Mapping[str, Sequence[EntryId]]) -> dict[str, JsonValue]:
    """Record in the matrix each dependency between two stacks that the mapper found and the matrix lacks.

    An edge runs from the prerequisite Task to the dependent Task. For each pair of different
    stacks the two Tasks build in, a dependency is lacking when no dependency relationship that
    starts at the dependent stack, or at an entry it holds, ends at the prerequisite stack or at
    an entry that one holds. A matrix that cannot be read or written, or that refuses a
    relationship, raises ``MatrixError``.

    Args:
        deps: The mapper's edges.
        built: The entries each Task builds, by Task name (:func:`built_by_task`).

    Returns:
        ``recorded``: each relationship added, with the edge it states. ``notRecorded``: each
        lacking dependency no registered kind can state between what the two Tasks build, with
        the edge, the two stacks and the kinds tried.

    """

    def change(matrix: Matrix) -> dict[str, JsonValue]:
        recorded: list[JsonValue] = []
        left: list[JsonValue] = []
        edge: TaskDepsEdge
        for edge in deps["edges"]:
            prerequisites: dict[EntryId, list[EntryId]] = _by_stack(matrix, built.get(edge["from"], ()))
            dependents: dict[EntryId, list[EntryId]] = _by_stack(matrix, built.get(edge["to"], ()))
            for dependent, starts in dependents.items():
                held: set[EntryId] = {
                    found.stack
                    for found in dependencies(matrix, [dependent])
                    if found.depth == DIRECT and found.stack is not None
                }
                for prerequisite, ends in prerequisites.items():
                    if prerequisite == dependent or prerequisite in held:
                        continue
                    stated: LinkResult | None = _stated(matrix, edge, starts, ends)
                    facts: dict[str, JsonValue] = {"from": edge["from"], "to": edge["to"], "kind": edge["kind"]}
                    if stated is None:
                        tried: list[JsonValue] = list(RELATIONSHIPS_OF[edge["kind"]])
                        left.append({**facts, "dependent": dependent, "prerequisite": prerequisite, "tried": tried})
                    else:
                        recorded.append({**facts, "relationship": stated["relationship"]})
        return {"recorded": recorded, "notRecorded": left}

    return update_matrix(matrix_path(None, os.environ), change)


@script_step(EDGE_CLOSURE)
def closure(run: StepRun) -> Completion:
    """Derive the edges the items' requirements make between Tasks of different Stories.

    An item requires another where the matrix holds a dependency relationship between what the
    two build (``atw-matrix deps --of``), as the span step wrote into the elements file. A
    requirement no Task builds fails the step.

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

    Accepting the mapper's result records in the matrix each dependency between two stacks that
    it found and the matrix lacks, and the step is done only when the matrix has confirmed the
    writes.

    Returns:
        The launch: the dependency file as output, checked against the schema narrowed to the
        span's Task names.

    """
    enter_phase(run.context, run.agents.emit, TASK_EDGES_PHASE, MAPPER)
    span: hierarchy.SpanStories = span_stories(run, None)

    def accept(accepted: StepRun, output: Path) -> Completion:
        try:
            found: TaskDeps = parse_task_deps(strict_json(output))
        except TaskDepsError as exc:
            raise accepted.tools.failure(MAPPER, OTHER_CAUSE, {"taskDeps": str(output), "error": str(exc)}) from exc
        built: dict[str, list[EntryId]] = accepted.tools.portfolio(MAPPER, built_by_task, span)
        recorded: dict[str, JsonValue] = accepted.tools.portfolio(MAPPER, record_dependencies, found, built)
        return Completion(
            artifacts=(file_artifact(TASK_DEPS, output), value_artifact(DEPENDENCIES_RECORDED, recorded)),
        )

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
