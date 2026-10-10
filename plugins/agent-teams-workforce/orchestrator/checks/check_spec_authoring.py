"""Bounded pure checks for UI normalization and the optional receipt boundary."""

from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import override

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.checks.check_support import report, require
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.io import JsonValue
from orchestrator.core.models import AgentStep, RunContext
from orchestrator.core.tools import Tools
from orchestrator.flows.spec_authoring_ui import normalize_ui


class UnavailableReceiptStore(ArtifactStore):
    """A typed store whose receipt destination is unavailable."""

    @override
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def accept(self, step: str, inputs: tuple[str, ...], outputs: tuple[Path, ...], producer: str = "python") -> None:
        """Fail the existing receipt probe without writing an artifact.

        Raises:
            OSError: The fixture destination is unavailable.

        """
        message = "receipt destination unavailable"
        raise OSError(message)


class ReceiptRunner(AgentRunner):
    """Expose the receipt operation to the existing isolated check."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def record_output(self, step: AgentStep) -> None:
        """Record one already validated output without dispatching an agent."""
        self._record_output(step, step.output)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate UI defaults and required versus optional receipts.

    Raises:
        AssertionError: A required receipt failure was swallowed.

    """
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rows = normalize_ui(
            {
                "uiItems": [
                    {"item": "UI-1", "designSource": "unknown"},
                    {"item": "UI-2", "designSource": "bundle", "bundle": "/missing"},
                    {"item": "outside", "designSource": "none"},
                ],
            },
            {"UI-1", "UI-2"},
            {"bundles": []},
            Tools(root / "evidence"),
        )
        items = check_type(
            rows["uiItems"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        require(len(items) == len({"UI-1", "UI-2"}), "UI scope changed")
        require(all(row["designSource"] == "cds" for row in items), "invalid bundles did not use CDS")
        require(items[0]["artifact"] == {"kind": "page", "slug": "ui-1"}, "UI artifact default changed")
        events: list[dict[str, object]] = []

        def emit(event: str, **fields: object) -> None:
            events.append({"event": event, **fields})

        context = RunContext("epic", "prd-to-spec", {}, root, "receipt-probe")
        store = UnavailableReceiptStore(load_artifactio(), root, root, "epic", "receipt-probe")
        runner = ReceiptRunner(context, store, emit=emit)
        step = AgentStep(
            "spec",
            "author",
            (),
            root / "document",
            "Document.",
            root / "schema",
            None,
            "sonnet",
            "medium",
        )
        try:
            runner.record_output(step)
        except OSError:
            pass
        else:
            message = "default receipt failure must propagate"
            raise AssertionError(message)
        runner.record_output(replace(step, receipt_required=False))
        require(len(events) == 1 and events[0]["kind"] == "warning", "optional receipt must warn")
    report("PASS: UI scope/default/downgrade and required/optional receipt checks")


if __name__ == "__main__":
    main()
