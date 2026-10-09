"""Write one Story, one Task, or one Task's edges to Tasks in other Stories into beads.

Each command writes ONE bead. It reads the document its elaboration step saved in the Epic's
working directory and is keyed by the durable `elab_key`: a Story or Task no bead under its
parent carries is created, an open one that carries it is updated where it differs, and any
other is left as it is. The plans (`plan_story_tasks`, `plan_task_edges`) read the saved
documents only and run no `bd` command. A write that fails raises `GraphError` from the
writer, and a rerun repairs it, because every write is keyed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from beadgraph import (
    SCOPE_JUDGING,
    bead_of,
    children,
    fingerprints,
    same_value,
)
from hierarchy import (
    SIZE_KEYS,
    _sizes,
    HierarchyError,
    Task,
    build_order,
    check_cds_contract,
    check_detailed_work,
    delta_requires,
    derive_prerequisites,
    detailed_items,
    elab_slug,
    item_briefs,
    read_story,
    read_task_deps,
    read_tasks,
    repo_slugs,
    str_list,
    take_warnings,
    uncited_work,
    work_items,
)
from scoring import JUDGED_HASH_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator

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


def _item_order(item: str) -> list:
    """Return the natural sort key of a delta item id, so D2 sorts before D10.

    Args:
        item: The id.

    Returns:
        Its text and number runs, the numbers as ints.
    """
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", item)]


def _work_cited(ids: list[str], work: list[str] | None) -> list[str]:
    """Return the work items among a Task's cited ids, naturally sorted.

    Args:
        ids: The ids the Task cites in `requirementIds`.
        work: The ids the repository's detailing marks add, modify or remove, or None.

    Returns:
        The cited work item ids, each once, in natural order.
    """
    marked = set(work or [])
    return sorted({i.strip() for i in ids if i.strip() in marked}, key=_item_order)


def _title_key(task: Task, slug: str) -> str:
    """Return the key a Task got from its title before keys came from its work items.

    Args:
        task: The Task.
        slug: The Story's repository slug.

    Returns:
        `task:<slug>:<title slug>`.
    """
    return f"task:{slug}:{elab_slug(task.title)}"


def _assign_keys(tasks: list[Task], slug: str, work: list[str] | None) -> None:
    """Give each Task its durable key, in build order.

    A Task keeps the key its `reuses` names when no earlier Task took it. Otherwise its key
    is `task:<slug>:items:<the work items it cites, naturally sorted>`, so a Task re-decomposed
    under another title keeps its key; a Task citing no work item is keyed by its title.
    Two Tasks with the same base key are suffixed `-2`, `-3` ... in build order.

    Args:
        tasks: The Tasks, in build order; each gains its `elab_key`.
        slug: The Story's repository slug.
        work: The ids the repository's detailing marks add, modify or remove, or None.
    """
    taken: set[str] = set()
    for t in tasks:
        if t.reuses and t.reuses not in taken:
            key = t.reuses
        else:
            cited = _work_cited(t.requirement_ids, work)
            base = (
                f"task:{slug}:items:{'+'.join(elab_slug(i) for i in cited)}"
                if cited
                else _title_key(t, slug)
            )
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
        HierarchyError: The file holds no `tasks` list. What the readers normalize
            instead of refusing is in `hierarchy.take_warnings`.
    """
    saved = read_story(directory, rel, repo, slug)
    tasks = read_tasks(directory, rel, slug, repo, saved.decision_ids, packages_dir)
    check_detailed_work(directory, slug, tasks)
    tasks = derive_prerequisites(directory, slug, tasks)
    check_cds_contract(slug, tasks)
    _assign_keys(tasks, slug, work_items(directory, slug))
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
    """Write one Story once; the orchestrator owns retries with a fresh graph."""
    return _write_story(
        graph, writer, epic_id, directory, slug=slug, repo=repo, root=root
    )


