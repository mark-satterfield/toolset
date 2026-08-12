---
description: Open any generated output — a Shell, a Page HTML, a View, an isolated Section or Component — in the visual review harness; click regions, attach comments, and copy out one change request that routes back to the owning composer.
argument-hint: "[path to a generated .html; empty resolves the most recent composer output]"
allowed-tools: Read, Bash, Glob, AskUserQuestion
---

# /cds:review

Invoke the `review` skill in this plugin. Load and execute `skills/review/SKILL.md` and follow its discovery checklist (resolve the target artifact → identify the owning composer → locate sidecars → resolve the harness output path), pipeline, halt conditions, and boundary exactly.

## Process

1. Load `skills/review/SKILL.md`.
2. Treat `$ARGUMENTS` as the artifact path or a plain-language reference to it. If `$ARGUMENTS` is empty, resolve the most recent composer state record's `output_path` (compose-page, compose-shell, or compose-view); if none exists, ask the user which output to review.
3. Run `${CLAUDE_PLUGIN_ROOT}/tools/build-review-harness.py` via Bash to emit `<basename>.review.html` beside the artifact, then `open` it in the browser.
4. Tell the user to hover regions (Section identity badges), click to pin comments, and press Copy — then paste the assembled change request back here. The pasted request routes to the composer that owns the artifact (`compose-page`, `compose-shell`, or `compose-view`) as an iteration against the same output path.

## Notes

- Opens ANY generated output: a Page HTML, a Shell, a View, or an isolated Section / Component render.
- The harness is one self-contained HTML file: the artifact renders unmodified in an iframe (light/dark toggle intact), regions map to the wireframe sidecar's Section blocks (fallback labels "Region 1..N" when no sidecar or counts mismatch), and the bottom panel builds one natural-language change request grouped by region.
- Quick tags per comment: copy, layout, color, spacing, swap-shape, remove, add. Only non-empty comments appear in the change request.
- The `.review.html` is a review artifact, not a deliverable — `package-change` does not bundle it. Delete it freely; re-running the command regenerates it deterministically.
- Halt codes the user may see: `TARGET_UNREADABLE`, `REVIEW_HARNESS_FAILED`, `STYLESHEETS_REGEN_FAILED`.
