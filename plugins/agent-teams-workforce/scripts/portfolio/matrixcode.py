"""The verified flag of the matrix, and the one command that sets it.

``verified`` holds one field, ``commit``. It is set on the architecture and relationships an
Epic's Stories built once all of the Tasks of all of the Stories of the Epic have been built and
tested, including CI/CD and CDK, with the deployment working. The driver runs ``verify`` when
GitHub reports a Story's pull request merged, which is after the Story's Tasks closed and its
deploy to AWS dev was verified, and before the Story itself closes. The call sets the flag only
when that merge completes the Epic: every Task of the Epic is closed and every other Story of the
Epic is closed. The commit is the merge commit of that last Story. Before then the call records
nothing and reports what is still open. Absent means not verified; no other value exists.

The flag is recorded on each stack and entry the Epic's Stories built, as the Task script's
``built`` read returns them for each Story (``matrixtasks.built``), and on each relationship a
build proves that starts at one of them. :func:`verify` takes no stack, entry or repository name.
One of them that carries another Epic's approved change, which this build did not build, is left
not verified (:func:`unbuilt_change`), so that the next spec for it covers all the work.

No session writes the flag. The driver records it through ``atw-matrix verify``, which runs
:func:`record_verified`.
"""

import sys
from collections.abc import Mapping, Sequence
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
from matrixtasks import BuiltEntry, BuiltRead, EpicWork, TaskBead, built, epic_work

COMMAND_VERIFY: Final = "verify"


