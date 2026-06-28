#!/usr/bin/env python3
"""
check_reference_prose — the reference is source, not a PM board.

Reference files (the design-system catalog) must read like source code: they
state what IS, never what is deferred, missing, or historical. Project
management lives in other tools. This guard fails if PM / deferral / history
prose re-enters the reference catalog.

PROPERTY — no PM prose in the reference catalog.
    Across plugins/cds/reference/**.md and plugins/cds/skills/*/reference/**.md,
    there is:
      * no heading-level PM section
        (Known gaps | TODO | FIXME | Open questions | Backlog | Future work), and
      * no inline deferral / history marker from a tight lexicon:
        TBD, FIXME, "(was ", "not yet (implemented|covered|represented|part of)",
        "future revision", "carry forward", "tentative", "in a later pass".

Deliberately NOT flagged: the word "placeholder" — it is legitimate spec
vocabulary in this corpus (input placeholders, the em-dash placeholder glyph).

Config-agnostic: asserts the absence property over whatever reference files
exist; hardcodes no filename, count, or section. Scopes to reference catalog
content only (not SKILL bodies, commands, or agents, which are instructions).

Entry point:
    run(repo_root) -> list[str]   # empty list == passed
"""

import os
import re

PLUGIN_SUBPATH = os.path.join("plugins", "cds")

# Heading whose title is a PM section.
_PM_HEADING = re.compile(
    r"^#{1,6}\s*(known gaps|todo|fixme|open questions|backlog|future work)\b",
    re.IGNORECASE,
)
# Inline deferral / history lexicon (tight, to avoid false positives).
_PM_INLINE = re.compile(
    r"\bTBD\b|\bFIXME\b|\(was\s|not yet (?:implemented|covered|represented|part of)"
    r"|future revision|carry forward|tentative|in a later pass",
    re.IGNORECASE,
)


def _reference_md_files(plugin_root):
    """Reference-catalog markdown: reference/** and skills/*/reference/**."""
    roots = [os.path.join(plugin_root, "reference")]
    skills = os.path.join(plugin_root, "skills")
    if os.path.isdir(skills):
        for name in os.listdir(skills):
            r = os.path.join(skills, name, "reference")
            if os.path.isdir(r):
                roots.append(r)
    files = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, filenames in os.walk(root):
            for fn in filenames:
                if fn.lower().endswith(".md"):
                    files.append(os.path.join(dirpath, fn))
    return sorted(files)


def run(repo_root):
    plugin_root = os.path.join(repo_root, PLUGIN_SUBPATH)
    if not os.path.isdir(plugin_root):
        return [f"REFERENCE-PROSE: plugin dir not found at {plugin_root}"]

    failures = []
    for path in _reference_md_files(plugin_root):
        rel = os.path.relpath(path, plugin_root)
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError) as e:
            failures.append(f"REFERENCE-PROSE: {rel}: unreadable ({e})")
            continue
        for n, line in enumerate(lines, 1):
            if _PM_HEADING.match(line):
                failures.append(
                    f"REFERENCE-PROSE: {rel}:{n}: PM heading — reference is "
                    f"source, not a project-management board: {line.strip()!r}")
            m = _PM_INLINE.search(line)
            if m:
                failures.append(
                    f"REFERENCE-PROSE: {rel}:{n}: deferral/history marker "
                    f"'{m.group(0)}' — state what IS, not what is deferred: "
                    f"{line.strip()[:80]!r}")
    return failures


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    out = run(root)
    print("PASS" if not out else "FAIL")
    for f in out:
        print("  -", f)
