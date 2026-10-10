"""Small isolated S03b checks: no tracker, agent session or pipeline is started."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Only fixture results and exception types, no launch.
import sys
import tempfile
import unittest
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from unittest.mock import patch

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/portfolio"))

import beadgraph as graph
import beads_contract as contract
from orchestrator.checks.check_support import expected_error, require
from orchestrator.core.events import EventWriter
from orchestrator.core.models import RetryExhaustedError, StepError
from orchestrator.core.tool_locks import bd_gate
from orchestrator.core.tools import Tools, retry_call

if TYPE_CHECKING:
    from contracts import JsonObject


@runtime_checkable
class CauseFailure(Protocol):
    """The factual failure cause exposed by the dynamically loaded graph module."""

    cause: str


def _raise_step(cause: str) -> None:
    stage = "x"
    raise StepError(stage, cause)


class ToolChecks(unittest.TestCase):
    """Existing isolated checks of tool and event boundaries."""

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def test_schedule_and_terminal_failure() -> None:
        """Check the existing tool boundary without an external invocation."""
        pauses: list[float] = []
        attempts = 0

        def action() -> str:
            nonlocal attempts
            attempts += 1
            limit = 3
            if attempts <= limit:
                stage = "write"
                raise StepError(stage, "bd-timeout")
            return "done"

        with expected_error(RetryExhaustedError):
            retry_call(action, sleep=pauses.append)
        require(pauses == [30, 60], "tool boundary check failed")
        for cause in ("api", "quota", "other"):
            with expected_error(StepError):
                retry_call(
                    partial(_raise_step, cause),
                    sleep=pauses.append,
                )
        require(len(pauses) == len([30, 60]), "tool boundary check failed")

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def test_bd_lock_timeout_exit_and_metadata_transport() -> None:
        """Check the existing tool boundary without an external invocation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            central = root / "central.lock"
            values = {
                "ATW_CONTROL_REPO": directory,
                "CENTRAL_BEADS_LOCK": str(central),
                "ATW_BD_TIMEOUT": "3",
                "ATW_BD_LOCK_WAIT": "0.01",
            }
            with (
                patch.dict(os.environ, values),
                patch.object(graph, "_target", return_value=root),
            ):

                def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                    require(kwargs["timeout"] == int(values["ATW_BD_TIMEOUT"]), "tool boundary check failed")
                    require(central.is_dir(), "tool boundary check failed")
                    return subprocess.CompletedProcess(
                        argv,
                        1,
                        "",
                        "database is locked",
                    )

                with patch.object(subprocess, "run", side_effect=run):
                    with expected_error(graph.GraphError) as caught:
                        graph.children(root, "example", "task")
                    require(
                        check_type(check_type(caught[0], CauseFailure).cause, str) == "other",
                        "tool boundary check failed",
                    )
                require(not (central.exists()), "tool boundary check failed")
                with patch.object(
                    subprocess,
                    "run",
                    side_effect=subprocess.TimeoutExpired("bd", 3),
                ):
                    with expected_error(graph.GraphError) as caught:
                        graph.children(root, "example", "task")
                    require(
                        check_type(check_type(caught[0], CauseFailure).cause, str) == "bd-timeout",
                        "tool boundary check failed",
                    )
                with bd_gate(write=False), patch.object(subprocess, "run") as run:
                    with expected_error(graph.GraphError) as caught:
                        graph.children(root, "example", "task")
                    require(
                        check_type(check_type(caught[0], CauseFailure).cause, str) == "contention",
                        "tool boundary check failed",
                    )
                    run.assert_not_called()
                with (
                    patch.object(contract.Reader, "route", return_value=directory),
                    patch.object(
                        graph,
                        "run_bd",
                        side_effect=[
                            "",
                            '[{"id":"example","metadata":{"state":"ready"}}]',
                        ],
                    ) as call,
                ):
                    graph.write_metadata("example", {"state": "ready"}, root)
                    require(call.call_count == len(["update", "read"]), "tool boundary check failed")
                    require(
                        call.call_args_list[0].args[0] == ["update", "example", "--set-metadata", "state=ready"],
                        "tool boundary check failed",
                    )
                record: JsonObject = {"id": "example", "title": "Example", "issue_type": "task"}
                require(
                    graph.fingerprints([record])["example"]
                    == contract.fingerprint_of("example", record)["fingerprint"],
                    "tool boundary check failed",
                )

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def test_tools_structured_results_and_keyed_retry() -> None:
        """Check the existing tool boundary without an external invocation."""
        with tempfile.TemporaryDirectory() as directory:
            tools = Tools(Path(directory))
            with patch(
                "orchestrator.core.tools.subprocess.run",
                return_value=subprocess.CompletedProcess(["git"], 1, "", "timeout"),
            ):
                with expected_error(StepError) as caught:
                    tools.command(["git"], stage="git")
                require(
                    check_type(check_type(caught[0], CauseFailure).cause, str) == "other",
                    "tool boundary check failed",
                )
                require(Path(check_type(caught[0], StepError).evidence[0]).is_file(), "tool boundary check failed")
            reads: list[dict[str, str]] = []
            stored: dict[str, str] = {}

            def write() -> str:
                reads.append(dict(stored))
                if not stored:
                    stored["elab_key"] = "created"
                    stage = "write"
                raise StepError(stage, "bd-timeout")
                return stored["elab_key"]

            with patch(
                "orchestrator.core.tools.retry_call",
                side_effect=lambda action: retry_call(action, sleep=lambda _: None),
            ):
                require(tools.operation("write", write) == "created", "tool boundary check failed")
            require(reads == [{}, {"elab_key": "created"}], "tool boundary check failed")

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def test_event_channel_survives_imported_stdout_redirection() -> None:
        """Check the existing tool boundary without an external invocation."""
        events, diagnostics = io.StringIO(), io.StringIO()
        writer = EventWriter(events)
        with contextlib.redirect_stdout(diagnostics):
            sys.stdout.write("library diagnostic\n")
            writer("phase", phase="architecture", step="survey")
        require(json.loads(events.getvalue())["step"] == "survey", "tool boundary check failed")
        require(diagnostics.getvalue() == "library diagnostic\n", "tool boundary check failed")


if __name__ == "__main__":
    unittest.main()
