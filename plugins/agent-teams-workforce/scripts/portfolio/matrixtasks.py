"""The Task script: what the Task beads say about the entries of the matrix.

The matrix holds no Story and no Task; beads is the authority for both. A Task states what it
builds in the matrix's ids, under its ``matrix_elements`` key. This module reads the Task beads
through ``bd`` (:func:`read_tasks`), matches the ids they carry against the matrix's entries and
stores nothing. It answers three questions, each one ``atw-matrix`` command:

- :func:`built` (``built --story``): the stacks and entries a Story built, for the verified flag.
- :func:`epic_work`: the Epic above a Story, with every Story and Task of that Epic and whether
  each is closed; ``verify`` reads the Story's Tasks from it.
- :func:`work` (``work --id``): the open Tasks that name an entry or, for a stack, an entry the
  stack holds; :func:`work_batch` (``work --ids``) answers it for several entries from one read
  of the tracker and the matrix.
- :func:`affected` (``affected --id``): the open Tasks a change to an entry affects.
"""

import json
import sys
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
import beadgraph
import beads_contract
import buildowner
from bead_metadata import BUILD_LIFECYCLE_KEYS, KEY_BUILDS_ENTRIES
from contracts import BuiltBy
from matrix_contract import (
    HOME_RELATIONSHIP,
    KIND_COMPONENT,
    KIND_EVENT,
    KIND_FILE,
    KIND_INFRASTRUCTURE,
    KIND_LAYER,
    KIND_PACKAGE,
    KIND_SERVICE,
    KIND_STACK,
    Entry,
    EntryId,
    EntryKind,
    MatrixError,
    Side,
)
from matrixstore import Matrix, MatrixRefusedError, as_entry_id, kind_of

if TYPE_CHECKING:
    from bead_metadata import BuildContract
    from contracts import JsonObject

COMMAND_BUILT: Final = "built"
COMMAND_WORK: Final = "work"
COMMAND_AFFECTED: Final = "affected"
COMMAND_BUILDERS: Final = "builders"
IN_PROGRESS: Final = "in_progress"
"""The beads status of a Task whose build is running."""
TASK_TYPE: Final = "task"
"""The beads issue type of a Task."""
STORY_TYPE: Final = "story"
"""The beads issue type of a Story."""
BUILT_KINDS: Final[frozenset[EntryKind]] = frozenset({
    KIND_SERVICE,
    KIND_COMPONENT,
    KIND_INFRASTRUCTURE,
    KIND_EVENT,
    KIND_PACKAGE,
    KIND_LAYER,
    KIND_FILE,
})
"""The kinds of entry, other than a stack, that a Task builds; any other id a Task names, such as a shared
capability it uses, is listed as not built."""
FALLBACK_BUILT_KINDS: Final[frozenset[EntryKind]] = BUILT_KINDS - {KIND_SERVICE}
"""The kinds of a ``matrix_elements`` id read as built by a Task that records no ``builds_entries``: a
service id there names the service the Task works in, never that the Task builds the whole service."""


@dataclass(frozen=True, slots=True)
class TaskBead:
    """One Task as beads holds it, reduced to what the three questions need."""

    id: str
    title: str
    status: str
    closed: bool
    story: str | None
    """The nearest Story above the Task; None when it has none."""
    story_closed: bool
    """Whether that Story is closed: its work has been delivered. False when the Task has no Story."""
    epic: str | None
    """The nearest Epic above the Task; None when it has none."""
    elements: tuple[str, ...]
    """The ids the Task's ``matrix_elements`` key carries, in the order stated."""
    created: str = ""
    """When the Task was written (its record's ``created_at``); empty when the record has none."""
    started: bool = False
    """Whether the Task's build started: it is closed, in progress, or carries a build lifecycle key."""
    builds: tuple[str, ...] = ()
    """The matrix ids of the entries the Task builds (:func:`built_entries`)."""
    spec_paths: tuple[str, ...] = ()
    """The spec paths the Task builds against."""


def built_entries(metadata: Mapping[str, str], elements: Sequence[str]) -> tuple[str, ...]:
    """Name the matrix entries a Task builds: the ownership record of the build-ownership rule.

    A Task elaboration wrote from 7.71.91 records them under ``builds_entries``. A Task without
    that key (written earlier, or outside elaboration) is read from its ``matrix_elements``: the
    ids of a kind :data:`FALLBACK_BUILT_KINDS` names, which leaves out its stack, the service it
    works in and the shared capabilities it uses.

    Args:
        metadata: The Task's metadata.
        elements: The ids its ``matrix_elements`` key carries.

    Returns:
        The entry ids, each once, in the order stated.

    Raises:
        MatrixError: ``builds_entries`` is not a JSON array of strings.

    """
    stated: str | None = metadata.get(KEY_BUILDS_ENTRIES)
    if stated is None:
        return tuple(dict.fromkeys(entry for entry in elements if _fallback_built(entry)))
    try:
        decoded: object = json.loads(stated or "[]")
    except json.JSONDecodeError as error:
        message: str = f"{KEY_BUILDS_ENTRIES} is not JSON: {error}"
        raise MatrixError(message) from error
    if not isinstance(decoded, list) or not all(isinstance(entry, str) for entry in decoded):
        message = f"{KEY_BUILDS_ENTRIES} is not a JSON array of strings"
        raise MatrixError(message)
    return tuple(dict.fromkeys(entry for entry in decoded if isinstance(entry, str)))


