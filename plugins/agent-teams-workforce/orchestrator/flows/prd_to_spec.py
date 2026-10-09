"""Elaborate one ready Epic into architecture, Specs, Stories and scored Tasks."""

from __future__ import annotations

import os
from pathlib import Path

from ..core.agents import AgentRunner
from ..core.artifacts import ArtifactStore, load_artifactio
from ..core.events import EventWriter
from ..core.io import write_json
from ..core.matrix import read_snapshot, snapshot
from ..core.models import RunContext, StepError
from ..core.tools import Tools
from . import architecture, repo_scoping, spec_authoring, task_edges, trd_authoring
from .elaboration_support import (
    done_rule,
    failed,
    lifecycle,
    parallel,
    phase,
    record,
    repository_failure,
)


def run(context: RunContext) -> dict:
    """Own the lifecycle once; every phase owns its own saved-work decision."""
    args = context.args
    if (
        not context.bead
        or not args.get("beadsRepoPath")
        or not Path(args.get("prd", {}).get("path", "")).is_file()
    ):
        raise StepError(
            "input",
            "other",
            ("Epic, beadsRepoPath and readable PRD path are required",),
        )
    context.work.mkdir(parents=True, exist_ok=True)
    args["archPath"] = args.get("archPath") or os.environ.get("ATW_ARCH_PATH", "")
    root = Path(args.get("skillspokeRoot") or os.environ["SKILLSPOKE_ROOT"])
    store = ArtifactStore(
        load_artifactio(), root, context.work, context.bead, context.run_id
    )
    tools = Tools(context.work / "evidence")
    notes = []
    output = EventWriter()

    def emit(event, **facts):
        if event in {"note", "verdict"}:
            notes.append({"event": event, **facts})
        output(event, **facts)

    runner = AgentRunner(context, store, emit=emit)
    phases = {}
    state = {"owner": str(args.get("owner") or context.run_id), "done": False}
    result = {
        "ok": False,
        "stage": "input",
        "lifecycle": state,
        "repoSpan": [],
        "hierarchy": {"epic": args.get("epic", {}), "stories": [], "tasks": []},
        "beadsEmitted": False,
        "artifacts": {
            "dir": str(context.work),
            "epicId": context.bead,
            "phases": phases,
            "filing": {},
        },
        "targetRemoval": {
            "removed": False,
            "commit": None,
            "reason": "elaboration incomplete",
        },
    }

    def release():
        if state.get("claimAttempted") and not state["done"] and "release" not in state:
            try:
                state["release"] = lifecycle(
                    context, tools, "release", owner=state["owner"]
                )
            except Exception as exc:
                state["release"] = failed("release", exc)

    # Registered before claiming: a timeout after the remote claim still releases by token.
    context.cleanup.insert(0, release)
    try:
        context.stage = "epic-lifecycle"
        state["claimAttempted"] = True
        state["start"] = lifecycle(
            context,
            tools,
            "start",
            owner=state["owner"],
            reclaim=bool(args.get("reclaim")),
        )
        if not state["start"].get("ok"):
            state["claimAttempted"] = False
            result.update(
                stage="epic-lifecycle",
                refusal=state["start"].get("refusal"),
                headline="Epic lifecycle refused elaboration",
            )
        else:
            state["owner"] = state["start"]["owner"]
            result.update(
                _elaborate(context, store, runner, tools, phases, state, result)
            )
    except Exception as exc:
        result.update(failed(context.stage, exc))
    finally:
        release()
    result.setdefault(
        "headline",
        "Epic elaboration finished" if result["ok"] else "Epic elaboration incomplete",
    )
    return record(context, result, phases, notes)


def _owner(result):
    actions = result.get("requiredHumanActions")
    if actions:
        return {
            "ok": False,
            "stage": "requires-human-action",
            "requiredHumanActions": actions,
            "headline": "Owner facts are required",
        }
    return result


