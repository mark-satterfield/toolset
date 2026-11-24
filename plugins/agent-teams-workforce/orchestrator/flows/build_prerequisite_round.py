"""Decide what follows a prerequisite diagnosis: a fresh suite run only when something changed.

A diagnosis identifies the failing suite's inputs by a fingerprint of the Task's work tree and
the tracker's Task and Story state (:func:`inputs_fingerprint`), recorded once per diagnosis as
``prerequisiteFingerprint``. The suite runs again only after a diagnosis changed something the
failing tests depend on (:func:`continuation`): the repository's declarations corrected, a
prerequisite Task or Story finished, producer work authored, or the environment observed ready.
A diagnosis that changed nothing hands the failure, once, to the implementers with the diagnosis
as feedback (:func:`hand_off`); the same failure on unchanged inputs is never diagnosed again.
A new round is placed beside the round that started it, never inside it (:func:`round_group`).
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Final

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
import beadgraph
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.journal_steps import UNDER_CONTAINER, Completion, NewStep, StepGroup, StepRun, value_artifact
from orchestrator.core.step_findings import record_for_run
from orchestrator.core.tool_locks import control_repo
from orchestrator.flows.build_sessions import OutputContract, accepted_steps, latest, reasoned
from orchestrator.flows.build_state import CONTRACTS, new_step, workspace_of
from orchestrator.flows.build_workspace import git_operation

if TYPE_CHECKING:
    from finding_contract import FindingKind
    from step_journal_contract import Step, StepId, ValueArtifact

    from orchestrator.core.io import JsonValue

BASELINE: Final = "build:baseline"
"""The continuation that resumes the baseline setup."""
SUITE_REVIEWED: Final = "build:suite-reviewed"
"""The red-phase suite judgment a diagnosis can resume."""
FINGERPRINT: Final = "prerequisiteFingerprint"
"""The inputs fingerprint each accepted diagnosis records, once, on its ``build:prerequisites-diagnosed`` step."""
HANDOFF: Final = "prerequisiteHandoff"
"""The inputs fingerprint whose failure was handed to the implementers because its diagnosis changed nothing."""
ROUND_SCRIPTS: Final = ("build:prerequisite", "build:repository-setup", "build:environment-observe")
"""The script prefixes of the steps a prerequisite round plans; a new round goes beside them, not inside."""


def inputs_fingerprint(run: StepRun, again: str) -> tuple[str, dict[str, JsonValue], beadgraph.Graph]:
    """Identify the failing suite's inputs: the phase, the work tree and the tracker's Task and Story state.

    The suite judgment's wording is left out, so the same failure on unchanged inputs always
    yields the same fingerprint.

    Args:
        run: The current build step.
        again: The phase the diagnosis resumes.

    Returns:
        The fingerprint, the tree digest record and the tracker graph it was taken from.

    """
    tree: dict[str, JsonValue] = git_operation(
        run.tools,
        run.step["script"],
        ["hash-files", "--tree", str(workspace_of(run).tree)],
    )
    graph: beadgraph.Graph = run.tools.portfolio_read(
        run.step["script"],
        beadgraph.load,
        control_repo(),
        with_description=True,
    )
    state: list[JsonValue] = [
        {"id": bead.id, "status": bead.status, "parent": bead.parent, "blockers": list(bead.blockers)}
        for bead in graph.of_kind("task", "story")
    ]
    fingerprint: str = hashlib.sha256(
        json.dumps([again, tree["treeDigest"], state], sort_keys=True).encode(),
    ).hexdigest()
    return fingerprint, tree, graph


def _this_dispatch(run: StepRun, step: Step) -> bool:
    """Tell whether an accepted step finished, or a running ancestor started, during this dispatch.

    Returns:
        True when the step's finish time, or start time while it runs, is not before the dispatch began.

    """
    return (step.get("finished") or step.get("started") or "") >= run.context.started


def recorded(run: StepRun, name: str, fingerprint: str) -> bool:
    """Tell whether this dispatch already recorded a fingerprint under one name.

    Returns:
        True when an accepted step of this dispatch holds the value artifact ``name`` with ``fingerprint``.

    """
    return any(
        artifact["kind"] == "value" and artifact["name"] == name and artifact["value"] == fingerprint
        for step in accepted_steps(run)
        if _this_dispatch(run, step)
        for artifact in step["artifacts"]
    )


def diagnosis_fingerprint(run: StepRun) -> str:
    """Read the fingerprint of the diagnosis this step follows.

    Returns:
        The step's ``fingerprint`` parameter, or the latest accepted ``prerequisiteFingerprint``.

    """
    named: JsonValue = run.params().get("fingerprint")
    return check_type(named if named is not None else latest(run, FINGERPRINT), str)


def story_of(run: StepRun) -> str:
    """Name the consumer Task's Story, the owner of its prerequisite findings.

    Returns:
        The Task's parent, or the Task itself when the tracker names none.

    """
    graph: beadgraph.Graph = run.tools.portfolio_read(run.step["script"], beadgraph.load, control_repo())
    held: beadgraph.Bead | None = graph.beads.get(str(run.bead))
    return str(run.bead) if held is None or held.parent is None else held.parent


def _in_round(step: Step, again: str) -> bool:
    """Tell whether a step belongs to a prerequisite round resuming ``again``.

    Returns:
        True for the resumed judgment itself and every step a prerequisite round plans.

    """
    script: str = step.get("script", "")
    return script == again or script.startswith(ROUND_SCRIPTS)


def round_group(run: StepRun, steps: tuple[NewStep, ...], again: str) -> StepGroup:
    """Place a new round beside the round that started it, so rounds never nest.

    The container is the nearest ancestor of the current step outside every prerequisite round;
    it is running, since the current step is under it, and the new steps become its last children.
    An outermost round has no such ancestor, and the steps follow the current step.

    Returns:
        The group of the new round's steps.

    """
    journal = run.journal()
    holder: Step | None = step_journal.parent_step(journal, run.step["id"])
    while holder is not None and _in_round(holder, again):
        holder = step_journal.parent_step(journal, holder["id"])
    if holder is None:
        return StepGroup(steps)
    container: StepId = holder["id"]
    return StepGroup(steps, where=UNDER_CONTAINER, container=container)


def continuation(run: StepRun, again: str) -> Completion:
    """Resume the consumer's verification after a diagnosis changed something its failing tests depend on.

    Returns:
        The baseline setup again, or the original suite run and its assessment, beside the round.

    """
    step: NewStep = new_step(
        BASELINE if again == BASELINE else "build:prerequisites-suite",
        "Resume the baseline setup" if again == BASELINE else "Run and reassess the original suite",
        {"again": again},
    )
    return Completion(add=(round_group(run, (step,), again),))


def hand_off(
    run: StepRun,
    again: str,
    finding: tuple[str, FindingKind, str],
    evidence: tuple[str, ...],
    fingerprint: str,
) -> Completion:
    """Give a failure whose diagnosis changed nothing to the implementers, once, with the diagnosis as feedback.

    The finding is recorded for its owner, and the handed fingerprint is recorded so the same
    failure on unchanged inputs is never handed again. The implementers already selected correct
    it; with none selected yet, the implementation lead selects them first. In the Red phase
    (before any implementer is selected) the build continues to its own implementer selection.
    A failing baseline setup goes back to the baseline, which measures the baseline without it.

    Args:
        run: The current build step.
        again: The phase the diagnosis resumes.
        finding: The finding's owner bead, kind and detail.
        evidence: The finding's evidence.
        fingerprint: The inputs fingerprint of the diagnosis.

    Returns:
        The implementation work, or the continuation of the consumer's verification.

    """
    owner, kind, detail = finding
    stated: str = f"{detail}; the diagnosis changed nothing the failing tests depend on, so the suite is not rerun"
    diagnosis: str = str(latest(run, "prerequisiteDiagnosis"))
    record_for_run(run, owner, kind=kind, detail=stated, evidence=(*evidence, diagnosis))
    handed: tuple[ValueArtifact, ...] = (value_artifact(HANDOFF, fingerprint),)
    if again == BASELINE:
        return Completion(artifacts=handed, add=continuation(run, again).add)
    if latest(run, "implementationSelection") is not None or latest(run, "implementers") is not None:
        correct: NewStep = new_step("build:plan-code", "Correct the failing suite with the latest diagnosis")
        return Completion(artifacts=handed, add=(StepGroup((correct,)),))
    if again == SUITE_REVIEWED:
        return Completion(artifacts=handed)
    planned: Completion = reasoned(
        run,
        "implementation-lead",
        OutputContract(CONTRACTS / "build-selection.schema.json", "implementationSelection"),
        "Select the implementation specialists that correct the failing suite. Its prerequisite diagnosis changed "
        "nothing the failing tests depend on, so the failure is this Task's to correct: read the suite evidence and "
        "the latest prerequisiteDiagnosis, and select at least one specialist whose specialty covers the failing tests",
        followups=(new_step("build:plan-code", "Plan the selected code specialists and suite check"),),
    )
    return Completion(artifacts=(*planned.artifacts, *handed), add=planned.add)
