---
name: issue-ready
description: Orchestrates the full 3-skill readiness pipeline for any issue. Runs /issue-review then /wsjf in sequence, posting an incremental comment at each step. Builds a full audit trail on the ticket. Triggers on /issue-ready or when user says "is this ready to implement", "run the pipeline", "prepare this issue".
---

# Issue Ready — Pipeline Orchestrator

Orchestrate /issue-review and /wsjf in sequence for any work item. Post an incremental
comment to the ticket after each step. Every run adds to the audit trail — never
overwrites prior comments.

Never ask clarifying questions. Run with what you have.

## Input Handling

- Beads issue ID (ssbd-xxxx) — run `bd show <id> --json`
- GitHub issue number — run `gh issue view <n>`
- Inline text — assess directly (no comment posted; output to chat only)
- No argument — ask once: "Paste the issue ID or describe the work item."

## Pipeline Execution

### Step 1 — Run /issue-review

Execute the /issue-review command against the issue. Capture the full structured output.

**Post comment to ticket:**
```
## Issue Review — [ISO 8601 timestamp]

[Full /issue-review output]
```

If result is INCOMPLETE:
- Post the comment with all findings
- Stop. Do not proceed to /wsjf.
- Respond to chat with the findings and recommended next actions

If result is COMPLETE (all dimensions ✅):
- Post the comment and continue to Step 2

### Step 2 — Run /wsjf

Execute the /wsjf command against the issue content. Capture the full structured output.

**Post comment to ticket:**
```
## WSJF Score — [ISO 8601 timestamp]

[Full /wsjf output]
```

### Step 3 — Ready Declaration

**Post final comment to ticket:**
```
## Ready for Implementation — [ISO 8601 timestamp]

This issue passed completeness review and has been scored.

WSJF: [score]
Cost of Delay: [CoD]
Job Size: [size]

Cleared for implementation.
```

### Step 4 — Store WSJF Score as Machine-Readable Metadata

Run the following to make the issue pipeline-eligible:

```
bd update <id> --notes "wsjf_score: <score>"
```

- `<id>` is the beads issue ID (e.g. `bd-42`)
- `<score>` is the numeric WSJF score from Step 2 (e.g. `8.75`)
- The pipeline reads this `wsjf_score` note to confirm an issue has been scored and to
  order ready issues by WSJF (highest first) when selecting the next bead to work —
  ordering is by WSJF score, never by P0–P4 priority labels
- If the issue already has notes, append `wsjf_score: <score>` on a new line rather
  than replacing existing content

Respond to chat with the WSJF score and confirmation.

## Audit Trail Rules

- Every run of /issue-ready appends new comments — never edits or deletes prior comments
- All comments include ISO 8601 timestamps
- If /issue-ready is run again after gaps are addressed, a new full review cycle begins
- The ticket's comment history is the canonical record of all review iterations

## Comment Posting

For Beads issues: `bd comment add <id> --body "..."`
For GitHub issues: `gh issue comment <n> --body "..."`

## Output Format (to chat)

After pipeline completes, respond with:

```
Pipeline result: [READY / INCOMPLETE]
Issue: [id or title]
Review: [COMPLETE / INCOMPLETE — n dimensions need attention]
WSJF: [score or "not scored — incomplete"]
Comments posted: [n]
```
