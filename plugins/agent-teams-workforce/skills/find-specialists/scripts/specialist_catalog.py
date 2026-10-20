"""The catalog of every agent of the plugin, generated from the agents' own definition files.

The catalog is ``catalog.json`` beside this skill's ``SKILL.md``, to
``schemas/specialist-catalog.schema.json``. Each entry is one agent: its name and description as
its definition's front matter states them, the skills its front matter lists, and the MCP servers
whose tools its ``tools`` list grants. Nothing is written into the catalog by hand: ``generate``
writes it from ``agents/*.md`` and ``generate --check`` fails when the file differs from what the
definitions give, which the repository's pre-commit hook runs whenever an agent definition changes.

Commands (each prints one JSON document on stdout):

- ``find <words>...``: the agents whose name, description, skills or MCP servers contain any of
  the words, the most matches first.
- ``show <agent>``: one agent's entry.
- ``list``: every agent's name and description.
- ``generate [--check]``: write the catalog, or check that it is current.

``find``, ``show`` and ``list`` need only the standard library; ``generate`` needs PyYAML.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Final, TypedDict, TypeIs

SKILL_DIR: Final[Path] = Path(__file__).resolve().parents[1]
PLUGIN_DIR: Final[Path] = SKILL_DIR.parents[1]
AGENTS_DIR: Final[Path] = PLUGIN_DIR / "agents"
CATALOG_PATH: Final[Path] = SKILL_DIR / "catalog.json"
OPENING: Final = "---\n"
CLOSING: Final = "\n---"
MCP_PREFIX: Final = "mcp__"
MCP_SEPARATOR: Final = "__"
TOOL_SEPARATOR: Final = ","
CATALOG_DESCRIPTION: Final = (
    "Every agent of the agent-teams-workforce plugin, generated from its definition file by "
    "skills/find-specialists/scripts/specialist_catalog.py. Do not edit by hand."
)
ENTRY_KEYS: Final[frozenset[str]] = frozenset({"name", "description", "skills", "mcpServers"})


class CatalogEntry(TypedDict):
    """One agent of the catalog."""

    name: str
    description: str
    skills: list[str]
    mcpServers: list[str]


class Catalog(TypedDict):
    """The whole catalog."""

    description: str
    agents: list[CatalogEntry]


class CatalogError(ValueError):
    """An agent definition or the catalog file does not have the shape the catalog needs."""


def _front_matter(path: Path) -> dict[str, object]:
    """Read the front matter of one agent definition.

    Returns:
        The front matter's fields by name.

    Raises:
        CatalogError: The file has no closed front matter, or it is not a mapping.

    """
    text: str = path.read_text(encoding="utf-8")
    if not text.startswith(OPENING):
        message: str = f"{path}: no front matter"
        raise CatalogError(message)
    front: str
    separator: str
    front, separator, _ = text[len(OPENING) :].partition(CLOSING)
    if not separator:
        message = f"{path}: front matter is not closed"
        raise CatalogError(message)
    loader: object = getattr(importlib.import_module("yaml"), "safe_load", None)
    if not callable(loader):
        message = "the yaml module does not provide safe_load"
        raise CatalogError(message)
    parsed: object = loader(front)
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        message = f"{path}: front matter is not a mapping with text keys"
        raise CatalogError(message)
    return {str(key): value for key, value in parsed.items()}


def _text(fields: dict[str, object], key: str, path: Path) -> str:
    """Read one required text field of a definition.

    Returns:
        The field, stripped.

    Raises:
        CatalogError: The field is missing or blank.

    """
    value: object = fields.get(key)
    if not isinstance(value, str) or not value.strip():
        message: str = f"{path}: front matter {key!r} is missing or blank"
        raise CatalogError(message)
    return " ".join(value.split())


def _names(value: object, path: Path, key: str) -> list[str]:
    """Read a list-or-comma-text field of a definition as names.

    Returns:
        The names, stripped, in the order stated, blanks left out.

    Raises:
        CatalogError: The field is neither text nor a list of text.

    """
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(TOOL_SEPARATOR) if part.strip()]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return [str(item).strip() for item in value if str(item).strip()]
    message: str = f"{path}: front matter {key!r} is neither text nor a list of text"
    raise CatalogError(message)


def _servers(tools: list[str]) -> list[str]:
    """Name the MCP servers whose tools a ``tools`` list grants.

    Returns:
        Each server once, in the order its first tool appears.

    """
    found: dict[str, None] = {}
    tool: str
    for tool in tools:
        if tool.startswith(MCP_PREFIX):
            found[tool.removeprefix(MCP_PREFIX).split(MCP_SEPARATOR, 1)[0]] = None
    return list(found)


def entry_of(path: Path) -> CatalogEntry:
    """Build one agent's catalog entry from its definition.

    Returns:
        The entry.

    Raises:
        CatalogError: The definition's name differs from its file name, or a field is malformed.

    """
    fields: dict[str, object] = _front_matter(path)
    name: str = _text(fields, "name", path)
    if name != path.stem:
        message: str = f"{path}: front matter name {name!r} differs from the file name"
        raise CatalogError(message)
    return {
        "name": name,
        "description": _text(fields, "description", path),
        "skills": _names(fields.get("skills"), path, "skills"),
        "mcpServers": _servers(_names(fields.get("tools"), path, "tools")),
    }


def build_catalog(agents_dir: Path = AGENTS_DIR) -> Catalog:
    """Build the catalog from every agent definition.

    Returns:
        The catalog, agents in name order.

    """
    return {
        "description": CATALOG_DESCRIPTION,
        "agents": [entry_of(path) for path in sorted(agents_dir.glob("*.md"))],
    }


def render(catalog: Catalog) -> str:
    """Render the catalog as the text of its file.

    Returns:
        Indented JSON with a final newline.

    """
    return json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"


def _is_names(value: object) -> TypeIs[list[str]]:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _is_entry(value: object) -> TypeIs[CatalogEntry]:
    return (
        isinstance(value, dict)
        and set(value) == ENTRY_KEYS
        and isinstance(value["name"], str)
        and bool(value["name"])
        and isinstance(value["description"], str)
        and bool(value["description"])
        and _is_names(value["skills"])
        and _is_names(value["mcpServers"])
    )


def read_catalog(path: Path = CATALOG_PATH) -> Catalog:
    """Read and check the catalog file.

    Returns:
        The catalog.

    Raises:
        CatalogError: The file is not JSON or does not have the catalog's shape.

    """
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        message: str = f"{path}: {error}"
        raise CatalogError(message) from None
    if not isinstance(document, dict) or set(document) != {"description", "agents"}:
        message = f"{path}: not an object with exactly description and agents"
        raise CatalogError(message)
    agents: object = document["agents"]
    if not isinstance(agents, list) or not all(_is_entry(item) for item in agents):
        message = f"{path}: agents is not a list of catalog entries"
        raise CatalogError(message)
    entries: list[CatalogEntry] = [item for item in agents if _is_entry(item)]
    return {"description": str(document["description"]), "agents": entries}


def agent_names(path: Path = CATALOG_PATH) -> frozenset[str]:
    """Name every agent the catalog lists.

    Returns:
        The agent names.

    """
    return frozenset(entry["name"] for entry in read_catalog(path)["agents"])


def find(catalog: Catalog, words: list[str]) -> list[CatalogEntry]:
    """Find the agents whose entry contains any of the words, ignoring case.

    Returns:
        The matching entries, the most words matched first, then by name.

    """
    wanted: list[str] = [word.lower() for word in words if word.strip()]
    scored: list[tuple[int, CatalogEntry]] = []
    entry: CatalogEntry
    for entry in catalog["agents"]:
        haystack: str = " ".join([entry["name"], entry["description"], *entry["skills"], *entry["mcpServers"]]).lower()
        score: int = sum(1 for word in wanted if word in haystack)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
    return [entry for _, entry in scored]


def _print(document: object) -> None:
    sys.stdout.write(json.dumps(document, indent=2, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run one command of the catalog.

    Returns:
        Zero on success; one when the catalog is stale, an agent is unknown or a file is malformed.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    finder: argparse.ArgumentParser = commands.add_parser("find", help="agents whose entry contains any of the words")
    finder.add_argument("words", nargs="+")
    shower: argparse.ArgumentParser = commands.add_parser("show", help="one agent's entry")
    shower.add_argument("agent")
    commands.add_parser("list", help="every agent's name and description")
    generator: argparse.ArgumentParser = commands.add_parser("generate", help="write the catalog from the agents")
    generator.add_argument("--check", action="store_true", help="fail when the catalog file is stale")
    args: argparse.Namespace = parser.parse_args(argv)
    try:
        return _run(args)
    except CatalogError as error:
        sys.stderr.write(f"{error}\n")
        return 1


def _generate(*, check: bool) -> int:
    """Write the catalog, or check that the file is current.

    Returns:
        Zero when written or current; one when ``check`` finds the file stale.

    """
    text: str = render(build_catalog())
    if not check:
        CATALOG_PATH.write_text(text, encoding="utf-8")
        return 0
    current: str = CATALOG_PATH.read_text(encoding="utf-8") if CATALOG_PATH.is_file() else ""
    if current != text:
        sys.stderr.write(f"{CATALOG_PATH} is stale: run specialist_catalog.py generate\n")
        return 1
    return 0


def _run(args: argparse.Namespace) -> int:
    """Run the parsed command.

    Returns:
        What :func:`main` returns.

    """
    if args.command == "generate":
        return _generate(check=bool(args.check))
    catalog: Catalog = read_catalog()
    if args.command == "find":
        _print({"agents": find(catalog, list(args.words))})
        return 0
    if args.command == "show":
        matched: list[CatalogEntry] = [entry for entry in catalog["agents"] if entry["name"] == args.agent]
        if not matched:
            sys.stderr.write(f"no agent named {args.agent!r} in {CATALOG_PATH}\n")
            return 1
        _print(matched[0])
        return 0
    _print({"agents": [{"name": entry["name"], "description": entry["description"]} for entry in catalog["agents"]]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
