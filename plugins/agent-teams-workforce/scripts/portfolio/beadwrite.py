"""Write one Story, one Task, or one Task's edges to Tasks in other Stories into beads.

Each command writes ONE bead. It reads the document its elaboration step saved in the Epic's
working directory and is keyed by the durable `elab_key`: a Story or Task no bead under its
parent carries is created, an open one that carries it is updated where it differs, and any
other is left as it is. The plans (`plan_story_tasks`, `plan_task_edges`) read the saved
documents only and run no `bd` command. A write that fails raises `GraphError` from the
writer, and a rerun repairs it, because every write is keyed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from beadgraph import SCOPE_JUDGING, bead_of, children, fingerprints, same_value
from hierarchy import (
    SIZE_KEYS,
    HierarchyError,
    Task,
    build_order,
    check_cds_contract,
    check_detailed_work,
    elab_slug,
    read_story,
    read_task_deps,
    read_tasks,
    repo_slugs,
)
from scoring import JUDGED_HASH_KEY

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Bead, Graph, Writer

#: The one status a matched Story or Task is rewritten in.
OPEN = "open"

#: The priority `bd create` gives a bead when none is passed.
DEFAULT_PRIORITY = 2


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


#: What each design source of a web-ui Task means for the build, as the contract states it.
DESIGN_SOURCE_TEXT = {
    "bundle": "built from the cds bundle the owner supplied, and audited against it",
    "cds": "designed with the CDS design system (cds:cds-ui-author and the project's "
    "design system config), and audited against the live design system",
    "none": "changes no design (copy, or data wired into an existing element); built "
    "like any other code change, with no cds design step or audit",
}


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
    if task.cds_design_source:
        lines.append(
            f"Design source: {task.cds_design_source} — "
            + DESIGN_SOURCE_TEXT.get(task.cds_design_source, "")
        )
    if len(task.cds_artifacts) == 1:
        art = task.cds_artifacts[0]
        lines.append(f"cds artifact: {art['kind']} {art['slug']}")
    if task.cds_bundle_path or task.cds_build_specs:
        lines += [
            f"cds bundle: {task.cds_bundle_path or '(none resolved)'}",
            f"cds build specs:\n{listed(task.cds_build_specs)}",
        ]
    return "\n".join(lines)


def task_text(task: Task, root: Path | None) -> str:
    """Return a Task's full description: its repository, its prose, then its build contract.

    Args:
        task: The Task.
        root: The project root.

    Returns:
        The description.
    """
    repository = f"Repository: {task.repo_path} — work only in this repository."
    return "\n\n".join(
        x for x in (repository, task.description, contract_block(task, root)) if x
    )


def task_metadata(task: Task) -> dict[str, str]:
    """Return every metadata key a Task is written with.

    Args:
        task: The Task, with its `elab_key`.

    Returns:
        The metadata.
    """
    m = {"elab_key": task.elab_key or "", "repoPath": task.repo_path}
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
    if task.cds_design_source:
        m["cds_design_source"] = task.cds_design_source
    if len(task.cds_artifacts) == 1:
        m["cds_artifact"] = _json(task.cds_artifacts[0])
    if task.cds_bundle_path:
        m["cds_bundle_path"] = task.cds_bundle_path
    if task.cds_build_specs:
        m["cds_build_specs"] = _json(task.cds_build_specs)
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
    """Update an open bead's prose and metadata where they differ, in one `bd update`.

    Args:
        writer: The tracker writer.
        bead: The bead as it stands.
        title: Its title.
        text: Its description.
        metadata: Its metadata; each key is merged onto the bead's.

    Returns:
        True when anything was written.
    """
    args: list[str] = []
    if _norm(title) != _norm(bead.title) or _norm(text) != _norm(bead.description):
        args += ["--title", title, "--description", text]
    for key, value in metadata.items():
        if not _same(bead.metadata.get(key), value):
            args += ["--set-metadata", f"{key}={value}"]
    if not args:
        return False
    writer.bd(["update", bead.id, *args])
    return True


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


def _assign_keys(tasks: list[Task], slug: str) -> None:
    """Give each Task its durable key, in build order.

    A Task keeps the key its `reuses` names when no earlier Task took it; otherwise its key
    is `task:<slug>:<title slug>`, suffixed `-2`, `-3` ... past the keys already taken.

    Args:
        tasks: The Tasks, in build order; each gains its `elab_key`.
        slug: The Story's repository slug.
    """
    taken: set[str] = set()
    for t in tasks:
        if t.reuses and t.reuses not in taken:
            key = t.reuses
        else:
            base = f"task:{slug}:{elab_slug(t.title)}"
            key, n = base, 2
            while key in taken:
                key = f"{base}-{n}"
                n += 1
        taken.add(key)
        t.elab_key = key


def plan_tasks(
    directory: Path,
    rel: str | None,
    slug: str,
    repo: str,
    packages_dir: str | None = None,
) -> list[Task]:
    """Return a Story's saved Tasks, each with its durable key, in build order.

    Reads `story-<slug>.json` and `tasks-<slug>.json` only; runs no `bd` command.

    Args:
        directory: The Epic's working directory.
        rel: The directory relative to the project root, or None.
        slug: The Story's repository slug.
        repo: The Story's repository.
        packages_dir: The packages directory a cited cds bundle must sit in, or None.

    Returns:
        The Tasks.

    Raises:
        HierarchyError: The file holds no `tasks` list, its edges form a cycle, a Task
            cites no delta item the repository's detailing marks as work, or a web-ui
            Task's contract does not match its design source.
    """
    saved = read_story(directory, rel, repo, slug)
    tasks = read_tasks(directory, rel, slug, repo, saved.decision_ids, packages_dir)
    check_detailed_work(directory, slug, tasks)
    check_cds_contract(slug, tasks)
    _assign_keys(tasks, slug)
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
        The Story, what was done to it, the keyed Tasks already under it, and the open
        Tasks of other Epics built in the same repository.
    """
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
        "otherEpicTasks": other_epic_tasks(graph, epic_id, repo),
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "id": story_id,
            "elabKey": story.metadata["elab_key"],
            "action": action,
            "created": int(action == "created"),
            "updated": int(action == "updated"),
        },
    }


