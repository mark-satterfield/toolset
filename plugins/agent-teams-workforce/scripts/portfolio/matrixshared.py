"""The shared items of the Epics, the judgments of which Epic goes first on each, and their batches.

An Epic has requirements; a requirement is served by features; a feature is realized by
architecture entries (services, components, infrastructure, events, stacks, packages, layers),
which depend on other entries. No Epic relates directly to another Epic. An item is SHARED when
two or more Epics need it, whatever repository or name it has: a feature serving a requirement of
each, or an architecture entry each reaches by the rule of reach
(``matrixtraverse.requirement_reach``: a serving feature's realizer, the stack it is or has its
home in, or the far end of one dependency from either).

While a shared item's architecture is not approved, one judgment decides the order of the Epics
that need it: an architecture-side ``drives`` relationship from one Epic to the item, with
``basis`` ``owns`` (this Epic builds and owns the item; the others use it) or ``shared`` (the
Epics share it independently; this Epic merely goes first) and a one-sentence ``reason``. Every
other Epic that needs the item waits for that Epic. The owner's records stay in force: a
``drives`` with no basis from an Epic to a stack says the Epic owns every shared item realized or
homed in that stack, and ``epicDriver: none`` on a stack says no shared item realized or homed in
it orders Epics (the stack is deployed in advance).

- :func:`shared_items`: every shared item with the Epics that need it, through which
  requirements, its approval and the record that decides it.
- :func:`write_batches`: the unapproved shared items no record decides, in batches for judging.
- :func:`record_judgments`: record a judgment file as ``drives`` relationships.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    AUTHORITY_SIDE,
    KIND_COMPONENT,
    KIND_EPIC,
    KIND_EVENT,
    KIND_FEATURE,
    KIND_INFRASTRUCTURE,
    KIND_LAYER,
    KIND_PACKAGE,
    KIND_SERVICE,
    KIND_STACK,
    REL_DRIVES,
    REL_HAS_REQUIREMENT,
    REL_REALIZED_BY,
    Entry,
    EntryId,
    EntryKind,
    JsonValue,
    MatrixError,
    Relationship,
)
from matrixstore import (
    ATTR_BASIS,
    ATTR_EPIC_DRIVER,
    ATTR_REASON,
    Matrix,
    MatrixRefusedError,
    kind_of,
)
from matrixsync import parse_requirements
from matrixtraverse import authority_holder, epic_id, requirement_reach
from matrixwrite import link, unlink
from strictschema import validator

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

type Basis = Literal["owns", "shared"]
type Source = Literal["judged", "owner-stack"]

BASIS_OWNS: Final[Basis] = "owns"
BASIS_SHARED: Final[Basis] = "shared"
BASES: Final[tuple[Basis, ...]] = (BASIS_OWNS, BASIS_SHARED)
SOURCE_JUDGED: Final[Source] = "judged"
SOURCE_OWNER_STACK: Final[Source] = "owner-stack"
DRIVER_NONE: Final = "none"
"""The ``epicDriver`` value by which the owner says a stack is deployed in advance."""
MIN_SHARED: Final = 2
"""The number of Epics that must need an item before it is shared."""
BATCH_SIZE: Final = 25
"""About how many items one batch holds; a group of items with the same Epics is never split."""
ARCHITECTURE_KINDS: Final[frozenset[EntryKind]] = frozenset({
    KIND_SERVICE,
    KIND_COMPONENT,
    KIND_INFRASTRUCTURE,
    KIND_EVENT,
    KIND_STACK,
    KIND_PACKAGE,
    KIND_LAYER,
})
"""The kinds of architecture entry an item may be, beside a feature."""
TITLE_PREFIX: Final = "Feature PRD: "
INDEX_FILE: Final = "index.json"
BATCH_FILE: Final = "batch-{number:03d}.json"
SCHEMAS: Final[Path] = Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "schemas"
JUDGMENT_SCHEMA_PATH: Final[Path] = SCHEMAS / "shared-item-judgments.schema.json"
"""The schema of a judgment file."""
JUDGMENTS: Final = "judgments"


@dataclass(frozen=True, slots=True)
class Decision:
    """The record that decides which Epic goes first on a shared item."""

    driver: str
    """The beads id of the Epic that goes first."""
    basis: Basis
    """``owns`` or ``shared``; the owner's decision for a whole stack is ``owns``."""
    reason: str
    source: Source
    """``judged``: a ``drives`` with a basis to the item; ``owner-stack``: the owner's ``drives`` to its stack."""


