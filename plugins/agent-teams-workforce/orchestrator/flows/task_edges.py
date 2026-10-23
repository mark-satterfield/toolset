"""The dependency edges between the Tasks of an Epic's Stories, as steps of the Epic's journal.

The Task edges container is created with its first step, which derives the edges that the
matrix's dependency relationships between what the Tasks build make between Tasks of different
Stories; the span step wrote those relationships into the items as what each requires. That step
plans the rest: the dependency listing, the mapper's session when the span has more than one
repository, and the edge write. Each step reads every repository's Story document and Tasks file
from the artifacts the Specs and Stories container and the Tasks container hold.

The mapper's edges are never written into the matrix: the matrix's architecture side is what
arc42 states, and the beads edge alone carries build order.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The Task dependency document is defined once, in the artifact-handoff skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
import beadgraph
import beadwrite
import strictschema
from task_deps_contract import TaskDepsError, empty_task_deps, parse_task_deps
from typeguard import CollectionCheckStrategy, check_type

from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE, warning_note
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
    CLOSURE_EDGES_SCHEMA,
    EDGE_CLOSURE,
    EDGE_LIST,
    EDGE_LISTING,
    EDGE_WRITE,
    EDGES_RESULT,
    LISTING_SCHEMA,
    MAPPER,
    SCHEMAS,
    TASK_DEPS,
    TASK_DEPS_SCHEMA,
    TASKS_FILE,
    span_stories,
    write_contract,
)
from orchestrator.flows.elaboration_support import TASK_EDGES_PHASE, emit_event, enter_phase

if TYPE_CHECKING:
    import hierarchy
    from step_journal_contract import StepPlan

    from orchestrator.core.models import OutputValidator

TASK_EDGES: Final = "task edges written"
SEVERAL: Final = 2
"""The number of repositories from which Tasks of different Stories can depend on each other."""


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
    path: Path = write_contract(run.context.work / "closure-edges.json", found, CLOSURE_EDGES_SCHEMA)
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
    """Name each Story's Tasks file for the dependency mapper, in span order.

    The listing points to the Tasks files and the closure edges file and copies none of them
    (``task-dependency-listing.schema.json``).

    Returns:
        The listing file.

    """
    enter_phase(run.context, run.agents.emit, TASK_EDGES_PHASE, EDGE_LISTING)
    span: hierarchy.SpanStories = span_stories(run, None)
    rows: list[JsonValue] = [
        {"story": f"S{index}", "repoPath": files.repo, "tasksFile": str(files.tasks_file)}
        for index, files in enumerate(span.stories, 1)
    ]
    path: Path = write_contract(
        run.context.work / "task-deps-inputs.json",
        {"stories": rows, "closureEdgesPath": str(run.inputs.file(CLOSURE_EDGES))},
        LISTING_SCHEMA,
    )
    return Completion(artifacts=(file_artifact(EDGE_LIST, path),))


def task_deps_check(span: hierarchy.SpanStories) -> OutputValidator:
    """Build the check of the mapper's dependency file: its contract, then the Task keys it names.

    Args:
        span: The Stories of the span with their Tasks files.

    Returns:
        A check that validates the file against ``task-deps.schema.json``
        (``jsonschema.ValidationError``) and raises ``ValueError`` naming every ``from`` or
        ``to`` that is no Task key of the span; both send the session to its one correction.

    """
    contract: Path = SCHEMAS / TASK_DEPS_SCHEMA
    keys: frozenset[str] = frozenset(
        check_type(
            beadwrite.span_tasks(span),
            tuple[dict[str, str], list[tuple[str, str]], dict[str, str]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )[0],
    )

    def check(path: Path) -> dict[str, JsonValue]:
        document: dict[str, JsonValue] = strict_json(path)
        strictschema.validate(document, strict_json(contract), location=contract)
        named: list[str] = [
            str(end)
            for edge in check_type(document["edges"], list[dict[str, JsonValue]])
            for end in (edge["from"], edge["to"])
            if end not in keys
        ]
        if named:
            message: str = f"not a Task key of the span: {', '.join(dict.fromkeys(named))}"
            raise ValueError(message)
        return document

    return check


@agent_step(MAPPER)
def mapper(run: StepRun) -> AgentLaunch:
    """Build the session that maps the dependencies between Tasks of different Stories.

    Accepting the mapper's result writes nothing into the matrix: the edges reach beads in the
    edge write, and the beads edge alone carries build order.

    Returns:
        The launch: the dependency file as output, checked against ``task-deps.schema.json`` and
        the span's Task keys.

    """
    enter_phase(run.context, run.agents.emit, TASK_EDGES_PHASE, MAPPER)
    span: hierarchy.SpanStories = span_stories(run, None)

    def accept(accepted: StepRun, output: Path) -> Completion:
        try:
            parse_task_deps(strict_json(output))
        except TaskDepsError as exc:
            raise accepted.tools.failure(MAPPER, OTHER_CAUSE, {"taskDeps": str(output), "error": str(exc)}) from None
        return Completion(artifacts=(file_artifact(TASK_DEPS, output),))

    return AgentLaunch(
        output=run.context.work / "task-deps.json",
        validate=run.tools.portfolio(MAPPER, task_deps_check, span),
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
        raise run.tools.failure(EDGE_WRITE, OTHER_CAUSE, {"taskDeps": str(mapped), "error": str(exc)}) from None
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
    warning: str
    for warning in check_type(written.get("warnings", []), list[str]):
        emit_event(run.agents.emit, warning_note(EDGE_WRITE, warning))
    if written.get("ok") is False:
        raise run.tools.failure(EDGE_WRITE, OTHER_CAUSE, written)
    result: dict[str, JsonValue] = {
        "ok": True,
        "closureEdges": strict_json(run.inputs.file(CLOSURE_EDGES)),
        "crossStoryDependencies": accepted,
        "written": written,
    }
    return Completion(artifacts=(file_artifact(TASK_EDGES, path), value_artifact(EDGES_RESULT, result)))
