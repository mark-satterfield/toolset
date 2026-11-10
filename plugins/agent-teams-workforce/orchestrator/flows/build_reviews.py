"""Regression, reuse and documentation work in the Task's Python journal."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from driver_surface_types import REGRESSION_TIMEOUT_DEFAULT, REGRESSION_TIMEOUT_ENV
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_registry import Registry
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, file_artifact, value_artifact
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import seconds
from orchestrator.flows import build_carried, build_policy
from orchestrator.flows.build_sessions import OutputContract, latest, reasoned
from orchestrator.flows.build_state import (
    ARTIFACT_CONTRACTS,
    CONTRACTS,
    REGRESSION,
    build_rounds,
    regression_rounds,
)
from orchestrator.flows.build_state import (
    artifact_document as _document,
)
from orchestrator.flows.build_state import (
    artifact_file as _file,
)
from orchestrator.flows.build_state import (
    count_in_dispatch as _count,
)
from orchestrator.flows.build_state import (
    new_step as _new,
)
from orchestrator.flows.build_state import (
    workspace_of as _workspace,
)
from orchestrator.flows.elaboration_files import project_root

if TYPE_CHECKING:
    from pathlib import Path

    from step_journal_contract import ValueArtifact


def _regression(run: StepRun, mode: str, plan: Path, extra: list[str]) -> tuple[Path, dict[str, JsonValue]]:
    """Call the existing regression contract checker without a model session.

    Returns:
        Evidence file and its exact result, including failure facts.

    """
    tree: Path = _workspace(run).tree
    folder: Path = run.context.work / "build" / str(run.step["id"])
    output: Path = folder / f"{run.step['id']}-regression-{mode}.json"
    result = run.tools.command(
        [
            sys.executable,
            str(REGRESSION),
            mode,
            "--plan",
            str(plan),
            "--ledger",
            str(tree / ".agent-workforce" / "regression.json"),
            "--output",
            str(output),
            *extra,
        ],
        stage=run.step["script"],
        timeout=seconds(REGRESSION_TIMEOUT_ENV, float(REGRESSION_TIMEOUT_DEFAULT)),
        check=False,
    )
    document: dict[str, JsonValue] = json_object(json.loads(result.stdout))
    return output, document


def _scope(run: StepRun, final: bool) -> Completion:
    """Have the regression specialist assess prior obligations or map their final evidence.

    Returns:
        The actual assessor session, with the shared regression schema.

    """
    name: str = "regressionMapped" if final else "regressionPlan"
    action: str = (
        "Map final test evidence against the approved regression scope"
        if final
        else "Assess cumulative regression scope from existing obligations and the Task's full sources"
    )
    return reasoned(
        run,
        "regression-impact-assessor",
        OutputContract(ARTIFACT_CONTRACTS / "regression-plan.schema.json", name),
        action,
    )


def task_sources(run: StepRun) -> list[str]:
    """Resolve the current Task's source citations to their backing paths.

    Returns:
        Unique absolute paths, without section citations.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    carried: list[str] = list(check_type(bead.get("specPaths", []), list[str]))
    carried.extend(check_type(bead[key], str) for key in ("specPath", "prdPath") if bead.get(key))
    root: Path = project_root()
    return list(dict.fromkeys(str(root / source.split("#", 1)[0]) for source in carried))


def refresh_sources(run: StepRun) -> Completion | None:
    """Reassess downstream evidence when the Task names new governing sources.

    Returns:
        Appended assessment, policy, baseline and review work, or None when covered.

    Raises:
        StepError: A reassessment still omitted the same current source paths.

    """
    sources: list[str] = sorted(task_sources(run))
    covered: list[str] = (
        check_type(_document(run, "regressionPlan")["sourceFiles"], list[str])
        if latest(run, "regressionPlan") is not None
        else []
    )
    missing: list[str] = [source for source in sources if source not in covered]
    if not missing:
        return None
    if latest(run, "regressionSourcesRefresh") == sources:
        raise StepError(
            run.step["script"],
            OTHER_CAUSE,
            ("Reassessed regression scope omitted current Task sources", *missing),
        )
    keys: tuple[str, ...] = (
        "build:regression-reassess",
        "build:regression-review",
        "build:regression-validate",
        "build:execution-policy",
        "build:baseline",
        "build:select-implementers",
    )
    return Completion(
        artifacts=(value_artifact("regressionSourcesRefresh", list(sources)),),
        add=(StepGroup(tuple(_new(key, "Refresh evidence for the Task's current governing sources") for key in keys)),),
    )


