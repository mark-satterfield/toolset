#!/usr/bin/env python3
"""The one place that reads and writes `lifecycle_state` on architecture files for the pipeline.

Every architecture file, in any version (effective, target, delta, built), carries its own
review state: `in-review` until an architecture review approves it, `effective` once it has.
The state is per file and says nothing about any other file.

`depscore.py arch-state` runs `states`, which reads the state of the files an architecture
step relies on and writes nothing. `depscore.py arch-approve` runs `promote`, which sets the
integrated files a conformance review covered to `effective`. Setting a file that is already
`effective` changes nothing, so the step can run again on resume.

Approval is by file, because the review state lives in each file's frontmatter: approving a
file approves every view in it.

`depscore.py arch-constraints` runs `snapshot_constraints`, which fingerprints section 2 (the
owner's constraints) so the architecture step can prove no session wrote there.
`depscore.py arch-target` runs `write_target`, which checks an approved draft and writes it to
`target/<subject>/` as `in-review`.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

STATE_KEY = "lifecycle_state"
EFFECTIVE = "effective"
IN_REVIEW = "in-review"
FENCE = "---"
EFFECTIVE_FOLDER = "arc42"
CONSTRAINTS_FOLDER = "02-architecture-constraints"
TARGET_FOLDER = "target"
DELTA_FOLDER = "delta"
CATALOG_KEYS = ("view_type", "scope", "subject", "shows")
SUBJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DATE_IN_NAME = re.compile(r"\d{4}-\d{2}(-\d{2})?")
SKIPPED_SUFFIXES = (".meta.json",)


def _split_frontmatter(text: str) -> tuple[list[str], int, int] | None:
    """Locate the YAML frontmatter block in a document.

    Args:
        text: The whole file.

    Returns:
        The frontmatter lines, the index of the first line after the opening fence, and
        the index of the closing fence — or None when the file opens with no fence.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == FENCE:
            return lines, 1, idx
    return None


def _set_state(text: str, state: str) -> tuple[str, str]:
    """Set the top-level `lifecycle_state` of one document's text.

    Args:
        text: The whole file.
        state: The value to set.

    Returns:
        The new text and "promoted" when the value changed, the text unchanged and
        "unchanged" when it already held `state`, or the text unchanged and
        "no-frontmatter" when it carries no YAML frontmatter.
    """
    split = _split_frontmatter(text)
    if split is None:
        return text, "no-frontmatter"
    lines, start, close = split
    for idx in range(start, close):
        # Top-level keys only: an indented `lifecycle_state:` belongs to a nested mapping,
        # and rewriting it unindented would break the frontmatter it sits in.
        line = lines[idx]
        if not line.startswith(f"{STATE_KEY}:"):
            continue
        if line[len(STATE_KEY) + 1 :].strip() == state:
            return text, "unchanged"
        lines[idx] = f"{STATE_KEY}: {state}"
        break
    else:
        # The field is required core on every managed document. An architecture file
        # without one is missing its classification, not exempt from it, so the key is
        # added rather than the file skipped.
        lines.insert(close, f"{STATE_KEY}: {state}")
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + trailing, "promoted"


def _promote_one(path: Path) -> str:
    """Set one file's `lifecycle_state` to `effective`.

    Args:
        path: The architecture file.

    Returns:
        "promoted" when the value changed, "unchanged" when it was already effective, or
        "no-frontmatter" when the file carries no YAML frontmatter to classify.
    """
    text = path.read_text(encoding="utf-8")
    new, outcome = _set_state(text, EFFECTIVE)
    if outcome == "promoted":
        path.write_text(new, encoding="utf-8")
    return outcome


def _state_of(path: Path) -> str:
    """Read one file's top-level `lifecycle_state`.

    Args:
        path: The architecture file.

    Returns:
        The value, or an empty string when the file has no frontmatter or no such key.
    """
    split = _split_frontmatter(path.read_text(encoding="utf-8"))
    if split is None:
        return ""
    lines, start, close = split
    for idx in range(start, close):
        if lines[idx].startswith(f"{STATE_KEY}:"):
            return lines[idx][len(STATE_KEY) + 1 :].strip()
    return ""


