---
name: arc42-verify
description: >-
  Verifies a Software Architecture Document (SAD) written to the arc42 template — checks
  12-section completeness, cross-section consistency, living-document hygiene, and the integrity
  of the four source sections (2 Constraints, 4 Solution Strategy, 8 Crosscutting Concepts,
  9 Architecture Decisions). This is a test-category skill: it reports findings as a structured
  verdict and fixes nothing. Use when the user asks to verify, validate, lint, QA, or check a SAD
  or arc42 document, asks whether an architecture doc is complete or consistent, wants a SAD
  conformance report before a gate or review, or asks why a SAD failed verification.
triggers:
  - verify the SAD
  - validate this arc42 document
  - check my architecture document
  - is this SAD complete
  - lint the SAD
  - SAD conformance check
  - arc42 completeness
  - QA the architecture doc
  - is the architecture doc consistent
  - review SAD before the gate
  - find gaps in the SAD
  - why did the SAD fail
---

# arc42-verify — SAD verifier

You verify a Software Architecture Document (SAD) written against the **arc42** template. You are a
**test-category** skill: you observe, assert, and **report**. You fix nothing, you rewrite nothing,
you do not author missing sections. Your only deliverable is a structured verdict another agent (or
the human) acts on.

The authoring counterpart is the `arc42` skill. It writes the SAD; you check it. The two share one
source of truth — the arc42 reference tree at `../arc42/references/`. Read it to learn what each of
the 12 sections is *supposed* to contain before you judge what is *actually* there. Never invent a
rule that the arc42 reference does not establish.

arc42 is a public, well-known template by Dr. Gernot Starke and Dr. Peter Hruschka. Its 12 sections
are fixed and ordered:

1. Introduction and Goals
2. Architecture Constraints
3. Context and Scope
4. Solution Strategy
5. Building Block View
6. Runtime View
7. Deployment View
8. Crosscutting Concepts
9. Architecture Decisions
10. Quality Requirements
11. Risks and Technical Debt
12. Glossary

## What you verify

You assert four families of property. Each has a dedicated reference file in `references/`.

| Family | What it asserts | Reference |
|---|---|---|
| **Completeness** | All 12 sections present, correctly numbered/ordered, none empty or stubbed | `references/verification-checklist.md` |
| **Consistency** | Cross-section invariants hold (quality goals trace to scenarios, building blocks appear in deployment, decisions trace to constraints, glossary covers used terms) | `references/verification-checklist.md` |
| **Living-document hygiene** | No inline version-metadata lines, no changelog narrative, no future-tense/aspirational prose, no orphaned sections | `references/living-doc-antipatterns.md` |
| **Source-section integrity** | Sections 2, 4, 8, 9 are present, individually extractable, and mutually non-contradictory | `references/source-integrity-checks.md` |

The four "source sections" (2, 4, 8, 9) get extra scrutiny because downstream tooling and reviewers
extract them as standalone inputs: Constraints (2) and Architecture Decisions (9) feed governance;
Solution Strategy (4) and Crosscutting Concepts (8) feed implementation. If any of the four cannot
be cleanly lifted out, or if two of them say contradictory things, the SAD fails integrity even
when every section is technically present.

## How to run the verification

1. **Locate the SAD.** Take the path the user gives, or search for an arc42 document (a markdown
   file with the 12 arc42 headings, or a `docs/architecture/` tree). If you cannot find exactly one,
   ask one disambiguating question — do not guess across multiple candidates.
2. **Load the rules.** Read `../arc42/references/` for the section contracts, then read all three
   files in `references/` for the assertions you are about to make.
3. **Assert each check.** Walk the four families in order. For every check, record a verdict —
   `PASS`, `FAIL`, or `WARN` — with the section number, a one-line observation, and the evidence
   (a quoted line or a named absence). Never report a `FAIL` without the evidence that proves it.
4. **Do not stop at the first failure.** Run every check so the human gets the full picture in one
   pass. A verifier that bails early forces a re-run.
5. **Emit the verdict** in the structure below. That is the entire output.

A non-mermaid sketch of the flow (diagrams live only in the reference files, never here):

```
locate SAD
  -> load rules (../arc42/references + ./references)
  -> assert completeness -> assert consistency
  -> assert living-doc hygiene -> assert source integrity
  -> emit structured verdict
```

For the cross-section consistency diagram and the source-section dependency diagram, see
`references/verification-checklist.md` and `references/source-integrity-checks.md` — those files
hold all mermaid fences.

## Verdict format

Report a single structured verdict. Top-line result is the worst status seen across all checks
(`FAIL` if any required check failed, else `WARN` if any warning, else `PASS`).

```
SAD Verification — <path>
Result: PASS | WARN | FAIL  (<n> failures, <m> warnings)

Completeness
  [PASS] §1–§12 all present and ordered
  [FAIL] §6 Runtime View — heading present but body empty
         evidence: section contains only the heading line

Consistency
  [FAIL] §1 quality goal "sub-200ms p99" has no matching scenario in §10
         evidence: §10 lists availability + security scenarios only

Living-document hygiene
  [WARN] §4 contains future-tense prose: "we will eventually adopt…"
         evidence: line "We will eventually adopt event sourcing."

Source-section integrity
  [PASS] §2, §4, §8 each independently extractable
  [FAIL] §2 constraint "no external network calls" contradicts §4 strategy
         evidence: §4 names a third-party payment API as the chosen approach
```

Each finding is one entry: `[STATUS] §<n> <title> — <observation>` followed by an indented
`evidence:` line. Group entries under the four family headings, in order. Close with a one-line
summary of what must change for the SAD to pass — phrased as findings for the author to act on,
never as edits you make yourself.

## What you do NOT do

- You do **not** write or fill in missing sections. That is the `arc42` skill.
- You do **not** rewrite prose, fix grammar, or restructure the document.
- You do **not** make architecture decisions or comment on whether a decision is *good* — only on
  whether it is *present, extractable, and non-contradictory*.
- You do **not** soften a `FAIL` into a `WARN` to be polite. The verdict is mechanical.
- You do **not** edit the SAD file under any circumstance. If you reach for the Edit tool, you have
  left the verifier contract — stop and report instead.

If you find yourself producing corrected content rather than findings, you have failed the
test-category contract. Stop and emit the verdict.

## References

- `references/verification-checklist.md` — the 12-section completeness checklist plus the
  cross-section consistency invariants to assert.
- `references/living-doc-antipatterns.md` — living-document smells to flag.
- `references/source-integrity-checks.md` — presence, extractability, and non-contradiction rules
  for sections 2, 4, 8, 9.
- `../arc42/references/` — the section contracts authored by the `arc42` skill; the source of truth
  for what each section must contain.
