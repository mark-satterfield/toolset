"""An Epic's Story -> Task hierarchy, rebuilt from the documents its elaboration saved.

prd-to-spec saves every step it completes into the Epic's working directory and lists the
step in that directory's `STEPS.md`. Emission needs no agent: the Stories are the saved
`story-<slug>.json` of each `spec:<slug>` step, the Tasks are the saved `tasks-<slug>.json`
of each `tasks:<slug>` step, and the edges between Stories are the saved `task-deps.json`.
This module reads those files and returns the hierarchy prd-to-spec writes into beads, so
the workflow and the host that finishes an Epic without a session build it the same way.

Keys follow prd-to-spec: the Story of the repository at index i of the span is `S<i+1>`,
and a Task keeps its decomposition key under its Story's key (`S1-T3`).
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: The steps-completed file of an Epic's working directory.
STEPS_FILE = "STEPS.md"
_STEP_LINE = re.compile(r"^\s*\d+\.\s+(\S+)\s*$")

#: The surfaces a Task may declare; anything else is dropped.
SURFACES = (
    "api-contract",
    "event-chain",
    "auth",
    "performance",
    "web-ui",
    "ios",
    "android",
    "cross-platform-mobile",
    "ml",
    "data-pipeline",
)

#: The judged-size keys a Task carries, from its decomposition's `scores`.
SIZE_KEYS = (
    "wsjf_size_estimate",
    "wsjf_size_low",
    "wsjf_size_high",
    "wsjf_size_confidence",
)

#: The steps every elaboration completes before its Stories exist.
LEADING_STEPS = ("architecture", "repo-scoping", "trd")

#: The step that derives the Task edges between Stories.
TASK_DEPS_STEP = "task-deps"

#: Reasons a caller may pass for holding the Epic short of `done`. Tokens, so they cross a
#: command line intact.
HOLD_REASONS = {
    "spec-failures": "a repository in the span produced no Spec",
    "decomposition-failures": "a Story produced no Tasks",
    "removal-not-emitted": "removal work the PRD requires reached no Task",
    "cross-story-degraded": "the Task edges between Stories were not derived",
    "knock-on-unsaved": "knock-on Tasks this run added could not be saved for emission",
}


class HierarchyError(ValueError):
    """The saved documents do not describe a hierarchy that can be written."""


def read_steps(directory: Path) -> list[str]:
    """The steps an Epic's steps-completed file lists, in its order.

    Args:
        directory: The Epic's working directory.

    Returns:
        The step names; empty when there is no file.
    """
    try:
        text = (directory / STEPS_FILE).read_text(encoding="utf-8")
    except OSError:
        return []
    steps: list[str] = []
    for line in text.splitlines():
        found = _STEP_LINE.match(line)
        if found and found.group(1) not in steps:
            steps.append(found.group(1))
    return steps


def repo_slugs(repos: list[str]) -> dict[str, str]:
    """Each repository's artifact slug: its directory name, suffixed on a collision.

    Args:
        repos: The span, in its ruled order.

    Returns:
        Repository path -> slug.
    """
    slugs: dict[str, str] = {}
    for repo in repos:
        if repo in slugs:
            continue
        base = (
            re.sub(r"[^A-Za-z0-9._-]+", "_", repo.rstrip("/").split("/")[-1]) or "repo"
        )
        slug, n = base, 2
        while slug in slugs.values():
            slug = f"{base}-{n}"
            n += 1
        slugs[repo] = slug
    return slugs


def elab_slug(text: object) -> str:
    """The title slug a Task's durable key is built from.

    Args:
        text: The title.

    Returns:
        Lowercase words joined by dashes, at most 60 characters.
    """
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:60]


def str_list(value: object) -> list[str]:
    """A list of non-empty, trimmed strings; anything that is not a list is empty.

    Args:
        value: The value.

    Returns:
        The strings.
    """
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if x is not None and str(x).strip()]


def _loose_list(value: object) -> list[str]:
    """A list saved either as a list or as the text of one.

    Args:
        value: A list, or a string holding a JSON or Python list.

    Returns:
        The strings.
    """
    if isinstance(value, str) and value.strip().startswith("["):
        for parse in (json.loads, ast.literal_eval):
            try:
                return str_list(parse(value))
            except (ValueError, SyntaxError):
                continue
    return str_list(value)


def ac_text(item: object) -> str:
    """One acceptance criterion as text; a given/when/then object is joined.

    Args:
        item: The criterion.

    Returns:
        The text.
    """
    if isinstance(item, dict) and (
        item.get("given") or item.get("when") or item.get("then")
    ):
        return f"Given {item.get('given') or ''} When {item.get('when') or ''} Then {item.get('then') or ''}"
    return str(item if item is not None else "").strip()


def _read_json(path: Path) -> dict:
    """A saved JSON object.

    Args:
        path: The file.

    Returns:
        The object.

    Raises:
        HierarchyError: The file is missing or is not a JSON object.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"{path.name} could not be read: {exc}"
        raise HierarchyError(msg) from exc
    if not isinstance(data, dict):
        msg = f"{path.name} is not a JSON object"
        raise HierarchyError(msg)
    return data


