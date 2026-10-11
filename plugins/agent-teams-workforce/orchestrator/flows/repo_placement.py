"""Placement acceptance: element coverage, project boundaries and naming facts."""

from __future__ import annotations

import copy
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from placement_contract import (
    KEY_ITEM_ID,
    KEY_ITEM_IDS,
    KEY_MISSING_REPOS,
    KEY_NAME,
    KEY_NO_CODE,
    KEY_PLACEMENTS,
    KEY_PURPOSE,
    KEY_REASON,
    KEY_REPO_NAME,
    KEY_REPO_PATH,
    KEY_TEMPLATE,
    MissingRepo,
    NoCodeEntry,
    Placement,
    PlacementRuling,
    parse_placement_ruling,
)

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
        for path in (self.control, self.arch, self.marketing):
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

    def __init__(self, inputs: PlacementInputs, result: PlacementRuling) -> None:
        self.inputs: PlacementInputs = inputs
        self.result: PlacementRuling = result
        self.by_id: dict[str, dict[str, JsonValue]] = {check_type(item["id"], str): item for item in inputs.items}
        self.ids: set[str] = set(self.by_id)
        self.inventory: dict[str, dict[str, JsonValue]] = {
            check_type(repo["name"], str).casefold(): repo for repo in _objects(inputs.inventory["repos"])
        }
        self.missing: dict[str, MissingRepo] = {repo[KEY_NAME].casefold(): repo for repo in result[KEY_MISSING_REPOS]}
        self.findings: list[str] = []
        self.warnings: list[str] = []
        self.seen: list[str] = []

    def _missing_repositories(self, *, reused: bool) -> None:
        missing: list[MissingRepo] = self.result[KEY_MISSING_REPOS]
        if len(self.missing) != len(missing):
            self.findings.append("duplicate missing repository names")
        for repo in missing:
            name: str = repo[KEY_NAME]
            try:
                app_space(name, self.inputs.config)
            except (KeyError, ValueError) as exc:
                self.findings.append(str(exc))
            if not (name.strip() and repo[KEY_TEMPLATE].strip() and repo[KEY_PURPOSE].strip()):
                self.findings.append(f"{name}: missing name, template or purpose")
            if not reused and name.casefold() in self.inventory:
                self.findings.append(f"{name}: already exists in inventory")

    def _placement_path(self, placement: Placement) -> None:
        name: str = placement[KEY_REPO_NAME]
        named: dict[str, JsonValue] | None = self.inventory.get(name.casefold())
        raw_path: str | None = placement[KEY_REPO_PATH]
        if name.casefold().startswith("marketing-"):
            self.findings.append(f"{name}: marketing repository")
        if raw_path:
            repo_path: Path = Path(raw_path).expanduser().resolve()
            if not named or not named.get("path") or Path(check_type(named["path"], str)).resolve() != repo_path:
                self.findings.append(f"{name}: path {raw_path} is not in the inventory")
            if forbidden(repo_path, self.inputs.control, self.inputs.arch, self.inputs.marketing):
                self.findings.append(f"{name}: forbidden placement {repo_path}")
            placement[KEY_REPO_PATH] = str(repo_path)
        elif name.casefold() not in self.missing:
            self.findings.append(f"{name}: null path without a {KEY_MISSING_REPOS} entry")
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

    def _avoided(self, placement: Placement) -> None:
        name: str = placement[KEY_REPO_NAME]
        raw_path: str | None = placement[KEY_REPO_PATH]
        for excluded in self.inputs.avoid:
            matches_name: bool = check_type(excluded.get(KEY_REPO_NAME, ""), str).casefold() == name.casefold()
            excluded_path: JsonValue = excluded.get(KEY_REPO_PATH)
            matches_path: bool = bool(
                raw_path
                and excluded_path
                and Path(raw_path).resolve() == Path(check_type(excluded_path, str)).resolve(),
            )
            affected: set[str] = set(placement[KEY_ITEM_IDS]) & set(
                _strings(excluded.get(KEY_ITEM_IDS) or placement[KEY_ITEM_IDS]),
            )
            if (matches_name or matches_path) and affected:
                reason: JsonValue = excluded.get(KEY_REASON, "")
                self.findings.append(f"{name}: avoided placement of {sorted(affected)}: {reason}")

    def _placement(self, placement: Placement) -> None:
        name: str = placement[KEY_REPO_NAME]
        self._placement_path(placement)
        unknown: set[str] = set(placement[KEY_ITEM_IDS]) - self.ids
        if unknown:
            self.warnings.append(f"{name}: dropped unknown item ids {sorted(unknown)}")
        items: list[str] = [item for item in placement[KEY_ITEM_IDS] if item in self.ids]
        placement[KEY_ITEM_IDS] = list(items)
        self.seen.extend(items)
        self._avoided(placement)
        for item_id in items:
            element: str = " ".join(check_type(self.by_id[item_id]["element"], str).split()).casefold()
            recorded: JsonValue = self.inputs.rows.get(element, {}).get("repository")
            if recorded and check_type(recorded, str).casefold() != name.casefold():
                self.warnings.append(f"{item_id}: matrix repository {recorded}, placement {name}")

    def _coverage(self) -> None:
        clean_no_code: list[NoCodeEntry] = []
        for entry in self.result[KEY_NO_CODE]:
            item: str = entry[KEY_ITEM_ID]
            if item in self.ids:
                clean_no_code.append(entry)
                self.seen.append(item)
            else:
                self.warnings.append(f"dropped unknown {KEY_NO_CODE} item {item}")
        self.result[KEY_NO_CODE] = clean_no_code
        placements: list[Placement] = [p for p in self.result[KEY_PLACEMENTS] if p[KEY_ITEM_IDS]]
        self.result[KEY_PLACEMENTS] = list(placements)
        counts: Counter[str] = Counter(self.seen)
        self.findings.extend(f"{item}: placed {counts[item]} times" for item in sorted(self.ids) if counts[item] != 1)
        for name, repo in self.missing.items():
            actual: set[str] = {
                item for p in placements if p[KEY_REPO_NAME].casefold() == name for item in p[KEY_ITEM_IDS]
            }
            items: list[str] = [item for item in repo[KEY_ITEM_IDS] if item in self.ids]
            repo[KEY_ITEM_IDS] = list(items)
            if not actual or set(items) != actual:
                self.findings.append(f"{repo[KEY_NAME]}: {KEY_MISSING_REPOS} {KEY_ITEM_IDS} do not match placements")
        if not placements:
            self.findings.append("empty repository span")

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self, *, reused: bool) -> tuple[PlacementRuling, list[str]]:
        """Apply placement checks and return the normalized ruling.

        Returns:
            The accepted ruling and visible warnings.

        Raises:
            ValueError: The ruling violates placement requirements.

        """
        self._missing_repositories(reused=reused)
        for placement in self.result[KEY_PLACEMENTS]:
            self._placement(placement)
        self._coverage()
        if self.findings:
            message: str = "; ".join(self.findings)
            raise ValueError(message)
        return self.result, self.warnings


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def accept_placement(
    path: Path,
    inputs: PlacementInputs,
    *,
    reused: bool = False,
) -> tuple[PlacementRuling, list[str]]:
    """Validate and normalize a ruling against the supplied placement evidence.

    The ruling is validated against the placement contract's one schema by ``parse_placement_ruling``,
    which raises ``ValueError`` for a file that does not hold a ruling; a ruling that violates the
    placement requirements raises ``ValueError`` from the review.

    Returns:
        The accepted ruling and nonfatal placement warnings.

    """
    ruling: PlacementRuling = parse_placement_ruling(strict_json(path))
    review: _PlacementReview = _PlacementReview(inputs, copy.deepcopy(ruling))
    return review.run(reused=reused)
