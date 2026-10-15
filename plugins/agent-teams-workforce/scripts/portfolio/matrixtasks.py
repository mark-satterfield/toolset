"""The Task script: what the Task beads say about the entries of the matrix.

The matrix holds no Story and no Task; beads is the authority for both. A Task states what it
builds in the matrix's ids, under its ``matrix_elements`` key. This module reads the Task beads
through ``bd`` (:func:`read_tasks`), matches the ids they carry against the matrix's entries and
stores nothing. It answers three questions, each one ``atw-matrix`` command:

- :func:`built` (``built --story``): the stacks and entries a Story built, for the verified mark.
- :func:`work` (``work --id``): the open Tasks that name an entry or, for a stack, an entry the
  stack holds.
- :func:`affected` (``affected --id``): the open Tasks a change to an entry affects.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
import beadgraph
import beads_contract
from matrix_contract import (
    HOME_RELATIONSHIP,
    KIND_STACK,
    VERIFIABLE_KINDS,
    Entry,
    EntryId,
    EntryKind,
    MatrixError,
    Side,
)
from matrixstore import Matrix, MatrixRefusedError

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from bead_metadata import BuildContract
    from contracts import JsonObject

COMMAND_BUILT: Final = "built"
COMMAND_WORK: Final = "work"
COMMAND_AFFECTED: Final = "affected"
TASK_TYPE: Final = "task"
"""The beads issue type of a Task."""
STORY_TYPE: Final = "story"
"""The beads issue type of a Story."""


@dataclass(frozen=True, slots=True)
class TaskBead:
    """One Task as beads holds it, reduced to what the three questions need."""

    id: str
    title: str
    status: str
    closed: bool
    story: str | None
    """The nearest Story above the Task; None when it has none."""
    epic: str | None
    """The nearest Epic above the Task; None when it has none."""
    elements: tuple[str, ...]
    """The ids the Task's ``matrix_elements`` key carries, in the order stated."""


class VerifiedMark(TypedDict):
    """The verified mark, as a command prints it."""

    commit: str


class BuiltEntry(TypedDict):
    """One entry of the matrix that a Story's Tasks name."""

    id: EntryId
    kind: EntryKind
    name: str
    side: Side
    """Which side the entry came from: the architecture, or what is in a repository today."""
    verified: NotRequired[VerifiedMark]
    tasks: list[str]
    """The Tasks of the Story that name the entry."""


class UnmatchedId(TypedDict):
    """One id a Task carries that is the id of no entry."""

    id: str
    tasks: list[str]


class BuiltRead(TypedDict):
    """What a Story built: also what ``built --story`` prints."""

    command: str
    story: str
    tasks: list[str]
    """Every Task of the Story, whatever its status."""
    stacks: list[BuiltEntry]
    entries: list[BuiltEntry]
    """The entries, other than stacks, of the kinds that carry the verified mark."""
    notBuilt: list[BuiltEntry]
    """Entries the Tasks name of a kind no build produces, such as a shared capability a Task uses."""
    unmatched: list[UnmatchedId]


class TaskRow(TypedDict):
    """One open Task that names an entry a read asked about."""

    task: str
    title: str
    status: str
    story: str | None
    epic: str | None
    names: list[EntryId]
    """The entries asked about that the Task names."""


class TasksRead(TypedDict):
    """The open Tasks that touch an entry: also what ``work --id`` and ``affected --id`` print."""

    command: str
    id: EntryId
    entries: list[EntryId]
    """Every entry the Tasks were matched against: the entry asked about and what the read adds to it."""
    notEpic: NotRequired[str]
    tasks: list[TaskRow]


def read_tasks(control: Path | None = None) -> list[TaskBead]:
    """Read every Task from beads, with its Story, its Epic and the ids it carries.

    One ``bd list`` call reads the tracker (``beadgraph.load``), and the ids come from each
    record through ``beads_contract.read_contract``, the one reader of the build contract.

    Args:
        control: The control repository, whose beads database holds the Tasks; None reads the
            one the driver's environment names.

    Returns:
        The Tasks, closed ones included, in id order.

    Raises:
        MatrixError: Beads could not be read, or a Task's metadata is not readable.

    """
    message: str
    try:
        graph: beadgraph.Graph = beadgraph.load(control)
    except beadgraph.GraphError as error:
        message = f"cannot read the Task beads: {error}"
        raise MatrixError(message) from error
    tasks: list[TaskBead] = []
    record: JsonObject
    for record in graph.records:
        bead: beadgraph.Bead = beadgraph.bead_of(record)
        if bead.kind != TASK_TYPE:
            continue
        try:
            contract: BuildContract = beads_contract.read_contract(record)
        except ValueError as error:
            message = f"cannot read the metadata of the Task {bead.id}: {error}"
            raise MatrixError(message) from error
        ancestors: list[beadgraph.Bead] = graph.ancestors(bead.id)
        epic: beadgraph.Bead | None = graph.epic_of(bead.id)
        tasks.append(
            TaskBead(
                id=bead.id,
                title=bead.title,
                status=bead.status,
                closed=bead.closed,
                story=next((ancestor.id for ancestor in ancestors if ancestor.kind == STORY_TYPE), None),
                epic=None if epic is None else epic.id,
                elements=tuple(dict.fromkeys(contract.get("matrix_elements", []))),
            ),
        )
    return sorted(tasks, key=lambda task: task.id)