@dataclass(frozen=True, slots=True)
class SharedItem:
    """One item two or more Epics need."""

    id: EntryId
    kind: EntryKind
    name: str
    purpose: str
    needs: Mapping[str, tuple[EntryId, ...]]
    """Each Epic that needs the item, by beads id, with the requirements through which it does."""
    approved: bool
    stack: EntryId | None
    """The stack the item is or is homed in; for a feature, the one stack all its realizers are in."""
    decision: Decision | None
    """The record that decides who goes first; None when none does."""
    in_advance: bool
    """Whether the item's stack says ``epicDriver: none``: the stack is deployed in advance."""


class Judgment(TypedDict):
    """One judgment of a judgment file."""

    item: EntryId
    driver: str
    basis: Basis
    reason: str


class Recorded(TypedDict):
    """What :func:`record_judgments` did."""

    file: str
    recorded: list[JsonValue]
    replaced: list[JsonValue]


def epic_needs(matrix: Matrix) -> dict[EntryId, dict[str, set[EntryId]]]:
    """Find, for every feature and architecture entry, the Epics that need it and through which requirements.

    A requirement needs the features that serve it and the architecture-side entries it reaches
    by the rule of reach (``matrixtraverse.requirement_reach``).

    Returns:
        Each item some Epic needs, with each Epic's beads id and its requirements.

    """
    needed: dict[EntryId, dict[str, set[EntryId]]] = {}
    prefix: str = f"{KIND_EPIC}:"
    epic: Entry
    for epic in matrix.entries((KIND_EPIC,)):
        bead: str = epic.id.removeprefix(prefix)
        stated: Relationship
        for stated in matrix.outgoing(epic.id, (REL_HAS_REQUIREMENT,)):
            features, reached = requirement_reach(matrix, stated.end)
            items: set[EntryId] = set(features) | {
                entry_id
                for entry_id in reached
                if (entry := matrix.find(entry_id)) is not None
                and entry.side == AUTHORITY_SIDE
                and entry.kind in ARCHITECTURE_KINDS
            }
            for item in items:
                needed.setdefault(item, {}).setdefault(bead, set()).add(stated.end)
    return needed


def realizers(matrix: Matrix, feature: EntryId) -> tuple[EntryId, ...]:
    """Name the architecture-side entries a feature is ``realizedBy`` on the architecture side.

    Returns:
        The entries, in id order.

    """
    return tuple(
        sorted({
            realizing.end
            for realizing in matrix.outgoing(feature, (REL_REALIZED_BY,))
            if realizing.side == AUTHORITY_SIDE and matrix.entry(realizing.end).side == AUTHORITY_SIDE
        }),
    )


def is_approved(matrix: Matrix, item: EntryId) -> bool:
    """Tell whether an item's architecture is approved.

    Returns:
        For a feature: it has a realizer and every realizer carries the approved mark. For an
        architecture entry: it carries the mark.

    """
    if kind_of(item) != KIND_FEATURE:
        return matrix.entry(item).approved
    realized: tuple[EntryId, ...] = realizers(matrix, item)
    return bool(realized) and all(matrix.entry(entry_id).approved for entry_id in realized)


def item_stack(matrix: Matrix, item: EntryId) -> EntryId | None:
    """Name the stack an item is realized or homed in, for the owner's stack decisions.

    Returns:
        For a feature, the one stack every realizer is or is homed in (None when it has none or
        several); for an architecture entry, the stack it is or the architecture side homes it in.

    """
    if kind_of(item) != KIND_FEATURE:
        return authority_holder(matrix, item)
    stacks: set[EntryId | None] = {authority_holder(matrix, entry_id) for entry_id in realizers(matrix, item)}
    return next(iter(stacks)) if len(stacks) == 1 else None


