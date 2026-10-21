"""The verified flag of the matrix, and the one command that sets it.

``verified`` holds one field, ``commit``: the commit of the Story's branch whose test passed. It
says the entry or relationship was built and tested, the CI checks and the test that its CDK
deployment works included; the deployment need not remain. The driver runs ``verify`` for one
Story when that Story's test passes: its deploy to AWS dev was verified working and the CI checks
on its branch pass. The test passing is the trigger: the call runs before, and apart from, any
merge, and waits for no other Story or Task of any Epic. Absent means not verified; no other value
exists.

The flag is recorded on each stack and entry the Story built, as the Task script's ``built`` read
returns them (``matrixtasks.built``), and on each relationship, of any kind and either side, that
starts at one of them. It belongs to the item and holds for every Epic that relates to it.
:func:`verify` takes no stack, entry or repository name, and leaves the approved flag as it is. One
of them that carries another Epic's approved change this build did not build is left not verified
(:func:`unbuilt_change`), so that the next spec for it covers that change. A later change to what
an item must be built as clears its flag (``matrixstore.Matrix.put`` and ``Matrix.link``), and the
next build and test of the item sets it again.

No session writes the flag. The driver records it through ``atw-matrix verify``, which runs
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
    Entry,
    EntryId,
    JsonValue,
    Relationship,
    Role,
    Verified,
    relationship_json,
)
from matrixstore import DEFAULT_LOCK_WAIT, Matrix, MatrixRefusedError, matrix_path, require_role, update_matrix
from matrixtasks import BuiltEntry, BuiltRead, EpicWork, built, epic_work

COMMAND_VERIFY: Final = "verify"


class StoryVerified(TypedDict):
    """What verifying one Story's tested build recorded: also what ``verify`` prints."""

    command: str
    story: str
    epic: str
    commit: str
    entries: list[EntryId]
    """Each stack and entry the Story built, which now carries the flag at the commit."""
    relationships: list[dict[str, JsonValue]]
    """Each relationship that starts at one of them, with the flag."""
    unbuiltEntries: list[EntryId]
    """Each stack and entry the Story built that carries another Epic's unbuilt change, left not verified."""
    unbuiltRelationships: list[dict[str, JsonValue]]
    """Each relationship that starts at an entry built and carries another Epic's unbuilt change, left not verified."""
    changed: int
    """How many entries and relationships took the flag, had its commit replaced or had it cleared."""
    unmatched: list[str]
    """The ids the Story's Tasks carry that are the id of no entry, so nothing was marked for them."""


