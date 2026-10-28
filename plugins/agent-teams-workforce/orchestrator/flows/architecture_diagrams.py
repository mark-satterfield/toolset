"""The syntax check of the diagrams a document maintainer changed, run by the script at no token cost.

A Mermaid block of a document written is changed when the vault's last commit does not hold the
same block in that document (``git show HEAD:<path>``). Each changed block is rendered once with
the Mermaid CLI through the ``architecture-diagramming`` skill's ``scripts/render-check.sh``; a
block that does not render is a problem the maintainer's session corrects. The check proves the
source parses and nothing more: the maintainer renders and looks at a diagram that is new to the
documents, as the skill's readability rule requires, and an edited diagram is checked by syntax
only.
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


def syntax_problems(run: StepRun, arch: Path, documents: Sequence[str], folder: Path) -> list[str]:
    """Render each changed Mermaid block of some documents once and name each that does not render.

    Args:
        run: The step whose session wrote the documents; its tools run the render script.
        arch: The architecture root.
        documents: The documents written, by their paths under the architecture root.
        folder: The scratch folder the sources and their images are written to.

    Returns:
        One line per block that does not render, naming its document and its number, with the
        render script's own report; none when every changed block renders or none changed.

    """
    blocks: list[tuple[str, int, str]] = changed_blocks(arch, documents)
    if not blocks:
        return []
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
        return []
    failed: list[str] = [found["source"] for found in _FAILED.finditer(done.stderr)]
    named: list[str] = [
        f"the Mermaid diagram {sources[held][1]} of {sources[held][0]} does not render; correct its syntax"
        for held in failed
        if held in sources
    ]
    report: str = done.stderr.strip()[-4000:]
    return [*named, f"the render script exited {done.exit}: {report}"]


__all__ = ["changed_blocks", "mermaid_blocks", "syntax_problems"]
