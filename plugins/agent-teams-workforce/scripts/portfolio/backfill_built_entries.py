#!/usr/bin/env python3
"""Backfill ``builds_entries`` on the Tasks written before the build-ownership rule, and report duplicate builds.

A Task elaboration writes from 7.71.91 records the matrix entries it builds under
``builds_entries``. A Task written earlier has none, and ``matrixtasks.built_entries`` reads it
from its ``matrix_elements`` instead, which names only what the architect named. This script
gives such a Task its entries at component level: the ``matrixId`` of each item its
``requirement_ids`` cite, from the elements file (``span-elements.json``) its Epic's span step
recorded in the Epic's step journal; a Task whose Epic has no readable elements file keeps the
``matrix_elements`` reading.

Two commands, both reading beads once:

- ``plan`` (the default): print the ``builds_entries`` each open or blocked Task without the key
  would be given; ``--apply`` writes them. A closed Task is never written: closed issues are
  history, and the ``matrix_elements`` reading already answers for it.
- ``report``: every entry that Tasks of two or more Epics build (with the backfilled entries),
  each with its owner Epic, the owner's Tasks, and the other Epics' Tasks split into unstarted,
  started and closed. That is the work list of the cleanup that restarts those Epics.

Usage:
  backfill_built_entries.py [plan|report] --runs <workflow-runs directory> [--control <repo>] [--apply]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

import portfolio_path  # ruff: ignore[unused-import] - Puts the plugin's contract modules on the path first.

# isort: split
import beadgraph
import buildowner
from bead_metadata import KEY_BUILDS_ENTRIES, KEY_REQUIREMENT_IDS
from contracts import BuiltBy
from matrixtasks import TaskBead, tasks_of

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


JOURNALS: Final = "step-journals"
JOURNAL_SUFFIX: Final = ".step-journal.json"
ELEMENTS_ARTIFACT: Final = "elements"
WRITABLE: Final[frozenset[str]] = frozenset({"open", "blocked"})
"""The statuses of a Task this script may write."""
COMMAND_PLAN: Final = "plan"
COMMAND_REPORT: Final = "report"


class Backfill(TypedDict):
    """One Task's planned ``builds_entries`` and where they came from."""

    task: str
    epic: str
    entries: list[str]
    source: str
    """``elements`` (its Epic's span items) or ``matrix_elements`` (no readable elements file)."""


class Duplicate(TypedDict):
    """One entry Tasks of two or more Epics build."""

    entry: str
    ownerEpic: str | None
    builtBy: list[BuiltBy]
    unstarted: list[BuiltBy]
    started: list[BuiltBy]
    closed: list[BuiltBy]


def _json_file(path: Path) -> object:
    """Read one JSON file.

    Returns:
        Its parsed content; None when it is missing or is not JSON.

    """
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        sys.stderr.write(f"skipping {path}: {error}\n")
        return None


def _elements_file(runs: Path, epic: str) -> Path | None:
    """Find the elements file the span step of an Epic recorded in its step journal.

    Returns:
        The last recorded ``elements`` file artifact, or None when the journal or the artifact is missing.

    """
    journal: object = _json_file(runs / JOURNALS / f"{epic}{JOURNAL_SUFFIX}")
    if not isinstance(journal, dict):
        return None
    found: list[str] = []
    pending: list[object] = list(journal.get("steps") or [])
    while pending:
        step: object = pending.pop(0)
        if not isinstance(step, dict):
            continue
        pending.extend(step.get("steps") or [])
        found.extend(
            str(artifact["path"])
            for artifact in step.get("artifacts") or []
            if isinstance(artifact, dict) and artifact.get("name") == ELEMENTS_ARTIFACT and artifact.get("path")
        )
    return Path(found[-1]) if found else None


def _item_entries(path: Path | None) -> dict[str, str]:
    """Map each item of an elements file to the matrix id of the entry it builds.

    Returns:
        Item id -> matrix id; empty when the file is missing or unreadable.

    """
    if path is None:
        return {}
    document: object = _json_file(path)
    items: object = document.get("items") if isinstance(document, dict) else None
    if not isinstance(items, list):
        return {}
    return {
        str(item["id"]): str(item["matrixId"])
        for item in items
        if isinstance(item, dict) and item.get("id") and item.get("matrixId")
    }


def _cited(bead: beadgraph.Bead) -> list[str]:
    """Read the item ids a Task cites (its ``requirement_ids``).

    Returns:
        The ids; empty when the key is missing or is not a JSON array of strings.

    """
    raw: str = bead.metadata.get(KEY_REQUIREMENT_IDS, "")
    try:
        decoded: object = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []
    return [str(item) for item in decoded] if isinstance(decoded, list) else []


