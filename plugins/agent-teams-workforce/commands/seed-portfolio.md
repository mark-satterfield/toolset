---
description: "Seed the Epic portfolio once: summaries, optionally dependencies, then a full WSJF re-judge"
argument-hint: "[--assess]"
allowed-tools: [Bash, Workflow]
---

# Seed the portfolio

A one-time batch over the beads tracker of the repository you are standing in. The normal
path sets summaries, edges and scores as Epics and Tasks are created or changed; this sets
them for the whole portfolio at once. It writes.

It runs three workflows in order, and stops at the first that returns `ok: false`:

1. `epic-summaries` — a summary for every open Epic that has none or whose PRD changed.
2. `dependency-assessment` in mode `portfolio`, **only with `--assess`**. Without it the
   edges already in the tracker stand.
3. `wsjf-scoring` with `all` and `rejudge` — every Epic's value, urgency and size, and every
   Task's size, judged again, then the arithmetic.

## Dispatch

```bash
REPO="$(git rev-parse --show-toplevel)"
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
echo "REPO=$REPO"
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
echo "RUN=$RUN"
echo "SAD=${ATW_SAD_PATH}"
echo "PROJECT=${ATW_PROJECT_ROOT}"
```

Use the printed values below; `<BASE>` is `<REPO>/.claude/workflow-runs/seed-portfolio/<RUN>`.
Leave `sadPath` or `projectRoot` out of every call when its value printed empty.

```
Workflow({scriptPath: "<ROOT>/workflows/epic-summaries.js", args: {
  repoPath: "<REPO>", pluginRoot: "<ROOT>", workDir: "<BASE>/summaries",
  sadPath: "<SAD>", projectRoot: "<PROJECT>"
}})
```

With `--assess` in `$ARGUMENTS`:

```
Workflow({scriptPath: "<ROOT>/workflows/dependency-assessment.js", args: {
  repoPath: "<REPO>", pluginRoot: "<ROOT>", workDir: "<BASE>/assessment",
  sadPath: "<SAD>", projectRoot: "<PROJECT>",
  mode: "portfolio", score: false
}})
```

`score: false` because the next step scores the whole portfolio.

```
Workflow({scriptPath: "<ROOT>/workflows/wsjf-scoring.js", args: {
  repoPath: "<REPO>", pluginRoot: "<ROOT>", workDir: "<BASE>/scoring",
  sadPath: "<SAD>", projectRoot: "<PROJECT>",
  all: true, rejudge: true
}})
```

## Report back

Per step: `ok`, and the step's own report — summaries written and missing; edges added,
converted and withdrawn; Epics and Tasks judged, scored and written, with the unscored,
incomplete and outside-range counts. When a step stopped the seeding, which one and its
`error`, `failures` and `dispatchFailures`, verbatim.

## Never

- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