def _write_story(
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
        Each Task's local key, `elab_key`, title and the local keys it depends on, and
        `uncited`: the work items of the repository's detailing no Task cites.

    """
    take_warnings()
    tasks = plan_tasks(directory, _rel(directory, root), slug, repo, packages_dir)
    warnings = take_warnings()
    uncited = uncited_work(directory, slug, tasks)
    return {
        "ok": True,
        "slug": slug,
        "warnings": warnings,
        "uncited": uncited,
        "uncitedItems": item_briefs(directory, slug, uncited),
        "unsized": [t.key for t in tasks if not t.sizes],
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
        "summary": {"tasks": len(tasks), "warnings": len(warnings)},
    }


#: Who records a work item as `done` when the corrective pass states no work is needed.
NO_WORK_RULED_BY = "task-decomposition corrective pass"


def _write_json(path: Path, value: dict) -> None:
    """Write a JSON file whole, through a temporary file beside it.

    Args:
        path: The file.
        value: Its content.
    """
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", "utf-8")
    temp.replace(path)


def _rebind_input(directory: Path, name: str) -> list[str]:
    """Record a rewritten file's new content hash wherever it is a recorded input.

    The saved files of the Epic's working directory record the hash of each input they
    were built from (`<file>.meta.json`); a file amended in place would make them stale.

    Args:
        directory: The Epic's working directory.
        name: The rewritten file's name in that directory.

    Returns:
        The records updated.
    """
    path = directory / name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    updated: list[str] = []
    for meta_path in sorted(directory.rglob("*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict):
            continue
        changed = False
        if meta_path.name == f"{name}.meta.json":
            meta["sha256"], meta["bytes"] = digest, path.stat().st_size
            changed = True
        for entry in meta.get("inputs") or []:
            recorded = str(entry.get("path") or "") if isinstance(entry, dict) else ""
            if (
                entry.get("kind") == "file"
                and recorded.endswith(f"{directory.name}/{name}")
                and entry.get("sha256") != digest
            ):
                entry["sha256"] = digest
                changed = True
        if changed:
            _write_json(meta_path, meta)
            updated.append(meta_path.name)
    return updated


def _local_keys(start: list[dict]) -> Iterator[str]:
    """Yield fresh local Task keys `T<n>` past every key already in the file.

    Args:
        start: The Tasks already saved.

    Yields:
        The next unused key.
    """
    taken = {str(t.get("key") or "") for t in start}
    n = 1 + max(
        (int(k[1:]) for k in taken if re.fullmatch(r"T\d+", k)),
        default=0,
    )
    while True:
        if f"T{n}" not in taken:
            yield f"T{n}"
        n += 1


def add_corrective_tasks(directory: Path, *, slug: str, correction: Path) -> dict:
    """Merge one gap repair, preserving saved Tasks and all upstream artifacts."""
    path = directory / f"tasks-{slug}.json"
    saved = json.loads(path.read_text("utf-8"))
    fix = json.loads(correction.read_text("utf-8"))
    if "noWork" in fix:
        raise HierarchyError("noWork is not a Task correction")
    existing = saved["tasks"]
    work = set(work_items(directory, slug))
    cited = {i for t in existing for i in str_list(t.get("requirementIds"))}
    gap = work - cited
    original_scores = {str(s["key"]): s for s in saved.get("scores", [])}
    unsized = {
        str(t["key"])
        for t in existing
        if not _sizes(original_scores.get(str(t["key"])))
    }
    fresh = _local_keys(existing)
    keymap, taken = {}, set()
    added, rejected, dropped, trimmed = [], [], [], []
    for task in fix["tasks"]:
        ids = set(str_list(task.get("requirementIds")))
        if not ids or not ids <= gap:
            rejected.append(
                {"task": task.get("key"), "reason": "cites items outside the gap"}
            )
            continue
        remaining = ids - taken
        if not remaining:
            dropped.append(task.get("key"))
            continue
        if remaining != ids:
            trimmed.append(task.get("key"))
        key = next(fresh)
        keymap[str(task.get("key"))] = key
        added.append({**task, "key": key, "requirementIds": sorted(remaining)})
        taken.update(remaining)
    keys = {str(t["key"]) for t in existing} | set(keymap.values())
    for edge in fix["edges"]:
        frm = keymap.get(edge["from"], edge["from"])
        to = keymap.get(edge["to"])
        if to and frm in keys:
            saved.setdefault("edges", []).append({"from": frm, "to": to})
        else:
            rejected.append({"edge": edge, "reason": "edge is not into a new Task"})
    resized = []
    for score in fix["scores"]:
        original = str(score["key"])
        key = keymap.get(original, original)
        if not _sizes(score) or (original not in keymap and key not in unsized):
            rejected.append(
                {"score": original, "reason": "invalid or outside unsized keys"}
            )
            continue
        original_scores[key] = {**score, "key": key}
        if key in unsized:
            resized.append(key)
    saved["tasks"] = [*existing, *added]
    saved["scores"] = list(original_scores.values())
    _write_json(path, saved)
    return {
        "ok": True,
        "added": [t["key"] for t in added],
        "resized": resized,
        "rejected": rejected,
        "dropped": dropped,
        "trimmed": trimmed,
        "uncited": sorted(gap - taken),
    }


def _cited_ids(value: object) -> list[str]:
    """Return the ids a bead's `requirement_ids` metadata holds.

    Args:
        value: The metadata value: a JSON list, as written, or a list.

    Returns:
        The ids; empty when the value holds none.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if isinstance(v, str)]


