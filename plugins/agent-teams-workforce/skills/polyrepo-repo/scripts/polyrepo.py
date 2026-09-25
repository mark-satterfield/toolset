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
  polyrepo.py deprecate <repo> [--dry-run]
  polyrepo.py agents-sync [--check] [--dry-run] [--repo R ...]
  polyrepo.py templates-check
  polyrepo.py doctor

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
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

GIT_TIMEOUT = 60
FETCH_TIMEOUT = 45
WORKERS = 16
LIFECYCLES_INACTIVE = ("deprecated", "archived")
ENTRY_LISTS = ("repos", "deprecations")


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
    owner: str
    default_branch: str
    max_depth: int
    exclude_dirs: set[str]
    exclude_names: set[str]
    ttl: int
    owned: list[re.Pattern[str]]
    patterns: list[dict[str, Any]]
    raw: dict[str, Any] = dataclasses.field(default_factory=dict)

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
        cp = git(r.path, "fetch", "--quiet", "--prune", "origin", timeout=FETCH_TIMEOUT)
        if cp.returncode != 0:
            r.fetch_error = (cp.stderr.strip().splitlines() or ["fetch failed"])[-1]
    fh = r.path / ".git" / "FETCH_HEAD"
    if fh.exists():
        r.fetched_at = dt.datetime.fromtimestamp(fh.stat().st_mtime, dt.UTC).isoformat(
            timespec="seconds"
        )
    r.branch = git_out(r.path, "symbolic-ref", "--short", "-q", "HEAD") or "(detached)"
    porcelain = git_out(r.path, "status", "--porcelain=v1", "--untracked-files=normal")
    r.uncommitted = len([ln for ln in (porcelain or "").splitlines() if ln.strip()])
    log = git_out(r.path, "log", "-1", "--format=%H%x1f%cI%x1f%s")
    if log:
        r.head_sha, r.head_date, r.head_subject = log.split("\x1f", 2)
    b = cfg.default_branch
    r.main_sha = git_out(r.path, "rev-parse", "--verify", "-q", f"refs/heads/{b}")
    r.origin_main_sha = git_out(
        r.path, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{b}"
    )
    if r.main_sha and r.origin_main_sha:
        counts = git_out(
            r.path,
            "rev-list",
            "--left-right",
            "--count",
            f"refs/heads/{b}...refs/remotes/origin/{b}",
        )
        if counts:
            a, bh = counts.split()
            r.ahead, r.behind = int(a), int(bh)
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

    def _groups(self) -> list[CommentedMap]:
        return [g for g in self.doc.get("groups") or [] if isinstance(g, dict)]

    def _edges(self) -> list[CommentedMap]:
        rel = self.doc.get("relationships") or {}
        return [e for e in rel.get("dependencies") or [] if isinstance(e, dict)]

    def groups_of(self, name: str) -> list[str]:
        """Return the groups a repo is a member of.

        Returns:
            Group names.
        """
        return [g["name"] for g in self._groups() if name in (g.get("members") or [])]

    def _expand(self, ref: str) -> list[str]:
        if ref.startswith("group:"):
            gname = ref[len("group:") :]
            for g in self._groups():
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
        for e in self._edges():
            kind = str(e.get("kind", ""))
            src, dst = (
                self._expand(str(e.get("from", ""))),
                self._expand(str(e.get("to", ""))),
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
        """Append a new repo entry."""
        m = CommentedMap()
        m["name"] = name
        for k, v in fields.items():
            m[k] = v
        self.doc["repos"].append(m)
        self.dirty = True

    def set_field(self, name: str, key: str, value: Any) -> None:  # noqa: ANN401
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
        for g in self._groups():
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
        for g in self._groups():
            members = g.get("members")
            if members and old in members:
                members[members.index(old)] = new
        for e in self._edges():
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

        In the repo that holds the steward's own folder, commits that touch only that
        folder do not count: recording a purpose there commits the manifest, which would
        otherwise mark the purpose stale again at once.

        Returns:
            True when the purpose needs a recheck.
        """
        if not r or not r.main_sha:
            return False
        if not purpose_head:
            return True
        if purpose_head == r.main_sha:
            return False
        own = self.cfg.file.parent.resolve()
        if r.path != own and r.path not in own.parents:
            return True
        rel = own.relative_to(r.path).as_posix()
        cp = git(
            r.path,
            "diff",
            "--quiet",
            str(purpose_head),
            r.main_sha,
            "--",
            ".",
            f":(exclude){rel}",
        )
        return cp.returncode != 0

    def tracked_names(self) -> list[str]:
        """Every repo in scope: on disk, in the manifest, or a deprecated project repo on GitHub.

        Returns:
            Sorted names.
        """
        names = set(self.local) | set(self.manifest.entries())
        for n in self.gh.repos:
            p = self.cfg.classify(n)
            if self.cfg.is_owned(n) and p and p["kind"] == "deprecated":
                names.add(n)
        return sorted(names, key=str.lower)

    def record(self, name: str) -> dict[str, Any]:
        """Build a repo's full record: live facts plus the manifest's purpose, owns, groups, dependencies.

        Returns:
            The record.
        """
        r = self.local.get(name)
        e = self.manifest.entries().get(name) or {}
        g = self.gh.get(name)
        pat = self.cfg.classify(name)
        purpose_head = e.get("purpose_head")
        rec: dict[str, Any] = {
            "name": name,
            "space": r.space if r else self.cfg.expected_space(name),
            "path": str(r.path) if r else None,
            "lifecycle": self.lifecycle(name),
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
            "owns": list(e.get("owns") or []),
            "groups": self.manifest.groups_of(name),
            "dependencies": self.manifest.dependencies(name),
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
                        n,
                        {
                            "lifecycle": lc,
                            "remote_url": cfg.github_url(n),
                            "default_branch": cfg.default_branch,
                            **(
                                {"deprecated_on": today()} if lc == "deprecated" else {}
                            ),
                        },
                    ),
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
                action=lambda: man.add_entry(
                    name,
                    {
                        "lifecycle": lc,
                        "remote_url": cfg.github_url(name),
                        "default_branch": b,
                        **({"deprecated_on": today()} if lc == "deprecated" else {}),
                    },
                ),
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
                    action=lambda: must(
                        git(
                            r.path,
                            "remote",
                            "add",
                            "origin",
                            cfg.github_url(rec["name"]),
                        )
                    ),
                )
            )
        else:
            out.append(_create_on_github(st, name, r, has_origin=False))
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
                out.append(_create_on_github(st, name, r, has_origin=True))
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
                            action=lambda old=gh_name: _rename_github(st, r, old, name),
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
                        action=lambda n=gh_name: must(
                            git(
                                r.path, "remote", "set-url", "origin", cfg.github_url(n)
                            )
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

    return [
        Finding(
            "archive-due",
            name,
            f"deprecated {age} days ago ({start}); repos are archived {days} days after deprecation",
            fix=f"archive {cfg.owner}/{name} on GitHub and set lifecycle archived",
            action=act,
        )
    ]


def _create_on_github(st: State, name: str, r: LocalRepo, has_origin: bool) -> Finding:
    cfg = st.cfg
    url = cfg.github_url(name)
    if cfg.classify(name) is None:
        return Finding(
            "local-only",
            name,
            "no GitHub repo; the folder must be renamed to a valid name first",
        )

    def act() -> None:
        must(
            run(
                ["gh", "repo", "create", f"{cfg.owner}/{name}", "--private"],
                timeout=120,
            )
        )
        if has_origin:
            must(git(r.path, "remote", "set-url", "origin", url))
        else:
            must(git(r.path, "remote", "add", "origin", url))
        if r.main_sha:
            must(git(r.path, "push", "-u", "origin", cfg.default_branch, timeout=120))

    return Finding(
        "local-only",
        name,
        "no GitHub repo for this folder",
        fix=f"create the private GitHub repo {cfg.owner}/{name}, point origin at it, and push {cfg.default_branch}",
        action=act,
    )


def _rename_github(st: State, r: LocalRepo, old: str, new: str) -> None:
    cfg = st.cfg
    must(
        run(
            ["gh", "repo", "rename", new, "--repo", f"{cfg.owner}/{old}", "--yes"],
            timeout=120,
        )
    )
    must(git(r.path, "remote", "set-url", "origin", cfg.github_url(new)))


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
        except (GitFailedError, KeyError, ValueError) as exc:
            f.status = "failed"
            f.error = str(exc)
    if dry_run:
        return
    st.manifest.save()
    done = [f for f in ordered if f.status == "fixed"]
    if done:
        st.gh.invalidate()
        append_changelog(
            st.cfg,
            "polyrepo reconcile --fix",
            [f"{f.kind} {f.repo}: {f.fix}" for f in done],
        )


def today() -> str:
    """Return today's local date.

    Returns:
        The date as YYYY-MM-DD.
    """
    return dt.datetime.now().astimezone().date().isoformat()


def append_changelog(cfg: Config, title: str, lines: list[str]) -> None:
    """Append a dated section to the steward's changelog."""
    today = dt.datetime.now(dt.UTC).astimezone().date().isoformat()
    body = "\n".join(f"- {ln}" for ln in lines)
    text = f"\n## {today} — {title}\n{body}\n  - **Source:** `polyrepo`, verified live against disk and GitHub.\n"
    with cfg.changelog.open("a") as fh:
        fh.write(text)


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


def resolve_names(st: State, wanted: list[str]) -> list[str]:
    """Resolve repo names or paths given on the command line.

    Returns:
        Canonical names.

    Raises:
        PolyrepoError: when an argument names no known repo.
    """
    known = st.tracked_names()
    lower = {n.lower(): n for n in known}
    by_path = {r.path: n for n, r in st.local.items()}
    out = []
    for w in wanted:
        p = Path(w).expanduser()
        if p.exists():
            p = p.resolve()
            hit = next(
                (n for rp, n in by_path.items() if p == rp or rp in p.parents), None
            )
            if hit:
                out.append(hit)
                continue
        n = lower.get(w.lower())
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

    def text() -> str:
        lines = [
            f"{len(st.local)} repos on disk, {len(st.manifest.entries())} manifest entries, "
            f"{len(findings)} findings ({data['fixed']} fixed) in {data['elapsed_s']}s"
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
        return "\n".join(lines)

    emit(args, data, text)
    return 1 if open_ else 0


def cmd_status(args: argparse.Namespace, cfg: Config) -> int:
    """Report live git and GitHub state for the named repos, or all of them.

    Returns:
        0.
    """
    st = gather(cfg, fetch=not args.no_fetch, use_cache=not args.no_cache)
    names = (
        resolve_names(st, args.repos) if args.repos else sorted(st.local, key=str.lower)
    )
    recs = [st.record(n) for n in names]
    emit(args, {"repos": recs}, lambda: "\n".join(_status_line(r) for r in recs))
    return 0


def cmd_inventory(args: argparse.Namespace, cfg: Config) -> int:
    """Report the full record of every repo on disk; --all adds GitHub-only deprecated repos.

    Returns:
        0.
    """
    st = gather(cfg, fetch=not args.no_fetch, use_cache=not args.no_cache)
    names = st.tracked_names() if args.all else sorted(st.local, key=str.lower)
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
    recs = [st.record(n) for n in st.tracked_names()]
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


def _lookup(rec: dict[str, Any], attr: str) -> Any:  # noqa: ANN401
    cur: Any = rec
    for part in attr.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _matches(value: Any, op: str, want: str) -> bool:  # noqa: ANN401
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
    recs = [st.record(n) for n in st.tracked_names()]
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
    (name,) = resolve_names(st, [args.repo])
    r = st.local.get(name)
    if r is None or not r.main_sha:
        msg = f"{name} has no local {cfg.default_branch} to check a purpose against"
        raise PolyrepoError(msg)
    entries = st.manifest.entries()
    if name not in entries:
        st.manifest.add_entry(
            name, {"lifecycle": st.lifecycle(name), "remote_url": cfg.github_url(name)}
        )
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
    emit(args, data, lambda: f"{name}: purpose {what} at {r.main_sha[:12]}")
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
    lower = {n.lower(): n for n in local}
    picked: list[LocalRepo] = []
    for w in names or []:
        n = lower.get(w.lower())
        p = Path(w).expanduser()
        if n is None and p.exists():
            p = p.resolve()
            n = next(
                (k for k, r in local.items() if r.path == p or r.path in p.parents),
                None,
            )
        if n is None:
            msg = f"no repo named {w!r} on disk"
            raise PolyrepoError(msg)
        picked.append(local[n])
    if not names:
        picked = list(local.values())
    if space:
        picked = [r for r in picked if r.space == space]
    return sorted(picked, key=lambda r: r.name.lower())


def _last_line(cp: subprocess.CompletedProcess[str]) -> str:
    lines = (cp.stderr or cp.stdout or "").strip().splitlines()
    return lines[-1] if lines else f"exit {cp.returncode}"


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
    cp = git(r.path, "fetch", "--quiet", "--prune", "origin", timeout=FETCH_TIMEOUT)
    if cp.returncode != 0:
        return {**res, "status": "fetch-failed", "detail": _last_line(cp)}
    main = git_out(r.path, "rev-parse", "--verify", "-q", f"refs/heads/{b}")
    om = git_out(r.path, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{b}")
    if not main or not om:
        return {**res, "status": "no-main", "detail": f"no {b} or no origin/{b}"}
    counts = git_out(
        r.path,
        "rev-list",
        "--left-right",
        "--count",
        f"refs/heads/{b}...refs/remotes/origin/{b}",
    )
    ahead, behind = (int(x) for x in (counts or "0 0").split())
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


def _service_name(name: str) -> str:
    n = name.lower()
    return n[len("skillspoke-") :] if n.startswith("skillspoke-") else n


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
    data = {"service_name": _service_name(name), "repo_name": name}
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
    block, marker = _agents_block(cfg)
    agents = dest / "AGENTS.md"
    agents.write_text(
        _with_block(
            agents.read_text() if agents.exists() else None, block, name, marker
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
        must(
            run(
                ["gh", "repo", "create", f"{cfg.owner}/{name}", "--private"],
                timeout=120,
            )
        )
        must(git(dest, "remote", "add", "origin", cfg.github_url(name)))
        must(git(dest, "push", "-u", "origin", b, timeout=120))
    except GitFailedError as exc:
        res["error"] = str(exc)
        emit(
            args, res, lambda: f"{name}: created at {dest} but stopped: {res['error']}"
        )
        return 1
    man = Manifest(cfg.manifest)
    man.add_entry(
        name,
        {
            "lifecycle": args.lifecycle,
            "remote_url": cfg.github_url(name),
            "default_branch": b,
            "purpose": args.purpose.strip(),
            "purpose_head": git_out(dest, "rev-parse", "HEAD"),
        },
    )
    man.save()
    append_changelog(
        cfg,
        "polyrepo create",
        [
            f"{name}: created in {args.space} from the {args.template} template and pushed to {cfg.owner}/{name}"
        ],
    )
    GitHub(cfg, use_cache=True).invalidate()
    emit(args, res, lambda: f"{name}: created at {dest} and pushed to GitHub")
    return 0


# deprecate ------------------------------------------------------------------------------------


def deprecated_name(name: str) -> str:
    """Return the deprecated name of a repo: the deprecated- prefix, all lowercase.

    Returns:
        The new name.
    """
    return "deprecated-" + name.lower()


def _deprecate_plan(
    st: State, name: str
) -> tuple[str, dict[str, Any] | None, LocalRepo | None, Path | None, list[str]]:
    """Work out and check a deprecation before anything moves.

    Returns:
        (new name, GitHub record, local repo, new local path, steps).

    Raises:
        PolyrepoError: when the repo cannot be deprecated as it stands.
    """
    cfg = st.cfg
    if name.startswith("deprecated-"):
        msg = f"{name} is already deprecated"
        raise PolyrepoError(msg)
    new = deprecated_name(name)
    p = cfg.classify(new)
    if p is None or p["kind"] != "deprecated":
        msg = f"{new} matches no deprecated naming pattern"
        raise PolyrepoError(msg)
    if st.gh.get(new) is not None:
        msg = f"{cfg.owner}/{new} already exists on GitHub"
        raise PolyrepoError(msg)
    r = st.local.get(name)
    parsed = parse_github_url(r.origin_url) if r else None
    rec = st.gh.resolve(parsed[1] if parsed else name)
    steps = []
    if rec:
        steps.append(f"rename the GitHub repo {cfg.owner}/{rec['name']} to {new}")
    new_path = None
    if r:
        if r.fetch_error:
            msg = f"{name}: git fetch failed ({r.fetch_error}); cannot confirm main is pushed"
            raise PolyrepoError(msg)
        if r.ahead:
            msg = f"{name}: {cfg.default_branch} is {r.ahead} commit(s) ahead of origin; push it first"
            raise PolyrepoError(msg)
        new_path = r.path.with_name(new)
        if new_path.exists():
            msg = f"{new_path} already exists"
            raise PolyrepoError(msg)
        steps += [
            f"move {r.path} to {new_path}",
            f"point origin at {cfg.github_url(new)}",
        ]
        if (git_out(r.path, "worktree", "list", "--porcelain") or "").count(
            "worktree "
        ) > 1:
            steps.append("repair the repo's linked worktrees")
    steps.append(
        f"manifest: rename the entry to {new}, lifecycle deprecated, deprecated_on {today()}"
    )
    return new, rec, r, new_path, steps


def cmd_deprecate(args: argparse.Namespace, cfg: Config) -> int:
    """Deprecate a repo: rename it on GitHub and on disk with the deprecated- prefix, and date it.

    Returns:
        0 on success, 1 when a step failed part way.
    """
    st = gather(cfg, fetch=True, use_cache=not args.no_cache)
    (name,) = resolve_names(st, [args.repo])
    new, rec, r, new_path, steps = _deprecate_plan(st, name)
    res: dict[str, Any] = {
        "repo": name,
        "new_name": new,
        "dry_run": args.dry_run,
        "steps": steps,
    }
    if args.dry_run:
        emit(
            args,
            res,
            lambda: "\n".join(
                [f"dry run: deprecate {name} as {new}"] + [f"  {s}" for s in steps]
            ),
        )
        return 0
    done: list[str] = []
    try:
        if rec:
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
            r.path.rename(new_path)
            done.append(f"moved {r.path} to {new_path}")
            verb = "set-url" if r.origin_url else "add"
            must(git(new_path, "remote", verb, "origin", cfg.github_url(new)))
            must(git(new_path, "worktree", "repair"))
    except (GitFailedError, OSError) as exc:
        res.update(error=str(exc), done=done)
        if done:
            append_changelog(cfg, f"polyrepo deprecate {name} (stopped)", done)
        emit(args, res, lambda: f"{name}: stopped after {done}: {res['error']}")
        return 1
    man = st.manifest
    if name in man.entries():
        man.rename_entry(name, new)
    else:
        man.add_entry(new, {})
    man.set_field(new, "lifecycle", "deprecated")
    man.set_field(new, "deprecated_on", today())
    man.set_field(new, "remote_url", cfg.github_url(new))
    man.set_field(new, "default_branch", cfg.default_branch)
    man.set_field(new, "local_path", None)
    man.save()
    append_changelog(
        cfg,
        f"polyrepo deprecate {name}",
        [*done, f"manifest entry is now {new}, deprecated on {today()}"],
    )
    st.gh.invalidate()
    emit(args, res, lambda: f"{name}: deprecated as {new}")
    return 0


# agents-sync ----------------------------------------------------------------------------------


def _agents_block(cfg: Config) -> tuple[str, str]:
    """Return the shared AGENTS.md block, wrapped in its markers, and the marker name.

    Returns:
        (block, marker).

    Raises:
        PolyrepoError: when the block file is missing.
    """
    sc = cfg.raw.get("agents_sync") or {}
    f = cfg.setting_path(
        "agents_sync", "block_file", "../repositories/agents-shared-block.md"
    )
    if not f.is_file():
        msg = f"shared AGENTS.md block file {f} not found"
        raise PolyrepoError(msg)
    marker = str(sc.get("marker") or "SKILLSPOKE SHARED")
    note = str(sc.get("note") or "written by polyrepo agents-sync")
    body = f.read_text().strip()
    return f"<!-- BEGIN {marker}: {note} -->\n{body}\n<!-- END {marker} -->", marker


def _with_block(text: str | None, block: str, name: str, marker: str) -> str:
    """Put the block into AGENTS.md text: replace the marked copy, or append one.

    Returns:
        The new text.
    """
    if text is None:
        return f"# {name}\n\n{block}\n"
    rx = re.compile(
        rf"<!-- BEGIN {re.escape(marker)}\b.*?<!-- END {re.escape(marker)} -->", re.S
    )
    if rx.search(text):
        return rx.sub(lambda _m: block, text, count=1)
    return text.rstrip("\n") + "\n\n" + block + "\n"


def _commit_paths(repo: Path, paths: list[str], message: str) -> None:
    """Commit only these paths, re-staging once when a pre-commit hook rewrote them.

    Raises:
        GitFailedError: when the commit still fails.
    """
    must(git(repo, "add", "--", *paths))
    cp = git(repo, "commit", "-m", message, "--", *paths, timeout=300)
    if cp.returncode != 0:
        must(git(repo, "add", "--", *paths))
        must(git(repo, "commit", "-m", message, "--", *paths, timeout=300))


def _sync_one(
    cfg: Config, r: LocalRepo, block: str, marker: str, write: bool
) -> dict[str, Any]:
    f = r.path / "AGENTS.md"
    cur = f.read_text() if f.is_file() else None
    want = _with_block(cur, block, r.name, marker)
    if cur == want:
        state = "current"
    elif cur is None:
        state = "missing-file"
    elif f"<!-- BEGIN {marker}" in cur:
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
    if git_out(r.path, "status", "--porcelain", "--", "AGENTS.md"):
        return {
            **res,
            "status": "skipped",
            "detail": "AGENTS.md has uncommitted changes",
        }
    f.write_text(want)
    paths = ["AGENTS.md"]
    claude = r.path / "CLAUDE.md"
    if cur is None and not claude.exists() and not claude.is_symlink():
        claude.symlink_to("AGENTS.md")
        paths.append("CLAUDE.md")
    try:
        _commit_paths(
            r.path, paths, "docs(agents): sync the shared SkillSpoke instructions block"
        )
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
    """Write the shared block into every repo's AGENTS.md, committing and pushing each repo.

    Returns:
        0 when every repo is current (or was brought current and pushed), else 1.
    """
    block, marker = _agents_block(cfg)
    skip = set((cfg.raw.get("agents_sync") or {}).get("exclude") or [])
    repos = [
        r
        for r in _local_repos(cfg, args.repo)
        if r.name not in skip and not r.name.startswith("deprecated-")
    ]
    write = not args.check and not args.dry_run
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(lambda r: _sync_one(cfg, r, block, marker, write), repos))
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
    r: LocalRepo, tdir: Path, files: dict[str, str], answers: dict[str, Any]
) -> dict[str, Any]:
    """Render the template as this repo would have been rendered and compare file by file.

    Returns:
        {repo, files: {path: (state, repo commit time)}} or {repo, error}.
    """
    data = {k: str(v) for k, v in answers.items() if not k.startswith("_")} or {
        "service_name": _service_name(r.name),
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
    tdir: Path, members: list[tuple[LocalRepo, str, dict[str, Any]]], ignore: list[str]
) -> dict[str, Any]:
    files = _template_files(tdir, ignore)
    now = int(time.time())
    tdates = {rel: _commit_time(tdir, src) or now for rel, src in files.items()}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        compared = list(
            ex.map(lambda m: _compare_to_template(m[0], tdir, files, m[2]), members)
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
        _check_template(troot / t, members, ignore)
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


DOCTOR_CHECKS: dict[str, list[str]] = {
    "reconcile": ["reconcile"],
    "agents-sync": ["agents-sync", "--check"],
}


def _doctor_findings(check: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn one check's JSON output into doctor findings.

    Returns:
        One finding per open problem the check reported.
    """
    out: list[dict[str, Any]] = []
    if "error" in data:
        return [
            {"check": check, "subject": "-", "kind": "error", "detail": data["error"]}
        ]
    if check == "reconcile":
        out.extend(
            {
                "check": check,
                "subject": f["repo"],
                "kind": f["kind"],
                "detail": f["detail"],
            }
            for f in data.get("findings") or []
            if f.get("status") in {"open", "failed", "planned"}
        )
    elif check == "agents-sync":
        out.extend(
            {
                "check": check,
                "subject": r["repo"],
                "kind": r["state"],
                "detail": r.get("detail") or "shared AGENTS.md block not current",
            }
            for r in data.get("repos") or []
            if isinstance(r, dict) and r.get("state") != "current"
        )
    return out


def _governance_findings(cfg: Config) -> list[dict[str, Any]]:
    """Check that every manifest governance entry's location exists.

    Returns:
        One finding per entry whose location does not resolve.
    """
    plugin_root = Path(__file__).resolve().parents[3]
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin_root)}
    doc = Manifest(cfg.manifest).doc
    out = []
    for e in doc.get("governance") or []:
        if not isinstance(e, dict) or not e.get("location"):
            continue
        loc = re.sub(
            r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?",
            lambda m: env.get(m.group(1), m.group(0)),
            str(e["location"]),
        )
        target = Path(loc).expanduser()
        if not target.is_absolute():
            target = cfg.file.parent.parent / target
        if not target.exists():
            out.append(
                {
                    "check": "governance",
                    "subject": str(e.get("id") or e.get("name")),
                    "kind": "location-missing",
                    "detail": f"{e['location']} does not resolve ({target})",
                }
            )
    return out


def cmd_doctor(args: argparse.Namespace, cfg: Config) -> int:
    """Run every deterministic health check and report one findings list.

    The checks are reconcile and agents-sync --check (run in parallel, each as
    its own process of this script) and the governance locations. Judgment checks (knowledge-
    store pointers written as prose) belong to the polyrepo-doctor skill.

    Returns:
        0 when no check reports a finding, else 1.
    """
    t0 = time.time()
    extra = ["--json", "--config", str(cfg.file)]
    if args.no_cache:
        extra.append("--no-cache")

    def one(item: tuple[str, list[str]]) -> tuple[str, int, dict[str, Any]]:
        name, argv = item
        cp = run(
            [sys.executable, str(Path(__file__).resolve()), *argv, *extra], timeout=900
        )
        try:
            data = json.loads(cp.stdout) if cp.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {"error": f"unreadable output: {cp.stdout[:200]}"}
        if cp.returncode == 2 and "error" not in data:  # noqa: PLR2004
            data["error"] = _last_line(cp) or "exited 2"
        return name, cp.returncode, data

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(DOCTOR_CHECKS)) as ex:
        results = list(ex.map(one, DOCTOR_CHECKS.items()))
    findings: list[dict[str, Any]] = []
    exits: dict[str, int] = {}
    for name, rc, data in results:
        exits[name] = rc
        findings.extend(_doctor_findings(name, data))
    findings.extend(_governance_findings(cfg))
    counts: dict[str, int] = {c: 0 for c in [*DOCTOR_CHECKS, "governance"]}
    for f in findings:
        counts[f["check"]] = counts.get(f["check"], 0) + 1
    data = {
        "findings": findings,
        "counts": counts,
        "exit_codes": exits,
        "open": len(findings),
        "elapsed_s": round(time.time() - t0, 1),
    }

    def text() -> str:
        lines = [f"{len(findings)} findings in {data['elapsed_s']}s"]
        lines.extend(f"  {c}: {n}" for c, n in counts.items())
        lines.extend(
            f"  [{f['check']}/{f['kind']}] {f['subject']}: {f['detail']}"
            for f in findings
        )
        return "\n".join(lines)

    emit(args, data, text)
    return 1 if findings else 0


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
        help="also the manifest's and GitHub's repos that are not on disk",
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
        help="rename a repo deprecated-*, here and on GitHub",
    )
    s.add_argument("repo")
    s.add_argument("--dry-run", action="store_true", help="check and plan only")
    s.set_defaults(func=cmd_deprecate)

    s = sub.add_parser(
        "agents-sync",
        parents=[common],
        help="write the shared AGENTS.md block into every repo",
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
        "doctor",
        parents=[common],
        help="reconcile, agents-sync --check and governance, as one report",
    )
    s.set_defaults(func=cmd_doctor)
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
