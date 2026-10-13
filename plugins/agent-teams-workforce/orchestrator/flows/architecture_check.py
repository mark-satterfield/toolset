"""The script step between the architect and the reviewers: what code can check, and what is in review.

It runs the matrix check and reads from the matrix what the review of the Epic is handed: the
documents the Epic reaches that are not effective. It then plans what follows by rule: a
mechanical defect goes back to the architect, a matter the architect could not settle goes to the
lead, and otherwise the reviewers the criteria file selects are planned with the promotion step
after them. It judges nothing and records nothing in the matrix: every branch is a rule over the
matrix, the criteria file and the architect's result.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import CONCLUSION_UNSETTLED, CheckResult
from matrixquery import epic_view
from matrixreview import ReviewScope, ScopeDocument, review_scope
from matrixstore import file_problems, read_matrix
from matrixtraverse import epic_id
from review_criteria import (
    LEVEL_ARCHITECTURE,
    LEVEL_TECHNICAL_REQUIREMENT,
    Criteria,
    ReviewerGroup,
    ScopeKind,
    load_criteria,
)
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type

from orchestrator.core.io import JsonValue, json_object, write_json
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
    ARCHITECTURE_FOLDER,
    ARTIFACT_CHECK,
    CHECK,
    LABEL_SCOPE,
    PROMOTE,
    ROLE_ARCHITECT,
    ROLE_LEAD,
    ArchitectureContext,
    ArchitectureStepError,
    agents_with_role,
    lead_resolved,
    matrix_file,
    read_context,
    read_result,
)
from orchestrator.flows.spec_review import CRITERIA_FILE

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureResult
    from matrixquery import EpicView
    from matrixstore import Matrix
    from step_journal_contract import Artifact, StepPlan

CHECK_DESCRIPTION: Final = "Check what code can check and list what is in review"
CHECK_PURPOSE: Final = (
    "Reviewers receive only content that is not yet effective, and nothing a script can verify reaches them"
)
CORRECTION_DESCRIPTION: Final = "Correct what the mechanical check found"
CORRECTION_PURPOSE: Final = "A defect a script can find is corrected by the architect before any reviewer is started"
LEAD_DESCRIPTION: Final = "Route what the architect could not settle"
LEAD_PURPOSE: Final = "The team settles an open matter before any reviewer is started"
FINDINGS_LEAD_DESCRIPTION: Final = "Route what the reviews found"
FINDINGS_LEAD_PURPOSE: Final = "The team settles each finding with the least further work"
REVIEW_PURPOSE: Final = "Independent check of content in review against the same criteria the architect worked to"
PROMOTE_DESCRIPTION: Final = "Set the reviewed documents effective and commit the matrix"
PROMOTE_PURPOSE: Final = "Reviewed content becomes effective and every later Epic finds it as effective"
SELECTED: Final = "reviewers selected by rule"
UNLINKED: Final = "links with nothing recorded at the other end"
CORRECTIONS: Final = "corrections"
MAX_CORRECTIONS: Final = 3
"""How many times the mechanical check sends its defects back to the architect before the step fails."""
SCOPE_HEADING: Final[ScopeKind] = "heading"
SCOPE_SCENARIO: Final[ScopeKind] = "scenario-fact"
SCOPE_TRD: Final[ScopeKind] = "trd-requirement"
ATTR_SECTION: Final = "section"
RUNTIME_VIEW_SECTION: Final = 6
"""The arc42 section that holds scenarios: a document of it in review is scenario content."""


class ReviewerScope(TypedDict):
    """What one reviewer is handed as its review scope: the Epic's review scope, narrowed to its criteria."""

    bead: str
    epic: str
    """The id of the Epic's entry in the matrix."""
    reviewer: str
    groups: list[str]
    """The reviewer groups of the criteria file that selected the reviewer."""
    criteria: list[str]
    documents: list[ScopeDocument]
    """The documents in review with the headings reached; empty when no group of the reviewer covers documents."""
    trd: str | None
    """The TRD's path when a group of the reviewer covers its requirements."""
    signals: dict[str, list[JsonValue]]
    """The lists of the architect's result that selected the reviewer, by name."""