def _arch_root(arch_root: str | None) -> Path | None:
    """Resolve the architecture directory a caller names, which may be a file inside it.

    Args:
        arch_root: The architecture directory or a file in it, or None.

    Returns:
        The directory, or None when no root was given.
    """
    if not arch_root:
        return None
    root = Path(arch_root).resolve()
    return root.parent if root.is_file() else root


def states(files: list[str], *, arch_root: str | None) -> dict:
    """Read the `lifecycle_state` of the architecture files a step relies on; writes nothing.

    Args:
        files: The architecture files, as absolute paths.
        arch_root: The architecture directory every file must sit under, or None to skip
            the check.

    Returns:
        A report: each readable file's state, the files not at `effective` (a file with
        no state counts as not effective), and the files refused or unreadable.
    """
    root = _arch_root(arch_root)
    report: dict = {"states": {}, "notEffective": [], "refused": [], "failed": []}
    for raw in files:
        name = str(raw).strip()
        if not name:
            continue
        try:
            resolved = Path(name).resolve()
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        if root is not None and not resolved.is_relative_to(root):
            report["refused"].append(
                {"path": name, "reason": f"outside the architecture at {root}"}
            )
            continue
        if not resolved.is_file():
            report["failed"].append({"path": name, "reason": "not a file"})
            continue
        try:
            state = _state_of(resolved)
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        report["states"][str(resolved)] = state
        if state != EFFECTIVE:
            report["notEffective"].append({"path": str(resolved), "state": state})
    report["summary"] = {
        "files": len(report["states"]),
        "notEffective": len(report["notEffective"]),
        "refused": len(report["refused"]),
        "failed": len(report["failed"]),
    }
    return report


def _resolved_set(files: list[str]) -> set[str]:
    """Resolve a list of paths to a set of absolute path strings.

    Args:
        files: The paths.

    Returns:
        Every path that resolves, as a string.
    """
    out: set[str] = set()
    for raw in files:
        name = str(raw).strip()
        if not name:
            continue
        try:
            out.add(str(Path(name).resolve()))
        except OSError:
            continue
    return out


def promote(files: list[str], *, arch_root: str | None, reviewed: list[str]) -> dict:
    """Set the integrated architecture files a conformance review covered to `effective`.

    Every path is held to `arch_root` when one is given. A changed-file list is reported by
    an agent, so a path outside the architecture is refused rather than written — this
    function rewrites documents, and the blast radius of a bad path is the vault. A file is
    promoted only when the review names it: a change nobody reviewed stays `in-review`.

    Args:
        files: The architecture files the step changed or created, as absolute paths.
        arch_root: The architecture directory every file must sit under, or None to skip
            the check.
        reviewed: The files the conformance review checked and found conforming.

    Returns:
        A report: the files promoted, those already effective, those carrying no
        frontmatter, those not reviewed, and those refused or unreadable, each with its
        reason.
    """
    report: dict = {
        "promoted": [],
        "unchanged": [],
        "noFrontmatter": [],
        "unreviewed": [],
        "refused": [],
        "failed": [],
    }
    root = _arch_root(arch_root)
    covered = _resolved_set(reviewed)
    for raw in files:
        name = str(raw).strip()
        if not name:
            continue
        try:
            resolved = Path(name).resolve()
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        if root is not None and not resolved.is_relative_to(root):
            report["refused"].append(
                {"path": name, "reason": f"outside the architecture at {root}"}
            )
            continue
        if not resolved.is_file():
            report["failed"].append({"path": name, "reason": "not a file"})
            continue
        if str(resolved) not in covered:
            report["unreviewed"].append(str(resolved))
            continue
        try:
            outcome = _promote_one(resolved)
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        bucket = {"promoted": "promoted", "unchanged": "unchanged"}.get(
            outcome, "noFrontmatter"
        )
        report[bucket].append(str(resolved))
    report["summary"] = {key: len(report[key]) for key in report}
    return report


