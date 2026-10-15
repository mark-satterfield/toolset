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

Nothing here sets or clears the verified mark: an entry or a relationship that is added carries
none, and one that is changed keeps the mark it has.

The architecture-approved mark is set by :func:`approve` alone, which only the script role may
run: the step that promotes an Epic's reviewed architecture runs it for the Epic's requirements
and the features that serve them. :func:`put` refuses to state the mark. A change to an approved
entry, or to a document that describes it, clears the mark (``matrixstore.Matrix.put``).
"""

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed Git argv without a shell.
import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

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
    entry_json,
    relationship_json,
)
from matrixstore import (
    APPROVAL_EPIC,
    ATTR_ARCHITECTURE_APPROVED,
    ATTR_EXTERNAL_SOURCE,
    DEFAULT_LOCK_WAIT,
    ID_SEPARATOR,
    Matrix,
    MatrixRefusedError,
    RelationshipId,
    approved_by,
    as_entry_id,
    id_stack,
    kind_of,
    make_id,
    matrix_lock,
    relationship_id,
    repository_side_id,
    slug,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

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
APPROVING_ROLE: Final[Role] = ROLE_SCRIPT
"""The one role that may set the architecture-approved mark: the script step that promotes an Epic's architecture."""

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

    epic: EntryId
    requirements: list[EntryId]
    """The Epic's requirements, each now carrying the mark, in id order."""
    features: list[EntryId]
    """The features that serve them, each now carrying the mark, in id order."""
    marked: list[EntryId]
    """Those of them whose mark this call set or changed."""


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


def put(  # ruff: ignore[too-many-arguments] - One keyword per member of an entry a caller may state.
    matrix: Matrix,
    kind: EntryKind,
    side: Side,
    *,
    entry_id: EntryId | None = None,
    name: str | None = None,
    aliases: Sequence[str] = (),
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
    join the ones held. A stated attribute replaces the one held, except that the members of an
    object are laid over the held object's and the items of a list join the held list, where an
    object with the ``id`` of a held one replaces it; an attribute stated as null is removed.
    The verified mark is left as it is. The architecture-approved mark is never stated; a call
    that changes an approved entry clears it (``Matrix.put``), and ``changed`` then names it. A
    call that states what the entry already holds changes nothing. An entry that then breaks its
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
        purpose: One or two sentences that identify the entry.
        attributes: The attributes the kind declares, by name.
        stack: The id of the stack that holds the entry; needed only to build the id of a
            repository-side component, piece of infrastructure or layer. It records no home.

    Returns:
        The entry's id, whether it was created, what changed and the entry.

    Raises:
        MatrixRefusedError: An attribute is not one the kind declares or is the
            architecture-approved mark, the id is of another kind,
            a new entry has no name or a name another entry of the kind answers to on its side,
            the id cannot be built from what is stated, or a put from the repository side states
            another name or purpose for an entry on the architecture side.

    """
    stated: dict[str, JsonValue] = dict(attributes or {})
    message: str
    stray: list[str] = sorted(set(stated) - ENTRY_RULES[kind].attributes)
    if stray:
        message = f"a {kind} does not take {', '.join(stray)}; it takes " + (
            ", ".join(sorted(ENTRY_RULES[kind].attributes)) or "no attributes"
        )
        raise MatrixRefusedError(message)
    if ATTR_ARCHITECTURE_APPROVED in stated:
        message = (
            f"{ATTR_ARCHITECTURE_APPROVED} is set only by the step that promotes an Epic's reviewed architecture, "
            "never by a put"
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
            dict.fromkeys(alias.strip() for alias in (*base.aliases, *aliases) if alias.strip() and alias != named),
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
    over the ones held, as :func:`put` does, and leaves its verified mark as it is. A relationship that breaks its
    kind, names an entry the matrix does not hold or joins kinds it may not join raises
    ``MatrixError`` from ``Matrix.link`` and changes nothing; so does a second relationship, on one
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


def approve(matrix: Matrix, bead: str, role: Role) -> ApproveResult:
    """Set the architecture-approved mark on an Epic's requirements and the features that serve them.

    Run by the step that promotes an Epic's reviewed architecture, once the reviews pass, in the
    same matrix change that brings the promoted documents' entries up to date. The mark names
    the Epic. An entry that already carries the Epic's mark is left as it is. An Epic the matrix
    does not hold raises ``MatrixError`` from ``Matrix.approval_scope``.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic's beads id.
        role: Who is running it.

    Returns:
        The Epic, its requirements and features, and those whose mark this call set or changed.

    Raises:
        MatrixRefusedError: The role is not the one that may set the mark.
        ValueError: ``bead`` is empty.

    """
    message: str
    if role != APPROVING_ROLE:
        message = f"the role {role} may not set {ATTR_ARCHITECTURE_APPROVED}; only {APPROVING_ROLE} may"
        raise MatrixRefusedError(message)
    if not bead.strip():
        message = "approve needs the Epic's beads id"
        raise ValueError(message)
    epic: EntryId = make_id(KIND_EPIC, bead.strip())
    requirements: list[EntryId]
    features: list[EntryId]
    requirements, features = matrix.approval_scope(epic)
    unmarked: list[Entry] = [
        entry
        for entry in (matrix.entry(entry_id) for entry_id in (*requirements, *features))
        if approved_by(entry) != bead.strip()
    ]
    entry: Entry
    for entry in unmarked:
        mark: JsonValue = {APPROVAL_EPIC: bead.strip()}
        matrix.put(replace(entry, attributes={**entry.attributes, ATTR_ARCHITECTURE_APPROVED: mark}))
    return {
        "epic": epic,
        "requirements": requirements,
        "features": features,
        "marked": [entry.id for entry in unmarked],
    }


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


def commit(path: Path, bead: str = "", *, wait: float = DEFAULT_LOCK_WAIT) -> CommitResult:
    """Commit the matrix file alone in the repository that holds it, and push it.

    Whatever else the repository has staged or changed is left as it is. The commit is made
    under the matrix's lock, so it holds the file as one change left it; the push follows. The
    repository's own commit and push hooks run. A matrix file that is as the last commit holds
    it is not committed again, and is pushed only when the branch it pushes to lacks a commit of
    it. A git command that fails raises ``MatrixError`` naming the command and what git printed;
    a commit already made stays, and the next call pushes it.

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
            _git(root, "add", "--", str(file))
            _git(root, "commit", "-m", subject, "--", str(file))
    pushed: bool = bool(_git(root, "log", "--format=%H", UPSTREAM_RANGE, "--", str(file)))
    if pushed:
        _git(root, "push")
    return {"committed": committed, "pushed": pushed, "head": _git(root, "rev-parse", "HEAD"), "message": subject}
