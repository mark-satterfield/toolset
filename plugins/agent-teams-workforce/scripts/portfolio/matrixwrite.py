"""The changes a session or a script makes to the matrix: entries, relationships, rulings, the commit.

:func:`put`, :func:`link`, :func:`unlink`, :func:`settle` and :func:`move_repository` each edit a
loaded matrix in place. ``atw-matrix`` runs each inside one locked read-modify-write
(``matrixstore.update_matrix``), which checks the result against the kinds registry before it
writes, so several sessions can record at once and none loses another's change.

- :func:`put` adds one entry of any registered kind, or changes the stated members of one.
- :func:`link` adds one relationship of any registered kind, or changes its attributes;
  :func:`unlink` removes one.
- :func:`put`, :func:`link` and :func:`unlink` each take the side the fact came from: the
  architecture side, which is the authority, or the repository side, which is a hint. The two
  sides are kept apart: a relationship is held once for each side that states it, and what is
  read from a repository never takes the place of what the architecture states.
- :func:`settle` records which statement of a disagreement stands and the rule it was ruled by.
- :func:`move_repository` gives every stack of one repository another repository's name.
- :func:`commit` commits the matrix file alone in the repository that holds it, and pushes it.

Nothing here sets the verified mark (``matrixcode`` sets it), and :func:`approve` leaves it as it
is. The approved and verified marks are plain yes/no marks on the architecture, each cleared on its
own: a change to an entry or a relationship clears its approved mark, except a change to a stack's
``repository`` attribute alone, and a change on the architecture side clears its verified mark too
(``matrixstore.Matrix.put`` and ``Matrix.link``).

The approved mark is set by :func:`approve` alone, which only the script role may run: the step
that promotes a feature's reviewed architecture and design runs it on the matrix content the
Epic's elaboration reached (``matrixtraverse.approval_scope``). :func:`put` and :func:`link` take
attributes only, so neither can state a mark. A change to an entry or relationship, to an
architecture-side relationship an entry starts, or to the text under the document heading that
describes it, clears the mark on that item alone (``matrixstore.Matrix.put`` and ``Matrix.link``).
"""

import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed Git argv without a shell.
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    AUTHORITY_SIDE,
    ENTRY_RULES,
    KIND_DISAGREEMENT,
    KIND_DOCUMENT,
    KIND_EPIC,
    KIND_EVENT,
    KIND_PACKAGE,
    KIND_REQUIREMENT,
    KIND_STACK,
    REL_DISPUTES,
    REL_PUBLISHES,
    ROLE_SCRIPT,
    Entry,
    EntryId,
    EntryKind,
    JsonValue,
    MatrixError,
    Relationship,
    RelationshipKind,
    Role,
    Side,
    as_side,
    entry_json,
    entry_kind,
    json_value,
    relationship_json,
    relationship_kind,
)
from matrixstore import (
    ATTR_EXTERNAL_SOURCE,
    DEFAULT_LOCK_WAIT,
    ID_SEPARATOR,
    Matrix,
    MatrixRefusedError,
    RelationshipId,
    as_entry_id,
    id_stack,
    kind_of,
    make_id,
    matrix_lock,
    relationship_id,
    repository_side_id,
    require_role,
    slug,
    update_matrix,
)
from strictschema import explain_all, validator

if TYPE_CHECKING:
    from matrixtraverse import ApprovalScope

NAMED_ID_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_STACK, KIND_PACKAGE, KIND_EVENT})
"""The kinds whose id is the kind and the entry's name as written: a stack name, a distribution name, a detail type."""
STATED_ID_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_EPIC, KIND_REQUIREMENT, KIND_DOCUMENT})
"""The kinds whose id is built from something other than the name, so a new entry states its id."""
ITEM_ID: Final = "id"
"""The member that identifies one object of a list attribute, such as one thing a feature provides."""
ATTR_REPOSITORY: Final = "repository"
ATTR_HEADING: Final = "heading"
ATTR_STANDS: Final = "stands"
ATTR_RULE: Final = "rule"
ATTR_REASON: Final = "reason"
STANDS_DOCUMENT: Final = "document"
MEMBER_NAME: Final = "name"
MEMBER_ALIASES: Final = "aliases"
MEMBER_PURPOSE: Final = "purpose"
MEMBER_SIDE: Final = "side"
GIT: Final = "git"
GIT_TIMEOUT: Final = 300.0
"""Seconds one git command may take; a push runs the repository's hooks."""
COMMIT_MESSAGE: Final = "chore(matrix): record the matrix"
UPSTREAM_RANGE: Final = "@{upstream}..HEAD"
"""The commits the branch has that the branch it pushes to does not."""
GIT_ATTEMPTS: Final = 3
GIT_RETRY_DELAY: Final = 5.0
"""Attempts at a git command another git process can block, and the pause before the next, in seconds."""
INDEX_LOCK: Final = "index.lock"
REBASE_STATES: Final[tuple[str, ...]] = ("rebase-merge", "rebase-apply")
"""The git paths that exist while a git process holds the index, and while a rebase is stopped."""
CHANGE_SCHEMA_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "schemas" / "matrix-change.schema.json"
)
"""The schema of a matrix change file."""
CHANGE_OPERATIONS: Final = "operations"
"""The member of a change file that holds its operations."""
CHANGE_DEFINITIONS: Final[dict[str, str]] = {"put": "Put", "link": "Link", "unlink": "Unlink", "settle": "Settle"}
"""Each operation a change file may hold, with the schema definition of its arguments; each is the atw-matrix
sub-command of the same name."""
APPROVING_ROLE: Final[Role] = ROLE_SCRIPT
"""The one role that may set the approved mark: the script step that promotes approved architecture and design."""

