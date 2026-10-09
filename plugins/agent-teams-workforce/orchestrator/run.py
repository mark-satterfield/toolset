"""Dispatch entry point: one flow, one atomic handback."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import signal
import sys
import traceback
from pathlib import Path
from uuid import uuid4

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.core.artifacts import load_artifactio
from orchestrator.core.io import write_json
from orchestrator.core.models import RunContext, StepError

FLOWS = {"prd-to-spec": "orchestrator.flows.prd_to_spec:run"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("flow", choices=FLOWS)
    result.add_argument("--bead", required=True)
    result.add_argument(
        "--args", required=True, type=Path, help="dispatch arguments JSON file"
    )
    result.add_argument("--handback", required=True, type=Path)
    return result


def _interrupted(number: int, _frame: object) -> None:
    raise InterruptedError(f"signal {number}")


def main(argv: list[str] | None = None) -> int:
    options = parser().parse_args(argv)
    context = None
    previous = {
        number: signal.signal(number, _interrupted)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with contextlib.redirect_stdout(sys.stderr):
            args = json.loads(options.args.read_text())
            if not isinstance(args, dict):
                raise TypeError("dispatch arguments must be a JSON object")
            artifacts = load_artifactio()
            control = Path(os.environ["ATW_CONTROL_REPO"])
            work = artifacts.working_dir(
                options.bead, control / ".claude/workflow-runs/artifacts"
            )
            context = RunContext(
                options.bead,
                options.flow,
                args,
                work,
                str(args.get("executionId") or uuid4()),
            )
            module, function = FLOWS[options.flow].split(":")
            flow = getattr(importlib.import_module(module), function)
        result = flow(context)
    except BaseException as exc:  # noqa: BLE001 - dispatch boundary must produce a handback
        stage = (
            exc.stage
            if isinstance(exc, StepError)
            else context.stage
            if context
            else "input"
        )
        cause = exc.cause if isinstance(exc, StepError) else "other"
        evidence = options.handback.with_suffix(".traceback.txt")
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(traceback.format_exc())
        if context:
            for cleanup in reversed(context.cleanup):
                try:
                    cleanup()
                except BaseException:  # noqa: BLE001 - complete remaining cleanup and handback
                    with evidence.open("a") as handle:
                        traceback.print_exc(file=handle)
        result = {
            "ok": False,
            "stage": stage,
            "beadId": options.bead,
            "headline": str(exc),
            "detailPath": str(evidence),
            "failure": {"stage": stage, "cause": cause, "repositories": []},
            "sessions": context.sessions if context else [],
        }
        if isinstance(exc, StepError) and exc.resume_at is not None:
            result["failure"]["resumeAt"] = exc.resume_at
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    write_json(options.handback, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
