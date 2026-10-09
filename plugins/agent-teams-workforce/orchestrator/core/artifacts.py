"""Use the driver's existing artifact receipts as the sole reuse authority."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
import threading
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any

from .models import DeterministicStep, StepError

REQUIRED_KINDS = {
    "file",
    "dir",
    "missing",
    "arc42-revision",
    "arch-views",
    "value",
    "matrix-rows",
}


def load_artifactio(path: Path | None = None) -> ModuleType:
    source = path or Path(os.environ["ATW_ARTIFACT_SCRIPT"])
    spec = importlib.util.spec_from_file_location("atw_artifactio", source)
    if spec is None or spec.loader is None:
        raise StepError("input", "other", (f"cannot load artifact script: {source}",))
    module = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(sys.stderr):
        spec.loader.exec_module(module)
    missing = [
        name
        for name in (
            "record",
            "hashed_inputs",
            "input_problem",
            "complete_step",
            "working_dir",
        )
        if not callable(getattr(module, name, None))
    ]
    missing.extend(sorted(REQUIRED_KINDS - set(getattr(module, "INPUT_KINDS", ()))))
    if missing:
        raise StepError(
            "input", "other", tuple(f"artifactio lacks {name}" for name in missing)
        )
    return module


class ArtifactStore:
    def __init__(
        self, module: ModuleType, root: Path, work: Path, epic: str, run_id: str
    ) -> None:
        self.module = module
        self.root = root
        self.work = work
        self.epic = epic
        self.run_id = run_id
        self._lock = threading.Lock()

    def reusable(self, inputs: tuple[str, ...], outputs: tuple[Path, ...]) -> bool:
        if not outputs:
            return False
        current = self.module.hashed_inputs(list(inputs), self.root)
        for output in outputs:
            try:
                meta = json.loads(
                    output.with_name(output.name + ".meta.json").read_text()
                )
                if meta["sha256"] != self.module.sha256_file(output):
                    return False
                recorded = meta["inputs"]
                for entry in current:
                    candidates = [
                        item
                        for item in recorded
                        if (item.get("path"), item.get("kind"))
                        == (entry["path"], entry["kind"])
                    ]
                    if entry not in candidates:
                        return False
                if any(
                    self.module.input_problem(item, self.root, output)
                    for item in recorded
                ):
                    return False
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                return False
        return True

    def invalidate(self, outputs: tuple[Path, ...]) -> None:
        for output in outputs:
            output.with_name(output.name + ".meta.json").unlink(missing_ok=True)

    def accept(
        self,
        step: str,
        inputs: tuple[str, ...],
        outputs: tuple[Path, ...],
        producer: str = "python",
    ) -> None:
        with self._lock:
            try:
                for output in outputs:
                    self.module.record(
                        output,
                        epic=self.epic,
                        phase=step,
                        inputs=list(inputs),
                        producer=producer,
                        run_id=self.run_id,
                        root=self.root,
                    )
                self.module.complete_step(self.work, step)
            except BaseException:
                self.invalidate(outputs)
                raise

    def execute(self, step: DeterministicStep) -> tuple[str, Any]:
        try:
            if step.reusable and self.reusable(step.inputs, step.outputs):
                return "reused", None
            self.invalidate(step.outputs)
            with contextlib.redirect_stdout(sys.stderr):
                result = step.action()
            self.accept(step.stage, step.inputs, step.outputs)
            return "ran", result
        except StepError:
            raise
        except Exception as exc:
            self.work.mkdir(parents=True, exist_ok=True)
            evidence = self.work / (self.module.safe_key(step.stage) + ".traceback.txt")
            evidence.write_text(traceback.format_exc())
            raise StepError(step.stage, "other", (str(evidence),)) from exc