def _same_repo(a: object, b: str) -> bool:
    """Whether two repository paths name the same checkout.

    Args:
        a: A recorded repository path.
        b: The repository path to compare with.

    Returns:
        True when both, with trailing separators removed, are the same path.
    """
    return isinstance(a, str) and a.strip().rstrip("/") == b.strip().rstrip("/")


def other_epic_tasks(graph: Graph, epic_id: str, repo: str) -> list[dict]:
    """Return the open Tasks of other Epics that are built in this repository.

    A Task is built in the repository its `repoPath` metadata names, or, when it records
    none, the one its Story records.

    Args:
        graph: The tracker graph, read with descriptions.
        epic_id: The Epic being elaborated; its own Tasks are left out.
        repo: The repository.

    Returns:
        Each Task's id, title, the start of its description, its status and its Epic.
    """
    out = []
    for task in graph.of_kind("task"):
        if task.closed:
            continue
        parent = graph.beads.get(task.parent) if task.parent else None
        where = task.metadata.get("repoPath") or (
            parent.metadata.get("repoPath") if parent else None
        )
        if not _same_repo(where, repo):
            continue
        epic = graph.epic_of(task.id)
        if epic is not None and epic.id == epic_id:
            continue
        out.append(
            {
                "id": task.id,
                "title": task.title,
                "description": task.description[:300],
                "status": task.status,
                "epic": epic.id if epic else None,
            }
        )
    return out


def plan_story_tasks(
    directory: Path,
    *,
    slug: str,
    repo: str,
    root: Path | None,
    packages_dir: str | None = None,
) -> dict:
    """Return a Story's Tasks in build order with their durable keys; runs no `bd` command.

    Args:
        directory: The Epic's working directory.
        slug: The Story's repository slug.
        repo: The Story's repository.
        root: The project root spec paths are recorded relative to.
        packages_dir: The packages directory a cited cds bundle must sit in, or None.

    Returns:
        Each Task's local key, `elab_key`, title and the local keys it depends on.
    """
    tasks = plan_tasks(directory, _rel(directory, root), slug, repo, packages_dir)
    return {
        "ok": True,
        "slug": slug,
        "tasks": [
            {
                "key": t.key,
                "elabKey": t.elab_key,
                "title": t.title,
                "dependsOn": t.depends_on,
                "blockedByExternal": t.blocked_by_external,
                **(
                    {"designSource": t.cds_design_source} if t.cds_design_source else {}
                ),
            }
            for t in tasks
        ],
        "summary": {"tasks": len(tasks)},
    }


