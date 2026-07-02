---
description: Draft patent claims for an assessed idea — broad independent claim plus 5–10 dependent claims, with method/system/CRM variants and 35 USC 112 compliance checks. Outputs claims.md.
argument-hint: "[slug or path to idea.md]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# /patent:claims

Invoke the `patent-claim-drafting` skill on an assessed idea.

## Process

1. Resolve `$ARGUMENTS`:
   - If a slug, look up `patents/ideas/{slug}/idea.md`.
   - If a path, use it.
   - If empty, list every idea at funnel stage `assessed` and ask which to draft claims for.
2. Verify funnel stage is `assessed`. If earlier, redirect to `/patent:assess` first.
3. Verify `eligibility.md` exists and contains the Step 2b conclusion that bounds claim scope.
4. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/patent-claim-drafting/SKILL.md`.
5. On completion (funnel stage `claim-ready`), recommend `/patent:enforce` as the next step.

## Notes

- Claim language is the legal scope of the invention. The skill's 112 compliance checklist must pass before the output is considered complete.
- Method, system, and CRM variants are mirrored — same invention, three statutory categories.
