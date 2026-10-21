"""Remove the finished branches and worktrees of the project's repositories.

The `sweep-branches` command of `polyrepo.py` is the fleet-wide safety net behind agents that clean
up after themselves. This module holds the judging and the removing; `polyrepo.py` supplies the
repositories, from its own fetch and inventory data.

A local branch is finished when its work is on `origin/<default>`:

1. git decides first, with no GitHub call: the branch tip is an ancestor of `origin/<default>`;
   every commit of the branch has the same patch on it (`git cherry`); or merging the branch into
   it changes nothing (`git merge-tree`, which finds work that was squash-merged).
2. For the branches git cannot settle, one GraphQL call covers up to GRAPHQL_BRANCHES_PER_CALL
   branches of any number of repositories and returns their pull requests. A branch whose pull
   request merged into the default branch with the branch tip as its head (or an ancestor of it)
   is finished; a branch with an open pull request, or with work no pull request landed, is kept.

A finished branch loses its worktree, its local branch and its GitHub branch. It is kept, and
listed with the reason, when its worktree has uncommitted changes or changed within the last hour,
when GitHub's branch holds work the default branch lacks, or when git or GitHub cannot say.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs git and gh with list argv and no shell
import time
from pathlib import Path

RECENT_SECONDS = 3600
GRAPHQL_BRANCHES_PER_CALL = 25
WORKERS = 16
GIT_TIMEOUT = 120
GH_TIMEOUT = 120
PRS_PER_BRANCH = 10
STATE_OPEN = "OPEN"
STATE_MERGED = "MERGED"
LANDED_ON_DEFAULT = "on-default"
LANDED_SAME_PATCHES = "same-patches"
LANDED_SAME_CONTENT = "content-on-default"
LANDED_PR_MERGED = "pr-merged"


@dataclasses.dataclass
class PullRequest:
    """One pull request that has a local branch as its head."""

    number: int
    state: str
    head: str
    base: str


@dataclasses.dataclass
class Branch:
    """One local branch, what was decided about it and what was done."""

    name: str
    tip: str
    remote_tip: str | None
    worktree: str | None
    landed: str | None = None
    kept: str | None = None
    pr: int | None = None
    pr_state: str | None = None
    removed_worktree: bool = False
    deleted_branch: bool = False
    deleted_remote: bool = False
    failures: list[str] = dataclasses.field(default_factory=list)

    @property
    def settled(self) -> bool:
        """Whether git (or GitHub) has decided it: it landed, or it is kept."""
        return self.landed is not None or self.kept is not None


@dataclasses.dataclass
class RepoSweep:
    """The judgments of one repository's branches."""

    repo: str
    path: Path
    default: str
    slug: str | None
    branches: list[Branch] = dataclasses.field(default_factory=list)
    notes: list[str] = dataclasses.field(default_factory=list)

    @property
    def base_ref(self) -> str:
        """The default branch as last fetched from origin."""
        return f"refs/remotes/origin/{self.default}"


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Run a command with captured text output and no shell.

    Returns:
        The completed process; a timeout comes back as exit status 124.

    """
    try:
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - list argv, no shell
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, "", f"timed out after {timeout}s")


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git in a repository without taking optional locks, so a read leaves no trace.

    Returns:
        The completed process.

    """
    return _run(["git", "--no-optional-locks", "-C", str(path), *args], GIT_TIMEOUT)


def _out(path: Path, *args: str) -> str | None:
    """Run git and return its stripped output, or None when it fails.

    Returns:
        The output, or None.

    """
    done = _git(path, *args)
    return done.stdout.strip() if done.returncode == 0 else None


def _failure(path: Path, args: tuple[str, ...], done: subprocess.CompletedProcess[str]) -> str:
    """Describe a git command that failed.

    Returns:
        The command, where it ran, its exit status and what git printed.

    """
    detail = (done.stderr or done.stdout).strip()
    return f"git {' '.join(args)} in {path} exited {done.returncode}: {detail}"


def _worktrees(path: Path) -> tuple[str | None, dict[str, str], set[str]]:
    """Read the registered worktrees of a repository.

    Returns:
        The primary tree's branch, the worktree path of each other branch, and the branches whose
        worktree is locked.

    """
    primary_branch: str | None = None
    by_branch: dict[str, str] = {}
    locked: set[str] = set()
    listing = _out(path, "worktree", "list", "--porcelain") or ""
    for index, block in enumerate(listing.split("\n\n")):
        tree = ""
        branch = ""
        is_locked = False
        for line in block.splitlines():
            if line.startswith("worktree "):
                tree = line.removeprefix("worktree ")
            elif line.startswith("branch "):
                branch = line.removeprefix("branch refs/heads/")
            elif line.startswith("locked"):
                is_locked = True
        if index == 0:
            primary_branch = branch or None
        elif tree and branch:
            by_branch[branch] = tree
            if is_locked:
                locked.add(branch)
    return primary_branch, by_branch, locked


