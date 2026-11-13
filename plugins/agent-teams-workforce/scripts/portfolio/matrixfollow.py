"""Correct the matrix's shared-capability guesses from what a Task's code actually does.

The matrix is a best guess. Where a built Task's code diverges from it, the build corrects the
matrix, never the code: :func:`follow_code` (``follow-code``) runs after the Task is committed and
writes the ``supportedBy`` relationships of the features the Task builds to match the code.

- A relationship ``supportedBy F→C`` whose relied ``provides`` items of the shared capability C
  carry use signals that occur nowhere in the repository's tracked source loses those items; it is
  unlinked when no item is left. This is written only when F is wholly in the Task's repository
  (every entry realizing F is held by one of its stacks; an event by its publishers' stacks) and
  no other open Task builds F, since otherwise code outside this worktree may still use C.
- A shared capability the Task's ids do not reach, whose use signals occur in the Task's own
  changed product files, is linked from the one feature the Task builds that is wholly in its
  repository.
- Everything else that diverges is recorded as ``deferred`` with its reason, and ids the matrix
  holds no entry for as ``unknownIds``: the code gives no kind, home or deployed name to record.

Items with no use signal cannot be judged and are kept. The walk, the signals and the evidence
are those of :func:`matrixreuse.check_reuse`.
"""

import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    KIND_EVENT,
    KIND_FEATURE,
    KIND_STACK,
    REL_REALIZED_BY,
    REL_SUPPORTED_BY,
    SIDE_ARCHITECTURE,
    EntryId,
    JsonValue,
    MatrixError,
    Relationship,
)
from matrixreuse import (
    Own,
    Provided,
    holds_signal,
    is_test,
    own_of,
    provided_items,
    source_lines,
    test_roots,
    walk_starts,
)
from matrixstore import Matrix
from matrixsync import program_output
from matrixtasks import TaskBead
from matrixtraverse import holder

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

COMMAND_FOLLOW_CODE: Final = "follow-code"
ATTR_RELIES: Final = "relies"
ATTR_REPOSITORY: Final = "repository"
REASON_ELSEWHERE: Final = "realized outside this repository's stacks, so code elsewhere may still use it"
REASON_BUILDING: Final = "other open Tasks still build it: "
REASON_NAMED: Final = "named only by the Task's matrix_elements: the bead, not a matrix relationship, holds the guess"
REASON_NO_FEATURE: Final = "no single feature the Task builds is wholly in this repository: "


class FollowedRelationship(TypedDict):
    """One ``supportedBy`` relationship the step wrote or removed."""

    kind: str
    start: str
    end: str
    relies: list[str]
    """For a removed relationship the items it relied on; otherwise the items it relies on now."""


class DeferredDivergence(TypedDict):
    """A divergence the step recorded without writing, and why."""

    start: str
    end: str
    provides: list[str]
    """The ``provides`` items concerned: unused ones for a guess, used ones for an unrecorded use."""
    used: bool
    """True for a use the matrix does not record; False for a relied-on item the code does not use."""
    reason: str


class FollowResult(TypedDict):
    """What ``follow-code`` changed in the matrix, and what it left as it was."""

    ids: list[str]
    files: list[str]
    """The Task's changed source files the unrecorded uses were looked for in."""
    removed: list[FollowedRelationship]
    narrowed: list[FollowedRelationship]
    linked: list[FollowedRelationship]
    deferred: list[DeferredDivergence]
    unknownIds: list[str]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True, slots=True)
class FollowScope:
    """What one built Task hands the correction."""

    task: str
    """The Task's beads id."""
    entry_ids: tuple[EntryId, ...]
    """The ids the Task's ``matrix_elements`` state."""
    worktree: Path
    files: tuple[str, ...]
    """The files the Task's own commits changed, relative to the worktree."""
    tasks: tuple[TaskBead, ...]
    """Every Task bead, to tell which other open Tasks build a feature."""


@dataclass(frozen=True, slots=True)
class _Place:
    """Where the Task is: its own entries and stacks, and every stack of its repository."""

    own: Own
    stacks: frozenset[EntryId]


