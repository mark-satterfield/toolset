"""Project stable walk identities onto the matrix-dependent build roots."""

from __future__ import annotations

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.matrix import row_for, satisfied
from orchestrator.core.models import StepError


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def classify(walk: dict[str, JsonValue], matrix: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Classify.

    Returns:
        The validated architecture result.

    """
    prerequisites, complete = [], []
    for element in check_type(
        walk["elements"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        row = row_for(matrix, check_type(element["element"], str))
        if satisfied(matrix, row):
            complete.append(
                {
                    "element": element["element"],
                    "state": row["state"],
                    "repository": row.get("repository"),
                    "task": row.get("task"),
                    "commit": row.get("commit"),
                },
            )
        else:
            prerequisites.append(
                {**element, "state": "unknown", "repository": row.get("repository")},
            )
    return json_object({
        "prerequisites": prerequisites,
        "satisfied": complete,
        "rootEdges": walk["rootEdges"],
        "summary": walk["summary"],
    })


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def project(
    walk: dict[str, JsonValue],
    all_roots: dict[str, JsonValue],
    current_roots: dict[str, JsonValue],
    matrix: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Project.

    Returns:
        The validated architecture result.

    Raises:
        StepError: A referenced element lacks walk evidence.

    """
    stage = "closure"
    aliases: dict[str, str] = {}
    for row in check_type(
        all_roots.get("items", []),
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        aliases[check_type(row["id"], str).casefold()] = check_type(row["element"], str)
        aliases[check_type(row["element"], str).casefold()] = check_type(row["element"], str)
    elements = {
        check_type(row["element"], str): row
        for row in check_type(
            walk["elements"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    }
    aliases.update({name.casefold(): name for name in elements})

    def resolve(name: str) -> str:
        if name.casefold() not in aliases:
            raise StepError(stage, "other", (f"Unknown walk reference: {name}",))
        return aliases[name.casefold()]

    roots = {
        check_type(row["element"], str)
        for row in check_type(
            current_roots.get("items", []),
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    }
    graph: dict[str, set[str]] = {name: set() for name in aliases.values()}
    evidence: dict[str, set[str]] = {name: set() for name in aliases.values()}
    for row in check_type(
        walk["elements"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        name = check_type(row["element"], str)
        graph[name].update(
            resolve(ref)
            for ref in check_type(
                row["requires"],
                list[str],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        )
        for ref in check_type(
            row["requiredBy"],
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ):
            graph[resolve(ref)].add(name)
            evidence[resolve(ref)].update(
                check_type(row["evidence"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS),
            )
    for edge in check_type(
        walk["rootEdges"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        evidence[resolve(check_type(edge["item"], str))].add(check_type(edge["evidence"], str))
        graph[resolve(check_type(edge["item"], str))].update(
            resolve(ref)
            for ref in check_type(
                edge["requires"],
                list[str],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        )
    reached = _reachable(graph, roots, matrix)
    rows = []
    for name in sorted(reached - roots):
        if name not in elements:
            raise StepError(stage, "other", (f"Missing walk evidence for {name}",))
        rows.append(
            {
                **elements[name],
                "requires": sorted(graph[name] & reached),
                "requiredBy": sorted(owner for owner in reached if name in graph[owner]),
            },
        )
    result = classify(
        json_object({
            "elements": rows,
            "rootEdges": [
                {
                    "item": name,
                    "requires": sorted(graph[name] & reached),
                    "evidence": "; ".join(sorted(evidence[name])),
                }
                for name in sorted(roots)
            ],
            "summary": walk["summary"],
        }),
        matrix,
    )
    result["satisfied"] = classify(walk, matrix)["satisfied"]
    return result


def _reachable(graph: dict[str, set[str]], roots: set[str], matrix: dict[str, JsonValue]) -> set[str]:
    reached, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        if name not in roots and satisfied(matrix, row_for(matrix, name)):
            continue
        reached.add(name)
        pending.extend(graph[name] - reached)
    return reached
