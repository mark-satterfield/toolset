"""The script step between the architect and the promotion: what code can check, and what is in review.

It runs the matrix check, checks every criterion answer of the architect's result and the Epic's
review log (``log-architecture-review``), and reads from the matrix the documents the Epic reaches
that are not effective. It then plans what follows by rule: a mechanical defect goes back to the
architect, a matter the architect could not settle goes to the lead, and otherwise the promotion
step follows. Nothing reviews the architect's work: the architect reviews and approves its own
architecture against the criteria, and the review log is the record of that review. The step
judges nothing and records nothing in the matrix: every branch is a rule over the matrix, the
criteria file, the architect's result and the review log.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "log-architecture-review" / "scripts"))
from architecture_work_contract import CONCLUSION_UNSETTLED, CheckResult
from matrix_contract import MatrixError
from matrixquery import epic_view
from matrixreview import ReviewScope, review_scope
from matrixstore import as_entry_id, file_problems, read_matrix
from matrixtraverse import epic_id
from review_criteria import LEVEL_ARCHITECTURE, LEVEL_TECHNICAL_REQUIREMENT, Criteria, load_criteria
from review_log import ReviewLogError, read_log
from review_log import problems as review_log_problems
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type

from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import (
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
)
from orchestrator.flows.architecture_files import (
    ARCHITECT,
    ARCHITECTURE_FOLDER,
    ARTIFACT_CHECK,
    CHECK,
    LABEL_SCOPE,
    LEAD,
    PROMOTE,
    ArchitectureContext,
    ArchitectureStepError,
    lead_resolved,
    matrix_file,
    read_context,
    read_result,
)
from orchestrator.flows.spec_review import CRITERIA_FILE

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureResult
    from matrix_contract import Entry
    from matrixquery import EpicView
    from matrixstore import Matrix
    from step_journal_contract import Artifact, StepPlan

CHECK_DESCRIPTION: Final = "Check what code can check and list what is in review"
CHECK_PURPOSE: Final = (
    "Nothing a script can verify reaches the promotion unverified, and the architect's review of its own work is logged"
)
CORRECTION_DESCRIPTION: Final = "Correct what the mechanical check found"
CORRECTION_PURPOSE: Final = (
    "A defect a script can find is corrected by the architect before the architecture is promoted"
)
LEAD_DESCRIPTION: Final = "Route what the architect could not settle"
LEAD_PURPOSE: Final = "The team settles an open matter before the architecture is promoted"
PROMOTE_DESCRIPTION: Final = "Set the approved documents effective and commit the matrix"
PROMOTE_PURPOSE: Final = "Approved content becomes effective and every later Epic finds it as effective"
UNLINKED: Final = "links with nothing recorded at the other end"
CORRECTIONS: Final = "corrections"
MAX_CORRECTIONS: Final = 3
"""How many times the mechanical check sends its defects back to the architect before the step fails."""
ATTR_RESOURCE_TYPE: Final = "resourceType"
"""The attribute of a matrix entry that names the one AWS resource it is (``matrix-kinds.json``)."""


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


def _aws_resources(matrix: Matrix, elements: list[str]) -> dict[str, str]:
    """Name the AWS resources among the elements the design adds or changes.

    Returns:
        Each element whose matrix entry has a ``resourceType``, with that type.

    """
    found: dict[str, str] = {}
    element: str
    for element in elements:
        try:
            entry: Entry | None = matrix.find(as_entry_id(element.strip()))
        except MatrixError:
            continue
        kind: JsonValue = None if entry is None else entry.attributes.get(ATTR_RESOURCE_TYPE)
        if isinstance(kind, str):
            found[element] = kind
    return found


def _review_log_problems(bead: str, log: Path, matrix: Matrix | None, result: ArchitectureResult) -> list[str]:
    """Check the Epic's review log against the AWS resources the design adds or changes.

    Returns:
        Every problem ``log-architecture-review`` reports for the log; the log's absence or a
        log that is not JSON as one problem.

    """
    try:
        decoded: object = read_log(log)
    except ReviewLogError as error:
        return [str(error)]
    resources: dict[str, str] = {} if matrix is None else _aws_resources(matrix, result["addedOrChangedElements"])
    return review_log_problems(decoded, bead, resources)


def _mechanical(run: StepRun, result: ArchitectureResult, criteria: Criteria, log: Path) -> CheckResult:
    """Run every check code can make on the matrix, the architect's result and the review log.

    Returns:
        The problems ``atw-matrix check`` reports for the matrix file, an Epic the matrix does
        not hold, each architecture or technical-requirement criterion the result leaves
        unanswered, and each problem of the Epic's review log.

    """
    path: Path = matrix_file()
    problems: list[str] = file_problems(path)
    matrix: Matrix | None = None if problems else read_matrix(path)
    if matrix is not None and matrix.find(epic_id(str(run.bead))) is None:
        problems.append(f"the matrix has no entry for the Epic {run.bead}")
    answered: set[str] = {answer["criterion"] for answer in result["criteria"]}
    unanswered: list[str] = [
        entry.id
        for level in (LEVEL_ARCHITECTURE, LEVEL_TECHNICAL_REQUIREMENT)
        for entry in criteria.at_level(level)
        if entry.id not in answered
    ]
    problems.extend(f"criterion {name} has no answer in the architecture result" for name in unanswered)
    problems.extend(_review_log_problems(str(run.bead), log, matrix, result))
    corrections: JsonValue = run.params().get(CORRECTIONS, 0)
    return {
        "valid": not problems,
        "problems": problems,
        "unansweredCriteria": unanswered,
        "corrections": corrections if isinstance(corrections, int) else 0,
    }


def _open_review(bead: str, added_or_changed: list[str]) -> tuple[ReviewScope, EpicView]:
    """Read from the matrix what the promotion of an Epic sets effective.

    Nothing is changed: a document's lifecycle mirrors its arc42 front matter, so what is in
    review is what ``atw-matrix review-scope`` returns, with the documents that describe what
    the architect's result adds or changes.

    Args:
        bead: The Epic.
        added_or_changed: The ids the architect's result lists under ``addedOrChangedElements``.

    Returns:
        The review scope, and what ``atw-matrix epic --unlinked`` returns: the Epic's links with
        nothing recorded at the other end.

    """
    matrix: Matrix = read_matrix(matrix_file())
    return review_scope(matrix, bead, added_or_changed), epic_view(matrix, bead, unlinked=True)


def _promotion(run: StepRun) -> Completion:
    """Plan the promotion step after this check.

    Returns:
        The completion that plans the promotion, handed this check step's review scope.

    """
    promote: StepPlan = {
        "description": PROMOTE_DESCRIPTION,
        "purpose": PROMOTE_PURPOSE,
        "script": PROMOTE,
        "inputs": [run.step["id"]],
    }
    return Completion(add=(StepGroup((NewStep(promote),)),))


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
    architect: str = ARCHITECT
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
    corrections did not clear end the step as a failure. Every file the step writes is in its
    own folder, named for the step, so a later check never overwrites what an earlier one
    recorded.

    Returns:
        The check result always; the review scope and the Epic's links with nothing recorded at
        the other end when the check passed; and the steps that follow.

    """
    context: ArchitectureContext = read_context(run)
    result: ArchitectureResult = read_result(run, context)
    criteria: Criteria = load_criteria(run.tools.plugin / CRITERIA_FILE)
    folder: Path = run.context.work / ARCHITECTURE_FOLDER / "checks" / run.step["id"]
    checked: CheckResult = run.tools.portfolio(
        CHECK,
        _mechanical,
        run,
        result,
        criteria,
        Path(context["reviewLogPath"]),
    )
    check_path: Path = folder / "check.json"
    write_json(check_path, checked)
    recorded: list[Artifact] = [file_artifact(ARTIFACT_CHECK, check_path)]
    if not checked["valid"]:
        return Completion(artifacts=tuple(recorded), add=_correction(run, checked, check_path).add)
    scope: ReviewScope
    unlinked: EpicView
    scope, unlinked = run.tools.portfolio(
        CHECK,
        _open_review,
        str(run.bead),
        result["addedOrChangedElements"],
    )
    recorded.extend(_review_files(folder, scope, unlinked))
    lead: str = LEAD
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
    return Completion(artifacts=tuple(recorded), add=_promotion(run).add)
