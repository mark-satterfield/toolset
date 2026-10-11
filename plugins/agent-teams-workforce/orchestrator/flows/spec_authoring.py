"""One repository's specifications and idempotent Story container.

The composite calls run concurrently for each span repository. Required args are
repoPath, slug, storyKey, prd (path/title), archPath and targetDir. Placement and
frontend come from the saved repo-scoping artifact. designSystem is optional.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
import beadgraph
import beadwrite
import cdsbundles
import specui
from driver_surface_types import CONTROL_REPO_ENV
from placement_contract import (
    KEY_FRONTEND,
    KEY_ITEM_IDS,
    KEY_PLACEMENTS,
    KEY_REPO_PATH,
    Placement,
    PlacementRuling,
    parse_placement_ruling,
)
from recon_contract import KEY_MOCKS_DIR
from target_contract import (
    DELTA_ITEMS_FILE,
    KEY_ARCHITECTURE_CHANGE,
    KEY_DELTA_DIR,
    KEY_ELEMENT,
    KEY_ID,
    KEY_ITEMS,
    KEY_TARGET_DIR,
    DeltaItem,
    DeltaResult,
    load_delta_report,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner, strict_json
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.driver_contracts import DispatchArgumentsContract, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext, StepError
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.spec_authoring_ui import normalize_ui
from orchestrator.flows.trd_authoring import document

_ARGUMENT_ERROR: str = "Arguments violate the spec_authoring input contract"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def nonempty(path: Path) -> None:
    """Require a nonempty authored document.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: The document contains no text.

    """
    if not (isinstance(path, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    if not path.read_text(encoding="utf-8").strip():
        message: str = f"missing or empty document: {path}"
        raise ValueError(message)


@dataclass(frozen=True)
class SpecRequest:
    """One specification author request and its validator."""

    agent: str
    output: Path
    inputs: tuple[str, ...]
    outcome: str
    validate: Path | Callable[[Path], tuple[list[str], list[str]] | None]
    model: str = "sonnet"
    effort: str = "medium"

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate the request fields before dispatch."""
        check_type(self.agent, str)
        check_type(self.output, Path)
        check_type(self.inputs, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.outcome, str)
        check_type(self.validate, Path | Callable[[Path], tuple[list[str], list[str]] | None])
        check_type(self.model, str)
        check_type(self.effort, str)


