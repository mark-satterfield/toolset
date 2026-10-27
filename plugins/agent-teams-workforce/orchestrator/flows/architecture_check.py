"""The script step between the architect and the promotion: what code can check, and what is in review.

It runs the matrix check, checks every criterion answer of the architect's result and the Epic's
review log (``log-architecture-review``), holds the result's reach verdicts to the Epic's reach as
the corrected matrix gives it (``matrixtraverse.approval_scope``, the set promotion approves), and
reads from the matrix the documents the Epic reaches
that are not effective. It then plans what follows by rule: a mechanical defect goes back to the
architect, a matter the architect could not settle goes to the lead, and otherwise the one TRD
write from the architect's decisions (``trd_steps``) and then the promotion step follow. Nothing
reviews the architect's work: the architect reviews and approves its own architecture against the
criteria, and the review log is the record of that review. The step
judges nothing and records nothing in the matrix: every branch is a rule over the matrix, the
criteria file, the architect's result and the review log.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "log-architecture-review" / "scripts"))
from architecture_work_contract import (
    CONCLUSION_UNSETTLED,
    VERDICT_CORRECTED,
    VERDICT_KEPT,
    VERDICT_PRUNED,
    CheckResult,
)
from matrix_contract import (
    KIND_COMPONENT,
    KIND_EPIC,
    KIND_INFRASTRUCTURE,
    KIND_LAYER,
    KIND_REQUIREMENT,
    KIND_SERVICE,
    MatrixError,
)
from matrixquery import epic_view
from matrixreview import ReviewScope, review_scope
from matrixstore import as_entry_id, file_problems, read_matrix
from matrixtraverse import approval_scope, epic_id, stacks_of
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
from orchestrator.flows.architecture_index import index_step
from orchestrator.flows.spec_review import CRITERIA_FILE
from orchestrator.flows.trd_steps import write_plan

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureResult
    from matrix_contract import Entry, EntryId, EntryKind
    from matrixquery import EpicView
    from matrixstore import Matrix
    from matrixtraverse import ApprovalScope
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
NO_VERDICT_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_EPIC, KIND_REQUIREMENT})
"""The entries of the reach that come from the PRD, which need no reach verdict."""
HOMED_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_SERVICE, KIND_COMPONENT, KIND_INFRASTRUCTURE, KIND_LAYER})
"""The kinds of reached entry a stack builds: each has a home stack or is listed under ``excluded``."""
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


def review_log_findings(bead: str, log: Path, matrix: Matrix | None, result: ArchitectureResult) -> list[str]:
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


def _reach_problems(matrix: Matrix, bead: str, result: ArchitectureResult) -> list[str]:
    """Hold the architect's reach verdicts and exclusions to the Epic's reach in the corrected matrix.

    The reach is recomputed on the matrix as the architect's change file left it, so the set the
    architect reviewed and the set promotion approves are one set.

    Returns:
        One problem for each entry of the reach, other than the Epic and its requirements, with
        no ``kept`` or ``corrected`` verdict (a ``pruned`` one is still reached); and one for each
        reached service, component, piece of infrastructure or layer with no home stack that is
        not listed under ``excluded``.

    """
    scope: ApprovalScope = approval_scope(matrix, epic_id(bead))
    verdicts: dict[str, str] = {row["id"]: row["verdict"] for row in result["reach"]}
    excluded: set[str] = {row["id"] for row in result["excluded"]}
    problems: list[str] = []
    entry_id: EntryId
    for entry_id in scope.entries:
        entry: Entry = matrix.entry(entry_id)
        verdict: str | None = verdicts.get(entry_id)
        if entry.kind not in NO_VERDICT_KINDS and verdict not in {VERDICT_KEPT, VERDICT_CORRECTED}:
            stated: str = (
                f"its verdict is {VERDICT_PRUNED} but the link that reaches it is still in the matrix"
                if verdict == VERDICT_PRUNED
                else "it has no verdict"
            )
            problems.append(
                f"reach: {entry_id} is in the Epic's reach ({scope.via[entry_id]}) and {stated}: review it and give "
                f"it a {VERDICT_KEPT} or {VERDICT_CORRECTED} verdict, or remove the link that reaches it",
            )
        if entry.kind in HOMED_KINDS and entry_id not in excluded and not stacks_of(matrix, entry_id):
            problems.append(
                f"excluded: {entry_id} is in the Epic's reach and has no home stack: place it in a stack, or list "
                "it under excluded with the reason no stack builds it",
            )
    return problems


def _mechanical(run: StepRun, result: ArchitectureResult, criteria: Criteria, log: Path) -> CheckResult:
    """Run every check code can make on the matrix, the architect's result and the review log.

    Returns:
        The problems ``atw-matrix check`` reports for the matrix file, an Epic the matrix does
        not hold, each reach verdict and exclusion :func:`_reach_problems` finds, each
        architecture or technical-requirement criterion the result leaves unanswered, and each
        problem of the Epic's review log.

    """
    path: Path = matrix_file()
    problems: list[str] = file_problems(path)
    matrix: Matrix | None = None if problems else read_matrix(path)
    if matrix is not None and matrix.find(epic_id(str(run.bead))) is None:
        problems.append(f"the matrix has no entry for the Epic {run.bead}")
    elif matrix is not None:
        problems.extend(_reach_problems(matrix, str(run.bead), result))
    answered: set[str] = {answer["criterion"] for answer in result["criteria"]}
    unanswered: list[str] = [
        entry.id
        for level in (LEVEL_ARCHITECTURE, LEVEL_TECHNICAL_REQUIREMENT)
        for entry in criteria.at_level(level)
        if entry.id not in answered
    ]
    problems.extend(f"criterion {name} has no answer in the architecture result" for name in unanswered)
    problems.extend(review_log_findings(str(run.bead), log, matrix, result))
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
    """Plan the one TRD write from the architect's decisions, then the promotion, after this check.

    Returns:
        The completion that plans the TRD write and the promotion, each handed this check step.

    """
    promote: StepPlan = {
        "description": PROMOTE_DESCRIPTION,
        "purpose": PROMOTE_PURPOSE,
        "script": PROMOTE,
        "inputs": [run.step["id"]],
    }
    return Completion(add=(StepGroup((NewStep(write_plan([run.step["id"]])), NewStep(promote))),))


def _correction(run: StepRun, check: CheckResult, path: Path) -> Completion:
    """Send mechanical defects back to the architect, and check again after the correction.

    Returns:
        The completion that plans one architect step, one index step and one check step after this one.

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
    return Completion(add=(StepGroup((NewStep(plan), index_step(["correction"]), again)),))


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
        return Completion(artifacts=tuple(recorded), add=(StepGroup((NewStep(routing), index_step(["lead"]), again)),))
    return Completion(artifacts=tuple(recorded), add=_promotion(run).add)
