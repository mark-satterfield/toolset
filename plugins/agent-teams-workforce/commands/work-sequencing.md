---
description: "Sequence all the work — set the dependency edges and WSJF scores, or refresh them"
argument-hint: "[--seed | --incremental] [--apply]"
allowed-tools: [Bash, Read, Agent, Skill]
---

# Work sequencing

Set the dependency edges over every Epic and every Task, score them, and keep both
current. Load `agent-teams-workforce:work-sequencing` and follow it; this command is the
entry point, not a second copy of the procedure.

`$ARGUMENTS` picks the shape:

- `--seed` — the full pass, including the reasoning pass over the whole Epic portfolio and
  an `epic-wsjf` run on every unscored Epic. **This costs money** and it is Mark's to
  start. It is a precondition for the next pipeline run, not a fallback.
- `--incremental` (the default) — the arithmetic half only: `score-tasks`, `rollup-epics`,
  and an `eligibility` report. Free, and safe to run after any decomposition lands.

Nothing writes without `--apply`. Run every step dry first and read the plan.

## Incremental

```bash
SEQ="${CLAUDE_PLUGIN_ROOT}/skills/work-sequencing/scripts/sequencing.py"
python3 "$SEQ" score-tasks                  # dry run — read it
python3 "$SEQ" score-tasks --apply
python3 "$SEQ" rollup-epics --apply
python3 "$SEQ" eligibility
```

Report the eligible pool, anything in `unscored`, and every Epic held with its reason.
An `unscored` entry means the provider cannot sort its pool: that Epic needs `epic-wsjf`,
which is a seed step, not something to improvise past.

## Seed

1. `python3 "$SEQ" snapshot --kinds epic --with-description > <out>/snapshot.json`
2. Dispatch ONE `epic-sequencer` agent over that snapshot. One session, not a team.
3. `python3 "$SEQ" validate --edges <out>/edges.json` — fix until `ok` is true.
4. `python3 "$SEQ" apply-edges --edges <out>/edges.json` → read the plan →
   re-run with `--apply`.
5. Run `agent-teams-workforce:epic-wsjf` on every Epic with no `wsjf`, and write the score
   with the `beads-contract` CLI. This is the expensive part and it is judged per Epic.
6. The incremental steps above, in order.

Then `eligibility` should report a non-empty pool with nothing `unscored`. If it does not,
say which step left it that way rather than starting a run.

## Never

- Start a pipeline run, a supervisor, a keeper or the dashboard from here. Sequencing ends
  with a report; Mark starts the run.
- Apply an edge set that `validate` refused.
- Invent an order for unscored work.
