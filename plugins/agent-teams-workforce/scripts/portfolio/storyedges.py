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

Ownership is recorded on the later Story as `story_owned_blockers`, with reasons as
`story_edge_reasons`, so an edge drawn
by hand is never removed and an edge the sources no longer derive is.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NotRequired, TypedDict

import beadgraph
import contracts
from beadcontracts import PlannedWrite
from beadgraph import Bead, Graph, Writer, join_ids, now_iso, split_ids
from contracts import JsonObject
from typeguard import CollectionCheckStrategy, typechecked

#: Metadata key on the later Story listing the Story edges this script created.
_ARGUMENT_ERROR: str = "Arguments violate the storyedges input contract"


OWNED_KEY = "story_owned_blockers"
OWNED_AT_KEY = "story_owned_blockers_at"

#: Metadata key on the later Story: blocker id -> the reasons the edge stands.
REASONS_KEY = "story_edge_reasons"

#: The metadata key a Story records its repository under.
REPO_KEY = "repoPath"

_REPO_LINE = re.compile(r"^\s*repoPath:\s*(\S.*?)\s*$", re.MULTILINE)


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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_of(bead: Bead, record: JsonObject) -> str | None:
    """Return the repository a Story is scoped to, normalized to an absolute path when it is one.

    Args:
        bead: The Story.
        record: Its tracker record, for the `repoPath:` line in its notes.

    Returns:
        The repository, or None when the Story records none.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(bead, Bead)):
        raise TypeError(_ARGUMENT_ERROR)
    value: str = bead.metadata.get(REPO_KEY, "").strip()
    if not value:
        match: re.Match[str] | None = _REPO_LINE.search(str(record.get("notes") or ""))
        value = match.group(1).strip() if match else ""
    if not value:
        return None
    return str(Path(value).resolve()) if value.startswith("/") else value


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


def _story_repositories(graph: Graph, records: dict[str, JsonObject]) -> dict[str, str]:
    result: dict[str, str] = {}
    story: Bead
    for story in graph.of_kind("story"):
        if story.closed:
            continue
        repository: str | None = repository_of(story, records.get(story.id, {}))
        if repository:
            result[story.id] = repository
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def derive(graph: Graph) -> DerivedEdges:
    """Return the Story edges Epic order within a repository and Task edges between Stories require.

    Args:
        graph: The tracker graph.

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
    if not (isinstance(graph, Graph)):
        raise TypeError(_ARGUMENT_ERROR)
    records: dict[str, dict[str, contracts.JsonValue]] = {str(r.get("id")): r for r in graph.records}
    repos: dict[str, str] = _story_repositories(graph, records)
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
        owned: set[str] = set(split_ids(bead.metadata.get(OWNED_KEY, "")))
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
        owned: set[str] = set(split_ids(bead.metadata.get(OWNED_KEY, "")))
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
                {OWNED_KEY: join_ids(owned | set(adds)), OWNED_AT_KEY: now_iso()},
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
            or final != bead.metadata.get(OWNED_KEY, "")
            or (wanted and reasons != bead.metadata.get(REASONS_KEY, ""))
        ):
            writer.metadata(
                story,
                {OWNED_KEY: final, OWNED_AT_KEY: now_iso(), REASONS_KEY: reasons},
            )
    return added, removed, unchanged


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_edges(graph: Graph, writer: Writer) -> StoryEdges:
    """Derive every Story edge and write the difference, except for refused Stories.

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
    derived: DerivedEdges = derive(graph)
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
