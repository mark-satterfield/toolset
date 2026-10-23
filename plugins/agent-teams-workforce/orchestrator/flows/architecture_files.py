"""The files and names the steps of the Architecture container share.

The open-run step writes one context file and records it in the journal. It names every path the
script chose for the architecture work of the Epic: the architect's state and result files and
the TRD. Every later step is handed that file through the journal, so no step derives a path of
its own.

A session reads the PRD it is handed, and the existing architecture in the arc42 documents and the
matrix, which are its starting point and not a complete record: the session runs the
``atw-matrix`` reads its definition names, or a script step writes the result of a matrix read to
a file and the brief names that file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import (
    ArchitectureContext,
    ArchitectureResult,
    ArchitectureWorkError,
    validate_architecture_context,
    validate_architecture_result,
    validate_write_request,
    validate_write_result,
)
from matrix_contract import KIND_DOCUMENT, EntryId, MatrixError
from matrixstore import ID_SEPARATOR, make_id, matrix_path
from matrixsync import program_output, vault_root
from step_journal_contract import STATUS_DONE

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import json_object, write_json
from orchestrator.core.journal_steps import is_finish_of
from orchestrator.core.models import PipelineDefectError, StepError

if TYPE_CHECKING:
    from collections.abc import Callable

    from architecture_work_contract import SourceHeading, WriteRequest, WriteResult
    from step_journal_contract import Artifact, Journal, Step

    from orchestrator.core.io import JsonValue
    from orchestrator.core.journal_steps import StepRun

OPEN_RUN: Final = "prd_to_spec.open_run"
PACK: Final = "architecture.pack"
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
PACK_FILE: Final = "pack.json"
PACK_TEXT_FILE: Final = "pack.md"
"""The Epic's architecture pack, and the same pack written for reading, beside the context file."""
CHANGE_FILE: Final = "matrix-changes.json"
"""The architect's matrix change file, beside the context file (``matrix-change.schema.json``)."""
REVIEWED_FILE: Final = "reviewed.json"
"""What the Epic's architect reviewed, as it stood when its result was last accepted: each entry of the
approval scope with its content hash and approved owner, and each heading of each document its
maintainers wrote with the hash of its text (``architecture_collision``)."""
MATRIX_COMMAND: Final = "atw-matrix"
MARKDOWN_SUFFIX: Final = ".md"
URL_MARK: Final = "://"
"""What a citation's source holds when it is a URL and no path."""
LABEL_PRD: Final = "prd"
LABEL_CONTEXT: Final = "context"
LABEL_STATE: Final = "state"
LABEL_FINDINGS: Final = "findings"
LABEL_RESULT: Final = "architecture result"
LABEL_SCOPE: Final = "review scope"
LABEL_TRD: Final = "trd"
LABEL_QUESTION: Final = "question"
LABEL_REQUEST: Final = "request"
LABEL_ANSWER: Final = "answer"
LABEL_RULING: Final = "ruling"
"""The input labels the definitions of the architecture team name.

``request``, ``question``, ``answer`` and ``ruling`` are also the names of the artifacts that
record those files in the journal, as ``helper-steps.schema.json`` fixes them.
"""

WRITE_REQUEST: Final = "write request"
WRITTEN: Final = "what was written"
"""The artifacts a document maintainer's step holds: what it was asked to write, and its result."""

ARTIFACT_PACK: Final = "architecture pack"
ARTIFACT_PACK_TEXT: Final = "architecture pack for reading"
ARTIFACT_CONCLUSION: Final = "conclusion"
ARTIFACT_CHECK: Final = "check result"
ARTIFACT_RESOLVED: Final = "every item is resolved"
ARTIFACT_TRD: Final = "TRD"
ARTIFACT_SPECIALIST_RECOMMENDATIONS: Final = "specialist recommendations"
"""The solutions architect's recommendations to the owner to create or update a specialist agent."""

