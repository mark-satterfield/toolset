"""What the review of one Epic is handed, and what a passed review approves.

Two rules with no judgment in them:

- :func:`open_review` (``unapproved``) lists exactly what is not approved for an Epic: the rows
  its PRD reaches or it recorded itself that are not approved, and the headings of the documents
  involved that are new, changed or removed against what was approved. It marks them in review
  for that Epic. Nothing that is approved is listed, so a reviewer is handed only what changed.
- :func:`approve` marks approved what is in review for the Epic, records each heading's hash as
  the approved one, releases the Epic's claims and, when nothing the PRD reaches is left
  unapproved, sets the PRD's coverage to approved.

What another Epic holds is not this Epic's to review or approve: it is reported and left alone.
"""

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    APPROVAL_APPROVED,
    APPROVAL_IN_REVIEW,
    BASIS_BUILT_CORRECTION,
    COVERAGE_APPROVED,
    COVERAGE_DESIGNED,
    COVERAGE_IN_PROGRESS,
    COVERAGE_NOT_ASSESSED,
    HEADING_CHANGED,
    HEADING_NEW,
    HEADING_REMOVED,
    KIND_DOCUMENT,
    KIND_PRD,
    LIFECYCLE_EFFECTIVE,
    LIFECYCLE_RETIRED,
    LINK_NEEDS,
    Anchor,
    Approval,
    ApprovalBasis,
    Claim,
    Coverage,
    HeadingChange,
    HeadingHash,
    HeldHeading,
    Matrix,
    Node,
    NodeId,
    ReviewScope,
    ScopeHeading,
    ScopeRow,
)
from matrixquery import reached_from
from matrixstore import MatrixRefusedError, Stamp, make_id, owner_of
from matrixsync import headings_match, placeholder

OPEN_COVERAGE: Final[frozenset[Coverage]] = frozenset({COVERAGE_NOT_ASSESSED, COVERAGE_IN_PROGRESS})
"""The coverage of a PRD whose design is not finished; opening its review makes it designed."""


class Remaining(TypedDict):
    """Something in review that could not be approved, and why."""

    id: NodeId
    reason: str


class Approved(TypedDict):
    """What :func:`approve` did: also what ``approve`` prints."""

    bead: str
    at: str
    steps: list[str]
    approved: list[NodeId]
    headings: list[Anchor]
    """Every heading whose present hash is now the approved one, and every approved removal."""
    remaining: list[Remaining]
    coverage: Coverage
    promoted: list[str]
    """The documents that are effective again, relative to the vault root."""
    claimsReleased: int


def _prd(matrix: Matrix, bead: str) -> Node:
    """Read the PRD row of an Epic.

    Returns:
        The row.

    Raises:
        MatrixRefusedError: The matrix has no PRD row for the Epic.

    """
    key: NodeId = make_id(KIND_PRD, bead)
    if not bead or key not in matrix["nodes"]:
        message: str = f"the matrix has no PRD row for {bead!r}; sync-prds writes it"
        raise MatrixRefusedError(message)
    return matrix["nodes"][key]


def _claimed_by(node: Node, bead: str) -> bool:
    """Tell whether an Epic claims a heading of a document row.

    Returns:
        True when one of the row's headings carries the Epic's claim.

    """
    return any(entry.get("claim", {}).get("bead") == bead for entry in node.get("headings", {}).values())


def _involved(matrix: Matrix, bead: str) -> list[Node]:
    """List the rows an Epic's review looks at.

    Returns:
        The rows the Epic's PRD reaches, the rows the Epic holds unapproved, and the documents
        with a heading the Epic claims; each once, in the order reached and then in id order.

    """
    keys: dict[NodeId, None] = dict.fromkeys(reached_from(matrix, make_id(KIND_PRD, bead)))
    key: NodeId
    for key in sorted(matrix["nodes"]):
        node: Node = matrix["nodes"][key]
        if owner_of(node) == bead or (node["kind"] == KIND_DOCUMENT and _claimed_by(node, bead)):
            keys.setdefault(key, None)
    return [matrix["nodes"][key] for key in keys]