def _digest(paths: list[Path], base: Path) -> tuple[dict[str, str], str]:
    """Hash each file and the whole set.

    Args:
        paths: The files, in a stable order.
        base: The directory the reported names are relative to.

    Returns:
        Each file's sha256 by relative name, and one sha256 over every name and hash.
    """
    each: dict[str, str] = {}
    whole = hashlib.sha256()
    for path in paths:
        rel = path.relative_to(base).as_posix()
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        each[rel] = sha
        whole.update(f"{rel}\0{sha}\n".encode())
    return each, whole.hexdigest()


def snapshot_constraints(arch_root: str) -> dict:
    """Fingerprint section 2 of the effective architecture: its files and its git status.

    The owner writes section 2 and the pipeline never does. The architecture step takes one
    snapshot before its sessions run and one after; any difference is a write the step made.

    Args:
        arch_root: The architecture directory holding `arc42/`.

    Returns:
        The folder, whether it exists, each file's sha256, one digest over all of them, and
        `git status --porcelain` for the folder (with git's error when it could not run).
    """
    root = _arch_root(arch_root)
    if root is None:
        return {"error": "no architecture directory was given"}
    folder = root / EFFECTIVE_FOLDER / CONSTRAINTS_FOLDER
    files = (
        sorted(p for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else []
    )
    each, digest = _digest(files, folder) if files else ({}, "")
    git = subprocess.run(  # noqa: S603
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            str(folder),
        ],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "folder": str(folder),
        "exists": folder.is_dir(),
        "files": each,
        "digest": digest,
        "gitStatus": git.stdout.splitlines() if git.returncode == 0 else [],
        "gitError": git.stderr.strip() if git.returncode != 0 else "",
        "summary": {"files": len(each), "digest": digest},
    }


def _subject_refusals(subject: str, forbid: list[str]) -> list[str]:
    """Name every reason a target subject name is not a subject.

    Args:
        subject: The proposed `<subject>` folder name.
        forbid: Names a subject never carries (the Epic, the PRD, the bead prefix).

    Returns:
        The reasons; empty when the name is a subject.
    """
    reasons = []
    if not SUBJECT_NAME.match(subject) or subject in {".", ".."}:
        reasons.append(
            f"subject {subject!r} is not one folder name of letters, digits, '.', '_' or '-'"
        )
    if DATE_IN_NAME.search(subject):
        reasons.append(f"subject {subject!r} carries a date")
    lowered = subject.lower()
    reasons.extend(
        f"subject {subject!r} carries {token!r}, which names the Epic, PRD or bead, not a subject"
        for token in (t.strip().lower() for t in forbid)
        if token and token in lowered
    )
    return reasons


def _draft_files(draft: Path) -> list[Path]:
    """List the files of a draft target, without recorder sidecars or hidden files.

    Args:
        draft: The draft directory.

    Returns:
        The files, sorted.
    """
    return sorted(
        p
        for p in draft.rglob("*")
        if p.is_file()
        and not p.name.endswith(SKIPPED_SUFFIXES)
        and not any(part.startswith(".") for part in p.relative_to(draft).parts)
    )


def _catalog_gaps(path: Path) -> list[str]:
    """Name the catalog keys a view's frontmatter lacks.

    Args:
        path: The view file.

    Returns:
        The missing keys; every key when the file has no frontmatter.
    """
    split = _split_frontmatter(path.read_text(encoding="utf-8"))
    if split is None:
        return list(CATALOG_KEYS)
    lines, start, close = split
    present = {
        lines[i].split(":", 1)[0].strip()
        for i in range(start, close)
        if ":" in lines[i]
    }
    return [key for key in CATALOG_KEYS if key not in present]


