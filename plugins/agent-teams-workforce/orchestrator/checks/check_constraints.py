"""Check the section 2 guard against a disposable vault, without agent sessions."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.core.constraints import Section2Guard
from orchestrator.core.models import StepError
from orchestrator.core.tools import Tools


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="atw-guard-") as scratch:
        root = Path(scratch)
        os.environ["ATW_CONTROL_REPO"] = str(root / "control")
        vault = root / "vault"
        vault.mkdir()

        def git(*args: str) -> None:
            subprocess.run(
                ["git", "-C", str(vault), *args],
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
            arch, Tools(root / "evidence"), lambda: stops.append(True)
        )
        with guard.session("unchanged"):
            pass
        try:
            with guard.session("changed"):
                note.write_text("unauthorized edit\n")
        except StepError as exc:
            assert exc.stage == "constraints-written"
        else:
            raise AssertionError("guard accepted an uncommitted write")
        assert note.read_text() == "Owner constraints\n" and stops
        assert list(guard.root.glob("changed-*"))
        with guard.session("owner-commit"):
            note.write_text("Owner revised constraints\n")
            git("add", "architecture")
            git("commit", "-m", "owner fixture revision")
        assert note.read_text() == "Owner revised constraints\n"
        assert not list(guard.live.iterdir())
    print(
        "PASS: unchanged section 2 accepted; edits preserved and restored; owner commit accepted; live markers cleared"
    )


if __name__ == "__main__":
    main()
