"""Dispatch entry point: one flow, one atomic handback."""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import signal
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, TextIO
from uuid import uuid4

from typeguard import CollectionCheckStrategy, check_type, typechecked

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.core.agent_context import SessionCleanupError
from orchestrator.core.artifacts import load_artifactio
from orchestrator.core.handback import (
    HandbackDocument,
    HandbackValidationError,
    failure_for,
    rejected,
    validate,
    wire_result,
)
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import RunContext, StepError
from orchestrator.flows.prd_to_spec import run as elaborate

if TYPE_CHECKING:
    from orchestrator.core.artifact_contract import ArtifactProducer

type SignalHandler = Callable[[int, FrameType | None], None] | int | None

FLOWS: dict[str, Callable[[RunContext], dict[str, JsonValue]]] = {"prd-to-spec": elaborate}
_LOGGER: logging.Logger = logging.getLogger(__name__)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parser() -> argparse.ArgumentParser:
    """Build the orchestrator command-line parser.

    Returns:
        Parser for the flow, bead, arguments file, and handback path.

    """
    result: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    result.add_argument("flow", choices=FLOWS)
    result.add_argument("--bead", required=True)
    result.add_argument("--args", required=True, type=Path, help="dispatch arguments JSON file")
    result.add_argument("--handback", required=True, type=Path)
    return result


def _interrupted(number: int, _frame: FrameType | None) -> None:
    message: str = f"signal {number}"
    raise InterruptedError(message)


def _context(bead: str, flow_name: str, path: Path) -> RunContext:
    args: dict[str, JsonValue] = json_object(json.loads(path.read_text(encoding="utf-8")))
    artifacts: ArtifactProducer = load_artifactio()
    control: Path = Path(os.environ["ATW_CONTROL_REPO"])
    work: Path = check_type(artifacts.working_dir(bead, control / ".claude/workflow-runs/artifacts"), Path)
    return RunContext(bead, flow_name, args, work, str(args.get("executionId") or uuid4()))


def _flow(flow_name: str) -> Callable[[RunContext], dict[str, JsonValue]]:
    return FLOWS[flow_name]


def _failed(context: RunContext | None, exc: BaseException, bead: str, destination: Path) -> dict[str, JsonValue]:
    stage: str = exc.stage if isinstance(exc, StepError) else context.stage if context else "input"
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
    return json_object({
        "ok": False,
        "stage": stage,
        "beadId": bead,
        "headline": str(exc),
        "detailPath": str(evidence),
        "failure": failure_for(
            stage,
            exc,
            agent_started=bool(context and any(row.get("startedAt") for row in context.sessions)),
            setup=context is None,
        ),
        "sessions": context.sessions if context else [],
    })


def _write_result(result: dict[str, JsonValue], destination: Path, bead: str) -> None:
    try:
        document: HandbackDocument = wire_result(result)
    except HandbackValidationError as exc:
        write_json(destination.with_suffix(".invalid.json"), result)
        document = validate(rejected(result, exc, bead, str(destination)))
    write_json(destination, document)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main(argv: list[str] | None = None) -> int:
    """Run the selected flow and persist its validated handback.

    Returns:
        Zero after the outcome has been written for the driver to classify.

    Raises:
        TypeError: CLI arguments violate the declared input contract.

    """
    number: signal.Signals
    handler: SignalHandler
    if argv is not None and (not isinstance(argv, list) or any(not isinstance(arg, str) for arg in argv)):
        message: str = "Arguments must be a list of strings"
        raise TypeError(message)
    options: argparse.Namespace = parser().parse_args(argv)
    bead: str
    flow_name: str
    path: Path
    destination: Path
    bead, flow_name = check_type(options.bead, str), check_type(options.flow, str)
    path, destination = check_type(options.args, Path), check_type(options.handback, Path)
    context: RunContext | None = None
    previous: dict[signal.Signals, SignalHandler] = {
        number: signal.signal(number, _interrupted) for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with contextlib.redirect_stdout(sys.stderr):
            context = _context(bead, flow_name, path)
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
