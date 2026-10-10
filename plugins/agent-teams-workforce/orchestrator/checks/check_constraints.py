"""Check the section 2 guard against a disposable vault, without agent sessions."""

from __future__ import annotations

import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Isolated fixture uses fixed Git argv without a shell.
import sys
import tempfile
from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.checks.check_support import report, require
from orchestrator.core.constraints import Section2Guard
from orchestrator.core.models import StepError
from orchestrator.core.tools import Tools


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract.

    Raises:
        AssertionError: A changed constraint was accepted.

    """
    with tempfile.TemporaryDirectory(prefix="atw-guard-") as scratch:
        root = Path(scratch)
        os.environ["ATW_CONTROL_REPO"] = str(root / "control")
        vault = root / "vault"
        vault.mkdir()

        def git(*args: str) -> None:
            executable = shutil.which("git")
            if executable is None:
                message = "git executable unavailable"
                raise FileNotFoundError(message)
            subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed Git fixture commands and local temporary path.
                [executable, "-C", str(vault), *args],
                check=True,
                capture_output=True,
                timeout=10,
            )

        git("init", "-b", "main")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        arch = vault / "architecture"
        note = arch / "arc42/02-architecture-constraints/README.md"
        note.parent.mkdir(parents=True)
        note.write_text("Owner constraints\n")
        git("add", "architecture")
        git("commit", "-m", "fixture baseline")
        stops = []
        guard = Section2Guard(
            arch,
            Tools(root / "evidence"),
            lambda: stops.append(True),
        )
        with guard.session("unchanged"):
            pass
        try:
            with guard.session("changed"):
                note.write_text("unauthorized edit\n")
        except StepError as exc:
            require(exc.stage == "constraints-written", "exc.stage == 'constraints-written'")
        else:
            message = "guard accepted an uncommitted write"
            raise AssertionError(message)
        require(note.read_text() == "Owner constraints\n", "note.read_text() == 'Owner constraints\\n'")
        require(stops, "stops")
        require(list(guard.root.glob("changed-*")), "list(guard.root.glob('changed-*'))")
        with guard.session("owner-commit"):
            note.write_text("Owner revised constraints\n")
            git("add", "architecture")
            git("commit", "-m", "owner fixture revision")
        require(note.read_text() == "Owner revised constraints\n", "note.read_text() == 'Owner revised constraints\\n'")
        require(not list(guard.live.iterdir()), "not list(guard.live.iterdir())")
    report(
        "PASS: unchanged section 2 accepted; edits preserved and restored; owner commit accepted; live markers cleared",
    )


if __name__ == "__main__":
    main()
