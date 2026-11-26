"""Commit and push the vault paths one pipeline step wrote, and nothing else.

Every pipeline step that writes files in the documentation vault, other than the filing clerk,
calls :func:`commit_paths` with exactly the paths it wrote: the elaboration's document
maintainers, the promotion, the built-version steps and the driver that files specs and TRDs.
Only the named paths are staged and committed, so another session's uncommitted edits elsewhere
in the vault stay out of the commit. The vault's branch is then pushed; a rejected push is
rebased onto the remote branch and pushed again.

The commands run through ``archgit.run_git``, which retries a command another git process blocks
with the index lock and records the pipeline execution on the commit (``Pipeline-Run:``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

# isort: split
from archgit import ArchitectureGitError, run_git

if TYPE_CHECKING:
    from collections.abc import Sequence

BRANCH: Final = "main"
"""The vault branch every pipeline commit lands on."""
REMOTE: Final = "origin"
"""The remote the vault branch is pushed to."""


def _relative(top: Path, path: str | Path) -> str:
    """Name one path relative to the vault's top folder.

    Returns:
        The POSIX path under the vault.

    Raises:
        ValueError: The path lies outside the vault.

    """
    candidate: Path = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    resolved: Path = candidate.resolve()
    if not resolved.is_relative_to(top):
        message: str = f"{path} is not inside the vault at {top}"
        raise ValueError(message)
    return resolved.relative_to(top).as_posix()


def _push(top: Path, execution_id: str) -> None:
    """Push the vault branch; when the remote refuses it, rebase onto the remote branch and push again."""
    try:
        run_git(top, "push", REMOTE, BRANCH, execution_id=execution_id)
    except ArchitectureGitError:
        run_git(top, "pull", "--rebase", "--autostash", REMOTE, BRANCH, execution_id=execution_id)
        run_git(top, "push", REMOTE, BRANCH, execution_id=execution_id)


def _ahead(top: Path, execution_id: str) -> bool:
    """Tell whether the vault branch holds commits its remote branch does not.

    Returns:
        True when at least one local commit is unpushed; False when none is, or when the remote
        branch cannot be compared.

    """
    try:
        counted: str = run_git(
            top,
            "rev-list",
            "--count",
            f"{REMOTE}/{BRANCH}..HEAD",
            execution_id=execution_id,
        ).stdout.strip()
    except ArchitectureGitError:
        return False
    return counted not in {"", "0"}


def commit_paths(
    repo: str | Path,
    paths: Sequence[str | Path],
    message: str,
    *,
    execution_id: str = "",
) -> str | None:
    """Commit the named vault paths and push the vault branch.

    Only the named paths that exist or that git tracks are staged and committed, so a path that
    was never created is left out and one that was deleted is committed as deleted; when no named
    path is left, nothing is staged, since git would stage the whole vault. The branch is pushed
    when this call made a commit or an earlier one was left unpushed.

    Args:
        repo: The vault, or any folder inside it (the architecture root, for one).
        paths: The paths the step wrote, absolute or relative to the vault's top folder.
        message: The commit message.
        execution_id: The pipeline execution recorded on the commit; empty reads ``ATW_EXECUTION_ID``.

    Returns:
        The commit this call made or pushed, or None when the paths held nothing to commit and
        nothing was left to push.

    Raises:
        TypeError: An argument has an invalid type.
        ValueError: The message is empty or a path lies outside the vault.

    """
    if not isinstance(repo, (str, Path)) or not isinstance(message, str) or not isinstance(execution_id, str):
        error_1: str = "commit_paths: arguments do not satisfy the declared input contract"
        raise TypeError(error_1)
    if any(not isinstance(path, (str, Path)) for path in paths):
        error_2: str = "commit_paths: every path must be a string or a path"
        raise TypeError(error_2)
    if not message.strip():
        error_3: str = "commit_paths: the commit message is empty"
        raise ValueError(error_3)
    top: Path = Path(run_git(repo, "rev-parse", "--show-toplevel", execution_id=execution_id).stdout.strip()).resolve()
    relative: list[str] = sorted({_relative(top, path) for path in paths})
    tracked: set[str] = set()
    if relative:
        tracked = set(run_git(top, "ls-files", "-z", "--", *relative, execution_id=execution_id).stdout.split("\0"))
    named: list[str] = [path for path in relative if (top / path).exists() or path in tracked]
    made: str | None = None
    staged: str = ""
    if named:
        run_git(top, "add", "-A", "--", *named, execution_id=execution_id)
        staged = run_git(top, "diff", "--cached", "--name-only", "--", *named, execution_id=execution_id).stdout
    if staged.strip():
        run_git(top, "commit", "-q", "-m", message, "--", *named, execution_id=execution_id)
        made = run_git(top, "rev-parse", "HEAD", execution_id=execution_id).stdout.strip()
    if made is not None or _ahead(top, execution_id):
        _push(top, execution_id)
        made = run_git(top, "rev-parse", "HEAD", execution_id=execution_id).stdout.strip()
    return made