def _epic_of(relationship: Relationship) -> str:
    return relationship.start.removeprefix(f"{KIND_EPIC}:")


def owner_decision(matrix: Matrix, stack: EntryId) -> tuple[str | None, bool]:
    """Read the owner's decision for a stack.

    Returns:
        The Epic a ``drives`` with no basis to the stack names (else None), and whether the stack
        says ``epicDriver: none``.

    Raises:
        ValueError: Two Epics drive the stack, or one does beside ``epicDriver: none``.

    """
    named: list[str] = sorted({
        _epic_of(relationship)
        for relationship in matrix.incoming(stack, (REL_DRIVES,))
        if relationship.side == AUTHORITY_SIDE
        and kind_of(relationship.start) == KIND_EPIC
        and ATTR_BASIS not in relationship.attributes
    })
    none: bool = matrix.entry(stack).attributes.get(ATTR_EPIC_DRIVER) == DRIVER_NONE
    if len(named) > 1 or (named and none):
        message: str = f"the matrix holds conflicting owner decisions for {stack}: {', '.join(named)}"
        raise ValueError(message + (f" and {ATTR_EPIC_DRIVER}: {DRIVER_NONE}" if none else ""))
    return (named[0] if named else None), none


def judgment_of(matrix: Matrix, item: EntryId) -> Decision | None:
    """Read the judgment recorded for one item: the ``drives`` with a basis that ends at it.

    Returns:
        The judgment, or None when none is recorded.

    """
    judged: list[Relationship] = [
        relationship
        for relationship in matrix.incoming(item, (REL_DRIVES,))
        if relationship.side == AUTHORITY_SIDE and ATTR_BASIS in relationship.attributes
    ]
    if not judged:
        return None
    relationship: Relationship = judged[0]
    basis: JsonValue = relationship.attributes[ATTR_BASIS]
    return Decision(
        _epic_of(relationship),
        BASIS_OWNS if basis == BASIS_OWNS else BASIS_SHARED,
        str(relationship.attributes.get(ATTR_REASON, "")),
        SOURCE_JUDGED,
    )


def _decided(matrix: Matrix, item: EntryId, stack: EntryId | None) -> tuple[Decision | None, bool]:
    """Find the record that decides an item: its own judgment, else the owner's decision for its stack.

    Returns:
        The decision (None: none), and whether the item's stack is deployed in advance.

    Raises:
        ValueError: The item carries a judgment and its stack an owner's decision as well.

    """
    judged: Decision | None = judgment_of(matrix, item)
    owner, none = owner_decision(matrix, stack) if stack is not None else (None, False)
    if judged is not None and (owner is not None or none):
        message: str = f"{item} carries a judgment and its stack {stack} the owner's decision; one decides an item"
        raise ValueError(message)
    if owner is not None:
        reason: str = f"the owner's decision: {owner} owns every shared item realized or homed in {stack}"
        return Decision(owner, BASIS_OWNS, reason, SOURCE_OWNER_STACK), False
    return judged, none


def shared_items(matrix: Matrix) -> list[SharedItem]:
    """List every item two or more Epics need, with what decides who goes first on it.

    Returns:
        The items, in id order.

    """
    found: list[SharedItem] = []
    item: EntryId
    by: dict[str, set[EntryId]]
    for item, by in sorted(epic_needs(matrix).items()):
        if len(by) < MIN_SHARED:
            continue
        entry: Entry = matrix.entry(item)
        stack: EntryId | None = item_stack(matrix, item)
        decision, in_advance = _decided(matrix, item, stack)
        found.append(
            SharedItem(
                id=item,
                kind=entry.kind,
                name=entry.name,
                purpose=entry.purpose,
                needs={bead: tuple(sorted(requirements)) for bead, requirements in sorted(by.items())},
                approved=is_approved(matrix, item),
                stack=stack,
                decision=decision,
                in_advance=in_advance,
            ),
        )
    return found


