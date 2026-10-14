"""The walks over the matrix that more than one lookup makes.

Every function here reads a matrix that is already loaded and changes nothing. A walk follows
relationships by the names the kinds registry declares (``matrix_contract``), and follows the
relationships of both sides: what the architecture states and what is in a repository today. It
returns the relationships it followed, so that whatever renders the result can show the side each
came from.

- :func:`dependencies`: the dependency family to any depth, in either direction.
- :func:`epic_reach`: an Epic to everything its requirements reach, with the links of the Epic
  that have nothing recorded at the other end; :func:`epic_touches`: what of that another Epic
  could also reach.
- :func:`constraints_for`: some entries to the constraints that bind them.
- :func:`capabilities`: some entries to the shared capabilities the work that builds them must use.
- :func:`impact`: an entry to everything a change to it reaches.

``matrixquery`` renders what these return as the objects the ``atw-matrix`` reads print.
"""

import re
import sys
from collections import deque
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    AUTHORITY_SIDE,
    FAMILY_DEPENDENCY,
    HOME_RELATIONSHIP,
    KIND_COMPONENT,
    KIND_CONSTRAINT,
    KIND_DOCUMENT,
    KIND_EPIC,
    KIND_EVENT,
    KIND_FEATURE,
    KIND_INFRASTRUCTURE,
    KIND_SERVICE,
    KIND_STACK,
    REL_APPLIES_TO,
    REL_CORRESPONDS_TO,
    REL_COVERS,
    REL_DESCRIBED_BY,
    REL_DRIVES,
    REL_HAS_REQUIREMENT,
    REL_REALIZED_BY,
    REL_RESTS_ON,
    REL_SERVED_BY,
    REL_STATED_IN,
    REL_SUPPORTED_BY,
    RELATIONSHIP_RULES,
    Entry,
    EntryId,
    EntryKind,
    JsonValue,
    MatrixError,
    Relationship,
    RelationshipKind,
    family_kinds,
)
from matrixstore import Matrix, RelationshipId, id_stack, make_id, relationship_id

MIN_WORD: Final = 2
"""The fewest characters of a word entries are matched by."""
STACK_NAME_SEPARATOR: Final = "-"
"""What separates the tokens of a stack's name; the last token is the stack's type."""
ATTR_APP: Final = "app"
ATTR_EXECUTION_USE: Final = "executionUse"
ATTR_HEADING: Final = "heading"
ATTR_PROVIDES: Final = "provides"
ATTR_RELIES: Final = "relies"
ATTR_REPOSITORY: Final = "repository"
ATTR_RESOURCE_TYPE: Final = "resourceType"
ATTR_SELECTOR: Final = "selector"
SELECTOR_STACK_TYPE: Final = "stackType"
"""The selector value that is computed from a stack's name and stored nowhere."""
HOMED_KINDS: Final[frozenset[EntryKind]] = RELATIONSHIP_RULES[HOME_RELATIONSHIP].sources
"""The kinds of entry that have a home in code."""
COUNTERPART_KINDS: Final[frozenset[EntryKind]] = RELATIONSHIP_RULES[REL_CORRESPONDS_TO].sources
"""The kinds of entry the architecture describes that something in a repository may correspond to."""
CODE_KINDS: Final[frozenset[EntryKind]] = RELATIONSHIP_RULES[REL_REALIZED_BY].targets | HOMED_KINDS
"""The kinds of entry an Epic reaches from a feature: what realizes a feature and what has a home in code."""
SHARED_KINDS: Final[frozenset[EntryKind]] = frozenset({
    KIND_FEATURE,
    KIND_DOCUMENT,
    KIND_STACK,
    KIND_SERVICE,
    KIND_COMPONENT,
    KIND_INFRASTRUCTURE,
})
"""The kinds of entry two Epics are related through when both reach one."""
_CAMEL: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_WORD: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Dependency:
    """One dependency relationship a walk found."""

    relationship: Relationship
    far: EntryId
    """The end away from where the walk began: the target of a walk outward, the source of one inward."""
    stack: EntryId | None
    """The stack that holds the far end, or the far end when it is a stack; None when it has no home."""
    depth: int
    """How many relationships from where the walk began; 1 for a relationship that touches a start."""


