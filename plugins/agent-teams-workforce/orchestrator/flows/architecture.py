"""Architecture phase: survey, bounded approval, canonical integration and Closure."""

from __future__ import annotations

import os
from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
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
from orchestrator.flows.architecture_support import Architecture
from orchestrator.flows.architecture_survey import prepare_survey


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

    """
    arch = context.args.get("archPath") or os.environ.get("ATW_ARCH_PATH")
    if not arch:
        return {
            "ok": False,
            "stage": "no-arch-path",
            "requiredHumanActions": ["Set ATW_ARCH_PATH to the architecture root."],
        }
    context.args["archPath"] = arch
    stage = "input"
    if not context.bead or not json_object(context.args.get("prd", {})).get("path"):
        raise StepError(
            stage,
            "other",
            ("Architecture requires an Epic and a PRD path.",),
        )
    context.stage = "architecture"
    runner.emit("phase", phase="architecture", step="survey")
    matrix_path = matrix_path or snapshot(context, tools)
    flow = Architecture(context, store, runner, tools, matrix_path)
    saved = completed(flow)
    if saved is not None:
        return refresh_closure(flow, saved)
    checkpoint = approved(flow)
    if checkpoint is not None:
        decision, target = json_object(checkpoint["decision"]), json_object(checkpoint["target"])
    else:
        prepare_survey(flow)
        decision = run_rounds(flow)
        actions = owner_actions(decision, flow.work / "decision.json")
        if actions:
            return {
                "ok": False,
                "stage": "owner-concern",
                "requiredHumanActions": list(actions),
            }
        target = flow.checked(flow.target(), "target")
        save_approval(flow, target, decision)
    update = integrate(flow, target)
    result = closure(flow, target)
    result = {
        "ok": True,
        "subject": flow.subject,
        "subjectName": target.get("subjectName", flow.subject),
        "targetDir": target["targetDir"],
        "deltaDir": target["deltaDir"],
        "architectureChange": target["architectureChange"],
        "closure": result,
        "targetPath": str(flow.work / "target.json"),
        "surveyPath": str(flow.work / "survey.json"),
        "decisionPath": str(flow.work / "decision.json"),
        "architectureUpdate": update,
        "architectureUpdatePath": str(flow.work / "architecture-update.json"),
        "ledgerPath": str(flow.work / "ledger.json"),
        "rounds": decision["round"],
        "openItems": update.get("openItems", {}),
        "noArchitectureChange": target["architectureChange"] == "none",
    }
    return save_completion(flow, result)
