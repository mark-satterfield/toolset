#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml>=0.18", "pyyaml>=6"]
# ///
"""polyrepo — live facts about the project's repositories, and the manifest kept true to them.

The repository folders and GitHub are the source of truth. Every fact this tool reports about
a repo (branch, uncommitted files, last commit, main against origin/main, GitHub state) is read
live from git and GitHub on each call, a repository's name included: a manifest entry records
GitHub's id of the repository, never its name, so a rename on GitHub leaves the record true. A
repository belongs to the project when the manifest records it or its clone is under the root.
The manifest contributes only what neither holds: tiers, groups and deprecation dates. What a
repository holds and why it exists is the matrix's: its stacks, with their purposes, read through
`atw-matrix` (`inventory` prints them), and this tool keeps the matrix's stacks true to the
repositories (`create`, `rename`, `deprecate`, `doctor`). `reconcile` compares disk, GitHub and
the manifest, and `reconcile --fix` repairs every mechanical finding: it rewrites the manifest,
pushes, creates or renames the GitHub repo so local and GitHub move together. The manifest keeps
no `owns`, `purpose`, `purpose_head`, `role` or `remote_url`; its next write drops them.

Settings come from `.polyrepo/config.yaml`, found in this order: `--config`, `$POLYREPO_CONFIG`,
the nearest `.polyrepo/config.yaml` above the working directory, `$SKILLSPOKE_CC/.polyrepo/`.
The repository root is the environment variable the config names in `root_env`.

Usage:
  polyrepo.py reconcile [--fix] [--dry-run] [--no-fetch]
  polyrepo.py status [repo ...] [--no-fetch]
  polyrepo.py list [--group G] [--lifecycle L] [--space S] [--include-inactive]
  polyrepo.py search attr=value [attr~regex ...] [--fetch] [--include-inactive]
  polyrepo.py inventory [--all] [--no-fetch] [--name N] [--include-inactive]
  polyrepo.py grep <pattern> [--space S] [--repo R ...] [-i] [-l] [-F] [-w] [--glob G ...]
  polyrepo.py rebase <repo ...|--all>
  polyrepo.py create <name> --space S [--template T] [--tier product|tooling] [--dry-run]
  polyrepo.py rename <repo> [<new-name>] [--also R ...] [--dry-run] [--skip-repo R ...] [--trailer TEXT]
                     [--pr-footer TEXT]
  polyrepo.py deprecate <repo> [--dry-run]
  polyrepo.py agents-sync [--check] [--dry-run] [--repo R ...] [--space S] [--trailer TEXT]
  polyrepo.py gitnexus-sync [--check] [--dry-run] [--repo R ...] [--space S]
  polyrepo.py naming <name>
  polyrepo.py tier <path>
  polyrepo.py tiers [--write]
  polyrepo.py set-tier <repo> product|tooling
  polyrepo.py templates-check
  polyrepo.py beads-setup [repo ...] [--space S] [--all] [--check] [--dry-run] [--trailer TEXT]
  polyrepo.py beads-fleet [--fix]
  polyrepo.py environment [repo ...] [--space S] [--fix]
  polyrepo.py python-names [repo ...] [--space S]
  polyrepo.py deprecated-prs [--fix]
  polyrepo.py archive-due [--dry-run]
  polyrepo.py doctor [--fix]
  polyrepo.py commit --message TEXT

A command that changes the steward's own files (manifest, knowledge store) commits and pushes
them itself, on the default branch of the repo that holds them, with a message that says what
changed; `commit` does the same after a hand edit. A line in the environment variable
POLYREPO_COMMIT_TRAILER ends the message of every commit the tool makes.

The tiers are defined in the project's root AGENTS.md ("Code quality"). The manifest records, for
every repository, whether it holds product code: `product` (its product files are tier 1:
worktrees and a pull request) or `tooling` (the repository is tier 2 throughout). `tier <path>`
says which the repository containing a path is, and the tier export
(`.polyrepo/repository-tiers.json`, path to `product` or `tooling`) is rewritten with every
records commit, for the hooks that read it. `agents-sync` writes AGENTS.md, which is tier 2 in
every repository, so it commits on `main` whatever the repository's recorded tier.

Every command takes --json (one JSON object on stdout) and --no-cache (ignore the fetch and
GitHub-listing freshness window). Exit status: 0 success, 1 findings remain (reconcile, a
repo left out of date by agents-sync or rebase, a template that lags), 2 usage or environment
error. grep follows rg: 0 matches, 1 no match, 2 error.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import fnmatch
import functools
import hashlib
import json
import operator
import os
import re
import shlex
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - the tool runs git, gh and bd with list argv and no shell
import sys
import tempfile
import time
from collections.abc import (
    Callable,  # ruff: ignore[typing-only-standard-library-import] - typing.get_type_hints resolves Finding.action at runtime
)
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline-contracts" / "scripts"))
from driver_surface_types import CONTROL_REPO_ENV
from name_sweep import (
    NameChange,
    NameSweepError,
    SweepTarget,
    adjust_pyproject,
    apply_moves,
    build_document_rules,
    build_rules,
    change_label,
    normalize,
    parse_repo_name,
    plan_changes,
    planned_moves,
    python_problems,
    read_facts,
    stack_module,
    sweep_repo,
)
from naming_rules import NamingPattern, NamingRules, NamingRulesError, read_rules, type_of

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from name_sweep import Checker, FileEdit, FileMove, Namer, Rule

GIT_TIMEOUT = 60
FETCH_TIMEOUT = 45
WORKERS = 16
LIFECYCLES_INACTIVE = ("deprecated", "archived")
RETIRED_FIELDS = (
    "owns", "purpose", "purpose_head", "role", "owner", "language", "notes", "default_branch", "remote_url",
)  # fmt: skip
ENTRY_ID = "id"
ENTRY_NAME = "name"
RETIRED_SECTIONS = ("conventions", "ownership", "relationships")
RETIRED_PROJECT_FIELDS = ("purpose", "owners")
ENTRY_LISTS = ("repos", "deprecations")
WORKTREES_LINE = ".worktrees/"
OPEN_ITEM_SECTIONS = ("drift_log", "open_questions")
PLUGIN_ROOT = Path(__file__).resolve().parents[3]
FILES_SHOWN = 5
EXIT_USAGE = 2
TIER_PRODUCT = "product"
TIER_TOOLING = "tooling"
TIERS = (TIER_PRODUCT, TIER_TOOLING)
TIER_EXPORT_FILE = "repository-tiers.json"
COMMIT_TRAILER_ENV = "POLYREPO_COMMIT_TRAILER"


class PolyrepoError(Exception):
    """An environment or usage error the tool cannot work around."""


class GhRepo(TypedDict):
    """One GitHub repository of the owner, as the tool records it; `id` is GitHub's node id, which a rename keeps."""

    id: str
    name: str
    archived: bool
    pushed_at: str | None
    url: str | None
    visibility: str | None


type PrCloseStatus = Literal["planned", "closed", "failed"]


class EnvResult(TypedDict):
    """What setting up a repo's environment did, and the problems that remain."""

    steps: list[str]
    problems: list[str]


@dataclasses.dataclass(frozen=True, slots=True)
class PullRequest:
    """One open pull request, as gh reports it."""

    repo: str
    number: int
    title: str
    url: str


@dataclasses.dataclass(frozen=True, slots=True)
class Worktree:
    """One linked worktree of a clone."""

    path: Path
    locked: bool
    prunable: bool


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateComparison:
    """One repo's files compared with its template's render: (state, repo commit time) by path."""

    repo: str
    files: dict[str, tuple[str, int | None]]
    error: str | None


class TemplateFileRow(TypedDict):
    """How one template file compares across the repos built from the template."""

    file: str
    same: int
    missing: list[str]
    repo_newer: list[str]
    template_newer: list[str]


class TemplateMember(TypedDict):
    """A repo built from a template, and how that was decided."""

    repo: str
    matched_by: str


class RenderError(TypedDict):
    """A repo the template could not be rendered for."""

    repo: str
    error: str


class TemplateReport(TypedDict):
    """The templates-check result for one template."""

    template: str
    repos: list[TemplateMember]
    render_errors: list[RenderError]
    files: list[TemplateFileRow]
    lags: bool


class KindWithoutTemplate(TypedDict):
    """A repo kind no template builds, and its repos."""

    kind: str
    repos: list[str]


class DoctorFinding(TypedDict):
    """One problem the doctor reports."""

    check: str
    subject: str
    kind: str
    detail: str


def _opt_str(value: object, what: str) -> str | None:
    """Narrow an optional string read from external data.

    Returns:
        The string, or None.

    Raises:
        PolyrepoError: when the value is neither a string nor None.

    """
    if value is None or isinstance(value, str):
        return value
    msg = f"{what} is {type(value).__name__}, not a string"
    raise PolyrepoError(msg)


def _map(value: object, what: str) -> dict[str, object]:
    """Narrow a record value to a string-keyed mapping.

    Returns:
        A dict with the value's string keys.

    Raises:
        PolyrepoError: when the value is not a mapping.

    """
    if not isinstance(value, dict):
        msg = f"{what} is {type(value).__name__}, not a mapping"
        raise PolyrepoError(msg)
    pairs: list[tuple[object, object]] = list(value.items())
    return {k: v for k, v in pairs if isinstance(k, str)}


def _seq(value: object, what: str) -> list[object]:
    """Narrow a record value to a list.

    Returns:
        A list of the value's items.

    Raises:
        PolyrepoError: when the value is not a list or tuple.

    """
    if not isinstance(value, (list, tuple)):
        msg = f"{what} is {type(value).__name__}, not a list"
        raise PolyrepoError(msg)
    items: list[object] = list(value)
    return items


def _strs(value: object, what: str) -> list[str]:
    """Narrow a record value to a list of strings.

    Returns:
        The strings.

    Raises:
        PolyrepoError: when the value is not a list of strings.

    """
    out: list[str] = []
    for item in _seq(value, what):
        if not isinstance(item, str):
            msg = f"{what} holds {type(item).__name__}, not a string"
            raise PolyrepoError(msg)
        out.append(item)
    return out


def _str(value: object, what: str) -> str:
    """Narrow a record value to a string.

    Returns:
        The string.

    Raises:
        PolyrepoError: when the value is not a string.

    """
    if not isinstance(value, str):
        msg = f"{what} is {type(value).__name__}, not a string"
        raise PolyrepoError(msg)
    return value


def _int(value: object, what: str) -> int:
    """Narrow a record value to an int.

    Returns:
        The integer.

    Raises:
        PolyrepoError: when the value is not an int.

    """
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"{what} is {type(value).__name__}, not an int"
        raise PolyrepoError(msg)
    return value


def parse_pull_request(value: object, repo: str, what: str) -> PullRequest:
    """Validate one pull request entry from gh's JSON; a malformed entry raises PolyrepoError.

    Returns:
        The pull request.

    """
    pr = _map(value, f"{what} entry")
    return PullRequest(
        repo=repo,
        number=_int(pr.get("number"), f"{what} number"),
        title=_str(pr.get("title"), f"{what} title"),
        url=_str(pr.get("url"), f"{what} url"),
    )


def parse_gh_repo(value: object) -> GhRepo:
    """Validate one cached GitHub repo record.

    Returns:
        The record.

    Raises:
        PolyrepoError: when the record is not a mapping or a field has the wrong type.

    """
    if not isinstance(value, dict):
        msg = f"GitHub record {value!r} is not a mapping"
        raise PolyrepoError(msg)
    rid: object = value.get("id")
    name: object = value.get("name")
    archived: object = value.get("archived", False)
    if not isinstance(rid, str) or not isinstance(name, str) or not isinstance(archived, bool):
        msg = f"GitHub record {value!r} lacks a string id, a string name or a boolean archived"
        raise PolyrepoError(msg)
    return GhRepo(
        id=rid,
        name=name,
        archived=archived,
        pushed_at=_opt_str(value.get("pushed_at"), "GitHub pushed_at"),
        url=_opt_str(value.get("url"), "GitHub url"),
        visibility=_opt_str(value.get("visibility"), "GitHub visibility"),
    )


# --------------------------------------------------------------------------------------------
# process helpers


def run(
    argv: list[str],
    cwd: Path | None = None,
    timeout: int = GIT_TIMEOUT,
    env: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with captured text output and no shell.

    `env` overrides variables of the inherited environment; a value of None removes one.

    Returns:
        The completed process; a timeout comes back as returncode 124.

    """
    base: dict[str, str] = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    for k, v in (env or {}).items():
        if v is None:
            base.pop(k, None)
        else:
            base[k] = v
    try:
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - list argv built by this tool, no shell
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=base,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, "", f"timed out after {timeout}s")


def git(
    repo: Path,
    *args: str,
    timeout: int = GIT_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Run git in a repository.

    Returns:
        The completed process.

    """
    return run(["git", "-C", str(repo), *args], timeout=timeout)


def git_out(repo: Path, *args: str) -> str | None:
    """Run git and return stripped stdout, or None when git fails.

    Returns:
        The stripped output, or None.

    """
    cp = git(repo, *args)
    return cp.stdout.strip() if cp.returncode == 0 else None


def _last_line(cp: subprocess.CompletedProcess[str]) -> str:
    lines = (cp.stderr or cp.stdout or "").strip().splitlines()
    return lines[-1] if lines else f"exit {cp.returncode}"


def expand_env(text: str, extra: dict[str, str] | None = None) -> str:
    """Replace $VAR and ${VAR} with the environment's values; unknown names are left as written.

    Returns:
        The expanded text.

    """
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), **(extra or {})}
    return re.sub(
        r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?",
        lambda m: env.get(m.group(1), m.group(0)),
        text,
    )


def fetch_origin(repo: Path) -> str | None:
    """Fetch origin, pruning deleted branches.

    Returns:
        None on success, else the last line of git's error.

    """
    cp = git(repo, "fetch", "--quiet", "--prune", "origin", timeout=FETCH_TIMEOUT)
    return None if cp.returncode == 0 else _last_line(cp)


def main_vs_origin(
    repo: Path,
    branch: str,
) -> tuple[str | None, str | None, int | None, int | None]:
    """Compare the local default branch with its origin copy, as last fetched.

    Returns:
        (main sha, origin/main sha, commits ahead, commits behind); the counts are None
        unless both branches exist.

    """
    main = git_out(repo, "rev-parse", "--verify", "-q", f"refs/heads/{branch}")
    om = git_out(repo, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}")
    if not main or not om:
        return main, om, None, None
    counts = git_out(
        repo,
        "rev-list",
        "--left-right",
        "--count",
        f"refs/heads/{branch}...refs/remotes/origin/{branch}",
    )
    if not counts:
        return main, om, None, None
    a, b = counts.split()
    return main, om, int(a), int(b)


# --------------------------------------------------------------------------------------------
# configuration


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


@dataclasses.dataclass
class Config:
    """Project settings resolved from `.polyrepo/config.yaml` and the environment."""

    file: Path
    root: Path
    manifest: Path
    knowledge: Path
    owner: str
    default_branch: str
    max_depth: int
    exclude_dirs: set[str]
    exclude_names: set[str]
    ttl: int
    raw: dict[str, object] = dataclasses.field(default_factory=dict)
    changes: list[str] = dataclasses.field(default_factory=list)
    change_lines: list[str] = dataclasses.field(default_factory=list)
    types_cache: tuple[str, ...] | None = None
    rules_cache: NamingRules | None = None

    @property
    def rules(self) -> NamingRules:
        """The repository naming rules, read once per run from the vault's naming note.

        The note is `naming.document` under `naming.document_root` in the config. The tool keeps
        no copy of its rules.

        Returns:
            The rules the note states.

        Raises:
            PolyrepoError: when the config does not point at the note, or the note cannot be read
                or does not state a rule the tool needs.

        """
        if self.rules_cache is None:
            try:
                self.rules_cache = read_rules(self.naming_note())
            except NamingRulesError as exc:
                raise PolyrepoError(str(exc)) from exc
        return self.rules_cache

    def naming_note(self) -> Path:
        """Resolve the path of the repository naming note from the config.

        Returns:
            The path `naming.document` names under `naming.document_root`.

        Raises:
            PolyrepoError: when the config names no document.

        """
        section = _map(self.raw.get("naming") or {}, "config naming")
        document, root = section.get("document"), section.get("document_root")
        if not document:
            msg = "config naming.document does not point at the repository naming note"
            raise PolyrepoError(msg)
        base = Path(expand_env(str(root))).expanduser() if root else self.file.parent
        return base / str(document)

    def _placement(self) -> dict[str, object]:
        """Return the config's `placement` section.

        Returns:
            The section; empty when the config has none.

        """
        return _map(self.raw.get("placement") or {}, "config placement")

    def placement_folder(self, space: str, name: str) -> str:
        """Return the folder inside an app space where a repository of this name is placed.

        A space the config's `placement.by_type` lists places each repository one folder deeper,
        in the folder its type (the last token of its name) maps to; every other space holds its
        repositories directly.

        Returns:
            The folder, empty when the space holds its repositories directly.

        Raises:
            PolyrepoError: when the space places by type and the config maps no folder to this type.

        """
        by_type = _map(self._placement().get("by_type") or {}, "config placement.by_type")
        if space not in by_type:
            return ""
        folders = _map(by_type[space], f"config placement.by_type.{space}")
        repo_type = type_of(name)
        folder = folders.get(repo_type)
        if not isinstance(folder, str) or not folder:
            msg = (
                f"config placement.by_type.{space} maps a folder only to the types {', '.join(folders)}; "
                f"it maps none to the type {repo_type!r} of {name}"
            )
            raise PolyrepoError(msg)
        return folder

    def stack_type_names(self) -> tuple[str, ...]:
        """Return the stack types a repository name's last token may be, read once per run.

        Returns:
            The types the project's naming rules list.

        """
        if self.types_cache is None:
            self.types_cache = stack_types(self)
        return self.types_cache

    def archive_after_days(self) -> int:
        """Return the days from deprecating to archiving a repo (config `deprecation.archive_after_days`).

        Returns:
            The number of days.

        Raises:
            PolyrepoError: when the config does not state a positive number of days.

        """
        days = _map(self.raw.get("deprecation") or {}, "config deprecation").get("archive_after_days")
        if not isinstance(days, int) or isinstance(days, bool) or days < 1:
            msg = "config deprecation.archive_after_days does not state a positive number of days"
            raise PolyrepoError(msg)
        return days

    def setting_path(self, section: str, key: str, default: str) -> Path:
        """Resolve a path setting, relative to the config file's folder.

        Returns:
            The absolute path.

        """
        rel = _map(self.raw.get(section) or {}, f"config {section}").get(key) or default
        return (self.file.parent / str(rel)).resolve()

    def classify(self, name: str) -> NamingPattern | None:
        """Return the first pattern of the naming note that the name matches.

        An application name must also end in a repository type the note lists (`service`,
        `infra`, `lib`, ...): `SkillSpoke-auth-utils` is refused.

        Returns:
            The pattern, or None when no pattern matches or the last token is no listed type.

        """
        return self.rules.classify(name)

    def naming_problem(self, name: str) -> str:
        """Say why a name is refused: no pattern of the naming note matches, or its last token is no listed type.

        Returns:
            One sentence naming the rule the name breaks.

        """
        return self.rules.problem(name)

    def is_deprecated_name(self, name: str) -> bool:
        """Tell whether a repo name carries the deprecated prefix the naming note gives.

        Returns:
            True when the name starts with the prefix.

        """
        return self.rules.is_deprecated(name)

    def expected_space(self, name: str) -> str:
        """Return the app space a repo of this name lives in; a deprecated repo keeps its space.

        The space is the folder under the root named by the first token of the name (of a
        deprecated name, after the deprecated prefix), or the folder the config's
        `placement.spaces` maps that token to; tokens are compared without case.

        Returns:
            The space name.

        """
        base = self.rules.deprecated_base(name) if self.is_deprecated_name(name) else name
        token = base.partition("-")[0]
        spaces = _map(self._placement().get("spaces") or {}, "config placement.spaces")
        mapped = next((v for k, v in spaces.items() if k.lower() == token.lower()), None)
        return mapped if isinstance(mapped, str) and mapped else token

    def github_url(self, name: str) -> str:
        """Return the canonical clone URL for a repo name.

        Returns:
            The https URL ending in .git.

        """
        return f"https://github.com/{self.owner}/{name}.git"


def find_config(explicit: str | None) -> Path:
    """Locate the config file.

    Returns:
        The config path.

    Raises:
        PolyrepoError: when no config file can be found.

    """
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("POLYREPO_CONFIG"):
        candidates.append(Path(os.environ["POLYREPO_CONFIG"]))
    here = Path.cwd().resolve()
    candidates.extend(d / ".polyrepo" / "config.yaml" for d in (here, *here.parents))
    if os.environ.get("SKILLSPOKE_CC"):
        candidates.append(
            Path(os.environ["SKILLSPOKE_CC"]) / ".polyrepo" / "config.yaml",
        )
    for c in candidates:
        if c.is_file():
            return c.resolve()
    msg = "no .polyrepo/config.yaml found (pass --config or set POLYREPO_CONFIG)"
    raise PolyrepoError(msg)


def load_config(explicit: str | None) -> Config:
    """Load and resolve the project settings.

    Returns:
        The resolved Config.

    Raises:
        PolyrepoError: when the root environment variable is unset or not a folder.

    """
    f = find_config(explicit)
    raw = YAML(typ="safe").load(f.read_text()) or {}
    env_name = raw.get("root_env", "")
    root_val = os.environ.get(env_name, "")
    if not root_val:
        msg = f"environment variable {env_name!r} (config root_env) is not set"
        raise PolyrepoError(msg)
    root = Path(root_val).expanduser().resolve()
    if not root.is_dir():
        msg = f"${env_name} = {root} is not a folder"
        raise PolyrepoError(msg)
    return Config(
        file=f,
        root=root,
        manifest=f.parent / raw.get("manifest", "manifest.yaml"),
        knowledge=f.parent / raw.get("knowledge", "knowledge.yaml"),
        owner=raw["github_owner"],
        default_branch=raw.get("default_branch", "main"),
        max_depth=int(raw.get("max_depth", 4)),
        exclude_dirs=set((raw.get("exclude") or {}).get("dirs") or []),
        exclude_names=set((raw.get("exclude") or {}).get("names") or []),
        ttl=int(raw.get("cache_ttl_seconds", 300)),
        raw=raw,
    )


# --------------------------------------------------------------------------------------------
# disk


@dataclasses.dataclass
class LocalRepo:
    """A git repository found on disk under the root."""

    name: str
    path: Path
    space: str
    origin_url: str | None = None
    branch: str | None = None
    uncommitted: int = 0
    uncommitted_files: list[str] = dataclasses.field(default_factory=list)
    head_sha: str | None = None
    head_date: str | None = None
    head_subject: str | None = None
    main_sha: str | None = None
    origin_main_sha: str | None = None
    ahead: int | None = None
    behind: int | None = None
    fetched_at: str | None = None
    fetch_error: str | None = None


def discover(cfg: Config) -> tuple[dict[str, LocalRepo], list[tuple[str, list[Path]]]]:
    """Find every primary git clone under the root.

    Returns:
        The repos by name, and any names found at more than one path.

    """
    found: dict[str, list[LocalRepo]] = {}

    def walk(d: Path, depth: int) -> None:
        try:
            entries = sorted(d.iterdir())
        except OSError:
            return
        for e in entries:
            if not e.is_dir() or e.name.startswith(".") or e.name in cfg.exclude_dirs:
                continue
            if (e / ".git").is_dir():
                if e.name not in cfg.exclude_names and depth > 1:
                    space = e.relative_to(cfg.root).parts[0]
                    found.setdefault(e.name, []).append(LocalRepo(e.name, e, space))
                continue
            if depth < cfg.max_depth:
                walk(e, depth + 1)

    walk(cfg.root, 1)
    repos = {n: rs[0] for n, rs in found.items()}
    dups = [(n, [r.path for r in rs]) for n, rs in found.items() if len(rs) > 1]
    return repos, dups


def fetch_is_fresh(repo: Path, ttl: int) -> bool:
    """Tell whether the repo was fetched within the freshness window.

    Returns:
        True when FETCH_HEAD is younger than ttl seconds.

    """
    fh = repo / ".git" / "FETCH_HEAD"
    return fh.exists() and time.time() - fh.stat().st_mtime < ttl


def collect_local(r: LocalRepo, cfg: Config, fetch: bool, use_cache: bool) -> LocalRepo:
    """Fill a LocalRepo with live git facts, fetching origin first when asked.

    Returns:
        The same LocalRepo, filled in.

    """
    r.origin_url = git_out(r.path, "remote", "get-url", "origin")
    if fetch and r.origin_url and not (use_cache and fetch_is_fresh(r.path, cfg.ttl)):
        r.fetch_error = fetch_origin(r.path)
    fh = r.path / ".git" / "FETCH_HEAD"
    if fh.exists():
        r.fetched_at = dt.datetime.fromtimestamp(fh.stat().st_mtime, dt.UTC).isoformat(
            timespec="seconds",
        )
    r.branch = git_out(r.path, "symbolic-ref", "--short", "-q", "HEAD") or "(detached)"
    porcelain = git(r.path, "status", "--porcelain=v1", "--untracked-files=normal")
    r.uncommitted_files = [ln[3:] for ln in porcelain.stdout.splitlines() if porcelain.returncode == 0 and ln.strip()]
    r.uncommitted = len(r.uncommitted_files)
    log = git_out(r.path, "log", "-1", "--format=%H%x1f%cI%x1f%s")
    if log:
        r.head_sha, r.head_date, r.head_subject = log.split("\x1f", 2)
    r.main_sha, r.origin_main_sha, r.ahead, r.behind = main_vs_origin(
        r.path,
        cfg.default_branch,
    )
    return r


def collect_all_local(
    repos: dict[str, LocalRepo],
    cfg: Config,
    fetch: bool,
    use_cache: bool,
) -> None:
    """Collect live git facts for every repo in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(lambda r: collect_local(r, cfg, fetch, use_cache), repos.values()))


def parse_github_url(url: str | None) -> tuple[str, str] | None:
    """Split a GitHub remote URL into owner and repo name.

    Returns:
        (owner, name), or None when the URL is not a GitHub URL.

    """
    if not url:
        return None
    m = re.match(
        r"^(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+)/(.+?)(?:\.git)?/?$",
        url,
    )
    return (m.group(1), m.group(2)) if m else None


# --------------------------------------------------------------------------------------------
# GitHub


class GitHub:
    """The owner's GitHub repos, listed once per freshness window, plus rename resolution."""

    def __init__(self, cfg: Config, use_cache: bool) -> None:
        """Load the listing from cache or GitHub."""
        self.cfg = cfg
        key = hashlib.sha256(str(cfg.file).encode()).hexdigest()[:16]
        cache_home = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        self.cache_file = cache_home / "polyrepo" / key / "github.json"
        self._resolved: dict[str, GhRepo | None] = {}
        self.repos = self._load(use_cache)
        self.lower = {n.lower(): n for n in self.repos}
        self.ids = {r["id"]: n for n, r in self.repos.items()}

    def _load(self, use_cache: bool) -> dict[str, GhRepo]:
        if use_cache and self.cache_file.exists() and time.time() - self.cache_file.stat().st_mtime < self.cfg.ttl:
            cached: object = json.loads(self.cache_file.read_text())
            if not isinstance(cached, dict):
                msg = f"{self.cache_file} does not hold a mapping"
                raise PolyrepoError(msg)
            if all(isinstance(v, dict) and v.get("id") for v in cached.values()):
                return {str(k): parse_gh_repo(v) for k, v in cached.items()}
        cp = run(
            [
                "gh", "repo", "list", self.cfg.owner, "--limit", "2000",
                "--json", "id,name,isArchived,pushedAt,url,visibility",
            ],
            timeout=120,
        )  # fmt: skip
        if cp.returncode != 0:
            msg = f"gh repo list {self.cfg.owner} failed: {cp.stderr.strip()}"
            raise PolyrepoError(msg)
        listing: object = json.loads(cp.stdout)
        if not isinstance(listing, list):
            msg = f"gh repo list {self.cfg.owner} did not return a list"
            raise PolyrepoError(msg)
        repos: dict[str, GhRepo] = {}
        for r in listing:
            if not isinstance(r, dict):
                msg = f"gh repo list {self.cfg.owner} returned a non-mapping entry {r!r}"
                raise PolyrepoError(msg)
            visibility = _opt_str(r.get("visibility"), "GitHub visibility")
            rec = parse_gh_repo(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "archived": r.get("isArchived"),
                    "pushed_at": r.get("pushedAt"),
                    "url": r.get("url"),
                    "visibility": visibility.lower() if visibility is not None else None,
                },
            )
            repos[rec["name"]] = rec
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(repos))
        return repos

    def invalidate(self) -> None:
        """Drop the cached listing so the next call lists GitHub again."""
        self.cache_file.unlink(missing_ok=True)

    def get(self, name: str) -> GhRepo | None:
        """Look a repo up by exact or case-insensitive name in the listing.

        Returns:
            The repo record, or None.

        """
        n = self.lower.get(name.lower())
        return self.repos.get(n) if n else None

    def resolve(self, name: str) -> GhRepo | None:
        """Resolve a name through GitHub's rename redirects.

        Returns:
            The current record of the repo the name leads to, or None when none exists.

        Raises:
            PolyrepoError: when GitHub's answer is not a repository mapping.

        """
        if name in self._resolved:
            return self._resolved[name]
        rec = self.get(name)
        if rec is None:
            cp = run(["gh", "api", f"repos/{self.cfg.owner}/{name}"], timeout=60)
            if cp.returncode == 0:
                d: object = json.loads(cp.stdout)
                if not isinstance(d, dict):
                    msg = f"gh api repos/{self.cfg.owner}/{name} did not return a mapping"
                    raise PolyrepoError(msg)
                owner: object = d.get("owner")
                login: object = owner.get("login", "") if isinstance(owner, dict) else ""
                if isinstance(login, str) and login.lower() == self.cfg.owner.lower():
                    gh_name: object = d.get("name")
                    found = self.get(gh_name) if isinstance(gh_name, str) else None
                    rec = found or parse_gh_repo(
                        {
                            "id": d.get("node_id"),
                            "name": gh_name,
                            "archived": d.get("archived", False),
                            "pushed_at": d.get("pushed_at"),
                            "url": d.get("html_url"),
                            "visibility": d.get("visibility"),
                        },
                    )
        self._resolved[name] = rec
        return rec

    def by_id(self, rid: str) -> GhRepo | None:
        """Look a repo up by GitHub's id in the listing.

        Returns:
            The repo record, or None when the owner has no repo with that id.

        """
        n = self.ids.get(rid)
        return self.repos.get(n) if n else None

    def id_of(self, name: str) -> str | None:
        """Return GitHub's id of the repo a name leads to, following GitHub's rename redirects.

        Returns:
            The id, or None when no repo of the owner has the name.

        """
        rec = self.resolve(name)
        return rec["id"] if rec else None

    def note_rename(self, old: str, new: str) -> None:
        """Rename a repo in the listing this run holds, after it was renamed on GitHub."""
        rec = self.repos.pop(old, None)
        if rec is None:
            return
        rec = GhRepo(**{**rec, "name": new})
        self.repos[new] = rec
        self.lower = {n.lower(): n for n in self.repos}
        self.ids[rec["id"]] = new
        self._resolved = {}


# --------------------------------------------------------------------------------------------
# manifest


def entry_key(e: Mapping[str, object]) -> str:
    """Return the key a manifest entry records: GitHub's id, or the name of a repository not on GitHub.

    Returns:
        The key.

    """
    return str(e.get(ENTRY_ID) or e.get(ENTRY_NAME))


