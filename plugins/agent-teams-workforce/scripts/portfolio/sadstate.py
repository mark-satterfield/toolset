#!/usr/bin/env python3
"""The one place that writes `lifecycle_state: effective` onto an arc42 SAD entry.

A SAD entry settles an architecture decision only when its ruling came out of a COMPLETED
prd-to-spec run. Nothing else vouches for a SAD entry: an entry written by an ad-hoc
architecture pass, or by a run that ended before its Tasks landed, has no provenance behind
it, and a downstream reader that treats it as settled is trusting a claim nobody checked.

So every entry sits at `in-review` until an elaboration finishes, and this module runs on
that one transition — `elaboration-finish --done`, the same call that marks the Epic
`done`. The predicate is false everywhere until a run makes it true, one Epic at a time,
and there is no flag to set.

Entries are promoted by FILE, because the vault's classification vocabulary lives in each
file's frontmatter. Section 8 carries one concept per file, so promotion there is per
decision; sections 2 and 4 are coarser, and promoting one of those files promotes
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
        stripped = lines[idx].lstrip()
        if not stripped.startswith(f"{STATE_KEY}:"):
            continue
        if stripped[len(STATE_KEY) + 1 :].strip() == EFFECTIVE:
            return "unchanged"
        lines[idx] = f"{STATE_KEY}: {EFFECTIVE}"
        break
    else:
        # The field is required core on every managed document. A SAD file that reaches a
        # completed elaboration without one is missing its classification, not exempt from
        # it, so the key is added rather than the file skipped.
        lines.insert(close, f"{STATE_KEY}: {EFFECTIVE}")
    trailing = "\n" if text.endswith("\n") else ""
    path.write_text("\n".join(lines) + trailing, encoding="utf-8")
    return "promoted"


def promote(files: list[str], *, sad_root: str | None) -> dict:
    """Promote the SAD files a completed elaboration vetted.

    Every path is held to `sad_root` when one is given. A changed-file list is reported by
    an agent, so a path outside the SAD is refused rather than written — this function
    rewrites documents, and the blast radius of a bad path is the vault.

    Args:
        files: The SAD files the run's architecture phase changed, as absolute paths.
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
