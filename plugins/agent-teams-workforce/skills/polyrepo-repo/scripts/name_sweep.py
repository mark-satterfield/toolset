"""The names a repository rename covers beyond the repository, and the sweep that updates every reference.

`polyrepo.py rename` uses this module. A rename covers four kinds of name besides the repository:
the CDK stack ids and the stack file names inside it, and the Python distribution and import
package it publishes. Every new name comes from the project's naming command
(`name repository-names`, which the caller runs and hands in as `RepositoryNames`); nothing here
composes or parses a name.

The source root is `src`, and the source package is the folder the naming command gives; the
project folder above it (`src/{project}`) is a namespace folder and holds no `__init__.py`. A
repository may also hold its package one folder deeper, under a `team` folder, or directly under
`src`; the facts read here find it in each of those places.

The old name of each kind is read from the repository (the `name` in `pyproject.toml`, the package
folders under `src/`, the stack modules under `cdk/stacks/`) or, for a stack id, from the names
the naming command gives the old repository name. A sweep then rewrites every reference to an
old name in the tracked text files of the repositories it is handed:

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

    from naming_command import RepositoryNames

type NameKind = Literal["repository", "stack", "stack-file", "distribution", "import-package"]
type Git = Callable[[Path, Sequence[str]], tuple[int, str, str]]

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
STACK_DEPTH = 3
MYPY_SECTION = re.compile(r"(?m)^\[tool\.mypy\][ \t]*\r?\n")
MYPY_PATH_SRC = '"src"'
MYPY_PATH_SRC_CDK = '["src", "cdk"]'
NAMESPACES_OFF = re.compile(r"(?m)^(namespaces[ \t]*=[ \t]*)false\b")
HATCH_WHEEL = "[tool.hatch.build.targets.wheel]"
HATCH_PACKAGES = re.compile(r'(?m)^packages[ \t]*=[ \t]*\["(src/[^"/]+/[^"]+)"\][ \t]*$')


class NameSweepError(Exception):
    """A name cannot be planned or a sweep cannot run."""


@dataclasses.dataclass(frozen=True, slots=True)
class NameChange:
    """One name that changes: its kind, the name now, and the name the naming command gives."""

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
    """One way a repository's Python names differ from what the naming command gives."""

    check: str
    detail: str


def _stem(module_file: str | None) -> str | None:
    """Drop the `.py` of a stack file name.

    Returns:
        The module name, or None when there is no file name.

    """
    return Path(module_file).stem if module_file else None


def stack_changes(
    old: str,
    before: RepositoryNames | None,
    after: RepositoryNames,
    facts: HolderFacts,
) -> tuple[list[NameChange], list[str]]:
    """Name the stack id and stack file module that change between two repository names.

    The new names are the ones the naming command gives the new repository name. The old stack
    id is the one it gives the old name; the old stack file is that one too, or else the one stack
    module the repository holds.

    Returns:
        One change per stack id and per stack module whose name differs, and notes on what was
        not planned and why.

    """
    out: list[NameChange] = []
    notes: list[str] = []
    if before is None:
        notes.append(
            f"{old} is not a repository name the naming command reads, so no old stack id is derived from it; "
            "a stack id spelled like the repository is covered by the repository rename",
        )
    elif before.cdk_stack and after.cdk_stack and before.cdk_stack != after.cdk_stack:
        out.append(NameChange("stack", before.cdk_stack, after.cdk_stack))
    held = facts.stack_modules[0] if len(facts.stack_modules) == 1 else None
    old_module = _stem(before.cdk_stack_file) if before is not None else held
    new_module = _stem(after.cdk_stack_file)
    if old_module and new_module and old_module != new_module:
        out.append(NameChange("stack-file", old_module, new_module))
    return out, notes


def _source_root(dirs: Sequence[str], projects: frozenset[str]) -> tuple[str, ...]:
    """Find the package folder a source file sits in: the project (and team) folders, then one more.

    A project folder (one of `projects`) and a `team` folder under it are namespace folders. A
    source package is the first folder below them; in a repository whose `src` holds no project
    folder, it is the first folder below `src`.

    Returns:
        The folders from `src`'s children down to the package folder, or () for a file that
        sits directly in a namespace folder.

    """
    depth = 0
    if dirs and dirs[0] in projects:
        depth = 2 if len(dirs) > 1 and dirs[1] == TEAM_FOLDER else 1
    return tuple(dirs[: depth + 1]) if len(dirs) > depth else ()


def project_folders(*names: RepositoryNames | None) -> frozenset[str]:
    """Collect the project folders under `src` that the repositories' import packages sit in.

    Returns:
        The first part of each import package the naming command gave.

    """
    return frozenset(n.python_import_package.split(".", 1)[0] for n in names if n is not None)


