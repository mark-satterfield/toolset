"""Placement acceptance: element coverage, project boundaries and naming facts."""

from __future__ import annotations

import copy
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import strict_json
from orchestrator.core.io import JsonValue, json_object


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _strings(value: object) -> list[str]:
    return check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def app_space(name: str, config: dict[str, JsonValue]) -> str:
    """Resolve an eligible application's space from the naming patterns.

    Returns:
        The configured application space.

    Raises:
        ValueError: The name does not identify an eligible application repository.

    """
    for pattern in _objects(json_object(config.get("repositories", {})).get("patterns", [])):
        if re.search(check_type(pattern["regex"], str), name):
            if pattern["kind"] != "application" or pattern.get("space") == "marketing":
                message = f"{name}: not an eligible application repository"
                raise ValueError(message)
            return check_type(pattern["space"], str)
    message = f"{name}: no application naming pattern"
    raise ValueError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def forbidden(path: Path, control: Path, arch: Path, marketing: Path) -> bool:
    """Check whether a path overlaps a protected repository or marketing tree.

    Returns:
        Whether this repository is forbidden for application placement.

    """
    path = path.resolve()
    control, arch, marketing = control.resolve(), arch.resolve(), marketing.resolve()
    return (
        path == control
        or path.is_relative_to(control)
        or arch.is_relative_to(path)
        or path.is_relative_to(arch)
        or path.is_relative_to(marketing)
    )


