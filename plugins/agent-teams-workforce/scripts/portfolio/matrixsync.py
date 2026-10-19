"""Bring the matrix up to date with the vault's architecture documents and with the Epics' PRDs.

Two operations, both rules with no judgment in them:

- :func:`sync_documents` (``sync-documents``) mirrors the architecture documents: every Markdown
  file of the arc42 folder, and every other Markdown file under the architecture root, outside the
  built and target versions, whose front matter states the catalog (a view type, a scope, a subject
  or the names it shows). One ``document`` entry per document that is effective, in review or
  draft, holding its front matter, its heading texts and its hash; one ``describedBy``
  relationship per name in the document's ``shows`` and ``subject`` that is the name or an alias
  of exactly one entry; and no entry for a document that is gone. It reads every document, or
  exactly the files the caller names.
- :func:`sync_epics` (``sync-epics``) gives every Epic one ``epic`` entry holding its PRD's path
  and hash, and one ``requirement`` entry per ``####`` heading under the PRD's ``## Requirements``
  heading, joined to the Epic by ``hasRequirement``. An Epic with no PRD file gets an entry that
  records no PRD.

Everything both record is on the architecture side: beads, a PRD or an architecture document states it.

Neither writes to beads. The one thing this module writes to the vault is the lifecycle line of a
document's front matter (:func:`set_lifecycle`), for the step that promotes a document; a
document entry's ``lifecycle`` only mirrors that line. Git is the only program run here; beads is
read through ``beadgraph``.
"""

import hashlib
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs the resolved git executable with a separate argv and no shell.
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, Literal, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import beadgraph
from matrix_contract import (
    AUTHORITY_SIDE,
    KIND_DOCUMENT,
    KIND_EPIC,
    KIND_REQUIREMENT,
    REL_DESCRIBED_BY,
    REL_HAS_REQUIREMENT,
    RELATIONSHIP_RULES,
    SIDE_ARCHITECTURE,
    Entry,
    EntryId,
    EntryKind,
    JsonValue,
    MatrixError,
    Relationship,
    relationship_json,
)
from matrixstore import Matrix, MatrixRefusedError, make_id, name_key, same_content, slug
from target_contract import TARGET_FOLDER

if TYPE_CHECKING:
    from contracts import JsonObject
    from contracts import JsonValue as BeadValue

type Lifecycle = Literal["effective", "in-review", "draft"]

LIFECYCLE_EFFECTIVE: Final[Lifecycle] = "effective"
LIFECYCLE_IN_REVIEW: Final[Lifecycle] = "in-review"
LIFECYCLE_DRAFT: Final[Lifecycle] = "draft"
LIFECYCLES: Final[tuple[Lifecycle, ...]] = (LIFECYCLE_EFFECTIVE, LIFECYCLE_IN_REVIEW, LIFECYCLE_DRAFT)
"""The lifecycles of a document the matrix holds an entry for."""
FENCE: Final = "---"
LIFECYCLE_KEY: Final = "lifecycle_state"
"""The front matter key that states a document's lifecycle."""
CODE_FENCES: Final[tuple[str, ...]] = ("```", "~~~")
MARKDOWN_SUFFIX: Final = ".md"
ARC42_FOLDER: Final = "arc42"
"""The folder of the architecture root that holds the arc42 documents: every Markdown file in it is a document."""
BUILT_FOLDER: Final = "built"
"""The folder of the architecture root that holds the built version: what a Story built that differs."""
VERSION_FOLDERS: Final[frozenset[str]] = frozenset({BUILT_FOLDER, TARGET_FOLDER})
"""The folders of the architecture root that hold another version than the one the matrix mirrors."""
PREAMBLE: Final = "(preamble)"
"""The key of the text a document holds before its first heading."""
EPIC_TYPE: Final = "epic"
"""The beads issue type of an Epic."""
PRD_LABEL_PREFIX: Final = "prd:"
"""What opens the beads label that names an Epic's PRD file by its stem."""
REQUIREMENTS_HEADING: Final = "requirements"
"""The second-level heading of a PRD that holds its requirements, as names are compared."""
SECTION_LEVEL: Final = 2
GROUP_LEVEL: Final = 3
REQUIREMENT_LEVEL: Final = 4
FIRST_SECTION: Final = 1
LAST_SECTION: Final = 12
DESCRIBED_KINDS: Final[frozenset[EntryKind]] = RELATIONSHIP_RULES[REL_DESCRIBED_BY].sources
"""The kinds of entry a document may describe."""
_HEADING: Final[re.Pattern[str]] = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SECTION: Final[re.Pattern[str]] = re.compile(r"^(\d{2})-")
_DOUBLE_QUOTED: Final[re.Pattern[str]] = re.compile(r'^"((?:[^"\\]|\\.)*)"')
_SINGLE_QUOTED: Final[re.Pattern[str]] = re.compile(r"^'((?:[^']|'')*)'")
_ESCAPED: Final[re.Pattern[str]] = re.compile(r"\\(.)")
_IDENTIFIER: Final[re.Pattern[str]] = re.compile(r"^([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)(?![A-Za-z0-9-])")
"""The identifier that opens a requirement heading: upper-case words and numbers joined by hyphens."""


