"""Seeding: fill an empty matrix from beads, the PRDs, the arc42 documents and the repositories.

The script steps, each one read over all of its inputs with no judgment in it:

- :func:`seed` (``seed``) writes an empty matrix file and runs the steps below in order: the
  Epics with their requirements and the arc42 documents (``matrixsync``), then
  :func:`seed_stacks`, :func:`seed_packages` and :func:`seed_inputs`.
- :func:`seed_stacks` (``seed-stacks``) records one stack per repository that is not deprecated
  and whose name the project's naming command reads as a repository that holds a stack.
- :func:`seed_packages` (``seed-packages``) records the package each library stack is
  distributed as, and the imports between stacks their ``pyproject.toml`` files state.
- :func:`seed_inputs` (``seed-inputs``) writes the batch files the seeding sessions are handed,
  each filled up to a session's reading allowance.
- :func:`list_proposed` (``seed-features --list``) lists the features the proposal files state.
- :func:`seed_apply` (``seed-apply``) records what the sessions wrote: every entry and
  relationship of a result file with the side the step states, or the features of the proposal
  files as the merge file names them.

Everything a repository shows is recorded on the repository side, and what the architecture
states never gives way to it. Nothing is seeded as verified. No step runs a ``cdk`` command,
reads a synthesized assembly or edits a repository.

A session writes these files, all JSON objects (:func:`seed_directory` names where):

- a result file of the architecture or the repository step: ``entries``, each with ``kind``,
  ``name`` and optionally ``id``, ``stack``, ``aliases``, ``purpose`` and ``attributes``; and
  ``relationships``, each with ``kind``, ``from``, ``to`` and optionally ``attributes``;
- a proposal file, one per PRD: ``epic`` and ``requirements``, each with ``requirement`` and
  ``features``, each with ``name``, ``purpose`` and ``documents``, each with ``document`` and
  ``heading``;
- the merge file: ``features``, each with ``name``, ``purpose`` and optionally ``aliases`` and
  ``proposed``, the proposed names that are this feature.
"""

import json
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal, TypedDict, assert_never

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "resource-naming" / "scripts"))
from matrix_contract import (
    AUTHORITY_SIDE,
    ENTRY_RULES,
    KIND_DOCUMENT,
    KIND_EPIC,
    KIND_EVENT,
    KIND_FEATURE,
    KIND_PACKAGE,
    KIND_REQUIREMENT,
    KIND_STACK,
    LOCK_DIRECTORY,
    REL_COVERS,
    REL_DESCRIBED_BY,
    REL_DISTRIBUTED_AS,
    REL_HAS_REQUIREMENT,
    REL_IMPORTS,
    REL_SERVED_BY,
    SIDE_ARCHITECTURE,
    SIDE_REPOSITORY,
    Entry,
    EntryId,
    EntryKind,
    JsonValue,
    MatrixError,
    Relationship,
    RelationshipKind,
    Side,
    entry_kind,
    json_value,
    relationship_kind,
    relationship_label,
)
from matrixstore import (
    DEFAULT_LOCK_WAIT,
    ID_SEPARATOR,
    STACK_SEPARATOR,
    Matrix,
    MatrixRefusedError,
    as_entry_id,
    create_matrix,
    make_id,
    name_key,
    read_matrix,
    relationship_id,
    repository_side_id,
    slug,
    update_matrix,
    write_text,
)
from matrixsync import (
    DocumentsSynced,
    EpicBead,
    EpicsSynced,
    program_output,
    read_epics,
    sync_documents,
    sync_epics,
    vault_root,
)
from naming_command import NamingCommandError, repository_type

type SeedStep = Literal["architecture", "repository", "features"]
type Outcome = Literal["created", "changed", "unchanged"]

STEP_ARCHITECTURE: Final[Literal["architecture"]] = "architecture"
STEP_REPOSITORY: Final[Literal["repository"]] = "repository"
STEP_FEATURES: Final[Literal["features"]] = "features"
SEED_STEPS: Final[tuple[SeedStep, ...]] = (STEP_ARCHITECTURE, STEP_REPOSITORY, STEP_FEATURES)
"""The seeding steps whose sessions write files that :func:`seed_apply` records."""
OUTCOME_CREATED: Final[Literal["created"]] = "created"
OUTCOME_CHANGED: Final[Literal["changed"]] = "changed"
OUTCOME_UNCHANGED: Final[Literal["unchanged"]] = "unchanged"
PLUGIN: Final[Path] = Path(__file__).resolve().parents[2]
POLYREPO_PARTS: Final[tuple[str, ...]] = ("skills", "polyrepo-repo", "scripts", "polyrepo.py")
"""Where the ``polyrepo`` tool is, under the plugin root."""
LIFECYCLE_DEPRECATED: Final = "deprecated"
LIBRARY_TYPE: Final = "lib"
"""The stack type of code other code imports."""
EXECUTION_IMPORTED: Final = "imported"
EXECUTION_EXECUTABLE: Final = "executable"
ORIGIN_PROJECT: Final = "project"
PURPOSE_NOT_STATED: Final = "The purpose is not stated."
"""The purpose of a stack no arc42 document gives a purpose for."""
ATTR_REPOSITORY: Final = "repository"
ATTR_APP: Final = "app"
ATTR_EXECUTION_USE: Final = "executionUse"
ATTR_ORIGIN: Final = "origin"
ATTR_THROUGH: Final = "through"
ATTR_HEADING: Final = "heading"
ATTR_VIA: Final = "via"
ATTR_LIFECYCLE: Final = "lifecycle"
ATTR_SUBJECT: Final = "subject"
ATTR_SECTION: Final = "section"
ATTR_PRD: Final = "prd"
ATTR_PRD_PATH: Final = "path"
LIFECYCLE_EFFECTIVE: Final = "effective"
ITEM_ID: Final = "id"
"""The member that identifies one object of a list attribute, such as one thing a feature provides."""
VERIFIED_MEMBER: Final = "verified"
PYPROJECT: Final = "pyproject.toml"
READING_ALLOWANCE: Final = 240_000
"""The bytes of text one seeding session reads: about 30% of its context."""
PRD_SHARE: Final[tuple[int, int]] = (2, 3)
"""The part of the allowance a batch of PRDs fills; the rest is for what ``find`` returns."""
STACK_CAP: Final = 40_000
"""The most bytes one stack counts as: a session reads its CDK app, handlers and file listing."""
SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".toml"})
"""The suffixes of the tracked files a stack's source size counts."""
SEED_FOLDER: Final = "seed"
BATCH_FOLDER: Final = "batches"
RESULT_FOLDER: Final = "results"
PROPOSAL_FOLDER: Final = "proposals"
MERGE_FILE: Final = "merge.json"
JSON_SUFFIX: Final = ".json"
BATCH_SEPARATOR: Final = "-"
"""What joins a step's name and a batch's number in the name of a batch file and of its result file."""
NAMED_ID_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_STACK, KIND_PACKAGE, KIND_EVENT})
"""The kinds whose id is the kind and the entry's name as written."""
STATED_ID_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_EPIC, KIND_REQUIREMENT, KIND_DOCUMENT})
"""The kinds the script steps record from beads and the vault; no session's file states one."""
RESULT_HOLDS: Final = (
    'One JSON object: "entries", a list of {"kind", "name", "aliases", "purpose", "attributes"}, and '
    '"relationships", a list of {"kind", "from", "to", "attributes"}. "from" and "to" are entry ids. An entry '
    'may state its "id"; otherwise it is built from the kind and the name. Nothing carries "verified".'
)
REPOSITORY_RESULT_HOLDS: Final = (
    RESULT_HOLDS + ' A component, an infrastructure entry or a layer found in a repository states "stack", the '
    "name of the stack that holds it; its id is then <kind>:<stack name>/<slug of the name>."
)
FEATURE_IS: Final = (
    " A feature is one discrete capability of the product, named as something the product can do, recorded once: "
    "no two features name the same capability, and one feature commonly serves several requirements, of one Epic "
    "or of several. A condition, quality or rule about how a capability behaves is a requirement that capability's "
    "feature serves, not a feature of its own."
)
"""What a feature is, in brief, for a seeding session: the matrix requirements define it (section 3.1.1)."""
PROPOSAL_HOLDS: Final = (
    'One JSON object per PRD, in the file named: "epic", the beads id, and "requirements", a list of '
    '{"requirement", "features"} with one item per requirement listed here. "features" is a list of {"name", '
    '"purpose", "documents"}, and "documents" a list of {"document", "heading"}. A requirement no feature serves '
    'has "features": [], and a feature no document covers has "documents": [].' + FEATURE_IS
)
MERGE_HOLDS: Final = (
    'One JSON object: "features", a list of {"name", "purpose", "aliases", "proposed"}. "proposed" lists the '
    "proposed names that are this feature; the feature's own name need not be repeated in it. Every proposed "
    "name is in exactly one feature. Two proposed features are one feature when they name the same capability: "
    "the same part of the architecture would provide both. A proposed feature that bundles capabilities different "
    "parts of the architecture provide is not merged into one of them. A proposed feature that is a feature the "
    "matrix already holds takes that feature's name." + FEATURE_IS
)
_REQUIREMENT_NAME: Final[re.Pattern[str]] = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_NAME_SEPARATORS: Final[re.Pattern[str]] = re.compile(r"[-_.]+")