class Verification(NamedTuple):
    """What :func:`verify` set and left not verified."""

    entries: list[EntryId]
    """The stacks and entries that carry the flag at the commit."""
    relationships: list[dict[str, JsonValue]]
    """The relationships that carry the flag at the commit."""
    unbuilt_entries: list[EntryId]
    """The stacks and entries left not verified (:func:`unbuilt_change`)."""
    unbuilt_relationships: list[dict[str, JsonValue]]
    """The relationships left not verified (:func:`unbuilt_change`)."""
    changed: int
    """How many entries and relationships the call changed."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def unbuilt_change(item: Entry | Relationship, epic: str) -> bool:
    """Say whether an entry or a relationship a Story built carries another Epic's approved, unbuilt change.

    A change to what an item must be built as clears its verified flag, so an item that still
    carries the flag has not changed since it was last built and tested, whoever approved it since.
    An item with no verified flag that carries the approved flag of an Epic other than the
    building Story's was approved after that Epic's architecture, which this build was specified
    from, and the matrix cannot show that the approval changed nothing it must be built as. When
    this returns True the build does not match the approved version, so the item is not verified and
    the next spec for it covers all the work.

    Args:
        item: The entry or relationship as held.
        epic: The beads id of the Epic of the Story that built it.

    Returns:
        True when another Epic's approved change may not be built in it.

    """
    return item.verified is None and item.approved is not None and item.approved.epic != epic


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def verify(matrix: Matrix, read: BuiltRead, commit: str, epic: str) -> Verification:
    """Set the verified flag on what one Story built and tested.

    Each stack and entry the ``built`` read returns takes the flag with the commit, and so does
    every relationship, of any kind and either side, that starts at one of them. A flag already
    there has its commit replaced. An entry or relationship that carries another Epic's approved,
    unbuilt change (:func:`unbuilt_change`) is left not verified instead. Only the verified flag
    changes: the approved flag and everything else are left as they are, and an entry the read
    lists as not built, and an id that matches no entry, are not touched.

    Args:
        matrix: The matrix, changed in place.
        read: What the Story built (``matrixtasks.built``).
        commit: The commit of the Story's branch whose test passed.
        epic: The beads id of the Story's Epic.

    Returns:
        What carries the flag at the commit, what was left not verified, and how many entries
        and relationships the call changed.

    Raises:
        MatrixRefusedError: No commit is given.

    """
    sha: str = commit.strip()
    if not sha:
        message: str = "verify needs the commit whose test passed"
        raise MatrixRefusedError(message)
    mark: Verified = Verified(commit=sha)
    rows: list[BuiltEntry] = [*read["stacks"], *read["entries"]]
    found: Verification = Verification([], [], [], [], 0)
    changed: int = 0
    entry_id: EntryId
    for entry_id in sorted({row["id"] for row in rows}):
        entry: Entry = matrix.entry(entry_id)
        flag: Verified | None = None if unbuilt_change(entry, epic) else mark
        (found.entries if flag else found.unbuilt_entries).append(entry_id)
        if flag is not None and entry.verified != flag:
            matrix.set_flags(replace(entry, verified=flag))
            changed += 1
        relationship: Relationship
        for relationship in matrix.outgoing(entry_id):
            held: Verified | None = None if unbuilt_change(relationship, epic) else mark
            settled: Relationship = replace(relationship, verified=held) if held is not None else relationship
            (found.relationships if held else found.unbuilt_relationships).append(relationship_json(settled))
            if held is not None and relationship.verified != held:
                matrix.set_flags(settled)
                changed += 1
    return found._replace(changed=changed)


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
    """Record the verified flag on what one Story built, when its test has passed.

    The Story's Epic and Tasks are read from beads before the lock is taken. Then what the
    Story's Tasks state they built is matched against the matrix under the lock and takes the
    flag, except what carries another Epic's approved, unbuilt change, which is left not verified
    (:func:`verify`). The call is safe to run again: a flag already at the commit is left as it is.
    A role that may not run ``verify``, beads that cannot be read, or a matrix that is missing or
    does not conform raises ``MatrixError``; the file is then left as it was.

    Args:
        path: The matrix file.
        story: The Story's beads id.
        commit: The commit of the Story's branch whose test passed: its CI checks and the test
            that its CDK deployment works.
        role: Who records it.
        control: The control repository, whose beads database holds the Story, its Epic and its
            Tasks; None reads the one the driver's environment names.

    Returns:
        What took the flag, what was left not verified, and the ids that matched no entry.

    Raises:
        MatrixRefusedError: No Story or no commit is given.

    """
    require_role(COMMAND_VERIFY, role)
    if not story.strip() or not commit.strip():
        message: str = "verify needs the Story's beads id and the commit whose test passed"
        raise MatrixRefusedError(message)
    work: EpicWork = epic_work(story, control)

    def change(matrix: Matrix) -> StoryVerified:
        read: BuiltRead = built(matrix, work.tasks, story)
        found: Verification = verify(matrix, read, commit, work.epic)
        return {
            "command": COMMAND_VERIFY,
            "story": story.strip(),
            "epic": work.epic,
            "commit": commit.strip(),
            "entries": found.entries,
            "relationships": found.relationships,
            "unbuiltEntries": found.unbuilt_entries,
            "unbuiltRelationships": found.unbuilt_relationships,
            "changed": found.changed,
            "unmatched": sorted(row["id"] for row in read["unmatched"]),
        }

    return update_matrix(path, change, wait=DEFAULT_LOCK_WAIT)
