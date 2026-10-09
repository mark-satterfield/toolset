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
from pathlib import Path

#: The heading of the section this module writes.
HEADING = "## UI design sources"


class SpecUiError(Exception):
    """The items argument is not a list of UI items."""


def _items(raw: str) -> list[dict]:
    """Parse the UI items argument.

    Returns:
        Each item as {id, designSource, buildSpec, sections}; an item that names no
        design source is a `bundle` item when it names a build spec, else a `cds` one.

    Raises:
        SpecUiError: The argument is not a JSON list; an entry with no id is left out.
    """
    try:
        value = json.loads(raw)
    except ValueError as exc:
        msg = f"--items is not JSON: {exc}"
        raise SpecUiError(msg) from exc
    if not isinstance(value, list):
        msg = "--items is not a JSON list"
        raise SpecUiError(msg)
    items = []
    for x in value:
        if not isinstance(x, dict) or not str(x.get("id") or "").strip():
            continue
        sections = x.get("sections") if isinstance(x.get("sections"), list) else []
        spec = str(x.get("buildSpec") or "").strip() or None
        source = str(x.get("designSource") or "").strip() or (
            "bundle" if spec else "cds"
        )
        items.append(
            {
                "id": str(x["id"]).strip(),
                "designSource": source,
                "buildSpec": spec,
                "sections": [str(s).strip() for s in sections if str(s).strip()],
            }
        )
    return items


def _line(item: dict) -> str:
    """One item of the section, as a markdown list entry.

    Returns:
        The entry.
    """
    if item["designSource"] == "bundle":
        sections = ", ".join(item["sections"]) or "none resolved"
        return (
            f"- `{item['id']}`: bundle; build spec `{item['buildSpec'] or 'not resolved'}`; "
            f"Section IDs {sections}"
        )
    if item["designSource"] == "none":
        return f"- `{item['id']}`: none; it changes no design"
    return f"- `{item['id']}`: cds; designed with the CDS design system"


def spec_ui_append(doc: Path, raw_items: str) -> dict:
    """Write the UI design sources section at the end of the saved spec document.

    Args:
        doc: The saved spec document, `spec-<slug>.md`.
        raw_items: The repository's `ui` items as JSON:
            [{id, designSource?, buildSpec?, sections?}].

    Returns:
        {ok, appended, summary}; `appended` counts the items written. With no items, or no
        saved document, nothing is written and `appended` is 0.

    Raises:
        SpecUiError: The items argument is not a JSON list.
    """
    items = _items(raw_items)
    if not items or not doc.is_file():
        return {
            "ok": True,
            "appended": 0,
            "summary": {"ok": True, "appended": 0, "saved": doc.is_file()},
        }
    text = doc.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == HEADING), None)
    if start is not None:
        end = next(
            (
                j
                for j in range(start + 1, len(lines))
                if lines[j].startswith("#")
                and len(lines[j]) - len(lines[j].lstrip("#")) <= 2
            ),
            len(lines),
        )
        lines = lines[:start] + lines[end:]
    body = "\n".join(lines).rstrip("\n")
    section = "\n".join([HEADING, "", *(_line(i) for i in items)])
    doc.write_text(f"{body}\n\n{section}\n", encoding="utf-8")
    return {
        "ok": True,
        "appended": len(items),
        "summary": {"ok": True, "appended": len(items), "saved": True},
    }
