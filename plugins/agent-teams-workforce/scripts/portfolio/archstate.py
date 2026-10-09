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
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from archgit import git_result, run_git
from archmatrix import catalog_elements, element_id, row_of, satisfied
from archrevision import arc42_revision

STATE_KEY = "lifecycle_state"
EFFECTIVE = "effective"
IN_REVIEW = "in-review"
FENCE = "---"
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


def _in_constraints(path: Path) -> bool:
    """Tell whether a path lies in section 2 of the effective version.

    Args:
        path: A resolved path.

    Returns:
        True when the path has `arc42/02-architecture-constraints` among its parts.
    """
    parts = path.parts
    return any(
        parts[i] == EFFECTIVE_FOLDER and parts[i + 1] == CONSTRAINTS_FOLDER
        for i in range(len(parts) - 1)
    )


def promote(files: list[str], *, arch_root: str | None, reviewed: list[str]) -> dict:
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
        if _in_constraints(resolved):
            report["refused"].append(
                {
                    "path": name,
                    "reason": "in section 2, which holds the owner's constraints",
                }
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


def snapshot_constraints(arch_root: str, *, keep: bool = False) -> dict:
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
    """
    root = _arch_root(arch_root)
    if root is None:
        return {"error": "no architecture directory was given"}
    folder = root / EFFECTIVE_FOLDER / CONSTRAINTS_FOLDER
    files = (
        sorted(p for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else []
    )
    each, digest = _digest(files, folder) if files else ({}, "")
    git = subprocess.run(
        [
            "git",
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
    out = {
        "folder": str(folder),
        "exists": folder.is_dir(),
        "files": each,
        "digest": digest,
        "gitStatus": git.stdout.splitlines() if git.returncode == 0 else [],
        "gitError": git.stderr.strip() if git.returncode != 0 else "",
        "summary": {"files": len(each), "digest": digest},
    }
    if keep:
        kept = Path(tempfile.mkdtemp(prefix="arch-constraints-"))
        for path in files:
            dest = kept / path.relative_to(folder)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        out["kept"] = str(kept)
    return out


def restore_constraints(arch_root: str, kept: str) -> dict:
    """Put section 2 back as `snapshot_constraints(keep=True)` copied it.

    A session that wrote under section 2 has already failed the step; this undoes the write
    so the owner's constraints stand as the owner left them. Files the copy does not hold are
    deleted, and every file it holds is written back where its content differs.

    Args:
        arch_root: The architecture directory holding `arc42/`.
        kept: The directory `snapshot_constraints` named in `kept`.

    Returns:
        The files written back and the files deleted, or `error` when the copy is missing.
    """
    root = _arch_root(arch_root)
    if root is None:
        return {"error": "no architecture directory was given"}
    source = Path(kept)
    if not source.is_dir():
        return {"error": f"the copy of section 2 at {source} does not exist"}
    folder = root / EFFECTIVE_FOLDER / CONSTRAINTS_FOLDER
    saved = {
        p.relative_to(source).as_posix(): p for p in source.rglob("*") if p.is_file()
    }
    current = (
        {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}
        if folder.is_dir()
        else {}
    )
    deleted = []
    for rel, path in sorted(current.items()):
        if rel not in saved:
            path.unlink()
            deleted.append(str(path))
    written = []
    for rel, path in sorted(saved.items()):
        dest = folder / rel
        if dest.is_file() and dest.read_bytes() == path.read_bytes():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        written.append(str(dest))
    for directory in sorted(
        (p for p in folder.rglob("*") if p.is_dir()) if folder.is_dir() else [],
        key=lambda p: len(p.parts),
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


def snapshot_tree(arch_root: str) -> dict:
    """Fingerprint every file of every version: `arc42/`, `target/` and `built/`.

    A step that must not write in the architecture, or must write only where it says it did,
    takes one snapshot before its sessions run and one after; the difference is what they
    wrote, measured rather than reported.

    Args:
        arch_root: The architecture directory holding the version folders.

    Returns:
        The root, each file's sha256 by path relative to the root, and one digest over all of
        them.
    """
    root = _arch_root(arch_root)
    if root is None:
        return {"error": "no architecture directory was given"}
    if not root.is_dir():
        return {"error": f"the architecture directory {root} does not exist"}
    files = sorted(
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


def tree_diff(was: dict, now: dict) -> dict:
    """Name the files created, changed and deleted between two `snapshot_tree` results.

    Args:
        was: The earlier fingerprint, as `snapshot_tree` returned or `--save` wrote it.
        now: The later fingerprint.

    Returns:
        The created, changed and deleted files, each relative to the architecture root.
    """
    before = was.get("files") if isinstance(was.get("files"), dict) else {}
    after = now.get("files") if isinstance(now.get("files"), dict) else {}
    return {
        "created": sorted(k for k in after if k not in before),
        "changed": sorted(k for k in after if k in before and before[k] != after[k]),
        "deleted": sorted(k for k in before if k not in after),
    }


def subject_folder(subject: str) -> str:
    """Derive the `<subject>` folder name from a subject as anyone names it.

    The folder name is the subject folded to ASCII, lower-cased, with every run of characters
    other than `a-z` and `0-9` replaced by one hyphen and no hyphen at either end:
    `Company Intelligence` is `company-intelligence`. A folder name maps to itself.

    Args:
        subject: The subject, as a display name or already as a folder name.

    Returns:
        The folder name; empty when the subject has no letter or digit.
    """
    ascii_only = (
        unicodedata.normalize("NFKD", subject).encode("ascii", "ignore").decode("ascii")
    )
    return SUBJECT_SEPARATOR.sub("-", ascii_only.lower()).strip("-")


def subject_name(folder: str, forbid: list[str]) -> str:
    """The folder name with every date and every name a subject never carries taken out.

    Args:
        folder: A folder name, from `subject_folder`.
        forbid: Names a subject never carries (the Epic, the PRD, the bead prefix).

    Returns:
        The folder name; empty when nothing is left.
    """
    name = DATE_IN_NAME.sub("-", folder)
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
            )
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


def _effective_elements(root: Path) -> set[str]:
    """Name every element a canonical arc42 view shows: the current set.

    Args:
        root: The architecture directory holding `arc42/`.

    Returns:
        The element names, case-folded.
    """
    arc42 = root / "arc42"
    if not arc42.is_dir():
        return set()
    return {
        element.casefold()
        for view in arc42.rglob("*.md")
        if CONSTRAINTS_FOLDER not in view.relative_to(arc42).parts
        for element in _catalog(view)["shows"]
    }


def _change_case(draft: Path, files: list[Path], manifest: dict | None) -> str:
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
    kind = _change_kind(draft, files)
    if (
        kind == "none"
        and manifest
        and (manifest["designChanged"] or manifest["documentationChanged"])
    ):
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
    rels = [p.relative_to(draft) for p in files if p.suffix == ".md"]
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
    reasons = []
    rels = [p.relative_to(draft) for p in files]
    if _change_kind(draft, files) == "none":
        reasons.append(
            "the draft has no views: the design or documentation work the assessment "
            "names has not been authored"
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
    warnings = []
    for path in files:
        if path.suffix != ".md":
            continue
        gaps = _catalog_gaps(path)
        if gaps:
            warnings.append(
                f"{path.relative_to(draft).as_posix()} lacks catalog frontmatter: "
                f"{', '.join(gaps)}"
            )
    return warnings


def _existing_views(files: list[Path], current: set[str]) -> list[Path]:
    """The authored views that show an element the effective version already shows.

    Args:
        files: The authored files.
        current: The elements the effective views show, case-folded.

    Returns:
        The views.
    """
    return [
        path
        for path in files
        if path.suffix == ".md"
        and any(e.casefold() in current for e in _catalog(path)["shows"])
    ]


def write_target(
    draft: str,
    *,
    arch_root: str,
    subject: str,
    forbid: list[str],
    dry_run: bool = False,
    baseline: str = "",
    seed: bool = False,
    matrix_snapshot: dict | None = None,
) -> dict:
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
        arch_root: The architecture directory holding `target/`.
        subject: The subject the target describes, as a display name or a folder name.
        forbid: Names a subject never carries (the Epic, the PRD, the bead prefix).
        dry_run: Check only; write nothing.
        seed: Write only the baseline handoff (`baseline.json` and `delta/baseline.json`) into
            the draft, so every review has a target and a delta to read, then stop. Seeded
            files are not authored views: they do not count as a written draft.

    Returns:
        `ok`, the refusals, `subject` (the folder name every later step uses), `subjectName`
        (the subject as given), the target and delta directories, and the files written (or
        that would be written).
    """
    root = _arch_root(arch_root)
    source = Path(draft).resolve()
    if root is None:
        none = ["no architecture directory was given"]
        return {
            "ok": False,
            "refusals": none,
            "subjectRefusals": [],
            "subject": subject_folder(subject),
            "subjectName": subject.strip(),
            "summary": {"ok": False, "refusals": none},
        }
    folder = subject_name(subject_folder(subject), forbid)
    subject_refusals = _subject_refusals(subject, folder)
    manifest = None
    baseline_refusals = []
    warnings: list[str] = []
    if baseline:
        from archbaseline import baseline_facts

        try:
            survey = json.loads(Path(baseline).read_text(encoding="utf-8"))
            facts = baseline_facts(survey, matrix_snapshot)
            baseline_refusals = facts["errors"]
            warnings.extend(facts["warnings"])
            warnings.extend(
                f"unresolved baseline, carried as implementation work: {item}"
                for item in facts["unknowns"]
            )
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
                    }
                ),
            }
        except (OSError, ValueError, TypeError, KeyError) as exc:
            baseline_refusals = [f"baseline unreadable or invalid: {exc}"]
    if seed:
        if manifest is None:
            reasons = baseline_refusals or [
                "no baseline was given to seed the draft from"
            ]
            return {
                "ok": False,
                "refusals": reasons,
                "seeded": [],
                "summary": {"ok": False, "refusals": reasons, "seeded": 0},
            }
        authored_now = (
            [
                p
                for p in _draft_files(source)
                if p.relative_to(source).as_posix() not in SEED_FILES
            ]
            if source.is_dir()
            else []
        )
        kind = _change_case(source, authored_now, manifest)
        noted = {**manifest, "architectureChange": kind, "note": CHANGE_NOTES[kind]}
        out = source / BASELINE_FILE
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(noted, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
    # A writer's draft is never dropped: when the rounds wrote draft views, the draft is the
    # target even if the survey's assessment lists no design or documentation work.
    # The seeded baseline handoff is not authored: the manifest is rewritten from the survey below.
    authored = (
        [
            p
            for p in _draft_files(source)
            if p.relative_to(source).as_posix() not in SEED_FILES
        ]
        if source.is_dir()
        else []
    )
    draft_written = bool(authored)
    no_author = (
        bool(manifest)
        and not (manifest["designChanged"] or manifest["documentationChanged"])
        and not draft_written
    )
    files = [] if no_author else authored
    change = _change_case(source, files, manifest)
    draft_refusals = (
        _draft_refusals(source, files)
        if source.is_dir()
        else [f"the draft {source} is not a directory"]
    )
    if no_author:
        draft_refusals = []
    warnings.extend(_draft_warnings(source, files) if source.is_dir() else [])
    # A new-looking draft whose views show elements the effective version shows is a
    # partial change: those views are its delta.
    as_delta = (
        _existing_views(files, _effective_elements(root)) if change == "new" else []
    )
    if as_delta:
        change = "partial"
        warnings.append(
            f"the draft has no {DELTA_FOLDER}/ views and shows elements the effective "
            f"version shows: {', '.join(p.relative_to(source).as_posix() for p in as_delta)} "
            f"are written to {DELTA_FOLDER}/ as the change"
        )
    refusals = subject_refusals + draft_refusals + baseline_refusals
    dest = root / TARGET_FOLDER / folder
    if not subject_refusals and not dest.resolve().is_relative_to(
        (root / TARGET_FOLDER).resolve()
    ):
        subject_refusals = [f"{dest} is outside {root / TARGET_FOLDER}"]
        refusals = subject_refusals + refusals
    delta = [p for p in files if p.relative_to(source).parts[0] == DELTA_FOLDER]
    delta_out = [dest / p.relative_to(source) for p in delta] + [
        dest / DELTA_FOLDER / p.relative_to(source) for p in as_delta
    ]
    report: dict = {
        "ok": not refusals,
        "refusals": refusals,
        "subjectRefusals": subject_refusals,
        "subject": folder,
        "subjectName": subject.strip(),
        "targetDir": str(dest),
        "deltaDir": str(dest / DELTA_FOLDER),
        "files": [str(dest / p.relative_to(source)) for p in files],
        "deltaFiles": [str(p) for p in delta_out],
        "warnings": warnings,
        "dryRun": dry_run,
        "draftWritten": draft_written,
        "architectureChange": change,
        "note": CHANGE_NOTES[change],
    }
    if manifest:
        report.update(
            {
                "designChanged": manifest["designChanged"],
                "documentationChanged": manifest["documentationChanged"],
                "implementationWork": len(manifest["implementationWork"]),
                "approvalFiles": manifest["approvalFiles"],
            }
        )
        report["files"].append(str(dest / BASELINE_FILE))
    # The summary carries what a caller acts on, because `--out` prints only the summary.
    report["summary"] = {
        key: report[key]
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
                key: report[key]
                for key in (
                    "designChanged",
                    "documentationChanged",
                    "implementationWork",
                    "approvalFiles",
                )
            }
        )
    if refusals or dry_run:
        return report
    if dest.exists():
        shutil.rmtree(dest)
    copies = [(p, dest / p.relative_to(source)) for p in files] + [
        (p, dest / DELTA_FOLDER / p.relative_to(source)) for p in as_delta
    ]
    for path, out in copies:
        out.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".md":
            text, outcome = _set_state(path.read_text(encoding="utf-8"), IN_REVIEW)
            if outcome == "no-frontmatter":
                text = f"{FENCE}\n{STATE_KEY}: {IN_REVIEW}\n{FENCE}\n{text}"
            out.write_text(text, encoding="utf-8")
        else:
            shutil.copyfile(path, out)
    if manifest:
        dest.mkdir(parents=True, exist_ok=True)
        noted = {**manifest, "architectureChange": change, "note": CHANGE_NOTES[change]}
        (dest / BASELINE_FILE).write_text(
            json.dumps(noted, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return report


def _unquote(value: str) -> str:
    """Strip one pair of matching YAML quotes from a scalar.

    Args:
        value: The scalar as written.

    Returns:
        The scalar without its quotes.
    """
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _catalog(path: Path) -> dict:
    """Read a view's catalog frontmatter: `view_type`, `scope`, `subject` and `shows`.

    `shows` is read as a block list (`- name` lines) or a flow list (`[a, b]`).

    Args:
        path: The view file.

    Returns:
        The four keys; a missing scalar is an empty string and a missing list is empty.
    """
    out: dict = {"view_type": "", "scope": "", "subject": "", "shows": []}
    split = _split_frontmatter(path.read_text(encoding="utf-8"))
    if split is None:
        return out
    lines, start, close = split
    idx = start
    while idx < close:
        line = lines[idx]
        idx += 1
        if ":" not in line or line[:1].isspace():
            continue
        key, _, rest = line.partition(":")
        key, rest = key.strip(), rest.strip()
        if key not in out:
            continue
        if key != "shows":
            out[key] = _unquote(rest)
            continue
        if rest.startswith("[") and rest.endswith("]"):
            out["shows"] = [_unquote(x) for x in rest[1:-1].split(",") if x.strip()]
            continue
        while idx < close and lines[idx].lstrip().startswith("- "):
            out["shows"].append(_unquote(lines[idx].lstrip()[2:]))
            idx += 1
    out["shows"] = [s for s in dict.fromkeys(out["shows"]) if s]
    return out


def target_names(target_dir: str, names: list[str]) -> dict:
    """Find which names an approved target's files mention, as whole words.

    A step that may create only the repositories the target names checks each name it
    created against the target's text.

    Args:
        target_dir: The `target/<subject>/` folder.
        names: The names to look for.

    Returns:
        Each name the target mentions with the files that mention it, and the names it does
        not mention, or `error` when the folder does not exist.
    """
    folder = Path(target_dir)
    if not folder.is_dir():
        return {"error": f"the target folder {folder} does not exist"}
    texts = {
        str(p): p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(folder.rglob("*"))
        if p.is_file() and not p.name.endswith(SKIPPED_SUFFIXES)
    }
    named: dict[str, list[str]] = {}
    unnamed: list[str] = []
    for raw in names:
        name = str(raw).strip()
        if not name:
            continue
        word = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])")
        hits = [path for path, text in texts.items() if word.search(text)]
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
    try:
        recorded = json.loads(baseline_file.read_text(encoding="utf-8")).get(
            "architectureChange"
        )
    except (OSError, ValueError, AttributeError):
        recorded = None
    if recorded in CHANGE_NOTES and recorded != "pending":
        return recorded
    return "partial" if delta_root.is_dir() else "none"


