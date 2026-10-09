#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml>=0.18"]
# ///
"""polyrepo — live facts about the project's repositories, and the manifest kept true to them.

The repository folders and GitHub are the source of truth. Every fact this tool reports about
a repo (branch, uncommitted files, last commit, main against origin/main, GitHub state) is read
live from git and GitHub on each call. The manifest contributes only what neither holds:
purpose, owns, groups and dependencies. `reconcile` compares disk, GitHub and the manifest, and
`reconcile --fix` repairs every mechanical finding: it rewrites the manifest, pushes, creates or
renames the GitHub repo so local and GitHub move together, and appends the changelog.

Settings come from `.polyrepo/config.yaml`, found in this order: `--config`, `$POLYREPO_CONFIG`,
the nearest `.polyrepo/config.yaml` above the working directory, `$SKILLSPOKE_CC/.polyrepo/`.
The repository root is the environment variable the config names in `root_env`.

Usage:
  polyrepo.py reconcile [--fix] [--dry-run] [--no-fetch]
  polyrepo.py status [repo ...] [--no-fetch]
  polyrepo.py list [--group G] [--lifecycle L] [--space S]
  polyrepo.py search attr=value [attr~regex ...] [--fetch]
  polyrepo.py inventory [--all] [--no-fetch]
  polyrepo.py purpose <repo> [--text TEXT]
  polyrepo.py grep <pattern> [--space S] [--repo R ...] [-i] [-l] [-F] [-w] [--glob G ...]
  polyrepo.py rebase <repo ...|--all>
  polyrepo.py create <name> --space S --template T --purpose TEXT [--dry-run]
  polyrepo.py rename <repo> <new-name> [--dry-run]
  polyrepo.py deprecate <repo> [--dry-run]
  polyrepo.py agents-sync [--check] [--dry-run] [--repo R ...]
  polyrepo.py templates-check
  polyrepo.py beads-fleet [--fix]
  polyrepo.py deprecated-prs [--fix]
  polyrepo.py doctor [--fix]
  polyrepo.py commit --message TEXT

A command that changes the steward's own files (manifest, changelog, knowledge store) commits
and pushes them itself, on the default branch of the repo that holds them; `commit` does the
same after a hand edit.

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
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import tomllib
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

GIT_TIMEOUT = 60
FETCH_TIMEOUT = 45
WORKERS = 16
LIFECYCLES_INACTIVE = ("deprecated", "archived")
PURPOSE_NEUTRAL_FILES = ("AGENTS.md", "CLAUDE.md")
ENTRY_LISTS = ("repos", "deprecations")
OPEN_ITEM_SECTIONS = ("drift_log", "open_questions")
PLUGIN_ROOT = Path(__file__).resolve().parents[3]


class PolyrepoError(Exception):
    """An environment or usage error the tool cannot work around."""


# --------------------------------------------------------------------------------------------
# process helpers


def run(
    argv: list[str], cwd: Path | None = None, timeout: int = GIT_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    """Run a command with captured text output and no shell.

    Returns:
        The completed process; a timeout comes back as returncode 124.
    """
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, "", f"timed out after {timeout}s")


def git(
    repo: Path, *args: str, timeout: int = GIT_TIMEOUT
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
    repo: Path, branch: str
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


def package_names(repo: Path) -> set[str]:
    """Read the names a repo publishes under: pyproject.toml's project or Poetry name and
    package.json's name, at the repo's root.

    Returns:
        The names found (possibly none).
    """
    out: set[str] = set()
    try:
        py = tomllib.loads((repo / "pyproject.toml").read_text())
        names = [
            (py.get("project") or {}).get("name"),
            ((py.get("tool") or {}).get("poetry") or {}).get("name"),
        ]
        out |= {str(n) for n in names if n}
    except (OSError, tomllib.TOMLDecodeError):
        pass
    try:
        pkg = json.loads((repo / "package.json").read_text())
        if isinstance(pkg, dict) and pkg.get("name"):
            out.add(str(pkg["name"]))
    except (OSError, json.JSONDecodeError):
        pass
    return out


_PUBLISHED_PARAMETER = re.compile(
    r"""(?:parameter_name\s*=\s*|\b[A-Z_]*(?:PARAM|SSM)[A-Z_]*\s*=\s*)f?["'](/[A-Za-z0-9]+/[A-Za-z0-9]+/)"""
)


def consumed_names(repo: Path) -> set[str]:
    """Read the names a dependent uses to reach a repo without naming it: the Python import
    packages under `src/`, and the SSM Parameter Store namespaces (`/{project}/{domain}/`)
    of the parameters its CDK stacks publish, which a consumer reads instead of a stack export.

    Returns:
        The import package names and parameter namespaces found (possibly none).
    """
    out: set[str] = set()
    src = repo / "src"
    if src.is_dir():
        # A one-word package (`event`, `chat`) would match ordinary prose in any repo.
        out |= {
            p.parent.name for p in src.glob("*/__init__.py") if "_" in p.parent.name
        }
    stacks = repo / "cdk" / "stacks"
    if stacks.is_dir():
        for f in stacks.glob("*.py"):
            try:
                out |= set(_PUBLISHED_PARAMETER.findall(f.read_text()))
            except OSError:
                continue
    return out


def mentions(repo: Path, target: str, aliases: Iterable[str] = ()) -> bool:
    """Tell whether a repo's tracked files name another repo or an item it claims to own.

    The target and each alias (for a repo, the package names it publishes) are matched
    case-insensitively as written and with `-` as `_`; a repo name is also matched without
    its application prefix when what is left still has a `-` (`shared-runtime-common` also
    matches `runtime-common`).

    Returns:
        True when a tracked file contains one of the forms.
    """
    forms: set[str] = set()
    for t in (target, *aliases):
        forms |= {t, t.replace("-", "_")}
    core = re.sub(r"(?i)^(skillspoke|shared|marketing|employer)-", "", target)
    if core != target and "-" in core:
        forms |= {core, core.replace("-", "_")}
    argv = ["grep", "-q", "-i", "-F", "-I"]
    for f in sorted(forms):
        argv += ["-e", f]
    return git(repo, *argv).returncode == 0


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
    changelog: Path
    knowledge: Path
    owner: str
    default_branch: str
    max_depth: int
    exclude_dirs: set[str]
    exclude_names: set[str]
    ttl: int
    owned: list[re.Pattern[str]]
    patterns: list[dict[str, Any]]
    raw: dict[str, Any] = dataclasses.field(default_factory=dict)
    changes: list[str] = dataclasses.field(default_factory=list)

    def setting_path(self, section: str, key: str, default: str) -> Path:
        """Resolve a path setting, relative to the config file's folder.

        Returns:
            The absolute path.
        """
        rel = (self.raw.get(section) or {}).get(key) or default
        return (self.file.parent / str(rel)).resolve()

    def classify(self, name: str) -> dict[str, Any] | None:
        """Return the first naming pattern the name matches.

        Returns:
            The pattern mapping, or None when no pattern matches.
        """
        for p in self.patterns:
            if re.fullmatch(p["regex"], name):
                return p
        return None

    def is_owned(self, name: str) -> bool:
        """Tell whether a GitHub repo name belongs to the project.

        Returns:
            True when the name is the project's and not excluded.
        """
        return name not in self.exclude_names and any(
            r.search(name) for r in self.owned
        )

    def expected_space(self, name: str) -> str | None:
        """Return the app space a repo of this name lives in; deprecated repos keep their space.

        Returns:
            The space name, or None when the name implies none.
        """
        p = self.classify(name)
        if p is None:
            return None
        if p["kind"] == "application":
            return p.get("space")
        if p["kind"] == "deprecated":
            base = name[len("deprecated-") :]
            if base.startswith("skillspoke"):
                base = "SkillSpoke" + base[len("skillspoke") :]
            q = self.classify(base)
            if q and q["kind"] == "application":
                return q.get("space")
        return None

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
            Path(os.environ["SKILLSPOKE_CC"]) / ".polyrepo" / "config.yaml"
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
    naming = raw.get("naming") or {}
    return Config(
        file=f,
        root=root,
        manifest=f.parent / raw.get("manifest", "manifest.yaml"),
        changelog=f.parent / raw.get("changelog", "changelog.md"),
        knowledge=f.parent / raw.get("knowledge", "knowledge.yaml"),
        owner=raw["github_owner"],
        default_branch=raw.get("default_branch", "main"),
        max_depth=int(raw.get("max_depth", 4)),
        exclude_dirs=set((raw.get("exclude") or {}).get("dirs") or []),
        exclude_names=set((raw.get("exclude") or {}).get("names") or []),
        ttl=int(raw.get("cache_ttl_seconds", 300)),
        owned=[re.compile(r) for r in naming.get("owned") or []],
        patterns=list(naming.get("patterns") or []),
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
            timespec="seconds"
        )
    r.branch = git_out(r.path, "symbolic-ref", "--short", "-q", "HEAD") or "(detached)"
    porcelain = git(r.path, "status", "--porcelain=v1", "--untracked-files=normal")
    r.uncommitted_files = [
        ln[3:]
        for ln in porcelain.stdout.splitlines()
        if porcelain.returncode == 0 and ln.strip()
    ]
    r.uncommitted = len(r.uncommitted_files)
    log = git_out(r.path, "log", "-1", "--format=%H%x1f%cI%x1f%s")
    if log:
        r.head_sha, r.head_date, r.head_subject = log.split("\x1f", 2)
    r.main_sha, r.origin_main_sha, r.ahead, r.behind = main_vs_origin(
        r.path, cfg.default_branch
    )
    return r


def collect_all_local(
    repos: dict[str, LocalRepo], cfg: Config, fetch: bool, use_cache: bool
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
        self._resolved: dict[str, dict[str, Any] | None] = {}
        self.repos = self._load(use_cache)
        self.lower = {n.lower(): n for n in self.repos}

    def _load(self, use_cache: bool) -> dict[str, dict[str, Any]]:
        if (
            use_cache
            and self.cache_file.exists()
            and time.time() - self.cache_file.stat().st_mtime < self.cfg.ttl
        ):
            return json.loads(self.cache_file.read_text())
        cp = run(
            [
                "gh", "repo", "list", self.cfg.owner, "--limit", "2000",
                "--json", "name,isArchived,pushedAt,url,visibility",
            ],
            timeout=120,
        )  # fmt: skip
        if cp.returncode != 0:
            msg = f"gh repo list {self.cfg.owner} failed: {cp.stderr.strip()}"
            raise PolyrepoError(msg)
        repos = {
            r["name"]: {
                "name": r["name"],
                "archived": r["isArchived"],
                "pushed_at": r["pushedAt"],
                "url": r["url"],
                "visibility": r["visibility"].lower(),
            }
            for r in json.loads(cp.stdout)
        }
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(repos))
        return repos

    def invalidate(self) -> None:
        """Drop the cached listing so the next call lists GitHub again."""
        self.cache_file.unlink(missing_ok=True)

    def get(self, name: str) -> dict[str, Any] | None:
        """Look a repo up by exact or case-insensitive name in the listing.

        Returns:
            The repo record, or None.
        """
        n = self.lower.get(name.lower())
        return self.repos.get(n) if n else None

    def resolve(self, name: str) -> dict[str, Any] | None:
        """Resolve a name through GitHub's rename redirects.

        Returns:
            The current record of the repo the name leads to, or None when none exists.
        """
        if name in self._resolved:
            return self._resolved[name]
        rec = self.get(name)
        if rec is None:
            cp = run(["gh", "api", f"repos/{self.cfg.owner}/{name}"], timeout=60)
            if cp.returncode == 0:
                d = json.loads(cp.stdout)
                if (
                    d.get("owner", {}).get("login", "").lower()
                    == self.cfg.owner.lower()
                ):
                    rec = self.get(d["name"]) or {
                        "name": d["name"],
                        "archived": d.get("archived", False),
                        "pushed_at": d.get("pushed_at"),
                        "url": d.get("html_url"),
                        "visibility": d.get("visibility"),
                    }
        self._resolved[name] = rec
        return rec


# --------------------------------------------------------------------------------------------
# manifest


