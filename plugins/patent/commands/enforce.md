---
description: Score the strategic value of an idea — detectability, designability difficulty, evidence-path, and FTO risk. Outputs enforceability.md with a tier recommendation (S/A/B/C/D).
argument-hint: "[slug or path to idea.md]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# /patent:enforce

Invoke the `patent-enforceability` skill on a claim-ready (or assessed) idea.

## Process

1. Resolve `$ARGUMENTS`:
   - If a slug, look up `patents/ideas/{slug}/idea.md`.
   - If a path, use it.
   - If empty, list every idea at funnel stage `assessed` or `claim-ready` and ask which to score.
2. Prefer claim-ready ideas (claims pin scope, which sharpens the scoring). If only `assessed` is available, proceed but flag the score as provisional.
3. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/patent-enforceability/SKILL.md`.
4. On completion, recommend either `/patent:claims` (if not yet drafted), `/patent:document` (if a tier-S/A idea is ready to convert to filing), or `/patent:triage` (for portfolio-level next steps).

## Notes

- Patentability and enforceability are scored independently. This command does not re-litigate Alice eligibility.
- A high enforceability tier is not a guarantee of value — it is a recommendation. Final filing decisions depend on the inventor's strategic context.
