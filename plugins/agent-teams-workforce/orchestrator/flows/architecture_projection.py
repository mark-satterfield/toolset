"""Project stable walk identities onto the matrix-dependent build roots."""

from __future__ import annotations

from ..core.matrix import row_for, satisfied
from ..core.models import StepError
from .architecture_closure import classify


def project(walk: dict, all_roots: dict, current_roots: dict, matrix: dict) -> dict:
    aliases = {}
    for row in all_roots.get("items", []):
        aliases[row["id"].casefold()] = row["element"]
        aliases[row["element"].casefold()] = row["element"]
    elements = {row["element"]: row for row in walk["elements"]}
    aliases.update({name.casefold(): name for name in elements})

    def resolve(name: str) -> str:
        if name.casefold() not in aliases:
            raise StepError("closure", "other", (f"Unknown walk reference: {name}",))
        return aliases[name.casefold()]

    roots = {row["element"] for row in current_roots.get("items", [])}
    graph = {name: set() for name in aliases.values()}
    evidence = {name: set() for name in aliases.values()}
    for row in walk["elements"]:
        name = row["element"]
        graph[name].update(resolve(ref) for ref in row["requires"])
        for ref in row["requiredBy"]:
            graph[resolve(ref)].add(name)
            evidence[resolve(ref)].update(row["evidence"])
    for edge in walk["rootEdges"]:
        evidence[resolve(edge["item"])].add(edge["evidence"])
        graph[resolve(edge["item"])].update(resolve(ref) for ref in edge["requires"])
    reached, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        if name not in roots and satisfied(matrix, row_for(matrix, name)):
            continue
        reached.add(name)
        pending.extend(graph[name] - reached)
    rows = []
    for name in sorted(reached - roots):
        if name not in elements:
            raise StepError("closure", "other", (f"Missing walk evidence for {name}",))
        rows.append(
            {
                **elements[name],
                "requires": sorted(graph[name] & reached),
                "requiredBy": sorted(
                    owner for owner in reached if name in graph[owner]
                ),
            }
        )
    result = classify(
        {
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
        },
        matrix,
    )
    result["satisfied"] = classify(walk, matrix)["satisfied"]
    return result