def delta_items(
    delta_dir: str, *, with_closure: bool = True, matrix_snapshot: dict | None = None
) -> dict:
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

    Returns:
        `ok`, the refusals, `architectureChange` and its note, the views, and the items.
    """
    root = Path(delta_dir).resolve()
    target = root.parent
    if root.name != DELTA_FOLDER or not target.is_dir():
        none = [f"{root} is not the {DELTA_FOLDER}/ path of a written target"]
        return {
            "ok": False,
            "refusals": none,
            "summary": {"ok": False, "refusals": none},
        }
    baseline_file = target / BASELINE_FILE
    if not baseline_file.is_file():
        baseline_file = root / BASELINE_FILE
    change = _change_of(baseline_file, root)
    if root.is_dir():
        views = [p for p in _draft_files(root) if p.suffix == ".md"]
    elif change == "new":
        views = [
            p
            for p in _draft_files(target)
            if p.suffix == ".md" and p.relative_to(target).parts[0] != DELTA_FOLDER
        ]
    else:
        views = []
    shown: dict[str, list[str]] = {}
    listed = []
    refusals = []
    warnings = []
    for view in views:
        cat = _catalog(view)
        listed.append({"path": str(view), **cat})
        elements = cat["shows"] or ([cat["subject"]] if cat["subject"] else [])
        if not cat["shows"]:
            warnings.append(
                f"{view} names no element in `shows`"
                + (f"; its subject {cat['subject']} is the element" if elements else "")
            )
        for element in elements:
            shown.setdefault(element, []).append(str(view))
    # The handoff written with the target is the record of the assessment the target was
    # approved on; a survey changed since then is noted, not re-validated.
    manifest = None
    if baseline_file.is_file():
        try:
            manifest = json.loads(baseline_file.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or not isinstance(
                manifest.get("entries"), list
            ):
                raise TypeError("it holds no assessment entries")
            manifest.setdefault("implementationWork", [])
            manifest.setdefault("designChanged", False)
            manifest.setdefault("documentationChanged", False)
            survey_path = Path(str(manifest.get("survey") or ""))
            if survey_path.is_file() and hashlib.sha256(
                survey_path.read_bytes()
            ).hexdigest() != manifest.get("surveySha256"):
                warnings.append(
                    f"the survey {survey_path} changed since the target was written; "
                    "the assessment recorded with the target is used"
                )
        except (OSError, ValueError, TypeError) as exc:
            refusals.append(f"invalid baseline handoff: {exc}")
            manifest = None
    if not views and (
        not manifest or manifest["designChanged"] or manifest["documentationChanged"]
    ):
        warnings.append(
            f"{target} holds no view, and its baseline handoff "
            + ("is missing" if not manifest else "names design or documentation work")
        )
    items = [
        {"id": f"D{n}", "element": element, "views": shown[element]}
        for n, element in enumerate(sorted(shown, key=str.casefold), start=1)
    ]
    # Build scope is catalog elements, not survey capability labels or code judgments.
    present = {element_id(item["element"]) for item in items}
    if change == "partial":
        documents = [
            {"path": str(path)}
            for path in _draft_files(target)
            if path.suffix == ".md"
            and DELTA_FOLDER not in path.relative_to(target).parts
        ]
    elif change == "none" and manifest:
        documents = [
            doc for entry in manifest["entries"] for doc in entry.get("documents", [])
        ]
    else:
        documents = []
    try:
        future = catalog_elements(documents)
    except (OSError, UnicodeError) as exc:
        future = {}
        refusals.append(f"cannot read future-set catalog: {exc}")
    for element, element_views in sorted(
        future.items(), key=lambda pair: element_id(pair[0])
    ):
        key = element_id(element)
        row = row_of(matrix_snapshot, element)
        if key in present or (
            change == "partial" and satisfied(matrix_snapshot or {}, row)
        ):
            continue
        items.append(
            {
                "id": f"D{len(items) + 1}",
                "element": element,
                "kind": "implementation-gap",
                "views": sorted(set(element_views)),
                "state": row.get("state", "unknown"),
                "repository": row.get("repository"),
                "baseline": str(baseline_file),
            }
        )
        present.add(key)
    if change == "none" and not items:
        refusals.append(
            "the unchanged architecture's cited effective views name no elements"
        )
    prerequisites = 0
    if with_closure and not refusals:
        from archclosure import merge_closure

        items, closure_refusals, prerequisites = merge_closure(root, items)
        refusals += closure_refusals
    baseline_validated = manifest is not None and not refusals
    baseline_summary = {
        "baselineValidated": baseline_validated,
        "implementationWork": len(items) if baseline_validated else None,
        "implementationComplete": baseline_validated and not items,
        "prerequisites": prerequisites,
    }
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
        **baseline_summary,
        "summary": {
            "ok": not refusals,
            "refusals": refusals,
            "warnings": len(warnings),
            "views": len(listed),
            "items": len(items),
            "architectureChange": change,
            "deltaExists": root.is_dir(),
            **baseline_summary,
        },
    }


@git_result
def remove_target(
    arch_root: str, target_dir: str, *, message: str, execution_id: str = ""
) -> dict:
    """Delete one `target/<subject>/` folder and commit the removal.

    The folder must be a direct child of `<arch_root>/target/`. Its tracked files are
    removed with `git rm` and committed on their own (`git commit -- <folder>`), so changes
    staged elsewhere in the repository stay out of the commit; files git does not track are
    deleted from disk. A folder already gone is reported, not refused.

    Args:
        arch_root: The architecture directory holding `target/`.
        target_dir: The target folder to remove.
        message: The commit message.

    Returns:
        `ok`, the refusals, whether the folder was removed, the commit, and git's output.
    """
    root = _arch_root(arch_root)
    if root is None:
        none = ["no architecture directory was given"]
        return {
            "ok": False,
            "refusals": none,
            "summary": {"ok": False, "refusals": none},
        }
    folder = Path(target_dir).resolve()
    targets = (root / TARGET_FOLDER).resolve()
    if folder.parent != targets:
        why = [f"{folder} is not a subject folder directly under {targets}"]
        return {"ok": False, "refusals": why, "summary": {"ok": False, "refusals": why}}
    report: dict = {
        "ok": True,
        "refusals": [],
        "targetDir": str(folder),
        "commit": None,
    }
    if not folder.exists():
        report["removed"] = False
        report["summary"] = {"ok": True, "removed": False, "commit": None}
        return report

    def git(*argv: str) -> subprocess.CompletedProcess:
        return run_git(root, *argv, execution_id=execution_id)

    tracked = git("ls-files", "--", str(folder))
    if tracked.returncode != 0:
        why = [f"git ls-files failed: {tracked.stderr.strip()}"]
        return report | {
            "ok": False,
            "refusals": why,
            "summary": {"ok": False, "refusals": why},
        }
    if tracked.stdout.strip():
        rm = git("rm", "-r", "-q", "--", str(folder))
        if rm.returncode != 0:
            why = [f"git rm failed: {rm.stderr.strip()}"]
            return report | {
                "ok": False,
                "refusals": why,
                "summary": {"ok": False, "refusals": why},
            }
    if folder.exists():
        shutil.rmtree(folder)
    if tracked.stdout.strip():
        done = git("commit", "-q", "-m", message, "--", str(folder))
        if done.returncode != 0:
            why = [f"git commit failed: {(done.stderr or done.stdout).strip()}"]
            return report | {
                "ok": False,
                "removed": True,
                "refusals": why,
                "summary": {"ok": False, "removed": True, "refusals": why},
            }
        head = git("rev-parse", "--short", "HEAD")
        report["commit"] = head.stdout.strip() or None
    report["removed"] = True
    report["summary"] = {"ok": True, "removed": True, "commit": report["commit"]}
    return report


def _refused(why: list[str]) -> dict:
    return {"ok": False, "refusals": why, "summary": {"ok": False, "refusals": why}}


@git_result
def remove_built(
    arch_root: str, files: list[str], *, message: str, execution_id: str = ""
) -> dict:
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

    Returns:
        `ok`, the refusals, the files removed and already gone, the commit, and git's output.
    """
    root = _arch_root(arch_root)
    if root is None:
        return _refused(["no architecture directory was given"])
    built = (root / BUILT_FOLDER).resolve()
    wanted = [Path(str(f).strip()).resolve() for f in files if str(f).strip()]
    if not wanted:
        return _refused(["no built file was named"])
    outside = [
        str(f)
        for f in wanted
        if not f.is_relative_to(built) or len(f.relative_to(built).parts) < 2
    ]
    if outside:
        return _refused(
            [f"not inside a subject folder under {built}: {', '.join(outside)}"]
        )

    def git(*argv: str) -> subprocess.CompletedProcess:
        return run_git(root, *argv, execution_id=execution_id)

    present = [f for f in wanted if f.exists()]
    gone = [str(f) for f in wanted if not f.exists()]
    report: dict = {
        "ok": True,
        "refusals": [],
        "removed": [],
        "gone": gone,
        "commit": None,
    }
    tracked: list[str] = []
    for f in present:
        listed = git("ls-files", "--", str(f))
        if listed.returncode != 0:
            return report | _refused([f"git ls-files failed: {listed.stderr.strip()}"])
        if listed.stdout.strip():
            tracked.append(str(f))
    if tracked:
        rm = git("rm", "-q", "--", *tracked)
        if rm.returncode != 0:
            return report | _refused([f"git rm failed: {rm.stderr.strip()}"])
    for f in present:
        if f.exists():
            f.unlink()
        report["removed"].append(str(f))
    for folder in sorted({built / f.relative_to(built).parts[0] for f in present}):
        for sub in sorted((d for d in folder.rglob("*") if d.is_dir()), reverse=True):
            if not any(sub.iterdir()):
                sub.rmdir()
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    if tracked:
        done = git("commit", "-q", "-m", message, "--", *tracked)
        if done.returncode != 0:
            why = [f"git commit failed: {(done.stderr or done.stdout).strip()}"]
            return report | _refused(why)
        head = git("rev-parse", "--short", "HEAD")
        report["commit"] = head.stdout.strip() or None
    report["summary"] = {
        "ok": True,
        "removed": len(report["removed"]),
        "gone": len(gone),
        "commit": report["commit"],
    }
    return report


