"""Bounded git commands and structured failures for architecture mutations."""

from __future__ import annotations

import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed Git argv without a shell.
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import ParamSpec, TypeVar

from contracts import GitFailure, GitFailureFact
from typeguard import CollectionCheckStrategy, typechecked

P = ParamSpec("P")
R = TypeVar("R")


class ArchitectureGitError(RuntimeError):
    """Carry the failing subprocess fact without classifying its message."""

    def __init__(
        self,
        subcommand: str,
        exit_code: int | None,
        timed_out: bool,
        detail: str,
    ) -> None:
        """Retain the failing command and its original diagnostic.

        Raises:
            TypeError: A failure field has an invalid type.

        """
        if not isinstance(subcommand, str) or not isinstance(detail, str):
            error_1: str = "Git failure command and diagnostic must be strings"
            raise TypeError(error_1)
        if exit_code is not None and type(exit_code) is not int:
            error_2: str = "Git exit code must be an integer or None"
            raise TypeError(error_2)
        if not isinstance(timed_out, bool):
            error_3: str = "Git timeout flag must be boolean"
            raise TypeError(error_3)
        super().__init__(detail)
        self.fact: GitFailureFact = {"subcommand": subcommand, "exit": exit_code, "timedOut": timed_out}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def git_result(function: Callable[P, R]) -> Callable[P, R | GitFailure]:  # ruff: ignore[non-pep695-generic-function] - Typeguard 4.6 misresolves PEP 695 ParamSpec as ForwardRef at runtime.
    """Keep command failures in the architecture scripts' result protocol.

    Returns:
        A signature-preserving wrapper with a structured Git failure alternative.

    Raises:
        TypeError: The operation is not callable.

    """
    if not callable(function):
        error_4: str = "Git result operation must be callable"
        raise TypeError(error_4)

    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R | GitFailure:
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


def _commit_message(arguments: list[str], execution_id: str) -> None:
    """Attach the execution trailer to a validated commit command.

    Raises:
        ValueError: The commit message argument is missing.
        ArchitectureGitError: No pipeline execution trailer is available.

    """
    execution_id = execution_id or os.environ.get("ATW_EXECUTION_ID", "")
    if "-m" not in arguments or arguments.index("-m") + 1 >= len(arguments):
        error_8: str = "Architecture commit requires an explicit -m message"
        raise ValueError(error_8)
    message_index: int = arguments.index("-m") + 1
    message: str = arguments[message_index]
    if execution_id:
        arguments[message_index] = message + f"\n\nPipeline-Run: {execution_id}"
    elif not any(line.startswith("Pipeline-Run: ") and line[14:].strip() for line in message.splitlines()):
        raise ArchitectureGitError(
            arguments[0],
            None,
            False,
            "pipeline execution id is required for an architecture commit",
        )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run_git(root: str | Path, *argv: str, execution_id: str = "") -> subprocess.CompletedProcess[str]:
    """Run one checked command with a timeout and a pipeline commit trailer.

    Returns:
        The completed successful Git command.

    Raises:
        ArchitectureGitError: Git cannot run, fails, or lacks its required trailer.
        TypeError: A command argument has an invalid type.
        ValueError: The subcommand or commit message is missing.

    """
    if not isinstance(root, (str, Path)):
        error_5: str = "Git root must be a path or string"
        raise TypeError(error_5)
    if not isinstance(execution_id, str) or any(not isinstance(arg, str) for arg in argv):
        error_6: str = "Git arguments and execution identity must be strings"
        raise TypeError(error_6)
    if not argv or not argv[0]:
        error_7: str = "Git requires a nonempty subcommand"
        raise ValueError(error_7)
    arguments: list[str] = list(argv)
    if arguments[0] == "commit":
        _commit_message(arguments, execution_id)
    executable: str | None = shutil.which("git")
    if executable is None:
        message: str = "Git executable is unavailable"
        raise ArchitectureGitError(arguments[0], None, False, message)
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved Git executable and separate argv.
            [executable, "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=float(os.environ.get("ATW_GIT_TIMEOUT", "120")),
        )
    except subprocess.TimeoutExpired as exc:
        raise ArchitectureGitError(
            arguments[0],
            None,
            True,
            f"git {arguments[0]} timed out",
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
