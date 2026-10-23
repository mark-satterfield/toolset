"""Readers for the Story and Task documents an Epic's elaboration saves.

prd-to-spec saves a Story document and a Tasks file for each repository, and one file of Task
edges between Stories. Every reader is handed the path of each file it reads (`StoryFiles`,
`SpanFiles`, `SpanStories`) and derives none. These readers turn those files into the Stories
and Tasks `beadwrite` writes into beads. A Task's `key` is its local decomposition key (`T3`);
`depends_on` holds local keys of the same Story.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from operator import itemgetter
from pathlib import Path
from typing import Final

import beadcontracts
import contracts
import portfolio_path  # ruff: ignore[unused-import] - Puts the artifact-handoff contract modules on the path first.
from beadcontracts import StoryBuild, TaskEdge
from cdsbundles import artifact_kind, bundle_problem, read_bundle
from contracts import DeltaItem, JsonObject, JsonValue, json_object
from typeguard import CollectionCheckStrategy, check_type, typechecked

# The bead metadata keys are generated from the beads-contract schema, their one definition.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))

# isort: split
from recon_contract import (
    DEFAULT_ARTIFACT_KIND,
    DESIGN_SOURCE_BUNDLE,
    DESIGN_SOURCE_CDS,
    DESIGN_SOURCE_NONE,
    KEY_ARTIFACT,
    KEY_BUILD_SPEC,
    KEY_BUNDLE,
    KEY_DESIGN_SOURCE,
    KEY_ITEM,
    KEY_KIND,
    KEY_SECTIONS,
    KEY_SLUG,
    KEY_UI_AUTHORITY,
    KEY_UI_ITEMS,
    DesignSource,
    ReconDetailing,
    UiArtifact,
    UiAuthority,
    UiItem,
    read_detailing,
)
from recon_contract import ArtifactKind as UiArtifactKind

# isort: split
from bead_metadata import (
    ARG_ACCEPTANCE_CRITERIA,
    ARG_DECISION_IDS,
    ARG_DEFINITION_OF_DONE,
    ARG_REQUIREMENT_IDS,
    ARG_SPEC_PATHS,
    ARG_SPEC_SECTIONS,
    ARG_SURFACES,
    ARG_TEST_STRATEGY,
    CDS_DESIGN_SOURCE_BUNDLE,
    CDS_DESIGN_SOURCE_CDS,
    CDS_DESIGN_SOURCE_NONE,
    KEY_DECISION_IDS,
    KEY_ELAB_KEY,
    KEY_REPO_PATH,
    KEY_WSJF_SIZE_CONFIDENCE,
    KEY_WSJF_SIZE_ESTIMATE,
    KEY_WSJF_SIZE_HIGH,
    KEY_WSJF_SIZE_LOW,
    SPEC_ASPECT_KIND,
    ArtifactKind,
    CdsDesignSource,
    artifact_key,
)

# isort: split
from infra_vocabulary import INFRA_TYPES
from matrix_contract import KIND_INFRASTRUCTURE, KIND_STACK, Entry, EntryId
from matrixstore import Matrix, as_entry_id, kind_of, matrix_path, read_matrix
from matrixtraverse import capabilities

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
SIZE_KEYS: Final[tuple[str, ...]] = (
    KEY_WSJF_SIZE_ESTIMATE,
    KEY_WSJF_SIZE_LOW,
    KEY_WSJF_SIZE_HIGH,
    KEY_WSJF_SIZE_CONFIDENCE,
)


#: The slug of an artifact whose item name yields no slug characters; a slug, not an artifact kind.
_FALLBACK_ARTIFACT_SLUG: Final[str] = "page"

#: The bead build-contract design source each detailing design source maps to.
_BEAD_DESIGN_SOURCE: Final[dict[DesignSource, CdsDesignSource]] = {
    DESIGN_SOURCE_BUNDLE: CDS_DESIGN_SOURCE_BUNDLE,
    DESIGN_SOURCE_CDS: CDS_DESIGN_SOURCE_CDS,
    DESIGN_SOURCE_NONE: CDS_DESIGN_SOURCE_NONE,
}


class HierarchyError(ValueError):
    """The saved documents do not describe a Story or Tasks that can be written."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class SpanFiles:
    """The two files an elaboration's span step wrote, each at the path the caller was handed.

    ``span`` holds the placements: which repository builds which items. ``elements`` holds the
    items themselves, each with the ids of the items it requires.
    """

    span: Path
    elements: Path


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class StoryFiles:
    """The saved files of one repository's Story, each at the path the caller was handed.

    ``specs`` are the contracts, data-model and criteria documents, in that order. ``tasks`` is
    the Tasks file, once the Story is decomposed. ``detailing`` is the repository's detailing
    file, when one was written.
    """

    slug: str
    repo: str
    scope: SpanFiles
    story: Path
    specs: tuple[Path, ...] = ()
    tasks: Path | None = None
    detailing: Path | None = None

    @property
    def tasks_file(self) -> Path:
        """The Tasks file of a Story that is decomposed.

        Raises:
            HierarchyError: The caller handed no Tasks file.

        """
        if self.tasks is None:
            msg: str = f"no Tasks file was handed for story:{self.slug}"
            raise HierarchyError(msg)
        return self.tasks


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class SpanStories:
    """The Stories of an Epic's span, in span order, and the mapper's edges file when there is one.

    The Story at index i is named ``S<i+1>`` in an edge between Stories.
    """

    scope: SpanFiles
    stories: tuple[StoryFiles, ...]
    task_deps: Path | None = None


