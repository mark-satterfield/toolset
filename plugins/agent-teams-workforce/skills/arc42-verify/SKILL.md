---
name: arc42-verify
description: >-
  Verifies the architecture documentation against the project's architecture
  documentation model: the arc42 folder layout, the catalog front matter on
  every document, documents named for their subjects, one home for each design
  fact, no content below architecture level, no rules outside section 2, no
  history, decision records or open items, and no documents contradicting each
  other. Checks the effective documents or the built documents. This is a
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
  fact and the level of detail), the living-document rules and how to find documents.
- `../architecture-baseline/review-criteria.json` — the criteria and the level of each.
- All three files in `references/` — the assertions you make.

## What you verify

| Family | What it asserts | Reference |
|---|---|---|
| **Layout and naming** | Every section is a folder with a `README.md`; no section 9; documents sit in the section the MODEL names; files and folders are named for their subjects, never for a PRD, Epic, bead id, date or pipeline gate; built documents use the same layout under `built/<element>/` | `references/verification-checklist.md` |
| **Catalog** | Every document carries `view_type` (a MENU type), `scope`, `subject`, `shows` and `lifecycle_state`, with valid values, and `shows` matches what the document's diagram shows | `references/verification-checklist.md` |
| **Content hygiene** | No rules outside section 2; no history, changelog, decision records or ADRs; no open items; no requirements; no repository names; section 4 is enterprise-level strategy of about one page | `references/living-doc-antipatterns.md` |
| **One home per fact** | Each design fact the matrix holds for the documents in scope is stated under its home heading and nowhere else; another document that needs it links to that heading | this file |
| **Level of detail** | No arc42 document holds content below architecture level | this file |
| **Consistency** | No two documents contradict each other; applicable subjects have the coverage the MODEL requires; no document conflicts with a section 2 constraint; navigation and links satisfy the MODEL | `references/view-consistency-checks.md` |

### One home per fact

The matrix registers each design fact with one home, a document and a heading, and refuses a
second. For the documents in scope:

1. List the facts whose home is in one of them: `atw-matrix node <document id>` names the rows
   that link to a document, and `atw-matrix find --kinds fact --text "<subject>"` lists facts by
   subject.
2. For each fact, the home heading exists in the home document and states the fact. A home that is
   missing is a `FAIL` with the fact id and the path.
3. Any other document in scope that states the same fact in its own words, where a link to the home
   heading belongs, is a `FAIL` with both paths and the restating sentence quoted.
4. A statement of design in a document that the matrix holds no fact for is a `WARN` with the
   quoted sentence: it has no registered home.

### Level of detail

Each criterion in `review-criteria.json` has a level: architecture (arc42), technical requirement
(the TRD) or implementation (the specs and Tasks). An arc42 document holds the architecture level
only: which block is responsible, which block owns the data, who may call whom, what happens in
what order, where it runs, and the rule with its reason. Each of the following in an arc42
document is a `FAIL` with the quoted line: a route method and path, a field name, a key or index
attribute name, a parameter name, a metric or alarm name, a payload schema. A value with a unit (a
limit, a lifetime, a timeout, a retry count) is a `WARN`: its home is the TRD.

## How to run the verification

1. **Resolve the scope.** Take the architecture root the router resolved and the version the
   caller names (`arc42/` or `built/<element>/`). With no version named, verify `arc42/`. When the
   root cannot be resolved, ask one question. State whether this is a bounded review of named
   documents or a whole-project assessment; a sample is never a whole-project verdict.
2. **Load the rules** from the MODEL, the MENU, the criteria file and the references above. For
   coverage, establish the subjects from the matrix and the design in scope, and apply the MODEL's
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
  -> one home per fact -> level of detail -> consistency
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

Level of detail
  [FAIL] 05-building-block-view/settings/README.md — a key attribute name
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
