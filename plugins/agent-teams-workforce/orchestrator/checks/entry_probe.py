"""Run one real elaboration dispatch up to its first agent session, with stand-ins; not a check itself.

The control repository's ``check_entry.py`` starts this in a child process with the interpreter, the
environment and the arguments the driver prepared for a dispatch. It takes the stages
``orchestrator/run.py`` takes before a flow runs (the dispatch-arguments contract, the argument
parser, the context, the flow lookup), moves the context's work directory into a temporary
control repository, and runs the flow's own entry function. The flow validates its input, plans
the Epic's journal when the file does not exist, and runs the journal's steps until the first
agent session is about to start; the stand-in for that session records the brief and stops the run.

Stood in: the Epic's claim and its release, the matrix sync, the ``bd`` process, every other
command and ``git``, the ``claude --version`` probe, the section 2 guard around a session, and
the session process. Everything else is the code a dispatch runs.
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
from contextlib import AbstractContextManager, ExitStack, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn, TypedDict
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))

import beadgraph
from driver_surface_types import HEADLESSENV_MODULE
from orchestrator import run as entry
from orchestrator.checks.check_support import require
from orchestrator.checks.journal_bench import Call, StandIns
from orchestrator.core import agents as session_runner
from orchestrator.core import step_journal as sj
from orchestrator.core.agent_process import SessionProcesses, SessionRequest
from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments, driver_module
from orchestrator.core.models import RunContext, SessionFacts
from orchestrator.core.tools import Tools
from orchestrator.flows import prd_to_spec
from orchestrator.flows.architecture import ARCHITECT_DESCRIPTION
from orchestrator.flows.architecture_files import (
    EARLIER_PREFIX,
    LABEL_STATE,
    OPEN_RUN,
    PLUGIN,
    ROLE_ARCHITECT,
    agents_with_role,
)
from step_journal_contract import STATUS_DONE, BeadId
from typeguard import CollectionCheckStrategy, check_type

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

    from orchestrator.core.io import JsonValue
    from step_journal_contract import Journal, Step

PLUGIN_VERSION_MODULE: Final = "pluginversion"
"""The driver module that says which plugin directory the driver's own code reads."""
STOOD_IN: Final[tuple[str, ...]] = (
    "the Epic's claim and its release (prd_to_spec.lifecycle)",
    "the matrix sync of the open-run step (prd_to_spec._sync_matrix)",
    "the bd process (beadgraph.run_bd), answered with the bd show output the check read",
    "git and every other command (Tools.git, Tools.command): none is expected, and one would fail the check",
    "the claude --version probe (AgentRunner._version)",
    (
        "the section 2 guard around a session (constraints.Section2Guard), which snapshots the owner's constraints "
        "under the driver's state directory and reads the vault with git"
    ),
    "the session process (SessionProcesses.run): the brief is recorded and the run stops",
)
REAL: Final[tuple[str, ...]] = (
    "the dispatch-arguments contract loaded from the control repository (driver_contracts.dispatch_arguments)",
    "the orchestrator's argument parser on the driver's command line (run.parser)",
    "the context from the driver's arguments file, validated by the driver's parse_arguments (run._context)",
    "the flow lookup (run._flow)",
    "the flow's entry and its input validation (prd_to_spec.run)",
    "journal planning (journal_run.open_journal with prd_to_spec.outermost_steps)",
    "the journal loop for the open-run step (JournalRunner.run, prd_to_spec.open_run)",
    "the architect's launch builder, the launcher and the brief (architecture.architect, AgentRunner.run_session)",
    "the handback writer and its contract validation (run._write_result)",
)


class Config(TypedDict):
    """What the check hands the probe."""

    workRoot: str
    bdShow: str
    journal: str | None
    report: str


class BriefInput(TypedDict):
    """One input of the architect's brief."""

    label: str
    path: str
    exists: bool


class Report(TypedDict):
    """What the probe found, for the check to assert and print."""

    real: list[str]
    stoodIn: list[str]
    realWork: str
    realJournal: str
    journal: str
    createdJournal: bool
    outermost: list[str]
    done: list[str]
    next: str
    nextAgent: str
    nextInputs: int
    agent: str
    request: str
    output: str
    inputs: list[BriefInput]
    sessions: int
    resultStage: str
    handback: str


