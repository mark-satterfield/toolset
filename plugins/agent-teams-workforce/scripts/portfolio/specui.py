#!/usr/bin/env python3
"""The UI sections of a saved spec document, checked against each item's design source.

A repository's spec document, `spec-<slug>.md`, carries one section per `ui` delta item,
headed by the item id. A `bundle` item's section specifies it by reference to the
`spec/build-spec.md` of the cds bundle the owner supplied; a `cds` item's section states
that it is designed with the CDS design system; a `none` item's section states that it
changes no design. This module reads the saved document, not what a model session reported
about it, and names every `ui` item whose section is missing and every `bundle` item whose
section cites no build spec that exists, cites another one than the detailing resolved, or
leaves out a build-spec Section ID the detailing resolved.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from cdsbundles import read_bundle

#: A markdown heading: its hashes and its text.
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

#: An absolute path to a cds build spec, as a section cites it.
_BUILD_SPEC = re.compile(r"(/[^\s`'\"()<>\[\]]*?/spec/build-spec\.md)")


class SpecUiError(Exception):
    """The items argument is not a list of UI items."""


def _sections(text: str, item_id: str) -> list[str]:
    """Return the text of every section whose heading names the item id as a whole word.

    Returns:
        Each section's text, from its heading to the next heading of the same or a
        higher level.
    """
    lines = text.splitlines()
    word = re.compile(rf"(?<![\w-]){re.escape(item_id)}(?![\w-])")
    found = []
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if not m or not word.search(m.group(2)):
            continue
        level = len(m.group(1))
        end = next(
            (
                j
                for j in range(i + 1, len(lines))
                if (n := _HEADING.match(lines[j])) and len(n.group(1)) <= level
            ),
            len(lines),
        )
        found.append("\n".join(lines[i:end]))
    return found


def _in_bundle(path: Path) -> bool:
    """Return whether a build spec is the one a cds bundle's `bundle.json` names."""
    return any(
        (b := read_bundle(p)) is not None and Path(b["buildSpec"]) == path.resolve()
        for p in path.parents
    )


def _items(raw: str) -> list[dict]:
    """Parse the UI items argument.

    Returns:
        Each item as {id, designSource, buildSpec, sections}; an item that names no
        design source is a `bundle` item when it names a build spec, else a `cds` one.

    Raises:
        SpecUiError: The argument is not a JSON list of objects with an id.
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
            msg = f"--items holds an entry with no id: {x!r}"
            raise SpecUiError(msg)
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


def spec_ui_check(doc: Path, raw_items: str) -> dict:
    """Check the saved spec document's UI sections against the build specs.

    Args:
        doc: The saved spec document, `spec-<slug>.md`.
        raw_items: The repository's `ui` items as JSON:
            [{id, designSource?, buildSpec?, sections?}].

    Returns:
        {ok, gaps: [{id, problem}], summary}; ok is true when no item has a gap.

    Raises:
        SpecUiError: The items argument is malformed.
    """
    items = _items(raw_items)
    if not doc.is_file():
        gaps = [
            {"id": i["id"], "problem": f"the spec document {doc} is not saved"}
            for i in items
        ]
        return {
            "ok": not gaps,
            "gaps": gaps,
            "summary": {"items": len(items), "gaps": len(gaps)},
        }
    text = doc.read_text(encoding="utf-8", errors="replace")
    gaps = []
    for item in items:
        own = _sections(text, item["id"])
        if not own:
            gaps.append(
                {
                    "id": item["id"],
                    "problem": f"{doc.name} has no section headed by {item['id']}",
                }
            )
            continue
        if item["designSource"] != "bundle":
            continue
        body = "\n".join(own)
        cited = list(dict.fromkeys(_BUILD_SPEC.findall(body)))
        real = [c for c in cited if Path(c).is_file() and _in_bundle(Path(c))]
        if not real:
            gaps.append(
                {
                    "id": item["id"],
                    "problem": f"its section in {doc.name} cites no spec/build-spec.md in a cds bundle that exists"
                    + (f" (it cites {', '.join(cited)})" if cited else ""),
                }
            )
            continue
        if item["buildSpec"] and item["buildSpec"] not in real:
            gaps.append(
                {
                    "id": item["id"],
                    "problem": f"its section in {doc.name} cites {', '.join(real)}, not the build spec the detailing resolved, {item['buildSpec']}",
                }
            )
            continue
        word = lambda s: re.compile(rf"(?<![\w-]){re.escape(s)}(?![\w-])")  # noqa: E731
        absent = [s for s in item["sections"] if not word(s).search(body)]
        if absent:
            gaps.append(
                {
                    "id": item["id"],
                    "problem": f"its section in {doc.name} does not cite the build-spec Sections {', '.join(absent)} the detailing resolved",
                }
            )
    return {
        "ok": not gaps,
        "gaps": gaps,
        "summary": {"items": len(items), "gaps": len(gaps)},
    }
