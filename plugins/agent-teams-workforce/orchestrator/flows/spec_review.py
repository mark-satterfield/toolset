"""The review of one repository's specification documents, each session a step of the journal.

One reviewer session reads the documents against the specs-and-Tasks criteria. Its step
plans what its result calls for: a finding goes once to the author of the document it names, in
the order the documents are written, each as its own step. A step that ends plans the next: the
next document with a finding, a document derived from one that changed, and, when an author
disputed a finding, the decider. A finding the decider upholds goes back to that author as a
directive, again one step per document. Nothing here decides whether a step runs again: the
journal does.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from review_criteria import LEVEL_IMPLEMENTATION, load_criteria
from spec_review_contract import (
    DOCUMENT_CRITERIA,
    DOCUMENT_DATA_MODEL,
    DOCUMENT_SPEC,
    RULING_FINDING_STANDS,
    SPEC_CORRECTION_SCHEMA_PATH,
    SPEC_REVIEW_SCHEMA_PATH,
    SPEC_RULING_SCHEMA_PATH,
    SpecDocument,
    validate_spec_correction,
    validate_spec_review,
    validate_spec_ruling,
)

from orchestrator.core.agents import strict_json
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.journal_registry import agent_step
from orchestrator.core.journal_steps import (
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import ARTIFACT_TRD
from orchestrator.flows.elaboration_files import (
    AUTHOR_CONTRACTS,
    AUTHOR_CRITERIA,
    AUTHOR_DATA_MODEL,
    CONTEXT,
    CRITERIA,
    DATA_MODEL,
    DECIDER,
    REVIEWER,
    SPEC,
    WARNINGS,
    WORK,
    Repository,
    objects,
    repository,
    strings,
)
from orchestrator.flows.elaboration_support import SPEC_AUTHORING_PHASE, enter_phase
from orchestrator.flows.spec_authoring import (
    WORK_DOCUMENT,
    WORK_UI,
    author_dirs,
    author_files,
    document_check,
    spec_document,
    ui_sources,
)

if TYPE_CHECKING:
    from spec_review_contract import SpecCorrection, SpecReview, SpecRuling
    from step_journal_contract import Artifact, Step, StepPlan

    from orchestrator.core.io import JsonValue

CRITERIA_FILE: Final = "skills/effective-architecture/review-criteria.json"

type Pass = Literal["correction", "revision"]
WORK_CORRECTION: Final[Pass] = "correction"
WORK_REVISION: Final[Pass] = "revision"
"""What a step of an author agent, planned by a step of the review, does."""
ORDER: Final[tuple[SpecDocument, ...]] = (DOCUMENT_SPEC, DOCUMENT_DATA_MODEL, DOCUMENT_CRITERIA)
"""The documents in the order they are written: a document follows every one it is derived from."""
DERIVED_FROM: Final[dict[SpecDocument, frozenset[SpecDocument]]] = {
    DOCUMENT_SPEC: frozenset(),
    DOCUMENT_DATA_MODEL: frozenset(),
    DOCUMENT_CRITERIA: frozenset({DOCUMENT_SPEC, DOCUMENT_DATA_MODEL}),
}
ARTIFACT_OF: Final[dict[SpecDocument, str]] = {
    DOCUMENT_SPEC: SPEC,
    DOCUMENT_DATA_MODEL: DATA_MODEL,
    DOCUMENT_CRITERIA: CRITERIA,
}
AUTHOR_OF: Final[dict[SpecDocument, str]] = {
    DOCUMENT_SPEC: AUTHOR_CONTRACTS,
    DOCUMENT_DATA_MODEL: AUTHOR_DATA_MODEL,
    DOCUMENT_CRITERIA: AUTHOR_CRITERIA,
}

REVIEW: Final = "spec review"
FINDINGS: Final = "spec review findings"
DROPPED: Final = "spec review findings dropped"
CORRECTION: Final = "spec correction"
REVISION: Final = "spec revision"
WORKED: Final = "spec review document worked on"
RULING: Final = "spec ruling"
UPHELD: Final = "spec review findings upheld"
"""The names of the artifacts the steps of the review record."""
DOCUMENT: Final = "document"

REVIEW_RESULT: Final = "Review of this repository's specification documents against the implementation criteria."
CORRECTION_RESULT: Final = "Correction of this specification document for the spec review findings."
RULING_RESULT: Final = "Ruling on each disputed spec review finding."
REVISION_RESULT: Final = "Revision of this specification document to the directives of the ruling."


def _kind(value: JsonValue) -> SpecDocument:
    """Narrow a recorded document kind.

    Returns:
        The kind.

    Raises:
        ValueError: The value is not a specification document kind.

    """
    kind: SpecDocument
    for kind in ORDER:
        if value == kind:
            return kind
    message: str = f"not a specification document kind: {value!r}"
    raise ValueError(message)


def _finding(identifier: str, kind: str) -> dict[str, JsonValue]:
    """Build the record of one finding the review sends to an author.

    Returns:
        The finding's id and the document it names.

    """
    return {"id": identifier, DOCUMENT: kind}


def _records(run: StepRun, own: dict[str, JsonValue] | None, phase: Pass) -> list[dict[str, JsonValue]]:
    """Read what the steps of one pass recorded: those the step is handed, then its own.

    Returns:
        One record per document an author worked on in the pass, in the order they ran.

    """
    earlier: list[dict[str, JsonValue]] = [held for held in objects(run.inputs.values(WORKED)) if held[WORK] == phase]
    return [*earlier, *([] if own is None else [own])]


def _findings(run: StepRun, phase: Pass) -> list[dict[str, JsonValue]]:
    """Read the findings one pass sends to the authors.

    Returns:
        The findings the review holds against an implementation criterion; in the revision
        pass, those of them the decider upheld.

    """
    kept: list[dict[str, JsonValue]] = objects(run.inputs.value(FINDINGS))
    if phase == WORK_CORRECTION:
        return kept
    upheld: list[str] = strings(run.inputs.optional_value(UPHELD, []))
    return [finding for finding in kept if finding["id"] in upheld]


def _plan(run: StepRun, held: Repository, work: str, agent: str, kind: SpecDocument | None) -> StepGroup:
    """Plan the next step of the review, after the step that ends.

    Returns:
        One step, handed everything the ending step was handed and what it records.

    """
    name: str = Path(held.path).name
    description: str = f"Rule on the disputed review findings of {name}"
    if kind is not None and work == WORK_CORRECTION:
        description = f"Correct the {kind} document of {name} for the review's findings"
    elif kind is not None:
        description = f"Revise the {kind} document of {name} to the ruling"
    plan: StepPlan = {
        "description": description,
        "purpose": "Every finding against the implementation criteria is settled",
        "agent": agent,
        "inputs": list(dict.fromkeys([*run.step.get("inputs", []), run.step["id"]])),
    }
    params: dict[str, JsonValue] = {WORK: work}
    if kind is not None:
        params[DOCUMENT] = kind
    return StepGroup((NewStep(plan, params),))


def following(run: StepRun, own: dict[str, JsonValue] | None, phase: Pass) -> tuple[StepGroup, ...]:
    """Plan what the result of a step of the review calls for.

    Args:
        run: The step that ends.
        own: What that step records about the document it worked on; None for the reviewer and
            the decider, which open a pass.
        phase: The pass the next author step belongs to.

    Returns:
        The step for the next document, in writing order, that has a finding of the pass or is
        derived from a document that changed in it; when the correction pass is over and an
        author disputed a finding, the decider's step; otherwise nothing.

    """
    held: Repository = repository(run.inputs)
    records: list[dict[str, JsonValue]] = _records(run, own, phase)
    findings: list[dict[str, JsonValue]] = _findings(run, phase)
    worked: list[SpecDocument] = [_kind(record[DOCUMENT]) for record in records]
    changed: set[SpecDocument] = {_kind(record[DOCUMENT]) for record in records if record["changed"] is True}
    start: int = 0 if not worked else ORDER.index(worked[-1]) + 1
    kind: SpecDocument
    for kind in ORDER[start:]:
        if any(finding[DOCUMENT] == kind for finding in findings) or changed & DERIVED_FROM[kind]:
            return (_plan(run, held, phase, AUTHOR_OF[kind], kind),)
    if phase == WORK_CORRECTION and any(strings(record["disputed"]) for record in records):
        return (_plan(run, held, "ruling", DECIDER, None),)
    return ()


def _documents(run: StepRun) -> tuple[tuple[str, Path], ...]:
    """Name the three spec documents a step of the review is handed.

    Returns:
        The contracts, the data model and the criteria, each with its artifact name.

    """
    return tuple((name, run.inputs.file(name)) for name in (SPEC, DATA_MODEL, CRITERIA))


@agent_step(REVIEWER)
def reviewer(run: StepRun) -> AgentLaunch:
    """Build the one reviewer session of a repository's specification documents.

    Returns:
        The launch: the review as output; when it is accepted, the findings held against an
        implementation criterion are recorded and the first author step they call for is planned.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, REVIEWER, held.path)
    criteria: Path = run.tools.plugin / CRITERIA_FILE

    def accept(accepted: StepRun, output: Path) -> Completion:
        review: SpecReview = validate_spec_review(strict_json(output), str(output))
        allowed: frozenset[str] = frozenset(
            entry.id for entry in load_criteria(criteria).at_level(LEVEL_IMPLEMENTATION)
        )
        kept: list[JsonValue] = [
            _finding(finding["id"], finding["document"])
            for finding in review["findings"]
            if finding["criterion"] in allowed
        ]
        dropped: list[JsonValue] = [
            finding["id"] for finding in review["findings"] if finding["criterion"] not in allowed
        ]
        recorded: StepRun = _with(accepted, value_artifact(FINDINGS, kept))
        return Completion(
            artifacts=(file_artifact(REVIEW, output), value_artifact(FINDINGS, kept), value_artifact(DROPPED, dropped)),
            add=following(recorded, None, WORK_CORRECTION),
        )

    return AgentLaunch(
        output=run.context.work / f"spec-{held.slug}.review.json",
        validate=SPEC_REVIEW_SCHEMA_PATH,
        outcome=REVIEW_RESULT,
        accept=accept,
        add_dirs=(run.context.work,),
        files=(
            *_documents(run),
            (ARTIFACT_TRD, run.inputs.file(ARTIFACT_TRD)),
            (CONTEXT, run.inputs.file(CONTEXT)),
        ),
        hand_inputs=False,
    )


