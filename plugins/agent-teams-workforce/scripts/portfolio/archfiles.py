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
from dataclasses import dataclass
from pathlib import Path

import contracts
from archstate import snapshot_tree, tree_diff
from contracts import FileError, IntegrationFiles, IntegrationReview, JsonObject, json_object
from jsonartifact import read_artifact
from typeguard import CollectionCheckStrategy, check_type, typechecked

EFFECTIVE = "arc42"
CONSTRAINTS = "arc42/02-architecture-constraints"


def _load(path: Path) -> contracts.JsonValue:
    """Parse a JSON file.

    Args:
        path: The file.

    Returns:
        The parsed value, or None when the file is absent.

    """
    return read_artifact(path, strict=False) if path.is_file() else None


def _paths(value: contracts.JsonValue) -> list[str]:
    """Return the non-empty strings of a list, stripped.

    Args:
        value: A JSON value.

    Returns:
        The strings.

    """
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def _list_count(value: contracts.JsonValue) -> int:
    """Count entries only when an optional report field is a list.

    Returns:
        The list length, otherwise zero.

    """
    return len(value) if isinstance(value, list) else 0


def _union(*lists: list[str]) -> list[str]:
    """Return the sorted union of lists of paths.

    Args:
        *lists: The lists.

    Returns:
        The union.

    """
    return sorted({p for lst in lists for p in lst})


@dataclass(frozen=True)
class IntegrationOptions:
    """Validated paths and accumulation policy for one measurement."""

    before: Path
    report: Path
    files_out: Path
    last: Path | None
    save_last: Path | None
    accumulate: bool

    def __post_init__(self) -> None:
        """Reject invalid measurement configuration.

        Raises:
            TypeError: A path or policy has an invalid type.

        """
        if any(not isinstance(path, Path) for path in (self.before, self.report, self.files_out)):
            message: str = "Integration measurement requires Path inputs"
            raise TypeError(message)
        if any(path is not None and not isinstance(path, Path) for path in (self.last, self.save_last)):
            message = "Optional integration snapshots must be Paths or None"
            raise TypeError(message)
        if not isinstance(self.accumulate, bool):
            message = "Integration accumulation policy must be boolean"
            raise TypeError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def integration_files(arch_root: str, options: IntegrationOptions) -> IntegrationFiles | FileError:
    """Measure and record the files an integration changed, created and deleted.

    Args:
        arch_root: The architecture directory (holding `arc42/`, `target/`, `built/`).
        options: Validated measurement paths and accumulation policy.

    Returns:
        The lists and their counts, or `{error}`.

    Raises:
        TypeError: The root or options have an invalid type.

    """
    was: contracts.JsonValue
    prev: contracts.JsonValue
    if not isinstance(arch_root, str) or not isinstance(options, IntegrationOptions):
        message: str = "Integration measurement requires an architecture root and validated options"
        raise TypeError(message)
    now: contracts.TreeSnapshot | contracts.FileError = snapshot_tree(arch_root)
    if "error" in now:
        return {"error": check_type(json_object(now)["error"], str)}
    root: str = str(arch_root).rstrip("/")
    was = _load(options.before)
    if not isinstance(was, dict):
        return {"error": f"{options.before}: no saved fingerprint"}

    def absolute(rels: list[str]) -> list[str]:
        if not (isinstance(rels, list)):
            argument_error: str = "absolute: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        return [f"{root}/{r}" for r in rels]

    diff: contracts.TreeDifference = tree_diff(json_object(was), json_object(now))
    since_last: list[str] = []
    if options.last is not None:
        prev = _load(options.last)
        if isinstance(prev, dict):
            d: contracts.TreeDifference = tree_diff(json_object(prev), json_object(now))
            since_last = absolute(d["created"] + d["changed"] + d["deleted"])
    if options.save_last is not None:
        options.save_last.parent.mkdir(parents=True, exist_ok=True)
        options.save_last.write_text(json.dumps(now), encoding="utf-8")
    return _report_files(root, options, diff, since_last)