class Manifest:
    """The steward's manifest, read and written with comments and layout preserved."""

    def __init__(self, path: Path) -> None:
        """Load the manifest; a missing file starts an empty one."""
        self.path = path
        self.yaml = _yaml()
        self.doc: CommentedMap = (
            self.yaml.load(path.read_text()) if path.exists() else CommentedMap()
        )
        if self.doc.get("repos") is None:
            self.doc["repos"] = []
        self.dirty = False

    def entries(self) -> dict[str, CommentedMap]:
        """Return the repo entries by name, from `repos` and from the `deprecations` list.

        Returns:
            A name → entry mapping.
        """
        return {
            e["name"]: e
            for key in ENTRY_LISTS
            for e in self.doc.get(key) or []
            if isinstance(e, dict) and e.get("name")
        }

    def groups(self) -> list[CommentedMap]:
        """Return the group mappings.

        Returns:
            Every group with a name.
        """
        return [
            g
            for g in self.doc.get("groups") or []
            if isinstance(g, dict) and g.get("name")
        ]

    def edges(self) -> list[CommentedMap]:
        """Return the dependency edges as written (group references not expanded).

        Returns:
            The edge mappings.
        """
        rel = self.doc.get("relationships") or {}
        return [e for e in rel.get("dependencies") or [] if isinstance(e, dict)]

    def groups_of(self, name: str) -> list[str]:
        """Return the groups a repo is a member of.

        Returns:
            Group names.
        """
        return [g["name"] for g in self.groups() if name in (g.get("members") or [])]

    def expand(self, ref: str) -> list[str]:
        if ref.startswith("group:"):
            gname = ref[len("group:") :]
            for g in self.groups():
                if g.get("name") == gname:
                    return list(g.get("members") or [])
            return []
        return [ref]

    def dependencies(self, name: str) -> dict[str, list[dict[str, str]]]:
        """Return a repo's dependency edges, with group references expanded.

        Returns:
            {"depends_on": [...], "depended_on_by": [...]}, each item {"repo", "kind"}.
        """
        out: dict[str, list[dict[str, str]]] = {"depends_on": [], "depended_on_by": []}
        for e in self.edges():
            kind = str(e.get("kind", ""))
            src, dst = (
                self.expand(str(e.get("from", ""))),
                self.expand(str(e.get("to", ""))),
            )
            if name in src:
                out["depends_on"].extend(
                    {"repo": d, "kind": kind} for d in dst if d != name
                )
            if name in dst:
                out["depended_on_by"].extend(
                    {"repo": s, "kind": kind} for s in src if s != name
                )
        return out

    def add_entry(self, name: str, fields: dict[str, Any]) -> None:
        """Append a new repo entry; for an entry that exists, fill only the fields it lacks."""
        e = self.entries().get(name)
        if e is not None:
            for k, v in fields.items():
                if e.get(k) is None:
                    e[k] = v
                    self.dirty = True
            return
        m = CommentedMap()
        m["name"] = name
        for k, v in fields.items():
            m[k] = v
        self.doc["repos"].append(m)
        self.dirty = True

    def set_member(self, group: str, old: str, new: str | None) -> None:
        """Rename a group member, or remove it when new is None."""
        for g in self.groups():
            members = g.get("members")
            if g["name"] == group and members and old in members:
                if new is None:
                    members.remove(old)
                else:
                    members[members.index(old)] = new
                self.dirty = True

    def remove_edge(self, edge: CommentedMap) -> None:
        """Remove one dependency edge."""
        deps = (self.doc.get("relationships") or {}).get("dependencies")
        if deps and edge in deps:
            deps.remove(edge)
            self.dirty = True

    def remove_section(self, key: str) -> None:
        """Remove a top-level section."""
        if key in self.doc:
            del self.doc[key]
            self.dirty = True

    def set_field(self, name: str, key: str, value: Any) -> None:
        """Set one field on an entry; None removes the field."""
        e = self.entries()[name]
        if value is None:
            e.pop(key, None)
        else:
            e[key] = value
        self.dirty = True

    def remove_entry(self, name: str) -> None:
        """Remove an entry, its group memberships and its dependency edges."""
        for key in ENTRY_LISTS:
            items = self.doc.get(key)
            if items:
                keep = [e for e in items if e.get("name") != name]
                items.clear()
                items.extend(keep)
        for g in self.groups():
            members = g.get("members")
            if members and name in members:
                members.remove(name)
        rel = self.doc.get("relationships") or {}
        deps = rel.get("dependencies")
        if deps:
            keep = [
                e
                for e in deps
                if not (isinstance(e, dict) and name in (e.get("from"), e.get("to")))
            ]
            deps.clear()
            deps.extend(keep)
        self.dirty = True

    def rename_entry(self, old: str, new: str) -> None:
        """Rename an entry everywhere it is referenced."""
        self.entries()[old]["name"] = new
        for g in self.groups():
            members = g.get("members")
            if members and old in members:
                members[members.index(old)] = new
        for e in self.edges():
            for k in ("from", "to"):
                if e.get(k) == old:
                    e[k] = new
        self.dirty = True

    def save(self) -> None:
        """Write the manifest back when it changed."""
        if self.dirty:
            with self.path.open("w") as fh:
                self.yaml.dump(self.doc, fh)
            self.dirty = False


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
    confirmed: dict[tuple[str, str], bool] = dataclasses.field(default_factory=dict)

    def resolve(self, wanted: list[str]) -> list[str]:
        """Resolve repo names or paths given on the command line to tracked repo names.

        Returns:
            Canonical names.
        """
        return resolve_names(self.tracked_names(), self.local, wanted)

    def live_state(self, name: str) -> str:
        """Say what disk and GitHub know of a name.

        Returns:
            "active", "inactive" (deprecated or archived), "renamed:<new name>" when GitHub
            redirects it, or "missing".
        """
        if name in self.local or self.gh.get(name):
            return (
                "inactive" if self.lifecycle(name) in LIFECYCLES_INACTIVE else "active"
            )
        rec = self.gh.resolve(name)
        return f"renamed:{rec['name']}" if rec else "missing"

    def confirm(self, src: str, target: str) -> bool | None:
        """Check live whether a repo's code names another repo or an item it owns.

        Returns:
            True or False from the repo's tracked files; None when src is not on disk.
        """
        r = self.local.get(src)
        if r is None:
            return None
        key = (src, target)
        if key not in self.confirmed:
            t = self.local.get(target)
            aliases = (package_names(t.path) | consumed_names(t.path)) if t else set()
            self.confirmed[key] = mentions(r.path, target, aliases)
        return self.confirmed[key]

    def dependency_pairs(self) -> list[tuple[str, str, str]]:
        """Return every dependency edge with its group references expanded.

        Returns:
            (from repo, to repo, kind) triples, without duplicates.
        """
        seen: dict[tuple[str, str], str] = {}
        for e in self.manifest.edges():
            kind = str(e.get("kind", ""))
            for s in self.manifest.expand(str(e.get("from", ""))):
                for d in self.manifest.expand(str(e.get("to", ""))):
                    if s != d:
                        seen.setdefault((s, d), kind)
        return [(s, d, k) for (s, d), k in seen.items()]

    def confirm_all(self, names: set[str] | None = None) -> None:
        """Run every live dependency and `owns` check touching the names (all when None), in parallel."""
        pairs = {
            (s, d)
            for s, d, _ in self.dependency_pairs()
            if names is None or s in names or d in names
        }
        for n, e in self.manifest.entries().items():
            if names is None or n in names:
                pairs |= {(n, str(o)) for o in e.get("owns") or []}
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            list(ex.map(lambda p: self.confirm(*p), sorted(pairs)))

    def lifecycle(self, name: str) -> str:
        """Derive a repo's lifecycle from reality first, the manifest second.

        Returns:
            archived, deprecated, or the manifest's lifecycle (active when absent).
        """
        g = self.gh.get(name)
        if g and g["archived"]:
            return "archived"
        if name.startswith("deprecated-"):
            return "deprecated"
        e = self.manifest.entries().get(name)
        man = str(e.get("lifecycle")) if e and e.get("lifecycle") else "active"
        return "active" if man in LIFECYCLES_INACTIVE else man

    def purpose_moved(self, r: LocalRepo | None, purpose_head: object) -> bool:
        """Say whether a repo's main has moved since its purpose was written.

        Commits that touch only agent instruction files (`AGENTS.md`, `CLAUDE.md`, at any
        depth) do not count: they say nothing about what the repo is. In the repo that
        holds the steward's own folder, commits that touch only that folder do not count
        either: recording a purpose there commits the manifest, which would otherwise
        mark the purpose stale again at once.

        Returns:
            True when the purpose needs a recheck.
        """
        if not r or not r.main_sha:
            return False
        if not purpose_head:
            return True
        if purpose_head == r.main_sha:
            return False
        excludes = [f":(exclude,glob)**/{n}" for n in PURPOSE_NEUTRAL_FILES]
        own = self.cfg.file.parent.resolve()
        if r.path == own or r.path in own.parents:
            excludes.append(f":(exclude){own.relative_to(r.path).as_posix()}")
        cp = git(
            r.path,
            "diff",
            "--quiet",
            str(purpose_head),
            r.main_sha,
            "--",
            ".",
            *excludes,
        )
        return cp.returncode != 0

    def tracked_names(self, all_github: bool = False) -> list[str]:
        """Every repo in scope: on disk, in the manifest, or a deprecated project repo on GitHub.

        With all_github, every project repo on GitHub is added as well.

        Returns:
            Sorted names.
        """
        names = set(self.local) | set(self.manifest.entries())
        for n in self.gh.repos:
            p = self.cfg.classify(n)
            if self.cfg.is_owned(n) and (
                all_github or (p and p["kind"] == "deprecated")
            ):
                names.add(n)
        return sorted(names, key=str.lower)

    def record(self, name: str, deep: bool = True) -> dict[str, Any]:
        """Build a repo's full record: live facts plus the manifest's purpose, owns, groups, dependencies.

        Groups are reported only for a repo that exists and is active. Each dependency and
        each `owns` item carries `confirmed`, checked live against the dependent repo's
        tracked files (None when that repo is not on disk, or when deep is False).

        Returns:
            The record.
        """
        r = self.local.get(name)
        e = self.manifest.entries().get(name) or {}
        g = self.gh.get(name)
        pat = self.cfg.classify(name)
        purpose_head = e.get("purpose_head")
        lifecycle = self.lifecycle(name)
        deps = self.manifest.dependencies(name)
        for d in deps["depends_on"]:
            d["confirmed"] = self.confirm(name, d["repo"]) if deep else None
        for d in deps["depended_on_by"]:
            d["confirmed"] = self.confirm(d["repo"], name) if deep else None
        live = r is not None or g is not None
        rec: dict[str, Any] = {
            "name": name,
            "space": r.space if r else self.cfg.expected_space(name),
            "path": str(r.path) if r else None,
            "lifecycle": lifecycle,
            "role": str(e["role"]) if e.get("role") else None,
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
                {"sha": r.head_sha, "date": r.head_date, "subject": r.head_subject}
                if r and r.head_sha
                else None
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
            "purpose": str(e["purpose"]).strip() if e.get("purpose") else None,
            "purpose_head": purpose_head,
            "purpose_stale": self.purpose_moved(r, purpose_head),
            "owns": [
                {
                    "item": str(o),
                    "confirmed": self.confirm(name, str(o)) if deep else None,
                }
                for o in e.get("owns") or []
            ],
            "groups": (
                self.manifest.groups_of(name)
                if live and lifecycle not in LIFECYCLES_INACTIVE
                else []
            ),
            "dependencies": deps,
        }
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
    return State(cfg, local, dups, gh, Manifest(cfg.manifest))


# --------------------------------------------------------------------------------------------
# reconcile


@dataclasses.dataclass
class Finding:
    """One way disk, GitHub and the manifest disagree, or a rule is broken."""

    kind: str
    repo: str
    detail: str
    fix: str | None = None
    action: Callable[[], None] | None = dataclasses.field(default=None, repr=False)
    manifest_change: bool = False
    logged: bool = False
    status: str = "open"
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
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
            (cp.stderr or cp.stdout).strip() or f"{cp.args} exited {cp.returncode}"
        )


def point_origin(repo: Path, url: str) -> None:
    """Point the repo's origin remote at a URL, adding the remote when it has none.

    Raises:
        GitFailedError: when git fails.
    """
    verb = "set-url" if git_out(repo, "remote", "get-url", "origin") else "add"
    must(git(repo, "remote", verb, "origin", url))


def create_on_github(cfg: Config, name: str, repo: Path) -> None:
    """Create the private GitHub repo with auto-merge allowed, point origin at it, and push.

    Raises:
        GitFailedError: when gh or git fails.
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
        )
    )
    point_origin(repo, cfg.github_url(name))
    b = cfg.default_branch
    if git_out(repo, "rev-parse", "--verify", "-q", f"refs/heads/{b}"):
        must(git(repo, "push", "-u", "origin", b, timeout=120))


def entry_fields(
    cfg: Config, name: str, lifecycle: str, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return the fields of a new manifest entry: lifecycle, GitHub URL, default branch,
    and the deprecation date when it is deprecated.

    Returns:
        The fields, with extra merged over them.
    """
    fields: dict[str, Any] = {
        "lifecycle": lifecycle,
        "remote_url": cfg.github_url(name),
        "default_branch": cfg.default_branch,
    }
    if lifecycle == "deprecated":
        fields["deprecated_on"] = today()
    return {**fields, **(extra or {})}


