"""Shared build artifacts, step plans and correction accounting."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

from driver_surface_types import (
    BUILD_CORRECTION_DEFAULT,
    BUILD_CORRECTION_ENV,
    BUILT_CORRECTION_DEFAULT,
    BUILT_CORRECTION_ENV,
    REGRESSION_CORRECTION_DEFAULT,
    REGRESSION_CORRECTION_ENV,
)
from step_journal_contract import PIPELINE_BUILD, Step, StepId
from typeguard import check_type

from orchestrator.core import pipeline_steps
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import NewStep, StepRun
from orchestrator.core.journal_views import AcceptedView, JournalIndex, index_journal
from orchestrator.flows.build_sessions import latest, view_of
from orchestrator.flows.build_workspace import Workspace

PLUGIN: Final = Path(__file__).resolve().parents[2]
CONTRACTS: Final = PLUGIN / "skills" / "pipeline-contracts" / "schemas"
ARTIFACT_CONTRACTS: Final = PLUGIN / "skills" / "artifact-handoff" / "schemas"
REGRESSION: Final = PLUGIN / "scripts" / "portfolio" / "regression.py"
TEST_LEAD: Final = "test-design-lead"
"""The agent that selects the test specialists a correction needs."""
TEST_SELECTION: Final = "testSelection"
"""The artifact name of the test design lead's accepted selection."""


def build_rounds() -> int:
    """Read the configured build correction allowance.

    Returns:
        A positive round count.

    """
    return _rounds(BUILD_CORRECTION_ENV, BUILD_CORRECTION_DEFAULT)


def regression_rounds() -> int:
    """Read the configured regression correction allowance.

    Returns:
        A positive round count.

    """
    return _rounds(REGRESSION_CORRECTION_ENV, REGRESSION_CORRECTION_DEFAULT)


def built_rounds() -> int:
    """Read the configured built-architecture correction allowance.

    Returns:
        A positive round count.

    """
    return _rounds(BUILT_CORRECTION_ENV, BUILT_CORRECTION_DEFAULT)


def _rounds(name: str, default: str) -> int:
    """Resolve a positive configurable correction bound.

    Returns:
        The configured positive integer.

    Raises:
        ValueError: Configuration is not a positive integer.

    """
    count: int = int(os.environ.get(name, default))
    if count < 1:
        message: str = f"{name} must be a positive integer"
        raise ValueError(message)
    return count


def new_step(key: str, description: str, params: dict[str, JsonValue] | None = None) -> NewStep:
    """Plan a build step from its canonical definition.

    Returns:
        The canonical step with this occurrence's reason and parameters.

    """
    return NewStep(pipeline_steps.step_plan(PIPELINE_BUILD, key, params, purpose=description), params)


def argument_object(run: StepRun, key: str) -> dict[str, JsonValue]:
    """Read a dispatch object at its JSON boundary.

    Returns:
        The checked object.

    """
    return json_object(run.context.args[key])


def artifact_file(run: StepRun, name: str) -> Path:
    """Read an accepted file or directory artifact.

    Returns:
        Its recorded path.

    """
    return Path(check_type(latest(run, name), str))


def artifact_document(run: StepRun, name: str) -> dict[str, JsonValue]:
    """Read an accepted result previously validated against its shared schema.

    Returns:
        The checked object.

    """
    return json_object(json.loads(artifact_file(run, name).read_text(encoding="utf-8")))


def workspace_of(run: StepRun) -> Workspace:
    """Read the verified Story workspace from accepted journal artifacts.

    Returns:
        Its worktree, actual branch and repository default branch.

    """
    view: AcceptedView = view_of(run)
    return Workspace(
        Path(check_type(view.held("worktree"), str)),
        check_type(view.held("branch"), str),
        check_type(view.held("defaultBranch"), str),
    )


def _correction_outcome(step: Step, outcome: str | None) -> bool:
    """Recognize a completed correction outcome, excluding successful suite and review results.

    Returns:
        Whether the step records the requested correction evidence.

    """
    matching = [artifact for artifact in step["artifacts"] if artifact["name"] == outcome]
    if not matching:
        return False
    artifact = matching[-1]
    value: JsonValue = check_type(
        json.loads(Path(artifact["path"]).read_text(encoding="utf-8"))
        if artifact["kind"] == "file"
        else artifact.get("value"),
        JsonValue,
    )
    if isinstance(value, dict) and "exitCode" in value:
        return isinstance(value["exitCode"], int) and value["exitCode"] != 0
    if isinstance(value, dict) and "approved" in value:
        findings: list[JsonValue] = check_type(value.get("findings", []), list[JsonValue])
        return value["approved"] is not True or any(json_object(item).get("severity") != "note" for item in findings)
    return bool(value)


def count_in_dispatch(run: StepRun, key: str, outcome: str | None = None) -> int:
    """Count accepted correction outcomes across resumes of the Task journal.

    Returns:
        Steps with the named completed outcome, including an immediate agent child's
        accepted outcome. Without an outcome name, only finished steps count.

    """
    accepted: list[Step] = view_of(run).steps()
    index: JournalIndex = index_journal(run.journal())
    producers: set[StepId] = {step["id"] for step in accepted if _correction_outcome(step, outcome)}
    agent_parents: set[StepId | None] = {
        index.parent[step["id"]] for step in accepted if step.get("agent") and step["id"] in producers
    }
    return sum(
        step.get("script") == key
        and ((outcome is None and step["status"] == "done") or step["id"] in producers or step["id"] in agent_parents)
        for step in accepted
    )
