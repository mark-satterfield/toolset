"""Deterministic calls with structured failures and one retry boundary."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed argv, no shell.
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ParamSpec, TypeVar

import beadgraph
from contracts import JsonInput, JsonObject, json_value
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from .models import RetryExhaustedError, StepError
from .tool_locks import bd_gate, seconds

RETRY_CAUSES = frozenset({"contention", "bd-timeout", "tool-timeout", "network"})
_LOG = logging.getLogger(__name__)
_MAX_ATTEMPTS = 3
_IMPORT_LOCK = threading.RLock()


P = ParamSpec("P")
R = TypeVar("R")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def retry_call[T](
    action: Callable[[], T],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry measured transient errors with three total attempts.

    Returns:
        The action result.

    Raises:
        StepError: A non-retryable step failure occurred.
        RetryExhaustedError: All transient attempts failed.
        RuntimeError: The retry configuration allowed no attempts.
        TypeError: The action or sleeper is not callable.

    """
    attempt: int
    if not callable(action) or not callable(sleep):
        message: str = "Retry action and sleeper must be callable"
        raise TypeError(message)
    delay: float = 30.0
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return action()
        except StepError as exc:
            if exc.cause not in RETRY_CAUSES:
                raise
            if attempt + 1 == _MAX_ATTEMPTS:
                raise RetryExhaustedError(exc.stage, exc.cause, exc.evidence, resume_at=exc.resume_at) from exc
            _LOG.warning("%s: %s; retry in %ss", exc.stage, exc.cause, delay)
            sleep(delay)
            delay *= 2
    message = "retry attempt loop did not execute"
    raise RuntimeError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def env_path(name: str) -> Path:
    """Resolve a required project path.

    Returns:
        The configured absolute path.

    Raises:
        StepError: The required variable is absent.
        TypeError: The variable name is not a string.

    """
    if not isinstance(name, str):
        message: str = "Environment variable name must be a string"
        raise TypeError(message)
    value: str = os.environ.get(name, "").strip()
    stage: str = "input"
    if not value:
        raise StepError(stage, "other", (f"{name} is required",))
    return Path(value).expanduser().resolve()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def vault_path(relative: str) -> Path:
    """Resolve a path within the configured architecture root.

    Returns:
        The resolved architecture path.

    Raises:
        StepError: The requested path escapes the architecture root.
        TypeError: The relative path is not a string.

    """
    if not isinstance(relative, str):
        message: str = "Vault relative path must be a string"
        raise TypeError(message)
    root: Path = env_path("ATW_ARCH_PATH")
    result: Path = (root / relative).resolve()
    stage: str = "input"
    if not result.is_relative_to(root):
        raise StepError(stage, "other", (f"path escapes ATW_ARCH_PATH: {relative}",))
    return result


