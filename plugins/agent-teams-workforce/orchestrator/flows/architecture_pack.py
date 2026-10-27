"""The script step that writes one Epic's architecture pack before the TRD and the architect start.

The pack is an index of the vault and the matrix for the Epic, in two local files beside the
context file, so no session reads the whole matrix, and a session reads a heading's words only when
a decision turns on them. ``pack.json`` holds:

- ``epic``: the Epic's beads id;
- ``prd``: the PRD's path;
- ``epicView``: what ``atw-matrix epic`` returns for the Epic;
- ``reach``: one row per entry of the Epic's approval scope (``matrixtraverse.reach_rows``, the rule
  of reach): its ``id``, ``kind``, ``approved`` (whether it carries the approved mark), ``via`` (the
  links that put it in reach), ``sharedWith`` (the other Epics that reach it) and ``headings``,
  each document heading that describes it (``covers`` for a requirement, ``describedBy`` for any
  other entry) as a reference ``<path>#<heading>``, the path under the architecture root, which
  ``atw-matrix heading`` takes to print the heading's text from the vault's last commit;
- ``constraints``: the ``id``, ``name`` and ``appliesTo`` of every constraint that binds an entry
  of the reach (``matrixtraverse.constraints_for``);
- ``constraintsFile``: the path of ``constraints.json``.

``constraints.json`` holds each constraint in full (its rule, selector, TRD pointer, what it
applies to in the reach and each document heading that states it): every constraint stated in
arc42 section 2, which binds every Epic, and every constraint the pack's ``constraints`` names.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    KIND_CONSTRAINT,
    KIND_DOCUMENT,
    KIND_REQUIREMENT,
    REL_COVERS,
    REL_DESCRIBED_BY,
    REL_STATED_IN,
)
from matrixheadings import heading_ref
from matrixquery import epic_view
from matrixstore import read_matrix
from matrixtraverse import constraints_for, epic_id, reach_rows

from orchestrator.core import step_journal
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, file_artifact
from orchestrator.core.models import StaleInputError
from orchestrator.flows.architecture_files import (
    ARTIFACT_PACK,
    ARTIFACT_PACK_CONSTRAINTS,
    CONSTRAINTS_FILE,
    OPEN_RUN,
    PACK,
    PACK_FILE,
    ArchitectureContext,
    architecture_folder,
    document_path,
    matrix_file,
    read_context,
)

if TYPE_CHECKING:
    from matrix_contract import Entry, EntryId, Relationship
    from matrixstore import Matrix
    from matrixtraverse import ConstraintReach, ReachRow
    from step_journal_contract import Step, StepId, StepPlan

PACK_DESCRIPTION: Final = "Assemble the Epic's architecture pack"
PACK_PURPOSE: Final = (
    "The TRD author, the architect and its specialists read the Epic's reach, the headings that "
    "describe it and the constraints that bind it from one local index, never the whole matrix or the vault"
)
PACK_REF: Final = "pack"
SECTION_TWO: Final = "02-"
"""What the folder of an arc42 section 2 document begins with."""
ATTR_HEADING: Final = "heading"
ATTR_STATEMENT: Final = "statement"
ATTR_SELECTOR: Final = "selector"
ATTR_TRD: Final = "trd"


class PackRow(TypedDict):
    """One entry of the Epic's reach, as the pack lists it."""

    id: str
    kind: str
    approved: bool
    via: str
    sharedWith: list[str]
    headings: list[str]
    """Each document heading that describes the entry, as ``<path>#<heading>``."""


class PackSource(TypedDict):
    """One document heading a constraint is stated in."""

    path: str
    heading: str


class PackConstraint(TypedDict):
    """One constraint that applies to the Epic, in full, as ``constraints.json`` lists it."""

    id: str
    name: str
    statement: str | None
    selector: dict[str, JsonValue] | None
    trd: dict[str, JsonValue] | None
    appliesTo: list[str]
    """The entries of the reach the constraint's ``appliesTo`` relationships name; its ``selector``
    states the rest of what it binds."""
    statedIn: list[PackSource]