def plan_backfill(graph: beadgraph.Graph, tasks: Sequence[TaskBead], runs: Path) -> list[Backfill]:
    """Plan ``builds_entries`` for every Task under an Epic that carries no such key.

    Args:
        graph: The beads graph.
        tasks: Its Tasks (``matrixtasks.tasks_of``).
        runs: The workflow-runs directory whose ``step-journals`` hold each Epic's journal.

    Returns:
        One row per such Task, closed ones included (the report reads them), in Task id order.

    """
    entries_of: dict[str, dict[str, str]] = {}
    rows: list[Backfill] = []
    for task in tasks:
        bead: beadgraph.Bead = graph.beads[task.id]
        if task.epic is None or KEY_BUILDS_ENTRIES in bead.metadata:
            continue
        if task.epic not in entries_of:
            entries_of[task.epic] = _item_entries(_elements_file(runs, task.epic))
        mapped: dict[str, str] = entries_of[task.epic]
        cited: list[str] = [mapped[item] for item in _cited(bead) if item in mapped]
        rows.append({
            "task": task.id,
            "epic": task.epic,
            "entries": list(dict.fromkeys(cited)) if cited else list(task.builds),
            "source": "elements" if cited else "matrix_elements",
        })
    return rows


def with_backfill(tasks: Sequence[TaskBead], rows: Sequence[Backfill]) -> list[TaskBead]:
    """Give each Task the entries the backfill plans for it.

    Returns:
        The Tasks, each with ``builds`` from its planned row when it has one.

    """
    planned: dict[str, list[str]] = {row["task"]: row["entries"] for row in rows}
    return [dataclasses.replace(task, builds=tuple(planned[task.id])) if task.id in planned else task for task in tasks]


def duplicates(tasks: Sequence[TaskBead]) -> list[Duplicate]:
    """List every entry that Tasks of two or more Epics build, with its owner and the others by state.

    Returns:
        One row per such entry, in entry id order.

    """
    index: buildowner.BuilderIndex = buildowner.builders(tasks)
    rows: list[Duplicate] = []
    for entry in sorted(index):
        found: list[buildowner.Builder] = index[entry]
        owner: str | None = buildowner.owner_epic(found)
        others: list[buildowner.Builder] = [builder for builder in found if builder.epic != owner]
        if not others:
            continue
        rows.append({
            "entry": entry,
            "ownerEpic": owner,
            "builtBy": [builder.row() for builder in found if builder.epic == owner],
            "unstarted": [builder.row() for builder in others if not builder.started],
            "started": [builder.row() for builder in others if builder.started and builder.status != "closed"],
            "closed": [builder.row() for builder in others if builder.status == "closed"],
        })
    return rows


def apply_backfill(rows: Sequence[Backfill], statuses: Mapping[str, str], control: Path | None) -> list[str]:
    """Write ``builds_entries`` onto each open or blocked Task the backfill planned.

    Returns:
        The Tasks written.

    """
    written: list[str] = []
    for row in rows:
        if statuses.get(row["task"]) not in WRITABLE:
            continue
        beadgraph.write_metadata(row["task"], {KEY_BUILDS_ENTRIES: json.dumps(row["entries"])}, control)
        written.append(row["task"])
    return written


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line.

    Returns:
        The arguments.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", default=COMMAND_PLAN, choices=(COMMAND_PLAN, COMMAND_REPORT))
    parser.add_argument("--runs", type=Path, required=True, help="the workflow-runs directory")
    parser.add_argument("--control", type=Path, help="the control repository; default: the driver's")
    parser.add_argument("--apply", action="store_true", help="plan only: write the planned builds_entries")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Plan, apply or report, and print one JSON object.

    Returns:
        The exit status.

    """
    args: argparse.Namespace = _arguments(argv)
    graph: beadgraph.Graph = beadgraph.load(args.control)
    tasks: list[TaskBead] = tasks_of(graph)
    rows: list[Backfill] = plan_backfill(graph, tasks, args.runs)
    statuses: dict[str, str] = {task.id: task.status for task in tasks}
    out: dict[str, object]
    if args.command == COMMAND_REPORT:
        found: list[Duplicate] = duplicates(with_backfill(tasks, rows))
        out = {"command": COMMAND_REPORT, "entries": len(found), "duplicates": found}
    else:
        writable: list[Backfill] = [row for row in rows if statuses.get(row["task"]) in WRITABLE]
        out = {"command": COMMAND_PLAN, "planned": writable, "applied": False}
        if args.apply:
            out["written"] = apply_backfill(writable, statuses, args.control)
            out["applied"] = True
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