@dataclass(frozen=True, slots=True)
class DocumentRead:
    """One architecture document as the vault holds it now."""

    path: str
    """The file, relative to the architecture root, with forward slashes."""
    title: str
    lifecycle: Lifecycle | None
    """None when the front matter states a lifecycle the matrix holds no entry for."""
    lifecycle_stated: bool
    """False when the front matter states no lifecycle; the document is then a draft."""
    section: int | None
    view_type: str | None
    scope: str | None
    subject: str | None
    shows: tuple[str, ...]
    headings: tuple[str, ...]
    """The heading texts, in document order; a text that repeats is ``<text> (2)`` and so on."""
    digest: str
    """The hash of the whole file."""


@dataclass(frozen=True, slots=True)
class EpicBead:
    """One Epic as beads holds it, reduced to what an epic entry needs."""

    bead: str
    title: str
    prd_stems: tuple[str, ...] = ()
    """The PRD file stems the Epic's ``prd:`` labels name, lower-cased, in order."""


@dataclass(frozen=True, slots=True)
class PrdSource:
    """Where one read of the Epics finds a PRD file."""

    vault: Path
    """The vault root, which every recorded PRD path is relative to."""
    given: str | None
    """The PRD file the caller gave for the one Epic read; None when it gave none."""
    files: Mapping[str, Sequence[str]]
    """The PRD folder's files by stem, lower-cased, each relative to the vault root."""


@dataclass(frozen=True, slots=True)
class RequirementRead:
    """One requirement of a PRD: one ``####`` heading under ``## Requirements``."""

    key: str
    """The identifier that opens the heading, else the slug of the heading."""
    name: str
    """The heading text."""
    group: str
    """The ``###`` heading above it; empty when it has none."""
    digest: str
    """The hash of the requirement's own text."""


class Described(TypedDict):
    """One ``describedBy`` relationship a read added."""

    entry: EntryId
    document: EntryId


class ShownName(TypedDict):
    """A name a document's ``shows`` or ``subject`` states that is the name of no entry."""

    document: str
    name: str


class AmbiguousName(TypedDict):
    """A name a document states that more than one entry answers to, so none was joined to it."""

    document: str
    name: str
    entries: list[EntryId]


class DocumentsSynced(TypedDict):
    """What :func:`sync_documents` did: also what ``sync-documents`` prints."""

    read: int
    """How many documents were read from the vault."""
    added: list[str]
    changed: list[str]
    removed: list[str]
    """The documents whose entry was removed: the file is gone, or is no longer one the matrix holds."""
    described: list[Described]
    unresolved: list[ShownName]
    ambiguous: list[AmbiguousName]
    lifecycleNotStated: list[str]
    leftOut: list[str]
    """Files looked at that get no entry: not an architecture document, or of a lifecycle the matrix does not hold."""


class EpicWithoutPrd(TypedDict):
    """An Epic whose entry records no PRD after the read, and why."""

    bead: str
    reason: str


class Carried(TypedDict):
    """One requirement whose relationships carried over to the requirement that replaced it in its group."""

    was: EntryId
    now: EntryId


class RemovedRequirement(TypedDict):
    """One requirement the PRD no longer states, with the relationships removed with it."""

    id: EntryId
    name: str
    relationships: list[dict[str, JsonValue]]
    """Every relationship it had besides ``hasRequirement``, for the run that corrects them."""


