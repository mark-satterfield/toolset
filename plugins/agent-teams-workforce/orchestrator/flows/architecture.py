"""The solutions architect's steps, and the sessions of the agents it left running.

One agent, the solutions architect, decides what the architecture should be for a PRD. Before it
starts, the TRD initial write runs as one of the very first steps of the architecture: ``trd-author``
writes the requirements not considered functional, many of them already pre-written in arc42, from a
request the script writes. The architect is handed that step's answer, works from the TRD, and has
it updated once the higher-level architecture is in arc42, before the detailed design. The script
starts the architect's session, hands it the files its definition names and records what it returns.
The architect always reads the PRD it is handed; the arc42 documents and the matrix are its
starting point, both input and output, possibly incomplete or wrong and possibly empty for the
Epic. It reads what the matrix holds for the Epic itself, live, with ``atw-matrix``, so nothing it
is handed drifts from the matrix it writes to. It decides the stack and repository of each element
after its detailed design and records that placement itself; the repository steward does the
repository work that follows. What the architect reads, whom it asks and in what order are its
own decisions. The same launch builder serves every step that agent
performs: the first, its "Finish" after an interruption, a correction after findings or after the
mechanical check, and a competing design the lead orders.

An agent the architect starts runs inside the architect's session. Only one it left running when
its session stopped is launched here, from the request file the architect saved for it.

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
    TRD_MODE_INITIAL,
    ArchitectureWorkError,
    validate_architecture_result,
    validate_specialist_answer,
    validate_specialist_request,
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
    SIDE_ARCHITECTURE,
    MatrixError,
)
from matrixquery import epic_view
from matrixstore import as_entry_id, make_id, name_key, read_matrix, slug, update_matrix
from matrixsync import LIFECYCLE_IN_REVIEW, relative_path, set_lifecycle, sync_documents, vault_root
from matrixtraverse import epic_id
from matrixwrite import link, put
from specialist_catalog import agent_names

from orchestrator.core.agents import strict_json
from orchestrator.core.io import write_json
from orchestrator.core.journal_registry import agent_step, any_agent_step, plan_under
from orchestrator.core.journal_steps import (
    UNDER_CONTAINER,
    UNDER_THIS,
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.flows.architecture_check import check_step
from orchestrator.flows.architecture_files import (
    ARCHITECT,
    ARCHITECTURE,
    ARTIFACT_CHECK,
    ARTIFACT_CONCLUSION,
    ARTIFACT_SPECIALIST_RECOMMENDATIONS,
    ARTIFACT_TRD,
    LABEL_ANSWER,
    LABEL_CONTEXT,
    LABEL_FINDINGS,
    LABEL_PRD,
    LABEL_QUESTION,
    LABEL_REQUEST,
    LABEL_RESULT,
    LABEL_RULING,
    LABEL_STATE,
    MAINTAINER,
    TRD_AUTHOR,
    WRITE_REQUEST,
    WRITTEN,
    ArchitectureContext,
    ArchitectureStepError,
    checked_file,
    cited_document,
    document_path,
    is_finish,
    journal_file,
    matrix_file,
    output_check,
    read_context,
)
from orchestrator.flows.repo_scoping import FIELD_ADDED_OR_CHANGED, FIELD_UNCHANGED_WORK, story_build_problems

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from architecture_work_contract import (
        AgentRequest,
        ArchitectureResult,
        Citation,
        SpecialistRecommendation,
        SpecialistRequest,
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
    from step_journal_contract import Step, StepId, StepPlan

    from orchestrator.core.io import JsonValue

ARCHITECT_DESCRIPTION: Final = "Decide what the architecture should be for this PRD"
ARCHITECT_PURPOSE: Final = "One agent is responsible for the architecture this PRD needs, and reviews and approves it"
ARCHITECT_REF: Final = "architect"
TRD_INITIAL_DESCRIPTION: Final = (
    "TRD initial write: the requirements not considered functional, many pre-written in arc42"
)
TRD_INITIAL_PURPOSE: Final = (
    "The TRD is written as one of the very first steps; the architecture and the detailed design read it"
)
TRD_INITIAL_REF: Final = "trd-initial"
TRD_INITIAL_FILE: Final = "trd-initial"
"""The stem of the request and answer files of the TRD initial write, in the helpers folder."""
ANSWER_SUFFIX: Final = ".answer.json"
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
PARAM_REQUEST: Final = "request"
"""The parameter that hands a requested agent's step the path of its request file."""
REQUEST_SUFFIX: Final = ".request.json"
"""What the request file of an entry of the result's ``requests`` adds to its answer file's stem."""
FINISH_DESCRIPTION: Final = "Finish deciding the architecture with the answers of the agents the architect requested"
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
    """Plan the architect's first step.

    Returns:
        The plan, handed the steps ``inputs`` names.

    """
    return {
        "ref": ARCHITECT_REF,
        "description": ARCHITECT_DESCRIPTION,
        "purpose": ARCHITECT_PURPOSE,
        "agent": architect,
        "inputs": inputs,
    }


