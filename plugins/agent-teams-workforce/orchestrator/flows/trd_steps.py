"""The TRD's two steps in the architecture: the script seed before the architect, the one TRD write after it.

The seed (``trd.seed``) runs after the architecture pack and before the solutions architect. It
writes the TRD at the context file's ``trdPath`` from the matrix, with no session: one
requirement for each constraint with a rule that binds the Epic or an entry of its reach
(``matrixtraverse.constraints_for``), and one for each constraint of arc42 section 2 with a rule,
no selector and nothing it applies to, which binds every Epic. Each requirement is headed by its
constraint's id and states the constraint's rule, what it applies to and each heading that states
it. The seed is not recorded in the matrix: its requirements are the matrix's own constraints, which
bind the entries they name already. The seed starts the TRD over: it removes every constraint that
points at a requirement of this Epic's TRD, which an earlier run recorded.

The TRD write (``trd-author``, request mode ``complete``) runs once, when the architecture check
passes and before the promotion (``architecture_check``): it adds the requirements the PRD implies
that the TRD does not state, applies the architect's ``trdChanges`` and writes each shared
capability of the result that the TRD does not yet state. Its launch and the recording of its
answer are ``architecture.trd_author``.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import yaml
from architecture_work_contract import TRD_MODE_COMPLETE, validate_trd_request
from matrix_contract import KIND_CONSTRAINT, REL_APPLIES_TO, REL_STATED_IN
from matrixheadings import heading_ref
from matrixstore import as_entry_id, update_matrix
from matrixtraverse import constraints_for, epic_id
from typeguard import CollectionCheckStrategy, check_type

from orchestrator.core.agents import strict_json
from orchestrator.core.io import JsonValue, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, file_artifact, value_artifact
from orchestrator.flows.architecture_files import (
    ARTIFACT_TRD,
    SEED_TRD,
    TRD_AUTHOR,
    ArchitectureContext,
    document_path,
    matrix_file,
    read_context,
    read_result,
)
from orchestrator.flows.architecture_pack import SECTION_TWO, pack_file
from orchestrator.flows.trd_authoring import cited

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureResult, TrdRequest
    from matrix_contract import Entry, EntryId
    from matrixstore import Matrix
    from matrixtraverse import ConstraintReach
    from step_journal_contract import StepPlan


SEED_REF: Final = "trd-seed"
SEED_DESCRIPTION: Final = "Seed the TRD from the constraints that bind the Epic"
SEED_PURPOSE: Final = (
    "The architect designs against every sourced constraint that binds the Epic, and no session copies them"
)
WRITE_DESCRIPTION: Final = "Write the TRD from the architect's decisions"
WRITE_PURPOSE: Final = "One TRD session adds the requirements the PRD implies and applies the architect's TRD changes"
WRITE_FILE: Final = "trd"
"""The stem of the request and answer files of the TRD write, in the helpers folder."""
REQUEST_SUFFIX: Final = ".request.json"
ANSWER_SUFFIX: Final = ".answer.json"
SEEDED: Final = "seeded requirements"
CLEARED: Final = "earlier TRD constraints removed"
ATTR_STATEMENT: Final = "statement"
ATTR_SELECTOR: Final = "selector"
ATTR_TRD: Final = "trd"
ATTR_EPIC: Final = "epic"
ATTR_HEADING: Final = "heading"
SECTION_TITLE: Final = "Constraints that bind the Epic"
EPIC_AS_A_WHOLE: Final = "the Epic as a whole"


class SeedRequirement(TypedDict):
    """One requirement of the TRD seed: one constraint of the matrix with a rule."""

    id: str
    statement: str
    appliesTo: list[str]
    """The entries of the reach the constraint's ``appliesTo`` relationships name; empty when it
    names only the Epic, or none."""
    selector: dict[str, JsonValue] | None
    """The constraint's selector, when it selects an entry of the reach."""
    sources: list[str]
    """Each document heading that states the constraint, as ``<path>#<heading>``."""


