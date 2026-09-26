"""Write an Epic's hierarchy into beads, then finish its elaboration.

The one implementation of prd-to-spec's mechanical tail. The workflow runs it through
`depscore.py elaboration-complete` when its Tasks are decomposed, and the host runs the same
command to finish an in-progress Epic whose agent steps are all complete, with no session.

Every write is keyed by the durable `elab_key`, so a repeat updates in place and never
writes a second Story or Task:

  Story  matched by `story:<slug>` (or, written before keys existed, by its repoPath). An open
         match whose prose changed is updated. A Story the span no longer covers is closed
         only when it holds nothing.
  Task   matched by the key its decomposition `reuses`, else its title key (suffixed or not),
         else — written before keys existed — its title under the same Story.
         open         updated in place when anything differs, edges included.
         in_progress  left as it is, and so is a closed one; if the decomposition now says
         or closed    something different, that difference becomes a follow-up Task citing it.
         An open Task the decomposition no longer contains is closed, naming this command.

Then every Task edge is written as `blocks`, backfilled stand-in Stories are retired, and the
Epic is finished: its Tasks and itself are scored, and it is set `done` when every part of it
landed and nothing holds it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from beadgraph import GraphError, _bd, _same_value
from elaboration import LifecycleError, finish
from hierarchy import SIZE_KEYS, Hierarchy, Task, elab_slug

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from beadgraph import Graph, Writer

#: Marks of a stand-in Story the build lane minted for a Task that had none.
STAND_IN_LABEL = "backfill-parent"
STAND_IN_TEXT = "backfilled by the sdlc automation"

#: The value a contract field carries when nothing was declared.
UNKNOWN = "unknown"


def _norm(text: object) -> str:
    """Text with its whitespace collapsed, as matching compares it.

    Args:
        text: The text.

    Returns:
        The collapsed text.
    """
    return " ".join(str(text or "").split())


def _json(value: object) -> str:
    """Compact JSON, as the workflow wrote it.

    Args:
        value: The value.

    Returns:
        The JSON text.
    """
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _same(stored: object, wanted: str) -> bool:
    """Whether a metadata value read back equals the value that would be written.

    Args:
        stored: The value on the bead.
        wanted: The value to write.

    Returns:
        True when writing it would change nothing.
    """
    if stored is None:
        return False
    return _same_value(stored, wanted) or str(stored).lower() == wanted.lower()


def contract_block(task: Task, root: Path | None) -> str:
    """The build contract appended to a Task's description.

    Args:
        task: The Task.
        root: The project root its spec paths are relative to.

    Returns:
        The Markdown block.
    """

    def listed(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items) if items else "- (none)"

    s = task.test_strategy
    if s:
        env = (
            ", ".join(
                str(x).strip() for x in s.get("envMatrix") or [] if str(x).strip()
            )
            or "n/a"
        )
        source = f" (from {s['source']})" if s.get("source") else ""
        strategy = f"pyramid={s.get('pyramid') or 'n/a'}; coverageThreshold={s.get('coverageThreshold') or 'n/a'}; envMatrix={env}{source}"
    else:
        strategy = "unknown (the spec states none)"
    if task.surfaces is None:
        surfaces = "unknown (none declared)"
    else:
        surfaces = ", ".join(task.surfaces) or "(declared none — internal-only)"
    lines = [
        "## Spec contract",
        f"Paths are relative to the project root{f' ({root})' if root else ''}.",
        f"Spec: {task.spec_paths[0] if task.spec_paths else 'MISSING — no spec reference could be recorded for this Task'}",
    ]
    if len(task.spec_paths) > 1:
        lines.append(f"Spec documents:\n{listed(task.spec_paths)}")
    lines += [
        f"Spec sections:\n{listed(task.spec_sections)}",
        f"Requirement ids: {', '.join(task.requirement_ids) or '(none)'}",
        f"Surfaces: {surfaces}",
        f"Test strategy: {strategy}",
        f"Definition of Done:\n{listed(task.definition_of_done)}",
    ]
    return "\n".join(lines)


def task_text(task: Task, root: Path | None) -> str:
    """A Task's full description: its prose, then its build contract.

    Args:
        task: The Task.
        root: The project root.

    Returns:
        The description.
    """
    return "\n\n".join(x for x in (task.description, contract_block(task, root)) if x)


def task_metadata(task: Task, elab_key: str) -> dict[str, str]:
    """Every metadata key a Task is written with.

    Args:
        task: The Task.
        elab_key: Its durable key.

    Returns:
        The metadata.
    """
    m = {"elab_key": elab_key}
    if task.repo_path:
        m["repoPath"] = task.repo_path
    if task.sizes:
        m.update({k: task.sizes[k] for k in SIZE_KEYS})
    if task.decision_ids:
        m["decision_ids"] = _json(list(dict.fromkeys(task.decision_ids)))
    if task.supersedes:
        m["elab_follows"] = task.supersedes
    m["spec_sections"] = _json(task.spec_sections)
    m["acceptance_criteria"] = _json(task.acceptance)
    m["definition_of_done"] = _json(task.definition_of_done)
    m["requirement_ids"] = _json(task.requirement_ids)
    m["surfaces"] = _json(task.surfaces) if task.surfaces is not None else UNKNOWN
    m["test_strategy"] = _json(task.test_strategy) if task.test_strategy else UNKNOWN
    if task.spec_paths:
        m["spec_path"] = task.spec_paths[0]
        m["spec_paths"] = _json(task.spec_paths)
        m["spec_paths_verified"] = task.verified
    return m


@dataclass
class Node:
    """One existing bead beneath the Epic."""

    id: str
    kind: str
    status: str
    title: str
    description: str
    parent: str | None
    elab_key: str | None
    repo_path: str | None
    labels: list[str]
    blocked_by: list[str]
    metadata: dict[str, str]


@dataclass
class Emission:
    """What was written, and what was not."""

    target: str
    attempted: int = 0
    created: int = 0
    adopted: int = 0
    written: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    spec_reference_missing: list[dict] = field(default_factory=list)
    knock_on_without_spec: list[dict] = field(default_factory=list)
    links: dict = field(
        default_factory=lambda: {"attempted": 0, "linked": 0, "failed": []}
    )
    heal: dict = field(
        default_factory=lambda: {
            "ran": False,
            "reason": None,
            "wrappers": 0,
            "reparented": 0,
            "closed": 0,
            "failed": [],
        }
    )
    reelaboration: dict = field(
        default_factory=lambda: {
            "ran": True,
            "reason": None,
            "storiesMatched": 0,
            "storiesClosed": 0,
            "tasksMatched": 0,
            "tasksUpdated": 0,
            "tasksUnchanged": 0,
            "tasksClosed": 0,
            "tasksKnockOn": 0,
            "tasksLeftAlone": 0,
            "edgesRemoved": 0,
            "edgesWithheld": 0,
            "failed": [],
        }
    )
    verdict: str = "none"
    reason: str | None = None

    def report(self) -> dict:
        """The emission as the workflow reports it.

        Returns:
            The report.
        """
        return {
            "target": self.target,
            "attempted": self.attempted,
            "created": self.created,
            "adopted": self.adopted,
            "written": self.written,
            "failed": self.failed,
            "skipped": self.skipped,
            "specReferenceMissing": self.spec_reference_missing,
            "knockOnWithoutSpec": self.knock_on_without_spec,
            "links": self.links,
            "heal": self.heal,
            "reelaboration": self.reelaboration,
            "verdict": self.verdict,
            "reason": self.reason,
        }


def survey(graph: Graph, epic_id: str) -> list[Node]:
    """The Epic's children and grandchildren, as they stand in the tracker.

    Args:
        graph: The tracker graph, read with descriptions.
        epic_id: The Epic.

    Returns:
        The nodes.
    """
    labels = {
        str(r.get("id")): [str(x).lower() for x in r.get("labels") or []]
        for r in graph.records
    }
    level1 = [b for b in graph.beads.values() if b.parent == epic_id]
    ids = {b.id for b in level1}
    level2 = [b for b in graph.beads.values() if b.parent in ids]
    return [
        Node(
            id=b.id,
            kind=b.kind.lower(),
            status=b.status.lower(),
            title=_norm(b.title),
            description=_norm(b.description),
            parent=b.parent,
            elab_key=b.metadata.get("elab_key") or None,
            repo_path=b.metadata.get("repoPath") or None,
            labels=labels.get(b.id, []),
            blocked_by=list(b.blockers),
            metadata=b.metadata,
        )
        for b in sorted(level1 + level2, key=lambda b: b.id)
    ]


class _Tracker:
    """The writes emission makes, each recorded or reported, never raised."""

    def __init__(self, writer: Writer) -> None:
        self.writer = writer

    def run(self, args: list[str]) -> str:
        if self.writer.dry_run:
            self.writer.planned.append({"op": "bd", "args": list(args)})
            return ""
        return _bd(args, self.writer.repo)

    def create(self, key: str, args: list[str]) -> str:
        if self.writer.dry_run:
            self.writer.planned.append({"op": "bd", "args": list(args)})
            return f"(new:{key})"
        return _bd(args, self.writer.repo).strip().splitlines()[-1].strip()


def _create_args(
    kind: str,
    title: str,
    text: str,
    parent: str,
    acceptance: list[str],
    notes: str | None,
    metadata: dict,
) -> list[str]:  # noqa: PLR0913
    """The `bd create` for one bead.

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


