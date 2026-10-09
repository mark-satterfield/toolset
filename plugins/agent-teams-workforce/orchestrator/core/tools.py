"""Deterministic calls with structured failures and one retry boundary."""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from .models import StepError
from .tool_locks import bd_gate, control_repo, seconds

T = TypeVar("T")
RETRY_CAUSES = frozenset({"contention", "bd-timeout"})
_IMPORT_LOCK = threading.RLock()


def retry_call(
    action: Callable[[], T], *, sleep: Callable[[float], None] = time.sleep
) -> T:
    """Retry only measured contention/timeouts; action must reread keyed write inputs."""
    delay = 30
    while True:
        try:
            return action()
        except StepError as exc:
            if exc.cause not in RETRY_CAUSES:
                raise
            print(f"{exc.stage}: {exc.cause}; retry in {delay}s", file=sys.stderr)
            sleep(delay)
            delay = min(delay * 2, 1800)


def env_path(name: str) -> Path:
    """Resolve a required project path without inventing a machine-local default."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise StepError("input", "other", (f"{name} is required",))
    return Path(value).expanduser().resolve()


def vault_path(relative: str) -> Path:
    """Resolve a path within the configured architecture root."""
    root = env_path("ATW_ARCH_PATH")
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise StepError("input", "other", (f"path escapes ATW_ARCH_PATH: {relative}",))
    return result


@dataclass(frozen=True)
class CommandResult:
    """An executable's factual result; stderr never determines its cause."""

    argv: tuple[str, ...]
    exit: int
    stdout: str
    stderr: str


class Tools:
    """One run's deterministic tool boundary and private incident evidence directory."""

    def __init__(self, evidence: Path) -> None:
        self.evidence = evidence
        self.plugin = Path(__file__).resolve().parents[2]

    def failure(self, stage: str, cause: str, facts: dict[str, Any]) -> StepError:
        """Persist evidence off stdout and return the structured step failure."""
        self.evidence.mkdir(parents=True, exist_ok=True)
        path = self.evidence / f"tool-{uuid.uuid4().hex}.json"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(facts, handle, ensure_ascii=False, default=str)
        return StepError(stage, cause, (str(path),))

    def command(
        self,
        argv: Sequence[str],
        *,
        stage: str,
        cwd: Path | None = None,
        timeout: float = 120,
        check: bool = True,
    ) -> CommandResult:
        """Run an executable once, with no shell and a finite timeout."""
        try:
            if not 0 < timeout < float("inf"):
                raise ValueError("command timeout must be positive and finite")
            done = subprocess.run(
                list(argv),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            raise self.failure(
                stage, "other", {"argv": list(argv), "exception": repr(exc)}
            ) from exc
        result = CommandResult(tuple(argv), done.returncode, done.stdout, done.stderr)
        if check and result.exit:
            raise self.failure(stage, "other", vars(result))
        return result

    def portfolio(
        self, module: str, function: str, *args: Any, stage: str, **kwargs: Any
    ) -> Any:
        """Import a portfolio function and make one attempt; callers own keyed retries."""
        try:
            with _IMPORT_LOCK:
                directory = str(self.plugin / "scripts/portfolio")
                if directory not in sys.path:
                    sys.path.insert(0, directory)
                with contextlib.redirect_stdout(sys.stderr):
                    imported = importlib.import_module(module)
                    graph = importlib.import_module("beadgraph")
                graph.BD_GATE = bd_gate
            # redirect_stdout is process-global. Serializing imported calls avoids one
            # worker restoring stdout while another is still printing diagnostics.
            with _IMPORT_LOCK, contextlib.redirect_stdout(sys.stderr):
                return getattr(imported, function)(*args, **kwargs)
        except StepError:
            raise
        except Exception as exc:
            graph = sys.modules.get("beadgraph")
            cause = (
                exc.cause if graph and isinstance(exc, graph.GraphError) else "other"
            )
            raise self.failure(
                stage,
                cause,
                {
                    "module": module,
                    "function": function,
                    "traceback": traceback.format_exc(),
                },
            ) from exc

    def bd(self, args: list[str], *, stage: str, stdin: str | None = None) -> str:
        """One bd attempt; a caller retries its whole keyed operation, not a create."""
        return self.portfolio(
            "beadgraph", "_bd", args, env_path("ATW_CONTROL_REPO"), stdin, stage=stage
        )

    def git(
        self,
        repo: Path,
        args: list[str],
        *,
        stage: str,
        branch: str = "main",
        remote: str = "origin",
    ) -> CommandResult:
        """Retry index contention and structurally verified push divergence."""

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
                ["git", "rev-parse", "--git-path", "index.lock"], stage=stage, cwd=repo
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

    def owner_need(self, epic: str, title: str, need: Any, *, run: str) -> Path:
        """Use the driver's existing owner-inbox writer and configured destination."""
        try:
            env_path("ATW_OWNER_INBOX")
            with _IMPORT_LOCK, contextlib.redirect_stdout(sys.stderr):
                directory = str(control_repo() / "ops/sdlc-automation")
                if directory not in sys.path:
                    sys.path.insert(0, directory)
                module = importlib.import_module("ownerinbox")
                return module.write_need(epic, title, need, beads=[epic], run=run)
        except Exception as exc:
            raise self.failure(
                "owner-inbox", "other", {"traceback": traceback.format_exc()}
            ) from exc

    def operation(self, stage: str, action: Callable[[], T]) -> T:
        """Retry a whole operation whose body refreshes its inputs before writing.

        For a Story write the body loads beadgraph first, then calls write_story;
        this avoids retrying a create whose first attempt may already have applied.
        """

        def attempt() -> T:
            try:
                return action()
            except StepError:
                raise
            except Exception as exc:
                graph = sys.modules.get("beadgraph")
                cause = (
                    exc.cause
                    if graph and isinstance(exc, graph.GraphError)
                    else "other"
                )
                raise self.failure(
                    stage, cause, {"traceback": traceback.format_exc()}
                ) from exc

        return retry_call(attempt)

    def polyrepo(
        self, args: Sequence[str], *, stage: str, timeout: float = 300
    ) -> CommandResult:
        """Run the configured plugin's repository CLI directly."""
        script = self.plugin / "skills/polyrepo-repo/scripts/polyrepo.py"
        return self.command(
            ["uv", "run", str(script), *args, "--json"], stage=stage, timeout=timeout
        )

    def cdk(
        self,
        subcommand: str,
        args: Sequence[str],
        *,
        repo: Path,
        profile: str,
        stage: str,
        timeout: float = 300,
    ) -> CommandResult:
        """Keep the AWS profile explicit and immediately after the subcommand."""
        return self.command(
            ["cdk", subcommand, "--profile", profile, *args],
            cwd=repo,
            stage=stage,
            timeout=timeout,
        )
