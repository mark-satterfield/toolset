---
name: record-issue
description: >-
  Use when something names an action not yet done — work that must happen later,
  not work finished this session. Fires when you catch yourself about to bury a
  "we still need to…" in a code comment or a deliverable; when the user says "file
  an issue", "open a ticket", "track this", or "add a task"; and when the
  record-observation router sends an issue here. Resolves the tracker (beads,
  GitHub, Linear, Jira) and files it there.
allowed-tools: [Read, Bash]
---

<!-- residue-lint:ignore-file (this rule names trackers to route among them) -->

# Recording an issue

An issue is a not-yet-done action given a home outside the work, so it stops
leaking into the deliverable. First confirm it *is* one: something done this
session is not an issue, just work — mention it on the console if it's worth
saying. An action still to do goes here.

## Resolve the tracker (SHOULD × CAN)

One issue goes to exactly one tracker. Pick it by crossing two axes.

**SHOULD** — read context. Does `AGENTS.md`, `CLAUDE.md`, or a loaded rule name a
tracker for issues — beads (instructions to run `bd`), GitHub, Linear, or Jira?

**CAN** — is that tracker available? Run the probe:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/probe_sinks.py" --text
```

It proves the command-line backends: **beads** (`bd` is `beads` and `.beads/`
exists), **github** (`gh` authenticated, origin is GitHub), **jira** (`jira` CLI
present). **Linear** has no CLI — it reports `ask-agent`. A probe sees only
shells: if a tracker's CLI is absent but its **MCP tools are present in your
context** (Linear, Jira, or GitHub MCP), that counts as CAN.

Then:

- **SHOULD names X, X is CAN** → file to X.
- **SHOULD names X, X is not CAN** → tell the user plainly: `AGENTS.md`/`CLAUDE.md`
  says to use X for issues, but X isn't available here — either that file needs
  cleaning up, or X needs to be installed and configured (the probe's `detail`
  says which part is missing). Then fall back to the console with the drafted
  issue. Never drop it.
- **SHOULD names more than one** → that's an ambiguity; surface it and ask rather
  than guessing.
- **SHOULD silent** → no designated tracker. The action still can't vanish:
  surface the drafted issue on the console.

## Enforce the shape

Whatever the tracker, an issue that can't be acted on later is worthless. Before
filing, confirm it carries:

- **Title** — the action, as an imperative ("Rate-limit the refresh-token
  endpoint"), not a symptom.
- **Context** — why it needs doing, enough that someone who wasn't here can pick
  it up cold.
- **Done** — what "done" looks like: the observable condition that closes it.

Missing any of the three, complete it before filing — don't file a stub.

## File it

Create the issue through the resolved backend:

- **beads** — `bd create` with the title and body (and acceptance criteria if the
  project's beads schema uses them).
- **GitHub** — `gh issue create` (CLI) or the GitHub MCP tool.
- **Jira** — `jira issue create` (CLI) or the Jira MCP tool.
- **Linear** — the Linear MCP tool.

Done when the issue exists in the resolved tracker, or — on the console-fallback
paths above — when the user has the full drafted issue and the reason it wasn't
filed. Stay quiet on success.