def _meta_sha(path: Path) -> str | None:
    """The sha256 the recorder wrote beside an artifact, when there is one.

    Args:
        path: The artifact.

    Returns:
        The hash, or None.
    """
    try:
        meta = json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    sha = meta.get("sha256") if isinstance(meta, dict) else None
    return sha if isinstance(sha, str) and sha else None


@dataclass
class Story:
    """One Story: the container of one repository's Spec."""

    key: str
    repo_path: str
    slug: str
    title: str
    description: str
    acceptance: list[str]
    decision_ids: list[str]
    metadata: dict[str, str]


@dataclass
class Task:
    """One Task as prd-to-spec writes it."""

    key: str
    story_key: str
    repo_path: str
    title: str
    description: str
    acceptance: list[str]
    definition_of_done: list[str]
    spec_paths: list[str]
    spec_sections: list[str]
    requirement_ids: list[str]
    decision_ids: list[str]
    surfaces: list[str] | None
    test_strategy: dict | None
    depends_on: list[str]
    sizes: dict[str, str] | None
    verified: str
    reuses: str | None = None
    supersedes: str | None = None
    out_of_span: bool = False


@dataclass
class Hierarchy:
    """The Stories and Tasks one Epic's saved documents describe."""

    repos: list[str]
    steps: list[str]
    stories: list[Story] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    missing_steps: list[str] = field(default_factory=list)
    holds: list[str] = field(default_factory=list)
    cross_story: dict = field(default_factory=dict)
    sad_files: list[str] = field(default_factory=list)


def span_of(directory: Path) -> list[str]:
    """The repository span the saved repo-scoping ruling placed work in, in order.

    Args:
        directory: The Epic's working directory.

    Returns:
        The repository paths.
    """
    ruling = _read_json(directory / "repo-scoping.json")
    repos: list[str] = []
    for placement in ruling.get("placements") or []:
        path = str((placement or {}).get("repoPath") or "").strip()
        if path and path not in repos:
            repos.append(path)
    return repos


def expected_steps(repos: list[str]) -> list[str]:
    """Every step that needs an agent before an Epic's hierarchy is whole.

    Args:
        repos: The span.

    Returns:
        The step names.
    """
    slugs = repo_slugs(repos)
    steps = list(LEADING_STEPS)
    for repo in repos:
        steps += [f"spec:{slugs[repo]}", f"tasks:{slugs[repo]}"]
    if len(repos) > 1:
        steps.append(TASK_DEPS_STEP)
    return steps


def _sizes(score: dict | None) -> dict[str, str] | None:
    """A judged size as the metadata the Task carries, or None when it is unusable.

    Args:
        score: The decomposition's score entry for the Task.

    Returns:
        The four size keys, or None.
    """
    if not isinstance(score, dict):
        return None
    values = [
        score.get(k) for k in ("jobSize", "sizeLow", "sizeHigh", "sizeConfidence")
    ]
    if not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
        for v in values
    ):
        return None
    size, low, high, confidence = values
    if not (low <= size <= high) or confidence > 100:  # noqa: PLR2004 - a percent
        return None
    return dict(
        zip(
            SIZE_KEYS,
            (_num(size), _num(low), _num(high), _num(confidence)),
            strict=True,
        )
    )


def _num(value: float) -> str:
    """A number as the text JavaScript would print for it.

    Args:
        value: The number.

    Returns:
        The text.
    """
    return str(int(value)) if float(value).is_integer() else str(value)