@dataclass(frozen=True, slots=True)
class Repository:
    """One repository as the ``polyrepo`` tool's inventory lists it."""

    name: str
    app: str
    lifecycle: str
    path: Path | None
    """The clone on this machine; None when the inventory names none."""


@dataclass(frozen=True, slots=True)
class Project:
    """What a repository's ``pyproject.toml`` states about its Python project."""

    name: str
    """The distribution name, as written."""
    dependencies: tuple[str, ...]
    """The names of the distributions it depends on, as names are compared."""


@dataclass(frozen=True, slots=True)
class StatedEntry:
    """One entry as a result file states it."""

    kind: EntryKind
    name: str
    id: str | None
    stack: str | None
    aliases: tuple[str, ...]
    purpose: str
    attributes: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class StatedRelationship:
    """One relationship as a result file states it."""

    kind: RelationshipKind
    start: str
    end: str
    attributes: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Anchor:
    """One document heading a proposal says covers a feature."""

    document: str
    heading: str


@dataclass(frozen=True, slots=True)
class ProposedFeature:
    """One feature a proposal file says serves a requirement."""

    name: str
    purpose: str
    documents: tuple[Anchor, ...]


@dataclass(frozen=True, slots=True)
class ProposedRequirement:
    """One requirement of a proposal file with the features proposed for it."""

    requirement: str
    features: tuple[ProposedFeature, ...]


@dataclass(frozen=True, slots=True)
class Proposal:
    """One proposal file: the features proposed for the requirements of one PRD."""

    file: Path
    epic: str
    requirements: tuple[ProposedRequirement, ...]


@dataclass(frozen=True, slots=True)
class MergedFeature:
    """One feature of the merge file: what several proposed features are."""

    name: str
    purpose: str
    aliases: tuple[str, ...]
    proposed: tuple[str, ...]


class Refusal(TypedDict):
    """One thing a seeding step could not read or record, and why."""

    file: str
    item: str
    reason: str


class StacksSeeded(TypedDict):
    """What :func:`seed_stacks` did: also what ``seed-stacks`` prints."""

    created: list[EntryId]
    changed: list[EntryId]
    unchanged: int
    noType: list[str]
    """The repositories whose name ends in no listed type; none got a stack."""
    deprecated: list[str]
    refused: list[Refusal]


class PackagesSeeded(TypedDict):
    """What :func:`seed_packages` did: also what ``seed-packages`` prints."""

    packages: list[EntryId]
    """The packages recorded or already held, in id order."""
    imports: list[str]
    """Each import between stacks recorded or already held, as ``<stack> imports <stack>``."""
    noProject: list[EntryId]
    """The stacks whose repository has no ``pyproject.toml`` that states a project name."""
    refused: list[Refusal]


class BatchWritten(TypedDict):
    """One batch file :func:`seed_inputs` wrote."""

    file: str
    items: int
    bytes: int


class InputsWritten(TypedDict):
    """What :func:`seed_inputs` did: also what ``seed-inputs`` prints."""

    directory: str
    allowance: int
    architecture: list[BatchWritten]
    features: list[BatchWritten]
    repository: list[BatchWritten]
    merge: str
    """Where the merge file of the feature proposals is to be written."""
    notSized: list[str]
    """The documents, PRDs and stacks left out of every batch because their files could not be found."""


class ProposedName(TypedDict):
    """One proposed feature, as ``seed-features --list`` prints it."""

    name: str
    purpose: str
    requirements: int
    """How many requirements, across the proposal files, it is proposed for."""


class ProposedFeatures(TypedDict):
    """What :func:`list_proposed` returns: also what ``seed-features --list`` prints."""

    files: int
    features: list[ProposedName]
    """Each proposed feature once, by name as names are compared, in name order."""
    requirementsNotProposed: list[EntryId]
    """The requirements the matrix holds that no proposal file lists."""
    mergeHolds: str
    refused: list[Refusal]


class Applied(TypedDict):
    """What :func:`seed_apply` did: also what ``seed-apply`` prints."""

    step: SeedStep
    files: list[str]
    entriesCreated: list[EntryId]
    entriesChanged: list[EntryId]
    entriesUnchanged: int
    relationshipsAdded: int
    relationshipsChanged: int
    relationshipsUnchanged: int
    unmerged: list[str]
    """The proposed features the merge file names nowhere; nothing was recorded for them."""
    refused: list[Refusal]
    """Each file that could not be read and each write that could not be made."""


class Seeded(TypedDict):
    """What :func:`seed` did: also what ``seed`` prints."""

    matrix: str
    epics: EpicsSynced
    documents: DocumentsSynced
    stacks: StacksSeeded
    packages: PackagesSeeded
    inputs: InputsWritten


def _read_object(path: Path) -> dict[str, JsonValue]:
    """Read a JSON file a session or a tool wrote, as one object.

    Returns:
        The decoded object.

    Raises:
        MatrixError: The file cannot be read, is not JSON, or is not a JSON object.

    """
    message: str
    try:
        text: str = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        message = f"cannot read {path}: {error}"
        raise MatrixError(message) from error
    return _decode_object(text, str(path))


def _decode_object(text: str, where: str) -> dict[str, JsonValue]:
    """Decode JSON text as one object.

    Returns:
        The decoded object.

    Raises:
        MatrixError: The text is not JSON, or is not a JSON object.

    """
    message: str
    try:
        decoded: object = json.loads(text)
        typed: JsonValue = json_value(decoded)
    except (json.JSONDecodeError, TypeError) as error:
        message = f"{where} is not JSON: {error}"
        raise MatrixError(message) from error
    if not isinstance(typed, dict):
        message = f"{where} is not a JSON object"
        raise MatrixError(message)
    return typed


def _text(value: JsonValue, where: str) -> str:
    """Narrow a member of a file to non-empty text.

    Returns:
        The text, stripped.

    Raises:
        MatrixError: The member is not a string, or is empty.

    """
    if not isinstance(value, str) or not value.strip():
        message: str = f"{where} is not a non-empty string"
        raise MatrixError(message)
    return value.strip()


def _optional_text(value: JsonValue, where: str) -> str:
    """Narrow a member of a file that may be left out to text.

    Returns:
        The text, stripped; empty when the member is absent.

    Raises:
        MatrixError: The member is present and is not a string.

    """
    if value is None:
        return ""
    if not isinstance(value, str):
        message: str = f"{where} is not a string"
        raise MatrixError(message)
    return value.strip()


def _texts(value: JsonValue, where: str) -> tuple[str, ...]:
    """Narrow a member of a file that may be left out to a list of non-empty strings.

    Returns:
        The strings, stripped, in order and without repeats; empty when the member is absent.

    Raises:
        MatrixError: The member is present and is not a list of strings.

    """
    if value is None:
        return ()
    if not isinstance(value, list):
        message: str = f"{where} is not a list"
        raise MatrixError(message)
    return tuple(dict.fromkeys(_text(item, where) for item in value))


def _objects(value: JsonValue, where: str) -> list[dict[str, JsonValue]]:
    """Narrow a member of a file that may be left out to a list of objects.

    Returns:
        The objects, in order; empty when the member is absent.

    Raises:
        MatrixError: The member is present and is not a list of objects.

    """
    if value is None:
        return []
    if not isinstance(value, list):
        message: str = f"{where} is not a list"
        raise MatrixError(message)
    items: list[dict[str, JsonValue]] = []
    item: JsonValue
    for item in value:
        if not isinstance(item, dict):
            message = f"{where} holds an item that is not an object"
            raise MatrixError(message)
        items.append(item)
    return items


