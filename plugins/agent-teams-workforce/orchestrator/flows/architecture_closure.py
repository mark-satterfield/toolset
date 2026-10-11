"""Join the view-only dependency walk to the run's immutable matrix snapshot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import archclosure
import archstate
from target_contract import (
    CLOSURE_FILE,
    CLOSURE_ROOTS_FILE,
    KEY_DELTA_DIR,
    KEY_ELEMENT,
    KEY_ITEMS,
    KEY_PREREQUISITES,
    KEY_TARGET_DIR,
    DeltaItem,
    DeltaResult,
    load_delta_report,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.matrix import element_id
from orchestrator.flows.architecture_projection import project
from orchestrator.flows.architecture_support import Architecture, ArchitectureStep, read


def _root_elements(roots: DeltaResult) -> frozenset[str]:
    """Name the matrix elements of the closure build roots.

    Returns:
        The element id of every item in closure-roots.json.

    Raises:
        TypeError: The roots report is not a mapping.

    """
    if not isinstance(roots, dict):
        message: str = "_root_elements: closure roots must be a validated DeltaResult"
        raise TypeError(message)
    items: list[DeltaItem] = roots.get(KEY_ITEMS, [])
    return frozenset(element_id(item[KEY_ELEMENT]) for item in items)


def _matrix_binding(matrix: Path, walk: dict[str, JsonValue], root_elements: frozenset[str]) -> str:
    """Bind the walk to the matrix rows of every element it and the roots name.

    Returns:
        The matrix-rows binding string the artifact store records for the closure.

    Raises:
        TypeError: An argument is not of its declared type.

    """
    if not isinstance(matrix, Path) or not isinstance(walk, dict) or not isinstance(root_elements, frozenset):
        message: str = "_matrix_binding: arguments do not satisfy the declared input contract"
        raise TypeError(message)
    walk_rows: list[dict[str, JsonValue]] = check_type(
        walk["elements"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    elements: list[str] = sorted(
        {element_id(check_type(row[KEY_ELEMENT], str)) for row in walk_rows} | root_elements,
    )
    return "matrix-rows:" + json.dumps(
        {"matrix": str(matrix), "elements": elements},
        sort_keys=True,
        separators=(",", ":"),
    )


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
            check_type(target[KEY_DELTA_DIR], str),
            with_closure=False,
            matrix_snapshot={"elements": {}},
        ),
    )
    roots_path: Path = flow.work / CLOSURE_ROOTS_FILE
    write_json(roots_path, roots)
    root_elements: frozenset[str] = _root_elements(load_delta_report(roots_path))
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
        binding: str = _matrix_binding(flow.matrix, walk, root_elements)

        current_roots: dict[str, JsonValue] = json_object(
            flow.call(
                "closure",
                archstate.delta_items,
                check_type(target[KEY_DELTA_DIR], str),
                with_closure=False,
                matrix_snapshot=flow.matrix_data,
            ),
        )
        classified: dict[str, JsonValue] = project(walk, roots, current_roots, flow.matrix_data)
        path: Path = flow.work / CLOSURE_FILE
        write_json(path, classified)
        result: dict[str, JsonValue] = json_object(
            flow.call(
                "closure",
                archclosure.write_closure,
                classified,
                check_type(target[KEY_DELTA_DIR], str),
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
                        check_type(target[KEY_DELTA_DIR], str),
                        matrix_snapshot=flow.matrix_data,
                    ),
                ),
                "closure",
            )
            canonical: Path = Path(check_type(target[KEY_TARGET_DIR], str)) / CLOSURE_FILE
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
                        classified[KEY_PREREQUISITES],
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
        OTHER_CAUSE,
        read(flow.work / "closure.errors.json"),
    )
