"""Land one tier 2 sync on the release branch and, where the primary tree is on the integration branch, on it too.

A repository whose primary working tree is on the default branch (`main`) takes the sync there, in
the primary tree. One whose primary tree is on the integration branch (`develop`, the config's
`product_branch_policy.integration_branch`) takes it on both branches: on `main` in a temporary
`main` worktree outside the repository, which is removed afterwards (or in a clean worktree that
already has `main` checked out), and on `develop` in the primary tree, staging only the synced paths.
Each branch runs the same tree function, so each gets the canonical content for what it holds. Each
branch is pushed on its own; a push the remote rejects leaves the commit local. A primary tree on any
other branch is skipped.

`--check` plans `main` in a detached temporary worktree of `origin/main`, so no ref moves; `--dry-run`
adds, for each branch, the action a write would take.
"""

from __future__ import annotations

import contextlib
import dataclasses
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Callable, Generator, Mapping

type Result = dict[str, object]
type TreeFn = Callable[[Path, str, bool], Result]
"""Plan, write and commit one sync in a tree: (tree, branch, write) to the tree's result.

The result holds `state` (`current` when the tree needs nothing), the sync's own keys, and, when it
stopped, `status` (`skipped` or `failed`) with a `detail`. It may hold `paths`, the paths it would
commit, which `land` reads for `--dry-run` and drops. It never advances, checks the branch or pushes.
"""
type Advance = Callable[[], Result | None]
"""Bring a branch up to origin: None when it is at or past origin, else {status, detail} saying why not."""

RunMode = Literal["write", "check", "dry-run"]
ModeKind = Literal["main-only", "two-branch", "skipped"]

DONE_STATUSES = frozenset({"pushed", "current-on-origin"})
STOPPED_STATUSES = frozenset({"skipped", "failed"})
STATUS_RANK: Mapping[str, int] = {"failed": 3, "committed": 2, "skipped": 1, "pushed": 0, "current-on-origin": 0}
BRANCH_KEYS = ("state", "status", "commit", "detail", "action", "worktree", "worktree_detail")
STATE_CURRENT = "current"
STATE_UNCHECKED = "unchecked"
WORKTREE_TEMPORARY = "temporary"
PUSH_TIMEOUT = 120
PUSH_WAITS = (0, 5, 15)
PUSH_ON_ORIGIN = "push reported an error but origin has the commit"
TRANSIENT_PUSH = re.compile(
    r"Internal Server Error|HTTP 5\d\d| 50[0-4] |remote end hung up|RPC failed|early EOF"
    r"|Connection reset|Connection timed out|Could not resolve host|timed out",
)
REJECTION_PREFIXES = (" ! ", "remote:")
NO_HOOKS = os.devnull


class GitRun(Protocol):
    """Runs git in a repository and returns the completed process (a timeout comes back as a failure)."""

    def __call__(self, repo: Path, *args: str, timeout: int = ...) -> subprocess.CompletedProcess[str]:
        """Run `git -C repo args`."""
        ...


class WorktreeError(Exception):
    """A temporary worktree could not be created."""


@dataclasses.dataclass(frozen=True)
class Landing:
    """What `land` needs to know about one repository and how to move its branches."""

    git: GitRun
    repo: Path
    name: str
    default_branch: str
    integration_branch: str | None
    sync_subjects: frozenset[str]
    fetch: Callable[[], str | None]
    advance_primary: Advance
    advance_release: Advance


@dataclasses.dataclass(frozen=True)
class Mode:
    """How a repository takes a sync: decided by the branch its primary tree is on."""

    kind: ModeKind
    branch: str
    detail: str = ""


@dataclasses.dataclass
class Lease:
    """A worktree a branch is planned or committed in, and what went wrong removing it."""

    path: Path
    reused: bool
    removal: str | None = None


