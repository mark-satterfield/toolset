"""Fast local boundary probes; never start an agent, workflow, or pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/wsjf/scripts"))

import archcatalog
import archmatrix
import wsjf
from orchestrator.checks.check_support import expected_error, require
from orchestrator.core.agent_context import prepare
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.matrix import read_snapshot, row_for, satisfied, snapshot
from orchestrator.core.models import AgentStep, DeterministicStep, RunContext, StepError
from orchestrator.core.tools import CommandResult, DeploymentTarget, Tools
from orchestrator.flows.architecture_survey import survey_repositories

EXPECTED_FAILURE_EXIT: int = 2
DEFAULT_WRAPPER_TIMEOUT: int = 300
PRIVATE_DIRECTORY_MODE: int = 0o700
PRIVATE_FILE_MODE: int = 0o600


class RuntimeContracts(unittest.TestCase):
    """Exercise real preparation and producer boundaries using temporary fixtures."""

    @staticmethod
    def test_local_command_defaults_and_numeric_contract() -> None:
        """Execute harmless Python commands with default, integer, and float limits."""
        directory: str
        with tempfile.TemporaryDirectory() as directory:
            tools: Tools = Tools(Path(directory))
            argv: list[str] = [sys.executable, "-c", "print('local-boundary')"]
            require(tools.command(argv, stage="probe").stdout == "local-boundary\n", "runtime boundary probe failed")
            timeout: float
            for timeout in (1, 1.5):
                require(tools.command(argv, stage="probe", timeout=timeout).exit == 0, "runtime boundary probe failed")
            for timeout in (0, -1, float("inf"), float("nan")):
                with expected_error(ValueError):
                    tools.command(argv, stage="probe", timeout=timeout)
            with expected_error(TypeError):
                tools.command(argv, stage="probe", timeout=True)
            with expected_error(TypeError):
                tools.command(sys.executable, stage="probe")
            failure: list[str] = [sys.executable, "-c", "raise SystemExit(2)"]
            require(
                tools.command(failure, stage="probe", check=False).exit == EXPECTED_FAILURE_EXIT,
                "runtime boundary probe failed",
            )
            with expected_error(StepError):
                tools.command(failure, stage="probe")

    @staticmethod
    def test_command_wrappers_preserve_defaults() -> None:
        """Validate wrapper arguments while capturing the final command, without tools."""
        directory: str
        with tempfile.TemporaryDirectory() as directory:
            root: Path = Path(directory)
            tools: Tools = Tools(root)
            target: DeploymentTarget = DeploymentTarget(root, "local-fixture")
            result: CommandResult = CommandResult(("fixture",), 0, "", "")
            with patch.object(tools, "command", return_value=result) as command:
                require(tools.polyrepo(["inventory"], stage="probe") == result, "runtime boundary probe failed")
                require(command.call_args.kwargs["timeout"] == DEFAULT_WRAPPER_TIMEOUT, "runtime boundary probe failed")
                require(
                    tools.cdk("list", [], target=target, stage="probe", timeout=3) == result,
                    "runtime boundary probe failed",
                )
                require(
                    command.call_args.args[0] == ["cdk", "list", "--profile", "local-fixture"],
                    "runtime boundary probe failed",
                )
                require(tools.cdk("list", [], target=target, stage="probe") == result, "runtime boundary probe failed")
                require(tools.polyrepo([], stage="probe", timeout=3.5) == result, "runtime boundary probe failed")
                with expected_error(TypeError):
                    tools.polyrepo("inventory", stage="probe")
                with expected_error(TypeError):
                    tools.cdk("list", "bad", target=target, stage="probe")
                with expected_error(TypeError):
                    tools.polyrepo([], stage="probe", timeout=True)
                with expected_error(TypeError):
                    tools.cdk("list", [], target=target, stage="probe", timeout=True)

    @staticmethod
    def test_size_integer_float_and_invalid_values() -> None:
        """Keep Fibonacci rounding finite while accepting Python numeric inputs."""
        require(wsjf.snap_size(3) == int("3"), "runtime boundary probe failed")
        require(wsjf.snap_size(3.1) == int("5"), "runtime boundary probe failed")
        require(wsjf.snap_size(0) == 1, "runtime boundary probe failed")
        with expected_error(TypeError):
            wsjf.snap_size(True)
        value: float
        for value in (float("inf"), float("-inf"), float("nan")):
            with expected_error(ValueError):
                wsjf.snap_size(value)

    @staticmethod
    def test_session_preparation_only() -> None:
        """Write private agent configuration without constructing or starting a runner."""
        control: str = os.environ["ATW_CONTROL_REPO"]
        directory: str
        with tempfile.TemporaryDirectory() as directory:
            root: Path = Path(directory)
            plugin: Path = root / "plugin"
            agents: Path = plugin / "agents"
            agents.mkdir(parents=True)
            (agents / "fixture.md").write_text(
                "---\ndescription: local fixture\ntools: Read\nmcpServers: fixture-local-probe\n---\nFixture only.\n",
                encoding="utf-8",
            )
            step: AgentStep = AgentStep(
                "probe",
                "fixture",
                (),
                root / "output",
                "Prepare only.",
                root / "schema",
                None,
                "sonnet",
                "high",
            )
            config: Path = root / "config"
            config.mkdir()
            mcp: Path = config / ".claude.json"
            mcp.write_text('{"mcpServers":{"fixture-local-probe":{"command":"never-executed"}}}', encoding="utf-8")
            session: Path = root / "session"
            with patch.dict(os.environ, {"ATW_CONTROL_REPO": control, "CLAUDE_CONFIG_DIR": str(config)}):
                args: list[str] = prepare(plugin, config, session, step, "sonnet")
                mcp.unlink()
                with expected_error(ValueError):
                    prepare(plugin, config, root / "missing-mcp", step, "sonnet")
            require((session / "mcp.json").stat().st_mode & 0o777 == PRIVATE_FILE_MODE, "MCP file privacy drift")
            require("--strict-mcp-config" in args, "runtime boundary probe failed")
            require(session.stat().st_mode & 0o777 == PRIVATE_DIRECTORY_MODE, "runtime boundary probe failed")
            agent: dict[str, JsonValue] = json_object(json.loads((session / "agents.json").read_text(encoding="utf-8")))
            require(json_object(agent["atw-fixture"])["tools"] == ["Read"], "runtime boundary probe failed")
            require(bool((session / "settings.json").is_file()), "runtime boundary probe failed")
            (agents / "fixture.md").write_text(
                "---\ndescription: fixture\nmaxTurns: ten\n---\nBody.\n",
                encoding="utf-8",
            )
            with expected_error(TypeError):
                prepare(plugin, config, root / "invalid-metadata", step, "sonnet")

    @staticmethod
    def test_catalog_producer_to_consumer() -> None:
        """Feed authored catalog metadata through the reader and actual matrix consumer."""
        directory: str
        with tempfile.TemporaryDirectory() as directory:
            path: Path = Path(directory) / "view.md"
            path.write_text(
                "---\nview_type: component\nsubject: Search\nshows:\n  - Search\n  - Index\n---\n# Fixture\n",
                encoding="utf-8",
            )
            require(archcatalog.read_catalog(path)["shows"] == ["Search", "Index"], "runtime boundary probe failed")
            documents: list[dict[str, JsonValue]] = [{"path": str(path)}]
            require(
                archmatrix.catalog_elements(documents) == {"Search": [str(path)], "Index": [str(path)]},
                "runtime boundary probe failed",
            )

    @staticmethod
    def test_deterministic_result_preserves_type() -> None:
        """Pass a concrete result through real artifact execution and reuse."""
        directory: str
        with tempfile.TemporaryDirectory() as directory:
            root: Path = Path(directory)
            output: Path = root / "result.txt"
            producer: Path = Path(os.environ["ATW_CONTROL_REPO"]) / "ops/sdlc-automation/artifactio.py"
            store: ArtifactStore = ArtifactStore(load_artifactio(producer), root, root / "work", "fixture", "fixture")

            def action() -> list[str]:
                output.write_text("fixture", encoding="utf-8")
                return ["typed-result"]

            step: DeterministicStep[list[str]] = DeterministicStep("fixture", (), (output,), action)
            status: str
            result: list[str] | None
            status, result = store.execute(step)
            require(status == "ran" and result == ["typed-result"], "action return contract drift")
            require(store.execute(step) == ("reused", None), "reuse return contract drift")

    @staticmethod
    def test_inventory_exact_producer_shape() -> None:
        """Accept nullable producer fields and reject alternate or missing row shapes."""
        row: dict[str, JsonValue] = {"name": "fixture", "path": "/local/fixture", "role": None, "lifecycle": "active"}
        require(survey_repositories(json.dumps({"repos": [row]})) == [row], "inventory row drift")
        require(survey_repositories('{"repos":[]}') == [], "empty inventory drift")
        with expected_error(ValueError):
            survey_repositories('{"repositories":[]}')
        with expected_error(TypeError):
            survey_repositories('{"repos":[{"name":"incomplete"}]}')

    @staticmethod
    def test_matrix_snapshot_preparation() -> None:
        """Capture a fixture using the real lock, hash command, and snapshot writer."""
        directory: str
        with tempfile.TemporaryDirectory() as directory:
            root: Path = Path(directory)
            source: Path = root / "matrix.json"
            fixture: dict[str, JsonValue] = {
                "elements": {
                    "search": {"state": "built", "repository": "library"},
                    "repository:library": {"contains": []},
                    "api": {"state": "built", "repository": "service"},
                    "repository:service": {"contains": ["stack:service/main"]},
                },
            }
            source.write_text(json.dumps(fixture), encoding="utf-8")
            work: Path = root / "work"
            work.mkdir()
            context: RunContext = RunContext("fixture", "fixture", {}, work, "local-probe")
            with patch.dict(os.environ, {"ATW_CONTROL_REPO": str(root), "ATW_ELEMENT_MATRIX": str(source)}):
                output: Path = snapshot(context, Tools(work))
            result: dict[str, JsonValue] = read_snapshot(output)
            require(result["elements"] == fixture["elements"], "snapshot data drift")
            require(satisfied(result, row_for(result, " Search ")), "built library should satisfy")
            require(not satisfied(result, row_for(result, "API")), "stack needs deployment")
            content: bytes = source.read_bytes()
            blob: bytes = f"blob {len(content)}\0".encode() + content
            require(result["gitBlob"] == hashlib.sha1(blob, usedforsecurity=False).hexdigest(), "snapshot hash drift")


if __name__ == "__main__":
    unittest.main()
