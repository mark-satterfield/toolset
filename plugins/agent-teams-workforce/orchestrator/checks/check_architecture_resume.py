"""Prove saved survey adoption on copies; never launch a pipeline or an agent."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.core.tools import Tools
from orchestrator.flows.architecture_survey import SURVEY_FILES, current_survey


def main() -> None:
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
        work = Path(temp)
        for name in originals:
            shutil.copy2(source / name, work / name)
        tools = Tools(work / "evidence")
        notes = []

        def unexpected_session(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("survey reuse started an agent session")

        flow = SimpleNamespace(
            work=work,
            schemas=tools.plugin / "skills/artifact-handoff/schemas",
            call=tools.portfolio,
            adopted=False,
            checked=lambda result, _stage: result,
            runner=SimpleNamespace(
                emit=lambda *a, **k: notes.append((a, k)), run=unexpected_session
            ),
        )
        assert current_survey(flow), "saved survey binding is no longer current"
        assert flow.adopted, "legacy survey was not adopted"
        assert current_survey(flow), "adopted seal cannot be reused"
        assert (
            hashlib.sha256((work / "survey.json").read_bytes()).hexdigest()
            == originals["survey.json"]
        )
        assert notes and all(n[1]["kind"] == "reused" for n in notes)
    assert all(
        hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
        for name, digest in originals.items()
    )
    print(
        "PASS: copied saved survey adopted and reused twice; zero agent sessions; original artifacts unchanged"
    )


if __name__ == "__main__":
    main()
