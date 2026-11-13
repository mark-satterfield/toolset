#!/usr/bin/env python3
"""Remove the Task ``blocks`` edges that order nothing real, once, and the Story edges they made.

Overlap with another Epic's planned work, a ``built`` prerequisite on another repository's
Story, and an edge a longer path implies order no build. The Task writer adds cross-Epic edges
and never removes them, so edges of those kinds already in the tracker stay until this script
removes them. It does, in this order, for every live Task edge (both ends open) whose dependent
Task has not started (``task_started``):

- ``C1``: same repository, another Story, the blocker named in the dependent's
  ``blockedByExternal`` and nothing else attributes the edge (no prerequisite row, no
  task-dependency-mapper or closure edge).
- ``C2``: same repository, another Story, a ``buildPrerequisites`` row that the dependent's
  description states only on its "same work planned by other Epics" (overlap) line. The row is
  stripped from ``build_prerequisites`` too.
- ``C3``: another repository, a ``buildPrerequisites`` row whose ``requiredStage`` is ``built``.
  The row is stripped too.
- ``C4``: another repository, the blocker named only in ``blockedByExternal``.
- ``C5``: on what remains, an edge inside one Story, or a same-repository edge carried by a
  prerequisite row, that a longer path already implies (a transitive reduction).

Every other edge is kept: same-repository consumption, cross-repository ``published`` or
``deployed`` prerequisites, task-dependency-mapper and closure edges, and every edge nothing
attributes. Then ``storyedges.story_edges`` is planned on the graph without those edges, and
the owned Story edges it no longer derives are removed and dropped from their Stories'
owned-blocker and edge-reason metadata. The Story edges the plan would add are recorded and
left to the pipeline's next Story edge pass.

Without ``--apply`` nothing is written. Either way ``--out`` receives every edge, prerequisite
row and Story edge the run removes (or would), with its category and reason, and the original
``build_prerequisites`` and Story edge metadata, which is enough to rebuild them.

Usage:
  edgeprune.py --artifacts <workflow-runs artifacts directory> --out <record.json> [--apply]

The tracker is the one the `CONTROL_REPO_ENV` variable names.
"""

from __future__ import annotations

import argparse
import dataclasses
import functools
import json
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

import portfolio_path  # ruff: ignore[unused-import] - Puts the plugin's contract modules on the path first.

# isort: split
import beadgraph
import storyedges
from bead_metadata import (
    KEY_BUILD_PREREQUISITES,
    KEY_REPO_PATH,
    KEY_STORY_EDGE_REASONS,
    KEY_STORY_OWNED_BLOCKERS,
    KEY_STORY_OWNED_BLOCKERS_AT,
)
from beadwrite import task_started
from hierarchy import redundant_edges

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

type Edge = tuple[str, str]
"""``(dependent, blocker)``: the dependent Task waits for the blocker."""

C1: Final = "C1"
C2: Final = "C2"
C3: Final = "C3"
C4: Final = "C4"
C5: Final = "C5"
REASONS: Final[dict[str, str]] = {
    C1: "same-repository overlap named in blockedByExternal; no prerequisite row",
    C2: "same-repository built prerequisite stated only as same work planned by other Epics",
    C3: "built prerequisite on another repository's Story: nothing to build against until it merges",
    C4: "another repository's Task named only in blockedByExternal; no prerequisite row",
    C5: "a longer path through the kept edges already implies it",
}
#: A line of the dependent's description that names the blocker as overlapping work.
OVERLAP_LINE: Final = re.compile(r"same work|overlap|planned by other epics|plans the same")
STAGE_BUILT: Final = "built"
PRODUCERS: Final = "producers"
#: Edge removals sent in one `bd batch` transaction.
CHUNK: Final = 500
#: The Story metadata ``storyedges`` writes, recorded before the run changes it.
STORY_EDGE_KEYS: Final[tuple[str, ...]] = (
    KEY_STORY_OWNED_BLOCKERS,
    KEY_STORY_OWNED_BLOCKERS_AT,
    KEY_STORY_EDGE_REASONS,
)
#: The pauses before each retry of a write `bd` refused for a lock or a timeout, in seconds.
BACKOFF: Final[tuple[int, ...]] = (10, 20, 40)


