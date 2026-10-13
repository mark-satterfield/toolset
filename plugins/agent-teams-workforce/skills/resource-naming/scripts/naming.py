#!/usr/bin/env python3
"""Generate and check resource names from a project's resource naming config.

The rules live in the project, not here: a YAML file (`.resource-naming.yaml`) names the
projects and their name prefixes, the segment styles, the domain reference table and one
pattern per resource type. This script only applies them, deterministically.

Usage:
  naming.py name <resource-type> --project P [--team] [--domain X] [--<segment> VALUE ...]
  naming.py check <resource-type> <name> [--project P] [--<segment> VALUE ...]
  naming.py list
  naming.py where

The config is found, in order: `--config PATH`; `$RESOURCE_NAMING_CONFIG`;
`.resource-naming.yaml` in the control repository named by the environment variable
`driver_surface_types.CONTROL_REPO_ENV` (pipeline-contracts skill); the first `.resource-naming.yaml` in the working
directory or any directory above it. With none of these the script exits 2. There are no
built-in defaults.

Pattern grammar: `{segment}` is a value the caller supplies, `{segment|transform}` applies
`lower`, `kebab`, `snake` or `upper_snake` to it, `[...]` is optional and is emitted only
when every segment inside it is supplied, and everything else is literal. `{project}` is the
name prefix of the project given with `--project` (required by `name` for every pattern that
uses it), `{projectLower}` is that prefix lowercased and `{metricsNamespace}` is the project's
metrics namespace. A segment declared with `flag: <word>` (the `team` qualifier) is a
value-less CLI flag that inserts that word. `check` accepts any project's prefix unless
`--project` narrows it. A project may restrict `{type}` to the types of its categories.
`check` also takes segment flags: each one given must be the value the name carries in that
segment, after the pattern's transform (`check python-package <name> --domain dataAccess`).

Exit codes: 0 ok; 1 a name fails `check`, or `name` was given invalid input; 2 the config
is missing or invalid, or the resource type is unknown.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline-contracts" / "scripts"))
from driver_surface_types import CONTROL_REPO_ENV

# PyYAML is optional until a config is loaded: its absence is reported as a config error
# by `load_rules`, not as an import failure, so `--help` works without it.
try:
    import yaml

    YAML_IMPORT_ERROR: ImportError | None = None
except ImportError as _yaml_exc:
    YAML_IMPORT_ERROR = _yaml_exc

CONFIG_ENV = "RESOURCE_NAMING_CONFIG"
CONFIG_FILE = ".resource-naming.yaml"

#: Regex for a value of each segment style.
STYLES: dict[str, str] = {
    "camelCase": r"[a-z][a-zA-Z0-9]*",
    "PascalCase": r"[A-Z][a-zA-Z0-9]*",
    "lowercase": r"[a-z0-9]+",
    "kebab": r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*",
    "hyphenated": r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*",
    "region": r"[a-z]{2}(?:-[a-z]+)+-[0-9]",
    "az": r"[a-z]{2}(?:-[a-z]+)+-[0-9][a-z]",
    "accountId": r"[0-9]{12}",
}

#: Regex for the output of each transform applied to a word-style value.
TRANSFORM_REGEX: dict[str, str] = {
    "lower": r"[a-z0-9]+",
    "kebab": r"[a-z0-9]+(?:-[a-z0-9]+)*",
    "snake": r"[a-z0-9]+(?:_[a-z0-9]+)*",
    "upper_snake": r"[A-Z0-9]+(?:_[A-Z0-9]+)*",
}

CONSTANTS = ("project", "projectLower", "metricsNamespace")


class NamingError(Exception):
    """A name or an input breaks the naming rules (exit 1)."""


class ConfigError(Exception):
    """The config is missing, unreadable or inconsistent (exit 2)."""


def words(value: str) -> list[str]:
    """Split a camelCase, PascalCase, kebab, snake or dotted value into lowercase words.

    Returns:
        The words, lowercased, in order.

    """
    out: list[str] = []
    for part in re.split(r"[^A-Za-z0-9]+", value):
        out.extend(w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+", part))
    return out


def transform(value: str, how: str) -> str:
    """Apply a pattern transform to a segment value.

    Returns:
        The transformed value.

    Raises:
        ConfigError: If the transform is unknown.

    """
    if how == "lower":
        return value.lower()
    if how == "kebab":
        return "-".join(words(value))
    if how == "snake":
        return "_".join(words(value))
    if how == "upper_snake":
        return "_".join(words(value)).upper()
    msg: str = f"unknown transform '{how}'"
    raise ConfigError(msg)


@dataclass
class Node:
    """One piece of a parsed pattern: literal text, a placeholder, or an optional group."""

    kind: str  # "lit" | "var" | "opt"
    text: str = ""
    transform: str = ""
    children: list[Node] = field(default_factory=list)


def flush_literal(nodes: list[Node], buf: str) -> str:
    """Append pending literal text to the nodes when there is any.

    Returns:
        The emptied buffer ("").

    """
    if buf:
        nodes.append(Node("lit", buf))
    return ""


class PatternParser:
    """A recursive-descent parser over one pattern string."""

    def __init__(self, pattern: str) -> None:
        """Start parsing `pattern` at its first character."""
        self.pattern: str = pattern
        self.pos: int = 0

    def parse_var(self, nodes: list[Node]) -> None:
        """Parse the `{segment|transform}` placeholder that starts at the current position.

        Raises:
            ConfigError: If the placeholder has no closing brace.

        """
        end: int = self.pattern.find("}", self.pos)
        if end < 0:
            msg: str = f"unclosed '{{' in pattern {self.pattern!r}"
            raise ConfigError(msg)
        name, _, how = self.pattern[self.pos + 1 : end].partition("|")
        nodes.append(Node("var", name.strip(), how.strip()))
        self.pos = end + 1

    def parse(self, until: str | None) -> list[Node]:
        """Parse nodes up to the closing `until` character, or to the end when None.

        Returns:
            The nodes parsed at this level.

        Raises:
            ConfigError: If brackets or braces are unbalanced.

        """
        nodes: list[Node] = []
        buf: str = ""
        msg: str
        while self.pos < len(self.pattern):
            ch: str = self.pattern[self.pos]
            if until and ch == until:
                self.pos += 1
                flush_literal(nodes, buf)
                return nodes
            if ch == "{":
                buf = flush_literal(nodes, buf)
                self.parse_var(nodes)
            elif ch == "[":
                buf = flush_literal(nodes, buf)
                self.pos += 1
                nodes.append(Node("opt", children=self.parse("]")))
            elif ch in "]}":
                msg = f"unbalanced '{ch}' in pattern {self.pattern!r}"
                raise ConfigError(msg)
            else:
                buf += ch
                self.pos += 1
        if until:
            msg = f"unclosed '[' in pattern {self.pattern!r}"
            raise ConfigError(msg)
        flush_literal(nodes, buf)
        return nodes


def parse_pattern(pattern: str) -> list[Node]:
    """Parse a pattern into nodes; unbalanced brackets or braces raise ConfigError.

    Returns:
        The top-level nodes.

    """
    return PatternParser(pattern).parse(None)


def placeholders(nodes: list[Node], optional: bool = False) -> list[tuple[str, bool]]:
    """List the caller-supplied placeholders of a pattern.

    Returns:
        (segment name, is optional) pairs in pattern order, constants excluded.

    """
    out: list[tuple[str, bool]] = []
    for n in nodes:
        if n.kind == "var" and n.text not in CONSTANTS:
            out.append((n.text, optional))
        elif n.kind == "opt":
            out.extend(placeholders(n.children, True))
    return out


def flatten_vars(nodes: list[Node]) -> list[Node]:
    """List every placeholder of a pattern in the order `Rules.regex` numbers its groups.

    Returns:
        The placeholder nodes, project constants included, optional groups flattened.

    """
    out: list[Node] = []
    for n in nodes:
        if n.kind == "var":
            out.append(n)
        elif n.kind == "opt":
            out.extend(flatten_vars(n.children))
    return out


def uses_constants(nodes: list[Node]) -> bool:
    """Tell whether a pattern uses a project constant anywhere.

    Returns:
        True when `{project}`, `{projectLower}` or `{metricsNamespace}` appears.

    """
    return any(
        (n.kind == "var" and n.text in CONSTANTS) or (n.kind == "opt" and uses_constants(n.children)) for n in nodes
    )


def trailing_literal(nodes: list[Node]) -> str:
    """Return the literal text after the pattern's last placeholder or group.

    Returns:
        The trailing literal, or "" when the pattern ends with a placeholder.

    """
    return nodes[-1].text if nodes and nodes[-1].kind == "lit" else ""


def leading_literal(nodes: list[Node]) -> str:
    """Return the literal text before the pattern's first placeholder or group.

    Returns:
        The leading literal, or "" when the pattern starts with a placeholder.

    """
    return nodes[0].text if nodes and nodes[0].kind == "lit" else ""


def kebab_flag(segment: str) -> str:
    """Return the CLI flag for a segment name (`resourceType` -> `--resource-type`).

    Returns:
        The flag.

    """
    return "--" + "-".join(words(segment))


def render(nodes: list[Node], constants: dict[str, str], values: dict[str, str]) -> str | None:
    """Render pattern nodes from project constants and segment values.

    Returns:
        The rendered text, or None when a placeholder outside any optional group has no value.

    """
    out: str = ""
    for n in nodes:
        if n.kind == "lit":
            out += n.text
        elif n.kind == "var":
            v: str
            if n.text in CONSTANTS:
                v = constants[n.text]
            elif n.text in values:
                v = values[n.text]
            else:
                return None
            out += transform(v, n.transform) if n.transform else v
        else:
            out += render(n.children, constants, values) or ""
    return out


def as_mapping(value: object, what: str) -> dict[str, object]:
    """Narrow a parsed YAML value to a mapping with string keys; None is the empty mapping.

    Returns:
        The mapping, its keys as strings.

    Raises:
        ConfigError: If the value is neither a mapping nor None.

    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        msg: str = f"{what} must be a mapping"
        raise ConfigError(msg)
    return {str(k): v for k, v in value.items()}