class EpicsSynced(TypedDict):
    """What :func:`sync_epics` did: also what ``sync-epics`` prints."""

    created: list[EntryId]
    refreshed: list[EntryId]
    """Epics whose title, PRD path or PRD hash changed."""
    unchanged: int
    requirementsAdded: list[EntryId]
    requirementsChanged: list[EntryId]
    requirementsCarried: list[Carried]
    requirementsRemoved: list[RemovedRequirement]
    noPrd: list[EpicWithoutPrd]
    """The Epics given whose PRD file is not known or cannot be read; each has an entry all the same."""
    unnamedPrds: list[str]
    """The Markdown files under the PRD folder that no epic entry names, relative to the vault root."""


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
    """Run git for another matrix module and return what it printed.

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
def relative_path(path: Path, root: Path) -> str:
    """Name a file by its path under a folder.

    Args:
        path: The file.
        root: The folder: the vault root for a PRD, the architecture root for a document.

    Returns:
        The path relative to the folder with forward slashes; the absolute path when the file is
        outside it.

    """
    resolved: Path = path.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return resolved.as_posix()


def _scalar(value: str) -> str:
    """Read one front matter scalar.

    Returns:
        The text inside a pair of quotes, with its escapes resolved; otherwise the text before a
        trailing comment.

    """
    stripped: str = value.strip()
    double: re.Match[str] | None = _DOUBLE_QUOTED.match(stripped)
    if double is not None:
        return _ESCAPED.sub(r"\1", double.group(1))
    single: re.Match[str] | None = _SINGLE_QUOTED.match(stripped)
    if single is not None:
        return single.group(1).replace("''", "'")
    return stripped.partition(" #")[0].strip()


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
            shows.append(_scalar(line.lstrip()[2:]))
            continue
        if ":" not in line or line[:1].isspace():
            continue
        key: str
        rest: str
        key, _, rest = line.partition(":")
        current = key.strip()
        scalars[current] = _scalar(rest)
        if current == "shows" and rest.strip().startswith("[") and rest.strip().endswith("]"):
            shows.extend(_scalar(value) for value in rest.strip()[1:-1].split(",") if value.strip())
    return scalars, tuple(name for name in dict.fromkeys(shows) if name), close + 1


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def heading_texts(body: Sequence[str]) -> dict[str, str]:
    """Split a document body into its headings, each with its own text.

    A heading's own text is its heading line and everything up to the next heading of any level.
    A ``#`` line inside a fenced code block is not a heading. A heading text that repeats within
    the document gets the key ``<text> (2)``, ``<text> (3)`` and so on.

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
            title: str = match.group(2) or line.strip()
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
def parse_document(relative: str, text: str) -> DocumentRead:
    """Read what the matrix records of one architecture document from its text.

    Args:
        relative: The file, relative to the architecture root.
        text: The whole file.

    Returns:
        The document's lifecycle, catalog keys, heading texts and hash. A document whose front
        matter states no lifecycle is a draft; one that states a lifecycle other than effective,
        in-review or draft has none the matrix holds.

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
    headings: dict[str, str] = heading_texts(lines[start:])
    stated: str = scalars.get(LIFECYCLE_KEY, "")
    lifecycle: Lifecycle | None = (
        next((choice for choice in LIFECYCLES if choice == stated), None) if stated else LIFECYCLE_DRAFT
    )
    titles: list[str] = [key for key in headings if key != PREAMBLE and headings[key].startswith("# ")]
    subject: str | None = scalars.get("subject") or None
    return DocumentRead(
        path=relative,
        title=(titles[0] if titles else "") or subject or Path(relative).stem,
        lifecycle=lifecycle,
        lifecycle_stated=bool(stated),
        section=_section(relative),
        view_type=scalars.get("view_type") or None,
        scope=scalars.get("scope") or None,
        subject=subject,
        shows=shows,
        headings=tuple(key for key in headings if key != PREAMBLE),
        digest=hashlib.sha256(text.encode()).hexdigest(),
    )


def _may_be_document(relative: str) -> bool:
    """Tell whether a path under the architecture root can be a document the matrix holds.

    Returns:
        True for a Markdown file under the architecture root that is outside the folders of the
        built and target versions.

    """
    given: PurePosixPath = PurePosixPath(relative)
    return (
        relative.endswith(MARKDOWN_SUFFIX)
        and not given.is_absolute()
        and bool(given.parts)
        and given.parts[0] not in VERSION_FOLDERS
    )


def _is_document(document: DocumentRead) -> bool:
    """Tell whether a file read is an architecture document the matrix holds.

    Returns:
        True for every file under the arc42 folder, and for any other file whose front matter
        states the catalog: a view type, a scope, a subject or the names it shows.

    """
    return document.path.startswith(ARC42_FOLDER + "/") or any(
        (document.view_type, document.scope, document.subject, document.shows),
    )


def _candidates(root: Path) -> list[str]:
    """List the files under the architecture root that can be documents.

    Returns:
        Each Markdown file's path relative to the root, outside the built and target versions.

    """
    return [
        relative
        for relative in (relative_path(path, root) for path in root.rglob("*" + MARKDOWN_SUFFIX) if path.is_file())
        if _may_be_document(relative)
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_documents(arch: Path, paths: Sequence[str] | None = None) -> list[DocumentRead]:
    """Read architecture documents from the vault.

    Args:
        arch: The architecture root inside the vault.
        paths: The documents to read, relative to the architecture root; None reads every
            document. A path that is not an architecture document, or no longer exists, is left
            out.

    Returns:
        The documents read, in path order.

    Raises:
        MatrixError: A document cannot be read.

    """
    root: Path = arch.expanduser().resolve()
    wanted: list[str] = sorted(_candidates(root)) if paths is None else sorted(set(paths))
    documents: list[DocumentRead] = []
    relative: str
    for relative in wanted:
        if not _may_be_document(relative) or not (root / relative).is_file():
            continue
        try:
            text: str = (root / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            message: str = f"cannot read the document {root / relative}: {error}"
            raise MatrixError(message) from error
        document: DocumentRead = parse_document(relative, text)
        if _is_document(document):
            documents.append(document)
    return documents


def _document_entry(document: DocumentRead, lifecycle: Lifecycle, existing: Entry | None) -> Entry:
    """Build the entry of a document from the document as it is now.

    Returns:
        The entry: the document's front matter, heading texts and hash, with the aliases and the
        purpose the entry already has.

    """
    headings: list[JsonValue] = list(document.headings)
    attributes: dict[str, JsonValue] = {"lifecycle": lifecycle, "headings": headings, "hash": document.digest}
    if document.section is not None:
        attributes["section"] = document.section
    if document.view_type is not None:
        attributes["viewType"] = document.view_type
    if document.scope is not None:
        attributes["scope"] = document.scope
    if document.subject is not None:
        attributes["subject"] = document.subject
    return Entry(
        id=make_id(KIND_DOCUMENT, document.path),
        kind=KIND_DOCUMENT,
        name=document.title,
        side=SIDE_ARCHITECTURE,
        aliases=() if existing is None else existing.aliases,
        purpose="" if existing is None else existing.purpose,
        attributes=attributes,
    )


def _name_index(matrix: Matrix) -> dict[str, list[EntryId]]:
    """Index the entries a document may describe by every name they answer to.

    A document describes what the architecture states. A name that entries on both sides answer
    to is therefore indexed to the architecture-side entries only; a name only repository-side
    entries answer to is indexed to those.

    Returns:
        Each name and alias, as names are compared, with the ids of the entries that have it.

    """
    sided: dict[str, list[Entry]] = {}
    entry: Entry
    for entry in matrix.entries(DESCRIBED_KINDS):
        key: str
        for key in sorted({name_key(entry.name), *(name_key(alias) for alias in entry.aliases)}):
            sided.setdefault(key, []).append(entry)
    index: dict[str, list[EntryId]] = {}
    found: list[Entry]
    for key, found in sided.items():
        stated: list[Entry] = [held for held in found if held.side == AUTHORITY_SIDE] or found
        index[key] = [held.id for held in stated]
    return index


def _describe(
    matrix: Matrix,
    document: DocumentRead,
    index: Mapping[str, Sequence[EntryId]],
    result: DocumentsSynced,
) -> None:
    """Join a document to each entry its ``shows`` and ``subject`` name.

    A name that is the name or an alias of exactly one entry gets one ``describedBy`` from that
    entry, unless the entry is already described by the document. A name no entry has, and a
    name more than one entry has, is reported and joins nothing. The relationship is on the
    architecture side and names no heading: the front matter states the document, not a heading.
    """
    target: EntryId = make_id(KIND_DOCUMENT, document.path)
    names: list[str] = [*document.shows, *([] if document.subject is None else [document.subject])]
    name: str
    for name in dict.fromkeys(names):
        found: Sequence[EntryId] = index.get(name_key(name), ())
        if not found:
            result["unresolved"].append({"document": document.path, "name": name})
        elif len(found) > 1:
            result["ambiguous"].append({"document": document.path, "name": name, "entries": sorted(found)})
        elif all(held.end != target for held in matrix.outgoing(found[0], (REL_DESCRIBED_BY,))):
            matrix.link(Relationship(kind=REL_DESCRIBED_BY, start=found[0], end=target, side=SIDE_ARCHITECTURE))
            result["described"].append({"entry": found[0], "document": target})


def _document_paths(matrix: Matrix) -> list[str]:
    """List the documents the matrix holds an entry for.

    Returns:
        Each document entry's path relative to the architecture root, in path order.

    """
    return sorted(entry.id.partition(":")[2] for entry in matrix.entries((KIND_DOCUMENT,)))


def _apply_documents(matrix: Matrix, arch: Path, wanted: Sequence[str]) -> DocumentsSynced:
    """Correct the document entries of the matrix for some paths.

    Returns:
        What was added, changed and removed, the relationships added and the names that joined
        nothing.

    """
    read: dict[str, DocumentRead] = {document.path: document for document in read_documents(arch, wanted)}
    index: dict[str, list[EntryId]] = _name_index(matrix)
    result: DocumentsSynced = {
        "read": len(read),
        "added": [],
        "changed": [],
        "removed": [],
        "described": [],
        "unresolved": [],
        "ambiguous": [],
        "lifecycleNotStated": sorted(path for path, document in read.items() if not document.lifecycle_stated),
        "leftOut": [],
    }
    path: str
    for path in sorted(set(wanted)):
        if not _may_be_document(path):
            result["leftOut"].append(path)
            continue
        document: DocumentRead | None = read.get(path)
        key: EntryId = make_id(KIND_DOCUMENT, path)
        existing: Entry | None = matrix.find(key)
        if document is None or document.lifecycle is None:
            if document is not None or (arch / path).is_file():
                result["leftOut"].append(path)
            if existing is not None:
                matrix.remove(key)
                result["removed"].append(path)
            continue
        entry: Entry = _document_entry(document, document.lifecycle, existing)
        if entry != existing:
            matrix.put(entry)
            result["added" if existing is None else "changed"].append(path)
        _describe(matrix, document, index, result)
    return result


def _named_paths(arch: Path, paths: Sequence[str]) -> list[str]:
    """Name the files a caller gave the way the matrix does: relative to the architecture root.

    Returns:
        Each file's path relative to the architecture root, once, in path order; a file given
        relative is taken as relative to the architecture root.

    Raises:
        MatrixRefusedError: A file is outside the architecture root.

    """
    named: set[str] = set()
    name: str
    for name in paths:
        given: Path = Path(name).expanduser()
        located: Path = (given if given.is_absolute() else arch / given).resolve()
        if not located.is_relative_to(arch):
            message: str = f"the document {name} is outside the architecture root {arch}"
            raise MatrixRefusedError(message)
        named.add(located.relative_to(arch).as_posix())
    return sorted(named)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def sync_documents(matrix: Matrix, arch: Path, *, paths: Sequence[str] | None = None) -> DocumentsSynced:
    """Bring the document entries and their ``describedBy`` relationships up to date with the vault.

    Each architecture document that is effective, in review or draft has one entry on the architecture
    side holding its front matter, its heading texts and its hash, and is joined by
    ``describedBy`` to each entry its ``shows`` and ``subject`` name. The entry of a document
    that is gone, or is no longer of one of those lifecycles, is removed with its relationships.

    With ``paths``, exactly those files are looked at: one that is gone loses its entry, and no
    other entry changes. Without, every document under the architecture root is read and every
    document entry the matrix holds is looked at, so the entry of any document that is gone is
    removed. An entry whose document is as the matrix records it is left as it is. A document
    that cannot be read raises ``MatrixError``, and a path outside the architecture root raises
    ``MatrixRefusedError``.

    Args:
        matrix: The matrix, changed in place.
        arch: The architecture root inside the vault.
        paths: The files to read: absolute, or relative to the architecture root. None reads
            every document.

    Returns:
        What the read did.

    Raises:
        MatrixError: The architecture root is not a directory.

    """
    root: Path = arch.expanduser().resolve()
    if not root.is_dir():
        message: str = f"the architecture root {arch} is not a directory"
        raise MatrixError(message)
    if paths is not None:
        return _apply_documents(matrix, root, _named_paths(root, paths))
    return _apply_documents(matrix, root, sorted({*_candidates(root), *_document_paths(matrix)}))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def set_lifecycle(vault: Path, relative: str, lifecycle: Lifecycle) -> bool:
    """Write a document's lifecycle into its front matter, the one place that states it.

    This is the only write this module makes to the vault. It changes the one front matter line
    and nothing of the document's body. The document's entry mirrors the line at the next
    ``sync-documents``.

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
    if at and _scalar(lines[at].partition(":")[2]) == lifecycle:
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


