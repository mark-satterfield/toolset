"""Composite lifecycle, phase views and the deterministic completion rule."""

from __future__ import annotations

import logging
import os
import traceback
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Concatenate, ParamSpec, TypeVar

import beadgraph
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.handback import Failure, failure_for
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import RunContext
from orchestrator.core.tools import Tools

_ARGUMENT_ERROR: str = "Arguments violate the elaboration_support input contract"


_LOGGER = logging.getLogger(__name__)


P = ParamSpec("P")
R = TypeVar("R")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def failed(stage: str, exc: Exception, repository: str = "", *, agent_started: bool = False) -> dict[str, JsonValue]:
    """Preserve and classify a failed phase before another session can start.

    Returns:
        The phase result with the complete original diagnostic.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(stage, str))
        or not (isinstance(exc, Exception))
        or not (isinstance(repository, str))
        or not (isinstance(agent_started, bool))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    failure: Failure = failure_for(stage, exc, agent_started=agent_started)
    if failure.get("classification") in {"setup", "pipeline-code-defect"}:
        marker: str | None = os.environ.get("ATW_STOP_FILE")
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
        function: Callable[Concatenate[RunContext, ArtifactStore, AgentRunner, Tools, P], dict[str, JsonValue]],
        additions: dict[str, JsonValue] | None = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> dict[str, JsonValue]:
        """Execute one phase with shared cleanup and private stage/arguments.

        Returns:
            The successful phase result or its classified failure.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if (
            not (isinstance(name, str))
            or not (callable(function))
            or not (isinstance(additions, dict) or additions is None)
        ):
            raise TypeError(_ARGUMENT_ERROR)
        local: RunContext = replace(self.context, stage=name, args={**self.context.args, **(additions or {})})
        child: AgentRunner = AgentRunner(
            local,
            self.store,
            plugin=self.runner.plugin,
            emit=self.runner.emit,
            executable=self.runner.executable,
        )
        child.share_processes(self.runner)
        self.runner.emit("phase", phase=name, step=name, repository=local.args.get("repoPath"))
        try:
            result: dict[str, JsonValue] = function(local, self.store, child, self.tools, *args, **kwargs)
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
        TypeError: An argument violates the declared input contract.
        InterruptedError: The owner sent a termination signal.
        KeyboardInterrupt: The owner interrupted the process.
        SystemExit: The process requested immediate termination.

    """
    cleanup: Callable[[], None]
    if not (isinstance(context, RunContext)) or not (isinstance(jobs, list)):
        raise TypeError(_ARGUMENT_ERROR)

    def invoke(job: Callable[[], T]) -> T:
        try:
            return job()
        except Exception as exc:
            failure: Failure = failure_for(context.stage, exc, agent_started=bool(context.sessions))
            if failure["classification"] in {"setup", "pipeline-code-defect"}:
                marker: str | None = os.environ.get("ATW_STOP_FILE")
                if marker:
                    try:
                        Path(marker).touch(mode=0o600)
                    except OSError as marker_error:
                        exc.add_note(f"Stop marker also failed: {marker_error}")
            raise

    pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max(1, len(jobs)))
    try:
        futures: list[Future[T]] = [pool.submit(invoke, job) for job in jobs]
        return _parallel_results(context, futures)
    except InterruptedError, KeyboardInterrupt, SystemExit:
        for cleanup in reversed(context.cleanup):
            cleanup()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def _parallel_results[T](context: RunContext, futures: list[Future[T]]) -> list[T]:
    error: BaseException | None
    wait(futures)
    errors: list[BaseException] = []
    future: Future[T]
    for future in futures:
        error = future.exception()
        if error is not None:
            errors.append(error)
    if errors:
        dominant: BaseException = max(
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
def lifecycle(  # ruff: ignore[non-pep695-generic-function] - Typeguard requires runtime ParamSpec identity on Python 3.14.
    context: RunContext,
    tools: Tools,
    stage: str,
    operation: Callable[Concatenate[beadgraph.Graph, beadgraph.Writer, str, P], R],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """Apply one tracker lifecycle operation through the deterministic boundary.

    Returns:
        The validated portfolio operation result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(context, RunContext))
        or not (isinstance(tools, Tools))
        or not (isinstance(stage, str))
        or not (callable(operation))
    ):
        raise TypeError(_ARGUMENT_ERROR)

    def attempt() -> R:
        repo: Path = Path(check_type(context.args["beadsRepoPath"], str))
        graph: beadgraph.Graph = tools.portfolio(stage, beadgraph.load, repo, with_description=True)
        writer: beadgraph.Writer = tools.portfolio(stage, beadgraph.Writer, repo)
        return tools.portfolio(stage, operation, graph, writer, context.bead, *args, **kwargs)

    return tools.operation(stage, attempt)


