"""The names a repository rename covers beyond the repository, and the sweep that updates every reference.

`polyrepo.py rename` uses this module. A rename covers four kinds of name besides the repository:
the CDK stack ids and the stack file names inside it, and the Python distribution and import
package it publishes. Every new name comes from `atw-naming` (the `Namer` the caller supplies);
nothing here composes a name by hand.

The Python names follow the "Python names" section of the resource naming standard. The source
root is `src`. The source package is `src/{app}/{domain}` (and `src/{app}/{team}/{domain}` for a
team repository), imported as `{app}.{domain}`; the app folder holds no `__init__.py`. The
distribution is the hyphenated lower case name with the type. The tool gives all three from the
repository name: `name python-package`, `name python-package-path` and `name python-distribution`,
each with `--repository`.

The old name of each kind is read from the repository (the `name` in `pyproject.toml`, the package
folders under `src/`, the stack modules under `cdk/stacks/`) or, for a stack, derived from the old
repository name. A sweep then rewrites every reference to an old name in the tracked text files of
the repositories it is handed:

- a hyphenated name (repository, stack id) is replaced wherever it stands alone;
- a distribution is replaced where it is a dependency line (`pyproject.toml`, `setup.cfg`, a
  requirements file), written in any case or separator spelling, never in a URL or in prose;
- an import package is replaced as a dotted name where it stands alone, and a `src/` path is
  replaced by the new folder path;
- a generic package name (`support`, `data`) is replaced only where it is an import, a dotted
  module path in a string, a `src/` path, a coverage option, a quoted token in `pyproject.toml`
  or the argument of `get_lambda_code`, and only in the repository that holds the package.

A lock file is edited only for the distribution of the repository that holds it. The matrix, the
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
type Checker = Callable[[Sequence[str]], tuple[bool, str]]

PREFIX_PROJECTS: dict[str, str] = {
    "SkillSpoke": "personal-agent",
    "shared": "shared",
    "marketing": "marketing",
    "employer": "employer",
}
APP_FOLDERS: frozenset[str] = frozenset(p.lower() for p in PREFIX_PROJECTS)
TEAM_FOLDER = "team"
LOCK_FILES: frozenset[str] = frozenset({"uv.lock", "poetry.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"})
PYTHON_SUFFIXES: frozenset[str] = frozenset({".py", ".pyi"})
CONFIG_SUFFIXES: frozenset[str] = frozenset({".py", ".toml", ".yml", ".yaml", ".json", ".cfg", ".ini"})
DEPENDENCY_SUFFIXES: frozenset[str] = frozenset({".toml", ".txt", ".cfg"})
PYTHON_CONFIG_FILES: frozenset[str] = frozenset({"pyproject.toml", "setup.cfg", "tox.ini", ".coveragerc"})
PYPROJECT = "pyproject.toml"
SRC_FOLDER = "src"
TESTS_FOLDER = "tests"
STACK_FOLDER = "cdk/stacks"
GREP_LIST_FOUND = 0
GREP_LIST_NONE = 1
TEAM_TOKENS = 3
BODY_TOKENS = 2
STACK_DEPTH = 3
SOURCE_TYPES: tuple[str, ...] = ("lib", "service")
STACK_KINDS: tuple[tuple[NameKind, str], ...] = (("stack", "stack"), ("stack-file", "cdk-stack-file"))
MYPY_SECTION = re.compile(r"(?m)^\[tool\.mypy\][ \t]*\r?\n")
MYPY_PATH_SRC = '"src"'
MYPY_PATH_SRC_CDK = '["src", "cdk"]'
NAMESPACES_OFF = re.compile(r"(?m)^(namespaces[ \t]*=[ \t]*)false\b")
HATCH_WHEEL = "[tool.hatch.build.targets.wheel]"
HATCH_PACKAGES = re.compile(r'(?m)^packages[ \t]*=[ \t]*\["(src/[^"/]+/[^"]+)"\][ \t]*$')


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
    """A tracked path that moves with `git mv`, relative to the repository; an empty `new` removes it."""

    old: str
    new: str


@dataclasses.dataclass(frozen=True, slots=True)
class HolderFacts:
    """What the repository that holds the names says its names are now."""

    distribution: str | None
    packages: tuple[str, ...]
    stack_modules: tuple[str, ...]
    has_src: bool
    has_tests: bool
    namespace_inits: tuple[str, ...]


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
    """One folder a sweep reads: its label, the folder, and the paths inside it the sweep is limited to."""

    label: str
    root: Path
    paths: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class FileEdit:
    """What a sweep did, or would do, to one file."""

    path: str
    replacements: int
    kinds: frozenset[NameKind]
    labels: frozenset[str]
    lines: tuple[int, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class PythonProblem:
    """One way a repository's Python names differ from what `atw-naming` gives."""

    check: str
    detail: str


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