def _fallback_built(entry: str) -> bool:
    """Report whether a ``matrix_elements`` id names an entry a Task without ``builds_entries`` builds.

    Returns:
        True when the id's kind is in :data:`FALLBACK_BUILT_KINDS`; an id with no kind is not one.

    """
    try:
        return kind_of(as_entry_id(entry)) in FALLBACK_BUILT_KINDS
    except MatrixError:
        return False


def build_started(status: str, metadata: Mapping[str, str], *, closed: bool) -> bool:
    """Report whether a Task's build started: closed, in progress, or a build lifecycle key set.

    Returns:
        True when it started.

    """
    return closed or status == IN_PROGRESS or any(metadata.get(key) for key in BUILD_LIFECYCLE_KEYS)


@dataclass(frozen=True, slots=True)
class EpicWork:
    """The Epic above one Story, with every Story and Task of that Epic."""

    epic: str
    stories: Mapping[str, bool]
    """Every Story, by beads id, with whether its build completed and it closed."""
    tasks: tuple[TaskBead, ...]
    """Every Task, of any Epic, as :func:`read_tasks` reads them."""


class BuiltEntry(TypedDict):
    """One entry of the matrix that a Story's Tasks name."""

    id: EntryId
    kind: EntryKind
    name: str
    side: Side
    """Which side the entry came from: the architecture, or what is in a repository today."""
    verified: bool
    """Whether the entry carries the verified mark."""
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
    """The entries, other than stacks, of the kinds a build produces (``BUILT_KINDS``)."""
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


class WorkFailure(TypedDict):
    """One entry of a batch read that could not be answered, and why."""

    id: str
    error: str


class WorkBatch(TypedDict):
    """The open Tasks of several entries: also what ``work --ids`` prints."""

    command: str
    ids: list[str]
    """The ids asked about, each once, in the order given."""
    notEpic: NotRequired[str]
    reads: list[TasksRead]
    """One read per id that could be answered, as ``work --id`` prints it, in the order given."""
    failures: list[WorkFailure]
    """One per id that could not be answered; the other ids are answered all the same."""


class EntryBuilders(TypedDict):
    """Who builds one entry, by the build-ownership rule (``buildowner``)."""

    id: str
    ownerEpic: str | None
    """The Epic whose Task owns the entry; None when no Task builds it."""
    builtBy: list[BuiltBy]
    """The owner Epic's Tasks that build it; empty when it has no owner or the asking Epic owns it."""
    builders: list[BuiltBy]
    """Every Task, of any Epic, that builds it."""


class BuildersRead(TypedDict):
    """What ``builders --ids`` prints."""

    command: str
    epic: NotRequired[str]
    entries: list[EntryBuilders]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def entry_builders(tasks: Sequence[TaskBead], ids: Sequence[str], epic: str | None = None) -> BuildersRead:
    """Name, for each entry, the Epic that owns it and the Tasks that build it.

    Args:
        tasks: The Task beads (:func:`read_tasks`).
        ids: The entries asked about; a repeated id is answered once.
        epic: The Epic asking, whose own ownership empties ``builtBy``; None leaves it as the
            owner Epic's Tasks.

    Returns:
        One row per id, in the order given.

    Raises:
        MatrixRefusedError: No id is given.

    """
    wanted: list[str] = list(dict.fromkeys(stated.strip() for stated in ids if stated.strip()))
    if not wanted:
        message: str = "builders needs at least one entry id"
        raise MatrixRefusedError(message)
    index: buildowner.BuilderIndex = buildowner.builders(tasks)
    asking: str = (epic or "").strip()
    read: BuildersRead = {
        "command": COMMAND_BUILDERS,
        "entries": [
            {
                "id": entry,
                "ownerEpic": buildowner.owner_epic(index.get(entry, [])),
                "builtBy": buildowner.built_by(index, entry, asking),
                "builders": [builder.row() for builder in index.get(entry, [])],
            }
            for entry in wanted
        ],
    }
    if asking:
        read["epic"] = asking
    return read


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_tasks(control: Path | None = None) -> list[TaskBead]:
    """Read every Task from beads, with its Story, its Epic and the ids it carries.

    One ``bd list`` call reads the tracker (``beadgraph.load``), and the ids come from each
    record through ``beads_contract.read_contract``, the one reader of the build contract.

    Args:
        control: The control repository, whose beads database holds the Tasks; None reads the
            one the driver's environment names.

    Returns:
        The Tasks, closed ones included, in id order. Beads that cannot be read, or a Task whose
        metadata is not readable, raises ``MatrixError``.

    """
    return tasks_of(_load(control))


def _load(control: Path | None) -> beadgraph.Graph:
    """Read the tracker once.

    Returns:
        The beads graph.

    Raises:
        MatrixError: Beads could not be read.

    """
    try:
        return beadgraph.load(control)
    except beadgraph.GraphError as error:
        message: str = f"cannot read the Task beads: {error}"
        raise MatrixError(message) from error


