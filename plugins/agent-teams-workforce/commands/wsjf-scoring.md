---
description: "Score open Epics and Tasks with WSJF from their existing dependency edges"
argument-hint: "[--all] [--rejudge]"
allowed-tools: [Bash, Read, Write]
---

# WSJF scoring

The owner invokes this command to score the portfolio. It reads dependency edges and sets none.
Genuine judgment remains one session per Epic and one grouped Task session per Epic. Planning,
input preparation, validation, recording and scoring arithmetic run directly in Python.

`--all` includes items with existing values. `--rejudge` judges the included existing values again.
Without these flags, only missing or changed source content requires judgment. The command writes
accepted judgments and computed values; a failed judgment leaves its items unjudged while other
valid judgments remain eligible for recording.

Read `pipeline-contracts` and the WSJF rubric. Resolve the current repository with
`git rev-parse --show-toplevel` and create a unique run directory under its
`.claude/workflow-runs/wsjf-scoring/`. Use `${CLAUDE_PLUGIN_ROOT}` as the plugin root. Preserve
the configured project, architecture and PRD/vault environment from the generated driver-surface
contract. Report missing required environment before launching reasoning work.

Write `args.json` in that directory:

- `repoPath`, `pluginRoot`, `workDir`: their absolute paths.
- `archPath`, `projectRoot`: the configured values when present.
- `all`, `rejudge`: booleans corresponding to the requested flags.
- `only`: an empty list unless the owner explicitly requests item IDs.
- `dryRun`: false for the normal owner command.

Run once through Bash:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/atw-portfolio" wsjf-scoring --args "<run>/args.json" --output "<run>/result.json"
```

Read the result file. Report the planned items, genuine judgment sessions, failed item IDs,
recording rejections and final scores, with the evidence directory. Do not run a Workflow or
start a command-runner agent. Do not assess or change any dependency edge.
