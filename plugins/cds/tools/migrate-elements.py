#!/usr/bin/env python3
"""
migrate-elements.py — mechanical CDS elements migrator, schema 1.x -> 2.0.

Applies ONLY the transforms that are unambiguously mechanical. It preserves the
source file's comments and formatting: pyyaml is used to *analyse* the document
(what themes exist, where conversion-card lives, which tile bindings look wrong),
while the edits themselves are line-level text rewrites.

What it DOES
  1. Bumps `$schema_version` to "2.0.0".
  2. Corrects the role convention `--role-{role key}` -> `--{role key}`
     (`$conventions.role_var_pattern`), if the dead form is present.
  3. Moves a `conversion-card` entry out of `geometry.containers` into a new
     `geometry.elements` group, if present (ruling 6 / finding 23).

What it does NOT do (by design)
  * It does NOT invent a `dark: mirror`. Commented-out mirror dark blocks are
    comments — not machine-readable intent — so they are left untouched. Instead,
    every concrete theme that parses with no `dark` binding is listed in a report
    so a human can add `dark: mirror` where it is genuinely wanted.
  * It does NOT apply the contrast correction (finding 26). That is a design
    decision, not a mechanical rewrite. When it detects the known bad
    tile-ink-on-dark-ground pairs it prints a WARNING pointing at the migration
    notes; it changes nothing.
  * It invents nothing else.

Migrated YAML goes to the chosen destination (or stdout on --dry-run). The
report and any warnings always go to stderr, so stdout stays clean YAML.

Usage
  python3 tools/migrate-elements.py SOURCE --dry-run      # print to stdout
  python3 tools/migrate-elements.py SOURCE --out DEST      # write DEST
  python3 tools/migrate-elements.py SOURCE --in-place      # rewrite SOURCE (+ SOURCE.bak)

Exit status: 0 on success, 2 on usage/IO error.
Python 3, standard library + PyYAML only.
"""
import argparse
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a declared plugin dependency
    sys.stderr.write("migrate-elements: PyYAML required (pip install pyyaml)\n")
    sys.exit(2)

NOTES = "analysis/schema-2-migration-notes.md"
# The documented contrast bug: near-black tile ink over a dark panels ground.
_BAD_INK = "--color-text-ink"
_BAD_GROUNDS = {"--color-panels-a", "--color-panels-g"}


def _indent(line):
    return len(line) - len(line.lstrip())


def bump_version(lines):
    """Set $schema_version to 2.0.0, preserving any inline comment. Returns
    (lines, note)."""
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*\$schema_version:\s*)(\S+)(.*)$", ln)
        if m:
            old = m.group(2).strip("\"'")
            lines[i] = f'{m.group(1)}"2.0.0"{m.group(3)}'
            return lines, f"$schema_version {old} -> 2.0.0"
    # absent: insert before the first non-comment, non-blank top-level line
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s and not s.startswith("#"):
            lines.insert(i, '$schema_version: "2.0.0"')
            return lines, "$schema_version (absent) -> inserted 2.0.0"
    lines.insert(0, '$schema_version: "2.0.0"')
    return lines, "$schema_version (absent) -> inserted 2.0.0"


def fix_role_pattern(lines):
    """Rewrite the dead --role-{role key} convention to --{role key}. Returns
    (lines, note|None)."""
    for i, ln in enumerate(lines):
        if "role_var_pattern" in ln and "--role-{role key}" in ln:
            lines[i] = ln.replace("--role-{role key}", "--{role key}")
            return lines, "role_var_pattern --role-{role key} -> --{role key}"
    return lines, None


def _containers_block(lines):
    """(containers_line_index, boundary_index) for the `geometry.containers`
    block, or (None, None). boundary_index is the first line at indent <= 2
    after the block (or len(lines))."""
    ci = None
    for i, ln in enumerate(lines):
        if re.match(r"^  containers:\s*(#.*)?$", ln):
            ci = i
            break
    if ci is None:
        return None, None
    b = ci + 1
    while b < len(lines):
        ln = lines[b]
        if ln.strip() == "":
            b += 1
            continue
        if _indent(ln) <= 2:
            break
        b += 1
    return ci, b


def move_conversion_card(lines, data):
    """Move conversion-card out of geometry.containers into a new
    geometry.elements group. Returns (lines, note|None)."""
    geom = (data or {}).get("geometry") or {}
    containers = geom.get("containers") or {}
    elements = geom.get("elements") or {}
    if "conversion-card" not in containers:
        return lines, None
    if "conversion-card" in elements:
        return lines, None  # already migrated; leave alone

    ci, b = _containers_block(lines)
    if ci is None:
        return lines, None

    # find the conversion-card member line inside the block
    cc_idx = None
    for i in range(ci + 1, b):
        if re.match(r"^\s+conversion-card\s*:", lines[i]):
            cc_idx = i
            break
    if cc_idx is None:
        return lines, None
    cc_line = lines[cc_idx]

    # remove the member from containers
    del lines[cc_idx]
    if cc_idx < b:
        b -= 1

    # trim blank lines that trailed the containers members so the new block sits
    # tight against the last member, with the pre-existing blank(s) separating it
    # from whatever section follows
    p = b
    while p - 1 > ci and lines[p - 1].strip() == "":
        p -= 1

    block = [
        "",
        "  # ----- fixed element widths -> --element-{key}",
        "  # A fixed-width UI element (a card, not a section wrapper): its width",
        "  # is BELOW the page width. --container-conversion-card is emitted as an",
        "  # alias of --element-conversion-card until consumers migrate.",
        "  elements:",
        cc_line,
    ]
    lines[p:p] = block
    return lines, "conversion-card moved geometry.containers -> geometry.elements"


