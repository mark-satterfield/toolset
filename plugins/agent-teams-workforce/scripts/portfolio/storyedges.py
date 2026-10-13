#!/usr/bin/env python3
"""The Story -> Story `blocks` edges, derived in code and never judged.

A Story is scoped to one repository, its Tasks commit to the Story's branch, and that code
reaches anything else only when the Story's pull request merges to `main`. So the Stories
are ordered from two sources:

1. Epic order, within one repository. A repository has at most one Story in progress, and a
   later Story's branch is cut from a `main` that already holds the earlier Story's code.
   The Story of the earlier Epic goes first, where one Epic reaches the other through
   `tracks` edges.
2. Task edges between two Stories, in the same repository or in different ones. The Story
   holding the depended-on Task goes first: that Task's code is usable by the other Story
   only once the Story holding it has merged.

The order is written as a `blocks` edge on the later Story, `bd dep add <later> <earlier>
--type blocks`. A blocked Story holds back every Task beneath it in `bd ready`, and the edge
releases when the earlier Story closes, which it does when its pull request merges.

When the sources disagree about a pair of Stories, or the Story graph holds a cycle together
with the hand-made Story edges and the hold an in-progress Story has on its repository (every
other Story of that repository waits for it), nothing is written for the Stories involved and
they and their Tasks are named; every other Story's edges are written as usual. Beads' own
cycle detection does not catch this: a Story edge against a Task edge freezes both Stories
without any single edge closing a loop.

Ownership is recorded on the later Story under the beads-contract Story owned-blockers key,
with reasons under its Story edge-reasons key, so an edge drawn
by hand is never removed and an edge the sources no longer derive is.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict

import beadgraph
from beadcontracts import PlannedWrite
from beadgraph import Bead, Graph, Writer, join_ids, now_iso, split_ids
from typeguard import CollectionCheckStrategy, typechecked

# The bead metadata keys and the matrix contract are generated from their schemas, their one
# definition each.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))

# isort: split
import beads_contract
from bead_metadata import (
    KEY_STORY_EDGE_REASONS,
    KEY_STORY_OWNED_BLOCKERS,
    KEY_STORY_OWNED_BLOCKERS_AT,
)
from matrix_contract import KIND_STACK, Entry, EntryId, JsonValue
from matrixstore import Matrix, matrix_path, read_matrix

if TYPE_CHECKING:
    from bead_metadata import BuildContract
    from contracts import JsonObject

_ARGUMENT_ERROR: str = "Arguments violate the storyedges input contract"

#: The attribute of a stack entry that names the repository holding it.
ATTR_REPOSITORY: Final = "repository"


class EdgeReason(TypedDict):
    """Describe the edge reason wire record."""

    source: str
    detail: str
    epics: NotRequired[list[str]]
    tasks: NotRequired[list[str]]


class DerivedEdges(TypedDict):
    """Describe the derived edges wire record."""

    required: dict[tuple[str, str], list[EdgeReason]]
    repos: dict[str, str]


class EdgeConflict(TypedDict):
    """Describe the edge conflict wire record."""

    stories: list[str]
    tasks: list[str]
    epics: list[str]
    reasons: dict[str, str]


class EdgePair(TypedDict):
    """Describe the edge pair wire record."""

    later: str
    earlier: str
    reasons: NotRequired[str]


class EdgeCycle(TypedDict):
    """Describe the edge cycle wire record."""

    stories: list[str]
    edges: list[EdgePair]
    tasks: list[str]


class DerivedEdge(TypedDict):
    """Describe the derived edge wire record."""

    later: str
    earlier: str
    repo: str
    reasons: list[EdgeReason]


class StoryEdgeSummary(TypedDict):
    """Describe the story edge summary wire record."""

    ok: bool
    derived: int
    added: int
    removed: int
    unchanged: int
    conflicts: int
    cycles: int
    refusedStories: list[str]


class StoryEdges(TypedDict):
    """Describe the story edges wire record."""

    ok: bool
    refused: bool
    reason: NotRequired[str]
    refusedStories: list[str]
    conflicts: list[EdgeConflict]
    cycles: list[EdgeCycle]
    edges: list[DerivedEdge]
    added: list[EdgePair]
    removed: list[EdgePair]
    unchanged: int
    dryRun: bool
    planned: list[PlannedWrite]
    summary: StoryEdgeSummary


def _stated_ids(record: JsonObject) -> list[str]:
    """Read the matrix ids one Task's tracker record states.

    Returns:
        The ids its `matrix_elements` key carries, read through `beads_contract.read_contract`,
        the one reader of the build contract; none when it carries none.

    Raises:
        ValueError: The Task's metadata is not readable.

    """
    try:
        contract: BuildContract = beads_contract.read_contract(record)
    except ValueError as error:
        message: str = f"reading the matrix ids of the Task {record.get('id')}: {error}"
        raise ValueError(message) from error
    return list(contract.get("matrix_elements", []))


def _repository_of(matrix: Matrix, stated: str) -> str | None:
    """Find the repository of the stack one stated id names or is held by.

    Returns:
        The stack's `repository`; None when the id is no entry's, the entry has no stack, or
        the stack names no repository.

    """
    entry: Entry | None = matrix.find(EntryId(stated))
    if entry is None:
        return None
    stack: Entry | None = entry if entry.kind == KIND_STACK else None
    if stack is None:
        home: EntryId | None = matrix.home(entry.id)
        stack = matrix.find(home) if home is not None else None
    repository: JsonValue = stack.attributes.get(ATTR_REPOSITORY) if stack is not None else None
    return repository if isinstance(repository, str) and repository else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_repositories(graph: Graph, matrix: Matrix) -> dict[str, str]:
    """Return the repository each open Story is scoped to, from the stack its Tasks state.

    A Task states the matrix ids of what it builds; the stack among them, or the stack that
    holds an entry among them, names its repository in the matrix. A Story whose Tasks state
    stacks of more than one repository takes the first in name order.

    Args:
        graph: The tracker graph.
        matrix: The matrix.

    Returns:
        Open Story id -> the repository's name. A Story whose Tasks state no stack that names a
        repository is left out.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    record: JsonObject
    if not isinstance(graph, Graph) or not isinstance(matrix, Matrix):
        raise TypeError(_ARGUMENT_ERROR)
    found: dict[str, set[str]] = {}
    for record in graph.records:
        task: Bead = beadgraph.bead_of(record)
        if task.kind != "task":
            continue
        story: str | None = _story_of(graph, task.id)
        if story is None or graph.beads[story].closed:
            continue
        stated: str
        for stated in _stated_ids(record):
            repository: str | None = _repository_of(matrix, stated)
            if repository is not None:
                found.setdefault(story, set()).add(repository)
    return {story: min(repositories) for story, repositories in found.items()}


