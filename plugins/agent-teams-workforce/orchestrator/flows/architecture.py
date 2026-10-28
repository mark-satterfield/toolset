"""The solutions architect's steps, and the sessions of the agents the script starts for it.

One agent, the solutions architect, decides what the architecture should be for a PRD. It starts
no agent: every step it performs is a fresh session that writes one file, and the script runs
everything between them (``architecture_rounds``).

1. Analyze: handed the PRD, the TRD the script step ``trd.seed`` wrote (``trd_steps``) and the
   context, it reads the Epic's architecture pack (``architecture_pack``) and writes its state
   file and one round of requests, one per specialist (``questions.json``).
2. The script starts each specialist with its request, each as its own session.
3. Decide: a fresh session handed the answers and their digest writes the architecture result,
   its decisions, and its matrix changes to one change file that the step accepting its result
   applies in one locked update. A result that asks a second round gets one more round and one
   more Decide; a Decide of the second round that still asks fails.
4. The script writes one request per group of arc42 sections from the result, at most three, and
   starts one ``architecture-maintainer`` per group; the step that accepts each write records
   ``describedBy`` and ``covers`` for the headings written.

A correction after the mechanical check, and a competing design the lead orders, are fresh
sessions too, continuing from the result file. The architect always reads the PRD it is handed;
the arc42 documents and the matrix are its starting point, both input and output, possibly
incomplete or wrong and possibly empty for the Epic. It decides the stack and repository of each
element after its detailed design and records that placement itself; the ``span`` step names and
creates each repository that placement needs. What the architect reads and whom it asks are its
own decisions.

The step that accepts a result file records in the matrix what that file states, and is done only
when the matrix shows it.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "find-specialists" / "scripts"))
from architecture_work_contract import (
    ArchitectureWorkError,
    validate_architecture_result,
    validate_architecture_state,
    validate_specialist_answer,
    validate_specialist_request,
    validate_specialist_round,
    validate_trd_answer,
    validate_trd_request,
    validate_write_request,
    validate_write_result,
)
from matrix_contract import (
    KIND_CONSTRAINT,
    REL_APPLIES_TO,
    REL_COVERS,
    REL_DESCRIBED_BY,
    REL_HAS_REQUIREMENT,
    REL_REALIZED_BY,
    REL_SERVED_BY,
    REL_STATED_IN,
    REL_SUPPORTED_BY,
    ROLE_SOLUTIONS_ARCHITECT,
    SIDE_ARCHITECTURE,
    MatrixError,
)
from matrixquery import epic_view
from matrixstore import as_entry_id, make_id, name_key, read_matrix, slug, update_matrix
from matrixsync import LIFECYCLE_IN_REVIEW, relative_path, set_lifecycle, sync_documents, vault_root
from matrixtraverse import epic_id
from matrixwrite import apply_change_file, apply_changes, link, put
from specialist_catalog import agent_names

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.journal_registry import agent_step, any_agent_step, plan_under
from orchestrator.core.journal_steps import (
    UNDER_CONTAINER,
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import MalformedRequestError, StaleInputError
from orchestrator.flows.architecture_check import check_step, review_log_findings
from orchestrator.flows.architecture_diagrams import syntax_problems
from orchestrator.flows.architecture_files import (
    ARCHITECT,
    ARCHITECTURE,
    ARTIFACT_CHECK,
    ARTIFACT_CONCLUSION,
    ARTIFACT_PACK,
    ARTIFACT_SPECIALIST_RECOMMENDATIONS,
    ARTIFACT_TRD,
    ARTIFACT_TRD_ANSWER,
    CHANGE_FILE,
    EXAMPLE_RESULT,
    EXAMPLE_ROUND,
    EXAMPLE_STATE,
    LABEL_ANSWER,
    LABEL_CONTEXT,
    LABEL_DIGEST,
    LABEL_EXAMPLE,
    LABEL_FINDINGS,
    LABEL_PRD,
    LABEL_QUESTION,
    LABEL_REQUEST,
    LABEL_RESULT,
    LABEL_ROUND,
    LABEL_RULING,
    LABEL_STATE,
    LABEL_TRD,
    MAINTAINER,
    PARAM_REQUEST,
    QUESTIONS_FILE,
    SCRIPT_STARTED,
    TRD_AUTHOR,
    WRITE_REQUEST,
    WRITTEN,
    ArchitectureContext,
    ArchitectureStepError,
    architecture_folder,
    checked_file,
    cited_document,
    journal_file,
    matrix_file,
    output_check,
    read_context,
    written_paths,
)
from orchestrator.flows.architecture_index import index_step
from orchestrator.flows.architecture_pack import PACK_REF, pack_file, pack_plan
from orchestrator.flows.architecture_rounds import (
    ID_LENGTH,
    MAX_ROUNDS,
    answered,
    handed_answers,
    round_of,
    round_steps,
    write_digest,
    write_steps,
)
from orchestrator.flows.repo_scoping import (
    FIELD_ADDED_OR_CHANGED,
    FIELD_UNCHANGED_WORK,
    story_build_entries,
    story_build_problems,
)
from orchestrator.flows.trd_authoring import (
    TRD_FRONT_MATTER,
    DocumentValidationError,
    document,
    unresolved_requirements,
)
from orchestrator.flows.trd_steps import SEED_REF, WRITE_DESCRIPTION, seed_plan, write_request

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from architecture_work_contract import (
        AgentRequest,
        ArchitectureResult,
        SourceHeading,
        SpecialistRecommendation,
        SpecialistRequest,
        SpecialistRound,
        TrdAnswer,
        TrdRequest,
        TrdRequirement,
        WriteRequest,
        WriteResult,
    )
    from matrix_contract import EntryId, RelationshipKind
    from matrixquery import EpicView
    from matrixstore import Matrix
    from matrixsync import DocumentsSynced
    from matrixwrite import ApplyResult
    from step_journal_contract import Step, StepId, StepPlan

    from orchestrator.core.io import JsonValue

ANALYZE_DESCRIPTION: Final = (
    "Analyze the PRD against the architecture and put the questions and draft reviews to the specialists"
)
ARCHITECT_PURPOSE: Final = "One agent is responsible for the architecture this PRD needs, and reviews and approves it"
ARCHITECT_REF: Final = "architect"
NO_SOURCE: Final = "obligations with no source"
NO_FEATURE: Final = "requirements with no feature"
SYNCED: Final = "documents synced"
CONSTRAINTS: Final = "constraints recorded"
ATTR_HEADING: Final = "heading"
ATTR_VIA: Final = "via"
ATTR_STATEMENT: Final = "statement"
ATTR_TRD: Final = "trd"
ATTR_EPIC: Final = "epic"
ATTR_REQUIREMENT: Final = "requirement"
REQUIREMENT_KEY_SEPARATOR: Final = "/"
HEADING_MARK: Final = "#"
ERRORS_SUFFIX: Final = ".errors.txt"
"""What the file of a request's validation errors adds to the request file's stem."""
_NOTHING_WRITTEN: Final[WriteResult] = {
    "headingsChanged": [],
    "headingsCreated": [],
    "linksAdded": [],
    "restatementsRemoved": [],
    "notApplied": [],
    "summary": "-",
}
"""A result that names no document, for an invalid result: only the request's own homes are rendered."""
CATALOG_AGENTS: Final[frozenset[str]] = agent_names()
"""Every agent the find-specialists skill's catalog lists: the names a request may give."""


