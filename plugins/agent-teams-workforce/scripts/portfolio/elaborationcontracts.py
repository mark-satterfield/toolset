"""Elaboration lifecycle writer contracts."""

from typing import Literal, NotRequired, TypedDict

from beadcontracts import PlannedWrite
from scoringcontracts import Applied, LevelUnscored
from wsjf_types import Fault, OutsideRange, Unscored


class Refusal(TypedDict):
    """Describe the refusal wire record."""

    code: str
    reason: str
    owner: NotRequired[str]


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


class Scored(TypedDict):
    """Describe the scored wire record."""

    epics: list[Applied]
    tasks: list[Applied]
    unscored: list[LevelUnscored]
    incomplete: list[Unscored]
    sizeFaults: list[Fault]
    outsideRange: list[OutsideRange]
    cycles: dict[str, None]


class FinishSummary(TypedDict):
    """Describe the finish summary wire record."""

    ok: bool
    epic: str
    epicsWritten: int
    tasksScored: int
    tasksWritten: int
    unscored: int
    done: bool


class Finished(TypedDict):
    """Describe the finished wire record."""

    ok: bool
    epic: str
    score: Scored
    lifecycle: dict[str, str] | None
    dryRun: bool
    planned: list[PlannedWrite]
    summary: FinishSummary


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


class FinishOptions(TypedDict):
    """Specify lifecycle ownership and the set of scores to finish."""

    owner: str | None
    done: bool
    scope: NotRequired[str]