def _attributes(raw: Mapping[str, JsonValue], where: str) -> dict[str, JsonValue]:
    """Read the attributes an item of a result file states.

    Returns:
        The attributes; empty when the item states none.

    Raises:
        MatrixError: ``attributes`` is not an object, or the item carries the verified mark.

    """
    message: str
    if VERIFIED_MEMBER in raw:
        message = f"{where} carries the verified mark, and nothing is seeded as verified"
        raise MatrixError(message)
    stated: JsonValue = raw.get("attributes")
    if stated is None:
        return {}
    if not isinstance(stated, dict):
        message = f"{where}: attributes is not an object"
        raise MatrixError(message)
    return stated


def _refusal(file: Path | str, item: str, error: Exception | str) -> Refusal:
    """Describe one thing a step could not read or record.

    Returns:
        The file, the item and the reason.

    """
    return {"file": str(file), "item": item, "reason": str(error)}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def seed_directory(matrix_file: Path) -> Path:
    """Name the folder the seeding files of a matrix file are in.

    Under it, ``batches`` holds the batch files :func:`seed_inputs` writes, ``results`` the
    result files of the architecture and repository sessions, ``proposals`` one proposal file
    per PRD, and ``merge.json`` is the merge file.

    Args:
        matrix_file: The matrix file.

    Returns:
        The ``seed`` folder of the contract's state folder beside the matrix.

    Raises:
        TypeError: ``matrix_file`` is not a path.

    """
    if not isinstance(matrix_file, Path):
        message: str = "the matrix file must be a path"
        raise TypeError(message)
    return matrix_file.parent / LOCK_DIRECTORY / SEED_FOLDER


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_types(repositories: Sequence[Repository], environ: Mapping[str, str]) -> dict[str, str]:
    """Ask the project's naming command which repositories hold a stack, and of what type.

    Args:
        repositories: The repositories (:func:`read_repositories`); deprecated ones are not asked.
        environ: The environment the naming command is read from.

    Returns:
        The type token of each repository the naming command reads as a repository that holds a
        stack, by repository name.

    Raises:
        MatrixError: No naming command is configured, or it does not answer.

    """
    types: dict[str, str] = {}
    for repository in repositories:
        if repository.lifecycle == LIFECYCLE_DEPRECATED:
            continue
        try:
            kind: str | None = repository_type(repository.name, environ)
        except NamingCommandError as error:
            raise MatrixError(str(error)) from error
        if kind is not None:
            types[repository.name] = kind
    return types


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_repositories(text: str) -> list[Repository]:
    """Read the repositories from what ``polyrepo inventory --json`` printed.

    Text that is not the inventory object, or a repository that states no name, raises
    ``MatrixError`` from the reader that finds it.

    Args:
        text: The JSON text.

    Returns:
        Every repository listed, in name order.

    Raises:
        TypeError: ``text`` is not a string.

    """
    if not isinstance(text, str):
        message: str = "the inventory must be text"
        raise TypeError(message)
    repositories: list[Repository] = []
    record: dict[str, JsonValue]
    for record in _objects(_decode_object(text, "the polyrepo inventory").get("repos"), "the inventory's repos"):
        name: str = _text(record.get("name"), "a repository's name")
        path: str = _optional_text(record.get("path"), f"the path of {name}")
        repositories.append(
            Repository(
                name=name,
                app=_optional_text(record.get("space"), f"the app of {name}"),
                lifecycle=_optional_text(record.get("lifecycle"), f"the lifecycle of {name}"),
                path=Path(path) if path else None,
            ),
        )
    return sorted(repositories, key=lambda repository: repository.name)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_repositories(control: Path) -> list[Repository]:
    """Ask the ``polyrepo`` tool for every known repository.

    The tool reads its own records and each clone; it fetches nothing and changes nothing. A
    tool that is missing or fails raises ``MatrixError`` from ``program_output``.

    Args:
        control: The control repository, which the tool is run in.

    Returns:
        The name, app, lifecycle and clone path of every repository, in name order.

    Raises:
        MatrixError: ``control`` is not a directory.

    """
    if not control.is_dir():
        message: str = f"the control repository {control} is not a directory"
        raise MatrixError(message)
    script: Path = PLUGIN.joinpath(*POLYREPO_PARTS)
    return parse_repositories(program_output("uv", ["run", str(script), "inventory", "--no-fetch", "--json"], control))


def _listed(held: Sequence[JsonValue], item: JsonValue) -> bool:
    """Tell whether a list attribute already holds an item.

    Returns:
        True when the list holds the item, or an object with the item's ``id``.

    """
    identity: JsonValue = item.get(ITEM_ID) if isinstance(item, dict) else None
    return item in held or (
        identity is not None and any(isinstance(kept, dict) and kept.get(ITEM_ID) == identity for kept in held)
    )


def _merged(held: Entry, stated: Entry) -> tuple[Entry, list[str]]:
    """Add what a step states about an entry to the entry the matrix holds.

    The held entry keeps its id, its name and its verified mark. A stated name that differs
    joins the aliases. A stated purpose fills a purpose that is empty or not stated. An attribute
    the entry lacks is added, the items of a list join the held list, and the members of an
    object the held object lacks are added. Where both state another value, the held one stays,
    unless the stated entry is on the authority side and the held one is not: the architecture's
    value then replaces the hint, and the entry moves to the authority side. An entry on the
    authority side never moves off it, and a hint never changes its purpose.

    Returns:
        The entry to record, and one sentence per stated value that was not taken.

    """
    over: bool = stated.side == AUTHORITY_SIDE and held.side != AUTHORITY_SIDE
    under: bool = stated.side != AUTHORITY_SIDE and held.side == AUTHORITY_SIDE
    kept: list[str] = []
    attributes: dict[str, JsonValue] = dict(held.attributes)
    name: str
    value: JsonValue
    for name, value in stated.attributes.items():
        current: JsonValue = attributes.get(name)
        if name not in attributes:
            attributes[name] = value
        elif isinstance(current, list) and isinstance(value, list):
            attributes[name] = [*current, *(item for item in value if not _listed(current, item))]
        elif isinstance(current, dict) and isinstance(value, dict):
            attributes[name] = {**current, **value} if over else {**value, **current}
        elif over:
            attributes[name] = value
        elif current != value:
            kept.append(f"{name} stays {current!r}: {value!r} was stated on the {stated.side} side")
    fills: bool = bool(stated.purpose.strip()) and not under and held.purpose.strip() in {"", PURPOSE_NOT_STATED}
    known: set[str] = {name_key(held.name), *(name_key(alias) for alias in held.aliases)}
    added: dict[str, None] = {
        alias: None for alias in (stated.name, *stated.aliases) if alias.strip() and name_key(alias) not in known
    }
    return (
        replace(
            held,
            side=AUTHORITY_SIDE if over else held.side,
            aliases=(*held.aliases, *added),
            purpose=stated.purpose.strip() if fills else held.purpose,
            attributes=attributes,
        ),
        kept,
    )


def _record_entry(matrix: Matrix, stated: Entry) -> tuple[Outcome, list[str]]:
    """Record one entry a seeding step states: add it, or add to the entry that has its id.

    An entry that breaks its kind raises ``MatrixError`` from ``Matrix.put`` and changes nothing.

    Returns:
        Whether the entry was created, changed or already as stated, and one sentence per stated
        value that was not taken (:func:`_merged`).

    """
    held: Entry | None = matrix.find(stated.id)
    if held is None:
        matrix.put(stated)
        return OUTCOME_CREATED, []
    merged: Entry
    kept: list[str]
    merged, kept = _merged(held, stated)
    if merged == held:
        return OUTCOME_UNCHANGED, kept
    matrix.put(merged)
    return OUTCOME_CHANGED, kept


