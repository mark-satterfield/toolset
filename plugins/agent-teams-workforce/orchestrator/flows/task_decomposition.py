"""Decompose one repository's specifications, preserving completed build work."""

from __future__ import annotations

import re
from pathlib import Path

from ..core.agents import AgentRunner
from ..core.artifacts import ArtifactStore
from ..core.io import write_json
from ..core.models import AgentStep, RunContext, StepError
from ..core.tools import Tools, env_path
from .task_state import replace, repoint, snapshot, task_facts


def task_inputs(work: Path, slug: str, *, ui: bool) -> tuple[str, ...]:
    names = [
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
    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        runner: AgentRunner,
        tools: Tools,
    ) -> None:
        self.context, self.store, self.runner, self.tools = (
            context,
            store,
            runner,
            tools,
        )
        self.work = context.work
        self.slug = str(context.args["slug"])
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.slug) or self.slug in {".", ".."}:
            raise StepError("input", "other", ("invalid Task artifact slug",))
        if not context.args.get("repoPath"):
            raise StepError("input", "other", ("repoPath is required",))
        self.repo = str(Path(context.args["repoPath"]).resolve())
        self.output = self.work / f"tasks-{self.slug}.json"
        self.facts = self.work / f"tasks-{self.slug}.context.json"
        self.items = self.work / f"tasks-{self.slug}.items.json"
        self.inputs = task_inputs(
            self.work, self.slug, ui=bool(context.args.get("uiPath"))
        )
        self.packages = context.args.get("packagesDir")
        self.warnings: list[str] = []

    def portfolio(self, function: str, *args: object, **kwargs: object) -> object:
        return self.tools.portfolio(
            "beadwrite", function, *args, stage="decompose", **kwargs
        )

    def record(self) -> None:
        try:
            self.store.accept(f"tasks:{self.slug}", self.inputs, (self.output,))
        except Exception as exc:
            raise self.tools.failure(
                "task-record", "other", {"error": repr(exc)}
            ) from exc

    def author(
        self,
        output: Path,
        inputs: tuple[str, ...],
        outcome: str,
        schema: str,
        *,
        corrective: bool = True,
    ) -> None:
        self.runner.run(
            AgentStep(
                stage="decompose" if corrective else "uncited-items",
                agent="task-decomposer",
                inputs=inputs,
                output=self.work / "candidates" / output.name,
                final=output,
                validate=self.runner.plugin
                / "skills/artifact-handoff/schemas"
                / schema,
                outcome=outcome,
                model="fable",
                effort="medium",
                add_dirs=(self.work, Path(self.repo)),
                corrective=corrective,
            )
        )

    def plan(self) -> dict:
        return self.portfolio(
            "plan_story_tasks",
            self.work,
            slug=self.slug,
            repo=self.repo,
            root=self.store.root,
            packages_dir=self.packages,
        )

    def correction(self, plan: dict) -> dict:
        gaps = self.work / f"tasks-{self.slug}.gaps.json"
        write_json(
            gaps,
            {
                "uncitedItems": plan["uncitedItems"],
                "unsized": plan["unsized"],
                "empty": not plan["tasks"],
            },
        )
        output = self.work / f"tasks-{self.slug}.correction.json"
        self.author(
            output,
            self.inputs + (str(self.output), str(self.items), str(gaps)),
            "Task and size corrections for the recorded coverage gaps.",
            "tasks-correction.schema.json",
            corrective=False,
        )
        merged = self.portfolio(
            "add_corrective_tasks", self.work, slug=self.slug, correction=output
        )
        self.record()
        after = self.plan()
        if not after["tasks"] or after["uncited"] or after["unsized"]:
            raise StepError(
                "decompose" if not after["tasks"] else "uncited-items",
                "other",
                (str(gaps), str(output), str(merged)),
            )
        return {
            "uncitedBefore": plan["uncited"],
            "uncitedAfter": after["uncited"],
            "unsizedBefore": plan["unsized"],
            "unsizedAfter": after["unsized"],
            **merged,
        }

    def write(self, plan: dict, *, missing_only: bool) -> tuple[list[dict], dict]:
        written = []
        edges = {"added": 0, "removed": 0, "standing": 0}
        for task in plan["tasks"]:

            def attempt() -> dict:
                writer = self.tools.portfolio(
                    "beadgraph",
                    "Writer",
                    env_path("ATW_CONTROL_REPO"),
                    stage="task-write",
                )
                return self.tools.portfolio(
                    "beadwrite",
                    "write_task",
                    writer,
                    self.context.bead,
                    self.work,
                    slug=self.slug,
                    repo=self.repo,
                    key=task["key"],
                    root=self.store.root,
                    packages_dir=self.packages,
                    missing_only=missing_only,
                    stage="task-write",
                )

            result = self.tools.operation("task-write", attempt)
            written.append(result["task"])
            self.warnings.extend(result["warnings"])
            for key in edges:
                edges[key] += result["edges"][key]
        return written, edges