def as_strings(value: object, what: str) -> list[str]:
    """Narrow a parsed YAML value to a list of strings; None is the empty list.

    Returns:
        The items, each as a string.

    Raises:
        ConfigError: If the value is neither a list nor None.

    """
    if value is None:
        return []
    if not isinstance(value, list):
        msg: str = f"{what} must be a list"
        raise ConfigError(msg)
    return [str(v) for v in value]


def as_int(value: object, default: int, what: str) -> int:
    """Narrow a parsed YAML value to an integer; None is the default.

    Returns:
        The integer.

    Raises:
        ConfigError: If the value is neither an integer nor None.

    """
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        msg: str = f"{what} must be an integer"
        raise ConfigError(msg)
    return value


@dataclass(frozen=True)
class Project:
    """One project of the config: its name constants, repository prefix and categories."""

    constants: dict[str, str]
    repo_prefix: str
    categories: dict[str, list[str]]
    types: frozenset[str]


@dataclass(frozen=True)
class Segment:
    """One segment declaration: a value-less flag, an enum, or a style, in that precedence."""

    flag: str | None
    enum: tuple[str, ...] | None
    style: str
    reject_words: frozenset[str]


@dataclass(frozen=True)
class Domain:
    """One row of the domain reference table."""

    name: str
    external: str
    internal: str
    avoid: tuple[str, ...]


