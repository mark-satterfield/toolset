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
    provision --repo R --branch B --path P [--stash-label L]
        Reuse the worktree registered for branch B or at P, or cut one at P on B from
        origin/<default>. A worktree lives inside its own repository: P must be
        R/.worktrees/<name>, and a reused tree found anywhere else is moved to P.
        With L, a reused tree's uncommitted changes are stashed under a
        message naming L. Reports the tree, its branch, whether it was reused, the default
        branch, the git-common-dir, the stash entry and what was worked around (`blocked`).
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
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

DOC_SUFFIXES = (".md", ".mdx", ".rst", ".adoc")
WORKTREES_DIRNAME = ".worktrees"


class GitError(Exception):
    """A git command this script needs failed."""


def git(tree: str, *argv: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run one git command in a tree.

    Args:
        tree: The directory git runs in (`git -C`).
        *argv: The git arguments.
        check: Raise GitError on a non-zero exit.

    Returns:
        The completed process, text mode.

    Raises:
        GitError: When check is set and git exits non-zero.
    """
    done = subprocess.run(
        ["git", "-C", tree, *argv], capture_output=True, text=True, check=False
    )
    if check and done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()
        raise GitError(
            f"git {' '.join(argv)} in {tree} exited {done.returncode}: {detail}"
        )
    return done


def out(tree: str, *argv: str) -> str | None:
    """The stripped stdout of a git command, or None when it fails.

    Args:
        tree: The directory git runs in.
        *argv: The git arguments.

    Returns:
        The output, or None.
    """
    done = git(tree, *argv, check=False)
    return done.stdout.strip() if done.returncode == 0 else None


def is_doc(path: str) -> bool:
    """Whether a path is documentation, which a restore leaves alone.

    Args:
        path: A repository-relative path.

    Returns:
        True for a documentation path.
    """
    return (
        path.lower().endswith(DOC_SUFFIXES)
        or path.startswith("docs/")
        or "/docs/" in path
    )


def absolute(tree: str, value: str | None) -> str | None:
    """A git path made absolute against the tree.

    Args:
        tree: The tree git printed it for.
        value: The path git printed.

    Returns:
        The real absolute path, or None.
    """
    if not value:
        return None
    return os.path.realpath(
        value if os.path.isabs(value) else os.path.join(tree, value)
    )


def default_branch(repo: str) -> str | None:
    """The repository's default branch: origin/HEAD, else main, else master.

    Args:
        repo: The repository.

    Returns:
        The branch name, or None.
    """
    head = out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head.removeprefix("origin/")
    for name in ("main", "master"):
        for ref in (f"refs/heads/{name}", f"refs/remotes/origin/{name}"):
            if out(repo, "rev-parse", "--verify", "--quiet", ref):
                return name
    return None


def status_lines(tree: str) -> list[str]:
    """The `git status --porcelain` lines of a tree.

    Args:
        tree: The tree.

    Returns:
        The lines.

    Raises:
        GitError: When git status fails.
    """
    text = git(tree, "status", "--porcelain").stdout
    return [line for line in text.splitlines() if line.strip()]


def tree_facts(path: str) -> dict:
    """The raw facts of one tree.

    Args:
        path: The tree.

    Returns:
        The facts; `isGitTree` false when git does not know the path.
    """
    if not os.path.isdir(path):
        return {"path": path, "exists": False, "isGitTree": False}
    top = out(path, "rev-parse", "--show-toplevel")
    if top is None:
        return {"path": path, "exists": True, "isGitTree": False}
    git_dir = absolute(path, out(path, "rev-parse", "--git-dir"))
    common = absolute(path, out(path, "rev-parse", "--git-common-dir"))
    lines = status_lines(path)
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
            path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
        ),
    }


def cmd_facts(args: argparse.Namespace) -> dict:
    """The `facts` command.

    Args:
        args: The parsed arguments.

    Returns:
        The facts.
    """
    notes: list[str] = []
    path = args.path
    if args.base and args.fetch_base and os.path.isdir(path):
        fetched = git(path, "fetch", "origin", args.base, check=False)
        if fetched.returncode != 0:
            notes.append(
                f"git fetch origin {args.base} failed: {fetched.stderr.strip()}"
            )
    facts = tree_facts(path)
    if args.base and facts.get("isGitTree"):
        base_ref = f"origin/{args.base}"
        facts["upstreamIsBase"] = facts.get("upstream") == base_ref
        if facts["upstreamIsBase"] and args.unset_base_upstream:
            git(path, "branch", "--unset-upstream")
            notes.append(f"the branch tracked {base_ref}; its upstream was unset")
            facts["upstream"] = None
        ahead = out(path, "rev-list", "--count", f"{base_ref}..HEAD")
        facts["base"] = args.base
        facts["aheadOfBase"] = (
            int(ahead) if ahead is not None and ahead.isdigit() else None
        )
    if args.repo:
        repo_common = absolute(
            args.repo, out(args.repo, "rev-parse", "--git-common-dir")
        )
        facts["repo"] = args.repo
        facts["repoGitCommonDir"] = repo_common
        facts["sameRepository"] = bool(
            repo_common and repo_common == facts.get("gitCommonDir")
        )
        facts["defaultBranch"] = default_branch(args.repo) if repo_common else None
    facts["notes"] = notes
    return facts


def registered_worktrees(repo: str) -> list[dict]:
    """The worktrees `git worktree list --porcelain` registers.

    Args:
        repo: The repository.

    Returns:
        One {worktree, branch} per registered tree (branch without refs/heads/, or None).
    """
    trees: list[dict] = []
    for block in git(repo, "worktree", "list", "--porcelain").stdout.split("\n\n"):
        entry: dict = {"worktree": None, "branch": None}
        for line in block.splitlines():
            if line.startswith("worktree "):
                entry["worktree"] = line[len("worktree ") :]
            elif line.startswith("branch "):
                entry["branch"] = line[len("branch ") :].removeprefix("refs/heads/")
        if entry["worktree"]:
            trees.append(entry)
    return trees


def cut_worktree(
    repo: str, branch: str, path: str, default: str, blocked: list[str]
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
    fetched = git(repo, "fetch", "origin", default, check=False)
    if fetched.returncode != 0:
        blocked.append(f"git fetch origin {default} failed: {fetched.stderr.strip()}")
    origin_ref = f"origin/{default}"
    has_origin = out(
        repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/{origin_ref}"
    )
    if has_origin and out(repo, "rev-parse", "--abbrev-ref", "HEAD") == default:
        behind = out(repo, "rev-list", "--count", f"HEAD..{origin_ref}")
        if not status_lines(repo) and behind and behind.isdigit() and int(behind) > 0:
            merged = git(repo, "merge", "--ff-only", origin_ref, check=False)
            if merged.returncode != 0:
                blocked.append(
                    f"the main tree could not fast-forward: {merged.stderr.strip()}"
                )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if out(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"):
        git(repo, "worktree", "add", path, branch)
        return
    start = origin_ref if has_origin else default
    if not has_origin:
        blocked.append(
            f"{origin_ref} does not exist; the branch was cut from the local {default}"
        )
    git(repo, "worktree", "add", "--no-track", "-b", branch, path, start)


def stash_changes(tree: str, label: str, blocked: list[str]) -> str:
    """Stash a reused tree's uncommitted changes under a message naming the run.

    Args:
        tree: The tree.
        label: The run's label.
        blocked: Where to note what was worked around.

    Returns:
        The `git stash list -n 1` line, or "" when nothing was stashed.
    """
    if not status_lines(tree):
        return ""
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    git(
        tree,
        "stash",
        "push",
        "--include-untracked",
        "-m",
        f"abandoned run {label} {stamp}",
    )
    entry = out(tree, "stash", "list", "-n", "1") or ""
    if status_lines(tree):
        blocked.append(f"{tree} still has uncommitted changes after the stash")
    return entry


def cmd_provision(args: argparse.Namespace) -> dict:
    """The `provision` command.

    Args:
        args: The parsed arguments.

    Returns:
        What was established.

    Raises:
        GitError: When the default branch cannot be found or the worktree cannot be added.
    """
    repo, branch, path = args.repo, args.branch, args.path
    blocked: list[str] = []
    home = Path(repo).resolve() / WORKTREES_DIRNAME
    if Path(path).resolve().parent != home:
        msg = f"{path} is not {home}/<name>; a worktree lives inside its own repository"
        raise GitError(msg)
    default = default_branch(repo)
    if not default:
        raise GitError(
            f"{repo} has no origin/HEAD, main or master to find its default branch by"
        )
    planned = os.path.realpath(path)
    reused_tree = next(
        (
            t["worktree"]
            for t in registered_worktrees(repo)
            if t["branch"] == branch or os.path.realpath(t["worktree"]) == planned
        ),
        None,
    )
    if reused_tree and Path(reused_tree).resolve().parent != home:
        moved = git(repo, "worktree", "move", reused_tree, path, check=False)
        if moved.returncode == 0:
            reused_tree = path
        else:
            blocked.append(
                f"{reused_tree} could not be moved to {path}: {moved.stderr.strip()}"
            )
    tree = reused_tree or path
    if not reused_tree:
        cut_worktree(repo, branch, path, default, blocked)
    stashed = ""
    if reused_tree and args.stash_label:
        stashed = stash_changes(tree, args.stash_label, blocked)
    facts = tree_facts(tree)
    on = facts.get("branch") or ""
    ok = bool(facts.get("isGitTree")) and on not in ("", "HEAD", default)
    if not ok:
        blocked.append(
            f"the tree {tree} is on {on or 'no branch'!r}, not a feature branch"
        )
    return {
        "ok": ok,
        "worktree": os.path.realpath(tree) if os.path.isdir(tree) else tree,
        "branch": on,
        "reused": reused_tree is not None,
        "defaultBranch": default,
        "gitCommonDir": facts.get("gitCommonDir"),
        "stashed": stashed,
        "blocked": blocked,
    }


def blob_hash(tree: str, rel: str) -> str:
    """The git blob hash of one file, or `missing`.

    Args:
        tree: The tree.
        rel: The path, relative to the tree.

    Returns:
        The hash, or "missing".
    """
    if not os.path.isfile(os.path.join(tree, rel)):
        return "missing"
    return git(tree, "hash-object", "--", rel).stdout.strip()


def cmd_hash_files(args: argparse.Namespace) -> dict:
    """The `hash-files` command.

    Args:
        args: The parsed arguments.

    Returns:
        The hashes and the tree digest.
    """
    tree = args.tree
    files = {f: blob_hash(tree, f) for f in args.files}
    raw = git(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    entries = [e for e in raw.split("\0") if e]
    changed: set[str] = set()
    origin_next = False
    for e in entries:
        if origin_next:
            origin_next = False
            continue
        changed.add(e[3:])
        origin_next = e[:1] in ("R", "C")
    state = {
        "head": out(tree, "rev-parse", "HEAD"),
        "status": entries,
        "content": {p: blob_hash(tree, p) for p in sorted(changed)},
    }
    digest = hashlib.sha256(
        json.dumps(state, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"files": files, "treeDigest": digest, "changedPaths": len(changed)}


def cmd_snapshot(args: argparse.Namespace) -> dict:
    """The `snapshot` command.

    Args:
        args: The parsed arguments.

    Returns:
        The tree id.
    """
    git(args.tree, "add", "-A")
    return {"tree": git(args.tree, "write-tree").stdout.strip()}


def differing(tree: str, snapshot: str) -> list[tuple[str, str]]:
    """The (status, path) pairs where the staged tree differs from a snapshot.

    Args:
        tree: The tree.
        snapshot: The snapshot tree id.

    Returns:
        The pairs.
    """
    git(tree, "add", "-A")
    text = git(
        tree, "diff", "--cached", "--no-renames", "--name-status", snapshot
    ).stdout
    pairs = []
    for line in text.splitlines():
        status, _, path = line.partition("\t")
        if path:
            pairs.append((status.strip(), path))
    return pairs


def cmd_changed(args: argparse.Namespace) -> dict:
    """The `changed` command.

    Args:
        args: The parsed arguments.

    Returns:
        The paths that differ from the snapshot.
    """
    return {"changedFiles": sorted({p for _, p in differing(args.tree, args.since)})}


def cmd_restore(args: argparse.Namespace) -> dict:
    """The `restore` command.

    Args:
        args: The parsed arguments.

    Returns:
        Whether only documentation now differs from the snapshot, and what still does.
    """
    tree, snapshot = args.tree, args.to
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
    remaining = [p for _, p in differing(tree, snapshot) if not is_doc(p)]
    return {"restored": not remaining, "remaining": remaining, "snapshot": snapshot}


def build_parser() -> argparse.ArgumentParser:
    """The command-line parser.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    facts = sub.add_parser("facts", help="the raw git facts of a tree")
    facts.add_argument("--path", required=True)
    facts.add_argument("--repo", default="")
    facts.add_argument("--base", default="")
    facts.add_argument("--fetch-base", action="store_true")
    facts.add_argument("--unset-base-upstream", action="store_true")
    prov = sub.add_parser("provision", help="reuse or cut the worktree for a branch")
    prov.add_argument("--repo", required=True)
    prov.add_argument("--branch", required=True)
    prov.add_argument("--path", required=True)
    prov.add_argument("--stash-label", default="")
    hashes = sub.add_parser("hash-files", help="blob hashes and the work tree digest")
    hashes.add_argument("--tree", required=True)
    hashes.add_argument("files", nargs="*")
    snap = sub.add_parser("snapshot", help="record the work tree as a tree id")
    snap.add_argument("--tree", required=True)
    chg = sub.add_parser("changed", help="the paths that differ from a tree id")
    chg.add_argument("--tree", required=True)
    chg.add_argument("--since", required=True)
    rest = sub.add_parser("restore", help="put the work tree back at a tree id")
    rest.add_argument("--tree", required=True)
    rest.add_argument("--to", required=True)
    return parser


COMMANDS = {
    "facts": cmd_facts,
    "provision": cmd_provision,
    "hash-files": cmd_hash_files,
    "snapshot": cmd_snapshot,
    "changed": cmd_changed,
    "restore": cmd_restore,
}


def main(argv: list[str] | None = None) -> int:
    """Entry point: prints one JSON object.

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        0 when the command did its work, 2 when it could not.
    """
    args = build_parser().parse_args(argv)
    try:
        result = COMMANDS[args.command](args)
    except (GitError, OSError) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
