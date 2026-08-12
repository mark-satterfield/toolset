#!/usr/bin/env python3
"""
check_decisions_conformance — composed output used the library it claims to.

Guards the two composer-side properties that no other check covers, and that a
style audit cannot see: a Page can satisfy every rule in `compliance.md` and
still render a Shape the library never offered, or render a self-contained
Shape whose behavior was never emitted. Both failures are silent — the artifact
looks finished and is structurally wrong.

Reads the decisions sidecar the pipeline already emits beside every composed
output (`<basename>.decisions.md`), so it verifies what a composer actually did
rather than re-deriving intent from markup.

PROPERTY 1 — a rendered Shape came from a rung of the waterfall, and says which.
    The Shape-assignment waterfall (`reference/pipeline.md`) has four rungs: the
    Section's own rule, then any other library Shape unmodified, then the closest
    library Shape adapted, then generation from scratch. For each Section recorded
    in a decisions sidecar, the recorded Shape MUST be one of:
      (a) a candidate in that Section's shape-selection rule (a `primary:`, an
          `alternates:` entry, or the `default:`) — rung 1;
      (b) the Section's eager `shape:` frontmatter;
      (c) a Shape recorded as library-sourced or library-adapted — rungs 2 and 3;
      (d) recorded as fallback-generated — rung 4.
    A Shape from outside the rule's candidate set that claims NO rung means the
    composer reached past the rules silently, which is the failure this catches.

PROPERTY 3 — a library-sourced or library-adapted Shape is a real Shape.
    Rungs 2 and 3 exist to reuse the library, so a record claiming either MUST
    name a Shape that has an entry in `reference/libraries/shapes/`. Only rung 4
    may produce a layout with no entry behind it — that is what makes it the last
    resort rather than an escape hatch with a nicer label.

PROPERTY 2 — a self-contained Shape carried its behavior.
    A Shape whose entry declares `self_contained: true` owns its own scoped
    `<style>` and, where the behavior is not pure CSS, a scoped `<script>`.
    When such a Shape is recorded in a sidecar, the composed HTML beside it
    MUST contain a `<style>` inside the document body — behavior deferred to
    the generated component stylesheet is the failure the entries call out by
    name.

Scope: runs only where composed output exists. A repo with no decisions
sidecars passes trivially — this check constrains composers, not the library.

Entry point:
    run(repo_root) -> list[str]   # empty list == all checks passed
"""

import os
import re

PLUGIN_SUBPATH = os.path.join("plugins", "cds")

SHAPES_LIB = os.path.join("reference", "libraries", "shapes")
SECTIONS_LIB = os.path.join("reference", "libraries", "sections")
SHAPE_RULES_DIR = os.path.join("reference", "rules", "shape-selection")

# Directories a composer may write output into, relative to the repo root.
OUTPUT_ROOTS = (os.path.join("plugins", "cds", "test", "visual-proof-out"),)

NON_ENTRY = {"FORMAT.md", "CONVENTIONS.md"}

FALLBACK_MARKERS = ("fallback-generated", "fallback generation")
# Rungs 2 and 3: the composer reached past the rule's table into the library.
LIBRARY_RUNG_MARKERS = ("library-sourced", "library-adapted")


def _frontmatter(text):
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def _read(path):
    return open(path, encoding="utf-8").read()


def _library(repo_root):
    """candidates[section] -> set of offered shape names; self_contained shape set."""
    base = os.path.join(repo_root, PLUGIN_SUBPATH)
    candidates = {}
    rules_dir = os.path.join(base, SHAPE_RULES_DIR)
    if os.path.isdir(rules_dir):
        for basename in sorted(os.listdir(rules_dir)):
            if not basename.endswith(".md") or basename in NON_ENTRY:
                continue
            front = _frontmatter(_read(os.path.join(rules_dir, basename)))
            served = re.search(r"^section:\s*(\S+)\s*$", front, re.MULTILINE)
            if not served:
                continue
            offered = set(re.findall(r"primary:\s*([A-Za-z0-9-]+)", front))
            for match in re.finditer(r"alternates:\s*\[([^\]]*)\]", front):
                offered.update(s.strip() for s in match.group(1).split(",") if s.strip())
            offered.update(re.findall(r"^default:\s*([A-Za-z0-9-]+)\s*$", front, re.MULTILINE))
            candidates[served.group(1)] = offered

    # An eagerly-assigned Section names its own Shape; that name is also legal.
    sections_dir = os.path.join(base, SECTIONS_LIB)
    if os.path.isdir(sections_dir):
        for basename in sorted(os.listdir(sections_dir)):
            if not basename.endswith(".md") or basename in NON_ENTRY:
                continue
            front = _frontmatter(_read(os.path.join(sections_dir, basename)))
            name_match = re.search(r"^name:\s*(\S+)\s*$", front, re.MULTILINE)
            name = name_match.group(1) if name_match else basename[:-3]
            eager = re.search(r"^shape:\s*(\S+)\s*$", front, re.MULTILINE)
            if eager:
                candidates.setdefault(name, set()).add(eager.group(1))

    self_contained = set()
    known_shapes = set()
    shapes_dir = os.path.join(base, SHAPES_LIB)
    if os.path.isdir(shapes_dir):
        for basename in sorted(os.listdir(shapes_dir)):
            if not basename.endswith(".md") or basename in NON_ENTRY:
                continue
            front = _frontmatter(_read(os.path.join(shapes_dir, basename)))
            name_match = re.search(r"^name:\s*(\S+)\s*$", front, re.MULTILINE)
            name = name_match.group(1) if name_match else basename[:-3]
            known_shapes.add(name)
            if re.search(r"^self_contained:\s*true\s*$", front, re.MULTILINE):
                self_contained.add(name)
    return candidates, self_contained, known_shapes