def reconcile(st: State) -> list[Finding]:
    """Compare disk, GitHub and the manifest, and name every disagreement with its fix.

    Returns:
        The findings, each carrying its fix action when the fix is mechanical.
    """
    cfg, man, gh = st.cfg, st.manifest, st.gh
    entries = man.entries()
    out: list[Finding] = []
    renamed_to: set[str] = set()

    out.extend(
        Finding(
            "duplicate-name",
            name,
            f"same folder name at {', '.join(str(p) for p in paths)}",
        )
        for name, paths in st.duplicates
    )

    # Manifest entries with no repo on disk.
    for name, e in entries.items():
        if name in st.local:
            continue
        lifecycle = str(e.get("lifecycle") or "active")
        rec = gh.resolve(name)
        if rec and rec["name"] != name and rec["name"] in entries:
            out.append(
                Finding(
                    "duplicate-entry",
                    name,
                    f"GitHub renamed {name} to {rec['name']}, which has its own manifest entry",
                    fix=f"remove the {name} entry",
                    action=lambda n=name: man.remove_entry(n),
                    manifest_change=True,
                )
            )
        elif rec and rec["name"] != name:
            new = rec["name"]
            renamed_to.add(new)
            out.append(
                Finding(
                    "renamed",
                    name,
                    f"GitHub renamed {name} to {new}",
                    fix=f"rename the manifest entry to {new}",
                    action=lambda o=name, n=new: man.rename_entry(o, n),
                    manifest_change=True,
                )
            )
        elif rec is None:
            out.append(
                Finding(
                    "orphan-entry",
                    name,
                    "manifest entry with no repo on disk or on GitHub",
                    fix="remove the entry, its group memberships and its dependency edges",
                    action=lambda n=name: man.remove_entry(n),
                    manifest_change=True,
                )
            )
        elif (
            lifecycle not in LIFECYCLES_INACTIVE
            and not name.startswith("deprecated-")
            and not rec["archived"]
        ):
            out.append(
                Finding(
                    "not-cloned",
                    name,
                    f"on GitHub and in the manifest but not under {cfg.root}",
                )
            )

    # Repos on disk.
    for name, r in sorted(st.local.items(), key=lambda kv: kv[0].lower()):
        out.extend(_check_local(st, name, r, entries, renamed_to))

    # Every tracked name, on disk or not: manifest fields that GitHub decides.
    for name in st.tracked_names():
        out.extend(_check_tracked(st, name, entries))

    # Project repos on GitHub.
    origins = {
        p[1].lower() for r in st.local.values() if (p := parse_github_url(r.origin_url))
    }
    for name, rec in sorted(gh.repos.items(), key=lambda kv: kv[0].lower()):
        if not cfg.is_owned(name) or name in st.local or name.lower() in origins:
            continue
        pat = cfg.classify(name)
        if pat is None:
            out.append(
                Finding(
                    "naming-violation",
                    name,
                    "GitHub repo name matches no naming pattern",
                )
            )
            continue
        if (
            pat["kind"] == "application"
            and name not in entries
            and name not in renamed_to
        ):
            out.append(
                Finding(
                    "github-only",
                    name,
                    f"on GitHub but not under {cfg.root} and not in the manifest",
                )
            )
        if (
            pat["kind"] == "deprecated"
            and name not in entries
            and name not in renamed_to
        ):
            lc = "archived" if rec["archived"] else "deprecated"
            out.append(
                Finding(
                    "untracked-github",
                    name,
                    f"{lc} repo on GitHub with no manifest entry",
                    fix=f"add a manifest entry (lifecycle {lc})",
                    action=lambda n=name, lc=lc: man.add_entry(
                        n, entry_fields(cfg, n, lc)
                    ),
                    manifest_change=True,
                )
            )

    out.extend(_check_relationships(st))
    out.extend(_check_open_items(st))
    return out


def _check_relationships(st: State) -> list[Finding]:
    """Check group members and dependency edges against disk and GitHub, and each
    dependency and `owns` claim against the dependent repo's code.

    Returns:
        The findings.
    """
    man = st.manifest
    out: list[Finding] = []
    states: dict[str, str] = {}

    def live(n: str) -> str:
        if n not in states:
            states[n] = st.live_state(n)
        return states[n]

    for g in man.groups():
        gname = str(g["name"])
        for m in [str(x) for x in g.get("members") or []]:
            s = live(m)
            if s == "active":
                continue
            if s.startswith("renamed:"):
                new = s.split(":", 1)[1]
                out.append(
                    Finding(
                        "group-member-renamed",
                        m,
                        f"member of group {gname}; GitHub renamed it to {new}",
                        fix=f"rename the member to {new}",
                        action=lambda gn=gname, o=m, n=new: man.set_member(gn, o, n),
                        manifest_change=True,
                    )
                )
                continue
            why = (
                "on neither disk nor GitHub"
                if s == "missing"
                else "deprecated or archived"
            )
            out.append(
                Finding(
                    f"group-member-{'unknown' if s == 'missing' else 'inactive'}",
                    m,
                    f"member of group {gname}, but {why}",
                    fix=f"remove it from group {gname}",
                    action=lambda gn=gname, o=m: man.set_member(gn, o, None),
                    manifest_change=True,
                )
            )

    groups = {str(g["name"]) for g in man.groups()}
    for e in man.edges():
        ends = {k: str(e.get(k, "")) for k in ("from", "to")}
        label = f"{ends['from']} -> {ends['to']}"
        problems: list[str] = []
        renames: dict[str, str] = {}
        for k, ref in ends.items():
            if ref.startswith("group:"):
                if ref[len("group:") :] not in groups:
                    problems.append(f"{ref} is not a group")
                continue
            s = live(ref)
            if s.startswith("renamed:"):
                renames[k] = s.split(":", 1)[1]
            elif s != "active":
                problems.append(
                    f"{ref} is {'on neither disk nor GitHub' if s == 'missing' else 'deprecated or archived'}"
                )
        if problems:
            out.append(
                Finding(
                    "dependency-endpoint",
                    ends["from"],
                    f"dependency {label}: {'; '.join(problems)}",
                    fix="remove the edge",
                    action=lambda e=e: man.remove_edge(e),
                    manifest_change=True,
                )
            )
        elif renames:

            def act(e: CommentedMap = e, renames: dict[str, str] = renames) -> None:
                for k, v in renames.items():
                    e[k] = v
                man.dirty = True

            out.append(
                Finding(
                    "dependency-endpoint",
                    ends["from"],
                    f"dependency {label}: GitHub renamed "
                    + ", ".join(f"{ends[k]} to {v}" for k, v in renames.items()),
                    fix="point the edge at the current names",
                    action=act,
                    manifest_change=True,
                )
            )

    st.confirm_all()
    for s, d, kind in st.dependency_pairs():
        if live(s) != "active" or live(d) != "active" or st.confirm(s, d) is not False:
            continue
        out.append(
            Finding(
                "dependency-unconfirmed",
                s,
                f"the manifest says {s} depends on {d} ({kind}), but no tracked file in {s} names {d}",
            )
        )
    for n, e in man.entries().items():
        for o in e.get("owns") or []:
            if st.confirm(n, str(o)) is False:
                out.append(
                    Finding(
                        "owns-unconfirmed",
                        n,
                        f"the manifest says {n} owns {o}, but no tracked file in {n} names it",
                    )
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
            i
            for i in items
            if not (
                isinstance(i, dict)
                and str(i.get("status", "")) in {"resolved", "false-alarm"}
            )
        ]
        if unsettled:
            out.append(
                Finding(
                    "open-items",
                    key,
                    f"the manifest's {key} holds {len(unsettled)} unsettled item(s); "
                    "put each to the user in the reply, record the answer where it belongs, "
                    "then remove the section",
                )
            )
        else:
            out.append(
                Finding(
                    "open-items",
                    key,
                    f"the manifest carries a {key} section ({len(items)} settled item(s))",
                    fix=f"remove the {key} section; git history keeps it",
                    action=lambda k=key: man.remove_section(k),
                    manifest_change=True,
                )
            )
    return out


def _check_local(
    st: State,
    name: str,
    r: LocalRepo,
    entries: dict[str, CommentedMap],
    renamed_to: set[str],
) -> list[Finding]:
    cfg, man, gh = st.cfg, st.manifest, st.gh
    out: list[Finding] = []
    e = entries.get(name)
    b = cfg.default_branch

    if e is None and name not in renamed_to:
        lc = "deprecated" if name.startswith("deprecated-") else "active"
        out.append(
            Finding(
                "untracked-repo",
                name,
                f"repo on disk at {r.path} with no manifest entry",
                fix=f"add a manifest entry (lifecycle {lc}); its purpose is then a purpose-missing finding",
                action=lambda: man.add_entry(name, entry_fields(cfg, name, lc)),
                manifest_change=True,
            )
        )

    # Naming and placement.
    pat = cfg.classify(name)
    if pat is None:
        out.append(
            Finding("naming-violation", name, "folder name matches no naming pattern")
        )
    else:
        space = cfg.expected_space(name)
        if space and space != r.space:
            out.append(
                Finding(
                    "space-mismatch",
                    name,
                    f"a {pat['name']} name lives in space {r.space}, not {space}",
                )
            )

    # Origin and GitHub.
    parsed = parse_github_url(r.origin_url)
    origin_ok = False
    if r.origin_url is None:
        rec = gh.get(name)
        if rec:
            out.append(
                Finding(
                    "no-origin",
                    name,
                    "no origin remote; GitHub has a repo of this name",
                    fix=f"add origin {cfg.github_url(rec['name'])}",
                    action=lambda: point_origin(r.path, cfg.github_url(rec["name"])),
                )
            )
        else:
            out.append(_local_only(st, name, r))
    elif parsed is None or parsed[0].lower() != cfg.owner.lower():
        out.append(
            Finding(
                "foreign-origin",
                name,
                f"origin {r.origin_url} is not a {cfg.owner} GitHub repo",
            )
        )
    else:
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
                    )
                )
        else:
            gh_name = rec["name"]
            if gh_name != name:
                taken = gh.resolve(name)
                if taken is None and pat is not None:
                    out.append(
                        Finding(
                            "name-mismatch",
                            name,
                            f"folder is {name} but its GitHub repo is {gh_name}",
                            fix=f"rename the GitHub repo {gh_name} to {name} and point origin at it",
                            action=lambda o=gh_name: rename(st, o, name),
                            logged=True,
                        )
                    )
                else:
                    why = (
                        "a different repo already has that name"
                        if taken
                        else "the folder name is not valid"
                    )
                    out.append(
                        Finding(
                            "name-mismatch",
                            name,
                            f"folder is {name} but its GitHub repo is {gh_name}; {why}",
                        )
                    )
            elif origin_name != gh_name:
                out.append(
                    Finding(
                        "origin-stale",
                        name,
                        f"origin names {origin_name}; GitHub now calls it {gh_name}",
                        fix=f"point origin at {cfg.github_url(gh_name)}",
                        action=lambda n=gh_name: point_origin(
                            r.path, cfg.github_url(n)
                        ),
                    )
                )
                origin_ok = True
            else:
                origin_ok = True

    # main pushed to GitHub.
    if origin_ok and r.main_sha:
        if r.fetch_error:
            out.append(
                Finding(
                    "fetch-failed", name, f"git fetch origin failed: {r.fetch_error}"
                )
            )
        elif r.origin_main_sha is None:
            out.append(
                Finding(
                    "unpushed",
                    name,
                    f"{b} has never been pushed to origin",
                    fix=f"git push -u origin {b}",
                    action=lambda: must(
                        git(r.path, "push", "-u", "origin", b, timeout=120)
                    ),
                )
            )
        elif r.ahead and not r.behind:
            out.append(
                Finding(
                    "unpushed",
                    name,
                    f"{b} is {r.ahead} commit(s) ahead of origin/{b}",
                    fix=f"git push origin {b}",
                    action=lambda: must(git(r.path, "push", "origin", b, timeout=120)),
                )
            )
        elif r.ahead and r.behind:
            out.append(
                Finding(
                    "diverged",
                    name,
                    f"{b} is {r.ahead} ahead and {r.behind} behind origin/{b}; needs a rebase",
                )
            )
    elif r.origin_url and r.main_sha is None:
        out.append(Finding("no-default-branch", name, f"no local {b} branch"))

    # Manifest fields the disk decides.
    if e is not None:
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
                )
            )
        if not e.get("purpose"):
            out.append(
                Finding("purpose-missing", name, "manifest entry has no purpose")
            )
        elif st.purpose_moved(r, e.get("purpose_head")):
            ph = e.get("purpose_head")
            why = (
                f"was written at {str(ph)[:12]}"
                if ph
                else "has no recorded purpose_head"
            )
            out.append(
                Finding(
                    "purpose-recheck",
                    name,
                    f"purpose {why}; {b} is now {r.main_sha[:12]}",
                )
            )
    return out