def _tree_of(path: Path, ref: str) -> str | None:
    """Return the tree id a ref points at.

    Returns:
        The id, or None.

    """
    return _out(path, "rev-parse", f"{ref}^{{tree}}")


def landed_how(path: Path, base_ref: str, ref: str) -> str | None:
    """Say whether a ref's work is on the base, deciding from git alone.

    Returns:
        How it landed (on-default, same-patches, content-on-default), or None when git cannot
        say it did.

    """
    if _git(path, "merge-base", "--is-ancestor", ref, base_ref).returncode == 0:
        return LANDED_ON_DEFAULT
    cherry = _out(path, "cherry", base_ref, ref)
    if cherry is not None and not any(line.startswith("+") for line in cherry.splitlines()):
        return LANDED_SAME_PATCHES
    merged = _git(path, "merge-tree", "--write-tree", base_ref, ref)
    lines = merged.stdout.splitlines()
    if merged.returncode == 0 and lines and lines[0].strip() == _tree_of(path, base_ref):
        return LANDED_SAME_CONTENT
    return None


def _remote_holds_work(sweep: RepoSweep, branch: Branch, pr_head: str | None) -> bool:
    """Whether GitHub's copy of a branch holds work the default branch lacks.

    Returns:
        True when deleting the GitHub branch would lose work.

    """
    if branch.remote_tip is None or branch.remote_tip == branch.tip:
        return False
    if landed_how(sweep.path, sweep.base_ref, branch.remote_tip) is not None:
        return False
    return not (pr_head and _is_ancestor(sweep.path, branch.remote_tip, pr_head))


def _is_ancestor(path: Path, ancestor: str, ref: str) -> bool:
    """Whether a commit is the ref or in its history.

    Returns:
        True when it is.

    """
    return ancestor == ref or _git(path, "merge-base", "--is-ancestor", ancestor, ref).returncode == 0