@dataclass
class _Outcome:
    """The result being gathered."""

    removed: list[FollowedRelationship]
    narrowed: list[FollowedRelationship]
    linked: list[FollowedRelationship]
    deferred: list[DeferredDivergence]


def _place(matrix: Matrix, known: Sequence[EntryId]) -> _Place:
    """Work out the Task's own entries and every stack of the repositories they are held in.

    Returns:
        The Task's own entries and stacks, and each stack whose repository is one of theirs.

    """
    own: Own = own_of(matrix, known)
    repositories: set[JsonValue] = {matrix.entry(stack).attributes.get(ATTR_REPOSITORY) for stack in own.stacks}
    repositories.discard(None)
    stacks: frozenset[EntryId] = frozenset(
        stack.id for stack in matrix.entries((KIND_STACK,)) if stack.attributes.get(ATTR_REPOSITORY) in repositories
    )
    return _Place(own, stacks | own.stacks)


def _held_here(matrix: Matrix, entry_id: EntryId, stacks: frozenset[EntryId]) -> bool:
    """Tell whether an entry that realizes a feature is held by the repository's stacks.

    Returns:
        For an event, True when it has publishers and all are homed in those stacks; otherwise
        True when the stack that holds the entry is one of them.

    """
    if matrix.entry(entry_id).kind == KIND_EVENT:
        publishers: frozenset[EntryId] = matrix.publisher_stacks(entry_id)
        return bool(publishers) and publishers <= stacks
    return holder(matrix, entry_id) in stacks


def _wholly_here(matrix: Matrix, feature: EntryId, stacks: frozenset[EntryId]) -> bool:
    """Tell whether every entry realizing a feature is held by the repository's stacks.

    Returns:
        True when the feature has a realizer and all of them are held there.

    """
    realizers: list[Relationship] = matrix.outgoing(feature, (REL_REALIZED_BY,))
    return bool(realizers) and all(_held_here(matrix, realizing.end, stacks) for realizing in realizers)


def _builders(matrix: Matrix, feature: EntryId, scope: FollowScope, stacks: frozenset[EntryId]) -> list[str]:
    """Name the other open Tasks that build a feature in this repository.

    A Task of another repository that names an entry realizing the feature consumes it there and
    does not build it, so only a Task that also names a stack of this repository counts.

    Returns:
        The ids of the Tasks that are not closed, are not this Task, name a stack of this
        repository, and state the feature or an entry realizing it.

    """
    building: set[str] = {feature, *(realizing.end for realizing in matrix.outgoing(feature, (REL_REALIZED_BY,)))}
    return [
        task.id
        for task in scope.tasks
        if not task.closed and task.id != scope.task and building & set(task.elements) and stacks & set(task.elements)
    ]


def _walk(matrix: Matrix, starts: Sequence[EntryId]) -> list[Relationship]:
    """Collect every ``supportedBy`` relationship the capability walk follows from some features.

    Returns:
        Each relationship once, in the order the walk meets it.

    """
    queue: deque[EntryId] = deque(starts)
    seen: set[EntryId] = set()
    followed: list[Relationship] = []
    while queue:
        feature: EntryId = queue.popleft()
        if feature in seen:
            continue
        seen.add(feature)
        supporting: list[Relationship] = matrix.outgoing(feature, (REL_SUPPORTED_BY,))
        followed.extend(supporting)
        queue.extend(relationship.end for relationship in supporting)
    return followed


def _relied(relationship: Relationship, provides: Sequence[Provided]) -> list[Provided]:
    """Read the items a ``supportedBy`` relationship relies on.

    Returns:
        The items it names, or every item when it names none.

    """
    stated: JsonValue = relationship.attributes.get(ATTR_RELIES)
    named: set[str] = {item for item in stated if isinstance(item, str)} if isinstance(stated, list) else set()
    return [item for item in provides if not named or item.id in named]


def _row(relationship: Relationship, relies: Sequence[str]) -> FollowedRelationship:
    """Describe a relationship for the result.

    Returns:
        Its kind, ends and relied items.

    """
    return {"kind": relationship.kind, "start": relationship.start, "end": relationship.end, "relies": [*relies]}


