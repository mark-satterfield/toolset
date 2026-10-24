"""What one Epic's architect reviewed, and whether another Epic changed any of it before the promotion.

Two Epics that rest on the same unapproved decision are ordered by a beads ``tracks`` edge. When the
edge is missing, both can review and change the same entries and documents at once; the one that
promotes second would approve, set effective and commit what the other changed. The promotion
detects that collision here, under the matrix's lock, before it changes anything.

What the review covered is recorded in ``reviewed.json`` beside the context file:

- each time the architect's result is accepted: every entry of the Epic's approval scope, with its
  content hash (``matrixtraverse.entry_content_hash``) and its approved owner, as the matrix holds
  it once the change file and the result are recorded; and each heading of each document this
  Epic's maintainers wrote, with the hash of its own text (``matrixsync.parse_document``);
- each time a maintainer the script ran is accepted: the headings of the documents it wrote.

A collision is one of these, each named with the other Epic or the Epics that could be it:

- an entry of the approval scope whose content hash differs from the one recorded, or whose
  approved flag names an Epic other than this one and the one recorded;
- an unapproved entry in the approval scope that the record does not hold;
- an entry the architect kept as the pack listed it, whose recorded hash or owner differs from the
  pack's: another Epic changed or approved it while this Epic's architect worked;
- a document to be set effective whose heading hashes differ from those recorded.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import VERDICT_KEPT
from matrix_contract import AUTHORITY_SIDE, KIND_DOCUMENT, KIND_EPIC, KIND_FEATURE, REL_DESCRIBED_BY
from matrixstore import as_entry_id, make_id, read_matrix
from matrixsync import parse_document
from matrixtraverse import (
    approval_scope,
    entry_content_hash,
    epic_id,
    rule_reach,
)

from orchestrator.core.handback_contract import MISSING_EDGE_CAUSE
from orchestrator.core.io import write_json
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import (
    PACK_FILE,
    REVIEWED_FILE,
    architecture_folder,
    matrix_file,
    written_documents,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from architecture_work_contract import ArchitectureResult
    from matrix_contract import Entry, EntryId
    from matrixstore import Matrix
    from matrixtraverse import ApprovalScope, RuleReach

    from orchestrator.core.io import JsonValue
    from orchestrator.core.journal_steps import StepRun


NAMED_OTHERS: Final = 10
"""How many of the Epics that could be the other Epic one line of evidence names."""


class ReviewedEntry(TypedDict):
    """One entry of the approval scope as the review left it."""

    contentHash: str
    approved: str | None


class Reviewed(TypedDict):
    """What ``reviewed.json`` holds."""

    epic: str
    entries: dict[str, ReviewedEntry]
    documents: dict[str, dict[str, str]]
    """Each document this Epic's maintainers wrote, by its path under the architecture root, with
    the hash of each heading's own text."""


@dataclass(frozen=True)
class Collision:
    """One entry or document another Epic changed or approved after this Epic reviewed it."""

    item: str
    """The entry id, or the document by its path under the architecture root."""
    what: str
    """What happened to it, as one sentence."""
    others: tuple[str, ...]
    """The other Epic, or the Epics that reach it and could be the other Epic."""


def _owner(entry: Entry) -> str | None:
    """Name the Epic an entry's approved flag names.

    Returns:
        Its beads id; None when the entry is not approved.

    """
    return None if entry.approved is None else entry.approved.epic


def scope_record(bead: str) -> dict[str, ReviewedEntry]:
    """Record each entry of an Epic's approval scope as the matrix holds it now.

    Returns:
        Each entry's id with its content hash and its approved owner.

    """
    matrix: Matrix = read_matrix(matrix_file())
    scope: ApprovalScope = approval_scope(matrix, epic_id(bead))
    recorded: dict[str, ReviewedEntry] = {}
    entry_id: EntryId
    for entry_id in scope.entries:
        entry: Entry = matrix.entry(entry_id)
        recorded[entry_id] = {"contentHash": entry_content_hash(entry), "approved": _owner(entry)}
    return recorded


def heading_digests(arch: Path, relative: str) -> dict[str, str]:
    """Hash each heading's own text of one document as the working tree holds it.

    Returns:
        Each heading with the hash of its own text; none when the document is gone.

    """
    path: Path = arch / relative
    if not path.is_file():
        return {}
    return parse_document(relative, path.read_text(encoding="utf-8")).heading_digests


