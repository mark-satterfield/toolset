"""Run every check script in this directory; print one line per check and exit non-zero unless all pass.

A check is any Python file beside this one that has a `__main__` entry point, so a new check is
picked up without registration. A check that declares `--control-repo` or `--survey-dir`
receives it: the control repository, or a saved architecture directory of that repository.

A saved survey is bound to the documents and repository trees it was made from, so it stops being
reusable when they change. A check that declares `--survey-dir` is therefore run against the saved
directories newest first until one passes, and its line names the directory that passed and how
many newer ones did not.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs this interpreter on the check scripts beside this file with fixed argv, no shell.
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, assert_never

CONTROL_REPO_VARIABLES: Final[tuple[str, ...]] = ("ATW_CONTROL_REPO", "SKILLSPOKE_CC")
SAVED_ARCHITECTURE_GLOB: Final[str] = ".claude/workflow-runs/artifacts/*/architecture"
SURVEY_FILE: Final[str] = "survey.json"
ENTRY_POINT: Final[str] = 'if __name__ == "__main__":'
OPTION_CONTROL_REPO: Final[str] = "--control-repo"
OPTION_SURVEY_DIR: Final[str] = "--survey-dir"
DECLARED_OPTION: Final[re.Pattern[str]] = re.compile(r'add_argument\(\s*"(--[a-z][a-z-]*)"')
DEFAULT_TIMEOUT_SECONDS: Final[int] = 300


class Outcome(StrEnum):
    """What happened to one check."""

    PASSED = "PASS"
    FAILED = "FAIL"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class Result:
    """The outcome of one check, a note for its line, and the full output of a failure."""

    name: str
    outcome: Outcome
    note: str
    output: str


@dataclass(frozen=True, slots=True)
class Supplies:
    """The value available for each option a check may declare, or why it is unavailable."""

    control_repo: Path | None
    control_repo_problem: str
    survey_dirs: tuple[Path, ...]
    survey_dir_problem: str


def discover(directory: Path) -> list[Path]:
    """List the check scripts in a directory: every Python file with an entry point but this one.

    Returns:
        The check scripts, sorted by name.

    Raises:
        TypeError: directory is not a Path.
        ValueError: directory is not an existing directory.

    """
    if not isinstance(directory, Path):
        argument_error: str = "discover requires a Path"
        raise TypeError(argument_error)
    if not directory.is_dir():
        message: str = f"not a directory: {directory}"
        raise ValueError(message)
    own: Path = Path(__file__).resolve()
    return [
        path
        for path in sorted(directory.glob("*.py"))
        if path.resolve() != own and ENTRY_POINT in path.read_text(encoding="utf-8")
    ]


def saved_architectures(control: Path) -> tuple[Path, ...]:
    """List the saved architecture directories of a control repository that hold a survey.

    Returns:
        The directories, the one whose survey was written last first.

    Raises:
        TypeError: control is not a Path.

    """
    if not isinstance(control, Path):
        argument_error: str = "saved_architectures requires a Path"
        raise TypeError(argument_error)
    surveys: list[Path] = [
        directory / SURVEY_FILE
        for directory in control.glob(SAVED_ARCHITECTURE_GLOB)
        if (directory / SURVEY_FILE).is_file()
    ]
    surveys.sort(key=lambda survey: (survey.stat().st_mtime, str(survey)), reverse=True)
    return tuple(survey.parent for survey in surveys)


def supplies(control: Path | None, survey_dir: Path | None) -> Supplies:
    """Resolve the option values the checks receive from the control repository.

    Returns:
        Each value, or the reason it cannot be supplied.

    Raises:
        TypeError: control or survey_dir is neither a Path nor None.

    """
    if control is not None and not isinstance(control, Path):
        control_error: str = "control must be a Path or None"
        raise TypeError(control_error)
    if survey_dir is not None and not isinstance(survey_dir, Path):
        survey_error: str = "survey_dir must be a Path or None"
        raise TypeError(survey_error)
    named: tuple[Path, ...] = (survey_dir,) if survey_dir is not None else ()
    if control is None:
        unnamed: str = f"control repository not named (set {CONTROL_REPO_VARIABLES[-1]} or pass --control-repo)"
        return Supplies(None, unnamed, named, "" if named else unnamed)
    directories: tuple[Path, ...] = named or saved_architectures(control)
    return Supplies(
        control if control.is_dir() else None,
        "" if control.is_dir() else f"no control repository at {control}",
        directories,
        "" if directories else f"no saved architecture directory under {control / SAVED_ARCHITECTURE_GLOB}",
    )


def attempts(check: Path, available: Supplies) -> list[list[str]] | str:
    """Build the argument lists to try for one check, from the options it declares.

    Returns:
        One argument list, or one per saved survey directory for a check that declares
        `--survey-dir`; or the reason a declared argument cannot be supplied.

    Raises:
        TypeError: check is not a Path or available is not a Supplies.

    """
    if not isinstance(check, Path) or not isinstance(available, Supplies):
        argument_error: str = "attempts requires a Path and a Supplies"
        raise TypeError(argument_error)
    declared: set[str] = set(DECLARED_OPTION.findall(check.read_text(encoding="utf-8")))
    fixed: list[str] = []
    if OPTION_CONTROL_REPO in declared:
        if available.control_repo is None:
            return available.control_repo_problem
        fixed.extend((OPTION_CONTROL_REPO, str(available.control_repo)))
    if OPTION_SURVEY_DIR not in declared:
        return [fixed]
    if not available.survey_dirs:
        return available.survey_dir_problem
    return [[*fixed, OPTION_SURVEY_DIR, str(directory)] for directory in available.survey_dirs]


def captured(output: object) -> str:
    """Read the output a timed-out child left, which the standard library types loosely.

    Returns:
        The text, decoded when it arrived as bytes, or an empty string when there is none.

    """
    if isinstance(output, str):
        return output
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return ""


def execute(check: Path, argv: list[str], timeout: int) -> tuple[bool, str]:
    """Run one check once with this interpreter.

    Returns:
        Whether it exited with status 0, and how it ended with everything it printed.

    Raises:
        TypeError: check is not a Path, argv is not a list of str or timeout is not an int.
        ValueError: timeout is not positive.

    """
    if (
        not isinstance(check, Path)
        or not isinstance(argv, list)
        or not all(isinstance(value, str) for value in argv)
        or not isinstance(timeout, int)
    ):
        argument_error: str = "execute requires a Path, a list of str and an int"
        raise TypeError(argument_error)
    if timeout <= 0:
        timeout_error: str = f"timeout must be positive: {timeout}"
        raise ValueError(timeout_error)
    shown: str = " ".join([check.name, *argv])
    try:
        finished: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv: this interpreter and a check script beside this file.
            [sys.executable, str(check), *argv],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        partial: str = captured(exc.stdout) + captured(exc.stderr)
        return False, f"{shown}: timed out after {timeout} seconds\n{partial}"
    return finished.returncode == 0, f"{shown}: exit status {finished.returncode}\n{finished.stdout}{finished.stderr}"


def run(check: Path, available: Supplies, timeout: int) -> Result:
    """Run one check and classify how it ended.

    Returns:
        Passed when an attempt exits with status 0; failed with the full output of every attempt
        otherwise; skipped when an argument the check declares cannot be supplied.

    Raises:
        TypeError: check is not a Path, available is not a Supplies or timeout is not an int.

    """
    if not isinstance(check, Path) or not isinstance(available, Supplies) or not isinstance(timeout, int):
        argument_error: str = "run requires a Path, a Supplies and an int"
        raise TypeError(argument_error)
    planned: list[list[str]] | str = attempts(check, available)
    if isinstance(planned, str):
        return Result(check.name, Outcome.SKIPPED, f"skipped: {planned}", "")
    outputs: list[str] = []
    for argv in planned:
        passed, output = execute(check, argv, timeout)
        if not passed:
            outputs.append(output)
            continue
        if OPTION_SURVEY_DIR not in argv:
            return Result(check.name, Outcome.PASSED, "", "")
        used: str = f"survey directory {argv[argv.index(OPTION_SURVEY_DIR) + 1]}"
        newer: str = f"; {len(outputs)} newer saved directories did not pass" if outputs else ""
        return Result(check.name, Outcome.PASSED, used + newer, "")
    return Result(check.name, Outcome.FAILED, "", "\n".join(outputs))


def line(result: Result) -> str:
    """Format the one line that reports a check.

    Returns:
        The outcome and the check name, followed by the note when there is one.

    Raises:
        TypeError: result is not a Result.

    """
    if not isinstance(result, Result):
        argument_error: str = "line requires a Result"
        raise TypeError(argument_error)
    match result.outcome:
        case Outcome.PASSED | Outcome.FAILED | Outcome.SKIPPED:
            note: str = f": {result.note}" if result.note else ""
            return f"{result.outcome.value:<8}{result.name}{note}"
        case _:
            assert_never(result.outcome)


def main() -> int:
    """Run every check and report each one.

    Returns:
        0 when every check passed; 1 when any check failed or was skipped.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--control-repo",
        type=Path,
        default=next((Path(os.environ[name]) for name in CONTROL_REPO_VARIABLES if os.environ.get(name)), None),
        help=f"control repository (defaults to the first set of {', '.join(CONTROL_REPO_VARIABLES)})",
    )
    parser.add_argument(
        "--survey-dir",
        type=Path,
        default=None,
        help="the one architecture directory to use (defaults to the saved ones, newest first)",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="seconds allowed per attempt")
    options: argparse.Namespace = parser.parse_args()
    control: Path | None = options.control_repo
    survey_dir: Path | None = options.survey_dir
    timeout: int = options.timeout
    if timeout <= 0:
        parser.error(f"--timeout must be positive: {timeout}")
    available: Supplies = supplies(control, survey_dir)
    results: list[Result] = []
    for check in discover(Path(__file__).resolve().parent):
        result: Result = run(check, available, timeout)
        results.append(result)
        sys.stdout.write(line(result) + "\n")
        sys.stdout.flush()
    for failed in (entry for entry in results if entry.outcome is Outcome.FAILED):
        sys.stdout.write(f"\n--- {failed.name}\n{failed.output.rstrip()}\n")
    passed: int = sum(entry.outcome is Outcome.PASSED for entry in results)
    not_run: int = sum(entry.outcome is Outcome.SKIPPED for entry in results)
    sys.stdout.write(
        f"\n{len(results)} checks: {passed} passed, {len(results) - passed - not_run} failed, {not_run} skipped\n",
    )
    return 0 if results and passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