def _judged_hash(title: str, text: str, priority: object) -> str:
    """Return the judging fingerprint of a Task carrying this content.

    Args:
        title: Its title.
        text: Its description.
        priority: Its priority as `bd` reports it.

    Returns:
        The fingerprint.
    """
    record = {
        "id": "task",
        "title": title,
        "description": text,
        "issue_type": "task",
        "priority": priority,
    }
    return fingerprints([record], SCOPE_JUDGING).get("task", "")


def write_task(  # noqa: PLR0913 - the caller's facts, one each
    writer: Writer,
    epic_id: str,
    directory: Path,
    *,
    slug: str,
    repo: str,
    key: str,
    root: Path | None,
    external: list[str] | None = None,
    packages_dir: str | None = None,
) -> dict:
    """Write ONE Task of a Story, and its `blocks` edges to the Story's other Tasks.

    The Task sits under the Epic's Story whose `elab_key` is `story:<slug>`, found in beads.
    The Task is created, or updated when it is open, keyed by its `elab_key`. Its blockers
    are the Tasks of the Story it depends on, which are written before it. One `bd list`
    finds the Story and one reads its Tasks; one `bd create`, or one `bd update` plus one
    `bd dep add` and a `bd dep remove` per blocker it no longer depends on, writes it.

    Args:
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic whose Story the Task sits under.
        directory: The Epic's working directory.
        slug: The Story's repository slug.
        repo: The Story's repository.
        key: The Task's local key in `tasks-<slug>.json`, as `plan-tasks` returns it.
        root: The project root spec paths are recorded relative to.
        external: Tasks of other Epics this Task is blocked by, beside the ones its saved
            `blockedByExternal` names.
        packages_dir: The packages directory a cited cds bundle must sit in, or None.

    Returns:
        The Task, what was done to it, its edge writes, and the blockers it carries
        outside the Story.

    Raises:
        HierarchyError: The repository is empty, the key names no Task, the Epic has no
            Story for the slug, a Task
            it depends on is not written, or an external blocker is a Task of its own Story.
    """
    if not repo.strip():
        msg = f"Task {key} of story:{slug} has no repository: a Task is never written without one"
        raise HierarchyError(msg)
    tasks = plan_tasks(directory, _rel(directory, root), slug, repo, packages_dir)
    by_key = {t.key: t for t in tasks}
    task = by_key.get(key)
    if task is None:
        msg = f"tasks-{slug}.json has no Task {key}"
        raise HierarchyError(msg)
    stories = _keyed(
        sorted(
            (bead_of(r) for r in children(writer.repo, epic_id, "story")),
            key=lambda b: b.id,
        )
    )
    story = stories.get(f"story:{slug}")
    if story is None:
        msg = f"{epic_id} has no Story story:{slug}: its Story is written before its Tasks"
        raise HierarchyError(msg)
    story_id = story.id
    records = children(writer.repo, story_id, "task")
    priority = {str(r["id"]): r.get("priority") for r in records}
    keyed = _keyed(sorted((bead_of(r) for r in records), key=lambda b: b.id))
    blockers: list[str] = []
    for dep in task.depends_on:
        blocker = keyed.get(by_key[dep].elab_key or "")
        if blocker is None:
            msg = (
                f"{key} depends on {dep} ({by_key[dep].elab_key}), which is not under "
                f"{story_id}: a Task is written after the Tasks it depends on"
            )
            raise HierarchyError(msg)
        blockers.append(blocker.id)
    story_ids = {b.id for b in keyed.values()}
    outer = list(dict.fromkeys([*task.blocked_by_external, *(external or [])]))
    inner = [b for b in outer if b in story_ids]
    if inner:
        msg = (
            f"{key}: {', '.join(inner)} are Tasks of {story_id}; an edge inside the Story "
            f"is a saved edge, not an external blocker"
        )
        raise HierarchyError(msg)
    bead = keyed.get(task.elab_key or "")
    text = task_text(task, root)
    meta = task_metadata(task)
    if task.sizes:
        meta[JUDGED_HASH_KEY] = _judged_hash(
            task.title, text, priority.get(bead.id) if bead else DEFAULT_PRIORITY
        )
    edges = {"added": 0, "removed": 0, "standing": 0}
    outside: list[str] = []
    if bead is None:
        args = _create_args(
            "task",
            title=task.title,
            text=text,
            parent=story_id,
            acceptance=task.acceptance,
            notes=f"repoPath: {task.repo_path}",
            metadata=meta,
        )
        if blockers or outer:
            args += [
                "--deps",
                ",".join(f"blocked-by:{b}" for b in [*blockers, *outer]),
            ]
        task_id, action = writer.create(args, task.elab_key or key), "created"
        edges["added"] = len(blockers) + len(outer)
        outside = outer
    elif bead.status != OPEN:
        task_id, action = bead.id, "unchanged-started"
    else:
        task_id = bead.id
        action = (
            "updated" if _refresh(writer, bead, task.title, text, meta) else "unchanged"
        )
        add = [b for b in [*blockers, *outer] if b not in bead.blockers]
        drop = [b for b in bead.blockers if b in story_ids and b not in blockers]
        if add:
            lines = [
                _json({"issue_id": bead.id, "depends_on_id": b, "type": "blocks"})
                for b in add
            ]
            writer.bd(["dep", "add", "--file", "-"], "\n".join(lines) + "\n")
        for b in drop:
            writer.bd(["dep", "remove", bead.id, b])
        edges = {
            "added": len(add),
            "removed": len(drop),
            "standing": len(blockers) + len(outer) - len(add),
        }
        outside = list(
            dict.fromkeys([*(b for b in bead.blockers if b not in story_ids), *outer])
        )
    return {
        "ok": True,
        "story": story_id,
        "task": {
            "key": task.key,
            "elabKey": task.elab_key,
            "id": task_id,
            "action": action,
            "title": task.title,
            "dependsOn": task.depends_on,
            "outsideBlockers": outside,
        },
        "edges": edges,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {"key": task.key, "id": task_id, "action": action, **edges},
    }


