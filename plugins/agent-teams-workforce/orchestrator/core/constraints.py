"""One standing section 2 snapshot shared by overlapping reasoning sessions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .io import write_json
from .models import StepError
from .tool_locks import LockTimeout, control_repo, file_lock, seconds
from .tools import Tools


class Section2Guard:
    def __init__(self, arch: Path, tools: Tools, stop: Callable[[], None]) -> None:
        self.arch = arch.resolve()
        self.tools = tools
        self.stop = stop
        key = hashlib.sha256(str(self.arch).encode()).hexdigest()[:16]
        self.root = control_repo() / "ops/sdlc-automation/state/section2-guard" / key
        self.live = self.root / "live"
        self.live.mkdir(parents=True, exist_ok=True)

    def _git(self, *args: str) -> str:
        return self.tools.command(
            ["git", "-C", str(self.arch), *args], stage="constraints-written"
        ).stdout.strip()

    def _take(self) -> dict:
        value = self.tools.portfolio(
            "archstate",
            "snapshot_constraints",
            str(self.arch),
            keep=True,
            stage="constraints-written",
        )
        if value.get("error") or value.get("gitError"):
            raise self.tools.failure("constraints-written", "other", value)
        value["head"] = self._git("rev-parse", "HEAD")
        kept = self.root / "kept"
        if kept.exists():
            shutil.rmtree(kept)
        shutil.move(value["kept"], kept)
        value["kept"] = str(kept)
        write_json(self.root / "snapshot.json", value)
        return value

    def _prune(self) -> None:
        for path in self.live.iterdir():
            data = json.loads(path.read_text())
            try:
                os.kill(data["pid"], 0)
            except ProcessLookupError:
                path.unlink()

    def _check(self) -> None:
        saved = json.loads((self.root / "snapshot.json").read_text())
        now = self.tools.portfolio(
            "archstate",
            "snapshot_constraints",
            str(self.arch),
            stage="constraints-written",
        )
        if now.get("error") or now.get("gitError"):
            raise self.tools.failure("constraints-written", "other", now)
        if all(
            saved.get(key) == now.get(key) for key in ("digest", "exists", "gitStatus")
        ):
            return
        head = self._git("rev-parse", "HEAD")
        folder = str(self.arch / "arc42/02-architecture-constraints")
        commits = self._git(
            "log", "--format=%B%x00", f"{saved['head']}..{head}", "--", folder
        )
        ancestor = self.tools.command(
            [
                "git",
                "-C",
                str(self.arch),
                "merge-base",
                "--is-ancestor",
                saved["head"],
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
            and not any(
                line.startswith("Pipeline-Run:") for line in commits.splitlines()
            )
        ):
            self._take()
            return
        changed = self.root / (
            "changed-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        )
        source = Path(now["folder"])
        if source.exists():
            shutil.copytree(source, changed)
        else:
            changed.mkdir()
        sessions = {p.name: json.loads(p.read_text()) for p in self.live.iterdir()}
        result = self.tools.portfolio(
            "archstate",
            "restore_constraints",
            str(self.arch),
            saved["kept"],
            stage="constraints-written",
        )
        if not saved["exists"] and source.exists() and not any(source.iterdir()):
            source.rmdir()
        self.stop()
        raise self.tools.failure(
            "constraints-written",
            "other",
            {"changedCopy": str(changed), "sessions": sessions, "restore": result},
        )

    @contextmanager
    def session(self, session_id: str) -> Iterator[None]:
        marker = self.live / session_id
        wait = seconds("ATW_ARCH_LOCK_WAIT", 120)
        try:
            with file_lock(self.root / "guard.lock", wait):
                self._prune()
                if not any(self.live.iterdir()):
                    self._take()
                write_json(marker, {"pid": os.getpid()})
            try:
                yield
            finally:
                with file_lock(self.root / "guard.lock", wait):
                    try:
                        self._check()
                    finally:
                        marker.unlink(missing_ok=True)
        except LockTimeout as exc:
            raise StepError("constraints-written", "contention", (str(exc),)) from exc
        except StepError:
            raise
        except Exception as exc:
            raise self.tools.failure(
                "constraints-written", "other", {"error": repr(exc)}
            ) from exc
