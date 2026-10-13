"""Bring the matrix up to date with the vault's architecture documents and with the Epics' PRDs.

Two operations, both rules with no judgment in them:

- :func:`sync_documents` reads the architecture documents that changed since the vault commit the
  matrix last read, records each heading's hash and the document's lifecycle, and marks what an
  edit made out of date: a heading whose text no longer matches the hash recorded at approval,
  every fact and supporting feature whose home is that heading, and every settled disagreement
  whose losing statement is gone.
- :func:`sync_prds` gives every Epic one ``prd`` row holding its PRD file, the hash of that file
  and the Epic id. A PRD whose hash changed is not assessed any more.

Neither writes to beads, and the one thing either side of this module writes to the vault is the
lifecycle line of a document's front matter (:func:`set_lifecycle`): in-review when an Epic's
read finds a heading nobody has reviewed in an effective document (:func:`hold_for_review`), and
effective again when the review approves it. Git and ``bd`` are the only programs run.
"""

import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs the resolved git and bd executables with a separate argv and no shell.
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    APPROVAL_APPROVED,
    APPROVAL_CHANGED_SINCE_APPROVAL,
    APPROVAL_UNVERIFIED,
    BASIS_CARRIED_FROM_EFFECTIVE_ARC42,
    COVERAGE_NOT_ASSESSED,
    DISAGREEMENT_APPLIED,
    DISAGREEMENT_SETTLED,
    DOCUMENT_ROOTS,
    KIND_DISAGREEMENT,
    KIND_DOCUMENT,
    KIND_FACT,
    KIND_PRD,
    LIFECYCLE_DRAFT,
    LIFECYCLE_EFFECTIVE,
    LIFECYCLE_IN_REVIEW,
    LIFECYCLE_RETIRED,
    LIFECYCLES,
    Anchor,
    Approval,
    ApprovalState,
    Claim,
    DisagreementStatus,
    DisputedStatement,
    DocumentClass,
    DocumentsSyncedAt,
    HeadingHash,
    Lifecycle,
    Matrix,
    MatrixError,
    Node,
    NodeId,
)
from matrixstore import Stamp, heading_state, make_id

FENCE: Final = "---"
LIFECYCLE_KEY: Final = "lifecycle_state"
"""The front matter key that states a document's lifecycle."""
CODE_FENCES: Final[tuple[str, ...]] = ("```", "~~~")
MARKDOWN_SUFFIX: Final = ".md"
PREAMBLE: Final = "(preamble)"
"""The key of the text a document holds before its first heading."""
PRD_LABEL_PREFIX: Final = "prd:"
"""An Epic names its PRD with a label of this prefix followed by the PRD file's stem."""
EPIC_TYPE: Final = "epic"
FIRST_SECTION: Final = 1
LAST_SECTION: Final = 12
QUOTE_PAIR: Final = 2
_HEADING: Final[re.Pattern[str]] = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
_TITLE: Final[re.Pattern[str]] = re.compile(r"^#\s+(.*?)\s*#*\s*$")
_SECTION: Final[re.Pattern[str]] = re.compile(r"^(\d{2})-")
_RENAMED: Final = "RC"
_SLUG_DROPPED: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9 -]")
CONSTRAINTS_SECTION: Final = 2
"""The arc42 section that holds the owner's constraints, which no pipeline step may change."""


@dataclass(frozen=True, slots=True)
class DocumentRead:
    """One architecture document as the vault holds it now."""

    path: str
    """The file, relative to the vault root, with forward slashes."""
    document_class: DocumentClass
    title: str
    lifecycle: Lifecycle
    lifecycle_stated: bool
    """False when the front matter states no lifecycle the contract knows; the document is then a draft."""
    section: int | None
    view_type: str | None
    scope: str | None
    subject: str | None
    shows: tuple[str, ...]
    headings: Mapping[str, str]
    """Each heading's key and the hash of its own text."""
    text: str
    """The document's body with runs of white space collapsed, for finding a quoted statement."""


@dataclass(frozen=True, slots=True)
class VaultChange:
    """What changed in the vault's architecture documents since the matrix last read them."""

    commit: str
    paths: tuple[str, ...]
    """Every document to read again, existing or deleted."""
    dirty: tuple[str, ...]
    """The documents that differ from ``commit`` in the working tree."""
    full: bool
    """True when every document is read because the last read cannot be compared with."""


@dataclass(frozen=True, slots=True)
class Epic:
    """One Epic as beads holds it, reduced to what a PRD row needs."""

    bead: str
    title: str
    stems: tuple[str, ...]
    """The PRD file stems its labels name."""


class DocumentsSynced(TypedDict):
    """What :func:`sync_documents` did: also what ``sync-documents`` prints."""

    vaultCommit: str
    skipped: bool
    """True when the vault is at the commit last read and no document differs from it."""
    full: bool
    read: int
    added: list[str]
    changed: list[str]
    retired: list[str]
    headingsChanged: list[Anchor]
    """Every heading that no longer matches the hash recorded at its approval."""
    rowsChanged: list[NodeId]
    """Every fact, feature and disagreement whose marker the read changed."""
    lifecycleNotStated: list[str]
    inReview: list[str]
    """Every effective document whose front matter this read set to in-review, for the Epic that changed it."""


class UnresolvedPrd(TypedDict):
    """An Epic that could not be given a PRD row, and why."""

    bead: str
    reason: str


