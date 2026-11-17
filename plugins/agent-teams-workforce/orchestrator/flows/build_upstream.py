"""Hand a build's upstream defect back to elaboration, releasing the build slot without a failure.

Some dead ends of a build have their cause in the Task's Story's specs or Tasks, not in its code:
producer work no Task builds, a wait that closes a completion cycle, a blocking review finding
owned by the contract, and requirement source bytes that keep changing after the scope was
approved. Retrying the build repeats them. The build records the defect as the ``upstreamDefect``
value artifact and plans :data:`UPSTREAM_STEP`, a gate. While the Story's respec is pending the
build hands back at stage ``upstream-defect`` and releases its slot; the driver records the
request on the Story and its Epic's elaboration specifies the Story again, which restarts the
Task's build. When the request is cleared without that restart, the gate runs the step that met
the defect again.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Final

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
import beadgraph
from bead_metadata import (
    ELABORATION_DONE,
    KEY_ELABORATION_STATE,
    KEY_RESPEC_STATE,
    KEY_RESPEC_STATE_AT,
    RESPEC_NONE,
)
from typeguard import check_type

from orchestrator.core.handback_contract import OTHER_CAUSE, UpstreamDefect, UpstreamKind
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, value_artifact
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import control_repo
from orchestrator.flows import build_carried
from orchestrator.flows.build_sessions import latest
from orchestrator.flows.build_state import new_step

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

UPSTREAM_STEP: Final = "build:upstream-respec"
"""The gate that holds the build while its Story is specified again."""
UPSTREAM_DEFECT: Final = "upstreamDefect"
"""The value artifact holding the defect the build hands back."""
REDIAGNOSE: Final = "build:prerequisites-rediagnose"
"""The step that diagnoses the Task's producer work again."""
LEGACY_AUTHORING: Final = ("build:prerequisite-author", "build:prerequisite-authored")
"""The retired steps that authored producer work inside the build, still planned in older journals."""


def route(  # ruff: ignore[too-many-arguments] - The defect's facts and where the build resumes.
    run: StepRun,
    kind: UpstreamKind,
    evidence: Sequence[str],
    *,
    again: str,
    again_params: dict[str, JsonValue] | None = None,
    story: str | None = None,
    evidence_path: Path | None = None,
) -> Completion:
    """Record an upstream defect and plan the gate that hands the Story back to elaboration.

    Args:
        run: The step that met the defect.
        kind: What is wrong upstream.
        evidence: The lines that show the defect.
        again: The build step that runs again when the respec is cleared without a journal reset.
        again_params: That step's parameters.
        story: The Story to specify again; the Task's own Story when omitted.
        evidence_path: The file holding the full evidence, when there is one.

    Returns:
        The ``upstreamDefect`` value and the :data:`UPSTREAM_STEP` gate.

    Raises:
        StepError: The Story or its Epic is not in the tracker.

    """
    task: str = str(run.bead)
    graph: beadgraph.Graph = run.tools.portfolio_read(run.step["script"], beadgraph.load, control_repo())
    owner: str | None = story if story is not None else _parent(graph, task)
    epic: beadgraph.Bead | None = graph.epic_of(owner) if owner is not None else None
    if owner is None or epic is None:
        raise StepError(run.step["script"], OTHER_CAUSE, (f"Task {task}'s upstream Story or Epic is not tracked",))
    lines: list[str] = [line for line in evidence if line.strip()]
    fingerprint: str = hashlib.sha256(json.dumps([kind, task, owner, lines], sort_keys=True).encode()).hexdigest()
    defect: UpstreamDefect = {
        "task": task,
        "story": owner,
        "epic": epic.id,
        "kind": kind,
        "evidence": lines,
        "evidencePath": str(evidence_path) if evidence_path is not None else None,
        "fingerprint": fingerprint,
        "again": again,
        "at": beadgraph.now_iso(),
    }
    params: dict[str, JsonValue] = {"again": again, "againParams": again_params or {}}
    return Completion(
        artifacts=(value_artifact(UPSTREAM_DEFECT, json_object(dict(defect))),),
        add=(StepGroup((new_step(UPSTREAM_STEP, f"Wait for Story {owner} to be specified again", params),)),),
    )


