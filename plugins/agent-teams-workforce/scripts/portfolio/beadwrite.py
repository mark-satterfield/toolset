"""Write one Story, one Task, or one Task's edges to Tasks in other Stories into beads.

Each command writes ONE bead. It reads the documents its caller hands it by path (`StoryFiles`,
`SpanStories`) and is keyed by the durable elaboration key: a Story or Task no bead under its
parent carries is created, an open one that carries it is updated where it differs, and any
other is left as it is. The plans (`plan_story_tasks`, `plan_task_edges`) read the saved
documents only and run no `bd` command. A write that fails raises `GraphError` from the
writer, and a rerun repairs it, because every write is keyed.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path
from typing import Final, Unpack

import portfolio_path  # ruff: ignore[unused-import] - Puts the plugin's contract modules on the path first.

# isort: split
import beadcontracts
import beadgraph
import contracts
import hierarchy
from beadcontracts import (
    AllEdgeWrite,
    ClosureEdges,
    CorrectionRejection,
    EdgeCounts,
    EdgePlan,
    ExistingTask,
    PlannedTask,
    ReplacedTask,
    RepointedEdge,
    StoryBuild,
    StoryWrite,
    SupersededTasks,
    TaskCorrection,
    TaskEdge,
    TaskEdgeWrite,
    TaskPlan,
    TaskReplacement,
    TaskWrite,
    TaskWriteOptions,
)
from beadgraph import (
    SCOPE_JUDGING,
    Bead,
    Graph,
    Writer,
    bead_of,
    children,
    fingerprints,
    same_value,
)
from contracts import JsonInput, JsonObject, JsonValue, json_object
from hierarchy import (
    SIZE_KEYS,
    HierarchyError,
    ReadTaskOptions,
    SpanStories,
    StoryFiles,
    Task,
    build_order,
    check_cds_contract,
    check_detailed_work,
    delta_requires,
    derive_prerequisites,
    elab_slug,
    item_briefs,
    read_story,
    read_task_deps,
    read_tasks,
    size_metadata,
    story_builds,
    str_list,
    take_warnings,
    uncited_work,
    work_items,
)
from scoring import JUDGED_HASH_KEY
from typeguard import CollectionCheckStrategy, check_type, typechecked

# isort: split
from bead_metadata import (
    ARG_REQUIREMENT_IDS,
    BUILD_LIFECYCLE_KEYS,
    CDS_AUDIT_KEYS,
    CDS_DESIGN_SOURCE_BUNDLE,
    CDS_DESIGN_SOURCE_CDS,
    CDS_DESIGN_SOURCE_NONE,
    KEY_ACCEPTANCE_CRITERIA,
    KEY_CDS_ARTIFACT,
    KEY_CDS_BUILD_SPECS,
    KEY_CDS_BUNDLE_PATH,
    KEY_CDS_DESIGN_SOURCE,
    KEY_DECISION_IDS,
    KEY_DEFINITION_OF_DONE,
    KEY_ELAB_KEY,
    KEY_MATRIX_ELEMENTS,
    KEY_REPO_PATH,
    KEY_REQUIREMENT_IDS,
    KEY_SPEC_PATH,
    KEY_SPEC_PATHS,
    KEY_SPEC_SECTIONS,
    KEY_SURFACES,
    KEY_TEST_STRATEGY,
    UNKNOWN,
)
from matrix_contract import (
    AUTHORITY_SIDE,
    FAMILY_DEPENDENCY,
    REL_CALLS,
    REL_IMPORTS,
    REL_MATCHES,
    REL_PUBLISHES,
    REL_READS,
    REL_RUNS_IN,
    family_kinds,
)
from matrixstore import Matrix, as_entry_id, matrix_path, read_matrix
from placement_contract import KEY_ITEM_ID, PlacementError, PlacementRuling, parse_placement_ruling
from recon_contract import DESIGN_SOURCES, DesignSource
from task_deps_contract import KIND_CONTRACT, KIND_DATA, KIND_INFRASTRUCTURE

#: The metadata keys the build lane writes on a Task; any of them set means the Task was started.
_BUILD_LANE_KEYS: Final[frozenset[str]] = frozenset((*BUILD_LIFECYCLE_KEYS, *CDS_AUDIT_KEYS))

#: The one status a matched Story or Task is rewritten in.
_ARGUMENT_ERROR: str = "Arguments violate the beadwrite input contract"


OPEN = "open"

#: The Task edge kind each architecture-side relationship between two built items makes, first match wins.
_EDGE_KIND: Final[dict[str, str]] = {
    REL_CALLS: KIND_CONTRACT,
    REL_IMPORTS: KIND_CONTRACT,
    REL_READS: KIND_DATA,
    REL_RUNS_IN: KIND_INFRASTRUCTURE,
}

#: The relationships that never order a build: a producer and a routing rule each depend only on the bus.
_NO_BUILD_ORDER: Final[frozenset[str]] = frozenset((REL_PUBLISHES, REL_MATCHES))

#: The priority `bd create` gives a bead when none is passed.
DEFAULT_PRIORITY = 2


def _norm(text: JsonValue) -> str:
    """Return the text with its whitespace collapsed, as matching compares it.

    Args:
        text: The text.

    Returns:
        The collapsed text.

    """
    return " ".join(str(text or "").split())


def _json(value: JsonInput) -> str:
    """Return compact JSON, as metadata stores it.

    Args:
        value: The value.

    Returns:
        The JSON text.

    """
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _same(stored: JsonValue, wanted: str) -> bool:
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


def _strategy_line(strategy: JsonObject | None) -> str:
    """Return a Task's test strategy as one contract line.

    Args:
        strategy: The strategy the spec states, or None.

    Returns:
        The line.

    """
    if not strategy:
        return "unknown (the spec states none)"
    env: list[str] = [
        str(x).strip()
        for x in check_type(
            strategy.get("envMatrix") or [],
            list[JsonValue],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        if str(x).strip()
    ]
    source: str = f" (from {strategy['source']})" if strategy.get("source") else ""
    return (
        f"pyramid={strategy.get('pyramid') or 'n/a'}; "
        f"coverageThreshold={strategy.get('coverageThreshold') or 'n/a'}; "
        f"envMatrix={', '.join(env) or 'n/a'}{source}"
    )


#: What each design source of a web-ui Task means for the build, as the contract states it.
DESIGN_SOURCE_TEXT: Final[dict[str, str]] = {
    CDS_DESIGN_SOURCE_BUNDLE: "built from the cds bundle the owner supplied, and audited against it",
    CDS_DESIGN_SOURCE_CDS: "designed with the CDS design system (cds-ui-implementer and the project's "
    "design system config), and audited against the live design system",
    CDS_DESIGN_SOURCE_NONE: "changes no design (copy, or data wired into an existing element); built "
    "like any other code change, with no cds design step or audit",
}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def contract_block(task: Task, root: Path | None) -> str:
    """Return the build contract appended to a Task's description.

    Args:
        task: The Task.
        root: The project root its spec paths are relative to.

    Returns:
        The Markdown block.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(task, Task)) or not (isinstance(root, Path) or root is None):
        raise TypeError(_ARGUMENT_ERROR)

    def listed(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items) if items else "- (none)"

    if task.surfaces is None:
        surfaces: str = "unknown (none declared)"
    else:
        surfaces = ", ".join(task.surfaces) or "(declared none — internal-only)"
    spec: str = task.spec_paths[0] if task.spec_paths else "MISSING — no spec reference could be recorded for this Task"
    lines: list[str] = [
        "## Spec contract",
        f"Paths are relative to the project root{f' ({root})' if root else ''}.",
        f"Spec: {spec}",
    ]
    if len(task.spec_paths) > 1:
        lines.append(f"Spec documents:\n{listed(task.spec_paths)}")
    lines += [
        f"Spec sections:\n{listed(task.spec_sections)}",
        f"Requirement ids: {', '.join(task.requirement_ids) or '(none)'}",
        f"Matrix ids (stack, entries built, shared capabilities used):\n{listed(task.matrix_elements)}",
    ]
    if task.events:
        lines.append(f"Events built (each with its publisher):\n{listed(task.events)}")
    lines += [
        f"Surfaces: {surfaces}",
        f"Test strategy: {_strategy_line(task.test_strategy)}",
        f"Definition of Done:\n{listed(task.definition_of_done)}",
    ]
    if task.cds_design_source:
        lines.append(
            f"Design source: {task.cds_design_source} — " + DESIGN_SOURCE_TEXT.get(task.cds_design_source, ""),
        )
    if len(task.cds_artifacts) == 1:
        art: dict[str, str] = task.cds_artifacts[0]
        lines.append(f"cds artifact: {art['kind']} {art['slug']}")
    if task.cds_bundle_path or task.cds_build_specs:
        lines += [
            f"cds bundle: {task.cds_bundle_path or '(none resolved)'}",
            f"cds build specs:\n{listed(task.cds_build_specs)}",
        ]
    return "\n".join(lines)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_text(task: Task, root: Path | None) -> str:
    """Return a Task's full description: its repository, its prose, then its build contract.

    Args:
        task: The Task.
        root: The project root.

    Returns:
        The description.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(task, Task)) or not (isinstance(root, Path) or root is None):
        raise TypeError(_ARGUMENT_ERROR)
    repository: str = f"Repository: {task.repo_path} — work only in this repository."
    return "\n\n".join(x for x in (repository, task.description, contract_block(task, root)) if x)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_metadata(task: Task) -> dict[str, str]:
    """Return every metadata key a Task is written with.

    Args:
        task: The Task, with its elaboration key.

    Returns:
        The metadata.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(task, Task)):
        raise TypeError(_ARGUMENT_ERROR)
    m: dict[str, str] = {KEY_ELAB_KEY: task.elab_key or "", KEY_REPO_PATH: task.repo_path}
    if task.sizes:
        m.update({k: task.sizes[k] for k in SIZE_KEYS})
    if task.decision_ids:
        m[KEY_DECISION_IDS] = _json(list(dict.fromkeys(task.decision_ids)))
    m[KEY_SPEC_SECTIONS] = _json(task.spec_sections)
    m[KEY_ACCEPTANCE_CRITERIA] = _json(task.acceptance)
    m[KEY_DEFINITION_OF_DONE] = _json(task.definition_of_done)
    m[KEY_REQUIREMENT_IDS] = _json(task.requirement_ids)
    m[KEY_MATRIX_ELEMENTS] = _json(task.matrix_elements)
    m[KEY_SURFACES] = _json(task.surfaces) if task.surfaces is not None else UNKNOWN
    m[KEY_TEST_STRATEGY] = _json(task.test_strategy) if task.test_strategy else UNKNOWN
    if task.cds_design_source:
        m[KEY_CDS_DESIGN_SOURCE] = task.cds_design_source
    if len(task.cds_artifacts) == 1:
        m[KEY_CDS_ARTIFACT] = _json(task.cds_artifacts[0])
    if task.cds_bundle_path:
        m[KEY_CDS_BUNDLE_PATH] = task.cds_bundle_path
    if task.cds_build_specs:
        m[KEY_CDS_BUILD_SPECS] = _json(task.cds_build_specs)
    if task.spec_paths:
        m[KEY_SPEC_PATH] = task.spec_paths[0]
        m[KEY_SPEC_PATHS] = _json(task.spec_paths)
    return m


