"""Repository placement: the placement contract.

The one definition is ``schemas/placement.schema.json``. This module is its Python form: the key
names, the typed shapes and the validating reader. On import it checks that every key below is
exactly the set of properties the schema declares (and requires), so a schema change that this
module does not follow fails the first import instead of drifting.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict, TypeIs

if TYPE_CHECKING:
    from collections.abc import Mapping

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

PLACEMENT_SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "schemas" / "placement.schema.json"

KEY_PLACEMENTS: Final = "placements"
KEY_MISSING_REPOS: Final = "missingRepos"
KEY_NO_CODE: Final = "noCode"
KEY_SPAN_RATIONALE: Final = "spanRationale"

KEY_REPO_PATH: Final = "repoPath"
KEY_REPO_NAME: Final = "repoName"
KEY_ITEM_IDS: Final = "itemIds"
KEY_FRONTEND: Final = "frontend"
KEY_RATIONALE: Final = "rationale"

KEY_NAME: Final = "name"
KEY_PURPOSE: Final = "purpose"

KEY_ITEM_ID: Final = "itemId"
KEY_REASON: Final = "reason"

RULING_KEYS: Final[frozenset[str]] = frozenset((KEY_PLACEMENTS, KEY_MISSING_REPOS, KEY_NO_CODE, KEY_SPAN_RATIONALE))
PLACEMENT_KEYS: Final[frozenset[str]] = frozenset(
    (KEY_REPO_PATH, KEY_REPO_NAME, KEY_ITEM_IDS, KEY_FRONTEND, KEY_RATIONALE),
)
MISSING_REPO_KEYS: Final[frozenset[str]] = frozenset((KEY_NAME, KEY_PURPOSE, KEY_ITEM_IDS))
NO_CODE_KEYS: Final[frozenset[str]] = frozenset((KEY_ITEM_ID, KEY_REASON))


class Placement(TypedDict):
    """One repository the ruling places delta items in; repoPath is None only for a missing repository."""

    repoPath: str | None
    repoName: str
    itemIds: list[str]
    frontend: bool
    rationale: str


class MissingRepo(TypedDict):
    """A repository the approved target names that does not exist yet."""

    name: str
    purpose: str
    itemIds: list[str]


class NoCodeEntry(TypedDict):
    """A delta item that has no code in this project."""

    itemId: str
    reason: str


class PlacementRuling(TypedDict):
    """The polyrepo-steward's placement ruling (repo-scoping.json)."""

    placements: list[Placement]
    missingRepos: list[MissingRepo]
    noCode: list[NoCodeEntry]
    spanRationale: str


class PlacementError(ValueError):
    """A document does not conform to the placement schema."""


def _is_object(value: object) -> TypeIs[dict[str, object]]:
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _member(value: object, key: str) -> dict[str, object]:
    if not _is_object(value):
        message: str = f"{PLACEMENT_SCHEMA_PATH}: expected an object holding {key!r}"
        raise TypeError(message)
    child: object = value.get(key)
    if not _is_object(child):
        message = f"{PLACEMENT_SCHEMA_PATH}: {key!r} is not an object"
        raise TypeError(message)
    return child


