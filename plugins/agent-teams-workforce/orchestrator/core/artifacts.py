"""Use the driver's existing artifact receipts as the sole reuse authority."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
import threading
import traceback
from collections.abc import Callable
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from driver_surface_types import ARTIFACT_SCRIPT_ENV

from .artifact_contract import ArtifactProducer
from .handback_contract import OTHER_CAUSE, REUSED_PHASE
from .io import JsonValue, json_object, write_json
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
def load_artifactio(path: Path | None = None) -> ArtifactProducer:
    """Load the configured receipt implementation and verify its public contract.

    Returns:
        The imported receipt module.

    Raises:
        StepError: The configured receipt implementation is incomplete.

    """
    stage = "input"
    source = (path or Path(os.environ[ARTIFACT_SCRIPT_ENV])).resolve()
    parent = str(source.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("atw_artifactio", source)
    if spec is None or spec.loader is None:
        raise StepError(stage, OTHER_CAUSE, (f"cannot load artifact script: {source}",))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with contextlib.redirect_stdout(sys.stderr):
        spec.loader.exec_module(module)
    factory: Callable[[], object] = check_type(module.ArtifactProducer, Callable[[], object])
    producer: ArtifactProducer = check_type(factory(), ArtifactProducer)
    missing = sorted(REQUIRED_KINDS - producer.INPUT_KINDS)
    if missing:
        raise StepError(
            stage,
            OTHER_CAUSE,
            tuple(f"artifactio lacks {name}" for name in missing),
        )
    return producer


class ArtifactStore:
    """Receipt authority for one dispatch and its accepted output files."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(
        self,
        module: ArtifactProducer,
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
        return self._inputs_match(meta["inputs"], current, output)

    def _inputs_match(self, recorded_value: JsonValue, current: list[dict[str, JsonValue]], output: Path) -> bool:
        """Compare recorded input provenance with the current inputs, as receipt reuse does.

        Returns:
            Whether every current input is recorded unchanged and no recorded input is stale.

        """
        recorded = check_type(
            recorded_value,
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
    def fingerprint_path(output: Path) -> Path:
        """Name the file that records the inputs a session was launched with for ``output``.

        Returns:
            ``<output>.inputs.json`` beside the output.

        """
        return output.with_name(output.name + ".inputs.json")

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def record_fingerprint(self, inputs: tuple[str, ...], output: Path) -> None:
        """Record, before a session launches, the provenance of the inputs it will read.

        The provenance is ``hashed_inputs``, the same record an accepted receipt holds, so a
        saved output can later be shown to come from unchanged inputs.
        """
        current: list[dict[str, JsonValue]] = check_type(
            self.module.hashed_inputs(list(inputs), self.root),
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        write_json(self.fingerprint_path(output), {"inputs": list[JsonValue](current)})

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def fingerprint_matches(self, inputs: tuple[str, ...], output: Path) -> bool:
        """Decide whether a saved, unaccepted output was produced from the current inputs.

        Returns:
            Whether ``output`` exists and its recorded launch inputs match the current inputs.
            A missing output or a missing fingerprint is no match.

        """
        if not output.is_file():
            return False
        try:
            text: str = self.fingerprint_path(output).read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        current: list[dict[str, JsonValue]] = check_type(
            self.module.hashed_inputs(list(inputs), self.root),
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        return self._inputs_match(json_object(json.loads(text))["inputs"], current, output)

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

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def execute[T](self, step: DeterministicStep[T]) -> tuple[str, T | None]:
        """Run one deterministic step or reuse its accepted output.

        Returns:
            The reuse status and the action result.

        Raises:
            StepError: The deterministic step failed.

        """
        try:
            if step.reusable and self.reusable(step.inputs, step.outputs):
                return REUSED_PHASE, None
            self.invalidate(step.outputs)
            with contextlib.redirect_stdout(sys.stderr):
                result: T = step.action()
            self.accept(step.stage, step.inputs, step.outputs)
        except StepError:
            raise
        except Exception as exc:
            self.work.mkdir(parents=True, exist_ok=True)
            evidence = self.work / (self.module.safe_key(step.stage) + ".traceback.txt")
            evidence.write_text(traceback.format_exc(), encoding="utf-8")
            raise StepError(step.stage, OTHER_CAUSE, (str(evidence),)) from exc
        else:
            return "ran", result
