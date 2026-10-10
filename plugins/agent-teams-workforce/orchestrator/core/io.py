"""Atomic, validated JSON files used by the dispatch boundary."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def json_object(value: object) -> dict[str, JsonValue]:
    """Validate every JSON value in an object.

    Returns:
        The validated JSON object.

    """
    return check_type(value, dict[str, JsonValue], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_json(path: Path, payload: object) -> None:
    """Atomically write a JSON value after validating its entire value tree."""
    checked = check_type(payload, JsonValue, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(checked, handle, sort_keys=True, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
