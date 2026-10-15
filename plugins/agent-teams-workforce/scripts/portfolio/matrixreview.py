"""What the review of one Epic is handed: the documents the Epic reaches that are not effective.

:func:`review_scope` (``review-scope``) is a read with no judgment in it. It walks from an Epic
to its requirements and to the features that serve them, with the features those are supported by
to any depth, and returns the documents a ``covers`` relationship joins to one of the
requirements, or a ``describedBy`` relationship joins to one of the features or to one of the
elements the architect's result adds or changes, whose ``lifecycle`` is not ``effective``, each
with the headings those relationships name.

The matrix holds no approval record: a document's ``lifecycle`` mirrors its arc42 front matter,
so what is in review for an Epic is exactly this list, and nothing here changes the matrix.
"""

import sys
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    KIND_EPIC,
    REL_COVERS,
    REL_DESCRIBED_BY,
    REL_HAS_REQUIREMENT,
    REL_SERVED_BY,
    REL_SUPPORTED_BY,
    Entry,
    EntryId,
    EntryKind,
    JsonValue,
    MatrixError,
    Relationship,
    RelationshipKind,
    Side,
)
from matrixstore import Matrix, as_entry_id
from matrixtraverse import epic_id

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

ATTR_LIFECYCLE: Final = "lifecycle"
ATTR_HEADING: Final = "heading"
LIFECYCLE_EFFECTIVE: Final = "effective"
"""The lifecycle of a document that is approved; a document of any other lifecycle is in the scope."""


class ScopeReach(TypedDict):
    """One relationship through which an Epic reaches a document."""

    relationship: RelationshipKind
    entry: EntryId
    """The requirement the document covers, or the feature or added or changed element it describes."""
    heading: str
    """The heading the relationship names; empty when it names none."""
    side: Side


class ScopeDocument(TypedDict):
    """One document an Epic reaches that is not effective."""

    id: EntryId
    kind: EntryKind
    name: str
    side: Side
    lifecycle: str
    headings: list[str]
    """The headings reached, sorted and without repeats."""
    reachedBy: list[ScopeReach]


class ReviewScope(TypedDict):
    """What ``review-scope`` prints."""

    epic: EntryId
    requirements: list[EntryId]
    features: list[EntryId]
    """The features that serve a requirement, then the features those are supported by."""
    documents: list[ScopeDocument]
    """The documents reached whose lifecycle is not effective, in id order."""


def _heading(relationship: Relationship) -> str:
    """Read the document heading a relationship names.

    Returns:
        The heading; empty when the relationship names none.

    """
    heading: JsonValue = relationship.attributes.get(ATTR_HEADING)
    return heading if isinstance(heading, str) else ""


def _lifecycle(document: Entry) -> str:
    """Read the lifecycle a document entry mirrors.

    Returns:
        The lifecycle; empty when the entry states none.

    """
    lifecycle: JsonValue = document.attributes.get(ATTR_LIFECYCLE)
    return lifecycle if isinstance(lifecycle, str) else ""


def _with_supporting(matrix: Matrix, serving: list[EntryId]) -> list[EntryId]:
    """Add to some features the features they are supported by, to any depth.

    Returns:
        The features given, then each feature a ``supportedBy`` relationship reaches from one
        already listed, in the order found and without repeats.

    """
    features: dict[EntryId, None] = dict.fromkeys(serving)
    queue: deque[EntryId] = deque(features)
    while queue:
        relationship: Relationship
        for relationship in matrix.outgoing(queue.popleft(), (REL_SUPPORTED_BY,)):
            if relationship.end not in features:
                features[relationship.end] = None
                queue.append(relationship.end)
    return list(features)


def _reach(relationship: Relationship, entry: EntryId) -> ScopeReach:
    """Render one relationship through which an Epic reaches a document.

    Returns:
        The relationship's kind, the entry it reaches the document from, the heading it names
        and its side.

    """
    return {
        "relationship": relationship.kind,
        "entry": entry,
        "heading": _heading(relationship),
        "side": relationship.side,
    }