def load_placement_schema() -> dict[str, JsonValue]:
    """Read the placement schema.

    Returns:
        The decoded schema.

    Raises:
        TypeError: The file is not a JSON object.

    """
    value: JsonValue = json.loads(PLACEMENT_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        message: str = f"{PLACEMENT_SCHEMA_PATH}: expected a JSON object"
        raise TypeError(message)
    return value


def _declared(node: Mapping[str, object], where: str, expected: frozenset[str]) -> None:
    properties: frozenset[str] = frozenset(_member(node, "properties"))
    required: object = node.get("required")
    names: frozenset[str] = (
        frozenset(name for name in required if isinstance(name, str)) if isinstance(required, list) else frozenset()
    )
    if properties != expected or names != expected or node.get("additionalProperties") is not False:
        message: str = (
            f"{PLACEMENT_SCHEMA_PATH} {where}: the schema declares {sorted(properties)} "
            f"(required {sorted(names)}); placement_contract.py names {sorted(expected)}"
        )
        raise TypeError(message)


def _check_schema() -> None:
    """Fail with a TypeError when the schema's properties, required keys or closedness differ from this module."""
    schema: dict[str, JsonValue] = load_placement_schema()
    _declared(schema, "root", RULING_KEYS)
    properties: dict[str, object] = _member(schema, "properties")
    for key, expected in (
        (KEY_PLACEMENTS, PLACEMENT_KEYS),
        (KEY_MISSING_REPOS, MISSING_REPO_KEYS),
        (KEY_NO_CODE, NO_CODE_KEYS),
    ):
        _declared(_member(_member(properties, key), "items"), key, expected)


_check_schema()


def _strings(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        message: str = f"{where}: expected an array of strings"
        raise PlacementError(message)
    return [item for item in value if isinstance(item, str)]


def _text(value: object, where: str) -> str:
    if not isinstance(value, str):
        message: str = f"{where}: expected a string"
        raise PlacementError(message)
    return value


def _closed(value: object, where: str, keys: frozenset[str]) -> dict[str, object]:
    if not _is_object(value):
        message: str = f"{where}: expected an object"
        raise PlacementError(message)
    if set(value) != keys:
        message = f"{where}: keys must be exactly {sorted(keys)}, got {sorted(value)}"
        raise PlacementError(message)
    return value


def _array(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        message: str = f"{where}: expected an array"
        raise PlacementError(message)
    return list(value)


def _placement(value: object, where: str) -> Placement:
    entry: dict[str, object] = _closed(value, where, PLACEMENT_KEYS)
    path: object = entry[KEY_REPO_PATH]
    if path is not None and not isinstance(path, str):
        message: str = f"{where}.{KEY_REPO_PATH}: expected a string or null"
        raise PlacementError(message)
    frontend: object = entry[KEY_FRONTEND]
    if not isinstance(frontend, bool):
        message = f"{where}.{KEY_FRONTEND}: expected a boolean"
        raise PlacementError(message)
    return {
        KEY_REPO_PATH: path,
        KEY_REPO_NAME: _text(entry[KEY_REPO_NAME], f"{where}.{KEY_REPO_NAME}"),
        KEY_ITEM_IDS: _strings(entry[KEY_ITEM_IDS], f"{where}.{KEY_ITEM_IDS}"),
        KEY_FRONTEND: frontend,
        KEY_RATIONALE: _text(entry[KEY_RATIONALE], f"{where}.{KEY_RATIONALE}"),
    }


def _missing_repo(value: object, where: str) -> MissingRepo:
    entry: dict[str, object] = _closed(value, where, MISSING_REPO_KEYS)
    return {
        KEY_NAME: _text(entry[KEY_NAME], f"{where}.{KEY_NAME}"),
        KEY_PURPOSE: _text(entry[KEY_PURPOSE], f"{where}.{KEY_PURPOSE}"),
        KEY_ITEM_IDS: _strings(entry[KEY_ITEM_IDS], f"{where}.{KEY_ITEM_IDS}"),
    }


def _no_code(value: object, where: str) -> NoCodeEntry:
    entry: dict[str, object] = _closed(value, where, NO_CODE_KEYS)
    return {
        KEY_ITEM_ID: _text(entry[KEY_ITEM_ID], f"{where}.{KEY_ITEM_ID}"),
        KEY_REASON: _text(entry[KEY_REASON], f"{where}.{KEY_REASON}"),
    }


def parse_placement_ruling(value: object) -> PlacementRuling:
    """Validate a decoded placement ruling against the schema and narrow it.

    Args:
        value: The decoded JSON document.

    A document that does not conform to the schema raises ``PlacementError`` (a ``ValueError``)
    whose message names the field.

    Returns:
        The typed ruling.

    """
    where: str = "placement"
    document: dict[str, object] = _closed(value, where, RULING_KEYS)
    return {
        KEY_PLACEMENTS: [
            _placement(item, f"{where}.{KEY_PLACEMENTS}[{index}]")
            for index, item in enumerate(_array(document[KEY_PLACEMENTS], f"{where}.{KEY_PLACEMENTS}"))
        ],
        KEY_MISSING_REPOS: [
            _missing_repo(item, f"{where}.{KEY_MISSING_REPOS}[{index}]")
            for index, item in enumerate(_array(document[KEY_MISSING_REPOS], f"{where}.{KEY_MISSING_REPOS}"))
        ],
        KEY_NO_CODE: [
            _no_code(item, f"{where}.{KEY_NO_CODE}[{index}]")
            for index, item in enumerate(_array(document[KEY_NO_CODE], f"{where}.{KEY_NO_CODE}"))
        ],
        KEY_SPAN_RATIONALE: _text(document[KEY_SPAN_RATIONALE], f"{where}.{KEY_SPAN_RATIONALE}"),
    }