def _earlier_epics(graph: Graph) -> dict[str, set[str]]:
    """Every Epic mapped to the Epics it reaches through `tracks` edges, transitively.

    Args:
        graph: The tracker graph.

    Returns:
        Epic id -> the Epics that come before it.

    """
    epic: str
    prerequisites: set[str]
    direct: dict[str, set[str]] = {b.id: set(b.tracked) for b in graph.of_kind("epic")}
    reach: dict[str, set[str]] = {}
    for epic, prerequisites in direct.items():
        seen: set[str] = set()
        stack: list[str] = list(prerequisites)
        while stack:
            current: str = stack.pop()
            if current in seen or current == epic:
                continue
            seen.add(current)
            stack.extend(direct.get(current, ()))
        reach[epic] = seen
    return reach


def _story_of(graph: Graph, bead_id: str) -> str | None:
    """Return the nearest Story above a bead.

    Args:
        graph: The tracker graph.
        bead_id: The bead.

    Returns:
        The Story id, or None.

    """
    return next((b.id for b in graph.ancestors(bead_id) if b.kind == "story"), None)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def derive(graph: Graph, repositories: Mapping[str, str]) -> DerivedEdges:
    """Return the Story edges Epic order within a repository and Task edges between Stories require.

    Args:
        graph: The tracker graph.
        repositories: Open Story id -> the repository it is scoped to (`story_repositories`).

    Returns:
        `required`: (later, earlier) -> the reasons; `repos`: Story id -> repository.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    later: str
    repo: str | None
    first: str
    other_repo: str
    a: str | None
    b: str | None
    task: Bead
    blocker: str
    if not isinstance(graph, Graph) or not isinstance(repositories, Mapping):
        raise TypeError(_ARGUMENT_ERROR)
    repos: dict[str, str] = dict(repositories)
    earlier: dict[str, set[str]] = _earlier_epics(graph)
    epic_of: dict[str, str | None] = {story: (epic.id if (epic := graph.epic_of(story)) else None) for story in repos}
    required: dict[tuple[str, str], list[EdgeReason]] = {}
    for later, repo in repos.items():
        for first, other_repo in repos.items():
            if first == later or other_repo != repo:
                continue
            a, b = epic_of[first], epic_of[later]
            if a and b and a != b and a in earlier.get(b, set()):
                required.setdefault((later, first), []).append(
                    {
                        "source": "epic-order",
                        "epics": [a, b],
                        "detail": f"Epic {b} follows Epic {a} by `tracks` edges",
                    },
                )
    for task in (bead for bead in graph.of_kind("task") if not bead.closed):
        task_story: str | None = _story_of(graph, task.id)
        if task_story is None or task_story not in repos:
            continue
        for blocker in task.blockers:
            blocker_story: str | None = _story_of(graph, blocker)
            if blocker_story is None or blocker_story == task_story or blocker_story not in repos:
                continue
            required.setdefault((task_story, blocker_story), []).append(
                {
                    "source": "task-edge",
                    "tasks": [blocker, task.id],
                    "detail": f"Task {task.id} depends on Task {blocker}",
                },
            )
    return {"required": required, "repos": repos}


def _hand_made(graph: Graph, repos: dict[str, str]) -> set[tuple[str, str]]:
    """Return the Story -> Story `blocks` edges standing between open Stories that this script does not own.

    Args:
        graph: The tracker graph.
        repos: Open Story id -> repository.

    Returns:
        The (later, earlier) pairs.

    """
    story: str
    pairs: set[tuple[str, str]] = set()
    for story in repos:
        bead: beadgraph.Bead = graph.beads[story]
        owned: set[str] = set(split_ids(bead.metadata.get(KEY_STORY_OWNED_BLOCKERS, "")))
        pairs |= {(story, b) for b in bead.blockers if b in repos and b not in owned}
    return pairs


def _in_progress_holds(graph: Graph, repos: dict[str, str]) -> set[tuple[str, str]]:
    """Return the waits the one-Story-per-repository rule imposes: each other open Story after an in-progress one.

    Args:
        graph: The tracker graph.
        repos: Open Story id -> repository.

    Returns:
        The (later, earlier) pairs.

    """
    return {
        (other, story)
        for story, repo in repos.items()
        if graph.beads[story].status == "in_progress"
        for other, other_repo in repos.items()
        if other != story and other_repo == repo and graph.beads[other].status != "in_progress"
    }


def _pop_group(stack: list[str], on_stack: set[str], node: str) -> list[str]:
    """Pop a strongly connected group through its root node.

    Returns:
        All members removed from the Tarjan stack.

    """
    group: list[str] = []
    while True:
        member: str = stack.pop()
        on_stack.discard(member)
        group.append(member)
        if member == node:
            break
    return group


def _cycles(edges: set[tuple[str, str]]) -> list[list[str]]:
    """Return the strongly connected groups of two or more Stories in a directed edge set.

    Args:
        edges: (later, earlier) pairs.

    Returns:
        Each cycle's Stories, sorted.

    """
    later: str
    first: str
    node: str
    graph: dict[str, set[str]] = {}
    for later, first in edges:
        graph.setdefault(later, set()).add(first)
        graph.setdefault(first, set())
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[list[str]] = []
    counter: list[int] = [0]

    def visit(node: str) -> None:
        succ: str
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for succ in sorted(graph[node]):
            if succ not in index:
                visit(succ)
                low[node] = min(low[node], low[succ])
            elif succ in on_stack:
                low[node] = min(low[node], index[succ])
        if low[node] == index[node]:
            group: list[str] = _pop_group(stack, on_stack, node)
            if len(group) > 1:
                found.append(sorted(group))

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return found


def _reasons_text(reasons: list[EdgeReason]) -> str:
    """Return the recorded reasons of one edge.

    Args:
        reasons: The derivations of the edge.

    Returns:
        The reasons, `; `-joined.

    """
    return "; ".join(r["detail"] for r in reasons)


def _write_story_edges(
    graph: Graph,
    writer: Writer,
    required: dict[tuple[str, str], list[EdgeReason]],
    repos: dict[str, str],
    refused: list[str],
) -> tuple[list[EdgePair], list[EdgePair], int]:
    """Write the approved difference between owned and required Story edges.

    Returns:
        Added edges, removed edges, and the unchanged count.

    """
    story: str
    first: str
    added: list[EdgePair] = []
    removed: list[EdgePair] = []
    unchanged: int = 0
    for story in sorted(set(repos) - set(refused)):
        bead: beadgraph.Bead = graph.beads[story]
        wanted: dict[str, list[EdgeReason]] = {
            first: reasons for (later, first), reasons in required.items() if later == story
        }
        owned: set[str] = set(split_ids(bead.metadata.get(KEY_STORY_OWNED_BLOCKERS, "")))
        standing: set[str] = set(bead.blockers)
        adds: list[str] = sorted(set(wanted) - standing)
        drops: list[str] = sorted((owned - set(wanted)) & standing)
        unchanged += len(set(wanted) & standing)
        reasons: str = json.dumps(
            {b: _reasons_text(r) for b, r in sorted(wanted.items())},
            sort_keys=True,
            separators=(",", ":"),
        )
        final: str = join_ids(set(wanted))
        if adds:
            writer.metadata(
                story,
                {KEY_STORY_OWNED_BLOCKERS: join_ids(owned | set(adds)), KEY_STORY_OWNED_BLOCKERS_AT: now_iso()},
            )
        for first in adds:
            writer.bd(["dep", "add", story, first, "--type", "blocks"])
            added.append(
                {
                    "later": story,
                    "earlier": first,
                    "reasons": _reasons_text(wanted[first]),
                },
            )
        for first in drops:
            writer.bd(["dep", "remove", story, first])
            removed.append({"later": story, "earlier": first})
        if (
            adds
            or drops
            or final != bead.metadata.get(KEY_STORY_OWNED_BLOCKERS, "")
            or (wanted and reasons != bead.metadata.get(KEY_STORY_EDGE_REASONS, ""))
        ):
            writer.metadata(
                story,
                {
                    KEY_STORY_OWNED_BLOCKERS: final,
                    KEY_STORY_OWNED_BLOCKERS_AT: now_iso(),
                    KEY_STORY_EDGE_REASONS: reasons,
                },
            )
    return added, removed, unchanged


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_edges(graph: Graph, writer: Writer) -> StoryEdges:
    """Derive every Story edge and write the difference, except for refused Stories.

    Each Story's repository is read from the matrix: the `repository` of the stack its Tasks
    state. The matrix is the file the environment names (`matrixstore.matrix_path`); a matrix
    that is missing or unreadable raises `MatrixError`, a `ValueError`, from `read_matrix`.

    Args:
        graph: The tracker graph, read after the Task edges were written.
        writer: The tracker writer; a dry-run writer records the writes instead.

    Returns:
        `ok` (false when a Story was refused), the derived `edges` with their reasons, the
        `conflicts` and `cycles` and the `refusedStories` they name, the `added`, `removed`
        and `unchanged` edges, and a `summary`.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    required: dict[tuple[str, str], list[EdgeReason]]
    repos: dict[str, str]
    group: list[str]
    added: list[EdgePair]
    removed: list[EdgePair]
    unchanged: int
    if not (isinstance(graph, Graph)) or not (isinstance(writer, Writer)):
        raise TypeError(_ARGUMENT_ERROR)
    matrix: Matrix = read_matrix(matrix_path(None, os.environ))
    derived: DerivedEdges = derive(graph, story_repositories(graph, matrix))
    required, repos = derived["required"], derived["repos"]
    conflicts: list[EdgeConflict] = [
        {
            "stories": [first, later],
            "tasks": sorted(
                {t for r in [*reasons, *required[first, later]] for t in r.get("tasks", [])},
            ),
            "epics": sorted(
                {e for r in [*reasons, *required[first, later]] for e in r.get("epics", [])},
            ),
            "reasons": {
                f"{later} after {first}": _reasons_text(reasons),
                f"{first} after {later}": _reasons_text(required[first, later]),
            },
        }
        for (later, first), reasons in sorted(required.items())
        if (first, later) in required and later < first
    ]
    cycles: list[EdgeCycle] = []
    standing_edges: set[tuple[str, str]] = _hand_made(graph, repos)
    holds: set[tuple[str, str]] = _in_progress_holds(graph, repos)
    for group in _cycles(set(required) | standing_edges | holds):
        members: set[str] = set(group)
        cycles.append(
            {
                "stories": group,
                "edges": [
                    {
                        "later": later,
                        "earlier": first,
                        "reasons": _reasons_text(required.get((later, first), []))
                        or (
                            "drawn by hand"
                            if (later, first) in standing_edges
                            else f"{first} is in progress in the repository"
                        ),
                    }
                    for later, first in sorted(set(required) | standing_edges | holds)
                    if later in members and first in members
                ],
                "tasks": sorted(
                    {
                        t
                        for (lt, ft), rs in required.items()
                        if lt in members and ft in members
                        for r in rs
                        for t in r.get("tasks", [])
                    },
                ),
            },
        )
    edges: list[DerivedEdge] = [
        {"later": later, "earlier": first, "repo": repos[later], "reasons": reasons}
        for (later, first), reasons in sorted(required.items())
    ]
    refused: list[str] = sorted(
        {x for c in conflicts for x in c["stories"]} | {x for c in cycles for x in c["stories"]},
    )
    added, removed, unchanged = _write_story_edges(graph, writer, required, repos, refused)
    result: StoryEdges = {
        "ok": not refused,
        "refused": bool(refused),
        "refusedStories": refused,
        "conflicts": conflicts,
        "cycles": cycles,
        "edges": edges,
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "ok": not refused,
            "derived": len(edges),
            "added": len(added),
            "removed": len(removed),
            "unchanged": unchanged,
            "conflicts": len(conflicts),
            "cycles": len(cycles),
            "refusedStories": refused,
        },
    }

    if refused:
        result["reason"] = (
            "the Story order of " + ", ".join(refused) + " is contradictory, so their Story edges were not written"
        )
    return result