@dataclass(frozen=True)
class Recorded:
    """What one accept step recorded in the matrix from a result file, and what it could not."""

    entries: tuple[EntryId, ...] = ()
    """The entries the step put, in the order recorded."""
    served: tuple[tuple[EntryId, EntryId], ...] = ()
    """Each requirement with a feature the result file says serves it."""
    problems: tuple[str, ...] = ()
    """One sentence for each thing the result file states that the matrix does not hold."""
    no_feature: tuple[EntryId, ...] = ()
    """The Epic's requirements no feature serves, as the matrix shows them afterwards."""
    listed: tuple[EntryId, ...] = ()
    """The requirements the result file lists as having no feature."""


def _architect_plan(architect: str, inputs: list[str]) -> StepPlan:
    """Plan the architect's first step, Analyze.

    Returns:
        The plan, handed the steps ``inputs`` names.

    """
    return {
        "ref": ARCHITECT_REF,
        "description": ANALYZE_DESCRIPTION,
        "purpose": ARCHITECT_PURPOSE,
        "agent": architect,
        "inputs": inputs,
    }


def first_steps(opened: StepId, container: StepId, architect: str) -> StepGroup:
    """Plan the pack, the TRD seed, the architect's Analyze step, the index and the check under the container.

    The pack comes first (``architecture_pack``): the seed and the architect read the Epic's reach
    from it, and the architect the headings that describe it and its constraints. The TRD seed
    (``trd_steps``) comes next, so the architect starts from the TRD and is handed it. The steps
    the Analyze step's output plans (the specialists, Decide, the document writes) go after it,
    before the index and the check (``architecture_rounds``). The open-run
    step plans the group, and records each step it plans on itself, so a start at or before the
    open-run step removes the group and the open-run step plans it again as the lane plans it
    then. The same plans are registered as what this lane plans under the container
    (``journal_registry.plan_under``), so a planned step whose key was renamed is replanned to the
    current key when the run opens the journal (``journal_run.replan_unhandled``).

    Args:
        opened: The open-run step, whose artifacts the planned steps are handed.
        container: The Architecture container.
        architect: The agent that plays the solutions architect.

    Returns:
        The pack, the TRD seed, the architect's Analyze step, and the index and the check that
        follow it, as the container's last child steps.

    """
    return StepGroup(
        (
            NewStep(pack_plan([opened])),
            NewStep(seed_plan([opened, PACK_REF])),
            NewStep(_architect_plan(architect, [opened, SEED_REF])),
            index_step([ARCHITECT_REF]),
            check_step([ARCHITECT_REF], corrections=0),
        ),
        UNDER_CONTAINER,
        container,
    )


plan_under(
    ARCHITECTURE,
    pack_plan([]),
    seed_plan([]),
    _architect_plan(ARCHITECT, []),
    index_step([ARCHITECT_REF]).plan,
    check_step([ARCHITECT_REF], corrections=0).plan,
)


def _handed_files(
    run: StepRun,
    context: ArchitectureContext,
    prd: Path,
    *examples: Path,
) -> tuple[tuple[str, Path], ...]:
    """Name the files of the architect's brief: exactly the labels its definition states.

    No file is written from the matrix for the architect: it runs the ``atw-matrix`` reads its
    definition names for the Epic, so what it reads is the matrix as it is at that moment.

    Returns:
        The PRD, the TRD, the context file and the state path; then each mechanical check
        result the step is handed, as findings; then the digest of the answers the step is handed
        (a specialist's), each answer and each ruling; then the example of each file the step writes.

    """
    findings: list[Path] = list(run.inputs.files(ARTIFACT_CHECK))
    digest: Path | None = write_digest(run, Path(context["helpersFolder"]))
    return (
        (LABEL_PRD, prd),
        (LABEL_TRD, Path(context["trdPath"])),
        (LABEL_CONTEXT, journal_file(run, LABEL_CONTEXT)),
        (LABEL_STATE, Path(context["statePath"])),
        *((LABEL_FINDINGS, path) for path in dict.fromkeys(findings)),
        *(() if digest is None else ((LABEL_DIGEST, digest),)),
        *((LABEL_ANSWER, path) for path in handed_answers(run)),
        *((LABEL_RULING, path) for path in dict.fromkeys(run.inputs.files(LABEL_RULING))),
        *((LABEL_EXAMPLE, example) for example in examples),
    )


def _held(matrix: Matrix, stated: str, what: str, problems: list[str]) -> EntryId | None:
    """Find the entry a result file names by its id.

    Returns:
        The id; None, with one sentence added to ``problems``, when the text is not an entry id
        or the matrix holds no entry with it.

    """
    try:
        named: EntryId = as_entry_id(stated.strip())
    except MatrixError as error:
        problems.append(f"{what}: {error}")
        return None
    if matrix.find(named) is None:
        problems.append(f"{what}: the matrix holds no entry {named}; it is recorded with atw-matrix put")
        return None
    return named


