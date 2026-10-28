"""The syntax check of the diagrams a document maintainer changed, run by the script at no token cost.

A Mermaid block of a document written is changed when the vault's last commit does not hold the
same block in that document (``git show HEAD:<path>``). Each changed block is rendered once with
the Mermaid CLI through the ``architecture-diagramming`` skill's ``scripts/render-check.sh``; a
block that does not render is a problem the maintainer's session corrects. Each changed sequence
diagram is also read for a ``;`` or a bare ``#`` in its message and note text, which the skill
forbids: a ``;`` breaks parsing and a ``#`` renders without error but cuts the label. The check
proves the source parses and nothing more: the maintainer renders and looks at a diagram that is
new to the documents, as the skill's readability rule requires, and an edited diagram is checked
by syntax only.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from matrix_contract import MatrixError
from matrixsync import program_output

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from orchestrator.core.journal_steps import StepRun
    from orchestrator.core.tools import CommandResult

RENDER_CHECK: Final = "skills/architecture-diagramming/scripts/render-check.sh"
"""The script, under the plugin root, that renders Mermaid sources and exits non-zero when one fails."""
RENDER_TIMEOUT: Final = 600
"""Seconds one run of the render script may take for every changed block of one write."""
STAGE: Final = "architecture.diagram-syntax"
_BLOCK: Final[re.Pattern[str]] = re.compile(
    r"^[ \t]*```mermaid[ \t]*\n(?P<source>.*?)^[ \t]*```",
    re.MULTILINE | re.DOTALL,
)
_FAILED: Final[re.Pattern[str]] = re.compile(r"^FAIL (?P<source>.+?)$", re.MULTILINE)
SEQUENCE_KIND: Final = "sequenceDiagram"
_COMMENT: Final = "%%"
_FRONT_MATTER: Final = "---"
_MESSAGE: Final[re.Pattern[str]] = re.compile(r"^[^:]*?-{1,2}(?:>>|>|x|\))[+-]?[^:]*:(?P<text>.*)$")
"""A sequence-diagram message: sender, arrow, receiver, then its text after the first colon."""
_NOTE: Final[re.Pattern[str]] = re.compile(r"^note\s+(?:left of|right of|over)\s[^:]*:(?P<text>.*)$", re.IGNORECASE)
"""A sequence-diagram note, with its text after the first colon."""
_ENTITY: Final[re.Pattern[str]] = re.compile(r"#(?:\d+|[A-Za-z]+);")
"""A Mermaid entity code such as ``#35;`` or ``#quot;``, the one legitimate use of ``#`` and ``;`` in text."""
_FORBIDDEN: Final = (";", "#")


def mermaid_blocks(text: str) -> list[str]:
    """List the Mermaid sources of a Markdown document, in order.

    Returns:
        The text inside each fenced ``mermaid`` block, stripped of surrounding blank space.

    """
    return [found["source"].strip() for found in _BLOCK.finditer(text)]


def _committed_blocks(arch: Path, relative: str) -> set[str]:
    """Read the Mermaid sources a document holds in the vault's last commit.

    Returns:
        Each source; none when the commit does not hold the document.

    """
    try:
        return set(mermaid_blocks(program_output("git", ["show", f"HEAD:./{relative}"], arch)))
    except MatrixError:
        return set()


def changed_blocks(arch: Path, documents: Sequence[str]) -> list[tuple[str, int, str]]:
    """List the Mermaid blocks of some documents that the vault's last commit does not hold.

    Args:
        arch: The architecture root, a folder of the vault.
        documents: The documents' paths under the architecture root.

    Returns:
        Each changed block as its document's path, its number in the document counted from 1,
        and its source.

    """
    changed: list[tuple[str, int, str]] = []
    relative: str
    for relative in documents:
        path: Path = arch / relative
        if not path.is_file():
            continue
        committed: set[str] = _committed_blocks(arch, relative)
        changed.extend(
            (relative, number, source)
            for number, source in enumerate(mermaid_blocks(path.read_text(encoding="utf-8")), start=1)
            if source not in committed
        )
    return changed


