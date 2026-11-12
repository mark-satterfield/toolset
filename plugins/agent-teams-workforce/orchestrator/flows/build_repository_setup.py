"""Correct the Task repository's own declarations when they fail its setup, as build work in its worktree."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from typeguard import check_type

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, value_artifact
from orchestrator.core.models import StepError
from orchestrator.flows.build_reviews import HARNESS_FILES, REPOSITORY_SETUP_WORK
from orchestrator.flows.build_sessions import OutputContract, accepted_steps, reasoned
from orchestrator.flows.build_state import CONTRACTS, artifact_document, new_step, workspace_of

if TYPE_CHECKING:
    from pathlib import Path

    from orchestrator.core.io import JsonValue

SELECTION: Final = "repositorySetupSelection"
"""The implementation lead's selection of the specialists that correct the repository's declarations."""
BASELINE: Final = "build:baseline"
"""The continuation of a setup failure found while measuring the baseline."""
RESCOPE_AND_BASELINE: Final = (
    "build:regression-reassess",
    "build:regression-review",
    "build:regression-validate",
    "build:execution-policy",
    BASELINE,
)
"""The steps that reassess the regression scope for the corrected declarations, re-derive its policy and rerun
the baseline."""


def start(again: str, fingerprint: str) -> Completion:
    """Begin a repository-setup correction for a diagnosis routed ``repository``.

    The diagnosis fingerprint is recorded, so the bound on distinct prerequisite diagnoses also bounds these
    corrections.

    Returns:
        The fingerprint and the implementation lead's selection step.

    """
    return Completion(
        artifacts=(value_artifact("prerequisiteFingerprint", fingerprint),),
        add=(
            StepGroup((
                new_step(
                    "build:repository-setup",
                    "Correct the repository declarations that fail the setup",
                    {"again": again},
                ),
            )),
        ),
    )


def _select(run: StepRun) -> Completion:
    """Have the implementation lead select the specialists that correct the repository's declarations.

    Returns:
        The lead's selection session and the step that plans the selected work.

    """
    again: str = check_type(run.params()["again"], str)
    return reasoned(
        run,
        "implementation-lead",
        OutputContract(CONTRACTS / "build-selection.schema.json", SELECTION),
        "Select the implementation specialists that correct only the repository declarations the latest "
        "prerequisiteDiagnosis names as the cause of the failing setup or suite: dependency manifests, lock "
        "files, overrides, peer-dependency conflicts, and test or build configuration that names a package no "
        "manifest declares. Select the specialists of the repository's language and package manager",
        followups=(
            new_step("build:repository-setup-plan", "Plan the selected declaration corrections", {"again": again}),
        ),
    )


def _plan(run: StepRun) -> Completion:
    """Plan one correction step per selected specialist, then the step that resumes the build.

    Returns:
        The correction steps and the resuming step.

    Raises:
        StepError: No specialist was selected, so nothing can correct the declarations.

    """
    again: str = check_type(run.params()["again"], str)
    agents: list[str] = check_type(artifact_document(run, SELECTION)["agents"], list[str])
    if not agents:
        raise StepError(
            run.step["script"],
            OTHER_CAUSE,
            ("The repository's own declarations fail its setup and no implementer was selected to correct them",),
        )
    work = tuple(
        new_step(
            "build:repository-setup-work",
            f"Correct the repository declarations with {agent}",
            {"implementer": agent},
        )
        for agent in agents
    )
    done = new_step("build:repository-setup-done", "Resume the build on the corrected declarations", {"again": again})
    return Completion(add=(StepGroup((*work, done)),))


def _work(run: StepRun) -> Completion:
    """Start one selected specialist's correction of the repository's declarations.

    Returns:
        Its code-work session.

    """
    agent: str = check_type(run.params()["implementer"], str)
    return reasoned(
        run,
        agent,
        OutputContract(CONTRACTS / "build-implementation.schema.json", REPOSITORY_SETUP_WORK),
        "Correct only the repository declarations the latest prerequisiteDiagnosis names, so the failing setup "
        "succeeds: declare in the repository's manifest every package the test configuration and the regression "
        "runs need, resolve a dependency conflict with a proper declaration (for example an npm overrides entry), "
        "regenerate the lock file with the repository's package manager without upgrading unrelated packages, and "
        "change nothing else. List every file you changed in changedFiles, and list each of them in harnessFiles too",
    )


def _harness(run: StepRun, tree: Path) -> list[str]:
    """List the files every accepted repository-setup correction changed, relative to the Task's tree.

    Returns:
        The tree-relative paths, each once, sorted; a path outside the tree is left out.

    """
    listed: list[str] = [
        path
        for step in accepted_steps(run)
        if any(artifact["name"] == REPOSITORY_SETUP_WORK for artifact in step["artifacts"])
        for artifact in step["artifacts"]
        if artifact["kind"] == "value" and artifact["name"] == "changedFiles"
        for path in check_type(artifact["value"], list[str])
    ]
    root: Path = tree.resolve()
    resolved: list[Path] = [(tree / path).resolve() for path in listed]
    return sorted({str(path.relative_to(root)) for path in resolved if path.is_relative_to(root)})


def _done(run: StepRun) -> Completion:
    """Record the corrected declaration files and resume the build where the setup failed.

    A failure found at the baseline reassesses the regression scope, so each run's setup installs the
    now-declared dependencies, re-derives the execution policy bound to that scope and reruns the baseline.
    A failure found by a suite judgment reruns the suite and reassesses it.

    Returns:
        The ``harnessFiles`` value and the resuming steps.

    """
    again: str = check_type(run.params()["again"], str)
    harness: list[JsonValue] = [*_harness(run, workspace_of(run).tree)]
    purpose: str = "Resume the build on the corrected repository declarations"
    steps = (
        tuple(new_step(key, purpose) for key in RESCOPE_AND_BASELINE)
        if again == BASELINE
        else (new_step("build:prerequisites-suite", "Run and reassess the original suite", {"again": again}),)
    )
    return Completion(artifacts=(value_artifact(HARNESS_FILES, harness),), add=(StepGroup(steps),))


HANDLERS: Final = {
    "build:repository-setup": _select,
    "build:repository-setup-plan": _plan,
    "build:repository-setup-work": _work,
    "build:repository-setup-done": _done,
}
"""The build script keys this module handles."""