def _source_root(dirs: Sequence[str]) -> tuple[str, ...]:
    """Find the package folder a source file sits in: the app (and team) folders, then one more.

    The app folder (`shared`, `skillspoke`, `employer`, `marketing`) and, under it, the `team`
    folder are namespace folders. A source package is the first folder below them; in the old
    layout, which has no app folder, it is the first folder below `src`.

    Returns:
        The folders from `src`'s children down to the package folder, or () for a file that
        sits directly in a namespace folder.

    """
    depth = 0
    if dirs and dirs[0] in APP_FOLDERS:
        depth = 2 if len(dirs) > 1 and dirs[1] == TEAM_FOLDER else 1
    return tuple(dirs[: depth + 1]) if len(dirs) > depth else ()


def stack_module(parts: RepoParts, namer: Namer) -> str:
    """Name the module file of the repository's own stack under `cdk/stacks`, without `.py`.

    Returns:
        The module name `atw-naming` gives (`cdk-stack-file`).

    """
    return Path(namer(["name", "cdk-stack-file", *_name_args(parts, parts.type)])).stem


def read_facts(git: Git, root: Path) -> HolderFacts:
    """Read the repository's current distribution, source packages, stack modules and layout.

    Only tracked files count: a leftover folder that git does not track is not the repository's.

    Returns:
        The facts. `packages` holds the dotted import name of each source package folder.

    Raises:
        NameSweepError: when git cannot list the files or `pyproject.toml` cannot be parsed.

    """
    code, out, err = git(root, ["ls-files", "-z"])
    if code != 0:
        msg = f"git ls-files failed in {root}: {err.strip()}"
        raise NameSweepError(msg)
    files = [f.split("/") for f in out.split("\0") if f]
    below_src = [p[1:] for p in files if len(p) > 1 and p[0] == SRC_FOLDER]
    roots = sorted({r for p in below_src if p[-1].endswith(".py") and (r := _source_root(p[:-1]))})
    inits = sorted(
        "/".join([SRC_FOLDER, *p])
        for p in below_src
        if p[-1] == "__init__.py" and _source_root(p[:-1]) == () and len(p) > 1
    )
    stacks = sorted(
        p[2].removesuffix(".py")
        for p in files
        if len(p) == STACK_DEPTH and f"{p[0]}/{p[1]}" == STACK_FOLDER and p[2].endswith(".py") and p[2] != "__init__.py"
    )
    return HolderFacts(
        _distribution(root),
        tuple(".".join(r) for r in roots),
        tuple(stacks),
        bool(below_src),
        any(p[0] == TESTS_FOLDER and len(p) > 1 for p in files),
        tuple(inits),
    )


def _distribution(root: Path) -> str | None:
    """Read `project.name` from the repository's `pyproject.toml`.

    Returns:
        The name, or None when there is no `pyproject.toml` or it names no project.

    Raises:
        NameSweepError: when the file cannot be read or parsed.

    """
    path = root / PYPROJECT
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
    holds are brought to what `atw-naming` gives for it (`python-distribution` and
    `python-package`, each with `--repository`). A repository that holds several source packages
    is reported in the notes and its packages are left alone.

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
    if len(facts.packages) == 1:
        package = namer(["name", "python-package", "--repository", new])
        if facts.packages[0] != package:
            changes.append(NameChange("import-package", facts.packages[0], package))
    elif facts.packages:
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


def package_path(import_name: str) -> str:
    """Write an import name as the folder path under `src`.

    Returns:
        `src/` and the dotted name with slashes.

    """
    return f"{SRC_FOLDER}/{import_name.replace('.', '/')}"


