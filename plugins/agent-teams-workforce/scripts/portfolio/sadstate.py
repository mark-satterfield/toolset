#!/usr/bin/env python3
"""The one place that writes `lifecycle_state: effective` onto an arc42 SAD entry.

`effective` is the approved state of the vault's document-classification vocabulary, and a
SAD entry settles an architecture decision only in that state. An entry becomes `effective`
when the architecture step of a prd-to-spec elaboration rules on it: the entries that
ruling creates, the entries it changes, and the existing entries it reviews and approves as
they stand. `depscore.py sad-approve` runs this module at that step, over exactly the files
holding those entries. Setting a file that is already `effective` changes nothing, so the
step can run again on resume.

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


def promote(files: list[str], *, sad_root: str | None) -> dict:
    """Set the SAD files an architecture ruling covers to `effective`.

    Every path is held to `sad_root` when one is given. A changed-file list is reported by
    an agent, so a path outside the SAD is refused rather than written — this function
    rewrites documents, and the blast radius of a bad path is the vault.

    Args:
        files: The SAD files the ruling created, changed or approved as they stand, as
            absolute paths.
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
    # The SAD location a caller holds may name the document's index file rather than the
    # directory it lives in. Both mean the same tree, and a file as the root would refuse
    # every path under it.
    root = None
    if sad_root:
        root = Path(sad_root).resolve()
        if root.is_file():
            root = root.parent
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
