"""The buildability gate of an Epic's elaboration: whether every Task the Epic wrote can be built as planned.

The gate runs as the step ``elaboration.buildable`` between scoring and the done rule, and over
Epics already marked done from the owner's one-shot backfill (:func:`evaluate_epic`). It makes
five checks, each finding a defect of one kind (``bead_metadata.BuildabilityKind``) that takes one
route (``bead_metadata.DefectRoute``):

- ``cycle-edge-dropped`` (respec): an edge between Tasks of two Stories was dropped because it
  would close a cycle (``written.dropped`` of the edges result; the edge write's warnings for a
  journal written before the drops were recorded). Each of the two Stories gets a defect.
- ``design-gap-carried`` (escalate, architecture): a journal created before design gaps escalated
  carried gap rows to the build (``design_gaps.leftover_rows``).
- ``completion-cycle`` and ``producer-unordered`` (respec): the open Tasks' declared build
  prerequisites close a Task/Story completion cycle, or name a producer the wait graph refuses
  (``build_prerequisites.validate_wait_graph``); or a Task consumes an item another Epic's Task
  builds without being ordered after that Task.
- ``producer-absent`` (escalate, owner): a Task consumes a buildable item no Task of any Epic
  builds, that is not verified in code and that no other Epic's ``drives`` judgment claims.
- ``producer-epic-unordered`` (escalate, owner): the matrix orders another Epic before this one,
  that Epic is not done with elaboration, and no ``blocks`` or ``tracks`` edge orders it first.

The gate is pure: it reads its arguments and the files the journal's artifacts name, and writes
nothing. The step and the backfill write the report.
"""

from __future__ import annotations

import json
import os
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
import beadgraph
import buildowner
import epicorder
import matrixtasks
from bead_metadata import (
    DEFECT_COMPLETION_CYCLE,
    DEFECT_CYCLE_EDGE_DROPPED,
    DEFECT_DESIGN_GAP_CARRIED,
    DEFECT_PRODUCER_ABSENT,
    DEFECT_PRODUCER_EPIC_UNORDERED,
    DEFECT_PRODUCER_UNORDERED,
    ELABORATION_DONE,
    KEY_ADDS_TO_ENTRIES,
    KEY_BUILD_PREREQUISITES,
    KEY_BUILDS_ENTRIES,
    KEY_ELAB_KEY,
    KEY_ELABORATION_STATE,
    KEY_MATRIX_ELEMENTS,
    PARK_DECISION_ARCHITECTURE,
    PARK_DECISION_OWNER,
    ROUTE_ESCALATE,
    ROUTE_RESPEC,
    BuildabilityDefect,
    BuildabilityKind,
    BuildabilityReport,
)
from matrix_contract import REL_DRIVES
from matrixshared import shared_items
from matrixstore import Matrix, as_entry_id, kind_of, matrix_path, read_matrix
from matrixtraverse import epic_id as matrix_epic_id
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.io import JsonValue
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import LABEL_CONTEXT
from orchestrator.flows.build_prerequisites import WaitCycleError, prerequisites_for_record, validate_wait_graph
from orchestrator.flows.design_gaps import leftover_rows
from orchestrator.flows.elaboration_files import (
    CLOSURE_EDGES,
    CONTEXT,
    EDGES_RESULT,
    REPOSITORY,
    SPECS_CONTAINER,
    control_repository,
)

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import KIND_VALUE, STATUS_DONE, BeadId

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from matrix_contract import Entry, EntryId
    from matrixtasks import TaskBead
    from step_journal_contract import Artifact, Journal, Step

REPORT_FILE: Final = "buildability.json"
"""The file, in the Epic's work folder, the gate's report is written to."""
EDGES_FILE: Final[tuple[str, str]] = ("task-edges", "all.json")
"""The edge write's record in the Epic's work folder (``task_edges.write``), read when no edges result is held."""
CONTEXT_FILE: Final = "spec-{slug}.context.json"
"""A repository's context file in the Epic's work folder, read when the journal holds no context artifact."""
STORY_KEY: Final = "story:{slug}"
"""The elaboration key of a Story bead (``elab_key``)."""
_TASK_CYCLE: Final = re.compile(r"^edge (\S+) -> (\S+) would close a cycle over the Task graph; dropped$")
_STORY_CYCLE: Final = re.compile(
    r"^edge (\S+) -> (\S+) would make Story (\S+) and Story (\S+) depend on each other; dropped$",
)
_TASK_NAME: Final = re.compile(r"^S(\d+)-")
_REPOSITORY_SIDE: Final = "repository"
"""The side of a dependency read from code: a hint, never an architecture fact."""


