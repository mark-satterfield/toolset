"""Writer-defined records exchanged by tracker, task and design operations."""

from __future__ import annotations

from pathlib import Path
from typing import NotRequired, TypedDict

from contracts import DeltaItem, JsonObject


class UiItem(TypedDict):
    """Describe the ui item wire record."""

    id: str
    designSource: str
    buildSpec: str | None
    sections: list[str]


class UiAppendSummary(TypedDict):
    """Describe the ui append summary wire record."""

    ok: bool
    appended: int
    saved: bool


class UiAppendResult(TypedDict):
    """Describe the ui append result wire record."""

    ok: bool
    appended: int
    summary: UiAppendSummary


class Bundle(TypedDict):
    """Describe the bundle wire record."""

    path: str
    kind: str
    slug: str
    shell: JsonObject | None
    createdAt: str
    buildSpec: str
    buildSpecExists: bool
    design: str
    styles: str


class BundleListing(TypedDict):
    """Describe the bundle listing wire record."""

    packagesDir: str | None
    bundles: list[Bundle]
    superseded: list[str]
    ignored: list[str]


class DesignArtifact(TypedDict):
    """Describe the design artifact wire record."""

    kind: str
    slug: str


class BuildSelection(TypedDict):
    """Describe the build selection wire record."""

    designSource: str
    recordedSource: str
    artifact: DesignArtifact | None
    bundle: str | None
    buildSpec: str | None
    switched: bool
    blocked: str | None


class OtherTask(TypedDict):
    """Describe the other task wire record."""

    id: str
    title: str
    description: str
    status: str
    epic: str | None


class PlannedTask(TypedDict):
    """Describe the planned task wire record."""

    key: str
    elabKey: str | None
    title: str
    dependsOn: list[str]
    blockedByExternal: list[str]
    designSource: NotRequired[str]


class TaskPlanSummary(TypedDict):
    """Describe the task plan summary wire record."""

    tasks: int
    warnings: int


class TaskPlan(TypedDict):
    """Describe the task plan wire record."""

    ok: bool
    slug: str
    warnings: list[str]
    uncited: list[str]
    uncitedItems: list[PlacedItem]
    unsized: list[str]
    tasks: list[PlannedTask]
    summary: TaskPlanSummary


class TaskInputSummary(TypedDict):
    """Describe the task input summary wire record."""

    saved: bool
    unchanged: bool
    changed: int
    unverified: int


class TaskInputs(TypedDict):
    """Describe the task inputs wire record."""

    ok: bool
    saved: bool
    recorded: bool
    changedInputs: list[InputChange]
    unverified: list[str]
    unchanged: bool
    summary: TaskInputSummary


class InputChange(TypedDict):
    """Describe the input change wire record."""

    path: str
    why: str


class PlannedWrite(TypedDict):
    """Describe the planned write wire record."""

    op: str
    args: NotRequired[list[str]]
    stdin: NotRequired[str | None]
    id: NotRequired[str]
    set: NotRequired[dict[str, str]]


class ExistingTask(TypedDict):
    """Describe the existing task wire record."""

    elabKey: str
    title: str
    description: str
    status: str


class WrittenStory(TypedDict):
    """Describe the written story wire record."""

    id: str
    elabKey: str
    action: str
    title: str
    description: str
    decisionIds: list[str]


class StoryWriteSummary(TypedDict):
    """Describe the story write summary wire record."""

    id: str
    elabKey: str
    action: str
    created: int
    updated: int


class StoryWrite(TypedDict):
    """Describe the story write wire record."""

    ok: bool
    epic: str
    story: WrittenStory
    existingTasks: list[ExistingTask]
    otherEpicTasks: list[OtherTask]
    dryRun: bool
    planned: list[PlannedWrite]
    summary: StoryWriteSummary


class EdgeCounts(TypedDict):
    """Describe the edge counts wire record."""

    added: int
    removed: int
    standing: int


class WrittenTask(TypedDict):
    """Describe the written task wire record."""

    key: str
    elabKey: str | None
    id: str
    action: str
    title: str
    dependsOn: list[str]
    outsideBlockers: list[str]


