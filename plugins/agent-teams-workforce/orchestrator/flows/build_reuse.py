"""The build's reuse audit: the deterministic reuse check, then a reviewer only for what it cannot rule on.

``build:reuse-audit`` runs ``check-reuse`` (:func:`matrixreuse.check_reuse`) in process against the
matrix ids the Task states (its ``matrix_elements``) and the Story worktree. A line that does itself
what a shared capability provides, and a capability the Task must use that nothing references, are
blocking findings the check settles. A new definition whose name reads like a provided behaviour is
an item the check cannot rule on: only then is the shared-capability-reviewer started, with every
such item in its request. With no such item the step records the review itself.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from typeguard import check_type

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import EntryId, MatrixError
from matrixreuse import ReuseItem, ReuseResult, check_reuse
from matrixstore import Matrix, read_matrix

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, file_artifact
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import matrix_file
from orchestrator.flows.build_sessions import OutputContract, reasoned
from orchestrator.flows.build_state import CONTRACTS, new_step, workspace_of

STAGE: Final = "build:reuse-audit"
REVIEW: Final = "reuseReview"
REVIEWER: Final = "shared-capability-reviewer"
ELEMENTS: Final = "matrix_elements"
"""The bead field that holds the matrix ids the Task states."""
REVIEW_FILE: Final = "reuse-review.json"
ITEMS_FILE: Final = "reuse-items.json"
"""The items handed to the reviewer, beside the step's facts."""


def _item_text(item: ReuseItem) -> str:
    """Describe one finding of the check: where it is, what it is, and the capability it concerns.

    Returns:
        ``<file>:<line> <finding> <feature> <provides>: <detail>``, without the place when it has none.

    """
    file: str | None = item.get("file")
    line: int | None = item.get("line")
    place: str = "" if file is None else f"{file}:{line} " if line is not None else f"{file} "
    return f"{place}{item['finding']} {item['feature']} {item['provides']}: {item['detail']}"


def _finding(item: ReuseItem, severity: str) -> dict[str, JsonValue]:
    """Turn one finding of the check into a build review finding.

    Returns:
        The finding, owned by implementation unless it is a note, with the item's file and line.

    """
    finding: dict[str, JsonValue] = {"severity": severity, "detail": _item_text(item)}
    if "file" in item:
        finding["file"] = item["file"]
    if "line" in item:
        finding["line"] = item["line"]
    if severity != "note":
        finding["owner"] = "implementation"
    return finding


def _item_json(item: ReuseItem) -> dict[str, JsonValue]:
    """Hand one item of the check to the reviewer as it was found.

    Returns:
        Its feature, provides id and detail, with its file and line when it has them.

    """
    handed: dict[str, JsonValue] = {"feature": item["feature"], "provides": item["provides"], "detail": item["detail"]}
    if "file" in item:
        handed["file"] = item["file"]
    if "line" in item:
        handed["line"] = item["line"]
    return handed


def _review(findings: list[dict[str, JsonValue]], evidence: str) -> dict[str, JsonValue]:
    """Shape a review under ``build-review.schema.json``.

    Returns:
        The review, approved when no finding asks for a change.

    """
    listed: list[JsonValue] = [*findings]
    return {
        "approved": all(finding["severity"] == "note" for finding in findings),
        "findings": listed,
        "evidence": evidence,
    }


def _unknown(matrix: Matrix, ids: list[EntryId]) -> list[EntryId]:
    """List the stated ids the matrix holds no entry for.

    Returns:
        Those ids, in the order stated.

    """
    return [entry_id for entry_id in ids if matrix.find(entry_id) is None]


def _unchecked_note(unchecked: str) -> dict[str, JsonValue]:
    """Note a relied-on behaviour whose use the check could not see.

    Returns:
        The note finding.

    """
    return {"severity": "note", "detail": f"{unchecked} carries no use signal, so its use could not be checked"}