def _record_relationship(matrix: Matrix, stated: Relationship) -> Outcome:
    """Record one relationship a seeding step states: add it, or add its attributes to the one held.

    The relationship held is the one with the same kind, ends, key attributes and side; an
    attribute it already has stays as it is. A relationship that breaks its kind, names an entry
    the matrix does not hold or joins kinds it may not join raises ``MatrixError`` from
    ``Matrix.link`` and changes nothing.

    Returns:
        Whether the relationship was added, changed or already as stated.

    """
    held: Relationship | None = next(
        (
            kept
            for kept in matrix.outgoing(stated.start, (stated.kind,))
            if relationship_id(kept) == relationship_id(stated)
        ),
        None,
    )
    if held is None:
        matrix.link(stated)
        return OUTCOME_CREATED
    attributes: dict[str, JsonValue] = {**stated.attributes, **held.attributes}
    if attributes == dict(held.attributes):
        return OUTCOME_UNCHANGED
    matrix.link(replace(held, attributes=attributes))
    return OUTCOME_CHANGED


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def seed_stacks(matrix: Matrix, repositories: Sequence[Repository], types: Mapping[str, str]) -> StacksSeeded:
    """Record one stack per repository that is not deprecated and that holds a stack.

    The stack takes the repository's name as its name, with its repository, its app and its
    execution use: imported when the type is the library type, otherwise executable. It is
    recorded on the repository side with the purpose not stated; a stack the matrix already holds
    keeps its side and its purpose.

    Args:
        matrix: The matrix, changed in place.
        repositories: Every known repository (:func:`read_repositories`).
        types: The type of each repository that holds a stack, by its name (:func:`repository_types`).

    Returns:
        The stacks created and changed, how many were already as stated, the repositories whose
        name ends in no listed type, the deprecated ones, and each stack that could not be
        recorded.

    Raises:
        ValueError: No stack type is given.

    """
    if not types:
        message: str = "seed-stacks needs the types of the repositories that hold a stack"
        raise ValueError(message)
    result: StacksSeeded = {
        "created": [],
        "changed": [],
        "unchanged": 0,
        "noType": [],
        "deprecated": [],
        "refused": [],
    }
    repository: Repository
    for repository in sorted(repositories, key=lambda found: found.name):
        if repository.lifecycle == LIFECYCLE_DEPRECATED:
            result["deprecated"].append(repository.name)
            continue
        kind: str | None = types.get(repository.name)
        if kind is None:
            result["noType"].append(repository.name)
            continue
        attributes: dict[str, JsonValue] = {
            ATTR_REPOSITORY: repository.name,
            ATTR_EXECUTION_USE: EXECUTION_IMPORTED if kind == LIBRARY_TYPE else EXECUTION_EXECUTABLE,
        }
        if repository.app:
            attributes[ATTR_APP] = repository.app
        try:
            stack: Entry = Entry(
                id=make_id(KIND_STACK, repository.name),
                kind=KIND_STACK,
                name=repository.name,
                side=SIDE_REPOSITORY,
                purpose=PURPOSE_NOT_STATED,
                attributes=attributes,
            )
            outcome: Outcome
            kept: list[str]
            outcome, kept = _record_entry(matrix, stack)
        except MatrixError as error:
            result["refused"].append(_refusal(repository.name, f"{KIND_STACK} {repository.name}", error))
            continue
        result["refused"].extend(_refusal(repository.name, stack.id, reason) for reason in kept)
        result["unchanged"] += _counted(result["created"], result["changed"], stack.id, outcome)
    return result


def _counted(created: list[EntryId], changed: list[EntryId], entry_id: EntryId, outcome: Outcome) -> int:
    """List one recorded entry under what recording it did.

    Returns:
        1 when the entry was already as stated, which the caller counts; otherwise 0.

    """
    if outcome == OUTCOME_CREATED:
        created.append(entry_id)
    elif outcome == OUTCOME_CHANGED:
        changed.append(entry_id)
    elif outcome == OUTCOME_UNCHANGED:
        return 1
    else:
        assert_never(outcome)
    return 0


def _distribution_key(name: str) -> str:
    """Reduce a distribution name to the form distribution names are compared in.

    Returns:
        The name in lower case with each run of hyphens, underscores and dots as one hyphen.

    """
    return _NAME_SEPARATORS.sub("-", name.strip()).lower()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_project(repository: Path) -> Project | None:
    """Read the Python project a repository's ``pyproject.toml`` states.

    Args:
        repository: The repository's clone.

    Returns:
        The project's distribution name and the names of the distributions its
        ``[project].dependencies`` list; None when the repository has no ``pyproject.toml`` or
        the file states no project name.

    Raises:
        MatrixError: The file cannot be read or is not TOML.

    """
    file: Path = repository / PYPROJECT
    if not file.is_file():
        return None
    try:
        loaded: dict[str, object] = tomllib.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        message: str = f"cannot read {file}: {error}"
        raise MatrixError(message) from error
    project: object = loaded.get("project")
    name: object = project.get("name") if isinstance(project, dict) else None
    if not isinstance(project, dict) or not isinstance(name, str) or not name.strip():
        return None
    stated: object = project.get("dependencies")
    found: list[re.Match[str] | None] = [
        _REQUIREMENT_NAME.match(item) for item in (stated if isinstance(stated, list) else []) if isinstance(item, str)
    ]
    return Project(
        name=name.strip(),
        dependencies=tuple(dict.fromkeys(_distribution_key(match.group(1)) for match in found if match is not None)),
    )


def _stack_projects(
    matrix: Matrix,
    repositories: Sequence[Repository],
    result: PackagesSeeded,
) -> dict[EntryId, Project]:
    """Read the Python project of each stack's repository.

    Returns:
        Each stack whose repository states a project, with the project. A stack whose repository
        states none, or is not on this machine, is listed in the result, and so is a
        ``pyproject.toml`` that cannot be read.

    """
    clones: dict[str, Path] = {found.name: found.path for found in repositories if found.path is not None}
    projects: dict[EntryId, Project] = {}
    stack: Entry
    for stack in matrix.entries((KIND_STACK,)):
        named: JsonValue = stack.attributes.get(ATTR_REPOSITORY)
        clone: Path | None = clones.get(named) if isinstance(named, str) else None
        try:
            project: Project | None = None if clone is None else read_project(clone)
        except MatrixError as error:
            result["refused"].append(_refusal(str(clone), stack.id, error))
            continue
        if project is None:
            result["noProject"].append(stack.id)
        else:
            projects[stack.id] = project
    return projects


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def seed_packages(matrix: Matrix, repositories: Sequence[Repository]) -> PackagesSeeded:
    """Record the package of each library stack and the imports between stacks.

    Each stack whose execution use is imported gets one package of the project's own, named as
    the ``[project].name`` of its repository's ``pyproject.toml``, joined to it by
    ``distributedAs``. Each stack whose ``[project].dependencies`` name such a package gets one
    ``imports`` relationship to the stack that is distributed as it, with ``through`` naming
    the package. Everything is recorded on the repository side. A dependency that is not a
    project package is not recorded.

    Args:
        matrix: The matrix, changed in place; it holds the stacks (:func:`seed_stacks`).
        repositories: Every known repository (:func:`read_repositories`).

    Returns:
        The packages and the imports recorded, the stacks whose repository states no project,
        and each write that could not be made.

    """
    result: PackagesSeeded = {"packages": [], "imports": [], "noProject": [], "refused": []}
    projects: dict[EntryId, Project] = _stack_projects(matrix, repositories, result)
    distributed: dict[str, tuple[EntryId, EntryId]] = {}
    stack_id: EntryId
    project: Project
    for stack_id, project in projects.items():
        if matrix.entry(stack_id).attributes.get(ATTR_EXECUTION_USE) != EXECUTION_IMPORTED:
            continue
        try:
            package: Entry = Entry(
                id=make_id(KIND_PACKAGE, project.name),
                kind=KIND_PACKAGE,
                name=project.name,
                side=SIDE_REPOSITORY,
                attributes={ATTR_ORIGIN: ORIGIN_PROJECT},
            )
            kept: list[str] = _record_entry(matrix, package)[1]
            _record_relationship(
                matrix,
                Relationship(kind=REL_DISTRIBUTED_AS, start=stack_id, end=package.id, side=SIDE_REPOSITORY),
            )
        except MatrixError as error:
            result["refused"].append(_refusal(stack_id, f"{KIND_PACKAGE} {project.name}", error))
            continue
        result["refused"].extend(_refusal(stack_id, package.id, reason) for reason in kept)
        result["packages"].append(package.id)
        distributed[_distribution_key(project.name)] = (package.id, stack_id)
    for stack_id, project in projects.items():
        dependency: str
        for dependency in project.dependencies:
            if dependency not in distributed or distributed[dependency][1] == stack_id:
                continue
            through: EntryId
            library: EntryId
            through, library = distributed[dependency]
            imported: Relationship = Relationship(
                kind=REL_IMPORTS,
                start=stack_id,
                end=library,
                side=SIDE_REPOSITORY,
                attributes={ATTR_THROUGH: through},
            )
            try:
                _record_relationship(matrix, imported)
            except MatrixError as error:
                result["refused"].append(_refusal(stack_id, relationship_label(imported), error))
                continue
            result["imports"].append(f"{stack_id} {REL_IMPORTS} {library}")
    result["packages"].sort()
    return result


def _size(file: Path) -> int | None:
    """Read the size of a file.

    Returns:
        The size in bytes; None when the file is missing or cannot be read.

    """
    try:
        return file.stat().st_size if file.is_file() else None
    except OSError:
        return None