type View = dict[str, JsonValue]
"""One entry or one relationship as the command prints it."""


class PutResult(TypedDict):
    """What :func:`put` did."""

    id: EntryId
    created: bool
    changed: list[str]
    """The members and attributes whose value the call changed; empty when the entry was as stated."""
    entry: View


class LinkResult(TypedDict):
    """What :func:`link` did."""

    relationship: View
    """The relationship as the matrix now holds it."""
    added: bool
    changed: bool
    """True when the relationship was added or its attributes changed."""


class UnlinkResult(TypedDict):
    """What :func:`unlink` did."""

    relationship: View
    """The relationship removed, or the one asked about when the matrix held none."""
    removed: bool


class SettleResult(TypedDict):
    """What :func:`settle` did."""

    id: EntryId
    stands: View
    """The document and heading of the statement that stands."""
    rule: str
    entry: View


class ApproveResult(TypedDict):
    """What :func:`approve` did."""

    entries: list[EntryId]
    """The entries the call was given that carry the approved mark, in id order; an Epic is never marked."""
    relationships: int
    """How many relationships between them the call was given that carry the approved mark."""
    marked: list[EntryId]
    """The entries whose mark this call set."""
    markedRelationships: int
    """How many relationships had their mark set by this call."""


class ChangeFailure(TypedDict):
    """One operation of a change file that could not be applied, or a fault of the file as a whole."""

    index: int | None
    """The operation's index in ``operations``, from 0; None for a fault of the file as a whole."""
    op: str | None
    """The operation's ``op``; None when the file or the operation names none."""
    error: str


class ApplyResult(TypedDict):
    """What :func:`apply_change_file` did."""

    file: str
    operations: int
    """How many operations the file holds."""
    applied: bool
    """True when every operation was applied and the matrix written; False when nothing was written."""
    failures: list[ChangeFailure]
    """Every operation that failed, in index order; empty when the file was applied."""
    results: list[Mapping[str, object]]
    """What each operation did, in index order, as the sub-command of the same name prints it; empty when
    nothing was applied."""


class MoveResult(TypedDict):
    """What :func:`move_repository` did."""

    old: str
    new: str
    stacks: list[EntryId]
    """The stacks whose repository changed, in id order."""


class CommitResult(TypedDict):
    """What :func:`commit` did."""

    committed: bool
    """False when the matrix file was already as the last commit holds it."""
    pushed: bool
    """False when the branch it pushes to already held every commit of the matrix file."""
    head: str
    """The commit the repository is at afterwards."""
    message: str


def _joined(current: JsonValue, stated: JsonValue) -> JsonValue:
    """Lay one stated value over the value held.

    Returns:
        The stated value; for an object over an object, the held members with the stated ones
        laid over them; for a list over a list, the held items followed by the stated ones not
        held, where a stated object replaces the held object with the same ``id``.

    """
    if isinstance(stated, dict) and isinstance(current, dict):
        return {**current, **stated}
    if not isinstance(stated, list) or not isinstance(current, list):
        return stated
    joined: list[JsonValue] = list(current)
    item: JsonValue
    for item in stated:
        identity: JsonValue = item.get(ITEM_ID) if isinstance(item, dict) else None
        at: int | None = next(
            (
                index
                for index, kept in enumerate(joined)
                if kept == item or (identity is not None and isinstance(kept, dict) and kept.get(ITEM_ID) == identity)
            ),
            None,
        )
        if at is None:
            joined.append(item)
        else:
            joined[at] = item
    return joined


