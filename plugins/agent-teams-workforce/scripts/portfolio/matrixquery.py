"""The questions the matrix answers without anyone reading a document.

Every function here reads a matrix that is already loaded and changes nothing: which rows match
some words (:func:`find`), one row with the links that point at it (:func:`node_view`), what a
PRD involves and whether it is approved (:func:`prd_view`), which shared capabilities some
elements must use (:func:`uses_view`), which disagreements touch a document
(:func:`disagreements_for`), and the counts by kind and marker (:func:`summarize`). A link is
stored once, on the row it starts from; the reverse direction is computed here and never stored.
"""

import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    APPROVAL_APPROVED,
    CODED_KINDS,
    COVERAGE_APPROVED,
    FEATURE_SUPPORTING,
    KIND_DISAGREEMENT,
    KIND_DOCUMENT,
    KIND_FACT,
    KIND_FEATURE,
    KIND_PRD,
    KIND_REPOSITORY,
    KIND_SERVICE,
    KIND_STACK,
    KINDS,
    LINK_CONTAINS,
    LINK_DEPENDS_ON,
    LINK_DESCRIBED_BY,
    LINK_NEEDS,
    LINK_PROVIDED_BY,
    LINK_REALIZED_BY,
    LINK_RULES,
    LINK_USES,
    PLACED_KINDS,
    Anchor,
    ApprovalState,
    CodeState,
    Coverage,
    DocumentsSyncedAt,
    FeatureType,
    Kind,
    Lifecycle,
    Link,
    LinkType,
    Matrix,
    Node,
    NodeId,
    Provides,
)
from matrixstore import MatrixRefusedError, make_id, name_index, name_key, owner_of

DEFAULT_LIMIT: Final = 50
"""The most rows :func:`find` returns unless the caller asks for another number; 0 asks for all."""
MIN_TOKEN: Final = 2
CLOSURE_LINKS: Final[frozenset[LinkType]] = frozenset({
    LINK_NEEDS,
    LINK_USES,
    LINK_REALIZED_BY,
    LINK_PROVIDED_BY,
    LINK_DEPENDS_ON,
    LINK_DESCRIBED_BY,
})
"""The link types a PRD's closure follows from every row; ``contains`` is followed from a service only."""
_CAMEL: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_WORD: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+")


class RowSummary(TypedDict):
    """One row reduced to what identifies it, where it lives and its markers."""

    id: NodeId
    kind: Kind
    name: str
    purpose: NotRequired[str]
    approval: NotRequired[ApprovalState]
    code: NotRequired[CodeState]
    repository: NotRequired[str]
    stack: NotRequired[str]
    resourceType: NotRequired[str]
    shared: NotRequired[bool]
    featureType: NotRequired[FeatureType]
    path: NotRequired[str]
    lifecycle: NotRequired[Lifecycle]
    coverage: NotRequired[Coverage]
    bead: NotRequired[str]
    home: NotRequired[Anchor]


class Capability(TypedDict):
    """One supporting feature with what it provides and the rows that provide it."""

    feature: RowSummary
    provides: list[Provides]
    reliedOn: list[str]
    """The ids of the ``provides`` entries the asking rows' links name; empty when they name none."""
    providedBy: list[RowSummary]


class Match(TypedDict):
    """One row :func:`find` returns."""

    row: RowSummary
    exact: bool
    """True when the whole query is the row's name or one of its aliases."""
    matched: list[str]
    """The query words found in the row."""
    capability: NotRequired[Capability]


class FindResult(TypedDict):
    """What ``find`` prints."""

    query: list[str]
    total: int
    """How many rows matched before the limit was applied."""
    matches: list[Match]


class NodeView(TypedDict):
    """What ``node`` prints: one row, and the links that point at it by their reverse names."""

    node: Node
    reverse: dict[str, list[NodeId]]