def local_state(repo: str, path: Path, default: str, slug: str | None) -> RepoSweep:
    """Judge a repository's local branches from git alone.

    Returns:
        The sweep, with every non-protected branch either landed, kept, or left unsettled for
        GitHub to decide.

    """
    sweep = RepoSweep(repo, path, default, slug)
    if _out(path, "rev-parse", "--verify", "--quiet", sweep.base_ref) is None:
        sweep.notes.append(f"origin/{default} does not exist; nothing judged")
        return sweep
    primary, trees, locked = _worktrees(path)
    protected = {default, "main", "master"} | ({primary} if primary else set())
    listing = _out(path, "for-each-ref", "--format=%(refname:short)%09%(objectname)", "refs/heads") or ""
    for line in listing.splitlines():
        name, _, tip = line.partition("\t")
        if name in protected:
            continue
        remote_tip = _out(path, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{name}")
        branch = Branch(name, tip, remote_tip, trees.get(name))
        sweep.branches.append(branch)
        if name in locked:
            branch.kept = f"its worktree {branch.worktree} is locked"
            continue
        branch.landed = landed_how(path, sweep.base_ref, tip)
        if branch.landed is not None and _remote_holds_work(sweep, branch, None):
            branch.landed = None
            branch.kept = f"origin/{name} holds work {sweep.base_ref.removeprefix('refs/remotes/')} lacks"
    return sweep


def _pull_requests(nodes: object, default: str) -> list[PullRequest]:
    """Read the pull requests of a GraphQL connection that count: same repository, into the default branch.

    Returns:
        The pull requests, newest first.

    """
    found: list[PullRequest] = []
    if not isinstance(nodes, list):
        return found
    for node in nodes:
        if not isinstance(node, dict) or node.get("isCrossRepository"):
            continue
        number, state, head, base = (node.get(k) for k in ("number", "state", "headRefOid", "baseRefName"))
        if isinstance(number, int) and isinstance(state, str) and isinstance(head, str) and isinstance(base, str):
            found.append(PullRequest(number, state, head, base))
    return [p for p in found if p.state == STATE_OPEN or p.base == default]


def _query(chunk: list[tuple[RepoSweep, Branch]]) -> tuple[str, list[str]]:
    """Build one GraphQL query for a chunk of branches, and the gh arguments that carry its variables.

    Returns:
        The query text and the `-f name=value` arguments of its variables.

    """
    declarations: list[str] = []
    selections: dict[str, list[str]] = {}
    fields: list[str] = []
    slots: dict[str, int] = {}
    for sweep, branch in chunk:
        if sweep.slug is None:
            continue
        slot = slots.setdefault(sweep.slug, len(slots))
        if not selections.get(sweep.slug):
            owner, _, name = sweep.slug.partition("/")
            declarations += [f"$o{slot}: String!", f"$n{slot}: String!"]
            fields += ["-f", f"o{slot}={owner}", "-f", f"n{slot}={name}"]
        index = len(selections.setdefault(sweep.slug, []))
        var = f"b{slot}_{index}"
        declarations.append(f"${var}: String!")
        fields += ["-f", f"{var}={branch.name}"]
        selections[sweep.slug].append(
            f"p{index}: pullRequests(headRefName: ${var}, first: {PRS_PER_BRANCH},"
            " orderBy: {field: CREATED_AT, direction: DESC})"
            " { nodes { number state headRefOid baseRefName isCrossRepository } }",
        )
    repos = " ".join(
        f"r{slots[slug]}: repository(owner: $o{slots[slug]}, name: $n{slots[slug]}) {{ {' '.join(parts)} }}"
        for slug, parts in selections.items()
    )
    return f"query({', '.join(declarations)}) {{ {repos} }}", fields


def _read_reply(done: subprocess.CompletedProcess[str]) -> tuple[dict[str, object], str | None]:
    """Read the reply of the GraphQL call.

    Returns:
        The reply's `data` object (empty when there is none), and an error text when the call
        failed or only part of it answered.

    """
    error = None if done.returncode == 0 else f"gh api graphql exited {done.returncode}: {done.stderr.strip()}"
    try:
        reply: object = json.loads(done.stdout)
    except json.JSONDecodeError:
        return {}, error or "gh api graphql returned no JSON"
    data = reply.get("data") if isinstance(reply, dict) else None
    if not isinstance(data, dict):
        return {}, error or "gh api graphql returned no data"
    return data, error


def fetch_pull_requests(
    chunk: list[tuple[RepoSweep, Branch]],
) -> tuple[dict[tuple[str, str], list[PullRequest]], str | None]:
    """Ask GitHub, in one call, for the pull requests of a chunk of branches.

    Returns:
        The pull requests by (repository slug, branch), and an error text when the call or part
        of it failed (a branch missing from the first is then undecided).

    """
    query, fields = _query(chunk)
    data, error = _read_reply(_run(["gh", "api", "graphql", "-f", f"query={query}", *fields], GH_TIMEOUT))
    found: dict[tuple[str, str], list[PullRequest]] = {}
    slots: dict[str, int] = {}
    seen: dict[str, int] = {}
    for sweep, branch in chunk:
        slug = sweep.slug
        if slug is None:
            continue
        slot = slots.setdefault(slug, len(slots))
        index = seen.get(slug, 0)
        seen[slug] = index + 1
        repository = data.get(f"r{slot}")
        connection = repository.get(f"p{index}") if isinstance(repository, dict) else None
        if isinstance(connection, dict):
            found[slug, branch.name] = _pull_requests(connection.get("nodes"), sweep.default)
    return found, error


def decide_with_pull_requests(sweep: RepoSweep, branch: Branch, prs: list[PullRequest] | None) -> None:
    """Settle a branch git could not, from the pull requests that have it as head.

    Args:
        sweep: The repository.
        branch: The unsettled branch; landed or kept is set on it.
        prs: Its pull requests, newest first; None when GitHub could not be asked.

    """
    base = sweep.base_ref.removeprefix("refs/remotes/")
    if prs is None:
        branch.kept = "GitHub could not say whether its pull request merged"
        return
    open_pr = next((p for p in prs if p.state == STATE_OPEN), None)
    if open_pr is not None:
        branch.pr, branch.pr_state = open_pr.number, open_pr.state
        branch.kept = f"pull request #{open_pr.number} is OPEN"
        return
    merged = [p for p in prs if p.state == STATE_MERGED]
    for pr in merged:
        if _is_ancestor(sweep.path, branch.tip, pr.head):
            branch.pr, branch.pr_state = pr.number, pr.state
            if _remote_holds_work(sweep, branch, pr.head):
                branch.kept = f"origin/{branch.name} holds work {base} lacks"
            else:
                branch.landed = LANDED_PR_MERGED
            return
    if merged:
        branch.pr, branch.pr_state = merged[0].number, merged[0].state
        branch.kept = f"it has commits after pull request #{merged[0].number}'s head that {base} lacks"
        return
    if prs:
        branch.pr, branch.pr_state = prs[0].number, prs[0].state
        branch.kept = f"pull request #{prs[0].number} was closed without merging; its work is not on {base}"
        return
    count = _out(sweep.path, "rev-list", "--count", f"{sweep.base_ref}..{branch.tip}")
    branch.kept = f"{count or 'some'} commit(s) hold work {base} lacks and no pull request has it as head"


def ask_github(sweeps: list[RepoSweep]) -> int:
    """Settle every branch git could not, with as few GitHub calls as the branches need.

    Returns:
        The number of GitHub calls made.

    """
    pending = [(s, b) for s in sweeps for b in s.branches if not b.settled]
    for sweep, branch in pending:
        if sweep.slug is None:
            branch.kept = "its repository has no GitHub origin; git cannot say its work landed"
    pending = [(s, b) for s, b in pending if not b.settled]
    calls = 0
    for start in range(0, len(pending), GRAPHQL_BRANCHES_PER_CALL):
        chunk = pending[start : start + GRAPHQL_BRANCHES_PER_CALL]
        found, error = fetch_pull_requests(chunk)
        calls += 1
        for sweep, branch in chunk:
            prs = found.get((sweep.slug or "", branch.name))
            decide_with_pull_requests(sweep, branch, prs)
            if prs is None and error:
                branch.failures.append(error)
    return calls


def recently_active(worktree: Path) -> bool:
    """Whether the worktree's git index or HEAD changed within the last RECENT_SECONDS.

    Returns:
        True when a session may be working in it.

    """
    git_dir = _out(worktree, "rev-parse", "--absolute-git-dir")
    if git_dir is None:
        return False
    stamps = [(Path(git_dir) / n).stat().st_mtime for n in ("index", "HEAD") if (Path(git_dir) / n).exists()]
    return bool(stamps) and time.time() - max(stamps) < RECENT_SECONDS


def _remove_worktree(sweep: RepoSweep, branch: Branch, *, dry_run: bool) -> bool:
    """Remove a finished branch's worktree, or record why it stays.

    Returns:
        True when the branch may go on to be deleted.

    """
    if branch.worktree is None or not Path(branch.worktree).is_dir():
        return True
    tree = Path(branch.worktree)
    if recently_active(tree):
        branch.kept = f"its worktree {tree} changed in the last {RECENT_SECONDS // 60} minutes"
        return False
    if _out(tree, "status", "--porcelain=v1", "--untracked-files=normal"):
        branch.kept = f"its worktree {tree} has uncommitted changes"
        return False
    if dry_run:
        return True
    args = ("worktree", "remove", "--force", str(tree))
    done = _git(sweep.path, *args)
    if done.returncode != 0:
        branch.failures.append(_failure(sweep.path, args, done))
        return False
    branch.removed_worktree = True
    return True


def remove_landed(sweep: RepoSweep, branch: Branch, *, dry_run: bool) -> None:
    """Remove a finished branch's worktree, local branch and GitHub branch, or record why it stays.

    With dry_run nothing is removed: the branch is judged and listed as it would be.
    """
    if not _remove_worktree(sweep, branch, dry_run=dry_run) or dry_run:
        return
    _git(sweep.path, "worktree", "prune")
    args = ("branch", "-D", branch.name)
    done = _git(sweep.path, *args)
    if done.returncode != 0:
        branch.failures.append(_failure(sweep.path, args, done))
        return
    branch.deleted_branch = True
    if branch.remote_tip is None:
        return
    push = ("push", "origin", "--delete", branch.name)
    pushed = _git(sweep.path, *push)
    if pushed.returncode == 0:
        branch.deleted_remote = True
    else:
        branch.failures.append(_failure(sweep.path, push, pushed))


def sweep_all(
    repos: list[tuple[str, Path, str, str | None]],
    *,
    dry_run: bool,
) -> tuple[list[RepoSweep], int]:
    """Judge and remove the finished branches of the given repositories.

    Args:
        repos: Each repository's name, path, default branch and GitHub slug (owner/name, or None).
        dry_run: Judge and list only.

    Returns:
        The sweeps, one per repository, and the number of GitHub calls made.

    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        sweeps = list(pool.map(lambda r: local_state(*r), repos))
    calls = ask_github(sweeps)
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(lambda s: _finish(s, dry_run=dry_run), sweeps))
    return sweeps, calls


def _finish(sweep: RepoSweep, *, dry_run: bool) -> None:
    """Remove the finished branches of one repository, then prune its worktree records."""
    for branch in sweep.branches:
        if branch.landed is not None:
            remove_landed(sweep, branch, dry_run=dry_run)
    if not dry_run:
        _git(sweep.path, "worktree", "prune")


def outcome(branch: Branch, *, dry_run: bool) -> str:
    """Say what happened to a branch.

    Returns:
        removed, would-remove (a dry run), failed or kept.

    """
    if branch.failures and not (branch.deleted_branch or branch.kept):
        return "failed"
    if branch.landed is not None and branch.kept is None:
        return "would-remove" if dry_run else "removed"
    return "kept"
