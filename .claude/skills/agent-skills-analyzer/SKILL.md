---
name: agent-skills-analyzer
description: Designs and audits Claude Code plugins by separating role (subagent) from playbook (skill), applying fork heuristics for skills, and detecting structural anti-patterns. Triggers when scaffolding a new plugin, refactoring an existing .claude/agents or .claude/skills layout, deciding what belongs in a subagent versus a skill, choosing whether a skill should fork, or running design review on a plugin before publication.
---

# Agent and Skills Analyzer

## Core principle

A subagent declares a *role*: identity, tool allowlist, model choice, output contract. A skill declares a *playbook*: methodology, references, scripts, or domain knowledge. The subagent file should reference skills, not restate them. A skill should be invokable by multiple callers — the main session, multiple subagents, other skills. If the same content appears in a subagent.md and a SKILL.md, the playbook wins and the subagent references it.

## Fork decision

Add `context: fork` to a SKILL.md when the skill is macro-shaped — defined input, fixed procedure, deliverable output, no conversational iteration with the parent — or when intermediate work would clutter the parent (large file reads, many tool calls, exploratory passes).

Do not fork when the skill is a thin inline rule set (spawn cost dominates), when the parent needs to iterate conversationally on the output, or when the skill produces context the parent needs downstream.

## Subagent constraints

A subagent file earns its existence by declaring at least one of: a restricted `tools` allowlist, a non-default `model`, a structured output contract, or a persona that materially shapes responses. Without any of these, a forking skill is the right choice instead.

The subagent body should be lean: identity statement, constraints, output contract, references to the skills it invokes. Subagent files exceeding roughly 50 lines of prose usually indicate embedded playbook content; extract.

## Anti-patterns

`role-justification-missing`: subagent.md with no `tools` allowlist, no `model` override, and no output contract. Convert to a forking skill.

`embedded-playbook`: subagent.md exceeds 50 lines of prose. Extract methodology to a skill, leave only role declaration.

`hollow-skill`: SKILL.md body is essentially "delegate to subagent X." The skill adds nothing. Remove or merge.

`duplicated-playbook`: paired xxx.md subagent and xxx/SKILL.md contain overlapping methodology. The skill owns the playbook; the subagent references it.

`undocumented-disabled-invocation`: `disable-model-invocation: true` set without a documented `/command` for the user. Either document or remove the flag.

`unnecessary-fork`: `context: fork` declared on a skill whose body is short, inline, or interactive. Remove the fork directive.

`missing-fork`: macro-shaped skill (defined input, fixed procedure, file output) running inline and polluting parent context. Add `context: fork`.

`unstructured-output`: subagent.md has no output contract. Parent receives prose, cannot reliably parse. Add format spec.

## Audit workflow

For an existing plugin, run `python scripts/audit_plugin.py <plugin-root>`. The script walks `.claude/agents/*.md` and `.claude/skills/*/SKILL.md` and emits JSON findings keyed by anti-pattern code. Pretty-print with `--pretty`. Exit codes: 0 (clean or info only), 1 (warnings), 2 (errors), 3 (scan failure).

Review findings, group by severity, then either patch in place (mechanical fixes), refactor (architectural fixes), or hand the JSON to a refactor subagent for batch work.

## Design workflow

For a new plugin, list responsibilities first. For each: decide role vs playbook. For each role: name its tools, model, output contract, and the skills it will reference. For each skill: decide whether to fork. Scaffold the files lean. Run the audit script before publishing.

## Output

When invoked on an audit task, produce a verdict per file (keep, patch, refactor, delete), a brief rationale, and concrete next-step instructions. Do not rewrite files unsolicited — surface findings and let the caller decide.

When invoked on a design task, produce the file-by-file scaffold plan before writing any files.

## References

`references/checklist.md` — full audit dimension list the script encodes; read when extending checks or interpreting findings.

`scripts/audit_plugin.py` — Python stdlib-only audit script; run against a plugin root.o
