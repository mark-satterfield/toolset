"""Project boundaries and naming facts a repository of the span must satisfy."""

from __future__ import annotations

import re
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


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