def _laid(current: Mapping[str, JsonValue], stated: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Lay stated attributes over the attributes held.

    Returns:
        The held attributes with each stated one joined in; an attribute stated as null is left out.

    """
    laid: dict[str, JsonValue] = dict(current)
    name: str
    value: JsonValue
    for name, value in stated.items():
        if value is None:
            laid.pop(name, None)
        else:
            laid[name] = _joined(laid.get(name), value)
    return laid


def _derived_id(kind: EntryKind, side: Side, name: str | None, stack: EntryId | None) -> EntryId:
    """Build the id of an entry from its kind, its side and its name.

    An id that does not have the form the kind's ids have raises ``MatrixError`` from ``make_id``
    or ``repository_side_id``.

    Returns:
        The kind, a colon and the slug of the name; the name as written for a kind whose id is
        its name; and for a repository-side entry of a kind with a second id form, the kind, a
        colon, the name of the stack that holds it, a slash and the slug of the name.

    Raises:
        MatrixRefusedError: No name is stated, the kind's ids are not built from the name, or a
            repository-side entry whose id names its stack states no stack.

    """
    message: str
    if kind in STATED_ID_KINDS:
        message = f"the id of a {kind} is not built from its name: state the id"
        raise MatrixRefusedError(message)
    if name is None or not name.strip():
        message = f"a {kind} needs its name, or the id of an entry that exists"
        raise MatrixRefusedError(message)
    if side != AUTHORITY_SIDE and ENTRY_RULES[kind].repository_id_pattern is not None:
        if stack is None:
            message = f"the id of a {kind} on the {side} side names the stack that holds it: state the stack, or the id"
            raise MatrixRefusedError(message)
        return repository_side_id(kind, stack, name)
    return make_id(kind, name.strip() if kind in NAMED_ID_KINDS else slug(name))


def _changed(before: Entry | None, after: Entry) -> list[str]:
    """Name what differs between an entry and the entry that replaces it.

    Returns:
        The common members and the attributes whose value differs, in name order; every stated
        member of an entry that is new.

    """
    held: Mapping[str, JsonValue] = {} if before is None else before.attributes
    changed: set[str] = {name for name in {*held, *after.attributes} if held.get(name) != after.attributes.get(name)}
    if before is None or before.name != after.name:
        changed.add(MEMBER_NAME)
    if (before is None and after.aliases) or (before is not None and before.aliases != after.aliases):
        changed.add(MEMBER_ALIASES)
    if (before is None and after.purpose) or (before is not None and before.purpose != after.purpose):
        changed.add(MEMBER_PURPOSE)
    if before is None or before.side != after.side:
        changed.add(MEMBER_SIDE)
    return sorted(changed)


def _new_entry(matrix: Matrix, key: EntryId, side: Side, name: str | None) -> Entry:
    """Start an entry the matrix does not hold yet.

    Returns:
        The entry with its id, kind, name and side and nothing else.

    Raises:
        MatrixRefusedError: No name is stated, or another entry of the kind answers to the name
            on the same side and, for an entry whose id names its stack, in the same stack.

    """
    kind: EntryKind = kind_of(key)
    message: str
    if name is None or not name.strip():
        message = f"{key} is new: a new {kind} needs its name"
        raise MatrixRefusedError(message)
    started: Entry = Entry(id=key, kind=kind, name=name.strip(), side=side)
    others: list[EntryId] = [
        other.id for other in matrix.named(name, (kind,)) if other.side == side and id_stack(other) == id_stack(started)
    ]
    if others:
        message = (
            f"the {kind} {others[0]} already answers to the name {name.strip()!r} on the {side} side: put that "
            "entry, or qualify this name with the service or subject the new entry belongs to"
        )
        raise MatrixRefusedError(message)
    return started


def _side_kept(existing: Entry | None, side: Side, name: str, purpose: str, stated: Mapping[str, JsonValue]) -> Side:
    """Decide the side an entry carries after a put.

    An entry is on the architecture side once that side states it: a later put from the
    repository side leaves it there, and may add to it but not restate what identifies it: its
    name, its purpose, or, for an event, the outside system that publishes it.

    Returns:
        The stated side for a new entry and for one the architecture side now states; the
        architecture side for an entry already on it.

    Raises:
        MatrixRefusedError: The put is from the repository side, the entry is on the
            architecture side, and the put states another name or purpose for it, or states
            the outside source of an event.

    """
    if existing is None or existing.side != AUTHORITY_SIDE or side == AUTHORITY_SIDE:
        return side
    message: str
    if name != existing.name or purpose != existing.purpose:
        message = (
            f"{existing.id} is on the {existing.side} side: a put from the {side} side does not change its name "
            "or its purpose"
        )
        raise MatrixRefusedError(message)
    if existing.kind == KIND_EVENT and ATTR_EXTERNAL_SOURCE in stated:
        message = (
            f"{existing.id} is on the {existing.side} side; a {side}-side put may not state its {ATTR_EXTERNAL_SOURCE}"
        )
        raise MatrixRefusedError(message)
    return existing.side


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def put(  # ruff: ignore[too-many-arguments] - One keyword per member of an entry a caller may state.
    matrix: Matrix,
    kind: EntryKind,
    side: Side,
    *,
    entry_id: EntryId | None = None,
    name: str | None = None,
    aliases: Sequence[str] = (),
    removed_aliases: Sequence[str] = (),
    purpose: str | None = None,
    attributes: Mapping[str, JsonValue] | None = None,
    stack: EntryId | None = None,
) -> PutResult:
    """Add one entry, or change the stated members of an entry that exists.

    The entry carries the side the fact came from. An entry the repository side recorded moves
    to the architecture side when that side states it. An entry on the architecture side stays
    there: a put from the repository side may add aliases and attributes to it, such as the
    repository that holds a stack, and may not state another name or purpose for it. A thing the
    architecture describes and the thing found in a repository are two entries, so for a
    component, a piece of infrastructure and a layer a repository-side put has its own id, which
    names the stack that holds it.

    Only what is stated changes. A stated name or purpose replaces the one held. Stated aliases
    join the ones held; aliases stated for removal leave them. A stated attribute replaces the
    one held, except that the members of an object are laid over the held object's and the items
    of a list join the held list, where an object with the ``id`` of a held one replaces it; an
    attribute stated as null is removed.
    The approved and verified flags are never stated. A call that changes an entry clears its
    approved flag, unless it changes only the ``repository`` attribute, and on the architecture
    side its verified flag too (``Matrix.put``). A call that states
    what the entry already holds changes nothing. An entry that then breaks its
    kind raises ``MatrixError`` from ``Matrix.put`` and changes nothing.

    Args:
        matrix: The matrix, changed in place.
        kind: The entry's kind.
        side: The side the fact came from: ``architecture`` when beads, a PRD or an arc42
            document states it or the architect designed it; ``repository`` when it was read
            from what is in a repository today.
        entry_id: The entry's id; None builds it from the kind and the name (the slug of the
            name; the name as written for a stack, a package and an event; the stack's name, a
            slash and the slug of the name for a repository-side component, piece of
            infrastructure or layer). An Epic, a requirement and a document state their id.
        name: The entry's name; needed for an entry that is new.
        aliases: Other names the entry is known by.
        removed_aliases: Aliases the entry is no longer known by; one it does not hold changes nothing.
        purpose: One or two sentences that identify the entry.
        attributes: The attributes the kind declares, by name.
        stack: The id of the stack that holds the entry; needed only to build the id of a
            repository-side component, piece of infrastructure or layer. It records no home.

    Returns:
        The entry's id, whether it was created, what changed and the entry.

    Raises:
        MatrixRefusedError: An attribute is not one the kind declares, the id is of another kind,
            a new entry has no name or a name another entry of the kind answers to on its side,
            the id cannot be built from what is stated, a put from the repository side states
            another name or purpose for an entry on the architecture side, or one alias is
            stated both to add and to remove.

    """
    stated: dict[str, JsonValue] = dict(attributes or {})
    message: str
    dropped: set[str] = {alias.strip() for alias in removed_aliases if alias.strip()}
    contested: list[str] = sorted(dropped & {alias.strip() for alias in aliases})
    if contested:
        message = f"the aliases {', '.join(contested)} are stated both to add and to remove"
        raise MatrixRefusedError(message)
    stray: list[str] = sorted(set(stated) - ENTRY_RULES[kind].attributes)
    if stray:
        message = f"a {kind} does not take {', '.join(stray)}; it takes " + (
            ", ".join(sorted(ENTRY_RULES[kind].attributes)) or "no attributes"
        )
        raise MatrixRefusedError(message)
    key: EntryId = _derived_id(kind, side, name, stack) if entry_id is None else as_entry_id(entry_id)
    if kind_of(key) != kind:
        message = f"{key} is not the id of a {kind}"
        raise MatrixRefusedError(message)
    existing: Entry | None = matrix.find(key)
    base: Entry = _new_entry(matrix, key, side, name) if existing is None else existing
    named: str = name.strip() if name is not None and name.strip() else base.name
    described: str = base.purpose if purpose is None else purpose.strip()
    entry: Entry = replace(
        base,
        name=named,
        side=_side_kept(existing, side, named, described, stated),
        aliases=tuple(
            dict.fromkeys(
                alias.strip()
                for alias in (*base.aliases, *aliases)
                if alias.strip() and alias != named and alias.strip() not in dropped
            ),
        ),
        purpose=described,
        attributes=_laid(base.attributes, stated),
    )
    if existing is None or _changed(existing, entry):
        matrix.put(entry)
    stored: Entry = matrix.entry(key)
    return {"id": key, "created": existing is None, "changed": _changed(existing, stored), "entry": entry_json(stored)}


def _held(matrix: Matrix, wanted: Relationship) -> Relationship | None:
    """Find the relationship the matrix holds with the kind, ends, key attributes and side of another.

    Returns:
        The relationship, or None when the matrix holds none.

    """
    identity: RelationshipId = relationship_id(wanted)
    return next(
        (kept for kept in matrix.outgoing(wanted.start, (wanted.kind,)) if relationship_id(kept) == identity),
        None,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def link(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - The parts of a relationship, as the command states them.
    matrix: Matrix,
    kind: RelationshipKind,
    start: EntryId,
    end: EntryId,
    side: Side,
    attributes: Mapping[str, JsonValue] | None = None,
) -> LinkResult:
    """Add one relationship, or change the attributes of the one that exists.

    A relationship is the same relationship when its kind, both ends, its kind's key attributes
    and its side are the same: each side that states a relationship holds its own, and stating
    it for one side leaves the other side's as it is. Stating it again lays the stated attributes
    over the ones held, as :func:`put` does; a change clears its approved flag, and on the
    architecture side its verified flag and both flags of the entry it starts from
    (``Matrix.link``). A relationship that breaks its kind, names an entry the matrix does not
    hold or joins kinds it may not join raises ``MatrixError`` from ``Matrix.link`` and changes
    nothing; so does a second relationship, on one
    side, of a kind an entry may start only one of (``MatrixRefusedError``: unlink the first).

    Args:
        matrix: The matrix, changed in place.
        kind: The relationship's kind.
        start: The entry the relationship starts from.
        end: The entry it ends at.
        side: The side that states the relationship.
        attributes: The attributes the kind declares, by name.

    Returns:
        The relationship as the matrix now holds it, whether it was added and whether it changed.

    """
    wanted: Relationship = Relationship(
        kind=kind,
        start=start,
        end=end,
        side=side,
        attributes=_laid({}, attributes or {}),
    )
    kept: Relationship | None = _held(matrix, wanted)
    stored: Relationship = (
        wanted if kept is None else replace(kept, attributes=_laid(kept.attributes, wanted.attributes))
    )
    changed: bool = kept is None or stored != kept
    if changed:
        matrix.link(stored)
    return {"relationship": relationship_json(stored), "added": kept is None, "changed": changed}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def unlink(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - The parts of a relationship, as the command states them.
    matrix: Matrix,
    kind: RelationshipKind,
    start: EntryId,
    end: EntryId,
    side: Side,
    attributes: Mapping[str, JsonValue] | None = None,
) -> UnlinkResult:
    """Remove one relationship as one side states it.

    The same relationship as the other side states it stays.

    Args:
        matrix: The matrix, changed in place.
        kind: The relationship's kind.
        start: The entry the relationship starts from.
        end: The entry it ends at.
        side: The side whose relationship is removed.
        attributes: The kind's key attributes, such as the heading of a ``describedBy``; the
            other attributes are not compared.

    Returns:
        The relationship removed and True; or the relationship asked about and False when the
        matrix held none with that kind, those ends, those key attributes and that side.

    Raises:
        MatrixRefusedError: The relationship is the last architecture-side publisher of an
            architecture-side event that states no outside source.

    """
    wanted: Relationship = Relationship(
        kind=kind,
        start=start,
        end=end,
        side=side,
        attributes=_laid({}, attributes or {}),
    )
    kept: Relationship | None = _held(matrix, wanted)
    if kept is None:
        return {"relationship": relationship_json(wanted), "removed": False}
    if _last_publisher(matrix, kept):
        message: str = (
            f"{kept.start} is the last service or component the {AUTHORITY_SIDE} side says publishes {kept.end}; "
            f"record another publisher, state its {ATTR_EXTERNAL_SOURCE} or remove the event first"
        )
        raise MatrixRefusedError(message)
    return {"relationship": relationship_json(kept), "removed": matrix.unlink(kept)}


def _last_publisher(matrix: Matrix, relationship: Relationship) -> bool:
    """Report whether a relationship is the only authority-side publisher of an authority-side event.

    Returns:
        True when it is an authority-side publishes relationship, its end is an event on the
        authority side with no outside source, and no other authority-side publisher remains.

    """
    if relationship.kind != REL_PUBLISHES or relationship.side != AUTHORITY_SIDE:
        return False
    event: Entry | None = matrix.find(relationship.end)
    if event is None or event.side != AUTHORITY_SIDE or ATTR_EXTERNAL_SOURCE in event.attributes:
        return False
    return matrix.publishers(relationship.end) == [relationship.start]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def settle(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - The ruling's parts, as the command states them.
    matrix: Matrix,
    entry_id: EntryId,
    document: str,
    heading: str,
    rule: str,
    reason: str = "",
) -> SettleResult:
    """Record which statement of a disagreement stands, and the rule it was ruled by.

    A disagreement the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix, changed in place.
        entry_id: The disagreement's id.
        document: The document that holds the statement that stands: its entry id, or its path
            under the architecture root.
        heading: The heading the statement is under.
        rule: The rule the ruling was made by.
        reason: Why, when the rule does not say it all.

    Returns:
        The disagreement's id, what stands, the rule and the entry.

    Raises:
        ValueError: ``heading`` or ``rule`` is empty.
        MatrixRefusedError: The entry is not a disagreement, or no ``disputes`` relationship of
            it names that document and heading.

    """
    message: str
    if not heading.strip() or not rule.strip():
        message = "a ruling names the heading of the statement that stands and the rule it was made by"
        raise ValueError(message)
    entry: Entry = matrix.entry(entry_id)
    if entry.kind != KIND_DISAGREEMENT:
        message = f"{entry_id} is a {entry.kind}, not a disagreement"
        raise MatrixRefusedError(message)
    prefix: str = f"{KIND_DOCUMENT}{ID_SEPARATOR}"
    standing: EntryId = as_entry_id(document) if document.startswith(prefix) else make_id(KIND_DOCUMENT, document)
    disputed: list[Relationship] = matrix.outgoing(entry_id, (REL_DISPUTES,))
    if not any(
        statement.end == standing and statement.attributes.get(ATTR_HEADING) == heading.strip()
        for statement in disputed
    ):
        stated: str = "; ".join(
            f"{statement.end} under {statement.attributes.get(ATTR_HEADING)!r}" for statement in disputed
        )
        message = f"{entry_id} disputes no statement in {standing} under {heading.strip()!r}; it disputes " + (
            stated or "nothing yet: link its disputes relationships first"
        )
        raise MatrixRefusedError(message)
    stands: View = {STANDS_DOCUMENT: standing, ATTR_HEADING: heading.strip()}
    attributes: dict[str, JsonValue] = {**entry.attributes, ATTR_STANDS: stands, ATTR_RULE: rule.strip()}
    if reason.strip():
        attributes[ATTR_REASON] = reason.strip()
    settled: Entry = replace(entry, attributes=attributes)
    matrix.put(settled)
    return {"id": entry_id, "stands": stands, "rule": rule.strip(), "entry": entry_json(settled)}


def approve(matrix: Matrix, scope: ApprovalScope, role: Role) -> ApproveResult:
    """Set the approved mark on the architecture the solutions architect reviewed and approved.

    Run by the step that promotes reviewed architecture and design, once the reviews pass, in the
    same matrix change that brings the promoted documents' entries up to date. The content is the
    scope the architect reviewed (``matrixtraverse.approval_scope``): every architecture-side entry
    it names except an Epic, which is not architecture, with the architecture-side relationships
    between them. The mark is a plain yes: it records nothing about who approved it. Only the
    approved mark is set: the verified mark each item carries is left as it is, because approving
    the architecture says nothing about what is built (``Matrix.set_flags``).

    Args:
        matrix: The matrix, changed in place.
        scope: The content to approve.
        role: Who is running it.

    Returns:
        The entries and the count of relationships approved, and what this call set.

    Raises:
        MatrixRefusedError: The role is not the one that may set the mark.

    """
    if role != APPROVING_ROLE:
        message: str = f"the role {role} may not set the approved mark; only {APPROVING_ROLE} may"
        raise MatrixRefusedError(message)
    entries: list[EntryId] = [entry_id for entry_id in scope.entries if matrix.entry(entry_id).kind != KIND_EPIC]
    approving: set[EntryId] = set(entries)
    relationships: list[Relationship] = [
        held for held in scope.relationships if held.start in approving and held.end in approving
    ]
    unmarked: list[Relationship] = [held for held in relationships if not held.approved]
    relationship: Relationship
    for relationship in unmarked:
        matrix.set_flags(replace(relationship, approved=True))
    marked: list[EntryId] = []
    entry_id: EntryId
    for entry_id in entries:
        entry: Entry = matrix.entry(entry_id)
        if not entry.approved:
            matrix.set_flags(replace(entry, approved=True))
            marked.append(entry_id)
    return {
        "entries": entries,
        "relationships": len(relationships),
        "marked": marked,
        "markedRelationships": len(unmarked),
    }


class _ChangeRefusedError(MatrixError):
    """At least one operation of a change file failed; raised inside the locked update so nothing is written."""

    def __init__(self, refused: ApplyResult) -> None:
        """Hold what was refused, with every failure."""
        super().__init__(f"{len(refused['failures'])} operation(s) of the change file failed")
        self.refused: ApplyResult = refused


def _text(operation: Mapping[str, JsonValue], member: str) -> str | None:
    """Read a string member of an operation the schema has checked.

    Returns:
        The value, or None when the operation does not state it.

    """
    value: JsonValue = operation.get(member)
    return value if isinstance(value, str) else None


def _texts(operation: Mapping[str, JsonValue], member: str) -> list[str]:
    """Read a list-of-strings member of an operation the schema has checked.

    Returns:
        The strings, or an empty list when the operation does not state it.

    """
    value: JsonValue = operation.get(member)
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _attributes(operation: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Read the attributes an operation states.

    Returns:
        The attributes by name; empty when it states none.

    """
    value: JsonValue = operation.get("attributes")
    return dict(value) if isinstance(value, dict) else {}