def parse_project(source: Path, pid: str, spec: object) -> Project:
    """Validate one project entry of the config and index it.

    Returns:
        The project's prefix constants, repository prefix, categories and types.

    Raises:
        ConfigError: If the entry is malformed or its prefix is not a camelCase single token.

    """
    where: str = f"{source}: project '{pid}'"
    entry: dict[str, object] = as_mapping(spec, where)
    prefix: str = str(entry.get("prefix", ""))
    if not re.fullmatch(STYLES["camelCase"], prefix):
        msg: str = f"{where} needs a camelCase one-token prefix"
        raise ConfigError(msg)
    categories: dict[str, list[str]] = {
        c: as_strings(types, f"{where} category '{c}'")
        for c, types in as_mapping(entry.get("categories"), f"{where} categories").items()
    }
    return Project(
        constants={
            "project": prefix,
            "projectLower": prefix.lower(),
            "metricsNamespace": str(
                entry.get("metrics_namespace", prefix[:1].upper() + prefix[1:]),
            ),
        },
        repo_prefix=str(entry.get("repo_prefix", prefix)),
        categories=categories,
        types=frozenset(t for types in categories.values() for t in types),
    )


def parse_segment_specs(source: Path, seg_cfg: Mapping[str, object]) -> dict[str, Segment]:
    """Validate the segment declarations of the config.

    Returns:
        Segment name to its declaration.

    Raises:
        ConfigError: If a segment is malformed or has neither an enum, a flag nor a known style.

    """
    segments: dict[str, Segment] = {}
    for name, spec in seg_cfg.items():
        where: str = f"{source}: segment '{name}'"
        entry: dict[str, object] = as_mapping(spec, where)
        style: str = str(entry.get("style", ""))
        if "enum" not in entry and "flag" not in entry and style not in STYLES:
            msg: str = f"{where} needs enum, flag or a style in {sorted(STYLES)}"
            raise ConfigError(msg)
        segments[name] = Segment(
            flag=str(entry["flag"]) if "flag" in entry else None,
            enum=tuple(as_strings(entry["enum"], f"{where} enum")) if "enum" in entry else None,
            style=style,
            reject_words=frozenset(w.lower() for w in as_strings(entry.get("reject_words"), f"{where} reject_words")),
        )
    return segments


