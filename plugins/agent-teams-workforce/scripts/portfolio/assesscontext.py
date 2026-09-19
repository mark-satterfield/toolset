#!/usr/bin/env python3
"""The material one item's dependency assessment reads: one Epic, or one Task.

An Epic's assessing session reads the Epic's own PRD in full, and finds the other PRDs it
needs by searching a corpus: every open Epic's PRD as its own file, and an index naming
each one's title, elaboration state and section headings.

A Task created outside elaboration is assessed the same way over the open Tasks: every
open Task as its own file, and an index naming each one's title, Epic, repository and
status.

Either session also needs every edge already standing between the item and another open
bead of its level, whichever way it points, with the reason recorded for it, because it
must keep or withdraw each owned one with a reason that answers the recorded one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import beadgraph
from edgeset import SequencingError, scope_defect, standing_edges
from prds import ELAB_KEY, write_index, write_prds

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Bead, Graph


def assess_context(graph: Graph, epic: str, out_dir: Path) -> dict:
    """Write the PRD corpus and index, and return the Epic and its standing edges.

    Args:
        graph: The tracker graph, read with descriptions.
        epic: The Epic to be assessed.
        out_dir: The directory to write into: `prd/<id>.md` per open Epic, and
            `index.md`.

    Returns:
        `epic` (`{id, title, fingerprint, elaborationState, prdPath}`), `standing` (every
        edge between the Epic and another open Epic, from `edgeset.standing_edges`),
        `corpusDir`, `indexPath`, and a `summary` of counts.

    Raises:
        SequencingError: `epic` is not an open Epic.
    """
    epics = [b for b in graph.of_kind("epic") if not b.closed]
    bead = next((b for b in epics if b.id == epic), None)
    if bead is None:
        msg = f"{epic} is not an open Epic"
        raise SequencingError(msg)
    corpus = out_dir / "prd"
    index = out_dir / "index.md"
    paths = write_prds(epics, corpus)
    write_index(graph, epics, paths, index)
    prints = beadgraph.fingerprints(graph.records)
    standing = standing_edges(graph, epic)
    owned = sum(1 for s in standing if s["owned"])
    return {
        "epic": {
            "id": bead.id,
            "title": bead.title,
            "fingerprint": prints.get(bead.id, ""),
            "elaborationState": bead.metadata.get(ELAB_KEY),
            "prdPath": paths[bead.id],
        },
        "standing": standing,
        "corpusDir": str(corpus),
        "indexPath": str(index),
        "summary": {
            "epic": bead.id,
            "openEpics": len(epics),
            "standing": len(standing),
            "owned": owned,
            "handMade": len(standing) - owned,
        },
    }


#: Metadata key naming the repository a Task is built in.
REPO_KEY = "repoPath"


def write_tasks(graph: Graph, tasks: list[Bead], task_dir: Path) -> dict[str, str]:
    """Write each Task to its own file: `# <id> — <title>`, then its description.

    Args:
        graph: The tracker graph the Tasks were read from.
        tasks: The Tasks.
        task_dir: The directory to write into; created when absent.

    Returns:
        Task id -> the file holding it.
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for task in tasks:
        bead = graph.beads.get(task.id, task)
        path = task_dir / f"{bead.id}.md"
        path.write_text(
            f"# {bead.id} — {bead.title}\n\n{bead.description}\n", encoding="utf-8"
        )
        paths[bead.id] = str(path)
    return paths


def write_task_index(
    graph: Graph, tasks: list[Bead], paths: dict[str, str], path: Path
) -> None:
    """Write the index of the open Tasks.

    One heading line, `# Open Tasks`, then one line per Task:
    `- <id> | <title> | Epic: <epic or none> | repo: <repoPath or unset> |
    status: <status> | file: <path>`.

    Args:
        graph: The tracker graph the Tasks were read from.
        tasks: The Tasks to list, in the order to list them.
        paths: Task id -> the file holding it, from `write_tasks`.
        path: The index file to write.
    """
    lines = ["# Open Tasks"]
    for task in tasks:
        epic = graph.epic_of(task.id)
        repo = task.metadata.get(REPO_KEY) or "unset"
        lines.append(
            f"- {task.id} | {task.title} | Epic: {epic.id if epic else 'none'} | "
            f"repo: {repo} | status: {task.status} | file: {paths.get(task.id, '')}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def task_context(graph: Graph, task: str, out_dir: Path) -> dict:
    """Write the open-Task corpus and index, and return the Task and its standing edges.

    Args:
        graph: The tracker graph, read with descriptions.
        task: The Task to be assessed: open, and not written by elaboration.
        out_dir: The directory to write into: `task/<id>.md` per open Task, and
            `index.md`.

    Returns:
        `task` (`{id, title, fingerprint, epic, repoPath, path}`), `standing` (every edge
        between the Task and another open Task, from `edgeset.standing_edges`),
        `corpusDir`, `indexPath`, and a `summary` of counts.

    Raises:
        SequencingError: `task` is not an open Task, or elaboration wrote it.
    """
    defect = scope_defect(graph, task, "task")
    if defect:
        raise SequencingError(defect)
    tasks = [b for b in graph.of_kind("task") if not b.closed]
    bead = graph.beads[task]
    corpus = out_dir / "task"
    index = out_dir / "index.md"
    paths = write_tasks(graph, tasks, corpus)
    write_task_index(graph, tasks, paths, index)
    prints = beadgraph.fingerprints(graph.records)
    standing = standing_edges(graph, task, "task")
    owned = sum(1 for s in standing if s["owned"])
    epic = graph.epic_of(task)
    return {
        "task": {
            "id": bead.id,
            "title": bead.title,
            "fingerprint": prints.get(bead.id, ""),
            "epic": epic.id if epic else None,
            "repoPath": bead.metadata.get(REPO_KEY),
            "path": paths[bead.id],
        },
        "standing": standing,
        "corpusDir": str(corpus),
        "indexPath": str(index),
        "summary": {
            "task": bead.id,
            "openTasks": len(tasks),
            "standing": len(standing),
            "owned": owned,
            "handMade": len(standing) - owned,
        },
    }