def _match_tasks(
    tasks: list[Task],
    beads: list[Bead],
    slug: str,
    items: dict[str, dict[str, str]],
) -> tuple[dict[str, Bead], list[Bead]]:
    """Match each of a Story's Tasks to the Task bead it is, and return the beads left over.

    A Task is the bead that carries its `elab_key`. Every other Task is matched against the
    Story's Task beads that elaboration wrote (`elab_key` `task:<slug>:...`), that are not
    closed and that no Task holds by key, whatever key they were written under: first by
    the delta items both cite, the pair citing the most in common first (then build order,
    then bead id), then by title. A bead is matched to one Task at most, so a Task whose
    cited items changed keeps its bead instead of getting a second one.

    Args:
        tasks: The Story's Tasks, in build order, each with its `elab_key`.
        beads: The Story's Task beads, closed ones included, in id order.
        slug: The Story's repository slug.
        items: Every detailed delta item of the Epic, as `detailed_items` returns them.

    Returns:
        Task local key -> its bead, and the candidate beads no Task matched, in id order.
    """
    keyed = _keyed(beads)
    matched: dict[str, Bead] = {}
    used: set[str] = set()
    for t in tasks:
        b = keyed.get(t.elab_key or "")
        if b is not None and b.id not in used:
            matched[t.key] = b
            used.add(b.id)
    prefix = f"task:{slug}:"
    free = [
        b
        for b in beads
        if b.id not in used
        and not b.closed
        and str(b.metadata.get("elab_key") or "").startswith(prefix)
    ]
    rest = [t for t in tasks if t.key not in matched]
    pairs: list[tuple[int, int, str, Task, Bead]] = []
    for n, t in enumerate(rest):
        mine = {i for i in t.requirement_ids if i in items}
        for b in free:
            common = mine & set(_cited_ids(b.metadata.get("requirement_ids")))
            if common:
                pairs.append((-len(common), n, b.id, t, b))
    for _, _, _, t, b in sorted(pairs, key=lambda p: p[:3]):
        if t.key not in matched and b.id not in used:
            matched[t.key] = b
            used.add(b.id)
    for t in rest:
        if t.key in matched:
            continue
        titled = _title_key(t, slug)
        for b in free:
            if b.id not in used and (
                _norm(b.title) == _norm(t.title) or b.metadata.get("elab_key") == titled
            ):
                matched[t.key] = b
                used.add(b.id)
                break
    return matched, [b for b in free if b.id not in used]


#: The suffix of the input record the artifact script writes beside a saved file.
META_SUFFIX = ".meta.json"

#: The statuses of a Task no one has started building.
UNSTARTED = frozenset({"open", "blocked", "deferred"})


