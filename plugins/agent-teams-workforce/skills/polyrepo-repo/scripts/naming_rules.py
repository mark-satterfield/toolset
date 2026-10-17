"""The project's repository naming rules, read from the vault's repository naming note.

The note is the one source of the rules: which prefix each project's repositories carry, the
repository types, the patterns a name must match (with the section of the note that states
each), and the deprecated prefix. This module reads those rules from the note's own text each time
the tool runs and keeps no copy of them. A rule the note does not state raises
NamingRulesError, naming the missing rule; there is no built-in rule to fall back on.

A project is an open token. The note's project table lists the projects that exist today, and is
not a limit: a name whose first token is no listed project, no deprecated prefix and no
non-application type is checked by its shape, `{project}[-team]-{domain}-{type}`, with `{type}`
one of the types the note lists. Its project is its first token.

The parser keys on the note's structure: the table whose header has a `Project` column and a
`Prefix` column; the "`{type}` is one of ..." sentence; the `### <project> repositories`
sections under the patterns, each with a `**Pattern:**` line.
"""

from __future__ import annotations

import dataclasses
import re
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from pathlib import Path

HYPHEN = "-"
KIND_APPLICATION = "application"
KIND_NON_APPLICATION = "non-application"
KIND_DEPRECATED = "deprecated"
PATTERN_LABEL = "**Pattern:**"
SECTION_SUFFIX = " repositories"
ALL_LOWERCASE = "all lowercase"
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
TYPES_SENTENCE = re.compile(r"`\{type\}` is one of (.+?)\.(?:\s|$)", re.DOTALL)
CODE_SPAN = re.compile(r"`([^`]+)`")
TYPE_MEANING = re.compile(r"`([a-z]+)` is ")
WORD_CAMEL = "[a-z0-9][A-Za-z0-9]*"
WORD_LOWER = "[a-z0-9]+"
NAME_SLOT = "{name}"
TYPE_SLOT = "{type}"
PATTERN_LEVEL = 3
OPEN_PROJECT = "open project"
OPEN_SECTION = "Shape"
OPEN_PROJECT_WORD = "[a-z][A-Za-z0-9]*"


class NamingRulesError(Exception):
    """The naming note is unreadable, or does not state a rule the tool needs."""


class NamingPattern(TypedDict):
    """One naming pattern, built from a `**Pattern:**` line of the naming note."""

    name: str
    kind: str
    regex: str
    section: str
    rule: str
    space: NotRequired[str]
    prefix: NotRequired[str]


@dataclasses.dataclass(frozen=True)
class Section:
    """One heading of the note and the text under it, up to the next heading."""

    level: int
    title: str
    body: str