def _order(keys: list[str], edges: list[tuple[str, str]]) -> list[str] | None:
    """A build order over the keys, ties in their given order; None on a cycle.

    Args:
        keys: The Task keys.
        edges: `(from, to)`: from is built before to.

    Returns:
        The keys in build order, or None.
    """
    rank = {k: i for i, k in enumerate(keys)}
    indegree = dict.fromkeys(keys, 0)
    out: dict[str, list[str]] = {k: [] for k in keys}
    for frm, to in edges:
        indegree[to] += 1
        out[frm].append(to)
    ready = [k for k in keys if indegree[k] == 0]
    order: list[str] = []
    while ready:
        ready.sort(key=rank.__getitem__)
        key = ready.pop(0)
        order.append(key)
        for nxt in out[key]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    return order if len(order) == len(keys) else None


def _story(directory: Path, rel: str | None, index: int, repo: str, slug: str) -> Story:
    """The Story a repository's saved spec step carries.

    Args:
        directory: The Epic's working directory.
        rel: The directory, relative to the project root, or None.
        index: The repository's place in the span.
        repo: The repository.
        slug: Its artifact slug.

    Returns:
        The Story.
    """
    saved = _read_json(directory / f"story-{slug}.json")
    metadata = {"elab_key": f"story:{slug}", "repoPath": repo}
    decisions = list(dict.fromkeys(_loose_list(saved.get("decisionIds"))))
    if decisions:
        metadata["decision_ids"] = json.dumps(
            decisions, separators=(",", ":"), ensure_ascii=False
        )
    if rel:
        entries = [
            ("spec", f"spec-{slug}.md"),
            ("spec_data_model", f"spec-{slug}.data-model.md"),
            ("spec_criteria", f"spec-{slug}.criteria.md"),
            ("story", f"story-{slug}.json"),
        ]
        for key, name in entries:
            if not (directory / name).is_file():
                continue
            metadata[f"artifact_{key}_path"] = f"{rel}/{name}"
            metadata[f"artifact_{key}_meta"] = f"{rel}/{name}.meta.json"
            sha = _meta_sha(directory / name)
            if sha:
                metadata[f"artifact_{key}_sha256"] = sha
    return Story(
        key=f"S{index + 1}",
        repo_path=repo,
        slug=slug,
        title=str(saved.get("title") or "").strip() or f"S{index + 1}",
        description=str(saved.get("description") or "").strip(),
        acceptance=[
            ac_text(x) for x in saved.get("acceptanceCriteria") or [] if ac_text(x)
        ]
        if isinstance(saved.get("acceptanceCriteria"), list)
        else [],
        decision_ids=decisions,
        metadata=metadata,
    )


def _tasks(directory: Path, rel: str | None, story: Story) -> list[Task]:
    """The Tasks a Story's saved decomposition carries, in build order.

    Args:
        directory: The Epic's working directory.
        rel: The directory, relative to the project root, or None.
        story: The Story.

    Returns:
        The Tasks.

    Raises:
        HierarchyError: The decomposition names no Task, or its edges form a cycle.
    """
    saved = _read_json(directory / f"tasks-{story.slug}.json")
    raw = [
        t
        for t in saved.get("tasks") or []
        if isinstance(t, dict) and str(t.get("key") or "").strip()
    ]
    if not raw:
        msg = f"tasks-{story.slug}.json names no Task"
        raise HierarchyError(msg)
    keys = [str(t["key"]).strip() for t in raw]
    known = set(keys)
    edges: list[tuple[str, str]] = []
    for e in saved.get("edges") or []:
        frm, to = str((e or {}).get("from") or ""), str((e or {}).get("to") or "")
        if frm in known and to in known and frm != to and (frm, to) not in edges:
            edges.append((frm, to))
    order = _order(keys, edges)
    if order is None:
        msg = f"tasks-{story.slug}.json: the Task edges form a cycle"
        raise HierarchyError(msg)
    reported = isinstance(saved.get("specDocsUnreadable"), list)
    unreadable = set(str_list(saved.get("specDocsUnreadable")))
    refs = []
    for name in (
        f"spec-{story.slug}.md",
        f"spec-{story.slug}.data-model.md",
        f"spec-{story.slug}.criteria.md",
    ):
        ref = f"{rel}/{name}" if rel else None
        if ref and str(directory / name) not in unreadable and ref not in unreadable:
            refs.append(ref)
    scores = {
        str(s.get("key")): s for s in saved.get("scores") or [] if isinstance(s, dict)
    }
    strategy = (
        saved.get("testStrategy")
        if isinstance(saved.get("testStrategy"), dict)
        else None
    )
    by_key = dict(zip(keys, raw, strict=True))
    tasks = []
    for key in order:
        t = by_key[key]
        cited = [p for p in str_list(t.get("specPaths")) if p in refs]
        surfaces = t.get("surfaces")
        tasks.append(
            Task(
                key=f"{story.key}-{key}",
                story_key=story.key,
                repo_path=story.repo_path,
                title=str(t.get("title") or "").strip() or f"{story.key}-{key}",
                description=str(t.get("description") or "").strip(),
                acceptance=[
                    ac_text(x) for x in t.get("acceptanceCriteria") or [] if ac_text(x)
                ],
                definition_of_done=str_list(t.get("definitionOfDone")),
                spec_paths=list(dict.fromkeys(cited)) or list(refs),
                spec_sections=str_list(t.get("specSections")),
                requirement_ids=str_list(t.get("requirementIds")),
                decision_ids=str_list(t.get("decisionIds")) or list(story.decision_ids),
                surfaces=list(
                    dict.fromkeys(
                        s.lower() for s in str_list(surfaces) if s.lower() in SURFACES
                    )
                )
                if isinstance(surfaces, list)
                else None,
                test_strategy=strategy,
                depends_on=[f"{story.key}-{frm}" for frm, to in edges if to == key],
                sizes=_sizes(scores.get(key)),
                verified="true" if reported else "unknown",
                reuses=str(t.get("reuses")).strip()
                if isinstance(t.get("reuses"), str) and t["reuses"].strip()
                else None,
            )
        )
    return tasks