def _link(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - The parts of one relationship.
    matrix: Matrix,
    kind: RelationshipKind,
    start: EntryId,
    end: EntryId,
    problems: list[str],
    attributes: Mapping[str, JsonValue] | None = None,
) -> None:
    """Record one relationship on the architecture side; a refusal becomes one sentence in ``problems``."""
    try:
        link(matrix, kind, start, end, SIDE_ARCHITECTURE, attributes)
    except MatrixError as error:
        problems.append(f"{kind} from {start} to {end}: {error}")


def _link_named(
    matrix: Matrix,
    kind: RelationshipKind,
    start: EntryId,
    names: Sequence[str],
    problems: list[str],
) -> None:
    """Record one relationship from an entry to each entry a result file names by its id."""
    name: str
    for name in names:
        target: EntryId | None = _held(matrix, name, f"{kind} of {start}", problems)
        if target is not None:
            _link(matrix, kind, start, target, problems)


def _requirements(matrix: Matrix, epic: EntryId) -> dict[str, EntryId]:
    """Index an Epic's requirements by every name a result file may give one.

    Returns:
        Each requirement's id under its id, its heading text and the key that ends its id, each
        in the form names are compared in.

    """
    index: dict[str, EntryId] = {}
    for stated in matrix.outgoing(epic, (REL_HAS_REQUIREMENT,)):
        entry = matrix.entry(stated.end)
        for name in (entry.id, entry.name, entry.id.rpartition(REQUIREMENT_KEY_SEPARATOR)[2]):
            index.setdefault(name_key(name), entry.id)
    return index


def _record_design(matrix: Matrix, bead: str, result: ArchitectureResult) -> Recorded:
    """Record what an architecture result states about the Epic's features.

    For each feature: ``servedBy`` from each requirement it serves, ``realizedBy`` to each entry
    that realizes it and ``supportedBy`` to each supporting feature; then ``covers`` from each
    document heading that describes the feature to each requirement it serves, with the feature
    as ``via``. The entries themselves are the architect's to record. A requirement the result
    lists as having no feature is found in the matrix and nothing is recorded for it.

    Returns:
        The requirement and feature pairs the result states, the requirements it lists as having
        no feature, and what could not be recorded.

    """
    requirements: dict[str, EntryId] = _requirements(matrix, epic_id(bead))
    problems: list[str] = []
    served: list[tuple[EntryId, EntryId]] = []
    listed: list[EntryId] = []
    for unserved in result["noFeature"]:
        without: EntryId | None = requirements.get(name_key(unserved["requirement"].lstrip(HEADING_MARK)))
        if without is None:
            problems.append(
                f"noFeature names {unserved['requirement']!r}, which is not a requirement of {bead} in the matrix",
            )
            continue
        listed.append(without)
    for stated in result["features"]:
        feature: EntryId | None = _held(matrix, stated["id"], f"feature {stated['name']!r}", problems)
        if feature is None:
            continue
        for heading in stated["prdRequirements"]:
            requirement: EntryId | None = requirements.get(name_key(heading.lstrip(HEADING_MARK)))
            if requirement is None:
                problems.append(f"{feature} names {heading!r}, which is not a requirement of {bead} in the matrix")
                continue
            _link(matrix, REL_SERVED_BY, requirement, feature, problems)
            served.append((requirement, feature))
        _link_named(matrix, REL_REALIZED_BY, feature, stated["elements"], problems)
        _link_named(matrix, REL_SUPPORTED_BY, feature, stated["sharedCapabilities"], problems)
    for requirement, feature in served:
        for describing in matrix.outgoing(feature, (REL_DESCRIBED_BY,)):
            heading_text: JsonValue = describing.attributes.get(ATTR_HEADING)
            if isinstance(heading_text, str) and heading_text:
                attributes: dict[str, JsonValue] = {ATTR_HEADING: heading_text, ATTR_VIA: feature}
                _link(matrix, REL_COVERS, describing.end, requirement, problems, attributes)
    return Recorded(
        served=tuple(dict.fromkeys(served)),
        problems=tuple(problems),
        listed=tuple(dict.fromkeys(listed)),
    )


def _record_result(bead: str, result: ArchitectureResult, changes: Path) -> Recorded:
    """Apply the architect's change file, record its result in the matrix, and compare with ``epic``.

    The change file (``matrix-changes.json``) is applied first, whole or not at all, in one locked
    update (``matrixwrite.apply_change_file``), so the result's links are recorded on the entries
    it puts. A change file that fails is reported operation by operation, and the result is not
    recorded. Applying a file again is harmless: each operation leaves the matrix as it found it
    when it already holds the fact.

    Returns:
        :func:`_compared` on the matrix as the write left it; or only the problems, one per
        operation of the change file that failed.

    """
    if changes.is_file():
        applied: ApplyResult = apply_change_file(matrix_file(), changes, ROLE_SOLUTIONS_ARCHITECT)
        if applied["failures"]:
            return Recorded(
                problems=tuple(
                    f"{changes} operation {'(file)' if failure['index'] is None else failure['index']} "
                    f"({failure['op'] or 'no op'}): {failure['error']}"
                    for failure in applied["failures"]
                ),
            )

    def change(matrix: Matrix) -> Recorded:
        return _record_design(matrix, bead, result)

    recorded: Recorded = update_matrix(matrix_file(), change)
    return _compared(read_matrix(matrix_file()), bead, recorded)


def _change_problems(matrix: Matrix, changes: Path) -> list[str]:
    """Apply the architect's change file to a matrix that is never written, and report what fails.

    Returns:
        One sentence per operation that fails, with its index; none when there is no change file.

    """
    if not changes.is_file():
        return []
    applied: ApplyResult = apply_changes(matrix, changes, ROLE_SOLUTIONS_ARCHITECT)
    return [
        f"{changes} operation {'(file)' if failure['index'] is None else failure['index']} "
        f"({failure['op'] or 'no op'}): {failure['error']}"
        for failure in applied["failures"]
    ]


