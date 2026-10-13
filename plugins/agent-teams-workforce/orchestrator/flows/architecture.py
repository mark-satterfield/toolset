"""The solutions architect's steps, and the sessions of the agents it left running.

One agent, the solutions architect, decides what the architecture should be for a PRD. The script
writes what the matrix holds for the Epic to one file, starts the agent's session, hands it the
files its definition names and records what it returns; what the architect reads, whom it asks
and in what order are its own decisions. The same launch builder serves every step that agent
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
from architecture_work_contract import (
    TRD_CHANGE_REMOVE,
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
from matrixquery import epic_view, impact_view
from matrixstore import as_entry_id, make_id, name_key, read_matrix, slug, update_matrix
from matrixsync import sync_documents
from matrixtraverse import epic_id
from matrixwrite import link, put

from orchestrator.core.io import json_object, write_json
from orchestrator.core.journal_registry import agent_step
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
from orchestrator.flows.architecture_check import check_step
from orchestrator.flows.architecture_files import (
    ARTIFACT_CHECK,
    ARTIFACT_CONCLUSION,
    ARTIFACT_REVIEW,
    ARTIFACT_TRD,
    LABEL_ANSWER,
    LABEL_CONTEXT,
    LABEL_CRITERIA,
    LABEL_CURRENT,
    LABEL_FINDINGS,
    LABEL_PRD,
    LABEL_QUESTION,
    LABEL_REQUEST,
    LABEL_RESULT,
    LABEL_RULING,
    LABEL_STATE,
    PLUGIN,
    ROLE_ARCHITECT,
    ROLE_DIAGRAMS,
    ROLE_MAINTAINER,
    ROLE_SPECIALIST,
    ROLE_STEWARD,
    ROLE_TRD_AUTHOR,
    WRITE_REQUEST,
    WRITTEN,
    ArchitectureContext,
    ArchitectureStepError,
    agents_with_role,
    checked_file,
    cited_document,
    current_architecture_path,
    document_path,
    earlier_files,
    is_finish,
    journal_file,
    matrix_file,
    output_check,
    read_context,
    result_validator,
)
from orchestrator.flows.spec_review import CRITERIA_FILE

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from architecture_work_contract import (
        ArchitectureResult,
        Citation,
        SpecialistRequest,
        TrdAnswer,
        TrdChange,
        TrdRequest,
        TrdRequirement,
        WriteRequest,
        WriteResult,
    )
    from matrix_contract import EntryId, RelationshipKind
    from matrixquery import EpicView
    from matrixstore import Matrix
    from matrixsync import DocumentsSynced
    from step_journal_contract import Artifact, Step, StepId, StepPlan

    from orchestrator.core.io import JsonValue

ARCHITECT_DESCRIPTION: Final = "Decide what the architecture should be for this PRD"
ARCHITECT_PURPOSE: Final = "One agent is responsible for the architecture this PRD needs until it is ready for review"
ARCHITECT_REF: Final = "architect"
NO_SOURCE: Final = "obligations with no source"
NO_FEATURE: Final = "requirements with no feature"
NO_STACK: Final = "entries with no stack"
SYNCED: Final = "documents synced"
CONSTRAINTS: Final = "constraints recorded"
ATTR_HEADING: Final = "heading"
ATTR_VIA: Final = "via"
ATTR_STATEMENT: Final = "statement"
REQUIREMENT_KEY_SEPARATOR: Final = "/"
HEADING_MARK: Final = "#"


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


def first_steps(opened: StepId, container: StepId, architect: str, earlier: Sequence[StepId] = ()) -> StepGroup:
    """Plan the architect's step and the check after it, under the Architecture container.

    Args:
        opened: The open-run step, whose artifacts the planned steps are handed.
        container: The Architecture container.
        architect: The agent that plays the solutions architect.
        earlier: Steps that hold files an earlier form of the pipeline produced for this PRD,
            which the architect's step is handed too.

    Returns:
        The architect's step and the check that follows it, as the container's last child steps.
        The group is left out when the container already holds a step of the architect that is
        not done.

    """
    plan: StepPlan = {
        "ref": ARCHITECT_REF,
        "description": ARCHITECT_DESCRIPTION,
        "purpose": ARCHITECT_PURPOSE,
        "agent": architect,
        "inputs": [opened, *earlier],
    }
    return StepGroup(
        (NewStep(plan), check_step([ARCHITECT_REF], corrections=0)),
        UNDER_CONTAINER,
        container,
        unless_agent=architect,
    )


def _view_ids(views: Sequence[Mapping[str, JsonValue]]) -> list[EntryId]:
    """Read the ids of entries as a matrix read prints them.

    Returns:
        The id of each entry that states one, in the order given.

    """
    return [as_entry_id(stated) for view in views for stated in (view.get("id"),) if isinstance(stated, str)]


def _reached(view: EpicView) -> list[EntryId]:
    """List what an Epic reaches: its features, the entries reached from them and their stacks.

    Returns:
        The ids, once each, in the order the closure lists them; none for a view with no closure.

    """
    if "closure" not in view:
        return []
    closure = view["closure"]
    return list(
        dict.fromkeys([
            *_view_ids([reach["feature"] for reach in closure["features"]]),
            *_view_ids([reach["entry"] for reach in closure["entries"]]),
            *_view_ids([reach["stack"] for held in closure["repositories"] for reach in held["stacks"]]),
        ]),
    )


def _current_architecture(bead: str) -> dict[str, JsonValue]:
    """Read from the matrix the current architecture that touches an Epic, with what rests on each piece.

    An Epic the matrix does not hold raises ``MatrixError``.

    Returns:
        ``epic``: what ``atw-matrix epic <bead> --closure --constraints --unlinked`` prints; and
        ``impact``: what ``atw-matrix impact --id`` prints for each feature, entry and stack in it.

    """
    matrix: Matrix = read_matrix(matrix_file())
    view: EpicView = epic_view(matrix, bead, closure=True, constraints=True, unlinked=True)
    impact: list[JsonValue] = [json_object(impact_view(matrix, reached)) for reached in _reached(view)]
    return {"epic": json_object(view), "impact": impact}


def _handed_files(run: StepRun, context: ArchitectureContext, prd: Path) -> tuple[tuple[str, Path], ...]:
    """Name the files of the architect's brief: exactly the labels its definition states.

    The file of the current architecture is written here, from the matrix as it is when the
    session starts, so the brief names the documents and headings the Epic reaches.

    Returns:
        The PRD, the criteria file, the context file, the state path and the current
        architecture; then each file an earlier form of the pipeline produced for this PRD; then
        each review and each mechanical check result the step is handed, as findings; then each
        specialist's answer and each ruling the step is handed.

    """
    current: Path = current_architecture_path(run.context.work)
    write_json(current, run.tools.portfolio(run.inputs.stage, _current_architecture, str(run.bead)))
    findings: list[Path] = [*run.inputs.files(ARTIFACT_REVIEW), *run.inputs.files(ARTIFACT_CHECK)]
    return (
        (LABEL_PRD, prd),
        (LABEL_CRITERIA, run.tools.plugin / CRITERIA_FILE),
        (LABEL_CONTEXT, journal_file(run, LABEL_CONTEXT)),
        (LABEL_STATE, Path(context["statePath"])),
        (LABEL_CURRENT, current),
        *earlier_files(run.inputs),
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
        What was recorded, with one more problem for each requirement the result says a feature
        serves that the matrix does not show as served by it, and one for each requirement the
        matrix shows with no feature that the result does not list as having none; and the
        requirements the matrix shows with no feature.

    """

    def change(matrix: Matrix) -> Recorded:
        return _record_design(matrix, bead, result)

    recorded: Recorded = update_matrix(matrix_file(), change)
    view: EpicView = epic_view(read_matrix(matrix_file()), bead)
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


