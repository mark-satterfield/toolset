"""Fold architecture coverage evidence into the existing round ledger.

Consumed by: archresume.resume_facts and architecture.js — report missing, unresolved
or unreviewed coverage to the coordinator and the decider; arch-review-check reads the
approved rows from the arch-resume relay file.
Project obligations and assessment vocabulary remain in the project's MODEL.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from itertools import starmap
from pathlib import Path
from typing import NotRequired, TypedDict

import contracts
from archevidence import evidence_state, view_bindings
from contracts import JsonInput, JsonObject, json_object
from jsonartifact import read_artifact
from roundcontracts import RevisionRef
from typeguard import CollectionCheckStrategy, check_type, typechecked


class CoverageRow(TypedDict):
    """The writer-normalized coverage row plus review evidence."""

    id: str
    subject: str
    scope: str
    obligation: str
    reason: str
    status: str
    action: str
    sources: list[str]
    views: list[str]
    disposition: str
    dispositionReason: NotRequired[str]
    evidenceRefs: NotRequired[list[JsonObject]]
    by: str
    revision: str
    review: JsonObject | None
    evidenceState: list[JsonObject]
    viewState: dict[str, str]
    excluded: bool


class CoverageFacts(TypedDict):
    """The persistent coverage evidence returned to the ledger writer."""

    coverage: list[CoverageRow]
    coverageRevision: str


class CoverageSummary(TypedDict):
    """The exact compact projection consumed by the decider."""

    revision: str
    gaps: list[str]
    warnings: list[str]
    rows: int
    checksNeeded: list[RevisionRef]


class _Origin(TypedDict):
    row: JsonObject
    by: str


STATUSES = (
    "Present and sufficient",
    "Present but incomplete",
    "Required and absent",
    "Not yet applicable",
    "Not assessed",
)
ACTIONS = ("create", "update", "unchanged", "remove", "not-applicable", "unresolved")


def _digest(value: JsonInput) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _rows(result: JsonObject) -> list[JsonObject]:
    value: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = result.get(
        "coverage",
        [],
    )
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _collect(survey: JsonObject, results: list[str]) -> tuple[dict[str, _Origin], list[JsonObject]]:
    row: JsonObject
    name: str
    rows: dict[str, _Origin] = {}
    checks: list[JsonObject] = []
    for row in _rows(survey):
        if row.get("id"):
            rows[check_type(row["id"], str)] = {"row": row, "by": "survey"}
    for name in results:
        result: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = read_artifact(
            Path(name),
            strict=False,
        )
        if not isinstance(result, dict):
            continue
        result = json_object(result)
        role: str = Path(name).stem.split("-", 3)[2]
        agent: str = Path(name).stem.split("-", 3)[3]
        if role in {"proposer", "diagram"}:
            for row in _rows(result):
                if row.get("id"):
                    rows[check_type(row["id"], str)] = {"row": row, "by": agent}
        else:
            review_checks: list[contracts.JsonObject] = check_type(
                result.get("coverageChecks", []),
                list[JsonObject],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
            checks.extend({**check, "by": agent} for check in review_checks)
    return rows, checks


def _normalize_paths(row: JsonObject, filled: list[str]) -> None:
    key_name: str | str
    for key_name in ("sources", "views"):
        values: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = row.get(
            key_name,
        )
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            row[key_name] = (
                [v for v in values or [] if isinstance(v, str) and v.strip()] if isinstance(values, list) else []
            )
            filled.append(key_name)


def _normalize(source: JsonObject, key: str, warnings: list[str]) -> JsonObject:
    key_name: str | str | str | str
    status: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None
    action: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None
    row: dict[str, int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None] = dict(source)
    filled: list[str] = []
    for key_name in ("subject", "scope", "obligation", "reason"):
        if not isinstance(row.get(key_name), str) or not check_type(row[key_name], str).strip():
            row[key_name] = row.get(key_name) if isinstance(row.get(key_name), str) else ""
            filled.append(key_name)
    if row.get("status") not in STATUSES:
        row["status"] = "Not assessed"
        filled.append("status")
    if row.get("action") not in ACTIONS:
        row["action"] = "unresolved"
        filled.append("action")
    _normalize_paths(row, filled)
    if row.get("disposition") not in {"required", "unrelated-debt"} or (
        row["disposition"] == "unrelated-debt" and not row.get("dispositionReason")
    ):
        row["disposition"] = "required"
        filled.append("disposition")
    if filled:
        warnings.append(f"coverage {key}: filled {', '.join(filled)}")
    status, action = row["status"], row["action"]
    if status == "Not yet applicable" and action != "not-applicable":
        row["action"] = "not-applicable"
    elif action == "not-applicable" and status != "Not yet applicable":
        row["action"] = "unchanged" if status == "Present and sufficient" else "unresolved"
    if row["action"] != action:
        warnings.append(
            f"coverage {key}: action {action} derived as {row['action']} from status {status}",
        )
    action = row["action"]
    return row


@dataclass
class _CoverageState:
    checks: list[JsonObject]
    warnings: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def render(self, key: str, item: _Origin) -> CoverageRow:
        evidence: list[JsonObject]
        evidence_warnings: list[str]
        status: contracts.JsonValue
        action: contracts.JsonValue
        if not (isinstance(key, str)):
            argument_error: str = "render: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        row: dict[str, contracts.JsonValue] = _normalize(item["row"], key, self.warnings)
        status, action = row["status"], row["action"]
        views: list[str] = check_type(
            row["views"],
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        refs: list[contracts.JsonObject] = check_type(
            row.get("evidenceRefs", []),
            list[JsonObject],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        evidence, evidence_warnings = evidence_state(refs)
        self.warnings.extend(f"coverage {key}: {e}" for e in evidence_warnings)
        content: dict[str, str] = view_bindings(views, refs)
        revision: str = _digest({"row": row, "files": content, "evidence": evidence})
        matching: list[dict[str, contracts.JsonValue]] = [
            c
            for c in self.checks
            if c.get("id") == key
            and c["by"] != item["by"]
            and isinstance(c.get("evidence"), str)
            and check_type(c["evidence"], str).strip()
        ]
        latest: dict[str, contracts.JsonValue] | None = matching[-1] if matching else None
        excluded: dict[str, contracts.JsonValue] | bool | None = (
            row["disposition"] == "unrelated-debt" and latest and latest.get("verdict") == "verified"
        )
        if not excluded and status not in {
            "Present and sufficient",
            "Not yet applicable",
        }:
            self.gaps.append(f"coverage {key}: assessment is not resolved ({status})")
        if not excluded and action == "unresolved":
            self.gaps.append(
                f"coverage {key}: applicability or required design remains unresolved",
            )
        if (
            not excluded
            and action in {"create", "update", "unchanged", "remove"}
            and (
                not content or any(v == "absent" or v.startswith(("invalid:", "unreadable:")) for v in content.values())
            )
        ):
            self.gaps.append(f"coverage {key}: required view missing or unreadable")
        if not latest or latest.get("verdict") != "verified":
            self.gaps.append(f"coverage {key}: no independent verified check")
        return check_type(
            {
                **row,
                "by": item["by"],
                "revision": revision,
                "review": latest,
                "evidenceState": evidence,
                "viewState": content,
                "excluded": bool(excluded),
            },
            CoverageRow,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def coverage_facts(survey: JsonObject, results: list[str]) -> tuple[CoverageFacts, CoverageSummary]:
    """Fold inventory and independent checks into typed ledger rows.

    Returns:
        Persistent coverage records and their compact decision summary.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    rows: dict[str, _Origin]
    checks: list[JsonObject]
    if not (isinstance(survey, dict)) or not (isinstance(results, list)):
        argument_error: str = "coverage_facts: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    rows, checks = _collect(survey, results)
    state: _CoverageState = _CoverageState(checks)
    if not rows:
        state.gaps.append("coverage: no subject/obligation inventory; assess even a no-change target")
    rendered: list[CoverageRow] = list(starmap(state.render, sorted(rows.items())))
    revision: str = _digest(
        [{"id": row["id"], "revision": row["revision"]} for row in rendered],
    )
    compact: CoverageSummary = {
        "revision": revision,
        "gaps": state.gaps,
        "warnings": state.warnings,
        "rows": len(rendered),
        "checksNeeded": [{"id": row["id"], "revision": row["revision"]} for row in rendered],
    }
    return {"coverage": rendered, "coverageRevision": revision}, compact
