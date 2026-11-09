"""Reasoning work as real journal agent steps, with contracts and facts handed by file."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from itertools import starmap
from pathlib import Path
from typing import TYPE_CHECKING, Final

from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import Registry
from orchestrator.core.journal_steps import (
    UNDER_THIS,
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.journal_views import AcceptedArtifact, AcceptedView, accepted_view
from orchestrator.core.models import StepError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from step_journal_contract import Step, StepId, StepPlan

FACTS_NAME: Final = "build facts"
REQUIREMENT_NAMES: Final = ("criteria", "spec", "data model", "TRD", "story document", "tasks")
"""The accepted artifacts that state the Task's requirements and acceptance criteria."""
WORKSPACE_NAMES: Final = ("worktree", "branch", "defaultBranch")
"""The accepted artifacts that name the Story workspace."""
FINDING_NAMES: Final = ("findings", "testIssues")
"""The accepted review and test-defect artifacts a later role resolves."""
APPROVED_NAME: Final = "approved"
INLINE_LIMIT: Final = 2048
"""The largest serialized value, in bytes, written inline in the facts file; larger values are
written beside it, one file each, so a role reads only the evidence it needs."""
SAFE_NAME: Final = re.compile(r"[^A-Za-z0-9._-]+")


def view_of(run: StepRun) -> AcceptedView:
    """Return the current step's accepted view of the journal as it stands now.

    Args:
        run: The current step.

    Returns:
        The view: the latest accepted artifact of each name with its producer, built once per
        journal revision and step.

    Raises:
        TypeError: The run is invalid.

    """
    if not isinstance(run, StepRun):
        message: str = "an accepted view requires StepRun"
        raise TypeError(message)
    return accepted_view(run.journal_path, run.step["id"])


def latest(run: StepRun, name: str) -> JsonValue:
    """Read an accepted earlier artifact, including facts on a running structural ancestor.

    Args:
        run: The current step.
        name: Exact artifact name.

    Returns:
        A copy of its value or its filesystem path; None when no accepted earlier step recorded it.

    Raises:
        TypeError: The run or name is invalid.

    """
    if not isinstance(run, StepRun) or not isinstance(name, str):
        message: str = "journal artifact lookup requires StepRun and an artifact name"
        raise TypeError(message)
    return view_of(run).held(name)


def accepted_steps(run: StepRun) -> list[Step]:
    """Expose recorded facts from completed steps and running structural ancestors only.

    Args:
        run: The current build step.

    Returns:
        Copies of the earlier steps whose own completion has already recorded accepted artifacts.
        A running ancestor may still wait for its children; running siblings and future steps are
        excluded.

    """
    return view_of(run).steps()


@dataclass(frozen=True)
class Role:
    """The agent a facts file is written for, and the artifact name of its result."""

    agent: str | None = None
    result: str | None = None


def _pointer(held: AcceptedArtifact, spill: Path, place: int) -> dict[str, JsonValue]:
    """Describe one accepted artifact for a role, with its producer.

    A file or directory artifact is named by path; a small value is written inline; a larger value
    is written to its own file beside the facts file.

    Returns:
        The pointer.

    """
    pointer: dict[str, JsonValue] = {
        "name": held.name,
        "kind": held.kind,
        "producerStep": held.step,
        "producer": held.producer,
        "producerStatus": held.producer_status,
    }
    if held.path is not None:
        return {**pointer, "path": held.path}
    text: str = json.dumps(held.value, ensure_ascii=False, sort_keys=True)
    if len(text.encode("utf-8")) <= INLINE_LIMIT:
        return {**pointer, "value": held.held()}
    target: Path = spill / f"{place:03d}-{SAFE_NAME.sub('-', held.name)}.json"
    write_json(target, held.held())
    return {**pointer, "valueFile": str(target), "bytes": len(text.encode("utf-8"))}


def _approved_by_same_review(view: AcceptedView, findings: AcceptedArtifact) -> bool:
    """Tell whether the review that recorded the latest findings also approved.

    Returns:
        True when the latest ``approved`` artifact is true and came from the same step.

    """
    approved: AcceptedArtifact | None = view.artifact(APPROVED_NAME)
    return approved is not None and approved.step == findings.step and approved.value is True


def _unresolved(view: AcceptedView) -> list[JsonValue]:
    """List the latest accepted findings a later role still has to resolve.

    Returns:
        The latest review findings when the same review did not approve, and the latest reported
        test defects when there are any, each with its producing step.

    """
    found: list[JsonValue] = []
    findings: AcceptedArtifact | None = view.artifact(FINDING_NAMES[0])
    if findings is not None and findings.value and not _approved_by_same_review(view, findings):
        found.append({"name": findings.name, "producerStep": findings.step, "items": findings.held()})
    issues: AcceptedArtifact | None = view.artifact(FINDING_NAMES[1])
    if issues is not None and issues.value:
        found.append({"name": issues.name, "producerStep": issues.step, "items": issues.held()})
    return found