def _out(git: GitRun, repo: Path, *args: str) -> str | None:
    """Run git and return its stripped output.

    Returns:
        The output, or None when git fails.

    """
    completed = git(repo, *args)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _last_line(completed: subprocess.CompletedProcess[str]) -> str:
    """Return the last line git printed.

    Returns:
        The line, or the exit status when git printed nothing.

    """
    lines = (completed.stderr or completed.stdout or "").strip().splitlines()
    return lines[-1] if lines else f"exit {completed.returncode}"


def worktree_on(git: GitRun, repo: Path, branch: str) -> Path | None:
    """Return the worktree that has the branch checked out.

    Returns:
        Its path, or None when no worktree has it.

    """
    current: Path | None = None
    for line in (_out(git, repo, "worktree", "list", "--porcelain") or "").splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{branch}" and current is not None:
            return current
    return None


def landing_mode(landing: Landing) -> Mode:
    """Decide how the repository takes a sync from the branch its primary tree is on.

    Returns:
        `main-only` on the default branch, `two-branch` on the integration branch, else `skipped`.

    """
    branch = _out(landing.git, landing.repo, "symbolic-ref", "--short", "-q", "HEAD") or "(detached)"
    if branch == landing.default_branch:
        return Mode("main-only", branch)
    if landing.integration_branch is not None and branch == landing.integration_branch:
        return Mode("two-branch", branch)
    wanted = " or ".join(b for b in (landing.default_branch, landing.integration_branch) if b)
    return Mode("skipped", branch, f"on {branch}, not {wanted}")