def _prd_stems(record: JsonObject) -> tuple[str, ...]:
    """Read the PRD file stems an Epic's ``prd:`` labels name.

    Returns:
        What follows the prefix in each such label, lower-cased, once, in the order beads lists
        the labels; empty for a record with no such label.

    """
    labels: BeadValue = record.get("labels")
    stems: list[str] = []
    if isinstance(labels, list):
        label: BeadValue
        for label in labels:
            stated: str = label.strip().casefold() if isinstance(label, str) else ""
            if stated.startswith(PRD_LABEL_PREFIX) and stated[len(PRD_LABEL_PREFIX) :]:
                stems.append(stated[len(PRD_LABEL_PREFIX) :])
    return tuple(dict.fromkeys(stems))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_epics(control: Path | None = None, bead: str | None = None) -> list[EpicBead]:
    """Ask beads for the open Epics, or for one Epic.

    Args:
        control: The control repository, whose beads database holds the Epics; None reads the
            one the driver's environment names.
        bead: The one Epic to read, whatever its status; None reads every Epic that is not closed.

    Returns:
        The Epics, each with its title and the PRD file stems its ``prd:`` labels name, in id
        order.

    Raises:
        MatrixError: Beads could not be read, or ``bead`` was given and is not an Epic.

    """
    message: str
    try:
        graph: beadgraph.Graph = beadgraph.load(control)
    except beadgraph.GraphError as error:
        message = f"cannot read the Epic beads: {error}"
        raise MatrixError(message) from error
    stems: dict[str, tuple[str, ...]] = {}
    record: JsonObject
    for record in graph.records:
        held: beadgraph.Bead = beadgraph.bead_of(record)
        if held.kind == EPIC_TYPE:
            stems[held.id] = _prd_stems(record)
    if bead is None:
        return sorted(
            (
                EpicBead(bead=epic.id, title=epic.title, prd_stems=stems.get(epic.id, ()))
                for epic in graph.of_kind(EPIC_TYPE)
                if not epic.closed
            ),
            key=lambda epic: epic.bead,
        )
    found: beadgraph.Bead | None = graph.beads.get(bead)
    if found is None or found.kind != EPIC_TYPE:
        message = f"{bead} is not an Epic"
        raise MatrixError(message)
    return [EpicBead(bead=found.id, title=found.title, prd_stems=stems.get(found.id, ()))]


