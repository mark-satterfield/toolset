---
name: audit-against-system
description: Audits existing UI — files, pasted markup/CSS, or rendered URLs — against the design system and emits a structured violation report with rule citations, observed vs. expected values, file locations, and suggested fixes. Trigger on "audit this page", "is this on-system?", "check this against the design system", "find design violations", "compliance check this UI", "where does this drift from the design system?", "lint this against the design system", "review my component for design system issues", "run a design check", "are there token violations here?", "does this match the design system?". Must NOT trigger on generation requests like "build this page" or "create this component" (route to compose-page). Must NOT trigger on requests to regenerate stylesheets or design tokens — stylesheet freshness is internal machinery every skill handles silently; there is no human-facing command for it. Must NOT trigger on informational or explanatory queries that do not request a pass/fail report (route to apply-design-system). This skill IS the compliance gate.
allowed-tools: Read, Write, Bash, Glob, Grep, WebFetch
---

## What this skill does

Walks a target (file, set of files, rendered URL, or pasted markup/CSS) against the rule set in `compliance.md`, scoped by the target's rendering context, and emits a report listing each violation with its rule citation, the observed and expected values, the file path and line, and a suggested fix that points at the relevant reference section. Before any rule is evaluated, the silent stylesheet-freshness stage guarantees the baseline is the current system, so findings never compare against a stale one. The report never restates rules — every finding cites a reference file.

## Inputs

- **From caller (runtime):** the target (file path, set of paths, rendered URL, or pasted markup/CSS); the audit scope (tokens, implementation, full design rules, or all three); the desired output format (inline annotations or structured report); the rendering context (app-embedded or standalone — the caller declares this; the skill does not infer it from host-project inspection).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the elements YAML — used to know the canonical token and role names.
- **From shared reference (`../../reference/`):** `compliance.md`, plus any `foundations/*.md` file implicated by the audit scope.
- **From the catalog** when relevant (plugin ∪ extensions, per `../../reference/pipeline.md` Catalog resolution): `libraries/pages/*.md`, `libraries/sections/*.md`, `libraries/shapes/*.md`, `libraries/components/*.md`, and the `rules/shape-selection/` + `rules/page-constraints/` entries they reference.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, and `manifest.json` — the current-system baseline findings compare against.
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, used by the silent stylesheet-freshness stage.

This skill does **not** read host-project code beyond the audit target the caller hands it. The target's rendering context is declared by the caller, not derived from surrounding code.

## Discovery checklist

1. **What is being audited.** File path, set of paths, rendered URL, or pasted markup/CSS.
2. **Surface kind.** Page, Section, or Component.
3. **Rendering context.** App-embedded or standalone. Context controls rule scope — app-embedded UI MUST NOT carry its own theme controller; a standalone MUST include one.
4. **Page and page family.** Which catalog Page entry (`../../reference/libraries/pages/`) the target corresponds to, if any, and its page family (landing, app, editorial, docs, auth) — needed for type-specific rules: the page family scopes which PageLevelAestheticConstraints apply.
5. **Audit scope.** Tokens, implementation, full design rules, or all three.
6. **Output format.** Inline annotations on the target, or a structured report file.

## Pipeline

