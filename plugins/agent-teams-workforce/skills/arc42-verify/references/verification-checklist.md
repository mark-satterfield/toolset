# Verification checklist — layout, naming and catalog

This file holds the assertions for two of the four families: **layout and naming** (the folders and
file names follow the MODEL) and **catalog** (every view declares what it describes). Run layout
first: a view in the wrong place is reported once there, and its catalog checks still run.

## Part A — Layout and naming

| Check | PASS when | FAIL when |
|---|---|---|
| Section folders | `arc42/` holds one folder per section, `01-introduction-and-goals/` through `12-glossary/`, each with a `README.md` | A section is a single file, a folder lacks `README.md`, or a section folder is missing |
| Detailed architecture | `detailed/` holds `system/`, `cross-component/`, `components/<component>/` and `features/<feature>/`, each folder with a `README.md` that states what belongs there and lists its documents | A `detailed/` folder lacks its `README.md`; a folder named for a PRD, Epic, bead id or date |
| No section 9 | No `09-*` folder or file, and no decision-record section | A section 9 or a decision log exists |
| View placement | Each view sits where the MODEL's view table places it for its scope and view type (structure in 5, behaviour in 6, deployment in 7, concepts in 8, context in 3, and the detailed design of a component, a feature, components working together or the whole system under `detailed/`) | A sequence diagram in section 5, a deployment view in section 6, a concept outside section 8, a feature view in a service's folder |
| Subject folders | Inside a section, views below the system scope sit in folders named for their domain, service or component | Service views loose at the section root among system views |
| Names | Files and folders are named for their subject | A name carries a PRD, an Epic, a bead id, a date or a pipeline gate (`-adjudicated`, `-v2`, `-proposal`) |
| Versions | Effective documents are in `arc42/` and `detailed/`; built documents are in `built/<element>/` with the arc42 section layout | A built document inside `arc42/`; a built folder named for an Epic or a date |
| Diagrams in views | Actual content fulfils the declared type and the MODEL/MENU construction requirements; rendering, visual readability and semantics were checked separately | A diagram declaration with no diagram, unsupported notation/semantics, or a failed check; report an unavailable check explicitly instead of passing it |
| Navigation | The MODEL-required entry points, highest-scope views and adjacent-view links are present and usable | A subject is unreachable through required navigation or a highest-scope obligation is left to an index alone |
| Section 2 | `02-architecture-constraints/` holds only its `README.md` with the owner's constraints | Other files in section 2 |
| Section 4 | `04-solution-strategy/README.md` is about one page of enterprise-level direction | Implementation detail (one service's technology, a table design) in section 4 — `WARN`; a section 4 several times that length — `FAIL` |

## Part B — Catalog

Every Markdown file under the version being verified, other than a folder index that holds no view,
is of one of two classes, whose front matter the artifact-handoff skill's
`schemas/document-front-matter.schema.json` defines: a view (`$defs/ArchitectureView`), or a
standard or policy (`$defs/ArchitectureStandard`). A view carries the catalog front matter below.
A standard or policy carries `document_class: standard` or `policy`, `lifecycle_state`,
`authority`, `provenance` and `purpose`; a `view_type`, `scope`, `shows` or diagram on it is a
`FAIL`, and the view checks below do not apply to it.

| Field | PASS when | FAIL when |
|---|---|---|
| `view_type` | Present, and a type the MENU lists | Missing, or a type the MENU does not list |
| `scope` | One of `system`, `domain`, `cross-component`, `service`, `component`, `feature`, `concept` | Missing or another value |
| `subject` | Present, and the one thing the view describes, named as the glossary or its stack name names it, never by a repository name | Missing; names a PRD, Epic, bead or date |
| `shows` | Names the architectural elements actually shown, by glossary or stack name and never by repository name, at the declared abstraction, including a justified prose-only model where the MODEL permits one | Missing or inconsistent with the actual content; name the missing or unsupported element |
| `lifecycle_state` | `in-review` or `effective` | Missing or another value; a file marked `effective` that no review approved |
| `purpose` | One sentence: why the document exists and who acts on it | Missing |
| Scope and place agree | A `scope: service` view sits in that service's subject folder; a `scope: concept` view sits in section 8; a `scope: feature` view sits under `detailed/features/<feature>/`; a `scope: cross-component` view sits under `detailed/cross-component/` | Scope and folder disagree |

## How to report from this file

For each check, emit one verdict line, `[STATUS] <path> — <observation>`, with an indented
`evidence:` line quoting the frontmatter or the file name, or naming the absence. Report only what is
and is not true; do not propose the fix.

## Coverage evidence

Apply the MODEL's coverage obligations to the independently established subject
inventory. Use the MODEL's applicability conditions and assessment vocabulary, not a fixed count
of view types. A catalog label or Mermaid fence is not proof of adequate coverage. Record a named
absence only after checking the relevant files and inventory; record insufficient evidence as
unassessed. Prose-only exceptions need the MODEL's rationale and honest type, not an automatic pass.
