"""Small isolated S03b checks: no tracker, agent session or pipeline is started."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/portfolio"))

from orchestrator.core.events import EventWriter
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import bd_gate
from orchestrator.core.tools import Tools, retry_call


class ToolChecks(unittest.TestCase):
    def test_schedule_and_terminal_failure(self):
        pauses = []
        attempts = 0

        def action():
            nonlocal attempts
            attempts += 1
            if attempts <= 9:
                raise StepError("write", "bd-timeout")
            return "done"

        self.assertEqual(retry_call(action, sleep=pauses.append), "done")
        self.assertEqual(pauses, [30, 60, 120, 240, 480, 960, 1800, 1800, 1800])
        for cause in ("api", "quota", "other"):
            with self.assertRaises(StepError):
                retry_call(
                    lambda: (_ for _ in ()).throw(StepError("x", cause)),
                    sleep=pauses.append,
                )
        self.assertEqual(len(pauses), 9)

    def test_bd_lock_timeout_exit_and_metadata_transport(self):
        graph = importlib.import_module("beadgraph")
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

                def run(argv, **kwargs):
                    self.assertEqual(kwargs["timeout"], 3)
                    self.assertTrue(central.is_dir())
                    return subprocess.CompletedProcess(
                        argv, 1, "", "database is locked"
                    )

                with patch.object(graph.subprocess, "run", side_effect=run):
                    with self.assertRaises(graph.GraphError) as caught:
                        graph._bd(["update", "example"], root)
                    self.assertEqual(caught.exception.cause, "other")
                self.assertFalse(central.exists())
                with patch.object(
                    graph.subprocess,
                    "run",
                    side_effect=subprocess.TimeoutExpired("bd", 3),
                ):
                    with self.assertRaises(graph.GraphError) as caught:
                        graph._bd(["show", "example"], root)
                    self.assertEqual(caught.exception.cause, "bd-timeout")
                with bd_gate(write=False), patch.object(graph.subprocess, "run") as run:
                    with self.assertRaises(graph.GraphError) as caught:
                        graph._bd(["show", "example"], root)
                    self.assertEqual(caught.exception.cause, "contention")
                    run.assert_not_called()
                contract = graph._contract()
                with (
                    patch.object(contract.Reader, "route", return_value=directory),
                    patch.object(
                        graph,
                        "_bd",
                        side_effect=[
                            "",
                            '[{"id":"example","metadata":{"state":"ready"}}]',
                        ],
                    ) as call,
                ):
                    graph.write_metadata("example", {"state": "ready"}, root)
                    self.assertEqual(call.call_count, 2)
                    self.assertEqual(
                        call.call_args_list[0].args[0],
                        ["update", "example", "--set-metadata", "state=ready"],
                    )
                record = {"id": "example", "title": "Example", "issue_type": "task"}
                self.assertEqual(
                    graph.fingerprints([record])["example"],
                    contract.fingerprint_of("example", record)["fingerprint"],
                )

    def test_tools_structured_results_and_keyed_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = Tools(Path(directory))
            with patch(
                "orchestrator.core.tools.subprocess.run",
                return_value=subprocess.CompletedProcess(["git"], 1, "", "timeout"),
            ):
                with self.assertRaises(StepError) as caught:
                    tools.command(["git"], stage="git")
                self.assertEqual(caught.exception.cause, "other")
                self.assertTrue(Path(caught.exception.evidence[0]).is_file())
            reads = []
            stored = {}

            def write():
                reads.append(dict(stored))
                if not stored:
                    stored["elab_key"] = "created"
                    raise StepError("write", "bd-timeout")
                return stored["elab_key"]

            with patch(
                "orchestrator.core.tools.retry_call",
                side_effect=lambda action: retry_call(action, sleep=lambda _: None),
            ):
                self.assertEqual(tools.operation("write", write), "created")
            self.assertEqual(reads, [{}, {"elab_key": "created"}])

    def test_event_channel_survives_imported_stdout_redirection(self):
        events, diagnostics = io.StringIO(), io.StringIO()
        writer = EventWriter(events)
        with contextlib.redirect_stdout(diagnostics):
            print("library diagnostic")
            writer("phase", phase="architecture", step="survey")
        self.assertEqual(json.loads(events.getvalue())["step"], "survey")
        self.assertEqual(diagnostics.getvalue(), "library diagnostic\n")


if __name__ == "__main__":
    unittest.main()
