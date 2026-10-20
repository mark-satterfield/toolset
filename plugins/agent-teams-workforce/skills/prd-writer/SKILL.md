---
name: prd-writer
description: Use when writing, revising, or validating a Product Requirements Document (PRD) against the standard PRD template — author a template-conformant PRD, verify an existing PRD for conformance (required sections, P0 acceptance criteria, no leftover scaffolding, WHAT-not-HOW), or inspect a PRD through one validation lens under the ground rules every lens applies (business versus technical requirements, what a reviewer judges in acceptance criteria). For any agent that produces or reviews a PRD.
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

1. **The pair is recorded in one place, the matrix, and neither side is a container for the other.**

   | Question | Lookup | What it returns |
   |---|---|---|
   | The PRD of an Epic | `atw-matrix epic <bead id>` | `prd.path`, the PRD's path relative to the vault root |
   | The Epic of a PRD | `atw-matrix find --kinds epic --prd <path>` | the `epic` entry |

   The `epic` entry holds the PRD's path and one `requirement` entry for each `####` heading under
   `## Requirements`. A read needs no role. You write no pointer on either side: the PRD carries
   no `**Epic:**` line and the Epic carries no `prd:` label, and one found in an older file or on
   an older bead is not a record. When a new pair is formed, report the Epic id and the PRD path;
   the workflow records the pair with `atw-matrix sync-epics --bead <id> --prd <path>`.

   **When the matrix names no PRD for an Epic, or no Epic for a PRD, that is a fact to report, never
   a gap to fill by guessing.** Matching Epics to PRDs by title resemblance mis-paired three Epics
   and overwrote them with another PRD's content. One Epic, one PRD, on recorded evidence only.
2. **Keep the file shape the mapping depends on.** The mapping is exact and two-way:

   ```
   PRD file  ==  "# " + epic.title + "\n\n" + epic.description
   ```

   So the PRD's **first and only** `# ` heading is the Epic title, and everything after it is the
   Epic description. Do not add YAML frontmatter, and do not introduce a second `# ` heading; both break
   the split. `.delta.md` files are working artifacts, not PRDs, and are never synced.
3. **A PRD edit is not finished until the Epic matches, and the one who writes the PRD's vault file
   brings the Epic in sync.** An agent a workflow starts writes no bead and runs neither script
   below: it writes the PRD where its brief says and names the slug in its result, and the
   workflow's caller, which writes the vault file and the Epic bead, syncs them and records the
   pair. A session that writes a PRD's vault file itself runs the sync. The project supplies two
   scripts through environment variables whose names are defined only by the
   `agent-teams-workforce:pipeline-contracts` skill (`schemas/driver-surface.schema.json`,
   `$defs.DriverEnvironment`): the sync script is the variable whose `x-constant` is
   `PRD_EPIC_SYNC_ENV`, the verify script the one whose `x-constant` is `PRD_EPIC_VERIFY_ENV`.
   Read the names from that schema, never from memory, and run:

   ```bash
   "<sync script>" --only <slug> --apply     # document -> Epic (creates the Epic if absent)
   "<verify script>" <slug>                  # check one PRD against its Epic
   "<verify script>" <slug> --apply          # Epic -> document, when the Epic was edited first
   ```

   If a variable is unset, report its name and the exact slug that needs syncing rather than
   leaving the halves divergent.

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
4. **Scope to a single verifiable requirement** — one outcome, stated as observable behavior with
   no components, files or technologies named, with a pass/fail check and an explicit
   out-of-scope list. A PRD carries no size; WSJF sizing judges that later. Run the template's
   smell tests; if any trigger, **decompose into multiple PRDs**.
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

   **When you find a contradiction like this in your own draft, fix it.** Close the under-specified
   `Given`; do not reword it into vagueness, and do not delete the criterion that exposed the
   conflict. **In an existing PRD, make the repair.** No workflow or pipeline ever edits a PRD.
8. **Fill every structured section:** Out of Scope, Constraints (behavioral, not tech choices),
   Measurable Outcomes (table + starting value/target/method), Visual References, Definition of Done.
   A PRD names no other PRD: ordering between Epics is carried by Epic dependency edges in beads.
9. **Settle every input gap within the feature's purpose by best-in-class practice and write it
   in; leave out anything outside the feature's purpose.** The owner gives high-level requirements
   and never gets product questions about scope they did not request; a list the owner provides is
   the complete list. A PRD holds requirements only — no risks, open questions, notes, or
   discussion. Never smooth a contradiction into vague language.
