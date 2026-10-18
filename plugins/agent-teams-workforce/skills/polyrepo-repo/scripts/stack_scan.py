"""Detect the stacks a repository holds and the checker configurations it carries.

Detection is generic: it reads evidence from the files in a working tree (file types,
manifests, configuration files, workflow files) and from no list of repositories. The files
scanned are the ones git reports as tracked or untracked-but-not-ignored, without virtual
environments, `node_modules`, build output and `.worktrees/`.

Every checker configuration carries a fingerprint: a hash of its normalised content (parsed
and re-serialised when the format allows, otherwise its non-blank lines stripped), so identical
copies in different repositories group together.
"""

from __future__ import annotations

import configparser
import dataclasses
import hashlib
import json
import re
import tomllib
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

type GitOutput = Callable[[Path, Sequence[str]], str | None]

FINGERPRINT_LENGTH: Final = 12
EXCLUDED_DIRS: Final = frozenset({
    ".git", ".worktrees", ".venv", "venv", "node_modules", "dist", "build", "cdk.out", ".next", ".nuxt",
    "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".tox", "site-packages", ".turbo",
    "coverage", ".gitnexus", ".code-checks",
})  # fmt: skip
SUFFIX_KINDS: Final[Mapping[str, str]] = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".yml": "yaml", ".yaml": "yaml",
    ".json": "json", ".jsonc": "json",
    ".md": "markdown", ".mdx": "markdown",
    ".toml": "toml",
    ".html": "html",
}  # fmt: skip
NAME_KINDS: Final[Mapping[str, str]] = {"Dockerfile": "dockerfile"}
DATA_STACKS: Final = ("shell", "yaml", "json", "markdown", "toml", "dockerfile")
WEB_FRAMEWORKS: Final[Mapping[str, str]] = {
    "next": "Next.js", "react": "React", "vue": "Vue", "nuxt": "Nuxt", "svelte": "Svelte",
    "@sveltejs/kit": "SvelteKit", "@angular/core": "Angular", "astro": "Astro", "solid-js": "Solid",
    "vite": "Vite",
}  # fmt: skip
WEB_CONFIG_FILE: Final = re.compile(r"(next|vite|nuxt|svelte|astro)\.config\.\w+")
CDK_PYTHON_PACKAGE: Final = "aws-cdk-lib"
CDK_APP_LANGUAGES: Final = (
    ("python", re.compile(r"\bpython3?\b|\buv run\b|\.py\b")),
    ("typescript", re.compile(r"ts-node|\btsx\b|\.ts\b")),
    ("javascript", re.compile(r"\bnode\b|\.js\b")),
    ("java", re.compile(r"\bmvn\b|\bgradle\b")),
    ("csharp", re.compile(r"\bdotnet\b")),
    ("go", re.compile(r"\bgo run\b")),
)
CONFIG_FILES: Final = (
    ("ruff", re.compile(r"\.?ruff\.toml")),
    ("mypy", re.compile(r"\.?mypy\.ini")),
    ("pyright", re.compile(r"pyrightconfig\.json")),
    ("flake8", re.compile(r"\.flake8")),
    ("eslint", re.compile(r"eslint\.config\.[cm]?[jt]s|\.eslintrc(\.(c?js|json|ya?ml))?")),
    ("biome", re.compile(r"biome\.jsonc?")),
    ("prettier", re.compile(r"\.prettierrc(\.(json|ya?ml|[cm]?js|toml))?|prettier\.config\.[cm]?[jt]s")),
    ("tsconfig", re.compile(r"tsconfig(\.[\w.-]+)?\.json")),
    ("pre-commit", re.compile(r"\.pre-commit-config\.ya?ml")),
    ("shellcheck", re.compile(r"\.shellcheckrc")),
    ("yamllint", re.compile(r"\.yamllint(\.ya?ml)?")),
    ("markdownlint", re.compile(r"\.markdownlint(-cli2)?(\.(jsonc?|ya?ml|[cm]?js))?|\.markdownlintrc|\.?rumdl\.toml")),
)
PYPROJECT_SECTIONS: Final = (("ruff", ("tool", "ruff")), ("mypy", ("tool", "mypy")), ("pyright", ("tool", "pyright")))
SETUP_CFG_SECTIONS: Final = (("mypy", re.compile(r"mypy(-.*)?")), ("flake8", re.compile(r"flake8")))
PACKAGE_JSON_KEYS: Final = (("eslint", "eslintConfig"), ("prettier", "prettier"))
TOOL_TOKENS: Final = (
    ("ruff", re.compile(r"\bruff\b")),
    ("flake8", re.compile(r"\bflake8\b")),
    ("pylint", re.compile(r"\bpylint\b")),
    ("mypy", re.compile(r"\bmypy\b")),
    ("pyright", re.compile(r"\bpyright\b")),
    ("eslint", re.compile(r"\beslint\b")),
    ("biome", re.compile(r"\bbiome\b")),
    ("prettier", re.compile(r"\bprettier\b")),
    ("tsc", re.compile(r"\btsc\b")),
    ("cdk-nag", re.compile(r"cdk[-_]nag", re.IGNORECASE)),
    ("pre-commit", re.compile(r"\bpre-commit\b")),
    ("shellcheck", re.compile(r"\bshellcheck\b")),
    ("yamllint", re.compile(r"\byamllint\b|\bcheck-yaml\b")),
    ("check-json", re.compile(r"\bcheck-json\b")),
    ("markdownlint", re.compile(r"markdownlint|\brumdl\b")),
)
LINT_TOOLS: Final = frozenset({"ruff", "flake8", "pylint", "eslint", "biome", "prettier", "shellcheck", "yamllint"})
TYPE_TOOLS: Final = frozenset({"mypy", "pyright", "tsc"})
STACK_CHECKS: Final[Mapping[str, tuple[tuple[str, frozenset[str]], ...]]] = {
    "python": (("lint", frozenset({"ruff", "flake8", "pylint"})), ("types", frozenset({"mypy", "pyright"}))),
    "typescript": (("lint", frozenset({"eslint", "biome"})), ("types", frozenset({"tsconfig", "tsc"}))),
    "javascript": (("lint", frozenset({"eslint", "biome"})),),
    "cdk": (("nag", frozenset({"cdk-nag"})),),
    "shell": (("lint", frozenset({"shellcheck"})),),
    "yaml": (("lint", frozenset({"yamllint"})),),
    "json": (("lint", frozenset({"check-json", "biome", "prettier"})),),
    "markdown": (("lint", frozenset({"markdownlint", "prettier"})),),
}
CODE_STACKS: Final = ("python", "typescript", "javascript", "cdk", "web")
WORKFLOW_FOLDER: Final = ".github/workflows/"
TASK_FILES: Final = re.compile(r"Taskfile(\.dist)?\.ya?ml|Makefile|justfile")
CDK_NAG_SOURCES: Final = ("*.py", "*.ts", "*.js", "*.mjs")
CDK_NAG_IMPORT: Final = (
    r"^[[:space:]]*(from|import)[[:space:]]+cdk_nag"
    r"|from[[:space:]]+['\"]cdk-nag['\"]"
    r"|require\(['\"]cdk-nag['\"]\)"
)
COVERAGE_EXCLUDED: Final = frozenset({"ci"})
REQUIREMENT_NAME: Final = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
REQUIREMENTS_FILE: Final = re.compile(r"requirements[\w.-]*\.txt")