def _report_files(
    root: str,
    options: IntegrationOptions,
    diff: contracts.TreeDifference,
    since_last: list[str],
) -> IntegrationFiles:
    """Combine measured changes and the maintainer report.

    Returns:
        The saved file record.

    """
    u: contracts.JsonValue
    kept: contracts.JsonValue
    u = _load(options.report)
    u = u if isinstance(u, dict) else {}
    kept = _load(options.files_out) if options.accumulate else None
    kept = kept if isinstance(kept, dict) else {}
    reported_touched: list[str] = _union(
        _paths(u.get("changedFiles")),
        _paths(u.get("createdFiles")),
        _paths(kept.get("reportedTouched")),
    )
    reported_deleted: list[str] = _union(
        _paths(u.get("deletedFiles")),
        _paths(kept.get("reportedDeleted")),
    )
    measured: list[str] = [f"{root}/{path}" for path in diff["created"] + diff["changed"]]
    measured_deleted: list[str] = [f"{root}/{path}" for path in diff["deleted"]]
    touched: list[str] = _union(reported_touched, measured)
    deleted: list[str] = _union(reported_deleted, measured_deleted)
    everything: list[str] = _union(touched, deleted)
    reported: set[str] = set(reported_touched) | set(reported_deleted)
    section2: list[str] = [
        p for p in everything if p == f"{root}/{CONSTRAINTS}" or p.startswith(f"{root}/{CONSTRAINTS}/")
    ]
    outside: list[str] = [p for p in everything if not p.startswith(f"{root}/{EFFECTIVE}/")]
    result: IntegrationFiles = {
        "touched": touched,
        "deleted": deleted,
        "all": everything,
        "unreported": [p for p in _union(measured, measured_deleted) if p not in reported],
        "section2": section2,
        "outside": outside,
        "changedSinceLast": since_last,
        "reportedTouched": reported_touched,
        "reportedDeleted": reported_deleted,
        "constraintIssues": _list_count(u.get("constraintIssues")),
        "contradictions": _list_count(u.get("contradictions")),
        "filesOut": str(options.files_out),
    }
    options.files_out.parent.mkdir(parents=True, exist_ok=True)
    options.files_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def review_check(review: Path, *, files: Path, coverage_from: Path) -> IntegrationReview | FileError:
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    r: contracts.JsonValue
    f: contracts.JsonValue
    saved: contracts.JsonValue
    result: contracts.JsonValue
    cov: contracts.JsonValue
    findings: contracts.JsonValue
    if not (isinstance(review, Path)) or not (isinstance(files, Path)) or not (isinstance(coverage_from, Path)):
        argument_error: str = "review_check: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
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
    rows: contracts.JsonValue = cov["checksNeeded"]
    if not isinstance(rows, list):
        return {"error": f"{coverage_from}: no arch-resume coverage rows"}
    needed: dict[str, str] = {
        str(row.get("id")): str(row.get("revision") or "") for row in rows if isinstance(row, dict) and row.get("id")
    }
    reviewed: set[str] = set(_paths(r.get("reviewedFiles")))
    saved_checks: contracts.JsonValue = r.get("coverageChecks")
    checks: list[JsonObject] = (
        [c for c in saved_checks if isinstance(c, dict)] if isinstance(saved_checks, list) else []
    )

    def verified(cid: str) -> JsonObject | None:
        """Find the verified check with evidence for one row id.

        Returns:
            The matching check, or None.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(cid, str)):
            argument_error: str = "verified: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        return next(
            (
                json_object(c)
                for c in checks
                if c.get("id") == cid
                and c.get("verdict") == "verified"
                and isinstance(evidence := c.get("evidence"), str)
                and evidence.strip()
            ),
            None,
        )

    unverified: list[str] = sorted(cid for cid in needed if verified(cid) is None)
    findings = r.get("findings")
    return {
        "missed": [p for p in _paths(f.get("touched")) if p not in reviewed],
        "coverageUnverified": unverified,
        "conforms": r.get("conforms") is True,
        "findings": len(findings) if isinstance(findings, list) else 0,
        "review": str(review),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def files_from(path: Path, key: str) -> list[str]:
    """One list from a saved JSON file, as a command's file argument.

    Args:
        path: The JSON file.
        key: The list's key.

    Returns:
        The list; empty when the file holds no such list.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    value: contracts.JsonValue
    if not (isinstance(path, Path)) or not (isinstance(key, str)):
        argument_error: str = "files_from: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    value = _load(path)
    if not isinstance(value, dict) or not isinstance(value.get(key), list):
        return []
    return _paths(value[key])
