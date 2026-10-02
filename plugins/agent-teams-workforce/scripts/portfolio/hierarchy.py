"""Readers for the Story and Task documents an Epic's elaboration saves.

prd-to-spec saves each step's output into the Epic's working directory: `story-<slug>.json`
for a repository's Story, `tasks-<slug>.json` for that Story's decomposition, and
`task-deps.json` for the Task edges between Stories. These readers turn those files into the
Stories and Tasks `beadwrite` writes into beads. A Task's `key` is its local decomposition
key (`T3`); `depends_on` holds local keys of the same Story.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

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


class HierarchyError(ValueError):
    """The saved documents do not describe a Story or Tasks that can be written."""


def repo_slugs(repos: list[str]) -> dict[str, str]:
    """Return each repository's artifact slug: its directory name, suffixed on a collision.

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
    """Return the title slug a Task's durable key is built from.

    Args:
        text: The title.

    Returns:
        Lowercase words joined by dashes, at most 60 characters.
    """
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:60]


def str_list(value: object) -> list[str]:
    """Return a list of non-empty, trimmed strings; anything but a list is empty.

    Args:
        value: The value.

    Returns:
        The strings.
    """
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if x is not None and str(x).strip()]


def _loose_list(value: object) -> list[str]:
    """Return a list saved either as a list or as the text of one.

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
    """Return one acceptance criterion as text; a given/when/then object is joined.

    Args:
        item: The criterion.

    Returns:
        The text.
    """
    if isinstance(item, dict) and (
        item.get("given") or item.get("when") or item.get("then")
    ):
        return (
            f"Given {item.get('given') or ''} When {item.get('when') or ''} "
            f"Then {item.get('then') or ''}"
        )
    return str(item if item is not None else "").strip()


def _read_json(path: Path) -> dict:
    """Return a saved JSON object.

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
    """Return the sha256 the recorder wrote beside an artifact, when there is one.

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

    repo_path: str
    slug: str
    title: str
    description: str
    acceptance: list[str]
    decision_ids: list[str]
    metadata: dict[str, str]


@dataclass
class Task:
    """One Task of a Story's decomposition."""

    key: str
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
    elab_key: str | None = None
    blocked_by_external: list[str] = field(default_factory=list)
    cds_bundle_path: str | None = None
    cds_build_specs: list[str] = field(default_factory=list)


def _sizes(score: dict | None) -> dict[str, str] | None:
    """Return a judged size as the metadata the Task carries, or None when unusable.

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
    """Return a number as the text JavaScript would print for it.

    Args:
        value: The number.

    Returns:
        The text.
    """
    return str(int(value)) if float(value).is_integer() else str(value)


def build_order(keys: list[str], edges: list[tuple[str, str]]) -> list[str] | None:
    """Return a build order over the keys, ties in their given order; None on a cycle.

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


