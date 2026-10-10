"""Decompose one repository's specifications, preserving completed build work."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar

import beadcontracts
import beadgraph
import beadwrite
import hierarchy
from beadcontracts import PlannedTask, TaskPlan
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext, StepError
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.task_state import replace, repoint, snapshot, task_facts

_ARGUMENT_ERROR: str = "Arguments violate the task_decomposition input contract"


P = ParamSpec("P")
R = TypeVar("R")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_inputs(work: Path, slug: str, *, ui: bool) -> tuple[str, ...]:
    """Collect the task inputs for one repository.

    Returns:
        The validated task result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(work, Path)) or not (isinstance(slug, str)) or not (isinstance(ui, bool)):
        raise TypeError(_ARGUMENT_ERROR)
    names: list[str] = [
        f"spec-{slug}.md",
        f"spec-{slug}.data-model.md",
        f"spec-{slug}.criteria.md",
        f"story-{slug}.json",
        "repo-scoping.json",
        "delta-items.json",
    ]
    if ui:
        names.append(f"spec-{slug}.ui.json")
    return tuple(str(work / name) for name in names)


class TaskDecomposition:
    """Author and preserve tasks for one repository Story."""

    context: RunContext
    store: ArtifactStore
    runner: AgentRunner
    tools: Tools
    work: Path
    slug: str
    repo: str
    output: Path
    facts: Path
    items: Path
    inputs: tuple[str, ...]
    packages: str | None

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        runner: AgentRunner,
        tools: Tools,
    ) -> None:
        """Bind one repository and its task artifact contracts.

        Raises:
            TypeError: An argument violates the declared input contract.
            StepError: The artifact slug or repository path is invalid.

        """
        if (
            not (isinstance(context, RunContext))
            or not (isinstance(store, ArtifactStore))
            or not (isinstance(runner, AgentRunner))
            or not (isinstance(tools, Tools))
        ):
            raise TypeError(_ARGUMENT_ERROR)
        self.context, self.store, self.runner, self.tools = (
            context,
            store,
            runner,
            tools,
        )
        self.work = context.work
        self.slug = str(context.args["slug"])
        stage: str = "input"
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.slug) or self.slug in {".", ".."}:
            raise StepError(stage, "other", ("invalid Task artifact slug",))
        if not context.args.get("repoPath"):
            raise StepError(stage, "other", ("repoPath is required",))
        self.repo = str(Path(check_type(context.args["repoPath"], str)).resolve())
        self.output = self.work / f"tasks-{self.slug}.json"
        self.facts = self.work / f"tasks-{self.slug}.context.json"
        self.items = self.work / f"tasks-{self.slug}.items.json"
        self.inputs = task_inputs(
            self.work,
            self.slug,
            ui=bool(context.args.get("uiPath")),
        )
        self.packages = check_type(context.args.get("packagesDir"), str | None)
        self.warnings: list[str] = []

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def portfolio(self, function: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
        """Dispatch a task portfolio operation.

        Returns:
            The validated task result.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (callable(function)):
            raise TypeError(_ARGUMENT_ERROR)
        return self.tools.portfolio(
            "decompose",
            function,
            *args,
            **kwargs,
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def record(self) -> None:
        """Record the accepted task output and its inputs.

        Raises:
            TypeCheckError: An artifact contract is invalid.

        """
        stage: str = "task-record"
        try:
            self.store.accept(f"tasks:{self.slug}", self.inputs, (self.output,))
        except TypeCheckError:
            raise
        except Exception as exc:
            raise self.tools.failure(
                stage,
                "other",
                {"error": repr(exc)},
            ) from exc

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def author(
        self,
        output: Path,
        inputs: tuple[str, ...],
        outcome: str,
        schema: str,
        *,
        corrective: bool = True,
    ) -> None:
        """Run task authoring against the requested schema.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if (
            not (isinstance(output, Path))
            or not (isinstance(inputs, tuple))
            or not (isinstance(outcome, str))
            or not (isinstance(schema, str))
            or not (isinstance(corrective, bool))
        ):
            raise TypeError(_ARGUMENT_ERROR)
        self.runner.run(
            AgentStep(
                stage="decompose" if corrective else "uncited-items",
                agent="task-decomposer",
                inputs=inputs,
                output=self.work / "candidates" / output.name,
                final=output,
                validate=self.runner.plugin / "skills/artifact-handoff/schemas" / schema,
                outcome=outcome,
                model="fable",
                effort="medium",
                add_dirs=(self.work, Path(self.repo)),
                corrective=corrective,
            ),
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def plan(self) -> TaskPlan:
        """Read the current task plan.

        Returns:
            The validated task result.

        """
        return self.portfolio(
            beadwrite.plan_story_tasks,
            self.work,
            slug=self.slug,
            repo=self.repo,
            root=self.store.root,
            packages_dir=self.packages,
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def correction(self, plan: TaskPlan) -> dict[str, JsonValue]:
        """Correct recorded task coverage and sizing gaps.

        Returns:
            The validated task result.

        Raises:
            TypeError: An argument violates the declared input contract.
            StepError: Coverage or sizing remains incomplete.

        """
        if not (isinstance(plan, dict)):
            raise TypeError(_ARGUMENT_ERROR)
        gaps: Path = self.work / f"tasks-{self.slug}.gaps.json"
        write_json(
            gaps,
            {
                "uncitedItems": plan["uncitedItems"],
                "unsized": list(plan["unsized"]),
                "empty": not plan["tasks"],
            },
        )
        output: Path = self.work / f"tasks-{self.slug}.correction.json"
        self.author(
            output,
            (*self.inputs, str(self.output), str(self.items), str(gaps)),
            "Task and size corrections for the recorded coverage gaps.",
            "tasks-correction.schema.json",
            corrective=False,
        )
        merged: dict[str, JsonValue] = json_object(
            self.portfolio(
                beadwrite.add_corrective_tasks,
                self.work,
                slug=self.slug,
                correction=output,
            ),
        )
        self.record()
        after: beadcontracts.TaskPlan = self.plan()
        if not after["tasks"] or after["uncited"] or after["unsized"]:
            stage: str = "decompose" if not after["tasks"] else "uncited-items"
            raise StepError(
                stage,
                "other",
                (str(gaps), str(output), str(merged)),
            )
        return {
            "uncitedBefore": list(plan["uncited"]),
            "uncitedAfter": list(after["uncited"]),
            "unsizedBefore": list(plan["unsized"]),
            "unsizedAfter": list(after["unsized"]),
            **merged,
        }

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def write(
        self,
        plan: TaskPlan,
        *,
        missing_only: bool,
    ) -> tuple[list[dict[str, JsonValue]], dict[str, int]]:
        """Write tasks and accumulate their measured dependency changes.

        Returns:
            The validated task result.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        task: PlannedTask
        key: str
        if not (isinstance(plan, dict)) or not (isinstance(missing_only, bool)):
            raise TypeError(_ARGUMENT_ERROR)
        written: list[dict[str, JsonValue]] = []
        edges: dict[str, int] = {"added": 0, "removed": 0, "standing": 0}
        for task in plan["tasks"]:

            def attempt(task: PlannedTask = task) -> dict[str, JsonValue]:
                writer: beadgraph.Writer = self.tools.portfolio(
                    "task-write",
                    beadgraph.Writer,
                    env_path("ATW_CONTROL_REPO"),
                )
                return json_object(
                    self.tools.portfolio(
                        "task-write",
                        beadwrite.write_task,
                        writer,
                        self.context.bead,
                        self.work,
                        slug=self.slug,
                        repo=self.repo,
                        key=task["key"],
                        root=self.store.root,
                        packages_dir=self.packages,
                        missing_only=missing_only,
                    ),
                )

            result: dict[str, JsonValue] = self.tools.operation("task-write", attempt)
            written.append(json_object(result["task"]))
            self.warnings.extend(
                check_type(result["warnings"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS),
            )
            for key in edges:
                edges[key] += check_type(json_object(result["edges"])[key], int)
        return written, edges


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run(
    context: RunContext,
    store: ArtifactStore,
    runner: AgentRunner,
    tools: Tools,
) -> dict[str, JsonValue]:
    """Decompose one Story while retaining completed build work.

    Returns:
        The recorded task, dependency, and replacement outcome.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    graph: beadgraph.Graph
    story: beadgraph.Bead
    tasks: list[beadgraph.Bead]
    written: list[dict[str, JsonValue]]
    edges: dict[str, int]
    if (
        not (isinstance(context, RunContext))
        or not (isinstance(store, ArtifactStore))
        or not (isinstance(runner, AgentRunner))
        or not (isinstance(tools, Tools))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    context.stage = "task-decomposition"
    flow: TaskDecomposition = TaskDecomposition(context, store, runner, tools)
    graph, story, tasks = tools.operation(
        "input",
        lambda: snapshot(tools, context.bead, flow.slug),
    )
    fresh: dict[str, JsonValue] = json_object(
        flow.portfolio(beadwrite.tasks_inputs, flow.work, slug=flow.slug, root=store.root),
    )
    unchanged: bool = check_type(fresh["unchanged"], bool) and store.reusable(flow.inputs, (flow.output,))
    facts: dict[str, JsonValue] = json_object({
        "deleted": [],
        "kept": [task_facts(b) for b in tasks],
        "reason": "unchanged inputs",
    })
    if not unchanged:
        reason: str = check_type(context.args.get("upstreamChange") or "", str) or str(
            fresh["changedInputs"] or "no current Task receipt",
        )
        facts = replace(tools, context.bead, flow.slug, flow.work, reason)
        graph, story, tasks = tools.operation(
            "input",
            lambda: snapshot(tools, context.bead, flow.slug),
        )
        write_json(
            flow.facts,
            {
                "existingTasks": facts["kept"],
                "otherEpicTasks": flow.portfolio(
                    beadwrite.other_epic_tasks,
                    graph,
                    context.bead,
                    flow.repo,
                ),
                "repoPath": flow.repo,
                "slug": flow.slug,
            },
        )
        items: dict[str, JsonValue] = json_object(
            tools.portfolio("decompose", hierarchy.placed_items, flow.work),
        )
        write_json(
            flow.items,
            {"items": [v for v in items.values() if json_object(v)["slug"] == flow.slug]},
        )
        flow.author(
            flow.output,
            (*flow.inputs, str(flow.facts), str(flow.items)),
            "Build activities, dependencies and sizes for this repository's placed items.",
            "tasks.schema.json",
        )
        flow.record()
    plan: beadcontracts.TaskPlan = flow.plan()
    coverage: dict[str, JsonValue] = {}
    if not plan["tasks"] or plan["uncited"] or plan["unsized"]:
        coverage = flow.correction(plan)
        plan = flow.plan()
    written, edges = flow.write(plan, missing_only=unchanged)
    flow.warnings.extend(repoint(tools, context.bead, flow.slug, flow.work))
    flow.warnings.extend(
        check_type(plan["warnings"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS),
    )
    rerun: dict[str, int | float | str | list[JsonValue] | dict[str, JsonValue] | None] = {
        "case": "unchanged" if unchanged else "replaced" if facts["deleted"] or facts["kept"] else "new",
        "reason": facts["reason"],
        "changedInputs": fresh["changedInputs"],
        "deleted": facts["deleted"],
        "kept": facts["kept"],
    }
    result: dict[str, JsonValue] = json_object({
        "ok": True,
        "rerun": rerun,
        "repoPath": flow.repo,
        "story": {"id": story.id, "elabKey": f"story:{flow.slug}"},
        "tasks": written,
        "edges": edges,
        "coverage": coverage,
        "warnings": flow.warnings,
        "summary": {key: sum(t["action"] == key for t in written) for key in ("created", "updated", "unchanged")},
    })
    write_json(flow.work / f"tasks-{flow.slug}.written.json", result)
    (flow.work / f"tasks-{flow.slug}.replacement.json").unlink(missing_ok=True)
    return result