class Removal(TypedDict):
    """One Task edge the run removes."""

    dependent: str
    blocker: str
    category: str
    reason: str
    epic: str


@dataclasses.dataclass(frozen=True)
class Attribution:
    """Which writer recorded each cross-Story Task edge, read from the elaboration artifacts."""

    external: frozenset[Edge]
    """Edges onto a Task the dependent's saved Task named in ``blockedByExternal``."""
    mapped: frozenset[Edge]
    """Edges the task-dependency-mapper (``task-deps.json``) or the closure (``closure-edges.json``) wrote."""


@dataclasses.dataclass(frozen=True)
class Places:
    """Each Task's Story, Epic and repository."""

    story: dict[str, str]
    epic: dict[str, str]
    repo: dict[str, str]


def _json_file(path: Path) -> object:
    """Read one JSON file.

    Returns:
        Its parsed content; None when it is unreadable or not JSON.

    """
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        sys.stderr.write(f"skipping {path}: {error}\n")
        return None


def _objects(value: object, key: str) -> list[dict[str, object]]:
    listed: object = value.get(key) if isinstance(value, dict) else None
    return [item for item in listed if isinstance(item, dict)] if isinstance(listed, list) else []


def _id_list(value: object) -> list[str]:
    """Read a ``blockedByExternal`` value, written as a list or, by older decompositions, as text.

    Returns:
        The ids; empty for any other shape.

    """
    if isinstance(value, str):
        try:
            value = json.loads(value.replace("'", '"'))
        except json.JSONDecodeError:
            return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _keymap(epic_dir: Path) -> tuple[dict[tuple[str, str], str], dict[Path, str]]:
    """Map each written Task's ``(repoPath, key)`` to its bead id, and each Tasks file to its repository.

    Returns:
        The id of each written Task, and the repository of each ``tasks-<repo>.json``.

    """
    ids: dict[tuple[str, str], str] = {}
    repos: dict[Path, str] = {}
    for written in sorted(epic_dir.glob("**/tasks-*.written.json")):
        document: object = _json_file(written)
        repo: str = str(document.get("repoPath") or "") if isinstance(document, dict) else ""
        repos[written.with_name(written.name.replace(".written.json", ".json"))] = repo
        ids.update({(repo, str(task.get("key"))): str(task.get("id")) for task in _objects(document, "tasks")})
    return ids, repos


def _external(ids: Mapping[tuple[str, str], str], repos: Mapping[Path, str]) -> set[Edge]:
    """Read every ``blockedByExternal`` entry of an Epic's saved Tasks files.

    Returns:
        ``(Task bead, named bead)`` for each entry of a written Task.

    """
    found: set[Edge] = set()
    for tasks_file, repo in repos.items():
        for task in _objects(_json_file(tasks_file) if tasks_file.is_file() else None, "tasks"):
            dependent: str | None = ids.get((repo, str(task.get("key"))))
            found.update((dependent, blocker) for blocker in _id_list(task.get("blockedByExternal")) if dependent)
    return found


def _mapped(epic_dir: Path, ids: Mapping[tuple[str, str], str]) -> set[Edge]:
    """Read the edges between an Epic's Stories that the mapper and the closure wrote.

    Returns:
        ``(dependent bead, blocker bead)`` for each edge whose two Tasks are written.

    """
    stories: dict[str, str] = {}
    for inputs in epic_dir.glob("**/task-deps-inputs.json"):
        stories.update({
            str(row.get("story")): str(row.get("repoPath")) for row in _objects(_json_file(inputs), "stories")
        })

    def bead(name: str) -> str | None:
        story, _, key = name.partition("-")
        return ids.get((stories.get(story, ""), key))

    rows: list[dict[str, object]] = [
        row
        for pattern in ("**/closure-edges.json", "**/task-deps.json")
        for path in epic_dir.glob(pattern)
        for row in _objects(_json_file(path), "edges")
    ]
    pairs: list[tuple[str | None, str | None]] = [
        (bead(str(row.get("to"))), bead(str(row.get("from")))) for row in rows
    ]
    return {(dependent, blocker) for dependent, blocker in pairs if dependent and blocker}