def _result_problems(matrix: Matrix, bead: str, result: ArchitectureResult, changes: Path) -> list[str]:
    """Find what the matrix could not hold of an architecture result and its change file.

    The architect's change file (``matrix-changes.json``) is applied first to ``matrix``, a copy
    of the matrix that is never written; each operation that fails is a problem, with its index. What the
    Epic's Stories build is then checked against that copy
    (``repo_scoping.story_build_problems``): the result's ``addedOrChangedElements`` and its
    ``unchangedWorkElements``, each list on its own; at least one of them must name something, and
    no element may be named in both. Then the design is recorded in an in-memory copy of the matrix, which is
    never written, and compared with what ``epic`` returns from that copy.

    Returns:
        One sentence per problem: the story-build problems, then what the recording and the
        comparison found. Empty when the result can be accepted.

    """
    refused: list[str] = _change_problems(matrix, changes)
    unbuildable: list[str] = [
        *story_build_problems(matrix, bead, result[FIELD_ADDED_OR_CHANGED], FIELD_ADDED_OR_CHANGED),
        *story_build_problems(matrix, bead, result[FIELD_UNCHANGED_WORK], FIELD_UNCHANGED_WORK),
    ]
    if not result[FIELD_ADDED_OR_CHANGED] and not result[FIELD_UNCHANGED_WORK]:
        nothing: str = (
            f"{bead}: {FIELD_ADDED_OR_CHANGED} and {FIELD_UNCHANGED_WORK} are both empty, so no Story builds "
            f"anything: name under {FIELD_ADDED_OR_CHANGED} what the design adds or changes, and under "
            f"{FIELD_UNCHANGED_WORK} the existing elements where the Epic's work that leaves them unchanged lands"
        )
        unbuildable.append(nothing)
    both: list[EntryId] = sorted(
        set(story_build_entries(result[FIELD_ADDED_OR_CHANGED]))
        & set(story_build_entries(result[FIELD_UNCHANGED_WORK])),
    )
    if both:
        twice: str = (
            f"{bead}: {', '.join(both)} named in both {FIELD_ADDED_OR_CHANGED} and {FIELD_UNCHANGED_WORK}: "
            f"an element the design adds or changes belongs under {FIELD_ADDED_OR_CHANGED} only, and one it "
            f"leaves unchanged under {FIELD_UNCHANGED_WORK} only"
        )
        unbuildable.append(twice)
    recorded: Recorded = _compared(matrix, bead, _record_design(matrix, bead, result))
    return [*refused, *unbuildable, *recorded.problems]


def _compared(matrix: Matrix, bead: str, recorded: Recorded) -> Recorded:
    """Compare what was recorded of an architecture result with what ``epic`` returns from a matrix.

    Returns:
        What was recorded, with one more problem for each requirement the result says a feature
        serves that the matrix does not show as served by it, and one for each requirement the
        matrix shows with no feature that the result does not list as having none; and the
        requirements the matrix shows with no feature.

    """
    view: EpicView = epic_view(matrix, bead)
    shown: set[tuple[JsonValue, JsonValue]] = {
        (stated["requirement"].get("id"), feature.get("id"))
        for stated in view["requirements"]
        for feature in stated["features"]
    }
    unconfirmed: list[str] = [
        f"the matrix does not show {requirement} as served by {feature}"
        for requirement, feature in recorded.served
        if (requirement, feature) not in shown
    ]
    unlisted: list[str] = [
        f"{requirement} is served by no feature and the result does not list it under noFeature"
        for requirement in view["noFeature"]
        if requirement not in recorded.listed
    ]
    return Recorded(
        served=recorded.served,
        problems=(*recorded.problems, *unconfirmed, *unlisted),
        no_feature=tuple(view["noFeature"]),
        listed=recorded.listed,
    )


def _request_problems(requests: Sequence[AgentRequest]) -> list[str]:
    """Hold a round of requests to the catalog, to the agents a request may name, and to one request per agent.

    Returns:
        One sentence for each agent the find-specialists catalog does not list, one for each agent
        the script starts from the result itself (:data:`SCRIPT_STARTED`), and one for each agent
        named by more than one request.

    """
    named: list[str] = [step_journal.agent_name(entry["agent"]) for entry in requests]
    unknown: list[str] = [
        f"requests: the find-specialists catalog lists no agent named {agent!r}"
        for agent in dict.fromkeys(named)
        if agent not in CATALOG_AGENTS
    ]
    started: list[str] = [
        f"requests: {agent} is started by the script from your result, never by a request: state each TRD "
        "change in trdChanges, and what the documents must say in facts, restatements, settlements and diagrams"
        for agent in dict.fromkeys(named)
        if agent in SCRIPT_STARTED
    ]
    twice: list[str] = [
        f"requests: {agent} is named by {named.count(agent)} requests; put all of its questions and draft reviews "
        "of this round in one request"
        for agent in dict.fromkeys(named)
        if named.count(agent) > 1
    ]
    return [*unknown, *started, *twice]


def _about_problems(matrix: Matrix, result: ArchitectureResult) -> list[str]:
    """Find each entry a fact of the result is about that the matrix does not hold.

    Returns:
        One sentence per id that is not an entry id, or is not held.

    """
    problems: list[str] = []
    for fact in result["facts"]:
        for named in fact["about"]:
            _held(matrix, named, f"fact {fact['id']} about", problems)
    return problems


def _decision_problems(bead: str, result: ArchitectureResult, changes: Path, log: Path) -> list[str]:
    """Find what an architecture result, its change file and its review log leave unfinished, writing nothing.

    Returns:
        :func:`_result_problems`; then each id a fact is about that the matrix, with the change
        file applied, does not hold; then, when the result asks no further round, each problem of
        the review log (``architecture_check.review_log_findings``).

    """
    matrix: Matrix = read_matrix(matrix_file())
    problems: list[str] = _result_problems(matrix, bead, result, changes)
    problems.extend(_about_problems(matrix, result))
    if not result["requests"]:
        problems.extend(review_log_findings(bead, log, matrix, result))
    return problems


