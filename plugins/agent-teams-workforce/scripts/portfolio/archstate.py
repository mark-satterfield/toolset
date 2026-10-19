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
`depscore.py arch-snapshot` runs `snapshot_tree`, which fingerprints every file under the
architecture directory (`arc42/`, `detailed/`, `target/`, `built/` and the rest), so a step
measures what its sessions wrote.
`depscore.py arch-built-remove` runs `remove_built`, which deletes the `built/<element>/` files
the effective version has been corrected to match, and commits the removal.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed Git argv without shell execution.
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import _hashlib

from archcatalog import split_frontmatter
from archgit import git_result, run_git
from contracts import (
    BuiltRemoval,
    ConstraintRestore,
    ConstraintSnapshot,
    FileError,
    JsonObject,
    PromotionReport,
    Refusal,
    StateReport,
    TreeDifference,
    TreeSnapshot,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

# The target report contract is generated into the artifact-handoff skill, its one definition;
# the path is declared here rather than inherited from another import.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))

# isort: split
from matrixsync import ARC42_FOLDER, BUILT_FOLDER, LIFECYCLE_EFFECTIVE
from target_contract import KEY_LIFECYCLE_STATE

STATE_KEY: Final = KEY_LIFECYCLE_STATE
EFFECTIVE: Final = LIFECYCLE_EFFECTIVE
FENCE = "---"
MIN_BUILT_PATH_PARTS = 2
EFFECTIVE_FOLDER = ARC42_FOLDER
CONSTRAINTS_FOLDER = "02-architecture-constraints"


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
    """Fingerprint every file under the architecture directory, every version included.

    A step that must not write in the architecture, or must write only where it says it did,
    takes one snapshot before its sessions run and one after; the difference is what they
    wrote, measured rather than reported.

    Args:
        arch_root: The architecture directory.

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
    files: list[Path] = sorted(p for p in root.rglob("*") if p.is_file())
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
