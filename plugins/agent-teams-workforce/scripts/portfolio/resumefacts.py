"""The facts a resumed prd-to-spec run reads from an Epic's saved architecture and span ruling.

`depscore.py saved-target` and `depscore.py saved-span` run these, so the workflow receives
them through the checked relay (see relay.py) rather than from a session reading the files.
"""

from __future__ import annotations

import json
from pathlib import Path

from archbaseline import FreshnessOptions, survey_freshness
from archevidence import saved_evidence_current
from archrevision import record_problem
from contracts import JsonObject, JsonValue, json_object
from typeguard import CollectionCheckStrategy, check_type


def _count(report: JsonValue, key: str) -> int:
    """Count one saved report list, returning zero when it is absent.

    Args:
        report: The parsed report.
        key: The list's key.

    Returns:
        Its length.

    """
    value: JsonValue = report.get(key) if isinstance(report, dict) else None
    return len(value) if isinstance(value, list) else 0


def saved_target(art_dir: Path) -> JsonObject:
    """Read saved target facts without changing its files.

    Args:
        art_dir: The Epic's artifacts directory.

    Returns:
        `{found, ok, revisionProblem, subject, targetDir, deltaDir, deltaFiles,
        integratedFiles, closureSaved}`; `ok` only when the saved target was written, its
        evidence is current and arc42 is still the revision it was produced against;
        `closureSaved` when its delta holds the checked prerequisite closure.

    Raises:
        TypeError: The directory or persisted JSON has an invalid shape.

    """
    if not isinstance(art_dir, Path):
        message: str = "art_dir must be a Path"
        raise TypeError(message)

    work: Path = art_dir / "architecture"
    target: Path = work / "target.json"
    update: Path = work / "architecture-update.json"
    saved: JsonObject | None = json_object(json.loads(target.read_text(encoding="utf-8"))) if target.is_file() else None
    summary: JsonObject = json_object(saved.get("summary") or saved) if saved is not None else {}
    report: JsonObject = json_object(json.loads(update.read_text(encoding="utf-8"))) if update.is_file() else {}
    delta_files: JsonValue = saved.get("deltaFiles") if isinstance(saved, dict) else None
    seal_path: Path = work / "survey.json.baseline-inputs.json"
    seal: JsonObject = json_object(json.loads(seal_path.read_text(encoding="utf-8"))) if seal_path.is_file() else {}
    baseline_current: bool = (
        survey_freshness(work / "survey.json", FreshnessOptions(form=check_type(seal.get("form"), str | None)))[
            "current"
        ]
        if saved
        else False
    )
    revision_problem: str | None = record_problem(work) if saved else None
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
        else int(check_type(summary.get("deltaFiles") or 0, int | str)),
        "integratedFiles": _count(report, "changedFiles") + _count(report, "createdFiles"),
        "closureSaved": bool(summary.get("deltaDir"))
        and (Path(str(summary.get("deltaDir"))).parent / "closure.json").is_file(),
    }


def _text(v: JsonValue) -> str:
    """Render a saved identifier as text or serialized JSON.

    Args:
        v: The saved value.

    Returns:
        The string.

    """
    return v if isinstance(v, str) else json.dumps(v)


def saved_span(art_dir: Path) -> JsonObject:
    """Read the saved span ruling (`repo-scoping.json`) for resume.

    Args:
        art_dir: The Epic's artifacts directory.

    Returns:
        `{found, placements: [{repoPath, itemIds, frontend}], noCode: [{itemId, reason}], spanRationale}`.

    Raises:
        TypeError: The directory or persisted JSON has an invalid shape.

    """
    if not isinstance(art_dir, Path):
        message: str = "art_dir must be a Path"
        raise TypeError(message)

    path: Path = art_dir / "repo-scoping.json"
    if not path.is_file():
        return {"found": False, "placements": [], "noCode": [], "spanRationale": None}
    ruling: JsonObject = json_object(json.loads(path.read_text(encoding="utf-8")))
    placements: list[JsonObject] = check_type(
        ruling.get("placements") or [],
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    no_code: list[JsonObject] = check_type(
        ruling.get("noCode") or [],
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    return {
        "found": True,
        "placements": [
            {
                "repoPath": p.get("repoPath") or "",
                "itemIds": [
                    _text(x)
                    for x in check_type(
                        p.get("itemIds") or [],
                        list[JsonValue],
                        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                    )
                ],
                "frontend": p.get("frontend") is True,
            }
            for p in placements
        ],
        "noCode": [{"itemId": _text(n.get("itemId")), "reason": str(n.get("reason") or "")} for n in no_code],
        "spanRationale": ruling.get("spanRationale"),
    }
