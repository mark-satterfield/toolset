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
import heapq
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
    KEY_UI_ITEMS,
    DesignSource,
    UiArtifact,
    UiAuthority,
    UiItem,
    violations,
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
from matrix_contract import (
    AUTHORITY_SIDE,
    FAMILY_DEPENDENCY,
    KIND_INFRASTRUCTURE,
    KIND_STACK,
    NO_BUILD_ORDER_KINDS,
    Entry,
    EntryId,
    family_kinds,
)
from matrixstore import Matrix, as_entry_id, kind_of, matrix_path, shared_matrix
from matrixtraverse import authority_holder, build_home, capabilities

#: The surfaces a Task may declare; anything else is dropped.
_ARGUMENT_ERROR: str = "Arguments violate the hierarchy input contract"
STATE_VERIFIED: Final = "built"
"""The ``state`` (target-report.schema.json ElementState) of a span item whose entry carries the
verified flag: built and tested as the matrix records it."""


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

#: The bead build-contract design source each UI sources design source maps to.
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
    the Tasks file, once the Story is decomposed. ``ui_sources`` is the repository's UI sources
    file (``spec-<slug>.ui.json``, ``spec-ui.schema.json``), when its Story builds UI items.
    """

    slug: str
    repo: str
    scope: SpanFiles
    story: Path
    specs: tuple[Path, ...] = ()
    tasks: Path | None = None
    ui_sources: Path | None = None

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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def note_warnings(warnings: Sequence[str]) -> None:
    """Hold normalizations again, so the next `take_warnings` returns them.

    A caller that reuses Tasks it read earlier hands back what that read normalized.

    Args:
        warnings: One line per normalization, in order.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if isinstance(warnings, str):
        raise TypeError(_ARGUMENT_ERROR)
    _WARNINGS.extend(warnings)


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
    """Return a kebab-case slug of a name, for an artifact a UI sources file named no slug for.

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


def _names_supplied_bundle(sources: Path) -> bool:
    """Report whether a UI sources file takes any ui item from a supplied cds bundle.

    Returns:
        True when an entry of its ``uiItems`` has the ``bundle`` design source, or when the file
        cannot be read, so a caller never keys on what it could not read.

    """
    try:
        held: object = json.loads(sources.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return True
    entries: object = held.get(KEY_UI_ITEMS) if isinstance(held, dict) else None
    listed: list[object] = entries if isinstance(entries, list) else []
    return any(isinstance(entry, dict) and entry.get(KEY_DESIGN_SOURCE) == DESIGN_SOURCE_BUNDLE for entry in listed)


def _file_part(path: Path) -> bytes:
    """Render one input file as part of a digest.

    Returns:
        Its path and bytes; its path and a missing marker when it cannot be read.

    """
    try:
        body: bytes = path.read_bytes()
    except OSError:
        body = b"\0missing"
    return f"{path}\0{len(body)}\0".encode() + body


def _matrix_part() -> bytes:
    """Render the matrix file the Tasks read their matrix ids from as part of a digest.

    Returns:
        Its path and its stat identity (inode, size, modification time); a missing marker when it
        does not exist. The matrix is replaced whole on every write, so this identity changes
        whenever its content does.

    """
    path: Path = matrix_path(None, os.environ)
    try:
        state: os.stat_result = path.stat()
    except OSError:
        return f"{path}\0missing".encode()
    return f"{path}\0{state.st_ino}\0{state.st_size}\0{state.st_mtime_ns}\0{state.st_ctime_ns}".encode()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def plan_inputs_digest(files: StoryFiles, root: Path | None, packages_dir: str | None) -> str | None:
    """Fingerprint everything reading a Story's planned Tasks depends on.

    The Story document, the spec documents, the Tasks file, the UI sources file, the span's two
    files, the matrix file, the repository and the arguments. Equal digests mean reading the
    Tasks again gives the same Tasks and the same normalizations.

    Args:
        files: The repository's saved files.
        root: The project root spec references are recorded relative to, or None.
        packages_dir: The packages directory a cited cds bundle must sit in, or None.

    Returns:
        The SHA-256 digest; None when the UI sources file takes an item from a supplied cds
        bundle, whose bundle directories and packages directory are read and not fingerprinted.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not isinstance(files, StoryFiles)
        or not (isinstance(root, Path) or root is None)
        or not (isinstance(packages_dir, str) or packages_dir is None)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    if files.ui_sources is not None and _names_supplied_bundle(files.ui_sources):
        return None
    paths: list[Path] = [
        files.story,
        *files.specs,
        *(path for path in (files.tasks, files.ui_sources) if path is not None),
        files.scope.span,
        files.scope.elements,
    ]
    digest = hashlib.sha256(f"{files.slug}\0{files.repo}\0{root}\0{packages_dir}\0".encode())
    digest.update(_matrix_part())
    for path in paths:
        digest.update(_file_part(path))
    return digest.hexdigest()


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
    build_prerequisites: JsonObject = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    """Each event the Task cites, as :func:`event_text` renders it."""
    infrastructure: bool = False
    """Whether the Task is infrastructure work: its stated type is in the infrastructure vocabulary,
    or it builds a piece of infrastructure. Its bead is labelled so the build adds Infra Intent."""

    def __post_init__(self) -> None:
        """Validate every constructor field, including all collection entries."""
        check_type(self.matrix_elements, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.build_prerequisites, JsonObject, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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
    ready: list[tuple[int, str]] = [(rank[k], k) for k in keys if indegree[k] == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        key: str = heapq.heappop(ready)[1]
        order.append(key)
        for nxt in out[key]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready, (rank[nxt], nxt))
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
    seen: set[tuple[str, str]] = set()
    for e in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(e, dict):
            continue
        for frm in expand(e.get("from")):
            for to in expand(e.get("to")):
                pair: tuple[str, str] = (frm, to)
                if frm in known and to in known and frm != to and pair not in seen:
                    seen.add(pair)
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
    """The design source one `ui` delta item takes, as the UI sources file records it."""

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
        entry: The UI sources file's `uiItems` entry, validated against the recon contract.
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


def _read_ui_sources(path: Path) -> UiAuthority:
    """Read a repository's UI sources file as the design source of each UI item.

    Args:
        path: The UI sources file (``spec-<slug>.ui.json``).

    Returns:
        Its ``uiItems`` and ``mocksDir``, validated against the recon contract's ``UiAuthority``.

    Raises:
        HierarchyError: The file cannot be read, or its UI items violate the contract.

    """
    held: JsonObject = _read_json(path)
    authority: JsonObject = {KEY_UI_ITEMS: held.get(KEY_UI_ITEMS, []), "mocksDir": held.get("mocksDir")}
    problems: list[str] = violations(authority, "UiAuthority")
    if problems:
        msg: str = f"{path.name} violates the recon contract's UiAuthority: {'; '.join(problems)}"
        raise HierarchyError(msg)
    return check_type(authority, UiAuthority, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def ui_authority(
    sources_file: Path | None,
    packages_dir: str | None = None,
) -> dict[str, UiDesign]:
    """Return the design source of each `ui` delta item the repository's UI sources file records.

    Reads the `uiItems` of the UI sources file the ui-design-source-selector's choices were
    normalized into, validated against the artifact-handoff recon contract. Each item takes
    `bundle` (a cds bundle the owner supplied packages it), `cds` (it changes design and is
    designed with the CDS design system) or `none` (it changes no design). A `bundle` item whose
    bundle or build spec cannot be built from is `cds`; a `cds` item with no artifact gets the
    contract's default artifact kind named for the item. Each is noted in `take_warnings`.

    Args:
        sources_file: The repository's UI sources file, or None when none was written.
        packages_dir: The packages directory a cited bundle must sit in, or None.

    Returns:
        Per delta item id its design: the source, and for a `bundle` item the bundle path
        and its build-spec citations (the absolute `build-spec.md` path, followed by
        `#<Section ID>` for each Section it builds). No UI sources file yields no designs.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(sources_file, Path) or sources_file is None) or not (
        isinstance(packages_dir, str) or packages_dir is None
    ):
        raise TypeError(_ARGUMENT_ERROR)
    del packages_dir
    if sources_file is None:
        return {}
    name: str = sources_file.name
    authority: UiAuthority = _read_ui_sources(sources_file)
    designs: dict[str, UiDesign] = {}
    for entry in authority[KEY_UI_ITEMS]:
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
    matrix guesses the work that builds those entries relies on (`matrixtraverse.capabilities`).
    An id the matrix holds no entry for is kept as stated and adds no stack and no capability.

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
        ui_authority(files.ui_sources, options.packages_dir)
        if any(UI_SURFACE in (_surfaces(t.get(ARG_SURFACES)) or []) for t in unique)
        else {},
        elements,
        shared_matrix(matrix_path(None, os.environ)) if elements else None,
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
    build_prerequisites: JsonObject
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
        build_prerequisites=check_type(value.get("buildPrerequisites") or {}, dict[str, JsonValue]),
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
        build_prerequisites=t.build_prerequisites,
        events=list(dict.fromkeys(sources.events[item] for item in t.requirement_ids if item in sources.events)),
        decision_ids=list(t.decision_ids) or list(sources.options.story_decision_ids),
        surfaces=surfaces,
        test_strategy=sources.strategy,
        depends_on=[frm for frm, to in sources.edges if to == key],
        sizes=size_metadata(sources.scores.get(key)),
        verified="true",
        reuses=t.reuses,
        blocked_by_external=list(
            dict.fromkeys([
                *t.blocked_by_external,
                *(
                    check_type(row["task"], str)
                    for row in check_type(t.build_prerequisites.get("producers", []), list[dict[str, JsonValue]])
                ),
            ]),
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


def _build_dependencies(items: Sequence[JsonValue]) -> list[tuple[str, str]]:
    """List which unverified thing of a Story must be built before which.

    The architecture side makes one thing need another built first (``requires`` and
    ``requiredBy`` of the repository context's items), when the matrix states a relationship
    between them that orders a build, or none (:func:`build_relations`): a call holds only at run
    time. A thing the span marks verified (``state`` :data:`STATE_VERIFIED`) is not work, so no
    dependency on it counts.

    Returns:
        (prerequisite item id, dependent item id) pairs between unverified items, without repeats.

    """
    shaped: dict[str, JsonObject] = {str(json_object(item)["id"]): json_object(item) for item in items}
    work: set[str] = {key for key, item in shaped.items() if item.get("state") != STATE_VERIFIED}
    pairs: list[tuple[str, str]] = [
        pair
        for key, item in shaped.items()
        for pair in (
            *((needed, key) for needed in str_list(item.get("requires"))),
            *((key, needing) for needing in str_list(item.get("requiredBy"))),
        )
    ]
    coupled: list[tuple[str, str]] = list(
        dict.fromkeys((first, then) for first, then in pairs if first in work and then in work and first != then),
    )
    if not coupled:
        return []
    matrix: Matrix = shared_matrix(matrix_path(None, os.environ))
    return [(first, then) for first, then in coupled if _orders_build(matrix, shaped[then], shaped[first])]


def _declared_edges(edges: Sequence[JsonValue]) -> list[tuple[str, str]]:
    """Read the Task edges a Tasks file declares.

    Returns:
        (prerequisite key, dependent key) for each edge that names both as strings.

    """
    shaped: list[JsonObject] = [json_object(edge) for edge in edges if isinstance(edge, dict)]
    return [
        (str(edge["from"]), str(edge["to"]))
        for edge in shaped
        if isinstance(edge.get("from"), str) and isinstance(edge.get("to"), str)
    ]


def _reachable(start: str, links: Mapping[str, set[str]]) -> set[str]:
    """Collect every Task a Task's work leads to through the Task order.

    Returns:
        The labels reachable from ``start`` by one or more links; ``start`` itself only on a cycle.

    """
    found: set[str] = set()
    pending: list[str] = list(links.get(start, ()))
    while pending:
        label: str = pending.pop()
        if label in found:
            continue
        found.add(label)
        pending.extend(links.get(label, ()))
    return found


def _ordering_cycles(labels: Sequence[str], links: Mapping[str, set[str]]) -> list[list[str]]:
    """Find the groups of Tasks that each need another of the group built first.

    Returns:
        Each group of two or more Tasks on one ordering cycle, in Tasks-file order, first seen first.

    """
    reach: dict[str, set[str]] = {label: _reachable(label, links) for label in labels}
    groups: dict[tuple[str, ...], None] = dict.fromkeys(
        tuple(other for other in labels if other in reach[label] and label in reach[other])
        for label in labels
        if label in reach[label]
    )
    return [list(group) for group in groups if len(group) > 1]


def task_grouping_problems(
    items: Sequence[JsonValue],
    tasks: Sequence[JsonValue],
    edges: Sequence[JsonValue] = (),
) -> list[str]:
    """Check that a Story's Tasks group what it builds into coherent units of build work.

    Coupled things of a Story (one ``requires`` the other, or is ``requiredBy`` it, by a
    relationship that orders a build) may be built in different Tasks when the Task order carries
    the coupling: the Task that builds the prerequisite comes first. A coupling binds Tasks only
    when one Task builds each of the two things; when several Tasks cite either, which of them
    consumes or provides it is the decomposer's judgment, carried by its declared edges. The grouping is
    incoherent when the couplings and the declared edges
    make Tasks need each other built first, because no build order exists between them; those
    Tasks' coupled things belong in one Task. How many things a Task cites is not judged.

    Args:
        items: The items of what the Story builds, each with its ``id`` and ``matrixId``, and the
            ``requires`` and ``requiredBy`` that couple it to the Story's other items.
        tasks: The Tasks of the decomposer's Tasks file.
        edges: The Tasks file's ``edges``, prerequisite ``from`` to dependent ``to`` by Task key.

    Returns:
        One sentence per group of Tasks that need each other built first, naming the coupled
        things to build together. Empty when the Tasks group what the Story builds.

    """
    by_id: dict[str, EntryId] = {
        str(json_object(item)["id"]): EntryId(str(json_object(item).get("matrixId", ""))) for item in items
    }
    shaped: list[JsonObject] = [json_object(task) for task in tasks]
    labels: list[str] = list(dict.fromkeys(_task_label(task) for task in shaped))
    builders: dict[str, list[str]] = {}
    for cited, label in [(cited, _task_label(task)) for task in shaped for cited in _cited(task, by_id)]:
        builders.setdefault(cited, []).append(label)
    sole: dict[str, str] = {cited: labels[0] for cited, labels in builders.items() if len(labels) == 1}
    crossing: list[tuple[str, str, str, str]] = [
        (first, then, sole[first], sole[then])
        for first, then in _build_dependencies(items)
        if first in sole and then in sole and sole[first] != sole[then]
    ]
    links: dict[str, set[str]] = {}
    for before, after in [*((before, after) for _f, _t, before, after in crossing), *_declared_edges(edges)]:
        links.setdefault(before, set()).add(after)
    return [
        f"Tasks {', '.join(group)} each need another of them built first, so no build order exists: "
        f"build {', '.join(_coupled_in(group, crossing))} together in one Task"
        for group in _ordering_cycles(labels, links)
    ]


def _coupled_in(group: Sequence[str], crossing: Sequence[tuple[str, str, str, str]]) -> list[str]:
    """Name the coupled things split across the Tasks of one ordering cycle.

    Returns:
        The item ids of the couplings that run between two Tasks of ``group``, sorted.

    """
    members: set[str] = set(group)
    return sorted({
        item
        for first, then, before, after in crossing
        if before in members and after in members
        for item in (first, then)
    })


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def work_items(files: StoryFiles) -> list[str]:
    """Name the work of a Story: what it builds that is not verified.

    An item the span marks verified (``state``, :data:`STATE_VERIFIED`) is built and tested as
    the matrix records it, so it is not work: no Task has to cite it.

    Returns:
        The ids of the items the span places in the Story's repository, less the verified ones.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(files, StoryFiles)):
        raise TypeError(_ARGUMENT_ERROR)
    return [
        key
        for key, item in story_builds(files.scope).items()
        if item["slug"] == files.slug and item.get("state") != STATE_VERIFIED
    ]


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


def _stated_needs(matrix: Matrix, start: str, end: str) -> tuple[frozenset[str], EntryId | None]:
    """Read the dependency relationships the architecture side states from one item's entry to another's.

    A relationship that ends at the other entry itself is stated directly. When there is none, a
    relationship that ends at the stack the other entry is homed in, or at a layer or package homed
    in that stack (:func:`matrixtraverse.build_home`), such as an ``imports`` of a library's stack
    through its package, is stated through that stack; never when it is the first entry's own stack.

    Returns:
        The kinds of the relationships found, and the stack they were found through (None when
        they end at the other entry itself or none is found).

    """
    start_id: EntryId = as_entry_id(start)
    end_id: EntryId = as_entry_id(end)
    stated: list[tuple[str, EntryId]] = [
        (relationship.kind, relationship.end)
        for relationship in matrix.outgoing(start_id, family_kinds(FAMILY_DEPENDENCY))
        if relationship.side == AUTHORITY_SIDE
    ]
    direct: frozenset[str] = frozenset(kind for kind, reached in stated if reached == end_id)
    if direct:
        return direct, None
    via: EntryId | None = authority_holder(matrix, end_id)
    if via is None or via == authority_holder(matrix, start_id):
        return frozenset(), None
    homed: frozenset[str] = frozenset(kind for kind, reached in stated if build_home(matrix, reached) == via)
    return homed, (via if homed else None)


def build_relations(matrix: Matrix, start: str, end: str) -> frozenset[str] | None:
    """Name the build needs the architecture side states from one item's entry to another's.

    The one rule of what orders a build (``matrix_contract.NO_BUILD_ORDER_KINDS``) is applied to
    the relationships the matrix states (:func:`_stated_needs`: to the entry itself, else to the
    stack it is homed in), so a ``requires`` a span file holds from before the rule (a call, say)
    makes no build need.

    Args:
        matrix: The matrix.
        start: The matrix id of the item that requires the other; empty when the item has none.
        end: The matrix id of the item it requires; empty when the item has none.

    Returns:
        The dependency relationship kinds stated from ``start`` to ``end`` that order a build;
        empty when the matrix states none or an id is empty, so the span's ``requires`` stands.
        None when every relationship stated between the two never orders a build.

    """
    if not start or not end:
        return frozenset()
    found: frozenset[str] = _stated_needs(matrix, start, end)[0]
    stated: frozenset[str] = found - NO_BUILD_ORDER_KINDS
    return None if found and not stated else stated


def build_via(matrix: Matrix, start: str, end: str) -> EntryId | None:
    """Name the stack through which one item's entry needs another's built, when it is not needed directly.

    A need stated through a stack (an ``imports`` of a library's stack, say) is satisfied by what
    that stack releases, not by one element of it.

    Args:
        matrix: The matrix.
        start: The matrix id of the item that requires the other; empty when the item has none.
        end: The matrix id of the item it requires; empty when the item has none.

    Returns:
        The stack the other entry is homed in when every relationship the architecture side states
        from ``start`` that orders a build ends at that stack or at a layer or package homed in it
        (:func:`_stated_needs`); None when a relationship ends at ``end`` itself, none is stated,
        or an id is empty.

    """
    if not start or not end:
        return None
    found: frozenset[str]
    via: EntryId | None
    found, via = _stated_needs(matrix, start, end)
    return via if found - NO_BUILD_ORDER_KINDS else None


def _orders_build(matrix: Matrix, item: StoryBuild | JsonObject, needed: StoryBuild | JsonObject) -> bool:
    """Report whether one item's ``requires`` of another is a build need under the rule.

    Returns:
        False when every relationship the matrix states between their entries never orders a build.

    """
    return build_relations(matrix, str(item.get("matrixId") or ""), str(needed.get("matrixId") or "")) is not None


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


def _story_needs(
    files: StoryFiles,
    requires: Mapping[str, list[str]],
    builders: Mapping[str, list[str]],
) -> list[tuple[str, str, str]]:
    """List the build needs within a Story that name the one Task on each end.

    An item's need names no Task: an edge is derived only when one Task of the Story builds the
    item and at most one builds the item it requires. When several Tasks cite either, which of
    them consumes or provides the required item is a judgment on the Tasks' content, which the
    decomposer's own edges carry, so no edge is fanned onto every one of them. A ``requires`` that
    every relationship the matrix states between the two never orders (a call, say) is no need
    (:func:`build_relations`).

    Args:
        files: The Story's saved files.
        requires: Item id -> the ids it needs built first (:func:`delta_requires`).
        builders: Item id -> the keys of the Story's Tasks that cite it.

    Returns:
        (dependent Task key, item, required item) for each need between items this Story builds
        whose required item one other Task builds or no Task builds.

    """
    detailed: dict[str, StoryBuild] = story_builds(files.scope)
    own: dict[str, StoryBuild] = {key: item for key, item in detailed.items() if item["slug"] == files.slug}
    sole: dict[str, str] = {item: keys[0] for item, keys in builders.items() if item in own and len(keys) == 1}
    matrix: Matrix = shared_matrix(matrix_path(None, os.environ))
    return [
        (key, item, needed)
        for item, key in sole.items()
        for needed in requires.get(item, [])
        if _single_provider(needed, key, own, builders) and _orders_build(matrix, own[item], own[needed])
    ]


def _single_provider(needed: str, key: str, own: Mapping[str, StoryBuild], builders: Mapping[str, list[str]]) -> bool:
    """Report whether a required item of the Story is built by one other Task, or by none.

    Returns:
        True when the Story builds ``needed`` and its builders are none or one Task other than ``key``.

    """
    providers: list[str] = builders.get(needed, [])
    return needed in own and key not in providers and len(providers) <= 1


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def derive_prerequisites(files: StoryFiles, tasks: list[Task]) -> list[Task]:
    """Derive in-Story prerequisite edges from what the Story builds.

    An item's build need becomes an edge onto the one Task of the Story that builds the item, from
    the one Task that builds the required item, and only when the matrix states a relationship that
    orders a build between them, or none (:func:`_story_needs`). Missing builders remain coverage
    findings. Cross-repository prerequisites are
    connected by closure_task_edges after every repository's Tasks exist.
    Cyclic derived edges are dropped and reported as normalization warnings.

    Returns:
        The Tasks in build order, each with the prerequisites derived for it.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    _taken: list[tuple[str, str]]
    left: list[tuple[str, str]]
    frm: str
    to: str
    if not (isinstance(files, StoryFiles)) or not (isinstance(tasks, list)):
        raise TypeError(_ARGUMENT_ERROR)
    requires: dict[str, list[str]] | None = delta_requires(files.scope.elements)
    if requires is None:
        return tasks
    by_key: dict[str, Task] = {t.key: t for t in tasks}
    builders: dict[str, list[str]] = _task_builders(tasks)
    problems: list[str] = []
    saved_edges: list[tuple[str, str]] = [(d, t.key) for t in tasks for d in t.depends_on]
    for key, item, needed in _story_needs(files, requires, builders):
        found: list[str] = [k for k in builders.get(needed, []) if k != key]
        if not found:
            problems.append(f"{key} builds {item}, which requires {needed}; no Task of this Story builds it")
        by_key[key].depends_on.extend(k for k in found if k not in by_key[key].depends_on)
    _WARNINGS.extend(f"{files.tasks_file.name}: {p}" for p in problems)
    nodes: list[str] = [t.key for t in tasks]
    saved: set[tuple[str, str]] = set(saved_edges)
    derived: list[tuple[str, str]] = [(d, t.key) for t in tasks for d in t.depends_on if (d, t.key) not in saved]
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
