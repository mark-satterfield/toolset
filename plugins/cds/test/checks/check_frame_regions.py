#!/usr/bin/env python3
"""
check_frame_regions — a region of a frame is a Section, and its variability lives
in Shapes.

The recurring modelling failure this exists to prevent: a repeating region of a
Shell — the top bar, the side rail, the footer — gets written as a Component, and
then, because real sites need differently-populated bars, every part of that
Component is made optional. The entity model forbids both halves. A Component
contains HTML Elements; anything that ARRANGES Components is a Shape, and the
thing that receives a Shape is a Frame. Section extends Frame, so a region of a
frame is a Section. And per the Shape definition, "variability is handled by
selecting a different Shape, not by leaving positions open" — so a bar carrying a
mark alone and a bar carrying a mark, a menu, and an action are two Shapes over
ONE Section, never one Component with optional slots.

PROPERTY 1 — no Component claims to be a region of a frame.
    No entry under `reference/libraries/components/` may declare `pins_to:` or the
    retired `shell_edge:` / `shell_component:` keys. Pinning to a canvas edge is a
    Frame property.

PROPERTY 2 — a pinned Section names real edges and owns a surface.
    Every Section declaring `pins_to:` MUST name one or more edges from the closed
    set {block-start, block-end, inline-start, inline-end}, and MUST declare at
    least one of `sizing:` / `token_bindings:` — the Frame owns its own dimensions
    and properties. `pins_to` is the set of edges the Section MAY pin to; the
    ShellDefinition picks one per instance, because placement is the Shell's
    decision and never the library's.

PROPERTY 3 — a pinned Section declares no slots of its own.
    Contents come from the Shape it receives. A `slots:` block on a shell Section
    is the optional-slot anti-pattern reappearing one level up.

PROPERTY 4 — the Shape set a shell Section can receive is a real partition.
    Every Shape named by that Section's shape-selection rule MUST exist, MUST
    declare at least one slot, and no two of them may declare the SAME set of slot
    names. Two Shapes with identical slot sets mean the rule branches on something
    the arrangements do not actually express — the point at which "pick a different
    Shape" degenerates back into "make the slot optional".

Nothing is hardcoded but the closed edge vocabulary: the Sections, their rules,
and their Shapes are all discovered from the library, so a new shell region is
covered the day it lands.

Entry point:
    run(repo_root) -> list[str]   # empty list == all checks passed
"""

import os
import re

PLUGIN_SUBPATH = os.path.join("plugins", "cds")
COMPONENTS_LIB = os.path.join("reference", "libraries", "components")
SECTIONS_LIB = os.path.join("reference", "libraries", "sections")
SHAPES_LIB = os.path.join("reference", "libraries", "shapes")
SHAPE_RULES_DIR = os.path.join("reference", "rules", "shape-selection")

NON_ENTRY = {"FORMAT.md", "CONVENTIONS.md"}
EDGES = {"block-start", "block-end", "inline-start", "inline-end"}
EDGE_LIST = re.compile(r"[A-Za-z-]+")

SLOT_NAME = re.compile(r"\{\s*name:\s*([A-Za-z0-9_-]+)")


def _entries(root, lib):
    d = os.path.join(root, PLUGIN_SUBPATH, lib)
    if not os.path.isdir(d):
        return {}
    out = {}
    for n in sorted(os.listdir(d)):
        if not n.endswith(".md") or n in NON_ENTRY:
            continue
        with open(os.path.join(d, n), encoding="utf-8") as fh:
            out[n[:-3]] = fh.read()
    return out


def _frontmatter(text):
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def _block(fm, key):
    """Return the raw text of a top-level frontmatter key's value (inline or block)."""
    m = re.search(rf"^{key}:(.*)$", fm, re.M)
    if not m:
        return None
    value = m.group(1)
    rest = fm[m.end():]
    for line in rest.split("\n"):
        if line[:1] in (" ", "-") and line.strip():
            value += "\n" + line
        elif line.strip():
            break
    return value


