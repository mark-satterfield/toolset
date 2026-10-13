"""The script step between the architect and the reviewers: what code can check, and what is unapproved.

It runs the matrix check and lists what is not approved for the Epic, both through the matrix
modules. It then plans what follows by rule: a mechanical defect goes back to the architect, a
matter the architect could not settle goes to the lead, and otherwise the reviewers the criteria
file selects are planned with the promotion step after them. It judges nothing: every branch is a
rule over the matrix, the criteria file and the architect's result.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import CONCLUSION_UNSETTLED, CheckResult
from matrix_contract import (
    FACT_SCENARIO,
    KIND_FACT,
    KIND_PRD,
    Claim,
    Matrix,
    ReviewerScope,
    ReviewScope,
    validate_review_scope,
)
from matrixreview import open_review
from matrixstore import Stamp, file_problems, make_id, matrix_path, read_matrix, timestamp, update_matrix
from matrixsync import vault_problems
from review_criteria import (
    LEVEL_ARCHITECTURE,
    LEVEL_TECHNICAL_REQUIREMENT,
    Criteria,
    ReviewerGroup,
    ScopeKind,
    load_criteria,
)
from typeguard import CollectionCheckStrategy, check_type

from orchestrator.core.io import JsonValue, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import (
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.flows.architecture_files import (
    APPROVE,
    ARCHITECTURE_FOLDER,
    ARTIFACT_CHECK,
    CHECK,
    LABEL_SCOPE,
    ROLE_ARCHITECT,
    ROLE_LEAD,
    ArchitectureContext,
    ArchitectureStepError,
    agents_with_role,
    lead_resolved,
    read_context,
    read_result,
)
from orchestrator.flows.spec_review import CRITERIA_FILE

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureResult
    from step_journal_contract import Artifact, StepPlan

CHECK_DESCRIPTION: Final = "Check what code can check and list what is unapproved"
CHECK_PURPOSE: Final = (
    "Reviewers receive only content that is not yet approved, and nothing a script can verify reaches them"
)
CORRECTION_DESCRIPTION: Final = "Correct what the mechanical check found"
CORRECTION_PURPOSE: Final = "A defect a script can find is corrected by the architect before any reviewer is started"
LEAD_DESCRIPTION: Final = "Route what the architect could not settle"
LEAD_PURPOSE: Final = "The team settles an open matter before any reviewer is started"
FINDINGS_LEAD_DESCRIPTION: Final = "Route what the reviews found"
FINDINGS_LEAD_PURPOSE: Final = "The team settles each finding with the least further work"
REVIEW_PURPOSE: Final = "Independent check of unapproved content against the same criteria the architect worked to"
PROMOTE_DESCRIPTION: Final = "Promote the reviewed documents and mark them approved"
PROMOTE_PURPOSE: Final = "Reviewed content becomes effective and every later Epic finds it as approved"
SELECTED: Final = "reviewers selected by rule"
CORRECTIONS: Final = "corrections"
MAX_CORRECTIONS: Final = 3
"""How many times the mechanical check sends its defects back to the architect before the step fails."""
SCOPE_HEADING: Final[ScopeKind] = "heading"
SCOPE_SCENARIO: Final[ScopeKind] = "scenario-fact"
SCOPE_TRD: Final[ScopeKind] = "trd-requirement"


def check_step(inputs: list[str], *, corrections: int) -> NewStep:
    """Plan one check step.

    Args:
        inputs: The steps whose artifacts the check is handed, by id or by ref.
        corrections: How many corrections of mechanical defects came before it.

    Returns:
        The planned step; a check that follows a correction is handed how many came before.

    """
    plan: StepPlan = {"description": CHECK_DESCRIPTION, "purpose": CHECK_PURPOSE, "script": CHECK, "inputs": inputs}
    return NewStep(plan, {CORRECTIONS: corrections} if corrections else None)


def _mechanical(
    run: StepRun,
    context: ArchitectureContext,
    result: ArchitectureResult,
    criteria: Criteria,
) -> CheckResult:
    """Run every check code can make on the matrix, the vault and the architect's result.

    Returns:
        The problems of the matrix file and of the documents it indexes, a missing PRD row, and
        each architecture or technical-requirement criterion the result leaves unanswered.

    """
    path: Path = matrix_path(None, os.environ)
    problems: list[str] = file_problems(path)
    if not problems:
        matrix: Matrix = read_matrix(path)
        problems.extend(vault_problems(matrix, Path(context["architectureRoot"])))
        if make_id(KIND_PRD, run.bead) not in matrix["nodes"]:
            problems.append(f"the matrix has no PRD row for {run.bead}")
    answered: set[str] = {answer["criterion"] for answer in result["criteria"]}
    unanswered: list[str] = [
        entry.id
        for level in (LEVEL_ARCHITECTURE, LEVEL_TECHNICAL_REQUIREMENT)
        for entry in criteria.at_level(level)
        if entry.id not in answered
    ]
    problems.extend(f"criterion {name} has no answer in the architecture result" for name in unanswered)
    corrections: JsonValue = run.params().get(CORRECTIONS, 0)
    return {
        "valid": not problems,
        "problems": problems,
        "unansweredCriteria": unanswered,
        "corrections": corrections if isinstance(corrections, int) else 0,
    }


def _scope_kinds(scope: ReviewScope) -> set[ScopeKind]:
    """Name the kinds of unapproved content one Epic's review holds.

    The TRD of an elaboration is always unapproved content: it is written for this Epic.

    Returns:
        The scope kinds the criteria file's selection rules test.

    """
    kinds: set[ScopeKind] = {SCOPE_TRD}
    if scope["headings"]:
        kinds.add(SCOPE_HEADING)
    matrix: Matrix = read_matrix(matrix_path(None, os.environ))
    if any(
        row["kind"] == KIND_FACT and matrix["nodes"][row["id"]].get("factKind") == FACT_SCENARIO
        for row in scope["rows"]
    ):
        kinds.add(SCOPE_SCENARIO)
    return kinds


def _narrowed(
    scope: ReviewScope,
    reviewer: str,
    groups: list[ReviewerGroup],
    result: ArchitectureResult,
    trd: str,
) -> ReviewerScope:
    """Narrow the review scope to what one reviewer's criteria apply to.

    Returns:
        The unapproved headings and rows when a group of the reviewer is selected by them or by
        a signal of the architect's result, the TRD when a group covers its requirements, and
        the signal lists that selected the reviewer.

    """
    kinds: set[ScopeKind] = {kind for group in groups for kind in group.applies_when.scope}
    signals: dict[str, list[JsonValue]] = {}
    stated: dict[str, object] = dict(result["reviewSignals"])
    name: str
    for name in dict.fromkeys(name for group in groups for name in group.applies_when.result):
        listed: object = stated.get(name)
        if isinstance(listed, list) and listed:
            signals[name] = check_type(
                listed,
                list[JsonValue],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
    documents: bool = bool(signals) or bool(kinds & {SCOPE_HEADING, SCOPE_SCENARIO})
    return {
        "bead": scope["bead"],
        "at": scope["at"],
        "prd": scope["prd"],
        "reviewer": reviewer,
        "groups": [group.id for group in groups],
        "criteria": list(dict.fromkeys(name for group in groups for name in group.criteria)),
        "rows": scope["rows"] if documents else [],
        "headings": scope["headings"] if documents else [],
        "heldByOthers": scope["heldByOthers"] if documents else [],
        "trd": trd if SCOPE_TRD in kinds else None,
        "signals": signals,
    }


def _review_steps(run: StepRun, scope: ReviewScope, result: ArchitectureResult, criteria: Criteria) -> Completion:
    """Plan one step per reviewer the criteria file selects, and the promotion after them.

    Returns:
        The completion: the review scope, the reviewers selected and the planned steps.

    Raises:
        ArchitectureStepError: The rule selects no reviewer, so nothing could approve the content.

    """
    context: ArchitectureContext = read_context(run)
    folder: Path = run.context.work / ARCHITECTURE_FOLDER
    present: set[ScopeKind] = _scope_kinds(scope)
    signals: list[str] = [name for name, listed in dict(result["reviewSignals"]).items() if listed]
    selected: dict[str, list[ReviewerGroup]] = {}
    group: ReviewerGroup
    for group in criteria.groups:
        if group.applies_when.selects(present, signals):
            selected.setdefault(group.reviewer, []).append(group)
    if not selected:
        raise ArchitectureStepError(run, "the criteria file selects no reviewer for the unapproved content")
    steps: list[NewStep] = []
    reviewer: str
    groups: list[ReviewerGroup]
    for reviewer, groups in selected.items():
        narrowed: ReviewerScope = _narrowed(scope, reviewer, groups, result, context["trdPath"])
        path: Path = folder / f"review-scope.{reviewer}.json"
        write_json(path, narrowed)
        covered: str = ", ".join(narrowed["groups"])
        plan: StepPlan = {
            "ref": reviewer,
            "description": f"Review the unapproved content for {covered}",
            "purpose": REVIEW_PURPOSE,
            "agent": reviewer,
            "inputs": [run.step["id"]],
        }
        steps.append(NewStep(plan, {"scope": str(path), "trd": narrowed["trd"]}))
    promote: StepPlan = {
        "description": PROMOTE_DESCRIPTION,
        "purpose": PROMOTE_PURPOSE,
        "script": APPROVE,
        "inputs": list(selected),
    }
    steps.append(NewStep(promote))
    return Completion(
        artifacts=(value_artifact(SELECTED, list(selected)),),
        add=(StepGroup(tuple(steps)),),
    )


def _correction(run: StepRun, check: CheckResult, path: Path) -> Completion:
    """Send mechanical defects back to the architect, and check again after the correction.

    Returns:
        The completion that plans one architect step and one check step after this one.

    Raises:
        ArchitectureStepError: The architect has already corrected mechanical defects as often
            as the pipeline allows.

    """
    if check["corrections"] >= MAX_CORRECTIONS:
        raise ArchitectureStepError(
            run,
            f"the mechanical check still finds defects after {MAX_CORRECTIONS} corrections; see {path}",
            *check["problems"],
        )
    architect: str = agents_with_role(run.tools.plugin, ROLE_ARCHITECT)[0]
    plan: StepPlan = {
        "ref": "correction",
        "description": CORRECTION_DESCRIPTION,
        "purpose": CORRECTION_PURPOSE,
        "agent": architect,
        "inputs": [run.step["id"]],
    }
    again: NewStep = check_step(["correction"], corrections=check["corrections"] + 1)
    return Completion(add=(StepGroup((NewStep(plan), again)),))


def _open_review(run: StepRun) -> ReviewScope:
    """List what is not approved for the Epic and mark it in review, as ``atw-matrix unapproved`` does.

    Returns:
        The review scope, validated against the matrix contract.

    """
    at: str = timestamp()
    claim: Claim = {"bead": run.bead, "step": run.step["id"], "at": at}
    stamp: Stamp = Stamp(at, f"{run.bead} {run.step['id']}")

    def opened(matrix: Matrix) -> ReviewScope:
        return validate_review_scope(open_review(matrix, run.bead, claim, stamp))

    return update_matrix(matrix_path(None, os.environ), opened)


@script_step(CHECK)
def check(run: StepRun) -> Completion:
    """Check what code can check, list what is unapproved, and plan what follows by rule.

    A result file that cannot be read, a matrix that refuses, and a defect that three
    corrections did not clear end the step as a failure.

    Returns:
        The check result always; the review scope and the selected reviewers when the check
        passed; and the steps that follow.

    """
    context: ArchitectureContext = read_context(run)
    result: ArchitectureResult = read_result(run, context)
    criteria: Criteria = load_criteria(run.tools.plugin / CRITERIA_FILE)
    folder: Path = run.context.work / ARCHITECTURE_FOLDER
    checked: CheckResult = run.tools.portfolio(CHECK, _mechanical, run, context, result, criteria)
    check_path: Path = folder / f"check-{checked['corrections']}.json"
    write_json(check_path, checked)
    recorded: list[Artifact] = [file_artifact(ARTIFACT_CHECK, check_path)]
    if not checked["valid"]:
        return Completion(artifacts=tuple(recorded), add=_correction(run, checked, check_path).add)
    scope: ReviewScope = run.tools.portfolio(CHECK, _open_review, run)
    scope_path: Path = folder / "review-scope.json"
    write_json(scope_path, scope)
    recorded.append(file_artifact(LABEL_SCOPE, scope_path))
    lead: str = agents_with_role(run.tools.plugin, ROLE_LEAD)[0]
    if result["conclusion"] == CONCLUSION_UNSETTLED and lead_resolved(run, lead) is None:
        routing: StepPlan = {
            "ref": "lead",
            "description": LEAD_DESCRIPTION,
            "purpose": LEAD_PURPOSE,
            "agent": lead,
            "inputs": [run.step["id"]],
        }
        again: NewStep = check_step(["lead"], corrections=checked["corrections"])
        return Completion(artifacts=tuple(recorded), add=(StepGroup((NewStep(routing), again)),))
    reviews: Completion = _review_steps(run, scope, result, criteria)
    return Completion(artifacts=(*recorded, *reviews.artifacts), add=reviews.add)
