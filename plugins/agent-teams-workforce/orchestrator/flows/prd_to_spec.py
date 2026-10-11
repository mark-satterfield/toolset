"""Elaborate one ready Epic into architecture, Specs, Stories and scored Tasks."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict

# The driver-surface and target contracts are generated into their skills, their one definitions.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import archstate
import beadgraph
import elaboration
import elaborationcontracts
import hierarchy
import storyedges
from driver_surface_types import ARCH_PATH_ENV
from elaborationcontracts import Finished, Refused, Released, Started
from target_contract import (
    DELTA_FOLDER,
    DELTA_ITEMS_FILE,
    KEY_ARCHITECTURE_CHANGE,
    KEY_DELTA_DIR,
    KEY_DELTA_EXISTS,
    KEY_NOTE,
    KEY_SUBJECT,
    KEY_TARGET_DIR,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.events import EventWriter
from orchestrator.core.handback_contract import (
    DEFECT_CLASS,
    EVENT_KEY,
    FATAL_CLASSES,
    INTERRUPTED_CLASS,
    ITEM_CLASS,
    NOTE_EVENT,
    OTHER_CAUSE,
    PASSED_PHASE,
    REUSED_PHASE,
    SETUP_CLASS,
    SPEC_PHASE_PREFIX,
    TRD_PHASE,
    VERDICT_EVENT,
    ArtifactReport,
    EventName,
    Failure,
    phase_event,
)
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.matrix import read_snapshot, snapshot
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tools import Tools
from orchestrator.flows import architecture, repo_scoping, spec_authoring, task_decomposition, task_edges, trd_authoring
from orchestrator.flows.architecture_support import (
    ARCHITECTURE_PHASE,
    FINISH_PHASE,
    REPO_SCOPING_PHASE,
    SPEC_AUTHORING_PHASE,
    TASK_DECOMPOSITION_PHASE,
    TASK_EDGES_PHASE,
    TRD_AUTHORING_PHASE,
)
from orchestrator.flows.elaboration_support import (
    PhaseRunner,
    done_rule,
    emit_event,
    failed,
    lifecycle,
    parallel,
    record,
    repository_failure,
)
from orchestrator.flows.target_removal import remove

_ARGUMENT_ERROR: str = "Arguments violate the prd_to_spec input contract"
TASK_SCORES_STAGE: Final = "task-scores"


if TYPE_CHECKING:
    from collections.abc import Callable


LOGGER = logging.getLogger(__name__)


type JsonObject = dict[str, JsonValue]


class _Lifecycle(TypedDict):
    owner: str
    done: bool
    claimAttempted: bool
    start: NotRequired[Started | Refused]
    release: NotRequired[Released | JsonObject]
    finish: NotRequired[Finished]


class _Repository(TypedDict):
    repository: str
    slug: str
    storyKey: str
    spec: NotRequired[JsonObject]
    tasks: NotRequired[JsonObject]


def _started(context: RunContext) -> bool:
    return any(row.get("startedAt") is not None for row in context.sessions)


def _objects(value: JsonValue) -> list[JsonObject]:
    return check_type(value, list[JsonObject], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _strings(value: JsonValue) -> list[str]:
    return check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _critical(results: list[JsonObject]) -> JsonObject | None:
    """Pick the result that ends elaboration: a pipeline defect, then a setup failure, then a stop.

    Returns:
        The critical result, or ``None`` when every failure is an item or transient failure.

    """
    result: JsonObject
    ranked: dict[str, JsonObject] = {}
    for result in results:
        failure: dict[str, JsonValue] = json_object(result.get("failure", {}))
        classification: JsonValue = failure.get("classification")
        if isinstance(classification, str) and classification in FATAL_CLASSES | {INTERRUPTED_CLASS}:
            ranked.setdefault(classification, result)
    return next((ranked[key] for key in (DEFECT_CLASS, SETUP_CLASS, INTERRUPTED_CLASS) if key in ranked), None)


def _owner(result: JsonObject) -> JsonObject:
    actions: int | float | str | list[JsonValue] | dict[str, JsonValue] | None = result.get("requiredHumanActions")
    if actions and _critical([result]) is None:
        return {
            **result,
            "ok": False,
            "stage": "requires-human-action",
            "requiredHumanActions": actions,
            "headline": "Owner facts are required",
        }
    return result


@dataclass
class _Elaboration:
    context: RunContext
    store: ArtifactStore
    runner: AgentRunner
    tools: Tools
    phases: JsonObject = field(default_factory=dict)
    state: _Lifecycle = field(init=False)
    result: JsonObject = field(init=False)
    artifacts: ArtifactReport = field(init=False)
    invoke: PhaseRunner = field(init=False)
    dispatch: DispatchArguments = field(init=False)

    def __post_init__(self) -> None:
        self.dispatch = dispatch_arguments()
        self.state = {
            "owner": str(self.context.args.get(self.dispatch.KEY_OWNER) or self.context.run_id),
            "done": False,
            "claimAttempted": False,
        }
        self.artifacts = {"dir": str(self.context.work), "epicId": self.context.bead, "phases": {}, "filing": {}}
        self.result = json_object({
            "ok": False,
            "stage": "input",
            "lifecycle": self.state,
            "repoSpan": [],
            "hierarchy": {"epic": self.context.args.get(self.dispatch.KEY_EPIC, {}), "stories": [], "tasks": []},
            "beadsEmitted": 0,
            "lifecycleDone": False,
            "artifacts": self.artifacts,
            "targetRemoval": {"removed": False, "commit": None, "reason": "elaboration incomplete"},
        })
        self.invoke = PhaseRunner(self.context, self.store, self.runner, self.tools)

    def _release(self) -> None:
        if not self.state["claimAttempted"] or self.state["done"] or "release" in self.state:
            return
        try:
            self.state["release"] = lifecycle(
                self.context,
                self.tools,
                "release",
                elaboration.release,
                owner=self.state["owner"],
            )
        except Exception as exc:
            LOGGER.exception("Elaboration operation failed")
            release: dict[str, JsonValue] = failed("release", exc, agent_started=_started(self.context))
            self.state["release"] = release
            cleanup_failure: dict[str, JsonValue] = json_object(release["failure"])
            prior: dict[str, JsonValue] = json_object(self.result.get("failure") or {})
            prior_class: JsonValue = prior.get("classification")
            cleanup_class: JsonValue = cleanup_failure.get("classification")
            prior_fatal: bool = isinstance(prior_class, str) and prior_class in FATAL_CLASSES
            cleanup_fatal: bool = isinstance(cleanup_class, str) and cleanup_class in FATAL_CLASSES
            if prior_fatal and not cleanup_fatal:
                prior["originalFailure"] = {
                    "priorEvidence": prior.get("originalFailure"),
                    "releaseFailure": cleanup_failure,
                }
                self.result.update(ok=False, failure=prior)
            elif not self.result.get("ok"):
                cleanup_failure["originalFailure"] = json_object({
                    "stage": self.result.get("stage"),
                    "headline": self.result.get("headline"),
                    "failure": prior,
                })
                self.result.update(ok=False, failure=cleanup_failure)
            else:
                self.result.update(release)

    def _claim_and_elaborate(self) -> None:
        self.context.stage = "epic-lifecycle"
        self.state["claimAttempted"] = True
        start: elaborationcontracts.Started | elaborationcontracts.Refused = lifecycle(
            self.context,
            self.tools,
            "start",
            elaboration.start,
            owner=self.state["owner"],
            reclaim=bool(self.context.args.get(self.dispatch.KEY_RECLAIM)),
        )
        self.state["start"] = start
        if not start["ok"]:
            self.state["claimAttempted"] = False
            self.result.update(
                stage="epic-lifecycle",
                refusal=json_object(start["refusal"]),
                headline="Epic lifecycle refused elaboration",
            )
            return
        self.state["owner"] = start["owner"]
        self.result.update(self._elaborate())

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def execute(self, notes: list[JsonValue]) -> JsonObject:
        """Run elaboration while retaining lifecycle and diagnostic records.

        Returns:
            The recorded flow report.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(notes, list)):
            raise TypeError(_ARGUMENT_ERROR)
        self.context.cleanup.insert(0, self._release)
        try:
            self._claim_and_elaborate()
        except Exception as exc:
            LOGGER.exception("Elaboration operation failed")
            self.result.update(failed(self.context.stage, exc, agent_started=_started(self.context)))
        finally:
            self._release()
        self.result.setdefault(
            "headline",
            "Epic elaboration finished" if self.result["ok"] else "Epic elaboration incomplete",
        )
        self.result["lifecycleDone"] = self.state["done"]
        return record(self.context, json_object(self.result), self.phases, notes)

    def _architecture(self, matrix: Path | None) -> JsonObject:
        arch: dict[str, JsonValue] = self.invoke.call(ARCHITECTURE_PHASE, architecture.run, matrix_path=matrix)
        self.phases[ARCHITECTURE_PHASE] = arch
        if not arch.get("ok"):
            return _owner(arch)
        self.context.args.update({key: arch[key] for key in (KEY_TARGET_DIR, KEY_DELTA_DIR, KEY_ARCHITECTURE_CHANGE)})
        self.context.args["architectureSubject"] = arch[KEY_SUBJECT]
        self.context.stage = ARCHITECTURE_PHASE
        if matrix is None:
            message: str = "successful architecture phase requires a matrix snapshot"
            raise ValueError(message)
        delta: dict[str, JsonValue] = json_object(
            self.tools.portfolio(
                ARCHITECTURE_PHASE,
                archstate.delta_items,
                str(Path(check_type(arch[KEY_TARGET_DIR], str)) / DELTA_FOLDER),
                matrix_snapshot=read_snapshot(matrix),
            ),
        )
        write_json(self.context.work / DELTA_ITEMS_FILE, delta)
        self.context.args.update({
            KEY_DELTA_DIR: arch[KEY_DELTA_DIR] if delta.get(KEY_DELTA_EXISTS) else "",
            KEY_NOTE: delta.get(KEY_NOTE, ""),
        })
        return arch

    def _scope_and_trd(self, matrix: Path | None) -> tuple[JsonObject, JsonObject]:
        scope: dict[str, JsonValue]
        trd: dict[str, JsonValue]
        scope, trd = parallel(
            self.context,
            [
                lambda: self.invoke.call(REPO_SCOPING_PHASE, repo_scoping.run, matrix_path=matrix),
                lambda: self.invoke.call(TRD_AUTHORING_PHASE, trd_authoring.run),
            ],
        )
        self.phases.update({REPO_SCOPING_PHASE: scope, TRD_AUTHORING_PHASE: trd})
        if trd.get("ok"):
            self.artifacts["phases"][TRD_PHASE] = REUSED_PHASE if trd.get("resumed") else PASSED_PHASE
            if trd.get("filingPath") is not None:
                self.artifacts["filing"]["trd.md"] = check_type(trd["filingPath"], str)
        return scope, trd

    def _specs(self, repos: list[str]) -> list[_Repository]:
        row: _Repository
        spec: dict[str, JsonValue]
        slugs: dict[str, str] = check_type(
            self.tools.portfolio(SPEC_AUTHORING_PHASE, hierarchy.repo_slugs, repos),
            dict[str, str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        rows: list[_Repository] = [
            {"repository": repo, "slug": slug, "storyKey": f"S{index}"}
            for index, (repo, slug) in enumerate(slugs.items(), 1)
        ]
        specs: list[dict[str, JsonValue]] = parallel(self.context, [self._spec_job(row) for row in rows])
        for row, spec in zip(rows, specs, strict=True):
            row["spec"] = spec
            if spec.get("ok"):
                phase: str = SPEC_PHASE_PREFIX + row["slug"]
                self.artifacts["phases"][phase] = REUSED_PHASE if spec.get("resumed") else PASSED_PHASE
        return rows

    def _spec_job(self, row: _Repository) -> Callable[[], JsonObject]:
        return lambda: self.invoke.call(
            SPEC_AUTHORING_PHASE,
            spec_authoring.run,
            {
                "repoPath": row["repository"],
                "slug": row["slug"],
                "storyKey": row["storyKey"],
            },
        )

    def _task_job(self, row: _Repository) -> Callable[[], JsonObject]:
        design: dict[str, JsonValue] = json_object(self.context.args.get(self.dispatch.KEY_DESIGN_SYSTEM, {}))
        return lambda: self.invoke.call(
            TASK_DECOMPOSITION_PHASE,
            task_decomposition.run,
            {
                "repoPath": row["repository"],
                "slug": row["slug"],
                "story": row["spec"]["story"],
                "specPaths": row["spec"]["specPaths"],
                "scopingPath": str(self.context.work / "repo-scoping.json"),
                "itemsPath": str(self.context.work / DELTA_ITEMS_FILE),
                "uiPath": row["spec"].get("uiPath"),
                "packagesDir": design.get(self.dispatch.DS_PACKAGES_DIR),
            },
        )

    def _tasks(self, rows: list[_Repository]) -> None:
        row: _Repository
        tasks: dict[str, JsonValue]
        eligible: list[_Repository] = [row for row in rows if row["spec"].get("ok")]
        critical: JsonObject | None = _critical([row["spec"] for row in rows])
        decomposed: list[dict[str, JsonValue]] = (
            parallel(self.context, [self._task_job(row) for row in eligible]) if critical is None else []
        )
        for row, tasks in zip(eligible if critical is None else [], decomposed, strict=True):
            row["tasks"] = tasks
        self.phases["repositories"] = [json_object(row) for row in rows]
        stories: list[dict[str, JsonValue]] = [json_object(row["spec"]["story"]) for row in eligible]
        task_records: list[dict[str, JsonValue]] = [
            task for row in eligible for task in _objects(row.get("tasks", {}).get("tasks", []))
        ]
        self.result["hierarchy"] = json_object({
            "epic": self.context.args.get(self.dispatch.KEY_EPIC, {}),
            "stories": stories,
            "tasks": task_records,
        })
        self.result["beadsEmitted"] = len(stories) + len(task_records)

    def _edges(self, repos: list[str], complete: bool) -> JsonObject:
        if not complete:
            return {"ok": False}
        try:
            return task_edges.run(self.context, self.store, self.runner, self.tools, repos)
        except Exception as exc:
            LOGGER.exception("Elaboration operation failed")
            return failed(TASK_EDGES_PHASE, exc, agent_started=_started(self.context))

    def _completion(self, rows: list[_Repository], repos: list[str]) -> JsonObject:
        records: list[dict[str, JsonValue]] = [json_object(row) for row in rows]
        critical: JsonObject | None = _critical([
            value for row in rows for value in (row["spec"], row.get("tasks", {}))
        ])
        if critical is not None:
            failure: dict[str, JsonValue] = json_object(repository_failure(records))
            original: dict[str, JsonValue] = json_object(critical["failure"])
            failure.update({key: value for key, value in original.items() if key != "repositories"})
            return {**critical, "failure": failure}
        complete: bool = not done_rule(records, True, [])["repositories"]
        edges: dict[str, JsonValue] = self._edges(repos, complete)
        self.phases[TASK_EDGES_PHASE] = edges
        if _critical([edges]) is not None:
            return edges
        self.result.update({key: edges[key] for key in ("closureEdges", "crossStoryDependencies") if key in edges})
        self.context.stage = FINISH_PHASE
        emit_event(self.runner.emit, phase_event(FINISH_PHASE, TASK_SCORES_STAGE))
        finish: Finished = lifecycle(
            self.context,
            self.tools,
            FINISH_PHASE,
            elaboration.finish,
            owner=self.state["owner"],
            done=False,
            scope="epic-tasks",
        )
        self.state["finish"] = finish
        unscored: list[JsonValue] = check_type(
            json_object(finish["score"])["unscored"],
            list[JsonValue],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        rule: dict[str, JsonValue] = done_rule(records, bool(edges.get("ok")), unscored)
        self.phases["done-rule"] = rule
        if not complete:
            incomplete: Failure = repository_failure(records)
            return {"ok": False, "stage": incomplete["stage"], "failure": json_object(incomplete)}
        if not edges.get("ok"):
            return edges
        if not rule["done"]:
            unscored_failure: Failure = {
                "stage": TASK_SCORES_STAGE,
                "cause": OTHER_CAUSE,
                "classification": ITEM_CLASS,
                "repositories": [],
                "unscored": unscored,
            }
            return {"ok": False, "stage": unscored_failure["stage"], "failure": json_object(unscored_failure)}
        self._finish()
        return {
            "ok": True,
            "stage": FINISH_PHASE,
            "headline": "Architecture, Specs, Stories and scored Tasks are ready",
        }

    def _elaborate(self) -> JsonObject:
        scope: JsonObject
        trd: JsonObject
        value: dict[str, JsonValue]
        matrix: Path | None = (
            snapshot(self.context, self.tools) if self.context.args.get(self.dispatch.KEY_ARCH_PATH) else None
        )
        arch: dict[str, JsonValue] = self._architecture(matrix)
        if not arch.get("ok"):
            return arch
        scope, trd = self._scope_and_trd(matrix)
        critical: JsonObject | None = _critical([scope, trd])
        if critical is not None:
            return critical
        for value in (scope, trd):
            if not value.get("ok"):
                return _owner(value)
        repos: list[str] = _strings(scope["repos"])
        self.result["repoSpan"] = list(repos)
        self.result["createdRepos"] = scope.get("createdRepos", [])
        self.context.args[self.dispatch.KEY_TRD_PATH] = trd["trdPath"]
        rows: list[_Repository] = self._specs(repos)
        self._tasks(rows)
        return self._completion(rows, repos)

    def _story_edges(self) -> storyedges.StoryEdges:
        repo: Path = Path(check_type(self.context.args[self.dispatch.KEY_BEADS_REPO_PATH], str))
        graph: beadgraph.Graph = self.tools.portfolio(FINISH_PHASE, beadgraph.load, repo)
        writer: beadgraph.Writer = self.tools.portfolio(FINISH_PHASE, beadgraph.Writer, repo)
        return self.tools.portfolio(FINISH_PHASE, storyedges.story_edges, graph, writer)

    def _finish(self) -> None:
        story_edges: dict[str, JsonValue] = json_object(self.tools.operation(FINISH_PHASE, self._story_edges))
        self.result["storyEdges"] = story_edges
        if story_edges.get("ok") is False:
            stage: str = FINISH_PHASE
            raise self.tools.failure(stage, OTHER_CAUSE, dict(story_edges))
        finish: Finished = lifecycle(
            self.context,
            self.tools,
            FINISH_PHASE,
            elaboration.finish,
            owner=self.state["owner"],
            done=True,
            scope="epic-tasks",
        )
        self.state["finish"] = finish
        self.state["done"] = finish["summary"]["done"]
        if not self.state["done"]:
            stage = TASK_SCORES_STAGE
            raise self.tools.failure(stage, OTHER_CAUSE, json_object(finish))
        self.result["targetRemoval"] = remove(self.context, self.tools)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run(context: RunContext) -> JsonObject:
    """Own the lifecycle once; every phase owns its own saved-work decision.

    Returns:
        The detailed internal report, projected to the wire contract by run.py.

    Raises:
        TypeError: An argument violates the declared input contract.
        StepError: Required Epic, tracker or PRD configuration is absent.

    """
    if not (isinstance(context, RunContext)):
        raise TypeError(_ARGUMENT_ERROR)
    dispatch: DispatchArguments = dispatch_arguments()
    args: dict[str, JsonValue] = context.args
    prd: dict[str, JsonValue] = json_object(args.get(dispatch.KEY_PRD, {}))
    if (
        not context.bead
        or not args.get(dispatch.KEY_BEADS_REPO_PATH)
        or not Path(check_type(prd.get(dispatch.PRD_PATH, ""), str)).is_file()
    ):
        stage: str = "input"
        raise StepError(stage, OTHER_CAUSE, ("Epic, beadsRepoPath and readable PRD path are required",))
    context.work.mkdir(parents=True, exist_ok=True)
    args[dispatch.KEY_ARCH_PATH] = args.get(dispatch.KEY_ARCH_PATH) or os.environ.get(ARCH_PATH_ENV, "")
    root: Path = Path(check_type(args.get(dispatch.KEY_SKILLSPOKE_ROOT) or os.environ["SKILLSPOKE_ROOT"], str))
    store: ArtifactStore = ArtifactStore(load_artifactio(), root, context.work, context.bead, context.run_id)
    tools: Tools = Tools(context.work / "evidence")
    notes: list[JsonValue] = []
    output: EventWriter = EventWriter()

    def emit(event: EventName, **facts: JsonValue) -> None:
        if event in {NOTE_EVENT, VERDICT_EVENT}:
            notes.append({EVENT_KEY: event, **facts})
        output(event, **facts)

    runner: AgentRunner = AgentRunner(context, store, emit=emit)
    return _Elaboration(context, store, runner, tools).execute(notes)