@dataclasses.dataclass(frozen=True)
class NamingRules:
    """The repository naming rules, as the naming note states them."""

    document: Path
    prefixes: dict[str, str]
    types: tuple[str, ...]
    patterns: tuple[NamingPattern, ...]
    bare_names: frozenset[str]
    deprecated_prefix: str
    reserved_tokens: frozenset[str]

    @property
    def open_regex(self) -> str:
        """The shape a name of a project the note's table does not list must have.

        Returns:
            `{project}[-team]-{domain}-{type}`: the project and the domain one camelCase token
            each, `{type}` one of the note's types.

        """
        types = "|".join(map(re.escape, self.types))
        return f"{OPEN_PROJECT_WORD}(?:-team)?-{WORD_CAMEL}-(?:{types})"

    def _open_project(self, name: str) -> NamingPattern | None:
        """Match a name whose first token is a project the note's table does not list.

        Returns:
            The open-project pattern, its space the first token, or None when the first token
            is a listed project, the deprecated prefix or a non-application type, or the name
            does not have the shape.

        """
        token = name.partition(HYPHEN)[0]
        if token.lower() in self.reserved_tokens or not re.fullmatch(self.open_regex, name):
            return None
        return NamingPattern(
            name=OPEN_PROJECT,
            kind=KIND_APPLICATION,
            regex=f"(?:{self.open_regex})",
            section=OPEN_SECTION,
            rule=f"`{{project}}[-team]-{{domain}}-{{type}}`, `{{type}}` one of {', '.join(self.types)}",
            space=token,
        )

    def is_deprecated(self, name: str) -> bool:
        """Tell whether a name carries the deprecated prefix.

        Returns:
            True when the name starts with the prefix the note gives deprecated repositories.

        """
        return name.startswith(self.deprecated_prefix)

    def deprecated_name(self, name: str) -> str:
        """Return the deprecated name of a repository: the deprecated prefix, then the name in lower case.

        Returns:
            The new name.

        """
        return self.deprecated_prefix + name.lower()

    def deprecated_base(self, name: str) -> str:
        """Return the name a deprecated name was made from, without the prefix.

        Returns:
            The name after the prefix; a name without the prefix unchanged.

        """
        return name.removeprefix(self.deprecated_prefix)

    def _underlying(self, rest: str) -> NamingPattern | None:
        """Find the non-deprecated pattern a deprecated name's remainder matches, in any case.

        Returns:
            The pattern, or None.

        """
        if not rest or rest != rest.lower():
            return None
        return next(
            (
                p
                for p in self.patterns
                if p["kind"] != KIND_DEPRECATED and re.fullmatch(p["regex"], rest, re.IGNORECASE)
            ),
            None,
        )

    def classify(self, name: str) -> NamingPattern | None:
        """Return the first pattern the name matches.

        An application name must also end in a repository type the note lists; the
        command-and-control repository, a name the note gives without `{name}`, is exempt, and
        so are non-application and deprecated names. A name of a project the note's table does
        not list is checked by its shape (`open_regex`).

        Returns:
            The pattern, or None when no pattern matches or the last token is no listed type.

        """
        for p in self.patterns:
            if p["kind"] == KIND_DEPRECATED:
                if self.is_deprecated(name) and self._underlying(self.deprecated_base(name)):
                    return p
            elif re.fullmatch(p["regex"], name):
                typed = p["kind"] != KIND_APPLICATION or name in self.bare_names
                return p if typed or type_of(name) in self.types else None
        return self._open_project(name)

    def problem(self, name: str) -> str:
        """Say why a name is refused: no pattern matches, or its last token is no listed type.

        Returns:
            One sentence naming the rule the name breaks.

        """
        if self.classify(name) is not None:
            return "it matches a naming pattern, but not an application one"
        open_token = name.partition(HYPHEN)[0].lower() not in self.reserved_tokens
        shaped = open_token and re.fullmatch(f"{OPEN_PROJECT_WORD}(?:-team)?-{WORD_CAMEL}-{WORD_LOWER}", name)
        if shaped or any(re.fullmatch(p["regex"], name) for p in self.patterns if p["kind"] != KIND_DEPRECATED):
            last = type_of(name)
            return f"its last token {last!r} is not a repository type the naming note lists ({', '.join(self.types)})"
        return "it matches no pattern the naming note states, and not the shape {project}[-team]-{domain}-{type}"

    def summary(self) -> dict[str, object]:
        """Describe what was read from the note, for a report.

        Returns:
            The note's path and the rules read from it.

        """
        return {
            "document": str(self.document),
            "prefixes": self.prefixes,
            "types": list(self.types),
            "patterns": [{k: v for k, v in p.items() if k != "regex"} for p in self.patterns],
            "deprecated_prefix": self.deprecated_prefix,
            "open_project_shape": "{project}[-team]-{domain}-{type}",
        }


def _missing(doc: Path, what: str) -> str:
    """Build the message for a rule the note does not state.

    Returns:
        The sentence naming the note and the missing rule.

    """
    return f"{doc.name} does not state {what}"


def type_of(name: str) -> str:
    """Return the repository type a name carries: its last hyphen-separated token.

    Returns:
        The token; the whole name when it has no hyphen.

    """
    return name.rpartition(HYPHEN)[2]


def _split_sections(text: str) -> list[Section]:
    """Split a note at its headings.

    Returns:
        The sections in order; the text before the first heading is a section of level 0.

    """
    sections: list[Section] = []
    level, title = 0, ""
    lines: list[str] = []
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            sections.append(Section(level, title, "\n".join(lines)))
            level, title, lines = len(m.group(1)), m.group(2), []
        else:
            lines.append(line)
    sections.append(Section(level, title, "\n".join(lines)))
    return sections


