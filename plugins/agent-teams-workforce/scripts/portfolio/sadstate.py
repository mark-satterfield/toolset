#!/usr/bin/env python3
"""The one place that reads and writes `lifecycle_state` on arc42 SAD files for the pipeline.

`effective` is per document: it means that document was reviewed and approved, nothing
about any other. A PRD's architecture relies on several documents; the architecture step
of a prd-to-spec elaboration reviews every relied-on document that is not `effective`
(approves it as it stands, updates it, or replaces it), and then every document the PRD
relies on, changes or creates becomes `effective`. `depscore.py sad-approve` runs
`promote` at that step over exactly those files; setting a file that is already
`effective` changes nothing, so the step can run again on resume. `depscore.py sad-state`
runs `states`, which reads the relied-on files' states so the step skips its analysts only
when every one is already `effective`.

Entries are approved by FILE, because the vault's classification vocabulary lives in each
file's frontmatter. Section 8 carries one concept per file, so approval there is per
decision; sections 2 and 4 are coarser, and approving one of those files approves
everything in it. That is a property of how the SAD is laid out, not a choice made here.
"""

from __future__ import annotations

from pathlib import Path

STATE_KEY = "lifecycle_state"
EFFECTIVE = "effective"
FENCE = "---"


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


def _promote_one(path: Path) -> str:
    """Set one file's `lifecycle_state` to `effective`.

    Args:
        path: The SAD file.

    Returns:
        "promoted" when the value changed, "unchanged" when it was already effective, or
        "no-frontmatter" when the file carries no YAML frontmatter to classify.
    """
    text = path.read_text(encoding="utf-8")
    split = _split_frontmatter(text)
    if split is None:
        return "no-frontmatter"
    lines, start, close = split
    for idx in range(start, close):
        # Top-level keys only: an indented `lifecycle_state:` belongs to a nested mapping,
        # and rewriting it unindented would break the frontmatter it sits in.
        line = lines[idx]
        if not line.startswith(f"{STATE_KEY}:"):
            continue
        if line[len(STATE_KEY) + 1 :].strip() == EFFECTIVE:
            return "unchanged"
        lines[idx] = f"{STATE_KEY}: {EFFECTIVE}"
        break
    else:
        # The field is required core on every managed document. A SAD file a ruling
        # covers without one is missing its classification, not exempt from it, so the
        # key is added rather than the file skipped.
        lines.insert(close, f"{STATE_KEY}: {EFFECTIVE}")
    trailing = "\n" if text.endswith("\n") else ""
    path.write_text("\n".join(lines) + trailing, encoding="utf-8")
    return "promoted"


def _state_of(path: Path) -> str:
    """Read one file's top-level `lifecycle_state`.

    Args:
        path: The SAD file.

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


def _sad_root(sad_root: str | None) -> Path | None:
    """Resolve the SAD directory a caller names, which may be its index file.

    Args:
        sad_root: The SAD directory or index file, or None.

    Returns:
        The directory, or None when no root was given.
    """
    if not sad_root:
        return None
    root = Path(sad_root).resolve()
    return root.parent if root.is_file() else root


def states(files: list[str], *, sad_root: str | None) -> dict:
    """Read the `lifecycle_state` of the SAD files a PRD relies on; writes nothing.

    Args:
        files: The SAD files, as absolute paths.
        sad_root: The SAD directory every file must sit under, or None to skip the check.

    Returns:
        A report: each readable file's state, the files not at `effective` (a file with
        no state counts as not effective), and the files refused or unreadable.
    """
    root = _sad_root(sad_root)
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
                {"path": name, "reason": f"outside the SAD at {root}"}
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


def promote(files: list[str], *, sad_root: str | None) -> dict:
    """Set the SAD files an architecture ruling covers to `effective`.

    Every path is held to `sad_root` when one is given. A changed-file list is reported by
    an agent, so a path outside the SAD is refused rather than written — this function
    rewrites documents, and the blast radius of a bad path is the vault.

    Args:
        files: The SAD files the PRD relies on and those the ruling changed or created,
            as absolute paths.
        sad_root: The SAD directory every file must sit under, or None to skip the check.

    Returns:
        A report: the files promoted, those already effective, those carrying no
        frontmatter, and those refused or unreadable, each with its reason.
    """
    report: dict = {
        "promoted": [],
        "unchanged": [],
        "noFrontmatter": [],
        "refused": [],
        "failed": [],
    }
    root = _sad_root(sad_root)
    for raw in files:
        name = str(raw).strip()
        if not name:
            continue
        path = Path(name)
        try:
            resolved = path.resolve()
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        if root is not None and not resolved.is_relative_to(root):
            report["refused"].append(
                {"path": name, "reason": f"outside the SAD at {root}"}
            )
            continue
        if not resolved.is_file():
            report["failed"].append({"path": name, "reason": "not a file"})
            continue
        try:
            outcome = _promote_one(resolved)
        except OSError as exc:
            report["failed"].append({"path": name, "reason": str(exc)})
            continue
        if outcome == "promoted":
            report["promoted"].append(str(resolved))
        elif outcome == "unchanged":
            report["unchanged"].append(str(resolved))
        else:
            report["noFrontmatter"].append(str(resolved))
    report["summary"] = {
        "promoted": len(report["promoted"]),
        "unchanged": len(report["unchanged"]),
        "noFrontmatter": len(report["noFrontmatter"]),
        "refused": len(report["refused"]),
        "failed": len(report["failed"]),
    }
    return report