def _requirement_key(title: str) -> str:
    """Key one requirement by its heading.

    Returns:
        The identifier that opens the heading, else the slug of the heading.

    Raises:
        MatrixError: The heading holds no letter or digit to build a key from.

    """
    opened: re.Match[str] | None = _IDENTIFIER.match(title)
    if opened is not None:
        return opened.group(1)
    try:
        return slug(title)
    except ValueError as error:
        message: str = f"cannot key the requirement heading {title!r}: {error}"
        raise MatrixError(message) from error


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_requirements(text: str) -> list[RequirementRead]:
    """Read the requirements a PRD states.

    A requirement is one ``####`` heading under the ``## Requirements`` heading. Its group is
    the ``###`` heading above it. Its own text is its heading line and everything up to the next
    heading of its level or above. A ``#`` line inside a fenced code block is not a heading. A
    key that repeats within the PRD gets ``-2``, ``-3`` and so on, so the same PRD yields the
    same keys on every read. A heading with no letter or digit raises ``MatrixError``.

    Args:
        text: The whole PRD file.

    Returns:
        The requirements, in document order.

    """
    found: list[tuple[str, str, list[str]]] = []
    inside: bool = False
    group: str = ""
    own: list[str] | None = None
    fenced: bool = False
    line: str
    for line in text.splitlines():
        if line.lstrip().startswith(CODE_FENCES):
            fenced = not fenced
        match: re.Match[str] | None = None if fenced else _HEADING.match(line)
        level: int = 0 if match is None else len(match.group(1))
        title: str = "" if match is None else match.group(2)
        if match is not None and level <= SECTION_LEVEL:
            inside = level == SECTION_LEVEL and name_key(title) == REQUIREMENTS_HEADING
            group, own = "", None
        elif inside and level == GROUP_LEVEL:
            group, own = title, None
        elif inside and level == REQUIREMENT_LEVEL and title:
            own = [line.rstrip()]
            found.append((title, group, own))
        elif own is not None:
            own.append(line.rstrip())
    seen: dict[str, int] = {}
    requirements: list[RequirementRead] = []
    lines: list[str]
    for title, group, lines in found:
        key: str = _requirement_key(title)
        seen[key] = seen.get(key, 0) + 1
        requirements.append(
            RequirementRead(
                key=key if seen[key] == 1 else f"{key}-{seen[key]}",
                name=title,
                group=group,
                digest=hashlib.sha256("\n".join(lines).strip("\n").encode()).hexdigest(),
            ),
        )
    return requirements