def _entry(operation: Mapping[str, JsonValue], member: str) -> EntryId:
    """Read an entry id an operation must state.

    Returns:
        The id.

    Raises:
        MatrixError: The operation does not state it, or it is not an entry id.

    """
    stated: str | None = _text(operation, member)
    if stated is None:
        message: str = f"the operation states no {member}"
        raise MatrixError(message)
    return as_entry_id(stated)


def _apply_put(matrix: Matrix, operation: Mapping[str, JsonValue]) -> PutResult:
    """Apply one ``put`` operation, as ``atw-matrix put`` does.

    Returns:
        What :func:`put` did.

    Raises:
        MatrixRefusedError: ``unset`` names an attribute the operation also states, or
            ``publishedBy`` is stated for another kind than an event or another side than the
            architecture side.

    """
    kind: EntryKind = entry_kind(_text(operation, "kind") or "")
    side: Side = as_side(_text(operation, "side") or "")
    stated: dict[str, JsonValue] = _attributes(operation)
    unset: list[str] = _texts(operation, "unset")
    both: list[str] = sorted(set(unset) & set(stated))
    message: str
    if both:
        message = f"unset names {', '.join(both)}, which the operation also states"
        raise MatrixRefusedError(message)
    published_by: EntryId | None = None if _text(operation, "publishedBy") is None else _entry(operation, "publishedBy")
    if published_by is not None and (kind != KIND_EVENT or side != AUTHORITY_SIDE):
        message = f"publishedBy is stated only for an event the {AUTHORITY_SIDE} side records"
        raise MatrixRefusedError(message)
    result: PutResult = put(
        matrix,
        kind,
        side,
        entry_id=None if _text(operation, "id") is None else _entry(operation, "id"),
        name=_text(operation, "name"),
        aliases=_texts(operation, "aliases"),
        removed_aliases=_texts(operation, "removeAliases"),
        purpose=_text(operation, "purpose"),
        attributes={**stated, **dict.fromkeys(unset)},
        stack=None if _text(operation, "stack") is None else _entry(operation, "stack"),
    )
    if published_by is not None:
        link(matrix, REL_PUBLISHES, published_by, result["id"], AUTHORITY_SIDE)
    return result


