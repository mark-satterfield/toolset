"""Carry the element matrix and the vault's effective architecture documents into the matrix.

The carry-over runs once, by hand. Every step is a rule; nothing here judges:

- a repository row and a stack row are carried as they are;
- an element row becomes a component, library, layer or infrastructure row, by the mapping file
  from its free-text resource type to the controlled list, and keeps its former id as an alias;
- a repository the architecture names that had no row becomes an unregistered repository row;
- a service repository gets a service row, a shared repository a supporting feature;
- evidence becomes ``describedBy`` links, a recorded conflict a disagreement row, and a name a
  document shows that no row answers to becomes a term row; a note in the unresolved list about
  a repository that has a row is reported and not carried, because it is not a row of anything;
- every row is marked ``legacy`` or ``none`` for code, never built, and approved only when every
  document that describes it is effective.

The mapping file and the optional repository inventory are data the caller passes in. A
resource type, status or conflict status with no mapping stops the carry-over and is named.
"""

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import starmap
from pathlib import Path
from typing import Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    APPROVAL_APPROVED,
    APPROVAL_UNVERIFIED,
    BASIS_CARRIED_FROM_EFFECTIVE_ARC42,
    CODE_LEGACY,
    CODE_NONE,
    DISAGREEMENT_SETTLED,
    DISAGREEMENT_STATUSES,
    ELEMENT_KINDS,
    FEATURE_SUPPORTING,
    KIND_DISAGREEMENT,
    KIND_DOCUMENT,
    KIND_FEATURE,
    KIND_LAYER,
    KIND_LIBRARY,
    KIND_REPOSITORY,
    KIND_SERVICE,
    KIND_STACK,
    KIND_TERM,
    LIFECYCLE_EFFECTIVE,
    LIFECYCLES,
    LINK_CONTAINS,
    LINK_DESCRIBED_BY,
    LINK_PROVIDED_BY,
    LINK_SHOWN_IN,
    RESOURCE_TYPE_PATTERN,
    STATUS_UNREGISTERED,
    STATUSES,
    Approval,
    CodeState,
    DisagreementStatus,
    DisputedStatement,
    DocumentsSyncedAt,
    ElementKind,
    JsonValue,
    Kind,
    Lifecycle,
    Link,
    Matrix,
    MatrixError,
    Node,
    NodeId,
    Status,
)
from matrixstore import Stamp, as_node_id, empty_matrix, make_id, name_key
from matrixsync import DocumentRead, apply_documents

SOURCE_VERSION: Final = 2
"""The version of the element matrix the carry-over reads."""
MAP_VERSION: Final = 1
OLD_REPOSITORY: Final = "repository"
OLD_STACK: Final = "stack"
OLD_ELEMENT: Final = "element"
CARRIED: Final = "carried"
CAPABILITY_SUFFIX: Final = " (shared capability)"
"""Added to a shared repository's name to name its supporting feature, so the two names differ."""
NOT_A_DOCUMENT: Final = "the path is not an architecture document of the vault"
NOT_IN_VAULT: Final = "the document is no longer in the vault"


class CarryOverError(MatrixError):
    """The element matrix, the mapping file or the inventory cannot be carried over as given."""


@dataclass(frozen=True, slots=True)
class Evidence:
    """One citation of a source text in the element matrix."""

    path: str
    section: str
    line: int | None
    quote: str


@dataclass(frozen=True, slots=True)
class Conflict:
    """One conflict note of the element matrix."""

    text: str
    """What disagrees: the note's issue, reason, topic or disposition."""
    resolution: str
    status: str | None
    settled_by_disposition: bool
    """True when the note records a disposition and no status."""
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class OldRow:
    """One row of the element matrix, reduced to what is carried."""

    old_id: str
    kind: str
    name: str
    repository: str
    stack: str | None
    purpose: str
    status: str | None
    resource_type: str | None
    contains: tuple[str, ...]
    declared: tuple[str, ...]
    """The stack names code declared for the row when the inventory was taken."""
    evidence: tuple[Evidence, ...]
    conflicts: tuple[Conflict, ...]


@dataclass(frozen=True, slots=True)
class Unresolved:
    """One entry of the element matrix's list of names it could not settle."""

    name: str | None
    """A repository the architecture names that has no row."""
    repository: str | None
    """A repository that has a row and an open question."""
    reason: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class OldMatrix:
    """The element matrix as read from its file."""

    rows: tuple[OldRow, ...]
    aliases: Mapping[str, tuple[str, ...]]
    unresolved: tuple[Unresolved, ...]


@dataclass(frozen=True, slots=True)
class MappedType:
    """What one free-text resource type becomes."""

    kind: ElementKind
    resource_type: str


@dataclass(frozen=True, slots=True)
class TypeMap:
    """The mapping file: the data the carry-over's rules read."""

    resource_types: Mapping[str, MappedType]
    rows: Mapping[str, MappedType]
    """The mapping of each row that states no resource type, by its id in the element matrix."""
    conflict_statuses: Mapping[str, DisagreementStatus]
    disposition_status: DisagreementStatus
    open_question_status: DisagreementStatus
    inventory_document: str
    inventory_lifecycle: Lifecycle
    shared_prefixes: tuple[str, ...]
    shared_suffixes: tuple[str, ...]
    service_suffix: str
    service_role: str
    no_code_lifecycles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InventoryEntry:
    """One repository of a ``polyrepo inventory`` listing."""

    name: str
    role: str | None
    lifecycle: str | None
    has_code: bool | None