def _span_tasks(
    directory: Path, repos: list[str]
) -> tuple[dict[str, str], list[tuple[str, str]], dict[str, str]]:
    """Return every saved Task of the span by its `S<i>-<local key>` name.

    The Story of the repository at index i of the span is `S<i+1>`. Reads the saved
    documents only; runs no `bd` command.

    Args:
        directory: The Epic's working directory.
        repos: The span, in its ruled order.

    Returns:
        Name -> the Story's slug, the `(from, to)` edges within each Story by name, and
        name -> the Task's `elab_key`.
    """
    slug_of: dict[str, str] = {}
    intra: list[tuple[str, str]] = []
    elab: dict[str, str] = {}
    for index, (repo, slug) in enumerate(repo_slugs(repos).items()):
        if not (directory / f"tasks-{slug}.json").is_file():
            continue
        story = f"S{index + 1}"
        for t in plan_tasks(directory, None, slug, repo):
            name = f"{story}-{t.key}"
            slug_of[name] = slug
            elab[name] = t.elab_key or ""
            intra += [(f"{story}-{d}", name) for d in t.depends_on]
    return slug_of, intra, elab


def _accept(
    saved: list[dict], slug_of: dict[str, str]
) -> tuple[list[dict], list[dict], set[tuple[str, str]]]:
    """Split the saved edges into accepted and rejected ones.

    Args:
        saved: The saved edges.
        slug_of: Task name -> its Story's slug.

    Returns:
        The accepted edges, the rejected ones with the reason, and `(from, to)` by name
        for each accepted edge.
    """
    accepted: list[dict] = []
    rejected: list[dict] = []
    pairs: set[tuple[str, str]] = set()
    for e in saved:
        frm, to = str(e.get("from") or ""), str(e.get("to") or "")
        a, b = slug_of.get(frm), slug_of.get(to)
        if a is None or b is None:
            why = "an end is not a Task of this run"
        elif a == b:
            why = "both ends are in the same Story"
        elif (frm, to) in pairs:
            why = "a duplicate"
        else:
            pairs.add((frm, to))
            accepted.append(
                {
                    "from": frm,
                    "to": to,
                    "kind": e.get("kind"),
                    "reason": e.get("reason"),
                }
            )
            continue
        rejected.append({"from": frm, "to": to, "reason": why})
    return accepted, rejected, pairs


