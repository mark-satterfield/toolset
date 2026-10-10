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
owner's constraints) so the architecture step can prove no session wrote there, and with
`--keep` copies it aside; `depscore.py arch-constraints-restore` runs `restore_constraints`,
which puts it back from that copy.
`depscore.py arch-snapshot` runs `snapshot_tree`, which fingerprints every file of `arc42/`,
`target/` and `built/`, so a step measures what its sessions wrote.
`depscore.py arch-target` runs `write_target`, which checks an approved draft and writes it to
`target/<subject>/` as `in-review`.
`depscore.py arch-delta` runs `delta_items`, which lists the elements a target's delta shows,
one item per element, for the phases that make Specs and Tasks from the delta.
`depscore.py arch-target-names` runs `target_names`, which tells which names a target's files
mention, so a step checks that a repository it created is one the target names.
`depscore.py arch-target-remove` runs `remove_target`, which deletes `target/<subject>/` once
the Specs and Tasks made from its delta are written, and commits the removal.
`depscore.py arch-built-remove` runs `remove_built`, which deletes the `built/<subject>/` files
the effective version has been corrected to match, and commits the removal.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed Git argv without shell execution.
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import archclosure
import contracts

if TYPE_CHECKING:
    import _hashlib

from archbaseline import baseline_facts
from archcatalog import read_catalog, split_frontmatter
from archgit import git_result, run_git
from archmatrix import catalog_elements, element_id, row_of, satisfied
from archrevision import arc42_revision
from contracts import (
    BaselineManifest,
    BuiltRemoval,
    ConstraintRestore,
    ConstraintSnapshot,
    DeltaItem,
    DeltaResult,
    DeltaView,
    FileError,
    IntegrationCommit,
    JsonObject,
    PromotionReport,
    Refusal,
    StateReport,
    TargetNames,
    TargetRemoval,
    TargetResult,
    TreeDifference,
    TreeSnapshot,
    json_object,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

STATE_KEY = "lifecycle_state"
EFFECTIVE = "effective"
IN_REVIEW = "in-review"
FENCE = "---"
MIN_BUILT_PATH_PARTS = 2
EFFECTIVE_FOLDER = "arc42"
CONSTRAINTS_FOLDER = "02-architecture-constraints"
TARGET_FOLDER = "target"
DELTA_FOLDER = "delta"
# The baseline handoff: the effective views each capability relies on and the implementation
# work derived from the element matrix. It belongs to the future set, never to the
# delta; `delta/baseline.json` is read only from targets written before that rule.
BASELINE_FILE = "baseline.json"
SEED_FILES = (BASELINE_FILE, f"{DELTA_FOLDER}/{BASELINE_FILE}")
# How the documents are deduplicated: `none` (future = current, one set, no delta), `new` (no
# current, one set that is both the future and the delta), `partial` (the future set and a delta
# of the change alone).
CHANGE_NOTES = {
    "none": "No architecture change: current and future are the same. The future set is the "
    "effective views cited in `entries[].documents`; there is no delta. Build work is "
    "every element those views show, including satisfied elements whose Tasks verify them.",
    "new": "Entirely new architecture: there is no current set. The target views are both the "
    "future and the delta; there is no separate delta folder. Build work is the elements those "
    "views show plus `implementationWork`.",
    "partial": "Partial change: the target views are the future set, and `delta/` holds the "
    "change alone. Build work is the elements the delta shows plus `implementationWork`, the "
    "elements of the future set not satisfied by the element matrix.",
    "pending": "Change not yet authored: the assessment names design or documentation work "
    "(`designChanged` or `documentationChanged`), and no view is written yet, so the case is "
    "not known: it becomes `new` or `partial` when the views are authored. It is never `none`, "
    "and no target is written in this state. Build work so far is `implementationWork`.",
}
BUILT_FOLDER = "built"
CATALOG_KEYS = ("view_type", "scope", "subject", "shows")
SUBJECT_SEPARATOR = re.compile(r"[^a-z0-9]+")
DATE_IN_NAME = re.compile(r"\d{4}-\d{2}(-\d{2})?")
SKIPPED_SUFFIXES = (".meta.json",)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def set_state(text: str, state: str) -> tuple[str, str]:
    """Set the top-level `lifecycle_state` of one document's text.

    Args:
        text: The whole file.
        state: The value to set.

    Returns:
        The new text and "promoted" when the value changed, the text unchanged and
        "unchanged" when it already held `state`, or the text unchanged and
        "no-frontmatter" when it carries no YAML frontmatter.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    idx: int
    lines: list[str]
    start: int
    close: int
    if not (isinstance(text, str)) or not (isinstance(state, str)):
        argument_error: str = "set_state: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    split: tuple[list[str], int, int] | None = split_frontmatter(text)
    if split is None:
        return text, "no-frontmatter"
    lines, start, close = split
    for idx in range(start, close):
        # Top-level keys only: an indented `lifecycle_state:` belongs to a nested mapping,
        # and rewriting it unindented would break the frontmatter it sits in.
        line: str = lines[idx]
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
    trailing: str = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + trailing, "promoted"


def _promote_one(path: Path) -> str:
    """Set one file's `lifecycle_state` to `effective`.

    Args:
        path: The architecture file.

    Returns:
        "promoted" when the value changed, "unchanged" when it was already effective, or
        "no-frontmatter" when the file carries no YAML frontmatter to classify.

    """
    new: str
    outcome: str
    text: str = path.read_text(encoding="utf-8")
    new, outcome = set_state(text, EFFECTIVE)
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
    idx: int
    lines: list[str]
    start: int
    close: int
    split: tuple[list[str], int, int] | None = split_frontmatter(path.read_text(encoding="utf-8"))
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
    root: Path = Path(arch_root).resolve()
    return root.parent if root.is_file() else root


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def states(files: list[str], *, arch_root: str | None) -> StateReport:
    """Read the `lifecycle_state` of the architecture files a step relies on; writes nothing.

    Args:
        files: The architecture files, as absolute paths.
        arch_root: The architecture directory every file must sit under, or None to skip
            the check.

    Returns:
        A report: each readable file's state, the files not at `effective` (a file with
        no state counts as not effective), and the files refused or unreadable.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    raw: str
    if not (isinstance(files, list)) or not (isinstance(arch_root, str) or arch_root is None):
        argument_error: str = "states: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path | None = _arch_root(arch_root)
    report: StateReport = {"states": {}, "notEffective": [], "refused": [], "failed": [], "summary": {}}
    for raw in files:
        name: str = str(raw).strip()
        if not name:
            continue
        try:
            resolved: Path = Path(name).resolve()
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        if root is not None and not resolved.is_relative_to(root):
            report["refused"].append(
                {"path": name, "reason": f"outside the architecture at {root}"},
            )
            continue
        if not resolved.is_file():
            report["failed"].append({"path": name, "reason": "not a file"})
            continue
        try:
            state: str = _state_of(resolved)
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
    raw: str
    out: set[str] = set()
    for raw in files:
        name: str = str(raw).strip()
        if not name:
            continue
        try:
            out.add(str(Path(name).resolve()))
        except OSError:
            continue
    return out


