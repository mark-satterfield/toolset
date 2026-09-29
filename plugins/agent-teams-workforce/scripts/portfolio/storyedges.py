#!/usr/bin/env python3
"""The Story -> Story `blocks` edges of each repository, derived in code and never judged.

A Story is scoped to one repository, and a repository has at most one Story in progress: a
later Story's branch is cut from a `main` that already holds the earlier Story's code, and
both deploy the same stacks. So within one repository the Stories are ordered, from two
sources:

1. Epic order. The Story of the earlier Epic goes first, where one Epic reaches the other
   through `tracks` edges.
2. Task edges between two Stories of the repository. The Story holding the depended-on Task
   goes first: that Task's code reaches the other Story's branch only through `main`.

The order is written as a `blocks` edge on the later Story, `bd dep add <later> <earlier>
--type blocks`. A blocked Story holds back every Task beneath it in `bd ready`, and the edge
releases when the earlier Story closes, which it does when its pull request merges.

When the sources disagree about a pair of Stories, or the Story graph holds a cycle together
with the hand-made Story edges and the hold an in-progress Story has on its repository (every
other Story of that repository waits for it), nothing is written and the Stories and Tasks
involved are named. Beads' own cycle detection does not catch this: a Story edge against a Task edge
freezes both Stories without any single edge closing a loop.

Stories in different repositories never get an edge. Ownership is recorded on the later
Story as `story_owned_blockers`, with the reasons as `story_edge_reasons`, so an edge drawn
by hand is never removed and an edge the sources no longer derive is.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from beadgraph import join_ids, now_iso, split_ids

if TYPE_CHECKING:
    from beadgraph import Bead, Graph, Writer

#: Metadata key on the later Story listing the Story edges this script created.
OWNED_KEY = "story_owned_blockers"
OWNED_AT_KEY = "story_owned_blockers_at"

#: Metadata key on the later Story: blocker id -> the reasons the edge stands.
REASONS_KEY = "story_edge_reasons"

#: The metadata key a Story records its repository under.
REPO_KEY = "repoPath"

_REPO_LINE = re.compile(r"^\s*repoPath:\s*(\S.*?)\s*$", re.MULTILINE)


def repository_of(bead: Bead, record: dict) -> str | None:
    """The repository a Story is scoped to, normalized to an absolute path when it is one.

    Args:
        bead: The Story.
        record: Its tracker record, for the `repoPath:` line in its notes.

    Returns:
        The repository, or None when the Story records none.
    """
    value = bead.metadata.get(REPO_KEY, "").strip()
    if not value:
        match = _REPO_LINE.search(str(record.get("notes") or ""))
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
    direct = {b.id: set(b.tracked) for b in graph.of_kind("epic")}
    reach: dict[str, set[str]] = {}
    for epic in direct:
        seen: set[str] = set()
        stack = list(direct[epic])
        while stack:
            current = stack.pop()
            if current in seen or current == epic:
                continue
            seen.add(current)
            stack.extend(direct.get(current, ()))
        reach[epic] = seen
    return reach


def _story_of(graph: Graph, bead_id: str) -> str | None:
    """The nearest Story above a bead.

    Args:
        graph: The tracker graph.
        bead_id: The bead.

    Returns:
        The Story id, or None.
    """
    return next((b.id for b in graph.ancestors(bead_id) if b.kind == "story"), None)


def derive(graph: Graph) -> dict:
    """The Story edges each repository's Epic order and Task edges require.

    Args:
        graph: The tracker graph.

    Returns:
        `required`: (later, earlier) -> the reasons; `repos`: Story id -> repository.
    """
    records = {str(r.get("id")): r for r in graph.records}
    repos = {
        b.id: repo
        for b in graph.of_kind("story")
        if not b.closed and (repo := repository_of(b, records.get(b.id, {})))
    }
    earlier = _earlier_epics(graph)
    epic_of = {
        story: (graph.epic_of(story).id if graph.epic_of(story) else None)
        for story in repos
    }
    required: dict[tuple[str, str], list[dict]] = {}
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
                    }
                )
    for task in graph.of_kind("task"):
        if task.closed:
            continue
        later = _story_of(graph, task.id)
        if later not in repos:
            continue
        for blocker in task.blockers:
            first = _story_of(graph, blocker)
            if (
                first is None
                or first == later
                or first not in repos
                or repos[first] != repos[later]
            ):
                continue
            required.setdefault((later, first), []).append(
                {
                    "source": "task-edge",
                    "tasks": [blocker, task.id],
                    "detail": f"Task {task.id} depends on Task {blocker}",
                }
            )
    return {"required": required, "repos": repos}


def _hand_made(graph: Graph, repos: dict[str, str]) -> set[tuple[str, str]]:
    """The Story -> Story `blocks` edges standing between open Stories that this script does not own.

    Args:
        graph: The tracker graph.
        repos: Open Story id -> repository.

    Returns:
        The (later, earlier) pairs.
    """
    pairs: set[tuple[str, str]] = set()
    for story in repos:
        bead = graph.beads[story]
        owned = set(split_ids(bead.metadata.get(OWNED_KEY, "")))
        pairs |= {(story, b) for b in bead.blockers if b in repos and b not in owned}
    return pairs


def _in_progress_holds(graph: Graph, repos: dict[str, str]) -> set[tuple[str, str]]:
    """The waits the one-Story-per-repository rule imposes: each other open Story after an in-progress one.

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
        if other != story
        and other_repo == repo
        and graph.beads[other].status != "in_progress"
    }


