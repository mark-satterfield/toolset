"""The arc42 revision the architecture step's saved work was produced against.

The revision is one sha256 over every file of the effective version (`<arch root>/arc42/`):
each file's path relative to that folder and the sha256 of its bytes, in path order, skipping
any path with a part that starts with a dot. It is the content the step read, whatever git
holds, so uncommitted files elsewhere in the vault do not move it and an uncommitted edit in
arc42 does. The Epic's artifact recorder hashes a directory input the same way.

`arc42-revision.json` in the step's working directory records it:
`{archRoot, revision, integrating, recordedAt}`. Saved work is current while the effective
version still hashes to `revision`, or while `integrating` is true (the step's own integration
is writing arc42 and resumes from its saved fingerprint). When the integration is approved, the
step records the integrated version as the new `revision`. Saved work with no record, or with a
revision the effective version no longer matches, was made against another arc42: `check` moves
it into `<artifacts dir>/stale-<timestamp>/architecture/` and the step starts again from the
survey.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

EFFECTIVE_FOLDER = "arc42"
RECORD_NAME = "arc42-revision.json"
ARCHITECTURE_DIR = "architecture"
KEPT = frozenset({RECORD_NAME, "relay"})


def arc42_revision(arch_root: str | Path) -> str | None:
    """Hash the effective version of the architecture.

    Args:
        arch_root: The architecture directory holding `arc42/`.

    Returns:
        The sha256 over every file of `arc42/`, or None when that folder does not exist.
    """
    folder = Path(arch_root).expanduser().resolve() / EFFECTIVE_FOLDER
    if not folder.is_dir():
        return None
    files = sorted(
        p
        for p in folder.rglob("*")
        if p.is_file()
        and not any(part.startswith(".") for part in p.relative_to(folder).parts)
    )
    whole = hashlib.sha256()
    for path in files:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        whole.update(f"{path.relative_to(folder).as_posix()}\0{sha}\n".encode())
    return whole.hexdigest()


def _now() -> str:
    """The current UTC time, to the second.

    Returns:
        The ISO 8601 timestamp.
    """
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_record(work_dir: str | Path) -> dict | None:
    """Read the step's revision record.

    Args:
        work_dir: The architecture step's working directory.

    Returns:
        The record, or None when it is missing or unreadable.
    """
    path = Path(work_dir) / RECORD_NAME
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_record(work_dir: Path, record: dict) -> None:
    """Write the step's revision record atomically.

    Args:
        work_dir: The architecture step's working directory.
        record: The record to write.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    tmp = work_dir / f".{RECORD_NAME}.tmp"
    tmp.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(work_dir / RECORD_NAME)


def record_problem(
    work_dir: str | Path, arch_root: str | Path | None = None
) -> str | None:
    """Say why saved work is not bound to the current arc42, or None when it is.

    Args:
        work_dir: The architecture step's working directory.
        arch_root: The architecture directory; the record's own `archRoot` when omitted.

    Returns:
        The reason, or None when the effective version still hashes to the recorded revision
        or the step's own integration is in progress.
    """
    record = read_record(work_dir)
    if record is None or not str(record.get("revision") or "").strip():
        return "no arc42 revision was recorded for this saved work (saved before revisions were recorded)"
    if record.get("integrating") is True:
        return None
    root = arch_root or record.get("archRoot")
    if not root:
        return "the revision record names no architecture directory"
    current = arc42_revision(root)
    if current is None:
        return f"the effective version {Path(root) / EFFECTIVE_FOLDER} does not exist"
    if current != record["revision"]:
        return f"arc42 changed since this work was produced (revision {record['revision'][:12]}, now {current[:12]})"
    return None


def _saved_items(work: Path) -> list[Path]:
    """List the saved work a stale revision sets aside.

    Args:
        work: The architecture step's working directory.

    Returns:
        Every entry of the working directory except the revision record and the relay logs.
    """
    if not work.is_dir():
        return []
    return sorted(
        p
        for p in work.iterdir()
        if p.name not in KEPT and not p.name.startswith(f".{RECORD_NAME}")
    )


