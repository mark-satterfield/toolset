"""One standing section 2 snapshot shared by overlapping reasoning sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import contracts

    from orchestrator.core.tools import CommandResult

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import archstate
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

from .io import JsonValue, json_object, write_json
from .models import StepError
from .tool_locks import LockTimeoutError, control_repo, file_lock, seconds
from .tools import Tools


class Section2Guard:
    """Detect changes to owner-managed architecture constraints during sessions."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self, arch: Path, tools: Tools, stop: Callable[[], None]) -> None:
        """Bind the shared snapshot location and the session-stop callback.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(arch, Path)) or not (isinstance(tools, Tools)) or not (callable(stop)):
            argument_error: str = "__init__: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        self.arch: Path = arch.resolve()
        self.tools: Tools = tools
        self.stop: Callable[[], None] = stop
        key: str = hashlib.sha256(str(self.arch).encode()).hexdigest()[:16]
        self.root: Path = control_repo() / "ops/sdlc-automation/state/section2-guard" / key
        self.live: Path = self.root / "live"
        self.live.mkdir(parents=True, exist_ok=True)

    def _git(self, *args: str) -> str:
        return self.tools.command(
            ["git", "-C", str(self.arch), *args],
            stage="constraints-written",
        ).stdout.strip()

    def _take(self) -> dict[str, JsonValue]:
        stage: str = "constraints-written"
        value: dict[str, JsonValue] = json_object(
            self.tools.portfolio("constraints-written", archstate.snapshot_constraints, str(self.arch), keep=True),
        )
        if value.get("error") or value.get("gitError"):
            raise self.tools.failure(stage, "other", value)
        value["head"] = self._git("rev-parse", "HEAD")
        kept: Path = self.root / "kept"
        if kept.exists():
            shutil.rmtree(kept)
        shutil.move(check_type(value["kept"], str), kept)
        value["kept"] = str(kept)
        write_json(self.root / "snapshot.json", value)
        return value

    def _prune(self) -> None:
        path: Path
        for path in self.live.iterdir():
            data: dict[str, JsonValue] = json_object(json.loads(path.read_text(encoding="utf-8")))
            try:
                os.kill(check_type(data["pid"], int), 0)
            except ProcessLookupError:
                path.unlink()

    def _check(self) -> None:
        stage: str = "constraints-written"
        saved: dict[str, JsonValue] = json_object(json.loads((self.root / "snapshot.json").read_text(encoding="utf-8")))
        now: dict[str, JsonValue] = json_object(
            self.tools.portfolio("constraints-written", archstate.snapshot_constraints, str(self.arch)),
        )
        if now.get("error") or now.get("gitError"):
            raise self.tools.failure(stage, "other", now)
        if all(saved.get(key) == now.get(key) for key in ("digest", "exists", "gitStatus")):
            return
        head: str = self._git("rev-parse", "HEAD")
        folder: str = str(self.arch / "arc42/02-architecture-constraints")
        commits: str = self._git(
            "log",
            "--format=%B%x00",
            f"{saved['head']}..{head}",
            "--",
            folder,
        )
        ancestor: CommandResult = self.tools.command(
            [
                "git",
                "-C",
                str(self.arch),
                "merge-base",
                "--is-ancestor",
                check_type(saved["head"], str),
                head,
            ],
            stage="constraints-written",
            check=False,
        )
        if (
            not now["gitStatus"]
            and head != saved["head"]
            and ancestor.exit == 0
            and commits
            and not any(line.startswith("Pipeline-Run:") for line in commits.splitlines())
        ):
            self._take()
            return
        changed: Path = self.root / ("changed-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
        source: Path = Path(check_type(now["folder"], str))
        if source.exists():
            shutil.copytree(source, changed)
        else:
            changed.mkdir()
        sessions: dict[str, dict[str, JsonValue]] = {
            p.name: json_object(json.loads(p.read_text(encoding="utf-8"))) for p in self.live.iterdir()
        }
        result: contracts.ConstraintRestore | contracts.FileError = self.tools.portfolio(
            "constraints-written",
            archstate.restore_constraints,
            str(self.arch),
            check_type(saved["kept"], str),
        )
        restore: dict[str, JsonValue]
        if "error" in result:
            error: object = result.get("error")
            if not isinstance(error, str):
                message: str = "Constraint restore error must be a string"
                raise TypeError(message)
            restore = {"error": error}
        else:
            restore = {
                "folder": result["folder"],
                "written": list(result["written"]),
                "deleted": list(result["deleted"]),
                "summary": dict(result["summary"]),
            }
        if not saved["exists"] and source.exists() and not any(source.iterdir()):
            source.rmdir()
        self.stop()
        raise self.tools.failure(
            stage,
            "other",
            {"changedCopy": str(changed), "sessions": sessions, "restore": restore},
        )

    @contextmanager
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def session(self, session_id: str) -> Generator[None]:
        """Guard one session against writes to the owner's constraints.

        Yields:
            Control while the session is registered with the shared guard.

        Raises:
            TypeError: An argument violates the declared input contract.
            StepError: A lock or guarded session failed.
            TypeCheckError: A runtime contract failed.

        """
        if not (isinstance(session_id, str)):
            argument_error: str = "session: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        stage: str = "constraints-written"
        marker: Path = self.live / session_id
        wait: float = seconds("ATW_ARCH_LOCK_WAIT", 120)
        try:
            yield from self._guarded_session(marker, wait)
        except LockTimeoutError as exc:
            raise StepError(stage, "contention", (str(exc),)) from exc
        except StepError, TypeCheckError:
            raise
        except Exception as exc:
            raise self.tools.failure(
                stage,
                "other",
                {"error": repr(exc)},
            ) from exc

    def _register(self, marker: Path, wait: float) -> None:
        with file_lock(self.root / "guard.lock", wait):
            self._prune()
            if not any(self.live.iterdir()):
                self._take()
            write_json(marker, {"pid": os.getpid()})

    def _finish(self, marker: Path, wait: float) -> None:
        with file_lock(self.root / "guard.lock", wait):
            try:
                self._check()
            finally:
                marker.unlink(missing_ok=True)

    def _guarded_session(self, marker: Path, wait: float) -> Generator[None]:
        self._register(marker, wait)
        try:
            yield
        finally:
            self._finish(marker, wait)
