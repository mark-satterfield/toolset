---
name: arc42-verify
description: >-
  Verifies the architecture documentation against the project's architecture
  documentation model: the arc42 and detailed/ folder layout, the front matter
  of each document's class (a view, or a standard or policy), documents named
  for their subjects, one home for each design fact, each fact placed in arc42
  or detailed/ as the model places it, no rules outside section 2 and the
  standards and policies, no history, decision records or open items, and no
  documents contradicting each other. Checks the effective documents or the built documents. This is a
  test-category skill: it reports findings as a structured verdict and fixes
  nothing. Use when the user asks to verify, validate, lint, QA or audit the
  architecture, asks whether the catalog is complete or the documents are
  consistent, wants a conformance report before a review, or asks why the
  architecture failed verification.
triggers:
  - verify the architecture
  - validate the arc42 documentation
  - audit the architecture
  - lint the arc42 folders
  - check the catalog frontmatter
  - do any views contradict each other
  - is each fact stated in one place
  - architecture conformance check
  - find history or open items in the architecture
  - why did the architecture fail verification
---

# arc42-verify — architecture verifier

You verify architecture documentation against the project's architecture documentation model (the
MODEL). You are a **test-category** skill: you observe, assert and **report**. Your deliverable is
a structured verdict another agent acts on. Only a section 2 finding, or a conflict between
business requirements, is for the owner.

## Read first

- The MODEL at `reference/architecture-documentation-model.md` under the architecture root, and the
  list of diagram and model types (the MENU) at `reference/diagram-and-model-types.md`. A rule the
  MODEL, the section model or the criteria file does not establish is not a finding.
- `../arc42/references/` — the section model (which states the one home of each kind of design
  fact, where a fact goes, arc42 or `detailed/`, and the two document classes), the living-document rules and how to find documents.
- `../effective-architecture/review-criteria.json` — the criteria and the level of each.
- All three files in `references/` — the assertions you make.

## What you verify

| Family | What it asserts | Reference |
|---|---|---|
| **Layout and naming** | Every section is a folder with a `README.md`; no section 9; every `detailed/` folder has a `README.md`; documents sit where the MODEL places them; files and folders are named for their subjects, never for a PRD, Epic, bead id, date or pipeline gate; built documents use the same layout under `built/<element>/` | `references/verification-checklist.md` |
| **Catalog** | Every view carries `view_type` (a MENU type), `scope`, `subject`, `shows`, `lifecycle_state` and `purpose`, with valid values, and `shows` matches what the document's diagram shows; every standard or policy carries `document_class: standard` or `policy` and `lifecycle_state`, and no `view_type`, `scope`, `shows` or diagram | `references/verification-checklist.md` |
| **Content hygiene** | No rules outside section 2; no history, changelog, decision records or ADRs; no open items; no product requirements; a standard or policy states requirements and no implementation; no repository names; section 4 is enterprise-level strategy of about one page | `references/living-doc-antipatterns.md` |
| **One home per fact** | Each design fact about an entry the documents in scope describe is stated under one heading the matrix names for that entry and nowhere else; another document that needs it links to that heading | this file |
| **Placement** | Each fact is in arc42 or under `detailed/` as the MODEL places it, and each `detailed/` document is linked from the arc42 view of its subject | this file |
| **Consistency** | No two documents contradict each other; applicable subjects have the coverage the MODEL requires; no document conflicts with a section 2 constraint; navigation and links satisfy the MODEL | `references/view-consistency-checks.md` |

### One home per fact

The matrix holds no entry for a design fact. A fact's content stays under its heading in an arc42
or `detailed/` document, and
the matrix holds the heading: a `describedBy` relationship from the entry the fact is about to the
document, with the heading. For the documents in scope:

1. List what each describes: `atw-matrix node document:<path under the architecture root>`
   returns the document's `headings` and, under `describes`, each entry it describes with the
   heading. `atw-matrix find --kinds document --text "<subject>"` lists documents by subject.
2. For each entry, `atw-matrix node <entry id>` returns under `describedBy` every document and
   heading that describes it, in scope or not. Each heading the matrix names exists in its
   document. A heading that is missing is a `FAIL` with the entry id, the path and the heading.
3. A fact about the entry is stated under one of those headings. Any other document in scope that
   states the same fact in its own words, where a link to that heading belongs, is a `FAIL` with
   both paths and the restating sentence quoted.
4. A statement of design in a document about a thing the matrix holds no `describedBy` for is a
   `WARN` with the quoted sentence: the matrix names no home for it.
5. `disputedBy` on a document's entry names each recorded disagreement that quotes it, and
   `atw-matrix node disagreement:<id>` returns the disagreeing statements with the ruling once
   one is made. A disagreement with no ruling is a `FAIL` under Consistency, with both paths.

