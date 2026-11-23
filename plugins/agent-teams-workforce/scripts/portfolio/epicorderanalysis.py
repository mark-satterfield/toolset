"""The result ``epicorder.py`` computes from the matrix, and what its report and summary read of it.

The command (``epicorder.py``) computes it and the report (``epicorderreport.py``) renders it; both
import it from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from matrix_contract import EntryId
    from matrixshared import SharedItem

type Pair = tuple[str, str]
"""An edge: the Epic that goes first, then the Epic that waits for it."""


@dataclass(frozen=True, slots=True)
class Epic:
    """One Epic the matrix holds."""

    id: str
    title: str
    release: str
    """The folder that holds the PRD's ``prds`` folder; empty when the Epic states no PRD there."""


@dataclass(frozen=True, slots=True)
class StandingEdge:
    """One dependency edge between two Epics in beads: ``blocked`` depends on ``blocker``."""

    blocker: str
    blocked: str
    kind: str


@dataclass(frozen=True, slots=True)
class Dropped:
    """One edge the loop break dropped, with the items that made it."""

    pair: Pair
    items: tuple[EntryId, ...]
    shared_only: bool
    """Whether only items judged ``shared`` made it."""


@dataclass(frozen=True, slots=True)
class Order:
    """The result: the edges before and after reduction, the dropped edges, levels and the longest chain."""

    raw: Mapping[Pair, tuple[EntryId, ...]]
    """The edges left after the loop break, before the reduction, each with the items that make it."""
    dropped: tuple[Dropped, ...]
    edges: Mapping[Pair, tuple[EntryId, ...]]
    levels: Mapping[str, int]
    unlocks: Mapping[str, int]
    chain: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Check:
    """One spot-check: whether ``waiter`` waits for ``driver``, and through which Epics."""

    waiter: str
    driver: str
    path: tuple[str, ...]
    direct: tuple[EntryId, ...]


@dataclass(frozen=True, slots=True)
class Analysis:
    """Everything the report shows."""

    release: str
    epics: Mapping[str, Epic]
    """The Epics of the release, the only ones ordered."""
    others: Mapping[str, Epic]
    """The Epics of every other release, which take no part in the order."""
    items: Mapping[EntryId, SharedItem]
    """Every item two or more Epics of the release need, with only those Epics as its needs."""
    foreign: tuple[EntryId, ...]
    """The items whose recorded driver is an Epic of another release, so no record decides them here."""
    order: Order
    standing: tuple[StandingEdge, ...] | None
    """Every dependency edge between two Epics in beads, or None when beads was not read."""
    checks: tuple[Check, ...]


def deciding(items: Iterable[SharedItem]) -> list[SharedItem]:
    """List the shared items a record decides and no ``epicDriver: none`` stack holds.

    Returns:
        The items that make edges before the loop break, in the order given.

    """
    return [item for item in items if item.decision is not None and not item.in_advance]


def unjudged(items: Iterable[SharedItem]) -> list[SharedItem]:
    """List the shared items no record decides, outside every stack deployed in advance.

    Returns:
        The items, in the order given.

    """
    return [item for item in items if item.decision is None and not item.in_advance]


def label(analysis: Analysis, item: EntryId) -> str:
    """Name an item by its matrix name and id.

    Returns:
        ``<name> (<id>)``.

    """
    found: SharedItem | None = analysis.items.get(item)
    return item if found is None else f"{found.name} ({item})"


def edges_made(analysis: Analysis) -> dict[EntryId, int]:
    """Count the edges each item makes after the loop break, before the reduction.

    Returns:
        Each item that makes an edge with its count.

    """
    made: dict[EntryId, int] = {}
    for item in (f for items in analysis.order.raw.values() for f in items):
        made[item] = made.get(item, 0) + 1
    return made
