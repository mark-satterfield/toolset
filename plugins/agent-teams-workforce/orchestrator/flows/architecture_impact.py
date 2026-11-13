"""The other Epics whose own approved architecture an Epic's elaboration changed, and their restart.

What an Epic's architecture change reaches is assessed once, when its elaboration ends: the Story
edges step plans these two steps after itself (:func:`follow_steps`), before the step that marks
the Epic elaborated, and never a promotion, since a design-gap round promotes again within the
same elaboration.

The scope (:func:`impact_scope`) is the other Epics whose own work rests on an entry this Epic
changed: each Epic with a Task whose matrix elements name an entry the architect's result lists
under ``addedOrChangedElements`` (the Task builds the entry, adds to it, or builds against it, as
the ``matrix`` skill's "Who builds an entry" reads a Task's entries), with those entries. An Epic
whose requirements merely reach a changed entry by the rule of reach, through shared
infrastructure or a view that describes it, is not in it. When the scope is empty, nothing is
planned.

1. ``architecture-impact-analyst`` is handed the scope (``impact scope``) and the architect's
   result. It rules on each Epic of the scope and on the open Tasks of those Epics that
   ``atw-matrix affected`` returns for a changed entry (``impact-rulings.schema.json``): elaborated
   but unbuilt only when the change makes something that Epic's specs or Tasks state about the
   entry wrong. It changes nothing.
2. A script step applies the rulings. Each Epic of the scope ruled ``elaborated-unbuilt``
   (``impact-rulings.schema.json`` defines the verdicts) is started again from the step that plans
   its Architecture steps by the driver's ``reelaborate.restart``, which owns how a restart is
   checked and made. An ``already-built`` item's knock-on Task is recorded as proposed and never
   created. An Epic outside the scope, and the Epic being elaborated, is never restarted, whatever
   its ruling.

A restart the driver refuses (the Epic is not elaborated, a build has started on it, or a run works
on it now) is recorded and changes nothing. A restart that raises is recorded too, and
fails the step once every Epic was tried; running the step again restarts nothing twice, since a
restarted Epic is no longer elaborated.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
import beadgraph
from bead_metadata import CAUSE_ARCHITECTURE_CHANGED
from matrixtasks import TaskBead, tasks_of
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import driver_module
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
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
    PROMOTE,
    ArchitectureContext,
    architecture_folder,
    read_context,
    read_result,
)
from orchestrator.flows.elaboration_files import control_repository
from orchestrator.flows.repo_scoping import story_build_entries

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import STATUS_DONE

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureResult
    from step_journal_contract import Journal, StepPlan

ANALYST: Final = "architecture-impact-analyst"
APPLY: Final = "reelaborate.restart"
"""The script step that applies the analyst's rulings."""
SCOPE: Final = "impact scope"
"""The file of the changed entries and the other Epics whose Tasks rest on them."""
RULINGS: Final = "impact rulings"
RESTARTS: Final = "re-elaborations"
KNOCK_ONS: Final = "knock-on proposals"
SCHEMA: Final = "skills/artifact-handoff/schemas/impact-rulings.schema.json"
VERDICT_UNBUILT: Final = "elaborated-unbuilt"
VERDICT_BUILT: Final = "already-built"
ID_LENGTH: Final = 8
OUTCOME_ERROR: Final = "error"
KEY_EPIC_ID: Final = "epicId"
KEY_ENTRIES: Final = "entries"


class _Restarted(Protocol):
    """What the driver's ``reelaborate.restart`` returns."""

    def record(self) -> dict[str, JsonValue]:
        """Give the outcome as this step records it."""


def impact_scope(tasks: Sequence[TaskBead], bead: str, changed: Sequence[str]) -> dict[str, list[str]]:
    """Map each other Epic whose Tasks rest on an entry this Epic changed to those entries.

    Args:
        tasks: Every Task of the tracker (``matrixtasks.tasks_of``).
        bead: The Epic being elaborated.
        changed: The ids the architect's result lists under ``addedOrChangedElements``.

    Returns:
        Each other Epic's bead id with the changed entries a Task of it names among its matrix
        elements or the entries it builds, in id order; empty when no Task of another Epic names one.

    """
    ids: set[str] = set(story_build_entries(changed))
    pairs: set[tuple[str, str]] = {
        (task.epic, entry)
        for task in tasks
        if task.epic is not None and task.epic != bead
        for entry in ids & {*task.elements, *task.builds}
    }
    scope: defaultdict[str, list[str]] = defaultdict(list)
    epic: str
    entry: str
    for epic, entry in sorted(pairs):
        scope[epic].append(entry)
    return dict(scope)


