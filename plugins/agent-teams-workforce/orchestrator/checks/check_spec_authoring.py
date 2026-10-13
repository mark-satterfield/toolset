"""Bounded checks for UI normalization, the receipt failure boundary and the flow's review call."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))
import cdsbundles
from orchestrator.checks.check_spec_review import Scenario, Sessions, build_scenario, finding, step_names
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback_contract import EVENT_KEY, EventName
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.models import AgentStep, RunContext, StepError
from orchestrator.core.tools import Tools
from orchestrator.flows import spec_authoring
from orchestrator.flows.spec_authoring import SpecAuthoring
from orchestrator.flows.spec_authoring_ui import normalize_ui
from recon_contract import (
    ARTIFACT_KIND_PAGE,
    DEFAULT_DESIGN_SOURCE,
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
from spec_review_contract import DOCUMENT_SPEC

AUTHORED: int = 3


class ReceiptRunner(AgentRunner):
    """Expose the receipt operation to the existing isolated check."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def record_output(self, step: AgentStep) -> None:
        """Record one already validated output without dispatching an agent."""
        self._record_output(step, step.output)


def run_flow(root: Path, sessions: Sessions) -> tuple[Scenario, MagicMock, dict[str, JsonValue] | None]:
    """Run the whole repository flow with stand-in sessions and the Story write replaced.

    Returns:
        The scenario, the stand-in for the Story write, and the flow's result (None when it raised
        the StepError a failed session gives).

    """
    scenario: Scenario = build_scenario(root, sessions)
    written: dict[str, JsonValue] = {"story": {"id": "story-1", "elabKey": "S1"}, "summary": "written"}
    result: dict[str, JsonValue] | None = None
    with patch.object(SpecAuthoring, "write_story", return_value=written) as write_story:
        try:
            result = spec_authoring.run(
                scenario.flow.context,
                scenario.store,
                scenario.runner,
                Tools(root / "evidence"),
            )
        except StepError:
            result = None
    return scenario, write_story, result


def check_review_call(root: Path) -> None:
    """Check where the flow's one review call sits: after the documents, before the Story.

    What the review step itself does with findings, disputes and rulings is checked in
    check_spec_review.py; this checks the flow around the call.
    """
    passed: Scenario
    story_write: MagicMock
    result: dict[str, JsonValue] | None
    passed, story_write, result = run_flow(root / "passes", Sessions())
    require(step_names(passed.runner.steps)[AUTHORED:] == ["review"], "a passing review is the flow's last session")
    require(result is not None and result["ok"] is True, "a passing review lets the flow finish")
    require(story_write.call_count == 1 and passed.flow.story.is_file(), "the Story is written after a passing review")

    corrected: Scenario
    corrected, story_write, result = run_flow(
        root / "findings",
        Sessions(findings=[finding("F1", DOCUMENT_SPEC, "I1")]),
    )
    after: list[str] = step_names(corrected.runner.steps)[AUTHORED:]
    require(after[:2] == ["review", "spec.correction"], f"a finding does not reach its author next: {after}")
    require(after.count("spec.correction") == 1, "the author corrects its document once")
    require(result is not None and story_write.call_count == 1, "the Story is written after the one correction")
    require(result is not None and result["resumed"] is False, "a run that started sessions is not a resumed run")

    failed: Scenario
    failed, story_write, result = run_flow(root / "fails", Sessions(reviewer_fails=True))
    require(result is None, "a failed reviewer session must fail the flow")
    require(step_names(failed.runner.steps)[AUTHORED:] == ["review"], "nothing runs after a failed review")
    require(story_write.call_count == 0 and not failed.flow.story.exists(), "no Story is written after a failed review")
    report("PASS: the flow reviews after the documents; a finding is corrected once; a failed review writes no Story")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate UI defaults and that a real receipt failure propagates without a warning.

    ``require`` fails the check when a receipt failure was swallowed or downgraded to a warning.
    """
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        # The listing the flow passes: the real producer's result for a run with no packages directory.
        no_bundles: dict[str, JsonValue] = json_object(cdsbundles.list_bundles(None))
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
            no_bundles,
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
        defaulted: dict[str, JsonValue] = normalize_ui(
            {KEY_UI_ITEMS: [{KEY_ITEM: "UI-1", KEY_DESIGN_SOURCE: "unknown"}]},
            {"UI-1"},
            no_bundles,
            Tools(root / "evidence"),
        )
        defaulted_items: list[dict[str, JsonValue]] = check_type(
            defaulted[KEY_UI_ITEMS],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        require(
            [row[KEY_DESIGN_SOURCE] for row in defaulted_items] == [DEFAULT_DESIGN_SOURCE],
            "an unknown design source did not take the default",
        )
        require(
            any(
                "unknown design source" in warning
                for warning in check_type(
                    defaulted["warnings"],
                    list[str],
                    collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                )
            ),
            "an unknown design source was defaulted without a warning",
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
        )
        with expected_error(OSError) as caught:
            runner.record_output(step)
        require(len(caught) == 1, "receipt failure must propagate")
        require(not events, "a receipt failure must never be downgraded to a warning")
    report("PASS: UI scope/default/downgrade and receipt failure propagation checks")
    with tempfile.TemporaryDirectory() as flows:
        check_review_call(Path(flows).resolve())


if __name__ == "__main__":
    main()