def _in_constraints(path: Path) -> bool:
    """Tell whether a path lies in section 2 of the effective version.

    Args:
        path: A resolved path.

    Returns:
        True when the path has `arc42/02-architecture-constraints` among its parts.

    """
    parts: tuple[str, ...] = path.parts
    return any(parts[i] == EFFECTIVE_FOLDER and parts[i + 1] == CONSTRAINTS_FOLDER for i in range(len(parts) - 1))


def _promotion_bucket(report: PromotionReport, outcome: str) -> list[str]:
    """Select the result list for an attempted lifecycle update.

    Returns:
        The corresponding mutable result list.

    """
    if outcome == "promoted":
        return report["promoted"]
    if outcome == "unchanged":
        return report["unchanged"]
    return report["noFrontmatter"]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def promote(files: list[str], *, arch_root: str | None, reviewed: list[str]) -> PromotionReport:
    """Set the integrated architecture files a conformance review covered to `effective`.

    Every path is held to `arch_root` when one is given. A changed-file list is reported by
    an agent, so a path outside the architecture is refused rather than written — this
    function rewrites documents, and the blast radius of a bad path is the vault. A file in
    section 2 is refused: section 2 holds the owner's constraints, which carry no review state
    the pipeline sets. A file is promoted only when the review names it: a change nobody
    reviewed stays `in-review`.

    Args:
        files: The architecture files the step changed or created, as absolute paths.
        arch_root: The architecture directory every file must sit under, or None to skip
            the check.
        reviewed: The files the conformance review checked and found conforming.

    Returns:
        A report: the files promoted, those already effective, those carrying no
        frontmatter, those not reviewed, and those refused or unreadable, each with its
        reason.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    raw: str
    if (
        not (isinstance(files, list))
        or not (isinstance(arch_root, str) or arch_root is None)
        or not (isinstance(reviewed, list))
    ):
        argument_error: str = "promote: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    report: PromotionReport = {
        "summary": {},
        "promoted": [],
        "unchanged": [],
        "noFrontmatter": [],
        "unreviewed": [],
        "refused": [],
        "failed": [],
    }
    root: Path | None = _arch_root(arch_root)
    covered: set[str] = _resolved_set(reviewed)
    for raw in files:
        name: str = str(raw).strip()
        if not name:
            continue
        try:
            resolved: Path = Path(name).resolve()
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        if root is not None and not resolved.is_relative_to(root):
            report["refused"].append(
                {"path": name, "reason": f"outside the architecture at {root}"},
            )
            continue
        if _in_constraints(resolved):
            report["refused"].append(
                {
                    "path": name,
                    "reason": "in section 2, which holds the owner's constraints",
                },
            )
            continue
        if not resolved.is_file():
            report["failed"].append({"path": name, "reason": "not a file"})
            continue
        if str(resolved) not in covered:
            report["unreviewed"].append(str(resolved))
            continue
        try:
            outcome: str = _promote_one(resolved)
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        _promotion_bucket(report, outcome).append(str(resolved))

    report["summary"] = {
        "promoted": len(report["promoted"]),
        "unchanged": len(report["unchanged"]),
        "noFrontmatter": len(report["noFrontmatter"]),
        "unreviewed": len(report["unreviewed"]),
        "refused": len(report["refused"]),
        "failed": len(report["failed"]),
    }
    return report


def _digest(paths: list[Path], base: Path) -> tuple[dict[str, str], str]:
    """Hash each file and the whole set.

    Args:
        paths: The files, in a stable order.
        base: The directory the reported names are relative to.

    Returns:
        Each file's sha256 by relative name, and one sha256 over every name and hash.

    """
    path: Path
    each: dict[str, str] = {}
    whole: _hashlib.HASH = hashlib.sha256()
    for path in paths:
        rel: str = path.relative_to(base).as_posix()
        sha: str = hashlib.sha256(path.read_bytes()).hexdigest()
        each[rel] = sha
        whole.update(f"{rel}\0{sha}\n".encode())
    return each, whole.hexdigest()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def snapshot_constraints(arch_root: str, *, keep: bool = False) -> ConstraintSnapshot | FileError:
    """Fingerprint section 2 of the effective architecture: its files and its git status.

    The owner writes section 2 and the pipeline never does. The architecture step takes one
    snapshot before its sessions run and one after; any difference is a write the step made.
    With `keep`, the folder's files are copied to a new temporary directory, named in `kept`,
    so `restore_constraints` can put the folder back as it was.

    Args:
        arch_root: The architecture directory holding `arc42/`.
        keep: Copy the folder's files aside for a later restore.

    Returns:
        The folder, whether it exists, each file's sha256, one digest over all of them,
        `git status --porcelain` for the folder (with git's error when it could not run), and
        with `keep` the directory holding the copy.

    Raises:
        TypeError: An argument violates the declared input contract.
        FileNotFoundError: The Git executable is unavailable.

    """
    path: Path
    each: dict[str, str]
    digest: str
    if not (isinstance(arch_root, str)) or not (isinstance(keep, bool)):
        argument_error: str = "snapshot_constraints: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path | None = _arch_root(arch_root)
    if root is None:
        return {"error": "no architecture directory was given"}
    folder: Path = root / EFFECTIVE_FOLDER / CONSTRAINTS_FOLDER
    files: list[Path] = sorted(p for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else []
    each, digest = _digest(files, folder) if files else ({}, "")
    executable: str | None = shutil.which("git")
    if executable is None:
        message: str = "Git executable is unavailable"
        raise FileNotFoundError(message)
    git: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved Git and fixed status argv.
        [
            executable,
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            str(folder),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=float(os.environ.get("ATW_GIT_TIMEOUT", "120")),
    )
    out: ConstraintSnapshot = {
        "folder": str(folder),
        "exists": folder.is_dir(),
        "files": each,
        "digest": digest,
        "gitStatus": git.stdout.splitlines() if git.returncode == 0 else [],
        "gitError": git.stderr.strip() if git.returncode != 0 else "",
        "summary": {"files": len(each), "digest": digest},
    }
    if keep:
        kept: Path = Path(tempfile.mkdtemp(prefix="arch-constraints-"))
        for path in files:
            dest: Path = kept / path.relative_to(folder)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        out["kept"] = str(kept)
    return out


def _path_depth(path: Path) -> int:
    """Count path components for deepest-first directory cleanup.

    Returns:
        The path depth.

    """
    return len(path.parts)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def restore_constraints(arch_root: str, kept: str) -> ConstraintRestore | FileError:
    """Put section 2 back as `snapshot_constraints(keep=True)` copied it.

    A session that wrote under section 2 has already failed the step; this undoes the write
    so the owner's constraints stand as the owner left them. Files the copy does not hold are
    deleted, and every file it holds is written back where its content differs.

    Args:
        arch_root: The architecture directory holding `arc42/`.
        kept: The directory `snapshot_constraints` named in `kept`.

    Returns:
        The files written back and the files deleted, or `error` when the copy is missing.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    rel: str
    path: Path
    directory: Path
    if not (isinstance(arch_root, str)) or not (isinstance(kept, str)):
        argument_error: str = "restore_constraints: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path | None = _arch_root(arch_root)
    if root is None:
        return {"error": "no architecture directory was given"}
    source: Path = Path(kept)
    if not source.is_dir():
        return {"error": f"the copy of section 2 at {source} does not exist"}
    folder: Path = root / EFFECTIVE_FOLDER / CONSTRAINTS_FOLDER
    saved: dict[str, Path] = {p.relative_to(source).as_posix(): p for p in source.rglob("*") if p.is_file()}
    current: dict[str, Path] = (
        {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()} if folder.is_dir() else {}
    )
    deleted: list[str] = []
    for rel, path in sorted(current.items()):
        if rel not in saved:
            path.unlink()
            deleted.append(str(path))
    written: list[str] = []
    for rel, path in sorted(saved.items()):
        dest: Path = folder / rel
        if dest.is_file() and dest.read_bytes() == path.read_bytes():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        written.append(str(dest))
    for directory in sorted(
        (p for p in folder.rglob("*") if p.is_dir()) if folder.is_dir() else [],
        key=_path_depth,
        reverse=True,
    ):
        if not any(directory.iterdir()):
            directory.rmdir()
    return {
        "folder": str(folder),
        "written": written,
        "deleted": deleted,
        "summary": {"written": len(written), "deleted": len(deleted)},
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def snapshot_tree(arch_root: str) -> TreeSnapshot | FileError:
    """Fingerprint every file of every version: `arc42/`, `target/` and `built/`.

    A step that must not write in the architecture, or must write only where it says it did,
    takes one snapshot before its sessions run and one after; the difference is what they
    wrote, measured rather than reported.

    Args:
        arch_root: The architecture directory holding the version folders.

    Returns:
        The root, each file's sha256 by path relative to the root, and one digest over all of
        them.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    each: dict[str, str]
    digest: str
    if not (isinstance(arch_root, str)):
        argument_error: str = "snapshot_tree: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path | None = _arch_root(arch_root)
    if root is None:
        return {"error": "no architecture directory was given"}
    if not root.is_dir():
        return {"error": f"the architecture directory {root} does not exist"}
    files: list[Path] = sorted(
        p
        for name in (EFFECTIVE_FOLDER, TARGET_FOLDER, BUILT_FOLDER)
        if (root / name).is_dir()
        for p in (root / name).rglob("*")
        if p.is_file()
    )
    each, digest = _digest(files, root) if files else ({}, "")
    return {
        "root": str(root),
        "files": each,
        "digest": digest,
        "summary": {"files": len(each), "digest": digest},
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def tree_diff(was: JsonObject, now: JsonObject) -> TreeDifference:
    """Name the files created, changed and deleted between two `snapshot_tree` results.

    Args:
        was: The earlier fingerprint, as `snapshot_tree` returned or `--save` wrote it.
        now: The later fingerprint.

    Returns:
        The created, changed and deleted files, each relative to the architecture root.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(was, dict)) or not (isinstance(now, dict)):
        argument_error: str = "tree_diff: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    before: dict[str, str] = check_type(
        was.get("files", {}),
        dict[str, str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    after: dict[str, str] = check_type(
        now.get("files", {}),
        dict[str, str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    return {
        "created": sorted(k for k in after if k not in before),
        "changed": sorted(k for k in after if k in before and before[k] != after[k]),
        "deleted": sorted(k for k in before if k not in after),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def subject_folder(subject: str) -> str:
    """Derive the `<subject>` folder name from a subject as anyone names it.

    The folder name is the subject folded to ASCII, lower-cased, with every run of characters
    other than `a-z` and `0-9` replaced by one hyphen and no hyphen at either end:
    `Company Intelligence` is `company-intelligence`. A folder name maps to itself.

    Args:
        subject: The subject, as a display name or already as a folder name.

    Returns:
        The folder name; empty when the subject has no letter or digit.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(subject, str)):
        argument_error: str = "subject_folder: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    ascii_only: str = unicodedata.normalize("NFKD", subject).encode("ascii", "ignore").decode("ascii")
    return SUBJECT_SEPARATOR.sub("-", ascii_only.lower()).strip("-")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def subject_name(folder: str, forbid: list[str]) -> str:
    """Remove dates and forbidden names from the subject folder name.

    Args:
        folder: A folder name, from `subject_folder`.
        forbid: Names a subject never carries (the Epic, the PRD, the bead prefix).

    Returns:
        The folder name; empty when nothing is left.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    token: str
    if not (isinstance(folder, str)) or not (isinstance(forbid, list)):
        argument_error: str = "subject_name: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    name: str = DATE_IN_NAME.sub("-", folder)
    for token in sorted((subject_folder(t) for t in forbid), key=len, reverse=True):
        if token:
            name = name.replace(token, "-")
    return SUBJECT_SEPARATOR.sub("-", name).strip("-")


def _subject_refusals(subject: str, folder: str) -> list[str]:
    """Name the reason a target subject cannot name a folder.

    Args:
        subject: The subject as given.
        folder: Its folder name, from `subject_name`.

    Returns:
        The reason; empty when the folder name is not empty.

    """
    if not folder:
        return [
            (
                f"subject {subject!r} has no letter or digit left to name a folder with, "
                "once dates and the Epic, PRD and bead names are taken out"
            ),
        ]
    return []


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
    lines: list[str]
    start: int
    close: int
    split: tuple[list[str], int, int] | None = split_frontmatter(path.read_text(encoding="utf-8"))
    if split is None:
        return list(CATALOG_KEYS)
    lines, start, close = split
    present: set[str] = {lines[i].split(":", 1)[0].strip() for i in range(start, close) if ":" in lines[i]}
    return [key for key in CATALOG_KEYS if key not in present]


def _effective_elements(root: Path) -> set[str]:
    """Name every element a canonical arc42 view shows: the current set.

    Args:
        root: The architecture directory holding `arc42/`.

    Returns:
        The element names, case-folded.

    """
    arc42: Path = root / "arc42"
    if not arc42.is_dir():
        return set()
    return {
        element.casefold()
        for view in arc42.rglob("*.md")
        if CONSTRAINTS_FOLDER not in view.relative_to(arc42).parts
        for element in read_catalog(view)["shows"]
    }


def _change_case(draft: Path, files: list[Path], manifest: BaselineManifest | None) -> str:
    """Tell which case a draft is, consistent with the survey's assessment (see CHANGE_NOTES).

    A draft with no authored view is `none` only when the assessment names no design or
    documentation work; when it names some, the change is `pending` until the views exist.

    Args:
        draft: The draft directory.
        files: Its authored files.
        manifest: The baseline handoff built from the survey, or None without one.

    Returns:
        `none`, `new`, `partial` or `pending`.

    """
    kind: str = _change_kind(draft, files)
    if kind == "none" and manifest and (manifest["designChanged"] or manifest["documentationChanged"]):
        return "pending"
    return kind


def _change_kind(draft: Path, files: list[Path]) -> str:
    """Tell how a draft's views deduplicate: `none`, `new` or `partial` (see CHANGE_NOTES).

    Args:
        draft: The draft directory.
        files: Its authored files.

    Returns:
        `none` with no authored view, `partial` with a `delta/` view, else `new`.

    """
    rels: list[Path] = [p.relative_to(draft) for p in files if p.suffix == ".md"]
    if not rels:
        return "none"
    if any(r.parts and r.parts[0] == DELTA_FOLDER for r in rels):
        return "partial"
    return "new"


def _draft_refusals(draft: Path, files: list[Path]) -> list[str]:
    """Name every reason a draft cannot become a target.

    Args:
        draft: The draft directory.
        files: Its files.

    Returns:
        The reasons: no authored view, or a file in section 2; empty when the draft can be
        written.

    """
    reasons: list[str] = []
    rels: list[Path] = [p.relative_to(draft) for p in files]
    if _change_kind(draft, files) == "none":
        reasons.append(
            "the draft has no views: the design or documentation work the assessment names has not been authored",
        )
    reasons.extend(
        f"{r.as_posix()} is in section 2, which holds the owner's constraints"
        for r in rels
        if CONSTRAINTS_FOLDER in r.parts
    )
    return reasons


def _draft_warnings(draft: Path, files: list[Path]) -> list[str]:
    """Name the catalog frontmatter keys each authored view lacks.

    Args:
        draft: The draft directory.
        files: Its files.

    Returns:
        One warning per view missing a key; the integration and its review complete them.

    """
    path: Path
    warnings: list[str] = []
    for path in files:
        if path.suffix != ".md":
            continue
        gaps: list[str] = _catalog_gaps(path)
        if gaps:
            warnings.append(
                f"{path.relative_to(draft).as_posix()} lacks catalog frontmatter: {', '.join(gaps)}",
            )
    return warnings


def _existing_views(files: list[Path], current: set[str]) -> list[Path]:
    """Find authored views showing an element the effective version already shows.

    Args:
        files: The authored files.
        current: The elements the effective views show, case-folded.

    Returns:
        The views.

    """
    return [
        path
        for path in files
        if path.suffix == ".md" and any(e.casefold() in current for e in read_catalog(path)["shows"])
    ]


def _target_baseline(
    baseline: str,
    root: Path,
    matrix_snapshot: JsonObject | None,
) -> tuple[BaselineManifest | None, list[str], list[str]]:
    manifest: BaselineManifest | None = None
    baseline_refusals: list[str] = []
    warnings: list[str] = []
    if baseline:
        try:
            survey: object = json.loads(Path(baseline).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return None, [f"baseline unreadable or invalid: {exc}"], []
        facts: contracts.BaselineFacts = baseline_facts(json_object(survey), matrix_snapshot)
        baseline_refusals = facts["errors"]
        warnings.extend(facts["warnings"])
        warnings.extend(f"unresolved baseline, carried as implementation work: {item}" for item in facts["unknowns"])
        manifest = {
            "version": 1,
            "arc42Revision": arc42_revision(root),
            "survey": str(Path(baseline).resolve()),
            "surveySha256": hashlib.sha256(Path(baseline).read_bytes()).hexdigest(),
            "designChanged": bool(facts["designWork"]),
            "documentationChanged": bool(facts["docWork"]),
            "entries": facts["entries"],
            "implementationWork": facts["implementationWork"],
            "approvalFiles": sorted(
                {
                    document["path"]
                    for entry in facts["entries"]
                    if entry["designAction"] == "validate-existing"
                    for document in entry["documents"]
                    if document["lifecycle_state"] == "in-review"
                },
            ),
        }
    return manifest, baseline_refusals, warnings


def _seed_target(source: Path, manifest: BaselineManifest | None, baseline_refusals: list[str]) -> TargetResult:
    noted: BaselineManifest
    if manifest is None:
        reasons: list[str] = baseline_refusals or [
            "no baseline was given to seed the draft from",
        ]
        return {
            "ok": False,
            "refusals": reasons,
            "seeded": [],
            "summary": json_object({"ok": False, "refusals": reasons, "seeded": 0}),
        }
    authored_now: list[Path] = (
        [p for p in _draft_files(source) if p.relative_to(source).as_posix() not in SEED_FILES]
        if source.is_dir()
        else []
    )
    kind: str = _change_case(source, authored_now, manifest)
    noted = {**manifest, "architectureChange": kind, "note": CHANGE_NOTES[kind]}
    out: Path = source / BASELINE_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(noted, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "refusals": [],
        "seeded": [str(out)],
        "architectureChange": kind,
        "summary": {
            "ok": True,
            "refusals": [],
            "seeded": 1,
            "architectureChange": kind,
            "implementationWork": len(manifest["implementationWork"]),
        },
    }


def _publish_target_files(source: Path, dest: Path, files: list[Path], as_delta: list[Path]) -> None:
    path: Path
    out: Path
    text: str
    outcome: str
    if dest.exists():
        shutil.rmtree(dest)
    copies: list[tuple[Path, Path]] = [(p, dest / p.relative_to(source)) for p in files] + [
        (p, dest / DELTA_FOLDER / p.relative_to(source)) for p in as_delta
    ]
    for path, out in copies:
        out.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".md":
            text, outcome = set_state(path.read_text(encoding="utf-8"), IN_REVIEW)
            if outcome == "no-frontmatter":
                text = f"{FENCE}\n{STATE_KEY}: {IN_REVIEW}\n{FENCE}\n{text}"
            out.write_text(text, encoding="utf-8")
        else:
            shutil.copyfile(path, out)


def _publish_target_manifest(dest: Path, manifest: BaselineManifest | None, change: str) -> None:
    noted: BaselineManifest
    if manifest:
        dest.mkdir(parents=True, exist_ok=True)
        noted = {**manifest, "architectureChange": change, "note": CHANGE_NOTES[change]}
        (dest / BASELINE_FILE).write_text(
            json.dumps(noted, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


@dataclass(frozen=True)
class TargetOptions:
    """Explicit configuration for write target."""

    arch_root: str
    subject: str
    forbid: list[str]
    dry_run: bool = False
    baseline: str = ""
    seed: bool = False
    matrix_snapshot: JsonObject | None = None

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate the target configuration before any filesystem operation.

        Raises:
            TypeError: A target field or forbidden-name member has an invalid type.

        """
        message: str = "Invalid architecture target configuration"
        if any(not isinstance(value, str) for value in (self.arch_root, self.subject, self.baseline)):
            raise TypeError(message)
        if not isinstance(self.dry_run, bool) or not isinstance(self.seed, bool):
            raise TypeError(message)
        if not isinstance(self.forbid, list) or any(not isinstance(name, str) for name in self.forbid):
            raise TypeError(message)
        if self.matrix_snapshot is not None and not isinstance(self.matrix_snapshot, dict):
            raise TypeError(message)
        check_type(self.matrix_snapshot, JsonObject | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@dataclass(frozen=True)
class _DraftPlan:
    files: list[Path]
    change: str
    as_delta: list[Path]
    refusals: list[str]
    warnings: list[str]
    written: bool


def _draft_plan(source: Path, root: Path, manifest: BaselineManifest | None) -> _DraftPlan:
    """Measure authored views and their relationship to the effective architecture.

    Returns:
        The measured draft, including explicit refusal and warning evidence.

    """
    warnings: list[str] = []
    authored: list[Path] = (
        [p for p in _draft_files(source) if p.relative_to(source).as_posix() not in SEED_FILES]
        if source.is_dir()
        else []
    )
    draft_written: bool = bool(authored)
    no_author: bool = (
        manifest is not None
        and not (manifest["designChanged"] or manifest["documentationChanged"])
        and not draft_written
    )
    files: list[Path] = [] if no_author else authored
    change: str = _change_case(source, files, manifest)
    draft_refusals: list[str] = (
        _draft_refusals(source, files) if source.is_dir() else [f"the draft {source} is not a directory"]
    )
    if no_author:
        draft_refusals = []
    warnings.extend(_draft_warnings(source, files) if source.is_dir() else [])
    # A new-looking draft whose views show elements the effective version shows is a
    # partial change: those views are its delta.
    as_delta: list[Path] = _existing_views(files, _effective_elements(root)) if change == "new" else []
    if as_delta:
        change = "partial"
        warnings.append(
            f"the draft has no {DELTA_FOLDER}/ views and shows elements the effective "
            f"version shows: {', '.join(p.relative_to(source).as_posix() for p in as_delta)} "
            f"are written to {DELTA_FOLDER}/ as the change",
        )
    return _DraftPlan(files, change, as_delta, draft_refusals, warnings, draft_written)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_target(draft: str, options: TargetOptions) -> TargetResult:
    """Check an approved draft and write it to `target/<subject>/`, every view `in-review`.

    The draft has the arc42 section layout and a `delta/` folder. It is refused, and nothing
    is written, when no folder name is left of the subject, the assessment names design or
    documentation work and no view is authored, a file sits in section 2, or the survey carries
    no assessment. The folder is named by `subject_folder` with dates and the Epic, PRD and
    bead names taken out (`subject_name`), so a display name such as `Company Intelligence`
    writes `target/company-intelligence/`. A draft with no `delta/` whose views show elements
    the effective version shows is a partial change, and those views are written to `delta/`
    as well. A view's missing catalog keys and the assessment's problems are `warnings`; a
    view with no frontmatter is written with `lifecycle_state: in-review`. A target already at
    that path is replaced, so a resumed step writes the same target again.
    With a baseline, `baseline.json` records `arc42Revision`, the revision of the effective
    version (`archrevision.arc42_revision`) the target was designed against, so a later step
    can tell an open target that predates later approvals.

    Args:
        draft: The draft directory.
        options: Validated subject, baseline, matrix and write policy.

    Returns:
        `ok`, the refusals, `subject` (the folder name every later step uses), `subjectName`
        (the subject as given), the target and delta directories, and the files written (or
        that would be written).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    manifest: BaselineManifest | None
    warnings: list[str]
    baseline_refusals: list[str]
    if not (isinstance(draft, str)) or not (isinstance(options, TargetOptions)):
        argument_error: str = "write_target: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path | None = _arch_root(options.arch_root)
    source: Path = Path(draft).resolve()
    if root is None:
        none: list[str] = ["no architecture directory was given"]
        return {
            "ok": False,
            "refusals": none,
            "subjectRefusals": [],
            "subject": subject_folder(options.subject),
            "subjectName": options.subject.strip(),
            "summary": json_object({"ok": False, "refusals": none}),
        }
    folder: str = subject_name(subject_folder(options.subject), options.forbid)
    subject_refusals: list[str] = _subject_refusals(options.subject, folder)
    manifest, baseline_refusals, warnings = _target_baseline(options.baseline, root, options.matrix_snapshot)
    if options.seed:
        return _seed_target(source, manifest, baseline_refusals)
    # A writer's draft is never dropped: when the rounds wrote draft views, the draft is the
    # target even if the survey's assessment lists no design or documentation work.
    # The seeded baseline handoff is not authored: the manifest is rewritten from the survey below.
    plan: _DraftPlan = _draft_plan(source, root, manifest)
    warnings.extend(plan.warnings)
    refusals: list[str] = subject_refusals + plan.refusals + baseline_refusals
    dest: Path = root / TARGET_FOLDER / folder
    if not subject_refusals and not dest.resolve().is_relative_to(
        (root / TARGET_FOLDER).resolve(),
    ):
        subject_refusals = [f"{dest} is outside {root / TARGET_FOLDER}"]
        refusals = subject_refusals + refusals
    delta: list[Path] = [p for p in plan.files if p.relative_to(source).parts[0] == DELTA_FOLDER]
    delta_out: list[Path] = [dest / p.relative_to(source) for p in delta] + [
        dest / DELTA_FOLDER / p.relative_to(source) for p in plan.as_delta
    ]
    report: TargetResult = {
        "summary": {},
        "ok": not refusals,
        "refusals": refusals,
        "subjectRefusals": subject_refusals,
        "subject": folder,
        "subjectName": options.subject.strip(),
        "targetDir": str(dest),
        "deltaDir": str(dest / DELTA_FOLDER),
        "files": [str(dest / p.relative_to(source)) for p in plan.files],
        "deltaFiles": [str(p) for p in delta_out],
        "warnings": warnings,
        "dryRun": options.dry_run,
        "draftWritten": plan.written,
        "architectureChange": plan.change,
        "note": CHANGE_NOTES[plan.change],
    }
    if manifest:
        report.update(
            {
                "designChanged": manifest["designChanged"],
                "documentationChanged": manifest["documentationChanged"],
                "implementationWork": len(manifest["implementationWork"]),
                "approvalFiles": manifest["approvalFiles"],
            },
        )
        report["files"].append(str(dest / BASELINE_FILE))
    # The summary carries what a caller acts on, because `--out` prints only the summary.
    report["summary"] = {
        key: json_object(report)[key]
        for key in (
            "ok",
            "refusals",
            "subjectRefusals",
            "subject",
            "subjectName",
            "targetDir",
            "deltaDir",
            "dryRun",
            "draftWritten",
            "architectureChange",
        )
    } | {
        "files": len(report["files"]),
        "deltaFiles": len(report["deltaFiles"]),
        "warnings": len(warnings),
    }
    if manifest:
        report["summary"].update(
            {
                key: json_object(report)[key]
                for key in (
                    "designChanged",
                    "documentationChanged",
                    "implementationWork",
                    "approvalFiles",
                )
            },
        )
    if refusals or options.dry_run:
        return report
    _publish_target_files(source, dest, plan.files, plan.as_delta)
    _publish_target_manifest(dest, manifest, plan.change)
    return report


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def target_names(target_dir: str, names: list[str]) -> TargetNames | FileError:
    """Find which names an approved target's files mention, as whole words.

    A step that may create only the repositories the target names checks each name it
    created against the target's text.

    Args:
        target_dir: The `target/<subject>/` folder.
        names: The names to look for.

    Returns:
        Each name the target mentions with the files that mention it, and the names it does
        not mention, or `error` when the folder does not exist.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    raw: str
    if not (isinstance(target_dir, str)) or not (isinstance(names, list)):
        argument_error: str = "target_names: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    folder: Path = Path(target_dir)
    if not folder.is_dir():
        return {"error": f"the target folder {folder} does not exist"}
    texts: dict[str, str] = {
        str(p): p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(folder.rglob("*"))
        if p.is_file() and not p.name.endswith(SKIPPED_SUFFIXES)
    }
    named: dict[str, list[str]] = {}
    unnamed: list[str] = []
    for raw in names:
        name: str = str(raw).strip()
        if not name:
            continue
        word: re.Pattern[str] = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])")
        hits: list[str] = [path for path, text in texts.items() if word.search(text)]
        if hits:
            named[name] = hits
        else:
            unnamed.append(name)
    return {
        "targetDir": str(folder),
        "named": named,
        "unnamed": unnamed,
        "summary": {"named": len(named), "unnamed": len(unnamed)},
    }


def _change_of(baseline_file: Path, delta_root: Path) -> str:
    """Read how a written target deduplicates its documents (see CHANGE_NOTES).

    Args:
        baseline_file: The target's baseline handoff.
        delta_root: The `delta/` folder beside it.

    Returns:
        The recorded `architectureChange`; a target written before it was recorded is
        `partial` when it has a `delta/` folder and `none` otherwise.

    """
    recorded: contracts.JsonValue = None
    try:
        raw: object = json.loads(baseline_file.read_text(encoding="utf-8"))
    except OSError, ValueError:
        raw = None
    if isinstance(raw, dict):
        value: JsonObject = json_object(raw)
        recorded = value.get("architectureChange")
    if isinstance(recorded, str) and recorded in CHANGE_NOTES and recorded != "pending":
        return recorded
    return "partial" if delta_root.is_dir() else "none"


@dataclass(frozen=True)
class _SavedAssessment:
    design_changed: bool
    documentation_changed: bool
    documents: tuple[str, ...]
    survey: str
    survey_sha256: str


def _assessment_document_paths(entries: contracts.JsonValue) -> tuple[str, ...]:
    """Validate the saved assessment's document references.

    Returns:
        The cited document paths.

    Raises:
        TypeError: An assessment entry or document reference is malformed.

    """
    entry: bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None
    document: bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None
    message: str = "baseline handoff has invalid assessment document references"
    if not isinstance(entries, list):
        raise TypeError(message)
    paths: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise TypeError(message)
        documents: contracts.JsonValue = entry.get("documents", [])
        if not isinstance(documents, list):
            raise TypeError(message)
        for document in documents:
            if not isinstance(document, dict) or not isinstance(document.get("path"), str):
                raise TypeError(message)
            path: contracts.JsonValue = document["path"]
            if not isinstance(path, str):
                raise TypeError(message)
            paths.append(path)
    return tuple(paths)


def _saved_assessment(path: Path) -> _SavedAssessment:
    """Decode a saved handoff at the filesystem boundary.

    Returns:
        A validated immutable projection of fields consumed by delta planning.

    Raises:
        TypeError: A persisted field has the wrong shape.

    """
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    value: JsonObject = json_object(raw)
    design: contracts.JsonValue = value.get("designChanged", False)
    documentation: contracts.JsonValue = value.get("documentationChanged", False)
    survey: contracts.JsonValue = value.get("survey", "")
    digest: contracts.JsonValue = value.get("surveySha256", "")
    message: str = "baseline handoff has invalid assessment metadata"
    if not isinstance(design, bool) or not isinstance(documentation, bool):
        raise TypeError(message)
    if not isinstance(survey, str) or not isinstance(digest, str):
        raise TypeError(message)
    return _SavedAssessment(design, documentation, _assessment_document_paths(value.get("entries")), survey, digest)


def _delta_assessment(path: Path, refusals: list[str], warnings: list[str]) -> _SavedAssessment | None:
    """Reject an invalid historical handoff and retain the diagnostic.

    Returns:
        The saved assessment, or None when absent or rejected.

    """
    if not path.is_file():
        return None
    try:
        assessment: _SavedAssessment = _saved_assessment(path)
    except (OSError, ValueError, TypeError) as exc:
        refusals.append(f"invalid baseline handoff: {exc}")
        return None
    survey: Path = Path(assessment.survey)
    if survey.is_file() and hashlib.sha256(survey.read_bytes()).hexdigest() != assessment.survey_sha256:
        warnings.append(
            f"the survey {survey} changed since the target was written; "
            "the assessment recorded with the target is used",
        )
    return assessment


def _delta_catalog(views: list[Path], warnings: list[str]) -> tuple[dict[str, list[str]], list[DeltaView]]:
    """Collect catalog elements and their source views.

    Returns:
        Element ownership and view metadata from the supplied paths.

    """
    view: Path
    element: str
    shown: dict[str, list[str]] = {}
    listed: list[DeltaView] = []
    for view in views:
        catalog: contracts.CatalogRecord = read_catalog(view)
        listed.append({"path": str(view), **catalog})
        elements: list[str] = catalog["shows"] or ([catalog["subject"]] if catalog["subject"] else [])
        if not catalog["shows"]:
            warnings.append(
                f"{view} names no element in `shows`"
                + (f"; its subject {catalog['subject']} is the element" if elements else ""),
            )
        for element in elements:
            shown.setdefault(element, []).append(str(view))
    return shown, listed


@dataclass(frozen=True)
class _DeltaScope:
    change: str
    target: Path
    baseline: Path
    matrix: JsonObject | None


def _catalog_sort_key(pair: tuple[str, list[str]]) -> str:
    """Normalize a catalog item's name for deterministic ordering.

    Returns:
        The canonical element identifier.

    """
    return element_id(pair[0])


def _implementation_gaps(
    scope: _DeltaScope,
    manifest: _SavedAssessment | None,
    items: list[DeltaItem],
    refusals: list[str],
) -> None:
    """Append unsatisfied effective-view elements to the current build scope."""
    element: str
    element_views: list[str]
    # Build scope is catalog elements, not survey capability labels or code judgments.
    present: set[str] = {element_id(item["element"]) for item in items}
    documents: list[JsonObject]
    if scope.change == "partial":
        documents = [
            {"path": str(path)}
            for path in _draft_files(scope.target)
            if path.suffix == ".md" and DELTA_FOLDER not in path.relative_to(scope.target).parts
        ]
    elif scope.change == "none" and manifest:
        documents = [{"path": path} for path in manifest.documents]
    else:
        documents = []
    try:
        future: dict[str, list[str]] = catalog_elements(documents)
    except (OSError, UnicodeError) as exc:
        future = {}
        refusals.append(f"cannot read future-set catalog: {exc}")
    for element, element_views in sorted(
        future.items(),
        key=_catalog_sort_key,
    ):
        key: str = element_id(element)
        row: dict[str, contracts.JsonValue] = row_of(scope.matrix, element)
        if key in present or (scope.change == "partial" and satisfied(scope.matrix or {}, row)):
            continue
        items.append(
            {
                "id": f"D{len(items) + 1}",
                "element": element,
                "kind": "implementation-gap",
                "views": sorted(set(element_views)),
                "state": check_type(row.get("state", "unknown"), str),
                "repository": check_type(row.get("repository"), str | None),
                "baseline": str(scope.baseline),
            },
        )
        present.add(key)


def _missing_delta(root: Path) -> DeltaResult:
    """Describe an absent or invalid target directory.

    Returns:
        The failed delta result with its exact refusal.

    """
    refusals: list[str] = [f"{root} is not the {DELTA_FOLDER}/ path of a written target"]
    return {"ok": False, "refusals": refusals, "summary": {"ok": False, "refusals": list(refusals)}}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def delta_items(
    delta_dir: str,
    *,
    with_closure: bool = True,
    matrix_snapshot: JsonObject | None = None,
) -> DeltaResult:
    """List the build items of a written target, one item per element.

    The documents deduplicate as CHANGE_NOTES describes. With a partial change an item is one
    element named in the `shows` frontmatter of a `delta/` view; with an entirely new
    architecture the target views are the delta, so their elements are the items; with no
    architecture change there is no delta and no view item. Items are numbered `D1`, `D2` ...
    in element-name order, so the same target always yields the same ids. The implementation
    gaps of the future set against the element matrix follow, then,
    when the target holds a checked `closure.json`, one `prerequisite` item per element the
    work rests on that is not built and current; every item then carries `requires`, the ids
    of the items it needs built first. Runs no `bd` command and writes nothing.

    Args:
        delta_dir: The `target/<subject>/delta/` path; the folder exists only for a partial
            change.
        with_closure: Merge the target's `closure.json`; False lists the root items alone.
        matrix_snapshot: The current element matrix used to resolve implementation gaps.

    Returns:
        `ok`, the refusals, `architectureChange` and its note, the views, and the items.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    closure_refusals: list[str]
    listed: list[DeltaView]
    shown: dict[str, list[str]]
    if (
        not (isinstance(delta_dir, str))
        or not (isinstance(with_closure, bool))
        or not (isinstance(matrix_snapshot, dict) or matrix_snapshot is None)
    ):
        argument_error: str = "delta_items: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path = Path(delta_dir).resolve()
    target: Path = root.parent
    if root.name != DELTA_FOLDER or not target.is_dir():
        return _missing_delta(root)
    baseline_file: Path = target / BASELINE_FILE
    if not baseline_file.is_file():
        baseline_file = root / BASELINE_FILE
    change: str = _change_of(baseline_file, root)
    if root.is_dir():
        views: list[Path] = [p for p in _draft_files(root) if p.suffix == ".md"]
    elif change == "new":
        views = [
            p for p in _draft_files(target) if p.suffix == ".md" and p.relative_to(target).parts[0] != DELTA_FOLDER
        ]
    else:
        views = []
    refusals: list[str] = []
    warnings: list[str] = []
    shown, listed = _delta_catalog(views, warnings)
    manifest: _SavedAssessment | None = _delta_assessment(baseline_file, refusals, warnings)
    if not views and (not manifest or manifest.design_changed or manifest.documentation_changed):
        warnings.append(
            f"{target} holds no view, and its baseline handoff "
            + ("is missing" if not manifest else "names design or documentation work"),
        )
    items: list[DeltaItem] = [
        {"id": f"D{n}", "element": element, "views": shown[element]}
        for n, element in enumerate(sorted(shown, key=str.casefold), start=1)
    ]
    _implementation_gaps(_DeltaScope(change, target, baseline_file, matrix_snapshot), manifest, items, refusals)
    if change == "none" and not items:
        refusals.append(
            "the unchanged architecture's cited effective views name no elements",
        )
    prerequisites: int = 0
    if with_closure and not refusals:
        items, closure_refusals, prerequisites = archclosure.merge_closure(root, items)
        refusals += closure_refusals
    baseline_validated: bool = manifest is not None and not refusals
    return {
        "ok": not refusals,
        "refusals": refusals,
        "warnings": warnings,
        "deltaDir": str(root),
        "deltaExists": root.is_dir(),
        "targetDir": str(target),
        "architectureChange": change,
        "note": CHANGE_NOTES[change],
        "views": listed,
        "items": items,
        "baselineValidated": baseline_validated,
        "implementationWork": len(items) if baseline_validated else None,
        "implementationComplete": baseline_validated and not items,
        "prerequisites": prerequisites,
        "summary": {
            "ok": not refusals,
            "refusals": list(refusals),
            "warnings": len(warnings),
            "views": len(listed),
            "items": len(items),
            "architectureChange": change,
            "deltaExists": root.is_dir(),
            "baselineValidated": baseline_validated,
            "implementationWork": len(items) if baseline_validated else None,
            "implementationComplete": baseline_validated and not items,
            "prerequisites": prerequisites,
        },
    }


@git_result
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def remove_target(
    arch_root: str,
    target_dir: str,
    *,
    message: str,
    execution_id: str = "",
) -> TargetRemoval | Refusal:
    """Delete one `target/<subject>/` folder and commit the removal.

    The folder must be a direct child of `<arch_root>/target/`. Its tracked files are
    removed with `git rm` and committed on their own (`git commit -- <folder>`), so changes
    staged elsewhere in the repository stay out of the commit; files git does not track are
    deleted from disk. A folder already gone is reported, not refused.

    Args:
        arch_root: The architecture directory holding `target/`.
        target_dir: The target folder to remove.
        message: The commit message.
        execution_id: The pipeline execution identity recorded on the commit.

    Returns:
        `ok`, the refusals, whether the folder was removed, the commit, and git's output.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(arch_root, str))
        or not (isinstance(target_dir, str))
        or not (isinstance(message, str))
        or not (isinstance(execution_id, str))
    ):
        argument_error: str = "remove_target: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path | None = _arch_root(arch_root)
    if root is None:
        none: list[str] = ["no architecture directory was given"]
        return {
            "ok": False,
            "refusals": none,
            "summary": {"ok": False, "refusals": none},
        }
    folder: Path = Path(target_dir).resolve()
    targets: Path = (root / TARGET_FOLDER).resolve()
    if folder.parent != targets:
        why: list[str] = [f"{folder} is not a subject folder directly under {targets}"]
        return {"ok": False, "refusals": why, "summary": {"ok": False, "refusals": why}}
    report: TargetRemoval = {
        "ok": True,
        "refusals": [],
        "targetDir": str(folder),
        "removed": False,
        "summary": {"ok": True, "commit": None},
        "commit": None,
    }
    pending: str = run_git(
        root,
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=D",
        "--",
        str(folder),
        execution_id=execution_id,
    ).stdout.strip()
    if not folder.exists() and not pending:
        report["removed"] = False
        report["summary"] = {"ok": True, "removed": False, "commit": None}
        return report

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def git(*argv: str) -> subprocess.CompletedProcess[str]:
        return run_git(root, *argv, execution_id=execution_id)

    tracked: subprocess.CompletedProcess[str] = git("ls-files", "--", str(folder))
    if tracked.stdout.strip():
        git("rm", "-r", "-q", "--", str(folder))
    if folder.exists():
        shutil.rmtree(folder)
    if tracked.stdout.strip() or pending:
        git("commit", "-q", "-m", message, "--", str(folder))
        head: subprocess.CompletedProcess[str] = git("rev-parse", "--short", "HEAD")
        report["commit"] = head.stdout.strip() or None
    report["removed"] = True
    report["summary"] = {"ok": True, "removed": True, "commit": report["commit"]}
    return report


def _refused(why: list[str]) -> Refusal:
    return {"ok": False, "refusals": why, "summary": {"ok": False, "refusals": why}}


def _remove_empty_subjects(built: Path, present: list[Path]) -> None:
    """Remove only empty directories below the affected built subjects."""
    folder: Path
    sub: Path
    for folder in sorted({built / f.relative_to(built).parts[0] for f in present}):
        for sub in sorted((d for d in folder.rglob("*") if d.is_dir()), reverse=True):
            if not any(sub.iterdir()):
                sub.rmdir()
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()


@git_result
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def remove_built(
    arch_root: str,
    files: list[str],
    *,
    message: str,
    execution_id: str = "",
) -> BuiltRemoval | Refusal:
    """Delete built files the effective version now matches, and commit the removal.

    Every file must sit inside a subject folder under `<arch_root>/built/`. Tracked files are
    removed with `git rm` and committed on their own (`git commit -- <paths>`), so changes
    staged elsewhere in the repository stay out of the commit; files git does not track are
    deleted from disk. A subject folder left empty is deleted. A file already gone is
    reported, not refused.

    Args:
        arch_root: The architecture directory holding `built/`.
        files: The built files to remove, as absolute paths.
        message: The commit message.
        execution_id: The pipeline execution identity recorded on the commit.

    Returns:
        `ok`, the refusals, the files removed and already gone, the commit, and git's output.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    f: Path
    if (
        not (isinstance(arch_root, str))
        or not (isinstance(files, list))
        or not (isinstance(message, str))
        or not (isinstance(execution_id, str))
    ):
        argument_error: str = "remove_built: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path | None = _arch_root(arch_root)
    if root is None:
        return _refused(["no architecture directory was given"])
    built: Path = (root / BUILT_FOLDER).resolve()
    wanted: list[Path] = [Path(str(f).strip()).resolve() for f in files if str(f).strip()]
    if not wanted:
        return _refused(["no built file was named"])
    outside: list[str] = [
        str(f) for f in wanted if not f.is_relative_to(built) or len(f.relative_to(built).parts) < MIN_BUILT_PATH_PARTS
    ]
    if outside:
        return _refused(
            [f"not inside a subject folder under {built}: {', '.join(outside)}"],
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def git(*argv: str) -> subprocess.CompletedProcess[str]:
        return run_git(root, *argv, execution_id=execution_id)

    present: list[Path] = [f for f in wanted if f.exists()]
    gone: list[str] = [str(f) for f in wanted if not f.exists()]
    report: BuiltRemoval = {
        "ok": True,
        "refusals": [],
        "removed": [],
        "summary": {"ok": True, "commit": None},
        "gone": gone,
        "commit": None,
    }
    tracked: list[str] = [str(path) for path in present if git("ls-files", "--", str(path)).stdout.strip()]
    if tracked:
        git("rm", "-q", "--", *tracked)
    for f in present:
        if f.exists():
            f.unlink()
        report["removed"].append(str(f))
    _remove_empty_subjects(built, present)
    pending: str = git(
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=D",
        "--",
        *(str(f) for f in wanted),
    ).stdout.strip()
    if tracked or pending:
        git("commit", "-q", "-m", message, "--", *(str(f) for f in wanted))
        head: subprocess.CompletedProcess[str] = git("rev-parse", "--short", "HEAD")
        report["commit"] = head.stdout.strip() or None
    report["summary"] = {
        "ok": True,
        "removed": len(report["removed"]),
        "gone": len(gone),
        "commit": report["commit"],
    }
    return report


@git_result
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def commit_integration(
    arch_root: str,
    files: list[str],
    *,
    message: str,
    execution_id: str = "",
) -> IntegrationCommit | Refusal:
    """Commit the architecture files an integration changed, and push the branch.

    Every file must sit under `arch_root`. Only these paths are staged (`git add -A --
    <paths>`, so a deleted file is staged as a deletion) and committed (`git commit --
    <paths>`), so other changes in the repository stay out of the commit. The commit is
    pushed to `origin` on the branch it was made on. Paths with nothing to commit give no
    commit; the branch is still pushed when it is ahead of `origin`, so a commit an earlier
    run made and did not push reaches the remote.

    Args:
        arch_root: The architecture directory the files sit under.
        files: The files the integration changed, created or deleted, as absolute paths.
        message: The commit message.
        execution_id: The pipeline execution identity recorded on the commit.

    Returns:
        `ok`, the refusals, the paths committed, the branch, the commit, and whether it was
        pushed.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(arch_root, str))
        or not (isinstance(files, list))
        or not (isinstance(message, str))
        or not (isinstance(execution_id, str))
    ):
        argument_error: str = "commit_integration: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    root: Path | None = _arch_root(arch_root)
    if root is None:
        return _refused(["no architecture directory was given"])
    wanted: list[str] = sorted(
        {str(Path(str(f).strip()).resolve()) for f in files if str(f).strip()},
    )
    if not wanted:
        return _refused(["no integrated file was named"])
    outside: list[str] = [f for f in wanted if not Path(f).is_relative_to(root)]
    if outside:
        return _refused([f"not under {root}: {', '.join(outside)}"])

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def git(*argv: str) -> subprocess.CompletedProcess[str]:
        return run_git(root, *argv, execution_id=execution_id)

    branch: str = git("symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if not branch:
        return _refused([f"the repository holding {root} is not on a branch"])
    report: IntegrationCommit = {
        "ok": True,
        "refusals": [],
        "files": wanted,
        "branch": branch,
        "commit": None,
        "pushed": False,
        "summary": {"ok": True, "commit": None},
    }
    git("add", "-A", "--", *wanted)
    staged: subprocess.CompletedProcess[str] = git("diff", "--cached", "--name-only", "--", *wanted)
    if staged.stdout.strip():
        git("commit", "-q", "-m", message, "--", *wanted)
        report["commit"] = git("rev-parse", "--short", "HEAD").stdout.strip() or None
    ahead: subprocess.CompletedProcess[str] = git("rev-list", "--count", f"origin/{branch}..HEAD")
    if ahead.returncode == 0 and ahead.stdout.strip() == "0":
        report["summary"] = {
            "ok": True,
            "commit": report["commit"],
            "pushed": False,
            "branch": branch,
        }
        return report
    git("push", "-q", "origin", branch)
    report["pushed"] = True
    report["summary"] = {
        "ok": True,
        "commit": report["commit"],
        "pushed": True,
        "branch": branch,
    }
    return report
