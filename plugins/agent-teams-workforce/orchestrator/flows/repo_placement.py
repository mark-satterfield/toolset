"""The project boundary a repository of the span must satisfy."""

from __future__ import annotations

from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def forbidden(path: Path, control: Path, arch: Path) -> bool:
    """Check whether a path overlaps a protected repository: the control repository or the architecture folder.

    Returns:
        Whether this repository is forbidden for application placement.

    """
    path = path.resolve()
    control, arch = control.resolve(), arch.resolve()
    return path == control or path.is_relative_to(control) or arch.is_relative_to(path) or path.is_relative_to(arch)
