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

- **Switched on** — the guards are armed but **hooks load at session start**, so
  they take effect on the next session, not this one. Say so plainly.
- **Switched off** — same caveat in reverse: anything currently blocking will keep
  blocking until the session restarts.
- **status** — just the mode and the project it applies to.

## What the mode means

`on` — this session is orchestrating an SDLC run. The orchestrator sequences
phases, dispatches agents, and routes verdicts. It does not write code, run the
project's diagnostics, verify its own output, dispatch a workflow by bare name, or
write into beads. Those are blocked, not advised.

`off` (the default) — ordinary work. Nothing is constrained. Troubleshooting,
one-off scripts, anything unrelated to the pipelines.

Off is the normal state of a repo. The guards constrain one narrow role, and a
repo where they are always armed is a repo where honest work gets blocked and the
operator learns to route around them — which is the behavior they exist to stop.

## What this is not

This is not an exemption the agent grants itself. The mode is a human decision,
recorded on disk before the work starts, the same for every call in the session,
and every transition is appended to `.claude/agent-teams-workforce.mode-log` with
a timestamp and reason.

While the mode is `on`, the edit guard refuses to let the orchestrator write the
mode file, so a run cannot quietly disarm itself part-way through. Turning it off
means running this command, which leaves a record.
