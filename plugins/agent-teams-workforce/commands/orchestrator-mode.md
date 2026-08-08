---
description: "Arm or disarm the orchestrator guards for this project, or report the current mode"
argument-hint: "[status|on|off] [reason]"
allowed-tools: [Bash, Read]
---

# Orchestrator mode

Run the mode script with whatever the user passed as `$ARGUMENTS` (default `status`):

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator-mode.cjs" $ARGUMENTS
```

Report its output, then add one line the user actually needs:

- **Switched on** — the arm is bound to this session. Say that other sessions in
  the repo stay unconstrained, so the user can open one for unrelated work.
- **Switched off** — the guards stop applying immediately, not at the next session
  start. If a run is still going, say that it just lost its guards.
- **status** — the mode, which session holds the arm, and whether this session is
  the one bound by it.

The mode file is re-read on every guard call, so a change is live at once wherever
the plugin's hooks were loaded at session start. Hooks that were never loaded (the
plugin was not enabled when the session began) do need a restart — that is the only
thing session start governs here.

## What the mode means

`on` — the session that armed it is orchestrating an SDLC run. The orchestrator
sequences phases, dispatches agents, and routes verdicts. It does not write code,
run the project's diagnostics, verify its own output, dispatch a workflow by bare
name, or write into beads. Those are blocked, not advised.

`off` (the default) — ordinary work. Nothing is constrained. Troubleshooting,
one-off scripts, anything unrelated to the pipelines.

Off is the normal state of a repo. The guards constrain one narrow role, and a
repo where they are always armed is a repo where honest work gets blocked and the
operator learns to route around them — which is the behavior they exist to stop.

## The arm binds one session

Arming records the arming session's id as `armed_by_session`. Only that session is
guarded; every other session in the same project runs unconstrained. A run and a
troubleshooting session can share a repo.

Two consequences worth stating when they come up:

- Running `on` from a second session while a first still holds the arm does not
  take it. Taking it would move the guards off the run they were protecting, so
  the command reports who holds it and changes nothing.
- An arm made where no session id was observable falls back to binding the whole
  project, exactly as it did before binding existed. Mode files written by older
  versions of this command have no `armed_by_session` and behave the same way.

## What this is not

This is not an exemption the agent grants itself. The mode is a human decision,
recorded on disk before the work starts, the same for every call in the session,
and every transition is appended to `.claude/agent-teams-workforce.mode-log` with
a timestamp, the session that made it, and a reason.

Binding the arm to a session does not weaken that. The id compared at guard time is
the one the harness puts in the hook event, not one the actor states about itself,
and an event carrying no id at all is guarded rather than waived.

While the mode is `on`, the edit guard refuses to let the orchestrator write the
mode file, so a run cannot quietly disarm itself part-way through. Turning it off
means running this command, which leaves a record.
