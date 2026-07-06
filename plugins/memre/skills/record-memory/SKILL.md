---
name: record-memory
description: >-
  Use when a fact worth keeping is true now, not derivable from code or git, and a
  future session would act differently for knowing it — record it as durable
  memory. Fires when you learn a standing preference, constraint, or project fact;
  when the user says "remember this", "note that going forward", or "save this to
  memory"; and when the record-observation router sends a memory here. Not for a
  decision's rationale (that is record-decision) or an action still to do
  (record-issue).
allowed-tools: [Read, Bash]
---

<!-- residue-lint:ignore-file (this rule quotes the memory vocabulary to shape it) -->

# Recording a memory

A memory is one fact, written for a future session that never saw this
conversation. You draft the content and pick its type; the script owns the
mechanics — the filename, the frontmatter, and the `MEMORY.md` index line.

## First, is it even a memory?

Don't save what the repo already records — code structure, past fixes, git
history, or what's already in `CLAUDE.md`. Don't save what only matters to this
conversation. If a fact fails both tests, it isn't a memory; route it elsewhere or
let it go.

## Resolve the store

Two homes; pick by crossing what context says against what is available.

1. **Beads for memory** — only when context (`AGENTS.md` / `CLAUDE.md` / a rule)
   says to keep memory in beads **and** beads is usable here. Confirm the latter:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/probe_sinks.py" --text
   ```

   `beads: ready` → write the memory through `bd`. A bare "use beads" for *issues*
   does not send memory to beads — the instruction must name memory.
2. **Auto-memory** (the default) — write a markdown file to the project's memory
   directory under `~/.claude/projects/`. That directory is already in your context
   (the `MEMORY.md` index and its path); use that exact path — never reconstruct it.
3. **Neither** — if context names beads-for-memory but beads isn't ready, tell the
   user plainly (the probe's `detail` says what's missing), then fall back to
   auto-memory if it's available, else surface the drafted memory to the console.
   Never drop it.

## Enforce the shape (auto-memory)

Every memory carries frontmatter with a `type` — one of **user** (who the user
is), **feedback** (how you should work, with the why), **project** (ongoing work
or constraints not derivable from code), **reference** (a pointer to an external
resource). A **feedback** or **project** memory must also state **Why** it exists
and **How to apply** it — a bare instruction with no why is a memory that a future
session can't weigh. The script rejects the write if either is missing.

Before writing, check for an existing memory that already covers the fact and
**update that one** rather than adding a near-duplicate. Link related memories in
the body with `[[their-name]]`.

## Write it

Assemble the JSON and pipe it to the script, passing the memory directory from
your context:

```bash
echo '<json>' | python3 "${CLAUDE_PLUGIN_ROOT}/skills/record-memory/scripts/record_memory.py" --dir "<memory-dir>"
```

JSON fields: `name` (kebab slug), `description`, `type`, `title`, `hook` (the
index one-liner), `body`, plus `why` and `how_to_apply` for feedback/project, and
optional `links`. The script writes `<type>_<name>.md`, adds the `MEMORY.md`
pointer, and refuses to clobber an existing memory unless you pass `--update`.

Exit 0 is success: **say nothing, end the turn.** On a non-zero exit, surface the
drafted memory and the script's stderr line so it isn't lost, and stop.
