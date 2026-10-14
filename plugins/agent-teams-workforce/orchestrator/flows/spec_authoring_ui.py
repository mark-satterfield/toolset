"""Normalize UI choices against the supplied bundles and repository placement."""

from __future__ import annotations

import re
from typing import TypeIs

import cdsbundles
from beadcontracts import Bundle, BundleListing
from recon_contract import (
    ARTIFACT_KINDS,
    DEFAULT_ARTIFACT_KIND,
    DEFAULT_DESIGN_SOURCE,
    DESIGN_SOURCE_BUNDLE,
    DESIGN_SOURCE_CDS,
    DESIGN_SOURCE_NONE,
    DESIGN_SOURCES,
    KEY_ARTIFACT,
    KEY_BUILD_SPEC,
    KEY_BUNDLE,
    KEY_DESIGN_SOURCE,
    KEY_ITEM,
    KEY_KIND,
    KEY_REASON,
    KEY_SECTIONS,
    KEY_SLUG,
    KEY_UI_ITEMS,
    ArtifactKind,
    DesignSource,
    UiArtifact,
    UiItem,
    violations,
)
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.tools import Tools

_ARGUMENT_ERROR: str = "Arguments violate the spec_authoring_ui input contract"
_UI_ITEM_DEFINITION: str = "UiItem"
_UI_ARTIFACT_DEFINITION: str = "UiArtifact"
_WARNINGS_KEY: str = "warnings"


def _design_source(value: JsonValue | None, item: str, warnings: list[str]) -> DesignSource:
    """Narrow a candidate design source to the recon contract's values.

    A value outside the contract takes the recon schema's default design source, with a warning.

    Returns:
        The design source.

    """
    source: DesignSource
    for source in DESIGN_SOURCES:
        if value == source:
            return source
    warnings.append(f"{item}: unknown design source {value!r}; using {DEFAULT_DESIGN_SOURCE}")
    return DEFAULT_DESIGN_SOURCE


def _artifact_kind(value: JsonValue | None) -> ArtifactKind | None:
    """Narrow a candidate artifact kind to the recon contract's values.

    Returns:
        The artifact kind, or None when the value is not one.

    """
    kind: ArtifactKind
    for kind in ARTIFACT_KINDS:
        if value == kind:
            return kind
    return None


def _artifact(value: JsonValue | None, item: str, warnings: list[str]) -> UiArtifact:
    """Keep a usable candidate artifact, or assign the default page artifact for the item.

    Returns:
        The artifact the item builds.

    """
    if isinstance(value, dict):
        kind: ArtifactKind | None = _artifact_kind(value.get(KEY_KIND))
        slug: JsonValue | None = value.get(KEY_SLUG)
        if kind is not None and isinstance(slug, str):
            kept: UiArtifact = {"kind": kind, "slug": slug}
            if not violations(kept, _UI_ARTIFACT_DEFINITION):
                return kept
    assigned: UiArtifact = {
        "kind": DEFAULT_ARTIFACT_KIND,
        "slug": re.sub(r"[^a-z0-9]+", "-", item.lower()).strip("-") or "item",
    }
    warnings.append(f"{item}: missing or invalid artifact; assigned {DEFAULT_ARTIFACT_KIND} {assigned['slug']}")
    return assigned


def _is_ui_item(value: object, errors: list[str]) -> TypeIs[UiItem]:
    """Validate one value against the recon schema's `UiItem` definition.

    Returns:
        True when the value conforms; each violation is appended to `errors`.

    """
    found: list[str] = violations(value, _UI_ITEM_DEFINITION)
    errors.extend(found)
    return not found


def _bundle_problem(
    row: dict[str, JsonValue],
    artifact: UiArtifact,
    supplied: dict[str, Bundle],
    tools: Tools,
) -> str | None:
    """Check a bundle item's bundle against the supplied bundles.

    Returns:
        Why the bundle cannot be used, or None when it can.

    """
    cited: JsonValue | None = row.get(KEY_BUNDLE)
    bundle_path: str | None = cited if isinstance(cited, str) and cited else None
    bundle: Bundle | None = supplied.get(bundle_path) if bundle_path else None
    if (
        bundle_path is None
        or bundle is None
        or (artifact["kind"], artifact["slug"]) != (bundle["kind"], bundle["slug"])
    ):
        return "not a supplied matching bundle"
    return check_type(
        tools.portfolio(
            "author",
            cdsbundles.bundle_problem,
            bundle_path,
            check_type(row.get(KEY_BUILD_SPEC) or "", str),
        ),
        str | None,
    )