class Manifest:
    """The steward's manifest, read and written with comments and layout preserved.

    An entry records GitHub's id of its repository (`id`), never the name: the name is read live
    from the GitHub listing on every call. Only an entry whose repository is not on GitHub yet (a
    planned repository) records a `name`, the steward's own fact. A group member is the key its
    entry records: the id, or the name of a planned repository.
    """

    def __init__(self, path: Path, gh: GitHub) -> None:
        """Load the manifest; a missing file starts an empty one."""
        self.path = path
        self.gh = gh
        self.yaml = _yaml()
        self.doc: CommentedMap = self.yaml.load(path.read_text(encoding="utf-8")) if path.exists() else CommentedMap()
        if self.doc.get("repos") is None:
            self.doc["repos"] = []
        self.dirty = False

    def _all(self) -> list[CommentedMap]:
        """Return every entry, from `repos` and from the `deprecations` list.

        Returns:
            The entries in file order.

        """
        return [e for key in ENTRY_LISTS for e in self.doc.get(key) or [] if isinstance(e, CommentedMap)]

    def _label(self, e: Mapping[str, object]) -> str | None:
        """Return the name an entry is known by: its repository's live GitHub name, or its own name.

        An entry whose id GitHub no longer has is labelled `id <id>`, so it can be reported.

        Returns:
            The label, or None for an entry that records neither an id nor a name.

        """
        rid = e.get(ENTRY_ID)
        if rid:
            rec = self.gh.by_id(str(rid))
            return rec["name"] if rec else f"{ENTRY_ID} {rid}"
        name = e.get(ENTRY_NAME)
        return str(name) if name else None

    def entries(self) -> dict[str, CommentedMap]:
        """Return the repo entries by the name each is known by (`label`); a later duplicate is left out.

        Returns:
            A name → entry mapping.

        """
        out: dict[str, CommentedMap] = {}
        for e in self._all():
            name = self._label(e)
            if name is not None:
                out.setdefault(name, e)
        return out

    def duplicates(self) -> list[tuple[str, CommentedMap]]:
        """Return each entry that records the same repository as an earlier one.

        Returns:
            (the name, the later entry) for each duplicate.

        """
        seen: set[str] = set()
        out: list[tuple[str, CommentedMap]] = []
        for e in self._all():
            name = self._label(e)
            if name is None:
                continue
            if name in seen:
                out.append((name, e))
            seen.add(name)
        return out

    def is_unresolved(self, e: Mapping[str, object]) -> bool:
        """Tell whether an entry records an id the owner's GitHub repositories no longer have.

        Returns:
            True when the entry has an id and GitHub has no repo with it.

        """
        rid = e.get(ENTRY_ID)
        return bool(rid) and self.gh.by_id(str(rid)) is None

    def member_name(self, member: str) -> str | None:
        """Return the live name of a group member, which is an entry's key.

        Returns:
            The repository's GitHub name for an id, the member itself for a name, None for an id GitHub does not have.

        """
        rec = self.gh.by_id(member)
        if rec is not None:
            return rec["name"]
        return None if any(e.get(ENTRY_ID) == member for e in self._all()) else member

    def groups(self) -> list[CommentedMap]:
        """Return the group mappings.

        Returns:
            Every group with a name.

        """
        return [g for g in self.doc.get("groups") or [] if isinstance(g, CommentedMap) and g.get("name")]

    def has_stored_dependencies(self) -> bool:
        """Say whether the manifest holds repo-to-repo dependency edges, which it may not.

        Returns:
            True when `relationships.dependencies` is present and not empty.

        """
        rel = self.doc.get("relationships") or {}
        return bool(rel.get("dependencies"))

    def drop_stored_dependencies(self) -> None:
        """Remove the `relationships.dependencies` field."""
        rel = self.doc.get("relationships")
        if rel is not None and "dependencies" in rel:
            del rel["dependencies"]
            self.dirty = True

    def groups_of(self, name: str) -> list[str]:
        """Return the groups a repo is a member of.

        Returns:
            Group names.

        """
        e = self.entries().get(name)
        if e is None:
            return []
        key = entry_key(e)
        return [g["name"] for g in self.groups() if key in (g.get("members") or [])]

    def add_entry(self, name: str, fields: dict[str, object]) -> None:
        """Append a new repo entry keyed by GitHub's id; for an entry that exists, fill only the fields it lacks.

        A repository GitHub does not have is keyed by its name.
        """
        rid = self.gh.id_of(name)
        rec = self.gh.by_id(rid) if rid else None
        e = self.entries().get(rec["name"] if rec else name)
        if e is None and rid:
            e = next((x for x in self._all() if x.get(ENTRY_ID) == rid), None)
        if e is not None:
            for k, v in fields.items():
                if e.get(k) is None:
                    e[k] = v
                    self.dirty = True
            return
        m = CommentedMap()
        if rid:
            m[ENTRY_ID] = rid
        else:
            m[ENTRY_NAME] = name
        for k, v in fields.items():
            m[k] = v
        self.doc["repos"].append(m)
        self.dirty = True

    def key_entry(self, name: str) -> None:
        """Record GitHub's id on an entry that records a name, and drop the name.

        Raises:
            PolyrepoError: when GitHub has no repository of that name.

        """
        e = self.entries()[name]
        rid = self.gh.id_of(name)
        if rid is None:
            msg = f"GitHub has no repository {name}"
            raise PolyrepoError(msg)
        e.pop(ENTRY_NAME, None)
        e.insert(0, ENTRY_ID, rid)
        for g in self.groups():
            members = g.get("members")
            if members and name in members:
                members[members.index(name)] = rid
        self.dirty = True

    def set_member(self, group: str, member: str, new: str | None) -> None:
        """Replace a group member's key, or remove the member when new is None."""
        for g in self.groups():
            members = g.get("members")
            if g["name"] == group and members and member in members:
                if new is None:
                    members.remove(member)
                else:
                    members[members.index(member)] = new
                self.dirty = True

    def remove_section(self, key: str) -> None:
        """Remove a top-level section."""
        if key in self.doc:
            del self.doc[key]
            self.dirty = True

    def drop_retired_project_fields(self) -> None:
        """Remove the `project` fields the manifest no longer keeps (`RETIRED_PROJECT_FIELDS`)."""
        project = self.doc.get("project")
        if project is None:
            return
        for key in RETIRED_PROJECT_FIELDS:
            if key in project:
                del project[key]
                self.dirty = True

    def set_field(self, name: str, key: str, value: object, after: str | None = None) -> None:
        """Set one field on an entry; None removes the field.

        A new field is placed after the field `after` names when the entry has it.
        """
        e = self.entries()[name]
        if value is None:
            e.pop(key, None)
        elif key not in e and after in e:
            e.insert(list(e).index(after) + 1, key, value)
        else:
            e[key] = value
        self.dirty = True

    def remove_entry(self, name: str) -> None:
        """Remove an entry and its group memberships."""
        self.drop_entry(self.entries()[name])

    def drop_entry(self, entry: CommentedMap) -> None:
        """Remove this entry object, and the group memberships of its key when no other entry records it."""
        for key in ENTRY_LISTS:
            items = self.doc.get(key)
            if items:
                keep = [e for e in items if e is not entry]
                items.clear()
                items.extend(keep)
        k = entry_key(entry)
        if not any(entry_key(e) == k for e in self._all()):
            for g in self.groups():
                members = g.get("members")
                if members and k in members:
                    members.remove(k)
        self.dirty = True

    def rename_entry(self, old: str, new: str) -> None:
        """Rename an entry that records a name; an entry keyed by GitHub's id needs no change."""
        e = self.entries()[old]
        if e.get(ENTRY_ID):
            return
        e[ENTRY_NAME] = new
        for g in self.groups():
            members = g.get("members")
            if members and old in members:
                members[members.index(old)] = new
        self.dirty = True

    def drop_retired_fields(self) -> None:
        """Remove the fields the manifest no longer keeps (`RETIRED_FIELDS`) from every entry.

        An entry keyed by GitHub's id keeps no name: the name is read live.
        """
        for e in self._all():
            for key in RETIRED_FIELDS:
                e.pop(key, None)
            if e.get(ENTRY_ID):
                e.pop(ENTRY_NAME, None)

    def save(self) -> None:
        """Write the manifest back when it changed, without the retired fields."""
        if self.dirty:
            self.drop_retired_fields()
            with self.path.open("w") as fh:
                self.yaml.dump(self.doc, fh)
            self.dirty = False


# --------------------------------------------------------------------------------------------
# the matrix: the stacks a repository holds, and why. The matrix is read and changed only
# through `atw-matrix`; this tool keeps its stacks true to the repositories (S1 to S3, S6).

MATRIX_COMMAND = PLUGIN_ROOT / "bin" / "atw-matrix"
MATRIX_ROLE = "repository-steward"
MATRIX_ROLE_ENV = "ATW_MATRIX_ROLE"
MATRIX_FILE_ENV = "ATW_MATRIX"
MATRIX_TIMEOUT = 300
NAMING_RULES_ENV = "RESOURCE_NAMING_CONFIG"
NAMING_RULES_FILE = ".resource-naming.yaml"
STACK_NAME_SEPARATOR = "-"
LIBRARY_STACK_TYPE = "lib"
EXECUTION_IMPORTED = "imported"
EXECUTION_EXECUTABLE = "executable"
PURPOSE_NOT_STATED = "The purpose is not stated."
CHECK_PROBLEMS_SHOWN = 5
HELD_KEYS = ("id", "kind", "name", "side")


@dataclasses.dataclass(frozen=True, slots=True)
class MatrixStack:
    """One stack the matrix holds, as `atw-matrix stacks` returns it."""

    id: str
    name: str
    side: str
    repository: str | None
    holds: int
    view: dict[str, object]
    commands: dict[str, str] = dataclasses.field(default_factory=dict)


def parse_matrix_stacks(data: dict[str, object]) -> list[MatrixStack]:
    """Read the stacks from what `atw-matrix stacks` printed.

    A value that is not the shape `stacks` prints raises the PolyrepoError of the narrowing
    helper that finds it.

    Returns:
        The stacks, in the order the matrix gave them.

    """
    out: list[MatrixStack] = []
    for row in _seq(data.get("stacks"), "the matrix's stacks"):
        item = _map(row, "a matrix stack row")
        stack = _map(item.get("stack"), "a matrix stack")
        held = [
            {k: v for k, v in _map(_map(h, "a hold").get("entry"), "a held entry").items() if k in HELD_KEYS}
            for h in _seq(item.get("holds") or [], "the entries a stack holds")
        ]
        repository = _opt_str(stack.get("repository"), "a stack's repository")
        view: dict[str, object] = {
            "id": _str(stack.get("id"), "a stack's id"),
            "name": _str(stack.get("name"), "a stack's name"),
            "type": stack.get("type"),
            "side": _str(stack.get("side"), "a stack's side"),
            "purpose": stack.get("purpose"),
            "executionUse": stack.get("executionUse"),
            "repository": repository,
            "holds": held,
        }
        commands = {
            k: v for k, v in _map(stack.get("commands") or {}, "a stack's commands").items() if isinstance(v, str)
        }
        out.append(
            MatrixStack(str(view["id"]), str(view["name"]), str(view["side"]), repository, len(held), view, commands),
        )
    return out


def matrix_run(cfg: Config, args: list[str]) -> dict[str, object]:
    """Run one `atw-matrix` command as the repository steward and read its JSON object.

    The matrix is the file `$ATW_MATRIX` names, else the one under `$ATW_CONTROL_REPO`, else the
    one in the control repository the config sits in. `check` prints its object and exits
    non-zero when the matrix is invalid; any other command that exits non-zero has failed.

    Returns:
        The object the command printed.

    Raises:
        PolyrepoError: when the command did not run, failed, or printed no JSON object.

    """
    env: dict[str, str | None] = {MATRIX_ROLE_ENV: MATRIX_ROLE}
    if not os.environ.get(MATRIX_FILE_ENV) and not os.environ.get(CONTROL_REPO_ENV):
        env[CONTROL_REPO_ENV] = str(cfg.file.parent.parent)
    cp = run([str(MATRIX_COMMAND), *args], timeout=MATRIX_TIMEOUT, env=env)
    try:
        parsed: object = json.loads(cp.stdout) if cp.stdout.strip() else None
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict) or (cp.returncode != 0 and args[0] != "check"):
        msg = f"atw-matrix {' '.join(args[:2])} failed: {_last_line(cp)}"
        raise PolyrepoError(msg)
    return _map(parsed, "the atw-matrix output")


def read_matrix_stacks(cfg: Config, repository: str | None = None) -> list[MatrixStack]:
    """Read the matrix's stacks, or only those one repository holds (`stacks --repository`).

    Returns:
        The stacks.

    """
    return parse_matrix_stacks(matrix_run(cfg, ["stacks", *(["--repository", repository] if repository else [])]))


def matrix_commit(cfg: Config) -> str:
    """Commit and push the matrix file after a change (`atw-matrix commit`).

    Returns:
        One sentence saying whether a commit was made and pushed.

    """
    done = matrix_run(cfg, ["commit"])
    return f"matrix committed: {bool(done.get('committed'))}, pushed: {bool(done.get('pushed'))}"


def stack_types(cfg: Config) -> tuple[str, ...]:
    """Read the stack types the project's naming rules list (`segments.type.enum`).

    The rules are the file `$RESOURCE_NAMING_CONFIG` names, else `.resource-naming.yaml` in the
    control repository.

    Returns:
        The values a repository name's type segment may have.

    Raises:
        PolyrepoError: when the file cannot be read or lists no types.

    """
    stated = os.environ.get(NAMING_RULES_ENV, "").strip()
    path = Path(stated).expanduser() if stated else cfg.file.parent.parent / NAMING_RULES_FILE
    try:
        loaded: object = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        msg = f"cannot read the naming rules {path}: {exc}"
        raise PolyrepoError(msg) from exc
    segment = _map(_map(_map(loaded, "the naming rules").get("segments"), "segments").get("type"), "segments.type")
    types = _strs(segment.get("enum"), "segments.type.enum")
    if not types:
        msg = f"the naming rules {path} list no stack types (segments.type.enum)"
        raise PolyrepoError(msg)
    return tuple(types)


def holds_stack(name: str, types: tuple[str, ...]) -> bool:
    """Tell whether a repository of this name holds a stack: its name ends in a listed stack type.

    Returns:
        True when the last hyphen-separated token of the name is one of the types.

    """
    return STACK_NAME_SEPARATOR in name and name.rpartition(STACK_NAME_SEPARATOR)[2] in types


def record_stack(cfg: Config, name: str, space: str, known: list[MatrixStack]) -> str:
    """Record in the matrix the stack a repository named `name` holds (S1).

    The stack takes the repository's name. A stack the matrix already holds under that id gets
    its `repository`; one it does not hold is recorded on the repository side with its app, its
    execution use (imported for a library, else executable) and the purpose not stated.

    An `atw-matrix` refusal propagates as the PolyrepoError of `matrix_run`.

    Returns:
        One sentence saying what was recorded.

    """
    sid = f"stack:{name}"
    args = ["put", "stack", "--side", "repository", "--id", sid, "--repository", name]
    if any(s.id == sid for s in known):
        matrix_run(cfg, args)
        return f"matrix: {sid} now names {name} as its repository"
    kind = name.rpartition(STACK_NAME_SEPARATOR)[2]
    use = EXECUTION_IMPORTED if kind == LIBRARY_STACK_TYPE else EXECUTION_EXECUTABLE
    matrix_run(cfg, [*args, "--name", name, "--app", space, "--execution-use", use, "--purpose", PURPOSE_NOT_STATED])
    return f"matrix: recorded {sid} ({use}, app {space}), purpose not stated"


def require_no_stacks(cfg: Config, repository: str) -> None:
    """Refuse to go on while the matrix has stacks in a repository that is leaving use (S3).

    Raises:
        PolyrepoError: when any stack names the repository, with the ids to move or remove.

    """
    held = read_matrix_stacks(cfg, repository)
    if held:
        msg = (
            f"the matrix still has stacks in {repository}: {', '.join(s.id for s in held)}; move each "
            "(put stack --repository) or remove it (remove stack:<id> --held), then try again"
        )
        raise PolyrepoError(msg)


# --------------------------------------------------------------------------------------------
# state: everything live, gathered once per call


@dataclasses.dataclass
class State:
    """Disk, GitHub and manifest, gathered together for one command."""

    cfg: Config
    local: dict[str, LocalRepo]
    duplicates: list[tuple[str, list[Path]]]
    gh: GitHub
    manifest: Manifest
    held_stacks: list[MatrixStack] | None = None

    def matrix_stacks(self) -> list[MatrixStack]:
        """Read the matrix's stacks once per command.

        Returns:
            Every stack the matrix holds.

        """
        if self.held_stacks is None:
            self.held_stacks = read_matrix_stacks(self.cfg)
        return self.held_stacks

    def resolve(self, wanted: list[str]) -> list[str]:
        """Resolve repo names or paths given on the command line to tracked repo names.

        Returns:
            Canonical names.

        """
        return resolve_names(self.tracked_names(), self.local, wanted)

    def live_state(self, name: str) -> str:
        """Say what disk and GitHub know of a name.

        Returns:
            "active", "inactive" (deprecated or archived), or "missing".

        """
        if name in self.local or self.gh.get(name):
            return "inactive" if self.lifecycle(name) in LIFECYCLES_INACTIVE else "active"
        return "missing"

    def local_id(self, r: LocalRepo) -> str | None:
        """Return GitHub's id of the repo a clone's origin leads to.

        Returns:
            The id, or None when origin is no GitHub repo of the owner.

        """
        parsed = parse_github_url(r.origin_url)
        if parsed is None or parsed[0].lower() != self.cfg.owner.lower():
            return None
        return self.gh.id_of(parsed[1])

    def lifecycle(self, name: str) -> str:
        """Derive a repo's lifecycle from reality first, the manifest second.

        Returns:
            archived, deprecated, or the manifest's lifecycle (active when absent).

        """
        g = self.gh.get(name)
        if g and g["archived"]:
            return "archived"
        if self.cfg.is_deprecated_name(name):
            return "deprecated"
        e = self.manifest.entries().get(name)
        man = str(e.get("lifecycle")) if e and e.get("lifecycle") else "active"
        return "active" if man in LIFECYCLES_INACTIVE else man

    def tracked_names(self) -> list[str]:
        """Every repo of the project: the ones the manifest records and the clones under the root.

        Returns:
            Sorted names.

        """
        return sorted(set(self.local) | set(self.manifest.entries()), key=str.lower)

    def record(self, name: str, deep: bool = True) -> dict[str, object]:
        """Build a repo's full record: live facts, the manifest's groups, and the matrix's stacks.

        Groups are reported only for a repo that exists and is active. With deep, the record
        carries `stacks`: the matrix's stacks that name the repo as their repository, each with
        its purpose and what it holds (an empty list when the matrix has none). The record
        carries no dependencies: a dependency is between services, components and
        infrastructure, never between repos.

        Returns:
            The record.

        """
        r = self.local.get(name)
        e = self.manifest.entries().get(name) or CommentedMap()
        g = self.gh.get(name)
        pat = self.cfg.classify(name)
        lifecycle = self.lifecycle(name)
        live = r is not None or g is not None
        rec: dict[str, object] = {
            "name": name,
            "space": r.space if r else self.cfg.expected_space(name),
            "path": str(r.path) if r else None,
            "lifecycle": lifecycle,
            "present": {
                "disk": r is not None,
                "github": g is not None,
                "manifest": bool(e),
            },
            "naming": {
                "pattern": pat["name"] if pat else None,
                "valid": pat is not None,
            },
            "branch": r.branch if r else None,
            "uncommitted": r.uncommitted if r else None,
            "uncommitted_files": r.uncommitted_files if r else None,
            "last_commit": (
                {"sha": r.head_sha, "date": r.head_date, "subject": r.head_subject} if r and r.head_sha else None
            ),
            "main": (
                {
                    "sha": r.main_sha,
                    "origin_sha": r.origin_main_sha,
                    "ahead": r.ahead,
                    "behind": r.behind,
                    "up_to_date": r.ahead == 0 and r.behind == 0,
                    "fetched_at": r.fetched_at,
                    "fetch_error": r.fetch_error,
                }
                if r
                else None
            ),
            "origin_url": r.origin_url if r else None,
            "github": g,
            "tier": e.get("tier"),
            "groups": (self.manifest.groups_of(name) if live and lifecycle not in LIFECYCLES_INACTIVE else []),
        }
        if deep:
            rec["stacks"] = [s.view for s in self.matrix_stacks() if s.repository == name]
        if e.get("deprecated_on"):
            rec["deprecated_on"] = str(e["deprecated_on"])
        return rec


def gather(cfg: Config, fetch: bool, use_cache: bool) -> State:
    """Gather disk, GitHub and manifest state, fetching in parallel with the GitHub listing.

    Returns:
        The State.

    """
    local, dups = discover(cfg)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        gh_future = ex.submit(GitHub, cfg, use_cache)
        collect_all_local(local, cfg, fetch, use_cache)
        gh = gh_future.result()
    return State(cfg, local, dups, gh, Manifest(cfg.manifest, gh))


# --------------------------------------------------------------------------------------------
# reconcile


@dataclasses.dataclass
class Finding:
    """One way disk, GitHub and the manifest disagree, or a rule is broken."""

    kind: str
    repo: str
    detail: str
    fix: str | None = None
    action: Callable[[], object] | None = dataclasses.field(default=None, repr=False)
    manifest_change: bool = False
    logged: bool = False
    status: str = "open"
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the finding as JSON-ready data.

        Returns:
            The finding without its action.

        """
        return {
            "kind": self.kind,
            "repo": self.repo,
            "detail": self.detail,
            "mechanical": self.fix is not None,
            "fix": self.fix,
            "status": self.status,
            "error": self.error,
        }


class GitFailedError(Exception):
    """A git or gh command run by a fix failed."""


def must(cp: subprocess.CompletedProcess[str]) -> None:
    """Raise when a fix's command failed.

    Raises:
        GitFailedError: when the command exited non-zero.

    """
    if cp.returncode != 0:
        raise GitFailedError(
            (cp.stderr or cp.stdout).strip() or f"{cp.args} exited {cp.returncode}",
        )


def _add_entry(man: Manifest, cfg: Config, name: str, lifecycle: str) -> None:
    """Add a manifest entry for a repo, with the fields computed when the fix runs."""
    man.add_entry(name, entry_fields(cfg, name, lifecycle))


def point_origin(repo: Path, url: str) -> None:
    """Point the repo's origin remote at a URL, adding the remote when it has none.

    A git failure propagates as the GitFailedError that `must` raises.
    """
    verb = "set-url" if git_out(repo, "remote", "get-url", "origin") else "add"
    must(git(repo, "remote", verb, "origin", url))


def create_on_github(cfg: Config, name: str, repo: Path) -> None:
    """Create the private GitHub repo with auto-merge allowed, point origin at it, and push.

    A gh or git failure propagates as the GitFailedError that `must` raises.
    """
    must(run(["gh", "repo", "create", f"{cfg.owner}/{name}", "--private"], timeout=120))
    must(
        run(
            [
                "gh",
                "api",
                "-X",
                "PATCH",
                f"repos/{cfg.owner}/{name}",
                "-F",
                "allow_auto_merge=true",
            ],
            timeout=120,
        ),
    )
    point_origin(repo, cfg.github_url(name))
    b = cfg.default_branch
    if git_out(repo, "rev-parse", "--verify", "-q", f"refs/heads/{b}"):
        must(git(repo, "push", "-u", "origin", b, timeout=120))


def entry_fields(
    cfg: Config,
    name: str,
    lifecycle: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return the fields of a new manifest entry: the lifecycle and the tier (see `default_tier`).

    A deprecated repo's `deprecated_on` is the date it was renamed deprecated; an entry added
    without one is reported undated by `reconcile`, never dated today.

    Returns:
        The fields, with extra merged over them.

    """
    fields: dict[str, object] = {
        "lifecycle": lifecycle,
        "tier": default_tier(cfg, name),
    }
    return {**fields, **(extra or {})}


def default_tier(cfg: Config, name: str) -> str:
    """Return the tier a repository gets when the owner states none.

    Returns:
        `tooling` for the control repository (the repository that holds the steward's config),
        `product` for every other repository.

    """
    return TIER_TOOLING if cfg.file.parent.parent.name == name else TIER_PRODUCT


def reconcile(st: State) -> list[Finding]:
    """Compare disk, GitHub and the manifest, and name every disagreement with its fix.

    Returns:
        The findings, each carrying its fix action when the fix is mechanical.

    """
    entries = st.manifest.entries()
    local_ids = {rid: name for name, r in st.local.items() if (rid := st.local_id(r))}
    out: list[Finding] = [
        Finding(
            "duplicate-name",
            name,
            f"same folder name at {', '.join(str(p) for p in paths)}",
        )
        for name, paths in st.duplicates
    ]

    out.extend(_check_entries_off_disk(st, entries, local_ids))

    # Repos on disk.
    tracked_ids = {str(e[ENTRY_ID]) for e in entries.values() if e.get(ENTRY_ID)}
    for name, r in sorted(st.local.items(), key=lambda kv: kv[0].lower()):
        out.extend(_check_local(st, name, r, entries, tracked_ids))

    # Every tracked name, on disk or not: manifest fields that GitHub decides.
    for name in st.tracked_names():
        out.extend(_check_tracked(st, name, entries))

    out.extend(_check_relationships(st))
    out.extend(_check_open_items(st))
    out.extend(_check_retired_sections(st))
    return out


def _check_entries_off_disk(
    st: State,
    entries: dict[str, CommentedMap],
    local_ids: dict[str, str],
) -> list[Finding]:
    """Check manifest entries with no clone on disk, and entries that record a repository twice.

    A clone whose origin leads to an entry's repository is that entry's clone, whatever its folder
    is called; `reconcile` reports the folder name separately.

    Returns:
        The findings, in manifest order.

    """
    cfg, man = st.cfg, st.manifest
    out: list[Finding] = [
        Finding(
            "duplicate-entry",
            name,
            f"two manifest entries record {name}",
            fix="remove the later entry",
            action=functools.partial(man.drop_entry, e),
            manifest_change=True,
        )
        for name, e in man.duplicates()
    ]
    for name, e in entries.items():
        if name in st.local or str(e.get(ENTRY_ID) or "") in local_ids:
            continue
        lifecycle = str(e.get("lifecycle") or "active")
        rec = None if man.is_unresolved(e) else st.gh.resolve(name)
        if rec is None and lifecycle != "planned":
            out.append(
                Finding(
                    "orphan-entry",
                    name,
                    "manifest entry with no repo on disk or on GitHub",
                    fix="remove the entry and its group memberships",
                    action=functools.partial(man.drop_entry, e),
                    manifest_change=True,
                ),
            )
        elif rec is not None and lifecycle not in LIFECYCLES_INACTIVE and not cfg.is_deprecated_name(name):
            if rec["archived"]:
                continue
            out.append(
                Finding(
                    "not-cloned",
                    name,
                    f"on GitHub and in the manifest but not under {cfg.root}",
                ),
            )
    return out


def _check_relationships(st: State) -> list[Finding]:
    """Check group members and stored dependencies.

    Group members are checked against disk and GitHub, and the manifest must store no
    repo-to-repo dependency.

    Returns:
        The findings.

    """
    man = st.manifest
    out: list[Finding] = _check_group_members(st)

    if man.has_stored_dependencies():
        out.append(
            Finding(
                "repo-dependency-stored",
                "relationships.dependencies",
                "the manifest stores repo-to-repo dependency edges; a dependency is "
                "between services, components and infrastructure, never between repos",
                fix="remove relationships.dependencies",
                action=man.drop_stored_dependencies,
                manifest_change=True,
            ),
        )
    return out


def _check_group_members(st: State) -> list[Finding]:
    """Check every group member against disk and GitHub.

    Returns:
        One finding per member that is unknown or inactive.

    """
    man = st.manifest
    out: list[Finding] = []
    for g in man.groups():
        gname = str(g["name"])
        for m in [str(x) for x in g.get("members") or []]:
            name = man.member_name(m)
            s = st.live_state(name) if name else "missing"
            if s == "active":
                continue
            why = "on neither disk nor GitHub" if s == "missing" else "deprecated or archived"
            out.append(
                Finding(
                    f"group-member-{'unknown' if s == 'missing' else 'inactive'}",
                    name or m,
                    f"member of group {gname}, but {why}",
                    fix=f"remove it from group {gname}",
                    action=functools.partial(man.set_member, gname, m, None),
                    manifest_change=True,
                ),
            )
    return out


def _check_retired_sections(st: State) -> list[Finding]:
    """Find manifest sections and entry fields that restate a canonical source, which it may not keep.

    The retired sections are the project conventions, owners and the stored relationships: the
    root AGENTS.md and the matrix are their sources. Entry fields are dropped on every save.

    Returns:
        One finding per retired section or `project` field present; removing it is mechanical.

    """
    man = st.manifest
    out: list[Finding] = [
        Finding(
            "retired-section",
            key,
            f"the manifest carries a {key} section, which restates a canonical source",
            fix=f"remove the {key} section; git history keeps it",
            action=functools.partial(man.remove_section, key),
            manifest_change=True,
        )
        for key in RETIRED_SECTIONS
        if key in man.doc
    ]
    project = man.doc.get("project") or {}
    out.extend(
        Finding(
            "retired-section",
            f"project.{key}",
            f"the manifest's project.{key} restates a canonical source",
            fix=f"remove project.{key}; git history keeps it",
            action=man.drop_retired_project_fields,
            manifest_change=True,
        )
        for key in RETIRED_PROJECT_FIELDS
        if key in project
    )
    return out


def _check_open_items(st: State) -> list[Finding]:
    """Find manifest sections that hold questions or open items, which it may not carry.

    Returns:
        One finding per such section; removing it is mechanical once every entry is settled.

    """
    man = st.manifest
    out: list[Finding] = []
    for key in OPEN_ITEM_SECTIONS:
        if key not in man.doc:
            continue
        items = man.doc.get(key) or []
        unsettled = [
            i for i in items if not (isinstance(i, dict) and str(i.get("status", "")) in {"resolved", "false-alarm"})
        ]
        if unsettled:
            out.append(
                Finding(
                    "open-items",
                    key,
                    f"the manifest's {key} holds {len(unsettled)} unsettled item(s); "
                    "put each to the user in the reply, record the answer where it belongs, "
                    "then remove the section",
                ),
            )
        else:
            out.append(
                Finding(
                    "open-items",
                    key,
                    f"the manifest carries a {key} section ({len(items)} settled item(s))",
                    fix=f"remove the {key} section; git history keeps it",
                    action=functools.partial(man.remove_section, key),
                    manifest_change=True,
                ),
            )
    return out


def _check_local(
    st: State,
    name: str,
    r: LocalRepo,
    entries: dict[str, CommentedMap],
    tracked_ids: set[str],
) -> list[Finding]:
    """Check one repo on disk: its entry, naming, origin, pushed main and disk-decided fields.

    A clone whose origin leads to a repository the manifest records is tracked, whatever its
    folder is called.

    Returns:
        The findings, in check order.

    """
    cfg, man = st.cfg, st.manifest
    out: list[Finding] = []
    e = entries.get(name)

    if e is None and st.local_id(r) not in tracked_ids:
        lc = "deprecated" if cfg.is_deprecated_name(name) else "active"
        out.append(
            Finding(
                "untracked-repo",
                name,
                f"repo on disk at {r.path} with no manifest entry",
                fix=f"add a manifest entry (lifecycle {lc})",
                action=lambda: man.add_entry(name, entry_fields(cfg, name, lc)),
                manifest_change=True,
            ),
        )

    pat = _check_naming(cfg, name, r, out)
    origin_ok = _check_origin(st, name, r, pat, out)
    out.extend(_check_main_pushed(st, name, r, origin_ok=origin_ok))
    if e is not None:
        out.extend(_check_disk_fields(st, name, r, e))
    return out


def _check_naming(cfg: Config, name: str, r: LocalRepo, out: list[Finding]) -> NamingPattern | None:
    """Check a repo's folder name and placement, appending findings to out.

    Returns:
        The naming pattern the name matches, or None.

    """
    pat = cfg.classify(name)
    if pat is None:
        out.append(
            Finding("naming-violation", name, f"folder name is refused: {cfg.naming_problem(name)}"),
        )
    else:
        space = cfg.expected_space(name)
        if space and space != r.space:
            out.append(
                Finding(
                    "space-mismatch",
                    name,
                    f"a {pat['name']} name lives in space {r.space}, not {space}",
                ),
            )
    return pat


def _check_origin(
    st: State,
    name: str,
    r: LocalRepo,
    pat: NamingPattern | None,
    out: list[Finding],
) -> bool:
    """Check a repo's origin remote against GitHub, appending findings to out.

    Returns:
        True when origin points at the repo's GitHub repo.

    """
    cfg, gh = st.cfg, st.gh
    parsed = parse_github_url(r.origin_url)
    if r.origin_url is None:
        rec = gh.get(name)
        if rec:
            out.append(
                Finding(
                    "no-origin",
                    name,
                    "no origin remote; GitHub has a repo of this name",
                    fix=f"add origin {cfg.github_url(rec['name'])}",
                    action=functools.partial(point_origin, r.path, cfg.github_url(rec["name"])),
                ),
            )
        else:
            out.append(_local_only(st, name, r))
        return False
    if parsed is None or parsed[0].lower() != cfg.owner.lower():
        out.append(
            Finding(
                "foreign-origin",
                name,
                f"origin {r.origin_url} is not a {cfg.owner} GitHub repo",
            ),
        )
        return False
    origin_name = parsed[1]
    rec = gh.resolve(origin_name)
    if rec is None:
        if origin_name == name:
            out.append(_local_only(st, name, r))
        else:
            out.append(
                Finding(
                    "github-missing",
                    name,
                    f"origin names {origin_name}, which is not on GitHub",
                ),
            )
        return False
    gh_name = rec["name"]
    if gh_name != name:
        out.append(_name_mismatch(st, name, gh_name, name_valid=pat is not None))
        return False
    if origin_name != gh_name:
        out.append(
            Finding(
                "origin-stale",
                name,
                f"origin names {origin_name}; GitHub now calls it {gh_name}",
                fix=f"point origin at {cfg.github_url(gh_name)}",
                action=functools.partial(point_origin, r.path, cfg.github_url(gh_name)),
            ),
        )
    return True


def _name_mismatch(st: State, name: str, gh_name: str, *, name_valid: bool) -> Finding:
    """Report a folder whose GitHub repo has another name, with the rename fix when it is free.

    Returns:
        The name-mismatch finding.

    """
    taken = st.gh.resolve(name)
    if taken is None and name_valid:
        return Finding(
            "name-mismatch",
            name,
            f"folder is {name} but its GitHub repo is {gh_name}",
            fix=f"rename the GitHub repo {gh_name} to {name} and point origin at it",
            action=functools.partial(rename, st, gh_name, name),
            logged=True,
        )
    why = "a different repo already has that name" if taken else "the folder name is not valid"
    return Finding(
        "name-mismatch",
        name,
        f"folder is {name} but its GitHub repo is {gh_name}; {why}",
    )


def _check_main_pushed(st: State, name: str, r: LocalRepo, *, origin_ok: bool) -> list[Finding]:
    """Check that a repo's default branch is pushed to GitHub.

    Returns:
        The findings.

    """
    b = st.cfg.default_branch
    out: list[Finding] = []
    if origin_ok and r.main_sha:
        if r.fetch_error:
            out.append(
                Finding(
                    "fetch-failed",
                    name,
                    f"git fetch origin failed: {r.fetch_error}",
                ),
            )
        elif r.origin_main_sha is None:
            out.append(
                Finding(
                    "unpushed",
                    name,
                    f"{b} has never been pushed to origin",
                    fix=f"git push -u origin {b}",
                    action=lambda: must(
                        git(r.path, "push", "-u", "origin", b, timeout=120),
                    ),
                ),
            )
        elif r.ahead and not r.behind:
            out.append(
                Finding(
                    "unpushed",
                    name,
                    f"{b} is {r.ahead} commit(s) ahead of origin/{b}",
                    fix=f"git push origin {b}",
                    action=lambda: must(git(r.path, "push", "origin", b, timeout=120)),
                ),
            )
        elif r.ahead and r.behind:
            out.append(
                Finding(
                    "diverged",
                    name,
                    f"{b} is {r.ahead} ahead and {r.behind} behind origin/{b}; needs a rebase",
                ),
            )
    elif r.origin_url and r.main_sha is None:
        out.append(Finding("no-default-branch", name, f"no local {b} branch"))
    return out


def _check_disk_fields(st: State, name: str, r: LocalRepo, e: CommentedMap) -> list[Finding]:
    """Check the manifest field the disk decides: local_path.

    Returns:
        The findings.

    """
    man = st.manifest
    out: list[Finding] = []
    lp = e.get("local_path")
    if lp is not None and Path(str(lp)).expanduser() != r.path:
        out.append(
            Finding(
                "local-path",
                name,
                f"manifest local_path {lp} is not where the repo is ({r.path})",
                fix="remove local_path; the tool finds the path on disk",
                action=lambda: man.set_field(name, "local_path", None),
                manifest_change=True,
            ),
        )
    return out


def _check_tracked(
    st: State,
    name: str,
    entries: dict[str, CommentedMap],
) -> list[Finding]:
    man = st.manifest
    e = entries.get(name)
    if e is None:
        return []
    out: list[Finding] = []
    rec = st.gh.get(name)
    if rec is not None and not e.get(ENTRY_ID):
        out.append(
            Finding(
                "entry-unkeyed",
                name,
                "manifest entry records the repository's name, not GitHub's id of it",
                fix="record GitHub's id and drop the name; the name is read live",
                action=functools.partial(man.key_entry, name),
                manifest_change=True,
            ),
        )
    lc = str(e.get("lifecycle") or "")
    if rec is not None:
        want = st.lifecycle(name)
        stale = (want in LIFECYCLES_INACTIVE and lc != want) or (
            lc in LIFECYCLES_INACTIVE and want not in LIFECYCLES_INACTIVE
        )
        if stale:
            out.append(
                Finding(
                    "lifecycle",
                    name,
                    f"manifest lifecycle is {lc or '(missing)'}; GitHub and the name say {want}",
                    fix=f"set lifecycle to {want}",
                    action=functools.partial(man.set_field, name, "lifecycle", want),
                    manifest_change=True,
                ),
            )
            if lc == "deprecated" and want == "active":
                out[-1] = Finding(
                    "deprecation-not-renamed",
                    name,
                    "manifest says deprecated but the repo was never renamed with the deprecated- prefix",
                )
        if st.lifecycle(name) == "deprecated":
            out.extend(_check_deprecation_age(name, e))
    out.extend(_check_tier(st, name, e))
    return out


def _check_tier(st: State, name: str, e: CommentedMap) -> list[Finding]:
    """Check that an entry records a tier, product or tooling.

    Returns:
        A mechanical finding for an entry with no tier (the fix records the default), an open
        finding for a tier that is neither.

    """
    tier = e.get("tier")
    if tier in TIERS:
        return []
    if tier is not None:
        return [Finding("tier-invalid", name, f"manifest tier {tier!r} is neither {TIER_PRODUCT} nor {TIER_TOOLING}")]
    want = default_tier(st.cfg, name)
    return [
        Finding(
            "tier-missing",
            name,
            "manifest entry records no tier",
            fix=f"set tier to {want}",
            action=functools.partial(st.manifest.set_field, name, "tier", want, "lifecycle"),
            manifest_change=True,
        ),
    ]


