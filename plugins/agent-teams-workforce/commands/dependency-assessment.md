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
The session validates its proposal and runs apply-edges, which validates it again and
writes nothing unless it passes. A proposal that does not validate stops the run, naming
the Epic and each finding, and writes nothing.

It writes, unless `--propose` is given.

- `--propose` passes `apply: false`: the workflow computes the edge diff as a dry run,
  returns it, and writes nothing — no edge, no reason, no score.

## Dispatch

```bash
if [ -z "${ATW_SAD_PATH}" ]; then
  echo "REFUSED: ATW_SAD_PATH is not set. /agent-teams-workforce:dependency-assessment judges against the architecture document (the arc42 SAD) and does not run without it. Export ATW_SAD_PATH in your shell environment and start a new session."
  exit 1
fi
REPO="$(git rev-parse --show-toplevel)"
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
echo "REPO=$REPO"
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
echo "RUN=$RUN"
echo "SAD=${ATW_SAD_PATH}"
echo "PROJECT=${ATW_PROJECT_ROOT}"
```

When the block prints `REFUSED`, report that line verbatim and stop; dispatch nothing.

Use the printed values below. Leave `projectRoot` out when it printed empty.

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
- `assessment.relatedRead` — the Epics whose PRDs the session read in full.
- `stop` — when the proposal did not validate: the Epic and every finding in
  `stop.findings`, with the `edgesFile` and `validationFile`, and what a person does: correct
  the PRD, or the hand-made edge a cycle runs through, then assess the Epic again. Under the
  ops triggers the Epic is assessed again once its content changes.
- With `--propose`: `edges.proposed`, then every edge in `edges.added`, `edges.converted`
  and `edges.removed` as `blocker -> blocked`, `edges.withdrawn` with reasons, the
  `unchanged` count, and the files holding the full diff (`resultFile`), the proposed edge set with its reasons (`edgesFile`) and the reasoning
  (`reasoning`).
- `scoring` — the `wsjf-scoring` result it triggered, reported as that command reports it.
- `error` and `dispatchFailures`, verbatim, when present.

## Never

- Score anything; the triggered `wsjf-scoring` does.
- Write to the tracker with `--propose`.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
