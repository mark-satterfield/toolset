# CDS Restructure — Review Bundle

Outputs of the read-only blast-radius workflow (Run `wf_7b4322ec-ad6`). Nothing in
the plugin has been edited. Two parts: (1) the draft **model statement** to ratify,
(2) the **change-map** of everything the restructure touches.

---

# Part 1 — Draft Model Statement (Phase 0, for ratification)

This document states the model the CDS plugin enforces. It is a **servant
document**: the owner controls it and may overrule any part of it at any time.
Where this statement and the owner's intent diverge, the owner wins. Read it as a
description of capability, not a list of permissions.

## Primary Responsibility

The design system **guarantees that whatever is built follows the predetermined
design aesthetic.** That is its job. It does not restrict which arrangements may
exist, which pages may be built, or how features may be composed. It makes a single
promise — everything stays on-aesthetic — and keeps that promise across any
arrangement the owner produces.

The governing principle is **enforce, don't enumerate.** Define every concept by
what it *guarantees and enables*, never by what it forbids. There is no allow-list,
no catalog of permitted layouts, no permission gate. If something is on-aesthetic,
the system carries it; the system's work is to make staying on-aesthetic automatic,
not to police which combinations are allowed.

## The Five Concepts

Each is defined by its capability.

- **Component** — A reusable, self-contained, on-aesthetic building block.
  Components run from simple to complex along atomic-design lines and carry their
  own interactive states. They are the smallest unit the system guarantees.
- **Theme** — The aesthetic skin applied to a section. Exactly one theme governs a
  section.
- **Shape** — A reusable, on-aesthetic layout template for arranging components.
  There is **one freely-composable shape library**; shapes are *offered, not
  rationed*. An app shell is a shape.
- **Section** — A themed region of a page. A page has one or more sections.
- **Page Type** — A behavioral archetype. Its role is **large and grows with
  capability**: a page type owns the policy for its kind of page and is built to
  **flex, not fence** — to accommodate what its pages need, not to constrain them.

## The Page-Type Behavioral Spectrum

All page types stand on the same aesthetic floor. They differ in how much behavior
they add above it.

- **Aesthetic enforcement** *(every page)* — Components, themes, and shapes
  guarantee look and feel. This is the floor; nothing sits below it.
- **Elastic app chrome** *(app pages)* — A base frame (for example: top menu, left
  nav, main) that absorbs new regions as features arrive — say, a right panel —
  **without requiring a new page type.** Whatever combination of regions is present
  or absent, the system keeps it on-aesthetic.
- **Deterministic generation** *(landing pages)* — A rules engine takes
  owner-supplied content and derives the sections, the themes, and the shapes that
  fill them.

## What Was Removed, and Why

Earlier framings have been retired because they enumerated rather than enforced, or
split one idea into false alternatives: **"surface"** as a concept and catalog; the
fixed **A1–A5** shell-layout enumeration; any **"two kinds of shape"** (S-vs-A)
split; **"page shape"** as a separate idea; and all **allow-list / permission**
framing. Each contradicted *enforce, don't enumerate* — fencing arrangements
instead of guaranteeing the aesthetic — so each is gone.

---

# Part 2 — Change-Map

99 findings across 28 distinct files (of 92 scanned). Concepts: `surface`,
`shell-layout-enum`, `shape-split`, `page-shape`, `constraint-language`, and one
`vocabulary-ref`.

## By concept

| deadConcept | count | most concentrated in |
|---|---|---|
| **surface** | 36 | `apply-design-system/SKILL.md` (8), `cds-ui-author.md` (4), `components.md` (3) — spread widely across skills/commands/agents |
| **shell-layout-enum** | 27 | `compose-app-surface/reference/app-shapes.md` (5), `app-kitchen-sink.html`, the 5 `_fragments/app/A*.html` |
| **shape-split** | 19 | `compose-app-surface/SKILL.md` (4), `app-shapes.md` (3) |
| **constraint-language** | 11 | `reference/page-types.md` (5 "Required Structure" blocks), the halt-code agents/commands |
| **page-shape** | 9 | `app-kitchen-sink.html` (P1–P15 badges), `compose-app-surface` SKILL/command/README |
| **vocabulary-ref** | 1 | `README.md` (dead link to deleted `reference/vocabulary.md`) |