1. **Stylesheet freshness (silent).** Run the shared pipeline's freshness stage (`../../reference/pipeline.md`) before evaluating anything: compare the `cds_hash.py` semantic fingerprints (elements YAML, reference tree, extensions tree) against `manifest.json`; on mismatch invoke the internal `generate-css` machinery and proceed. Never halt for staleness, never mention staleness or regeneration to the human, never instruct the human to run anything. Halt `STYLESHEETS_REGEN_FAILED:{inner}` only if that regeneration itself fails.
2. **Load the rule set.** Read `../../reference/compliance.md`, the relevant `../../reference/libraries/pages/` entry (when the target corresponds to a catalog Page) and the `rules/page-constraints/` entries it references, and any `foundations/*.md` file implicated by the requested scope. Filter rules by their `[scope: ...]` tag based on the declared rendering context.
3. **Walk the target.** For each rule, check compliance against the target. Record every violation with: rule identifier, observed value, expected value, file path and line (or selector path / pasted-region offset), and a suggested fix that cites the relevant reference section. Adjust rule scope as you go — rules tagged `[scope: app-embedded]` do not apply to a standalone target and vice versa; rules tagged `[scope: both]` apply to either.
   - **Page-block override of system-defined geometry (`compliance.md` §23 #18).** Flag any page-block `<style>` rule or inline `style=` that re-declares a system geometry token (`--sp-*`, `--radius-*`, `--section-pad-*`, `--container-*`, or a `--{component}-{property}` token such as `--topbar-height`) **or** hardcodes a literal dimension for a Component the system already sizes — the canonical case is `.topbar-logo img { height: 26px }` while `--topbar-logo-height` exists. Observed = the page-block declaration; expected = consume the generated token (`var(--topbar-logo-height)`, `var(--container-marketing-primary)`, …); fix cites `libraries/components/topbar.md` `sizing` / `foundations/layout.md` §11. Note: a value the design system does **not** define is not this finding — it is `undefined-in-reference` (step 4), with the suggested fix "add it to the YAML `geometry:` block."
   - **`no-preference`-gated entrance motion (`compliance.md` §23 #19).** Flag any entrance/reveal animation — a rule or `@keyframes` that brings content from `opacity: 0` / a `translate` offset to its visible state (hero word reveal, card stagger, content fade/`.is-inview`, `.reveal-word` / `.card-stagger` / `.content-fade` / `.content-fade-up`) — whose animation or transition is gated **inside** `@media (prefers-reduced-motion: no-preference)`. This is the failure where entrance motion vanishes for reduce-motion users (and `opacity: 0` content can be stranded invisible). Observed = the `no-preference` wrapper around the entrance; expected = animate in the base rule, disable only inside `@media (prefers-reduced-motion: reduce)`; fix cites `foundations/motion.md` §15.4/§15.5. **Do not flag** `no-preference` used for continuous/ambient enhancement whose static baseline is the no-animation state (e.g. a looping logo marquee, an optional expand transition) — that is a legitimate use, not an entrance.
4. **Handle undefined patterns.** If the target uses a pattern the reference does not define (an unrecognized Component, an off-system token, a layout Shape with no entry), flag it as `undefined-in-reference` — this is itself an audit finding, not a free pass.
5. **Emit the report** in the chosen output format. Inline annotations attach each violation to its location in the target. Structured reports list violations grouped by file, with a header summarizing total counts by severity tier (from `compliance.md`).

## Halt conditions

- `MISSING_SPEC` — the reference is too thin to evaluate a category of rules the caller asked about (name the gap; do not silently skip).
- `TARGET_UNREADABLE` — the target cannot be read or parsed (file unreadable, URL unreachable, pasted markup malformed past recovery).
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set; the skill cannot know the canonical token names.
- `STYLESHEETS_REGEN_FAILED:{inner}` — the silent freshness stage found the stylesheet set stale or missing and the auto-invoked `generate-css` machinery itself halted; the inner code is surfaced verbatim.

Halt surface format:

```
STOP: audit-against-system: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

N/A — this skill IS the compliance gate.

## Boundary — does not

- Does not modify the audited code, markup, or CSS. Suggested fixes are recommendations; the caller (or the owning composer) applies them.
- Does not certify compliance. Absence of violations in a scoped audit is not blanket certification — it only states that the rules in the chosen scope did not fail against the target as inspected.
- Does not invent rules. Every finding cites a reference file; if a behavior is undefined in the reference, the finding is `undefined-in-reference`, not a fabricated violation.
- Does not author stylesheet CSS as a deliverable; the silent freshness stage INVOKES the internal `generate-css` machinery when inputs have moved, then proceeds — never as an instruction to the human. Does not generate new UI (the composers) or surface reference into an author's context for proactive use (`apply-design-system`).
- Does not infer rendering context from inspecting host-project code surrounding the target — the caller declares it.
