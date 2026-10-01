# Verification checklist — layout, naming and catalog

This file holds the assertions for two of the four families: **layout and naming** (the folders and
file names follow the MODEL) and **catalog** (every view declares what it describes). Run layout
first: a view in the wrong place is reported once there, and its catalog checks still run.

## Part A — Layout and naming

| Check | PASS when | FAIL when |
|---|---|---|
| Section folders | `arc42/` holds one folder per section, `01-introduction-and-goals/` through `12-glossary/`, each with a `README.md` | A section is a single file, a folder lacks `README.md`, or a section folder is missing |
| No section 9 | No `09-*` folder or file, and no decision-record section | A section 9 or a decision log exists |
| View placement | Each view sits in the section the MODEL's view table names for its scope and view type (structure in 5, behaviour in 6, deployment in 7, concepts in 8, context in 3) | A sequence diagram in section 5, a deployment view in section 6, a concept outside section 8 |
| Subject folders | Inside a section, views below the system scope sit in folders named for their domain, service or component | Service views loose at the section root among system views |
| Names | Files and folders are named for their subject | A name carries a PRD, an Epic, a bead id, a date or a pipeline gate (`-adjudicated`, `-v2`, `-proposal`) |
| Versions | Target views are in `target/<subject>/` with the arc42 section layout, the delta in `target/<subject>/delta/`, built in `built/<subject>/` | A target view inside `arc42/`; a delta outside its target; a `<subject>` named for an Epic or a date |
| Diagrams in views | Diagrams are Mermaid in the view files they belong to | A diagram in a folder outside the sections, or a binary diagram format with no Mermaid view |
| Section 2 | `02-architecture-constraints/` holds only its `README.md` with the owner's constraints | Other files in section 2 |
| Section 4 | `04-solution-strategy/README.md` is about one page of enterprise-level direction | Implementation detail (one service's technology, a table design) in section 4 — `WARN`; a section 4 several times that length — `FAIL` |

## Part B — Catalog

Every view file (every Markdown file under the version being verified other than a folder index that
holds no view) carries the catalog frontmatter.

| Field | PASS when | FAIL when |
|---|---|---|
| `view_type` | Present, and a type the MENU lists | Missing, or a type the MENU does not list |
| `scope` | One of `system`, `domain`, `service`, `component`, `concept` | Missing or another value |
| `subject` | Present, and the one thing the view describes, named as the glossary and repositories name it | Missing; names a PRD, Epic, bead or date |
| `shows` | A list of every element in the view's diagram | Missing; an element in the diagram absent from the list (`FAIL`); a listed element the diagram does not contain (`WARN`) |
| `lifecycle_state` | `in-review` or `effective` | Missing or another value; a target or delta file marked `effective` before approval |
| Scope and place agree | A `scope: service` view sits in that service's subject folder; a `scope: concept` view sits in section 8 | Scope and folder disagree |

## How to report from this file

For each check, emit one verdict line, `[STATUS] <path> — <observation>`, with an indented
`evidence:` line quoting the frontmatter or the file name, or naming the absence. Report only what is
and is not true; do not propose the fix.