def _trd_initial_plan(inputs: list[str]) -> StepPlan:
    """Plan the TRD initial write.

    Returns:
        The plan of ``trd-author``'s step, handed the steps ``inputs`` names.

    """
    return {
        "ref": TRD_INITIAL_REF,
        "description": TRD_INITIAL_DESCRIPTION,
        "purpose": TRD_INITIAL_PURPOSE,
        "agent": TRD_AUTHOR,
        "inputs": inputs,
    }


def first_steps(opened: StepId, container: StepId, architect: str) -> StepGroup:
    """Plan the TRD initial write, the architect's step and the check, under the Architecture container.

    The TRD initial write comes first, so the architect starts from the TRD and is handed its
    answer. The same three plans are registered as what this lane plans under the container
    (``journal_registry.plan_under``). A journal written before the check's key was renamed
    therefore has its planned check step replanned to the current ``CHECK`` when the run opens
    the journal (``journal_run.replan_unhandled``), whether or not a step of the architect is
    still pending, which is when this group is left out.

    Args:
        opened: The open-run step, whose artifacts the planned steps are handed.
        container: The Architecture container.
        architect: The agent that plays the solutions architect.

    Returns:
        The TRD initial write, the architect's step and the check that follows it, as the
        container's last child steps.
        The group is left out when the container already holds a step of the architect that is
        not done.

    """
    return StepGroup(
        (
            NewStep(_trd_initial_plan([opened])),
            NewStep(_architect_plan(architect, [opened, TRD_INITIAL_REF])),
            check_step([ARCHITECT_REF], corrections=0),
        ),
        UNDER_CONTAINER,
        container,
        unless_agent=architect,
    )


plan_under(
    ARCHITECTURE,
    _trd_initial_plan([]),
    _architect_plan(ARCHITECT, []),
    check_step([ARCHITECT_REF], corrections=0).plan,
)


