"""Check the architecture work contract: generated files current, readers strict, reviewer selection by rule."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))
from architecture_work_contract import (
    ARCHITECTURE_RESULT_SCHEMA_PATH,
    CONCLUSION_COMPLETE_AND_APPROVED,
    ArchitectureResult,
    ArchitectureWorkError,
    is_scope_review,
    load_schema,
    validate_architecture_result,
)
from generate_architecture_work_contract import DOCUMENTS, OUTPUT_PATH, SCHEMA_DIR, SCHEMA_PATH, render, wrappers
from orchestrator.checks.check_support import expected_error, report, require
from review_criteria import Criteria, ScopeKind, load_criteria

SIGNALS_DEFINITION: Final[str] = "ReviewSignals"
NEW_DESIGN_SCOPE: Final[frozenset[ScopeKind]] = frozenset({"heading", "scenario-fact", "trd-requirement"})
APPROVED_SCOPE: Final[frozenset[ScopeKind]] = frozenset({"trd-requirement"})


def _generated_current() -> int:
    """Require the generated module and every wrapper schema to be what the schema produces.

    Returns:
        The number of schema files of the contract.

    """
    decoded: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    require(isinstance(decoded, dict), f"{SCHEMA_PATH.name} is not a JSON object")
    schema: dict[str, object] = {str(key): value for key, value in decoded.items()} if isinstance(decoded, dict) else {}
    require(
        OUTPUT_PATH.read_text(encoding="utf-8") == render(schema),
        f"{OUTPUT_PATH.name} is stale against {SCHEMA_PATH.name}",
    )
    Draft202012Validator.check_schema(schema)
    name: str
    text: str
    for name, text in wrappers().items():
        path: Path = SCHEMA_DIR / name
        require(path.is_file() and path.read_text(encoding="utf-8") == text, f"{name} is stale or missing")
    require(ARCHITECTURE_RESULT_SCHEMA_PATH == SCHEMA_PATH, "the generated module reads another root schema")
    return len(DOCUMENTS)


def _signal_names() -> frozenset[str]:
    """Name the lists of the architect's result a reviewer group may be selected by.

    Returns:
        The property names of the ReviewSignals definition.

    """
    definitions: object = load_schema().get("$defs")
    signals: object = definitions.get(SIGNALS_DEFINITION) if isinstance(definitions, dict) else None
    properties: object = signals.get("properties") if isinstance(signals, dict) else None
    require(isinstance(properties, dict) and bool(properties), f"the schema defines no {SIGNALS_DEFINITION} lists")
    return frozenset(properties) if isinstance(properties, dict) else frozenset()


def _selected(criteria: Criteria, scope: frozenset[ScopeKind], signals: frozenset[str]) -> list[str]:
    """Apply every group's rule to one run.

    Returns:
        The reviewers selected, sorted.

    """
    return sorted({group.reviewer for group in criteria.groups if group.applies_when.selects(scope, signals)})


def _selection(criteria: Criteria) -> None:
    """Require the selection rules to name real result lists and to select by content alone."""
    known: frozenset[str] = _signal_names()
    for group in criteria.groups:
        unknown: list[str] = sorted(set(group.applies_when.result) - known)
        require(not unknown, f"reviewer group {group.id} is selected by lists the result does not have: {unknown}")
    require(
        _selected(criteria, APPROVED_SCOPE, frozenset()) == ["trd-validator"],
        "an Epic whose architecture is approved is reviewed by trd-validator alone",
    )
    require(
        _selected(criteria, NEW_DESIGN_SCOPE, frozenset())
        == ["architecture-boundary-guardian", "failure-mode-analyst", "trd-validator"],
        "new headings, a scenario and a TRD select the boundary, failure and TRD reviewers",
    )
    require(
        "cost-architecture-reviewer" in _selected(criteria, APPROVED_SCOPE, frozenset({"newBillableResources"})),
        "a new billable resource selects the cost reviewer",
    )
    require(not _selected(criteria, frozenset(), frozenset()), "a run with nothing unapproved selects no reviewer")


def _readers() -> None:
    """Require the readers to accept a complete document and refuse one that is not."""
    result: ArchitectureResult = {
        "bead": "epic-1",
        "conclusion": CONCLUSION_COMPLETE_AND_APPROVED,
        "features": [],
        "newElements": [],
        "sharedCapabilities": [],
        "facts": [],
        "settledDisagreements": [],
        "criteria": [],
        "notesForSpecs": [],
        "unsettled": [],
        "reviewSignals": {
            "newRuntimeResources": [],
            "newBillableResources": [],
            "changedBillableLimits": [],
            "choices": [],
            "newPatterns": [],
            "failureBehaviours": [],
        },
        "costEvidence": [],
        "summary": "Everything the PRD needs exists and is approved.",
    }
    require(validate_architecture_result(result) == result, "a complete result is accepted")
    without_signals: dict[str, object] = {key: value for key, value in result.items() if key != "reviewSignals"}
    with expected_error(ArchitectureWorkError):
        validate_architecture_result(without_signals)
    with expected_error(ArchitectureWorkError):
        validate_architecture_result({**result, "conclusion": "approved"})
    require(not is_scope_review({"passed": [], "findings": []}), "a review that leaves out a list is refused")
    require(
        is_scope_review({
            "passed": ["T1"],
            "findings": [],
            "dependsOnApproved": [],
            "alternativesRequested": [],
            "summary": "One requirement, sound.",
        }),
        "a review that passes its scope is accepted",
    )


def main() -> None:
    """Check the generated contract, its readers and the reviewer selection rules."""
    documents: int = _generated_current()
    criteria: Criteria = load_criteria()
    _selection(criteria)
    _readers()
    report(
        f"PASS: {documents} architecture work documents defined once; generated module and wrappers current; "
        f"{len(criteria.groups)} reviewer groups selected by rule",
    )


if __name__ == "__main__":
    main()
