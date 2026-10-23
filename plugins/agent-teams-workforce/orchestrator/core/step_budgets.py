"""The time budget of each step of an elaboration journal, read from ``orchestrator/step-budgets.json``.

The file is the one place the budgets are stated: a script step's budget by its script key, an
agent step's by its agent, and one budget for every other agent.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, typechecked

from . import step_journal  # ruff: ignore[unused-import] - Imported for its sys.path setup.

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import Step

BUDGETS_FILE: Final[Path] = Path(__file__).resolve().parents[1] / "step-budgets.json"
"""The budget table."""


class StepBudgetsError(ValueError):
    """The budget table is not the shape its readers need."""


def _seconds(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        message: str = f"{BUDGETS_FILE}: {where} is not a positive whole number of seconds: {value!r}"
        raise StepBudgetsError(message)
    return value


def _table(value: object, where: str) -> dict[str, int]:
    if not isinstance(value, dict):
        message: str = f"{BUDGETS_FILE}: {where} is not an object"
        raise StepBudgetsError(message)
    return {str(key): _seconds(seconds, f"{where}.{key}") for key, seconds in value.items()}


@cache
def _budgets() -> tuple[dict[str, int], dict[str, int], int]:
    """Read the budget table once.

    Returns:
        The script budgets, the agent budgets and the budget of every other agent.

    Raises:
        StepBudgetsError: The file is not an object holding ``scripts``, ``agents`` and
            ``otherAgents`` with positive whole numbers of seconds.

    """
    document: object = json.loads(BUDGETS_FILE.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        message: str = f"{BUDGETS_FILE} is not an object"
        raise StepBudgetsError(message)
    return (
        _table(document.get("scripts"), "scripts"),
        _table(document.get("agents"), "agents"),
        _seconds(document.get("otherAgents"), "otherAgents"),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def step_budget(step: Step) -> int | None:
    """Name the time budget of a step.

    Returns:
        The seconds the table gives the step's script key or agent; ``otherAgents`` for an agent
        it does not list; None for a script key it does not list and for a step with neither.

    """
    scripts: dict[str, int]
    agents: dict[str, int]
    other: int
    scripts, agents, other = _budgets()
    if "script" in step:
        return scripts.get(step["script"])
    if "agent" in step:
        return agents.get(step["agent"], other)
    return None