class TaskWriteSummary(EdgeCounts):
    """Describe the task write summary wire record."""

    key: str
    id: str
    action: str
    warnings: int


class TaskWrite(TypedDict):
    """Describe the task write wire record."""

    ok: bool
    story: str
    task: WrittenTask
    edges: EdgeCounts
    warnings: list[str]
    dryRun: bool
    planned: list[PlannedWrite]
    summary: TaskWriteSummary


class ReplacedTask(TypedDict):
    """Describe the replaced task wire record."""

    id: str
    title: str
    elabKey: str
    status: str
    requirementIds: NotRequired[list[str]]


class ReplacementSummary(TypedDict):
    """Describe the replacement summary wire record."""

    deleted: int
    kept: int


class TaskReplacement(TypedDict):
    """Describe the task replacement wire record."""

    ok: bool
    story: str | None
    deleted: list[ReplacedTask]
    kept: list[ReplacedTask]
    reason: str
    dryRun: bool
    planned: list[PlannedWrite]
    summary: ReplacementSummary


class PlacedItem(DeltaItem, TypedDict):
    """An architecture item with its declared repository placement."""

    slug: str
    repoPath: str


TaskEdge = TypedDict(
    "TaskEdge",
    {"from": str, "to": str, "kind": NotRequired[str | None], "reason": NotRequired[str | None]},
)


class ClosureEdgeSummary(TypedDict):
    """Describe the closure edge summary wire record."""

    ok: bool
    edges: int
    warnings: list[str]


class ClosureEdges(TypedDict):
    """Describe the closure edges wire record."""

    ok: bool
    edges: list[TaskEdge]
    warnings: list[str]
    summary: ClosureEdgeSummary


class EdgePlanSummary(TypedDict):
    """Describe the edge plan summary wire record."""

    edges: int
    rejected: int
    blockers: dict[str, list[str]]
    warnings: int


class EdgePlan(TypedDict):
    """Describe the edge plan wire record."""

    ok: bool
    edges: list[TaskEdge]
    rejected: list[TaskEdge]
    blockers: dict[str, list[str]]
    warnings: list[str]
    summary: EdgePlanSummary


class TaskEdgeIdentity(TypedDict):
    """Describe the task edge identity wire record."""

    name: str
    id: str | None


class TaskEdgeSummary(TaskEdgeIdentity, EdgeCounts):
    """Describe the task edge summary wire record."""


class TaskEdgeWrite(TypedDict):
    """Describe the task edge write wire record."""

    ok: bool
    epic: str
    task: TaskEdgeIdentity
    edges: list[TaskEdge]
    warnings: list[str]
    dryRun: bool
    planned: list[PlannedWrite]
    summary: TaskEdgeSummary


class AllEdgeSummary(EdgeCounts):
    """Describe the all edge summary wire record."""

    edges: int
    rejected: int
    blockers: dict[str, list[str]]
    written: list[str]
    warnings: int


class AllEdgeWrite(TypedDict):
    """Describe the all edge write wire record."""

    ok: bool
    epic: str
    tasks: list[TaskEdgeSummary]
    warnings: list[str]
    dryRun: bool
    planned: list[PlannedWrite]
    summary: AllEdgeSummary


class CorrectionRejection(TypedDict):
    """Describe the correction rejection wire record."""

    task: NotRequired[str | None]
    score: NotRequired[str]
    edge: NotRequired[TaskEdge]
    reason: str


class TaskCorrection(TypedDict):
    """Describe the task correction wire record."""

    ok: bool
    added: list[str]
    resized: list[str]
    rejected: list[CorrectionRejection]
    dropped: list[str | None]
    trimmed: list[str | None]
    uncited: list[str]


class StoryWriteOptions(TypedDict):
    """Name the repository and source root for one Story write."""

    slug: str
    repo: str
    root: Path | None


class TaskWriteOptions(StoryWriteOptions, TypedDict):
    """Supply the local Task key and optional dependencies and design bundle."""

    key: str
    external: NotRequired[list[str] | None]
    packages_dir: NotRequired[str | None]
    missing_only: NotRequired[bool]
