---
description: "Assess the architecture dependencies of one Epic"
argument-hint: "<epic-id> [--propose]"
allowed-tools: [Bash, Workflow]
---

# Dependency assessment

Assess the architecture dependencies of one Epic in the beads tracker of the repository you
are standing in, by dispatching the `dependency-assessment` workflow. An edge between two
Epics is an architecture dependency: an architecture decision one Epic rests on should be
designed from another Epic's requirements first, and the matrix does not hold that decision approved
(`agent-teams-workforce:epic-sequencing`). The workflow writes the Epic's edges to beads. It
writes nothing to the matrix and scores nothing.

The owner runs this command; the driver never dispatches the workflow. The order of every Epic
is set before `keeper.py` runs by `scripts/portfolio/epicorder.py`, which computes it from the
matrix chain alone, and its `--apply` removes every Epic-to-Epic edge in beads, this command's
included, and writes the computed ones. WSJF is scored
once, before `keeper.py` runs, by the owner's own `/agent-teams-workforce:wsjf-scoring`.

`<epic-id>` is required: the one Epic to assess. Report the usage and stop
without it. The epic-dependency-assessor reads that Epic's full PRD, at the path the matrix holds for it,
and names the architecture decisions its requirements drive and the ones it rests on. It asks
the matrix what already states each decision (`atw-matrix find --kinds document,constraint,feature`,
then `atw-matrix node`) and drops only those an Epic's elaboration has already approved (the
matrix `approved` flag). An `effective` document is approved content, but it still iterates with
each Epic, so being effective alone does not remove the need for an edge.
It takes the related Epics from the matrix (`atw-matrix related --epic`, and
`atw-matrix find --kinds requirement,feature` for an Epic no feature serves yet), reads those
PRDs in full, and applies the edge test in both directions. It proposes every edge to or from
the Epic with a reason, and keeps or withdraws, with a reason, every owned edge standing on
it. Code refuses any edge that does not touch the Epic, a cycle, an unaccounted standing edge
and a missing reason, and writes only that Epic's edges. Hand-made edges are never touched.
The session checks its proposal with the validate command and writes nothing to beads or the
matrix. The workflow validates the proposal and runs apply-edges, which validates it again and
writes nothing unless it passes. The Epic-to-Epic edge is a beads `tracks` edge, and the matrix
records no Epic-to-Epic relationship.
A proposal that does not validate stops the run, naming the Epic and each finding, and writes
nothing.

It writes, unless `--propose` is given.

- `--propose` passes `apply: false`: the workflow computes the edge diff as a dry run,
  returns it, and writes nothing — no edge, no reason, no matrix relationship.

## Dispatch

The environment variables read below are named and described by the `pipeline-contracts` skill
(`${CLAUDE_PLUGIN_ROOT}/skills/pipeline-contracts/SKILL.md`, schema
`schemas/driver-surface.schema.json`, `$defs.DriverEnvironment`). The block reads each name from
that skill's generated module (`PRD_DIR_ENV`, `ARCH_PATH_ENV`, `PROJECT_ROOT_ENV`); never type a
name from memory. The PRD folder is required: the matrix holds each PRD's path relative to the
vault that folder is in, and the workflow's context step locates the vault from it. The other
two are optional: the matrix, not the architecture folder, is what the assessment judges against.

```bash
CONTRACTS="${CLAUDE_PLUGIN_ROOT}/skills/pipeline-contracts/scripts"
{ read -r PRD_VAR; read -r PRD_DIR; read -r ARCH; read -r PROJECT; } < <(PYTHONPATH="$CONTRACTS" python3 -c 'import os, driver_surface_types as d; print(d.PRD_DIR_ENV); print(os.environ.get(d.PRD_DIR_ENV, "")); print(os.environ.get(d.ARCH_PATH_ENV, "")); print(os.environ.get(d.PROJECT_ROOT_ENV, ""))')
if [ -z "${PRD_VAR}" ]; then
  echo "REFUSED: the pipeline-contracts skill could not be loaded from ${CONTRACTS}."
  exit 1
fi
if [ -z "${PRD_DIR}" ]; then
  echo "REFUSED: ${PRD_VAR} is not set. /agent-teams-workforce:dependency-assessment reads each Epic's PRD at the path the matrix holds for it, which is relative to the vault that folder is in. Export ${PRD_VAR} in your shell environment and start a new session."
  exit 1
fi
REPO="$(git rev-parse --show-toplevel)"
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
echo "REPO=$REPO"
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
echo "RUN=$RUN"
echo "ARCH=${ARCH}"
echo "PROJECT=${PROJECT}"
```

When the block prints `REFUSED`, report that line verbatim and stop; dispatch nothing.

Use the printed values below. Leave `archPath` out when it printed empty, and `projectRoot`
likewise. `<REPO>` is the control repository: its tracker holds the Epics, and its
`ops/sdlc-automation/matrix.json` is the matrix the workflow reads.

```
Workflow({name: "agent-teams-workforce:dependency-assessment", args: {
  repoPath:    "<REPO>",
  pluginRoot:  "<ROOT>",
  workDir:     "<REPO>/.claude/workflow-runs/dependency-assessment/<RUN>",
  archPath:    "<ARCH>",
  projectRoot: "<PROJECT>",
  epic:        "<epic-id>",
  apply:       false         (with --propose only)
}})
```

## Report back

From the workflow's result:

- `edges` — the counts `added`, `converted`, `removed`, `withdrawn` and `unchanged`. The
  edges themselves are in the file `edges.resultFile` names: every edge added, converted or
  removed as `blocker -> blocked` from its `plan.add`, `plan.convert` and `plan.remove`, and
  every withdrawal with its reason from its `withdrawn`. Then the reasoning file
  (`edges.reasoning`), which holds the Epics whose PRDs the session read in full and the edges
  the sequencer was unsure of. When `edges.applied` is false, its `reason`, or the validation
  defects.
- `stop` — when the proposal did not validate: the Epic and every finding in
  `stop.findings`, with the `edgesFile` and `validationFile`, and what a person does: correct
  the PRD, or the hand-made edge a cycle runs through, then assess the Epic again.
- With `--propose`: `edges.proposed`, then the counts and the edges read from
  `edges.resultFile` as above — there they are the diff that would be written — the proposed
  edge set with its reasons (`edgesFile`) and the reasoning (`reasoning`).
- `error` and `dispatchFailures`, verbatim, when present.

## Never

- Score anything, or start `wsjf-scoring`.
- Write to the tracker with `--propose`.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