def _recorded_prd(entry: Entry | None) -> str | None:
    """Read the PRD path an epic entry records.

    Returns:
        The path relative to the vault root, or None when there is no entry or it records none.

    """
    prd: JsonValue = None if entry is None else entry.attributes.get("prd")
    path: JsonValue = prd.get("path") if isinstance(prd, dict) else None
    return path if isinstance(path, str) and path else None


def _given_prd(prd: str, vault: Path) -> str:
    """Name the PRD file a caller gave the way the matrix does: relative to the vault root.

    Returns:
        The file's path relative to the vault root; a file given relative is taken as relative
        to the vault root.

    Raises:
        MatrixRefusedError: The file is outside the vault.

    """
    given: Path = Path(prd).expanduser()
    located: Path = (given if given.is_absolute() else vault / given).resolve()
    if not located.is_relative_to(vault):
        message: str = f"the PRD {prd} is outside the vault {vault}"
        raise MatrixRefusedError(message)
    return located.relative_to(vault).as_posix()


def _labelled_prd(epic: EpicBead, files: Mapping[str, Sequence[str]]) -> tuple[str | None, str]:
    """Find the PRD file an Epic's ``prd:`` labels name.

    Returns:
        The file's path relative to the vault root and an empty reason, when the labels name
        exactly one file of the PRD folder; otherwise None and why no file is named.

    """
    if not epic.prd_stems:
        return None, "the matrix records no PRD for it and it has no prd: label; give its PRD"
    named: list[str] = sorted({path for stem in epic.prd_stems for path in files.get(stem, ())})
    if len(named) == 1:
        return named[0], ""
    labels: str = ", ".join(PRD_LABEL_PREFIX + stem for stem in epic.prd_stems)
    if not named:
        return None, f"no file of the PRD folder has the name its label states ({labels})"
    return None, f"its labels ({labels}) name more than one PRD file: {', '.join(named)}"


