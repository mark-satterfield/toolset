"""The other Epics whose own approved architecture an Epic's elaboration changed, recorded as findings.

What an Epic's architecture change reaches is assessed once, when its elaboration ends: the Story
edges step plans these two steps after itself (:func:`follow_steps`), before the step that marks
the Epic elaborated, and never a promotion, since a design-gap round promotes again within the
same elaboration.

The changed entries are taken only from a promotion this run of the Epic made: the journal's last
done promotion, when neither a done apply step after it (a journal planned when a promotion
planned these steps) nor the record an earlier end of elaboration wrote for it
(``<arch-work>/impact-assessed-<promotion step id>.json``, :func:`_record_assessment`) shows it
assessed.

The scope (:func:`impact_scope`) is the other Epics whose own work rests on an entry this Epic
changed: each Epic with a Task whose matrix elements name an entry the architect's result lists
under ``addedOrChangedElements`` (the Task builds the entry, adds to it, or builds against it, as
the ``matrix`` skill's "Who builds an entry" reads a Task's entries), with those entries. An Epic
whose requirements merely reach a changed entry by the rule of reach, through shared
infrastructure or a view that describes it, is not in it. When the scope is empty, nothing is
planned, and the promotion is recorded as assessed.

1. ``architecture-impact-analyst`` is handed the scope (``impact scope``) and the architect's
   result. It rules on each Epic of the scope and on the open Tasks of those Epics that
   ``atw-matrix affected`` returns for a changed entry (``impact-rulings.schema.json``): elaborated
   but unbuilt only when the change makes something that Epic's specs or Tasks state about the
   entry wrong. It changes nothing.
2. A script step applies the rulings. Each Epic of the scope ruled ``elaborated-unbuilt``
   (``impact-rulings.schema.json`` defines the verdicts) gets one finding of kind
   ``architecture-impact`` addressed to it (``core.findings``), naming the entries this Epic
   changed that its work rests on, with the rulings file as evidence. No Epic is started again and
   no journal is set back: the other Epic's builds carry the change through their own contract
   checks. An ``already-built`` item's knock-on Task is recorded as proposed and never created. An
   Epic outside the scope, and the Epic being elaborated, gets no finding, whatever its ruling. The
   step never fails on a ruling; when it completes, the promotion is recorded as assessed.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
import beadgraph
from matrixtasks import TaskBead, tasks_of
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.findings import record_for_run
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
    from collections.abc import Sequence

    from architecture_work_contract import ArchitectureResult
    from step_journal_contract import Journal, Step, StepPlan

ANALYST: Final = "architecture-impact-analyst"
APPLY: Final = "reelaborate.restart"
"""The script step that applies the analyst's rulings."""
SCOPE: Final = "impact scope"
"""The file of the changed entries and the other Epics whose Tasks rest on them."""
RULINGS: Final = "impact rulings"
FINDINGS: Final = "impact findings"
KNOCK_ONS: Final = "knock-on proposals"
SCHEMA: Final = "skills/artifact-handoff/schemas/impact-rulings.schema.json"
VERDICT_UNBUILT: Final = "elaborated-unbuilt"
VERDICT_BUILT: Final = "already-built"
ID_LENGTH: Final = 8
KEY_EPIC_ID: Final = "epicId"
KEY_ENTRIES: Final = "entries"
ASSESSED_PREFIX: Final = "impact-assessed-"


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


def _assessment_file(run: StepRun, promotion: str) -> Path:
    """Name the record that a promotion's change was assessed at the end of an elaboration.

    Returns:
        ``<arch-work>/impact-assessed-<promotion step id>.json``.

    """
    return architecture_folder(run.context.work) / f"{ASSESSED_PREFIX}{promotion}.json"


def _record_assessment(run: StepRun, promotion: str, scope: dict[str, list[str]]) -> None:
    """Record that a promotion's change was assessed, so a later run of this Epic does not assess it again."""
    write_json(
        _assessment_file(run, promotion),
        {"epic": str(run.bead), "promotion": promotion, "assessedBy": run.step["id"], "epics": sorted(scope)},
    )


