"""Dispatch entry point: one flow, one atomic handback."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import logging
import os
import signal
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from typeguard import CollectionCheckStrategy, check_type, typechecked

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.core.agent_context import SessionCleanupError
from orchestrator.core.artifacts import load_artifactio
from orchestrator.core.handback import HandbackValidationError, failure_for, rejected, validate, wire_result
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import RunContext, StepError

FLOWS = {"prd-to-spec": "orchestrator.flows.prd_to_spec:run"}
_LOGGER = logging.getLogger(__name__)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parser() -> argparse.ArgumentParser:
    """Build the orchestrator command-line parser.

    Returns:
        Parser for the flow, bead, arguments file, and handback path.

    """
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("flow", choices=FLOWS)
    result.add_argument("--bead", required=True)
    result.add_argument("--args", required=True, type=Path, help="dispatch arguments JSON file")
    result.add_argument("--handback", required=True, type=Path)
    return result


def _interrupted(number: int, _frame: object) -> None:
    message = f"signal {number}"
    raise InterruptedError(message)


def _context(bead: str, flow_name: str, path: Path) -> RunContext:
    args = json_object(json.loads(path.read_text(encoding="utf-8")))
    artifacts = load_artifactio()
    control = Path(os.environ["ATW_CONTROL_REPO"])
    work = check_type(artifacts.working_dir(bead, control / ".claude/workflow-runs/artifacts"), Path)
    return RunContext(bead, flow_name, args, work, str(args.get("executionId") or uuid4()))


def _flow(flow_name: str) -> Callable[[RunContext], dict[str, JsonValue]]:
    module, function = FLOWS[flow_name].split(":")
    loaded: Callable[[RunContext], dict[str, JsonValue]] = check_type(
        getattr(importlib.import_module(module), function),
        Callable[[RunContext], dict[str, JsonValue]],
    )
    return loaded


def _failed(context: RunContext | None, exc: BaseException, bead: str, destination: Path) -> dict[str, object]:
    stage = exc.stage if isinstance(exc, StepError) else context.stage if context else "input"
    evidence = destination.with_suffix(".traceback.txt")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("".join(traceback.format_exception(exc)))
    if context:
        for cleanup in reversed(context.cleanup):
            try:
                cleanup()
            except BaseException as cleanup_error:
                _LOGGER.exception("Flow cleanup failed")
                failure = SessionCleanupError(f"Flow cleanup failed: {cleanup_error}")
                failure.__cause__ = cleanup_error
                failure.add_note("Original flow failure:\n" + "".join(traceback.format_exception(exc)))
                exc = failure
                with evidence.open("a") as handle:
                    traceback.print_exception(failure, file=handle)
    return {
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
    }


def _write_result(result: dict[str, object], destination: Path, bead: str) -> None:
    try:
        document = wire_result(result)
    except HandbackValidationError as exc:
        write_json(destination.with_suffix(".invalid.json"), result)
        document = validate(rejected(result, exc, bead, str(destination)))
    write_json(destination, document)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main(argv: list[str] | None = None) -> int:
    """Run the selected flow and persist its validated handback.

    Returns:
        Zero after the outcome has been written for the driver to classify.

    """
    options = parser().parse_args(argv)
    bead, flow_name = check_type(options.bead, str), check_type(options.flow, str)
    path, destination = check_type(options.args, Path), check_type(options.handback, Path)
    context = None
    previous = {number: signal.signal(number, _interrupted) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        with contextlib.redirect_stdout(sys.stderr):
            context = _context(bead, flow_name, path)
            flow = _flow(flow_name)
        result: dict[str, object] = dict(json_object(flow(context)))
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