def _with(run: StepRun, *recorded: Artifact) -> StepRun:
    """Hand a step, for planning, what it is about to record as well as what it was handed.

    Returns:
        The step with the artifacts it records added after its inputs.

    """
    return replace(run, inputs=replace(run.inputs, sources=(*run.inputs.sources, recorded)))


def _digest(path: Path) -> str:
    """Hash a document, to tell afterwards whether its author changed it.

    Returns:
        The SHA-256 of its bytes.

    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def correction(run: StepRun) -> AgentLaunch:
    """Build the session in which an author works on its document again, after the review or the ruling.

    The session continues the one in which the author wrote the document, when the journal holds it.

    Returns:
        The launch: the author's account of what it applied and disputed as output; when it is
        accepted the document is checked again, what the step did is recorded, and the next
        step of the review is planned.

    A document that no longer passes its own check after its author worked on it fails the step.

    """
    held: Repository = repository(run.inputs)
    params: dict[str, JsonValue] = dict(run.params())
    phase: Pass = WORK_REVISION if params.get(WORK) == WORK_REVISION else WORK_CORRECTION
    kind: SpecDocument = _kind(params.get(DOCUMENT))
    name: str = ARTIFACT_OF[kind]
    path: Path = run.inputs.file(name)
    before: str = _digest(path)
    stage: str = f"{kind}.{phase}"
    resumed: bool = "session" in run.step
    writing: Step | None = run.earlier_sibling(AUTHOR_OF[kind])
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, f"{kind}.{phase}", held.path)
    basis: list[tuple[str, Path]] = [(REVIEW, run.inputs.file(REVIEW))]
    if phase == WORK_REVISION:
        basis.append((RULING, run.inputs.file(RULING)))

    def accept(accepted: StepRun, output: Path) -> Completion:
        account: SpecCorrection = validate_spec_correction(strict_json(output), str(output))
        try:
            document_check(accepted, name)(path)
        except (OSError, ValueError) as exc:
            raise StepError(stage, OTHER_CAUSE, (str(path), str(exc))) from exc
        own: set[JsonValue] = {finding["id"] for finding in _findings(accepted, phase) if finding[DOCUMENT] == kind}
        disputed: list[JsonValue] = [d["findingId"] for d in account["disputes"] if d["findingId"] in own]
        foreign: list[JsonValue] = [
            f"{AUTHOR_OF[kind]} disputed {d['findingId']}, which is no finding on its document"
            for d in account["disputes"]
            if d["findingId"] not in own
        ]
        if phase == WORK_REVISION:
            foreign.extend(
                f"spec review finding {identifier} was disputed again after the ruling; the ruling stands"
                for identifier in disputed
            )
        record: dict[str, JsonValue] = {
            WORK: phase,
            DOCUMENT: kind,
            "changed": resumed or _digest(path) != before,
            "disputed": disputed,
        }
        return Completion(
            artifacts=(
                file_artifact(CORRECTION if phase == WORK_CORRECTION else REVISION, output),
                file_artifact(name, path),
                value_artifact(WORKED, record),
                value_artifact(WARNINGS, foreign),
            ),
            add=following(accepted, record, phase),
        )

    return AgentLaunch(
        output=run.context.work / f"spec-{held.slug}.{kind}.{phase}.json",
        validate=SPEC_CORRECTION_SCHEMA_PATH,
        outcome=CORRECTION_RESULT if phase == WORK_CORRECTION else REVISION_RESULT,
        accept=accept,
        add_dirs=author_dirs(run, held),
        files=tuple(dict.fromkeys((*author_files(run, name), (name, path), *basis))),
        resume_from=None if writing is None or "session" not in writing else writing["id"],
        hand_inputs=False,
    )


@agent_step(DECIDER)
def decider(run: StepRun) -> AgentLaunch:
    """Build the one decider session for every disputed finding of a repository.

    Returns:
        The launch: the ruling as output; when it is accepted the upheld findings are recorded
        and the first revision step they call for is planned.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, DECIDER, held.path)
    disputed: set[str] = {
        identifier for record in _records(run, None, WORK_CORRECTION) for identifier in strings(record["disputed"])
    }

    def accept(accepted: StepRun, output: Path) -> Completion:
        ruling: SpecRuling = validate_spec_ruling(strict_json(output), str(output))
        ruled: dict[str, str] = {
            entry["findingId"]: entry["ruling"] for entry in ruling["rulings"] if entry["findingId"] in disputed
        }
        upheld: list[JsonValue] = [*sorted(key for key, value in ruled.items() if value == RULING_FINDING_STANDS)]
        unruled: list[JsonValue] = [
            f"spec review finding {identifier} was disputed and not ruled on; its document stands"
            for identifier in sorted(disputed - set(ruled))
        ]
        recorded: StepRun = _with(accepted, value_artifact(UPHELD, upheld))
        return Completion(
            artifacts=(
                file_artifact(RULING, output),
                value_artifact(UPHELD, upheld),
                value_artifact(WARNINGS, unruled),
            ),
            add=following(recorded, None, WORK_REVISION),
        )

    return AgentLaunch(
        output=run.context.work / f"spec-{held.slug}.ruling.json",
        validate=SPEC_RULING_SCHEMA_PATH,
        outcome=RULING_RESULT,
        accept=accept,
        add_dirs=author_dirs(run, held),
        files=(
            (REVIEW, run.inputs.file(REVIEW)),
            *((CORRECTION, path) for path in dict.fromkeys(run.inputs.files(CORRECTION))),
            *_documents(run),
            (ARTIFACT_TRD, run.inputs.file(ARTIFACT_TRD)),
        ),
        hand_inputs=False,
    )


@agent_step(AUTHOR_CONTRACTS, AUTHOR_DATA_MODEL, AUTHOR_CRITERIA)
def author(run: StepRun) -> AgentLaunch:
    """Build the session of any step an author of a spec document performs.

    The parameters the planning step handed say which: choosing UI design sources, writing the
    document, correcting it after the review, or revising it after the ruling.

    Returns:
        The launch of that kind of step.

    Raises:
        StepError: The step was handed no kind of work this agent performs.

    """
    work: JsonValue = run.params().get(WORK)
    if work == WORK_UI:
        return ui_sources(run)
    if work == WORK_DOCUMENT:
        return spec_document(run)
    if work in {WORK_CORRECTION, WORK_REVISION}:
        return correction(run)
    evidence: str = f"step {run.step['id']} ({run.step['description']}) is handed no work for its agent: {work!r}"
    raise StepError(run.inputs.stage, OTHER_CAUSE, (evidence,))
