#!/usr/bin/env python3
"""
check_shape_alignment — shape-name integrity.

Guards shape-NAME integrity: a property that, once broken, produces silent
visual regressions (a section rendered with the wrong shape, or the retired
S#-index scheme creeping back after an incomplete rename). Checked statically
against whatever the repo currently declares — no shape list, count, or class
name is hardcoded beyond the structural contract under test.

PROPERTY 1 — shape-name integrity (the retired S#-index scheme stays dead).
    Shapes are identified by semantic name. The authoritative set is the
    frontmatter `name:` of each entry in the `reference/libraries/shapes/`
    Building Blocks tree (excluding FORMAT.md / CONVENTIONS.md). Every
    `data-shape="..."` in the render sample and every `shapes/<name>.html`
    fragment basename MUST be a name in that set, and no bare `S<number>` index
    (the retired scheme) may survive anywhere in the shape/section libraries, the
    shape-selection rules, or the render artifacts. An incomplete rename or a
    typo'd `data-shape` is caught here.

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

# Building Blocks library trees (one entry per file, typed frontmatter).
SHAPES_LIB = os.path.join("reference", "libraries", "shapes")
SECTIONS_LIB = os.path.join("reference", "libraries", "sections")
SHAPE_RULES_DIR = os.path.join("reference", "rules", "shape-selection")
LANDING_HTML = os.path.join("test", "visual-proof-out", "landing.html")
SHAPES_DIR = os.path.join("test", "visual-proof-out", "shapes")

# Non-entry files that live in the library dirs.
NON_ENTRIES = {"FORMAT.md", "CONVENTIONS.md"}

RETIRED_INDEX = re.compile(r"\bS\d{1,2}\b")
SHAPE_NAME = re.compile(r"^[a-z][a-z0-9-]+$")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _frontmatter_name(text):
    """Return the `name:` value from a leading `---` YAML frontmatter block, or
    None. Parsed line-wise (no YAML dependency): the frontmatter is a flat block
    and `name:` is a top-level scalar."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    for line in block.splitlines():
        m = re.match(r"\s*name:\s*(\S+)\s*$", line)
        if m:
            return m.group(1).strip().strip("\"'")
    return None


def _entry_files(dir_path):
    """Absolute paths of every `.md` entry file in a library dir (excluding the
    FORMAT/CONVENTIONS meta files)."""
    if not os.path.isdir(dir_path):
        return []
    return [
        os.path.join(dir_path, fn)
        for fn in sorted(os.listdir(dir_path))
        if fn.endswith(".md") and fn not in NON_ENTRIES
    ]


def _shape_catalog(plugin):
    """The authoritative shape-name set: frontmatter `name:` of each entry in
    reference/libraries/shapes/."""
    names = set()
    for p in _entry_files(os.path.join(plugin, SHAPES_LIB)):
        name = _frontmatter_name(_read(p))
        if name and SHAPE_NAME.match(name):
            names.add(name)
    return names


def run(repo_root):
    plugin = os.path.join(repo_root, PLUGIN_SUBPATH)
    if not os.path.isdir(plugin):
        return [f"cds plugin directory not found at {plugin}"]

    failures = []

    shapes_lib = os.path.join(plugin, SHAPES_LIB)
    if not os.path.isdir(shapes_lib):
        return [f"shape library not found at {shapes_lib}"]
    catalog = _shape_catalog(plugin)
    if not catalog:
        return [
            f"could not parse any shape names from frontmatter in {SHAPES_LIB}"
        ]

    # --- PROPERTY 1a: retired S#-index scheme must be fully gone ---
    # Scan the shape + section libraries and the shape-selection rules (where the
    # former shapes.md / section-types.md / landing-rules.md content now lives),
    # plus the render sample.
    scanned = []
    for tree in (SHAPES_LIB, SECTIONS_LIB, SHAPE_RULES_DIR):
        scanned.extend(_entry_files(os.path.join(plugin, tree)))
    scanned.append(os.path.join(plugin, LANDING_HTML))
    for p in scanned:
        if not os.path.exists(p):
            continue
        hits = sorted(set(RETIRED_INDEX.findall(_read(p))))
        if hits:
            rel = os.path.relpath(p, plugin)
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
                    f"{SHAPES_DIR}/{fn}: fragment basename '{base}' is not a "
                    f"shape in the {SHAPES_LIB} library.")

    # --- PROPERTY 1c: every data-shape in the sample is a catalog name ---
    landing_path = os.path.join(plugin, LANDING_HTML)
    if os.path.exists(landing_path):
        landing = _read(landing_path)
        for val in sorted(set(re.findall(r'data-shape="([^"]+)"', landing))):
            if val not in catalog:
                failures.append(
                    f"{LANDING_HTML}: data-shape=\"{val}\" is not a shape in the "
                    f"{SHAPES_LIB} library.")

    # If the render sample is absent the render-dependent property (1c) simply
    # does not apply — artifact EXISTENCE is enforced by run-tests.sh tier 3,
    # not here; this check guards name CORRECTNESS when present. The static
    # reference scan (property 1a over the libraries) above always runs.
    #
    # NOTE: centered-shape alignment ("a centered heading never sits above
    # left-anchored content") is a VISUAL property. It is verified by the render
    # proof galleries + eyeball, not by grepping for a specific CSS selector — a
    # grep check necessarily hardcodes one render's class names and goes stale,
    # which is exactly the snapshot anti-pattern these checks avoid.

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
