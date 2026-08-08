---
name: orchestrator-discipline
description: >-
  Orchestrator role enforcement for multi-agent workflows. Registers blocking
  PreToolUse and PostToolUse guards that stop the orchestrator editing code,
  verifying its own output, dispatching workflows by stale name, absorbing full
  completion payloads, routing domain work to generic agents, or writing into
  the beads channel agents use to pass findings. Use when setting up
  orchestrator guardrails, reviewing delegation discipline, diagnosing context
  window waste, or investigating why an orchestrator bypassed a workflow.
user-invocable: true
---

# Orchestrator Discipline

Enforce the orchestrator role in multi-agent workflows. The orchestrator
sequences phases, dispatches agents, and routes verdicts. It does not produce,
and it does not verify.

The constraint exists because the orchestrator's context window is the only one
in a run that cannot be refreshed — subagents get a fresh window per task. An
orchestrator that reads source, runs diagnostics, and forms its own view of the
code has spent that shared resource and acquired opinions that compete with the
agents chartered to hold them.

## Enforcement, not advice

Every constraint here is a hook that terminates with exit code 2.

This is the design principle, learned the hard way: **a constraint expressed as
prose is a factor the actor weighs against other pressures, and the actor is the
party under constraint.** Advisory text asking the orchestrator to consider
whether it should proceed is consistently answered "yes, this time." Any guard
covering a forbidden action must deny, not warn.

The same reasoning rules out exemptions conditioned on the actor's own account
of its intent. "Proceed if you intend to edit this file" is not a machine
decision — the predicate is unobservable and self-reported. Every exemption a
guard implements is derived from the hook input and the state it names.

## Orchestrator mode — off by default

The guards constrain one role: an orchestrator sequencing an SDLC run. Most
sessions in a repo are not that. Troubleshooting, a one-off script, anything
unrelated to the pipelines — enforcing the orchestrator contract on those blocks
honest work, and an operator who is blocked doing honest work learns to route
around the guards. That is the exact behavior they exist to prevent, so leaving
them permanently armed is self-defeating.

Mode is therefore **off by default** and switched on for a run:

```bash
/agent-teams-workforce:orchestrator-mode on   "starting the MVP-1 run"
/agent-teams-workforce:orchestrator-mode off  "run complete"
/agent-teams-workforce:orchestrator-mode status
```

It is stored at `.claude/agent-teams-workforce.local.md` in the project, and every
transition is appended to `.claude/agent-teams-workforce.mode-log` with a timestamp,
the session that made it, and a reason. The guards re-read that file on every call,
so a change is live at once — it does not wait for a session restart.

**The arm binds the session that made it**, recorded as `armed_by_session`. Other
sessions in the same project run unconstrained, so a run and an unrelated
troubleshooting session can share a repo. An arm made where no session id was
observable — and any mode file predating the binding — falls back to binding the
whole project.

This is not the actor granting itself an exemption. The mode is a human decision
recorded on disk before the work starts, identical for every call in the session,
and never a per-call judgement about intent. While mode is on, the edit guard
refuses to let the orchestrator write the mode file, so a run cannot quietly
disarm itself part-way through — turning it off means running the command, which
leaves a record.

## Where the guards apply

The guards govern sessions that **use** this plugin. They are inert in the
monorepo that **builds** it — authoring a hook means writing `.cjs` and `.json`
files from a top-level session, which is precisely what the edit guard denies,
and a guard that blocks its own maintenance is one nobody can maintain.

The boundary is machine-observable and settles on where the files are, not on
what anyone intends. A session is building this plugin when its project
directory contains `.claude-plugin/marketplace.json` — the registry manifest,
present only in the source monorepo — **and** this plugin's directory sits
inside that project. Installed under `~/.claude/plugins/cache/`, the second
condition fails; in a consuming project, the first does. No flag, assertion, or
declared intent can satisfy either.

This is a scope boundary, not an exemption. Inside the source repo the guards
are not the applicable ruleset; they are never waived for an actor that asked.

Implemented in `hooks/lib/plugin-scope.cjs`.

## Registered guards

All guards exempt subagent sessions, identified by `agent_id` in the hook input.
Subagents implement, verify, and run diagnostics — that is their job.