def run(
    context: RunContext, store: ArtifactStore, runner: AgentRunner, tools: Tools
) -> dict:
    """The per-Story phase; the composite owns cross-Story edges and Task WSJF."""
    context.stage = "task-decomposition"
    flow = TaskDecomposition(context, store, runner, tools)
    graph, story, tasks = tools.operation(
        "input", lambda: snapshot(tools, context.bead, flow.slug)
    )
    fresh = flow.portfolio("tasks_inputs", flow.work, slug=flow.slug, root=store.root)
    unchanged = fresh["unchanged"] and store.reusable(flow.inputs, (flow.output,))
    facts = {
        "deleted": [],
        "kept": [task_facts(b) for b in tasks],
        "reason": "unchanged inputs",
    }
    if not unchanged:
        reason = context.args.get("upstreamChange") or str(
            fresh["changedInputs"] or "no current Task receipt"
        )
        facts = replace(tools, context.bead, flow.slug, flow.work, reason)
        graph, story, tasks = tools.operation(
            "input", lambda: snapshot(tools, context.bead, flow.slug)
        )
        write_json(
            flow.facts,
            {
                "existingTasks": facts["kept"],
                "otherEpicTasks": flow.portfolio(
                    "other_epic_tasks", graph, context.bead, flow.repo
                ),
                "repoPath": flow.repo,
                "slug": flow.slug,
            },
        )
        items = tools.portfolio(
            "hierarchy", "placed_items", flow.work, stage="decompose"
        )
        write_json(
            flow.items, {"items": [v for v in items.values() if v["slug"] == flow.slug]}
        )
        flow.author(
            flow.output,
            flow.inputs + (str(flow.facts), str(flow.items)),
            "Build activities, dependencies and sizes for this repository's placed items.",
            "tasks.schema.json",
        )
        flow.record()
    plan = flow.plan()
    coverage = {}
    if not plan["tasks"] or plan["uncited"] or plan["unsized"]:
        coverage = flow.correction(plan)
        plan = flow.plan()
    written, edges = flow.write(plan, missing_only=unchanged)
    flow.warnings.extend(repoint(tools, context.bead, flow.slug, flow.work))
    flow.warnings.extend(plan["warnings"])
    rerun = {
        "case": "unchanged"
        if unchanged
        else "replaced"
        if facts["deleted"] or facts["kept"]
        else "new",
        "reason": facts["reason"],
        "changedInputs": fresh["changedInputs"],
        "deleted": facts["deleted"],
        "kept": facts["kept"],
    }
    result = {
        "ok": True,
        "rerun": rerun,
        "repoPath": flow.repo,
        "story": {"id": story.id, "elabKey": f"story:{flow.slug}"},
        "tasks": written,
        "edges": edges,
        "coverage": coverage,
        "warnings": flow.warnings,
        "summary": {
            key: sum(t["action"] == key for t in written)
            for key in ("created", "updated", "unchanged")
        },
    }
    write_json(flow.work / f"tasks-{flow.slug}.written.json", result)
    (flow.work / f"tasks-{flow.slug}.replacement.json").unlink(missing_ok=True)
    return result
