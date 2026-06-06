#!/usr/bin/env python3
"""
check_shape_alignment — shape-name integrity.

Guards shape-NAME integrity: a property that, once broken, produces silent
visual regressions (a section rendered with the wrong shape, or the retired
S#-index scheme creeping back after an incomplete rename). Checked statically
against whatever the repo currently declares — no shape list, count, or class
name is hardcoded beyond the structural contract under test.

PROPERTY 1 — shape-name integrity (the retired S#-index scheme stays dead).
    Shapes are identified by semantic name. The authoritative set is the Part A
    catalog in `reference/shapes.md`. Every `data-shape="..."` in the render
    sample and every `shapes/<name>.html` fragment basename MUST be a name in
    that catalog, and no bare `S<number>` index (the retired scheme) may survive
    anywhere in the shape reference or the render artifacts. An incomplete rename
    or a typo'd `data-shape` is caught here.

Centered-shape ALIGNMENT (a centered heading never sits above left-anchored
content) is deliberately NOT checked here: it is a visual property and is
verified by the render proof galleries + eyeball, not by grepping for a CSS
selector — a grep would hardcode one render's class names and go stale.

Entry point:
    run(repo_root) -> list[str]   # empty list == all checks passed
"""

import os
import re

PLUGIN_SUBPATH = os.path.join("plugins", "cds")

SHAPES_MD = os.path.join("reference", "shapes.md")
SECTION_TYPES_MD = os.path.join("reference", "section-types.md")
LANDING_RULES_MD = os.path.join(
    "skills", "compose-page", "reference", "landing-sections-shape-rules.md")
LANDING_HTML = os.path.join("test", "visual-proof-out", "landing.html")
SHAPES_DIR = os.path.join("test", "visual-proof-out", "shapes")

RETIRED_INDEX = re.compile(r"\bS\d{1,2}\b")
SHAPE_NAME = re.compile(r"^[a-z][a-z0-9-]+$")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _catalog_names(shapes_md_text):
    """Parse the Part A catalog: first column of each table row is the name."""
    names = set()
    in_part_a = False
    for line in shapes_md_text.splitlines():
        if line.strip().startswith("## Part A"):
            in_part_a = True
            continue
        if in_part_a:
            if line.startswith("## ") and "Part A" not in line:
                break
            if line.startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                first = cells[0] if cells else ""
                if SHAPE_NAME.match(first):
                    names.add(first)
    return names


def run(repo_root):
    plugin = os.path.join(repo_root, PLUGIN_SUBPATH)
    if not os.path.isdir(plugin):
        return [f"cds plugin directory not found at {plugin}"]

    failures = []

    shapes_md_path = os.path.join(plugin, SHAPES_MD)
    if not os.path.exists(shapes_md_path):
        return [f"shape catalog not found at {shapes_md_path}"]
    shapes_md = _read(shapes_md_path)
    catalog = _catalog_names(shapes_md)
    if not catalog:
        return [f"could not parse any shape names from Part A catalog in {SHAPES_MD}"]

    # --- PROPERTY 1a: retired S#-index scheme must be fully gone ---
    scanned = [SHAPES_MD, SECTION_TYPES_MD, LANDING_RULES_MD, LANDING_HTML]
    for rel in scanned:
        p = os.path.join(plugin, rel)
        if not os.path.exists(p):
            continue
        hits = sorted(set(RETIRED_INDEX.findall(_read(p))))
        if hits:
            failures.append(
                f"{rel}: retired shape index(es) {hits} still present — shapes "
                f"use semantic names; finish the rename.")

    shapes_dir = os.path.join(plugin, SHAPES_DIR)
    if os.path.isdir(shapes_dir):
        for fn in sorted(os.listdir(shapes_dir)):
            if not fn.endswith(".html"):
                continue
            base = fn[:-len(".html")]
            # 1b: fragment filenames must be catalog names (not S#, not typos)
            if base not in catalog:
                failures.append(
                    f"{SHAPES_DIR}/{fn}: fragment basename '{base}' is not a shape "
                    f"in the Part A catalog of {SHAPES_MD}.")

    # --- PROPERTY 1c: every data-shape in the sample is a catalog name ---
    landing_path = os.path.join(plugin, LANDING_HTML)
    if os.path.exists(landing_path):
        landing = _read(landing_path)
        for val in sorted(set(re.findall(r'data-shape="([^"]+)"', landing))):
            if val not in catalog:
                failures.append(
                    f"{LANDING_HTML}: data-shape=\"{val}\" is not a shape in the "
                    f"Part A catalog of {SHAPES_MD}.")

    # If the render sample is absent the render-dependent property (1c) simply
    # does not apply — artifact EXISTENCE is enforced by run-tests.sh tier 3,
    # not here; this check guards name CORRECTNESS when present. The static
    # reference scan (property 1a over the reference docs) above always runs.
    #
    # NOTE: centered-shape alignment ("a centered heading never sits above
    # left-anchored content") is a VISUAL property defined in the reference
    # (landing-sections-shape-rules.md). It is verified by the render proof
    # galleries + eyeball, not by grepping for a specific CSS selector — a grep
    # check necessarily hardcodes one render's class names and goes stale, which
    # is exactly the snapshot anti-pattern these checks avoid.

    return failures


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    out = run(root)
    if out:
        print("FAIL")
        for f in out:
            print("  -", f)
    else:
        print("PASS")
