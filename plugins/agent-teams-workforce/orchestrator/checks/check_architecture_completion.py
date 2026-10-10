"""Small pure checks for completed receipts and matrix-dependent root projection."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import override

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.checks.check_support import report, require
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import RunContext
from orchestrator.core.tools import Tools
from orchestrator.flows.architecture_projection import project
from orchestrator.flows.architecture_resume import (
    approved,
    completed,
    retire_generation,
    save_approval,
    save_completion,
)
from orchestrator.flows.architecture_support import Architecture


class CompletionFlow(Architecture):
    """Use real flow state while controlling the cited-view freshness response."""

    problem: str | None = None

    @override
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def call(self, module: str, function: str, *args: object, stage: str, **kwargs: object) -> object:
        """Return the selected cited-view freshness result.

        Returns:
            The fixture's current problem, if any.

        """
        return self.problem


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-script", type=Path, required=True)
    parser.add_argument("--survey-dir", type=Path, required=True)
    args = parser.parse_args()
    _completion_inputs(args.artifact_script, args.survey_dir)
    _projection()


def _flow(root: Path, artifact_script: Path) -> CompletionFlow:
    context = RunContext(
        "example",
        "architecture",
        {"archPath": str(root / "vault"), "prd": {"path": str(root / "prd.md")}},
        root,
        "check",
    )
    store = ArtifactStore(load_artifactio(artifact_script), root, root / "architecture", "example", "check")
    runner = AgentRunner(context, store)
    matrix = root / "matrix.json"
    write_json(matrix, {"elements": {}})
    return CompletionFlow(context, store, runner, Tools(root / "evidence"), matrix)


def _completion_inputs(artifact_script: Path, survey_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="architecture-completion-") as temp:
        root = Path(temp)
        work = root / "architecture"
        arch = root / "vault"
        schemas = root / "schemas"
        work.mkdir()
        schemas.mkdir()
        (arch / "arc42/02-architecture-constraints").mkdir(parents=True)
        target = arch / "target/example"
        target.mkdir(parents=True)
        flow = _flow(root, artifact_script)
        flow.schemas = schemas
        flow.prd.write_text("PRD")
        view = arch / "arc42/view.md"
        view.write_text("post-integration canonical")
        write_json(work / "arc42-revision.json", {"views": {"view.md": "old"}})
        write_json(work / "closure-walk.json", {"elements": []})
        saved_seal = survey_dir / "survey.json.baseline-inputs.json"
        original_seal = saved_seal.read_bytes()
        seal = json_object(json.loads(original_seal))
        inputs = check_type(seal["inputs"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        seal["inputs"] = [*inputs, str(flow.prd), str(view)]
        write_json(work / "survey.json.baseline-inputs.json", seal)
        result: dict[str, JsonValue] = {"ok": True, "subject": "example", "targetDir": str(target)}
        save_completion(flow, result)
        require(completed(flow) == result, "completed(flow) == result")
        (arch / "arc42/unrelated.md").write_text("another Epic")
        require(completed(flow) == result, "unrelated view invalidated completed work")
        for path in (
            flow.prd,
            view,
            schemas / "survey.schema.json",
            arch / "arc42/02-architecture-constraints/owner.md",
        ):
            previous = path.read_bytes() if path.exists() else None
            path.write_text("changed")
            require(completed(flow) is None, f"missed changed input {path}")
            if previous is None:
                path.unlink()
            else:
                path.write_bytes(previous)
        require(completed(flow) == result, "completed(flow) == result")
        _approval(flow, target, view)
        require(saved_seal.read_bytes() == original_seal, "saved_seal.read_bytes() == original_seal")


def _approval(flow: CompletionFlow, target: Path, view: Path) -> None:
    flow.subject = "example"
    flow.problem = None
    write_json(flow.work / "target.json", {"targetDir": str(target)})
    target_view = target / "view.md"
    target_view.write_text("approved")
    save_approval(
        flow,
        {"targetDir": str(target)},
        {"round": 3, "verdict": "approve"},
    )
    target_view.write_text("unreviewed target edit")
    require(approved(flow) is None, "target bytes were not fingerprinted")
    target_view.write_text("approved")
    (target / "closure.json").write_text("downstream Closure publication", encoding="utf-8")
    require(approved(flow), "Closure publication revoked architecture approval")
    view.write_text("interrupted maintainer write", encoding="utf-8")
    require(approved(flow), "owned canonical writes invalidated integration recovery")
    flow.problem = "cited view changed"
    require(approved(flow) is None, "approved(flow) is None")
    require((flow.work / "architecture-approved.json").exists(), "read-only check moved work")
    flow.problem = None
    flow.prd.write_text("new PRD during integration")
    require(approved(flow) is None, "upstream change reused integration recovery")
    write_json(flow.work / "decision.json", {"round": 3, "verdict": "deny"})
    (flow.work / "plans").mkdir()
    write_json(flow.work / "plans/round3-plan-0.json", {"old": True})
    retire_generation(flow)
    require(not (flow.work / "decision.json").exists(), "not (flow.work / 'decision.json').exists()")
    require(not (flow.work / "plans").exists(), "not (flow.work / 'plans').exists()")
    require(
        list(flow.work.parent.glob("stale-survey-*/architecture/decision.json")),
        "list(flow.work.parent.glob('stale-survey-*/architecture/decision.json'))",
    )


def _projection() -> None:
    all_roots: dict[str, JsonValue] = {"items": [{"id": "D1", "element": "A"}, {"id": "D2", "element": "B"}]}
    walk: dict[str, JsonValue] = {
        "elements": [
            {
                "element": "P",
                "views": [],
                "evidence": [],
                "requires": [],
                "requiredBy": ["D2"],
            },
        ],
        "rootEdges": [{"item": "D2", "requires": ["P"], "evidence": "view"}],
        "summary": "dependencies",
    }
    current: dict[str, JsonValue] = {"items": [{"id": "D1", "element": "B"}]}
    projected = project(walk, all_roots, current, {"elements": {}})
    require(
        check_type(
            projected["rootEdges"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )[0]["item"]
        == "B",
        "saved architecture contract changed",
    )
    require(
        check_type(
            projected["rootEdges"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )[0]["evidence"]
        == "view",
        "saved architecture contract changed",
    )
    require(
        check_type(
            projected["prerequisites"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )[0]["requiredBy"]
        == ["B"],
        "saved architecture contract changed",
    )
    expanded = project(walk, all_roots, all_roots, {"elements": {}})
    require(
        {
            edge["item"]
            for edge in check_type(
                expanded["rootEdges"],
                list[dict[str, JsonValue]],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        }
        == {"A", "B"},
        "saved architecture contract changed",
    )
    report("PASS: completion inputs, approval recovery, retired generation and stable root projection")


if __name__ == "__main__":
    main()