def _epic_entry(epic: EpicBead, prd: tuple[str, str] | None, existing: Entry | None) -> Entry:
    """Build the entry of an Epic from its bead and its PRD file.

    Returns:
        The entry, on the architecture side: the Epic's title and everything else the entry
        already has; with a PRD (its path and its hash), also the PRD's path and hash and the
        PRD file's stem among its aliases.

    """
    aliases: tuple[str, ...] = () if existing is None else existing.aliases
    attributes: dict[str, JsonValue] = {} if existing is None else dict(existing.attributes)
    if prd is not None:
        stem: str = Path(prd[0]).stem
        if name_key(stem) not in {name_key(epic.title), *(name_key(alias) for alias in aliases)}:
            aliases = (*aliases, stem)
        attributes["prd"] = {"path": prd[0], "hash": prd[1]}
    return Entry(
        id=make_id(KIND_EPIC, epic.bead),
        kind=KIND_EPIC,
        name=epic.title,
        side=SIDE_ARCHITECTURE,
        aliases=aliases,
        purpose="" if existing is None else existing.purpose,
        attributes=attributes,
    )


def _carry_over(matrix: Matrix, gone: Sequence[EntryId], arrived: Mapping[EntryId, RequirementRead]) -> list[Carried]:
    """Re-key each requirement that was replaced one for one within its group.

    When exactly one requirement left a group and exactly one arrived in it, the one that left
    takes the id of the one that arrived, so its relationships carry over.

    Returns:
        Each requirement re-keyed, with the id it had and the id it has now.

    """
    leaving: dict[str, list[EntryId]] = {}
    arriving: dict[str, list[EntryId]] = {}
    key: EntryId
    for key in gone:
        group: JsonValue = matrix.entry(key).attributes.get("group")
        leaving.setdefault(group if isinstance(group, str) else "", []).append(key)
    read: RequirementRead
    for key, read in arrived.items():
        arriving.setdefault(read.group, []).append(key)
    carried: list[Carried] = []
    name: str
    for name in sorted(leaving):
        if len(leaving[name]) == 1 and len(arriving.get(name, [])) == 1:
            matrix.rename(leaving[name][0], arriving[name][0])
            carried.append({"was": leaving[name][0], "now": arriving[name][0]})
    return carried


def _sync_requirements(matrix: Matrix, epic: EntryId, bead: str, text: str, result: EpicsSynced) -> None:
    """Bring the requirement entries of one Epic up to date with its PRD.

    Each requirement the PRD states has one entry joined to the Epic by ``hasRequirement``, both
    on the architecture side. A
    requirement replaced one for one within its group keeps its relationships
    (:func:`_carry_over`); any other requirement the PRD no longer states is removed and reported
    with the relationships removed with it.
    """
    current: dict[EntryId, RequirementRead] = {
        make_id(KIND_REQUIREMENT, f"{bead}/{read.key}"): read for read in parse_requirements(text)
    }
    held: list[EntryId] = [relationship.end for relationship in matrix.outgoing(epic, (REL_HAS_REQUIREMENT,))]
    gone: list[EntryId] = [key for key in held if key not in current]
    arrived: dict[EntryId, RequirementRead] = {key: read for key, read in current.items() if key not in held}
    carried: list[Carried] = _carry_over(matrix, gone, arrived)
    result["requirementsCarried"].extend(carried)
    replaced: set[EntryId] = {pair["was"] for pair in carried}
    key: EntryId
    for key in gone:
        if key in replaced:
            continue
        lost: list[Relationship] = [*matrix.outgoing(key), *matrix.incoming(key)]
        result["requirementsRemoved"].append({
            "id": key,
            "name": matrix.entry(key).name,
            "relationships": [relationship_json(each) for each in lost if each.kind != REL_HAS_REQUIREMENT],
        })
        matrix.remove(key)
    read: RequirementRead
    for key, read in current.items():
        existing: Entry | None = matrix.find(key)
        attributes: dict[str, JsonValue] = {"hash": read.digest}
        if read.group:
            attributes["group"] = read.group
        entry: Entry = Entry(
            id=key,
            kind=KIND_REQUIREMENT,
            name=read.name,
            side=SIDE_ARCHITECTURE,
            aliases=() if existing is None else existing.aliases,
            purpose="" if existing is None else existing.purpose,
            attributes=attributes,
        )
        if existing is None or not same_content(existing, entry):
            matrix.put(entry)
            result["requirementsAdded" if existing is None else "requirementsChanged"].append(key)
        if all(relationship.end != key for relationship in matrix.outgoing(epic, (REL_HAS_REQUIREMENT,))):
            matrix.link(Relationship(kind=REL_HAS_REQUIREMENT, start=epic, end=key, side=SIDE_ARCHITECTURE))