def themes_without_dark(data):
    """Concrete theme names whose parsed modes carry no `dark` binding."""
    out = []
    for name, t in (data.get("themes") or {}).items():
        if not isinstance(t, dict) or "modes" not in t:
            continue  # alias theme or malformed
        if "dark" not in (t.get("modes") or {}):
            out.append(name)
    return out


def bad_contrast_pairs(data):
    """(theme, role) for every light-mode tile-ink bound to near-black ink over a
    dark panels ground — the documented finding-26 contrast bug."""
    hits = []
    for name, t in (data.get("themes") or {}).items():
        if not isinstance(t, dict) or "modes" not in t:
            continue
        light = (t.get("modes") or {}).get("light")
        if not isinstance(light, dict):
            continue
        b = light.get("bindings") or {}
        for n in ("1", "2", "3", "accent"):
            ink = b.get(f"tile-ink-{n}")
            ground = b.get(f"tile-ground-{n}")
            if not isinstance(ink, dict) or not isinstance(ground, dict):
                continue
            if ink.get("var") == _BAD_INK and ground.get("var") in _BAD_GROUNDS:
                hits.append((name, f"tile-ink-{n} over {ground['var']}"))
    return hits


def migrate(text):
    """Return (migrated_text, notes, warnings)."""
    data = yaml.safe_load(text)
    lines = text.split("\n")
    notes = []
    warnings = []

    lines, n = bump_version(lines)
    notes.append(n)
    lines, n = fix_role_pattern(lines)
    if n:
        notes.append(n)
    else:
        notes.append("role_var_pattern already bare (--{role key}) — no change")
    lines, n = move_conversion_card(lines, data)
    if n:
        notes.append(n)
    else:
        notes.append("conversion-card not in geometry.containers — no move")

    no_dark = themes_without_dark(data)
    if no_dark:
        warnings.append(
            "themes with no `dark` binding (consider `dark: mirror` if the theme "
            "should not change on mode flip): " + ", ".join(no_dark))
    bad = bad_contrast_pairs(data)
    if bad:
        detail = "; ".join(f"{th}: {what}" for th, what in bad)
        warnings.append(
            f"contrast bug NOT fixed (mechanical migrator leaves design "
            f"corrections alone) — near-black tile ink over a dark panels ground "
            f"in [{detail}]. See {NOTES} for the rebindings to apply by hand.")

    return "\n".join(lines), notes, warnings


def _report(notes, warnings):
    sys.stderr.write("migrate-elements: applied 1.x -> 2.0\n")
    for n in notes:
        sys.stderr.write(f"  - {n}\n")
    for w in warnings:
        sys.stderr.write(f"  ! {w}\n")


def main(argv):
    ap = argparse.ArgumentParser(
        prog="migrate-elements.py",
        description="Mechanical CDS elements migrator, schema 1.x -> 2.0.")
    ap.add_argument("source", help="path to the 1.x elements YAML")
    dest = ap.add_mutually_exclusive_group(required=True)
    dest.add_argument("--out", metavar="DEST",
                      help="write the migrated YAML to DEST")
    dest.add_argument("--in-place", action="store_true",
                      help="rewrite SOURCE, backing the original up to SOURCE.bak")
    dest.add_argument("--dry-run", action="store_true",
                      help="print the migrated YAML to stdout, write nothing")
    args = ap.parse_args(argv)

    try:
        with open(args.source, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        sys.stderr.write(f"migrate-elements: cannot read {args.source}: {e}\n")
        return 2

    try:
        migrated, notes, warnings = migrate(text)
    except yaml.YAMLError as e:
        sys.stderr.write(f"migrate-elements: {args.source} is not valid YAML: {e}\n")
        return 2

    if args.dry_run:
        sys.stdout.write(migrated if migrated.endswith("\n") else migrated + "\n")
        _report(notes, warnings)
        return 0

    if args.in_place:
        bak = args.source + ".bak"
        try:
            with open(bak, "w", encoding="utf-8") as f:
                f.write(text)
            with open(args.source, "w", encoding="utf-8") as f:
                f.write(migrated if migrated.endswith("\n") else migrated + "\n")
        except OSError as e:
            sys.stderr.write(f"migrate-elements: cannot write {args.source}: {e}\n")
            return 2
        sys.stderr.write(f"migrate-elements: wrote {args.source} (backup {bak})\n")
        _report(notes, warnings)
        return 0

    # --out
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(migrated if migrated.endswith("\n") else migrated + "\n")
    except OSError as e:
        sys.stderr.write(f"migrate-elements: cannot write {args.out}: {e}\n")
        return 2
    sys.stderr.write(f"migrate-elements: wrote {args.out}\n")
    _report(notes, warnings)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