`surface` + `shell-layout-enum` ≈ two-thirds of all records.

## Phase mapping

| Phase | Covers | ~Findings | Key files |
|---|---|---|---|
| **2 — unify shapes** | all `shape-split` + `page-shape` (collapse S0–S28, A/P, "page shapes" → one library) | ~28 | `app-shapes.md`, `landing-sections-shape-rules.md`, both SKILLs, `compose-page.md`, `audit/SKILL.md`, README |
| **3 — elastic app frame** | every `shell-layout-enum` (kill A1–A5, `app-shell--aN` markup, three-pane prescriptions, letter codes) | ~27 | `app-shapes.md` (source), `_fragments/app/A1–A5.html`, `app-kitchen-sink.html`, `foundations/layout.md`, `responsive.md`, `imagery.md`, `components.md` |
| **4 — page types + section purposes** | `constraint-language` "Required Structure" reframes; app-section gates; Application Shell entry | ~11 | `reference/page-types.md`, halt-codes in `cds-ui-author.md`, `cds-code-companion.md`, `compose-app-surface.md` |
| **5 — tools/skills/commands/agents** | bulk of `surface` renames (skill rename, env var, cross-refs, routing) | ~30 | `apply-design-system`, `setup`, `generate-stylesheets`, `audit` SKILLs, both agents, four commands |
| **6 — tests/validation** | retitles, badges, fragment labels, aria/class renames | ~16 | `app-kitchen-sink.html`, `landing-kitchen-sink.html`, `index.html`, `_fragments/app/*` |
| **7 — README** | surface-kind row, shell/page-shape rows, dead vocab link | 5 | `README.md` |

**Heaviest:** Phase 5 (~30 edits — `surface` is woven through every skill/command/agent). **Highest-risk:** Phase 3 (touches the canonical source file + live HTML/CSS). Phases 2→3→5 are tightly coupled: the skill rename (5) depends on the unified library (2) and elastic frame (3) being settled first.

## Ground zero

`skills/compose-app-surface/reference/app-shapes.md` is the source of truth for the
A1–A5 catalog and the landing-vs-app split. Almost every other shell-layout /
shape-split finding (in `components.md`, the kitchen-sink HTML, the `A*.html`
fragments, README, the apply/audit routing) is a *downstream reference* to it. Fix
this file first and dozens of pointer-fixes elsewhere become mechanical.

## Risks & care points

1. **Dead concept hidden in a data enum.** `landing-sections-shape-rules.md:63` has
   `taxonomy_type: "discipline" | "role" | "workload" | "surface" | null` — a
   find-and-replace on "surface" would silently change a *data-contract value*.
   Needs a deliberate term rename, not a phrasing tweak.
2. **Dead concept hidden in an env var.** `setup/SKILL.md:37` —
   `CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR`. Renaming it is a breaking config
   change downstream, not a doc edit.
3. **A real false positive.** `audit/SKILL.md:60` ("surface reference into an
   author's context") is the verb *to surface* — must be preserved.
4. **The audit rule that undermines the whole model.** `audit/SKILL.md:33` flags any
   "layout shape with no entry" as `undefined-in-reference`. Left as-is, it will
   actively flag every new elastic-frame arrangement as a violation — directly
   fighting Phase 3. This is the riskiest single line.
5. **Lines carrying multiple dead concepts.** `index.html:316` and `README.md:229`
   each pack `surface` + `shell-layout-enum` + `page-shape` into one sentence — need
   a single coherent rewrite, not concept-by-concept edits.
6. **A broken link.** `README.md:258` points to the deleted `reference/vocabulary.md`
   — redirect it to this model statement (the new vocabulary source of truth) or
   remove it.

## Decisions the owner needs to make (the workflow assumed answers; you decide)

- **Rename `compose-app-surface` → `compose-app`?** The workflow assumed yes (it's a
  "surface"-named skill/command). This renames a skill, a command, and breaks all
  cross-references until updated. Confirm the new name or keep the old.
- **Rename the env var `..._APP_SURFACE_DIR`?** Breaking config change — confirm the
  replacement name (e.g. `..._APP_OUTPUT_DIR`).
- **Rename the `taxonomy_type: "surface"` value?** It's a routing term reusing the
  dead word — confirm a replacement.
- **README vocabulary pointer** — point to this model statement, or elsewhere?