@dataclass(frozen=True)
class _Span:
    """What the Epic's journal and work folder say about its repositories."""

    work: Path
    slugs: tuple[str, ...]
    """The repositories' slugs in span order; empty when the journal holds no repository container."""
    repositories: dict[str, str]
    """Repository path -> slug."""
    contexts: dict[str, Path]
    """Slug -> the repository's context file."""
    written: dict[str, JsonValue]
    """The edge write's record: ``written`` of the edges result; empty when there is none."""


@dataclass
class _Epic:
    """One Epic as the checks read it."""

    id: str
    graph: beadgraph.Graph
    span: _Span
    stories: dict[str, str]
    """Story slug -> Story bead id."""
    defects: list[BuildabilityDefect] = field(default_factory=list)

    def story_of_task(self, task: str) -> str | None:
        """Name the Story bead a Task bead is under.

        Returns:
            Its parent; None when the Task is not in the tracker.

        """
        held: beadgraph.Bead | None = self.graph.beads.get(task)
        return None if held is None else held.parent

    def open_tasks(self) -> list[beadgraph.Bead]:
        """List the Epic's open Task beads.

        Returns:
            Each Task under the Epic that is not closed, in id order.

        """
        return [bead for bead in self.graph.descendants(self.id) if bead.kind == "task" and not bead.closed]

    def add(self, kind: BuildabilityKind, story: str | None, tasks: Sequence[str], evidence: Sequence[str]) -> None:
        """Record one defect, with its route and, for an escalated one, who decides it."""
        defect: BuildabilityDefect = {
            "kind": kind,
            "route": ROUTE_RESPEC,
            "story": story,
            "tasks": list(tasks),
            "evidence": list(evidence),
        }
        if kind == DEFECT_DESIGN_GAP_CARRIED:
            defect |= {"route": ROUTE_ESCALATE, "decision": PARK_DECISION_ARCHITECTURE}
        elif kind in {DEFECT_PRODUCER_ABSENT, DEFECT_PRODUCER_EPIC_UNORDERED}:
            defect |= {"route": ROUTE_ESCALATE, "decision": PARK_DECISION_OWNER}
        self.defects.append(defect)


def _done_artifacts(journal: Journal) -> list[Artifact]:
    """List the artifacts of every done step of a journal, in walk order.

    Returns:
        The artifacts.

    """
    return [
        artifact
        for step in step_journal.steps_in_order(journal)
        if step["status"] == STATUS_DONE
        for artifact in step["artifacts"]
    ]


def _last_value(artifacts: Iterable[Artifact], name: str) -> JsonValue | None:
    """Read the last value artifact of a name.

    Returns:
        Its value; None when there is none.

    """
    found: list[JsonValue] = [
        artifact["value"] for artifact in artifacts if artifact["name"] == name and artifact["kind"] == KIND_VALUE
    ]
    return found[-1] if found else None


def _last_file(artifacts: Iterable[Artifact], name: str) -> Path | None:
    """Read the last file artifact of a name.

    Returns:
        Its path; None when there is none.

    """
    found: list[Path] = [
        Path(artifact["path"]) for artifact in artifacts if artifact["name"] == name and artifact["kind"] != KIND_VALUE
    ]
    return found[-1] if found else None


def _repository_containers(journal: Journal) -> list[list[Artifact]]:
    """List the artifacts of each repository container under the Specs and Stories step, in span order.

    Returns:
        One list per container that holds steps; empty when the journal has no such step.

    """
    outer: Step | None = next((step for step in journal["steps"] if step["description"] == SPECS_CONTAINER), None)
    if outer is None:
        return []
    return [
        [artifact for below in step_journal.steps_in_order_from(child) for artifact in below["artifacts"]]
        for child in outer["steps"]
        if child["steps"]
    ]


def _json_file(path: Path) -> dict[str, JsonValue]:
    """Read a JSON object file.

    Returns:
        Its content; empty when the file does not exist.

    """
    if not path.is_file():
        return {}
    return check_type(json.loads(path.read_text(encoding="utf-8")), dict[str, JsonValue])