def _scope(run: StepRun) -> tuple[list[str], dict[str, list[str]]]:
    """Read the changed entries of the Epic's result and the other Epics whose Tasks rest on them.

    Returns:
        The result's ``addedOrChangedElements``, and :func:`impact_scope` on the tracker as it is now.

    """
    result: ArchitectureResult = read_result(run, read_context(run))
    graph: beadgraph.Graph = run.tools.portfolio_read(run.inputs.stage, beadgraph.load, control_repository())
    tasks: list[TaskBead] = run.tools.portfolio_read(run.inputs.stage, tasks_of, graph)
    changed: list[str] = list(result["addedOrChangedElements"])
    return changed, impact_scope(tasks, str(run.bead), changed)


def _assessed(journal: Journal) -> bool:
    """Tell whether the architecture as last promoted was already assessed by an applied impact step.

    An Epic whose journal planned the impact steps after a promotion holds them in its Architecture
    container: a done apply step after the last done promotion has assessed what this Epic changed.

    Returns:
        True when such a step is done after the last done promotion, in walk order.

    """
    done: list[str] = [
        step.get("script", "")
        for step in step_journal.steps_in_order(journal)
        if step["status"] == STATUS_DONE and step.get("script") in {PROMOTE, APPLY}
    ]
    return bool(done) and done[-1] == APPLY


def follow_steps(run: StepRun) -> tuple[StepGroup, ...]:
    """Plan the analyst and the step that applies its rulings after the step that runs now, when they are due.

    Returns:
        The two steps, in the order they run; nothing when this Epic's last promoted architecture
        was already assessed, or when no Task of another Epic rests on an entry this Epic changed.

    """
    if _assessed(run.journal()) or not _scope(run)[1]:
        return ()
    analyst: StepPlan = {
        "ref": "impact",
        "description": "Rule on each other Epic whose own work rests on an entry this Epic changed",
        "purpose": "No work elaborated or built against an entry this Epic changed is left silently wrong",
        "agent": ANALYST,
        "inputs": [run.step["id"]],
    }
    apply: StepPlan = {
        "description": "Start again each other Epic elaborated but unbuilt against the changed architecture",
        "purpose": "An Epic whose specs and Tasks rest on changed architecture is elaborated again before it is built",
        "script": APPLY,
        "inputs": ["impact"],
    }
    return (StepGroup((NewStep(analyst), NewStep(apply))),)


@agent_step(ANALYST)
def analyst(run: StepRun) -> AgentLaunch:
    """Build the analyst's session: the impact scope and the architect's result in, its rulings out.

    Returns:
        The launch.

    """
    context: ArchitectureContext = read_context(run)
    changed: list[str]
    scope: dict[str, list[str]]
    changed, scope = _scope(run)
    folder: Path = architecture_folder(run.context.work)
    path: Path = folder / f"impact-scope-{run.step['id'][:ID_LENGTH]}.json"
    write_json(
        path,
        {
            "epic": str(run.bead),
            "changedEntries": changed,
            "epics": [{KEY_EPIC_ID: epic, KEY_ENTRIES: list(entries)} for epic, entries in scope.items()],
        },
    )

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(RULINGS, output), file_artifact(SCOPE, path)))

    return AgentLaunch(
        output=folder / f"impact-{run.step['id'][:ID_LENGTH]}.json",
        validate=run.tools.plugin / SCHEMA,
        outcome="A ruling on each Epic of the impact scope and on each open Task of it a changed entry affects.",
        accept=accept,
        files=((SCOPE, path), (LABEL_RESULT, Path(context["resultPath"]))),
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
    """Start again each Epic of the impact scope the analyst ruled elaborated but unbuilt, and record the knock-ons.

    The scope is read again from the tracker (:func:`impact_scope`), so a ruling on an Epic outside
    it restarts nothing. A restart that raised fails the step, as the module states, through
    ``run.tools.failure``.

    Returns:
        What each restart did, and the knock-on Tasks proposed for already-built items.

    """
    rulings: list[dict[str, JsonValue]] = _rulings(run.inputs.file(RULINGS))
    scope: dict[str, list[str]] = _scope(run)[1]
    epics: list[str] = list(
        dict.fromkeys(
            check_type(ruling[KEY_EPIC_ID], str)
            for ruling in rulings
            if ruling["verdict"] == VERDICT_UNBUILT and ruling[KEY_EPIC_ID] in scope
        ),
    )
    restarts: list[JsonValue] = [restart_epic(epic) for epic in epics]
    proposals: list[JsonValue] = [
        {"beadId": ruling["beadId"], KEY_EPIC_ID: ruling[KEY_EPIC_ID], "knockOn": ruling["knockOn"]}
        for ruling in rulings
        if ruling["verdict"] == VERDICT_BUILT
    ]
    if any(json_object(record)["outcome"] == OUTCOME_ERROR for record in restarts):
        raise run.tools.failure(APPLY, OTHER_CAUSE, {RESTARTS: restarts, KNOCK_ONS: proposals})
    return Completion(artifacts=(value_artifact(RESTARTS, restarts), value_artifact(KNOCK_ONS, proposals)))
