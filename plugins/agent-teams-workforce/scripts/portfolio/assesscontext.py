#!/usr/bin/env python3
"""The material one item's dependency assessment reads: one Epic, or one Task.

An Epic's assessing session reads the Epic's own PRD in full, and is handed the other Epics the
matrix relates it to (``related --epic``), each with its PRD file and what the two share. An Epic
no feature serves yet is also handed the requirements and features of other Epics that share
words with its own requirements (``find --kinds requirement,feature``). The named PRDs are then
read in full; nothing is copied out of the vault.

A Task created outside elaboration is assessed from the ids it states: the open Tasks that name
its stack or an entry the stack holds (``work --id``), what the stack depends on (``deps --of``)
and what depends on it (``deps --on``).

Either session also needs every edge already standing between the item and another open bead of
its level, whichever way it points, with the reason recorded for it, because it must keep or
withdraw each owned one with a reason that answers the recorded one.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
import beadgraph
from bead_metadata import KEY_ELABORATION_STATE
from beadgraph import Graph
from edgeset import (
    EdgeWithdrawal,
    StandingEdge,
    standing_edges,
    withdrawal_history,
)
from matrix_contract import (
    KIND_DOCUMENT,
    KIND_EPIC,
    KIND_FEATURE,
    KIND_REQUIREMENT,
    KIND_STACK,
    Entry,
    EntryId,
    EntryKind,
)
from matrixquery import (
    DepsView,
    EpicView,
    Match,
    RelatedEpic,
    Shared,
    deps_view,
    epic_view,
    find,
    related_view,
)
from matrixstore import Matrix
from matrixtasks import TaskBead, TasksRead, work
from matrixtraverse import epic_id

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from beadgraph import Bead

_ARGUMENT_ERROR: Final = "Arguments violate the assesscontext input contract"
ATTR_PRD: Final = "prd"
"""The attribute of an epic entry that holds its PRD."""
ATTR_PRD_PATH: Final = "path"
"""The member of ``prd`` that holds the PRD's path, relative to the vault root."""
SIMILAR_KINDS: Final[tuple[EntryKind, ...]] = (KIND_REQUIREMENT, KIND_FEATURE)
"""The kinds searched for an Epic no feature serves yet."""
DECISION_KINDS: Final[frozenset[EntryKind]] = frozenset((KIND_FEATURE, KIND_DOCUMENT))
"""The kinds of shared entry a related Epic is handed with: the entries that state decisions.

The stacks, services, components and infrastructure two Epics both reach are build facts, and
every open Epic reaches nearly all of them through the code, so they name no candidate.
"""


class AssessedEpic(TypedDict):
    """The Epic an assessment reads, with its PRD file."""

    id: str
    title: str
    fingerprint: str
    elaborationState: str | None
    prdPath: str | None
    """The PRD file in the vault, absolute; None when the matrix names none for the Epic."""


class RelatedPrd(TypedDict):
    """One other Epic the matrix relates to the Epic assessed."""

    epic: str
    """The related Epic's beads id."""
    title: str
    prdPath: str | None
    """Its PRD file in the vault, absolute; None when the matrix names none."""
    shared: list[Shared]
    """Each feature and document both Epics reach, with how each reaches it."""


class EpicContextSummary(TypedDict):
    """The counts of one Epic's assessment context."""

    epic: str
    related: int
    similar: int
    standing: int
    withdrawn: int
    owned: int
    handMade: int


class EpicContext(TypedDict):
    """The `assess-context` result for one Epic."""

    epic: AssessedEpic
    related: list[RelatedPrd]
    similar: list[Match]
    """For an Epic no feature serves: other Epics' requirements and features that share its words."""
    standing: list[StandingEdge]
    withdrawn: list[EdgeWithdrawal]
    summary: EpicContextSummary


class AssessedTask(TypedDict):
    """The Task an assessment reads, with the ids it states."""

    id: str
    title: str
    fingerprint: str
    epic: str | None
    elements: list[str]
    """The ids the Task's ``matrix_elements`` key carries."""
    stacks: list[EntryId]
    """The stacks the Task states, and the stacks that hold the entries it states."""
    unmatched: list[str]
    """The ids the Task states that are the id of no entry of the matrix."""


class StackContext(TypedDict):
    """What the matrix and the open Tasks say about one stack a Task states."""

    stack: EntryId
    work: TasksRead
    """The open Tasks that name the stack or an entry it holds."""
    dependsOn: DepsView
    dependents: DepsView


class TaskContextSummary(TypedDict):
    """The counts of one Task's assessment context."""

    task: str
    stacks: int
    openTasks: int
    standing: int
    owned: int
    handMade: int
    withdrawn: int


class TaskContext(TypedDict):
    """The `assess-context --task` result for one Task."""

    task: AssessedTask
    stacks: list[StackContext]
    standing: list[StandingEdge]
    withdrawn: list[EdgeWithdrawal]
    summary: TaskContextSummary