def epic_titles(matrix: Matrix) -> dict[str, str]:
    """Read every Epic's title.

    Returns:
        Each Epic's title by its beads id.

    """
    prefix: str = f"{KIND_EPIC}:"
    return {
        entry.id.removeprefix(prefix): entry.name.removeprefix(TITLE_PREFIX).strip()
        for entry in matrix.entries((KIND_EPIC,))
    }


def requirement_texts(matrix: Matrix, vault: Path, epics: Collection[str]) -> dict[EntryId, str]:
    """Read the text of every requirement of some Epics from their PRDs.

    Returns:
        Each requirement's own text by its id; a requirement whose PRD is missing has none.

    """
    texts: dict[EntryId, str] = {}
    bead: str
    for bead in sorted(epics):
        prd: JsonValue = matrix.entry(epic_id(bead)).attributes.get("prd")
        path: JsonValue = prd.get("path") if isinstance(prd, dict) else None
        file: Path | None = vault / path if isinstance(path, str) else None
        if file is None or not file.is_file():
            continue
        texts.update({
            EntryId(f"requirement:{bead}/{read.key}"): read.text
            for read in parse_requirements(file.read_text(encoding="utf-8"))
        })
    return texts


def to_judge(items: Sequence[SharedItem]) -> list[SharedItem]:
    """Select the items a judgment is still needed for.

    Returns:
        The unapproved items no record decides and whose stack is not deployed in advance.

    """
    return [item for item in items if not item.approved and item.decision is None and not item.in_advance]


def _groups(items: Sequence[SharedItem]) -> list[list[SharedItem]]:
    """Group the items whose sets of Epics are identical.

    Returns:
        The groups, the largest first, a tie by their Epics.

    """
    grouped: dict[tuple[str, ...], list[SharedItem]] = {}
    for item in items:
        grouped.setdefault(tuple(item.needs), []).append(item)
    return [grouped[key] for key in sorted(grouped, key=lambda key: (-len(grouped[key]), key))]


def batches(items: Sequence[SharedItem], size: int = BATCH_SIZE) -> list[list[list[SharedItem]]]:
    """Pack groups of items into batches of about ``size`` items, never splitting a group.

    Returns:
        The batches, each a list of groups.

    """
    packed: list[list[list[SharedItem]]] = []
    current: list[list[SharedItem]] = []
    count: int = 0
    group: list[SharedItem]
    for group in _groups(items):
        if current and count + len(group) > size:
            packed.append(current)
            current, count = [], 0
        current.append(group)
        count += len(group)
    if current:
        packed.append(current)
    return packed


def _item_json(item: SharedItem, titles: Mapping[str, str]) -> JsonValue:
    """Render one item of a batch; its requirements are named by id, their texts are the batch's ``requirements``.

    Returns:
        The item.

    """
    return {
        "id": item.id,
        "kind": item.kind,
        "name": item.name,
        "purpose": item.purpose,
        "stack": item.stack,
        "epics": [
            {"epic": bead, "title": titles.get(bead, bead), "requirements": list(requirements)}
            for bead, requirements in item.needs.items()
        ],
    }


def _requirements_json(
    matrix: Matrix,
    groups: Sequence[Sequence[SharedItem]],
    texts: Mapping[EntryId, str],
) -> JsonValue:
    """Render every requirement the items of one batch are needed through, once.

    Returns:
        Each requirement by id with its heading and its own text (null when its PRD is missing).

    """
    named: set[EntryId] = {
        requirement
        for group in groups
        for item in group
        for requirements in item.needs.values()
        for requirement in requirements
    }
    return {
        requirement: {"name": matrix.entry(requirement).name, "text": texts.get(requirement)}
        for requirement in sorted(named)
    }