class PrdsSynced(TypedDict):
    """What :func:`sync_prds` did: also what ``sync-prds`` prints."""

    created: list[NodeId]
    refreshed: list[NodeId]
    """Rows whose PRD hash changed and whose coverage is not assessed any more."""
    unchanged: int
    unresolved: list[UnresolvedPrd]


def _run(executable: str, arguments: Sequence[str], folder: Path) -> str:
    """Run one program and return what it printed.

    Returns:
        The program's standard output.

    Raises:
        MatrixError: The program is not installed, could not be started or exited non-zero.

    """
    resolved: str | None = shutil.which(executable)
    message: str
    if resolved is None:
        message = f"{executable} is not on PATH"
        raise MatrixError(message)
    try:
        done: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved executable and separate argv; shell disabled.
            [resolved, *arguments],
            cwd=folder,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        message = f"cannot run {executable} in {folder}: {error}"
        raise MatrixError(message) from error
    if done.returncode != 0:
        message = f"{executable} {' '.join(arguments[:3])} failed in {folder}: {done.stderr.strip()}"
        raise MatrixError(message)
    return done.stdout


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def program_output(executable: str, arguments: Sequence[str], folder: Path) -> str:
    """Run git or bd for another matrix module and return what it printed.

    A program that is not installed, cannot be started or exits non-zero raises ``MatrixError``.

    Args:
        executable: The program's name; it is resolved on PATH.
        arguments: Its arguments.
        folder: The folder to run it in.

    Returns:
        The program's standard output.

    """
    return _run(executable, arguments, folder)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def vault_root(folder: Path) -> Path:
    """Find the root of the git repository a folder of the vault is in.

    A folder that is in no git repository raises ``MatrixError``.

    Args:
        folder: A folder inside the vault.

    Returns:
        The repository's top folder, with symbolic links resolved.

    Raises:
        MatrixError: ``folder`` is not a directory.

    """
    if not folder.is_dir():
        message: str = f"{folder} is not a directory"
        raise MatrixError(message)
    return Path(_run("git", ["rev-parse", "--show-toplevel"], folder).strip()).resolve()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def relative_path(path: Path, vault: Path) -> str:
    """Name a file the way the matrix records it.

    Args:
        path: The file.
        vault: The vault root.

    Returns:
        The path relative to the vault root with forward slashes; the absolute path when the file
        is outside the vault.

    """
    resolved: Path = path.resolve()
    if resolved.is_relative_to(vault):
        return resolved.relative_to(vault).as_posix()
    return resolved.as_posix()


def _unquote(value: str) -> str:
    """Strip one pair of matching quotes from a front matter scalar.

    Returns:
        The scalar without its quotes.

    """
    stripped: str = value.strip()
    if len(stripped) >= QUOTE_PAIR and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def _front_matter(lines: Sequence[str]) -> tuple[dict[str, str], tuple[str, ...], int]:
    """Read the scalars and the ``shows`` list of a document's front matter.

    Returns:
        The top-level scalars by key, the ``shows`` names in order without repeats, and the index
        of the first body line. A document with no front matter has no scalars and its body
        starts at line 0.

    """
    if not lines or lines[0].strip() != FENCE:
        return {}, (), 0
    close: int = next((index for index in range(1, len(lines)) if lines[index].strip() == FENCE), 0)
    if not close:
        return {}, (), 0
    scalars: dict[str, str] = {}
    shows: list[str] = []
    current: str = ""
    line: str
    for line in lines[1:close]:
        if line.lstrip().startswith("- ") and current == "shows":
            shows.append(_unquote(line.lstrip()[2:]))
            continue
        if ":" not in line or line[:1].isspace():
            continue
        key: str
        rest: str
        key, _, rest = line.partition(":")
        current = key.strip()
        scalars[current] = _unquote(rest)
        if current == "shows" and rest.strip().startswith("[") and rest.strip().endswith("]"):
            shows.extend(_unquote(value) for value in rest.strip()[1:-1].split(",") if value.strip())
    return scalars, tuple(name for name in dict.fromkeys(shows) if name), close + 1


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def heading_texts(body: Sequence[str]) -> dict[str, str]:
    """Split a document body into its headings, each with its own text.

    A heading's own text is its heading line and everything up to the next heading of any level,
    so a change under a sub-heading changes that sub-heading only. A ``#`` line inside a fenced
    code block is not a heading. A heading text that repeats within the document gets the key
    ``<text> (2)``, ``<text> (3)`` and so on.

    Args:
        body: The document's lines after its front matter.

    Returns:
        Each heading's key and its text with trailing white space removed, in document order.
        Text before the first heading is filed under :data:`PREAMBLE` when it is not blank.

    """
    texts: dict[str, list[str]] = {}
    seen: dict[str, int] = {}
    key: str = PREAMBLE
    fenced: bool = False
    line: str
    for line in body:
        if line.lstrip().startswith(CODE_FENCES):
            fenced = not fenced
        match: re.Match[str] | None = None if fenced else _HEADING.match(line)
        if match is not None:
            title: str = match.group(1) or line.strip()
            seen[title] = seen.get(title, 0) + 1
            key = title if seen[title] == 1 else f"{title} ({seen[title]})"
        texts.setdefault(key, []).append(line.rstrip())
    joined: dict[str, str] = {name: "\n".join(lines).strip("\n") for name, lines in texts.items()}
    return {name: text for name, text in joined.items() if text.strip() or name != PREAMBLE}


