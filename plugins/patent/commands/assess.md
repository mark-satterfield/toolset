---
description: Run patentability assessment on a shaped idea — Alice/Mayo two-step, EPO further-technical-effect, and prior-art search across PatentsView, Google Patents, EPO, web, arXiv, GitHub. Outputs eligibility.md and prior-art.md.
argument-hint: "[slug or path to idea.md]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, AskUserQuestion
---

# /patent:assess

Invoke the `patent-patentability` skill on a shaped idea.

## Process

1. Resolve `$ARGUMENTS`:
   - If it is a slug (e.g., `database-indexing-adaptive-bloom`), look up `patents/ideas/{slug}/idea.md`.
   - If it is a path, use that path.
   - If empty, list every idea at funnel stage `shaped` or later in `patents/ideas/` and ask the user which to assess.
2. Verify the idea is at funnel stage `shaped` or later. If `raw`, redirect to `/patent:idea` to complete shaping.
3. Load and execute `skills/patent-patentability/SKILL.md`.
4. On completion (funnel stage `assessed`), recommend `/patent:claims` as the next step.

## Notes

- Prior-art searches can be slow. Use the cache in `patents/prior-art-cache/` aggressively.
- If any external integration fails, the eligibility output must flag the coverage gap, not hide it.