class EpicVerified(TypedDict):
    """What verifying after a Story's merge recorded: also what ``verify`` prints."""

    command: str
    story: str
    epic: str
    commit: str
    complete: bool
    """Whether the Story's merge completes the Epic, so that the flag was set."""
    openStories: list[str]
    """The other Stories of the Epic that are not closed; the flag waits for them."""
    openTasks: list[str]
    """The Tasks of the Epic that are not closed; the flag waits for them."""
    entries: list[EntryId]
    """Each stack and entry the Epic's Stories built, which now carries the flag; empty when not complete."""
    relationships: list[dict[str, JsonValue]]
    """Each relationship that starts at one of them, with the flag."""
    unbuiltEntries: list[EntryId]
    """Each stack and entry the Epic's Stories built that carries another Epic's unbuilt change, left not verified."""
    unbuiltRelationships: list[dict[str, JsonValue]]
    """Each relationship that starts at an entry built and carries another Epic's unbuilt change, left not verified."""
    changed: int
    """How many entries and relationships took the flag, had its commit replaced or had it cleared."""
    unmatched: list[str]
    """The ids the Epic's Tasks carry that are the id of no entry, so nothing was marked for them."""


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
    """Say whether an entry or a relationship an Epic built carries another Epic's approved, unbuilt change.

    It does when its verified flag names another Epic in ``changedBy``: that Epic's change was
    approved after the commit the flag holds and is not yet built. It does too when it carries no
    verified flag and carries another Epic's approved flag: that Epic's approval came after this
    Epic's, or this Epic's approval never reached it, and with no flag the matrix cannot show that
    the approval changed nothing. A verified flag with no ``changedBy``, or naming this Epic,
    under another Epic's approved flag means that Epic approved it unchanged, since a change
    clears the approved flag and ``matrixwrite.approve`` then names the changing Epic. When this
    returns True the build does not match the approved version, so the item is not verified and
    the next spec for it covers all the work.

    Args:
        item: The entry or relationship as held.
        epic: The beads id of the Epic whose Stories built it.

    Returns:
        True when another Epic's approved change is not built in it.

    """
    changed_elsewhere: bool = item.verified is not None and item.verified.changed_by not in {None, epic}
    approved_elsewhere: bool = item.verified is None and item.approved is not None and item.approved.epic != epic
    return changed_elsewhere or approved_elsewhere


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def verify(
    matrix: Matrix,
    reads: Sequence[BuiltRead],
    commit: str,
    epic: str,
) -> Verification:
    """Set the verified flag on what an Epic's Stories built.

    Each stack and entry the ``built`` reads return takes the flag with the commit, and so does
    every relationship, of any kind and either side, that starts at one of them: the
    architecture and relationships of the Epic are verified together. A flag already there has
    its commit replaced and loses ``changedBy``. An entry or relationship that carries another
    Epic's approved, unbuilt change (:func:`unbuilt_change`) is left not verified instead: a flag
    it carries is cleared. Nothing else changes: an entry a read lists as not built, and an id
    that matches no entry, are left as they are.

    Args:
        matrix: The matrix, changed in place.
        reads: What each Story of the Epic built (``matrixtasks.built``).
        commit: The merge commit of the Story whose merge completed the Epic.
        epic: The beads id of the Epic.

    Returns:
        What carries the flag at the commit, what was left not verified, and how many entries
        and relationships the call changed.

    Raises:
        MatrixRefusedError: No commit is given.

    """
    sha: str = commit.strip()
    if not sha:
        message: str = "verify needs the merge commit"
        raise MatrixRefusedError(message)
    mark: Verified = Verified(commit=sha)
    rows: list[BuiltEntry] = [row for read in reads for row in (*read["stacks"], *read["entries"])]
    found: Verification = Verification([], [], [], [], 0)
    changed: int = 0
    entry_id: EntryId
    for entry_id in sorted({row["id"] for row in rows}):
        entry: Entry = matrix.entry(entry_id)
        flag: Verified | None = None if unbuilt_change(entry, epic) else mark
        (found.entries if flag else found.unbuilt_entries).append(entry_id)
        if entry.verified != flag:
            matrix.put(replace(entry, verified=flag))
            changed += 1
        relationship: Relationship
        for relationship in matrix.outgoing(entry_id):
            held: Verified | None = None if unbuilt_change(relationship, epic) else mark
            settled: Relationship = replace(relationship, verified=held)
            (found.relationships if held else found.unbuilt_relationships).append(relationship_json(settled))
            if relationship.verified != held:
                matrix.link(settled)
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
) -> EpicVerified:
    """Record, after a Story's merge, the verified flag of its Epic when the merge completes the Epic.

    The Epic, its Stories and every Task are read from beads before the lock is taken. The merge
    completes the Epic when every Task of the Epic is closed and every Story of the Epic other
    than this one is closed. Then what every Story of the Epic built is matched against the matrix
    under the lock and takes the flag, except what carries another Epic's approved, unbuilt
    change, which is left not verified (:func:`verify`). Otherwise nothing is written and the open Stories and Tasks
    are returned. A role that may not run ``verify``, beads that cannot be read, or a matrix that
    is missing or does not conform raises ``MatrixError``; the file is then left as it was.

    Args:
        path: The matrix file.
        story: The merged Story's beads id.
        commit: The merge commit of the Story's pull request.
        role: Who records it.
        control: The control repository, whose beads database holds the Epic, its Stories and
            Tasks; None reads the one the driver's environment names.

    Returns:
        Whether the merge completed the Epic, what is still open, and what took the flag.

    Raises:
        MatrixRefusedError: No Story or no commit is given.

    """
    require_role(COMMAND_VERIFY, role)
    if not story.strip() or not commit.strip():
        message: str = "verify needs the Story's beads id and the merge commit"
        raise MatrixRefusedError(message)
    work: EpicWork = epic_work(story, control)
    mine: list[TaskBead] = [task for task in work.tasks if task.epic == work.epic]
    open_stories: list[str] = sorted(
        held for held, closed in work.stories.items() if not closed and held != story.strip()
    )
    open_tasks: list[str] = sorted(task.id for task in mine if not task.closed)
    result: EpicVerified = {
        "command": COMMAND_VERIFY,
        "story": story.strip(),
        "epic": work.epic,
        "commit": commit.strip(),
        "complete": not open_stories and not open_tasks,
        "openStories": open_stories,
        "openTasks": open_tasks,
        "entries": [],
        "relationships": [],
        "unbuiltEntries": [],
        "unbuiltRelationships": [],
        "changed": 0,
        "unmatched": [],
    }
    if not result["complete"]:
        return result

    def change(matrix: Matrix) -> EpicVerified:
        reads: list[BuiltRead] = [built(matrix, mine, held) for held in sorted(work.stories)]
        found: Verification = verify(matrix, reads, commit, work.epic)
        unmatched: list[str] = sorted({row["id"] for read in reads for row in read["unmatched"]})
        return {
            **result,
            "entries": found.entries,
            "relationships": found.relationships,
            "unbuiltEntries": found.unbuilt_entries,
            "unbuiltRelationships": found.unbuilt_relationships,
            "changed": found.changed,
            "unmatched": unmatched,
        }

    return update_matrix(path, change, wait=DEFAULT_LOCK_WAIT)
