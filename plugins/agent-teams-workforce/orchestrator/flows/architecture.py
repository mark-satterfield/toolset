"""Architecture phase: survey, bounded approval, canonical integration and Closure."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The driver surface and the target report are each defined once, in a plugin skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from driver_surface_types import ARCH_PATH_ENV
from target_contract import (
    CHANGE_NONE,
    KEY_ARCHITECTURE_CHANGE,
    KEY_DELTA_DIR,
    KEY_OK,
    KEY_SUBJECT,
    KEY_SUBJECT_NAME,
    KEY_TARGET_DIR,
    TargetResult,
    validate_target_report,
)
from typeguard import CollectionCheckStrategy, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE, phase_event
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.matrix import snapshot
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tools import Tools
from orchestrator.flows.architecture_closure import closure
from orchestrator.flows.architecture_integration import integrate
from orchestrator.flows.architecture_resume import (
    approved,
    completed,
    refresh_closure,
    save_approval,
    save_completion,
)
from orchestrator.flows.architecture_rounds import owner_actions, run_rounds
from orchestrator.flows.architecture_support import ARCHITECTURE_PHASE, Architecture
from orchestrator.flows.architecture_survey import prepare_survey
from orchestrator.flows.elaboration_support import emit_event


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run(
    context: RunContext,
    store: ArtifactStore,
    runner: AgentRunner,
    tools: Tools,
    *,
    matrix_path: Path | None = None,
) -> dict[str, JsonValue]:
    """Run.

    Returns:
        The validated architecture artifact result.

    Raises:
        StepError: The required Epic or PRD path is missing.
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(context, RunContext) or not (matrix_path is None or isinstance(matrix_path, Path)):
        argument_error: str = "run: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    dispatch: DispatchArguments = dispatch_arguments()
    arch: JsonValue = context.args.get(dispatch.KEY_ARCH_PATH) or os.environ.get(ARCH_PATH_ENV)
    if not arch:
        return {
            "ok": False,
            "stage": "no-arch-path",
            "requiredHumanActions": [f"Set {ARCH_PATH_ENV} to the architecture root."],
        }
    context.args[dispatch.KEY_ARCH_PATH] = arch
    stage: str = "input"
    if not context.bead or not json_object(context.args.get(dispatch.KEY_PRD, {})).get(dispatch.PRD_PATH):
        raise StepError(
            stage,
            OTHER_CAUSE,
            ("Architecture requires an Epic and a PRD path.",),
        )
    context.stage = ARCHITECTURE_PHASE
    emit_event(runner.emit, phase_event(ARCHITECTURE_PHASE, "survey"))
    snapshot_path: Path = matrix_path or snapshot(context, tools)
    flow: Architecture = Architecture(context, store, runner, tools, snapshot_path)
    saved: dict[str, JsonValue] | None = completed(flow)
    if saved is not None:
        return refresh_closure(flow, saved)
    checkpoint: dict[str, JsonValue] | None = approved(flow)
    decision: dict[str, JsonValue]
    target: dict[str, JsonValue]
    if checkpoint is not None:
        decision = json_object(checkpoint["decision"])
        target = json_object(checkpoint["target"])
    else:
        prepare_survey(flow)
        decision = run_rounds(flow)
        actions: list[str] = owner_actions(decision, flow.work / "decision.json")
        if actions:
            return {
                "ok": False,
                "stage": "owner-concern",
                "requiredHumanActions": list(actions),
            }
        target = flow.checked(flow.target(), "target")
        save_approval(flow, target, decision)
    report: TargetResult = validate_target_report(target)
    update: dict[str, JsonValue] = integrate(flow, report)
    closure_result: dict[str, JsonValue] = closure(flow, target)
    result: dict[str, JsonValue] = {
        KEY_OK: True,
        KEY_SUBJECT: flow.subject,
        KEY_SUBJECT_NAME: report.get(KEY_SUBJECT_NAME, flow.subject),
        KEY_TARGET_DIR: report[KEY_TARGET_DIR],
        KEY_DELTA_DIR: report[KEY_DELTA_DIR],
        KEY_ARCHITECTURE_CHANGE: report[KEY_ARCHITECTURE_CHANGE],
        "closure": closure_result,
        "targetPath": str(flow.work / "target.json"),
        "surveyPath": str(flow.work / "survey.json"),
        "decisionPath": str(flow.work / "decision.json"),
        "architectureUpdate": update,
        "architectureUpdatePath": str(flow.work / "architecture-update.json"),
        "ledgerPath": str(flow.work / "ledger.json"),
        "rounds": decision["round"],
        "openItems": update.get("openItems", {}),
        "noArchitectureChange": report[KEY_ARCHITECTURE_CHANGE] == CHANGE_NONE,
    }
    return save_completion(flow, result)