def _reached(
    matrix: Matrix,
    requirements: Iterable[EntryId],
    described: Iterable[EntryId],
) -> dict[EntryId, list[ScopeReach]]:
    """Collect the documents some requirements and described entries reach.

    Returns:
        Each document a ``covers`` relationship joins to one of the requirements, or a
        ``describedBy`` relationship joins to one of the described entries, with the
        relationships that reach it.

    """
    covering: list[tuple[EntryId, ScopeReach]] = [
        (relationship.start, _reach(relationship, requirement))
        for requirement in requirements
        for relationship in matrix.incoming(requirement, (REL_COVERS,))
    ]
    describing: list[tuple[EntryId, ScopeReach]] = [
        (relationship.end, _reach(relationship, entry_id))
        for entry_id in described
        for relationship in matrix.outgoing(entry_id, (REL_DESCRIBED_BY,))
    ]
    reached: dict[EntryId, list[ScopeReach]] = {}
    document_id: EntryId
    reach: ScopeReach
    for document_id, reach in (*covering, *describing):
        reached.setdefault(document_id, []).append(reach)
    return reached


def review_scope(matrix: Matrix, bead: str, added_or_changed: Sequence[str] = ()) -> ReviewScope:
    """List the documents one Epic reaches that are not effective, with the headings reached.

    Nothing is changed. An empty beads id raises ``ValueError`` from ``epic_id``, an Epic the
    matrix does not hold raises ``MatrixError`` from ``Matrix.entry``, and an added or changed id
    that does not have the form of an entry id raises ``MatrixError`` from ``as_entry_id``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id, or the id of its entry.
        added_or_changed: The ids the architect's result lists under ``addedOrChangedElements``;
            the documents that describe them are reached too.

    Returns:
        The Epic, its requirements, the features that serve them with the features those are
        supported by, and each document a ``covers`` relationship joins to one of the
        requirements or a ``describedBy`` relationship joins to one of the features or added or
        changed elements whose lifecycle is not effective, with the headings and the
        relationships that reach it.

    Raises:
        TypeError: ``bead`` is not a string.
        MatrixError: The entry is not an Epic.

    """
    message: str
    if not isinstance(bead, str):
        message = "an Epic is named by its beads id, a string"
        raise TypeError(message)
    epic: EntryId = epic_id(bead)
    if matrix.entry(epic).kind != KIND_EPIC:
        message = f"{epic} is not an Epic"
        raise MatrixError(message)
    requirements: list[EntryId] = [stated.end for stated in matrix.outgoing(epic, (REL_HAS_REQUIREMENT,))]
    serving: list[EntryId] = list(
        dict.fromkeys(
            served.end for requirement in requirements for served in matrix.outgoing(requirement, (REL_SERVED_BY,))
        ),
    )
    features: list[EntryId] = _with_supporting(matrix, serving)
    elements: list[EntryId] = [as_entry_id(element) for element in dict.fromkeys(added_or_changed)]
    described: list[EntryId] = list(dict.fromkeys([*features, *elements]))
    reached: dict[EntryId, list[ScopeReach]] = _reached(matrix, requirements, described)
    documents: list[ScopeDocument] = []
    document_id: EntryId
    for document_id in sorted(reached):
        document: Entry = matrix.entry(document_id)
        lifecycle: str = _lifecycle(document)
        if lifecycle == LIFECYCLE_EFFECTIVE:
            continue
        documents.append({
            "id": document.id,
            "kind": document.kind,
            "name": document.name,
            "side": document.side,
            "lifecycle": lifecycle,
            "headings": sorted({reach["heading"] for reach in reached[document_id] if reach["heading"]}),
            "reachedBy": reached[document_id],
        })
    return {"epic": epic, "requirements": requirements, "features": features, "documents": documents}
