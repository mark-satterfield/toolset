"""Composite lifecycle, phase views and the deterministic completion rule."""

from __future__ import annotations

import logging
import os
import traceback
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.handback import failure_for
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import RunContext
from orchestrator.core.tools import Tools

_LOGGER = logging.getLogger(__name__)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def failed(stage: str, exc: Exception, repository: str = "", *, agent_started: bool = False) -> dict[str, JsonValue]:
    """Preserve and classify a failed phase before another session can start.

    Returns:
        The phase result with the complete original diagnostic.

    """
    failure = failure_for(stage, exc, agent_started=agent_started)
    if failure.get("classification") in {"setup", "pipeline-code-defect"}:
        marker = os.environ.get("ATW_STOP_FILE")
        if marker:
            Path(marker).touch(mode=0o600)
    if failure["cause"] == "shutdown":
        stage = "shutdown"
    return json_object({
        "ok": False,
        "stage": stage,
        "headline": str(exc),
        "repository": repository,
        "failure": failure,
    })


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass
class PhaseRunner:
    """Bind one run's services while giving each phase independent mutable inputs."""

    context: RunContext
    store: ArtifactStore
    runner: AgentRunner
    tools: Tools

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructor field, including collection members."""
        check_type(self.context, RunContext, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.store, ArtifactStore, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.runner, AgentRunner, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.tools, Tools, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)

    def call(
        self,
        name: str,
        function: Callable[..., dict[str, JsonValue]],
        additions: dict[str, JsonValue] | None = None,
        **kwargs: object,
    ) -> dict[str, JsonValue]:
        """Execute one phase with shared cleanup and private stage/arguments.

        Returns:
            The successful phase result or its classified failure.

        """
        local = replace(self.context, stage=name, args={**self.context.args, **(additions or {})})
        child = AgentRunner(
            local,
            self.store,
            plugin=self.runner.plugin,
            emit=self.runner.emit,
            executable=self.runner.executable,
        )
        child.share_processes(self.runner)
        self.runner.emit("phase", phase=name, step=name, repository=local.args.get("repoPath"))
        try:
            result = function(local, self.store, child, self.tools, **kwargs)
            if result.get("resumed"):
                self.runner.emit("note", kind="reused", phase=name, repository=local.args.get("repoPath"))
        except Exception as exc:
            _LOGGER.exception("Phase %s failed", name)
            return failed(
                local.stage,
                exc,
                str(local.args.get("repoPath", "")),
                agent_started=any(row.get("startedAt") is not None for row in local.sessions),
            )
        else:
            return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parallel[T](context: RunContext, jobs: list[Callable[[], T]]) -> list[T]:
    """Join phase results and terminate live groups only on interruption.

    Returns:
        Job results in the original submission order.

    Raises:
        InterruptedError: The owner sent a termination signal.
        KeyboardInterrupt: The owner interrupted the process.
        SystemExit: The process requested immediate termination.

    """

    def invoke(job: Callable[[], T]) -> T:
        try:
            return job()
        except Exception as exc:
            failure = failure_for(context.stage, exc, agent_started=bool(context.sessions))
            if failure["classification"] in {"setup", "pipeline-code-defect"}:
                marker = os.environ.get("ATW_STOP_FILE")
                if marker:
                    try:
                        Path(marker).touch(mode=0o600)
                    except OSError as marker_error:
                        exc.add_note(f"Stop marker also failed: {marker_error}")
            raise

    pool = ThreadPoolExecutor(max_workers=max(1, len(jobs)))
    try:
        futures = [pool.submit(invoke, job) for job in jobs]
        return _parallel_results(context, futures)
    except InterruptedError, KeyboardInterrupt, SystemExit:
        for cleanup in reversed(context.cleanup):
            cleanup()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def _parallel_results[T](context: RunContext, futures: list[Future[T]]) -> list[T]:
    wait(futures)
    errors = [error for future in futures if (error := future.exception()) is not None]
    if errors:
        dominant = max(
            errors,
            key=lambda error: {"item": 0, "transient": 1, "setup": 2, "pipeline-code-defect": 3}[
                failure_for(context.stage, error, agent_started=bool(context.sessions))["classification"]
            ],
        )
        for error in errors:
            if error is not dominant:
                dominant.add_note("Concurrent phase failure:\n" + "".join(traceback.format_exception(error)))
        raise dominant
    return [future.result() for future in futures]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def lifecycle(context: RunContext, tools: Tools, operation: str, **kwargs: object) -> dict[str, JsonValue]:
    """Apply one tracker lifecycle operation through the deterministic boundary.

    Returns:
        The validated portfolio operation result.

    """

    def attempt() -> dict[str, JsonValue]:
        repo = Path(check_type(context.args["beadsRepoPath"], str))
        graph = tools.portfolio("beadgraph", "load", repo, with_description=True, stage=operation)
        writer = tools.portfolio("beadgraph", "Writer", repo, stage=operation)
        return json_object(
            tools.portfolio("elaboration", operation, graph, writer, context.bead, stage=operation, **kwargs),
        )

    return tools.operation(operation, attempt)


def _repository_gap(row: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    spec = json_object(row.get("spec", {}))
    tasks = json_object(row.get("tasks", {}))
    story = json_object(spec.get("story", {}))
    if not spec.get("ok") or not story.get("id"):
        return {"repository": row["repository"], "reason": "missing Story", "result": spec}
    task_rows = check_type(
        tasks.get("tasks", []),
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    if not tasks.get("ok") or not task_rows or any(not task.get("id") for task in task_rows):
        return {"repository": row["repository"], "reason": "missing Tasks", "result": tasks}
    if json_object(tasks.get("coverage", {})).get("uncitedAfter"):
        return {"repository": row["repository"], "reason": "uncited items", "result": tasks}
    return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def done_rule(
    repositories: list[dict[str, JsonValue]],
    edges_ok: bool,
    unscored: list[JsonValue],
) -> dict[str, JsonValue]:
    """Require a Story, Tasks and complete placed-item coverage for every repository.

    Returns:
        Completion status and the exact unmet requirements.

    """
    gaps: list[JsonValue] = []
    if not repositories:
        gaps.append({"repository": "", "reason": "empty repository span"})
    for row in repositories:
        gap = _repository_gap(row)
        if gap is not None:
            gaps.append(gap)
    return {
        "done": not gaps and edges_ok and not unscored,
        "repositories": gaps,
        "edgesWritten": edges_ok,
        "unscored": unscored,
    }


def _repository_failures(rows: list[dict[str, JsonValue]]) -> tuple[list[dict[str, JsonValue]], list[float]]:
    failures: list[dict[str, JsonValue]] = []
    resets: list[float] = []
    for row in rows:
        for value in (json_object(row.get("spec", {})), json_object(row.get("tasks", {}))):
            if not value or value.get("ok"):
                continue
            fact = json_object(value.get("failure", {}))
            reset = fact.get("resumeAt")
            if reset is not None:
                resets.append(check_type(reset, float))
            failure = {
                "repository": row["repository"],
                "stage": fact.get("stage", value.get("stage", "repositories-incomplete")),
                "cause": fact.get("cause", "other"),
                "headline": value.get("headline", "incomplete repository"),
            }
            for field in ("classification", "diagnostic"):
                if field in fact:
                    failure[field] = fact[field]
            failures.append(failure)
    return failures, resets


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_failure(rows: list[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    """Combine repository failures without losing a systemic failure's diagnostic.

    Returns:
        Repository evidence, dominant cause and any fatal diagnostic.

    """
    failures, resets = _repository_failures(rows)
    causes = {check_type(row["cause"], str) for row in failures}
    transient = {"quota", "api", "bd-timeout", "contention"}
    cause = (
        next((value for value in ("quota", "api", "bd-timeout", "contention") if value in causes), "other")
        if causes and causes <= transient
        else "other"
    )
    result = json_object({"stage": "repositories-incomplete", "cause": cause, "repositories": failures})
    fatal = next((row for row in failures if row.get("classification") in {"setup", "pipeline-code-defect"}), None)
    if fatal is not None:
        result.update(classification=fatal["classification"], diagnostic=fatal["diagnostic"])
    if resets and cause == "quota":
        result["resumeAt"] = max(resets)
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record(
    context: RunContext,
    result: dict[str, JsonValue],
    phases: dict[str, JsonValue],
    notes: list[JsonValue],
) -> dict[str, JsonValue]:
    """Persist detailed run evidence separately from the compact wire handback.

    Returns:
        The result with its saved detail path and session manifest.

    """
    path = context.work / "run.json"
    result.update(json_object({"beadId": context.bead, "detailPath": str(path), "sessions": context.sessions}))
    prd = json_object(context.args.get("prd", {}))
    write_json(
        path,
        {
            "runId": context.run_id,
            "composite": context.flow,
            "epicId": context.bead,
            "prdId": prd.get("id"),
            "result": result,
            "phases": phases,
            "notes": notes,
            "sessions": context.sessions,
        },
    )
    return result