@dataclass(frozen=True)
class PlacementInputs:
    """Inventory, matrix intent, and path boundaries for a placement ruling."""

    schema: Path
    items: list[dict[str, JsonValue]]
    inventory: dict[str, JsonValue]
    rows: dict[str, dict[str, JsonValue]]
    config: dict[str, JsonValue]
    control: Path
    arch: Path
    marketing: Path
    avoid: list[dict[str, JsonValue]] = field(default_factory=list)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every input before using it in placement acceptance."""
        for path in (self.schema, self.control, self.arch, self.marketing):
            check_type(path, Path)
        _objects(self.items)
        _objects(self.avoid)
        json_object(self.inventory)
        json_object(self.config)
        check_type(
            self.rows,
            dict[str, dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )


class _PlacementReview:
    """Accumulate one ruling's findings without changing its input evidence."""

    def __init__(self, inputs: PlacementInputs, result: dict[str, JsonValue]) -> None:
        self.inputs = inputs
        self.result = result
        self.by_id = {check_type(item["id"], str): item for item in inputs.items}
        self.ids = set(self.by_id)
        self.inventory = {
            check_type(repo["name"], str).casefold(): repo for repo in _objects(inputs.inventory["repos"])
        }
        self.missing = {check_type(repo["name"], str).casefold(): repo for repo in _objects(result["missingRepos"])}
        self.findings: list[str] = []
        self.warnings: list[str] = []
        self.seen: list[str] = []

    def _missing_repositories(self, *, reused: bool) -> None:
        missing = _objects(self.result["missingRepos"])
        if len(self.missing) != len(missing):
            self.findings.append("duplicate missing repository names")
        for repo in missing:
            name = check_type(repo["name"], str)
            try:
                app_space(name, self.inputs.config)
            except (KeyError, ValueError) as exc:
                self.findings.append(str(exc))
            if not all(check_type(repo[key], str).strip() for key in ("name", "template", "purpose")):
                self.findings.append(f"{name}: missing name, template or purpose")
            if not reused and name.casefold() in self.inventory:
                self.findings.append(f"{name}: already exists in inventory")

    def _placement_path(self, placement: dict[str, JsonValue]) -> None:
        name = check_type(placement["repoName"], str)
        named = self.inventory.get(name.casefold())
        raw_path = check_type(placement["repoPath"], str | None)
        if name.casefold().startswith("marketing-"):
            self.findings.append(f"{name}: marketing repository")
        if raw_path:
            repo_path = Path(raw_path).expanduser().resolve()
            if not named or not named.get("path") or Path(check_type(named["path"], str)).resolve() != repo_path:
                self.findings.append(f"{name}: path {raw_path} is not in the inventory")
            if forbidden(repo_path, self.inputs.control, self.inputs.arch, self.inputs.marketing):
                self.findings.append(f"{name}: forbidden placement {repo_path}")
            placement["repoPath"] = str(repo_path)
        elif name.casefold() not in self.missing:
            self.findings.append(f"{name}: null path without a missingRepos entry")
        elif (
            named
            and named.get("path")
            and forbidden(
                Path(check_type(named["path"], str)),
                self.inputs.control,
                self.inputs.arch,
                self.inputs.marketing,
            )
        ):
            self.findings.append(f"{name}: forbidden inventory path {named['path']}")

    def _avoided(self, placement: dict[str, JsonValue]) -> None:
        name = check_type(placement["repoName"], str)
        raw_path = check_type(placement["repoPath"], str | None)
        for excluded in self.inputs.avoid:
            matches_name = check_type(excluded.get("repoName", ""), str).casefold() == name.casefold()
            matches_path = bool(
                raw_path
                and excluded.get("repoPath")
                and Path(raw_path).resolve() == Path(check_type(excluded["repoPath"], str)).resolve(),
            )
            affected = set(_strings(placement["itemIds"])) & set(
                _strings(excluded.get("itemIds") or placement["itemIds"]),
            )
            if (matches_name or matches_path) and affected:
                self.findings.append(f"{name}: avoided placement of {sorted(affected)}: {excluded.get('reason', '')}")

    def _placement(self, placement: dict[str, JsonValue]) -> None:
        name = check_type(placement["repoName"], str)
        self._placement_path(placement)
        unknown = set(_strings(placement["itemIds"])) - self.ids
        if unknown:
            self.warnings.append(f"{name}: dropped unknown item ids {sorted(unknown)}")
        items = [item for item in _strings(placement["itemIds"]) if item in self.ids]
        placement["itemIds"] = list(items)
        self.seen.extend(items)
        self._avoided(placement)
        for item_id in items:
            element = " ".join(check_type(self.by_id[item_id]["element"], str).split()).casefold()
            recorded = self.inputs.rows.get(element, {}).get("repository")
            if recorded and check_type(recorded, str).casefold() != name.casefold():
                self.warnings.append(f"{item_id}: matrix repository {recorded}, placement {name}")

    def _coverage(self) -> None:
        clean_no_code: list[JsonValue] = []
        for entry in _objects(self.result["noCode"]):
            item = check_type(entry["itemId"], str)
            if item in self.ids:
                clean_no_code.append(entry)
                self.seen.append(item)
            else:
                self.warnings.append(f"dropped unknown noCode item {item}")
        self.result["noCode"] = clean_no_code
        placements = [p for p in _objects(self.result["placements"]) if p["itemIds"]]
        self.result["placements"] = list(placements)
        counts = Counter(self.seen)
        self.findings.extend(f"{item}: placed {counts[item]} times" for item in sorted(self.ids) if counts[item] != 1)
        for name, repo in self.missing.items():
            actual = {
                item
                for p in placements
                if check_type(p["repoName"], str).casefold() == name
                for item in _strings(p["itemIds"])
            }
            items = [item for item in _strings(repo["itemIds"]) if item in self.ids]
            repo["itemIds"] = list(items)
            if not actual or set(items) != actual:
                self.findings.append(f"{repo['name']}: missingRepos itemIds do not match placements")
        if not placements:
            self.findings.append("empty repository span")

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self, *, reused: bool) -> tuple[dict[str, JsonValue], list[str]]:
        """Apply placement checks and return the normalized ruling.

        Returns:
            The accepted ruling and visible warnings.

        Raises:
            ValueError: The ruling violates placement requirements.

        """
        self._missing_repositories(reused=reused)
        for placement in _objects(self.result["placements"]):
            self._placement(placement)
        self._coverage()
        if self.findings:
            message = "; ".join(self.findings)
            raise ValueError(message)
        return self.result, self.warnings


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def accept_placement(
    path: Path,
    inputs: PlacementInputs,
    *,
    reused: bool = False,
) -> tuple[dict[str, JsonValue], list[str]]:
    """Validate and normalize a ruling against the supplied placement evidence.

    Returns:
        The accepted ruling and nonfatal placement warnings.

    """
    value = strict_json(path)
    jsonschema.validate(value, strict_json(inputs.schema))
    review = _PlacementReview(inputs, copy.deepcopy(value))
    return review.run(reused=reused)