class Closure(TypedDict):
    """Everything a PRD reaches through its links."""

    features: list[RowSummary]
    supportingFeatures: list[RowSummary]
    elements: list[RowSummary]
    services: list[RowSummary]
    stacks: list[RowSummary]
    repositories: list[RowSummary]
    documents: list[RowSummary]
    facts: list[RowSummary]


class PrdView(TypedDict):
    """What ``prd`` prints."""

    prd: Node
    coverage: Coverage
    features: list[RowSummary]
    """The features the PRD needs, each with its approval state."""
    fullyApproved: bool
    """True when the PRD's coverage is approved, and every row it reaches or its Epic recorded is approved."""
    notApproved: list[NodeId]
    closure: NotRequired[Closure]


class UsesResult(TypedDict):
    """What ``uses`` prints."""

    elements: list[NodeId]
    capabilities: list[Capability]


class MatrixSummary(TypedDict):
    """What ``summary`` prints: the counts by kind and by marker."""

    rows: int
    byKind: dict[str, int]
    approvalByKind: dict[str, dict[str, int]]
    codeByKind: dict[str, dict[str, int]]
    coverage: dict[str, int]
    resourceTypes: int
    documentsSyncedAt: DocumentsSyncedAt


def _add_placement(node: Node, row: RowSummary) -> None:
    """Copy where a row lives, and what it is made of, into its summary."""
    repository: str | None = node.get("repository")
    stack: str | None = node.get("stack")
    resource_type: str | None = node.get("resourceType")
    if repository is not None:
        row["repository"] = repository
    if stack is not None:
        row["stack"] = stack
    if resource_type is not None:
        row["resourceType"] = resource_type
    if "shared" in node:
        row["shared"] = node["shared"]
    if "path" in node:
        row["path"] = node["path"]


def _add_markers(node: Node, row: RowSummary) -> None:
    """Copy a row's approval, code, lifecycle and coverage markers into its summary."""
    if "approval" in node:
        row["approval"] = node["approval"]["state"]
    if "code" in node:
        row["code"] = node["code"]["state"]
    if "lifecycle" in node:
        row["lifecycle"] = node["lifecycle"]
    if "coverage" in node:
        row["coverage"] = node["coverage"]


def _summary(node: Node) -> RowSummary:
    """Reduce a row to its summary.

    Returns:
        The row's identity, placement and markers; a field the row lacks is left out.

    """
    row: RowSummary = {"id": node["id"], "kind": node["kind"], "name": node["name"]}
    _add_markers(node, row)
    _add_placement(node, row)
    if "purpose" in node:
        row["purpose"] = node["purpose"]
    if "featureType" in node:
        row["featureType"] = node["featureType"]
    if "bead" in node:
        row["bead"] = node["bead"]
    if "home" in node:
        row["home"] = node["home"]
    return row


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def words(text: str) -> list[str]:
    """Split text into the words rows are matched by.

    Args:
        text: Any text: a query, a name, a sentence.

    Returns:
        The lower-case runs of letters and digits at least two characters long, with a camelCase
        name split at each capital, in order and without repeats.

    """
    spaced: str = _CAMEL.sub(" ", text)
    return list(dict.fromkeys(word for word in _WORD.findall(spaced.lower()) if len(word) >= MIN_TOKEN))


def _provides_text(node: Node) -> list[str]:
    """Collect the text of what a row provides.

    Returns:
        The behaviour, the consumer rule and the interface name of each ``provides`` entry.

    """
    texts: list[str] = []
    entry: Provides
    for entry in node.get("provides", []):
        texts.extend([entry["behaviour"], entry["consumersMust"], entry["interface"]["name"]])
    return texts


def _searched_text(node: Node, *, capability_only: bool) -> list[str]:
    """Collect the text of a row that a query is matched against.

    Returns:
        The row's name, aliases, purpose and ``provides`` text; and, unless only capabilities are
        asked about, its subject, its statement, its requirements and its heading titles.

    """
    texts: list[str] = [node["name"], *node.get("aliases", []), node.get("purpose", ""), *_provides_text(node)]
    if not capability_only:
        texts.extend([node.get("subject") or "", node.get("statement", ""), *node.get("requirements", [])])
        texts.extend(node.get("headings", {}))
    return texts