| Guard | Fires on | Behavior |
| --- | --- | --- |
| Orchestrator Edit Guard | `Edit`, `Write`, `MultiEdit`, `NotebookEdit` | **Blocking.** Denies writes to code, config, and infrastructure files. Prose stays writable. Fails closed on unreadable input. |
| Self-Verification Gate | `Bash` | **Blocking.** Denies network fetches and git inspection of artifacts this session produced, read from the session transcript. |
| Diagnostic Command Gate | `Bash` | **Blocking.** Denies test runners, type checkers, and linters. Delegate the run and take the verdict. |
| Beads Write Guard | `Bash` | **Blocking.** Denies beads mutations. Reads are unaffected. |
| Workflow Dispatch Guard | `Workflow` | **Blocking.** Denies dispatch by bare name; requires `scriptPath`, an inline `script`, or `resumeFromRunId`. |
| Roster Dispatch Guard | `Agent`, `Task` | **Blocking.** Denies generic agent types for domain or reasoning work and names the roster owner. |
| Source File Read Guard | `Read` | Records the read and states its cost. Editing the file is separately blocked, so no exemption is implied or offered. |
| Workflow Payload Cap | `Workflow`, `Task` completion | **Blocking.** Denies completion payloads over 15 lines. |

## Rules

`rules/CLAUDE.md` is loaded into every session and carries the behavioral layer
the guards enforce: read permission and prohibition with a falsifiable test,
delegation constraints with no exemption categories, the investigation
escalation anti-pattern, the tool use denial protocol, built-in tool
enforcement, diagnostic command delegation, and epistemic identity scoping for
the orchestrator role.

## Correct workflow

1. A task arrives. The orchestrator does not read the codebase to understand it.
2. If current state is needed, dispatch a roster agent with the paths in the
   prompt. The agent reads in its own context and returns a verdict.
3. If scope changed, present that to the human for a routing decision.
4. Dispatch implementation to the workflow that owns the phase, by `scriptPath`.
5. Take the verdict. Route it to the gate. Do not re-derive it.

The anti-pattern this replaces: read source to scope the delegation, read more
for context, run a diagnostic to check an assumption, conclude the work is
simple enough to do directly. Each step is defensible alone; the sequence ends
with the orchestrator having done the work unobserved.

## Guard behavior reference

**Orchestrator Edit Guard.** Denies by target extension: `js`, `cjs`, `mjs`,
`jsx`, `ts`, `cts`, `mts`, `tsx`, `py`, `pyi`, `ipynb`, `rb`, `go`, `rs`,
`java`, `kt`, `swift`, `c`, `h`, `cpp`, `hpp`, `cc`, `cs`, `sh`, `bash`, `zsh`,
`fish`, `sql`, `toml`, `yaml`, `yml`, `json`, `jsonc`, `ini`, `cfg`, `conf`,
`env`, `tf`, `tfvars`, `gradle`, `properties`. Prose extensions are absent by
design. Empty or unparseable input is denied — a guard that cannot read its
input has no basis for permitting a write.

**Self-Verification Gate.** Reads `transcript_path` from the hook input and
collects paths from successful `Edit`, `Write`, `MultiEdit`, and `NotebookEdit`
tool_use entries. With no produced artifacts, git access is normal. With
produced artifacts, `curl`/`wget` and any `git diff|log|show|blame|status`
naming a produced path are denied.

**Diagnostic Command Gate.** Matches `pytest`, `mypy`, `pyright`,
`basedpyright`, `pylint`, `ty check`, `ruff check`, `eslint`, `tsc --noEmit`,
`cargo check`, `cargo clippy`, `go vet`, `pre-commit run`, `prek run` at a
command position. Quoted spans are stripped, so searching for one of these
names is not an invocation of it.

**Roster Dispatch Guard.** Treats `Explore`, `Plan`, `general-purpose`,
`claude`, `fork`, and any un-namespaced type as generic. A namespaced roster
agent passes. Generic types are denied when the task text matches a domain
(architecture, requirements, TRD, spec, decomposition, bug, test design,
refactor, security, deployment, integration, documentation) or a reasoning verb.
Pure file-pattern and keyword searches pass.

**Source File Read Guard.** Fires on source, config, and test paths. Prose,
plans, and backlog items do not fire.

**On tool choice.** There is deliberately no guard policing `cat` versus `Read`,
or `grep` versus a search tool. Claude Code removed the standalone `Grep` and
`Glob` tools from native builds in 2.1.117 — search runs through Bash now — so
rules redirecting `grep`, `find`, and `ls` pointed at tools that do not exist,
leaving a blocked command with no way forward except around the guard. What was
left after removing them was `cat`/`head`/`tail` versus `Read`: a style
preference, not one of the forbidden actions this layer exists to enforce.

A guard that blocks honest work teaches the operator to route around the guards.
That is the failure mode this hook set exists to prevent, so the enforcement layer
covers forbidden actions only.

See [Investigation Escalation Anti-Pattern](./references/investigation-escalation.md)
for the full pattern analysis and correct alternatives.
