"""The script step that promotes reviewed architecture: approval, lifecycle, and the two commits.

It promotes by rule: when no review returned a finding, or the lead recorded that every item is
resolved. It marks the reviewed rows and headings approved in the matrix, sets the reviewed
documents effective in the vault, commits and pushes the vault when a document changed, and
commits the matrix file. Anything else is a failure with a structured cause.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import BASIS_REVIEWED, LIFECYCLE_EFFECTIVE, Matrix, ReviewScope, validate_review_scope
from matrixreview import Approved, approve
from matrixstore import Stamp, matrix_path, timestamp, update_matrix
from matrixsync import set_lifecycle, vault_root

from orchestrator.core import step_journal
from orchestrator.core.io import write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, file_artifact, value_artifact
from orchestrator.flows.architecture_files import (
    APPROVE,
    ARCHITECTURE_FOLDER,
    LABEL_SCOPE,
    ROLE_LEAD,
    ArchitectureContext,
    ArchitectureStepError,
    agents_with_role,
    checked_file,
    lead_resolved,
    read_context,
)
from orchestrator.flows.architecture_review import ALTERNATIVES, FINDINGS

if TYPE_CHECKING:
    from step_journal_contract import Artifact, Journal, Step, StepId

APPROVED_ITEMS: Final = "approved items"
VAULT_COMMIT: Final = "vault commit"
MATRIX_COMMIT: Final = "matrix commit"
BRANCH: Final = "main"
REMOTE: Final = "origin"


def _approve(run: StepRun, steps: list[StepId], arch: Path) -> Approved:
    """Mark approved what is in review for the Epic, as ``atw-matrix approve`` does.

    Returns:
        What was approved, what remains, the coverage and the documents made effective; each
        of those documents is set effective in the vault in the same matrix change.

    """
    stamp: Stamp = Stamp(timestamp(), f"{run.bead} approve")

    def change(matrix: Matrix) -> Approved:
        result: Approved = approve(matrix, run.bead, steps, BASIS_REVIEWED, stamp)
        if result["promoted"]:
            vault: Path = vault_root(arch)
            path: str
            for path in result["promoted"]:
                set_lifecycle(vault, path, LIFECYCLE_EFFECTIVE)
        return result

    return update_matrix(matrix_path(None, os.environ), change)


def _commit(run: StepRun, repository: Path, paths: list[str], message: str, *, push: bool) -> str | None:
    """Commit named paths of one repository, and push when asked.

    Only the named paths are staged and committed. With ``push``, the branch is pushed when
    this call made a commit or an earlier one was left unpushed.

    Returns:
        The commit this call made or pushed, or None when the paths held nothing to commit and
        nothing was left to push.

    """
    run.tools.git(repository, ["add", "-A", "--", *paths], stage=APPROVE)
    staged: str = run.tools.command(
        ["git", "diff", "--cached", "--name-only", "--", *paths],
        stage=APPROVE,
        cwd=repository,
    ).stdout.strip()
    commit: str | None = None
    if staged:
        run.tools.git(repository, ["commit", "-q", "-m", message, "--", *paths], stage=APPROVE)
        commit = run.tools.command(["git", "rev-parse", "HEAD"], stage=APPROVE, cwd=repository).stdout.strip()
    if push:
        ahead = run.tools.command(
            ["git", "rev-list", "--count", f"{REMOTE}/{BRANCH}..HEAD"],
            stage=APPROVE,
            cwd=repository,
            check=False,
        )
        if commit is not None or (ahead.exit == 0 and ahead.stdout.strip() != "0"):
            run.tools.git(repository, ["push", REMOTE, BRANCH], stage=APPROVE)
            commit = run.tools.command(["git", "rev-parse", "HEAD"], stage=APPROVE, cwd=repository).stdout.strip()
    return commit


def _require_resolved(run: StepRun) -> None:
    """Refuse to promote while a finding or a request for alternatives is not resolved.

    Raises:
        ArchitectureStepError: A review raised something and no lead before this step records
            that every item is resolved.

    """
    raised: bool = any(run.inputs.values(FINDINGS)) or any(run.inputs.values(ALTERNATIVES))
    lead: str = agents_with_role(run.tools.plugin, ROLE_LEAD)[0]
    if raised and lead_resolved(run, lead) is not True:
        raise ArchitectureStepError(
            run,
            "a review returned a finding or asked for alternatives, and no lead records that every item is resolved",
        )


def _scope_documents(run: StepRun) -> list[str]:
    """List the documents the review scope of this promotion names.

    The check step that planned the promotion recorded the scope. Naming its documents again
    lets a promotion that was interrupted after the approval still commit and push them.

    Returns:
        The documents with an unapproved heading when the review was opened; none when no step
        recorded a scope for this promotion.

    """
    planned: str = step_journal.planned_for_name(run.step["id"])
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        if not any(held["name"] == planned for held in step["artifacts"]):
            continue
        for held in step["artifacts"]:
            if held["name"] == LABEL_SCOPE and held["kind"] != "value":
                scope: ReviewScope = checked_file(run, Path(held["path"]), validate_review_scope)
                return [listed["document"] for listed in scope["headings"]]
    return []


@script_step(APPROVE)
def promote(run: StepRun) -> Completion:
    """Promote the reviewed documents and mark them approved.

    Returns:
        The approved items file, and the vault commit and the matrix commit when one was made.

    Raises:
        ArchitectureStepError: Something in review could not be approved; the file of approved
            items names each and the reason.

    """
    _require_resolved(run)
    context: ArchitectureContext = read_context(run)
    arch: Path = Path(context["architectureRoot"])
    journal: Journal = run.journal()
    named: list[Step] = [step_journal.find_step(journal, step_id) for step_id in run.step.get("inputs", [])]
    reviews: list[StepId] = [step["id"] for step in named if "agent" in step]
    approved: Approved = run.tools.portfolio(APPROVE, _approve, run, reviews, arch)
    path: Path = run.context.work / ARCHITECTURE_FOLDER / "approved.json"
    write_json(path, approved)
    artifacts: list[Artifact] = [file_artifact(APPROVED_ITEMS, path)]
    documents: list[str] = sorted({
        *approved["promoted"],
        *(anchor["document"] for anchor in approved["headings"]),
        *_scope_documents(run),
    })
    if documents:
        vault: Path = run.tools.portfolio(APPROVE, vault_root, arch)
        made: str | None = _commit(
            run,
            vault,
            documents,
            f"docs(architecture): approve the reviewed architecture of {run.bead}",
            push=True,
        )
        if made is not None:
            artifacts.append(value_artifact(VAULT_COMMIT, made))
    matrix: Path = matrix_path(None, os.environ)
    recorded: str | None = _commit(
        run,
        matrix.parent,
        [matrix.name],
        f"chore(matrix): record the approved architecture of {run.bead}",
        push=False,
    )
    if recorded is not None:
        artifacts.append(value_artifact(MATRIX_COMMIT, recorded))
    if approved["remaining"]:
        raise ArchitectureStepError(
            run,
            f"{len(approved['remaining'])} items in review could not be approved; see {path}",
            *(f"{left['id']}: {left['reason']}" for left in approved["remaining"]),
        )
    return Completion(artifacts=tuple(artifacts))