def read_attribution(artifacts: Path) -> Attribution:
    """Read which writer recorded each edge from every Epic's elaboration artifacts.

    Args:
        artifacts: The directory holding one work directory per Epic.

    Returns:
        The attributed edges.

    """
    external: set[Edge] = set()
    mapped: set[Edge] = set()
    for epic_dir in sorted(path for path in artifacts.glob("ssbd-*") if path.is_dir()):
        ids, repos = _keymap(epic_dir)
        external |= _external(ids, repos)
        mapped |= _mapped(epic_dir, ids)
    return Attribution(frozenset(external), frozenset(mapped))


def _nearest(graph: beadgraph.Graph, bead_id: str, kind: str) -> str:
    return next((bead.id for bead in graph.ancestors(bead_id) if bead.kind == kind), "")


def places(graph: beadgraph.Graph) -> Places:
    """Find each Task's Story, Epic and repository (its own ``repoPath``, else its Story's).

    Returns:
        The places.

    """
    tasks: list[beadgraph.Bead] = graph.of_kind("task")
    story: dict[str, str] = {task.id: _nearest(graph, task.id, "story") for task in tasks}
    repo: dict[str, str] = {
        task.id: task.metadata.get(KEY_REPO_PATH)
        or (graph.beads[story[task.id]].metadata.get(KEY_REPO_PATH, "") if story[task.id] else "")
        for task in tasks
    }
    return Places(story, {task.id: _nearest(graph, task.id, "epic") for task in tasks}, repo)


def producer_rows(bead: beadgraph.Bead) -> list[dict[str, object]]:
    """Read a Task's ``build_prerequisites`` producer rows.

    Returns:
        The rows; empty when the key is missing or is not a JSON object.

    """
    raw: str = bead.metadata.get(KEY_BUILD_PREREQUISITES, "")
    try:
        document: object = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return []
    return _objects(document, PRODUCERS)


def _overlap_stated(dependent: beadgraph.Bead, blocker: str) -> bool:
    """Report whether the dependent's description names the blocker on an overlap line.

    Returns:
        True when the line that first names the blocker reads as same work planned elsewhere.

    """
    text: str = dependent.description
    at: int = text.find(blocker)
    if at < 0:
        return False
    line: str = text[text.rfind("\n", 0, at) + 1 :].split("\n", 1)[0]
    return bool(OVERLAP_LINE.search(line.lower()))


@dataclasses.dataclass(frozen=True)
class Context:
    """What judging one edge needs."""

    graph: beadgraph.Graph
    places: Places
    attribution: Attribution
    stages: dict[Edge, str]
    """The ``requiredStage`` of the prerequisite row behind each edge that has one."""


def _cross_story(context: Context, edge: Edge) -> str | None:
    """Judge one live edge between two Stories against C1 to C4.

    Returns:
        The category it is removed under, or None when it is kept.

    """
    dependent, blocker = edge
    same: bool = context.places.repo.get(dependent) == context.places.repo.get(blocker)
    stage: str | None = context.stages.get(edge)
    if stage is not None and same:
        return C2 if _overlap_stated(context.graph.beads[dependent], blocker) else None
    if stage is not None:
        return C3 if stage == STAGE_BUILT else None
    if edge in context.attribution.mapped or edge not in context.attribution.external:
        return None
    return C1 if same else C4


