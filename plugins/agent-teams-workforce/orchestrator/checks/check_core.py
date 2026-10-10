"""Small isolated checks for artifact reuse and additive fingerprint kinds."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.checks.check_support import report, require
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import DeterministicStep


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_resume(module: ModuleType, root: Path) -> None:
    """Evaluate the existing isolated check contract."""
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
    require(store.execute(step)[0] == "ran", "store.execute(step)[0] == 'ran'")
    require(store.execute(step)[0] == "reused", "store.execute(step)[0] == 'reused'")
    source.write_text("two")
    require(store.execute(step)[0] == "ran", "store.execute(step)[0] == 'ran'")
    require(len(calls) == len(("initial", "changed")), "initial and changed inputs each execute once")
    output.write_text("tampered")
    require(not store.reusable(step.inputs, step.outputs), "not store.reusable(step.inputs, step.outputs)")
    store.execute(step)
    extra = root / "extra.txt"
    extra.write_text("new dependency")
    require(
        not store.reusable((*step.inputs, str(extra)), step.outputs),
        "not store.reusable((*step.inputs, str(extra)), step.outputs)",
    )
    value = 'value:{"name":"round","value":1}'
    store.accept("copy", (*step.inputs, value), step.outputs)
    require(store.reusable((*step.inputs, value), step.outputs), "store.reusable((*step.inputs, value), step.outputs)")
    require(
        not store.reusable((*step.inputs, value.replace(":1", ":2")), step.outputs),
        "not store.reusable((*step.inputs, value.replace(':1', ':2')), step.outputs)",
    )
    report("PASS: unchanged inputs skip; edits, tampering, added dependencies and changed values rerun")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_matrix(module: ModuleType, root: Path) -> None:
    """Evaluate the existing isolated check contract."""
    matrix = root / "matrix.json"
    data: dict[str, JsonValue] = {
        "elements": {
            "service": {"state": "built", "repository": "repo"},
            "repository:repo": {"contains": ["stack:repo/main"]},
        },
    }
    matrix.write_text(json.dumps(data))
    raw = "matrix-rows:" + json.dumps(
        {"matrix": str(matrix), "elements": ["service", "unknown"]},
    )
    hashed = check_type(
        module.hashed_inputs([raw], root),
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    before = hashed[0]
    json_object(json_object(data["elements"])["service"])["task"] = "different-task"
    matrix.write_text(json.dumps(data))
    require(module.input_problem(before, root) is None, "module.input_problem(before, root) is None")
    json_object(json_object(data["elements"])["service"])["state"] = "deployed"
    matrix.write_text(json.dumps(data))
    require(module.input_problem(before, root) is not None, "module.input_problem(before, root) is not None")
    report("PASS: matrix fingerprints ignore tracking facts and detect satisfaction changes")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract."""
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
