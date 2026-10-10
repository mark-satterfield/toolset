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

from typeguard import CollectionCheckStrategy, check_type, typechecked

from .io import JsonValue, json_object
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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_artifactio(path: Path | None = None) -> ModuleType:
    """Load the configured receipt implementation and verify its public contract.

    Returns:
        The imported receipt module.

    Raises:
        StepError: The configured receipt implementation is incomplete.

    """
    stage = "input"
    source = (path or Path(os.environ["ATW_ARTIFACT_SCRIPT"])).resolve()
    parent = str(source.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("atw_artifactio", source)
    if spec is None or spec.loader is None:
        raise StepError(stage, "other", (f"cannot load artifact script: {source}",))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with contextlib.redirect_stdout(sys.stderr):
        spec.loader.exec_module(module)
    missing = [
        name
        for name in (
            "record",
            "RecordOptions",
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
            stage,
            "other",
            tuple(f"artifactio lacks {name}" for name in missing),
        )
    return module


class ArtifactStore:
    """Receipt authority for one dispatch and its accepted output files."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(
        self,
        module: ModuleType,
        root: Path,
        work: Path,
        epic: str,
        run_id: str,
    ) -> None:
        """Bind the receipt implementation and this dispatch identity."""
        self.module = module
        self.root = root
        self.work = work
        self.epic = epic
        self.run_id = run_id
        self._lock = threading.Lock()

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def reusable(self, inputs: tuple[str, ...], outputs: tuple[Path, ...]) -> bool:
        """Check all current inputs and output receipts before accepting reuse.

        Returns:
            Whether every output and its original inputs remain unchanged.

        """
        if not outputs:
            return False
        current = check_type(
            self.module.hashed_inputs(list(inputs), self.root),
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        return all(self._output_reusable(output, current) for output in outputs)

    def _output_reusable(self, output: Path, current: list[dict[str, JsonValue]]) -> bool:
        try:
            text = output.with_name(output.name + ".meta.json").read_text(encoding="utf-8")
            digest = check_type(self.module.sha256_file(output), str)
        except FileNotFoundError:
            return False
        meta = json_object(json.loads(text))
        if check_type(meta["sha256"], str) != digest:
            return False
        recorded = check_type(
            meta["inputs"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        for entry in current:
            candidates = [
                item for item in recorded if (item.get("path"), item.get("kind")) == (entry["path"], entry["kind"])
            ]
            if entry not in candidates:
                return False
        return not any(check_type(self.module.input_problem(item, self.root, output), str | None) for item in recorded)

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def invalidate(outputs: tuple[Path, ...]) -> None:
        """Remove receipts so failed or changed artifacts cannot be reused."""
        for output in outputs:
            output.with_name(output.name + ".meta.json").unlink(missing_ok=True)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def accept(
        self,
        step: str,
        inputs: tuple[str, ...],
        outputs: tuple[Path, ...],
        producer: str = "python",
    ) -> None:
        """Accept every output receipt, invalidating all receipts if one fails."""
        with self._lock:
            try:
                for output in outputs:
                    options = self.module.RecordOptions(
                        epic=self.epic,
                        phase=step,
                        inputs=list(inputs),
                        producer=producer,
                        run_id=self.run_id,
                        root=self.root,
                    )
                    self.module.record(output, options)
                self.module.complete_step(self.work, step)
            except BaseException:
                self.invalidate(outputs)
                raise

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def execute(self, step: DeterministicStep) -> tuple[str, object]:
        """Run one deterministic step or reuse its accepted output.

        Returns:
            The reuse status and the action result.

        Raises:
            StepError: The deterministic step failed.

        """
        try:
            if step.reusable and self.reusable(step.inputs, step.outputs):
                return "reused", None
            self.invalidate(step.outputs)
            with contextlib.redirect_stdout(sys.stderr):
                result = step.action()
            self.accept(step.stage, step.inputs, step.outputs)
        except StepError:
            raise
        except Exception as exc:
            self.work.mkdir(parents=True, exist_ok=True)
            evidence = self.work / (self.module.safe_key(step.stage) + ".traceback.txt")
            evidence.write_text(traceback.format_exc(), encoding="utf-8")
            raise StepError(step.stage, "other", (str(evidence),)) from exc
        else:
            return "ran", result