def _check_tracked(
    st: State, name: str, entries: dict[str, CommentedMap]
) -> list[Finding]:
    cfg, man = st.cfg, st.manifest
    e = entries.get(name)
    if e is None:
        return []
    out: list[Finding] = []
    rec = st.gh.get(name)
    want_url = cfg.github_url(name)
    if rec is not None and e.get("remote_url") != want_url:
        out.append(
            Finding(
                "remote-url",
                name,
                f"manifest remote_url is {e.get('remote_url') or '(missing)'}",
                fix=f"set remote_url to {want_url}",
                action=lambda: man.set_field(name, "remote_url", want_url),
                manifest_change=True,
            )
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
                    action=lambda w=want: man.set_field(name, "lifecycle", w),
                    manifest_change=True,
                )
            )
            if lc == "deprecated" and want == "active":
                out[-1] = Finding(
                    "deprecation-not-renamed",
                    name,
                    "manifest says deprecated but the repo was never renamed with the deprecated- prefix",
                )
        if st.lifecycle(name) == "deprecated":
            out.extend(_check_deprecation_age(st, name, e))
    return out


def _check_deprecation_age(st: State, name: str, e: CommentedMap) -> list[Finding]:
    """Date an undated deprecation, and archive a deprecated repo once its time is up."""
    cfg, man = st.cfg, st.manifest
    since = e.get("deprecated_on")
    if not since:
        return [
            Finding(
                "deprecated-undated",
                name,
                "deprecated repo with no deprecated_on date",
                fix=f"record deprecated_on {today()}, the first day the tool saw it deprecated",
                action=lambda: man.set_field(name, "deprecated_on", today()),
                manifest_change=True,
            )
        ]
    try:
        start = dt.date.fromisoformat(str(since)[:10])
    except ValueError:
        return [
            Finding(
                "deprecated-undated", name, f"deprecated_on {since!r} is not a date"
            )
        ]
    days = int((cfg.raw.get("deprecation") or {}).get("archive_after_days", 60))
    age = (dt.date.fromisoformat(today()) - start).days
    if age < days:
        return []

    def act() -> None:
        must(
            run(["gh", "repo", "archive", f"{cfg.owner}/{name}", "--yes"], timeout=120)
        )
        man.set_field(name, "lifecycle", "archived")
        r = st.local.get(name)
        if r:
            fleet_edit(cfg, remove=[r.path])

    return [
        Finding(
            "archive-due",
            name,
            f"deprecated {age} days ago ({start}); repos are archived {days} days after deprecation",
            fix=f"archive {cfg.owner}/{name} on GitHub, set lifecycle archived, and drop it from the beads fleet list",
            action=act,
        )
    ]


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
    """Run every mechanical fix: GitHub and git actions first, then manifest changes, then the changelog."""
    todo = [f for f in findings if f.action is not None]
    ordered = [f for f in todo if not f.manifest_change] + [
        f for f in todo if f.manifest_change
    ]
    for f in ordered:
        if dry_run:
            f.status = "planned"
            continue
        try:
            f.action()  # type: ignore[misc]
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
        append_changelog(
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


def append_changelog(cfg: Config, title: str, lines: list[str]) -> None:
    """Append a dated section to the steward's changelog, and note it for the commit."""
    body = "\n".join(f"- {ln}" for ln in lines)
    text = f"\n## {today()} — {title}\n{body}\n  - **Source:** `polyrepo`, verified live against disk and GitHub.\n"
    with cfg.changelog.open("a") as fh:
        fh.write(text)
    cfg.changes.append(title.removeprefix("polyrepo ").strip())


def commit_records(cfg: Config, subject: str) -> dict[str, Any]:
    """Commit the steward's own files (manifest, changelog, knowledge store) on the default
    branch of the repo that holds them, then pull --rebase and push.

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
    rels = [
        p.resolve().relative_to(root.resolve()).as_posix()
        for p in (cfg.manifest, cfg.changelog, cfg.knowledge, fleet_file(cfg))
        if p.exists() and p.resolve().is_relative_to(root.resolve())
    ]
    changed = git(root, "status", "--porcelain=v1", "--", *rels).stdout
    files = [ln[3:] for ln in changed.splitlines() if ln.strip()]
    if not files:
        return {"status": "clean", "files": []}
    b = cfg.default_branch
    branch = git_out(root, "symbolic-ref", "--short", "-q", "HEAD")
    try:
        if branch != b:
            msg = f"{root} is on {branch}, not {b}"
            raise GitFailedError(msg)
        _commit_paths(root, files, f"chore(polyrepo): {subject}", force=True)
        must(git(root, "pull", "--rebase", "--autostash", "--quiet", timeout=120))
        must(git(root, "push", "origin", b, timeout=120))
    except GitFailedError as exc:
        return {"status": "failed", "files": files, "error": str(exc)}
    return {"status": "pushed", "files": files}


def finish_records(cfg: Config, data: dict[str, Any]) -> None:
    """Commit and push the steward's files when this run changed them, reporting it in data."""
    if cfg.changes:
        data["records"] = commit_records(cfg, "; ".join(dict.fromkeys(cfg.changes)))


# --------------------------------------------------------------------------------------------
# beads fleet list: `repos.additional` in the control repo's beads config. The beads
# fleet watcher watches the `.beads` folder of every path listed there, so the list must
# name every active repo that has one, and nothing else.

_FLEET_ITEM = re.compile(
    r"""^(?P<indent>\s*)-\s*(?P<q>["']?)(?P<path>[^"'#\s][^"'#]*?)(?P=q)\s*(?:#.*)?$"""
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
        (i for i, ln in enumerate(lines) if re.match(r"^repos:\s*(#.*)?$", ln)), None
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


def fleet_edit(
    cfg: Config,
    remove: Iterable[Path] = (),
    add: Iterable[Path] = (),
    replace: dict[Path, Path] | None = None,
) -> list[str]:
    """Remove, add or replace fleet list entries, editing the file's lines in place.

    The file is read immediately before it is written, so a concurrent edit to another
    entry is kept; comments and every other line are left as they are. A new entry goes
    beside the entries in the same folder, in name order.

    Returns:
        One line per change made (none when the list already says it).

    Raises:
        PolyrepoError: when an entry must be added and the file has no `repos.additional`.
    """
    f = fleet_file(cfg)
    if not f.is_file():
        return []
    base = f.parent.parent
    lines = f.read_text().splitlines(keepends=True)
    blk = _fleet_block([ln.rstrip("\n") for ln in lines])
    items: list[tuple[int, str, str, re.Match[str]]] = []
    if blk:
        for i in range(*blk):
            m = _FLEET_ITEM.match(lines[i].rstrip("\n"))
            if m:
                items.append(
                    (i, _fleet_norm(base, m.group("path")), m.group("path"), m)
                )
    listed = {n for _, n, _, _ in items}

    def entry(p: Path) -> str:
        return os.path.relpath(p, base).replace(os.sep, "/").rstrip("/") + "/"

    def norm(p: Path) -> str:
        return os.path.normpath(p)

    changes: list[str] = []
    drop = {norm(p) for p in remove}
    swap = {norm(o): n for o, n in (replace or {}).items()}
    out = {i: lines[i] for i, *_ in items}
    for i, n, raw, m in items:
        if n in drop:
            out[i] = ""
            changes.append(f"removed {raw}")
        elif n in swap and norm(swap[n]) in listed:
            out[i] = ""
            changes.append(f"removed {raw} ({entry(swap[n])} is already listed)")
        elif n in swap:
            out[i] = (
                f"{m.group('indent')}- {m.group('q')}{entry(swap[n])}{m.group('q')}\n"
            )
            changes.append(f"replaced {raw} with {entry(swap[n])}")
    kept = [(i, n, raw, m) for i, n, raw, m in items if out[i]]
    before: dict[int, list[str]] = {}
    for p in add:
        new, want = entry(p), norm(p)
        if want in listed or want in {norm(v) for v in swap.values()}:
            continue
        if blk is None:
            msg = f"{f} has no repos.additional list to add {new} to"
            raise PolyrepoError(msg)
        tmpl = kept[0][3] if kept else None
        line = (
            f"{tmpl.group('indent')}- {tmpl.group('q')}{new}{tmpl.group('q')}\n"
            if tmpl
            else f'        - "{new}"\n'
        )
        same = [k for k in kept if Path(k[1]).parent == Path(want).parent]
        later = [k for k in same if k[2].lower() > new.lower()]
        if later:
            at = later[0][0]
        elif same:
            at = same[-1][0] + 1
        else:
            at = kept[-1][0] + 1 if kept else blk[1]
        before.setdefault(at, []).append(line)
        listed.add(want)
        changes.append(f"added {new}")
    if not changes:
        return []
    text = []
    for i, ln in enumerate(lines):
        text.extend(before.get(i, []))
        text.append(out.get(i, ln))
    text.extend(before.get(len(lines), []))
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
    args: argparse.Namespace, data: dict[str, Any], text: Callable[[], str]
) -> None:
    """Print JSON or text."""
    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(text())


def _status_line(rec: dict[str, Any]) -> str:
    parts = [f"{rec['name']}  [{rec['space'] or '-'}]  {rec['lifecycle']}"]
    if rec["present"]["disk"]:
        parts.append(f"branch {rec['branch']}")
        parts.append(f"uncommitted {rec['uncommitted']}")
        lc = rec["last_commit"]
        if lc:
            parts.append(
                f"last {lc['date'][:10]} {lc['sha'][:8]} {lc['subject'][:60]!r}"
            )
        m = rec["main"]
        if m and m["fetch_error"]:
            parts.append(f"fetch failed: {m['fetch_error']}")
        elif m and m["ahead"] is not None:
            parts.append(
                "main = origin/main"
                if m["up_to_date"]
                else f"main +{m['ahead']}/-{m['behind']} vs origin/main"
            )
        elif m and m["sha"] and not m["origin_sha"]:
            parts.append("main not on origin")
    else:
        parts.append("not on disk")
    g = rec["github"]
    if g:
        parts.append(
            f"GitHub pushed {str(g['pushed_at'])[:10]}{' archived' if g['archived'] else ''}"
        )
    else:
        parts.append("not on GitHub")
    return "  ".join(parts)


# --------------------------------------------------------------------------------------------
# commands


def resolve_names(
    known: Iterable[str], local: dict[str, LocalRepo], wanted: list[str]
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
            )
        ]
        for f in findings:
            tag = (
                f.status if f.status != "open" else ("fixable" if f.fix else "judgment")
            )
            lines.append(
                f"  [{f.kind}] {f.repo}: {f.detail}  ({tag}{': ' + f.fix if f.fix else ''})"
            )
            if f.error:
                lines.append(f"      error: {f.error}")
        return "\n".join([*lines, *_records_line(data)])

    emit(args, data, text)
    return 1 if open_ else 0


def _records_line(data: dict[str, Any]) -> list[str]:
    rec = data.get("records")
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
    st.confirm_all(set(names))
    recs = [st.record(n) for n in names]

    def text() -> str:
        lines = []
        for rec in recs:
            lines.append(_status_line(rec))
            if args.repos:
                lines.extend(f"    {f}" for f in rec["uncommitted_files"] or [])
        return "\n".join(lines)

    emit(args, {"repos": recs}, text)
    return 0


def cmd_inventory(args: argparse.Namespace, cfg: Config) -> int:
    """Report the full record of every repo on disk; --all adds every other repo the
    manifest or GitHub has.

    Returns:
        0.
    """
    st = gather(cfg, fetch=not args.no_fetch, use_cache=not args.no_cache)
    names = (
        st.tracked_names(all_github=True)
        if args.all
        else sorted(st.local, key=str.lower)
    )
    st.confirm_all()
    recs = [st.record(n) for n in names]
    data = {
        "root": str(cfg.root),
        "count": len(recs),
        "on_disk": len(st.local),
        "repos": recs,
    }
    emit(args, data, lambda: "\n".join(_status_line(r) for r in recs))
    return 0


