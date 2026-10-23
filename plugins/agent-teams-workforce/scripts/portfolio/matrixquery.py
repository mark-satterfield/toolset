"""The questions the matrix answers without anyone reading a document.

Every function here reads a matrix that is already loaded and changes nothing. Each is one
``atw-matrix`` read and returns the one JSON object the command prints:

- :func:`epic_view` (``epic``): an Epic's PRD, its requirements with the features that serve them
  and the documents that cover them, and on request the constraints that bind the Epic, its
  features and their realizers, its closure and its links with nothing recorded at the other end.
- :func:`realizers_view` (``epic --realizers``): what realizes each feature of an Epic, and the
  stack and repository of each realizer.
- :func:`find` (``find``): the entries that share words with some text, ranked.
- :func:`node_view` (``node``): one entry with its relationships from both ends.
- :func:`deps_view` (``deps``): what an entry depends on, or what depends on it, to any depth.
- :func:`stacks_view` (``stacks``), :func:`layers_view` (``layers``).
- :func:`impact_view` (``impact``): what a change to an entry reaches.
- :func:`related_view` (``related``): the Epics that reach what an Epic reaches.
- :func:`uses_view` (``uses``), :func:`story_scope` (``story-scope``).
- :func:`summarize` (``summary``): the counts by kind and by side, and on request the
  repository-side entries with no architecture-side counterpart.
- :func:`approval_view` (``approval``): the matrix content an Epic reaches, split into what
  carries the approved flag and what does not.

A read follows the relationships of both sides, so a result shows what the architecture states and
what is in a repository today. Each entry and relationship returned carries its kind, the side it
came from and, where set, its approved flag and its verified flag. The walks are in
``matrixtraverse``.
"""

import sys
from collections import deque
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    AUTHORITY_SIDE,
    ENTRY_KINDS,
    KIND_COMPONENT,
    KIND_DOCUMENT,
    KIND_EPIC,
    KIND_EVENT,
    KIND_FEATURE,
    KIND_FILE,
    KIND_INFRASTRUCTURE,
    KIND_LAYER,
    KIND_SERVICE,
    KIND_STACK,
    REL_CONTAINS,
    REL_CORRESPONDS_TO,
    REL_COVERS,
    REL_DESCRIBED_BY,
    REL_HAS_REQUIREMENT,
    REL_PART_OF,
    REL_READS,
    REL_REALIZED_BY,
    REL_SERVED_BY,
    REL_USES_LAYER,
    SIDE_REPOSITORY,
    Entry,
    EntryId,
    EntryKind,
    JsonValue,
    MatrixError,
    Relationship,
    RelationshipKind,
    Side,
    definition_problems,
    entry_json,
    relationship_json,
    relationship_rule,
)
from matrixstore import Matrix, approved_by, name_key
from matrixtraverse import (
    ATTR_APP,
    ATTR_EXECUTION_USE,
    ATTR_HEADING,
    ATTR_PROVIDES,
    ATTR_REPOSITORY,
    ATTR_RESOURCE_TYPE,
    ATTR_SELECTOR,
    ApprovalScope,
    CapabilityReach,
    ConstraintReach,
    Dependency,
    EpicReach,
    Impact,
    Touch,
    Way,
    approval_scope,
    authority_holder,
    capabilities,
    constraints_for,
    dependencies,
    epic_id,
    epic_reach,
    epic_touches,
    held,
    holder,
    holding,
    impact,
    stack_type,
    words,
)

DEFAULT_LIMIT: Final = 10
"""The most entries :func:`find` returns unless the caller asks for another number; 0 asks for all."""
ATTR_LIFECYCLE: Final = "lifecycle"
ATTR_STATEMENT: Final = "statement"
RULE_ATTRIBUTES: Final[tuple[str, ...]] = (ATTR_STATEMENT, "trd", ATTR_SELECTOR)
"""The attributes a constraint keeps when a read returns it as binding some entries."""
ATTR_PRD: Final = "prd"
ATTR_PRD_PATH: Final = "path"
ATTR_VIA: Final = "via"
BRIEF_ATTRIBUTES: Final[tuple[str, ...]] = (
    ATTR_LIFECYCLE,
    ATTR_REPOSITORY,
    ATTR_APP,
    ATTR_EXECUTION_USE,
    ATTR_RESOURCE_TYPE,
)
"""The attributes an entry keeps when it is returned as the end of a relationship."""
SEARCHED_ATTRIBUTES: Final[tuple[str, ...]] = (ATTR_STATEMENT, "subject", "group", "headings")
"""The attributes whose text :func:`find` matches beside the name, the aliases and the purpose."""
PROVIDES_SEARCHED: Final = "behaviour"
"""The member of each ``provides`` item whose text :func:`find` matches."""
REALIZER_KINDS: Final[frozenset[EntryKind]] = frozenset({
    KIND_SERVICE,
    KIND_COMPONENT,
    KIND_INFRASTRUCTURE,
    KIND_EVENT,
    KIND_LAYER,
})
"""The kinds of entry an arc42 heading that covers an Epic's requirement names as realizing a feature."""
FOUND_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_COMPONENT, KIND_INFRASTRUCTURE, KIND_LAYER, KIND_STACK})
"""The kinds of entry read from a repository that an architecture-side entry corresponds to."""
RESOURCE_SSM_PARAMETER: Final = "ssm-parameter"
"""The resource type of an SSM parameter: its home is the stack that writes it, and ``reads`` joins each reader."""
DOCUMENT_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_DOCUMENT, KIND_FILE})
"""The kinds of entry that are documents: an architecture or design document in the vault, or a file in a repository."""
LINK_OUT: Final = "out"
LINK_IN: Final = "in"
LINK_BOTH: Final = "both"
LINK_DIRECTIONS: Final[tuple[str, ...]] = (LINK_OUT, LINK_IN, LINK_BOTH)
"""Which ends :func:`links_view` follows from each entry it reaches."""
DIRECTION_OF: Final = "of"
DIRECTION_ON: Final = "on"

type View = dict[str, JsonValue]
"""One entry or one relationship as the command prints it, with its kind and its side."""


class Related(TypedDict):
    """One relationship, with the entry at its other end."""

    relationship: View
    entry: View


class Covered(TypedDict):
    """One document heading that covers a requirement."""

    document: EntryId
    heading: str
    via: str
    """The id of the feature that connects the document and the requirement."""
    lifecycle: str
    side: Side


class RequirementView(TypedDict):
    """One requirement of an Epic."""

    requirement: View
    features: list[View]
    """The features that serve it."""
    coveredBy: list[Covered]


class Uncovered(TypedDict):
    """A requirement and a feature that serves it, which no document covers together."""

    requirement: EntryId
    feature: EntryId


class Described(TypedDict):
    """One document heading that describes an entry, or that a constraint is stated in."""

    document: EntryId
    heading: str
    """Empty when the relationship names the document as a whole."""
    lifecycle: str
    side: Side


class Applied(TypedDict):
    """One entry a constraint names with a relationship."""

    entry: EntryId
    side: Side
    """The side that states the constraint applies."""


class BoundConstraint(TypedDict):
    """One constraint that binds some entries, with the entries it names by a relationship."""

    constraint: View
    """The constraint's id, kind, name, side, statement or TRD pointer (``trd``), and selector where set."""
    statedIn: list[Described]
    appliesTo: list[Applied]
    """The entries asked about that the constraint names with a relationship."""


class ConstraintView(BoundConstraint):
    """One constraint that binds some entries."""

    selected: list[EntryId]
    """The entries asked about that the constraint's selector names."""


class Selection(TypedDict):
    """The entries one selector names among those asked about, and the constraints that state it."""

    selector: dict[str, JsonValue]
    selected: list[EntryId]
    constraints: list[EntryId]


class DependencyView(TypedDict):
    """One dependency relationship."""

    relationship: View
    depth: int
    entry: View
    """The far end: what is depended on, or what depends."""
    stack: EntryId | None
    """The stack that holds the far end."""


