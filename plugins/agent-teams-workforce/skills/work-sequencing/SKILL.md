---
name: work-sequencing
description: >-
  Sequence ALL the work — a batch pass over every Epic and every Task that sets the
  dependency edges, scores them with WSJF, and keeps both current. Eligibility and
  priority are separate: edges decide what CAN be worked, WSJF decides what SHOULD go
  first among what can. Epic edges gate ELABORATION only and are tested against the
  blocker's elaboration_state, never `bd ready`; Task edges use `bd ready` and gate
  building. Run it before the next pipeline run and whenever Epics or Tasks are added,
  scored, or decomposed. Triggers on /work-sequencing, "sequence the work", "set the
  dependency edges", "why is nothing eligible", "seed the WSJF scores".
allowed-tools: [Bash, Read, Agent]
---

# Work Sequencing

One pass, two halves, and the split is the whole design.

- **Deterministic** — reading the tracker, proving an edge set applicable, applying the
  diff, and all the WSJF arithmetic. Scripts do this. Running it twice over the same
  tracker produces the same answer and costs nothing.
- **Judged** — which Epic must be designed before which. ONE reasoning agent does this,
  reading the whole portfolio at once, and it emits an edge file the scripts then check.

Nothing here invents a rubric. Scores come from `agent-teams-workforce:epic-wsjf` and
`agent-teams-workforce:task-wsjf`; metadata keys come from
`agent-teams-workforce:beads-contract`, which is also the only writer.

## Eligibility and priority are different questions

| | Eligibility — what CAN be worked | Priority — what goes FIRST |
|---|---|---|
| Epic | every blocking Epic's `elaboration_state` is `done` | Epic WSJF, descending |
| Task | `bd ready` semantics: blockers closed, not deferred | Task WSJF, descending |

**Epic edges gate elaboration and nothing else.** They never gate building or deploying a
Task. A blocking Epic stays OPEN until its requirements are in production, sometimes for
months, so `bd ready` would hold every Epic behind it forever and hold the Tasks beneath
them too. The test is the blocker's `elaboration_state == done` — the Tasks were written —
and `sequencing.py eligibility` is the one implementation of it.

Do not add an edge merely to force a total order. Edges exist for the cases where one
Epic's architecture must be designed from another Epic's requirements. WSJF orders the
rest, and an edge added "for tidiness" removes an Epic from the eligible pool for months.

## Run it

```bash
SEQ="${CLAUDE_PLUGIN_ROOT}/skills/work-sequencing/scripts/sequencing.py"
python3 "$SEQ" <command> [-C <repoPath>] [--apply]
```

Every command prints ONE JSON object naming the tracker source it read — `bd` when `bd`
answered, the passive `.beads/issues.jsonl` export when it did not, and it says so rather
than letting a caller assume. **Nothing writes without `--apply`**; the default is a dry
run that reports exactly what it would do.

| Command | What it does |
|---|---|
| `snapshot` | The tracker as a graph: Epics, Stories, Tasks, lineage, blockers, scores. What the reasoning pass reads. `--with-description` for the PRD text, `--include-closed` for finished work. |
| `validate --edges <file>` | Proves a proposed edge set applicable: reports the cycle, dangling ids, self-edges, edges onto closed items, duplicates. |
| `apply-edges --edges <file> [--apply]` | Applies the DIFF through `bd dep <blocker> --blocks <blocked>`. Idempotent. |
| `score-tasks [--apply]` | Inherits each Task's value from its Epic (walking Story → Epic), computes RR-OE from the graph, recomputes WSJF. No model call. |
| `rollup-epics [--apply]` | Replaces each Epic's span estimate with the sum of its Tasks' job sizes and rescores it. |
| `eligibility` | Which Epics may be elaborated now, and for each of the rest, why not. |

### The edge file

```json
{"edges": [
  {"from": "<blocker>", "to": "<blocked>", "reason": "<one line>", "confidence": "high"}
]}
```

`from` must be elaborated before `to`. `reason` and `confidence` are for the person
reading the proposal; the scripts carry them through and do not judge them.

## A hand-made edge is never removed

The pass records the edges IT created on the blocked bead as `seq_owned_blockers`. The
diff only ever withdraws an edge in that list. An edge Mark drew by hand is invisible to
the withdrawal path and survives every pass, however the proposal changes.

This is why `apply-edges` is safe to re-run: with an unchanged proposal it adds nothing,
removes nothing, and writes no metadata.

## The order of a full pass

1. `snapshot` → hand it to the reasoning pass (below) → an edge file.
2. `validate --edges` → fix the proposal until `ok` is true. A cycle is a wrong edge, not
   a tie to break.
3. `apply-edges --edges` → read the plan → re-run with `--apply`.
4. Epics that carry no score: run `agent-teams-workforce:epic-wsjf` on each. **This is the
   one part of a seed that costs money**, and it is judged per Epic, not batched here.
5. `score-tasks --apply` → every Task under a scored Epic is now scored, arithmetically.
6. `rollup-epics --apply` → Epics with Tasks beneath them trade their span estimate for
   the sum of those Tasks. Top-down value, bottom-up cost.
7. `eligibility` → confirm the pool is non-empty and nothing is `unscored`.

An incremental pass is the same steps over a smaller proposal. Steps 5 and 6 are free and
should be re-run whenever a decomposition lands.

## The reasoning pass

Dispatch ONE `epic-sequencer` agent. Not a team — splitting domains across agents costs
more and produces a worse answer, because the judgment being made is precisely about how
domains relate to each other, and no agent holding one domain can make it.

Its procedure is `references/reasoning-pass.md`; its starting grouping is
`references/domain-table.md`, which is Mark's own and is **known to be imperfect** —
correcting it is part of the job.

## When it runs

- **On demand.** `/agent-teams-workforce:work-sequencing` — a full seed or an incremental
  pass. Mark starts it; a seed costs money and nothing starts one on its own.
- **When scored items are missing.** `eligibility` reporting anything in `unscored` means
  the provider cannot sort its own pool. That is a request for sequencing, not a fallback
  to an invented order.
- **When a decomposition lands.** `score-tasks` and `rollup-epics` are arithmetic; re-run
  them and the portfolio stays current for free.

## Errors to avoid

- Adding an Epic edge to express "this is more important". That is WSJF's job, and an edge
  costs the blocked Epic its eligibility until the blocker's Tasks are written.
- Testing Epic eligibility with `bd ready`. A blocking Epic is open for months.
- Judging a Task's value from the Task's own text. It is inherited, always.
- Removing an edge the pass does not own.
- Re-scoring an Epic from its Tasks. Only COST rolls up; value stays top-down.
