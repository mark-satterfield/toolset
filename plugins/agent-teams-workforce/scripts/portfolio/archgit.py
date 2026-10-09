"""Bounded git commands and structured failures for architecture mutations."""

from __future__ import annotations

import os
import subprocess
from functools import wraps


class ArchitectureGitError(RuntimeError):
    """Carry the failing subprocess fact without classifying its message."""

    def __init__(
        self, subcommand: str, exit_code: int | None, timed_out: bool, detail: str
    ):
        super().__init__(detail)
        self.fact = {"subcommand": subcommand, "exit": exit_code, "timedOut": timed_out}


def git_result(function):
    """Keep command failures in the architecture scripts' result protocol."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ArchitectureGitError as exc:
            return {
                "ok": False,
                **exc.fact,
                "refusals": [str(exc)],
                "summary": {"ok": False, **exc.fact, "refusals": [str(exc)]},
            }

    return wrapped


def run_git(root, *argv: str, execution_id: str = "") -> subprocess.CompletedProcess:
    """Run one checked command with a timeout and a pipeline commit trailer."""
    arguments = list(argv)
    if arguments[0] == "commit":
        execution_id = execution_id or os.environ.get("ATW_EXECUTION_ID", "")
        message_index = arguments.index("-m") + 1
        message = arguments[message_index]
        if execution_id:
            arguments[message_index] = message + f"\n\nPipeline-Run: {execution_id}"
        elif not any(
            line.startswith("Pipeline-Run: ") and line[14:].strip()
            for line in message.splitlines()
        ):
            raise ArchitectureGitError(
                "commit",
                None,
                False,
                "pipeline execution id is required for an architecture commit",
            )
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=float(os.environ.get("ATW_GIT_TIMEOUT", "120")),
        )
    except subprocess.TimeoutExpired as exc:
        raise ArchitectureGitError(
            arguments[0], None, True, f"git {arguments[0]} timed out"
        ) from exc
    except OSError as exc:
        raise ArchitectureGitError(arguments[0], None, False, str(exc)) from exc
    if result.returncode:
        raise ArchitectureGitError(
            arguments[0],
            result.returncode,
            False,
            (result.stderr or result.stdout).strip(),
        )
    return result
