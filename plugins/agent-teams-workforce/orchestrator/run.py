"""Dispatch entry point: one flow, one atomic handback."""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import signal
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import TextIO

from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# The composite and driver surface contracts are defined once, in the pipeline-contracts skill.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "pipeline-contracts" / "scripts"))

from composites_contract import ORCHESTRATED, PRD_TO_SPEC
from driver_surface_types import CONTROL_REPO_ENV

from orchestrator.core.agent_context import SessionCleanupError
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback import failure_for, stop_stage
from orchestrator.core.handback_contract import (
    SHUTDOWN_CAUSE,
    VERSION,
    Failure,
    HandbackDocument,
    HandbackValidationError,
    Session,
    StopStage,
    rejected,
    wire_result,
)
from orchestrator.core.io import JsonValue, json_object, work_directory, write_json
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tools import env_path
from orchestrator.flows.prd_to_spec import run as elaborate

type SignalHandler = Callable[[int, FrameType | None], None] | int | None

FLOWS: dict[str, Callable[[RunContext], dict[str, JsonValue]]] = {PRD_TO_SPEC: elaborate}
if frozenset(FLOWS) != ORCHESTRATED:
    _drift: str = f"run.py flows {sorted(FLOWS)} are not the orchestrated composites {sorted(ORCHESTRATED)}"
    raise ImportError(_drift)
_LOGGER: logging.Logger = logging.getLogger(__name__)


def _not_contract(contract: object) -> str:
    return f"expected the driver dispatch-arguments contract, got {type(contract).__name__}"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parser(contract: DispatchArguments) -> argparse.ArgumentParser:
    """Build the orchestrator command-line parser from the driver's dispatch-arguments contract.

    Args:
        contract: The control repository's dispatch-arguments contract, loaded once by the caller.

    Returns:
        Parser for the flow, bead, arguments file, and handback path.

    Raises:
        TypeError: ``contract`` is not the dispatch-arguments contract.

    """
    if not isinstance(contract, DispatchArguments):
        raise TypeError(_not_contract(contract))
    result: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    result.add_argument("flow", choices=FLOWS)
    result.add_argument(contract.OPT_BEAD, dest="bead", required=True)
    result.add_argument(contract.OPT_ARGS, dest="args", required=True, type=Path, help="dispatch arguments JSON file")
    result.add_argument(contract.OPT_HANDBACK, dest="handback", required=True, type=Path)
    return result


def _interrupted(number: int, _frame: FrameType | None) -> None:
    message: str = f"signal {number}"
    raise InterruptedError(message)


def _context(contract: DispatchArguments, bead: str, flow_name: str, path: Path) -> RunContext:
    if not isinstance(contract, DispatchArguments):
        raise TypeError(_not_contract(contract))
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    args: dict[str, JsonValue] = json_object(dict(contract.parse_arguments(raw)))
    work: Path = work_directory(env_path(CONTROL_REPO_ENV), bead)
    run_id: str = check_type(args[contract.KEY_EXECUTION_ID], str)
    return RunContext(bead, flow_name, args, work, run_id)


def _flow(flow_name: str) -> Callable[[RunContext], dict[str, JsonValue]]:
    return FLOWS[flow_name]


def _close_stopped_sessions(sessions: list[Session], since: float) -> None:
    """Close the session rows a stop cut short, keeping every row and its recorded facts.

    A row that started and has not ended, or that ended while the stop was being handled,
    is closed with the shutdown failure cause. The stop stage belongs to the failure, not the
    session. Its exit stays as recorded (``None`` when the process never reported one).
    """
    now: float = time.time()
    row: Session
    for row in sessions:
        if row.get("startedAt") is None:
            continue
        ended: float | None = row.get("endedAt")
        if ended is None or ended >= since:
            row["endedAt"] = ended if ended is not None else now
            row["exit"] = row.get("exit")
            row["cause"] = SHUTDOWN_CAUSE