def _record_root(path: Path, meta: object, root: Path | None) -> Path | None:
    """The root an artifact record's paths are relative to.

    The record names the saved file itself (`path`) relative to that root, so the root is
    what the file's absolute path holds before it. The caller's root is used when the
    record's own path resolves under it.

    Args:
        path: The saved file.
        meta: Its parsed record, or None.
        root: The caller's project root, or None.

    Returns:
        The root, or None when neither the caller nor the record gives one.
    """
    named = str(meta.get("path") or "") if isinstance(meta, dict) else ""
    if not named or Path(named).is_absolute():
        return root
    if root is not None and (root / named).resolve() == path.resolve():
        return root
    full = path.resolve()
    parts = Path(named).parts
    if len(full.parts) > len(parts) and full.parts[-len(parts) :] == parts:
        return Path(*full.parts[: -len(parts)])
    return root


def tasks_inputs(directory: Path, *, slug: str, root: Path | None) -> dict:
    """Whether a Story's saved Tasks were decomposed from the inputs they record, unchanged.

    The artifact script records, beside `tasks-<slug>.json`, the content hash of every input
    it was decomposed from (`tasks-<slug>.json.meta.json`): the Spec documents and the Story,
    which carry every change upstream of them (PRD, architecture, TRD, detailing). Each file
    input is hashed again and compared. Runs no `bd` command.

    Args:
        directory: The Epic's working directory.
        slug: The Story's repository slug.
        root: The project root the recorded input paths are relative to, or None; when
            it is None or does not hold the saved file, `_record_root` derives it.

    Returns:
        `saved` (the file exists), `recorded` (its input record was read), `changedInputs`
        (each recorded input that changed or is gone, with why), `unverified` (each recorded
        input that could not be checked), and `unchanged`: True only when the file is saved,
        its record names at least one input, and every input checks out unchanged.
    """
    path = directory / f"tasks-{slug}.json"
    meta_path = path.with_name(path.name + META_SUFFIX)
    changed: list[dict] = []
    unverified: list[str] = []
    meta: object = None
    if path.is_file() and meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text("utf-8"))
        except (OSError, ValueError):
            meta = None
    inputs = meta.get("inputs") if isinstance(meta, dict) else None
    root = _record_root(path, meta, root)
    for entry in inputs if isinstance(inputs, list) else []:
        name = str(entry.get("path") or "") if isinstance(entry, dict) else ""
        recorded = str(entry.get("sha256") or "") if isinstance(entry, dict) else ""
        given = Path(name)
        source = given if given.is_absolute() else (root / given if root else None)
        if not name or not recorded or entry.get("kind") != "file" or source is None:
            unverified.append(name or "(an entry naming no path)")
            continue
        if not source.is_file():
            changed.append({"path": name, "why": "no longer exists"})
        elif hashlib.sha256(source.read_bytes()).hexdigest() != recorded:
            changed.append(
                {"path": name, "why": "changed since the Tasks were decomposed"}
            )
    saved = path.is_file()
    checked = bool(inputs) and not unverified
    return {
        "ok": True,
        "saved": saved,
        "recorded": isinstance(meta, dict),
        "changedInputs": changed,
        "unverified": unverified,
        "unchanged": saved and checked and not changed,
        "summary": {
            "saved": saved,
            "unchanged": saved and checked and not changed,
            "changed": len(changed),
            "unverified": len(unverified),
        },
    }


