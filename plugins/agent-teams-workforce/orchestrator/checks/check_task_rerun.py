"""Bounded pure checks for Task reruns; no pipeline, tracker or agent is run."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import ParamSpec, Protocol, TypeVar, override, runtime_checkable
from unittest.mock import patch

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/beads-contract/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import beadwrite
from bead_metadata import (
    CDS_AUDIT_PASSED,
    KEY_BUILD_STOP_STAGE,
    KEY_CDS_AUDIT_VERDICT,
    KEY_ELAB_KEY,
    KEY_REQUIREMENT_IDS,
)
from beadgraph import Bead, Graph
from beadgraph import Writer as TrackerWriter
from orchestrator.checks.check_support import report, require
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.tools import Tools
from orchestrator.flows import task_state
from orchestrator.flows.task_decomposition import task_inputs
from placement_contract import (
    KEY_FRONTEND,
    KEY_ITEM_IDS,
    KEY_MISSING_REPOS,
    KEY_NO_CODE,
    KEY_PLACEMENTS,
    KEY_RATIONALE,
    KEY_REPO_NAME,
    KEY_REPO_PATH,
    KEY_SPAN_RATIONALE,
    PlacementRuling,
)
from target_contract import DELTA_ITEMS_FILE, DeltaItem, DeltaResult

P = ParamSpec("P")
R = TypeVar("R")

# The task decomposition output (tasks.schema.json) has no generated module yet, so its
# citation key is held here until that contract exports it.
TASK_REQUIREMENT_IDS: str = "requirementIds"


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@runtime_checkable
class SavedTask(Protocol):
    """Fields read from the portfolio task planner."""

    title: str
    elab_key: str
    key: str


class Writer(TrackerWriter):
    """Record requested tracker operations without executing them."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self, work: Path) -> None:
        """Bind the isolated repository and a fresh operation log."""
        super().__init__(work, False)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def bd(self, args: list[str], stdin: str | None = None) -> None:
        """Record a tracker operation."""
        require(stdin is None, "fixture does not expect stdin")
        self.planned.append({"op": "bd", "args": args})