def _span(journal: Journal, folder: Path) -> _Span:
    """Read the Epic's repositories, their context files and the edge write's record.

    Returns:
        What the journal records, with the work folder's files where the journal holds none.

    """
    artifacts: list[Artifact] = _done_artifacts(journal)
    slugs: list[str] = []
    repositories: dict[str, str] = {}
    contexts: dict[str, Path] = {}
    for held in _repository_containers(journal):
        value: JsonValue | None = _last_value(held, REPOSITORY)
        if not isinstance(value, dict) or not isinstance(value.get("slug"), str):
            continue
        slug: str = check_type(value["slug"], str)
        slugs.append(slug)
        repositories[str(value.get("repoPath"))] = slug
        context: Path | None = _last_file(held, CONTEXT)
        if context is not None:
            contexts[slug] = context
    result: JsonValue | None = _last_value(artifacts, EDGES_RESULT)
    written: dict[str, JsonValue] = (
        check_type(result.get("written", {}), dict[str, JsonValue])
        if isinstance(result, dict)
        else _json_file(folder.joinpath(*EDGES_FILE))
    )
    return _Span(folder, tuple(slugs), repositories, contexts, written)


def _stories(graph: beadgraph.Graph, epic: str) -> dict[str, str]:
    """Find each Story bead of the Epic by its elaboration key.

    Returns:
        Story slug -> Story bead id.

    """
    prefix: str = STORY_KEY.format(slug="")
    return {
        bead.metadata[KEY_ELAB_KEY].removeprefix(prefix): bead.id
        for bead in graph.descendants(epic)
        if bead.kind == "story" and bead.metadata.get(KEY_ELAB_KEY, "").startswith(prefix)
    }


def _dropped_edges(span: _Span) -> list[tuple[str, str, str]]:
    """List each edge dropped to break a cycle, with what says so.

    Returns:
        ``(from, to, evidence)`` by Task name: from ``dropped`` when the record holds it, else
        from the warnings of a record written before the drops were recorded.

    """
    dropped: JsonValue = span.written.get("dropped")
    if isinstance(dropped, list):
        return [
            (str(row["from"]), str(row["to"]), f"edge {row['from']} -> {row['to']} dropped: {row.get('reason')}")
            for row in check_type(dropped, list[dict[str, JsonValue]])
        ]
    edges: list[tuple[str, str, str]] = []
    for warning in check_type(span.written.get("warnings", []), list[str]):
        found: re.Match[str] | None = _TASK_CYCLE.match(warning) or _STORY_CYCLE.match(warning)
        if found is not None:
            edges.append((found.group(1), found.group(2), warning))
    return edges


def _cycle_edges(epic: _Epic) -> None:
    """Record each dropped cycle edge as a defect of both its Stories (``cycle-edge-dropped``)."""
    ids: dict[str, str] = {
        str(row.get("name")): str(row["id"])
        for row in check_type(epic.span.written.get("tasks", []), list[dict[str, JsonValue]])
        if row.get("id")
    }

    def story(name: str) -> str | None:
        position: re.Match[str] | None = _TASK_NAME.match(name)
        index: int = int(position.group(1)) - 1 if position else -1
        if 0 <= index < len(epic.span.slugs):
            return epic.stories.get(epic.span.slugs[index])
        return epic.story_of_task(ids[name]) if name in ids else None

    for frm, to, evidence in _dropped_edges(epic.span):
        tasks: list[str] = [ids.get(frm, frm), ids.get(to, to)]
        for owner in dict.fromkeys((story(frm), story(to))):
            epic.add(DEFECT_CYCLE_EDGE_DROPPED, owner, tasks, [evidence])


def _carried_gaps(epic: _Epic) -> None:
    """Record each repository whose gap rows an earlier journal carried to the build (``design-gap-carried``)."""
    rows: dict[str, list[str]] = {}
    for repository, row in leftover_rows(epic.span.work):
        rows.setdefault(repository, []).append(row)
    for repository, held in rows.items():
        slug: str = epic.span.repositories.get(repository, Path(repository).name)
        epic.add(DEFECT_DESIGN_GAP_CARRIED, epic.stories.get(slug), [], held)