def replace_tasks(writer: Writer, epic_id: str, *, slug: str, reason: str) -> dict:
    """Delete a Story's unstarted Task beads, before its Tasks are decomposed again.

    Runs only when something upstream of the Story's Tasks changed. A Task elaboration wrote
    (`elab_key` `task:...`) that no one has started (open/blocked, no build-lane facts)
    is deleted; a started or closed Task, or one elaboration did not write, is kept and
    returned, so the new decomposition is told about it instead of duplicating it.

    Args:
        writer: The tracker writer; a dry-run writer records the deletion instead.
        epic_id: The Epic whose `story:<slug>` Story the Tasks sit under.
        slug: The Story's repository slug.
        reason: Which input changed, recorded with the result.

    Returns:
        `story` (its id, or None when the Story has no bead yet), `deleted` and `kept`, each
        `{id, title, elabKey, status}` (`kept` also with `requirementIds`), and `reason`.

    """
    stories = _keyed(
        sorted(
            (bead_of(r) for r in children(writer.repo, epic_id, "story")),
            key=lambda b: b.id,
        ),
    )
    story = stories.get(f"story:{slug}")
    deleted: list[dict] = []
    kept: list[dict] = []
    if story is not None:
        records = children(writer.repo, story.id, "task")
        for b in sorted((bead_of(r) for r in records), key=lambda b: b.id):
            key = str(b.metadata.get("elab_key") or "")
            facts = {"id": b.id, "title": b.title, "elabKey": key, "status": b.status}
            started = task_started(b)
            if started or not key.startswith("task:"):
                ids = _cited_ids(b.metadata.get("requirement_ids"))
                kept.append(facts | {"requirementIds": ids})
            else:
                deleted.append(facts)
        if deleted:
            writer.bd(["delete", *(d["id"] for d in deleted), "--force"])
    return {
        "ok": True,
        "story": story.id if story is not None else None,
        "deleted": deleted,
        "kept": kept,
        "reason": reason,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {"deleted": len(deleted), "kept": len(kept)},
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
    missing_only: bool = False,
) -> dict:
    """Write one Task once; the keyed implementation reads the current Story's Tasks."""
    return _write_task(
        writer,
        epic_id,
        directory,
        slug=slug,
        repo=repo,
        key=key,
        root=root,
        external=external,
        packages_dir=packages_dir,
        missing_only=missing_only,
    )


def _write_task(
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
    missing_only: bool = False,
) -> dict:
    """Write ONE Task of a Story, and its `blocks` edges to the Story's other Tasks.

    The Task sits under the Epic's Story whose `elab_key` is `story:<slug>`, found in beads.
    The Task is the bead `_match_tasks` matches it to (by `elab_key`, else by the items both
    cite, else by title), updated when it is open, or a new bead when none matches. It
    never deletes or closes a bead: when the Story's inputs changed, `replace_tasks` removed
    the unstarted Tasks before the new set was decomposed. Its blockers
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
        The Task, what was done to it, its edge writes, the blockers it carries outside the
        Story, and `warnings`: a Task it depends on that is not written yet is left out of
        its edges (the next run's refresh adds the edge), and an external blocker that is a
        Task of its own Story is taken as a Story edge.

    Raises:
        HierarchyError: The repository is empty, the key names no Task, or the Epic has no
            Story for the slug.

    """
    if not repo.strip():
        msg = f"Task {key} of story:{slug} has no repository: a Task is never written without one"
        raise HierarchyError(msg)
    take_warnings()
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
        ),
    )
    story = stories.get(f"story:{slug}")
    if story is None:
        msg = f"{epic_id} has no Story story:{slug}: its Story is written before its Tasks"
        raise HierarchyError(msg)
    story_id = story.id
    records = children(writer.repo, story_id, "task")
    priority = {str(r["id"]): r.get("priority") for r in records}
    beads = sorted((bead_of(r) for r in records), key=lambda b: b.id)
    keyed = _keyed(beads)
    items = detailed_items(directory)
    matched, _ = _match_tasks(tasks, beads, slug, items)

    def found(t: Task) -> Bead | None:
        return matched.get(t.key)

    blockers: list[str] = []
    warnings: list[str] = take_warnings()
    for dep in task.depends_on:
        blocker = found(by_key[dep]) if dep in by_key else None
        if blocker is None:
            msg = f"{key} depends on {dep}, which is not written under {story_id}"
            raise HierarchyError(msg)
        blockers.append(blocker.id)
    story_ids = {b.id for b in keyed.values()}
    outer = list(dict.fromkeys([*task.blocked_by_external, *(external or [])]))
    inner = [b for b in outer if b in story_ids]
    if inner:
        warnings.append(
            f"{key}: {', '.join(inner)} are Tasks of {story_id}; taken as Story edges",
        )
        blockers = list(dict.fromkeys([*blockers, *inner]))
        outer = [b for b in outer if b not in story_ids]
    bead = found(task)
    text = task_text(task, root)
    meta = task_metadata(task)
    if task.sizes:
        meta[JUDGED_HASH_KEY] = _judged_hash(
            task.title,
            text,
            priority.get(bead.id) if bead else DEFAULT_PRIORITY,
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
    elif task_started(bead) or missing_only:
        # A started Task (not open, or open with a build_state) or a closed one is never
        # rewritten: neither its prose, its metadata nor its edges.
        task_id, action = (
            bead.id,
            "unchanged-started" if task_started(bead) else "unchanged",
        )
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
            dict.fromkeys([*(b for b in bead.blockers if b not in story_ids), *outer]),
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
        "warnings": warnings,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "key": task.key,
            "id": task_id,
            "action": action,
            **edges,
            "warnings": len(warnings),
        },
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