class PackConstraintRef(TypedDict):
    """One constraint that binds an entry of the reach, as the pack's index names it."""

    id: str
    name: str
    appliesTo: list[str]


class Pack(TypedDict):
    """What ``pack.json`` holds."""

    epic: str
    prd: str
    epicView: dict[str, JsonValue]
    reach: list[PackRow]
    constraints: list[PackConstraintRef]
    constraintsFile: str


class MatrixPart(TypedDict):
    """What the pack and its constraints file take from the matrix."""

    epicView: dict[str, JsonValue]
    reach: list[PackRow]
    constraints: list[PackConstraint]


def pack_plan(inputs: list[str]) -> StepPlan:
    """Plan the step that assembles the pack.

    Returns:
        The plan of the script step, handed the steps ``inputs`` names.

    """
    return {"ref": PACK_REF, "description": PACK_DESCRIPTION, "purpose": PACK_PURPOSE, "script": PACK, "inputs": inputs}


def _text(entry: Entry, name: str) -> str | None:
    """Read a text attribute of an entry.

    Returns:
        The attribute when it is a string; else None.

    """
    value: JsonValue = entry.attributes.get(name)
    return value if isinstance(value, str) else None


def _object(entry: Entry, name: str) -> dict[str, JsonValue] | None:
    """Read an object attribute of an entry.

    Returns:
        The attribute when it is an object; else None.

    """
    value: JsonValue = entry.attributes.get(name)
    return dict(value) if isinstance(value, dict) else None


def _describing(matrix: Matrix, row: ReachRow) -> list[str]:
    """Name the document headings that describe one entry of the reach.

    Returns:
        For a requirement, each heading that ``covers`` it; for any other entry, each heading it
        is ``describedBy``; each as ``<path>#<heading>``, the path under the architecture root,
        once, in the order the matrix holds them.

    """
    found: list[Relationship] = (
        [*matrix.incoming(row.id, (REL_COVERS,))]
        if row.kind == KIND_REQUIREMENT
        else [*matrix.outgoing(row.id, (REL_DESCRIBED_BY,))]
    )
    refs: dict[str, None] = {}
    relationship: Relationship
    for relationship in found:
        document: EntryId = relationship.start if row.kind == KIND_REQUIREMENT else relationship.end
        heading: JsonValue = relationship.attributes.get(ATTR_HEADING)
        if document.startswith(f"{KIND_DOCUMENT}:") and isinstance(heading, str) and heading:
            refs[heading_ref(document_path(document), heading)] = None
    return list(refs)


def _constraint(matrix: Matrix, constraint: Entry, binds: list[str]) -> PackConstraint:
    """Render one constraint in full.

    Returns:
        Its rule, what it binds in the reach, and each document heading that states it.

    """
    sources: list[PackSource] = []
    stated: Relationship
    for stated in matrix.outgoing(constraint.id, (REL_STATED_IN,)):
        heading: JsonValue = stated.attributes.get(ATTR_HEADING)
        sources.append({"path": document_path(stated.end), "heading": heading if isinstance(heading, str) else ""})
    return {
        "id": constraint.id,
        "name": constraint.name,
        "statement": _text(constraint, ATTR_STATEMENT),
        "selector": _object(constraint, ATTR_SELECTOR),
        "trd": _object(constraint, ATTR_TRD),
        "appliesTo": binds,
        "statedIn": sources,
    }