def _cycle_owners(epic: _Epic, cycle: Sequence[str], error: WaitCycleError) -> None:
    """Record a completion cycle as a defect of each Story of the Epic that owns an open Task in it."""
    open_ids: set[str] = {bead.id for bead in epic.open_tasks()}
    owned: dict[str, list[str]] = {}
    for task in dict.fromkeys(cycle):
        story: str | None = epic.story_of_task(task)
        if task in open_ids and story is not None:
            owned.setdefault(story, []).append(task)
    for story, tasks in owned.items():
        epic.add(DEFECT_COMPLETION_CYCLE, story, sorted(tasks), [str(error)])


def _wait_graph(epic: _Epic) -> None:
    """Check the open Tasks' declared build prerequisites against the wait graph.

    Each Task's wait is checked alone, so a refused producer names its consumer; the waits that
    pass are then checked together for a cycle only several of them close.
    """
    records: dict[str, dict[str, JsonValue]] = {str(row.get("id")): row for row in epic.graph.records}
    waits: list[JsonValue] = []
    for task in epic.open_tasks():
        try:
            producers: list[dict[str, JsonValue]] = prerequisites_for_record(records.get(task.id, {"id": task.id}))
            if not producers:
                continue
            wait: dict[str, JsonValue] = {
                "task": task.id,
                "evidencePath": "",
                "fingerprint": "",
                "producers": list(producers),
            }
            validate_wait_graph(epic.graph.records, [wait])
        except WaitCycleError as error:
            _cycle_owners(epic, error.cycle, error)
            continue
        except (ValueError, StepError) as error:
            epic.add(DEFECT_PRODUCER_UNORDERED, task.parent, [task.id], [str(error)])
            continue
        waits.append(wait)
    try:
        validate_wait_graph(epic.graph.records, waits)
    except WaitCycleError as error:
        _cycle_owners(epic, error.cycle, error)


def _listed(metadata: dict[str, str], key: str) -> list[str]:
    """Read a metadata key that holds a JSON array of strings.

    Returns:
        Its strings; empty when the key is absent or holds no array.

    """
    try:
        value: object = json.loads(metadata.get(key) or "[]")
    except ValueError:
        return []
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _cites(task: beadgraph.Bead, entry: str) -> bool:
    """Tell whether a Task works on an entry: it names it, builds it, or adds to it.

    Returns:
        True when ``matrix_elements``, ``builds_entries`` or ``adds_to_entries`` holds the entry.

    """
    keys: tuple[str, ...] = (KEY_MATRIX_ELEMENTS, KEY_BUILDS_ENTRIES, KEY_ADDS_TO_ENTRIES)
    return any(entry in _listed(task.metadata, key) for key in keys)


def _reaches(graph: beadgraph.Graph, start: str, goal: str) -> bool:
    """Tell whether following blockers from one bead reaches another.

    Returns:
        True when ``goal`` is ``start`` or is reached through ``blockers``.

    """
    seen: set[str] = {start}
    pending: deque[str] = deque([start])
    while pending:
        node: str = pending.popleft()
        if node == goal:
            return True
        held: beadgraph.Bead | None = graph.beads.get(node)
        fresh: set[str] = set(() if held is None else held.blockers) - seen
        seen |= fresh
        pending.extend(sorted(fresh))
    return False


def _buildable(entry: str) -> bool:
    """Tell whether an entry is of a kind a Task builds.

    Returns:
        True for a kind ``matrixtasks.FALLBACK_BUILT_KINDS`` names (a service is never one Task's to
        build); False for any other, or an id with no kind.

    """
    try:
        return kind_of(as_entry_id(entry)) in matrixtasks.FALLBACK_BUILT_KINDS
    except ValueError:
        return False


def _claimed(matrix: Matrix, entry: EntryId, epic: str) -> bool:
    """Tell whether another Epic's ``drives`` judgment claims an entry.

    Returns:
        True when a ``drives`` relationship ends at the entry from another Epic's entry.

    """
    own: EntryId = matrix_epic_id(epic)
    return any(held.start != own for held in matrix.incoming(entry, (REL_DRIVES,)))


@dataclass(frozen=True)
class _Consumed:
    """One dependency of a Story on something no Story of the Epic builds."""

    story: str
    source: str
    target: str
    row: str


