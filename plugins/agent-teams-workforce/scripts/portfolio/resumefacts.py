"""The facts a resumed prd-to-spec run reads from an Epic's saved architecture and span ruling.

`depscore.py saved-target` and `depscore.py saved-span` run these, so the workflow receives
them through the checked relay (see relay.py) rather than from a session reading the files.
"""

from __future__ import annotations

import json
from pathlib import Path

from archevidence import saved_evidence_current
from archrevision import record_problem
from archbaseline import survey_freshness


def _count(report: object, key: str) -> int:
    """The length of one list in a saved report, 0 when the report or list is absent.

    Args:
        report: The parsed report.
        key: The list's key.

    Returns:
        Its length.
    """
    value = report.get(key) if isinstance(report, dict) else None
    return len(value) if isinstance(value, list) else 0


def saved_target(art_dir: Path) -> dict:
    """The saved target's facts a resume needs; the files themselves stay on disk.

    Args:
        art_dir: The Epic's artifacts directory.

    Returns:
        `{found, ok, revisionProblem, subject, targetDir, deltaDir, deltaFiles,
        integratedFiles, closureSaved}`; `ok` only when the saved target was written, its
        evidence is current and arc42 is still the revision it was produced against; `closureSaved` when its delta holds the checked prerequisite closure.
    """
    work = art_dir / "architecture"
    target = work / "target.json"
    update = work / "architecture-update.json"
    saved = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None
    summary = (saved.get("summary") or saved) if isinstance(saved, dict) else {}
    report = json.loads(update.read_text(encoding="utf-8")) if update.is_file() else {}
    delta_files = saved.get("deltaFiles") if isinstance(saved, dict) else None
    baseline_current = (
        survey_freshness(work / "survey.json")["current"] if saved else False
    )
    revision_problem = record_problem(work) if saved else None
    return {
        "found": saved is not None,
        "ok": summary.get("ok") is True
        and baseline_current
        and revision_problem is None
        and saved_evidence_current(str(work)),
        "revisionProblem": revision_problem or "",
        "subject": summary.get("subject"),
        "targetDir": summary.get("targetDir"),
        "deltaDir": summary.get("deltaDir"),
        "deltaFiles": len(delta_files)
        if isinstance(delta_files, list)
        else int(summary.get("deltaFiles") or 0),
        "integratedFiles": _count(report, "changedFiles")
        + _count(report, "createdFiles"),
        "closureSaved": bool(summary.get("deltaDir"))
        and any(
            (folder / "closure.json").is_file()
            for folder in (
                Path(str(summary.get("deltaDir"))).parent,
                Path(str(summary.get("deltaDir"))),
            )
        ),
    }


def _text(v: object) -> str:
    """A saved id as a string: a string as it is, anything else as its JSON.

    Args:
        v: The saved value.

    Returns:
        The string.
    """
    return v if isinstance(v, str) else json.dumps(v)


def saved_span(art_dir: Path) -> dict:
    """The saved span ruling (`repo-scoping.json`) a resumed run replays.

    Args:
        art_dir: The Epic's artifacts directory.

    Returns:
        `{found, placements: [{repoPath, itemIds, frontend}], noCode: [{itemId, reason}], spanRationale}`.
    """
    path = art_dir / "repo-scoping.json"
    if not path.is_file():
        return {"found": False, "placements": [], "noCode": [], "spanRationale": None}
    ruling = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(ruling, dict):
        ruling = {}
    return {
        "found": True,
        "placements": [
            {
                "repoPath": p.get("repoPath") or "",
                "itemIds": [_text(x) for x in p.get("itemIds") or []],
                "frontend": p.get("frontend") is True,
            }
            for p in ruling.get("placements") or []
            if isinstance(p, dict)
        ],
        "noCode": [
            {"itemId": _text(n.get("itemId")), "reason": str(n.get("reason") or "")}
            for n in ruling.get("noCode") or []
            if isinstance(n, dict)
        ],
        "spanRationale": ruling.get("spanRationale"),
    }