def write_batches(matrix: Matrix, vault: Path, folder: Path, size: int = BATCH_SIZE) -> dict[str, JsonValue]:
    """Write the shared items still to be judged, in batches, with an index.

    Args:
        matrix: The matrix, read only.
        vault: The vault root the PRD paths are relative to.
        folder: The folder to write the batch files and ``index.json`` into; it is created.
        size: About how many items one batch holds.

    Returns:
        The index: the counts and each batch file with its items.

    """
    items: list[SharedItem] = shared_items(matrix)
    open_items: list[SharedItem] = to_judge(items)
    packed: list[list[list[SharedItem]]] = batches(open_items, size)
    titles: dict[str, str] = epic_titles(matrix)
    texts: dict[EntryId, str] = requirement_texts(matrix, vault, {bead for item in open_items for bead in item.needs})
    folder.mkdir(parents=True, exist_ok=True)
    listed: list[JsonValue] = []
    number: int
    groups: list[list[SharedItem]]
    for number, groups in enumerate(packed, start=1):
        name: str = BATCH_FILE.format(number=number)
        document: dict[str, JsonValue] = {
            "batch": number,
            "of": len(packed),
            "groups": [
                {"epics": list(group[0].needs), "items": [_item_json(item, titles) for item in group]}
                for group in groups
            ],
            "requirements": _requirements_json(matrix, groups, texts),
        }
        (folder / name).write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        listed.append({
            "file": name,
            "items": sum(len(group) for group in groups),
            "groups": len(groups),
            "ids": [item.id for group in groups for item in group],
        })
    unapproved: list[SharedItem] = [item for item in items if not item.approved]
    by_kind: dict[str, int] = {}
    for item in open_items:
        by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
    index: dict[str, JsonValue] = {
        "shared": len(items),
        "approved": len(items) - len(unapproved),
        "judged": sum(1 for item in unapproved if item.decision is not None and item.decision.source == SOURCE_JUDGED),
        "ownerStack": sum(
            1 for item in unapproved if item.decision is not None and item.decision.source == SOURCE_OWNER_STACK
        ),
        "deployedInAdvance": sum(1 for item in unapproved if item.in_advance),
        "toJudge": len(open_items),
        "toJudgeByKind": dict(sorted(by_kind.items())),
        "groups": sum(len(groups) for groups in packed),
        "batchSize": size,
        "batches": listed,
    }
    (folder / INDEX_FILE).write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return index


def item_json(item: SharedItem, titles: Mapping[str, str]) -> JsonValue:
    """Render one shared item with its Epics and its decision, for the ``shared-items`` read.

    Returns:
        The item.

    """
    decision: JsonValue = (
        None
        if item.decision is None
        else {
            "driver": item.decision.driver,
            "basis": item.decision.basis,
            "reason": item.decision.reason,
            "source": item.decision.source,
        }
    )
    return {
        "id": item.id,
        "kind": item.kind,
        "name": item.name,
        "approved": item.approved,
        "stack": item.stack,
        "deployedInAdvance": item.in_advance,
        "decision": decision,
        "epics": [
            {"epic": bead, "title": titles.get(bead, bead), "requirements": list(requirements)}
            for bead, requirements in item.needs.items()
        ],
    }


