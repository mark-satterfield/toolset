---
description: "Assess the architecture dependencies of one Epic, then score"
argument-hint: "<epic-id> [--propose]"
allowed-tools: [Bash, Workflow]
---

# Dependency assessment

Assess the architecture dependencies of one Epic in the beads tracker of the repository you
are standing in, by dispatching the `dependency-assessment` workflow. An edge between two
Epics is an architecture dependency: an architecture decision one Epic rests on should be
designed from another Epic's requirements first, and the SAD does not already settle it
(`agent-teams-workforce:epic-sequencing`). The workflow writes edges and nothing else, then
triggers `wsjf-scoring`, because edges decide RR-OE.

`<epic-id>` is required: the one Epic, new or changed, to assess. Report the usage and stop
without it. The epic-sequencer reads that Epic's full PRD, names the architecture decisions its
requirements drive and the ones it rests on, drops those the SAD settles, searches the other
Epics' PRDs for the requirements that drive or rest on each remaining decision, reads those
PRDs in full, and applies the edge test in both directions. It proposes every edge to or from
the Epic with a reason, and keeps or withdraws, with a reason, every owned edge standing on
it. Code refuses any edge that does not touch the Epic, a cycle, an unaccounted standing edge
and a missing reason, and writes only that Epic's edges. Hand-made edges are never touched.
Code validates every proposal; one that does not validate is assessed again with the
validator's findings, at most twice, and then the run stops, naming the Epic and each
finding, and writes nothing.

It writes, unless `--propose` is given.

- `--propose` passes `apply: false`: the workflow computes the edge diff as a dry run,
  returns it, and writes nothing — no edge, no reason, no score.

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
  epic:        "<epic-id>",
  apply:       false         (with --propose only)
}})
```

## Report back

From the workflow's result:

- `edges` — added, converted, withdrawn and unchanged; every withdrawal in `edges.withdrawn`
  as `blocker -> blocked` with its reason; the reasoning file (`reasoning`); the edges the
  sequencer was unsure of. When `edges.applied` is false, its `reason`, or the validation
  defects.
- `assessment.relatedRead` — the Epics whose PRDs the session read in full, and `attempts`.
- `stop` — when no attempt validated: the Epic, the `attempts` and every finding in
  `stop.findings`, with the `edgesFile` and `validationFile`, and what a person does: correct
  the PRD, or the hand-made edge a cycle runs through, then assess the Epic again. Under the
  ops triggers the Epic is assessed again once its content changes.
- With `--propose`: `edges.proposed`, then every edge in `edges.added`, `edges.converted`
  and `edges.removed` as `blocker -> blocked`, `edges.withdrawn` with reasons, the
  `unchanged` count, the `protectedHandMadeEdges`, and the files holding the full diff
  (`diffFile`), the proposed edge set with its reasons (`edgesFile`) and the reasoning
  (`reasoning`).
- `scoring` — the `wsjf-scoring` result it triggered, reported as that command reports it.
- `failures` and `dispatchFailures`, verbatim, when present.

## Never

- Score anything; the triggered `wsjf-scoring` does.
- Write to the tracker with `--propose`.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