class FeatureReach(TypedDict):
    """One feature an Epic reaches."""

    feature: View
    supporting: bool
    """True when the feature is reached only because another feature is supported by it."""
    describedBy: list[Described]


class ReachedBy(TypedDict):
    """One way an Epic reaches an entry from one of its features."""

    feature: EntryId
    through: str
    """``realizedBy``, or ``describedBy`` when a document that describes the feature describes the entry."""
    document: EntryId | None
    """The document that describes both; None for an entry that realizes the feature."""
    side: Side
    """The side that states the relationship to the entry."""


class EntryReach(TypedDict):
    """One entry an Epic reaches from its features."""

    entry: View
    reachedBy: list[ReachedBy]
    correspondsTo: list[Related]
    """What is in a repository today for the entry; empty when nothing is recorded."""


class StackReach(TypedDict):
    """One stack an Epic reaches."""

    stack: View
    features: list[EntryId]
    """The features that lead to the stack."""
    dependencyOf: list[EntryId]
    """The stacks and entries of the Epic that depend on it; empty when no dependency reaches it."""


class RepositoryReach(TypedDict):
    """One repository an Epic reaches, with its stacks."""

    repository: str
    """The repository's name; empty for the stacks that name none."""
    stacks: list[StackReach]


class ClosureView(TypedDict):
    """Everything an Epic reaches."""

    features: list[FeatureReach]
    entries: list[EntryReach]
    repositories: list[RepositoryReach]
    dependencies: list[DependencyView]


class EpicView(TypedDict):
    """What ``epic`` prints."""

    epic: View
    prd: str
    """The PRD's path in the vault."""
    requirements: list[RequirementView]
    noFeature: list[EntryId]
    """The requirements no feature serves."""
    noDocument: list[Uncovered]
    constraints: NotRequired[list[BoundConstraint]]
    """Each constraint that binds the Epic, its features or the entries that realize them."""
    selections: NotRequired[list[Selection]]
    """Each selector those constraints state, once, with the entries it selects: a selector such
    as ``{"stackType": "service"}`` names the same entries for every constraint that states it."""
    noSource: NotRequired[list[EntryId]]
    """The constraints that name no document they are stated in."""
    closure: NotRequired[ClosureView]
    noStack: NotRequired[list[EntryId]]
    """The architecture-side entries reached that have no home in code."""
    noRepository: NotRequired[list[EntryId]]
    """The stacks reached that name no repository."""
    noCounterpart: NotRequired[list[EntryId]]
    """The architecture-side entries reached that nothing in a repository is recorded as corresponding to."""


class RealizerView(TypedDict):
    """One entry that realizes a feature of an Epic, with where the architecture side places it."""

    id: EntryId
    stack: EntryId | None
    """The stack the architecture side places it in (for an event, its publisher's stack)."""
    repository: str | None
    """The repository of that stack; None while the stack names none."""
    resourceType: NotRequired[str]
    """The entry's AWS resource type, as the matrix holds it; absent when the entry has none."""
    publishers: NotRequired[list[EntryId]]
    """For an event: the services and components the architecture side says publish it."""


class FeatureRealizers(TypedDict):
    """One feature of an Epic with the ids of what realizes it."""

    feature: EntryId
    supporting: bool
    """True when the feature is reached only because another feature is supported by it."""
    realizedBy: list[EntryId]
    """The ends of its ``realizedBy`` relationships, then each realizing entry an arc42 heading
    describes that covers one of the Epic's requirements by way of the feature."""


class RealizersView(TypedDict):
    """What ``epic --realizers`` adds: what realizes each feature, and where each realizer is placed."""

    features: list[FeatureRealizers]
    entries: list[RealizerView]
    """Each realizer once, with its stack and repository."""
    noStack: list[EntryId]
    """The realizers the architecture side places in no stack."""


class Match(TypedDict):
    """One entry :func:`find` returns."""

    entry: View
    exact: bool
    """True when the whole text is the entry's name or one of its aliases, or its PRD is the one asked for."""
    matched: list[str]
    """The words of the text found in the entry."""
    epics: NotRequired[list[EntryId]]
    """For a feature: the Epics whose requirements it serves."""


class FindResult(TypedDict):
    """What ``find`` prints."""

    query: list[str]
    total: int
    """How many entries matched before the limit was applied."""
    matches: list[Match]


class NodeView(TypedDict):
    """What ``node`` prints."""

    entry: View
    relationships: dict[str, list[Related]]
    """The relationships that start at the entry by kind, and those that end at it by reverse name."""


class DepsView(TypedDict):
    """What ``deps`` prints."""

    id: EntryId
    direction: str
    """``of``: what the entry depends on. ``on``: what depends on the entry."""
    dependencies: list[DependencyView]
    stacks: list[EntryId]
    """The stacks that hold the far ends, in id order."""


class StackView(TypedDict):
    """One stack with what it holds."""

    stack: View
    holds: list[Related]
    """Each home relationship that ends at the stack, with the entry it starts from."""
    matching: NotRequired[list[EntryId]]
    """With a resource type asked for: the entries the stack holds that have it."""


class StacksView(TypedDict):
    """What ``stacks`` prints."""

    stacks: list[StackView]


class LayerView(TypedDict):
    """One layer with what it carries and what attaches it."""

    layer: View
    packages: list[Related]
    usedBy: list[Related]


class LayersView(TypedDict):
    """What ``layers`` prints."""

    layers: list[LayerView]


class RequirementReach(TypedDict):
    """One requirement a change reaches."""

    requirement: View
    feature: EntryId
    epic: EntryId
    prd: str


class ImpactView(TypedDict):
    """What ``impact`` prints."""

    id: EntryId
    holds: list[Related]
    """For a stack: the entries it holds, which the change is also followed from."""
    describes: list[Related]
    """For a document: the entries it describes."""
    realizes: list[Related]
    """The features the entry, an entry it holds or an entry it describes realizes."""
    supports: list[Related]
    """The features that rely on a feature reached, to any depth."""
    features: list[EntryId]
    """Every feature reached."""
    constrainedBy: list[Related]
    supportsEpic: list[Related]
    """The Epics that rest on what the change reaches."""
    dependents: list[DependencyView]
    requirements: list[RequirementReach]
    epics: list[EntryId]
    ids: list[EntryId]
    """The id of every entry above, without repeats."""


class TouchView(TypedDict):
    """One way an Epic reaches an entry."""

    through: str
    heading: str


class Shared(TypedDict):
    """One entry two Epics both reach."""

    entry: View
    this: list[TouchView]
    other: list[TouchView]


class RelatedEpic(TypedDict):
    """One Epic that reaches what the Epic asked about reaches."""

    epic: View
    shared: list[Shared]


class RelatedView(TypedDict):
    """What ``related`` prints."""

    epic: EntryId
    related: list[RelatedEpic]


class Provider(TypedDict):
    """One entry that provides a shared capability."""

    relationship: View
    entry: View
    stack: View | None


class Capability(TypedDict):
    """One shared capability."""

    feature: View
    relies: list[str]
    """The ids of the ``provides`` items relied on; empty when the relationships name none."""
    providers: list[Provider]


class UsesResult(TypedDict):
    """What ``uses`` prints."""

    ids: list[EntryId]
    capabilities: list[Capability]


class ScopedEntry(TypedDict):
    """One entry a Story builds, with the documents that describe it."""

    entry: View
    documents: list[Described]


class StoryScope(TypedDict):
    """What ``story-scope`` prints."""

    stack: View
    repository: str
    documents: list[Described]
    """The documents that describe the stack."""
    entries: list[ScopedEntry]
    constraints: list[ConstraintView]
    noSource: list[EntryId]
    capabilities: list[Capability]