@dataclass(frozen=True)
class Seed:
    """What the seed wrote and changed."""

    text: str
    """The TRD."""
    requirements: int
    """How many requirements the TRD holds."""
    cleared: tuple[str, ...]
    """The constraints of this Epic's earlier TRD the seed removed from the matrix."""


def seed_plan(inputs: list[str]) -> StepPlan:
    """Plan the step that seeds the TRD.

    Returns:
        The plan of the script step, handed the steps ``inputs`` names.

    """
    return {
        "ref": SEED_REF,
        "description": SEED_DESCRIPTION,
        "purpose": SEED_PURPOSE,
        "script": SEED_TRD,
        "inputs": inputs,
    }


def write_plan(inputs: list[str]) -> StepPlan:
    """Plan the one TRD write after the architect's decisions.

    Returns:
        The plan of ``trd-author``'s step, handed the steps ``inputs`` names.

    """
    return {"description": WRITE_DESCRIPTION, "purpose": WRITE_PURPOSE, "agent": TRD_AUTHOR, "inputs": inputs}


def _sources(matrix: Matrix, constraint: EntryId) -> list[str]:
    """Name the document headings that state one constraint.

    Returns:
        Each as ``<path>#<heading>``, the path under the architecture root, once, in matrix order.

    """
    refs: dict[str, None] = {}
    for stated in matrix.outgoing(constraint, (REL_STATED_IN,)):
        heading: JsonValue = stated.attributes.get(ATTR_HEADING)
        refs[heading_ref(document_path(stated.end), heading if isinstance(heading, str) else "")] = None
    return list(refs)


def _requirement(
    matrix: Matrix,
    constraint: Entry,
    applied: list[str],
    selector: dict[str, JsonValue] | None,
) -> SeedRequirement | None:
    """State one constraint as a requirement of the seed.

    Returns:
        The requirement; None for a constraint with no rule, such as one that points at a
        requirement of a TRD.

    """
    statement: JsonValue = constraint.attributes.get(ATTR_STATEMENT)
    if not isinstance(statement, str) or not statement.strip() or ATTR_TRD in constraint.attributes:
        return None
    return {
        "id": constraint.id,
        "statement": " ".join(statement.split()),
        "appliesTo": applied,
        "selector": selector,
        "sources": _sources(matrix, constraint.id),
    }


def _binds_every_epic(matrix: Matrix, constraint: Entry) -> bool:
    """Tell whether a constraint is one of arc42 section 2 that names nothing it applies to.

    Returns:
        True when an arc42 section 2 document states it, and it has no selector and no
        ``appliesTo`` relationship.

    """
    if constraint.attributes.get(ATTR_SELECTOR) or matrix.outgoing(constraint.id, (REL_APPLIES_TO,)):
        return False
    return any(
        "/" in document_path(stated.end) and document_path(stated.end).split("/")[-2].startswith(SECTION_TWO)
        for stated in matrix.outgoing(constraint.id, (REL_STATED_IN,))
    )


def seed_requirements(matrix: Matrix, bead: str, reach: list[str]) -> list[SeedRequirement]:
    """List the requirements of an Epic's TRD seed.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id.
        reach: The ids of the entries of the Epic's reach, as the architecture pack lists them.

    Returns:
        One requirement for each constraint with a rule that binds the Epic or an entry of its
        reach, and for each constraint of arc42 section 2 with a rule that binds every Epic, in
        constraint id order.

    """
    epic: EntryId = epic_id(bead)
    found: dict[str, SeedRequirement] = {}
    binding: ConstraintReach
    for binding in constraints_for(matrix, [epic, *(as_entry_id(entry) for entry in reach)]):
        constraint: Entry = matrix.entry(binding.constraint)
        held: JsonValue = constraint.attributes.get(ATTR_SELECTOR)
        selector: dict[str, JsonValue] | None = dict(held) if binding.selected and isinstance(held, dict) else None
        applied: list[str] = list(dict.fromkeys(str(link.end) for link in binding.applied if link.end != epic))
        row: SeedRequirement | None = _requirement(matrix, constraint, applied, selector)
        if row is not None:
            found[row["id"]] = row
    for constraint in matrix.entries((KIND_CONSTRAINT,)):
        if constraint.id not in found and _binds_every_epic(matrix, constraint):
            every: SeedRequirement | None = _requirement(matrix, constraint, [], None)
            if every is not None:
                found[every["id"]] = every
    return [found[key] for key in sorted(found)]


