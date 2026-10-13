"""The project boundary a repository of the span must satisfy."""

from __future__ import annotations

from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked


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
