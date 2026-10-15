"""Atomic, validated JSON files used by the dispatch boundary."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, check_type

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

WORK_DIRECTORY_PARTS: Final[tuple[str, ...]] = (".claude", "workflow-runs", "artifacts")
"""Where, inside the control repository, the work directory of every Epic is held."""
SAFE_KEY_LENGTH: Final = 120


def safe_key(identifier: str) -> str:
    """Turn an identifier into a name that is safe as one path segment.

    Returns:
        The identifier with every run of other characters replaced by one underscore, without
        leading or trailing underscores, cut to 120 characters.

    """
    return re.sub(r"^_+|_+$", "", re.sub(r"[^A-Za-z0-9._-]+", "_", identifier))[:SAFE_KEY_LENGTH]


def work_directory(control: Path, bead: str) -> Path:
    """Name the work directory of one Epic.

    Args:
        control: The control repository.
        bead: The Epic.

    Returns:
        ``<control>/.claude/workflow-runs/artifacts/<bead>``, the bead made safe as a path segment.

    Raises:
        ValueError: The bead leaves no safe name.

    """
    name: str = safe_key(bead)
    if not name:
        message: str = f"the bead id {bead!r} names no work directory"
        raise ValueError(message)
    return control.joinpath(*WORK_DIRECTORY_PARTS, name)


def json_object(value: object) -> dict[str, JsonValue]:
    """Validate every JSON value in an object.

    Returns:
        The validated JSON object.

    """
    return check_type(value, dict[str, JsonValue], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


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
