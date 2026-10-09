"""Normalize UI choices against the supplied bundles and repository placement."""

from __future__ import annotations

import re

from ..core.tools import Tools


def normalize_ui(
    candidate: dict, placed: set[str], bundles: dict, tools: Tools
) -> dict:
    """Keep only placed items and downgrade unusable bundle references to CDS."""
    warnings, rows = [], []
    supplied = {row["path"]: row for row in bundles["bundles"]}
    for original in candidate["uiItems"]:
        row = dict(original)
        item = row["item"]
        if item not in placed:
            warnings.append(f"{item}: not a placed item; removed")
            continue
        source = row["designSource"]
        if source not in {"bundle", "cds", "none"}:
            warnings.append(f"{item}: unknown design source; using cds")
            source = "cds"
        artifact = row.get("artifact")
        if source in {"bundle", "cds"} and (
            not artifact
            or artifact.get("kind") not in {"page", "shell", "view"}
            or not artifact.get("slug")
        ):
            artifact = {
                "kind": "page",
                "slug": re.sub(r"[^a-z0-9]+", "-", item.lower()).strip("-") or "item",
            }
            warnings.append(
                f"{item}: missing artifact; assigned page {artifact['slug']}"
            )
        if source == "bundle":
            bundle = supplied.get(row.get("bundle"))
            problem = "not a supplied matching bundle"
            if bundle and artifact == {"kind": bundle["kind"], "slug": bundle["slug"]}:
                problem = tools.portfolio(
                    "cdsbundles",
                    "bundle_problem",
                    row["bundle"],
                    row.get("buildSpec") or "",
                    stage="author",
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
    return {"uiItems": rows, "warnings": warnings}
