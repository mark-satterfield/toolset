#!/usr/bin/env python3
"""Generate and check resource names from a project's resource naming config.

The rules live in the project, not here: a YAML file (`.resource-naming.yaml`) names the
projects and their name prefixes, the segment styles, the domain reference table and one
pattern per resource type. This script only applies them, deterministically.

Usage:
  naming.py name <resource-type> --project P [--team] [--domain X] [--<segment> VALUE ...]
  naming.py check <resource-type> <name> [--project P]
  naming.py list
  naming.py where

The config is found, in order: `--config PATH`; `$RESOURCE_NAMING_CONFIG`;
`$ATW_CONTROL_REPO/.resource-naming.yaml`; the first `.resource-naming.yaml` in the working
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

CONFIG_ENV = "RESOURCE_NAMING_CONFIG"
CONTROL_REPO_ENV = "ATW_CONTROL_REPO"
CONFIG_FILE = ".resource-naming.yaml"

#: Regex for a value of each segment style.
STYLES: dict[str, str] = {
    "camelCase": r"[a-z][a-zA-Z0-9]*",
    "PascalCase": r"[A-Z][a-zA-Z0-9]*",
    "lowercase": r"[a-z0-9]+",
    "kebab": r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*",
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
        out.extend(
            w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+", part)
        )
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
    raise ConfigError(f"unknown transform '{how}'")


@dataclass
class Node:
    """One piece of a parsed pattern: literal text, a placeholder, or an optional group."""

    kind: str  # "lit" | "var" | "opt"
    text: str = ""
    transform: str = ""
    children: list[Node] = field(default_factory=list)


def parse_pattern(pattern: str) -> list[Node]:
    """Parse a pattern into nodes.

    Returns:
        The top-level nodes.

    Raises:
        ConfigError: If brackets or braces are unbalanced.
    """
    pos = 0

    def parse(until: str | None) -> list[Node]:
        nonlocal pos
        nodes: list[Node] = []
        buf = ""
        while pos < len(pattern):
            ch = pattern[pos]
            if until and ch == until:
                pos += 1
                if buf:
                    nodes.append(Node("lit", buf))
                return nodes
            if ch == "{":
                end = pattern.find("}", pos)
                if end < 0:
                    raise ConfigError(f"unclosed '{{' in pattern {pattern!r}")
                if buf:
                    nodes.append(Node("lit", buf))
                    buf = ""
                name, _, how = pattern[pos + 1 : end].partition("|")
                nodes.append(Node("var", name.strip(), how.strip()))
                pos = end + 1
            elif ch == "[":
                if buf:
                    nodes.append(Node("lit", buf))
                    buf = ""
                pos += 1
                nodes.append(Node("opt", children=parse("]")))
            elif ch in "]}":
                raise ConfigError(f"unbalanced '{ch}' in pattern {pattern!r}")
            else:
                buf += ch
                pos += 1
        if until:
            raise ConfigError(f"unclosed '[' in pattern {pattern!r}")
        if buf:
            nodes.append(Node("lit", buf))
        return nodes

    return parse(None)


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


def uses_constants(nodes: list[Node]) -> bool:
    """Tell whether a pattern uses a project constant anywhere.

    Returns:
        True when `{project}`, `{projectLower}` or `{metricsNamespace}` appears.
    """
    return any(
        (n.kind == "var" and n.text in CONSTANTS)
        or (n.kind == "opt" and uses_constants(n.children))
        for n in nodes
    )


def trailing_literal(nodes: list[Node]) -> str:
    """Return the literal text after the pattern's last placeholder or group.

    Returns:
        The trailing literal, or "" when the pattern ends with a placeholder.
    """
    return nodes[-1].text if nodes and nodes[-1].kind == "lit" else ""


def kebab_flag(segment: str) -> str:
    """Return the CLI flag for a segment name (`resourceType` -> `--resource-type`).

    Returns:
        The flag.
    """
    return "--" + "-".join(words(segment))


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

    def __init__(self, data: dict, source: Path) -> None:
        """Validate the config and index it.

        Raises:
            ConfigError: If a required key is missing or a rule is inconsistent.
        """
        self.source = source
        if not isinstance(data, dict):
            raise ConfigError(f"{source}: top level must be a mapping")
        try:
            proj_cfg = data["projects"]
            seg_cfg = data["segments"]
            res_cfg = data["resources"]
        except (KeyError, TypeError) as exc:
            raise ConfigError(f"{source}: missing required key {exc}") from exc
        if not isinstance(proj_cfg, dict) or not proj_cfg:
            raise ConfigError(f"{source}: projects must be a non-empty mapping")
        self.projects: dict[str, dict] = {}
        for pid, spec in proj_cfg.items():
            spec = spec or {}
            prefix = str(spec.get("prefix", ""))
            if not re.fullmatch(STYLES["camelCase"], prefix):
                raise ConfigError(
                    f"{source}: project '{pid}' needs a camelCase one-token prefix"
                )
            categories = {
                str(c): [str(t) for t in types]
                for c, types in (spec.get("categories") or {}).items()
            }
            self.projects[str(pid)] = {
                "constants": {
                    "project": prefix,
                    "projectLower": prefix.lower(),
                    "metricsNamespace": str(
                        spec.get("metrics_namespace", prefix[:1].upper() + prefix[1:])
                    ),
                },
                "repo_prefix": str(spec.get("repo_prefix", prefix)),
                "categories": categories,
                "types": {t for types in categories.values() for t in types},
            }
        self.forbidden_substrings = [
            s.lower() for s in data.get("forbidden_substrings", [])
        ]
        self.forbidden_tokens = {t.lower() for t in data.get("forbidden_tokens", [])}
        self.permitted_suffixes = set(data.get("permitted_suffixes", []))
        self.type_words = {t.lower() for t in data.get("type_words", [])}
        self.segments: dict[str, dict] = {}
        for name, spec in seg_cfg.items():
            spec = spec or {}
            if (
                "enum" not in spec
                and "flag" not in spec
                and spec.get("style") not in STYLES
            ):
                raise ConfigError(
                    f"{source}: segment '{name}' needs enum, flag or a style in {sorted(STYLES)}"
                )
            self.segments[name] = spec
        self.domains: list[dict] = []
        self.avoid: dict[str, str] = {}
        for d in data.get("domains", []):
            internal = d["internal"]
            if not re.fullmatch(STYLES["camelCase"], internal):
                raise ConfigError(
                    f"{source}: domain internal name '{internal}' is not camelCase"
                )
            if d.get("external") and d["external"] != transform(internal, "kebab"):
                raise ConfigError(
                    f"{source}: domain external '{d['external']}' is not kebab of '{internal}'"
                )
            self.domains.append(d)
            for term in d.get("avoid", []):
                self.avoid[term.lower()] = internal
        self.resources: dict[str, Resource] = {}
        for key, spec in res_cfg.items():
            nodes = parse_pattern(spec["pattern"])
            for seg, _ in placeholders(nodes):
                if seg not in self.segments:
                    raise ConfigError(
                        f"{source}: resource '{key}' uses undefined segment '{seg}'"
                    )
            category = spec.get("category", "aws")
            tail = trailing_literal(nodes)
            if category == "aws" and tail and tail not in self.permitted_suffixes:
                raise ConfigError(
                    f"{source}: resource '{key}' ends in '{tail}', not a permitted suffix"
                )
            self.resources[key] = Resource(
                key,
                spec.get("description", ""),
                spec["pattern"],
                nodes,
                category,
                int(spec.get("min_length", 1)),
                int(spec.get("max_length", 0)),
                {t.lower() for t in spec.get("type_words", [])},
            )

    def resource(self, key: str) -> Resource:
        """Look up a resource type.

        Returns:
            The resource.

        Raises:
            ConfigError: If the type is not in the config.
        """
        if key not in self.resources:
            raise ConfigError(
                f"unknown resource type '{key}'; known: {', '.join(sorted(self.resources))}"
            )
        return self.resources[key]

    def project(self, pid: str | None) -> dict:
        """Look up a project by id.

        Returns:
            The project's prefix constants, categories and types.

        Raises:
            NamingError: If the id is not a configured project.
        """
        if pid not in self.projects:
            raise NamingError(
                f"--project '{pid}' is not a project; projects: {', '.join(self.projects)}"
            )
        return self.projects[pid]

    def project_types(self, prefix: str, seg_values: dict[str, str]) -> list[str]:
        """Check `{type}` against the categories of the project a prefix belongs to.

        Returns:
            One reason when the project restricts its types and the type is not one of them.
        """
        for pid, proj in self.projects.items():
            if proj["constants"]["project"].lower() != prefix.lower():
                continue
            value = seg_values.get("type")
            if proj["types"] and value is not None and value not in proj["types"]:
                cats = "; ".join(
                    f"{c}: {', '.join(t)}" for c, t in proj["categories"].items()
                )
                return [
                    f"type '{value}' is not a type of project '{pid}' (categories {cats})"
                ]
        return []

    # -- segments ---------------------------------------------------------------------

    def segment_regex(self, seg: str, how: str) -> str:
        """Return the regex for a segment, after its transform.

        Returns:
            A regex (no anchors).
        """
        spec = self.segments[seg]
        if "flag" in spec:
            return re.escape(str(spec["flag"]))
        if "enum" in spec:
            values = [transform(v, how) if how else v for v in spec["enum"]]
            return (
                "(?:"
                + "|".join(re.escape(v) for v in sorted(values, key=len, reverse=True))
                + ")"
            )
        if how:
            return TRANSFORM_REGEX[how]
        return STYLES[spec["style"]]

    def validate_segment(self, seg: str, value: str) -> None:
        """Check one supplied segment value against its style and rejected words.

        Raises:
            NamingError: If the value breaks a rule.
        """
        spec = self.segments[seg]
        flag = kebab_flag(seg)
        if "flag" in spec:
            if value != str(spec["flag"]):
                raise NamingError(f"{flag} takes no value")
        elif "enum" in spec:
            if value not in spec["enum"]:
                raise NamingError(
                    f"{flag} '{value}' must be one of: {', '.join(spec['enum'])}"
                )
        elif not re.fullmatch(STYLES[spec["style"]], value):
            raise NamingError(
                f"{flag} '{value}' is not {spec['style']} (one token, {STYLES[spec['style']]})"
            )
        rejected = {t.lower() for t in spec.get("reject_words", [])}
        bad = [w for w in words(value) if w in rejected]
        if bad:
            raise NamingError(
                f"{flag} '{value}' contains redundant word(s) {bad}; drop them"
            )

    # -- whole-name rules ---------------------------------------------------------------

    def global_violations(self, name: str) -> list[str]:
        """Apply the rules that hold for every name: forbidden spellings, environment
        words and avoided domain terms.

        Returns:
            One reason per violation; empty when the name passes.
        """
        reasons: list[str] = []
        low = name.lower()
        for sub in self.forbidden_substrings:
            if sub in low:
                reasons.append(f"contains forbidden spelling '{sub}'")
        toks = words(name)
        for t in toks:
            if t in self.forbidden_tokens:
                reasons.append(f"contains '{t}' (no environment segment in names)")
            if t in self.avoid:
                reasons.append(
                    f"contains avoided term '{t}'; use domain '{self.avoid[t]}'"
                )
        return reasons

    # -- name ---------------------------------------------------------------------------

    def build(self, res: Resource, values: dict[str, str], pid: str | None) -> str:
        """Generate a name from segment values for one project.

        Returns:
            The name.

        Raises:
            NamingError: If the project or a value is missing, extra or invalid, or the
                result breaks a rule.
        """
        constants: dict[str, str] = {}
        if uses_constants(res.nodes):
            if not pid:
                raise NamingError(
                    f"'{res.key}' needs --project (one of: {', '.join(self.projects)})"
                )
            constants = self.project(pid)["constants"]
        elif pid:
            self.project(pid)
        segs = placeholders(res.nodes)
        known = {s for s, _ in segs}
        extra = sorted(set(values) - known)
        if extra:
            raise NamingError(
                f"'{res.key}' takes no {', '.join(kebab_flag(e) for e in extra)}; "
                f"it takes {', '.join(kebab_flag(s) for s, _ in segs) or 'no segments'}"
            )
        missing = [kebab_flag(s) for s, opt in segs if not opt and s not in values]
        if missing:
            raise NamingError(
                f"'{res.key}' needs {', '.join(missing)} (pattern {res.pattern})"
            )
        for seg, value in values.items():
            self.validate_segment(seg, value)

        def render(nodes: list[Node]) -> str | None:
            out = ""
            for n in nodes:
                if n.kind == "lit":
                    out += n.text
                elif n.kind == "var":
                    if n.text in CONSTANTS:
                        v = constants[n.text]
                    elif n.text in values:
                        v = values[n.text]
                    else:
                        return None
                    out += transform(v, n.transform) if n.transform else v
                else:
                    out += render(n.children) or ""
            return out

        name = render(res.nodes) or ""
        reasons = self.violations(res, name, pid)
        if reasons:
            raise NamingError(
                f"generated '{name}' breaks the rules: " + "; ".join(reasons)
            )
        return name

    # -- check --------------------------------------------------------------------------

    def regex(self, res: Resource, pid: str | None = None) -> str:
        """Compile a resource pattern into an anchored regex with one group per segment.

        A project constant matches the given project's value, or any project's when no
        project is given; its group is named `c<n>_<constant>`.

        Returns:
            The regex.
        """
        counter = {"n": 0}
        projects = [self.projects[pid]] if pid else list(self.projects.values())

        def emit(nodes: list[Node]) -> str:
            out = ""
            for n in nodes:
                if n.kind == "lit":
                    out += re.escape(n.text)
                elif n.kind == "var":
                    if n.text in CONSTANTS:
                        counter["n"] += 1
                        alts = {
                            transform(v, n.transform) if n.transform else v
                            for v in (p["constants"][n.text] for p in projects)
                        }
                        out += (
                            f"(?P<c{counter['n']}_{n.text}>"
                            + "|".join(
                                re.escape(a)
                                for a in sorted(alts, key=len, reverse=True)
                            )
                            + ")"
                        )
                    else:
                        counter["n"] += 1
                        out += f"(?P<g{counter['n']}_{n.text}>{self.segment_regex(n.text, n.transform)})"
                else:
                    out += "(?:" + emit(n.children) + ")?"
            return out

        return "^" + emit(res.nodes) + "$"

    def violations(self, res: Resource, name: str, pid: str | None = None) -> list[str]:
        """Check a name against its resource pattern and every global rule.

        Returns:
            One reason per violation; empty when the name passes.
        """
        reasons: list[str] = []
        if pid:
            self.project(pid)
        match = re.fullmatch(self.regex(res, pid), name)
        if not match:
            scope = f"project '{pid}'" if pid else "any project"
            reasons.append(f"does not match '{res.pattern}' for {res.key} ({scope})")
        else:
            seg_values: dict[str, str] = {}
            prefix = ""
            for group, value in match.groupdict().items():
                if value is None:
                    continue
                kind, seg = group.split("_", 1)
                if kind.startswith("c"):
                    if seg in ("project", "projectLower"):
                        prefix = value
                    continue
                seg_values[seg] = value
                rejected = {
                    t.lower() for t in self.segments[seg].get("reject_words", [])
                }
                bad = [w for w in words(value) if w in rejected]
                if bad:
                    reasons.append(
                        f"segment {seg} '{value}' contains redundant word(s) {bad}"
                    )
            if prefix:
                reasons.extend(self.project_types(prefix, seg_values))
        if len(name) < res.min_length:
            reasons.append(f"shorter than {res.min_length} characters")
        if res.max_length and len(name) > res.max_length:
            reasons.append(
                f"{len(name)} characters, over the {res.key} limit of {res.max_length}"
            )
        reasons.extend(self.global_violations(name))
        reasons.extend(self.type_word_violations(res, name))
        return reasons

    def type_word_violations(self, res: Resource, name: str) -> list[str]:
        """Reject a cloud resource name containing a word for its kind of resource.

        The global `type_words` and the resource's own `type_words` are matched as whole
        tokens (camelCase, hyphen, underscore, dot or slash boundaries); a permitted suffix
        at the end of the name is removed first, so it is never a violation.

        Returns:
            One reason per violating word; empty when the name passes.
        """
        if res.category != "aws":
            return []
        stem = name
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
    if explicit:
        candidates.append(("--config", Path(explicit)))
    env = os.environ.get(CONFIG_ENV, "").strip()
    if env:
        candidates.append((f"${CONFIG_ENV}", Path(env)))
    control = os.environ.get(CONTROL_REPO_ENV, "").strip()
    if control:
        candidates.append((f"${CONTROL_REPO_ENV}", Path(control) / CONFIG_FILE))
    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidates.append(("search", parent / CONFIG_FILE))
    for how, path in candidates:
        tried.append(f"{how}: {path}")
        if path.is_file():
            return path, tried
        if how != "search":
            # An explicitly named config that is absent is an error, not a fallthrough.
            raise ConfigError(f"naming config named by {how} does not exist: {path}")
    raise ConfigError(
        "no resource naming config found. Set $RESOURCE_NAMING_CONFIG, or $ATW_CONTROL_REPO "
        f"to a repo holding {CONFIG_FILE}. Tried:\n  " + "\n  ".join(tried)
    )


def load_rules(explicit: str | None) -> Rules:
    """Find, read and validate the naming config.

    Returns:
        The rules.

    Raises:
        ConfigError: If the config is missing, unreadable or invalid.
    """
    path, _ = find_config(explicit)
    try:
        import yaml
    except ImportError as exc:
        raise ConfigError("PyYAML is required: pip install pyyaml") from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"{path}: cannot read: {exc}") from exc
    return Rules(data, path)


def cmd_list(rules: Rules) -> None:
    """Print every resource type with its pattern and segments."""
    print(f"# config: {rules.source}")
    print("# projects (--project: prefix / repository prefix / categories)")
    for pid, proj in rules.projects.items():
        cats = "; ".join(f"{c}: {', '.join(t)}" for c, t in proj["categories"].items())
        print(
            f"{pid}: {proj['constants']['project']} / {proj['repo_prefix']}"
            + (f" / {cats}" if cats else "")
        )
    print()
    width = max(len(k) for k in rules.resources)
    for key, res in rules.resources.items():
        flags = " ".join(
            (["--project"] if uses_constants(res.nodes) else [])
            + [
                (f"[{kebab_flag(s)}]" if opt else kebab_flag(s))
                for s, opt in placeholders(res.nodes)
            ]
        )
        print(f"{key:<{width}}  {res.pattern:<55}  {flags}")
    if rules.domains:
        print("\n# domains (external / internal / avoid)")
        for d in rules.domains:
            print(
                f"{d.get('name', '')}: {d.get('external', '')} / {d['internal']} / {', '.join(d.get('avoid', []))}"
            )


def parse_segments(rules: Rules, argv: list[str]) -> dict[str, str]:
    """Parse `--segment value` pairs into segment values.

    Returns:
        Segment name to value.

    Raises:
        NamingError: If a flag is unknown or has no value.
    """
    by_flag = {kebab_flag(s): s for s in rules.segments}
    values: dict[str, str] = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        flag, eq, inline = arg.partition("=")
        if flag not in by_flag:
            raise NamingError(
                f"unknown option '{flag}'; segments: {', '.join(sorted(by_flag))}"
            )
        spec = rules.segments[by_flag[flag]]
        if "flag" in spec:
            if eq:
                raise NamingError(f"{flag} takes no value")
            values[by_flag[flag]] = str(spec["flag"])
            i += 1
            continue
        if eq:
            value = inline
        else:
            if i + 1 >= len(argv):
                raise NamingError(f"{flag} needs a value")
            i += 1
            value = argv[i]
        values[by_flag[flag]] = value
        i += 1
    return values


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(description="Generate and check resource names.")
    parser.add_argument(
        "--config", help="path to the naming config (overrides the lookup)"
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
    if rest and args.command != "name":
        parser.error(f"unrecognized arguments: {' '.join(rest)}")
    try:
        rules = load_rules(args.config)
        if args.command == "list":
            cmd_list(rules)
        elif args.command == "where":
            print(rules.source)
        elif args.command == "name":
            res = rules.resource(args.kind)
            print(rules.build(res, parse_segments(rules, rest), args.project))
        else:
            res = rules.resource(args.kind)
            reasons = rules.violations(res, args.name, args.project)
            if reasons:
                print(f"FAIL {args.kind} '{args.name}':", file=sys.stderr)
                for r in reasons:
                    print(f"  - {r}", file=sys.stderr)
                print(f"  pattern: {res.pattern}", file=sys.stderr)
                return 1
            print(f"OK {args.kind} '{args.name}'")
    except ConfigError as exc:
        print(f"naming: config error: {exc}", file=sys.stderr)
        return 2
    except NamingError as exc:
        print(f"naming: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