def _applies(requirement: SeedRequirement) -> str:
    """Say what one seeded requirement applies to.

    Returns:
        The entries it names, then the selector it selects entries by; the Epic as a whole when neither.

    """
    parts: list[str] = [f"`{entry}`" for entry in requirement["appliesTo"]]
    if requirement["selector"] is not None:
        parts.append(f"every entry the selector `{json.dumps(requirement['selector'], sort_keys=True)}` selects")
    return "; ".join(parts) or EPIC_AS_A_WHOLE


def _block(requirement: SeedRequirement) -> str:
    """Render one seeded requirement as its heading, its rule and its sources.

    Returns:
        The Markdown of the requirement.

    """
    sources: str = ", ".join(f"`{ref}`" for ref in requirement["sources"]) or "no document; the matrix's constraint"
    return f"#### {requirement['id']}\n\n{requirement['statement']}\n\nSource: {sources}\n"


def seed_text(name: str, bead: str, requirements: list[SeedRequirement], citations: list[str]) -> str:
    """Write the TRD seed.

    Args:
        name: The Epic's name.
        bead: The Epic's beads id.
        requirements: The seeded requirements.
        citations: The ``<path>#<heading>`` references of the front matter's ``decisionIds``.

    Returns:
        The TRD: its front matter, its introduction, and one heading for each set of entries the
        requirements apply to, the Epic as a whole first, with one heading per requirement under it.

    """
    front: str = yaml.safe_dump({"decisionIds": citations}, sort_keys=False, allow_unicode=True, width=10_000)
    groups: dict[str, list[SeedRequirement]] = {}
    for requirement in requirements:
        groups.setdefault(_applies(requirement), []).append(requirement)
    order: list[str] = sorted(groups, key=lambda applies: (applies != EPIC_AS_A_WHOLE, applies))
    sections: str = "\n".join(
        f"### Applies to {applies}\n\n" + "\n".join(_block(requirement) for requirement in groups[applies])
        for applies in order
    )
    introduction: str = (
        f"# Technical Requirements: {name} ({bead})\n\n"
        "The requirements not considered functional that the architecture of this Epic must support: "
        "the quality constraints and operational boundaries of the technical architecture. The script "
        "`trd.seed` wrote this TRD from the matrix before the solutions architect started: under "
        f'"{SECTION_TITLE}", one requirement for each constraint with a rule that binds the Epic or an '
        "entry it reaches, and for each constraint of arc42 section 2 that binds every Epic. Each is of "
        "kind `obligation`, headed by its constraint's id, under the heading that names what it applies "
        "to (matrix ids, or the selector that selects them), with its rule and each heading that states "
        "it as `<path>#<heading>`. The TRD write after the architect's decisions adds the requirements "
        "the PRD implies and the architect's changes.\n\n"
        "Each requirement is one heading whose text is its id. Kind `obligation` is something that must "
        "be true of the element with a checkable value; `reuse` is a behaviour the element obtains from "
        "a shared capability and does not implement itself.\n\n"
        f"## {SECTION_TITLE}\n\n"
    )
    return f"---\n{front}---\n\n{introduction}{sections}"