def check(
    arch_root: str | Path, work_dir: str | Path, stale_root: str | Path | None = None
) -> dict:
    """Bind the step's saved work to the current arc42, setting it aside when it is bound to another.

    With no saved work, the current revision is recorded. With saved work whose record is
    missing or names another revision (and no integration of this step in progress), every
    saved file and folder but the relay logs moves to `<stale_root>/stale-<timestamp>/architecture/`
    and the current revision is recorded, so the step redoes its work from the survey.

    Args:
        arch_root: The architecture directory holding `arc42/`.
        work_dir: The architecture step's working directory.
        stale_root: Where the dated stale folder is made; the working directory's parent when
            omitted.

    Returns:
        `{ok, status, revision, reason, movedTo, moved}`: `status` is `new`, `current`,
        `integrating` or `stale`; `moved` counts the entries set aside.
    """
    work = Path(work_dir).expanduser().resolve()
    root = Path(arch_root).expanduser().resolve()
    current = arc42_revision(root)
    if current is None:
        why = f"the effective version {root / EFFECTIVE_FOLDER} does not exist"
        return {"ok": False, "error": why, "summary": {"ok": False, "error": why}}
    saved = _saved_items(work)
    record = read_record(work)
    out: dict = {
        "ok": True,
        "revision": current,
        "movedTo": None,
        "moved": 0,
        "reason": "",
    }
    if not saved:
        _write_record(
            work,
            {
                "archRoot": str(root),
                "revision": current,
                "integrating": False,
                "recordedAt": _now(),
            },
        )
        out["status"] = "new"
    elif record is not None and record.get("integrating") is True:
        out["status"] = "integrating"
    else:
        problem = record_problem(work, root)
        if problem is None:
            out["status"] = "current"
        else:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            parent = (
                Path(stale_root).expanduser().resolve() if stale_root else work.parent
            )
            dest = parent / f"stale-{stamp}" / ARCHITECTURE_DIR
            dest.mkdir(parents=True, exist_ok=True)
            for item in saved:
                item.rename(dest / item.name)
            old = work / RECORD_NAME
            if old.is_file():
                old.rename(dest / RECORD_NAME)
            _write_record(
                work,
                {
                    "archRoot": str(root),
                    "revision": current,
                    "integrating": False,
                    "recordedAt": _now(),
                },
            )
            out.update(
                status="stale", reason=problem, movedTo=str(dest), moved=len(saved)
            )
    out["summary"] = {
        k: out[k] for k in ("ok", "status", "revision", "reason", "movedTo", "moved")
    }
    return out


def mark(arch_root: str | Path, work_dir: str | Path, state: str) -> dict:
    """Record the step's own integration: begun (`integrating`) or approved (`integrated`).

    `integrating` keeps the recorded revision and marks arc42 as being written by this step;
    `integrated` records the effective version as it now is, the revision the saved work now
    stands on.

    Args:
        arch_root: The architecture directory holding `arc42/`.
        work_dir: The architecture step's working directory.
        state: `integrating` or `integrated`.

    Returns:
        `{ok, state, revision}`, or `{ok: false, error}`.
    """
    work = Path(work_dir).expanduser().resolve()
    root = Path(arch_root).expanduser().resolve()
    record = read_record(work)
    if record is None:
        why = f"no {RECORD_NAME} in {work}: the step records its revision before it designs"
        return {"ok": False, "error": why, "summary": {"ok": False, "error": why}}
    if state == "integrating":
        record["integrating"] = True
    elif state == "integrated":
        current = arc42_revision(root)
        if current is None:
            why = f"the effective version {root / EFFECTIVE_FOLDER} does not exist"
            return {"ok": False, "error": why, "summary": {"ok": False, "error": why}}
        record.update(revision=current, integrating=False)
    else:
        why = f"unknown state {state!r}: integrating or integrated"
        return {"ok": False, "error": why, "summary": {"ok": False, "error": why}}
    record["recordedAt"] = _now()
    _write_record(work, record)
    out = {"ok": True, "state": state, "revision": record["revision"]}
    return out | {"summary": dict(out)}
