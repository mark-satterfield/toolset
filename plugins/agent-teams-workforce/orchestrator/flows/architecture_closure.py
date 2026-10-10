"""Join the view-only dependency walk to the run's immutable matrix snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import archclosure
import archstate
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)) or not (isinstance(target, dict)):
        argument_error: str = "closure: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    stage: str = "closure"
    roots: dict[str, JsonValue] = json_object(
        flow.call(
            "closure",
            archstate.delta_items,
            check_type(target["deltaDir"], str),
            with_closure=False,
            matrix_snapshot={"elements": {}},
        ),
    )
    roots_path: Path = flow.work / "closure-roots.json"
    write_json(roots_path, roots)
    walk_path: Path = flow.work / "closure-walk.json"
    inputs: tuple[str, ...] = (str(roots_path), str(flow.arch / "arc42"), str(flow.prd))
    for _ in range(2):
        walk: dict[str, JsonValue] = flow.agent(
            ArchitectureStep(
                "prd-reality-reconciler",
                walk_path,
                "closure-walk",
                inputs,
                "Walk architecture prerequisites from the build roots.",
            ),
        )
        elements: list[str] = sorted(
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
        binding: str = "matrix-rows:" + json.dumps(
            {"matrix": str(flow.matrix), "elements": elements},
            sort_keys=True,
            separators=(",", ":"),
        )

        current_roots: dict[str, JsonValue] = json_object(
            flow.call(
                "closure",
                archstate.delta_items,
                check_type(target["deltaDir"], str),
                with_closure=False,
                matrix_snapshot=flow.matrix_data,
            ),
        )
        classified: dict[str, JsonValue] = project(walk, roots, current_roots, flow.matrix_data)
        path: Path = flow.work / "closure.json"
        write_json(path, classified)
        result: dict[str, JsonValue] = json_object(
            flow.call(
                "closure",
                archclosure.write_closure,
                classified,
                check_type(target["deltaDir"], str),
                dry_run=True,
                matrix_snapshot=flow.matrix_data,
            ),
        )
        if not result.get("refused") and not result.get("error") and result.get("ok") is not False:
            result = flow.checked(
                json_object(
                    flow.call(
                        "closure",
                        archclosure.write_closure,
                        classified,
                        check_type(target["deltaDir"], str),
                        matrix_snapshot=flow.matrix_data,
                    ),
                ),
                "closure",
            )
            canonical: Path = Path(check_type(target["targetDir"], str)) / "closure.json"
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
        errors: Path = flow.work / "closure.errors.json"
        write_json(errors, result)
        inputs += (str(errors),)
    raise flow.tools.failure(
        stage,
        "other",
        read(flow.work / "closure.errors.json"),
    )
