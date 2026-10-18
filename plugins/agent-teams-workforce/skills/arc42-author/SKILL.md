---
name: arc42-author
description: >-
  Writes the architecture documents of a subject that has none, to the
  project's architecture documentation model: a new service, component or
  concept, or the first documents of a new architecture in the arc42 section
  folders. Each document is a diagram (Mermaid) and the prose around it, at the
  scope it describes, with the catalog front matter. It writes no constraints,
  no decision records and no section 9. Use when the user asks to write, scaffold
  or start the architecture documents of a subject that has none.
triggers:
  - add the documents for a new service
  - write the documents of a new subject
  - create the architecture documentation
  - scaffold arc42
  - bootstrap arc42
  - document the system architecture
  - write a building block view
  - write a runtime view
  - write a deployment view
  - write a crosscutting concept
---

# arc42 Author — write the documents of a new subject

You write architecture documents for a subject the architecture does not yet describe:

- **The documents of a new subject** in `arc42/`: a new service, component or concept.
- **A new architecture** in `arc42/`, when the project has none.

A change to a subject that already has documents is `arc42-maintain`: it writes decided design
facts into the effective documents, each in its one home. Checking documents is `arc42-verify`.

## Read first

1. The project's architecture documentation model (the MODEL), at
   `reference/architecture-documentation-model.md` under the architecture root the router resolved.
   It is the authority for what goes where; this skill tells you how to write it.
2. The list of diagram and model types (the MENU), at `reference/diagram-and-model-types.md`.
3. `../arc42/references/` — the section model, the living-document rules and how to find the
   documents that describe an element.
4. This skill's `references/section-templates.md` — what each section's documents hold and the
   Mermaid skeletons.

## What the documents start from

- the owner's constraints in `arc42/02-architecture-constraints/`;
- the strategy in `arc42/04-solution-strategy/`;
- the design the caller gives you for the subject: its design facts, each with its reason;
- the effective documents that describe the elements the subject connects to, which the matrix
  names (`../arc42/references/finding-views.md`).

An `in-review` document, and code that no pipeline built, is input to check and not evidence that
a design is right.

## Procedure

1. **Name the subject.** The service, component or concept the documents describe, as the glossary
   and the stack names name it. It names the subject folder and appears in every document's
   `subject`. It is never a PRD, an Epic, a bead id or a date.
2. **Confirm the subject has no documents.** Ask the matrix:
   `atw-matrix find --kinds document --text "<subject>"` returns the documents whose subject,
   name or headings match, and `atw-matrix node <id>` for the subject's own entry (found with
   `atw-matrix find --text "<subject>"`) names under `describedBy` each document and heading that
   describes it. When the matrix names documents for the subject, the work is `arc42-maintain`.
3. **Choose the documents the subject needs.** The MODEL's table of documents by scope is where to
   start, and the MENU says which type answers which reader question. Write only the documents the
   design supports.
4. **Write each document as a diagram and its prose.** The diagram (Mermaid, fenced in the file)
   shows structure and flow. The prose states what the document is for, what the diagram cannot
   show (reasons, limits) and where the neighbouring documents are. Each document goes in the
   section folder the MODEL names, inside the subject's folder, and is named for its subject.
5. **State each design fact in one home.** Section 5 holds what a building block is responsible
   for, what it owns and its interfaces by name; section 6 holds which blocks interact, in what
   order; section 7 holds where each block runs; section 8 holds a rule with its reason. A document
   that needs a fact whose home is elsewhere links to that heading
   (`../arc42/references/arc42-section-model.md`).
6. **Keep to architecture level.** A route path, a field name, a key or index name, a parameter
   name, a metric or alarm name and a schema belong to the TRD or the specs, not to an arc42
   document.
7. **Add the catalog front matter** to every document: `view_type` (a type from the MENU), `scope`,
   `subject`, `shows` (every element in the document, by the name the matrix holds for its
   entry, which is its glossary name or its stack name) and `lifecycle_state: in-review`. Keep
   any classification fields the project uses beside them. `atw-matrix sync-documents` reads
   this front matter and the headings, and records the document as describing each entry that
   `shows` and `subject` name, so a name the matrix does not hold joins the document to nothing.
8. **Link the documents in.** Each new document links its parent and its neighbours, and the
   section entry point gives a route to it, as the MODEL's navigation rules say.
9. **Report** the documents written, by path, so that the caller's script step runs
   `atw-matrix sync-documents --paths` on them; the checks made on each diagram (it renders, it
   is readable, it shows what its type promises); each name in a `shows` that the matrix holds
   no entry for; and anything the design did not let you write.

## What a document contains

- A description of the design, in present tense.
- Reasons where a reader needs them, in the prose around the diagram.
- Claims about AWS that a reviewer can check against the AWS documentation.

A document names stacks, services and components and never repositories; the matrix is the record
of which repository holds each stack (`atw-matrix node stack:<id>`). A deployed element is named by its stack
name from the project's naming standard (the project's naming command: `name build cdk-stack ...`; the `resource-naming` skill).

A document holds no requirements, history, decision records, rules ("services MUST …") or open
items (`../arc42/references/living-document-rules.md`). A question the inputs cannot answer goes
in your report to the caller.

## Section 2 is the owner's

Section 2 holds the owner's constraints. You read them and write nothing in
`02-architecture-constraints/` (`references/constraints-guide.md`). When a design would need a
constraint to change, report that to the caller with the reason.

## A new architecture

When the project has no architecture yet, create `arc42/` with one folder per section,
`01-introduction-and-goals/` through `12-glossary/` (no section 9), each with a `README.md`. Write
the documents the inputs support, starting from the system scope: context (section 3), container
(section 5 entry point), system flows (section 6), system deployment (section 7 entry point). The
MODEL says whether an entry point embeds or links its highest-scope document. Section 2's
`README.md` is the owner's to fill. A section the inputs cannot fill yet stays as its folder and a
`README.md` holding only the section title; the gap goes in your report.

## What is outside this skill

- Changing an effective document: `arc42-maintain`.
- Constraints, decision records, ADRs and a section 9.
- Approval: every file you write is `in-review`, and a script sets `effective` after review.

## References

- `references/section-templates.md` — what each section's documents hold, per scope, with Mermaid
  skeletons.
- `references/constraints-guide.md` — what a constraint is, and that section 2 is read and never
  written.
- `references/solution-strategy-guide.md` — what section 4 holds.
- `references/crosscutting-concepts-guide.md` — how a section 8 concept is written.
- `../arc42/references/` — the shared section model, living-document rules and how to find
  documents.
