"""The sessions that route what the solutions architect could not settle and rule on what stays disputed.

The check step plans the lead when the architect's result lists a matter it could not settle; the
lead decides what each matter needs and adds the steps for it under its own step. The decider
rules only where the lead sends a matter to it. Nothing reviews the architect's work: the
architect reviews and approves its own architecture against the criteria.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import (
    ROUTING_REJECT,
    validate_architecture_question,
    validate_architecture_ruling,
    validate_lead_routing,
)
from matrix_contract import KIND_DISAGREEMENT, REL_DISPUTES
from matrixstore import read_matrix

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.journal_registry import agent_step
from orchestrator.core.journal_steps import (
    AgentLaunch,
    Completion,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import (
    ARCHITECTURE_FOLDER,
    ARTIFACT_RESOLVED,
    DECIDER,
    HUMAN_ACTION_STAGE,
    LABEL_QUESTION,
    LABEL_RESULT,
    LABEL_RULING,
    LEAD,
    ArchitectureContext,
    ArchitectureStepError,
    checked_file,
    cited_document,
    is_finish,
    matrix_file,
    output_check,
    read_context,
)

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureRuling, LeadRouting, UnsettledMatter
    from matrixstore import Matrix
    from step_journal_contract import Step

    from orchestrator.core.io import JsonValue

ROUTING: Final = "routing"
STANDS: Final = "stands"
SETTLED: Final = "disagreements settled"
ATTR_STANDS: Final = "stands"
ATTR_HEADING: Final = "heading"
ID_LENGTH: Final = 8
"""How much of a step id names a file the step's session writes."""


@agent_step(LEAD)
def lead(run: StepRun) -> AgentLaunch:
    """Build the session of the lead: its routing of the unsettled matters, or its "Finish" after the steps it added.

    The lead adds the steps its routing calls for under its own step, so its session normally
    ends with child steps and nothing is accepted here. A routing that rejects every item needs
    no step. Launched for "Finish", the lead either records that every item is resolved or adds
    the steps that remain. The specialists it asks for an opinion are its own choice, made from
    the find-specialists skill's catalog, so nothing is listed for it.

    Returns:
        The launch, with exactly the input labels the lead's definition names.

    """
    context: ArchitectureContext = read_context(run)
    folder: Path = run.context.work / ARCHITECTURE_FOLDER
    finishing: bool = is_finish(run)
    owner: Step | None = step_journal.parent_step(run.journal(), run.step["id"]) if finishing else run.step
    owner_id: str = run.step["id"] if owner is None else owner["id"]

    def accept(accepted: StepRun, output: Path) -> Completion:
        routing: LeadRouting = checked_file(accepted, output, validate_lead_routing)
        waiting: list[str] = [item["item"] for item in routing["items"] if item["routing"] != ROUTING_REJECT]
        if finishing and not accepted.step["artifacts"]:
            raise ArchitectureStepError(
                accepted,
                "the lead neither recorded that every item is resolved nor added a step for what remains",
            )
        if not finishing and waiting:
            raise ArchitectureStepError(accepted, f"the routing sends {waiting} to further work and adds no step")
        return Completion(artifacts=(file_artifact(ROUTING, output), value_artifact(ARTIFACT_RESOLVED, True)))

    return AgentLaunch(
        output=folder / f"routing-{owner_id[:ID_LENGTH]}.json",
        validate=output_check(validate_lead_routing),
        outcome="The routing of every item.",
        accept=accept,
        add_dirs=(run.context.work, Path(context["architectureRoot"])),
        files=((LABEL_RESULT, Path(context["resultPath"])),),
        fresh_output=not finishing,
        hand_inputs=False,
    )


def _disagreements(arch: Path, matter: UnsettledMatter) -> tuple[list[JsonValue], list[str]]:
    """Read back from the matrix the disagreements a question to the decider is about.

    A disagreement is one the question is about when the positions' evidence cites every document
    heading the disagreement disputes.

    Returns:
        The ids of those disagreements whose ``stands`` is set, and of those whose ``stands`` is
        unset.

    """
    matrix: Matrix = read_matrix(matrix_file())
    cited: set[tuple[str | None, str]] = {
        (cited_document(arch, citation["source"]), citation["heading"].strip())
        for position in matter["positions"]
        for citation in position["evidence"]
    }
    settled: list[JsonValue] = []
    unset: list[str] = []
    for entry in matrix.entries((KIND_DISAGREEMENT,)):
        disputed: set[tuple[str | None, str]] = {
            (statement.end, str(statement.attributes.get(ATTR_HEADING, "")).strip())
            for statement in matrix.outgoing(entry.id, (REL_DISPUTES,))
        }
        if disputed and disputed <= cited:
            if entry.attributes.get(ATTR_STANDS):
                settled.append(entry.id)
            else:
                unset.append(entry.id)
    return settled, unset


@agent_step(DECIDER)
def decider(run: StepRun) -> AgentLaunch:
    """Build the session of the decider: one question file in, one ruling out.

    The decider records its ruling in the matrix itself, with ``atw-matrix settle``, as the
    settlement of the matter. The accept step reads each disagreement the question is about back
    from the matrix and fails the step when its ``stands`` is unset. A ruling that raises an owner
    concern fails the step with the concerns as its evidence.

    Returns:
        The launch, with the question as its only input.

    Raises:
        ArchitectureStepError: The step is handed no question file.

    """
    context: ArchitectureContext = read_context(run)
    question: Path | None = run.inputs.optional_file(LABEL_QUESTION)
    if question is None:
        raise ArchitectureStepError(run, f"its inputs hold no file artifact named {LABEL_QUESTION!r}")
    matter: UnsettledMatter = checked_file(run, question, validate_architecture_question)
    arch: Path = Path(context["architectureRoot"])

    def accept(accepted: StepRun, output: Path) -> Completion:
        ruling: ArchitectureRuling = checked_file(accepted, output, validate_architecture_ruling)
        concerns: tuple[str, ...] = tuple(f"{entry['kind']}: {entry['concern']}" for entry in ruling["ownerConcerns"])
        if concerns:
            raise StepError(HUMAN_ACTION_STAGE, OTHER_CAUSE, concerns)
        settled: list[JsonValue]
        unset: list[str]
        settled, unset = accepted.tools.portfolio(accepted.inputs.stage, _disagreements, arch, matter)
        if unset:
            raise ArchitectureStepError(
                accepted,
                "the matrix holds no ruling for a disagreement the question is about: its `stands` is unset; "
                "the ruling is recorded with atw-matrix settle",
                *unset,
            )
        return Completion(
            artifacts=(
                file_artifact(LABEL_RULING, output),
                value_artifact(STANDS, ruling["stands"]),
                value_artifact(SETTLED, settled),
            ),
        )

    return AgentLaunch(
        output=run.context.work / ARCHITECTURE_FOLDER / f"ruling-{run.step['id'][:ID_LENGTH]}.json",
        validate=output_check(validate_architecture_ruling),
        outcome="The ruling on the question.",
        accept=accept,
        add_dirs=(run.context.work, Path(context["architectureRoot"])),
        files=((LABEL_QUESTION, question),),
        hand_inputs=False,
    )
