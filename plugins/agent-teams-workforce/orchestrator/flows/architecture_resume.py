"""Post-integration completion receipts and survey generation retirement."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..core.io import write_json
from ..core.matrix import element_id
from .architecture_projection import project
from .architecture_support import Architecture, read


def completion_inputs(flow: Architecture, result: dict) -> tuple[str, ...]:
    # Capture canonical views after integration, not the survey's pre-integration seal.
    # Matrix rows deliberately remain Closure's separate, deterministic dependency.
    paths = [
        flow.prd,
        flow.arch / "reference/architecture-documentation-model.md",
        flow.arch / "reference/diagram-and-model-types.md",
        flow.arch / "arc42/02-architecture-constraints",
        flow.schemas,
        flow.context_path,
        flow.work / "draft",
        flow.work / "survey.json",
        flow.work / "decision.json",
        flow.work / "target.json",
        flow.work / "architecture-update.json",
        flow.work / "closure-walk.json",
        flow.work / "closure-roots.json",
        Path(result["targetDir"]),
    ]
    revision = read(flow.work / "arc42-revision.json")
    paths.extend(flow.arch / "arc42" / name for name in revision.get("views", {}))
    for element in read(flow.work / "closure-walk.json").get("elements", []):
        for view in element.get("views", []):
            path = Path(view)
            if not path.is_absolute():
                path = (
                    flow.arch / path
                    if path.parts[0] == "arc42"
                    else flow.arch / "arc42" / path
                )
            paths.append(path)
    seal = read(flow.work / "survey.json.baseline-inputs.json")
    paths.extend(Path(path) for path in seal.get("inputs", []))
    return tuple(sorted(set(map(str, paths))))


def save_completion(flow: Architecture, result: dict) -> dict:
    path = flow.work / "architecture-result.json"
    write_json(path, result)
    flow.store.accept("architecture:complete", completion_inputs(flow, result), (path,))
    return result


def completed(flow: Architecture) -> dict | None:
    path = flow.work / "architecture-result.json"
    result = read(path)
    if not result.get("ok") or not result.get("targetDir"):
        return None
    if not flow.store.reusable(completion_inputs(flow, result), (path,)):
        return None
    flow.subject = result["subject"]
    flow.runner.emit("note", kind="reused", step="architecture:complete")
    return result


def retire_generation(flow: Architecture) -> None:
    """Retain evidence but remove every downstream result of a stale survey."""
    destination = flow.work.parent / f"stale-survey-{time.time_ns()}" / "architecture"
    destination.mkdir(parents=True)
    for path in tuple(flow.work.iterdir()):
        path.rename(destination / path.name)
    flow.runner.emit(
        "note", kind="invalidated", step="architecture:survey", path=str(destination)
    )


def refresh_closure(flow: Architecture, result: dict) -> dict:
    """Reclassify the complete accepted future-set walk without another session."""
    walk_path = flow.work / "closure-walk.json"
    walk = read(walk_path)
    target = read(flow.work / "target.json")
    roots = read(flow.work / "closure-roots.json")
    current_roots = flow.call(
        "archstate",
        "delta_items",
        target["deltaDir"],
        with_closure=False,
        matrix_snapshot=flow.matrix_data,
        stage="closure",
    )
    classified = project(walk, roots, current_roots, flow.matrix_data)
    flow.checked(
        flow.call(
            "archclosure",
            "write_closure",
            classified,
            target["deltaDir"],
            matrix_snapshot=flow.matrix_data,
            stage="closure",
        ),
        "closure",
    )
    path = flow.work / "closure.json"
    canonical = Path(result["targetDir"]) / "closure.json"
    write_json(path, classified)
    binding = "matrix-rows:" + json.dumps(
        {
            "matrix": str(flow.matrix),
            "elements": sorted(
                {
                    element_id(row["element"])
                    for row in walk["elements"] + roots.get("items", [])
                }
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    flow.store.accept(
        "architecture:closure", (str(walk_path), binding), (path, canonical)
    )
    result["closure"] = {
        "path": str(canonical),
        "workPath": str(path),
        "prerequisites": len(classified["prerequisites"]),
    }
    return save_completion(flow, result)


def approval_inputs(flow: Architecture) -> tuple[str, ...]:
    target = read(flow.work / "target.json")
    # Closure is a downstream output: its publication cannot revoke approval.
    target_inputs = tuple(sorted(target.get("targetHashes", {})))
    if target.get("targetDir"):
        target_inputs = tuple(
            sorted(
                set(target_inputs)
                | {
                    str(path)
                    for path in Path(target["targetDir"]).rglob("*")
                    if path.is_file()
                    and path.name != "closure.json"
                    and not path.name.endswith(".meta.json")
                }
            )
        )
    return target_inputs + tuple(
        map(
            str,
            (
                flow.prd,
                flow.arch / "reference/architecture-documentation-model.md",
                flow.arch / "reference/diagram-and-model-types.md",
                flow.arch / "arc42/02-architecture-constraints",
                flow.schemas,
                flow.context_path,
                flow.work / "survey.json",
                flow.work / "decision.json",
                flow.work / "draft",
                flow.work / "target.json",
            ),
        )
    )


def save_approval(flow: Architecture, target: dict, decision: dict) -> None:
    path = flow.work / "architecture-approved.json"
    write_json(path, {"target": target, "decision": decision, "subject": flow.subject})
    flow.store.accept("architecture:approved", approval_inputs(flow), (path,))


def approved(flow: Architecture) -> dict | None:
    path = flow.work / "architecture-approved.json"
    if not flow.store.reusable(approval_inputs(flow), (path,)):
        return None
    # While integrating, this record explicitly permits the maintainer's own writes.
    # After integration, it again checks cited canonical views against accepted hashes.
    problem = flow.call(
        "archrevision", "record_problem", str(flow.work), str(flow.arch), stage="resume"
    )
    if problem:
        return None
    result = read(path)
    flow.subject = result["subject"]
    return result
