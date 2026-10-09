"""Placement acceptance: element coverage, project boundaries and naming facts."""

from __future__ import annotations

import copy
import re
from collections import Counter
from pathlib import Path

import jsonschema

from ..core.agents import strict_json


def app_space(name: str, config: dict) -> str:
    for pattern in config.get("repositories", {}).get("patterns", []):
        if re.search(pattern["regex"], name):
            if pattern["kind"] != "application" or pattern.get("space") == "marketing":
                raise ValueError(f"{name}: not an eligible application repository")
            return pattern["space"]
    raise ValueError(f"{name}: no application naming pattern")


def forbidden(path: Path, control: Path, arch: Path, marketing: Path) -> bool:
    path = path.resolve()
    control, arch, marketing = control.resolve(), arch.resolve(), marketing.resolve()
    return (
        path == control
        or path.is_relative_to(control)
        or arch.is_relative_to(path)
        or path.is_relative_to(arch)
        or path.is_relative_to(marketing)
    )


def accept_placement(
    path: Path,
    schema: Path,
    items: list[dict],
    inventory: dict,
    rows: dict,
    config: dict,
    control: Path,
    arch: Path,
    marketing: Path,
    *,
    reused: bool = False,
    avoid: list[dict] | None = None,
) -> tuple[dict, list[str]]:
    value = strict_json(path)
    jsonschema.validate(value, strict_json(schema))
    result = copy.deepcopy(value)
    ids = {item["id"] for item in items}
    inventory_by_name = {repo["name"].casefold(): repo for repo in inventory["repos"]}
    missing = {repo["name"].casefold(): repo for repo in result["missingRepos"]}
    findings, warnings = [], []
    if len(missing) != len(result["missingRepos"]):
        findings.append("duplicate missing repository names")
    for repo in result["missingRepos"]:
        name = repo["name"]
        try:
            app_space(name, config)
        except (KeyError, ValueError) as exc:
            findings.append(str(exc))
        if (
            not name.strip()
            or not repo["template"].strip()
            or not repo["purpose"].strip()
        ):
            findings.append(f"{name}: missing name, template or purpose")
        if not reused and name.casefold() in inventory_by_name:
            findings.append(f"{name}: already exists in inventory")
    seen = []
    by_id = {item["id"]: item for item in items}
    for placement in result["placements"]:
        name = placement["repoName"]
        named = inventory_by_name.get(name.casefold())
        raw_path = placement["repoPath"]
        if name.casefold().startswith("marketing-"):
            findings.append(f"{name}: marketing repository")
        if raw_path:
            repo_path = Path(raw_path).expanduser().resolve()
            if (
                not named
                or not named.get("path")
                or Path(named["path"]).resolve() != repo_path
            ):
                findings.append(f"{name}: path {raw_path} is not in the inventory")
            if forbidden(repo_path, control, arch, marketing):
                findings.append(f"{name}: forbidden placement {repo_path}")
            placement["repoPath"] = str(repo_path)
        elif name.casefold() not in missing:
            findings.append(f"{name}: null path without a missingRepos entry")
        elif named and named.get("path"):
            if forbidden(Path(named["path"]), control, arch, marketing):
                findings.append(f"{name}: forbidden inventory path {named['path']}")
        unknown = set(placement["itemIds"]) - ids
        if unknown:
            warnings.append(f"{name}: dropped unknown item ids {sorted(unknown)}")
        placement["itemIds"] = [item for item in placement["itemIds"] if item in ids]
        seen.extend(placement["itemIds"])
        for excluded in avoid or []:
            matches_name = excluded.get("repoName", "").casefold() == name.casefold()
            matches_path = bool(
                raw_path
                and excluded.get("repoPath")
                and Path(raw_path).resolve() == Path(excluded["repoPath"]).resolve()
            )
            affected = set(placement["itemIds"]) & set(
                excluded.get("itemIds") or placement["itemIds"]
            )
            if (matches_name or matches_path) and affected:
                findings.append(
                    f"{name}: avoided placement of {sorted(affected)}: {excluded.get('reason', '')}"
                )
        for item_id in placement["itemIds"]:
            element = " ".join(by_id[item_id]["element"].split()).casefold()
            recorded = rows.get(element, {}).get("repository")
            if recorded and recorded.casefold() != name.casefold():
                warnings.append(
                    f"{item_id}: matrix repository {recorded}, placement {name}"
                )
    clean_no_code = []
    for entry in result["noCode"]:
        if entry["itemId"] in ids:
            clean_no_code.append(entry)
            seen.append(entry["itemId"])
        else:
            warnings.append(f"dropped unknown noCode item {entry['itemId']}")
    result["noCode"] = clean_no_code
    result["placements"] = [p for p in result["placements"] if p["itemIds"]]
    counts = Counter(seen)
    findings.extend(
        f"{item}: placed {counts[item]} times"
        for item in sorted(ids)
        if counts[item] != 1
    )
    for name, repo in missing.items():
        actual = {
            i
            for p in result["placements"]
            if p["repoName"].casefold() == name
            for i in p["itemIds"]
        }
        repo["itemIds"] = [i for i in repo["itemIds"] if i in ids]
        if not actual or set(repo["itemIds"]) != actual:
            findings.append(
                f"{repo['name']}: missingRepos itemIds do not match placements"
            )
    if not result["placements"]:
        findings.append("empty repository span")
    if findings:
        raise ValueError("; ".join(findings))
    return result, warnings