def _apply_operation(matrix: Matrix, operation: Mapping[str, JsonValue]) -> Mapping[str, object]:
    """Apply one operation of a change file to a loaded matrix.

    Returns:
        What the operation did, as the sub-command of the same name prints it.

    Raises:
        MatrixError: The operation names no operation this module applies.

    """
    op: str | None = _text(operation, "op")
    if op == "put":
        return _apply_put(matrix, operation)
    if op == "settle":
        stands: list[str] = _texts(operation, "stands")
        return settle(
            matrix,
            _entry(operation, "id"),
            stands[0],
            stands[1],
            _text(operation, "rule") or "",
            _text(operation, "reason") or "",
        )
    if op in {"link", "unlink"}:
        kind: RelationshipKind = relationship_kind(_text(operation, "kind") or "")
        start: EntryId = _entry(operation, "from")
        end: EntryId = _entry(operation, "to")
        side: Side = as_side(_text(operation, "side") or "")
        if op == "link":
            return link(matrix, kind, start, end, side, _attributes(operation))
        return unlink(matrix, kind, start, end, side, _attributes(operation))
    message: str = f"{op!r} is not an operation of a change file; it holds {', '.join(CHANGE_DEFINITIONS)}"
    raise MatrixError(message)


def _failure(index: int | None, op: str | None, error: str) -> ChangeFailure:
    """Name one failure of a change file.

    Returns:
        The failure.

    """
    return {"index": index, "op": op, "error": error}


