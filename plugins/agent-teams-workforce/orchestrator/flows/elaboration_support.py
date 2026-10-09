"""Composite lifecycle, phase views and the deterministic completion rule."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..core.agents import AgentRunner
from ..core.io import write_json
from ..core.models import RunContext, StepError
from ..core.tools import Tools


def failed(stage: str, exc: Exception, repository: str = "") -> dict:
    failure = {"stage": stage, "cause": "other", "repositories": []}
    if isinstance(exc, StepError):
        failure.update(stage=exc.stage, cause=exc.cause, evidence=list(exc.evidence))
        if exc.resume_at is not None:
            failure["resumeAt"] = exc.resume_at
    return {
        "ok": False,
        "stage": stage,
        "headline": str(exc),
        "repository": repository,
        "failure": failure,
    }


def phase(context, store, runner, tools, name, function, additions=None, **kwargs):
    # Mutable stage/args belong to the phase, while manifest, cleanup and cap are run-wide.
    local = replace(context, stage=name, args={**context.args, **(additions or {})})
    child = AgentRunner(
        local,
        store,
        plugin=runner.plugin,
        emit=runner.emit,
        executable=runner.executable,
    )
    child.processes = runner.processes
    child._lock = runner._lock
    runner.emit("phase", phase=name, step=name, repository=local.args.get("repoPath"))
    try:
        result = function(local, store, child, tools, **kwargs)
        if result.get("resumed"):
            runner.emit(
                "note", kind="reused", phase=name, repository=local.args.get("repoPath")
            )
        return result
    except Exception as exc:
        return failed(local.stage, exc, str(local.args.get("repoPath", "")))


def parallel(context: RunContext, jobs: list) -> list:
    """Join all results; terminate live groups before joining on interruption."""
    pool = ThreadPoolExecutor(max_workers=max(1, len(jobs)))
    try:
        futures = [pool.submit(job) for job in jobs]
        return [future.result() for future in futures]
    except BaseException:
        for cleanup in reversed(context.cleanup):
            cleanup()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def lifecycle(context: RunContext, tools: Tools, operation: str, **kwargs: Any) -> dict:
    def attempt():
        repo = Path(context.args["beadsRepoPath"])
        graph = tools.portfolio(
            "beadgraph", "load", repo, with_description=True, stage=operation
        )
        writer = tools.portfolio("beadgraph", "Writer", repo, stage=operation)
        return tools.portfolio(
            "elaboration",
            operation,
            graph,
            writer,
            context.bead,
            stage=operation,
            **kwargs,
        )

    return tools.operation(operation, attempt)


def done_rule(repositories: list[dict], edges_ok: bool, unscored: list) -> dict:
    """Every repository needs a persisted Story, Tasks and full placed-item coverage."""
    gaps = []
    if not repositories:
        gaps.append({"repository": "", "reason": "empty repository span"})
    for row in repositories:
        spec, tasks = row.get("spec", {}), row.get("tasks", {})
        if not spec.get("ok") or not spec.get("story", {}).get("id"):
            gaps.append(
                {
                    "repository": row["repository"],
                    "reason": "missing Story",
                    "result": spec,
                }
            )
        elif (
            not tasks.get("ok")
            or not tasks.get("tasks")
            or any(not t.get("id") for t in tasks["tasks"])
        ):
            gaps.append(
                {
                    "repository": row["repository"],
                    "reason": "missing Tasks",
                    "result": tasks,
                }
            )
        elif tasks.get("coverage", {}).get("uncitedAfter"):
            gaps.append(
                {
                    "repository": row["repository"],
                    "reason": "uncited items",
                    "result": tasks,
                }
            )
    return {
        "done": not gaps and edges_ok and not unscored,
        "repositories": gaps,
        "edgesWritten": edges_ok,
        "unscored": unscored,
    }


def repository_failure(rows: list[dict]) -> dict:
    failures = []
    resets = []
    for row in rows:
        for value in (row.get("spec", {}), row.get("tasks", {})):
            if value and not value.get("ok"):
                fact = value.get("failure", {})
                if fact.get("resumeAt") is not None:
                    resets.append(fact["resumeAt"])
                failures.append(
                    {
                        "repository": row["repository"],
                        "stage": fact.get(
                            "stage", value.get("stage", "repositories-incomplete")
                        ),
                        "cause": fact.get("cause", "other"),
                        "headline": value.get("headline", "incomplete repository"),
                    }
                )
    causes = {row["cause"] for row in failures}
    cause = (
        next(
            (c for c in ("quota", "api", "bd-timeout", "contention") if c in causes),
            "other",
        )
        if causes and causes <= {"quota", "api", "bd-timeout", "contention"}
        else "other"
    )
    return {
        "stage": "repositories-incomplete",
        "cause": cause,
        "repositories": failures,
        **({"resumeAt": max(resets)} if resets and cause == "quota" else {}),
    }


def record(context: RunContext, result: dict, phases: dict, notes: list) -> dict:
    path = context.work / "run.json"
    result.update(beadId=context.bead, detailPath=str(path), sessions=context.sessions)
    write_json(
        path,
        {
            "runId": context.run_id,
            "composite": context.flow,
            "epicId": context.bead,
            "prdId": context.args.get("prd", {}).get("id"),
            "result": result,
            "phases": phases,
            "notes": notes,
            "sessions": context.sessions,
        },
    )
    return result
