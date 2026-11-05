"""Diagnose deployment failures, then measure and commit the resulting Story changes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from typeguard import check_type

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.journal_registry import Registry
from orchestrator.core.journal_steps import Completion, StepRun, value_artifact
from orchestrator.core.models import RunContext, StepError
from orchestrator.flows.build_sessions import OutputContract, latest, reasoned
from orchestrator.flows.build_suite import run_suite
from orchestrator.flows.build_workspace import Workspace, checkpoint, git_operation
from orchestrator.flows.deploy_support import SCHEMAS, arguments, execute, handback, recorded

if TYPE_CHECKING:
    from orchestrator.core.io import JsonValue


def _author(run: StepRun) -> Completion:
    """Plan a genuine deployment diagnosis session on the Story's own branch.

    Returns:
        Its validated author session as a journal child.

    """
    args = arguments(run.context, "StoryDeployFixArgs")
    request = (
        f"Fix the deployment failure of Story {run.context.bead} in {args['repoPath']}. "
        f"Use only that absolute worktree; branch {args.get('branch', '')}. "
        "Diagnose the supplied output and correct the source. Do not deploy or publish. "
        "Report cause, changedFiles, testCommand and evidence; the host measures changes and runs tests.\n"
        + json.dumps(args["failure"], ensure_ascii=False)
    )
    return reasoned(
        run,
        "deploy-failure-fixer",
        OutputContract(SCHEMAS / "deploy-fix.schema.json", "deploy fix"),
        request,
    )


def _changed_paths(status: str) -> list[str]:
    """Read both paths of renames from git's NUL-delimited porcelain output.

    Returns:
        Paths of changed or untracked files, sorted without losing spaces or newlines.

    """
    parts = iter(status.split("\0"))
    paths: set[str] = set()
    for entry in parts:
        prefix, path = entry[:3], entry[3:]
        if not path:
            continue
        paths.add(path)
        if "R" in prefix[:2] or "C" in prefix[:2]:
            paths.add(next(parts, ""))
    return sorted(path for path in paths if path)


def _verify(run: StepRun) -> Completion:
    """Measure changes and run the explicitly declared regression command directly.

    Returns:
        The actual changed paths, cause, test command and test exit verdict.

    Raises:
        StepError: The fixer changed no file.

    """
    tree = Path(check_type(run.context.args["repoPath"], str))
    status = run.tools.git(tree, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], stage="deploy:fix-verify")
    changed: list[JsonValue] = list(_changed_paths(status.stdout))
    if not changed:
        msg = "no-change"
        raise StepError(msg, OTHER_CAUSE, ("deployment fixer changed no file",))
    test = check_type(latest(run, "testCommand") or latest(run, "fixTestCommand") or "", str).strip()
    passed = False
    if test:
        result = run_suite(run.tools, tree, test, run.context.work / "deploy-fix-tests.json", "deploy:fix-verify")
        passed = result.exit_code == 0
    return Completion(
        artifacts=(
            value_artifact("fixCause", latest(run, "cause") or latest(run, "fixCause") or ""),
            value_artifact("fixTestCommand", test),
            value_artifact("fixChangedFiles", changed),
            value_artifact("fixTestsPassed", passed),
        ),
    )


def _commit(run: StepRun) -> Completion:
    """Commit the measured fix through the repository's normal hooks.

    Returns:
        The independently read commit id.

    """
    tree = Path(check_type(run.context.args["repoPath"], str))
    facts = git_operation(run.tools, "deploy:fix-commit", ["facts", "--path", str(tree)])
    branch = check_type(run.context.args.get("branch") or facts["branch"], str)
    default = check_type(run.context.args.get("defaultBranch") or facts["defaultBranch"], str)
    cause = check_type(latest(run, "fixCause") or "deployment failure", str)
    message = f"fix the deploy of Story {run.context.bead}: {cause[:160]}"
    commit = checkpoint(run.tools, Workspace(tree, branch, default), message)
    return Completion(artifacts=(value_artifact("fixCommit", commit),))


def run(context: RunContext) -> dict[str, JsonValue]:
    """Run the existing deploy-fix child plan through the Python journal runner.

    Returns:
        The driver's fix result, preserving its cause, changes, tests and commit fields.

    """
    args = arguments(context, "StoryDeployFixArgs")
    registry = Registry()
    registry.script_step("deploy:fix-author")(_author)
    registry.script_step("deploy:fix-verify")(_verify)
    registry.script_step("deploy:fix-commit")(_commit)
    runner = execute(context, args, "deploy:fix", registry)
    results = recorded(runner, ("fixCause", "fixChangedFiles", "fixTestsPassed", "fixCommit"))
    return handback(
        context,
        "fixed",
        f"Story {context.bead}: deployment fix measured and committed",
        cause=results.get("fixCause"),
        changedFiles=results.get("fixChangedFiles", []),
        testsPassed=results.get("fixTestsPassed", False),
        commit=results.get("fixCommit"),
    )
