"""Publish terminal target removal under the shared architecture writer lock."""

from pathlib import Path

from ..core.models import StepError
from ..core.tool_locks import LockTimeout, control_repo, file_lock, seconds


def remove(context, tools):
    arch = Path(context.args["archPath"])
    latest = {"removed": False, "commit": None}

    def attempt():
        try:
            with file_lock(
                control_repo() / "ops/sdlc-automation/state/arch-integrate.lock",
                seconds("ATW_ARCH_LOCK_WAIT", 120),
            ):
                result = tools.portfolio(
                    "archstate",
                    "remove_target",
                    str(arch),
                    context.args["targetDir"],
                    message="docs(architecture): remove target after Specs and Tasks are written",
                    execution_id=context.run_id,
                    stage="target-removal",
                )
                latest.update(result)
                if not result.get("ok") and result.get("subcommand"):
                    lock = tools.command(
                        ["git", "rev-parse", "--git-path", "index.lock"],
                        cwd=arch,
                        stage="target-removal",
                    )
                    if (arch / lock.stdout.strip()).exists():
                        raise tools.failure("target-removal", "contention", result)
                if result.get("ok"):
                    tools.git(arch, ["push", "origin", "main"], stage="target-removal")
                return {**result, "reason": "; ".join(result.get("refusals", []))}
        except LockTimeout as exc:
            raise StepError("target-removal", "contention", (str(exc),)) from exc

    try:
        return tools.operation("target-removal", attempt)
    except StepError as exc:
        return {
            **latest,
            "ok": False,
            "reason": str(exc),
            "cause": exc.cause,
            "evidence": list(exc.evidence),
        }