def _row(entry: Entry, tasks: Sequence[str]) -> BuiltEntry:
    """Render one entry a Story's Tasks name.

    Returns:
        The entry's id, kind, name and side, its verified mark when it has one, and the Tasks.

    """
    row: BuiltEntry = {
        "id": entry.id,
        "kind": entry.kind,
        "name": entry.name,
        "side": entry.side,
        "tasks": sorted(tasks),
    }
    if entry.verified is not None:
        row["verified"] = {"commit": entry.verified.commit}
    return row


def built(matrix: Matrix, tasks: Sequence[TaskBead], story: str) -> BuiltRead:
    """List the stacks and entries a Story built, from the ids its Tasks carry.

    Args:
        matrix: The matrix.
        tasks: The Task beads (:func:`read_tasks`).
        story: The Story's beads id.

    Returns:
        The Story's Tasks; the stacks and the other entries of a kind that carries the verified
        mark that they name; the entries they name of any other kind; and each id that is the id
        of no entry, under ``unmatched``. Each list is in id order.

    Raises:
        MatrixRefusedError: No Story is named.

    """
    wanted: str = story.strip()
    if not wanted:
        message: str = "built needs the Story's beads id"
        raise MatrixRefusedError(message)
    naming: dict[str, list[str]] = {}
    mine: list[TaskBead] = [task for task in tasks if task.story == wanted]
    task: TaskBead
    for task in mine:
        named: str
        for named in task.elements:
            naming.setdefault(named, []).append(task.id)
    read: BuiltRead = {
        "command": COMMAND_BUILT,
        "story": wanted,
        "tasks": sorted(task.id for task in mine),
        "stacks": [],
        "entries": [],
        "notBuilt": [],
        "unmatched": [],
    }
    for named in sorted(naming):
        entry: Entry | None = matrix.find(EntryId(named))
        if entry is None:
            read["unmatched"].append({"id": named, "tasks": sorted(naming[named])})
        elif entry.kind == KIND_STACK:
            read["stacks"].append(_row(entry, naming[named]))
        elif entry.kind in VERIFIABLE_KINDS:
            read["entries"].append(_row(entry, naming[named]))
        else:
            read["notBuilt"].append(_row(entry, naming[named]))
    return read


def _open_naming(tasks: Sequence[TaskBead], wanted: Collection[EntryId], not_epic: str | None) -> list[TaskRow]:
    """Find the open Tasks that name any of some entries.

    Returns:
        One row per open Task that names at least one of the entries, in Task id order, leaving
        out the Tasks of ``not_epic`` when one is given.

    """
    rows: list[TaskRow] = []
    task: TaskBead
    for task in sorted(tasks, key=lambda held: held.id):
        if task.closed or (not_epic is not None and task.epic == not_epic):
            continue
        names: list[EntryId] = sorted(entry_id for entry_id in wanted if entry_id in task.elements)
        if names:
            rows.append({
                "task": task.id,
                "title": task.title,
                "status": task.status,
                "story": task.story,
                "epic": task.epic,
                "names": names,
            })
    return rows


def work(matrix: Matrix, tasks: Sequence[TaskBead], entry_id: EntryId, not_epic: str | None = None) -> TasksRead:
    """List the open Tasks that name an entry or, for a stack, an entry the stack holds.

    An id the matrix holds no entry for raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        tasks: The Task beads (:func:`read_tasks`).
        entry_id: The entry asked about.
        not_epic: The beads id of an Epic whose own Tasks are left out, which gives the open
            work from other Epics; None leaves none out.

    Returns:
        The entries matched against and the open Tasks that name one, each with its Story and
        its Epic.

    Raises:
        MatrixRefusedError: ``not_epic`` is given and is empty.

    """
    if not_epic is not None and not not_epic.strip():
        message: str = "work was given an empty Epic id to leave out"
        raise MatrixRefusedError(message)
    entry: Entry = matrix.entry(entry_id)
    wanted: set[EntryId] = {entry.id}
    if entry.kind == KIND_STACK:
        wanted.update(relationship.start for relationship in matrix.incoming(entry.id, (HOME_RELATIONSHIP,)))
    left_out: str | None = None if not_epic is None else not_epic.strip()
    read: TasksRead = {
        "command": COMMAND_WORK,
        "id": entry.id,
        "entries": sorted(wanted),
        "tasks": _open_naming(tasks, wanted, left_out),
    }
    if left_out is not None:
        read["notEpic"] = left_out
    return read


def affected(
    matrix: Matrix,
    tasks: Sequence[TaskBead],
    entry_id: EntryId,
    impacted: Collection[EntryId],
) -> TasksRead:
    """List the open Tasks a change to an entry affects.

    An id the matrix holds no entry for raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        tasks: The Task beads (:func:`read_tasks`).
        entry_id: The entry that changes.
        impacted: The id of every entry ``impact --id`` returns for the entry.

    Returns:
        The entries matched against (the entry and what the impact read returned) and the open
        Tasks that name one, each with its Story and its Epic.

    """
    entry: Entry = matrix.entry(entry_id)
    wanted: set[EntryId] = {entry.id, *impacted}
    return {
        "command": COMMAND_AFFECTED,
        "id": entry.id,
        "entries": sorted(wanted),
        "tasks": _open_naming(tasks, wanted, None),
    }