def read_story(directory: Path, rel: str | None, repo: str, slug: str) -> Story:
    """Return the Story a repository's saved `story-<slug>.json` carries.

    Args:
        directory: The Epic's working directory.
        rel: The directory, relative to the project root, or None.
        repo: The repository.
        slug: Its artifact slug.

    Returns:
        The Story, with the metadata it is written with.
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
    criteria = saved.get("acceptanceCriteria")
    return Story(
        repo_path=repo,
        slug=slug,
        title=str(saved.get("title") or "").strip() or slug,
        description=str(saved.get("description") or "").strip(),
        acceptance=[ac_text(x) for x in criteria if ac_text(x)]
        if isinstance(criteria, list)
        else [],
        decision_ids=decisions,
        metadata=metadata,
    )


def _unique_tasks(raw: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    """Return the Tasks with unique keys, and each saved key's copies.

    The first Task carrying key K keeps it; the n-th (n >= 2) becomes K-n, or the next K-m
    no Task carries.

    Args:
        raw: The Tasks as saved.

    Returns:
        The Tasks, and saved key -> the keys its Tasks now carry.
    """

    def base_of(t: dict) -> str:
        return str(t.get("key") or "").strip() or "T"

    taken = {base_of(t) for t in raw}
    copies: dict[str, list[str]] = {}
    tasks = []
    for t in raw:
        base = base_of(t)
        key = base
        if base in copies:
            n = len(copies[base]) + 1
            while f"{base}-{n}" in taken:
                n += 1
            key = f"{base}-{n}"
            taken.add(key)
        copies.setdefault(base, []).append(key)
        tasks.append({**t, "key": key})
    return tasks, copies


def _unique_scores(raw_scores: object, copies: dict[str, list[str]]) -> dict[str, dict]:
    """Return each Task's score: the n-th score carrying K goes to the n-th copy of K.

    A copy left without one takes the first score carrying K.

    Args:
        raw_scores: The saved scores.
        copies: Saved key -> the keys its Tasks now carry.

    Returns:
        Task key -> score.
    """
    by_base: dict[str, list[dict]] = {}
    for s in raw_scores if isinstance(raw_scores, list) else []:
        if isinstance(s, dict) and isinstance(s.get("key"), str):
            by_base.setdefault(s["key"].strip(), []).append(s)
    scores: dict[str, dict] = {}
    for base, keys in copies.items():
        listed = by_base.get(base) or []
        for i, key in enumerate(keys):
            if listed:
                scores[key] = listed[i] if i < len(listed) else listed[0]
    return scores


def _unique_edges(
    raw_edges: object, copies: dict[str, list[str]]
) -> list[tuple[str, str]]:
    """Return the edges joining two distinct known Tasks, once each.

    An edge naming a repeated key applies to every Task that carried it.

    Args:
        raw_edges: The saved edges.
        copies: Saved key -> the keys its Tasks now carry.

    Returns:
        The `(from, to)` edges.
    """
    known = {k for keys in copies.values() for k in keys}

    def expand(k: object) -> list[str]:
        k = str(k or "").strip()
        return copies.get(k, [k])

    edges: list[tuple[str, str]] = []
    for e in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(e, dict):
            continue
        for frm in expand(e.get("from")):
            for to in expand(e.get("to")):
                pair = (frm, to)
                if frm in known and to in known and frm != to and pair not in edges:
                    edges.append(pair)
    return edges


def _surfaces(value: object) -> list[str] | None:
    """Return the known surfaces a Task declares, or None when it declares no list.

    Args:
        value: The saved `surfaces`.

    Returns:
        The surfaces, lowercased, once each; None when every name it declares is
        unknown.
    """
    if not isinstance(value, list):
        return None
    known = list(
        dict.fromkeys(s.lower() for s in str_list(value) if s.lower() in SURFACES)
    )
    return known if known or not str_list(value) else None


#: The surface whose Tasks carry the cds design system in their build contract.
UI_SURFACE = "web-ui"


def _is_bundle(path: Path) -> bool:
    """Return whether a directory is a cds hand-off bundle: it holds styles/tokens.css."""
    return (path / "styles" / "tokens.css").is_file()


def ui_authority(
    directory: Path, slug: str, packages_dir: str | None = None
) -> tuple[str | None, dict[str, list[str]]]:
    """Return the cds bundle and the build specs per delta item the detailing resolved.

    Reads `uiAuthority` of the repository's saved detailing, `recon-<slug>.json`.
    The caller's exact package root must agree with the saved selection. Without
    a caller override, the saved root is authoritative. No directory scan or
    producer environment fallback can select a different design.

    Args:
        directory: The Epic's working directory.
        slug: The Story's repository slug.
        packages_dir: The exact selected bundle root, or None to use the saved selection.

    Returns:
        The bundle path (None when none resolves), and per delta item id its build-spec
        citations: the absolute `build-spec.md` path, followed by `#<Section ID>` for
        each Section it builds.
    """
    path = directory / f"recon-{slug}.json"
    ua = _read_json(path).get("uiAuthority") if path.is_file() else None
    ua = ua if isinstance(ua, dict) else {}
    named = str(ua.get("bundlePath") or "").strip()
    entries = []
    for entry in ua.get("buildSpecs") or []:
        if not isinstance(entry, dict):
            continue
        item = str(entry.get("item") or "").strip()
        spec = str(entry.get("buildSpec") or "").strip()
        if item and spec:
            entries.append((item, spec, str_list(entry.get("sections"))))
    supplied = packages_dir or named
    if not supplied:
        raise HierarchyError(f"recon-{slug}.json: no selected cds package root")
    root = Path(supplied).expanduser().resolve()
    if not _is_bundle(root):
        raise HierarchyError(
            f"cds package is not ready at {root}: styles/tokens.css must be directly inside it; "
            "place the complete package there, not inside a timestamped child"
        )
    if named and Path(named).expanduser().resolve() != root:
        raise HierarchyError(
            f"recon-{slug}.json: saved cds package {named} conflicts with {root}"
        )
    bundle = str(root)
    cites: dict[str, list[str]] = {}
    for item, spec, sections in entries:
        candidate = Path(spec)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise HierarchyError(
                f"recon-{slug}.json: build spec is missing or outside selected package: {spec}"
            )
        spec = str(candidate)
        cites.setdefault(item, []).extend(
            [f"{spec}#{x}" for x in sections] if sections else [spec]
        )
    return bundle, cites


def check_cds_contract(slug: str, tasks: list[Task]) -> None:
    """Refuse a web-ui Task whose build contract does not name its cds bundle and build specs.

    Every Task with the web-ui surface is built from the cds design system, so its
    contract names the cds bundle and at least one `build-spec.md` citation, each of
    them a file that exists.

    Args:
        slug: The Story's repository slug.
        tasks: The Story's Tasks.

    Raises:
        HierarchyError: A web-ui Task resolves no bundle, cites no ui delta item with a
            resolved build spec, or cites a build spec that does not exist.
    """
    problems = []
    for t in tasks:
        if UI_SURFACE not in (t.surfaces or []):
            continue
        if not t.cds_bundle_path:
            problems.append(
                f"{t.key} resolves no cds bundle (the detailing names none and "
                "--packages-dir names no selected package)"
            )
        if not t.cds_build_specs:
            problems.append(
                f"{t.key} cites, in requirementIds ({', '.join(t.requirement_ids) or 'none'}), "
                f"no ui delta item recon-{slug}.json resolves to a cds build-spec.md; a ui "
                "item with no packaged build spec is packaged with cds:package-change first"
            )
        missing = sorted(
            {c.split("#", 1)[0] for c in t.cds_build_specs}
            - {
                c.split("#", 1)[0]
                for c in t.cds_build_specs
                if Path(c.split("#", 1)[0]).is_file()
            }
        )
        if missing:
            problems.append(
                f"{t.key} cites build specs that do not exist: {', '.join(missing)}"
            )
    if problems:
        msg = (
            f"tasks-{slug}.json: web-ui Tasks without their cds contract: "
            + "; ".join(problems)
        )
        raise HierarchyError(msg)


def _spec_refs(directory: Path, rel: str | None, slug: str) -> list[str]:
    """Return the Story's spec documents on disk a Task may cite, relative to the project root.

    Args:
        directory: The Epic's working directory.
        rel: The directory, relative to the project root, or None.
        slug: The Story's repository slug.

    Returns:
        The references.
    """
    names = (
        f"spec-{slug}.md",
        f"spec-{slug}.data-model.md",
        f"spec-{slug}.criteria.md",
    )
    if not rel:
        return []
    return [f"{rel}/{name}" for name in names if (directory / name).is_file()]


def read_tasks(
    directory: Path,
    rel: str | None,
    slug: str,
    repo: str,
    story_decision_ids: list[str],
    packages_dir: str | None = None,
) -> list[Task]:
    """Return the Tasks a Story's saved `tasks-<slug>.json` carries, in build order.

    Args:
        directory: The Epic's working directory.
        rel: The directory, relative to the project root, or None.
        slug: The Story's repository slug.
        repo: The Story's repository.
        story_decision_ids: The Story's decision ids, which a Task citing none inherits.
        packages_dir: The exact selected bundle root, or None to use the saved selection.

    Returns:
        The Tasks, with `depends_on` holding local keys; empty for a Story with no Tasks.

    Raises:
        HierarchyError: The file holds no `tasks` list, or its edges form a cycle.
    """
    saved = _read_json(directory / f"tasks-{slug}.json")
    if not isinstance(saved.get("tasks"), list):
        msg = f"tasks-{slug}.json holds no `tasks` list"
        raise HierarchyError(msg)
    raw = [t for t in saved["tasks"] if isinstance(t, dict)]
    unique, copies = _unique_tasks(raw)
    edges = _unique_edges(saved.get("edges"), copies)
    scores = _unique_scores(saved.get("scores"), copies)
    order = build_order([t["key"] for t in unique], edges)
    if order is None:
        msg = f"tasks-{slug}.json: the Task edges form a cycle"
        raise HierarchyError(msg)
    refs = _spec_refs(directory, rel, slug)
    verified = "true"
    strategy = (
        saved.get("testStrategy")
        if isinstance(saved.get("testStrategy"), dict)
        else None
    )
    by_key = {t["key"]: t for t in unique}
    bundle, ui_cites = (
        ui_authority(directory, slug, packages_dir)
        if any(UI_SURFACE in (_surfaces(t.get("surfaces")) or []) for t in unique)
        else (None, {})
    )
    tasks = []
    for key in order:
        t = by_key[key]
        cited = [p for p in str_list(t.get("specPaths")) if p in refs]
        surfaces = _surfaces(t.get("surfaces"))
        ui = bool(surfaces) and UI_SURFACE in surfaces
        build_specs = (
            list(
                dict.fromkeys(
                    c
                    for r in str_list(t.get("requirementIds"))
                    for c in ui_cites.get(r, [])
                )
            )
            if ui
            else []
        )
        tasks.append(
            Task(
                key=key,
                repo_path=repo,
                title=str(t.get("title") or "").strip() or key,
                description=str(t.get("description") or "").strip(),
                acceptance=[
                    ac_text(x) for x in t.get("acceptanceCriteria") or [] if ac_text(x)
                ],
                definition_of_done=str_list(t.get("definitionOfDone")),
                spec_paths=list(dict.fromkeys(cited)) or list(refs),
                spec_sections=str_list(t.get("specSections")),
                requirement_ids=str_list(t.get("requirementIds")),
                decision_ids=str_list(t.get("decisionIds")) or list(story_decision_ids),
                surfaces=surfaces,
                test_strategy=strategy,
                depends_on=[frm for frm, to in edges if to == key],
                sizes=_sizes(scores.get(key)),
                verified=verified,
                reuses=next(iter(str_list([t.get("reuses")])), None)
                if isinstance(t.get("reuses"), str)
                else None,
                blocked_by_external=list(
                    dict.fromkeys(str_list(t.get("blockedByExternal")))
                ),
                cds_bundle_path=bundle if ui else None,
                cds_build_specs=build_specs,
            )
        )
    return tasks


#: The detailing statuses that make work: a Task exists only for an item carrying one.
WORK_STATUSES = ("add", "modify", "remove")


def check_detailed_work(directory: Path, slug: str, tasks: list[Task]) -> None:
    """Refuse Tasks that build no delta item the repository's detailing marks as work.

    The detailing of a repository, `recon-<slug>.json`, gives each delta item placed in it
    a status; only `add`, `modify` and `remove` make work. Every Task cites, in its
    `requirementIds`, at least one item with one of those statuses. A Story whose detailing
    is not saved, or saves no `items` list, is not checked.

    Args:
        directory: The Epic's working directory.
        slug: The Story's repository slug.
        tasks: The Story's Tasks.

    Raises:
        HierarchyError: A Task cites no delta item that makes work.
    """
    path = directory / f"recon-{slug}.json"
    if not path.is_file():
        return
    saved = _read_json(path)
    items = saved.get("items")
    if not isinstance(items, list):
        return
    work = {
        str(i.get("id")).strip()
        for i in items
        if isinstance(i, dict) and i.get("status") in WORK_STATUSES
    }
    idle = [t.key for t in tasks if not work.intersection(t.requirement_ids)]
    if idle:
        msg = (
            f"tasks-{slug}.json: {', '.join(idle)} cite no delta item recon-{slug}.json "
            f"marks {', '.join(WORK_STATUSES)} in requirementIds; a Task is made only "
            f"for such an item ({', '.join(sorted(work)) or 'none here'})"
        )
        raise HierarchyError(msg)


def read_task_deps(directory: Path) -> list[dict]:
    """Return the saved Task edges between Stories.

    Args:
        directory: The Epic's working directory.

    Returns:
        The edges as saved (`from`, `to`, `kind`, `reason`; ends are
        `S<i>-<local key>`).
    """
    saved = _read_json(directory / "task-deps.json")
    return [e for e in saved.get("edges") or [] if isinstance(e, dict)]
