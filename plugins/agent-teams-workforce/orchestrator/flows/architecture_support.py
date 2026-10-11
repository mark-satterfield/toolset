"""Architecture file contracts and direct step dispatch."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, ParamSpec, TypeVar

# The survey, target and architecture-artifact contracts are generated into their skills, their one
# definitions.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import archmatrix
import archresume
import archstate
from architecture_artifacts import (
    CONFORMANCE_SCHEMA_PATH,
    REVIEW_SCHEMA_PATH,
    VERDICT_UNSUPPORTED,
    VERDICT_WRONG,
    ConformanceResult,
    ReviewResult,
    parse_conformance_result,
    parse_review_result,
)
from survey_contract import SURVEY_FILE, BaselineEntry, parse_survey
from target_contract import (
    ARCHITECTURE_WORK_FOLDER,
    CLOSURE_FILE,
    KEY_OK,
    KEY_TARGET_DIR,
    KEY_TARGET_HASHES,
    TARGET_CHECK_FILE,
    TARGET_REPORT_NAME,
    TargetResult,
    load_target_report,
    validate_target_report,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner, strict_json
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.driver_contracts import DispatchArgumentsContract, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE, PRD_TO_SPEC_PHASES, verdict_event
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext
from orchestrator.core.tools import Tools
from orchestrator.flows.elaboration_support import emit_event

(
    ARCHITECTURE_PHASE,
    REPO_SCOPING_PHASE,
    TRD_AUTHORING_PHASE,
    SPEC_AUTHORING_PHASE,
    TASK_DECOMPOSITION_PHASE,
    TASK_EDGES_PHASE,
    FINISH_PHASE,
) = PRD_TO_SPEC_PHASES
_REJECTING_VERDICTS: Final[frozenset[str]] = frozenset({VERDICT_UNSUPPORTED, VERDICT_WRONG})

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


P = ParamSpec("P")
R = TypeVar("R")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def value_input(name: str, value: object) -> str:
    """Encode a validated JSON value as a stable artifact input.

    Returns:
        The validated result for this operation.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(name, str)):
        argument_error: str = "value_input: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(path, Path)):
        argument_error: str = "read: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    return strict_json(path) if path.is_file() else {}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def model_for(agent: str) -> tuple[str, str]:
    """Choose the configured model and effort for an architecture role.

    Returns:
        The validated result for this operation.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(agent, str)):
        argument_error: str = "model_for: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
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
        """Bind architecture paths and write the shared agent context.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if (
            not (isinstance(context, RunContext))
            or not (isinstance(store, ArtifactStore))
            or not (isinstance(runner, AgentRunner))
            or not (isinstance(tools, Tools))
            or not (isinstance(matrix, Path))
        ):
            argument_error: str = "__init__: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        self.context: RunContext = context
        self.store: ArtifactStore = store
        self.runner: AgentRunner = runner
        self.tools: Tools = tools
        dispatch: DispatchArgumentsContract = dispatch_arguments()
        self.work: Path = context.work / ARCHITECTURE_WORK_FOLDER
        self.work.mkdir(parents=True, exist_ok=True)
        self.arch: Path = Path(check_type(context.args[dispatch.KEY_ARCH_PATH], str)).expanduser().resolve()
        prd: dict[str, JsonValue] = json_object(context.args[dispatch.KEY_PRD])
        self.prd: Path = Path(check_type(prd[dispatch.PRD_PATH], str)).expanduser().resolve()
        self.matrix: Path = matrix
        self.matrix_data: dict[str, JsonValue] = read(matrix)
        self.draft: Path = self.work / "draft"
        self.draft.mkdir(exist_ok=True)
        self.schemas: Path = runner.plugin / "skills/artifact-handoff/schemas"
        self.subject: str = str(context.args.get("architectureSubject") or "")
        self.forbid: list[str] = [
            context.bead,
            str(prd.get(dispatch.PRD_ID, "")),
            self.prd.stem,
        ]
        self.ran: set[Path] = set()
        self.adopted: bool = False
        self.context_path: Path = self.work / "architecture-context.json"
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
        stage: str,
        operation: Callable[P, R],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Dispatch a portfolio function through the typed tool boundary.

        Returns:
            The validated result for this operation.

        Raises:
            TypeError: The dispatch arguments have invalid types.

        """
        if not isinstance(stage, str) or not callable(operation):
            message: str = "Portfolio dispatch requires a string stage and a callable operation"
            raise TypeError(message)
        return self.tools.portfolio(stage, operation, *args, **kwargs)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def checked(self, result: object, stage: str) -> dict[str, JsonValue]:
        """Validate a portfolio result and raise for a reported failure.

        Returns:
            The validated result for this operation.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(stage, str)):
            argument_error: str = "checked: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        result = json_object(result)
        if result.get("error") or result.get("refused") or result.get("ok") is False:
            raise self.tools.failure(stage, OTHER_CAUSE, result)
        return result

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def facts(self, *, assign: str = "", team: str = "", plan: str = "") -> dict[str, JsonValue]:
        """Read and validate the current resume facts.

        Returns:
            The validated result for this operation.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(assign, str)) or not (isinstance(team, str)) or not (isinstance(plan, str)):
            argument_error: str = "facts: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        return json_object(
            self.call(
                "resume",
                archresume.resume_facts,
                str(self.work),
                archresume.ResumeOptions(
                    roster=ROSTER,
                    matrix_snapshot=self.matrix_data,
                    assign=assign,
                    team=team,
                    plan=plan,
                ),
            ),
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def target(self, *, seed: bool = False, dry_run: bool = False) -> dict[str, JsonValue]:
        """Write or reuse the measured target manifest.

        Returns:
            The validated result for this operation.

        Raises:
            TypeError: A target policy has an invalid type.

        """
        if not isinstance(seed, bool) or not isinstance(dry_run, bool):
            message: str = "Target policies must be boolean"
            raise TypeError(message)
        target_path: Path = self.work / TARGET_REPORT_NAME
        survey_path: Path = self.work / SURVEY_FILE
        baseline: list[BaselineEntry] = parse_survey(read(survey_path))["baseline"] if survey_path.is_file() else []
        docs: list[dict[str, JsonValue]] = [
            {"path": document["path"]} for entry in baseline for document in entry["documents"]
        ]
        docs += [{"path": str(path)} for path in self.draft.rglob("*.md")]
        elements: dict[str, list[str]] = self.call("target", archmatrix.catalog_elements, docs)
        binding: str = "matrix-rows:" + json.dumps(
            {
                "matrix": str(self.matrix),
                "elements": [" ".join(name.split()).casefold() for name in elements],
            },
            sort_keys=True,
        )
        inputs: tuple[str, ...] = (*self.base_inputs(), str(self.draft), binding)
        if not seed and not dry_run and self.store.reusable(inputs, (target_path,)):
            previous: TargetResult = load_target_report(target_path)
            hashes: dict[str, str] = previous.get(KEY_TARGET_HASHES, {})
            if hashes and all(
                Path(path).is_file() and self.store.module.sha256_file(Path(path)) == digest
                for path, digest in hashes.items()
            ):
                return json_object(previous)
        produced: object = self.call(
            "target",
            archstate.write_target,
            str(self.draft),
            archstate.TargetOptions(
                arch_root=str(self.arch),
                subject=self.subject,
                forbid=self.forbid,
                baseline=str(survey_path),
                matrix_snapshot=self.matrix_data,
                seed=seed,
                dry_run=dry_run,
            ),
        )
        result: TargetResult = validate_target_report(json_object(produced), "archstate.write_target result")
        target_dir: str | None = result.get(KEY_TARGET_DIR)
        if not seed and not dry_run and target_dir and result[KEY_OK]:
            result[KEY_TARGET_HASHES] = {
                str(path): self.store.module.sha256_file(path)
                for path in Path(target_dir).rglob("*")
                if path.is_file() and path.name != CLOSURE_FILE and not path.name.endswith(".meta.json")
            }
        write_json(
            self.work / (TARGET_CHECK_FILE if dry_run or seed else TARGET_REPORT_NAME),
            result,
        )
        if not seed and not dry_run and result.get(KEY_TARGET_HASHES):
            self.store.accept("architecture:target", inputs, (target_path,))
        return json_object(result)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def agent(self, request: ArchitectureStep) -> dict[str, JsonValue]:
        """Execute one architecture agent and emit its recorded verdict.

        Returns:
            The validated result for this operation.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(request, ArchitectureStep)):
            argument_error: str = "agent: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        model: str
        effort: str
        model, effort = model_for(request.agent)
        schema: Path = self.schemas / f"{request.schema}.schema.json"
        step: AgentStep = AgentStep(
            stage=request.stage or f"architecture:{request.output.stem}",
            agent=request.agent,
            inputs=(*request.inputs, str(self.context_path)),
            output=self.work / "candidates" / request.output.name,
            final=request.output,
            outcome=request.outcome,
            validate=schema,
            model=model,
            effort=effort,
            add_dirs=(self.context.work, self.arch, self.prd.parent),
        )
        if not self.store.reusable(step.inputs, (request.output,)):
            self.ran.add(request.output)
        self.runner.run(step)
        result: dict[str, JsonValue] = read(request.output)
        verdict: str
        if request.agent == "architecture-decider":
            verdict = check_type(result["verdict"], str)
        elif schema.name == REVIEW_SCHEMA_PATH.name:
            review: ReviewResult = parse_review_result(request.output)
            verdict = (
                "reject" if any(finding["verdict"] in _REJECTING_VERDICTS for finding in review["findings"]) else "pass"
            )
        elif schema.name == CONFORMANCE_SCHEMA_PATH.name:
            conformance: ConformanceResult = parse_conformance_result(request.output)
            verdict = "pass" if conformance["conforms"] else "reject"
        else:
            return result
        emit_event(self.runner.emit, verdict_event(ARCHITECTURE_PHASE, request.agent, verdict, str(request.output)))
        return result

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def base_inputs(self) -> tuple[str, ...]:
        """Return the shared architecture artifact inputs.

        Returns:
            The validated result for this operation.

        """
        return (str(self.prd), str(self.work / SURVEY_FILE))

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def ledger_input(self, name: str, *, refresh: bool = False) -> Path:
        """Snapshot the current resume ledger as an artifact input.

        Returns:
            The validated result for this operation.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(name, str)) or not (isinstance(refresh, bool)):
            argument_error: str = "ledger_input: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        path: Path = self.work / "inputs" / f"{name}.ledger.json"
        if refresh or not path.exists():
            self.facts()
            write_json(path, read(self.work / "ledger.json"))
        return path
