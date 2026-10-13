"""The changes a session makes to the matrix while it designs: rows, links, claims, settlements.

Each function edits a loaded matrix in place and is run by ``matrix.py`` inside one locked
read-modify-write, so several sessions can record at once and none loses another's change.

- :func:`put` adds or changes one row. The schema's tables say which kinds a role may put and
  which fields a caller may state for each kind; everything else of a row is set here.
- :func:`link` adds or removes one link, stored once on the row it starts from.
- :func:`claim` marks a fact or a document heading as being changed by an Epic, so a second Epic
  that reaches for it is told who holds it and builds on that Epic's design.
- :func:`settle` records a disagreement between statements and how it was settled. A statement
  in approved text always stands over one that is not; the command decides that itself.
- :func:`note_sendback` records that a review sent a criterion back, on the Epic's PRD row.
- :func:`add_resource_type` extends the controlled list of resource types.

A row or link that is new or changed is not approved: its marker becomes unverified and names the
Epic that changed it, which is how that Epic's review (``matrixreview``) finds exactly what it
must be handed.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    APPROVAL_APPROVED,
    APPROVAL_UNVERIFIED,
    CODE_NONE,
    CODED_KINDS,
    COVERAGE_IN_PROGRESS,
    COVERAGE_NOT_ASSESSED,
    DISAGREEMENT_OPEN,
    DISAGREEMENT_SETTLED,
    ELEMENT_KINDS,
    FEATURE_PRD,
    FEATURE_SUPPORTING,
    KIND_DISAGREEMENT,
    KIND_DOCUMENT,
    KIND_FACT,
    KIND_FEATURE,
    KIND_PRD,
    KIND_STACK,
    KIND_TERM,
    LIFECYCLE_EFFECTIVE,
    LIFECYCLES,
    LINK_RULES,
    PLACED_KINDS,
    PUT_FIELDS,
    PUT_KINDS,
    RESOURCE_TYPE_PATTERN,
    SETTLE_RULES,
    Claim,
    DisagreementRule,
    DisputedStatement,
    HeadingHash,
    JsonValue,
    Kind,
    Link,
    Matrix,
    Node,
    NodeId,
    Role,
    is_statements,
    json_value,
    validate_node,
)
from matrixstore import MatrixRefusedError, Stamp, make_id, owner_of, unapprove

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

REPOSITORY_LEVEL: Final = "@repository"
"""The id part that stands for the stack of an element that lives in no stack, as carried rows have it."""
NAME_FIELD: Final = "name"
ENTRY_ID: Final = "id"
"""The key that identifies one entry of a list of objects, such as one thing a capability provides."""
MIN_STATEMENTS: Final = 2
SHOWN: Final = 3
"""The most ids a refusal names."""


@dataclass(frozen=True, slots=True)
class Actor:
    """Who makes a change: the role that runs the command, and the Epic and journal step it works for."""

    role: Role
    bead: str
    """The Epic the change is made for; empty for a change no Epic makes."""
    step: str
    """The journal step id of the session; empty when it has none."""
    at: str
    """The date-time of the change."""

    def __post_init__(self) -> None:
        """Refuse an actor with no moment.

        Raises:
            ValueError: ``at`` is empty.

        """
        if not self.at:
            message: str = "a change needs the moment it is made"
            raise ValueError(message)

    def stamp(self) -> Stamp:
        """Name the change for a row's ``changed`` record.

        Returns:
            The moment, and the Epic and step that make the change; the role when no Epic does.

        """
        return Stamp(self.at, " ".join(part for part in (self.bead, self.step) if part) or self.role)

    def claim(self) -> Claim:
        """Build the claim this actor's Epic places.

        Returns:
            The claim.

        Raises:
            MatrixRefusedError: The actor works for no Epic.

        """
        if not self.bead:
            message: str = "a claim needs the Epic that makes it: give --bead"
            raise MatrixRefusedError(message)
        return {"bead": self.bead, "step": self.step or self.role, "at": self.at}


@dataclass(frozen=True, slots=True)
class Put:
    """One row to add or change."""

    kind: Kind
    row: NodeId | None
    """The row's id; None derives it from the kind, the placement and the name."""
    stated: Mapping[str, JsonValue]
    """The row fields the caller states, by their name in the schema."""


