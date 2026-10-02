#!/usr/bin/env python3
"""Epic PRDs as files: one file per Epic, and an index a session searches them through.

An Epic's PRD is its description. A session that assesses or judges an Epic reads that
Epic's PRD in full from its file, and finds the other PRDs it needs by searching the
directory; the index names every open Epic with its title, elaboration state, PRD file and
section headings, so a search can be narrowed before any PRD is opened.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beadgraph import Bead, Graph

#: Metadata key set on an Epic by the elaboration pipeline, shown in the index.
ELAB_KEY = "elaboration_state"

#: The most headings the index lists for one PRD.
MAX_HEADINGS = 40

#: The frontmatter key holding a document's lifecycle state.
STATE_KEY = "lifecycle_state"

#: The section holding a PRD's requirements.
REQUIREMENTS_SECTION = "Requirements"

#: The heading level of a PRD section, and the levels of the requirement headings in one.
SECTION_LEVEL = 2
REQUIREMENT_LEVELS = (3, 4)

#: A level-3 or level-4 heading under Requirements that names no requirement.
LEGEND_HEADING = "priority legend"

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


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

    EVERY heading, uncapped. The cap belongs to the index line, which states how many it
    withheld; capping here returned a partial list a caller could not tell from a complete
    one, and the index is what narrows a search before a PRD is opened.

    Returns:
        The text of every line that starts with `#` outside a fenced code block, with the
        `#` characters and the surrounding space stripped, empty ones left out. A `#` line
        inside a fence is a comment in the code, not a section.
    """
    found = []
    fenced = False
    for line in description.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or not line.startswith("#"):
            continue
        text = line.lstrip("#").strip()
        if text:
            found.append(text)
    return found


def write_index(
    graph: Graph, epics: list[Bead], paths: dict[str, str], path: Path
) -> None:
    """Write the index of the open Epics' PRDs.

    One heading line, `# Open Epics`, then one line per Epic:
    `- <id> | <title> | elaboration: <state or unset> | PRD: <path> | sections: <headings>`.
    Nothing else from the Epic's text or metadata is written. At most `MAX_HEADINGS`
    sections are listed, and a PRD with more says how many were withheld, so a truncated
    line is never read as a complete one.

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
        found = headings(bead.description)
        sections = "; ".join(found[:MAX_HEADINGS])
        if len(found) > MAX_HEADINGS:
            sections += f"; +{len(found) - MAX_HEADINGS} more headings not listed"
        lines.append(
            f"- {bead.id} | {bead.title} | elaboration: {state} | "
            f"PRD: {paths.get(bead.id, '')} | sections: {sections}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _body_and_state(text: str) -> tuple[list[str], str]:
    """Split a PRD into its body lines and its frontmatter `lifecycle_state`.

    Args:
        text: The whole PRD file.

    Returns:
        The lines after the frontmatter (all lines when there is none), and the top-level
        `lifecycle_state` value, or an empty string when the PRD states none.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return lines, ""
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            state = ""
            for line in lines[1:idx]:
                if line.startswith(f"{STATE_KEY}:"):
                    state = line[len(STATE_KEY) + 1 :].strip().strip("\"'")
            return lines[idx + 1 :], state
    return lines, ""


def _outline(lines: list[str]) -> list[tuple[int, str, int]]:
    """The headings of a PRD body, outside fenced code blocks.

    Args:
        lines: The PRD body lines.

    Returns:
        One (level, text, line index) per heading, in document order.
    """
    found = []
    fenced = False
    for idx, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        match = None if fenced else _HEADING.match(line)
        if match and match.group(2):
            found.append((len(match.group(1)), match.group(2), idx))
    return found


def _section(
    lines: list[str], outline: list[tuple[int, str, int]], title: str
) -> tuple[int, int] | None:
    """The line range of the first level-2 section with this title.

    Args:
        lines: The PRD body lines.
        outline: The headings from `_outline`.
        title: The section title, compared without case.

    Returns:
        The (first, end) line indexes of the section body, or None when the PRD has no
        such section. The body ends at the next heading of level 1 or 2.
    """
    for pos, (level, text, idx) in enumerate(outline):
        if level == SECTION_LEVEL and text.strip().lower() == title.lower():
            end = next(
                (i for lvl, _, i in outline[pos + 1 :] if lvl <= SECTION_LEVEL),
                len(lines),
            )
            return idx + 1, end
    return None


def prd_parse(path: Path) -> dict:
    """Read from a PRD file what elaboration takes from it; runs no `bd` command.

    Parsing assumes the PRD was validated before its Epic was made ready: it checks
    nothing about the PRD's content and ignores everything it does not take. It takes
    the level-3 and level-4 headings under `## Requirements`, other than a Priority
    Legend, when the PRD has that section. The one failure is a file that cannot be read.

    Args:
        path: The PRD file.

    Returns:
        `{ok, prd, requirementHeadings, failed, summary}`: `ok` is false only when the file
        cannot be read, and `failed` then names that; `requirementHeadings` lists the
        headings taken, empty when the PRD has none.
    """
    failed: list[dict] = []
    headings_found: list[str] = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        failed.append({"check": "readable", "reason": f"{path} is not readable: {exc}"})
        text = None
    if text is not None:
        lines, _ = _body_and_state(text)
        outline = _outline(lines)
        reqs = _section(lines, outline, REQUIREMENTS_SECTION)
        if reqs is not None:
            first, end = reqs
            headings_found = [
                t
                for lvl, t, i in outline
                if first <= i < end
                and lvl in REQUIREMENT_LEVELS
                and t.strip().lower() != LEGEND_HEADING
            ]
    return {
        "ok": not failed,
        "prd": str(path),
        "requirementHeadings": headings_found,
        "failed": failed,
        "summary": {
            "ok": not failed,
            "requirements": len(headings_found),
            "failed": [f["check"] for f in failed],
        },
    }
