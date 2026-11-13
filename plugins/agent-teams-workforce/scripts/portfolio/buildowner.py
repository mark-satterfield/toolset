"""Build ownership across Epics: which Epic's Task builds a matrix entry, so no other Epic builds it again.

An entry of the matrix is built once. Among every Task of every Epic that builds the entry (any
status, closed included; :attr:`matrixtasks.TaskBead.builds`), the owner Task is the one whose
build started, else the earliest written, else the lowest id. Its Epic is the owner Epic. An item
of another Epic whose entry the owner Epic builds is not work for that Epic: it records the owner
Epic's Tasks under ``builtBy``, no Task has to cite it, and a Task that does builds only its
Epic's addition and is blocked by those Tasks. An Epic's own Tasks take part in the comparison, so
an Epic that owns an entry keeps it when it is elaborated again, and a Task that only adds to an
entry (``adds_to_entries``) never builds it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NotRequired, TypedDict

from contracts import BuiltBy

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from matrixtasks import TaskBead


class OwnedItem(TypedDict):
    """The part of a build item (``DeltaItem``) the ownership rule reads and writes."""

    id: str
    matrixId: NotRequired[str]
    requires: NotRequired[list[str]]
    builtBy: NotRequired[list[BuiltBy]]


@dataclass(frozen=True, slots=True)
class Builder:
    """One Task that builds an entry, with what the ownership rule compares."""

    task: str
    epic: str
    story: str | None
    status: str
    started: bool
    created: str
    spec_paths: tuple[str, ...]

    def row(self) -> BuiltBy:
        """Render the Task as a ``builtBy`` row.

        Returns:
            The row.

        """
        return {
            "task": self.task,
            "epic": self.epic,
            "story": self.story,
            "status": self.status,
            "started": self.started,
            "specPaths": list(self.spec_paths),
        }


type BuilderIndex = dict[str, list[Builder]]
"""Entry id -> every Task, of any Epic, that builds it, in Task id order."""


def builders(tasks: Sequence[TaskBead]) -> BuilderIndex:
    """Index every Task that belongs to an Epic by the entries it builds.

    Args:
        tasks: The Task beads (``matrixtasks.tasks_of``).

    Returns:
        Entry id -> the Tasks that build it, in Task id order; a Task under no Epic owns nothing.

    """
    index: BuilderIndex = {}
    for task in sorted((held for held in tasks if held.epic is not None), key=lambda held: held.id):
        found: Builder = Builder(
            task.id,
            str(task.epic),
            task.story,
            task.status,
            task.started,
            task.created,
            task.spec_paths,
        )
        for entry in task.builds:
            index.setdefault(entry, []).append(found)
    return index


def owner(found: Sequence[Builder]) -> Builder | None:
    """Choose the owner Task among the Tasks that build one entry.

    Returns:
        The Task whose build started, else the earliest written, else the lowest id; None when
        no Task builds the entry.

    """
    if not found:
        return None
    return min(found, key=lambda builder: (not builder.started, builder.created, builder.task))


def owner_epic(found: Sequence[Builder]) -> str | None:
    """Name the Epic that owns an entry.

    Returns:
        The owner Task's Epic, or None when no Task builds the entry.

    """
    chosen: Builder | None = owner(found)
    return None if chosen is None else chosen.epic


def built_by(index: BuilderIndex, entry_id: str, epic: str) -> list[BuiltBy]:
    """List the Tasks of another Epic that build an entry an Epic would build.

    Args:
        index: The builders (:func:`builders`).
        entry_id: The entry's matrix id.
        epic: The Epic asking.

    Returns:
        Every Task of the owner Epic that builds the entry, in Task id order; empty when no Task
        builds it or the owner Epic is ``epic``.

    """
    found: list[Builder] = index.get(entry_id, [])
    chosen: str | None = owner_epic(found)
    if chosen is None or chosen == epic:
        return []
    return [builder.row() for builder in found if builder.epic == chosen]


def mark_built_by[T: OwnedItem](items: Sequence[T], index: BuilderIndex, epic: str) -> list[str]:
    """Record on each item the Tasks of the Epic that owns its entry, when that is another Epic.

    Args:
        items: The Epic's build items; each gains ``builtBy`` (empty when this Epic builds it).
        index: The builders (:func:`builders`).
        epic: The Epic whose items these are.

    Returns:
        One sentence per started build of the same entry by an Epic that is neither this one nor
        the owner: two Epics built it, which only the owner can rule on. Information, never work.

    """
    duplicates: list[str] = []
    for item in items:
        stated: object = item.get("matrixId")
        entry: str = stated if isinstance(stated, str) else ""
        found: list[Builder] = index.get(entry, []) if entry else []
        item["builtBy"] = built_by(index, entry, epic) if entry else []
        chosen: str | None = owner_epic(found)
        duplicates.extend(
            f"{item['id']} ({entry}): {builder.task} of {builder.epic} also built it; the owner is {chosen}"
            for builder in found
            if builder.started and builder.epic not in {epic, chosen}
        )
    return duplicates


def _recorded_owner(item: OwnedItem) -> str | None:
    """Name the owner Epic an item recorded when it was marked.

    Returns:
        The Epic of its first ``builtBy`` row; None when it has none or never had the key.

    """
    rows: list[BuiltBy] = item.get("builtBy", [])
    return rows[0]["epic"] if rows else None


def ownership_drift(items: Sequence[OwnedItem], index: BuilderIndex, epic: str) -> list[str]:
    """Find the items whose owner Epic is no longer the one their ``builtBy`` records.

    An item marked before another Epic wrote a Task that owns its entry, or whose owner changed
    (a build started), was planned on a stale snapshot. An item that never had ``builtBy`` (its
    elements file was written before the rule) is read as owned by no other Epic.

    Args:
        items: The Epic's build items, as the span step wrote them.
        index: The builders, from a fresh read of beads.
        epic: The Epic whose items these are.

    Returns:
        One sentence per drifted item, naming it, its entry, the recorded and the current owner.

    """
    drifted: list[str] = []
    for item in items:
        entry: str = item.get("matrixId", "")
        if not entry:
            continue
        current: str | None = owner_epic(index.get(entry, []))
        now: str | None = None if current == epic else current
        recorded: str | None = _recorded_owner(item)
        if now != recorded:
            drifted.append(
                f"{item['id']} ({entry}) was planned as built by {recorded or 'this Epic'}, "
                f"and is now built by {now or 'this Epic'}",
            )
    return drifted


def owner_blockers(item_id: str, items: Mapping[str, OwnedItem]) -> list[str]:
    """Name the Tasks of other Epics a Task citing an item must wait for.

    Args:
        item_id: The item the Task cites.
        items: Every build item of the Epic, by id.

    Returns:
        The ``builtBy`` Tasks of the item and of each item it requires, each once, in order.

    """
    item: OwnedItem | None = items.get(item_id)
    if item is None:
        return []
    needed: list[OwnedItem] = [items[required] for required in item.get("requires", []) if required in items]
    return list(dict.fromkeys(row["task"] for owned in (item, *needed) for row in owned.get("builtBy", [])))
