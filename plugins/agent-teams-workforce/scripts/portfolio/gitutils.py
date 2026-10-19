"""Git utilities for the workflow scripts: git facts and mechanical git steps, printed as one JSON object.

A workflow script runs this through relayrun.py (`run -- python3 gitutils.py ...`), so what it
prints reaches the script checked. Every command prints one JSON object on stdout and exits 0;
a command that cannot do its work prints `{"error": ...}` and exits 2. Nothing here judges
anything: each command runs fixed git commands and reports what git printed.

Commands:

    facts --path P [--repo R] [--base B] [--fetch-base] [--unset-base-upstream]
        The raw facts of the tree at P: whether it is a git tree, its toplevel, git-dir and
        git-common-dir (absolute), branch (`HEAD` when detached), head commit, whether it is
        dirty and how many status lines, its upstream, and whether it is a linked worktree.
        With R, the repository's own git-common-dir, whether P belongs to it, and the
        repository's default branch. With B, how many commits HEAD has that origin/B lacks
        (`--fetch-base` fetches origin B first; `--unset-base-upstream` unsets an upstream
        that is origin/B, so nothing pushes to the default branch).
    provision --repo R --branch B (--name N | --path P) [--from-origin]
        Reuse the worktree registered for branch B or at P, or cut one at P on B from
        origin/<default>. A worktree lives inside its own repository: P must be
        R/.worktrees/<name>, and a reused tree found anywhere else is moved to P. `--name N`
        places the tree at R/.worktrees/N, so a caller names the tree and never writes the
        path. `--from-origin` stands the tree on the existing remote branch origin/B (a pull
        request's head, for example) instead of cutting B from the default branch; it fails
        when origin/B does not exist. A reused tree is left as it is. Reports the tree, its
        branch, whether it was reused, the default branch, the git-common-dir and what was
        worked around (`blocked`).
    hash-files --tree T [FILE ...]
        The git blob hash of each FILE in T (`missing` when it is not a file), and
        `treeDigest`: the SHA-256 of HEAD, the status and the content of every changed or
        untracked file, which changes exactly when the work tree changes.
    snapshot --tree T
        `git add -A` then `git write-tree`: the tree id the work tree can be restored to.
    changed --tree T --since ID
        `git add -A`, then every path whose staged content differs from the tree ID.
    restore --tree T --to ID
        Put the work tree back at the tree ID, documentation excepted (.md, .mdx, .rst, .adoc,
        anything under docs/), and report whether only documentation now differs from it.
    cleanup-merged-pr PR --repo R [--branch] [--wait SECONDS]
        Clean up after the pull request PR of the clone R (whose origin is the PR's GitHub
        repository). Reads the PR's state and head branch with gh; an OPEN PR is read again
        every 60 seconds until it is MERGED or CLOSED or SECONDS run out. MERGED: the linked
        worktree on the head branch is removed (`git worktree remove --force`, since anything
        left in a merged PR's tree is a leftover), then `git worktree prune`; with `--branch`
        the local branch is deleted too (`git branch -D`, since a squash-merged branch is
        never an ancestor of main). CLOSED, or still OPEN after the wait: nothing is deleted.
        The primary working tree, main, the default branch and the branch the primary tree
        has checked out are never touched. Reports the state, what was removed, and every
        failure with git's exact message; it exits 0 whatever the PR's state, and 2 only
        when it could not run (gh missing, origin naming no GitHub repository, gh failing).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs the resolved git executable with a separate argv and no shell.
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

DOC_SUFFIXES: Final[tuple[str, ...]] = (".md", ".mdx", ".rst", ".adoc")
WORKTREES_DIRNAME: Final[str] = ".worktrees"
POLL_INTERVAL_SECONDS: Final[int] = 60
PR_ENDED: Final[frozenset[str]] = frozenset({"MERGED", "CLOSED"})
GITHUB_URL: Final[re.Pattern[str]] = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?/?$")


class GitError(Exception):
    """A git command this script needs failed."""


class TreeFacts(TypedDict):
    """The raw facts of one tree, and what the `facts` command adds to them."""

    path: str
    exists: bool
    isGitTree: bool
    toplevel: NotRequired[str]
    gitDir: NotRequired[str | None]
    gitCommonDir: NotRequired[str | None]
    isLinkedWorktree: NotRequired[bool]
    branch: NotRequired[str | None]
    head: NotRequired[str | None]
    dirty: NotRequired[bool]
    statusLines: NotRequired[int]
    upstream: NotRequired[str | None]
    upstreamIsBase: NotRequired[bool]
    base: NotRequired[str]
    aheadOfBase: NotRequired[int | None]
    repo: NotRequired[str]
    repoGitCommonDir: NotRequired[str | None]
    sameRepository: NotRequired[bool]
    defaultBranch: NotRequired[str | None]
    notes: NotRequired[list[str]]


class Worktree(TypedDict):
    """One worktree `git worktree list --porcelain` registers."""

    worktree: str
    branch: str | None


class ProvisionResult(TypedDict):
    """What the `provision` command established."""

    ok: bool
    worktree: str
    branch: str
    reused: bool
    defaultBranch: str
    gitCommonDir: str | None
    blocked: list[str]


class DigestState(TypedDict):
    """What the `hash-files` tree digest is computed over."""

    head: str | None
    status: list[str]
    content: dict[str, str]


class HashFilesResult(TypedDict):
    """The blob hashes and the work tree digest the `hash-files` command reports."""

    files: dict[str, str]
    treeDigest: str
    changedPaths: int


class SnapshotResult(TypedDict):
    """The tree id the `snapshot` command recorded."""

    tree: str


class ChangedResult(TypedDict):
    """The paths the `changed` command found differing from a snapshot."""

    changedFiles: list[str]


class RestoreResult(TypedDict):
    """Whether the `restore` command left only documentation differing from a snapshot."""

    restored: bool
    remaining: list[str]
    snapshot: str


class PullRequest(TypedDict):
    """A pull request's state and head branch, as gh reports them."""

    state: str
    branch: str


