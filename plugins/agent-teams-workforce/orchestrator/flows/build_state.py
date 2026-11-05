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
from step_journal_contract import PIPELINE_BUILD
from typeguard import check_type

from orchestrator.core import pipeline_steps, step_journal
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import NewStep, StepRun
from orchestrator.flows.build_sessions import latest
from orchestrator.flows.build_workspace import Workspace

PLUGIN: Final = Path(__file__).resolve().parents[2]
CONTRACTS: Final = PLUGIN / "skills" / "pipeline-contracts" / "schemas"
ARTIFACT_CONTRACTS: Final = PLUGIN / "skills" / "artifact-handoff" / "schemas"
REGRESSION: Final = PLUGIN / "scripts" / "portfolio" / "regression.py"


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
    return Workspace(
        artifact_file(run, "worktree"),
        check_type(latest(run, "branch"), str),
        check_type(latest(run, "defaultBranch"), str),
    )


def count_in_dispatch(run: StepRun, key: str) -> int:
    """Count completed occurrences within this dispatch's correction allowance.

    Returns:
        Prior occurrences started during this dispatch, not earlier dispatches.

    """
    started: str = check_type(run.context.args["buildDispatchStarted"], str)
    return sum(
        step.get("script") == key and step["status"] == "done" and step.get("started", "") >= started
        for step in step_journal.steps_in_order(run.journal())
    )