def _create_args(  # ruff: ignore[too-many-arguments] - one `bd create` flag each
    kind: str,
    *,
    title: str,
    text: str,
    parent: str,
    acceptance: list[str],
    notes: str | None,
    metadata: dict[str, str],
) -> list[str]:
    """Return the `bd create` arguments for one bead.

    Returns:
        The arguments.

    """
    args: list[str] = [
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
    writer: Writer,
    bead: Bead,
    title: str,
    text: str,
    metadata: dict[str, str],
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
    key: str
    value: str
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
    """Return beads by their elaboration key, the first one winning.

    Args:
        beads: The beads.

    Returns:
        elaboration key -> bead.

    """
    b: Bead
    out: dict[str, Bead] = {}
    for b in beads:
        key: str | None = b.metadata.get(KEY_ELAB_KEY)
        if key and key not in out:
            out[key] = b
    return out


def _story_of(graph: Graph, epic_id: str, slug: str) -> Bead | None:
    """Return the Story under the Epic whose elaboration key is `story:<slug>`.

    Args:
        graph: The tracker graph.
        epic_id: The Epic.
        slug: The Story's repository slug.

    Returns:
        The Story, or None.

    """
    return _keyed(_children(graph, epic_id, "story")).get(f"story:{slug}")


def _item_order(item: str) -> list[int | str]:
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
    marked: set[str] = set(work or [])
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
        tasks: The Tasks, in build order; each gains its elaboration key.
        slug: The Story's repository slug.
        work: The ids the repository's detailing marks add, modify or remove, or None.

    """
    t: Task
    key: str
    n: int
    taken: set[str] = set()
    for t in tasks:
        if t.reuses and t.reuses not in taken:
            key = t.reuses
        else:
            cited: list[str] = _work_cited(t.requirement_ids, work)
            base: str = f"task:{slug}:items:{'+'.join(elab_slug(i) for i in cited)}" if cited else _title_key(t, slug)
            key, n = base, 2
            while key in taken:
                key = f"{base}-{n}"
                n += 1
        taken.add(key)
        t.elab_key = key


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def plan_tasks(files: StoryFiles, root: Path | None, packages_dir: str | None = None) -> list[Task]:
    """Return a Story's saved Tasks, each with its durable key, in build order.

    Reads the Story document, the Tasks file and the span's two files; runs no `bd` command.

    Args:
        files: The repository's saved files.
        root: The project root spec references are recorded relative to, or None.
        packages_dir: The packages directory a cited cds bundle must sit in, or None.

    Returns:
        The Tasks.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(files, StoryFiles))
        or not (isinstance(root, Path) or root is None)
        or not (isinstance(packages_dir, str) or packages_dir is None)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    saved: hierarchy.Story = read_story(files, root)
    tasks: list[hierarchy.Task] = read_tasks(
        files,
        root,
        ReadTaskOptions(files.slug, files.repo, saved.decision_ids, packages_dir),
    )
    check_detailed_work(files, tasks)
    tasks = derive_prerequisites(files, tasks)
    check_cds_contract(files.slug, tasks)
    _assign_keys(tasks, files.slug, work_items(files))
    return tasks


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_story(graph: Graph, writer: Writer, epic_id: str, files: StoryFiles, *, root: Path | None) -> StoryWrite:
    """Write one repository's Story under the Epic from its saved Story document.

    The Story is found by its elaboration key `story:<slug>` among the Epic's Stories: one that
    exists is refreshed where it differs and is open, and is never created a second time.

    Args:
        graph: The tracker graph, read with descriptions.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        files: The repository's saved files.
        root: The project root artifact paths are recorded relative to.

    Returns:
        The Story, what was done to it, and the keyed Tasks already under it.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not all((
        isinstance(graph, Graph),
        isinstance(writer, Writer),
        isinstance(epic_id, str),
        isinstance(files, StoryFiles),
        isinstance(root, Path) or root is None,
    )):
        raise TypeError(_ARGUMENT_ERROR)
    slug: str = files.slug
    repo: str = files.repo
    story: hierarchy.Story = read_story(files, root)
    bead: beadgraph.Bead | None = _story_of(graph, epic_id, slug)
    existing: list[ExistingTask] = []
    if bead is None:
        args: list[str] = _create_args(
            "story",
            title=story.title,
            text=story.description,
            parent=epic_id,
            acceptance=story.acceptance,
            notes=f"{KEY_REPO_PATH}: {repo}",
            metadata=story.metadata,
        )
        story_id: str = writer.create(args, story.metadata[KEY_ELAB_KEY])
        action: str = "created"
    else:
        story_id = bead.id
        wrote: bool = bead.status == OPEN and _refresh(
            writer,
            bead,
            story.title,
            story.description,
            story.metadata,
        )
        action = "updated" if wrote else "unchanged"
        existing = [
            {
                "elabKey": b.metadata[KEY_ELAB_KEY],
                "title": b.title,
                "description": b.description[:300],
                "status": b.status,
            }
            for b in _children(graph, bead.id, "task")
            if b.metadata.get(KEY_ELAB_KEY)
        ]
    return {
        "ok": True,
        "epic": epic_id,
        "story": {
            "id": story_id,
            "elabKey": story.metadata[KEY_ELAB_KEY],
            "action": action,
            "title": story.title,
            "description": story.description,
            "decisionIds": story.decision_ids,
        },
        "existingTasks": existing,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "id": story_id,
            "elabKey": story.metadata[KEY_ELAB_KEY],
            "action": action,
            "created": int(action == "created"),
            "updated": int(action == "updated"),
        },
    }


def _design_source(value: str) -> DesignSource:
    """Return the recon contract's design source the text names.

    Returns:
        The contract design source equal to `value`.

    Raises:
        ValueError: When the text is not a design source the contract allows.

    """
    for source in DESIGN_SOURCES:
        if value == source:
            return source
    message: str = f"cds design source {value!r} is not one of {DESIGN_SOURCES}"
    raise ValueError(message)


def _planned_task(task: Task) -> PlannedTask:
    result: PlannedTask = {
        "key": task.key,
        "elabKey": task.elab_key,
        "title": task.title,
        "dependsOn": task.depends_on,
        "blockedByExternal": task.blocked_by_external,
    }
    if task.cds_design_source:
        result["designSource"] = _design_source(task.cds_design_source)
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def plan_story_tasks(files: StoryFiles, *, root: Path | None, packages_dir: str | None = None) -> TaskPlan:
    """Return a Story's Tasks in build order with their durable keys; runs no `bd` command.

    Args:
        files: The repository's saved files.
        root: The project root spec paths are recorded relative to.
        packages_dir: The packages directory a cited cds bundle must sit in, or None.

    Returns:
        Each Task's local key, elaboration key, title and the local keys it depends on, and
        `uncited`: the items of what the Story builds that no Task cites.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(files, StoryFiles))
        or not (isinstance(root, Path) or root is None)
        or not (isinstance(packages_dir, str) or packages_dir is None)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    take_warnings()
    tasks: list[hierarchy.Task] = plan_tasks(files, root, packages_dir)
    warnings: list[str] = take_warnings()
    uncited: list[str] = uncited_work(files, tasks)
    return {
        "ok": True,
        "slug": files.slug,
        "warnings": warnings,
        "uncited": uncited,
        "uncitedItems": item_briefs(files, uncited),
        "unsized": [t.key for t in tasks if not t.sizes],
        "tasks": [_planned_task(task) for task in tasks],
        "summary": {"tasks": len(tasks), "warnings": len(warnings)},
    }


