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
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

STATE_KEY = "lifecycle_state"
EFFECTIVE = "effective"
IN_REVIEW = "in-review"
FENCE = "---"
EFFECTIVE_FOLDER = "arc42"
CONSTRAINTS_FOLDER = "02-architecture-constraints"
TARGET_FOLDER = "target"
DELTA_FOLDER = "delta"
BUILT_FOLDER = "built"
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


def _unquote(value: str) -> str:
    """Strip one pair of matching YAML quotes from a scalar.

    Args:
        value: The scalar as written.

    Returns:
        The scalar without its quotes.
    """
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:  # noqa: PLR2004 - a quote pair
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


def delta_items(delta_dir: str) -> dict:
    """List the elements a target's delta shows, one item per element.

    An item is one element named in the `shows` frontmatter of a delta view, with every
    delta view that shows it. Items are numbered `D1`, `D2` ... in element-name order, so
    the same delta always yields the same ids. Runs no `bd` command and writes nothing.

    Args:
        delta_dir: The `target/<subject>/delta/` directory.

    Returns:
        `ok`, the refusals, the delta views, and the items.
    """
    root = Path(delta_dir).resolve()
    if root.name != DELTA_FOLDER or not root.is_dir():
        none = [f"{root} is not a {DELTA_FOLDER}/ directory"]
        return {
            "ok": False,
            "refusals": none,
            "summary": {"ok": False, "refusals": none},
        }
    views = [p for p in _draft_files(root) if p.suffix == ".md"]
    shown: dict[str, list[str]] = {}
    listed = []
    refusals = []
    for view in views:
        cat = _catalog(view)
        listed.append({"path": str(view), **cat})
        if not cat["shows"]:
            refusals.append(f"{view} names no element in `shows`")
        for element in cat["shows"]:
            shown.setdefault(element, []).append(str(view))
    if not views:
        refusals.append(f"{root} holds no view")
    items = [
        {"id": f"D{n}", "element": element, "views": shown[element]}
        for n, element in enumerate(sorted(shown, key=str.casefold), start=1)
    ]
    return {
        "ok": not refusals,
        "refusals": refusals,
        "deltaDir": str(root),
        "views": listed,
        "items": items,
        "summary": {
            "ok": not refusals,
            "refusals": refusals,
            "views": len(listed),
            "items": len(items),
        },
    }


def remove_target(arch_root: str, target_dir: str, *, message: str) -> dict:
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
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(root), *argv],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )

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


def remove_built(arch_root: str, files: list[str], *, message: str) -> dict:
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
        if not f.is_relative_to(built) or len(f.relative_to(built).parts) < 2  # noqa: PLR2004
    ]
    if outside:
        return _refused(
            [f"not inside a subject folder under {built}: {', '.join(outside)}"]
        )

    def git(*argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(root), *argv],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )

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
