"""Fold architecture coverage evidence into the existing round ledger.

Consumed by: archresume.resume_facts and architecture.js — block approval on missing,
unresolved or unreviewed coverage and bind saved decisions to current view content.
Project obligations and assessment vocabulary remain in the project's MODEL.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from archstate import snapshot_tree


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _files(paths: list[str]) -> dict[str, str]:
    result = {}
    for name in paths:
        path = Path(name)
        if not path.is_absolute():
            result[name] = "invalid: expected absolute path"
            continue
        try:
            content = path.read_bytes()
            # Promotion changes only review metadata, not the reviewed architecture.
            if content.startswith(b"---\n"):
                end = content.find(b"\n---", 4)
                if end >= 0:
                    content = (
                        re.sub(
                            rb"(?m)^lifecycle_state:.*$",
                            b"lifecycle_state: <review-state>",
                            content[:end],
                        )
                        + content[end:]
                    )
            result[name] = hashlib.sha256(content).hexdigest()
        except FileNotFoundError:
            result[name] = "absent"
        except OSError as exc:
            result[name] = f"unreadable: {exc}"
    return result


def _rows(result: dict) -> list[dict]:
    value = result.get("coverage", [])
    return (
        [row for row in value if isinstance(row, dict)]
        if isinstance(value, list)
        else []
    )


def coverage_facts(work: Path, survey: dict, results: list[str]) -> tuple[dict, dict]:
    """Return ledger rows and compact gating facts; omitted ids never disappear.

    Survey seeds inventory, writers replace explicitly named rows, and independent
    reviewers attest the generated revision, which includes current view bytes.
    """
    rows = {}
    checks = []
    for row in _rows(survey):
        if row.get("id"):
            rows[row["id"]] = {"row": row, "by": "survey"}
    for name in results:
        result = json.loads(Path(name).read_text(encoding="utf-8"))
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
        row = item["row"]
        required = (
            "id",
            "subject",
            "scope",
            "obligation",
            "status",
            "action",
            "reason",
        )
        invalid = [
            field
            for field in required
            if not isinstance(row.get(field), str) or not row[field].strip()
        ]
        sources = row.get("sources")
        views = row.get("views")
        if (
            not isinstance(sources, list)
            or not sources
            or any(not isinstance(s, str) or not s.strip() for s in sources)
        ):
            invalid.append("sources")
        if not isinstance(views, list) or any(
            not isinstance(v, str) or not v.strip() for v in views
        ):
            invalid.append("views")
            views = []
        content = _files(views)
        revision = _digest({"row": row, "files": content})
        matching = [
            c
            for c in checks
            if c.get("id") == key
            and c.get("revision") == revision
            and c["by"] != item["by"]
            and isinstance(c.get("evidence"), str)
            and c["evidence"].strip()
        ]
        latest = matching[-1] if matching else None
        action = row.get("action")
        status = row.get("status")
        if status not in ("Present and sufficient", "Not yet applicable"):
            gaps.append(f"coverage {key}: assessment is not resolved ({status})")
        if (status == "Not yet applicable") != (action == "not-applicable"):
            gaps.append(f"coverage {key}: assessment and action disagree")
        if invalid:
            gaps.append(f"coverage {key}: invalid {', '.join(invalid)}")
        if action not in ("create", "update", "unchanged", "remove", "not-applicable"):
            gaps.append(
                f"coverage {key}: applicability or required design remains unresolved"
            )
        if action in ("create", "update", "unchanged", "remove") and (
            not content
            or any(
                v == "absent" or v.startswith(("invalid:", "unreadable:"))
                for v in content.values()
            )
        ):
            gaps.append(f"coverage {key}: required view missing or unreadable")
        if action == "remove" and any(
            not Path(v).is_relative_to(work / "draft") for v in views
        ):
            gaps.append(
                f"coverage {key}: removal evidence must be retained in the draft/delta, not the deleted canonical view"
            )
        if not latest or latest.get("verdict") != "verified":
            gaps.append(
                f"coverage {key}: current revision {revision} lacks independent verified evidence"
            )
        rendered.append(
            {**row, "by": item["by"], "revision": revision, "review": latest}
        )
    revision = _digest(
        [{"id": row["id"], "revision": row["revision"]} for row in rendered]
    )
    compact = {
        "revision": revision,
        "gaps": gaps,
        "rows": len(rendered),
        "checksNeeded": [
            {"id": row["id"], "revision": row["revision"]} for row in rendered
        ],
    }
    return {"coverage": rendered, "coverageRevision": revision}, compact


def integration_revision(
    coverage_revision: str, update: dict | None, work: Path
) -> str:
    """Bind conformance to approved coverage and current integrated/deleted file bytes."""
    paths = []
    for field in ("changedFiles", "createdFiles", "deletedFiles"):
        paths.extend((update or {}).get(field, []))
    before_path = work / "integrate-before.json"
    if before_path.is_file():
        before = json.loads(before_path.read_text(encoding="utf-8"))
        root = before.get("root")
        if root:
            after = snapshot_tree(root)
            old_files = before.get("files", {})
            new_files = after.get("files", {})
            paths.extend(
                str(Path(root) / name)
                for name in old_files.keys() | new_files.keys()
                if old_files.get(name) != new_files.get(name)
            )
    return _digest({"coverage": coverage_revision, "files": _files(sorted(set(paths)))})
