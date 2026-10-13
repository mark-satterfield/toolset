"""Skill files: where a named skill lives, the text a session is given, and what a skill is expertise for.

Claude Code does not place the text of an agent's front matter skills in a session it starts with
``--agent``; the launcher appends that text to the agent's prompt, and this module produces it.

A skill declares the domains it is expertise for in its own front matter, under ``expertiseFor``:
``resourceTypes`` (resource types an Epic's architecture records) and ``terms`` (words and phrases
of a PRD). No table of skills exists anywhere else; ``matching_skills`` reads the declarations.

Run as a command (``bin/atw-expertise``):

- ``match [--resource-type T]... [--text-file F]`` prints ``{"skills": [...]}``, the skills whose
  declaration matches a named resource type or a term found in the file.
- ``text NAME...`` prints the text of the named skills, in the form a launched session is given.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, check_type, typechecked

from . import portfolio_bootstrap  # ruff: ignore[unused-import] - Imported for its sys.path setup.
from .frontmatter import split_front_matter, string_list
from .io import JsonValue, json_object

# isort: split
from driver_surface_types import CONTROL_REPO_ENV

PLUGIN_NAME: Final = "agent-teams-workforce"
SKILLS_DIRECTORY: Final = "skills"
SKILL_FILE: Final = "SKILL.md"
PROJECT_SKILLS: Final = (".claude", "skills")
EXPERTISE_KEY: Final = "expertiseFor"
RESOURCE_TYPES_KEY: Final = "resourceTypes"
TERMS_KEY: Final = "terms"
MATRIX_ENV: Final = "ATW_MATRIX"
"""The matrix file of the control repository. The matrix contract defines the same name."""
MATRIX_NODES: Final = "nodes"
MATRIX_KIND: Final = "kind"
MATRIX_PRD_KIND: Final = "prd"
MATRIX_BEAD: Final = "bead"
MATRIX_EXPERTISE: Final = "expertise"
PLUGIN_ROOT_VARIABLE: Final = "${CLAUDE_PLUGIN_ROOT}"
SKILL_DIRECTORY_VARIABLE: Final = "${CLAUDE_SKILL_DIR}"
SKILLS_HEADING: Final = (
    "# Your skills\n\n"
    "The full text of every skill your definition lists follows. Each one is loaded already: "
    "apply it, and do not call the Skill tool for it."
)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class SkillRoots:
    """The places a skill named in front matter can live."""

    plugin: Path
    config: Path
    control: Path | None

    def __post_init__(self) -> None:
        """Validate every constructed field."""
        check_type(self.plugin, Path)
        check_type(self.config, Path)
        check_type(self.control, Path | None)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class SkillExpertise:
    """What a skill declares itself expertise for."""

    resource_types: frozenset[str]
    terms: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        check_type(self.resource_types, frozenset[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.terms, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class Skill:
    """One skill file, read and validated."""

    name: str
    directory: Path
    plugin_root: Path | None
    body: str
    expertise: SkillExpertise

    def __post_init__(self) -> None:
        """Validate every constructed field."""
        check_type(self.name, str)
        check_type(self.directory, Path)
        check_type(self.plugin_root, Path | None)
        check_type(self.body, str)
        check_type(self.expertise, SkillExpertise)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def installed_plugin(config: Path, name: str) -> Path:
    """Find the installed copy of another plugin from the Claude configuration directory.

    Returns:
        The plugin's install path.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: The plugin is not installed.

    """
    if not isinstance(config, Path) or not isinstance(name, str):
        argument_error: str = "installed_plugin requires the configuration Path and a plugin name"
        raise TypeError(argument_error)
    registry: Path = config / "plugins" / "installed_plugins.json"
    recorded: dict[str, JsonValue] = (
        json_object(json.loads(registry.read_text(encoding="utf-8"))) if registry.exists() else {}
    )
    installed: dict[str, list[dict[str, JsonValue]]] = check_type(
        recorded.get("plugins", {}),
        dict[str, list[dict[str, JsonValue]]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    key: str
    entries: list[dict[str, JsonValue]]
    for key, entries in installed.items():
        if key.split("@", 1)[0] != name:
            continue
        entry: dict[str, JsonValue]
        for entry in entries:
            path: JsonValue = entry.get("installPath")
            if isinstance(path, str) and path:
                return Path(path)
    message: str = f"required skill plugin is not installed: {name}"
    raise ValueError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def skill_plugin(name: str) -> str | None:
    """Name the plugin a skill reference is qualified with.

    Returns:
        The plugin name of ``<plugin>:<skill>``, or None for an unqualified skill name.

    Raises:
        TypeError: ``name`` is not text.

    """
    if not isinstance(name, str):
        argument_error: str = "skill_plugin requires a skill name"
        raise TypeError(argument_error)
    prefix: str
    separator: str
    prefix, separator, _ = name.partition(":")
    return prefix if separator else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def skill_location(roots: SkillRoots, name: str) -> tuple[Path, Path | None]:
    """Find the directory of a skill named in front matter.

    A qualified name ``<plugin>:<skill>`` is a skill of that plugin. An unqualified name is a
    skill of this plugin, else a project skill of the control repository, else a skill of the
    Claude configuration directory.

    Returns:
        The skill's directory, and the root of the plugin it belongs to (None for a project or
        configuration skill).

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: No skill of that name exists in any of those places.

    """
    if not isinstance(roots, SkillRoots) or not isinstance(name, str):
        argument_error: str = "skill_location requires SkillRoots and a skill name"
        raise TypeError(argument_error)
    owner: str | None = skill_plugin(name)
    stem: str = name.rpartition(":")[2]
    if not stem or Path(stem).name != stem:
        message: str = f"not a skill name: {name!r}"
        raise ValueError(message)
    if owner is not None:
        root: Path = roots.plugin if owner == PLUGIN_NAME else installed_plugin(roots.config, owner)
        qualified: Path = root / SKILLS_DIRECTORY / stem
        if (qualified / SKILL_FILE).is_file():
            return qualified, root
        message = f"skill {name} has no {SKILL_FILE} at {qualified}"
        raise ValueError(message)
    own: Path = roots.plugin / SKILLS_DIRECTORY / stem
    if (own / SKILL_FILE).is_file():
        return own, roots.plugin
    candidates: list[Path] = []
    if roots.control is not None:
        project: Path = roots.control.joinpath(*PROJECT_SKILLS)
        candidates.append(project / stem)
        candidates.extend(sorted(project.glob(f"*/{stem}")))
    candidates.append(roots.config / SKILLS_DIRECTORY / stem)
    candidate: Path
    for candidate in candidates:
        if (candidate / SKILL_FILE).is_file():
            return candidate, None
    message = f"skill {name} has no {SKILL_FILE} in the plugin, the control repository or {roots.config}"
    raise ValueError(message)


def _expertise(front: Mapping[str, object], what: str) -> SkillExpertise:
    """Read the ``expertiseFor`` declaration of a skill's front matter.

    Returns:
        The declared resource types and terms; both empty when the skill declares none.

    Raises:
        ValueError: The declaration holds a key other than the two lists, or an empty entry.

    """
    declared: object = front.get(EXPERTISE_KEY)
    if declared is None:
        return SkillExpertise(frozenset(), ())
    fields: dict[str, JsonValue] = json_object(declared)
    unknown: list[str] = sorted(set(fields) - {RESOURCE_TYPES_KEY, TERMS_KEY})
    if unknown:
        message: str = f"{what}: {EXPERTISE_KEY} has unknown keys {unknown}"
        raise ValueError(message)
    resource_types: list[str] = string_list(fields.get(RESOURCE_TYPES_KEY))
    terms: list[str] = string_list(fields.get(TERMS_KEY))
    if not all(entry.strip() for entry in (*resource_types, *terms)):
        message = f"{what}: {EXPERTISE_KEY} has an empty entry"
        raise ValueError(message)
    return SkillExpertise(frozenset(resource_types), tuple(terms))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_skill(roots: SkillRoots, name: str) -> Skill:
    """Read one skill named in front matter.

    Returns:
        The skill, with its body and its expertise declaration.

    A skill that does not exist, has no front matter or declares its expertise wrongly fails with
    the ValueError of ``skill_location``, ``split_front_matter`` or the declaration check.

    Returns:
        The skill, with its body and its expertise declaration.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(roots, SkillRoots) or not isinstance(name, str):
        argument_error: str = "load_skill requires SkillRoots and a skill name"
        raise TypeError(argument_error)
    directory: Path
    plugin_root: Path | None
    directory, plugin_root = skill_location(roots, name)
    front: dict[str, object]
    body: str
    front, body = split_front_matter((directory / SKILL_FILE).read_text(encoding="utf-8"), f"skill {name}")
    return Skill(name, directory.resolve(), plugin_root, body, _expertise(front, f"skill {name}"))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def skill_block(skill: Skill) -> str:
    """Format one skill as the text a session is given in place of Claude Code's own preload.

    The block carries the skill's name, the base directory line Claude Code writes when it loads
    a skill itself, and the skill's body with the variables Claude Code would have replaced.

    Returns:
        The block.

    Raises:
        TypeError: ``skill`` is not a Skill.

    """
    if not isinstance(skill, Skill):
        argument_error: str = "skill_block requires a Skill"
        raise TypeError(argument_error)
    body: str = skill.body.replace(SKILL_DIRECTORY_VARIABLE, str(skill.directory))
    if skill.plugin_root is not None:
        body = body.replace(PLUGIN_ROOT_VARIABLE, str(skill.plugin_root.resolve()))
    return f'<skill name="{skill.name}">\nBase directory for this skill: {skill.directory}\n\n{body}\n</skill>'


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_skills(roots: SkillRoots, names: Iterable[str]) -> list[Skill]:
    """Read the named skills once each, in the order first named.

    Two names that resolve to the same skill directory give one skill, under the first name.

    Returns:
        The skills.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(roots, SkillRoots) or isinstance(names, str):
        argument_error: str = "load_skills requires SkillRoots and skill names"
        raise TypeError(argument_error)
    seen: set[Path] = set()
    loaded: list[Skill] = []
    name: str
    for name in names:
        skill: Skill = load_skill(roots, name)
        if skill.directory not in seen:
            seen.add(skill.directory)
            loaded.append(skill)
    return loaded


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def skills_text(skills: Sequence[Skill]) -> str:
    """Format skills as the section appended to a launched agent's prompt.

    Returns:
        The section, or an empty string for no skills.

    Raises:
        TypeError: ``skills`` is not a sequence of Skill.

    """
    if isinstance(skills, str) or not all(isinstance(skill, Skill) for skill in skills):
        argument_error: str = "skills_text requires a sequence of Skill"
        raise TypeError(argument_error)
    if not skills:
        return ""
    return "\n\n".join([SKILLS_HEADING, *(skill_block(skill) for skill in skills)])


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def matching_skills(plugin: Path, resource_types: Iterable[str], text: str) -> tuple[str, ...]:
    """Name the plugin's skills that declare themselves expertise for these domains.

    A skill matches when one of its declared resource types is among ``resource_types``, or one
    of its declared terms occurs in ``text`` as a whole word or phrase, whatever its letter case.

    Returns:
        The matching skills' directory names, sorted.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(plugin, Path) or isinstance(resource_types, str) or not isinstance(text, str):
        argument_error: str = "matching_skills requires the plugin Path, resource types and a text"
        raise TypeError(argument_error)
    wanted: frozenset[str] = frozenset(resource_types)
    roots: SkillRoots = SkillRoots(plugin, plugin, None)
    matched: list[str] = []
    path: Path
    for path in sorted((plugin / SKILLS_DIRECTORY).glob(f"*/{SKILL_FILE}")):
        name: str = path.parent.name
        expertise: SkillExpertise = load_skill(roots, name).expertise
        if expertise.resource_types & wanted or any(
            re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE) for term in expertise.terms
        ):
            matched.append(name)
    return tuple(matched)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_expertise(bead: str, environ: Mapping[str, str]) -> tuple[str, ...]:
    """Read the expertise list recorded for an Epic: the skills its domains need.

    This is the launcher's one dependency on the matrix. The list is the ``expertise`` field of
    the Epic's PRD row in the matrix file ``ATW_MATRIX`` names.

    Returns:
        The skill names recorded for the Epic; empty when no matrix file is named, the file does
        not exist, or it holds no PRD row for the Epic.

    Raises:
        TypeError: An argument violates the declared input contract, or the matrix file does not
            hold the rows as a JSON object.

    """
    if not isinstance(bead, str) or not isinstance(environ, Mapping):
        argument_error: str = "epic_expertise requires a bead id and an environment mapping"
        raise TypeError(argument_error)
    named: str = environ.get(MATRIX_ENV, "").strip()
    if not named or not Path(named).is_file():
        return ()
    matrix: dict[str, JsonValue] = json_object(json.loads(Path(named).read_text(encoding="utf-8")))
    row: JsonValue
    for row in json_object(matrix.get(MATRIX_NODES, {})).values():
        node: dict[str, JsonValue] = json_object(row)
        if node.get(MATRIX_KIND) == MATRIX_PRD_KIND and node.get(MATRIX_BEAD) == bead:
            return tuple(string_list(node.get(MATRIX_EXPERTISE)))
    return ()


