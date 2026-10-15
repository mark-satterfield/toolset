"""Bring the matrix's events up to date with the event catalog in arc42 section 6 (``sync-events``).

The event catalog is one Markdown document whose JSON block is an object keyed by event type;
each value holds the event's ``description`` and its ``producers``, by the names of the services
and components that publish it. :func:`sync_events` makes the architecture side of the matrix
match it in one change:

- each catalogued event's purpose is the catalog's description, and an event the matrix lacks is
  added;
- its ``publishes`` relationships are the catalog's producers, each mapped to the one
  architecture-side service or component whose name or alias it is. A producer name that maps
  to no entry is reported; an event with such a name keeps the publishers it has and gains the
  ones that map;
- an architecture-side event the catalog does not hold is removed with its relationships, and
  then every EventBridge rule that matched it and is left matching nothing, without
  ``matchesAllEvents``, is removed too.

A catalog key holding a ``{placeholder}`` names a family of event types (``{domain}.ai-usage.reported``):
it adds no event, and the events whose type fits it are catalogued as they stand. An event that
states ``externalSource`` is published outside SkillSpoke, which the catalog does not list, so it
is left as it is. Repository-side events state what code shows and are not touched.
"""

import json
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    KIND_COMPONENT,
    KIND_EVENT,
    KIND_INFRASTRUCTURE,
    KIND_SERVICE,
    REL_MATCHES,
    REL_PUBLISHES,
    SIDE_ARCHITECTURE,
    Entry,
    EntryId,
    EntryKind,
    Relationship,
)
from matrixstore import (
    ATTR_EXTERNAL_SOURCE,
    ATTR_MATCHES_ALL_EVENTS,
    ATTR_RESOURCE_TYPE,
    RESOURCE_EVENTBRIDGE_RULE,
    Matrix,
    MatrixRefusedError,
    make_id,
    name_key,
)

CATALOG_PATH: Final = Path("arc42") / "06-runtime-view" / "event-catalog.md"
"""The event catalog, relative to the architecture root."""
PUBLISHER_KINDS: Final[tuple[EntryKind, ...]] = (KIND_SERVICE, KIND_COMPONENT)
"""The kinds of entry a producer name may map to."""
_JSON_BLOCK: Final[re.Pattern[str]] = re.compile(r"^```json[ \t]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{[^{}]+\}")
_PLACEHOLDER_MATCH: Final = r"[^.\s]+"
"""What a placeholder of a catalog key stands for: one dot-free part of an event type."""


@dataclass(frozen=True, slots=True)
class CatalogEvent:
    """One event type as the event catalog states it."""

    event_type: str
    description: str
    producers: tuple[str, ...]


class EventsSynced(TypedDict):
    """What :func:`sync_events` did: also what ``sync-events`` prints."""

    catalogued: int
    """How many event types the catalog holds, families included."""
    added: list[EntryId]
    updated: list[EntryId]
    """Events whose purpose or publishers changed."""
    removed: list[EntryId]
    rulesRemoved: list[EntryId]
    """EventBridge rules removed because every event they matched was removed."""
    familyEvents: list[EntryId]
    """Events kept because their type fits a catalog family such as ``{domain}.ai-usage.reported``."""
    external: list[EntryId]
    """Events published outside SkillSpoke, which the catalog does not list; left as they are."""
    unmappedProducers: list[str]
    """Producer names that are the name or alias of no one architecture-side service or component."""


def _text(value: object, where: str) -> str:
    """Narrow one catalog value to a string.

    Returns:
        The value.

    Raises:
        MatrixRefusedError: The value is not a non-empty string.

    """
    if not isinstance(value, str) or not value.strip():
        message: str = f"the event catalog: {where} must be a non-empty string"
        raise MatrixRefusedError(message)
    return value


def _catalog_event(event_type: str, value: object) -> CatalogEvent:
    """Narrow one member of the catalog's JSON object to a catalogued event.

    Returns:
        The event type with its description and producer names.

    Raises:
        MatrixRefusedError: The value is not an object holding a description and a list of producers.

    """
    if not isinstance(value, dict):
        message: str = f"the event catalog: {event_type} must be an object"
        raise MatrixRefusedError(message)
    producers: object = value.get("producers")
    if not isinstance(producers, list):
        message = f"the event catalog: {event_type}/producers must be a list"
        raise MatrixRefusedError(message)
    return CatalogEvent(
        event_type=event_type,
        description=_text(value.get("description"), f"{event_type}/description"),
        producers=tuple(_text(producer, f"{event_type}/producers") for producer in producers),
    )


