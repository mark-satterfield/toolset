"""Correct the matrix's shared-capability guesses from what a Task's code actually does.

The matrix is a best guess. Where a built Task's code diverges from it, the build corrects the
matrix, never the code: :func:`follow_code` (``follow-code``) runs after the Task is committed and
writes the ``supportedBy`` relationships of the features the Task builds to match the code. A wrong
removal is worse than a stale guess, so whatever cannot be judged safely is recorded as
``deferred`` with its reason and left as it was.

- A relationship ``supportedBy F→C`` whose relied ``provides`` items of the shared capability C
  carry use signals that occur nowhere loses those items; it is unlinked when no item is left.
  "Nowhere" means: not in the Story worktree's tracked source, and not in the committed source of
  the repository's integration branch (``origin/HEAD``) or of any of its Story branches, local or
  on the remote (the caller fetches first). It is written only when F is wholly in the worktree's
  repository (every entry realizing F is held by one of that repository's stacks; an event by its
  publishers' stacks) and no other Task still builds F there: an open Task, or a closed Task of
  another Story that is not closed yet, whose code may not have reached the integration branch.
- A shared capability item whose code-shaped use signals occur in the code (comments and
  docstrings left out) of the Task's own changed product files, and which no relationship from
  what the Task reaches records, is added to ``relies`` of the relationship from the one feature
  the Task builds wholly in its repository, or linked from that feature when there is none. A use
  shown only by prose signals (words and spaces, for example ``central event API``) is too weak
  to record on its own.
- Everything else that diverges is recorded as ``deferred`` with its reason, and ids the matrix
  holds no entry for as ``unknownIds``: the code gives no kind, home or deployed name to record.

Items with no use signal cannot be judged and are kept. The walk, the signals and the evidence
are those of :func:`matrixreuse.check_reuse`.
"""

import io
import re
import sys
import tokenize
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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
    PIPELINE_FOLDER,
    SOURCE_SUFFIXES,
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
REMOTE: Final = "origin"
OTHER_CODE_REFS: Final[tuple[str, ...]] = (
    f"refs/remotes/{REMOTE}/HEAD",
    "refs/heads/story/",
    f"refs/remotes/{REMOTE}/story/",
)
"""The committed code of the repository outside the Story worktree: its integration branch and every Story branch."""
GIT_GREP_NO_MATCH: Final = 1
PYTHON_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi"})
COMMENT_LINE_STARTS: Final[tuple[str, ...]] = ("#", "//", "/*", "*", "<!--", "--")
TRAILING_COMMENT: Final[re.Pattern[str]] = re.compile(r"\s(?:#|//)\s.*$")
PROSE_SIGNAL: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)+$")
"""A use signal of words and spaces only: it may appear in any prose, so it never records a use on its own."""
STATEMENT_START: Final[frozenset[int]] = frozenset({tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT})
STATEMENT_END: Final[frozenset[int]] = frozenset({tokenize.NEWLINE, tokenize.ENDMARKER})
REASON_ELSEWHERE: Final = "realized outside this repository's stacks, so code elsewhere may still use it"
REASON_BUILDING: Final = "other Tasks still build it, open or in a Story not closed yet: "
REASON_OTHER_CODE: Final = "its use signals occur in this repository's committed code outside the Story worktree: "
REASON_NAMED: Final = "named only by the Task's matrix_elements: the bead, not a matrix relationship, holds the guess"
REASON_NO_FEATURE: Final = "no single feature the Task builds is wholly in this repository: "
REASON_OTHER_PATH: Final = "already reached from another feature or capability, so the use cannot be placed: "
REASON_PROSE: Final = "only prose use signals occur in the changed code, too weak to record a use on their own"


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
    repository: str
    """The repository of the worktree: only features wholly in it are corrected."""
    refs: list[str]
    """The branches outside the worktree whose committed code was searched before removing an item."""
    files: list[str]
    """The Task's changed source files the unrecorded uses were looked for in."""
    removed: list[FollowedRelationship]
    narrowed: list[FollowedRelationship]
    widened: list[FollowedRelationship]
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
    """The Story worktree; its ``origin`` was fetched just before, so its remote branches are current."""
    files: tuple[str, ...]
    """The files the Task's own commits changed, relative to the worktree."""
    tasks: tuple[TaskBead, ...]
    """Every Task bead, to tell which other Tasks still build a feature."""