class SpecAuthoring:
    """Per-repository state; safe to use alongside other repository flow instances."""

    context: RunContext
    store: ArtifactStore
    runner: AgentRunner
    tools: Tools
    dispatch: DispatchArgumentsContract
    work: Path
    slug: str
    repo: Path
    arch: Path
    prd: Path
    stage: str
    ran: bool
    items: list[DeltaItem]
    frontend: bool
    design: dict[str, JsonValue]
    inputs: tuple[str, ...]
    docs: tuple[Path, Path, Path]
    ui: Path
    bundles: Path
    story: Path
    facts: Path

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        runner: AgentRunner,
        tools: Tools,
    ) -> None:
        """Bind the placed items and specification artifact paths.

        Raises:
            TypeError: An argument violates the declared input contract.
            StepError: The slug is invalid or no items are placed here.

        """
        args: dict[str, JsonValue]
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
        args, self.work = context.args, context.work
        self.dispatch = dispatch_arguments()
        self.slug = str(args["slug"])
        stage: str = "input"
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.slug) or self.slug in {".", ".."}:
            raise StepError(stage, OTHER_CAUSE, ("invalid repository artifact slug",))
        self.repo = Path(check_type(args["repoPath"], str)).resolve()
        self.arch = Path(check_type(args[self.dispatch.KEY_ARCH_PATH], str)).resolve()
        self.prd = Path(
            check_type(json_object(args[self.dispatch.KEY_PRD])[self.dispatch.PRD_PATH], str),
        ).resolve()
        self.stage = f"spec:{self.slug}"
        self.warnings: list[str] = []
        self.ran = False
        ruling: PlacementRuling = parse_placement_ruling(strict_json(self.work / "repo-scoping.json"))
        selected: list[Placement] = [
            p
            for p in ruling[KEY_PLACEMENTS]
            if (path := p[KEY_REPO_PATH]) is not None and Path(path).resolve() == self.repo
        ]
        ids: set[str] = {item for p in selected for item in p[KEY_ITEM_IDS]}
        delta: DeltaResult = load_delta_report(self.work / DELTA_ITEMS_FILE)
        self.items = [item for item in delta.get(KEY_ITEMS, []) if item[KEY_ID] in ids]
        if not self.items:
            raise StepError(stage, OTHER_CAUSE, (f"no placed items for {self.repo}",))
        self.frontend = any(p[KEY_FRONTEND] for p in selected)
        self.design = json_object(args.get(self.dispatch.KEY_DESIGN_SYSTEM) or {})
        self.inputs = tuple(
            map(
                str,
                (
                    self.work / "trd.md",
                    self.work / "repo-scoping.json",
                    self.work / DELTA_ITEMS_FILE,
                    self.prd,
                    Path(check_type(args[KEY_TARGET_DIR], str)),
                ),
            ),
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

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def record(self, inputs: tuple[str, ...], outputs: tuple[Path, ...]) -> None:
        """Record artifact receipts; a receipt write failure is raised, never downgraded.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        output: Path
        if not (isinstance(inputs, tuple)) or not (isinstance(outputs, tuple)):
            raise TypeError(_ARGUMENT_ERROR)
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

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def author(self, request: SpecRequest) -> None:
        """Run one specification author against its declared contract."""
        if self.store.reusable(request.inputs, (request.output,)):
            return
        self.ran = True
        self.runner.run(
            AgentStep(
                stage=f"{self.stage}:{request.output.name}",
                agent=request.agent,
                inputs=(*request.inputs, str(self.facts)),
                output=request.output,
                final=None,
                validate=request.validate,
                outcome=request.outcome,
                model=request.model,
                effort=request.effort,
                add_dirs=(self.work, self.arch, self.prd.parent, self.repo),
            ),
        )
        self.record(request.inputs, (request.output,))

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def ui_sources(self) -> None:
        """Normalize UI source selections against supplied bundles."""
        if self.store.reusable((*self.inputs, str(self.bundles)), (self.ui,)):
            return
        listed: dict[str, JsonValue] = json_object(
            self.tools.portfolio(
                "author",
                cdsbundles.list_bundles,
                check_type(self.design.get(self.dispatch.DS_PACKAGES_DIR), str | None),
            ),
        )
        write_json(self.bundles, listed)
        candidate: Path = self.work / "candidates" / self.ui.name
        inputs: tuple[str, ...] = (*self.inputs, str(self.bundles))
        self.author(
            SpecRequest(
                "api-specification-author",
                candidate,
                inputs,
                "UI design sources for this repository's placed items.",
                self.runner.plugin / "skills/artifact-handoff/schemas/spec-ui.schema.json",
            ),
        )
        normalized: dict[str, JsonValue] = normalize_ui(
            strict_json(candidate),
            {i[KEY_ID] for i in self.items},
            listed,
            self.tools,
        )
        normalized[KEY_MOCKS_DIR] = self.design.get(self.dispatch.DS_MOCKS_DIR)
        write_json(self.ui, normalized)
        self.warnings.extend(
            check_type(normalized["warnings"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS),
        )
        self.record(inputs, (self.ui,))

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def documents(self) -> None:
        """Produce repository specification documents."""
        future: Future[None]
        write_json(
            self.facts,
            {
                "repoPath": str(self.repo),
                "slug": self.slug,
                "frontend": self.frontend,
                "items": self.items,
                KEY_ARCHITECTURE_CHANGE: self.context.args.get(KEY_ARCHITECTURE_CHANGE),
                KEY_TARGET_DIR: self.context.args[KEY_TARGET_DIR],
                KEY_DELTA_DIR: self.context.args.get(KEY_DELTA_DIR),
                self.dispatch.KEY_DESIGN_SYSTEM: self.design,
            },
        )
        pool: ThreadPoolExecutor
        if self.frontend:
            self.ui_sources()
        contract_inputs: tuple[str, ...] = self.inputs + ((str(self.ui),) if self.frontend else ())
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures: list[Future[None]] = [
                pool.submit(
                    self.author,
                    SpecRequest(
                        "api-specification-author",
                        self.docs[0],
                        contract_inputs,
                        "API, event and error contracts for this repository's placed items.",
                        lambda path: document(path, self.arch),
                    ),
                ),
                pool.submit(
                    self.author,
                    SpecRequest(
                        "data-model-specification-author",
                        self.docs[1],
                        self.inputs,
                        "Data model specification for this repository's placed items.",
                        lambda path: document(path, self.arch),
                        model="fable",
                    ),
                ),
            ]
            for future in futures:
                future.result()
        if self.frontend:
            self.tools.portfolio("author", specui.spec_ui_append, self.docs[0], self.ui)
            self.record(contract_inputs, (self.docs[0],))
        criteria_inputs: tuple[str, ...] = self.inputs + tuple(map(str, self.docs[:2]))
        self.author(
            SpecRequest(
                "acceptance-criteria-writer",
                self.docs[2],
                criteria_inputs,
                "Acceptance criteria and definition of done for the saved specifications.",
                nonempty,
                effort="low",
            ),
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def story_document(self) -> dict[str, JsonValue]:
        """Read or construct the Story document.

        Returns:
            The validated specification result.

        """
        inputs: tuple[str, ...] = tuple(map(str, self.docs))
        if not self.store.reusable(inputs, (self.story,)):
            ids: list[str] = list(
                dict.fromkeys(
                    value.strip() for path in self.docs[:2] for value in document(path, self.arch)[0] if value.strip()
                ),
            )
            prd: dict[str, JsonValue] = json_object(self.context.args[self.dispatch.KEY_PRD])
            body: dict[str, Sequence[str]] = {
                "title": f"{self.repo.name}: {prd.get(self.dispatch.PRD_TITLE) or self.context.bead}",
                "description": "\n".join(
                    [
                        f"Repository: {self.repo}",
                        "",
                        "Placed items:",
                        *(f"- {item[KEY_ID]}: {item[KEY_ELEMENT]}" for item in self.items),
                        "",
                        "Specifications:",
                        *(f"- {path}" for path in self.docs),
                    ],
                ),
                "decisionIds": ids,
            }
            write_json(self.story, body)
            self.record(inputs, (self.story,))
        return strict_json(self.story)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def write_story(self) -> dict[str, JsonValue]:
        """Write the Story container through the portfolio boundary.

        Returns:
            The validated specification result.

        """
        control: Path = env_path(CONTROL_REPO_ENV)

        def attempt() -> dict[str, JsonValue]:
            graph: beadgraph.Graph = self.tools.portfolio("story-write", beadgraph.load, control, with_description=True)
            writer: beadgraph.Writer = self.tools.portfolio("story-write", beadgraph.Writer, control)
            return json_object(
                self.tools.portfolio(
                    "story-write",
                    beadwrite.write_story,
                    graph,
                    writer,
                    self.context.bead,
                    self.work,
                    slug=self.slug,
                    repo=str(self.repo),
                    root=self.store.root,
                ),
            )

        return self.tools.operation("story-write", attempt)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run(
    context: RunContext,
    store: ArtifactStore,
    runner: AgentRunner,
    tools: Tools,
) -> dict[str, JsonValue]:
    """Produce specifications and the Story for one repository.

    Returns:
        Story, specification paths, UI path, decision IDs, and write summary.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(context, RunContext))
        or not (isinstance(store, ArtifactStore))
        or not (isinstance(runner, AgentRunner))
        or not (isinstance(tools, Tools))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    flow: SpecAuthoring = SpecAuthoring(context, store, runner, tools)
    context.stage = "spec-authoring"
    flow.documents()
    body: dict[str, JsonValue] = flow.story_document()
    written: dict[str, JsonValue] = flow.write_story()
    if flow.ran:
        store.module.complete_step(context.work, flow.stage)
    return json_object({
        "ok": True,
        "story": {
            "key": context.args["storyKey"],
            "type": "story",
            "id": json_object(written["story"])["id"],
            "elabKey": json_object(written["story"])["elabKey"],
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
    })