@dataclass(frozen=True, slots=True)
class CarrySources:
    """What the carry-over reads besides the vault."""

    old: OldMatrix
    types: TypeMap
    inventory: Mapping[str, InventoryEntry] | None = None
    """A ``polyrepo inventory`` listing by reduced repository name, when one is passed in."""


class CarryReport(TypedDict):
    """What the carry-over did with every part of the element matrix: also what ``carry-over`` prints."""

    rowsBefore: int
    carried: int
    notCarried: list[str]
    """The ids of element matrix rows that have no row in the matrix; the carry-over leaves none."""
    renamed: int
    """Rows whose id changed because their kind did; each keeps its former id as an alias."""
    byKind: dict[str, int]
    unregisteredRepositories: list[str]
    services: int
    supportingFeatures: list[NodeId]
    documents: int
    terms: int
    disagreements: list[NodeId]
    conflictNotesNotCarried: list[str]
    unresolvedNotesNotCarried: list[str]
    """Entries of the element matrix's unresolved list that are a note about a repository that has a row."""
    evidenceCarried: int
    evidenceDropped: dict[str, int]
    showsResolved: int
    showsAmbiguous: int
    showsUnresolved: int
    codeStateFrom: str


@dataclass(slots=True)
class _Carry:
    """The carry-over in progress."""

    matrix: Matrix
    old: OldMatrix
    types: TypeMap
    stamp: Stamp
    inventory: Mapping[str, InventoryEntry] | None
    lifecycles: dict[str, Lifecycle]
    """Each vault document's path and lifecycle."""
    ids: dict[str, NodeId] = field(default_factory=dict)
    """Each element matrix row id and the id of the row it became."""
    dropped: dict[str, int] = field(default_factory=dict)
    evidence_carried: int = 0


def _object(value: JsonValue, where: str) -> dict[str, JsonValue]:
    """Narrow a JSON value to an object.

    Returns:
        The object.

    Raises:
        CarryOverError: The value is not a JSON object.

    """
    if not isinstance(value, dict):
        message: str = f"{where} is not a JSON object"
        raise CarryOverError(message)
    return value


def _text(source: Mapping[str, JsonValue], key: str, where: str) -> str:
    """Read a string the carry-over cannot do without.

    Returns:
        The string.

    Raises:
        CarryOverError: The key is missing or does not hold a nonempty string.

    """
    value: JsonValue = source.get(key)
    if not isinstance(value, str) or not value:
        message: str = f"{where}: {key} is not a nonempty string"
        raise CarryOverError(message)
    return value


def _optional(source: Mapping[str, JsonValue], key: str, where: str) -> str | None:
    """Read a string that may be absent.

    Returns:
        The string, or None when the key is missing, null or empty.

    Raises:
        CarryOverError: The key holds something that is not a string.

    """
    value: JsonValue = source.get(key)
    if value is None or (isinstance(value, str) and not value):
        return None
    if not isinstance(value, str):
        message: str = f"{where}: {key} is not a string"
        raise CarryOverError(message)
    return value


def _objects(source: Mapping[str, JsonValue], key: str, where: str) -> list[dict[str, JsonValue]]:
    """Read a list of objects that may be absent.

    Returns:
        The objects; none when the key is missing or null.

    Raises:
        CarryOverError: The key holds something that is not a list.

    """
    value: JsonValue = source.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        message: str = f"{where}: {key} is not a list"
        raise CarryOverError(message)
    return [_object(item, f"{where}: {key}") for item in value]


def _strings(source: Mapping[str, JsonValue], key: str, where: str) -> tuple[str, ...]:
    """Read a list of strings that may be absent.

    Returns:
        The strings; none when the key is missing or null.

    Raises:
        CarryOverError: The key holds something that is not a list of strings.

    """
    value: JsonValue = source.get(key)
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        message: str = f"{where}: {key} is not a list of strings"
        raise CarryOverError(message)
    return tuple(item for item in value if isinstance(item, str))


def _evidence(source: Mapping[str, JsonValue], where: str) -> tuple[Evidence, ...]:
    """Read the citations of a row, a conflict note or an unresolved entry.

    Returns:
        The citations, in order.

    """
    found: list[Evidence] = []
    entry: dict[str, JsonValue]
    for entry in _objects(source, "evidence", where):
        line: JsonValue = entry.get("line")
        found.append(
            Evidence(
                path=_text(entry, "path", where),
                section=_optional(entry, "section", where) or "",
                line=line if isinstance(line, int) and not isinstance(line, bool) else None,
                quote=_optional(entry, "quote", where) or "",
            ),
        )
    return tuple(found)