def planned_moves(changes: Sequence[NameChange], facts: HolderFacts) -> list[FileMove]:
    """List the tracked paths the changes move: the package folder, the stack modules, stray inits.

    A tracked `__init__.py` in an app or team folder is removed: those folders are namespace
    packages and start no package of their own.

    Returns:
        One move per package folder and per held stack module that changes name, and one removal
        per `__init__.py` in a namespace folder.

    """
    moves: list[FileMove] = []
    for c in changes:
        if c.kind == "import-package":
            moves.append(FileMove(package_path(c.old), package_path(c.new)))
        elif c.kind == "stack-file" and c.old in facts.stack_modules:
            moves.append(FileMove(f"{STACK_FOLDER}/{c.old}.py", f"{STACK_FOLDER}/{c.new}.py"))
    moves.extend(FileMove(init, "") for init in facts.namespace_inits)
    return moves


def apply_moves(git: Git, root: Path, moves: Sequence[FileMove]) -> None:
    """Move each path with `git mv` (creating the folder it moves into), or remove it with `git rm`.

    Raises:
        NameSweepError: when git refuses a move.

    """
    for m in moves:
        if m.new:
            (root / m.new).parent.mkdir(parents=True, exist_ok=True)
            code, _, err = git(root, ["mv", m.old, m.new])
        else:
            code, _, err = git(root, ["rm", "-q", m.old])
        if code != 0:
            msg = f"git {'mv' if m.new else 'rm'} {m.old} {m.new} failed in {root}: {err.strip()}".replace("  ", " ")
            raise NameSweepError(msg)


def adjust_pyproject(root: Path) -> list[str]:
    """Bring the package discovery and type check settings of `pyproject.toml` to the nested layout.

    A source package under a namespace folder needs setuptools to scan namespaces
    (`namespaces = true`, the default, so only an explicit `false` is changed) and mypy to map
    the files to module names from `src` (`explicit_package_bases = true` and
    `mypy_path = "src"`, added to an existing `[tool.mypy]` section when it lacks them). Nothing
    is added to a repository that configures neither.

    Returns:
        A line for each setting changed.

    Raises:
        NameSweepError: when `pyproject.toml` cannot be read or written.

    """
    path = root / PYPROJECT
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        msg = f"cannot read {path}: {exc}"
        raise NameSweepError(msg) from exc
    done: list[str] = []
    text, n = NAMESPACES_OFF.subn(r"\g<1>true", text)
    if HATCH_WHEEL in text and "only-include" not in text:
        text, hatch = HATCH_PACKAGES.subn(r'only-include = ["\g<1>"]\nsources = ["src"]', text)
        if hatch:
            done.append("hatch wheel: only-include and sources, so the app folder is shipped")
    if n:
        done.append("setuptools packages.find: namespaces = true")
    section = MYPY_SECTION.search(text)
    if section:
        body = text[section.end() :]
        end = re.search(r"(?m)^\[", body)
        body = body[: end.start()] if end else body
        keys = (
            ("explicit_package_bases", "true"),
            ("mypy_path", MYPY_PATH_SRC_CDK if (root / "cdk").is_dir() else MYPY_PATH_SRC),
        )
        missing = [(k, v) for k, v in keys if not re.search(rf"(?m)^{k}[ \t]*=", body)]
        if missing:
            lines = "".join(f"{k} = {v}\n" for k, v in missing)
            text = text[: section.end()] + lines + text[section.end() :]
            done.append("mypy: " + ", ".join(k for k, _ in missing))
    if done:
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            msg = f"cannot write {path}: {exc}"
            raise NameSweepError(msg) from exc
    return done


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


def _hyphen_rule(change: NameChange, only_in: str | None = None) -> Rule:
    """Build the rule for a hyphenated name that stands alone (not part of a longer name).

    Returns:
        The rule.

    """
    pattern = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(change.old)}(?![A-Za-z0-9_]|-[A-Za-z0-9])")
    return Rule(change.kind, change_label(change), change.old, pattern, change.new, only_in)


def _distribution_rules(change: NameChange, holder: str) -> list[Rule]:
    """Build the rules for a distribution name: its dependency lines, and the holder's own lock file.

    A dependency line names the distribution in any case and with any of `-`, `_`, `.` between
    its words (PEP 503), so the rule matches the normalized name that way. It never matches after
    a `/` (a URL) or in a Markdown file, where the same text is the repository's name.

    Returns:
        The rules.

    """
    label = change_label(change)
    words = normalize(change.old).split("-")
    spelling = r"[-_.]+".join(re.escape(w) for w in words)
    pattern = re.compile(rf"(?i)(?<![A-Za-z0-9_./-]){spelling}(?![A-Za-z0-9_]|-[A-Za-z0-9])")
    rules = [Rule(change.kind, label, words[0], pattern, change.new, None, DEPENDENCY_SUFFIXES)]
    before, after = normalize(change.old), normalize(change.new)
    if before != after:
        lock = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(before)}(?![A-Za-z0-9_]|-[A-Za-z0-9])")
        rules.append(Rule(change.kind, label, before, lock, after, holder, lock=True))
    return rules


