"""The script step that assembles one Epic's architecture pack before the TRD and the architect start.

The pack is the architect's, the TRD author's and the specialists' view of the vault and the
matrix for the Epic, in one local file, so no session reads the whole matrix or the vault document
by document. ``pack.json`` holds:

- ``epic``: the Epic's beads id;
- ``prd``: the PRD's path and text;
- ``epicView``: what ``atw-matrix epic`` returns for the Epic;
- ``reach``: one row per entry of the Epic's approval scope (``matrixtraverse.reach_rows``, the rule
  of reach): its ``id``, ``kind``, ``approved`` (whether it carries the approved mark), ``via`` (the
  links that put it in reach), ``sharedWith`` (the other Epics that reach it) and ``headings``,
  each document heading that describes it (``covers`` for a requirement, ``describedBy`` for any
  other entry) as its ``path`` under the architecture root and its ``heading``;
- ``headings``: each heading the rows name, once, with its ``text``: many entries share a heading,
  so its text is listed once rather than in every row that names it;
- ``constraints``: every constraint stated in arc42 section 2, and every other constraint that
  binds an entry of the reach (``matrixtraverse.constraints_for``).

Heading text is read from the vault's last commit (``git show HEAD:<path>``), never from the
working tree. ``pack.md`` holds the same content for reading.
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
from matrixquery import epic_view
from matrixstore import read_matrix
from matrixsync import heading_texts, relative_path, vault_root
from matrixtraverse import constraints_for, epic_id, reach_rows

from orchestrator.core import step_journal
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, file_artifact
from orchestrator.core.models import StaleInputError
from orchestrator.flows.architecture_files import (
    ARTIFACT_PACK,
    ARTIFACT_PACK_TEXT,
    OPEN_RUN,
    PACK,
    PACK_FILE,
    PACK_TEXT_FILE,
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
    "The TRD author, the architect and its specialists read the Epic's reach, its headings and its "
    "constraints from one local file, never the whole matrix or the vault"
)
PACK_REF: Final = "pack"
SECTION_TWO: Final = "02-"
"""What the folder of an arc42 section 2 document begins with."""
ATTR_HEADING: Final = "heading"
ATTR_STATEMENT: Final = "statement"
ATTR_SELECTOR: Final = "selector"
ATTR_TRD: Final = "trd"
GIT: Final = "git"


class PackHeadingRef(TypedDict):
    """One document heading that describes an entry of the reach."""

    path: str
    """The document, by its path under the architecture root."""
    heading: str


class PackHeading(TypedDict):
    """One document heading the reach names, with its text."""

    path: str
    heading: str
    text: str
    """The heading's own text at the vault's last commit; empty when that commit does not hold it."""


class PackRow(TypedDict):
    """One entry of the Epic's reach, as the pack lists it."""

    id: str
    kind: str
    approved: bool
    via: str
    sharedWith: list[str]
    headings: list[PackHeadingRef]


class PackSource(TypedDict):
    """One document heading a constraint is stated in."""

    path: str
    heading: str


class PackConstraint(TypedDict):
    """One constraint that applies to the Epic."""

    id: str
    name: str
    statement: str | None
    selector: dict[str, JsonValue] | None
    trd: dict[str, JsonValue] | None
    appliesTo: list[str]
    """The entries of the reach the constraint's ``appliesTo`` relationships name; its ``selector``
    states the rest of what it binds."""
    statedIn: list[PackSource]


class PackPrd(TypedDict):
    """The PRD the Epic is elaborated from."""

    path: str
    text: str


class Pack(TypedDict):
    """What ``pack.json`` holds."""

    epic: str
    prd: PackPrd
    epicView: dict[str, JsonValue]
    reach: list[PackRow]
    headings: list[PackHeading]
    constraints: list[PackConstraint]


class MatrixPart(TypedDict):
    """What the pack takes from the matrix, before the heading texts are read from the vault."""

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


def _describing(matrix: Matrix, row: ReachRow) -> list[tuple[str, str]]:
    """Name the document headings that describe one entry of the reach.

    Returns:
        For a requirement, each heading that ``covers`` it; for any other entry, each heading it
        is ``describedBy``; each as the document's path under the architecture root and the
        heading, once, in the order the matrix holds them.

    """
    found: list[Relationship] = (
        [*matrix.incoming(row.id, (REL_COVERS,))]
        if row.kind == KIND_REQUIREMENT
        else [*matrix.outgoing(row.id, (REL_DESCRIBED_BY,))]
    )
    pairs: dict[tuple[str, str], None] = {}
    relationship: Relationship
    for relationship in found:
        document: EntryId = relationship.start if row.kind == KIND_REQUIREMENT else relationship.end
        heading: JsonValue = relationship.attributes.get(ATTR_HEADING)
        if document.startswith(f"{KIND_DOCUMENT}:") and isinstance(heading, str) and heading:
            pairs[document_path(document), heading] = None
    return list(pairs)


def _constraint(matrix: Matrix, constraint: Entry, binds: list[str]) -> PackConstraint:
    """Render one constraint for the pack.

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


def matrix_part(bead: str) -> tuple[MatrixPart, list[list[tuple[str, str]]]]:
    """Read from the matrix what the pack holds of it.

    Returns:
        The Epic's view, its reach rows with no heading text yet and its constraints; and, for
        each row in the same order, the document headings that describe it.

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
            "headings": [],
        }
        for row in rows
    ]
    part: MatrixPart = {
        "epicView": json_object(epic_view(matrix, bead)),
        "reach": reach,
        "constraints": _constraints(matrix, [epic, *(row.id for row in rows)]),
    }
    return part, [_describing(matrix, row) for row in rows]


