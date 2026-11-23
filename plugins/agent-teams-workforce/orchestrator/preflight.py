"""Preflight: check the saved run files under ``.claude/workflow-runs`` with the current plugin, before a run.

The command reads every file a run reads back and this plugin has a validator for: each step
journal (``step-journals/*.step-journal.json``) against the schema, the four rules a journal alone
states and the rules that need the current plugin's code (``step_journal.code_problems``); each
change log a workflow run saved beside the journals (``step-journals/changes/*.jsonl``), which must
belong to a journal that exists and hold JSON strings; and each Epic run record
(``artifacts/<bead>/run.json``) against ``RunManifest``. Files in an older format are read through
their migration tables, as a run reads them. The history records (``archive/`` and
``constitutional-precedents.jsonl``) are not read.

It writes nothing. It prints one JSON object on stdout, naming each file and its defects, and
exits 1 when any file has a defect. The keeper runs it before it launches a supervisor.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.core import pipeline_steps, step_journal
from orchestrator.core.journal_registry import REGISTRY, Registry
from orchestrator.core.manifest import RUN_MANIFEST_FILE, read_manifest
from orchestrator.flows import prd_to_spec  # ruff: ignore[unused-import] - Importing the elaboration flows fills REGISTRY.

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import (
    JOURNAL_SUFFIX,
    PIPELINE_BUILD,
    PIPELINE_DEPLOY,
    PIPELINE_ELABORATION,
    Journal,
    Pipeline,
    Step,
    StepJournalError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

PLUGIN_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
AGENTS_DIRECTORY: Final[Path] = PLUGIN_ROOT / "agents"
ARTIFACTS_DIRECTORY: Final = "artifacts"
JOURNAL_GLOB: Final = f"*{JOURNAL_SUFFIX}"
CHANGE_LOG_GLOB: Final = f"*{step_journal.CHANGES_SUFFIX}"
EXIT_OK: Final = 0
EXIT_DEFECTS: Final = 1


class Defect(TypedDict):
    """One defect of one file."""

    file: str
    defect: str


class Checked(TypedDict):
    """How many files of each kind were read."""

    stepJournals: int
    changeLogs: int
    runRecords: int


class PreflightReport(TypedDict):
    """What the command prints."""

    ok: bool
    runs: str
    checked: Checked
    defects: list[Defect]


@dataclass(frozen=True, slots=True)
class ElaborationCode:
    """What the plugin knows of the elaboration steps: the registry its flows fill."""

    registry: Registry

    def known(self, step: Step) -> bool:
        """Tell whether a flow runs the step's key or agent, or drops it as removed.

        Returns:
            True when the registry holds its code or registers it as removed.

        """
        return self.registry.handles(step) or self.registry.is_removed(step)

    def required_params(self, step: Step) -> tuple[str, ...] | None:
        """Name the parameters the step's code needs.

        Returns:
            Empty when its script key needs its planner's parameters record; otherwise None.

        """
        return () if self.registry.requires_params(step) else None

    def plans_child_containers(self, container: str) -> bool:
        """Tell whether the container's child containers are each planned by a step's result.

        Returns:
            True for a container whose child containers run together (one per repository).

        """
        return self.registry.runs_children_together(container)


@dataclass(frozen=True, slots=True)
class LaneCode:
    """What the plugin knows of the build or the deploy steps: their kinds and the plugin's agents."""

    definition: pipeline_steps.PipelineDefinition
    agents: frozenset[str]

    def known(self, step: Step) -> bool:
        """Tell whether the step's script key is a kind of the pipeline, or its agent one of the plugin's.

        Returns:
            True when it is.

        """
        script: str | None = step.get("script")
        if script is not None:
            return script in self.definition.kinds
        agent: str | None = step.get("agent")
        return agent is not None and agent in self.agents

    def required_params(self, step: Step) -> tuple[str, ...] | None:
        """Name the parameters the kind of the step is handed by the step that adds it.

        A kind the pipeline also plans up front, or under a step when it first runs, is planned
        there without parameters, so its code does without them.

        Returns:
            The kind's parameters; None for a kind that is handed none or is also planned up front.

        """
        script: str | None = step.get("script")
        kind: pipeline_steps.StepKind | None = None if script is None else self.definition.kinds.get(script)
        upfront: set[str] = {*self.definition.plan, *(key for keys in self.definition.inner.values() for key in keys)}
        if kind is None or not kind.params or kind.key in upfront:
            return None
        return kind.params

    def plans_child_containers(self, container: str) -> bool:  # ruff: ignore[no-self-use, unused-method-argument] - StepCode method.
        """Tell whether a container's child containers are each planned by a step's result.

        Returns:
            False: the build and deploy pipelines plan no such containers.

        """
        return False


