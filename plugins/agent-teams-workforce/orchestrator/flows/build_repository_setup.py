"""Correct the Task repository's own declarations when they fail its setup, as build work in its worktree."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from typeguard import check_type

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun
from orchestrator.core.models import StepError
from orchestrator.flows import build_prerequisite_round
from orchestrator.flows.build_sessions import OutputContract, reasoned
from orchestrator.flows.build_state import CONTRACTS, artifact_document, new_step

if TYPE_CHECKING:
    from finding_contract import FindingKind

REPOSITORY_SETUP_WORK: Final = "repositorySetupWork"
"""One selected specialist's correction of the repository's declarations: the artifact that marks its step."""
SELECTION: Final = "repositorySetupSelection"
"""The implementation lead's selection of the specialists that correct the repository's declarations."""
BASELINE: Final = "build:baseline"
"""The continuation of a setup failure found while measuring the baseline."""
VALIDATE: Final = "build:regression-validate"
"""The continuation of a scope whose setups install packages the repository does not declare."""
RESCOPE: Final = ("build:regression-reassess", "build:regression-review", VALIDATE)
"""The steps that assess, review and validate the regression scope again."""
RESCOPE_AND_BASELINE: Final = (*RESCOPE, "build:execution-policy", BASELINE)
"""The steps that reassess the regression scope for the corrected declarations, re-derive its policy and rerun
the baseline."""


def start(again: str) -> Completion:
    """Begin a repository-setup correction for a diagnosis routed ``repository``.

    The diagnosis that routes here records its own inputs fingerprint.

    Returns:
        The implementation lead's selection step.

    """
    return Completion(
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
        "change nothing else. List every file you changed in changedFiles",
    )


def _done(run: StepRun) -> Completion:
    """Resume the build where the setup failed, on the corrected declarations.

    A failure found at the baseline reassesses the regression scope, so each run's setup installs the
    now-declared dependencies, re-derives the execution policy bound to that scope and reruns the baseline.
    Undeclared packages found by scope validation reassess the scope, whose policy and baseline steps still
    follow. A failure found by a suite judgment reruns the suite and reassesses it, when the correction
    changed the suite's inputs; a correction that changed nothing hands the failure to the implementers.

    Returns:
        The resuming steps, or the failure handed to the implementers.

    """
    again: str = check_type(run.params()["again"], str)
    purpose: str = "Resume the build on the corrected repository declarations"
    resumed: dict[str, tuple[str, ...]] = {BASELINE: RESCOPE_AND_BASELINE, VALIDATE: RESCOPE}
    if again in resumed:
        return Completion(add=(StepGroup(tuple(new_step(key, purpose) for key in resumed[again])),))
    diagnosed: str = build_prerequisite_round.diagnosis_fingerprint(run)
    if build_prerequisite_round.inputs_fingerprint(run, again)[0] == diagnosed:
        finding: tuple[str, FindingKind, str] = (
            build_prerequisite_round.story_of(run),
            "prerequisite-carried",
            "the repository-setup correction changed no file",
        )
        return build_prerequisite_round.hand_off(run, again, finding, (), diagnosed)
    return build_prerequisite_round.continuation(run, again)


HANDLERS: Final = {
    "build:repository-setup": _select,
    "build:repository-setup-plan": _plan,
    "build:repository-setup-work": _work,
    "build:repository-setup-done": _done,
}
"""The build script keys this module handles."""