@dataclass(frozen=True, slots=True)
class _Place:
    """Where the Task is: its own entries, its worktree's repository and that repository's stacks."""

    own: Own
    repository: str
    stacks: frozenset[EntryId]
    refs: tuple[str, ...]
    """The branches outside the worktree whose committed code may still use a capability."""


@dataclass
class _Outcome:
    """The result being gathered."""

    removed: list[FollowedRelationship]
    narrowed: list[FollowedRelationship]
    widened: list[FollowedRelationship]
    linked: list[FollowedRelationship]
    deferred: list[DeferredDivergence]


def _repository(worktree: Path) -> str:
    """Name the repository a worktree is a clone of, as a stack's ``repository`` names it.

    Returns:
        The last part of the ``origin`` URL, without ``.git``.

    """
    url: str = program_output("git", ["remote", "get-url", REMOTE], worktree).strip().rstrip("/")
    return PurePosixPath(url.replace(":", "/")).name.removesuffix(".git")


def _other_refs(worktree: Path) -> tuple[str, ...]:
    """List the branches whose committed code is outside the worktree: the integration branch and every Story branch.

    Returns:
        Each such ref's full name.

    """
    printed: str = program_output("git", ["for-each-ref", "--format=%(refname)", *OTHER_CODE_REFS], worktree)
    return tuple(line.strip() for line in printed.splitlines() if line.strip())


def _place(matrix: Matrix, known: Sequence[EntryId], worktree: Path) -> _Place:
    """Work out the Task's own entries, its worktree's repository and that repository's stacks.

    Only the repository whose code is scanned counts: a Task whose ids span two repositories
    judges no feature of the other one.

    Returns:
        The Task's own entries, the repository, each stack the matrix places in it, and the
        branches whose code is outside the worktree.

    """
    repository: str = _repository(worktree)
    stacks: frozenset[EntryId] = frozenset(
        stack.id for stack in matrix.entries((KIND_STACK,)) if stack.attributes.get(ATTR_REPOSITORY) == repository
    )
    return _Place(own_of(matrix, known), repository, stacks, _other_refs(worktree))


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


def _still_building(task: TaskBead, scope: FollowScope, story: str | None) -> bool:
    """Tell whether another Task's code may not be in the worktree or on the integration branch yet.

    Returns:
        True for a Task that is not this one and is open, or is closed in another Story that is
        not closed yet (Tasks close when built, before their Story's work is delivered).

    """
    if task.id == scope.task:
        return False
    return not task.closed or (task.story is not None and task.story != story and not task.story_closed)


