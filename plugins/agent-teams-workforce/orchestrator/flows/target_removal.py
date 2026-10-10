"""Publish terminal target removal under the shared architecture writer lock."""

from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.handback import failure_for
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tool_locks import LockTimeoutError, control_repo, file_lock, seconds
from orchestrator.core.tools import Tools


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def remove(context: RunContext, tools: Tools) -> dict[str, JsonValue]:
    """Remove the completed target, retaining diagnostics for expected failures.

    Returns:
        The removal result, including structured evidence for an item failure.

    Raises:
        StepError: A systemic defect prevents safe continuation.

    """
    stage = "target-removal"
    latest: dict[str, JsonValue] = {"removed": False, "commit": None}

    def attempt() -> dict[str, JsonValue]:
        try:
            with file_lock(
                control_repo() / "ops/sdlc-automation/state/arch-integrate.lock",
                seconds("ATW_ARCH_LOCK_WAIT", 120),
            ):
                return _remove_locked(context, tools, latest)
        except LockTimeoutError as exc:
            raise StepError(stage, "contention", (str(exc),)) from exc

    try:
        return tools.operation(stage, attempt)
    except StepError as exc:
        failure = failure_for(stage, exc, agent_started=False)
        if failure.get("classification") in {"setup", "pipeline-code-defect"}:
            raise
        return json_object({
            **latest,
            "ok": False,
            "reason": str(exc),
            "cause": exc.cause,
            "evidence": list(exc.evidence),
            "failure": failure,
        })


def _remove_locked(context: RunContext, tools: Tools, latest: dict[str, JsonValue]) -> dict[str, JsonValue]:
    stage = "target-removal"
    arch = Path(check_type(context.args["archPath"], str))
    result = json_object(
        tools.portfolio(
            "archstate",
            "remove_target",
            str(arch),
            check_type(context.args["targetDir"], str),
            message="docs(architecture): remove target after Specs and Tasks are written",
            execution_id=context.run_id,
            stage=stage,
        ),
    )
    latest.update(result)
    if not result.get("ok") and result.get("subcommand"):
        lock = tools.command(
            ["git", "rev-parse", "--git-path", "index.lock"],
            cwd=arch,
            stage=stage,
        )
        if (arch / lock.stdout.strip()).exists():
            raise tools.failure(stage, "contention", result)
    if result.get("ok"):
        tools.git(arch, ["push", "origin", "main"], stage=stage)
    refusals = check_type(
        result.get("refusals", []),
        list[str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    return {**result, "reason": "; ".join(refusals)}