def _section(relative: str) -> int | None:
    """Read the arc42 section number a document's folder states.

    Returns:
        The number of the first folder named ``NN-...``, or None when no folder is.

    """
    part: str
    for part in Path(relative).parts:
        match: re.Match[str] | None = _SECTION.match(part)
        if match is not None and FIRST_SECTION <= int(match.group(1)) <= LAST_SECTION:
            return int(match.group(1))
    return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_document(relative: str, document_class: DocumentClass, text: str) -> DocumentRead:
    """Read what the matrix records of one architecture document from its text.

    Args:
        relative: The file, relative to the vault root.
        document_class: The class of document the file's folder holds.
        text: The whole file.

    Returns:
        The document's lifecycle, catalog keys, headings with the hash of each heading's own
        text, and its body for finding quoted statements.

    Raises:
        ValueError: ``relative`` is empty.

    """
    if not relative:
        message: str = "a document needs its path"
        raise ValueError(message)
    lines: list[str] = text.splitlines()
    scalars: dict[str, str]
    shows: tuple[str, ...]
    start: int
    scalars, shows, start = _front_matter(lines)
    body: list[str] = lines[start:]
    stated: str = scalars.get(LIFECYCLE_KEY, "")
    lifecycle: Lifecycle = next((choice for choice in LIFECYCLES if choice == stated), LIFECYCLE_DRAFT)
    titles: list[str] = [match.group(1) for match in map(_TITLE.match, body) if match is not None]
    subject: str | None = scalars.get("subject") or None
    return DocumentRead(
        path=relative,
        document_class=document_class,
        title=(titles[0] if titles else "") or subject or Path(relative).stem,
        lifecycle=lifecycle,
        lifecycle_stated=stated == lifecycle,
        section=_section(relative),
        view_type=scalars.get("view_type") or None,
        scope=scalars.get("scope") or None,
        subject=subject,
        shows=shows,
        headings={key: hashlib.sha256(own.encode()).hexdigest() for key, own in heading_texts(body).items()},
        text=" ".join("\n".join(body).split()),
    )


def _class_roots(vault: Path, arch: Path) -> dict[str, DocumentClass]:
    """Name the folder of each class of document the read covers.

    Returns:
        Each folder, relative to the vault root, and the class of document it holds.

    """
    return {relative_path(arch / folder, vault): document_class for document_class, folder in DOCUMENT_ROOTS.items()}


def _class_of(relative: str, roots: Mapping[str, DocumentClass]) -> DocumentClass | None:
    """Find the class of document a path belongs to.

    Returns:
        The class of the folder the Markdown file is under, or None when it is under none.

    """
    if not relative.endswith(MARKDOWN_SUFFIX):
        return None
    return next((kind for root, kind in roots.items() if relative.startswith(root + "/")), None)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_documents(vault: Path, arch: Path, paths: Sequence[str] | None = None) -> list[DocumentRead]:
    """Read architecture documents from the vault.

    Args:
        vault: The vault root.
        arch: The architecture root inside the vault.
        paths: The documents to read, relative to the vault root; None reads every document. A
            path that is not a Markdown file under a document folder, or no longer exists, is
            left out.

    Returns:
        The documents read, in path order.

    Raises:
        MatrixError: A document cannot be read.

    """
    roots: dict[str, DocumentClass] = _class_roots(vault, arch)
    wanted: list[str] = (
        sorted(relative_path(path, vault) for root in roots for path in (vault / root).rglob("*" + MARKDOWN_SUFFIX))
        if paths is None
        else sorted(set(paths))
    )
    documents: list[DocumentRead] = []
    relative: str
    for relative in wanted:
        document_class: DocumentClass | None = _class_of(relative, roots)
        if document_class is None or not (vault / relative).is_file():
            continue
        try:
            text: str = (vault / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            message: str = f"cannot read the document {vault / relative}: {error}"
            raise MatrixError(message) from error
        documents.append(parse_document(relative, document_class, text))
    return documents


def _dirty_paths(vault: Path, roots: Sequence[str]) -> list[str]:
    """List the files under the document folders that differ from the vault's commit.

    Returns:
        Every modified, added, deleted or untracked path, and both names of a renamed one.

    """
    printed: str = _run("git", ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *roots], vault)
    entries: list[str] = [entry for entry in printed.split("\0") if entry]
    paths: list[str] = []
    index: int = 0
    while index < len(entries):
        entry: str = entries[index]
        paths.append(entry[3:])
        if set(entry[:2]) & set(_RENAMED) and index + 1 < len(entries):
            index += 1
            paths.append(entries[index])
        index += 1
    return paths


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def vault_change(vault: Path, arch: Path, synced: DocumentsSyncedAt, *, full: bool = False) -> VaultChange:
    """Work out which architecture documents to read again.

    The documents to read are those git reports changed between the commit last read and the
    present commit, those that differ from the present commit in the working tree, and those
    that differed when they were last read. Every document is read when the caller asks, when
    nothing was read before, or when git no longer knows the commit last read.

    Args:
        vault: The vault root.
        arch: The architecture root inside the vault.
        synced: What the matrix recorded at its last read.
        full: Whether to read every document whatever git reports.

    Returns:
        The vault's present commit and the documents to read.

    """
    roots: dict[str, DocumentClass] = _class_roots(vault, arch)
    commit: str = _run("git", ["rev-parse", "HEAD"], vault).strip()
    dirty: list[str] = sorted(path for path in _dirty_paths(vault, list(roots)) if _class_of(path, roots) is not None)
    everything: bool = full or not synced["vaultCommit"]
    committed: list[str] = []
    if not everything and synced["vaultCommit"] != commit:
        compare: list[str] = ["diff", "--name-only", "-z", synced["vaultCommit"], commit, "--", *roots]
        try:
            printed: str = _run("git", compare, vault)
        except MatrixError:
            everything = True
        else:
            committed = [path for path in printed.split("\0") if _class_of(path, roots) is not None]
    if everything:
        present: list[str] = [document.path for document in read_documents(vault, arch)]
        return VaultChange(commit=commit, paths=tuple(sorted({*present, *dirty})), dirty=tuple(dirty), full=True)
    paths: set[str] = {*committed, *dirty, *synced["dirtyPaths"]}
    return VaultChange(commit=commit, paths=tuple(sorted(paths)), dirty=tuple(dirty), full=False)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def placeholder(entry: HeadingHash) -> bool:
    """Tell whether a heading entry only holds a claim on a heading that is not written yet.

    Args:
        entry: One heading entry of a document row.

    Returns:
        True when the heading is not in the document and was never approved.

    """
    return not entry["hash"] and entry["approvedHash"] is None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def headings_match(headings: Mapping[str, HeadingHash]) -> bool:
    """Tell whether every heading of a document is as it was approved.

    Args:
        headings: The heading entries of a document row.

    Returns:
        True when each heading is present and its hash equals the hash recorded at approval. An
        entry that only holds a claim on a heading still to be written is left out.

    """
    return all(
        bool(entry["hash"]) and entry["hash"] == entry["approvedHash"]
        for entry in headings.values()
        if not placeholder(entry)
    )