def _prd_file(entry: Entry | None, vault: Path) -> str | None:
    """Locate the PRD file an epic entry names.

    Returns:
        The file's absolute path; None when there is no entry or it names no PRD.

    """
    if entry is None:
        return None
    prd: object = entry.attributes.get(ATTR_PRD)
    if not isinstance(prd, dict):
        return None
    relative: object = prd.get(ATTR_PRD_PATH)
    return str(vault / relative) if isinstance(relative, str) and relative else None


def prd_paths(matrix: Matrix, vault: Path, epics: Iterable[str]) -> dict[str, str]:
    """Locate the PRD file of each Epic, as the matrix names it.

    Args:
        matrix: The matrix.
        vault: The vault root every recorded PRD path is relative to.
        epics: The Epics' beads ids.

    Returns:
        Epic beads id -> its PRD file, absolute. An Epic the matrix holds no entry for, or names
        no PRD for, is left out.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(matrix, Matrix) or not isinstance(vault, Path):
        raise TypeError(_ARGUMENT_ERROR)
    paths: dict[str, str] = {}
    bead: str
    for bead in epics:
        if not isinstance(bead, str):
            raise TypeError(_ARGUMENT_ERROR)
        located: str | None = _prd_file(matrix.find(epic_id(bead)), vault)
        if located is not None:
            paths[bead] = located
    return paths


def _bead_of(entry_id: str) -> str:
    """Read the beads id out of an epic entry's id.

    Returns:
        What follows ``epic:``.

    """
    return entry_id.removeprefix(f"{KIND_EPIC}:")


def _related(matrix: Matrix, vault: Path, related: Sequence[RelatedEpic]) -> list[RelatedPrd]:
    """Render the Epics related to the one assessed, each with its PRD file.

    Returns:
        One row per related Epic with the features and documents both reach, those sharing the
        most first, then in the order the matrix returned them.

    """
    rows: list[RelatedPrd] = []
    other: RelatedEpic
    for other in related:
        entry_id: object = other["epic"].get("id")
        name: object = other["epic"].get("name")
        if not isinstance(entry_id, str):
            continue
        bead: str = _bead_of(entry_id)
        rows.append({
            "epic": bead,
            "title": name if isinstance(name, str) else "",
            "prdPath": _prd_file(matrix.find(epic_id(bead)), vault),
            "shared": [shared for shared in other["shared"] if shared["entry"].get("kind") in DECISION_KINDS],
        })
    return sorted(rows, key=lambda row: -len(row["shared"]))


def _similar(matrix: Matrix, bead: Bead, view: EpicView) -> list[Match]:
    """Find other Epics' requirements and features that share words with an Epic no feature serves.

    Returns:
        The ranked matches, leaving out the Epic's own requirements; none when a feature already
        serves one of its requirements, since ``related`` then answers.

    """
    own: set[str] = {str(requirement["requirement"].get("id")) for requirement in view["requirements"]}
    if len(view["noFeature"]) < len(own):
        return []
    names: list[str] = [str(requirement["requirement"].get("name") or "") for requirement in view["requirements"]]
    text: str = " ".join([bead.title, *names]).strip()
    if not text:
        return []
    return [
        match for match in find(matrix, text, kinds=SIMILAR_KINDS)["matches"] if match["entry"].get("id") not in own
    ]


def _held(graph: Graph, bead_id: str, what: str) -> Bead:
    """Read one bead the assessment is about.

    Returns:
        The bead.

    Raises:
        ValueError: The tracker holds no bead with that id.

    """
    bead: Bead | None = graph.beads.get(bead_id)
    if bead is None:
        message: str = f"assess-context: the tracker holds no {what} {bead_id}"
        raise ValueError(message)
    return bead


def assess_context(graph: Graph, matrix: Matrix, epic: str, vault: Path) -> EpicContext:
    """Return the Epic, the Epics the matrix relates it to, and its standing edges.

    An Epic the matrix holds no entry for raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        graph: The tracker graph, read with descriptions.
        matrix: The matrix.
        epic: The Epic to be assessed.
        vault: The vault root every recorded PRD path is relative to.

    Returns:
        `epic` (`{id, title, fingerprint, elaborationState, prdPath}`), `related` (each other
        Epic that reaches what this one reaches, with its PRD file and what is shared),
        `similar` (for an Epic no feature serves, the requirements and features of other Epics
        that share its words), `standing` (every edge between the Epic and another open Epic,
        from `edgeset.standing_edges`), `withdrawn` (every edge touching it that an assessment
        withdrew, with the reason, from `edgeset.withdrawal_history`), and a `summary` of counts.

    A tracker that holds no bead with the Epic's id raises ``ValueError`` from ``_held``.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not isinstance(graph, Graph)
        or not isinstance(matrix, Matrix)
        or not isinstance(epic, str)
        or not isinstance(vault, Path)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    bead: Bead = _held(graph, epic, "Epic")
    view: EpicView = epic_view(matrix, epic)
    related: list[RelatedPrd] = _related(matrix, vault, related_view(matrix, epic)["related"])
    similar: list[Match] = _similar(matrix, bead, view)
    prints: dict[str, str] = beadgraph.fingerprints(graph.records, beadgraph.SCOPE_JUDGING)
    standing: list[StandingEdge] = standing_edges(graph, epic)
    withdrawn: list[EdgeWithdrawal] = withdrawal_history(graph, epic)
    owned: int = sum(1 for edge in standing if edge["owned"])
    return {
        "epic": {
            "id": bead.id,
            "title": bead.title,
            "fingerprint": prints.get(bead.id, ""),
            "elaborationState": bead.metadata.get(KEY_ELABORATION_STATE),
            "prdPath": _prd_file(matrix.find(epic_id(epic)), vault),
        },
        "related": related,
        "similar": similar,
        "standing": standing,
        "withdrawn": withdrawn,
        "summary": {
            "epic": bead.id,
            "related": len(related),
            "similar": len(similar),
            "standing": len(standing),
            "withdrawn": len(withdrawn),
            "owned": owned,
            "handMade": len(standing) - owned,
        },
    }


