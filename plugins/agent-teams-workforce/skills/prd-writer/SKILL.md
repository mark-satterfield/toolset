---
name: prd-writer
description: Use when writing, revising, or validating a Product Requirements Document (PRD) against the standard PRD template — author a template-conformant PRD, or verify an existing PRD for conformance (required sections, P0 acceptance criteria, no leftover scaffolding, WHAT-not-HOW). For any agent that produces or reviews a PRD.
---

# PRD Writer & Template Conformance

The canonical PRD template lives in `references/prd-template.md`. It is a two-sided contract:
**writers produce against it; reviewers verify against it.** This skill serves both sides so they
never drift apart.

A PRD defines **WHAT** a feature does, never **HOW** it is built. The template is the contract —
do not add, drop, rename, or reorder its sections.

## When To Use

- **Author mode** — drafting or revising a PRD from an intake brief, persona profiles, and an OKR
  cascade, or from a feature request.
- **Validate mode** — checking that an existing PRD conforms to the template before it passes a
  gate, gets handed downstream, or is marked done. Any agent that verifies a PRD uses this mode.

Both modes share one source of truth (`references/prd-template.md`) and one mechanism
(`scripts/check_prd.py`).

## The One Rule That Governs Everything

**Describe behavior, not implementation.** Every section states the observable outcome a user or
the system produces — not the mechanism that produces it.

- Good: "The system must allow new data sources to be added without redeploying existing components."
- Bad: "Implement a plugin registry with dynamic class loading."

If a sentence names a library, table, queue, framework, or class, it belongs in a Spec, not a PRD.

## The Mechanism: `scripts/check_prd.py`

A deterministic conformance linter both modes run. It reads `references/prd-template.md` at runtime
to derive the required sections, so it never drifts from the template.

```bash
python3 scripts/check_prd.py path/to/your-prd.md          # human-readable report
python3 scripts/check_prd.py path/to/your-prd.md --json    # machine-readable
```

Exit code is `0` when there are no errors (warnings allowed), `1` otherwise.

It checks what is **mechanically decidable**:
- the `# Feature PRD:` title line is present
- every required `##` section from the template is present and in template order
- `Last Updated` is a real `YYYY-MM-DD` date, not the placeholder
- no leftover scaffolding — HTML comments, `[placeholder]` brackets, unfilled `P0 | P1 | P2` lines
- every **P0** requirement carries an Acceptance Criteria block

It **cannot** decide *semantic* conformance — that is the reviewer's job (see Validate mode).

## Author Mode — Workflow

1. **Read the template first.** Open `references/prd-template.md`. It is the source of truth for
   section order, headings, and the inline guidance comments. Reproduce its structure exactly.
2. **Name the file with the grouping convention:** `[domain]-[area]-[feature].md` so files sort and
   group naturally — e.g. `opportunities-page-table-search.md`, not `search.md`.
3. **Set `Last Updated`** to today's date in `YYYY-MM-DD`.
4. **Scope to a single verifiable feature** — one outcome, a small set of tightly coupled files,
   100–300 lines of change, completable in one think-plan-act-verify loop, with a pass/fail check.
   Run the template's smell tests; if any trigger, **decompose into multiple PRDs**.
5. **State the Problem from the user's perspective** — the pain, not the absence of your solution —
   and back it with Evidence (or delete Evidence only if the problem is self-evident).
6. **Write Requirements grouped by use case or capability.** Each carries a **Priority** (P0/P1/P2)
   and states a behavior. **Every P0 requirement MUST have Acceptance Criteria** as Given/When/Then
   or boolean assertions, each verifiable pass/fail. If a requirement needs more than 5 assertions,
   the feature is too big — decompose.
7. **Fill every structured section:** Out of Scope, Constraints (behavioral, not tech choices),
   Dependencies (table + status), Measurable Outcomes (table + baseline/target/method), Risks &
   Open Questions, Visual References, Definition of Done.
8. **Record every unresolved input gap as an Open Question.** Never invent a requirement, metric, or
   constraint to look finished; never smooth an upstream contradiction into vague language.
9. **Delete every template comment (`<!-- ... -->`) and `[placeholder]`** before saving.
10. **Run `scripts/check_prd.py` on your draft and resolve every error** before handoff.

## Validate Mode — Workflow

Use this when reviewing someone else's PRD (or your own before a gate).

1. **Run the linter:** `python3 scripts/check_prd.py path/to/prd.md`. Every `FAIL` is a hard defect;
   record it. `WARN`s (possible placeholders, extra sections) need a human judgment call.
2. **Then verify what the linter cannot** — the semantic checks:
   - **WHAT-not-HOW:** does any section leak implementation (named services, schemas, frameworks)?
   - **Problem framing:** is it stated as user pain, not "absence of our solution"?
   - **Acceptance criteria testability:** is each P0 criterion actually pass/fail, not aspirational?
   - **Traceability:** does every requirement trace to an upstream source (brief, persona, OKR)?
   - **Measurable Outcomes:** does each metric have a baseline, a target, and a measurement method?
   - **Scope:** do the smell tests pass, or should this be decomposed?
3. **Report findings as structured defects** (location + what's wrong + why) — do not fix them if
   your role is review-only; route them back to the author.

## Conformance Checklist (shared)

The linter covers the structural items (✓-able by `check_prd.py`); the rest require judgment.

- [ ] Title `# Feature PRD: <name>` and `Last Updated: YYYY-MM-DD` — *linter*
- [ ] All template `##` sections present and in order — *linter*
- [ ] No leftover comments / `[placeholders]` / unfilled priority legend — *linter*
- [ ] Every P0 requirement has Acceptance Criteria — *linter*
- [ ] Feature scoped to one outcome; smell tests pass — judgment
- [ ] Problem stated as user pain, with Evidence (or justified deletion) — judgment
- [ ] No HOW leaked into any section — judgment
- [ ] Each P0 acceptance criterion is genuinely testable — judgment
- [ ] Dependencies, Measurable Outcomes tables fully filled — judgment
- [ ] Every requirement/metric traces to an upstream source — judgment

## Anti-Goals

- Inventing requirements to make the document look complete
- Leaking HOW (named services, schemas, frameworks) into a WHAT document
- Aspirational metrics with no baseline or measurement method
- Shipping the template's guidance comments or placeholder brackets in the final file
- Marking a PRD conformant on the linter alone — structural pass ≠ semantic pass
- Writing one giant PRD when the scope smell tests demand decomposition

See `references/prd-template.md` for the full template and the inline guidance for every section.