def _merged_headings(read: DocumentRead, existing: Mapping[str, HeadingHash]) -> dict[str, HeadingHash]:
    """Join the headings a document has now with the hashes recorded when it was approved.

    Returns:
        One entry per present heading, keeping its approved hash and its claim; and one entry
        with an empty hash per heading the document does not have that was approved or is claimed.

    """
    merged: dict[str, HeadingHash] = {}
    key: str
    value: str
    for key, value in read.headings.items():
        merged[key] = {"hash": value, "approvedHash": existing[key]["approvedHash"] if key in existing else None}
    entry: HeadingHash
    for key, entry in existing.items():
        if key not in merged and (entry["approvedHash"] is not None or "claim" in entry):
            merged[key] = {"hash": "", "approvedHash": entry["approvedHash"]}
        if key in merged and "claim" in entry:
            merged[key]["claim"] = entry["claim"]
    return merged


def _new_document(read: DocumentRead, stamp: Stamp, *, carried: bool) -> Node:
    """Build the row of a document the matrix does not hold yet.

    Returns:
        The row. A carried effective document is approved with every heading's present hash; any
        other new document is unverified with no approved hash.

    """
    approved: bool = carried and read.lifecycle == LIFECYCLE_EFFECTIVE
    approval: Approval = (
        {"state": APPROVAL_APPROVED, "basis": BASIS_CARRIED_FROM_EFFECTIVE_ARC42, "at": stamp.at}
        if approved
        else {"state": APPROVAL_UNVERIFIED}
    )
    return {
        "id": make_id(KIND_DOCUMENT, read.path),
        "kind": KIND_DOCUMENT,
        "name": read.title,
        "links": [],
        "changed": stamp.change(),
        "path": read.path,
        "documentClass": read.document_class,
        "section": read.section,
        "viewType": read.view_type,
        "scope": read.scope,
        "subject": read.subject,
        "lifecycle": read.lifecycle,
        "headings": {
            key: {"hash": value, "approvedHash": value if approved else None} for key, value in read.headings.items()
        },
        "approval": approval,
    }


def _document_state(current: ApprovalState, headings: Mapping[str, HeadingHash]) -> ApprovalState:
    """Work out a document's approval state from its headings.

    Returns:
        Changed since approval for an approved document with a heading that differs; approved
        again for such a document whose headings all match; otherwise the state it has.

    """
    matches: bool = headings_match(headings)
    if current == APPROVAL_APPROVED and not matches:
        return APPROVAL_CHANGED_SINCE_APPROVAL
    if current == APPROVAL_CHANGED_SINCE_APPROVAL and matches:
        return APPROVAL_APPROVED
    return current


def _apply_document(node: Node, read: DocumentRead | None, stamp: Stamp) -> bool:
    """Correct a document row from the document as it is now, or from its absence.

    Returns:
        True when the row changed.

    """
    before: str = json.dumps(node, sort_keys=True)
    existing: dict[str, HeadingHash] = node.get("headings", {})
    if read is None:
        node["lifecycle"] = LIFECYCLE_RETIRED
        node["headings"] = {
            key: {"hash": "", "approvedHash": entry["approvedHash"]}
            for key, entry in existing.items()
            if entry["approvedHash"] is not None
        }
    else:
        node["name"] = read.title
        node["section"] = read.section
        node["viewType"] = read.view_type
        node["scope"] = read.scope
        node["subject"] = read.subject
        node["lifecycle"] = read.lifecycle
        node["headings"] = _merged_headings(read, existing)
    unverified: Approval = {"state": APPROVAL_UNVERIFIED}
    approval: Approval = node.get("approval", unverified)
    if read is not None:
        approval["state"] = _document_state(approval["state"], node["headings"])
    elif approval["state"] == APPROVAL_APPROVED:
        approval["state"] = APPROVAL_CHANGED_SINCE_APPROVAL
    node["approval"] = approval
    if json.dumps(node, sort_keys=True) == before:
        return False
    node["changed"] = stamp.change()
    return True