def read_facts(git: Git, root: Path, projects: frozenset[str]) -> HolderFacts:
    """Read the repository's current distribution, source packages, stack modules and layout.

    Only tracked files count: a leftover folder that git does not track is not the repository's.
    `projects` are the project folders a source package may sit in (:func:`project_folders`).

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
    roots = sorted({r for p in below_src if p[-1].endswith(".py") and (r := _source_root(p[:-1], projects))})
    inits = sorted(
        "/".join([SRC_FOLDER, *p])
        for p in below_src
        if p[-1] == "__init__.py" and _source_root(p[:-1], projects) == () and len(p) > 1
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
    facts: HolderFacts,
    before: RepositoryNames | None,
    after: RepositoryNames | None,
    new: str,
) -> tuple[list[NameChange], list[str]]:
    """Plan every name a rename of `old` to `new` changes, each as the naming command gives it.

    `before` and `after` are what the naming command gives the old and the new repository name
    (`name repository-names`), None for a name it does not read as a repository holding a stack.
    With `old == new` only the Python names are planned: the repository stays and the names it
    holds are brought to what the naming command gives for it. A repository that holds several
    source packages is reported in the notes and its packages are left alone.

    Returns:
        The changes (repository first), and notes on what was not planned and why.

    """
    changes: list[NameChange] = []
    notes: list[str] = []
    if old != new:
        changes.append(NameChange("repository", old, new))
    if after is None:
        notes.append(f"the naming command gives {new} no stack or Python names, so none is planned for it")
        return changes, notes
    if facts.distribution is not None and facts.distribution != after.python_distribution:
        changes.append(NameChange("distribution", facts.distribution, after.python_distribution))
    if len(facts.packages) == 1:
        if facts.packages[0] != after.python_import_package:
            changes.append(NameChange("import-package", facts.packages[0], after.python_import_package))
    elif facts.packages:
        notes.append(f"{new} holds several source packages ({', '.join(facts.packages)}); none is renamed")
    if old != new:
        stacks, stack_notes = stack_changes(old, before, after, facts)
        changes.extend(c for c in stacks if _held(c, facts))
        notes.extend(stack_notes)
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


def _is_generic(change: NameChange) -> bool:
    """Tell whether the old package name is a common word that real code and prose also use.

    A name that starts with the project folder of the new package (`acme_text`,
    `shared.text`) is distinctive. Any other name is generic, an underscore included:
    `career_profile` and `job_boards` are also variable names, file names and prose, so they are
    replaced only where they are an import, a dotted path, a `src/` path and the like.

    Returns:
        False when the old name starts with the new package's project folder followed by `_`
        or `.`, else True.

    """
    return change.old.replace(".", "_").split("_", 1)[0] != change.new.split(".", 1)[0]


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
    generic = _is_generic(change)
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
    """Build the rules that find the old names in the architecture documents, matched only where they are names.

    A rename reports the documents these rules match and edits none of them: every vault edit
    is the filing-clerk's. A document says a published package, an import package or a source
    folder in prose and in code blocks. The `src/` path and a distinctive import name are matched
    as in code. A generic import name is matched only as an `import` or `from` line or in a
    quoted dotted path. A distribution is matched as the whole word, unless it is spelled like
    the repository that publishes it, because that is the document's reference to the repository.
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


def _name_problems(facts: HolderFacts, names: RepositoryNames | None) -> list[PythonProblem]:
    """Compare the distribution and the one source package with the names the naming command gives.

    Returns:
        One problem per name that differs, or that the naming command does not give.

    """
    if names is None:
        return [PythonProblem("python-names", "the naming command gives this repository name no Python names")]
    out: list[PythonProblem] = []
    if facts.distribution is not None and facts.distribution != names.python_distribution:
        out.append(
            PythonProblem(
                "python-distribution",
                f"pyproject.toml names {facts.distribution}; the naming command gives {names.python_distribution}",
            ),
        )
    if facts.has_src and len(facts.packages) == 1:
        package = facts.packages[0]
        out.extend(
            PythonProblem(kind, f"{value} is not {wanted}, which the naming command gives")
            for kind, value, wanted in (
                ("python-package", package, names.python_import_package),
                ("python-package-path", package_path(package), names.python_source_package),
            )
            if value != wanted
        )
    return out


def python_problems(
    facts: HolderFacts,
    names: RepositoryNames | None,
    *,
    requires_src: bool = True,
    unit_tests: bool = True,
) -> list[PythonProblem]:
    """Check what a repository has against the Python names the naming command gives it.

    `names` is what the naming command gives the repository name (`name repository-names`), None
    for a name it does not read as a repository holding a stack. The distribution (the `name` in
    `pyproject.toml`), the import package and the source folder path must be those names. The rest
    is the layout: `src` is the source root (required when `requires_src`: the caller decides it
    from the template that builds the repository), `tests` the unit test root, and no `__init__.py` sits
    in a project or team folder. A repository with several source packages has none of the package
    checks run, because there is no one package to check.

    Returns:
        One problem per failed check or missing part; empty when the repository conforms.

    """
    out = _name_problems(facts, names)
    if facts.distribution is None:
        out.append(PythonProblem("python-distribution", "pyproject.toml names no project"))
    if not facts.has_src:
        if requires_src:
            out.append(PythonProblem("src", "no src folder: the source root is src"))
    elif len(facts.packages) != 1:
        found = ", ".join(facts.packages) or "none"
        out.append(PythonProblem("python-package", f"src holds {len(facts.packages)} source packages ({found})"))
    if unit_tests and not facts.has_tests:
        out.append(PythonProblem("tests", "no tests folder: the unit test root is tests"))
    out.extend(
        PythonProblem("namespace-init", f"{init} must not exist: the folder is a namespace package")
        for init in facts.namespace_inits
    )
    return out