def contract_route(
    run: StepRun,
    review: str,
    required: list[JsonValue],
    *,
    again: str,
    again_params: dict[str, JsonValue] | None = None,
) -> Completion | None:
    """Hand the Story back to elaboration when a review holds a blocking finding owned by the contract.

    Such a finding says the governing requirements contradict themselves or the design; no build
    correction removes it, so it is never carried.

    Args:
        run: The step deciding the review.
        review: The review's artifact name.
        required: The review's findings that ask for a change.
        again: The step that reviews again when the respec is cleared without a journal reset.
        again_params: That step's parameters.

    Returns:
        The ``contract-finding`` defect and its gate, or None when no such finding is open.

    """
    blocking: list[JsonValue] = build_carried.blocking_contract(required)
    if not blocking:
        return None
    lines: list[str] = build_carried.contract_evidence(review, blocking)
    return route(run, "contract-finding", lines, again=again, again_params=again_params)


def _parent(graph: beadgraph.Graph, task: str) -> str | None:
    """Read the Task's Story.

    Returns:
        The Task's parent id, or None when the Task or its parent is not tracked.

    """
    bead: beadgraph.Bead | None = graph.beads.get(task)
    return bead.parent if bead is not None and bead.parent else None


def pending(defect: Mapping[str, JsonValue], control: Path) -> bool:
    """Check, without a session, whether the Story the defect names still waits for its respec.

    The respec is pending until the driver has answered this defect and the answer is settled:
    the Story's respec state is cleared after the defect was raised, and its Epic is elaborated.

    Args:
        defect: The accepted ``upstreamDefect`` value.
        control: The central tracker repository.

    Returns:
        Whether the build must keep its slot released.

    """
    graph: beadgraph.Graph = beadgraph.load(control)
    story: beadgraph.Bead | None = graph.beads.get(check_type(defect["story"], str))
    epic: beadgraph.Bead | None = graph.beads.get(check_type(defect["epic"], str))
    if story is None or epic is None:
        return False
    if story.metadata.get(KEY_RESPEC_STATE, RESPEC_NONE) != RESPEC_NONE:
        return True
    if epic.metadata.get(KEY_ELABORATION_STATE) != ELABORATION_DONE:
        return True
    cleared: str = story.metadata.get(KEY_RESPEC_STATE_AT, "")
    raised: str = check_type(defect["at"], str)
    return not cleared or datetime.fromisoformat(cleared) <= datetime.fromisoformat(raised)


def released(run: StepRun) -> Completion:
    """Run the step that met the defect again, once the respec was cleared without a journal reset.

    Returns:
        That step, with the parameters it had.

    """
    params: Mapping[str, JsonValue] = run.params()
    again: str = check_type(params["again"], str)
    given: dict[str, JsonValue] = json_object(params.get("againParams") or {})
    return Completion(
        add=(StepGroup((new_step(again, "Run the step that met the upstream defect again", given),)),),
    )


def legacy_authoring(run: StepRun) -> Completion:
    """Route a retired producer-authoring step of an older journal to its producer Story's elaboration.

    The build no longer authors producer work; the Story whose specs should hold it is specified
    again instead.

    Returns:
        The ``producer-missing`` defect and its gate.

    """
    context: JsonValue = latest(run, "prerequisiteAuthoring")
    found: dict[str, JsonValue] = json_object(context) if isinstance(context, dict) else {}
    story: JsonValue = found.get("story")
    again: JsonValue = run.params().get("again")
    return route(
        run,
        "producer-missing",
        (f"producer work the build used to author: {json.dumps(context, sort_keys=True)}",),
        again=REDIAGNOSE,
        again_params={"again": again} if isinstance(again, str) else None,
        story=story if isinstance(story, str) and story else None,
    )