def _refresh_homes(matrix: Matrix, touched: set[str], stamp: Stamp) -> list[NodeId]:
    """Correct the marker of every row whose home is a heading of a document that was read again.

    Returns:
        The ids of the rows whose approval state changed.

    """
    changed: list[NodeId] = []
    node: Node
    for node in matrix["nodes"].values():
        home: Anchor | None = node.get("home")
        approval: Approval | None = node.get("approval")
        if home is None or approval is None or home["document"] not in touched:
            continue
        document: Node | None = matrix["nodes"].get(make_id(KIND_DOCUMENT, home["document"]))
        if document is None:
            continue
        state: ApprovalState = heading_state(document, home["heading"], approval["state"])
        if state != approval["state"]:
            approval["state"] = state
            node["changed"] = stamp.change()
            changed.append(node["id"])
    return changed


def _disagreement_status(node: Node, texts: Mapping[str, str]) -> DisagreementStatus | None:
    """Work out whether a settled disagreement has been applied to the documents.

    Returns:
        None when no statement that can be looked for names a document the vault holds. For a
        settlement that names the statements that lost: applied when none of them is in its
        document any more, else settled. For a carried note that names no loser: applied when a
        statement is no longer in its document, else settled.

    """
    stated: list[DisputedStatement] = [
        statement for statement in node.get("statements", []) if statement["document"] in texts
    ]
    losers: list[DisputedStatement] = [statement for statement in stated if statement.get("stands") is False]
    ruled: bool = any("stands" in statement for statement in node.get("statements", []))
    watched: list[DisputedStatement] = losers if ruled else stated
    found: list[bool] = [" ".join(entry["text"].split()) in texts[entry["document"]] for entry in watched]
    if not found:
        return None
    if ruled:
        return DISAGREEMENT_SETTLED if any(found) else DISAGREEMENT_APPLIED
    return DISAGREEMENT_SETTLED if all(found) else DISAGREEMENT_APPLIED


def _refresh_disagreements(matrix: Matrix, vault: Path, arch: Path, touched: set[str], stamp: Stamp) -> list[NodeId]:
    """Correct the status of every settled disagreement that quotes a document that was read again.

    Returns:
        The ids of the disagreement rows whose status changed.

    """
    watched: list[Node] = [
        node
        for node in matrix["nodes"].values()
        if node["kind"] == KIND_DISAGREEMENT
        and node.get("disagreementStatus") in {DISAGREEMENT_SETTLED, DISAGREEMENT_APPLIED}
        and any(statement["document"] in touched for statement in node.get("statements", []))
    ]
    quoted: set[str] = {statement["document"] for node in watched for statement in node.get("statements", [])}
    texts: dict[str, str] = {document.path: document.text for document in read_documents(vault, arch, sorted(quoted))}
    changed: list[NodeId] = []
    node: Node
    for node in watched:
        status: DisagreementStatus | None = _disagreement_status(node, texts)
        if status is not None and status != node.get("disagreementStatus"):
            node["disagreementStatus"] = status
            node["changed"] = stamp.change()
            changed.append(node["id"])
    return changed