ARCHITECT: Final = "aws-solutions-architect"
LEAD: Final = "architecture-team-lead"
DECIDER: Final = "architecture-decider"
TRD_AUTHOR: Final = "trd-author"
MAINTAINER: Final = "architecture-maintainer"
"""The agents of the architecture team's fixed steps, by name. The agents the architect or the lead
chooses for a subject are named in their own files (``architecture-result.schema.json``
``requests``; ``lead-routing.schema.json``), never here."""
PARAM_REQUEST: Final = "request"
"""The parameter that hands a planned helper step the path of its request file."""
REVIEW_LOG_FILE: Final = "review-log.json"
"""The name of the Epic's review log, beside the architect's result (``log-architecture-review``)."""

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
        "reviewLogPath": str(folder / REVIEW_LOG_FILE),
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
def architecture_folder(work: Path) -> Path:
    """Name the Epic's architecture work folder: the folder of the context file.

    Returns:
        The folder inside the run's work folder that holds the context file, the pack, the
        architect's state, result, review log and change file, and the helpers folder.

    """
    return work / ARCHITECTURE_FOLDER


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

    Only the file's own faults are the item's: a file that is missing or is not JSON, and a
    document the contract refuses (``ArchitectureWorkError``). A contract whose schema cannot be
    loaded or applied is pipeline code that failed.

    Returns:
        The validated document.

    Raises:
        ArchitectureStepError: The file is missing, is not JSON or does not satisfy its contract.
        PipelineDefectError: The contract's schema could not be loaded or applied.

    """
    try:
        document: dict[str, JsonValue] = strict_json(path)
    except (OSError, ValueError) as exc:
        raise ArchitectureStepError(run, f"{path}: {exc}") from None
    try:
        return validate(document)
    except ArchitectureWorkError as exc:
        raise ArchitectureStepError(run, f"{path}: {exc}") from None
    except Exception as exc:
        raise PipelineDefectError(run.inputs.stage, exc, (str(path),)) from exc


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


def read_context(run: StepRun) -> ArchitectureContext:
    """Read the context file a step is handed through the journal.

    The open-run step is the only writer of the context file. A context file that is missing or is
    not JSON raises ``ArchitectureStepError``. One that does not satisfy the context contract was
    written to an earlier contract: it is written again in place to the current one
    (:func:`_rewritten_context`), and no step is set back to planned.

    Returns:
        The validated context.

    Raises:
        PipelineDefectError: The context written again does not satisfy the context contract.

    """
    path: Path = journal_file(run, LABEL_CONTEXT)
    held: object = checked_file(run, path, lambda value: value)
    try:
        return validate_architecture_context(held)
    except ArchitectureWorkError:
        context: ArchitectureContext = _rewritten_context(run, held)
    try:
        validate_architecture_context(context)
    except ArchitectureWorkError as exc:
        raise PipelineDefectError(run.inputs.stage, exc, (str(path),)) from exc
    write_json(path, context)
    return context


def _rewritten_context(run: StepRun, held: object) -> ArchitectureContext:
    """Write the context of the run again to the current contract, as the open-run step writes it.

    The PRD and the architecture root are the ones the dispatch names, as the open-run step reads
    them; the vault commit is the one the stale file recorded, else the vault's present commit.

    Returns:
        The context (:func:`new_context`).

    """
    dispatch: DispatchArguments = dispatch_arguments()
    args: dict[str, JsonValue] = run.context.args
    prd: Path = Path(check_type(json_object(args[dispatch.KEY_PRD])[dispatch.PRD_PATH], str)).resolve()
    arch: Path = Path(check_type(args[dispatch.KEY_ARCH_PATH], str)).resolve()
    recorded: object = held.get("vaultCommit") if isinstance(held, dict) else None
    commit: str = (
        recorded
        if isinstance(recorded, str) and recorded
        else program_output("git", ["rev-parse", "HEAD"], vault_root(arch)).strip()
    )
    return new_context(run.bead, prd, arch, run.context.work, commit)


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


def written_paths(arch: Path, request: WriteRequest, written: WriteResult) -> list[str]:
    """Name the arc42 documents one write request and its result touch.

    Returns:
        The path under the architecture root of each document the result says was changed or
        created, and of each home the request names, once, in path order.

    """
    cited: list[SourceHeading] = [
        *written["headingsChanged"],
        *written["headingsCreated"],
        *written["linksAdded"],
        *written["restatementsRemoved"],
        *(fact["home"] for fact in request["facts"]),
        *(diagram["home"] for diagram in request["diagrams"]),
        *(
            place
            for settlement in request["settlements"]
            for place in (settlement["stands"], *settlement["corrections"])
        ),
    ]
    documents: set[EntryId] = {
        document for citation in cited for document in (cited_document(arch, citation["source"]),) if document
    }
    return sorted(document_path(document) for document in documents)


def held_file(step: Step, *names: str) -> Path | None:
    """Find a file a step holds under one of some artifact names.

    Returns:
        The path of the first file artifact with one of the names, in the order the names are
        given; None when the step holds none.

    """
    name: str
    for name in names:
        held: Artifact
        for held in step["artifacts"]:
            if held["name"] == name and held["kind"] != "value":
                return Path(held["path"])
    return None


def written_documents(run: StepRun, arch: Path) -> list[str]:
    """List the documents this Epic's document maintainers wrote.

    Every done step under the Epic's Architecture container that holds what a document
    maintainer wrote and the write request it was launched from counts: a maintainer the script
    ran and one the architect ran in its own session alike. The documents are those
    :func:`written_paths` names for each.

    Returns:
        The path under the architecture root of each document written, once, in path order. A
        write request or a result a done step holds that cannot be read raises
        ``ArchitectureStepError`` from :func:`checked_file`.

    """
    container: Step = run.step_named(ARCHITECTURE)
    paths: set[str] = set()
    step: Step
    for step in step_journal.steps_in_order_from(container):
        written: Path | None = held_file(step, WRITTEN)
        asked: Path | None = held_file(step, WRITE_REQUEST, LABEL_REQUEST)
        if step["status"] != STATUS_DONE or written is None or asked is None:
            continue
        request: WriteRequest = checked_file(run, asked, validate_write_request)
        result: WriteResult = checked_file(run, written, validate_write_result)
        paths.update(written_paths(arch, request, result))
    return sorted(paths)


def is_finish(run: StepRun) -> bool:
    """Tell whether a step is the "Finish" step of the agent whose step contains it.

    Returns:
        True when the step's description begins with "Finish" and the step directly above it
        has the same agent.

    """
    parent: Step | None = step_journal.parent_step(run.journal(), run.step["id"])
    return parent is not None and is_finish_of(parent, run.step)


MAX_FINISH_GENERATIONS: Final = 3
"""How many "Finish" steps one agent step may run, each below the one before."""


def finish_generation(run: StepRun) -> int:
    """Count the "Finish" generations a step stands in.

    A "Finish" whose result plans more work is followed by another "Finish" below it; the
    generation is how many of them are chained through the step: each step above it that is the
    "Finish" of the step above that, the step itself when it is one, and each done "Finish" its
    last child step is, below it in turn (a "Finish" the agent closed in its own session is
    accepted on the step above it).

    Returns:
        The number of "Finish" steps in that chain; 0 for an agent step that is not one and holds none.

    """
    journal: Journal = run.journal()
    count: int = 0
    step: Step = run.step
    parent: Step | None = step_journal.parent_step(journal, step["id"])
    while parent is not None and is_finish_of(parent, step):
        count += 1
        step = parent
        parent = step_journal.parent_step(journal, step["id"])
    step = run.step
    while step["steps"] and is_finish_of(step, step["steps"][-1]) and step["steps"][-1]["status"] == STATUS_DONE:
        count += 1
        step = step["steps"][-1]
    return count


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


__all__ = [
    "ArchitectureContext",
    "ArchitectureResult",
    "ArchitectureWorkError",
]
