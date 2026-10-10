"""Prove saved survey adoption on copies; never launch a pipeline or an agent."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import override

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.checks.check_support import report, require
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.io import write_json
from orchestrator.core.models import AgentStep, RunContext
from orchestrator.core.tools import Tools
from orchestrator.flows.architecture_support import Architecture
from orchestrator.flows.architecture_survey import SURVEY_FILES, current_survey


class NoAgentRunner(AgentRunner):
    """Ensure the saved-survey check never starts an agent."""

    @override
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self, step: AgentStep) -> Path:
        """Reject any attempt to produce a fresh survey.

        Raises:
            AssertionError: The saved survey attempted an agent session.

        """
        message = "survey reuse started an agent session"
        raise AssertionError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.survey_dir.resolve()
    originals = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in SURVEY_FILES
        if (source / name).exists()
    }
    with tempfile.TemporaryDirectory(prefix="atw-survey-adoption-") as temp:
        root = Path(temp)
        work = root / "architecture"
        work.mkdir()
        for name in originals:
            shutil.copy2(source / name, work / name)
        tools = Tools(work / "evidence")
        notes: list[dict[str, object]] = []

        def emit(_event: str, **fields: object) -> None:
            notes.append(fields)

        context = RunContext(
            "epic",
            "architecture",
            {"archPath": str(root / "vault"), "prd": {"path": str(root / "prd.md")}},
            root,
            "survey-check",
        )
        store = ArtifactStore(ModuleType("unused"), root, work, "epic", "survey-check")
        runner = NoAgentRunner(context, store, emit=emit)
        matrix = root / "matrix.json"
        write_json(matrix, {"elements": {}})
        flow = Architecture(context, store, runner, tools, matrix)
        require(current_survey(flow), "saved survey binding is no longer current")
        require(flow.adopted, "legacy survey was not adopted")
        require(current_survey(flow), "adopted seal cannot be reused")
        require(
            hashlib.sha256((work / "survey.json").read_bytes()).hexdigest() == originals["survey.json"],
            "hashlib.sha256((work / 'survey.json').read_bytes()).hexdigest() == originals['survey.json']",
        )
        require(notes, "notes")
        require(all(n["kind"] == "reused" for n in notes), "all((n[1]['kind'] == 'reused' for n in notes))")
    require(
        all(hashlib.sha256((source / name).read_bytes()).hexdigest() == digest for name, digest in originals.items()),
        "original survey artifacts changed",
    )
    report("PASS: copied saved survey adopted and reused twice; zero agent sessions; original artifacts unchanged")


if __name__ == "__main__":
    main()
