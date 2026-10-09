"""The file sets of an architecture integration, measured and kept on disk, never relayed.

`depscore.py arch-integration-files` measures what an integration wrote since the fingerprint
saved before it, unions that with what the architecture-maintainer reported, and writes the
lists to a files file; `depscore.py arch-review-check` checks a saved conformance review against
those lists and the approved coverage rows. Their relay views carry counts only (relay.py), and
`arch-approve --arch-files-from` and `arch-commit --files-from` read the lists from the files
file, so no file list passes through a model on its way between commands.
"""

from __future__ import annotations

import json
from pathlib import Path

from archstate import snapshot_tree, tree_diff
from jsonartifact import read_artifact

EFFECTIVE = "arc42"
CONSTRAINTS = "arc42/02-architecture-constraints"


def _load(path: Path) -> object:
    """Parse a JSON file.

    Args:
        path: The file.

    Returns:
        The parsed value, or None when the file is absent.
    """
    return read_artifact(path, strict=False) if path.is_file() else None


def _paths(value: object) -> list[str]:
    """The non-empty strings of a list, stripped.

    Args:
        value: A JSON value.

    Returns:
        The strings.
    """
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def _union(*lists: list[str]) -> list[str]:
    """The sorted union of lists of paths.

    Args:
        *lists: The lists.

    Returns:
        The union.
    """
    return sorted({p for lst in lists for p in lst})


def integration_files(
    arch_root: str,
    *,
    before: Path,
    report: Path,
    files_out: Path,
    last: Path | None,
    save_last: Path | None,
    accumulate: bool,
) -> dict:
    """Measure and record the files an integration changed, created and deleted.

    Args:
        arch_root: The architecture directory (holding `arc42/`, `target/`, `built/`).
        before: The fingerprint saved before the integration.
        report: The architecture-maintainer's saved report.
        files_out: The files file to write the lists to.
        last: A fingerprint saved at the previous measurement, to name the files changed since.
        save_last: Where to save this measurement's fingerprint.
        accumulate: Union the reported lists with those already in `files_out`.

    Returns:
        The lists and their counts, or `{error}`.
    """
    now = snapshot_tree(arch_root)
    if "error" in now:
        return {"error": now["error"]}
    root = str(arch_root).rstrip("/")
    was = _load(before)
    if not isinstance(was, dict):
        return {"error": f"{before}: no saved fingerprint"}

    def absolute(rels: list[str]) -> list[str]:
        return [f"{root}/{r}" for r in rels]

    diff = tree_diff(was, now)
    since_last: list[str] = []
    if last is not None:
        prev = _load(last)
        if isinstance(prev, dict):
            d = tree_diff(prev, now)
            since_last = absolute(d["created"] + d["changed"] + d["deleted"])
    if save_last is not None:
        save_last.parent.mkdir(parents=True, exist_ok=True)
        save_last.write_text(json.dumps(now), encoding="utf-8")
    u = _load(report)
    u = u if isinstance(u, dict) else {}
    kept = _load(files_out) if accumulate else None
    kept = kept if isinstance(kept, dict) else {}
    reported_touched = _union(
        _paths(u.get("changedFiles")),
        _paths(u.get("createdFiles")),
        _paths(kept.get("reportedTouched")),
    )
    reported_deleted = _union(
        _paths(u.get("deletedFiles")), _paths(kept.get("reportedDeleted"))
    )
    measured = absolute(diff["created"] + diff["changed"])
    measured_deleted = absolute(diff["deleted"])
    touched = _union(reported_touched, measured)
    deleted = _union(reported_deleted, measured_deleted)
    everything = _union(touched, deleted)
    reported = set(reported_touched) | set(reported_deleted)
    section2 = [
        p
        for p in everything
        if p == f"{root}/{CONSTRAINTS}" or p.startswith(f"{root}/{CONSTRAINTS}/")
    ]
    outside = [p for p in everything if not p.startswith(f"{root}/{EFFECTIVE}/")]
    result = {
        "touched": touched,
        "deleted": deleted,
        "all": everything,
        "unreported": [
            p for p in _union(measured, measured_deleted) if p not in reported
        ],
        "section2": section2,
        "outside": outside,
        "changedSinceLast": since_last,
        "reportedTouched": reported_touched,
        "reportedDeleted": reported_deleted,
        "constraintIssues": len(u.get("constraintIssues") or [])
        if isinstance(u.get("constraintIssues"), list)
        else 0,
        "contradictions": len(u.get("contradictions") or [])
        if isinstance(u.get("contradictions"), list)
        else 0,
        "filesOut": str(files_out),
    }
    files_out.parent.mkdir(parents=True, exist_ok=True)
    files_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def review_check(review: Path, *, files: Path, coverage_from: Path) -> dict:
    """Check a saved conformance review against the integration's files and approved coverage.

    Args:
        review: The saved review (`conformance-N.json`).
        files: The files file `integration_files` wrote.
        coverage_from: The relay file of the `arch-resume` run that read the approved
            coverage: its `result.coverage.checksNeeded` rows are the rows every one of
            which needs a verified check, matched by row id.

    Returns:
        `missed` (touched files not reviewed), `coverageUnverified` (row ids without a verified
        check with evidence), the review's verdict and its findings count; or `{error}`.
    """
    r = _load(review)
    f = _load(files)
    if not isinstance(r, dict):
        return {"error": f"{review}: no saved review"}
    if not isinstance(f, dict):
        return {"error": f"{files}: no saved integration files"}
    saved = _load(coverage_from)
    result = saved.get("result") if isinstance(saved, dict) else None
    cov = result.get("coverage") if isinstance(result, dict) else None
    if not isinstance(cov, dict) or not isinstance(cov.get("checksNeeded"), list):
        return {"error": f"{coverage_from}: no arch-resume coverage rows"}
    needed = {
        str(row.get("id")): str(row.get("revision") or "")
        for row in cov["checksNeeded"]
        if isinstance(row, dict) and row.get("id")
    }
    reviewed = set(_paths(r.get("reviewedFiles")))
    checks = [c for c in r.get("coverageChecks") or [] if isinstance(c, dict)]

    def verified(cid: str) -> dict | None:
        """The verified check with evidence for one row id, if any."""
        return next(
            (
                c
                for c in checks
                if c.get("id") == cid
                and c.get("verdict") == "verified"
                and isinstance(c.get("evidence"), str)
                and c.get("evidence").strip()
            ),
            None,
        )

    unverified = sorted(cid for cid in needed if verified(cid) is None)
    findings = r.get("findings")
    return {
        "missed": [p for p in _paths(f.get("touched")) if p not in reviewed],
        "coverageUnverified": unverified,
        "conforms": r.get("conforms") is True,
        "findings": len(findings) if isinstance(findings, list) else 0,
        "review": str(review),
    }


def files_from(path: Path, key: str) -> list[str]:
    """One list from a saved JSON file, as a command's file argument.

    Args:
        path: The JSON file.
        key: The list's key.

    Returns:
        The list; empty when the file holds no such list.
    """
    value = _load(path)
    if not isinstance(value, dict) or not isinstance(value.get(key), list):
        return []
    return _paths(value[key])
