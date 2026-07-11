# SPDX-License-Identifier: Apache-2.0
# Adapted from the OKF reference agent (Google Cloud Knowledge Catalog),
# licensed under Apache License 2.0:
# https://github.com/GoogleCloudPlatform/knowledge-catalog
# See NOTICE.md in this directory.
"""Concept addressing: a concept id is the tuple of path segments under the
bundle root, sans the `.md` suffix (e.g. `('tables', 'orders')` ->
`tables/orders.md`)."""
from __future__ import annotations

import re
from pathlib import Path

_SEGMENT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\- ]*")


def _validate_segment(seg: str) -> None:
    if not _SEGMENT_RE.fullmatch(seg):
        raise ValueError(f"Invalid concept id segment: {seg!r}")


def concept_id_to_path(bundle_root: Path, concept_id: tuple[str, ...]) -> Path:
    if not concept_id:
        raise ValueError("concept_id must have at least one segment")
    for seg in concept_id:
        _validate_segment(seg)
    *dirs, name = concept_id
    return bundle_root.joinpath(*dirs, f"{name}.md")


def path_to_concept_id(bundle_root: Path, path: Path) -> tuple[str, ...]:
    rel = path.relative_to(bundle_root).with_suffix("")
    return tuple(rel.parts)


def parse_concept_id(s: str) -> tuple[str, ...]:
    parts = tuple(p for p in s.split("/") if p)
    if not parts:
        raise ValueError(f"Empty concept id: {s!r}")
    for p in parts:
        _validate_segment(p)
    return parts
