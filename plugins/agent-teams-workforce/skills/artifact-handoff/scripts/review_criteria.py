"""Read the review criteria and write the review standard from them, or check that it is current.

``skills/effective-architecture/review-criteria.json`` is the one definition of the criteria the
architecture, the TRD and the specs are written to and reviewed against. This module is its typed
reader, and it writes ``skills/effective-architecture/review-standard.md`` from it, so the prose
standard cannot differ from the data. With --check it writes nothing and exits 1 when the
standard differs from what the criteria produce.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, TypeIs

if TYPE_CHECKING:
    from collections.abc import Collection

type Level = Literal["all", "architecture", "technical-requirement", "implementation"]
type Home = Literal["arc42", "trd", "specs"]
type ScopeKind = Literal["heading", "scenario-fact", "trd-requirement", "spec-document"]
"""A kind of unapproved content a reviewer group is selected for.

``heading``: an arc42 heading that was added or changed. ``scenario-fact``: a design fact of
kind ``scenario``. ``trd-requirement``: a TRD requirement that is new or changed.
``spec-document``: a specification document of a repository.
"""

LEVEL_ALL: Final[Literal["all"]] = "all"
LEVEL_ARCHITECTURE: Final[Literal["architecture"]] = "architecture"
LEVEL_TECHNICAL_REQUIREMENT: Final[Literal["technical-requirement"]] = "technical-requirement"
LEVEL_IMPLEMENTATION: Final[Literal["implementation"]] = "implementation"
LEVELS: Final[tuple[Level, ...]] = (
    LEVEL_ALL,
    LEVEL_ARCHITECTURE,
    LEVEL_TECHNICAL_REQUIREMENT,
    LEVEL_IMPLEMENTATION,
)
HOMES: Final[tuple[Home, ...]] = ("arc42", "trd", "specs")
SCOPE_KINDS: Final[tuple[ScopeKind, ...]] = ("heading", "scenario-fact", "trd-requirement", "spec-document")

SKILL_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "effective-architecture"
CRITERIA_PATH: Final[Path] = SKILL_DIR / "review-criteria.json"
STANDARD_PATH: Final[Path] = SKILL_DIR / "review-standard.md"
STANDARD_WIDTH: Final[int] = 92

_DOCUMENT_KEYS: Final[frozenset[str]] = frozenset({"title", "introduction", "levels", "criteria", "reviewerGroups"})
_LEVEL_KEYS: Final[frozenset[str]] = frozenset({"id", "idPrefix", "heading", "note", "responsible", "reviewPoint"})
_RULE_KEYS: Final[frozenset[str]] = frozenset({"id", "level", "text"})
_CRITERION_KEYS: Final[frozenset[str]] = _RULE_KEYS | {"home"}
_GROUP_KEYS: Final[frozenset[str]] = frozenset({"id", "reviewer", "criteria", "appliesWhen"})
_CONDITION_KEYS: Final[frozenset[str]] = frozenset({"scope", "result"})


class ReviewCriteriaError(ValueError):
    """The criteria file does not hold a well-formed set of criteria."""


@dataclass(frozen=True, slots=True)
class LevelSection:
    """One level: its heading in the standard, who writes to it and where it is reviewed."""

    id: Level
    id_prefix: str
    heading: str
    note: str | None
    responsible: tuple[str, ...]
    review_point: str | None


@dataclass(frozen=True, slots=True)
class Criterion:
    """One criterion: its id, its one level, its one home document and its text.

    ``home`` is None only at the level ``all``, whose entries say how to work and demand no
    content of any document.
    """

    id: str
    level: Level
    home: Home | None
    text: str


@dataclass(frozen=True, slots=True)
class AppliesWhen:
    """When a reviewer group is selected: the rule a script applies, with no judgment.

    The group is selected when the unapproved content holds an item of one of the ``scope``
    kinds, or when one of the lists named in ``result`` is not empty in ``reviewSignals`` of the
    solutions architect's result (``ReviewSignals`` in architecture-result.schema.json).
    """

    scope: tuple[ScopeKind, ...]
    result: tuple[str, ...]

    def selects(self, scope_kinds: Collection[ScopeKind], result_signals: Collection[str]) -> bool:
        """Apply the rule to one run.

        Args:
            scope_kinds: The kinds of unapproved content the run holds.
            result_signals: The names of the ``reviewSignals`` lists that are not empty.

        Returns:
            True when the group's reviewer reviews this run.

        Raises:
            TypeError: An argument is a string and not a collection of names.

        """
        if isinstance(scope_kinds, str) or isinstance(result_signals, str):
            message: str = "selects requires two collections of names"
            raise TypeError(message)
        return any(kind in scope_kinds for kind in self.scope) or any(name in result_signals for name in self.result)


@dataclass(frozen=True, slots=True)
class ReviewerGroup:
    """The criteria one reviewer covers, and when that reviewer is selected.

    A criterion may be in more than one group: each group's reviewer reviews it for its own
    specialty.
    """

    id: str
    reviewer: str
    criteria: tuple[str, ...]
    applies_when: AppliesWhen


@dataclass(frozen=True, slots=True)
class Criteria:
    """The whole criteria file."""

    title: str
    introduction: str
    levels: tuple[LevelSection, ...]
    criteria: tuple[Criterion, ...]
    groups: tuple[ReviewerGroup, ...]

    def at_level(self, level: Level) -> tuple[Criterion, ...]:
        """List the criteria of one level, in file order.

        Returns:
            The criteria whose level is ``level``.

        Raises:
            ValueError: ``level`` is not a level.

        """
        if not _is_level(level):
            message: str = f"not a level: {level!r}"
            raise ValueError(message)
        return tuple(entry for entry in self.criteria if entry.level == level)

    def agents(self) -> frozenset[str]:
        """Name every agent the criteria file gives the criteria to.

        Returns:
            The agents responsible for a level and the reviewers of every group.

        """
        responsible: set[str] = {name for section in self.levels for name in section.responsible}
        return frozenset(responsible | {group.reviewer for group in self.groups})


def _is_level(value: object) -> TypeIs[Level]:
    return isinstance(value, str) and value in LEVELS


def _is_home(value: object) -> TypeIs[Home]:
    return isinstance(value, str) and value in HOMES


def _closed(value: object, where: str, keys: frozenset[str]) -> dict[str, object]:
    """Narrow a decoded value to an object with exactly the given keys.

    Returns:
        The object.

    Raises:
        ReviewCriteriaError: The value is not an object or its keys differ.

    """
    if not isinstance(value, dict):
        message: str = f"{where}: expected an object"
        raise ReviewCriteriaError(message)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"{where}: has a key that is not a string"
            raise ReviewCriteriaError(message)
        result[key] = item
    if set(result) != keys:
        message = f"{where}: keys must be exactly {sorted(keys)}, got {sorted(result)}"
        raise ReviewCriteriaError(message)
    return result


def _line(value: object, where: str) -> str:
    """Narrow a decoded value to one nonempty line of text.

    Returns:
        The text.

    Raises:
        ReviewCriteriaError: The value is not a nonempty single-line string.

    """
    if not isinstance(value, str) or not value.strip() or "\n" in value or value != value.strip():
        message: str = f"{where}: expected one nonempty line of text with no surrounding space"
        raise ReviewCriteriaError(message)
    return value


def _items(value: object, where: str) -> list[object]:
    """Narrow a decoded value to a list.

    Returns:
        The list.

    Raises:
        ReviewCriteriaError: The value is not a list.

    """
    if not isinstance(value, list):
        message: str = f"{where}: expected an array"
        raise ReviewCriteriaError(message)
    return list(value)


def _names(value: object, where: str) -> tuple[str, ...]:
    """Narrow a decoded value to a list of distinct names.

    Returns:
        The names in file order.

    Raises:
        ReviewCriteriaError: The value is not a list of distinct nonempty lines.

    """
    names: tuple[str, ...] = tuple(_line(item, f"{where}[{index}]") for index, item in enumerate(_items(value, where)))
    if len(set(names)) != len(names):
        message: str = f"{where}: holds a name twice"
        raise ReviewCriteriaError(message)
    return names


def _level_section(value: object, where: str) -> LevelSection:
    """Read one level.

    Returns:
        The level.

    Raises:
        ReviewCriteriaError: The entry is malformed, or a level other than ``all`` names no
            responsible agent or review point, or ``all`` names one.

    """
    entry: dict[str, object] = _closed(value, where, _LEVEL_KEYS)
    level: object = entry["id"]
    if not _is_level(level):
        message: str = f"{where}.id: {level!r} is not one of {list(LEVELS)}"
        raise ReviewCriteriaError(message)
    note: object = entry["note"]
    review_point: object = entry["reviewPoint"]
    responsible: tuple[str, ...] = _names(entry["responsible"], f"{where}.responsible")
    section: LevelSection = LevelSection(
        id=level,
        id_prefix=_line(entry["idPrefix"], f"{where}.idPrefix"),
        heading=_line(entry["heading"], f"{where}.heading"),
        note=None if note is None else _line(note, f"{where}.note"),
        responsible=responsible,
        review_point=None if review_point is None else _line(review_point, f"{where}.reviewPoint"),
    )
    documented: bool = bool(section.responsible) and section.review_point is not None
    unassigned: bool = not section.responsible and section.review_point is None
    if (level == LEVEL_ALL and not unassigned) or (level != LEVEL_ALL and not documented):
        message = f"{where}: every level but {LEVEL_ALL!r} names its responsible agents and its review point"
        raise ReviewCriteriaError(message)
    return section


def _criterion(value: object, where: str) -> Criterion:
    """Read one criterion.

    Returns:
        The criterion, with exactly one level and, below the level ``all``, exactly one home.

    Raises:
        ReviewCriteriaError: The entry is malformed.

    """
    if not isinstance(value, dict):
        message: str = f"{where}: expected an object"
        raise ReviewCriteriaError(message)
    level: object = value.get("level")
    if not _is_level(level):
        message = f"{where}.level: {level!r} is not one of {list(LEVELS)}"
        raise ReviewCriteriaError(message)
    entry: dict[str, object] = _closed(value, where, _RULE_KEYS if level == LEVEL_ALL else _CRITERION_KEYS)
    home: object = entry.get("home")
    if level != LEVEL_ALL and not _is_home(home):
        message = f"{where}.home: {home!r} is not one of {list(HOMES)}"
        raise ReviewCriteriaError(message)
    return Criterion(
        id=_line(entry["id"], f"{where}.id"),
        level=level,
        home=home if _is_home(home) else None,
        text=_line(entry["text"], f"{where}.text"),
    )


def _is_scope_kind(value: object) -> TypeIs[ScopeKind]:
    return isinstance(value, str) and value in SCOPE_KINDS


def _applies_when(value: object, where: str) -> AppliesWhen:
    """Read the rule that selects one reviewer group.

    Returns:
        The rule.

    Raises:
        ReviewCriteriaError: The entry is malformed, names an unknown kind of unapproved content,
            or states no condition.

    """
    entry: dict[str, object] = _closed(value, where, _CONDITION_KEYS)
    scope: tuple[ScopeKind, ...] = tuple(
        kind for kind in _names(entry["scope"], f"{where}.scope") if _is_scope_kind(kind)
    )
    result: tuple[str, ...] = _names(entry["result"], f"{where}.result")
    if len(scope) != len(_items(entry["scope"], f"{where}.scope")):
        message: str = f"{where}.scope: every entry is one of {list(SCOPE_KINDS)}"
        raise ReviewCriteriaError(message)
    if not scope and not result:
        message = f"{where}: a group states at least one condition that selects it"
        raise ReviewCriteriaError(message)
    return AppliesWhen(scope=scope, result=result)


def _group(value: object, where: str) -> ReviewerGroup:
    """Read one reviewer group.

    A malformed selection rule fails with the ReviewCriteriaError of ``_applies_when``.

    Returns:
        The group.

    Raises:
        ReviewCriteriaError: The entry is malformed or covers no criterion.

    """
    entry: dict[str, object] = _closed(value, where, _GROUP_KEYS)
    criteria: tuple[str, ...] = _names(entry["criteria"], f"{where}.criteria")
    if not criteria:
        message: str = f"{where}.criteria: a group covers at least one criterion"
        raise ReviewCriteriaError(message)
    return ReviewerGroup(
        id=_line(entry["id"], f"{where}.id"),
        reviewer=_line(entry["reviewer"], f"{where}.reviewer"),
        criteria=criteria,
        applies_when=_applies_when(entry["appliesWhen"], f"{where}.appliesWhen"),
    )


def _check_levels(levels: tuple[LevelSection, ...]) -> None:
    """Require each level once, in order, each with its own id prefix.

    Raises:
        ReviewCriteriaError: A level is missing, repeated or out of order, or two share a prefix.

    """
    if tuple(section.id for section in levels) != LEVELS:
        message: str = f"levels: must be exactly {list(LEVELS)}, in that order"
        raise ReviewCriteriaError(message)
    prefixes: list[str] = [section.id_prefix for section in levels]
    if len(set(prefixes)) != len(prefixes):
        message = "levels: two levels share an id prefix"
        raise ReviewCriteriaError(message)


def _check_criteria(levels: tuple[LevelSection, ...], criteria: tuple[Criterion, ...]) -> None:
    """Require ids numbered from 1 within each level, and one home document per level.

    Raises:
        ReviewCriteriaError: An id does not fit its level, a level has no criterion, the
            criteria of one level name two homes, or two levels share a home.

    """
    homes: dict[Level, Home] = {}
    section: LevelSection
    for section in levels:
        members: list[Criterion] = [entry for entry in criteria if entry.level == section.id]
        expected: list[str] = [f"{section.id_prefix}{number}" for number in range(1, len(members) + 1)]
        if not members or [entry.id for entry in members] != expected:
            message: str = f"criteria: level {section.id!r} must hold {section.id_prefix}1 onward, numbered in order"
            raise ReviewCriteriaError(message)
        found: set[Home] = {entry.home for entry in members if entry.home is not None}
        if section.id == LEVEL_ALL:
            continue
        if len(found) != 1:
            message = f"criteria: level {section.id!r} must have exactly one home document, got {sorted(found)}"
            raise ReviewCriteriaError(message)
        homes[section.id] = next(iter(found))
    if len(set(homes.values())) != len(homes):
        message = f"criteria: two levels share a home document: {homes}"
        raise ReviewCriteriaError(message)


def _check_groups(criteria: tuple[Criterion, ...], groups: tuple[ReviewerGroup, ...]) -> None:
    """Require every group to name real criteria and every document criterion to have a reviewer.

    Raises:
        ReviewCriteriaError: Two groups share an id, a group names an unknown criterion, or a
            criterion below the level ``all`` is in no group.

    """
    identifiers: list[str] = [group.id for group in groups]
    if len(set(identifiers)) != len(identifiers):
        message: str = "reviewerGroups: two groups share an id"
        raise ReviewCriteriaError(message)
    known: set[str] = {entry.id for entry in criteria}
    covered: set[str] = {identifier for group in groups for identifier in group.criteria}
    unknown: set[str] = covered - known
    if unknown:
        message = f"reviewerGroups: unknown criteria {sorted(unknown)}"
        raise ReviewCriteriaError(message)
    unreviewed: list[str] = [entry.id for entry in criteria if entry.level != LEVEL_ALL and entry.id not in covered]
    if unreviewed:
        message = f"reviewerGroups: no group reviews {unreviewed}"
        raise ReviewCriteriaError(message)


def parse_criteria(value: object) -> Criteria:
    """Validate a decoded criteria file and narrow it.

    A document that is not a well-formed set of criteria fails with ReviewCriteriaError, raised
    by the reader of the entry at fault; the message names that entry.

    Args:
        value: The decoded JSON document.

    Returns:
        The criteria.

    """
    document: dict[str, object] = _closed(value, "review criteria", _DOCUMENT_KEYS)
    levels: tuple[LevelSection, ...] = tuple(
        _level_section(item, f"levels[{index}]") for index, item in enumerate(_items(document["levels"], "levels"))
    )
    criteria: tuple[Criterion, ...] = tuple(
        _criterion(item, f"criteria[{index}]") for index, item in enumerate(_items(document["criteria"], "criteria"))
    )
    groups: tuple[ReviewerGroup, ...] = tuple(
        _group(item, f"reviewerGroups[{index}]")
        for index, item in enumerate(_items(document["reviewerGroups"], "reviewerGroups"))
    )
    _check_levels(levels)
    _check_criteria(levels, criteria)
    _check_groups(criteria, groups)
    return Criteria(
        title=_line(document["title"], "title"),
        introduction=_line(document["introduction"], "introduction"),
        levels=levels,
        criteria=criteria,
        groups=groups,
    )


def load_criteria(path: Path = CRITERIA_PATH) -> Criteria:
    """Read and validate a criteria file.

    A read failure (OSError), a decode failure (json.JSONDecodeError) or a malformed set of
    criteria (ReviewCriteriaError, from ``parse_criteria``) propagates unchanged.

    Args:
        path: The criteria file.

    Returns:
        The criteria.

    Raises:
        TypeError: ``path`` is not a Path.

    """
    if not isinstance(path, Path):
        message: str = "load_criteria requires a Path"
        raise TypeError(message)
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    return parse_criteria(decoded)


def render_standard(criteria: Criteria) -> str:
    """Render the review standard from the criteria.

    Args:
        criteria: The criteria.

    Returns:
        The complete Markdown text of review-standard.md.

    Raises:
        TypeError: ``criteria`` is not a Criteria.

    """
    if not isinstance(criteria, Criteria):
        message: str = "render_standard requires a Criteria"
        raise TypeError(message)
    blocks: list[str] = [
        f"<!-- GENERATED from {CRITERIA_PATH.name} by {Path(__file__).name}. Edit {CRITERIA_PATH.name}. -->",
        f"# {criteria.title}",
        textwrap.fill(criteria.introduction, width=STANDARD_WIDTH),
    ]
    section: LevelSection
    for section in criteria.levels:
        members: tuple[Criterion, ...] = criteria.at_level(section.id)
        label_width: int = max(len(entry.id) for entry in members) + 2
        blocks.append(f"## {section.heading}")
        if section.note is not None:
            blocks.append(textwrap.fill(section.note, width=STANDARD_WIDTH))
        blocks.append(
            "\n".join(
                textwrap.fill(
                    entry.text,
                    width=STANDARD_WIDTH,
                    initial_indent=f"{entry.id}.".ljust(label_width),
                    subsequent_indent=" " * label_width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                for entry in members
            ),
        )
    return "\n\n".join(blocks) + "\n"


def criterion_ids(text: str) -> list[str]:
    """List the criterion ids a rendered standard states, in order.

    Args:
        text: The text of a review standard.

    Returns:
        The id that opens each criterion line.

    Raises:
        TypeError: ``text`` is not a string.

    """
    if not isinstance(text, str):
        message: str = "criterion_ids requires a string"
        raise TypeError(message)
    return re.findall(r"^([A-Z][1-9][0-9]*)\.\s", text, flags=re.MULTILINE)


def main() -> int:
    """Write the review standard, or with --check report whether it is current.

    Returns:
        0 when written or current, 1 when --check finds the standard stale or missing.

    Raises:
        TypeError: The parsed --check flag is not a boolean.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when review-standard.md is stale")
    args: argparse.Namespace = parser.parse_args()
    check: object = args.check
    if not isinstance(check, bool):
        message: str = "--check must be a flag"
        raise TypeError(message)
    expected: str = render_standard(load_criteria())
    if check:
        current: str | None = STANDARD_PATH.read_text(encoding="utf-8") if STANDARD_PATH.is_file() else None
        if current != expected:
            sys.stderr.write(f"{STANDARD_PATH} is stale against {CRITERIA_PATH}; run {Path(__file__).name}\n")
            return 1
        return 0
    STANDARD_PATH.write_text(expected, encoding="utf-8")
    sys.stdout.write(f"wrote {STANDARD_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