def _checked(run: StepRun, ids: list[EntryId]) -> tuple[ReuseResult | None, list[dict[str, JsonValue]]]:
    """Run the deterministic reuse check on the ids the matrix holds.

    Returns:
        The check's result, or None when no stated id is in the matrix; and a contract finding for
        the stated ids the matrix does not hold.

    Raises:
        StepError: The check could not read the worktree.

    """
    matrix: Matrix = read_matrix(matrix_file())
    unknown: list[EntryId] = _unknown(matrix, ids)
    contract: list[dict[str, JsonValue]] = (
        [
            {
                "severity": "blocking",
                "owner": "contract",
                "detail": f"the Task's {ELEMENTS} name ids the matrix holds no entry for: {', '.join(unknown)}",
            },
        ]
        if unknown
        else []
    )
    known: list[EntryId] = [entry_id for entry_id in ids if entry_id not in unknown]
    if not known:
        return None, contract
    try:
        return check_reuse(matrix, known, workspace_of(run).tree), contract
    except MatrixError as error:
        raise StepError(STAGE, OTHER_CAUSE, (f"check-reuse could not check the worktree: {error}",)) from error


def _settled_findings(result: ReuseResult) -> list[dict[str, JsonValue]]:
    """Turn what the check settles into review findings.

    Returns:
        Each violation as a blocking finding, and each relied-on behaviour with no use signal as a note.

    """
    return [
        *(_finding(item, "blocking") for item in result["violations"]),
        *(_unchecked_note(unchecked) for unchecked in result["unchecked"]),
    ]


def _settled(result: ReuseResult, contract: list[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    """Record what the check settles, for a Task with no definition left to rule on.

    Returns:
        The review of the contract findings and the check's settled findings.

    """
    evidence: str = (
        f"check-reuse read {len(result['files'])} changed file(s) against {len(result['capabilities'])} shared "
        f"capability(ies): {len(result['violations'])} violation(s), no definition left for a reviewer to rule on"
    )
    return _review([*contract, *_settled_findings(result)], evidence)


def _reviewer_request(run: StepRun, result: ReuseResult, settled: list[dict[str, JsonValue]]) -> str:
    """Write the items the check could not rule on, and what it settled, to a file the reviewer reads.

    Returns:
        The request, naming that file.

    """
    items: list[JsonValue] = [_item_json(item) for item in result["judgment"]]
    carried: list[JsonValue] = [*settled]
    handed: Path = run.context.work / "build" / str(run.step["id"]) / ITEMS_FILE
    write_json(handed, {"items": items, "settled": carried})
    return (
        f"Rule on each of the {len(items)} items the deterministic reuse check could not rule on, listed under "
        f"items in {handed} (file and line in the work tree, the capability as feature, its provides id, and the "
        "definition with the words it shares with the provided behaviour as detail). Read each definition once, "
        "however many items name it. Record a blocking finding, owner implementation, with its file and line for "
        "each item you rule a duplicate, its detail the feature, the provides id and the reason; record no finding "
        "for a not-duplicate. Copy each finding under settled in that file into findings unchanged: the check "
        "settled them. In evidence, state how many items you ruled and how many were duplicates. approved is true "
        "only when no finding is blocking"
    )


def audit(run: StepRun) -> Completion:
    """Check the changed files against the Task's shared capabilities; start the reviewer only when needed.

    Args:
        run: The ``build:reuse-audit`` step.

    Returns:
        The review the step recorded, or the reviewer's session; then the consumer of the review.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    ids: list[EntryId] = [EntryId(entry_id) for entry_id in check_type(bead.get(ELEMENTS, []), list[str])]
    consumer = new_step(
        "build:audit-reviewed",
        "Resolve the shared-capability review",
        {"review": REVIEW, "again": STAGE},
    )
    result: ReuseResult | None = None
    contract: list[dict[str, JsonValue]] = []
    if ids:
        result, contract = _checked(run, ids)
    if result is not None and result["judgment"]:
        return reasoned(
            run,
            REVIEWER,
            OutputContract(CONTRACTS / "build-review.schema.json", REVIEW),
            _reviewer_request(run, result, [*contract, *_settled_findings(result)]),
            followups=(consumer,),
        )
    document: dict[str, JsonValue] = (
        _settled(result, contract)
        if result is not None
        else _review(contract, f"the Task states no matrix id the reuse check can use: {ids}")
    )
    output: Path = run.context.work / "build" / str(run.step["id"]) / REVIEW_FILE
    write_json(output, document)
    return Completion(artifacts=(file_artifact(REVIEW, output),), add=(StepGroup((consumer,)),))