def hooks_config(git: GitRun, primary: Path, tree: Path) -> tuple[str, ...]:
    """Return the git options that make a commit in a linked worktree run the primary tree's hooks.

    A relative `core.hooksPath` (for example `.beads/hooks`) is taken from the root of the tree the
    commit runs in, and an ignored hook folder does not exist in a new worktree, so no hook would run
    there. The primary tree's hook folder, as an absolute path, is the one every tree must run.

    Returns:
        `-c core.hooksPath=<absolute path>` for a linked worktree; nothing for the primary tree.

    """
    if tree == primary:
        return ()
    hooks = _out(git, primary, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    return ("-c", f"core.hooksPath={hooks}") if hooks else ()


def _counts(git: GitRun, tree: Path, branch: str) -> tuple[int, int] | None:
    """Count the branch's commits ahead of and behind its origin copy.

    Returns:
        (ahead, behind), or None when the branch or its origin copy does not exist.

    """
    symmetric = f"refs/heads/{branch}...refs/remotes/origin/{branch}"
    counts = _out(git, tree, "rev-list", "--left-right", "--count", symmetric)
    if not counts:
        return None
    ahead, behind = counts.split()
    return int(ahead), int(behind)


def _only_sync_commits(landing: Landing, branch: str) -> bool:
    """Say whether every commit the branch has that origin lacks is an earlier sync commit.

    Returns:
        True when each such commit's subject is one of the sync subjects.

    """
    local_only = f"refs/remotes/origin/{branch}..refs/heads/{branch}"
    subjects = _out(landing.git, landing.repo, "log", "--format=%s", local_only)
    return subjects is not None and set(subjects.splitlines()) <= landing.sync_subjects


def _integration_problem(landing: Landing, branch: str) -> str | None:
    """Say why the integration branch cannot take a sync commit, reading only.

    Returns:
        The reason, or None when it can (behind is fine: a fast-forward brings it up).

    """
    if not _out(landing.git, landing.repo, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}"):
        return f"origin has no {branch}"
    counts = _counts(landing.git, landing.repo, branch) or (0, 0)
    if all(counts):
        return f"{branch} has diverged from origin/{branch}"
    if counts[0] and not _only_sync_commits(landing, branch):
        return f"{branch} has unpushed commits that are not sync commits"
    return None


def _advance_integration(landing: Landing, branch: str) -> Result | None:
    """Fast-forward the primary tree's integration branch to origin when it is behind.

    Git refuses the merge when an incoming change touches a file with uncommitted changes, and then
    nothing moves. The primary tree holds active work, so it is never rebased.

    Returns:
        None when the branch can take the commit, else {status, detail}.

    """
    if (problem := _integration_problem(landing, branch)) is not None:
        return {"status": "skipped", "detail": problem}
    if not (_counts(landing.git, landing.repo, branch) or (0, 0))[1]:
        return None
    merged = landing.git(landing.repo, "merge", "--ff-only", "--quiet", f"refs/remotes/origin/{branch}")
    if merged.returncode == 0:
        return None
    return {"status": "skipped", "detail": f"{branch} not brought up to origin/{branch}: {_last_line(merged)}"}


def _dirty(git: GitRun, tree: Path) -> bool:
    """Say whether a tree has uncommitted changes to tracked files.

    Returns:
        True when it has.

    """
    return bool(_out(git, tree, "status", "--porcelain", "--untracked-files=no"))


def _release_problem(landing: Landing, branch: str) -> str | None:
    """Say why the release branch cannot take a sync commit in a separate worktree, reading only.

    Returns:
        The reason, or None when it can.

    """
    existing = worktree_on(landing.git, landing.repo, branch)
    if existing is not None and _dirty(landing.git, existing):
        return f"{branch} is checked out at {existing} with uncommitted changes"
    if all(_counts(landing.git, landing.repo, branch) or (0, 0)):
        return f"{branch} has diverged from origin/{branch}"
    return None


def _push_rejection(completed: subprocess.CompletedProcess[str]) -> str:
    """Keep the lines of a failed push that say why: each ` ! ` and `remote:` line, and the last line.

    Returns:
        The lines, joined.

    """
    lines = (completed.stderr or completed.stdout or "").strip().splitlines()
    kept = [line.strip() for line in lines if line.startswith(REJECTION_PREFIXES)]
    last = _last_line(completed)
    return "; ".join(dict.fromkeys([*kept, last]))


def push_verified(git: GitRun, tree: Path, branch: str, expected_sha: str) -> Result:
    """Push a branch, checking origin after a failure and retrying a transient one.

    GitHub can answer a push with a 500 after it has taken the ref, so after every failure origin's
    tip is read with `ls-remote`; when it is the expected commit, the push succeeded. A transient
    failure is retried, at most three attempts in all.

    Returns:
        {status, commit, detail}: `pushed`, or `committed` with the exact rejection when the commit
        stays local.

    """
    commit = expected_sha[:8]
    rejection = ""
    for wait in PUSH_WAITS:
        time.sleep(wait)
        pushed = git(tree, "push", "origin", branch, timeout=PUSH_TIMEOUT)
        if pushed.returncode == 0:
            return {"status": "pushed", "commit": commit}
        remote = git(tree, "ls-remote", "origin", f"refs/heads/{branch}", timeout=PUSH_TIMEOUT)
        if remote.returncode == 0 and remote.stdout.split()[:1] == [expected_sha]:
            return {"status": "pushed", "commit": commit, "detail": PUSH_ON_ORIGIN}
        rejection = _push_rejection(pushed)
        if not TRANSIENT_PUSH.search(f"{pushed.stderr}\n{pushed.stdout}\n{remote.stderr}"):
            break
    return {"status": "committed", "commit": commit, "detail": f"push failed: {rejection}"}


def _remove_worktree(git: GitRun, repo: Path, folder: Path) -> str | None:
    """Remove a temporary worktree the tool created, its folder and its registration.

    Returns:
        None when it is gone, else what failed.

    """
    problems: list[str] = []
    removed = git(repo, "worktree", "remove", "--force", str(folder))
    if removed.returncode != 0:
        problems.append(f"git worktree remove: {_last_line(removed)}")
    try:
        shutil.rmtree(folder)
    except FileNotFoundError:
        pass
    except OSError as exc:
        problems.append(f"removing {folder}: {exc}")
    pruned = git(repo, "worktree", "prune")
    if pruned.returncode != 0:
        problems.append(f"git worktree prune: {_last_line(pruned)}")
    return "; ".join(problems) if folder.exists() or pruned.returncode != 0 else None


@contextlib.contextmanager
def temporary_worktree(git: GitRun, repo: Path, name: str, checkout: tuple[str, ...]) -> Generator[Lease]:
    """Check out a worktree in a new folder of the system's temporary folder, and remove it afterwards.

    The folder is never inside the repository, so Story worktrees and `sweep-branches` never see it.
    A registration a crashed run left behind is pruned first. The checkout runs no git hook.

    Args:
        git: The git runner.
        repo: The primary tree.
        name: The repository name, part of the folder name.
        checkout: What `git worktree add` checks out after the folder (a branch, or `--detach` and a ref).

    Yields:
        The lease; its `removal` says what failed removing it, once the block has ended.

    Raises:
        WorktreeError: when the worktree cannot be added.

    """
    git(repo, "worktree", "prune")
    folder = Path(tempfile.mkdtemp(prefix=f"polyrepo-{name}-main-"))
    added = git(repo, "-c", f"core.hooksPath={NO_HOOKS}", "worktree", "add", "--quiet", str(folder), *checkout)
    if added.returncode != 0:
        shutil.rmtree(folder)
        message = f"git worktree add: {_last_line(added)}"
        raise WorktreeError(message)
    lease = Lease(folder, reused=False)
    try:
        yield lease
    finally:
        lease.removal = _remove_worktree(git, repo, folder)


def _commit_and_push(landing: Landing, tree: Path, branch: str, tree_fn: TreeFn, *, push_when_ahead: bool) -> Result:
    """Run the tree function for writing, then push the branch when it committed (or is ahead, when asked).

    Returns:
        The tree's result with the push status, commit and detail.

    """
    before = _out(landing.git, tree, "rev-parse", "HEAD")
    out = tree_fn(tree, branch, True)
    if out.get("status") in STOPPED_STATUSES:
        return out
    after = _out(landing.git, tree, "rev-parse", "HEAD") or ""
    ahead = (_counts(landing.git, tree, branch) or (0, 0))[0]
    if after == before and not (push_when_ahead and ahead):
        return out
    return {**out, **push_verified(landing.git, tree, branch, after)}


def _stopped(tree: Path, branch: str, tree_fn: TreeFn, stop: Result) -> Result:
    """Report a branch that could not be brought up to origin: its state, and why it was not written.

    Returns:
        The tree's result when it needs nothing, else `stale-<branch>` with the stop's status and detail.

    """
    out = tree_fn(tree, branch, False)
    if out.get("state") == STATE_CURRENT:
        return out
    return {**out, "state": f"stale-{branch}", **stop}


def _write_release(landing: Landing, tree_fn: TreeFn) -> Result:
    """Commit the sync on the release branch in a separate worktree and push it.

    Returns:
        The branch's result, with the worktree it used.

    """
    branch = landing.default_branch
    existing = worktree_on(landing.git, landing.repo, branch)
    if existing is not None and _dirty(landing.git, existing):
        detail = f"{branch} is checked out at {existing} with uncommitted changes"
        return {"state": f"stale-{branch}", "status": "skipped", "detail": detail}
    if (stop := landing.advance_release()) is not None:
        return {"state": f"stale-{branch}", **stop}
    if existing is not None:
        return {**_commit_and_push(landing, existing, branch, tree_fn, push_when_ahead=True), "worktree": str(existing)}
    try:
        with temporary_worktree(landing.git, landing.repo, landing.name, (branch,)) as lease:
            out = _commit_and_push(landing, lease.path, branch, tree_fn, push_when_ahead=True)
    except WorktreeError as exc:
        return {"state": STATE_UNCHECKED, "status": "failed", "detail": str(exc)}
    return {**out, "worktree": WORKTREE_TEMPORARY, **({"worktree_detail": lease.removal} if lease.removal else {})}


def _plan_release(landing: Landing, tree_fn: TreeFn) -> Result:
    """Plan the sync against origin's release branch in a detached temporary worktree.

    Returns:
        The branch's result, with the worktree it used.

    """
    branch = landing.default_branch
    try:
        detached = ("--detach", f"refs/remotes/origin/{branch}")
        with temporary_worktree(landing.git, landing.repo, landing.name, detached) as lease:
            out = tree_fn(lease.path, branch, False)
    except WorktreeError as exc:
        return {"state": STATE_UNCHECKED, "status": "failed", "detail": str(exc)}
    return {**out, "worktree": WORKTREE_TEMPORARY, **({"worktree_detail": lease.removal} if lease.removal else {})}


def _write_integration(landing: Landing, branch: str, tree_fn: TreeFn) -> Result:
    """Commit the sync on the integration branch in the primary tree, only the synced paths, and push it.

    Returns:
        The branch's result.

    """
    if not _out(landing.git, landing.repo, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}"):
        return {**tree_fn(landing.repo, branch, False), "status": "skipped", "detail": f"origin has no {branch}"}
    if (stop := _advance_integration(landing, branch)) is not None:
        return _stopped(landing.repo, branch, tree_fn, stop)
    return _commit_and_push(landing, landing.repo, branch, tree_fn, push_when_ahead=True)


def _planned_paths(out: Result) -> list[str]:
    """Return the paths a tree result says a write would commit.

    Returns:
        Its `paths`, else its `files`, else its `changes`; empty when it names none.

    """
    paths = out.get("paths") or out.get("files") or out.get("changes") or []
    return [str(path) for path in paths] if isinstance(paths, list) else []


def _action(out: Result, problem: str | None, counts: tuple[int, int] | None) -> str:
    """Say what a write would do on a branch, from its plan and its counts against origin.

    Returns:
        `would skip: <reason>`, `would commit <paths>`, `nothing to commit: <state>`, `would push local
        sync commits`, `would fast-forward` or `up-to-date`.

    """
    ahead, behind = counts or (0, 0)
    if problem is not None:
        return f"would skip: {problem}"
    if out.get("state") != STATE_CURRENT:
        paths = _planned_paths(out)
        return f"would commit {', '.join(paths)}" if paths else f"nothing to commit: {out.get('state')}"
    if ahead:
        return "would push local sync commits"
    if behind:
        return "would fast-forward"
    return "up-to-date"


def _check_two_branch(landing: Landing, mode: Mode, run_mode: RunMode, tree_fn: TreeFn) -> dict[str, Result]:
    """Plan both branches, reading only.

    Returns:
        Branch name to its result.

    """
    fetch_error = landing.fetch()
    release, integration = landing.default_branch, mode.branch
    planned = {release: _plan_release(landing, tree_fn), integration: tree_fn(landing.repo, integration, False)}
    if fetch_error:
        planned[release] = {**planned[release], "detail": f"planned against the last fetch: {fetch_error}"}
    if run_mode != "dry-run":
        return planned
    problems = {release: _release_problem(landing, release), integration: _integration_problem(landing, integration)}
    return {
        branch: {**out, "action": _action(out, problems[branch], _counts(landing.git, landing.repo, branch))}
        for branch, out in planned.items()
    }


def _write_two_branch(landing: Landing, mode: Mode, tree_fn: TreeFn) -> dict[str, Result]:
    """Land the sync on the release branch, then on the integration branch, each on its own.

    Returns:
        Branch name to its result.

    """
    fetch_error = landing.fetch()
    if fetch_error:
        stop: Result = {"state": STATE_UNCHECKED, "status": "skipped", "detail": f"fetch failed: {fetch_error}"}
        return {landing.default_branch: stop, mode.branch: stop}
    return {
        landing.default_branch: _write_release(landing, tree_fn),
        mode.branch: _write_integration(landing, mode.branch, tree_fn),
    }


def _worst_status(branches: Mapping[str, Result]) -> str | None:
    """Return the worst status of the branches: failed, committed, skipped, then pushed.

    Returns:
        The status, or None when no branch has one.

    """
    statuses = [str(out["status"]) for out in branches.values() if "status" in out]
    return max(statuses, key=lambda status: STATUS_RANK.get(status, 0)) if statuses else None


def combine(branches: Mapping[str, Result]) -> Result:
    """Put the branches' results together into one repository result.

    The sync's own keys come from the first branch that is not current (else the first branch);
    `state` is `current` only when every branch is; `status` is the worst branch status; `detail`
    names each branch's detail; `commit` is the release branch's (the first branch).

    Returns:
        The repository result, with `branches`.

    """
    order = list(branches)
    stale = [branch for branch in order if branches[branch].get("state") != STATE_CURRENT]
    extras: Result = {}
    for branch in reversed([*order, *stale[:1]]):
        extras.update(branches[branch])
    details = [f"{branch}: {branches[branch]['detail']}" for branch in order if branches[branch].get("detail")]
    status = _worst_status(branches)
    result: Result = {
        **{key: value for key, value in extras.items() if key not in BRANCH_KEYS},
        "state": branches[stale[0]].get("state") if stale else STATE_CURRENT,
        **({"status": status} if status else {}),
        **({"commit": branches[order[0]]["commit"]} if "commit" in branches[order[0]] else {}),
        **({"detail": "; ".join(details)} if details else {}),
    }
    result["branches"] = {
        branch: {key: out[key] for key in BRANCH_KEYS if key in out} for branch, out in branches.items()
    }
    return result


def _main_only(landing: Landing, mode: Mode, run_mode: RunMode, tree_fn: TreeFn) -> Result:
    """Land, or plan, the sync in the primary tree on the default branch.

    Returns:
        The repository result.

    """
    if run_mode != "write":
        out = tree_fn(landing.repo, mode.branch, False)
        if run_mode == "check":
            return out
        counts = _counts(landing.git, landing.repo, mode.branch)
        problem = f"{mode.branch} has diverged from origin/{mode.branch}" if all(counts or (0, 0)) else None
        return {**out, "action": _action(out, problem, counts)}
    if (stop := landing.advance_primary()) is not None:
        return _stopped(landing.repo, mode.branch, tree_fn, stop)
    return _commit_and_push(landing, landing.repo, mode.branch, tree_fn, push_when_ahead=False)


def _skipped(landing: Landing, mode: Mode, run_mode: RunMode, tree_fn: TreeFn) -> Result:
    """Report a primary tree on neither branch: its state, and, when writing or dry-running, why it is skipped.

    Returns:
        The repository result.

    """
    out = tree_fn(landing.repo, mode.branch, False)
    if out.get("state") == STATE_CURRENT or run_mode == "check":
        return out
    if run_mode == "dry-run":
        return {**out, "action": f"would skip: {mode.detail}"}
    return {**out, "status": "skipped", "detail": mode.detail}


def land(landing: Landing, run_mode: RunMode, tree_fn: TreeFn) -> Result:
    """Land, check or dry-run one sync in one repository, on the branches its primary tree's branch calls for.

    Returns:
        The repository result (without `repo`); in two-branch mode it carries `branches`.

    """
    mode = landing_mode(landing)
    if mode.kind == "main-only":
        out = _main_only(landing, mode, run_mode, tree_fn)
    elif mode.kind == "skipped":
        out = _skipped(landing, mode, run_mode, tree_fn)
    elif run_mode == "write":
        out = combine(_write_two_branch(landing, mode, tree_fn))
    else:
        out = combine(_check_two_branch(landing, mode, run_mode, tree_fn))
    out.pop("paths", None)
    return out


def done(result: Mapping[str, object], *, write: bool) -> bool:
    """Say whether a repository result needs nothing more: every branch current, or (writing) pushed.

    A temporary worktree that could not be removed also leaves the result not done.

    Returns:
        True when nothing is left.

    """
    branches = result.get("branches")
    outs = list(branches.values()) if isinstance(branches, dict) else [result]
    return all(_branch_done(out, write=write) for out in outs if isinstance(out, dict))


def _branch_done(out: Mapping[str, object], *, write: bool) -> bool:
    """Say whether one branch's result needs nothing more.

    Returns:
        True when it is current or, writing, its status is done, and no worktree removal failed.

    """
    settled = out.get("state") == STATE_CURRENT or (write and out.get("status") in DONE_STATUSES)
    return settled and not out.get("worktree_detail")