def cmd_list(args: argparse.Namespace, cfg: Config) -> int:
    """List repos, filtered by group, lifecycle or space.

    Returns:
        0.
    """
    st = gather(cfg, fetch=False, use_cache=not args.no_cache)
    recs = [st.record(n, deep=False) for n in st.tracked_names()]
    if args.group:
        recs = [r for r in recs if args.group in r["groups"]]
    if args.lifecycle:
        recs = [r for r in recs if r["lifecycle"] == args.lifecycle]
    if args.space:
        recs = [r for r in recs if r["space"] == args.space]
    rows = [
        {
            "name": r["name"],
            "space": r["space"],
            "lifecycle": r["lifecycle"],
            "path": r["path"],
        }
        for r in recs
    ]
    emit(
        args,
        {"count": len(rows), "repos": rows},
        lambda: "\n".join(
            f"{r['name']}  [{r['space'] or '-'}]  {r['lifecycle']}" for r in rows
        ),
    )
    return 0


def _lookup(rec: dict[str, Any], attr: str) -> Any:
    cur: Any = rec
    for part in attr.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _matches(value: Any, op: str, want: str) -> bool:
    if isinstance(value, list):
        return any(_matches(v, op, want) for v in value)
    if isinstance(value, dict):
        return any(_matches(v, op, want) for v in value.values())
    s = "" if value is None else str(value).lower()
    if op == "~":
        return (
            re.search(want, "" if value is None else str(value), re.IGNORECASE)
            is not None
        )
    return s == want.lower()


def cmd_search(args: argparse.Namespace, cfg: Config) -> int:
    """Find repos whose record matches every attr=value (equality) or attr~regex term.

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
    deep = any(a.split(".")[0] in {"dependencies", "owns"} for a, _, _ in terms)
    if deep:
        st.confirm_all()
    recs = [st.record(n, deep=deep) for n in st.tracked_names()]
    hits = [
        r for r in recs if all(_matches(_lookup(r, a), op, v) for a, op, v in terms)
    ]
    emit(
        args,
        {"count": len(hits), "repos": hits},
        lambda: "\n".join(_status_line(r) for r in hits),
    )
    return 0


def cmd_purpose(args: argparse.Namespace, cfg: Config) -> int:
    """Record a repo's purpose (or confirm the current one) as checked at its current main.

    Returns:
        0.

    Raises:
        PolyrepoError: when the repo is not on disk, has no main, or has no purpose to confirm.
    """
    st = gather(cfg, fetch=False, use_cache=True)
    (name,) = st.resolve([args.repo])
    r = st.local.get(name)
    if r is None or not r.main_sha:
        msg = f"{name} has no local {cfg.default_branch} to check a purpose against"
        raise PolyrepoError(msg)
    st.manifest.add_entry(name, entry_fields(cfg, name, st.lifecycle(name)))
    e = st.manifest.entries()[name]
    if args.text:
        st.manifest.set_field(name, "purpose", args.text.strip())
    elif not e.get("purpose"):
        msg = f"{name} has no purpose to confirm; pass --text"
        raise PolyrepoError(msg)
    st.manifest.set_field(name, "purpose_head", r.main_sha)
    st.manifest.save()
    what = "set" if args.text else "confirmed"
    append_changelog(
        cfg,
        "polyrepo purpose",
        [f"{name}: purpose {what} at {cfg.default_branch} {r.main_sha[:12]}"],
    )
    data = {
        "repo": name,
        "purpose": str(st.manifest.entries()[name]["purpose"]).strip(),
        "purpose_head": r.main_sha,
    }
    finish_records(cfg, data)
    emit(
        args,
        data,
        lambda: "\n".join(
            [f"{name}: purpose {what} at {r.main_sha[:12]}", *_records_line(data)]
        ),
    )
    return 0


# --------------------------------------------------------------------------------------------
# actions: grep, rebase, create, deprecate, agents-sync, templates-check

REBASE_OK = ("up-to-date", "rebased", "fast-forwarded")


def _local_repos(
    cfg: Config, names: list[str] | None = None, space: str | None = None
) -> list[LocalRepo]:
    """Return the repos on disk, optionally narrowed to names (or paths) and one app space.

    Returns:
        The repos, sorted by name.

    Raises:
        PolyrepoError: when a name is not a repo on disk.
    """
    local, _ = discover(cfg)
    picked = (
        [local[n] for n in resolve_names(local, local, names)]
        if names
        else list(local.values())
    )
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
    cp = run(argv, cwd=cfg.root, timeout=300)
    if cp.returncode not in (0, 1):
        msg = f"rg failed: {_last_line(cp)}"
        raise PolyrepoError(msg)
    if not args.json:
        print(cp.stdout, end="")
        return cp.returncode
    matches: list[dict[str, Any]] = []
    for ln in cp.stdout.splitlines():
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
            }
        )
    if args.files:
        files = sorted({(m["repo"], m["file"]) for m in matches}, key=str)
        data: dict[str, Any] = {
            "count": len(files),
            "files": [{"repo": r, "file": f} for r, f in files],
        }
    else:
        data = {"count": len(matches), "matches": matches}
    print(json.dumps(data, indent=2))
    return 0 if matches else 1


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


def rebase_one(cfg: Config, r: LocalRepo) -> dict[str, Any]:
    """Fetch origin and bring main up to origin/main, stopping on a dirty tree or a conflict.

    Returns:
        {repo, status, ...}; status is one of REBASE_OK or the reason it stopped.
    """
    b = cfg.default_branch
    res: dict[str, Any] = {"repo": r.name, "path": str(r.path)}
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
    wt = _worktree_on(r.path, b)
    if wt is None:
        if ahead:
            return {
                **res,
                "status": "not-checked-out",
                "detail": f"{b} has diverged and is not checked out in any worktree",
            }
        cp = git(r.path, "update-ref", f"refs/heads/{b}", om, main)
        if cp.returncode != 0:
            return {**res, "status": "failed", "detail": _last_line(cp)}
        return {**res, "status": "fast-forwarded", "behind": 0}
    res["worktree"] = str(wt)
    dirty = git(wt, "status", "--porcelain=v1", "--untracked-files=no").stdout
    if dirty.strip():
        return {
            **res,
            "status": "dirty",
            "files": [ln[3:] for ln in dirty.splitlines() if ln.strip()],
        }
    if ahead == 0:
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
                s for s in (x.get("detail"), ", ".join(x.get("files") or [])) if s
            )
            lines.append(f"{x['repo']}: {x['status']}{'  ' + extra if extra else ''}")
        return "\n".join(lines)

    emit(args, {"repos": results, "stopped": len(bad)}, text)
    return 1 if bad else 0


# create ---------------------------------------------------------------------------------------


def _templates(cfg: Config) -> tuple[Path, dict[str, Any]]:
    """Return the templates folder and the templates settings.

    Returns:
        (folder, settings).
    """
    return (
        cfg.setting_path("templates", "dir", "../repositories/templates"),
        cfg.raw.get("templates") or {},
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


def _copier_render(
    tdir: Path, dest: Path, data: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    argv = ["copier", "copy", "--defaults", "--quiet"]
    for k, v in data.items():
        argv += ["--data", f"{k}={v}"]
    return run([*argv, str(tdir), str(dest)], timeout=300)


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
        msg = f"{name} matches no application naming pattern"
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
    rx = ((tset.get("kinds") or {}).get(template) or {}).get("name_regex")
    if rx and not re.search(rx, name):
        msg = f"a {template} repo name must match {rx}"
        raise PolyrepoError(msg)
    sub = args.dir
    if sub is None:
        sub = ((tset.get("placement") or {}).get(space) or {}).get(template, "")
    space_dir = cfg.root / space
    if not space_dir.is_dir():
        msg = f"no app space folder {space_dir}"
        raise PolyrepoError(msg)
    dest = space_dir / sub / name if sub else space_dir / name
    local, _ = discover(cfg)
    if dest.exists() or name.lower() in {n.lower() for n in local}:
        msg = f"{name} already exists on disk"
        raise PolyrepoError(msg)
    if GitHub(cfg, use_cache=False).resolve(name) is not None:
        msg = f"{cfg.owner}/{name} already exists on GitHub"
        raise PolyrepoError(msg)
    if name in Manifest(cfg.manifest).entries():
        msg = f"{name} already has a manifest entry"
        raise PolyrepoError(msg)
    return tdir, dest


def cmd_create(args: argparse.Namespace, cfg: Config) -> int:
    """Create a repo from a template, on disk and on GitHub, with its manifest entry.

    Returns:
        0 on success, 1 when a step after rendering failed.

    Raises:
        PolyrepoError: when the request is invalid or the template does not render.
    """
    name, b = args.name, cfg.default_branch
    tdir, dest = _create_checks(args, cfg)
    data = {"service_name": _service_name(cfg, name), "repo_name": name}
    res: dict[str, Any] = {
        "repo": name,
        "space": args.space,
        "template": args.template,
        "path": str(dest),
        "dry_run": args.dry_run,
        "steps": [
            f"render the {args.template} template into {dest}",
            "write the shared AGENTS.md block",
            f"git init on {b} and commit",
            f"create the private GitHub repo {cfg.owner}/{name} and push {b}",
            f"add the manifest entry (lifecycle {args.lifecycle}) with the purpose given",
            "add it to the beads fleet list (repos.additional) when it has a .beads folder",
        ],
    }
    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="polyrepo-create-") as tmp:
            out = Path(tmp) / name
            cp = _copier_render(tdir, out, data)
            if cp.returncode != 0:
                msg = f"copier failed: {_last_line(cp)}"
                raise PolyrepoError(msg)
            res["rendered_files"] = sorted(
                p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()
            )
        emit(
            args,
            res,
            lambda: "\n".join(
                [f"dry run: {name} -> {dest}"]
                + [f"  {s}" for s in res["steps"]]
                + [f"  template renders {len(res['rendered_files'])} files"]
            ),
        )
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    cp = _copier_render(tdir, dest, data)
    if cp.returncode != 0:
        msg = f"copier failed: {_last_line(cp)}"
        raise PolyrepoError(msg)
    agents = dest / "AGENTS.md"
    agents.write_text(
        _with_blocks(
            agents.read_text() if agents.exists() else None,
            _blocks_for(_agents_blocks(cfg), name),
            name,
        )
    )
    try:
        must(git(dest, "init", f"--initial-branch={b}"))
        must(git(dest, "add", "-A"))
        must(
            git(
                dest,
                "commit",
                "-m",
                f"chore(repo): scaffold {name} from the {args.template} template",
                timeout=300,
            )
        )
        create_on_github(cfg, name, dest)
    except GitFailedError as exc:
        res["error"] = str(exc)
        emit(
            args, res, lambda: f"{name}: created at {dest} but stopped: {res['error']}"
        )
        return 1
    man = Manifest(cfg.manifest)
    man.add_entry(
        name,
        entry_fields(
            cfg,
            name,
            args.lifecycle,
            {
                "purpose": args.purpose.strip(),
                "purpose_head": git_out(dest, "rev-parse", "HEAD"),
            },
        ),
    )
    man.save()
    log = [
        f"{name}: created in {args.space} from the {args.template} template and pushed to {cfg.owner}/{name}"
    ]
    if args.lifecycle not in LIFECYCLES_INACTIVE and (dest / ".beads").is_dir():
        try:
            log.extend(f"beads fleet list: {c}" for c in fleet_edit(cfg, add=[dest]))
        except (OSError, PolyrepoError) as exc:
            res["fleet_error"] = str(exc)
            log.append(f"beads fleet list NOT updated: {exc}")
    append_changelog(cfg, "polyrepo create", log)
    GitHub(cfg, use_cache=True).invalidate()
    finish_records(cfg, res)
    emit(
        args,
        res,
        lambda: "\n".join(
            [f"{name}: created at {dest} and pushed to GitHub", *_records_line(res)]
        ),
    )
    return 0


# rename ----------------------------------------------------------------------------------------


def deprecated_name(name: str) -> str:
    """Return the deprecated name of a repo: the deprecated- prefix, all lowercase.

    Returns:
        The new name.
    """
    return "deprecated-" + name.lower()


def rename(
    st: State,
    old: str,
    new: str,
    extra_fields: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Rename a repo on GitHub and on disk together, repoint origin, and rename its manifest entry.

    The one rename operation: `rename`, `deprecate` and reconcile's name-parity repair all
    run it. It finds the local clone under either name and the GitHub repo through its
    origin (following GitHub's rename redirects), so it also completes a rename that only
    one side has made. It refuses when the new name matches no naming pattern, another
    GitHub repo has it, the target folder exists, or the local default branch is not known
    to be pushed. A name starting with `deprecated-` makes the entry deprecated, dated
    today unless it already has a date.

    Returns:
        The steps planned (dry run) or done.

    Raises:
        PolyrepoError: when the rename cannot proceed as it stands.
        GitFailedError: when a step fails part way; the message names the steps done.
    """
    cfg, man = st.cfg, st.manifest
    if old == new:
        msg = f"{old} is already named {new}"
        raise PolyrepoError(msg)
    if cfg.classify(new) is None:
        msg = f"{new} matches no naming pattern"
        raise PolyrepoError(msg)
    r = st.local.get(old) or st.local.get(new)
    parsed = parse_github_url(r.origin_url) if r else None
    rec = st.gh.resolve(parsed[1] if parsed else old)
    taken = st.gh.resolve(new)
    if taken is not None and (rec is None or taken["name"] != rec["name"]):
        msg = f"{cfg.owner}/{new} already exists on GitHub"
        raise PolyrepoError(msg)
    url = cfg.github_url(new)
    steps: list[str] = []
    if rec and rec["name"] != new:
        steps.append(f"rename the GitHub repo {cfg.owner}/{rec['name']} to {new}")
    new_path = None
    if r:
        if r.fetch_error:
            msg = f"{r.name}: git fetch failed ({r.fetch_error}); cannot confirm {cfg.default_branch} is pushed"
            raise PolyrepoError(msg)
        if r.ahead:
            msg = f"{r.name}: {cfg.default_branch} is {r.ahead} commit(s) ahead of origin; push it first"
            raise PolyrepoError(msg)
        new_path = r.path.with_name(new)
        if new_path != r.path:
            if new_path.exists():
                msg = f"{new_path} already exists"
                raise PolyrepoError(msg)
            steps.append(f"move {r.path} to {new_path}")
        if r.origin_url != url:
            steps.append(f"point origin at {url}")
    entry = man.entries().get(old) or man.entries().get(new) or {}
    lc = str(entry.get("lifecycle") or "active")
    if new.startswith("deprecated-"):
        lc = "deprecated"
    elif lc in LIFECYCLES_INACTIVE:
        lc = "active"
    fields = entry_fields(cfg, new, lc, extra_fields)
    if entry.get("deprecated_on") and lc == "deprecated":
        fields["deprecated_on"] = entry["deprecated_on"]
    steps.append(
        f"manifest: entry {new}, " + ", ".join(f"{k} {v}" for k, v in fields.items())
    )
    active = lc not in LIFECYCLES_INACTIVE
    if r and new_path:
        steps.append(
            "beads fleet list (repos.additional): "
            + (
                f"point the entry at {new_path}, or add it when it has a .beads folder"
                if active
                else f"remove {r.path}"
            )
        )
    if dry_run:
        return steps

    done: list[str] = []
    try:
        if rec and rec["name"] != new:
            must(
                run(
                    [
                        "gh", "repo", "rename", new,
                        "--repo", f"{cfg.owner}/{rec['name']}", "--yes",
                    ],
                    timeout=120,
                )
            )  # fmt: skip
            done.append(f"GitHub {rec['name']} renamed to {new}")
        if r and new_path:
            if new_path != r.path:
                r.path.rename(new_path)
                done.append(f"moved {r.path} to {new_path}")
            point_origin(new_path, url)
            done.append(f"origin set to {url}")
            must(git(new_path, "worktree", "repair"))
    except (GitFailedError, OSError) as exc:
        so_far = f" (done before it stopped: {'; '.join(done)})" if done else ""
        raise GitFailedError(f"{exc}{so_far}") from exc
    if old in man.entries() and new not in man.entries():
        man.rename_entry(old, new)
    man.add_entry(new, {})
    for k, v in fields.items():
        man.set_field(new, k, v)
    man.set_field(new, "local_path", None)
    man.save()
    if r and new_path:
        try:
            done.extend(
                f"beads fleet list: {c}"
                for c in fleet_after_rename(cfg, r.path, new_path, active)
            )
        except (OSError, PolyrepoError) as exc:
            done.append(f"beads fleet list NOT updated: {exc}")
    append_changelog(
        cfg, f"polyrepo rename {old} to {new}", [*done, f"manifest entry is now {new}"]
    )
    st.gh.invalidate()
    return done