@git_result
def commit_integration(
    arch_root: str, files: list[str], *, message: str, execution_id: str = ""
) -> dict:
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

    Returns:
        `ok`, the refusals, the paths committed, the branch, the commit, and whether it was
        pushed.
    """
    root = _arch_root(arch_root)
    if root is None:
        return _refused(["no architecture directory was given"])
    wanted = sorted(
        {str(Path(str(f).strip()).resolve()) for f in files if str(f).strip()}
    )
    if not wanted:
        return _refused(["no integrated file was named"])
    outside = [f for f in wanted if not Path(f).is_relative_to(root)]
    if outside:
        return _refused([f"not under {root}: {', '.join(outside)}"])

    def git(*argv: str) -> subprocess.CompletedProcess:
        return run_git(root, *argv, execution_id=execution_id)

    branch = git("symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if not branch:
        return _refused([f"the repository holding {root} is not on a branch"])
    report: dict = {
        "ok": True,
        "refusals": [],
        "files": wanted,
        "branch": branch,
        "commit": None,
        "pushed": False,
    }
    added = git("add", "-A", "--", *wanted)
    if added.returncode != 0:
        return report | _refused([f"git add failed: {added.stderr.strip()}"])
    staged = git("diff", "--cached", "--name-only", "--", *wanted)
    if staged.stdout.strip():
        done = git("commit", "-q", "-m", message, "--", *wanted)
        if done.returncode != 0:
            return report | _refused(
                [f"git commit failed: {(done.stderr or done.stdout).strip()}"]
            )
        report["commit"] = git("rev-parse", "--short", "HEAD").stdout.strip() or None
    ahead = git("rev-list", "--count", f"origin/{branch}..HEAD")
    if ahead.returncode == 0 and ahead.stdout.strip() == "0":
        report["summary"] = {
            "ok": True,
            "commit": report["commit"],
            "pushed": False,
            "branch": branch,
        }
        return report
    pushed = git("push", "-q", "origin", branch)
    if pushed.returncode != 0:
        why = [f"git push failed: {(pushed.stderr or pushed.stdout).strip()}"]
        return report | _refused(why) | {"commit": report["commit"]}
    report["pushed"] = True
    report["summary"] = {
        "ok": True,
        "commit": report["commit"],
        "pushed": True,
        "branch": branch,
    }
    return report