def _source_bytes(clone: Path) -> int | None:
    """Add up the sizes of the source files git tracks in a repository.

    Returns:
        The bytes of the tracked files with a source suffix; None when the folder is no git tree.

    """
    try:
        tracked: list[str] = program_output("git", ["ls-files", "-z"], clone).split("\0")
    except MatrixError:
        return None
    return sum(
        _size(clone / relative) or 0 for relative in tracked if relative and Path(relative).suffix in SOURCE_SUFFIXES
    )


def _packed[T](groups: Sequence[tuple[int, list[T]]], limit: int) -> list[tuple[int, list[T]]]:
    """Fill batches with groups, in order, each up to a limit.

    A group is never split; one larger than the limit is a batch of its own.

    Returns:
        The batches, each with its bytes and its items.

    """
    batches: list[tuple[int, list[T]]] = []
    size: int = 0
    items: list[T] = []
    weight: int
    group: list[T]
    for weight, group in groups:
        if items and size + weight > limit:
            batches.append((size, items))
            size, items = 0, []
        size += weight
        items = [*items, *group]
    if items:
        batches.append((size, items))
    return batches


def _write_batches(
    folder: Path,
    step: SeedStep,
    batches: Sequence[tuple[int, list[dict[str, JsonValue]]]],
    members: Mapping[str, JsonValue],
    listed: str,
) -> list[BatchWritten]:
    """Write the batch files of one step, and remove the step's batch files of an earlier run.

    Returns:
        Each file written, with how many items it lists and their bytes.

    Raises:
        MatrixError: The folder cannot be created or an earlier batch file cannot be removed.

    """
    target: Path = folder / BATCH_FOLDER
    message: str
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        message = f"cannot create the folder {target}: {error}"
        raise MatrixError(message) from error
    written: list[BatchWritten] = []
    index: int
    size: int
    items: list[dict[str, JsonValue]]
    for index, (size, items) in enumerate(batches, start=1):
        name: str = f"{step}{BATCH_SEPARATOR}{index:02d}"
        batch: dict[str, JsonValue] = {"step": step, "batch": name, "bytes": size, **members, listed: [*items]}
        if step != STEP_FEATURES:
            batch["result"] = str(folder / RESULT_FOLDER / f"{name}{JSON_SUFFIX}")
        file: Path = target / f"{name}{JSON_SUFFIX}"
        write_text(file, json.dumps(batch, indent=1, ensure_ascii=False) + "\n")
        written.append({"file": str(file), "items": len(items), "bytes": size})
    kept: set[str] = {entry["file"] for entry in written}
    stale: Path
    for stale in sorted(target.glob(f"{step}{BATCH_SEPARATOR}*{JSON_SUFFIX}")):
        if str(stale) not in kept:
            try:
                stale.unlink()
            except OSError as error:
                message = f"cannot remove the earlier batch file {stale}: {error}"
                raise MatrixError(message) from error
    return written


def _document_groups(matrix: Matrix, arch: Path, missing: list[str]) -> list[tuple[int, list[dict[str, JsonValue]]]]:
    """Group the effective arc42 documents by subject, then order the groups by arc42 section.

    Returns:
        One group per subject, and one per document that states no subject, each with its bytes;
        a document whose file is not found is left out and listed.

    """
    groups: dict[str, tuple[int, list[dict[str, JsonValue]]]] = {}
    order: dict[str, tuple[int, str]] = {}
    document: Entry
    for document in matrix.entries((KIND_DOCUMENT,)):
        if document.attributes.get(ATTR_LIFECYCLE) != LIFECYCLE_EFFECTIVE:
            continue
        file: Path = arch / document.id.partition(ID_SEPARATOR)[2]
        size: int | None = _size(file)
        if size is None:
            missing.append(document.id)
            continue
        subject: JsonValue = document.attributes.get(ATTR_SUBJECT)
        section: JsonValue = document.attributes.get(ATTR_SECTION)
        key: str = name_key(subject) if isinstance(subject, str) and subject.strip() else document.id
        position: int = section if isinstance(section, int) else 0
        held: tuple[int, list[dict[str, JsonValue]]] = groups.get(key, (0, []))
        item: dict[str, JsonValue] = {
            "id": document.id,
            "path": str(file),
            "section": section,
            "subject": subject,
            "bytes": size,
        }
        groups[key] = (held[0] + size, [*held[1], item])
        order[key] = min(order.get(key, (position, key)), (position, key))
    return [groups[key] for key in sorted(groups, key=lambda found: order[found])]


def _prd_groups(matrix: Matrix, vault: Path, missing: list[str]) -> list[tuple[int, list[dict[str, JsonValue]]]]:
    """List the PRD of each Epic with its requirements, one group per PRD.

    Returns:
        One group per Epic that names a PRD file, with the file's bytes; an Epic whose PRD file
        is not found is left out and listed.

    """
    groups: list[tuple[int, list[dict[str, JsonValue]]]] = []
    epic: Entry
    for epic in matrix.entries((KIND_EPIC,)):
        prd: JsonValue = epic.attributes.get(ATTR_PRD)
        relative: JsonValue = prd.get(ATTR_PRD_PATH) if isinstance(prd, dict) else None
        size: int | None = _size(vault / relative) if isinstance(relative, str) and relative else None
        if size is None or not isinstance(relative, str):
            missing.append(epic.id)
            continue
        bead: str = epic.id.partition(ID_SEPARATOR)[2]
        requirements: list[JsonValue] = [stated.end for stated in matrix.outgoing(epic.id, (REL_HAS_REQUIREMENT,))]
        item: dict[str, JsonValue] = {
            "epic": bead,
            "path": str(vault / relative),
            "requirements": requirements,
            "bytes": size,
        }
        groups.append((size, [item]))
    return groups