def emit(
    graph: Graph, writer: Writer, epic_id: str, hier: Hierarchy, root: Path | None
) -> tuple[Emission, dict, dict, list[str]]:  # noqa: C901, PLR0912, PLR0915 - one pass over the hierarchy, in the workflow's order
    """Write the hierarchy beneath the Epic, updating what an earlier run wrote.

    Args:
        graph: The tracker graph, read with descriptions.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        hier: The hierarchy.
        root: The project root spec paths are relative to.

    Returns:
        The emission, Story key -> id, Task key -> id, and the Tasks whose judged size
        now describes the content they carry.
    """
    out = Emission(target=str(writer.repo or ""))
    tracker = _Tracker(writer)
    reelab = out.reelaboration
    nodes = survey(graph, epic_id)
    by_parent: dict[str, list[Node]] = {}
    for n in nodes:
        if n.parent:
            by_parent.setdefault(n.parent, []).append(n)
    taken = {n.elab_key for n in nodes if n.elab_key}
    existing_stories: dict[str, Node] = {}
    for n in nodes:
        if n.kind == "story" and n.parent == epic_id:
            key = n.elab_key or (
                f"story:{n.repo_path.rstrip('/').split('/')[-1]}"
                if n.repo_path
                else None
            )
            if key and key not in existing_stories:
                existing_stories[key] = n
    story_ids: dict[str, str] = {}
    task_ids: dict[str, str] = {}
    mutations: list[dict] = []
    matched_story: dict[str, Node] = {}

    # Stories: matched by the repository they cover.
    covered = set()
    for s in hier.stories:
        match = existing_stories.get(s.metadata["elab_key"])
        if not match:
            continue
        covered.add(match.id)
        matched_story[s.key] = match
        story_ids[s.key] = match.id
        reelab["storiesMatched"] += 1
        out.adopted += 1
        if match.status == "open" and (
            _norm(s.title) != match.title or _norm(s.description) != match.description
        ):
            mutations.append(
                {
                    "key": f"update:{match.id}",
                    "op": "update",
                    "id": match.id,
                    "title": s.title,
                    "description": s.description,
                }
            )
    for node in existing_stories.values():
        if node.id in covered or node.status == "closed":
            continue
        held = by_parent.get(node.id, [])
        if held:
            reelab["failed"].append(
                {
                    "what": node.id,
                    "reason": f"left open: the span no longer covers it, but it holds {len(held)} Task(s)",
                }
            )
            continue
        reelab["storiesClosed"] += 1
        mutations.append(
            {
                "key": f"close:{node.id}",
                "op": "close",
                "id": node.id,
                "reason": f"Closed by elaboration of {epic_id}: the repository this Story covered is no longer in the Epic's span, and it holds no Task.",
            }
        )

    # Tasks: matched by durable key, then by title for a Task written before keys existed.
    elab_keys: dict[str, str] = {}
    refreshed: list[tuple[Task, Node]] = []
    held_keys: set[str] = set()
    follow_ups: list[tuple[Task, Node, str]] = []
    matched_ids: set[str] = set()
    reused: set[str] = set()
    for t in hier.tasks:
        story = matched_story.get(t.story_key)
        if not story:
            continue
        siblings = [c for c in by_parent.get(story.id, []) if c.kind == "task"]
        existing_keys = {c.elab_key for c in siblings if c.elab_key}
        reuse = (
            t.reuses if t.reuses in existing_keys and t.reuses not in reused else None
        )
        if reuse:
            reused.add(reuse)
        title_key = f"task:{story_slug(t, hier)}:{elab_slug(t.title)}"

        def matches(
            k: str, reuse: str | None = reuse, title_key: str = title_key
        ) -> bool:
            if reuse:
                return k == reuse
            return k == title_key or (
                k.startswith(f"{title_key}-") and k[len(title_key) + 1 :].isdigit()
            )

        match = next(
            (
                c
                for c in siblings
                if c.elab_key and matches(c.elab_key) and c.id not in matched_ids
            ),
            None,
        ) or next(
            (
                c
                for c in siblings
                if not c.elab_key
                and c.title == _norm(t.title)
                and c.id not in matched_ids
            ),
            None,
        )
        if not match:
            continue
        if match.elab_key:
            elab_keys[t.key] = match.elab_key
        else:
            elab_keys[t.key] = _fresh_key(title_key, taken)
        matched_ids.add(match.id)
        reelab["tasksMatched"] += 1
        task_ids[t.key] = match.id
        out.adopted += 1
        text = task_text(t, root)
        if match.status == "open":
            refreshed.append((t, match))
            meta = task_metadata(t, elab_keys[t.key])
            changed = {
                k: v for k, v in meta.items() if not _same(match.metadata.get(k), v)
            }
            prose = _norm(t.title) != match.title or _norm(text) != match.description
            if prose or changed:
                reelab["tasksUpdated"] += 1
                mutations.append(
                    {
                        "key": f"update:{match.id}",
                        "op": "update",
                        "id": match.id,
                        "title": t.title,
                        "description": text,
                        "metadata": changed,
                    }
                    if prose
                    else {
                        "key": f"update:{match.id}",
                        "op": "update",
                        "id": match.id,
                        "metadata": changed,
                    }
                )
            else:
                reelab["tasksUnchanged"] += 1
            continue
        held_keys.add(t.key)
        if _norm(t.title) == match.title and _norm(text) == match.description:
            reelab["tasksLeftAlone"] += 1
            continue
        follow_ups.append((t, match, story.id))
        reelab["tasksKnockOn"] += 1

    # A follow-up an earlier run wrote for the same built Task is the one refreshed.
    new_follow_ups: list[Task] = []
    for t, existing, story_id in follow_ups:
        base = f"{existing.elab_key or f'task:{story_slug(t, hier)}:{elab_slug(t.title)}'}:follow-up"
        prior = next(
            (
                c
                for c in by_parent.get(story_id, [])
                if c.kind == "task"
                and c.status == "open"
                and c.id not in matched_ids
                and c.elab_key
                and (c.elab_key == base or c.elab_key.startswith(f"{base}-"))
            ),
            None,
        )
        follow = Task(
            **{
                **t.__dict__,
                "key": f"{t.key}-knockon",
                "title": f"{t.title} (follow-up to {existing.id})",
                "description": (
                    f"{t.description}\n\nFOLLOW-UP. {existing.id} already covered this work and is "
                    f"{'built' if existing.status == 'closed' else 'in progress'}, so it was not rewritten. "
                    "This Task carries what the current specification says differently, against the same Story and the same contract."
                ),
                "supersedes": existing.id,
                "reuses": None,
                "depends_on": [],
            }
        )
        if prior:
            matched_ids.add(prior.id)
            elab_keys[follow.key] = prior.elab_key or base
            task_ids[follow.key] = prior.id
            out.adopted += 1
            refreshed.append((follow, prior))
            mutations.append(
                {
                    "key": f"update:{prior.id}",
                    "op": "update",
                    "id": prior.id,
                    "title": follow.title,
                    "description": task_text(follow, root),
                    "metadata": task_metadata(follow, elab_keys[follow.key]),
                }
            )
        else:
            elab_keys[follow.key] = _fresh_key(base, taken)
        new_follow_ups.append(follow)
    tasks = [*hier.tasks, *new_follow_ups]

    # An open Task the decomposition no longer contains is closed.
    for story in matched_story.values():
        for c in by_parent.get(story.id, []):
            if c.kind != "task" or c.status != "open" or c.id in matched_ids:
                continue
            reelab["tasksClosed"] += 1
            mutations.append(
                {
                    "key": f"close:{c.id}",
                    "op": "close",
                    "id": c.id,
                    "reason": f"Closed by elaboration of {epic_id}: the current decomposition of this Story no longer contains this Task, and no work had started on it.",
                }
            )

    # New Stories, under the Epic.
    for s in hier.stories:
        if s.key in story_ids:
            continue
        out.attempted += 1
        args = _create_args(
            "story",
            s.title,
            s.description,
            epic_id,
            s.acceptance,
            f"repoPath: {s.repo_path}",
            s.metadata,
        )
        try:
            story_ids[s.key] = tracker.create(s.key, args)
            out.created += 1
            out.written.append({"level": "story", "key": s.key, "id": story_ids[s.key]})
        except GraphError as exc:
            out.failed.append({"level": "story", "key": s.key, "reason": str(exc)})

    # New Tasks, each under its own Story; a Task whose Story is not durable is skipped.
    created_keys: set[str] = set()
    for t in tasks:
        _account_contract(out, t)
        if t.key in task_ids:
            continue
        parent = story_ids.get(t.story_key)
        if not parent:
            out.skipped.append(
                {
                    "level": "task",
                    "key": t.key,
                    "reason": f"its parent Story {t.story_key} was not written",
                }
            )
            continue
        key = elab_keys.get(t.key) or _fresh_key(
            f"task:{story_slug(t, hier)}:{elab_slug(t.title)}", taken
        )
        elab_keys[t.key] = key
        out.attempted += 1
        args = _create_args(
            "task",
            t.title,
            task_text(t, root),
            parent,
            t.acceptance,
            f"repoPath: {t.repo_path}" if t.repo_path else None,
            task_metadata(t, key),
        )
        try:
            task_ids[t.key] = tracker.create(t.key, args)
            out.created += 1
            created_keys.add(t.key)
            out.written.append({"level": "task", "key": t.key, "id": task_ids[t.key]})
        except GraphError as exc:
            out.failed.append({"level": "task", "key": t.key, "reason": str(exc)})

    # The edges of a refreshed Task are refreshed with it.
    epic_task_ids = set(task_ids.values()) | {c.id for c in nodes if c.kind == "task"}
    standing = {(c.id, b) for c in nodes if c.kind == "task" for b in c.blocked_by}
    for t, match in refreshed:
        wanted = {task_ids[d] for d in t.depends_on if d in task_ids}
        for b in match.blocked_by:
            if b in epic_task_ids and b not in wanted:
                mutations.append(
                    {
                        "key": f"unlink:{match.id}->{b}",
                        "op": "unlink",
                        "id": match.id,
                        "dependsOnId": b,
                    }
                )
                reelab["edgesRemoved"] += 1
    _apply(tracker, writer, mutations, reelab)

    # Every Task edge, as a `blocks` edge.
    for t in tasks:
        for dep in t.depends_on:
            frm, to = task_ids.get(t.key), task_ids.get(dep)
            is_standing = bool(frm and to and (frm, to) in standing)
            if t.key in held_keys and not is_standing:
                reelab["edgesWithheld"] += 1
                continue
            out.links["attempted"] += 1
            if not frm or not to:
                out.links["failed"].append(
                    {
                        "from": t.key,
                        "to": dep,
                        "reason": "one end of the edge was not written",
                    }
                )
            elif is_standing:
                out.links["linked"] += 1
            else:
                try:
                    tracker.run(["dep", "add", frm, to, "--type", "blocks"])
                    out.links["linked"] += 1
                except GraphError as exc:
                    out.links["failed"].append(
                        {"from": t.key, "to": dep, "reason": str(exc)}
                    )

    _heal(tracker, out, nodes, epic_id, hier, story_ids)

    beneath = len(story_ids) + len(task_ids)
    unwritten = len(out.failed) + len(out.skipped)
    if not beneath:
        out.verdict = "none"
    elif (
        unwritten
        or out.links["failed"]
        or out.spec_reference_missing
        or hier.cross_story.get("degraded")
    ):
        out.verdict = "partial"
    else:
        out.verdict = "complete"
    durable = out.created + out.adopted
    out.reason = (
        f"all {durable} bead(s) of this hierarchy are durable"
        if out.verdict == "complete"
        else f"{durable} bead(s) durable, {unwritten} NOT written, {len(out.links['failed'])} dependency edge(s) unlinked, "
        f"{len(out.spec_reference_missing)} Task(s) written with no spec reference"
        + (
            f"; {hier.cross_story['degraded']}"
            if hier.cross_story.get("degraded")
            else ""
        )
    )
    # The Tasks whose size was judged from the content they now carry: every one written
    # now, and every open one matched, whose content is this decomposition's.
    current = created_keys | {t.key for t, _ in refreshed}
    judged = [
        task_ids[t.key]
        for t in tasks
        if t.key in task_ids and t.sizes and t.key in current
    ]
    return (
        out,
        story_ids,
        task_ids,
        [j for j in dict.fromkeys(judged) if not j.startswith("(new:")],
    )


