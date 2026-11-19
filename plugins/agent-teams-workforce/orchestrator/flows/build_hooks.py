"""Correct a checkpoint commit the repository's hooks rejected, once, then hold the Task.

When the hooks reject a checkpoint commit (``build:commit`` or ``build:refactor-snapshot``), the
committing step records the rejection (``commitHookRejection``: the failing hook ids, their trimmed
output and the command evidence), ``build:hook-fix`` hands those findings to ``lint-finding-fixer``,
and the step commits again. That is the one correction round the step gets in the Task's journal.

When the hooks reject the step's commit again, nothing is committed: the step records a
``commit-hook-rejected`` finding naming the remaining hook findings and raises
:class:`CommitHookHeldError`, which :func:`held_handback` turns into the Task's
``stopped-until-changed`` handback. That handback is no failure; the driver holds the Task until
its Story worktree changes, and the next dispatch commits again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from typeguard import check_type

from orchestrator.core.findings import record_for_run
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, value_artifact
from orchestrator.core.models import StepError
from orchestrator.flows.build_sessions import OutputContract, reasoned, view_of
from orchestrator.flows.build_state import CONTRACTS
from orchestrator.flows.build_state import new_step as _new

if TYPE_CHECKING:
    from pathlib import Path

    from orchestrator.core.models import RunContext
    from orchestrator.flows.build_workspace import HookRejectionError

HOOK_REJECTION: Final = "commitHookRejection"
"""The artifact a committing step records for its hooks' rejection: hook ids, trimmed output, evidence."""
FIX_STAGE: Final = "build:hook-fix"
FIXER: Final = "lint-finding-fixer"
HELD_STAGE: Final = "stopped-until-changed"
"""The handback stage of a Task whose commit its hooks still reject after its correction round."""
HEADLINE_REPORT_LINES: Final = 12


def _held_headline(bead: str, rejection: HookRejectionError) -> str:
    """Name the Task, the hooks that still fail and the first lines of their output.

    Returns:
        The held Task's headline.

    """
    report: str = "\n".join(rejection.report.splitlines()[:HEADLINE_REPORT_LINES])
    return (
        f"{bead} is stopped until its Story worktree changes: the repository's commit hooks still "
        f"reject its commit after one correction round ({', '.join(rejection.hooks)}):\n{report}"
    )


class CommitHookHeldError(StepError):
    """The hooks still reject a checkpoint commit after its one correction round; the Task is held."""

    def __init__(self, headline: str, rejection: HookRejectionError) -> None:
        """Attach the held Task's headline and the rejected commit's evidence."""
        self.headline: str = headline
        super().__init__(rejection.stage, OTHER_CAUSE, (headline, *rejection.evidence[-1:]))


def _corrected(run: StepRun, script: str) -> bool:
    """Tell whether this committing step already had its correction round, in any dispatch.

    Returns:
        True when an accepted step of the same script recorded a hook rejection.

    """
    return any(
        step.get("script") == script and any(artifact["name"] == HOOK_REJECTION for artifact in step["artifacts"])
        for step in view_of(run).steps()
    )


def correction(run: StepRun, rejection: HookRejectionError) -> Completion:
    """Hand a hook rejection of this step's commit to the lint finding fixer once, then commit again.

    Args:
        run: The committing step.
        rejection: The repository's hooks' rejection, naming the failing hooks and their output.

    Returns:
        The recorded rejection, the fixer's step and this step again.

    Raises:
        CommitHookHeldError: This step's commit already had its correction round; the remaining
            findings are recorded as a ``commit-hook-rejected`` finding and nothing is committed.

    """
    script: str = check_type(run.step["script"], str)
    if _corrected(run, script):
        headline: str = _held_headline(str(run.bead), rejection)
        record_for_run(
            run,
            str(run.bead),
            kind="commit-hook-rejected",
            detail=headline,
            evidence=tuple(rejection.evidence[-1:]),
        )
        raise CommitHookHeldError(headline, rejection) from rejection
    recorded: dict[str, JsonValue] = {
        "hooks": list(rejection.hooks),
        "output": rejection.report,
        "evidence": rejection.evidence[-1],
    }
    return Completion(
        artifacts=(value_artifact(HOOK_REJECTION, recorded),),
        add=(
            StepGroup((
                _new(FIX_STAGE, "Fix what the repository's commit hooks rejected"),
                _new(script, "Commit again after the hook findings are fixed"),
            )),
        ),
    )


def fix(run: StepRun) -> Completion:
    """Start the lint finding fixer on the latest hook rejection.

    Returns:
        The fixer's session.

    """
    return reasoned(
        run,
        FIXER,
        OutputContract(CONTRACTS / "build-implementation.schema.json", "hookFixWork"),
        f"The repository's commit hooks rejected the Task's commit. Fix every finding in the accepted "
        f"{HOOK_REJECTION} (its hooks, their output and the command evidence) with the smallest change, "
        "keeping the suite green. A finding in a test file is fixed like any other: change its types or "
        "style, never what the test asserts. Never suppress, ignore or reconfigure a rule; report each "
        "finding you cannot fix with its reason. Do not commit",
    )


def held_handback(context: RunContext, journal: Path, held: CommitHookHeldError) -> dict[str, JsonValue]:
    """State that the Task is held until its Story worktree changes, with no failure.

    Returns:
        The ``stopped-until-changed`` handback.

    """
    return {
        "ok": False,
        "stage": HELD_STAGE,
        "beadId": context.bead,
        "headline": held.headline,
        "detailPath": str(journal),
        "sessions": json_object({"sessions": context.sessions})["sessions"],
        "lifecycleDone": False,
    }
