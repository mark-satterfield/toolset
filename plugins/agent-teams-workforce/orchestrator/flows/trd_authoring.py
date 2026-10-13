"""Confirm the Epic's TRD: verify its architecture citations and mark it on the Epic bead.

The solutions architect has the TRD drafted and updated in place, and it is reviewed with the
architecture. This step starts no session. It reads the TRD at the path the open-run step chose
and recorded in the context file, checks that the matrix holds every document and heading it
cites, and records its path and digest on the Epic bead. Nothing is recorded in the matrix.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The driver surface is defined once, in the pipeline-contracts skill; the matrix contract in artifact-handoff.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import beadgraph
import beads_contract
import yaml
from bead_metadata import KEY_ARTIFACT_TRD_PATH, KEY_ARTIFACT_TRD_SHA256
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import KIND_DOCUMENT, Entry, EntryId, MatrixError
from matrixstore import Matrix, make_id, matrix_path, name_key, read_matrix, slug
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.handback_contract import TRD_PHASE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, file_artifact, value_artifact
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.architecture_files import (
    ARTIFACT_TRD,
    CONFIRM_TRD,
    ArchitectureContext,
    ArchitectureStepError,
    read_context,
)
from orchestrator.flows.elaboration_support import TRD_AUTHORING_PHASE, enter_phase

if TYPE_CHECKING:
    from orchestrator.core.models import RunContext

_ARGUMENT_ERROR: str = "Arguments violate the trd_authoring input contract"
TRD_HASH: Final = "TRD hash on the Epic bead"
TRD_WARNINGS: Final = "TRD warnings"
ARC42_FOLDER: Final = "arc42"
"""The folder of the architecture root the arc42 documents are under; a citation may leave it out."""
HEADING_SEPARATOR: Final = "#"
"""What separates a cited document's path from the heading cited in it."""
ATTR_HEADINGS: Final = "headings"
"""The attribute of a document entry that holds its heading texts."""


class DocumentValidationError(ValueError):
    """An authored document fails its content contract."""


def _anchor(heading: str) -> str:
    """Reduce a heading to the form a link to it is written in.

    Returns:
        The heading's lowercase words joined by hyphens; empty for a heading with no letter or digit.

    """
    try:
        return slug(heading)
    except ValueError:
        return ""