def parse_domains(source: Path, domain_cfg: object) -> tuple[list[Domain], dict[str, str]]:
    """Validate the domain reference table of the config.

    Returns:
        The domains, and each avoided term (lowercased) mapped to its domain's internal name.

    Raises:
        ConfigError: If the table is malformed, an internal name is not camelCase or an
            external name is not its kebab.

    """
    domains: list[Domain] = []
    avoid: dict[str, str] = {}
    msg: str
    if domain_cfg is None:
        return domains, avoid
    if not isinstance(domain_cfg, list):
        msg = f"{source}: domains must be a list"
        raise ConfigError(msg)
    for raw in domain_cfg:
        d: dict[str, object] = as_mapping(raw, f"{source}: a domains entry")
        internal: str = str(d.get("internal", ""))
        if not re.fullmatch(STYLES["camelCase"], internal):
            msg = f"{source}: domain internal name '{internal}' is not camelCase"
            raise ConfigError(msg)
        external: str = str(d.get("external") or "")
        if external and external != transform(internal, "kebab"):
            msg = f"{source}: domain external '{external}' is not kebab of '{internal}'"
            raise ConfigError(msg)
        terms: tuple[str, ...] = tuple(as_strings(d.get("avoid"), f"{source}: domain '{internal}' avoid"))
        domains.append(Domain(str(d.get("name") or ""), external, internal, terms))
        for term in terms:
            avoid[term.lower()] = internal
    return domains, avoid


@dataclass
class Resource:
    """One resource type from the config."""

    key: str
    description: str
    pattern: str
    nodes: list[Node]
    category: str
    min_length: int
    max_length: int
    type_words: set[str] = field(default_factory=set)