def _run_rename(
    args: argparse.Namespace,
    cfg: Config,
    st: State,
    name: str,
    new: str,
    after: Callable[[dict[str, Any]], bool] | None = None,
) -> int:
    """Run a rename for a command and report it.

    `after`, when given, runs once the rename is done (or planned, on a dry run), adds its
    own results to the report and steps, and returns False when it failed.

    Returns:
        0 on success, 1 when a step failed part way.
    """
    res: dict[str, Any] = {"repo": name, "new_name": new, "dry_run": args.dry_run}
    try:
        res["steps"] = rename(st, name, new, dry_run=args.dry_run)
    except GitFailedError as exc:
        res["error"] = str(exc)
        emit(args, res, lambda: f"{name}: stopped: {res['error']}")
        return 1
    ok = after(res) if after else True
    finish_records(cfg, res)
    head = (
        f"dry run: rename {name} to {new}"
        if args.dry_run
        else f"{name}: renamed to {new}"
    )
    emit(
        args,
        res,
        lambda: "\n".join(
            [head, *[f"  {s}" for s in res["steps"]], *_records_line(res)]
        ),
    )
    return 0 if ok else 1


def cmd_rename(args: argparse.Namespace, cfg: Config) -> int:
    """Rename a repo: on GitHub and on disk together, repointing origin and the manifest.

    The new name must match a naming pattern. The beads fleet list (`repos.additional`)
    is updated with the folder. Anything else outside git, GitHub and the steward's
    records that names the repo by its old name (docs, workflow artifacts) is the
    caller's to update.

    Returns:
        0 on success, 1 when a step failed part way.
    """
    st = gather(cfg, fetch=True, use_cache=not args.no_cache)
    (name,) = st.resolve([args.repo])
    return _run_rename(args, cfg, st, name, args.new_name)


DEPRECATED_PR_COMMENT = "Closed: this repository is deprecated."


def open_prs(cfg: Config, repo: str) -> list[dict[str, Any]]:
    """List a GitHub repo's open pull requests.

    Returns:
        One {number, title, url} per open pull request.

    Raises:
        GitFailedError: when gh cannot list them.
    """
    cp = run(
        [
            "gh", "pr", "list", "--repo", f"{cfg.owner}/{repo}", "--state", "open",
            "--limit", "500", "--json", "number,title,url",
        ],
        timeout=120,
    )  # fmt: skip
    must(cp)
    return json.loads(cp.stdout or "[]")


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


def _close_repo_prs(cfg: Config, repo: str, dry_run: bool, res: dict[str, Any]) -> bool:
    """Close every open pull request of a repo, recording each in res["closed_prs"].

    Returns:
        False when the pull requests could not be listed or one did not close.
    """
    try:
        prs = open_prs(cfg, repo)
    except (GitFailedError, json.JSONDecodeError) as exc:
        res["pr_error"] = f"could not list open pull requests: {exc}"
        res["steps"].append(f"open pull requests NOT closed: {res['pr_error']}")
        return False
    ok = True
    for pr in prs:
        pr["status"] = "planned" if dry_run else "closed"
        if not dry_run and (err := close_pr(cfg, repo, pr["number"])):
            pr["status"], pr["error"], ok = "failed", err, False
        verb = {"planned": "close", "closed": "closed", "failed": "FAILED to close"}
        res["steps"].append(
            f"{verb[pr['status']]} pull request #{pr['number']} {pr['title']}"
            + (f": {pr['error']}" if pr.get("error") else "")
        )
    if not prs:
        res["steps"].append("no open pull requests to close")
    res["closed_prs"] = prs
    return ok


def cmd_deprecate(args: argparse.Namespace, cfg: Config) -> int:
    """Deprecate a repo: rename it to its deprecated- name, which dates the deprecation,
    then close every open pull request in it with the deprecation comment.

    Returns:
        0 on success, 1 when a step failed part way or a pull request did not close.

    Raises:
        PolyrepoError: when the repo is already deprecated.
    """
    st = gather(cfg, fetch=True, use_cache=not args.no_cache)
    (name,) = st.resolve([args.repo])
    if name.startswith("deprecated-"):
        msg = f"{name} is already deprecated"
        raise PolyrepoError(msg)
    new = deprecated_name(name)
    return _run_rename(
        args,
        cfg,
        st,
        name,
        new,
        after=lambda res: _close_repo_prs(
            cfg, name if args.dry_run else new, args.dry_run, res
        ),
    )


# agents-sync ----------------------------------------------------------------------------------


PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"
PLUGIN_IMPORT = re.compile(r"^@\$\{CLAUDE_PLUGIN_ROOT\}/(\S+?)`?\s*$", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class AgentsBlock:
    """One marked block agents-sync owns in every repo's AGENTS.md."""

    marker: str
    text: str
    exclude: frozenset[str]

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
    text = f.read_text()
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
    sc = cfg.raw.get("agents_sync") or {}
    specs = sc.get("blocks") or []
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
        body = (
            _plugin_block_body(f) if spec.get("plugin_file") else f.read_text().strip()
        )
        note = str(spec.get("note") or "written by polyrepo agents-sync")
        out.append(
            AgentsBlock(
                marker,
                f"<!-- BEGIN {marker}: {note} -->\n{body}\n<!-- END {marker} -->",
                frozenset(spec.get("exclude") or []),
            )
        )
    if not out:
        msg = "agents_sync.blocks in the polyrepo config lists no block"
        raise PolyrepoError(msg)
    return out


def _blocks_for(blocks: list[AgentsBlock], name: str) -> list[AgentsBlock]:
    """Return the blocks a repo receives.

    Returns:
        The blocks whose exclude list does not name the repo.
    """
    return [b for b in blocks if name not in b.exclude]


def _with_blocks(text: str | None, blocks: list[AgentsBlock], name: str) -> str:
    """Put each block into AGENTS.md text: replace its marked copy, or append one.

    Returns:
        The new text.
    """
    out = f"# {name}\n" if text is None else text
    for b in blocks:
        rx = b.pattern()
        if rx.search(out):
            out = rx.sub(lambda _m, t=b.text: t, out, count=1)
        else:
            out = out.rstrip("\n") + "\n\n" + b.text + "\n"
    return out


def _without_blocks(text: str, blocks: list[AgentsBlock]) -> str:
    """Return the text with every owned block removed, for comparing what else changed.

    Returns:
        The text outside the owned blocks.
    """
    for b in blocks:
        text = b.pattern().sub("", text)
    return text


def _commit_paths(
    repo: Path, paths: list[str], message: str, force: bool = False
) -> None:
    """Commit only these paths, re-staging once when a pre-commit hook rewrote them.

    With force, the paths are staged even inside an ignored folder (the beads fleet list
    is a tracked file under the gitignored `.beads/`).

    Raises:
        GitFailedError: when the commit still fails.
    """
    add = ["add", "-f", "--"] if force else ["add", "--"]
    must(git(repo, *add, *paths))
    cp = git(repo, "commit", "-m", message, "--", *paths, timeout=300)
    if cp.returncode != 0:
        must(git(repo, *add, *paths))
        must(git(repo, "commit", "-m", message, "--", *paths, timeout=300))


def _sync_one(
    cfg: Config, r: LocalRepo, blocks: list[AgentsBlock], write: bool
) -> dict[str, Any]:
    f = r.path / "AGENTS.md"
    cur = f.read_text() if f.is_file() else None
    want = _with_blocks(cur, blocks, r.name)
    if cur == want:
        state = "current"
    elif cur is None:
        state = "missing-file"
    elif all(b.pattern().search(cur) for b in blocks):
        state = "outdated"
    else:
        state = "missing-block"
    res: dict[str, Any] = {"repo": r.name, "state": state}
    if state == "current" or not write:
        return res
    b = cfg.default_branch
    branch = git_out(r.path, "symbolic-ref", "--short", "-q", "HEAD")
    if branch != b:
        return {**res, "status": "skipped", "detail": f"on {branch}, not {b}"}
    if cur is not None and git_out(r.path, "status", "--porcelain", "--", "AGENTS.md"):
        head = git(r.path, "show", "HEAD:AGENTS.md")
        if head.returncode != 0 or _without_blocks(
            head.stdout, blocks
        ) != _without_blocks(cur, blocks):
            return {
                **res,
                "status": "skipped",
                "detail": "AGENTS.md has uncommitted changes outside the synced blocks",
            }
    f.write_text(want)
    paths = ["AGENTS.md"]
    claude = r.path / "CLAUDE.md"
    if cur is None and not claude.exists() and not claude.is_symlink():
        claude.symlink_to("AGENTS.md")
        paths.append("CLAUDE.md")
    try:
        _commit_paths(r.path, paths, "docs(agents): sync the shared instruction blocks")
    except GitFailedError as exc:
        git(r.path, "reset", "-q", "--", *paths)
        if cur is None:
            f.unlink(missing_ok=True)
        else:
            f.write_text(cur)
        if "CLAUDE.md" in paths:
            claude.unlink(missing_ok=True)
        return {**res, "status": "failed", "detail": str(exc)}
    cp = git(r.path, "push", "origin", b, timeout=120)
    if cp.returncode != 0:
        return {
            **res,
            "status": "committed",
            "detail": f"push failed: {_last_line(cp)}",
        }
    return {**res, "status": "pushed"}


def cmd_agents_sync(args: argparse.Namespace, cfg: Config) -> int:
    """Write the owned blocks into every repo's AGENTS.md, committing and pushing each repo.

    Returns:
        0 when every repo is current (or was brought current and pushed), else 1.
    """
    blocks = _agents_blocks(cfg)
    repos = [
        (r, own)
        for r in _local_repos(cfg, args.repo)
        if not r.name.startswith("deprecated-") and (own := _blocks_for(blocks, r.name))
    ]
    write = not args.check and not args.dry_run
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(lambda rb: _sync_one(cfg, rb[0], rb[1], write), repos))
    if write:
        bad = [
            x for x in results if x["state"] != "current" and x["status"] != "pushed"
        ]
    else:
        bad = [x for x in results if x["state"] != "current"]
    counts: dict[str, int] = {}
    for x in results:
        counts[x["state"]] = counts.get(x["state"], 0) + 1

    def text() -> str:
        lines = [
            f"{len(results)} repos: "
            + ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
        ]
        for x in results:
            if x["state"] == "current":
                continue
            st_ = x.get("status", "would update" if args.dry_run else "")
            detail = x.get("detail", "")
            lines.append(
                f"  {x['repo']}: {x['state']}{'  ' + st_ if st_ else ''}{'  ' + detail if detail else ''}"
            )
        return "\n".join(lines)

    emit(args, {"repos": results, "counts": counts, "not_current": len(bad)}, text)
    return 1 if bad else 0