@dataclass(frozen=True, slots=True)
class Way:
    """One way an Epic reaches an entry from one of its features."""

    feature: EntryId
    relationship: Relationship
    """The ``realizedBy`` relationship from the feature, or the ``describedBy`` relationship from the entry."""
    document: EntryId | None
    """The document that describes both the feature and the entry; None for an entry that realizes the feature."""


@dataclass(frozen=True, slots=True)
class EpicReach:
    """Everything one Epic reaches through its requirements, the features they are served by and their code."""

    epic: EntryId
    served: Mapping[EntryId, tuple[EntryId, ...]]
    """Each requirement of the Epic with the features that serve it; empty for a requirement none serves."""
    features: tuple[EntryId, ...]
    """The features that serve a requirement, then the features those are supported by to any depth."""
    supporting: frozenset[EntryId]
    """The features reached only through ``supportedBy``."""
    documents: Mapping[EntryId, tuple[Relationship, ...]]
    """Each feature with its ``describedBy`` relationships."""
    ways: Mapping[EntryId, tuple[Way, ...]]
    """Each entry reached from a feature, by ``realizedBy`` or through a document that describes both."""
    counterparts: Mapping[EntryId, tuple[Relationship, ...]]
    """Each entry reached that has them, with its ``correspondsTo`` relationships."""
    stacks: Mapping[EntryId, frozenset[EntryId]]
    """Each stack reached, with the features that lead to it."""
    dependents: Mapping[EntryId, frozenset[EntryId]]
    """Each stack reached through a dependency, with the stacks and entries of the Epic that depend on it."""
    dependencies: tuple[Dependency, ...]
    """The dependencies of the stacks that hold what the features reach, to any depth."""
    no_stack: tuple[EntryId, ...]
    """The architecture-side entries reached that have no home in code."""
    no_repository: tuple[EntryId, ...]
    """The stacks reached that name no repository."""
    no_counterpart: tuple[EntryId, ...]
    """The architecture-side entries reached that nothing in a repository is recorded as corresponding to."""

    def entries(self) -> list[EntryId]:
        """List every entry the Epic reaches.

        Returns:
            The features, the entries reached from them, what is in a repository for each, the
            stacks and the far end of every dependency, in the order found and without repeats.

        """
        found: dict[EntryId, None] = dict.fromkeys(self.features)
        found.update(dict.fromkeys(self.ways))
        corresponding: tuple[Relationship, ...]
        for corresponding in self.counterparts.values():
            found.update(dict.fromkeys(relationship.end for relationship in corresponding))
        found.update(dict.fromkeys(self.stacks))
        found.update(dict.fromkeys(dependency.far for dependency in self.dependencies))
        return list(found)


@dataclass(frozen=True, slots=True)
class Touch:
    """One way an Epic reaches an entry."""

    through: str
    """The kind of the relationship that reaches the entry."""
    heading: str
    """The document heading the relationship names; empty when it names none."""


@dataclass(frozen=True, slots=True)
class ConstraintReach:
    """One constraint that binds some of the entries asked about."""

    constraint: EntryId
    applied: tuple[Relationship, ...]
    """The ``appliesTo`` relationships of the constraint that end at an entry asked about."""
    selected: tuple[EntryId, ...]
    """The entries asked about that the constraint's selector names."""
    sources: tuple[Relationship, ...]
    """The constraint's ``statedIn`` relationships; empty when it names no source."""


@dataclass(frozen=True, slots=True)
class CapabilityReach:
    """One shared capability the work that builds some entries must use."""

    feature: EntryId
    relies: tuple[str, ...]
    """The ids of the ``provides`` items the relationships that led here rely on; empty when they name none."""
    providers: tuple[tuple[Relationship, EntryId | None], ...]
    """Each ``realizedBy`` relationship of the feature, with the stack that holds the entry it ends at."""


@dataclass(frozen=True, slots=True)
class Serving:
    """One requirement a feature serves, with the Epic that states it."""

    feature: EntryId
    requirement: EntryId
    epic: EntryId