def _accepted_facts(run: StepRun, view: AcceptedView, role: Role) -> dict[str, JsonValue]:
    """Build the role-specific accepted evidence section of a facts file.

    Returns:
        Pointers to the requirements, the workspace, every other latest accepted artifact, the
        role's own previous result, the artifacts accepted since the role last ran, and the
        unresolved findings; with the journal revision and step they were resolved for.

    """
    spill: Path = run.context.work / "build" / str(run.step["id"]) / "accepted"
    pointers: dict[str, dict[str, JsonValue]] = {
        name: _pointer(held, spill, place) for place, (name, held) in enumerate(sorted(view.latest.items()))
    }
    fixed: set[str] = {*REQUIREMENT_NAMES, *WORKSPACE_NAMES, FACTS_NAME}
    since: StepId | None = view.last_performed_by(role.agent) if role.agent else None
    delta: list[JsonValue] = [pointers[held.name] for held in view.produced_after(since) if held.name != FACTS_NAME]
    previous: AcceptedArtifact | None = view.artifact(role.result) if role.result else None
    return {
        "journalRevision": view.revision,
        "viewStep": view.step,
        "acceptedSteps": len(view.boundary),
        "requirements": [pointers[name] for name in REQUIREMENT_NAMES if name in pointers],
        "workspace": [pointers[name] for name in WORKSPACE_NAMES if name in pointers],
        "artifacts": [pointer for name, pointer in pointers.items() if name not in fixed],
        "previousResult": pointers[previous.name] if previous is not None else None,
        "deltaSince": since,
        "delta": delta,
        "unresolvedFindings": _unresolved(view),
    }


def facts(run: StepRun, role: Role | None = None) -> Path:
    """Write the current Task facts and the role's accepted evidence for a reasoning agent.

    Args:
        run: The current journal step.
        role: The agent the facts are for and its result's artifact name; None for no role.

    Returns:
        Facts file path, unique to the current step.

    Raises:
        TypeError: The run is invalid.

    """
    if not isinstance(run, StepRun):
        message: str = "build facts require StepRun"
        raise TypeError(message)
    path: Path = run.context.work / "build" / str(run.step["id"]) / "facts.json"
    accepted: dict[str, JsonValue] = _accepted_facts(run, view_of(run), role or Role())
    write_json(
        path,
        {"arguments": run.context.args, "journal": str(run.journal_path), "step": run.step, "accepted": accepted},
    )
    return path


@dataclass(frozen=True)
class OutputContract:
    """Pair a shared output schema with its journal artifact name."""

    schema: Path
    name: str


def reasoned(
    run: StepRun,
    agent: str,
    output: OutputContract,
    request: str,
    *,
    followups: Sequence[NewStep] = (),
) -> Completion:
    """Plan bounded reasoning as an agent child, then its deterministic consumers.

    Args:
        run: The parent script step.
        agent: A roster agent selected for this subject, bare or qualified by this plugin.
        output: Shared output schema and its journal artifact name.
        request: The bounded action, with instructions supplied by the agent's skills.
        followups: Script steps that consume the result, within this parent.

    Returns:
        A completion that keeps the parent running until its children complete.

    Raises:
        ValueError: The schema does not exist or the request is blank.
        StepError: A selected agent is absent from the roster.

    """
    plugin: Path = run.agents.plugin
    schema: Path = output.schema
    agent = step_journal.agent_name(agent)
    if not (plugin / "agents" / f"{agent}.md").is_file():
        raise StepError(
            run.step.get("script", "build:selection"),
            OTHER_CAUSE,
            (f"Selected specialist is absent from the roster: {agent}",),
        )
    if not schema.is_file() or not request.strip():
        message: str = f"reasoning request has no agent, schema or action: {agent}, {schema}"
        raise ValueError(message)
    handed: Path = facts(run, Role(agent, output.name))
    plan: StepPlan = {
        "description": request,
        "purpose": run.step["purpose"],
        "agent": agent,
        "inputs": [run.step["id"]],
    }
    params: dict[str, JsonValue] = {
        "schema": str(schema),
        "resultName": output.name,
        "facts": str(handed),
        "request": request,
    }
    return Completion(
        artifacts=(file_artifact(FACTS_NAME, handed),),
        add=(StepGroup((NewStep(plan, params), *followups), where=UNDER_THIS),),
    )


def attach(registry: Registry, plugin: Path) -> None:
    """Register one launch builder for actual roster agents chosen by build reasoning.

    Args:
        registry: The flow's own registry, separate from elaboration's.
        plugin: Plugin root.

    Raises:
        TypeError: The registry or plugin has an invalid type.

    """
    if not isinstance(registry, Registry) or not isinstance(plugin, Path):
        message: str = "build agent registration requires Registry and plugin Path"
        raise TypeError(message)
    names: frozenset[str] = frozenset(path.stem for path in (plugin / "agents").glob("*.md"))
    registry.any_agent_step(names)(_launch)


def _launch(run: StepRun) -> AgentLaunch:
    """Build a session from its validated journal parameters.

    Returns:
        Launch request whose result is recorded as a file and its exact named fields.

    """
    params = run.params()
    schema: Path = Path(check_type(params["schema"], str))
    name: str = check_type(params["resultName"], str)
    handed: Path = Path(check_type(params["facts"], str))
    output: Path = run.context.work / "build" / str(run.step["id"]) / "result.json"

    def accept(_accepted_run: StepRun, path: Path) -> Completion:
        document: dict[str, JsonValue] = json_object(json.loads(path.read_text(encoding="utf-8")))
        return Completion(
            artifacts=(file_artifact(name, path), *starmap(value_artifact, document.items())),
        )

    tree: JsonValue = latest(run, "worktree")
    directories: tuple[Path, ...] = (Path(tree),) if isinstance(tree, str) else ()
    return AgentLaunch(
        output=output,
        validate=schema,
        outcome=name,
        accept=accept,
        files=(
            (FACTS_NAME, handed),
            ("build execution contract", run.agents.plugin / "skills" / "tdd-guide" / "SKILL.md"),
        ),
        request=(
            f"{check_type(params['request'], str)}. Output schema: {schema}; "
            "write exactly the shape that schema defines, and no other fields"
        ),
        add_dirs=directories,
    )
