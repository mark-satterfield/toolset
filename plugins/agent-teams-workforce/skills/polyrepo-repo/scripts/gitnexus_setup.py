"""The GitNexus setup the steward keeps outside a repository's files: its re-index git hook and its group membership.

Both are local to the machine, so nothing here is committed:

- The re-index git hook is a git config hook (`hook.<name>.command` and `hook.<name>.event`) in the
  repository's own `.git/config`, read from the control repo's `gitnexus-git-hook.json`. Git runs
  it after a commit, merge, checkout or rewrite, besides any hook file the repository has, and it
  queues a background re-index.
- The group is the GitNexus group named in the control repo's `gitnexus-group`. Its members are the
  steward's repositories, each at a group path equal to its clone's path under the repository root,
  so the session-start check finds every clone from the group alone.

Every GitNexus command runs through the control repo's `gitnexus-pinned.sh`.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed argument lists run git and the pinned GitNexus script
from pathlib import Path

CLI_TIMEOUT = 300
MEMBER_LINE = re.compile(r"^\s+(\S+)\s+->\s+(\S+)\s*$")


class GitNexusSetupError(Exception):
    """A GitNexus setup file is missing or malformed, or GitNexus failed."""


@dataclasses.dataclass(frozen=True)
class GitHookSpec:
    """The git config hook every repository registers."""

    name: str
    command: str
    events: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class GroupPlan:
    """How the group's members differ from the repositories it should hold."""

    exists: bool
    add: dict[str, str]
    remove: list[str]

    @property
    def current(self) -> bool:
        """Say whether the group already holds exactly the wanted members.

        Returns:
            True when nothing needs to change.

        """
        return self.exists and not self.add and not self.remove