def validate_review_scope(value: object, where: str = "ReviewScope") -> ReviewScope:
    """Accept a decoded JSON value as the review scope of one Epic.

    Returns:
        The same value, typed.

    Raises:
        ValueError: The value is not what ``atw-matrix review-scope`` prints.

    """
    try:
        return check_type(value, ReviewScope, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    except TypeCheckError as error:
        message: str = f"{where}: {error}"
        raise ValueError(message) from error


def validate_reviewer_scope(value: object, where: str = "ReviewerScope") -> ReviewerScope:
    """Accept a decoded JSON value as the review scope one reviewer is handed.

    Returns:
        The same value, typed.

    Raises:
        ValueError: The value is not a reviewer's scope as the check step writes it.

    """
    try:
        return check_type(value, ReviewerScope, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    except TypeCheckError as error:
        message: str = f"{where}: {error}"
        raise ValueError(message) from error


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


def _mechanical(run: StepRun, result: ArchitectureResult, criteria: Criteria) -> CheckResult:
    """Run every check code can make on the matrix and the architect's result.

    Returns:
        The problems ``atw-matrix check`` reports for the matrix file, an Epic the matrix does
        not hold, and each architecture or technical-requirement criterion the result leaves
        unanswered.

    """
    path: Path = matrix_file()
    problems: list[str] = file_problems(path)
    if not problems and read_matrix(path).find(epic_id(str(run.bead))) is None:
        problems.append(f"the matrix has no entry for the Epic {run.bead}")
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


def _scope_kinds(matrix: Matrix, scope: ReviewScope) -> set[ScopeKind]:
    """Name the kinds of content in review one Epic's review holds.

    The TRD of an elaboration is always content in review: it is written for this Epic.

    Returns:
        The scope kinds the criteria file's selection rules test: headings when a document is in
        review, and scenarios when one of those documents is of the arc42 runtime view.

    """
    kinds: set[ScopeKind] = {SCOPE_TRD}
    if scope["documents"]:
        kinds.add(SCOPE_HEADING)
    if any(
        matrix.entry(document["id"]).attributes.get(ATTR_SECTION) == RUNTIME_VIEW_SECTION
        for document in scope["documents"]
    ):
        kinds.add(SCOPE_SCENARIO)
    return kinds


def _open_review(bead: str) -> tuple[ReviewScope, set[ScopeKind], EpicView]:
    """Read from the matrix what the review of an Epic is handed.

    Nothing is changed: a document's lifecycle mirrors its arc42 front matter, so what is in
    review is what ``atw-matrix review-scope`` returns.

    Returns:
        The review scope, the kinds of content it holds, and what ``atw-matrix epic --unlinked``
        returns: the Epic's links with nothing recorded at the other end.

    """
    matrix: Matrix = read_matrix(matrix_file())
    scope: ReviewScope = review_scope(matrix, bead)
    return scope, _scope_kinds(matrix, scope), epic_view(matrix, bead, unlinked=True)


def _narrowed(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - What one reviewer's scope is made from.
    bead: str,
    scope: ReviewScope,
    reviewer: str,
    groups: list[ReviewerGroup],
    result: ArchitectureResult,
    trd: str,
) -> ReviewerScope:
    """Narrow the review scope to what one reviewer's criteria apply to.

    Returns:
        The documents in review when a group of the reviewer is selected by them or by a signal
        of the architect's result, the TRD when a group covers its requirements, and the signal
        lists that selected the reviewer.

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
        "bead": bead,
        "epic": scope["epic"],
        "reviewer": reviewer,
        "groups": [group.id for group in groups],
        "criteria": list(dict.fromkeys(name for group in groups for name in group.criteria)),
        "documents": scope["documents"] if documents else [],
        "trd": trd if SCOPE_TRD in kinds else None,
        "signals": signals,
    }


def _review_steps(
    run: StepRun,
    scope: ReviewScope,
    present: set[ScopeKind],
    result: ArchitectureResult,
    criteria: Criteria,
) -> Completion:
    """Plan one step per reviewer the criteria file selects, and the promotion after them.

    Returns:
        The completion: the reviewers selected and the planned steps.

    Raises:
        ArchitectureStepError: The rule selects no reviewer, so nothing could review the content.

    """
    context: ArchitectureContext = read_context(run)
    folder: Path = run.context.work / ARCHITECTURE_FOLDER
    signals: list[str] = [name for name, listed in dict(result["reviewSignals"]).items() if listed]
    selected: dict[str, list[ReviewerGroup]] = {}
    group: ReviewerGroup
    for group in criteria.groups:
        if group.applies_when.selects(present, signals):
            selected.setdefault(group.reviewer, []).append(group)
    if not selected:
        raise ArchitectureStepError(run, "the criteria file selects no reviewer for the content in review")
    steps: list[NewStep] = []
    reviewer: str
    groups: list[ReviewerGroup]
    for reviewer, groups in selected.items():
        narrowed: ReviewerScope = _narrowed(str(run.bead), scope, reviewer, groups, result, context["trdPath"])
        path: Path = folder / f"review-scope.{reviewer}.json"
        write_json(path, narrowed)
        covered: str = ", ".join(narrowed["groups"])
        plan: StepPlan = {
            "ref": reviewer,
            "description": f"Review the content in review for {covered}",
            "purpose": REVIEW_PURPOSE,
            "agent": reviewer,
            "inputs": [run.step["id"]],
        }
        steps.append(NewStep(plan, {"scope": str(path), "trd": narrowed["trd"]}))
    promote: StepPlan = {
        "description": PROMOTE_DESCRIPTION,
        "purpose": PROMOTE_PURPOSE,
        "script": PROMOTE,
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


def _review_files(folder: Path, scope: ReviewScope, unlinked: EpicView) -> list[Artifact]:
    """Write what the matrix returned for the review to the Epic's architecture work folder.

    Returns:
        The review scope and the Epic's links with nothing recorded at the other end, as the file
        artifacts the step records.

    """
    scope_path: Path = folder / "review-scope.json"
    write_json(scope_path, scope)
    unlinked_path: Path = folder / "unlinked.json"
    write_json(unlinked_path, json_object(unlinked))
    return [file_artifact(LABEL_SCOPE, scope_path), file_artifact(UNLINKED, unlinked_path)]


@script_step(CHECK)
def check(run: StepRun) -> Completion:
    """Check what code can check, list what is in review, and plan what follows by rule.

    A result file that cannot be read, a matrix that refuses, and a defect that three
    corrections did not clear end the step as a failure.

    Returns:
        The check result always; the review scope, the Epic's links with nothing recorded at the
        other end and the selected reviewers when the check passed; and the steps that follow.

    """
    context: ArchitectureContext = read_context(run)
    result: ArchitectureResult = read_result(run, context)
    criteria: Criteria = load_criteria(run.tools.plugin / CRITERIA_FILE)
    folder: Path = run.context.work / ARCHITECTURE_FOLDER
    checked: CheckResult = run.tools.portfolio(CHECK, _mechanical, run, result, criteria)
    check_path: Path = folder / f"check-{checked['corrections']}.json"
    write_json(check_path, checked)
    recorded: list[Artifact] = [file_artifact(ARTIFACT_CHECK, check_path)]
    if not checked["valid"]:
        return Completion(artifacts=tuple(recorded), add=_correction(run, checked, check_path).add)
    scope: ReviewScope
    present: set[ScopeKind]
    unlinked: EpicView
    scope, present, unlinked = run.tools.portfolio(CHECK, _open_review, str(run.bead))
    recorded.extend(_review_files(folder, scope, unlinked))
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
    reviews: Completion = _review_steps(run, scope, present, result, criteria)
    return Completion(artifacts=(*recorded, *reviews.artifacts), add=reviews.add)