def _codes() -> dict[Pipeline, step_journal.StepCode]:
    """Name what the current plugin knows of the steps of each pipeline.

    Returns:
        The code of each pipeline's steps.

    """
    agents: frozenset[str] = frozenset(path.stem for path in AGENTS_DIRECTORY.glob("*.md"))
    return {
        PIPELINE_ELABORATION: ElaborationCode(REGISTRY),
        PIPELINE_BUILD: LaneCode(pipeline_steps.definition(PIPELINE_BUILD), agents),
        PIPELINE_DEPLOY: LaneCode(pipeline_steps.definition(PIPELINE_DEPLOY), agents),
    }


def _journal_defects(path: Path, codes: Mapping[Pipeline, step_journal.StepCode]) -> list[str]:
    """Check one step journal file with the current plugin.

    Returns:
        Each defect: the format, schema and journal rules first; when those pass, the rules that
        need the plugin's code.

    """
    try:
        problems: list[str] = step_journal.file_problems(path)
        if problems:
            return problems
        journal: Journal = step_journal.read_journal(path)
    except StepJournalError as error:
        return [str(error)]
    return step_journal.code_problems(journal, codes[journal["pipeline"]])


def _change_log_defects(path: Path, journals: Path) -> list[str]:
    """Check one change log a workflow run saved: its journal exists and its lines are JSON strings.

    Returns:
        Each defect.

    """
    journal_name: str = path.name.split(JOURNAL_SUFFIX, 1)[0] + JOURNAL_SUFFIX
    run: str = path.name.removeprefix(journal_name + ".").removesuffix(step_journal.CHANGES_SUFFIX)
    journal: Path = journals / journal_name
    if not journal.is_file():
        return [f"the change log belongs to {journal.name}, which does not exist"]
    try:
        step_journal.recorded_changes(journal, run)
    except StepJournalError as error:
        return [str(error)]
    return []


def _run_record_defects(path: Path) -> list[str]:
    """Check one Epic run record against ``RunManifest``, read through its migration table.

    Returns:
        Each defect.

    """
    try:
        read_manifest(path)
    except (OSError, ValueError) as error:
        return [str(error)]
    return []


def _defects_of(paths: list[Path], check: Callable[[Path], list[str]]) -> Iterator[Defect]:
    """Check each file of one kind.

    Yields:
        Each defect of each file, in file order.

    """
    path: Path
    for path in paths:
        yield from (Defect(file=str(path), defect=found) for found in check(path))


def preflight(runs: Path) -> PreflightReport:
    """Check every saved run file under a workflow runs directory that this plugin has a validator for.

    Args:
        runs: The control repository's ``.claude/workflow-runs`` directory.

    Returns:
        The files checked and every defect found.

    Raises:
        ValueError: ``runs`` is not a directory.

    """
    if not runs.is_dir():
        message: str = f"{runs} is not a directory, so it holds no saved run files"
        raise ValueError(message)
    journals_directory: Path = step_journal.journals_directory(runs)
    codes: dict[Pipeline, step_journal.StepCode] = _codes()
    journals: list[Path] = sorted(journals_directory.glob(JOURNAL_GLOB))
    change_logs: list[Path] = sorted((journals_directory / step_journal.CHANGES_DIRECTORY).glob(CHANGE_LOG_GLOB))
    records: list[Path] = sorted((runs / ARTIFACTS_DIRECTORY).glob(f"*/{RUN_MANIFEST_FILE}"))
    defects: list[Defect] = [
        *_defects_of(journals, lambda path: _journal_defects(path, codes)),
        *_defects_of(change_logs, lambda path: _change_log_defects(path, journals_directory)),
        *_defects_of(records, _run_record_defects),
    ]
    return {
        "ok": not defects,
        "runs": str(runs),
        "checked": {"stepJournals": len(journals), "changeLogs": len(change_logs), "runRecords": len(records)},
        "defects": defects,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the preflight over one workflow runs directory.

    Args:
        argv: The arguments after the program name; None reads the process's own.

    Returns:
        0 when no file has a defect; 1 when one has, after printing the report on stdout; 1
        after printing why on stderr when the directory cannot be checked.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="atw-preflight",
        description="Check the saved run files under .claude/workflow-runs with the current plugin. Writes nothing.",
    )
    parser.add_argument("--runs", required=True, help="the control repository's .claude/workflow-runs directory")
    runs: Path = Path(str(parser.parse_args(argv).runs))
    try:
        report: PreflightReport = preflight(runs)
    except ValueError as error:
        sys.stderr.write(f"atw-preflight: {error}\n")
        return EXIT_DEFECTS
    sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
    return EXIT_OK if report["ok"] else EXIT_DEFECTS


if __name__ == "__main__":
    sys.exit(main())