def live_edges(graph: beadgraph.Graph) -> list[Edge]:
    """List every ``blocks`` edge between two open Tasks.

    Returns:
        ``(dependent, blocker)`` edges, sorted.

    """
    tasks: dict[str, beadgraph.Bead] = {bead.id: bead for bead in graph.of_kind("task") if not bead.closed}
    return sorted((task.id, blocker) for task in tasks.values() for blocker in task.blockers if blocker in tasks)


def _reducible(context: Context, edge: Edge) -> bool:
    dependent, blocker = edge
    if context.places.story.get(dependent) == context.places.story.get(blocker):
        return True
    return edge in context.stages and context.places.repo.get(dependent) == context.places.repo.get(blocker)


def judge(context: Context, edges: list[Edge]) -> tuple[dict[Edge, str], int]:
    """Choose the edges to remove and their categories.

    Args:
        context: The graph, places, attribution and prerequisite stages.
        edges: The live Task edges.

    Returns:
        Each removed edge's category, and how many removable edges were kept because their
        dependent Task has started.

    """
    started: set[str] = {dependent for dependent, _ in edges if task_started(context.graph.beads[dependent])}
    chosen: dict[Edge, str] = {}
    for edge in edges:
        category: str | None = (
            None
            if context.places.story.get(edge[0]) == context.places.story.get(edge[1])
            else _cross_story(context, edge)
        )
        if category is not None:
            chosen[edge] = category
    kept: list[Edge] = [edge for edge in edges if edge not in chosen or edge[0] in started]
    implied: set[tuple[str, str]] = redundant_edges([(blocker, dependent) for dependent, blocker in kept])
    chosen.update({
        (dependent, blocker): C5
        for blocker, dependent in implied
        if _reducible(context, (dependent, blocker)) and (dependent, blocker) not in chosen
    })
    held: int = sum(1 for edge in chosen if edge[0] in started)
    return {edge: category for edge, category in chosen.items() if edge[0] not in started}, held


