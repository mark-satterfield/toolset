"""Write one Story, one Story's Tasks, or the Task edges between Stories into beads.

Each write reads the document its elaboration step saved in the Epic's working directory and
is keyed by the durable `elab_key`: a Story or Task no bead under its parent carries is
created, an open one that carries it is updated where it differs, and any other is left as it
is. A write that fails raises `GraphError` from the writer, and a rerun repairs it, because
every write is idempotent.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from beadgraph import SCOPE_JUDGING, fingerprints, same_value
from hierarchy import (
    SIZE_KEYS,
    HierarchyError,
    Task,
    build_order,
    elab_slug,
    read_story,
    read_task_deps,
    read_tasks,
    repo_slugs,
)
from scoring import JUDGED_HASH_KEY

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from beadgraph import Bead, Graph, Writer

#: The one status a matched Story or Task is rewritten in.
OPEN = "open"

#: The Task actions after which the Task carries this decomposition's content.
CURRENT = frozenset({"created", "updated", "unchanged"})


def _norm(text: object) -> str:
    """Return the text with its whitespace collapsed, as matching compares it.

    Args:
        text: The text.

    Returns:
        The collapsed text.
    """
    return " ".join(str(text or "").split())


def _json(value: object) -> str:
    """Return compact JSON, as metadata stores it.

    Args:
        value: The value.

    Returns:
        The JSON text.
    """
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _same(stored: object, wanted: str) -> bool:
    """Return whether a metadata value read back equals the value to be written.

    Args:
        stored: The value on the bead.
        wanted: The value to write.

    Returns:
        True when writing it would change nothing.
    """
    if stored is None:
        return False
    return same_value(stored, wanted) or str(stored).lower() == wanted.lower()


def _rel(directory: Path, root: Path | None) -> str | None:
    """Return the working directory relative to the project root.

    Args:
        directory: The Epic's working directory.
        root: The project root, or None.

    Returns:
        The relative path, or None when there is no root or the directory is outside it.
    """
    if root is None:
        return None
    try:
        return str(directory.resolve().relative_to(root.resolve()))
    except ValueError:
        return None


def _strategy_line(strategy: dict | None) -> str:
    """Return a Task's test strategy as one contract line.

    Args:
        strategy: The strategy the spec states, or None.

    Returns:
        The line.
    """
    if not strategy:
        return "unknown (the spec states none)"
    env = [str(x).strip() for x in strategy.get("envMatrix") or [] if str(x).strip()]
    source = f" (from {strategy['source']})" if strategy.get("source") else ""
    return (
        f"pyramid={strategy.get('pyramid') or 'n/a'}; "
        f"coverageThreshold={strategy.get('coverageThreshold') or 'n/a'}; "
        f"envMatrix={', '.join(env) or 'n/a'}{source}"
    )


def contract_block(task: Task, root: Path | None) -> str:
    """Return the build contract appended to a Task's description.

    Args:
        task: The Task.
        root: The project root its spec paths are relative to.

    Returns:
        The Markdown block.
    """

    def listed(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items) if items else "- (none)"

    if task.surfaces is None:
        surfaces = "unknown (none declared)"
    else:
        surfaces = ", ".join(task.surfaces) or "(declared none — internal-only)"
    spec = (
        task.spec_paths[0]
        if task.spec_paths
        else "MISSING — no spec reference could be recorded for this Task"
    )
    lines = [
        "## Spec contract",
        f"Paths are relative to the project root{f' ({root})' if root else ''}.",
        f"Spec: {spec}",
    ]
    if len(task.spec_paths) > 1:
        lines.append(f"Spec documents:\n{listed(task.spec_paths)}")
    lines += [
        f"Spec sections:\n{listed(task.spec_sections)}",
        f"Requirement ids: {', '.join(task.requirement_ids) or '(none)'}",
        f"Surfaces: {surfaces}",
        f"Test strategy: {_strategy_line(task.test_strategy)}",
        f"Definition of Done:\n{listed(task.definition_of_done)}",
    ]
    return "\n".join(lines)


def task_text(task: Task, root: Path | None) -> str:
    """Return a Task's full description: its prose, then its build contract.

    Args:
        task: The Task.
        root: The project root.

    Returns:
        The description.
    """
    return "\n\n".join(x for x in (task.description, contract_block(task, root)) if x)


def task_metadata(task: Task) -> dict[str, str]:
    """Return every metadata key a Task is written with.

    Args:
        task: The Task, with its `elab_key`.

    Returns:
        The metadata.
    """
    m = {"elab_key": task.elab_key or ""}
    if task.repo_path:
        m["repoPath"] = task.repo_path
    if task.sizes:
        m.update({k: task.sizes[k] for k in SIZE_KEYS})
    if task.decision_ids:
        m["decision_ids"] = _json(list(dict.fromkeys(task.decision_ids)))
    m["spec_sections"] = _json(task.spec_sections)
    m["acceptance_criteria"] = _json(task.acceptance)
    m["definition_of_done"] = _json(task.definition_of_done)
    m["requirement_ids"] = _json(task.requirement_ids)
    m["surfaces"] = _json(task.surfaces) if task.surfaces is not None else "unknown"
    m["test_strategy"] = _json(task.test_strategy) if task.test_strategy else "unknown"
    if task.spec_paths:
        m["spec_path"] = task.spec_paths[0]
        m["spec_paths"] = _json(task.spec_paths)
        m["spec_paths_verified"] = task.verified
    return m


def _create_args(  # noqa: PLR0913 - one `bd create` flag each
    kind: str,
    *,
    title: str,
    text: str,
    parent: str,
    acceptance: list[str],
    notes: str | None,
    metadata: dict,
) -> list[str]:
    """Return the `bd create` arguments for one bead.

    Returns:
        The arguments.
    """
    args = [
        "create",
        "--silent",
        "--type",
        kind,
        "--title",
        title,
        "--description",
        text,
        "--parent",
        parent,
    ]
    if acceptance:
        args += ["--acceptance", "\n".join(acceptance)]
    if notes:
        args += ["--notes", notes]
    return [*args, "--metadata", _json(metadata)]


def _refresh(
    writer: Writer, bead: Bead, title: str, text: str, metadata: dict[str, str]
) -> bool:
    """Update an open bead's prose and metadata where they differ.

    Args:
        writer: The tracker writer.
        bead: The bead as it stands.
        title: Its title.
        text: Its description.
        metadata: Its metadata.

    Returns:
        True when anything was written.
    """
    wrote = False
    if _norm(title) != _norm(bead.title) or _norm(text) != _norm(bead.description):
        writer.bd(["update", bead.id, "--title", title, "--description", text])
        wrote = True
    changed = {k: v for k, v in metadata.items() if not _same(bead.metadata.get(k), v)}
    if changed:
        writer.metadata(bead.id, changed)
        wrote = True
    return wrote


def _children(graph: Graph, parent: str, kind: str) -> list[Bead]:
    """Return the beads of one kind directly beneath a parent, in id order.

    Args:
        graph: The tracker graph.
        parent: The parent id.
        kind: The issue type.

    Returns:
        The beads.
    """
    return sorted(
        (b for b in graph.beads.values() if b.parent == parent and b.kind == kind),
        key=lambda b: b.id,
    )


def _keyed(beads: list[Bead]) -> dict[str, Bead]:
    """Return beads by their `elab_key`, the first one winning.

    Args:
        beads: The beads.

    Returns:
        elab_key -> bead.
    """
    out: dict[str, Bead] = {}
    for b in beads:
        key = b.metadata.get("elab_key")
        if key and key not in out:
            out[key] = b
    return out


def _story_of(graph: Graph, epic_id: str, slug: str) -> Bead | None:
    """Return the Story under the Epic whose `elab_key` is `story:<slug>`.

    Args:
        graph: The tracker graph.
        epic_id: The Epic.
        slug: The Story's repository slug.

    Returns:
        The Story, or None.
    """
    return _keyed(_children(graph, epic_id, "story")).get(f"story:{slug}")


def _assign_keys(tasks: list[Task], slug: str, existing: set[str]) -> None:
    """Give each Task its durable key, in build order.

    A Task keeps the key its `reuses` names when a Task under the Story carries it and no
    earlier Task took it; otherwise its key is `task:<slug>:<title slug>`, suffixed `-2`,
    `-3` ... past the keys already taken.

    Args:
        tasks: The Tasks, in build order; each gains its `elab_key`.
        slug: The Story's repository slug.
        existing: The keys the Tasks under the Story carry.
    """
    taken: set[str] = set()
    for t in tasks:
        if t.reuses and t.reuses in existing and t.reuses not in taken:
            key = t.reuses
        else:
            base = f"task:{slug}:{elab_slug(t.title)}"
            key, n = base, 2
            while key in taken:
                key = f"{base}-{n}"
                n += 1
        taken.add(key)
        t.elab_key = key


def _story_tasks(
    graph: Graph, story: Bead, directory: Path, rel: str | None, slug: str
) -> list[Task]:
    """Return a Story's saved Tasks, each with its durable key, in build order.

    Args:
        graph: The tracker graph.
        story: The Story bead.
        directory: The Epic's working directory.
        rel: The directory relative to the project root, or None.
        slug: The Story's repository slug.

    Returns:
        The Tasks.
    """
    repo = story.metadata.get("repoPath") or ""
    saved = read_story(directory, rel, repo, slug)
    tasks = read_tasks(directory, rel, slug, repo, saved.decision_ids)
    _assign_keys(tasks, slug, set(_keyed(_children(graph, story.id, "task"))))
    return tasks


def write_story(  # noqa: PLR0913 - the caller's facts, one each
    graph: Graph,
    writer: Writer,
    epic_id: str,
    directory: Path,
    *,
    slug: str,
    repo: str,
    root: Path | None,
) -> dict:
    """Write one repository's Story under the Epic from its saved `story-<slug>.json`.

    Args:
        graph: The tracker graph, read with descriptions.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        directory: The Epic's working directory.
        slug: The repository's slug.
        repo: The repository.
        root: The project root artifact paths are recorded relative to.

    Returns:
        The Story, what was done to it, and the keyed Tasks already under it.

    Raises:
        HierarchyError: The Epic is not an open Epic.
    """
    epic = graph.beads.get(epic_id)
    if epic is None or epic.kind != "epic" or epic.closed:
        msg = f"{epic_id} is not an open Epic in this tracker"
        raise HierarchyError(msg)
    story = read_story(directory, _rel(directory, root), repo, slug)
    bead = _story_of(graph, epic_id, slug)
    existing: list[dict] = []
    if bead is None:
        args = _create_args(
            "story",
            title=story.title,
            text=story.description,
            parent=epic_id,
            acceptance=story.acceptance,
            notes=f"repoPath: {repo}",
            metadata=story.metadata,
        )
        story_id = writer.create(args, story.metadata["elab_key"])
        action = "created"
    else:
        story_id = bead.id
        wrote = bead.status == OPEN and _refresh(
            writer, bead, story.title, story.description, story.metadata
        )
        action = "updated" if wrote else "unchanged"
        existing = [
            {
                "elabKey": b.metadata["elab_key"],
                "title": b.title,
                "description": b.description[:300],
                "status": b.status,
            }
            for b in _children(graph, bead.id, "task")
            if b.metadata.get("elab_key")
        ]
    return {
        "ok": True,
        "epic": epic_id,
        "story": {
            "id": story_id,
            "elabKey": story.metadata["elab_key"],
            "action": action,
            "title": story.title,
            "description": story.description,
            "decisionIds": story.decision_ids,
        },
        "existingTasks": existing,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "created": int(action == "created"),
            "updated": int(action == "updated"),
        },
    }


def _write_task(
    writer: Writer, story: Bead, task: Task, bead: Bead | None, root: Path | None
) -> tuple[str, str]:
    """Create one Task, or update it when it is open.

    Args:
        writer: The tracker writer.
        story: The Story it sits under.
        task: The Task, with its `elab_key`.
        bead: The bead carrying its `elab_key`, or None.
        root: The project root spec paths are relative to.

    Returns:
        Its id, and `created`, `updated`, `unchanged` or `unchanged-started`.
    """
    text = task_text(task, root)
    meta = task_metadata(task)
    if bead is None:
        args = _create_args(
            "task",
            title=task.title,
            text=text,
            parent=story.id,
            acceptance=task.acceptance,
            notes=f"repoPath: {task.repo_path}" if task.repo_path else None,
            metadata=meta,
        )
        return writer.create(args, task.elab_key or task.key), "created"
    if bead.status != OPEN:
        return bead.id, "unchanged-started"
    wrote = _refresh(writer, bead, task.title, text, meta)
    return bead.id, "updated" if wrote else "unchanged"


def _write_story_edges(
    writer: Writer,
    graph: Graph,
    derived: set[tuple[str, str]],
    refreshed: list[str],
    keyed: set[str],
) -> dict[str, int]:
    """Add the derived edges within a Story and remove the ones no longer derived.

    Args:
        writer: The tracker writer.
        graph: The tracker graph.
        derived: `(blocker id, blocked id)` for every derived edge.
        refreshed: The open Tasks matched rather than created.
        keyed: The ids of the keyed Tasks under the Story.

    Returns:
        The edges added, removed and already standing.
    """
    counts = {"added": 0, "removed": 0, "standing": 0}
    for frm, to in sorted(derived):
        bead = graph.beads.get(to)
        if bead is not None and frm in bead.blockers:
            counts["standing"] += 1
            continue
        writer.bd(["dep", "add", to, frm, "--type", "blocks"])
        counts["added"] += 1
    for task_id in refreshed:
        for blocker in graph.beads[task_id].blockers:
            if blocker in keyed and (blocker, task_id) not in derived:
                writer.bd(["dep", "remove", task_id, blocker])
                counts["removed"] += 1
    return counts


def _fingerprint(writer: Writer, graph: Graph, sized: list[str]) -> int:
    """Write each sized Task's judging fingerprint where it differs.

    Args:
        writer: The tracker writer.
        graph: The tracker as it stands after the Task writes.
        sized: The Tasks whose judged size describes the content they now carry.

    Returns:
        The number of fingerprints written.
    """
    if not sized:
        return 0
    prints = fingerprints(graph.records, SCOPE_JUDGING)
    written = 0
    for task_id in sized:
        current = prints.get(task_id, "")
        bead = graph.beads.get(task_id)
        if current and bead and bead.metadata.get(JUDGED_HASH_KEY) != current:
            writer.metadata(task_id, {JUDGED_HASH_KEY: current})
            written += 1
    return written


def write_tasks(  # noqa: PLR0913 - the caller's facts, one each
    graph: Graph,
    writer: Writer,
    epic_id: str,
    directory: Path,
    *,
    slug: str,
    root: Path | None,
    reload: Callable[[], Graph],
) -> dict:
    """Write one Story's Tasks, the edges between them, and their size fingerprints.

    An open Task the decomposition no longer contains is closed; a Task carrying no
    `elab_key` is never touched.

    Args:
        graph: The tracker graph, read with descriptions.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        directory: The Epic's working directory.
        slug: The Story's repository slug.
        root: The project root spec paths are recorded relative to.
        reload: Reads the tracker again, after the writes.

    Returns:
        Each Task and what was done to it, the Tasks closed, the edge writes, and the
        number of fingerprints written.

    Raises:
        HierarchyError: No Story `story:<slug>` is under the Epic.
    """
    story = _story_of(graph, epic_id, slug)
    if story is None:
        msg = f"no Story story:{slug} under {epic_id}: a Story is written before its Tasks"
        raise HierarchyError(msg)
    tasks = _story_tasks(graph, story, directory, _rel(directory, root), slug)
    existing = _keyed(_children(graph, story.id, "task"))
    written = {
        t.key: _write_task(writer, story, t, existing.get(t.elab_key or ""), root)
        for t in tasks
    }
    wanted = {t.elab_key for t in tasks}
    closed = [
        b.id for key, b in existing.items() if key not in wanted and b.status == OPEN
    ]
    for bead_id in closed:
        reason = (
            f"Closed by elaboration of {epic_id}: the current decomposition of this "
            "Story no longer contains this Task, and no work had started on it."
        )
        writer.bd(["close", bead_id, "--reason", reason])
    edges = _write_story_edges(
        writer,
        graph,
        {(written[d][0], written[t.key][0]) for t in tasks for d in t.depends_on},
        [i for i, action in written.values() if action in {"updated", "unchanged"}],
        {b.id for b in existing.values()},
    )
    sized = [
        written[t.key][0] for t in tasks if t.sizes and written[t.key][1] in CURRENT
    ]
    fingerprinted = _fingerprint(
        writer, graph if writer.dry_run or not sized else reload(), sized
    )
    actions = [action for _, action in written.values()]
    return {
        "ok": True,
        "epic": epic_id,
        "story": {"id": story.id, "elabKey": f"story:{slug}"},
        "tasks": [
            {
                "key": t.key,
                "elabKey": t.elab_key,
                "id": written[t.key][0],
                "action": written[t.key][1],
                "title": t.title,
                "dependsOn": t.depends_on,
            }
            for t in tasks
        ],
        "closed": closed,
        "edges": edges,
        "fingerprinted": fingerprinted,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "created": actions.count("created"),
            "updated": actions.count("updated"),
            "unchanged": actions.count("unchanged")
            + actions.count("unchanged-started"),
            "closed": len(closed),
        },
    }


def _resolve_span(
    graph: Graph, epic_id: str, directory: Path, repos: list[str]
) -> dict[str, tuple[str, str]]:
    """Return each written Task of the span by its `S<i>-<local key>` name.

    The Story of the repository at index i of the span is `S<i+1>`.

    Args:
        graph: The tracker graph.
        epic_id: The Epic.
        directory: The Epic's working directory.
        repos: The span, in its ruled order.

    Returns:
        Name -> (Task id, Story id).
    """
    resolved: dict[str, tuple[str, str]] = {}
    for index, (_repo, slug) in enumerate(repo_slugs(repos).items()):
        story = _story_of(graph, epic_id, slug)
        if story is None or not (directory / f"tasks-{slug}.json").is_file():
            continue
        existing = _keyed(_children(graph, story.id, "task"))
        for t in _story_tasks(graph, story, directory, None, slug):
            bead = existing.get(t.elab_key or "")
            if bead is not None:
                resolved[f"S{index + 1}-{t.key}"] = (bead.id, story.id)
    return resolved


def _accept(
    saved: list[dict], resolved: dict[str, tuple[str, str]]
) -> tuple[list[dict], list[dict], set[tuple[str, str]]]:
    """Split the saved edges into accepted and rejected ones.

    Args:
        saved: The saved edges.
        resolved: Name -> (Task id, Story id).

    Returns:
        The accepted edges, the rejected ones with the reason, and `(blocker id,
        blocked id)` for each accepted edge.
    """
    accepted: list[dict] = []
    rejected: list[dict] = []
    pairs: set[tuple[str, str]] = set()
    for e in saved:
        frm, to = str(e.get("from") or ""), str(e.get("to") or "")
        a, b = resolved.get(frm), resolved.get(to)
        if a is None or b is None:
            why = "an end is not a Task of this run"
        elif a[1] == b[1]:
            why = "both ends are in the same Story"
        elif (a[0], b[0]) in pairs:
            why = "a duplicate"
        else:
            pairs.add((a[0], b[0]))
            accepted.append({
                "from": frm,
                "to": to,
                "kind": e.get("kind"),
                "reason": e.get("reason"),
            })
            continue
        rejected.append({"from": frm, "to": to, "reason": why})
    return accepted, rejected, pairs


def write_task_edges(
    graph: Graph, writer: Writer, epic_id: str, directory: Path, repos: list[str]
) -> dict:
    """Write the saved `blocks` edges between Tasks of different Stories of the Epic.

    An open Task loses each blocker in another of the Epic's Stories that the saved edges
    no longer name.

    Args:
        graph: The tracker graph, read with descriptions.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        directory: The Epic's working directory.
        repos: The span, in its ruled order.

    Returns:
        The edges written or standing, the edges rejected, and the counts.

    Raises:
        HierarchyError: The mapper reported a cycle, or the edges close one over the
            Epic's Task graph.
    """
    acyclic, saved = read_task_deps(directory)
    if not acyclic:
        msg = "task-deps.json: the mapper reported the edges between Stories imply a cycle"
        raise HierarchyError(msg)
    accepted, rejected, pairs = _accept(
        saved, _resolve_span(graph, epic_id, directory, repos)
    )
    story_of = {
        bead.id: story.id
        for story in _children(graph, epic_id, "story")
        for bead in _keyed(_children(graph, story.id, "task")).values()
    }
    intra = [
        (blocker, task_id)
        for task_id, story_id in story_of.items()
        for blocker in graph.beads[task_id].blockers
        if story_of.get(blocker) == story_id
    ]
    if build_order(sorted(story_of), [*intra, *sorted(pairs)]) is None:
        msg = "the saved edges between Stories close a cycle over the Task graph"
        raise HierarchyError(msg)
    counts = {"added": 0, "removed": 0, "standing": 0}
    for a, b in sorted(pairs):
        if a in graph.beads[b].blockers:
            counts["standing"] += 1
            continue
        writer.bd(["dep", "add", b, a, "--type", "blocks"])
        counts["added"] += 1
    for task_id, story_id in sorted(story_of.items()):
        bead = graph.beads[task_id]
        if bead.status != OPEN:
            continue
        for blocker in bead.blockers:
            other = story_of.get(blocker)
            if other and other != story_id and (blocker, task_id) not in pairs:
                writer.bd(["dep", "remove", task_id, blocker])
                counts["removed"] += 1
    return {
        "ok": True,
        "epic": epic_id,
        "edges": accepted,
        "rejected": rejected,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": counts,
    }