# templates-check ------------------------------------------------------------------------------


def _read_yaml(f: Path) -> dict[str, Any]:
    if not f.is_file():
        return {}
    try:
        d = YAML(typ="safe").load(f.read_text())
    except (OSError, YAMLError):
        return {}
    return d if isinstance(d, dict) else {}


def _template_for(
    r: LocalRepo, kinds: dict[str, Any]
) -> tuple[str | None, str | None, dict[str, Any]]:
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
        if stype and stype in ((k or {}).get("status_types") or []):
            return t, "repo.status.yaml", answers
    for t, k in kinds.items():
        rx = (k or {}).get("name_regex")
        if rx and re.search(rx, r.name):
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
    answers: dict[str, Any],
) -> dict[str, Any]:
    """Render the template as this repo would have been rendered and compare file by file.

    Returns:
        {repo, files: {path: (state, repo commit time)}} or {repo, error}.
    """
    data = {k: str(v) for k, v in answers.items() if not k.startswith("_")} or {
        "service_name": _service_name(cfg, r.name),
        "repo_name": r.name,
    }
    out: dict[str, tuple[str, int | None]] = {}
    with tempfile.TemporaryDirectory(prefix="polyrepo-tc-") as tmp:
        rendered = Path(tmp) / r.name
        cp = _copier_render(tdir, rendered, data)
        if cp.returncode != 0:
            return {"repo": r.name, "error": _last_line(cp)}
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
    return {"repo": r.name, "files": out}


def _check_template(
    cfg: Config,
    tdir: Path,
    members: list[tuple[LocalRepo, str, dict[str, Any]]],
    ignore: list[str],
) -> dict[str, Any]:
    files = _template_files(tdir, ignore)
    now = int(time.time())
    tdates = {rel: _commit_time(tdir, src) or now for rel, src in files.items()}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        compared = list(
            ex.map(
                lambda m: _compare_to_template(cfg, m[0], tdir, files, m[2]), members
            )
        )
    rows = []
    for rel in files:
        row: dict[str, Any] = {
            "file": rel,
            "same": 0,
            "missing": [],
            "repo_newer": [],
            "template_newer": [],
        }
        for c in compared:
            state, when = (c.get("files") or {}).get(rel, (None, None))
            if state == "same":
                row["same"] += 1
            elif state == "missing":
                row["missing"].append(c["repo"])
            elif state == "differs":
                key = "repo_newer" if when and when > tdates[rel] else "template_newer"
                row[key].append(c["repo"])
        if row["missing"] or row["repo_newer"] or row["template_newer"]:
            rows.append(row)
    return {
        "template": tdir.name,
        "repos": [{"repo": m[0].name, "matched_by": m[1]} for m in members],
        "render_errors": [
            {"repo": c["repo"], "error": c["error"]} for c in compared if "error" in c
        ],
        "files": rows,
        "lags": any(row["repo_newer"] for row in rows),
    }


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
        for t, k in (tset.get("kinds") or {}).items()
        if (troot / t / "copier.yml").is_file()
    }
    ignore = list(tset.get("ignore") or [])
    by_template: dict[str, list[tuple[LocalRepo, str, dict[str, Any]]]] = {
        t: [] for t in kinds
    }
    untemplated: dict[str, list[str]] = {}
    for r in _local_repos(cfg):
        if r.name.startswith("deprecated-"):
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
    results = [
        _check_template(cfg, troot / t, members, ignore)
        for t, members in sorted(by_template.items())
    ]
    no_template = [
        {"kind": k, "repos": sorted(v)} for k, v in sorted(untemplated.items())
    ]
    data = {
        "templates": results,
        "kinds_without_template": no_template,
        "lagging_templates": [x["template"] for x in results if x["lags"]],
    }

    def text() -> str:
        lines = []
        for x in results:
            how: dict[str, int] = {}
            for m in x["repos"]:
                how[m["matched_by"]] = how.get(m["matched_by"], 0) + 1
            lines.append(
                f"{x['template']}: {len(x['repos'])} repos ("
                + ", ".join(f"{v} by {k}" for k, v in sorted(how.items()))
                + f"){'  TEMPLATE LAGS' if x['lags'] else ''}"
            )
            for row in x["files"]:
                bits = []
                if row["repo_newer"]:
                    bits.append(
                        f"newer in {len(row['repo_newer'])} repo(s) than the template"
                    )
                if row["template_newer"]:
                    bits.append(f"older in {len(row['template_newer'])} repo(s)")
                if row["missing"]:
                    bits.append(f"missing from {len(row['missing'])} repo(s)")
                lines.append(
                    f"  {row['file']}: same in {row['same']}; " + "; ".join(bits)
                )
            lines.extend(
                f"  render error {e['repo']}: {e['error']}" for e in x["render_errors"]
            )
        lines.append("repo kinds with no template:")
        lines.extend(f"  {k['kind']}: {', '.join(k['repos'])}" for k in no_template)
        return "\n".join(lines)

    emit(args, data, text)
    return 1 if data["lagging_templates"] or no_template else 0


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
    lc = {
        os.path.normpath(r.path): (r.name, st.lifecycle(r.name))
        for r in st.local.values()
    }
    active = {
        p: n
        for p, (n, life) in lc.items()
        if life not in LIFECYCLES_INACTIVE and p != control
    }
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
            )
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
                )
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
            append_changelog(
                cfg,
                "polyrepo beads-fleet --fix",
                [f"beads fleet list (repos.additional): {c}" for c in changes],
            )
    data: dict[str, Any] = {
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
            f"{data['listed']} listed in {data['file']}, {len(findings)} findings ({data['fixed']} fixed)"
        ]
        lines.extend(
            f"  [{f.kind}] {f.repo}: {f.detail} ({f.status})" for f in findings
        )
        return "\n".join([*lines, *_records_line(data)])

    emit(args, data, text)
    return 1 if data["open"] else 0


def deprecated_open_prs(cfg: Config) -> list[dict[str, Any]]:
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
    return [
        {
            "repo": pr["repository"]["name"],
            "number": pr["number"],
            "title": pr["title"],
            "url": pr["url"],
        }
        for pr in json.loads(cp.stdout or "[]")
        if pr["repository"]["name"].startswith("deprecated-")
    ]


def cmd_deprecated_prs(args: argparse.Namespace, cfg: Config) -> int:
    """Check for open pull requests in deprecated- repos; with --fix, close them.

    Returns:
        0 when none is open (or every one was closed), else 1.
    """
    prs = deprecated_open_prs(cfg)
    findings = [
        Finding(
            "deprecated-repo-open-pr",
            pr["repo"],
            f"#{pr['number']} {pr['title']} ({pr['url']}) is open in a deprecated repo",
            fix=f"close #{pr['number']} with the comment {DEPRECATED_PR_COMMENT!r}",
        )
        for pr in prs
    ]
    if args.fix:
        for pr, f in zip(prs, findings, strict=True):
            err = close_pr(cfg, pr["repo"], pr["number"])
            f.status, f.error = ("failed", err) if err else ("fixed", None)
    data: dict[str, Any] = {
        "findings": [f.as_dict() for f in findings],
        "open": sum(f.status in {"open", "failed"} for f in findings),
        "fixed": sum(f.status == "fixed" for f in findings),
    }

    def text() -> str:
        lines = [
            f"{len(findings)} open pull requests in deprecated repos ({data['fixed']} closed)"
        ]
        lines.extend(
            f"  [{f.kind}] {f.repo}: {f.detail} ({f.status})"
            + (f": {f.error}" if f.error else "")
            for f in findings
        )
        return "\n".join(lines)

    emit(args, data, text)
    return 1 if data["open"] else 0


BEADS_AUDIT = PLUGIN_ROOT / "skills" / "polyrepo-beads" / "scripts" / "audit-fleet.sh"
SELF = Path(__file__).resolve()
DOCTOR_CHECKS: dict[str, list[str]] = {
    "reconcile": [sys.executable, str(SELF), "reconcile", "--json"],
    "agents-sync": [sys.executable, str(SELF), "agents-sync", "--check", "--json"],
    "beads": ["bash", str(BEADS_AUDIT), "--json"],
    "beads-fleet": [sys.executable, str(SELF), "beads-fleet", "--json"],
    "deprecated-prs": [sys.executable, str(SELF), "deprecated-prs", "--json"],
}
DOCTOR_REPAIRS: dict[str, list[str]] = {
    "reconcile --fix": [sys.executable, str(SELF), "reconcile", "--fix", "--json"],
    "agents-sync": [sys.executable, str(SELF), "agents-sync", "--json"],
    "beads-fleet --fix": [sys.executable, str(SELF), "beads-fleet", "--fix", "--json"],
    "deprecated-prs --fix": [
        sys.executable, str(SELF), "deprecated-prs", "--fix", "--json",
    ],
}  # fmt: skip


def _finding(check: str, subject: str, kind: str, detail: str) -> dict[str, Any]:
    return {"check": check, "subject": subject, "kind": kind, "detail": detail}


def _run_json(argv: list[str], extra: list[str]) -> tuple[int, dict[str, Any]]:
    """Run one of the tool's own checks or repairs as a separate process and read its JSON.

    Returns:
        (exit status, parsed output); unreadable output becomes {"error": ...}.
    """
    cp = run([*argv, *extra], timeout=900)
    try:
        data = json.loads(cp.stdout) if cp.stdout.strip() else {}
    except json.JSONDecodeError:
        data = {"error": f"unreadable output: {cp.stdout[:200]}"}
    if not isinstance(data, dict):
        data = {"error": f"unexpected output: {cp.stdout[:200]}"}
    if cp.returncode == 2 and "error" not in data:
        data["error"] = _last_line(cp) or "exited 2"
    return cp.returncode, data