def _no_code(directory: Path) -> set[str]:
    """Return the delta items the saved span ruling records as having no code here.

    Args:
        directory: The Epic's working directory.

    Returns:
        Their ids; empty when `repo-scoping.json` is not saved.
    """
    path = directory / "repo-scoping.json"
    if not path.is_file():
        return set()
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    rows = saved.get("noCode") if isinstance(saved, dict) else None
    return {
        str(r.get("itemId")).strip()
        for r in rows or []
        if isinstance(r, dict) and r.get("itemId")
    }


def closure_task_edges(directory: Path, repos: list[str]) -> dict:
    """Derive cross-Story edges from placements and declared requires relations.

    Every placed requirement needs a builder. Only explicit no-code items and
    matrix-satisfied Closure elements may lack Tasks without a finding.
    """
    requires = delta_requires(directory)
    edges: list[dict] = []
    warnings: list[str] = []
    if requires is not None:
        detailed = detailed_items(directory)
        no_code = _no_code(directory)
        closure = directory / "architecture" / "closure.json"
        if closure.is_file():
            data = json.loads(closure.read_text("utf-8"))
            no_code.update(
                str(i.get("id") or i.get("element")) for i in data.get("satisfied", [])
            )
        slug_story: dict[str, str] = {}
        builds: dict[str, list[str]] = {}
        task_slug: dict[str, str] = {}
        for index, (repo, slug) in enumerate(repo_slugs(repos).items()):
            slug_story[slug] = f"S{index + 1}"
            if not (directory / f"tasks-{slug}.json").is_file():
                continue
            for t in plan_tasks(directory, None, slug, repo):
                name = f"S{index + 1}-{t.key}"
                task_slug[name] = slug
                builds[name] = t.requirement_ids
        seen: set[tuple[str, str]] = set()
        for name, items in builds.items():
            slug = task_slug[name]
            for x in items:
                own = detailed.get(x, {})
                if own.get("slug") != slug:
                    continue
                for y in requires.get(x, []):
                    d = detailed.get(y)
                    if d is None:
                        if y not in no_code:
                            warnings.append(
                                f"{name} builds {x}, which requires {y}; no repository's "
                                "placement holds it",
                            )
                        continue
                    if d["slug"] == slug:
                        continue
                    found = [
                        n
                        for n, built in builds.items()
                        if task_slug[n] == d["slug"] and y in built
                    ]
                    if not found:
                        warnings.append(
                            f"{name} builds {x}, which requires {y}; no "
                            f"Task of {slug_story.get(d['slug'], d['slug'])} builds it",
                        )
                        continue
                    for frm in found:
                        if (frm, name) in seen:
                            continue
                        seen.add((frm, name))
                        edges.append(
                            {
                                "from": frm,
                                "to": name,
                                "kind": "infrastructure",
                                "reason": f"{x} requires {y} (the delta's prerequisite closure)",
                            },
                        )
    return {
        "ok": True,
        "edges": edges,
        "warnings": warnings,
        "summary": {"ok": True, "edges": len(edges), "warnings": warnings},
    }


