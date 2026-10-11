"""Publish terminal target removal under the shared architecture writer lock."""

from pathlib import Path
from typing import TYPE_CHECKING, TypeIs

import archstate
from contracts import GitFailure
from target_contract import KEY_TARGET_DIR
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from orchestrator.core.driver_contracts import DispatchArgumentsContract, dispatch_arguments
from orchestrator.core.handback import failure_for
from orchestrator.core.handback_contract import CONTENTION_CAUSE, FATAL_CLASSES, Failure
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tool_locks import LockTimeoutError, control_repo, file_lock, seconds
from orchestrator.core.tools import Tools

if TYPE_CHECKING:
    from contracts import Refusal, TargetRemoval

    from orchestrator.core.tools import CommandResult


def _git_failure(removal: TargetRemoval | Refusal | GitFailure) -> TypeIs[GitFailure]:
    """Narrow a removal result to the Git failure archgit.git_result returns.

    Returns:
        Whether the result satisfies the GitFailure contract.

    """
    try:
        check_type(removal, GitFailure, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    except TypeCheckError:
        return False
    return True


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def remove(context: RunContext, tools: Tools) -> dict[str, JsonValue]:
    """Remove the completed target, retaining diagnostics for expected failures.

    Returns:
        The removal result, including structured evidence for an item failure.

    Raises:
        StepError: A systemic defect prevents safe continuation.
        TypeError: The context or tools have an invalid type.

    """
    if not isinstance(context, RunContext) or not isinstance(tools, Tools):
        message: str = "Target removal requires a run context and tool boundary"
        raise TypeError(message)
    stage: str = "target-removal"
    latest: dict[str, JsonValue] = {"removed": False, "commit": None}

    def attempt() -> dict[str, JsonValue]:
        try:
            with file_lock(
                control_repo() / "ops/sdlc-automation/state/arch-integrate.lock",
                seconds("ATW_ARCH_LOCK_WAIT", 120),
            ):
                return _remove_locked(context, tools, latest)
        except LockTimeoutError as exc:
            raise StepError(stage, CONTENTION_CAUSE, (str(exc),)) from exc

    try:
        return tools.operation(stage, attempt)
    except StepError as exc:
        failure: Failure = failure_for(stage, exc, agent_started=False)
        if failure["classification"] in FATAL_CLASSES:
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
    stage: str = "target-removal"
    dispatch: DispatchArgumentsContract = dispatch_arguments()
    arch: Path = Path(check_type(context.args[dispatch.KEY_ARCH_PATH], str))
    removal: TargetRemoval | Refusal | GitFailure = tools.portfolio(
        stage,
        archstate.remove_target,
        str(arch),
        check_type(context.args[KEY_TARGET_DIR], str),
        message="docs(architecture): remove target after Specs and Tasks are written",
        execution_id=context.run_id,
    )
    result: dict[str, JsonValue] = json_object(removal)
    latest.update(result)
    ok: bool = removal["ok"]
    if not ok and _git_failure(removal) and removal["subcommand"]:
        lock: CommandResult = tools.command(
            ["git", "rev-parse", "--git-path", "index.lock"],
            cwd=arch,
            stage=stage,
        )
        if (arch / lock.stdout.strip()).exists():
            raise tools.failure(stage, CONTENTION_CAUSE, result)
    if ok:
        tools.git(arch, ["push", "origin", "main"], stage=stage)
    refusals: list[str] = removal["refusals"]
    return {**result, "reason": "; ".join(refusals)}