def result_check(run: StepRun) -> Callable[[Path], dict[str, JsonValue]]:
    """Build the output check of a session that writes the architecture result.

    Returns:
        A check that reads the output as strict JSON, validates it with its contract, then runs
        :func:`_decision_problems` with the change file beside the context file and the review
        log, and :func:`_request_problems` on its ``requests``. Each problem is one line of the
        ``ArchitectureWorkError`` it raises, which sends the session to its one correction.

    """
    context: ArchitectureContext = read_context(run)

    def check(path: Path) -> dict[str, JsonValue]:
        document: dict[str, JsonValue] = strict_json(path)
        result: ArchitectureResult = validate_architecture_result(document, str(path))
        problems: list[str] = [
            *run.tools.portfolio(
                run.inputs.stage,
                _decision_problems,
                str(run.bead),
                result,
                architecture_folder(run.context.work) / CHANGE_FILE,
                Path(context["reviewLogPath"]),
            ),
            *_request_problems(result["requests"]),
        ]
        if problems:
            raise ArchitectureWorkError("\n".join(problems))
        return document

    return check


def _round_check(context: ArchitectureContext) -> Callable[[Path], dict[str, JsonValue]]:
    """Build the output check of the Analyze step.

    Returns:
        A check that reads the output as strict JSON, validates it as a round of requests, refuses
        what :func:`_request_problems` finds, and validates the state file at the context's
        ``statePath``, which the step writes first.

    """

    def check(path: Path) -> dict[str, JsonValue]:
        document: dict[str, JsonValue] = strict_json(path)
        stated: SpecialistRound = validate_specialist_round(document, str(path))
        state: Path = Path(context["statePath"])
        validate_architecture_state(strict_json(state), str(state))
        problems: list[str] = _request_problems(stated["requests"])
        if problems:
            raise ArchitectureWorkError("\n".join(problems))
        return document

    return check


def _recommendation(entry: SpecialistRecommendation) -> JsonValue:
    """State one specialist recommendation as the action the owner reads.

    Returns:
        The recommendation as one sentence naming the agent, what it would hold and the subject.

    """
    return (
        f"Solutions architect recommends: {entry['action']} the specialist agent {entry['agent']!r}: "
        f"{entry['recommendation']} (subject it designed itself: {entry['subject']})"
    )


def _analyze(run: StepRun, context: ArchitectureContext, prd: Path) -> AgentLaunch:
    """Build the session of the architect's Analyze step.

    The output is the first round of requests, one per specialist; the state file is written
    first. The accepted round plans after the step one step per request whose answer is not yet
    a valid answer, then the Decide step (``architecture_rounds.round_steps``).

    Returns:
        The launch.

    """

    def accept(accepted: StepRun, output: Path) -> Completion:
        stated: SpecialistRound = checked_file(accepted, output, validate_specialist_round)
        return Completion(
            add=(round_steps(accepted, stated["requests"], 1),),
            artifacts=(file_artifact(LABEL_ROUND, output), file_artifact(LABEL_STATE, Path(context["statePath"]))),
        )

    return AgentLaunch(
        output=architecture_folder(run.context.work) / QUESTIONS_FILE,
        validate=_round_check(context),
        outcome="The state file, then one request per specialist this Epic needs.",
        accept=accept,
        add_dirs=(architecture_folder(run.context.work),),
        files=_handed_files(run, context, prd, EXAMPLE_STATE, EXAMPLE_ROUND),
        hand_inputs=False,
    )


@agent_step(ARCHITECT)
def architect(run: StepRun) -> AgentLaunch:
    """Build the session of any step the solutions architect performs, always a fresh session.

    The Analyze step writes the first round of requests (:func:`_analyze`). Every other step (a
    Decide, a correction after findings, a competing design the lead orders) writes the
    architecture result, its decisions, which every step after the first updates in place: a
    result already at the result path is kept, so a session that starts again continues from it,
    and a valid file there is never taken as the step's finished output without the session
    (``reuse_output`` False).

    The accepted result is recorded in the matrix. A result that asks a further round plans that
    round and a Decide after it; one that asks it after :data:`MAX_ROUNDS` rounds fails the step.
    A result that asks none plans the document writes it needs (``architecture_rounds.write_steps``).

    The session is handed files and no folder of the architecture or of the PRDs: it reads the PRD
    it is handed in full, and the documents and headings the Epic reaches through the matrix, which
    is its starting point and not a complete record.

    Returns:
        The launch: the output, the files the definition names, and what the journal records when
        the output is accepted.

    """
    context: ArchitectureContext = read_context(run)
    prd: Path = journal_file(run, LABEL_PRD)
    pack_file(run)
    if run.step["description"] == ANALYZE_DESCRIPTION:
        return _analyze(run, context, prd)
    number: int = round_of(run)
    arch: Path = Path(context["architectureRoot"])

    def accept(accepted: StepRun, output: Path) -> Completion:
        result: ArchitectureResult = checked_file(accepted, output, validate_architecture_result)
        open_requests: list[AgentRequest] = [entry for entry in result["requests"] if not answered(entry["request"])]
        if open_requests and number >= MAX_ROUNDS:
            raise ArchitectureStepError(
                accepted,
                f"the architect's result still requests work of {[entry['agent'] for entry in open_requests]} after "
                f"{MAX_ROUNDS} rounds; the architecture does not converge",
            )
        recorded: Recorded = accepted.tools.portfolio(
            accepted.inputs.stage,
            _record_result,
            str(accepted.bead),
            result,
            architecture_folder(accepted.context.work) / CHANGE_FILE,
        )
        if recorded.problems:
            raise ArchitectureStepError(
                accepted,
                f"the matrix does not hold what the architecture result {output} and its change file state",
                *recorded.problems,
            )
        unserved: list[JsonValue] = [*recorded.no_feature]
        follows: tuple[StepGroup, ...] = (
            (round_steps(accepted, open_requests, number + 1),)
            if open_requests
            else write_steps(arch, Path(context["helpersFolder"]), result)
        )
        return Completion(
            add=follows,
            artifacts=(
                file_artifact(LABEL_RESULT, output),
                value_artifact(ARTIFACT_CONCLUSION, result["conclusion"]),
                value_artifact(NO_FEATURE, unserved),
                value_artifact(
                    ARTIFACT_SPECIALIST_RECOMMENDATIONS,
                    [_recommendation(entry) for entry in result["specialistRecommendations"]],
                ),
            ),
        )

    return AgentLaunch(
        output=Path(context["resultPath"]),
        validate=result_check(run),
        outcome="The architecture result of this PRD.",
        accept=accept,
        add_dirs=(architecture_folder(run.context.work),),
        files=_handed_files(run, context, prd, EXAMPLE_RESULT),
        fresh_output=False,
        hand_inputs=False,
        reuse_output=False,
    )


