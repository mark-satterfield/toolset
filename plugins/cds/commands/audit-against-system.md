---
description: Audit existing UI (file paths, rendered URL, or pasted markup/CSS) against the design system's compliance rules and emit a report with citations and suggested fixes.
argument-hint: "[file path, set of paths, URL, or pasted markup/CSS] [--inline | --report]"
allowed-tools: Read, Glob, Grep, WebFetch
---

# /cds:audit-against-system

Invoke the `audit-against-system` skill in this plugin. Load and execute `skills/audit-against-system/SKILL.md` and follow its discovery checklist, pipeline, halt conditions, and reporting format exactly.

## Process

1. Load `skills/audit-against-system/SKILL.md`.
2. Treat `$ARGUMENTS` as the target plus optional output-format flag. If `$ARGUMENTS` is empty, ask: "What should I audit — a file path, a URL, or pasted markup/CSS? And do you want inline annotations or a structured report?"
3. Run the discovery checklist (what is being audited → surface kind → rendering context [caller-declared, never inferred] → page type → audit scope → output format).
4. Apply the pipeline: load the rule set from `compliance.md` filtered by the declared rendering context, walk the target rule-by-rule, flag undefined-in-reference patterns as findings, emit the report in the chosen output format.

## Notes

- This command IS the compliance gate. It does not have one of its own.
- The caller declares the rendering context (`app-embedded` or `standalone`) — the skill does NOT infer it from host-project inspection.
- Every finding cites a reference file. Absence of violations in a scoped audit is NOT blanket certification.
- Halt codes the user may see: `MISSING_SPEC`, `PRECONDITION_FAILED`, `ELEMENTS_YAML_UNSET`.
