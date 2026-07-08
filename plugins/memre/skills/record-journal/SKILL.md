---
name: record-journal
description: >-
  Use when a step, thought, status update, or session narrative is worth keeping
  across sessions but isn't a settled decision, a durable fact, or a not-yet-done
  action — a running lab-notebook entry filed under a subject and task. Fires when
  the record-observation router sends process narrative here (its default
  fallback), when the user asks to "leave a note," "log this," or "add to the
  journal," or when Claude wants to leave itself a working note mid-task. Also
  fires alongside record-decision, record-issue, or record-memory when a task
  produced one of those, to narrate what the task was and that the write
  happened. Not for the settled record itself — a decision's rationale stays in
  record-decision, a fact in record-memory, an action in record-issue.
allowed-tools: [Read, Bash]
---

<!-- residue-lint:ignore-file (this rule quotes the residue vocabulary to route it here instead) -->

# Recording a journal entry

## Journal

**As a noun**
- **A personal diary or log:** a daily written record of activities, thoughts,
  feelings, experiences, or observations.
- **Computing:** a chronological log of database changes used for system
  recovery.

**As a verb**
- **To write down daily activities, thoughts, feelings, experiences, or
  observations:** the action of writing one's activities, thoughts, feelings,
  experiences, or observations.
- **To record financial or technical information** (also *journalize*): the act
  of logging financial transactions.

A journal entry is a dated snapshot — a step taken, a thought, a status — filed
under the subject and task it belongs to, so a later session (yours or the
user's) can scroll one subject's file and see what happened, in order, without
digging through chat history that's already gone.

## First, is it even a journal entry?

If it's a settled choice with a real rejected alternative, it's a decision —
route it to `record-decision` instead. If it's a standing fact a future session
would act differently for knowing, it's a memory — route it to `record-memory`.
If it names something not yet done, it's an issue — route it to `record-issue`.
A journal entry is what's left: process, narrative, a note to your future self.

## Resolve the subject and task

**Subject** — the broad area this belongs to (a project, an initiative, a
recurring theme) — becomes the file: `journal/<slug-of-subject>.md`. Reuse an
existing subject exactly (check `journal/` for a close match) rather than
splintering one initiative across two similarly-named files.

**Task** — the specific unit of work within that subject — becomes the entry's
heading, so scanning a subject's file, table-of-contents style, shows every task
worked on, in order.

## Write it

Assemble the JSON and pipe it to the script:

```bash
echo '<json>' | python3 "${CLAUDE_PLUGIN_ROOT}/skills/record-journal/scripts/record_journal.py"
```

JSON fields: `subject`, `task`, `entry` (required — free-form prose or bullets,
written for a reader who wasn't there), and optional `made_by`. The script
resolves the project root, slugifies the subject into its file under `journal/`,
stamps today's date, and inserts the entry newest-on-top. Pass `--dir <path>` to
override the journal directory (e.g. when the subject belongs to a different
project than the one you're sitting in), or `--file <path>` to override the
target file outright.

Exit 0 is success: **say nothing, end the turn.** On a non-zero exit, surface the
drafted entry and the script's stderr line so it isn't lost, and stop.

## Alongside another sink, not instead of it

A journal entry can run *in addition to* a Decision, Issue, or Memory write from
the same task — narrating the task, not repeating the sink's content. If a long
task produced three decisions, the journal entry says the task was worked on and
that three decisions came out of it (naming them briefly), while the decisions
themselves keep their full rationale in `decisions.md`. Split by layer: the
settled record lives in its own sink; the journal carries the thread connecting
it back to the task.

## Unlike a decision or a memory

A journal entry carries no enforced shape beyond subject/task/entry — no
required rationale, no rejected alternatives, no supersession. It is a log, not
an analysis: write what happened and what you noticed, and let the next entry
correct or extend it rather than editing this one.
