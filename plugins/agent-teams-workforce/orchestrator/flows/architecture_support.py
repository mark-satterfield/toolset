"""Architecture file contracts and direct step dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.agents import AgentRunner, strict_json
from ..core.artifacts import ArtifactStore
from ..core.io import write_json
from ..core.models import AgentStep, RunContext
from ..core.tools import Tools

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


def value_input(name: str, value: Any) -> str:
    return "value:" + json.dumps(
        {"name": name, "value": value}, sort_keys=True, separators=(",", ":")
    )


def read(path: Path) -> dict:
    return strict_json(path) if path.is_file() else {}


def model_for(agent: str) -> tuple[str, str]:
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


class Architecture:
    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        runner: AgentRunner,
        tools: Tools,
        matrix: Path,
    ) -> None:
        self.context, self.store, self.runner, self.tools = (
            context,
            store,
            runner,
            tools,
        )
        self.work = context.work / "architecture"
        self.work.mkdir(parents=True, exist_ok=True)
        self.arch = Path(context.args["archPath"]).expanduser().resolve()
        self.prd = Path(context.args["prd"]["path"]).expanduser().resolve()
        self.matrix = matrix
        self.matrix_data = read(matrix)
        self.draft = self.work / "draft"
        self.draft.mkdir(exist_ok=True)
        self.schemas = runner.plugin / "skills/artifact-handoff/schemas"
        self.subject = str(context.args.get("architectureSubject") or "")
        self.forbid = [
            context.bead,
            str(context.args["prd"].get("id", "")),
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
                    self.arch / "reference/architecture-documentation-model.md"
                ),
                "menuPath": str(self.arch / "reference/diagram-and-model-types.md"),
                "roster": ROLES,
                "roundLimit": 3,
            },
        )

    def call(
        self, module: str, function: str, *args: Any, stage: str, **kwargs: Any
    ) -> Any:
        return self.tools.portfolio(module, function, *args, stage=stage, **kwargs)

    def checked(self, result: dict, stage: str) -> dict:
        if result.get("error") or result.get("refused") or result.get("ok") is False:
            raise self.tools.failure(stage, "other", result)
        return result

    def facts(self, **kwargs: Any) -> dict:
        return self.call(
            "archresume",
            "resume_facts",
            str(self.work),
            roster=ROSTER,
            matrix_snapshot=self.matrix_data,
            stage="resume",
            **kwargs,
        )

    def target(self, *, seed: bool = False, dry_run: bool = False) -> dict:
        target_path = self.work / "target.json"
        docs = [
            document
            for entry in read(self.work / "survey.json").get("baseline", [])
            for document in entry.get("documents", [])
        ]
        docs += [{"path": str(path)} for path in self.draft.rglob("*.md")]
        elements = self.call("archmatrix", "catalog_elements", docs, stage="target")
        binding = "matrix-rows:" + json.dumps(
            {
                "matrix": str(self.matrix),
                "elements": [" ".join(name.split()).casefold() for name in elements],
            },
            sort_keys=True,
        )
        inputs = self.base_inputs() + (str(self.draft), binding)
        previous = read(target_path)
        if not seed and not dry_run and self.store.reusable(inputs, (target_path,)):
            hashes = previous.get("targetHashes", {})
            if hashes and all(
                Path(path).is_file()
                and self.store.module.sha256_file(Path(path)) == digest
                for path, digest in hashes.items()
            ):
                return previous
        result = self.call(
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
        )
        if (
            not seed
            and not dry_run
            and result.get("targetDir")
            and result.get("ok") is True
        ):
            result["targetHashes"] = {
                str(path): self.store.module.sha256_file(path)
                for path in Path(result["targetDir"]).rglob("*")
                if path.is_file()
                and path.name != "closure.json"
                and not path.name.endswith(".meta.json")
            }
        write_json(
            self.work / ("target-check.json" if dry_run or seed else "target.json"),
            result,
        )
        if not seed and not dry_run and result.get("targetHashes"):
            self.store.accept("architecture:target", inputs, (target_path,))
        return result

    def agent(
        self,
        agent: str,
        output: Path,
        schema: str,
        inputs: tuple[str, ...],
        outcome: str,
        *,
        stage: str | None = None,
    ) -> dict:
        model, effort = model_for(agent)
        step = AgentStep(
            stage=stage or f"architecture:{output.stem}",
            agent=agent,
            inputs=inputs + (str(self.context_path),),
            output=self.work / "candidates" / output.name,
            final=output,
            outcome=outcome,
            validate=self.schemas / f"{schema}.schema.json",
            model=model,
            effort=effort,
            add_dirs=(self.context.work, self.arch, self.prd.parent),
        )
        if not self.store.reusable(step.inputs, (output,)):
            self.ran.add(output)
        self.runner.run(step)
        result = read(output)
        if agent == "architecture-decider":
            verdict = result["verdict"]
        elif schema in {"architecture-review", "conformance"}:
            verdict = (
                "pass"
                if result.get("conforms", True)
                and not any(
                    f.get("verdict") in {"unsupported", "wrong"}
                    for f in result.get("findings", [])
                )
                else "reject"
            )
        else:
            return result
        self.runner.emit(
            "verdict",
            phase="architecture",
            label=agent,
            verdict=verdict,
            detail=str(output),
        )
        return result

    def base_inputs(self) -> tuple[str, ...]:
        return (str(self.prd), str(self.work / "survey.json"))

    def ledger_input(self, name: str, *, refresh: bool = False) -> Path:
        path = self.work / "inputs" / f"{name}.ledger.json"
        if refresh or not path.exists():
            self.facts()
            write_json(path, read(self.work / "ledger.json"))
        return path
