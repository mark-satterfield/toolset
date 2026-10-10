"""Deterministic calls with structured failures and one retry boundary."""

from __future__ import annotations

import contextlib
import importlib
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
from typing import TYPE_CHECKING

from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from .models import RetryExhaustedError, StepError
from .tool_locks import bd_gate, control_repo, seconds

if TYPE_CHECKING:
    from types import ModuleType

RETRY_CAUSES = frozenset({"contention", "bd-timeout", "tool-timeout", "network"})
_LOG = logging.getLogger(__name__)
_MAX_ATTEMPTS = 3
_IMPORT_LOCK = threading.RLock()


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

    """
    delay = 30.0
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

    """
    value = os.environ.get(name, "").strip()
    stage = "input"
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

    """
    root = env_path("ATW_ARCH_PATH")
    result = (root / relative).resolve()
    stage = "input"
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
        """Validate every constructed field, including nested collection entries."""
        check_type(self.argv, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.exit, int, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.stdout, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.stderr, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@dataclass(frozen=True)
class DeploymentTarget:
    """Repository and explicit AWS profile for a deployment command."""

    repository: Path
    profile: str

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every constructed field, including nested collection entries."""
        check_type(self.repository, Path, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.profile, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


class Tools:
    """One run's deterministic tool boundary and private incident evidence directory."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self, evidence: Path) -> None:
        """Bind the evidence directory for deterministic operation failures."""
        self.evidence = evidence
        self.plugin = Path(__file__).resolve().parents[2]

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def failure(self, stage: str, cause: str, facts: Mapping[str, object]) -> StepError:
        """Persist evidence off stdout and return the structured step failure.

        Returns:
            The failure referencing its evidence file.

        """
        self.evidence.mkdir(parents=True, exist_ok=True)
        path = self.evidence / f"tool-{uuid.uuid4().hex}.json"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dict(facts), handle, ensure_ascii=False, default=str)
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
            ValueError: The timeout is invalid.
            FileNotFoundError: The executable cannot be resolved.

        """
        if not 0 < timeout < float("inf"):
            message = "command timeout must be positive and finite"
            raise ValueError(message)
        resolved = shutil.which(argv[0]) if argv else None
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

        done = retry_call(attempt)
        result = CommandResult(tuple(argv), done.returncode, done.stdout, done.stderr)
        if check and result.exit:
            raise self.failure(stage, "other", vars(result))
        return result

    def _portfolio_module(self, module: str) -> ModuleType:
        with _IMPORT_LOCK:
            directory = str(self.plugin / "scripts/portfolio")
            if directory not in sys.path:
                sys.path.insert(0, directory)
            with contextlib.redirect_stdout(sys.stderr):
                imported = importlib.import_module(module)
                graph = importlib.import_module("beadgraph")
            vars(graph)["BD_GATE"] = bd_gate
        return imported

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def portfolio(
        self,
        module: str,
        function: str,
        *args: object,
        stage: str,
        **kwargs: object,
    ) -> object:
        """Import a portfolio function and make one attempt.

        Returns:
            The unparsed result, validated by the caller at its contract boundary.

        Raises:
            StepError: The portfolio operation failed.
            TypeCheckError: A runtime contract failed.

        """
        try:
            imported = self._portfolio_module(module)
            # redirect_stdout is process-global. Serializing imported calls avoids one
            # worker restoring stdout while another is still printing diagnostics.
            with _IMPORT_LOCK, contextlib.redirect_stdout(sys.stderr):
                return check_type(getattr(imported, function), Callable[..., object])(*args, **kwargs)
        except StepError, TypeCheckError:
            raise
        except Exception as exc:
            loaded_graph = sys.modules.get("beadgraph")
            cause = check_type(exc.cause, str) if loaded_graph and isinstance(exc, loaded_graph.GraphError) else "other"
            raise self.failure(
                stage,
                cause,
                {
                    "module": module,
                    "function": function,
                    "traceback": traceback.format_exc(),
                },
            ) from exc

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def bd(self, args: list[str], *, stage: str, stdin: str | None = None) -> str:
        """Make one bd attempt within the caller's keyed operation.

        Returns:
            The validated command output.

        """
        return check_type(
            self.portfolio(
                "beadgraph",
                "_bd",
                args,
                env_path("ATW_CONTROL_REPO"),
                stdin,
                stage=stage,
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

        """

        def attempt() -> CommandResult:
            result = self.command(
                ["git", *args],
                stage=stage,
                cwd=repo,
                timeout=seconds("ATW_GIT_TIMEOUT", 120),
                check=False,
            )
            if not result.exit:
                return result
            lock = self.command(
                ["git", "rev-parse", "--git-path", "index.lock"],
                stage=stage,
                cwd=repo,
            )
            if (repo / lock.stdout.strip()).exists():
                raise self.failure(stage, "contention", vars(result))
            if args and args[0] == "push":
                self.command(
                    ["git", "fetch", remote],
                    stage=stage,
                    cwd=repo,
                    timeout=seconds("ATW_GIT_TIMEOUT", 120),
                )
                ancestor = self.command(
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
                    raise self.failure(stage, "contention", vars(result))
                if ancestor.exit:
                    raise self.failure(stage, "other", vars(ancestor))
            raise self.failure(stage, "other", vars(result))

        return retry_call(attempt)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def owner_need(self, epic: str, title: str, need: object, *, run: str) -> Path:
        """Use the driver's owner-inbox writer and configured destination.

        Returns:
            The created owner-inbox artifact path.

        Raises:
            TypeCheckError: The writer returned a value outside its contract.

        """
        stage = "owner-inbox"
        env_path("ATW_OWNER_INBOX")
        try:
            with _IMPORT_LOCK, contextlib.redirect_stdout(sys.stderr):
                directory = str(control_repo() / "ops/sdlc-automation")
                if directory not in sys.path:
                    sys.path.insert(0, directory)
                module = importlib.import_module("ownerinbox")
                return check_type(module.write_need(epic, title, need, beads=[epic], run=run), Path)
        except TypeCheckError:
            raise
        except Exception as exc:
            raise self.failure(
                stage,
                "other",
                {"traceback": traceback.format_exc()},
            ) from exc

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def operation[T](self, stage: str, action: Callable[[], T]) -> T:
        """Retry a whole operation whose body refreshes its inputs before writing.

        For a Story write the body loads beadgraph first, then calls write_story;
        this avoids retrying a create whose first attempt may already have applied.

        Returns:
            The successful operation result.

        """

        def attempt() -> T:
            try:
                return action()
            except StepError, TypeCheckError:
                raise
            except Exception as exc:
                loaded_graph = sys.modules.get("beadgraph")
                cause = exc.cause if loaded_graph and isinstance(exc, loaded_graph.GraphError) else "other"
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

        """
        script = self.plugin / "skills/polyrepo-repo/scripts/polyrepo.py"
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

        """
        return self.command(
            ["cdk", subcommand, "--profile", target.profile, *args],
            cwd=target.repository,
            stage=stage,
            timeout=timeout,
        )
