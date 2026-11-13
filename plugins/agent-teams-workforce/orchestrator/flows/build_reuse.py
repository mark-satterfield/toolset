"""The build's reuse audit: the deterministic reuse check, recorded as the review by script.

The matrix is a best guess, so every finding of this audit is a note: divergence between the code
and the matrix is never a build failure, starts no correction round and gives implementers no
work. The build corrects the matrix from the code after the commit (``build:matrix-follow``,
:mod:`orchestrator.flows.build_follow`). Re-implementing a shared component is a note too: the
owner's architecture constraints (arc42 section 2) hold no general rule that code must use shared
components, and the duplicate signals are the matrix's own guess.

``build:reuse-audit`` runs ``check-reuse`` (:func:`matrixreuse.check_reuse`) in process against the
matrix ids the Task states (its ``matrix_elements``) and the Story worktree, and records the review
itself, always; it starts no agent. A line that does itself what a shared capability provides, a
relied-on capability nothing references, stated ids the matrix does not hold, and each new
definition whose name reads like a provided behaviour (a candidate match) are notes in the review.
"""

from __future__ import annotations

import sys
from itertools import starmap
from pathlib import Path
from typing import TYPE_CHECKING, Final

from typeguard import check_type

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import KIND_FEATURE, Entry, EntryId, MatrixError
from matrixreuse import ReuseItem, ReuseResult, check_reuse
from matrixstore import Matrix, read_matrix
from matrixtraverse import holder

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, file_artifact, value_artifact
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import matrix_file
from orchestrator.flows.build_state import new_step, workspace_of

if TYPE_CHECKING:
    from step_journal_contract import Artifact

STAGE: Final = "build:reuse-audit"
REVIEW: Final = "reuseReview"
ELEMENTS: Final = "matrix_elements"
"""The bead field that holds the matrix ids the Task states."""
REVIEW_FILE: Final = "reuse-review.json"


def _item_text(item: ReuseItem) -> str:
    """Describe one finding of the check: where it is, what it is, and the capability it concerns.

    Returns:
        ``<file>:<line> <finding> <feature> <provides>: <detail>``, without the place when it has none.

    """
    file: str | None = item.get("file")
    line: int | None = item.get("line")
    place: str = "" if file is None else f"{file}:{line} " if line is not None else f"{file} "
    return f"{place}{item['finding']} {item['feature']} {item['provides']}: {item['detail']}"


def _finding(item: ReuseItem) -> dict[str, JsonValue]:
    """Turn one item the check found into a note.

    Returns:
        The note, with the item's file and line when it has them.

    """
    finding: dict[str, JsonValue] = {"severity": "note", "detail": _item_text(item)}
    if "file" in item:
        finding["file"] = item["file"]
    if "line" in item:
        finding["line"] = item["line"]
    return finding


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


def _recorded(run: StepRun, document: dict[str, JsonValue]) -> tuple[Artifact, ...]:
    """Write a review beside the step and record it as a reviewer's result is recorded.

    Returns:
        The review file, then its ``approved``, ``findings`` and ``evidence`` as values.

    """
    output: Path = run.context.work / "build" / str(run.step["id"]) / REVIEW_FILE
    write_json(output, document)
    return (file_artifact(REVIEW, output), *starmap(value_artifact, document.items()))


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
        The check's result, or None when no stated id is in the matrix; and a note naming the
        stated ids the matrix does not hold.

    Raises:
        StepError: The check could not read the worktree.

    """
    matrix: Matrix = read_matrix(matrix_file())
    unknown: list[EntryId] = _unknown(matrix, ids)
    contract: list[dict[str, JsonValue]] = (
        [
            {
                "severity": "note",
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
    """Turn what the check found into review findings.

    Returns:
        Each divergence, each candidate match and each relied-on behaviour with no use signal, as a note.

    """
    return [
        *(_finding(item) for item in result["violations"]),
        *(_finding(item) for item in result["judgment"]),
        *(_unchecked_note(unchecked) for unchecked in result["unchecked"]),
    ]


def _check_evidence(result: ReuseResult) -> str:
    """State what the check read and found.

    Returns:
        The files read, the capabilities checked and those left out as this repository's own, the
        divergence and the candidate matches.

    """
    provided: str = f" ({', '.join(result['provided'])} provided by this repository, not checked)"
    return (
        f"check-reuse read {len(result['files'])} changed file(s) against {len(result['capabilities'])} shared "
        f"capability(ies){provided if result['provided'] else ''}: {len(result['violations'])} divergence(s) "
        f"from the matrix's guess and {len(result['judgment'])} candidate match(es) of a new definition with a "
        "provided behaviour, recorded as notes"
    )


def _physical(entry: Entry) -> bool:
    """Tell whether an entry's name is the name its resource is deployed under.

    Returns:
        True for an entry that is not a feature and whose name holds no whitespace.

    """
    return entry.kind != KIND_FEATURE and bool(entry.name) and not any(character.isspace() for character in entry.name)


def own_outputs(run: StepRun) -> list[str]:
    """Name the resources the Task itself creates, from the ids it states in the matrix.

    Returns:
        The deployed name of each entry the Task states that is not a feature, and of each stack that
        holds one, without repeats; empty when the Task states no id the matrix holds.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    ids: list[str] = check_type(bead.get(ELEMENTS, []), list[str])
    if not ids:
        return []
    matrix: Matrix = read_matrix(matrix_file())
    stated: list[Entry] = [entry for entry in map(matrix.find, map(EntryId, ids)) if entry is not None]
    stacks: list[Entry | None] = [matrix.find(stack) for entry in stated if (stack := holder(matrix, entry.id))]
    return list(
        dict.fromkeys(entry.name for entry in [*stated, *stacks] if entry is not None and _physical(entry)),
    )


def audit(run: StepRun) -> Completion:
    """Check the changed files against the Task's shared capabilities and record the review.

    Args:
        run: The ``build:reuse-audit`` step.

    Returns:
        The review the step recorded, approved with every finding a note; then the consumer of the review.

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
    document: dict[str, JsonValue] = (
        _review([*contract, *_settled_findings(result)], _check_evidence(result))
        if result is not None
        else _review(contract, f"the Task states no matrix id the reuse check can use: {ids}")
    )
    return Completion(artifacts=_recorded(run, document), add=(StepGroup((consumer,)),))
