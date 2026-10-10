"""Post-integration completion receipts and survey generation retirement."""

from __future__ import annotations

import json
import time
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.matrix import element_id
from orchestrator.flows.architecture_projection import project
from orchestrator.flows.architecture_support import Architecture, read


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def completion_inputs(flow: Architecture, result: dict[str, JsonValue]) -> tuple[str, ...]:
    # Capture canonical views after integration, not the survey's pre-integration seal.
    # Matrix rows deliberately remain Closure's separate, deterministic dependency.
    """Completion inputs.

    Returns:
        The validated architecture artifact result.

    """
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
        Path(check_type(result["targetDir"], str)),
    ]
    revision = read(flow.work / "arc42-revision.json")
    paths.extend(flow.arch / "arc42" / name for name in json_object(revision.get("views", {})))
    for element in check_type(
        read(flow.work / "closure-walk.json").get("elements", []),
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        for view in check_type(
            element.get("views", []),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ):
            path = Path(view)
            if not path.is_absolute():
                path = flow.arch / path if path.parts[0] == "arc42" else flow.arch / "arc42" / path
            paths.append(path)
    seal = read(flow.work / "survey.json.baseline-inputs.json")
    paths.extend(
        Path(path)
        for path in check_type(
            seal.get("inputs", []),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    )
    return tuple(sorted(set(map(str, paths))))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def save_completion(flow: Architecture, result: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Save completion.

    Returns:
        The validated architecture artifact result.

    """
    path = flow.work / "architecture-result.json"
    write_json(path, result)
    flow.store.accept("architecture:complete", completion_inputs(flow, result), (path,))
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def completed(flow: Architecture) -> dict[str, JsonValue] | None:
    """Completed.

    Returns:
        The validated architecture artifact result.

    """
    path = flow.work / "architecture-result.json"
    result = read(path)
    if not result.get("ok") or not result.get("targetDir"):
        return None
    if not flow.store.reusable(completion_inputs(flow, result), (path,)):
        return None
    flow.subject = check_type(result["subject"], str)
    flow.runner.emit("note", kind="reused", step="architecture:complete")
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def retire_generation(flow: Architecture) -> None:
    """Retain evidence but remove every downstream result of a stale survey."""
    destination = flow.work.parent / f"stale-survey-{time.time_ns()}" / "architecture"
    destination.mkdir(parents=True)
    for path in tuple(flow.work.iterdir()):
        path.rename(destination / path.name)
    flow.runner.emit(
        "note",
        kind="invalidated",
        step="architecture:survey",
        path=str(destination),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def refresh_closure(flow: Architecture, result: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Reclassify the accepted future-set walk without another session.

    Returns:
        The completed architecture result with refreshed closure evidence.

    """
    walk_path = flow.work / "closure-walk.json"
    walk = read(walk_path)
    target = read(flow.work / "target.json")
    roots = read(flow.work / "closure-roots.json")
    current_roots = json_object(
        flow.call(
            "archstate",
            "delta_items",
            target["deltaDir"],
            with_closure=False,
            matrix_snapshot=flow.matrix_data,
            stage="closure",
        ),
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
    canonical = Path(check_type(result["targetDir"], str)) / "closure.json"
    write_json(path, classified)
    binding = "matrix-rows:" + json.dumps(
        {
            "matrix": str(flow.matrix),
            "elements": sorted(
                {
                    element_id(check_type(row["element"], str))
                    for row in [
                        *check_type(
                            walk["elements"],
                            list[dict[str, JsonValue]],
                            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                        ),
                        *check_type(
                            roots.get("items", []),
                            list[dict[str, JsonValue]],
                            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                        ),
                    ]
                },
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    flow.store.accept(
        "architecture:closure",
        (str(walk_path), binding),
        (path, canonical),
    )
    result["closure"] = {
        "path": str(canonical),
        "workPath": str(path),
        "prerequisites": len(
            check_type(
                classified["prerequisites"],
                list[JsonValue],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ),
        ),
    }
    return save_completion(flow, result)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approval_inputs(flow: Architecture) -> tuple[str, ...]:
    """Approval inputs.

    Returns:
        The validated architecture artifact result.

    """
    target = read(flow.work / "target.json")
    # Closure is a downstream output: its publication cannot revoke approval.
    target_inputs = tuple(sorted(json_object(target.get("targetHashes", {}))))
    if target.get("targetDir"):
        target_inputs = tuple(
            sorted(
                set(target_inputs)
                | {
                    str(path)
                    for path in Path(check_type(target["targetDir"], str)).rglob("*")
                    if path.is_file() and path.name != "closure.json" and not path.name.endswith(".meta.json")
                },
            ),
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
        ),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def save_approval(flow: Architecture, target: dict[str, JsonValue], decision: dict[str, JsonValue]) -> None:
    """Save approval."""
    path = flow.work / "architecture-approved.json"
    write_json(path, {"target": target, "decision": decision, "subject": flow.subject})
    flow.store.accept("architecture:approved", approval_inputs(flow), (path,))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approved(flow: Architecture) -> dict[str, JsonValue] | None:
    """Approved.

    Returns:
        The validated architecture artifact result.

    """
    path = flow.work / "architecture-approved.json"
    if not flow.store.reusable(approval_inputs(flow), (path,)):
        return None
    # While integrating, this record explicitly permits the maintainer's own writes.
    # After integration, it again checks cited canonical views against accepted hashes.
    problem = flow.call(
        "archrevision",
        "record_problem",
        str(flow.work),
        str(flow.arch),
        stage="resume",
    )
    if problem:
        return None
    result = read(path)
    flow.subject = check_type(result["subject"], str)
    return result
