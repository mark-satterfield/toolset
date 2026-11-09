"""Immutable read views of one revision of a step journal.

A step reads the journal many times while it runs: to find itself, its inputs, its ancestors and
the artifacts earlier steps accepted. Each of those walks the whole step tree. The views here are
built once from one revision (``step_journal.read_snapshot``) and answer those questions by
index:

- :class:`JournalIndex`: every step by id, its parent, its walk position and the steps below it.
- :class:`AcceptedView`: what one step may treat as accepted. Done steps before it in walk order
  and its running structural ancestors are accepted; running siblings, future steps and failed or
  planned steps are not. The latest artifact of each name among them is indexed with the step that
  produced it.

A view is keyed by the journal file, the digest of the revision it was built from and the step it
was built for, so a journal change (a new revision) never serves an older view. Values handed out
are copies: a caller that changes one changes nothing another caller sees. Nothing here writes a
journal; every change still goes through ``step_journal.update_journal``.
"""

from __future__ import annotations

import copy
import threading
from collections import OrderedDict
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from . import step_journal

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import (
    KIND_VALUE,
    PLANNED_FOR_PREFIX,
    STATUS_DONE,
    STATUS_RUNNING,
    Artifact,
    ArtifactKind,
    Journal,
    JsonValue,
    Step,
    StepId,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence
    from pathlib import Path

VIEW_CACHE_SIZE: Final = 64
"""How many accepted views a process keeps; each is keyed by journal, revision and step."""


@dataclass(frozen=True, slots=True)
class JournalIndex:
    """Every step of one journal revision by id, with its parent, walk position and subtree end.

    ``order`` lists the steps in walk order (each step before its child steps, siblings in
    order). The steps below a step are the slice of ``order`` from its position to its ``end``.
    """

    order: tuple[Step, ...]
    position: Mapping[StepId, int]
    end: Mapping[StepId, int]
    parent: Mapping[StepId, StepId | None]

    def step(self, step_id: StepId) -> Step:
        """Find a step by id.

        Returns:
            The step of this revision.

        Raises:
            StepRefusedError: No step of the revision has that id.

        """
        found: int | None = self.position.get(step_id)
        if found is None:
            message: str = f"no step {step_id} in this step journal revision"
            raise step_journal.StepRefusedError(message)
        return self.order[found]

    def parent_of(self, step_id: StepId) -> Step | None:
        """Find the step that directly contains a step.

        Returns:
            The containing step, or None for an outermost step.

        """
        self.step(step_id)
        above: StepId | None = self.parent.get(step_id)
        return None if above is None else self.step(above)

    def ancestors(self, step_id: StepId) -> tuple[StepId, ...]:
        """List the steps that contain a step, nearest first.

        Returns:
            Each containing step's id, from the direct parent to the outermost step.

        """
        chain: list[StepId] = []
        above: StepId | None = self.parent.get(self.step(step_id)["id"])
        while above is not None:
            chain.append(above)
            above = self.parent.get(above)
        return tuple(chain)

    def outermost(self, step_id: StepId) -> Step:
        """Find the outermost step that holds a step.

        Returns:
            The outermost containing step, or the step itself when it is outermost.

        """
        chain: tuple[StepId, ...] = self.ancestors(step_id)
        return self.step(chain[-1]) if chain else self.step(step_id)

    def subtree(self, step_id: StepId) -> tuple[Step, ...]:
        """List a step and every step below it in walk order.

        Returns:
            The step, then each step below it before its own child steps.

        """
        start: int = self.position[self.step(step_id)["id"]]
        return self.order[start : self.end[step_id]]

    def before(self, step_id: StepId) -> tuple[Step, ...]:
        """List the steps before a step in walk order.

        Returns:
            Every step that the walk reaches before ``step_id``.

        """
        return self.order[: self.position[self.step(step_id)["id"]]]


def _visit(
    steps: Sequence[Step],
    above: StepId | None,
    order: list[Step],
    parents: dict[StepId, StepId | None],
    ends: dict[StepId, int],
) -> None:
    """Record a list of sibling steps and everything below them in walk order."""
    step: Step
    for step in steps:
        order.append(step)
        parents[step["id"]] = above
        _visit(step["steps"], step["id"], order, parents, ends)
        ends[step["id"]] = len(order)


def index_journal(journal: Journal) -> JournalIndex:
    """Index every step of a journal once.

    Args:
        journal: A validated journal; the index refers to its steps, so the journal is not changed
            while the index is used.

    Returns:
        The index.

    Raises:
        TypeError: ``journal`` is not a journal object.

    """
    if not isinstance(journal, dict) or not isinstance(journal.get("steps"), list):
        message: str = "a journal index is built from a validated step journal"
        raise TypeError(message)
    order: list[Step] = []
    parents: dict[StepId, StepId | None] = {}
    ends: dict[StepId, int] = {}
    _visit(journal["steps"], None, order, parents, ends)
    return JournalIndex(
        order=tuple(order),
        position=MappingProxyType({step["id"]: place for place, step in enumerate(order)}),
        end=MappingProxyType(ends),
        parent=MappingProxyType(parents),
    )


@dataclass(frozen=True, slots=True)
class AcceptedArtifact:
    """The latest accepted artifact of one name, with the step that produced it.

    ``producer`` is the producing step's script key, else its agent, else its description;
    ``producer_status`` is ``done``, or ``running`` for a structural ancestor of the viewing step.
    ``path`` is set for a file or directory artifact and ``value`` for a value artifact.
    """

    name: str
    kind: ArtifactKind
    step: StepId
    producer: str
    producer_status: str
    path: str | None
    value: JsonValue

    def held(self) -> JsonValue:
        """Read what the artifact holds, the way an artifact lookup returns it.

        Returns:
            A copy of the value of a value artifact, or the path of a file or directory artifact.

        """
        return copy.deepcopy(self.value) if self.path is None else self.path


@dataclass(frozen=True, slots=True)
class AcceptedView:
    """What one step may treat as accepted in one revision of its journal.

    ``boundary`` lists the accepted steps' ids in walk order: the done steps before the viewing
    step and its running structural ancestors. ``latest`` holds, for every artifact name those
    steps recorded, the one the last of them recorded (within a step, its last of that name).
    """

    journal: Path
    revision: str
    step: StepId
    boundary: tuple[StepId, ...]
    latest: Mapping[str, AcceptedArtifact]
    _steps: tuple[Step, ...]

    def artifact(self, name: str) -> AcceptedArtifact | None:
        """Find the latest accepted artifact of a name.

        Returns:
            The artifact with its producer, or None when no accepted step recorded the name.

        """
        return self.latest.get(name)

    def held(self, name: str) -> JsonValue:
        """Read the latest accepted artifact of a name, as ``build_sessions.latest`` returns it.

        Returns:
            A copy of its value, or its path; None when no accepted step recorded it.

        """
        found: AcceptedArtifact | None = self.latest.get(name)
        return None if found is None else found.held()

    def steps(self) -> list[Step]:
        """Copy the accepted steps in walk order.

        Returns:
            Each accepted step, a copy a caller may change.

        """
        return copy.deepcopy(list(self._steps))

    def last_performed_by(self, agent: str) -> StepId | None:
        """Find the last accepted step an agent performed.

        Returns:
            Its id, or None when the agent performed no accepted step.

        """
        performed: list[StepId] = [step["id"] for step in self._steps if step.get("agent") == agent]
        return performed[-1] if performed else None

    def produced_after(self, step_id: StepId | None) -> Iterator[AcceptedArtifact]:
        """Yield the latest artifacts whose producing step comes after a step in walk order.

        Args:
            step_id: An accepted step; None yields every latest artifact.

        Yields:
            Each latest artifact produced after ``step_id``, in name order.

        """
        after: int = -1 if step_id is None or step_id not in self.boundary else self.boundary.index(step_id)
        rank: dict[StepId, int] = {held: place for place, held in enumerate(self.boundary)}
        yield from (self.latest[name] for name in sorted(self.latest) if rank[self.latest[name].step] > after)


def _is_accepted(step: Step, ancestors: frozenset[StepId]) -> bool:
    """Tell whether a step before the viewing step holds accepted artifacts.

    Returns:
        True for a done step, or a running step that structurally contains the viewing step.

    """
    return step["status"] == STATUS_DONE or (step["status"] == STATUS_RUNNING and step["id"] in ancestors)


def _latest(steps: Sequence[Step]) -> dict[str, AcceptedArtifact]:
    """Index the last artifact of each name over accepted steps in walk order.

    Returns:
        The latest artifact of every name, planned parameters (``for <step id>``) excluded.

    """
    found: dict[str, AcceptedArtifact] = {}
    pairs: Iterator[tuple[Step, Artifact]] = (
        (step, artifact)
        for step in steps
        for artifact in step["artifacts"]
        if not artifact["name"].startswith(PLANNED_FOR_PREFIX)
    )
    step: Step
    artifact: Artifact
    for step, artifact in pairs:
        found[artifact["name"]] = _accepted_artifact(step, artifact)
    return found


def _accepted_artifact(step: Step, artifact: Artifact) -> AcceptedArtifact:
    """Describe one accepted artifact with its producer.

    Returns:
        The artifact, its value copied so the view does not share the journal's objects.

    """
    producer: str = step.get("script") or step.get("agent") or step["description"]
    if artifact["kind"] == KIND_VALUE:
        return AcceptedArtifact(
            artifact["name"],
            artifact["kind"],
            step["id"],
            producer,
            step["status"],
            None,
            copy.deepcopy(artifact["value"]),
        )
    return AcceptedArtifact(
        artifact["name"],
        artifact["kind"],
        step["id"],
        producer,
        step["status"],
        artifact["path"],
        None,
    )


def build_accepted_view(snapshot: step_journal.JournalSnapshot, step_id: StepId) -> AcceptedView:
    """Build the accepted view of one step from one journal revision.

    A revision with no step ``step_id`` raises ``StepRefusedError``.

    Args:
        snapshot: The revision, as ``step_journal.read_snapshot`` read it.
        step_id: The viewing step.

    Returns:
        The view.

    """
    index: JournalIndex = index_journal(snapshot.journal)
    ancestors: frozenset[StepId] = frozenset(index.ancestors(step_id))
    accepted: tuple[Step, ...] = tuple(
        copy.deepcopy(step) for step in index.before(step_id) if _is_accepted(step, ancestors)
    )
    return AcceptedView(
        journal=snapshot.path,
        revision=snapshot.revision,
        step=step_id,
        boundary=tuple(step["id"] for step in accepted),
        latest=MappingProxyType(_latest(accepted)),
        _steps=accepted,
    )


class _ViewCache:
    """The accepted views built in this process, keyed by journal file, revision and step."""

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._views: OrderedDict[tuple[Path, str, StepId], AcceptedView] = OrderedDict()

    def view(self, journal: Path, step_id: StepId) -> AcceptedView:
        """Read the journal's current revision and return the step's view of it.

        Returns:
            The cached view of that exact revision, or one built from it now.

        """
        snapshot: step_journal.JournalSnapshot = step_journal.read_snapshot(journal)
        key: tuple[Path, str, StepId] = (journal, snapshot.revision, step_id)
        with self._lock:
            held: AcceptedView | None = self._views.get(key)
            if held is not None:
                self._views.move_to_end(key)
                return held
        built: AcceptedView = build_accepted_view(snapshot, step_id)
        with self._lock:
            self._views[key] = built
            while len(self._views) > VIEW_CACHE_SIZE:
                self._views.popitem(last=False)
        return built


_VIEWS: Final = _ViewCache()
"""The process's accepted views; disposable, rebuilt from the journal on any miss."""


def accepted_view(journal: Path, step_id: StepId) -> AcceptedView:
    """Return a step's accepted view of the journal's current revision.

    The journal is read on every call; a view is reused only for the same bytes and step.

    Args:
        journal: The journal file.
        step_id: The viewing step.

    Returns:
        The view.

    """
    return _VIEWS.view(journal, step_id)