def _stated(document_entry: Entry, heading: str) -> str | None:
    """Find the heading of a document entry that a citation names, by its text or by a link to it.

    Returns:
        The heading text as the entry holds it; None when the entry holds no such heading.

    """
    held: JsonValue = document_entry.attributes.get(ATTR_HEADINGS)
    texts: list[str] = [text for text in held if isinstance(text, str)] if isinstance(held, list) else []
    wanted: str = name_key(heading)
    link: str = _anchor(heading)
    return next((text for text in texts if name_key(text) == wanted or (link and _anchor(text) == link)), None)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def cited(matrix: Matrix, citation: str) -> tuple[EntryId, str] | None:
    """Find the document entry and heading one citation names, as ``atw-matrix node document:<path>`` holds them.

    A citation is a document's path under the architecture root, with or without the arc42
    folder, or the document's entry id; a heading follows a ``#``.

    Args:
        matrix: The matrix.
        citation: The citation as a document's ``decisionIds`` writes it.

    Returns:
        The document's entry id and the heading cited, as the entry holds its text (empty when
        the citation names none); None when the matrix holds no such document, or the document
        holds no such heading.

    """
    relative, _, heading = citation.partition(HEADING_SEPARATOR)
    relative = relative.strip().removeprefix(f"{KIND_DOCUMENT}:")
    if not relative or Path(relative).is_absolute():
        return None
    rest: str
    for rest in (relative, f"{ARC42_FOLDER}/{relative}"):
        try:
            entry: Entry | None = matrix.find(make_id(KIND_DOCUMENT, rest))
        except MatrixError:
            continue
        if entry is not None and entry.kind == KIND_DOCUMENT:
            if not heading.strip():
                return entry.id, ""
            held: str | None = _stated(entry, heading)
            return None if held is None else (entry.id, held)
    return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def document(path: Path, matrix: Matrix) -> tuple[list[str], list[str]]:
    """Validate document frontmatter and check each architecture citation against the matrix.

    Args:
        path: The authored document.
        matrix: The matrix, whose document entries hold every arc42 document and its headings.

    Returns:
        The citations of the document's ``decisionIds``, and the warnings the check raised.

    Raises:
        TypeError: An argument violates the declared input contract.
        DocumentValidationError: Frontmatter is invalid, or a citation names a document or a
            heading the matrix does not hold.

    """
    if not (isinstance(path, Path)) or not (isinstance(matrix, Matrix)):
        raise TypeError(_ARGUMENT_ERROR)
    text: str = path.read_text(encoding="utf-8")
    if not text.strip():
        message: str = f"missing or empty document: {path}"
        raise DocumentValidationError(message)
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        message = f"{path}: YAML frontmatter is missing"
        raise DocumentValidationError(message)
    try:
        raw_front: object = yaml.safe_load(text[4:].split("\n---", 1)[0]) or {}
    except yaml.YAMLError as exc:
        message = f"{path}: invalid YAML frontmatter: {exc}"
        raise DocumentValidationError(message) from exc
    if not isinstance(raw_front, dict):
        message = f"{path}: frontmatter must be an object"
        raise DocumentValidationError(message)
    front: dict[str, JsonValue] = json_object(raw_front)
    raw_ids: JsonValue = front.get("decisionIds", [])
    if not isinstance(raw_ids, list) or any(not isinstance(item, str) for item in raw_ids):
        message = f"{path}: decisionIds must be a list of strings"
        raise DocumentValidationError(message)
    ids: list[str] = check_type(raw_ids, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    unresolved: list[str] = [citation for citation in ids if cited(matrix, citation) is None]
    if unresolved:
        message = f"decisionIds the matrix holds no document and heading for: {unresolved}"
        raise DocumentValidationError(message)
    warnings: list[str] = [] if ids else ["decisionIds is absent or empty"]
    return ids, warnings


def _mark_trd(context: RunContext, tools: Tools, output: Path) -> str:
    """Record the TRD's path and digest on the Epic bead, unless the bead already holds them.

    Returns:
        The SHA-256 digest of the TRD.

    """
    digest: str = hashlib.sha256(output.read_bytes()).hexdigest()
    relative: str = str(output.resolve().relative_to(env_path("SKILLSPOKE_ROOT")))
    control: Path = env_path(CONTROL_REPO_ENV)

    def mark() -> None:
        raw: object = json.loads(tools.bd(["show", context.bead, "--json"], stage=TRD_PHASE))
        bead: dict[str, JsonValue] = json_object(raw[0] if isinstance(raw, list) else raw)
        metadata: dict[str, JsonValue] = json_object(beads_contract.metadata_of(bead))
        pairs: dict[str, str] = {
            KEY_ARTIFACT_TRD_PATH: relative,
            KEY_ARTIFACT_TRD_SHA256: digest,
        }
        if all(metadata.get(key) == value for key, value in pairs.items()):
            return
        tools.portfolio(TRD_PHASE, beadgraph.write_metadata, context.bead, pairs, control)

    tools.operation(TRD_PHASE, mark)
    return digest


@script_step(CONFIRM_TRD)
def confirm(run: StepRun) -> Completion:
    """Confirm the reviewed TRD: the matrix holds every source it cites, and the Epic bead carries it.

    Returns:
        The TRD file and the digest recorded on the Epic bead.

    Raises:
        ArchitectureStepError: The TRD is missing, or its front matter or a citation is invalid.

    """
    enter_phase(run.context, run.agents.emit, TRD_AUTHORING_PHASE, CONFIRM_TRD)
    context: ArchitectureContext = read_context(run)
    trd: Path = Path(context["trdPath"])
    matrix: Matrix = run.tools.portfolio(CONFIRM_TRD, read_matrix, matrix_path(None, os.environ))
    try:
        warnings: list[str] = document(trd, matrix)[1]
    except (OSError, UnicodeError, DocumentValidationError) as exc:
        raise ArchitectureStepError(run, f"{trd}: {exc}") from None
    digest: str = _mark_trd(run.context, run.tools, trd)
    warned: list[JsonValue] = list(warnings)
    return Completion(
        artifacts=(
            file_artifact(ARTIFACT_TRD, trd),
            value_artifact(TRD_HASH, digest),
            *((value_artifact(TRD_WARNINGS, warned),) if warned else ()),
        ),
    )
