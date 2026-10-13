"""Small isolated checks of the core's file helpers: the work directory, safe names and JSON files."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.core.agents import strict_json
from orchestrator.core.io import WORK_DIRECTORY_PARTS, safe_key, work_directory, write_json

LONGEST: int = 120


def check_names(root: Path) -> None:
    """Check the name an identifier is given as a path segment, and an Epic's work directory."""
    require(safe_key("ssbd-q5km.1") == "ssbd-q5km.1", "a bead id is already a safe name")
    require(safe_key("  a/b c  ") == "a_b_c", "other characters become one underscore, none at the ends")
    require(len(safe_key("x" * 300)) == LONGEST, "a safe name is cut to 120 characters")
    work: Path = work_directory(root, "ssbd-q5km.1")
    require(
        work == root.joinpath(*WORK_DIRECTORY_PARTS, "ssbd-q5km.1"),
        "the work directory is under the control repository",
    )
    require(work.parent.parent.name == "workflow-runs", "the work directory is two levels under workflow-runs")
    with expected_error(ValueError):
        work_directory(root, "///")
    report("PASS: safe names and the Epic work directory")


def check_json(root: Path) -> None:
    """Check that a JSON file is written whole and read back strictly."""
    path: Path = root / "nested" / "value.json"
    write_json(path, {"b": 1, "a": [True, None]})
    require(strict_json(path) == {"a": [True, None], "b": 1}, "a written object is read back")
    require(not list(path.parent.glob("tmp*")), "no temporary file is left beside it")
    path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with expected_error(ValueError):
        strict_json(path)
    report("PASS: JSON files are written whole and a duplicate key is refused")


def main() -> None:
    """Run the checks in a temporary directory."""
    directory: str
    with tempfile.TemporaryDirectory() as directory:
        root: Path = Path(directory)
        check_names(root)
        check_json(root)


if __name__ == "__main__":
    main()
