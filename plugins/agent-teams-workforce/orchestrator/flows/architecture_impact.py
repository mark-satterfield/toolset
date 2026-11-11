"""What a promoted architecture change reaches, and the Epics elaborated against the architecture it changed.

The promotion step plans these two steps after itself whenever it set documents effective:

1. ``architecture-impact-analyst`` is handed the promoted documents and the architect's result. It
   runs ``atw-matrix impact`` and ``atw-matrix affected`` for each changed view and rules on every
   Epic and open Task they return (``impact-rulings.schema.json``). It changes nothing.
2. A script step applies the rulings. Each other Epic ruled ``elaborated-unbuilt`` (its Stories and
   Tasks exist, and no Task is in progress or closed) is started again from the step that plans its
   Architecture steps by the driver's ``reelaborate.restart``, which checks the ruling against the tracker again, makes
   the journal change ``elabmark.py --start-at`` makes, starts again the journals of its Stories and
   Tasks a build or deploy worked on, and sets the Epic's elaboration state to ready with the cause
   ``architecture-changed``; its re-elaboration then rewrites its Stories and Tasks in place,
   matched by ``elab_key``. An ``already-built`` item's knock-on Task is recorded as proposed and
   never created. The Epic being elaborated is never restarted by its own promotion.

A restart the driver refuses (the Epic is not elaborated, a Task of it is in progress or closed, or
a run works on it now) is recorded and changes nothing. A restart that raises is recorded too, and
fails the step once every Epic was tried; running the step again restarts nothing twice, since a
restarted Epic is no longer elaborated.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
from bead_metadata import CAUSE_ARCHITECTURE_CHANGED
from typeguard import check_type

from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import driver_module
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
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
from orchestrator.flows.architecture_files import (
    LABEL_RESULT,
    ArchitectureContext,
    architecture_folder,
    read_context,
)

if TYPE_CHECKING:
    from step_journal_contract import StepPlan

ANALYST: Final = "architecture-impact-analyst"
APPLY: Final = "reelaborate.restart"
"""The script step that applies the analyst's rulings."""
PROMOTED: Final = "promoted documents"
"""The promotion step's file of the documents it set effective (``architecture_promotion.PROMOTED``)."""
RULINGS: Final = "impact rulings"
RESTARTS: Final = "re-elaborations"
KNOCK_ONS: Final = "knock-on proposals"
SCHEMA: Final = "skills/artifact-handoff/schemas/impact-rulings.schema.json"
VERDICT_UNBUILT: Final = "elaborated-unbuilt"
VERDICT_BUILT: Final = "already-built"
ID_LENGTH: Final = 8
OUTCOME_ERROR: Final = "error"


class _Restarted(Protocol):
    """What the driver's ``reelaborate.restart`` returns."""

    def record(self) -> dict[str, JsonValue]:
        """Give the outcome as this step records it."""


def impact_steps(promotion: str) -> StepGroup:
    """Plan the analyst and the step that applies its rulings, after the promotion.

    Args:
        promotion: The promotion step, whose file of promoted documents the analyst is handed.

    Returns:
        The two steps, in the order they run.

    """
    analyst: StepPlan = {
        "ref": "impact",
        "description": "Rule on every Epic and open Task the promoted architecture change reaches",
        "purpose": "No work elaborated or built against a view this Epic changed is left silently wrong",
        "agent": ANALYST,
        "inputs": [promotion],
    }
    apply: StepPlan = {
        "description": "Start again each other Epic elaborated but unbuilt against the changed architecture",
        "purpose": "An Epic whose specs and Tasks rest on changed architecture is elaborated again before it is built",
        "script": APPLY,
        "inputs": ["impact"],
    }
    return StepGroup((NewStep(analyst), NewStep(apply)))


@agent_step(ANALYST)
def analyst(run: StepRun) -> AgentLaunch:
    """Build the analyst's session: the promoted documents and the architect's result in, its rulings out.

    Returns:
        The launch.

    """
    context: ArchitectureContext = read_context(run)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(RULINGS, output),))

    return AgentLaunch(
        output=architecture_folder(run.context.work) / f"impact-{run.step['id'][:ID_LENGTH]}.json",
        validate=run.tools.plugin / SCHEMA,
        outcome="A ruling on every Epic and open Task the promoted architecture change reaches.",
        accept=accept,
        files=((PROMOTED, run.inputs.file(PROMOTED)), (LABEL_RESULT, Path(context["resultPath"]))),
        hand_inputs=False,
    )


def _rulings(path: Path) -> list[dict[str, JsonValue]]:
    """Read the analyst's rulings.

    Returns:
        Each ruling, as the analyst wrote it.

    """
    return [json_object(ruling) for ruling in check_type(strict_json(path)["rulings"], list[JsonValue])]


def restart_epic(epic: str) -> dict[str, JsonValue]:
    """Start one elaborated, unbuilt Epic again from the step that plans its Architecture steps, by the driver.

    Returns:
        What the driver did: restarted with the journals it changed, or refused with the reason;
        or the error it raised, as outcome ``error``.

    """
    operation: Callable[[str, str], _Restarted] = check_type(
        driver_module("reelaborate").restart,
        Callable[[str, str], _Restarted],
    )
    try:
        return check_type(operation(epic, CAUSE_ARCHITECTURE_CHANGED).record(), dict[str, JsonValue])
    except (RuntimeError, ValueError) as exc:
        return {"epic": epic, "outcome": OUTCOME_ERROR, "reason": f"{type(exc).__name__}: {exc}", "journals": []}


@script_step(APPLY)
def apply_rulings(run: StepRun) -> Completion:
    """Start again each other Epic the analyst ruled elaborated but unbuilt, and record the knock-on proposals.

    A restart that raised fails the step (``run.tools.failure``) once every Epic was tried, with
    each outcome in its evidence.

    Returns:
        What each restart did, and the knock-on Tasks proposed for already-built items.

    """
    rulings: list[dict[str, JsonValue]] = _rulings(run.inputs.file(RULINGS))
    epics: list[str] = list(
        dict.fromkeys(
            check_type(ruling["epicId"], str)
            for ruling in rulings
            if ruling["verdict"] == VERDICT_UNBUILT and ruling["epicId"] != str(run.bead)
        ),
    )
    restarts: list[JsonValue] = [restart_epic(epic) for epic in epics]
    proposals: list[JsonValue] = [
        {"beadId": ruling["beadId"], "epicId": ruling["epicId"], "knockOn": ruling["knockOn"]}
        for ruling in rulings
        if ruling["verdict"] == VERDICT_BUILT
    ]
    if any(json_object(record)["outcome"] == OUTCOME_ERROR for record in restarts):
        raise run.tools.failure(APPLY, OTHER_CAUSE, {RESTARTS: restarts, KNOCK_ONS: proposals})
    return Completion(artifacts=(value_artifact(RESTARTS, restarts), value_artifact(KNOCK_ONS, proposals)))