class MatrixSummary(TypedDict):
    """What ``summary`` prints."""

    entries: int
    relationships: int
    byKind: dict[str, int]
    bySide: dict[str, int]
    relationshipsByKind: dict[str, int]
    relationshipsBySide: dict[str, int]
    verifiedByKind: dict[str, int]
    verifiedRelationshipsByKind: dict[str, int]
    approvedByKind: dict[str, int]
    """The entries that carry the approved flag, by kind."""
    approvedRelationshipsByKind: dict[str, int]
    """The relationships that carry the approved flag, by kind."""
    documentsByLifecycle: dict[str, int]
    stacksByApp: dict[str, int]
    repositories: list[str]
    """The repositories the stacks name, in name order."""
    noArchitecture: NotRequired[list[EntryId]]
    """The repository-side entries that nothing on the architecture side is recorded as corresponding to."""


class Approval(TypedDict):
    """One entry that carries the approved flag."""

    id: EntryId
    kind: str
    name: str
    approvedBy: str
    """The beads id of the Epic whose architecture and design approval set the flag."""


class ApprovalView(TypedDict):
    """What ``approval`` prints."""

    epic: EntryId
    approved: list[Approval]
    """The entries the Epic reaches that carry the flag."""
    notApproved: list[EntryId]
    """The entries the Epic reaches that do not."""
    relationships: int
    """How many architecture-side relationships join two of the entries the Epic reaches."""
    approvedRelationships: int
    """How many of them carry the flag."""


def _text(value: JsonValue) -> str:
    """Narrow an attribute to text.

    Returns:
        The value when it is a string, otherwise the empty string.

    """
    return value if isinstance(value, str) else ""


def _strings(value: JsonValue) -> list[str]:
    """Narrow an attribute to the strings it holds.

    Returns:
        The value when it is a string, its string items when it is a list, otherwise nothing.

    """
    if isinstance(value, str):
        return [value]
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _prd_path(entry: Entry) -> str:
    """Read the path of an Epic's PRD.

    Returns:
        The path in the vault; empty for an entry that states no PRD.

    """
    prd: JsonValue = entry.attributes.get(ATTR_PRD)
    return _text(prd.get(ATTR_PRD_PATH)) if isinstance(prd, dict) else ""


def _entry_view(entry: Entry) -> View:
    """Render one entry in full.

    Returns:
        The entry as the matrix file holds it, with its side; a stack also carries ``type``, the
        last token of its name.

    """
    view: View = entry_json(entry)
    if entry.kind == KIND_STACK:
        view["type"] = stack_type(entry.name)
    return view


def _brief(matrix: Matrix, entry_id: EntryId) -> View:
    """Render one entry as the end of a relationship.

    Returns:
        The entry's id, kind, name and side, its purpose, approved and verified flags where set,
        the attributes that say where and what it is, a stack's type, and ``stack``: the id of its
        home.

    """
    entry: Entry = matrix.entry(entry_id)
    view: View = {"id": entry.id, "kind": entry.kind, "name": entry.name, "side": entry.side}
    if entry.purpose:
        view["purpose"] = entry.purpose
    view.update({name: entry.attributes[name] for name in BRIEF_ATTRIBUTES if name in entry.attributes})
    if entry.kind == KIND_STACK:
        view["type"] = stack_type(entry.name)
    home: EntryId | None = matrix.home(entry_id, side=None)
    if home is not None:
        view["stack"] = home
    if entry.approved is not None:
        view["approved"] = {"epic": entry.approved.epic}
    if entry.verified is not None:
        view["verified"] = {"commit": entry.verified.commit}
    return view


def _related(matrix: Matrix, relationship: Relationship, far: EntryId) -> Related:
    """Render one relationship with the entry at one of its ends.

    Returns:
        The relationship as the matrix file holds it, with its side, and the entry.

    """
    return {"relationship": relationship_json(relationship), "entry": _brief(matrix, far)}


def _described(matrix: Matrix, relationship: Relationship) -> Described:
    """Render a relationship that ends at a document.

    Returns:
        The document, the heading the relationship names, the document's lifecycle and the side
        that states the relationship.

    """
    return {
        "document": relationship.end,
        "heading": _text(relationship.attributes.get(ATTR_HEADING)),
        "lifecycle": _text(matrix.entry(relationship.end).attributes.get(ATTR_LIFECYCLE)),
        "side": relationship.side,
    }


def _dependency(matrix: Matrix, dependency: Dependency) -> DependencyView:
    """Render one dependency a walk found.

    Returns:
        The relationship with its attributes and side, its depth, the far end and the stack that
        holds it.

    """
    return {
        "relationship": relationship_json(dependency.relationship),
        "depth": dependency.depth,
        "entry": _brief(matrix, dependency.far),
        "stack": dependency.stack,
    }


def _bound_constraint(matrix: Matrix, reach: ConstraintReach) -> BoundConstraint:
    """Render one constraint that binds some entries, without the entries its selector names.

    The constraint carries what a reader applies: its rule (its ``statement``, or for a TRD
    requirement ``trd``, the Epic and requirement id whose heading in the Epic's TRD states it)
    and what selects it. Its purpose and aliases are left out; ``atw-matrix node <constraint id>``
    returns them.

    Returns:
        The constraint's id, kind, name, side, statement or trd, and selector, the documents and headings
        it is stated in, and the entries it names with a relationship.

    """
    entry: Entry = matrix.entry(reach.constraint)
    view: View = {"id": entry.id, "kind": entry.kind, "name": entry.name, "side": entry.side}
    view.update({name: entry.attributes[name] for name in RULE_ATTRIBUTES if name in entry.attributes})
    return {
        "constraint": view,
        "statedIn": [_described(matrix, source) for source in reach.sources],
        "appliesTo": [{"entry": applying.end, "side": applying.side} for applying in reach.applied],
    }


def _constraint(matrix: Matrix, reach: ConstraintReach) -> ConstraintView:
    """Render one constraint that binds some entries.

    Returns:
        :func:`_bound_constraint`, and the entries its selector names.

    """
    bound: BoundConstraint = _bound_constraint(matrix, reach)
    return {
        "constraint": bound["constraint"],
        "statedIn": bound["statedIn"],
        "appliesTo": bound["appliesTo"],
        "selected": list(reach.selected),
    }


def _selections(matrix: Matrix, binding: Sequence[ConstraintReach]) -> list[Selection]:
    """Group the entries the constraints' selectors name by selector.

    Returns:
        Each distinct selector that names at least one entry asked about, in the order first
        stated, with those entries and the constraints that state it.

    """
    grouped: dict[str, Selection] = {}
    reach: ConstraintReach
    for reach in binding:
        selector: JsonValue = matrix.entry(reach.constraint).attributes.get(ATTR_SELECTOR)
        if not reach.selected or not isinstance(selector, dict):
            continue
        key: str = repr(sorted(selector.items()))
        grouped.setdefault(key, {"selector": selector, "selected": list(reach.selected), "constraints": []})
        grouped[key]["constraints"].append(reach.constraint)
    return list(grouped.values())


def _capability(matrix: Matrix, reach: CapabilityReach) -> Capability:
    """Render one shared capability.

    Returns:
        The feature with what it provides, the items relied on, and each provider with its stack.

    """
    return {
        "feature": _entry_view(matrix.entry(reach.feature)),
        "relies": list(reach.relies),
        "providers": [
            {
                "relationship": relationship_json(realizing),
                "entry": _brief(matrix, realizing.end),
                "stack": None if stack is None else _brief(matrix, stack),
            }
            for realizing, stack in reach.providers
        ],
    }


def _requirement(matrix: Matrix, requirement: EntryId, features: Sequence[EntryId]) -> RequirementView:
    """Render one requirement of an Epic.

    Returns:
        The requirement, the features that serve it and the document headings that cover it.

    """
    covered: list[Covered] = [
        {
            "document": covering.start,
            "heading": _text(covering.attributes.get(ATTR_HEADING)),
            "via": _text(covering.attributes.get(ATTR_VIA)),
            "lifecycle": _text(matrix.entry(covering.start).attributes.get(ATTR_LIFECYCLE)),
            "side": covering.side,
        }
        for covering in matrix.incoming(requirement, (REL_COVERS,))
    ]
    return {
        "requirement": _entry_view(matrix.entry(requirement)),
        "features": [_brief(matrix, feature) for feature in features],
        "coveredBy": covered,
    }