def stripped_prerequisites(graph: beadgraph.Graph, chosen: Mapping[Edge, str]) -> dict[str, str]:
    """Compute the ``build_prerequisites`` each Task keeps once its C2 and C3 rows are stripped.

    Returns:
        Task id -> its new ``build_prerequisites`` metadata value.

    """
    dropped: dict[str, set[str]] = {}
    for (dependent, blocker), category in chosen.items():
        if category in {C2, C3}:
            dropped.setdefault(dependent, set()).add(blocker)
    return {
        task: json.dumps(
            {PRODUCERS: [row for row in producer_rows(graph.beads[task]) if str(row.get("task")) not in blockers]},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        for task, blockers in sorted(dropped.items())
    }


def _without(graph: beadgraph.Graph, removed: Iterable[Edge]) -> beadgraph.Graph:
    """Copy the graph without the removed Task edges, for planning the Story edges.

    Returns:
        The copy.

    """
    gone: dict[str, set[str]] = {}
    for dependent, blocker in removed:
        gone.setdefault(dependent, set()).add(blocker)
    beads: dict[str, beadgraph.Bead] = {
        bead_id: dataclasses.replace(bead, blockers=tuple(b for b in bead.blockers if b not in gone[bead_id]))
        if bead_id in gone
        else bead
        for bead_id, bead in graph.beads.items()
    }
    return beadgraph.Graph(beads=beads, source=graph.source, records=graph.records)


def _retried[T](action: Callable[[], T], what: str) -> T:
    """Run one write, again after each pause in BACKOFF when `bd` reports a lock or a timeout.

    Returns:
        What the write returns.

    Raises:
        beadgraph.GraphError: The write failed for another cause, or every retry failed.

    """
    for pause in (*BACKOFF, None):
        try:
            return action()
        except beadgraph.GraphError as error:
            if pause is None or error.cause not in beadgraph.RETRIED_CAUSES:
                raise
            sys.stderr.write(f"[edgeprune] {what}: {error.cause}; retrying in {pause}s\n")
            time.sleep(pause)
    unreached: str = f"{what} was never run"
    raise beadgraph.GraphError(unreached)


def _remove_standing(writer: beadgraph.Writer, edges: list[Edge]) -> None:
    standing: dict[str, set[str]] = beadgraph.blocking_edges(writer.repo)
    writer.write_blocks(
        {},
        [(dependent, blocker) for dependent, blocker in edges if blocker in standing.get(dependent, set())],
    )


def remove_edges(writer: beadgraph.Writer, edges: list[Edge]) -> None:
    """Remove edges in `bd batch` transactions of CHUNK edges, skipping any already gone.

    Each chunk rereads the standing edges first, so a retry after a write that committed but
    reported a timeout removes only what is left.

    Args:
        writer: The tracker writer.
        edges: The ``(dependent, blocker)`` edges to remove.

    """
    for start in range(0, len(edges), CHUNK):
        chunk: list[Edge] = edges[start : start + CHUNK]

        _retried(
            functools.partial(_remove_standing, writer, chunk),
            f"removing edges {start + 1}-{start + len(chunk)} of {len(edges)}",
        )
        sys.stderr.write(f"[edgeprune] removed {start + len(chunk)} of {len(edges)} edges\n")


def _write_metadata(writer: beadgraph.Writer, writes: list[tuple[str, dict[str, str]]]) -> None:
    for bead_id, pairs in writes:
        _retried(functools.partial(writer.metadata, bead_id, pairs), f"metadata of {bead_id}")


def plan_story_edges(graph: beadgraph.Graph) -> storyedges.StoryEdges:
    """Plan the Story edges on a graph without writing anything.

    Returns:
        The ``story_edges`` result, its writes in ``planned``.

    """
    return storyedges.story_edges(graph, beadgraph.Writer(None, dry_run=True))


def story_metadata(graph: beadgraph.Graph, removed: list[Edge]) -> list[tuple[str, dict[str, str]]]:
    """Compute each Story's owned blockers and edge reasons without its removed Story edges.

    Returns:
        ``(Story, metadata)`` for each Story that loses an edge.

    """
    gone: dict[str, set[str]] = {}
    for later, earlier in removed:
        gone.setdefault(later, set()).add(earlier)
    at: str = beadgraph.now_iso()
    return [
        (
            story,
            {
                KEY_STORY_OWNED_BLOCKERS: beadgraph.join_ids(set(beadgraph.split_ids(_owned(graph, story))) - earlier),
                KEY_STORY_OWNED_BLOCKERS_AT: at,
                KEY_STORY_EDGE_REASONS: _reasons_without(
                    graph.beads[story].metadata.get(KEY_STORY_EDGE_REASONS, ""),
                    earlier,
                ),
            },
        )
        for story, earlier in sorted(gone.items())
    ]


def _owned(graph: beadgraph.Graph, story: str) -> str:
    return graph.beads[story].metadata.get(KEY_STORY_OWNED_BLOCKERS, "")


def _reasons_without(raw: str, earlier: set[str]) -> str:
    """Drop the reasons of removed Story edges from a Story's edge reasons.

    Returns:
        The reasons JSON without those Stories; the text unchanged when it is not a JSON object.

    """
    try:
        reasons: object = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return raw
    if not isinstance(reasons, dict):
        return raw
    return json.dumps(
        {story: reason for story, reason in reasons.items() if story not in earlier},
        sort_keys=True,
        separators=(",", ":"),
    )


def apply_story_edges(writer: beadgraph.Writer, graph: beadgraph.Graph, planned: storyedges.StoryEdges) -> None:
    """Remove the owned Story edges the Task edges no longer derive, and update their Stories' metadata.

    The Story edges the plan would add are left to the pipeline's next Story edge pass: they were
    pending before this run and are no removal.

    Args:
        writer: The tracker writer.
        graph: The tracker graph the plan was made on.
        planned: The dry-run ``story_edges`` result.

    """
    removed: list[Edge] = [(edge["later"], edge["earlier"]) for edge in planned["removed"]]
    remove_edges(writer, removed)
    _write_metadata(writer, story_metadata(graph, removed))


def _record(
    context: Context,
    chosen: Mapping[Edge, str],
    held: int,
    prerequisites: Mapping[str, str],
) -> dict[str, object]:
    """Describe the Task edge and prerequisite removals.

    Returns:
        The counts, the counts per Epic, every removed edge and every changed prerequisite value.

    """
    removals: list[Removal] = [
        {
            "dependent": dependent,
            "blocker": blocker,
            "category": category,
            "reason": REASONS[category],
            "epic": context.places.epic.get(dependent, ""),
        }
        for (dependent, blocker), category in sorted(chosen.items())
    ]
    per_epic: dict[str, Counter[str]] = {}
    for removal in removals:
        per_epic.setdefault(removal["epic"], Counter())[removal["category"]] += 1
    return {
        "counts": {**Counter(chosen.values()), "total": len(chosen), "keptStarted": held},
        "perEpic": {epic: dict(counts) for epic, counts in sorted(per_epic.items())},
        "taskEdges": removals,
        "prerequisites": [
            {
                "task": task,
                "before": context.graph.beads[task].metadata.get(KEY_BUILD_PREREQUISITES, ""),
                "after": value,
                "rowsRemoved": len(producer_rows(context.graph.beads[task]))
                - len(_objects(json.loads(value), PRODUCERS)),
            }
            for task, value in prerequisites.items()
        ],
    }


def _story_record(graph: beadgraph.Graph, planned: storyedges.StoryEdges) -> dict[str, object]:
    """Describe the Story edge changes and the Story metadata they replace.

    Returns:
        The removed Story edges, the additions left unwritten, the refused Stories and their cycles, and
        the metadata before of each Story that loses an edge.

    """
    written: list[str] = sorted({edge["later"] for edge in planned["removed"]})
    return {
        "removed": planned["removed"],
        "pendingAdditionsNotWritten": planned["added"],
        "refusedStories": planned["refusedStories"],
        "cycles": planned["cycles"],
        "metadataBefore": {
            story: {key: graph.beads[story].metadata.get(key, "") for key in STORY_EDGE_KEYS} for story in written
        },
    }


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line.

    Returns:
        The arguments.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--artifacts", type=Path, required=True, help="the workflow-runs artifacts directory")
    parser.add_argument("--out", type=Path, required=True, help="the file the removal record is written to")
    parser.add_argument("--apply", action="store_true", help="write the removals; without it nothing is written")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Plan the removals, write the record, and with ``--apply`` make them.

    Returns:
        The exit status.

    """
    args: argparse.Namespace = _arguments(argv)
    graph: beadgraph.Graph = beadgraph.load(None, with_description=True)
    rows: dict[Edge, str] = {
        (task.id, str(row.get("task"))): str(row.get("requiredStage"))
        for task in graph.of_kind("task")
        for row in producer_rows(task)
    }
    context: Context = Context(graph, places(graph), read_attribution(args.artifacts), rows)
    chosen, held = judge(context, live_edges(graph))
    prerequisites: dict[str, str] = stripped_prerequisites(graph, chosen)
    planned: storyedges.StoryEdges = plan_story_edges(_without(graph, chosen))
    record: dict[str, object] = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "applied": args.apply,
        **_record(context, chosen, held, prerequisites),
        "storyEdges": _story_record(graph, planned),
    }
    args.out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    sys.stdout.write(
        json.dumps({"counts": record["counts"], "storyEdgesRemoved": len(planned["removed"]), "out": str(args.out)})
        + "\n",
    )
    if not args.apply:
        return 0
    writer: beadgraph.Writer = beadgraph.Writer(None)
    remove_edges(writer, sorted(chosen))
    _write_metadata(writer, [(task, {KEY_BUILD_PREREQUISITES: value}) for task, value in prerequisites.items()])
    reloaded: beadgraph.Graph = beadgraph.load(None)
    apply_story_edges(writer, reloaded, plan_story_edges(reloaded))
    return 0


if __name__ == "__main__":
    sys.exit(main())
