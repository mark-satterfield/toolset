#!/usr/bin/env python3
"""
check_shape_conformance — the Shape a Section renders with is one the rules offer.

Guards the property that makes the Shape Selection Rules load-bearing rather
than advisory: a composer resolves a Section by taking candidates from that
Section's rule, not by reaching for whatever layout is nearest to hand. Once
broken, a Page renders a layout the library never offered and every downstream
audit still passes — the artifact is style-compliant and structurally wrong.

Checked statically against whatever the repo currently declares. No shape list,
section list, or candidate set is hardcoded: the authoritative sets are read
from the rule entries themselves.

PROPERTY 1 — every Shape a rule names exists.
    For each entry in `reference/rules/shape-selection/`, every shape named in
    a `table:` row (`primary:` and each entry of `alternates:`) and in
    `default:` MUST resolve to an entry in `reference/libraries/shapes/`. A
    rule offering a Shape the library does not define is unresolvable at build
    time and fails here instead.

PROPERTY 2 — every rule serves a Section that exists, and every lazy Section
    has a rule.
    Each rule's `section:` MUST name an entry in
    `reference/libraries/sections/`. Conversely a Section entry that declares
    no eager `shape:` MUST have a rule file, since lazy assignment has nothing
    to run without one.

PROPERTY 3 — a rule's candidate set is non-empty.
    Every rule MUST yield at least one candidate: a `default:` is required, so
    exhaustion falls to fallback generation rather than to nothing.

Composer-side conformance — that a *rendered* Section used a Shape from its
own rule's candidate set — is verified against the decisions sidecar by
`check_decisions_conformance.py`, which runs over composed output rather than
over the library.

Entry point:
    run(repo_root) -> list[str]   # empty list == all checks passed
"""

import os
import re

PLUGIN_SUBPATH = os.path.join("plugins", "cds")

SHAPES_LIB = os.path.join("reference", "libraries", "shapes")
SECTIONS_LIB = os.path.join("reference", "libraries", "sections")
SHAPE_RULES_DIR = os.path.join("reference", "rules", "shape-selection")

NON_ENTRY = {"FORMAT.md", "CONVENTIONS.md"}


def _frontmatter(text):
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def _entry_names(root, subpath):
    """Declared `name:` of every entry in a library tree."""
    names = set()
    directory = os.path.join(root, PLUGIN_SUBPATH, subpath)
    if not os.path.isdir(directory):
        return names
    for basename in sorted(os.listdir(directory)):
        if not basename.endswith(".md") or basename in NON_ENTRY:
            continue
        text = open(os.path.join(directory, basename), encoding="utf-8").read()
        match = re.search(r"^name:\s*(\S+)\s*$", _frontmatter(text), re.MULTILINE)
        names.add(match.group(1) if match else basename[:-3])
    return names


def _shapes_named_by(front):
    """Every shape name a rule's table and default offer, in declaration order."""
    named = []
    for match in re.finditer(r"primary:\s*([A-Za-z0-9-]+)", front):
        named.append(match.group(1))
    for match in re.finditer(r"alternates:\s*\[([^\]]*)\]", front):
        named.extend(s.strip() for s in match.group(1).split(",") if s.strip())
    for match in re.finditer(r"^default:\s*([A-Za-z0-9-]+)\s*$", front, re.MULTILINE):
        named.append(match.group(1))
    return named


def run(repo_root):
    failures = []

    shape_names = _entry_names(repo_root, SHAPES_LIB)
    section_names = _entry_names(repo_root, SECTIONS_LIB)

    rules_dir = os.path.join(repo_root, PLUGIN_SUBPATH, SHAPE_RULES_DIR)
    if not os.path.isdir(rules_dir):
        return [f"{SHAPE_RULES_DIR}: shape-selection rule directory is missing"]

    sections_with_rule = set()

    for basename in sorted(os.listdir(rules_dir)):
        if not basename.endswith(".md") or basename in NON_ENTRY:
            continue
        rel = os.path.join(SHAPE_RULES_DIR, basename)
        front = _frontmatter(open(os.path.join(rules_dir, basename), encoding="utf-8").read())

        # PROPERTY 1 — every offered Shape resolves in the shape library.
        offered = _shapes_named_by(front)
        for shape in offered:
            if shape not in shape_names:
                failures.append(
                    f"{rel}: offers shape '{shape}', which no entry in {SHAPES_LIB} declares"
                )

        # PROPERTY 3 — the candidate set is non-empty.
        if not re.search(r"^default:\s*\S+", front, re.MULTILINE):
            failures.append(f"{rel}: no `default:` — the candidate set can exhaust to nothing")

        # PROPERTY 2a — the rule serves a Section that exists.
        served = re.search(r"^section:\s*(\S+)\s*$", front, re.MULTILINE)
        if not served:
            failures.append(f"{rel}: no `section:` — the rule serves no Section")
        else:
            name = served.group(1)
            sections_with_rule.add(name)
            if name not in section_names:
                failures.append(
                    f"{rel}: serves section '{name}', which no entry in {SECTIONS_LIB} declares"
                )

    # PROPERTY 2b — a lazily-assigned Section has a rule to run.
    sections_dir = os.path.join(repo_root, PLUGIN_SUBPATH, SECTIONS_LIB)
    if os.path.isdir(sections_dir):
        for basename in sorted(os.listdir(sections_dir)):
            if not basename.endswith(".md") or basename in NON_ENTRY:
                continue
            front = _frontmatter(
                open(os.path.join(sections_dir, basename), encoding="utf-8").read()
            )
            name_match = re.search(r"^name:\s*(\S+)\s*$", front, re.MULTILINE)
            name = name_match.group(1) if name_match else basename[:-3]
            eager = re.search(r"^shape:\s*\S+", front, re.MULTILINE)
            if not eager and name not in sections_with_rule:
                failures.append(
                    f"{os.path.join(SECTIONS_LIB, basename)}: declares no eager `shape:` and has no "
                    f"rule in {SHAPE_RULES_DIR} — lazy assignment has nothing to run"
                )

    return failures


if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    problems = run(root)
    for problem in problems:
        print(problem)
    sys.exit(1 if problems else 0)