def _elaborate(context, store, runner, tools, phases, state, result):
    from . import task_decomposition

    # Missing architecture configuration is an owner fact, even if no matrix exists yet.
    matrix = snapshot(context, tools) if context.args.get("archPath") else None
    arch = phase(
        context,
        store,
        runner,
        tools,
        "architecture",
        architecture.run,
        matrix_path=matrix,
    )
    phases["architecture"] = arch
    if not arch.get("ok"):
        return _owner(arch)
    context.args.update(
        {k: arch[k] for k in ("targetDir", "deltaDir", "architectureChange")}
    )
    context.args["architectureSubject"] = arch["subject"]
    context.stage = "architecture"
    delta = tools.portfolio(
        "archstate",
        "delta_items",
        str(Path(arch["targetDir"]) / "delta"),
        matrix_snapshot=read_snapshot(matrix),
        stage="architecture",
    )
    write_json(context.work / "delta-items.json", delta)
    context.args.update(
        {
            "deltaDir": arch["deltaDir"] if delta.get("deltaExists") else "",
            "note": delta.get("note", ""),
        }
    )
    scope, trd = parallel(
        context,
        [
            lambda: phase(
                context,
                store,
                runner,
                tools,
                "repo-scoping",
                repo_scoping.run,
                matrix_path=matrix,
            ),
            lambda: phase(
                context, store, runner, tools, "trd-authoring", trd_authoring.run
            ),
        ],
    )
    phases.update({"repo-scoping": scope, "trd-authoring": trd})
    for value in (scope, trd):
        if not value.get("ok"):
            return _owner(value)
    repos = scope["repos"]
    result.update(repoSpan=repos, createdRepos=scope.get("createdRepos", []))
    context.args["trdPath"] = trd["trdPath"]
    result["artifacts"]["filing"]["trd"] = trd.get("filingPath")
    slugs = tools.portfolio("beadwrite", "repo_slugs", repos, stage="spec-authoring")
    rows = [
        {"repository": repo, "slug": slug, "storyKey": f"S{index}"}
        for index, (repo, slug) in enumerate(slugs.items(), 1)
    ]
    specs = parallel(
        context,
        [
            lambda row=row: phase(
                context,
                store,
                runner,
                tools,
                "spec-authoring",
                spec_authoring.run,
                {
                    "repoPath": row["repository"],
                    "slug": row["slug"],
                    "storyKey": row["storyKey"],
                },
            )
            for row in rows
        ],
    )
    for row, spec in zip(rows, specs, strict=True):
        row["spec"] = spec
    eligible = [row for row in rows if row["spec"].get("ok")]
    decomposed = parallel(
        context,
        [
            lambda row=row: phase(
                context,
                store,
                runner,
                tools,
                "task-decomposition",
                task_decomposition.run,
                {
                    "repoPath": row["repository"],
                    "slug": row["slug"],
                    "story": row["spec"]["story"],
                    "specPaths": row["spec"]["specPaths"],
                    "scopingPath": str(context.work / "repo-scoping.json"),
                    "itemsPath": str(context.work / "delta-items.json"),
                    "uiPath": row["spec"].get("uiPath"),
                    "packagesDir": context.args.get("designSystem", {}).get(
                        "packagesDir"
                    ),
                },
            )
            for row in eligible
        ],
    )
    for row, tasks in zip(eligible, decomposed, strict=True):
        row["tasks"] = tasks
    phases["repositories"] = rows
    result["hierarchy"]["stories"] = [row["spec"]["story"] for row in eligible]
    result["hierarchy"]["tasks"] = [
        task for row in eligible for task in row.get("tasks", {}).get("tasks", [])
    ]
    result["beadsEmitted"] = bool(result["hierarchy"]["stories"])
    complete = not done_rule(rows, True, [])["repositories"]
    edges = {"ok": False}
    if complete:
        try:
            edges = task_edges.run(context, store, runner, tools, repos)
        except Exception as exc:
            edges = failed("task-edges", exc)
    phases["task-edges"] = edges
    result.update(
        {k: edges[k] for k in ("closureEdges", "crossStoryDependencies") if k in edges}
    )
    context.stage = "finish"
    runner.emit("phase", phase="finish", step="task-scores")
    state["finish"] = lifecycle(
        context, tools, "finish", owner=state["owner"], done=False, scope="epic-tasks"
    )
    unscored = state["finish"]["score"]["unscored"]
    rule = done_rule(rows, edges.get("ok", False), unscored)
    phases["done-rule"] = rule
    if not complete:
        return {
            "ok": False,
            "stage": "repositories-incomplete",
            "failure": repository_failure(rows),
        }
    if not edges.get("ok"):
        return edges
    if not rule["done"]:
        return {
            "ok": False,
            "stage": "task-scores",
            "failure": {
                "stage": "task-scores",
                "cause": "other",
                "repositories": [],
                "unscored": unscored,
            },
        }
    _finish(context, tools, state, result)
    return {
        "ok": True,
        "stage": "finish",
        "headline": "Architecture, Specs, Stories and scored Tasks are ready",
    }


def _finish(context, tools, state, result):
    def story_edges():
        repo = Path(context.args["beadsRepoPath"])
        graph = tools.portfolio("beadgraph", "load", repo, stage="finish")
        writer = tools.portfolio("beadgraph", "Writer", repo, stage="finish")
        return tools.portfolio(
            "storyedges", "story_edges", graph, writer, stage="finish"
        )

    # Lifecycle done is published only after the dependent Story writes succeed.
    result["storyEdges"] = tools.operation("finish", story_edges)
    if result["storyEdges"].get("ok") is False:
        raise tools.failure("finish", "other", result["storyEdges"])
    state["finish"] = lifecycle(
        context, tools, "finish", owner=state["owner"], done=True, scope="epic-tasks"
    )
    state["done"] = state["finish"]["summary"]["done"]
    if not state["done"]:
        raise tools.failure("task-scores", "other", state["finish"])
    from .target_removal import remove

    result["targetRemoval"] = remove(context, tools)