@dataclass(frozen=True)
class CommandResult:
    """An executable's factual result; stderr never determines its cause."""

    argv: tuple[str, ...]
    exit: int
    stdout: str
    stderr: str

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries.

        Raises:
            TypeError: A field violates its declared type.

        """
        if not isinstance(self.argv, tuple) or any(not isinstance(argument, str) for argument in self.argv):
            message: str = "Command arguments must be a tuple of strings"
            raise TypeError(message)
        if not isinstance(self.exit, int) or not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            message = "Command exit and output fields violate their declared types"
            raise TypeError(message)
        check_type(self.argv, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.exit, int, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.stdout, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.stderr, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def to_json(self) -> JsonObject:
        """Preserve command evidence as its exact JSON fields.

        Returns:
            The argument vector, exit code and captured output.

        """
        return {"argv": json_value(self.argv), "exit": self.exit, "stdout": self.stdout, "stderr": self.stderr}


@dataclass(frozen=True)
class DeploymentTarget:
    """Repository and explicit AWS profile for a deployment command."""

    repository: Path
    profile: str

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries.

        Raises:
            TypeError: A field violates its declared type.

        """
        if not isinstance(self.repository, Path) or not isinstance(self.profile, str):
            message: str = "Deployment target requires a repository Path and profile string"
            raise TypeError(message)
        check_type(self.repository, Path, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.profile, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _command_arguments(arguments: Sequence[str], timeout: float) -> None:
    """Validate argv and a finite timeout consistently before wrapper expansion.

    Raises:
        TypeError: Arguments are not a sequence of strings or timeout is not numeric.
        ValueError: The timeout is not positive and finite.

    """
    if not isinstance(arguments, Sequence) or isinstance(arguments, (str, bytes)):
        message: str = "Command arguments must be a sequence of strings, not a string"
        raise TypeError(message)
    if any(not isinstance(argument, str) for argument in arguments):
        message = "Every command argument must be a string"
        raise TypeError(message)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        message = "Command timeout must be numeric, not boolean"
        raise TypeError(message)
    if not 0 < timeout < float("inf"):
        message = "Command timeout must be positive and finite"
        raise ValueError(message)


class Tools:
    """One run's deterministic tool boundary and private operation evidence directory."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self, evidence: Path) -> None:
        """Bind the evidence directory for deterministic operation failures.

        Raises:
            TypeError: The evidence directory is not a Path.

        """
        if not isinstance(evidence, Path):
            message: str = "Tool evidence directory must be a Path"
            raise TypeError(message)
        self.evidence: Path = evidence
        self.plugin: Path = Path(__file__).resolve().parents[2]

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def failure(self, stage: str, cause: str, facts: Mapping[str, JsonInput]) -> StepError:
        """Persist evidence off stdout and return the structured step failure.

        Returns:
            The failure referencing its evidence file.

        Raises:
            TypeError: Identifiers or evidence violate the declared contract.

        """
        if not isinstance(stage, str) or not isinstance(cause, str) or not isinstance(facts, Mapping):
            message: str = "Failure evidence requires string identifiers and a JSON mapping"
            raise TypeError(message)
        self.evidence.mkdir(parents=True, exist_ok=True)
        path: Path = self.evidence / f"tool-{uuid.uuid4().hex}.json"
        descriptor: int = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(json_value(facts), handle, ensure_ascii=False)
        return StepError(stage, cause, (str(path),))

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def command(
        self,
        argv: Sequence[str],
        *,
        stage: str,
        cwd: Path | None = None,
        timeout: float = 120,
        check: bool = True,
    ) -> CommandResult:
        """Run an executable with a finite timeout and bounded transient retries.

        Returns:
            The executable result.

        Raises:
            TypeError: An argument violates the declared input contract.
            FileNotFoundError: The executable cannot be resolved.

        """
        if not (isinstance(stage, str)) or not (isinstance(cwd, Path) or cwd is None) or not (isinstance(check, bool)):
            argument_error: str = "command: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        _command_arguments(argv, timeout)
        resolved: str | None = shutil.which(argv[0]) if argv else None
        if resolved is None:
            message = f"executable not found: {argv[0] if argv else '<empty argv>'}"
            raise FileNotFoundError(message)

        def attempt() -> subprocess.CompletedProcess[str]:
            try:
                return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved argv; no shell.
                    [resolved, *argv[1:]],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise self.failure(stage, "tool-timeout", {"argv": list(argv), "exception": repr(exc)}) from exc
            except ConnectionError as exc:
                raise self.failure(stage, "network", {"argv": list(argv), "exception": repr(exc)}) from exc
            except OSError as exc:
                raise self.failure(stage, "other", {"argv": list(argv), "exception": repr(exc)}) from exc

        done: subprocess.CompletedProcess[str] = retry_call(attempt)
        result: CommandResult = CommandResult(tuple(argv), done.returncode, done.stdout, done.stderr)
        if check and result.exit:
            raise self.failure(stage, "other", result.to_json())
        return result

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def portfolio(
        self,
        stage: str,
        operation: Callable[P, R],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Call a statically selected portfolio operation with its actual signature.

        Returns:
            The actual producer result with its statically declared return type preserved.

        Raises:
            StepError: The portfolio operation failed.
            TypeCheckError: A runtime contract failed.
            TypeError: The dispatch arguments have invalid types.

        """
        if not isinstance(stage, str) or not callable(operation):
            message: str = "Portfolio dispatch requires a string stage and a callable operation"
            raise TypeError(message)
        try:
            # redirect_stdout is process-global. Serializing imported calls avoids one
            # worker restoring stdout while another is still printing diagnostics.
            with _IMPORT_LOCK, contextlib.redirect_stdout(sys.stderr):
                beadgraph.BD_GATE = bd_gate
                return operation(*args, **kwargs)
        except StepError, TypeCheckError:
            raise
        except Exception as exc:
            cause: str = exc.cause if isinstance(exc, beadgraph.GraphError) else "other"
            raise self.failure(
                stage,
                cause,
                {
                    "operation": repr(operation),
                    "traceback": traceback.format_exc(),
                },
            ) from exc

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def bd(self, args: list[str], *, stage: str, stdin: str | None = None) -> str:
        """Make one bd attempt within the caller's keyed operation.

        Returns:
            The validated command output.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if (
            not (isinstance(args, list))
            or not (isinstance(stage, str))
            or not (isinstance(stdin, str) or stdin is None)
        ):
            argument_error: str = "bd: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        return check_type(
            self.portfolio(
                stage,
                beadgraph.run_bd,
                args,
                env_path("ATW_CONTROL_REPO"),
                stdin,
            ),
            str,
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def git(
        self,
        repo: Path,
        args: list[str],
        *,
        stage: str,
        branch: str = "main",
        remote: str = "origin",
    ) -> CommandResult:
        """Retry index contention and structurally verified push divergence.

        Returns:
            The successful Git command result.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if (
            not (isinstance(repo, Path))
            or not (isinstance(args, list))
            or not (isinstance(stage, str))
            or not (isinstance(branch, str))
            or not (isinstance(remote, str))
        ):
            argument_error: str = "git: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)

        def attempt() -> CommandResult:
            result: CommandResult = self.command(
                ["git", *args],
                stage=stage,
                cwd=repo,
                timeout=seconds("ATW_GIT_TIMEOUT", 120),
                check=False,
            )
            if not result.exit:
                return result
            lock: CommandResult = self.command(
                ["git", "rev-parse", "--git-path", "index.lock"],
                stage=stage,
                cwd=repo,
            )
            if (repo / lock.stdout.strip()).exists():
                raise self.failure(stage, "contention", result.to_json())
            if args and args[0] == "push":
                self.command(
                    ["git", "fetch", remote],
                    stage=stage,
                    cwd=repo,
                    timeout=seconds("ATW_GIT_TIMEOUT", 120),
                )
                ancestor: CommandResult = self.command(
                    [
                        "git",
                        "merge-base",
                        "--is-ancestor",
                        f"{remote}/{branch}",
                        "HEAD",
                    ],
                    stage=stage,
                    cwd=repo,
                    check=False,
                )
                if ancestor.exit == 1:
                    self.git(repo, ["pull", "--rebase", remote, branch], stage=stage)
                    raise self.failure(stage, "contention", result.to_json())
                if ancestor.exit:
                    raise self.failure(stage, "other", ancestor.to_json())
            raise self.failure(stage, "other", result.to_json())

        return retry_call(attempt)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def operation[T](self, stage: str, action: Callable[[], T]) -> T:
        """Retry a whole operation whose body refreshes its inputs before writing.

        For a Story write the body loads beadgraph first, then calls write_story;
        this avoids retrying a create whose first attempt may already have applied.

        Returns:
            The successful operation result.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(stage, str)) or not (callable(action)):
            argument_error: str = "operation: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)

        def attempt() -> T:
            try:
                return action()
            except StepError, TypeCheckError:
                raise
            except Exception as exc:
                cause: str = exc.cause if isinstance(exc, beadgraph.GraphError) else "other"
                raise self.failure(
                    stage,
                    cause,
                    {"traceback": traceback.format_exc()},
                ) from exc

        return retry_call(attempt)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def polyrepo(
        self,
        args: Sequence[str],
        *,
        stage: str,
        timeout: float = 300,
    ) -> CommandResult:
        """Run the configured plugin's repository CLI directly.

        Returns:
            The repository CLI result.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        _command_arguments(args, timeout)
        if not isinstance(stage, str):
            argument_error: str = "polyrepo: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        script: Path = self.plugin / "skills/polyrepo-repo/scripts/polyrepo.py"
        return self.command(
            ["uv", "run", str(script), *args, "--json"],
            stage=stage,
            timeout=timeout,
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def cdk(
        self,
        subcommand: str,
        args: Sequence[str],
        *,
        target: DeploymentTarget,
        stage: str,
        timeout: float = 300,
    ) -> CommandResult:
        """Keep the AWS profile explicit and immediately after the subcommand.

        Returns:
            The CDK command result.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if (
            not (isinstance(subcommand, str))
            or not isinstance(target, DeploymentTarget)
            or not (isinstance(stage, str))
        ):
            argument_error: str = "cdk: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        _command_arguments(args, timeout)
        return self.command(
            ["cdk", subcommand, "--profile", target.profile, *args],
            cwd=target.repository,
            stage=stage,
            timeout=timeout,
        )
