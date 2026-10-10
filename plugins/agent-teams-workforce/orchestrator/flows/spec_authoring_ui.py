"""Normalize UI choices against the supplied bundles and repository placement."""

from __future__ import annotations

import re

import cdsbundles
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.tools import Tools

_ARGUMENT_ERROR: str = "Arguments violate the spec_authoring_ui input contract"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def normalize_ui(
    candidate: dict[str, JsonValue],
    placed: set[str],
    bundles: dict[str, JsonValue],
    tools: Tools,
) -> dict[str, JsonValue]:
    """Keep placed items and downgrade unusable bundle references to CDS.

    Returns:
        Normalized UI items and visible fallback warnings.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    warnings: list[str]
    rows: list[dict[str, int | float | str | list[JsonValue] | dict[str, JsonValue] | None]]
    original: dict[str, JsonValue]
    if (
        not (isinstance(candidate, dict))
        or not (isinstance(placed, set))
        or not (isinstance(bundles, dict))
        or not (isinstance(tools, Tools))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    warnings, rows = [], []
    supplied: dict[str, dict[str, JsonValue]] = {
        check_type(row["path"], str): row
        for row in check_type(
            bundles["bundles"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    }
    for original in check_type(
        candidate["uiItems"],
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        row: dict[str, int | float | str | list[JsonValue] | dict[str, JsonValue] | None] = dict(original)
        item: str = check_type(row["item"], str)
        if item not in placed:
            warnings.append(f"{item}: not a placed item; removed")
            continue
        source: int | float | str | list[JsonValue] | dict[str, JsonValue] | None = row["designSource"]
        if source not in {"bundle", "cds", "none"}:
            warnings.append(f"{item}: unknown design source; using cds")
            source = "cds"
        artifact_value: int | float | str | list[JsonValue] | dict[str, JsonValue] | None = row.get("artifact")
        artifact: dict[str, JsonValue] | None = json_object(artifact_value) if artifact_value is not None else None
        if source in {"bundle", "cds"} and (
            not artifact or artifact.get("kind") not in {"page", "shell", "view"} or not artifact.get("slug")
        ):
            artifact = {
                "kind": "page",
                "slug": re.sub(r"[^a-z0-9]+", "-", item.lower()).strip("-") or "item",
            }
            warnings.append(
                f"{item}: missing artifact; assigned page {artifact['slug']}",
            )
        if source == "bundle":
            bundle: dict[str, JsonValue] | None = supplied.get(check_type(row.get("bundle"), str | None))
            problem: str = "not a supplied matching bundle"
            if bundle and artifact == {"kind": bundle["kind"], "slug": bundle["slug"]}:
                problem = check_type(
                    tools.portfolio(
                        "author",
                        cdsbundles.bundle_problem,
                        check_type(row["bundle"], str),
                        check_type(row.get("buildSpec") or "", str),
                    ),
                    str | None,
                )
            if problem:
                warnings.append(f"{item}: {problem}; using cds")
                source = "cds"
        row["designSource"] = source
        row["artifact"] = artifact
        if source != "bundle":
            row.pop("bundle", None)
            row.pop("buildSpec", None)
            row.pop("sections", None)
        rows.append(row)
    return json_object({"uiItems": rows, "warnings": warnings})
