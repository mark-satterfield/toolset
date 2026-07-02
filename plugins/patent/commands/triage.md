---
description: Triage shaped ideas — rank by priority, identify coverage gaps, and produce a focused "bring to my lawyer next" list with what's ready and what's missing for each top idea.
argument-hint: ""
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# /patent:triage

Invoke the `patent-triage` skill across every idea in `patents/ideas/`.

## Process

1. Ensure `patents/portfolio.md` exists. If absent or missing a moat-thesis section, the skill prompts the user to provide one.
2. Walk every `patents/ideas/{slug}/idea.md` and its sibling files (`eligibility.md`, `enforceability.md`, `decision.md`).
3. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/patent-triage/SKILL.md`.
4. Output is an updated `portfolio.md` with:
   - Top-ranked priority table across all shaped ideas
   - Coverage gaps in your moat thesis (your thinking gaps, with inventor-actionable recommendations)
   - "Bring to lawyer next" list — what's ready, what's missing
   - Discussion points to raise with your lawyer (provisional windows, continuation/divisional candidates, maintenance-horizon decisions)
   - Tier-by-tier discussion strategy

## Notes

- The acceptance criterion: this is an actionable ranking with concrete inventor next-steps and concrete lawyer talking-points — not a neutral summary.
- This skill does NOT track docket dates, recommend filings, or compute fees. Items the lawyer owns are surfaced as discussion points, not action items.
- Run after any meaningful change: a new idea reaches `assessed`, a tier shifts, you come back from a lawyer meeting and need to plan the next one.
