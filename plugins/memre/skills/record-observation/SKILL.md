---
name: record-observation
description: >-
  Use the moment you have something worth recording and aren't sure where it
  belongs — a fact you learned, a decision you settled, an action someone must take
  later, a step or thought worth keeping across sessions, or something the user
  should just see now. Fires when you catch yourself about to stitch that record
  into a deliverable, a commit message, or a code comment because you have nowhere
  else to put it. Classifies the record and hands it to the sink skill that owns
  it; never lets it drop silently.
allowed-tools: [Read, Skill]
---

<!-- residue-lint:ignore-file (this router quotes the decision-narration vocabulary to route it) -->

# Where a recordable thing goes

A model fuses the work with the story of how it was made, because the surest way it
knows to honor an instruction is to write it down — and the one place it fully
controls is the deliverable. This skill breaks that reflex by giving the record a
real home.

Invariant: every urge to record ends at exactly one sink. Never drop it. If a
sink skill can't complete the write, it falls back to console with the drafted
record and the reason. Silence is the only forbidden outcome.

This skill only classifies. Each sink owns its own resolution and enforcement —
which backend, what fields are required — so route to the right one and let it do
the rest.

## Pick the sink (first match wins)

1. **Names an action not yet done → Issue.** States something someone must do
   later. Invoke [`record-issue`](../record-issue/SKILL.md). Done this session →
   not an issue, just work; console if worth mentioning.
2. **A choice with a road not taken → Decision.** You can name both a path taken
   and a live path rejected. Invoke [`record-decision`](../record-decision/SKILL.md).
   No rejected alternative → not a decision; re-check.
3. **A fact true now, not derivable from code or git, useful later → Memory.**
   Invoke [`record-memory`](../record-memory/SKILL.md). A future session would act
   differently for knowing it.
4. **A step, thought, or status worth keeping across sessions, scoped to a
   subject and task, but not a fact, decision, or action on its own → Journal.**
   Invoke [`record-journal`](../record-journal/SKILL.md). This is the default
   fallback — most process narrative belongs here, not the console.
5. **Nothing above fits, and it isn't even worth a dated log line → Console.**
   Say it; persist nothing.

Order matters: a decision produces a fact, so check Decision (2) before Memory (3),
or rationale gets misfiled as a bare fact. Check Journal (4) only after the first
three — narrative that turns out to be a fact, a decision, or an action belongs
there instead, not filed twice.

## Secondary records, only when each stands alone

One event can warrant more than one. Route each independently; never copy content
between sinks.

- Decision leaving follow-up work → Decision **and** Issue.
- Decision setting a now-true constraint others must follow → Decision **and** Memory.
- Any Decision, Issue, or Memory write that happened mid-task → also Journal,
  narrating what the task was and what got done, and naming the other write
  rather than repeating its content — e.g. a long task that produced three
  decisions gets a journal entry saying the task was worked on and that three
  decisions came out of it, while the decisions keep their own full rationale in
  `decisions.md`.

Split by layer: rationale only in the decision, the resulting fact only in memory,
the action only in the issue, the narrative thread only in the journal.

## Fallbacks

- Unsure which sink → journal if there's any narrative worth keeping, console if
  there truly isn't; surface and ask when genuinely unsure.
- The chosen sink can't write (no backend, missing config) → the sink skill itself
  falls back to console with the drafted record and the reason. Never discard.

## Calibration

- "Lambda runtime is 3.13 across services." → Memory.
- "Use DynamoDB over Redis; Redis added a second datastore to keep in sync." →
  Decision. Add an Issue only if setup work remains.
- "The refresh-token endpoint still needs rate limiting." → Issue.
- "Spent an hour narrowing down why the CDS audit kept flagging false
  positives before finding the real cause." → Journal (subject: the CDS plugin;
  task: audit false-positive triage).
- "This test run took 9 minutes, nothing else notable." → Console.
