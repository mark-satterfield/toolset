"""Writer-derived WSJF planning, judgment, and result records."""

from typing import NotRequired, TypedDict

from beadcontracts import PlannedWrite
from wsjf_types import Fault, OutsideRange, Unscored


class JudgeEntry(TypedDict):
    """Describe the judge entry wire record."""

    id: str
    reason: str
    epic: NotRequired[str | None]


class PlanSummary(TypedDict):
    """Describe the plan summary wire record."""

    includeAll: bool
    rejudge: bool
    openEpics: int
    openTasks: int
    states: dict[str, int]
    epicsToJudge: int
    tasksToJudge: int
    toAdopt: int
    only: NotRequired[list[str]]


class Plan(TypedDict):
    """Describe the plan wire record."""

    judge: dict[str, list[JudgeEntry]]
    adopt: list[str]
    fingerprints: dict[str, str]
    summary: PlanSummary


class ReferenceJob(TypedDict):
    """Describe the reference job wire record."""

    id: str
    title: str
    estimate: int | None
    low: int | None
    high: int | None
    refinedSize: int
    tasks: int


class Group(TypedDict):
    """Describe the group wire record."""

    key: str
    epic: str | None
    tasks: list[str]


class JudgeItem(TypedDict):
    """Describe the judge item wire record."""

    id: str
    title: str
    reason: str
    prdPath: NotRequired[str | None]
    sizedFromTasks: NotRequired[bool]
    description: NotRequired[str]
    epic: NotRequired[dict[str, str] | None]


class JudgeSummary(TypedDict):
    """Describe the judge summary wire record."""

    items: int
    toJudge: int
    referenceJobs: int
    ids: NotRequired[list[str]]
    groups: NotRequired[list[Group]]


class JudgeInput(TypedDict):
    """Describe the judge input wire record."""

    level: str
    items: list[JudgeItem]
    referenceJobs: list[ReferenceJob]
    summary: JudgeSummary


class RecordSummary(TypedDict):
    """Describe the record summary wire record."""

    dryRun: bool
    written: int
    adopted: int
    rejected: int
    missing: int


class Recorded(TypedDict):
    """Describe the recorded wire record."""

    dryRun: bool
    written: list[str]
    adopted: list[str]
    rejected: list[dict[str, str]]
    missing: list[str]
    planned: list[PlannedWrite]
    summary: RecordSummary


class Applied(TypedDict):
    """Describe the applied wire record."""

    id: str
    wsjf: float
    costOfDelay: int
    rroe: int
    reaches: int | None
    jobSize: int
    sizeSource: str
    sizeOutsideRange: bool | None
    written: bool


class LevelUnscored(Unscored):
    """Describe the level unscored wire record."""

    level: str


class ScoreSummary(TypedDict):
    """Describe the score summary wire record."""

    dryRun: bool
    epicsScored: int
    epicsWritten: int
    tasksScored: int
    tasksWritten: int
    unscored: int
    incomplete: int
    outsideRange: int
    epicCycle: None
    taskCycle: None


class ScoreResult(TypedDict):
    """Describe the score result wire record."""

    epics: list[Applied]
    tasks: list[Applied]
    unscored: list[LevelUnscored]
    incomplete: list[Unscored]
    sizeFaults: list[Fault]
    outsideRange: list[OutsideRange]
    cycles: dict[str, None]
    dryRun: bool
    planned: list[PlannedWrite]
    summary: ScoreSummary