def tasks_of(graph: beadgraph.Graph) -> list[TaskBead]:
    """Reduce every Task of a beads graph to what the questions need.

    A caller that already read the tracker hands its graph here instead of reading it again.

    Args:
        graph: The beads graph (``beadgraph.load``).

    Returns:
        The Tasks, closed ones included, in id order.

    Raises:
        TypeError: The graph is not a beads graph.
        MatrixError: A Task's metadata is not readable.

    """
    message: str
    if not isinstance(graph, beadgraph.Graph):
        message = "tasks_of needs a beads graph"
        raise TypeError(message)
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
        epic: beadgraph.Bead | None = graph.epic_of(bead.id)
        story: beadgraph.Bead | None = next(
            (ancestor for ancestor in graph.ancestors(bead.id) if ancestor.kind == STORY_TYPE),
            None,
        )
        elements: tuple[str, ...] = tuple(dict.fromkeys(contract.get("matrix_elements", [])))
        try:
            builds: tuple[str, ...] = built_entries(bead.metadata, elements)
        except MatrixError as error:
            message = f"cannot read what the Task {bead.id} builds: {error}"
            raise MatrixError(message) from error
        tasks.append(
            TaskBead(
                id=bead.id,
                title=bead.title,
                status=bead.status,
                closed=bead.closed,
                story=None if story is None else story.id,
                story_closed=story is not None and story.closed,
                epic=None if epic is None else epic.id,
                elements=elements,
                created=str(record.get("created_at") or ""),
                started=build_started(bead.status, bead.metadata, closed=bead.closed),
                builds=builds,
                spec_paths=tuple(contract.get("specPaths", [])),
            ),
        )
    return sorted(tasks, key=lambda task: task.id)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_work(story: str, control: Path | None = None) -> EpicWork:
    """Read the Epic above a Story, with every Story and Task of it, from one read of beads.

    Args:
        story: The Story's beads id.
        control: The control repository, whose beads database holds them; None reads the one
            the driver's environment names.

    Returns:
        The Epic, each of its Stories with whether it is closed, and every Task.

    Raises:
        MatrixRefusedError: The Story is not in beads, or has no Epic above it.

    """
    graph: beadgraph.Graph = _load(control)
    wanted: str = story.strip()
    message: str
    if wanted not in graph.beads:
        message = f"beads holds no Story {wanted!r}"
        raise MatrixRefusedError(message)
    epic: beadgraph.Bead | None = graph.epic_of(wanted)
    if epic is None:
        message = f"the Story {wanted} has no Epic above it"
        raise MatrixRefusedError(message)
    return EpicWork(
        epic=epic.id,
        stories={bead.id: bead.closed for bead in graph.beads.values() if bead.kind == STORY_TYPE},
        tasks=tuple(tasks_of(graph)),
    )


def _row(entry: Entry, tasks: Sequence[str]) -> BuiltEntry:
    """Render one entry a Story's Tasks name.

    Returns:
        The entry's id, kind, name and side, whether it carries the verified mark, and the Tasks.

    """
    row: BuiltEntry = {
        "id": entry.id,
        "kind": entry.kind,
        "name": entry.name,
        "side": entry.side,
        "verified": entry.verified,
        "tasks": sorted(tasks),
    }
    return row


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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
        elif entry.kind in BUILT_KINDS:
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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def work_batch(
    matrix: Matrix,
    tasks: Sequence[TaskBead],
    ids: Sequence[str],
    not_epic: str | None = None,
) -> WorkBatch:
    """List the open Tasks of several entries, each as :func:`work` lists them, from one read.

    The tracker and the matrix are read once by the caller; each id is answered on its own, so an
    id that is not an entry's is reported under ``failures`` and the others are answered.

    Args:
        matrix: The matrix.
        tasks: The Task beads (:func:`read_tasks`).
        ids: The entries asked about; a repeated id is answered once.
        not_epic: The beads id of an Epic whose own Tasks are left out of every read; None
            leaves none out.

    Returns:
        The ids asked about, one read per id answered and one failure per id that was not.

    Raises:
        MatrixRefusedError: No id is given, or ``not_epic`` is given and is empty.

    """
    message: str
    wanted: list[str] = list(dict.fromkeys(stated.strip() for stated in ids if stated.strip()))
    if not wanted:
        message = "work needs at least one entry id"
        raise MatrixRefusedError(message)
    if not_epic is not None and not not_epic.strip():
        message = "work was given an empty Epic id to leave out"
        raise MatrixRefusedError(message)
    left_out: str | None = None if not_epic is None else not_epic.strip()
    batch: WorkBatch = {"command": COMMAND_WORK, "ids": wanted, "reads": [], "failures": []}
    for stated in wanted:
        try:
            batch["reads"].append(work(matrix, tasks, as_entry_id(stated), left_out))
        except MatrixError as error:
            batch["failures"].append({"id": stated, "error": str(error)})
    if left_out is not None:
        batch["notEpic"] = left_out
    return batch


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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
