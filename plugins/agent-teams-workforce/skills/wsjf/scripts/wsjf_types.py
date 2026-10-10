"""Records consumed and produced by the WSJF arithmetic implementation."""

from __future__ import annotations

from typing import NotRequired, TypedDict

Number = int | float | str | None


class Item(TypedDict):
    """Describe the item wire record."""

    id: str
    userBusinessValue: NotRequired[Number]
    timeCriticality: NotRequired[Number]
    confidence: NotRequired[Number]
    riskReductionOpportunityEnablement: NotRequired[Number]
    reaches: NotRequired[Number]
    childSizes: NotRequired[list[Number]]
    jobSize: NotRequired[Number]
    sizeLow: NotRequired[Number]
    sizeHigh: NotRequired[Number]
    sizeConfidence: NotRequired[Number]
    valueFrom: NotRequired[str | None]


class Payload(TypedDict, total=False):
    """Describe the payload wire record."""

    level: str
    items: list[Item]
    edges: list[dict[str, str]]


class LevelBase(TypedDict):
    """Describe the level base wire record."""

    rubric: str
    rroeBands: tuple[tuple[int, int], ...]
    rroeTop: int
    decompositionFaultAbove: int | None
    rollup: bool
    reachKey: str


class Level(LevelBase):
    """Describe the level wire record."""

    level: str


class SizeFault(TypedDict):
    """Describe the size fault wire record."""

    supplied: int | float
    rung: int
    aboveScale: bool


class Estimate(TypedDict, total=False):
    """Describe the estimate wire record."""

    sizeEstimate: int | float
    sizeLow: int | float
    sizeHigh: int | float
    sizeConfidence: int


class Size(Estimate):
    """Describe the size wire record."""

    jobSize: int
    sizeSource: str
    sizeFault: NotRequired[SizeFault]
    sizeOutsideRange: NotRequired[bool]


class Rroe(TypedDict):
    """Describe the rroe wire record."""

    riskReductionOpportunityEnablement: int
    reaches: int | None
    rroeSource: str


class Reason(TypedDict):
    """Describe the reason wire record."""

    reason: str


class Unscored(Reason):
    """Describe the unscored wire record."""

    id: str


class Fault(SizeFault):
    """Describe the fault wire record."""

    id: str


class OutsideRange(TypedDict):
    """Describe the outside range wire record."""

    id: str
    size: int
    estimate: int | float | None
    low: int | float
    high: int | float


class ScoreData(Size, Rroe):
    """Describe the score data wire record."""

    id: str
    userBusinessValue: int
    timeCriticality: int
    valueFrom: str | None
    costOfDelay: int
    wsjf: float
    confidence: int | None


class ScoreRow(ScoreData):
    """Describe the score row wire record."""

    metadata: dict[str, str]


class ScoreResult(TypedDict):
    """Describe the score result wire record."""

    ok: bool
    level: str
    scores: list[ScoreRow]
    unscored: list[Unscored]
    sizeFaults: list[Fault]
    outsideRange: list[OutsideRange]
    cycle: None


class ReachRow(TypedDict):
    """Describe the reach row wire record."""

    id: str
    reaches: int
    riskReductionOpportunityEnablement: int


class ReachResult(TypedDict):
    """Describe the reach result wire record."""

    ok: bool
    level: str
    reaches: list[ReachRow]
    cycle: None


class BandRow(TypedDict):
    """Describe the band row wire record."""

    upTo: int
    rroe: int


class RroeScale(TypedDict):
    """Describe the rroe scale wire record."""

    bands: list[BandRow]
    above: int


class JobScale(TypedDict):
    """Describe the job scale wire record."""

    scale: str
    rungs: list[int]
    continuesUpward: bool
    decompositionFaultAbove: int | None


class Scales(TypedDict):
    """Describe the scales wire record."""

    level: str
    rubric: str
    rroe: RroeScale
    jobSize: JobScale
    childSizeRollup: str | None
    reachMetadataKey: str