class CleanupResult(TypedDict):
    """What the `cleanup-merged-pr` command found and removed."""

    pr: int
    repo: str
    state: str
    branch: str
    waitedSeconds: int
    removedWorktree: str | None
    deletedBranch: str | None
    notes: list[str]
    failures: list[str]


class ErrorResult(TypedDict):
    """The payload a command that could not do its work prints."""

    error: str
    command: str


type CommandResult = (
    TreeFacts | ProvisionResult | HashFilesResult | SnapshotResult | ChangedResult | RestoreResult | CleanupResult
)


def failure_message(tree: str, argv: Sequence[str], done: subprocess.CompletedProcess[str]) -> str:
    """Describe a git command that exited non-zero.

    Args:
        tree: The directory git ran in.
        argv: The git arguments.
        done: The completed process.

    Returns:
        The message, naming the command, the tree, the exit status and what git printed.

    """
    detail: str = (done.stderr or done.stdout).strip()
    return f"git {' '.join(argv)} in {tree} exited {done.returncode}: {detail}"


def git(tree: str, *argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run one git command in a tree.

    Args:
        tree: The directory git runs in (`git -C`).
        *argv: The git arguments.
        check: Raise GitError on a non-zero exit.

    Returns:
        The completed process, text mode.

    Raises:
        GitError: When git is not on PATH, or when check is set and git exits non-zero.

    """
    executable: str | None = shutil.which("git")
    if executable is None:
        missing: str = "the git executable is not on PATH"
        raise GitError(missing)
    done: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved git executable and separate argv; shell disabled.
        [executable, "-C", tree, *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and done.returncode != 0:
        raise GitError(failure_message(tree, argv, done))
    return done


def out(tree: str, *argv: str) -> str | None:
    """Return the stripped stdout of a git command, or None when it fails.

    Args:
        tree: The directory git runs in.
        *argv: The git arguments.

    Returns:
        The output, or None.

    """
    done: subprocess.CompletedProcess[str] = git(tree, *argv, check=False)
    return done.stdout.strip() if done.returncode == 0 else None


def is_doc(path: str) -> bool:
    """Whether a path is documentation, which a restore leaves alone.

    Args:
        path: A repository-relative path.

    Returns:
        True for a documentation path.

    """
    return path.lower().endswith(DOC_SUFFIXES) or path.startswith("docs/") or "/docs/" in path


def absolute(tree: str, value: str | None) -> str | None:
    """Make a git path absolute against the tree.

    Args:
        tree: The tree git printed it for.
        value: The path git printed.

    Returns:
        The real absolute path, or None.

    """
    if not value:
        return None
    joined: str = value if Path(value).is_absolute() else str(Path(tree) / value)
    return os.path.realpath(joined)


def default_branch(repo: str) -> str | None:
    """Find the repository's default branch: origin/HEAD, else main, else master.

    Args:
        repo: The repository.

    Returns:
        The branch name, or None.

    """
    head: str | None = out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head.removeprefix("origin/")
    for name in ("main", "master"):
        for ref in (f"refs/heads/{name}", f"refs/remotes/origin/{name}"):
            if out(repo, "rev-parse", "--verify", "--quiet", ref):
                return name
    return None


def status_lines(tree: str) -> list[str]:
    """Return the `git status --porcelain` lines of a tree.

    Args:
        tree: The tree.

    Returns:
        The lines.

    Raises:
        GitError: When git status fails.

    """
    argv: tuple[str, ...] = ("status", "--porcelain")
    done: subprocess.CompletedProcess[str] = git(tree, *argv, check=False)
    if done.returncode != 0:
        raise GitError(failure_message(tree, argv, done))
    return [line for line in done.stdout.splitlines() if line.strip()]


def tree_facts(path: str) -> TreeFacts:
    """Read the raw facts of one tree.

    Args:
        path: The tree.

    Returns:
        The facts; `isGitTree` false when git does not know the path.

    """
    if not Path(path).is_dir():
        return {"path": path, "exists": False, "isGitTree": False}
    top: str | None = out(path, "rev-parse", "--show-toplevel")
    if top is None:
        return {"path": path, "exists": True, "isGitTree": False}
    git_dir: str | None = absolute(path, out(path, "rev-parse", "--git-dir"))
    common: str | None = absolute(path, out(path, "rev-parse", "--git-common-dir"))
    lines: list[str] = status_lines(path)
    return {
        "path": path,
        "exists": True,
        "isGitTree": True,
        "toplevel": os.path.realpath(top),
        "gitDir": git_dir,
        "gitCommonDir": common,
        "isLinkedWorktree": bool(git_dir and common and git_dir != common),
        "branch": out(path, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": out(path, "rev-parse", "HEAD"),
        "dirty": bool(lines),
        "statusLines": len(lines),
        "upstream": out(
            path,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{u}",
        ),
    }


def cmd_facts(args: argparse.Namespace) -> TreeFacts:
    """Run the `facts` command.

    Args:
        args: The parsed arguments.

    Returns:
        The facts.

    """
    notes: list[str] = []
    path: str = args.path
    base: str = args.base
    repo: str = args.repo
    if base and args.fetch_base and Path(path).is_dir():
        fetched: subprocess.CompletedProcess[str] = git(path, "fetch", "origin", base, check=False)
        if fetched.returncode != 0:
            notes.append(
                f"git fetch origin {base} failed: {fetched.stderr.strip()}",
            )
    facts: TreeFacts = tree_facts(path)
    if base and facts.get("isGitTree"):
        base_ref: str = f"origin/{base}"
        facts["upstreamIsBase"] = facts.get("upstream") == base_ref
        if facts["upstreamIsBase"] and args.unset_base_upstream:
            git(path, "branch", "--unset-upstream")
            notes.append(f"the branch tracked {base_ref}; its upstream was unset")
            facts["upstream"] = None
        ahead: str | None = out(path, "rev-list", "--count", f"{base_ref}..HEAD")
        facts["base"] = base
        facts["aheadOfBase"] = int(ahead) if ahead is not None and ahead.isdigit() else None
    if repo:
        repo_common: str | None = absolute(
            repo,
            out(repo, "rev-parse", "--git-common-dir"),
        )
        facts["repo"] = repo
        facts["repoGitCommonDir"] = repo_common
        facts["sameRepository"] = bool(
            repo_common and repo_common == facts.get("gitCommonDir"),
        )
        facts["defaultBranch"] = default_branch(repo) if repo_common else None
    facts["notes"] = notes
    return facts


def registered_worktrees(repo: str) -> list[Worktree]:
    """List the worktrees `git worktree list --porcelain` registers.

    Args:
        repo: The repository.

    Returns:
        One {worktree, branch} per registered tree (branch without refs/heads/, or None).

    """
    trees: list[Worktree] = []
    for block in git(repo, "worktree", "list", "--porcelain").stdout.split("\n\n"):
        worktree: str | None = None
        branch: str | None = None
        for line in block.splitlines():
            if line.startswith("worktree "):
                worktree = line[len("worktree ") :]
            elif line.startswith("branch "):
                branch = line[len("branch ") :].removeprefix("refs/heads/")
        if worktree:
            trees.append({"worktree": worktree, "branch": branch})
    return trees


def cut_worktree(
    repo: str,
    branch: str,
    path: str,
    default: str,
    blocked: list[str],
) -> None:
    """Fetch, fast-forward the main tree when it is safe, and add the worktree.

    Args:
        repo: The repository.
        branch: The feature branch.
        path: Where the worktree goes.
        default: The default branch.
        blocked: Where to note what was worked around.

    Raises:
        GitError: When the worktree cannot be added.

    """
    fetched: subprocess.CompletedProcess[str] = git(repo, "fetch", "origin", default, check=False)
    if fetched.returncode != 0:
        blocked.append(f"git fetch origin {default} failed: {fetched.stderr.strip()}")
    origin_ref: str = f"origin/{default}"
    has_origin: str | None = out(
        repo,
        "rev-parse",
        "--verify",
        "--quiet",
        f"refs/remotes/{origin_ref}",
    )
    if has_origin and out(repo, "rev-parse", "--abbrev-ref", "HEAD") == default:
        behind: str | None = out(repo, "rev-list", "--count", f"HEAD..{origin_ref}")
        if not status_lines(repo) and behind and behind.isdigit() and int(behind) > 0:
            merged: subprocess.CompletedProcess[str] = git(repo, "merge", "--ff-only", origin_ref, check=False)
            if merged.returncode != 0:
                blocked.append(
                    f"the main tree could not fast-forward: {merged.stderr.strip()}",
                )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    add: tuple[str, ...]
    if out(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"):
        add = ("worktree", "add", path, branch)
    else:
        start: str = origin_ref if has_origin else default
        if not has_origin:
            blocked.append(
                f"{origin_ref} does not exist; the branch was cut from the local {default}",
            )
        add = ("worktree", "add", "--no-track", "-b", branch, path, start)
    added: subprocess.CompletedProcess[str] = git(repo, *add, check=False)
    if added.returncode != 0:
        raise GitError(failure_message(repo, add, added))


def checkout_from_origin(repo: str, branch: str, path: str, blocked: list[str]) -> None:
    """Fetch origin/<branch> and add the worktree on that existing remote branch.

    A local branch of that name is checked out as it is, and a difference from origin is
    noted; otherwise the local branch is created from origin/<branch>, tracking it.

    Args:
        repo: The repository.
        branch: The remote branch, for example a pull request's head.
        path: Where the worktree goes.
        blocked: Where to note what was worked around.

    Raises:
        GitError: When origin/<branch> cannot be fetched or the worktree cannot be added.

    """
    fetched: subprocess.CompletedProcess[str] = git(repo, "fetch", "origin", branch, check=False)
    remote_ref: str = f"origin/{branch}"
    remote_head: str | None = out(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/{remote_ref}")
    if not remote_head:
        msg: str = f"{remote_ref} does not exist: git fetch origin {branch} said {fetched.stderr.strip()!r}"
        raise GitError(msg)
    if fetched.returncode != 0:
        blocked.append(f"git fetch origin {branch} failed; using the {remote_ref} already fetched")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    add: tuple[str, ...]
    local_head: str | None = out(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    if local_head:
        add = ("worktree", "add", path, branch)
        if local_head != remote_head:
            blocked.append(f"the local {branch} ({local_head[:12]}) differs from {remote_ref} ({remote_head[:12]})")
    else:
        add = ("worktree", "add", "--track", "-b", branch, path, remote_ref)
    added: subprocess.CompletedProcess[str] = git(repo, *add, check=False)
    if added.returncode != 0:
        raise GitError(failure_message(repo, add, added))


def planned_path(repo: str, name: str | None, path: str | None) -> str:
    """Return where the worktree belongs: R/.worktrees/<name>, from --name or --path.

    Args:
        repo: The repository.
        name: The tree's name under R/.worktrees, or None when a path is given.
        path: The tree's full path, or None when a name is given.

    Returns:
        The path.

    Raises:
        GitError: When the name is not one path component, or the path is not R/.worktrees/<name>.

    """
    home: Path = Path(repo).resolve() / WORKTREES_DIRNAME
    if name is not None:
        if name in {"", ".", ".."} or Path(name).name != name:
            msg: str = f"--name {name!r} is not a single directory name"
            raise GitError(msg)
        return str(home / name)
    planned: str = path or ""
    if Path(planned).resolve().parent != home:
        msg = f"{planned} is not {home}/<name>; a worktree lives inside its own repository"
        raise GitError(msg)
    return planned


def require_default_branch(repo: str) -> str:
    """Return the repository's default branch, which provisioning cannot do without.

    Args:
        repo: The repository.

    Returns:
        The branch name.

    Raises:
        GitError: When the repository has no origin/HEAD, main or master.

    """
    default: str | None = default_branch(repo)
    if not default:
        msg: str = f"{repo} has no origin/HEAD, main or master to find its default branch by"
        raise GitError(msg)
    return default


def reuse_worktree(repo: str, branch: str, path: str, home: Path, blocked: list[str]) -> str | None:
    """Find the worktree registered for the branch or at the path, moving it under home.

    Args:
        repo: The repository.
        branch: The feature branch.
        path: Where the worktree belongs.
        home: The repository's worktrees directory.
        blocked: Where to note what was worked around.

    Returns:
        The reused tree (the path when it was moved there), or None when none is registered.

    """
    planned: str = os.path.realpath(path)
    reused_tree: str | None = next(
        (
            t["worktree"]
            for t in registered_worktrees(repo)
            if t["branch"] == branch or os.path.realpath(t["worktree"]) == planned
        ),
        None,
    )
    if reused_tree and Path(reused_tree).resolve().parent != home:
        moved: subprocess.CompletedProcess[str] = git(repo, "worktree", "move", reused_tree, path, check=False)
        if moved.returncode == 0:
            return path
        blocked.append(
            f"{reused_tree} could not be moved to {path}: {moved.stderr.strip()}",
        )
    return reused_tree


def cmd_provision(args: argparse.Namespace) -> ProvisionResult:
    """Run the `provision` command.

    Args:
        args: The parsed arguments.

    Returns:
        What was established.

    """
    repo: str = args.repo
    branch: str = args.branch
    path: str = planned_path(repo, args.name, args.path)
    blocked: list[str] = []
    home: Path = Path(repo).resolve() / WORKTREES_DIRNAME
    default: str = require_default_branch(repo)
    reused_tree: str | None = reuse_worktree(repo, branch, path, home, blocked)
    tree: str = reused_tree or path
    if not reused_tree and args.from_origin:
        checkout_from_origin(repo, branch, path, blocked)
    elif not reused_tree:
        cut_worktree(repo, branch, path, default, blocked)
    facts: TreeFacts = tree_facts(tree)
    on: str = facts.get("branch") or ""
    ok: bool = bool(facts.get("isGitTree")) and on not in {"", "HEAD", default}
    if not ok:
        blocked.append(
            f"the tree {tree} is on {on or 'no branch'!r}, not a feature branch",
        )
    return {
        "ok": ok,
        "worktree": os.path.realpath(tree) if Path(tree).is_dir() else tree,
        "branch": on,
        "reused": reused_tree is not None,
        "defaultBranch": default,
        "gitCommonDir": facts.get("gitCommonDir"),
        "blocked": blocked,
    }


def blob_hash(tree: str, rel: str) -> str:
    """Return the git blob hash of one file, or `missing`.

    Args:
        tree: The tree.
        rel: The path, relative to the tree.

    Returns:
        The hash, or "missing".

    """
    if not (Path(tree) / rel).is_file():
        return "missing"
    return git(tree, "hash-object", "--", rel).stdout.strip()


def cmd_hash_files(args: argparse.Namespace) -> HashFilesResult:
    """Run the `hash-files` command.

    Args:
        args: The parsed arguments.

    Returns:
        The hashes and the tree digest.

    """
    tree: str = args.tree
    names: list[str] = args.files
    files: dict[str, str] = {f: blob_hash(tree, f) for f in names}
    raw: str = git(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    entries: list[str] = [e for e in raw.split("\0") if e]
    changed: set[str] = set()
    origin_next: bool = False
    for e in entries:
        if origin_next:
            origin_next = False
            continue
        changed.add(e[3:])
        origin_next = e[:1] in {"R", "C"}
    state: DigestState = {
        "head": out(tree, "rev-parse", "HEAD"),
        "status": entries,
        "content": {p: blob_hash(tree, p) for p in sorted(changed)},
    }
    digest: str = hashlib.sha256(
        json.dumps(state, sort_keys=True).encode("utf-8"),
    ).hexdigest()
    return {"files": files, "treeDigest": digest, "changedPaths": len(changed)}


def cmd_snapshot(args: argparse.Namespace) -> SnapshotResult:
    """Run the `snapshot` command.

    Args:
        args: The parsed arguments.

    Returns:
        The tree id.

    """
    tree: str = args.tree
    git(tree, "add", "-A")
    return {"tree": git(tree, "write-tree").stdout.strip()}


def differing(tree: str, snapshot: str) -> list[tuple[str, str]]:
    """List the (status, path) pairs where the staged tree differs from a snapshot.

    Args:
        tree: The tree.
        snapshot: The snapshot tree id.

    Returns:
        The pairs.

    """
    git(tree, "add", "-A")
    text: str = git(
        tree,
        "diff",
        "--cached",
        "--no-renames",
        "--name-status",
        snapshot,
    ).stdout
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        status, _, path = line.partition("\t")
        if path:
            pairs.append((status.strip(), path))
    return pairs


def cmd_changed(args: argparse.Namespace) -> ChangedResult:
    """Run the `changed` command.

    Args:
        args: The parsed arguments.

    Returns:
        The paths that differ from the snapshot.

    """
    tree: str = args.tree
    since: str = args.since
    return {"changedFiles": sorted({p for _, p in differing(tree, since)})}


def cmd_restore(args: argparse.Namespace) -> RestoreResult:
    """Run the `restore` command.

    Args:
        args: The parsed arguments.

    Returns:
        Whether only documentation now differs from the snapshot, and what still does.

    """
    tree: str = args.tree
    snapshot: str = args.to
    for status, path in differing(tree, snapshot):
        if is_doc(path):
            continue
        if status == "A":
            git(tree, "rm", "-f", "-q", "--", path)
        else:
            git(
                tree,
                "restore",
                f"--source={snapshot}",
                "--staged",
                "--worktree",
                "--",
                path,
            )
    remaining: list[str] = [p for _, p in differing(tree, snapshot) if not is_doc(p)]
    return {"restored": not remaining, "remaining": remaining, "snapshot": snapshot}


def gh_pr(repo: str, pr: int) -> PullRequest:
    """Read a pull request's state and head branch with gh, in the repository's clone.

    Args:
        repo: The local clone whose origin is the pull request's GitHub repository.
        pr: The pull request number.

    Returns:
        The state and head branch.

    Raises:
        GitError: When gh is not on PATH, origin names no GitHub repository, or gh fails.

    """
    executable: str | None = shutil.which("gh")
    if executable is None:
        missing: str = "the gh executable is not on PATH"
        raise GitError(missing)
    slug: str = github_slug(repo)
    argv: list[str] = [executable, "pr", "view", str(pr), "--repo", slug, "--json", "state,headRefName"]
    done: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved gh executable and separate argv; shell disabled.
        argv,
        capture_output=True,
        text=True,
        check=False,
        cwd=repo,
    )
    if done.returncode != 0:
        msg: str = f"gh pr view {pr} --repo {slug} exited {done.returncode}: {(done.stderr or done.stdout).strip()}"
        raise GitError(msg)
    try:
        data: dict[str, str] = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        msg = f"gh pr view {pr} --repo {slug} printed no JSON: {exc}"
        raise GitError(msg) from exc
    return {"state": str(data.get("state", "")), "branch": str(data.get("headRefName", ""))}


def github_slug(repo: str) -> str:
    """Return the OWNER/REPO that the clone's origin names on GitHub.

    Args:
        repo: The local clone.

    Returns:
        OWNER/REPO.

    Raises:
        GitError: When origin is missing or names no GitHub repository.

    """
    url: str = git(repo, "remote", "get-url", "origin").stdout.strip()
    match: re.Match[str] | None = GITHUB_URL.search(url)
    if match is None:
        msg: str = f"origin of {repo} is {url!r}, which names no GitHub repository"
        raise GitError(msg)
    return f"{match.group('owner')}/{match.group('name')}"


def await_pr_end(repo: str, pr: int, wait: int) -> tuple[PullRequest, int]:
    """Read the pull request until it is MERGED or CLOSED, or the wait runs out.

    A read that fails while wait remains is retried at the next poll; the last read must succeed.

    Args:
        repo: The local clone.
        pr: The pull request number.
        wait: How many seconds an OPEN pull request is waited for (0 reads once).

    Returns:
        The last state read and the seconds waited.

    Raises:
        GitError: When the last read fails.

    """
    waited: int = 0
    while True:
        try:
            current: PullRequest = gh_pr(repo, pr)
        except GitError:
            if waited >= wait:
                raise
        else:
            if current["state"] in PR_ENDED or waited >= wait:
                return current, waited
        time.sleep(POLL_INTERVAL_SECONDS)
        waited += POLL_INTERVAL_SECONDS


def protected_branches(repo: str, trees: list[Worktree]) -> set[str]:
    """Return the branches a cleanup never touches: main, the default branch, the primary tree's branch.

    Args:
        repo: The repository.
        trees: Its registered worktrees, the primary tree first.

    Returns:
        The branch names.

    """
    names: set[str] = {"main"}
    default: str | None = default_branch(repo)
    if default:
        names.add(default)
    primary: str | None = trees[0]["branch"] if trees else None
    if primary:
        names.add(primary)
    return names


def remove_tree(repo: str, branch: str, trees: list[Worktree], result: CleanupResult) -> bool:
    """Remove the linked worktree on the branch with `git worktree remove --force`.

    Args:
        repo: The repository.
        branch: The pull request's head branch.
        trees: The registered worktrees, the primary tree first.
        result: Where what was removed, skipped or failed is recorded.

    Returns:
        False when a tree stands on the branch and was not removed.

    """
    primary: str = os.path.realpath(trees[0]["worktree"]) if trees else ""
    tree: str | None = next((t["worktree"] for t in trees if t["branch"] == branch), None)
    if tree is None:
        result["notes"].append(f"no worktree stands on {branch}")
        return True
    if os.path.realpath(tree) == primary or not tree_facts(tree).get("isLinkedWorktree", False):
        result["notes"].append(f"{tree} is not a linked worktree; nothing deleted")
        return False
    removed: subprocess.CompletedProcess[str] = git(repo, "worktree", "remove", "--force", tree, check=False)
    if removed.returncode != 0:
        result["failures"].append(failure_message(repo, ("worktree", "remove", "--force", tree), removed))
        return False
    result["removedWorktree"] = tree
    return True


def delete_branch(repo: str, branch: str, result: CleanupResult) -> None:
    """Delete the local branch with `git branch -D`, since a squash-merged branch is never an ancestor of main.

    Args:
        repo: The repository.
        branch: The pull request's head branch.
        result: Where what was deleted or failed is recorded.

    """
    if not out(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"):
        result["notes"].append(f"no local branch {branch}")
        return
    deleted: subprocess.CompletedProcess[str] = git(repo, "branch", "-D", branch, check=False)
    if deleted.returncode != 0:
        result["failures"].append(failure_message(repo, ("branch", "-D", branch), deleted))
        return
    result["deletedBranch"] = branch


def clean_merged(repo: str, branch: str, delete: bool, result: CleanupResult) -> None:
    """Remove a merged pull request's worktree, prune, and with delete its local branch.

    Args:
        repo: The repository.
        branch: The pull request's head branch.
        delete: Whether the local branch is deleted too.
        result: Where the outcome is recorded.

    """
    trees: list[Worktree] = registered_worktrees(repo)
    if not branch or branch in protected_branches(repo, trees):
        named: str = branch or "no branch"
        result["notes"].append(f"{named} is main, the default branch or the primary tree's branch; nothing deleted")
        return
    tree_gone: bool = remove_tree(repo, branch, trees, result)
    pruned: subprocess.CompletedProcess[str] = git(repo, "worktree", "prune", check=False)
    if pruned.returncode != 0:
        result["failures"].append(failure_message(repo, ("worktree", "prune"), pruned))
    if delete and tree_gone:
        delete_branch(repo, branch, result)
    elif delete:
        result["notes"].append(f"the branch {branch} was kept because its worktree was not removed")


def cmd_cleanup_merged_pr(args: argparse.Namespace) -> CleanupResult:
    """Run the `cleanup-merged-pr` command.

    Args:
        args: The parsed arguments.

    Returns:
        The pull request's state and what was removed.

    Raises:
        GitError: When --wait is negative or the repository is not a git tree.

    """
    repo: str = args.repo
    pr: int = args.pr
    wait: int = args.wait
    if wait < 0:
        msg: str = f"--wait must not be negative, got {wait}"
        raise GitError(msg)
    if out(repo, "rev-parse", "--git-common-dir") is None:
        msg = f"{repo} is not a git repository"
        raise GitError(msg)
    current, waited = await_pr_end(repo, pr, wait)
    result: CleanupResult = {
        "pr": pr,
        "repo": repo,
        "state": current["state"],
        "branch": current["branch"],
        "waitedSeconds": waited,
        "removedWorktree": None,
        "deletedBranch": None,
        "notes": [],
        "failures": [],
    }
    if current["state"] == "MERGED":
        clean_merged(repo, current["branch"], args.branch, result)
    else:
        result["notes"].append(f"the pull request is {current['state']}; nothing deleted")
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        The parser.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    facts: argparse.ArgumentParser = sub.add_parser("facts", help="the raw git facts of a tree")
    facts.add_argument("--path", required=True)
    facts.add_argument("--repo", default="")
    facts.add_argument("--base", default="")
    facts.add_argument("--fetch-base", action="store_true")
    facts.add_argument("--unset-base-upstream", action="store_true")
    prov: argparse.ArgumentParser = sub.add_parser("provision", help="reuse or cut the worktree for a branch")
    prov.add_argument("--repo", required=True)
    prov.add_argument("--branch", required=True)
    where = prov.add_mutually_exclusive_group(required=True)
    where.add_argument("--name", help="the tree's directory name under <repo>/.worktrees")
    where.add_argument("--path", help="the tree's full path, which must be <repo>/.worktrees/<name>")
    prov.add_argument("--from-origin", action="store_true", help="stand the tree on the existing origin/<branch>")
    hashes: argparse.ArgumentParser = sub.add_parser("hash-files", help="blob hashes and the work tree digest")
    hashes.add_argument("--tree", required=True)
    hashes.add_argument("files", nargs="*")
    snap: argparse.ArgumentParser = sub.add_parser("snapshot", help="record the work tree as a tree id")
    snap.add_argument("--tree", required=True)
    chg: argparse.ArgumentParser = sub.add_parser("changed", help="the paths that differ from a tree id")
    chg.add_argument("--tree", required=True)
    chg.add_argument("--since", required=True)
    rest: argparse.ArgumentParser = sub.add_parser("restore", help="put the work tree back at a tree id")
    rest.add_argument("--tree", required=True)
    rest.add_argument("--to", required=True)
    clean: argparse.ArgumentParser = sub.add_parser("cleanup-merged-pr", help="remove a merged pull request's worktree")
    clean.add_argument("pr", type=int, help="the pull request number in the repository at --repo")
    clean.add_argument("--repo", required=True, help="a local clone whose origin is the pull request's repository")
    clean.add_argument("--branch", action="store_true", help="also delete the local head branch")
    clean.add_argument("--wait", type=int, default=0, help="seconds to wait for an OPEN pull request to end")
    return parser


COMMANDS: Final[dict[str, Callable[[argparse.Namespace], CommandResult]]] = {
    "facts": cmd_facts,
    "provision": cmd_provision,
    "hash-files": cmd_hash_files,
    "snapshot": cmd_snapshot,
    "changed": cmd_changed,
    "restore": cmd_restore,
    "cleanup-merged-pr": cmd_cleanup_merged_pr,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point: prints one JSON object.

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        0 when the command did its work, 2 when it could not.

    """
    args: argparse.Namespace = build_parser().parse_args(argv)
    command: str = args.command
    try:
        result: CommandResult = COMMANDS[command](args)
    except (GitError, OSError) as exc:
        failure: ErrorResult = {"error": str(exc), "command": command}
        sys.stdout.write(json.dumps(failure) + "\n")
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