class ProbeStopError(Exception):
    """The first agent session was reached; the probe starts none."""


def _refuse(*_arguments: object, **_named: object) -> NoReturn:
    """Fail the probe when a step runs a command the probe did not expect.

    Raises:
        AssertionError: Always.

    """
    message: str = "a step before the first agent session ran git or another command"
    raise AssertionError(message)


class _NoGuard:
    """Stands in for the section 2 guard: nothing is snapshotted and no git command runs."""

    def __init__(self, _arch: Path, _tools: Tools, _stop: Callable[[], None]) -> None:
        """Take what the guard takes and keep none of it."""

    @staticmethod
    def session(_session_id: str) -> AbstractContextManager[None]:
        """Guard nothing.

        Returns:
            A context that does nothing on entry or exit.

        """
        return nullcontext()


def _lifecycle(_context: RunContext, _tools: Tools, _stage: str, operation: object, /, **facts: object) -> object:
    """Stand in for the Epic's claim and its release: no bead is read or written.

    Returns:
        A granted claim for the start; an empty record for the release.

    """
    if getattr(operation, "__name__", "") == "start":
        return {"ok": True, "owner": facts.get("owner", "entry-probe")}
    return {"ok": True}


def _sync_matrix(*_arguments: object) -> str:
    """Stand in for the matrix sync: the matrix is neither read nor written.

    Returns:
        A vault commit that names no commit.

    """
    return "0" * 40


def _moved(context: RunContext, root: Path) -> RunContext:
    """Move a dispatch's work directory into a temporary control repository.

    Returns:
        The same context with its work directory under ``root``.

    """
    work: Path = root / ".claude" / sj.WORKFLOW_RUNS_DIRECTORY / "artifacts" / context.bead
    return RunContext(context.bead, context.flow, context.args, work, context.run_id)


def _stand_ins(config: Config, sessions: StandIns) -> ExitStack:
    """Put every stand-in of the probe in place.

    Returns:
        The stack of stand-ins, entered; closing it removes them.

    """

    def answer(args: list[str], _control: Path, _stdin: str | None = None) -> str:
        require(args[:1] == ["show"], f"a step before the first agent session ran bd {args}")
        return config["bdShow"]

    def launch(_processes: SessionProcesses, request: SessionRequest) -> SessionFacts:
        return sessions.run(request)

    driver_module(HEADLESSENV_MODULE)
    versions: object = importlib.import_module(PLUGIN_VERSION_MODULE)
    stack: ExitStack = ExitStack()
    stack.enter_context(patch.object(prd_to_spec, "lifecycle", _lifecycle))
    stack.enter_context(patch.object(prd_to_spec, "_sync_matrix", _sync_matrix))
    stack.enter_context(patch.object(beadgraph, "run_bd", answer))
    stack.enter_context(patch.object(Tools, "git", _refuse))
    stack.enter_context(patch.object(Tools, "command", _refuse))
    stack.enter_context(patch.object(AgentRunner, "_version", lambda _runner: None))
    stack.enter_context(patch.object(session_runner, "Section2Guard", _NoGuard))
    stack.enter_context(patch.object(SessionProcesses, "run", launch))
    stack.enter_context(patch.object(versions, "running_dir", return_value=(PLUGIN, "")))
    return stack