def _check_deprecation_age(name: str, e: CommentedMap) -> list[Finding]:
    """Check that a deprecated repo's entry carries its real deprecation date.

    An undated entry stays an open finding: the date is found in the git history of the
    manifest, because today's date would restart the clock to archiving. Archiving itself is
    `archive-due`'s.

    Returns:
        The findings.

    """
    since = e.get("deprecated_on")
    if since and _deprecation_start(e) is None:
        return [Finding("deprecated-undated", name, f"deprecated_on {since!r} is not a date")]
    if since:
        return []
    return [
        Finding(
            "deprecated-undated",
            name,
            "deprecated repo with no deprecated_on date: find the date it was deprecated in the git "
            "history of the manifest and record it",
        ),
    ]


def _deprecation_start(e: Mapping[str, object]) -> dt.date | None:
    """Read an entry's deprecation date.

    Returns:
        The date, or None when the entry has none or it is not a date.

    """
    since = e.get("deprecated_on")
    if not since:
        return None
    try:
        return dt.date.fromisoformat(str(since)[:10])
    except ValueError:
        return None


def _local_only(st: State, name: str, r: LocalRepo) -> Finding:
    cfg = st.cfg
    if cfg.classify(name) is None:
        return Finding(
            "local-only",
            name,
            "no GitHub repo; the folder must be renamed to a valid name first",
        )
    return Finding(
        "local-only",
        name,
        "no GitHub repo for this folder",
        fix=f"create the private GitHub repo {cfg.owner}/{name}, point origin at it, and push {cfg.default_branch}",
        action=lambda: create_on_github(cfg, name, r.path),
    )


def apply_fixes(st: State, findings: list[Finding], dry_run: bool) -> None:
    """Run every mechanical fix: GitHub and git actions first, then manifest changes; note them for the commit."""
    todo = [f for f in findings if f.action is not None]
    ordered = [f for f in todo if not f.manifest_change] + [f for f in todo if f.manifest_change]
    for f in ordered:
        action = f.action
        if action is None:
            continue
        if dry_run:
            f.status = "planned"
            continue
        try:
            action()
            f.status = "fixed"
        except (GitFailedError, PolyrepoError, OSError, KeyError, ValueError) as exc:
            f.status = "failed"
            f.error = str(exc)
    if dry_run:
        return
    st.manifest.save()
    done = [f for f in ordered if f.status == "fixed"]
    if done:
        st.gh.invalidate()
    unlogged = [f for f in done if not f.logged]
    if unlogged:
        note_change(
            st.cfg,
            "polyrepo reconcile --fix",
            [f"{f.kind} {f.repo}: {f.fix}" for f in unlogged],
        )


def today() -> str:
    """Return today's local date.

    Returns:
        The date as YYYY-MM-DD.

    """
    return dt.datetime.now().astimezone().date().isoformat()


def note_change(cfg: Config, title: str, lines: list[str]) -> None:
    """Note a change to the steward's files for the message of the commit that records it.

    The title joins the commit subject and each line becomes a line of its body, so the git
    history of the records says what changed.
    """
    cfg.changes.append(title.removeprefix("polyrepo ").strip())
    cfg.change_lines.extend(lines)


def commit_records(cfg: Config, subject: str, body: list[str] | None = None) -> dict[str, object]:
    """Commit the steward's own files, then pull --rebase and push.

    The files are the manifest, knowledge store and fleet list, committed on the default branch
    of the repo that holds them. The body lines, when given, follow the subject in the message.

    The tier export (`write_tier_export`) is rewritten first, so it follows every manifest write;
    it is derived and machine-specific, so it is not committed.

    Returns:
        {"status": "clean" | "pushed" | "failed", "files": [...], "error"?: str}.

    """
    top = git_out(cfg.file.parent, "rev-parse", "--show-toplevel")
    if top is None:
        return {
            "status": "failed",
            "files": [],
            "error": f"{cfg.file.parent} is not in a git repo",
        }
    root = Path(top)
    try:
        write_tier_export(cfg)
    except (PolyrepoError, OSError) as exc:
        return {"status": "failed", "files": [], "error": f"tier export not written: {exc}"}
    rels = [
        p.resolve().relative_to(root.resolve()).as_posix()
        for p in (cfg.manifest, cfg.knowledge, fleet_file(cfg))
        if p.exists() and p.resolve().is_relative_to(root.resolve())
    ]
    changed = git(root, "status", "--porcelain=v1", "--", *rels).stdout
    files = [ln[3:] for ln in changed.splitlines() if ln.strip()]
    if not files:
        return {"status": "clean", "files": []}
    b = cfg.default_branch
    branch = git_out(root, "symbolic-ref", "--short", "-q", "HEAD")
    try:
        _require_branch(root, branch, b)
        message = f"chore(polyrepo): {subject}" + ("\n\n" + "\n".join(f"- {ln}" for ln in body) if body else "")
        _commit_paths(root, files, message, force=True)
        must(git(root, "pull", "--rebase", "--autostash", "--quiet", timeout=120))
        must(git(root, "push", "origin", b, timeout=120))
    except GitFailedError as exc:
        return {"status": "failed", "files": files, "error": str(exc)}
    return {"status": "pushed", "files": files}


def _require_branch(root: Path, branch: str | None, want: str) -> None:
    """Refuse to commit in a repo that is not on the wanted branch.

    Raises:
        GitFailedError: when the repo is on another branch.

    """
    if branch != want:
        msg = f"{root} is on {branch}, not {want}"
        raise GitFailedError(msg)


def finish_records(cfg: Config, data: dict[str, object]) -> None:
    """Commit and push the steward's files when this run changed them, reporting it in data."""
    if cfg.changes:
        data["records"] = commit_records(cfg, "; ".join(dict.fromkeys(cfg.changes)), cfg.change_lines)


# --------------------------------------------------------------------------------------------
# tiers: which repositories are product (tier 1) and which are tooling (tier 2). The manifest
# records the tier of every repository it has an entry for. A repository outside the repository
# root, which has no entry, is listed in the config's `tiers.external`. The export is the file the
# hooks read: a JSON object from each clone's absolute path to its tier.


@dataclasses.dataclass(frozen=True, slots=True)
class TierRepo:
    """One repository clone with its recorded tier."""

    name: str
    path: Path
    tier: str
    source: str

    def paths(self) -> tuple[Path, ...]:
        """Return the clone's path as recorded and, when a symbolic link makes it differ, its real path.

        Returns:
            One path, or two.

        """
        real = self.path.resolve()
        return (self.path,) if real == self.path else (self.path, real)


@dataclasses.dataclass(frozen=True, slots=True)
class TierAnswer:
    """The tier of the repository that contains one path."""

    path: Path
    repo: TierRepo | None
    linked_worktree: bool
    toplevel: Path | None


def _absolute(raw: str) -> Path:
    """Make a path absolute and tidy without following a symbolic link.

    Returns:
        The path as written, joined to the working folder when it is relative.

    """
    return Path(os.path.normpath(Path.cwd() / Path(raw).expanduser()))


def tier_export_path(cfg: Config) -> Path:
    """Return the tier export file (config `tiers.export`, by default `repository-tiers.json` in `.polyrepo/`).

    Returns:
        The path.

    """
    return cfg.setting_path("tiers", "export", TIER_EXPORT_FILE)


def _external_tiers(cfg: Config) -> tuple[list[TierRepo], list[str]]:
    """Read the config's `tiers.external`: repositories outside the repository root, each with its tier.

    Each entry has a `name`, a `path` (environment variables are expanded) and a `tier`.

    Returns:
        The repositories whose path is the root of a git clone, and a problem for each that is not.

    Raises:
        PolyrepoError: when the section is malformed or an entry names a tier that does not exist.

    """
    section = _map(cfg.raw.get("tiers") or {}, "config tiers")
    repos: list[TierRepo] = []
    problems: list[str] = []
    for item in _seq(section.get("external") or [], "config tiers.external"):
        entry = _map(item, "config tiers.external entry")
        name = _str(entry.get("name"), "tiers.external name")
        tier = _str(entry.get("tier"), f"tiers.external tier of {name}")
        if tier not in TIERS:
            msg = f"config tiers.external: {name} has tier {tier!r}, which is neither {TIER_PRODUCT} nor {TIER_TOOLING}"
            raise PolyrepoError(msg)
        raw = expand_env(_str(entry.get("path"), f"tiers.external path of {name}"))
        path = _absolute(raw)
        if not (path / ".git").exists():
            problems.append(f"{name}: {path} is not the root of a git clone")
            continue
        repos.append(TierRepo(name, path, tier, "config"))
    return repos, problems


def tier_repos(cfg: Config, manifest: Manifest, local: dict[str, LocalRepo]) -> tuple[list[TierRepo], list[str]]:
    """List every clone with a recorded tier: those on disk with a manifest tier, and the external ones.

    Returns:
        The repositories, sorted by path, and the problems found with the external ones.

    """
    entries = manifest.entries()
    repos = [
        TierRepo(name, r.path, str(entries[name]["tier"]), "manifest")
        for name, r in local.items()
        if name in entries and entries[name].get("tier") in TIERS
    ]
    external, problems = _external_tiers(cfg)
    return sorted([*repos, *external], key=lambda t: str(t.path)), problems


def tier_export_text(repos: list[TierRepo]) -> str:
    """Render the tier export.

    Returns:
        A JSON object from each repository's absolute path to its tier (a clone reached through
        a symbolic link has both paths), with a final newline.

    """
    return json.dumps(dict(sorted((str(p), r.tier) for r in repos for p in r.paths())), indent=2) + "\n"


def write_tier_export(cfg: Config, *, check: bool = False) -> tuple[Path, bool]:
    """Write the tier export, or with check only compare it, from the manifest, the clones on disk and the config.

    The file is replaced in one step, so a hook never reads half of it.

    Returns:
        The export path, and whether the file differed from what it should hold (and so was
        rewritten, unless check is set).

    """
    repos, _ = tier_repos(cfg, Manifest(cfg.manifest, GitHub(cfg, use_cache=True)), discover(cfg)[0])
    want = tier_export_text(repos)
    out = tier_export_path(cfg)
    have = out.read_text(encoding="utf-8") if out.is_file() else None
    if have == want:
        return out, False
    if not check:
        tmp = out.with_name(out.name + ".tmp")
        tmp.write_text(want, encoding="utf-8")
        tmp.replace(out)
    return out, True


def tier_of_path(repos: list[TierRepo], paths: tuple[Path, ...]) -> TierAnswer:
    """Find the repository that contains a path, and its recorded tier.

    `paths` is the path as given and its real path. A path inside a clone, a clone's `.worktrees/`
    included, belongs to that clone. A path in a linked worktree anywhere else belongs to the
    clone that git names as its common directory.

    Returns:
        The answer; `repo` is None when no recorded repository contains the path, and `toplevel`
        then names the git clone that does, when there is one.

    """
    path = paths[-1]
    inside = [
        (len(c.parts), r, p.relative_to(c)) for r in repos for c in r.paths() for p in paths if p == c or c in p.parents
    ]
    if inside:
        _, repo, rel = max(inside, key=operator.itemgetter(0))
        return TierAnswer(paths[0], repo, rel.parts[:1] == (WORKTREES_LINE.rstrip("/"),), None)
    start = next((p for p in (path, *path.parents) if p.is_dir()), None)
    common = git_out(start, "rev-parse", "--path-format=absolute", "--git-common-dir") if start else None
    top = git_out(start, "rev-parse", "--show-toplevel") if start else None
    main = Path(common).parent.resolve() if common and Path(common).name == ".git" else None
    owner = next((r for r in repos if main in r.paths()), None)
    return TierAnswer(paths[0], owner, owner is not None, Path(top).resolve() if top else None)


def cmd_naming(args: argparse.Namespace, cfg: Config) -> int:
    """Check one repository name against the vault's repository naming note, and show the rule it matched.

    Read-only. The rules are read from the note on every call; the report names the note, the
    section and the pattern line of the rule the name matched, and the space and folder the
    config's placement gives the name.

    Returns:
        0 when the name matches a pattern of the note, else 1.

    """
    rules = cfg.rules
    name: str = args.name
    pat = rules.classify(name)
    space = cfg.expected_space(name)
    folder: str | None = None
    folder_note: str | None = None
    try:
        folder = cfg.placement_folder(space, rules.deprecated_base(name))
    except PolyrepoError as exc:
        folder_note = str(exc)
    data: dict[str, object] = {
        "name": name,
        "valid": pat is not None,
        "pattern": pat["name"] if pat else None,
        "kind": pat["kind"] if pat else None,
        "section": pat["section"] if pat else None,
        "rule": pat["rule"] if pat else None,
        "document": str(rules.document),
        "type": type_of(rules.deprecated_base(name)) if pat else None,
        "types": list(rules.types),
        "space": space,
        "folder": folder,
        "folder_note": folder_note,
        "problem": None if pat else rules.problem(name),
    }
    emit(
        args,
        data,
        lambda: (
            f"{name}: matches {pat['name']} ({pat['kind']}), {pat['rule']}  [{rules.document.name}, {pat['section']}]"
            if pat
            else f"{name}: refused, {data['problem']}  [{rules.document.name}]"
        ),
    )
    return 0 if pat else 1


def cmd_tier(args: argparse.Namespace, cfg: Config) -> int:
    """Say which tier the repository containing a path is in.

    Returns:
        0 when a repository that records a tier contains the path, else 1.

    """
    repos, _ = tier_repos(cfg, Manifest(cfg.manifest, GitHub(cfg, use_cache=True)), discover(cfg)[0])
    given = _absolute(expand_env(args.path))
    got = tier_of_path(repos, tuple(dict.fromkeys((given, given.resolve()))))
    where = got.repo.path if got.repo else got.toplevel
    data: dict[str, object] = {
        "path": str(got.path),
        "repository": got.repo.name if got.repo else None,
        "repository_path": str(where) if where else None,
        "tier": got.repo.tier if got.repo else None,
        "source": got.repo.source if got.repo else None,
        "linked_worktree": got.linked_worktree,
    }
    emit(
        args,
        data,
        lambda: (
            f"{data['path']}: {data['repository'] or 'no repository that records a tier'}"
            + (f" is {data['tier']}" if data["tier"] else "")
        ),
    )
    return 0 if got.repo else 1


def cmd_tiers(args: argparse.Namespace, cfg: Config) -> int:
    """List every recorded tier and check the tier export; with --write, rewrite the export first.

    Returns:
        0 when the export is current and every external repository resolves, else 1.

    """
    repos, problems = tier_repos(cfg, Manifest(cfg.manifest, GitHub(cfg, use_cache=True)), discover(cfg)[0])
    out, differs = write_tier_export(cfg, check=not args.write)
    findings: list[dict[str, object]] = [
        {"repo": "-", "kind": "tier-external", "detail": p, "status": "open"} for p in problems
    ]
    if differs and not args.write:
        missing = not out.is_file()
        findings.append(
            {
                "repo": "-",
                "kind": "tier-export-missing" if missing else "tier-export-stale",
                "detail": f"{out} {'does not exist' if missing else 'differs from the manifest and the config'}",
                "status": "open",
            },
        )
    data: dict[str, object] = {
        "export": str(out),
        "written": differs and args.write,
        "repositories": [{"name": r.name, "path": str(r.path), "tier": r.tier, "source": r.source} for r in repos],
        "findings": findings,
        "open": len(findings),
    }
    emit(
        args,
        data,
        lambda: "\n".join(
            [f"{len(repos)} repositories record a tier; export {out}{' (rewritten)' if data['written'] else ''}"]
            + [f"  {r.tier:8} {r.name}  {r.path}" for r in repos]
            + [f"  [{f['kind']}] {f['detail']}" for f in findings],
        ),
    )
    return 1 if findings else 0


def cmd_set_tier(args: argparse.Namespace, cfg: Config) -> int:
    """Record a repository's tier in the manifest, log it, and commit it with the rewritten export.

    Returns:
        0.

    Raises:
        PolyrepoError: when the manifest has no entry for the repository.

    """
    man = Manifest(cfg.manifest, GitHub(cfg, use_cache=True))
    entry = man.entries().get(args.repo)
    if entry is None:
        msg = f"the manifest has no entry for {args.repo!r}"
        raise PolyrepoError(msg)
    before = entry.get("tier")
    data: dict[str, object] = {"repo": args.repo, "tier": args.tier, "was": before, "changed": before != args.tier}
    if before != args.tier:
        man.set_field(args.repo, "tier", args.tier, "lifecycle")
        man.save()
        note_change(cfg, "polyrepo set-tier", [f"{args.repo}: tier {before or '(none)'} -> {args.tier}"])
    finish_records(cfg, data)
    emit(
        args,
        data,
        lambda: (
            f"{args.repo}: tier {args.tier}"
            + ("" if data["changed"] else " (unchanged)")
            + "".join(_records_line(data))
        ),
    )
    return 0


# --------------------------------------------------------------------------------------------
# beads fleet list: `repos.additional` in the control repo's beads config. The beads
# fleet watcher watches the `.beads` folder of every path listed there, so the list must
# name every active repo that has one, and nothing else.

_FLEET_ITEM = re.compile(
    r"""^(?P<indent>\s*)-\s*(?P<q>["']?)(?P<path>[^"'#\s][^"'#]*?)(?P=q)\s*(?:#.*)?$""",
)


def fleet_file(cfg: Config) -> Path:
    """Return the beads config that holds the fleet list (config `beads.fleet_config`).

    Returns:
        The path; by default `.beads/config.yaml` beside the steward's folder.

    """
    return cfg.setting_path("beads", "fleet_config", "../.beads/config.yaml")


def _fleet_norm(base: Path, raw: str) -> str:
    return os.path.normpath(base / Path(raw).expanduser())


def _fleet_block(lines: list[str]) -> tuple[int, int] | None:
    """Find the item lines of `repos.additional`.

    Returns:
        (first line after `additional:`, one past its last item), or None when absent.

    """
    top = next(
        (i for i, ln in enumerate(lines) if re.match(r"^repos:\s*(#.*)?$", ln)),
        None,
    )
    if top is None:
        return None
    head = None
    for i in range(top + 1, len(lines)):
        if lines[i].strip() and not lines[i][0].isspace():
            break
        if re.match(r"^\s+additional:\s*(#.*)?$", lines[i]):
            head = i
            break
    if head is None:
        return None
    indent = len(lines[head]) - len(lines[head].lstrip())
    end = head + 1
    for i in range(head + 1, len(lines)):
        s = lines[i].strip()
        if not s or s.startswith("#"):
            continue
        cur = len(lines[i]) - len(lines[i].lstrip())
        if cur < indent or (cur == indent and not s.startswith("-")):
            break
        end = i + 1
    return head + 1, end


def fleet_paths(cfg: Config) -> dict[str, str]:
    """Read the fleet list.

    Returns:
        Each listed path, normalized and absolute, mapped to the entry as written.

    """
    f = fleet_file(cfg)
    if not f.is_file():
        return {}
    lines = f.read_text().splitlines()
    blk = _fleet_block(lines)
    if blk is None:
        return {}
    out = {}
    for ln in lines[blk[0] : blk[1]]:
        m = _FLEET_ITEM.match(ln)
        if m:
            out[_fleet_norm(f.parent.parent, m.group("path"))] = m.group("path")
    return out


type _FleetItem = tuple[int, str, str, re.Match[str]]


@dataclasses.dataclass
class _FleetDoc:
    """The fleet list file's lines and the parsed items of its `repos.additional` list."""

    path: Path
    base: Path
    lines: list[str]
    blk: tuple[int, int] | None
    items: list[_FleetItem]
    listed: set[str]

    @classmethod
    def read(cls, f: Path) -> _FleetDoc:
        """Read the fleet list file and parse its items.

        Returns:
            The parsed file.

        """
        base = f.parent.parent
        lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
        blk = _fleet_block([ln.rstrip("\n") for ln in lines])
        items: list[_FleetItem] = []
        if blk:
            for i in range(*blk):
                m = _FLEET_ITEM.match(lines[i].rstrip("\n"))
                if m:
                    items.append(
                        (i, _fleet_norm(base, m.group("path")), m.group("path"), m),
                    )
        return cls(f, base, lines, blk, items, {n for _, n, _, _ in items})

    def entry(self, p: Path) -> str:
        """Return the fleet list entry for a repo folder.

        Returns:
            The folder relative to the control repo, with a trailing slash.

        """
        return os.path.relpath(p, self.base).replace(os.sep, "/").rstrip("/") + "/"

    def rewrite(self, drop: set[str], swap: dict[str, Path]) -> tuple[dict[int, str], list[str]]:
        """Remove the dropped items and replace the swapped ones.

        Returns:
            The new text of every item line (empty when removed), and one line per change.

        """
        changes: list[str] = []
        out = {i: self.lines[i] for i, *_ in self.items}
        for i, n, raw, m in self.items:
            if n in drop:
                out[i] = ""
                changes.append(f"removed {raw}")
            elif n in swap and os.path.normpath(swap[n]) in self.listed:
                out[i] = ""
                changes.append(f"removed {raw} ({self.entry(swap[n])} is already listed)")
            elif n in swap:
                out[i] = f"{m.group('indent')}- {m.group('q')}{self.entry(swap[n])}{m.group('q')}\n"
                changes.append(f"replaced {raw} with {self.entry(swap[n])}")
        return out, changes

    def insertions(
        self,
        add: Iterable[Path],
        swap: dict[str, Path],
        kept: list[_FleetItem],
    ) -> tuple[dict[int, list[str]], list[str]]:
        """Place each added repo beside the kept entries in the same folder, in name order.

        Returns:
            The lines to insert before each line index, and one line per entry added.

        Raises:
            PolyrepoError: when an entry must be added and the file has no `repos.additional`.

        """
        before: dict[int, list[str]] = {}
        changes: list[str] = []
        for p in add:
            new, want = self.entry(p), os.path.normpath(p)
            if want in self.listed or want in {os.path.normpath(v) for v in swap.values()}:
                continue
            if self.blk is None:
                msg = f"{self.path} has no repos.additional list to add {new} to"
                raise PolyrepoError(msg)
            tmpl = kept[0][3] if kept else None
            line = (
                f"{tmpl.group('indent')}- {tmpl.group('q')}{new}{tmpl.group('q')}\n" if tmpl else f'        - "{new}"\n'
            )
            before.setdefault(_fleet_insert_at(kept, new, want, self.blk[1]), []).append(line)
            self.listed.add(want)
            changes.append(f"added {new}")
        return before, changes


def _fleet_insert_at(kept: list[_FleetItem], new: str, want: str, end: int) -> int:
    """Choose the line a new fleet entry goes before.

    Returns:
        Before the first later-named entry in the same folder, else after that folder's last
        entry, else after the last entry, else at the end of the list.

    """
    same = [k for k in kept if Path(k[1]).parent == Path(want).parent]
    later = [k for k in same if k[2].lower() > new.lower()]
    if later:
        return later[0][0]
    if same:
        return same[-1][0] + 1
    return kept[-1][0] + 1 if kept else end


def fleet_edit(
    cfg: Config,
    remove: Iterable[Path] = (),
    add: Iterable[Path] = (),
    replace: dict[Path, Path] | None = None,
) -> list[str]:
    """Remove, add or replace fleet list entries, editing the file's lines in place.

    The file is read immediately before it is written, so a concurrent edit to another
    entry is kept; comments and every other line are left as they are. A new entry goes
    beside the entries in the same folder, in name order. Adding to a file with no
    `repos.additional` propagates the PolyrepoError of `_FleetDoc.insertions`.

    Returns:
        One line per change made (none when the list already says it).

    """
    f = fleet_file(cfg)
    if not f.is_file():
        return []
    doc = _FleetDoc.read(f)
    swap = {os.path.normpath(o): n for o, n in (replace or {}).items()}
    out, changes = doc.rewrite({os.path.normpath(p) for p in remove}, swap)
    kept = [it for it in doc.items if out[it[0]]]
    before, added = doc.insertions(add, swap, kept)
    changes += added
    if not changes:
        return []
    text: list[str] = []
    for i, ln in enumerate(doc.lines):
        text.extend(before.get(i, []))
        text.append(out.get(i, ln))
    text.extend(before.get(len(doc.lines), []))
    f.write_text("".join(text))
    return changes


def fleet_after_rename(cfg: Config, old: Path, new: Path, active: bool) -> list[str]:
    """Keep the fleet list true after a repo folder moved from old to new.

    An active repo's entry is replaced in place (or added when it was missing and the repo
    has a `.beads` folder); a deprecated repo's entry is removed.

    Returns:
        One line per change made.

    """
    if not active:
        return fleet_edit(cfg, remove=[old, new])
    if old != new and os.path.normpath(old) in fleet_paths(cfg):
        return fleet_edit(cfg, replace={old: new})
    return fleet_edit(cfg, add=[new]) if (new / ".beads").is_dir() else []


# --------------------------------------------------------------------------------------------
# output


def emit(
    args: argparse.Namespace,
    data: Mapping[str, object],
    text: Callable[[], str],
) -> None:
    """Print JSON or text."""
    if args.json:
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
    else:
        sys.stdout.write(text() + "\n")


def _status_line(rec: dict[str, object]) -> str:
    parts = [f"{rec['name']}  [{rec['space'] or '-'}]  {rec['lifecycle']}"]
    if _map(rec["present"], "present")["disk"]:
        parts.extend((f"branch {rec['branch']}", f"uncommitted {rec['uncommitted']}"))
        lc = _map(rec["last_commit"] or {}, "last_commit")
        if lc:
            parts.append(
                f"last {str(lc['date'])[:10]} {str(lc['sha'])[:8]} {str(lc['subject'])[:60]!r}",
            )
        m = _map(rec["main"] or {}, "main")
        if m and m["fetch_error"]:
            parts.append(f"fetch failed: {m['fetch_error']}")
        elif m and m["ahead"] is not None:
            parts.append(
                "main = origin/main" if m["up_to_date"] else f"main +{m['ahead']}/-{m['behind']} vs origin/main",
            )
        elif m and m["sha"] and not m["origin_sha"]:
            parts.append("main not on origin")
    else:
        parts.append("not on disk")
    g = _map(rec["github"] or {}, "github")
    if g:
        parts.append(
            f"GitHub pushed {str(g['pushed_at'])[:10]}{' archived' if g['archived'] else ''}",
        )
    else:
        parts.append("not on GitHub")
    return "  ".join(parts)


# --------------------------------------------------------------------------------------------
# commands


def resolve_names(
    known: Iterable[str],
    local: dict[str, LocalRepo],
    wanted: list[str],
) -> list[str]:
    """Resolve repo names (any case) or paths inside a repo to known repo names.

    Returns:
        Canonical names, in the order given.

    Raises:
        PolyrepoError: when an argument names no known repo.

    """
    lower = {n.lower(): n for n in known}
    out = []
    for w in wanted:
        n = lower.get(w.lower())
        p = Path(w).expanduser()
        if n is None and p.exists():
            p = p.resolve()
            n = next(
                (k for k, r in local.items() if r.path == p or r.path in p.parents),
                None,
            )
        if n is None:
            msg = f"no repo named {w!r}"
            raise PolyrepoError(msg)
        out.append(n)
    return out


def cmd_reconcile(args: argparse.Namespace, cfg: Config) -> int:
    """Compare disk, GitHub and the manifest; with --fix, repair every mechanical finding.

    Returns:
        0 when no finding is left open, else 1.

    """
    t0 = time.time()
    st = gather(cfg, fetch=not args.no_fetch, use_cache=not args.no_cache)
    findings = reconcile(st)
    if args.fix:
        apply_fixes(st, findings, args.dry_run)
    open_ = [f for f in findings if f.status in {"open", "failed", "planned"}]
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    data = {
        "root": str(cfg.root),
        "repos_on_disk": len(st.local),
        "manifest_entries": len(st.manifest.entries()),
        "findings": [f.as_dict() for f in findings],
        "counts": counts,
        "open": len(open_),
        "fixed": sum(f.status == "fixed" for f in findings),
        "elapsed_s": round(time.time() - t0, 1),
    }
    finish_records(cfg, data)

    def text() -> str:
        lines = [
            (
                f"{len(st.local)} repos on disk, {len(st.manifest.entries())} manifest entries, "
                f"{len(findings)} findings ({data['fixed']} fixed) in {data['elapsed_s']}s"
            ),
        ]
        for f in findings:
            tag = f.status if f.status != "open" else ("fixable" if f.fix else "judgment")
            lines.append(
                f"  [{f.kind}] {f.repo}: {f.detail}  ({tag}{': ' + f.fix if f.fix else ''})",
            )
            if f.error:
                lines.append(f"      error: {f.error}")
        return "\n".join([*lines, *_records_line(data)])

    emit(args, data, text)
    return 1 if open_ else 0


def _records_line(data: Mapping[str, object]) -> list[str]:
    rec = _map(data.get("records") or {}, "records")
    if not rec:
        return []
    err = f": {rec['error']}" if rec.get("error") else ""
    return [f"steward files {rec['status']}{err}"]


def cmd_status(args: argparse.Namespace, cfg: Config) -> int:
    """Report live git and GitHub state for the named repos, or all of them.

    Returns:
        0.

    """
    st = gather(cfg, fetch=not args.no_fetch, use_cache=not args.no_cache)
    names = st.resolve(args.repos) if args.repos else sorted(st.local, key=str.lower)
    recs = [st.record(n, deep=False) for n in names]

    def text() -> str:
        lines = []
        for rec in recs:
            lines.append(_status_line(rec))
            if args.repos:
                lines.extend(f"    {f}" for f in _strs(rec["uncommitted_files"] or [], "uncommitted_files"))
        return "\n".join(lines)

    emit(args, {"repos": recs}, text)
    return 0


def cmd_inventory(args: argparse.Namespace, cfg: Config) -> int:
    """Report the full record of every repo on disk, with the matrix's stacks for each.

    --all adds every other repo the manifest records. --name keeps only the repo with that
    name, compared without case; `repos` is empty when no repo has it. Deprecated and archived
    repos are left out unless --include-inactive is given or --name names one.

    Returns:
        0.

    """
    st = gather(cfg, fetch=not args.no_fetch, use_cache=not args.no_cache)
    names = st.tracked_names() if args.all else sorted(st.local, key=str.lower)
    if args.name:
        names = [n for n in names if n.casefold() == args.name.casefold()]
    recs = [st.record(n) for n in names]
    if not (args.include_inactive or args.name):
        recs = [r for r in recs if r["lifecycle"] not in LIFECYCLES_INACTIVE]
    data = {
        "root": str(cfg.root),
        "count": len(recs),
        "on_disk": len(st.local),
        "repos": recs,
    }
    emit(args, data, lambda: "\n".join(_status_line(r) for r in recs))
    return 0


def _wants_inactive(args: argparse.Namespace) -> bool:
    """Say whether a listing should include deprecated and archived repos.

    A listing hands batch work its list of repos, so it holds active repos only unless the
    caller asks for the inactive ones with --include-inactive or names a lifecycle.

    Returns:
        True when deprecated and archived repos belong in the listing.

    """
    return bool(getattr(args, "include_inactive", False) or getattr(args, "lifecycle", None))


def cmd_list(args: argparse.Namespace, cfg: Config) -> int:
    """List repos, filtered by group, lifecycle or space; active repos unless asked otherwise.

    Returns:
        0.

    """
    st = gather(cfg, fetch=False, use_cache=not args.no_cache)
    recs = [st.record(n, deep=False) for n in st.tracked_names()]
    if not _wants_inactive(args):
        recs = [r for r in recs if r["lifecycle"] not in LIFECYCLES_INACTIVE]
    if args.group:
        recs = [r for r in recs if args.group in _strs(r["groups"], "groups")]
    if args.lifecycle:
        recs = [r for r in recs if r["lifecycle"] == args.lifecycle]
    if args.space:
        recs = [r for r in recs if r["space"] == args.space]
    rows = [
        {
            "name": r["name"],
            "space": r["space"],
            "lifecycle": r["lifecycle"],
            "tier": r["tier"],
            "path": r["path"],
        }
        for r in recs
    ]
    emit(
        args,
        {"count": len(rows), "repos": rows},
        lambda: "\n".join(f"{r['name']}  [{r['space'] or '-'}]  {r['lifecycle']}  {r['tier'] or '-'}" for r in rows),
    )
    return 0


def _lookup(rec: dict[str, object], attr: str) -> object:
    cur: object = rec
    for part in attr.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _matches(value: object, op: str, want: str) -> bool:
    if isinstance(value, list):
        return any(_matches(v, op, want) for v in value)
    if isinstance(value, dict):
        return any(_matches(v, op, want) for v in value.values())
    s = "" if value is None else str(value).lower()
    if op == "~":
        return re.search(want, "" if value is None else str(value), re.IGNORECASE) is not None
    return s == want.lower()


def cmd_search(args: argparse.Namespace, cfg: Config) -> int:
    """Find repos whose record matches every attr=value (equality) or attr~regex term.

    Deprecated and archived repos are left out unless --include-inactive is given or a term
    names the lifecycle.

    Returns:
        0.

    Raises:
        PolyrepoError: when a term has neither = nor ~.

    """
    terms = []
    for t in args.terms:
        m = re.match(r"^([A-Za-z0-9_.]+)(=|~)(.*)$", t)
        if not m:
            msg = f"search term {t!r} is not attr=value or attr~regex"
            raise PolyrepoError(msg)
        terms.append(m.groups())
    st = gather(cfg, fetch=args.fetch, use_cache=not args.no_cache)
    deep = any(a.split(".")[0] == "stacks" for a, _, _ in terms)
    recs = [st.record(n, deep=deep) for n in st.tracked_names()]
    if not (args.include_inactive or any(a == "lifecycle" for a, _, _ in terms)):
        recs = [r for r in recs if r["lifecycle"] not in LIFECYCLES_INACTIVE]
    hits = [r for r in recs if all(_matches(_lookup(r, a), op, v) for a, op, v in terms)]
    emit(
        args,
        {"count": len(hits), "repos": hits},
        lambda: "\n".join(_status_line(r) for r in hits),
    )
    return 0


# --------------------------------------------------------------------------------------------
# actions: grep, rebase, create, deprecate, agents-sync, templates-check

REBASE_OK = ("up-to-date", "rebased", "fast-forwarded")


def _local_repos(
    cfg: Config,
    names: list[str] | None = None,
    space: str | None = None,
) -> list[LocalRepo]:
    """Return the repos on disk, optionally narrowed to names (or paths) and one app space.

    A name that is not a repo on disk propagates the PolyrepoError of `resolve_names`.

    Returns:
        The repos, sorted by name.

    """
    local, _ = discover(cfg)
    picked = [local[n] for n in resolve_names(local, local, names)] if names else list(local.values())
    if space:
        picked = [r for r in picked if r.space == space]
    return sorted(picked, key=lambda r: r.name.lower())


# grep -----------------------------------------------------------------------------------------