def _change(entry: HeadingHash) -> HeadingChange | None:
    """Work out how one heading differs from what was approved.

    Returns:
        New for a heading never approved, removed for an approved heading the document no longer
        has, changed for one whose text differs, and None for one that is as approved or is only
        a claim on a heading still to be written.

    """
    if placeholder(entry) or entry["hash"] == entry["approvedHash"]:
        return None
    if entry["approvedHash"] is None:
        return HEADING_NEW
    return HEADING_CHANGED if entry["hash"] else HEADING_REMOVED


def _in_review(bead: str) -> Approval:
    """Build the marker of a row that is in review for an Epic.

    Returns:
        The marker.

    """
    return {"state": APPROVAL_IN_REVIEW, "bead": bead}


def _unapproved(node: Node) -> bool:
    """Tell whether a row carries the approval marker and is not approved.

    Returns:
        True for a row that is unverified, in review or changed since its approval.

    """
    return "approval" in node and node["approval"]["state"] != APPROVAL_APPROVED


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def review_scope(matrix: Matrix, bead: str, at: str) -> ReviewScope:
    """List exactly what is not approved for one Epic, and change nothing.

    An Epic with no PRD row in the matrix is refused with ``MatrixRefusedError``.

    Args:
        matrix: The matrix.
        bead: The Epic.
        at: The date-time to record on the scope.

    Returns:
        The rows that are not approved and are the Epic's to have reviewed, each with the state
        it has; the headings of the documents involved that are new, changed or removed against
        what was approved; and the differing headings another Epic claims. A row another Epic
        holds unapproved is left out.

    """
    prd: Node = _prd(matrix, bead)
    scope: ReviewScope = {
        "bead": bead,
        "at": at,
        "prd": prd["id"],
        "rows": [],
        "headings": [],
        "heldByOthers": [],
    }
    node: Node
    for node in _involved(matrix, bead):
        if node["kind"] != KIND_DOCUMENT:
            if _unapproved(node) and owner_of(node) in {"", bead}:
                row: ScopeRow = {
                    "id": node["id"],
                    "kind": node["kind"],
                    "name": node["name"],
                    "was": node["approval"]["state"],
                }
                if "home" in node:
                    row["home"] = node["home"]
                scope["rows"].append(row)
            continue
        if node.get("lifecycle") == LIFECYCLE_RETIRED:
            continue
        heading: str
        entry: HeadingHash
        for heading, entry in sorted(node.get("headings", {}).items()):
            change: HeadingChange | None = _change(entry)
            holder: str = entry.get("claim", {}).get("bead", bead)
            if change is None:
                continue
            if holder != bead:
                held: HeldHeading = {"document": node.get("path", ""), "heading": heading, "bead": holder}
                scope["heldByOthers"].append(held)
                continue
            listed: ScopeHeading = {"document": node.get("path", ""), "heading": heading, "change": change}
            scope["headings"].append(listed)
    return scope


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def open_review(matrix: Matrix, bead: str, claim: Claim, stamp: Stamp) -> ReviewScope:
    """List what is not approved for one Epic and mark it in review for that Epic.

    Every listed row becomes in review and names the Epic. Every listed heading is claimed for
    the Epic and its document becomes in review. A PRD whose design was not finished becomes
    designed. Running it again with nothing changed lists the same things.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic.
        claim: The claim to place on each listed heading: the Epic, its journal step, the moment.
        stamp: The moment and the maker to record on each changed row.

    Returns:
        The scope, as :func:`review_scope` lists it before anything is marked.

    """
    scope: ReviewScope = review_scope(matrix, bead, stamp.at)
    row: ScopeRow
    for row in scope["rows"]:
        node: Node = matrix["nodes"][row["id"]]
        if node.get("approval") != _in_review(bead):
            node["approval"] = _in_review(bead)
            node["changed"] = stamp.change()
    listed: ScopeHeading
    for listed in scope["headings"]:
        document: Node = matrix["nodes"][make_id(KIND_DOCUMENT, listed["document"])]
        entry: HeadingHash = document["headings"][listed["heading"]]
        if "claim" not in entry or document.get("approval") != _in_review(bead):
            entry.setdefault("claim", claim)
            document["approval"] = _in_review(bead)
            document["changed"] = stamp.change()
    prd: Node = _prd(matrix, bead)
    if prd.get("coverage") in OPEN_COVERAGE:
        prd["coverage"] = COVERAGE_DESIGNED
        prd["changed"] = stamp.change()
    return scope


