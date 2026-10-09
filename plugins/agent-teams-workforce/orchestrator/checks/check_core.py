"""Small isolated checks for artifact reuse and additive fingerprint kinds."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.models import DeterministicStep


def check_resume(module: object, root: Path) -> None:
    source, output = root / "input.txt", root / "output.txt"
    source.write_text("one")
    work = root / "work"
    work.mkdir()
    store = ArtifactStore(module, root, work, "epic", "run")
    calls = []

    def produce() -> None:
        calls.append(1)
        output.write_text(source.read_text())

    step = DeterministicStep("copy", (str(source),), (output,), produce)
    assert store.execute(step)[0] == "ran"
    assert store.execute(step)[0] == "reused"
    source.write_text("two")
    assert store.execute(step)[0] == "ran"
    assert len(calls) == 2
    output.write_text("tampered")
    assert not store.reusable(step.inputs, step.outputs)
    store.execute(step)
    extra = root / "extra.txt"
    extra.write_text("new dependency")
    assert not store.reusable((*step.inputs, str(extra)), step.outputs)
    value = 'value:{"name":"round","value":1}'
    store.accept("copy", (*step.inputs, value), step.outputs)
    assert store.reusable((*step.inputs, value), step.outputs)
    assert not store.reusable((*step.inputs, value.replace(":1", ":2")), step.outputs)
    print(
        "PASS: unchanged inputs skip; edits, tampering, added dependencies and changed values rerun"
    )


def check_matrix(module: object, root: Path) -> None:
    matrix = root / "matrix.json"
    data = {
        "elements": {
            "service": {"state": "built", "repository": "repo"},
            "repository:repo": {"contains": ["stack:repo/main"]},
        }
    }
    matrix.write_text(json.dumps(data))
    raw = "matrix-rows:" + json.dumps(
        {"matrix": str(matrix), "elements": ["service", "unknown"]}
    )
    before = module.hashed_inputs([raw], root)[0]
    data["elements"]["service"]["task"] = "different-task"
    matrix.write_text(json.dumps(data))
    assert module.input_problem(before, root) is None
    data["elements"]["service"]["state"] = "deployed"
    matrix.write_text(json.dumps(data))
    assert module.input_problem(before, root) is not None
    print(
        "PASS: matrix fingerprints ignore tracking facts and detect satisfaction changes"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-script", required=True, type=Path)
    options = parser.parse_args()
    module = load_artifactio(options.artifact_script)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        check_resume(module, root)
        check_matrix(module, root)


if __name__ == "__main__":
    main()
