"""Pure architecture projections of the dispatch's element matrix snapshot."""

from __future__ import annotations

import typing
from collections.abc import Mapping, Sequence
from pathlib import Path

import contracts
from archcatalog import read_catalog
from contracts import JsonObject
from typeguard import CollectionCheckStrategy, check_type, typechecked


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def element_id(name: str) -> str:
    """Match catalog names using the matrix's canonical identifier rule.

    Returns:
        The canonical element identifier.

    Raises:
        TypeError: The element name is not a string.

    """
    if not isinstance(name, str):
        message: str = "Element names must be strings"
        raise TypeError(message)
    return " ".join(name.split()).casefold()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def satisfied(snapshot: JsonObject, row: JsonObject) -> bool:
    """Require deployment for repositories with stacks; libraries need built code.

    Returns:
        Whether the recorded element satisfies its required build state.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(snapshot, dict)) or not (isinstance(row, dict)):
        argument_error: str = "satisfied: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    if row.get("state") == "deployed":
        return True
    if row.get("state") != "built" or not row.get("repository"):
        return False
    repository: str = element_id(check_type(row["repository"], str))
    rows: dict[str, contracts.JsonObject] = check_type(
        snapshot.get("elements", {}),
        dict[str, JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    owner: dict[str, contracts.JsonValue] = rows.get(f"repository:{repository}", {})
    if not owner or owner.get("stacksError"):
        return False
    return not any(
        str(key).startswith("stack:")
        for key in check_type(
            owner.get("contains", []),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    ) and not any(key.startswith(f"stack:{repository}/") for key in rows)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def catalog_elements(documents: Sequence[Mapping[str, contracts.JsonValue]]) -> dict[str, list[str]]:
    """Map element names to cited views, using the architecture catalog reader.

    Returns:
        Each catalog element and the paths of views citing it.

    Raises:
        TypeError: A document or its required path has an invalid type.

    """
    document: typing.Mapping[str, contracts.JsonValue]
    name: str
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        message: str = "Catalog documents must be a sequence of document mappings"
        raise TypeError(message)
    elements: dict[str, list[str]] = {}
    for document in documents:
        if not isinstance(document, Mapping):
            message = "Each catalog document must be a mapping"
            raise TypeError(message)
        raw_path: contracts.JsonValue = document.get("path")
        if not isinstance(raw_path, str):
            message = "Each catalog document requires a string path"
            raise TypeError(message)
        path: Path = Path(raw_path)
        catalog: contracts.CatalogRecord = read_catalog(path)
        names: list[str] = catalog["shows"] or ([catalog["subject"]] if catalog["subject"] else [])
        for name in names:
            elements.setdefault(name, []).append(str(path))
    return elements