class Rules:
    """A loaded, validated naming config."""

    def __init__(self, data: object, source: Path) -> None:
        """Validate the config and index it.

        Raises:
            ConfigError: If a required key is missing or a rule is inconsistent.

        """
        self.source: Path = source
        msg: str
        if not isinstance(data, dict):
            msg = f"{source}: top level must be a mapping"
            raise ConfigError(msg)
        config: dict[str, object] = as_mapping(data, f"{source}: top level")
        for required in ("projects", "segments", "resources"):
            if required not in config:
                msg = f"{source}: missing required key '{required}'"
                raise ConfigError(msg)
        proj_cfg: dict[str, object] = as_mapping(config["projects"], f"{source}: projects")
        if not proj_cfg:
            msg = f"{source}: projects must be a non-empty mapping"
            raise ConfigError(msg)
        self.projects: dict[str, Project] = {pid: parse_project(source, pid, spec) for pid, spec in proj_cfg.items()}
        self.forbidden_substrings: list[str] = [
            s.lower() for s in as_strings(config.get("forbidden_substrings"), f"{source}: forbidden_substrings")
        ]
        self.forbidden_tokens: set[str] = {
            t.lower() for t in as_strings(config.get("forbidden_tokens"), f"{source}: forbidden_tokens")
        }
        self.permitted_suffixes: set[str] = set(
            as_strings(config.get("permitted_suffixes"), f"{source}: permitted_suffixes"),
        )
        self.type_words: set[str] = {t.lower() for t in as_strings(config.get("type_words"), f"{source}: type_words")}
        self.segments: dict[str, Segment] = parse_segment_specs(
            source,
            as_mapping(config["segments"], f"{source}: segments"),
        )
        self.domains: list[Domain]
        self.avoid: dict[str, str]
        self.domains, self.avoid = parse_domains(source, config.get("domains"))
        self.resources: dict[str, Resource] = {
            key: self.parse_resource(key, spec)
            for key, spec in as_mapping(config["resources"], f"{source}: resources").items()
        }

    def parse_resource(self, key: str, spec: object) -> Resource:
        """Validate one resource declaration against the loaded segments and suffixes.

        Returns:
            The resource.

        Raises:
            ConfigError: If the declaration is malformed, the pattern uses an undefined
                segment, or an AWS resource ends in a literal that is not a permitted suffix.

        """
        msg: str
        where: str = f"{self.source}: resource '{key}'"
        entry: dict[str, object] = as_mapping(spec, where)
        pattern: object = entry.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            msg = f"{where} needs a pattern"
            raise ConfigError(msg)
        nodes: list[Node] = parse_pattern(pattern)
        for seg, _ in placeholders(nodes):
            if seg not in self.segments:
                msg = f"{where} uses undefined segment '{seg}'"
                raise ConfigError(msg)
        category: str = str(entry.get("category", "aws"))
        tail: str = trailing_literal(nodes)
        if category == "aws" and tail and tail not in self.permitted_suffixes:
            msg = f"{where} ends in '{tail}', not a permitted suffix"
            raise ConfigError(msg)
        return Resource(
            key,
            str(entry.get("description", "")),
            pattern,
            nodes,
            category,
            as_int(entry.get("min_length"), 1, f"{where} min_length"),
            as_int(entry.get("max_length"), 0, f"{where} max_length"),
            {t.lower() for t in as_strings(entry.get("type_words"), f"{where} type_words")},
        )

    def resource(self, key: str) -> Resource:
        """Look up a resource type.

        Returns:
            The resource.

        Raises:
            ConfigError: If the type is not in the config.

        """
        if key not in self.resources:
            msg: str = f"unknown resource type '{key}'; known: {', '.join(sorted(self.resources))}"
            raise ConfigError(msg)
        return self.resources[key]

    def project(self, pid: str | None) -> Project:
        """Look up a project by id.

        Returns:
            The project's prefix constants, categories and types.

        Raises:
            NamingError: If the id is not a configured project.

        """
        if pid is None or pid not in self.projects:
            msg: str = f"--project '{pid}' is not a project; projects: {', '.join(self.projects)}"
            raise NamingError(msg)
        return self.projects[pid]

    def project_types(self, prefix: str, seg_values: dict[str, str]) -> list[str]:
        """Check `{type}` against the categories of the project a prefix belongs to.

        Returns:
            One reason when the project restricts its types and the type is not one of them.

        """
        for pid, proj in self.projects.items():
            if proj.constants["project"].lower() != prefix.lower():
                continue
            value: str | None = seg_values.get("type")
            if proj.types and value is not None and value not in proj.types:
                cats: str = "; ".join(f"{c}: {', '.join(t)}" for c, t in proj.categories.items())
                return [
                    f"type '{value}' is not a type of project '{pid}' (categories {cats})",
                ]
        return []

    # -- segments ---------------------------------------------------------------------

    def segment_regex(self, seg: str, how: str) -> str:
        """Return the regex for a segment, after its transform.

        Returns:
            A regex (no anchors).

        """
        spec: Segment = self.segments[seg]
        if spec.flag is not None:
            return re.escape(spec.flag)
        if spec.enum is not None:
            values: list[str] = [transform(v, how) if how else v for v in spec.enum]
            return "(?:" + "|".join(re.escape(v) for v in sorted(values, key=len, reverse=True)) + ")"
        if how:
            return TRANSFORM_REGEX[how]
        return STYLES[spec.style]

    def validate_segment(self, seg: str, value: str) -> None:
        """Check one supplied segment value against its style and rejected words.

        Raises:
            NamingError: If the value breaks a rule.

        """
        spec: Segment = self.segments[seg]
        flag: str = kebab_flag(seg)
        msg: str
        if spec.flag is not None:
            if value != spec.flag:
                msg = f"{flag} takes no value"
                raise NamingError(msg)
        elif spec.enum is not None:
            if value not in spec.enum:
                msg = f"{flag} '{value}' must be one of: {', '.join(spec.enum)}"
                raise NamingError(msg)
        elif not re.fullmatch(STYLES[spec.style], value):
            msg = f"{flag} '{value}' is not {spec.style} ({STYLES[spec.style]})"
            raise NamingError(msg)
        bad: list[str] = self.rejected_words(seg, value)
        if bad:
            msg = f"{flag} '{value}' contains redundant word(s) {bad}; drop them"
            raise NamingError(msg)

    def rejected_words(self, seg: str, value: str) -> list[str]:
        """List the words of a segment value that the segment declares redundant.

        Returns:
            The rejected words, in the order they appear in the value.

        """
        rejected: frozenset[str] = self.segments[seg].reject_words
        return [w for w in words(value) if w in rejected]

    # -- whole-name rules ---------------------------------------------------------------

    def global_violations(self, name: str) -> list[str]:
        """Apply the rules that hold for every name.

        The rules are the forbidden spellings, environment words and avoided domain terms.

        Returns:
            One reason per violation; empty when the name passes.

        """
        low: str = name.lower()
        reasons: list[str] = [f"contains forbidden spelling '{sub}'" for sub in self.forbidden_substrings if sub in low]
        toks: list[str] = words(name)
        for t in toks:
            if t in self.forbidden_tokens:
                reasons.append(f"contains '{t}' (no environment segment in names)")
            if t in self.avoid:
                reasons.append(
                    f"contains avoided term '{t}'; use domain '{self.avoid[t]}'",
                )
        return reasons

    # -- name ---------------------------------------------------------------------------

    def build_constants(self, res: Resource, pid: str | None) -> dict[str, str]:
        """Resolve the project constants a resource pattern needs.

        Returns:
            The project's constants, or an empty mapping when the pattern uses none.

        Raises:
            NamingError: If the pattern needs a project and none is given, or the project
                is not configured.

        """
        if uses_constants(res.nodes):
            if not pid:
                msg: str = f"'{res.key}' needs --project (one of: {', '.join(self.projects)})"
                raise NamingError(msg)
            return self.project(pid).constants
        if pid:
            self.project(pid)
        return {}

    @staticmethod
    def check_segment_set(res: Resource, values: Mapping[str, str], *, partial: bool = False) -> None:
        """Check that the supplied segments are exactly ones the pattern takes.

        With `partial`, a required segment may be absent: `check` compares only the segments
        the caller states.

        Raises:
            NamingError: If a supplied segment is not in the pattern, or a required one is missing.

        """
        msg: str
        segs: list[tuple[str, bool]] = placeholders(res.nodes)
        known: set[str] = {s for s, _ in segs}
        extra: list[str] = sorted(set(values) - known)
        if extra:
            msg = (
                f"'{res.key}' takes no {', '.join(kebab_flag(e) for e in extra)}; "
                f"it takes {', '.join(kebab_flag(s) for s, _ in segs) or 'no segments'}"
            )
            raise NamingError(msg)
        if partial:
            return
        missing: list[str] = [kebab_flag(s) for s, opt in segs if not opt and s not in values]
        if missing:
            msg = f"'{res.key}' needs {', '.join(missing)} (pattern {res.pattern})"
            raise NamingError(msg)

    def build(self, res: Resource, values: dict[str, str], pid: str | None) -> str:
        """Generate a name from segment values for one project.

        Returns:
            The name.

        Raises:
            NamingError: If the project or a value is missing, extra or invalid, or the
                result breaks a rule.

        """
        constants: dict[str, str] = self.build_constants(res, pid)
        self.check_segment_set(res, values)
        for seg, value in values.items():
            self.validate_segment(seg, value)
        name: str = render(res.nodes, constants, values) or ""
        reasons: list[str] = self.violations(res, name, pid)
        if reasons:
            msg: str = f"generated '{name}' breaks the rules: " + "; ".join(reasons)
            raise NamingError(msg)
        return name

    # -- check --------------------------------------------------------------------------

    def regex(self, res: Resource, pid: str | None = None) -> str:
        """Compile a resource pattern into an anchored regex with one group per segment.

        A project constant matches the given project's value, or any project's when no
        project is given; its group is named `c<n>_<constant>`.

        Returns:
            The regex.

        """
        counter: dict[str, int] = {"n": 0}
        projects: list[Project] = [self.projects[pid]] if pid else list(self.projects.values())

        def emit(nodes: list[Node]) -> str:
            out: str = ""
            for n in nodes:
                if n.kind == "lit":
                    out += re.escape(n.text)
                elif n.kind == "var":
                    if n.text in CONSTANTS:
                        counter["n"] += 1
                        alts: set[str] = {
                            transform(v, n.transform) if n.transform else v
                            for v in (p.constants[n.text] for p in projects)
                        }
                        out += (
                            f"(?P<c{counter['n']}_{n.text}>"
                            + "|".join(re.escape(a) for a in sorted(alts, key=len, reverse=True))
                            + ")"
                        )
                    else:
                        counter["n"] += 1
                        out += f"(?P<g{counter['n']}_{n.text}>{self.segment_regex(n.text, n.transform)})"
                else:
                    out += "(?:" + emit(n.children) + ")?"
            return out

        return "^" + emit(res.nodes) + "$"

    def pattern_violations(self, res: Resource, name: str, pid: str | None) -> list[str]:
        """Match a name against its resource pattern and check the matched segments.

        Returns:
            One reason per violation; empty when the name matches and its segments pass.

        """
        match: re.Match[str] | None = re.fullmatch(self.regex(res, pid), name)
        if not match:
            scope: str = f"project '{pid}'" if pid else "any project"
            return [f"does not match '{res.pattern}' for {res.key} ({scope})"]
        reasons: list[str] = []
        seg_values: dict[str, str] = {}
        prefix: str = ""
        for group, value in match.groupdict().items():
            if value is None:
                continue
            kind, seg = group.split("_", 1)
            if kind.startswith("c"):
                if seg in {"project", "projectLower"}:
                    prefix = value
                continue
            seg_values[seg] = value
            bad: list[str] = self.rejected_words(seg, value)
            if bad:
                reasons.append(
                    f"segment {seg} '{value}' contains redundant word(s) {bad}",
                )
        if prefix:
            reasons.extend(self.project_types(prefix, seg_values))
        return reasons

    @staticmethod
    def length_violations(res: Resource, name: str) -> list[str]:
        """Check a name's length against its resource's limits.

        Returns:
            One reason per violated limit; empty when the length is within them.

        """
        reasons: list[str] = []
        if len(name) < res.min_length:
            reasons.append(f"shorter than {res.min_length} characters")
        if res.max_length and len(name) > res.max_length:
            reasons.append(
                f"{len(name)} characters, over the {res.key} limit of {res.max_length}",
            )
        return reasons

    def segment_mismatches(
        self,
        res: Resource,
        name: str,
        pid: str | None,
        expected: Mapping[str, str],
    ) -> list[str]:
        """Compare the segments a name carries with the values the caller states for them.

        Each stated value is transformed as the pattern transforms that segment, so
        `--domain dataAccess` is compared as `data_access` under `{domain|snake}`. A name
        that does not match the pattern at all is reported by `pattern_violations`, not here.

        Returns:
            One reason per segment whose value in the name is not the stated one.

        """
        if not expected:
            return []
        match: re.Match[str] | None = re.fullmatch(self.regex(res, pid), name)
        if match is None:
            return []
        found: dict[str, str | None] = match.groupdict()
        reasons: list[str] = []
        index: int
        node: Node
        for index, node in enumerate(flatten_vars(res.nodes), start=1):
            if node.text in CONSTANTS or node.text not in expected:
                continue
            stated: str = expected[node.text]
            want: str = transform(stated, node.transform) if node.transform else stated
            got: str | None = found.get(f"g{index}_{node.text}")
            if got != want:
                carried: str = "is absent" if got is None else f"is '{got}'"
                reasons.append(
                    f"segment {node.text} {carried}, not '{want}' ({kebab_flag(node.text)} '{stated}')",
                )
        return reasons

    def violations(
        self,
        res: Resource,
        name: str,
        pid: str | None = None,
        expected: Mapping[str, str] | None = None,
    ) -> list[str]:
        """Check a name against its resource pattern and every global rule.

        `expected` holds the segment values the caller states the name was built from; each
        must be the value the name carries in that segment.

        Returns:
            One reason per violation; empty when the name passes.

        """
        if pid:
            self.project(pid)
        reasons: list[str] = self.pattern_violations(res, name, pid)
        reasons.extend(self.segment_mismatches(res, name, pid, expected or {}))
        reasons.extend(self.length_violations(res, name))
        reasons.extend(self.global_violations(name))
        reasons.extend(self.type_word_violations(res, name))
        return reasons

    def type_word_violations(self, res: Resource, name: str) -> list[str]:
        """Reject a cloud resource name containing a word for its kind of resource.

        The global `type_words` and the resource's own `type_words` are matched as whole
        tokens (camelCase, hyphen, underscore, dot or slash boundaries). The pattern's own
        leading literal (such as the `alias/` AWS requires of a KMS alias) and a permitted
        suffix at the end of the name are removed first: the pattern, not the caller, put
        them there, so they are never a violation.

        Returns:
            One reason per violating word; empty when the name passes.

        """
        if res.category != "aws":
            return []
        stem = name
        head = leading_literal(res.nodes)
        if head and stem.startswith(head):
            stem = stem[len(head) :]
        for suffix in sorted(self.permitted_suffixes, key=len, reverse=True):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        forbidden = self.type_words | res.type_words
        return [
            f"contains '{w}', a word for the kind of resource; drop it"
            for w in dict.fromkeys(words(stem))
            if w in forbidden
        ]