def _repository_gap(row: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    spec: dict[str, JsonValue] = json_object(row.get("spec", {}))
    tasks: dict[str, JsonValue] = json_object(row.get("tasks", {}))
    story: dict[str, JsonValue] = json_object(spec.get("story", {}))
    if not spec.get("ok") or not story.get("id"):
        return {"repository": row["repository"], "reason": "missing Story", "result": spec}
    task_rows: list[dict[str, JsonValue]] = check_type(
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    row: dict[str, JsonValue]
    if not (isinstance(repositories, list)) or not (isinstance(edges_ok, bool)) or not (isinstance(unscored, list)):
        raise TypeError(_ARGUMENT_ERROR)
    gaps: list[JsonValue] = []
    if not repositories:
        gaps.append({"repository": "", "reason": "empty repository span"})
    for row in repositories:
        gap: dict[str, JsonValue] | None = _repository_gap(row)
        if gap is not None:
            gaps.append(gap)
    return {
        "done": not gaps and edges_ok and not unscored,
        "repositories": gaps,
        "edgesWritten": edges_ok,
        "unscored": unscored,
    }


def _repository_failures(rows: list[dict[str, JsonValue]]) -> tuple[list[dict[str, JsonValue]], list[float]]:
    row: dict[str, JsonValue]
    value: dict[str, JsonValue]
    field: str | str
    failures: list[dict[str, JsonValue]] = []
    resets: list[float] = []
    for row in rows:
        for value in (json_object(row.get("spec", {})), json_object(row.get("tasks", {}))):
            if not value or value.get("ok"):
                continue
            fact: dict[str, JsonValue] = json_object(value.get("failure", {}))
            reset: int | float | str | list[JsonValue] | dict[str, JsonValue] | None = fact.get("resumeAt")
            if reset is not None:
                resets.append(check_type(reset, float))
            failure: dict[str, int | float | str | list[JsonValue] | dict[str, JsonValue] | None] = {
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    failures: list[dict[str, JsonValue]]
    resets: list[float]
    if not (isinstance(rows, list)):
        raise TypeError(_ARGUMENT_ERROR)
    failures, resets = _repository_failures(rows)
    causes: set[str] = {check_type(row["cause"], str) for row in failures}
    transient: set[str] = {"quota", "api", "bd-timeout", "contention"}
    cause: str = (
        next((value for value in ("quota", "api", "bd-timeout", "contention") if value in causes), "other")
        if causes and causes <= transient
        else "other"
    )
    result: dict[str, JsonValue] = json_object({
        "stage": "repositories-incomplete",
        "cause": cause,
        "repositories": failures,
    })
    fatal: dict[str, JsonValue] | None = next(
        (row for row in failures if row.get("classification") in {"setup", "pipeline-code-defect"}),
        None,
    )
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(context, RunContext))
        or not (isinstance(result, dict))
        or not (isinstance(phases, dict))
        or not (isinstance(notes, list))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    path: Path = context.work / "run.json"
    result.update(json_object({"beadId": context.bead, "detailPath": str(path), "sessions": context.sessions}))
    prd: dict[str, JsonValue] = json_object(context.args.get("prd", {}))
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
