"""Cross-Story dependency acceptance and deterministic edge writes."""

from __future__ import annotations

from pathlib import Path

from ..core.io import write_json
from ..core.models import AgentStep
from .architecture_support import read


def run(context, store, runner, tools, repos):
    context.stage = "task-edges"
    runner.emit("phase", phase="task-edges", step="closure-edges")
    closure = tools.portfolio(
        "beadwrite", "closure_task_edges", context.work, repos, stage="task-edges"
    )
    closure_path = context.work / "closure-edges.json"
    write_json(closure_path, closure)
    if (
        closure.get("ok") is False
        or closure.get("warnings")
        or closure.get("summary", {}).get("warnings")
    ):
        raise tools.failure("task-edges", "other", closure)
    slugs = tools.portfolio("beadwrite", "repo_slugs", repos, stage="task-edges")
    task_paths = tuple(
        str(context.work / f"tasks-{slug}.json") for slug in slugs.values()
    )
    listing = context.work / "task-deps-inputs.json"
    rows = []
    for index, slug in enumerate(slugs.values(), 1):
        doc = read(context.work / f"tasks-{slug}.json")
        rows.append(
            {
                "story": f"S{index}",
                "tasks": [
                    {k: t.get(k) for k in ("key", "title", "dependsOn")}
                    for t in doc.get("tasks", [])
                ],
                "edges": doc.get("edges", []),
            }
        )
    write_json(listing, {"stories": rows, "closureEdgesPath": str(closure_path)})
    final = context.work / "task-deps.json"
    if len(repos) >= 2:
        schema = read(
            runner.plugin / "skills/artifact-handoff/schemas/task-deps.schema.json"
        )
        keys = tools.portfolio(
            "beadwrite", "_span_tasks", context.work, repos, stage="task-edges"
        )[0]
        for field in ("from", "to"):
            schema["properties"]["edges"]["items"]["properties"][field]["enum"] = list(
                keys
            )
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
            )
        )
    else:
        write_json(final, {"edges": [], "acyclic": True, "cycle": []})
        store.accept("task-deps", task_paths, (final,))

    def write_edges():
        repo = Path(context.args["beadsRepoPath"])
        graph = tools.portfolio("beadgraph", "load", repo, stage="task-edges")
        writer = tools.portfolio("beadgraph", "Writer", repo, stage="task-edges")
        return tools.portfolio(
            "beadwrite",
            "write_all_task_edges",
            graph,
            writer,
            context.bead,
            context.work,
            repos,
            [],
            stage="task-edges",
        )

    written = tools.operation("task-edges", write_edges)
    write_json(context.work / "task-edges/all.json", written)
    if written.get("ok") is False:
        raise tools.failure("task-edges", "other", written)
    return {
        "ok": True,
        "closureEdges": closure,
        "crossStoryDependencies": read(final),
        "written": written,
    }