def find_config(explicit: str | None) -> tuple[Path, list[str]]:
    """Locate the naming config.

    Returns:
        The config path and the list of places tried.

    Raises:
        ConfigError: If no config is found.

    """
    tried: list[str] = []
    candidates: list[tuple[str, Path]] = []
    msg: str
    if explicit:
        candidates.append(("--config", Path(explicit)))
    env = os.environ.get(CONFIG_ENV, "").strip()
    if env:
        candidates.append((f"${CONFIG_ENV}", Path(env)))
    control = os.environ.get(CONTROL_REPO_ENV, "").strip()
    if control:
        candidates.append((f"${CONTROL_REPO_ENV}", Path(control) / CONFIG_FILE))
    candidates.extend(("search", parent / CONFIG_FILE) for parent in [Path.cwd(), *Path.cwd().parents])
    for how, path in candidates:
        tried.append(f"{how}: {path}")
        if path.is_file():
            return path, tried
        if how != "search":
            # An explicitly named config that is absent is an error, not a fallthrough.
            msg = f"naming config named by {how} does not exist: {path}"
            raise ConfigError(msg)
    msg = (
        f"no resource naming config found. Set ${CONFIG_ENV}, or ${CONTROL_REPO_ENV} "
        f"to a repo holding {CONFIG_FILE}. Tried:\n  " + "\n  ".join(tried)
    )
    raise ConfigError(msg)