def _home_reason(matrix: Matrix, node: Node) -> str:
    """Say why a row cannot be approved because of its home.

    Returns:
        The reason, or an empty string when the row has no home or its home heading is written.

    """
    if "home" not in node:
        return ""
    home: Anchor = node["home"]
    document: Node | None = matrix["nodes"].get(make_id(KIND_DOCUMENT, home["document"]))
    if document is None:
        return f"its home document {home['document']} is not a row; sync-documents reads it"
    entry: HeadingHash | None = document.get("headings", {}).get(home["heading"])
    if entry is None or not entry["hash"]:
        return f"{home['document']} has no heading {home['heading']!r}"
    return ""


def _approve_headings(node: Node, bead: str, result: Approved) -> None:
    """Record the present text of a document's headings as approved, and release the Epic's claims.

    A heading another Epic claims is left as it is. A removal is approved by dropping the
    heading's entry, and so is a claim on a heading that was never written.
    """
    headings: dict[str, HeadingHash] = node.get("headings", {})
    heading: str
    for heading in sorted(headings):
        entry: HeadingHash = headings[heading]
        holder: str = entry.get("claim", {}).get("bead", bead)
        if holder != bead:
            continue
        if "claim" in entry:
            del entry["claim"]
            result["claimsReleased"] += 1
        if entry["hash"] == entry["approvedHash"]:
            continue
        if entry["hash"]:
            entry["approvedHash"] = entry["hash"]
        else:
            del headings[heading]
        if not placeholder(entry):
            result["headings"].append({"document": node.get("path", ""), "heading": heading})


def _approve_row(matrix: Matrix, node: Node, basis: ApprovalBasis, result: Approved) -> None:
    """Approve one row that is in review, or record why it cannot be approved."""
    bead: str = result["bead"]
    reason: str = _home_reason(matrix, node)
    if node["kind"] == KIND_DOCUMENT:
        _approve_headings(node, bead, result)
        if not headings_match(node.get("headings", {})):
            reason = "a heading another Epic claims is not as it was approved"
        elif node.get("lifecycle") not in {LIFECYCLE_EFFECTIVE, LIFECYCLE_RETIRED}:
            node["lifecycle"] = LIFECYCLE_EFFECTIVE
            result["promoted"].append(node.get("path", ""))
    if reason:
        result["remaining"].append({"id": node["id"], "reason": reason})
        return
    node["approval"] = {
        "state": APPROVAL_APPROVED,
        "basis": basis,
        "bead": bead,
        "steps": list(result["steps"]),
        "at": result["at"],
    }
    if node.get("claim", {}).get("bead") == bead:
        del node["claim"]
        result["claimsReleased"] += 1
    result["approved"].append(node["id"])


def _release_claims(matrix: Matrix, stamp: Stamp, result: Approved) -> None:
    """Release the claims an Epic still holds on what is as it was approved.

    A claim on a row that is approved, on a heading that is as approved, and on a heading that
    was never written is given up. A claim on something that is still not approved is kept: it
    is still that Epic's to finish.
    """
    bead: str = result["bead"]
    key: NodeId
    for key in sorted(matrix["nodes"]):
        node: Node = matrix["nodes"][key]
        released: int = 0
        if node.get("claim", {}).get("bead") == bead and not _unapproved(node):
            del node["claim"]
            released += 1
        headings: dict[str, HeadingHash] = node.get("headings", {})
        heading: str
        for heading in sorted(headings):
            entry: HeadingHash = headings[heading]
            if entry.get("claim", {}).get("bead") != bead or _change(entry) is not None:
                continue
            del entry["claim"]
            released += 1
            if placeholder(entry):
                del headings[heading]
        if released:
            node["changed"] = stamp.change()
            result["claimsReleased"] += released


