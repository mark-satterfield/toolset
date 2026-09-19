---
description: "Seed the portfolio once: the per-Epic dependency assessment for every open Epic, then a full WSJF re-judge"
argument-hint: "[--since <iso>]"
allowed-tools: [Bash, Workflow]
---

# Seed the portfolio

A one-time batch over the beads tracker of the repository you are standing in, by
dispatching the `seed-portfolio` workflow. The normal path assesses an Epic's architecture
dependencies and scores it when it is created or changed; seeding does the same for every
open Epic at once. It writes.

The workflow runs the per-Epic `dependency-assessment` for every open Epic not assessed
since `since`, one Epic after another in id order, each applying its own edges with their
reasons and seeing every edge the earlier ones set. An assessment whose edge proposal does
not validate is assessed again with the validator's findings, at most twice; if it still
does not validate, the seeding stops at that Epic and writes nothing for it. An edge between two Epics is an
architecture dependency (`agent-teams-workforce:epic-sequencing`). When every open Epic has
been assessed since `since`, it runs `wsjf-scoring` with `all` and `rejudge`: every Epic's
value, urgency and size, and every Task's size, judged again, then the arithmetic.

- `--since <iso>` resumes an interrupted seeding: pass the `since` the interrupted run
  printed. Only the Epics not assessed since then are assessed, then scoring runs. Without
  it, `since` is now.

## Dispatch

```bash
REPO="$(git rev-parse --show-toplevel)"
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
SINCE="<the value after --since in $ARGUMENTS, or empty>"
[ -n "$SINCE" ] || SINCE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "REPO=$REPO"
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
echo "RUN=$RUN"
echo "SINCE=$SINCE"
echo "SAD=${ATW_SAD_PATH}"
echo "PROJECT=${ATW_PROJECT_ROOT}"
```

Tell the user the printed `SINCE` before dispatching: an interrupted seeding resumes with
`--since <SINCE>`. Use the printed values below. Leave `sadPath` or `projectRoot` out when
its value printed empty.

```
Workflow({scriptPath: "<ROOT>/workflows/seed-portfolio.js", args: {
  repoPath:    "<REPO>",
  pluginRoot:  "<ROOT>",
  workDir:     "<REPO>/.claude/workflow-runs/seed-portfolio/<RUN>",
  since:       "<SINCE>",
  sadPath:     "<SAD>",
  projectRoot: "<PROJECT>"
}})
```

Anything else in `$ARGUMENTS` is ignored.

## Report back

From the workflow's result:

- `since`, so the seeding can be resumed.
- `assessed` — per Epic: edges added, converted and withdrawn, and the `unchanged` count;
  every added edge as `blocker -> blocked` with its reason, from the Epic's `edgesFile` and
  `resultFile`; every withdrawal in `withdrawn` as `blocker -> blocked` with its reason.
- `stoppedAt` — when the seeding stopped: the Epic, its `error`, `failures` and
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

- Dispatch `dependency-assessment` or `wsjf-scoring` yourself; the workflow runs both, in
  order.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
