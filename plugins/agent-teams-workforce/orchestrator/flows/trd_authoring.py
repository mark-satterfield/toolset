"""Confirm the Epic's TRD: verify its architecture citations and mark it on the Epic bead.

The solutions architect has the TRD drafted and updated in place, and it is reviewed with the
architecture. This step starts no session. It reads the TRD at the path the open-run step chose
and recorded in the context file, checks that the matrix holds every document and heading it
cites, checks that every constraint the matrix holds as a requirement of this TRD (its ``trd``
pointer) names a requirement heading the TRD has, and records its path and digest on the Epic
bead. A TRD that fails a check is corrected once: the step plans one TRD author update of what it
found, then itself again. Nothing is recorded in the matrix.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections.abc import Collection
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The driver surface is defined once, in the pipeline-contracts skill; the matrix contract in artifact-handoff.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import beadgraph
import beads_contract
import strictschema
import yaml
from architecture_work_contract import TRD_MODE_UPDATE, validate_trd_request
from bead_metadata import KEY_ARTIFACT_TRD_PATH, KEY_ARTIFACT_TRD_SHA256
from driver_surface_types import CONTROL_REPO_ENV, PROJECT_ROOT_ENV
from jsonschema import ValidationError
from matrix_contract import KIND_CONSTRAINT, KIND_DOCUMENT, Entry, EntryId, MatrixError
from matrixstore import Matrix, make_id, matrix_path, name_key, read_matrix, slug
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.handback_contract import TRD_PHASE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import (
    UNDER_THIS,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.architecture_files import (
    ARTIFACT_TRD,
    CONFIRM_TRD,
    PARAM_REQUEST,
    TRD_AUTHOR,
    ArchitectureContext,
    ArchitectureStepError,
    read_context,
)
from orchestrator.flows.elaboration_support import TRD_AUTHORING_PHASE, enter_phase

if TYPE_CHECKING:
    from architecture_work_contract import TrdChange, TrdRequest
    from step_journal_contract import Step, StepPlan

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
ATTR_TRD: Final = "trd"
"""The attribute of a constraint that points at a requirement of an Epic's TRD."""
MARKDOWN_HEADING: Final = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)
SCHEMAS: Final[Path] = Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "schemas"
FRONT_MATTER_CONTRACT: Final[Path] = SCHEMAS / "document-front-matter.schema.json"
"""The contract of the front matter of the Markdown documents elaboration hands on."""
TRD_FRONT_MATTER: Final = "TrdDocument"
"""The TRD's definition in :data:`FRONT_MATTER_CONTRACT`."""
SPEC_FRONT_MATTER: Final = "SpecDocument"
"""The contracts and data-model documents' definition in :data:`FRONT_MATTER_CONTRACT`."""


class DocumentValidationError(ValueError):
    """An authored document fails its content contract."""


class _JsonSafeLoader(yaml.SafeLoader):
    """A safe YAML loader whose values are all JSON values: a date or a time stays its text."""


