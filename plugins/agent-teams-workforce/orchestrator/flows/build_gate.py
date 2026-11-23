"""The deterministic checks that stand in for an independent code review of a Task when they all pass.

A Task's code review (``build:select-implementers``) and its final review (``build:final-suite``)
start ``code-correctness-reviewer`` only when a deterministic check fails or cannot decide. The
checks pass together when the whole suite exits 0 on the current content tree, the Task's test
writers wrote tests in this build (the Task's acceptance criteria have tests; the regression
verification maps each one to tests the suite collects before the commit), and the deterministic
checks (``build_checks``: the repository's declared lint task, and an infrastructure Task's CDK
synth) exit 0 on the same tree. A repository that declares no lint task cannot be decided, so the
reviewer runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from orchestrator.flows import build_checks, build_policy
from orchestrator.flows.build_sessions import accepted_steps

if TYPE_CHECKING:
    from orchestrator.core.io import JsonValue
    from orchestrator.core.journal_steps import StepRun

TEST_FILES: Final = "testFiles"
"""The artifact in which a test writer names the test files it wrote."""


def _tests_written(run: StepRun) -> bool:
    """Tell whether a test writer of this Task recorded test files it wrote.

    Returns:
        True when an accepted step names at least one test file.

    """
    return any(
        artifact["name"] == TEST_FILES and artifact["kind"] == "value" and artifact["value"]
        for step in accepted_steps(run)
        for artifact in step["artifacts"]
    )


def passed(
    run: StepRun,
    suite: dict[str, JsonValue],
    stage: str,
    checks: build_checks.Checks | None = None,
) -> str | None:
    """Run the deterministic checks that stand in for a review, and say why they all pass.

    Args:
        run: The step that would start the reviewer.
        suite: The latest whole-suite result, with its evidence key.
        stage: The stage the reviewer would run, for the checks' evidence file names.
        checks: The deterministic checks this step already ran on the current tree, if any.

    Returns:
        The reason the review is not needed, or None when a check fails or cannot decide.

    """
    key: JsonValue = suite.get("evidenceKey")
    tree: str = build_policy.content_tree(run)
    if suite.get("exitCode") != 0 or not isinstance(key, dict) or key.get("tree") != tree:
        return None
    if not _tests_written(run):
        return None
    verified: build_checks.Checks = checks if checks is not None else build_checks.run_checks(run, stage)
    if verified.failure is not None or not verified.lint_declared:
        return None
    commands: str = ", ".join(f"`{command}`" for command in verified.commands)
    return (
        f"every deterministic check passed on tree {tree}: the whole suite exited 0, the Task's tests were "
        f"written in this build, and {commands} exited 0"
    )
