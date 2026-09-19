---
description: "Seed the portfolio once: the per-Epic dependency assessment for every open Epic, then a full WSJF re-judge"
argument-hint: "[--since <iso>]"
allowed-tools: [Bash, Workflow]
---

# Seed the portfolio

A one-time run over the beads tracker of the repository you are standing in, by dispatching
the `seed-portfolio` workflow, then the `wsjf-scoring` workflow. The normal path assesses an
Epic's architecture dependencies and scores it when it is created or changed; seeding does
the same for every open Epic at once. It writes.

`seed-portfolio.js` assesses every open Epic not assessed since `since`, one Epic after
another in id order, each in one session that applies its own edges with their reasons and
sees every edge the earlier ones set. It never scores. Then scoring runs, as its own
workflow: `wsjf-scoring` with `all` and `rejudge` judges every Epic's value, urgency and
size, and every Task's size, again, then runs the arithmetic.

An assessment whose edge proposal does not validate stops the seeding at that Epic and
writes nothing for it. An edge between two Epics is an architecture dependency
(`agent-teams-workforce:epic-sequencing`).

- `--since <iso>` resumes an interrupted seeding: pass the `since` the interrupted run
  printed. Only the Epics not assessed since then are assessed, then scoring runs. Without
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
when it printed empty. Pass `EPICS` as a JSON list. When it is empty, go to scoring.

### The seeding

```
Workflow({scriptPath: "<ROOT>/workflows/seed-portfolio.js", args: {
  repoPath:    "<REPO>",
  pluginRoot:  "<ROOT>",
  workDir:     "<WORK>",
  since:       "<SINCE>",
  epics:       <EPICS>,
  sadPath:     "<SAD>",
  projectRoot: "<PROJECT>"
}})
```

`ok` is false: stop, report, and do not score.

When `ok` is true, check what is left, from the tracker rather than the workflow's word:

```bash
python3 "<ROOT>/scripts/portfolio/depscore.py" assess-plan -C "<REPO>" --since "<SINCE>" --out "<WORK>/seed-plan-after.json" \
  | python3 -c 'import json,sys; print("LEFT=" + json.dumps(json.load(sys.stdin)["summary"]["unassessedIds"]))'
```

`LEFT` is not empty: stop and report those Epics; do not score. An Epic listed there either
changed during the seeding or was reported applied without its assessment being recorded.

### Scoring

Only after the seeding returned `ok: true` and `LEFT` is empty, dispatch from here:

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

From the seeding result and the scoring result:

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
- `scoring` — the `wsjf-scoring` result, reported as `/agent-teams-workforce:wsjf-scoring`
  reports it.
- `dispatchFailures`, verbatim, when present.

## Never

- Dispatch `dependency-assessment` yourself; the seeding runs it, one Epic at a time.
- Run two seedings at once: each assessment must see the edges the earlier ones set.
- Dispatch `wsjf-scoring` before the seeding returns `ok: true` with `LEFT` empty, or with
  anything but `all` and `rejudge`.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
