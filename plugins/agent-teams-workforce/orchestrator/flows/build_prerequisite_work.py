"""Hand missing producer work back to the elaboration of the Story that should specify it.

The build never authors producer work. When a diagnosis finds consumed output no Task builds, the
Story whose specs should hold that work is specified again: the open producer Story the diagnosis
names once its Epic is elaborated, or the Task's own Story when no open Story authorizes the work.
A producer Story whose Epic is still elaborating has no specs or Tasks yet; the consumer waits for
that elaboration instead, which is a wait and not a defect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
import beadgraph
from bead_metadata import ELABORATION_DONE, KEY_ELABORATION_STATE
from typeguard import check_type

from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, value_artifact
from orchestrator.flows import build_upstream
from orchestrator.flows.build_state import artifact_file, new_step
from orchestrator.flows.elaboration_files import control_repository

if TYPE_CHECKING:
    from pathlib import Path

ELABORATION_STAGE = "build:prerequisite-elaboration"
"""The gate that holds a consumer while its producer Story's Epic finishes elaboration."""
ELABORATION_WAIT = "prerequisiteElaborationWait"
"""The journal value naming the consumer, its diagnosis and the Epic and Story it waits for."""
AUTHORING_GAP = "Producer work-authoring gap: no open Story authorizes the missing producer work"


def prepare(run: StepRun, diagnosis: dict[str, JsonValue]) -> Completion:
    """Send missing producer work to the elaboration of the Story whose specs should hold it.

    Returns:
        The wait for the producer Story's Epic to finish elaboration, or the upstream defect that
        specifies the producer Story (or, with no open producer Story, the Task's own Story) again.

    """
    graph: beadgraph.Graph = run.tools.portfolio_read(run.step["script"], beadgraph.load, control_repository())
    story: beadgraph.Bead | None = graph.beads.get(check_type(diagnosis.get("authoringStory") or "", str))
    evidence: tuple[str, str] = (AUTHORING_GAP, check_type(diagnosis["evidence"], str))
    again: str = build_upstream.REDIAGNOSE
    params: dict[str, JsonValue] = {"again": check_type(run.params()["again"], str)}
    path: Path = artifact_file(run, "prerequisiteDiagnosis")
    epic: beadgraph.Bead | None = graph.epic_of(story.id) if story is not None else None
    if story is None or story.kind != "story" or story.closed or epic is None:
        return fingerprinted(
            run,
            build_upstream.route(
                run,
                "producer-missing",
                evidence,
                again=again,
                again_params=params,
                evidence_path=path,
            ),
        )
    if epic.metadata.get(KEY_ELABORATION_STATE) != ELABORATION_DONE:
        return _await_elaboration(run, story, epic)
    found: str = f"Producer Story {story.id} of elaborated Epic {epic.id} has no Task that builds the consumed output"
    return fingerprinted(
        run,
        build_upstream.route(
            run,
            "producer-missing",
            (found, evidence[1]),
            again=again,
            again_params=params,
            story=story.id,
            evidence_path=path,
        ),
    )


def fingerprinted(run: StepRun, routed: Completion) -> Completion:
    """Record the accepted diagnosis fingerprint with an upstream route, so the diagnosis bound holds.

    Returns:
        The route with the step's ``prerequisiteFingerprint``.

    """
    fingerprint: str = check_type(run.params()["fingerprint"], str)
    return Completion(
        artifacts=(*routed.artifacts, value_artifact("prerequisiteFingerprint", fingerprint)),
        add=routed.add,
    )


def _await_elaboration(run: StepRun, story: beadgraph.Bead, epic: beadgraph.Bead) -> Completion:
    """Hold the consumer until the producer Story's Epic has written its specs and Tasks.

    Returns:
        The accepted wait and the gate that releases the build slot while the Epic elaborates.

    """
    fingerprint: str = check_type(run.params()["fingerprint"], str)
    wait: dict[str, JsonValue] = {
        "task": str(run.bead),
        "evidencePath": str(artifact_file(run, "prerequisiteDiagnosis")),
        "fingerprint": fingerprint,
        "producers": [],
        "elaboration": {"epic": epic.id, "story": story.id},
    }
    return Completion(
        artifacts=(value_artifact(ELABORATION_WAIT, wait), value_artifact("prerequisiteFingerprint", fingerprint)),
        add=(
            StepGroup((
                new_step(
                    ELABORATION_STAGE,
                    f"Wait for Epic {epic.id} to finish elaboration",
                    {"again": check_type(run.params()["again"], str)},
                ),
            )),
        ),
    )


def elaboration_pending(wait: dict[str, JsonValue], control: Path) -> bool:
    """Check, without a session, whether the awaited Epic has not finished its elaboration.

    Args:
        wait: The accepted elaboration wait.
        control: Central tracker repository.

    Returns:
        Whether the Epic is still not marked elaborated.

    """
    epic: str = check_type(json_object(wait["elaboration"])["epic"], str)
    graph: beadgraph.Graph = beadgraph.load(control)
    found: beadgraph.Bead | None = graph.beads.get(epic)
    return found is None or found.metadata.get(KEY_ELABORATION_STATE) != ELABORATION_DONE


def elaborated(run: StepRun) -> Completion:
    """Diagnose again against the Tasks the producer Story's finished elaboration wrote.

    Returns:
        A fresh diagnosis of the now-decomposed producer work within the correction allowance.

    """
    return Completion(
        add=(
            StepGroup((
                new_step(
                    "build:prerequisites-rediagnose",
                    "Diagnose the producer work the finished elaboration wrote",
                    {"again": check_type(run.params()["again"], str)},
                ),
            )),
        ),
    )