def _extra_task(entry: dict) -> Task:
    """One Task the workflow added beside the decompositions (a knock-on or a removal).

    Args:
        entry: The Task as the workflow saved it.

    Returns:
        The Task.
    """
    sizes = entry.get("wsjfMetadata")
    sizes = (
        {k: str(sizes[k]) for k in SIZE_KEYS if sizes.get(k) not in (None, "")}
        if isinstance(sizes, dict)
        else None
    )
    surfaces = entry.get("surfaces")
    return Task(
        key=str(entry["key"]),
        story_key=str(entry.get("parentStoryId") or ""),
        repo_path=str(entry.get("repoPath") or ""),
        title=str(entry.get("title") or "").strip() or str(entry["key"]),
        description=str(entry.get("description") or "").strip(),
        acceptance=[
            ac_text(x) for x in entry.get("acceptanceCriteria") or [] if ac_text(x)
        ],
        definition_of_done=str_list(entry.get("definitionOfDone")),
        spec_paths=str_list(entry.get("specPaths")),
        spec_sections=str_list(entry.get("specSections")),
        requirement_ids=str_list(entry.get("requirementIds")),
        decision_ids=str_list(entry.get("decisionIds")),
        surfaces=str_list(surfaces) if isinstance(surfaces, list) else None,
        test_strategy=entry.get("testStrategy")
        if isinstance(entry.get("testStrategy"), dict)
        else None,
        depends_on=str_list(entry.get("dependsOn")),
        sizes=sizes if sizes and len(sizes) == len(SIZE_KEYS) else None,
        verified=str(entry.get("specPathsVerified") or "unknown"),
        supersedes=str(entry["supersedes"])
        if isinstance(entry.get("supersedes"), str)
        else None,
        out_of_span=entry.get("outOfSpanKnockOn") is True,
    )


