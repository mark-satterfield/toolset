"""Writer-defined records exchanged by tracker, task and design operations."""

from __future__ import annotations

from pathlib import Path
from typing import NotRequired, TypedDict

import portfolio_path  # ruff: ignore[unused-import] - Puts the artifact-handoff contract scripts on sys.path.
from contracts import DeltaItem, JsonObject
from recon_contract import ArtifactKind, DesignSource


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
    kind: ArtifactKind
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

    designSource: DesignSource
    recordedSource: DesignSource
    artifact: DesignArtifact | None
    bundle: str | None
    buildSpec: str | None
    switched: bool
    blocked: str | None


class PlannedTask(TypedDict):
    """Describe the planned task wire record."""

    key: str
    elabKey: str | None
    title: str
    dependsOn: list[str]
    blockedByExternal: list[str]
    designSource: NotRequired[DesignSource]


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
    uncitedItems: list[StoryBuild]
    unsized: list[str]
    tasks: list[PlannedTask]
    summary: TaskPlanSummary


class TaskInputSummary(TypedDict):
    """Describe the task input summary wire record."""

    saved: bool
    unchanged: bool
    changed: int
    unverified: int


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


class RepointedEdge(TypedDict):
    """One `blocks` edge moved from a deleted Task onto a Task that now builds the same item."""

    dependent: str
    deleted: str
    replacement: str


class SupersededSummary(TypedDict):
    """Count what retiring a Story's superseded Tasks did."""

    deleted: int
    repointed: int
    warnings: int


class SupersededTasks(TypedDict):
    """What retiring the Task beads a Story's saved Tasks no longer name did."""

    ok: bool
    story: str
    deleted: list[ReplacedTask]
    repointed: list[RepointedEdge]
    warnings: list[str]
    dryRun: bool
    planned: list[PlannedWrite]
    summary: SupersededSummary


class StoryBuild(DeltaItem, TypedDict):
    """One thing a Story builds, with the repository whose Story builds it."""

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


class TaskWriteOptions(TypedDict):
    """Supply the local Task key, the project root and optional dependencies and design bundle."""

    key: str
    root: Path | None
    external: NotRequired[list[str] | None]
    packages_dir: NotRequired[str | None]
