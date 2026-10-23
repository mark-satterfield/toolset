"""The review of one repository's specification documents, each session a step of the journal.

One reviewer session reads the documents against the specs-and-Tasks criteria; for a repository
whose stacks hold a DynamoDB store, a second reviewer session reads the data-model document's
DynamoDB access patterns first, and its findings join the review's. After the review at most
three rounds of sessions follow, each round's sessions running together:

1. One correction: every document with a finding goes once to its author, and the criteria go
   to theirs as well when a document they are derived from has a finding, all in one round.
2. The decider, when an author disputed a finding, rules on every disputed finding at once.
3. One revision: every document with an upheld finding goes back to its author with the
   ruling's directive, and the criteria with them when a document they are derived from does.

A script step after the correction round plans the decider when a finding was disputed; the
decider's step plans the revision round. Nothing here decides whether a step runs again: the
journal does.
"""

from __future__ import annotations

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
    SPEC_RULING_SCHEMA_PATH,
    SpecDocument,
    validate_spec_correction,
    validate_spec_review,
    validate_spec_ruling,
)

from orchestrator.core.agents import strict_json
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.journal_registry import agent_step, script_step
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
    DATA_MODEL_REVIEW,
    DATA_MODEL_REVIEWER,
    DECIDER,
    REVIEWER,
    SPEC,
    SPEC_PACK,
    SPEC_REVIEW_SETTLE,
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
    author_dirs,
    author_files,
    document_check,
    spec_document,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from spec_review_contract import Finding, SpecCorrection, SpecReview, SpecRuling
    from step_journal_contract import Artifact, Step, StepPlan

    from orchestrator.core.io import JsonValue
    from orchestrator.core.models import OutputValidator

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
DATA_MODEL_REVIEW_RESULT: Final = "Review of the DynamoDB access patterns of this repository's data-model document."
FINDING_PREFIX_REVIEW: Final = "F"
FINDING_PREFIX_DATA_MODEL: Final = "D"
"""The first letter of a finding id: the review's findings are F1, F2 and so on, the data-model review's D1, D2."""
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
        One record per document an author worked on in the pass.

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


def worked_on(findings: Sequence[Mapping[str, JsonValue]]) -> list[SpecDocument]:
    """Name the documents one round sends to their authors.

    Returns:
        In writing order, each document with a finding, and each document derived from one
        with a finding, so the criteria follow a change the findings direct in the contracts
        or the data model.

    """
    named: set[SpecDocument] = {_kind(finding[DOCUMENT]) for finding in findings}
    return [kind for kind in ORDER if kind in named or named & DERIVED_FROM[kind]]


def _round(run: StepRun, phase: Pass, findings: Sequence[Mapping[str, JsonValue]]) -> tuple[StepGroup, ...]:
    """Plan one round of author steps after the step that ends, all handed the same inputs.

    The author steps are consecutive agent steps with done inputs, so their sessions run
    together. After a correction round a script step plans the decider when an author disputed a
    finding (:func:`settle`).

    Args:
        run: The step that ends: the review, or the decider.
        phase: The pass of the round.
        findings: The findings the round sends to the authors.

    Returns:
        The round, or nothing when no document has a finding.

    """
    kinds: list[SpecDocument] = worked_on(findings)
    if not kinds:
        return ()
    name: str = Path(repository(run.inputs).path).name
    handed: list[str] = list(dict.fromkeys([*run.step.get("inputs", []), run.step["id"]]))
    steps: list[NewStep] = []
    kind: SpecDocument
    for kind in kinds:
        plan: StepPlan = {
            "ref": f"{phase}-{kind}",
            "description": (
                f"Correct the {kind} document of {name} for the review's findings"
                if phase == WORK_CORRECTION
                else f"Revise the {kind} document of {name} to the ruling"
            ),
            "purpose": "Every finding against the implementation criteria is settled",
            "agent": AUTHOR_OF[kind],
            "inputs": handed,
        }
        steps.append(NewStep(plan, {WORK: phase, DOCUMENT: kind}))
    if phase == WORK_CORRECTION:
        settling: StepPlan = {
            "ref": "settle",
            "description": f"Decide whether a finding on the documents of {name} is disputed",
            "purpose": "Every disputed finding goes to the decider",
            "script": SPEC_REVIEW_SETTLE,
            "inputs": [*handed, *(f"{phase}-{kind}" for kind in kinds)],
        }
        steps.append(NewStep(settling))
    return (StepGroup(tuple(steps)),)