def _consumed(epic: _Epic) -> list[_Consumed]:
    """List each architecture dependency of each Story that no Story of the Epic builds.

    Returns:
        One row per ``dependsOn`` row of a context file whose ``builtBy`` is null and whose side
        is not the repository side, for a Story the Epic holds.

    """
    found: list[_Consumed] = []
    for slug, story in sorted(epic.stories.items()):
        path: Path = epic.span.contexts.get(slug, epic.span.work / CONTEXT_FILE.format(slug=slug))
        rows: list[dict[str, JsonValue]] = check_type(
            _json_file(path).get("dependsOn", []),
            list[dict[str, JsonValue]],
        )
        found.extend(
            _Consumed(story, str(row["from"]), str(row["to"]), json.dumps(row, sort_keys=True))
            for row in rows
            if row.get("builtBy") is None and row.get("side") != _REPOSITORY_SIDE
        )
    return found


def _declared(task: beadgraph.Bead) -> set[str]:
    """Name the producer Tasks and Stories a Task's declared build prerequisites wait for.

    Returns:
        The ``task`` and ``story`` of each producer of ``build_prerequisites``; empty when none is declared.

    """
    try:
        declared: object = json.loads(task.metadata.get(KEY_BUILD_PREREQUISITES) or "{}")
    except ValueError:
        return set()
    producers: object = declared.get("producers") if isinstance(declared, dict) else None
    rows: list[object] = producers if isinstance(producers, list) else []
    return {str(row[end]) for row in rows if isinstance(row, dict) for end in ("task", "story") if row.get(end)}


def _ordered(epic: _Epic, consumer: beadgraph.Bead, owner: buildowner.Builder) -> bool:
    """Tell whether a producer Task is ordered before a consumer Task.

    Returns:
        True when the consumer reaches the producer through its blockers, or its declared build
        prerequisites wait for the producer Task or its Story.

    """
    return _reaches(epic.graph, consumer.id, owner.task) or bool({owner.task, owner.story or ""} & _declared(consumer))


def _absent(epic: _Epic, row: _Consumed, needs: dict[str, list[str]]) -> None:
    """Record a consumed item no Task of any Epic builds (``producer-absent``), naming the Epics that need it."""
    others: list[str] = [held for held in needs.get(row.target, []) if held != epic.id]
    evidence: str = f"no Task of any Epic builds {row.target}; Epics that need it: {', '.join(others) or 'none'}"
    epic.add(DEFECT_PRODUCER_ABSENT, row.story, [], [evidence, row.row])


def _producers(epic: _Epic, matrix: Matrix, tasks: Sequence[TaskBead]) -> None:
    """Check that every item a Story consumes from another Epic has a producer ordered before its consumers.

    A dependency whose item is verified in code needs no producer. One another Epic's Task builds
    needs that Task (the owner Task, ``buildowner.owner``) closed, or ordered before every open
    Task of the Story that works on the consuming item (:func:`_ordered`; ``producer-unordered``).
    An item of a kind Tasks build (``matrixtasks.FALLBACK_BUILT_KINDS``) that no Task of any Epic
    builds and no other Epic's ``drives`` judgment claims has no producer (``producer-absent``),
    with the Epics that need it as evidence; a claimed one is the Epic-order check's
    (:func:`_epic_order`).
    """
    index: buildowner.BuilderIndex = buildowner.builders(tasks)
    needs: dict[str, list[str]] = {item.id: sorted(item.needs) for item in shared_items(matrix)}
    for row in _consumed(epic):
        entry: EntryId | None = _entry_id(row.target)
        held: Entry | None = None if entry is None else matrix.find(entry)
        if entry is None or (held is not None and held.verified):
            continue
        builders: list[buildowner.Builder] = index.get(row.target, [])
        if not builders:
            if _buildable(row.target) and not _claimed(matrix, entry, epic.id):
                _absent(epic, row, needs)
            continue
        owner: buildowner.Builder | None = buildowner.owner([found for found in builders if found.epic != epic.id])
        producer: beadgraph.Bead | None = None if owner is None else epic.graph.beads.get(owner.task)
        if owner is None or producer is None or producer.closed:
            continue
        unordered: list[str] = [
            bead.id
            for bead in epic.open_tasks()
            if bead.parent == row.story and _cites(bead, row.source) and not _ordered(epic, bead, owner)
        ]
        if unordered:
            evidence: str = (
                f"{row.target} is built by {owner.task} (Epic {owner.epic}), ordered before none of {unordered}"
            )
            epic.add(DEFECT_PRODUCER_UNORDERED, row.story, [*unordered, owner.task], [evidence, row.row])