def recorded_path(path: Path, root: Path | None) -> str | None:
    """Return a file's path as a bead records it: relative to the project root.

    Args:
        path: The file.
        root: The project root, or None.

    Returns:
        The relative path, or None when there is no root or the file is not under it.

    """
    if root is None:
        return None
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return None


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
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or _FALLBACK_ARTIFACT_SLUG


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


def _content_sha(path: Path) -> str:
    """Return the SHA-256 of a saved file's bytes, as a bead records it.

    Args:
        path: The file.

    Returns:
        The digest.

    Raises:
        HierarchyError: The file cannot be read.

    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        msg: str = f"{path.name} could not be read: {exc}"
        raise HierarchyError(msg) from exc


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
    matrix_elements: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    """Each event the Task cites, as :func:`event_text` renders it."""
    infrastructure: bool = False
    """Whether the Task is infrastructure work: its stated type is in the infrastructure vocabulary,
    or it builds a piece of infrastructure. Its bead is labelled so the build adds Infra Intent."""

    def __post_init__(self) -> None:
        """Validate every constructor field, including all collection entries."""
        check_type(self.matrix_elements, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.events, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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
def read_story(files: StoryFiles, root: Path | None) -> Story:
    """Return the Story a repository's saved Story document carries.

    Args:
        files: The repository's saved files.
        root: The project root the spec documents and the Story document are recorded
            relative to, or None to record none of them.

    Returns:
        The Story, with the metadata it is written with: for the Story document and each spec
        document under the root, its path and the SHA-256 of its bytes.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    kind: ArtifactKind
    path: Path
    if not (isinstance(files, StoryFiles)) or not (isinstance(root, Path) or root is None):
        raise TypeError(_ARGUMENT_ERROR)
    repo: str = files.repo
    slug: str = files.slug
    saved: dict[str, contracts.JsonValue] = _read_json(files.story)
    metadata: dict[str, str] = {KEY_ELAB_KEY: f"story:{slug}", KEY_REPO_PATH: repo}
    decisions: list[str] = list(dict.fromkeys(_loose_list(saved.get(ARG_DECISION_IDS))))
    if decisions:
        metadata[KEY_DECISION_IDS] = json.dumps(
            decisions,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    entries: list[tuple[ArtifactKind, Path]] = [
        *zip(SPEC_ASPECT_KIND.values(), files.specs, strict=False),
        ("story", files.story),
    ]
    for kind, path in entries:
        named: str | None = recorded_path(path, root)
        if named is None:
            continue
        metadata[artifact_key(kind, "path")] = named
        metadata[artifact_key(kind, "sha256")] = _content_sha(path)
    criteria: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = saved.get(
        ARG_ACCEPTANCE_CRITERIA,
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
    artifact: UiArtifact | None = None

    def __post_init__(self) -> None:
        """Validate every constructor field, including all collection entries."""
        check_type(self.source, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.bundle, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.cites, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.artifact, UiArtifact | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _supplied_bundle(entry: UiItem, named: UiArtifact | None, warn: str) -> UiDesign | None:
    """Return the design of a `bundle` ui item built from its supplied bundle, or None.

    Args:
        entry: The detailing's `uiItems` entry, validated against the recon contract.
        named: The artifact the entry names, or None.
        warn: The prefix a warning about the entry carries.

    Returns:
        The design, or None (with a warning) when the bundle or build spec cannot be built from.

    """
    bundle: str = entry.get(KEY_BUNDLE) or ""
    spec: str = entry.get(KEY_BUILD_SPEC) or ""
    problem: str | None = bundle_problem(bundle, spec)
    root: Path = Path(bundle).resolve()
    held: beadcontracts.Bundle | None = None if problem else read_bundle(root)
    if held is None:
        _WARNINGS.append(f"{warn}: {problem or 'unreadable'}; taken as {DESIGN_SOURCE_CDS}")
        return None
    resolved: str = str(Path(spec).resolve())
    sections: list[str] = entry.get(KEY_SECTIONS, [])
    kind: UiArtifactKind | None = artifact_kind(held["kind"])
    packaged: UiArtifact | None = {KEY_KIND: kind, KEY_SLUG: held["slug"]} if kind is not None else named
    return UiDesign(
        DESIGN_SOURCE_BUNDLE,
        str(root),
        [f"{resolved}#{x}" for x in sections] if sections else [resolved],
        packaged,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def ui_authority(
    detailing_file: Path | None,
    packages_dir: str | None = None,
) -> dict[str, UiDesign]:
    """Return the design source of each `ui` delta item the detailing resolved.

    Reads `uiAuthority.uiItems` of the repository's saved detailing,
    validated against the artifact-handoff recon contract. Each item takes `bundle` (a cds
    bundle the owner supplied packages it), `cds` (it changes design and is designed with the
    CDS design system) or `none` (it changes no design). A `bundle` item whose bundle or build
    spec cannot be built from is `cds`; a `cds` item with no artifact gets the contract's
    default artifact kind named for the item. Each is noted in `take_warnings`.

    Args:
        detailing_file: The repository's detailing file, or None when none was written.
        packages_dir: The packages directory a cited bundle must sit in, or None.

    Returns:
        Per delta item id its design: the source, and for a `bundle` item the bundle path
        and its build-spec citations (the absolute `build-spec.md` path, followed by
        `#<Section ID>` for each Section it builds). No detailing yields no designs.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(detailing_file, Path) or detailing_file is None) or not (
        isinstance(packages_dir, str) or packages_dir is None
    ):
        raise TypeError(_ARGUMENT_ERROR)
    del packages_dir
    if detailing_file is None:
        return {}
    name: str = detailing_file.name
    detailing: ReconDetailing = read_detailing(detailing_file)
    authority: UiAuthority | None = detailing.get(KEY_UI_AUTHORITY)
    designs: dict[str, UiDesign] = {}
    for entry in authority[KEY_UI_ITEMS] if authority is not None else []:
        item: str = entry[KEY_ITEM]
        if item in designs:
            continue
        source: DesignSource = entry[KEY_DESIGN_SOURCE]
        if source == DESIGN_SOURCE_NONE:
            designs[item] = UiDesign(source)
            continue
        named: UiArtifact | None = entry.get(KEY_ARTIFACT)
        if source == DESIGN_SOURCE_BUNDLE:
            supplied: UiDesign | None = _supplied_bundle(entry, named, f"{name}: ui item {item}")
            if supplied is not None:
                designs[item] = supplied
                continue
        artifact: UiArtifact = (
            named if named is not None else {KEY_KIND: DEFAULT_ARTIFACT_KIND, KEY_SLUG: _artifact_slug(item)}
        )
        if named is None:
            _WARNINGS.append(
                f"{name}: {DESIGN_SOURCE_CDS} ui item {item} names no artifact; "
                f"taken as {artifact[KEY_KIND]} {artifact[KEY_SLUG]}",
            )
        designs[item] = UiDesign(DESIGN_SOURCE_CDS, artifact=artifact)
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
    if CDS_DESIGN_SOURCE_BUNDLE in sources:
        return CDS_DESIGN_SOURCE_BUNDLE, bundles, cites, artifacts
    if CDS_DESIGN_SOURCE_CDS in sources or not cited:
        return CDS_DESIGN_SOURCE_CDS, [], [], artifacts
    return CDS_DESIGN_SOURCE_NONE, [], [], []


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
        if t.cds_design_source != CDS_DESIGN_SOURCE_BUNDLE:
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


def _spec_refs(files: StoryFiles, root: Path | None) -> list[str]:
    """Return the Story's spec documents a Task may cite, relative to the project root.

    Args:
        files: The repository's saved files.
        root: The project root, or None.

    Returns:
        The references; none without a root.

    """
    return [named for path in files.specs if (named := recorded_path(path, root)) is not None]


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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def stated_ids(matrix: Matrix, built: Sequence[str]) -> list[str]:
    """Return the matrix ids a Task states for what it builds: its stack, the entries, the capabilities.

    A Task states in full what it builds in the matrix's ids. The stack is a built id that is a
    stack, or the stack that holds a built entry. The shared capabilities are the features the
    work that builds those entries must use (`matrixtraverse.capabilities`). An id the matrix
    holds no entry for is kept as stated and adds no stack and no capability.

    Args:
        matrix: The matrix.
        built: The ids of the entries the Task builds.

    Returns:
        The stack ids, then the built ids, then the capability ids, each once, in that order.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(matrix, Matrix) or isinstance(built, (str, bytes)):
        raise TypeError(_ARGUMENT_ERROR)
    stacks: list[str] = []
    known: list[EntryId] = []
    stated: str
    for stated in built:
        entry: Entry | None = matrix.find(EntryId(stated))
        if entry is None:
            continue
        known.append(entry.id)
        home: EntryId | None = entry.id if entry.kind == KIND_STACK else matrix.home(entry.id, side=None)
        if home is not None:
            stacks.append(home)
    shared: list[str] = [reach.feature for reach in capabilities(matrix, known)]
    return list(dict.fromkeys([*stacks, *built, *shared]))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def publisher_names(published_by: Sequence[str], names: Mapping[str, str]) -> list[str]:
    """Name the publishers of an event as a line about it shows them.

    Args:
        published_by: The event item's ``publishedBy``: item ids of what the Epic builds, or
            matrix ids.
        names: The name of each item id that can be named.

    Returns:
        Each publisher as ``<name> (<item id>)`` when it is an item that can be named, otherwise
        its id as given, in order.

    """
    return [f"{names[publisher]} ({publisher})" if publisher in names else publisher for publisher in published_by]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def event_text(item_id: str, name: str, publishers: Sequence[str], description: str) -> str:
    """Render one event a Story or a Task builds: the fact, who publishes it and what it is.

    Args:
        item_id: The event's item id.
        name: The event's name.
        publishers: Its publishers, as :func:`publisher_names` names them; may be empty.
        description: The event's description, the purpose the matrix gives it.

    Returns:
        ``<item id>: <name>, published by <publishers>: <description>``, or
        ``<item id>: <name>: <description>`` when it names no publisher.

    Raises:
        ValueError: The event's description is empty.

    """
    stated: str = description.strip()
    if not stated:
        message: str = f"the event {item_id} ({name}) has no description"
        raise ValueError(message)
    if not publishers:
        return f"{item_id}: {name}: {stated}"
    return f"{item_id}: {name}, published by {', '.join(publishers)}: {stated}"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def event_lines(items: Mapping[str, StoryBuild]) -> dict[str, str]:
    """Render each event among what the Epic's Stories build.

    An event that names no trigger raises ``ValueError`` from :func:`event_text`.

    Args:
        items: What every Story of the Epic builds, by item id.

    Returns:
        Each event's item id with its line (:func:`event_text`); an item that carries no
        ``trigger`` is not an event and has none.

    """
    names: dict[str, str] = {key: item["element"] for key, item in items.items()}
    return {
        key: event_text(key, item["element"], publisher_names(item.get("publishedBy", []), names), item["trigger"])
        for key, item in items.items()
        if "trigger" in item
    }


@dataclass(frozen=True)
class _TaskSources:
    options: ReadTaskOptions
    refs: list[str]
    strategy: JsonObject | None
    edges: list[tuple[str, str]]
    scores: dict[str, JsonObject]
    designs: dict[str, UiDesign]
    elements: dict[str, str]
    matrix: Matrix | None
    """The matrix, read when a Task builds an entry of it; None when nothing the Story builds names one."""
    events: dict[str, str]
    """The line of each event the Epic's Stories build, by item id (:func:`event_lines`)."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_tasks(files: StoryFiles, root: Path | None, options: ReadTaskOptions) -> list[Task]:
    """Return the Tasks a Story's saved Tasks file carries, in build order.

    Args:
        files: The repository's saved files.
        root: The project root spec references are recorded relative to, or None.
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
        not (isinstance(files, StoryFiles))
        or not (isinstance(root, Path) or root is None)
        or not (isinstance(options, ReadTaskOptions))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    saved: dict[str, contracts.JsonValue] = _read_json(files.tasks_file)
    if not isinstance(saved.get("tasks"), list):
        msg: str = f"{files.tasks_file.name} holds no `tasks` list"
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
    _WARNINGS.extend(f"tasks-{options.slug}.json: the edge {frm} -> {to} closes a cycle; dropped" for frm, to in left)
    order: list[str] | None = build_order(nodes, edges)
    if order is None:
        message: str = "Task edges remain cyclic after normalization"
        raise HierarchyError(message)
    every_build: dict[str, StoryBuild] = story_builds(files.scope)
    elements: dict[str, str] = {
        key: item["matrixId"]
        for key, item in every_build.items()
        if "matrixId" in item and item["slug"] == options.slug
    }
    sources: _TaskSources = _TaskSources(
        options,
        _spec_refs(files, root),
        json_object(saved[ARG_TEST_STRATEGY]) if isinstance(saved.get(ARG_TEST_STRATEGY), dict) else None,
        edges,
        scores,
        ui_authority(files.detailing, options.packages_dir)
        if any(UI_SURFACE in (_surfaces(t.get(ARG_SURFACES)) or []) for t in unique)
        else {},
        elements,
        read_matrix(matrix_path(None, os.environ)) if elements else None,
        event_lines(every_build),
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
    kind: str

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
        if (self.reuses is not None and not isinstance(self.reuses, str)) or not isinstance(self.kind, str):
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
        value.get(ARG_ACCEPTANCE_CRITERIA) or [],
        list[JsonValue],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    surfaces: list[str] | None = _surfaces(value.get(ARG_SURFACES))
    reuses: JsonValue = value.get("reuses")
    return _TaskDocument(
        title=title,
        description=description,
        acceptance=tuple(ac_text(item) for item in criteria if ac_text(item)),
        definition_of_done=_task_strings(value.get(ARG_DEFINITION_OF_DONE)),
        spec_paths=_task_strings(value.get(ARG_SPEC_PATHS)),
        spec_sections=_task_strings(value.get(ARG_SPEC_SECTIONS)),
        requirement_ids=_task_strings(value.get(ARG_REQUIREMENT_IDS)),
        decision_ids=_task_strings(value.get(ARG_DECISION_IDS)),
        surfaces=tuple(surfaces) if surfaces is not None else None,
        reuses=check_type(reuses, str).strip() or None if reuses is not None else None,
        blocked_by_external=_task_strings(value.get("blockedByExternal")),
        kind=check_type(value.get("type") or "", str).strip().casefold(),
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
    built: list[str] = list(
        dict.fromkeys(sources.elements[item] for item in t.requirement_ids if item in sources.elements),
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
        matrix_elements=stated_ids(sources.matrix, built) if sources.matrix is not None else built,
        events=list(dict.fromkeys(sources.events[item] for item in t.requirement_ids if item in sources.events)),
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
        infrastructure=t.kind in INFRA_TYPES
        or any(kind_of(as_entry_id(entry)) == KIND_INFRASTRUCTURE for entry in built),
    )


def _task_label(task: JsonObject) -> str:
    """Name a Task of a Tasks file in a sentence.

    Returns:
        Its key, or its title when it states no key.

    """
    return str(task.get("key") or task.get("title") or "")


def _cited(task: JsonObject, items: Mapping[str, EntryId]) -> list[str]:
    """List the things a Story builds that one Task cites.

    Returns:
        The item ids among the Task's ``requirementIds``, in its order.

    """
    stated: JsonValue = task.get("requirementIds") or []
    return [cited for cited in stated if isinstance(cited, str) and cited in items] if isinstance(stated, list) else []


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_grouping_problems(items: Sequence[JsonValue], tasks: Sequence[JsonValue]) -> list[str]:
    """Check that a Story's Tasks group what it builds into coherent units of build work.

    Args:
        items: The items of what the Story builds, each with its ``id`` and ``matrixId``.
        tasks: The Tasks of the decomposer's Tasks file.

    Returns:
        One sentence per Task that covers one thing when the Story builds two or more. Empty
        when the Tasks group what the Story builds.

    """
    by_id: dict[str, EntryId] = {
        str(json_object(item)["id"]): EntryId(str(json_object(item).get("matrixId", ""))) for item in items
    }
    shaped: list[JsonObject] = [json_object(task) for task in tasks]
    return [
        f"Task {_task_label(task)} covers one thing: group the things this Story builds into coherent Tasks"
        for task in shaped
        if len(by_id) > 1 and len(_cited(task, by_id)) == 1
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def work_items(files: StoryFiles) -> list[str]:
    """Everything the Story builds is work; no built-state judgment.

    Returns:
        The ids of the items the span places in the Story's repository.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(files, StoryFiles)):
        raise TypeError(_ARGUMENT_ERROR)
    return [key for key, item in story_builds(files.scope).items() if item["slug"] == files.slug]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def uncited_work(files: StoryFiles, tasks: list[Task]) -> list[str]:
    """Return the work items of a repository that no Task cites in its `requirementIds`.

    Args:
        files: The repository's saved files.
        tasks: The Story's Tasks.

    Returns:
        The ids of what the Story builds that no Task cites, in the span's order; empty when
        every one is cited or there is none.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(files, StoryFiles)) or not (isinstance(tasks, list)):
        raise TypeError(_ARGUMENT_ERROR)
    cited: set[str] = {r for t in tasks for r in t.requirement_ids}
    return [i for i in work_items(files) if i not in cited]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def item_briefs(files: StoryFiles, ids: list[str]) -> list[StoryBuild]:
    """Return architecture facts for the precise uncited items.

    Returns:
        What the Story of the repository builds among ``ids``, in that order.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(files, StoryFiles)) or not (isinstance(ids, list)):
        raise TypeError(_ARGUMENT_ERROR)
    items: dict[str, beadcontracts.StoryBuild] = story_builds(files.scope)
    return [items[key] for key in ids if key in items and items[key]["slug"] == files.slug]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_detailed_work(files: StoryFiles, tasks: list[Task]) -> None:
    """Warn when a Task cites nothing the Story builds; never classify existing code.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(files, StoryFiles)) or not (isinstance(tasks, list)):
        raise TypeError(_ARGUMENT_ERROR)
    work: set[str] = set(work_items(files))
    idle: list[str] = [t.key for t in tasks if not work.intersection(t.requirement_ids)]
    if idle:
        _WARNINGS.append(
            f"{files.tasks_file.name}: {', '.join(idle)} cite nothing the Story builds in requirementIds "
            f"({', '.join(sorted(work)) or 'none here'})",
        )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def delta_requires(elements: Path) -> dict[str, list[str]] | None:
    """Return each item's `requires`, from the span's elements file.

    The span step writes `requires` from the `dependsOn` links between the elements in the matrix.

    Args:
        elements: The elements file.

    Returns:
        Item id -> the ids it needs built first; None when no item carries `requires`.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(elements, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    items: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = _read_json(
        elements,
    ).get("items")
    if not isinstance(items, list) or not any(isinstance(i, dict) and "requires" in i for i in items):
        return None
    return {str(i.get("id")): str_list(i.get("requires")) for i in items if isinstance(i, dict) and i.get("id")}


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
def derive_prerequisites(files: StoryFiles, tasks: list[Task]) -> list[Task]:
    """Derive in-Story prerequisite edges from what the Story builds.

    Missing builders remain coverage findings. Cross-repository prerequisites are
    connected by closure_task_edges after every repository's Tasks exist.
    Cyclic derived edges are dropped and reported as normalization warnings.

    Returns:
        The Tasks in build order, each with the prerequisites derived for it.

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
    if not (isinstance(files, StoryFiles)) or not (isinstance(tasks, list)):
        raise TypeError(_ARGUMENT_ERROR)
    slug: str = files.slug
    requires: dict[str, list[str]] | None = delta_requires(files.scope.elements)
    if requires is None:
        return tasks
    detailed: dict[str, beadcontracts.StoryBuild] = story_builds(files.scope)
    builders: dict[str, list[str]] = _task_builders(tasks)
    problems: list[str] = []
    saved_edges: list[tuple[str, str]] = [(d, t.key) for t in tasks for d in t.depends_on]
    for t in tasks:
        for x in t.requirement_ids:
            own: beadcontracts.StoryBuild | None = detailed.get(x)
            if own is None or own["slug"] != slug:
                continue
            for y in requires.get(x, []):
                d: beadcontracts.StoryBuild | None = detailed.get(y)
                if d is None or y in t.requirement_ids or d["slug"] != slug:
                    continue
                found: list[str] = [k for k in builders.get(y, []) if k != t.key]
                if not found:
                    problems.append(
                        f"{t.key} builds {x}, which requires {y}; no Task of this Story builds it",
                    )
                t.depends_on.extend(k for k in found if k not in t.depends_on)
    _WARNINGS.extend(f"{files.tasks_file.name}: {p}" for p in problems)
    by_key: dict[str, Task] = {t.key: t for t in tasks}
    nodes: list[str] = [t.key for t in tasks]
    derived: list[tuple[str, str]] = [
        (d, t.key) for t in tasks for d in t.depends_on if (d, t.key) not in set(saved_edges)
    ]
    _taken, left = _acyclic(nodes, saved_edges, derived)
    for frm, to in left:
        by_key[to].depends_on.remove(frm)
        _WARNINGS.append(
            f"{files.tasks_file.name}: the derived edge {frm} -> {to} closes a cycle; dropped",
        )
    return _ordered_tasks(nodes, tasks, by_key)


def _ordered_tasks(nodes: list[str], tasks: list[Task], by_key: dict[str, Task]) -> list[Task]:
    order: list[str] | None = build_order(nodes, [(d, t.key) for t in tasks for d in t.depends_on])
    if order is None:
        message: str = "Task prerequisite graph remains cyclic"
        raise HierarchyError(message)
    return [by_key[k] for k in order]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_task_deps(path: Path) -> list[TaskEdge]:
    """Return the saved Task edges between Stories.

    Args:
        path: The mapper's edges file.

    Returns:
        The edges as saved (`from`, `to`, `kind`, `reason`; ends are
        `S<i>-<local key>`).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(path, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    saved: dict[str, contracts.JsonValue] = _read_json(path)
    return check_type(
        saved.get("edges") or [],
        list[TaskEdge],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_builds(scope: SpanFiles) -> dict[str, StoryBuild]:
    """List what each Story of the Epic builds: the span's items joined to the repository whose Story builds each.

    Returns:
        Item id -> the item with the slug and the path of the repository whose Story builds it.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(scope, SpanFiles)):
        raise TypeError(_ARGUMENT_ERROR)
    placements: list[contracts.JsonObject] = check_type(
        _read_json(scope.span)["placements"],
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    repos: list[str] = list(dict.fromkeys(check_type(p["repoPath"], str) for p in placements))
    slugs: dict[str, str] = repo_slugs(repos)
    items: dict[str, contracts.DeltaItem] = {
        check_type(i["id"], str): i
        for i in check_type(
            _read_json(scope.elements)["items"],
            list[DeltaItem],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    }
    return {
        item: {**items[item], "slug": slugs[check_type(p["repoPath"], str)], "repoPath": check_type(p["repoPath"], str)}
        for p in placements
        for item in check_type(p["itemIds"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    }