def _cross_story(directory: Path, hier: Hierarchy) -> None:
    """Apply the saved Task edges between Stories, or record why none were applied.

    Args:
        directory: The Epic's working directory.
        hier: The hierarchy; its Tasks gain the edges.
    """
    story_of = {t.key: t.story_key for t in hier.tasks}
    report: dict = {
        "ran": False,
        "reason": None,
        "degraded": None,
        "edges": [],
        "rejected": [],
    }
    hier.cross_story = report
    if len({t.story_key for t in hier.tasks}) < 2:  # noqa: PLR2004 - two Stories
        report["reason"] = (
            "the Tasks sit in one Story, so no dependency crosses Stories"
        )
        return
    report["ran"] = True
    if TASK_DEPS_STEP not in hier.steps:
        report["degraded"] = (
            "the task-deps step is not complete, so no Task edge between Stories was derived"
        )
        return
    saved = _read_json(directory / "task-deps.json")
    if saved.get("acyclic") is False:
        report["degraded"] = (
            "the mapper reported that the edges between Stories imply a cycle"
        )
        return
    seen: set[tuple[str, str]] = set()
    for e in saved.get("edges") or []:
        frm, to = str((e or {}).get("from") or ""), str((e or {}).get("to") or "")
        why = (
            "an end is not a Task of this run"
            if frm not in story_of or to not in story_of
            else "both ends are in the same Story"
            if story_of[frm] == story_of[to]
            else "a duplicate"
            if (frm, to) in seen
            else None
        )
        if why:
            report["rejected"].append({"from": frm, "to": to, "reason": why})
            continue
        seen.add((frm, to))
        report["edges"].append(
            {"from": frm, "to": to, "kind": e.get("kind"), "reason": e.get("reason")}
        )
    pairs = [(d, t.key) for t in hier.tasks for d in t.depends_on] + [
        (e["from"], e["to"]) for e in report["edges"]
    ]
    if (
        _order([t.key for t in hier.tasks], [p for p in pairs if p[0] in story_of])
        is None
    ):
        report["rejected"] += [
            {**e, "reason": "dropped: the edge set closes a cycle"}
            for e in report["edges"]
        ]
        report["edges"] = []
        report["degraded"] = (
            "the saved edges between Stories close a cycle over the Task graph, so none was applied"
        )
        return
    by_key = {t.key: t for t in hier.tasks}
    for e in report["edges"]:
        by_key[e["to"]].depends_on.append(e["from"])


def build(  # noqa: PLR0913 - the caller's facts, one each
    directory: Path,
    project_root: Path | None,
    *,
    repos: list[str] | None = None,
    steps: list[str] | None = None,
    extra: Path | None = None,
    holds: list[str] | None = None,
) -> Hierarchy:
    """Rebuild an Epic's hierarchy from its working directory.

    Args:
        directory: The Epic's working directory.
        project_root: The root spec references are recorded relative to, or None.
        repos: The span; absent, the saved repo-scoping ruling's.
        steps: The completed steps; absent, the steps-completed file's.
        extra: A saved `{"tasks": [...]}` of Tasks added beside the decompositions.
        holds: Reasons, from `HOLD_REASONS`, that hold the Epic short of done.

    Returns:
        The hierarchy, with every step it is missing and every reason it is held.

    Raises:
        HierarchyError: A hold reason is unknown, or a saved document is unusable.
    """
    directory = directory.resolve()
    unknown = [h for h in holds or [] if h not in HOLD_REASONS]
    if unknown:
        msg = f"unknown hold reason(s): {', '.join(unknown)}"
        raise HierarchyError(msg)
    done_steps = list(steps) if steps is not None else read_steps(directory)
    # No span is ruled until repo scoping passes, and then its saved ruling names it.
    span = (
        list(repos)
        if repos
        else span_of(directory)
        if "repo-scoping" in done_steps
        else []
    )
    hier = Hierarchy(repos=span, steps=done_steps)
    hier.missing_steps = [s for s in expected_steps(span) if s not in done_steps]
    if not span and "repo-scoping" not in hier.missing_steps:
        hier.missing_steps.append("repo-scoping")
    hier.holds = [HOLD_REASONS[h] for h in holds or []]
    rel = None
    if project_root is not None:
        try:
            rel = str(directory.relative_to(project_root.resolve()))
        except ValueError:
            rel = None
    slugs = repo_slugs(span)
    for index, repo in enumerate(span):
        slug = slugs[repo]
        if f"spec:{slug}" not in done_steps:
            hier.holds.append(f"{repo} has no completed Spec")
            continue
        story = _story(directory, rel, index, repo, slug)
        hier.stories.append(story)
        if f"tasks:{slug}" not in done_steps:
            hier.holds.append(
                f"Story {story.key} ({repo}) has no completed decomposition"
            )
            continue
        hier.tasks += _tasks(directory, rel, story)
    _cross_story(directory, hier)
    if hier.cross_story.get("degraded"):
        hier.holds.append(hier.cross_story["degraded"])
    if extra is not None:
        hier.tasks += [
            _extra_task(t)
            for t in _read_json(extra).get("tasks") or []
            if isinstance(t, dict) and t.get("key")
        ]
    if "architecture" in done_steps and (directory / "sad-update.json").is_file():
        hier.sad_files = str_list(
            _read_json(directory / "sad-update.json").get("changedFiles")
        )
    return hier
