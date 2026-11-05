"""Declared suite commands executed directly, with their complete output retained as evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from driver_surface_types import SUITE_TIMEOUT_DEFAULT, SUITE_TIMEOUT_ENV

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import seconds
from orchestrator.core.tools import CommandResult, Tools

TASKFILES: Final = ("Taskfile.yml", "Taskfile.yaml")
TAIL_LINES: Final = 120
FAILURE_LINE: Final = re.compile(r"^(?:FAILED|ERROR)\s+(\S+?)(?:\s+-\s+.*)?$")


@dataclass(frozen=True, slots=True)
class SuiteResult:
    """A factual suite result; zero exit does not itself establish requirement coverage."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    evidence: Path

    def document(self) -> dict[str, JsonValue]:
        """Return the build journal's suite artifact, including unabridged evidence location.

        Returns:
            The command, exit, output tail and failures explicitly named by the runner.

        """
        lines: list[str] = (self.stdout + "\n" + self.stderr).splitlines()
        failures: list[JsonValue] = [_failure(match) for line in lines if (match := FAILURE_LINE.match(line))]
        return {
            "command": self.command,
            "exitCode": self.exit_code,
            "tail": "\n".join(lines[-TAIL_LINES:]),
            "failing": failures,
            "summary": next((line for line in reversed(lines) if line.strip()), ""),
            "evidence": str(self.evidence),
        }


def _failure(match: re.Match[str]) -> dict[str, JsonValue]:
    """Preserve a pytest failure identifier without diagnosing its cause.

    Returns:
        One failure in the suite artifact's existing shape.

    """
    identifier: str = match.group(1)
    filename, _, test = identifier.partition("::")
    return {"kind": "test" if test else "load", "file": filename, "test": test, "line": match.group(0)}


def declared_command(tree: Path, supplied: str = "") -> str | None:
    """Use a previously declared command, otherwise the repository's explicit test task.

    Args:
        tree: The repository worktree.
        supplied: Exact command already recorded by the repository's build contract.

    Returns:
        A declared command, or None when declaration needs a configuration judgment.

    Raises:
        TypeError: Arguments have invalid types.
        ValueError: The tree is not an absolute directory or a Taskfile is not a mapping.

    """
    if not isinstance(tree, Path) or not isinstance(supplied, str):
        message: str = "suite declaration requires a Path and a command string"
        raise TypeError(message)
    if not tree.is_absolute() or not tree.is_dir():
        message = f"suite worktree is not an absolute directory: {tree}"
        raise ValueError(message)
    if supplied.strip():
        return supplied.strip()
    return next((command for name in TASKFILES if (command := _task_command(tree / name))), None)


def _task_command(path: Path) -> str | None:
    """Read the presence of an explicitly declared Taskfile test task.

    Returns:
        The Task CLI command when the file declares test, otherwise None.

    Raises:
        StepError: The operation cannot proceed with the supplied evidence.

    """
    if not path.is_file():
        return None
    try:
        document: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        msg = "build:baseline"
        raise StepError(msg, OTHER_CAUSE, (f"Invalid suite Taskfile {path}: {error}",)) from None
    if not isinstance(document, dict):
        message: str = f"Taskfile is not a mapping: {path}"
        msg = "build:baseline"
        raise StepError(msg, OTHER_CAUSE, (message,))
    tasks: object = document.get("tasks")
    return "task test" if isinstance(tasks, dict) and "test" in tasks else None


def run_suite(tools: Tools, tree: Path, command: str, evidence: Path, stage: str) -> SuiteResult:
    """Execute the exact declared shell command with no model session or output relay.

    Args:
        tools: The dispatch's command and failure boundary.
        tree: Repository worktree.
        command: Repository-declared command, without adaptation or framework inference.
        evidence: Full result file.
        stage: Journal step key for attribution.

    Returns:
        The exact command result, including nonzero exits.

    Raises:
        TypeError: Arguments violate the suite execution contract.
        ValueError: The command is blank or paths are not absolute.

    """
    if not isinstance(tools, Tools) or not isinstance(tree, Path) or not isinstance(evidence, Path):
        message: str = "suite execution requires Tools and Path arguments"
        raise TypeError(message)
    if not isinstance(command, str) or not isinstance(stage, str):
        message = "suite command and stage must be strings"
        raise TypeError(message)
    if not command.strip() or not tree.is_absolute() or not evidence.is_absolute():
        message = "suite command must be declared and paths must be absolute"
        raise ValueError(message)
    result: CommandResult = tools.command(
        ["/bin/sh", "-c", command],
        stage=stage,
        cwd=tree,
        timeout=seconds(SUITE_TIMEOUT_ENV, float(SUITE_TIMEOUT_DEFAULT)),
        check=False,
    )
    write_json(evidence, json_object(result.to_json()))
    return SuiteResult(command, result.exit, result.stdout, result.stderr, evidence)
