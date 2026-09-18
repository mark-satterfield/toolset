---
name: dependencies-and-scoring
description: >-
  Maintain the dependency edges and the WSJF scores over the Epics and Tasks in the beads
  tracker. ONE operation — recalculate — whose SCOPE varies: everything when nothing is
  scored yet, and what a declared material change reached when something changed. The two
  mechanisms it maintains are separate on purpose: edges decide ELIGIBILITY (what may be
  elaborated at all), WSJF decides PRIORITY among what is eligible. It writes; there is no
  dry run and no mode. Triggers on /dependencies-and-scoring, "set the dependency edges",
  "score the Epics", "refresh the WSJF scores", "nothing is scored".
allowed-tools: [Bash, Read, Agent, Skill]
---

# Dependencies and scoring

This maintains two things over the tracker and nothing else: the **dependency edges**
between Epics, and the **WSJF scores** on Epics and Tasks. It does not decide what to work
on and it does not start anything.

Nothing here invents a rubric. Scores come from `agent-teams-workforce:wsjf`, at Epic level
and at Task level; metadata keys come from `agent-teams-workforce:beads-contract`, which is
also the only writer.

## What each mechanism decides

Two decisions put foundations first, and they answer different questions from one input.

- **The dependency graph decides ELIGIBILITY** — what may be elaborated or built at all. An
  Epic whose architecture must be designed from another Epic's requirements is blocked
  until that one is elaborated.
- **WSJF decides PRIORITY** among what is already eligible. It is what makes the Epic that
  establishes a canonical pattern (sign-up and sign-in) outrank one that merely consumes it
  (password reset).

The graph is the input to both. `agent-teams-workforce:wsjf` computes RR-OE from transitive
reachability in it at Epic level, and does the same over the Task graph at Task level, so
the edges decide eligibility directly and set priority through RR-OE.

Eligibility is not computed here. This skill supplies the inputs — the edges and the scores
— and whatever consumes them decides from those.

**The edge set is therefore the only place either decision can be corrected.** Draw every
edge that passes the derivation test and none that does not.

## One operation, and its scope

There is one thing this does — recalculate — and only its scope varies. The scope is read
off the tracker and the material-change queue. **No flag sets it.**

| What is true | The scope |
|---|---|
| Nothing carries a score yet | Everything: every Epic, every Task, edges and scores |
| A material change was declared | The Epics that change reached, and their Tasks with them |
| Something arrived unscored | The Epic it belongs to, and its Tasks |
| Every Epic edge changed in this pass | The whole portfolio — establish-versus-consume is judged relative to it, so a changed edge moves scores beyond the Epic it touched |
| Nothing declared, nothing unscored | Nothing. Say so and stop |

A materially changed or new PRD, or an architecture decision, reaches particular Epics; the
recalculation covers those Epics **and their Tasks**. Where the change genuinely shifts the
portfolio's ranking the rescore widens to the portfolio; where it does not, it does not.

**A recalculated Epic recalculates its Tasks. Always, in the same pass.** Value and time
criticality flow DOWN from the Epic to its Tasks; size flows UP from the Tasks and replaces
the Epic's estimate, and the Epic's score is recomputed from that concrete number. One
loop, not two commands, and never something a person has to remember to run afterwards.

**Nothing is skipped because it already carries a score.** A score is a function of a graph
that moves. If an item is in scope it is recomputed and the old value is overwritten.

## It writes

There is no dry run and no `--apply`. A run costs the same money whether or not it writes,
so a rehearsal is pure waste. An unchanged proposal adds no edge, withdraws none and writes
no metadata — that is what makes a re-run free, not a dry run.

## The pass

The steps below are the skill's internals. A person runs
`/agent-teams-workforce:dependencies-and-scoring`; this is what happens when they do.

```bash
DS="${CLAUDE_PLUGIN_ROOT}/skills/dependencies-and-scoring/scripts/depscore.py"
```

1. **`scope`** — read what this pass covers and why. Report it before doing anything. A
   `none` scope ends the pass: say so rather than inventing work.
