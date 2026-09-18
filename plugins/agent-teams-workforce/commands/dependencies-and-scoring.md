---
description: "Maintain the dependency edges and the WSJF scores over every Epic and Task"
argument-hint: "[--all]"
allowed-tools: [Bash, Read, Agent, Skill]
---

# Dependencies and scoring

Recalculate the dependency edges between Epics and the WSJF scores on Epics and Tasks in
the beads tracker. Load `agent-teams-workforce:dependencies-and-scoring` and follow it;
this command is the entry point, not a second copy of the procedure.

There is ONE operation. Its scope comes off the tracker and the material-change queue:
everything when nothing is scored yet, and what a declared change reached when something
changed. `--all` includes the items that already carry a score, so every open Epic and its
Tasks are recalculated. When `$ARGUMENTS` contains `--all`, pass it to the skill's `query`
and `score` steps; anything else in `$ARGUMENTS` is ignored.

It writes. There is no dry run.

An Epic that is recalculated has its Tasks recalculated with it, in the same pass: value
and time criticality flow down to the Tasks, their sizes flow back up and replace the
Epic's estimate. That is not a second command and there is nothing to remember afterwards.

## Report back

- The scope, and why each Epic is in it. A scope of `none` is a finished answer: everything
  is scored and nothing has declared a change.
- The edges added and withdrawn, with the reason the reasoning pass gave for each.
- The Epics and Tasks scored, and anything that came back `incomplete` — a Task with no
  judged size is a decomposition that did not finish, and it needs naming.

## Never

- Start a pipeline run, a supervisor, a keeper or the dashboard from here. This ends with a
  report; a person starts the run.
- Apply an edge set that failed validation.
- Decide what is eligible to work on. Edges and scores are inputs to that decision, and
  whatever consumes them makes it.