def cmd_grep(args: argparse.Namespace, cfg: Config) -> int:
    """Search every repo on disk (or one space, or named repos) with rg.

    Returns:
        rg's status: 0 matches, 1 no match.

    Raises:
        PolyrepoError: when there is nothing to search or rg fails.

    """
    repos = _local_repos(cfg, args.repo, args.space)
    if not repos:
        msg = "no repos to search"
        raise PolyrepoError(msg)
    rels = {r.path.relative_to(cfg.root).as_posix(): r.name for r in repos}
    cp = run(_rg_argv(args, list(rels)), cwd=cfg.root, timeout=300)
    if cp.returncode not in {0, 1}:
        msg = f"rg failed: {_last_line(cp)}"
        raise PolyrepoError(msg)
    if not args.json:
        sys.stdout.write(cp.stdout)
        return cp.returncode
    matches = _rg_matches(cp.stdout, rels)
    if args.files:
        files = sorted({(m["repo"], m["file"]) for m in matches}, key=str)
        data: dict[str, object] = {
            "count": len(files),
            "files": [{"repo": r, "file": f} for r, f in files],
        }
    else:
        data = {"count": len(matches), "matches": matches}
    sys.stdout.write(json.dumps(data, indent=2) + "\n")
    return 0 if matches else 1


def _rg_argv(args: argparse.Namespace, rels: list[str]) -> list[str]:
    """Build the rg command line for a grep over the repo folders rels.

    Returns:
        The argv.

    """
    argv = ["rg", "--no-config", "--color=never", "--glob", "!.worktrees"]
    for g in args.glob or []:
        argv += ["--glob", g]
    for flag, on in (
        ("-i", args.ignore_case),
        ("-F", args.fixed_strings),
        ("-w", args.word),
    ):
        if on:
            argv.append(flag)
    if args.json:
        argv.append("--json")
    elif args.files:
        argv.append("--files-with-matches")
    else:
        argv += ["--line-number", "--with-filename"]
    argv += ["-e", args.pattern, "--", *rels]
    return argv


def _rg_matches(stdout: str, rels: dict[str, str]) -> list[dict[str, object]]:
    """Parse rg --json output into one record per matching line.

    Returns:
        One {repo, file, line, text} per match.

    """
    matches: list[dict[str, object]] = []
    for ln in stdout.splitlines():
        ev = json.loads(ln)
        if ev.get("type") != "match":
            continue
        d = ev["data"]
        rel = d["path"].get("text", "")
        top = next((k for k in rels if rel.startswith(k + "/")), None)
        matches.append(
            {
                "repo": rels[top] if top else None,
                "file": rel[len(top) + 1 :] if top else rel,
                "line": d["line_number"],
                "text": d["lines"].get("text", "").rstrip("\n"),
            },
        )
    return matches


# rebase ---------------------------------------------------------------------------------------


def _worktree_on(repo: Path, branch: str) -> Path | None:
    """Return the worktree that has the branch checked out.

    Returns:
        Its path, or None when no worktree has it.

    """
    cur: Path | None = None
    for ln in (git_out(repo, "worktree", "list", "--porcelain") or "").splitlines():
        if ln.startswith("worktree "):
            cur = Path(ln[len("worktree ") :])
        elif ln == f"branch refs/heads/{branch}" and cur is not None:
            return cur
    return None


def rebase_one(cfg: Config, r: LocalRepo) -> dict[str, object]:
    """Fetch origin and bring main up to origin/main, stopping on a dirty tree or a conflict.

    Returns:
        {repo, status, ...}; status is one of REBASE_OK or the reason it stopped.

    """
    b = cfg.default_branch
    res: dict[str, object] = {"repo": r.name, "path": str(r.path)}
    if not git_out(r.path, "remote", "get-url", "origin"):
        return {**res, "status": "no-origin"}
    err = fetch_origin(r.path)
    if err:
        return {**res, "status": "fetch-failed", "detail": err}
    main, om, a, bh = main_vs_origin(r.path, b)
    if not main or not om:
        return {**res, "status": "no-main", "detail": f"no {b} or no origin/{b}"}
    ahead, behind = a or 0, bh or 0
    res.update(ahead=ahead, behind=behind)
    if behind == 0:
        return {**res, "status": "up-to-date"}
    return _advance_main(r, b, res, (main, om))


def _advance_main(r: LocalRepo, b: str, res: dict[str, object], refs: tuple[str, str]) -> dict[str, object]:
    """Bring a main that is behind origin/main up to it, where it is checked out or not.

    `refs` is (main, origin/main) as commit ids; res carries ahead and behind.

    Returns:
        res with the status, and the worktree when main is checked out.

    """
    wt = _worktree_on(r.path, b)
    if wt is None:
        return _advance_unchecked_out(r, b, res, refs)
    res["worktree"] = str(wt)
    dirty = git(wt, "status", "--porcelain=v1", "--untracked-files=no").stdout
    if dirty.strip():
        return {
            **res,
            "status": "dirty",
            "files": [ln[3:] for ln in dirty.splitlines() if ln.strip()],
        }
    if res["ahead"] == 0:
        cp = git(wt, "merge", "--ff-only", "--quiet", f"refs/remotes/origin/{b}")
        if cp.returncode != 0:
            return {**res, "status": "failed", "detail": _last_line(cp)}
        return {**res, "status": "fast-forwarded", "behind": 0}
    cp = git(wt, "rebase", f"refs/remotes/origin/{b}", timeout=300)
    if cp.returncode != 0:
        conflicts = git_out(wt, "diff", "--name-only", "--diff-filter=U") or ""
        git(wt, "rebase", "--abort")
        return {
            **res,
            "status": "conflict",
            "files": conflicts.splitlines(),
            "detail": "rebase aborted; main is as it was",
        }
    return {**res, "status": "rebased", "behind": 0}


def _advance_unchecked_out(r: LocalRepo, b: str, res: dict[str, object], refs: tuple[str, str]) -> dict[str, object]:
    """Fast-forward a main no worktree has checked out, unless it has diverged.

    Returns:
        res with the status.

    """
    main, om = refs
    if res["ahead"]:
        return {
            **res,
            "status": "not-checked-out",
            "detail": f"{b} has diverged and is not checked out in any worktree",
        }
    cp = git(r.path, "update-ref", f"refs/heads/{b}", om, main)
    if cp.returncode != 0:
        return {**res, "status": "failed", "detail": _last_line(cp)}
    return {**res, "status": "fast-forwarded", "behind": 0}


def cmd_rebase(args: argparse.Namespace, cfg: Config) -> int:
    """Rebase main on origin/main in the named repos, or all of them.

    Returns:
        0 when every repo ended up to date, else 1.

    Raises:
        PolyrepoError: when neither repos nor --all are given.

    """
    if not args.repos and not args.all:
        msg = "name one or more repos, or pass --all"
        raise PolyrepoError(msg)
    repos = _local_repos(cfg, None if args.all else args.repos)
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(lambda r: rebase_one(cfg, r), repos))
    bad = [x for x in results if x["status"] not in REBASE_OK]

    def text() -> str:
        lines = []
        for x in results:
            extra = "; ".join(
                s for s in (str(x.get("detail") or ""), ", ".join(_strs(x.get("files") or [], "files"))) if s
            )
            lines.append(f"{x['repo']}: {x['status']}{'  ' + extra if extra else ''}")
        return "\n".join(lines)

    emit(args, {"repos": results, "stopped": len(bad)}, text)
    return 1 if bad else 0


# create ---------------------------------------------------------------------------------------


def _templates(cfg: Config) -> tuple[Path, dict[str, object]]:
    """Return the templates folder and the templates settings.

    Returns:
        (folder, settings).

    """
    return (
        cfg.setting_path("templates", "dir", "../repositories/templates"),
        _map(cfg.raw.get("templates") or {}, "config templates"),
    )


def _service_name(cfg: Config, name: str) -> str:
    """Return the template's service_name: the repo name without its project prefix.

    The prefix is the first token of a name an application naming pattern matches, so every
    project (SkillSpoke-, shared-, marketing-, employer-) is stripped the same way, and the
    camelCase domain keeps its case because the templates' validators require it.

    Returns:
        The name after the project prefix, or the name unchanged when no application
        pattern matches it.

    """
    pattern = cfg.classify(name)
    if pattern and pattern.get("kind") == "application" and "-" in name:
        return name.split("-", 1)[1]
    return name


def _template_data(cfg: Config, name: str) -> dict[str, str]:
    """Build the answers a template is rendered with: the names, each given by `atw-naming`.

    A template holds no naming rule of its own. The import package (`package_name`, dotted),
    its folder under `src` (`package_path`), the distribution (`distribution_name`) and the
    stack module (`stack_module_name`) are what `atw-naming name` prints for the repository.

    Returns:
        The answers; the Python names are left out for a name that is not
        `{prefix}[-team]-{domain}-{type}`, so a template that needs them then refuses to render.

    Raises:
        PolyrepoError: when `atw-naming` refuses a name of a repository that parses.

    """
    data = {"service_name": _service_name(cfg, name), "repo_name": name}
    parts = parse_repo_name(name)
    if parts is None:
        return data
    namer = _namer(cfg)
    try:
        data["package_name"] = namer(["name", "python-package", "--repository", name])
        data["package_path"] = namer(["name", "python-package-path", "--repository", name]).removeprefix("src/")
        data["distribution_name"] = namer(["name", "python-distribution", "--repository", name])
        data["stack_module_name"] = stack_module(parts, namer)
    except NameSweepError as exc:
        raise PolyrepoError(str(exc)) from exc
    return data


