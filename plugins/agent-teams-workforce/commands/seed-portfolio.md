---
description: "Seed the portfolio once: the per-Epic dependency assessment for every open Epic, in batches, then a full WSJF re-judge"
argument-hint: "[--since <iso>] [--batch <n>]"
allowed-tools: [Bash, Workflow]
---

# Seed the portfolio

A one-time batch over the beads tracker of the repository you are standing in, by
dispatching the `seed-portfolio` workflow again and again, then the `wsjf-scoring` workflow.
The normal path assesses an Epic's architecture dependencies and scores it when it is
created or changed; seeding does the same for every open Epic at once. It writes.

Each run of `seed-portfolio.js` assesses one batch: at most `--batch` open Epics (default
40, at most 100) not assessed since `since`, one Epic after another in id order, each
applying its own edges with their reasons and seeing every edge the earlier ones set. It
returns the Epics still to assess in `remaining` and never scores. You run it again, one run
after another with the same `since`, until `remaining` is empty, because the runtime caps a
workflow at 1000 agent sessions and a batch must fit inside that. Then scoring runs, as its
own workflow: `wsjf-scoring` with `all` and `rejudge` judges every Epic's value, urgency and
size, and every Task's size, again, then runs the arithmetic.

An assessment whose edge proposal does not validate is assessed again with the validator's
findings, at most twice; if it still does not validate, the seeding stops at that Epic and
writes nothing for it. An edge between two Epics is an architecture dependency
(`agent-teams-workforce:epic-sequencing`).

- `--since <iso>` resumes an interrupted seeding: pass the `since` the interrupted run
  printed. Only the Epics not assessed since then are assessed, in batches, then scoring
  runs; when there are none, the first batch returns `remaining` empty and scoring runs.
  Without it, `since` is now.
- `--batch <n>` sets the most Epics one run assesses, from 1 to 100. Without it, 40.

## Dispatch

```bash
if [ -z "${ATW_SAD_PATH}" ]; then
  echo "REFUSED: ATW_SAD_PATH is not set. /agent-teams-workforce:seed-portfolio judges against the architecture document (the arc42 SAD) and does not run without it. Set ATW_SAD_PATH in the project's environment (for Claude Code, the env block of the project's .claude/settings.json) and start a new session."
  exit 1
fi
REPO="$(git rev-parse --show-toplevel)"
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
SINCE="<the value after --since in $ARGUMENTS, or empty>"
[ -n "$SINCE" ] || SINCE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BATCH="<the value after --batch in $ARGUMENTS, or empty>"
[ -n "$BATCH" ] || BATCH=40
echo "REPO=$REPO"
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
echo "RUN=$RUN"
echo "SINCE=$SINCE"
echo "BATCH=$BATCH"
echo "SAD=${ATW_SAD_PATH}"
echo "PROJECT=${ATW_PROJECT_ROOT}"
```

When the block prints `REFUSED`, report that line verbatim and stop; dispatch nothing.

Tell the user the printed `SINCE` before dispatching: an interrupted seeding resumes with
`--since <SINCE>`. Use the printed values below. Leave `projectRoot` out when it printed empty.
Pass `BATCH` as a number.

### The batches

Start with `n = 1`.

1. Dispatch
   ```
   Workflow({scriptPath: "<ROOT>/workflows/seed-portfolio.js", args: {
     repoPath:    "<REPO>",
     pluginRoot:  "<ROOT>",
     workDir:     "<REPO>/.claude/workflow-runs/seed-portfolio/<RUN>/batch-<n>",
     since:       "<SINCE>",
     batch:       <BATCH>,
     sadPath:     "<SAD>",
     projectRoot: "<PROJECT>"
   }})
   ```
2. Tell the user `batch <n>: <assessed count> assessed, <remaining count> remain`.
3. `ok` is false: stop, report, and do not score.
4. `remaining` is empty: go to scoring.
5. `assessed` is empty and `remaining` is not: stop and report that the batch made no
   progress, naming `remaining`; do not score.
6. Otherwise `n = n + 1` and go to 1, with the same `SINCE` and `BATCH`.

### Scoring

Only after a batch returned `ok: true` with `remaining` empty, dispatch from here:

```
Workflow({scriptPath: "<ROOT>/workflows/wsjf-scoring.js", args: {
  repoPath:    "<REPO>",
  pluginRoot:  "<ROOT>",
  workDir:     "<REPO>/.claude/workflow-runs/wsjf-scoring/<RUN>",
  sadPath:     "<SAD>",
  projectRoot: "<PROJECT>",
  all:         true,
  rejudge:     true
}})
```

Anything else in `$ARGUMENTS` is ignored.

## Report back

From the batches' results and the scoring result:

- `since`, so the seeding can be resumed.
- One line per batch, as step 2 of the batches told it.
- `assessed`, over all batches — per Epic: edges added, converted and withdrawn, and the
  `unchanged` count; every added edge as `blocker -> blocked` with its reason, from the
  Epic's `edgesFile` and `resultFile`; every withdrawal in `withdrawn` as
  `blocker -> blocked` with its reason.
- `stoppedAt` — when a batch stopped: the Epic, its `error`, `failures` and
  `dispatchFailures`, verbatim, and the `remaining` Epics. When its edge proposal did not
  validate, also the `attempts` and every finding in `findings`, with the `edgesFile` and
  `validationFile`, and what a person does: correct the PRD, or the hand-made edge a cycle
  runs through, then resume with `--since <since>`.
- `remaining` — the open Epics still not assessed since `since`; scoring runs only when it
  is empty.
- `scoring` — the `wsjf-scoring` result, reported as `/agent-teams-workforce:wsjf-scoring`
  reports it.
- `failures` and `dispatchFailures`, verbatim, when present.

## Never

- Dispatch `dependency-assessment` yourself; each batch runs it, one Epic at a time.
- Run two batches at once: each assessment must see the edges the earlier ones set.
- Dispatch `wsjf-scoring` before a batch returns `remaining` empty, or with anything but
  `all` and `rejudge`.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
