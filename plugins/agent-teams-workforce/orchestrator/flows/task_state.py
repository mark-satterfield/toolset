"""Durable Task replacement facts and preservation of incoming dependency edges."""

from __future__ import annotations

import json
from pathlib import Path

from ..core.agents import strict_json
from ..core.io import write_json
from ..core.models import StepError
from ..core.tools import Tools, env_path


def snapshot(tools: Tools, epic: str, slug: str) -> tuple[object, object, list]:
    graph = tools.portfolio(
        "beadgraph",
        "load",
        env_path("ATW_CONTROL_REPO"),
        with_description=True,
        stage="decompose",
    )
    stories = [
        b
        for b in graph.beads.values()
        if b.parent == epic
        and b.kind == "story"
        and b.metadata.get("elab_key") == f"story:{slug}"
    ]
    if len(stories) != 1:
        raise StepError("input", "other", (f"expected one Story story:{slug}",))
    story = stories[0]
    return (
        graph,
        story,
        [b for b in graph.beads.values() if b.parent == story.id and b.kind == "task"],
    )


def task_facts(bead: object) -> dict:
    raw = bead.metadata.get("requirement_ids", [])
    ids = json.loads(raw) if isinstance(raw, str) and raw else raw
    return {
        "id": bead.id,
        "title": bead.title,
        "elabKey": bead.metadata.get("elab_key"),
        "description": bead.description[:2000],
        "status": bead.status,
        "requirementIds": ids or [],
    }


def replace(tools: Tools, epic: str, slug: str, work: Path, reason: str) -> dict:
    """Journal incoming edges before deletion; survive interruption after any write."""
    journal = work / f"tasks-{slug}.replacement.json"

    def attempt() -> dict:
        graph, story, tasks = snapshot(tools, epic, slug)
        deleted, kept = [], []
        for bead in tasks:
            started = tools.portfolio(
                "beadwrite", "task_started", bead, stage="decompose"
            )
            (
                kept
                if started
                or not str(bead.metadata.get("elab_key", "")).startswith("task:")
                else deleted
            ).append(task_facts(bead))
        ids = {b["id"]: b for b in deleted}
        previous = strict_json(journal) if journal.is_file() else {}
        incoming = list(previous.get("incoming", []))
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
        merged = {b["id"]: b for b in previous.get("deleted", []) + deleted}
        facts = {
            "story": story.id,
            "deleted": list(merged.values()),
            "kept": kept,
            "incoming": incoming,
            "reason": reason,
        }
        write_json(journal, facts)
        writer = tools.portfolio(
            "beadgraph", "Writer", env_path("ATW_CONTROL_REPO"), stage="decompose"
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


def repoint(tools: Tools, epic: str, slug: str, work: Path) -> list[str]:
    journal = work / f"tasks-{slug}.replacement.json"
    if not journal.is_file():
        return []

    def attempt() -> list[str]:
        graph, _, tasks = snapshot(tools, epic, slug)
        warnings = []
        for edge in strict_json(journal).get("incoming", []):
            dependent = graph.beads.get(edge["dependent"])
            if dependent is None:
                continue
            ids = set(edge["requirementIds"])
            targets = [
                b.id for b in tasks if ids.intersection(task_facts(b)["requirementIds"])
            ]
            if not targets:
                warnings.append(
                    f"No replacement for dependency {dependent.id} -> {edge['deleted']}"
                )
            for target in targets:
                if target not in dependent.blockers:
                    tools.bd(
                        ["dep", "add", dependent.id, target, "--type", "blocks"],
                        stage="task-write",
                    )
        return warnings

    return tools.operation("task-write", attempt)
