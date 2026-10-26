"""The spec pack of one repository's Story: what its spec sessions read instead of the vault.

The repository context step writes it (``spec-pack.schema.json``) beside the repository context.
It holds the entries the Story builds with their approved marks, the text of every heading the
Story's scopes name, read from the vault's last commit (the approved architecture promotion
committed), the constraints and shared capabilities that bind the entries, the requirements of
the Epic's TRD that bind them, and the contract files the repository holds today. A spec session
reads the pack, not the vault and not the matrix.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

from matrix_contract import KIND_CONSTRAINT, REL_APPLIES_TO, MatrixError
from matrixsync import heading_texts, program_output
from typeguard import check_type

from orchestrator.core.io import JsonValue, json_object

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from matrix_contract import Entry, EntryId
    from matrixquery import StoryScope
    from matrixstore import Matrix

ATTR_TRD: Final = "trd"
ATTR_RESOURCE_TYPE: Final = "resourceType"
ATTR_SELECTOR: Final = "selector"
FENCE: Final = "---"
"""The line that opens and closes a document's front matter."""
SKIPPED_FOLDERS: Final[frozenset[str]] = frozenset({
    ".git",
    ".claude",
    ".worktrees",
    ".venv",
    "venv",
    "node_modules",
    "cdk.out",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
})
"""Folders of a repository that hold no contract of its own: tools, dependencies and build output."""
CONTRACT_FILE: Final[re.Pattern[str]] = re.compile(
    r"(^(openapi|swagger|asyncapi)[^/]*\.(ya?ml|json)$)|(\.(graphql|gql)$)|(\.schema\.json$)",
    re.IGNORECASE,
)
"""The file names of API, event and data contracts: OpenAPI, AsyncAPI, GraphQL and JSON Schema files."""


def document_body(text: str) -> list[str]:
    """Split a document's text into the lines after its front matter.

    Returns:
        Every line when the document has no front matter.

    """
    lines: list[str] = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return lines
    close: int = next((index for index in range(1, len(lines)) if lines[index].strip() == FENCE), 0)
    return lines[close + 1 :] if close else lines


def committed_headings(arch: Path, documents: Sequence[Mapping[str, JsonValue]]) -> list[JsonValue]:
    """Read the text of each heading some documents name, from the vault's last commit.

    Each document is read once with ``git show HEAD:<path>``, never from the vault's working
    tree. A heading's text is its own text (its heading line and everything up to the next
    heading), as the matrix hashes it; a document named as a whole gives its whole body.

    Args:
        arch: The architecture root, a folder of the vault.
        documents: The documents, as the repository context lists them: the entry id, the file
            and the headings to read.

    Returns:
        One row per heading (one per document named as a whole): the document, its file, the
        heading (empty for the whole document) and its text; the text is null when the last
        commit holds no such document or heading.

    """
    rows: list[JsonValue] = []
    document: Mapping[str, JsonValue]
    for document in documents:
        identifier: str = check_type(document["document"], str)
        relative: str = identifier.partition(":")[2]
        try:
            body: list[str] | None = document_body(program_output("git", ["show", f"HEAD:./{relative}"], arch))
        except MatrixError:
            body = None
        texts: dict[str, str] = {} if body is None else heading_texts(body)
        named: list[str] = check_type(document["headings"], list[str])
        wanted: list[str] = named or [""]
        heading: str
        for heading in wanted:
            whole: str | None = None if body is None else "\n".join(body).strip("\n")
            text: str | None = texts.get(heading) if heading else whole
            rows.append({"document": identifier, "path": document["path"], "heading": heading, "text": text})
    return rows