def _unassessed_promotion(run: StepRun) -> str | None:
    """Name the promotion this run of the Epic made, whose change is not assessed yet.

    Returns:
        The id of the journal's last done promotion, in walk order, when no done apply step
        follows it (:func:`_assessed`) and no assessment of it is recorded
        (:func:`_record_assessment`); None otherwise, and when no promotion is done.

    """
    journal: Journal = run.journal()
    if _assessed(journal):
        return None
    promotions: list[Step] = [
        step
        for step in step_journal.steps_in_order(journal)
        if step["status"] == STATUS_DONE and step.get("script") == PROMOTE
    ]
    if not promotions:
        return None
    promotion: str = promotions[-1]["id"]
    return None if _assessment_file(run, promotion).is_file() else promotion


def _scope(run: StepRun) -> tuple[list[str], dict[str, list[str]]]:
    """Read the entries this run of the Epic changed and the other Epics whose Tasks rest on them.

    Returns:
        The result's ``addedOrChangedElements`` and :func:`impact_scope` on the tracker as it is
        now; both empty when no promotion of this run is left to assess (:func:`_unassessed_promotion`).

    """
    if _unassessed_promotion(run) is None:
        return [], {}
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
        The two steps, in the order they run; nothing when no promotion of this run is left to
        assess, or when no Task of another Epic rests on an entry this run changed, in which case
        the promotion is recorded as assessed.

    """
    promotion: str | None = _unassessed_promotion(run)
    if promotion is None:
        return ()
    if not _scope(run)[1]:
        _record_assessment(run, promotion, {})
        return ()
    analyst: StepPlan = {
        "ref": "impact",
        "description": "Rule on each other Epic whose own work rests on an entry this Epic changed",
        "purpose": "No work elaborated or built against an entry this Epic changed is left silently wrong",
        "agent": ANALYST,
        "inputs": [run.step["id"]],
    }
    apply: StepPlan = {
        "description": "Record a finding for each other Epic elaborated but unbuilt against the changed architecture",
        "purpose": "An Epic whose specs and Tasks rest on changed architecture is told so before it is built",
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


@script_step(APPLY)
def apply_rulings(run: StepRun) -> Completion:
    """Record a finding for each Epic of the impact scope the analyst ruled elaborated but unbuilt, and the knock-ons.

    The scope is read again from the tracker (:func:`impact_scope`), so a ruling on an Epic outside
    it records nothing. The step never fails on a ruling; the promotion is recorded as assessed.

    Returns:
        The findings recorded, and the knock-on Tasks proposed for already-built items.

    """
    rulings_file: Path = run.inputs.file(RULINGS)
    rulings: list[dict[str, JsonValue]] = _rulings(rulings_file)
    promotion: str | None = _unassessed_promotion(run)
    scope: dict[str, list[str]] = _scope(run)[1]
    epics: list[str] = list(
        dict.fromkeys(
            check_type(ruling[KEY_EPIC_ID], str)
            for ruling in rulings
            if ruling["verdict"] == VERDICT_UNBUILT and ruling[KEY_EPIC_ID] in scope
        ),
    )
    findings: list[JsonValue] = []
    epic: str
    for epic in epics:
        detail: str = f"{run.bead} changed {', '.join(scope[epic])}, which this Epic's specs or Tasks rest on"
        record_for_run(run, epic, kind="architecture-impact", detail=detail, evidence=(str(rulings_file),))
        findings.append({KEY_EPIC_ID: epic, KEY_ENTRIES: list(scope[epic]), "detail": detail})
    proposals: list[JsonValue] = [
        {"beadId": ruling["beadId"], KEY_EPIC_ID: ruling[KEY_EPIC_ID], "knockOn": ruling["knockOn"]}
        for ruling in rulings
        if ruling["verdict"] == VERDICT_BUILT
    ]
    if promotion is not None:
        _record_assessment(run, promotion, scope)
    return Completion(artifacts=(value_artifact(FINDINGS, findings), value_artifact(KNOCK_ONS, proposals)))