def _scope_initial(run: StepRun) -> Completion:
    """Assess regression scope before suite work.

    Returns:
        The assessor's journal children.

    Raises:
        StepError: The operation cannot proceed with the supplied evidence.

    """
    sources: list[str] = list(
        dict.fromkeys(
            task_sources(run)
            + [
                artifact["path"]
                for step in step_journal.steps_in_order(run.journal())
                for artifact in step["artifacts"]
                if artifact["kind"] == "file" and artifact["name"] in {"spec", "criteria", "TRD", "data model"}
            ],
        ),
    )
    plan: Path = run.context.work / "build" / str(run.step["id"]) / "pending-plan.json"
    output, prepared = _regression(
        run,
        "prepare",
        plan,
        [value for source in sources for value in ("--source", source)],
    )
    if prepared.get("ok") is not True:
        errors: list[str] = check_type(prepared.get("errors", []), list[str])
        raise StepError(run.step["script"], OTHER_CAUSE, tuple(errors or ["Regression source preparation failed"]))
    assessed: Completion = _scope(run, False)
    return Completion(artifacts=(*assessed.artifacts, file_artifact("regressionPrevious", output)), add=assessed.add)


def _scope_final(run: StepRun) -> Completion:
    """Map the complete approved scope to the resulting suite.

    Returns:
        The mapper's journal children.

    """
    return _scope(run, True)


def _review(run: StepRun, final: bool) -> Completion:
    """Keep regression review separate from the author that produced its scope or mapping.

    Returns:
        The independent reviewer session.

    """
    name: str = "regressionMappedReview" if final else "regressionPlanReview"
    action: str = (
        "Review the final regression evidence mapping against the approved scope"
        if final
        else "Review cumulative regression source coverage and supersession evidence"
    )
    return reasoned(
        run,
        "regression-coverage-reviewer",
        OutputContract(ARTIFACT_CONTRACTS / "regression-review.schema.json", name),
        action,
    )


def _review_initial(run: StepRun) -> Completion:
    """Review regression scope.

    Returns:
        The reviewer's journal children.

    """
    return _review(run, False)


def _review_final(run: StepRun) -> Completion:
    """Review final evidence mapping.

    Returns:
        The reviewer's journal children.

    """
    return _review(run, True)


def _validate(run: StepRun, final: bool) -> Completion:
    """Validate or verify the exact regression schema, source seal and independent review.

    Returns:
        Required evidence, or bounded scope correction steps.

    Raises:
        StepError: Validation still fails after the permitted correction rounds.

    """
    plan: Path = _file(run, "regressionMapped" if final else "regressionPlan")
    review: Path = _file(run, "regressionMappedReview" if final else "regressionPlanReview")
    extra: list[str] = ["--review", str(review)]
    if final:
        extra.extend(["--approved-plan", str(_file(run, "regressionPlan"))])
        extra.extend(["--bindings", str(_file(run, "regressionScope").parent / "source-bindings.json")])
    output, document = _regression(run, "verify" if final else "validate", plan, extra)
    if document.get("ok") is True:
        return Completion(artifacts=(file_artifact("regressionEvidence" if final else "regressionScope", output),))
    key: str = "build:regression-verify" if final else "build:regression-validate"
    if _count(run, key, "regressionCorrection") >= regression_rounds():
        raise StepError(key, OTHER_CAUSE, (str(output),))
    keys: tuple[str, ...] = (
        ("build:regression-remap", "build:regression-map-review", "build:regression-verify")
        if final
        else ("build:regression-reassess", "build:regression-review", "build:regression-validate")
    )
    return Completion(
        artifacts=(file_artifact("regressionCorrection", output),),
        add=(StepGroup(tuple(_new(kind, "Correct the regression contract and verify its evidence") for kind in keys)),),
    )


