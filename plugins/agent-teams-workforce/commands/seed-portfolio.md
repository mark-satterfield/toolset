---
description: "Seed the Epic portfolio once: optionally dependencies, then a full WSJF re-judge"
argument-hint: "[--assess | --propose]"
allowed-tools: [Bash, Workflow]
---

# Seed the portfolio

A one-time batch over the beads tracker of the repository you are standing in. The normal
path sets edges and scores as Epics and Tasks are created or changed; this sets
them for the whole portfolio at once. It writes.

It runs two workflows in order, and stops at the first that returns `ok: false`:

1. `dependency-assessment` in mode `portfolio`, **only with `--assess`** — the Epic
   architecture-dependency edges, set before any score. Without it the edges already in the tracker
   stand.
2. `wsjf-scoring` with `all` and `rejudge` — every Epic's value, urgency and size, and every
   Task's size, judged again, then the arithmetic.

With `--propose` it runs `dependency-assessment` in mode `portfolio` with
`apply: false`, and stops there: it reports the proposed edge diff against the edges in the
tracker, writes no edge and runs no scoring. `--assess` and `--propose` are exclusive; report
the usage and stop when both are given.

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

With `--assess` in `$ARGUMENTS`:

```
Workflow({scriptPath: "<ROOT>/workflows/dependency-assessment.js", args: {
  repoPath: "<REPO>", pluginRoot: "<ROOT>", workDir: "<BASE>/assessment",
  sadPath: "<SAD>", projectRoot: "<PROJECT>",
  mode: "portfolio", score: false
}})
```

`score: false` because the next step scores the whole portfolio.

With `--propose` in `$ARGUMENTS`, instead of the call above:

```
Workflow({scriptPath: "<ROOT>/workflows/dependency-assessment.js", args: {
  repoPath: "<REPO>", pluginRoot: "<ROOT>", workDir: "<BASE>/proposal",
  sadPath: "<SAD>", projectRoot: "<PROJECT>",
  mode: "portfolio", apply: false
}})
```

Then stop: `wsjf-scoring` does not run.

```
Workflow({scriptPath: "<ROOT>/workflows/wsjf-scoring.js", args: {
  repoPath: "<REPO>", pluginRoot: "<ROOT>", workDir: "<BASE>/scoring",
  sadPath: "<SAD>", projectRoot: "<PROJECT>",
  all: true, rejudge: true
}})
```

## Report back

With `--propose`: the proposed diff — every edge to add,
convert and withdraw as `blocker -> blocked` with its reason from `edgesFile`, the
`unchanged` count, the `protectedHandMadeEdges`, and the paths of `diffFile`, `edgesFile`
and `tiering`.

Otherwise, per step: `ok`, and the step's own report — edges added,
converted and withdrawn; Epics and Tasks judged, scored and written, with the unscored,
incomplete and outside-range counts. When a step stopped the seeding, which one and its
`error`, `failures` and `dispatchFailures`, verbatim.

## Never

- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
