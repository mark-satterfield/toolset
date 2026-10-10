"""Join the view-only dependency walk to the run's immutable matrix snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.matrix import element_id
from orchestrator.flows.architecture_projection import project
from orchestrator.flows.architecture_support import Architecture, ArchitectureStep, read


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def closure(flow: Architecture, target: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Closure.

    Returns:
        The validated architecture result.

    """
    stage = "closure"
    roots = json_object(
        flow.call(
            "archstate",
            "delta_items",
            target["deltaDir"],
            with_closure=False,
            # Walk the entire future set so matrix-only changes never omit new build roots.
            matrix_snapshot={"elements": {}},
            stage="closure",
        ),
    )
    roots_path = flow.work / "closure-roots.json"
    write_json(roots_path, roots)
    walk_path = flow.work / "closure-walk.json"
    inputs: tuple[str, ...] = (str(roots_path), str(flow.arch / "arc42"), str(flow.prd))
    for _ in range(2):
        walk = flow.agent(
            ArchitectureStep(
                "prd-reality-reconciler",
                walk_path,
                "closure-walk",
                inputs,
                "Walk architecture prerequisites from the build roots.",
            ),
        )
        elements = sorted(
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
        )
        binding = "matrix-rows:" + json.dumps(
            {"matrix": str(flow.matrix), "elements": elements},
            sort_keys=True,
            separators=(",", ":"),
        )

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
        path = flow.work / "closure.json"
        write_json(path, classified)
        result = json_object(
            flow.call(
                "archclosure",
                "write_closure",
                classified,
                target["deltaDir"],
                dry_run=True,
                matrix_snapshot=flow.matrix_data,
                stage="closure",
            ),
        )
        if not result.get("refused") and not result.get("error") and result.get("ok") is not False:
            result = flow.checked(
                json_object(
                    flow.call(
                        "archclosure",
                        "write_closure",
                        classified,
                        target["deltaDir"],
                        matrix_snapshot=flow.matrix_data,
                        stage="closure",
                    ),
                ),
                "closure",
            )
            canonical = Path(check_type(target["targetDir"], str)) / "closure.json"
            flow.store.accept(
                "architecture:closure",
                (str(walk_path), binding),
                (path, canonical),
            )
            return {
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
        errors = flow.work / "closure.errors.json"
        write_json(errors, result)
        inputs += (str(errors),)
    raise flow.tools.failure(
        stage,
        "other",
        read(flow.work / "closure.errors.json"),
    )
