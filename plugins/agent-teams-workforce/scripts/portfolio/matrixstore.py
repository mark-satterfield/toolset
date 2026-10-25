"""The matrix file: where it is, how it is locked, read and written, and the matrix it holds in memory.

The matrix is one JSON file (``ops/sdlc-automation/matrix.json`` in the control repository unless
the caller or the environment names another). It holds entries by id and relationships, each
stored once for each side that states it. Every entry and every relationship carries its side:
the architecture side, which is the authority, or the repository side, which is a hint. The
generic shape of the file is ``skills/artifact-handoff/schemas/matrix.schema.json``
and the kinds of entry and relationship are declared in ``matrix-kinds.json`` beside it (the kinds
registry); every type, value and check of either comes from ``matrix_contract``, the module
generated from both.

:class:`Matrix` is the matrix in memory: generic entries and relationships of any registered kind,
with an index that answers a relationship from both of its ends. Every change to the file is one
read-modify-write under an exclusive lock (:func:`update_matrix`), checked against the registry,
written to a temporary file in the matrix's directory and moved into place. A read takes no lock:
a write replaces the file in one move.
"""

import fcntl
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Callable, Collection, Generator, Mapping
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Final, NamedTuple

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import (
    AUTHORITY_SIDE,
    COMMAND_RULES,
    DEFAULT_MATRIX_PARTS,
    ENTRY_ID_PATTERN,
    ENTRY_RULES,
    HOME_RELATIONSHIP,
    KIND_DOCUMENT,
    KIND_EVENT,
    KIND_INFRASTRUCTURE,
    LOCK_DIRECTORY,
    LOCK_SUFFIX,
    MATRIX_ENV,
    OPERATOR_ROLE,
    REL_DESCRIBED_BY,
    REL_MATCHES,
    REL_PUBLISHES,
    ROLE_ENV,
    ROLES,
    STACK_KIND,
    Approved,
    Entry,
    EntryId,
    EntryKind,
    EntryRule,
    JsonValue,
    MatrixDocument,
    MatrixError,
    Relationship,
    RelationshipKind,
    RelationshipRule,
    Role,
    Side,
    document_json,
    entry_kind,
    entry_problems,
    parse_document,
    relationship_key,
    relationship_label,
    relationship_problems,
    relationship_rule,
)

DEFAULT_LOCK_WAIT: Final = 60.0
"""Seconds a change waits for another process's change to the same matrix to finish."""
LOCK_POLL: Final = 0.05
FILE_MODE: Final = 0o644
"""The mode of a matrix file: it is committed to the control repository and read by every session."""
ID_SEPARATOR: Final = ":"
STACK_SEPARATOR: Final = "/"
"""What follows the stack name in the id of an entry whose id names the stack that holds it."""
SLUG_SEPARATOR: Final = "-"
ATTR_EXTERNAL_SOURCE: Final = "externalSource"
"""The event attribute that names the system outside the project that publishes it."""
ATTR_RESOURCE_TYPE: Final = "resourceType"
RESOURCE_EVENTBRIDGE_RULE: Final = "eventbridge-rule"
"""The resource type of an EventBridge rule: it belongs to one bus, matches events and routes them to targets."""
ATTR_MATCHES_ALL_EVENTS: Final = "matchesAllEvents"
"""The rule attribute that says its event pattern matches every event on its bus."""
PROBLEMS_SHOWN: Final = 20
"""The most problems an error message lists."""
ATTR_HEADING_HASHES: Final = "headingHashes"
"""The document attribute that holds the hash of each heading's own text, by heading."""
ATTR_HEADINGS: Final = "headings"
"""The document attribute that lists the document's headings as the vault holds them."""
ATTR_HEADING: Final = "heading"
"""The attribute of a relationship to a document that names the document heading it rests on."""
ATTR_REPOSITORY: Final = "repository"
"""The stack attribute that names the repository which holds the stack."""
ATTR_EPIC_DRIVER: Final = "epicDriver"
"""The stack attribute by which the owner says no Epic drives the stack."""
OUTSIDE_APPROVAL: Final[frozenset[str]] = frozenset({ATTR_REPOSITORY, ATTR_EPIC_DRIVER})
"""The attributes whose change alone keeps the approved flag: neither changes an approved design."""
_NOT_SLUG: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


class MatrixRefusedError(MatrixError):
    """The matrix refuses the request in the state it is in, or for the role that asked."""


class MatrixLockTimeoutError(MatrixError):
    """Another process held the matrix's lock for the whole wait."""