def _constraints(matrix: Matrix, scope: list[EntryId]) -> list[PackConstraint]:
    """List the constraints that apply to an Epic's reach.

    Returns:
        Every constraint stated in an arc42 section 2 document, and every constraint that binds
        an entry of the reach, in id order, each once.

    """
    binding: dict[EntryId, list[str]] = {}
    found: ConstraintReach
    for found in constraints_for(matrix, scope):
        binding[found.constraint] = list(dict.fromkeys(relationship.end for relationship in found.applied))
    constraint: Entry
    for constraint in matrix.entries((KIND_CONSTRAINT,)):
        if any(
            document_path(stated.end).split("/")[-2].startswith(SECTION_TWO)
            for stated in matrix.outgoing(constraint.id, (REL_STATED_IN,))
            if "/" in document_path(stated.end)
        ):
            binding.setdefault(constraint.id, [])
    return [_constraint(matrix, matrix.entry(entry_id), binding[entry_id]) for entry_id in sorted(binding)]


def matrix_part(bead: str) -> MatrixPart:
    """Read from the matrix what the pack and its constraints file hold.

    Returns:
        The Epic's view, its reach rows with the headings that describe each, and every
        constraint that applies, in full.

    """
    matrix: Matrix = read_matrix(matrix_file())
    epic: EntryId = epic_id(bead)
    rows: list[ReachRow] = reach_rows(matrix, epic)
    reach: list[PackRow] = [
        {
            "id": row.id,
            "kind": row.kind,
            "approved": row.approved,
            "via": row.via,
            "sharedWith": [*row.shared_with],
            "headings": _describing(matrix, row),
        }
        for row in rows
    ]
    return {
        "epicView": json_object(epic_view(matrix, bead)),
        "reach": reach,
        "constraints": _constraints(matrix, [epic, *(row.id for row in rows)]),
    }


def write_pack(folder: Path, bead: str, prd: Path, part: MatrixPart) -> tuple[Path, Path]:
    """Write the pack and its constraints file into the Epic's architecture work folder.

    Returns:
        ``pack.json`` and ``constraints.json``.

    """
    constraints: Path = folder / CONSTRAINTS_FILE
    write_json(constraints, part["constraints"])
    pack: Pack = {
        "epic": bead,
        "prd": str(prd),
        "epicView": part["epicView"],
        "reach": part["reach"],
        "constraints": [
            {"id": held["id"], "name": held["name"], "appliesTo": held["appliesTo"]}
            for held in part["constraints"]
            if held["appliesTo"]
        ],
        "constraintsFile": str(constraints),
    }
    written: Path = folder / PACK_FILE
    write_json(written, pack)
    return written, constraints


@script_step(PACK)
def assemble(run: StepRun) -> Completion:
    """Assemble the Epic's architecture pack beside the context file.

    Returns:
        ``pack.json`` and ``constraints.json`` as artifacts.

    """
    context: ArchitectureContext = read_context(run)
    part: MatrixPart = run.tools.portfolio(PACK, matrix_part, str(run.bead))
    written: Path
    constraints: Path
    written, constraints = write_pack(
        architecture_folder(run.context.work),
        str(run.bead),
        Path(context["prdPath"]),
        part,
    )
    return Completion(
        artifacts=(file_artifact(ARTIFACT_PACK, written), file_artifact(ARTIFACT_PACK_CONSTRAINTS, constraints)),
    )


def pack_file(run: StepRun) -> Path:
    """Name the Epic's architecture pack, which the pack step wrote before the TRD and the architect.

    A pack that is missing was never assembled for this run, as in a journal opened before the
    pack step existed: the open-run step runs again and plans the pack step with the rest.

    Returns:
        ``pack.json`` beside the context file.

    Raises:
        StaleInputError: The pack is missing.

    """
    written: Path = architecture_folder(run.context.work) / PACK_FILE
    if written.is_file():
        return written
    opened: Step | None = next(
        (step for step in step_journal.steps_in_order(run.journal()) if step.get("script") == OPEN_RUN),
        None,
    )
    if opened is None:
        return written
    writer: StepId = opened["id"]
    raise StaleInputError(
        run.inputs.stage,
        writer,
        (f"step {run.step['id']} ({run.step['description']}): the architecture pack {written} was never assembled",),
    )


__all__ = ["PACK_REF", "assemble", "matrix_part", "pack_file", "pack_plan", "write_pack"]
