"""Cross-Story dependency acceptance and deterministic edge writes."""

from __future__ import annotations

from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext
from orchestrator.core.tools import Tools
from orchestrator.flows.architecture_support import read


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

    """
    stage = "task-edges"
    context.stage = "task-edges"
    runner.emit("phase", phase="task-edges", step="closure-edges")
    closure = json_object(
        tools.portfolio(
            "beadwrite",
            "closure_task_edges",
            context.work,
            repos,
            stage="task-edges",
        ),
    )
    closure_path = context.work / "closure-edges.json"
    write_json(closure_path, closure)
    if closure.get("ok") is False or closure.get("warnings") or json_object(closure.get("summary", {})).get("warnings"):
        raise tools.failure(stage, "other", closure)
    slugs = check_type(
        tools.portfolio("beadwrite", "repo_slugs", repos, stage="task-edges"),
        dict[str, str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    task_paths = tuple(str(context.work / f"tasks-{slug}.json") for slug in slugs.values())
    listing = context.work / "task-deps-inputs.json"
    rows = []
    for index, slug in enumerate(slugs.values(), 1):
        doc = read(context.work / f"tasks-{slug}.json")
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
    final = context.work / "task-deps.json"
    if len(repos) > 1:
        schema = read(
            runner.plugin / "skills/artifact-handoff/schemas/task-deps.schema.json",
        )
        keys = check_type(
            tools.portfolio(
                "beadwrite",
                "_span_tasks",
                context.work,
                repos,
                stage="task-edges",
            ),
            tuple[dict[str, str], list[tuple[str, str]], dict[str, str]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )[0]
        for field in ("from", "to"):
            properties = json_object(
                json_object(json_object(json_object(schema["properties"])["edges"])["items"])["properties"],
            )
            json_object(properties[field])["enum"] = list(keys)
        schema_path = context.work / "task-deps.schema.json"
        write_json(schema_path, schema)
        runner.run(
            AgentStep(
                stage="task-deps",
                agent="task-dependency-mapper",
                inputs=(*task_paths, str(closure_path), str(listing)),
                output=context.work / "candidates/task-deps.json",
                final=final,
                outcome="Cross-Story Task dependencies for the supplied Stories.",
                validate=schema_path,
                model="fable",
                effort="medium",
                add_dirs=(context.work,),
            ),
        )
    else:
        write_json(final, {"edges": [], "acyclic": True, "cycle": []})
        store.accept("task-deps", task_paths, (final,))

    def write_edges() -> dict[str, JsonValue]:
        repo = Path(check_type(context.args["beadsRepoPath"], str))
        graph = tools.portfolio("beadgraph", "load", repo, stage="task-edges")
        writer = tools.portfolio("beadgraph", "Writer", repo, stage="task-edges")
        return json_object(
            tools.portfolio(
                "beadwrite",
                "write_all_task_edges",
                graph,
                writer,
                context.bead,
                context.work,
                repos,
                [],
                stage="task-edges",
            ),
        )

    written = tools.operation("task-edges", write_edges)
    write_json(context.work / "task-edges/all.json", written)
    if written.get("ok") is False:
        raise tools.failure(stage, "other", written)
    return {
        "ok": True,
        "closureEdges": closure,
        "crossStoryDependencies": read(final),
        "written": written,
    }
