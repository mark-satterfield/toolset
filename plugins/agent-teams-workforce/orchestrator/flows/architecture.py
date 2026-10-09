"""Architecture phase: survey, bounded approval, canonical integration and Closure."""

from __future__ import annotations

import os
from pathlib import Path

from ..core.agents import AgentRunner
from ..core.artifacts import ArtifactStore
from ..core.matrix import snapshot
from ..core.models import RunContext, StepError
from ..core.tools import Tools
from .architecture_closure import closure
from .architecture_integration import integrate
from .architecture_resume import (
    approved,
    completed,
    refresh_closure,
    save_approval,
    save_completion,
)
from .architecture_rounds import owner_actions, run_rounds
from .architecture_support import Architecture
from .architecture_survey import prepare_survey


def run(
    context: RunContext,
    store: ArtifactStore,
    runner: AgentRunner,
    tools: Tools,
    *,
    matrix_path: Path | None = None,
) -> dict:
    arch = context.args.get("archPath") or os.environ.get("ATW_ARCH_PATH")
    if not arch:
        return {
            "ok": False,
            "stage": "no-arch-path",
            "requiredHumanActions": ["Set ATW_ARCH_PATH to the architecture root."],
        }
    context.args["archPath"] = arch
    if not context.bead or not context.args.get("prd", {}).get("path"):
        raise StepError(
            "input", "other", ("Architecture requires an Epic and a PRD path.",)
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
        decision, target = checkpoint["decision"], checkpoint["target"]
    else:
        prepare_survey(flow)
        decision = run_rounds(flow)
        actions = owner_actions(decision, flow.work / "decision.json")
        if actions:
            return {
                "ok": False,
                "stage": "owner-concern",
                "requiredHumanActions": actions,
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