def _conflict(note: Mapping[str, JsonValue], where: str) -> Conflict:
    """Read one conflict note.

    Returns:
        The note.

    Raises:
        CarryOverError: The note states nothing that disagrees.

    """
    disposition: str | None = _optional(note, "disposition", where)
    stated: list[str | None] = [_optional(note, key, where) for key in ("issue", "reason", "topic")]
    text: str | None = next((value for value in stated if value is not None), None)
    if text is None and disposition is None:
        message: str = f"{where}: a conflict note states no issue, reason, topic or disposition"
        raise CarryOverError(message)
    status: str | None = _optional(note, "status", where)
    return Conflict(
        text=text or f"Disposition: {disposition}",
        resolution=_optional(note, "resolution", where) or (disposition or ""),
        status=status,
        settled_by_disposition=status is None and disposition is not None,
        evidence=_evidence(note, where),
    )


def _declared(row: Mapping[str, JsonValue], where: str) -> tuple[str, ...]:
    """Read the stack names code declared for a row.

    Returns:
        The construct ids and explicit stack names, without repeats.

    """
    names: list[str] = []
    entry: dict[str, JsonValue]
    for entry in [*_objects(row, "declaredNames", where), *_objects(row, "declaredStacks", where)]:
        names.extend(name for key in ("constructId", "explicitStackName") if (name := _optional(entry, key, where)))
    return tuple(dict.fromkeys(names))