@dataclass(frozen=True, slots=True)
class Impact:
    """Everything a change to one entry reaches."""

    entry: EntryId
    subjects: tuple[EntryId, ...]
    """The entry, then for a stack every entry it holds."""
    described: tuple[Relationship, ...]
    """For a document: the ``describedBy`` relationships that end at it."""
    realizing: tuple[Relationship, ...]
    """The ``realizedBy`` relationships that end at the entry, at an entry it holds or at one it describes."""
    features: tuple[EntryId, ...]
    """The features reached: the entry itself when it is one, those a document describes, those realized, then
    every feature supported by one of them, to any depth."""
    supporting: tuple[Relationship, ...]
    """The ``supportedBy`` relationships followed from a feature reached to the features that rely on it."""
    constraining: tuple[Relationship, ...]
    """The ``appliesTo`` relationships that end at the entry, at an entry it holds, at one it describes or at a
    feature reached."""
    resting: tuple[Relationship, ...]
    """The ``restsOn`` relationships of Epics that end at any of the same."""
    dependents: tuple[Dependency, ...]
    """What depends on the entry, to any depth."""
    serving: tuple[Serving, ...]
    """Each requirement a feature reached serves, with its Epic."""

    def epics(self) -> list[EntryId]:
        """List the Epics the change reaches.

        Returns:
            The Epics whose requirements a feature reached serves and those that rest on something
            reached, in id order.

        """
        return sorted({*(served.epic for served in self.serving), *(resting.start for resting in self.resting)})

    def ids(self) -> list[EntryId]:
        """List the id of every entry the change reaches.

        Returns:
            The entries a stack holds, those a document describes, the features, the constraints,
            the dependents, the requirements and the Epics, in the order found, without repeats
            and without the entry itself.

        """
        found: dict[EntryId, None] = dict.fromkeys([
            *self.subjects,
            *(describing.start for describing in self.described),
            *self.features,
            *(applying.start for applying in self.constraining),
            *(dependency.far for dependency in self.dependents),
            *(served.requirement for served in self.serving),
            *self.epics(),
        ])
        found.pop(self.entry, None)
        return list(found)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def words(text: str) -> list[str]:
    """Split text into the words entries are matched by.

    Args:
        text: Any text: a query, a name, a sentence.

    Returns:
        The lower-case runs of letters and digits at least two characters long, with a camelCase
        name split at each capital, in order and without repeats.

    Raises:
        TypeError: ``text`` is not a string.

    """
    if not isinstance(text, str):
        message: str = "the text to split into words must be a string"
        raise TypeError(message)
    spaced: str = _CAMEL.sub(" ", text)
    return list(dict.fromkeys(word for word in _WORD.findall(spaced.lower()) if len(word) >= MIN_WORD))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def stack_type(name: str) -> str:
    """Read a stack's type from its name.

    Args:
        name: The stack's name.

    Returns:
        The last token of the name. The matrix stores no stack type.

    Raises:
        ValueError: The name is empty.

    """
    if not name.strip():
        message: str = "a stack's type is read from its name, and the name is empty"
        raise ValueError(message)
    return name.strip().rpartition(STACK_NAME_SEPARATOR)[2]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_id(bead: str) -> EntryId:
    """Name the entry of an Epic.

    A beads id that cannot be part of an entry id raises ``MatrixError`` from ``make_id``.

    Args:
        bead: The Epic's beads id, or the id of its entry.

    Returns:
        ``epic:<beads id>``.

    Raises:
        ValueError: ``bead`` is empty.

    """
    if not bead.strip():
        message: str = "an Epic is named by its beads id, and the id is empty"
        raise ValueError(message)
    prefix: str = f"{KIND_EPIC}:"
    return make_id(KIND_EPIC, bead.strip().removeprefix(prefix))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def holding(matrix: Matrix, stack: EntryId) -> list[Relationship]:
    """List the home relationships that end at a stack.

    Args:
        matrix: The matrix.
        stack: The stack's id.

    Returns:
        The relationships, in file order: one for each side that states that an entry's home is
        the stack. Empty for an entry that holds none.

    """
    return matrix.incoming(stack, (HOME_RELATIONSHIP,))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def held(matrix: Matrix, stack: EntryId) -> list[EntryId]:
    """List the entries whose home is a stack, as either side states it.

    Args:
        matrix: The matrix.
        stack: The stack's id.

    Returns:
        The ids of the entries the stack holds, in id order and without repeats; empty for an
        entry that holds none.

    """
    return list(dict.fromkeys(relationship.start for relationship in holding(matrix, stack)))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def holder(matrix: Matrix, entry_id: EntryId) -> EntryId | None:
    """Name the stack an entry belongs to.

    Args:
        matrix: The matrix.
        entry_id: The entry's id.

    This is the reader that reports what the repositories hold. A step that decides what is
    built reads :func:`authority_holder`.

    Returns:
        The entry itself when it is a stack; for an event, its :func:`authority_holder`;
        otherwise its home, as the architecture side states it before the repository side;
        otherwise the stack its id names; None when it has none of these or the matrix does not
        hold it.

    """
    entry: Entry | None = matrix.find(entry_id)
    if entry is None:
        return None
    if entry.kind == KIND_STACK:
        return entry_id
    if entry.kind == KIND_EVENT:
        return authority_holder(matrix, entry_id)
    return matrix.home(entry_id, side=None) or id_stack(entry)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def authority_holder(matrix: Matrix, entry_id: EntryId) -> EntryId | None:
    """Name the stack the architecture side places an entry in: the holder of what is built.

    Args:
        matrix: The matrix.
        entry_id: The entry's id.

    Returns:
        The entry itself when it is a stack; for an event, the one stack its architecture-side
        publishers are homed in (None when they are homed in none or in more than one); for
        any other kind, its architecture-side home; None when the matrix does not hold it or
        the architecture side states none.

    """
    entry: Entry | None = matrix.find(entry_id)
    if entry is None:
        return None
    if entry.kind == KIND_STACK:
        return entry_id
    if entry.kind != KIND_EVENT:
        return matrix.home(entry_id)
    stacks: frozenset[EntryId] = matrix.publisher_stacks(entry_id)
    return next(iter(stacks)) if len(stacks) == 1 else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def follow(
    matrix: Matrix,
    starts: Sequence[EntryId],
    kinds: Collection[RelationshipKind],
    *,
    inward: bool = False,
) -> list[Relationship]:
    """Walk from some entries along relationships of some kinds, to any depth.

    Args:
        matrix: The matrix.
        starts: The entries to walk from.
        kinds: The relationship kinds to follow.
        inward: Whether to follow each relationship from its end to its start.

    Returns:
        Each relationship followed, once for each side that states it, in the order found.

    """
    seen: set[EntryId] = set(starts)
    followed: dict[RelationshipId, Relationship] = {}
    queue: deque[EntryId] = deque(starts)
    while queue:
        current: EntryId = queue.popleft()
        relationship: Relationship
        for relationship in matrix.incoming(current, kinds) if inward else matrix.outgoing(current, kinds):
            followed.setdefault(relationship_id(relationship), relationship)
            far: EntryId = relationship.start if inward else relationship.end
            if far not in seen:
                seen.add(far)
                queue.append(far)
    return list(followed.values())


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def dependencies(matrix: Matrix, starts: Sequence[EntryId], *, inward: bool = False) -> list[Dependency]:
    """Follow the dependency family from some entries, to any depth.

    A walk outward answers what the entries depend on; a walk inward answers what depends on
    them. A stack stands for itself and every entry it holds: at a start in either direction, and
    wherever a walk outward arrives at one. A walk inward that arrives at an entry also continues
    from the stack that holds it, because whatever depends on that stack depends on what the
    stack's entries depend on. The two directions therefore find the same relationships. A
    dependency both sides state is found once for each.

    Args:
        matrix: The matrix.
        starts: The entries to walk from.
        inward: Whether to follow each relationship from its end to its start.

    Returns:
        Each dependency relationship found, once, nearest first.

    """
    family: frozenset[RelationshipKind] = family_kinds(FAMILY_DEPENDENCY)
    visited: set[EntryId] = set()
    queue: deque[tuple[EntryId, int]] = deque()

    def visit(entry_ids: Sequence[EntryId], depth: int) -> None:
        entry_id: EntryId
        for entry_id in entry_ids:
            if entry_id not in visited:
                visited.add(entry_id)
                queue.append((entry_id, depth))

    def with_held(entry_id: EntryId) -> list[EntryId]:
        entry: Entry | None = matrix.find(entry_id)
        return [entry_id, *held(matrix, entry_id)] if entry is not None and entry.kind == KIND_STACK else [entry_id]

    start: EntryId
    for start in starts:
        visit(with_held(start), 0)
    found: dict[RelationshipId, Dependency] = {}
    while queue:
        current: EntryId
        depth: int
        current, depth = queue.popleft()
        relationship: Relationship
        for relationship in matrix.incoming(current, family) if inward else matrix.outgoing(current, family):
            identity: RelationshipId = relationship_id(relationship)
            if identity in found:
                continue
            far: EntryId = relationship.start if inward else relationship.end
            stack: EntryId | None = holder(matrix, far)
            found[identity] = Dependency(relationship, far, stack, depth + 1)
            visit([far, *([stack] if stack is not None else [])] if inward else with_held(far), depth + 1)
    return list(found.values())


