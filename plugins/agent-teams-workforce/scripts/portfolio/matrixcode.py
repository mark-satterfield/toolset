"""The verified mark: the one code mark of the matrix, and the one command that sets it.

``verified`` holds one field, ``commit``. It is set when a Story's code has been built and tested
and has passed, including its CI/CD and its CDK: the driver sets it when GitHub reports the
Story's pull request merged, and the commit is the merge commit. Absent means not verified; no
other value exists. When verified code is changed by a later Story the mark stays, with its
commit, until that Story is verified and replaces the commit.

The mark is recorded on each stack and entry the Story built, as the Task script's ``built`` read
returns them (``matrixtasks.built``), and on each relationship a build proves that starts at one
of them. :func:`verify` takes no stack, entry or repository name.

No session writes the mark. The driver records it through :func:`record_verified`, which it loads
from this file by path; ``atw-matrix verify`` runs the same code.
"""

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    BUILD_PROVED_KINDS,
    Entry,
    EntryId,
    JsonValue,
    Relationship,
    Role,
    Verified,
    relationship_json,
)
from matrixstore import DEFAULT_LOCK_WAIT, Matrix, MatrixRefusedError, matrix_path, require_role, update_matrix
from matrixtasks import BuiltEntry, BuiltRead, TaskBead, built, read_tasks

COMMAND_VERIFY: Final = "verify"


class StoryVerified(TypedDict):
    """What verifying a Story recorded: also what ``verify`` prints."""

    command: str
    story: str
    commit: str
    entries: list[EntryId]
    """Each stack and entry the Story built, which now carries the mark at the commit."""
    relationships: list[dict[str, JsonValue]]
    """Each relationship a build proves that starts at one of them, with the mark at the commit."""
    changed: int
    """How many entries and relationships took the mark or had its commit replaced."""
    unmatched: list[str]
    """The ids the Story's Tasks carry that are the id of no entry, so nothing was marked for them."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def verify(matrix: Matrix, read: BuiltRead, commit: str) -> StoryVerified:
    """Set the verified mark on what a Story built.

    Each stack and entry the ``built`` read returns takes the mark with the commit, and so does
    each relationship a build proves (the kinds the registry declares ``provedByBuild``) that
    starts at one of them. A mark already there has its commit replaced. Nothing else changes: an
    entry the read lists as not built, and an id that matches no entry, are left as they are.

    Args:
        matrix: The matrix, changed in place.
        read: What the Story built (``matrixtasks.built``).
        commit: The merge commit of the Story's pull request.

    Returns:
        The entries and relationships that carry the mark at the commit, how many of them the
        call changed, and the unmatched ids of the read.

    Raises:
        MatrixRefusedError: No commit is given.

    """
    sha: str = commit.strip()
    if not sha:
        message: str = "verify needs the merge commit"
        raise MatrixRefusedError(message)
    mark: Verified = Verified(commit=sha)
    rows: list[BuiltEntry] = [*read["stacks"], *read["entries"]]
    marked: list[EntryId] = sorted({row["id"] for row in rows})
    proved: list[dict[str, JsonValue]] = []
    changed: int = 0
    entry_id: EntryId
    for entry_id in marked:
        entry: Entry = matrix.entry(entry_id)
        if entry.verified != mark:
            matrix.put(replace(entry, verified=mark))
            changed += 1
        relationship: Relationship
        for relationship in matrix.outgoing(entry_id, BUILD_PROVED_KINDS):
            if relationship.verified != mark:
                matrix.link(replace(relationship, verified=mark))
                changed += 1
            proved.append(relationship_json(replace(relationship, verified=mark)))
    return {
        "command": COMMAND_VERIFY,
        "story": read["story"],
        "commit": sha,
        "entries": marked,
        "relationships": proved,
        "changed": changed,
        "unmatched": [unmatched["id"] for unmatched in read["unmatched"]],
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def matrix_file(environ: Mapping[str, str]) -> Path:
    """Name the matrix file the driver records in.

    Args:
        environ: The driver's environment.

    Returns:
        The file the matrix variable names, else the matrix of the control repository the
        environment names. An environment that names neither raises ``MatrixError``.

    """
    return matrix_path(None, environ)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_verified(
    path: Path,
    story: str,
    commit: str,
    role: Role,
    control: Path | None = None,
) -> StoryVerified:
    """Record a verified Story in a matrix file, as one locked change.

    The Story's Tasks are read from beads before the lock is taken; what they built is matched
    against the matrix under the lock. A role that may not run ``verify``, beads that cannot be
    read, or a matrix that is missing or does not conform raises ``MatrixError``; the file is then
    left as it was.

    Args:
        path: The matrix file.
        story: The Story's beads id.
        commit: The merge commit of the Story's pull request.
        role: Who records it.
        control: The control repository, whose beads database holds the Tasks; None reads the
            one the driver's environment names.

    Returns:
        What :func:`verify` recorded.

    Raises:
        MatrixRefusedError: No Story or no commit is given.

    """
    require_role(COMMAND_VERIFY, role)
    if not story.strip() or not commit.strip():
        message: str = "verify needs the Story's beads id and the merge commit"
        raise MatrixRefusedError(message)
    beads: list[TaskBead] = read_tasks(control)

    def change(matrix: Matrix) -> StoryVerified:
        return verify(matrix, built(matrix, beads, story), commit)

    return update_matrix(path, change, wait=DEFAULT_LOCK_WAIT)