2. **`snapshot --kinds epic --with-description`** — the whole Epic portfolio. Even a narrow
   scope reads it whole, because the judgment in step 3 is about how Epics relate.
3. **The reasoning pass** — dispatch ONE `epic-sequencer` agent over that snapshot. Not a
   team: splitting domains across agents costs more and answers worse, because the
   judgment is precisely about how domains relate and no agent holding one domain can make
   it. Its procedure is `references/reasoning-pass.md`. It reads the snapshot and returns
   the edge set and the tiering that produced it. When the scope is narrow it proposes
   edges for the in-scope Epics only.
4. **`validate --edges <file>`** — fix the proposal until `ok` is true. A cycle is a wrong
   edge, not a tie to break.
5. **`apply-edges --edges <file> [--epics <scope>]`** — applies the diff through
   `bd dep`. Pass the scope so withdrawal is confined to it; omit it only for a
   portfolio-wide pass. If anything was added or removed, the scope widens to the
   portfolio for the rest of the pass.
6. **`agent-teams-workforce:wsjf` at Epic level, over the portfolio** — the judged part,
   and the part that costs money. It runs AFTER the edges are applied, because it computes
   RR-OE from the graph they form. One session scores every in-scope Epic, including ones
   that already carry a score; never split the Epic set across sessions and never hand the
   scoring session calibration bands of your own — the rubric owns its bands. Write the
   result with the `beads-contract` CLI, and carry any `graphDefects` it reports into the
   report at step 8.
7. **`score [--epics <scope>]`** — the arithmetic: every in-scope Epic and its Tasks, value
   down and size up, in one loop.
8. **Report** — the scope and why, the edges added and withdrawn, the Epics and Tasks
   scored, and everything `incomplete` came back with. An `incomplete` entry naming a
   missing `wsjf_size` is a decomposition that did not size its Tasks; say which.

## A hand-made edge is never removed

The pass records the edges IT created on the blocked bead as `seq_owned_blockers`. The diff
only ever withdraws an edge in that list, and only within the pass's scope. An edge drawn
by hand is invisible to the withdrawal path and survives every pass.

## The edge file

```json
{"edges": [
  {"from": "<blocker>", "to": "<blocked>", "reason": "<one line>", "confidence": "high"}
]}
```

`from` must be elaborated before `to`. `reason` and `confidence` are for the person reading
the proposal; the scripts carry them through and do not judge them.

## When it runs

- **On demand.** `/agent-teams-workforce:dependencies-and-scoring`. A person starts it.
- **When a material change is queued.** A pending declaration means an agent that produced a
  work product DECLARED that what it changed is something others depend on, and named the
  decision ids. That declaration IS the scope. Recalculate against it, then drain.

  Nothing here is triggered by a timestamp, a file mtime or a content hash, and nothing ever
  will be: an mtime moves when a formatter runs and a hash changes when a sentence is
  reworded, and neither says whether anything else depends on what changed. Only the agent
  that did the work knows that, so only a declaration counts.
- **When a decomposition lands.** Its Tasks arrive unscored, so its Epic is in scope on the
  next pass without anyone asking for it.

## Errors to avoid

- Adding an Epic edge to express "this is more important". That is WSJF's job, and an edge
  costs the blocked Epic its eligibility until the blocker is elaborated.
- Withholding an edge that passes the derivation test because the fan-out looks excessive.
  It releases an Epic that is not ready and computes its blocker's RR-OE as though nothing
  were designed from it.
- Handing the scoring session calibration bands, expected distributions, or a reachability
  table of your own. The rubric computes what it needs; supplied bands replace it.
- Deciding eligibility here, or reimplementing it. This skill supplies its inputs only.
- Judging a Task's value from the Task's own text. It is inherited, always.
- Removing an edge the pass does not own, or one outside its scope.
- Re-scoring an Epic from its Tasks' value. Only COST rolls up; value stays top-down.
- Leaving an Epic scored and its Tasks stale. They are one recalculation.