@dataclasses.dataclass(frozen=True, slots=True)
class Stack:
    """One stack a repository holds, with the evidence for it."""

    name: str
    evidence: tuple[str, ...]
    languages: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class CheckerConfig:
    """One checker configuration found in a repository."""

    checker: str
    path: str
    fingerprint: str | None
    detail: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class RepoScan:
    """What one repository holds: its stacks, its checker configurations and its missing checks."""

    repo: str
    path: str
    stacks: tuple[Stack, ...]
    configs: tuple[CheckerConfig, ...]
    tools: tuple[str, ...]
    gaps: tuple[str, ...]
    error: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class Tree:
    """The files of a working tree that the scan reads."""

    root: Path
    files: tuple[str, ...]
    kinds: Counter[str]

    def named(self, pattern: re.Pattern[str]) -> list[str]:
        """Return the files whose base name matches the pattern in full.

        Args:
            pattern: The base-name pattern.

        Returns:
            The relative paths, in tree order.

        """
        return [rel for rel in self.files if pattern.fullmatch(PurePosixPath(rel).name)]

    def text(self, rel: str) -> str | None:
        """Read one file as text.

        Args:
            rel: The path relative to the tree root.

        Returns:
            The text, or None when the file cannot be read as UTF-8.

        """
        try:
            return (self.root / rel).read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            return None


# ------------------------------------------------------------------------------------------
# reading the tree


def _is_scanned(rel: str) -> bool:
    """Report whether a path lies outside every excluded folder.

    Args:
        rel: A path relative to the tree root.

    Returns:
        True when no folder in the path is excluded.

    """
    parts: tuple[str, ...] = PurePosixPath(rel).parts[:-1]
    return bool(rel) and not rel.endswith("/") and not EXCLUDED_DIRS.intersection(parts)