#: Who records a work item as `done` when the corrective pass states no work is needed.
NO_WORK_RULED_BY = "task-decomposition corrective pass"


def _write_json(path: Path, value: JsonObject) -> None:
    """Write a JSON file whole, through a temporary file beside it.

    Args:
        path: The file.
        value: Its content.

    """
    temp: Path = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", "utf-8")
    temp.replace(path)


def _local_keys(start: list[JsonObject]) -> Iterator[str]:
    """Yield fresh local Task keys `T<n>` past every key already in the file.

    Args:
        start: The Tasks already saved.

    Yields:
        The next unused key.

    """
    taken: set[str] = {str(t.get("key") or "") for t in start}
    n: int = 1 + max(
        (int(k[1:]) for k in taken if re.fullmatch(r"T\d+", k)),
        default=0,
    )
    while True:
        if f"T{n}" not in taken:
            yield f"T{n}"
        n += 1


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class _TaskCorrection:
    """Merge a single correction while retaining its original Task document."""

    path: Path
    saved: JsonObject
    fix: JsonObject
    existing: list[JsonObject]
    work: set[str]
    cited: set[str]
    gap: set[str]
    original_scores: dict[str, JsonObject]
    unsized: set[str]
    fresh: Iterator[str]
    keymap: dict[str, str]
    taken: set[str]
    added: list[JsonObject]
    rejected: list[CorrectionRejection]
    dropped: list[str | None]
    trimmed: list[str | None]
    keys: set[str]
    resized: list[str]

    def __init__(self, files: StoryFiles, correction: Path) -> None:
        if not (isinstance(files, StoryFiles)) or not (isinstance(correction, Path)):
            raise TypeError(_ARGUMENT_ERROR)
        self.files: StoryFiles = files
        self.correction: Path = correction

    def execute(self) -> TaskCorrection:
        """Merge new tasks, edges, and justified score corrections.

        Returns:
            The exact accepted and rejected correction results.

        Raises:
            HierarchyError: The correction incorrectly declares no work.

        """
        task: JsonObject
        self.path = self.files.tasks_file
        self.saved = json_object(json.loads(self.path.read_text("utf-8")))
        self.fix = json_object(json.loads(self.correction.read_text("utf-8")))
        if "noWork" in self.fix:
            message: str = "noWork is not a Task correction"
            raise HierarchyError(message)
        self.existing = check_type(
            self.saved["tasks"],
            list[JsonObject],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        self.work = set(work_items(self.files))
        self.cited = {i for t in self.existing for i in str_list(t.get(ARG_REQUIREMENT_IDS))}
        self.gap = self.work - self.cited
        self.original_scores = {
            str(s["key"]): s
            for s in check_type(
                self.saved.get("scores", []),
                list[JsonObject],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        }
        self.unsized = {
            str(t["key"]) for t in self.existing if not size_metadata(self.original_scores.get(str(t["key"])))
        }
        self.fresh = _local_keys(self.existing)
        self.keymap: dict[str, str] = {}
        self.taken: set[str] = set()
        self.added: list[JsonObject] = []
        self.rejected: list[CorrectionRejection] = []
        self.dropped: list[str | None] = []
        self.trimmed: list[str | None] = []
        for task in check_type(
            self.fix["tasks"],
            list[JsonObject],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ):
            ids: set[str] = set(str_list(task.get(ARG_REQUIREMENT_IDS)))
            if not ids or not ids <= self.gap:
                self.rejected.append({
                    "task": check_type(task.get("key"), str | None),
                    "reason": "cites items outside the gap",
                })
                continue
            remaining: set[str] = ids - self.taken
            if not remaining:
                self.dropped.append(check_type(task.get("key"), str | None))
                continue
            if remaining != ids:
                self.trimmed.append(check_type(task.get("key"), str | None))
            key: str = next(self.fresh)
            self.keymap[str(check_type(task.get("key"), str | None))] = key
            self.added.append(json_object({**task, "key": key, ARG_REQUIREMENT_IDS: sorted(remaining)}))
            self.taken.update(remaining)
        self._edges()
        self._scores()
        self.saved["tasks"] = [json_object(row) for row in [*self.existing, *self.added]]
        self.saved["scores"] = [json_object(row) for row in self.original_scores.values()]
        _write_json(self.path, self.saved)
        return {
            "ok": True,
            "added": [check_type(t["key"], str) for t in self.added],
            "resized": self.resized,
            "rejected": self.rejected,
            "dropped": self.dropped,
            "trimmed": self.trimmed,
            "uncited": sorted(self.gap - self.taken),
        }

    def _edges(self) -> None:
        """Merge validated correction edges into the saved document."""
        edge: TaskEdge
        self.keys = {str(t["key"]) for t in self.existing} | set(self.keymap.values())
        for edge in check_type(
            self.fix["edges"],
            list[TaskEdge],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ):
            frm: str = self.keymap.get(edge["from"], edge["from"])
            to: str | None = self.keymap.get(edge["to"])
            if to and frm in self.keys:
                saved_edges: list[contracts.JsonValue] = check_type(
                    self.saved.setdefault("edges", []),
                    list[JsonValue],
                    collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                )
                saved_edges.append({"from": frm, "to": to})
            else:
                self.rejected.append({"edge": edge, "reason": "edge is not into a new Task"})

    def _scores(self) -> None:
        """Merge validated correction scores into the saved document."""
        score: JsonObject
        self.resized = []
        for score in check_type(
            self.fix["scores"],
            list[JsonObject],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ):
            original: str = str(score["key"])
            key: str = self.keymap.get(original, original)
            if not size_metadata(score) or (original not in self.keymap and key not in self.unsized):
                self.rejected.append({"score": original, "reason": "invalid or outside unsized keys"})
                continue
            self.original_scores[key] = {**score, "key": key}
            if key in self.unsized:
                self.resized.append(key)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def add_corrective_tasks(files: StoryFiles, *, correction: Path) -> TaskCorrection:
    """Merge one gap repair into the Story's Tasks file while retaining its Tasks.

    A correction merged a second time adds nothing: its Tasks cite items the first merge covered.

    Returns:
        The accepted and rejected correction details.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(files, StoryFiles)) or not (isinstance(correction, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    return _TaskCorrection(files, correction).execute()


def _cited_ids(value: JsonValue) -> list[str]:
    """Return the ids a bead's `requirement_ids` metadata holds.

    Args:
        value: The metadata value: a JSON list, as written, or a list.

    Returns:
        The ids; empty when the value holds none.

    """
    if isinstance(value, str):
        try:
            decoded: object = json.loads(value)
            value = check_type(decoded, JsonValue, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if isinstance(v, str)]


def _candidate_pairs(
    rest: list[Task],
    free: list[Bead],
    items: dict[str, StoryBuild],
) -> list[tuple[int, int, str, Task, Bead]]:
    """Rank unmatched Tasks by shared cited architecture items.

    Returns:
        Pairs ordered later by overlap, task order, and bead identifier.

    """
    n: int
    t: Task
    b: Bead
    pairs: list[tuple[int, int, str, Task, Bead]] = []
    for n, t in enumerate(rest):
        mine: set[str] = {i for i in t.requirement_ids if i in items}
        for b in free:
            common: set[str] = mine & set(_cited_ids(b.metadata.get(KEY_REQUIREMENT_IDS)))
            if common:
                pairs.append((-len(common), n, b.id, t, b))
    return pairs


def _match_tasks(
    tasks: list[Task],
    beads: list[Bead],
    slug: str,
    items: dict[str, StoryBuild],
) -> tuple[dict[str, Bead], list[Bead]]:
    """Match each of a Story's Tasks to the Task bead it is, and return the beads left over.

    A Task is the bead that carries its elaboration key. Every other Task is matched against the
    Story's Task beads that elaboration wrote (elaboration key `task:<slug>:...`), that are not
    closed and that no Task holds by key, whatever key they were written under: first by
    the delta items both cite, the pair citing the most in common first (then build order,
    then bead id), then by title. A bead is matched to one Task at most, so a Task whose
    cited items changed keeps its bead instead of getting a second one.

    Args:
        tasks: The Story's Tasks, in build order, each with its elaboration key.
        beads: The Story's Task beads, closed ones included, in id order.
        slug: The Story's repository slug.
        items: Every detailed delta item of the Epic, as `detailed_items` returns them.

    Returns:
        Task local key -> its bead, and the candidate beads no Task matched, in id order.

    """
    t: Task
    keyed: dict[str, beadgraph.Bead] = _keyed(beads)
    matched: dict[str, Bead] = {}
    used: set[str] = set()
    for t in tasks:
        b: beadgraph.Bead | None = keyed.get(t.elab_key or "")
        if b is not None and b.id not in used:
            matched[t.key] = b
            used.add(b.id)
    prefix: str = f"task:{slug}:"
    free: list[beadgraph.Bead] = [
        b
        for b in beads
        if b.id not in used and not b.closed and str(b.metadata.get(KEY_ELAB_KEY) or "").startswith(prefix)
    ]
    rest: list[hierarchy.Task] = [t for t in tasks if t.key not in matched]
    pairs: list[tuple[int, int, str, hierarchy.Task, beadgraph.Bead]] = _candidate_pairs(rest, free, items)
    for _, _, _, t, b in sorted(pairs, key=itemgetter(slice(3))):
        if t.key not in matched and b.id not in used:
            matched[t.key] = b
            used.add(b.id)
    for t in rest:
        if t.key in matched:
            continue
        titled: str = _title_key(t, slug)
        for b in free:
            if b.id not in used and (_norm(b.title) == _norm(t.title) or b.metadata.get(KEY_ELAB_KEY) == titled):
                matched[t.key] = b
                used.add(b.id)
                break
    return matched, [b for b in free if b.id not in used]


#: The statuses of a Task no one has started building.
UNSTARTED = frozenset({"open", "blocked", "deferred"})


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def replace_tasks(writer: Writer, epic_id: str, *, slug: str, reason: str) -> TaskReplacement:
    """Delete a Story's unstarted Task beads, before its Tasks are decomposed again.

    Runs only when something upstream of the Story's Tasks changed. A Task elaboration wrote
    (elaboration key `task:...`) that no one has started (open/blocked, no build-lane facts)
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    b: Bead
    if (
        not (isinstance(writer, Writer))
        or not (isinstance(epic_id, str))
        or not (isinstance(slug, str))
        or not (isinstance(reason, str))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    stories: dict[str, beadgraph.Bead] = _keyed(
        sorted(
            (bead_of(r) for r in children(writer.repo, epic_id, "story")),
            key=lambda b: b.id,
        ),
    )
    story: beadgraph.Bead | None = stories.get(f"story:{slug}")
    deleted: list[ReplacedTask] = []
    kept: list[ReplacedTask] = []
    if story is not None:
        records: list[contracts.JsonObject] = children(writer.repo, story.id, "task")
        for b in sorted((bead_of(r) for r in records), key=lambda b: b.id):
            key: str = str(b.metadata.get(KEY_ELAB_KEY) or "")
            facts: ReplacedTask = {"id": b.id, "title": b.title, "elabKey": key, "status": b.status}
            started: bool = task_started(b)
            if started or not key.startswith("task:"):
                ids: list[str] = _cited_ids(b.metadata.get(KEY_REQUIREMENT_IDS))
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


def _judged_hash(title: str, text: str, priority: JsonValue) -> str:
    """Return the judging fingerprint of a Task carrying this content.

    Args:
        title: Its title.
        text: Its description.
        priority: Its priority as `bd` reports it.

    Returns:
        The fingerprint.

    """
    record: dict[str, contracts.JsonValue] = json_object({
        "id": "task",
        "title": title,
        "description": text,
        "issue_type": "task",
        "priority": priority,
    })
    return fingerprints([record], SCOPE_JUDGING).get("task", "")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_task(
    writer: Writer,
    epic_id: str,
    files: StoryFiles,
    **options: Unpack[TaskWriteOptions],
) -> TaskWrite:
    """Write one Task of a Story from its saved Tasks file.

    The Task is found by its elaboration key among the Story's Task beads: one that exists is
    refreshed where it differs, or left as it is once building has started, and is never created
    a second time.

    Returns:
        The Task identity, content action, edges, and warnings.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(writer, Writer)) or not (isinstance(epic_id, str)) or not (isinstance(files, StoryFiles)):
        raise TypeError(_ARGUMENT_ERROR)
    check_type(options, TaskWriteOptions, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    return _TaskWriter(writer, epic_id, files, options).execute()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
class _TaskWriter:
    """Keep preparation and persistence facts for one keyed Task write."""

    writer: Writer
    epic_id: str
    files: StoryFiles
    options: TaskWriteOptions
    slug: str
    repo: str
    key: str
    root: Path | None
    external: list[str] | None
    packages_dir: str | None
    tasks: list[Task]
    by_key: dict[str, Task]
    task: Task
    stories: dict[str, Bead]
    story: Bead | None
    story_id: str
    records: list[JsonObject]
    priority: dict[str, JsonValue]
    beads: list[Bead]
    keyed: dict[str, Bead]
    items: dict[str, StoryBuild]
    matched: dict[str, Bead]
    blockers: list[str]
    warnings: list[str]
    story_ids: set[str]
    outer: list[str]
    inner: list[str]
    bead: Bead | None
    text: str
    meta: dict[str, str]
    edges: EdgeCounts
    outside: list[str]
    task_id: str
    action: str

    def __init__(self, writer: Writer, epic_id: str, files: StoryFiles, options: TaskWriteOptions) -> None:
        if (
            not (isinstance(writer, Writer))
            or not (isinstance(epic_id, str))
            or not (isinstance(files, StoryFiles))
            or not (isinstance(options, dict))
        ):
            raise TypeError(_ARGUMENT_ERROR)
        self.writer = writer
        self.epic_id = epic_id
        self.files = files
        self.options = options

    def _prepare_options(self) -> None:
        check_type(self.options, TaskWriteOptions, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        self.slug, self.repo = self.files.slug, self.files.repo
        self.key, self.root = self.options["key"], self.options["root"]
        self.external = self.options.get("external")
        self.packages_dir = self.options.get("packages_dir")
        if not self.repo.strip():
            msg: str = f"Task {self.key} of story:{self.slug} has no repository: a Task is never written without one"
            raise HierarchyError(msg)

    def execute(self) -> TaskWrite:
        """Prepare one Task and return its persisted tracker changes.

        Returns:
            The Task identity and its exact persisted changes.

        Raises:
            HierarchyError: Required repository, Story, Task, or blocker facts are missing.

        """
        msg: str
        dep: str
        self._prepare_options()
        take_warnings()
        self.tasks = plan_tasks(self.files, self.root, self.packages_dir)
        self.by_key = {t.key: t for t in self.tasks}
        task: hierarchy.Task | None = self.by_key.get(self.key)
        if task is None:
            msg = f"{self.files.tasks_file.name} has no Task {self.key}"
            raise HierarchyError(msg)
        self.task = task
        self.stories = _keyed(
            sorted((bead_of(r) for r in children(self.writer.repo, self.epic_id, "story")), key=lambda b: b.id),
        )
        self.story = self.stories.get(f"story:{self.slug}")
        if self.story is None:
            msg = f"{self.epic_id} has no Story story:{self.slug}: its Story is written before its Tasks"
            raise HierarchyError(msg)
        self.story_id = self.story.id
        self.records = children(self.writer.repo, self.story_id, "task")
        self.priority = {str(r["id"]): r.get("priority") for r in self.records}
        self.beads = sorted((bead_of(r) for r in self.records), key=lambda b: b.id)
        self.keyed = _keyed(self.beads)
        self.items = story_builds(self.files.scope)
        self.matched, _ = _match_tasks(self.tasks, self.beads, self.slug, self.items)

        def found(t: Task) -> Bead | None:
            return self.matched.get(t.key)

        self.blockers: list[str] = []
        self.warnings: list[str] = take_warnings()
        for dep in self.task.depends_on:
            blocker: beadgraph.Bead | None = found(self.by_key[dep]) if dep in self.by_key else None
            if blocker is None:
                msg = f"{self.key} depends on {dep}, which is not written under {self.story_id}"
                raise HierarchyError(msg)
            self.blockers.append(blocker.id)
        self.story_ids = {b.id for b in self.keyed.values()}
        self.outer = list(dict.fromkeys([*self.task.blocked_by_external, *(self.external or [])]))
        self.inner = [b for b in self.outer if b in self.story_ids]
        if self.inner:
            self.warnings.append(
                f"{self.key}: {', '.join(self.inner)} are Tasks of {self.story_id}; taken as Story edges",
            )
            self.blockers = list(dict.fromkeys([*self.blockers, *self.inner]))
            self.outer = [b for b in self.outer if b not in self.story_ids]
        self.bead = found(self.task)
        self.text = task_text(self.task, self.root)
        self.meta = task_metadata(self.task)
        if self.task.sizes:
            self.meta[JUDGED_HASH_KEY] = _judged_hash(
                self.task.title,
                self.text,
                self.priority.get(self.bead.id) if self.bead else DEFAULT_PRIORITY,
            )
        self._persist()
        return {
            "ok": True,
            "story": self.story_id,
            "task": {
                "key": self.task.key,
                "elabKey": self.task.elab_key,
                "id": self.task_id,
                "action": self.action,
                "title": self.task.title,
                "dependsOn": self.task.depends_on,
                "outsideBlockers": self.outside,
            },
            "edges": self.edges,
            "warnings": self.warnings,
            "dryRun": self.writer.dry_run,
            "planned": self.writer.planned,
            "summary": {
                "key": self.task.key,
                "id": self.task_id,
                "action": self.action,
                **self.edges,
                "warnings": len(self.warnings),
            },
        }

    def _persist(self) -> None:
        """Create, retain, or refresh the prepared Task and its edges."""
        b: str
        self.edges: EdgeCounts = {"added": 0, "removed": 0, "standing": 0}
        self.outside: list[str] = []
        if self.bead is None:
            args: list[str] = _create_args(
                "task",
                title=self.task.title,
                text=self.text,
                parent=self.story_id,
                acceptance=self.task.acceptance,
                notes=f"{KEY_REPO_PATH}: {self.task.repo_path}",
                metadata=self.meta,
            )
            if self.blockers or self.outer:
                args += ["--deps", ",".join(f"blocked-by:{b}" for b in [*self.blockers, *self.outer])]
            self.task_id, self.action = (self.writer.create(args, self.task.elab_key or self.key), "created")
            self.edges["added"] = len(self.blockers) + len(self.outer)
            self.outside = self.outer
        elif task_started(self.bead):
            self.task_id, self.action = (self.bead.id, "unchanged-started")
        else:
            self.task_id = self.bead.id
            self.action = (
                "updated" if _refresh(self.writer, self.bead, self.task.title, self.text, self.meta) else "unchanged"
            )
            add: list[str] = [b for b in [*self.blockers, *self.outer] if b not in self.bead.blockers]
            drop: list[str] = [b for b in self.bead.blockers if b in self.story_ids and b not in self.blockers]
            if add:
                lines: list[str] = [
                    _json({"issue_id": self.bead.id, "depends_on_id": b, "type": "blocks"}) for b in add
                ]
                self.writer.bd(["dep", "add", "--file", "-"], "\n".join(lines) + "\n")
            for b in drop:
                self.writer.bd(["dep", "remove", self.bead.id, b])
            self.edges = {
                "added": len(add),
                "removed": len(drop),
                "standing": len(self.blockers) + len(self.outer) - len(add),
            }
            self.outside = list(
                dict.fromkeys([*(b for b in self.bead.blockers if b not in self.story_ids), *self.outer]),
            )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def span_tasks(span: SpanStories) -> tuple[dict[str, str], list[tuple[str, str]], dict[str, str]]:
    """Return every saved Task of the span by its `S<i>-<local key>` name.

    The Story at index i of the span is `S<i+1>`. Reads the saved documents only; runs no
    `bd` command.

    Args:
        span: The Stories of the span, in span order, with their saved files.

    Returns:
        Name -> the Story's slug, the `(from, to)` edges within each Story by name, and
        name -> the Task's elaboration key.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    index: int
    files: StoryFiles
    t: Task
    if not (isinstance(span, SpanStories)):
        raise TypeError(_ARGUMENT_ERROR)
    slug_of: dict[str, str] = {}
    intra: list[tuple[str, str]] = []
    elab: dict[str, str] = {}
    for index, files in enumerate(span.stories):
        story: str = f"S{index + 1}"
        for t in plan_tasks(files, None):
            name: str = f"{story}-{t.key}"
            slug_of[name] = files.slug
            elab[name] = t.elab_key or ""
            intra += [(f"{story}-{d}", name) for d in t.depends_on]
    return slug_of, intra, elab


def _accept(
    saved: list[TaskEdge],
    slug_of: dict[str, str],
) -> tuple[list[TaskEdge], list[TaskEdge], set[tuple[str, str]]]:
    """Split the saved edges into accepted and rejected ones.

    Args:
        saved: The saved edges.
        slug_of: Task name -> its Story's slug.

    Returns:
        The accepted edges, the rejected ones with the reason, and `(from, to)` by name
        for each accepted edge.

    """
    e: TaskEdge
    frm: str
    to: str
    a: str | None
    b: str | None
    accepted: list[TaskEdge] = []
    rejected: list[TaskEdge] = []
    pairs: set[tuple[str, str]] = set()
    for e in saved:
        frm, to = str(e.get("from") or ""), str(e.get("to") or "")
        a, b = slug_of.get(frm), slug_of.get(to)
        if a is None or b is None:
            why: str = "an end is not a Task of this run"
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
                },
            )
            continue
        rejected.append({"from": frm, "to": to, "reason": why})
    return accepted, rejected, pairs


def _no_code(span_file: Path) -> set[str]:
    """Return the items the span file records as having no code here.

    Args:
        span_file: The span file.

    Returns:
        Their ids.

    Raises:
        HierarchyError: The span file cannot be read or does not conform to the placement contract.

    """
    try:
        ruling: PlacementRuling = parse_placement_ruling(json.loads(span_file.read_text(encoding="utf-8")))
    except (OSError, ValueError, PlacementError) as exc:
        message: str = f"cannot read the span file {span_file}: {exc}"
        raise HierarchyError(message) from exc
    return {entry[KEY_ITEM_ID].strip() for entry in ruling["noCode"] if entry[KEY_ITEM_ID].strip()}


@dataclass(frozen=True)
class _ClosureContext:
    detailed: dict[str, StoryBuild]
    no_code: set[str]
    builds: dict[str, list[str]]
    task_slug: dict[str, str]
    slug_story: dict[str, str]
    matrix: Matrix
    """The matrix, which states the relationship between an item and an item it requires."""


def _closure_context(span: SpanStories) -> _ClosureContext:
    """Read placements and saved Task builders for prerequisite closure.

    Returns:
        The exact builder and placement facts used to derive edges.

    A span file that cannot be read or does not conform to its contract raises
    ``HierarchyError`` from the span reader.

    """
    index: int
    files: StoryFiles
    task: Task
    no_code: set[str] = _no_code(span.scope.span)
    slug_story: dict[str, str] = {}
    builds: dict[str, list[str]] = {}
    task_slug: dict[str, str] = {}
    for index, files in enumerate(span.stories):
        slug_story[files.slug] = f"S{index + 1}"
        for task in plan_tasks(files, None):
            name: str = f"S{index + 1}-{task.key}"
            task_slug[name] = files.slug
            builds[name] = task.requirement_ids
    return _ClosureContext(
        story_builds(span.scope),
        no_code,
        builds,
        task_slug,
        slug_story,
        read_matrix(matrix_path(None, os.environ)),
    )


def _edge_kind(item: str, requirement: str, context: _ClosureContext) -> tuple[str, str] | None:
    """Name the kind of a closure edge from the relationship the architecture side states.

    Args:
        item: The item a Task builds.
        requirement: The item it requires, which a Task of another Story builds.
        context: The closure's facts, with the matrix.

    Returns:
        The Task edge kind the first relationship of :data:`_EDGE_KIND` between the two entries
        maps to (infrastructure when none of them is stated), and the relationship kinds found,
        joined; empty when the matrix states none. None when every relationship stated between
        the two is one of :data:`_NO_BUILD_ORDER`, which makes no Task edge.

    """
    start: str = context.detailed[item].get("matrixId", "")
    end: str = context.detailed[requirement].get("matrixId", "")
    if not start or not end:
        return KIND_INFRASTRUCTURE, ""
    found: set[str] = {
        relationship.kind
        for relationship in context.matrix.outgoing(as_entry_id(start), family_kinds(FAMILY_DEPENDENCY))
        if relationship.end == end and relationship.side == AUTHORITY_SIDE
    }
    stated: set[str] = found - _NO_BUILD_ORDER
    if found and not stated:
        return None
    kinds: list[str] = [kind for relation, kind in _EDGE_KIND.items() if relation in stated]
    return (kinds[0] if kinds else KIND_INFRASTRUCTURE), ", ".join(sorted(stated))


def _required_builders(name: str, item: str, requirement: str, context: _ClosureContext) -> tuple[list[str], list[str]]:
    """Locate prerequisite builders and explain any missing placement.

    Returns:
        Matching builders and placement or coverage warnings.

    """
    own_item: StoryBuild | None = context.detailed.get(requirement)
    if own_item is None:
        warnings: list[str] = (
            []
            if requirement in context.no_code
            else [f"{name} builds {item}, which requires {requirement}; no repository's placement holds it"]
        )
        return [], warnings
    if own_item["slug"] == context.task_slug[name]:
        return [], []
    found: list[str] = [
        builder
        for builder, built in context.builds.items()
        if context.task_slug[builder] == own_item["slug"] and requirement in built
    ]
    if found:
        return found, []
    return [], [
        (
            f"{name} builds {item}, which requires {requirement}; no "
            f"Task of {context.slug_story.get(own_item['slug'], own_item['slug'])} builds it"
        ),
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def closure_task_edges(span: SpanStories) -> ClosureEdges:
    """Derive cross-Story edges from placements and declared requires relations.

    Returns:
        Explicit prerequisite edges and missing-builder warnings.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    name: str
    items: list[str]
    item: str
    requirement: str
    found: list[str]
    missing: list[str]
    source: str
    if not (isinstance(span, SpanStories)):
        raise TypeError(_ARGUMENT_ERROR)
    requires: dict[str, list[str]] | None = delta_requires(span.scope.elements)
    edges: list[TaskEdge] = []
    warnings: list[str] = []
    if requires is not None:
        context: _ClosureContext = _closure_context(span)
        seen: set[tuple[str, str]] = set()
        for name, items in context.builds.items():
            for item in items:
                own: StoryBuild | None = context.detailed.get(item)
                if own is None or own["slug"] != context.task_slug[name]:
                    continue
                for requirement in requires.get(item, []):
                    found, missing = _required_builders(name, item, requirement, context)
                    warnings.extend(missing)
                    named: tuple[str, str] | None = _edge_kind(item, requirement, context)
                    if named is None:
                        continue
                    kind, relation = named
                    for source in [builder for builder in found if (builder, name) not in seen]:
                        seen.add((source, name))
                        edges.append({
                            "from": source,
                            "to": name,
                            "kind": kind,
                            "reason": f"{item} requires {requirement} "
                            f"({relation or 'no relationship stated'}; the delta's prerequisite closure)",
                        })
    return {
        "ok": True,
        "edges": edges,
        "warnings": warnings,
        "summary": {"ok": True, "edges": len(edges), "warnings": warnings},
    }


def _acyclic(
    accepted: list[TaskEdge],
    slug_of: dict[str, str],
    intra: list[tuple[str, str]],
    warnings: list[str],
) -> tuple[list[TaskEdge], set[tuple[str, str]]]:
    """Keep the accepted edges, in order, that close no cycle over the Tasks or over the Stories.

    A Story follows another when one of its Tasks follows one of the other's, so an edge is
    dropped when the Story order it adds would make two Stories depend on each other.

    Args:
        accepted: The accepted edges between Tasks of different Stories, in order.
        slug_of: Task name -> its Story's slug.
        intra: The `(from, to)` edges within each Story by name.
        warnings: Changed in place: one warning for each edge dropped.

    Returns:
        The edges kept, and `(from, to)` by name for each.

    """
    edge: TaskEdge
    pairs: set[tuple[str, str]] = set()
    story_pairs: set[tuple[str, str]] = set()
    stories: list[str] = sorted(set(slug_of.values()))
    kept: list[TaskEdge] = []
    for edge in accepted:
        pair: tuple[str, str] = (edge["from"], edge["to"])
        if build_order(sorted(slug_of), [*intra, *sorted(pairs | {pair})]) is None:
            warnings.append(f"edge {pair[0]} -> {pair[1]} would close a cycle over the Task graph; dropped")
            continue
        story_pair: tuple[str, str] = (slug_of[pair[0]], slug_of[pair[1]])
        if build_order(stories, sorted(story_pairs | {story_pair})) is None:
            warnings.append(
                f"edge {pair[0]} -> {pair[1]} would make Story {story_pair[1]} and Story {story_pair[0]} "
                "depend on each other; dropped",
            )
            continue
        pairs.add(pair)
        story_pairs.add(story_pair)
        kept.append(edge)
    return kept, pairs


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def plan_task_edges(span: SpanStories) -> EdgePlan:
    """Return the saved Task edges between Stories, checked; runs no `bd` command.

    The edges are those `closure_task_edges` derives from the delta's `requires`
    relations, then the edges of the mapper's file, when the span names one.

    Args:
        span: The Stories of the span, in span order, with their saved files.

    Returns:
        The accepted edges, the rejected ones, each blocked Task's blockers by name, and
        `warnings`: the closure's warnings, and each edge dropped because it would close a
        cycle over the Epic's Task graph, or over its Stories, where a Story follows another when
        one of its Tasks follows one of the other's, so that no two Stories depend on each other
        (edges are taken in order, the closure's first).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    slug_of: dict[str, str]
    intra: list[tuple[str, str]]
    _elab: dict[str, str]
    accepted: list[TaskEdge]
    rejected: list[TaskEdge]
    _pairs: set[tuple[str, str]]
    pairs: set[tuple[str, str]]
    frm: str
    to: str
    if not (isinstance(span, SpanStories)):
        raise TypeError(_ARGUMENT_ERROR)
    closure: beadcontracts.ClosureEdges = closure_task_edges(span)
    warnings: list[str] = list(closure["warnings"])
    standing: set[tuple[str, str]] = {(e["from"], e["to"]) for e in closure["edges"]}
    mapped: list[beadcontracts.TaskEdge] = read_task_deps(span.task_deps) if span.task_deps is not None else []
    saved: list[TaskEdge] = [
        *closure["edges"],
        *(e for e in mapped if (str(e.get("from") or ""), str(e.get("to") or "")) not in standing),
    ]
    slug_of, intra, _elab = span_tasks(span)
    accepted, rejected, _pairs = _accept(saved, slug_of)
    accepted, pairs = _acyclic(accepted, slug_of, intra, warnings)
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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_task_edges(
    graph: Graph,
    writer: Writer,
    epic_id: str,
    span: SpanStories,
    *,
    name: str,
) -> TaskEdgeWrite:
    """Write ONE Task's `blocks` edges to Tasks in the Epic's other Stories.

    The Task gains each saved blocker it lacks, in one `bd dep add`, and, when it is open,
    loses each blocker in another of the Epic's Stories that the saved edges no longer name.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        span: The Stories of the span, in span order, with their saved files.
        name: The Task, as `S<i>-<local key>`.

    Returns:
        The Task, its saved edges, the edges added, removed and standing, and `warnings`:
        an edge whose other end is not written is skipped, and a Task that is not written
        has no edges written.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not all((
        isinstance(graph, Graph),
        isinstance(writer, Writer),
        isinstance(epic_id, str),
        isinstance(span, SpanStories),
        isinstance(name, str),
    )):
        raise TypeError(_ARGUMENT_ERROR)
    return _write_planned_task_edges(graph, writer, _EdgeScope(epic_id, span, plan_task_edges(span)), name)


@dataclass(frozen=True)
class _EdgeScope:
    """The Epic, its span and the span's Task edge plan, computed once for every Task written."""

    epic_id: str
    span: SpanStories
    plan: beadcontracts.EdgePlan


def _write_planned_task_edges(graph: Graph, writer: Writer, scope: _EdgeScope, name: str) -> TaskEdgeWrite:
    """Write ONE Task's `blocks` edges from an edge plan already computed for its span.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.
        scope: The Epic, the span and the span's edge plan.
        name: The Task, as `S<i>-<local key>`.

    Returns:
        The result `write_task_edges` returns.

    """
    slug_of: dict[str, str]
    _intra: list[tuple[str, str]]
    elab: dict[str, str]
    dropped_id: str
    epic_id: str = scope.epic_id
    edge_plan: beadcontracts.EdgePlan = scope.plan
    slug_of, _intra, elab = span_tasks(scope.span)
    warnings: list[str] = []

    def bead_named(n: str) -> Bead | None:
        story: beadgraph.Bead | None = _story_of(graph, epic_id, slug_of.get(n, ""))
        bead: beadgraph.Bead | None = _keyed(_children(graph, story.id, "task")).get(elab.get(n, "")) if story else None
        if bead is None:
            warnings.append(f"Task {n} ({elab.get(n)}) is not written under {epic_id}")
        return bead

    task: beadgraph.Bead | None = bead_named(name)
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
    wanted: list[str] = [b.id for n in edge_plan["blockers"].get(name, []) if (b := bead_named(n)) is not None]
    story_of: dict[str, str] = {
        bead.id: story.id
        for story in _children(graph, epic_id, "story")
        for bead in _keyed(_children(graph, story.id, "task")).values()
    }
    add: list[str] = [b for b in wanted if b not in task.blockers]
    drop: list[str] = (
        []
        if task.status != OPEN
        else [b for b in task.blockers if story_of.get(b) not in {None, task.parent} and b not in wanted]
    )
    if add:
        lines: list[str] = [_json({"issue_id": task.id, "depends_on_id": b, "type": "blocks"}) for b in add]
        writer.bd(["dep", "add", "--file", "-"], "\n".join(lines) + "\n")
    for dropped_id in drop:
        writer.bd(["dep", "remove", task.id, dropped_id])
    counts: EdgeCounts = {
        "added": len(add),
        "removed": len(drop),
        "standing": len(wanted) - len(add),
    }
    return {
        "ok": True,
        "epic": epic_id,
        "task": {"name": name, "id": task.id},
        "edges": [e for e in edge_plan["edges"] if e["to"] == name],
        "warnings": warnings,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {"name": name, "id": task.id, **counts},
    }


def _task_beads(graph: Graph, epic_id: str, span: SpanStories) -> dict[str, Bead]:
    """Return the bead of every saved Task of the span that beads holds, by its name.

    Args:
        graph: The tracker graph.
        epic_id: The Epic.
        span: The Stories of the span, in span order, with their saved files.

    Returns:
        `S<i>-<local key>` -> the Task's bead.

    """
    slug_of: dict[str, str]
    _intra: list[tuple[str, str]]
    elab: dict[str, str]
    name: str
    slug: str
    slug_of, _intra, elab = span_tasks(span)
    out: dict[str, Bead] = {}
    for name, slug in slug_of.items():
        story: beadgraph.Bead | None = _story_of(graph, epic_id, slug)
        bead: beadgraph.Bead | None = _keyed(_children(graph, story.id, "task")).get(elab[name]) if story else None
        if bead is not None:
            out[name] = bead
    return out


def _carrying(graph: Graph, epic_id: str, span: SpanStories) -> list[str]:
    """Return the saved Tasks whose open bead carries a blocker in another of the Epic's Stories.

    Args:
        graph: The tracker graph.
        epic_id: The Epic.
        span: The Stories of the span, in span order, with their saved files.

    Returns:
        The Tasks, as `S<i>-<local key>`.

    """
    story_of: dict[str, str] = {
        bead.id: story.id for story in _children(graph, epic_id, "story") for bead in _children(graph, story.id, "task")
    }
    return [
        name
        for name, bead in _task_beads(graph, epic_id, span).items()
        if bead.status == OPEN and any(story_of.get(b) not in {None, bead.parent} for b in bead.blockers)
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_all_task_edges(
    graph: Graph,
    writer: Writer,
    epic_id: str,
    span: SpanStories,
    *,
    also: list[str],
) -> AllEdgeWrite:
    """Write the saved edges to other Stories of every Task that has them, one Task at a time.

    A Task the saved edges name no blocker for is written too when its bead carries a
    blocker in another of the Epic's Stories, so an edge the saved edges no longer name
    is removed.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        span: The Stories of the span, in span order, with their saved files.
        also: Tasks, as `S<i>-<local key>`, whose edges to other Stories are
            written even when the saved edges name no blocker for them.

    Returns:
        Each Task written with its counts, and a summary carrying the blockers by
        name, the totals, the Tasks written and the number of warnings.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not all((
        isinstance(graph, Graph),
        isinstance(writer, Writer),
        isinstance(epic_id, str),
        isinstance(span, SpanStories),
        isinstance(also, list),
    )):
        raise TypeError(_ARGUMENT_ERROR)
    plan: beadcontracts.EdgePlan = plan_task_edges(span)
    scope: _EdgeScope = _EdgeScope(epic_id, span, plan)
    names: list[str] = list(
        dict.fromkeys(
            [*plan["blockers"], *also, *_carrying(graph, epic_id, span)],
        ),
    )
    written: list[beadcontracts.TaskEdgeWrite] = [
        _write_planned_task_edges(graph, writer, scope, name) for name in names
    ]
    tasks: list[beadcontracts.TaskEdgeSummary] = [w["summary"] for w in written]
    warnings: list[str] = list(
        dict.fromkeys([*plan["warnings"], *(m for w in written for m in w["warnings"])]),
    )
    totals: EdgeCounts = {
        "added": sum(t["added"] for t in tasks),
        "removed": sum(t["removed"] for t in tasks),
        "standing": sum(t["standing"] for t in tasks),
    }
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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def retire_superseded_tasks(  # ruff: ignore[too-many-arguments] - the caller's facts, one each
    graph: Graph,
    writer: Writer,
    epic_id: str,
    files: StoryFiles,
    *,
    root: Path | None,
    packages_dir: str | None = None,
) -> SupersededTasks:
    """Delete the unstarted Task beads a Story's saved Tasks no longer name.

    A Task bead elaboration wrote under the Story that no saved Task matches and that no one has
    started is superseded. Each `blocks` edge from a Task of another Story onto it is first added
    onto every written Task that cites an item it cited; then the superseded beads are deleted.
    Run again, it adds no edge twice and finds nothing left to delete.

    Args:
        graph: The tracker graph, read after the Story's Tasks were written.
        writer: The tracker writer; a dry-run writer records the writes instead.
        epic_id: The Epic.
        files: The repository's saved files.
        root: The project root spec references are recorded relative to.
        packages_dir: The packages directory a cited cds bundle must sit in, or None.

    Returns:
        The Story, the beads deleted, the edges moved, and a warning for each edge onto a deleted
        bead that no written Task replaces.

    Raises:
        TypeError: An argument violates the declared input contract.
        HierarchyError: The Epic has no Story for the repository.

    """
    dependent: Bead
    blocker: str
    target: str
    if not all((
        isinstance(graph, Graph),
        isinstance(writer, Writer),
        isinstance(epic_id, str),
        isinstance(files, StoryFiles),
        isinstance(root, Path) or root is None,
        isinstance(packages_dir, str) or packages_dir is None,
    )):
        raise TypeError(_ARGUMENT_ERROR)
    tasks: list[Task] = plan_tasks(files, root, packages_dir)
    take_warnings()
    story: Bead | None = _story_of(graph, epic_id, files.slug)
    if story is None:
        msg: str = f"{epic_id} has no Story story:{files.slug}"
        raise HierarchyError(msg)
    beads: list[Bead] = sorted(_children(graph, story.id, "task"), key=lambda bead: bead.id)
    matched: dict[str, Bead]
    left: list[Bead]
    matched, left = _match_tasks(tasks, beads, files.slug, story_builds(files.scope))
    cited: dict[str, set[str]] = {
        bead.id: set(_cited_ids(bead.metadata.get(KEY_REQUIREMENT_IDS))) for bead in left if not task_started(bead)
    }
    builds: dict[str, set[str]] = {
        matched[task.key].id: set(task.requirement_ids) for task in tasks if task.key in matched
    }
    repointed: list[RepointedEdge] = []
    warnings: list[str] = []
    for dependent in sorted(graph.beads.values(), key=lambda bead: bead.id):
        if dependent.kind != "task" or dependent.parent == story.id:
            continue
        for blocker in [held for held in dependent.blockers if held in cited]:
            targets: list[str] = [bead for bead, items in builds.items() if items & cited[blocker]]
            if not targets:
                warnings.append(f"no written Task replaces {blocker}, which blocked {dependent.id}")
            for target in targets:
                if target not in dependent.blockers:
                    writer.bd(["dep", "add", dependent.id, target, "--type", "blocks"])
                repointed.append({"dependent": dependent.id, "deleted": blocker, "replacement": target})
    deleted: list[ReplacedTask] = [
        {
            "id": bead.id,
            "title": bead.title,
            "elabKey": str(bead.metadata.get(KEY_ELAB_KEY) or ""),
            "status": bead.status,
        }
        for bead in left
        if bead.id in cited
    ]
    if deleted:
        writer.bd(["delete", *(entry["id"] for entry in deleted), "--force"])
    return {
        "ok": True,
        "story": story.id,
        "deleted": deleted,
        "repointed": repointed,
        "warnings": warnings,
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {"deleted": len(deleted), "repointed": len(repointed), "warnings": len(warnings)},
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_started(bead: Bead) -> bool:
    """Deferred is an owner ruling; any build-lane fact protects existing work.

    Returns:
        The computed task started result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(bead, Bead)):
        raise TypeError(_ARGUMENT_ERROR)
    return bead.status not in {"open", "blocked"} or any(
        key in _BUILD_LANE_KEYS and bool(value) for key, value in bead.metadata.items()
    )