def _run(argv: list[str], timeout: int = CLI_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Run a command with captured text output and no shell.

    Returns:
        The completed process; a timeout comes back as returncode 124.

    """
    try:
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed argument list, no shell
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, "", f"timed out after {timeout}s")


def _git() -> str:
    found = shutil.which("git")
    if found is None:
        msg = "git is not on PATH"
        raise GitNexusSetupError(msg)
    return found


def _tail(cp: subprocess.CompletedProcess[str]) -> str:
    lines = (cp.stderr or cp.stdout or "").strip().splitlines()
    return lines[-1] if lines else f"exit {cp.returncode}"


def load_git_hook(path: Path) -> GitHookSpec:
    """Read the git config hook spec.

    Returns:
        The spec.

    Raises:
        GitNexusSetupError: when the file is not a JSON object with a name, a command and events.

    """
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"git hook spec {path} is unreadable: {exc}"
        raise GitNexusSetupError(msg) from exc
    if not isinstance(parsed, dict):
        msg = f"git hook spec {path} is not a JSON object"
        raise GitNexusSetupError(msg)
    name, command, events = parsed.get("name"), parsed.get("command"), parsed.get("events")
    if not isinstance(name, str) or not isinstance(command, str) or not isinstance(events, list) or not events:
        msg = f"git hook spec {path} needs a name, a command and a list of events"
        raise GitNexusSetupError(msg)
    return GitHookSpec(name, command, tuple(str(e) for e in events))


def hook_current(repo: Path, spec: GitHookSpec) -> bool:
    """Say whether a repository's local config registers the hook exactly as specified.

    Returns:
        True when the command and the set of events match.

    """
    git = _git()
    cmd = _run([git, "-C", str(repo), "config", "--local", "--get", f"hook.{spec.name}.command"])
    events = _run([git, "-C", str(repo), "config", "--local", "--get-all", f"hook.{spec.name}.event"])
    return cmd.stdout.strip() == spec.command and sorted(events.stdout.split()) == sorted(spec.events)


def install_hook(repo: Path, spec: GitHookSpec) -> str | None:
    """Register the hook in a repository's local config, replacing any earlier registration of it.

    Returns:
        None on success, else what failed.

    """
    git = _git()
    base = [git, "-C", str(repo), "config", "--local"]
    steps = [
        [*base, f"hook.{spec.name}.command", spec.command],
        [*base, "--replace-all", f"hook.{spec.name}.event", spec.events[0]],
        *([*base, "--add", f"hook.{spec.name}.event", e] for e in spec.events[1:]),
    ]
    for argv in steps:
        cp = _run(argv)
        if cp.returncode != 0:
            return f"git config failed: {_tail(cp)}"
    return None


def read_group_name(path: Path) -> str:
    """Read the group name file.

    Returns:
        The group name.

    Raises:
        GitNexusSetupError: when the file is unreadable or empty.

    """
    try:
        name = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        msg = f"group file {path} is unreadable: {exc}"
        raise GitNexusSetupError(msg) from exc
    if not name:
        msg = f"group file {path} is empty"
        raise GitNexusSetupError(msg)
    return name


def group_members(pinned: Path, group: str) -> dict[str, str] | None:
    """List the group's members.

    Returns:
        Group path to registry name, or None when the group does not exist.

    Raises:
        GitNexusSetupError: when GitNexus cannot list the group for another reason.

    """
    cp = _run([str(pinned), "group", "list", group])
    if cp.returncode != 0:
        if "not found" in cp.stdout + cp.stderr:
            return None
        msg = f"gitnexus group list {group} failed: {_tail(cp)}"
        raise GitNexusSetupError(msg)
    return {m.group(1): m.group(2) for line in cp.stdout.splitlines() if (m := MEMBER_LINE.match(line))}


def plan_group(current: dict[str, str] | None, wanted: dict[str, str], prune: bool) -> GroupPlan:
    """Compare the group with the members it should hold.

    Args:
        current: The group's members, or None when it does not exist.
        wanted: Group path to registry name of every repository it should hold.
        prune: Whether members not wanted are removed (only when every repository was considered).

    Returns:
        The plan.

    """
    have = current or {}
    add = {p: n for p, n in wanted.items() if have.get(p) != n}
    remove = sorted(p for p, n in have.items() if wanted.get(p) != n) if prune else []
    return GroupPlan(exists=current is not None, add=add, remove=remove)


def apply_group(pinned: Path, group: str, plan: GroupPlan) -> list[str]:
    """Create the group when missing and add and remove members as planned.

    Returns:
        What failed; empty on success.

    """
    failures: list[str] = []
    if not plan.exists:
        cp = _run([str(pinned), "group", "create", group])
        if cp.returncode != 0:
            return [f"gitnexus group create {group} failed: {_tail(cp)}"]
    for path in plan.remove:
        cp = _run([str(pinned), "group", "remove", group, path])
        if cp.returncode != 0:
            failures.append(f"gitnexus group remove {group} {path} failed: {_tail(cp)}")
    for path, name in sorted(plan.add.items()):
        cp = _run([str(pinned), "group", "add", group, path, name])
        if cp.returncode != 0:
            failures.append(f"gitnexus group add {group} {path} {name} failed: {_tail(cp)}")
    return failures


def remove_index(pinned: Path, name: str) -> str | None:
    """Delete a retired repository's index and its entry in the GitNexus registry.

    `gitnexus remove` is idempotent: a name the registry does not hold succeeds.

    Returns:
        None on success, else what failed.

    """
    cp = _run([str(pinned), "remove", "--force", name])
    return None if cp.returncode == 0 else f"gitnexus remove {name} failed: {_tail(cp)}"


def sync_group(pinned: Path, group: str) -> str | None:
    """Rebuild the group's cross-repository contracts.

    Returns:
        None on success, else what failed.

    """
    cp = _run([str(pinned), "group", "sync", group], timeout=3600)
    return None if cp.returncode == 0 else f"gitnexus group sync {group} failed: {_tail(cp)}"


def group_path(root: Path, repo: Path) -> str:
    """Return a repository's group path: its clone's path relative to the repository root.

    A clone under the root gets its path below it (`personal-agent/SkillSpoke`). A repository the
    config's `gitnexus.extra_repos` adds from outside the root gets the relative path from the root
    to the path the config names, symlinks unresolved (`../skillspoke-docs`), so joining the root
    and the group path still reaches the clone.

    Returns:
        The POSIX relative path.

    """
    return Path(os.path.relpath(repo.absolute(), root.resolve())).as_posix()


def enqueue_reindex(fleet: Path, repos: list[Path]) -> str | None:
    """Queue repositories for a background re-index through the control repo's fleet script.

    Returns:
        None on success, else what failed.

    """
    if not repos:
        return None
    python = shutil.which("python3")
    if python is None:
        return "python3 is not on PATH"
    cp = _run([python, str(fleet), "enqueue", *(str(r) for r in repos)], timeout=60)
    return None if cp.returncode == 0 else f"gitnexus-fleet.py enqueue failed: {_tail(cp)}"