def _stack_groups(
    matrix: Matrix,
    repositories: Sequence[Repository],
    missing: list[str],
) -> list[tuple[int, list[dict[str, JsonValue]]]]:
    """List each stack with the clone of its repository, one group per stack, by app.

    Returns:
        One group per stack whose repository is on this machine, counted as its source size up to
        the cap; a stack with no clone to read is left out and listed.

    """
    clones: dict[str, Path] = {found.name: found.path for found in repositories if found.path is not None}
    groups: list[tuple[str, int, dict[str, JsonValue]]] = []
    stack: Entry
    for stack in matrix.entries((KIND_STACK,)):
        named: JsonValue = stack.attributes.get(ATTR_REPOSITORY)
        clone: Path | None = clones.get(named) if isinstance(named, str) else None
        size: int | None = None if clone is None or not clone.is_dir() else _source_bytes(clone)
        if clone is None or size is None:
            missing.append(stack.id)
            continue
        app: JsonValue = stack.attributes.get(ATTR_APP)
        counted: int = min(size, STACK_CAP)
        item: dict[str, JsonValue] = {
            "id": stack.id,
            "repository": named,
            "path": str(clone),
            "sourceBytes": size,
            "bytes": counted,
        }
        groups.append((app if isinstance(app, str) else "", counted, item))
    return [(counted, [item]) for _, counted, item in sorted(groups, key=lambda found: (found[0], str(found[2]["id"])))]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def seed_inputs(  # ruff: ignore[too-many-arguments] - One place per source the batches are cut from.
    matrix: Matrix,
    *,
    arch: Path,
    vault: Path,
    repositories: Sequence[Repository],
    directory: Path,
    allowance: int = READING_ALLOWANCE,
) -> InputsWritten:
    """Write the batch files the seeding sessions are handed, and change nothing in the matrix.

    Three sets are written under ``directory``, each batch filled up to the reading allowance
    and each file naming what its session reads, what its result holds and where it writes it.
    The effective arc42 documents are grouped by subject, so every document about one subject is
    in one batch, and then by arc42 section. The PRDs are packed to two thirds of the allowance.
    A stack counts as its source size up to the cap. The batch files of an earlier run are
    replaced. A file that cannot be written raises ``MatrixError``.

    Args:
        matrix: The matrix, which holds the Epics, the documents and the stacks.
        arch: The architecture root, which the document ids are paths under.
        vault: The vault root, which the PRD paths are relative to.
        repositories: Every known repository (:func:`read_repositories`), for the clone paths.
        directory: The seeding folder (:func:`seed_directory`).
        allowance: The bytes of text one session reads.

    Returns:
        The batch files written for each step, and what was left out because its files could not
        be found.

    Raises:
        ValueError: ``allowance`` is not positive.

    """
    if allowance <= 0:
        message: str = f"the reading allowance {allowance} is not a positive number of bytes"
        raise ValueError(message)
    missing: list[str] = []
    proposals: Path = directory / PROPOSAL_FOLDER
    prds: list[tuple[int, list[dict[str, JsonValue]]]] = [
        (size, [{**item, "proposal": str(proposals / f"{item['epic']}{JSON_SUFFIX}")} for item in items])
        for size, items in _prd_groups(matrix, vault, missing)
    ]
    return {
        "directory": str(directory),
        "allowance": allowance,
        "architecture": _write_batches(
            directory,
            STEP_ARCHITECTURE,
            _packed(_document_groups(matrix, arch, missing), allowance),
            {"side": SIDE_ARCHITECTURE, "resultHolds": RESULT_HOLDS},
            "documents",
        ),
        "features": _write_batches(
            directory,
            STEP_FEATURES,
            _packed(prds, allowance * PRD_SHARE[0] // PRD_SHARE[1]),
            {"side": SIDE_ARCHITECTURE, "proposalHolds": PROPOSAL_HOLDS},
            "prds",
        ),
        "repository": _write_batches(
            directory,
            STEP_REPOSITORY,
            _packed(_stack_groups(matrix, repositories, missing), allowance),
            {"side": SIDE_REPOSITORY, "resultHolds": REPOSITORY_RESULT_HOLDS},
            "stacks",
        ),
        "merge": str(directory / MERGE_FILE),
        "notSized": missing,
    }


def _parse_proposal(file: Path) -> Proposal:
    """Read one proposal file.

    A file that cannot be read, or is not a JSON object, raises ``MatrixError`` from
    :func:`_read_object`, and so does a member that is missing or of another shape from the
    reader that finds it.

    Returns:
        The Epic and, for each requirement, the features proposed with their documents.

    """
    raw: dict[str, JsonValue] = _read_object(file)
    requirements: list[ProposedRequirement] = []
    stated: dict[str, JsonValue]
    for stated in _objects(raw.get("requirements"), "requirements"):
        requirement: str = _text(stated.get("requirement"), "a requirement's id")
        features: list[ProposedFeature] = [
            ProposedFeature(
                name=_text(feature.get("name"), f"the name of a feature of {requirement}"),
                purpose=_optional_text(feature.get("purpose"), f"the purpose of a feature of {requirement}"),
                documents=tuple(
                    Anchor(
                        document=_text(anchor.get("document"), f"a document of a feature of {requirement}"),
                        heading=_optional_text(anchor.get("heading"), f"a heading of a feature of {requirement}"),
                    )
                    for anchor in _objects(feature.get("documents"), f"the documents of a feature of {requirement}")
                ),
            )
            for feature in _objects(stated.get("features"), f"the features of {requirement}")
        ]
        requirements.append(ProposedRequirement(requirement=requirement, features=tuple(features)))
    return Proposal(file=file, epic=_text(raw.get("epic"), "epic"), requirements=tuple(requirements))


def _files(paths: Sequence[Path], opening: str = "") -> list[Path]:
    """List the JSON files some paths name.

    Returns:
        Each file given, and the JSON files directly in each folder given whose name starts with
        ``opening``, in name order within a folder and without repeats.

    """
    found: dict[Path, None] = {}
    path: Path
    for path in paths:
        found.update(dict.fromkeys(sorted(path.glob(f"{opening}*{JSON_SUFFIX}")) if path.is_dir() else [path]))
    return list(found)


def _proposals(paths: Sequence[Path], refused: list[Refusal]) -> list[Proposal]:
    """Read the proposal files some paths name.

    Returns:
        The proposals read; a file that cannot be read as one is listed among the refusals.

    """
    proposals: list[Proposal] = []
    file: Path
    for file in _files(paths):
        try:
            proposals.append(_parse_proposal(file))
        except MatrixError as error:
            refused.append(_refusal(file, "the proposal file", error))
    return proposals


def _requirement_id(proposal: Proposal, stated: str) -> EntryId:
    """Name the requirement a proposal file states.

    An id that does not have the form of a requirement's raises ``MatrixError`` from ``make_id``.

    Returns:
        The id stated; for a key stated alone, the requirement of the proposal's Epic with that key.

    """
    prefix: str = f"{KIND_REQUIREMENT}{ID_SEPARATOR}"
    if stated.startswith(prefix):
        return as_entry_id(stated)
    bead: str = proposal.epic.removeprefix(f"{KIND_EPIC}{ID_SEPARATOR}")
    return make_id(KIND_REQUIREMENT, f"{bead}{STACK_SEPARATOR}{stated}")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def list_proposed(proposals: Sequence[Path], matrix: Matrix | None = None) -> ProposedFeatures:
    """List the features the proposal files state, each once, for the session that merges them.

    Args:
        proposals: The proposal files, or the folders that hold them.
        matrix: The matrix; when given, the requirements it holds that no proposal file lists
            are returned too.

    Returns:
        Each proposed feature once by name, as names are compared, with the first purpose stated
        for it and the number of requirements it is proposed for; the requirements no proposal
        file lists; what the merge file holds; and each proposal file that could not be read.

    Raises:
        ValueError: No proposal file or folder is given.

    """
    if not proposals:
        message: str = "seed-features needs the proposal files or the folder that holds them"
        raise ValueError(message)
    refused: list[Refusal] = []
    read: list[Proposal] = _proposals(proposals, refused)
    features: dict[str, ProposedName] = {}
    listed: set[EntryId] = set()
    proposal: Proposal
    for proposal in read:
        requirement: ProposedRequirement
        for requirement in proposal.requirements:
            try:
                listed.add(_requirement_id(proposal, requirement.requirement))
            except ValueError as error:
                refused.append(_refusal(proposal.file, requirement.requirement, error))
            feature: ProposedFeature
            for feature in requirement.features:
                held: ProposedName = features.setdefault(
                    name_key(feature.name),
                    {"name": feature.name, "purpose": feature.purpose, "requirements": 0},
                )
                held["requirements"] += 1
                if not held["purpose"]:
                    held["purpose"] = feature.purpose
    return {
        "files": len(read),
        "features": [features[key] for key in sorted(features)],
        "requirementsNotProposed": []
        if matrix is None
        else [entry.id for entry in matrix.entries((KIND_REQUIREMENT,)) if entry.id not in listed],
        "mergeHolds": MERGE_HOLDS,
        "refused": refused,
    }


def _parse_merge(file: Path) -> list[MergedFeature]:
    """Read the merge file.

    A file that cannot be read, or is not a JSON object, raises ``MatrixError`` from
    :func:`_read_object`, and so does a member that is missing or of another shape from the
    reader that finds it.

    Returns:
        The features, each with the proposed names that are it.

    """
    return [
        MergedFeature(
            name=_text(stated.get("name"), "a feature's name"),
            purpose=_optional_text(stated.get("purpose"), "a feature's purpose"),
            aliases=_texts(stated.get("aliases"), "a feature's aliases"),
            proposed=_texts(stated.get("proposed"), "a feature's proposed names"),
        )
        for stated in _objects(_read_object(file).get("features"), "features")
    ]


def _merge_index(file: Path, applied: Applied) -> dict[str, MergedFeature]:
    """Index the merge file by proposed name.

    Returns:
        Each proposed name, and each feature's own name, as names are compared, with the feature
        it is. A name two features claim stays with the first and is listed among the refusals.

    """
    index: dict[str, MergedFeature] = {}
    feature: MergedFeature
    for feature in _parse_merge(file):
        name: str
        for name in dict.fromkeys(name_key(stated) for stated in (feature.name, *feature.proposed)):
            if name in index and index[name] != feature:
                applied["refused"].append(
                    _refusal(file, feature.name, f"{name!r} is already the feature {index[name].name!r}"),
                )
            else:
                index[name] = feature
    return index


def _tally(applied: Applied, outcome: Outcome) -> None:
    """Count one recorded relationship in the result of :func:`seed_apply`."""
    if outcome == OUTCOME_CREATED:
        applied["relationshipsAdded"] += 1
    elif outcome == OUTCOME_CHANGED:
        applied["relationshipsChanged"] += 1
    elif outcome == OUTCOME_UNCHANGED:
        applied["relationshipsUnchanged"] += 1
    else:
        assert_never(outcome)


@dataclass(frozen=True, slots=True)
class Recorder:
    """Where the writes of one file go, and where they are counted."""

    matrix: Matrix
    file: Path
    applied: Applied


def _put(recorder: Recorder, entry: Entry) -> bool:
    """Record one entry of a file and count it, or list why it could not be recorded.

    Returns:
        True when the matrix holds the entry afterwards.

    """
    applied: Applied = recorder.applied
    try:
        outcome: Outcome
        kept: list[str]
        outcome, kept = _record_entry(recorder.matrix, entry)
    except MatrixError as error:
        applied["refused"].append(_refusal(recorder.file, entry.id, error))
        return False
    applied["refused"].extend(_refusal(recorder.file, entry.id, reason) for reason in kept)
    applied["entriesUnchanged"] += _counted(applied["entriesCreated"], applied["entriesChanged"], entry.id, outcome)
    return True


def _link(recorder: Recorder, relationship: Relationship) -> None:
    """Record one relationship of a file and count it, or list why it could not be recorded."""
    try:
        _tally(recorder.applied, _record_relationship(recorder.matrix, relationship))
    except MatrixError as error:
        recorder.applied["refused"].append(_refusal(recorder.file, relationship_label(relationship), error))


def _document_id(stated: str) -> EntryId:
    """Name the document a proposal file states.

    An id that does not have the form of a document's raises ``MatrixError`` from ``make_id``.

    Returns:
        The id stated; for a path stated alone, the document with that path.

    """
    return make_id(KIND_DOCUMENT, stated.removeprefix(f"{KIND_DOCUMENT}{ID_SEPARATOR}"))


def _apply_feature(
    recorder: Recorder,
    requirement: EntryId,
    proposed: ProposedFeature,
    merged: MergedFeature,
) -> None:
    """Record one feature for one requirement: the feature, ``servedBy``, ``describedBy`` and ``covers``."""
    refused: list[Refusal] = recorder.applied["refused"]
    known: str = name_key(merged.name)
    try:
        feature: Entry = Entry(
            id=make_id(KIND_FEATURE, slug(merged.name)),
            kind=KIND_FEATURE,
            name=merged.name,
            side=SIDE_ARCHITECTURE,
            aliases=tuple(
                dict.fromkeys(alias for alias in (*merged.aliases, proposed.name) if name_key(alias) != known),
            ),
            purpose=merged.purpose or proposed.purpose,
        )
    except ValueError as error:
        refused.append(_refusal(recorder.file, merged.name, error))
        return
    if not _put(recorder, feature):
        return
    _link(recorder, Relationship(kind=REL_SERVED_BY, start=requirement, end=feature.id, side=SIDE_ARCHITECTURE))
    anchor: Anchor
    for anchor in proposed.documents:
        try:
            document: EntryId = _document_id(anchor.document)
        except ValueError as error:
            refused.append(_refusal(recorder.file, anchor.document, error))
            continue
        heading: dict[str, JsonValue] = {ATTR_HEADING: anchor.heading} if anchor.heading else {}
        _link(
            recorder,
            Relationship(
                kind=REL_DESCRIBED_BY,
                start=feature.id,
                end=document,
                side=SIDE_ARCHITECTURE,
                attributes=heading,
            ),
        )
        _link(
            recorder,
            Relationship(
                kind=REL_COVERS,
                start=document,
                end=requirement,
                side=SIDE_ARCHITECTURE,
                attributes={**heading, ATTR_VIA: feature.id},
            ),
        )


def _apply_features(matrix: Matrix, results: Sequence[Path], merge: Path, applied: Applied) -> None:
    """Record the features of the proposal files as the merge file names them.

    Each feature is recorded once, joined by ``servedBy`` to every requirement it is proposed
    for, by ``describedBy`` to each document heading a proposal says covers it, and each such
    document by ``covers`` to the requirement. A proposed feature the merge file names nowhere
    is listed and nothing is recorded for it. A merge file that cannot be read, or is of another
    shape, raises ``MatrixError`` from :func:`_parse_merge`.
    """
    index: dict[str, MergedFeature] = _merge_index(merge, applied)
    unmerged: dict[str, None] = {}
    proposal: Proposal
    for proposal in _proposals(results, applied["refused"]):
        applied["files"].append(str(proposal.file))
        stated: ProposedRequirement
        for stated in proposal.requirements:
            try:
                requirement: EntryId = _requirement_id(proposal, stated.requirement)
            except ValueError as error:
                applied["refused"].append(_refusal(proposal.file, stated.requirement, error))
                continue
            if matrix.find(requirement) is None:
                applied["refused"].append(
                    _refusal(proposal.file, requirement, "the matrix holds no such requirement"),
                )
                continue
            proposed: ProposedFeature
            for proposed in stated.features:
                merged: MergedFeature | None = index.get(name_key(proposed.name))
                if merged is None:
                    unmerged[proposed.name] = None
                else:
                    _apply_feature(Recorder(matrix, proposal.file, applied), requirement, proposed, merged)
    applied["unmerged"] = sorted(unmerged)


def _stated_id(text: str) -> EntryId:
    """Read an entry id a result file states, in the form the matrix holds it.

    The part of an id that is the slug of a name is reduced to a slug, so an id written with the
    name itself names the same entry. A kind the registry does not declare raises ``MatrixError``
    from ``entry_kind``, and an id of another form from ``make_id``. A part that is a name and
    holds no letter or digit raises ``ValueError`` from ``slug``.

    Returns:
        The id.

    Raises:
        MatrixError: The text is not a kind, a colon and the rest.

    """
    head: str
    separator: str
    rest: str
    head, separator, rest = text.strip().partition(ID_SEPARATOR)
    if not separator or not rest.strip():
        message: str = f"{text!r} is not an entry id: a kind, a colon and the rest"
        raise MatrixError(message)
    kind: EntryKind = entry_kind(head)
    if kind in NAMED_ID_KINDS or kind in STATED_ID_KINDS:
        return make_id(kind, rest.strip())
    stack: str
    slash: str
    tail: str
    stack, slash, tail = rest.strip().rpartition(STACK_SEPARATOR)
    if slash and ENTRY_RULES[kind].repository_id_pattern is not None:
        return make_id(kind, f"{stack}{STACK_SEPARATOR}{slug(tail)}")
    return make_id(kind, slug(rest))


def _entry_of(stated: StatedEntry, side: Side) -> Entry:
    """Build the entry a result file states, with the side its step states.

    The id is the one stated; else the kind and the name as written for a stack, a package and
    an event; else, for a component, an infrastructure entry or a layer on the repository side,
    the kind, the stack named and the slug of the name; else the kind and the slug of the name.
    An id of another form raises ``MatrixError`` from ``make_id``, and a name that holds no
    letter or digit raises ``ValueError`` from ``slug``.

    Returns:
        The entry.

    Raises:
        MatrixRefusedError: The kind is one the script steps record, or the entry needs the
            stack that holds it and states none.

    """
    message: str
    if stated.kind in STATED_ID_KINDS:
        message = f"an entry of kind {stated.kind} is recorded by the script steps of seeding, not from a result file"
        raise MatrixRefusedError(message)
    key: EntryId
    if stated.id is not None:
        key = _stated_id(stated.id)
    elif stated.kind in NAMED_ID_KINDS:
        key = make_id(stated.kind, stated.name)
    elif side != AUTHORITY_SIDE and ENTRY_RULES[stated.kind].repository_id_pattern is not None:
        if stated.stack is None:
            message = f"an entry of kind {stated.kind} found in a repository states the stack that holds it"
            raise MatrixRefusedError(message)
        key = repository_side_id(stated.kind, _stated_id(_stack_text(stated.stack)), stated.name)
    else:
        key = make_id(stated.kind, slug(stated.name))
    return Entry(
        id=key,
        kind=stated.kind,
        name=stated.name,
        side=side,
        aliases=tuple(alias for alias in stated.aliases if name_key(alias) != name_key(stated.name)),
        purpose=stated.purpose,
        attributes=dict(stated.attributes),
    )


def _stack_text(stated: str) -> str:
    """Write the stack a result file names as an entry id.

    Returns:
        The text given when it is an id already, else ``stack:<name>``.

    """
    prefix: str = f"{KIND_STACK}{ID_SEPARATOR}"
    return stated if stated.startswith(prefix) else f"{prefix}{stated}"


def _stated_entry(raw: Mapping[str, JsonValue]) -> StatedEntry:
    """Read one entry of a result file.

    A kind the registry does not declare raises ``MatrixError`` from ``entry_kind``, and so
    does a member that is missing or of another shape, or the verified mark, from the reader
    that finds it.

    Returns:
        The entry as stated.

    """
    kind: EntryKind = entry_kind(_text(raw.get("kind"), "an entry's kind"))
    name: str = _text(raw.get("name"), f"the name of a {kind}")
    return StatedEntry(
        kind=kind,
        name=name,
        id=_optional_text(raw.get("id"), f"the id of {name}") or None,
        stack=_optional_text(raw.get("stack"), f"the stack of {name}") or None,
        aliases=_texts(raw.get("aliases"), f"the aliases of {name}"),
        purpose=_optional_text(raw.get("purpose"), f"the purpose of {name}"),
        attributes=_attributes(raw, f"the {kind} {name}"),
    )


def _stated_relationship(raw: Mapping[str, JsonValue]) -> StatedRelationship:
    """Read one relationship of a result file.

    A kind the registry does not declare raises ``MatrixError`` from ``relationship_kind``,
    and so does a member that is missing or of another shape, or the verified mark, from the
    reader that finds it.

    Returns:
        The relationship as stated.

    """
    kind: RelationshipKind = relationship_kind(_text(raw.get("kind"), "a relationship's kind"))
    return StatedRelationship(
        kind=kind,
        start=_text(raw.get("from"), f"the from of a {kind}"),
        end=_text(raw.get("to"), f"the to of a {kind}"),
        attributes=_attributes(raw, f"a {kind} relationship"),
    )


def _apply_results(matrix: Matrix, results: Sequence[Path], side: Side, applied: Applied) -> None:
    """Record every entry and relationship of some result files with one side.

    A folder stands for the result files in it that are named for the step. The entries of every
    file are recorded before any relationship, stacks first, so a relationship may join entries
    of two files and an entry may name a stack of its own file.
    """
    entries: list[tuple[Path, Entry]] = []
    relationships: list[tuple[Path, Mapping[str, JsonValue]]] = []
    file: Path
    raw: Mapping[str, JsonValue]
    for file in _files(results, f"{applied['step']}{BATCH_SEPARATOR}"):
        try:
            content: dict[str, JsonValue] = _read_object(file)
            stated_entries: list[dict[str, JsonValue]] = _objects(content.get("entries"), "entries")
            stated_relationships: list[dict[str, JsonValue]] = _objects(content.get("relationships"), "relationships")
        except MatrixError as error:
            applied["refused"].append(_refusal(file, "the result file", error))
            continue
        applied["files"].append(str(file))
        for raw in stated_entries:
            try:
                entries.append((file, _entry_of(_stated_entry(raw), side)))
            except ValueError as error:
                applied["refused"].append(_refusal(file, f"{raw.get('kind')} {raw.get('name')}", error))
        relationships.extend((file, raw) for raw in stated_relationships)
    entry: Entry
    for file, entry in sorted(entries, key=lambda found: found[1].kind != KIND_STACK):
        _put(Recorder(matrix, file, applied), entry)
    for file, raw in relationships:
        try:
            stated: StatedRelationship = _stated_relationship(raw)
            relationship: Relationship = Relationship(
                kind=stated.kind,
                start=_stated_id(stated.start),
                end=_stated_id(stated.end),
                side=side,
                attributes=dict(stated.attributes),
            )
        except ValueError as error:
            applied["refused"].append(
                _refusal(file, f"{raw.get('from')} {raw.get('kind')} {raw.get('to')}", error),
            )
            continue
        _link(Recorder(matrix, file, applied), relationship)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def as_step(text: str) -> SeedStep:
    """Accept a string as a seeding step whose files :func:`seed_apply` records.

    Args:
        text: The candidate step.

    Returns:
        The step.

    Raises:
        MatrixRefusedError: The text is not one of the steps.

    """
    step: SeedStep
    for step in SEED_STEPS:
        if step == text:
            return step
    message: str = f"{text!r} is not a seeding step; the steps are {', '.join(SEED_STEPS)}"
    raise MatrixRefusedError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def seed_apply(matrix: Matrix, step: SeedStep, results: Sequence[Path], merge: Path | None = None) -> Applied:
    """Record what the sessions of one seeding step wrote.

    For the architecture step and the repository step, every entry and relationship of each
    result file is recorded with that side. An entry the matrix already holds is added to: what
    the architecture states replaces a hint read from a repository and never gives way to one
    (:func:`_merged`). For the features step, each feature the merge file names is recorded once
    on the architecture side, with ``servedBy`` from every requirement a proposal file proposes
    it for, ``describedBy`` to each covering document heading and ``covers`` from that document
    to the requirement. Nothing recorded carries the verified mark. Whatever cannot be read or
    recorded is listed and the rest is recorded, except a merge file that cannot be read or is
    of another shape, which raises ``MatrixError`` from :func:`_parse_merge`.

    Args:
        matrix: The matrix, changed in place.
        step: The step whose files these are.
        results: The result files of the step, or the proposal files of the features step. A
            folder stands for the result files in it that are named for the step
            (``<step>-<number>.json``), or for every proposal file in it.
        merge: The merge file; needed for the features step and for no other.

    Returns:
        The files read, the entries created and changed, the relationships added and changed,
        the proposed features the merge file names nowhere, and each write that could not be made.

    Raises:
        ValueError: No file is given.
        MatrixRefusedError: The features step is given no merge file, or another step is given one.

    """
    message: str
    if not results:
        message = "seed-apply needs the files a step's sessions wrote, or the folder that holds them"
        raise ValueError(message)
    if (merge is None) == (step == STEP_FEATURES):
        message = "seed-apply takes the merge file for the features step, and for no other step"
        raise MatrixRefusedError(message)
    applied: Applied = {
        "step": step,
        "files": [],
        "entriesCreated": [],
        "entriesChanged": [],
        "entriesUnchanged": 0,
        "relationshipsAdded": 0,
        "relationshipsChanged": 0,
        "relationshipsUnchanged": 0,
        "unmerged": [],
        "refused": [],
    }
    if step == STEP_ARCHITECTURE:
        _apply_results(matrix, results, SIDE_ARCHITECTURE, applied)
    elif step == STEP_REPOSITORY:
        _apply_results(matrix, results, SIDE_REPOSITORY, applied)
    elif step == STEP_FEATURES:
        if merge is not None:
            _apply_features(matrix, results, merge, applied)
    else:
        assert_never(step)
    return applied


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def seed(  # ruff: ignore[too-many-arguments] - One place per source seeding reads.
    path: Path,
    *,
    control: Path,
    arch: Path,
    prd_dir: Path,
    environ: Mapping[str, str],
    replace_existing: bool = False,
    wait: float = DEFAULT_LOCK_WAIT,
) -> Seeded:
    """Write an empty matrix file and fill it from beads, the PRDs, the documents and the repositories.

    The open Epics, the repositories and their types are read first, so a source that cannot
    be read leaves the file as it was. Then the empty file is written, and in one write the
    Epics with their requirements, the arc42 documents, the stacks and the packages are
    recorded. The batch files are written last, into the seeding folder of the matrix file
    (:func:`seed_directory`). Nothing a matrix file at ``path`` held before is a source. A source
    that cannot be read raises ``MatrixError`` from the function that reads it.

    Args:
        path: The matrix file to write.
        control: The control repository: its beads hold the Epics, and the ``polyrepo`` tool is
            run in it.
        arch: The architecture root inside the vault.
        prd_dir: The folder of the vault the PRD files are under.
        environ: The environment the naming command is read from (:func:`repository_types`).
        replace_existing: Whether a matrix file already at ``path`` is replaced by the empty one.
        wait: Seconds to wait for the matrix's lock.

    Returns:
        What each step did.

    Raises:
        MatrixRefusedError: A matrix file already exists at ``path`` and ``replace_existing`` is
            False.

    """
    if path.exists() and not replace_existing:
        message: str = f"a matrix already exists at {path}; seeding replaces it only when told to"
        raise MatrixRefusedError(message)
    epics: list[EpicBead] = read_epics(control)
    repositories: list[Repository] = read_repositories(control)
    types: dict[str, str] = repository_types(repositories, environ)
    vault: Path = vault_root(prd_dir)
    create_matrix(path, replace_existing=replace_existing, wait=wait)

    def fill(matrix: Matrix) -> tuple[EpicsSynced, DocumentsSynced, StacksSeeded, PackagesSeeded]:
        synced: EpicsSynced = sync_epics(matrix, epics, prd_dir)
        documents: DocumentsSynced = sync_documents(matrix, arch)
        stacks: StacksSeeded = seed_stacks(matrix, repositories, types)
        return synced, documents, stacks, seed_packages(matrix, repositories)

    filled: tuple[EpicsSynced, DocumentsSynced, StacksSeeded, PackagesSeeded] = update_matrix(path, fill, wait=wait)
    inputs: InputsWritten = seed_inputs(
        read_matrix(path),
        arch=arch.expanduser(),
        vault=vault,
        repositories=repositories,
        directory=seed_directory(path),
    )
    return {
        "matrix": str(path),
        "epics": filled[0],
        "documents": filled[1],
        "stacks": filled[2],
        "packages": filled[3],
        "inputs": inputs,
    }