@script_step(SPEC_REVIEW_SETTLE)
def settle(run: StepRun) -> Completion:
    """Plan the decider when an author disputed a finding in the correction round.

    Returns:
        Nothing recorded; the decider's step, handed everything this step was handed, when a
        record of the correction round names a disputed finding.

    """
    if not any(strings(record["disputed"]) for record in _records(run, None, WORK_CORRECTION)):
        return Completion()
    name: str = Path(repository(run.inputs).path).name
    plan: StepPlan = {
        "description": f"Rule on the disputed review findings of {name}",
        "purpose": "Every finding against the implementation criteria is settled",
        "agent": DECIDER,
        "inputs": list(dict.fromkeys([*run.step.get("inputs", []), run.step["id"]])),
    }
    return Completion(add=(StepGroup((NewStep(plan, {WORK: "ruling"}),)),))


def review_check(prefix: str, documents: frozenset[SpecDocument]) -> OutputValidator:
    """Give the check a review must pass: the review contract, with its finding ids and documents.

    Args:
        prefix: The first letter every finding id of this review carries.
        documents: The documents its findings may name.

    Returns:
        The check; a review that fails it raises ``ValueError`` and goes back to its session.

    """

    def check(path: Path) -> None:
        review: SpecReview = validate_spec_review(strict_json(path), str(path))
        wrong: list[str] = [
            finding["id"]
            for finding in review["findings"]
            if not finding["id"].startswith(prefix) or finding["document"] not in documents
        ]
        if wrong:
            named: str = ", ".join(sorted(documents))
            message: str = f"findings {', '.join(wrong)}: every id starts with {prefix} and names one of {named}"
            raise ValueError(message)

    return check


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
        data_model: Path | None = accepted.inputs.optional_file(DATA_MODEL_REVIEW)
        found: list[Finding] = [
            *review["findings"],
            *([] if data_model is None else validate_spec_review(strict_json(data_model), str(data_model))["findings"]),
        ]
        allowed: frozenset[str] = frozenset(
            entry.id for entry in load_criteria(criteria).at_level(LEVEL_IMPLEMENTATION)
        )
        kept: list[JsonValue] = [
            _finding(finding["id"], finding["document"]) for finding in found if finding["criterion"] in allowed
        ]
        dropped: list[JsonValue] = [finding["id"] for finding in found if finding["criterion"] not in allowed]
        return Completion(
            artifacts=(file_artifact(REVIEW, output), value_artifact(FINDINGS, kept), value_artifact(DROPPED, dropped)),
            add=_round(accepted, WORK_CORRECTION, objects(kept)),
        )

    return AgentLaunch(
        output=run.context.work / f"spec-{held.slug}.review.json",
        validate=review_check(FINDING_PREFIX_REVIEW, frozenset(ORDER)),
        outcome=REVIEW_RESULT,
        accept=accept,
        add_dirs=(run.context.work,),
        files=(
            *_documents(run),
            (ARTIFACT_TRD, run.inputs.file(ARTIFACT_TRD)),
            (CONTEXT, run.inputs.file(CONTEXT)),
            (SPEC_PACK, run.inputs.file(SPEC_PACK)),
        ),
        hand_inputs=False,
    )