def _handed_files(run: StepRun, context: ArchitectureContext, prd: Path) -> tuple[tuple[str, Path], ...]:
    """Name the files of the architect's brief: exactly the labels its definition states.

    No file is written from the matrix for the architect: it runs the ``atw-matrix`` reads its
    definition names for the Epic, so what it reads is the matrix as it is at that moment.

    Returns:
        The PRD, the context file and the state path; then each mechanical check result the
        step is handed, as findings; then each answer the step is handed (the TRD initial
        write's answer on the first step, a specialist's answer later) and each ruling.

    """
    findings: list[Path] = list(run.inputs.files(ARTIFACT_CHECK))
    return (
        (LABEL_PRD, prd),
        (LABEL_CONTEXT, journal_file(run, LABEL_CONTEXT)),
        (LABEL_STATE, Path(context["statePath"])),
        *((LABEL_FINDINGS, path) for path in dict.fromkeys(findings)),
        *((LABEL_ANSWER, path) for path in dict.fromkeys(run.inputs.files(LABEL_ANSWER))),
        *((LABEL_RULING, path) for path in dict.fromkeys(run.inputs.files(LABEL_RULING))),
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


def _record_result(bead: str, result: ArchitectureResult) -> Recorded:
    """Record an architecture result in the matrix and compare it with what ``epic`` then returns.

    Returns:
        :func:`_compared` on the matrix as the write left it.

    """

    def change(matrix: Matrix) -> Recorded:
        return _record_design(matrix, bead, result)

    recorded: Recorded = update_matrix(matrix_file(), change)
    return _compared(read_matrix(matrix_file()), bead, recorded)


def _result_problems(bead: str, result: ArchitectureResult) -> list[str]:
    """Find what the matrix could not hold of an architecture result, without writing the matrix.

    What the Epic's Stories build is checked against the matrix as it is
    (``repo_scoping.story_build_problems``): the result's ``addedOrChangedElements`` and its
    ``unchangedWorkElements``, each list on its own, and at least one of them must name something.
    Then the design is recorded in an in-memory copy of the matrix, which is
    never written, and compared with what ``epic`` returns from that copy.

    Returns:
        One sentence per problem: the story-build problems, then what the recording and the
        comparison found. Empty when the result can be accepted.

    """
    matrix: Matrix = read_matrix(matrix_file())
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
    recorded: Recorded = _compared(matrix, bead, _record_design(matrix, bead, result))
    return [*unbuildable, *recorded.problems]


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


def result_check(run: StepRun) -> Callable[[Path], dict[str, JsonValue]]:
    """Build the output check of a session that writes the architecture result.

    Returns:
        A check that reads the output as strict JSON, validates it with its contract, then runs
        :func:`_result_problems`, and refuses a request naming an agent the find-specialists
        catalog does not list. Each problem is one line of the ``ArchitectureWorkError`` it
        raises, which sends the session to its one correction.

    """

    def check(path: Path) -> dict[str, JsonValue]:
        document: dict[str, JsonValue] = strict_json(path)
        result: ArchitectureResult = validate_architecture_result(document, str(path))
        problems: list[str] = [
            *run.tools.portfolio(run.inputs.stage, _result_problems, str(run.bead), result),
            *(
                f"requests: the find-specialists catalog lists no agent named {entry['agent']!r}"
                for entry in result["requests"]
                if entry["agent"] not in CATALOG_AGENTS
            ),
        ]
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


@agent_step(ARCHITECT)
def architect(run: StepRun) -> AgentLaunch:
    """Build the session of any step the solutions architect performs.

    The resolved inputs say which step it is. A step that is handed findings is a correction; the
    "Finish" step below the architect's own step continues that step's session; any other step
    after one of the architect's continues the nearest earlier session the agent holds. The
    output is always the architecture result, which every step after the first updates in place.

    The session is handed files and no folder of the architecture or of the PRDs: it reads the PRD
    it is handed in full, and the documents and headings the Epic reaches through the matrix, which
    is its starting point and not a complete record. A result already at the result path is
    kept for every step: the architect writes its result as the work goes, so a session that
    starts again, for the first step as for any other, continues from the partial result. A
    valid file at the result path is therefore never taken as the step's finished output
    without the session (``reuse_output`` False).

    Returns:
        The launch: the result file as output, the files the definition names, and what the
        journal records when the result is accepted.

    """
    context: ArchitectureContext = read_context(run)
    prd: Path = journal_file(run, LABEL_PRD)
    holder: Step | None = None if is_finish(run) else run.session_holder()

    def accept(accepted: StepRun, output: Path) -> Completion:
        result: ArchitectureResult = checked_file(accepted, output, validate_architecture_result)
        recorded: Recorded = accepted.tools.portfolio(accepted.inputs.stage, _record_result, str(accepted.bead), result)
        if recorded.problems:
            raise ArchitectureStepError(
                accepted,
                f"the matrix does not hold what the architecture result {output} states",
                *recorded.problems,
            )
        unserved: list[JsonValue] = [*recorded.no_feature]
        requested: tuple[StepGroup, ...] = _requested(result["requests"])
        return Completion(
            add=requested,
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
        add_dirs=(run.context.work,),
        files=_handed_files(run, context, prd),
        resume_from=None if holder is None else holder["id"],
        fresh_output=False,
        hand_inputs=False,
        reuse_output=False,
    )


def _answered(request: SpecialistRequest) -> bool:
    """Tell whether a request's answer file already holds a valid answer.

    Returns:
        True when the file at the request's answer path is a valid specialist answer.

    """
    path: Path = Path(request["answerPath"])
    if not path.is_file():
        return False
    try:
        validate_specialist_answer(strict_json(path), str(path))
    except OSError, ValueError:
        return False
    return True


def _requested(requests: Sequence[AgentRequest]) -> tuple[StepGroup, ...]:
    """Plan the work the architect's result requests of other agents, below the accepting step.

    Each request whose answer is not yet a valid answer gets one step, performed by the agent the
    request names and handed its request file, written beside the answer path; then one
    ``Finish`` step of the architect, handed every answer. The agent of each step is the one the
    result names; nothing here chooses it.

    Returns:
        One group below the accepting step; none when every request is answered.

    """
    steps: list[NewStep] = []
    refs: list[str] = []
    index: int
    entry: AgentRequest
    for index, entry in enumerate(requests):
        if _answered(entry["request"]):
            continue
        answer: Path = Path(entry["request"]["answerPath"])
        asked: Path = answer.with_name(answer.stem + REQUEST_SUFFIX)
        write_json(asked, entry["request"])
        ref: str = f"request-{index}"
        refs.append(ref)
        steps.append(
            NewStep(
                {
                    "ref": ref,
                    "description": f"Answer the solutions architect's request to {entry['agent']}",
                    "purpose": "The solutions architect named this agent for this work in its result",
                    "agent": entry["agent"],
                },
                params={PARAM_REQUEST: str(asked)},
            ),
        )
    if not steps:
        return ()
    finish: StepPlan = {
        "description": FINISH_DESCRIPTION,
        "purpose": "The architect decides with the answers to the requests its result made",
        "agent": ARCHITECT,
        "inputs": refs,
    }
    return (StepGroup((*steps, NewStep(finish)), UNDER_THIS),)


def _saved_request(run: StepRun, *names: str) -> tuple[str, Path]:
    """Find the request file a helper step is launched from.

    Returns:
        The artifact name and the path of the request the step itself held when its agent's
        session stopped, or that the step's inputs hand it.

    Raises:
        ArchitectureStepError: Neither the step nor its inputs hold a request file.

    """
    name: str
    for name in names:
        held: Path | None = run.saved.optional_file(name) or run.inputs.optional_file(name)
        if held is not None:
            return name, held
    raise ArchitectureStepError(run, f"neither the step nor its inputs hold a request file named one of {names!r}")


@any_agent_step(CATALOG_AGENTS)
def specialist(run: StepRun) -> AgentLaunch:
    """Build the session of any agent the architect or the lead named for a request.

    The agent is the one the step names: the architect's result named it (``requests``), the
    architect started it in its own session and it was left running, or the lead asked it for an
    opinion. No code chooses it. The repository steward, when named, does the repository work the
    architect's placement calls for; the placement itself is the architect's, recorded in the
    matrix before the steward starts and checked when the architect's result is accepted
    (``repo_scoping.story_build_problems``).

    Returns:
        The launch from the request file the step's parameters name, else the saved one: the
        answer path the request names as output.

    """
    name: str
    asked: Path
    planned: JsonValue = run.params().get(PARAM_REQUEST)
    if isinstance(planned, str):
        name, asked = LABEL_REQUEST, Path(planned)
    else:
        name, asked = _saved_request(run, LABEL_REQUEST, LABEL_QUESTION)
    request: SpecialistRequest = checked_file(run, asked, validate_specialist_request)

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


def _stated_in(matrix: Matrix, arch: Path, source: Citation) -> tuple[EntryId, str] | None:
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


def _initial_request(run: StepRun) -> Path:
    """Write the request of the TRD initial write from the architecture context.

    Returns:
        The request file, in the helpers folder: mode ``initial`` for the Epic, its PRD, the TRD
        path the context names, and the answer path beside the request.

    """
    context: ArchitectureContext = read_context(run)
    helpers: Path = Path(context["helpersFolder"])
    asked: Path = helpers / (TRD_INITIAL_FILE + REQUEST_SUFFIX)
    request: TrdRequest = {
        "mode": TRD_MODE_INITIAL,
        "epic": context["bead"],
        "prdPath": context["prdPath"],
        "trdPath": context["trdPath"],
        "sharedCapabilities": [],
        "changes": [],
        "answerPath": str(helpers / (TRD_INITIAL_FILE + ANSWER_SUFFIX)),
    }
    write_json(asked, request)
    return asked


@agent_step(TRD_AUTHOR)
def trd_author(run: StepRun) -> AgentLaunch:
    """Build the session of the TRD author: the TRD initial write, or an update left running.

    The TRD initial write is one of the very first steps of the architecture, before the
    architect's: the script writes its request (:func:`_initial_request`). An update, the TRD
    architecture update among them, is requested by the architect in its own session, and is
    launched here only when it was left running, from the request file the architect saved. The
    accepted answer is recorded in the matrix: one constraint for each technical requirement the
    answer states, none for each it lists as removed, and one for each obligation it lists with no
    source.

    Returns:
        The launch from the request file; the TRD it names is kept and updated in place.

    """
    name: str
    asked: Path
    if run.step["description"] == TRD_INITIAL_DESCRIPTION:
        name, asked = LABEL_REQUEST, _initial_request(run)
    else:
        name, asked = _saved_request(run, LABEL_REQUEST)
    request: TrdRequest = checked_file(run, asked, validate_trd_request)
    arch: Path = Path(read_context(run)["architectureRoot"])

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
                file_artifact(ARTIFACT_TRD, Path(request["trdPath"])),
                file_artifact(LABEL_ANSWER, output),
                value_artifact(NO_SOURCE, unsourced),
                value_artifact(CONSTRAINTS, constraints),
            ),
        )

    return AgentLaunch(
        output=Path(request["answerPath"]),
        validate=output_check(validate_trd_answer),
        outcome="The TRD and the answer, each at the path the request names.",
        accept=accept,
        add_dirs=(run.context.work,),
        files=((LABEL_REQUEST, asked),),
        hand_inputs=False,
        keep=(file_artifact(name, asked),),
    )


