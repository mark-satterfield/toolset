"""Bounded pure checks for UI normalization and the optional receipt boundary."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.core.agents import AgentRunner
from orchestrator.core.models import AgentStep
from orchestrator.flows.spec_authoring_ui import normalize_ui


def main() -> None:
    rows = normalize_ui(
        {
            "uiItems": [
                {"item": "UI-1", "designSource": "unknown"},
                {"item": "UI-2", "designSource": "bundle", "bundle": "/missing"},
                {"item": "outside", "designSource": "none"},
            ]
        },
        {"UI-1", "UI-2"},
        {"bundles": []},
        None,
    )
    assert len(rows["uiItems"]) == 2
    assert all(row["designSource"] == "cds" for row in rows["uiItems"])
    assert rows["uiItems"][0]["artifact"] == {"kind": "page", "slug": "ui-1"}
    events = []

    def failed_receipt(*_args, **_kwargs) -> None:
        raise OSError("receipt destination unavailable")

    runner = SimpleNamespace(
        store=SimpleNamespace(accept=failed_receipt),
        emit=lambda *args, **kwargs: events.append((args, kwargs)),
    )
    step = AgentStep(
        "spec",
        "author",
        (),
        Path("document"),
        "Document.",
        Path("schema"),
        None,
        "sonnet",
        "medium",
    )
    try:
        AgentRunner._record_output(runner, step, step.output)
    except OSError:
        pass
    else:
        raise AssertionError("default receipt failure must propagate")
    AgentRunner._record_output(
        runner, replace(step, receipt_required=False), step.output
    )
    assert len(events) == 1 and events[0][1]["kind"] == "warning"
    print("PASS: UI scope/default/downgrade and required/optional receipt checks")


if __name__ == "__main__":
    main()