def _hold_reason(matrix: Matrix, feature: EntryId, place: _Place, scope: FollowScope) -> str | None:
    """Say why a guess about a feature is not corrected here.

    Returns:
        The reason, or None when the feature is wholly in this repository and no other open Task builds it.

    """
    if not _wholly_here(matrix, feature, place.stacks):
        return REASON_ELSEWHERE
    builders: list[str] = _builders(matrix, feature, scope, place.stacks)
    return f"{REASON_BUILDING}{', '.join(builders)}" if builders else None


def _correct_guess(
    matrix: Matrix,
    relationship: Relationship,
    unused: Sequence[Provided],
    context: tuple[_Place, FollowScope, _Outcome],
) -> None:
    """Narrow or remove one ``supportedBy`` whose relied items the code does not use, or defer it."""
    place, scope, outcome = context
    unused_ids: list[str] = [item.id for item in unused]
    reason: str | None = _hold_reason(matrix, relationship.start, place, scope)
    if reason is not None:
        outcome.deferred.append({
            "start": relationship.start,
            "end": relationship.end,
            "provides": unused_ids,
            "used": False,
            "reason": reason,
        })
        return
    provides: tuple[Provided, ...] = provided_items(matrix.entry(relationship.end))
    kept: list[str] = [item.id for item in _relied(relationship, provides) if item.id not in unused_ids]
    if not kept:
        matrix.unlink(relationship)
        outcome.removed.append(_row(relationship, [item.id for item in _relied(relationship, provides)]))
        return
    matrix.link(
        Relationship(
            kind=relationship.kind,
            start=relationship.start,
            end=relationship.end,
            side=relationship.side,
            attributes={**relationship.attributes, ATTR_RELIES: [*kept]},
            approved=relationship.approved,
            verified=relationship.verified,
        ),
    )
    outcome.narrowed.append(_row(relationship, kept))


def _unused_items(relied: Sequence[Provided], everything: dict[str, list[str]]) -> list[Provided]:
    """Pick the relied-on items whose use signals occur nowhere.

    Returns:
        Those items; an item with no use signal is never among them.

    """
    return [item for item in relied if item.use_signals and not holds_signal(everything, item.use_signals)]


def _record_use(
    matrix: Matrix,
    capability: EntryId,
    used: Sequence[str],
    context: tuple[Sequence[EntryId], _Place, _Outcome],
) -> None:
    """Link the Task's one wholly-local feature to a capability its code uses, or defer the use."""
    starts, place, outcome = context
    local: list[EntryId] = [feature for feature in starts if _wholly_here(matrix, feature, place.stacks)]
    if len(local) != 1:
        outcome.deferred.append({
            "start": ", ".join(starts),
            "end": capability,
            "provides": [*used],
            "used": True,
            "reason": f"{REASON_NO_FEATURE}{', '.join(local) or 'none'}",
        })
        return
    linked: Relationship = Relationship(
        kind=REL_SUPPORTED_BY,
        start=local[0],
        end=capability,
        side=SIDE_ARCHITECTURE,
        attributes={ATTR_RELIES: [*used]},
    )
    matrix.link(linked)
    outcome.linked.append(_row(linked, used))


def _named_capabilities(matrix: Matrix, known: Sequence[EntryId]) -> list[EntryId]:
    """Pick the ids that are shared capabilities named directly.

    Returns:
        The features among the ids that state what they provide.

    """
    return [
        entry_id
        for entry_id in known
        if matrix.entry(entry_id).kind == KIND_FEATURE and provided_items(matrix.entry(entry_id))
    ]


def _tracked(worktree: Path) -> dict[str, list[str]]:
    """Read every tracked source file of the worktree.

    Returns:
        Each source file's path and lines.

    """
    return source_lines(worktree, program_output("git", ["ls-files", "-z"], worktree).split("\0"))


def _defer_named(matrix: Matrix, named: Sequence[EntryId], everything: dict[str, list[str]], outcome: _Outcome) -> None:
    """Record each directly named capability whose items the code does not use as deferred."""
    for capability in named:
        unused: list[Provided] = _unused_items(provided_items(matrix.entry(capability)), everything)
        if unused:
            outcome.deferred.append({
                "start": "",
                "end": capability,
                "provides": [item.id for item in unused],
                "used": False,
                "reason": REASON_NAMED,
            })


