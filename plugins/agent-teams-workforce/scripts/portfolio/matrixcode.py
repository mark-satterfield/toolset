"""The verified mark of the matrix, and the one command that sets it.

The verified mark is a plain yes on an architecture entry or relationship: the architecture it is
part of was built and its test passed, the CI checks and the test that its CDK deployment works
included; the deployment need not remain. It records nothing about who or which commit. The driver
runs ``verify`` when a Story completes its build pipeline. An item with contributing work in
another unfinished Story remains unverified. A feature is verified only when its recorded
architecture realizers are verified; missing realization evidence never implies completion.

The mark is recorded on each stack and entry the Story built, as the Task script's ``built`` read
returns them (``matrixtasks.built``), and on each relationship, of any kind and either side, that
starts at one of them. :func:`verify` takes no stack, entry or repository name, and leaves the
approved mark as it is. A later change to what an item must be built as clears its mark
(``matrixstore.Matrix.put`` and ``Matrix.link``), and the next build and test of the item sets it
again.

No session writes the mark. The driver records it through ``atw-matrix verify``, which runs
:func:`record_verified`.
"""

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final, NamedTuple, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    AUTHORITY_SIDE,
    KIND_FEATURE,
    REL_REALIZED_BY,
    Entry,
    EntryId,
    JsonValue,
    Relationship,
    Role,
    relationship_json,
)
from matrixstore import DEFAULT_LOCK_WAIT, Matrix, MatrixRefusedError, matrix_path, require_role, update_matrix
from matrixtasks import BuiltEntry, BuiltRead, EpicWork, built, epic_work

COMMAND_VERIFY: Final = "verify"


class StoryVerified(TypedDict):
    """What verifying one Story's tested build recorded: also what ``verify`` prints."""

    command: str
    story: str
    entries: list[EntryId]
    """Each stack and entry the Story built, which now carries the verified mark."""
    relationships: list[dict[str, JsonValue]]
    """Each relationship that starts at one of them, with the mark."""
    changed: int
    """How many entries and relationships took the mark."""
    unmatched: list[str]
    """The ids the Story's Tasks carry that are the id of no entry, so nothing was marked for them."""


class Verification(NamedTuple):
    """What :func:`verify` set."""

    entries: list[EntryId]
    """The stacks and entries that carry the mark."""
    relationships: list[dict[str, JsonValue]]
    """The relationships that carry the mark."""
    changed: int
    """How many entries and relationships the call changed."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def verify(matrix: Matrix, read: BuiltRead) -> Verification:
    """Set the verified mark on what one Story built and tested.

    Each stack and entry the ``built`` read returns takes the mark, and so does every
    relationship, of any kind and either side, that starts at one of them. Only the verified mark
    changes: the approved mark and everything else are left as they are, and an entry the read
    lists as not built, and an id that matches no entry, are not touched.

    Args:
        matrix: The matrix, changed in place.
        read: What the Story built (``matrixtasks.built``).

    Returns:
        What carries the mark, and how many entries and relationships the call changed.

    """
    rows: list[BuiltEntry] = [*read["stacks"], *read["entries"]]
    entries: list[EntryId] = sorted({row["id"] for row in rows})
    relationships: list[dict[str, JsonValue]] = []
    changed: int = 0
    entry_id: EntryId
    for entry_id in entries:
        entry: Entry = matrix.entry(entry_id)
        if not entry.verified:
            matrix.set_flags(replace(entry, verified=True))
            changed += 1
        relationship: Relationship
        for relationship in matrix.outgoing(entry_id):
            settled: Relationship = replace(relationship, verified=True)
            relationships.append(relationship_json(settled))
            if not relationship.verified:
                matrix.set_flags(settled)
                changed += 1
    return Verification(entries, relationships, changed)


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
    role: Role,
    control: Path | None = None,
) -> StoryVerified:
    """Record the verified mark on what one Story built, when its test has passed.

    The Story's Tasks are read from beads before the lock is taken. Then what the Story's Tasks
    state they built is matched against the matrix under the lock and takes the mark
    (:func:`verify`). The call is safe to run again: a mark already set is left as it is. A role
    that may not run ``verify``, beads that cannot be read, or a matrix that is missing or does not
    conform raises ``MatrixError``; the file is then left as it was.

    Args:
        path: The matrix file.
        story: The Story's beads id.
        role: Who records it.
        control: The control repository, whose beads database holds the Story, its Epic and its
            Tasks; None reads the one the driver's environment names.

    Returns:
        What took the mark, and the ids that matched no entry.

    Raises:
        MatrixRefusedError: No Story is given.

    """
    require_role(COMMAND_VERIFY, role)
    if not story.strip():
        message: str = "verify needs the Story's beads id"
        raise MatrixRefusedError(message)
    work: EpicWork = epic_work(story, control)

    def change(matrix: Matrix) -> StoryVerified:
        read: BuiltRead = built(matrix, work.tasks, story)
        pending: set[str] = {
            element
            for task in work.tasks
            if not task.closed or (task.story != story and not work.stories.get(task.story or "", False))
            for element in task.elements
        }
        read["stacks"] = [row for row in read["stacks"] if row["id"] not in pending]
        read["entries"] = [row for row in read["entries"] if row["id"] not in pending]
        found: Verification = verify(matrix, read)
        completed: set[EntryId] = set(found.entries)
        feature_changes: int = 0
        feature: Entry
        for feature in matrix.entries((KIND_FEATURE,)):
            realizers: list[EntryId] = [
                link.end for link in matrix.outgoing(feature.id, (REL_REALIZED_BY,)) if link.side == AUTHORITY_SIDE
            ]
            if feature.side != AUTHORITY_SIDE or not completed.intersection(realizers) or feature.id in pending:
                continue
            if realizers and all(
                (entry := matrix.find(realizer)) is not None
                and entry.side == AUTHORITY_SIDE
                and entry.verified
                and realizer not in pending
                for realizer in realizers
            ):
                if not feature.verified:
                    matrix.set_flags(replace(feature, verified=True))
                    feature_changes += 1
                completed.add(feature.id)
        return {
            "command": COMMAND_VERIFY,
            "story": story.strip(),
            "entries": sorted(completed),
            "relationships": found.relationships,
            "changed": found.changed + feature_changes,
            "unmatched": sorted(row["id"] for row in read["unmatched"]),
        }

    return update_matrix(path, change, wait=DEFAULT_LOCK_WAIT)