def _shape_failures(document: JsonValue) -> tuple[list[dict[str, JsonValue]], list[ChangeFailure]]:
    """Check a decoded change file against its schema, each operation against the schema of its ``op``.

    Returns:
        The operations, and a failure for each operation (or for the file) the schema refuses.

    """
    schema: dict[str, JsonValue] = json.loads(CHANGE_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get(CHANGE_OPERATIONS), list):
        return [], [_failure(None, None, f"a change file is an object whose {CHANGE_OPERATIONS} is a list")]
    extra: list[str] = sorted(set(document) - {CHANGE_OPERATIONS})
    failures: list[ChangeFailure] = []
    if extra:
        failures.append(_failure(None, None, f"a change file holds only {CHANGE_OPERATIONS}, not {', '.join(extra)}"))
    operations: list[dict[str, JsonValue]] = []
    listed: JsonValue = document[CHANGE_OPERATIONS]
    index: int
    item: JsonValue
    for index, item in enumerate(listed if isinstance(listed, list) else []):
        operation: dict[str, JsonValue] = item if isinstance(item, dict) else {}
        operations.append(operation)
        op: str | None = _text(operation, "op")
        definition: str | None = CHANGE_DEFINITIONS.get(op or "")
        if definition is None:
            failures.append(_failure(index, op, f"op must be one of {', '.join(CHANGE_DEFINITIONS)}"))
            continue
        checking = validator(
            {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"},
            location=CHANGE_SCHEMA_PATH,
        )
        failures.extend(
            _failure(index, op, problem)
            for problem in explain_all(
                checking.iter_errors(item),
                root=checking.schema if isinstance(checking.schema, dict) else None,
                location=CHANGE_SCHEMA_PATH,
                definition=definition,
            )
        )
    return operations, failures


def _failure_order(failure: ChangeFailure) -> int:
    """Order failures: those of the file as a whole first, then by operation index.

    Returns:
        The sort key.

    """
    return -1 if failure["index"] is None else failure["index"]


def _role_failures(operations: Sequence[Mapping[str, JsonValue]], role: Role) -> list[ChangeFailure]:
    """Refuse each operation the role may not run as the sub-command of the same name.

    Returns:
        A failure for each operation the registry's command table does not allow the role.

    """
    failures: list[ChangeFailure] = []
    index: int
    operation: Mapping[str, JsonValue]
    for index, operation in enumerate(operations):
        op: str | None = _text(operation, "op")
        try:
            require_role(op or "", role)
        except MatrixError as error:
            failures.append(_failure(index, op, str(error)))
    return failures


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def apply_changes(matrix: Matrix, change_file: Path, role: Role) -> ApplyResult:
    """Apply a whole matrix change file to a loaded matrix, and report every failure.

    The file is checked against ``matrix-change.schema.json``, each operation against the
    schema of its ``op``, and each operation against the registry's command table for the
    role, as ``atw-matrix`` checks the sub-command of the same name. The operations the checks
    pass are applied in order to ``matrix``, each as the sub-command of the same name applies
    it. The operations after a failed one are still tried, against the matrix as the operations
    before them left it, so a failure that follows from an earlier one is reported too. Nothing
    is written: a caller that wants the file applied writes the matrix only when no failure is
    reported (:func:`apply_change_file`), and a caller that only checks it passes a matrix it
    never writes.

    Args:
        matrix: The matrix, changed in place, also when a failure is reported.
        change_file: The change file.
        role: Who wrote the change file: the role each operation is checked for.

    Returns:
        The file, how many operations it holds, whether every operation was applied, every
        failure in index order (those of the file as a whole first) and what each applied
        operation did.

    """
    result: ApplyResult = {"file": str(change_file), "operations": 0, "applied": False, "failures": [], "results": []}
    try:
        document: JsonValue = json_value(json.loads(change_file.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as error:
        result["failures"] = [_failure(None, None, f"cannot read {change_file}: {error}")]
        return result
    operations, failed = _shape_failures(document)
    failed.extend(_role_failures(operations, role))
    result["operations"] = len(operations)
    skipped: set[int] = {failure["index"] for failure in failed if failure["index"] is not None}
    results: list[Mapping[str, object]] = []
    index: int
    operation: dict[str, JsonValue]
    for index, operation in enumerate(operations):
        if index in skipped:
            continue
        try:
            results.append(_apply_operation(matrix, operation))
        except (MatrixError, ValueError, TypeError) as error:
            failed.append(_failure(index, _text(operation, "op"), str(error)))
    result["failures"] = sorted(failed, key=_failure_order)
    result["results"] = results
    result["applied"] = not failed
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def apply_change_file(
    path: Path,
    change_file: Path,
    role: Role,
    *,
    wait: float = DEFAULT_LOCK_WAIT,
) -> ApplyResult:
    """Apply a whole matrix change file in one locked update of the matrix, or none of it.

    Under the matrix's lock the file is applied to one read of the matrix as
    :func:`apply_changes` applies it, and the matrix is written once. When any check or
    operation fails, every failure is reported with its operation's index and nothing is
    written, so one correction of the file can address them all.

    Args:
        path: The matrix file.
        change_file: The change file.
        role: Who wrote the change file: the role each operation is checked for.
        wait: Seconds to wait for the matrix's lock.

    Returns:
        The file, how many operations it holds, whether it was applied, every failure and what
        each operation did; no results when nothing was applied.

    """

    def change(matrix: Matrix) -> ApplyResult:
        applied: ApplyResult = apply_changes(matrix, change_file, role)
        if applied["failures"]:
            raise _ChangeRefusedError(applied)
        return applied

    try:
        return update_matrix(path, change, wait=wait)
    except _ChangeRefusedError as error:
        return {**error.refused, "applied": False, "results": []}
    except MatrixError as error:
        return {
            "file": str(change_file),
            "operations": 0,
            "applied": False,
            "failures": [_failure(None, None, str(error))],
            "results": [],
        }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def move_repository(matrix: Matrix, old: str, new: str) -> MoveResult:
    """Give every stack of one repository another repository's name.

    No id changes: the repository is an attribute of a stack. Each stack keeps its side.

    Args:
        matrix: The matrix, changed in place.
        old: The repository's name as the stacks hold it now.
        new: The name they are to hold.

    Returns:
        Both names and the stacks whose repository changed; none when no stack named ``old``.

    Raises:
        ValueError: A name is empty, or the two are the same.

    """
    if not old.strip() or not new.strip() or old.strip() == new.strip():
        message: str = "move-repository needs the repository's name now and a different name to give it"
        raise ValueError(message)
    moved: list[EntryId] = []
    stack: Entry
    for stack in matrix.entries((KIND_STACK,)):
        if stack.attributes.get(ATTR_REPOSITORY) == old.strip():
            matrix.put(replace(stack, attributes={**stack.attributes, ATTR_REPOSITORY: new.strip()}))
            moved.append(stack.id)
    return {"old": old.strip(), "new": new.strip(), "stacks": moved}


def _git(root: Path, *arguments: str) -> str:
    """Run one git command in a directory.

    Returns:
        What the command printed, without the white space around it.

    Raises:
        MatrixError: git is not installed, did not run, ran out of time or exited with a failure.

    """
    command: str = f"git {' '.join(arguments)} in {root}"
    message: str
    executable: str | None = shutil.which(GIT)
    if executable is None:
        message = f"cannot run {command}: git is not on the PATH"
        raise MatrixError(message)
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved Git executable and separate argv.
            [executable, "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        message = f"cannot run {command}: {error}"
        raise MatrixError(message) from error
    if result.returncode != 0:
        message = f"{command} failed with exit status {result.returncode}: {(result.stderr or result.stdout).strip()}"
        raise MatrixError(message)
    return result.stdout.strip()


def _git_path(root: Path, name: str) -> Path:
    """Name a path inside the repository's git directory.

    Returns:
        The path ``git rev-parse --git-path`` gives, resolved against the repository.

    """
    return root / _git(root, "rev-parse", "--git-path", name)


def _git_retried(root: Path, *arguments: str) -> str:
    """Run one git command, again after a pause while another git process holds the index lock.

    Returns:
        What the command printed, without the white space around it.

    Raises:
        MatrixError: The command failed while no git process held the index lock, or on its last attempt.

    """
    attempt: int
    for attempt in range(1, GIT_ATTEMPTS + 1):
        try:
            return _git(root, *arguments)
        except MatrixError:
            if attempt == GIT_ATTEMPTS or not _git_path(root, INDEX_LOCK).exists():
                raise
            time.sleep(GIT_RETRY_DELAY * attempt)
    message: str = f"git {' '.join(arguments)} in {root} made no attempt"
    raise MatrixError(message)


def _rebase(root: Path) -> None:
    """Rebase the branch on the branch it pushes to, keeping uncommitted changes (``--autostash``).

    A rebase git stops is aborted, which puts the branch and the stashed changes back as they were.

    Raises:
        MatrixError: The pull failed; the message names what git printed.

    """
    try:
        _git_retried(root, "pull", "--rebase", "--autostash")
    except MatrixError:
        if any(_git_path(root, state).exists() for state in REBASE_STATES):
            _git(root, "rebase", "--abort")
        raise


def _push(root: Path, path: Path, file: Path, wait: float) -> bool:
    """Push the commits of the matrix file, rebasing on the branch it pushes to first.

    Each attempt rebases under the matrix's lock, so no matrix write is stashed or overwritten by
    the rebase, then pushes outside it. A push the remote rejects, because its branch moved after
    the rebase, is tried again after a pause and another rebase.

    Returns:
        False when the branch it pushes to already held every commit of the matrix file.

    Raises:
        MatrixError: The rebase failed, or the push failed on its last attempt.

    """
    attempt: int
    for attempt in range(1, GIT_ATTEMPTS + 1):
        with matrix_lock(path, wait):
            if not _git(root, "log", "--format=%H", UPSTREAM_RANGE, "--", str(file)):
                return False
            _rebase(root)
        try:
            _git_retried(root, "push")
        except MatrixError:
            if attempt == GIT_ATTEMPTS:
                raise
            time.sleep(GIT_RETRY_DELAY * attempt)
        else:
            return True
    message: str = f"the push of {file} made no attempt"
    raise MatrixError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def commit(path: Path, bead: str = "", *, wait: float = DEFAULT_LOCK_WAIT) -> CommitResult:
    """Commit the matrix file alone in the repository that holds it, and push it.

    Whatever else the repository has staged or changed is left as it is. The commit is made
    under the matrix's lock, so it holds the file as one change left it. Before the push the
    branch is rebased on the branch it pushes to with ``--autostash``, under the matrix's lock;
    the push follows outside it, and a rejected push is rebased and tried again (:func:`_push`).
    A git command another git process blocks with the index lock is tried again after a pause.
    The repository's own commit and push hooks run. A matrix file that is as the last commit
    holds it is not committed again, and is pushed only when the branch it pushes to lacks a
    commit of it. A git command that fails raises ``MatrixError`` naming the command and what
    git printed; a commit already made stays, and the next call pushes it.

    Args:
        path: The matrix file.
        bead: The beads id of the Epic or Story the recorded changes belong to; the commit
            message names it. Empty for a change no bead owns.
        wait: Seconds to wait for the matrix's lock.

    Returns:
        Whether a commit was made, whether it was pushed, the commit the repository is at and
        the commit message.

    Raises:
        MatrixError: There is no matrix at ``path``.

    """
    if not path.is_file():
        message: str = f"there is no matrix at {path}"
        raise MatrixError(message)
    file: Path = path.resolve()
    root: Path = Path(_git(file.parent, "rev-parse", "--show-toplevel"))
    subject: str = f"{COMMIT_MESSAGE} for {bead.strip()}" if bead.strip() else COMMIT_MESSAGE
    with matrix_lock(path, wait):
        committed: bool = bool(_git(root, "status", "--porcelain", "--", str(file)))
        if committed:
            _git_retried(root, "add", "--", str(file))
            _git_retried(root, "commit", "-m", subject, "--", str(file))
    pushed: bool = _push(root, path, file, wait)
    return {"committed": committed, "pushed": pushed, "head": _git(root, "rev-parse", "HEAD"), "message": subject}