def read_catalog(path: Path) -> list[CatalogEvent]:
    """Read the event catalog's JSON block.

    Args:
        path: The event catalog document.

    Returns:
        Every catalogued event, in the catalog's order.

    Raises:
        MatrixRefusedError: The document cannot be read, holds no JSON block, or the block is not
            an object of events each with a description and producers.

    """
    message: str
    try:
        with path.open(encoding="utf-8") as catalog_file:
            text: str = catalog_file.read()
    except OSError as error:
        message = f"reading the event catalog {path} failed"
        raise MatrixRefusedError(message) from error
    block: re.Match[str] | None = _JSON_BLOCK.search(text)
    if block is None:
        message = f"the event catalog {path} holds no JSON block"
        raise MatrixRefusedError(message)
    try:
        decoded: object = json.loads(block.group(1))
    except json.JSONDecodeError as error:
        message = f"the JSON block of the event catalog {path} is not valid JSON"
        raise MatrixRefusedError(message) from error
    if not isinstance(decoded, dict):
        message = f"the JSON block of the event catalog {path} must be an object keyed by event type"
        raise MatrixRefusedError(message)
    return [_catalog_event(str(event_type), value) for event_type, value in decoded.items()]


def _family_pattern(event_type: str) -> re.Pattern[str]:
    """Build the pattern of the event types a catalog family key names.

    Returns:
        A pattern that matches a whole event type, each placeholder standing for one dot-free part.

    """
    literal_parts: list[str] = _PLACEHOLDER.split(event_type)
    return re.compile(_PLACEHOLDER_MATCH.join(re.escape(part) for part in literal_parts) + r"\Z")


def _publisher_index(matrix: Matrix) -> dict[str, list[EntryId]]:
    """Index the architecture-side services and components by every name they answer to.

    Returns:
        Each name and alias, as names are compared, with the ids of the entries that have it.

    """
    named: list[tuple[str, EntryId]] = [
        (key, entry.id)
        for entry in matrix.entries(PUBLISHER_KINDS)
        if entry.side == SIDE_ARCHITECTURE
        for key in {name_key(entry.name), *(name_key(alias) for alias in entry.aliases)}
    ]
    index: dict[str, list[EntryId]] = {}
    for key, entry_id in sorted(named):
        index.setdefault(key, []).append(entry_id)
    return index


def _mapped(producers: tuple[str, ...], index: dict[str, list[EntryId]]) -> tuple[set[EntryId], list[str]]:
    """Map producer names to the one entry each names.

    Returns:
        The ids of the producers that map to exactly one entry, and the names that do not.

    """
    found: list[list[EntryId]] = [index.get(name_key(producer), []) for producer in producers]
    mapped: set[EntryId] = {ids[0] for ids in found if len(ids) == 1}
    unmapped: list[str] = [producer for producer, ids in zip(producers, found, strict=True) if len(ids) != 1]
    return mapped, unmapped


def _publishers(matrix: Matrix, event_id: EntryId) -> set[EntryId]:
    """List the entries the architecture side says publish an event.

    Returns:
        The ids of the architecture-side publishers.

    """
    return {held.start for held in matrix.incoming(event_id, (REL_PUBLISHES,)) if held.side == SIDE_ARCHITECTURE}


def _set_publishers(matrix: Matrix, event_id: EntryId, wanted: set[EntryId], *, keep_others: bool) -> bool:
    """Make an event's architecture-side publishers the ones wanted.

    Returns:
        True when a publishes relationship was added or removed.

    """
    held: set[EntryId] = _publishers(matrix, event_id)
    adding: set[EntryId] = wanted - held
    dropping: set[EntryId] = set() if keep_others else held - wanted
    for publisher in sorted(adding):
        matrix.link(Relationship(kind=REL_PUBLISHES, start=publisher, end=event_id, side=SIDE_ARCHITECTURE))
    for publisher in sorted(dropping):
        matrix.unlink(Relationship(kind=REL_PUBLISHES, start=publisher, end=event_id, side=SIDE_ARCHITECTURE))
    return bool(adding or dropping)