def load_rules(explicit: str | None) -> Rules:
    """Find, read and validate the naming config.

    Returns:
        The rules.

    Raises:
        ConfigError: If the config is missing, unreadable or invalid, or PyYAML is not installed.

    """
    path, _ = find_config(explicit)
    msg: str
    if YAML_IMPORT_ERROR is not None:
        msg = "PyYAML is required: pip install pyyaml"
        raise ConfigError(msg) from YAML_IMPORT_ERROR
    try:
        data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        msg = f"{path}: cannot read: {exc}"
        raise ConfigError(msg) from exc
    return Rules(data, path)


def cmd_list(rules: Rules) -> None:
    """Print every resource type with its pattern and segments."""
    sys.stdout.write(f"# config: {rules.source}\n")
    sys.stdout.write("# projects (--project: prefix / repository prefix / categories)\n")
    for pid, proj in rules.projects.items():
        cats: str = "; ".join(f"{c}: {', '.join(t)}" for c, t in proj.categories.items())
        sys.stdout.write(
            f"{pid}: {proj.constants['project']} / {proj.repo_prefix}" + (f" / {cats}" if cats else "") + "\n",
        )
    sys.stdout.write("\n")
    width: int = max(len(k) for k in rules.resources)
    for key, res in rules.resources.items():
        flags: str = " ".join(
            (["--project"] if uses_constants(res.nodes) else [])
            + [(f"[{kebab_flag(s)}]" if opt else kebab_flag(s)) for s, opt in placeholders(res.nodes)],
        )
        sys.stdout.write(f"{key:<{width}}  {res.pattern:<55}  {flags}\n")
    if rules.domains:
        sys.stdout.write("\n# domains (external / internal / avoid)\n")
        for d in rules.domains:
            sys.stdout.write(f"{d.name}: {d.external} / {d.internal} / {', '.join(d.avoid)}\n")


