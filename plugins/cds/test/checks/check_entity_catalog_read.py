#!/usr/bin/env python3
"""
check_entity_catalog_read — the entity catalog is read in full at every entry point.

`reference/model/entity-catalog.md` is the normative Building Blocks model. It is
not a name/definition list: the Type / Extends / Construct / Contains columns carry
meaning that the descriptions alone do not, inheritance through `Extends` is
transitive, `Contains` never implies "is a container", `Abstract` vs `Concrete` is
deliberate per entity, and `can` / `may` / `typically` grant permission rather than
impose obligation. An agent that skims it, samples it, or works from a remembered
summary of it silently mis-models the system — the failure mode this check exists
to make impossible to reintroduce quietly.

PROPERTY 1 — the catalog states its own reading rules.
    `reference/model/entity-catalog.md` MUST carry a "How to read this catalog"
    section and MUST state, in some form, each of the four rules above.

PROPERTY 2 — every entry point mandates the full read.
    Every `skills/*/SKILL.md` and every `agents/*.md` MUST carry a "Read the model
    first" section that cites `reference/model/entity-catalog.md` and requires it be
    read IN FULL. A file opts out only by declaring `entity_catalog_read:
    not-applicable` in its frontmatter, with the reason stated inline.

PROPERTY 3 — the mandate is the first thing the file says.
    Where present, the "Read the model first" section MUST be the first `##` heading
    in the file. A read-the-model rule buried below the working instructions is a
    rule that gets reached after the work has already started.

No skill names, agent names, or counts are hardcoded — the entry points are
discovered from the filesystem, so a new skill or agent is covered the day it lands.

Entry point:
    run(repo_root) -> list[str]   # empty list == passed
"""

import os
import re

PLUGIN_SUBPATH = os.path.join("plugins", "cds")
CATALOG_SUBPATH = os.path.join("reference", "model", "entity-catalog.md")

HEADING = "Read the model first"
OPT_OUT = re.compile(r"^entity_catalog_read:\s*not-applicable\b", re.M)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)

# Each reading rule, as (label, alternative phrasings any one of which satisfies it).
CATALOG_RULES = [
    ("transitive inheritance", ("transitive",)),
    ("Contains is not a container", ("is a container", "container semantics")),
    ("Abstract/Concrete is deliberate", ("deliberate", "deliberately")),
    ("can/may is not must", ("never mean `must`", "never impose obligation",
                             "grant permission")),
]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _entry_points(plugin_root):
    """Every SKILL.md and agent definition, discovered — never enumerated."""
    found = []
    skills_dir = os.path.join(plugin_root, "skills")
    if os.path.isdir(skills_dir):
        for name in sorted(os.listdir(skills_dir)):
            path = os.path.join(skills_dir, name, "SKILL.md")
            if os.path.isfile(path):
                found.append((f"skills/{name}/SKILL.md", path))
    agents_dir = os.path.join(plugin_root, "agents")
    if os.path.isdir(agents_dir):
        for name in sorted(os.listdir(agents_dir)):
            if name.endswith(".md"):
                found.append((f"agents/{name}", os.path.join(agents_dir, name)))
    return found


def run(repo_root):
    failures = []
    plugin_root = os.path.join(repo_root, PLUGIN_SUBPATH)
    catalog_path = os.path.join(plugin_root, CATALOG_SUBPATH)

    # PROPERTY 1 — the catalog states its own reading rules.
    if not os.path.isfile(catalog_path):
        return [f"{CATALOG_SUBPATH}: normative entity catalog is missing"]

    catalog = _read(catalog_path)
    if "## How to read this catalog" not in catalog:
        failures.append(
            f"{CATALOG_SUBPATH}: no '## How to read this catalog' section — the "
            "columns' semantics must be stated in the file that carries them")
    for label, phrasings in CATALOG_RULES:
        if not any(p in catalog for p in phrasings):
            failures.append(
                f"{CATALOG_SUBPATH}: reading rule not stated — {label}")
    if "in full" not in catalog.lower():
        failures.append(
            f"{CATALOG_SUBPATH}: does not declare itself a full read")

    # PROPERTIES 2 and 3 — every entry point mandates it, first.
    entries = _entry_points(plugin_root)
    if not entries:
        failures.append("no skills or agents discovered under plugins/cds")

    for rel, path in entries:
        text = _read(path)
        fm = FRONTMATTER.match(text)
        if fm and OPT_OUT.search(fm.group(1)):
            continue

        headings = re.findall(r"^##\s+(.+?)\s*$", text, re.M)
        if HEADING not in headings:
            failures.append(
                f"{rel}: no '## {HEADING}' section — every entry point must "
                "require the full read of reference/model/entity-catalog.md, or "
                "declare `entity_catalog_read: not-applicable` with a reason")
            continue
        if headings[0] != HEADING:
            failures.append(
                f"{rel}: '## {HEADING}' is not the first section (found "
                f"'{headings[0]}' first) — the mandate must precede the work")

        body = text[fm.end():] if fm else text
        section = body.split(f"## {HEADING}", 1)[1].split("\n## ", 1)[0]
        if "entity-catalog.md" not in section:
            failures.append(
                f"{rel}: '## {HEADING}' does not cite "
                "reference/model/entity-catalog.md")
        if "in full" not in section.lower():
            failures.append(
                f"{rel}: '## {HEADING}' does not require the catalog be read "
                "IN FULL")

    return failures


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    for f in run(root):
        print(f)
