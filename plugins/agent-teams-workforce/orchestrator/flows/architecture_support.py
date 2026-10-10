"""Architecture file contracts and direct step dispatch."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner, strict_json
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext
from orchestrator.core.tools import Tools

PROPOSERS = (
    "integration-pattern-architect",
    "persistence-architecture-specialist",
    "security-architecture-designer",
    "cdk-infrastructure-designer",
    "event-schema-designer",
    "api-contract-designer",
    "graphql-schema-designer",
    "domain-event-modeler",
    "bounded-context-mapper",
)
DIAGRAMS = ("architecture-diagram-author", "c4-diagram-author", "uml-diagram-author")
REVIEWERS = (
    "architecture-pattern-challenger",
    "architecture-tradeoff-skeptic",
    "architecture-boundary-guardian",
    "operational-readiness-reviewer",
    "failure-mode-analyst",
)
COST = ("cost-architecture-reviewer", "cost-impact-reviewer")
ROLES = {
    **dict.fromkeys(PROPOSERS, "proposer"),
    **dict.fromkeys(DIAGRAMS, "diagram"),
    **dict.fromkeys(REVIEWERS, "reviewer"),
    **dict.fromkeys(COST, "cost"),
}
ROSTER = ";".join(
    f"{role}={','.join(a for a, r in ROLES.items() if r == role)}"
    for role in ("proposer", "diagram", "reviewer", "cost")
)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def value_input(name: str, value: object) -> str:
    """Encode a validated JSON value as a stable artifact input.

    Returns:
        The validated result for this operation.

    """
    return "value:" + json.dumps(
        json_object({"name": name, "value": value}),
        sort_keys=True,
        separators=(",", ":"),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read(path: Path) -> dict[str, JsonValue]:
    """Read a present JSON artifact or return an empty object.

    Returns:
        The validated result for this operation.

    """
    return strict_json(path) if path.is_file() else {}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def model_for(agent: str) -> tuple[str, str]:
    """Choose the configured model and effort for an architecture role.

    Returns:
        The validated result for this operation.

    """
    if agent in PROPOSERS:
        return "fable", "high"
    if agent in {
        "architecture-pattern-challenger",
        "architecture-tradeoff-skeptic",
        "failure-mode-analyst",
    }:
        return "fable", "medium"
    if agent in {"prd-reality-reconciler", "operational-readiness-reviewer"}:
        return "opus", "medium"
    if agent == "architecture-decider":
        return "opus", "high"
    return "sonnet", "medium"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class ArchitectureStep:
    """One architecture agent request and its artifact contract."""

    agent: str
    output: Path
    schema: str
    inputs: tuple[str, ...]
    outcome: str
    stage: str | None = None

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        check_type(self.agent, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.output, Path, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.schema, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.inputs, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.outcome, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.stage, str | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


class Architecture:
    """Bind architecture flow state and its validated external contracts."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        runner: AgentRunner,
        tools: Tools,
        matrix: Path,
    ) -> None:
        """Bind architecture paths and write the shared agent context."""
        self.context, self.store, self.runner, self.tools = (
            context,
            store,
            runner,
            tools,
        )
        self.work = context.work / "architecture"
        self.work.mkdir(parents=True, exist_ok=True)
        self.arch = Path(check_type(context.args["archPath"], str)).expanduser().resolve()
        prd = json_object(context.args["prd"])
        self.prd = Path(check_type(prd["path"], str)).expanduser().resolve()
        self.matrix = matrix
        self.matrix_data = read(matrix)
        self.draft = self.work / "draft"
        self.draft.mkdir(exist_ok=True)
        self.schemas = runner.plugin / "skills/artifact-handoff/schemas"
        self.subject = str(context.args.get("architectureSubject") or "")
        self.forbid = [
            context.bead,
            str(prd.get("id", "")),
            self.prd.stem,
        ]
        self.ran: set[Path] = set()
        self.adopted = False
        self.context_path = self.work / "architecture-context.json"
        write_json(
            self.context_path,
            {
                "archPath": str(self.arch),
                "draftPath": str(self.draft),
                "roundsPath": str(self.work / "rounds"),
                "modelPath": str(
                    self.arch / "reference/architecture-documentation-model.md",
                ),
                "menuPath": str(self.arch / "reference/diagram-and-model-types.md"),
                "roster": ROLES,
                "roundLimit": 3,
            },
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def call(
        self,
        module: str,
        function: str,
        *args: object,
        stage: str,
        **kwargs: object,
    ) -> object:
        """Dispatch a portfolio function through the typed tool boundary.

        Returns:
            The validated result for this operation.

        """
        return self.tools.portfolio(module, function, *args, stage=stage, **kwargs)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def checked(self, result: object, stage: str) -> dict[str, JsonValue]:
        """Validate a portfolio result and raise for a reported failure.

        Returns:
            The validated result for this operation.

        """
        result = json_object(result)
        if result.get("error") or result.get("refused") or result.get("ok") is False:
            raise self.tools.failure(stage, "other", result)
        return result

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def facts(self, **kwargs: object) -> dict[str, JsonValue]:
        """Read and validate the current resume facts.

        Returns:
            The validated result for this operation.

        """
        return json_object(
            self.call(
                "archresume",
                "resume_facts",
                str(self.work),
                roster=ROSTER,
                matrix_snapshot=self.matrix_data,
                stage="resume",
                **kwargs,
            ),
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def target(self, *, seed: bool = False, dry_run: bool = False) -> dict[str, JsonValue]:
        """Write or reuse the measured target manifest.

        Returns:
            The validated result for this operation.

        """
        target_path = self.work / "target.json"
        docs = [
            document
            for entry in check_type(
                read(self.work / "survey.json").get("baseline", []),
                list[dict[str, JsonValue]],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
            for document in check_type(
                entry.get("documents", []),
                list[dict[str, JsonValue]],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        ]
        docs += [{"path": str(path)} for path in self.draft.rglob("*.md")]
        elements = check_type(
            self.call("archmatrix", "catalog_elements", docs, stage="target"),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        binding = "matrix-rows:" + json.dumps(
            {
                "matrix": str(self.matrix),
                "elements": [" ".join(name.split()).casefold() for name in elements],
            },
            sort_keys=True,
        )
        inputs = (*self.base_inputs(), str(self.draft), binding)
        previous = read(target_path)
        if not seed and not dry_run and self.store.reusable(inputs, (target_path,)):
            hashes = check_type(
                previous.get("targetHashes", {}),
                dict[str, str],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
            if hashes and all(
                Path(path).is_file() and self.store.module.sha256_file(Path(path)) == digest
                for path, digest in hashes.items()
            ):
                return previous
        result = json_object(
            self.call(
                "archstate",
                "write_target",
                str(self.draft),
                arch_root=str(self.arch),
                subject=self.subject,
                forbid=self.forbid,
                baseline=str(self.work / "survey.json"),
                matrix_snapshot=self.matrix_data,
                seed=seed,
                dry_run=dry_run,
                stage="target",
            ),
        )
        if not seed and not dry_run and result.get("targetDir") and result.get("ok") is True:
            result["targetHashes"] = {
                str(path): check_type(self.store.module.sha256_file(path), str)
                for path in Path(check_type(result["targetDir"], str)).rglob("*")
                if path.is_file() and path.name != "closure.json" and not path.name.endswith(".meta.json")
            }
        write_json(
            self.work / ("target-check.json" if dry_run or seed else "target.json"),
            result,
        )
        if not seed and not dry_run and result.get("targetHashes"):
            self.store.accept("architecture:target", inputs, (target_path,))
        return result

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def agent(self, request: ArchitectureStep) -> dict[str, JsonValue]:
        """Execute one architecture agent and emit its recorded verdict.

        Returns:
            The validated result for this operation.

        """
        model, effort = model_for(request.agent)
        step = AgentStep(
            stage=request.stage or f"architecture:{request.output.stem}",
            agent=request.agent,
            inputs=(*request.inputs, str(self.context_path)),
            output=self.work / "candidates" / request.output.name,
            final=request.output,
            outcome=request.outcome,
            validate=self.schemas / f"{request.schema}.schema.json",
            model=model,
            effort=effort,
            add_dirs=(self.context.work, self.arch, self.prd.parent),
        )
        if not self.store.reusable(step.inputs, (request.output,)):
            self.ran.add(request.output)
        self.runner.run(step)
        result = read(request.output)
        if request.agent == "architecture-decider":
            verdict = result["verdict"]
        elif request.schema in {"architecture-review", "conformance"}:
            verdict = (
                "pass"
                if result.get("conforms", True)
                and not any(
                    f.get("verdict") in {"unsupported", "wrong"}
                    for f in check_type(
                        result.get("findings", []),
                        list[dict[str, JsonValue]],
                        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                    )
                )
                else "reject"
            )
        else:
            return result
        self.runner.emit(
            "verdict",
            phase="architecture",
            label=request.agent,
            verdict=verdict,
            detail=str(request.output),
        )
        return result

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def base_inputs(self) -> tuple[str, ...]:
        """Return the shared architecture artifact inputs.

        Returns:
            The validated result for this operation.

        """
        return (str(self.prd), str(self.work / "survey.json"))

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def ledger_input(self, name: str, *, refresh: bool = False) -> Path:
        """Snapshot the current resume ledger as an artifact input.

        Returns:
            The validated result for this operation.

        """
        path = self.work / "inputs" / f"{name}.ledger.json"
        if refresh or not path.exists():
            self.facts()
            write_json(path, read(self.work / "ledger.json"))
        return path