@agent_step(*agents_with_role(PLUGIN, ROLE_ARCHITECT))
def architect(run: StepRun) -> AgentLaunch:
    """Build the session of any step the solutions architect performs.

    The resolved inputs say which step it is. A step that is handed findings is a correction; the
    "Finish" step below the architect's own step continues that step's session; any other step
    after one of the architect's continues the nearest earlier session the agent holds. The
    output is always the architecture result, which every step after the first updates in place.

    The session is handed files and no folder of the architecture or of the PRDs: the file of the
    current architecture names the documents and headings the Epic reaches.

    Returns:
        The launch: the result file as output, the files the definition names, and what the
        journal records when the result is accepted.

    """
    context: ArchitectureContext = read_context(run)
    prd: Path = journal_file(run, LABEL_PRD)
    finishing: bool = is_finish(run)
    holder: Step | None = None if finishing else run.session_holder()
    continues: bool = finishing or holder is not None

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
        return Completion(
            artifacts=(
                file_artifact(LABEL_RESULT, output),
                value_artifact(ARTIFACT_CONCLUSION, result["conclusion"]),
                value_artifact(NO_FEATURE, unserved),
            ),
        )

    return AgentLaunch(
        output=Path(context["resultPath"]),
        validate=result_validator,
        outcome="The architecture result of this PRD.",
        accept=accept,
        add_dirs=(run.context.work,),
        files=_handed_files(run, context, prd),
        resume_from=None if holder is None else holder["id"],
        fresh_output=not continues,
        hand_inputs=False,
    )


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


def _no_stack(bead: str) -> list[JsonValue]:
    """List the entries an Epic reaches that have no home in code, as ``epic --unlinked`` returns them.

    Returns:
        The ids under ``noStack``.

    """
    view: EpicView = epic_view(read_matrix(matrix_file()), bead, unlinked=True)
    return [*view.get("noStack", [])]