10. **Delete every template comment (`<!-- ... -->`) and `[placeholder]`** before saving.
11. **Run `scripts/check_prd.py` on your draft and resolve every error** before you finish.
12. **Sync the Epic half when you write the PRD's vault file yourself** — run the sync script
    (rule 3) with `--only <slug> --apply` and say so in your reply. A workflow agent writing a draft
    names the slug in its result instead.

## Validate Mode — Workflow

Use this when reviewing someone else's PRD (or your own before a gate).

1. **Run the linter:** `python3 scripts/check_prd.py path/to/prd.md`. Every `FAIL` is a hard defect;
   record it. `WARN`s (possible placeholders, extra sections) need a judgment call: make it for each
   one (a real placeholder or not, a section that belongs or not) and record the call and its reason.
2. **Then verify what the linter cannot** — the semantic checks:
   - **WHAT-not-HOW:** does any section leak implementation (named services, schemas, frameworks)?
   - **Problem framing:** is it stated as user pain, not "absence of our solution"?
   - **Acceptance criteria testability:** is each P0 criterion actually pass/fail, not aspirational?
   - **Traceability:** does every requirement trace to an upstream source (brief, persona, OKR)?
   - **Measurable Outcomes:** does each metric have a starting value, a target, and a measurement method?
   - **Scope:** do the smell tests pass, or should this be decomposed?
3. **Report findings as structured defects** (location + what's wrong + why) — do not fix them if
   your role is review-only.

## Acceptance Criteria: What the Author Writes and What a Reviewer Judges

The author of a PRD written to the template gives every P0 requirement an Acceptance Criteria
block (Author mode step 6), and `scripts/check_prd.py` reports a P0 requirement without one as a
structural `FAIL`. A reviewer judging substance asks a different question: does the requirement
state an observable outcome that can be checked pass/fail? A requirement whose own statement names
such an outcome ("the button on the login screen is green") has its acceptance criterion in that
statement. A PRD is a business requirement and may be one sentence: a reviewer never faults a
requirement for lacking a separately headed criteria block, an identifier, or length. It faults a
criterion that only restates its requirement without an observable outcome, and a criterion that
is not pass/fail.

## Validation Lenses — The Ground Rules Every Lens Applies

A PRD validation runs one specialist per lens (requirement class, ambiguity, completeness,
conflict, constraints, domain boundaries, clarifications, and BRD traceability when a BRD is
named). Each applies these rules:

- **A PRD is WHAT-level.** A requirement that names a desired outcome without naming its
  implementation mechanism is not defective. Never flag absent mechanism, thresholds, schemas,
  or quantified non-functional requirements: they belong to the TRD and the specs.
- **A PRD is one slice of a decomposed set and names no other PRD.** Ordering between features is
  carried by Epic dependency edges, not by the PRD. Behavior another feature provides is not a
  gap in this one.
- **The product is built iteratively.** An absence that may legitimately arrive as its own later
  PRD is scheduling, not a defect: report it at `info` severity only, or not at all.
- **The PRD is the top of the requirements chain.** Judge it against itself (and, for traceability,
  map it to a BRD for information only); never fault it for diverging from a document above it.
- **Read the PRD and only the files your brief names.** It is the entire object of every lens. Do
  not survey the repository, the architecture folders or the polyrepo.
- **Identify each requirement as the PRD writes it**, or as R1, R2, … in document order where it
  gives none.
- **Severity says what the finding does to specifying the requirement.** `blocker` only when the
  requirement cannot be specified as written; `info` for scheduling.
- **Report findings, not essays.** One finding once, never restated as several; every issue,
  question and detail under 40 words.

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
- [ ] Measurable Outcomes table fully filled; no other PRD named — judgment
- [ ] Every requirement/metric traces to an upstream source — judgment

## Anti-Goals

- Inventing requirements to make the document look complete
- Leaking HOW (named services, schemas, frameworks) into a WHAT document
- Aspirational metrics with no starting value or measurement method
- Shipping the template's guidance comments or placeholder brackets in the final file
- Marking a PRD conformant on the linter alone — structural pass ≠ semantic pass
- Writing one giant PRD when the scope smell tests demand decomposition

See `references/prd-template.md` for the full template and the inline guidance for every section.