def _feature_ways(matrix: Matrix, features: Sequence[EntryId]) -> dict[EntryId, list[Way]]:
    """Walk from the features of an Epic to the entries each leads to.

    Returns:
        Each entry that realizes a feature, and each entry of a kind that has code which a
        document that describes a feature also describes, with the ways it is reached: one for
        each relationship, of either side, that reaches it from a feature.

    """
    ways: dict[EntryId, list[Way]] = {}
    feature: EntryId
    for feature in features:
        realizing: Relationship
        for realizing in matrix.outgoing(feature, (REL_REALIZED_BY,)):
            ways.setdefault(realizing.end, []).append(Way(feature, realizing, None))
        document: EntryId
        for document in dict.fromkeys(stated.end for stated in matrix.outgoing(feature, (REL_DESCRIBED_BY,))):
            describing: Relationship
            for describing in matrix.incoming(document, (REL_DESCRIBED_BY,)):
                if matrix.entry(describing.start).kind in CODE_KINDS:
                    ways.setdefault(describing.start, []).append(Way(feature, describing, document))
    return ways


def _origins(
    matrix: Matrix,
    ways: Mapping[EntryId, Collection[Way]],
    counterparts: Mapping[EntryId, Sequence[Relationship]],
) -> dict[EntryId, set[EntryId]]:
    """Group the features of an Epic by where the entries they lead to live.

    Returns:
        Each stack that holds an entry reached or what is in a repository for it, and each such
        entry with no stack, with the features it leads from.

    """
    origins: dict[EntryId, set[EntryId]] = {}
    entry_id: EntryId
    reaching: Collection[Way]
    for entry_id, reaching in ways.items():
        leading: set[EntryId] = {way.feature for way in reaching}
        found: EntryId
        for found in (entry_id, *(corresponding.end for corresponding in counterparts.get(entry_id, ()))):
            origins.setdefault(holder(matrix, found) or found, set()).update(leading)
    return origins