def _report(config: Config, context: RunContext, moved: RunContext, sessions: StandIns, stage: str) -> Report:
    """Read what the run left in the temporary journal and what the stand-in session was sent.

    Returns:
        The report the check asserts on.

    """
    path: Path = sj.journal_path(sj.journals_directory(moved.work), BeadId(moved.bead))
    journal: Journal = sj.read_journal(path)
    following: Step | None = sj.next_step(journal)
    require(following is not None, "the journal has no step left after the open-run step")
    require(len(sessions.calls) == 1, f"{len(sessions.calls)} sessions were started before the run stopped")
    call: Call = sessions.calls[0]
    return {
        "real": list(REAL),
        "stoodIn": list(STOOD_IN),
        "realWork": str(context.work),
        "realJournal": str(sj.journal_path(sj.journals_directory(context.work), BeadId(context.bead))),
        "journal": str(path),
        "createdJournal": config["journal"] is None,
        "outermost": [step["description"] for step in journal["steps"]],
        "done": [
            step["description"]
            for step in sj.steps_in_order(journal)
            if not step["steps"] and step["status"] == STATUS_DONE
        ],
        "next": following["description"] if following is not None else "",
        "nextAgent": following.get("agent", "") if following is not None else "",
        "nextInputs": len(following.get("inputs", [])) if following is not None else 0,
        "agent": call.agent,
        "request": call.request,
        "output": str(call.output),
        "inputs": [{"label": label, "path": str(held), "exists": held.exists()} for label, held in call.inputs.items()],
        "sessions": len(sessions.calls),
        "resultStage": stage,
        "handback": "",
    }


def _require_brief(report: Report, architect: str, carried: bool) -> None:
    """Require the architect's step to be next, with a brief that names files that exist."""
    require(
        (report["next"], report["nextAgent"], report["agent"]) == (ARCHITECT_DESCRIPTION, architect, architect),
        f"the step after the open-run step is not the architect's: {report['next']!r} by {report['nextAgent']!r}",
    )
    missing: list[str] = [
        f"{held['label']} = {held['path']}"
        for held in report["inputs"]
        if not held["exists"] and held["label"] != LABEL_STATE
    ]
    require(not missing, f"the architect's brief names files that do not exist: {missing}")
    earlier: list[str] = [held["label"] for held in report["inputs"] if held["label"].startswith(EARLIER_PREFIX)]
    require(bool(earlier) == carried, f"earlier work in the architect's brief: {earlier}")


def main(config_path: str, argv: list[str]) -> int:
    """Take one dispatch from the driver's command line to the architect's brief.

    Args:
        config_path: The JSON file the check wrote: the temporary control repository, the
            ``bd show`` output, a journal to start from or null, and where to write the report.
        argv: The arguments the driver prepared for ``orchestrator/run.py``.

    Returns:
        Zero after the report is written. A stage that refuses raises what it raises.

    """
    config: Config = check_type(
        json.loads(Path(config_path).read_text(encoding="utf-8")),
        Config,
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    require(Path(str(entry.__file__)).resolve() == PLUGIN / "orchestrator" / "run.py", "run.py of another plugin")
    contract: DispatchArguments = dispatch_arguments()
    options: argparse.Namespace = entry.parser(contract).parse_args(argv)
    bead: str = check_type(options.bead, str)
    flow_name: str = check_type(options.flow, str)
    context: RunContext = entry._context(contract, bead, flow_name, check_type(options.args, Path))  # ruff: ignore[private-member-access] - The probe takes the stages run.py takes before a flow runs.
    flow: Callable[[RunContext], dict[str, JsonValue]] = entry._flow(flow_name)  # ruff: ignore[private-member-access] - The probe takes the stages run.py takes before a flow runs.
    require(flow is prd_to_spec.run, "the flow looked up is not the elaboration flow")
    moved: RunContext = _moved(context, Path(config["workRoot"]))
    if config["journal"] is not None:
        copied: Path = sj.journal_path(sj.journals_directory(moved.work), BeadId(bead))
        copied.parent.mkdir(parents=True)
        shutil.copyfile(config["journal"], copied)
    architect: str = agents_with_role(PLUGIN, ROLE_ARCHITECT)[0]
    sessions: StandIns = StandIns()

    def stop(_call: Call) -> None:
        raise ProbeStopError(OPEN_RUN)

    sessions.behaviours[architect] = stop
    with _stand_ins(config, sessions):
        result: dict[str, JsonValue] = flow(moved)
    report: Report = _report(config, context, moved, sessions, str(result.get("stage")))
    _require_brief(report, architect, carried=config["journal"] is not None)
    handback: Path = check_type(options.handback, Path)
    entry._write_result(result, handback, bead)  # ruff: ignore[private-member-access] - The probe writes the handback as run.py does.
    report["handback"] = str(handback)
    Path(config["report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0
