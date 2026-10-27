"""Read the text of architecture document headings as the vault's last commit holds them.

``atw-matrix heading`` prints it, so a session reads the words of a heading only when a decision
turns on them, instead of being handed every heading's text up front. A heading is named by a
reference, ``<path>#<heading>``: the document's path under the architecture root (or its absolute
path inside it) and the heading's key as the matrix records it (``matrixsync.heading_texts``).
A reference with no ``#`` names the document as a whole. Each document is read once with
``git show HEAD:<path>``, never from the vault's working tree.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

from matrix_contract import MatrixError
from matrixsync import heading_texts, program_output, relative_path

if TYPE_CHECKING:
    from collections.abc import Sequence

HEADING_MARK: Final = "#"
"""What separates a document's path from the heading in a heading reference."""
FENCE: Final = "---"
"""The line that opens and closes a document's front matter."""


class HeadingText(TypedDict):
    """One heading reference with its text."""

    ref: str
    path: str
    """The document's path under the architecture root."""
    heading: str
    """The heading's key; empty for the document as a whole."""
    text: str | None
    """The heading's own text (its heading line and everything up to the next heading), or the
    document's whole body; null when the vault's last commit holds no such document or heading."""


class HeadingsRead(TypedDict):
    """What ``atw-matrix heading`` prints."""

    headings: list[HeadingText]


def document_body(text: str) -> list[str]:
    """Split a document's text into the lines after its front matter.

    Returns:
        Every line when the document has no front matter.

    """
    lines: list[str] = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return lines
    close: int = next((index for index in range(1, len(lines)) if lines[index].strip() == FENCE), 0)
    return lines[close + 1 :] if close else lines


def heading_ref(path: str, heading: str) -> str:
    """Name one heading of a document as a reference ``atw-matrix heading`` takes.

    Returns:
        ``<path>#<heading>``; the path alone for the document as a whole.

    """
    return f"{path}{HEADING_MARK}{heading}" if heading else path


def _committed_body(arch: Path, relative: str) -> list[str] | None:
    """Read a document's body from the vault's last commit.

    Returns:
        The lines after its front matter; None when the commit does not hold the document.

    """
    try:
        return document_body(program_output("git", ["show", f"HEAD:./{relative}"], arch))
    except MatrixError:
        return None


def committed_headings(arch: Path, refs: Sequence[str]) -> HeadingsRead:
    """Read the text of each heading some references name, from the vault's last commit.

    Args:
        arch: The architecture root, a folder of the vault.
        refs: The heading references, ``<path>#<heading>`` or a document's path alone.

    Returns:
        One row per reference, in the order given.

    """
    root: Path = arch.resolve()
    bodies: dict[str, list[str] | None] = {}
    texts: dict[str, dict[str, str]] = {}
    rows: list[HeadingText] = []
    ref: str
    for ref in refs:
        stated: str
        heading: str
        stated, _, heading = ref.partition(HEADING_MARK)
        relative: str = relative_path(Path(stated), root) if Path(stated).is_absolute() else stated
        if relative not in bodies:
            bodies[relative] = _committed_body(arch, relative)
            held: list[str] | None = bodies[relative]
            texts[relative] = {} if held is None else heading_texts(held)
        body: list[str] | None = bodies[relative]
        whole: str | None = None if body is None else "\n".join(body).strip("\n")
        rows.append({
            "ref": ref,
            "path": relative,
            "heading": heading,
            "text": texts[relative].get(heading) if heading else whole,
        })
    return {"headings": rows}