def _draft_refusals(draft: Path, files: list[Path]) -> list[str]:
    """Name every reason a draft cannot become a target.

    Args:
        draft: The draft directory.
        files: Its files.

    Returns:
        The reasons; empty when the draft can be written.
    """
    reasons = []
    rels = [p.relative_to(draft) for p in files]
    if not any(r.parts and r.parts[0] == DELTA_FOLDER for r in rels):
        reasons.append(
            f"the draft has no {DELTA_FOLDER}/ views: the delta is what Specs and Tasks read"
        )
    reasons.extend(
        f"{r.as_posix()} is in section 2, which holds the owner's constraints"
        for r in rels
        if CONSTRAINTS_FOLDER in r.parts
    )
    for path, rel in zip(files, rels, strict=True):
        if path.suffix != ".md":
            continue
        gaps = _catalog_gaps(path)
        if gaps:
            reasons.append(
                f"{rel.as_posix()} lacks catalog frontmatter: {', '.join(gaps)}"
            )
    return reasons


def write_target(
    draft: str,
    *,
    arch_root: str,
    subject: str,
    forbid: list[str],
    dry_run: bool = False,
) -> dict:
    """Check an approved draft and write it to `target/<subject>/`, every view `in-review`.

    The draft has the arc42 section layout and a `delta/` folder. It is refused, and nothing
    is written, when the subject is not a subject name, the draft has no delta, a file sits in
    section 2, or a Markdown view lacks its catalog frontmatter. A target already at that path
    is replaced, so a resumed step writes the same target again.

    Args:
        draft: The draft directory.
        arch_root: The architecture directory holding `target/`.
        subject: The subject the target describes.
        forbid: Names a subject never carries (the Epic, the PRD, the bead prefix).
        dry_run: Check only; write nothing.

    Returns:
        `ok`, the refusals, the target and delta directories, and the files written (or that
        would be written).
    """
    root = _arch_root(arch_root)
    source = Path(draft).resolve()
    if root is None:
        none = ["no architecture directory was given"]
        return {
            "ok": False,
            "refusals": none,
            "subjectRefusals": [],
            "summary": {"ok": False, "refusals": none},
        }
    subject_refusals = _subject_refusals(subject, forbid)
    files = _draft_files(source) if source.is_dir() else []
    draft_refusals = (
        _draft_refusals(source, files)
        if source.is_dir()
        else [f"the draft {source} is not a directory"]
    )
    refusals = subject_refusals + draft_refusals
    dest = root / TARGET_FOLDER / subject
    if not subject_refusals and not dest.resolve().is_relative_to(
        (root / TARGET_FOLDER).resolve()
    ):
        subject_refusals = [f"{dest} is outside {root / TARGET_FOLDER}"]
        refusals = subject_refusals + refusals
    delta = [p for p in files if p.relative_to(source).parts[0] == DELTA_FOLDER]
    report: dict = {
        "ok": not refusals,
        "refusals": refusals,
        "subjectRefusals": subject_refusals,
        "subject": subject,
        "targetDir": str(dest),
        "deltaDir": str(dest / DELTA_FOLDER),
        "files": [str(dest / p.relative_to(source)) for p in files],
        "deltaFiles": [str(dest / p.relative_to(source)) for p in delta],
        "dryRun": dry_run,
    }
    # The summary carries what a caller acts on, because `--out` prints only the summary.
    report["summary"] = {
        key: report[key]
        for key in (
            "ok",
            "refusals",
            "subjectRefusals",
            "subject",
            "targetDir",
            "deltaDir",
            "dryRun",
        )
    } | {"files": len(report["files"]), "deltaFiles": len(report["deltaFiles"])}
    if refusals or dry_run:
        return report
    if dest.exists():
        shutil.rmtree(dest)
    for path in files:
        out = dest / path.relative_to(source)
        out.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".md":
            text, _ = _set_state(path.read_text(encoding="utf-8"), IN_REVIEW)
            out.write_text(text, encoding="utf-8")
        else:
            shutil.copyfile(path, out)
    return report
