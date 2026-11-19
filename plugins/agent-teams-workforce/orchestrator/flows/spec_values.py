"""The values the design headings a Story's spec cites state, extracted by script for the spec authors.

:func:`design_values` lists, for every heading the repository context names, the values the heading
states word for word: each code span and each table row of its own text. The spec authors are handed
the file and copy those values verbatim, citing the heading. No scripted check compares a spec line
with the heading it cites: a line often cites a heading for one property while naming values another
heading states, so such a comparison refuses correct documents.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

from matrixchecklist import heading_text
from typeguard import check_type

from orchestrator.core.io import JsonValue, json_object, write_json

if TYPE_CHECKING:
    from collections.abc import Sequence

DESIGN_VALUES: Final = "design values"
"""The artifact name of the design values file the spec authors are handed."""
CODE_SPAN: Final = re.compile(r"`([^`\n]+)`")
"""A code span: how a design heading states a name, a key, a type or a limit."""


def _values(text: str) -> tuple[list[str], list[str]]:
    """Read the code spans and the table rows of one heading's own text.

    Returns:
        The distinct code spans, and the table rows other than separator rows, in order.

    """
    spans: list[str] = list(dict.fromkeys(match.group(1).strip() for match in CODE_SPAN.finditer(text)))
    rows: list[str] = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("|") and not set(line.strip()) <= set("|-: ")
    ]
    return spans, rows


def design_values_path(context: Path) -> Path:
    """Name the design values file beside a repository context (``spec-<slug>.context.json``).

    Returns:
        ``spec-<slug>.design-values.json`` in the same folder.

    """
    return context.with_name(context.name.removesuffix(".context.json") + ".design-values.json")


def design_values(documents: Sequence[JsonValue], output: Path) -> Path:
    """Write the values every heading the repository context names states.

    Args:
        documents: The repository context's ``documents``, each with its ``file``, ``path`` and ``headings``.
        output: The file to write.

    Returns:
        The written file: one ``{"citation", "values", "rows"}`` per heading that states any,
        ``citation`` being ``<path>#<heading>``.

    """
    found: list[JsonValue] = []
    for held in documents:
        document: dict[str, JsonValue] = json_object(held)
        file: str = check_type(document.get("file"), str)
        for heading in check_type(document.get("headings", []), list[str]):
            text: str | None = heading_text(Path(file).parent, {"source": file, "heading": heading})
            if text is None:
                continue
            spans, rows = _values(text)
            if spans or rows:
                values: list[JsonValue] = [*spans]
                table: list[JsonValue] = [*rows]
                found.append({"citation": f"{document.get('path')}#{heading}", "values": values, "rows": table})
    write_json(output, found)
    return output