def _reached_by(way: Way) -> ReachedBy:
    """Render one way an Epic reaches an entry.

    Returns:
        The feature, the kind of the relationship, the document for an entry reached through
        one, and the side that states the relationship.

    """
    return {
        "feature": way.feature,
        "through": way.relationship.kind,
        "document": way.document,
        "side": way.relationship.side,
    }


def _closure(matrix: Matrix, reach: EpicReach) -> ClosureView:
    """Render everything an Epic reaches.

    Returns:
        The features with the documents that describe each, the entries reached from them with
        what is in a repository for each, the stacks grouped by repository with the features that
        lead to each, and the dependencies of those stacks.

    """
    by_repository: dict[str, list[StackReach]] = {}
    stack: EntryId
    for stack in sorted(reach.stacks):
        entry: Entry = matrix.entry(stack)
        by_repository.setdefault(_text(entry.attributes.get(ATTR_REPOSITORY)), []).append({
            "stack": _entry_view(entry),
            "features": sorted(reach.stacks[stack]),
            "dependencyOf": sorted(reach.dependents.get(stack, frozenset())),
        })
    return {
        "features": [
            {
                "feature": _brief(matrix, feature),
                "supporting": feature in reach.supporting,
                "describedBy": [_described(matrix, describing) for describing in reach.documents[feature]],
            }
            for feature in reach.features
        ],
        "entries": [
            {
                "entry": _brief(matrix, reached),
                "reachedBy": [_reached_by(way) for way in ways],
                "correspondsTo": [
                    _related(matrix, corresponding, corresponding.end)
                    for corresponding in reach.counterparts.get(reached, ())
                ],
            }
            for reached, ways in reach.ways.items()
        ],
        "repositories": [
            {"repository": repository, "stacks": by_repository[repository]} for repository in sorted(by_repository)
        ],
        "dependencies": [_dependency(matrix, dependency) for dependency in reach.dependencies],
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_view(
    matrix: Matrix,
    bead: str,
    *,
    closure: bool = False,
    constraints: bool = False,
    unlinked: bool = False,
) -> EpicView:
    """Return what the matrix holds for one Epic.

    An Epic the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id.
        closure: Whether to include everything the Epic reaches: its features with the documents
            that describe each, the entries reached from them with what is in a repository for
            each, the stacks grouped by repository and their dependencies.
        constraints: Whether to include the constraints that bind the Epic, its features and
            the entries that realize those features (``epic --realizers`` names them), each
            with its statement; ``selections``, each selector they state once with the entries
            it selects; and ``noSource``.
            The entries the closure reaches only through a dependency are not asked about:
            ``atw-matrix impact --id <id>`` names the constraints of one of them
            (``constrainedBy``).
        unlinked: Whether to include every list of links of the Epic with nothing recorded at the
            other end: ``noSource``, ``noStack``, ``noRepository`` and ``noCounterpart`` beside
            ``noFeature`` and ``noDocument``, which are always returned.

    Returns:
        The Epic with its PRD path, each requirement with the features that serve it and the
        document headings that cover it, and the links with nothing recorded at the other end.
        ``noStack``, ``noRepository`` and ``noCounterpart`` are also returned with the closure.

    """
    epic: EntryId = epic_id(bead)
    reach: EpicReach = epic_reach(matrix, epic)
    entry: Entry = matrix.entry(epic)
    view: EpicView = {
        "epic": _entry_view(entry),
        "prd": _prd_path(entry),
        "requirements": [_requirement(matrix, requirement, serving) for requirement, serving in reach.served.items()],
        "noFeature": [requirement for requirement, serving in reach.served.items() if not serving],
        "noDocument": [
            {"requirement": requirement, "feature": feature}
            for requirement, serving in reach.served.items()
            for feature in serving
            if feature
            not in {covering.attributes.get(ATTR_VIA) for covering in matrix.incoming(requirement, (REL_COVERS,))}
        ],
    }
    if constraints or unlinked:
        realizing: dict[EntryId, list[EntryId]] = _realizing(matrix, reach)
        asked: list[EntryId] = [epic, *reach.features, *(entry for found in realizing.values() for entry in found)]
        binding: list[ConstraintReach] = constraints_for(matrix, asked)
        if constraints:
            view["constraints"] = [_bound_constraint(matrix, found) for found in binding]
            view["selections"] = _selections(matrix, binding)
        view["noSource"] = [found.constraint for found in binding if not found.sources]
    if closure:
        view["closure"] = _closure(matrix, reach)
    if closure or unlinked:
        view["noStack"] = list(reach.no_stack)
        view["noRepository"] = list(reach.no_repository)
        view["noCounterpart"] = list(reach.no_counterpart)
    return view


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def realizers_view(matrix: Matrix, bead: str) -> RealizersView:
    """Return what realizes each feature of an Epic: what ``epic --realizers`` adds.

    An Epic the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id.

    Returns:
        Each feature the Epic reaches with the ids of the entries that realize it: the ends of
        its ``realizedBy`` relationships, then each realizing entry an arc42 heading describes
        that covers one of the Epic's requirements by way of the feature; each of those entries
        once with its stack and repository; and those the architecture side places in no stack.
        ``atw-matrix node <id>`` returns an entry's purpose and the documents that describe it.

    """
    reach: EpicReach = epic_reach(matrix, epic_id(bead))
    return _realizers_view(matrix, reach, _realizing(matrix, reach))


def _heading_index(matrix: Matrix) -> dict[tuple[EntryId, str], list[EntryId]]:
    """Index the architecture-side entries of the realizing kinds by the document heading that describes them.

    Returns:
        Each (document, heading) pair with the realizing entries whose architecture-side
        ``describedBy`` names exactly that pair, in file order.

    """
    index: dict[tuple[EntryId, str], list[EntryId]] = {}
    describing: Relationship
    for describing in matrix.relationships((REL_DESCRIBED_BY,)):
        start: Entry | None = matrix.find(describing.start)
        if describing.side != AUTHORITY_SIDE or start is None or start.kind not in REALIZER_KINDS:
            continue
        pair: tuple[EntryId, str] = (describing.end, _text(describing.attributes.get(ATTR_HEADING)))
        index.setdefault(pair, []).append(start.id)
    return index


def _feature_realizers(
    matrix: Matrix,
    reach: EpicReach,
    feature: EntryId,
    by_heading: dict[tuple[EntryId, str], list[EntryId]],
) -> list[EntryId]:
    """Find what realizes one feature of an Epic.

    Returns:
        The ends of the feature's ``realizedBy`` relationships, then every realizing entry an
        arc42 heading describes that covers one of the Epic's requirements by way of the
        feature; in the order found, each once.

    """
    realized: list[EntryId] = [relationship.end for relationship in matrix.outgoing(feature, (REL_REALIZED_BY,))]
    pairs: list[tuple[EntryId, str]] = [
        (covering.start, _text(covering.attributes.get(ATTR_HEADING)))
        for requirement in reach.served
        for covering in matrix.incoming(requirement, (REL_COVERS,))
        if covering.attributes.get(ATTR_VIA) == feature
    ]
    described: list[EntryId] = [entry_id for pair in pairs for entry_id in by_heading.get(pair, [])]
    return list(dict.fromkeys([*realized, *described]))


def _realizer(matrix: Matrix, entry_id: EntryId) -> RealizerView:
    """Render one entry that realizes a feature, with the stack and repository that hold it.

    Returns:
        The entry's id, its architecture-side stack, that stack's repository (None when it
        names none), its AWS resource type when it has one and, for an event, the services and
        components that publish it.

    """
    stack: EntryId | None = authority_holder(matrix, entry_id)
    repository: JsonValue = None if stack is None else matrix.entry(stack).attributes.get(ATTR_REPOSITORY)
    view: RealizerView = {
        "id": entry_id,
        "stack": stack,
        "repository": repository if isinstance(repository, str) and repository else None,
    }
    resource_type: JsonValue = matrix.entry(entry_id).attributes.get(ATTR_RESOURCE_TYPE)
    if isinstance(resource_type, str) and resource_type:
        view["resourceType"] = resource_type
    if matrix.entry(entry_id).kind == KIND_EVENT:
        view["publishers"] = list(matrix.publishers(entry_id))
    return view


def _realizing(matrix: Matrix, reach: EpicReach) -> dict[EntryId, list[EntryId]]:
    """Find what realizes each feature an Epic reaches.

    Returns:
        Each feature, in the order reached, with :func:`_feature_realizers` for it.

    """
    by_heading: dict[tuple[EntryId, str], list[EntryId]] = _heading_index(matrix)
    return {feature: _feature_realizers(matrix, reach, feature, by_heading) for feature in reach.features}


def _realizers_view(matrix: Matrix, reach: EpicReach, realizing: dict[EntryId, list[EntryId]]) -> RealizersView:
    """Render what realizes each feature of an Epic, each realizer once.

    Returns:
        Each feature with the ids of its realizers, each realizer with its stack and repository,
        and the realizers the architecture side places in no stack.

    """
    realizers: list[EntryId] = list(dict.fromkeys(entry_id for found in realizing.values() for entry_id in found))
    return {
        "features": [
            {"feature": feature, "supporting": feature in reach.supporting, "realizedBy": found}
            for feature, found in realizing.items()
        ],
        "entries": [_realizer(matrix, entry_id) for entry_id in realizers],
        "noStack": [entry_id for entry_id in realizers if authority_holder(matrix, entry_id) is None],
    }


def _searched(matrix: Matrix, entry: Entry) -> list[str]:
    """Collect the text of an entry that a query is matched against.

    Returns:
        The entry's name, aliases and purpose; its statement, subject, group and heading texts
        where it has them; the behaviour of each thing a feature provides; and for a stack the
        names and purposes of the entries it holds and of the features those and it realize.

    """
    texts: list[str] = [entry.name, *entry.aliases, entry.purpose]
    name: str
    for name in SEARCHED_ATTRIBUTES:
        texts.extend(_strings(entry.attributes.get(name)))
    provided: JsonValue = entry.attributes.get(ATTR_PROVIDES)
    texts.extend(
        _text(item.get(PROVIDES_SEARCHED))
        for item in (provided if isinstance(provided, list) else [])
        if isinstance(item, dict)
    )
    if entry.kind == KIND_STACK:
        inside: list[EntryId] = held(matrix, entry.id)
        related: dict[EntryId, None] = dict.fromkeys(inside)
        related.update(
            dict.fromkeys(
                realizing.start
                for realized in (entry.id, *inside)
                for realizing in matrix.incoming(realized, (REL_REALIZED_BY,))
            ),
        )
        other: EntryId
        for other in related:
            texts.extend([matrix.entry(other).name, matrix.entry(other).purpose])
    return texts


def _serving_epics(matrix: Matrix, feature: EntryId) -> list[EntryId]:
    """Name the Epics whose requirements a feature serves.

    Returns:
        The ids of those Epics, in id order.

    """
    return sorted({
        stating.start
        for served in matrix.incoming(feature, (REL_SERVED_BY,))
        for stating in matrix.incoming(served.start, (REL_HAS_REQUIREMENT,))
    })


def _match(matrix: Matrix, entry: Entry, query: Sequence[str], whole: str, prd: str | None) -> Match | None:
    """Match one entry against a query.

    Returns:
        The match, or None when the entry is neither named by the whole text, nor the Epic of the
        PRD asked for, nor holds a word of the query.

    """
    if prd is not None and _prd_path(entry) != prd:
        return None
    holds: set[str] = set(words(" ".join(_searched(matrix, entry)))) if query else set()
    exact: bool = prd is not None or (
        bool(whole) and whole in {name_key(entry.name), *(name_key(alias) for alias in entry.aliases)}
    )
    matched: list[str] = [word for word in query if word in holds]
    if not exact and not matched:
        return None
    match: Match = {"entry": _entry_view(entry), "exact": exact, "matched": matched}
    if entry.kind == KIND_FEATURE:
        match["epics"] = _serving_epics(matrix, entry.id)
    return match


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def find(
    matrix: Matrix,
    text: str = "",
    *,
    kinds: Collection[EntryKind] = ENTRY_KINDS,
    prd: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> FindResult:
    """Find the entries that share words with some text, ranked.

    An entry matches exactly when the whole text is its name or one of its aliases. Otherwise it
    matches when it holds at least one word of the text: in its name, aliases and purpose; in its
    statement, subject, group or headings; for a feature, in the behaviour of each thing it
    provides; for a stack, in the names and purposes of the entries it holds and of the features
    those realize. Entries of both sides are searched, and each is returned with its side. A
    matching feature is returned with the Epics whose requirements it serves. With ``prd``, only
    the Epic whose PRD has that path matches. The ranking uses nothing but the matrix, so the
    same text returns the same order; an empty result means no such entry exists.

    Args:
        matrix: The matrix.
        text: The words to look for; may be empty when ``prd`` is given.
        kinds: The kinds of entry to search.
        prd: A PRD's path in the vault.
        limit: The most entries to return; 0 returns all.

    Returns:
        The matching entries: exact matches first, then by the number of words found, then by id.

    Raises:
        ValueError: Neither ``text`` holds a word nor ``prd`` is given, or ``limit`` is negative.

    """
    message: str
    if limit < 0:
        message = "the limit of a find must not be negative"
        raise ValueError(message)
    query: list[str] = words(text)
    if not query and prd is None:
        message = "a find needs at least one word to look for, or the path of a PRD"
        raise ValueError(message)
    whole: str = name_key(text)
    searched: list[EntryKind] = [KIND_EPIC] if prd is not None else list(kinds)
    matches: list[Match] = [
        match for entry in matrix.entries(searched) if (match := _match(matrix, entry, query, whole, prd)) is not None
    ]
    matches.sort(key=lambda found: (not found["exact"], -len(found["matched"]), _text(found["entry"].get("id"))))
    return {"query": query, "total": len(matches), "matches": matches[:limit] if limit else matches}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def node_view(matrix: Matrix, entry_id: EntryId) -> NodeView:
    """Return one entry with its relationships from both ends.

    An entry the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        entry_id: The entry's id.

    Returns:
        The entry (a stack with its ``type``), the relationships that start at it under each
        kind's name and those that end at it under each kind's reverse name, once for each side
        that states one. The entry at the other end of each carries its side, its home
        (``stack``) and, for a document, its lifecycle.

    """
    entry: Entry = matrix.entry(entry_id)
    relationships: dict[str, list[Related]] = {}
    relationship: Relationship
    for relationship in matrix.outgoing(entry_id):
        relationships.setdefault(relationship.kind, []).append(_related(matrix, relationship, relationship.end))
    for relationship in matrix.incoming(entry_id):
        relationships.setdefault(relationship_rule(relationship.kind).reverse, []).append(
            _related(matrix, relationship, relationship.start),
        )
    return {"entry": _entry_view(entry), "relationships": relationships}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def deps_view(matrix: Matrix, entry_id: EntryId, *, inward: bool = False) -> DepsView:
    """Return what an entry depends on, or what depends on it, to any depth.

    A stack stands for itself and every entry it holds. The dependencies of both sides are
    followed, and each is returned with its side. An entry the matrix does not hold raises
    ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        entry_id: The entry's id.
        inward: False (``deps --of``) follows the dependency family outward; True (``deps --on``)
            follows it inward.

    Returns:
        Each dependency relationship with its kind and attributes, the entry at its far end and
        the stack that holds that entry, nearest first; and the stacks reached.

    """
    matrix.entry(entry_id)
    found: list[Dependency] = dependencies(matrix, [entry_id], inward=inward)
    return {
        "id": entry_id,
        "direction": DIRECTION_ON if inward else DIRECTION_OF,
        "dependencies": [_dependency(matrix, dependency) for dependency in found],
        "stacks": sorted({dependency.stack for dependency in found if dependency.stack is not None}),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def stacks_view(
    matrix: Matrix,
    *,
    app: str | None = None,
    repository: str | None = None,
    resource_type: str | None = None,
) -> StacksView:
    """List the stacks, or those of one app, of one repository, or that hold one resource type.

    Args:
        matrix: The matrix.
        app: Keep the stacks whose ``app`` equals this.
        repository: Keep the stacks whose ``repository`` equals this.
        resource_type: Keep the stacks that hold an entry with this resource type; each then
            carries ``matching``, the ids of those entries.

    Returns:
        The stacks that pass every filter given, in id order, each with its ``type`` and what it
        holds on each side.

    Raises:
        MatrixError: ``resource_type`` is not of the form of a resource type (the kinds
            registry's ``resourceType`` definition).

    """
    problems: list[str] = [] if resource_type is None else definition_problems(ATTR_RESOURCE_TYPE, resource_type)
    if problems:
        message: str = f"{resource_type!r} is not a resource type: {'; '.join(problems)}"
        raise MatrixError(message)
    stacks: list[StackView] = []
    stack: Entry
    for stack in matrix.entries((KIND_STACK,)):
        if app is not None and stack.attributes.get(ATTR_APP) != app:
            continue
        if repository is not None and stack.attributes.get(ATTR_REPOSITORY) != repository:
            continue
        view: StackView = {
            "stack": _entry_view(stack),
            "holds": [_related(matrix, homed, homed.start) for homed in holding(matrix, stack.id)],
        }
        if resource_type is not None:
            matching: list[EntryId] = [
                inside
                for inside in held(matrix, stack.id)
                if matrix.entry(inside).attributes.get(ATTR_RESOURCE_TYPE) == resource_type
            ]
            if not matching:
                continue
            view["matching"] = matching
        stacks.append(view)
    return {"stacks": stacks}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def layers_view(matrix: Matrix) -> LayersView:
    """List every layer with the packages it carries and the components that attach it.

    Args:
        matrix: The matrix.

    Returns:
        The layers of both sides in id order, each relationship with the side that states it.

    """
    return {
        "layers": [
            {
                "layer": _brief(matrix, layer.id),
                "packages": [
                    _related(matrix, carried, carried.end) for carried in matrix.outgoing(layer.id, (REL_CONTAINS,))
                ],
                "usedBy": [
                    _related(matrix, using, using.start) for using in matrix.incoming(layer.id, (REL_USES_LAYER,))
                ],
            }
            for layer in matrix.entries((KIND_LAYER,))
        ],
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def impact_view(matrix: Matrix, entry_id: EntryId) -> ImpactView:
    """Return what a change to an entry reaches.

    From the entry, and for a stack from every entry it holds: the entries a document describes;
    the features those and the entry realize, and the features that rely on one of them, to any
    depth; the constraints that apply to any of those; the Epics that rest on any of those; what
    depends on the entry, to any depth; then from every feature reached, the requirements it
    serves and their Epics, each requirement with its PRD. An entry the matrix does not hold
    raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        entry_id: The entry's id.

    Returns:
        What the change reaches, each relationship with its side, and ``ids``: the id of every
        entry reached.

    """
    reached: Impact = impact(matrix, entry_id)
    return {
        "id": entry_id,
        "holds": (
            [_related(matrix, homed, homed.start) for homed in holding(matrix, entry_id)]
            if matrix.entry(entry_id).kind == KIND_STACK
            else []
        ),
        "describes": [_related(matrix, describing, describing.start) for describing in reached.described],
        "realizes": [_related(matrix, realizing, realizing.start) for realizing in reached.realizing],
        "supports": [_related(matrix, supporting, supporting.start) for supporting in reached.supporting],
        "features": list(reached.features),
        "constrainedBy": [_related(matrix, applying, applying.start) for applying in reached.constraining],
        "supportsEpic": [_related(matrix, resting, resting.start) for resting in reached.resting],
        "dependents": [_dependency(matrix, dependency) for dependency in reached.dependents],
        "requirements": [
            {
                "requirement": _brief(matrix, served.requirement),
                "feature": served.feature,
                "epic": served.epic,
                "prd": _prd_path(matrix.entry(served.epic)),
            }
            for served in reached.serving
        ],
        "epics": reached.epics(),
        "ids": reached.ids(),
    }


def _touches(ways: Sequence[Touch]) -> list[TouchView]:
    """Render the ways an Epic reaches an entry.

    Returns:
        Each relationship kind with the heading it names.

    """
    return [{"through": way.through, "heading": way.heading} for way in ways]


def related_view(matrix: Matrix, bead: str) -> RelatedView:
    """Return the Epics that reach what one Epic reaches.

    Two Epics are related when both reach the same feature, document, stack, service, component
    or infrastructure entry: through their closure, through a document that covers one of their
    requirements, or through what they drive and rest on. An Epic the matrix does not hold raises
    ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id.

    Returns:
        Each related Epic in id order, with every shared entry and the relationship kinds, and
        document headings, through which each of the two Epics reaches it.

    """
    epic: EntryId = epic_id(bead)
    walked: dict[EntryId, tuple[Dependency, ...]] = {}
    mine: dict[EntryId, list[Touch]] = epic_touches(matrix, epic, walked)
    related: list[RelatedEpic] = []
    other: Entry
    for other in matrix.entries((KIND_EPIC,)):
        if other.id == epic:
            continue
        theirs: dict[EntryId, list[Touch]] = epic_touches(matrix, other.id, walked)
        shared: list[Shared] = [
            {"entry": _brief(matrix, touched), "this": _touches(mine[touched]), "other": _touches(theirs[touched])}
            for touched in sorted(mine)
            if touched in theirs
        ]
        if shared:
            related.append({"epic": _brief(matrix, other.id), "shared": shared})
    return {"epic": epic, "related": related}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def uses_view(matrix: Matrix, entry_ids: Sequence[EntryId]) -> UsesResult:
    """Return the shared capabilities the work that builds some entries must use.

    The walk is entries → the features they realize → the features those are supported by, to any
    depth → the ones that state what they provide. A shared capability that is itself among the
    ids is returned too. An id the matrix does not hold raises ``MatrixError`` from
    ``Matrix.entry``.

    Args:
        matrix: The matrix.
        entry_ids: The ids of the entries the work builds and of the shared capabilities it states.

    Returns:
        Each capability with what it provides, the ``provides`` items relied on, and each entry
        that realizes it with that entry's stack.

    Raises:
        ValueError: No id is given.

    """
    if not entry_ids:
        message: str = "uses needs the id of at least one entry"
        raise ValueError(message)
    return {
        "ids": list(dict.fromkeys(entry_ids)),
        "capabilities": [_capability(matrix, reach) for reach in capabilities(matrix, entry_ids)],
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_scope(matrix: Matrix, stack: EntryId, entry_ids: Sequence[EntryId]) -> StoryScope:
    """Return in one object what a Story that builds some entries of a stack must be handed.

    An id the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        stack: The id of the stack the Story builds in.
        entry_ids: The ids of the entries the Story builds.

    Returns:
        The stack and its repository, the documents and headings that describe the stack and
        each entry, the constraints that bind the stack or an entry, and the shared capabilities
        the entries must use.

    Raises:
        MatrixError: ``stack`` is not a stack.

    """
    home: Entry = matrix.entry(stack)
    if home.kind != KIND_STACK:
        message: str = f"{stack} is not a stack"
        raise MatrixError(message)
    built: list[EntryId] = list(dict.fromkeys(entry_ids))
    binding: list[ConstraintReach] = constraints_for(matrix, [stack, *(found for found in built if found != stack)])
    return {
        "stack": _entry_view(home),
        "repository": _text(home.attributes.get(ATTR_REPOSITORY)),
        "documents": [_described(matrix, describing) for describing in matrix.outgoing(stack, (REL_DESCRIBED_BY,))],
        "entries": [
            {
                "entry": _entry_view(matrix.entry(found)),
                "documents": [
                    _described(matrix, describing) for describing in matrix.outgoing(found, (REL_DESCRIBED_BY,))
                ],
            }
            for found in built
        ],
        "constraints": [_constraint(matrix, found) for found in binding],
        "noSource": [found.constraint for found in binding if not found.sources],
        "capabilities": [_capability(matrix, reach) for reach in capabilities(matrix, built)] if built else [],
    }


def _count(counts: dict[str, int], key: str) -> None:
    """Add one to the count kept under a key."""
    counts[key] = counts.get(key, 0) + 1


def _no_architecture(matrix: Matrix) -> list[EntryId]:
    """List the repository-side entries with no architecture-side counterpart.

    Returns:
        The id of every repository-side entry of the kinds found in a repository
        (``FOUND_KINDS``) that no ``correspondsTo`` ends at, in id order.

    """
    return sorted(
        entry.id
        for entry in matrix.entries(FOUND_KINDS)
        if entry.side == SIDE_REPOSITORY and not matrix.incoming(entry.id, (REL_CORRESPONDS_TO,))
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def summarize(matrix: Matrix, *, unlinked: bool = False) -> MatrixSummary:
    """Count what the matrix holds.

    Args:
        matrix: The matrix.
        unlinked: Whether to include ``noArchitecture``: the repository-side entries, of the kinds
            ``correspondsTo`` may end at, that nothing on the architecture side is recorded as
            corresponding to. It is the other direction of the ``noCounterpart`` list of
            :func:`epic_view`, over the whole matrix.

    Returns:
        The number of entries and relationships, of each kind, of each side and of each kind that
        is approved and that is verified; the documents by lifecycle; the stacks by app; the repositories the stacks
        name; and on request ``noArchitecture``.

    """
    summary: MatrixSummary = {
        "entries": 0,
        "relationships": 0,
        "byKind": {},
        "bySide": {},
        "relationshipsByKind": {},
        "relationshipsBySide": {},
        "verifiedByKind": {},
        "verifiedRelationshipsByKind": {},
        "approvedByKind": {},
        "approvedRelationshipsByKind": {},
        "documentsByLifecycle": {},
        "stacksByApp": {},
        "repositories": [],
    }
    entries: list[Entry] = matrix.entries()
    summary["entries"] = len(entries)
    summary["repositories"] = sorted({
        _text(stack.attributes.get(ATTR_REPOSITORY)) for stack in entries if stack.attributes.get(ATTR_REPOSITORY)
    })
    entry: Entry
    for entry in entries:
        _count(summary["byKind"], entry.kind)
        _count(summary["bySide"], entry.side)
        if entry.verified is not None:
            _count(summary["verifiedByKind"], entry.kind)
        if approved_by(entry) is not None:
            _count(summary["approvedByKind"], entry.kind)
        if entry.kind == KIND_DOCUMENT:
            _count(summary["documentsByLifecycle"], _text(entry.attributes.get(ATTR_LIFECYCLE)))
        if entry.kind == KIND_STACK:
            _count(summary["stacksByApp"], _text(entry.attributes.get(ATTR_APP)))
    relationship: Relationship
    for relationship in matrix.relationships():
        summary["relationships"] += 1
        _count(summary["relationshipsByKind"], relationship.kind)
        _count(summary["relationshipsBySide"], relationship.side)
        if relationship.verified is not None:
            _count(summary["verifiedRelationshipsByKind"], relationship.kind)
        if relationship.approved is not None:
            _count(summary["approvedRelationshipsByKind"], relationship.kind)
    if unlinked:
        summary["noArchitecture"] = _no_architecture(matrix)
    return summary


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approval_view(matrix: Matrix, bead: str) -> ApprovalView:
    """List which of the matrix content an Epic reaches carries the approved flag.

    The content is ``matrixtraverse.approval_scope``: the Epic, its requirements and every
    architecture-side entry it reaches by the rule of reach, with the architecture-side
    relationships between them. An
    Epic the matrix does not hold raises ``MatrixError``, and an empty beads id raises
    ``ValueError`` from ``epic_id``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id.

    Returns:
        The Epic; the entries it reaches that carry the flag (with the Epic whose approval set
        it) and those that do not, in id order; and how many of the relationships between them
        there are and carry the flag.

    """
    epic: EntryId = epic_id(bead)
    scope: ApprovalScope = approval_scope(matrix, epic)
    approved: list[Approval] = []
    not_approved: list[EntryId] = []
    entry_id: EntryId
    for entry_id in scope.entries:
        entry: Entry = matrix.entry(entry_id)
        by: str | None = approved_by(entry)
        if by is None:
            not_approved.append(entry_id)
        else:
            approved.append({"id": entry.id, "kind": entry.kind, "name": entry.name, "approvedBy": by})
    return {
        "epic": epic,
        "approved": approved,
        "notApproved": not_approved,
        "relationships": len(scope.relationships),
        "approvedRelationships": sum(1 for held in scope.relationships if held.approved is not None),
    }


def _with_stack(matrix: Matrix, entry_id: EntryId) -> View:
    """Render one entry with the stack that holds it and that stack's repository.

    Returns:
        The entry as the end of a relationship renders it, with ``stack`` (the architecture-side
        home, else the repository-side one) and ``repository`` where they are recorded.

    """
    view: View = _brief(matrix, entry_id)
    stack: EntryId | None = holder(matrix, entry_id)
    if stack is not None:
        view["stack"] = stack
        repository: JsonValue = matrix.entry(stack).attributes.get(ATTR_REPOSITORY)
        if isinstance(repository, str):
            view["repository"] = repository
    return view


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def resources_view(matrix: Matrix, bead: str) -> View:
    """Return the AWS resources an Epic reaches, with their stacks and repositories.

    What the Epic reaches is what ``epic --closure`` walks (``epic_reach``): the entries its
    features lead to, what is in a repository for each, and the far end of every dependency of
    their stacks (a Lambda function's VPC, subnets and security groups among them), together with
    every entry the Epic links to itself. An AWS resource is an entry that states ``resourceType``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id.

    Returns:
        ``resources``: each resource with its stack and repository; ``stacks``: each stack that
        holds one, with its repository and the resources it holds; ``noStack``: the resources no
        stack holds.

    """
    epic: EntryId = epic_id(bead)
    reach: EpicReach = epic_reach(matrix, epic)
    reached: dict[EntryId, None] = dict.fromkeys(reach.ways)
    reached.update(
        dict.fromkeys(corresponding.end for found in reach.counterparts.values() for corresponding in found),
    )
    reached.update(dict.fromkeys(dependency.far for dependency in reach.dependencies))
    reached.update(dict.fromkeys(linked.end for linked in matrix.outgoing(epic)))
    resources: list[View] = []
    stacks: dict[EntryId, list[JsonValue]] = {}
    no_stack: list[JsonValue] = []
    entry_id: EntryId
    for entry_id in sorted(reached):
        if not isinstance(matrix.entry(entry_id).attributes.get(ATTR_RESOURCE_TYPE), str):
            continue
        resources.append(_with_stack(matrix, entry_id))
        stack: EntryId | None = holder(matrix, entry_id)
        if stack is None:
            no_stack.append(entry_id)
        else:
            stacks.setdefault(stack, []).append(entry_id)
    return {
        "command": "resources",
        "epic": epic,
        "resources": list(resources),
        "stacks": [
            {
                "stack": stack,
                "repository": matrix.entry(stack).attributes.get(ATTR_REPOSITORY),
                "resources": held_ids,
            }
            for stack, held_ids in sorted(stacks.items())
        ],
        "noStack": no_stack,
    }


def _parameter(matrix: Matrix, parameter: EntryId) -> View:
    """Render one SSM parameter with the entries that read it.

    Returns:
        The parameter with the stack that writes it and its repository, and ``readBy``: each
        ``reads`` relationship that ends at it, with the reader, its stack and its repository.

    """
    view: View = _with_stack(matrix, parameter)
    view["readBy"] = [
        {"relationship": relationship_json(reading), "entry": _with_stack(matrix, reading.start)}
        for reading in matrix.incoming(parameter, (REL_READS,))
    ]
    return view


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parameters_view(matrix: Matrix, stack: EntryId) -> View:
    """Return the SSM parameters a stack writes and those it reads.

    An SSM parameter is an entry of ``resourceType`` ``ssm-parameter``; the stack that holds it
    (``homeIn``) writes it, and each entry that reads it states ``reads``. A stack's reads are
    those of the stack and of every entry it holds.

    Args:
        matrix: The matrix.
        stack: The stack's id.

    Returns:
        ``writes``: each parameter the stack holds, with the entries that read it; ``reads``:
        each parameter the stack or an entry it holds reads, with the stack that writes it.

    Raises:
        MatrixError: The entry is not a stack.

    """
    if matrix.entry(stack).kind != KIND_STACK:
        message: str = f"{stack} is not a stack"
        raise MatrixError(message)
    writes: list[JsonValue] = [
        _parameter(matrix, inside)
        for inside in held(matrix, stack)
        if matrix.entry(inside).attributes.get(ATTR_RESOURCE_TYPE) == RESOURCE_SSM_PARAMETER
    ]
    readers: list[EntryId] = [stack, *held(matrix, stack)]
    reads: list[JsonValue] = [
        {"relationship": relationship_json(reading), "entry": _with_stack(matrix, reading.end)}
        for reader in readers
        for reading in matrix.outgoing(reader, (REL_READS,))
        if matrix.entry(reading.end).attributes.get(ATTR_RESOURCE_TYPE) == RESOURCE_SSM_PARAMETER
    ]
    return {"command": "parameters", "stack": _brief(matrix, stack), "writes": writes, "reads": reads}


def _parts(matrix: Matrix, entry_id: EntryId) -> list[EntryId]:
    """Name an entry and what belongs to it.

    Returns:
        The entry, every entry that is part of it (``partOf``) to any depth and, for a stack,
        every entry it holds, each once.

    """
    found: dict[EntryId, None] = {entry_id: None}
    queue: deque[EntryId] = deque([entry_id])
    while queue:
        current: EntryId = queue.popleft()
        inside: list[EntryId] = [part.start for part in matrix.incoming(current, (REL_PART_OF,))]
        if matrix.entry(current).kind == KIND_STACK:
            inside.extend(held(matrix, current))
        fresh: list[EntryId] = [item for item in inside if item not in found]
        found.update(dict.fromkeys(fresh))
        queue.extend(fresh)
    return list(found)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def documents_view(matrix: Matrix, entry_id: EntryId) -> View:
    """Return every architecture and design document related to an entry, such as a service.

    The entry stands for itself and what belongs to it (:func:`_parts`). A document is related
    when any relationship, of any kind and either side, joins it to one of those: an arc42 or
    detailed design document that describes them, or a file such as a saved OpenAPI document.

    Args:
        matrix: The matrix.
        entry_id: The entry's id.

    Returns:
        ``documents``: each related document once, with its kind, lifecycle where it has one, and
        ``links``: each relationship that joins it, with the entry at the other end.

    """
    documents: dict[EntryId, list[JsonValue]] = {}
    member: EntryId
    for member in _parts(matrix, entry_id):
        relationship: Relationship
        for relationship in matrix.outgoing(member):
            if matrix.entry(relationship.end).kind in DOCUMENT_KINDS:
                documents.setdefault(relationship.end, []).append(
                    {"relationship": relationship_json(relationship), "entry": member},
                )
        for relationship in matrix.incoming(member):
            if matrix.entry(relationship.start).kind in DOCUMENT_KINDS:
                documents.setdefault(relationship.start, []).append(
                    {"relationship": relationship_json(relationship), "entry": member},
                )
    rendered: list[JsonValue] = []
    document: EntryId
    for document in sorted(documents):
        entry: Entry = matrix.entry(document)
        view: View = {"id": document, "kind": entry.kind, "name": entry.name, "side": entry.side}
        lifecycle: JsonValue = entry.attributes.get(ATTR_LIFECYCLE)
        if lifecycle is not None:
            view["lifecycle"] = lifecycle
        view["links"] = documents[document]
        rendered.append(view)
    return {"command": "documents", "entry": _brief(matrix, entry_id), "documents": rendered}


def _steps(matrix: Matrix, entry_id: EntryId, direction: str) -> list[tuple[Relationship, EntryId]]:
    """List the relationships one step of :func:`links_view` follows from an entry.

    Returns:
        Each relationship with the entry at its far end: those that start at the entry for
        ``out`` and ``both``, those that end at it for ``in`` and ``both``.

    """
    steps: list[tuple[Relationship, EntryId]] = []
    if direction in {LINK_OUT, LINK_BOTH}:
        steps.extend((relationship, relationship.end) for relationship in matrix.outgoing(entry_id))
    if direction in {LINK_IN, LINK_BOTH}:
        steps.extend((relationship, relationship.start) for relationship in matrix.incoming(entry_id))
    return steps


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def links_view(
    matrix: Matrix,
    entry_id: EntryId,
    *,
    depth: int | None = None,
    direction: str = LINK_OUT,
    kinds: tuple[RelationshipKind, ...] = (),
) -> View:
    """Follow an entry's links to any depth.

    The walk is breadth first: each entry is reached once, by the first relationship that reaches
    it, so a link to an entry already reached is listed and not followed again.

    Args:
        matrix: The matrix.
        entry_id: The entry the walk starts at.
        depth: The most relationships from the start; None follows to any depth.
        direction: ``out`` follows the relationships that start at each entry, ``in`` those that
            end at it, ``both`` either.
        kinds: The relationship kinds to follow; empty follows every kind.

    Returns:
        ``links``: each relationship followed, with its depth, which end the walk came from
        (``direction``) and the entry at the far end; ``reached``: how many entries were reached.

    Raises:
        MatrixError: The direction is not one of ``LINK_DIRECTIONS`` or the depth is below 1.

    """
    message: str
    if direction not in LINK_DIRECTIONS:
        message = f"{direction!r} is not a direction; the directions are {', '.join(LINK_DIRECTIONS)}"
        raise MatrixError(message)
    if depth is not None and depth < 1:
        message = "the depth is a whole number of 1 or more"
        raise MatrixError(message)
    start: View = _brief(matrix, entry_id)
    seen: set[EntryId] = {entry_id}
    links: list[JsonValue] = []
    frontier: list[EntryId] = [entry_id]
    level: int = 0
    while frontier and (depth is None or level < depth):
        level += 1
        following: list[EntryId] = []
        current: EntryId
        for current in frontier:
            relationship: Relationship
            far: EntryId
            for relationship, far in _steps(matrix, current, direction):
                if kinds and relationship.kind not in kinds:
                    continue
                links.append({
                    "depth": level,
                    "direction": LINK_OUT if relationship.start == current else LINK_IN,
                    "relationship": relationship_json(relationship),
                    "entry": _brief(matrix, far),
                })
                if far not in seen:
                    seen.add(far)
                    following.append(far)
        frontier = following
    return {"command": "links", "start": start, "links": links, "reached": len(seen) - 1}