def _document_rows(matrix: Matrix) -> dict[str, Node]:
    """Index the document rows of the classes the read covers by their path.

    Returns:
        Each such document's path and its row.

    """
    return {
        node["path"]: node
        for node in matrix["nodes"].values()
        if node["kind"] == KIND_DOCUMENT and "path" in node and node.get("documentClass") in DOCUMENT_ROOTS
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def apply_documents(
    matrix: Matrix,
    documents: Sequence[DocumentRead],
    paths: Sequence[str],
    stamp: Stamp,
    *,
    carried: bool = False,
) -> DocumentsSynced:
    """Correct the document rows of the matrix from documents already read.

    Args:
        matrix: The matrix, changed in place.
        documents: The documents read from the vault.
        paths: Every path that was looked at; a path with no document among ``documents`` no
            longer exists, and its row is retired.
        stamp: The moment and the maker to record on each changed row.
        carried: Whether a new effective document is recorded as approved, as the carry-over
            does. An ordinary read records a new document as unverified.

    Returns:
        What was added, changed and retired, and the headings that no longer match the hash
        recorded at their approval. The commit, ``skipped``, ``full`` and ``rowsChanged`` are
        left for the caller to fill.

    """
    rows: dict[str, Node] = _document_rows(matrix)
    read: dict[str, DocumentRead] = {document.path: document for document in documents}
    result: DocumentsSynced = {
        "vaultCommit": "",
        "skipped": False,
        "full": False,
        "read": len(read),
        "added": [],
        "changed": [],
        "retired": [],
        "headingsChanged": [],
        "rowsChanged": [],
        "lifecycleNotStated": sorted(path for path, document in read.items() if not document.lifecycle_stated),
        "inReview": [],
    }
    path: str
    for path in sorted({*paths, *read}):
        document: DocumentRead | None = read.get(path)
        if path not in rows:
            if document is not None:
                matrix["nodes"][make_id(KIND_DOCUMENT, path)] = _new_document(document, stamp, carried=carried)
                result["added"].append(path)
            continue
        if _apply_document(rows[path], document, stamp):
            result["retired" if document is None else "changed"].append(path)
        result["headingsChanged"].extend(
            {"document": path, "heading": key}
            for key, entry in rows[path].get("headings", {}).items()
            if entry["approvedHash"] is not None and entry["hash"] != entry["approvedHash"]
        )
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def sync_documents(matrix: Matrix, arch: Path, stamp: Stamp, *, full: bool = False) -> DocumentsSynced:
    """Bring the document rows and what depends on them up to date with the vault.

    When the vault is at the commit the matrix last read and no document differs from it, nothing
    is read and nothing changes. Otherwise only the documents git reports changed are read
    (:func:`vault_change`). A heading whose text no longer matches the hash recorded at its
    approval makes its document, and every fact and supporting feature whose home it is, changed
    since approval; a heading that matches again makes them approved again. A settled
    disagreement whose quoted statement is gone becomes applied. Git failures raise
    ``MatrixError``.

    Args:
        matrix: The matrix, changed in place.
        arch: The architecture root inside the vault.
        stamp: The moment to record on each changed row, and its maker: a bead id, or ``sync``.
        full: Whether to read every document whatever git reports.

    Returns:
        What the read did.

    """
    vault: Path = vault_root(arch)
    change: VaultChange = vault_change(vault, arch, matrix["documentsSyncedAt"], full=full)
    if not change.paths and change.commit == matrix["documentsSyncedAt"]["vaultCommit"]:
        result: DocumentsSynced = apply_documents(matrix, [], [], stamp)
        result["vaultCommit"] = change.commit
        result["skipped"] = True
        return result
    wanted: set[str] = {*change.paths, *_document_rows(matrix)} if change.full else set(change.paths)
    result = apply_documents(matrix, read_documents(vault, arch, sorted(wanted)), sorted(wanted), stamp)
    result["vaultCommit"] = change.commit
    result["full"] = change.full
    touched: set[str] = {*result["added"], *result["changed"], *result["retired"]}
    result["rowsChanged"] = [
        *_refresh_homes(matrix, touched, stamp),
        *_refresh_disagreements(matrix, vault, arch, touched, stamp),
    ]
    recorded: DocumentsSyncedAt = matrix["documentsSyncedAt"]
    if touched or recorded["vaultCommit"] != change.commit or recorded["dirtyPaths"] != list(change.dirty):
        matrix["documentsSyncedAt"] = {"vaultCommit": change.commit, "at": stamp.at, "dirtyPaths": list(change.dirty)}
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def set_lifecycle(vault: Path, relative: str, lifecycle: Lifecycle) -> bool:
    """Write a document's lifecycle into its front matter, the one place that states it.

    This is the only write the matrix makes to the vault. It changes the one front matter line
    and nothing of the document's body, so no heading hash changes.

    Args:
        vault: The vault root.
        relative: The document, relative to the vault root.
        lifecycle: The lifecycle to state.

    Returns:
        True when the file was changed; False when it already stated that lifecycle.

    Raises:
        MatrixError: The document cannot be read or written, or has no front matter.

    """
    file: Path = vault / relative
    message: str
    try:
        lines: list[str] = file.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError) as error:
        message = f"cannot read the document {file}: {error}"
        raise MatrixError(message) from error
    close: int = (
        next((index for index in range(1, len(lines)) if lines[index].strip() == FENCE), 0)
        if lines and lines[0].strip() == FENCE
        else 0
    )
    if not close:
        message = f"the document {file} has no front matter to state its lifecycle in"
        raise MatrixError(message)
    stated: str = f"{LIFECYCLE_KEY}: {lifecycle}\n"
    at: int = next((index for index in range(1, close) if lines[index].partition(":")[0] == LIFECYCLE_KEY), 0)
    if at and _unquote(lines[at].partition(":")[2]) == lifecycle:
        return False
    if at:
        lines[at] = stated
    else:
        lines.insert(close, stated)
    try:
        file.write_text("".join(lines), encoding="utf-8")
    except OSError as error:
        message = f"cannot write the document {file}: {error}"
        raise MatrixError(message) from error
    return True


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def hold_for_review(matrix: Matrix, arch: Path, paths: Sequence[str], claim: Claim) -> list[str]:
    """Record that an Epic changed some documents, so its review finds exactly what it changed.

    For each document that has a heading that is not as it was approved: every such heading no
    other Epic claims is claimed for the Epic, the document's marker names the Epic, and a
    document whose front matter still says effective is set to in-review in the vault, because
    it now holds text nobody has reviewed. A vault that cannot be written raises ``MatrixError``.

    Args:
        matrix: The matrix, changed in place.
        arch: The architecture root inside the vault.
        paths: The documents the Epic's read found added or changed, relative to the vault root.
        claim: The Epic, its journal step and the moment.

    Returns:
        The documents whose front matter was set to in-review.

    """
    vault: Path = vault_root(arch)
    rows: dict[str, Node] = _document_rows(matrix)
    held: list[str] = []
    path: str
    for path in sorted(set(paths) & set(rows)):
        node: Node = rows[path]
        differing: list[HeadingHash] = [
            entry
            for entry in node.get("headings", {}).values()
            if not placeholder(entry) and entry["hash"] != entry["approvedHash"]
        ]
        if not differing or node.get("lifecycle") == LIFECYCLE_RETIRED:
            continue
        entry: HeadingHash
        for entry in differing:
            entry.setdefault("claim", claim)
        if "approval" in node and node["approval"]["state"] != APPROVAL_APPROVED:
            node["approval"]["bead"] = claim["bead"]
        if node.get("lifecycle") == LIFECYCLE_EFFECTIVE:
            set_lifecycle(vault, path, LIFECYCLE_IN_REVIEW)
            node["lifecycle"] = LIFECYCLE_IN_REVIEW
            held.append(path)
    return held