def story_slug(task: Task, hier: Hierarchy) -> str:
    """The slug of the repository a Task's Story covers.

    Args:
        task: The Task.
        hier: The hierarchy.

    Returns:
        The slug, or `repo`.
    """
    story = next((s for s in hier.stories if s.key == task.story_key), None)
    return story.slug if story else "repo"


def _fresh_key(base: str, taken: set[str]) -> str:
    """A durable key no bead carries yet, reserved.

    Args:
        base: The key it is built from.
        taken: Every key in use; the new one is added.

    Returns:
        The key.
    """
    key, n = base, 2
    while key in taken:
        key = f"{base}-{n}"
        n += 1
    taken.add(key)
    return key


def _account_contract(out: Emission, task: Task) -> None:
    """Record a Task that carries no spec reference.

    Args:
        out: The emission.
        task: The Task.
    """
    if task.spec_paths:
        return
    if task.out_of_span:
        out.knock_on_without_spec.append(
            {
                "key": task.key,
                "follows": task.supersedes,
                "repoPath": task.repo_path or None,
            }
        )
        return
    out.spec_reference_missing.append(
        {
            "key": task.key,
            "reason": "spec-reference-missing: no project-root-relative spec document is known for its Story",
        }
    )


def _apply(
    tracker: _Tracker, writer: Writer, mutations: list[dict], reelab: dict
) -> set[str]:
    """Apply the re-elaboration mutations, recording each one that did not land.

    Args:
        tracker: The tracker.
        writer: The writer, for verified metadata.
        mutations: The mutations, in order.
        reelab: The re-elaboration report.

    Returns:
        The Tasks whose metadata was refreshed.
    """
    refreshed: set[str] = set()
    for m in mutations:
        try:
            if m["op"] == "close":
                tracker.run(["close", m["id"], "--reason", m["reason"]])
            elif m["op"] == "unlink":
                tracker.run(["dep", "remove", m["id"], m["dependsOnId"]])
            elif m["op"] == "reparent":
                tracker.run(["update", m["id"], "--parent", m["newParentId"]])
            else:
                if "title" in m:
                    tracker.run(
                        [
                            "update",
                            m["id"],
                            "--title",
                            m["title"],
                            "--description",
                            m["description"],
                        ]
                    )
                if m.get("metadata"):
                    writer.metadata(m["id"], m["metadata"])
                    refreshed.add(m["id"])
        except GraphError as exc:
            reelab["failed"].append(
                {"what": m["id"], "reason": f"the {m['op']} did not land: {exc}"}
            )
    return refreshed