def _normalized_item(
    row: dict[str, JsonValue],
    item: str,
    supplied: dict[str, Bundle],
    tools: Tools,
    warnings: list[str],
) -> UiItem:
    """Normalize one candidate item the Story builds.

    Returns:
        The item, validated against the recon schema's `UiItem`.

    Raises:
        ValueError: The normalized item does not conform to `UiItem`.

    """
    source: DesignSource = _design_source(row.get(KEY_DESIGN_SOURCE), item, warnings)
    artifact: UiArtifact | None = (
        None if source == DESIGN_SOURCE_NONE else _artifact(row.get(KEY_ARTIFACT), item, warnings)
    )
    if source == DESIGN_SOURCE_BUNDLE and artifact is not None:
        problem: str | None = _bundle_problem(row, artifact, supplied, tools)
        if problem:
            warnings.append(f"{item}: {problem}; using {DESIGN_SOURCE_CDS}")
            source = DESIGN_SOURCE_CDS
    normalized: dict[str, JsonValue] = {KEY_ITEM: item, KEY_DESIGN_SOURCE: source}
    reason: JsonValue | None = row.get(KEY_REASON)
    if isinstance(reason, str):
        normalized[KEY_REASON] = reason
    normalized[KEY_ARTIFACT] = None if artifact is None else {KEY_KIND: artifact["kind"], KEY_SLUG: artifact["slug"]}
    if source == DESIGN_SOURCE_BUNDLE:
        key: str
        for key in (KEY_BUNDLE, KEY_BUILD_SPEC, KEY_SECTIONS):
            if key in row:
                normalized[key] = row[key]
    errors: list[str] = []
    if not _is_ui_item(normalized, errors):
        msg: str = f"{item}: normalized ui item does not conform: {'; '.join(errors)}"
        raise ValueError(msg)
    return normalized


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def normalize_ui(
    candidate: dict[str, JsonValue],
    built_ids: set[str],
    bundles: dict[str, JsonValue],
    tools: Tools,
) -> dict[str, JsonValue]:
    """Keep what the Story builds and downgrade unusable bundle references to CDS.

    A candidate design source outside the contract takes the recon schema's default, and a
    missing or invalid artifact takes the default page artifact, each with a warning.

    Returns:
        Normalized UI items (the recon schema's `UiItem`) and visible fallback warnings.

    Raises:
        TypeError: An argument violates the declared input contract, the candidate has no
            `uiItems` list of objects with a string `item`, or the bundle listing violates its
            contract.

    """
    if (
        not (isinstance(candidate, dict))
        or not (isinstance(built_ids, set))
        or not (isinstance(bundles, dict))
        or not (isinstance(tools, Tools))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    listing: BundleListing = _bundle_listing(bundles)
    supplied: dict[str, Bundle] = {bundle["path"]: bundle for bundle in listing["bundles"]}
    warnings: list[str] = []
    rows: list[UiItem] = []
    original: dict[str, JsonValue]
    for original in _candidate_items(candidate):
        item: str = check_type(original[KEY_ITEM], str)
        if item not in built_ids:
            warnings.append(f"{item}: not something the Story builds; removed")
            continue
        rows.append(_normalized_item(original, item, supplied, tools, warnings))
    return json_object({KEY_UI_ITEMS: rows, _WARNINGS_KEY: warnings})


def _bundle_listing(bundles: dict[str, JsonValue]) -> BundleListing:
    """Narrow the bundle listing to the cdsbundles listing contract.

    Returns:
        The listing.

    Raises:
        TypeError: The listing violates `BundleListing`.

    """
    try:
        return check_type(bundles, BundleListing, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    except TypeCheckError as exc:
        msg: str = f"bundle listing violates the cdsbundles listing contract: {exc}"
        raise TypeError(msg) from exc


def _candidate_items(candidate: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """Narrow the candidate document's ui items, each with a string `item` key.

    Returns:
        The candidate's ui item rows.

    Raises:
        TypeError: `uiItems` is missing or not a list of objects, or a row has no string `item`.

    """
    rows: JsonValue | None = candidate.get(KEY_UI_ITEMS)
    if not isinstance(rows, list):
        msg: str = f"candidate spec-ui document has no {KEY_UI_ITEMS} list"
        raise TypeError(msg)
    found: list[dict[str, JsonValue]] = []
    index: int
    row: JsonValue
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get(KEY_ITEM), str):
            msg = f"candidate {KEY_UI_ITEMS}[{index}] is not an object with a string {KEY_ITEM}"
            raise TypeError(msg)
        found.append(row)
    return found