### Placement

All of the architecture and design is architecture; the only question is where each document is
stored. Apply the MODEL's rule: a statement belongs in arc42 when it stays true if the code is
rewritten, and the detailed design of one component, one feature, components working together or
the whole system belongs in its document under `detailed/`, linked from the arc42 view of its
subject, which states the responsibility and does not restate the detail.

- Detail stated in an arc42 document whose home the MODEL places under `detailed/` is a `WARN`
  with the quoted line and the `detailed/` folder it belongs in. It is placement, not an error of
  content: the detail is kept, and moved.
- A `detailed/` document that no arc42 view of its subject links to, or that does not link to its
  parent, is a `FAIL` under this family.
- A value with a unit (a limit, a lifetime, a timeout, a retry count) that no TRD requirement
  states is a `WARN`: its home is the TRD, which the detailed design applies.
- A standard or policy that names an implementation (a construct, a library, a class or code that
  meets its requirements) is a `FAIL` with the quoted line: that belongs in the detailed design of
  the component that meets it.

## How to run the verification

1. **Resolve the scope.** Take the architecture root the router resolved and the version the
   caller names (the effective version, `arc42/` and `detailed/`, or `built/<element>/`). With no
   version named, verify the effective version. When the
   root cannot be resolved, ask one question. State whether this is a bounded review of named
   documents or a whole-project assessment; a sample is never a whole-project verdict.
2. **Load the rules** from the MODEL, the MENU, the criteria file and the references above. For
   coverage, establish the subjects from the matrix (the `subject` of each document entry, and
   the services, components and stacks `atw-matrix find --kinds service,component,stack` returns)
   and the design in scope, and apply the MODEL's
   coverage obligations and its assessment results.
3. **Assert each check.** Walk the six families in order. For every check, record `PASS`, `FAIL`
   or `WARN` with the path, a one-line observation and the evidence (a quoted line, or a named
   absence). A `FAIL` without evidence is not reported.
4. **Run every check**, so that the caller gets the full picture in one pass.
5. **Emit the verdict** in the structure below. Name each check you could not make; a missing
   renderer or an unmade visual inspection is not a passing check.

```text
resolve root and version
  -> load MODEL, MENU, criteria and references
  -> layout and naming -> catalog -> content hygiene
  -> one home per fact -> placement -> consistency
  -> emit structured verdict
```

## Verdict

The verdict contains the top-line result and every finding with its evidence, carried by the
caller's schema. The layout below is the form it takes only when the caller gives no schema.

The top-line result is the worst status seen (`FAIL` if any check failed, else `WARN` if any
warning, else `PASS`).

```text
Architecture verification — <root>/<version>
Result: PASS | WARN | FAIL  (<n> failures, <m> warnings)

Layout and naming
  [PASS] every section is a folder with a README.md; no section 9
  [FAIL] 05-building-block-view/identity-2026-08-20.md — named for a date
         evidence: file name contains "2026-08-20"

Catalog
  [FAIL] 06-runtime-view/settings/save-settings.md — view_type missing
         evidence: front matter has scope, subject, shows; no view_type

Content hygiene
  [FAIL] 08-crosscutting-concepts/idempotency.md — written as a rule
         evidence: "Every consumer MUST deduplicate by event id."

One home per fact
  [FAIL] fact "the address is verified by the proof service" — restated outside its home
         evidence: home 08-crosscutting-concepts/address-proof.md#Proof;
                   06-runtime-view/sign-up.md says "the sign-up handler verifies the address"

Placement
  [WARN] 05-building-block-view/settings/README.md — detail whose home is detailed/components/SkillSpoke-settings-service/
         evidence: "partition key userId, sort key settingName"

Consistency
  [FAIL] settings service — two documents contradict
         evidence: 05-building-block-view/README.md shows a synchronous call;
                   06-runtime-view/settings/save-settings.md shows an event
```

Each finding is one entry, `[STATUS] <path or element> — <observation>`, followed by an indented
`evidence:` line. Group entries under the six family headings in order. Close with a one-line
summary of what must change for the architecture to pass, phrased as findings for the author to
act on.

## What is outside this skill

- Writing, filling in or correcting documents: `arc42-author` or `arc42-maintain`.
- Judging whether a design is good. You judge whether the documentation conforms to the MODEL and
  is consistent with itself.
- Softening a `FAIL` into a `WARN`. The verdict is mechanical.
- Editing any file. Report instead.

## References

- `references/verification-checklist.md` — layout, naming and catalog checks.
- `references/living-doc-antipatterns.md` — content that does not belong in any version.
- `references/view-consistency-checks.md` — the checks that documents agree with each other and
  with section 2.
- `../arc42/references/` — the shared section model, living-document rules and how to find
  documents.