def _diagram_lines(source: str) -> list[str]:
    """List the statements of a Mermaid source: its stripped lines past any front matter, without comments.

    Returns:
        Each non-blank line that is no ``%%`` comment or directive, outside a ``---`` front matter block.

    """
    lines: list[str] = [line.strip() for line in source.splitlines()]
    if lines and lines[0] == _FRONT_MATTER and _FRONT_MATTER in lines[1:]:
        lines = lines[lines.index(_FRONT_MATTER, 1) + 1 :]
    return [line for line in lines if line and not line.startswith(_COMMENT)]


def sequence_text_problems(relative: str, number: int, source: str) -> list[str]:
    """Name each message or note of a sequence diagram whose text holds a ``;`` or a bare ``#``.

    Args:
        relative: The document's path under the architecture root.
        number: The block's number in the document, counted from 1.
        source: The block's Mermaid source.

    Returns:
        One line per offending message or note, naming the document, the block and the line; none
        when the block is no sequence diagram or its text is clean. An entity code such as ``#35;``
        is legitimate.

    """
    lines: list[str] = _diagram_lines(source)
    if not lines or not lines[0].startswith(SEQUENCE_KIND):
        return []
    problems: list[str] = []
    line: str
    for line in lines[1:]:
        found: re.Match[str] | None = _NOTE.match(line) or _MESSAGE.match(line)
        if found is None:
            continue
        text: str = _ENTITY.sub("", found["text"])
        held: list[str] = [character for character in _FORBIDDEN if character in text]
        if held:
            named: str = " and ".join(repr(character) for character in held)
            problems.append(
                f"the Mermaid diagram {number} of {relative} has {named} in the text of {line!r}; "
                "write ',' for ';' and '#35;' or words for '#'",
            )
    return problems


def syntax_problems(run: StepRun, arch: Path, documents: Sequence[str], folder: Path) -> list[str]:
    """Render each changed Mermaid block of some documents once and name each that does not render.

    Args:
        run: The step whose session wrote the documents; its tools run the render script.
        arch: The architecture root.
        documents: The documents written, by their paths under the architecture root.
        folder: The scratch folder the sources and their images are written to.

    Returns:
        One line per sequence-diagram message or note whose text holds a ``;`` or a bare ``#``
        (:func:`sequence_text_problems`), then one line per block that does not render, naming its
        document and its number, with the render script's own report; none when every changed
        block is clean and renders, or none changed.

    """
    blocks: list[tuple[str, int, str]] = changed_blocks(arch, documents)
    if not blocks:
        return []
    texts: list[str] = [problem for block in blocks for problem in sequence_text_problems(*block)]
    folder.mkdir(parents=True, exist_ok=True)
    sources: dict[str, tuple[str, int]] = {}
    for index, (relative, number, source) in enumerate(blocks, start=1):
        written: Path = folder / f"diagram-{index}.mmd"
        written.write_text(source + "\n", encoding="utf-8")
        sources[str(written)] = (relative, number)
    script: Path = run.tools.plugin / RENDER_CHECK
    done: CommandResult = run.tools.command(
        ["bash", str(script), str(folder / "rendered"), *sources],
        stage=STAGE,
        timeout=RENDER_TIMEOUT,
        check=False,
    )
    if done.exit == 0:
        return texts
    failed: list[str] = [found["source"] for found in _FAILED.finditer(done.stderr)]
    named: list[str] = [
        f"the Mermaid diagram {sources[held][1]} of {sources[held][0]} does not render; correct its syntax"
        for held in failed
        if held in sources
    ]
    report: str = done.stderr.strip()[-4000:]
    return [*texts, *named, f"the render script exited {done.exit}: {report}"]


__all__ = ["changed_blocks", "mermaid_blocks", "sequence_text_problems", "syntax_problems"]