def _slot_names(fm):
    raw = _block(fm, "slots")
    return set(SLOT_NAME.findall(raw)) if raw else set()


def run(repo_root):
    failures = []
    components = _entries(repo_root, COMPONENTS_LIB)
    sections = _entries(repo_root, SECTIONS_LIB)
    shapes = _entries(repo_root, SHAPES_LIB)
    rules = _entries(repo_root, SHAPE_RULES_DIR)

    if not sections or not shapes:
        return ["reference/libraries/{sections,shapes}/ has no entries"]

    # PROPERTY 1
    for name, text in components.items():
        fm = _frontmatter(text)
        for key in ("pins_to", "shell_edge", "shell_component"):
            if re.search(rf"^{key}:", fm, re.M):
                failures.append(
                    f"components/{name}.md: declares `{key}:` — a region of a "
                    "frame is a Section (Section extends Frame), not a Component. "
                    "Move the surface contract to reference/libraries/sections/ "
                    "and express its contents as Shapes.")

    shell_sections = {}
    for name, text in sections.items():
        fm = _frontmatter(text)
        m = re.search(r"^pins_to:\s*\[([^\]]*)\]", fm, re.M)
        if not m:
            continue
        edges = [e for e in EDGE_LIST.findall(m.group(1))]
        shell_sections[name] = fm

        # PROPERTY 2
        if not edges:
            failures.append(
                f"sections/{name}.md: `pins_to:` names no edge — a pinned Section "
                "must name at least one edge it may pin to")
        for edge in edges:
            if edge not in EDGES:
                failures.append(
                    f"sections/{name}.md: pins_to edge `{edge}` is not one of "
                    f"{sorted(EDGES)}")
        if not (_block(fm, "sizing") or _block(fm, "token_bindings")):
            failures.append(
                f"sections/{name}.md: pins to {edges} but declares neither "
                "`sizing:` nor `token_bindings:` — a Frame owns its own "
                "dimensions and properties")

        # PROPERTY 3
        if _block(fm, "slots"):
            failures.append(
                f"sections/{name}.md: declares `slots:` — a pinned Section's "
                "contents are the contract of the Shape it receives. Optional "
                "slots on the region are the anti-pattern Shapes exist to replace.")

    # PROPERTY 4
    for name, fm in shell_sections.items():
        eager = re.search(r"^shape:\s*(\S+)", fm, re.M)
        named = []
        if eager:
            named = [eager.group(1).strip()]
        else:
            rule = rules.get(name)
            if rule is None:
                failures.append(
                    f"sections/{name}.md: no eager `shape:` and no "
                    f"rules/shape-selection/{name}.md — lazy assignment has "
                    "nothing to run")
                continue
            rfm = _frontmatter(rule)
            named = re.findall(r"primary:\s*([A-Za-z0-9_-]+)", rfm)
            for alts in re.findall(r"alternates:\s*\[([^\]]*)\]", rfm):
                named += [a.strip() for a in alts.split(",") if a.strip()]
            d = re.search(r"^default:\s*(\S+)", rfm, re.M)
            if d:
                named.append(d.group(1).strip())

        seen = {}
        for shape in dict.fromkeys(named):
            text = shapes.get(shape)
            if text is None:
                failures.append(
                    f"sections/{name}.md: offered Shape `{shape}` has no entry "
                    "in reference/libraries/shapes/")
                continue
            slots = _slot_names(_frontmatter(text))
            if not slots:
                failures.append(
                    f"shapes/{shape}.md: declares no slots, so it arranges "
                    f"nothing for the `{name}` Section")
                continue
            key = frozenset(slots)
            if key in seen:
                failures.append(
                    f"shapes/{shape}.md and shapes/{seen[key]}.md offer the "
                    f"`{name}` Section identical slot sets "
                    f"({sorted(slots)}) — two Shapes that arrange the same parts "
                    "are not a partition of the region's variability")
            else:
                seen[key] = shape

    return failures


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    out = run(root)
    print("PASS" if not out else "FAIL")
    for f in out:
        print("  -", f)
