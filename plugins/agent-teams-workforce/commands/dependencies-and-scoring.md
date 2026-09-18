---
description: "Maintain the dependency edges and the WSJF scores over every Epic and Task"
argument-hint: "[--all]"
allowed-tools: [Bash, Workflow]
---

# Dependencies and scoring

Recalculate the dependency edges between Epics and the WSJF scores on every open Epic and
Task in the beads tracker of the repository you are standing in, by dispatching the
`dependencies-and-scoring` workflow. The workflow does all of it; this command resolves its
arguments, dispatches it, and reports.

Every run recomputes the whole portfolio's arithmetic. A model judges only what the content
it is judged from changed since it was last judged, or what was never judged. `--all`
re-judges every judged input and re-derives the edges whatever the fingerprints say — for
seeding, or after the rubric or the edge test changes.

It writes. There is no dry run.

## Dispatch

```bash
REPO="$(git rev-parse --show-toplevel)"
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
echo "REPO=$REPO"
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
echo "RUN=$RUN"
```

Use the three printed values below.

```
Workflow({scriptPath: "<ROOT>/workflows/dependencies-and-scoring.js", args: {
  repoPath:   "<REPO>",
  pluginRoot: "<ROOT>",
  workDir:    "<REPO>/.claude/workflow-runs/dependencies-and-scoring/<RUN>",
  all:        <true when $ARGUMENTS contains --all, otherwise false>
}})
```

Anything else in `$ARGUMENTS` is ignored.

## Report back

From the workflow's result:

- `plan` — how many Epics and Tasks were judged and why, and whether the sequencer ran.
- `edges` — added, withdrawn and unchanged; the tiering account's path; the edges the
  sequencer was unsure of. When `edges.ran` is false, its `reason`.
- `score` — Epics and Tasks scored and written, and the counts of unscored and incomplete
  items. Name them from `<workDir>/score.json`: a Task with no inherited value sits under an
  unscored Epic or under no Epic; an `incomplete` Epic has Tasks with no size.
- `failures` and `dispatchFailures`, verbatim, when present.

## Never

- Start a pipeline run, a supervisor, a keeper or the dashboard from here. This ends with a
  report; a person starts the run.
- Decide what is eligible to work on. Edges and scores are inputs to that decision, and
  whatever consumes them makes it.