class RelationshipId(NamedTuple):
    """What tells one relationship from every other: the order a matrix file lists them in."""

    start: EntryId
    kind: RelationshipKind
    end: EntryId
    key: str
    """The values of the kind's key attributes, as ``relationship_key`` renders them."""
    side: Side
    """The side that states the relationship; each side that states one stores its own."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def name_key(name: str) -> str:
    """Reduce a name to the form names are compared in.

    Args:
        name: A name as a document or a caller writes it.

    Returns:
        The name with runs of white space collapsed to one space, case-folded.

    Raises:
        TypeError: ``name`` is not a string.

    """
    if not isinstance(name, str):
        message: str = "a name must be a string"
        raise TypeError(message)
    return " ".join(name.split()).casefold()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def slug(name: str) -> str:
    """Reduce a name to the slug an id is built from.

    Args:
        name: The entry's name.

    Returns:
        The name's lowercase words joined by hyphens.

    Raises:
        TypeError: ``name`` is not a string.
        ValueError: The name holds no letter or digit.

    """
    message: str
    if not isinstance(name, str):
        message = "a name must be a string"
        raise TypeError(message)
    reduced: str = _NOT_SLUG.sub(SLUG_SEPARATOR, name.casefold()).strip(SLUG_SEPARATOR)
    if not reduced:
        message = f"the name {name!r} holds no letter or digit to build an id from"
        raise ValueError(message)
    return reduced


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def as_entry_id(text: str) -> EntryId:
    """Accept a string as an entry id when it has the form of one.

    A kind the registry does not declare raises ``MatrixError`` from ``entry_kind``.

    Args:
        text: The candidate id.

    Returns:
        The same text, typed.

    Raises:
        MatrixError: The text is not a kind, a colon and the rest, or does not have a form the
            kind's ids have on either side.

    """
    message: str
    if not isinstance(text, str) or ENTRY_ID_PATTERN.search(text) is None:
        message = f"{text!r} is not an entry id: it must match {ENTRY_ID_PATTERN.pattern}"
        raise MatrixError(message)
    kind: EntryKind = entry_kind(text.partition(ID_SEPARATOR)[0])
    rule: EntryRule = ENTRY_RULES[kind]
    forms: list[re.Pattern[str]] = [rule.id_pattern]
    if rule.repository_id_pattern is not None:
        forms.append(rule.repository_id_pattern)
    if all(form.search(text) is None for form in forms):
        allowed: str = " or ".join(form.pattern for form in forms)
        message = f"{text!r} is not the id of a {kind}: it must match {allowed}"
        raise MatrixError(message)
    return EntryId(text)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def make_id(kind: EntryKind, rest: str) -> EntryId:
    """Build an entry id from the entry's kind and the rest of the id.

    An id that does not have the form the kind's ids have raises ``MatrixError`` from
    :func:`as_entry_id`.

    Args:
        kind: The entry's kind.
        rest: What follows the colon: the slug of the name (:func:`slug`) unless the kind's ids
            are built from something else, such as a beads id or a document path.

    Returns:
        ``<kind>:<rest>``.

    Raises:
        ValueError: ``rest`` is empty.

    """
    if not rest:
        message: str = f"a {kind} id needs something after the colon"
        raise ValueError(message)
    return as_entry_id(f"{kind}{ID_SEPARATOR}{rest}")


def kind_of(entry_id: EntryId) -> EntryKind:
    """Read the kind an entry id states.

    An id that starts with no registered kind raises ``MatrixError`` from ``entry_kind``.

    Args:
        entry_id: An entry id.

    Returns:
        The kind before the colon.

    """
    return entry_kind(entry_id.partition(ID_SEPARATOR)[0])


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_side_id(kind: EntryKind, stack: EntryId, name: str) -> EntryId:
    """Build the id of an entry that is not on the authority side, for a kind with two id forms.

    Such an entry is what is in a stack's repository today. Its id names the stack, so that it
    never takes the id of the architecture-side entry it corresponds to. A name that holds no
    letter or digit raises ``ValueError`` from :func:`slug`, and an id that does not have the
    form raises ``MatrixError`` from :func:`as_entry_id`.

    Args:
        kind: The entry's kind, one whose registry declaration has a second id form.
        stack: The id of the stack that holds the entry.
        name: The entry's name.

    Returns:
        ``<kind>:<stack name>/<slug of the name>``.

    Raises:
        MatrixError: The kind has one id form, or ``stack`` is not the id of a stack.

    """
    message: str
    if ENTRY_RULES[kind].repository_id_pattern is None:
        message = f"a {kind} has one id form on both sides; build its id with make_id"
        raise MatrixError(message)
    if kind_of(stack) != STACK_KIND:
        message = f"{stack} is not the id of a {STACK_KIND}"
        raise MatrixError(message)
    return make_id(kind, f"{stack.partition(ID_SEPARATOR)[2]}{STACK_SEPARATOR}{slug(name)}")


def id_stack(entry: Entry) -> EntryId | None:
    """Name the stack an entry's id names.

    Args:
        entry: An entry.

    Returns:
        The id of the stack, for an entry that is not on the authority side and whose kind has a
        second id form; None for every other entry, and for an id that does not have that form.

    """
    form: re.Pattern[str] | None = ENTRY_RULES[entry.kind].repository_id_pattern
    if entry.side == AUTHORITY_SIDE or form is None or form.search(entry.id) is None:
        return None
    rest: str = entry.id.partition(ID_SEPARATOR)[2]
    return EntryId(f"{STACK_KIND}{ID_SEPARATOR}{rest.rpartition(STACK_SEPARATOR)[0]}")


def relationship_id(relationship: Relationship) -> RelationshipId:
    """Name what tells a relationship from every other.

    Args:
        relationship: The relationship.

    Returns:
        Its start, kind, end, the values of its kind's key attributes, and the side that states it.

    """
    return RelationshipId(
        relationship.start,
        relationship.kind,
        relationship.end,
        relationship_key(relationship),
        relationship.side,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def dirtied[T: (Entry, Relationship)](item: T) -> T:
    """Take both flags off an entry or a relationship a change affects.

    Args:
        item: An entry or a relationship of any kind.

    Returns:
        The item without the approved and the verified flag; the item itself when it carries neither.

    """
    if item.approved is None and item.verified is None:
        return item
    return replace(item, approved=None, verified=None)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def same_content[T: (Entry, Relationship)](held: T, item: T) -> bool:
    """Tell whether two entries, or two relationships, differ in nothing but the approved and verified flags.

    Args:
        held: The entry or relationship the matrix holds.
        item: The one that is to replace it.

    Returns:
        True when the two are equal once both flags are taken off both.

    """
    return replace(held, approved=None, verified=None) == replace(item, approved=None, verified=None)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approved_by(item: Entry | Relationship) -> str | None:
    """Read which Epic's approval an entry or a relationship carries.

    Args:
        item: An entry or a relationship of any kind.

    Returns:
        The beads id of the Epic the approved flag names; None when it carries no flag, which
        means not approved.

    """
    return None if item.approved is None else item.approved.epic


def _flags_settled[T: (Entry, Relationship)](held: T | None, item: T) -> T:
    """Decide the flags an entry or a relationship carries once it replaces the one held.

    Each flag is a dirty bit settled on its own. A change that leaves everything but the flags
    as it was keeps both flags the held item carries. A change to the ``repository`` or the
    ``epicDriver`` attribute alone keeps the approved flag: the name of the repository that holds a
    stack is given when the Epic's repositories are spanned, after its design was approved, and the
    owner's decision that no Epic drives a stack orders Epics; neither changes anything the
    approval covers. Any other change clears the approved flag. A change clears the verified flag
    only when the item is on the architecture side, because only that side states what the item
    must be built as; a repository-side change keeps it. Flags the replacing item states are not
    taken: only :meth:`Matrix.set_flags` sets a flag.

    Returns:
        The item as given when it is new; otherwise the item with the flags settled as above.

    """
    if held is None:
        return item
    if same_content(held, item):
        return replace(item, approved=held.approved, verified=held.verified)
    authority: bool = AUTHORITY_SIDE in {held.side, item.side}
    approved: Approved | None = held.approved if _outside_approval_alone_changed(held, item) else None
    return replace(item, approved=approved, verified=None if authority else held.verified)


def _outside_approval_alone_changed[T: (Entry, Relationship)](held: T, item: T) -> bool:
    """Tell whether two entries, or two relationships, differ in nothing but the flags and ``OUTSIDE_APPROVAL``.

    Returns:
        True when the two are equal once the flags and the attributes outside approval are taken off both.

    """

    def without(value: T) -> T:
        attributes: dict[str, JsonValue] = {
            name: attribute for name, attribute in value.attributes.items() if name not in OUTSIDE_APPROVAL
        }
        return replace(value, attributes=attributes, approved=None, verified=None)

    return without(held) == without(item)


def _changed_headings(held: Entry | None, entry: Entry) -> frozenset[str] | None:
    """Name the headings whose own text a change to a document entry changed.

    The front matter belongs to no heading, so the move of a document to effective changes none.

    Returns:
        None when the entry is not a document the matrix held; otherwise each heading whose hash
        differs, or that one of the two has and the other lacks.

    """
    if held is None or entry.kind != KIND_DOCUMENT or held.kind != KIND_DOCUMENT:
        return None
    before: JsonValue = held.attributes.get(ATTR_HEADING_HASHES)
    after: JsonValue = entry.attributes.get(ATTR_HEADING_HASHES)
    old: dict[str, JsonValue] = before if isinstance(before, dict) else {}
    new: dict[str, JsonValue] = after if isinstance(after, dict) else {}
    return frozenset(heading for heading in {*old, *new} if old.get(heading) != new.get(heading))


def _document_end(relationship: Relationship) -> EntryId | None:
    """Name the end of a relationship that is a document entry.

    Returns:
        The end when it is a document, else the start when it is one; None when neither is.

    """
    if kind_of(relationship.end) == KIND_DOCUMENT:
        return relationship.end
    if kind_of(relationship.start) == KIND_DOCUMENT:
        return relationship.start
    return None


def _selected[T](kinds: Collection[T] | None, kind: T) -> bool:
    """Tell whether a kind is among those a read asked for.

    Returns:
        True when the read named no kinds, or named this one.

    """
    return kinds is None or kind in kinds


def _raise_problems(problems: list[str], where: str) -> None:
    """Refuse something that breaks the registry or the rules between entries.

    Raises:
        MatrixError: There is at least one problem.

    """
    if problems:
        shown: str = "; ".join(problems[:PROBLEMS_SHOWN])
        message: str = f"{where} does not conform ({len(problems)} problems): {shown}"
        raise MatrixError(message)


class Matrix:
    """The matrix in memory: entries by id, relationships once for each side, and an index of both ends.

    An entry or a relationship is of any kind the registry declares; nothing here names a kind
    except the registry's home relationship, which :meth:`home` reads and :meth:`remove` follows
    for ``held``, the registry's stack kind, whose name is part of the id of an entry that
    is what a stack's repository holds today (:func:`id_stack`), and the event kind with its
    publishes relationship: an event's stack is its publisher's (:meth:`publisher_stacks`), and
    an authority-side event states when it is triggered (:meth:`_event_problems`); and, for the
    approved and verified flags, the documents that describe an entry (:meth:`put`).

    The two sides are kept apart. A relationship is stored once for each side that states it. An
    entry on the authority side never becomes a repository-side entry (:meth:`put`).
    """

    def __init__(self, document: MatrixDocument | None = None) -> None:
        """Index a matrix file, or start an empty matrix.

        Args:
            document: The typed file; None starts a matrix that holds nothing.

        Raises:
            MatrixError: Two entries share an id, or two relationships share a kind, both ends,
                the values of the kind's key attributes and a side.

        """
        source: MatrixDocument = MatrixDocument() if document is None else document
        self._entries: dict[EntryId, Entry] = {}
        self._relationships: dict[RelationshipId, Relationship] = {}
        self._starting: dict[EntryId, set[RelationshipId]] = {}
        self._ending: dict[EntryId, set[RelationshipId]] = {}
        message: str
        entry: Entry
        for entry in source.entries:
            if entry.id in self._entries:
                message = f"the matrix holds two entries with the id {entry.id}"
                raise MatrixError(message)
            self._entries[entry.id] = entry
        relationship: Relationship
        for relationship in source.relationships:
            if relationship_id(relationship) in self._relationships:
                message = f"the matrix holds the relationship {relationship_label(relationship)} twice"
                raise MatrixError(message)
            self._add(relationship)

    def _add(self, relationship: Relationship) -> None:
        """File a relationship and index both of its ends."""
        identity: RelationshipId = relationship_id(relationship)
        self._relationships[identity] = relationship
        self._starting.setdefault(relationship.start, set()).add(identity)
        self._ending.setdefault(relationship.end, set()).add(identity)

    def _drop(self, identity: RelationshipId) -> None:
        """Take a relationship out of the matrix and out of the index of both ends."""
        del self._relationships[identity]
        self._starting[identity.start].discard(identity)
        self._ending[identity.end].discard(identity)

    def document(self) -> MatrixDocument:
        """Render the matrix as the typed form of its file.

        Returns:
            The entries in id order and the relationships in file order.

        """
        return MatrixDocument(entries=tuple(self.entries()), relationships=tuple(self.relationships()))

    def find(self, entry_id: EntryId) -> Entry | None:
        """Read an entry that may not exist.

        Args:
            entry_id: The entry's id.

        Returns:
            The entry, or None when the matrix holds none with that id.

        """
        return self._entries.get(entry_id)

    def entry(self, entry_id: EntryId) -> Entry:
        """Read an entry that must exist.

        Args:
            entry_id: The entry's id.

        Returns:
            The entry.

        Raises:
            MatrixError: The matrix holds no entry with that id.

        """
        found: Entry | None = self._entries.get(entry_id)
        if found is None:
            message: str = f"the matrix holds no entry {entry_id}"
            raise MatrixError(message)
        return found

    def entries(self, kinds: Collection[EntryKind] | None = None) -> list[Entry]:
        """List entries.

        Args:
            kinds: The kinds to list; None lists every kind.

        Returns:
            The entries of those kinds, in id order.

        """
        return [self._entries[key] for key in sorted(self._entries) if _selected(kinds, self._entries[key].kind)]

    def named(self, name: str, kinds: Collection[EntryKind] | None = None) -> list[Entry]:
        """Find the entries that answer to a name.

        Args:
            name: A name or an alias, compared as :func:`name_key` reduces it.
            kinds: The kinds to look among; None looks among every kind.

        Returns:
            The entries whose name or one of whose aliases is that name, in id order.

        """
        wanted: str = name_key(name)
        return [
            entry
            for entry in self.entries(kinds)
            if wanted in {name_key(entry.name), *(name_key(alias) for alias in entry.aliases)}
        ]

    def relationships(self, kinds: Collection[RelationshipKind] | None = None) -> list[Relationship]:
        """List relationships.

        Args:
            kinds: The kinds to list; None lists every kind.

        Returns:
            The relationships of those kinds, in file order: by start, kind, end, key and side.
            A relationship both sides state is listed once for each.

        """
        return [self._relationships[key] for key in sorted(self._relationships) if _selected(kinds, key.kind)]

    def outgoing(self, entry_id: EntryId, kinds: Collection[RelationshipKind] | None = None) -> list[Relationship]:
        """List the relationships that start at an entry.

        Args:
            entry_id: The entry's id.
            kinds: The kinds to list; None lists every kind.

        Returns:
            The relationships, in file order. Empty for an id the matrix does not hold.

        """
        found: list[RelationshipId] = sorted(self._starting.get(entry_id, ()))
        return [self._relationships[key] for key in found if _selected(kinds, key.kind)]

    def incoming(self, entry_id: EntryId, kinds: Collection[RelationshipKind] | None = None) -> list[Relationship]:
        """List the relationships that end at an entry.

        Args:
            entry_id: The entry's id.
            kinds: The kinds to list; None lists every kind.

        Returns:
            The relationships, in file order. Empty for an id the matrix does not hold.

        """
        found: list[RelationshipId] = sorted(self._ending.get(entry_id, ()))
        return [self._relationships[key] for key in found if _selected(kinds, key.kind)]

    def ends(self, entry_id: EntryId) -> dict[str, list[Relationship]]:
        """Answer every relationship of an entry from the entry's own end.

        Args:
            entry_id: The entry's id.

        Returns:
            The relationships that start at the entry under each kind's name, and those that end
            at it under each kind's reverse name.

        """
        named: dict[str, list[Relationship]] = {}
        relationship: Relationship
        for relationship in self.outgoing(entry_id):
            named.setdefault(relationship.kind, []).append(relationship)
        for relationship in self.incoming(entry_id):
            named.setdefault(relationship_rule(relationship.kind).reverse, []).append(relationship)
        return named

    def home(self, entry_id: EntryId, side: Side | None = AUTHORITY_SIDE) -> EntryId | None:
        """Name the entry that is an entry's home in code.

        Args:
            entry_id: The entry's id.
            side: The side whose home relationship is read. None reads the authority side
                first and, when it states none, the other side: only a reader that reports
                what the repositories hold passes None, never a step that decides what is built.

        Returns:
            The end of the entry's home relationship as ``side`` states it (or, with None, as
            the authority side and then the other side states it); None when it states none.

        """
        homes: list[Relationship] = self.outgoing(entry_id, (HOME_RELATIONSHIP,))
        authority: list[Relationship] = [home for home in homes if home.side == AUTHORITY_SIDE]
        stated: list[Relationship] = (
            (authority or homes) if side is None else [home for home in homes if home.side == side]
        )
        return stated[0].end if stated else None

    def publishers(self, event_id: EntryId) -> list[EntryId]:
        """Name the services and components that publish an event, as the authority side states it.

        Args:
            event_id: The event's id.

        Returns:
            The starts of the authority-side publishes relationships that end at the event, in
            id order, each once.

        """
        found: list[Relationship] = self.incoming(event_id, (REL_PUBLISHES,))
        return sorted({relationship.start for relationship in found if relationship.side == AUTHORITY_SIDE})

    def publisher_stacks(self, event_id: EntryId) -> frozenset[EntryId]:
        """Name the stacks an event is published from: the one place an event's stack is decided.

        Args:
            event_id: The event's id.

        Returns:
            The authority-side home of each authority-side publisher of the event; a publisher
            with no home there is left out.

        """
        homes: list[EntryId | None] = [self.home(publisher) for publisher in self.publishers(event_id)]
        return frozenset(home for home in homes if home is not None)

    def _dirty(self, entry_id: EntryId) -> None:
        """Clear both flags of one entry a change affects; an entry without them stays as it is."""
        held: Entry | None = self._entries.get(entry_id)
        if held is not None:
            self._entries[entry_id] = dirtied(held)

    def _dirty_described(self, document_id: EntryId, headings: frozenset[str]) -> None:
        """Clear both flags of each entry whose describing text in a document changed.

        An architecture-side ``describedBy`` that names a heading is affected when that heading's
        text changed; one that names no heading is described by the whole document, and is
        affected when any heading's text changed. The other entries the document describes keep
        their flags.
        """
        if not headings:
            return
        described: set[EntryId] = set()
        describing: Relationship
        for describing in self.incoming(document_id, (REL_DESCRIBED_BY,)):
            heading: JsonValue = describing.attributes.get(ATTR_HEADING)
            if describing.side == AUTHORITY_SIDE and (not isinstance(heading, str) or heading in headings):
                described.add(describing.start)
        start: EntryId
        for start in sorted(described):
            self._dirty(start)

    def set_flags(self, item: Entry | Relationship) -> None:
        """Replace the flags of an entry or a relationship the matrix holds, and nothing else.

        Only ``matrixwrite.approve`` (the approved flag) and ``matrixcode.verify`` (the verified
        flag) call it; each states the other flag as the item holds it.

        Args:
            item: The held entry or relationship with the flags it is to carry.

        Raises:
            MatrixRefusedError: The matrix holds no such item, or it differs from the held one in
                more than its flags.

        """
        message: str = f"{item}: setting a flag needs the held item and changes nothing else"
        if isinstance(item, Entry):
            held: Entry | None = self._entries.get(item.id)
            if held is None or not same_content(held, item):
                raise MatrixRefusedError(message)
            self._entries[item.id] = item
            return
        identity: RelationshipId = relationship_id(item)
        before: Relationship | None = self._relationships.get(identity)
        if before is None or not same_content(before, item):
            raise MatrixRefusedError(message)
        self._drop(identity)
        self._add(item)

    def _one_event_problems(self, event: Entry) -> list[str]:
        """Check one authority-side event's publishers.

        Returns:
            One sentence per rule the event breaks; empty when it has publishers or an outside
            source, but not both. Any number of publishers, in any number of stacks, may publish
            one event type.

        """
        problems: list[str] = []
        external: bool = ATTR_EXTERNAL_SOURCE in event.attributes
        published: bool = bool(self.publishers(event.id))
        if external and published:
            problems.append(
                f"{event.id}: it states {ATTR_EXTERNAL_SOURCE} and a service or component of the project publishes it; "
                f"state one or the other",
            )
        if not external and not published:
            problems.append(
                f"{event.id}: no service or component publishes it; record one with put event --published-by, "
                f"or state {ATTR_EXTERNAL_SOURCE}",
            )
        return problems

    def _event_problems(self) -> list[str]:
        """Check every authority-side event; a repository-side event states only what its code shows.

        Returns:
            The problems of each authority-side event, in id order.

        """
        return [
            problem
            for event in self.entries((KIND_EVENT,))
            if event.side == AUTHORITY_SIDE
            for problem in self._one_event_problems(event)
        ]

    def _one_rule_problems(self, entry: Entry) -> list[str]:
        """Check one infrastructure entry's event pattern: matchesAllEvents only on a rule, never with matches.

        Returns:
            One sentence per breach; empty when the pattern is stated one way only, on a rule.

        """
        is_rule: bool = entry.attributes.get(ATTR_RESOURCE_TYPE) == RESOURCE_EVENTBRIDGE_RULE
        all_events: bool = ATTR_MATCHES_ALL_EVENTS in entry.attributes
        if all_events and not is_rule:
            return [f"{entry.id}: only an {RESOURCE_EVENTBRIDGE_RULE} states {ATTR_MATCHES_ALL_EVENTS}"]
        if all_events and self.outgoing(entry.id, (REL_MATCHES,)):
            return [f"{entry.id}: it states {ATTR_MATCHES_ALL_EVENTS} and names events with matches; state one"]
        return []

    def _rule_problems(self) -> list[str]:
        """Check the event pattern each infrastructure entry states.

        Returns:
            The problems of every infrastructure entry, in order.

        """
        return [problem for entry in self.entries((KIND_INFRASTRUCTURE,)) for problem in self._one_rule_problems(entry)]

    def _between_problems(self, relationship: Relationship) -> list[str]:
        """Check one relationship against the entries it names.

        Any entry may link to any other, so only the entries' existence is checked.

        Returns:
            One sentence per end or referenced entry the matrix does not hold.

        """
        rule: RelationshipRule = relationship_rule(relationship.kind)
        label: str = relationship_label(relationship)
        problems: list[str] = []
        if relationship.start not in self._entries:
            problems.append(f"{label}: {relationship.start} is not an entry")
        if relationship.end not in self._entries:
            problems.append(f"{label}: {relationship.end} is not an entry")
        name: str
        for name in sorted(rule.references):
            named: JsonValue = relationship.attributes.get(name)
            if isinstance(named, str) and EntryId(named) not in self._entries:
                problems.append(f"{label}: {name} names {named}, which is not an entry")
        return problems

    def _single_problems(self) -> list[str]:
        """Check every kind an entry may start at most one relationship of on one side.

        Returns:
            One sentence per entry that starts more than one on a side.

        """
        problems: list[str] = []
        start: EntryId
        for start in sorted(self._starting):
            counts: dict[tuple[RelationshipKind, Side], int] = {}
            identity: RelationshipId
            for identity in self._starting[start]:
                counts[identity.kind, identity.side] = counts.get((identity.kind, identity.side), 0) + 1
            problems.extend(
                f"{start}: starts {count} {kind} relationships on the {side} side; at most {limit} are allowed"
                for (kind, side), count in sorted(counts.items())
                if (limit := relationship_rule(kind).max_per_start) is not None and count > limit
            )
        return problems

    def _id_stack_problems(self, entry: Entry) -> list[str]:
        """Check the stack an entry's id names.

        Returns:
            One sentence when the id names a stack the matrix does not hold; otherwise empty.

        """
        stack: EntryId | None = id_stack(entry)
        if stack is None or stack in self._entries:
            return []
        return [f"{entry.id}: the id names {stack}, which is not an entry"]

    def problems(self) -> list[str]:
        """Check the whole matrix against the kinds registry and the rules between entries.

        Returns:
            One sentence per entry that breaks its kind or whose id names a stack the matrix does
            not hold; per relationship that breaks its kind or names an entry the matrix does not
            hold; and per entry that starts more relationships of
            a kind on one side than the kind allows. Empty when the matrix conforms.

        """
        problems: list[str] = []
        entry: Entry
        for entry in self.entries():
            problems.extend(entry_problems(entry))
            problems.extend(self._id_stack_problems(entry))
        relationship: Relationship
        for relationship in self.relationships():
            problems.extend(relationship_problems(relationship))
            problems.extend(self._between_problems(relationship))
        problems.extend(self._single_problems())
        problems.extend(self._event_problems())
        problems.extend(self._rule_problems())
        return problems

    def put(self, entry: Entry) -> None:
        """Add an entry, or replace the entry that has its id.

        An entry that breaks its kind, or whose id names a stack the matrix does not hold, raises
        ``MatrixError`` and changes nothing.

        The flags are dirty bits, settled each on its own (:func:`_flags_settled`): an entry that
        replaces another and differs from it in anything but its flags and its ``repository``
        attribute loses the approved flag, and one that differs in anything but its flags loses the
        verified flag when it is on the architecture side; one that differs in nothing else keeps
        the held entry's flags. Flags the entry states are not taken. When the text under
        a heading of a document changes, each entry an architecture-side ``describedBy`` says that
        heading describes loses both flags, and the other entries the document describes keep theirs
        (:meth:`_dirty_described`); the front matter is under no heading, so the move of a document
        to effective changes no entry's flags.

        Args:
            entry: The entry, of any registered kind, with the side it came from.

        Raises:
            MatrixError: The entry's id does not start with its kind.
            MatrixRefusedError: The matrix holds the entry on the authority side and ``entry``
                is on the other side: what is read from a repository never replaces what the
                architecture states.

        """
        message: str
        if kind_of(entry.id) != entry.kind:
            message = f"{entry.id}: the id does not start with the entry's kind, {entry.kind}"
            raise MatrixError(message)
        held: Entry | None = self._entries.get(entry.id)
        if held is not None and held.side == AUTHORITY_SIDE and entry.side != AUTHORITY_SIDE:
            message = (
                f"{entry.id} is on the {held.side} side; an entry on the {entry.side} side does not replace it. "
                f"Keep its side when changing it"
            )
            raise MatrixRefusedError(message)
        stored: Entry = _flags_settled(held, entry)
        _raise_problems([*entry_problems(stored), *self._id_stack_problems(stored)], f"the entry {entry.id}")
        self._entries[entry.id] = stored
        headings: frozenset[str] | None = _changed_headings(held, stored)
        if headings is not None:
            self._dirty_described(stored.id, headings)

    def _refuse_over_limit(self, relationship: Relationship, identity: RelationshipId) -> None:
        """Refuse a new relationship that would exceed the most its kind allows from one start on one side.

        Raises:
            MatrixRefusedError: The kind declares a limit and, on the relationship's side, the start
                already has that many others of the kind.

        """
        limit: int | None = relationship_rule(relationship.kind).max_per_start
        if limit is None:
            return
        others: list[Relationship] = [
            other
            for other in self.outgoing(relationship.start, (relationship.kind,))
            if other.side == identity.side and relationship_id(other) != identity
        ]
        if len(others) < limit:
            return
        message: str = (
            f"{relationship.start} already has {len(others)} {relationship.kind} relationships on the "
            f"{identity.side} side (to {', '.join(sorted(other.end for other in others))}); at most {limit} "
            f"are allowed, so unlink one first"
        )
        raise MatrixRefusedError(message)

    def link(self, relationship: Relationship) -> None:
        """Add a relationship, or replace the one with the same kind, ends, key attributes and side.

        The relationship is stored for the side it states; the same relationship as the other
        side states it stays as it is. A relationship that breaks its kind, names an entry the
        matrix does not hold or joins kinds it may not join raises ``MatrixError`` and changes
        nothing. A new relationship of a kind that limits the relationships from an entry on a
        side, when on its side the start already has that many others, raises
        ``MatrixRefusedError`` (:meth:`_refuse_over_limit`) and changes nothing. The flags are
        settled as :meth:`put` settles an entry's. An architecture-side relationship that is added,
        or changed in anything but its approved and verified flags, clears both flags of the entry
        it starts from.

        Args:
            relationship: The relationship, of any registered kind, with the side that states it.

        """
        _raise_problems(
            [*relationship_problems(relationship), *self._between_problems(relationship)],
            f"the relationship {relationship_label(relationship)}",
        )
        identity: RelationshipId = relationship_id(relationship)
        self._refuse_over_limit(relationship, identity)
        before: Relationship | None = self._relationships.get(identity)
        stored: Relationship = _flags_settled(before, relationship)
        if before is not None:
            self._drop(identity)
        self._add(stored)
        if relationship.side == AUTHORITY_SIDE and (before is None or not same_content(before, stored)):
            self._dirty(relationship.start)

    def unlink(self, relationship: Relationship) -> bool:
        """Remove the relationship with the same kind, ends, key attributes and side.

        Args:
            relationship: A relationship that names the kind, both ends, the key attributes and
                the side of the one to remove; its other attributes are not compared. The same
                relationship as the other side states it stays.

        Returns:
            True when the matrix held it and it was removed; an architecture-side relationship
            removed clears both flags of the entry it started from.

        """
        identity: RelationshipId = relationship_id(relationship)
        if identity not in self._relationships:
            return False
        self._drop(identity)
        if identity.side == AUTHORITY_SIDE:
            self._dirty(identity.start)
        return True

    def _referring(self, entry_id: EntryId) -> list[tuple[RelationshipId, list[str]]]:
        """Find the relationships that name an entry in an attribute.

        Returns:
            Each such relationship with the attributes that name the entry, in file order.

        """
        found: list[tuple[RelationshipId, list[str]]] = []
        identity: RelationshipId
        for identity in sorted(self._relationships):
            relationship: Relationship = self._relationships[identity]
            names: list[str] = [
                name
                for name in sorted(relationship_rule(identity.kind).references)
                if relationship.attributes.get(name) == entry_id
            ]
            if names:
                found.append((identity, names))
        return found

    def _named_for(self, stack: EntryId) -> list[Entry]:
        """Find the entries whose ids name a stack.

        Returns:
            The entries, in id order.

        """
        return [entry for entry in self.entries() if id_stack(entry) == stack]

    def rename(self, old: EntryId, new: EntryId) -> None:
        """Re-key an entry and every relationship that names it, at either end or in an attribute.

        The entry keeps its name, its side and everything else it holds. For a stack, every
        entry whose id names the stack is re-keyed with it, so that its id names the stack's new
        id. An id that is not the old id's kind's raises ``MatrixError`` from
        :func:`as_entry_id`, as does an entry that does not exist from :meth:`entry` and an id
        that does not have the form the entry's side requires. Whatever is refused changes
        nothing.

        Args:
            old: The entry's id now.
            new: The id it is to have, of the same kind.

        Raises:
            MatrixRefusedError: The new id is of another kind, or an entry already has it or one
                of the ids the entries named for a stack are to have.

        """
        entry: Entry = self.entry(old)
        message: str
        if kind_of(as_entry_id(new)) != entry.kind:
            message = f"{old} cannot become {new}: an entry keeps its kind"
            raise MatrixRefusedError(message)
        moves: list[tuple[Entry, EntryId]] = [(entry, new)]
        if entry.kind == STACK_KIND:
            prefix: str = new.partition(ID_SEPARATOR)[2] + STACK_SEPARATOR
            moves.extend(
                (inside, make_id(inside.kind, prefix + inside.id.rpartition(STACK_SEPARATOR)[2]))
                for inside in self._named_for(old)
            )
        problems: list[str] = [] if entry.kind == STACK_KIND else self._id_stack_problems(replace(entry, id=new))
        moving: Entry
        target: EntryId
        for moving, target in moves:
            if target in self._entries:
                message = f"{moving.id} cannot become {target}: an entry already has that id"
                raise MatrixRefusedError(message)
            problems.extend(entry_problems(replace(moving, id=target)))
        _raise_problems(problems, f"the rename of {old} to {new}")
        for moving, target in moves:
            self._rekey(moving.id, target)

    def _rekey(self, old: EntryId, new: EntryId) -> None:
        """Give one entry a new id, at both ends of its relationships and in every attribute that names it."""
        entry: Entry = self._entries[old]
        touched: set[RelationshipId] = {*self._starting.get(old, set()), *self._ending.get(old, set())}
        touched.update(identity for identity, _ in self._referring(old))
        moved: list[Relationship] = []
        identity: RelationshipId
        for identity in sorted(touched):
            relationship: Relationship = self._relationships[identity]
            references: frozenset[str] = relationship_rule(identity.kind).references
            moved.append(
                replace(
                    relationship,
                    start=new if relationship.start == old else relationship.start,
                    end=new if relationship.end == old else relationship.end,
                    attributes={
                        name: new if name in references and value == old else value
                        for name, value in relationship.attributes.items()
                    },
                ),
            )
            self._drop(identity)
        del self._entries[old]
        self._entries[new] = replace(entry, id=new)
        relationship_moved: Relationship
        for relationship_moved in moved:
            self._add(relationship_moved)

    def remove(self, entry_id: EntryId, *, held: bool = False) -> list[EntryId]:
        """Remove an entry and every relationship that starts or ends at it.

        A relationship that names a removed entry in an attribute is removed when the attribute is
        one of its kind's key or required attributes, and otherwise loses the attribute. An entry
        that is left and starts an architecture-side relationship removed or changed this way loses
        both flags, as :meth:`unlink` clears them. An entry that does not exist raises
        ``MatrixError`` from :meth:`entry`.

        Args:
            entry_id: The entry's id.
            held: Whether every entry whose home is this entry, on either side, and every entry
                whose id names it, is removed with it.

        Returns:
            The ids of the entries removed, in id order.

        Raises:
            MatrixRefusedError: The entry is a stack, entries have ids that name it and ``held``
                is False.

        """
        self.entry(entry_id)
        named: list[EntryId] = [entry.id for entry in self._named_for(entry_id)]
        if named and not held:
            message: str = (
                f"{entry_id} cannot be removed alone: the ids of {len(named)} entries name it "
                f"({', '.join(named[:PROBLEMS_SHOWN])}); remove it with what it holds"
            )
            raise MatrixRefusedError(message)
        removed: dict[EntryId, None] = {entry_id: None}
        if held:
            removed.update(
                dict.fromkeys(relationship.start for relationship in self.incoming(entry_id, (HOME_RELATIONSHIP,))),
            )
            removed.update(dict.fromkeys(named))
        touched: set[EntryId] = set()
        gone: EntryId
        for gone in list(removed):
            identity: RelationshipId
            for identity in sorted({*self._starting.get(gone, set()), *self._ending.get(gone, set())}):
                if identity.side == AUTHORITY_SIDE:
                    touched.add(identity.start)
                self._drop(identity)
            names: list[str]
            for identity, names in self._referring(gone):
                relationship: Relationship = self._relationships[identity]
                rule: RelationshipRule = relationship_rule(identity.kind)
                if identity.side == AUTHORITY_SIDE:
                    touched.add(identity.start)
                self._drop(identity)
                if not set(names) & {*rule.key, *rule.required}:
                    kept: dict[str, JsonValue] = {
                        name: value for name, value in relationship.attributes.items() if name not in names
                    }
                    self._add(replace(relationship, attributes=kept))
            del self._entries[gone]
            self._starting.pop(gone, None)
            self._ending.pop(gone, None)
        start: EntryId
        for start in sorted(touched - set(removed)):
            self._dirty(start)
        return sorted(removed)


def _heading_keys(matrix: Matrix, document_id: EntryId) -> frozenset[str] | None:
    """Read the headings a document entry holds, as names are compared.

    Returns:
        Each heading of the document entry reduced by :func:`name_key`; None when the matrix
        holds no document entry with that id.

    """
    held: Entry | None = matrix.find(document_id)
    if held is None or held.kind != KIND_DOCUMENT:
        return None
    headings: JsonValue = held.attributes.get(ATTR_HEADINGS)
    listed: list[JsonValue] = headings if isinstance(headings, list) else []
    return frozenset(name_key(heading) for heading in listed if isinstance(heading, str))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def stale_headings(matrix: Matrix, documents: Collection[EntryId] | None = None) -> list[Relationship]:
    """List the relationships that name a heading their document entry does not hold.

    A relationship names a heading when it has a ``heading`` attribute; its document is the end
    of it that is a document entry. Headings are compared as :func:`name_key` reduces them. A
    relationship whose document the matrix does not hold is left to :meth:`Matrix.problems`.

    Args:
        matrix: The matrix.
        documents: The document entries to look at; None looks at every one.

    Returns:
        Each such relationship, in file order.

    """
    known: dict[EntryId, frozenset[str] | None] = {}
    stale: list[Relationship] = []
    relationship: Relationship
    for relationship in matrix.relationships():
        heading: JsonValue = relationship.attributes.get(ATTR_HEADING)
        document_id: EntryId | None = _document_end(relationship)
        wanted: bool = documents is None or document_id in documents
        if not isinstance(heading, str) or not heading or document_id is None or not wanted:
            continue
        if document_id not in known:
            known[document_id] = _heading_keys(matrix, document_id)
        held: frozenset[str] | None = known[document_id]
        if held is not None and name_key(heading) not in held:
            stale.append(relationship)
    return stale


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def heading_problems(matrix: Matrix) -> list[str]:
    """Check that every heading a relationship names is a heading of its document entry.

    ``sync-documents`` records each document's headings as the vault holds them; a relationship
    naming a heading the document no longer has joins on text that is gone. Writes do not run
    this check: a change to a document leaves such relationships behind until whoever recorded
    them corrects them, and ``atw-matrix check`` reports each one.

    Args:
        matrix: The matrix.

    Returns:
        One sentence per relationship that names a heading its document entry does not hold.

    """
    return [
        f"{relationship_label(relationship)}: names the heading "
        f"{relationship.attributes.get(ATTR_HEADING)!r}, which {_document_end(relationship)} does not have"
        for relationship in stale_headings(matrix)
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def role_of(environ: Mapping[str, str]) -> Role:
    """Read who is running the command from the environment.

    Args:
        environ: The process environment.

    Returns:
        The role the launcher set, or the operator role when it set none.

    Raises:
        MatrixRefusedError: The variable holds something that is not a role.

    """
    stated: str = environ.get(ROLE_ENV, "").strip()
    if not stated:
        return OPERATOR_ROLE
    role: Role
    for role in ROLES:
        if role == stated:
            return role
    message: str = f"{ROLE_ENV} is {stated!r}, which is not one of {', '.join(ROLES)}"
    raise MatrixRefusedError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def require_role(command: str, role: Role) -> None:
    """Refuse a sub-command the role may not run.

    Args:
        command: The sub-command.
        role: Who is running it.

    Raises:
        MatrixRefusedError: The registry's command table does not name the command, or does not
            allow the role to run it.

    """
    if command not in COMMAND_RULES:
        message: str = f"{command!r} is not a command of the matrix"
        raise MatrixRefusedError(message)
    if role not in COMMAND_RULES[command].roles:
        allowed: str = ", ".join(sorted(COMMAND_RULES[command].roles))
        message = f"the role {role} may not run {command}; it is for {allowed}"
        raise MatrixRefusedError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def matrix_path(explicit: str | None, environ: Mapping[str, str]) -> Path:
    """Decide which matrix file a command works on.

    Args:
        explicit: The path the caller gave, or None.
        environ: The process environment.

    Returns:
        The caller's path; else the path in the matrix variable; else the default place under
        the control repository the driver's variable, or the project's, names.

    Raises:
        MatrixError: No path was given and the environment names neither a matrix nor a control
            repository.

    """
    if explicit:
        return Path(explicit).expanduser()
    stated: str = environ.get(MATRIX_ENV, "").strip()
    if stated:
        return Path(stated).expanduser()
    control: str = environ.get(CONTROL_REPO_ENV, "").strip()
    if not control:
        message: str = f"give --matrix, or set {MATRIX_ENV} or {CONTROL_REPO_ENV}"
        raise MatrixError(message)
    return Path(control).expanduser().joinpath(*DEFAULT_MATRIX_PARTS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def lock_path(path: Path) -> Path:
    """Name the lock file of a matrix file.

    Args:
        path: The matrix file.

    Returns:
        The file named for the matrix, with the contract's lock suffix, in the contract's lock
        directory beside the matrix.

    """
    return path.parent / LOCK_DIRECTORY / f"{path.stem}{LOCK_SUFFIX}"


def _decode(path: Path) -> object:
    """Read a matrix file as decoded JSON.

    Returns:
        The decoded document.

    Raises:
        MatrixError: The file is missing, unreadable or not JSON.

    """
    message: str
    try:
        text: str = path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"cannot read the matrix {path}: {error}"
        raise MatrixError(message) from error
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as error:
        message = f"the matrix {path} is not JSON: {error}"
        raise MatrixError(message) from error
    return decoded


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_matrix(path: Path) -> Matrix:
    """Read a matrix file, validate its shape and index it.

    A read takes no lock: a write replaces the file in one move, so a reader sees the matrix
    before the change or after it. Each entry and relationship is checked against its kind on
    every write and by :func:`file_problems`, not here, so a read stays quick. A file that is
    missing, unreadable, not JSON, of another shape or of an unregistered kind raises
    ``MatrixError``.

    Args:
        path: The matrix file.

    Returns:
        The matrix.

    """
    return Matrix(parse_document(_decode(path), str(path)))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def serialize(matrix: Matrix) -> str:
    """Render a matrix as the text of its file.

    Args:
        matrix: The matrix.

    Returns:
        Indented JSON with sorted keys, the relationships in file order and a final newline, so
        a change reads as a small diff.

    """
    return json.dumps(document_json(matrix.document()), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_text(path: Path, text: str) -> None:
    """Put text in place of a file the matrix command writes, in one move.

    A reader of the file sees it as it was or as it is now, never half written. A file that
    cannot be written raises ``MatrixError``.

    Args:
        path: The file; its directory must exist.
        text: The whole text of the file.

    """
    _write_text(path, text)


def _write_text(path: Path, text: str) -> None:
    """Put text in place of a file in one move.

    Raises:
        MatrixError: The file cannot be written.

    """
    message: str
    descriptor: int
    temporary: str
    try:
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
        os.fchmod(descriptor, FILE_MODE)
    except OSError as error:
        message = f"cannot write {path}: {error}"
        raise MatrixError(message) from error
    scratch: Path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        scratch.replace(path)
    except OSError as error:
        scratch.unlink(missing_ok=True)
        message = f"cannot write {path}: {error}"
        raise MatrixError(message) from error


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def matrix_lock(path: Path, wait: float = DEFAULT_LOCK_WAIT) -> Generator[None]:
    """Hold the exclusive lock of a matrix file.

    The lock is an advisory lock on the matrix's lock file (:func:`lock_path`), which is left in
    place afterwards.

    Args:
        path: The matrix file.
        wait: Seconds to wait for another holder before giving up.

    Yields:
        Control while the lock is held.

    Raises:
        ValueError: ``wait`` is not a positive, finite number.
        MatrixError: The lock file cannot be opened.
        MatrixLockTimeoutError: Another process held the lock for the whole wait.

    """
    message: str
    if not 0 < wait < float("inf"):
        message = f"matrix: the lock wait {wait!r} is not a positive, finite number of seconds"
        raise ValueError(message)
    lock: Path = lock_path(path)
    deadline: float = time.monotonic() + wait
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        descriptor: int = os.open(lock, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as error:
        message = f"cannot open the matrix lock {lock}: {error}"
        raise MatrixError(message) from error
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    message = f"the matrix {path} stayed locked by another process for {wait} seconds"
                    raise MatrixLockTimeoutError(message) from error
                time.sleep(LOCK_POLL)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def create_matrix(
    path: Path,
    matrix: Matrix | None = None,
    *,
    replace_existing: bool = False,
    wait: float = DEFAULT_LOCK_WAIT,
) -> None:
    """Write a new matrix file, creating its directory when it does not exist.

    A matrix that does not conform, or a lock another process holds for the whole wait, raises
    ``MatrixError``.

    Args:
        path: The matrix file to create.
        matrix: The matrix; None writes a matrix that holds nothing.
        replace_existing: Whether a matrix file already at ``path`` is replaced.
        wait: Seconds to wait for the matrix's lock.

    Raises:
        MatrixRefusedError: A matrix file already exists at ``path`` and ``replace_existing`` is False.
        MatrixError: The directory cannot be created.

    """
    message: str
    content: Matrix = Matrix() if matrix is None else matrix
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        message = f"cannot create the matrix directory {path.parent}: {error}"
        raise MatrixError(message) from error
    with matrix_lock(path, wait):
        if path.exists() and not replace_existing:
            message = f"a matrix already exists at {path}"
            raise MatrixRefusedError(message)
        _raise_problems(content.problems(), f"the matrix to write to {path}")
        _write_text(path, serialize(content))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def update_matrix[T](path: Path, change: Callable[[Matrix], T], *, wait: float = DEFAULT_LOCK_WAIT) -> T:
    """Apply one change to a matrix file as a single locked read-modify-write.

    The matrix is read under the lock, ``change`` edits it in place, and the result is checked
    against the kinds registry and moved into place before the lock is released. A change that
    leaves the matrix as it was writes nothing. When ``change`` raises, or the changed matrix
    does not conform (``MatrixError``), the file is left as it was.

    Args:
        path: The matrix file.
        change: The edit; it receives the matrix and returns whatever the caller wants back.
        wait: Seconds to wait for the matrix's lock.

    Returns:
        What ``change`` returned.

    Raises:
        MatrixError: There is no matrix at ``path``.

    """
    if not path.is_file():
        message: str = f"there is no matrix at {path}"
        raise MatrixError(message)
    with matrix_lock(path, wait):
        matrix: Matrix = read_matrix(path)
        before: str = serialize(matrix)
        result: T = change(matrix)
        after: str = serialize(matrix)
        if after != before:
            _raise_problems(matrix.problems(), f"the matrix to write to {path}")
            _write_text(path, after)
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def rename_entry(path: Path, old: EntryId, new: EntryId, *, wait: float = DEFAULT_LOCK_WAIT) -> None:
    """Re-key an entry of a matrix file and both ends of its relationships in one write.

    For a stack, the entries whose ids name it are re-keyed in the same write. Whatever
    :meth:`Matrix.rename` refuses raises ``MatrixError`` and leaves the file as it was.

    Args:
        path: The matrix file.
        old: The entry's id now.
        new: The id it is to have, of the same kind.
        wait: Seconds to wait for the matrix's lock.

    """

    def change(matrix: Matrix) -> None:
        matrix.rename(old, new)

    update_matrix(path, change, wait=wait)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def remove_entry(
    path: Path,
    entry_id: EntryId,
    *,
    held: bool = False,
    wait: float = DEFAULT_LOCK_WAIT,
) -> list[EntryId]:
    """Remove an entry of a matrix file and its relationships in one write.

    An entry that does not exist, or a stack that entries' ids name when ``held`` is False,
    raises ``MatrixError`` and leaves the file as it was.

    Args:
        path: The matrix file.
        entry_id: The entry's id.
        held: Whether every entry whose home is this entry, and every entry whose id names it,
            is removed with it.
        wait: Seconds to wait for the matrix's lock.

    Returns:
        The ids of the entries removed, in id order.

    """

    def change(matrix: Matrix) -> list[EntryId]:
        return matrix.remove(entry_id, held=held)

    return update_matrix(path, change, wait=wait)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def file_problems(path: Path) -> list[str]:
    """Describe every way a matrix file fails the schema, the kinds registry and the rules between entries.

    A file that is missing, unreadable or not JSON raises ``MatrixError``.

    Args:
        path: The matrix file.

    Returns:
        What the file's shape breaks when it cannot be read as a matrix, otherwise what
        :meth:`Matrix.problems` and :func:`heading_problems` find; empty when the file conforms.

    """
    decoded: object = _decode(path)
    try:
        matrix: Matrix = Matrix(parse_document(decoded, str(path)))
    except MatrixError as error:
        return [str(error)]
    return [*matrix.problems(), *heading_problems(matrix)]
