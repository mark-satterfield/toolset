"""One repository's specifications and idempotent Story container.

The composite calls run concurrently for each span repository. Required args are
repoPath, slug, storyKey, prd (path/title), archPath and targetDir. Placement and
frontend come from the saved repo-scoping artifact. designSystem is optional.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..core.agents import AgentRunner, strict_json
from ..core.artifacts import ArtifactStore
from ..core.io import write_json
from ..core.models import AgentStep, RunContext, StepError
from ..core.tools import Tools, env_path
from .spec_authoring_ui import normalize_ui
from .trd_authoring import document


def nonempty(path: Path) -> None:
    if not path.read_text(encoding="utf-8").strip():
        raise ValueError(f"missing or empty document: {path}")


class SpecAuthoring:
    """Per-repository state; safe to use alongside other repository flow instances."""

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
        args, self.work = context.args, context.work
        self.slug = str(args["slug"])
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.slug) or self.slug in {".", ".."}:
            raise StepError("input", "other", ("invalid repository artifact slug",))
        self.repo = Path(args["repoPath"]).resolve()
        self.arch = Path(args["archPath"]).resolve()
        self.prd = Path(args["prd"]["path"]).resolve()
        self.stage = f"spec:{self.slug}"
        self.warnings: list[str] = []
        self.ran = False
        placement = strict_json(self.work / "repo-scoping.json")["placements"]
        selected = [
            p
            for p in placement
            if p.get("repoPath") and Path(p["repoPath"]).resolve() == self.repo
        ]
        ids = {item for p in selected for item in p["itemIds"]}
        self.items = [
            item
            for item in strict_json(self.work / "delta-items.json")["items"]
            if item["id"] in ids
        ]
        if not self.items:
            raise StepError("input", "other", (f"no placed items for {self.repo}",))
        self.frontend = any(p.get("frontend", False) for p in selected)
        self.design = args.get("designSystem") or {}
        self.inputs = tuple(
            map(
                str,
                (
                    self.work / "trd.md",
                    self.work / "repo-scoping.json",
                    self.work / "delta-items.json",
                    self.prd,
                    Path(args["targetDir"]),
                ),
            )
        )
        self.docs = (
            self.work / f"spec-{self.slug}.md",
            self.work / f"spec-{self.slug}.data-model.md",
            self.work / f"spec-{self.slug}.criteria.md",
        )
        self.ui = self.work / f"spec-{self.slug}.ui.json"
        self.bundles = self.work / f"spec-{self.slug}.bundles.json"
        self.story = self.work / f"story-{self.slug}.json"
        self.facts = self.work / f"spec-{self.slug}.context.json"

    def record(self, inputs: tuple[str, ...], outputs: tuple[Path, ...]) -> None:
        try:
            self.store.invalidate(outputs)
            for output in outputs:
                self.store.module.record(
                    output,
                    epic=self.context.bead,
                    phase=self.stage,
                    inputs=list(inputs),
                    producer="python",
                    run_id=self.context.run_id,
                    root=self.store.root,
                )
        except Exception as exc:  # noqa: BLE001 - receipt failure is explicitly nonfatal
            self.warnings.append(f"artifact receipt: {type(exc).__name__}: {exc}")

    def author(
        self,
        agent: str,
        output: Path,
        inputs: tuple[str, ...],
        outcome: str,
        validate: Path | Callable[[Path], object],
        *,
        model: str = "sonnet",
        effort: str = "medium",
    ) -> None:
        if self.store.reusable(inputs, (output,)):
            return
        self.ran = True
        self.runner.run(
            AgentStep(
                stage=f"{self.stage}:{output.name}",
                receipt_required=False,
                agent=agent,
                inputs=inputs + (str(self.facts),),
                output=output,
                final=None,
                validate=validate,
                outcome=outcome,
                model=model,
                effort=effort,
                add_dirs=(self.work, self.arch, self.prd.parent, self.repo),
            )
        )
        self.record(inputs, (output,))

    def ui_sources(self) -> None:
        if self.store.reusable(self.inputs + (str(self.bundles),), (self.ui,)):
            return
        listed = self.tools.portfolio(
            "cdsbundles", "list_bundles", self.design.get("packagesDir"), stage="author"
        )
        write_json(self.bundles, listed)
        candidate = self.work / "candidates" / self.ui.name
        inputs = self.inputs + (str(self.bundles),)
        self.author(
            "api-specification-author",
            candidate,
            inputs,
            "UI design sources for this repository's placed items.",
            self.runner.plugin / "skills/artifact-handoff/schemas/spec-ui.schema.json",
        )
        normalized = normalize_ui(
            strict_json(candidate), {i["id"] for i in self.items}, listed, self.tools
        )
        normalized["mocksDir"] = self.design.get("mocksDir")
        write_json(self.ui, normalized)
        self.warnings.extend(normalized["warnings"])
        self.record(inputs, (self.ui,))

    def documents(self) -> None:
        write_json(
            self.facts,
            {
                "repoPath": str(self.repo),
                "slug": self.slug,
                "frontend": self.frontend,
                "items": self.items,
                "architectureChange": self.context.args.get("architectureChange"),
                "targetDir": self.context.args["targetDir"],
                "deltaDir": self.context.args.get("deltaDir"),
                "designSystem": self.design,
            },
        )
        if self.frontend:
            self.ui_sources()
        contract_inputs = self.inputs + ((str(self.ui),) if self.frontend else ())
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    self.author,
                    "api-specification-author",
                    self.docs[0],
                    contract_inputs,
                    "API, event and error contracts for this repository's placed items.",
                    lambda path: document(path, self.arch),
                ),
                pool.submit(
                    self.author,
                    "data-model-specification-author",
                    self.docs[1],
                    self.inputs,
                    "Data model specification for this repository's placed items.",
                    lambda path: document(path, self.arch),
                    model="fable",
                ),
            ]
            for future in futures:
                future.result()
        if self.frontend:
            ui = strict_json(self.ui)
            self.tools.portfolio(
                "specui",
                "spec_ui_append",
                self.docs[0],
                json.dumps(
                    [
                        {
                            "id": row["item"],
                            **{
                                k: row[k]
                                for k in ("designSource", "buildSpec", "sections")
                                if k in row
                            },
                        }
                        for row in ui["uiItems"]
                    ]
                ),
                stage="author",
            )
            self.record(contract_inputs, (self.docs[0],))
        criteria_inputs = self.inputs + tuple(map(str, self.docs[:2]))
        self.author(
            "acceptance-criteria-writer",
            self.docs[2],
            criteria_inputs,
            "Acceptance criteria and definition of done for the saved specifications.",
            nonempty,
            effort="low",
        )

    def story_document(self) -> dict:
        inputs = tuple(map(str, self.docs))
        if not self.store.reusable(inputs, (self.story,)):
            ids = list(
                dict.fromkeys(
                    value.strip()
                    for path in self.docs[:2]
                    for value in document(path, self.arch)[0]
                    if value.strip()
                )
            )
            body = {
                "title": f"{self.repo.name}: {self.context.args['prd'].get('title') or self.context.bead}",
                "description": "\n".join(
                    [
                        f"Repository: {self.repo}",
                        "",
                        "Placed items:",
                        *(f"- {item['id']}: {item['element']}" for item in self.items),
                        "",
                        "Specifications:",
                        *(f"- {path}" for path in self.docs),
                    ]
                ),
                "decisionIds": ids,
            }
            write_json(self.story, body)
            self.record(inputs, (self.story,))
        return strict_json(self.story)

    def write_story(self) -> dict:
        control = env_path("ATW_CONTROL_REPO")

        def attempt() -> dict:
            graph = self.tools.portfolio(
                "beadgraph", "load", control, with_description=True, stage="story-write"
            )
            writer = self.tools.portfolio(
                "beadgraph", "Writer", control, stage="story-write"
            )
            return self.tools.portfolio(
                "beadwrite",
                "write_story",
                graph,
                writer,
                self.context.bead,
                self.work,
                slug=self.slug,
                repo=str(self.repo),
                root=self.store.root,
                stage="story-write",
            )

        return self.tools.operation("story-write", attempt)


def run(
    context: RunContext, store: ArtifactStore, runner: AgentRunner, tools: Tools
) -> dict:
    """Return story/specPaths/uiPath/decisionIds/summary/resumed for the composite."""
    flow = SpecAuthoring(context, store, runner, tools)
    context.stage = "spec-authoring"
    flow.documents()
    body = flow.story_document()
    written = flow.write_story()
    if flow.ran:
        try:
            store.module.complete_step(context.work, flow.stage)
        except Exception as exc:  # noqa: BLE001 - final step receipt is nonfatal
            flow.warnings.append(f"step receipt: {type(exc).__name__}: {exc}")
    return {
        "ok": True,
        "story": {
            "key": context.args["storyKey"],
            "type": "story",
            "id": written["story"]["id"],
            "elabKey": written["story"]["elabKey"],
            "title": body["title"],
            "descriptionPath": f"{flow.story}#/description",
            "repoPath": str(flow.repo),
            "parentEpicKey": context.bead,
        },
        "specPaths": list(map(str, flow.docs)),
        "uiPath": str(flow.ui) if flow.frontend else None,
        "decisionIds": body["decisionIds"],
        "summary": written["summary"],
        "resumed": not flow.ran,
        "warnings": flow.warnings,
    }