def _validate_initial(run: StepRun) -> Completion:
    """Validate reviewed scope.

    Returns:
        Validation evidence or corrections.

    """
    return _validate(run, False)


def _validate_final(run: StepRun) -> Completion:
    """Verify reviewed final evidence.

    Returns:
        Verification evidence or corrections.

    """
    return _validate(run, True)


def _reuse(run: StepRun) -> Completion:
    """Review use of shared capabilities instead of duplicating their implementation.

    Returns:
        The shared-capability specialist's independent review, or the policy's recorded omission.

    """
    decision: build_policy.Decision = build_policy.decide(run, "reuse-audit")
    if decision.action == "omit":
        return Completion(artifacts=(decision.artifact(),))
    reviewed: Completion = reasoned(
        run,
        "shared-capability-reviewer",
        OutputContract(CONTRACTS / "build-review.schema.json", "reuseReview"),
        "Review changed code against the shared capabilities the Task's matrix ids require",
        followups=(
            _new(
                "build:audit-reviewed",
                "Resolve the shared-capability review",
                {"review": "reuseReview", "again": "build:reuse-audit"},
            ),
        ),
    )
    return Completion(artifacts=(*reviewed.artifacts, decision.artifact()), add=reviewed.add)


def _cds(run: StepRun) -> Completion:
    """Review UI changes against the design source the Task actually records.

    Returns:
        A semantic CDS review and bounded correction consumer.

    """
    return reasoned(
        run,
        "cds-live-auditor",
        OutputContract(CONTRACTS / "build-review.schema.json", "cdsReview"),
        "Review changed UI against its recorded supplied bundle or live CDS design system",
        followups=(
            _new("build:audit-reviewed", "Resolve the CDS review", {"review": "cdsReview", "again": "build:cds-audit"}),
        ),
    )


