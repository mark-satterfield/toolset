"""Bounded pure checks for UI normalization and the receipt failure boundary."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback_contract import EVENT_KEY, EventName
from orchestrator.core.io import JsonValue
from orchestrator.core.models import AgentStep, RunContext
from orchestrator.core.tools import Tools
from orchestrator.flows.spec_authoring_ui import normalize_ui
from recon_contract import (
    ARTIFACT_KIND_PAGE,
    DESIGN_SOURCE_BUNDLE,
    DESIGN_SOURCE_CDS,
    DESIGN_SOURCE_NONE,
    KEY_ARTIFACT,
    KEY_BUNDLE,
    KEY_DESIGN_SOURCE,
    KEY_ITEM,
    KEY_KIND,
    KEY_SLUG,
    KEY_UI_ITEMS,
)


class ReceiptRunner(AgentRunner):
    """Expose the receipt operation to the existing isolated check."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def record_output(self, step: AgentStep) -> None:
        """Record one already validated output without dispatching an agent."""
        self._record_output(step, step.output)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate UI defaults and that a real receipt failure propagates without a warning.

    ``require`` fails the check when a receipt failure was swallowed or downgraded to a warning.
    """
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rows = normalize_ui(
            {
                KEY_UI_ITEMS: [
                    # A valid source with no artifact: normalization assigns the default page artifact.
                    {KEY_ITEM: "UI-1", KEY_DESIGN_SOURCE: DESIGN_SOURCE_CDS},
                    {KEY_ITEM: "UI-2", KEY_DESIGN_SOURCE: DESIGN_SOURCE_BUNDLE, KEY_BUNDLE: "/missing"},
                    {KEY_ITEM: "outside", KEY_DESIGN_SOURCE: DESIGN_SOURCE_NONE},
                ],
            },
            {"UI-1", "UI-2"},
            {"bundles": []},
            Tools(root / "evidence"),
        )
        items = check_type(
            rows[KEY_UI_ITEMS],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        require(len(items) == len({"UI-1", "UI-2"}), "UI scope changed")
        require(all(row[KEY_DESIGN_SOURCE] == DESIGN_SOURCE_CDS for row in items), "invalid bundles did not use CDS")
        require(
            items[0][KEY_ARTIFACT] == {KEY_KIND: ARTIFACT_KIND_PAGE, KEY_SLUG: "ui-1"},
            "UI artifact default changed",
        )
        with expected_error(ValueError):
            normalize_ui(
                {KEY_UI_ITEMS: [{KEY_ITEM: "UI-1", KEY_DESIGN_SOURCE: "unknown"}]},
                {"UI-1"},
                {"bundles": []},
                Tools(root / "evidence"),
            )
        events: list[dict[str, JsonValue]] = []

        def emit(event: EventName, **fields: JsonValue) -> None:
            events.append({EVENT_KEY: event, **fields})

        context = RunContext("epic", dispatch_arguments().FLOW_PRD_TO_SPEC, {}, root, "receipt-probe")
        store = ArtifactStore(load_artifactio(), root, root, "epic", "receipt-probe")
        runner = ReceiptRunner(context, store, emit=emit)
        document = root / "document.md"
        document.write_text("# Document\n", encoding="utf-8")
        # The real receipt path is occupied by a directory, so the real store fails to read it.
        document.with_name(document.name + ".meta.json").mkdir()
        step = AgentStep(
            "spec",
            "author",
            (),
            document,
            "Document.",
            root / "schema",
            None,
            "sonnet",
            "medium",
        )
        with expected_error(OSError) as caught:
            runner.record_output(step)
        require(len(caught) == 1, "receipt failure must propagate")
        require(not events, "a receipt failure must never be downgraded to a warning")
    report("PASS: UI scope/default/downgrade and receipt failure propagation checks")


if __name__ == "__main__":
    main()