def _read(folder: Path, bead: str) -> Reviewed:
    """Read ``reviewed.json``.

    Returns:
        What it holds; an empty record when there is none or it is not a record of this Epic.

    """
    path: Path = folder / REVIEWED_FILE
    empty: Reviewed = {"epic": bead, "entries": {}, "documents": {}}
    if not path.is_file():
        return empty
    held: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(held, dict) or held.get("epic") != bead:
        return empty
    entries: object = held.get("entries")
    documents: object = held.get("documents")
    return {
        "epic": bead,
        "entries": entries if isinstance(entries, dict) else {},
        "documents": documents if isinstance(documents, dict) else {},
    }


def record_review(run: StepRun, arch: Path) -> None:
    """Record what the Epic's architect reviewed, once its result is accepted.

    Every entry of the approval scope is recorded as the matrix holds it now, and every document
    this Epic's maintainers wrote with its heading hashes as the working tree holds it now.
    """
    bead: str = str(run.bead)
    entries: dict[str, ReviewedEntry] = run.tools.portfolio(run.inputs.stage, scope_record, bead)
    documents: dict[str, dict[str, str]] = {
        relative: heading_digests(arch, relative) for relative in written_documents(run, arch)
    }
    record: Reviewed = {"epic": bead, "entries": entries, "documents": documents}
    write_json(architecture_folder(run.context.work) / REVIEWED_FILE, record)


def record_written(run: StepRun, arch: Path, paths: Sequence[str]) -> None:
    """Record the heading hashes of the documents a maintainer the script ran has written."""
    folder: Path = architecture_folder(run.context.work)
    record: Reviewed = _read(folder, str(run.bead))
    record["documents"] = {**record["documents"], **{relative: heading_digests(arch, relative) for relative in paths}}
    write_json(folder / REVIEWED_FILE, record)


@dataclass(frozen=True)
class Baseline:
    """What a promotion compares the matrix and the documents with."""

    reviewed: Reviewed
    pack: Mapping[str, ReviewedEntry]
    """Each entry the pack listed, with the hash and owner it listed."""
    kept: frozenset[str]
    """The entries the architect's result kept as the pack listed them."""


def baseline(work: Path, bead: str, result: ArchitectureResult) -> Baseline:
    """Read what the promotion of an Epic compares with.

    Returns:
        The review record, the pack's hashes and owners, and the entries the result kept.

    """
    folder: Path = architecture_folder(work)
    listed: dict[str, ReviewedEntry] = {}
    pack: Path = folder / PACK_FILE
    if pack.is_file():
        held: object = json.loads(pack.read_text(encoding="utf-8"))
        rows: object = held.get("reach") if isinstance(held, dict) else None
        row: object
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("contentHash"), str):
                owner: JsonValue = row.get("approved")
                approved: str | None = owner if isinstance(owner, str) else None
                listed[row["id"]] = {"contentHash": row["contentHash"], "approved": approved}
    kept: frozenset[str] = frozenset(verdict["id"] for verdict in result["reach"] if verdict["verdict"] == VERDICT_KEPT)
    return Baseline(reviewed=_read(folder, bead), pack=listed, kept=kept)


def _entry_collision(bead: str, entry: Entry, recorded: ReviewedEntry | None) -> str | None:
    """Tell what happened to one entry of the approval scope since the review recorded it.

    Returns:
        One sentence; None when nothing did.

    """
    owner: str | None = _owner(entry)
    if recorded is None:
        return "entered the reach after the review" if owner is None else None
    if owner not in {None, bead, recorded["approved"]}:
        return f"was approved by {owner} after the review"
    if entry_content_hash(entry) != recorded["contentHash"]:
        return "changed after the review"
    return None


def _kept_collision(bead: str, recorded: ReviewedEntry, listed: ReviewedEntry) -> str | None:
    """Tell what happened to an entry the architect kept as the pack listed it, while it worked.

    Returns:
        One sentence; None when nothing did.

    """
    if recorded["approved"] not in {None, bead, listed["approved"]}:
        return f"was approved by {recorded['approved']} while this Epic's architect reviewed it"
    if recorded["contentHash"] != listed["contentHash"]:
        return "changed while this Epic's architect reviewed it, and the architect kept it as the pack listed it"
    return None


def _reaches(matrix: Matrix, bead: str) -> dict[str, set[EntryId]]:
    """Walk every other Epic by the rule of reach.

    Returns:
        Each other Epic's beads id with every entry it reaches.

    """
    found: dict[str, set[EntryId]] = {}
    other: Entry
    for other in matrix.entries((KIND_EPIC,)):
        name: str = other.id.removeprefix(f"{KIND_EPIC}:")
        if name != bead:
            reach: RuleReach = rule_reach(matrix, other.id)
            found[name] = {*reach.requirements, *reach.features, *reach.ids()}
    return found


