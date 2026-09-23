---
description: "Seed the portfolio once: the per-Epic dependency assessment for every open Epic, then WSJF scoring over the new edges"
argument-hint: "[--since <iso>]"
allowed-tools: [Bash, Workflow]
---

# Seed the portfolio

A one-time run over the beads tracker of the repository you are standing in, by dispatching
the `seed-portfolio` workflow. Seeding is both halves: dependency assessment and WSJF
scoring. The normal path assesses an Epic's architecture dependencies and scores it when it
is created or changed; seeding does the same for every open Epic at once. It writes.

`seed-portfolio.js` assesses every open Epic not assessed since `since`, one Epic after
another in id order, each in one session that applies its own edges with their reasons and
sees every edge the earlier ones set. When every Epic is assessed and applied, it runs
`wsjf-scoring` itself, once: missing values are judged, and the arithmetic recomputes RR-OE
from the new edges and every WSJF over every open item.

An assessment whose edge proposal does not validate stops the seeding at that Epic, writes
nothing for it, and nothing is scored. An edge between two Epics is an architecture dependency
(`agent-teams-workforce:epic-sequencing`).

- `--since <iso>` resumes an interrupted seeding: pass the `since` the interrupted run
  printed. Only the Epics not assessed since then are assessed, then the workflow scores. Without
  it, `since` is now.

## Dispatch

```bash
if [ -z "${ATW_SAD_PATH}" ]; then
  echo "REFUSED: ATW_SAD_PATH is not set. /agent-teams-workforce:seed-portfolio judges against the architecture document (the arc42 SAD) and does not run without it. Export ATW_SAD_PATH in your shell environment and start a new session."
  exit 1
fi
REPO="$(git rev-parse --show-toplevel)"
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
SINCE="<the value after --since in $ARGUMENTS, or empty>"
[ -n "$SINCE" ] || SINCE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
WORK="$REPO/.claude/workflow-runs/seed-portfolio/$RUN"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/portfolio/depscore.py" assess-plan -C "$REPO" --since "$SINCE" --out "$WORK/seed-plan.json" \
  | python3 -c 'import json,sys; print("EPICS=" + json.dumps(json.load(sys.stdin)["summary"]["unassessedIds"]))'
echo "REPO=$REPO"
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
echo "WORK=$WORK"
echo "SINCE=$SINCE"
echo "SAD=${ATW_SAD_PATH}"
echo "PROJECT=${ATW_PROJECT_ROOT}"
```

When the block prints `REFUSED`, or `EPICS=` is missing, report the output verbatim and stop;
dispatch nothing.

Tell the user the printed `SINCE` and the number of Epics before dispatching: an interrupted
seeding resumes with `--since <SINCE>`. Use the printed values below. Leave `projectRoot` out
when it printed empty. Pass `EPICS` as a JSON list. When it is empty, dispatch anyway: the workflow then only
scores.

### The seeding

```
Workflow({name: "agent-teams-workforce:seed-portfolio", args: {
  repoPath:    "<REPO>",
  pluginRoot:  "<ROOT>",
  workDir:     "<WORK>",
  since:       "<SINCE>",
  epics:       <EPICS>,
  sadPath:     "<SAD>",
  projectRoot: "<PROJECT>"
}})
```

`ok` is false: stop and report `stage` and `headline`. The seeding either refused its
arguments (`stage: input` — correct the dispatch; nothing ran), stopped at an Epic
(`stoppedAt`) and scored nothing, or assessed every Epic and scoring failed (`scoring`). In
the last two a resume with `--since <SINCE>` finishes it; `stage: agent-dispatch-failed`
means the sessions died rather than the work failing, and the same resume applies once the
API is back.

When `ok` is true, check what is left, from the tracker rather than the workflow's word:

```bash
python3 "<ROOT>/scripts/portfolio/depscore.py" assess-plan -C "<REPO>" --since "<SINCE>" --out "<WORK>/seed-plan-after.json" \
  | python3 -c 'import json,sys; print("LEFT=" + json.dumps(json.load(sys.stdin)["summary"]["unassessedIds"]))'
```

`LEFT` is not empty: report those Epics and tell the user to resume with `--since <SINCE>`.
An Epic listed there either changed during the seeding or was reported applied without its
assessment being recorded.

Anything else in `$ARGUMENTS` is ignored.

## Report back

From the seeding result:

- `since`, so the seeding can be resumed.
- `assessed` — per Epic: edges added, converted and withdrawn, and the `unchanged` count;
  every added edge as `blocker -> blocked` with its reason, from the Epic's `edgesFile` and
  `resultFile`; every withdrawal as `blocker -> blocked` with its reason.
- `stoppedAt` — when the seeding stopped: the Epic, its `error` and `dispatchFailures`,
  verbatim, and the `remaining` Epics. When its edge proposal did not validate, also every
  finding in `findings`, with the `edgesFile` and `validationFile`, and what a person does:
  correct the PRD, or the hand-made edge a cycle runs through, then resume with
  `--since <since>`.
- `LEFT`, when it is not empty.
- `scoring` — the `wsjf-scoring` result the seeding returned, reported as
  `/agent-teams-workforce:wsjf-scoring` reports it; when it is null, say that nothing was
  scored and why (the seeding stopped).
- `dispatchFailures`, verbatim, when present.

## Never

- Dispatch `dependency-assessment` or `wsjf-scoring` yourself; the seeding runs both.
- Run two seedings at once: each assessment must see the edges the earlier ones set.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