def _heal(
    tracker: _Tracker,
    out: Emission,
    nodes: list[Node],
    epic_id: str,
    hier: Hierarchy,
    story_ids: dict[str, str],
) -> None:  # noqa: PLR0913
    """Retire the backfilled stand-in Stories, moving their Tasks under a real Story.

    Args:
        tracker: The tracker.
        out: The emission; its heal report is filled.
        nodes: The surveyed nodes.
        epic_id: The Epic.
        hier: The hierarchy.
        story_ids: Story key -> id, for the Stories that are durable.
    """
    heal = out.heal
    real = [(s, story_ids[s.key]) for s in hier.stories if s.key in story_ids]
    if not real:
        heal["reason"] = (
            "no Story of this Epic is durable, so there is nowhere to re-parent a stand-in's Tasks"
        )
        return
    heal["ran"] = True
    ours = set(story_ids.values())
    wrappers = [
        n
        for n in nodes
        if n.parent == epic_id
        and n.kind == "story"
        and n.status != "closed"
        and n.id not in ours
        and (
            STAND_IN_LABEL in n.labels
            or STAND_IN_TEXT in f"{n.title} {n.description}".lower()
        )
    ]
    heal["wrappers"] = len(wrappers)
    if not wrappers:
        heal["reason"] = "the Epic carried no backfilled roll-up Story"
        return
    for w in wrappers:
        children = [n for n in nodes if n.parent == w.id]
        foreign = [c for c in children if c.kind not in ("task", "bug")]
        if foreign:
            heal["failed"].append(
                {
                    "wrapper": w.id,
                    "reason": f"left open: it holds {len(foreign)} child(ren) that are not Tasks or Bugs",
                }
            )
            continue
        moved = []
        for c in children:
            text = f"{c.title} {c.description}".lower()
            dest = (
                real[0][1]
                if len(real) == 1
                else next(
                    (
                        sid
                        for s, sid in real
                        if s.repo_path.lower() in text
                        or len(s.slug) > 2
                        and s.slug.lower() in text
                    ),  # noqa: PLR2004
                    real[0][1],
                )
            )
            try:
                tracker.run(["update", c.id, "--parent", dest])
                heal["reparented"] += 1
                moved.append(f"{c.id} -> {dest}")
            except GraphError as exc:
                heal["failed"].append(
                    {
                        "wrapper": w.id,
                        "reason": f"reparent of {c.id} did not land: {exc}",
                    }
                )
        try:
            tracker.run(
                [
                    "close",
                    w.id,
                    "--reason",
                    "Retired by elaboration: this was a backfilled roll-up parent standing in for a Story that did not exist yet. "
                    + (
                        f"Re-parented: {'; '.join(moved)}."
                        if moved
                        else "It was holding nothing."
                    ),
                ]
            )
            heal["closed"] += 1
        except GraphError as exc:
            heal["failed"].append(
                {"wrapper": w.id, "reason": f"the close did not land: {exc}"}
            )


