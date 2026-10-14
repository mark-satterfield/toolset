"""The files and names the steps of the Architecture container share.

The open-run step writes one context file and records it in the journal. It names every path the
script chose for the architecture work of the Epic: the architect's state and result files and
the TRD. Every later step is handed that file through the journal, so no step derives a path of
its own.

What a session reads of the architecture comes from the matrix: a script step writes the result
of a matrix read to a file, and the brief names that file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import (
    ArchitectureContext,
    ArchitectureResult,
    ArchitectureWorkError,
    SpecialistEntry,
    validate_architecture_context,
    validate_architecture_result,
)
from matrix_contract import KIND_DOCUMENT, EntryId, MatrixError
from matrixstore import ID_SEPARATOR, make_id, matrix_path
from review_criteria import CRITERIA_PATH

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.frontmatter import split_front_matter
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.models import StepError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from step_journal_contract import Artifact, Journal, Step, StepId

    from orchestrator.core.io import JsonValue
    from orchestrator.core.journal_steps import StepInputs, StepRun

OPEN_RUN: Final = "prd_to_spec.open_run"
CHECK: Final = "atw-matrix check; atw-matrix review-scope"
PROMOTE: Final = "atw-matrix sync-documents; atw-matrix commit"
CONFIRM_TRD: Final = "trd.confirm"
EARLIER_WORK: Final = "architecture.earlier_work"
"""The script keys of the steps of an elaboration's architecture part, as the journal shows them."""

ARCHITECTURE: Final = "Architecture"
"""The description of the outermost step that contains the architecture steps."""
EARLIER_PREFIX: Final = "earlier work: "
"""What the name of an artifact begins with when an earlier form of the pipeline produced the file."""

ARCHITECTURE_FOLDER: Final = "architecture"
MATRIX_COMMAND: Final = "atw-matrix"
MARKDOWN_SUFFIX: Final = ".md"
URL_MARK: Final = "://"
"""What a citation's source holds when it is a URL and no path."""
FINISH: Final = "Finish"
"""What the description of the last child step of an agent that started helpers begins with."""

LABEL_PRD: Final = "prd"
LABEL_CRITERIA: Final = "criteria"
LABEL_CONTEXT: Final = "context"
LABEL_STATE: Final = "state"
LABEL_FINDINGS: Final = "findings"
LABEL_RESULT: Final = "architecture result"
LABEL_SCOPE: Final = "review scope"
LABEL_TRD: Final = "trd"
LABEL_SPECIALISTS: Final = "specialists"
LABEL_QUESTION: Final = "question"
LABEL_REQUEST: Final = "request"
LABEL_ANSWER: Final = "answer"
LABEL_RULING: Final = "ruling"
LABEL_EPIC_BRIEF: Final = "epic brief"
"""The input labels the definitions of the architecture team name.

``request``, ``question``, ``answer`` and ``ruling`` are also the names of the artifacts that
record those files in the journal. ``epic brief`` is the file that holds what the matrix states
for the Epic itself (``matrixquery.epic_brief``): its requirements, its features with the arc42
headings that describe them, the entries that realize them with their stacks and repositories,
and the constraints that apply to those.
"""

WRITE_REQUEST: Final = "write request"
WRITTEN: Final = "what was written"
"""The artifacts a document maintainer's step holds: what it was asked to write, and its result."""

ARTIFACT_CONCLUSION: Final = "conclusion"
ARTIFACT_REVIEW: Final = "review"
ARTIFACT_CHECK: Final = "check result"
ARTIFACT_RESOLVED: Final = "every item is resolved"
ARTIFACT_TRD: Final = "TRD"

ROLE_ARCHITECT: Final = "solutions-architect"
ROLE_REVIEWER: Final = "architecture-reviewer"
ROLE_LEAD: Final = "architecture-lead"
ROLE_DECIDER: Final = "decider"
ROLE_SPECIALIST: Final = "design-specialist"
ROLE_DIAGRAMS: Final = "diagram-author"
ROLE_MAINTAINER: Final = "document-maintainer"
ROLE_TRD_AUTHOR: Final = "trd-author"
ROLE_STEWARD: Final = "repository-steward"
"""The roles agent definitions state in front matter; the flow names agents by role only."""