def parse_segments(rules: Rules, argv: list[str]) -> dict[str, str]:
    """Parse `--segment value` pairs into segment values.

    Returns:
        Segment name to value.

    Raises:
        NamingError: If a flag is unknown or has no value.

    """
    by_flag = {kebab_flag(s): s for s in rules.segments}
    values: dict[str, str] = {}
    msg: str
    i = 0
    while i < len(argv):
        arg = argv[i]
        flag, eq, inline = arg.partition("=")
        if flag not in by_flag:
            msg = f"unknown option '{flag}'; segments: {', '.join(sorted(by_flag))}"
            raise NamingError(msg)
        spec: Segment = rules.segments[by_flag[flag]]
        if spec.flag is not None:
            if eq:
                msg = f"{flag} takes no value"
                raise NamingError(msg)
            values[by_flag[flag]] = spec.flag
            i += 1
            continue
        if eq:
            value = inline
        else:
            if i + 1 >= len(argv):
                msg = f"{flag} needs a value"
                raise NamingError(msg)
            i += 1
            value = argv[i]
        values[by_flag[flag]] = value
        i += 1
    return values


def cmd_check(rules: Rules, kind: str, name: str, pid: str | None, expected: Mapping[str, str]) -> int:
    """Check one name, and the segment values stated for it, and report the result.

    Returns:
        0 when the name passes, 1 when it breaks a rule.

    Raises:
        NamingError: If a stated segment is not one the pattern takes, or its value is invalid.

    """
    if not name:
        msg: str = "check needs a non-empty name"
        raise NamingError(msg)
    res: Resource = rules.resource(kind)
    rules.check_segment_set(res, expected, partial=True)
    seg: str
    value: str
    for seg, value in expected.items():
        rules.validate_segment(seg, value)
    reasons: list[str] = rules.violations(res, name, pid, expected)
    if reasons:
        sys.stderr.write(f"FAIL {kind} '{name}':\n")
        for r in reasons:
            sys.stderr.write(f"  - {r}\n")
        sys.stderr.write(f"  pattern: {res.pattern}\n")
        return 1
    sys.stdout.write(f"OK {kind} '{name}'\n")
    return 0


def run_command(args: argparse.Namespace, rest: list[str]) -> int:
    """Run the parsed subcommand; ConfigError and NamingError propagate to the caller.

    Returns:
        The exit code.

    """
    command: str = args.command
    rules: Rules = load_rules(args.config)
    if command == "list":
        cmd_list(rules)
    elif command == "where":
        sys.stdout.write(f"{rules.source}\n")
    elif command == "name":
        res: Resource = rules.resource(args.kind)
        sys.stdout.write(f"{rules.build(res, parse_segments(rules, rest), args.project)}\n")
    else:
        return cmd_check(rules, args.kind, args.name, args.project, parse_segments(rules, rest))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        The exit code.

    """
    parser = argparse.ArgumentParser(description="Generate and check resource names.")
    parser.add_argument(
        "--config",
        help="path to the naming config (overrides the lookup)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_name = sub.add_parser("name", help="print the name for a resource type")
    p_name.add_argument("kind", metavar="resource-type")
    p_name.add_argument("--project", help="the project the resource belongs to")
    p_check = sub.add_parser("check", help="exit 0 when the name follows the rules")
    p_check.add_argument("kind", metavar="resource-type")
    p_check.add_argument("name")
    p_check.add_argument("--project", help="accept only this project's prefix")
    sub.add_parser("list", help="print resource types and patterns")
    sub.add_parser("where", help="print the config path in use")
    args, rest = parser.parse_known_args(argv)
    if rest and args.command not in {"name", "check"}:
        parser.error(f"unrecognized arguments: {' '.join(rest)}")
    try:
        return run_command(args, rest)
    except ConfigError as exc:
        sys.stderr.write(f"naming: config error: {exc}\n")
        return 2
    except NamingError as exc:
        sys.stderr.write(f"naming: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