def entry_rows(matrix: Matrix, ids: Iterable[EntryId]) -> list[JsonValue]:
    """Describe the entries a Story builds, each with whether it is approved.

    Returns:
        One row per entry: its id, kind, name and purpose, its resource type (null when it has
        none), and whether it carries the approved mark. An id the matrix does not hold gives a row
        with only its id.

    """
    rows: list[JsonValue] = []
    entry_id: EntryId
    for entry_id in ids:
        found: Entry | None = matrix.find(entry_id)
        if found is None:
            rows.append(dict.fromkeys(("kind", "name", "purpose", "resourceType", "approved")) | {"id": entry_id})
            continue
        resource: JsonValue = found.attributes.get(ATTR_RESOURCE_TYPE)
        rows.append({
            "id": found.id,
            "kind": found.kind,
            "name": found.name,
            "purpose": found.purpose,
            "resourceType": resource if isinstance(resource, str) else None,
            "approved": found.approved,
        })
    return rows


def scope_bindings(scopes: Sequence[StoryScope]) -> tuple[list[JsonValue], list[JsonValue]]:
    """Gather the constraints and shared capabilities the story scopes of a Story name.

    Returns:
        The constraints, each once by its id, and the shared capabilities, each once by its
        feature, as ``atw-matrix story-scope`` prints them.

    """
    constraints: dict[str, JsonValue] = {}
    capabilities: dict[str, JsonValue] = {}
    scope: StoryScope
    for scope in scopes:
        for binding in scope["constraints"]:
            constraints.setdefault(str(binding["constraint"]["id"]), json_object(dict(binding)))
        for capability in scope["capabilities"]:
            capabilities.setdefault(str(capability["feature"]["id"]), json_object(dict(capability)))
    return list(constraints.values()), list(capabilities.values())


def trd_requirements(
    matrix: Matrix,
    bead: str,
    trd: str,
    constraints: Sequence[JsonValue],
) -> list[JsonValue]:
    """Gather the TRD requirements that bind what a Story builds.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id.
        trd: The text of the Epic's TRD.
        constraints: The constraints that bind the Story's entries (:func:`scope_bindings`).

    Returns:
        One row per requirement: each constraint with a TRD pointer among ``constraints``, then
        each requirement of this Epic's TRD that applies to the Epic as a whole (its constraint
        names no entry and no selector). A row holds the requirement id, its Epic, its
        constraint and, for this Epic's TRD, the requirement's text (null when the TRD has no
        such heading, and for another Epic's TRD).

    """
    texts: dict[str, str] = heading_texts(document_body(trd))
    rows: dict[str, JsonValue] = {}

    def add(constraint: str, pointer: Mapping[str, JsonValue]) -> None:
        epic: str = str(pointer.get("epic"))
        requirement: str = str(pointer.get("requirement"))
        rows.setdefault(
            constraint,
            {
                "requirement": requirement,
                "epic": epic,
                "constraint": constraint,
                "text": texts.get(requirement) if epic == bead else None,
            },
        )

    binding: JsonValue
    for binding in constraints:
        view: dict[str, JsonValue] = json_object(json_object(binding)["constraint"])
        pointer: JsonValue = view.get(ATTR_TRD)
        if isinstance(pointer, dict):
            add(check_type(view["id"], str), pointer)
    entry: Entry
    for entry in matrix.entries((KIND_CONSTRAINT,)):
        held: JsonValue = entry.attributes.get(ATTR_TRD)
        if not isinstance(held, dict) or held.get("epic") != bead or ATTR_SELECTOR in entry.attributes:
            continue
        if not matrix.outgoing(entry.id, (REL_APPLIES_TO,)):
            add(entry.id, held)
    return list(rows.values())


def contract_files(repo: Path) -> list[str]:
    """List the contract files a repository holds today.

    Returns:
        The path under the repository of each OpenAPI, AsyncAPI, GraphQL and JSON Schema file
        outside its tool, dependency and build folders, in walk order; empty when the repository
        has no checkout.

    """
    found: list[str] = []
    folder: str
    folders: list[str]
    files: list[str]
    for folder, folders, files in os.walk(repo):
        folders[:] = sorted(name for name in folders if name not in SKIPPED_FOLDERS)
        found.extend(
            str((Path(folder) / name).relative_to(repo)) for name in sorted(files) if CONTRACT_FILE.search(name)
        )
    return found
