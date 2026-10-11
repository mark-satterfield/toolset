#!/usr/bin/env python3
"""The UI design sources of a repository's spec, written into the saved spec document.

A repository's `ui` delta items each have a design source the detailing resolved, as the
artifact-handoff skill's recon schema defines it (`UiItem`). The script writes them into
`spec-<slug>.md` itself, as one `## UI design sources` section at the end of the document,
replacing the section an earlier run wrote. The build Tasks carry the same sources in their
contracts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypeIs

from beadcontracts import UiAppendResult
from typeguard import CollectionCheckStrategy, typechecked

# The per-repository detailing contract (its ui items) is generated into the artifact-handoff skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))

# isort: split
from recon_contract import (
    DESIGN_SOURCE_BUNDLE,
    DESIGN_SOURCE_CDS,
    DESIGN_SOURCE_NONE,
    KEY_UI_ITEMS,
    DesignSource,
    UiItem,
    violations,
)

_ARGUMENT_ERROR: str = "Arguments violate the specui input contract"

#: The heading of the section this module writes.
HEADING = "## UI design sources"


MAX_SECTION_LEVEL = 2

_UI_ITEM_DEFINITION: str = "UiItem"


class SpecUiError(Exception):
    """The UI design sources document cannot be read or does not hold valid UI items."""


def _is_ui_item(value: object, errors: list[str]) -> TypeIs[UiItem]:
    """Validate one decoded value against the recon schema's `UiItem` definition.

    Returns:
        True when the value conforms; each violation is appended to `errors`.

    """
    found: list[str] = violations(value, _UI_ITEM_DEFINITION)
    errors.extend(found)
    return not found


def _items(path: Path) -> list[UiItem]:
    """Read the UI items of a saved UI design sources document.

    Returns:
        Each item of the document's `uiItems`, validated as the recon schema's `UiItem`.

    Raises:
        SpecUiError: The file cannot be read, is not JSON, has no `uiItems` list, or an item
            does not conform to `UiItem`.

    """
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        msg: str = f"{path}: cannot read the UI design sources: {exc}"
        raise SpecUiError(msg) from exc
    if not isinstance(value, dict):
        msg = f"{path}: the UI design sources are not a JSON object"
        raise SpecUiError(msg)
    entries: object = value.get(KEY_UI_ITEMS)
    if not isinstance(entries, list):
        msg = f"{path}: {KEY_UI_ITEMS} is not a JSON list"
        raise SpecUiError(msg)
    items: list[UiItem] = []
    entry: object
    for index, entry in enumerate(entries):
        errors: list[str] = []
        if not _is_ui_item(entry, errors):
            msg = f"{path}: {KEY_UI_ITEMS}[{index}] is not a ui item: {'; '.join(errors)}"
            raise SpecUiError(msg)
        items.append(entry)
    return items


def _line(item: UiItem) -> str:
    """One item of the section, as a markdown list entry.

    Returns:
        The entry.

    """
    name: str = item["item"]
    source: DesignSource = item["designSource"]
    if source == DESIGN_SOURCE_BUNDLE:
        sections: str = ", ".join(section.strip() for section in item.get("sections", []) if section.strip())
        build_spec: str = item.get("buildSpec") or "not resolved"
        return (
            f"- `{name}`: {DESIGN_SOURCE_BUNDLE}; build spec `{build_spec}`; Section IDs {sections or 'none resolved'}"
        )
    if source == DESIGN_SOURCE_NONE:
        return f"- `{name}`: {DESIGN_SOURCE_NONE}; it changes no design"
    return f"- `{name}`: {DESIGN_SOURCE_CDS}; designed with the CDS design system"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def spec_ui_append(doc: Path, ui: Path) -> UiAppendResult:
    """Write the UI design sources section at the end of the saved spec document.

    Args:
        doc: The saved spec document, `spec-<slug>.md`.
        ui: The saved UI design sources document, `spec-<slug>.ui.json`, whose `uiItems`
            are the recon schema's `UiItem` rows.

    Returns:
        {ok, appended, summary}; `appended` counts the items written. With no items, or no
        saved document, nothing is written and `appended` is 0. A UI design sources
        document that cannot be read or holds an invalid item raises `SpecUiError`.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(doc, Path)) or not (isinstance(ui, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    items: list[UiItem] = _items(ui)
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
