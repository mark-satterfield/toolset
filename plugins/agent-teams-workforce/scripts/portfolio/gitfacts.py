"""Git facts and mechanical git steps for the workflow scripts, printed as one JSON object.

A workflow script runs this through relayrun.py (`run -- python3 gitfacts.py ...`), so what it
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
        First, every run cleans up the repository's merged work: `git worktree prune`, then
        each linked worktree under R/.worktrees/ whose branch's PR GitHub reports MERGED is
        removed (`git worktree remove`, then `git branch -D`, since a squash-merged branch is
        never an ancestor of the default branch). Never touched: a tree with uncommitted or
        untracked changes, the tree being provisioned (branch B or path P), the primary
        working tree, a detached tree, a branch with no merged PR or with an open one, and a
        branch with commits beyond the merged PR's head. `cleanup` reports what was removed
        and every failure; a failure never stops the provisioning.
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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs the resolved git executable with a separate argv and no shell.
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

DOC_SUFFIXES: Final[tuple[str, ...]] = (".md", ".mdx", ".rst", ".adoc")
WORKTREES_DIRNAME: Final[str] = ".worktrees"


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


class RemovedTree(TypedDict):
    """One merged-PR worktree the cleanup removed, with its branch."""

    worktree: str
    branch: str
    pr: int
    branchDeleted: bool


class Cleanup(TypedDict):
    """What the merged-PR worktree cleanup removed, and what it could not do."""

    removed: list[RemovedTree]
    failures: list[str]


class ProvisionResult(TypedDict):
    """What the `provision` command established."""

    ok: bool
    worktree: str
    branch: str
    reused: bool
    defaultBranch: str
    gitCommonDir: str | None
    blocked: list[str]
    cleanup: Cleanup


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


class ErrorResult(TypedDict):
    """The payload a command that could not do its work prints."""

    error: str
    command: str


type CommandResult = TreeFacts | ProvisionResult | HashFilesResult | SnapshotResult | ChangedResult | RestoreResult


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


def merged_pr(repo: str, branch: str) -> tuple[int, str] | None:
    """Ask GitHub for the merged pull request whose head is the branch.

    Args:
        repo: The repository; `gh` infers the GitHub repository from its remotes.
        branch: The head branch.

    Returns:
        The merged PR's number and head commit, or None when the branch has no merged PR
        or also has an open one.

    Raises:
        GitError: When `gh` is not on PATH or its answer cannot be read.

    """
    executable: str | None = shutil.which("gh")
    if executable is None:
        missing: str = "the gh executable is not on PATH"
        raise GitError(missing)
    fields: str = "number,state,headRefOid"
    argv: list[str] = [executable, "pr", "list", "--head", branch, "--state", "all", "--json", fields]
    done: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved gh executable and separate argv; shell disabled.
        argv,
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        msg: str = f"gh pr list --head {branch} in {repo} exited {done.returncode}: {done.stderr.strip()}"
        raise GitError(msg)
    prs: object = json.loads(done.stdout or "[]")
    if not isinstance(prs, list):
        msg = f"gh pr list --head {branch} printed no list"
        raise GitError(msg)
    states: list[dict[str, object]] = [p for p in prs if isinstance(p, dict)]
    if any(p.get("state") == "OPEN" for p in states):
        return None
    merged: dict[str, object] | None = next((p for p in states if p.get("state") == "MERGED"), None)
    if merged is None:
        return None
    number: object = merged.get("number")
    head: object = merged.get("headRefOid")
    if not isinstance(number, int) or not isinstance(head, str):
        return None
    return number, head


def branch_landed(repo: str, branch: str, pr_head: str) -> bool:
    """Tell whether the local branch holds nothing beyond the merged PR's head commit.

    Args:
        repo: The repository.
        branch: The local branch.
        pr_head: The merged PR's head commit.

    Returns:
        True when the branch tip is the PR head or one of its ancestors.

    """
    tip: str | None = out(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    if tip is None:
        return False
    if tip == pr_head:
        return True
    return git(repo, "merge-base", "--is-ancestor", tip, pr_head, check=False).returncode == 0


def removable(repo: str, tree: Worktree, home: Path, keep: set[str]) -> tuple[str, int] | None:
    """Decide whether one registered worktree is a merged PR's tree that may be removed.

    Args:
        repo: The repository.
        tree: The registered worktree.
        home: The repository's worktrees directory.
        keep: Branches and real paths never touched (the tree being provisioned).

    Returns:
        The branch and PR number when the tree may be removed, else None.

    """
    path: str = tree["worktree"]
    branch: str | None = tree["branch"]
    if branch is None or branch in keep or os.path.realpath(path) in keep:
        return None
    if not Path(path).is_dir() or Path(path).resolve().parent != home or status_lines(path):
        return None
    found: tuple[int, str] | None = merged_pr(repo, branch)
    if found is None or not branch_landed(repo, branch, found[1]):
        return None
    return branch, found[0]


def remove_tree(repo: str, path: str, branch: str, pr: int, cleanup: Cleanup) -> None:
    """Remove one merged-PR worktree, then its local branch, recording the outcome.

    Args:
        repo: The repository.
        path: The worktree.
        branch: Its branch.
        pr: The merged PR's number.
        cleanup: Where the outcome is recorded.

    """
    removed: subprocess.CompletedProcess[str] = git(repo, "worktree", "remove", path, check=False)
    if removed.returncode != 0:
        cleanup["failures"].append(failure_message(repo, ("worktree", "remove", path), removed))
        return
    deleted: subprocess.CompletedProcess[str] = git(repo, "branch", "-D", branch, check=False)
    if deleted.returncode != 0:
        cleanup["failures"].append(failure_message(repo, ("branch", "-D", branch), deleted))
    cleanup["removed"].append({"worktree": path, "branch": branch, "pr": pr, "branchDeleted": deleted.returncode == 0})


def clean_merged_worktrees(repo: str, branch: str, path: str) -> Cleanup:
    """Remove the repository's linked worktrees whose branch's PR GitHub reports MERGED.

    Only trees under <repo>/.worktrees/ are considered. A tree with uncommitted or untracked
    changes, the tree being provisioned (its branch or its path), the primary working tree,
    a detached tree, a branch with no merged PR or with an open PR, and a branch with commits
    beyond the merged PR's head are left alone. `git worktree prune` runs first. A failure is
    recorded and never raised: provisioning goes on.

    Args:
        repo: The repository.
        branch: The branch being provisioned.
        path: The tree being provisioned.

    Returns:
        What was removed and what failed.

    """
    cleanup: Cleanup = {"removed": [], "failures": []}
    keep: set[str] = {branch, os.path.realpath(path)}
    try:
        trees: list[Worktree] = prune_and_list(repo, cleanup)
    except (GitError, OSError) as exc:
        cleanup["failures"].append(str(exc))
        return cleanup
    for tree in trees:
        clean_one(repo, tree, keep, cleanup)
    return cleanup


def prune_and_list(repo: str, cleanup: Cleanup) -> list[Worktree]:
    """Run `git worktree prune`, recording a failure, and list the registered worktrees.

    Args:
        repo: The repository.
        cleanup: Where a prune failure is recorded.

    Returns:
        The registered worktrees.

    """
    pruned: subprocess.CompletedProcess[str] = git(repo, "worktree", "prune", check=False)
    if pruned.returncode != 0:
        cleanup["failures"].append(failure_message(repo, ("worktree", "prune"), pruned))
    return registered_worktrees(repo)


def clean_one(repo: str, tree: Worktree, keep: set[str], cleanup: Cleanup) -> None:
    """Remove one worktree when it is a merged PR's tree, recording any failure.

    Args:
        repo: The repository.
        tree: The registered worktree.
        keep: Branches and real paths never touched.
        cleanup: Where the outcome is recorded.

    """
    home: Path = Path(repo).resolve() / WORKTREES_DIRNAME
    try:
        target: tuple[str, int] | None = removable(repo, tree, home, keep)
    except (GitError, OSError, ValueError) as exc:
        cleanup["failures"].append(f"{tree['worktree']}: {exc}")
        return
    if target is not None:
        remove_tree(repo, tree["worktree"], target[0], target[1], cleanup)


def cmd_provision(args: argparse.Namespace) -> ProvisionResult:
    """Run the `provision` command.

    Before it reuses or cuts the tree, it removes the repository's merged-PR worktrees
    (clean_merged_worktrees); a failure there is reported in `cleanup` and never stops it.

    Args:
        args: The parsed arguments.

    Returns:
        What was established.

    """
    repo: str = args.repo
    branch: str = args.branch
    path: str = planned_path(repo, args.name, args.path)
    cleanup: Cleanup = clean_merged_worktrees(repo, branch, path)
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
        "cleanup": cleanup,
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
    return parser


COMMANDS: Final[dict[str, Callable[[argparse.Namespace], CommandResult]]] = {
    "facts": cmd_facts,
    "provision": cmd_provision,
    "hash-files": cmd_hash_files,
    "snapshot": cmd_snapshot,
    "changed": cmd_changed,
    "restore": cmd_restore,
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