@agent_step(
    *agents_with_role(PLUGIN, ROLE_SPECIALIST),
    *agents_with_role(PLUGIN, ROLE_DIAGRAMS),
    *agents_with_role(PLUGIN, ROLE_STEWARD),
)
def specialist(run: StepRun) -> AgentLaunch:
    """Build the session of a specialist, a diagram author or the repository steward.

    The repository steward records each home it places in the matrix itself; its step records the
    entries of the Epic that have no stack afterwards.

    Returns:
        The launch from the saved request file: the answer path the request names as output.

    """
    name: str
    asked: Path
    name, asked = _saved_request(run, LABEL_REQUEST, LABEL_QUESTION)
    request: SpecialistRequest = checked_file(run, asked, validate_specialist_request)

    def accept(accepted: StepRun, output: Path) -> Completion:
        artifacts: list[Artifact] = [file_artifact(LABEL_ANSWER, output)]
        if accepted.step.get("agent") in agents_with_role(PLUGIN, ROLE_STEWARD):
            unplaced: list[JsonValue] = accepted.tools.portfolio(accepted.inputs.stage, _no_stack, str(accepted.bead))
            artifacts.append(value_artifact(NO_STACK, unplaced))
        return Completion(artifacts=tuple(artifacts))

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
    statement: str,
    applies_to: EntryId,
    problems: list[str],
    stated_in: tuple[EntryId, str] | None = None,
) -> EntryId | None:
    """Record one constraint with what it applies to and, when a document states it, where.

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
            attributes={ATTR_STATEMENT: statement},
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


def _record_constraints(matrix: Matrix, bead: str, arch: Path, request: TrdRequest, answer: TrdAnswer) -> Recorded:
    """Record the technical requirements a TRD request and its answer state, as constraints.

    Each requirement the request adds or changes, and each requirement the answer states for a
    drafted TRD, is one constraint with ``statedIn`` to the
    document heading that is its source and ``appliesTo`` to the entry it names, or to the Epic
    when it names none; a requirement the request removes loses its constraint. Each obligation
    the answer lists with no source is one constraint with no ``statedIn`` that applies to the
    Epic.

    Returns:
        The constraints recorded, and what could not be recorded.

    """
    epic: EntryId = epic_id(bead)
    problems: list[str] = []
    entries: list[EntryId | None] = []
    stated_requirements: list[TrdChange | TrdRequirement] = [*request["changes"], *answer["requirements"]]
    for change in stated_requirements:
        named: str = f"{bead} {change['id'].strip()}" if change["id"].strip() else change["statement"].strip()
        if change.get("change") == TRD_CHANGE_REMOVE:
            gone: EntryId = make_id(KIND_CONSTRAINT, slug(named))
            if matrix.find(gone) is not None:
                matrix.remove(gone)
            continue
        target: EntryId | None = (
            _held(matrix, change["appliesTo"], f"constraint {named!r} applies to", problems)
            if change["appliesTo"].strip()
            else epic
        )
        if target is not None:
            stated: tuple[EntryId, str] | None = _stated_in(matrix, arch, change["source"])
            entries.append(_constraint(matrix, named, change["statement"].strip(), target, problems, stated))
    entries.extend(
        _constraint(matrix, unsourced["obligation"].strip(), unsourced["obligation"].strip(), epic, problems)
        for unsourced in answer["noSource"]
    )
    return Recorded(entries=tuple(entry for entry in entries if entry is not None), problems=tuple(problems))


def _record_trd(bead: str, arch: Path, request: TrdRequest, answer: TrdAnswer) -> Recorded:
    """Record a TRD request and its answer in the matrix as one change.

    Returns:
        What :func:`_record_constraints` returns.

    """

    def change(matrix: Matrix) -> Recorded:
        return _record_constraints(matrix, bead, arch, request, answer)

    return update_matrix(matrix_file(), change)


@agent_step(*agents_with_role(PLUGIN, ROLE_TRD_AUTHOR))
def trd_author(run: StepRun) -> AgentLaunch:
    """Build the session of the TRD author the architect left running.

    The accepted answer is recorded in the matrix: one constraint for each technical requirement
    the request states or a drafted TRD's answer states, and for each obligation the answer lists
    with no source.

    Returns:
        The launch from the saved request file; the TRD it names is kept and updated in place.

    """
    name: str
    asked: Path
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
            request,
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
    """Bring the entries of the named documents up to date, as ``atw-matrix sync-documents --paths`` does.

    Returns:
        What the read did.

    """

    def change(matrix: Matrix) -> DocumentsSynced:
        return sync_documents(matrix, arch, paths=paths)

    return update_matrix(matrix_file(), change)


@agent_step(*agents_with_role(PLUGIN, ROLE_MAINTAINER))
def maintainer(run: StepRun) -> AgentLaunch:
    """Build the session of the document maintainer the architect left running.

    The accepted result is mirrored in the matrix: the entry of each document written is brought
    up to date with its headings and lifecycle, and the entry of a document that is gone is
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
