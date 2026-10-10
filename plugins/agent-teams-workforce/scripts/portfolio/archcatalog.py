"""Read the existing lightweight architecture frontmatter catalog."""

from pathlib import Path

from contracts import CatalogRecord
from typeguard import CollectionCheckStrategy, typechecked

FENCE = "---"
QUOTE_PAIR_LENGTH = 2


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def split_frontmatter(text: str) -> tuple[list[str], int, int] | None:
    """Locate the YAML frontmatter block in a document.

    Args:
        text: The whole file.

    Returns:
        The frontmatter lines, the index of the first line after the opening fence, and
        the index of the closing fence — or None when the file opens with no fence.

    Raises:
        TypeError: The document is not a string.

    """
    idx: int
    if not isinstance(text, str):
        message: str = "Frontmatter input must be document text"
        raise TypeError(message)
    lines: list[str] = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == FENCE:
            return lines, 1, idx
    return None


def _unquote(value: str) -> str:
    """Strip one pair of matching YAML quotes from a scalar.

    Args:
        value: The scalar as written.

    Returns:
        The scalar without its quotes.

    """
    value = value.strip()
    if len(value) >= QUOTE_PAIR_LENGTH and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _shown_elements(
    rest: str,
    lines: list[str],
    index: int,
    close: int,
    existing: list[str],
) -> tuple[list[str], int]:
    """Parse the supported inline or block element list.

    Returns:
        Element names and the next unread frontmatter line.

    """
    if rest.startswith("[") and rest.endswith("]"):
        return [_unquote(value) for value in rest[1:-1].split(",") if value.strip()], index
    shown: list[str] = list(existing)
    while index < close and lines[index].lstrip().startswith("- "):
        shown.append(_unquote(lines[index].lstrip()[2:]))
        index += 1
    return shown, index


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_catalog(path: Path) -> CatalogRecord:
    """Read a view's catalog frontmatter: `view_type`, `scope`, `subject` and `shows`.

    `shows` is read as a block list (`- name` lines) or a flow list (`[a, b]`).

    Args:
        path: The view file.

    Returns:
        The four keys; a missing scalar is an empty string and a missing list is empty.

    Raises:
        TypeError: The catalog path has an invalid type.

    """
    _: str
    if not isinstance(path, Path):
        message: str = "Catalog input must be a Path"
        raise TypeError(message)
    out: CatalogRecord = {"view_type": "", "scope": "", "subject": "", "shows": []}
    split: tuple[list[str], int, int] | None = split_frontmatter(path.read_text(encoding="utf-8"))
    if split is None:
        return out
    lines: list[str]
    start: int
    close: int
    lines, start, close = split
    idx: int = start
    while idx < close:
        line: str = lines[idx]
        idx += 1
        if ":" not in line or line[:1].isspace():
            continue
        key: str
        rest: str
        key, _, rest = line.partition(":")
        key, rest = key.strip(), rest.strip()
        if key == "view_type":
            out["view_type"] = _unquote(rest)
            continue
        if key == "scope":
            out["scope"] = _unquote(rest)
            continue
        if key == "subject":
            out["subject"] = _unquote(rest)
            continue
        if key != "shows":
            continue
        parsed: tuple[list[str], int] = _shown_elements(rest, lines, idx, close, out["shows"])
        out["shows"] = parsed[0]
        idx = parsed[1]
    out["shows"] = [s for s in dict.fromkeys(out["shows"], None) if s]
    return out
