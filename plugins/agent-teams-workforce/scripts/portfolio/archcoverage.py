"""Fold architecture coverage evidence into the existing round ledger.

Consumed by: archresume.resume_facts and architecture.js — report missing, unresolved
or unreviewed coverage to the coordinator and the decider; arch-review-check reads the
approved rows from the arch-resume relay file.
Project obligations and assessment vocabulary remain in the project's MODEL.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from archevidence import evidence_state, view_bindings
from jsonartifact import read_artifact

STATUSES = (
    "Present and sufficient",
    "Present but incomplete",
    "Required and absent",
    "Not yet applicable",
    "Not assessed",
)
ACTIONS = ("create", "update", "unchanged", "remove", "not-applicable", "unresolved")


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _rows(result: dict) -> list[dict]:
    value = result.get("coverage", [])
    return (
        [row for row in value if isinstance(row, dict)]
        if isinstance(value, list)
        else []
    )


def coverage_facts(survey: dict, results: list[str]) -> tuple[dict, dict]:
    """Return ledger rows and compact facts for the decider; omitted ids never disappear.

    Survey seeds inventory, writers replace explicitly named rows, and independent
    reviewers check rows by id. `gaps` name what the decider and the conformance reviewer
    should know (unresolved status, missing views, rows without a verified check); they
    gate nothing. A field a row omits is filled and named in `warnings`, and an action its
    status contradicts is derived from the status.
    """
    rows = {}
    checks = []
    warnings: list[str] = []
    for row in _rows(survey):
        if row.get("id"):
            rows[row["id"]] = {"row": row, "by": "survey"}
    for name in results:
        result = read_artifact(Path(name), strict=False)
        if not isinstance(result, dict):
            continue
        role = Path(name).stem.split("-", 3)[2]
        agent = Path(name).stem.split("-", 3)[3]
        if role in ("proposer", "diagram"):
            for row in _rows(result):
                if row.get("id"):
                    rows[row["id"]] = {"row": row, "by": agent}
        else:
            for check in result.get("coverageChecks", []):
                if isinstance(check, dict):
                    checks.append({**check, "by": agent})
    gaps = []
    if not rows:
        gaps.append(
            "coverage: no subject/obligation inventory; assess even a no-change target"
        )
    rendered = []
    for key, item in sorted(rows.items()):
        row = dict(item["row"])
        filled = []
        for field in ("subject", "scope", "obligation", "reason"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                row[field] = row.get(field) if isinstance(row.get(field), str) else ""
                filled.append(field)
        if row.get("status") not in STATUSES:
            row["status"] = "Not assessed"
            filled.append("status")
        if row.get("action") not in ACTIONS:
            row["action"] = "unresolved"
            filled.append("action")
        for field in ("sources", "views"):
            values = row.get(field)
            if not isinstance(values, list) or any(
                not isinstance(v, str) or not v.strip() for v in values
            ):
                row[field] = (
                    [v for v in values or [] if isinstance(v, str) and v.strip()]
                    if isinstance(values, list)
                    else []
                )
                filled.append(field)
        if row.get("disposition") not in ("required", "unrelated-debt") or (
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
            row["action"] = (
                "unchanged" if status == "Present and sufficient" else "unresolved"
            )
        if row["action"] != action:
            warnings.append(
                f"coverage {key}: action {action} derived as {row['action']} from status {status}"
            )
        action = row["action"]
        views = row["views"]
        refs = row.get("evidenceRefs", [])
        evidence, evidence_warnings = evidence_state(refs)
        warnings.extend(f"coverage {key}: {e}" for e in evidence_warnings)
        content = view_bindings(views, refs)
        revision = _digest({"row": row, "files": content, "evidence": evidence})
        matching = [
            c
            for c in checks
            if c.get("id") == key
            and c["by"] != item["by"]
            and isinstance(c.get("evidence"), str)
            and c["evidence"].strip()
        ]
        latest = matching[-1] if matching else None
        excluded = (
            row["disposition"] == "unrelated-debt"
            and latest
            and latest.get("verdict") == "verified"
        )
        if not excluded and status not in (
            "Present and sufficient",
            "Not yet applicable",
        ):
            gaps.append(f"coverage {key}: assessment is not resolved ({status})")
        if not excluded and action == "unresolved":
            gaps.append(
                f"coverage {key}: applicability or required design remains unresolved"
            )
        if (
            not excluded
            and action in ("create", "update", "unchanged", "remove")
            and (
                not content
                or any(
                    v == "absent" or v.startswith(("invalid:", "unreadable:"))
                    for v in content.values()
                )
            )
        ):
            gaps.append(f"coverage {key}: required view missing or unreadable")
        if not latest or latest.get("verdict") != "verified":
            gaps.append(f"coverage {key}: no independent verified check")
        rendered.append(
            {
                **row,
                "by": item["by"],
                "revision": revision,
                "review": latest,
                "evidenceState": evidence,
                "viewState": content,
                "excluded": bool(excluded),
            }
        )
    revision = _digest(
        [{"id": row["id"], "revision": row["revision"]} for row in rendered]
    )
    compact = {
        "revision": revision,
        "gaps": gaps,
        "warnings": warnings,
        "rows": len(rendered),
        "checksNeeded": [
            {"id": row["id"], "revision": row["revision"]} for row in rendered
        ],
    }
    return {"coverage": rendered, "coverageRevision": revision}, compact