def _doctor_findings(check: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn one check's JSON output into doctor findings.

    Returns:
        One finding per open problem the check reported.
    """
    if "error" in data:
        return [_finding(check, "-", "error", str(data["error"]))]
    if check in {"reconcile", "beads-fleet", "deprecated-prs"}:
        return [
            _finding(check, f["repo"], f["kind"], f["detail"])
            for f in data.get("findings") or []
            if f.get("status") in {"open", "failed", "planned"}
        ]
    if check == "agents-sync":
        return [
            _finding(
                check,
                r["repo"],
                r["state"],
                r.get("detail") or "shared AGENTS.md block not current",
            )
            for r in data.get("repos") or []
            if isinstance(r, dict) and r.get("state") != "current"
        ]
    if check == "beads":
        return [
            _finding(check, a["repo"], "beads-anomaly", a["detail"])
            for a in data.get("anomalies") or []
        ]
    return []


def _resolve_location(cfg: Config, loc: str) -> Path:
    target = Path(expand_env(loc)).expanduser()
    return target if target.is_absolute() else cfg.file.parent.parent / target


def _governance_findings(cfg: Config) -> list[dict[str, Any]]:
    """Check every governance entry: its location exists, and a script or tool's `invoke`
    runs (the part before its first `<placeholder>`, with `--help`).

    Returns:
        One finding per entry that does not resolve or does not run.
    """
    out = []
    for e in Manifest(cfg.manifest).doc.get("governance") or []:
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
                )
            )
        if str(e.get("type")) not in {"script", "tool"}:
            continue
        invoke = str(e.get("invoke") or "").split("<", 1)[0].strip()
        if not invoke:
            out.append(
                _finding("governance", subject, "invoke-missing", "no invoke command")
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
                )
            )
    return out


def _knowledge_findings(cfg: Config) -> list[dict[str, Any]]:
    """Check that every location or pointer in the knowledge store resolves.

    A `location` or `pointer` entry names what it points at in `resolves` (one path or a
    list; environment variables are expanded); each must exist.

    Returns:
        One finding per entry with no `resolves`, and per path that does not exist.
    """
    doc = (
        YAML(typ="safe").load(cfg.knowledge.read_text())
        if cfg.knowledge.exists()
        else {}
    )
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
                )
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
                    )
                )
    return out


def _naming_doc_findings(cfg: Config) -> list[dict[str, Any]]:
    """Check the repository-naming document against the config's naming patterns.

    Every naming pattern has a section in the document (its heading's first word is the
    pattern's name); every example in a section matches that section's pattern; every
    "`A` becomes `B`" is the tool's deprecated name of A; and "N days after deprecation"
    is the configured archive delay.

    Returns:
        One finding per disagreement.
    """
    loc = ((cfg.raw.get("naming") or {}).get("document")) or ""
    if not loc:
        return [
            _finding(
                "naming-doc", "-", "not-configured", "config naming.document is not set"
            )
        ]
    path = _resolve_location(cfg, str(loc))
    if not path.is_file():
        return [_finding("naming-doc", "-", "missing", f"{loc} ({path}) not found")]
    text = path.read_text()
    out = []
    sections = {
        m.group(1).split()[0].lower(): m.group(2)
        for m in re.finditer(r"(?m)^### (.+)\n((?:(?!^##).*\n?)*)", text)
    }
    for p in cfg.patterns:
        if p["name"] not in sections:
            out.append(
                _finding(
                    "naming-doc",
                    p["name"],
                    "pattern-undocumented",
                    f"naming pattern {p['name']} has no section in {path.name}",
                )
            )
    for sec, body in sections.items():
        ex = re.search(r"\*\*Examples:\*\*(.*)", body)
        for name in re.findall(r"`([^`]+)`", ex.group(1) if ex else ""):
            got = cfg.classify(name)
            if got is None or got["name"] != sec:
                out.append(
                    _finding(
                        "naming-doc",
                        name,
                        "example-mismatch",
                        f"{path.name} gives {name} as a {sec} example; the config's patterns "
                        f"classify it as {got['name'] if got else 'no pattern'}",
                    )
                )
    for a, b in re.findall(r"`([^`]+)` becomes `([^`]+)`", text):
        if b.startswith("deprecated-") and deprecated_name(a) != b:
            out.append(
                _finding(
                    "naming-doc",
                    a,
                    "deprecation-mismatch",
                    f"{path.name} says {a} becomes {b}; the tool makes it {deprecated_name(a)}",
                )
            )
    days = int((cfg.raw.get("deprecation") or {}).get("archive_after_days", 60))
    for n in re.findall(r"(\d+) days after deprecation", text):
        if int(n) != days:
            out.append(
                _finding(
                    "naming-doc",
                    "-",
                    "archive-delay-mismatch",
                    f"{path.name} says {n} days; the config archives after {days}",
                )
            )
    return out


def cmd_doctor(args: argparse.Namespace, cfg: Config) -> int:
    """Run every deterministic health check and report one findings list.

    With --fix, first run the repairs (`reconcile --fix`, `agents-sync`, `beads-fleet
    --fix`, then `deprecated-prs --fix`), each of which commits and pushes its own changes
    or closes the pull requests it finds. The checks are reconcile, agents-sync --check, the
    beads fleet audit, the beads fleet list and open pull requests in deprecated repos (in
    parallel, each its own process), the governance
    entries, the knowledge-store pointers and the repository-naming document.

    Returns:
        0 when no check reports a finding, else 1.
    """
    t0 = time.time()
    extra = ["--config", str(cfg.file)] + (["--no-cache"] if args.no_cache else [])
    repairs: dict[str, dict[str, Any]] = {}
    if args.fix:
        for name, argv in DOCTOR_REPAIRS.items():
            rc, data = _run_json(argv, extra)
            repairs[name] = {
                "exit": rc,
                "fixed": data.get("fixed"),
                "records": data.get("records"),
                "error": data.get("error"),
            }

    def one(item: tuple[str, list[str]]) -> tuple[str, int, dict[str, Any]]:
        name, argv = item
        return (name, *_run_json(argv, [] if name == "beads" else extra))

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(DOCTOR_CHECKS)) as ex:
        results = list(ex.map(one, DOCTOR_CHECKS.items()))
    findings: list[dict[str, Any]] = []
    exits: dict[str, int] = {}
    for name, rc, data in results:
        exits[name] = rc
        findings.extend(_doctor_findings(name, data))
    findings.extend(_governance_findings(cfg))
    findings.extend(_knowledge_findings(cfg))
    findings.extend(_naming_doc_findings(cfg))
    counts: dict[str, int] = {
        c: 0 for c in [*DOCTOR_CHECKS, "governance", "knowledge", "naming-doc"]
    }
    for f in findings:
        counts[f["check"]] = counts.get(f["check"], 0) + 1
    data = {
        "repairs": repairs,
        "findings": findings,
        "counts": counts,
        "exit_codes": exits,
        "open": len(findings),
        "elapsed_s": round(time.time() - t0, 1),
    }

    def text() -> str:
        lines = [f"{len(findings)} findings in {data['elapsed_s']}s"]
        lines.extend(
            f"  repair {n}: exit {r['exit']}"
            + (f", {r['fixed']} fixed" if r.get("fixed") is not None else "")
            + (f", {r['error']}" if r.get("error") else "")
            for n, r in repairs.items()
        )
        lines.extend(f"  {c}: {n}" for c, n in counts.items())
        lines.extend(
            f"  [{f['check']}/{f['kind']}] {f['subject']}: {f['detail']}"
            for f in findings
        )
        return "\n".join(lines)

    emit(args, data, text)
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
            + (f": {', '.join(res['files'])}" if res["files"] else "")
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
        "--no-cache", action="store_true", help="fetch and list GitHub even when fresh"
    )

    p = argparse.ArgumentParser(
        prog="polyrepo",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser(
        "reconcile", parents=[common], help="compare disk, GitHub and the manifest"
    )
    s.add_argument("--fix", action="store_true", help="repair every mechanical finding")
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="with --fix, report the fixes without running them",
    )
    s.add_argument("--no-fetch", action="store_true", help="skip git fetch")
    s.set_defaults(func=cmd_reconcile)

    s = sub.add_parser(
        "status", parents=[common], help="live git and GitHub state per repo"
    )
    s.add_argument(
        "repos", nargs="*", help="repo names or paths (default: every repo on disk)"
    )
    s.add_argument("--no-fetch", action="store_true", help="skip git fetch")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("list", parents=[common], help="list repos")
    s.add_argument("--group")
    s.add_argument("--lifecycle")
    s.add_argument("--space")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser(
        "search", parents=[common], help="find repos by record attribute"
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
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("inventory", parents=[common], help="every repo's full record")
    s.add_argument("--no-fetch", action="store_true", help="skip git fetch")
    s.add_argument(
        "--all",
        action="store_true",
        help="also every repo the manifest or GitHub has that is not on disk",
    )
    s.set_defaults(func=cmd_inventory)

    s = sub.add_parser(
        "purpose",
        parents=[common],
        help="record or confirm a repo's purpose at its current main",
    )
    s.add_argument("repo")
    s.add_argument("--text", help="the new purpose (omit to confirm the current one)")
    s.set_defaults(func=cmd_purpose)

    s = sub.add_parser("grep", parents=[common], help="rg across the repos on disk")
    s.add_argument("pattern")
    s.add_argument("--space", help="only this app space")
    s.add_argument("--repo", action="append", help="only this repo (repeatable)")
    s.add_argument("-i", "--ignore-case", action="store_true")
    s.add_argument("-F", "--fixed-strings", action="store_true")
    s.add_argument("-w", "--word", action="store_true")
    s.add_argument("-l", "--files", action="store_true", help="files with matches only")
    s.add_argument("--glob", action="append", help="rg --glob (repeatable)")
    s.set_defaults(func=cmd_grep)

    s = sub.add_parser(
        "rebase", parents=[common], help="rebase main on origin/main after a fetch"
    )
    s.add_argument("repos", nargs="*", help="repo names or paths")
    s.add_argument("--all", action="store_true", help="every repo on disk")
    s.set_defaults(func=cmd_rebase)

    s = sub.add_parser(
        "create", parents=[common], help="create a repo from a template, on GitHub too"
    )
    s.add_argument("name")
    s.add_argument("--space", required=True, help="the app space it belongs in")
    s.add_argument("--template", required=True, help="the Copier template")
    s.add_argument("--purpose", required=True, help="one line: what the repo is")
    s.add_argument("--lifecycle", default="active")
    s.add_argument(
        "--dir", help="folder inside the space (default: the config's placement)"
    )
    s.add_argument("--dry-run", action="store_true", help="check and render only")
    s.set_defaults(func=cmd_create)

    s = sub.add_parser(
        "deprecate",
        parents=[common],
        help="rename a repo deprecated-*, here and on GitHub, and close its open PRs",
    )
    s.add_argument("repo")
    s.add_argument("--dry-run", action="store_true", help="check and plan only")
    s.set_defaults(func=cmd_deprecate)

    s = sub.add_parser(
        "rename",
        parents=[common],
        help="rename a repo, here and on GitHub, and repoint the manifest",
    )
    s.add_argument("repo")
    s.add_argument("new_name")
    s.add_argument("--dry-run", action="store_true", help="check and plan only")
    s.set_defaults(func=cmd_rename)

    s = sub.add_parser(
        "agents-sync",
        parents=[common],
        help="write the shared AGENTS.md blocks into every repo",
    )
    s.add_argument("--check", action="store_true", help="report repos out of date")
    s.add_argument("--dry-run", action="store_true", help="same as --check")
    s.add_argument("--repo", action="append", help="only this repo (repeatable)")
    s.set_defaults(func=cmd_agents_sync)

    s = sub.add_parser(
        "templates-check",
        parents=[common],
        help="compare the templates with the repos built from them",
    )
    s.set_defaults(func=cmd_templates_check)

    s = sub.add_parser(
        "beads-fleet",
        parents=[common],
        help="check the beads fleet list (repos.additional) against the repos",
    )
    s.add_argument("--fix", action="store_true", help="correct the list")
    s.set_defaults(func=cmd_beads_fleet)

    s = sub.add_parser(
        "deprecated-prs",
        parents=[common],
        help="report open pull requests in deprecated- repos",
    )
    s.add_argument("--fix", action="store_true", help="close them")
    s.set_defaults(func=cmd_deprecated_prs)

    s = sub.add_parser(
        "doctor",
        parents=[common],
        help="every health check as one report; --fix runs the repairs first",
    )
    s.add_argument(
        "--fix",
        action="store_true",
        help="run every repair (reconcile, agents-sync, beads-fleet, deprecated-prs) first",
    )
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser(
        "commit",
        parents=[common],
        help="commit and push the steward's own files after a hand edit",
    )
    s.add_argument("--message", "-m", required=True, help="what changed")
    s.set_defaults(func=cmd_commit)
    return p


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
            print(json.dumps({"error": str(exc)}))
        else:
            print(f"polyrepo: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