def plan_task_edges(directory: Path, repos: list[str]) -> dict:
    """Return the saved Task edges between Stories, checked; runs no `bd` command.

    Args:
        directory: The Epic's working directory.
        repos: The span, in its ruled order.

    Returns:
        The accepted edges, the rejected ones, and each blocked Task's blockers by name.

    Raises:
        HierarchyError: The edges close a cycle over the Epic's Task graph.
    """
    saved = read_task_deps(directory)
    slug_of, intra, _elab = _span_tasks(directory, repos)
    accepted, rejected, pairs = _accept(saved, slug_of)
    if build_order(sorted(slug_of), [*intra, *sorted(pairs)]) is None:
        msg = "the saved edges between Stories close a cycle over the Task graph"
        raise HierarchyError(msg)
    blockers: dict[str, list[str]] = {}
    for frm, to in sorted(pairs):
        blockers.setdefault(to, []).append(frm)
    return {
        "ok": True,
        "edges": accepted,
        "rejected": rejected,
        "blockers": blockers,
        "summary": {
            "edges": len(accepted),
            "rejected": len(rejected),
            "blockers": blockers,
        },
    }


def write_task_edges(  # noqa: PLR0913 - the caller's facts, one each
    graph: Graph,
    writer: Writer,
    epic_id: str,
    directory: Path,
    repos: list[str],
    name: str,
) -> dict:
    """Write ONE Task's `blocks` edges to Tasks in the Epic's other Stories.

    The Task gains each saved blocker it lacks, in one `bd dep add`, and, when it is open,
    loses each blocker in another of the Epic's Stories that the saved edges no longer name.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        directory: The Epic's working directory.
        repos: The span, in its ruled order.
        name: The Task, as `S<i>-<local key>`.

    Returns:
        The Task, its saved edges, and the edges added, removed and standing.

    Raises:
        HierarchyError: The saved edges are refused, or the Task or a blocker is not
            written.
    """
    plan = plan_task_edges(directory, repos)
    slug_of, _intra, elab = _span_tasks(directory, repos)

    def bead_named(n: str) -> Bead:
        story = _story_of(graph, epic_id, slug_of.get(n, ""))
        bead = (
            _keyed(_children(graph, story.id, "task")).get(elab.get(n, ""))
            if story
            else None
        )
        if bead is None:
            msg = f"Task {n} ({elab.get(n)}) is not written under {epic_id}"
            raise HierarchyError(msg)
        return bead

    task = bead_named(name)
    wanted = [bead_named(n).id for n in plan["blockers"].get(name, [])]
    story_of = {
        bead.id: story.id
        for story in _children(graph, epic_id, "story")
        for bead in _keyed(_children(graph, story.id, "task")).values()
    }
    add = [b for b in wanted if b not in task.blockers]
    drop = (
        []
        if task.status != OPEN
        else [
            b
            for b in task.blockers
            if story_of.get(b) not in {None, task.parent} and b not in wanted
        ]
    )
    if add:
        lines = [
            _json({"issue_id": task.id, "depends_on_id": b, "type": "blocks"})
            for b in add
        ]
        writer.bd(["dep", "add", "--file", "-"], "\n".join(lines) + "\n")
    for b in drop:
        writer.bd(["dep", "remove", task.id, b])
    counts = {
        "added": len(add),
        "removed": len(drop),
        "standing": len(wanted) - len(add),
    }
    return {
        "ok": True,
        "epic": epic_id,
        "task": {"name": name, "id": task.id},
        "edges": [e for e in plan["edges"] if e["to"] == name],
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {"name": name, "id": task.id, **counts},
    }


def _task_beads(
    graph: Graph, epic_id: str, directory: Path, repos: list[str]
) -> dict[str, Bead]:
    """Return the bead of every saved Task of the span that beads holds, by its name.

    Args:
        graph: The tracker graph.
        epic_id: The Epic.
        directory: The Epic's working directory.
        repos: The span, in its ruled order.

    Returns:
        `S<i>-<local key>` -> the Task's bead.
    """
    slug_of, _intra, elab = _span_tasks(directory, repos)
    out: dict[str, Bead] = {}
    for name, slug in slug_of.items():
        story = _story_of(graph, epic_id, slug)
        bead = (
            _keyed(_children(graph, story.id, "task")).get(elab[name])
            if story
            else None
        )
        if bead is not None:
            out[name] = bead
    return out


def _carrying(
    graph: Graph, epic_id: str, directory: Path, repos: list[str]
) -> list[str]:
    """Return the saved Tasks whose open bead carries a blocker in another of the Epic's Stories.

    Args:
        graph: The tracker graph.
        epic_id: The Epic.
        directory: The Epic's working directory.
        repos: The span, in its ruled order.

    Returns:
        The Tasks, as `S<i>-<local key>`.
    """
    story_of = {
        bead.id: story.id
        for story in _children(graph, epic_id, "story")
        for bead in _children(graph, story.id, "task")
    }
    return [
        name
        for name, bead in _task_beads(graph, epic_id, directory, repos).items()
        if bead.status == OPEN
        and any(story_of.get(b) not in {None, bead.parent} for b in bead.blockers)
    ]


