"""The names a repository rename covers beyond the repository, and the sweep that updates every reference.

`polyrepo.py rename` uses this module. A rename covers four kinds of name besides the repository:
the CDK stack ids and the stack file names inside it, and the Python distribution and import
package it publishes. Every new name comes from `atw-naming` (the `Namer` the caller supplies);
nothing here composes a name by hand.

The old name of each kind is read from the repository (the `name` in `pyproject.toml`, the package
folder under `src/`, the stack modules under `cdk/stacks/`) or, for a stack, derived from the old
repository name. A sweep then rewrites every reference to an old name in the tracked text files of
the repositories it is handed:

- a hyphenated name (repository, stack id, distribution) is replaced wherever it stands alone;
- a package or module name that carries an underscore or the `skillspoke` prefix is replaced
  wherever it stands alone;
- a generic package name (`support`, `data`) is replaced only where it is an import, a dotted
  module path in a string, a `src/` path, a coverage option, a quoted token in `pyproject.toml`
  or the argument of `get_lambda_code`, and only in the repository that holds the package.

A lock file is edited only for a distribution whose normalized name changes. The matrix, the
changelogs, the beads files and every other path the caller lists in `excludes` are records, and
are never edited.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Literal, assert_never

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

type NameKind = Literal["repository", "stack", "stack-file", "distribution", "import-package"]
type Namer = Callable[[Sequence[str]], str]
type Git = Callable[[Path, Sequence[str]], tuple[int, str, str]]

PREFIX_PROJECTS: dict[str, str] = {
    "SkillSpoke": "personal-agent",
    "shared": "shared",
    "marketing": "marketing",
    "employer": "employer",
}
PACKAGE_TYPES: tuple[str, ...] = ("lib", "service")
LOCK_FILES: frozenset[str] = frozenset({"uv.lock", "poetry.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"})
PYTHON_SUFFIXES: frozenset[str] = frozenset({".py", ".pyi"})
CONFIG_SUFFIXES: frozenset[str] = frozenset({".py", ".toml", ".yml", ".yaml", ".json", ".cfg", ".ini"})
PYTHON_CONFIG_FILES: frozenset[str] = frozenset({"pyproject.toml", "setup.cfg", "tox.ini", ".coveragerc"})
SRC_FOLDER = "src"
STACK_FOLDER = "cdk/stacks"
GREP_LIST_FOUND = 0
GREP_LIST_NONE = 1
TEAM_TOKENS = 3
BODY_TOKENS = 2
FILE_DEPTH = 3
STACK_KINDS: tuple[tuple[NameKind, str], ...] = (("stack", "stack"), ("stack-file", "cdk-stack-file"))


class NameSweepError(Exception):
    """A name cannot be planned or a sweep cannot run."""


@dataclasses.dataclass(frozen=True, slots=True)
class RepoParts:
    """A repository name taken apart: `{prefix}[-team]-{domain}-{type}`."""

    project: str
    team: bool
    domain: str
    type: str


@dataclasses.dataclass(frozen=True, slots=True)
class NameChange:
    """One name that changes: its kind, the name now, and the name `atw-naming` gives."""

    kind: NameKind
    old: str
    new: str


@dataclasses.dataclass(frozen=True, slots=True)
class FileMove:
    """A tracked path that moves with `git mv`, relative to the repository."""

    old: str
    new: str


@dataclasses.dataclass(frozen=True, slots=True)
class HolderFacts:
    """What the repository that holds the names says its names are now."""

    distribution: str | None
    packages: tuple[str, ...]
    stack_modules: tuple[str, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Rule:
    """One rewrite: a pattern, its replacement, and where it applies."""

    kind: NameKind
    label: str
    needle: str
    pattern: re.Pattern[str]
    repl: str
    only_in: str | None = None
    suffixes: frozenset[str] | None = None
    basenames: frozenset[str] | None = None
    lock: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class SweepTarget:
    """One repository a sweep reads: its name after the rename, and the folder to read."""

    label: str
    root: Path


@dataclasses.dataclass(frozen=True, slots=True)
class FileEdit:
    """What a sweep did, or would do, to one file."""

    path: str
    replacements: int
    kinds: frozenset[NameKind]
    labels: frozenset[str]


def parse_repo_name(name: str) -> RepoParts | None:
    """Take a repository name apart into project, team flag, domain and type.

    Returns:
        The parts, or None when the name is not `{prefix}[-team]-{domain}-{type}` with a known prefix.

    """
    tokens = name.split("-")
    project = PREFIX_PROJECTS.get(tokens[0])
    if project is None:
        return None
    rest = tokens[1:]
    team = len(rest) == TEAM_TOKENS and rest[0] == "team"
    body = rest[1:] if team else rest
    if len(body) != BODY_TOKENS:
        return None
    return RepoParts(project, team, body[0], body[1])


def _name_args(parts: RepoParts, stack_type: str) -> list[str]:
    """Build the `atw-naming` flags that name a stack of this repository.

    Returns:
        The flags.

    """
    args = ["--project", parts.project]
    if parts.team:
        args.append("--team")
    return [*args, "--domain", parts.domain, "--type", stack_type]


def _try_name(namer: Namer, args: Sequence[str]) -> str | None:
    """Ask `atw-naming` for a name, treating its refusal as "no such name for these inputs".

    A stack type that the repository's project does not allow is refused; that is not an error here.

    Returns:
        The name, or None when `atw-naming` refuses the inputs.

    """
    try:
        return namer(args)
    except NameSweepError:
        return None


def stack_changes(old: RepoParts, new: RepoParts, types: Sequence[str], namer: Namer) -> list[NameChange]:
    """Name the stack ids and stack file modules that change between two repository names.

    Every stack type is tried, so a repository's data stack follows its service stack; the
    stacks that the renamed repository holds are the ones a sweep finds hits for.

    Returns:
        One change per stack id and per stack module whose name differs.

    """
    pairs = {(t, t) for t in types} | {(old.type, new.type)}
    out: list[NameChange] = []
    for t_old, t_new in sorted(pairs):
        for kind, resource in STACK_KINDS:
            before = _try_name(namer, ["name", resource, *_name_args(old, t_old)])
            after = _try_name(namer, ["name", resource, *_name_args(new, t_new)])
            if before is None or after is None:
                continue
            if kind == "stack-file":
                before, after = Path(before).stem, Path(after).stem
            change = NameChange(kind, before, after)
            if before != after and change not in out:
                out.append(change)
    return out


def read_facts(git: Git, root: Path) -> HolderFacts:
    """Read the repository's current distribution, source packages and stack modules.

    Returns:
        The facts.

    Raises:
        NameSweepError: when git cannot list the files or `pyproject.toml` cannot be parsed.

    """
    code, out, err = git(root, ["ls-files", "-z"])
    if code != 0:
        msg = f"git ls-files failed in {root}: {err.strip()}"
        raise NameSweepError(msg)
    files = [f.split("/") for f in out.split("\0") if f]
    shallow = [p for p in files if len(p) == FILE_DEPTH]
    packages = sorted({p[1] for p in shallow if p[0] == SRC_FOLDER and p[2] == "__init__.py"})
    stacks = sorted(
        p[2].removesuffix(".py")
        for p in shallow
        if f"{p[0]}/{p[1]}" == STACK_FOLDER and p[2].endswith(".py") and p[2] != "__init__.py"
    )
    return HolderFacts(_distribution(root), tuple(packages), tuple(stacks))


def _distribution(root: Path) -> str | None:
    """Read `project.name` from the repository's `pyproject.toml`.

    Returns:
        The name, or None when there is no `pyproject.toml` or it names no project.

    Raises:
        NameSweepError: when the file cannot be read or parsed.

    """
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    try:
        data: object = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        msg = f"cannot read {path}: {exc}"
        raise NameSweepError(msg) from exc
    project = data.get("project") if isinstance(data, dict) else None
    name = project.get("name") if isinstance(project, dict) else None
    return name if isinstance(name, str) else None


def plan_changes(
    old: str,
    new: str,
    facts: HolderFacts,
    types: Sequence[str],
    namer: Namer,
) -> tuple[list[NameChange], list[str]]:
    """Plan every name a rename of `old` to `new` changes, each named by `atw-naming`.

    With `old == new` only the Python names are planned: the repository stays and the names it
    holds are brought to what `atw-naming` gives. A repository that holds several source
    packages is reported in the notes and its packages are left alone.

    Returns:
        The changes (repository first), and notes on what was not planned and why.

    """
    changes: list[NameChange] = []
    notes: list[str] = []
    if old != new:
        changes.append(NameChange("repository", old, new))
    parts = parse_repo_name(new)
    if parts is None:
        notes.append(
            f"{new} is not {{prefix}}[-team]-{{domain}}-{{type}}, so no stack or Python name is planned for it",
        )
        return changes, notes
    wanted = namer(["name", "python-distribution", "--repository", new])
    if facts.distribution is not None and facts.distribution != wanted:
        changes.append(NameChange("distribution", facts.distribution, wanted))
    if parts.type in PACKAGE_TYPES and len(facts.packages) == 1:
        package = namer(["name", "python-package", "--domain", parts.domain])
        if facts.packages[0] != package:
            changes.append(NameChange("import-package", facts.packages[0], package))
    elif parts.type in PACKAGE_TYPES and facts.packages:
        notes.append(f"{new} holds several source packages ({', '.join(facts.packages)}); none is renamed")
    before = parse_repo_name(old)
    if before is not None and before != parts:
        changes.extend(c for c in stack_changes(before, parts, types, namer) if _held(c, facts))
    return changes, notes


def _held(change: NameChange, facts: HolderFacts) -> bool:
    """Tell whether a stack change can apply: a stack file only when the repository has that module.

    Returns:
        True for a stack id (its hits decide) and for a stack module the repository holds.

    """
    return change.kind != "stack-file" or change.old in facts.stack_modules


def planned_moves(changes: Sequence[NameChange], facts: HolderFacts) -> list[FileMove]:
    """List the tracked paths the changes move: the package folder and the stack modules.

    Returns:
        One move per package folder and per held stack module that changes name.

    """
    moves: list[FileMove] = []
    for c in changes:
        if c.kind == "import-package":
            moves.append(FileMove(f"{SRC_FOLDER}/{c.old}", f"{SRC_FOLDER}/{c.new}"))
        elif c.kind == "stack-file" and c.old in facts.stack_modules:
            moves.append(FileMove(f"{STACK_FOLDER}/{c.old}.py", f"{STACK_FOLDER}/{c.new}.py"))
    return moves


def apply_moves(git: Git, root: Path, moves: Sequence[FileMove]) -> None:
    """Move each path with `git mv`.

    Raises:
        NameSweepError: when git refuses a move.

    """
    for m in moves:
        code, _, err = git(root, ["mv", m.old, m.new])
        if code != 0:
            msg = f"git mv {m.old} {m.new} failed in {root}: {err.strip()}"
            raise NameSweepError(msg)


def normalize(distribution: str) -> str:
    """Normalize a distribution name the way PEP 503 does (what a lock file stores).

    Returns:
        The lowercase name with each run of `-`, `_` and `.` as one `-`.

    """
    return re.sub(r"[-_.]+", "-", distribution).lower()


def change_label(change: NameChange) -> str:
    """Say a change in the form a rule and an edit carry.

    Returns:
        `old -> new`.

    """
    return f"{change.old} -> {change.new}"


def _hyphen_rule(change: NameChange, only_in: str | None = None, *, lock: bool = False) -> Rule:
    """Build the rule for a hyphenated name that stands alone (not part of a longer name).

    Returns:
        The rule.

    """
    pattern = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(change.old)}(?![A-Za-z0-9_]|-[A-Za-z0-9])")
    return Rule(change.kind, change_label(change), change.old, pattern, change.new, only_in, lock=lock)


def _snake_rule(change: NameChange, only_in: str | None = None) -> Rule:
    """Build the rule for a snake_case name that stands alone.

    Returns:
        The rule.

    """
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(change.old)}(?![A-Za-z0-9_])")
    return Rule(change.kind, change_label(change), change.old, pattern, change.new, only_in)


def _is_generic(package: str) -> bool:
    """Tell whether a package name is a common word that real code and prose also use.

    Returns:
        False when the name carries an underscore or the `skillspoke` prefix.

    """
    return "_" not in package and not package.startswith("skillspoke")


def _package_rules(change: NameChange, holder: str) -> list[Rule]:
    """Build the rules for an import package: plain for a distinctive name, contextual for a generic one.

    Returns:
        The rules.

    """
    if not _is_generic(change.old):
        return [_snake_rule(change)]
    old, new = re.escape(change.old), change.new
    label = change_label(change)
    kind = change.kind
    return [
        Rule(
            kind, label, change.old,
            re.compile(rf"(?m)^([ \t]*(?:from|import)[ \t]+){old}(?![A-Za-z0-9_])"),
            rf"\g<1>{new}", holder, PYTHON_SUFFIXES,
        ),
        Rule(
            kind, label, change.old,
            re.compile(rf"([\"']){old}\.(?=[A-Za-z_])"),
            rf"\g<1>{new}.", holder, CONFIG_SUFFIXES,
        ),
        Rule(
            kind, label, change.old,
            re.compile(rf"(?<![A-Za-z0-9_-])(src/){old}(?![A-Za-z0-9_-])"),
            rf"\g<1>{new}", holder,
        ),
        Rule(
            kind, label, change.old,
            re.compile(rf"(--cov[= ]){old}(?![A-Za-z0-9_])"),
            rf"\g<1>{new}", holder,
        ),
        Rule(
            kind, label, change.old,
            re.compile(rf"([\"']){old}\1"),
            rf"\g<1>{new}\g<1>", holder, None, PYTHON_CONFIG_FILES,
        ),
        Rule(
            kind, label, change.old,
            re.compile(rf"(get_lambda_code\(\s*)([\"']){old}\2"),
            rf"\g<1>\g<2>{new}\g<2>", holder, PYTHON_SUFFIXES,
        ),
    ]  # fmt: skip


def build_rules(changes: Sequence[NameChange], holder: str) -> list[Rule]:
    """Build every rewrite the changes call for.

    `holder` is the repository's name after the rename; the rules that must not touch any
    other repository carry it.

    Returns:
        The rules.

    """
    rules: list[Rule] = []
    for c in changes:
        match c.kind:
            case "repository" | "stack":
                rules.append(_hyphen_rule(c))
            case "distribution":
                rules.append(_hyphen_rule(c))
                before, after = normalize(c.old), normalize(c.new)
                if before != after:
                    rules.append(_hyphen_rule(NameChange(c.kind, before, after), lock=True))
            case "stack-file":
                rules.append(_snake_rule(c, holder))
            case "import-package":
                rules.extend(_package_rules(c, holder))
            case _:
                assert_never(c.kind)
    return rules


def _applicable(rules: Sequence[Rule], rel: str, excludes: Sequence[str]) -> list[Rule]:
    """Pick the rules that may edit one file.

    Returns:
        The rules whose file filters the path passes.

    """
    base = rel.rsplit("/", 1)[-1]
    suffix = Path(rel).suffix
    excluded = any(fnmatch.fnmatchcase(rel, g) for g in excludes)
    out: list[Rule] = []
    for r in rules:
        allowed = base == "uv.lock" if r.lock else base not in LOCK_FILES and not excluded
        if allowed and (r.suffixes is None or suffix in r.suffixes) and (r.basenames is None or base in r.basenames):
            out.append(r)
    return out


def _read_text(path: Path) -> str | None:
    """Read a file as UTF-8 without translating line endings.

    Returns:
        The text, or None when the file cannot be read or is not UTF-8.

    """
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return None
    except OSError:
        return None


def _edit_file(root: Path, rel: str, rules: Sequence[Rule], excludes: Sequence[str], *, write: bool) -> FileEdit | None:
    """Apply the rules that suit one file, writing it when asked.

    Returns:
        What changed, or None when the file is skipped (a link, not UTF-8) or nothing matched.

    """
    path = root / rel
    chosen = _applicable(rules, rel, excludes)
    if not chosen or path.is_symlink():
        return None
    text = _read_text(path)
    if text is None:
        return None
    total = 0
    kinds: set[NameKind] = set()
    labels: set[str] = set()
    for r in chosen:
        text, n = r.pattern.subn(r.repl, text)
        if n:
            total += n
            kinds.add(r.kind)
            labels.add(r.label)
    if not total:
        return None
    if write:
        path.write_bytes(text.encode("utf-8"))
    return FileEdit(rel, total, frozenset(kinds), frozenset(labels))


def sweep_repo(
    git: Git,
    target: SweepTarget,
    rules: Sequence[Rule],
    excludes: Sequence[str],
    *,
    write: bool,
) -> list[FileEdit]:
    """Find, and with `write` make, every edit the rules call for in one repository.

    Only tracked text files are read: a fixed-string `git grep` narrows them to the files that
    hold an old name first.

    Returns:
        One edit per file that changes, in path order.

    Raises:
        NameSweepError: when `git grep` fails.

    """
    root = target.root
    live = [r for r in rules if r.only_in in {None, target.label}]
    if not live:
        return []
    args = ["grep", "--null", "-l", "-I", "-F"]
    for needle in sorted({r.needle for r in live}):
        args += ["-e", needle]
    code, out, err = git(root, args)
    if code == GREP_LIST_NONE:
        return []
    if code != GREP_LIST_FOUND:
        msg = f"git grep failed in {root}: {err.strip()}"
        raise NameSweepError(msg)
    edits = (_edit_file(root, rel, live, excludes, write=write) for rel in sorted(p for p in out.split("\0") if p))
    return [e for e in edits if e is not None]