def _on_authority_side(matrix: Matrix, entry_ids: Collection[EntryId], kinds: Collection[EntryKind]) -> list[EntryId]:
    """Keep the entries of some kinds that the architecture side states.

    Returns:
        The ids kept, in the order given.

    """
    return [
        entry_id
        for entry_id in entry_ids
        if matrix.entry(entry_id).kind in kinds and matrix.entry(entry_id).side == AUTHORITY_SIDE
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_reach(matrix: Matrix, epic: EntryId) -> EpicReach:
    """Walk from an Epic to everything its requirements reach.

    The walk is epic → requirements → the features that serve them, with the features those are
    supported by to any depth. From each feature: the entries that realize it, and the entries a
    document that describes the feature also describes. From each entry: the stack that is its
    home, and what is in a repository for it (``correspondsTo``) with the stack that holds that.
    Then the dependency family outward from those stacks. An Epic the matrix does not hold raises
    ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        epic: The Epic's entry id.

    Returns:
        What the walk reached, and the links of the Epic with nothing recorded at the other end.

    Raises:
        MatrixError: The entry is not an Epic.

    """
    if matrix.entry(epic).kind != KIND_EPIC:
        message: str = f"{epic} is not an Epic"
        raise MatrixError(message)
    served: dict[EntryId, tuple[EntryId, ...]] = {
        stated.end: tuple(dict.fromkeys(serving.end for serving in matrix.outgoing(stated.end, (REL_SERVED_BY,))))
        for stated in matrix.outgoing(epic, (REL_HAS_REQUIREMENT,))
    }
    direct: list[EntryId] = list(dict.fromkeys(feature for serving in served.values() for feature in serving))
    supporting: list[EntryId] = [
        found
        for found in dict.fromkeys(relationship.end for relationship in follow(matrix, direct, (REL_SUPPORTED_BY,)))
        if found not in direct
    ]
    features: tuple[EntryId, ...] = (*direct, *supporting)
    ways: dict[EntryId, list[Way]] = _feature_ways(matrix, features)
    counterparts: dict[EntryId, tuple[Relationship, ...]] = {
        entry_id: corresponding
        for entry_id in ways
        if (corresponding := tuple(matrix.outgoing(entry_id, (REL_CORRESPONDS_TO,))))
    }
    origins: dict[EntryId, set[EntryId]] = _origins(matrix, ways, counterparts)
    stacks: dict[EntryId, set[EntryId]] = {
        origin: set(leading) for origin, leading in origins.items() if matrix.entry(origin).kind == KIND_STACK
    }
    dependents: dict[EntryId, set[EntryId]] = {}
    found_dependencies: dict[RelationshipId, Dependency] = {}
    origin: EntryId
    for origin in sorted(origins):
        dependency: Dependency
        for dependency in dependencies(matrix, [origin]):
            identity: RelationshipId = relationship_id(dependency.relationship)
            if identity not in found_dependencies or dependency.depth < found_dependencies[identity].depth:
                found_dependencies[identity] = dependency
            if dependency.stack is not None and dependency.stack != origin:
                stacks.setdefault(dependency.stack, set()).update(origins[origin])
                dependents.setdefault(dependency.stack, set()).add(origin)
    reached: dict[EntryId, None] = dict.fromkeys(ways)
    reached.update(dict.fromkeys(dependency.far for dependency in found_dependencies.values()))
    return EpicReach(
        epic=epic,
        served=served,
        features=features,
        supporting=frozenset(supporting),
        documents={feature: tuple(matrix.outgoing(feature, (REL_DESCRIBED_BY,))) for feature in features},
        ways={entry_id: tuple(reaching) for entry_id, reaching in ways.items()},
        counterparts=counterparts,
        stacks={stack: frozenset(leading) for stack, leading in stacks.items()},
        dependents={stack: frozenset(depending) for stack, depending in dependents.items()},
        dependencies=tuple(
            sorted(found_dependencies.values(), key=lambda item: (item.depth, relationship_id(item.relationship))),
        ),
        no_stack=tuple(
            entry_id
            for entry_id in _on_authority_side(matrix, reached, HOMED_KINDS)
            if not matrix.outgoing(entry_id, (HOME_RELATIONSHIP,))
        ),
        no_repository=tuple(
            stack for stack in sorted(stacks) if not matrix.entry(stack).attributes.get(ATTR_REPOSITORY)
        ),
        no_counterpart=tuple(
            entry_id
            for entry_id in _on_authority_side(matrix, reached, COUNTERPART_KINDS)
            if not matrix.outgoing(entry_id, (REL_CORRESPONDS_TO,))
        ),
    )


def _heading(relationship: Relationship) -> str:
    """Read the document heading a relationship names.

    Returns:
        The heading; empty when the relationship names none.

    """
    heading: JsonValue = relationship.attributes.get(ATTR_HEADING)
    return heading if isinstance(heading, str) else ""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_touches(matrix: Matrix, epic: EntryId) -> dict[EntryId, list[Touch]]:
    """List what an Epic reaches that another Epic could also reach, and how it reaches each.

    An entry that is not an Epic raises ``MatrixError`` from :func:`epic_reach`.

    Args:
        matrix: The matrix.
        epic: The Epic's entry id.

    Returns:
        Each feature, document, stack, service, component and infrastructure entry the Epic
        reaches through :func:`epic_reach`, through a ``covers`` relationship that ends at one of
        its requirements, or through its own ``drives`` and ``restsOn`` relationships, with the
        relationship kinds that reach it.

    """
    reach: EpicReach = epic_reach(matrix, epic)
    ways: list[tuple[EntryId | None, Touch]] = _closure_touches(matrix, reach)
    ways.extend(
        (relationship.start, Touch(REL_COVERS, _heading(relationship)))
        for requirement in reach.served
        for relationship in matrix.incoming(requirement, (REL_COVERS,))
    )
    ways.extend(
        (relationship.end, Touch(relationship.kind, _heading(relationship)))
        for relationship in matrix.outgoing(epic, (REL_DRIVES, REL_RESTS_ON))
    )
    touches: dict[EntryId, dict[Touch, None]] = {}
    entry_id: EntryId | None
    way: Touch
    for entry_id, way in ways:
        if entry_id is not None and matrix.entry(entry_id).kind in SHARED_KINDS:
            touches.setdefault(entry_id, {})[way] = None
    return {touched: list(found) for touched, found in touches.items()}


def _closure_touches(matrix: Matrix, reach: EpicReach) -> list[tuple[EntryId | None, Touch]]:
    """List how an Epic reaches each entry of its closure.

    Returns:
        Each feature and each document that describes one; each entry reached from a feature with
        its stack; what is in a repository for each with its stack; and the far end of each
        dependency with the stack that holds it; each with the kind of the relationship that
        reaches it. The entry is None where an entry has no stack.

    """
    ways: list[tuple[EntryId | None, Touch]] = []
    feature: EntryId
    for feature in reach.features:
        ways.append((feature, Touch(REL_SUPPORTED_BY if feature in reach.supporting else REL_SERVED_BY, "")))
        ways.extend(
            (describing.end, Touch(REL_DESCRIBED_BY, _heading(describing))) for describing in reach.documents[feature]
        )
    entry_id: EntryId
    reaching: tuple[Way, ...]
    for entry_id, reaching in reach.ways.items():
        ways.extend((entry_id, Touch(way.relationship.kind, "")) for way in reaching)
        ways.append((holder(matrix, entry_id), Touch(HOME_RELATIONSHIP, "")))
        corresponding: Relationship
        for corresponding in reach.counterparts.get(entry_id, ()):
            ways.extend([
                (corresponding.end, Touch(REL_CORRESPONDS_TO, "")),
                (holder(matrix, corresponding.end), Touch(HOME_RELATIONSHIP, "")),
            ])
    dependency: Dependency
    for dependency in reach.dependencies:
        through: Touch = Touch(dependency.relationship.kind, "")
        ways.extend([(dependency.far, through), (dependency.stack, through)])
    return ways


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def selector_values(matrix: Matrix, entry: Entry) -> dict[str, JsonValue]:
    """Read the values of an entry a constraint's selector is compared with.

    Args:
        matrix: The matrix.
        entry: The entry.

    Returns:
        The app and the type of the stack the entry belongs to, and the entry's own resource type
        and execution use; the execution use of its stack when it states none. A value the entry
        does not have is left out.

    """
    values: dict[str, JsonValue] = {}
    stack_id: EntryId | None = holder(matrix, entry.id)
    stack: Entry | None = None if stack_id is None else matrix.find(stack_id)
    name: str
    if stack is not None:
        values[SELECTOR_STACK_TYPE] = stack_type(stack.name)
        for name in (ATTR_APP, ATTR_EXECUTION_USE):
            if name in stack.attributes:
                values[name] = stack.attributes[name]
    for name in (ATTR_RESOURCE_TYPE, ATTR_EXECUTION_USE):
        if name in entry.attributes:
            values[name] = entry.attributes[name]
    return values


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def constraints_for(matrix: Matrix, entry_ids: Sequence[EntryId]) -> list[ConstraintReach]:
    """Find the constraints that bind some entries.

    An id the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        entry_ids: The entries asked about.

    Returns:
        Each constraint with an ``appliesTo`` relationship to one of the entries, or whose
        selector names one of them, in id order, with the relationships and entries it reached
        and its sources.

    """
    asked: list[EntryId] = list(dict.fromkeys(entry_ids))
    values: dict[EntryId, dict[str, JsonValue]] = {
        entry_id: selector_values(matrix, matrix.entry(entry_id)) for entry_id in asked
    }
    found: list[ConstraintReach] = []
    constraint: Entry
    for constraint in matrix.entries((KIND_CONSTRAINT,)):
        applied: tuple[Relationship, ...] = tuple(
            relationship
            for relationship in matrix.outgoing(constraint.id, (REL_APPLIES_TO,))
            if relationship.end in values
        )
        selector: JsonValue = constraint.attributes.get(ATTR_SELECTOR)
        selected: tuple[EntryId, ...] = ()
        if isinstance(selector, dict) and selector:
            selected = tuple(
                entry_id
                for entry_id in asked
                if all(values[entry_id].get(name) == wanted for name, wanted in selector.items())
            )
        if applied or selected:
            sources: tuple[Relationship, ...] = tuple(matrix.outgoing(constraint.id, (REL_STATED_IN,)))
            found.append(ConstraintReach(constraint.id, applied, selected, sources))
    return found


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def capabilities(matrix: Matrix, entry_ids: Sequence[EntryId]) -> list[CapabilityReach]:
    """Find the shared capabilities the work that builds some entries must use.

    The walk is entries → the features they realize → the features those are supported by, to any
    depth; a feature given among the entries is walked from itself. A capability is a feature
    that states what it provides and is reached through ``supportedBy`` or is itself among the
    entries given: work that states a shared capability uses it. An id the matrix does not hold
    raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        entry_ids: The entries the work builds, and the shared capabilities it states.

    Returns:
        Each capability in id order, with the ``provides`` items relied on (none named means
        every item) and the relationships to the entries that realize it, each with the stack
        that holds the entry.

    """
    queue: deque[EntryId] = deque()
    relied: dict[EntryId, set[str]] = {}
    entry_id: EntryId
    for entry_id in dict.fromkeys(entry_ids):
        if matrix.entry(entry_id).kind == KIND_FEATURE:
            queue.append(entry_id)
            relied.setdefault(entry_id, set())
        queue.extend(relationship.start for relationship in matrix.incoming(entry_id, (REL_REALIZED_BY,)))
    walked: set[EntryId] = set()
    while queue:
        feature: EntryId = queue.popleft()
        if feature in walked:
            continue
        walked.add(feature)
        relationship: Relationship
        for relationship in matrix.outgoing(feature, (REL_SUPPORTED_BY,)):
            relies: JsonValue = relationship.attributes.get(ATTR_RELIES)
            named: list[str] = [item for item in relies if isinstance(item, str)] if isinstance(relies, list) else []
            relied.setdefault(relationship.end, set()).update(named)
            queue.append(relationship.end)
    return [
        CapabilityReach(
            feature=supporting,
            relies=tuple(sorted(relied[supporting])),
            providers=tuple(
                (realizing, holder(matrix, realizing.end))
                for realizing in matrix.outgoing(supporting, (REL_REALIZED_BY,))
            ),
        )
        for supporting in sorted(relied)
        if matrix.entry(supporting).attributes.get(ATTR_PROVIDES)
    ]


def _served(matrix: Matrix, features: Sequence[EntryId]) -> list[Serving]:
    """Walk from some features to the requirements they serve and the Epics that state those.

    Returns:
        Each requirement a feature serves with its Epic, without repeats.

    """
    return list(
        dict.fromkeys(
            Serving(feature, serving.start, stating.start)
            for feature in features
            for serving in matrix.incoming(feature, (REL_SERVED_BY,))
            for stating in matrix.incoming(serving.start, (REL_HAS_REQUIREMENT,))
        ),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def impact(matrix: Matrix, entry_id: EntryId) -> Impact:
    """Walk from an entry to everything a change to it reaches.

    From the entry, and for a stack from every entry it holds: the entries a document describes;
    the features those and the entry realize, and every feature supported by one of them, to any
    depth; the constraints that apply to any of those; the Epics that rest on any of those; what
    depends on the entry, to any depth; then from every feature reached, the requirements it
    serves and the Epics that state them. An entry the matrix does not hold raises
    ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        entry_id: The entry's id.

    Returns:
        What the change reaches.

    """
    entry: Entry = matrix.entry(entry_id)
    subjects: list[EntryId] = [entry_id, *(held(matrix, entry_id) if entry.kind == KIND_STACK else [])]
    described: list[Relationship] = (
        matrix.incoming(entry_id, (REL_DESCRIBED_BY,)) if entry.kind == KIND_DOCUMENT else []
    )
    touched: list[EntryId] = list(dict.fromkeys([*subjects, *(describing.start for describing in described)]))
    realizing: list[Relationship] = [
        relationship for found in touched for relationship in matrix.incoming(found, (REL_REALIZED_BY,))
    ]
    roots: list[EntryId] = list(
        dict.fromkeys([
            *(found for found in touched if matrix.entry(found).kind == KIND_FEATURE),
            *(relationship.start for relationship in realizing),
        ]),
    )
    supporting: list[Relationship] = follow(matrix, roots, (REL_SUPPORTED_BY,), inward=True)
    features: list[EntryId] = list(dict.fromkeys([*roots, *(relationship.start for relationship in supporting)]))
    bound: list[EntryId] = list(dict.fromkeys([*touched, *features]))
    return Impact(
        entry=entry_id,
        subjects=tuple(subjects),
        described=tuple(described),
        realizing=tuple(realizing),
        features=tuple(features),
        supporting=tuple(supporting),
        constraining=tuple(
            relationship for found in bound for relationship in matrix.incoming(found, (REL_APPLIES_TO,))
        ),
        resting=tuple(relationship for found in bound for relationship in matrix.incoming(found, (REL_RESTS_ON,))),
        dependents=tuple(dependencies(matrix, [entry_id], inward=True)),
        serving=tuple(_served(matrix, features)),
    )
