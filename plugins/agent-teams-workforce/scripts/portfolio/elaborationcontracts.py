"""Elaboration lifecycle writer contracts."""

from typing import Literal, TypedDict

# isort: split
import portfolio_path  # ruff: ignore[unused-import] - Standalone imports need the bundled plugin path before orchestrator imports.

# isort: split
from beadcontracts import PlannedWrite
from orchestrator.core.handback_contract import Refusal

__all__: list[str] = [
    "EpicValue",
    "Refusal",
    "Refused",
    "RefusedSummary",
    "ReleaseSummary",
    "Released",
    "StartSummary",
    "Started",
]


class EpicValue(TypedDict):
    """Describe the epic value wire record."""

    id: str
    title: str
    userBusinessValue: int | None
    timeCriticality: int | None
    confidence: int | None
    wsjf: str | None


class RefusedSummary(TypedDict):
    """Describe the refused summary wire record."""

    ok: Literal[False]
    refusal: str


class Refused(TypedDict):
    """Describe the refused wire record."""

    ok: Literal[False]
    refusal: Refusal
    epic: dict[str, str] | None
    summary: RefusedSummary


class StartSummary(TypedDict):
    """Describe the start summary wire record."""

    ok: Literal[True]
    epic: str
    previousState: str | None


class Started(TypedDict):
    """Describe the started wire record."""

    ok: Literal[True]
    refusal: None
    epic: EpicValue
    owner: str
    previousState: str | None
    warnings: list[str]
    dryRun: bool
    planned: list[PlannedWrite]
    summary: StartSummary


class ReleaseSummary(TypedDict):
    """Describe the release summary wire record."""

    ok: bool
    epic: str
    released: bool


class Released(TypedDict):
    """Describe the released wire record."""

    ok: bool
    epic: str
    released: bool
    owner: str | None
    state: str | None
    dryRun: bool
    planned: list[PlannedWrite]
    summary: ReleaseSummary