def _timestamp_text(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> str:
    """Construct a YAML timestamp as the text it is written as.

    Returns:
        The scalar's text.

    """
    return loader.construct_scalar(node)


_JsonSafeLoader.add_constructor("tag:yaml.org,2002:timestamp", _timestamp_text)


def _json_safe_yaml(text: str) -> object:
    """Load one YAML document so that every value is a JSON value.

    Returns:
        The document; a date or a time in it is its text.

    """
    loader: _JsonSafeLoader = _JsonSafeLoader(text)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


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


def _front_matter_problem(front: dict[str, JsonValue], definition: str) -> str | None:
    """Check a document's front matter against its definition in the front matter contract.

    Args:
        front: The decoded front matter.
        definition: The ``$defs`` entry of :data:`FRONT_MATTER_CONTRACT` the document satisfies.

    Returns:
        The most relevant problem as one sentence; None when the front matter satisfies it.

    """
    contract: dict[str, JsonValue] = strict_json(FRONT_MATTER_CONTRACT)
    target: dict[str, JsonValue] = {"$defs": contract["$defs"], "$ref": f"#/$defs/{definition}"}
    if "$schema" in contract:
        target["$schema"] = contract["$schema"]
    try:
        strictschema.validate(front, target, location=FRONT_MATTER_CONTRACT)
    except ValidationError as exc:
        where: str = "/".join(str(part) for part in exc.absolute_path) or "<root>"
        return f"front matter does not satisfy {FRONT_MATTER_CONTRACT.name}#/$defs/{definition}: {where}: {exc.message}"
    return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def document(path: Path, matrix: Matrix, definition: str) -> tuple[list[str], list[str]]:
    """Validate document frontmatter and check each architecture citation against the matrix.

    Args:
        path: The authored document.
        matrix: The matrix, whose document entries hold every arc42 document and its headings.
        definition: The document's ``$defs`` entry in :data:`FRONT_MATTER_CONTRACT`
            (:data:`TRD_FRONT_MATTER` or :data:`SPEC_FRONT_MATTER`).

    Returns:
        The citations of the document's ``decisionIds``, and the warnings the check raised.

    Raises:
        TypeError: An argument violates the declared input contract.
        DocumentValidationError: Frontmatter is missing or does not satisfy its contract, or a
            citation names a document or a heading the matrix does not hold.

    """
    if not (isinstance(path, Path)) or not (isinstance(matrix, Matrix)) or not isinstance(definition, str):
        raise TypeError(_ARGUMENT_ERROR)
    text: str = path.read_text(encoding="utf-8")
    if not text.strip():
        message: str = f"missing or empty document: {path}"
        raise DocumentValidationError(message)
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        message = f"{path}: YAML frontmatter is missing"
        raise DocumentValidationError(message)
    try:
        raw_front: object = _json_safe_yaml(text[4:].split("\n---", 1)[0]) or {}
    except yaml.YAMLError as exc:
        message = f"{path}: invalid YAML frontmatter: {exc}"
        raise DocumentValidationError(message) from exc
    if not isinstance(raw_front, dict):
        message = f"{path}: frontmatter must be an object"
        raise DocumentValidationError(message)
    front: dict[str, JsonValue] = json_object(raw_front)
    problem: str | None = _front_matter_problem(front, definition)
    if problem is not None:
        message = f"{path}: {problem}"
        raise DocumentValidationError(message)
    ids: list[str] = check_type(
        front["decisionIds"],
        list[str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    unresolved: list[str] = [citation for citation in ids if cited(matrix, citation) is None]
    if unresolved:
        message = f"decisionIds the matrix holds no document and heading for: {unresolved}"
        raise DocumentValidationError(message)
    warnings: list[str] = [] if ids else ["decisionIds is empty"]
    return ids, warnings


def _dangling(matrix: Matrix, bead: str, headings: set[str], removed: Collection[str]) -> list[tuple[EntryId, str]]:
    """Find the constraints of an Epic's TRD whose requirement is no heading of the TRD.

    Returns:
        Each such constraint with the requirement id it points at, in matrix order; a constraint
        of a requirement in ``removed`` is left out.

    """
    gone: set[str] = {requirement.strip() for requirement in removed}
    found: list[tuple[EntryId, str]] = []
    entry: Entry
    for entry in matrix.entries((KIND_CONSTRAINT,)):
        pointer: JsonValue = entry.attributes.get(ATTR_TRD)
        if not isinstance(pointer, dict) or pointer.get("epic") != bead:
            continue
        requirement: str = str(pointer.get("requirement"))
        if requirement not in headings and requirement not in gone:
            found.append((entry.id, requirement))
    return found


def _headings(text: str) -> set[str]:
    """Read the heading texts of a Markdown document.

    Returns:
        Each heading's text, stripped.

    """
    return {found.strip() for found in MARKDOWN_HEADING.findall(text)}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def unresolved_requirements(
    matrix: Matrix,
    bead: str,
    text: str,
    *,
    removed: Collection[str],
    written: Collection[str],
) -> list[str]:
    """Find the requirements of an Epic's TRD the matrix would point at that are no heading of the TRD.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id.
        text: The TRD's text.
        removed: The requirement ids a TRD answer removes; recording the answer removes their
            constraints, so they are not checked.
        written: The requirement ids a TRD answer adds or changes; recording the answer points a
            constraint at each, so each needs a heading.

    Returns:
        One sentence per constraint whose ``trd`` names this Epic and a requirement id that is no
        heading of the TRD, and per written id that is no heading; empty when every pointer resolves.

    """
    headings: set[str] = _headings(text)
    problems: list[str] = [
        f"{constraint} points at TRD requirement {requirement!r}, which the TRD has no heading for"
        for constraint, requirement in _dangling(matrix, bead, headings, removed)
    ]
    problems.extend(
        f"the answer states requirement {requirement!r}, which the TRD has no heading for"
        for requirement in written
        if requirement.strip() not in headings
    )
    return problems


def _mark_trd(context: RunContext, tools: Tools, output: Path) -> str:
    """Record the TRD's path and digest on the Epic bead, unless the bead already holds them.

    Returns:
        The SHA-256 digest of the TRD.

    """
    digest: str = hashlib.sha256(output.read_bytes()).hexdigest()
    relative: str = str(output.resolve().relative_to(env_path(PROJECT_ROOT_ENV)))
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


CORRECTION_DESCRIPTION: Final = "Correct the TRD where its confirmation found it does not resolve"
RECONFIRM_DESCRIPTION: Final = "Confirm the TRD after its correction"
TRD_CORRECTIONS: Final = "TRD corrections requested"
CORRECTION_FILE: Final = "trd-confirm"
"""The stem of the request and answer files of the TRD correction, in the helpers folder."""
REQUEST_SUFFIX: Final = ".request.json"
ANSWER_SUFFIX: Final = ".answer.json"
ID_LENGTH: Final = 8
"""How much of the confirm step's id names its correction's files."""


def _dangling_change(trd: Path, constraint: EntryId, requirement: str) -> TrdChange:
    """State one constraint whose requirement the TRD has no heading for as a change to the TRD.

    Returns:
        A ``change`` of the requirement that says what is wrong and what correcting it means.

    """
    return {
        "change": "change",
        "id": requirement,
        "kind": "obligation",
        "statement": (
            f"The matrix's constraint {constraint} points at requirement {requirement}, and the TRD has no "
            f"heading whose text is exactly {requirement}: make that requirement's heading exactly its id, "
            "or remove the requirement and list it under removed when no source states it any longer."
        ),
        "source": {"source": str(trd), "heading": requirement},
        "appliesTo": "",
    }


def _document_change(trd: Path, problem: str) -> TrdChange:
    """State a problem of the TRD's front matter or citations as a change to the TRD.

    Returns:
        A ``change`` with no requirement id that says what is wrong.

    """
    return {
        "change": "change",
        "id": "",
        "kind": "obligation",
        "statement": (
            f"The TRD fails its check: {problem}. Correct the front matter and every decisionIds citation "
            "so that each names a document and heading the matrix holds, as the architecture pack and "
            "`atw-matrix node document:<path>` give them."
        ),
        "source": {"source": str(trd), "heading": ""},
        "appliesTo": "",
    }


def _correction(run: StepRun, context: ArchitectureContext, changes: list[TrdChange]) -> Completion:
    """Plan one TRD author update of what the confirmation found, then the confirmation again.

    Returns:
        The completion that keeps the step running with the update and the second confirmation
        under it, and records the changes requested.

    """
    helpers: Path = Path(context["helpersFolder"])
    stem: str = f"{CORRECTION_FILE}-{run.step['id'][:ID_LENGTH]}"
    asked: Path = helpers / (stem + REQUEST_SUFFIX)
    request: TrdRequest = validate_trd_request(
        {
            "mode": TRD_MODE_UPDATE,
            "epic": context["bead"],
            "prdPath": context["prdPath"],
            "trdPath": context["trdPath"],
            "sharedCapabilities": [],
            "changes": changes,
            "answerPath": str(helpers / (stem + ANSWER_SUFFIX)),
        },
    )
    write_json(asked, request)
    update: StepPlan = {
        "description": CORRECTION_DESCRIPTION,
        "purpose": "The TRD's citations and requirement headings resolve against the matrix",
        "agent": TRD_AUTHOR,
    }
    again: StepPlan = {
        "description": RECONFIRM_DESCRIPTION,
        "purpose": "The Epic carries one reviewed TRD whose every source resolves",
        "script": CONFIRM_TRD,
    }
    requested: list[JsonValue] = [change["statement"] for change in changes]
    return Completion(
        artifacts=(value_artifact(TRD_CORRECTIONS, requested),),
        add=(StepGroup((NewStep(update, params={PARAM_REQUEST: str(asked)}), NewStep(again)), UNDER_THIS),),
    )


@script_step(CONFIRM_TRD)
def confirm(run: StepRun) -> Completion:
    """Confirm the reviewed TRD: the matrix holds every source it cites, and the Epic bead carries it.

    A TRD whose front matter or a citation is invalid, or that has no heading for a requirement a
    constraint of the matrix points at, is corrected once: the step plans one TRD author update
    of what it found and then itself again under it. The second confirmation corrects nothing.

    Returns:
        The TRD file and the digest recorded on the Epic bead; or, for the first confirmation of
        a TRD that does not resolve, the correction it plans.

    Raises:
        ArchitectureStepError: The TRD is missing or unreadable, or it still does not resolve at
            the confirmation after its correction.

    """
    enter_phase(run.context, run.agents.emit, TRD_AUTHORING_PHASE, CONFIRM_TRD)
    context: ArchitectureContext = read_context(run)
    trd: Path = Path(context["trdPath"])
    matrix: Matrix = run.tools.portfolio(CONFIRM_TRD, read_matrix, matrix_path(None, os.environ))
    try:
        text: str = trd.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ArchitectureStepError(run, f"{trd}: {exc}") from None
    warnings: list[str] = []
    changes: list[TrdChange] = [
        _dangling_change(trd, constraint, requirement)
        for constraint, requirement in _dangling(matrix, str(run.bead), _headings(text), ())
    ]
    try:
        warnings = document(trd, matrix, TRD_FRONT_MATTER)[1]
    except DocumentValidationError as exc:
        changes.insert(0, _document_change(trd, str(exc)))
    if changes:
        above: Step | None = step_journal.parent_step(run.journal(), run.step["id"])
        if above is None or above.get("script") != CONFIRM_TRD:
            return _correction(run, context, changes)
        raise ArchitectureStepError(run, *(change["statement"] for change in changes))
    digest: str = _mark_trd(run.context, run.tools, trd)
    warned: list[JsonValue] = list(warnings)
    return Completion(
        artifacts=(
            file_artifact(ARTIFACT_TRD, trd),
            value_artifact(TRD_HASH, digest),
            *((value_artifact(TRD_WARNINGS, warned),) if warned else ()),
        ),
    )