def _link_targets(document: str, heading: str) -> list[str]:
    """List the forms a link to one heading of one document can take in Markdown.

    Returns:
        The document's file stem followed by the heading as written (a wikilink) and as a
        lower-case, hyphenated anchor (a Markdown link), with and without the file suffix.

    """
    stem: str = Path(document).stem
    slug: str = "-".join(_SLUG_DROPPED.sub("", heading.lower()).split())
    return [
        f"{stem}#{heading}",
        f"{stem}#{slug}",
        f"{stem}{MARKDOWN_SUFFIX}#{heading}",
        f"{stem}{MARKDOWN_SUFFIX}#{slug}",
    ]


def _linked_from_problems(matrix: Matrix, vault: Path) -> list[str]:
    """Check that every document a fact lists as linking to its home holds that link.

    Returns:
        One sentence per listed document that cannot be read or holds no link to the home heading.

    """
    problems: list[str] = []
    texts: dict[str, str | None] = {}
    node: Node
    for node in matrix["nodes"].values():
        home: Anchor | None = node.get("home")
        if node["kind"] != KIND_FACT or home is None:
            continue
        targets: list[str] = _link_targets(home["document"], home["heading"])
        linked: str
        for linked in node.get("linkedFrom", []):
            if linked not in texts:
                file: Path = vault / linked
                texts[linked] = file.read_text(encoding="utf-8", errors="replace") if file.is_file() else None
            text: str | None = texts[linked]
            if text is None:
                problems.append(f"{node['id']}: the linking document {linked} is not in the vault")
            elif not any(target in text for target in targets):
                problems.append(f"{node['id']}: {linked} holds no link to {home['document']}#{home['heading']}")
    return problems


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def vault_problems(matrix: Matrix, arch: Path) -> list[str]:
    """Check the matrix against the vault for the two rules that need the documents themselves.

    The owner's constraints (arc42 section 2) must be as the matrix last read them: a pipeline
    step that changed them is a fault. And every document a fact lists in ``linkedFrom`` must
    hold a link to the fact's home heading. Git failures raise ``MatrixError``.

    Args:
        matrix: The matrix.
        arch: The architecture root inside the vault.

    Returns:
        One sentence per constraints heading that differs from the hash the matrix holds, per
        constraints document added or removed since the last read, and per missing link.

    """
    vault: Path = vault_root(arch)
    recorded: dict[str, Node] = {
        path: node for path, node in _document_rows(matrix).items() if node.get("section") == CONSTRAINTS_SECTION
    }
    present: dict[str, DocumentRead] = {
        document.path: document for document in read_documents(vault, arch) if document.section == CONSTRAINTS_SECTION
    }
    problems: list[str] = [
        f"{path}: the constraints document is not as the matrix last read it (it was added or removed)"
        for path in sorted(set(recorded) ^ set(present))
        if path in present or recorded[path].get("lifecycle") != LIFECYCLE_RETIRED
    ]
    path: str
    for path in sorted(set(recorded) & set(present)):
        held: dict[str, str] = {key: entry["hash"] for key, entry in recorded[path].get("headings", {}).items()}
        current: dict[str, str] = dict(present[path].headings)
        problems.extend(
            f"{path}: the constraints heading {key!r} is not as the matrix last read it"
            for key in sorted({*held, *current})
            if held.get(key, "") != current.get(key, "")
        )
    return [*problems, *_linked_from_problems(matrix, vault)]


def _epic(entry: object) -> Epic | None:
    """Narrow one decoded bead to an Epic.

    Returns:
        The Epic, or None when the bead is not an Epic.

    Raises:
        MatrixError: The bead lacks an id or a title, or its labels are not a list of strings.

    """
    message: str
    if not isinstance(entry, dict):
        message = "beads printed an issue that is not a JSON object"
        raise MatrixError(message)
    bead: object = entry.get("id")
    title: object = entry.get("title")
    labels: object = entry.get("labels") or []
    if not isinstance(bead, str) or not bead or not isinstance(title, str) or not title:
        message = "beads printed an issue with no id or no title"
        raise MatrixError(message)
    if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
        message = f"the labels of {bead} are not a list of strings"
        raise MatrixError(message)
    if entry.get("issue_type") != EPIC_TYPE:
        return None
    stems: list[str] = [
        label.strip()[len(PRD_LABEL_PREFIX) :]
        for label in labels
        if isinstance(label, str) and label.strip().startswith(PRD_LABEL_PREFIX)
    ]
    return Epic(bead=bead, title=title, stems=tuple(dict.fromkeys(stem for stem in stems if stem)))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_epics(text: str) -> list[Epic]:
    """Read the Epics from the JSON ``bd list --json`` or ``bd show --json`` prints.

    Args:
        text: The JSON text: an array of issues.

    Returns:
        The Epics among the issues, in the order printed. Issues of another type are left out.

    Raises:
        MatrixError: The text is not a JSON array of issues.

    """
    message: str
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as error:
        message = f"beads did not print JSON: {error}"
        raise MatrixError(message) from error
    if not isinstance(decoded, list):
        message = "beads did not print a JSON array of issues"
        raise MatrixError(message)
    return [epic for epic in map(_epic, decoded) if epic is not None]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_epics(control: Path, bead: str | None = None) -> list[Epic]:
    """Ask beads for the open Epics, or for one Epic.

    A ``bd`` that is missing or fails raises ``MatrixError``.

    Args:
        control: The control repository, whose beads database holds the Epics.
        bead: The one Epic to read; None reads every open Epic.

    Returns:
        The Epics.

    Raises:
        MatrixError: ``bead`` was given and is not an Epic.

    """
    arguments: list[str] = (
        ["list", "--type", EPIC_TYPE, "--status", "open", "--json", "--limit", "0"]
        if bead is None
        else ["show", bead, "--json"]
    )
    epics: list[Epic] = parse_epics(_run("bd", arguments, control))
    if bead is not None and [epic.bead for epic in epics] != [bead]:
        message: str = f"{bead} is not an Epic"
        raise MatrixError(message)
    return epics


