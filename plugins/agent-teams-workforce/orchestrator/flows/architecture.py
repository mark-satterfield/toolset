"""The solutions architect's steps, and the sessions of the agents it left running.

One agent, the solutions architect, establishes the architecture a PRD needs. The script starts
its session, hands it the files its definition names and records what it returns; what the
architect reads, whom it asks and in what order are its own decisions. The same launch builder
serves every step that agent performs: the first, its "Finish" after an interruption, a
correction after findings or after the mechanical check, and a competing design the lead orders.

An agent the architect starts runs inside the architect's session. Only one it left running when
its session stopped is launched here, from the request file the architect saved for it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import (
    validate_architecture_result,
    validate_specialist_answer,
    validate_specialist_request,
    validate_trd_answer,
    validate_trd_request,
    validate_write_request,
    validate_write_result,
)

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
    ArchitectureContext,
    ArchitectureStepError,
    agents_with_role,
    checked_file,
    earlier_files,
    is_finish,
    journal_file,
    output_check,
    read_context,
    result_validator,
)
from orchestrator.flows.spec_review import CRITERIA_FILE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from architecture_work_contract import (
        ArchitectureResult,
        SpecialistRequest,
        TrdAnswer,
        TrdRequest,
        WriteRequest,
    )
    from step_journal_contract import Step, StepId, StepPlan

    from orchestrator.core.io import JsonValue

ARCHITECT_DESCRIPTION: Final = "Establish the state of the architecture for this PRD"
ARCHITECT_PURPOSE: Final = "One agent is responsible for the architecture this PRD needs until it is ready for review"
ARCHITECT_REQUEST: Final = "Establish the state of the architecture for this PRD."
ARCHITECT_REF: Final = "architect"
WRITE_REQUEST: Final = "write request"
WRITTEN: Final = "what was written"
NO_SOURCE: Final = "obligations with no source"


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


def _handed_files(run: StepRun, context: ArchitectureContext, prd: Path) -> tuple[tuple[str, Path], ...]:
    """Name the files of the architect's brief: exactly the labels its definition states.

    Returns:
        The PRD, the criteria file, the context file and the state path; then each file an
        earlier form of the pipeline produced for this PRD; then each review and each mechanical
        check result the step is handed, as findings; then each specialist's answer and each
        ruling the step is handed.

    """
    findings: list[Path] = [*run.inputs.files(ARTIFACT_REVIEW), *run.inputs.files(ARTIFACT_CHECK)]
    return (
        (LABEL_PRD, prd),
        (LABEL_CRITERIA, run.tools.plugin / CRITERIA_FILE),
        (LABEL_CONTEXT, journal_file(run, LABEL_CONTEXT)),
        (LABEL_STATE, Path(context["statePath"])),
        *earlier_files(run.inputs),
        *((LABEL_FINDINGS, path) for path in dict.fromkeys(findings)),
        *((LABEL_ANSWER, path) for path in dict.fromkeys(run.inputs.files(LABEL_ANSWER))),
        *((LABEL_RULING, path) for path in dict.fromkeys(run.inputs.files(LABEL_RULING))),
    )


@agent_step(*agents_with_role(PLUGIN, ROLE_ARCHITECT))
def architect(run: StepRun) -> AgentLaunch:
    """Build the session of any step the solutions architect performs.

    The resolved inputs say which step it is. A step that is handed findings is a correction; the
    "Finish" step below the architect's own step continues that step's session; any other step
    after one of the architect's continues the nearest earlier session the agent holds. The
    output is always the architecture result, which every step after the first updates in place.

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
        return Completion(
            artifacts=(file_artifact(LABEL_RESULT, output), value_artifact(ARTIFACT_CONCLUSION, result["conclusion"])),
        )

    return AgentLaunch(
        output=Path(context["resultPath"]),
        validate=result_validator,
        outcome="The architecture result of this PRD.",
        accept=accept,
        add_dirs=(run.context.work, Path(context["architectureRoot"]), prd.parent),
        files=_handed_files(run, context, prd),
        request=None if continues else ARCHITECT_REQUEST,
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


def _helper_dirs(run: StepRun) -> tuple[Path, ...]:
    """Name the directories a helper's session may read.

    Returns:
        The Epic's work directory, the architecture root and the PRD's folder.

    """
    context: ArchitectureContext = read_context(run)
    return (run.context.work, Path(context["architectureRoot"]), Path(context["prdPath"]).parent)


@agent_step(
    *agents_with_role(PLUGIN, ROLE_SPECIALIST),
    *agents_with_role(PLUGIN, ROLE_DIAGRAMS),
    *agents_with_role(PLUGIN, ROLE_STEWARD),
)
def specialist(run: StepRun) -> AgentLaunch:
    """Build the session of a specialist, a diagram author or the repository steward.

    Returns:
        The launch from the saved request file: the answer path the request names as output.

    """
    name: str
    asked: Path
    name, asked = _saved_request(run, LABEL_REQUEST, LABEL_QUESTION)
    request: SpecialistRequest = checked_file(run, asked, validate_specialist_request)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(name, asked), file_artifact(LABEL_ANSWER, output)))

    return AgentLaunch(
        output=Path(request["answerPath"]),
        validate=output_check(validate_specialist_answer),
        outcome="The answer to the request, at the path the request names.",
        accept=accept,
        add_dirs=_helper_dirs(run),
        files=((LABEL_REQUEST, asked),),
        hand_inputs=False,
    )


@agent_step(*agents_with_role(PLUGIN, ROLE_TRD_AUTHOR))
def trd_author(run: StepRun) -> AgentLaunch:
    """Build the session of the TRD author the architect left running.

    Returns:
        The launch from the saved request file; the TRD it names is kept and updated in place.

    """
    name: str
    asked: Path
    name, asked = _saved_request(run, LABEL_REQUEST)
    request: TrdRequest = checked_file(run, asked, validate_trd_request)

    def accept(accepted: StepRun, output: Path) -> Completion:
        answer: TrdAnswer = checked_file(accepted, output, validate_trd_answer)
        unsourced: list[JsonValue] = [entry["obligation"] for entry in answer["noSource"]]
        return Completion(
            artifacts=(
                file_artifact(name, asked),
                file_artifact(ARTIFACT_TRD, Path(request["trdPath"])),
                file_artifact(LABEL_ANSWER, output),
                value_artifact(NO_SOURCE, unsourced),
            ),
        )

    return AgentLaunch(
        output=Path(request["answerPath"]),
        validate=output_check(validate_trd_answer),
        outcome="The TRD and the answer, each at the path the request names.",
        accept=accept,
        add_dirs=_helper_dirs(run),
        files=((LABEL_REQUEST, asked),),
        hand_inputs=False,
    )


@agent_step(*agents_with_role(PLUGIN, ROLE_MAINTAINER))
def maintainer(run: StepRun) -> AgentLaunch:
    """Build the session of the document maintainer the architect left running.

    Returns:
        The launch from the saved write request: the result path the request names as output.

    """
    name: str
    asked: Path
    name, asked = _saved_request(run, WRITE_REQUEST, LABEL_REQUEST)
    request: WriteRequest = checked_file(run, asked, validate_write_request)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(name, asked), file_artifact(WRITTEN, output)))

    return AgentLaunch(
        output=Path(request["resultPath"]),
        validate=output_check(validate_write_result),
        outcome="The arc42 documents written as the request states, and the result at the path it names.",
        accept=accept,
        add_dirs=_helper_dirs(run),
        files=((LABEL_REQUEST, asked),),
        hand_inputs=False,
    )
