"""Elaborate one ready Epic into architecture, Specs, Stories and scored Tasks."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict

import archstate
import beadgraph
import elaboration
import elaborationcontracts
import hierarchy
import storyedges
from elaborationcontracts import Finished, Refused, Released, Started
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.events import EventWriter
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.matrix import read_snapshot, snapshot
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tools import Tools
from orchestrator.flows import architecture, repo_scoping, spec_authoring, task_decomposition, task_edges, trd_authoring
from orchestrator.flows.elaboration_support import (
    PhaseRunner,
    done_rule,
    failed,
    lifecycle,
    parallel,
    record,
    repository_failure,
)
from orchestrator.flows.target_removal import remove

_ARGUMENT_ERROR: str = "Arguments violate the prd_to_spec input contract"


if TYPE_CHECKING:
    from collections.abc import Callable

    from orchestrator.core.handback import ArtifactReport


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
    result: JsonObject
    ranked: dict[str, JsonObject] = {}
    for result in results:
        failure: dict[str, JsonValue] = json_object(result.get("failure", {}))
        classification: str = str(failure.get("classification", ""))
        if classification in {"pipeline-code-defect", "setup"}:
            ranked.setdefault(classification, result)
        elif failure.get("cause") == "shutdown":
            ranked.setdefault("shutdown", result)
    return next((ranked[key] for key in ("pipeline-code-defect", "setup", "shutdown") if key in ranked), None)


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

    def __post_init__(self) -> None:
        self.state = {
            "owner": str(self.context.args.get("owner") or self.context.run_id),
            "done": False,
            "claimAttempted": False,
        }
        self.artifacts = {"dir": str(self.context.work), "epicId": self.context.bead, "phases": {}, "filing": {}}
        self.result = json_object({
            "ok": False,
            "stage": "input",
            "lifecycle": self.state,
            "repoSpan": [],
            "hierarchy": {"epic": self.context.args.get("epic", {}), "stories": [], "tasks": []},
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
            fatal: set[str] = {"setup", "pipeline-code-defect"}
            if prior.get("classification") in fatal and cleanup_failure.get("classification") not in fatal:
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
            reclaim=bool(self.context.args.get("reclaim")),
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
        arch: dict[str, JsonValue] = self.invoke.call("architecture", architecture.run, matrix_path=matrix)
        self.phases["architecture"] = arch
        if not arch.get("ok"):
            return _owner(arch)
        self.context.args.update({key: arch[key] for key in ("targetDir", "deltaDir", "architectureChange")})
        self.context.args["architectureSubject"] = arch["subject"]
        self.context.stage = "architecture"
        if matrix is None:
            message: str = "successful architecture phase requires a matrix snapshot"
            raise ValueError(message)
        delta: dict[str, JsonValue] = json_object(
            self.tools.portfolio(
                "architecture",
                archstate.delta_items,
                str(Path(check_type(arch["targetDir"], str)) / "delta"),
                matrix_snapshot=read_snapshot(matrix),
            ),
        )
        write_json(self.context.work / "delta-items.json", delta)
        self.context.args.update(
            deltaDir=arch["deltaDir"] if delta.get("deltaExists") else "",
            note=delta.get("note", ""),
        )
        return arch

    def _scope_and_trd(self, matrix: Path | None) -> tuple[JsonObject, JsonObject]:
        scope: dict[str, JsonValue]
        trd: dict[str, JsonValue]
        scope, trd = parallel(
            self.context,
            [
                lambda: self.invoke.call("repo-scoping", repo_scoping.run, matrix_path=matrix),
                lambda: self.invoke.call("trd-authoring", trd_authoring.run),
            ],
        )
        self.phases.update({"repo-scoping": scope, "trd-authoring": trd})
        if trd.get("ok"):
            self.artifacts["phases"]["trd"] = "reused" if trd.get("resumed") else "passed"
            if trd.get("filingPath") is not None:
                self.artifacts["filing"]["trd.md"] = check_type(trd["filingPath"], str)
        return scope, trd

    def _specs(self, repos: list[str]) -> list[_Repository]:
        row: _Repository
        spec: dict[str, JsonValue]
        slugs: dict[str, str] = check_type(
            self.tools.portfolio("spec-authoring", hierarchy.repo_slugs, repos),
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
                self.artifacts["phases"]["spec:" + row["slug"]] = "reused" if spec.get("resumed") else "passed"
        return rows

    def _spec_job(self, row: _Repository) -> Callable[[], JsonObject]:
        return lambda: self.invoke.call(
            "spec-authoring",
            spec_authoring.run,
            {
                "repoPath": row["repository"],
                "slug": row["slug"],
                "storyKey": row["storyKey"],
            },
        )

    def _task_job(self, row: _Repository) -> Callable[[], JsonObject]:
        design: dict[str, JsonValue] = json_object(self.context.args.get("designSystem", {}))
        return lambda: self.invoke.call(
            "task-decomposition",
            task_decomposition.run,
            {
                "repoPath": row["repository"],
                "slug": row["slug"],
                "story": row["spec"]["story"],
                "specPaths": row["spec"]["specPaths"],
                "scopingPath": str(self.context.work / "repo-scoping.json"),
                "itemsPath": str(self.context.work / "delta-items.json"),
                "uiPath": row["spec"].get("uiPath"),
                "packagesDir": design.get("packagesDir"),
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
            "epic": self.context.args.get("epic", {}),
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
            return failed("task-edges", exc, agent_started=_started(self.context))

    def _completion(self, rows: list[_Repository], repos: list[str]) -> JsonObject:
        records: list[dict[str, JsonValue]] = [json_object(row) for row in rows]
        critical: JsonObject | None = _critical([
            value for row in rows for value in (row["spec"], row.get("tasks", {}))
        ])
        if critical is not None:
            failure: dict[str, JsonValue] = repository_failure(records)
            original: dict[str, JsonValue] = json_object(critical["failure"])
            failure.update({key: value for key, value in original.items() if key != "repositories"})
            return {**critical, "failure": failure}
        complete: bool = not done_rule(records, True, [])["repositories"]
        edges: dict[str, JsonValue] = self._edges(repos, complete)
        self.phases["task-edges"] = edges
        if _critical([edges]) is not None:
            return edges
        self.result.update({key: edges[key] for key in ("closureEdges", "crossStoryDependencies") if key in edges})
        self.context.stage = "finish"
        self.runner.emit("phase", phase="finish", step="task-scores")
        finish: Finished = lifecycle(
            self.context,
            self.tools,
            "finish",
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
            return {"ok": False, "stage": "repositories-incomplete", "failure": repository_failure(records)}
        if not edges.get("ok"):
            return edges
        if not rule["done"]:
            return {
                "ok": False,
                "stage": "task-scores",
                "failure": {"stage": "task-scores", "cause": "other", "repositories": [], "unscored": unscored},
            }
        self._finish()
        return {"ok": True, "stage": "finish", "headline": "Architecture, Specs, Stories and scored Tasks are ready"}

    def _elaborate(self) -> JsonObject:
        scope: JsonObject
        trd: JsonObject
        value: dict[str, JsonValue]
        matrix: Path | None = snapshot(self.context, self.tools) if self.context.args.get("archPath") else None
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
        self.context.args["trdPath"] = trd["trdPath"]
        rows: list[_Repository] = self._specs(repos)
        self._tasks(rows)
        return self._completion(rows, repos)

    def _story_edges(self) -> storyedges.StoryEdges:
        repo: Path = Path(check_type(self.context.args["beadsRepoPath"], str))
        graph: beadgraph.Graph = self.tools.portfolio("finish", beadgraph.load, repo)
        writer: beadgraph.Writer = self.tools.portfolio("finish", beadgraph.Writer, repo)
        return self.tools.portfolio("finish", storyedges.story_edges, graph, writer)

    def _finish(self) -> None:
        story_edges: dict[str, JsonValue] = json_object(self.tools.operation("finish", self._story_edges))
        self.result["storyEdges"] = story_edges
        if story_edges.get("ok") is False:
            stage: str = "finish"
            raise self.tools.failure(stage, "other", dict(story_edges))
        finish: Finished = lifecycle(
            self.context,
            self.tools,
            "finish",
            elaboration.finish,
            owner=self.state["owner"],
            done=True,
            scope="epic-tasks",
        )
        self.state["finish"] = finish
        self.state["done"] = finish["summary"]["done"]
        if not self.state["done"]:
            stage = "task-scores"
            raise self.tools.failure(stage, "other", json_object(finish))
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
    args: dict[str, JsonValue] = context.args
    prd: dict[str, JsonValue] = json_object(args.get("prd", {}))
    if not context.bead or not args.get("beadsRepoPath") or not Path(check_type(prd.get("path", ""), str)).is_file():
        stage: str = "input"
        raise StepError(stage, "other", ("Epic, beadsRepoPath and readable PRD path are required",))
    context.work.mkdir(parents=True, exist_ok=True)
    args["archPath"] = args.get("archPath") or os.environ.get("ATW_ARCH_PATH", "")
    root: Path = Path(check_type(args.get("skillspokeRoot") or os.environ["SKILLSPOKE_ROOT"], str))
    store: ArtifactStore = ArtifactStore(load_artifactio(), root, context.work, context.bead, context.run_id)
    tools: Tools = Tools(context.work / "evidence")
    notes: list[JsonValue] = []
    output: EventWriter = EventWriter()

    def emit(event: str, **facts: JsonValue) -> None:
        if event in {"note", "verdict"}:
            notes.append({"event": event, **facts})
        output(event, **facts)

    runner: AgentRunner = AgentRunner(context, store, emit=emit)
    return _Elaboration(context, store, runner, tools).execute(notes)