def _capability(matrix: Matrix, node: Node, relied_on: Sequence[str]) -> Capability:
    """Describe one supporting feature for a consumer.

    Returns:
        The feature, what it provides, the entries relied on and the rows that provide it.

    """
    providers: list[RowSummary] = [
        _summary(matrix["nodes"][link["to"]])
        for link in node["links"]
        if link["type"] == LINK_PROVIDED_BY and link["to"] in matrix["nodes"]
    ]
    return {
        "feature": _summary(node),
        "provides": list(node.get("provides", [])),
        "reliedOn": sorted(set(relied_on)),
        "providedBy": providers,
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def find(
    matrix: Matrix,
    text: str,
    *,
    provides: str = "",
    kinds: Sequence[Kind] = KINDS,
    limit: int = DEFAULT_LIMIT,
) -> FindResult:
    """Find the rows that match some words, by exact and by word match.

    A row matches exactly when the whole query is its name or one of its aliases. Otherwise it
    matches when it holds at least one word of the query in its name, aliases, purpose, subject,
    statement, requirements, heading titles or ``provides`` text. With ``provides``, only
    supporting features are searched, by their name, aliases, purpose and ``provides`` text, and
    each comes back with what it provides and the rows that provide it.

    Args:
        matrix: The matrix.
        text: The words to look for; may be empty when ``provides`` is given.
        provides: A behaviour to look for among the shared capabilities.
        kinds: The kinds of row to search.
        limit: The most rows to return; 0 returns all.

    Returns:
        The matching rows: exact matches first, then by the number of query words found, then by id.

    Raises:
        ValueError: Neither ``text`` nor ``provides`` holds a word, or ``limit`` is negative.

    """
    message: str
    if limit < 0:
        message = "the limit of a find must not be negative"
        raise ValueError(message)
    capability_only: bool = bool(provides.strip())
    query: list[str] = words(f"{text} {provides}")
    if not query:
        message = "a find needs at least one word to look for"
        raise ValueError(message)
    whole: str = name_key(provides if capability_only else text)
    matches: list[Match] = []
    node: Node
    for node in matrix["nodes"].values():
        if node["kind"] not in kinds:
            continue
        if capability_only and (node["kind"] != KIND_FEATURE or node.get("featureType") != FEATURE_SUPPORTING):
            continue
        held: set[str] = set(words(" ".join(_searched_text(node, capability_only=capability_only))))
        exact: bool = whole in {name_key(node["name"]), *(name_key(alias) for alias in node.get("aliases", []))}
        matched: list[str] = [word for word in query if word in held]
        if not exact and not matched:
            continue
        match: Match = {"row": _summary(node), "exact": exact, "matched": matched}
        if capability_only:
            match["capability"] = _capability(matrix, node, [])
        matches.append(match)
    matches.sort(key=lambda found: (not found["exact"], -len(found["matched"]), found["row"]["id"]))
    return {"query": query, "total": len(matches), "matches": matches[:limit] if limit else matches}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def resolve(matrix: Matrix, reference: str) -> NodeId:
    """Find the one row a caller means by an id, a former id or a name.

    Args:
        matrix: The matrix.
        reference: A row id; or a name or alias, which includes the id a carried row had in the
            element matrix.

    Returns:
        The row's id.

    Raises:
        MatrixRefusedError: No row answers to the reference, or more than one does.

    """
    key: NodeId
    for key in matrix["nodes"]:
        if key == reference:
            return key
    candidates: list[NodeId] = name_index(matrix, KINDS).get(name_key(reference), [])
    message: str
    if not candidates:
        message = f"no row has the id, name or alias {reference!r}"
        raise MatrixRefusedError(message)
    if len(candidates) > 1:
        message = f"{reference!r} names more than one row: {', '.join(candidates)}"
        raise MatrixRefusedError(message)
    return candidates[0]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def node_view(matrix: Matrix, node_id: NodeId) -> NodeView:
    """Return one row with the links that point at it.

    Args:
        matrix: The matrix.
        node_id: The row's id.

    Returns:
        The row, and for each link type that points at it the ids of the rows the links start
        from, under the link type's reverse name (``usedBy`` for ``uses``, and so on).

    Raises:
        MatrixRefusedError: The matrix has no such row.

    """
    if node_id not in matrix["nodes"]:
        message: str = f"there is no row {node_id}"
        raise MatrixRefusedError(message)
    reverse: dict[str, list[NodeId]] = {}
    key: NodeId
    for key in sorted(matrix["nodes"]):
        link: Link
        for link in matrix["nodes"][key]["links"]:
            if link["to"] == node_id:
                reverse.setdefault(LINK_RULES[link["type"]].reverse, []).append(key)
    return {"node": matrix["nodes"][node_id], "reverse": reverse}


def _owners(matrix: Matrix, node: Node) -> list[NodeId]:
    """Name the repository and stack rows a placed row lives in.

    Returns:
        The ids of the row's repository and stack, where the matrix has them.

    """
    repository: str | None = node.get("repository")
    if node["kind"] not in PLACED_KINDS or repository is None:
        return []
    owners: list[NodeId] = [make_id(KIND_REPOSITORY, repository)]
    stack: str | None = node.get("stack")
    if stack is not None and node["kind"] != KIND_STACK:
        owners.append(make_id(KIND_STACK, repository, stack))
    return [owner for owner in owners if owner in matrix["nodes"]]


def _reached(matrix: Matrix, start: Sequence[NodeId]) -> list[NodeId]:
    """Walk from some rows to everything they reach.

    Returns:
        The ids reached, in the order found: through the closure link types from any row, through
        ``contains`` from a service, and from a placed row to its repository and stack.

    """
    seen: dict[NodeId, None] = dict.fromkeys(key for key in start if key in matrix["nodes"])
    queue: list[NodeId] = list(seen)
    while queue:
        node: Node = matrix["nodes"][queue.pop(0)]
        followed: list[NodeId] = [
            link["to"]
            for link in node["links"]
            if link["type"] in CLOSURE_LINKS or (link["type"] == LINK_CONTAINS and node["kind"] == KIND_SERVICE)
        ]
        target: NodeId
        for target in [*followed, *_owners(matrix, node)]:
            if target in matrix["nodes"] and target not in seen:
                seen[target] = None
                queue.append(target)
    return list(seen)


def _facts_at(matrix: Matrix, reached: Sequence[NodeId]) -> list[NodeId]:
    """Find the facts whose home is a heading a reached row is described by.

    Returns:
        The ids of those facts, in id order.

    """
    anchors: set[tuple[str, str]] = {
        (link["to"], link.get("heading", ""))
        for key in reached
        for link in matrix["nodes"][key]["links"]
        if link["type"] == LINK_DESCRIBED_BY
    }
    return sorted(
        node["id"]
        for node in matrix["nodes"].values()
        if node["kind"] == KIND_FACT
        and "home" in node
        and (make_id(KIND_DOCUMENT, node["home"]["document"]), node["home"]["heading"]) in anchors
    )


def _closure(matrix: Matrix, reached: Sequence[NodeId]) -> Closure:
    """Sort the rows a PRD reaches by what they are.

    Returns:
        The reached rows as summaries, grouped by kind.

    """
    closure: Closure = {
        "features": [],
        "supportingFeatures": [],
        "elements": [],
        "services": [],
        "stacks": [],
        "repositories": [],
        "documents": [],
        "facts": [],
    }
    key: NodeId
    for key in reached:
        node: Node = matrix["nodes"][key]
        if node["kind"] == KIND_FEATURE:
            supporting: bool = node.get("featureType") == FEATURE_SUPPORTING
            closure["supportingFeatures" if supporting else "features"].append(_summary(node))
        elif node["kind"] == KIND_SERVICE:
            closure["services"].append(_summary(node))
        elif node["kind"] == KIND_STACK:
            closure["stacks"].append(_summary(node))
        elif node["kind"] == KIND_REPOSITORY:
            closure["repositories"].append(_summary(node))
        elif node["kind"] == KIND_DOCUMENT:
            closure["documents"].append(_summary(node))
        elif node["kind"] == KIND_FACT:
            closure["facts"].append(_summary(node))
        elif node["kind"] in CODED_KINDS:
            closure["elements"].append(_summary(node))
    return closure


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def reached_from(matrix: Matrix, start: NodeId) -> list[NodeId]:
    """List everything one row reaches through its links.

    Args:
        matrix: The matrix.
        start: The row to start from; a PRD row gives what its Epic involves.

    Returns:
        The ids reached, without the row itself: features, the capabilities they use to any
        depth, the elements that realize and provide them with their stacks and repositories,
        the documents that describe them, and the facts whose home is a heading that describes
        one of them. Empty when the matrix has no such row.

    """
    reached: list[NodeId] = [found for found in _reached(matrix, [start]) if found != start]
    known: list[NodeId] = [key for key in (start, *reached) if key in matrix["nodes"]]
    reached.extend(fact for fact in _facts_at(matrix, known) if fact not in reached)
    return reached


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def prd_view(matrix: Matrix, bead: str, *, closure: bool = False) -> PrdView:
    """Return what the matrix holds for one Epic's PRD.

    Args:
        matrix: The matrix.
        bead: The Epic id.
        closure: Whether to include every feature, supporting feature, element, service, stack,
            repository, document and fact the PRD reaches, each with its markers.

    Returns:
        The PRD row, its coverage, the features it needs, and whether everything it reaches is
        approved, with the ids of the rows that are not.

    Raises:
        MatrixRefusedError: The matrix has no PRD row for the Epic.

    """
    key: NodeId = make_id(KIND_PRD, bead)
    if key not in matrix["nodes"]:
        message: str = f"the matrix has no PRD row for {bead}; sync-prds writes it"
        raise MatrixRefusedError(message)
    prd: Node = matrix["nodes"][key]
    needed: list[NodeId] = [link["to"] for link in prd["links"] if link["type"] == LINK_NEEDS]
    reached: list[NodeId] = reached_from(matrix, key)
    pending: list[NodeId] = [
        found
        for found in reached
        if "approval" in matrix["nodes"][found] and matrix["nodes"][found]["approval"]["state"] != APPROVAL_APPROVED
    ]
    pending.extend(
        found for found in sorted(matrix["nodes"]) if found not in pending and owner_of(matrix["nodes"][found]) == bead
    )
    coverage: Coverage = prd.get("coverage", COVERAGE_APPROVED)
    view: PrdView = {
        "prd": prd,
        "coverage": coverage,
        "features": [_summary(matrix["nodes"][found]) for found in needed if found in matrix["nodes"]],
        "fullyApproved": coverage == COVERAGE_APPROVED and bool(needed) and not pending,
        "notApproved": pending,
    }
    if closure:
        view["closure"] = _closure(matrix, reached)
    return view


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def elements_of_repository(matrix: Matrix, repository: str) -> list[NodeId]:
    """List the rows that live in one repository.

    Args:
        matrix: The matrix.
        repository: The repository's name.

    Returns:
        The ids of the repository's stack, component, library, layer and infrastructure rows, in
        id order.

    Raises:
        MatrixRefusedError: The matrix has no such repository.

    """
    if make_id(KIND_REPOSITORY, repository) not in matrix["nodes"]:
        message: str = f"the matrix has no repository {repository!r}"
        raise MatrixRefusedError(message)
    wanted: str = name_key(repository)
    return sorted(
        node["id"]
        for node in matrix["nodes"].values()
        if node["kind"] in PLACED_KINDS and name_key(node.get("repository") or "") == wanted
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def uses_view(matrix: Matrix, elements: Sequence[NodeId]) -> UsesResult:
    """Return the shared capabilities some elements must use.

    A capability applies to an element when the element has a ``uses`` link to it, or when a
    feature the element realizes uses it, directly or through other features.

    Args:
        matrix: The matrix.
        elements: The ids of the elements asked about.

    Returns:
        Each supporting feature that applies, with what it provides, the ``provides`` entries the
        links name, and the rows that provide it with their repository, stack and code marker.

    Raises:
        MatrixRefusedError: An id names no row.

    """
    unknown: list[NodeId] = [key for key in elements if key not in matrix["nodes"]]
    if unknown:
        message: str = f"no row has the id {', '.join(unknown)}"
        raise MatrixRefusedError(message)
    asked: set[NodeId] = set(elements)
    queue: list[NodeId] = [
        *elements,
        *(
            node["id"]
            for node in matrix["nodes"].values()
            if node["kind"] == KIND_FEATURE
            and any(link["type"] == LINK_REALIZED_BY and link["to"] in asked for link in node["links"])
        ),
    ]
    relied: dict[NodeId, list[str]] = {}
    walked: set[NodeId] = set()
    while queue:
        key: NodeId = queue.pop(0)
        if key in walked:
            continue
        walked.add(key)
        link: Link
        for link in matrix["nodes"][key]["links"]:
            if link["type"] == LINK_USES and link["to"] in matrix["nodes"]:
                relied.setdefault(link["to"], []).extend(link.get("provides", []))
                queue.append(link["to"])
    capabilities: list[Capability] = [
        _capability(matrix, matrix["nodes"][key], relied[key])
        for key in sorted(relied)
        if matrix["nodes"][key].get("featureType") == FEATURE_SUPPORTING
    ]
    return {"elements": list(elements), "capabilities": capabilities}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def disagreements_for(matrix: Matrix, document: str) -> list[Node]:
    """Return the recorded disagreements that quote a document, with their settlements.

    Args:
        matrix: The matrix.
        document: The document's path relative to the vault root.

    Returns:
        The disagreement rows with a statement in that document, in id order.

    Raises:
        ValueError: ``document`` is empty.

    """
    if not document.strip():
        message: str = "a document path is needed to look up its disagreements"
        raise ValueError(message)
    return [
        matrix["nodes"][key]
        for key in sorted(matrix["nodes"])
        if matrix["nodes"][key]["kind"] == KIND_DISAGREEMENT
        and any(statement["document"] == document for statement in matrix["nodes"][key].get("statements", []))
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def summarize(matrix: Matrix) -> MatrixSummary:
    """Count the rows of the matrix by kind and by marker.

    Args:
        matrix: The matrix.

    Returns:
        The number of rows of each kind; for each kind the number in each approval state and each
        code state; and the number of PRDs at each coverage.

    """
    summary: MatrixSummary = {
        "rows": len(matrix["nodes"]),
        "byKind": {},
        "approvalByKind": {},
        "codeByKind": {},
        "coverage": {},
        "resourceTypes": len(matrix["resourceTypes"]),
        "documentsSyncedAt": matrix["documentsSyncedAt"],
    }
    node: Node
    for node in matrix["nodes"].values():
        kind: str = node["kind"]
        summary["byKind"][kind] = summary["byKind"].get(kind, 0) + 1
        if "approval" in node:
            states: dict[str, int] = summary["approvalByKind"].setdefault(kind, {})
            states[node["approval"]["state"]] = states.get(node["approval"]["state"], 0) + 1
        if "code" in node:
            codes: dict[str, int] = summary["codeByKind"].setdefault(kind, {})
            codes[node["code"]["state"]] = codes.get(node["code"]["state"], 0) + 1
        if "coverage" in node:
            summary["coverage"][node["coverage"]] = summary["coverage"].get(node["coverage"], 0) + 1
    return summary