def _kind(rel: str) -> str | None:
    """Return the file kind of a path, from its base name or its suffix.

    Args:
        rel: A relative path.

    Returns:
        The kind, or None when the file is of no kind the scan counts.

    """
    path: PurePosixPath = PurePosixPath(rel)
    return NAME_KINDS.get(path.name) or SUFFIX_KINDS.get(path.suffix.lower())


def read_tree(root: Path, git_output: GitOutput) -> Tree:
    """List the files of a working tree that git tracks or does not ignore.

    Args:
        root: The working tree.
        git_output: Runs git in a folder and returns its output, or None when git fails.

    Returns:
        The tree.

    Raises:
        ValueError: When git cannot list the files.

    """
    listing: str | None = git_output(root, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    if listing is None:
        message: str = f"git ls-files failed in {root}"
        raise ValueError(message)
    files: tuple[str, ...] = tuple(sorted({rel for rel in listing.split("\0") if _is_scanned(rel)}))
    kinds: Counter[str] = Counter(kind for kind in map(_kind, files) if kind)
    return Tree(root, files, kinds)


# ------------------------------------------------------------------------------------------
# fingerprints


def _digest(text: str) -> str:
    """Hash normalised content.

    Args:
        text: The normalised content.

    Returns:
        The first characters of its SHA-256 hex digest.

    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]


def _plain_lines(text: str) -> str:
    """Normalise text by stripping every line and dropping blank and comment-only lines.

    Args:
        text: The raw text.

    Returns:
        The normalised text.

    """
    kept: list[str] = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in kept if line and not line.startswith(("#", "//")))


def _canonical(value: object) -> str:
    """Serialise a parsed value with sorted keys.

    Args:
        value: The parsed configuration.

    Returns:
        Its canonical JSON text.

    """
    return json.dumps(value, sort_keys=True, default=str)


def _parsed(rel: str, text: str) -> object | None:
    """Parse configuration text by the format its file name gives.

    Args:
        rel: The file's relative path.
        text: The file's text.

    Returns:
        The parsed value, or None when the format is not parsed or the text does not parse.

    """
    suffix: str = PurePosixPath(rel).suffix.lower()
    try:
        if suffix == ".json":
            decoded: object = json.loads(text)
            return decoded
        if suffix == ".toml":
            return tomllib.loads(text)
        if suffix in {".yaml", ".yml"}:
            return _yaml_load(text)
        if suffix == ".ini":
            return _ini_sections(text)
    except ValueError, YAMLError, configparser.Error:
        return None
    return None


def fingerprint_file(rel: str, text: str) -> str:
    """Fingerprint a configuration file.

    Args:
        rel: The file's relative path.
        text: The file's text.

    Returns:
        The fingerprint of its parsed content, or of its normalised lines when it does not parse.

    """
    parsed: object | None = _parsed(rel, text)
    return _digest(_plain_lines(text) if parsed is None else _canonical(parsed))


def _yaml_load(text: str) -> object:
    """Parse YAML safely.

    Args:
        text: The YAML text.

    Returns:
        The parsed value.

    """
    loaded: object = YAML(typ="safe").load(text)
    return loaded


def _ini_sections(text: str) -> dict[str, dict[str, str]]:
    """Parse INI text into its sections.

    Args:
        text: The INI text.

    Returns:
        Each section with its keys.

    """
    parser: configparser.ConfigParser = configparser.ConfigParser(interpolation=None)
    parser.read_string(text)
    return {section: dict(parser.items(section)) for section in parser.sections()}


def _table(value: object, keys: Sequence[str]) -> dict[str, object] | None:
    """Follow keys through nested tables.

    Args:
        value: The parsed document.
        keys: The keys, outermost first.

    Returns:
        The table at the end of the keys, or None when any key is missing or not a table.

    """
    current: object = value
    for key in keys:
        current = current.get(key) if isinstance(current, dict) else None
    return current if isinstance(current, dict) else None


# ------------------------------------------------------------------------------------------
# manifests


@dataclasses.dataclass(frozen=True, slots=True)
class Manifests:
    """The parsed dependency manifests of a tree."""

    pyprojects: dict[str, dict[str, object]]
    package_jsons: dict[str, dict[str, object]]
    python_deps: dict[str, frozenset[str]]
    node_deps: dict[str, frozenset[str]]


def _requirement_names(lines: Iterable[object]) -> set[str]:
    """Extract package names from requirement strings.

    Args:
        lines: Requirement strings, as PEP 508 or requirements-file lines.

    Returns:
        The lower-cased package names.

    """
    matches: Iterable[re.Match[str] | None] = (REQUIREMENT_NAME.match(line) for line in lines if isinstance(line, str))
    return {match.group(1).lower() for match in matches if match}


def _pyproject_deps(document: dict[str, object]) -> frozenset[str]:
    """List every dependency a pyproject.toml declares.

    Args:
        document: The parsed pyproject.toml.

    Returns:
        The package names.

    """
    project: dict[str, object] = _table(document, ["project"]) or {}
    groups: list[object] = [
        *(_table(document, ["project", "optional-dependencies"]) or {}).values(),
        *(_table(document, ["dependency-groups"]) or {}).values(),
    ]
    flat: list[object] = [item for group in groups if isinstance(group, list) for item in group]
    direct: object = project.get("dependencies")
    poetry: dict[str, object] = _table(document, ["tool", "poetry", "dependencies"]) or {}
    names: set[str] = _requirement_names([*(direct if isinstance(direct, list) else []), *flat, *poetry])
    return frozenset(names)


def _package_deps(document: dict[str, object]) -> frozenset[str]:
    """List every dependency a package.json declares.

    Args:
        document: The parsed package.json.

    Returns:
        The package names.

    """
    sections: Iterable[str] = ("dependencies", "devDependencies", "peerDependencies")
    return frozenset(name for section in sections for name in (_table(document, [section]) or {}))


def _parsed_tables(tree: Tree, pattern: re.Pattern[str]) -> dict[str, dict[str, object]]:
    """Parse every file of a name as a table.

    Args:
        tree: The tree.
        pattern: The base-name pattern.

    Returns:
        Each file that parsed to a table, by relative path.

    """
    parsed: dict[str, object | None] = {rel: _parsed(rel, tree.text(rel) or "") for rel in tree.named(pattern)}
    return {rel: value for rel, value in parsed.items() if isinstance(value, dict)}


def read_manifests(tree: Tree) -> Manifests:
    """Parse the dependency manifests of a tree.

    Args:
        tree: The tree.

    Returns:
        The manifests and the dependencies each declares.

    """
    pyprojects: dict[str, dict[str, object]] = _parsed_tables(tree, re.compile(r"pyproject\.toml"))
    package_jsons: dict[str, dict[str, object]] = _parsed_tables(tree, re.compile(r"package\.json"))
    requirements: dict[str, frozenset[str]] = {
        rel: frozenset(_requirement_names((tree.text(rel) or "").splitlines())) for rel in tree.named(REQUIREMENTS_FILE)
    }
    python_deps: dict[str, frozenset[str]] = {
        **{rel: _pyproject_deps(doc) for rel, doc in pyprojects.items()},
        **requirements,
    }
    node_deps: dict[str, frozenset[str]] = {rel: _package_deps(doc) for rel, doc in package_jsons.items()}
    return Manifests(pyprojects, package_jsons, python_deps, node_deps)


def _declaring(deps: Mapping[str, frozenset[str]], package: str) -> list[str]:
    """Name the manifests that declare a package.

    Args:
        deps: The dependencies of each manifest.
        package: The package name.

    Returns:
        The manifests' relative paths.

    """
    return [rel for rel, names in deps.items() if package in names]


# ------------------------------------------------------------------------------------------
# stacks


def _count_line(tree: Tree, kind: str, label: str) -> list[str]:
    """Describe how many files of a kind the tree holds.

    Args:
        tree: The tree.
        kind: The file kind.
        label: How the files are named in the line.

    Returns:
        One line, or none when the tree holds no such file.

    """
    count: int = tree.kinds[kind]
    return [f"{count} {label} files"] if count else []


def _python_stack(tree: Tree, manifests: Manifests) -> Stack | None:
    """Detect Python.

    Args:
        tree: The tree.
        manifests: The tree's manifests.

    Returns:
        The stack, or None when the tree holds no Python.

    """
    evidence: list[str] = [*manifests.pyprojects, *tree.named(REQUIREMENTS_FILE), *_count_line(tree, "python", "*.py")]
    return Stack("python", tuple(evidence)) if evidence else None


def _cdk_language(tree: Tree, rel: str) -> str:
    """Read the language of a CDK app from its cdk.json `app` command.

    Args:
        tree: The tree.
        rel: The cdk.json path.

    Returns:
        The language, or "unknown".

    """
    command: object = (_table(_parsed(rel, tree.text(rel) or ""), []) or {}).get("app")
    text: str = command if isinstance(command, str) else ""
    return next((language for language, pattern in CDK_APP_LANGUAGES if pattern.search(text)), "unknown")


def _cdk_stack(tree: Tree, manifests: Manifests) -> Stack | None:
    """Detect a CDK app or construct library.

    Args:
        tree: The tree.
        manifests: The tree's manifests.

    Returns:
        The stack with its app languages, or None when the tree holds no CDK.

    """
    apps: list[str] = tree.named(re.compile(r"cdk\.json"))
    python_lib: list[str] = _declaring(manifests.python_deps, CDK_PYTHON_PACKAGE)
    node_lib: list[str] = _declaring(manifests.node_deps, CDK_PYTHON_PACKAGE)
    evidence: list[str] = [*apps, *(f"{CDK_PYTHON_PACKAGE} in {rel}" for rel in [*python_lib, *node_lib])]
    if not evidence:
        return None
    languages: set[str] = {_cdk_language(tree, rel) for rel in apps}
    languages |= {"python"} if python_lib else set()
    languages |= {"typescript" if tree.kinds["typescript"] else "javascript"} if node_lib else set()
    return Stack("cdk", tuple(evidence), tuple(sorted(languages)))


def _typescript_stack(tree: Tree) -> Stack | None:
    """Detect TypeScript.

    Args:
        tree: The tree.

    Returns:
        The stack, or None when the tree holds no TypeScript.

    """
    evidence: list[str] = [*tree.named(re.compile(r"tsconfig\.json")), *_count_line(tree, "typescript", "*.ts/*.tsx")]
    return Stack("typescript", tuple(evidence)) if evidence else None


def _javascript_stack(tree: Tree, manifests: Manifests) -> Stack | None:
    """Detect JavaScript: JavaScript files, or a package.json with no TypeScript beside it.

    Args:
        tree: The tree.
        manifests: The tree's manifests.

    Returns:
        The stack, or None when the tree holds no JavaScript.

    """
    lone_packages: list[str] = [] if tree.kinds["typescript"] else list(manifests.package_jsons)
    evidence: list[str] = [*lone_packages, *_count_line(tree, "javascript", "*.js/*.mjs/*.cjs/*.jsx")]
    return Stack("javascript", tuple(evidence)) if evidence else None


def _web_stack(tree: Tree, manifests: Manifests) -> Stack | None:
    """Detect a web front end: a front-end framework dependency or framework configuration.

    Args:
        tree: The tree.
        manifests: The tree's manifests.

    Returns:
        The stack with its frameworks, or None when the tree holds no web front end.

    """
    found: dict[str, list[str]] = {
        label: _declaring(manifests.node_deps, package) for package, label in WEB_FRAMEWORKS.items()
    }
    frameworks: dict[str, list[str]] = {label: rels for label, rels in found.items() if rels}
    configs: list[str] = tree.named(WEB_CONFIG_FILE)
    evidence: list[str] = [*(f"{label} in {', '.join(rels)}" for label, rels in frameworks.items()), *configs]
    return Stack("web", tuple(evidence), tuple(frameworks)) if evidence else None


def _data_stacks(tree: Tree) -> list[Stack]:
    """Detect the other file kinds that have common checkers.

    Args:
        tree: The tree.

    Returns:
        One stack per kind the tree holds.

    """
    return [Stack(kind, (f"{tree.kinds[kind]} files",)) for kind in DATA_STACKS if tree.kinds[kind]]


def detect_stacks(tree: Tree, manifests: Manifests) -> tuple[Stack, ...]:
    """Detect every stack a tree holds.

    Args:
        tree: The tree.
        manifests: The tree's manifests.

    Returns:
        The stacks, code stacks first.

    """
    code: list[Stack | None] = [
        _python_stack(tree, manifests),
        _cdk_stack(tree, manifests),
        _typescript_stack(tree),
        _javascript_stack(tree, manifests),
        _web_stack(tree, manifests),
    ]
    return (*(stack for stack in code if stack), *_data_stacks(tree))


# ------------------------------------------------------------------------------------------
# checker configurations


def _tools_in(text: str) -> tuple[str, ...]:
    """Name the checker tools a piece of text runs or names.

    Args:
        text: Command text.

    Returns:
        The tool names, in table order.

    """
    return tuple(tool for tool, pattern in TOOL_TOKENS if pattern.search(text))


def _hook_ids(value: object) -> tuple[str, ...]:
    """List the hook ids of a parsed pre-commit configuration.

    Args:
        value: The parsed `.pre-commit-config.yaml`.

    Returns:
        The hook ids, in file order.

    """
    repos: object = value.get("repos") if isinstance(value, dict) else None
    hook_lists: list[object] = (
        [repo.get("hooks") for repo in repos if isinstance(repo, dict)] if isinstance(repos, list) else []
    )
    hooks: list[object] = [hook for hooks in hook_lists if isinstance(hooks, list) for hook in hooks]
    return tuple(str(hook.get("id")) for hook in hooks if isinstance(hook, dict))


def _file_config(tree: Tree, checker: str, rel: str) -> CheckerConfig:
    """Describe one checker configuration file.

    Args:
        tree: The tree.
        checker: The checker the file configures.
        rel: The file's relative path.

    Returns:
        The configuration; a pre-commit configuration carries its hook ids.

    """
    text: str | None = tree.text(rel)
    if text is None:
        return CheckerConfig(checker, rel, None, ("unreadable",))
    detail: tuple[str, ...] = _hook_ids(_parsed(rel, text)) if checker == "pre-commit" else ()
    return CheckerConfig(checker, rel, fingerprint_file(rel, text), detail)


def _file_configs(tree: Tree) -> list[CheckerConfig]:
    """Find every checker configuration file.

    Args:
        tree: The tree.

    Returns:
        The configurations.

    """
    return [_file_config(tree, checker, rel) for checker, pattern in CONFIG_FILES for rel in tree.named(pattern)]


def _section_configs(manifests: Manifests) -> list[CheckerConfig]:
    """Find checker sections in pyproject.toml files and checker keys in package.json files.

    Args:
        manifests: The tree's manifests.

    Returns:
        The configurations, each with a path of `<file>#<section>`.

    """
    sections: list[tuple[str, str, dict[str, object] | None]] = [
        (checker, f"{rel}#{'.'.join(keys)}", _table(doc, keys))
        for rel, doc in manifests.pyprojects.items()
        for checker, keys in PYPROJECT_SECTIONS
    ]
    keys: list[tuple[str, str, object]] = [
        (checker, f"{rel}#{key}", doc.get(key))
        for rel, doc in manifests.package_jsons.items()
        for checker, key in PACKAGE_JSON_KEYS
    ]
    found: list[tuple[str, str, object]] = [*sections, *keys]
    return [
        CheckerConfig(checker, path, _digest(_canonical(value))) for checker, path, value in found if value is not None
    ]


def _setup_cfg_configs(tree: Tree) -> list[CheckerConfig]:
    """Find checker sections in setup.cfg and tox.ini files.

    Args:
        tree: The tree.

    Returns:
        The configurations, each with a path of `<file>#<section>`.

    """
    parsed: dict[str, object | None] = {
        rel: _parsed(f"{rel}.ini", tree.text(rel) or "") for rel in tree.named(re.compile(r"setup\.cfg|tox\.ini"))
    }
    tables: dict[str, dict[str, object]] = {rel: value for rel, value in parsed.items() if isinstance(value, dict)}
    return [
        CheckerConfig(checker, f"{rel}#{section}", _digest(_canonical(values)))
        for rel, sections in tables.items()
        for section, values in sections.items()
        for checker, pattern in SETUP_CFG_SECTIONS
        if pattern.fullmatch(section)
    ]


def _workflow_jobs(value: object) -> dict[str, str]:
    """Return each job of a parsed GitHub Actions workflow as text.

    Args:
        value: The parsed workflow.

    Returns:
        Each job's id with its canonical text.

    """
    jobs: dict[str, object] = _table(value, ["jobs"]) or {}
    return {str(job_id): _canonical(job) for job_id, job in jobs.items()}


def _workflow_config(tree: Tree, rel: str) -> CheckerConfig | None:
    """Describe the checker jobs of one workflow file.

    Args:
        tree: The tree.
        rel: The workflow's relative path.

    Returns:
        The configuration, listing each job that lints, type-checks, runs cdk-nag or pre-commit,
        or None when no job does.

    """
    text: str = tree.text(rel) or ""
    job_tools: dict[str, tuple[str, ...]] = {
        job: _tools_in(body) for job, body in _workflow_jobs(_parsed(rel, text)).items()
    }
    detail: tuple[str, ...] = tuple(f"{job}: {', '.join(tools)}" for job, tools in job_tools.items() if tools)
    return CheckerConfig("ci", rel, fingerprint_file(rel, text), detail) if detail else None


def _workflow_configs(tree: Tree) -> list[CheckerConfig]:
    """Find the CI workflows that run checkers.

    Args:
        tree: The tree.

    Returns:
        The configurations.

    """
    workflows: list[str] = [rel for rel in tree.files if rel.startswith(WORKFLOW_FOLDER) and _kind(rel) == "yaml"]
    configs: list[CheckerConfig | None] = [_workflow_config(tree, rel) for rel in workflows]
    return [config for config in configs if config]


def _task_configs(tree: Tree, manifests: Manifests) -> list[CheckerConfig]:
    """Find task runners (Taskfile, Makefile, justfile, package.json scripts) that run checkers.

    Args:
        tree: The tree.
        manifests: The tree's manifests.

    Returns:
        The configurations, each listing the checker tools it runs.

    """
    texts: dict[str, str] = {rel: tree.text(rel) or "" for rel in tree.named(TASK_FILES)}
    script_texts: dict[str, str] = {
        f"{rel}#scripts": _canonical(doc["scripts"]) for rel, doc in manifests.package_jsons.items() if "scripts" in doc
    }
    found: list[tuple[str, str, tuple[str, ...]]] = [
        (rel, text, _tools_in(text)) for rel, text in {**texts, **script_texts}.items()
    ]
    return [CheckerConfig("tasks", rel, _digest(_plain_lines(text)), tools) for rel, text, tools in found if tools]


def _cdk_nag_configs(tree: Tree, git_output: GitOutput) -> list[CheckerConfig]:
    """Find the source files that use cdk-nag.

    Args:
        tree: The tree.
        git_output: Runs git in a folder and returns its output, or None when git fails.

    Returns:
        One configuration per source file that names cdk-nag.

    """
    listing: str = (
        git_output(tree.root, ["grep", "-l", "-I", "--untracked", "-E", CDK_NAG_IMPORT, "--", *CDK_NAG_SOURCES]) or ""
    )
    return [CheckerConfig("cdk-nag", rel, None) for rel in listing.splitlines() if _is_scanned(rel)]


def find_configs(tree: Tree, manifests: Manifests, git_output: GitOutput) -> tuple[CheckerConfig, ...]:
    """Find every checker configuration of a tree.

    Args:
        tree: The tree.
        manifests: The tree's manifests.
        git_output: Runs git in a folder and returns its output, or None when git fails.

    Returns:
        The configurations.

    """
    return (
        *_file_configs(tree),
        *_section_configs(manifests),
        *_setup_cfg_configs(tree),
        *_workflow_configs(tree),
        *_task_configs(tree, manifests),
        *_cdk_nag_configs(tree, git_output),
    )


# ------------------------------------------------------------------------------------------
# coverage


def _config_tools(config: CheckerConfig) -> set[str]:
    """Name the checker tools one configuration stands for.

    Args:
        config: The configuration.

    Returns:
        The checker itself for a checker's own configuration; the tools it runs for a
        pre-commit configuration, a CI workflow or a task runner.

    """
    runners: set[str] = {"pre-commit", "ci", "tasks"}
    named: set[str] = {tool for line in config.detail for tool in _tools_in(line)}
    return named | {config.checker} if config.checker in runners else {config.checker}


def checker_tools(configs: Iterable[CheckerConfig]) -> tuple[str, ...]:
    """Name every checker tool a repository configures or runs.

    Args:
        configs: The repository's configurations.

    Returns:
        The tool names, sorted.

    """
    return tuple(sorted({tool for config in configs for tool in _config_tools(config)}))


def find_gaps(stacks: Iterable[Stack], tools: Iterable[str]) -> tuple[str, ...]:
    """Name each check a stack calls for that no tool of the repository provides.

    A tool counts when the repository configures it, or runs it from its own pre-commit hooks
    or task runner. A CI workflow does not count on its own: a shared workflow can name a tool
    and run it only when the repository configures it.

    Args:
        stacks: The repository's stacks.
        tools: The checker tools the repository configures or runs.

    Returns:
        One `<stack>:<check>` per missing check.

    """
    present: frozenset[str] = frozenset(tools)
    return tuple(
        f"{stack.name}:{check}"
        for stack in stacks
        for check, satisfying in STACK_CHECKS.get(stack.name, ())
        if not satisfying & present
    )


def scan_repository(repo: str, root: Path, git_output: GitOutput) -> RepoScan:
    """Scan one working tree.

    Args:
        repo: The repository name.
        root: The working tree.
        git_output: Runs git in a folder and returns its output, or None when git fails.

    Returns:
        The scan; a tree git cannot list comes back with its error and nothing else.

    """
    try:
        tree: Tree = read_tree(root, git_output)
    except ValueError as error:
        return RepoScan(repo, str(root), (), (), (), (), str(error))
    manifests: Manifests = read_manifests(tree)
    stacks: tuple[Stack, ...] = detect_stacks(tree, manifests)
    configs: tuple[CheckerConfig, ...] = find_configs(tree, manifests, git_output)
    own: tuple[str, ...] = checker_tools(config for config in configs if config.checker not in COVERAGE_EXCLUDED)
    return RepoScan(repo, str(root), stacks, configs, checker_tools(configs), find_gaps(stacks, own))


# ------------------------------------------------------------------------------------------
# summary


@dataclasses.dataclass(frozen=True, slots=True)
class Variant:
    """Identical copies of one checker configuration."""

    fingerprint: str
    count: int
    locations: tuple[str, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Summary:
    """Repositories grouped by stack, configurations grouped by fingerprint, and missing checks."""

    repositories: int
    stacks: dict[str, list[str]]
    configs: dict[str, list[Variant]]
    variant_counts: dict[str, int]
    gaps: dict[str, list[str]]
    gaps_by_check: dict[str, list[str]]
    code_stack_gaps: list[str]
    errors: dict[str, str]


def _group(pairs: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """Group values by key.

    Args:
        pairs: (key, value) pairs.

    Returns:
        Each key, sorted, with its values in the order given.

    """
    groups: dict[str, list[str]] = {}
    for key, value in pairs:
        groups.setdefault(key, []).append(value)
    return dict(sorted(groups.items()))


def _variants(scans: Sequence[RepoScan], checker: str) -> list[Variant]:
    """Group the configurations of one checker by fingerprint.

    Args:
        scans: Every repository's scan.
        checker: The checker.

    Returns:
        One variant per fingerprint, the most common first.

    """
    pairs: Iterable[tuple[str, str]] = (
        (config.fingerprint or "-", f"{scan.repo}:{config.path}")
        for scan in scans
        for config in scan.configs
        if config.checker == checker
    )
    ranked: list[tuple[str, list[str]]] = sorted(_group(pairs).items(), key=lambda item: (-len(item[1]), item[0]))
    return [Variant(key, len(where), tuple(where)) for key, where in ranked]


def summarize(scans: Sequence[RepoScan]) -> Summary:
    """Group repositories by stack, configurations by fingerprint, and list missing checks.

    Args:
        scans: Every repository's scan.

    Returns:
        The summary.

    """
    checkers: list[str] = sorted({config.checker for scan in scans for config in scan.configs})
    configs: dict[str, list[Variant]] = {checker: _variants(scans, checker) for checker in checkers}
    return Summary(
        repositories=len(scans),
        stacks=_group((stack.name, scan.repo) for scan in scans for stack in scan.stacks),
        configs=configs,
        variant_counts={checker: len(variants) for checker, variants in configs.items()},
        gaps={scan.repo: list(scan.gaps) for scan in scans if scan.gaps},
        gaps_by_check=_group((gap, scan.repo) for scan in scans for gap in scan.gaps),
        code_stack_gaps=sorted({s.repo for s in scans for g in s.gaps if g.partition(":")[0] in CODE_STACKS}),
        errors={scan.repo: scan.error for scan in scans if scan.error},
    )


def summary_markdown(summary: Summary) -> str:
    """Render a summary as Markdown.

    Args:
        summary: The summary.

    Returns:
        The Markdown text.

    """
    copies: dict[str, int] = {name: sum(v.count for v in variants) for name, variants in summary.configs.items()}
    lines: list[str] = [f"# Repository stacks and checker configurations ({summary.repositories} repositories)", ""]
    lines += ["## Repositories per stack", "", "| Stack | Count | Repositories |", "|---|---|---|"]
    lines += [f"| {name} | {len(repos)} | {', '.join(repos)} |" for name, repos in summary.stacks.items()]
    lines += ["", "## Configuration variants per checker", "", "| Checker | Variants | Copies |", "|---|---|---|"]
    lines += [f"| {name} | {count} | {copies[name]} |" for name, count in summary.variant_counts.items()]
    for name, variants in summary.configs.items():
        lines += ["", f"### {name}", ""]
        lines += [f"- `{v.fingerprint}` ({v.count}): {', '.join(v.locations)}" for v in variants]
    lines += ["", "## Missing checks", "", "| Check | Repositories lacking it |", "|---|---|"]
    lines += [f"| {gap} | {len(repos)}: {', '.join(repos)} |" for gap, repos in summary.gaps_by_check.items()]
    lines += ["", f"Repositories lacking a check for a code stack they contain: {len(summary.code_stack_gaps)}"]
    lines += [f"- error in {repo}: {error}" for repo, error in summary.errors.items()]
    return "\n".join(lines) + "\n"


def scan_markdown(scan: RepoScan) -> str:
    """Render one repository's scan as text.

    Args:
        scan: The scan.

    Returns:
        The text.

    """
    lines: list[str] = [f"{scan.repo}  {scan.path}"]
    lines += [f"  error: {scan.error}"] if scan.error else []
    lines += [f"  stack {stack.name}{_languages(stack)}: {'; '.join(stack.evidence)}" for stack in scan.stacks]
    lines += [
        f"  config {c.checker} {c.path} {c.fingerprint or '-'} {' '.join(c.detail)}".rstrip() for c in scan.configs
    ]
    lines += [f"  missing: {', '.join(scan.gaps)}"] if scan.gaps else []
    return "\n".join(lines)


def _languages(stack: Stack) -> str:
    """Format a stack's languages for text output.

    Args:
        stack: The stack.

    Returns:
        ` (<languages>)`, or an empty string when the stack names none.

    """
    return f" ({', '.join(stack.languages)})" if stack.languages else ""
