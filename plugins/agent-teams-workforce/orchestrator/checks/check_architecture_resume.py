"""Prove saved survey adoption on copies; never launch a pipeline or an agent."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from typing import override

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff"))

import archbaseline
from contracts import SealForm, survey_seal_path
from orchestrator.checks.check_support import report, require
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import EVENT_KEY, REUSED_NOTE, EventName
from orchestrator.core.io import JsonValue, write_json
from orchestrator.core.models import AgentStep, RunContext
from orchestrator.core.tools import Tools
from orchestrator.flows.architecture_support import Architecture
from orchestrator.flows.architecture_survey import SURVEY_FILES, current_survey
from survey_contract import SURVEY_FILE


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


_SEAL_NAME: str = survey_seal_path(Path(SURVEY_FILE)).name


def _names_no_form(seal: Path) -> bool:
    """Read whether a saved survey seal names no form, which is the form the survey step adopts.

    Returns:
        True for a seal with no form; False for a seal that names its form.

    Raises:
        TypeError: seal is not a Path.
        ValueError: The seal is missing or fails the seal contract.

    """
    if not isinstance(seal, Path):
        argument_error: str = "_names_no_form requires a Path"
        raise TypeError(argument_error)
    binding: tuple[SealForm | None, str] | None = archbaseline.survey_binding(seal)
    if binding is None:
        message: str = f"--survey-dir holds no readable survey seal: {seal}"
        raise ValueError(message)
    return binding[0] is None


def _reused_twice(flow: Architecture, originals: dict[str, str], *, legacy: bool) -> None:
    """Require the copied survey to be reused twice, adopted only when its seal names no form."""
    seal: Path = flow.work / _SEAL_NAME
    survey: Path = flow.work / SURVEY_FILE
    require(current_survey(flow), "saved survey binding is no longer current")
    require(flow.adopted == legacy, "only a seal that names no form is adopted")
    require(current_survey(flow), "the seal cannot be reused a second time")
    require(
        legacy or hashlib.sha256(seal.read_bytes()).hexdigest() == originals[_SEAL_NAME],
        "reusing a seal that names its form rewrote it",
    )
    require(
        hashlib.sha256(survey.read_bytes()).hexdigest() == originals[SURVEY_FILE],
        "reusing the survey changed it",
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate saved-survey reuse on a copy of the directory `--survey-dir` names.

    `--survey-dir` is an architecture work directory holding a sealed `survey.json`, for example
    `<control repo>/.claude/workflow-runs/artifacts/<epic>/architecture`.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.survey_dir.resolve()
    legacy: bool = _names_no_form(source / _SEAL_NAME)
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

        def emit(event: EventName, **fields: JsonValue) -> None:
            notes.append({EVENT_KEY: event, **fields})

        dispatch: DispatchArguments = dispatch_arguments()
        context = RunContext(
            "epic",
            "architecture",
            {
                dispatch.KEY_ARCH_PATH: str(root / "vault"),
                dispatch.KEY_PRD: {dispatch.PRD_PATH: str(root / "prd.md")},
            },
            root,
            "survey-check",
        )
        store = ArtifactStore(load_artifactio(), root, work, "epic", "survey-check")
        runner = NoAgentRunner(context, store, emit=emit)
        matrix = root / "matrix.json"
        write_json(matrix, {"elements": {}})
        flow = Architecture(context, store, runner, tools, matrix)
        _reused_twice(flow, originals, legacy=legacy)
        require(notes, "notes")
        require(all(n["kind"] == REUSED_NOTE for n in notes), "every emitted note must be a reused note")
    require(
        all(hashlib.sha256((source / name).read_bytes()).hexdigest() == digest for name, digest in originals.items()),
        "original survey artifacts changed",
    )
    report(
        f"PASS: copied saved survey ({'adopted' if legacy else 'sealed form kept'}) reused twice; "
        "zero agent sessions; original artifacts unchanged",
    )


if __name__ == "__main__":
    main()