def _is_generic(package: str) -> bool:
    """Tell whether a package name is a common word that real code and prose also use.

    A name that starts with an app (`skillspoke_text`, `shared.text`, `employer_authn_service`)
    is distinctive. Any other name is generic, an underscore included: `career_profile` and
    `job_boards` are also variable names, file names and prose, so they are replaced only
    where they are an import, a dotted path, a `src/` path and the like.

    Returns:
        False when the name starts with an app name followed by `_` or `.`, else True.

    """
    return package.replace(".", "_").split("_", 1)[0] not in APP_FOLDERS


def _package_rules(change: NameChange, holder: str) -> list[Rule]:
    """Build the rules for an import package: plain for a distinctive name, contextual for a generic one.

    The order matters, because the rules run one after another on a file: the `src/` path (a
    folder path, where the new name is written with slashes) and the bare `pyproject.toml` key
    (which must be quoted once the name has a dot) come before the plain dotted replacement.

    Returns:
        The rules.

    """
    old, new = re.escape(change.old), change.new
    old_path, new_path = change.old.replace(".", "/"), change.new.replace(".", "/")
    label = change_label(change)
    kind = change.kind
    generic = _is_generic(change.old)
    where = holder if generic else None
    app = new_path.split("/", 1)[0]
    rules = [
        Rule(
            kind, label, old_path,
            re.compile(rf"([└├]──[ \t]+){re.escape(old_path)}(?=/)"),
            rf"\g<1>{new_path}", where,
        ),
        Rule(
            kind, label, old_path,
            re.compile(rf"(?<![A-Za-z0-9_-])(cp[ \t]+-r[ \t]+)src/{re.escape(old_path)}(?=[ \t])"),
            rf"\g<1>src/{app}", where,
        ),
        Rule(
            kind, label, old_path,
            re.compile(rf"(?<![A-Za-z0-9_-])(src/){re.escape(old_path)}(?![A-Za-z0-9_-])"),
            rf"\g<1>{new_path}", where,
        ),
        Rule(
            kind, label, change.old,
            re.compile(rf"(?m)^([ \t]*){old}([ \t]*=)"),
            rf'\g<1>"{new}"\g<2>', holder, None, frozenset({PYPROJECT}),
        ),
    ]  # fmt: skip
    if not generic:
        rules.append(
            Rule(
                kind,
                label,
                change.old,
                re.compile(rf"(?<![A-Za-z0-9_./-]){old}(?![A-Za-z0-9_/])"),
                new,
            ),
        )
        return rules
    rules += [
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
            re.compile(rf"(--cov[= ]){old}(?![A-Za-z0-9_])"),
            rf"\g<1>{new}", holder,
        ),
        Rule(
            kind, label, change.old,
            re.compile(rf"([\"']){old}(\*?)\1"),
            rf"\g<1>{new}\g<2>\g<1>", holder, None, PYTHON_CONFIG_FILES,
        ),
        Rule(
            kind, label, change.old,
            re.compile(rf"(get_lambda_code\(\s*)([\"']){old}\2"),
            rf"\g<1>\g<2>{new}\g<2>", holder, PYTHON_SUFFIXES,
        ),
    ]  # fmt: skip
    return rules


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
                rules.extend(_distribution_rules(c, holder))
            case "stack-file":
                rules.append(
                    Rule(
                        c.kind, change_label(c), c.old,
                        re.compile(rf"(?<![A-Za-z0-9_]){re.escape(c.old)}(?![A-Za-z0-9_])"),
                        c.new, holder,
                    ),
                )  # fmt: skip
            case "import-package":
                rules.extend(_package_rules(c, holder))
            case _:
                assert_never(c.kind)
    return rules