def _copier_render(
    tdir: Path,
    dest: Path,
    data: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    argv = ["copier", "copy", "--defaults", "--quiet"]
    for k, v in data.items():
        argv += ["--data", f"{k}={v}"]
    return run([*argv, str(tdir), str(dest)], timeout=300)


def _exclude_worktrees(repo: Path) -> None:
    """Add `.worktrees/` to the repo's `.git/info/exclude`; its worktrees live there."""
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    text = exclude.read_text() if exclude.exists() else ""
    if WORKTREES_LINE in text.splitlines():
        return
    sep = "" if not text or text.endswith("\n") else "\n"
    exclude.write_text(f"{text}{sep}{WORKTREES_LINE}\n")


def _kind_types(spec: object) -> list[str]:
    """Return the repository types (the last token of a name) a template kind builds.

    Returns:
        The `types` of the kind in the config; none when the kind lists none.

    """
    return _strs(_map(spec or {}, "template kind").get("types") or [], "template kind types")


def _template_of_name(cfg: Config, name: str) -> str:
    """Name the template a repo is created from, from the template whose types include the type of its name.

    Returns:
        The template's name.

    Raises:
        PolyrepoError: when no template builds the type of the name.

    """
    kinds = _map(_templates(cfg)[1].get("kinds") or {}, "templates kinds")
    for kind, spec in kinds.items():
        if type_of(name) in _kind_types(spec):
            return str(kind)
    msg = f"no template builds the type {type_of(name)} of {name}"
    raise PolyrepoError(msg)


def _create_checks(args: argparse.Namespace, cfg: Config) -> tuple[Path, Path]:
    """Validate a create request against the naming rules, the templates, disk and GitHub.

    Returns:
        (template folder, destination folder).

    Raises:
        PolyrepoError: when the request breaks a rule or the name is taken.

    """
    name, space, template = args.name, args.space, args.template
    pat = cfg.classify(name)
    if pat is None or pat["kind"] != "application":
        msg = f"{name} is refused as an application repository: {cfg.naming_problem(name)}"
        raise PolyrepoError(msg)
    want = cfg.expected_space(name)
    if want != space:
        msg = f"a {pat['name']} repo belongs in space {want}, not {space}"
        raise PolyrepoError(msg)
    troot, tset = _templates(cfg)
    tdir = troot / template
    if not (tdir / "copier.yml").is_file():
        msg = f"no template {template!r} in {troot}"
        raise PolyrepoError(msg)
    types = _kind_types(_map(tset.get("kinds") or {}, "templates kinds").get(template))
    if types and type_of(name) not in types:
        msg = f"a {template} repo name must end in one of {', '.join(types)}"
        raise PolyrepoError(msg)
    sub = args.dir
    if sub is None:
        sub = cfg.placement_folder(space, name)
    space_dir = cfg.root / space
    dest = space_dir / sub / name if sub else space_dir / name
    local, _ = discover(cfg)
    if dest.exists() or name.lower() in {n.lower() for n in local}:
        msg = f"{name} already exists on disk"
        raise PolyrepoError(msg)
    _require_new_name(cfg, name)
    return tdir, dest


def _require_new_name(cfg: Config, name: str) -> None:
    """Refuse a name GitHub or the manifest already has.

    Raises:
        PolyrepoError: when a repository of the owner, or a manifest entry, has the name.

    """
    gh = GitHub(cfg, use_cache=False)
    if gh.resolve(name) is not None:
        msg = f"{cfg.owner}/{name} already exists on GitHub"
        raise PolyrepoError(msg)
    if name in Manifest(cfg.manifest, gh).entries():
        msg = f"{name} already has a manifest entry"
        raise PolyrepoError(msg)


def cmd_create(args: argparse.Namespace, cfg: Config) -> int:
    """Create a repo from a template, on disk and on GitHub, with its manifest entry and its stack.

    Returns:
        0 on success, 1 when a step after rendering failed.

    Raises:
        PolyrepoError: when the request is invalid or the template does not render.

    """
    name, b = args.name, cfg.default_branch
    args.template = args.template or _template_of_name(cfg, name)
    tdir, dest = _create_checks(args, cfg)
    data = _template_data(cfg, name)
    res: dict[str, object] = {
        "repo": name,
        "space": args.space,
        "template": args.template,
        "path": str(dest),
        "dry_run": args.dry_run,
        "steps": [
            f"render the {args.template} template into {dest}",
            "write the shared AGENTS.md blocks, including GitNexus",
            "install GitNexus: .gitnexusrc, the .gitnexus ignore rule and .claude/skills/gitnexus/",
            f"git init on {b}, exclude {WORKTREES_LINE} locally",
            (
                "run the template's setup task (task install) and verify .venv/bin/python, "
                "every declared dependency, and for an infra template cdk synth --profile dev; "
                "then commit"
            ),
            f"create the private GitHub repo {cfg.owner}/{name} and push {b}",
            f"add the manifest entry (lifecycle {args.lifecycle}, tier {args.tier or default_tier(cfg, name)})",
            "record the repo's stack in the matrix when its name ends in a stack type (purpose not stated)",
            "set up beads: .beads config files, shared-server database, standard .gitignore; commit and push",
            "add it to the beads fleet list (repos.additional)",
            "index it once with the pinned GitNexus (gitnexus-reindex.sh)",
        ],
    }
    if args.dry_run:
        return _create_dry_run(args, tdir, dest, data, res)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cp = _copier_render(tdir, dest, data)
    if cp.returncode != 0:
        msg = f"copier failed: {_last_line(cp)}"
        raise PolyrepoError(msg)
    agents = dest / "AGENTS.md"
    agents.write_text(
        _with_blocks(
            agents.read_text() if agents.exists() else None,
            _blocks_for(_agents_blocks(cfg), name, args.space),
            name,
        ),
    )
    try:
        _create_scaffold(args, cfg, dest, res)
    except GitFailedError as exc:
        res["error"] = str(exc)
        emit(
            args,
            res,
            lambda: f"{name}: created at {dest} but stopped: {res['error']}",
        )
        return 1
    code = _create_records(args, cfg, dest, res)
    emit(
        args,
        res,
        lambda: "\n".join(
            [
                f"{name}: created at {dest} and pushed to GitHub"
                + (f"; environment setup failed: {res['environment_error']}" if res.get("environment_error") else "")
                + (f"; matrix update failed: {res['matrix_error']}" if res.get("matrix_error") else "")
                + (f"; beads setup failed: {res['beads_error']}" if res.get("beads_error") else "")
                + (f"; GitNexus index failed: {res['gitnexus_error']}" if res.get("gitnexus_error") else ""),
                *_records_line(res),
            ],
        ),
    )
    return code


def _create_dry_run(
    args: argparse.Namespace,
    tdir: Path,
    dest: Path,
    data: dict[str, str],
    res: dict[str, object],
) -> int:
    """Render the template into a temporary folder and report the plan, changing nothing.

    Returns:
        0.

    Raises:
        PolyrepoError: when the template does not render.

    """
    name = args.name
    with tempfile.TemporaryDirectory(prefix="polyrepo-create-") as tmp:
        out = Path(tmp) / name
        cp = _copier_render(tdir, out, data)
        if cp.returncode != 0:
            msg = f"copier failed: {_last_line(cp)}"
            raise PolyrepoError(msg)
        res["rendered_files"] = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    emit(
        args,
        res,
        lambda: "\n".join(
            [f"dry run: {name} -> {dest}"]
            + [f"  {s}" for s in _strs(res["steps"], "steps")]
            + [f"  template renders {len(_seq(res['rendered_files'], 'rendered_files'))} files"],
        ),
    )
    return 0


def _create_scaffold(args: argparse.Namespace, cfg: Config, dest: Path, res: dict[str, object]) -> None:
    """Initialise the rendered repo, set up its environment, commit it and create it on GitHub.

    The environment result is recorded in res; a failed git or gh step propagates as the
    GitFailedError that `must` raises.
    """
    name, b = args.name, cfg.default_branch
    must(git(dest, "init", f"--initial-branch={b}"))
    _exclude_worktrees(dest)
    # Before the first commit, so the lockfile the setup task writes is committed too.
    if env_applicable(dest):
        tspec = _map(
            _map(_templates(cfg)[1].get("kinds") or {}, "templates kinds").get(args.template) or {},
            "template kind",
        )
        synth = bool(tspec.get("synth", args.template in ENV_SYNTH_KINDS))
        env_res = setup_environment(dest, synth)
        res["environment"] = env_res
        if env_res["problems"]:
            res["environment_error"] = "; ".join(env_res["problems"])
    res["gitnexus_files"] = gitnexus_install(cfg, dest)
    must(git(dest, "add", "-A"))
    must(
        git(
            dest,
            "commit",
            "-m",
            f"chore(repo): scaffold {name} from the {args.template} template",
            timeout=300,
        ),
    )
    create_on_github(cfg, name, dest)
    failure = gitnexus_index(cfg, dest)
    if failure:
        res["gitnexus_error"] = failure


def _create_stack_records(cfg: Config, name: str, space: str) -> list[str]:
    """Record in the matrix the stack the new repo holds, when it holds one (S1).

    A repo holds a stack when its name ends in a stack type the naming rules list. A repo that
    some stack already names as its repository is left as it is. The matrix file is committed after a change.

    Returns:
        One sentence for each thing done or left.

    """
    known = read_matrix_stacks(cfg)
    held = [s.id for s in known if s.repository == name]
    if held:
        return [f"matrix: {', '.join(held)} already name {name} as their repository"]
    if not holds_stack(name, stack_types(cfg)):
        return [f"matrix: no stack recorded; {name} ends in no stack type"]
    return [record_stack(cfg, name, space, known), matrix_commit(cfg)]


def _create_records(args: argparse.Namespace, cfg: Config, dest: Path, res: dict[str, object]) -> int:
    """Add the new repo's manifest entry, record its stack in the matrix, set up its beads, log it, and commit.

    Returns:
        0, or 1 when the environment, matrix or beads setup failed.

    """
    name = args.name
    man = Manifest(cfg.manifest, GitHub(cfg, use_cache=False))
    man.add_entry(name, entry_fields(cfg, name, args.lifecycle, {"tier": args.tier} if args.tier else None))
    man.save()
    log = [
        f"{name}: created in {args.space} from the {args.template} template and pushed to {cfg.owner}/{name}",
    ]
    code = 0
    try:
        stack_log = _create_stack_records(cfg, name, args.space)
        res["matrix"] = stack_log
        log.extend(stack_log)
    except PolyrepoError as exc:
        res["matrix_error"] = str(exc)
        log.append(f"matrix update FAILED: {exc}")
        code = 1
    if res.get("environment_error"):
        log.append(f"environment setup FAILED: {res['environment_error']}")
        code = 1
    elif res.get("environment"):
        log.append(f"environment set up: {'; '.join(_strs(_map(res['environment'], 'environment')['steps'], 'steps'))}")
    if res.get("gitnexus_error"):
        log.append(f"GitNexus index FAILED: {res['gitnexus_error']}")
        code = 1
    elif res.get("gitnexus_files") is not None:
        log.append("GitNexus installed and indexed once with the pinned version")
    if args.lifecycle not in LIFECYCLES_INACTIVE:
        try:
            done = beads_setup(
                cfg,
                LocalRepo(name=name, path=dest, space=args.space),
                None,
            )
            log.append(f"beads set up: {'; '.join(_strs(done['steps'], 'steps')) or 'already set up'}")
            log.extend(f"beads fleet list: {c}" for c in fleet_edit(cfg, add=[dest]))
        except (GitFailedError, OSError, PolyrepoError) as exc:
            res["beads_error"] = str(exc)
            log.append(f"beads setup FAILED: {exc}")
            code = 1
    note_change(cfg, "polyrepo create", log)
    GitHub(cfg, use_cache=True).invalidate()
    finish_records(cfg, res)
    return code


# development environment -------------------------------------------------------------------------
# Creating a repo ends with a working environment: the template's setup task has run,
# `.venv/bin/python` runs, every declared dependency is installed and importable, and for an
# infra template `cdk synth --profile dev` succeeds. `doctor` reports a repo that lost any of it.

ENV_SYNTH_KINDS = ("infra",)
ENV_SETUP_TIMEOUT = 1800
ENV_SYNTH_TIMEOUT = 900
ENV_PROBE = r"""
import importlib, importlib.metadata as md, json, os, re, sys, tomllib

repo = sys.argv[1]
JUNK = {"dist", "build", "tests", "test", "docs", "examples"}
out = {"missing": [], "failed": [], "needs_cdk": False, "cdk_ok": True}


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


try:
    with open(os.path.join(repo, "pyproject.toml"), "rb") as f:
        py = tomllib.load(f)
except Exception as exc:
    out["error"] = f"cannot read pyproject.toml: {exc}"
    print(json.dumps(out))
    sys.exit(0)
proj = py.get("project", {})
reqs = list(proj.get("dependencies", []))
for v in (proj.get("optional-dependencies") or {}).values():
    reqs += v
for v in (py.get("dependency-groups") or {}).values():
    reqs += [x for x in v if isinstance(x, str)]
reqs += py.get("tool", {}).get("uv", {}).get("dev-dependencies") or []
own = norm(proj.get("name", ""))
try:
    from packaging.requirements import Requirement
except Exception:
    Requirement = None
names = []
for r in reqs:
    if Requirement is not None:
        try:
            q = Requirement(r)
        except Exception:
            continue
        if q.marker is not None and not q.marker.evaluate({"extra": ""}):
            continue
        n = q.name
    else:
        if ";" in r:
            continue
        m = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", r.strip())
        if not m:
            continue
        n = m.group(0)
    if norm(n) != own and norm(n) not in names:
        names.append(norm(n))
mods = {}
for mod, dists in md.packages_distributions().items():
    for d in dists:
        mods.setdefault(norm(d), []).append(mod)
for n in names:
    try:
        md.distribution(n)
    except md.PackageNotFoundError:
        out["missing"].append(n)
        continue
    for mod in sorted(mods.get(n, [])):
        if mod.startswith("_") or not mod.isidentifier() or mod in JUNK:
            continue
        try:
            importlib.import_module(mod)
        except BaseException as exc:
            out["failed"].append(f"{mod}: {type(exc).__name__}: {exc}"[:200])
skip = {".venv", "node_modules", "cdk.out", ".git", ".worktrees", "dist", "build"}
pat = re.compile(r"^\s*(import aws_cdk|from aws_cdk)", re.M)
for root, dirs, files in os.walk(repo):
    dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
    for f in files:
        if f.endswith(".py"):
            try:
                with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                    if pat.search(fh.read()):
                        out["needs_cdk"] = True
            except OSError:
                pass
    if out["needs_cdk"]:
        break
if out["needs_cdk"]:
    try:
        importlib.import_module("aws_cdk")
    except BaseException as exc:
        out["cdk_ok"] = False
        out["cdk_error"] = f"{type(exc).__name__}: {exc}"[:200]
print(json.dumps(out))
"""


def _tail(cp: subprocess.CompletedProcess[str], n: int = 4) -> str:
    lines = [ln for ln in (cp.stderr + "\n" + cp.stdout).splitlines() if ln.strip()]
    return " | ".join(ln.strip() for ln in lines[-n:]) or f"exit {cp.returncode}"


def env_applicable(path: Path) -> bool:
    """Tell whether the repo is a Python repo whose Taskfile declares an `install` task.

    Returns:
        True when it has a `pyproject.toml` and an `install` task.

    """
    if not (path / "pyproject.toml").is_file():
        return False
    for name in ("Taskfile.yml", "Taskfile.yaml"):
        tasks = _read_yaml(path / name).get("tasks")
        if isinstance(tasks, dict) and "install" in tasks:
            return True
    return False


def probe_environment(path: Path) -> list[str]:
    """Check a repo's environment without changing anything.

    Returns:
        One line per problem: a missing or broken `.venv/bin/python`, declared dependencies
        not installed or not importable, `aws_cdk` imported by the code but not importable.

    """
    py = path / ".venv" / "bin" / "python"
    if not py.is_file():
        return [".venv/bin/python is missing"]
    ver = run([str(py), "--version"], timeout=30)
    if ver.returncode != 0:
        return [f".venv/bin/python does not run: {_tail(ver)}"]
    cp = run([str(py), "-I", "-c", ENV_PROBE, str(path)], timeout=600)
    try:
        data = json.loads(cp.stdout.strip().splitlines()[-1])
    except IndexError, ValueError:
        return [f"environment probe failed: {_tail(cp)}"]
    problems: list[str] = []
    if data.get("error"):
        problems.append(data["error"])
    if data["missing"]:
        problems.append(
            "declared dependencies not installed: " + ", ".join(data["missing"]),
        )
    if data["failed"]:
        problems.append("installed but not importable: " + "; ".join(data["failed"]))
    if data["needs_cdk"] and not data["cdk_ok"]:
        problems.append(
            f"aws_cdk is imported by the code but not importable: {data.get('cdk_error')}",
        )
    return problems


def setup_environment(path: Path, synth: bool) -> EnvResult:
    """Run the repo's `install` task, then verify the environment (and `cdk synth --profile dev`).

    Returns:
        {"steps": [...], "problems": [...]}; empty problems means the environment holds.

    """
    steps: list[str] = []
    problems: list[str] = []
    if shutil.which("task") is None:
        return EnvResult(steps=steps, problems=["the task binary is not on PATH"])
    cp = run(
        ["task", "--dir", str(path), "install"],
        timeout=ENV_SETUP_TIMEOUT,
        env={"VIRTUAL_ENV": None},
    )
    if cp.returncode != 0:
        problems.append(f"task install failed: {_tail(cp)}")
    else:
        steps.append("ran task install")
    problems.extend(probe_environment(path))
    if not problems:
        steps.append("verified .venv/bin/python, dependencies and imports")
    if synth and not problems:
        cp = run(
            ["npx", "cdk", "synth", "--profile", "dev", "--quiet"],
            cwd=path,
            timeout=ENV_SYNTH_TIMEOUT,
            env={"VIRTUAL_ENV": None},
        )
        if cp.returncode != 0:
            problems.append(f"cdk synth --profile dev failed: {_tail(cp)}")
        else:
            steps.append("cdk synth --profile dev succeeded")
    return EnvResult(steps=steps, problems=problems)


def _env_kind(cfg: Config, r: LocalRepo) -> str | None:
    _troot, tset = _templates(cfg)
    kind, _how, _answers = _template_for(r, _map(tset.get("kinds") or {}, "templates kinds"))
    return kind


def _env_synth(cfg: Config, r: LocalRepo) -> bool:
    kind = _env_kind(cfg, r)
    if not kind:
        return False
    _troot, tset = _templates(cfg)
    spec = _map(_map(tset.get("kinds") or {}, "templates kinds").get(kind) or {}, "template kind")
    return bool(spec.get("synth", kind in ENV_SYNTH_KINDS))


def scope_names(st: State, repos: list[str], space: str | None) -> list[str] | None:
    """Narrow a command to the named repos and one app space.

    Returns:
        The repo names in scope, or None when neither names nor a space narrow the command.

    """
    if not repos and not space:
        return None
    names: list[str] = st.resolve(repos) if repos else list(st.local)
    if not space:
        return names
    return [n for n in names if n in st.local and st.local[n].space == space]


def environment_findings(st: State, only: list[str] | None = None) -> list[Finding]:
    """Check that every active Python repo has a working environment.

    Returns:
        One finding per repo with a problem.

    """
    cfg = st.cfg
    control = os.path.normpath(fleet_file(cfg).parent.parent)
    todo = [
        r
        for name, r in sorted(st.local.items(), key=lambda kv: kv[0].lower())
        if (only is None or name in only)
        and st.lifecycle(name) not in LIFECYCLES_INACTIVE
        and os.path.normpath(r.path) != control
        and env_applicable(r.path)
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        probed = list(ex.map(lambda r: probe_environment(r.path), todo))
    return [
        Finding("environment-missing", r.name, "; ".join(problems))
        for r, problems in zip(todo, probed, strict=True)
        if problems
    ]


def cmd_environment(args: argparse.Namespace, cfg: Config) -> int:
    """Check every active repo's development environment.

    With --fix, run the setup task of each repo that has a gap and verify it again.

    Returns:
        0 when no repo has a gap left, else 1.

    """
    st = gather(cfg, fetch=False, use_cache=not args.no_cache)
    only = scope_names(st, args.repos, args.space)
    findings = environment_findings(st, only)
    if args.fix:
        for f in findings:
            r = st.local[f.repo]
            res = setup_environment(r.path, _env_synth(cfg, r))
            if res["problems"]:
                f.status, f.error = "failed", "; ".join(res["problems"])
            else:
                f.status = "fixed"
    data: dict[str, object] = {
        "findings": [f.as_dict() for f in findings],
        "open": sum(f.status in {"open", "failed"} for f in findings),
        "fixed": sum(f.status == "fixed" for f in findings),
    }
    emit(
        args,
        data,
        lambda: "\n".join(
            [f"{len(findings)} repos with an environment gap ({data['fixed']} fixed)"]
            + [
                f"  [{f.kind}] {f.repo}: {f.detail} ({f.status})" + (f": {f.error}" if f.error else "")
                for f in findings
            ],
        ),
    )
    return 1 if data["open"] else 0


# beads setup -------------------------------------------------------------------------------------
# Creating a repo includes its beads setup: the `.beads` config files committed, its database on
# the shared server, its entry in the control repo's beads fleet list, and a `.gitignore` that
# covers the beads runtime and database files and the standard ignores for its template kind.

BEADS_GITIGNORE = (
    ".dolt/",
    "*.db",
    ".beads-credential-key",
    ".beads/proxieddb/",
    ".beads/issues.jsonl",
    "*.gate.lock*",
)
BEADS_TRACKED = (
    ".beads/config.yaml",
    ".beads/metadata.json",
    ".beads/.gitignore",
    ".beads/README.md",
)
BEADS_REQUIRED = BEADS_TRACKED[:3]
BEADS_SCRIPTS = PLUGIN_ROOT / "skills" / "polyrepo-beads" / "scripts"


def _ignore_key(line: str) -> str:
    return line.strip().rstrip("/")


def _template_ignore_lines(cfg: Config, r: LocalRepo) -> list[str]:
    """Return the ignore lines of the `.gitignore` of the template this repo's kind is built from.

    Returns:
        The non-comment lines; empty when the repo matches no template.

    """
    troot, tset = _templates(cfg)
    kind, _how, _answers = _template_for(r, _map(tset.get("kinds") or {}, "templates kinds"))
    f = troot / kind / ".gitignore" if kind else None
    if f is None or not f.is_file():
        return []
    return [ln.strip() for ln in f.read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def gitignore_missing(cfg: Config, r: LocalRepo) -> list[str]:
    """List the ignore lines the repo's `.gitignore` lacks: the beads ones and its kind's standard ones.

    Returns:
        The missing lines, in order.

    """
    f = r.path / ".gitignore"
    have = {_ignore_key(ln) for ln in f.read_text().splitlines()} if f.is_file() else set()
    want = [*BEADS_GITIGNORE, *_template_ignore_lines(cfg, r)]
    out: list[str] = []
    for w in want:
        if _ignore_key(w) not in have and w not in out:
            out.append(w)
    return out


def ensure_gitignore(cfg: Config, r: LocalRepo) -> list[str]:
    """Append the missing ignore lines to the repo's `.gitignore`.

    Returns:
        The lines added.

    """
    miss = gitignore_missing(cfg, r)
    if not miss:
        return []
    f = r.path / ".gitignore"
    text = f.read_text() if f.is_file() else ""
    sep = "" if not text or text.endswith("\n") else "\n"
    f.write_text(
        f"{text}{sep}\n# Beads runtime and database files, and the standard ignores (polyrepo)\n"
        + "\n".join(miss)
        + "\n",
    )
    return miss


def _beads_prefix(cfg: Config) -> str:
    """Read the fleet's issue prefix from the control repo's beads config.

    Returns:
        The prefix.

    Raises:
        PolyrepoError: when the control repo has none.

    """
    cp = run(["bd", "config", "get", "issue_prefix"], cwd=fleet_file(cfg).parent.parent)
    prefix = cp.stdout.strip()
    if cp.returncode != 0 or not prefix:
        msg = "could not read issue_prefix from the beads config of the control repo"
        raise PolyrepoError(msg)
    return prefix


def _beads_port() -> int:
    return int(os.environ.get("ATW_BEADS_PORT") or 3308)


def _server_databases() -> set[str]:
    """Return the database names on the shared Dolt server.

    Returns:
        The names.

    Raises:
        PolyrepoError: when the server cannot be listed.

    """
    cp = run(
        [
            "env",
            f"BEADS_SHARED_PORT={_beads_port()}",
            "uv",
            "run",
            "--quiet",
            str(BEADS_SCRIPTS / "beads_server.py"),
            "list",
        ],
        timeout=120,
    )
    if cp.returncode != 0:
        msg = f"could not list the shared Dolt server's databases: {_last_line(cp)}"
        raise PolyrepoError(msg)
    return {ln.strip() for ln in cp.stdout.splitlines() if ln.strip()}


@dataclasses.dataclass(frozen=True)
class _BeadsTarget:
    """Where a repo's beads live: its folder, issue prefix, sync remote, database and server port."""

    path: Path
    prefix: str
    remote: str
    db: str
    port: int


def _beads_files(t: _BeadsTarget, *, shared: bool) -> None:
    """Write `.beads/config.yaml` and `.beads/metadata.json` in shared-server or embedded mode.

    A `project_id` already in the metadata is kept.
    """
    beads = t.path / ".beads"
    beads.mkdir(mode=0o700, exist_ok=True)
    cfgtext = f'issue-prefix: "{t.prefix}"\nsync:\n    remote: "{t.remote}"\n'
    meta: dict[str, object] = {"database": "dolt", "backend": "dolt"}
    if shared:
        cfgtext += f"dolt:\n    shared-server: true\n    port: {t.port}\n    database: {t.db}\n"
        meta.update(dolt_mode="server", dolt_server_port=t.port, dolt_database=t.db)
    else:
        meta.update(dolt_mode="embedded")
    try:
        old = json.loads((beads / "metadata.json").read_text())
    except OSError, ValueError:
        old = {}
    if shared and old.get("project_id"):
        meta["project_id"] = old["project_id"]
    (beads / "config.yaml").write_text(cfgtext)
    (beads / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")


def _bd(path: Path, *args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return run(
        ["env", "BD_ALLOW_REMOTE_MIGRATE=1", "bd", "-C", str(path), *args],
        timeout=timeout,
    )


def _create_beads_database(t: _BeadsTarget) -> list[str]:
    """Give the repo a database on the shared server, without `bd init`.

    `bd bootstrap` clones the repo's `refs/dolt/data` into the shared server when the remote
    has it. When it has not, bootstrap creates a fresh database only as an embedded store, so
    the repo is bootstrapped in embedded mode, given the fleet prefix, pushed to
    `refs/dolt/data`, and bootstrapped again in shared-server mode, which clones it. A failed
    step propagates as the GitFailedError that `must` raises.

    Returns:
        One line per step taken.

    """
    path = t.path
    steps: list[str] = []
    remote_has = git_out(path, "ls-remote", "origin", "refs/dolt/data")
    if not remote_has:
        _beads_files(t, shared=False)
        must(_bd(path, "bootstrap", "--yes"))
        must(_bd(path, "rename-prefix", f"{t.prefix}-", "--repair"))
        must(_bd(path, "dolt", "push"))
        shutil.rmtree(path / ".beads" / "embeddeddolt", ignore_errors=True)
        steps.append("created the database (embedded) and pushed it to refs/dolt/data")
    _beads_files(t, shared=True)
    must(_bd(path, "bootstrap", "--yes"))
    steps.append(f"cloned refs/dolt/data into the shared server as {t.db}")
    return steps


def _unstage(repo: Path, pattern: str) -> None:
    """Take the staged entries matching a pattern (an index-only change) out of the index."""
    names = git(repo, "diff", "--cached", "--name-only", "--", pattern).stdout.split()
    for n in names:
        git(repo, "rm", "--cached", "-q", "-f", "--", n)


def beads_setup(
    cfg: Config,
    r: LocalRepo,
    trailer: str | None = None,
) -> dict[str, object]:
    """Bring one repo to the canonical beads state, commit and push it.

    Gives it a database when the shared server has none, repairs identity, prefix and mode
    (`bd doctor --fix` and the polyrepo-beads `converge-repo.sh`), completes its `.gitignore`,
    and commits `.beads/` config files and the `.gitignore` on the default branch. When the
    environment lacks what a step needs, the step's PolyrepoError propagates.

    Returns:
        {"repo", "steps": [...], "committed": bool, "pushed": bool}.

    Raises:
        GitFailedError: when a step fails.

    """
    path, name, b = r.path, r.name, cfg.default_branch
    if git_out(path, "symbolic-ref", "--short", "-q", "HEAD") != b:
        msg = f"{name} is not on {b}"
        raise GitFailedError(msg)
    prefix, port, remote = _beads_prefix(cfg), _beads_port(), cfg.github_url(name)
    try:
        db = json.loads((path / ".beads" / "metadata.json").read_text()).get(
            "dolt_database",
        )
    except OSError, ValueError:
        db = None
    t = _BeadsTarget(path, prefix, remote, db or name.replace("-", "_"), port)
    steps = _beads_converge(cfg, name, t)
    _unstage(path, "*.gate.lock*")
    added = ensure_gitignore(cfg, r)
    if added:
        steps.append(f"added {len(added)} lines to .gitignore")
    return _beads_commit(cfg, name, path, steps, trailer)


def _beads_converge(cfg: Config, name: str, t: _BeadsTarget) -> list[str]:
    """Give the repo its database and config files, and converge its identity when it lacks one.

    Returns:
        One line per step taken.

    Raises:
        GitFailedError: when the repo still has no project_id after convergence.

    """
    path = t.path
    steps: list[str] = []
    meta_f = path / ".beads" / "metadata.json"

    def project_id() -> str | None:
        try:
            meta: object = json.loads(meta_f.read_text())
            pid: object = meta.get("project_id") if isinstance(meta, dict) else None
            return pid if isinstance(pid, str) else None
        except OSError, ValueError:
            return None

    on_server = t.db in _server_databases()
    files_ok = (path / ".beads" / "config.yaml").is_file() and meta_f.is_file()
    if not on_server:
        steps.extend(_create_beads_database(t))
    elif not files_ok:
        _beads_files(t, shared=True)
        steps.append("wrote the missing .beads config files")
    if not (on_server and files_ok and project_id()):
        _bd(path, "doctor", "--fix", "--yes")
        _bd(path, "vc", "commit", "-m", "chore: record project identity")
        env = f"{CONTROL_REPO_ENV}={fleet_file(cfg).parent.parent}"
        conv = ["env", env, "bash", str(BEADS_SCRIPTS / "converge-repo.sh"), str(path)]
        must(run([*conv, "--clean"], timeout=600))
        steps.append("converged to the shared-server canonical state")
        if not project_id():
            msg = f"{name}: metadata.json has no project_id after convergence"
            raise GitFailedError(msg)
    return steps


def _beads_commit(
    cfg: Config,
    name: str,
    path: Path,
    steps: list[str],
    trailer: str | None,
) -> dict[str, object]:
    """Commit the repo's beads config files and `.gitignore` on the default branch, and push.

    A failed git step propagates as the GitFailedError that `must` raises.

    Returns:
        {"repo", "steps": [...], "committed": bool, "pushed": bool}.

    """
    paths = [p for p in (*BEADS_TRACKED, ".gitignore") if (path / p).is_file()]
    must(git(path, "add", "-f", "--", *paths))
    res: dict[str, object] = {
        "repo": name,
        "steps": steps,
        "committed": False,
        "pushed": False,
    }
    if git(path, "diff", "--cached", "--quiet", "--", *paths).returncode == 0:
        return res
    msg = f"chore(beads): set up beads for {name}"
    if trailer:
        msg += f"\n\n{trailer}"
    cp = git(path, "commit", "-m", msg, "--", *paths, timeout=300)
    if cp.returncode != 0:
        must(git(path, "add", "-f", "--", *paths))
        must(git(path, "commit", "-m", msg, "--", *paths, timeout=300))
    res["committed"] = True
    must(git(path, "pull", "--rebase", "--autostash", "--quiet", timeout=120))
    must(git(path, "push", "origin", cfg.default_branch, timeout=120))
    res["pushed"] = True
    return res


def beads_setup_findings(st: State, space: str | None = None) -> list[Finding]:
    """Check that every active repo (or every active repo of one app space) carries its beads setup.

    The setup is its config files committed, its entry in the fleet list, and a complete
    `.gitignore`.

    Returns:
        One finding per gap. The database on the server is the beads audit's check.

    """
    cfg = st.cfg
    control = os.path.normpath(fleet_file(cfg).parent.parent)
    listed = fleet_paths(cfg)
    out: list[Finding] = []
    for name, r in sorted(st.local.items(), key=lambda kv: kv[0].lower()):
        if (
            st.lifecycle(name) in LIFECYCLES_INACTIVE
            or os.path.normpath(r.path) == control
            or (space and r.space != space)
        ):
            continue
        missing = [p for p in BEADS_REQUIRED if not (r.path / p).is_file()]
        if missing:
            out.append(
                Finding("beads-config-missing", name, f"missing {', '.join(missing)}"),
            )
        else:
            loose = [p for p in BEADS_REQUIRED if git(r.path, "ls-files", "--error-unmatch", "--", p).returncode != 0]
            if loose:
                out.append(
                    Finding(
                        "beads-config-uncommitted",
                        name,
                        f"not tracked by git: {', '.join(loose)}",
                    ),
                )
        if os.path.normpath(r.path) not in listed:
            out.append(
                Finding(
                    "beads-not-in-fleet",
                    name,
                    "not in the control repo's beads fleet list (repos.additional)",
                ),
            )
        gi = gitignore_missing(cfg, r)
        if gi:
            out.append(
                Finding(
                    "gitignore-incomplete",
                    name,
                    f".gitignore lacks {', '.join(gi)}",
                ),
            )
    return out


def cmd_beads_setup(args: argparse.Namespace, cfg: Config) -> int:
    """Check every active repo's beads setup (--check), or set up repos.

    The repos set up are the named ones or, with --all, every active repo that has a gap or
    no database on the server. Neither repos, --all nor --check propagates the PolyrepoError
    of `_beads_setup_names`.

    Returns:
        0 when nothing is left open, else 1.

    """
    st = gather(cfg, fetch=False, use_cache=not args.no_cache)
    findings = beads_setup_findings(st, args.space)
    if args.check:
        data: dict[str, object] = {
            "findings": [f.as_dict() for f in findings],
            "open": len(findings),
        }
        emit(
            args,
            data,
            lambda: "\n".join(
                [f"{len(findings)} beads setup gaps"] + [f"  [{f.kind}] {f.repo}: {f.detail}" for f in findings],
            ),
        )
        return 1 if findings else 0
    names = _beads_setup_names(args, cfg, st, findings)
    results, log = _beads_setup_run(args, cfg, st, names)
    if log:
        note_change(cfg, "polyrepo beads-setup", log)
    data = {
        "repos": results,
        "open": sum("error" in x for x in results),
        "fixed": sum("error" not in x and not x.get("dry_run") for x in results),
    }
    finish_records(cfg, data)
    emit(
        args,
        data,
        lambda: "\n".join(
            f"{x['repo']}: " + str(x.get("error") or ("would set up" if x.get("dry_run") else "set up"))
            for x in results
        ),
    )
    return 1 if data["open"] else 0


def _beads_setup_names(
    args: argparse.Namespace,
    cfg: Config,
    st: State,
    findings: list[Finding],
) -> list[str]:
    """Choose the repos beads-setup works on: the named ones, or with --all every gap.

    With --all, a repo is chosen when it has a setup gap or no database on the server.

    Returns:
        The repo names.

    Raises:
        PolyrepoError: when neither repos nor --all is given.

    """
    if args.repos:
        return st.resolve(args.repos)
    if not args.all:
        msg = "give repo names, --all, or --check"
        raise PolyrepoError(msg)
    dbs = _server_databases()
    control = os.path.normpath(fleet_file(cfg).parent.parent)
    gaps = {f.repo for f in findings}
    names: list[str] = []
    for n, r in sorted(st.local.items(), key=lambda kv: kv[0].lower()):
        if (
            st.lifecycle(n) in LIFECYCLES_INACTIVE
            or os.path.normpath(r.path) == control
            or (args.space and r.space != args.space)
        ):
            continue
        try:
            db = json.loads((r.path / ".beads" / "metadata.json").read_text())
            db = db.get("dolt_database")
        except OSError, ValueError:
            db = None
        if n in gaps or (db or n.replace("-", "_")) not in dbs:
            names.append(n)
    return names


def _beads_setup_run(
    args: argparse.Namespace,
    cfg: Config,
    st: State,
    names: list[str],
) -> tuple[list[dict[str, object]], list[str]]:
    """Set up beads in each named repo, then add the set-up repos to the fleet list in one write.

    Returns:
        (one result per repo, plus one for a failed fleet list write; the lines for the commit message).

    """
    results: list[dict[str, object]] = []
    log: list[str] = []
    fleet_adds: list[Path] = []
    for n in names:
        r = st.local[n]
        if args.dry_run:
            results.append({"repo": n, "dry_run": True})
            continue
        try:
            res = beads_setup(cfg, r, args.trailer)
            if (r.path / ".beads").is_dir():
                fleet_adds.append(r.path)
        except (GitFailedError, PolyrepoError, OSError) as exc:
            res = {"repo": n, "error": str(exc)}
        results.append(res)
        if "error" not in res:
            log.append(
                f"{n}: beads set up ({'; '.join(_strs(res['steps'], 'steps')) or 'already set up'})",
            )
    if fleet_adds:
        # One write for the whole run: the fleet watcher restarts on each list change.
        try:
            log.extend(f"beads fleet list: {c}" for c in fleet_edit(cfg, add=fleet_adds))
        except (PolyrepoError, OSError) as exc:
            results.append({"repo": "(beads fleet list)", "error": str(exc)})
    return results, log


# clone -----------------------------------------------------------------------------------------


def _clone_dest(cfg: Config, name: str) -> Path:
    """Return the one folder a clone of this repo belongs in, from the config's placement.

    Returns:
        The destination path: the app space, then the folder the config places its type in.

    Raises:
        PolyrepoError: when its app space folder does not exist.

    """
    space = cfg.expected_space(name)
    space_dir = cfg.root / space
    if not space_dir.is_dir():
        msg = f"no app space folder {space_dir}"
        raise PolyrepoError(msg)
    sub = cfg.placement_folder(space, cfg.rules.deprecated_base(name))
    return space_dir / sub / name if sub else space_dir / name


def _clone_conflicts(cfg: Config, name: str) -> list[Path]:
    """Find every clone of this repo already on disk, by folder name or by origin URL.

    Returns:
        The paths of those clones.

    """
    local, dups = discover(cfg)
    found = {r.path for n, r in local.items() if n.lower() == name.lower()}
    for n, paths in dups:
        if n.lower() == name.lower():
            found.update(paths)
    wanted = {
        cfg.github_url(name).lower(),
        cfg.github_url(name)[: -len(".git")].lower(),
    }
    for r in local.values():
        url = (git_out(r.path, "remote", "get-url", "origin") or "").lower()
        if url in wanted:
            found.add(r.path)
    return sorted(found)


def cmd_clone(args: argparse.Namespace, cfg: Config) -> int:
    """Clone a repo into the folder its name and project give it, never anywhere else.

    Returns:
        0 when the repo is cloned or is already at its correct folder.

    Raises:
        PolyrepoError: when the repo already exists at any other path, is on disk more than
            once, does not exist on GitHub, or the clone fails.

    """
    name = args.repo
    dest = _clone_dest(cfg, name)
    here = _clone_conflicts(cfg, name)
    res: dict[str, object] = {"repo": name, "path": str(dest), "cloned": False}
    wrong = [p for p in here if p != dest]
    if wrong:
        msg = f"refusing to clone {name} into {dest}: it already exists at " + ", ".join(str(p) for p in wrong)
        raise PolyrepoError(msg)
    if dest in here:
        emit(args, res, lambda: f"{name}: already at {dest}")
        return 0
    if dest.exists():
        msg = f"{dest} exists and is not a git clone"
        raise PolyrepoError(msg)
    if GitHub(cfg, use_cache=False).resolve(name) is None:
        msg = f"{cfg.owner}/{name} does not exist on GitHub"
        raise PolyrepoError(msg)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cp = run(["git", "clone", cfg.github_url(name), str(dest)], timeout=600)
    if cp.returncode != 0:
        msg = f"git clone failed: {_last_line(cp)}"
        raise PolyrepoError(msg)
    res["cloned"] = True
    emit(args, res, lambda: f"{name}: cloned to {dest}")
    return 0


# rename ----------------------------------------------------------------------------------------


def rename(
    st: State,
    old: str,
    new: str,
    extra_fields: dict[str, object] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Rename a repo on GitHub and on disk together, repoint origin, and rename its manifest entry.

    The one rename operation: `rename`, `deprecate` and reconcile's name-parity repair all
    run it. It finds the local clone under either name and the GitHub repo through its
    origin (following GitHub's rename redirects), so it also completes a rename that only
    one side has made. It refuses, with the PolyrepoError of `_rename_plan`, when the new
    name matches no naming pattern, another GitHub repo has it, the target folder exists, or
    the local default branch is not known to be pushed. A name starting with `deprecated-`
    makes the entry deprecated, dated today unless it already has a date.

    Returns:
        The steps planned (dry run) or done.

    Raises:
        GitFailedError: when a step fails part way; the message names the steps done.

    """
    plan = _rename_plan(st, old, new, extra_fields)
    if dry_run:
        return plan.steps
    done: list[str] = []
    try:
        _rename_moves(st.cfg, new, plan, done)
    except (GitFailedError, OSError) as exc:
        so_far = f" (done before it stopped: {'; '.join(done)})" if done else ""
        msg = f"{exc}{so_far}"
        raise GitFailedError(msg) from exc
    _rename_record(st, old, new, plan, done)
    return done


@dataclasses.dataclass
class _RenamePlan:
    """What a rename will do: the clone and GitHub repo it moves, and the entry it writes."""

    r: LocalRepo | None
    rec: GhRepo | None
    new_path: Path | None
    url: str
    fields: dict[str, object]
    active: bool
    steps: list[str]


def _rename_plan(
    st: State,
    old: str,
    new: str,
    extra_fields: dict[str, object] | None,
) -> _RenamePlan:
    """Check that a rename can proceed and plan its steps.

    Returns:
        The plan.

    Raises:
        PolyrepoError: when the rename cannot proceed as it stands.

    """
    cfg, man = st.cfg, st.manifest
    if old == new:
        msg = f"{old} is already named {new}"
        raise PolyrepoError(msg)
    if cfg.classify(new) is None:
        msg = f"{new} is refused: {cfg.naming_problem(new)}"
        raise PolyrepoError(msg)
    r = st.local.get(old) or st.local.get(new)
    parsed = parse_github_url(r.origin_url) if r else None
    rec = st.gh.resolve(parsed[1] if parsed else old)
    taken = st.gh.resolve(new)
    if taken is not None and (rec is None or taken["name"] != rec["name"]):
        msg = f"{cfg.owner}/{new} already exists on GitHub"
        raise PolyrepoError(msg)
    deprecating = cfg.is_deprecated_name(new)
    if deprecating:
        require_no_stacks(cfg, old)
    url = cfg.github_url(new)
    steps: list[str] = []
    if rec and rec["name"] != new:
        steps.append(f"rename the GitHub repo {cfg.owner}/{rec['name']} to {new}")
    new_path = _rename_local_steps(cfg, r, new, url, steps) if r else None
    entry = man.entries().get(old) or man.entries().get(new) or CommentedMap()
    fields, lc = _rename_fields(cfg, new, entry, extra_fields)
    steps.append(
        f"manifest: entry {new}, " + ", ".join(f"{k} {v}" for k, v in fields.items()),
    )
    active = lc not in LIFECYCLES_INACTIVE
    if not deprecating:
        steps.append(f"matrix: move-repository, so every stack that names {old} names {new}")
    if r and new_path:
        steps.append(
            "beads fleet list (repos.additional): "
            + (
                f"point the entry at {new_path}, or add it when it has a .beads folder"
                if active
                else f"remove {r.path}"
            ),
        )
    return _RenamePlan(r, rec, new_path, url, fields, active, steps)


def _renamed_path(cfg: Config, path: Path, new: str) -> Path:
    """Return the folder a clone belongs in once renamed: where the new name places it.

    A name goes in its app space's placement folder for its type, as a clone of it would, so a
    rename that changes the space also moves the clone there. A deprecated name keeps the
    clone's parent folder.

    Returns:
        The clone's path after the rename.

    """
    if cfg.is_deprecated_name(new):
        return path.with_name(new)
    return _clone_dest(cfg, new)


def _rename_local_steps(cfg: Config, r: LocalRepo, new: str, url: str, steps: list[str]) -> Path:
    """Check the local clone can move to its new name, appending its steps.

    Returns:
        The clone's path after the rename.

    Raises:
        PolyrepoError: when main is not known to be pushed or the new folder exists.

    """
    if r.fetch_error:
        msg = f"{r.name}: git fetch failed ({r.fetch_error}); cannot confirm {cfg.default_branch} is pushed"
        raise PolyrepoError(msg)
    if r.ahead:
        msg = f"{r.name}: {cfg.default_branch} is {r.ahead} commit(s) ahead of origin; push it first"
        raise PolyrepoError(msg)
    new_path = _renamed_path(cfg, r.path, new)
    if new_path != r.path:
        if new_path.exists():
            msg = f"{new_path} already exists"
            raise PolyrepoError(msg)
        steps.append(f"move {r.path} to {new_path}")
    if r.origin_url != url:
        steps.append(f"point origin at {url}")
    return new_path


def _rename_fields(
    cfg: Config,
    new: str,
    entry: dict[str, object],
    extra_fields: dict[str, object] | None,
) -> tuple[dict[str, object], str]:
    """Work out the renamed entry's fields and lifecycle.

    Returns:
        (the fields, the lifecycle).

    """
    lc = str(entry.get("lifecycle") or "active")
    if cfg.is_deprecated_name(new):
        lc = "deprecated"
    elif lc in LIFECYCLES_INACTIVE:
        lc = "active"
    fields = entry_fields(cfg, new, lc, extra_fields)
    if lc == "deprecated":
        fields["deprecated_on"] = entry.get("deprecated_on") or today()
    return fields, lc


def _rename_moves(cfg: Config, new: str, plan: _RenamePlan, done: list[str]) -> None:
    """Rename the GitHub repo, move the clone and repoint origin, appending each step done.

    A failed git or gh step propagates as the GitFailedError that `must` raises; a failed
    move as OSError.
    """
    rec, r, new_path = plan.rec, plan.r, plan.new_path
    if rec and rec["name"] != new:
        must(
            run(
                [
                    "gh", "repo", "rename", new,
                    "--repo", f"{cfg.owner}/{rec['name']}", "--yes",
                ],
                timeout=120,
            ),
        )  # fmt: skip
        done.append(f"GitHub {rec['name']} renamed to {new}")
    if r and new_path:
        if new_path != r.path:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            r.path.rename(new_path)
            done.append(f"moved {r.path} to {new_path}")
        point_origin(new_path, plan.url)
        done.append(f"origin set to {plan.url}")
        must(git(new_path, "worktree", "repair"))


def _rename_record(st: State, old: str, new: str, plan: _RenamePlan, done: list[str]) -> None:
    """Write the renamed manifest entry, update the fleet list, and log the rename."""
    cfg, man = st.cfg, st.manifest
    if plan.rec and plan.rec["name"] != new:
        st.gh.note_rename(plan.rec["name"], new)
    if old in man.entries() and new not in man.entries():
        man.rename_entry(old, new)
    man.add_entry(new, {})
    for k, v in plan.fields.items():
        man.set_field(new, k, v)
    man.set_field(new, "local_path", None)
    man.save()
    if not cfg.is_deprecated_name(new):
        try:
            moved = _seq(matrix_run(cfg, ["move-repository", "--from", old, "--to", new]).get("stacks"), "moved stacks")
            if moved:
                done.extend([f"matrix: {', '.join(str(i) for i in moved)} now name {new}", matrix_commit(cfg)])
        except PolyrepoError as exc:
            done.append(f"matrix NOT updated: {exc}")
    if plan.r and plan.new_path:
        try:
            done.extend(
                f"beads fleet list: {c}" for c in fleet_after_rename(cfg, plan.r.path, plan.new_path, plan.active)
            )
        except (OSError, PolyrepoError) as exc:
            done.append(f"beads fleet list NOT updated: {exc}")
    note_change(
        cfg,
        f"polyrepo rename {old} to {new}",
        [*done, f"the manifest entry's repository is now {new}"],
    )
    st.gh.invalidate()


def _run_rename(
    args: argparse.Namespace,
    st: State,
    name: str,
    new: str,
    after: Callable[[dict[str, object], list[str]], bool] | None = None,
) -> int:
    """Run a rename for a command and report it.

    `after`, when given, runs once the rename is done (or planned, on a dry run), adds its
    own results to the report and steps, and returns False when it failed.

    Returns:
        0 on success, 1 when a step failed part way.

    """
    res: dict[str, object] = {"repo": name, "new_name": new, "dry_run": args.dry_run}
    try:
        steps: list[str] = rename(st, name, new, dry_run=args.dry_run)
        res["steps"] = steps
    except GitFailedError as exc:
        res["error"] = str(exc)
        emit(args, res, lambda: f"{name}: stopped: {res['error']}")
        return 1
    ok = after(res, steps) if after else True
    finish_records(st.cfg, res)
    head = f"dry run: rename {name} to {new}" if args.dry_run else f"{name}: renamed to {new}"
    emit(
        args,
        res,
        lambda: "\n".join(
            [head, *[f"  {s}" for s in steps], *_records_line(res)],
        ),
    )
    return 0 if ok else 1


def cmd_rename(args: argparse.Namespace, cfg: Config) -> int:
    """Rename a repo with every name it carries: the repository, its stacks and its Python names.

    The new name must match a naming pattern and end in a stack type. The repository moves on
    GitHub and on disk together, origin and the manifest follow, and the beads fleet list
    (`repos.additional`) is updated with the folder. The stack ids, the stack file names, the
    Python distribution and the import package are then brought to what `atw-naming` gives
    for the new name, and every import, dependency line and written reference to an old name
    in the other repositories is rewritten. Each repository that changes gets one worktree,
    one commit and one pull request opened with the project's PR command; the plan lists all
    of it first (`--dry-run` stops there). With no new name only the stack and Python names
    are brought into line, and `--also` brings those of further repositories into line in the
    same pull requests, so a repository that several names change still gets one. The vault
    documents that still carry an old name (in the folders the config's `rename.documents`
    names) are reported under `names.documents`, never edited: the filing-clerk changes them.
    Anything else outside git, GitHub, the repositories and the steward's records that names the
    repo by its old name (workflow artifacts) is the caller's to update.

    Returns:
        0 on success, 1 when a step failed part way.

    """
    st = gather(cfg, fetch=True, use_cache=not args.no_cache)
    name, *others = st.resolve([args.repo, *args.also])
    new: str = args.new_name or name
    pairs = [(name, new), *[(o, o) for o in others]]

    def names(res: dict[str, object], steps: list[str]) -> bool:
        return _rename_names(st, args, pairs, res, steps)

    if new == name:
        return _run_names_only(args, st, [p[0] for p in pairs], names)
    return _run_rename(args, st, name, new, after=names)


def _run_names_only(
    args: argparse.Namespace,
    st: State,
    repos: list[str],
    names: Callable[[dict[str, object], list[str]], bool],
) -> int:
    """Bring the stack and Python names of one or more repos into line without renaming any repository.

    Returns:
        0 on success, 1 when a step failed.

    """
    steps: list[str] = []
    label = ", ".join(repos)
    res: dict[str, object] = {"repo": repos[0], "repos": repos, "dry_run": args.dry_run, "steps": steps}
    ok = names(res, steps)
    if not args.dry_run:
        note_change(st.cfg, f"polyrepo rename {label} (stack and Python names)", steps)
    finish_records(st.cfg, res)
    head = f"dry run: names of {label}" if args.dry_run else f"{label}: names"
    emit(args, res, lambda: "\n".join([head, *[f"  {s}" for s in steps], *_records_line(res)]))
    return 0 if ok else 1


# --------------------------------------------------------------------------------------------
# the names a rename covers besides the repository (name_sweep.py has the rules)

NAMING_COMMAND = PLUGIN_ROOT / "bin" / "atw-naming"
NAMING_TIMEOUT = 60
PR_COMMAND_ENV = "ATW_PR_COMMAND"
PR_COMMAND_DEFAULT = "~/.local/bin/skillspoke-pr"
PR_TIMEOUT = 900
PR_AUTOMERGE_NOT_ARMED = 3
CHECK_TASKS = ("lint", "typecheck", "test")
APPLY_WORKERS = 4
CHECK_TIMEOUT = 3600
CHECK_TAIL_LINES = 15
TITLE_NAMES = 2
RENAME_BRANCH = "rename"
SHARED_BRANCH_SLUG = "python-layout"
KIND_NOUNS: dict[str, str] = {
    "repository": "repository",
    "stack": "stack",
    "stack-file": "stack file",
    "distribution": "Python distribution",
    "import-package": "Python package",
}


@dataclasses.dataclass
class _Subject:
    """One repository whose names change: the names, the paths that move, the clone."""

    old: str
    new: str
    path: Path
    changes: list[NameChange]
    moves: list[FileMove]
    notes: list[str]


@dataclasses.dataclass
class _Documents:
    """The vault documents that still carry an old name: the vault, the folders searched, what each carries.

    A rename reports them and edits none: the filing-clerk changes the vault.
    """

    root: Path
    paths: tuple[str, ...]
    found: list[FileEdit]


@dataclasses.dataclass
class _NamesPlan:
    """The names a rename changes and every repository it touches."""

    subjects: list[_Subject]
    rules: list[Rule]
    edits: dict[str, list[FileEdit]]
    paths: dict[str, Path]
    held_back: dict[str, list[tuple[str, FileEdit]]]
    waits_on: dict[str, list[str]]
    documents: _Documents | None = None
    keep_src: set[str] = dataclasses.field(default_factory=set)
    branch_slug: str = SHARED_BRANCH_SLUG

    def holders(self) -> list[str]:
        """Name the repositories whose names change, as they are called after the rename.

        Returns:
            The names, in the order they were given.

        """
        return [s.new for s in self.subjects]

    def slug(self) -> str:
        """Name the branch and worktree these changes share: the one repository's name, else a shared slug.

        Returns:
            The slug.

        """
        return self.subjects[0].new.lower() if len(self.subjects) == 1 else self.branch_slug


def _sweep_git(repo: Path, args: Sequence[str]) -> tuple[int, str, str]:
    """Run git for a name sweep.

    Returns:
        (exit status, stdout, stderr).

    """
    cp = git(repo, *args)
    return cp.returncode, cp.stdout, cp.stderr


def _namer(cfg: Config) -> Namer:
    """Build the function that asks `atw-naming` for a name.

    Returns:
        A function from `atw-naming` arguments to the name it prints; a refusal raises NameSweepError.

    """
    env: dict[str, str | None] = {}
    if not os.environ.get(CONTROL_REPO_ENV):
        env[CONTROL_REPO_ENV] = str(cfg.file.parent.parent)

    def name(args: Sequence[str]) -> str:
        cp = run([str(NAMING_COMMAND), *args], timeout=NAMING_TIMEOUT, env=env)
        out = cp.stdout.strip()
        if cp.returncode != 0 or not out:
            msg = f"atw-naming {' '.join(args)} failed: {_last_line(cp)}"
            raise NameSweepError(msg)
        return out

    return name


def _rename_settings(cfg: Config) -> tuple[list[str], Path]:
    """Read the paths a sweep never edits from the config's `rename` section, and the PR command from `$ATW_PR_COMMAND`.

    Returns:
        (fnmatch patterns of repository paths, the PR command).

    """
    section = _map(cfg.raw.get("rename") or {}, "config rename")
    excludes = _strs(section.get("sweep_exclude") or [], "rename.sweep_exclude")
    return excludes, Path(os.environ.get(PR_COMMAND_ENV) or PR_COMMAND_DEFAULT).expanduser()


def _names_subjects(st: State, pairs: list[tuple[str, str]], *, dry_run: bool) -> tuple[list[_Subject], list[Rule]]:
    """Plan the names of each repository that changes, and the rewrites they call for.

    Returns:
        The subjects, and the rules of all of them.

    Raises:
        NameSweepError: when a repository has no local clone or a name cannot be planned.

    """
    cfg = st.cfg
    namer = _namer(cfg)
    subjects: list[_Subject] = []
    rules: list[Rule] = []
    for old, new in pairs:
        held = st.local.get(old) or st.local.get(new)
        if held is None:
            msg = f"{old} has no local clone"
            raise NameSweepError(msg)
        path = held.path if dry_run or old == new else _renamed_path(cfg, held.path, new)
        facts = read_facts(_sweep_git, path)
        changes, notes = plan_changes(old, new, facts, cfg.stack_type_names(), namer)
        subjects.append(_Subject(old, new, path, changes, planned_moves(changes, facts), notes))
        rules.extend(build_rules(changes, new))
    return subjects, rules


def _names_plan(
    st: State,
    pairs: list[tuple[str, str]],
    skip: set[str],
    keep_src: set[str],
    *,
    dry_run: bool,
) -> _NamesPlan:
    """Plan the names that change and sweep every repository for the references.

    The repositories that change are swept under their new names; the others under their
    own. Archived and deprecated repositories are not swept. A repository named in `skip` is
    swept but never edited, so the plan can report what in it uses a renamed name. A repository
    whose edits use another repository's renamed package waits on it. A name that cannot be
    planned or a sweep that fails raises the NameSweepError of `name_sweep`.

    Returns:
        The plan.

    """
    subjects, rules = _names_subjects(st, pairs, dry_run=dry_run)
    excludes, _ = _rename_settings(st.cfg)
    given = {n for pair in pairs for n in pair}
    paths: dict[str, Path] = {s.new: s.path for s in subjects}
    for name, r in st.local.items():
        if name not in given and st.lifecycle(name) not in LIFECYCLES_INACTIVE:
            paths[name] = r.path
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        swept = dict(
            zip(
                paths,
                ex.map(lambda n: sweep_repo(_sweep_git, SweepTarget(n, paths[n]), rules, excludes, write=False), paths),
                strict=True,
            ),
        )
    plan = _NamesPlan(subjects, rules, {}, paths, {}, {})
    plan.keep_src = keep_src
    _sort_edits(plan, swept, skip)
    for s in subjects:
        if s.moves and s.new not in skip:
            plan.edits.setdefault(s.new, [])
    hit = {label for found in plan.edits.values() for e in found for label in e.labels}
    for s in subjects:
        s.changes = [c for c in s.changes if c.kind != "stack" or change_label(c) in hit]
    plan.waits_on = _waits_on(plan)
    plan.documents = _names_documents_plan(st.cfg, subjects)
    return plan


def _sort_edits(
    plan: _NamesPlan,
    swept: dict[str, list[FileEdit]],
    skip: set[str],
) -> None:
    """Sort what the sweep found into edits to make and edits held back, with the reason for each.

    A `--skip-repo` repository is only reported; a `--keep-src` repository is edited except for
    its files under `src/`.
    """
    for name, found in swept.items():
        if not found:
            continue
        if name in skip:
            plan.held_back.setdefault("skipped", []).extend((name, e) for e in found)
            continue
        kept = [e for e in found if name in plan.keep_src and e.path.startswith("src/")]
        if kept:
            plan.held_back.setdefault("kept", []).extend((name, e) for e in kept)
        if rest := [e for e in found if e not in kept]:
            plan.edits[name] = rest


def _waits_on(plan: _NamesPlan) -> dict[str, list[str]]:
    """Find the repositories whose edits use a name another repository publishes under a new name.

    Such a repository cannot install or import the new name until the other repository is
    released, so its pull request waits on it.

    Returns:
        For each waiting repository, the repositories it waits on.

    """
    published = {
        s.new: {
            change_label(c)
            for c in s.changes
            if c.kind == "import-package" or (c.kind == "distribution" and normalize(c.old) != normalize(c.new))
        }
        for s in plan.subjects
    }
    waits: dict[str, list[str]] = {}
    for name, found in plan.edits.items():
        used = {label for e in found for label in e.labels}
        if names := sorted(h for h, labels in published.items() if h != name and labels & used):
            waits[name] = names
    return waits


def _documents_settings(cfg: Config) -> tuple[Path, tuple[str, ...]] | None:
    """Read the config's `rename.documents` section: the vault folder and the folders in it a rename searches.

    Returns:
        (the vault's root, the folders under it), or None when the config names no documents.

    Raises:
        NameSweepError: when the section lacks an absolute root or the folders.

    """
    section = _map(cfg.raw.get("rename") or {}, "config rename")
    documents = section.get("documents")
    if not documents:
        return None
    spec = _map(documents, "config rename.documents")
    root = Path(expand_env(str(spec.get("root") or ""))).expanduser()
    paths = tuple(_strs(spec.get("paths") or [], "rename.documents.paths"))
    if not root.is_absolute() or not paths:
        msg = "config rename.documents needs an absolute root (environment variables allowed) and paths"
        raise NameSweepError(msg)
    return root, paths


def _names_documents_plan(cfg: Config, subjects: list[_Subject]) -> _Documents | None:
    """Find the vault documents that still carry an old name the subjects change, for the filing-clerk.

    Names only: the rules are the ones for the repositories' own names, with the document
    differences `build_document_rules` states. The search reads the vault and never writes it.

    Returns:
        The documents found, or None when the config names no vault folders or the vault is absent.

    """
    settings = _documents_settings(cfg)
    if settings is None or not (settings[0] / ".git").exists():
        return None
    root, paths = settings
    changes = [c for s in subjects for c in s.changes]
    repository_of = {change_label(c): s.new for s in subjects for c in s.changes}
    rules = build_document_rules(changes, repository_of)
    excludes, _ = _rename_settings(cfg)
    found = sweep_repo(_sweep_git, SweepTarget("documents", root, paths), rules, excludes, write=False) if rules else []
    return _Documents(root, paths, found)


def _names_lines(plan: _NamesPlan) -> list[str]:
    """Write the plan as the lines the rename's steps carry.

    Returns:
        One line per name change, move, edited repository, pull request and repository left alone.

    """
    lines: list[str] = []
    for s in plan.subjects:
        lines.extend(f"name: {KIND_NOUNS[c.kind]} {c.old} -> {c.new}" for c in s.changes if c.kind != "repository")
        lines.extend(f"note: {n}" for n in s.notes)
        lines.extend(f"git mv {s.new}: {m.old} -> {m.new}" for m in s.moves)
    order = sorted(plan.edits, key=lambda n: (n not in plan.holders(), n.lower()))
    for name in order:
        found = plan.edits[name]
        files = ", ".join(f"{e.path} ({e.replacements})" for e in found[:FILES_SHOWN])
        more = f", and {len(found) - FILES_SHOWN} more" if len(found) > FILES_SHOWN else ""
        lines.append(f"edit {name}: {len(found)} file(s): {files}{more}")
    for name in order:
        line = f"pull request {name}: one worktree, one commit, opened with the project's PR command"
        if name in plan.waits_on:
            line += f"; waits on {', '.join(plan.waits_on[name])}, whose new package is not importable until released"
        lines.append(line)
    for why, rows in sorted(plan.held_back.items()):
        what = {
            "kept": "source kept as is by --keep-src",
        }.get(why, "named by --skip-repo")
        lines.extend(f"not edited ({what}) {name}: {e.path}" for name, e in rows)
    lines.extend(_documents_lines(plan.documents))
    return lines


def _documents_lines(docs: _Documents | None) -> list[str]:
    """Write the vault documents that still carry an old name as step lines for the filing-clerk.

    Returns:
        One line per document.

    """
    if docs is None:
        return []
    return [
        f"vault document for the filing-clerk {e.path}: line(s) {', '.join(str(n) for n in e.lines)} "
        f"carry {', '.join(sorted(e.labels))}"
        for e in docs.found
    ]


def _documents_record(docs: _Documents | None) -> dict[str, object]:
    """Write the vault documents that still carry an old name as JSON.

    Returns:
        The vault's root and each document with its lines and names; empty when no vault was searched.

    """
    if docs is None:
        return {}
    return {
        "root": str(docs.root),
        "carry_old_names": [
            {"path": e.path, "lines": list(e.lines), "names": sorted(e.labels), "occurrences": e.replacements}
            for e in docs.found
        ],
    }


def _repository_documents(cfg: Config, old: str, new: str) -> _Documents | None:
    """Find the vault documents that still carry a repository's old name, for the filing-clerk.

    Returns:
        The documents found, or None when the config names no vault folders or the vault is absent.

    """
    settings = _documents_settings(cfg)
    if settings is None or not (settings[0] / ".git").exists():
        return None
    root, paths = settings
    change = NameChange("repository", old, new)
    rules = build_document_rules([change], {change_label(change): new})
    excludes, _ = _rename_settings(cfg)
    return _Documents(
        root,
        paths,
        sweep_repo(_sweep_git, SweepTarget("documents", root, paths), rules, excludes, write=False),
    )


def _names_record(plan: _NamesPlan) -> dict[str, object]:
    """Write the plan as the JSON the rename reports under `names`.

    Returns:
        The changes, moves, edits per repository and the files left alone.

    """

    def rows(found: list[FileEdit]) -> list[dict[str, object]]:
        return [{"path": e.path, "replacements": e.replacements, "kinds": sorted(e.kinds)} for e in found]

    documents = _documents_record(plan.documents)
    return {
        "documents": documents,
        "changes": [
            {"repo": s.new, "kind": c.kind, "old": c.old, "new": c.new} for s in plan.subjects for c in s.changes
        ],
        "notes": [n for s in plan.subjects for n in s.notes],
        "moves": [{"repo": s.new, "old": m.old, "new": m.new} for s in plan.subjects for m in s.moves],
        "edits": {n: rows(found) for n, found in plan.edits.items()},
        "waits_on": plan.waits_on,
        "not_edited": {
            why: [{"repo": n, "path": e.path, "replacements": e.replacements, "lines": list(e.lines)} for n, e in held]
            for why, held in plan.held_back.items()
        },
    }


def _rename_names(
    st: State,
    args: argparse.Namespace,
    pairs: list[tuple[str, str]],
    res: dict[str, object],
    steps: list[str],
) -> bool:
    """Plan, and unless it is a dry run carry out, the stack and Python name changes of a rename.

    `pairs` is (old name, new name) for each repository whose names change.

    Returns:
        False when the plan failed or a repository's change did not reach a pull request.

    """
    try:
        plan = _names_plan(st, pairs, set(args.skip_repo or []), set(args.keep_src or []), dry_run=args.dry_run)
    except (NameSweepError, PolyrepoError) as exc:
        res["names_error"] = str(exc)
        steps.append(f"stack and Python names NOT planned: {exc}")
        return False
    plan.branch_slug = args.branch_slug or SHARED_BRANCH_SLUG
    lines = _names_lines(plan)
    steps.extend(lines or ["stack and Python names: already what atw-naming gives, no reference to update"])
    res["names"] = _names_record(plan)
    if args.dry_run or not plan.edits:
        return True
    rows = _names_apply(st.cfg, plan, args)
    res["pull_requests"] = rows
    steps.extend(_pr_line(row) for row in rows)
    steps.extend(_update_matrix_names(st.cfg, plan))
    return all(row["status"] == "pr-opened" for row in rows)


def _update_matrix_names(cfg: Config, plan: _NamesPlan) -> list[str]:
    """Re-key in the matrix every package a rename changed, and commit the matrix when one was re-keyed.

    A package entry is named by the distribution, so a distribution that changes re-keys its
    entry and both ends of every relationship it has; an entry already under the new name is
    left. The vault documents are not read here: the filing-clerk changes them, and the steward
    then reads the changed ones into the matrix (`atw-matrix sync-documents --paths`).

    Returns:
        A line for each matrix command run, or that failed.

    """
    steps: list[str] = []
    try:
        steps.extend(_rekey_packages(cfg, plan))
        if steps:
            steps.append(f"matrix: {matrix_commit(cfg)}")
    except PolyrepoError as exc:
        steps.append(f"matrix NOT updated: {exc}")
    return steps


def _rekey_packages(cfg: Config, plan: _NamesPlan) -> list[str]:
    """Re-key each package entry the matrix holds under an old distribution name.

    Returns:
        A line for each `atw-matrix rename` run.

    """
    steps: list[str] = []
    for c in (c for s in plan.subjects for c in s.changes if c.kind == "distribution"):
        old, new = f"package:{normalize(c.old)}", f"package:{normalize(c.new)}"
        if old != new and _matrix_has(cfg, old) and not _matrix_has(cfg, new):
            result = matrix_run(cfg, ["rename", "--from", old, "--to", new])
            side = str(_map(_map(matrix_run(cfg, ["node", new]), "node").get("entry"), "entry").get("side"))
            matrix_run(cfg, ["put", "package", "--side", side, "--id", new, "--name", new.removeprefix("package:")])
            steps.append(f"matrix rename {old} -> {new}: {json.dumps(result, sort_keys=True)[:200]}")
    return steps


def _matrix_has(cfg: Config, entry_id: str) -> bool:
    """Tell whether the matrix holds an entry.

    Returns:
        True when `atw-matrix node` finds it.

    """
    try:
        matrix_run(cfg, ["node", entry_id])
    except PolyrepoError:
        return False
    return True


def _pr_line(row: dict[str, object]) -> str:
    """Write one repository's outcome as a step line.

    Returns:
        The line.

    """
    head = f"{row['repo']}: {row['status']}"
    parts = [str(row[k]) for k in ("pr_url", "error") if row.get(k)]
    if row.get("waits_on"):
        parts.append(f"waits on {', '.join(str(w) for w in _seq(row['waits_on'], 'waits_on'))}")
    return head + (": " + "; ".join(parts) if parts else "")


def _names_apply(cfg: Config, plan: _NamesPlan, args: argparse.Namespace) -> list[dict[str, object]]:
    """Open one pull request for each repository that changes: those that wait on no one first.

    Returns:
        One row per repository: its status, pull request URL, worktree and any error.

    """
    settings = _rename_settings(cfg)
    order = sorted(plan.edits, key=lambda n: (n in plan.waits_on, n not in plan.holders(), n.lower()))
    with concurrent.futures.ThreadPoolExecutor(max_workers=APPLY_WORKERS) as ex:
        return list(ex.map(lambda name: _apply_repo(cfg, plan, name, settings, args), order))


def _apply_repo(
    cfg: Config,
    plan: _NamesPlan,
    name: str,
    settings: tuple[list[str], Path],
    args: argparse.Namespace,
) -> dict[str, object]:
    """Change one repository in a worktree on its own branch, check it, commit it and open its pull request.

    A repository that waits on the one holding a renamed package is not checked: its code
    imports a package that does not exist until that one is released.

    Returns:
        The row for this repository; `status` is `pr-opened` or the step that failed.

    """
    excludes, pr_command = settings
    if name in plan.keep_src:
        excludes = [*excludes, "src/*"]
    slug = plan.slug()
    worktree = plan.paths[name] / ".worktrees" / f"{RENAME_BRANCH}-{slug}"
    row: dict[str, object] = {"repo": name, "status": "failed", "waits_on": plan.waits_on.get(name)}
    _exclude_worktrees(plan.paths[name])
    for argv in (
        ["fetch", "origin", cfg.default_branch],
        [
            "worktree",
            "add",
            "--no-track",
            "-b",
            f"{RENAME_BRANCH}/{slug}",
            str(worktree),
            f"origin/{cfg.default_branch}",
        ],
    ):
        cp = git(plan.paths[name], *argv, timeout=FETCH_TIMEOUT if argv[0] == "fetch" else GIT_TIMEOUT)
        if cp.returncode != 0:
            row["error"] = f"git {argv[0]} failed: {_last_line(cp)}"
            return row
    row["worktree"] = str(worktree)
    if error := _stage_changes(plan, name, worktree, excludes, row):
        row["error"] = error
        return row
    failure = _run_checks(worktree, waiting=name in plan.waits_on)
    if failure:
        row["checks"] = failure
    title, body = _pr_text(plan, name)
    if failure:
        body += f"\n\nThe repository's checks failed before this pull request was opened:\n{failure}"
    _commit_and_open(worktree, (title, body), pr_command, args, row)
    return row


def _commit_and_open(
    worktree: Path,
    text: tuple[str, str],
    pr_command: Path,
    args: argparse.Namespace,
    row: dict[str, object],
) -> None:
    """Commit the staged changes with the text's subject and body, and open the pull request.

    The row gets `status` `pr-opened` (with `pr_url`), `commit-failed` or `pr-failed`.
    """
    title, body = text
    message = [body, args.trailer] if args.trailer else [body]
    for argv in (["add", "-A"], ["commit", "-m", title, *[x for m in message for x in ("-m", m)]]):
        cp = git(worktree, *argv)
        if cp.returncode != 0:
            row.update(status="commit-failed", error=_last_line(cp))
            return
    _open_pr(worktree, (title, body), (pr_command, args.pr_footer), row)


def _open_pr(
    worktree: Path,
    text: tuple[str, str],
    how: tuple[Path, str | None],
    row: dict[str, object],
) -> None:
    """Push the worktree's branch and open its pull request with the project's PR command.

    `text` is the title and body, `how` the PR command and a footer line for the body. The row gets
    `status` `pr-opened` (with `pr_url`, and `error` when auto-merge could not be armed) or `pr-failed`.
    """
    title, body = text
    pr_command, pr_footer = how
    footer = f"\n\n{pr_footer}" if pr_footer else ""
    cp = run([str(pr_command), "--title", title, "--body", body + footer], cwd=worktree, timeout=PR_TIMEOUT)
    url = cp.stdout.strip().splitlines()[0] if cp.stdout.strip() else ""
    if url and cp.returncode in {0, PR_AUTOMERGE_NOT_ARMED}:
        row.update(status="pr-opened", pr_url=url)
        if cp.returncode == PR_AUTOMERGE_NOT_ARMED:
            row["error"] = f"auto-merge not armed: {_last_line(cp)}"
    else:
        row.update(status="pr-failed", error=_last_line(cp))


def _stage_changes(
    plan: _NamesPlan,
    name: str,
    worktree: Path,
    excludes: list[str],
    row: dict[str, object],
) -> str | None:
    """Make one repository's changes in its worktree: the moves, the settings, the sweep, the import order.

    Returns:
        None when the changes are staged, else why they could not be made.

    """
    moved = False
    try:
        for s in (s for s in plan.subjects if s.new == name):
            apply_moves(_sweep_git, worktree, s.moves)
            moved = moved or any(m.new for m in s.moves)
        sweep_repo(_sweep_git, SweepTarget(name, worktree), plan.rules, excludes, write=True)
        if moved:
            row["settings"] = adjust_pyproject(worktree)
    except NameSweepError as exc:
        return str(exc)
    cp = git(worktree, "add", "-A")
    if cp.returncode == 0:
        row["ruff"] = _fix_changed_python(worktree)
    return None


def _pr_text(plan: _NamesPlan, name: str) -> tuple[str, str]:
    """Write the commit subject and the body for one repository's change.

    A repository whose own names change is titled by them; one that only follows another's
    new names says so.

    Returns:
        (the `type(scope): description` subject, the body).

    """
    own = [c for s in plan.subjects if s.new == name for c in s.changes]
    shown = [f"{KIND_NOUNS[c.kind]} {c.old} to {c.new}" for c in own]
    if shown:
        more = f" and {len(shown) - TITLE_NAMES} more" if len(shown) > TITLE_NAMES else ""
        title = f"refactor(names): rename {', '.join(shown[:TITLE_NAMES])}{more}"
    else:
        followed = plan.waits_on.get(name) or [h for h in plan.holders() if h != name]
        more = f" and {len(followed) - TITLE_NAMES} more" if len(followed) > TITLE_NAMES else ""
        title = f"refactor(names): follow the new names of {', '.join(followed[:TITLE_NAMES])}{more}"
    used = {label for e in plan.edits.get(name, []) for label in e.labels}
    lines = [
        f"- {s.new}: {KIND_NOUNS[c.kind]} {c.old} -> {c.new}"
        for s in plan.subjects
        for c in s.changes
        if s.new == name or change_label(c) in used
    ]
    if name in plan.waits_on:
        lines.append(f"\nWaits on {', '.join(plan.waits_on[name])}: a new package name is importable once released.")
    return title, "\n".join(lines)


def _fix_changed_python(worktree: Path) -> str:
    """Put the import order and format of the Python files the change touched right, with the repo's ruff settings.

    The new import names move a line among the groups `isort` keeps, and a longer name can
    pass the line length, so only the files the change touched are fixed (`I` rules and
    `ruff format`), and nothing else in the repository is reformatted.

    Returns:
        A short note of what ran.

    """
    cp = git(worktree, "diff", "--cached", "--name-only", "--diff-filter=AMR", "-z")
    files = [f for f in cp.stdout.split("\0") if f.endswith(".py")]
    if cp.returncode != 0 or not files:
        return "no Python files changed"
    ran: list[str] = []
    for argv in (
        ["uvx", "ruff", "check", "--select", "I", "--fix", "--fix-only", "--quiet", *files],
        ["uvx", "ruff", "format", "--quiet", *files],
    ):
        out = run(argv, cwd=worktree, timeout=CHECK_TIMEOUT)
        ran.append(f"{argv[2]} exit {out.returncode}")
    return ", ".join(ran)


def _run_checks(worktree: Path, *, waiting: bool = False) -> str | None:
    """Run the repository's own checks in the worktree, as its Taskfile declares them.

    The tasks are `lint` (ruff, and mypy where the Taskfile puts it there), `typecheck` and
    `test`. A repository that waits on a library's renamed package cannot install or import
    it until the library is released, so for it only `ruff check` runs, which needs no
    installed package.

    Returns:
        None when every check passed (or none is declared), else what failed.

    """
    if waiting:
        cp = run(["uvx", "ruff", "check", "--quiet", "."], cwd=worktree, timeout=CHECK_TIMEOUT)
        if cp.returncode != 0:
            tail = "\n".join((cp.stdout + cp.stderr).strip().splitlines()[-CHECK_TAIL_LINES:])
            return f"ruff check failed:\n{tail}"
        return None
    taskfile = worktree / "Taskfile.yml"
    declared = set(re.findall(r"(?m)^  ([a-z][\w-]*):\s*$", taskfile.read_text())) if taskfile.is_file() else set()
    for task in (t for t in CHECK_TASKS if t in declared):
        cp = run(["task", task], cwd=worktree, timeout=CHECK_TIMEOUT)
        if cp.returncode != 0:
            tail = "\n".join((cp.stdout + cp.stderr).strip().splitlines()[-CHECK_TAIL_LINES:])
            return f"task {task} failed:\n{tail}"
    return None


DEPRECATED_PR_COMMENT = "Closed: this repository is deprecated."


def open_prs(cfg: Config, repo: str) -> list[PullRequest]:
    """List a GitHub repo's open pull requests.

    When gh cannot list them, the GitFailedError that `must` raises propagates.

    Returns:
        One {number, title, url} per open pull request.

    Raises:
        PolyrepoError: when gh's answer is not a list of mappings.

    """
    cp = run(
        [
            "gh", "pr", "list", "--repo", f"{cfg.owner}/{repo}", "--state", "open",
            "--limit", "500", "--json", "number,title,url",
        ],
        timeout=120,
    )  # fmt: skip
    must(cp)
    prs: object = json.loads(cp.stdout or "[]")
    if not isinstance(prs, list):
        msg = f"gh pr list for {cfg.owner}/{repo} did not return a list"
        raise PolyrepoError(msg)
    return [parse_pull_request(p, repo, f"gh pr list for {cfg.owner}/{repo}") for p in prs]


def close_pr(cfg: Config, repo: str, number: int) -> str | None:
    """Close one pull request with the deprecation comment; its branch is kept.

    Returns:
        None when it closed, else gh's error.

    """
    cp = run(
        [
            "gh", "pr", "close", str(number), "--repo", f"{cfg.owner}/{repo}",
            "--comment", DEPRECATED_PR_COMMENT,
        ],
        timeout=120,
    )  # fmt: skip
    return None if cp.returncode == 0 else _last_line(cp)


def _close_repo_prs(cfg: Config, repo: str, dry_run: bool, res: dict[str, object], steps: list[str]) -> bool:
    """Close every open pull request of a repo, recording each in res["closed_prs"].

    Returns:
        False when the pull requests could not be listed or one did not close.

    """
    try:
        prs = open_prs(cfg, repo)
    except (GitFailedError, json.JSONDecodeError) as exc:
        pr_error = f"could not list open pull requests: {exc}"
        res["pr_error"] = pr_error
        steps.append(f"open pull requests NOT closed: {pr_error}")
        return False
    ok = True
    closed: list[dict[str, object]] = []
    for pr in prs:
        status: PrCloseStatus = "planned" if dry_run else "closed"
        error: str | None = None
        if not dry_run and (err := close_pr(cfg, repo, pr.number)):
            status, error, ok = "failed", err, False
        verb: dict[PrCloseStatus, str] = {"planned": "close", "closed": "closed", "failed": "FAILED to close"}
        steps.append(
            f"{verb[status]} pull request #{pr.number} {pr.title}" + (f": {error}" if error else ""),
        )
        row: dict[str, object] = {"number": pr.number, "title": pr.title, "url": pr.url, "status": status}
        if error:
            row["error"] = error
        closed.append(row)
    if not prs:
        steps.append("no open pull requests to close")
    res["closed_prs"] = closed
    return ok


def _worktrees(repo: Path) -> list[Worktree]:
    """List a clone's linked worktrees (not its main one).

    When git cannot list them, the GitFailedError that `must` raises propagates.

    Returns:
        One {path, locked, prunable} per linked worktree.

    """
    cp = git(repo, "worktree", "list", "--porcelain")
    must(cp)
    out: list[Worktree] = []
    for block in cp.stdout.strip().split("\n\n")[1:]:
        lines = block.splitlines()
        path = next(
            (ln[len("worktree ") :] for ln in lines if ln.startswith("worktree ")),
            None,
        )
        if path:
            out.append(
                Worktree(
                    path=Path(path),
                    locked=any(ln.startswith("locked") for ln in lines),
                    prunable=any(ln.startswith("prunable") for ln in lines),
                ),
            )
    return out


def clone_local_work(repo: Path) -> tuple[list[str], list[Path]]:
    """Find work in a clone that exists only on this machine.

    Checks the clone and every linked worktree for uncommitted changes and untracked files
    outside ignored paths, the clone for a stash, and every local branch and every
    worktree's HEAD for commits that no remote-tracking branch contains.

    Returns:
        The reasons not to delete it (empty when nothing would be lost), and the linked
        worktrees that hold no such work, which may be removed.

    """
    reasons: list[str] = []
    try:
        wts = _worktrees(repo)
    except GitFailedError as exc:
        return [f"cannot list worktrees: {exc}"], []
    trees = [repo] + [w.path for w in wts if not w.prunable]
    for t in trees:
        reasons.extend(_tree_local_work(t))
    cp = git(repo, "stash", "list")
    if cp.returncode != 0:
        reasons.append(f"git stash list failed: {_last_line(cp)}")
    elif stashes := [ln for ln in cp.stdout.splitlines() if ln.strip()]:
        reasons.append(f"stash entries: {len(stashes)}")
    reasons.extend(_branch_local_work(repo))
    removable = [] if reasons else [w.path for w in wts]
    return reasons, removable


def _tree_local_work(t: Path) -> list[str]:
    """Find uncommitted or untracked files in one working tree, and commits HEAD has on no remote.

    Returns:
        The reasons not to delete the tree.

    """
    reasons: list[str] = []
    cp = git(t, "status", "--porcelain=v1", "--untracked-files=normal")
    if cp.returncode != 0:
        reasons.append(f"{t}: git status failed: {_last_line(cp)}")
    elif files := [ln[3:] for ln in cp.stdout.splitlines() if ln.strip()]:
        reasons.append(
            f"{t}: {len(files)} uncommitted or untracked file(s): "
            + ", ".join(files[:FILES_SHOWN])
            + (" ..." if len(files) > FILES_SHOWN else ""),
        )
    cp = git(t, "rev-list", "--count", "HEAD", "--not", "--remotes")
    if cp.returncode == 0 and cp.stdout.strip() not in {"", "0"}:
        reasons.append(
            f"{t}: HEAD has {cp.stdout.strip()} commit(s) on no remote branch",
        )
    return reasons


def _branch_local_work(repo: Path) -> list[str]:
    """Find local branches with commits that no remote-tracking branch contains.

    Returns:
        The reasons not to delete the clone.

    """
    reasons: list[str] = []
    cp = git(
        repo,
        "for-each-ref",
        "--format=%(refname:short)",
        "refs/heads",
    )
    if cp.returncode != 0:
        reasons.append(f"cannot list local branches: {_last_line(cp)}")
    for b in cp.stdout.split() if cp.returncode == 0 else []:
        n = git(repo, "rev-list", "--count", f"refs/heads/{b}", "--not", "--remotes")
        if n.returncode != 0:
            reasons.append(f"branch {b}: rev-list failed: {_last_line(n)}")
        elif n.stdout.strip() != "0":
            reasons.append(
                f"branch {b} has {n.stdout.strip()} commit(s) on no remote branch",
            )
    return reasons


def delete_clone(
    cfg: Config,
    clone: Path,
    final: Path,
    dry_run: bool,
    res: dict[str, object],
) -> tuple[bool, list[str]]:
    """Delete a deprecated repo's local clone and its linked worktrees, when no work exists only in them.

    Otherwise the clone is left and the path to delete by hand is named.

    `clone` is where the clone is now and `final` where it is after the rename (the same
    path once the rename is done). `final` must be under the repository root and its name
    must carry the deprecated prefix the naming note gives. Records the outcome in res["clone"]; the caller notes
    the steps of a deletion for the commit message.

    Returns:
        False when the clone was left in place or could not be deleted, and the steps taken or planned.

    """
    path, final = clone.resolve(), final.resolve()
    bad = (
        f"{final} is not under {cfg.root}"
        if not final.is_relative_to(cfg.root) or final == cfg.root
        else f"{final.name} does not start with {cfg.rules.deprecated_prefix}"
        if not cfg.is_deprecated_name(final.name)
        else None
    )
    steps: list[str] = []
    reasons = [bad] if bad else []
    worktrees: list[Path] = []
    if not bad:
        reasons, worktrees = clone_local_work(path)
    if reasons:
        res["clone"] = {"path": str(final), "status": "refused", "reasons": reasons}
        steps.append(
            f"local clone NOT {'to be ' if dry_run else ''}deleted: {'; '.join(reasons)}; "
            f"once resolved, delete it by hand: {final}",
        )
        return False, steps
    if dry_run:
        res["clone"] = {
            "path": str(final),
            "status": "planned",
            "worktrees": [str(w) for w in worktrees],
        }
        steps.extend(f"remove linked worktree {w}" for w in worktrees)
        steps.append(f"delete the local clone {final}")
        return True, steps
    done: list[str] = []
    try:
        for w in worktrees:
            must(git(path, "worktree", "remove", "--force", "--force", str(w)))
            done.append(f"removed linked worktree {w}")
        must(git(path, "worktree", "prune"))
        shutil.rmtree(path)
    except (GitFailedError, OSError) as exc:
        res["clone"] = {"path": str(path), "status": "failed", "error": str(exc)}
        steps.extend(done)
        steps.append(
            f"local clone NOT deleted: {exc}; delete it by hand: {path}",
        )
        return False, steps
    done.append(f"deleted the local clone {path}")
    res["clone"] = {
        "path": str(path),
        "status": "deleted",
        "worktrees": [str(w) for w in worktrees],
    }
    steps.extend(done)
    return True, steps


def cmd_deprecate(args: argparse.Namespace, cfg: Config) -> int:
    """Deprecate a repo: rename it, close its pull requests, then delete its local clone.

    The rename to its deprecated- name dates the deprecation; every open pull request is
    closed with the deprecation comment. The vault documents that still carry the old name (in the
    folders the config's `rename.documents` names) are reported under `documents`, never edited:
    the filing-clerk changes them.

    The clone is deleted only when it holds no work that exists only on this machine
    (uncommitted or untracked files, a stash, commits on no remote branch, or such work in
    a linked worktree); otherwise it is left, the rest of the deprecation stands, and the
    path to delete by hand is reported. Its linked worktrees are removed with it.

    The matrix must hold no stack that names the repo: the rename refuses, with the stack ids,
    until each is moved (`put stack --repository`) or removed (`remove stack:<id> --held`).

    Returns:
        0 on success, 1 when a step failed part way, a pull request did not close, or the
        local clone was left in place.

    Raises:
        PolyrepoError: when the repo is already deprecated.

    """
    st = gather(cfg, fetch=True, use_cache=not args.no_cache)
    (name,) = st.resolve([args.repo])
    if cfg.is_deprecated_name(name):
        msg = f"{name} is already deprecated"
        raise PolyrepoError(msg)
    new = cfg.rules.deprecated_name(name)
    r = st.local.get(name) or st.local.get(new)

    def after(res: dict[str, object], steps: list[str]) -> bool:
        docs = _repository_documents(cfg, name, new)
        res["documents"] = _documents_record(docs)
        steps.extend(_documents_lines(docs))
        ok = _close_repo_prs(cfg, name if args.dry_run else new, args.dry_run, res, steps)
        if r is None:
            steps.append("no local clone to delete")
            return ok
        final = r.path.with_name(new)
        clone = r.path if args.dry_run else final
        deleted, clone_steps = delete_clone(cfg, clone, final, args.dry_run, res)
        steps.extend(clone_steps)
        if deleted and not args.dry_run:
            note_change(cfg, f"polyrepo deprecate {final.name}: local clone", clone_steps)
        return deleted and ok

    return _run_rename(args, st, name, new, after=after)


# agents-sync ----------------------------------------------------------------------------------


PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"  # ruff: ignore[hardcoded-password-string] - a plugin path placeholder, not a secret
PLUGIN_IMPORT = re.compile(r"^@\$\{CLAUDE_PLUGIN_ROOT\}/(\S+?)`?\s*$", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class AgentsBlock:
    """One marked block agents-sync owns in every repo's AGENTS.md."""

    marker: str
    text: str
    exclude: frozenset[str]
    exclude_spaces: frozenset[str] = frozenset()
    legacy: str = ""

    def render(self, name: str) -> str:
        """Return the block text for one repo: `{{repo}}` becomes the repo's name.

        Returns:
            The text to write.

        """
        return self.text.replace("{{repo}}", name)

    def legacy_pattern(self) -> re.Pattern[str] | None:
        """Return the regex of the older unmarked section this block replaces, if it has one.

        The older section is `<!-- <legacy>:start -->` to `<!-- <legacy>:end -->` with the
        blank lines after it.

        Returns:
            The compiled pattern, or None when the block replaces no older section.

        """
        if not self.legacy:
            return None
        m = re.escape(self.legacy)
        return re.compile(rf"<!-- {m}:start -->.*?<!-- {m}:end -->\n*", re.DOTALL)

    def pattern(self) -> re.Pattern[str]:
        """Return the regex matching this block, markers included, whatever its BEGIN note.

        Returns:
            The compiled pattern.

        """
        m = re.escape(self.marker)
        return re.compile(rf"<!-- BEGIN {m}\b.*?<!-- END {m} -->", re.DOTALL)


def _plugin_block_body(f: Path) -> str:
    """Render a plugin block source: drop its front matter and inline every plugin import.

    A line `@${CLAUDE_PLUGIN_ROOT}/<file>` is replaced by that plugin file's content, so the
    block names no installed-plugin path and no plugin version.

    Returns:
        The block body.

    Raises:
        PolyrepoError: when an imported file is missing or a plugin path is left in the body.

    """
    text = f.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]

    def inline(m: re.Match[str]) -> str:
        src = PLUGIN_ROOT / m.group(1)
        if not src.is_file():
            msg = f"{f.name} imports {m.group(1)}, which is not in the plugin"
            raise PolyrepoError(msg)
        return src.read_text().strip()

    body = PLUGIN_IMPORT.sub(inline, text).strip()
    if PLUGIN_ROOT_TOKEN in body:
        msg = f"{f.name} still names {PLUGIN_ROOT_TOKEN} after its imports are inlined"
        raise PolyrepoError(msg)
    return body


def _agents_blocks(cfg: Config) -> list[AgentsBlock]:
    """Return every block agents-sync owns, in the order they appear in a new AGENTS.md.

    A block's content comes from `block_file` (relative to the config folder) or from
    `plugin_file` (relative to this plugin's root, rendered by _plugin_block_body).

    Returns:
        The blocks.

    Raises:
        PolyrepoError: when a block has no source or its source file is missing.

    """
    sc = _map(cfg.raw.get("agents_sync") or {}, "config agents_sync")
    specs = [_map(s, "agents_sync block") for s in _seq(sc.get("blocks") or [], "agents_sync blocks")]
    out = []
    for spec in specs:
        marker = str(spec.get("marker") or "")
        if spec.get("plugin_file"):
            f = PLUGIN_ROOT / str(spec["plugin_file"])
        elif spec.get("block_file"):
            f = (cfg.file.parent / str(spec["block_file"])).resolve()
        else:
            msg = f"agents_sync block {marker or '(unnamed)'} names no source file"
            raise PolyrepoError(msg)
        if not marker or not f.is_file():
            msg = f"agents_sync block {marker or '(unnamed)'}: {f} not found"
            raise PolyrepoError(msg)
        body = _plugin_block_body(f) if spec.get("plugin_file") else f.read_text().strip()
        note = str(spec.get("note") or "written by polyrepo agents-sync")
        out.append(
            AgentsBlock(
                marker,
                f"<!-- BEGIN {marker}: {note} -->\n{body}\n<!-- END {marker} -->",
                frozenset(_strs(spec.get("exclude") or [], "agents_sync exclude")),
                frozenset(_strs(spec.get("exclude_spaces") or [], "agents_sync exclude_spaces")),
                str(spec.get("legacy_marker") or ""),
            ),
        )
    if not out:
        msg = "agents_sync.blocks in the polyrepo config lists no block"
        raise PolyrepoError(msg)
    return out


def _blocks_for(blocks: list[AgentsBlock], name: str, space: str = "") -> list[AgentsBlock]:
    """Return the blocks a repo receives.

    Returns:
        The blocks whose exclude list does not name the repo and whose excluded spaces do not
        include the repo's app space.

    """
    return [b for b in blocks if name not in b.exclude and space not in b.exclude_spaces]


def _literal(text: str) -> Callable[[re.Match[str]], str]:
    """Build a re.sub replacement that inserts text as written, with no backslash expansion.

    Returns:
        A replacement function that ignores its match and returns text.

    """

    def replace(_m: re.Match[str]) -> str:
        return text

    return replace


def _with_blocks(text: str | None, blocks: list[AgentsBlock], name: str) -> str:
    """Put each block into AGENTS.md text: replace its marked copy, or append one.

    Returns:
        The new text.

    """
    out = f"# {name}\n" if text is None else text
    for b in blocks:
        rx = b.pattern()
        legacy = b.legacy_pattern()
        body = b.render(name)
        if rx.search(out):
            out = rx.sub(_literal(body), out, count=1)
            if legacy is not None:
                out = legacy.sub("", out)
        elif legacy is not None and legacy.search(out):
            out = legacy.sub(_literal(body + "\n\n"), out, count=1)
        else:
            out = out.rstrip("\n") + "\n\n" + body + "\n"
    return out


def _without_blocks(text: str, blocks: list[AgentsBlock]) -> str:
    """Return the text with every owned block removed, for comparing what else changed.

    Returns:
        The text outside the owned blocks.

    """
    for b in blocks:
        text = b.pattern().sub("", text)
        legacy = b.legacy_pattern()
        if legacy is not None:
            text = legacy.sub("", text)
    return text


def _with_trailer(message: str, trailer: str | None = None) -> str:
    """End a commit message with a trailer line: the one given, else POLYREPO_COMMIT_TRAILER.

    Returns:
        The message, with the trailer after a blank line unless the message has it already.

    """
    line = trailer or os.environ.get(COMMIT_TRAILER_ENV) or ""
    return message if not line or line in message else f"{message}\n\n{line}"


def _commit_paths(
    repo: Path,
    paths: list[str],
    message: str,
    force: bool = False,
) -> None:
    """Commit only these paths, re-staging once when a pre-commit hook rewrote them.

    With force, the paths are staged even inside an ignored folder (the beads fleet list
    is a tracked file under the gitignored `.beads/`). The message ends with the trailer line
    of POLYREPO_COMMIT_TRAILER when it is set. When the commit still fails, the
    GitFailedError that `must` raises propagates.
    """
    message = _with_trailer(message)
    add = ["add", "-f", "--"] if force else ["add", "--"]
    must(git(repo, *add, *paths))
    cp = git(repo, "commit", "-m", message, "--", *paths, timeout=300)
    if cp.returncode != 0:
        must(git(repo, *add, *paths))
        must(git(repo, "commit", "-m", message, "--", *paths, timeout=300))


AGENTS_SYNC_SUBJECT = "docs(agents): sync the shared instruction blocks"
AGENTS_SYNC_DONE = frozenset({"pushed", "current-on-origin"})
AGENTS_SYNC_ADVANCED = frozenset({"up-to-date", "rebased", "fast-forwarded"})


def _sync_one(
    cfg: Config,
    r: LocalRepo,
    blocks: list[AgentsBlock],
    write: bool,
    trailer: str | None,
) -> dict[str, object]:
    """Bring one repo's AGENTS.md blocks current: committed on main in its primary working tree and pushed.

    AGENTS.md is tier 2 in every repository, tooling for building the product, so the blocks are
    committed directly on main whatever the repo's tier: no worktree, no branch and no pull request.
    When writing, the primary tree's main is first brought up to `origin/main` (a fast-forward, or a
    rebase of local commits), so the commit is a fast-forward push.

    Returns:
        {repo, state} plus, when it wrote, the status and any detail.

    """
    if write and (stopped := _advance_for_sync(cfg, r)) is not None:
        return {"repo": r.name, "state": "stale-main", **stopped}
    f = r.path / "AGENTS.md"
    cur = f.read_text() if f.is_file() else None
    want = _with_blocks(cur, blocks, r.name)
    res: dict[str, object] = {"repo": r.name, "state": _agents_state(cur, want, blocks)}
    if res["state"] == "current" or not write:
        return res
    return {**res, **_sync_on_main(cfg, r, blocks, (cur, want), trailer)}


def _ff_past_dirty_files(r: LocalRepo, branch: str) -> bool:
    """Fast-forward the checked-out main to origin/main while the tree has uncommitted changes.

    Git refuses the merge when an incoming change touches a file with uncommitted changes, and then
    nothing is moved; the uncommitted files are never changed or committed by this.

    Returns:
        True when main now equals origin/main, else False.

    """
    cp = git(r.path, "merge", "--ff-only", "--quiet", f"refs/remotes/origin/{branch}")
    return cp.returncode == 0


def _advance_for_sync(cfg: Config, r: LocalRepo) -> dict[str, object] | None:
    """Fetch origin and bring the primary tree's main up to origin/main before a commit.

    Returns:
        None when main is at or past origin/main, else {status, detail} saying why it was not
        brought up (fetch failed, no origin, dirty tree, conflict).

    """
    if not git_out(r.path, "remote", "get-url", "origin"):
        return {"status": "skipped", "detail": "no origin"}
    moved = rebase_one(cfg, r)
    if moved["status"] in AGENTS_SYNC_ADVANCED:
        return None
    if moved["status"] == "dirty" and moved.get("ahead") == 0 and _ff_past_dirty_files(r, cfg.default_branch):
        return None
    detail = "; ".join(s for s in (str(moved["status"]), str(moved.get("detail") or "")) if s)
    return {"status": "skipped", "detail": f"main not brought up to origin/{cfg.default_branch}: {detail}"}


def _sync_on_main(
    cfg: Config,
    r: LocalRepo,
    blocks: list[AgentsBlock],
    texts: tuple[str | None, str],
    trailer: str | None,
) -> dict[str, object]:
    """Commit the new AGENTS.md on the default branch in the primary working tree and push it.

    A rejected push (for example branch protection) leaves the commit local, status `committed`.

    `texts` is the file's current text (None when it has none) and the text it should have.

    Returns:
        The status (`pushed`, `committed` when the push failed, `failed`, `skipped`) and any detail.

    """
    cur, want = texts
    f = r.path / "AGENTS.md"
    b = cfg.default_branch
    branch = git_out(r.path, "symbolic-ref", "--short", "-q", "HEAD")
    if branch != b:
        return {"status": "skipped", "detail": f"on {branch}, not {b}"}
    if cur is not None and _edited_outside_blocks(r.path, cur, blocks):
        return {"status": "skipped", "detail": "AGENTS.md has uncommitted changes outside the synced blocks"}
    f.write_text(want)
    paths = ["AGENTS.md"]
    claude = r.path / "CLAUDE.md"
    if cur is None and not claude.exists() and not claude.is_symlink():
        claude.symlink_to("AGENTS.md")
        paths.append("CLAUDE.md")
    try:
        _commit_paths(r.path, paths, _with_trailer(AGENTS_SYNC_SUBJECT, trailer))
    except GitFailedError as exc:
        git(r.path, "reset", "-q", "--", *paths)
        if cur is None:
            f.unlink(missing_ok=True)
        else:
            f.write_text(cur)
        if "CLAUDE.md" in paths:
            claude.unlink(missing_ok=True)
        return {"status": "failed", "detail": str(exc)}
    cp = git(r.path, "push", "origin", b, timeout=120)
    commit = git_out(r.path, "rev-parse", "--short=8", "HEAD")
    if cp.returncode != 0:
        return {"status": "committed", "commit": commit, "detail": f"push failed: {_last_line(cp)}"}
    return {"status": "pushed", "commit": commit}


def _agents_state(cur: str | None, want: str, blocks: list[AgentsBlock]) -> str:
    """Classify a repo's AGENTS.md against the text it should have.

    Returns:
        current, missing-file, outdated or missing-block.

    """
    if cur == want:
        return "current"
    if cur is None:
        return "missing-file"
    if all(b.pattern().search(cur) for b in blocks):
        return "outdated"
    return "missing-block"


def _edited_outside_blocks(repo: Path, cur: str, blocks: list[AgentsBlock]) -> bool:
    """Say whether AGENTS.md has uncommitted changes outside the synced blocks.

    Returns:
        True when it is modified and differs from HEAD outside the blocks, or HEAD has none.

    """
    if not git_out(repo, "status", "--porcelain", "--", "AGENTS.md"):
        return False
    head = git(repo, "show", "HEAD:AGENTS.md")
    return head.returncode != 0 or _without_blocks(head.stdout, blocks) != _without_blocks(cur, blocks)


def cmd_agents_sync(args: argparse.Namespace, cfg: Config) -> int:
    """Write the owned blocks into every repo's AGENTS.md, committing and pushing each repo.

    Every repo is committed on its default branch in its primary working tree and pushed, whatever its
    tier: AGENTS.md is tier 2 in every repository (see `_sync_one`).

    Returns:
        0 when every repo is current (or was brought current and pushed), else 1.

    """
    blocks = _agents_blocks(cfg)
    repos = [
        (r, own)
        for r in _local_repos(cfg, args.repo, args.space)
        if not cfg.is_deprecated_name(r.name) and (own := _blocks_for(blocks, r.name, r.space))
    ]
    write = not args.check and not args.dry_run
    with concurrent.futures.ThreadPoolExecutor(max_workers=APPLY_WORKERS if write else WORKERS) as ex:
        results = list(
            ex.map(lambda rb: _sync_one(cfg, rb[0], rb[1], write, args.trailer), repos),
        )
    if write:
        bad = [x for x in results if x["state"] != "current" and x.get("status") not in AGENTS_SYNC_DONE]
    else:
        bad = [x for x in results if x["state"] != "current"]
    counts: dict[str, int] = {}
    for x in results:
        counts[str(x["state"])] = counts.get(str(x["state"]), 0) + 1

    def text() -> str:
        lines = [
            f"{len(results)} repos: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())),
        ]
        for x in results:
            if x["state"] == "current":
                continue
            st_ = str(x.get("status", "would update" if args.dry_run else ""))
            detail = str(x.get("detail", ""))
            lines.append(
                f"  {x['repo']}: {x['state']}{'  ' + st_ if st_ else ''}{'  ' + detail if detail else ''}",
            )
        return "\n".join(lines)

    emit(args, {"repos": results, "counts": counts, "not_current": len(bad)}, text)
    return 1 if bad else 0


# GitNexus ---------------------------------------------------------------------------------
# Every repo has GitNexus: `.gitnexusrc`, the `.gitnexus` ignore rule, the six
# skills in `.claude/skills/gitnexus/`, and the GITNEXUS block in AGENTS.md (an agents-sync
# block). The sources are files of the control repo named by the config's `gitnexus` section.
# Re-indexing is `gitnexus-reindex.sh`, which runs the one pinned GitNexus version.

GITNEXUS_RC = ".gitnexusrc"
GITNEXUS_SKILLS = ".claude/skills/gitnexus"
GITNEXUS_IGNORE = ".gitnexus"
GITNEXUS_INDEX_TIMEOUT = 3600


@dataclasses.dataclass(frozen=True)
class GitNexusSources:
    """The control repo files every repo's GitNexus setup is copied from."""

    rc: Path
    skills: Path
    reindex: Path


def _gitnexus_sources(cfg: Config) -> GitNexusSources:
    """Resolve the config's `gitnexus` section to the source files.

    Returns:
        The sources.

    Raises:
        PolyrepoError: when a key is missing or its file or folder does not exist.

    """
    gc = _map(cfg.raw.get("gitnexus") or {}, "config gitnexus")
    found: dict[str, Path] = {}
    for key in ("rc_file", "skills_dir", "reindex_script"):
        v = gc.get(key)
        if not isinstance(v, str) or not v:
            msg = f"config gitnexus.{key} is missing"
            raise PolyrepoError(msg)
        f = (cfg.file.parent / v).resolve()
        if not (f.is_dir() if key == "skills_dir" else f.is_file()):
            msg = f"config gitnexus.{key}: {f} not found"
            raise PolyrepoError(msg)
        found[key] = f
    return GitNexusSources(found["rc_file"], found["skills_dir"], found["reindex_script"])


def _gitnexus_plan(src: GitNexusSources, repo: Path) -> dict[str, bytes]:
    """Return the files a repo needs written for its GitNexus setup, path to new content.

    Returns:
        Repo-relative path to content; empty when the repo is complete.

    """
    plan: dict[str, bytes] = {}
    rc = repo / GITNEXUS_RC
    if not rc.is_file():
        plan[GITNEXUS_RC] = src.rc.read_bytes()
    gi = repo / ".gitignore"
    cur = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    if not any(ln.strip().rstrip("/").lstrip("/") == GITNEXUS_IGNORE for ln in cur.splitlines()):
        plan[".gitignore"] = (
            (cur.rstrip("\n") + f"\n\n# GitNexus index data\n{GITNEXUS_IGNORE}/\n").lstrip("\n").encode()
        )
    for f in sorted(src.skills.rglob("*")):
        if not f.is_file() or f.name == ".DS_Store":
            continue
        rel = f"{GITNEXUS_SKILLS}/{f.relative_to(src.skills).as_posix()}"
        dest = repo / rel
        if not dest.is_file() or dest.read_bytes() != f.read_bytes():
            plan[rel] = f.read_bytes()
    return plan


def gitnexus_install(cfg: Config, repo: Path) -> list[str]:
    """Write a repo's missing or outdated GitNexus files (no commit).

    Returns:
        The repo-relative paths written.

    """
    plan = _gitnexus_plan(_gitnexus_sources(cfg), repo)
    for rel, data in plan.items():
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return sorted(plan)


def gitnexus_index(cfg: Config, repo: Path) -> str | None:
    """Index one repo with the pinned GitNexus, through the control repo's reindex script.

    Returns:
        None on success, else the failure text.

    """
    cp = run([str(_gitnexus_sources(cfg).reindex), str(repo)], timeout=GITNEXUS_INDEX_TIMEOUT)
    return None if cp.returncode == 0 else f"gitnexus-reindex.sh exited {cp.returncode}: {_last_line(cp)}"


def _gitnexus_sync_one(cfg: Config, src: GitNexusSources, r: LocalRepo, write: bool) -> dict[str, object]:
    """Bring one repo's GitNexus files current, committing and pushing them when write is set.

    Returns:
        {repo, state, files} plus, when it wrote, the status and any detail.

    """
    plan = _gitnexus_plan(src, r.path)
    res: dict[str, object] = {"repo": r.name, "state": "outdated" if plan else "current", "files": sorted(plan)}
    if not plan or not write:
        return res
    b = cfg.default_branch
    branch = git_out(r.path, "symbolic-ref", "--short", "-q", "HEAD")
    if branch != b:
        return {**res, "status": "skipped", "detail": f"on {branch}, not {b}"}
    dirty = git_out(r.path, "status", "--porcelain", "--", *plan)
    if dirty:
        return {**res, "status": "skipped", "detail": "files to write have uncommitted changes"}
    for rel, data in plan.items():
        dest = r.path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    try:
        _commit_paths(r.path, sorted(plan), "chore(gitnexus): install the pinned GitNexus configuration and skills")
    except GitFailedError as exc:
        return {**res, "status": "failed", "detail": str(exc)}
    cp = git(r.path, "push", "origin", b, timeout=120)
    if cp.returncode != 0:
        return {**res, "status": "committed", "detail": f"push failed: {_last_line(cp)}"}
    return {**res, "status": "pushed"}


def cmd_gitnexus_sync(args: argparse.Namespace, cfg: Config) -> int:
    """Give every repo its GitNexus configuration and skills, committing and pushing each.

    Returns:
        0 when every repo is current (or was brought current and pushed), else 1.

    """
    src = _gitnexus_sources(cfg)
    repos = [r for r in _local_repos(cfg, args.repo, args.space) if not cfg.is_deprecated_name(r.name)]
    write = not args.check and not args.dry_run
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(lambda r: _gitnexus_sync_one(cfg, src, r, write), repos))
    if write:
        bad = [x for x in results if x["state"] != "current" and x["status"] != "pushed"]
    else:
        bad = [x for x in results if x["state"] != "current"]

    def text() -> str:
        lines = [f"{len(results)} repos, {len([x for x in results if x['state'] != 'current'])} not current"]
        for x in results:
            if x["state"] == "current":
                continue
            lines.append(f"  {x['repo']}: {x.get('status', 'would update')} {x.get('detail', '')}".rstrip())
        return "\n".join(lines)

    emit(args, {"repos": results, "not_current": len(bad)}, text)
    return 1 if bad else 0


# templates-check ------------------------------------------------------------------------------


def _read_yaml(f: Path) -> dict[str, object]:
    if not f.is_file():
        return {}
    try:
        d = YAML(typ="safe").load(f.read_text(encoding="utf-8"))
    except OSError, YAMLError:
        return {}
    return _map(d, str(f)) if isinstance(d, dict) else {}


def _template_for(
    r: LocalRepo,
    kinds: Mapping[str, object],
) -> tuple[str | None, str | None, dict[str, object]]:
    """Decide which template a repo was built from: Copier answers, then repo.status.yaml, then its name.

    Returns:
        (template, how it was decided, Copier answers).

    """
    answers = _read_yaml(r.path / ".copier-answers.yml")
    src = str(answers.get("_src_path") or "").rstrip("/")
    if src and Path(src).name in kinds:
        return Path(src).name, "copier-answers", answers
    stype = _read_yaml(r.path / "repo.status.yaml").get("service_type")
    for t, k in kinds.items():
        if stype and stype in _seq(_map(k or {}, "template kind").get("status_types") or [], "status_types"):
            return t, "repo.status.yaml", answers
    for t, k in kinds.items():
        if type_of(r.name) in _kind_types(k):
            return t, "name", answers
    return None, None, answers


def _template_files(tdir: Path, ignore: list[str]) -> dict[str, str]:
    """Map each file a template renders at a fixed path to its source in the template.

    Returns:
        rendered path → template source path.

    """
    out: dict[str, str] = {}
    for p in sorted(tdir.rglob("*")):
        if not p.is_file():
            continue
        src = p.relative_to(tdir).as_posix()
        if src == "copier.yml" or "_copier_conf" in src:
            continue
        rel = src.removesuffix(".jinja")
        if "{{" in rel or any(fnmatch.fnmatch(rel, g) for g in ignore):
            continue
        out[rel] = src
    return out


def _commit_time(repo: Path, rel: str) -> int | None:
    s = git_out(repo, "log", "-1", "--format=%ct", "--", rel)
    return int(s) if s else None


def _compare_to_template(
    cfg: Config,
    r: LocalRepo,
    tdir: Path,
    files: dict[str, str],
    answers: dict[str, object],
) -> TemplateComparison:
    """Render the template as this repo would have been rendered and compare file by file.

    Returns:
        The repo, its files' (state, repo commit time) by path, and the render error if any.

    """
    given = {k: str(v) for k, v in answers.items() if not k.startswith("_")}
    data = {**_template_data(cfg, r.name), **given}
    out: dict[str, tuple[str, int | None]] = {}
    with tempfile.TemporaryDirectory(prefix="polyrepo-tc-") as tmp:
        rendered = Path(tmp) / r.name
        cp = _copier_render(tdir, rendered, data)
        if cp.returncode != 0:
            return TemplateComparison(repo=r.name, files={}, error=_last_line(cp))
        for rel in files:
            t, mine = rendered / rel, r.path / rel
            if not t.is_file():
                continue
            if not mine.is_file():
                out[rel] = ("missing", None)
            elif t.read_bytes() == mine.read_bytes():
                out[rel] = ("same", None)
            else:
                out[rel] = ("differs", _commit_time(r.path, rel))
    return TemplateComparison(repo=r.name, files=out, error=None)


def _check_template(
    cfg: Config,
    tdir: Path,
    members: list[tuple[LocalRepo, str, dict[str, object]]],
    ignore: list[str],
) -> TemplateReport:
    files = _template_files(tdir, ignore)
    now = int(time.time())
    tdates = {rel: _commit_time(tdir, src) or now for rel, src in files.items()}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        compared = list(
            ex.map(
                lambda m: _compare_to_template(cfg, m[0], tdir, files, m[2]),
                members,
            ),
        )
    rows: list[TemplateFileRow] = []
    for rel in files:
        row = TemplateFileRow(file=rel, same=0, missing=[], repo_newer=[], template_newer=[])
        for c in compared:
            state, when = c.files.get(rel, (None, None))
            if state == "same":
                row["same"] += 1
            elif state == "missing":
                row["missing"].append(c.repo)
            elif state == "differs":
                if when and when > tdates[rel]:
                    row["repo_newer"].append(c.repo)
                else:
                    row["template_newer"].append(c.repo)
        if row["missing"] or row["repo_newer"] or row["template_newer"]:
            rows.append(row)
    return TemplateReport(
        template=tdir.name,
        repos=[TemplateMember(repo=m[0].name, matched_by=m[1]) for m in members],
        render_errors=[RenderError(repo=c.repo, error=c.error) for c in compared if c.error is not None],
        files=rows,
        lags=any(row["repo_newer"] for row in rows),
    )


def cmd_templates_check(args: argparse.Namespace, cfg: Config) -> int:
    """Compare each template with the repos built from it, and name repo kinds with no template.

    Returns:
        0 when no template lags and every repo kind has a template, else 1.

    Raises:
        PolyrepoError: when the templates folder is missing.

    """
    troot, tset = _templates(cfg)
    if not troot.is_dir():
        msg = f"templates folder {troot} not found"
        raise PolyrepoError(msg)
    kinds = {
        t: k
        for t, k in _map(tset.get("kinds") or {}, "templates kinds").items()
        if (troot / t / "copier.yml").is_file()
    }
    ignore = _strs(tset.get("ignore") or [], "templates ignore")
    by_template: dict[str, list[tuple[LocalRepo, str, dict[str, object]]]] = {t: [] for t in kinds}
    untemplated: dict[str, list[str]] = {}
    for r in _local_repos(cfg):
        if cfg.is_deprecated_name(r.name):
            continue
        t, how, answers = _template_for(r, kinds)
        if t is None:
            kind = r.name.rsplit("-", 1)[-1].lower() if "-" in r.name else r.name
            untemplated.setdefault(kind, []).append(r.name)
        else:
            by_template[t].append((r, str(how), answers))
    for d in sorted(troot.iterdir()):
        if d.is_dir() and (d / "copier.yml").is_file() and d.name not in kinds:
            by_template[d.name] = []
    results = [_check_template(cfg, troot / t, members, ignore) for t, members in sorted(by_template.items())]
    no_template = [KindWithoutTemplate(kind=k, repos=sorted(v)) for k, v in sorted(untemplated.items())]
    lagging: list[str] = [x["template"] for x in results if x["lags"]]
    data: dict[str, object] = {
        "templates": results,
        "kinds_without_template": no_template,
        "lagging_templates": lagging,
    }
    emit(args, data, lambda: _templates_text(results, no_template))
    return 1 if lagging or no_template else 0


def _templates_text(results: list[TemplateReport], no_template: list[KindWithoutTemplate]) -> str:
    """Render the templates-check report as text.

    Returns:
        One block per template, then the repo kinds with no template.

    """
    lines = []
    for x in results:
        how: dict[str, int] = {}
        for m in x["repos"]:
            how[m["matched_by"]] = how.get(m["matched_by"], 0) + 1
        lines.append(
            f"{x['template']}: {len(x['repos'])} repos ("
            + ", ".join(f"{v} by {k}" for k, v in sorted(how.items()))
            + f"){'  TEMPLATE LAGS' if x['lags'] else ''}",
        )
        lines.extend(_template_file_line(row) for row in x["files"])
        lines.extend(f"  render error {e['repo']}: {e['error']}" for e in x["render_errors"])
    lines.append("repo kinds with no template:")
    lines.extend(f"  {k['kind']}: {', '.join(k['repos'])}" for k in no_template)
    return "\n".join(lines)


def _template_file_line(row: TemplateFileRow) -> str:
    """Render one template file's comparison with its repos.

    Returns:
        The line.

    """
    bits = []
    if row["repo_newer"]:
        bits.append(
            f"newer in {len(row['repo_newer'])} repo(s) than the template",
        )
    if row["template_newer"]:
        bits.append(f"older in {len(row['template_newer'])} repo(s)")
    if row["missing"]:
        bits.append(f"missing from {len(row['missing'])} repo(s)")
    return f"  {row['file']}: same in {row['same']}; " + "; ".join(bits)


def fleet_findings(st: State) -> tuple[list[Finding], set[Path], list[Path]]:
    """Check the beads fleet list against the repos on disk.

    Every listed path must exist and be an active repo of the fleet; every active repo on
    disk with a `.beads` folder (other than the control repo itself) must be listed.

    Returns:
        The findings, the paths to remove and the paths to add.

    """
    cfg = st.cfg
    f = fleet_file(cfg)
    if not f.is_file():
        return [Finding("fleet-config-missing", "-", f"{f} not found")], set(), []
    control = os.path.normpath(f.parent.parent)
    lc = {os.path.normpath(r.path): (r.name, st.lifecycle(r.name)) for r in st.local.values()}
    active = {p: n for p, (n, life) in lc.items() if life not in LIFECYCLES_INACTIVE and p != control}
    listed = fleet_paths(cfg)
    out: list[Finding] = []
    remove: set[Path] = set()
    add: list[Path] = []
    for p, raw in sorted(listed.items()):
        if p in active:
            continue
        name, life = lc.get(p, (Path(p).name, None))
        if not Path(p).is_dir():
            detail = f"{raw} does not exist"
        elif life is None:
            detail = f"{raw} is not a repo of the fleet on disk"
        else:
            detail = f"{raw} is {life}"
        out.append(
            Finding(
                "fleet-path-missing" if not Path(p).is_dir() else "fleet-path-inactive",
                name,
                detail,
                fix=f"remove {raw} from repos.additional",
            ),
        )
        remove.add(Path(p))
    for p, name in sorted(active.items(), key=lambda kv: kv[1].lower()):
        if p not in listed and (Path(p) / ".beads").is_dir():
            out.append(
                Finding(
                    "fleet-repo-unlisted",
                    name,
                    f"active repo with a .beads folder, not in repos.additional ({p})",
                    fix=f"add {os.path.relpath(p, control)}/ to repos.additional",
                ),
            )
            add.append(Path(p))
    return out, remove, add


def cmd_beads_fleet(args: argparse.Namespace, cfg: Config) -> int:
    """Check the beads fleet list (`repos.additional`); with --fix, correct it.

    Returns:
        0 when the list is correct (or was corrected), else 1.

    """
    st = gather(cfg, fetch=False, use_cache=not args.no_cache)
    findings, remove, add = fleet_findings(st)
    changes: list[str] = []
    if args.fix and (remove or add):
        try:
            changes = fleet_edit(cfg, remove=remove, add=add)
            for f in findings:
                f.status = "fixed" if f.fix else f.status
        except (OSError, PolyrepoError) as exc:
            for f in findings:
                f.status, f.error = ("failed", str(exc)) if f.fix else (f.status, None)
        if changes:
            note_change(
                cfg,
                "polyrepo beads-fleet --fix",
                [f"beads fleet list (repos.additional): {c}" for c in changes],
            )
    data: dict[str, object] = {
        "file": str(fleet_file(cfg)),
        "listed": len(fleet_paths(cfg)),
        "findings": [f.as_dict() for f in findings],
        "changes": changes,
        "open": sum(f.status in {"open", "failed"} for f in findings),
        "fixed": sum(f.status == "fixed" for f in findings),
    }
    finish_records(cfg, data)

    def text() -> str:
        lines = [
            f"{data['listed']} listed in {data['file']}, {len(findings)} findings ({data['fixed']} fixed)",
        ]
        lines.extend(f"  [{f.kind}] {f.repo}: {f.detail} ({f.status})" for f in findings)
        return "\n".join([*lines, *_records_line(data)])

    emit(args, data, text)
    return 1 if data["open"] else 0


def deprecated_open_prs(cfg: Config) -> list[PullRequest]:
    """Find every open pull request in a deprecated- repo of the owner on GitHub.

    Returns:
        One {repo, number, title, url} per open pull request.

    Raises:
        PolyrepoError: when gh cannot search.

    """
    cp = run(
        [
            "gh", "search", "prs", "--owner", cfg.owner, "--state", "open",
            "--limit", "1000", "--json", "repository,number,title,url",
        ],
        timeout=120,
    )  # fmt: skip
    if cp.returncode != 0:
        msg = f"gh search prs failed: {_last_line(cp)}"
        raise PolyrepoError(msg)
    parsed: object = json.loads(cp.stdout or "[]")
    prs: list[PullRequest] = []
    for item in _seq(parsed, "gh search prs output"):
        repo = _str(
            _map(_map(item, "gh search prs entry").get("repository"), "gh search prs repository").get("name"),
            "repository name",
        )
        if cfg.is_deprecated_name(repo):
            prs.append(parse_pull_request(item, repo, "gh search prs"))
    return prs


def cmd_deprecated_prs(args: argparse.Namespace, cfg: Config) -> int:
    """Check for open pull requests in deprecated- repos; with --fix, close them.

    Returns:
        0 when none is open (or every one was closed), else 1.

    """
    prs = deprecated_open_prs(cfg)
    findings = [
        Finding(
            "deprecated-repo-open-pr",
            pr.repo,
            f"#{pr.number} {pr.title} ({pr.url}) is open in a deprecated repo",
            fix=f"close #{pr.number} with the comment {DEPRECATED_PR_COMMENT!r}",
        )
        for pr in prs
    ]
    if args.fix:
        for pr, f in zip(prs, findings, strict=True):
            err = close_pr(cfg, pr.repo, pr.number)
            f.status, f.error = ("failed", err) if err else ("fixed", None)
    data: dict[str, object] = {
        "findings": [f.as_dict() for f in findings],
        "open": sum(f.status in {"open", "failed"} for f in findings),
        "fixed": sum(f.status == "fixed" for f in findings),
    }

    def text() -> str:
        lines = [
            f"{len(findings)} open pull requests in deprecated repos ({data['fixed']} closed)",
        ]
        lines.extend(
            f"  [{f.kind}] {f.repo}: {f.detail} ({f.status})" + (f": {f.error}" if f.error else "") for f in findings
        )
        return "\n".join(lines)

    emit(args, data, text)
    return 1 if data["open"] else 0


# archive-due ----------------------------------------------------------------------------------

ARCHIVE_FINDING_STATUS = {"kept": "open", "undated": "open", "failed": "failed", "planned": "planned"}


def _archive_blockers(st: State, name: str) -> list[str]:
    """Find what keeps a deprecated repo from being archived: a matrix stack in it, or an open pull request.

    Archiving makes a repo read-only, so an open pull request could no longer be closed or merged.

    Returns:
        The reasons, empty when the repo may be archived.

    """
    reasons: list[str] = []
    held = [s.id for s in st.matrix_stacks() if s.repository == name]
    if held:
        reasons.append(
            f"the matrix still has stacks in it: {', '.join(held)}; move each (put stack --repository) "
            "or remove it (remove stack:<id> --held)",
        )
    try:
        prs = open_prs(st.cfg, name)
    except (GitFailedError, PolyrepoError, json.JSONDecodeError) as exc:
        reasons.append(f"could not list open pull requests: {exc}")
    else:
        reasons.extend(f"open pull request #{pr.number} {pr.title} ({pr.url})" for pr in prs)
    return reasons


def _retire_clone(st: State, name: str, dry_run: bool, row: dict[str, object]) -> list[str]:
    """Drop an archived repo's clone from the beads fleet list, and delete it when no work exists only there.

    Records the clone's outcome in row["clone"] (absent when there is no clone).

    Returns:
        The lines for the commit message, one per change.

    """
    r = st.local.get(name)
    if r is None:
        return []
    lines: list[str] = []
    if not dry_run:
        lines.extend(fleet_edit(st.cfg, remove=[r.path]))
    deleted, steps = delete_clone(st.cfg, r.path, r.path, dry_run, row)
    if deleted and not dry_run:
        lines.extend(steps)
    return lines


def _archive_one(st: State, name: str, dry_run: bool, row: dict[str, object]) -> list[str]:
    """Archive one deprecated repo that is due: on GitHub, then its manifest lifecycle, then its local clone.

    A repo GitHub already shows archived is not archived again. A repo with a blocker
    (`_archive_blockers`) is kept and left deprecated.

    Returns:
        The lines for the commit message, one per change.

    """
    cfg = st.cfg
    g = st.gh.get(name)
    on_github = g is not None and g["archived"]
    if not on_github and (reasons := _archive_blockers(st, name)):
        row.update(status="kept", detail="; ".join(reasons))
        return []
    if dry_run:
        row["status"] = "planned"
        _retire_clone(st, name, dry_run, row)
        return []
    if not on_github:
        try:
            must(run(["gh", "repo", "archive", f"{cfg.owner}/{name}", "--yes"], timeout=120))
        except GitFailedError as exc:
            row.update(status="failed", detail=f"gh repo archive failed: {exc}")
            return []
    st.manifest.set_field(name, "lifecycle", "archived")
    row["status"] = "archived"
    lines = [
        f"{name}: "
        + ("GitHub already shows it archived" if on_github else f"archived {cfg.owner}/{name} on GitHub")
        + f" ({row['detail']}); lifecycle archived",
    ]
    return lines + _retire_clone(st, name, dry_run, row)


def _archive_row(st: State, name: str, e: CommentedMap, days: int) -> tuple[dict[str, object], bool]:
    """Classify one deprecated manifest entry for archive-due.

    Returns:
        The repo's row (status `missing`, `undated`, `not-due` or `due`, with detail) and
        whether it is due for archiving.

    """
    row: dict[str, object] = {"repo": name, "deprecated_on": None}
    if st.gh.get(name) is None:
        row.update(status="missing", detail="not on GitHub; reconcile removes the record of a deleted repo")
        return row, False
    start = _deprecation_start(e)
    if start is None:
        row.update(status="undated", detail="no valid deprecated_on date; record it from the manifest's git history")
        return row, False
    due = start + dt.timedelta(days=days)
    age = (dt.date.fromisoformat(today()) - start).days
    row.update(deprecated_on=start.isoformat(), due_on=due.isoformat())
    if age < days:
        row.update(status="not-due", detail=f"deprecated {age} days ago; due {due}")
        return row, False
    row.update(status="due", detail=f"deprecated {start}, {age} days ago")
    return row, True


def archive_due(st: State, dry_run: bool) -> tuple[list[dict[str, object]], list[str]]:
    """Archive every deprecated repo deprecated at least `deprecation.archive_after_days` (config) days ago.

    An entry the manifest already records archived only has its local clone retired, so a run
    after a clone that was kept is cleaned retries it, and a second run changes nothing.

    Returns:
        One row per deprecated or archived entry, and the lines for the commit message, one per change.

    """
    days = st.cfg.archive_after_days()
    rows: list[dict[str, object]] = []
    lines: list[str] = []
    for name, e in sorted(st.manifest.entries().items(), key=lambda kv: kv[0].lower()):
        lc = e.get("lifecycle")
        if lc == "archived":
            if name in st.local:
                row: dict[str, object] = {"repo": name, "status": "archived", "detail": "already archived"}
                lines.extend(_retire_clone(st, name, dry_run, row))
                rows.append(row)
            continue
        if lc != "deprecated":
            continue
        row, due = _archive_row(st, name, e, days)
        if due:
            lines.extend(_archive_one(st, name, dry_run, row))
        rows.append(row)
    return rows, lines


def _archive_findings(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Turn archive-due rows into findings: a repo kept, undated, failed or planned, and a clone kept.

    Returns:
        The findings, in the shape `Finding.as_dict` gives.

    """
    out: list[dict[str, object]] = []
    for row in rows:
        status = str(row["status"])
        if status in ARCHIVE_FINDING_STATUS:
            out.append(
                {"kind": f"archive-{status}", "repo": row["repo"], "detail": row["detail"],
                 "mechanical": status == "planned", "fix": None, "status": ARCHIVE_FINDING_STATUS[status],
                 "error": None},
            )  # fmt: skip
        clone = row.get("clone")
        if isinstance(clone, dict) and clone.get("status") in {"refused", "failed"}:
            why = clone.get("reasons") or [clone.get("error")]
            out.append(
                {"kind": "archived-clone-kept", "repo": row["repo"],
                 "detail": f"local clone {clone.get('path')} kept: " + "; ".join(str(x) for x in _seq(why, "reasons")),
                 "mechanical": False, "fix": None, "status": "open", "error": None},
            )  # fmt: skip
    return out


def cmd_archive_due(args: argparse.Namespace, cfg: Config) -> int:
    """Archive every deprecated repo whose deprecation is old enough, keeping its manifest record.

    For each due repo: refuse while a matrix stack is in it or a pull request is open (reported,
    left deprecated), `gh repo archive --yes`, set its lifecycle to archived, drop it from the
    beads fleet list, and delete its local clone unless work exists only there (uncommitted or
    untracked files, a stash, commits on no remote branch, or such work in a linked worktree),
    in which case the clone is kept and reported. Idempotent. Never deletes a repo on GitHub.

    Returns:
        0 when nothing is left kept, undated or failed, else 1.

    """
    st = gather(cfg, fetch=False, use_cache=not args.no_cache)
    rows, lines = archive_due(st, args.dry_run)
    if not args.dry_run:
        st.manifest.save()
        if lines:
            st.gh.invalidate()
            note_change(cfg, "polyrepo archive-due", lines)
    findings = _archive_findings(rows)
    data: dict[str, object] = {
        "archive_after_days": cfg.archive_after_days(),
        "dry_run": args.dry_run,
        "repos": rows,
        "findings": findings,
        "fixed": sum(r["status"] == "archived" for r in rows),
        "open": sum(f["status"] in {"open", "failed"} for f in findings),
    }
    if not args.dry_run:
        finish_records(cfg, data)

    def text() -> str:
        out = [
            f"archive-due ({data['archive_after_days']} days after deprecation)"
            + (" — dry run" if args.dry_run else ""),
        ]
        for r in rows:
            clone = r.get("clone")
            tail = f"; clone {clone.get('status')}" if isinstance(clone, dict) else ""
            out.append(f"  [{r['status']}] {r['repo']}: {r['detail']}{tail}")
        records = data.get("records")
        if isinstance(records, dict):
            out.append(f"records {records.get('status')}" + (f": {records['error']}" if records.get("error") else ""))
        return "\n".join(out)

    emit(args, data, text)
    return 1 if data["open"] else 0


PYTHON_NAMES_DETAIL = 300
PYTHON_NAMES_TEXT = 110


def _name_checker(cfg: Config) -> Checker:
    """Build the function that runs `atw-naming check`.

    Returns:
        A function from the check's arguments (type, name, `--repository`, repository) to
        (whether the name passed, the check's message).

    """
    env: dict[str, str | None] = {}
    if not os.environ.get(CONTROL_REPO_ENV):
        env[CONTROL_REPO_ENV] = str(cfg.file.parent.parent)

    def check(args: Sequence[str]) -> tuple[bool, str]:
        cp = run([str(NAMING_COMMAND), "check", *args], timeout=NAMING_TIMEOUT, env=env)
        text = " ".join(line.strip() for line in (cp.stdout + cp.stderr).strip().splitlines())
        return cp.returncode == 0, text[:PYTHON_NAMES_DETAIL]

    return check


def python_names_findings(st: State, only: list[str] | None = None) -> list[Finding]:
    """Check every active Python repo's names and layout against the naming standard.

    For each repository that has a `pyproject.toml` (the control repo is left out) the three
    `atw-naming check` commands run against what it has: the `name` in `pyproject.toml`, the
    source package and its folder under `src`. `src` and `tests` must exist and no `__init__.py`
    may sit in an app or team folder. The check is deterministic: nothing is judged.

    Returns:
        One finding per failed check or missing part.

    """
    cfg = st.cfg
    control = os.path.normpath(fleet_file(cfg).parent.parent)
    check = _name_checker(cfg)
    todo = [
        r
        for name, r in sorted(st.local.items(), key=lambda kv: kv[0].lower())
        if (only is None or name in only)
        and st.lifecycle(name) not in LIFECYCLES_INACTIVE
        and os.path.normpath(r.path) != control
        and (r.path / "pyproject.toml").is_file()
    ]

    def one(r: LocalRepo) -> list[Finding]:
        try:
            facts = read_facts(_sweep_git, r.path)
        except NameSweepError as exc:
            return [Finding("python-names", r.name, str(exc))]
        return [
            Finding(p.check if p.check.startswith("python-") else f"python-{p.check}", r.name, p.detail)
            for p in python_problems(facts, r.name, check)
        ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        return [f for found in ex.map(one, todo) for f in found]


def cmd_python_names(args: argparse.Namespace, cfg: Config) -> int:
    """Report every repo whose Python names or layout differ from what `atw-naming` gives.

    Returns:
        0 when every repo conforms, else 1.

    """
    st = gather(cfg, fetch=False, use_cache=not args.no_cache)
    only = scope_names(st, args.repos, args.space)
    findings = python_names_findings(st, only)
    data: dict[str, object] = {
        "findings": [f.as_dict() for f in findings],
        "repos": sorted({f.repo for f in findings}),
        "open": len(findings),
    }
    emit(
        args,
        data,
        lambda: "\n".join(
            [f"{len(findings)} finding(s) in {len(_seq(data['repos'], 'repos'))} repo(s)"]
            + [f"  [{f.kind}] {f.repo}: {f.detail[:PYTHON_NAMES_TEXT]}" for f in findings],
        ),
    )
    return 1 if findings else 0


BEADS_AUDIT = PLUGIN_ROOT / "skills" / "polyrepo-beads" / "scripts" / "audit-fleet.sh"
SELF = Path(__file__).resolve()
DOCTOR_CHECKS: dict[str, list[str]] = {
    "reconcile": [sys.executable, str(SELF), "reconcile", "--json"],
    "agents-sync": [sys.executable, str(SELF), "agents-sync", "--check", "--json"],
    "gitnexus-sync": [sys.executable, str(SELF), "gitnexus-sync", "--check", "--json"],
    "beads": ["bash", str(BEADS_AUDIT), "--json"],
    "beads-setup": [sys.executable, str(SELF), "beads-setup", "--check", "--json"],
    "beads-fleet": [sys.executable, str(SELF), "beads-fleet", "--json"],
    "environment": [sys.executable, str(SELF), "environment", "--json"],
    "python-names": [sys.executable, str(SELF), "python-names", "--json"],
    "tiers": [sys.executable, str(SELF), "tiers", "--json"],
    "deprecated-prs": [sys.executable, str(SELF), "deprecated-prs", "--json"],
    "archive-due": [sys.executable, str(SELF), "archive-due", "--dry-run", "--json"],
}
DOCTOR_REPAIRS: dict[str, list[str]] = {
    "reconcile --fix": [sys.executable, str(SELF), "reconcile", "--fix", "--json"],
    "tiers --write": [sys.executable, str(SELF), "tiers", "--write", "--json"],
    "agents-sync": [sys.executable, str(SELF), "agents-sync", "--json"],
    "gitnexus-sync": [sys.executable, str(SELF), "gitnexus-sync", "--json"],
    "beads-setup --all": [sys.executable, str(SELF), "beads-setup", "--all", "--json"],
    "beads-fleet --fix": [sys.executable, str(SELF), "beads-fleet", "--fix", "--json"],
    "deprecated-prs --fix": [
        sys.executable, str(SELF), "deprecated-prs", "--fix", "--json",
    ],
    "archive-due": [sys.executable, str(SELF), "archive-due", "--json"],
}  # fmt: skip


def _finding(check: str, subject: str, kind: str, detail: str) -> DoctorFinding:
    return DoctorFinding(check=check, subject=subject, kind=kind, detail=detail)


def _run_json(argv: list[str], extra: list[str]) -> tuple[int, dict[str, object]]:
    """Run one of the tool's own checks or repairs as a separate process and read its JSON.

    Returns:
        (exit status, parsed output); unreadable output becomes {"error": ...}.

    """
    cp = run([*argv, *extra], timeout=900)
    data: dict[str, object]
    try:
        parsed: object = json.loads(cp.stdout) if cp.stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = None
        data = {"error": f"unreadable output: {cp.stdout[:200]}"}
    else:
        data = (
            _map(parsed, "check output")
            if isinstance(parsed, dict)
            else {"error": f"unexpected output: {cp.stdout[:200]}"}
        )
    if cp.returncode == EXIT_USAGE and "error" not in data:
        data["error"] = _last_line(cp) or "exited 2"
    return cp.returncode, data


def _doctor_findings(check: str, data: dict[str, object]) -> list[DoctorFinding]:
    """Turn one check's JSON output into doctor findings.

    Returns:
        One finding per open problem the check reported.

    """
    if "error" in data:
        return [_finding(check, "-", "error", str(data["error"]))]
    if check in {
        "reconcile",
        "archive-due",
        "beads-fleet",
        "beads-setup",
        "deprecated-prs",
        "environment",
        "python-names",
        "tiers",
    }:
        rows = [_map(f, "finding") for f in _seq(data.get("findings") or [], "findings")]
        return [
            _finding(check, str(f["repo"]), str(f["kind"]), str(f["detail"]))
            for f in rows
            if f.get("status") in {"open", "failed", "planned"}
        ]
    if check == "gitnexus-sync":
        return [
            _finding(
                check,
                str(r["repo"]),
                str(r["state"]),
                "GitNexus files out of date: " + ", ".join(_strs(r.get("files") or [], "files")),
            )
            for r in (_map(x, "gitnexus-sync repo") for x in _seq(data.get("repos") or [], "repos"))
            if r.get("state") != "current"
        ]
    if check == "agents-sync":
        return [
            _finding(
                check,
                str(r["repo"]),
                str(r["state"]),
                str(r.get("detail") or "shared AGENTS.md block not current"),
            )
            for r in (_map(x, "agents-sync repo") for x in _seq(data.get("repos") or [], "repos"))
            if r.get("state") != "current"
        ]
    if check == "beads":
        return [
            _finding(check, str(a["repo"]), "beads-anomaly", str(a["detail"]))
            for a in (_map(x, "beads anomaly") for x in _seq(data.get("anomalies") or [], "anomalies"))
        ]
    return []


def _resolve_location(cfg: Config, loc: str) -> Path:
    target = Path(expand_env(loc)).expanduser()
    return target if target.is_absolute() else cfg.file.parent.parent / target


def _governance_findings(cfg: Config) -> list[DoctorFinding]:
    """Check every governance entry's location and invoke command.

    Its location must exist, and a script or tool's `invoke` must run (the part before its
    first `<placeholder>`, with `--help`).

    Returns:
        One finding per entry that does not resolve or does not run.

    """
    out = []
    doc: object = YAML(typ="safe").load(cfg.manifest.read_text(encoding="utf-8")) if cfg.manifest.exists() else {}
    for e in (doc if isinstance(doc, dict) else {}).get("governance") or []:
        if not isinstance(e, dict):
            continue
        subject = str(e.get("id") or e.get("name"))
        loc = e.get("location")
        if loc and not _resolve_location(cfg, str(loc)).exists():
            out.append(
                _finding(
                    "governance",
                    subject,
                    "location-missing",
                    f"{loc} does not resolve ({_resolve_location(cfg, str(loc))})",
                ),
            )
        if str(e.get("type")) not in {"script", "tool"}:
            continue
        invoke = str(e.get("invoke") or "").split("<", 1)[0].strip()
        if not invoke:
            out.append(
                _finding("governance", subject, "invoke-missing", "no invoke command"),
            )
            continue
        try:
            argv = [*shlex.split(expand_env(invoke)), "--help"]
        except ValueError as exc:
            out.append(_finding("governance", subject, "invoke-fails", str(exc)))
            continue
        cp = run(argv, timeout=120)
        if cp.returncode != 0:
            out.append(
                _finding(
                    "governance",
                    subject,
                    "invoke-fails",
                    f"`{shlex.join(argv)}` exited {cp.returncode}: {_last_line(cp)}",
                ),
            )
    return out


def _knowledge_findings(cfg: Config) -> list[DoctorFinding]:
    """Check that every location or pointer in the knowledge store resolves.

    A `location` or `pointer` entry names what it points at in `resolves` (one path or a
    list; environment variables are expanded); each must exist.

    Returns:
        One finding per entry with no `resolves`, and per path that does not exist.

    """
    doc = YAML(typ="safe").load(cfg.knowledge.read_text()) if cfg.knowledge.exists() else {}
    out = []
    for e in (doc or {}).get("knowledge") or []:
        if not isinstance(e, dict) or e.get("kind") not in {"location", "pointer"}:
            continue
        subject = str(e.get("id"))
        targets = e.get("resolves")
        if not targets:
            out.append(
                _finding(
                    "knowledge",
                    subject,
                    "pointer-unchecked",
                    "no `resolves` path, so the pointer cannot be checked",
                ),
            )
            continue
        for t in targets if isinstance(targets, list) else [targets]:
            p = _resolve_location(cfg, str(t))
            if not p.exists():
                out.append(
                    _finding(
                        "knowledge",
                        subject,
                        "pointer-missing",
                        f"{t} ({p}) does not exist",
                    ),
                )
    return out


def _naming_doc_findings(cfg: Config) -> list[DoctorFinding]:
    """Check that the vault's repository naming note is readable and states every rule the tool needs.

    The tool keeps no copy of the note's rules: every command reads them from the note
    (`naming.document` under `naming.document_root`), so there is nothing to compare. This check
    reads the note the way every command does.

    Returns:
        One finding when the note is missing, unreadable, or does not state a rule; else none.

    """
    try:
        _ = cfg.rules
    except PolyrepoError as exc:
        return [_finding("naming-doc", "-", "unreadable", str(exc))]
    return []


def _template_type_findings(cfg: Config) -> list[DoctorFinding]:
    """Check that every repository type the config maps to a template is a type the naming note lists.

    The config's `templates.kinds[].types` is the steward's own map from repository types to the
    template that builds them; the types themselves are the naming note's. A listed type the note
    no longer has is a stale copy.

    Returns:
        One finding per kind and type the naming note does not list.

    """
    try:
        known = set(cfg.rules.types)
    except PolyrepoError:
        return []
    kinds = _map(_templates(cfg)[1].get("kinds") or {}, "templates kinds")
    return [
        _finding(
            "templates",
            kind,
            "type-unknown",
            f"template kind {kind} lists the type {t}, which the naming note does not",
        )
        for kind, spec in kinds.items()
        for t in _kind_types(spec)
        if t not in known
    ]


ORGANIZATION_RECORD = "organization-structure.md"
ORGANIZATION_VARIABLE = re.compile(r"^- (SKILLSPOKE_[A-Z_]+):.*?set as \"?([^\"\s]+)\"?")


def _organization_findings(cfg: Config) -> list[DoctorFinding]:
    """Check each environment variable value the steward's organization record states against the environment.

    The record `organization-structure.md` is the owner's text and the steward's own record. The
    values it states for the `SKILLSPOKE_*` variables are a copy of the shell environment, whose
    values are the live ones; each stated value, with its variables expanded, must equal the
    variable's value.

    Returns:
        One finding per variable the record states that is unset or has another value.

    """
    record = cfg.file.parent / ORGANIZATION_RECORD
    if not record.is_file():
        return [_finding("organization", ORGANIZATION_RECORD, "missing", f"{record} does not exist")]
    out: list[DoctorFinding] = []
    for line in record.read_text(encoding="utf-8").splitlines():
        m = ORGANIZATION_VARIABLE.match(line)
        if m is None:
            continue
        name, stated = m.group(1), os.path.expandvars(m.group(2))
        live = os.environ.get(name)
        if live is None:
            out.append(
                _finding(
                    "organization",
                    name,
                    "unset",
                    f"{ORGANIZATION_RECORD} states {name}, which the environment does not set",
                ),
            )
        elif Path(live) != Path(stated):
            out.append(
                _finding(
                    "organization",
                    name,
                    "differs",
                    f"{ORGANIZATION_RECORD} states {stated}, the environment has {live}",
                ),
            )
    return out


def _matrix_findings(st: State) -> list[Finding]:
    """Check the matrix's stacks against the repositories (S6), with the repair for each.

    The findings are an active code repository (its name ends in a listed stack type, and it is
    not in a space the matrix leaves alone) that no stack names as its repository; a stack whose
    repository is deprecated or archived, or exists nowhere; and a matrix that
    `atw-matrix check` finds invalid. A stack whose repository exists nowhere may belong to a
    repository elaboration has yet to create, so it is reported and not repaired.

    Returns:
        The findings; each repairable one carries the `atw-matrix` call that corrects it.

    """
    cfg = st.cfg
    known = st.matrix_stacks()
    types = stack_types(cfg)
    named = {s.repository for s in known if s.repository}
    out: list[Finding] = []
    for name in st.tracked_names():
        r = st.local.get(name)
        if name in named or st.lifecycle(name) in LIFECYCLES_INACTIVE or (r is None and st.gh.get(name) is None):
            continue
        space = r.space if r else cfg.expected_space(name)
        if not holds_stack(name, types):
            continue
        out.append(
            Finding(
                "stack-missing",
                name,
                f"{name} holds code, but no stack in the matrix names it as its repository",
                fix=f"record stack:{name} on the repository side, purpose not stated",
                action=functools.partial(record_stack, cfg, name, space, known),
            ),
        )
    for s in known:
        if s.repository is None:
            continue
        out.extend(_stack_repository_findings(st, s))
        out.extend(_stack_command_findings(st, s))
    checked = matrix_run(cfg, ["check"])
    if checked.get("valid") is not True:
        problems = _strs(checked.get("problems") or [], "the matrix's problems")
        shown = "; ".join(problems[:CHECK_PROBLEMS_SHOWN])
        out.append(
            Finding("matrix-invalid", "matrix", f"atw-matrix check reports {len(problems)} problem(s): {shown}"),
        )
    return out


TASK_COMMAND = re.compile(r"^task (\S+)")
NPM_COMMAND = re.compile(r"^npm (?:run )?(\S+)")


def _declared_tasks(path: Path) -> set[str] | None:
    """List the tasks a repository's Taskfile declares.

    Returns:
        The task names, or None when `task` is not installed or the repository has no readable Taskfile.

    """
    if shutil.which("task") is None:
        return None
    cp = run(["task", "--list-all", "--json"], cwd=path, timeout=60)
    if cp.returncode != 0:
        return None
    tasks = _seq(_map(json.loads(cp.stdout), "the task list").get("tasks") or [], "the task list's tasks")
    return {_str(_map(t, "a task").get("name"), "a task's name") for t in tasks}


def _declared_scripts(path: Path) -> set[str]:
    """List the scripts a repository's package.json declares.

    Returns:
        The script names; none when there is no package.json.

    """
    package = path / "package.json"
    if not package.is_file():
        return set()
    return set(
        _map(_map(json.loads(package.read_text(encoding="utf-8")), "package.json").get("scripts") or {}, "scripts"),
    )


def _stack_command_findings(st: State, s: MatrixStack) -> list[Finding]:
    """Check that each command a stack records is still declared by the repository it names.

    A stack's `commands` are a copy of what the repository declares (its Taskfile tasks or its
    package.json scripts), kept in the matrix so that nobody has to open the repository. The
    copy stays true only if each command resolves, so a `task X` command needs the task X and an
    `npm test` or `npm run X` command needs the script.

    Returns:
        One finding per command the repository no longer declares; the refresh is `put stack
        --commands-<test|publish|deploy>` with what the repository declares now.

    """
    r = st.local.get(str(s.repository))
    if r is None or not s.commands:
        return []
    tasks = _declared_tasks(r.path)
    scripts = _declared_scripts(r.path)
    out: list[Finding] = []
    for key, command in s.commands.items():
        task, script = TASK_COMMAND.match(command), NPM_COMMAND.match(command)
        stale = (task is not None and tasks is not None and task.group(1) not in tasks) or (
            script is not None and script.group(1) not in scripts
        )
        if stale:
            out.append(
                Finding(
                    "stack-command-stale",
                    str(s.repository),
                    f"{s.id} records {key} as `{command}`, which {s.repository} no longer declares",
                ),
            )
    return out


def _stack_repository_findings(st: State, s: MatrixStack) -> list[Finding]:
    """Check that the repository one stack names is an active repository.

    Returns:
        No finding for an active repository. For a deprecated or archived one, the repair that
        removes a hint stack holding nothing or else unsets the repository; for one that exists
        nowhere, a finding with no repair.

    """
    cfg, repo = st.cfg, str(s.repository)
    state = st.live_state(repo)
    if state == "active":
        return []
    put = ["put", "stack", "--side", "repository", "--id", s.id]
    if state == "missing":
        return [
            Finding(
                "stack-repository-missing",
                repo,
                f"{s.id} names {repo} as its repository, which exists on neither disk nor GitHub",
            ),
        ]
    drop = s.side == "repository" and s.holds == 0
    return [
        Finding(
            "stack-repository-inactive",
            repo,
            f"{s.id} names {repo}, which is deprecated or archived",
            fix=f"remove {s.id}, a hint that holds nothing" if drop else f"unset the repository of {s.id}",
            action=functools.partial(matrix_run, cfg, ["remove", s.id] if drop else [*put, "--unset", "repository"]),
        ),
    ]


def _matrix_doctor(cfg: Config, fix: bool, no_cache: bool) -> tuple[int, list[DoctorFinding]]:
    """Run the matrix check of the doctor, and with fix repair what it can and commit the matrix.

    Returns:
        (the number of findings repaired, the findings still open). A matrix that cannot be
        read or committed is one `error` finding.

    """
    try:
        findings = _matrix_findings(gather(cfg, fetch=False, use_cache=not no_cache))
        fixed = _repair_matrix_findings(findings) if fix else 0
        if fixed:
            matrix_commit(cfg)
    except PolyrepoError as exc:
        return 0, [_finding("matrix", "-", "error", str(exc))]
    return fixed, [
        _finding("matrix", f.repo, f.kind, f.detail + (f" ({f.error})" if f.error else ""))
        for f in findings
        if f.status != "fixed"
    ]


def _repair_matrix_findings(findings: list[Finding]) -> int:
    """Run the repair of each matrix finding that has one, marking it fixed or failed.

    Returns:
        The number repaired.

    """
    for f in findings:
        if f.action is None:
            continue
        try:
            f.action()
            f.status = "fixed"
        except (GitFailedError, PolyrepoError) as exc:
            f.status, f.error = "failed", str(exc)
    return sum(f.status == "fixed" for f in findings)


def cmd_doctor(args: argparse.Namespace, cfg: Config) -> int:
    """Run every deterministic health check and report one findings list.

    With --fix, first run the repairs (`reconcile --fix`, `agents-sync`, `beads-fleet
    --fix`, `deprecated-prs --fix`, then `archive-due`), each of which commits and pushes its
    own changes, closes the pull requests it finds or archives the deprecated repos that are
    due. The checks are reconcile, agents-sync --check, the beads fleet audit, the beads fleet
    list, open pull requests in deprecated repos and `archive-due --dry-run` (in
    parallel, each its own process), the governance
    entries, the knowledge-store pointers, the repository-naming document, the template types
    against the naming note's types, the organization record's environment variables against
    the environment, and the matrix's stacks against the repositories (repaired under --fix,
    and the matrix committed).

    Returns:
        0 when no check reports a finding, else 1.

    """
    t0 = time.time()
    extra = ["--config", str(cfg.file)] + (["--no-cache"] if args.no_cache else [])
    repairs: dict[str, dict[str, object]] = {}
    if args.fix:
        for name, argv in DOCTOR_REPAIRS.items():
            rc, data = _run_json(argv, extra)
            repairs[name] = {
                "exit": rc,
                "fixed": data.get("fixed"),
                "records": data.get("records"),
                "error": data.get("error"),
            }

    def one(item: tuple[str, list[str]]) -> tuple[str, int, dict[str, object]]:
        name, argv = item
        return (name, *_run_json(argv, [] if name == "beads" else extra))

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(DOCTOR_CHECKS)) as ex:
        results = list(ex.map(one, DOCTOR_CHECKS.items()))
    findings: list[DoctorFinding] = []
    exits: dict[str, int] = {}
    for name, rc, data in results:
        exits[name] = rc
        findings.extend(_doctor_findings(name, data))
    findings.extend(_governance_findings(cfg))
    findings.extend(_knowledge_findings(cfg))
    findings.extend(_naming_doc_findings(cfg))
    findings.extend(_template_type_findings(cfg))
    findings.extend(_organization_findings(cfg))
    matrix_fixed, matrix_open = _matrix_doctor(cfg, args.fix, args.no_cache)
    findings.extend(matrix_open)
    if args.fix:
        repairs["matrix"] = {"exit": 0, "fixed": matrix_fixed, "records": None, "error": None}
    counts: dict[str, int] = dict.fromkeys(
        [*DOCTOR_CHECKS, "governance", "knowledge", "naming-doc", "templates", "organization", "matrix"],
        0,
    )
    for f in findings:
        counts[f["check"]] = counts.get(f["check"], 0) + 1
    report: dict[str, object] = {
        "naming_note": cfg.rules.summary() if not any(f["check"] == "naming-doc" for f in findings) else None,
        "repairs": repairs,
        "findings": findings,
        "counts": counts,
        "exit_codes": exits,
        "open": len(findings),
        "elapsed_s": round(time.time() - t0, 1),
    }

    def text() -> str:
        lines = [f"{len(findings)} findings in {report['elapsed_s']}s", f"  naming rules read from {cfg.naming_note()}"]
        lines.extend(
            f"  repair {n}: exit {r['exit']}"
            + (f", {r['fixed']} fixed" if r.get("fixed") is not None else "")
            + (f", {r['error']}" if r.get("error") else "")
            for n, r in repairs.items()
        )
        lines.extend(f"  {c}: {n}" for c, n in counts.items())
        lines.extend(f"  [{f['check']}/{f['kind']}] {f['subject']}: {f['detail']}" for f in findings)
        return "\n".join(lines)

    emit(args, report, text)
    return 1 if findings else 0


def cmd_commit(args: argparse.Namespace, cfg: Config) -> int:
    """Commit and push the steward's own files after a hand edit.

    Returns:
        0 when they are committed and pushed or already clean, else 1.

    """
    res = commit_records(cfg, args.message.strip())
    emit(
        args,
        res,
        lambda: (
            f"steward files {res['status']}"
            + (f": {', '.join(_strs(res['files'], 'files'))}" if res["files"] else "")
            + (f"; {res['error']}" if res.get("error") else "")
        ),
    )
    return 0 if res["status"] in {"clean", "pushed"} else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        The parser.

    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print one JSON object")
    common.add_argument("--config", help="path to .polyrepo/config.yaml")
    common.add_argument(
        "--no-cache",
        action="store_true",
        help="fetch and list GitHub even when fresh",
    )

    p = argparse.ArgumentParser(
        prog="polyrepo",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=[common], help=help_text)

    _add_inspect_commands(add)
    _add_repo_commands(add)
    _add_upkeep_commands(add)
    _add_tier_commands(add)
    return p


def _add_inspect_commands(add: Callable[[str, str], argparse.ArgumentParser]) -> None:
    """Add the commands that report on the repos: reconcile to grep."""
    s = add(
        "reconcile",
        "compare disk, GitHub and the manifest",
    )
    s.add_argument("--fix", action="store_true", help="repair every mechanical finding")
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="with --fix, report the fixes without running them",
    )
    s.add_argument("--no-fetch", action="store_true", help="skip git fetch")
    s.set_defaults(func=cmd_reconcile)

    s = add(
        "status",
        "live git and GitHub state per repo",
    )
    s.add_argument(
        "repos",
        nargs="*",
        help="repo names or paths (default: every repo on disk)",
    )
    s.add_argument("--no-fetch", action="store_true", help="skip git fetch")
    s.set_defaults(func=cmd_status)

    s = add("list", "list repos")
    s.add_argument("--group")
    s.add_argument("--lifecycle", help="only this lifecycle (naming deprecated or archived includes those repos)")
    s.add_argument("--space")
    s.add_argument("--include-inactive", action="store_true", help="also deprecated and archived repos")
    s.set_defaults(func=cmd_list)

    s = add(
        "search",
        "find repos by record attribute",
    )
    s.add_argument(
        "terms",
        nargs="+",
        help="attr=value or attr~regex; dotted attrs reach nested fields",
    )
    s.add_argument(
        "--fetch",
        action="store_true",
        help="git fetch first (for main.ahead / main.behind)",
    )
    s.add_argument("--include-inactive", action="store_true", help="also deprecated and archived repos")
    s.set_defaults(func=cmd_search)

    s = add("inventory", "every repo's full record")
    s.add_argument("--no-fetch", action="store_true", help="skip git fetch")
    s.add_argument(
        "--all",
        action="store_true",
        help="also every repo the manifest records that is not on disk",
    )
    s.add_argument("--name", help="only the repo with this name, compared without case")
    s.add_argument("--include-inactive", action="store_true", help="also deprecated and archived repos")
    s.set_defaults(func=cmd_inventory)

    s = add("grep", "rg across the repos on disk")
    s.add_argument("pattern")
    s.add_argument("--space", help="only this app space")
    s.add_argument("--repo", action="append", help="only this repo (repeatable)")
    s.add_argument("-i", "--ignore-case", action="store_true")
    s.add_argument("-F", "--fixed-strings", action="store_true")
    s.add_argument("-w", "--word", action="store_true")
    s.add_argument("-l", "--files", action="store_true", help="files with matches only")
    s.add_argument("--glob", action="append", help="rg --glob (repeatable)")
    s.set_defaults(func=cmd_grep)


def _add_repo_commands(add: Callable[[str, str], argparse.ArgumentParser]) -> None:
    """Add the commands that change repos: rebase, create, deprecate, clone and rename."""
    s = add(
        "rebase",
        "rebase main on origin/main after a fetch",
    )
    s.add_argument("repos", nargs="*", help="repo names or paths")
    s.add_argument("--all", action="store_true", help="every repo on disk")
    s.set_defaults(func=cmd_rebase)

    s = add(
        "create",
        "create a repo from a template, on GitHub too",
    )
    s.add_argument("name")
    s.add_argument("--space", required=True, help="the app space it belongs in")
    s.add_argument("--template", help="the Copier template; omitted, the template that builds the type of the name")
    s.add_argument("--lifecycle", default="active")
    s.add_argument(
        "--tier",
        choices=TIERS,
        help="the tier to record (default: tooling for the control repository, else product)",
    )
    s.add_argument(
        "--dir",
        help="folder inside the space (default: the folder the naming note places the type in)",
    )
    s.add_argument("--dry-run", action="store_true", help="check and render only")
    s.set_defaults(func=cmd_create)

    s = add(
        "deprecate",
        "rename a repo deprecated-*, here and on GitHub, close its open PRs, "
        "and delete its local clone when no work exists only there",
    )
    s.add_argument("repo")
    s.add_argument("--dry-run", action="store_true", help="check and plan only")
    s.set_defaults(func=cmd_deprecate)

    s = add(
        "clone",
        "clone a repo into the folder its name gives it; refuse if it exists elsewhere",
    )
    s.add_argument("repo")
    s.set_defaults(func=cmd_clone)

    s = add(
        "rename",
        "rename a repo with its stack, Python and written names: GitHub, disk, manifest, one pull request per repo",
    )
    s.add_argument("repo")
    s.add_argument(
        "new_name",
        nargs="?",
        help="the new repository name; omit it to bring only the stack and Python names to what atw-naming gives",
    )
    s.add_argument("--dry-run", action="store_true", help="check and print the whole plan, change nothing")
    s.add_argument(
        "--also",
        action="append",
        default=[],
        help="a further repo whose stack and Python names are brought into line in the same pull requests",
    )
    s.add_argument(
        "--skip-repo",
        action="append",
        default=[],
        help="a repository whose references are reported and not edited (repeatable)",
    )
    s.add_argument(
        "--branch-slug",
        help="name of the branch and worktree a run of several repositories shares (default python-layout)",
    )
    s.add_argument(
        "--keep-src",
        action="append",
        default=[],
        help="a repository whose files under src are reported and not edited; its other files are (repeatable)",
    )
    s.add_argument("--trailer", help="a line to end each commit message body with")
    s.add_argument("--pr-footer", help="a line to end each pull request description with")
    s.set_defaults(func=cmd_rename)


def _add_tier_commands(add: Callable[[str, str], argparse.ArgumentParser]) -> None:
    """Add the tier commands: tier, tiers and set-tier."""
    s = add(
        "naming",
        "check one repository name against the vault's repository naming note and show the rule it matched",
    )
    s.add_argument("name", help="a repository name")
    s.set_defaults(func=cmd_naming)

    s = add(
        "tier",
        "say which tier (product or tooling) the repository containing a path is in",
    )
    s.add_argument("path", help="a file or folder; a linked worktree resolves to its clone")
    s.set_defaults(func=cmd_tier)

    s = add(
        "tiers",
        "list every recorded tier and check the tier export; --write rewrites the export",
    )
    s.add_argument("--write", action="store_true", help="rewrite the export")
    s.set_defaults(func=cmd_tiers)

    s = add(
        "set-tier",
        "record a repository's tier in the manifest and commit it with the rewritten export",
    )
    s.add_argument("repo")
    s.add_argument("tier", choices=TIERS)
    s.set_defaults(func=cmd_set_tier)


def _add_upkeep_commands(add: Callable[[str, str], argparse.ArgumentParser]) -> None:
    """Add the upkeep commands: agents-sync to commit."""
    s = add(
        "agents-sync",
        "write the shared AGENTS.md blocks into every repo",
    )
    s.add_argument("--check", action="store_true", help="report repos out of date")
    s.add_argument("--dry-run", action="store_true", help="same as --check")
    s.add_argument("--repo", action="append", help="only this repo (repeatable)")
    s.add_argument("--space", help="only this app space (default: every app space)")
    s.add_argument("--trailer", help="a line to end each commit message with")
    s.set_defaults(func=cmd_agents_sync)

    s = add(
        "gitnexus-sync",
        "give every repo its GitNexus configuration and skills",
    )
    s.add_argument("--check", action="store_true", help="report repos out of date")
    s.add_argument("--dry-run", action="store_true", help="same as --check")
    s.add_argument("--repo", action="append", help="only this repo (repeatable)")
    s.add_argument("--space", help="only this app space (default: every app space)")
    s.set_defaults(func=cmd_gitnexus_sync)

    s = add(
        "templates-check",
        "compare the templates with the repos built from them",
    )
    s.set_defaults(func=cmd_templates_check)

    s = add(
        "beads-fleet",
        "check the beads fleet list (repos.additional) against the repos",
    )
    s.add_argument("--fix", action="store_true", help="correct the list")
    s.set_defaults(func=cmd_beads_fleet)

    s = add(
        "beads-setup",
        "check every active repo's beads setup; set up the named repos or --all",
    )
    s.add_argument("repos", nargs="*", help="repos to set up")
    s.add_argument("--space", help="only this app space (default: every app space)")
    s.add_argument(
        "--all",
        action="store_true",
        help="set up every active repo with a gap",
    )
    s.add_argument(
        "--check",
        action="store_true",
        help="report the gaps, change nothing",
    )
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="list the repos it would set up",
    )
    s.add_argument("--trailer", help="a line to end each commit message body with")
    s.set_defaults(func=cmd_beads_setup)

    s = add(
        "environment",
        "check every active repo's development environment; --fix runs its setup task",
    )
    s.add_argument("repos", nargs="*", help="only these repos (default: all active)")
    s.add_argument("--space", help="only this app space (default: every app space)")
    s.add_argument(
        "--fix",
        action="store_true",
        help="run the setup task of each repo with a gap",
    )
    s.set_defaults(func=cmd_environment)

    s = add(
        "python-names",
        "check every active Python repo's names and layout against the naming standard",
    )
    s.add_argument("repos", nargs="*", help="only these repos (default: all active)")
    s.add_argument("--space", help="only this app space (default: every app space)")
    s.set_defaults(func=cmd_python_names)

    s = add(
        "deprecated-prs",
        "report open pull requests in deprecated- repos",
    )
    s.add_argument("--fix", action="store_true", help="close them")
    s.set_defaults(func=cmd_deprecated_prs)

    s = add(
        "archive-due",
        "archive on GitHub every deprecated repo deprecation.archive_after_days (config) or more days "
        "after deprecated_on, "
        "keeping its record, and delete its local clone when no work exists only there",
    )
    s.add_argument("--dry-run", action="store_true", help="report what is due and what would be kept")
    s.set_defaults(func=cmd_archive_due)

    s = add(
        "doctor",
        "every health check as one report; --fix runs the repairs first",
    )
    s.add_argument(
        "--fix",
        action="store_true",
        help="run every repair (reconcile, agents-sync, beads-fleet, deprecated-prs, archive-due, matrix stacks)",
    )
    s.set_defaults(func=cmd_doctor)

    s = add(
        "commit",
        "commit and push the steward's own files after a hand edit",
    )
    s.add_argument("--message", "-m", required=True, help="what changed")
    s.set_defaults(func=cmd_commit)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        The exit status.

    """
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        return int(args.func(args, cfg))
    except PolyrepoError as exc:
        if getattr(args, "json", False):
            sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        else:
            sys.stderr.write(f"polyrepo: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
