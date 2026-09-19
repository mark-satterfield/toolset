#!/usr/bin/env python3
"""Epic PRDs as files: one file per Epic, and an index a session searches them through.

An Epic's PRD is its description. A session that assesses or judges an Epic reads that
Epic's PRD in full from its file, and finds the other PRDs it needs by searching the
directory; the index names every open Epic with its title, elaboration state, PRD file and
section headings, so a search can be narrowed before any PRD is opened.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Bead, Graph

#: Metadata key set on an Epic by the elaboration pipeline, shown in the index.
ELAB_KEY = "elaboration_state"

#: The most headings the index lists for one PRD.
MAX_HEADINGS = 40


def write_prds(epics: list[Bead], prd_dir: Path) -> dict[str, str]:
    """Write each Epic's PRD, its description, to its own file.

    Args:
        epics: The Epics.
        prd_dir: The directory to write into; created when absent.

    Returns:
        Epic id -> the file holding its PRD.
    """
    prd_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for epic in epics:
        path = prd_dir / f"{epic.id}.md"
        path.write_text(f"# {epic.title}\n\n{epic.description}\n", encoding="utf-8")
        paths[epic.id] = str(path)
    return paths


def headings(description: str) -> list[str]:
    """The section headings of a PRD.

    Args:
        description: The PRD text.

    Returns:
        The text of every line that starts with `#`, with the `#` characters and the
        surrounding space stripped, empty ones left out, at most `MAX_HEADINGS`.
    """
    found = []
    for line in description.splitlines():
        if not line.startswith("#"):
            continue
        text = line.lstrip("#").strip()
        if text:
            found.append(text)
        if len(found) == MAX_HEADINGS:
            break
    return found


def write_index(
    graph: Graph, epics: list[Bead], paths: dict[str, str], path: Path
) -> None:
    """Write the index of the open Epics' PRDs.

    One heading line, `# Open Epics`, then one line per Epic:
    `- <id> | <title> | elaboration: <state or unset> | PRD: <path> | sections: <headings>`.
    Nothing else from the Epic's text or metadata is written.

    Args:
        graph: The tracker graph the Epics were read from.
        epics: The Epics to list, in the order to list them.
        paths: Epic id -> the file holding its PRD, from `write_prds`.
        path: The index file to write.
    """
    lines = ["# Open Epics"]
    for epic in epics:
        bead = graph.beads.get(epic.id, epic)
        state = bead.metadata.get(ELAB_KEY) or "unset"
        sections = "; ".join(headings(bead.description))
        lines.append(
            f"- {bead.id} | {bead.title} | elaboration: {state} | "
            f"PRD: {paths.get(bead.id, '')} | sections: {sections}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
