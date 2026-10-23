---
name: arc42-maintain
description: >-
  Maintains the effective architecture documents, arc42 and the detailed
  architecture (detailed/), to the project's architecture documentation model. It writes the solutions architect's decisions into the
  documents, each design fact in its one home with links from every other
  document that needs it, and corrects the documents from what a Story built.
  It writes nothing in section 2, which is the owner's. Use when the user asks
  to write decided design facts into arc42 or the detailed architecture, bring the architecture up to date
  with what was built, or replace a restated fact with a link to its home.
triggers:
  - write the decisions into arc42
  - update the effective architecture
  - correct the architecture from the build
  - the build differs from the architecture
  - keep the architecture current
  - maintain the arc42 documentation
---

# arc42 Maintain — keep the effective documents current

You change the effective documents: the arc42 documents in `arc42/` and, below arc42's level,
the documents in `detailed/`. They change in two ways only:

- **Decisions.** The solutions architect decided design facts. A write request lists each
  fact with its statement and reason, its one home (document and heading) and the documents
  that link to it.
- **Correction from built.** `built/<element>/` records where a Story's build differs from
  the approved architecture. The documents are corrected to match what was built.

The design is the solutions architect's. A fact that is not in the request is not written.

## Read first

- The MODEL at `reference/architecture-documentation-model.md` under the architecture root, and the
  MENU at `reference/diagram-and-model-types.md`.
- `../arc42/references/arc42-section-model.md` — what each section and each `detailed/` folder
  holds, the one home of each design fact, where a fact goes (arc42 or `detailed/`) and the two
  document classes — and `../arc42/references/living-document-rules.md`.
- `references/consistency-rules.md` — what holds across documents after every pass.

## The procedure

1. **Take each fact of the request in turn.** Write it in its home, under the heading named, in
   the form its section requires (the section model lists the forms).
2. **Replace restatements with links.** In every other document the request names, and in every
   document the matrix lists as describing the same entry (`atw-matrix node <entry id>` names
   each under `describedBy`, with its heading and `lifecycle`), a restatement of the fact becomes
   a link to the home heading. A fact is stated in one place.
3. **Apply settled disagreements.** The statement that stands stays; each statement that lost is
   replaced by a link to it.
4. **Write the detail where the MODEL places it.** A fact the MODEL places below arc42's level
   (a class or object model, a data model with its attributes, columns, keys and types, an
   interface or payload schema, a route, a name) is written in its document under `detailed/`,
   and the arc42 view of its subject links to it. No entry is returned for being too detailed.
5. **Create a document only for a home path that does not exist**, with the front matter of its
   class (the artifact-handoff skill's `schemas/document-front-matter.schema.json`): a view's
   catalog front matter (`view_type`, `scope`, `subject`, `shows`, `lifecycle_state`, `purpose`),
   or for a standard or policy `document_class: standard` or `policy` with no `view_type`,
   `scope`, `shows` or diagram; and a file name that names its subject. Extend an existing view of
   the same subject and scope rather than create a second one.
6. **Place and update diagrams.** Place each diagram the request carries; update or redraw a
   diagram when a fact changes what it shows; check that it renders and reads well.
7. **Keep the catalog true and check the invariants** in `references/consistency-rules.md` across
   every document you touched and every document that links to them.
8. **Report**: each heading changed or created, each link added, each restatement removed, and
   what could not be applied with the reason. For a write request, set `lifecycle_state:
   in-review` on each `effective` document you edit and on each new one; a script moves them to
   `effective` after review. A correction from built leaves every `lifecycle_state` as it is. You record nothing
   in the matrix: a script step runs `atw-matrix sync-documents --paths` on the files you report,
   which mirrors each document, its headings and what its `shows` names. A correction from built
   is mirrored by the next run's sync.

## Section 2 is the owner's

You write nothing under `arc42/02-architecture-constraints/`. A fact that conflicts with a
constraint is reported and left unwritten. A correction from built is made even when it conflicts
with a constraint, so that the documents describe the system as it is; report the conflict with the
correction, so the owner can change the build or the constraint.

## What "in place" means

- A document reads as if its current content were always true: no "previously", no changelog, no
  superseded content kept for reference.
- No open item is written into any document. What is still open goes in the report.
- A rule is written in section 8 as a design fact with its reason. There are no decision records.
- A document names stacks, services and components and never repositories; the matrix is the
  record of which repository holds each stack (`atw-matrix node stack:<id>`).

## References

- `references/consistency-rules.md` — the invariants that hold across documents after every pass.
- `../arc42/references/` — the shared section model and living-document rules.