def _committed(run: StepRun, vault: Path, path: Path) -> str | None:
    """Read a file of the vault as its last commit holds it.

    Returns:
        The file's text at ``HEAD``; None when the path is outside the vault or ``HEAD`` does not
        hold it.

    """
    if not path.resolve().is_relative_to(vault.resolve()):
        return None
    shown = run.tools.command(
        [GIT, "-C", str(vault), "show", f"HEAD:{relative_path(path, vault)}"],
        stage=PACK,
        check=False,
    )
    return shown.stdout if shown.exit == 0 else None


def _heading_texts(run: StepRun, arch: Path, vault: Path, wanted: set[str]) -> dict[str, dict[str, str]]:
    """Read the heading texts of some documents from the vault's last commit.

    Returns:
        Each document, by its path under the architecture root, with each heading's own text
        (``matrixsync.heading_texts``); a document the commit does not hold has none.

    """
    texts: dict[str, dict[str, str]] = {}
    relative: str
    for relative in sorted(wanted):
        held: str | None = _committed(run, vault, arch / relative)
        texts[relative] = {} if held is None else heading_texts(held.splitlines())
    return texts


def _prd_text(run: StepRun, prd: Path, vault: Path) -> str:
    """Read the PRD from the vault's last commit, or from its file when no commit holds it.

    Returns:
        The PRD's text.

    """
    held: str | None = _committed(run, vault, prd)
    return prd.read_text(encoding="utf-8") if held is None else held


def _markdown(pack: Pack) -> str:
    """Render the pack for reading.

    Returns:
        The PRD path, each reach row with the headings that describe it, each heading's text once,
        and each constraint.

    """
    lines: list[str] = [
        f"# Architecture pack of {pack['epic']}",
        "",
        f"PRD: `{pack['prd']['path']}` (its text is in pack.json under prd.text).",
        "",
        f"## Reach ({len(pack['reach'])} entries)",
    ]
    row: PackRow
    for row in pack["reach"]:
        approved: str = "yes" if row["approved"] else "no"
        shared: str = ", ".join(row["sharedWith"]) or "no other Epic"
        lines.extend([
            "",
            f"### {row['id']}",
            "",
            f"- kind: {row['kind']}; approved: {approved}",
            f"- via: {row['via']}",
            f"- shared with: {shared}",
        ])
        lines.extend(f"- described by `{named['path']}` # {named['heading']}" for named in row["headings"])
    lines.extend(["", f"## Headings ({len(pack['headings'])})"])
    heading: PackHeading
    for heading in pack["headings"]:
        text: str = heading["text"] or "(the vault's last commit holds no such heading)"
        lines.extend(["", f"### `{heading['path']}` # {heading['heading']}", "", text])
    lines.extend(["", f"## Constraints ({len(pack['constraints'])})"])
    constraint: PackConstraint
    for constraint in pack["constraints"]:
        rule: str = constraint["statement"] or (f"TRD requirement {constraint['trd']}" if constraint["trd"] else "")
        stated: str = "; ".join(f"`{source['path']}` # {source['heading']}" for source in constraint["statedIn"])
        lines.extend([
            "",
            f"- **{constraint['id']}**: {rule}",
            f"  - selector: {constraint['selector']}; applies to: {', '.join(constraint['appliesTo']) or 'none named'}",
            f"  - stated in: {stated or 'no document'}",
        ])
    return "\n".join([*lines, ""])


def build_pack(run: StepRun, arch: Path, prd: Path) -> Pack:
    """Assemble the pack of the step's Epic from the matrix and the vault's last commit.

    Returns:
        The pack.

    """
    vault: Path = run.tools.portfolio(PACK, vault_root, arch)
    part: MatrixPart
    describing: list[list[tuple[str, str]]]
    part, describing = run.tools.portfolio(PACK, matrix_part, str(run.bead))
    texts: dict[str, dict[str, str]] = _heading_texts(
        run,
        arch,
        vault,
        {relative for pairs in describing for relative, _ in pairs},
    )
    row: PackRow
    pairs: list[tuple[str, str]]
    for row, pairs in zip(part["reach"], describing, strict=True):
        row["headings"] = [{"path": relative, "heading": heading} for relative, heading in pairs]
    named: list[tuple[str, str]] = sorted({pair for pairs in describing for pair in pairs})
    return {
        "epic": str(run.bead),
        "prd": {"path": str(prd), "text": _prd_text(run, prd, vault)},
        "epicView": part["epicView"],
        "reach": part["reach"],
        "headings": [
            {"path": relative, "heading": heading, "text": texts.get(relative, {}).get(heading, "")}
            for relative, heading in named
        ],
        "constraints": part["constraints"],
    }


def write_pack(folder: Path, pack: Pack) -> tuple[Path, Path]:
    """Write the pack and the same pack for reading into the Epic's architecture work folder.

    Returns:
        ``pack.json`` and ``pack.md``.

    """
    written: Path = folder / PACK_FILE
    write_json(written, pack)
    readable: Path = folder / PACK_TEXT_FILE
    readable.write_text(_markdown(pack), encoding="utf-8")
    return written, readable


@script_step(PACK)
def assemble(run: StepRun) -> Completion:
    """Assemble the Epic's architecture pack beside the context file.

    Returns:
        ``pack.json`` and ``pack.md`` as artifacts.

    """
    context: ArchitectureContext = read_context(run)
    pack: Pack = build_pack(run, Path(context["architectureRoot"]), Path(context["prdPath"]))
    written: Path
    readable: Path
    written, readable = write_pack(architecture_folder(run.context.work), pack)
    return Completion(artifacts=(file_artifact(ARTIFACT_PACK, written), file_artifact(ARTIFACT_PACK_TEXT, readable)))


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


__all__ = ["PACK_REF", "assemble", "build_pack", "matrix_part", "pack_file", "pack_plan", "write_pack"]
