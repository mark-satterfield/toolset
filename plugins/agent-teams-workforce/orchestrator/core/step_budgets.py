"""The time and token budgets of each step of an elaboration journal, read from ``orchestrator/step-budgets.json``.

The file is the one place the budgets are stated: a script step's time budget by its script key,
an agent step's time and token budgets by its agent, and one pair of budgets for every other
agent. A script step runs no session, so it has no token budget.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Final, NamedTuple

from typeguard import CollectionCheckStrategy, typechecked

from . import step_journal  # ruff: ignore[unused-import] - Imported for its sys.path setup.

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import Step

BUDGETS_FILE: Final[Path] = Path(__file__).resolve().parents[1] / "step-budgets.json"
"""The budget table."""


class StepBudgetsError(ValueError):
    """The budget table is not the shape its readers need."""


class Budget(NamedTuple):
    """The budgets of one step; None where the table gives it none."""

    seconds: int | None
    """Wall time, in seconds."""
    tokens: int | None
    """Tokens of the step's sessions and their helpers, as ``TokenUsage.total`` counts them."""


def _positive(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        message: str = f"{BUDGETS_FILE}: {where} is not a positive whole number: {value!r}"
        raise StepBudgetsError(message)
    return value


def _object(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        message: str = f"{BUDGETS_FILE}: {where} is not an object"
        raise StepBudgetsError(message)
    return {str(key): item for key, item in value.items()}


def _agent_budget(value: object, where: str) -> Budget:
    fields: dict[str, object] = _object(value, where)
    return Budget(
        _positive(fields.get("seconds"), f"{where}.seconds"),
        _positive(fields.get("tokens"), f"{where}.tokens"),
    )


@cache
def _budgets() -> tuple[dict[str, int], dict[str, Budget], Budget]:
    """Read the budget table once.

    A file that is not an object holding ``scripts`` (positive whole numbers of seconds),
    ``agents`` and ``otherAgents`` (each ``seconds`` and ``tokens``, positive whole numbers)
    raises ``StepBudgetsError``.

    Returns:
        The script time budgets, the agent budgets and the budgets of every other agent.

    """
    document: dict[str, object] = _object(json.loads(BUDGETS_FILE.read_text(encoding="utf-8")), "the file")
    script_table: dict[str, object] = _object(document.get("scripts"), "scripts")
    agent_table: dict[str, object] = _object(document.get("agents"), "agents")
    scripts: dict[str, int] = {key: _positive(seconds, f"scripts.{key}") for key, seconds in script_table.items()}
    agents: dict[str, Budget] = {key: _agent_budget(budget, f"agents.{key}") for key, budget in agent_table.items()}
    return scripts, agents, _agent_budget(document.get("otherAgents"), "otherAgents")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def step_budget(step: Step) -> Budget:
    """Name the budgets of a step.

    Returns:
        For a script step, the seconds the table gives its script key (None when it lists none)
        and no token budget; for an agent step, the budgets the table gives its agent, or
        ``otherAgents`` for an agent it does not list; neither for a step with neither.

    """
    scripts: dict[str, int]
    agents: dict[str, Budget]
    other: Budget
    scripts, agents, other = _budgets()
    if "script" in step:
        return Budget(scripts.get(step["script"]), None)
    if "agent" in step:
        return agents.get(step["agent"], other)
    return Budget(None, None)