def _sidecars(repo_root):
    for output_root in OUTPUT_ROOTS:
        directory = os.path.join(repo_root, output_root)
        if not os.path.isdir(directory):
            continue
        for dirpath, _dirnames, filenames in os.walk(directory):
            for basename in sorted(filenames):
                if basename.endswith(".decisions.md"):
                    yield os.path.join(dirpath, basename)


def _recorded_sections(text):
    """(section-name, shape-name, block-text) per Section recorded in a sidecar."""
    recorded = []
    blocks = re.split(r"^#{2,4}\s+", text, flags=re.MULTILINE)
    for block in blocks:
        section = re.search(r"^\s*[-*]\s*\*\*Section:?\*\*\s*`?([A-Za-z0-9-]+)`?", block, re.MULTILINE)
        if not section:
            section = re.search(r"[-—]\s*([a-z0-9-]+)\s*$", block.split("\n", 1)[0].strip())
        shape = re.search(r"^\s*[-*]\s*\*\*Shape:?\*\*\s*`?([A-Za-z0-9-]+)`?", block, re.MULTILINE)
        if section and shape:
            recorded.append((section.group(1), shape.group(1), block))
    return recorded


def run(repo_root):
    failures = []
    candidates, self_contained, known_shapes = _library(repo_root)

    for sidecar in _sidecars(repo_root):
        rel = os.path.relpath(sidecar, repo_root)
        text = _read(sidecar)
        artifact = sidecar[: -len(".decisions.md")] + ".html"
        artifact_html = _read(artifact) if os.path.isfile(artifact) else ""

        for section, shape, block in _recorded_sections(text):
            if any(marker in block.lower() for marker in FALLBACK_MARKERS):
                continue  # fallback generation is a recorded, legal outcome

            lowered = block.lower()
            from_library_rung = any(m in lowered for m in LIBRARY_RUNG_MARKERS)

            if from_library_rung:
                # PROPERTY 3 — rungs 2 and 3 reuse the library, so the Shape must exist.
                if known_shapes and shape not in known_shapes:
                    failures.append(
                        f"{rel}: section '{section}' records shape '{shape}' as reached through "
                        f"the library rung of the waterfall, but no entry for it exists in "
                        f"reference/libraries/shapes/ — only fallback generation may produce a "
                        f"layout with no entry behind it"
                    )
            else:
                offered = candidates.get(section)
                if offered is None:
                    continue  # Section not in the library; check_shape_conformance owns that
                if shape not in offered:
                    failures.append(
                        f"{rel}: section '{section}' rendered with shape '{shape}', which its rule "
                        f"does not offer (candidates: {', '.join(sorted(offered)) or 'none'}) and "
                        f"which claims no rung of the Shape-assignment waterfall. Record it as "
                        f"library-sourced, library-adapted, or fallback-generated "
                        f"(reference/pipeline.md)."
                    )

            if shape in self_contained and artifact_html:
                body = artifact_html[artifact_html.find("<body") :]
                if "<style" not in body:
                    failures.append(
                        f"{rel}: shape '{shape}' declares self_contained: true but "
                        f"{os.path.basename(artifact)} carries no scoped <style> in its body — "
                        f"its behavior is deferred to the generated stylesheet, which does not "
                        f"provide it"
                    )

    return failures


if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    problems = run(root)
    for problem in problems:
        print(problem)
    sys.exit(1 if problems else 0)