def _saved_request(run: StepRun, *names: str) -> tuple[str, Path]:
    """Find the request file a helper step is launched from.

    A step the script planned from the architect's output (``architecture_rounds``) is handed its
    request file as a parameter. A step the lead planned holds its request file itself, or is
    handed it by its inputs.

    Returns:
        The artifact name and the path of the request: the parameter the planning step handed,
        else the file the step itself held when its agent's session stopped, else the one the
        step's inputs hand it.

    Raises:
        ArchitectureStepError: Neither the parameters, the step nor its inputs hold a request file.

    """
    planned: JsonValue = run.params().get(PARAM_REQUEST)
    if isinstance(planned, str):
        return LABEL_REQUEST, Path(planned)
    name: str
    for name in names:
        held: Path | None = run.saved.optional_file(name) or run.inputs.optional_file(name)
        if held is not None:
            return name, held
    raise ArchitectureStepError(run, f"neither the step nor its inputs hold a request file named one of {names!r}")


def _planner(run: StepRun) -> Step | None:
    """Find the step that planned a helper step.

    Returns:
        The step that holds the record of planning it (``step_journal.planned_for_name``), else
        the step directly above it.

    """
    record: str = step_journal.planned_for_name(run.step["id"])
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        if any(held["name"] == record for held in step["artifacts"]):
            return step
    return step_journal.parent_step(run.journal(), run.step["id"])


def _helper_request[T](run: StepRun, asked: Path, validate: Callable[[object], T]) -> T:
    """Read the request a helper step is launched from, written by the step that planned it (:func:`_planner`).

    The architect's output, or the lead's session, holds the request. A request that
    does not satisfy the current contract is stale only when the writer's session was made under
    another agent definition or contracts (``AgentRunner.resumable``), or the writer holds no
    session: the step above the helper then runs again and writes its requests to the current
    contract. Otherwise the writer wrote it wrongly under the current contract, and its session
    corrects the file from the errors written beside it.

    Returns:
        The validated request.

    Raises:
        ArchitectureStepError: The file is missing or is not JSON, or the helper has no step above it.
        StaleInputError: The request does not satisfy the current contract, and the writer's
            session is not one of the current agent definition and contracts.
        MalformedRequestError: The request does not satisfy the current contract, and the
            writer's session is one of the current agent definition and contracts.

    """
    held: object = checked_file(run, asked, lambda value: value)
    try:
        return validate(held)
    except ArchitectureWorkError as exc:
        writer: Step | None = _planner(run)
        if writer is None:
            raise ArchitectureStepError(run, f"{asked}: {exc}") from None
        evidence: tuple[str, ...] = (f"step {run.step['id']} ({run.step['description']}): {asked}: {exc}",)
        session: str | None = writer.get("session")
        if session is None or not run.agents.resumable(session):
            raise StaleInputError(run.inputs.stage, writer["id"], evidence) from None
        errors: Path = asked.with_name(asked.stem + ERRORS_SUFFIX)
        errors.write_text(f"{exc}\n", encoding="utf-8")

        def check(path: Path) -> dict[str, JsonValue]:
            document: dict[str, JsonValue] = strict_json(path)
            validate(document)
            return document

        raise MalformedRequestError(
            run.inputs.stage,
            writer["id"],
            session=session,
            request=asked,
            errors=errors,
            check=check,
            evidence=evidence,
        ) from None


@any_agent_step(CATALOG_AGENTS)
def specialist(run: StepRun) -> AgentLaunch:
    """Build the session of any agent the architect or the lead named for a request.

    The agent is the one the step names: the architect's round of requests named it
    (``questions.json``, or a result's ``requests``), or the lead asked it for an opinion. No
    code chooses it. The repository steward, when named, answers what the architect's
    placement needs to know about the repositories; the placement itself is the architect's,
    recorded in the matrix before the steward starts and checked when the architect's result is
    accepted (``repo_scoping.story_build_problems``).

    Returns:
        The launch from the request file the step's parameters name, else the saved one: the
        answer path the request names as output.

    """
    name: str
    asked: Path
    name, asked = _saved_request(run, LABEL_REQUEST, LABEL_QUESTION)
    request: SpecialistRequest = _helper_request(run, asked, validate_specialist_request)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(LABEL_ANSWER, output),))

    return AgentLaunch(
        output=Path(request["answerPath"]),
        validate=output_check(validate_specialist_answer),
        outcome="The answer to the request, at the path the request names.",
        accept=accept,
        add_dirs=(run.context.work,),
        files=((LABEL_REQUEST, asked),),
        hand_inputs=False,
        keep=(file_artifact(name, asked),),
    )


def _constraint(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - The parts of one constraint.
    matrix: Matrix,
    name: str,
    rule: Mapping[str, JsonValue],
    applies_to: EntryId,
    problems: list[str],
    stated_in: tuple[EntryId, str] | None = None,
) -> EntryId | None:
    """Record one constraint with its rule, what it applies to and, when a document states it, where.

    ``rule`` is the constraint's ``statement``, or for a TRD requirement its ``trd`` pointer with
    ``statement`` null, which removes a statement the entry held.

    Returns:
        The constraint's id; None, with one sentence added to ``problems``, when the matrix
        refused the entry.

    """
    try:
        recorded: EntryId = put(
            matrix,
            KIND_CONSTRAINT,
            SIDE_ARCHITECTURE,
            name=name,
            attributes=rule,
        )["id"]
    except MatrixError as error:
        problems.append(f"constraint {name!r}: {error}")
        return None
    _link(matrix, REL_APPLIES_TO, recorded, applies_to, problems)
    if stated_in is not None:
        _link(matrix, REL_STATED_IN, recorded, stated_in[0], problems, {ATTR_HEADING: stated_in[1]})
    return recorded


