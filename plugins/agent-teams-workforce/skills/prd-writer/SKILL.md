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

## A PRD and Its Epic Are One Entity

A PRD document and its Epic bead are **the same entity in two places** — the document and its
tracker half. Neither contains, summarises, or points at the other. They hold the same content.
Change the PRD and the Epic changes; change the Epic and the PRD changes. Epics exist as separate
records only because PRDs were written before the tracker was in use.

Three consequences bind every PRD author and reviewer:

1. **Never describe an Epic as a container for a PRD.** A "Container for PRD `<file>`" line is the
   old, wrong convention: it is prose, so any rewrite deletes it silently, and 29 PRD-to-Epic links
   were lost exactly that way. The link is the Epic label **`prd:<slug>`**, where `<slug>` is the
   PRD filename without `.md`. A label survives a description or notes rewrite.
2. **Keep the file shape the mapping depends on.** The mapping is exact and two-way:

   ```
   PRD file  ==  "# " + epic.title + "\n\n" + epic.description
   ```

   So the PRD's **first and only** `# ` heading is the Epic title, and everything after it is the
   Epic description. Do not add YAML frontmatter, and do not introduce a second `# ` heading — both
   break the split. `.delta.md` files are working artifacts, not PRDs, and are never synced.
3. **A PRD edit is not finished until the Epic matches.** After writing or revising a PRD, bring its
   Epic into sync, and say in your handoff that you did:

   ```bash
   ops/prd-epic-sync.py --only <slug> --apply    # document -> Epic (creates the Epic if absent)
   ops/prd-epic-verify.py <slug>                 # check one PRD against its Epic
   ops/prd-epic-verify.py <slug> --apply         # Epic -> document, when the Epic was edited first
   ```

   Both scripts live in the SkillSpoke command repo under `ops/`. If you cannot reach them from your
   working tree, report the exact slug that needs syncing rather than leaving the halves divergent.

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
7. **Make the criteria within one requirement mutually consistent.** No two criteria may both apply
   to the same input and demand opposite outcomes. The usual cause is a success criterion whose
   `Given` lists only some of the conditions its sibling criteria make decisive — so a rejected
   input also satisfies the success case. **Every success criterion's `Given` must restate every
   condition that any sibling criterion treats as grounds for rejection.**

   A real example that halted a pipeline for a day. One criterion said an out-of-range value must be
   rejected; another said "Given a settings write containing no unknown fields … then the write
   succeeds." A write with a known field holding an out-of-range value satisfied both, so the gate
   could not certify the requirement. The repair was to close the second `Given`: "Given a settings
   write containing no unknown fields **and no field value outside its defined type or range** …".

   **When you find a contradiction like this — in your own draft or an existing PRD — fix it and
   carry on.** Close the under-specified `Given`; do not reword it into vagueness, do not delete the
   criterion that exposed the conflict, and do not escalate. Name the repair in your handoff. This is
   the one exception to review-only routing: a self-contradictory criterion blocks every downstream
   phase, and it is repairable from the document alone.
8. **Fill every structured section:** Out of Scope, Constraints (behavioral, not tech choices),
   Dependencies (table + status), Measurable Outcomes (table + baseline/target/method), Risks &
   Open Questions, Visual References, Definition of Done.
9. **Record every unresolved input gap as an Open Question.** Never invent a requirement, metric, or
   constraint to look finished; never smooth an upstream contradiction into vague language.
10. **Delete every template comment (`<!-- ... -->`) and `[placeholder]`** before saving.
11. **Run `scripts/check_prd.py` on your draft and resolve every error** before handoff.
12. **Sync the Epic half** — `ops/prd-epic-sync.py --only <slug> --apply` — and say so in the handoff.

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