@agent_step(DATA_MODEL_REVIEWER)
def data_model_reviewer(run: StepRun) -> AgentLaunch:
    """Build the session that reviews the DynamoDB access patterns of a repository's data model.

    It is planned only for a repository whose stacks hold a DynamoDB store, before the review,
    whose step adds these findings to its own.

    Returns:
        The launch: the data-model review as output, every finding on the data-model document.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, DATA_MODEL_REVIEWER, held.path)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(DATA_MODEL_REVIEW, output),))

    return AgentLaunch(
        output=run.context.work / f"spec-{held.slug}.data-model-review.json",
        validate=review_check(FINDING_PREFIX_DATA_MODEL, frozenset((DOCUMENT_DATA_MODEL,))),
        outcome=DATA_MODEL_REVIEW_RESULT,
        accept=accept,
        add_dirs=(run.context.work,),
        files=(
            (DATA_MODEL, run.inputs.file(DATA_MODEL)),
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


def _data_model_review(run: StepRun) -> tuple[tuple[str, Path], ...]:
    """Name the data-model review a step of the review is handed, when one was made.

    Returns:
        The data-model review with its artifact name, or nothing.

    """
    path: Path | None = run.inputs.optional_file(DATA_MODEL_REVIEW)
    return () if path is None else ((DATA_MODEL_REVIEW, path),)


def correction(run: StepRun) -> AgentLaunch:
    """Build the session in which an author works on its document again, after the review or the ruling.

    The session continues the one in which the author wrote the document, when the journal holds it.

    Returns:
        The launch: the author's account of what it applied and disputed as output; when it is
        accepted the document is checked again and what the step did is recorded.

    A document that no longer passes its own check after its author worked on it fails the step.

    """
    held: Repository = repository(run.inputs)
    params: dict[str, JsonValue] = dict(run.params())
    phase: Pass = WORK_REVISION if params.get(WORK) == WORK_REVISION else WORK_CORRECTION
    kind: SpecDocument = _kind(params.get(DOCUMENT))
    name: str = ARTIFACT_OF[kind]
    path: Path = run.inputs.file(name)
    stage: str = f"{kind}.{phase}"
    writing: Step | None = run.earlier_sibling(AUTHOR_OF[kind])
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, f"{kind}.{phase}", held.path)
    basis: list[tuple[str, Path]] = [(REVIEW, run.inputs.file(REVIEW)), *_data_model_review(run)]
    if phase == WORK_REVISION:
        basis.append((RULING, run.inputs.file(RULING)))

    def accept(accepted: StepRun, output: Path) -> Completion:
        account: SpecCorrection = validate_spec_correction(strict_json(output), str(output))
        try:
            document_check(accepted, name)(path)
        except (OSError, ValueError) as exc:
            raise StepError(stage, OTHER_CAUSE, (str(path), str(exc))) from None
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
        record: dict[str, JsonValue] = {WORK: phase, DOCUMENT: kind, "disputed": disputed}
        return Completion(
            artifacts=(
                file_artifact(CORRECTION if phase == WORK_CORRECTION else REVISION, output),
                file_artifact(name, path),
                value_artifact(WORKED, record),
                value_artifact(WARNINGS, foreign),
            ),
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
        and the revision round they call for is planned.

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
            add=_round(recorded, WORK_REVISION, _findings(recorded, WORK_REVISION)),
        )

    return AgentLaunch(
        output=run.context.work / f"spec-{held.slug}.ruling.json",
        validate=SPEC_RULING_SCHEMA_PATH,
        outcome=RULING_RESULT,
        accept=accept,
        add_dirs=author_dirs(run, held),
        files=(
            (REVIEW, run.inputs.file(REVIEW)),
            *_data_model_review(run),
            *((CORRECTION, path) for path in dict.fromkeys(run.inputs.files(CORRECTION))),
            *_documents(run),
            (ARTIFACT_TRD, run.inputs.file(ARTIFACT_TRD)),
        ),
        hand_inputs=False,
    )


@agent_step(AUTHOR_CONTRACTS, AUTHOR_DATA_MODEL, AUTHOR_CRITERIA)
def author(run: StepRun) -> AgentLaunch:
    """Build the session of any step an author of a spec document performs.

    The parameters the planning step handed say which: writing the document, correcting it after
    the review, or revising it after the ruling.

    Returns:
        The launch of that kind of step.

    Raises:
        StepError: The step was handed no kind of work this agent performs.

    """
    work: JsonValue = run.params().get(WORK)
    if work == WORK_DOCUMENT:
        return spec_document(run)
    if work in {WORK_CORRECTION, WORK_REVISION}:
        return correction(run)
    evidence: str = f"step {run.step['id']} ({run.step['description']}) is handed no work for its agent: {work!r}"
    raise StepError(run.inputs.stage, OTHER_CAUSE, (evidence,))