def _cycles(edges: set[tuple[str, str]]) -> list[list[str]]:
    """The strongly connected groups of two or more Stories in a directed edge set.

    Args:
        edges: (later, earlier) pairs.

    Returns:
        Each cycle's Stories, sorted.
    """
    graph: dict[str, set[str]] = {}
    for later, first in edges:
        graph.setdefault(later, set()).add(first)
        graph.setdefault(first, set())
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[list[str]] = []
    counter = [0]

    def visit(node: str) -> None:
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
            group: list[str] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                group.append(member)
                if member == node:
                    break
            if len(group) > 1:
                found.append(sorted(group))

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return found


def _reasons_text(reasons: list[dict]) -> str:
    """The recorded reasons of one edge.

    Args:
        reasons: The derivations of the edge.

    Returns:
        The reasons, `; `-joined.
    """
    return "; ".join(r["detail"] for r in reasons)


def story_edges(graph: Graph, writer: Writer) -> dict:
    """Derive every repository's Story edges and write the difference, or refuse the whole set.

    Args:
        graph: The tracker graph, read after the Task edges were written.
        writer: The tracker writer; a dry-run writer records the writes instead.

    Returns:
        `ok`, the derived `edges` with their reasons, the `conflicts` and `cycles` that
        refused the set, the `added`, `removed` and `unchanged` edges, and a `summary`.
    """
    derived = derive(graph)
    required, repos = derived["required"], derived["repos"]
    conflicts = [
        {
            "stories": [first, later],
            "tasks": sorted(
                {
                    t
                    for r in [*reasons, *required[(first, later)]]
                    for t in r.get("tasks", [])
                }
            ),
            "epics": sorted(
                {
                    e
                    for r in [*reasons, *required[(first, later)]]
                    for e in r.get("epics", [])
                }
            ),
            "reasons": {
                f"{later} after {first}": _reasons_text(reasons),
                f"{first} after {later}": _reasons_text(required[(first, later)]),
            },
        }
        for (later, first), reasons in sorted(required.items())
        if (first, later) in required and later < first
    ]
    cycles = []
    standing = _hand_made(graph, repos)
    holds = _in_progress_holds(graph, repos)
    if not conflicts:
        for group in _cycles(set(required) | standing | holds):
            members = set(group)
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
                                if (later, first) in standing
                                else f"{first} is in progress in the repository"
                            ),
                        }
                        for later, first in sorted(set(required) | standing | holds)
                        if later in members and first in members
                    ],
                    "tasks": sorted(
                        {
                            t
                            for (lt, ft), rs in required.items()
                            if lt in members and ft in members
                            for r in rs
                            for t in r.get("tasks", [])
                        }
                    ),
                }
            )
    edges = [
        {"later": later, "earlier": first, "repo": repos[later], "reasons": reasons}
        for (later, first), reasons in sorted(required.items())
    ]
    if conflicts or cycles:
        return {
            "ok": False,
            "refused": True,
            "reason": "the Story order is contradictory, so no Story edge was written",
            "conflicts": conflicts,
            "cycles": cycles,
            "edges": edges,
            "dryRun": writer.dry_run,
            "planned": writer.planned,
            "summary": {
                "ok": False,
                "conflicts": len(conflicts),
                "cycles": len(cycles),
                "derived": len(edges),
            },
        }
    added: list[dict] = []
    removed: list[dict] = []
    unchanged = 0
    for story in sorted(repos):
        bead = graph.beads[story]
        wanted = {
            first: reasons
            for (later, first), reasons in required.items()
            if later == story
        }
        owned = set(split_ids(bead.metadata.get(OWNED_KEY, "")))
        standing = set(bead.blockers)
        adds = sorted(set(wanted) - standing)
        drops = sorted((owned - set(wanted)) & standing)
        unchanged += len(set(wanted) & standing)
        reasons = json.dumps(
            {b: _reasons_text(r) for b, r in sorted(wanted.items())},
            sort_keys=True,
            separators=(",", ":"),
        )
        final = join_ids(set(wanted))
        if adds:
            writer.metadata(
                story, {OWNED_KEY: join_ids(owned | set(adds)), OWNED_AT_KEY: now_iso()}
            )
        for first in adds:
            writer.bd(["dep", "add", story, first, "--type", "blocks"])
            added.append(
                {
                    "later": story,
                    "earlier": first,
                    "reasons": _reasons_text(wanted[first]),
                }
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
                story, {OWNED_KEY: final, OWNED_AT_KEY: now_iso(), REASONS_KEY: reasons}
            )
    return {
        "ok": True,
        "refused": False,
        "conflicts": [],
        "cycles": [],
        "edges": edges,
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "ok": True,
            "derived": len(edges),
            "added": len(added),
            "removed": len(removed),
            "unchanged": unchanged,
        },
    }
