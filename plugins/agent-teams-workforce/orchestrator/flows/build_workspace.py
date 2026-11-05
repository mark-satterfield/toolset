"""Mechanical workspace and checkpoint operations, without a command-runner session."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from typeguard import check_type

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import StepError
from orchestrator.core.tools import Tools

GITUTILS: Final = Path(__file__).resolve().parents[2] / "scripts" / "portfolio" / "gitutils.py"
WORKTREE_PREFIX: Final = "story"
PATH_COMPONENT: Final = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class Workspace:
    """The independently verified Story worktree and its actual branch."""

    tree: Path
    branch: str
    default_branch: str


def git_operation(tools: Tools, stage: str, arguments: list[str]) -> dict[str, JsonValue]:
    """Call the existing git utilities directly and validate their object result.

    Args:
        tools: The dispatch's command boundary.
        stage: The journal step for attribution.
        arguments: Exact gitutils subcommand arguments.

    Returns:
        The checked utility result.

    Raises:
        TypeError: Arguments violate the operation contract.
        StepError: The utility cannot execute successfully.

    """
    if not isinstance(tools, Tools) or not isinstance(stage, str):
        message: str = "git operation requires Tools and a stage string"
        raise TypeError(message)
    if not arguments or any(not isinstance(argument, str) for argument in arguments):
        message = "git operation requires nonempty string arguments"
        raise TypeError(message)
    result = tools.command([sys.executable, str(GITUTILS), *arguments], stage=stage)
    document: dict[str, JsonValue] = json_object(json.loads(result.stdout))
    if document.get("error"):
        message = f"{stage}: {document['error']}"
        raise StepError(stage, OTHER_CAUSE, (message,))
    return document


def provision(tools: Tools, repository: Path, story_id: str) -> Workspace:
    """Create or reuse the Story's own worktree and independently verify its git identity.

    Args:
        tools: The dispatch's command boundary.
        repository: The canonical repository path named by the Story.
        story_id: The parent Story's bead id.

    Returns:
        A verified workspace on the Story's branch.

    Raises:
        TypeError: Inputs or utility fields have invalid types.
        StepError: A git operation fails.

    """
    if not isinstance(repository, Path) or not isinstance(story_id, str):
        message: str = "workspace provision requires a repository Path and Story id"
        raise TypeError(message)
    if not repository.is_absolute() or not repository.is_dir() or not story_id.startswith("ssbd-"):
        message = "workspace provision requires an absolute repository and parent Story id"
        msg = "build:workspace"
        raise StepError(msg, OTHER_CAUSE, (message,))
    name: str = PATH_COMPONENT.sub("-", f"{story_id}-{repository.name}")
    branch: str = f"{WORKTREE_PREFIX}/{story_id}"
    planned: dict[str, JsonValue] = git_operation(
        tools,
        "build:workspace",
        ["provision", "--repo", str(repository), "--branch", branch, "--name", name],
    )
    if planned.get("ok") is not True:
        message = f"Story worktree provision failed: {planned.get('blocked', [])}"
        msg = "build:workspace"
        raise StepError(msg, OTHER_CAUSE, (message,))
    tree: Path = Path(check_type(planned["worktree"], str))
    facts: dict[str, JsonValue] = git_operation(
        tools,
        "build:workspace",
        ["facts", "--path", str(tree), "--repo", str(repository)],
    )
    actual_branch: str = check_type(facts["branch"], str)
    default: str = check_type(facts["defaultBranch"], str)
    if facts.get("sameRepository") is not True or actual_branch != branch or actual_branch == default:
        message = f"Story worktree identity mismatch: {facts}"
        msg = "build:workspace"
        raise StepError(msg, OTHER_CAUSE, (message,))
    return Workspace(tree, actual_branch, default)


def checkpoint(tools: Tools, workspace: Workspace, message: str) -> str:
    """Commit a dirty Story worktree through its normal hooks, preserving clean-tree commits.

    Args:
        tools: The dispatch's command boundary.
        workspace: Verified Story worktree.
        message: Task-specific commit message.

    Returns:
        Actual HEAD after the commit, or unchanged HEAD for a clean tree.

    Raises:
        TypeError: Arguments have invalid types.
        StepError: Git or the repository's hooks reject the commit.

    """
    if not isinstance(workspace, Workspace) or not isinstance(message, str):
        problem: str = "checkpoint requires a Workspace and commit message"
        raise TypeError(problem)
    facts: dict[str, JsonValue] = git_operation(tools, "build:commit", ["facts", "--path", str(workspace.tree)])
    if facts.get("branch") != workspace.branch or workspace.branch in {workspace.default_branch, "HEAD"}:
        problem = "checkpoint worktree is no longer on its Story branch"
        msg = "build:commit"
        raise StepError(msg, OTHER_CAUSE, (problem,))
    if facts.get("dirty") is True:
        tools.git(workspace.tree, ["add", "--all"], stage="build:commit")
        tools.git(workspace.tree, ["commit", "-m", message], stage="build:commit")
    after: dict[str, JsonValue] = git_operation(tools, "build:commit", ["facts", "--path", str(workspace.tree)])
    if after.get("branch") != workspace.branch or after.get("dirty") is True:
        problem = "checkpoint did not leave a clean Story worktree on its original branch"
        msg = "build:commit"
        raise StepError(msg, OTHER_CAUSE, (problem,))
    return check_type(after["head"], str)