def _named_others(
    matrix: Matrix,
    bead: str,
    entries: Sequence[EntryId],
    documents: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    """Name the Epics that could be the other Epic of each collision no approved flag names.

    An entry's are the other Epics whose rule of reach holds it; a document's are those whose rule
    of reach holds an entry one of its headings describes.

    Returns:
        Each entry id and each document path with those Epics' beads ids, in id order.

    """
    reaches: dict[str, set[EntryId]] = _reaches(matrix, bead)
    wanted: dict[str, set[EntryId]] = {entry_id: {entry_id} for entry_id in entries}
    relative: str
    for relative in documents:
        document: EntryId = make_id(KIND_DOCUMENT, relative)
        wanted[relative] = {
            describing.start
            for describing in matrix.incoming(document, (REL_DESCRIBED_BY,))
            if describing.side == AUTHORITY_SIDE and matrix.entry(describing.start).kind != KIND_FEATURE
        }
    return {
        item: tuple(sorted(name for name, reached in reaches.items() if items & reached))
        for item, items in wanted.items()
    }


def collisions(matrix: Matrix, bead: str, arch: Path, documents: Sequence[str], held: Baseline) -> list[Collision]:
    """Find every entry and document another Epic changed or approved after this Epic reviewed it.

    Returns:
        One collision per entry or document, entries first in id order, then documents in path
        order; none when no record was ever made (a promotion with nothing to compare with).

    """
    if not held.reviewed["entries"] and not held.reviewed["documents"]:
        return []
    scope: ApprovalScope = approval_scope(matrix, epic_id(bead))
    found: list[tuple[str, str, tuple[str, ...]]] = []
    entry_id: EntryId
    for entry_id in scope.entries:
        entry: Entry = matrix.entry(entry_id)
        recorded: ReviewedEntry | None = held.reviewed["entries"].get(entry_id)
        listed: ReviewedEntry | None = held.pack.get(entry_id)
        what: str | None = _entry_collision(bead, entry, recorded)
        if what is None and recorded is not None and listed is not None and entry_id in held.kept:
            what = _kept_collision(bead, recorded, listed)
        if what is not None:
            owner: str | None = _owner(entry)
            found.append((entry_id, what, () if owner in {None, bead} else (str(owner),)))
    for relative in documents:
        recorded_headings: dict[str, str] | None = held.reviewed["documents"].get(relative)
        if recorded_headings is not None and heading_digests(arch, relative) != recorded_headings:
            found.append((relative, "changed after this Epic's maintainer wrote it", ()))
    entries: list[EntryId] = [as_entry_id(item) for item, _, others in found if not others and item in scope.via]
    paths: list[str] = [item for item, _, others in found if not others and item not in scope.via]
    named: dict[str, tuple[str, ...]] = _named_others(matrix, bead, entries, paths) if entries or paths else {}
    return [Collision(item=item, what=what, others=others or named.get(item, ())) for item, what, others in found]


def evidence(bead: str, found: Sequence[Collision]) -> tuple[str, ...]:
    """State each collision as one line of the failure's evidence.

    Returns:
        One line per collision, naming the item, what happened and the other Epic.

    """
    lines: list[str] = []
    collision: Collision
    for collision in found:
        shown: tuple[str, ...] = collision.others[:NAMED_OTHERS]
        more: int = len(collision.others) - len(shown)
        others: str = ", ".join(shown) + (f" and {more} more Epics that reach it" if more else "")
        others = others or "an Epic not named in the matrix"
        lines.append(f"missing edge: {collision.item} {collision.what}; other Epic: {others}")
    lines.append(
        f"{bead} rests on what another Epic changed without a tracks edge between them: its assessment is "
        "re-run and its architecture is reviewed again from the pack",
    )
    return tuple(lines)


class MissingEdgeError(StepError):
    """The promotion found collisions: another Epic changed or approved what this Epic reviewed."""

    def __init__(self, stage: str, bead: str, found: Sequence[Collision]) -> None:
        """State each collision as evidence, with the cause ``missing-edge``."""
        super().__init__(stage, MISSING_EDGE_CAUSE, evidence(bead, found))
        self.found: tuple[Collision, ...] = tuple(found)