def _stated_in(matrix: Matrix, arch: Path, source: SourceHeading) -> tuple[EntryId, str] | None:
    """Find the document heading a technical requirement's source is.

    Returns:
        The document entry and the heading; None when the source is not a document heading the
        matrix holds, such as a PRD requirement.

    """
    document: EntryId | None = cited_document(arch, source["source"])
    if document is None or matrix.find(document) is None or not source["heading"].strip():
        return None
    return document, source["heading"].strip()


def _record_constraints(matrix: Matrix, bead: str, arch: Path, answer: TrdAnswer) -> Recorded:
    """Record the technical requirements a TRD answer states, as constraints.

    The answer lists each requirement the TRD write added or changed. Each is one constraint that
    points at the requirement (``trd``: the Epic and the requirement id, its heading in the TRD)
    and copies none of its text, with ``statedIn`` to the document heading that is its source and ``appliesTo`` to
    the entry it names, or to the Epic when it names none; each requirement the answer lists as
    removed loses its constraint. Each obligation the answer lists with no source is one
    constraint with no ``statedIn`` that applies to the Epic.

    Returns:
        The constraints recorded, and what could not be recorded.

    """
    epic: EntryId = epic_id(bead)
    problems: list[str] = []
    entries: list[EntryId | None] = []
    removed: str
    for removed in answer["removed"]:
        gone: EntryId = make_id(KIND_CONSTRAINT, slug(f"{bead} {removed.strip()}"))
        if matrix.find(gone) is not None:
            matrix.remove(gone)
    requirement: TrdRequirement
    for requirement in answer["requirements"]:
        named: str = f"{bead} {requirement['id'].strip()}"
        target: EntryId | None = (
            _held(matrix, requirement["appliesTo"], f"constraint {named!r} applies to", problems)
            if requirement["appliesTo"].strip()
            else epic
        )
        if target is not None:
            stated: tuple[EntryId, str] | None = _stated_in(matrix, arch, requirement["source"])
            pointer: dict[str, JsonValue] = {ATTR_EPIC: bead, ATTR_REQUIREMENT: requirement["id"].strip()}
            rule: dict[str, JsonValue] = {ATTR_TRD: pointer, ATTR_STATEMENT: None}
            entries.append(_constraint(matrix, named, rule, target, problems, stated))
    entries.extend(
        _constraint(
            matrix,
            unsourced["obligation"].strip(),
            {ATTR_STATEMENT: unsourced["obligation"].strip()},
            epic,
            problems,
        )
        for unsourced in answer["noSource"]
    )
    return Recorded(entries=tuple(entry for entry in entries if entry is not None), problems=tuple(problems))


def _record_trd(bead: str, arch: Path, answer: TrdAnswer) -> Recorded:
    """Record a TRD answer in the matrix as one change.

    Returns:
        What :func:`_record_constraints` returns.

    """

    def change(matrix: Matrix) -> Recorded:
        return _record_constraints(matrix, bead, arch, answer)

    return update_matrix(matrix_file(), change)


@agent_step(TRD_AUTHOR)
def trd_author(run: StepRun) -> AgentLaunch:
    """Build the session of the TRD author: the one TRD write after the decisions, or a correction.

    The TRD write runs once, when the architecture check passes and before the promotion: the
    script writes its request from the architect's result (``trd_steps.write_request``), and the
    session completes the TRD the seed wrote. A correction runs from the request file its step is
    handed, which the TRD confirm step writes. Every session of the author is handed the Epic's
    architecture pack. The answer is checked against
    the TRD it names: its front matter and citations, and every constraint that points at a
    requirement of this TRD names a heading of it once the answer is recorded. The accepted answer
    is recorded in the matrix: one constraint for each technical requirement the answer states,
    none for each it lists as removed, and one for each obligation it lists with no source.

    Returns:
        The launch from the request file; the TRD it names is kept and updated in place.

    """
    name: str
    asked: Path
    request: TrdRequest
    pack: Path = pack_file(run)
    complete: bool = run.step["description"] == WRITE_DESCRIPTION
    if complete:
        name, asked = LABEL_REQUEST, write_request(run)
        request = checked_file(run, asked, validate_trd_request)
    else:
        name, asked = _saved_request(run, LABEL_REQUEST)
        request = _helper_request(run, asked, validate_trd_request)
    arch: Path = Path(read_context(run)["architectureRoot"])
    trd: Path = Path(request["trdPath"])

    def check(output: Path) -> dict[str, JsonValue]:
        answer: dict[str, JsonValue] = strict_json(output)
        stated: TrdAnswer = validate_trd_answer(answer, str(output))
        matrix: Matrix = read_matrix(matrix_file())
        document(trd, matrix, TRD_FRONT_MATTER)
        dangling: list[str] = unresolved_requirements(
            matrix,
            str(run.bead),
            trd.read_text(encoding="utf-8"),
            removed=stated["removed"],
            written=[requirement["id"] for requirement in stated["requirements"]],
        )
        if dangling:
            raise DocumentValidationError("; ".join(dangling))
        return answer

    def accept(accepted: StepRun, output: Path) -> Completion:
        answer: TrdAnswer = checked_file(accepted, output, validate_trd_answer)
        recorded: Recorded = accepted.tools.portfolio(
            accepted.inputs.stage,
            _record_trd,
            str(accepted.bead),
            arch,
            answer,
        )
        if recorded.problems:
            raise ArchitectureStepError(
                accepted,
                f"the matrix does not hold the technical requirements of {asked} and {output}",
                *recorded.problems,
            )
        unsourced: list[JsonValue] = [entry["obligation"] for entry in answer["noSource"]]
        constraints: list[JsonValue] = [*recorded.entries]
        return Completion(
            artifacts=(
                file_artifact(ARTIFACT_TRD, trd),
                file_artifact(ARTIFACT_TRD_ANSWER, output),
                value_artifact(NO_SOURCE, unsourced),
                value_artifact(CONSTRAINTS, constraints),
            ),
        )

    return AgentLaunch(
        output=Path(request["answerPath"]),
        validate=check,
        outcome=(
            "The TRD completed from the PRD and the architect's decisions as the request asks, and the answer, "
            "each at the path the request names."
            if complete
            else "The TRD updated as the request asks, and the answer, each at the path the request names."
        ),
        accept=accept,
        add_dirs=(run.context.work,),
        files=((LABEL_REQUEST, asked), (ARTIFACT_PACK, pack)),
        hand_inputs=False,
        keep=(file_artifact(name, asked),),
    )


