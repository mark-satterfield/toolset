"""Durable Task replacement facts and preservation of incoming dependency edges."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import strict_json
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import StepError
from orchestrator.core.tools import Tools, env_path


@runtime_checkable
class BeadRecord(Protocol):
    """Fields consumed from a portfolio tracker record."""

    id: str
    title: str
    kind: str
    status: str
    parent: str | None
    metadata: dict[str, JsonValue]
    blockers: tuple[str, ...]
    description: str


@runtime_checkable
class GraphRecord(Protocol):
    """Tracker graph fields consumed by task replacement."""

    beads: dict[str, BeadRecord]


def _graph(value: object) -> GraphRecord:
    graph: GraphRecord = check_type(value, GraphRecord)
    for bead in check_type(
        graph.beads,
        dict[str, BeadRecord],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ).values():
        _validate_bead(bead)
    return graph


def _validate_bead(bead: BeadRecord) -> None:
    for value in (bead.id, bead.title, bead.kind, bead.status, bead.description):
        check_type(value, str)
    check_type(bead.parent, str | None)
    check_type(bead.metadata, dict[str, JsonValue], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    check_type(bead.blockers, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def snapshot(tools: Tools, epic: str, slug: str) -> tuple[GraphRecord, BeadRecord, list[BeadRecord]]:
    """Snapshot the Story and its current tasks.

    Returns:
        Validated task state from the portfolio graph.

    Raises:
        StepError: The repository does not have exactly one matching Story.

    """
    stage = "input"
    graph = _graph(
        tools.portfolio(
            "beadgraph",
            "load",
            env_path("ATW_CONTROL_REPO"),
            with_description=True,
            stage="decompose",
        ),
    )
    stories = [
        b
        for b in graph.beads.values()
        if b.parent == epic and b.kind == "story" and b.metadata.get("elab_key") == f"story:{slug}"
    ]
    if len(stories) != 1:
        raise StepError(stage, "other", (f"expected one Story story:{slug}",))
    story = stories[0]
    return (
        graph,
        story,
        [b for b in graph.beads.values() if b.parent == story.id and b.kind == "task"],
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_facts(bead: BeadRecord) -> dict[str, JsonValue]:
    """Task facts.

    Returns:
        Validated task state from the portfolio graph.

    """
    _validate_bead(bead)
    raw = bead.metadata.get("requirement_ids", [])
    ids = json.loads(raw) if isinstance(raw, str) and raw else raw
    return json_object({
        "id": bead.id,
        "title": bead.title,
        "elabKey": bead.metadata.get("elab_key"),
        "description": bead.description[:2000],
        "status": bead.status,
        "requirementIds": ids or [],
    })


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def replace(tools: Tools, epic: str, slug: str, work: Path, reason: str) -> dict[str, JsonValue]:
    """Journal incoming edges before deletion and preserve interrupted writes.

    Returns:
        The durable replacement journal.

    """
    journal = work / f"tasks-{slug}.replacement.json"

    def attempt() -> dict[str, JsonValue]:
        graph, story, tasks = snapshot(tools, epic, slug)
        deleted: list[dict[str, JsonValue]] = []
        kept: list[dict[str, JsonValue]] = []
        for bead in tasks:
            started = tools.portfolio(
                "beadwrite",
                "task_started",
                bead,
                stage="decompose",
            )
            (kept if started or not str(bead.metadata.get("elab_key", "")).startswith("task:") else deleted).append(
                task_facts(bead),
            )
        ids = {check_type(b["id"], str): b for b in deleted}
        previous = strict_json(journal) if journal.is_file() else {}
        incoming = _objects(previous.get("incoming", []))
        for bead in graph.beads.values():
            if bead.kind == "task" and bead.parent != story.id:
                for blocker in bead.blockers:
                    if blocker in ids:
                        row = {
                            "dependent": bead.id,
                            "deleted": blocker,
                            "requirementIds": ids[blocker]["requirementIds"],
                        }
                        if row not in incoming:
                            incoming.append(row)
        merged = {check_type(b["id"], str): b for b in _objects(previous.get("deleted", [])) + deleted}
        facts = json_object({
            "story": story.id,
            "deleted": list(merged.values()),
            "kept": kept,
            "incoming": incoming,
            "reason": reason,
        })
        write_json(journal, facts)
        writer = tools.portfolio(
            "beadgraph",
            "Writer",
            env_path("ATW_CONTROL_REPO"),
            stage="decompose",
        )
        tools.portfolio(
            "beadwrite",
            "replace_tasks",
            writer,
            epic,
            slug=slug,
            reason=reason,
            stage="decompose",
        )
        return facts

    return tools.operation("decompose", attempt)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repoint(tools: Tools, epic: str, slug: str, work: Path) -> list[str]:
    """Repoint.

    Returns:
        Validated task state from the portfolio graph.

    """
    journal = work / f"tasks-{slug}.replacement.json"
    if not journal.is_file():
        return []

    def attempt() -> list[str]:
        graph, _, tasks = snapshot(tools, epic, slug)
        warnings = []
        for edge in _objects(strict_json(journal).get("incoming", [])):
            dependent = graph.beads.get(check_type(edge["dependent"], str))
            if dependent is None:
                continue
            ids = set(
                check_type(
                    edge["requirementIds"],
                    list[str],
                    collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                ),
            )
            targets = [
                b.id
                for b in tasks
                if ids.intersection(
                    check_type(
                        task_facts(b)["requirementIds"],
                        list[str],
                        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                    ),
                )
            ]
            if not targets:
                warnings.append(
                    f"No replacement for dependency {dependent.id} -> {edge['deleted']}",
                )
            for target in targets:
                if target not in dependent.blockers:
                    tools.bd(
                        ["dep", "add", dependent.id, target, "--type", "blocks"],
                        stage="task-write",
                    )
        return warnings

    return tools.operation("task-write", attempt)