def complete(  # noqa: PLR0913 - the caller's facts, one each
    graph: Graph,
    writer: Writer,
    epic_id: str,
    hier: Hierarchy,
    root: Path | None,
    *,
    owner: str | None,
    sad_root: str | None,
    reload: Callable[[], Graph],
) -> dict:
    """Emit the hierarchy and finish the Epic's elaboration.

    Args:
        graph: The tracker graph, read with descriptions.
        writer: The tracker writer.
        epic_id: The Epic.
        hier: The hierarchy.
        root: The project root spec paths are relative to.
        owner: The owner token of the run finishing it, or None.
        sad_root: The SAD directory the architecture step's files must sit under.
        reload: Reads the tracker again, after the writes.

    Returns:
        The emission, the ids, whether the Epic is done, and the finish result.

    Raises:
        LifecycleError: The Epic is not an open Epic.
    """
    epic = graph.beads.get(epic_id)
    if epic is None or epic.kind != "epic" or epic.closed:
        msg = f"{epic_id} is not an open Epic in this tracker"
        raise LifecycleError(msg)
    out, story_ids, task_ids, judged = emit(graph, writer, epic_id, hier, root)
    done = bool(task_ids) and out.verdict == "complete" and not hier.holds
    finish_out = None
    if out.verdict != "none":
        after = graph if writer.dry_run else reload()
        try:
            finish_out = finish(
                after,
                writer,
                epic_id,
                judged=judged,
                owner=owner,
                done=done,
                sad_files=hier.sad_files if done else [],
                sad_root=sad_root,
            )
        except (LifecycleError, GraphError) as exc:
            finish_out = {"error": str(exc)}
    finished = bool(
        finish_out and not finish_out.get("error") and finish_out.get("lifecycle")
    )
    return {
        "ok": out.verdict != "none",
        "epic": epic_id,
        "emission": out.report(),
        "stories": story_ids,
        "tasks": task_ids,
        "judged": judged,
        "holds": hier.holds,
        "missingSteps": hier.missing_steps,
        "crossStory": hier.cross_story,
        "done": finished,
        "finish": finish_out,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "ok": out.verdict != "none",
            "epic": epic_id,
            "verdict": out.verdict,
            "stories": len(story_ids),
            "tasks": len(task_ids),
            "created": out.created,
            "updated": out.reelaboration["tasksUpdated"],
            "linked": out.links["linked"],
            "done": finished,
            "holds": len(hier.holds),
        },
    }