def _unrecorded(
    matrix: Matrix,
    reached: Collection[EntryId],
    place: _Place,
    product: dict[str, list[str]],
) -> list[tuple[EntryId, list[str]]]:
    """Find the shared capabilities the Task's changed product files use that its ids do not reach.

    Returns:
        Each such capability with the ids of the items whose use signals occur, in id order.

    """
    candidates: list[tuple[EntryId, list[str]]] = [
        (
            feature.id,
            [
                item.id
                for item in provided_items(feature)
                if item.use_signals and holds_signal(product, item.use_signals)
            ],
        )
        for feature in matrix.entries((KIND_FEATURE,))
        if feature.id not in reached and not place.own.provides(matrix, feature.id)
    ]
    return sorted((capability, used) for capability, used in candidates if used)


def _correct_walked(
    matrix: Matrix,
    walked: Sequence[Relationship],
    everything: dict[str, list[str]],
    context: tuple[_Place, FollowScope, _Outcome],
) -> None:
    """Correct each walked ``supportedBy`` whose relied items the tracked source does not use."""
    for relationship in walked:
        unused: list[Provided] = _unused_items(
            _relied(relationship, provided_items(matrix.entry(relationship.end))),
            everything,
        )
        if unused:
            _correct_guess(matrix, relationship, unused, context)


def _product(worktree: Path, changed: dict[str, list[str]]) -> dict[str, list[str]]:
    """Keep the changed source files that are not the repository's tests.

    Returns:
        Those files and their lines.

    """
    roots: frozenset[str] = test_roots(worktree)
    return {file: lines for file, lines in changed.items() if not is_test(file, roots)}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def follow_code(matrix: Matrix, scope: FollowScope) -> FollowResult:
    """Correct the ``supportedBy`` guesses of the features a Task builds from what its code uses.

    Args:
        matrix: The matrix, changed in place (the caller holds its lock through ``update_matrix``).
        scope: The Task, its ids, its worktree, its changed files and every Task bead.

    Returns:
        The relationships removed, narrowed and linked, the divergence left as it was with its
        reason, and the ids the matrix holds no entry for.

    Raises:
        MatrixError: The worktree is not a directory, or git cannot list its files.

    """
    if not scope.worktree.is_dir():
        message: str = f"the worktree {scope.worktree} is not a directory"
        raise MatrixError(message)
    known: list[EntryId] = [entry_id for entry_id in dict.fromkeys(scope.entry_ids) if matrix.find(entry_id)]
    unknown: list[str] = [entry_id for entry_id in dict.fromkeys(scope.entry_ids) if entry_id not in known]
    outcome: _Outcome = _Outcome([], [], [], [])
    changed: dict[str, list[str]] = source_lines(scope.worktree, scope.files)
    result: FollowResult = {
        "ids": [*known],
        "files": sorted(changed),
        "removed": outcome.removed,
        "narrowed": outcome.narrowed,
        "linked": outcome.linked,
        "deferred": outcome.deferred,
        "unknownIds": unknown,
    }
    if not known:
        return result
    place: _Place = _place(matrix, known)
    named: list[EntryId] = _named_capabilities(matrix, known)
    starts: list[EntryId] = walk_starts(matrix, [entry_id for entry_id in known if entry_id not in named], place.own)
    followed: list[Relationship] = _walk(matrix, starts)
    reached: set[EntryId] = {*named, *starts, *(relationship.end for relationship in followed)}
    walked: list[Relationship] = [
        relationship
        for relationship in followed
        if provided_items(matrix.entry(relationship.end)) and not place.own.provides(matrix, relationship.end)
    ]
    everything: dict[str, list[str]] = _tracked(scope.worktree)
    _defer_named(matrix, named, everything, outcome)
    _correct_walked(matrix, walked, everything, (place, scope, outcome))
    for capability, used in _unrecorded(matrix, reached, place, _product(scope.worktree, changed)):
        _record_use(matrix, capability, used, (starts, place, outcome))
    return result