def build_document_rules(changes: Sequence[NameChange], repository_of: dict[str, str]) -> list[Rule]:
    """Build the rewrites for the architecture documents: the same names, written only where they are names.

    A document says a published package, an import package or a source folder in prose and in
    code blocks. The `src/` path and a distinctive import name are replaced as in code. A
    generic import name is replaced only as an `import` or `from` line or in a quoted dotted
    path. A distribution is replaced as the whole word, unless it is spelled like the repository
    that publishes it, because then the document's reference to the repository would change too.
    `repository_of` maps each change's old name to the repository it belongs to, by its label.

    Returns:
        The rules, none limited to a repository.

    """
    rules: list[Rule] = []
    for c in changes:
        match c.kind:
            case "distribution":
                if c.old != repository_of.get(change_label(c)):
                    rules.append(_hyphen_rule(c))
            case "import-package":
                rules.extend(dataclasses.replace(r, only_in=None) for r in _package_rules(c, "") if r.basenames is None)
            case "repository" | "stack" | "stack-file":
                rules.append(_hyphen_rule(c))
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
        allowed = base in LOCK_FILES if r.lock else base not in LOCK_FILES and not excluded
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
    original = _read_text(path)
    if original is None:
        return None
    text = original
    total = 0
    kinds: set[NameKind] = set()
    labels: set[str] = set()
    for r in chosen:
        text, n = r.pattern.subn(r.repl, text)
        if n:
            total += n
            kinds.add(r.kind)
            labels.add(r.label)
    if not total or text == original:
        return None
    if write:
        path.write_bytes(text.encode("utf-8"))
    changed = tuple(
        i for i, (a, b) in enumerate(zip(original.split("\n"), text.split("\n"), strict=False), 1) if a != b
    )
    return FileEdit(rel, total, frozenset(kinds), frozenset(labels), changed)


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
    hold an old name first. A target with `paths` reads only those folders.

    Returns:
        One edit per file that changes, in path order.

    Raises:
        NameSweepError: when `git grep` fails.

    """
    root = target.root
    live = [r for r in rules if r.only_in in {None, target.label}]
    if not live:
        return []
    args = ["grep", "--null", "-l", "-I", "-i", "-F"]
    for needle in sorted({r.needle for r in live}):
        args += ["-e", needle]
    if target.paths:
        args += ["--", *target.paths]
    code, out, err = git(root, args)
    if code == GREP_LIST_NONE:
        return []
    if code != GREP_LIST_FOUND:
        msg = f"git grep failed in {root}: {err.strip()}"
        raise NameSweepError(msg)
    edits = (_edit_file(root, rel, live, excludes, write=write) for rel in sorted(p for p in out.split("\0") if p))
    return [e for e in edits if e is not None]


def python_problems(
    facts: HolderFacts,
    repository: str,
    check: Checker,
    *,
    unit_tests: bool = True,
) -> list[PythonProblem]:
    """Check what a repository has against the Python names `atw-naming` gives it.

    Three checks go to `atw-naming check` with `--repository`: the distribution (the `name` in
    `pyproject.toml`), the import package, and the source folder path. The rest is the layout the
    standard sets: `src` is the source root, `tests` the unit test root, and no `__init__.py` sits
    in an app or team folder. A repository with several source packages has none of the three
    package checks run, because there is no one package to check.

    Returns:
        One problem per failed check or missing part; empty when the repository conforms.

    """
    out: list[PythonProblem] = []
    if facts.distribution is None:
        out.append(PythonProblem("python-distribution", "pyproject.toml names no project"))
    else:
        ok, msg = check(["python-distribution", facts.distribution, "--repository", repository])
        if not ok:
            out.append(PythonProblem("python-distribution", msg))
    parts = parse_repo_name(repository)
    if not facts.has_src:
        if parts is None or parts.type in SOURCE_TYPES:
            out.append(PythonProblem("src", "no src folder: the source root is src"))
    elif len(facts.packages) != 1:
        found = ", ".join(facts.packages) or "none"
        out.append(PythonProblem("python-package", f"src holds {len(facts.packages)} source packages ({found})"))
    else:
        package = facts.packages[0]
        for kind, value in (("python-package", package), ("python-package-path", package_path(package))):
            ok, msg = check([kind, value, "--repository", repository])
            if not ok:
                out.append(PythonProblem(kind, msg))
    if unit_tests and not facts.has_tests:
        out.append(PythonProblem("tests", "no tests folder: the unit test root is tests"))
    out.extend(
        PythonProblem("namespace-init", f"{init} must not exist: the folder is a namespace package")
        for init in facts.namespace_inits
    )
    return out
