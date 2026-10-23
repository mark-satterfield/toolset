"""The script step that promotes approved architecture: lifecycle, the matrix's mirror of it, and the commits.

It follows the check step that passed the architect's result and its review log: the architect
reviews and approves its own architecture. First, under the matrix's lock, it compares what the
architect reviewed with what the matrix and the documents hold now (``architecture_collision``):
when another Epic changed or approved any of it, that is a missing ``tracks`` edge, and the step
changes nothing, sets this Epic's architecture back to its pack step so that it is reviewed again,
and fails this Epic only, with the cause ``missing-edge``. Otherwise it sets the documents this
Epic's document maintainers wrote effective in their front matter, files the Epic's review log in
the vault beside the architecture, brings the documents' matrix entries up to date so that each
mirrors its lifecycle, links the review log from the Epic's matrix entry, removes each
disagreement a document maintainer of this run corrected the losing statement of, sets the
approved flag on the Epic's approval scope (its reach by the rule of reach, in the corrected
matrix), commits and pushes those documents and the review log, and commits and pushes the
matrix file. Anything else is a failure
with a structured cause.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import validate_write_request, validate_write_result
from matrix_contract import KIND_DISAGREEMENT, KIND_DOCUMENT, ROLE_SCRIPT
from matrixstore import as_entry_id, make_id, read_matrix, update_matrix
from matrixsync import LIFECYCLE_EFFECTIVE, relative_path, set_lifecycle, sync_documents, vault_root
from matrixtraverse import epic_id
from matrixwrite import approve, commit
from step_journal_contract import STATUS_DONE

from orchestrator.core import step_journal
from orchestrator.core.io import write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, file_artifact, value_artifact
from orchestrator.flows.architecture_collision import Baseline, Collision, MissingEdgeError, baseline, collisions
from orchestrator.flows.architecture_files import (
    ARCHITECT,
    ARCHITECTURE,
    ARCHITECTURE_FOLDER,
    LABEL_REQUEST,
    PACK,
    PROMOTE,
    WRITE_REQUEST,
    WRITTEN,
    ArchitectureContext,
    ArchitectureStepError,
    checked_file,
    checked_output,
    held_file,
    matrix_file,
    read_context,
    read_result,
    written_documents,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from architecture_work_contract import ArchitectureResult, WriteRequest, WriteResult
    from matrix_contract import Entry, EntryId
    from matrixstore import Matrix
    from matrixwrite import ApproveResult, CommitResult
    from step_journal_contract import Artifact, Journal, Step, StepId

    from orchestrator.core.io import JsonValue

PROMOTED: Final = "promoted documents"
VAULT_COMMIT: Final = "vault commit"
MATRIX_COMMIT: Final = "matrix commit"
BRANCH: Final = "main"
REMOTE: Final = "origin"
ATTR_LIFECYCLE: Final = "lifecycle"
ATTR_STANDS: Final = "stands"
ATTR_REVIEW_LOG: Final = "reviewLog"
"""The Epic entry's attribute that links its review log (``matrix-kinds.json``)."""
REVIEW_LOGS: Final = "review-logs"
"""The folder under the architecture root that holds each Epic's review log, as ``<epic id>.json``."""


@dataclass(frozen=True)
class Promoted:
    """What one promotion did in the vault and in the matrix."""

    documents: tuple[str, ...]
    """The documents set effective, each by its path under the architecture root."""
    not_effective: tuple[str, ...]
    """Those of them whose matrix entry does not show the lifecycle effective afterwards."""
    removed: tuple[EntryId, ...]
    """The disagreements removed: settled, and the losing statement corrected in this run."""
    approved: tuple[EntryId, ...]
    """The entries the Epic reaches, which now carry the approved flag with the relationships between them."""
    review_log: str
    """The Epic's review log, by its path under the architecture root."""


def _file_review_log(bead: str, arch: Path, log: Path) -> tuple[str, str]:
    """Copy the Epic's review log into the vault, beside the architecture.

    Returns:
        The log's path under the architecture root, and the SHA-256 of its content.

    Raises:
        FileNotFoundError: The review log the check step passed is gone.

    """
    if not log.is_file():
        message: str = f"the review log {log} does not exist"
        raise FileNotFoundError(message)
    relative: str = f"{REVIEW_LOGS}/{bead}.json"
    target: Path = arch / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(log, target)
    return relative, hashlib.sha256(target.read_bytes()).hexdigest()


def _link_review_log(matrix: Matrix, bead: str, vault: Path, target: Path, digest: str) -> None:
    """Record the review log's path in the vault and its hash on the Epic's matrix entry."""
    epic: Entry = matrix.entry(epic_id(bead))
    linked: dict[str, JsonValue] = {"path": relative_path(target, vault), "hash": digest}
    matrix.put(replace(epic, attributes={**epic.attributes, ATTR_REVIEW_LOG: linked}))