@dataclass(frozen=True, slots=True)
class Settlement:
    """A disagreement and, unless it is recorded as open, how it is settled."""

    name: str
    row: NodeId | None
    """The id of the disagreement; None derives it from the name."""
    statements: Sequence[Mapping[str, JsonValue]]
    """The statements that disagree; empty when an existing disagreement is being settled."""
    rule: DisagreementRule | None
    """The rule that settles it; None records it as open."""
    stands: int | None
    """The number, from 1, of the statement that stands; None when the rule computes it."""
    reason: str
    evidence: Sequence[str]
    fact: NodeId | None
    """The fact that states what stands."""
    reopens: NodeId | None
    """The earlier disagreement a new requirement reopens."""


class PutResult(TypedDict):
    """What :func:`put` did."""

    id: NodeId
    created: bool
    changed: list[str]
    """The fields whose value the call changed; empty when the row was already as stated."""
    node: Node


class LinkResult(TypedDict):
    """What :func:`link` did."""

    source: NodeId
    link: Link
    added: bool
    removed: bool


class ClaimResult(TypedDict):
    """What :func:`claim` did."""

    id: NodeId
    heading: NotRequired[str]
    granted: bool
    """False when another Epic holds the claim; the claim returned is then that Epic's."""
    released: bool
    claim: NotRequired[Claim]
    standing: list[NodeId]
    """The unapproved rows of the Epic that holds the claim, which stand as the design to build on."""


class SettleResult(TypedDict):
    """What :func:`settle` did."""

    id: NodeId
    created: bool
    node: Node
    approved: list[bool]
    """For each statement, whether it is in approved text."""


class SendBackResult(TypedDict):
    """What :func:`note_sendback` did."""

    id: NodeId
    criterion: str
    sendBacks: int


class ResourceTypeResult(TypedDict):
    """What :func:`add_resource_type` did."""

    resourceType: str
    added: bool


def _copy(node: Node) -> dict[str, JsonValue]:
    """Copy a row as plain JSON, so stated fields can be laid over it and the result validated.

    Returns:
        The copy.

    Raises:
        TypeError: The row does not serialize to a JSON object.

    """
    copied: JsonValue = json_value(json.loads(json.dumps(node)))
    if not isinstance(copied, dict):
        message: str = "a row must be a JSON object"
        raise TypeError(message)
    return copied


def _row(matrix: Matrix, key: NodeId) -> Node:
    """Read a row a request names.

    Returns:
        The row.

    Raises:
        MatrixRefusedError: The matrix has no such row.

    """
    if key not in matrix["nodes"]:
        message: str = f"there is no row {key}"
        raise MatrixRefusedError(message)
    return matrix["nodes"][key]


def _text(stated: Mapping[str, JsonValue], field: str) -> str:
    """Read a stated field that must be nonempty text.

    Returns:
        The text; empty when the field was not stated or is not text.

    """
    value: JsonValue = stated.get(field)
    return value.strip() if isinstance(value, str) else ""


def _derived_id(request: Put) -> NodeId:
    """Build the id of a row from its kind, where it lives and its name.

    Returns:
        ``<kind>:<name>``; ``<kind>:<repository>/<name>`` for a stack; and
        ``<kind>:<repository>/<stack>/<name>`` for an element, with the repository level in
        place of the stack of an element that lives in none.

    Raises:
        MatrixRefusedError: The name, or the repository of a row that lives in one, is not stated.

    """
    name: str = _text(request.stated, NAME_FIELD)
    repository: str = _text(request.stated, "repository")
    message: str
    if not name:
        message = f"a {request.kind} row needs --name, or --id for a row that exists"
        raise MatrixRefusedError(message)
    if request.kind not in PLACED_KINDS:
        return make_id(request.kind, name)
    if not repository:
        message = f"a {request.kind} row lives in a repository: give --repository"
        raise MatrixRefusedError(message)
    if request.kind == KIND_STACK:
        return make_id(request.kind, repository, name)
    return make_id(request.kind, repository, _text(request.stated, "stack") or REPOSITORY_LEVEL, name)


