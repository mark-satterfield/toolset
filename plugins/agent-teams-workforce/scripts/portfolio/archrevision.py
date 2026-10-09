"""The arc42 views the architecture step's saved work was produced against.

The effective version (`<arch root>/arc42/`) is fingerprinted file by file: each file's path
relative to that folder and the sha256 of its bytes, skipping any path with a part that
starts with a dot. `revision` is one sha256 over those pairs in path order, the hash the
Epic's artifact recorder computes for a directory input.

`arc42-revision.json` in the step's working directory records them:
`{archRoot, revision, files, views, integrating, recordedAt}`. `files` holds every file's
hash; `views` holds the hashes of the arc42 files the saved work read or wrote: those its
survey, ledger and decision name by absolute path, and those its draft holds a copy of.
Saved work is stale only when one of those views changed since it was recorded, so another
Epic integrating its own views into arc42 leaves this Epic's work in place. While
`integrating` is true the step's own integration is writing arc42 and the work is current.
Saved work found current is recorded again against the arc42 as it now is. Stale work is
moved into `<artifacts dir>/stale-<timestamp>/architecture/` and the step starts again from
the survey.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

EFFECTIVE_FOLDER = "arc42"
RECORD_NAME = "arc42-revision.json"
ARCHITECTURE_DIR = "architecture"
KEPT = frozenset({RECORD_NAME, "relay"})
#: The saved files whose text names the views the work read.
READ_RECORDS = ("survey.json", "ledger.json", "decision.json")
DRAFT_DIR = "draft"
PATH_END = re.compile(r"[\s\"'`#)\]>|,;]")


def arc42_files(arch_root: str | Path) -> dict[str, str] | None:
    """Hash every file of the effective version.

    Args:
        arch_root: The architecture directory holding `arc42/`.

    Returns:
        Each file's path relative to `arc42/` and the sha256 of its bytes, or None when that
        folder does not exist.
    """
    folder = Path(arch_root).expanduser().resolve() / EFFECTIVE_FOLDER
    if not folder.is_dir():
        return None
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
        and not any(part.startswith(".") for part in p.relative_to(folder).parts)
    }


def _whole(files: dict[str, str]) -> str:
    """One sha256 over every file's path and hash, in path order.

    Args:
        files: The file hashes, from `arc42_files`.

    Returns:
        The digest.
    """
    whole = hashlib.sha256()
    for name in sorted(files):
        whole.update(f"{name}\0{files[name]}\n".encode())
    return whole.hexdigest()


def arc42_revision(arch_root: str | Path) -> str | None:
    """Hash the effective version of the architecture.

    Args:
        arch_root: The architecture directory holding `arc42/`.

    Returns:
        The sha256 over every file of `arc42/`, or None when that folder does not exist.
    """
    files = arc42_files(arch_root)
    return None if files is None else _whole(files)


def referenced_views(work: Path, arch_root: str | Path, known: set[str]) -> list[str]:
    """The arc42 files the saved work read or wrote.

    Args:
        work: The architecture step's working directory.
        arch_root: The architecture directory holding `arc42/`, as the step names it; its
            resolved spelling is matched too.
        known: Every arc42 file, relative to `arc42/`, recorded or current.

    Returns:
        The files, relative to `arc42/`: each one the survey, ledger or decision names by
        absolute path (a named folder stands for the files under it), and each one the
        draft holds a copy of.
    """
    given = Path(arch_root).expanduser()
    roots = {
        str(given / EFFECTIVE_FOLDER),
        str(given.resolve() / EFFECTIVE_FOLDER),
    }
    found: set[str] = set()
    for name in READ_RECORDS:
        path = work / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = text.replace("\\/", "/")
        for root in roots:
            for chunk in text.split(root + "/")[1:]:
                end = PATH_END.search(chunk)
                rel = (chunk[: end.start()] if end else chunk).rstrip(".:/")
                if rel in known:
                    found.add(rel)
                elif rel:
                    found |= {k for k in known if k.startswith(rel + "/")}
    draft = work / DRAFT_DIR
    if draft.is_dir():
        found |= {
            p.relative_to(draft).as_posix()
            for p in draft.rglob("*")
            if p.is_file() and p.relative_to(draft).as_posix() in known
        }
    return sorted(found)


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


def _write_record(
    work_dir: Path,
    root: str | Path,
    files: dict[str, str],
    *,
    integrating: bool = False,
) -> dict:
    """Record the arc42 the saved work now stands on, atomically.

    Args:
        work_dir: The architecture step's working directory.
        root: The architecture directory holding `arc42/`, as the step names it.
        files: The current file hashes, from `arc42_files`.
        integrating: Whether the step's own integration is writing arc42.

    Returns:
        The record written.
    """
    views = referenced_views(work_dir, root, set(files))
    record = {
        "archRoot": str(Path(root).expanduser()),
        "revision": _whole(files),
        "files": files,
        "views": {name: files[name] for name in views},
        "integrating": integrating,
        "recordedAt": _now(),
    }
    work_dir.mkdir(parents=True, exist_ok=True)
    tmp = work_dir / f".{RECORD_NAME}.tmp"
    tmp.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(work_dir / RECORD_NAME)
    return record


def record_problem(
    work_dir: str | Path, arch_root: str | Path | None = None
) -> str | None:
    """Say which views the saved work read have changed in arc42, or None when none has.

    Args:
        work_dir: The architecture step's working directory.
        arch_root: The architecture directory; the record's own `archRoot` when omitted.

    Returns:
        The reason, or None when every view the work read or wrote still has the hash it was
        recorded with, the step's own integration is in progress, or the record predates
        per-file hashes (then the survey's own freshness binding judges the views it cited).
    """
    record = read_record(work_dir)
    if record is None or record.get("integrating") is True:
        return None
    root = arch_root or record.get("archRoot")
    if not root:
        return None
    current = arc42_files(root)
    if current is None:
        return f"the effective version {Path(root) / EFFECTIVE_FOLDER} does not exist"
    recorded = record.get("files")
    if not isinstance(recorded, dict):
        return None
    work = Path(work_dir).expanduser().resolve()
    views = referenced_views(work, root, set(recorded) | set(current))
    changed = [v for v in views if recorded.get(v) != current.get(v)]
    if not changed:
        return None
    shown = ", ".join(changed[:5]) + (
        f" and {len(changed) - 5} more" if len(changed) > 5 else ""
    )
    return f"arc42 views this work read changed since it was produced: {shown}"


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
    """Bind the step's saved work to the arc42 views it read, setting it aside when they changed.

    With no saved work, or saved work whose views are unchanged, the arc42 as it now is is
    recorded. With saved work one of whose views changed (and no integration of this step in
    progress), every saved file and folder but the relay logs moves to
    `<stale_root>/stale-<timestamp>/architecture/` and the current arc42 is recorded, so the
    step redoes its work from the survey.

    Args:
        arch_root: The architecture directory holding `arc42/`.
        work_dir: The architecture step's working directory.
        stale_root: Where the dated stale folder is made; the working directory's parent when
            omitted.

    Returns:
        `{ok, status, revision, reason, movedTo, moved, views}`: `status` is `new`, `current`,
        `integrating` or `stale`; `moved` counts the entries set aside; `views` counts the
        arc42 files the saved work read or wrote.
    """
    work = Path(work_dir).expanduser().resolve()
    root = Path(arch_root).expanduser()
    files = arc42_files(root)
    if files is None:
        why = f"the effective version {root / EFFECTIVE_FOLDER} does not exist"
        return {"ok": False, "error": why, "summary": {"ok": False, "error": why}}
    saved = _saved_items(work)
    record = read_record(work)
    out: dict = {
        "ok": True,
        "revision": _whole(files),
        "movedTo": None,
        "moved": 0,
        "reason": "",
    }
    if record is not None and record.get("integrating") is True:
        out["status"] = "integrating"
        out["views"] = len(record.get("views") or {})
    else:
        problem = record_problem(work, root) if saved else None
        if problem is None:
            out["status"] = "current" if saved else "new"
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
            out.update(
                status="stale", reason=problem, movedTo=str(dest), moved=len(saved)
            )
        written = _write_record(work, root, files)
        out["views"] = len(written["views"])
    out["summary"] = {
        k: out[k]
        for k in ("ok", "status", "revision", "reason", "movedTo", "moved", "views")
    }
    return out


def mark(arch_root: str | Path, work_dir: str | Path, state: str) -> dict:
    """Record the step's own integration: begun (`integrating`) or approved (`integrated`).

    `integrating` keeps the recorded hashes and marks arc42 as being written by this step;
    `integrated` records the effective version as it now is, the views the saved work now
    stands on.

    Args:
        arch_root: The architecture directory holding `arc42/`.
        work_dir: The architecture step's working directory.
        state: `integrating` or `integrated`.

    Returns:
        `{ok, state, revision}`, or `{ok: false, error}`.
    """
    work = Path(work_dir).expanduser().resolve()
    root = Path(arch_root).expanduser()
    files = arc42_files(root)
    if files is None:
        why = f"the effective version {root / EFFECTIVE_FOLDER} does not exist"
        return {"ok": False, "error": why, "summary": {"ok": False, "error": why}}
    if state == "integrating":
        record = read_record(work)
        if record is None or not isinstance(record.get("files"), dict):
            record = _write_record(work, root, files, integrating=True)
        else:
            record["integrating"] = True
            record["recordedAt"] = _now()
            tmp = work / f".{RECORD_NAME}.tmp"
            tmp.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            tmp.replace(work / RECORD_NAME)
    elif state == "integrated":
        record = _write_record(work, root, files)
    else:
        why = f"unknown state {state!r}: integrating or integrated"
        return {"ok": False, "error": why, "summary": {"ok": False, "error": why}}
    out = {"ok": True, "state": state, "revision": record["revision"]}
    return out | {"summary": dict(out)}