def _promote(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - What one promotion is handed.
    bead: str,
    arch: Path,
    documents: Sequence[str],
    corrected: Sequence[str],
    log: Path,
    held: Baseline,
) -> Promoted:
    """Promote what the Epic reviewed, unless another Epic changed or approved it since.

    In one matrix change, under the matrix's lock: what the architect reviewed is compared with
    the matrix and the documents as they are now (``architecture_collision.collisions``), and a
    collision raises ``MissingEdgeError`` before anything is written. Otherwise each document this
    Epic's maintainers wrote that still exists is set effective in its front matter, the review log
    is copied into the vault, the entries of the written documents are brought up to date as
    ``atw-matrix sync-documents --paths`` does (a document that is gone loses its entry), the
    Epic's entry links the review log, each disagreement named that the matrix holds with a ruling
    is removed, and the Epic's approval scope gets the approved flag (``matrixwrite.approve``, as
    the script role).

    Args:
        bead: The Epic.
        arch: The architecture root inside the vault.
        documents: The documents this Epic's maintainers wrote, by their paths under the root.
        corrected: The ids of the disagreements whose losing statement a document maintainer of
            this run corrected.
        log: The Epic's review log, at the architecture context's ``reviewLogPath``.
        held: What the architect reviewed, to compare with.

    Returns:
        The documents set effective, those the matrix does not show as effective afterwards, the
        disagreements removed, the entries now approved, and where the review log was filed.

    """
    path: Path = matrix_file()
    vault: Path = vault_root(arch)
    present: list[str] = [relative for relative in documents if (arch / relative).is_file()]
    filed: list[str] = []

    def change(matrix: Matrix) -> tuple[list[EntryId], ApproveResult]:
        found: list[Collision] = collisions(matrix, bead, arch, documents, held)
        if found:
            raise MissingEdgeError(PROMOTE, bead, found)
        copied: str
        digest: str
        copied, digest = _file_review_log(bead, arch, log)
        filed.append(copied)
        relative: str
        for relative in present:
            set_lifecycle(vault, relative_path(arch / relative, vault), LIFECYCLE_EFFECTIVE)
        if documents:
            sync_documents(matrix, arch, paths=documents)
        _link_review_log(matrix, bead, vault, arch / copied, digest)
        removed: list[EntryId] = []
        stated: str
        for stated in dict.fromkeys(corrected):
            entry = matrix.find(as_entry_id(stated))
            if entry is not None and entry.kind == KIND_DISAGREEMENT and entry.attributes.get(ATTR_STANDS):
                matrix.remove(entry.id)
                removed.append(entry.id)
        return removed, approve(matrix, bead, ROLE_SCRIPT)

    removed: list[EntryId]
    approved: ApproveResult
    removed, approved = update_matrix(path, change)
    after: Matrix = read_matrix(path)
    not_effective: list[str] = []
    for relative in present:
        mirrored = after.find(make_id(KIND_DOCUMENT, relative))
        if mirrored is None or mirrored.attributes.get(ATTR_LIFECYCLE) != LIFECYCLE_EFFECTIVE:
            not_effective.append(relative)
    return Promoted(
        tuple(documents),
        tuple(not_effective),
        tuple(removed),
        tuple(approved["entries"]),
        filed[0],
    )


def _commit_vault(run: StepRun, vault: Path, paths: list[str], message: str) -> str | None:
    """Commit named paths of the vault and push them.

    Only the named paths are staged and committed. The branch is pushed when this call made a
    commit or an earlier one was left unpushed.

    Returns:
        The commit this call made or pushed, or None when the paths held nothing to commit and
        nothing was left to push.

    """
    run.tools.git(vault, ["add", "-A", "--", *paths], stage=PROMOTE)
    staged: str = run.tools.command(
        ["git", "diff", "--cached", "--name-only", "--", *paths],
        stage=PROMOTE,
        cwd=vault,
    ).stdout.strip()
    made: str | None = None
    if staged:
        run.tools.git(vault, ["commit", "-q", "-m", message, "--", *paths], stage=PROMOTE)
        made = run.tools.command(["git", "rev-parse", "HEAD"], stage=PROMOTE, cwd=vault).stdout.strip()
    ahead = run.tools.command(
        ["git", "rev-list", "--count", f"{REMOTE}/{BRANCH}..HEAD"],
        stage=PROMOTE,
        cwd=vault,
        check=False,
    )
    if made is not None or (ahead.exit == 0 and ahead.stdout.strip() != "0"):
        run.tools.git(vault, ["push", REMOTE, BRANCH], stage=PROMOTE)
        made = run.tools.command(["git", "rev-parse", "HEAD"], stage=PROMOTE, cwd=vault).stdout.strip()
    return made


