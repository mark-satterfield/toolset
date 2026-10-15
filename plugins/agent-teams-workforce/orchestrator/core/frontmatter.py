"""YAML front matter of an authored Markdown file: an agent definition or a skill."""

from __future__ import annotations

import importlib
from typing import Final

from typeguard import CollectionCheckStrategy, check_type

OPENING: Final = "---\n"
CLOSING: Final = "\n---"


def yaml_safe_load(stream: str) -> object:
    """Parse one YAML document with PyYAML behind a typed edge, since the library ships no type stubs.

    Returns:
        The parsed document as plain Python values.

    Raises:
        TypeError: ``stream`` is not text, or the imported yaml module has no safe_load.

    """
    if not isinstance(stream, str):
        message: str = f"YAML input must be text, got {type(stream).__name__}"
        raise TypeError(message)
    module: object = importlib.import_module("yaml")
    loader: object = getattr(module, "safe_load", None)
    if not callable(loader):
        message = "the yaml module does not provide safe_load"
        raise TypeError(message)
    parsed: object = loader(stream)
    return parsed


def split_front_matter(text: str, what: str) -> tuple[dict[str, object], str]:
    """Separate the front matter of an authored file from its body.

    A value of the front matter is whatever YAML makes of it (an unquoted date is a date), so a
    caller narrows each field it reads.

    Args:
        text: The whole file.
        what: The file's name in an error message, for example ``agent trd-author``.

    Returns:
        The front matter's fields by name, and the body without surrounding blank lines.

    Raises:
        TypeError: An argument is not text, or the front matter is not a mapping with text keys.
        ValueError: The file does not open with front matter, or the front matter is not closed.

    """
    if not isinstance(text, str) or not isinstance(what, str):
        argument_error: str = "split_front_matter requires the file text and its name"
        raise TypeError(argument_error)
    if not text.startswith(OPENING):
        message: str = f"{what} has no frontmatter"
        raise ValueError(message)
    front: str
    separator: str
    body: str
    front, separator, body = text[len(OPENING) :].partition(CLOSING)
    if not separator:
        message = f"{what} has frontmatter that is not closed"
        raise ValueError(message)
    parsed: object = yaml_safe_load(front)
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        message = f"{what} has frontmatter that is not a mapping with text keys"
        raise TypeError(message)
    fields: dict[str, object] = check_type(
        parsed,
        dict[str, object],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    return fields, body.strip()


def string_list(value: object) -> list[str]:
    """Read a string-list field of authored front matter.

    Returns:
        The validated strings; a comma-separated string gives its trimmed, non-empty entries, and
        an absent field (None) gives an empty list.

    Raises:
        TypeError: The field is neither text, None nor a list of strings.

    """
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        message: str = f"a front matter list must be text or a list of strings, got {value!r}"
        raise TypeError(message)
    return check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
