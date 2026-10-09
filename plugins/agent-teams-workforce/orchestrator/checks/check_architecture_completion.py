"""Small pure checks for completed receipts and matrix-dependent root projection."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.io import write_json
from orchestrator.flows.architecture_projection import project
from orchestrator.flows.architecture_resume import (
    approved,
    completed,
    retire_generation,
    save_approval,
    save_completion,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-script", type=Path, required=True)
    parser.add_argument("--survey-dir", type=Path, required=True)
    args = parser.parse_args()
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
        flow = SimpleNamespace(
            work=work,
            arch=arch,
            prd=root / "prd.md",
            schemas=schemas,
            context_path=work / "context.json",
            runner=SimpleNamespace(emit=lambda *a, **k: None),
        )
        flow.store = ArtifactStore(
            load_artifactio(args.artifact_script), root, work, "example", "check"
        )
        flow.prd.write_text("PRD")
        view = arch / "arc42/view.md"
        view.write_text("post-integration canonical")
        write_json(work / "arc42-revision.json", {"views": {"view.md": "old"}})
        write_json(work / "closure-walk.json", {"elements": []})
        saved_seal = args.survey_dir / "survey.json.baseline-inputs.json"
        original_seal = saved_seal.read_bytes()
        seal = json.loads(original_seal)
        seal["inputs"] += [str(flow.prd), str(view)]
        write_json(work / "survey.json.baseline-inputs.json", seal)
        result = {"ok": True, "subject": "example", "targetDir": str(target)}
        save_completion(flow, result)
        assert completed(flow) == result
        (arch / "arc42/unrelated.md").write_text("another Epic")
        assert completed(flow) == result, "unrelated view invalidated completed work"
        for path in (
            flow.prd,
            view,
            schemas / "survey.schema.json",
            arch / "arc42/02-architecture-constraints/owner.md",
        ):
            previous = path.read_bytes() if path.exists() else None
            path.write_text("changed")
            assert completed(flow) is None, f"missed changed input {path}"
            if previous is None:
                path.unlink()
            else:
                path.write_bytes(previous)
        assert completed(flow) == result
        flow.subject = "example"
        flow.call = lambda *a, **k: None
        flow.checked = lambda value, stage: value
        write_json(work / "target.json", {"targetDir": str(target)})
        target_view = target / "view.md"
        target_view.write_text("approved")
        save_approval(
            flow, {"targetDir": str(target)}, {"round": 3, "verdict": "approve"}
        )
        target_view.write_text("unreviewed target edit")
        assert approved(flow) is None, "target bytes were not fingerprinted"
        target_view.write_text("approved")
        (target / "closure.json").write_text("downstream Closure publication")
        assert approved(flow), "Closure publication revoked architecture approval"
        view.write_text("interrupted maintainer write")
        assert approved(flow), "owned canonical writes invalidated integration recovery"
        flow.call = lambda *a, **k: "cited view changed"
        assert approved(flow) is None
        assert (work / "architecture-approved.json").exists(), (
            "read-only check moved work"
        )
        flow.call = lambda *a, **k: None
        flow.prd.write_text("new PRD during integration")
        assert approved(flow) is None, "upstream change reused integration recovery"
        write_json(work / "decision.json", {"round": 3, "verdict": "deny"})
        (work / "plans").mkdir()
        write_json(work / "plans/round3-plan-0.json", {"old": True})
        retire_generation(flow)
        assert not (work / "decision.json").exists() and not (work / "plans").exists()
        assert list(root.glob("stale-survey-*/architecture/decision.json"))
        assert saved_seal.read_bytes() == original_seal
    all_roots = {"items": [{"id": "D1", "element": "A"}, {"id": "D2", "element": "B"}]}
    walk = {
        "elements": [
            {
                "element": "P",
                "views": [],
                "evidence": [],
                "requires": [],
                "requiredBy": ["D2"],
            }
        ],
        "rootEdges": [{"item": "D2", "requires": ["P"], "evidence": "view"}],
        "summary": "dependencies",
    }
    current = {"items": [{"id": "D1", "element": "B"}]}
    projected = project(walk, all_roots, current, {"elements": {}})
    assert projected["rootEdges"][0]["item"] == "B"
    assert projected["rootEdges"][0]["evidence"] == "view"
    assert projected["prerequisites"][0]["requiredBy"] == ["B"]
    expanded = project(walk, all_roots, all_roots, {"elements": {}})
    assert {edge["item"] for edge in expanded["rootEdges"]} == {"A", "B"}
    print(
        "PASS: post-integration receipt reuse; changed PRD/schema/constraints/view invalidation; unrelated view reuse; retired round3; stable roots across matrix transitions"
    )


if __name__ == "__main__":
    main()