def _review_again(run: StepRun) -> StepId | None:
    """Set this Epic's architecture back to its pack step, so that it is reviewed again from a new pack.

    The pack lists the matrix as it was; another Epic has changed it since, so the pack is
    assembled again, the TRD initial write updates the TRD from it and the architect reviews
    again. A journal with no pack step is set back to the architect's first step.

    Returns:
        The step set back to; None when the Architecture container holds neither.

    """
    container: Step = run.step_named(ARCHITECTURE)
    below: list[Step] = step_journal.steps_in_order_from(container)
    target: Step | None = next((step for step in below if step.get("script") == PACK), None) or next(
        (step for step in below if step.get("agent") == ARCHITECT),
        None,
    )
    if target is None:
        return None
    first: StepId = target["id"]

    def change(journal: Journal) -> None:
        step_journal.invalidate_from(journal, first, step_journal.timestamp())

    step_journal.update_journal(run.journal_path, change)
    return first


def _corrected(run: StepRun) -> list[str]:
    """List the disagreements whose losing statement a document maintainer of this run corrected.

    A done step that holds what a document maintainer wrote also holds the write request it was
    launched from. A settlement of that request is applied unless the result lists it among what
    was not written.

    Returns:
        The matrix ids of those disagreements, in journal order.

    """
    corrected: list[str] = []
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        written: Path | None = held_file(step, WRITTEN)
        asked: Path | None = held_file(step, WRITE_REQUEST, LABEL_REQUEST)
        if step["status"] != STATUS_DONE or written is None or asked is None:
            continue
        request: WriteRequest = checked_file(run, asked, validate_write_request)
        result: WriteResult = checked_output(run, written, validate_write_result, step)
        unapplied: list[str] = [left["entry"] for left in result["notApplied"]]
        corrected.extend(
            settlement["disagreement"]
            for settlement in request["settlements"]
            if not any(settlement["disagreement"] in entry for entry in unapplied)
        )
    return corrected


@script_step(PROMOTE)
def promote(run: StepRun) -> Completion:
    """Promote what the Epic reviewed, file the review log, mirror both in the matrix, and commit.

    The documents set effective and committed are exactly those this Epic's document maintainers
    wrote (``architecture_files.written_documents``), each staged by its path with the review log.

    Returns:
        The file of what was promoted, and the vault commit and the matrix commit when one was
        made or pushed.

    Raises:
        MissingEdgeError: Another Epic changed or approved what this Epic reviewed; nothing was
            approved or committed, and the architecture is set back to its pack step.
        ArchitectureStepError: The matrix does not show a promoted document as effective; the
            file of what was promoted names each.

    """
    context: ArchitectureContext = read_context(run)
    arch: Path = Path(context["architectureRoot"])
    result: ArchitectureResult = read_result(run, context)
    documents: list[str] = written_documents(run, arch)
    held: Baseline = baseline(run.context.work, str(run.bead), result)
    try:
        promoted: Promoted = run.tools.portfolio(
            PROMOTE,
            _promote,
            str(run.bead),
            arch,
            documents,
            _corrected(run),
            Path(context["reviewLogPath"]),
            held,
        )
    except MissingEdgeError as edge:
        again: StepId | None = _review_again(run)
        if again is not None:
            edge.add_note(f"the Epic's architecture is set back to step {again}, to be reviewed again")
        raise
    path: Path = run.context.work / ARCHITECTURE_FOLDER / "promoted.json"
    record: dict[str, JsonValue] = {
        "documents": [*promoted.documents],
        "notEffective": [*promoted.not_effective],
        "removedDisagreements": [*promoted.removed],
        "approved": [*promoted.approved],
        "reviewLog": promoted.review_log,
    }
    write_json(path, record)
    artifacts: list[Artifact] = [file_artifact(PROMOTED, path)]
    vault: Path = run.tools.portfolio(PROMOTE, vault_root, arch)
    made: str | None = _commit_vault(
        run,
        vault,
        [relative_path(arch / relative, vault) for relative in sorted({*promoted.documents, promoted.review_log})],
        f"docs(architecture): set the approved architecture of {run.bead} effective, with its review log",
    )
    if made is not None:
        artifacts.append(value_artifact(VAULT_COMMIT, made))
    recorded: CommitResult = run.tools.portfolio(PROMOTE, commit, matrix_file(), str(run.bead))
    if recorded["committed"] or recorded["pushed"]:
        artifacts.append(value_artifact(MATRIX_COMMIT, recorded["head"]))
    if promoted.not_effective:
        raise ArchitectureStepError(
            run,
            f"the matrix does not show {len(promoted.not_effective)} promoted documents as effective; see {path}",
            *promoted.not_effective,
        )
    return Completion(artifacts=tuple(artifacts))