def _failed(context: RunContext | None, exc: BaseException, bead: str, destination: Path) -> dict[str, JsonValue]:
    since: float = time.time()
    evidence: Path = destination.with_suffix(".traceback.txt")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
    if context:
        cleanup: Callable[[], None]
        handle: TextIO
        for cleanup in reversed(context.cleanup):
            try:
                cleanup()
            except BaseException as cleanup_error:
                _LOGGER.exception("Flow cleanup failed")
                failure: SessionCleanupError = SessionCleanupError(f"Flow cleanup failed: {cleanup_error}")
                failure.__cause__ = cleanup_error
                failure.add_note("Original flow failure:\n" + "".join(traceback.format_exception(exc)))
                exc = failure
                with evidence.open("a", encoding="utf-8") as handle:
                    traceback.print_exception(failure, file=handle)
    running: str = exc.stage if isinstance(exc, StepError) else context.stage if context else "input"
    stopped: StopStage | None = stop_stage(exc)
    headline: str = str(exc)
    if stopped is not None:
        headline = f"{stopped} during {running}: {exc}"
        if context:
            _close_stopped_sessions(context.sessions, since)
    outcome: Failure = failure_for(
        running,
        exc,
        agent_started=bool(context and any(row.get("startedAt") for row in context.sessions)),
        setup=context is None,
    )
    document: HandbackDocument = {
        "version": VERSION,
        "ok": False,
        "stage": outcome["stage"],
        "beadId": bead,
        "headline": headline,
        "detailPath": str(evidence),
        "failure": outcome,
        "sessions": context.sessions if context else [],
    }
    return json_object(document)


def _write_result(result: dict[str, JsonValue], destination: Path, bead: str) -> None:
    try:
        document: HandbackDocument = wire_result(result)
    except HandbackValidationError as exc:
        write_json(destination.with_suffix(".invalid.json"), result)
        document = rejected(result, exc, bead, str(destination))
    write_json(destination, document)


def _handback_options(contract: DispatchArguments, argv: list[str] | None) -> argparse.Namespace:
    """Read the handback path and the bead from the command line before the full parse.

    Returns:
        ``handback`` (a Path) and ``bead``; each None when the command line does not give it
        readably.

    """
    early: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    early.add_argument(contract.OPT_HANDBACK, dest="handback", type=Path)
    early.add_argument(contract.OPT_BEAD, dest="bead")
    try:
        return early.parse_known_args(argv)[0]
    except SystemExit:
        return argparse.Namespace(handback=None, bead=None)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main(argv: list[str] | None = None) -> int:
    """Run the selected flow and persist its validated handback.

    The dispatch-arguments contract is loaded once, before argument parsing, because it names
    the options that carry the handback path. A missing control repository or an unloadable
    contract therefore raises before any handback path is known: the process exits non-zero and
    writes no handback, and the driver reads the absent handback as a rejected document
    (classification ``pipeline-code-defect``), which stops new dispatch. Once the contract is
    loaded, a command line the full parse refuses writes a setup handback to the handback path
    the command line names, when it names one readably.

    Args:
        argv: Command-line arguments; ``None`` reads ``sys.argv``.

    Returns:
        Zero after the outcome has been written for the driver to classify.

    Raises:
        TypeError: ``argv`` is not a list of strings, or the control repository's
            dispatch-arguments contract is incomplete. Loading the contract also propagates
            ``KeyError`` when the control repository variable is unset and ``ImportError``
            when the control repository has no dispatch-arguments module.
        SystemExit: The full parse refused the command line, which names no handback path.
        TypeCheckError: A parsed option has the wrong type, and the command line names no
            handback path.

    """
    number: signal.Signals
    handler: SignalHandler
    if argv is not None and (not isinstance(argv, list) or any(not isinstance(arg, str) for arg in argv)):
        message: str = "Arguments must be a list of strings"
        raise TypeError(message)
    contract: DispatchArguments = dispatch_arguments()
    early: argparse.Namespace = _handback_options(contract, argv)
    bead: str
    flow_name: str
    path: Path
    destination: Path
    try:
        options: argparse.Namespace = parser(contract).parse_args(argv)
        bead, flow_name = check_type(options.bead, str), check_type(options.flow, str)
        path, destination = check_type(options.args, Path), check_type(options.handback, Path)
    except (SystemExit, TypeCheckError) as exc:
        if early.handback is None:
            raise
        named: str = early.bead or ""
        _write_result(_failed(None, exc, named, early.handback), early.handback, named)
        return 0
    context: RunContext | None = None
    previous: dict[signal.Signals, SignalHandler] = {
        number: signal.signal(number, _interrupted) for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with contextlib.redirect_stdout(sys.stderr):
            context = _context(contract, bead, flow_name, path)
            flow: Callable[[RunContext], dict[str, JsonValue]] = _flow(flow_name)
        result: dict[str, JsonValue] = dict(json_object(flow(context)))
    except BaseException as exc:
        _LOGGER.exception("Orchestrator flow failed")
        result = _failed(context, exc, bead, destination)
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    _write_result(result, destination, bead)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