def _stated_stacks(matrix: Matrix, elements: Sequence[str]) -> tuple[list[EntryId], list[str]]:
    """Find the stacks a Task states, from the ids it carries.

    Returns:
        The stacks named and the stacks that hold the entries named, in id order, and the ids
        that are the id of no entry.

    """
    stacks: set[EntryId] = set()
    unmatched: list[str] = []
    stated: str
    for stated in elements:
        entry: Entry | None = matrix.find(EntryId(stated))
        if entry is None:
            unmatched.append(stated)
            continue
        home: EntryId | None = entry.id if entry.kind == KIND_STACK else matrix.home(entry.id, side=None)
        if home is not None:
            stacks.add(home)
    return sorted(stacks), unmatched


def task_context(graph: Graph, matrix: Matrix, tasks: Sequence[TaskBead], task: str) -> TaskContext:
    """Return the Task, what the matrix says about each stack it states, and its standing edges.

    Args:
        graph: The tracker graph, read with descriptions.
        matrix: The matrix.
        tasks: The Task beads with the ids each carries (`matrixtasks.read_tasks`).
        task: The Task to be assessed: open, and not written by elaboration.

    Returns:
        `task` (`{id, title, fingerprint, epic, elements, stacks, unmatched}`), `stacks` (for
        each stack the Task states: the open Tasks that name it or an entry it holds, what it
        depends on and what depends on it), `standing` (every edge between the Task and another
        open Task, from `edgeset.standing_edges`), `withdrawn` (every edge touching it that an
        assessment withdrew, with the reason, from `edgeset.withdrawal_history`), and a
        `summary` of counts. A Task that states no id has no stacks.

    A tracker that holds no bead with the Task's id raises ``ValueError`` from ``_held``.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(graph, Graph) or not isinstance(matrix, Matrix) or not isinstance(task, str):
        raise TypeError(_ARGUMENT_ERROR)
    bead: Bead = _held(graph, task, "Task")
    held: TaskBead | None = next((candidate for candidate in tasks if candidate.id == task), None)
    elements: list[str] = [] if held is None else list(held.elements)
    stack_ids: list[EntryId]
    unmatched: list[str]
    stack_ids, unmatched = _stated_stacks(matrix, elements)
    stacks: list[StackContext] = [
        {
            "stack": stack,
            "work": work(matrix, tasks, stack),
            "dependsOn": deps_view(matrix, stack),
            "dependents": deps_view(matrix, stack, inward=True),
        }
        for stack in stack_ids
    ]
    others: set[str] = {row["task"] for stack in stacks for row in stack["work"]["tasks"]} - {task}
    prints: dict[str, str] = beadgraph.fingerprints(graph.records, beadgraph.SCOPE_JUDGING)
    standing: list[StandingEdge] = standing_edges(graph, task, "task")
    withdrawn: list[EdgeWithdrawal] = withdrawal_history(graph, task, "task")
    owned: int = sum(1 for edge in standing if edge["owned"])
    epic: Bead | None = graph.epic_of(task)
    return {
        "task": {
            "id": bead.id,
            "title": bead.title,
            "fingerprint": prints.get(bead.id, ""),
            "epic": epic.id if epic else None,
            "elements": elements,
            "stacks": stack_ids,
            "unmatched": unmatched,
        },
        "stacks": stacks,
        "standing": standing,
        "withdrawn": withdrawn,
        "summary": {
            "task": bead.id,
            "stacks": len(stacks),
            "openTasks": len(others),
            "standing": len(standing),
            "owned": owned,
            "handMade": len(standing) - owned,
            "withdrawn": len(withdrawn),
        },
    }
