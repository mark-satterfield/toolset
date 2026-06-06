---
description: Compose a standalone HTML mock — full page (landing / blog / doc / sign-in / announcement), a section in isolation, or a single component in isolation. Also handles iteration on prior mocks.
argument-hint: "[plain-language request, content path, or output_path of a prior run]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:compose-page

Invoke the `compose-page` skill in this plugin. Load and execute `skills/compose-page/SKILL.md` and follow its discovery checklist (handoff check → state-directory check → page type → surface kind → content mode → asset paths → mandatory/forbidden/leading elements → stylesheet staleness), pipeline, halt conditions, and compliance gate exactly.

## Process

1. Load `skills/compose-page/SKILL.md`.
2. Treat `$ARGUMENTS` as the caller's plain-language request, supplied-content pointer, or output-path target. If `$ARGUMENTS` is empty, ask the user what they want to mock.
3. Run the discovery checklist in the exact order defined in the skill — step 1 (handoff check) routes app-embedding requests to `/cds:compose-app-surface`.
4. Apply the pipeline: load page-type rules, derive section sequence + shape, resolve content, render the self-contained HTML at the resolved output path, run the compliance pass, write the state record.

## Notes

- Default surface kind is a full page. Section-in-isolation and component-in-isolation are wrapped in a minimal HTML container (1440px content width, 64px outer padding, light-mode default with a top-right toggle).
- Iteration: if a state record exists at the resolved `output_path`, the skill loads the prior `brief_snapshot` and `sections` and treats the request as a modification. Matching uses strict `output_path` equality.
- Page types whose shape rules are present in the reference compose; types without rules halt with `SHAPE_RULES_PENDING:{page-type}` (no guessing).
- The emitted HTML inlines the stylesheet set; it does NOT contain agent-side metadata.