def read_judgments(path: Path) -> list[Judgment]:
    """Read a judgment file and check it against its schema.

    Returns:
        The judgments, in file order.

    Raises:
        MatrixRefusedError: The file cannot be read, is not JSON or breaks the schema.

    """
    message: str
    try:
        document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        message = f"cannot read the judgment file {path}: {error}"
        raise MatrixRefusedError(message) from error
    schema: dict[str, JsonValue] = json.loads(JUDGMENT_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors: list[str] = [
        f"{'/'.join(str(part) for part in error.absolute_path) or '(file)'}: {error.message}"
        for error in validator(schema, location=JUDGMENT_SCHEMA_PATH).iter_errors(document)
    ]
    if errors or not isinstance(document, dict):
        message = f"the judgment file {path} breaks {JUDGMENT_SCHEMA_PATH.name}: {'; '.join(errors)}"
        raise MatrixRefusedError(message)
    listed: JsonValue = document[JUDGMENTS]
    judgments: list[Judgment] = []
    for each in listed if isinstance(listed, list) else []:
        record: dict[str, JsonValue] = each if isinstance(each, dict) else {}
        judgments.append({
            "item": EntryId(str(record["item"])),
            "driver": str(record["driver"]).removeprefix(f"{KIND_EPIC}:"),
            "basis": BASIS_OWNS if record["basis"] == BASIS_OWNS else BASIS_SHARED,
            "reason": str(record["reason"]),
        })
    return judgments


def _problems(
    matrix: Matrix,
    judgments: Sequence[Judgment],
    needed: Mapping[EntryId, Mapping[str, object]],
) -> list[str]:
    """Check each judgment against the matrix.

    Returns:
        One sentence per judgment that names an item no two Epics need, a driver that does not
        need the item, an item the owner's decision for its stack covers, or an item judged twice.

    """
    problems: list[str] = []
    seen: set[EntryId] = set()
    index: int
    judgment: Judgment
    for index, judgment in enumerate(judgments):
        item: EntryId = judgment["item"]
        where: str = f"judgment {index} ({item})"
        by: Mapping[str, object] = needed.get(item, {})
        if item in seen:
            problems.append(f"{where}: the item is judged twice in the file")
        seen.add(item)
        if len(by) < MIN_SHARED:
            problems.append(f"{where}: fewer than {MIN_SHARED} Epics need the item, so it is not shared")
            continue
        if judgment["driver"] not in by:
            needing: str = ", ".join(sorted(by))
            problems.append(f"{where}: {judgment['driver']} does not need the item; one of {needing} does")
        stack: EntryId | None = item_stack(matrix, item)
        owner, none = owner_decision(matrix, stack) if stack is not None else (None, False)
        if owner is not None or none:
            problems.append(f"{where}: the owner's decision for {stack} already decides the item")
    return problems


def record_judgments(matrix: Matrix, path: Path) -> Recorded:
    """Record every judgment of one file as a ``drives`` relationship, all of them or none.

    Each judgment becomes the one architecture-side ``drives`` with a basis that ends at its
    item, from the Epic that goes first, with its ``basis`` and ``reason``. A judgment by another
    Epic recorded earlier for the item is replaced. A change to the item later leaves the
    ``drives`` as it is.

    Args:
        matrix: The matrix, changed in place.
        path: The judgment file (``schemas/shared-item-judgments.schema.json``).

    Returns:
        Each relationship recorded, and each earlier judgment it replaced.

    Raises:
        MatrixRefusedError: The file breaks its schema, or a judgment breaks :func:`_problems`;
            nothing is recorded.
        MatrixError: An item is not an entry of the matrix.

    """
    judgments: list[Judgment] = read_judgments(path)
    missing: list[str] = [judgment["item"] for judgment in judgments if matrix.find(judgment["item"]) is None]
    if missing:
        message: str = f"the judgment file names items the matrix does not hold: {', '.join(missing)}"
        raise MatrixError(message)
    needed: dict[EntryId, dict[str, set[EntryId]]] = epic_needs(matrix)
    problems: list[str] = _problems(matrix, judgments, needed)
    if problems:
        raise MatrixRefusedError("; ".join(problems) + "; nothing is recorded")
    result: Recorded = {"file": str(path), "recorded": [], "replaced": []}
    for judgment in judgments:
        driver: EntryId = epic_id(judgment["driver"])
        earlier: Relationship
        for earlier in matrix.incoming(judgment["item"], (REL_DRIVES,)):
            if earlier.side == AUTHORITY_SIDE and ATTR_BASIS in earlier.attributes and earlier.start != driver:
                result["replaced"].append(
                    unlink(matrix, REL_DRIVES, earlier.start, earlier.end, AUTHORITY_SIDE)["relationship"],
                )
        attributes: dict[str, JsonValue] = {ATTR_BASIS: judgment["basis"], ATTR_REASON: judgment["reason"]}
        result["recorded"].append(
            link(matrix, REL_DRIVES, driver, judgment["item"], AUTHORITY_SIDE, attributes)["relationship"],
        )
    return result