def _command_roots() -> SkillRoots:
    """Resolve the skill roots of a command run from the plugin and the environment.

    Returns:
        This plugin, the Claude configuration directory and the control repository when named.

    """
    control: str = os.environ.get(CONTROL_REPO_ENV, "").strip()
    return SkillRoots(
        Path(__file__).resolve().parents[2],
        Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser(),
        Path(control) if control else None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the expertise command.

    Returns:
        0 after printing the result.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    match: argparse.ArgumentParser = commands.add_parser("match", help="name the skills that are expertise for domains")
    match.add_argument("--resource-type", action="append", default=[], help="a resource type; repeatable")
    match.add_argument("--text-file", type=Path, default=None, help="a file whose text is searched for terms")
    text: argparse.ArgumentParser = commands.add_parser("text", help="print the text of the named skills")
    text.add_argument("names", nargs="+", help="skill names")
    options: argparse.Namespace = parser.parse_args(argv)
    roots: SkillRoots = _command_roots()
    if options.command == "match":
        resource_types: list[str] = string_list(options.resource_type)
        searched: Path | None = check_type(options.text_file, Path | None)
        content: str = searched.read_text(encoding="utf-8") if searched is not None else ""
        sys.stdout.write(json.dumps({"skills": list(matching_skills(roots.plugin, resource_types, content))}) + "\n")
        return 0
    sys.stdout.write(skills_text(load_skills(roots, string_list(options.names))) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