def _new_row(key: NodeId, kind: Kind, stated: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Build what a new row of one kind holds before the caller's fields are laid over it.

    Returns:
        The row's id and kind, no links, and the markers and empty lists its kind carries: every
        design row is unverified, a row that can hold code holds none, an element is not shared
        until stated, and a supporting feature is shared and provides nothing yet.

    """
    row: dict[str, JsonValue] = {"id": key, "kind": kind, "links": []}
    if kind != KIND_TERM:
        row["approval"] = {"state": APPROVAL_UNVERIFIED}
    if kind in CODED_KINDS:
        row["code"] = {"state": CODE_NONE}
    if kind in ELEMENT_KINDS:
        row.update({"resourceType": None, "shared": False})
    if kind == KIND_FACT:
        row["linkedFrom"] = []
    if kind == KIND_FEATURE and stated.get("featureType") == FEATURE_SUPPORTING:
        row.update({"shared": True, "provides": []})
    if kind == KIND_FEATURE and stated.get("featureType") == FEATURE_PRD:
        row["requirements"] = []
    return row


def _joined(current: JsonValue, stated: JsonValue) -> JsonValue:
    """Lay one stated value over the value a row holds.

    Returns:
        The stated value; for a list, the held entries followed by the stated ones the row does
        not hold, where a stated object replaces the held object with the same ``id``.

    """
    if not isinstance(stated, list) or not isinstance(current, list):
        return stated
    joined: list[JsonValue] = list(current)
    entry: JsonValue
    for entry in stated:
        identity: JsonValue = entry.get(ENTRY_ID) if isinstance(entry, dict) else None
        at: int | None = next(
            (
                index
                for index, held in enumerate(joined)
                if (isinstance(held, dict) and identity is not None and held.get(ENTRY_ID) == identity) or held == entry
            ),
            None,
        )
        if at is None:
            joined.append(entry)
        else:
            joined[at] = entry
    return joined


def _require_put(request: Put, actor: Actor) -> None:
    """Refuse a put the schema's tables do not allow.

    Raises:
        MatrixRefusedError: The role may not put a row of that kind, or the caller states a field
            a row of that kind does not take.

    """
    allowed: frozenset[Kind] = PUT_KINDS.get(actor.role, frozenset())
    message: str
    if request.kind not in allowed:
        owners: list[str] = sorted(role for role, kinds in PUT_KINDS.items() if request.kind in kinds)
        message = f"the role {actor.role} may not put a {request.kind} row; " + (
            f"it is for {', '.join(owners)}" if owners else "no put writes that kind"
        )
        raise MatrixRefusedError(message)
    stray: list[str] = sorted(set(request.stated) - PUT_FIELDS[request.kind])
    if stray:
        message = f"a {request.kind} row does not take {', '.join(stray)}"
        raise MatrixRefusedError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def put(matrix: Matrix, request: Put, actor: Actor) -> PutResult:
    """Add one row, or change the stated fields of a row that exists.

    A list field is added to, never replaced: stated aliases, requirements, linking documents
    and ``provides`` entries join the ones held, and a ``provides`` entry with the id of a held
    one replaces it. A row that is created or changed is unverified and names the actor's Epic.
    A call that states what the row already holds changes nothing.

    Args:
        matrix: The matrix, changed in place.
        request: The kind, the id when known, and the fields stated.
        actor: Who makes the change.

    Returns:
        The row's id, whether it was created, the fields changed and the row.

    Raises:
        MatrixRefusedError: The role may not put the kind, a field does not belong to it, the id
            names a row of another kind, or the stated fields do not make a row of that kind.

    """
    _require_put(request, actor)
    key: NodeId = request.row or _derived_id(request)
    existing: Node | None = matrix["nodes"].get(key)
    message: str
    if existing is not None and existing["kind"] != request.kind:
        message = f"{key} is a {existing['kind']} row, not a {request.kind} row"
        raise MatrixRefusedError(message)
    row: dict[str, JsonValue] = _new_row(key, request.kind, request.stated) if existing is None else _copy(existing)
    changed: list[str] = []
    field: str
    value: JsonValue
    for field, value in request.stated.items():
        merged: JsonValue = _joined(row.get(field), value)
        if field not in row or merged != row[field]:
            row[field] = merged
            changed.append(field)
    if existing is not None and not changed:
        return {"id": key, "created": False, "changed": [], "node": existing}
    row["changed"] = {"at": actor.at, "by": actor.stamp().by}
    node: Node = validate_node(row, f"the {request.kind} row {key}")
    unapprove(node, actor.bead, actor.stamp())
    matrix["nodes"][key] = node
    return {"id": key, "created": existing is None, "changed": sorted(changed), "node": node}


def _same_link(held: Link, wanted: Link) -> bool:
    """Tell whether two links are the same relationship.

    Returns:
        True when they have the same type, target and heading.

    """
    return (
        held["type"] == wanted["type"]
        and held["to"] == wanted["to"]
        and held.get("heading", "") == wanted.get("heading", "")
    )


def _merged_link(held: Link, wanted: Link) -> Link:
    """Join a link a row holds with the same link stated again.

    Returns:
        The held link with the stated ``provides`` entries added and the stated ambiguity.

    """
    merged: Link = {"type": held["type"], "to": held["to"]}
    if "heading" in held:
        merged["heading"] = held["heading"]
    relied: list[str] = list(dict.fromkeys([*held.get("provides", []), *wanted.get("provides", [])]))
    if relied:
        merged["provides"] = relied
    if wanted.get("ambiguous", held.get("ambiguous", False)):
        merged["ambiguous"] = True
    return merged


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def link(matrix: Matrix, source: NodeId, wanted: Link, actor: Actor, *, remove: bool = False) -> LinkResult:
    """Add one link to the row it starts from, or remove it.

    A link is the same link when its type, target and heading are the same; stating it again
    adds to the ``provides`` entries it relies on. A row whose links change is unverified again
    and names the actor's Epic; a PRD row that gains a link is in progress.

    Args:
        matrix: The matrix, changed in place.
        source: The row the link starts from.
        wanted: The link.
        actor: Who makes the change.
        remove: Whether to remove the link instead of adding it.

    Returns:
        The source, the link as the row now holds it, and whether it was added or removed.

    Raises:
        MatrixRefusedError: A row is missing, or the link type may not join the two kinds.

    """
    node: Node = _row(matrix, source)
    target: Node = _row(matrix, wanted["to"])
    if (
        node["kind"] not in LINK_RULES[wanted["type"]].sources
        or target["kind"] not in LINK_RULES[wanted["type"]].targets
    ):
        message: str = f"a {wanted['type']} link may not join a {node['kind']} row to a {target['kind']} row"
        raise MatrixRefusedError(message)
    at: int | None = next((index for index, held in enumerate(node["links"]) if _same_link(held, wanted)), None)
    stored: Link = wanted if at is None else _merged_link(node["links"][at], wanted)
    result: LinkResult = {"source": source, "link": stored, "added": False, "removed": False}
    if remove and at is not None:
        del node["links"][at]
        result["removed"] = True
    elif not remove and at is None:
        node["links"].append(wanted)
        result["added"] = True
    elif not remove and at is not None and stored != node["links"][at]:
        node["links"][at] = stored
        result["added"] = True
    if result["added"] or result["removed"]:
        unapprove(node, actor.bead, actor.stamp())
        if node["kind"] == KIND_PRD and node.get("coverage") == COVERAGE_NOT_ASSESSED:
            node["coverage"] = COVERAGE_IN_PROGRESS
    return result


def _held_rows(matrix: Matrix, bead: str, document: str, heading: str) -> list[NodeId]:
    """List the unapproved rows one Epic has recorded at one heading.

    Returns:
        The ids of that Epic's unapproved rows whose home is the heading, in id order.

    """
    return sorted(
        node["id"]
        for node in matrix["nodes"].values()
        if owner_of(node) == bead
        and "home" in node
        and node["home"]["document"] == document
        and node["home"]["heading"] == heading
    )


def _claim_heading(matrix: Matrix, node: Node, heading: str, actor: Actor, *, release: bool) -> ClaimResult:
    """Claim or release one heading of a document row.

    Returns:
        What the claim did.

    """
    headings: dict[str, HeadingHash] = node.setdefault("headings", {})
    entry: HeadingHash = headings.setdefault(heading, {"hash": "", "approvedHash": None})
    wanted: Claim = actor.claim()
    held: Claim | None = entry.get("claim")
    result: ClaimResult = {"id": node["id"], "heading": heading, "granted": True, "released": False, "standing": []}
    if held is not None and held["bead"] != wanted["bead"]:
        result.update({"granted": False, "claim": held})
        result["standing"] = _held_rows(matrix, held["bead"], node.get("path", ""), heading)
        return result
    if release:
        entry.pop("claim", None)
        if not entry["hash"] and entry["approvedHash"] is None:
            del headings[heading]
        result["released"] = held is not None
        return result
    result["claim"] = held or wanted
    if held is None:
        entry["claim"] = wanted
        node["changed"] = actor.stamp().change()
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def claim(
    matrix: Matrix,
    target: NodeId,
    heading: str | None,
    actor: Actor,
    *,
    release: bool = False,
) -> ClaimResult:
    """Mark a fact, a feature or a document heading as being changed by the actor's Epic.

    A claim another Epic holds is not taken: the call reports that Epic's claim and the
    unapproved rows it has recorded there, which stand as the design to build on. A claim on a
    heading that is still to be written is kept until the heading is approved. ``approve``
    releases an Epic's claims; ``release`` gives one up without an approval.

    Args:
        matrix: The matrix, changed in place.
        target: The fact or feature row, or the document row whose heading is claimed.
        heading: The heading of a document row; None for a fact or a feature.
        actor: Who claims; it must work for an Epic.
        release: Whether to give the actor's own claim up.

    Returns:
        Whether the claim is the actor's, the claim that stands, and the holder's unapproved rows.

    Raises:
        MatrixRefusedError: The row is missing, cannot be claimed, or a document row is given
            without a heading or another row with one.

    """
    node: Node = _row(matrix, target)
    message: str
    if node["kind"] == KIND_DOCUMENT:
        if not heading:
            message = "a claim on a document names the heading: give --heading"
            raise MatrixRefusedError(message)
        return _claim_heading(matrix, node, heading, actor, release=release)
    if heading or node["kind"] not in {KIND_FACT, KIND_FEATURE}:
        message = f"a claim is placed on a fact, a feature or a document heading, not on {target}"
        raise MatrixRefusedError(message)
    wanted: Claim = actor.claim()
    held: Claim | None = node.get("claim")
    result: ClaimResult = {"id": target, "granted": True, "released": False, "standing": []}
    if held is not None and held["bead"] != wanted["bead"]:
        result.update({"granted": False, "claim": held})
        result["standing"] = [target] if owner_of(node) == held["bead"] else []
        return result
    if release:
        node.pop("claim", None)
        result["released"] = held is not None
        return result
    result["claim"] = held or wanted
    if held is None:
        node["claim"] = wanted
        node["changed"] = actor.stamp().change()
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def statement_approved(matrix: Matrix, statement: DisputedStatement) -> bool:
    """Tell whether a statement is in approved text.

    A statement in a document the matrix holds is approved when the document is effective and
    the heading it is under is as it was approved; when the heading named is not one the
    document row records, the document must be effective and approved as a whole. A statement
    in a document the matrix does not hold is approved when it is stated to be effective.

    Args:
        matrix: The matrix.
        statement: The statement.

    Returns:
        True when the statement is approved.

    """
    document: Node | None = matrix["nodes"].get(make_id(KIND_DOCUMENT, statement["document"]))
    if document is None:
        return statement["lifecycle"] == LIFECYCLE_EFFECTIVE
    if document.get("lifecycle") != LIFECYCLE_EFFECTIVE:
        return False
    entry: HeadingHash | None = document.get("headings", {}).get(statement["heading"])
    if entry is None:
        return "approval" in document and document["approval"]["state"] == APPROVAL_APPROVED
    return bool(entry["hash"]) and entry["hash"] == entry["approvedHash"]


def _statements(matrix: Matrix, stated: Sequence[Mapping[str, JsonValue]]) -> list[DisputedStatement]:
    """Read the statements of a disagreement as the caller gives them.

    Returns:
        The statements, each with the lifecycle of its document as the matrix holds it, and with
        no ruling on which stands.

    Raises:
        MatrixRefusedError: A statement lacks a field, or names a document the matrix does not
            hold without stating that document's lifecycle.

    """
    read: list[dict[str, JsonValue]] = []
    index: int
    given: Mapping[str, JsonValue]
    message: str
    for index, given in enumerate(stated, start=1):
        entry: dict[str, JsonValue] = {key: value for key, value in given.items() if key != "stands"}
        path: JsonValue = entry.get("document")
        document: Node | None = matrix["nodes"].get(make_id(KIND_DOCUMENT, path)) if isinstance(path, str) else None
        if document is not None and "lifecycle" in document:
            entry["lifecycle"] = document["lifecycle"]
        if entry.get("lifecycle") not in LIFECYCLES:
            message = f"statement {index} is in a document the matrix does not hold: state its lifecycle"
            raise MatrixRefusedError(message)
        read.append(entry)
    if not is_statements(read):
        message = "each statement needs its document, its heading and its text, and may give its line"
        raise MatrixRefusedError(message)
    return read


def _standing(settlement: Settlement, approved: Sequence[bool], actor: Actor) -> int:
    """Decide which statement stands under the rule a settlement names.

    Returns:
        The index, from 0, of the statement that stands.

    Raises:
        MatrixRefusedError: No rule is named, the role may not settle by the rule, the rule that
            computes its outcome does not have exactly one approved statement to choose, or a
            statement that is not approved is put over one that is.

    """
    message: str
    if settlement.rule is None:
        message = "a settlement names its rule"
        raise MatrixRefusedError(message)
    rule: DisagreementRule = settlement.rule
    if actor.role not in SETTLE_RULES[rule].roles:
        message = f"the role {actor.role} may not settle by {rule}; it is for " + ", ".join(
            sorted(SETTLE_RULES[rule].roles),
        )
        raise MatrixRefusedError(message)
    winners: list[int] = [index for index, holds in enumerate(approved) if holds]
    computed: str = next(name for name, entry in SETTLE_RULES.items() if entry.computed)
    chosen: int | None = None if settlement.stands is None else settlement.stands - 1
    if SETTLE_RULES[rule].computed:
        if len(winners) != 1:
            message = f"{rule} decides nothing here: {len(winners)} of {len(approved)} statements are approved"
            raise MatrixRefusedError(message)
        if chosen not in {None, winners[0]}:
            message = f"statement {winners[0] + 1} is the approved one; it stands, whatever --stands says"
            raise MatrixRefusedError(message)
        return winners[0]
    if chosen is None or not 0 <= chosen < len(approved):
        message = f"give --stands with the number of the statement that stands, from 1 to {len(approved)}"
        raise MatrixRefusedError(message)
    if len(winners) == 1 and len(approved) > 1:
        message = f"statement {winners[0] + 1} is approved and the others are not: it stands; settle with {computed}"
        raise MatrixRefusedError(message)
    if winners and chosen not in winners:
        message = f"statement {chosen + 1} is not approved and cannot stand over an approved statement"
        raise MatrixRefusedError(message)
    return chosen


def _disagreement(matrix: Matrix, settlement: Settlement, actor: Actor) -> tuple[Node, bool]:
    """Find the disagreement a settlement names, or make its row.

    Returns:
        The row, with the statements the settlement gives when it gives any, and whether the
        row is new. A new row is not in the matrix yet.

    Raises:
        MatrixRefusedError: The id names a row that is no disagreement, or a new disagreement
            has fewer than two statements.

    """
    key: NodeId = settlement.row or make_id(KIND_DISAGREEMENT, settlement.name)
    existing: Node | None = matrix["nodes"].get(key)
    message: str
    if existing is not None and existing["kind"] != KIND_DISAGREEMENT:
        message = f"{key} is a {existing['kind']} row, not a disagreement"
        raise MatrixRefusedError(message)
    statements: list[DisputedStatement] = _statements(matrix, settlement.statements)
    if existing is not None:
        if statements:
            existing["statements"] = statements
        return existing, False
    if len(statements) < MIN_STATEMENTS or not settlement.name.strip():
        message = "a new disagreement needs its name and at least two statements"
        raise MatrixRefusedError(message)
    created: Node = {
        "id": key,
        "kind": KIND_DISAGREEMENT,
        "name": settlement.name.strip(),
        "links": [],
        "changed": actor.stamp().change(),
        "statements": statements,
        "disagreementStatus": DISAGREEMENT_OPEN,
    }
    return created, True


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def settle(matrix: Matrix, settlement: Settlement, actor: Actor) -> SettleResult:
    """Record a disagreement between statements and, unless it is recorded as open, its settlement.

    A statement in approved text stands over one that is not, without discussion: when exactly
    one statement is approved, only the rule that computes its outcome is accepted, and it names
    the approved statement itself. When the statements are all approved, or none is, that rule
    decides nothing and is refused; the caller names the rule that decided and the statement
    that stands. The row keeps each statement marked as standing or lost, the rule, the reason,
    the evidence and the fact that now stands, so the question is not asked again.

    Args:
        matrix: The matrix, changed in place.
        settlement: The statements and the settlement.
        actor: Who settles.

    Returns:
        The row's id, whether it was created, the row, and whether each statement is approved.

    Raises:
        MatrixRefusedError: The settlement is refused by :func:`_standing`, or names a fact or an
            earlier disagreement that is not a row of that kind.

    """
    node: Node
    created: bool
    node, created = _disagreement(matrix, settlement, actor)
    statements: list[DisputedStatement] = node.get("statements", [])
    approved: list[bool] = [statement_approved(matrix, statement) for statement in statements]
    named: NodeId | None
    kind: Kind
    for named, kind in ((settlement.fact, KIND_FACT), (settlement.reopens, KIND_DISAGREEMENT)):
        if named is not None and _row(matrix, named)["kind"] != kind:
            message: str = f"{named} is not a {kind} row"
            raise MatrixRefusedError(message)
    if settlement.rule is not None:
        winner: int = _standing(settlement, approved, actor)
        index: int
        statement: DisputedStatement
        for index, statement in enumerate(statements):
            statement["stands"] = index == winner
        node["rule"] = settlement.rule
        node["disagreementStatus"] = DISAGREEMENT_SETTLED
        node["settledBy"] = actor.stamp().by
    if settlement.reason:
        node["reason"] = settlement.reason
    if settlement.evidence:
        node["evidence"] = list(dict.fromkeys([*node.get("evidence", []), *settlement.evidence]))
    if settlement.fact is not None:
        node["standingFact"] = settlement.fact
    if settlement.reopens is not None:
        node["reopens"] = settlement.reopens
    node["approval"] = {"state": APPROVAL_UNVERIFIED}
    unapprove(node, actor.bead, actor.stamp())
    matrix["nodes"][node["id"]] = node
    return {"id": node["id"], "created": created, "node": node, "approved": approved}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def note_sendback(matrix: Matrix, criterion: str, actor: Actor) -> SendBackResult:
    """Record on an Epic's PRD row that a review sent a criterion back.

    Args:
        matrix: The matrix, changed in place.
        criterion: The id of the criterion.
        actor: The lead that records it; it must work for an Epic.

    Returns:
        The PRD row's id, the criterion and how many send-backs the row now holds.

    Raises:
        MatrixRefusedError: The criterion is empty, or the Epic has no PRD row.

    """
    message: str
    if not criterion.strip() or not actor.bead:
        message = "a send-back names its criterion and its Epic: give --criterion and --bead"
        raise MatrixRefusedError(message)
    key: NodeId = make_id(KIND_PRD, actor.bead)
    if key not in matrix["nodes"]:
        message = f"the matrix has no PRD row for {actor.bead}; sync-prds writes it"
        raise MatrixRefusedError(message)
    node: Node = matrix["nodes"][key]
    step: str = actor.step or actor.role
    held: bool = any(
        entry["criterion"] == criterion.strip() and entry["step"] == step for entry in node.get("sendBacks", [])
    )
    if not held:
        node.setdefault("sendBacks", []).append({"criterion": criterion.strip(), "step": step, "at": actor.at})
        node["changed"] = actor.stamp().change()
    return {"id": key, "criterion": criterion.strip(), "sendBacks": len(node.get("sendBacks", []))}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def add_resource_type(matrix: Matrix, name: str) -> ResourceTypeResult:
    """Add one value to the controlled list of resource types.

    Args:
        matrix: The matrix, changed in place.
        name: The resource type, in lower case with hyphens.

    Returns:
        The resource type and whether it was added; False when the list already holds it.

    Raises:
        MatrixRefusedError: The name does not have the form of a resource type.

    """
    if RESOURCE_TYPE_PATTERN.search(name) is None:
        message: str = f"{name!r} is not a resource type: it must match {RESOURCE_TYPE_PATTERN.pattern}"
        raise MatrixRefusedError(message)
    if name in matrix["resourceTypes"]:
        return {"resourceType": name, "added": False}
    matrix["resourceTypes"] = sorted([*matrix["resourceTypes"], name])
    return {"resourceType": name, "added": True}
