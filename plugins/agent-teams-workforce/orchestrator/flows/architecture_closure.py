"""Join the view-only dependency walk to the run's immutable matrix snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from ..core.io import write_json
from ..core.matrix import element_id, row_for, satisfied
from .architecture_support import Architecture, read


def classify(walk: dict, matrix: dict) -> dict:
    prerequisites, complete = [], []
    for element in walk["elements"]:
        row = row_for(matrix, element["element"])
        if satisfied(matrix, row):
            complete.append(
                {
                    "element": element["element"],
                    "state": row["state"],
                    "repository": row.get("repository"),
                    "task": row.get("task"),
                    "commit": row.get("commit"),
                }
            )
        else:
            prerequisites.append(
                {**element, "state": "unknown", "repository": row.get("repository")}
            )
    return {
        "prerequisites": prerequisites,
        "satisfied": complete,
        "rootEdges": walk["rootEdges"],
        "summary": walk["summary"],
    }


def closure(flow: Architecture, target: dict) -> dict:
    roots = flow.call(
        "archstate",
        "delta_items",
        target["deltaDir"],
        with_closure=False,
        matrix_snapshot=flow.matrix_data,
        stage="closure",
    )
    roots_path = flow.work / "closure-roots.json"
    write_json(roots_path, roots)
    walk_path = flow.work / "closure-walk.json"
    inputs = (str(roots_path), str(flow.arch / "arc42"), str(flow.prd))
    for attempt in range(2):
        walk = flow.agent(
            "prd-reality-reconciler",
            walk_path,
            "closure-walk",
            inputs,
            "Walk architecture prerequisites from the build roots.",
        )
        elements = [element_id(row["element"]) for row in walk["elements"]]
        binding = "matrix-rows:" + json.dumps(
            {"matrix": str(flow.matrix), "elements": elements},
            sort_keys=True,
            separators=(",", ":"),
        )
        classified = classify(walk, flow.matrix_data)
        path = flow.work / "closure.json"
        write_json(path, classified)
        result = flow.call(
            "archclosure",
            "write_closure",
            classified,
            target["deltaDir"],
            dry_run=True,
            matrix_snapshot=flow.matrix_data,
            stage="closure",
        )
        if (
            not result.get("refused")
            and not result.get("error")
            and result.get("ok") is not False
        ):
            result = flow.checked(
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
            canonical = Path(target["targetDir"]) / "closure.json"
            flow.store.accept(
                "architecture:closure", (str(walk_path), binding), (path, canonical)
            )
            return {
                "path": str(canonical),
                "workPath": str(path),
                "prerequisites": len(classified["prerequisites"]),
            }
        errors = flow.work / "closure.errors.json"
        write_json(errors, result)
        inputs += (str(errors),)
    raise flow.tools.failure(
        "closure", "other", read(flow.work / "closure.errors.json")
    )