def _written_paths(arch: Path, request: WriteRequest, written: WriteResult) -> list[str]:
    """Name the arc42 documents one write request and its result touch.

    Returns:
        The path under the architecture root of each document the result says was changed or
        created, and of each home the request names, once, in path order.

    """
    cited: list[Citation] = [
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


@agent_step(MAINTAINER)
def maintainer(run: StepRun) -> AgentLaunch:
    """Build the session of the document maintainer the architect left running.

    The accepted result is mirrored in the matrix: each document written is set in review and its
    entry is brought up to date with its headings and lifecycle, and the entry of a document that is gone is
    removed. The session is granted the architecture root, where it writes the arc42 documents.

    Returns:
        The launch from the saved write request: the result path the request names as output.

    """
    name: str
    asked: Path
    name, asked = _saved_request(run, WRITE_REQUEST, LABEL_REQUEST)
    request: WriteRequest = checked_file(run, asked, validate_write_request)
    arch: Path = Path(read_context(run)["architectureRoot"])

    def accept(accepted: StepRun, output: Path) -> Completion:
        written: WriteResult = checked_file(accepted, output, validate_write_result)
        paths: list[str] = _written_paths(arch, request, written)
        if paths:
            accepted.tools.portfolio(accepted.inputs.stage, _sync, arch, paths)
        synced: list[JsonValue] = [*paths]
        return Completion(artifacts=(file_artifact(WRITTEN, output), value_artifact(SYNCED, synced)))

    return AgentLaunch(
        output=Path(request["resultPath"]),
        validate=output_check(validate_write_result),
        outcome="The arc42 documents written as the request states, and the result at the path it names.",
        accept=accept,
        add_dirs=(run.context.work, arch),
        files=((LABEL_REQUEST, asked),),
        hand_inputs=False,
        keep=(file_artifact(name, asked),),
    )