def _clear(matrix: Matrix, bead: str) -> tuple[str, ...]:
    """Remove the constraints that point at a requirement of an Epic's TRD.

    Returns:
        The ids removed, in matrix order.

    """
    gone: list[EntryId] = []
    constraint: Entry
    for constraint in matrix.entries((KIND_CONSTRAINT,)):
        pointer: JsonValue = constraint.attributes.get(ATTR_TRD)
        if isinstance(pointer, dict) and pointer.get(ATTR_EPIC) == bead:
            gone.append(constraint.id)
    for entry_id in gone:
        matrix.remove(entry_id)
    return tuple(str(entry_id) for entry_id in gone)


def write_seed(bead: str, reach: list[str], arch: Path) -> Seed:
    """Start an Epic's TRD over from the matrix, as one change of the matrix.

    Args:
        bead: The Epic's beads id.
        reach: The ids of the entries of the Epic's reach.
        arch: The architecture root.

    Returns:
        The TRD seed's text, how many requirements it holds, and the constraints of the Epic's
        earlier TRD removed from the matrix.

    """

    def change(matrix: Matrix) -> Seed:
        cleared: tuple[str, ...] = _clear(matrix, bead)
        requirements: list[SeedRequirement] = seed_requirements(matrix, bead, reach)
        refs: dict[str, None] = dict.fromkeys(ref for requirement in requirements for ref in requirement["sources"])
        citations: list[str] = sorted(ref for ref in refs if cited(matrix, arch, ref) is not None)
        name: str = matrix.entry(epic_id(bead)).name
        return Seed(seed_text(name, bead, requirements, citations), len(requirements), cleared)

    return update_matrix(matrix_file(), change)


@script_step(SEED_TRD)
def seed(run: StepRun) -> Completion:
    """Write the Epic's TRD seed at the context file's ``trdPath``.

    Returns:
        The TRD as an artifact, how many requirements it holds, and the constraints of the
        Epic's earlier TRD removed from the matrix.

    """
    context: ArchitectureContext = read_context(run)
    rows: list[dict[str, JsonValue]] = check_type(
        strict_json(pack_file(run))["reach"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    reach: list[str] = [check_type(row["id"], str) for row in rows]
    written: Seed = run.tools.portfolio(SEED_TRD, write_seed, str(run.bead), reach, Path(context["architectureRoot"]))
    trd: Path = Path(context["trdPath"])
    trd.parent.mkdir(parents=True, exist_ok=True)
    trd.write_text(written.text, encoding="utf-8")
    cleared: list[JsonValue] = [*written.cleared]
    return Completion(
        artifacts=(
            file_artifact(ARTIFACT_TRD, trd),
            value_artifact(SEEDED, written.requirements),
            value_artifact(CLEARED, cleared),
        ),
    )


def write_request(run: StepRun) -> Path:
    """Write the request of the TRD write from the architect's result.

    Returns:
        The request file, in the helpers folder: mode ``complete`` for the Epic, its PRD and TRD,
        the result's ``trdChanges`` and ``sharedCapabilities``, and the answer path beside it.

    """
    context: ArchitectureContext = read_context(run)
    result: ArchitectureResult = read_result(run, context)
    helpers: Path = Path(context["helpersFolder"])
    asked: Path = helpers / (WRITE_FILE + REQUEST_SUFFIX)
    request: TrdRequest = validate_trd_request(
        {
            "mode": TRD_MODE_COMPLETE,
            "epic": context["bead"],
            "prdPath": context["prdPath"],
            "trdPath": context["trdPath"],
            "sharedCapabilities": result["sharedCapabilities"],
            "changes": result["trdChanges"],
            "answerPath": str(helpers / (WRITE_FILE + ANSWER_SUFFIX)),
        },
        str(asked),
    )
    write_json(asked, request)
    return asked


__all__ = [
    "SEED_REF",
    "WRITE_DESCRIPTION",
    "seed",
    "seed_plan",
    "seed_requirements",
    "write_plan",
    "write_request",
    "write_seed",
]