def _put_epic(matrix: Matrix, entry: Entry, existing: Entry | None, result: EpicsSynced) -> None:
    """Record an Epic's entry when it differs from the one the matrix holds, and count it."""
    if entry == existing:
        result["unchanged"] += 1
        return
    matrix.put(entry)
    result["created" if existing is None else "refreshed"].append(entry.id)


def _sync_epic(matrix: Matrix, epic: EpicBead, source: PrdSource, result: EpicsSynced) -> None:
    """Create or refresh the entry of one Epic and its requirements.

    The PRD is the file the caller gave, else the one the Epic's entry already records, else the
    one its ``prd:`` labels name. An Epic with none of them, or whose PRD cannot be read, gets
    an entry that records no PRD, or keeps the entry it has, and is reported; its requirement
    entries are left as they are.
    """
    key: EntryId = make_id(KIND_EPIC, epic.bead)
    existing: Entry | None = matrix.find(key)
    relative: str | None = _recorded_prd(existing) if source.given is None else _given_prd(source.given, source.vault)
    reason: str = ""
    if relative is None:
        relative, reason = _labelled_prd(epic, source.files)
    raw: bytes = b""
    text: str = ""
    if relative is not None:
        try:
            raw = (source.vault / relative).read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            reason = f"its PRD {relative} cannot be read: {error}"
    if relative is None or reason:
        kept: Entry = _epic_entry(epic, None, existing)
        _put_epic(matrix, kept, existing, result)
        result["noPrd"].append({"bead": epic.bead, "reason": reason})
        return
    _put_epic(matrix, _epic_entry(epic, (relative, hashlib.sha256(raw).hexdigest()), existing), existing, result)
    _sync_requirements(matrix, key, epic.bead, text, result)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def sync_epics(matrix: Matrix, epics: Sequence[EpicBead], prd_dir: Path, *, prd: str | None = None) -> EpicsSynced:
    """Give every Epic one entry with its PRD, and one requirement entry per requirement the PRD states.

    An Epic's PRD is the file ``prd`` names, else the file its entry already records, else the
    one file of the PRD folder whose stem its ``prd:`` labels name. The entry holds the Epic's
    title, the PRD's path in the vault and the hash of the file. Each ``####`` heading under the
    PRD's ``## Requirements`` heading is one requirement (:func:`parse_requirements`), keyed
    under the Epic's beads id and joined to the Epic by ``hasRequirement``. Everything recorded
    is on the architecture side. A requirement replaced one for one within its group keeps its
    relationships; any other requirement the PRD no longer states is removed and reported. An
    Epic whose PRD file is not known or cannot be read gets an entry that records no PRD and is
    listed under ``noPrd``. An entry whose Epic is not among ``epics`` is left as it is. A vault
    that is not a git repository raises ``MatrixError``.

    Args:
        matrix: The matrix, changed in place.
        epics: The Epics to give entries (:func:`read_epics`).
        prd_dir: The folder the PRD files are under, at any depth.
        prd: The PRD file of the one Epic given: absolute, or relative to the vault root. None
            takes each Epic's PRD from its entry, else from its labels.

    Returns:
        The epic entries created and refreshed, how many were already current, what changed
        among the requirements, the Epics with no PRD, and the PRD files no epic entry names.

    Raises:
        MatrixError: The PRD folder is not a directory.
        MatrixRefusedError: ``prd`` is given with other than one Epic, or is outside the vault.

    """
    message: str
    if not prd_dir.is_dir():
        message = f"the PRD folder {prd_dir} is not a directory"
        raise MatrixError(message)
    if prd is not None and len(epics) != 1:
        message = "a PRD file is given for exactly one Epic"
        raise MatrixRefusedError(message)
    vault: Path = vault_root(prd_dir)
    listed: list[str] = sorted(relative_path(path, vault) for path in prd_dir.rglob("*" + MARKDOWN_SUFFIX))
    files: dict[str, list[str]] = {}
    path: str
    for path in listed:
        files.setdefault(Path(path).stem.casefold(), []).append(path)
    result: EpicsSynced = {
        "created": [],
        "refreshed": [],
        "unchanged": 0,
        "requirementsAdded": [],
        "requirementsChanged": [],
        "requirementsCarried": [],
        "requirementsRemoved": [],
        "noPrd": [],
        "unnamedPrds": [],
    }
    source: PrdSource = PrdSource(vault=vault, given=prd, files=files)
    epic: EpicBead
    for epic in epics:
        _sync_epic(matrix, epic, source, result)
    named: set[str] = {held for held in map(_recorded_prd, matrix.entries((KIND_EPIC,))) if held is not None}
    result["unnamedPrds"] = [path for path in listed if path not in named]
    return result
