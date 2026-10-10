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
from operator import itemgetter
from pathlib import Path

import beadcontracts
import contracts
from beadcontracts import PlacedItem, TaskEdge
from cdsbundles import DESIGN_SOURCES, KINDS, bundle_problem, read_bundle
from contracts import DeltaItem, JsonObject, JsonValue, json_object
from typeguard import CollectionCheckStrategy, check_type, typechecked

#: The surfaces a Task may declare; anything else is dropped.
_ARGUMENT_ERROR: str = "Arguments violate the hierarchy input contract"


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


#: What reading a Story's Tasks normalized instead of refusing, since `take_warnings` last ran.
_WARNINGS: list[str] = []


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def take_warnings() -> list[str]:
    """Return, and forget, what reading the saved Tasks normalized instead of refusing.

    Returns:
        One line per normalization, in order.

    """
    out: list[str] = list(dict.fromkeys(_WARNINGS))
    _WARNINGS.clear()
    return out


def _acyclic(
    nodes: list[str],
    fixed: list[tuple[str, str]],
    added: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Take the edges in `added` one at a time, leaving out each that would close a cycle.

    Args:
        nodes: The graph's nodes.
        fixed: Edges already taken, acyclic among themselves.
        added: The edges to take, in order.

    Returns:
        The edges of `added` taken, and those left out.

    """
    edge: tuple[str, str]
    taken: list[tuple[str, str]] = []
    left: list[tuple[str, str]] = []
    for edge in added:
        if build_order(nodes, [*fixed, *taken, edge]) is None:
            left.append(edge)
        else:
            taken.append(edge)
    return taken, left


def _artifact_slug(text: str) -> str:
    """Return a kebab-case slug of a name, for an artifact a detailing named no slug for.

    Returns:
        The slug.

    """
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "page"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repo_slugs(repos: list[str]) -> dict[str, str]:
    """Return each repository's artifact slug: its directory name, suffixed on a collision.

    Args:
        repos: The span, in its ruled order.

    Returns:
        Repository path -> slug.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    repo: str
    slug: str
    n: int
    if not (isinstance(repos, list)):
        raise TypeError(_ARGUMENT_ERROR)
    slugs: dict[str, str] = {}
    for repo in repos:
        if repo in slugs:
            continue
        base: str = re.sub(r"[^A-Za-z0-9._-]+", "_", repo.rstrip("/").split("/")[-1]) or "repo"
        slug, n = base, 2
        while slug in slugs.values():
            slug = f"{base}-{n}"
            n += 1
        slugs[repo] = slug
    return slugs


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def elab_slug(text: JsonValue) -> str:
    """Return the title slug a Task's durable key is built from.

    Args:
        text: The title.

    Returns:
        Lowercase words joined by dashes, at most 60 characters.

    """
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:60]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def str_list(value: JsonValue) -> list[str]:
    """Return a list of non-empty, trimmed strings; anything but a list is empty.

    Args:
        value: The value.

    Returns:
        The strings.

    """
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if x is not None and str(x).strip()]