def _design(run: StepRun) -> Completion:
    """Carry the Task's already-selected design source into its build journal.

    Returns:
        The stated source, bundle and build-spec paths without inventing another design.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    return Completion(
        artifacts=(
            value_artifact(
                "design",
                {
                    "designSource": bead.get("cdsDesignSource", "none"),
                    "bundle": bead.get("cdsBundlePath"),
                    "buildSpecs": bead.get("cdsBuildSpecs", []),
                },
            ),
        ),
    )


def _infrastructure(run: StepRun) -> Completion:
    """Make infrastructure implementation detail explicit through its real design specialist.

    Returns:
        A concrete provisioning-intent session.

    """
    return reasoned(
        run,
        "cdk-infrastructure-designer",
        OutputContract(CONTRACTS / "build-infrastructure.schema.json", "provisioning"),
        "Define concrete resources, stacks and cross-stack references for the Task's approved architecture",
    )


def _audit_reviewed(run: StepRun) -> Completion:
    """Correct the review's findings within the allowance, and never stop on a finding.

    Findings owned by the contract or the tooling are carried at once; findings still open when
    the correction allowance is spent are carried too, and the build continues.

    Returns:
        A clean review, the carried findings recorded, or implementation and repeat-review work.

    """
    params = run.params()
    name: str = check_type(params["review"], str)
    review: dict[str, JsonValue] = _document(run, name)
    required: list[JsonValue] = build_carried.required(check_type(review["findings"], list[JsonValue]))
    work: list[JsonValue] = build_carried.owned_here(required)
    reason: str = "its correction belongs to the contract or the tooling, or its correction allowance is spent"
    carried: tuple[ValueArtifact, ...] = (build_carried.carry(name, required, reason),) if required else ()
    if not work and (review["approved"] is True or required):
        return Completion(artifacts=carried)
    again: str = check_type(params["again"], str)
    if _count(run, again, name) >= build_rounds():
        return Completion(artifacts=carried)
    return Completion(
        add=(
            StepGroup((
                _new("build:correct-findings", "Resolve the independent review findings", {"review": name}),
                _new(again, "Re-review the corrected work against its prior findings"),
            )),
        ),
    )


def _correct(run: StepRun) -> Completion:
    """Select implementers for one review's unresolved findings, without a fresh whole-Task review.

    Returns:
        The implementation lead's selection for those findings and its plan.

    """
    review: str = check_type(run.params()["review"], str)
    return reasoned(
        run,
        "implementation-lead",
        OutputContract(CONTRACTS / "build-selection.schema.json", "implementationSelection"),
        f"Select the implementation specialists needed to resolve only the unresolved findings of the {review} "
        "review and the artifacts they name; accepted unrelated work stays as it is. Findings owned by the "
        "contract or the tooling are carried as recorded residuals and are not implementation work",
        followups=(_new("build:plan-code", "Plan the selected code specialists and suite check"),),
    )


def _docs(run: StepRun) -> Completion:
    """Select documentation specialists only for documents this change makes stale.

    Returns:
        The documentation lead's bounded subject judgment, or the policy's recorded omission.

    """
    decision: build_policy.Decision = build_policy.decide(run, "docs")
    if decision.action == "omit":
        return Completion(artifacts=(decision.artifact(),))
    selected: Completion = reasoned(
        run,
        "documentation-lead",
        OutputContract(CONTRACTS / "build-selection.schema.json", "documentationSelection"),
        "Select documentation specialists for the actual public and internal contracts changed by this Task",
        followups=(_new("build:docs-write", "Update the documentation this Task made stale"),),
    )
    return Completion(artifacts=(*selected.artifacts, decision.artifact()), add=selected.add)


def _docs_write(run: StepRun) -> Completion:
    """Plan the selected real documentation writers.

    Returns:
        Writer steps; no command relay or universal fixed documentation roster.

    """
    agents: list[str] = check_type(_document(run, "documentationSelection")["agents"], list[str])
    if not agents:
        return Completion()
    steps = tuple(
        _new("build:docs-specialist", f"Update stale documentation with {agent}", {"agent": agent}) for agent in agents
    )
    return Completion(add=(StepGroup(steps),))


def _docs_specialist(run: StepRun) -> Completion:
    """Start the documentation specialist chosen for the changed subject.

    Returns:
        Its genuine writing session.

    """
    agent: str = check_type(run.params()["agent"], str)
    return reasoned(
        run,
        agent,
        OutputContract(CONTRACTS / "build-implementation.schema.json", "documentationWork"),
        "Update the documents this Task's code and tests made stale",
    )


def attach_reviews(registry: Registry) -> None:
    """Register migration-compatible regression and documentation handler keys.

    Args:
        registry: The build flow's registry.

    Raises:
        TypeError: The registry is invalid.

    """
    if not isinstance(registry, Registry):
        message: str = "build reviews require Registry"
        raise TypeError(message)
    handlers = {
        "build:regression-assess": _scope_initial,
        "build:regression-reassess": _scope_initial,
        "build:regression-review": _review_initial,
        "build:regression-validate": _validate_initial,
        "build:regression-map": _scope_final,
        "build:regression-remap": _scope_final,
        "build:regression-map-review": _review_final,
        "build:regression-verify": _validate_final,
        "build:reuse-audit": _reuse,
        "build:cds-audit": _cds,
        "build:design-source": _design,
        "build:infra-intent": _infrastructure,
        "build:audit-reviewed": _audit_reviewed,
        "build:correct-findings": _correct,
        "build:docs-audit": _docs,
        "build:docs-write": _docs_write,
        "build:docs-specialist": _docs_specialist,
    }
    for key, handler in handlers.items():
        registry.script_step(key)(handler)
