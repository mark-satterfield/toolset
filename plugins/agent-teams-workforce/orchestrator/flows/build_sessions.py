"""Reasoning work as real journal agent steps, with contracts and facts handed by file."""

from __future__ import annotations

import json
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
from orchestrator.core.models import StepError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from step_journal_contract import Artifact, Step, StepPlan

FACTS_NAME: Final = "build facts"


def latest(run: StepRun, name: str) -> JsonValue:
    """Read an accepted earlier artifact using the shared journal, including legacy build steps.

    Args:
        run: The current step.
        name: Exact artifact name.

    Returns:
        Its value or filesystem path; None when no earlier done step recorded it.

    Raises:
        TypeError: The run or name is invalid.

    """
    if not isinstance(run, StepRun) or not isinstance(name, str):
        message: str = "journal artifact lookup requires StepRun and an artifact name"
        raise TypeError(message)
    held: JsonValue = None
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        if step["id"] == run.step["id"]:
            break
        held = _accepted(step, name, held)
    return held


def _accepted(step: Step, name: str, previous: JsonValue) -> JsonValue:
    """Take the last matching artifact of a completed step.

    Returns:
        The matching value, otherwise the previous value.

    """
    if step["status"] != "done":
        return previous
    matches: list[Artifact] = [artifact for artifact in step["artifacts"] if artifact["name"] == name]
    if not matches:
        return previous
    artifact: Artifact = matches[-1]
    return artifact["value"] if artifact["kind"] == "value" else artifact["path"]


def facts(run: StepRun) -> Path:
    """Write the current Task facts and accepted outputs for a reasoning agent.

    Args:
        run: The current journal step.

    Returns:
        Facts file path, unique to the current step.

    Raises:
        TypeError: The run is invalid.

    """
    if not isinstance(run, StepRun):
        message: str = "build facts require StepRun"
        raise TypeError(message)
    path: Path = run.context.work / "build" / str(run.step["id"]) / "facts.json"
    write_json(path, {"arguments": run.context.args, "journal": str(run.journal_path), "step": run.step})
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
    handed: Path = facts(run)
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