def _put_event(matrix: Matrix, event: CatalogEvent, result: EventsSynced) -> EntryId:
    """Add a catalogued event the matrix lacks, or give the one it holds the catalog's description.

    Returns:
        The event's id.

    """
    event_id: EntryId = make_id(KIND_EVENT, event.event_type)
    held: Entry | None = matrix.find(event_id)
    if held is None:
        matrix.put(
            Entry(
                id=event_id,
                kind=KIND_EVENT,
                name=event.event_type,
                side=SIDE_ARCHITECTURE,
                purpose=event.description,
            ),
        )
        result["added"].append(event_id)
        return event_id
    if held.purpose != event.description or held.side != SIDE_ARCHITECTURE:
        matrix.put(replace(held, purpose=event.description, side=SIDE_ARCHITECTURE))
        result["updated"].append(event_id)
    return event_id


def _sync_event(matrix: Matrix, event: CatalogEvent, index: dict[str, list[EntryId]], result: EventsSynced) -> None:
    """Make one catalogued event's entry and publishers match the catalog."""
    event_id: EntryId = _put_event(matrix, event, result)
    mapped: set[EntryId]
    unmapped: list[str]
    mapped, unmapped = _mapped(event.producers, index)
    result["unmappedProducers"].extend(unmapped)
    changed: bool = _set_publishers(matrix, event_id, mapped, keep_others=bool(unmapped))
    if changed and event_id not in result["added"] and event_id not in result["updated"]:
        result["updated"].append(event_id)


def _is_rule_left_empty(matrix: Matrix, rule_id: EntryId) -> bool:
    """Report whether an EventBridge rule matches nothing.

    Returns:
        True when the entry is an EventBridge rule with no matches and without matchesAllEvents.

    """
    rule: Entry | None = matrix.find(rule_id)
    return (
        rule is not None
        and rule.kind == KIND_INFRASTRUCTURE
        and rule.attributes.get(ATTR_RESOURCE_TYPE) == RESOURCE_EVENTBRIDGE_RULE
        and ATTR_MATCHES_ALL_EVENTS not in rule.attributes
        and not matrix.outgoing(rule_id, (REL_MATCHES,))
    )


def _remove_uncatalogued(matrix: Matrix, gone: list[EntryId], result: EventsSynced) -> None:
    """Remove the events the catalog does not hold, then the rules left matching nothing."""
    rules: set[EntryId] = {held.start for event_id in gone for held in matrix.incoming(event_id, (REL_MATCHES,))}
    for event_id in gone:
        matrix.remove(event_id)
        result["removed"].append(event_id)
    for rule_id in sorted(rule_id for rule_id in rules if _is_rule_left_empty(matrix, rule_id)):
        matrix.remove(rule_id)
        result["rulesRemoved"].append(rule_id)


def sync_events(matrix: Matrix, catalog: list[CatalogEvent]) -> EventsSynced:
    """Make the matrix's architecture-side events match the event catalog.

    Args:
        matrix: The matrix, changed in place; the caller loads and saves it once.
        catalog: The catalogued events (:func:`read_catalog`).

    Returns:
        What was added, updated and removed, the events kept as family members or as external,
        and the producer names that map to no entry.

    """
    result: EventsSynced = {
        "catalogued": len(catalog),
        "added": [],
        "updated": [],
        "removed": [],
        "rulesRemoved": [],
        "familyEvents": [],
        "external": [],
        "unmappedProducers": [],
    }
    index: dict[str, list[EntryId]] = _publisher_index(matrix)
    families: list[CatalogEvent] = [event for event in catalog if _PLACEHOLDER.search(event.event_type)]
    singles: list[CatalogEvent] = [event for event in catalog if event not in families]
    patterns: list[re.Pattern[str]] = [_family_pattern(event.event_type) for event in families]
    family_unmapped: list[str] = [producer for event in families for producer in _mapped(event.producers, index)[1]]
    for event in singles:
        _sync_event(matrix, event, index, result)
    catalogued: set[EntryId] = {make_id(KIND_EVENT, event.event_type) for event in singles}
    uncatalogued: list[Entry] = [
        held for held in matrix.entries((KIND_EVENT,)) if held.side == SIDE_ARCHITECTURE and held.id not in catalogued
    ]
    result["external"] = [held.id for held in uncatalogued if ATTR_EXTERNAL_SOURCE in held.attributes]
    result["familyEvents"] = [
        held.id
        for held in uncatalogued
        if ATTR_EXTERNAL_SOURCE not in held.attributes and any(pattern.match(held.name) for pattern in patterns)
    ]
    kept: set[EntryId] = {*result["external"], *result["familyEvents"]}
    _remove_uncatalogued(matrix, [held.id for held in uncatalogued if held.id not in kept], result)
    result["unmappedProducers"] = sorted({*result["unmappedProducers"], *family_unmapped})
    return result
