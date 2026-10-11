"""The facts a resumed prd-to-spec run reads from an Epic's saved architecture and span ruling.

`depscore.py saved-target` and `depscore.py saved-span` run these, so the workflow receives
them through the checked relay (see relay.py) rather than from a session reading the files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from archbaseline import FreshnessOptions, survey_freshness
from archevidence import saved_evidence_current
from archrevision import record_problem
from contracts import JsonObject, JsonValue, SealForm, SurveySeal, json_object, read_survey_seal, survey_seal_path
from typeguard import CollectionCheckStrategy, check_type

# The survey and target report contracts are generated into the artifact-handoff skill, their one definitions.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))

# isort: split
from survey_contract import SURVEY_FILE
from target_contract import (
    CLOSURE_FILE,
    KEY_DELTA_DIR,
    KEY_DELTA_FILES,
    KEY_OK,
    KEY_SUBJECT,
    KEY_TARGET_DIR,
    TargetResult,
    TargetSummary,
    load_target_report,
    target_report_path,
)


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

    A saved target report that breaks its schema raises target_contract.TargetContractError, and
    a target report or survey seal that exists but cannot be read raises OSError; neither is
    downgraded to an unsaved target.

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

    target: Path = target_report_path(art_dir)
    work: Path = target.parent
    update: Path = work / "architecture-update.json"
    saved: TargetResult | None = load_target_report(target) if target.is_file() else None
    report: JsonObject = json_object(json.loads(update.read_text(encoding="utf-8"))) if update.is_file() else {}
    baseline_current: bool = False
    if saved is not None:
        survey: Path = work / SURVEY_FILE
        seal_warnings: list[str] = []
        seal: SurveySeal | None = read_survey_seal(survey_seal_path(survey), seal_warnings)
        form: SealForm | None = seal.get("form") if seal is not None else None
        baseline_current = survey_freshness(survey, FreshnessOptions(form=form))["current"]
    revision_problem: str | None = record_problem(work) if saved is not None else None
    summary: TargetSummary | None = saved["summary"] if saved is not None else None
    delta_dir: str | None = summary.get(KEY_DELTA_DIR) if summary is not None else None
    delta_files: list[str] | None = saved.get(KEY_DELTA_FILES) if saved is not None else None
    return {
        "found": saved is not None,
        "ok": summary is not None
        and summary[KEY_OK]
        and baseline_current
        and revision_problem is None
        and saved_evidence_current(str(work)),
        "revisionProblem": revision_problem or "",
        "subject": summary.get(KEY_SUBJECT) if summary is not None else None,
        "targetDir": summary.get(KEY_TARGET_DIR) if summary is not None else None,
        "deltaDir": delta_dir,
        "deltaFiles": len(delta_files)
        if delta_files is not None
        else (summary.get(KEY_DELTA_FILES, 0) if summary is not None else 0),
        "integratedFiles": _count(report, "changedFiles") + _count(report, "createdFiles"),
        "closureSaved": bool(delta_dir) and (Path(str(delta_dir)).parent / CLOSURE_FILE).is_file(),
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
