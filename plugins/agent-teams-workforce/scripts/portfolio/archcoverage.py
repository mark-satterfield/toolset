"""Fold architecture coverage evidence into the existing round ledger.

Consumed by: archresume.resume_facts and the architecture flow
(orchestrator/flows/architecture_support.py) — report missing, unresolved
or unreviewed coverage to the coordinator and the decider; arch-review-check reads the
approved rows from the arch-resume relay file.
The coverage row, its statuses, actions and dispositions are defined once, in the
artifact-handoff skill's survey.schema.json; survey_contract is its generated Python view.
Rows arrive already parsed: the survey through survey_contract.parse_survey, writer rows and
review checks through architecture_artifacts' parsers, so this module reads no file and
re-validates nothing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import starmap
from typing import TypedDict

import portfolio_path  # ruff: ignore[unused-import] - puts skills/artifact-handoff and its scripts on sys.path.
import survey_contract
from archevidence import evidence_state, view_bindings
from architecture_artifacts import VERDICT_VERIFIED, CoverageCheck
from contracts import JsonInput, JsonObject, json_object
from roundcontracts import RevisionRef
from survey_contract import (
    ACTION_NOT_APPLICABLE,
    ACTION_UNCHANGED,
    ACTION_UNRESOLVED,
    COVERAGE_STATUS_ACTION,
    COVERAGE_UNRELATED_DEBT,
    STATUS_NOT_YET_APPLICABLE,
    STATUS_PRESENT_AND_SUFFICIENT,
    CoverageAction,
    CoverageRow,
    CoverageStatus,
    Survey,
)

#: The `by` value of a coverage row the survey authored.
SURVEY_AUTHOR: str = "survey"


class LedgerCoverageRow(CoverageRow):
    """A contract coverage row plus the review evidence the ledger adds to it."""

    by: str
    revision: str
    review: JsonObject | None
    evidenceState: list[JsonObject]  # ruff: ignore[mixed-case-variable-in-class-scope] - JSON ledger key; ruff exempts only direct TypedDict subclasses.
    viewState: dict[str, str]  # ruff: ignore[mixed-case-variable-in-class-scope] - JSON ledger key; ruff exempts only direct TypedDict subclasses.
    excluded: bool


class CoverageFacts(TypedDict):
    """The persistent coverage evidence returned to the ledger writer."""

    coverage: list[LedgerCoverageRow]
    coverageRevision: str


class CoverageSummary(TypedDict):
    """The exact compact projection consumed by the decider."""

    revision: str
    gaps: list[str]
    warnings: list[str]
    rows: int
    checksNeeded: list[RevisionRef]


@dataclass(frozen=True)
class RoundCoverage:
    """The coverage one parsed round result carries.

    A writer result (architecture-writer schema) supplies `rows`; a review result
    (architecture-review schema) supplies `checks`. `agent` is the roster agent that saved it.
    """

    agent: str
    rows: tuple[CoverageRow, ...] = ()
    checks: tuple[CoverageCheck, ...] = ()

    def __post_init__(self) -> None:
        """Reject an agent-less or wrongly typed round coverage.

        Raises:
            TypeError: A field has the wrong type.
            ValueError: The agent is empty.

        """
        if not isinstance(self.agent, str) or not isinstance(self.rows, tuple) or not isinstance(self.checks, tuple):
            message: str = "RoundCoverage requires an agent string and tuples of rows and checks"
            raise TypeError(message)
        if not self.agent:
            message = "RoundCoverage requires a non-empty agent"
            raise ValueError(message)


@dataclass(frozen=True)
class _Origin:
    row: CoverageRow
    by: str


@dataclass(frozen=True)
class _Check:
    check: CoverageCheck
    by: str


#: Actions that require a readable architecture view.
_VIEW_ACTIONS: frozenset[CoverageAction] = frozenset(
    survey_contract.COVERAGE_ACTIONS - {ACTION_NOT_APPLICABLE, ACTION_UNRESOLVED},
)
#: Statuses that resolve an assessment.
_RESOLVED_STATUSES: frozenset[CoverageStatus] = frozenset({STATUS_PRESENT_AND_SUFFICIENT, STATUS_NOT_YET_APPLICABLE})


def _digest(value: JsonInput) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _collect(
    survey: Survey | None,
    rounds: Sequence[RoundCoverage],
    gaps: list[str],
) -> tuple[dict[str, _Origin], list[_Check]]:
    """Gather survey and writer coverage rows and the reviewers' coverage checks.

    A later writer row with the same id replaces an earlier one; a row with an empty id
    cannot be tracked and is reported as a gap.

    Returns:
        The coverage rows by id with their author, and every review coverage check in order.

    """
    rows: dict[str, _Origin] = {}
    checks: list[_Check] = []
    sources: list[tuple[str, Sequence[CoverageRow]]] = [(SURVEY_AUTHOR, survey["coverage"] if survey else [])]
    sources.extend((item.agent, item.rows) for item in rounds)
    by: str
    authored: Sequence[CoverageRow]
    for by, authored in sources:
        for row in authored:
            if row["id"]:
                rows[row["id"]] = _Origin(row, by)
            else:
                gaps.append(f"coverage: a row by {by} has no id")
    for item in rounds:
        checks.extend(_Check(check, item.agent) for check in item.checks)
    return rows, checks


def _derive_action(row: CoverageRow, warnings: list[str]) -> CoverageRow:
    """Apply the status-to-action rule to one row.

    A status COVERAGE_STATUS_ACTION maps fixes the action; otherwise `not-applicable` on a
    status that is not "Not yet applicable" means unchanged when the coverage is present
    and sufficient, and unresolved for every other status.

    Returns:
        The row with its derived action.

    """
    status: CoverageStatus = row["status"]
    action: CoverageAction = row["action"]
    derived: CoverageAction = action
    if status in COVERAGE_STATUS_ACTION:
        derived = COVERAGE_STATUS_ACTION[status]
    elif action == ACTION_NOT_APPLICABLE:
        derived = ACTION_UNCHANGED if status == STATUS_PRESENT_AND_SUFFICIENT else ACTION_UNRESOLVED
    if derived == action:
        return row
    warnings.append(f"coverage {row['id']}: action {action} derived as {derived} from status {status}")
    return {**row, "action": derived}


@dataclass
class _CoverageState:
    checks: list[_Check]
    repository_paths: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def _exclusion_gaps(self, key: str, row: CoverageRow, content: dict[str, str]) -> None:
        status: CoverageStatus = row["status"]
        action: CoverageAction = row["action"]
        if status not in _RESOLVED_STATUSES:
            self.gaps.append(f"coverage {key}: assessment is not resolved ({status})")
        if action == ACTION_UNRESOLVED:
            self.gaps.append(f"coverage {key}: applicability or required design remains unresolved")
        unreadable: bool = not content or any(
            v == "absent" or v.startswith(("invalid:", "unreadable:")) for v in content.values()
        )
        if action in _VIEW_ACTIONS and unreadable:
            self.gaps.append(f"coverage {key}: required view missing or unreadable")

    def render(self, key: str, item: _Origin) -> LedgerCoverageRow:
        evidence: list[JsonObject]
        evidence_warnings: list[str]
        row: CoverageRow = _derive_action(item.row, self.warnings)
        refs: list[JsonObject] = [json_object(ref) for ref in row["evidenceRefs"]]
        evidence, evidence_warnings = evidence_state(refs, repository_paths=self.repository_paths)
        self.warnings.extend(f"coverage {key}: {e}" for e in evidence_warnings)
        content: dict[str, str] = view_bindings(row["views"], refs)
        revision: str = _digest({"row": json_object(row), "files": content, "evidence": evidence})
        matching: list[_Check] = [
            c for c in self.checks if c.check["id"] == key and c.by != item.by and c.check["evidence"].strip()
        ]
        latest_check: _Check | None = matching[-1] if matching else None
        latest: JsonObject | None = (
            None if latest_check is None else json_object({**latest_check.check, "by": latest_check.by})
        )
        verified: bool = latest_check is not None and latest_check.check["verdict"] == VERDICT_VERIFIED
        debt: bool = row["disposition"] == COVERAGE_UNRELATED_DEBT
        reasoned: bool = bool(row["dispositionReason"].strip())
        if debt and not reasoned:
            self.warnings.append(f"coverage {key}: unrelated-debt without a dispositionReason is treated as required")
        excluded: bool = debt and reasoned and verified
        if not excluded:
            self._exclusion_gaps(key, row, content)
        if not verified:
            self.gaps.append(f"coverage {key}: no independent verified check")
        rendered: LedgerCoverageRow = {
            **row,
            "by": item.by,
            "revision": revision,
            "review": latest,
            "evidenceState": evidence,
            "viewState": content,
            "excluded": excluded,
        }
        return rendered


def coverage_facts(
    survey: Survey | None,
    rounds: Sequence[RoundCoverage],
    *,
    repository_paths: Mapping[str, str] | None = None,
) -> tuple[CoverageFacts, CoverageSummary]:
    """Fold inventory and independent checks into typed ledger rows.

    Args:
        survey: The saved survey as survey_contract.parse_survey returned it; None when no
            valid survey is saved.
        rounds: The coverage of every parsed round result, in round order.
        repository_paths: Local checkout path of each repository evidence may cite.

    Returns:
        Persistent coverage records and their compact decision summary.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if survey is not None and not isinstance(survey, dict):
        message: str = "coverage_facts: survey must be a parsed Survey or None"
        raise TypeError(message)
    if isinstance(rounds, str) or not all(isinstance(item, RoundCoverage) for item in rounds):
        message = "coverage_facts: rounds must be a sequence of RoundCoverage"
        raise TypeError(message)
    if repository_paths is not None and not isinstance(repository_paths, Mapping):
        message = "coverage_facts: repository_paths must be a mapping or None"
        raise TypeError(message)
    gaps: list[str] = []
    rows: dict[str, _Origin]
    checks: list[_Check]
    rows, checks = _collect(survey, rounds, gaps)
    state: _CoverageState = _CoverageState(checks, dict(repository_paths or {}), gaps=gaps)
    if not rows:
        state.gaps.append("coverage: no subject/obligation inventory; assess even a no-change target")
    rendered: list[LedgerCoverageRow] = list(starmap(state.render, sorted(rows.items())))
    refs: list[RevisionRef] = [{"id": row["id"], "revision": row["revision"]} for row in rendered]
    revision: str = _digest([json_object(ref) for ref in refs])
    compact: CoverageSummary = {
        "revision": revision,
        "gaps": state.gaps,
        "warnings": state.warnings,
        "rows": len(rendered),
        "checksNeeded": refs,
    }
    return {"coverage": rendered, "coverageRevision": revision}, compact