def _sync(arch: Path, paths: Sequence[str]) -> DocumentsSynced:
    """Set the named documents in review, then bring their entries up to date.

    Each named document that exists is set ``in-review`` in its front matter
    (``matrixsync.set_lifecycle``), so the check and the promotion of this run reach
    it; then the entries are synced as ``atw-matrix sync-documents --paths`` does. A named
    document that is gone is not set; the sync removes its entry.

    Returns:
        What the read did.

    """
    vault: Path = vault_root(arch)
    present: list[str] = [relative for relative in paths if (arch / relative).is_file()]
    relative: str
    for relative in present:
        set_lifecycle(vault, relative_path(arch / relative, vault), LIFECYCLE_IN_REVIEW)

    def change(matrix: Matrix) -> DocumentsSynced:
        return sync_documents(matrix, arch, paths=paths)

    return update_matrix(matrix_file(), change)


def _record_homes(arch: Path, request: WriteRequest, written: WriteResult) -> Recorded:
    """Record the headings a write states the request's facts under, in one matrix change.

    For each fact the result does not list under ``notApplied``: ``describedBy`` from each entry
    it is about to its home heading, and ``covers`` from that heading to each requirement an
    entry among them serves as a feature (``servedBy``), with that feature as ``via``. A home
    with no heading (a document that holds no Markdown heading) is the whole document: its
    ``describedBy`` names no heading and it covers nothing, since ``covers`` requires a heading.

    Returns:
        What could not be recorded: a home that is no document the matrix holds, an entry it does not hold.

    """
    skipped: set[str] = {entry["entry"] for entry in written["notApplied"]}

    def change(matrix: Matrix) -> Recorded:
        problems: list[str] = []
        for fact in request["facts"]:
            if fact["id"] in skipped or not fact["about"]:
                continue
            home: EntryId | None = cited_document(arch, fact["home"]["source"])
            heading: str = fact["home"]["heading"].strip()
            stated: dict[str, JsonValue] = {ATTR_HEADING: heading} if heading else {}
            if home is None or matrix.find(home) is None:
                source: str = fact["home"]["source"]
                problems.append(f"fact {fact['id']}: its home {source!r} is no document the matrix holds")
                continue
            for named in fact["about"]:
                entry: EntryId | None = _held(matrix, named, f"fact {fact['id']} about", problems)
                if entry is None:
                    continue
                _link(matrix, REL_DESCRIBED_BY, entry, home, problems, stated)
                if not heading:
                    continue
                for served in matrix.incoming(entry, (REL_SERVED_BY,)):
                    covered: dict[str, JsonValue] = {ATTR_HEADING: heading, ATTR_VIA: entry}
                    _link(matrix, REL_COVERS, home, served.start, problems, covered)
        return Recorded(problems=tuple(problems))

    return update_matrix(matrix_file(), change)


@agent_step(MAINTAINER)
def maintainer(run: StepRun) -> AgentLaunch:
    """Build the session of the document maintainer of one write request the script wrote.

    A request holds one group of arc42 sections (``architecture_rounds.SECTION_GROUPS``). The
    output check validates the result and, in the same pass, checks each Mermaid block of the
    documents written that the vault's last commit does not hold
    (``architecture_diagrams.syntax_problems``), so the session's one correction is handed every
    problem at once; a result that does not validate still has the request's homes checked. The
    accepted result is mirrored in the matrix: each document written is set in review and its
    entry is brought up to date with its headings and lifecycle, and the entry of a document that
    is gone is removed; then each fact's home heading is recorded (:func:`_record_homes`). The
    session is granted the architecture root, where it writes the arc42 documents.

    Returns:
        The launch from the write request the step's parameters name, else the saved one: the
        result path the request names as output.

    """
    name: str
    asked: Path
    name, asked = _saved_request(run, WRITE_REQUEST, LABEL_REQUEST)
    request: WriteRequest = _helper_request(run, asked, validate_write_request)
    context: ArchitectureContext = read_context(run)
    arch: Path = Path(context["architectureRoot"])
    rendered: Path = Path(context["helpersFolder"]) / "diagrams" / run.step["id"][:ID_LENGTH]

    def check(path: Path) -> dict[str, JsonValue]:
        document: dict[str, JsonValue] = strict_json(path)
        problems: list[str] = []
        written: WriteResult = _NOTHING_WRITTEN
        try:
            written = validate_write_result(document, str(path))
        except ArchitectureWorkError as invalid:
            problems.append(str(invalid))
        problems.extend(syntax_problems(run, arch, written_paths(arch, request, written), rendered))
        if problems:
            raise ArchitectureWorkError("\n".join(problems))
        return document

    def accept(accepted: StepRun, output: Path) -> Completion:
        written: WriteResult = checked_file(accepted, output, validate_write_result)
        paths: list[str] = written_paths(arch, request, written)
        if paths:
            accepted.tools.portfolio(accepted.inputs.stage, _sync, arch, paths)
        recorded: Recorded = accepted.tools.portfolio(accepted.inputs.stage, _record_homes, arch, request, written)
        if recorded.problems:
            raise ArchitectureStepError(
                accepted,
                f"the matrix does not hold the headings {output} states the facts of {asked} under",
                *recorded.problems,
            )
        synced: list[JsonValue] = [*paths]
        return Completion(artifacts=(file_artifact(WRITTEN, output), value_artifact(SYNCED, synced)))

    return AgentLaunch(
        output=Path(request["resultPath"]),
        validate=check,
        outcome="The arc42 documents written as the request states, and the result at the path it names.",
        accept=accept,
        add_dirs=(run.context.work, arch),
        files=((LABEL_REQUEST, asked),),
        hand_inputs=False,
        keep=(file_artifact(name, asked),),
    )
