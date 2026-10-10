"""Durable Task replacement facts and preservation of incoming dependency edges."""

from __future__ import annotations

import json
from pathlib import Path

import beadgraph
import beadwrite
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import strict_json
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import StepError
from orchestrator.core.tools import Tools, env_path

_ARGUMENT_ERROR: str = "Arguments violate the task_state input contract"


def _objects(value: JsonValue) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def snapshot(tools: Tools, epic: str, slug: str) -> tuple[beadgraph.Graph, beadgraph.Bead, list[beadgraph.Bead]]:
    """Snapshot the Story and its current tasks.

    Returns:
        Validated task state from the portfolio graph.

    Raises:
        TypeError: An argument violates the declared input contract.
        StepError: The repository does not have exactly one matching Story.

    """
    if not (isinstance(tools, Tools)) or not (isinstance(epic, str)) or not (isinstance(slug, str)):
        raise TypeError(_ARGUMENT_ERROR)
    stage: str = "input"
    graph: beadgraph.Graph = tools.portfolio(
        "decompose",
        beadgraph.load,
        env_path("ATW_CONTROL_REPO"),
        with_description=True,
    )
    stories: list[beadgraph.Bead] = [
        b
        for b in graph.beads.values()
        if b.parent == epic and b.kind == "story" and b.metadata.get("elab_key") == f"story:{slug}"
    ]
    if len(stories) != 1:
        raise StepError(stage, "other", (f"expected one Story story:{slug}",))
    story: beadgraph.Bead = stories[0]
    return (
        graph,
        story,
        [b for b in graph.beads.values() if b.parent == story.id and b.kind == "task"],
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_facts(bead: beadgraph.Bead) -> dict[str, JsonValue]:
    """Task facts.

    Returns:
        Validated task state from the portfolio graph.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(bead, beadgraph.Bead)):
        raise TypeError(_ARGUMENT_ERROR)
    raw: str | list[str] = bead.metadata.get("requirement_ids", [])
    decoded: object = json.loads(raw) if isinstance(raw, str) and raw else raw
    ids: list[str] = check_type(decoded, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(tools, Tools))
        or not (isinstance(epic, str))
        or not (isinstance(slug, str))
        or not (isinstance(work, Path))
        or not (isinstance(reason, str))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    journal: Path = work / f"tasks-{slug}.replacement.json"

    def attempt() -> dict[str, JsonValue]:
        graph: beadgraph.Graph
        story: beadgraph.Bead
        tasks: list[beadgraph.Bead]
        bead: beadgraph.Bead
        blocker: str
        graph, story, tasks = snapshot(tools, epic, slug)
        deleted: list[dict[str, JsonValue]] = []
        kept: list[dict[str, JsonValue]] = []
        for bead in tasks:
            started: bool = tools.portfolio("decompose", beadwrite.task_started, bead)
            (kept if started or not str(bead.metadata.get("elab_key", "")).startswith("task:") else deleted).append(
                task_facts(bead),
            )
        ids: dict[str, dict[str, JsonValue]] = {check_type(b["id"], str): b for b in deleted}
        previous: dict[str, JsonValue] = strict_json(journal) if journal.is_file() else {}
        incoming: list[dict[str, JsonValue]] = _objects(previous.get("incoming", []))
        for bead in graph.beads.values():
            if bead.kind == "task" and bead.parent != story.id:
                for blocker in bead.blockers:
                    if blocker in ids:
                        row: dict[str, int | float | str | list[JsonValue] | dict[str, JsonValue] | None] = {
                            "dependent": bead.id,
                            "deleted": blocker,
                            "requirementIds": ids[blocker]["requirementIds"],
                        }
                        if row not in incoming:
                            incoming.append(row)
        merged: dict[str, dict[str, JsonValue]] = {
            check_type(b["id"], str): b for b in _objects(previous.get("deleted", [])) + deleted
        }
        facts: dict[str, JsonValue] = json_object({
            "story": story.id,
            "deleted": list(merged.values()),
            "kept": kept,
            "incoming": incoming,
            "reason": reason,
        })
        write_json(journal, facts)
        writer: beadgraph.Writer = tools.portfolio("decompose", beadgraph.Writer, env_path("ATW_CONTROL_REPO"))
        tools.portfolio("decompose", beadwrite.replace_tasks, writer, epic, slug=slug, reason=reason)
        return facts

    return tools.operation("decompose", attempt)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repoint(tools: Tools, epic: str, slug: str, work: Path) -> list[str]:
    """Repoint.

    Returns:
        Validated task state from the portfolio graph.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(tools, Tools))
        or not (isinstance(epic, str))
        or not (isinstance(slug, str))
        or not (isinstance(work, Path))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    journal: Path = work / f"tasks-{slug}.replacement.json"
    if not journal.is_file():
        return []

    def attempt() -> list[str]:
        ids: set[str]
        graph: beadgraph.Graph
        tasks: list[beadgraph.Bead]
        edge: dict[str, JsonValue]
        target: str
        graph, _, tasks = snapshot(tools, epic, slug)
        warnings: list[str] = []
        for edge in _objects(strict_json(journal).get("incoming", [])):
            dependent: beadgraph.Bead | None = graph.beads.get(check_type(edge["dependent"], str))
            if dependent is None:
                continue
            ids = set(
                check_type(
                    edge["requirementIds"],
                    list[str],
                    collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                ),
            )
            targets: list[str] = [
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