def _old_row(key: str, value: JsonValue) -> OldRow:
    """Read one row of the element matrix.

    Returns:
        The row.

    Raises:
        CarryOverError: The row is filed under an id that is not its own.

    """
    where: str = f"element matrix row {key}"
    row: dict[str, JsonValue] = _object(value, where)
    if _text(row, "id", where) != key:
        message: str = f"{where} says its id is {row.get('id')!r}"
        raise CarryOverError(message)
    return OldRow(
        old_id=key,
        kind=_text(row, "kind", where),
        name=_text(row, "name", where),
        repository=_text(row, "repository", where),
        stack=_optional(row, "stack", where),
        purpose=_optional(row, "purpose", where) or "",
        status=_optional(row, "status", where),
        resource_type=_optional(row, "resourceType", where),
        contains=_strings(row, "contains", where),
        declared=_declared(row, where),
        evidence=_evidence(row, where),
        conflicts=tuple(_conflict(note, where) for note in _objects(row, "conflicts", where)),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_old_matrix(decoded: JsonValue) -> OldMatrix:
    """Read the element matrix from its decoded file.

    Args:
        decoded: The decoded ``element-matrix.json``.

    Returns:
        Its rows, its alias table and its unresolved entries.

    Raises:
        CarryOverError: The file is not version 2 of the element matrix, or a part of it is malformed.

    """
    document: dict[str, JsonValue] = _object(decoded, "the element matrix")
    if document.get("version") != SOURCE_VERSION:
        message: str = f"the element matrix is version {document.get('version')!r}, not {SOURCE_VERSION}"
        raise CarryOverError(message)
    elements: dict[str, JsonValue] = _object(document.get("elements"), "the element matrix: elements")
    table: dict[str, JsonValue] = _object(document.get("aliases"), "the element matrix: aliases")
    unresolved: list[Unresolved] = [
        Unresolved(
            name=_optional(entry, "name", "unresolved"),
            repository=_optional(entry, "repository", "unresolved"),
            reason=_optional(entry, "reason", "unresolved") or "",
            evidence=_evidence(entry, "unresolved"),
        )
        for entry in _objects(document, "unresolved", "the element matrix")
    ]
    return OldMatrix(
        rows=tuple(starmap(_old_row, elements.items())),
        aliases={name: _strings(table, name, "the element matrix: aliases") for name in table},
        unresolved=tuple(unresolved),
    )


def _mapped(value: JsonValue, where: str) -> MappedType:
    """Read one entry of the mapping file's resource type tables.

    Returns:
        The kind and the controlled resource type.

    Raises:
        CarryOverError: The kind is not an element kind, or the resource type is not well formed.

    """
    entry: dict[str, JsonValue] = _object(value, where)
    stated: str = _text(entry, "kind", where)
    resource_type: str = _text(entry, "resourceType", where)
    kind: ElementKind | None = next((choice for choice in ELEMENT_KINDS if choice == stated), None)
    if kind is None or RESOURCE_TYPE_PATTERN.search(resource_type) is None:
        message: str = f"{where}: {stated!r} with {resource_type!r} is not an element kind with a resource type"
        raise CarryOverError(message)
    return MappedType(kind=kind, resource_type=resource_type)


def _disagreement_status(value: JsonValue, where: str) -> DisagreementStatus:
    """Read a disagreement status from the mapping file.

    Returns:
        The status.

    Raises:
        CarryOverError: The value is not a disagreement status.

    """
    status: DisagreementStatus | None = next((choice for choice in DISAGREEMENT_STATUSES if choice == value), None)
    if status is None:
        message: str = f"{where}: {value!r} is not one of {', '.join(DISAGREEMENT_STATUSES)}"
        raise CarryOverError(message)
    return status


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_type_map(decoded: JsonValue) -> TypeMap:
    """Read the mapping file from its decoded form.

    Args:
        decoded: The decoded ``resource-type-map.json``.

    Returns:
        The mapping.

    Raises:
        CarryOverError: The file is not version 1 of the mapping, or a part of it is malformed.

    """
    where: str = "the mapping file"
    document: dict[str, JsonValue] = _object(decoded, where)
    message: str
    if document.get("version") != MAP_VERSION:
        message = f"{where} is version {document.get('version')!r}, not {MAP_VERSION}"
        raise CarryOverError(message)
    conflicts: dict[str, JsonValue] = _object(document.get("conflicts"), f"{where}: conflicts")
    statuses: dict[str, JsonValue] = _object(conflicts.get("statuses"), f"{where}: conflicts.statuses")
    inventory: dict[str, JsonValue] = _object(conflicts.get("inventoryStatement"), f"{where}: inventoryStatement")
    shared: dict[str, JsonValue] = _object(document.get("sharedRepositories"), f"{where}: sharedRepositories")
    service: dict[str, JsonValue] = _object(document.get("serviceRepositories"), f"{where}: serviceRepositories")
    stated: str = _text(inventory, "lifecycle", where)
    lifecycle: Lifecycle | None = next((choice for choice in LIFECYCLES if choice == stated), None)
    if lifecycle is None:
        message = f"{where}: {stated!r} is not a lifecycle"
        raise CarryOverError(message)
    types: dict[str, JsonValue] = _object(document.get("resourceTypes"), f"{where}: resourceTypes")
    rows: dict[str, JsonValue] = _object(document.get("rows"), f"{where}: rows")
    return TypeMap(
        resource_types={name: _mapped(value, f"{where}: resourceTypes.{name}") for name, value in types.items()},
        rows={name: _mapped(value, f"{where}: rows.{name}") for name, value in rows.items()},
        conflict_statuses={name: _disagreement_status(value, f"{where}: {name}") for name, value in statuses.items()},
        disposition_status=_disagreement_status(conflicts.get("withDisposition"), f"{where}: withDisposition"),
        open_question_status=_disagreement_status(conflicts.get("openQuestion"), f"{where}: openQuestion"),
        inventory_document=_text(inventory, "document", where),
        inventory_lifecycle=lifecycle,
        shared_prefixes=_strings(shared, "prefixes", where),
        shared_suffixes=_strings(shared, "suffixes", where),
        service_suffix=_text(service, "suffix", where),
        service_role=_text(service, "inventoryRole", where),
        no_code_lifecycles=_strings(document, "noCodeLifecycles", where),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_inventory(decoded: JsonValue) -> dict[str, InventoryEntry]:
    """Read a ``polyrepo inventory`` listing from its decoded form.

    Args:
        decoded: The decoded listing: an array of repositories, each with ``name`` and, where
            known, ``role``, ``lifecycle`` and ``hasCode``.

    Returns:
        The repositories by reduced name.

    Raises:
        CarryOverError: The listing is not an array of repositories.

    """
    if not isinstance(decoded, list):
        message: str = "the repository inventory is not a JSON array"
        raise CarryOverError(message)
    entries: dict[str, InventoryEntry] = {}
    item: JsonValue
    for item in decoded:
        entry: dict[str, JsonValue] = _object(item, "the repository inventory")
        has_code: JsonValue = entry.get("hasCode")
        name: str = _text(entry, "name", "the repository inventory")
        entries[name_key(name)] = InventoryEntry(
            name=name,
            role=_optional(entry, "role", name),
            lifecycle=_optional(entry, "lifecycle", name),
            has_code=has_code if isinstance(has_code, bool) else None,
        )
    return entries


def _code_state(carry: _Carry, repository: str) -> CodeState:
    """Decide the code marker of everything in one registered repository.

    Returns:
        ``legacy`` when the repository holds code no pipeline built; ``none`` when the inventory
        says it holds none. Without an inventory a registered repository is ``legacy``.

    """
    if carry.inventory is None:
        return CODE_LEGACY
    entry: InventoryEntry = carry.inventory[name_key(repository)]
    if entry.has_code is not None:
        return CODE_LEGACY if entry.has_code else CODE_NONE
    return CODE_NONE if entry.lifecycle in carry.types.no_code_lifecycles else CODE_LEGACY


def _is_shared(carry: _Carry, repository: str) -> bool:
    """Tell whether a repository holds a shared capability by its name.

    Returns:
        True when the name starts with a shared prefix or ends with a shared suffix.

    """
    return repository.startswith(carry.types.shared_prefixes) or repository.endswith(carry.types.shared_suffixes)


def _described_by(carry: _Carry, evidence: Sequence[Evidence]) -> list[Link]:
    """Turn citations into links to the documents cited.

    Returns:
        One ``describedBy`` link per document and section cited, without repeats. A citation of
        something that is not a document of the vault is counted as dropped.

    """
    links: dict[tuple[str, str], Link] = {}
    cited: Evidence
    for cited in evidence:
        if cited.path not in carry.lifecycles:
            reason: str = NOT_IN_VAULT if cited.path.endswith(".md") and "/" in cited.path else NOT_A_DOCUMENT
            carry.dropped[reason] = carry.dropped.get(reason, 0) + 1
            continue
        link: Link = {"type": LINK_DESCRIBED_BY, "to": make_id(KIND_DOCUMENT, cited.path)}
        if cited.section:
            link["heading"] = cited.section
        links.setdefault((cited.path, cited.section), link)
        carry.evidence_carried += 1
    return list(links.values())


def _status(row: OldRow) -> Status | None:
    """Read the status of a row of the element matrix.

    Returns:
        The status, or None when the row states none.

    Raises:
        CarryOverError: The row states a status the matrix does not have.

    """
    if row.status is None:
        return None
    status: Status | None = next((choice for choice in STATUSES if choice == row.status), None)
    if status is None:
        message: str = f"{row.old_id}: the status {row.status!r} has no counterpart in the matrix"
        raise CarryOverError(message)
    return status


def _mapped_type(carry: _Carry, row: OldRow) -> MappedType:
    """Find what an element row becomes.

    Returns:
        The kind and controlled resource type the mapping file gives the row.

    Raises:
        CarryOverError: The mapping file has no entry for the row's resource type, or for the
            row itself when it states none.

    """
    message: str
    if row.resource_type is None:
        if row.old_id not in carry.types.rows:
            message = f"{row.old_id} states no resource type and the mapping file's rows table does not name it"
            raise CarryOverError(message)
        return carry.types.rows[row.old_id]
    if row.resource_type not in carry.types.resource_types:
        message = f"the resource type {row.resource_type!r} ({row.old_id}) has no entry in the mapping file"
        raise CarryOverError(message)
    return carry.types.resource_types[row.resource_type]


def _new_id(carry: _Carry, row: OldRow) -> NodeId:
    """Name the row a row of the element matrix becomes.

    Returns:
        The same id for a repository or a stack; for an element, its id with the element's new
        kind in place of ``element``.

    Raises:
        CarryOverError: The row is of a kind the element matrix does not have.

    """
    rest: str = row.old_id.partition(":")[2]
    if row.kind in {OLD_REPOSITORY, OLD_STACK}:
        return as_node_id(row.old_id)
    if row.kind != OLD_ELEMENT:
        message: str = f"{row.old_id}: {row.kind!r} is not a kind of element matrix row"
        raise CarryOverError(message)
    return as_node_id(f"{_mapped_type(carry, row).kind}:{rest}")


def _aliases(carry: _Carry, row: OldRow, new_id: NodeId) -> list[str]:
    """Collect the other names a carried row answers to.

    Returns:
        The names the element matrix's alias table gives the row, the stack names code declared
        for it, and its former id when its id changed; without the row's own name.

    """
    names: list[str] = [name for name, ids in carry.old.aliases.items() if row.old_id in ids]
    names.extend(row.declared)
    if new_id != row.old_id:
        names.append(row.old_id)
    own: str = name_key(row.name)
    return sorted({name for name in names if name_key(name) != own})


def _carry_row(carry: _Carry, row: OldRow, shared: set[str]) -> Node:
    """Build the row one row of the element matrix becomes.

    Returns:
        The row, with its links, its code marker and an approval still to be decided.

    """
    new_id: NodeId = carry.ids[row.old_id]
    contained: list[Link] = [
        {"type": LINK_CONTAINS, "to": carry.ids[child]} for child in row.contains if child in carry.ids
    ]
    node: Node = {
        "id": new_id,
        "kind": _kind(new_id),
        "name": row.name,
        "purpose": row.purpose,
        "links": [*contained, *_described_by(carry, row.evidence)],
        "changed": carry.stamp.change(),
        "code": {"state": _code_state(carry, row.repository)},
        "approval": {"state": APPROVAL_UNVERIFIED},
    }
    aliases: list[str] = _aliases(carry, row, new_id)
    if aliases:
        node["aliases"] = aliases
    status: Status | None = _status(row)
    if status is not None:
        node["status"] = status
    if row.kind == OLD_REPOSITORY:
        node["shared"] = name_key(row.repository) in shared
        return node
    node["repository"] = row.repository
    node["stack"] = None if row.kind == OLD_STACK else row.stack
    if row.kind == OLD_ELEMENT:
        node["resourceType"] = _mapped_type(carry, row).resource_type
        node["shared"] = name_key(row.repository) in shared
    return node


def _kind(node_id: NodeId) -> Kind:
    """Read the kind a carried row's id states.

    Returns:
        The kind before the colon: a repository, a stack or an element kind.

    Raises:
        CarryOverError: The id starts with no kind a carried row can have.

    """
    prefix: str = node_id.partition(":")[0]
    kind: Kind
    for kind in (KIND_REPOSITORY, KIND_STACK, *ELEMENT_KINDS):
        if kind == prefix:
            return kind
    message: str = f"{node_id} is not the id of a repository, a stack or an element"
    raise CarryOverError(message)


def _carry_rows(carry: _Carry) -> set[str]:
    """Carry every row of the element matrix.

    Returns:
        The reduced names of the shared repositories: those shared by name, and those that hold
        a library or a layer.

    Raises:
        CarryOverError: A repository row is missing from the inventory that was passed in.

    """
    row: OldRow
    for row in carry.old.rows:
        carry.ids[row.old_id] = _new_id(carry, row)
    registered: list[OldRow] = [row for row in carry.old.rows if row.kind == OLD_REPOSITORY]
    missing: list[str] = [
        row.name for row in registered if carry.inventory is not None and name_key(row.name) not in carry.inventory
    ]
    if missing:
        message: str = f"the repository inventory does not list {', '.join(sorted(missing))}"
        raise CarryOverError(message)
    shared: set[str] = {name_key(row.name) for row in registered if _is_shared(carry, row.name)}
    shared.update(
        name_key(row.repository)
        for row in carry.old.rows
        if row.kind == OLD_ELEMENT and _kind(carry.ids[row.old_id]) in {KIND_LIBRARY, KIND_LAYER}
    )
    for row in carry.old.rows:
        carry.matrix["nodes"][carry.ids[row.old_id]] = _carry_row(carry, row, shared)
    return shared


def _carry_unregistered(carry: _Carry) -> list[str]:
    """Give every repository the architecture names without a row an unregistered repository row.

    Returns:
        The names of the repositories added.

    """
    added: list[str] = []
    entry: Unresolved
    for entry in carry.old.unresolved:
        if entry.name is None or make_id(KIND_REPOSITORY, entry.name) in carry.matrix["nodes"]:
            continue
        carry.matrix["nodes"][make_id(KIND_REPOSITORY, entry.name)] = {
            "id": make_id(KIND_REPOSITORY, entry.name),
            "kind": KIND_REPOSITORY,
            "name": entry.name,
            "purpose": entry.reason,
            "links": _described_by(carry, entry.evidence),
            "changed": carry.stamp.change(),
            "status": STATUS_UNREGISTERED,
            "shared": _is_shared(carry, entry.name),
            "code": {"state": CODE_NONE},
            "approval": {"state": APPROVAL_UNVERIFIED},
        }
        added.append(entry.name)
    return added


def _is_service(carry: _Carry, repository: str) -> bool:
    """Tell whether a registered repository is a service.

    Returns:
        True when the inventory gives it the service role; without an inventory, when its name
        ends with the service suffix of the repository naming standard.

    """
    if carry.inventory is None:
        return repository.endswith(carry.types.service_suffix)
    return carry.inventory[name_key(repository)].role == carry.types.service_role


def _carry_services(carry: _Carry) -> int:
    """Give every service repository a service row that contains its repository and its stacks.

    Returns:
        How many service rows were added.

    """
    count: int = 0
    row: OldRow
    for row in carry.old.rows:
        if row.kind != OLD_REPOSITORY or not _is_service(carry, row.name):
            continue
        repository: Node = carry.matrix["nodes"][carry.ids[row.old_id]]
        stacks: list[NodeId] = [carry.ids[child] for child in row.contains if child.startswith(OLD_STACK + ":")]
        service: Node = {
            "id": make_id(KIND_SERVICE, row.name),
            "kind": KIND_SERVICE,
            "name": row.name,
            "purpose": row.purpose,
            "links": [{"type": LINK_CONTAINS, "to": target} for target in (repository["id"], *stacks)],
            "changed": carry.stamp.change(),
            "shared": repository.get("shared", False),
            "code": {"state": _code_state(carry, row.name)},
            "approval": {"state": APPROVAL_UNVERIFIED},
        }
        if "status" in repository:
            service["status"] = repository["status"]
        carry.matrix["nodes"][service["id"]] = service
        count += 1
    return count


def _carry_features(carry: _Carry, shared: set[str]) -> list[NodeId]:
    """Give every shared repository one supporting feature, provided by what the repository holds.

    Returns:
        The ids of the features added, in id order.

    """
    added: list[NodeId] = []
    row: OldRow
    for row in carry.old.rows:
        if row.kind != OLD_REPOSITORY or name_key(row.name) not in shared:
            continue
        providers: list[NodeId] = [
            carry.ids[child] for child in row.contains if _kind(carry.ids[child]) in ELEMENT_KINDS
        ]
        if make_id(KIND_SERVICE, row.name) in carry.matrix["nodes"]:
            providers.append(make_id(KIND_SERVICE, row.name))
        feature: NodeId = make_id(KIND_FEATURE, row.name)
        carry.matrix["nodes"][feature] = {
            "id": feature,
            "kind": KIND_FEATURE,
            "name": row.name + CAPABILITY_SUFFIX,
            "purpose": row.purpose,
            "links": [{"type": LINK_PROVIDED_BY, "to": provider} for provider in providers],
            "changed": carry.stamp.change(),
            "featureType": FEATURE_SUPPORTING,
            "provides": [],
            "shared": True,
            "approval": {"state": APPROVAL_UNVERIFIED},
        }
        added.append(feature)
    return sorted(added)


def _statements(carry: _Carry, heading: str, note: Conflict, row: Sequence[Evidence]) -> list[DisputedStatement]:
    """Build the statements of a carried conflict note.

    Returns:
        The note itself, as a statement of the inventory record, then one statement per vault
        document the note cites, or the row cites when the note cites none.

    """
    statements: list[DisputedStatement] = [
        {
            "document": carry.types.inventory_document,
            "heading": heading,
            "text": note.text,
            "lifecycle": carry.types.inventory_lifecycle,
        },
    ]
    cited: Evidence
    for cited in note.evidence or row:
        if cited.path not in carry.lifecycles or not cited.quote:
            continue
        statement: DisputedStatement = {
            "document": cited.path,
            "heading": cited.section,
            "text": cited.quote,
            "lifecycle": carry.lifecycles[cited.path],
        }
        if cited.line is not None:
            statement["line"] = cited.line
        statements.append(statement)
    return statements


def _conflict_status(carry: _Carry, where: str, conflict: Conflict) -> DisagreementStatus:
    """Decide the status a carried conflict note has as a disagreement.

    Returns:
        The status the mapping file gives the note's status; the mapping file's status for a
        note that records a disposition and no status; its status for an open question otherwise.

    Raises:
        CarryOverError: The note states a status the mapping file does not name.

    """
    if conflict.status is not None:
        if conflict.status not in carry.types.conflict_statuses:
            message: str = f"{where}: the conflict status {conflict.status!r} has no entry in the mapping file"
            raise CarryOverError(message)
        return carry.types.conflict_statuses[conflict.status]
    return carry.types.disposition_status if conflict.settled_by_disposition else carry.types.open_question_status


def _carry_conflicts(carry: _Carry) -> tuple[list[NodeId], list[str]]:
    """Turn every conflict note of a row into a disagreement row.

    A note needs two statements to be a disagreement: itself, and a quoted statement of a vault
    document. A note with no such quotation is not carried, and is reported.

    Returns:
        The ids of the disagreement rows added, and one line per note not carried.

    """
    notes: list[tuple[str, str, Conflict, tuple[Evidence, ...]]] = [
        (row.old_id, row.name, conflict, row.evidence) for row in carry.old.rows for conflict in row.conflicts
    ]
    added: list[NodeId] = []
    skipped: list[str] = []
    counts: dict[str, int] = {}
    for old_id, name, conflict, fallback in notes:
        statements: list[DisputedStatement] = _statements(carry, old_id, conflict, fallback)
        if len(statements) < len(("note", "quotation")):
            skipped.append(f"{old_id}: {conflict.text} (no quoted statement of a vault document)")
            continue
        counts[old_id] = counts.get(old_id, 0) + 1
        status: DisagreementStatus = _conflict_status(carry, old_id, conflict)
        key: NodeId = make_id(KIND_DISAGREEMENT, CARRIED, *old_id.split(":", 1), str(counts[old_id]))
        carry.matrix["nodes"][key] = {
            "id": key,
            "kind": KIND_DISAGREEMENT,
            "name": f"{name}: {conflict.text}",
            "links": [],
            "changed": carry.stamp.change(),
            "statements": statements,
            "reason": conflict.resolution,
            "settledBy": carry.stamp.by if status == DISAGREEMENT_SETTLED else None,
            "evidence": sorted({statement["document"] for statement in statements}),
            "disagreementStatus": status,
        }
        added.append(key)
    return added, skipped


def _carry_shows(carry: _Carry, documents: Sequence[DocumentRead]) -> tuple[int, int, int]:
    """Link every name a document shows to the row that answers to it, or record it as a term.

    A name resolves the way the element matrix resolved it: through its alias table. A name with
    one row gets a ``describedBy`` link from that row; a name with several gets one from each,
    marked ambiguous; a name with none becomes a term row with a ``shownIn`` link.

    Returns:
        How many distinct names resolved to one row, were ambiguous, and resolved to none.

    """
    outcomes: dict[str, int] = {}
    document: DocumentRead
    for document in documents:
        target: NodeId = make_id(KIND_DOCUMENT, document.path)
        shown: str
        for shown in document.shows:
            candidates: list[NodeId] = [
                carry.ids[old] for old in carry.old.aliases.get(name_key(shown), ()) if old in carry.ids
            ]
            outcomes[name_key(shown)] = len(candidates)
            if not candidates:
                term: Node = carry.matrix["nodes"].setdefault(
                    make_id(KIND_TERM, shown),
                    {
                        "id": make_id(KIND_TERM, shown),
                        "kind": KIND_TERM,
                        "name": shown,
                        "links": [],
                        "changed": carry.stamp.change(),
                    },
                )
                term["links"].append({"type": LINK_SHOWN_IN, "to": target})
                continue
            candidate: NodeId
            for candidate in candidates:
                links: list[Link] = carry.matrix["nodes"][candidate]["links"]
                if any(link["type"] == LINK_DESCRIBED_BY and link["to"] == target for link in links):
                    continue
                link: Link = {"type": LINK_DESCRIBED_BY, "to": target}
                if len(candidates) > 1:
                    link["ambiguous"] = True
                links.append(link)
    resolved: int = sum(1 for count in outcomes.values() if count == 1)
    unresolved: int = sum(1 for count in outcomes.values() if count == 0)
    return resolved, len(outcomes) - resolved - unresolved, unresolved


def _carried_approval(stamp: Stamp) -> Approval:
    """Build the approval of a row carried from effective documents.

    Returns:
        An approval on the basis of the carry-over, at the carry-over's moment.

    """
    return {"state": APPROVAL_APPROVED, "basis": BASIS_CARRIED_FROM_EFFECTIVE_ARC42, "at": stamp.at}


def _approve_described(carry: _Carry) -> None:
    """Approve every carried row that effective documents describe.

    A repository, stack, service, component, library, layer or infrastructure row is approved,
    on the basis of the carry-over, when it has at least one ``describedBy`` link and every
    document it is described by is effective. A service takes the approval of its repository.
    """
    node: Node
    for node in carry.matrix["nodes"].values():
        if node["kind"] not in {KIND_REPOSITORY, KIND_STACK, *ELEMENT_KINDS}:
            continue
        described: list[NodeId] = [link["to"] for link in node["links"] if link["type"] == LINK_DESCRIBED_BY]
        effective: bool = all(
            carry.matrix["nodes"][target].get("lifecycle") == LIFECYCLE_EFFECTIVE for target in described
        )
        if described and effective:
            node["approval"] = _carried_approval(carry.stamp)
    for node in carry.matrix["nodes"].values():
        if node["kind"] != KIND_SERVICE:
            continue
        repository: Approval | None = carry.matrix["nodes"][make_id(KIND_REPOSITORY, node["name"])].get("approval")
        if repository is not None and repository["state"] == APPROVAL_APPROVED:
            node["approval"] = _carried_approval(carry.stamp)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def carry_over(
    sources: CarrySources,
    documents: Sequence[DocumentRead],
    synced: DocumentsSyncedAt,
    stamp: Stamp,
) -> tuple[Matrix, CarryReport]:
    """Build the matrix from the element matrix and the vault's architecture documents.

    With a repository inventory among the sources, a repository is a service when its role says
    so, and holds no code when the listing says so. Without one, a repository is a service by its
    name and every registered repository is taken to hold code no pipeline built.

    Args:
        sources: The element matrix, the mapping file and, when there is one, the inventory.
        documents: Every architecture document of the vault, as read now.
        synced: The vault commit the documents were read at, and the documents that differed from it.
        stamp: The moment of the carry-over and what to record as its maker.

    Returns:
        The matrix, and the account of what became of every part of the element matrix.

    Raises:
        CarryOverError: A row of the element matrix has no row in the result.

    """
    matrix: Matrix = empty_matrix(stamp.at)
    matrix["documentsSyncedAt"] = synced
    apply_documents(matrix, documents, [], stamp, carried=True)
    carry: _Carry = _Carry(
        matrix=matrix,
        old=sources.old,
        types=sources.types,
        stamp=stamp,
        inventory=sources.inventory,
        lifecycles={document.path: document.lifecycle for document in documents},
    )
    shared: set[str] = _carry_rows(carry)
    unregistered: list[str] = _carry_unregistered(carry)
    services: int = _carry_services(carry)
    features: list[NodeId] = _carry_features(carry, shared)
    conflicts: tuple[list[NodeId], list[str]] = _carry_conflicts(carry)
    shows: tuple[int, int, int] = _carry_shows(carry, documents)
    _approve_described(carry)
    matrix["resourceTypes"] = sorted({
        entry.resource_type for entry in (*sources.types.resource_types.values(), *sources.types.rows.values())
    })
    lost: list[str] = [row.old_id for row in sources.old.rows if carry.ids.get(row.old_id) not in matrix["nodes"]]
    if lost:
        message: str = f"{len(lost)} rows of the element matrix were not carried: {', '.join(lost[:10])}"
        raise CarryOverError(message)
    by_kind: dict[str, int] = {}
    node: Node
    for node in matrix["nodes"].values():
        by_kind[node["kind"]] = by_kind.get(node["kind"], 0) + 1
    report: CarryReport = {
        "rowsBefore": len(sources.old.rows),
        "carried": len(sources.old.rows) - len(lost),
        "notCarried": lost,
        "renamed": sum(1 for former, present in carry.ids.items() if former != present),
        "byKind": by_kind,
        "unregisteredRepositories": unregistered,
        "services": services,
        "supportingFeatures": features,
        "documents": by_kind.get(KIND_DOCUMENT, 0),
        "terms": by_kind.get(KIND_TERM, 0),
        "disagreements": conflicts[0],
        "conflictNotesNotCarried": conflicts[1],
        "unresolvedNotesNotCarried": [
            f"{entry.repository}: {entry.reason}" for entry in sources.old.unresolved if entry.repository is not None
        ],
        "evidenceCarried": carry.evidence_carried,
        "evidenceDropped": carry.dropped,
        "showsResolved": shows[0],
        "showsAmbiguous": shows[1],
        "showsUnresolved": shows[2],
        "codeStateFrom": "the repository naming rule" if sources.inventory is None else "the repository inventory",
    }
    return matrix, report