class CreatingWriter(Writer):
    """Record task creation and return its deterministic fixture identifier."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def create(self, args: list[str], key: str) -> str:
        """Record one creation request.

        Returns:
            The created fixture task identifier.

        """
        require(bool(key), "creation must carry its idempotency key")
        self.planned.append({"op": "bd", "args": args})
        return "task-missing"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def save(path: Path, data: Mapping[str, object]) -> None:
    """Write one fixture document as JSON."""
    path.write_text(json.dumps(data), encoding="utf-8")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check() -> None:
    """Evaluate the existing isolated check contract."""
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        repo = str(work / "repo")
        _input_facts(work, repo)
        _preserve_tasks(work, repo)
        _journal(work)


def _input_facts(work: Path, repo: str) -> None:
    scoping: PlacementRuling = {
        KEY_PLACEMENTS: [
            {
                KEY_REPO_PATH: repo,
                KEY_REPO_NAME: "repo",
                KEY_ITEM_IDS: ["D1", "D2"],
                KEY_FRONTEND: False,
                KEY_RATIONALE: "The repository changes for both items.",
            },
        ],
        KEY_MISSING_REPOS: [],
        KEY_NO_CODE: [],
        KEY_SPAN_RATIONALE: "One repository carries the delta.",
    }
    save(work / "repo-scoping.json", scoping)
    items: list[DeltaItem] = [
        {"id": "D1", "element": "service", "views": ["05-building-blocks/service.md"], "requires": ["D2"]},
        {"id": "D2", "element": "layer", "views": ["05-building-blocks/layer.md"], "requires": []},
    ]
    delta: DeltaResult = {
        "ok": True,
        "refusals": [],
        "summary": {"ok": True, "refusals": [], "items": len(items)},
        "items": items,
    }
    save(work / DELTA_ITEMS_FILE, delta)
    save(
        work / "story-repo.json",
        {"title": "Story", "description": "Build", "decisionIds": []},
    )
    for name in [
        "spec-repo.md",
        "spec-repo.data-model.md",
        "spec-repo.criteria.md",
    ]:
        (work / name).write_text("Specification", encoding="utf-8")
    task: dict[str, JsonValue] = {
        "key": "T1",
        "title": "Build service",
        "description": "Implement service",
        TASK_REQUIREMENT_IDS: ["D1"],
    }
    score: dict[str, JsonValue] = {
        "key": "T1",
        "jobSize": 2,
        "sizeLow": 1,
        "sizeHigh": 3,
        "sizeConfidence": 80,
    }
    save(
        work / "tasks-repo.json",
        {"tasks": [task], "scores": [score], "edges": []},
    )
    inputs = task_inputs(work, "repo", ui=False)
    save(
        work / "tasks-repo.json.meta.json",
        {
            "inputs": [
                {
                    "path": path,
                    "kind": "file",
                    "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                }
                for path in inputs
            ],
        },
    )
    require(
        json_object(beadwrite.tasks_inputs(work, slug="repo", root=work))["unchanged"],
        "beadwrite.tasks_inputs(work, slug='repo', root=work)['unchanged']",
    )
    (work / "spec-repo.md").write_text("Changed specification", encoding="utf-8")
    require(
        not json_object(beadwrite.tasks_inputs(work, slug="repo", root=work))["unchanged"],
        "not beadwrite.tasks_inputs(work, slug='repo', root=work)['unchanged']",
    )
    planned = json_object(beadwrite.plan_story_tasks(work, slug="repo", repo=repo, root=work))
    require(planned["uncited"] == ["D2"], "planned['uncited'] == ['D2']")
    correction = work / "correction.json"
    save(
        correction,
        {
            "tasks": [
                {
                    **task,
                    "key": "N1",
                    "title": "Build layer",
                    TASK_REQUIREMENT_IDS: ["D2"],
                },
            ],
            "edges": [],
            "scores": [{**score, "key": "N1"}],
        },
    )
    beadwrite.add_corrective_tasks(work, slug="repo", correction=correction)
    planned = json_object(beadwrite.plan_story_tasks(work, slug="repo", repo=repo, root=work))
    require(not planned["uncited"], "not planned['uncited']")
    require(not planned["unsized"], "not planned['unsized']")
    require(_objects(planned["tasks"])[0]["key"] == "T2", "planned['tasks'][0]['key'] == 'T2'")
    report("PASS: input fingerprints and placed prerequisite coverage/correction")


def _preserve_tasks(work: Path, repo: str) -> None:
    story = {
        "id": "story",
        "title": "Story",
        "issue_type": "story",
        "status": "open",
        "metadata": {KEY_ELAB_KEY: "story:repo"},
    }
    records = []
    fixtures: list[tuple[str, str, dict[str, str]]] = [
        ("unstarted", "open", {}),
        ("blocked", "blocked", {}),
        ("started", "in_progress", {}),
        ("closed", "closed", {}),
        ("deferred", "deferred", {}),
        ("stopped", "open", {KEY_BUILD_STOP_STAGE: "red-unsatisfied"}),
        ("audited", "open", {KEY_CDS_AUDIT_VERDICT: CDS_AUDIT_PASSED}),
    ]
    for key, status, metadata in fixtures:
        records.append(
            {
                "id": key,
                "title": key,
                "issue_type": "task",
                "status": status,
                "metadata": {KEY_ELAB_KEY: f"task:repo:{key}", **metadata},
            },
        )

    writer = Writer(work)
    with patch.object(
        beadwrite,
        "children",
        side_effect=lambda _, _parent, kind: [story] if kind == "story" else records,
    ):
        result = json_object(
            beadwrite.replace_tasks(
                writer,
                "epic",
                slug="repo",
                reason="changed",
            ),
        )
    require(
        {x["id"] for x in _objects(result["deleted"])} == {"unstarted", "blocked"},
        "{x['id'] for x in result['deleted']} == {'unstarted', 'blocked'}",
    )
    require(
        {x["id"] for x in _objects(result["kept"])} == {"started", "closed", "deferred", "stopped", "audited"},
        "{x['id'] for x in result['kept']} == {'started', 'closed', 'deferred', 'stopped', 'audited'}",
    )
    report("PASS: changed inputs delete only unstarted; started/closed/deferred/build facts survive")

    saved = check_type(
        beadwrite.plan_tasks(work, None, "repo", repo),
        list[SavedTask],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    for planned_task in saved:
        for value in (planned_task.title, planned_task.elab_key, planned_task.key):
            check_type(value, str)
    existing = Bead(
        "task-existing",
        saved[0].title,
        "task",
        "open",
        "story",
        {KEY_ELAB_KEY: saved[0].elab_key},
        (),
    )
    writer.planned = []
    task_record = {
        "id": existing.id,
        "title": existing.title,
        "issue_type": "task",
        "status": "open",
        "metadata": existing.metadata,
    }
    with (
        patch.object(
            beadwrite,
            "children",
            side_effect=lambda _, _parent, kind: [story] if kind == "story" else [task_record],
        ),
        patch.object(
            beadwrite,
            "_refresh",
            side_effect=AssertionError("existing Task changed"),
        ),
    ):
        result = json_object(
            beadwrite.write_task(
                writer,
                "epic",
                work,
                slug="repo",
                repo=repo,
                key=saved[0].key,
                root=work,
                missing_only=True,
            ),
        )
    require(json_object(result["task"])["action"] == "unchanged", "result['task']['action'] == 'unchanged'")
    require(not writer.planned, "not writer.planned")

    writer = CreatingWriter(work)
    writer.planned = []
    with patch.object(
        beadwrite,
        "children",
        side_effect=lambda _, _parent, kind: [story] if kind == "story" else [task_record],
    ):
        result = json_object(
            beadwrite.write_task(
                writer,
                "epic",
                work,
                slug="repo",
                repo=repo,
                key=saved[1].key,
                root=work,
                missing_only=True,
            ),
        )
    require(json_object(result["task"])["action"] == "created", "result['task']['action'] == 'created'")
    require(len(writer.planned) == 1, "len(writer.planned) == 1")
    report("PASS: unchanged inputs preserve existing Tasks and create only missing Tasks")


class JournalTools(Tools):
    """Run portfolio operations in process and capture the one tracker edge write."""

    added: bool = False

    @override
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def operation[T](self, stage: str, action: Callable[[], T]) -> T:
        """Run the operation once without retry.

        Returns:
            The operation result.

        """
        return action()

    @override
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def portfolio(self, stage: str, operation: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
        """Call the actual portfolio function directly.

        Returns:
            The portfolio function result.

        """
        return operation(*args, **kwargs)

    @override
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def bd(self, args: list[str], *, stage: str, stdin: str | None = None) -> str:
        """Record the expected dependency re-point instead of running the tracker.

        Returns:
            Empty tracker output.

        """
        require(args == ["dep", "add", "outside", "new", "--type", "blocks"], "wrong dependency edge")
        self.added = True
        return ""


def _journal(work: Path) -> None:
    outgoing = Bead(
        "outside",
        "outside",
        "task",
        "open",
        "other-story",
        {},
        ("old",),
    )
    old = Bead(
        "old",
        "old",
        "task",
        "open",
        "story",
        {KEY_ELAB_KEY: "task:repo:old", KEY_REQUIREMENT_IDS: '["D1"]'},
        (),
    )
    new = Bead(
        "new",
        "new",
        "task",
        "open",
        "story",
        {KEY_ELAB_KEY: "task:repo:new", KEY_REQUIREMENT_IDS: '["D1"]'},
        (),
    )
    graph = Graph({"outside": outgoing, "old": old}, "fixture")

    tools = JournalTools(work / "evidence")
    with (
        patch.object(task_state, "env_path", return_value=work),
        patch.object(beadwrite, "replace_tasks", side_effect=lambda *_args, **_kwargs: graph.beads.pop("old", None)),
        patch.object(
            task_state,
            "snapshot",
            side_effect=lambda *_: (
                graph,
                Bead("story", "story", "story", "open", "epic", {}, ()),
                [b for b in graph.beads.values() if b.parent == "story"],
            ),
        ),
    ):
        first = task_state.replace(tools, "epic", "repo", work, "changed")
        resumed = task_state.replace(tools, "epic", "repo", work, "changed")
        require(first["incoming"] == resumed["incoming"], "first['incoming'] == resumed['incoming']")
        require(resumed["deleted"], "resumed['deleted']")
        graph.beads["new"] = new
        require(
            not task_state.repoint(tools, "epic", "repo", work),
            "not task_state.repoint(tools, 'epic', 'repo', work)",
        )
        require(tools.added, "tools.added")
    report("PASS: replacement journal survives interruption and re-points external blockers")


if __name__ == "__main__":
    check()
