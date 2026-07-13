---
description: Open a composed mock in the visual review harness — click regions, attach change comments, and copy out one change request that feeds compose-page iteration.
argument-hint: "[path to a composed mock .html; empty resolves the most recent mock]"
allowed-tools: Read, Bash, Glob, AskUserQuestion
---

# /cds:review-mock

Invoke the `review-mock` skill in this plugin. Load and execute `skills/review-mock/SKILL.md` and follow its discovery checklist (resolve the target mock → locate sidecars → resolve the harness output path), pipeline, halt conditions, and boundary exactly.

## Process

1. Load `skills/review-mock/SKILL.md`.
2. Treat `$ARGUMENTS` as the mock path or a plain-language reference to it. If `$ARGUMENTS` is empty, resolve the most recent `compose-page` state record's `output_path`; if none exists, ask the user which mock to review.
3. Run `tools/build-review-harness.py` via Bash to emit `<basename>.review.html` beside the mock, then `open` it in the browser.
4. Tell the user to hover regions (Section identity badges), click to pin comments, and press Copy — then paste the assembled change request back here. The pasted request routes to `compose-page` iteration against the same output path.

## Notes

- The harness is one self-contained HTML file: the mock renders unmodified in an iframe (light/dark toggle intact), regions map to the wireframe sidecar's Section blocks (fallback labels "Region 1..N" when no sidecar or counts mismatch), and the bottom panel builds one natural-language change request grouped by region.
- Quick tags per comment: copy, layout, color, spacing, swap-shape, remove, add. Only non-empty comments appear in the change request.
- The `.review.html` is a review artifact, not a deliverable — `package-change` does not bundle it. Delete it freely; re-running the command regenerates it deterministically.
- Halt codes the user may see: `TARGET_UNREADABLE`, `REVIEW_HARNESS_FAILED`.