def _prd_file(epic: Epic, files: Mapping[str, Sequence[Path]]) -> Path | str:
    """Find the one PRD file an Epic's labels name.

    Returns:
        The file, or the reason there is not exactly one.

    """
    if not epic.stems:
        return f"it has no {PRD_LABEL_PREFIX}<stem> label"
    found: list[Path] = [path for stem in epic.stems for path in files.get(stem, [])]
    if not found:
        return f"no file is named {' or '.join(stem + MARKDOWN_SUFFIX for stem in epic.stems)} under the PRD folder"
    if len(found) > 1:
        return "its labels name more than one PRD file: " + ", ".join(sorted(str(path) for path in found))
    return found[0]


def _apply_prd(matrix: Matrix, epic: Epic, relative: str, digest: str, stamp: Stamp) -> str:
    """Create or refresh the PRD row of one Epic.

    Returns:
        ``created``, ``refreshed`` when the PRD's hash changed, or ``unchanged``.

    """
    key: NodeId = make_id(KIND_PRD, epic.bead)
    stem: str = Path(relative).stem
    node: Node | None = matrix["nodes"].get(key)
    if node is None:
        matrix["nodes"][key] = {
            "id": key,
            "kind": KIND_PRD,
            "name": epic.title,
            "aliases": [stem],
            "links": [],
            "changed": stamp.change(),
            "bead": epic.bead,
            "path": relative,
            "hash": digest,
            "coverage": COVERAGE_NOT_ASSESSED,
            "expertise": [],
        }
        return "created"
    outcome: str = "unchanged"
    if node.get("hash") != digest:
        node["hash"] = digest
        node["coverage"] = COVERAGE_NOT_ASSESSED
        outcome = "refreshed"
    if outcome == "refreshed" or node.get("path") != relative or node["name"] != epic.title:
        node["path"] = relative
        node["name"] = epic.title
        node["aliases"] = sorted({*node.get("aliases", []), stem})
        node["changed"] = stamp.change()
    return outcome


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def sync_prds(matrix: Matrix, epics: Sequence[Epic], prd_dir: Path, stamp: Stamp) -> PrdsSynced:
    """Give every Epic one PRD row holding its PRD file, the file's hash and the Epic id.

    An Epic names its PRD with a ``prd:<stem>`` label; the PRD is the one Markdown file of that
    stem under the PRD folder. A new row, and a row whose PRD hash changed, has coverage not
    assessed. An Epic whose label names no file, or more than one, gets no row and is reported.
    A row whose Epic is not among ``epics`` is left as it is.

    Args:
        matrix: The matrix, changed in place.
        epics: The Epics to give rows.
        prd_dir: The folder the PRD files are under, at any depth.
        stamp: The moment and the maker to record on each changed row.

    Returns:
        The rows created and refreshed, how many were already current, and the Epics left out.

    Raises:
        MatrixError: The PRD folder is not a directory, or a PRD file cannot be read.

    """
    message: str
    if not prd_dir.is_dir():
        message = f"the PRD folder {prd_dir} is not a directory"
        raise MatrixError(message)
    vault: Path = vault_root(prd_dir)
    files: dict[str, list[Path]] = {}
    path: Path
    for path in sorted(prd_dir.rglob("*" + MARKDOWN_SUFFIX)):
        files.setdefault(path.stem, []).append(path)
    result: PrdsSynced = {"created": [], "refreshed": [], "unchanged": 0, "unresolved": []}
    epic: Epic
    for epic in epics:
        found: Path | str = _prd_file(epic, files)
        if isinstance(found, str):
            result["unresolved"].append({"bead": epic.bead, "reason": found})
            continue
        try:
            digest: str = hashlib.sha256(found.read_bytes()).hexdigest()
        except OSError as error:
            message = f"cannot read the PRD {found}: {error}"
            raise MatrixError(message) from error
        outcome: str = _apply_prd(matrix, epic, relative_path(found, vault), digest, stamp)
        if outcome == "unchanged":
            result["unchanged"] += 1
        else:
            result["created" if outcome == "created" else "refreshed"].append(make_id(KIND_PRD, epic.bead))
    return result