def _loose_list(value: JsonValue) -> list[str]:
    """Return a list saved either as a list or as the text of one.

    Args:
        value: A list, or a string holding a JSON or Python list.

    Returns:
        The strings.

    """
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            decoded: object = json.loads(value)
        except ValueError:
            try:
                decoded = ast.literal_eval(value)
            except ValueError, SyntaxError:
                return str_list(value)
        checked: JsonValue = check_type(decoded, JsonValue, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        return str_list(checked)
    return str_list(value)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def ac_text(item: JsonValue) -> str:
    """Return one acceptance criterion as text; a given/when/then object is joined.

    Args:
        item: The criterion.

    Returns:
        The text.

    """
    if isinstance(item, dict) and (item.get("given") or item.get("when") or item.get("then")):
        return f"Given {item.get('given') or ''} When {item.get('when') or ''} Then {item.get('then') or ''}"
    return str(item if item is not None else "").strip()


def _read_json(path: Path) -> JsonObject:
    """Return a saved JSON object.

    Args:
        path: The file.

    Returns:
        The object.

    Raises:
        HierarchyError: The file is missing or is not a JSON object.

    """
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg: str = f"{path.name} could not be read: {exc}"
        raise HierarchyError(msg) from exc
    if not isinstance(data, dict):
        msg = f"{path.name} is not a JSON object"
        raise HierarchyError(msg)
    return json_object(data)


def _meta_sha(path: Path) -> str | None:
    """Return the sha256 the recorder wrote beside an artifact, when there is one.

    Args:
        path: The artifact.

    Returns:
        The hash, or None.

    """
    try:
        meta: object = json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    fields: JsonObject = json_object(meta) if isinstance(meta, dict) else {}
    sha: JsonValue = fields.get("sha256")
    return sha if isinstance(sha, str) and sha else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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

    def __post_init__(self) -> None:
        """Validate every constructor field, including all collection entries."""
        check_type(self.repo_path, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.slug, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.title, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.description, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.acceptance, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.decision_ids, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.metadata, dict[str, str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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
    test_strategy: JsonObject | None
    depends_on: list[str]
    sizes: dict[str, str] | None
    verified: str
    reuses: str | None = None
    elab_key: str | None = None
    blocked_by_external: list[str] = field(default_factory=list)
    cds_bundle_path: str | None = None
    cds_build_specs: list[str] = field(default_factory=list)
    cds_design_source: str | None = None
    cds_bundles: list[str] = field(default_factory=list)
    cds_artifacts: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate every constructor field, including all collection entries."""
        check_type(self.key, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.repo_path, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.title, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.description, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.acceptance, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.definition_of_done, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.spec_paths, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.spec_sections, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.requirement_ids, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.decision_ids, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.surfaces, list[str] | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.test_strategy, JsonObject | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.depends_on, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.sizes, dict[str, str] | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.verified, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.reuses, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.elab_key, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.blocked_by_external, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.cds_bundle_path, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.cds_build_specs, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.cds_design_source, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.cds_bundles, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(
            self.cds_artifacts,
            list[dict[str, str]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )


def size_metadata(score: JsonObject | None) -> dict[str, str] | None:
    """Return a judged size as the metadata the Task carries, or None when unusable.

    Args:
        score: The decomposition's score entry for the Task.

    Returns:
        The four size keys, or None.

    """
    size: int | float
    low: int | float
    high: int | float
    confidence: int | float
    if not isinstance(score, dict):
        return None
    values: list[int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None] = [
        score.get(k) for k in ("jobSize", "sizeLow", "sizeHigh", "sizeConfidence")
    ]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in values):
        return None
    size, low, high, confidence = check_type(
        values,
        list[int | float],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    if not (low <= size <= high) or confidence > 100:  # ruff: ignore[magic-value-comparison] - a percent
        return None
    return dict(
        zip(
            SIZE_KEYS,
            (_num(size), _num(low), _num(high), _num(confidence)),
            strict=True,
        ),
    )


def _num(value: float) -> str:
    """Return a number as the text JavaScript would print for it.

    Args:
        value: The number.

    Returns:
        The text.

    """
    return str(int(value)) if float(value).is_integer() else str(value)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def build_order(keys: list[str], edges: list[tuple[str, str]]) -> list[str] | None:
    """Return a build order over the keys, ties in their given order; None on a cycle.

    Args:
        keys: The Task keys.
        edges: `(from, to)`: from is built before to.

    Returns:
        The keys in build order, or None.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    frm: str
    to: str
    nxt: str
    if not (isinstance(keys, list)) or not (isinstance(edges, list)):
        raise TypeError(_ARGUMENT_ERROR)
    rank: dict[str, int] = {k: i for i, k in enumerate(keys)}
    indegree: dict[str, int] = dict.fromkeys(keys, 0)
    out: dict[str, list[str]] = {k: [] for k in keys}
    for frm, to in edges:
        indegree[to] += 1
        out[frm].append(to)
    ready: list[str] = [k for k in keys if indegree[k] == 0]
    order: list[str] = []
    while ready:
        ready.sort(key=rank.__getitem__)
        key: str = ready.pop(0)
        order.append(key)
        for nxt in out[key]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    return order if len(order) == len(keys) else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_story(directory: Path, rel: str | None, repo: str, slug: str) -> Story:
    """Return the Story a repository's saved `story-<slug>.json` carries.

    Args:
        directory: The Epic's working directory.
        rel: The directory, relative to the project root, or None.
        repo: The repository.
        slug: Its artifact slug.

    Returns:
        The Story, with the metadata it is written with.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    key: str
    name: str
    if (
        not (isinstance(directory, Path))
        or not (isinstance(rel, str) or rel is None)
        or not (isinstance(repo, str))
        or not (isinstance(slug, str))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    saved: dict[str, contracts.JsonValue] = _read_json(directory / f"story-{slug}.json")
    metadata: dict[str, str] = {"elab_key": f"story:{slug}", "repoPath": repo}
    decisions: list[str] = list(dict.fromkeys(_loose_list(saved.get("decisionIds"))))
    if decisions:
        metadata["decision_ids"] = json.dumps(
            decisions,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    if rel:
        entries: list[tuple[str, str]] = [
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
            sha: str | None = _meta_sha(directory / name)
            if sha:
                metadata[f"artifact_{key}_sha256"] = sha
    criteria: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = saved.get(
        "acceptanceCriteria",
    )
    return Story(
        repo_path=repo,
        slug=slug,
        title=str(saved.get("title") or "").strip() or slug,
        description=str(saved.get("description") or "").strip(),
        acceptance=[ac_text(x) for x in criteria if ac_text(x)] if isinstance(criteria, list) else [],
        decision_ids=decisions,
        metadata=metadata,
    )


def _unique_tasks(raw: list[JsonObject]) -> tuple[list[JsonObject], dict[str, list[str]]]:
    """Return the Tasks with unique keys, and each saved key's copies.

    The first Task carrying key K keeps it; the n-th (n >= 2) becomes K-n, or the next K-m
    no Task carries.

    Args:
        raw: The Tasks as saved.

    Returns:
        The Tasks, and saved key -> the keys its Tasks now carry.

    """
    t: JsonObject

    def base_of(t: JsonObject) -> str:
        return str(t.get("key") or "").strip() or "T"

    taken: set[str] = {base_of(t) for t in raw}
    copies: dict[str, list[str]] = {}
    tasks: list[dict[str, int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None]] = []
    for t in raw:
        base: str = base_of(t)
        key: str = base
        if base in copies:
            n: int = len(copies[base]) + 1
            while f"{base}-{n}" in taken:
                n += 1
            key = f"{base}-{n}"
            taken.add(key)
        copies.setdefault(base, []).append(key)
        tasks.append({**t, "key": key})
    return tasks, copies


def _unique_scores(raw_scores: JsonValue, copies: dict[str, list[str]]) -> dict[str, JsonObject]:
    """Return each Task's score: the n-th score carrying K goes to the n-th copy of K.

    A copy left without one takes the first score carrying K.

    Args:
        raw_scores: The saved scores.
        copies: Saved key -> the keys its Tasks now carry.

    Returns:
        Task key -> score.

    """
    s: bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
    base: str
    keys: list[str]
    i: int
    key: str
    by_base: dict[str, list[JsonObject]] = {}
    for s in raw_scores if isinstance(raw_scores, list) else []:
        if isinstance(s, dict):
            score_key: JsonValue = s.get("key")
            if isinstance(score_key, str):
                by_base.setdefault(score_key.strip(), []).append(s)
    scores: dict[str, JsonObject] = {}
    for base, keys in copies.items():
        listed: list[contracts.JsonObject] = by_base.get(base) or []
        for i, key in enumerate(keys):
            if listed:
                scores[key] = listed[i] if i < len(listed) else listed[0]
    return scores


def _unique_edges(
    raw_edges: JsonValue,
    copies: dict[str, list[str]],
) -> list[tuple[str, str]]:
    """Return the edges joining two distinct known Tasks, once each.

    An edge naming a repeated key applies to every Task that carried it.

    Args:
        raw_edges: The saved edges.
        copies: Saved key -> the keys its Tasks now carry.

    Returns:
        The `(from, to)` edges.

    """
    e: bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
    frm: str
    to: str
    known: set[str] = {k for keys in copies.values() for k in keys}

    def expand(k: JsonValue) -> list[str]:
        k = str(k or "").strip()
        return copies.get(k, [k])

    edges: list[tuple[str, str]] = []
    for e in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(e, dict):
            continue
        for frm in expand(e.get("from")):
            for to in expand(e.get("to")):
                pair: tuple[str, str] = (frm, to)
                if frm in known and to in known and frm != to and pair not in edges:
                    edges.append(pair)
    return edges


def _surfaces(value: JsonValue) -> list[str] | None:
    """Return the known surfaces a Task declares, or None when it declares no list.

    Args:
        value: The saved `surfaces`.

    Returns:
        The surfaces, lowercased, once each; None when every name it declares is
        unknown.

    """
    if not isinstance(value, list):
        return None
    known: list[str] = list(
        dict.fromkeys(s.lower() for s in str_list(value) if s.lower() in SURFACES),
    )
    return known if known or not str_list(value) else None


#: The surface whose Tasks carry the cds design system in their build contract.
UI_SURFACE = "web-ui"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass
class UiDesign:
    """The design source one `ui` delta item takes, as the detailing resolved it."""

    source: str
    bundle: str | None = None
    cites: list[str] = field(default_factory=list)
    artifact: dict[str, str] | None = None

    def __post_init__(self) -> None:
        """Validate every constructor field, including all collection entries."""
        check_type(self.source, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.bundle, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.cites, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.artifact, dict[str, str] | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _design_source(source: str, slug: str, item: str) -> str:
    if source not in DESIGN_SOURCES:
        _WARNINGS.append(f"recon-{slug}.json: ui item {item} has design source {json.dumps(source)}; taken as cds")
        return "cds"
    return source


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def ui_authority(
    directory: Path,
    slug: str,
    packages_dir: str | None = None,
) -> dict[str, UiDesign]:
    """Return the design source of each `ui` delta item the detailing resolved.

    Reads `uiAuthority.uiItems` of the repository's saved detailing, `recon-<slug>.json`.
    Each item takes `bundle` (a cds bundle the owner supplied packages it), `cds` (it changes
    design and is designed with the CDS design system) or `none` (it changes no design).
    A design source outside those is `cds`; a `cds` item with no artifact gets a `page`
    named for the item; a `bundle` item whose bundle or build spec cannot be built from is
    `cds`. Each is noted in `take_warnings`.

    Args:
        directory: The Epic's working directory.
        slug: The Story's repository slug.
        packages_dir: The packages directory a cited bundle must sit in, or None.

    Returns:
        Per delta item id its design: the source, and for a `bundle` item the bundle path
        and its build-spec citations (the absolute `build-spec.md` path, followed by
        `#<Section ID>` for each Section it builds).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    entry: JsonValue
    if (
        not (isinstance(directory, Path))
        or not (isinstance(slug, str))
        or not (isinstance(packages_dir, str) or packages_dir is None)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    path: Path = directory / f"recon-{slug}.json"
    ua: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = (
        _read_json(path).get("uiAuthority") if path.is_file() else None
    )
    ua = json_object(ua) if isinstance(ua, dict) else {}
    del packages_dir
    designs: dict[str, UiDesign] = {}
    for entry in check_type(
        ua.get("uiItems") or [],
        list[JsonValue],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        if not isinstance(entry, dict):
            continue
        item: str = str(entry.get("item") or "").strip()
        source: str = str(entry.get("designSource") or "").strip()
        if not item or item in designs:
            continue
        source = _design_source(source, slug, item)
        raw_art: dict[str, contracts.JsonValue] = (
            json_object(entry["artifact"]) if isinstance(entry.get("artifact"), dict) else {}
        )
        artifact: dict[str, str] = {
            "kind": str(raw_art.get("kind") or "").strip(),
            "slug": str(raw_art.get("slug") or "").strip(),
        }
        if source == "none":
            designs[item] = UiDesign(source)
            continue
        if source == "bundle":
            bundle: str = str(entry.get("bundle") or "").strip()
            spec: str = str(entry.get("buildSpec") or "").strip()
            problem: str | None = bundle_problem(bundle, spec)
            if problem:
                _WARNINGS.append(
                    f"recon-{slug}.json: ui item {item}: {problem}; taken as cds",
                )
                source = "cds"
        if source == "cds":
            if artifact["kind"] not in KINDS or not artifact["slug"]:
                artifact = {"kind": "page", "slug": _artifact_slug(item)}
                _WARNINGS.append(
                    f"recon-{slug}.json: cds ui item {item} names no artifact; taken as page {artifact['slug']}",
                )
            designs[item] = UiDesign(source, artifact=artifact)
            continue
        root: Path = Path(bundle).resolve()
        spec = str(Path(spec).resolve())
        sections: list[str] = str_list(entry.get("sections"))
        held: beadcontracts.Bundle | None = read_bundle(root)
        designs[item] = UiDesign(
            "bundle",
            str(root),
            [f"{spec}#{x}" for x in sections] if sections else [spec],
            {"kind": held["kind"] if held else "", "slug": held["slug"] if held else ""},
        )
    return designs


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_design(
    requirement_ids: list[str],
    designs: dict[str, UiDesign],
) -> tuple[str, list[str], list[str], list[dict[str, str]]]:
    """Return the design source a web-ui Task takes from the `ui` items it cites.

    `bundle` when any cited item takes a supplied bundle, else `cds` when any takes the CDS
    design system or the Task cites no `ui` item, else `none`.

    Args:
        requirement_ids: The delta item ids the Task cites.
        designs: Per delta item id its design.

    Returns:
        The source, the distinct bundles of the cited `bundle` items, their build-spec
        citations, and the distinct artifacts (`{kind, slug}`) of the cited `bundle` or `cds`
        items.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(requirement_ids, list)) or not (isinstance(designs, dict)):
        raise TypeError(_ARGUMENT_ERROR)
    cited: list[UiDesign] = [designs[r] for r in requirement_ids if r in designs]
    sources: set[str] = {d.source for d in cited}
    bundles: list[str] = list(dict.fromkeys(d.bundle for d in cited if d.bundle))
    cites: list[str] = list(dict.fromkeys(c for d in cited for c in d.cites))
    keyed: set[tuple[str, str]] = {(d.artifact["kind"], d.artifact["slug"]) for d in cited if d.artifact}
    artifacts: list[dict[str, str]] = [{"kind": k, "slug": s} for k, s in sorted(keyed)]
    if "bundle" in sources:
        return "bundle", bundles, cites, artifacts
    if "cds" in sources or not cited:
        return "cds", [], [], artifacts
    return "none", [], [], []


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_cds_contract(slug: str, tasks: list[Task]) -> None:
    """Settle each web-ui Task's build contract on one design source and one artifact.

    A Task citing ui items of more than one artifact keeps the first for its contract and
    names the others in its description. A `bundle` Task citing more than one bundle builds
    against the newest; with no build-spec citation of that bundle, it takes the build spec
    the bundle's `bundle.json` names. Each is noted in `take_warnings`.

    Args:
        slug: The Story's repository slug.
        tasks: The Story's Tasks; changed in place.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    t: Task
    if not (isinstance(slug, str)) or not (isinstance(tasks, list)):
        raise TypeError(_ARGUMENT_ERROR)
    for t in tasks:
        if UI_SURFACE not in (t.surfaces or []):
            continue
        if len(t.cds_artifacts) > 1:
            others: list[dict[str, str]] = t.cds_artifacts[1:]
            t.cds_artifacts = t.cds_artifacts[:1]
            named: str = ", ".join(f"{a['kind']} {a['slug']}" for a in others)
            t.description = (f"{t.description}\n\nIt also builds ui items of: {named}.").strip()
            _WARNINGS.append(
                f"tasks-{slug}.json: {t.key} builds ui items of more than one artifact; "
                f"its contract takes {t.cds_artifacts[0]['kind']} "
                f"{t.cds_artifacts[0]['slug']} and its description names {named}",
            )
        if t.cds_design_source != "bundle":
            continue
        if not t.cds_bundle_path and t.cds_bundles:
            held: list[beadcontracts.Bundle] = [b for b in (read_bundle(Path(p)) for p in t.cds_bundles) if b]
            newest: beadcontracts.Bundle | None = max(held, key=itemgetter("createdAt")) if held else None
            t.cds_bundle_path = newest["path"] if newest else t.cds_bundles[0]
            _WARNINGS.append(
                f"tasks-{slug}.json: {t.key} cites more than one cds bundle; it builds "
                f"against the newest, {t.cds_bundle_path}",
            )
        root: str = t.cds_bundle_path or ""
        own: list[str] = [c for c in t.cds_build_specs if root and c.startswith(f"{root}/")]
        if not own:
            own_bundle: beadcontracts.Bundle | None = read_bundle(Path(root)) if root else None
            own = [own_bundle["buildSpec"]] if own_bundle else []
        t.cds_build_specs = own


def _spec_refs(directory: Path, rel: str | None, slug: str) -> list[str]:
    """Return the Story's spec documents on disk a Task may cite, relative to the project root.

    Args:
        directory: The Epic's working directory.
        rel: The directory, relative to the project root, or None.
        slug: The Story's repository slug.

    Returns:
        The references.

    """
    names: tuple[str, str, str] = (
        f"spec-{slug}.md",
        f"spec-{slug}.data-model.md",
        f"spec-{slug}.criteria.md",
    )
    if not rel:
        return []
    return [f"{rel}/{name}" for name in names if (directory / name).is_file()]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class ReadTaskOptions:
    """Provide repository placement and inherited Story facts for saved Tasks."""

    slug: str
    repo: str
    story_decision_ids: list[str]
    packages_dir: str | None = None

    def __post_init__(self) -> None:
        """Validate all inherited identifiers and the optional bundle path."""
        check_type(self.slug, str)
        check_type(self.repo, str)
        check_type(self.story_decision_ids, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.packages_dir, str | None)


@dataclass(frozen=True)
class _TaskSources:
    options: ReadTaskOptions
    refs: list[str]
    strategy: JsonObject | None
    edges: list[tuple[str, str]]
    scores: dict[str, JsonObject]
    designs: dict[str, UiDesign]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_tasks(directory: Path, rel: str | None, options: ReadTaskOptions) -> list[Task]:
    """Return the Tasks a Story's saved `tasks-<slug>.json` carries, in build order.

    Args:
        directory: The Epic's working directory.
        rel: The directory, relative to the project root, or None.
        options: Repository placement, inherited Story decisions, and bundle location.

    Returns:
        The Tasks, with `depends_on` holding local keys; empty for a Story with no Tasks.

    Raises:
        TypeError: An argument violates the declared input contract.
        HierarchyError: The file holds no `tasks` list.

    """
    unique: list[JsonObject]
    copies: dict[str, list[str]]
    edges: list[tuple[str, str]]
    left: list[tuple[str, str]]
    if (
        not (isinstance(directory, Path))
        or not (isinstance(rel, str) or rel is None)
        or not (isinstance(options, ReadTaskOptions))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    slug: str = options.slug
    saved: dict[str, contracts.JsonValue] = _read_json(directory / f"tasks-{slug}.json")
    if not isinstance(saved.get("tasks"), list):
        msg: str = f"tasks-{slug}.json holds no `tasks` list"
        raise HierarchyError(msg)
    raw: list[contracts.JsonObject] = check_type(
        saved["tasks"],
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    unique, copies = _unique_tasks(raw)
    edges = _unique_edges(saved.get("edges"), copies)
    scores: dict[str, contracts.JsonObject] = _unique_scores(saved.get("scores"), copies)
    nodes: list[str] = [check_type(t["key"], str) for t in unique]
    edges, left = _acyclic(nodes, [], list(edges))
    _WARNINGS.extend(f"tasks-{slug}.json: the edge {frm} -> {to} closes a cycle; dropped" for frm, to in left)
    order: list[str] | None = build_order(nodes, edges)
    if order is None:
        message: str = "Task edges remain cyclic after normalization"
        raise HierarchyError(message)
    sources: _TaskSources = _TaskSources(
        options,
        _spec_refs(directory, rel, slug),
        json_object(saved["testStrategy"]) if isinstance(saved.get("testStrategy"), dict) else None,
        edges,
        scores,
        ui_authority(directory, slug, options.packages_dir)
        if any(UI_SURFACE in (_surfaces(t.get("surfaces")) or []) for t in unique)
        else {},
    )
    by_key: dict[str, dict[str, contracts.JsonValue]] = {check_type(t["key"], str): t for t in unique}
    return [_read_task(key, _task_document(by_key[key]), sources) for key in order]


@dataclass(frozen=True)
class _TaskDocument:
    title: str
    description: str
    acceptance: tuple[str, ...]
    definition_of_done: tuple[str, ...]
    spec_paths: tuple[str, ...]
    spec_sections: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    surfaces: tuple[str, ...] | None
    reuses: str | None
    blocked_by_external: tuple[str, ...]

    def __post_init__(self) -> None:
        values: tuple[str, ...]
        if not isinstance(self.title, str) or not isinstance(self.description, str):
            raise TypeError(_ARGUMENT_ERROR)
        for values in (
            self.acceptance,
            self.definition_of_done,
            self.spec_paths,
            self.spec_sections,
            self.requirement_ids,
            self.decision_ids,
            self.blocked_by_external,
        ):
            if not isinstance(values, tuple) or any(not isinstance(value, str) for value in values):
                raise TypeError(_ARGUMENT_ERROR)
        if self.surfaces is not None and (
            not isinstance(self.surfaces, tuple) or any(not isinstance(value, str) for value in self.surfaces)
        ):
            raise TypeError(_ARGUMENT_ERROR)
        if self.reuses is not None and not isinstance(self.reuses, str):
            raise TypeError(_ARGUMENT_ERROR)


def _task_strings(value: JsonValue) -> tuple[str, ...]:
    if value is None:
        return ()
    values: list[str] = check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    return tuple(item.strip() for item in values if item.strip())


def _task_document(value: JsonObject) -> _TaskDocument:
    title: str = check_type(value.get("title") or "", str).strip()
    description: str = check_type(value.get("description") or "", str).strip()
    criteria: list[JsonValue] = check_type(
        value.get("acceptanceCriteria") or [],
        list[JsonValue],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    surfaces: list[str] | None = _surfaces(value.get("surfaces"))
    reuses: JsonValue = value.get("reuses")
    return _TaskDocument(
        title=title,
        description=description,
        acceptance=tuple(ac_text(item) for item in criteria if ac_text(item)),
        definition_of_done=_task_strings(value.get("definitionOfDone")),
        spec_paths=_task_strings(value.get("specPaths")),
        spec_sections=_task_strings(value.get("specSections")),
        requirement_ids=_task_strings(value.get("requirementIds")),
        decision_ids=_task_strings(value.get("decisionIds")),
        surfaces=tuple(surfaces) if surfaces is not None else None,
        reuses=check_type(reuses, str).strip() or None if reuses is not None else None,
        blocked_by_external=_task_strings(value.get("blockedByExternal")),
    )


def _read_task(key: str, t: _TaskDocument, sources: _TaskSources) -> Task:
    """Construct one Task from its validated source and shared Story facts.

    Returns:
        The normalized Task ready for dependency derivation.

    """
    source: str | None
    bundles: list[str]
    build_specs: list[str]
    artifacts: list[dict[str, str]]
    cited: list[str] = [p for p in t.spec_paths if p in sources.refs]
    surfaces: list[str] | None = list(t.surfaces) if t.surfaces is not None else None
    ui: bool = surfaces is not None and UI_SURFACE in surfaces
    source, bundles, build_specs, artifacts = (
        task_design(list(t.requirement_ids), sources.designs) if ui else (None, [], [], [])
    )
    return Task(
        key=key,
        repo_path=sources.options.repo,
        title=t.title or key,
        description=t.description,
        acceptance=list(t.acceptance),
        definition_of_done=list(t.definition_of_done),
        spec_paths=list(dict.fromkeys(cited)) or list(sources.refs),
        spec_sections=list(t.spec_sections),
        requirement_ids=list(t.requirement_ids),
        decision_ids=list(t.decision_ids) or list(sources.options.story_decision_ids),
        surfaces=surfaces,
        test_strategy=sources.strategy,
        depends_on=[frm for frm, to in sources.edges if to == key],
        sizes=size_metadata(sources.scores.get(key)),
        verified="true",
        reuses=t.reuses,
        blocked_by_external=list(
            dict.fromkeys(list(t.blocked_by_external)),
        ),
        cds_bundle_path=bundles[0] if len(bundles) == 1 else None,
        cds_build_specs=build_specs,
        cds_design_source=source,
        cds_bundles=bundles,
        cds_artifacts=artifacts,
    )


#: The detailing statuses that make work: a Task exists only for an item carrying one.
WORK_STATUSES = ("add", "modify", "remove")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def work_items(directory: Path, slug: str) -> list[str]:
    """Every item placed in the repository is work; no built-state judgment.

    Returns:
        The computed work items result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)) or not (isinstance(slug, str)):
        raise TypeError(_ARGUMENT_ERROR)
    return [key for key, item in placed_items(directory).items() if item["slug"] == slug]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def uncited_work(directory: Path, slug: str, tasks: list[Task]) -> list[str]:
    """Return the work items of a repository that no Task cites in its `requirementIds`.

    Args:
        directory: The Epic's working directory.
        slug: The repository slug.
        tasks: The Story's Tasks.

    Returns:
        The ids the detailing marks add, modify or remove and no Task cites, in the
        detailing's order; empty when every one is cited or there is none.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)) or not (isinstance(slug, str)) or not (isinstance(tasks, list)):
        raise TypeError(_ARGUMENT_ERROR)
    cited: set[str] = {r for t in tasks for r in t.requirement_ids}
    return [i for i in work_items(directory, slug) or [] if i not in cited]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def item_briefs(directory: Path, slug: str, ids: list[str]) -> list[PlacedItem]:
    """Return architecture facts for the precise uncited items.

    Returns:
        The computed item briefs result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)) or not (isinstance(slug, str)) or not (isinstance(ids, list)):
        raise TypeError(_ARGUMENT_ERROR)
    items: dict[str, beadcontracts.PlacedItem] = placed_items(directory)
    return [items[key] for key in ids if key in items and items[key]["slug"] == slug]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_detailed_work(directory: Path, slug: str, tasks: list[Task]) -> None:
    """Warn when a Task cites no placed item; never classify existing code.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)) or not (isinstance(slug, str)) or not (isinstance(tasks, list)):
        raise TypeError(_ARGUMENT_ERROR)
    listed: list[str] = work_items(directory, slug)
    if listed is None:
        return
    work: set[str] = set(listed)
    idle: list[str] = [t.key for t in tasks if not work.intersection(t.requirement_ids)]
    if idle:
        _WARNINGS.append(
            f"tasks-{slug}.json: {', '.join(idle)} cite no placed item in requirementIds "
            f"({', '.join(sorted(work)) or 'none here'})",
        )


#: The listing `depscore.py arch-delta --save` writes in the Epic's working directory.
DELTA_ITEMS_FILE = "delta-items.json"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def delta_requires(directory: Path) -> dict[str, list[str]] | None:
    """Return each delta item's `requires`, from the saved `delta-items.json`.

    Args:
        directory: The Epic's working directory.

    Returns:
        Item id -> the ids it needs built first; None when the listing is not saved or no
        item carries `requires` (a delta with no prerequisite closure).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    path: Path = directory / DELTA_ITEMS_FILE
    if not path.is_file():
        return None
    items: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = _read_json(path).get(
        "items",
    )
    if not isinstance(items, list) or not any(isinstance(i, dict) and "requires" in i for i in items):
        return None
    return {str(i.get("id")): str_list(i.get("requires")) for i in items if isinstance(i, dict) and i.get("id")}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def planned_prerequisites(directory: Path) -> dict[str, str]:
    """Return the prerequisite items an open bead of another Epic already plans.

    Such an item is placed in no repository: its bead is the plan, and the Tasks that need
    it are blocked by that bead.

    Args:
        directory: The Epic's working directory.

    Returns:
        Item id -> the bead that plans it; empty when `delta-items.json` is not saved.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    path: Path = directory / DELTA_ITEMS_FILE
    items: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = (
        _read_json(path).get("items") if path.is_file() else None
    )
    return {
        str(i["id"]): str(i["plannedBy"]).strip()
        for i in (items if isinstance(items, list) else [])
        if isinstance(i, dict)
        and i.get("id")
        and i.get("kind") == "prerequisite"
        and i.get("state") == "planned"
        and str(i.get("plannedBy") or "").strip()
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def detailed_items(directory: Path) -> dict[str, PlacedItem]:
    """Compatibility name for the declared placement map; contains no status labels.

    Returns:
        The computed detailed items result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    return placed_items(directory)


def _task_builders(tasks: list[Task]) -> dict[str, list[str]]:
    """Index the Tasks that cite each architecture requirement.

    Returns:
        Requirement identifiers mapped to their builder Task keys.

    """
    t: Task
    item: str
    builders: dict[str, list[str]] = {}
    for t in tasks:
        for item in t.requirement_ids:
            builders.setdefault(item, []).append(t.key)
    return builders


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def derive_prerequisites(directory: Path, slug: str, tasks: list[Task]) -> list[Task]:
    """Derive in-Story prerequisite edges from placed architecture items.

    Missing builders remain coverage findings. Cross-repository prerequisites are
    connected by closure_task_edges after every repository's Tasks exist.
    Cyclic derived edges are dropped and reported as normalization warnings.

    Returns:
        The computed derive prerequisites result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    t: Task
    x: str
    y: str
    _taken: list[tuple[str, str]]
    left: list[tuple[str, str]]
    frm: str
    to: str
    if not (isinstance(directory, Path)) or not (isinstance(slug, str)) or not (isinstance(tasks, list)):
        raise TypeError(_ARGUMENT_ERROR)
    requires: dict[str, list[str]] | None = delta_requires(directory)
    if requires is None:
        return tasks
    detailed: dict[str, beadcontracts.PlacedItem] = detailed_items(directory)
    builders: dict[str, list[str]] = _task_builders(tasks)
    problems: list[str] = []
    saved_edges: list[tuple[str, str]] = [(d, t.key) for t in tasks for d in t.depends_on]
    for t in tasks:
        for x in t.requirement_ids:
            own: beadcontracts.PlacedItem | None = detailed.get(x)
            if own is None or own["slug"] != slug:
                continue
            for y in requires.get(x, []):
                d: beadcontracts.PlacedItem | None = detailed.get(y)
                if d is None or y in t.requirement_ids or d["slug"] != slug:
                    continue
                found: list[str] = [k for k in builders.get(y, []) if k != t.key]
                if not found:
                    problems.append(
                        f"{t.key} builds {x}, which requires {y}; no Task of this Story builds it",
                    )
                t.depends_on.extend(k for k in found if k not in t.depends_on)
    _WARNINGS.extend(f"tasks-{slug}.json: {p}" for p in problems)
    by_key: dict[str, Task] = {t.key: t for t in tasks}
    nodes: list[str] = [t.key for t in tasks]
    derived: list[tuple[str, str]] = [
        (d, t.key) for t in tasks for d in t.depends_on if (d, t.key) not in set(saved_edges)
    ]
    _taken, left = _acyclic(nodes, saved_edges, derived)
    for frm, to in left:
        by_key[to].depends_on.remove(frm)
        _WARNINGS.append(
            f"tasks-{slug}.json: the derived edge {frm} -> {to} closes a cycle; dropped",
        )
    return _ordered_tasks(nodes, tasks, by_key)


def _ordered_tasks(nodes: list[str], tasks: list[Task], by_key: dict[str, Task]) -> list[Task]:
    order: list[str] | None = build_order(nodes, [(d, t.key) for t in tasks for d in t.depends_on])
    if order is None:
        message: str = "Task prerequisite graph remains cyclic"
        raise HierarchyError(message)
    return [by_key[k] for k in order]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_task_deps(directory: Path) -> list[TaskEdge]:
    """Return the saved Task edges between Stories.

    Args:
        directory: The Epic's working directory.

    Returns:
        The edges as saved (`from`, `to`, `kind`, `reason`; ends are
        `S<i>-<local key>`).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    saved: dict[str, contracts.JsonValue] = _read_json(directory / "task-deps.json")
    return check_type(
        saved.get("edges") or [],
        list[TaskEdge],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def placed_items(directory: Path) -> dict[str, PlacedItem]:
    """Join declared placements to architecture items, without inspecting code.

    Returns:
        The computed placed items result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(directory, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    scope: dict[str, contracts.JsonValue] = _read_json(directory / "repo-scoping.json")
    placements: list[contracts.JsonObject] = check_type(
        scope["placements"],
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    repos: list[str] = list(dict.fromkeys(check_type(p["repoPath"], str) for p in placements))
    slugs: dict[str, str] = repo_slugs(repos)
    items: dict[str, contracts.DeltaItem] = {
        check_type(i["id"], str): i
        for i in check_type(
            _read_json(directory / "delta-items.json")["items"],
            list[DeltaItem],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    }
    return {
        item: {**items[item], "slug": slugs[check_type(p["repoPath"], str)], "repoPath": check_type(p["repoPath"], str)}
        for p in placements
        for item in check_type(p["itemIds"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    }
