#!/usr/bin/env python3
"""The UI design sources of a repository's spec, written into the saved spec document.

A repository's `ui` delta items each have a design source the detailing resolved: `bundle`
(a cds bundle the owner supplied, specified by its `spec/build-spec.md` and the Section IDs
the detailing resolved), `cds` (designed with the CDS design system) or `none` (no design
change). The script knows them, so it writes them into `spec-<slug>.md` itself, as one
`## UI design sources` section at the end of the document, replacing the section an earlier
run wrote. The build Tasks carry the same sources in their contracts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import contracts
from beadcontracts import UiAppendResult
from contracts import JsonValue
from typeguard import CollectionCheckStrategy, check_type, typechecked

#: The heading of the section this module writes.
_ARGUMENT_ERROR: str = "Arguments violate the specui input contract"


HEADING = "## UI design sources"


MAX_SECTION_LEVEL = 2


class SpecUiError(Exception):
    """The items argument is not a list of UI items."""


@dataclass(frozen=True)
class _UiSource:
    id: str
    design_source: Literal["bundle", "cds", "none"]
    build_spec: str | None
    sections: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or self.design_source not in {"bundle", "cds", "none"}:
            raise TypeError(_ARGUMENT_ERROR)
        if self.build_spec is not None and not isinstance(self.build_spec, str):
            raise TypeError(_ARGUMENT_ERROR)
        if not isinstance(self.sections, tuple) or any(not isinstance(value, str) for value in self.sections):
            raise TypeError(_ARGUMENT_ERROR)


def _items(raw: str) -> list[_UiSource]:
    """Parse the UI items argument.

    Returns:
        Each item as {id, designSource, buildSpec, sections}; an item that names no
        design source is a `bundle` item when it names a build spec, else a `cds` one.

    Raises:
        SpecUiError: The argument is not a JSON list; an entry with no id is left out.

    """
    x: JsonValue
    try:
        value: object = json.loads(raw)
    except ValueError as exc:
        msg: str = f"--items is not JSON: {exc}"
        raise SpecUiError(msg) from exc
    if not isinstance(value, list):
        msg = "--items is not a JSON list"
        raise SpecUiError(msg)
    items: list[_UiSource] = []
    entries: list[contracts.JsonValue] = check_type(
        value,
        list[JsonValue],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    for x in entries:
        if not isinstance(x, dict) or not str(x.get("id") or "").strip():
            continue
        raw_sections: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = x.get(
            "sections",
        )
        sections: list[str] = (
            check_type(raw_sections, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
            if raw_sections is not None
            else []
        )
        spec: str | None = check_type(x.get("buildSpec") or "", str).strip() or None
        source: Literal["bundle", "cds", "none"] = check_type(
            check_type(x.get("designSource") or "", str).strip() or ("bundle" if spec else "cds"),
            Literal["bundle", "cds", "none"],
        )
        items.append(
            _UiSource(
                id=check_type(x["id"], str).strip(),
                design_source=source,
                build_spec=spec,
                sections=tuple(item.strip() for item in sections if item.strip()),
            ),
        )
    return items


def _line(item: _UiSource) -> str:
    """One item of the section, as a markdown list entry.

    Returns:
        The entry.

    """
    if item.design_source == "bundle":
        sections: str = ", ".join(item.sections) or "none resolved"
        return f"- `{item.id}`: bundle; build spec `{item.build_spec or 'not resolved'}`; Section IDs {sections}"
    if item.design_source == "none":
        return f"- `{item.id}`: none; it changes no design"
    return f"- `{item.id}`: cds; designed with the CDS design system"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def spec_ui_append(doc: Path, raw_items: str) -> UiAppendResult:
    """Write the UI design sources section at the end of the saved spec document.

    Args:
        doc: The saved spec document, `spec-<slug>.md`.
        raw_items: The repository's `ui` items as JSON:
            [{id, designSource?, buildSpec?, sections?}].

    Returns:
        {ok, appended, summary}; `appended` counts the items written. With no items, or no
        saved document, nothing is written and `appended` is 0.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(doc, Path)) or not (isinstance(raw_items, str)):
        raise TypeError(_ARGUMENT_ERROR)
    items: list[_UiSource] = _items(raw_items)
    if not items or not doc.is_file():
        return {
            "ok": True,
            "appended": 0,
            "summary": {"ok": True, "appended": 0, "saved": doc.is_file()},
        }
    text: str = doc.read_text(encoding="utf-8", errors="replace")
    lines: list[str] = text.splitlines()
    start: int | None = next((i for i, line in enumerate(lines) if line.strip() == HEADING), None)
    if start is not None:
        end: int = next(
            (
                j
                for j in range(start + 1, len(lines))
                if lines[j].startswith("#") and len(lines[j]) - len(lines[j].lstrip("#")) <= MAX_SECTION_LEVEL
            ),
            len(lines),
        )
        lines = lines[:start] + lines[end:]
    body: str = "\n".join(lines).rstrip("\n")
    section: str = "\n".join([HEADING, "", *(_line(i) for i in items)])
    doc.write_text(f"{body}\n\n{section}\n", encoding="utf-8")
    return {
        "ok": True,
        "appended": len(items),
        "summary": {"ok": True, "appended": len(items), "saved": True},
    }