PLUGIN: Final[Path] = Path(__file__).resolve().parents[2]
HUMAN_ACTION_STAGE: Final = "requires-human-action"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def new_context(bead: str, prd: Path, arch: Path, work: Path, vault_commit: str) -> ArchitectureContext:
    """Name every path of one Epic's architecture work.

    Returns:
        The context the open-run step writes to its context file.

    """
    folder: Path = work / ARCHITECTURE_FOLDER
    return {
        "bead": bead,
        "prdPath": str(prd),
        "architectureRoot": str(arch),
        "vaultCommit": vault_commit,
        "matrixCommand": MATRIX_COMMAND,
        "statePath": str(folder / "state.json"),
        "resultPath": str(folder / "result.json"),
        "trdPath": str(work / "trd.md"),
        "helpersFolder": str(folder / "helpers"),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def context_path(work: Path) -> Path:
    """Name the context file the open-run step writes.

    Returns:
        The file inside the Epic's architecture work folder.

    """
    return work / ARCHITECTURE_FOLDER / "context.json"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_brief_path(work: Path) -> Path:
    """Name the file that holds the Epic's brief from the matrix.

    Returns:
        The file inside the Epic's architecture work folder.

    """
    return work / ARCHITECTURE_FOLDER / "epic-brief.json"


def matrix_file() -> Path:
    """Name the matrix file the run reads and changes.

    Returns:
        The file ``ATW_MATRIX`` names, or the one inside the control repository.

    """
    return matrix_path(None, os.environ)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def cited_document(arch: Path, source: str) -> EntryId | None:
    """Name the document entry a citation's source is.

    Args:
        arch: The architecture root.
        source: A citation's source: an arc42 path relative to the architecture root or absolute,
            or the id of a document entry; or anything else a citation may name.

    Returns:
        The id a document at that path has in the matrix; None when the source is not the path
        of a Markdown file under the architecture root. The matrix may hold no entry with the id.

    """
    prefix: str = f"{KIND_DOCUMENT}{ID_SEPARATOR}"
    stated: str = source.strip().removeprefix(prefix)
    if not stated.endswith(MARKDOWN_SUFFIX) or URL_MARK in stated:
        return None
    root: Path = arch.resolve()
    given: Path = Path(stated)
    located: Path = (given if given.is_absolute() else root / given).resolve()
    if not located.is_relative_to(root) or located == root:
        return None
    try:
        return make_id(KIND_DOCUMENT, located.relative_to(root).as_posix())
    except MatrixError:
        return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def document_path(document: str) -> str:
    """Name a document by its path under the architecture root.

    Args:
        document: The id of a document entry.

    Returns:
        What follows the kind and the colon in the id.

    """
    return document.partition(ID_SEPARATOR)[2]


class ArchitectureStepError(StepError):
    """A step of the architecture part was handed, or its agent wrote, something it cannot work with."""

    def __init__(self, run: StepRun, *evidence: str, stage: str | None = None) -> None:
        """Name the step in every line of the evidence."""
        super().__init__(
            stage or run.inputs.stage,
            OTHER_CAUSE,
            tuple(f"step {run.step['id']} ({run.step['description']}): {line}" for line in evidence),
        )


def checked_file[T](run: StepRun, path: Path, validate: Callable[[object], T]) -> T:
    """Read a JSON file a step was handed and validate it with its contract.

    Returns:
        The validated document.

    Raises:
        ArchitectureStepError: The file is missing, is not JSON or does not satisfy its contract.

    """
    try:
        return validate(strict_json(path))
    except (OSError, ValueError) as exc:
        raise ArchitectureStepError(run, f"{path}: {exc}") from None


def journal_file(run: StepRun, name: str) -> Path:
    """Find a file a step is handed, or that the open-run step of the journal recorded.

    A step an agent planned names its inputs itself; the files the open-run step recorded for
    every architecture step are then read from that step of the journal.

    Returns:
        The path of the file artifact named ``name``.

    Raises:
        ArchitectureStepError: Neither the step's inputs nor the open-run step hold it.

    """
    handed: Path | None = run.inputs.optional_file(name)
    if handed is not None:
        return handed
    step: Step
    held: Artifact
    for step in step_journal.steps_in_order(run.journal()):
        if step.get("script") != OPEN_RUN:
            continue
        for held in step["artifacts"]:
            if held["name"] == name and held["kind"] != "value":
                return Path(held["path"])
    raise ArchitectureStepError(run, f"neither its inputs nor the open-run step hold a file artifact named {name!r}")


def earlier_files(inputs: StepInputs) -> list[tuple[str, Path]]:
    """List the files an earlier form of the pipeline produced, among the artifacts a step is handed.

    Returns:
        Each file or directory artifact whose name begins with ``EARLIER_PREFIX``, with that name
        as its label, in the order handed.

    """
    return [(name, path) for name, path in inputs.labelled_files() if name.startswith(EARLIER_PREFIX)]


def read_context(run: StepRun) -> ArchitectureContext:
    """Read the context file a step is handed through the journal.

    A context file that is missing or does not satisfy its schema raises
    ``ArchitectureStepError``.

    Returns:
        The validated context.

    """
    return checked_file(run, journal_file(run, LABEL_CONTEXT), validate_architecture_context)


def read_result(run: StepRun, context: ArchitectureContext) -> ArchitectureResult:
    """Read the solutions architect's result.

    A result file that is missing or does not satisfy its schema raises ``ArchitectureStepError``.

    Returns:
        The validated result.

    """
    return checked_file(run, Path(context["resultPath"]), validate_architecture_result)


def output_check(validate: Callable[[object, str], object]) -> Callable[[Path], dict[str, JsonValue]]:
    """Turn a reader of the architecture work contract into a session's output check.

    Returns:
        A check that reads the output as strict JSON and validates it with the reader, whose
        ``ArchitectureWorkError`` sends the session to its one correction.

    """

    def check(path: Path) -> dict[str, JsonValue]:
        document: dict[str, JsonValue] = strict_json(path)
        validate(document, str(path))
        return document

    return check


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def agents_with_role(plugin: Path, role: str) -> tuple[str, ...]:
    """Name the agents of a plugin whose definition states one role.

    Returns:
        The agent names, sorted.

    Raises:
        ValueError: No definition of the plugin states the role.

    """
    found: list[str] = []
    path: Path
    for path in sorted((plugin / "agents").glob("*.md")):
        fields: dict[str, object]
        fields, _ = split_front_matter(path.read_text(encoding="utf-8"), f"agent {path.stem}")
        if fields.get("role") == role:
            found.append(path.stem)
    if not found:
        message: str = f"no agent definition under {plugin / 'agents'} has the role {role!r}"
        raise ValueError(message)
    return tuple(found)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def descriptions_with_role(plugin: Path, role: str) -> list[SpecialistEntry]:
    """List the agents that play one role with what each definition says the agent does.

    Returns:
        One entry per agent: its name and its description.

    """
    listed: list[SpecialistEntry] = []
    name: str
    for name in agents_with_role(plugin, role):
        fields: dict[str, object]
        fields, _ = split_front_matter((plugin / "agents" / f"{name}.md").read_text(encoding="utf-8"), f"agent {name}")
        listed.append({"agent": name, "description": str(fields.get("description") or "")})
    return listed


def is_finish(run: StepRun) -> bool:
    """Tell whether a step is the "Finish" step of the agent whose step contains it.

    Returns:
        True when the step's description begins with "Finish" and the step directly above it
        has the same agent.

    """
    parent: Step | None = step_journal.parent_step(run.journal(), run.step["id"])
    return (
        parent is not None
        and parent.get("agent") == run.step.get("agent")
        and run.step["description"].startswith(FINISH)
    )


def lead_resolved(run: StepRun, lead: str) -> bool | None:
    """Tell what the lead that ran before a step, in the same container, came to.

    Args:
        run: The step that asks.
        lead: The agent that plays the lead.

    Returns:
        None when no step of the lead comes before the step among its siblings; otherwise
        whether that step is done and it, or a step below it, records that every item is resolved.

    """
    step: Step | None = run.earlier_sibling(lead)
    if step is None:
        return None
    recorded: bool = any(
        held["name"] == ARTIFACT_RESOLVED and held["kind"] == "value" and held["value"] is True
        for below in step_journal.steps_in_order_from(step)
        for held in below["artifacts"]
    )
    return step["status"] == "done" and recorded


def planned_params(journal: Journal, step_id: StepId) -> Mapping[str, JsonValue]:
    """Read the parameters the step that planned a step handed it.

    Returns:
        The value of the artifact ``for <step id>`` wherever the journal holds it; an empty
        mapping when no step planned it with parameters.

    """
    name: str = step_journal.planned_for_name(step_id)
    step: Step
    held: Artifact
    for step in step_journal.steps_in_order(journal):
        for held in step["artifacts"]:
            if held["name"] == name and held["kind"] == "value" and isinstance(held["value"], dict):
                return held["value"]
    return {}


__all__ = [
    "CRITERIA_PATH",
    "ArchitectureContext",
    "ArchitectureResult",
    "ArchitectureWorkError",
]