def _markdown_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Read every Markdown table in a note: its header cells and its body rows.

    Returns:
        (header cells, body rows) per table, cells stripped, the separator row left out.

    """
    tables: list[list[list[str]]] = []
    run_open = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            run_open = False
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not run_open:
            tables.append([])
            run_open = True
        if not all(re.fullmatch(r":?-+:?", c) for c in cells):
            tables[-1].append(cells)
    return [(t[0], t[1:]) for t in tables if t]


def _first_code(cell: str) -> str | None:
    """Return the first `code` span of a table cell.

    Returns:
        The span's text, or None when the cell has none.

    """
    m = CODE_SPAN.search(cell)
    return m.group(1) if m else None


def _read_prefixes(doc: Path, text: str) -> dict[str, str]:
    """Read each project's repository prefix from the note's table that lists them.

    The table is the one whose header has a column that begins with "Project" and a column
    that begins with "Prefix". A row's project is the first code span of its project cell
    (the whole cell when it has none), and its prefix the first code span of its prefix cell.

    Returns:
        Each project's repository prefix.

    Raises:
        NamingRulesError: when the note has no such table.

    """
    for header, rows in _markdown_tables(text):
        cols = [h.lower() for h in header]
        project = next((i for i, h in enumerate(cols) if h.startswith("project")), None)
        prefix = next((i for i, h in enumerate(cols) if h.startswith("prefix")), None)
        if project is None or prefix is None:
            continue
        out: dict[str, str] = {}
        for row in rows:
            if len(row) <= max(project, prefix):
                continue
            p, x = _first_code(row[project]) or row[project].strip(), _first_code(row[prefix])
            if p and x:
                out[p] = x
        if out:
            return out
    msg = _missing(doc, "each project's repository prefix in a table with a Project column and a Prefix column")
    raise NamingRulesError(msg)


def _read_types(doc: Path, text: str) -> tuple[str, ...]:
    """Read the repository types from the sentence "`{type}` is one of ...".

    Returns:
        The types, in the order the note lists them.

    Raises:
        NamingRulesError: when the note has no such sentence or it lists no type.

    """
    m = TYPES_SENTENCE.search(text)
    types = tuple(CODE_SPAN.findall(m.group(1))) if m else ()
    if not types:
        msg = _missing(doc, "the repository types (a sentence reading '`{type}` is one of ...')")
        raise NamingRulesError(msg)
    return types


def _span_regex(doc: Path, span: str, type_alt: str | None, word: str) -> str:
    """Turn one pattern written in the note into a regular expression.

    `{name}` is one or more hyphen-separated tokens, each in the case the note's pattern line
    states; `{type}` is one of the types the pattern's own section lists.

    Returns:
        The regular expression, without anchors.

    Raises:
        NamingRulesError: when the pattern uses `{type}` and its section lists none.

    """
    out = ""
    for part in re.split(r"(\{type\}|\{name\})", span):
        if part == NAME_SLOT:
            out += f"{word}(?:-{word})*"
        elif part == TYPE_SLOT:
            if not type_alt:
                msg = _missing(doc, f"the values of {{type}} for the pattern {span}")
                raise NamingRulesError(msg)
            out += f"(?:{type_alt})"
        else:
            out += re.escape(part)
    return out


def _read_pattern(
    doc: Path,
    sec: Section,
    prefixes: dict[str, str],
) -> tuple[NamingPattern, list[str]]:
    """Read the pattern a `### <name> repositories` section states.

    Returns:
        The pattern, and the names it states without `{name}` (the command-and-control repository).

    Raises:
        NamingRulesError: when the section is no project's and no non-application or
            deprecated section, or states its pattern incompletely.

    """
    line = next(ln for ln in sec.body.splitlines() if ln.startswith(PATTERN_LABEL))
    name = sec.title.removesuffix(SECTION_SUFFIX)
    spans = CODE_SPAN.findall(line)
    if not spans:
        msg = _missing(doc, f"a pattern in a code span under '{sec.title}'")
        raise NamingRulesError(msg)
    lowercase = ALL_LOWERCASE in line
    word = WORD_LOWER if lowercase else WORD_CAMEL
    pat = NamingPattern(name=name, kind=KIND_APPLICATION, regex="", section=sec.title, rule=line.strip())
    bare: list[str] = []
    if name == KIND_NON_APPLICATION:
        pat["kind"] = KIND_NON_APPLICATION
        types = TYPE_MEANING.findall(sec.body)
        pat["regex"] = "|".join(_span_regex(doc, s, "|".join(map(re.escape, types)), word) for s in spans)
    elif name == KIND_DEPRECATED:
        prefix = spans[0].partition("{")[0]
        if not prefix or not lowercase:
            msg = _missing(doc, "the deprecated prefix, or that a deprecated name is in lower case")
            raise NamingRulesError(msg)
        pat["kind"] = KIND_DEPRECATED
        pat["prefix"] = prefix
        pat["regex"] = re.escape(prefix) + ".+"
    elif name in prefixes:
        pat["space"] = name
        for s in spans:
            if NAME_SLOT in s and s.partition(NAME_SLOT)[0] != prefixes[name]:
                msg = (
                    f"{doc.name}: the pattern {s} under '{sec.title}' does not start with the prefix "
                    f"{prefixes[name]} its table gives {name}"
                )
                raise NamingRulesError(msg)
            if NAME_SLOT not in s:
                bare.append(s)
        pat["regex"] = "|".join(_span_regex(doc, s, None, word) for s in spans)
    else:
        msg = _missing(doc, f"which project '{sec.title}' is (its table lists {', '.join(prefixes)})")
        raise NamingRulesError(msg)
    pat["regex"] = f"(?:{pat['regex']})"
    return pat, bare


def _read_patterns(
    doc: Path,
    sections: list[Section],
    prefixes: dict[str, str],
) -> tuple[tuple[NamingPattern, ...], frozenset[str], str]:
    """Read every pattern the note states.

    Returns:
        The patterns in the note's order, the names stated without `{name}`, and the deprecated prefix.

    Raises:
        NamingRulesError: when a project of the table, the non-application repositories or
            the deprecated repositories have no pattern.

    """
    patterns: list[NamingPattern] = []
    bare: list[str] = []
    for sec in sections:
        if sec.level == PATTERN_LEVEL and PATTERN_LABEL in sec.body:
            pat, names = _read_pattern(doc, sec, prefixes)
            patterns.append(pat)
            bare.extend(names)
    spaces = {p.get("space") for p in patterns}
    for project in prefixes:
        if project not in spaces:
            msg = _missing(doc, f"a pattern for the {project} repositories")
            raise NamingRulesError(msg)
    deprecated = next((p for p in patterns if p["kind"] == KIND_DEPRECATED), None)
    if deprecated is None:
        msg = _missing(doc, "a pattern for deprecated repositories")
        raise NamingRulesError(msg)
    if not any(p["kind"] == KIND_NON_APPLICATION for p in patterns):
        msg = _missing(doc, "a pattern for non-application repositories")
        raise NamingRulesError(msg)
    return tuple(patterns), frozenset(bare), deprecated.get("prefix", "")


def read_rules(path: Path) -> NamingRules:
    """Read the repository naming rules from the naming note at `path`.

    Returns:
        The rules.

    Raises:
        NamingRulesError: when the note cannot be read, or does not state a rule the tool needs.

    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        msg = f"cannot read the repository naming note {path}: {exc}"
        raise NamingRulesError(msg) from exc
    sections = _split_sections(text)
    prefixes = _read_prefixes(path, text)
    types = _read_types(path, text)
    patterns, bare, deprecated_prefix = _read_patterns(path, sections, prefixes)
    non_application = {
        t
        for sec in sections
        if sec.title.removesuffix(SECTION_SUFFIX) == KIND_NON_APPLICATION
        for t in TYPE_MEANING.findall(sec.body)
    }
    reserved = {x.rstrip(HYPHEN).lower() for x in (*prefixes.values(), deprecated_prefix)} | non_application
    return NamingRules(
        document=path,
        prefixes=prefixes,
        types=types,
        patterns=patterns,
        bare_names=bare,
        deprecated_prefix=deprecated_prefix,
        reserved_tokens=frozenset(reserved),
    )