def plan_task_edges(directory: Path, repos: list[str]) -> dict:
    """Return the saved Task edges between Stories, checked; runs no `bd` command.

    The edges are those `closure_task_edges` derives from the delta's `requires`
    relations, then the mapper's saved `task-deps.json` edges.

    Args:
        directory: The Epic's working directory.
        repos: The span, in its ruled order.

    Returns:
        The accepted edges, the rejected ones, each blocked Task's blockers by name, and
        `warnings`: the closure's warnings, and each edge dropped because it would close a
        cycle over the Epic's Task graph (edges are taken in order, the closure's first).
    """
    closure = closure_task_edges(directory, repos)
    warnings = list(closure["warnings"])
    standing = {(e["from"], e["to"]) for e in closure["edges"]}
    mapped = (
        read_task_deps(directory)
        if (directory / "task-deps.json").is_file() or not standing
        else []
    )
    saved = [
        *closure["edges"],
        *(
            e
            for e in mapped
            if (str(e.get("from") or ""), str(e.get("to") or "")) not in standing
        ),
    ]
    slug_of, intra, _elab = _span_tasks(directory, repos)
    accepted, rejected, _pairs = _accept(saved, slug_of)
    pairs: set[tuple[str, str]] = set()
    kept = []
    for edge in accepted:
        pair = (edge["from"], edge["to"])
        if build_order(sorted(slug_of), [*intra, *sorted(pairs | {pair})]) is None:
            warnings.append(
                f"edge {pair[0]} -> {pair[1]} would close a cycle over the Task graph; dropped"
            )
            continue
        pairs.add(pair)
        kept.append(edge)
    accepted = kept
    blockers: dict[str, list[str]] = {}
    for frm, to in sorted(pairs):
        blockers.setdefault(to, []).append(frm)
    return {
        "ok": True,
        "edges": accepted,
        "rejected": rejected,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "edges": len(accepted),
            "rejected": len(rejected),
            "blockers": blockers,
            "warnings": len(warnings),
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
        The Task, its saved edges, the edges added, removed and standing, and `warnings`:
        an edge whose other end is not written is skipped, and a Task that is not written
        has no edges written.
    """
    plan = plan_task_edges(directory, repos)
    slug_of, _intra, elab = _span_tasks(directory, repos)
    warnings: list[str] = []

    def bead_named(n: str) -> Bead | None:
        story = _story_of(graph, epic_id, slug_of.get(n, ""))
        bead = (
            _keyed(_children(graph, story.id, "task")).get(elab.get(n, ""))
            if story
            else None
        )
        if bead is None:
            warnings.append(f"Task {n} ({elab.get(n)}) is not written under {epic_id}")
        return bead

    task = bead_named(name)
    if task is None:
        return {
            "ok": True,
            "epic": epic_id,
            "task": {"name": name, "id": None},
            "edges": [],
            "warnings": warnings,
            "dryRun": writer.dry_run,
            "planned": writer.planned,
            "summary": {
                "name": name,
                "id": None,
                "added": 0,
                "removed": 0,
                "standing": 0,
            },
        }
    wanted = [
        b.id for n in plan["blockers"].get(name, []) if (b := bead_named(n)) is not None
    ]
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
        "warnings": warnings,
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
        name, the totals, the Tasks written and the number of warnings.
    """
    plan = plan_task_edges(directory, repos)
    names = list(
        dict.fromkeys(
            [*plan["blockers"], *also, *_carrying(graph, epic_id, directory, repos)]
        )
    )
    written = [
        write_task_edges(graph, writer, epic_id, directory, repos, name)
        for name in names
    ]
    tasks = [w["summary"] for w in written]
    warnings = list(
        dict.fromkeys([*plan["warnings"], *(m for w in written for m in w["warnings"])])
    )
    totals = {k: sum(t[k] for t in tasks) for k in ("added", "removed", "standing")}
    return {
        "ok": True,
        "epic": epic_id,
        "tasks": tasks,
        "warnings": warnings,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "edges": plan["summary"]["edges"],
            "rejected": plan["summary"]["rejected"],
            "blockers": plan["blockers"],
            "written": names,
            "warnings": len(warnings),
            **totals,
        },
    }


def task_started(bead: Bead) -> bool:
    """Deferred is an owner ruling; any build-lane fact protects existing work."""
    return bead.status not in {"open", "blocked"} or any(
        str(key).startswith(("build_", "cds_audit_")) and bool(value)
        for key, value in bead.metadata.items()
    )
