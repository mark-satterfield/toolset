"""Cross-Story dependency acceptance and deterministic edge writes."""

from __future__ import annotations

import sys
from pathlib import Path

# The Task dependency document is defined once, in the artifact-handoff skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import beadgraph
import beadwrite
import hierarchy
from task_deps_contract import TaskDepsError, empty_task_deps, narrowed_task_deps_schema, parse_task_deps
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE, phase_event
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext
from orchestrator.core.tools import Tools
from orchestrator.flows.architecture_support import TASK_EDGES_PHASE, read
from orchestrator.flows.elaboration_support import emit_event

_ARGUMENT_ERROR: str = "Arguments violate the task_edges input contract"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run(
    context: RunContext,
    store: ArtifactStore,
    runner: AgentRunner,
    tools: Tools,
    repos: list[str],
) -> dict[str, JsonValue]:
    """Accept cross-Story dependencies and write the deterministic edges.

    Returns:
        The accepted dependency report and measured write results.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    index: int
    slug: str
    if (
        not (isinstance(context, RunContext))
        or not (isinstance(store, ArtifactStore))
        or not (isinstance(runner, AgentRunner))
        or not (isinstance(tools, Tools))
        or not (isinstance(repos, list))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    stage: str = TASK_EDGES_PHASE
    context.stage = stage
    emit_event(runner.emit, phase_event(TASK_EDGES_PHASE, "closure-edges"))
    closure: dict[str, JsonValue] = json_object(
        tools.portfolio(stage, beadwrite.closure_task_edges, context.work, repos),
    )
    closure_path: Path = context.work / "closure-edges.json"
    write_json(closure_path, closure)
    if closure.get("ok") is False or closure.get("warnings") or json_object(closure.get("summary", {})).get("warnings"):
        raise tools.failure(stage, OTHER_CAUSE, closure)
    slugs: dict[str, str] = check_type(
        tools.portfolio(stage, hierarchy.repo_slugs, repos),
        dict[str, str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    task_paths: tuple[str, ...] = tuple(str(context.work / f"tasks-{slug}.json") for slug in slugs.values())
    listing: Path = context.work / "task-deps-inputs.json"
    rows: list[
        dict[
            str,
            list[dict[str, int | float | str | list[JsonValue] | dict[str, JsonValue] | None]]
            | int
            | float
            | str
            | list[JsonValue]
            | dict[str, JsonValue]
            | None,
        ]
    ] = []
    for index, slug in enumerate(slugs.values(), 1):
        doc: dict[str, JsonValue] = read(context.work / f"tasks-{slug}.json")
        rows.append(
            {
                "story": f"S{index}",
                "tasks": [
                    {k: t.get(k) for k in ("key", "title", "dependsOn")}
                    for t in check_type(
                        doc.get("tasks", []),
                        list[dict[str, JsonValue]],
                        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                    )
                ],
                "edges": doc.get("edges", []),
            },
        )
    write_json(listing, {"stories": rows, "closureEdgesPath": str(closure_path)})
    final: Path = context.work / "task-deps.json"
    if len(repos) > 1:
        keys: dict[str, str] = check_type(
            tools.portfolio(stage, beadwrite.span_tasks, context.work, repos),
            tuple[dict[str, str], list[tuple[str, str]], dict[str, str]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )[0]
        schema_path: Path = context.work / "task-deps.schema.json"
        write_json(schema_path, narrowed_task_deps_schema(list(keys)))
        runner.run(
            AgentStep(
                stage="task-deps",
                agent="task-dependency-mapper",
                inputs=(*task_paths, str(closure_path), str(listing)),
                output=context.work / "candidates/task-deps.json",
                final=final,
                outcome="Cross-Story Task dependencies for the supplied Stories.",
                validate=schema_path,
                add_dirs=(context.work,),
            ),
        )
    else:
        write_json(final, empty_task_deps())
        store.accept("task-deps", task_paths, (final,))
    accepted: dict[str, JsonValue] = read(final)
    try:
        parse_task_deps(accepted)
    except TaskDepsError as exc:
        raise tools.failure(stage, OTHER_CAUSE, {"taskDeps": str(final), "error": str(exc)}) from exc

    dispatch: DispatchArguments = dispatch_arguments()

    def write_edges() -> dict[str, JsonValue]:
        repo: Path = Path(check_type(context.args[dispatch.KEY_BEADS_REPO_PATH], str))
        graph: beadgraph.Graph = tools.portfolio(stage, beadgraph.load, repo)
        writer: beadgraph.Writer = tools.portfolio(stage, beadgraph.Writer, repo)
        return json_object(
            tools.portfolio(
                stage,
                beadwrite.write_all_task_edges,
                graph,
                writer,
                context.bead,
                context.work,
                repos,
                also=[],
            ),
        )

    written: dict[str, JsonValue] = tools.operation(stage, write_edges)
    write_json(context.work / "task-edges/all.json", written)
    if written.get("ok") is False:
        raise tools.failure(stage, OTHER_CAUSE, written)
    return {
        "ok": True,
        "closureEdges": closure,
        "crossStoryDependencies": accepted,
        "written": written,
    }