def _builders(matrix: Matrix, feature: EntryId, scope: FollowScope, stacks: frozenset[EntryId]) -> list[str]:
    """Name the other Tasks that still build a feature in this repository.

    A Task of another repository that names an entry realizing the feature consumes it there and
    does not build it, so only a Task that also names a stack of this repository counts.

    Returns:
        The ids of the Tasks still building (:func:`_still_building`) that name a stack of this
        repository and state the feature or an entry realizing it.

    """
    building: set[str] = {feature, *(realizing.end for realizing in matrix.outgoing(feature, (REL_REALIZED_BY,)))}
    story: str | None = next((task.story for task in scope.tasks if task.id == scope.task), None)
    return [
        task.id
        for task in scope.tasks
        if building & set(task.elements) and stacks & set(task.elements) and _still_building(task, scope, story)
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


def _named_items(relationship: Relationship) -> list[str]:
    """Read the item ids a ``supportedBy`` relationship names in ``relies``.

    Returns:
        Those ids in order; empty when it names none, which means it relies on every item.

    """
    stated: JsonValue = relationship.attributes.get(ATTR_RELIES)
    return [item for item in stated if isinstance(item, str)] if isinstance(stated, list) else []


def _relied(relationship: Relationship, provides: Sequence[Provided]) -> list[Provided]:
    """Read the items a ``supportedBy`` relationship relies on.

    Returns:
        The items it names, or every item when it names none.

    """
    named: set[str] = set(_named_items(relationship))
    return [item for item in provides if not named or item.id in named]


def _row(relationship: Relationship, relies: Sequence[str]) -> FollowedRelationship:
    """Describe a relationship for the result.

    Returns:
        Its kind, ends and relied items.

    """
    return {"kind": relationship.kind, "start": relationship.start, "end": relationship.end, "relies": [*relies]}


def _with_relies(relationship: Relationship, relies: Sequence[str]) -> Relationship:
    """Copy a relationship with another ``relies`` list, keeping its marks.

    Returns:
        The copy.

    """
    return Relationship(
        kind=relationship.kind,
        start=relationship.start,
        end=relationship.end,
        side=relationship.side,
        attributes={**relationship.attributes, ATTR_RELIES: [*relies]},
        approved=relationship.approved,
        verified=relationship.verified,
    )


def _deferral(relationship: Relationship, items: Sequence[str], reason: str) -> DeferredDivergence:
    """Describe a relied-on guess left as it was.

    Returns:
        Its ends, the items concerned and the reason.

    """
    return {"start": relationship.start, "end": relationship.end, "provides": [*items], "used": False, "reason": reason}


def _hold_reason(matrix: Matrix, feature: EntryId, place: _Place, scope: FollowScope) -> str | None:
    """Say why a guess about a feature is not corrected here.

    Returns:
        The reason, or None when the feature is wholly in this repository and no other Task still builds it.

    """
    if not _wholly_here(matrix, feature, place.stacks):
        return REASON_ELSEWHERE
    builders: list[str] = _builders(matrix, feature, scope, place.stacks)
    return f"{REASON_BUILDING}{', '.join(builders)}" if builders else None


def _pathspecs() -> list[str]:
    """Name the source files ``git grep`` searches, as the worktree scan reads them.

    Returns:
        One pathspec per source suffix, and the exclusion of the pipeline's folder.

    """
    return [*(f"*{suffix}" for suffix in sorted(SOURCE_SUFFIXES)), f":(exclude){PIPELINE_FOLDER}"]


def _used_in(worktree: Path, refs: Sequence[str], item: Provided) -> list[str]:
    """Find the branches whose committed source holds one of an item's use signals.

    Returns:
        Those refs, in name order; empty when there are none to search or none holds one. A
        search ``git grep`` cannot make raises ``MatrixError``.

    """
    if not refs:
        return []
    patterns: list[str] = [argument for signal in item.use_signals for argument in ("-e", signal)]
    printed: str = program_output(
        "git",
        ["grep", "-l", "-F", *patterns, *refs, "--", *_pathspecs()],
        worktree,
        (0, GIT_GREP_NO_MATCH),
    )
    return sorted({line.split(":", 1)[0] for line in printed.splitlines() if line.strip()})


def _correct_guess(
    matrix: Matrix,
    relationship: Relationship,
    unused: Sequence[Provided],
    context: tuple[_Place, FollowScope, _Outcome],
) -> None:
    """Narrow or remove one ``supportedBy`` whose relied items no code uses, or defer it."""
    place, scope, outcome = context
    reason: str | None = _hold_reason(matrix, relationship.start, place, scope)
    if reason is not None:
        outcome.deferred.append(_deferral(relationship, [item.id for item in unused], reason))
        return
    used_elsewhere: dict[str, list[str]] = {item.id: _used_in(scope.worktree, place.refs, item) for item in unused}
    elsewhere: list[str] = [item_id for item_id, refs in used_elsewhere.items() if refs]
    if elsewhere:
        found: str = ", ".join(sorted({ref for item_id in elsewhere for ref in used_elsewhere[item_id]}))
        outcome.deferred.append(_deferral(relationship, elsewhere, f"{REASON_OTHER_CODE}{found}"))
    unused_ids: list[str] = [item_id for item_id in used_elsewhere if item_id not in elsewhere]
    if not unused_ids:
        return
    relied: list[str] = [item.id for item in _relied(relationship, provided_items(matrix.entry(relationship.end)))]
    kept: list[str] = [item_id for item_id in relied if item_id not in unused_ids]
    if not kept:
        matrix.unlink(relationship)
        outcome.removed.append(_row(relationship, relied))
        return
    matrix.link(_with_relies(relationship, kept))
    outcome.narrowed.append(_row(relationship, kept))


def _unused_items(relied: Sequence[Provided], everything: dict[str, list[str]]) -> list[Provided]:
    """Pick the relied-on items whose use signals occur nowhere in the worktree.

    Returns:
        Those items; an item with no use signal is never among them.

    """
    return [item for item in relied if item.use_signals and not holds_signal(everything, item.use_signals)]


def _local_feature(matrix: Matrix, starts: Sequence[EntryId], place: _Place) -> tuple[EntryId | None, list[EntryId]]:
    """Find the one feature the Task builds wholly in its repository.

    Returns:
        That feature, or None when there is not exactly one; and every such feature.

    """
    local: list[EntryId] = [feature for feature in starts if _wholly_here(matrix, feature, place.stacks)]
    return (local[0] if len(local) == 1 else None), local


def _record_use(
    matrix: Matrix,
    capability: EntryId,
    used: Sequence[str],
    context: tuple[Sequence[EntryId], Collection[EntryId], _Place, _Outcome],
) -> None:
    """Record a use the code makes of a capability on the Task's one wholly-local feature, or defer it.

    The use is recorded when no relationship from what the Task reaches relies on the item yet:
    added to ``relies`` of the local feature's relationship to the capability, or linked from the
    local feature when it has none. A use that another reached feature or capability may make is
    not placed.
    """
    starts, reached, place, outcome = context
    recording: list[Relationship] = [
        relationship
        for relationship in matrix.incoming(capability, (REL_SUPPORTED_BY,))
        if relationship.start in reached
    ]
    provides: tuple[Provided, ...] = provided_items(matrix.entry(capability))
    recorded: set[str] = {item.id for relationship in recording for item in _relied(relationship, provides)}
    missing: list[str] = [item_id for item_id in used if item_id not in recorded]
    if not missing:
        return
    local, candidates = _local_feature(matrix, starts, place)
    others: list[str] = sorted({relationship.start for relationship in recording if relationship.start != local})
    if local is None or others:
        reason: str = (
            f"{REASON_NO_FEATURE}{', '.join(candidates) or 'none'}"
            if local is None
            else f"{REASON_OTHER_PATH}{', '.join(others)}"
        )
        outcome.deferred.append({
            "start": ", ".join(starts),
            "end": capability,
            "provides": missing,
            "used": True,
            "reason": reason,
        })
        return
    mine: Relationship | None = next((relationship for relationship in recording if relationship.start == local), None)
    if mine is not None:
        widened: Relationship = _with_relies(mine, [*_named_items(mine), *missing])
        matrix.link(widened)
        outcome.widened.append(_row(widened, _named_items(widened)))
        return
    linked: Relationship = Relationship(
        kind=REL_SUPPORTED_BY,
        start=local,
        end=capability,
        side=SIDE_ARCHITECTURE,
        attributes={ATTR_RELIES: [*missing]},
    )
    matrix.link(linked)
    outcome.linked.append(_row(linked, missing))


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


def _strong(signals: Sequence[str]) -> list[str]:
    """Keep the code-shaped use signals.

    Returns:
        The signals that are not prose (``PROSE_SIGNAL``).

    """
    return [signal for signal in signals if not PROSE_SIGNAL.match(signal.strip())]


def _code_uses(
    matrix: Matrix,
    place: _Place,
    code: dict[str, list[str]],
) -> list[tuple[EntryId, list[str], list[str]]]:
    """Find the shared capability items the code of the Task's changed product files uses.

    Returns:
        Each capability not provided by the Task's own repository, in id order, with the items a
        code-shaped signal shows and the items only a prose signal shows; capabilities with
        neither are left out.

    """
    found: list[tuple[EntryId, list[str], list[str]]] = []
    for feature in matrix.entries((KIND_FEATURE,)):
        if place.own.provides(matrix, feature.id):
            continue
        items: tuple[Provided, ...] = provided_items(feature)
        strong: list[str] = [item.id for item in items if holds_signal(code, _strong(item.use_signals))]
        prose: list[str] = [item.id for item in items if item.id not in strong and holds_signal(code, item.use_signals)]
        found.append((feature.id, strong, prose))
    return sorted(use for use in found if use[1] or use[2])


def _blank(lines: list[str], token: tokenize.TokenInfo) -> None:
    """Replace the text of one token with spaces, across the lines it spans."""
    (first_row, first_column), (last_row, last_column) = token.start, token.end
    for row in range(first_row, last_row + 1):
        line: str = lines[row - 1]
        begin: int = first_column if row == first_row else 0
        end: int = last_column if row == last_row else len(line)
        lines[row - 1] = f"{line[:begin]}{' ' * (end - begin)}{line[end:]}"


def _python_prose(lines: Sequence[str]) -> list[tokenize.TokenInfo] | None:
    """Find the comments and docstrings (strings standing as statements) of a Python file.

    Returns:
        Those tokens, or None when the file does not tokenize.

    """
    try:
        tokens: list[tokenize.TokenInfo] = list(tokenize.generate_tokens(io.StringIO("\n".join(lines)).readline))
    except tokenize.TokenError, SyntaxError:
        return None
    meaningful: list[tokenize.TokenInfo] = [
        token for token in tokens if token.type not in {tokenize.NL, tokenize.COMMENT}
    ]
    before: list[int] = [tokenize.NEWLINE, *(token.type for token in meaningful)]
    after: list[int] = [*(token.type for token in meaningful[1:]), tokenize.ENDMARKER]
    docstrings: list[tokenize.TokenInfo] = [
        token
        for token, previous, following in zip(meaningful, before, after, strict=False)
        if token.type == tokenize.STRING and previous in STATEMENT_START and following in STATEMENT_END
    ]
    return [*(token for token in tokens if token.type == tokenize.COMMENT), *docstrings]


def _code_line(line: str) -> str:
    """Drop the comment of one line of a file that is not Python.

    Returns:
        Empty for a line that starts as a comment; otherwise the line without a trailing comment.

    """
    if line.lstrip().startswith(COMMENT_LINE_STARTS):
        return ""
    return TRAILING_COMMENT.sub("", line)


def _code_only(relative: str, lines: Sequence[str]) -> list[str]:
    """Keep the code of a source file, leaving out its comments and docstrings.

    Returns:
        The file's lines with comments and docstrings blanked.

    """
    prose: list[tokenize.TokenInfo] | None = (
        _python_prose(lines) if PurePosixPath(relative).suffix in PYTHON_SUFFIXES else None
    )
    if prose is None:
        return [_code_line(line) for line in lines]
    code: list[str] = [*lines]
    for token in prose:
        _blank(code, token)
    return code


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


def _product_code(worktree: Path, changed: dict[str, list[str]]) -> dict[str, list[str]]:
    """Keep the code of the changed source files that are not the repository's tests.

    Returns:
        Those files and their lines, with comments and docstrings blanked.

    """
    roots: frozenset[str] = test_roots(worktree)
    return {file: _code_only(file, lines) for file, lines in changed.items() if not is_test(file, roots)}


def _follow_uses(
    matrix: Matrix,
    code: dict[str, list[str]],
    context: tuple[Sequence[EntryId], Collection[EntryId], _Place, _Outcome],
) -> None:
    """Record or defer each use the changed product code makes of a shared capability."""
    starts, _reached, place, outcome = context
    for capability, strong, prose in _code_uses(matrix, place, code):
        if prose:
            outcome.deferred.append({
                "start": ", ".join(starts),
                "end": capability,
                "provides": prose,
                "used": True,
                "reason": REASON_PROSE,
            })
        if strong:
            _record_use(matrix, capability, strong, context)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def follow_code(matrix: Matrix, scope: FollowScope) -> FollowResult:
    """Correct the ``supportedBy`` guesses of the features a Task builds from what its code uses.

    Args:
        matrix: The matrix, changed in place (the caller holds its lock through ``update_matrix``).
        scope: The Task, its ids, its fetched worktree, its changed files and every Task bead.

    Returns:
        The relationships removed, narrowed, widened and linked, the divergence left as it was
        with its reason, and the ids the matrix holds no entry for.

    Raises:
        MatrixError: The worktree is not a directory, or git cannot list or search its files.

    """
    if not scope.worktree.is_dir():
        message: str = f"the worktree {scope.worktree} is not a directory"
        raise MatrixError(message)
    known: list[EntryId] = [entry_id for entry_id in dict.fromkeys(scope.entry_ids) if matrix.find(entry_id)]
    unknown: list[str] = [entry_id for entry_id in dict.fromkeys(scope.entry_ids) if entry_id not in known]
    outcome: _Outcome = _Outcome([], [], [], [], [])
    changed: dict[str, list[str]] = source_lines(scope.worktree, scope.files)
    place: _Place = _place(matrix, known, scope.worktree)
    result: FollowResult = {
        "ids": [*known],
        "repository": place.repository,
        "refs": [*place.refs],
        "files": sorted(changed),
        "removed": outcome.removed,
        "narrowed": outcome.narrowed,
        "widened": outcome.widened,
        "linked": outcome.linked,
        "deferred": outcome.deferred,
        "unknownIds": unknown,
    }
    if not known:
        return result
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
    _follow_uses(matrix, _product_code(scope.worktree, changed), (starts, reached, place, outcome))
    return result
