---
description: "Assess the Epic dependency edges for one Epic or the whole portfolio, then score"
argument-hint: "<epic-id> | --portfolio [--propose]"
allowed-tools: [Bash, Workflow]
---

# Dependency assessment

Assess the Epic-to-Epic dependency edges in the beads tracker of the repository you are
standing in, by dispatching the `dependency-assessment` workflow. An Epic edge records design
order: an architecture decision one Epic rests on should be designed from another Epic's
requirements first (`agent-teams-workforce:epic-sequencing`). The workflow writes edges and
nothing else, then triggers `wsjf-scoring`, because edges decide RR-OE.

- `<epic-id>` assesses that one Epic — new or changed — against the portfolio's summaries
  and its own full PRD. Only edges to or from that Epic are added or withdrawn.
- `--portfolio` assesses the whole portfolio.

Exactly one of the two is required; report the usage and stop otherwise. It writes, unless
`--propose` is given.

- `--propose` passes `apply: false`: the workflow reads the summaries as stored, computes the
  edge diff as a dry run, returns it, and writes nothing — no summary, no edge, no score.

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

Use the printed values below. Leave `sadPath` or `projectRoot` out when its value printed
empty.

```
Workflow({scriptPath: "<ROOT>/workflows/dependency-assessment.js", args: {
  repoPath:    "<REPO>",
  pluginRoot:  "<ROOT>",
  workDir:     "<REPO>/.claude/workflow-runs/dependency-assessment/<RUN>",
  sadPath:     "<SAD>",
  projectRoot: "<PROJECT>",
  mode:        <"portfolio" for --portfolio, otherwise "epic">,
  epic:        "<epic-id>"   (mode "epic" only),
  apply:       false         (with --propose only)
}})
```

## Report back

From the workflow's result:

- `edges` — added, converted, withdrawn and unchanged; the reasoning file (`tiering`); the
  edges the sequencer was unsure of. When `edges.applied` is false, its `reason`, or the
  validation defects.
- With `--propose`: `edges.proposed`, then every edge in `edges.added`, `edges.converted`
  and `edges.removed` as `blocker -> blocked`, the `unchanged` count, the
  `protectedHandMadeEdges`, and the files holding the full diff (`diffFile`), the proposed
  edge set with its reasons (`edgesFile`) and the reasoning (`tiering`).
- `scoring` — the `wsjf-scoring` result it triggered, reported as that command reports it.
- `failures` and `dispatchFailures`, verbatim, when present.

## Never

- Score anything; the triggered `wsjf-scoring` does.
- Write to the tracker with `--propose`.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