def _coverage(matrix: Matrix, prd: Node, bead: str) -> Coverage:
    """Work out the coverage of a PRD after an approval.

    Returns:
        Approved when the PRD needs at least one feature and nothing it reaches or its Epic
        recorded is left unapproved; otherwise the coverage it has.

    """
    needs: bool = any(link["type"] == LINK_NEEDS for link in prd["links"])
    pending: bool = any(_unapproved(node) for node in _involved(matrix, bead))
    return COVERAGE_APPROVED if needs and not pending else prd.get("coverage", COVERAGE_NOT_ASSESSED)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approve(matrix: Matrix, bead: str, steps: Sequence[str], basis: ApprovalBasis, stamp: Stamp) -> Approved:
    """Mark approved everything that is in review for one Epic.

    A row is approved with the basis, the Epic and the review steps. A document's headings take
    their present hash as the approved one, and a document that is wholly as approved is
    effective again; the caller writes that into the vault for each document in ``promoted``. A
    fact or a supporting feature whose home heading is not written is not approved and is
    reported. The Epic's claims are released. The PRD's coverage becomes approved when nothing
    it reaches or its Epic recorded is left unapproved. Something recorded after the review was
    opened is not in review, is not approved, and keeps the coverage from becoming approved.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic.
        steps: The journal step ids of the reviews that passed.
        basis: Why the approval is given.
        stamp: The moment and the maker to record on each changed row.

    Returns:
        What was approved, what remains and why, the coverage and the claims released.

    Raises:
        MatrixRefusedError: No review step is named, or the matrix has no PRD row for the Epic.

    """
    prd: Node = _prd(matrix, bead)
    named: list[str] = list(dict.fromkeys(step for step in steps if step.strip()))
    if not named:
        message: str = "an approval names the review steps that passed: give --steps"
        raise MatrixRefusedError(message)
    result: Approved = {
        "bead": bead,
        "at": stamp.at,
        "steps": named,
        "approved": [],
        "headings": [],
        "remaining": [],
        "coverage": prd.get("coverage", COVERAGE_NOT_ASSESSED),
        "promoted": [],
        "claimsReleased": 0,
    }
    documents_first: list[Node] = sorted(
        (node for node in matrix["nodes"].values() if node.get("approval") == _in_review(bead)),
        key=lambda node: (node["kind"] != KIND_DOCUMENT, node["id"]),
    )
    node: Node
    for node in documents_first:
        _approve_row(matrix, node, basis, result)
        node["changed"] = stamp.change()
    _release_claims(matrix, stamp, result)
    coverage: Coverage = _coverage(matrix, prd, bead)
    if coverage != prd.get("coverage"):
        prd["coverage"] = coverage
        prd["changed"] = stamp.change()
    result["coverage"] = coverage
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approve_built_correction(
    matrix: Matrix,
    bead: str,
    paths: Sequence[str],
    steps: Sequence[str],
    stamp: Stamp,
) -> Approved:
    """Mark approved the documents a reviewed correction from built code changed, and nothing else.

    Each named document's headings take their present hash as the approved one, except a
    heading another Epic claims; a document that is then wholly as approved is approved with
    the built-correction basis, the Epic and the review steps, and is effective again: the caller writes that
    into the vault for each document in ``promoted``. A named document the matrix holds no row
    for, and a document left with a heading another Epic claims, is reported in ``remaining``.
    No other row is approved and the PRD's coverage is left as it is.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic the documents were corrected for.
        paths: The documents, relative to the vault root.
        steps: The journal step ids of the reviews that passed.
        stamp: The moment and the maker to record on each changed row.

    Returns:
        What was approved and what remains and why; ``coverage`` is the PRD's as it stands.

    Raises:
        MatrixRefusedError: No Epic or no review step is named.

    """
    named: list[str] = list(dict.fromkeys(step for step in steps if step.strip()))
    if not bead.strip() or not named:
        message: str = "an approval of documents names the Epic and the review steps that passed"
        raise MatrixRefusedError(message)
    prd: Node | None = matrix["nodes"].get(make_id(KIND_PRD, bead))
    result: Approved = {
        "bead": bead,
        "at": stamp.at,
        "steps": named,
        "approved": [],
        "headings": [],
        "remaining": [],
        "coverage": COVERAGE_NOT_ASSESSED if prd is None else prd.get("coverage", COVERAGE_NOT_ASSESSED),
        "promoted": [],
        "claimsReleased": 0,
    }
    path: str
    for path in sorted(set(paths)):
        key: NodeId = make_id(KIND_DOCUMENT, path)
        node: Node | None = matrix["nodes"].get(key)
        if node is None or node["kind"] != KIND_DOCUMENT:
            result["remaining"].append({"id": key, "reason": "the matrix holds no row for the document"})
            continue
        _approve_row(matrix, node, BASIS_BUILT_CORRECTION, result)
        node["changed"] = stamp.change()
    return result