def unpersisted(
    graph: Graph, epic_id: str, directory: Path, repos: list[str]
) -> list[str]:
    """Return what the span's saved documents name that beads does not hold.

    Every repository of the span has its saved `story-<slug>.json` and `tasks-<slug>.json`,
    its Story under the Epic, and a Task bead under that Story for every saved Task; every
    open Task carries its saved blockers in its own Story and the Tasks of other Epics its
    saved `blockedByExternal` names, and, when `task-deps.json` is saved, its blockers in
    other Stories. Reads the documents and the graph only.

    Args:
        graph: The tracker graph.
        epic_id: The Epic.
        directory: The Epic's working directory.
        repos: The span, in its ruled order.

    Returns:
        One line per missing document, Story, Task or edge; empty when all are held.
    """
    missing: list[str] = []
    for repo, slug in repo_slugs(repos).items():
        for name in (f"story-{slug}.json", f"tasks-{slug}.json"):
            if not (directory / name).is_file():
                missing.append(f"{name} is not saved")
        story = _story_of(graph, epic_id, slug)
        if story is None:
            missing.append(f"Story story:{slug} is not under {epic_id}")
            continue
        if not (directory / f"tasks-{slug}.json").is_file():
            continue
        try:
            tasks = plan_tasks(directory, None, slug, repo)
        except HierarchyError as exc:
            missing.append(str(exc))
            continue
        keyed = _keyed(_children(graph, story.id, "task"))
        for t in tasks:
            bead = keyed.get(t.elab_key or "")
            if bead is None:
                missing.append(f"Task {t.elab_key} is not under {story.id}")
                continue
            if bead.status != OPEN:
                continue
            for dep in t.depends_on:
                blocker = next((x for x in tasks if x.key == dep), None)
                held = keyed.get(blocker.elab_key or "") if blocker else None
                if held is None or held.id not in bead.blockers:
                    missing.append(f"edge {dep} -> {t.key} in story:{slug}")
            missing.extend(
                f"edge {b} -> {t.key} in story:{slug} from another Epic"
                for b in t.blocked_by_external
                if b not in bead.blockers
            )
    if not missing and (directory / "task-deps.json").is_file():
        try:
            blockers = plan_task_edges(directory, repos)["blockers"]
        except HierarchyError as exc:
            return [str(exc)]
        beads = _task_beads(graph, epic_id, directory, repos)
        for to, froms in blockers.items():
            for frm in froms:
                if beads[frm].id not in beads[to].blockers:
                    missing.append(f"edge {frm} -> {to} between Stories")
    return missing


def write_all_task_edges(  # noqa: PLR0913 - the caller's facts, one each
    graph: Graph,
    writer: Writer,
    epic_id: str,
    directory: Path,
    repos: list[str],
    also: list[str],
) -> dict:
    """Write the saved edges to other Stories of every Task that has them, one Task at a time.

    A Task the saved edges name no blocker for is written too when its bead carries a
    blocker in another of the Epic's Stories, so an edge the saved edges no longer name
    is removed.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        directory: The Epic's working directory.
        repos: The span, in its ruled order.
        also: Tasks, as `S<i>-<local key>`, whose edges to other Stories are
            written even when the saved edges name no blocker for them.

    Returns:
        Each Task written with its counts, and a summary carrying the blockers by
        name, the totals and the Tasks written.

    Raises:
        HierarchyError: The saved edges are refused, or a Task or a blocker is not
            written.
    """
    plan = plan_task_edges(directory, repos)
    names = list(
        dict.fromkeys(
            [*plan["blockers"], *also, *_carrying(graph, epic_id, directory, repos)]
        )
    )
    tasks = [
        write_task_edges(graph, writer, epic_id, directory, repos, name)["summary"]
        for name in names
    ]
    totals = {k: sum(t[k] for t in tasks) for k in ("added", "removed", "standing")}
    return {
        "ok": True,
        "epic": epic_id,
        "tasks": tasks,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "edges": plan["summary"]["edges"],
            "rejected": plan["summary"]["rejected"],
            "blockers": plan["blockers"],
            "written": names,
            **totals,
        },
    }
