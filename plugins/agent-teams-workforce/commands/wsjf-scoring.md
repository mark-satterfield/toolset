---
description: "Score every open Epic and Task with WSJF from the dependency edges already in beads"
argument-hint: "[--all] [--rejudge]"
allowed-tools: [Bash, Workflow]
---

# WSJF scoring

Score every open Epic and Task in the beads tracker of the repository you are standing in,
by dispatching the `wsjf-scoring` workflow. The workflow does all of it; this command
resolves its arguments, dispatches it, and reports.

Scoring reads the dependency edges from beads and never sets one. A model judges only
values that are missing or whose source content changed: each Epic from its full PRD, one
Epic per session, and each Epic's Tasks together, in a session per Epic. Then the
arithmetic runs over the whole portfolio and only changed values are written.

- `--all` includes items that already have a value.
- `--rejudge` judges the existing values of the included items again.

Together they re-judge every Epic and Task. It writes.

## Dispatch

```bash
if [ -z "${ATW_SAD_PATH}" ]; then
  echo "REFUSED: ATW_SAD_PATH is not set. /agent-teams-workforce:wsjf-scoring judges against the architecture document (the arc42 SAD) and does not run without it. Set ATW_SAD_PATH in the project's environment (for Claude Code, the env block of the project's .claude/settings.json) and start a new session."
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
Workflow({name: "agent-teams-workforce:wsjf-scoring", args: {
  repoPath:    "<REPO>",
  pluginRoot:  "<ROOT>",
  workDir:     "<REPO>/.claude/workflow-runs/wsjf-scoring/<RUN>",
  sadPath:     "<SAD>",
  projectRoot: "<PROJECT>",
  all:         <true when $ARGUMENTS contains --all, otherwise false>,
  rejudge:     <true when $ARGUMENTS contains --rejudge, otherwise false>
}})
```

Anything else in `$ARGUMENTS` is ignored.

## Report back

From the workflow's result:

- `plan` — how many Epics and Tasks were judged, the state counts (`missing`, `changed`,
  `unfingerprinted`, `current`), and how many stored values were adopted.
- `judging` — per level, the sessions run, the items judged, and the ids of the items
  whose session failed (for Tasks, the failed groups too, in `failedGroups`).
- `judgingFailed` — every Epic and Task a failed judging session left unjudged, with
  `error`. A failed session fails the run (`ok: false`): those items keep no new value and
  stay to judge, while the judgments that did return are recorded and scored.
- `record` — values written and adopted; `rejected`, each judgment refused for a value off
  the rubric's scale, named with its reason from `<workDir>/record.json`; and `missing`,
  what the plan asked for and no session returned.
- `score` — Epics and Tasks scored and written, and the counts of unscored, incomplete and
  outside-range items. Name them from `<workDir>/score.json`: a Task with no inherited value
  sits under an unscored Epic or under no Epic; an `incomplete` Epic has Tasks with no size.
- `failures` and `dispatchFailures`, verbatim, when present.

## Never

- Assess or change a dependency edge. That is `/agent-teams-workforce:dependency-assessment`.
- Start a pipeline run, a supervisor, a keeper or the dashboard from here.
- Decide what is eligible to work on. Edges and scores are inputs to that decision, and
  whatever consumes them makes it.