def _entry_id(value: str) -> EntryId | None:
    """Read an entry id.

    Returns:
        The id; None when the value is no entry id.

    """
    try:
        return as_entry_id(value)
    except ValueError:
        return None


def _epic_order(epic: _Epic, matrix: Matrix) -> None:
    """Check that each Epic the matrix orders before this one is done or ordered first (``producer-epic-unordered``)."""
    found: epicorder.Epic | None = epicorder.read_epics(matrix).get(epic.id)
    if found is None:
        return
    analysis: epicorder.Analysis = epicorder.analyse(matrix, found.release, (), None)
    own: beadgraph.Bead | None = epic.graph.beads.get(epic.id)
    ordered: set[str] = set() if own is None else {*own.blockers, *own.tracked}
    for (driver, waiter), items in analysis.order.raw.items():
        held: beadgraph.Bead | None = epic.graph.beads.get(driver)
        if waiter != epic.id or held is None or driver in ordered:
            continue
        if held.metadata.get(KEY_ELABORATION_STATE) == ELABORATION_DONE:
            continue
        epic.add(DEFECT_PRODUCER_EPIC_UNORDERED, None, [], [*items, driver])


def _deduplicated(defects: Iterable[BuildabilityDefect]) -> list[BuildabilityDefect]:
    """Keep the first defect of each kind, Story and Tasks.

    Returns:
        The defects, in the order found.

    """
    kept: dict[tuple[str, str | None, tuple[str, ...]], BuildabilityDefect] = {}
    for defect in defects:
        kept.setdefault((defect["kind"], defect["story"], tuple(defect["tasks"])), defect)
    return list(kept.values())


def _work_folder(epic: str, journal: Journal) -> Path:
    """Name the Epic's work folder from the files its journal records.

    Returns:
        The folder of the closure edges file; for a journal whose later steps were set back, the
        folder above the open-run step's context file (``architecture_files.context_path``).

    Raises:
        ValueError: The journal records neither file.

    """
    artifacts: list[Artifact] = _done_artifacts(journal)
    closure: Path | None = _last_file(artifacts, CLOSURE_EDGES)
    if closure is not None:
        return closure.parent
    context: Path | None = _last_file(artifacts, LABEL_CONTEXT)
    if context is not None:
        return context.parent.parent
    message: str = f"the journal of {epic} records neither a {CLOSURE_EDGES!r} nor a {LABEL_CONTEXT!r} file"
    raise ValueError(message)


def evaluate(
    epic: str,
    journal: Journal,
    graph: beadgraph.Graph,
    matrix: Matrix,
    tasks: Sequence[TaskBead],
) -> BuildabilityReport:
    """Evaluate whether an Epic's elaborated work can be built as planned.

    Args:
        epic: The Epic's bead id.
        journal: The Epic's elaboration journal.
        graph: The tracker graph.
        matrix: The matrix.
        tasks: Every Task bead (``matrixtasks.tasks_of``), for the builders of each entry.

    Returns:
        The report: buildable when no defect was found, and every defect, deduplicated.

    """
    checked: _Epic = _Epic(epic, graph, _span(journal, _work_folder(epic, journal)), _stories(graph, epic))
    _cycle_edges(checked)
    _carried_gaps(checked)
    _wait_graph(checked)
    _producers(checked, matrix, tasks)
    _epic_order(checked, matrix)
    defects: list[BuildabilityDefect] = _deduplicated(checked.defects)
    return {
        "epic": epic,
        "buildable": not defects,
        "at": beadgraph.now_iso(),
        "reportPath": str(checked.span.work / REPORT_FILE),
        "defects": defects,
    }


def evaluate_epic(epic: str, journals: Path) -> BuildabilityReport:
    """Evaluate one Epic from its journal, the tracker and the matrix, for the driver's backfill.

    Args:
        epic: The Epic's bead id.
        journals: The step journals' folder (``step_journal.journals_directory``).

    Returns:
        What :func:`evaluate` returns.

    """
    journal: Journal = step_journal.read_journal(step_journal.journal_path(journals, BeadId(epic)))
    graph: beadgraph.Graph = beadgraph.load(control_repository())
    matrix: Matrix = read_matrix(matrix_path(None, os.environ))
    return evaluate(epic, journal, graph, matrix, matrixtasks.tasks_of(graph))
