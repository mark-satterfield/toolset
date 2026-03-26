---
name: skills-hygiene
description: Manage Claude Code skill installation hygiene across global (~/.claude/skills/) and project (.claude/skills/) levels. Use when deduplicating skills at multiple levels, promoting project skills to global, auditing skill health, updating skills from prompts.chat origin, resetting manually modified skills, generating a full skill inventory, making skills self-contained and portable, or generalizing project-specific language so a skill can be shared. Also manages the bespoke skill registry (skill-overrides.local.json) to protect intentionally project-specific skills from being generalized or promoted. Triggers on: skill hygiene, skills hygiene, deduplicate skills, clean up skills, promote skills, backfill skills to global, skill audit, skills audit, skill inventory, skills inventory, skill maintenance, skills maintenance, skill management, skills management, skill conflicts, duplicate skills, orphaned skills, oversized skill, skill health check, skills health check, move skill global, copy skill global, skill origin, reset skill, update skill from source, self-contained skill, contain skill, skill dependencies, internalize skill resources, portable skill, skill portability, skill external dependencies, skill hooks, promote skill global, cleanup rules, generalize skill, project-specific skill, bespoke skill, protect skill, skill-overrides, skill registry, genericize skill.
---

# Skill Hygiene

Manage Claude Code skill installations across global and project levels.

## Skill Levels

| Level | Path |
|-------|------|
| Global | `~/.claude/skills/` |
| Project | `.claude/skills/` (repo root) |

---

## Domain Knowledge & Architecture References

This skill makes decisions based on deep architectural understanding of Claude Skills, plugins, hooks, and related systems. Detailed reference documentation is available in:

**`references/claude-skills-architecture.md`** – Comprehensive guide covering:
- Core meta-tool architecture and progressive disclosure patterns
- Skills vs. Plugins vs. Subagents vs. MCP Servers comparison
- SKILL.md frontmatter specification and discovery mechanisms
- Hook system deep dive with 15 lifecycle events
- MCP integration and tool naming conventions
- Best practices for skill design, portability, and composition
- Open Agent Skills specification compliance
- Troubleshooting and common architectural pitfalls

When making decisions about skill architecture, portability, bespoke status, or self-containment, this skill consults the architecture reference to ensure decisions align with best practices, specification compliance, and platform-agnostic design patterns.

---

## Execution Protocol (ALL operations)

**Every operation follows this exact sequence — no exceptions:**

1. **Analyze** — discover skills, run checks, build a plan
2. **Present** — show findings, state exactly what will change (files created / deleted / modified)
3. **Await approval** — user chooses: **Approve**, **Modify scope**, or **Cancel**
4. **Execute** — only after explicit approval; report results

**Never modify files before step 3 approval.**

---

## skill-rules.json (Non-standard)

`skill-rules.json` is **not a Claude Code standard**. It is part of the antigravity hook framework (keyword-driven proactive skill suggestion via a custom `UserPromptSubmit` hook). Not every installation has it.

**Detection:** At the start of every operation, check whether `skill-rules.json` exists at the relevant level(s). Report its presence; do not assume it.

**Default behavior:** All operations work on SKILL.md directories only. Rules file is ignored unless `--with-rules` is passed.

**Opt-in:** Pass `--with-rules` to include rules file maintenance in any operation:
- `dedupe --with-rules` → also removes project rules entries for deduped skills
- `backfill --with-rules` → also copies/moves rules entries to global
- `audit --with-rules` → also checks orphaned entries, broken entries, trigger conflicts
- `inventory --with-rules` → also reports rules entry mismatches

**Cleanup sub-operation:** `cleanup rules [global|project|both]` — removes rules entries that have no corresponding SKILL.md directory at that level. Useful after bulk skill deletions. Requires `skill-rules.json` to be present; no-ops silently if absent.

---

## Operations

### `dedupe` — Remove duplicates

Find skills installed at both global and project level. Where the project copy adds no meaningful value, remove it and keep only the global copy.

**A project copy is "meaningful" if ANY of these are true:**
- SKILL.md content differs by more than whitespace/formatting
- The skill is listed as `bespoke` in `skill-overrides.local.json` — the project copy is intentional; skip without analysis
- The project copy contains domain-specific hooks or internal scripts that would not work globally
- The skill has project-specific trigger keywords that make it more discoverable for this codebase

**Architectural principle:** Deduplication maintains the Agent Skills specification's single-responsibility and portability principles. Duplicate skills at different levels create maintenance burden and inconsistent behavior across Claude Code instances.

**Protocol:**
1. Load bespoke registry (project and global `skill-overrides.local.json` if present)
2. List all skills present at both levels
3. For each: skip if bespoke; otherwise diff SKILL.md content
4. Classify each non-bespoke skill as: `safe to remove` / `meaningful override` / `global missing` (→ suggest backfill instead)
5. Present table of findings with recommendation per skill
6. On approval: remove project SKILL.md directory for each safe-to-remove skill

**With `--with-rules`:** also compare skill-rules.json entries as an additional meaningful-override criterion, and remove project rules entries for deduped skills.

---

### `promote` — Move project skills to global

Find skills in `.claude/skills/` that are NOT present in `~/.claude/skills/`. **Only self-contained skills are eligible for promotion** — non-self-contained skills are blocked until they pass the `internalize` operation.

**Pre-checks:** Before promoting each skill:
1. **Bespoke check:** If the skill is listed in `skill-overrides.local.json` (project or global level), skip it and report it as excluded — bespoke skills are intentionally project-specific and must NOT be promoted globally.
2. **Self-containment check (BLOCKING):** If the skill depends on files outside its own directory (hooks, scripts, tools), it is **not eligible for promotion**. Refuse the operation and require `internalize` first. A non-self-contained skill will not work correctly when installed globally (violates Agent Skills specification portability requirements).
3. **Agent Skills compliance check:** Verify frontmatter has required `name` and `description` fields. Check description uses specific keywords (discovery requirement per Agent Skills spec).
4. **Platform portability check:** Verify the skill makes no assumptions about file paths, environment variables, or platform-specific tooling that would break in other projects.

**Protocol:**
1. Load bespoke registry; exclude bespoke skills from the candidate list
2. Diff both directories; list remaining project-only skills with name + description + self-containment status
3. For each non-self-contained skill, REFUSE to proceed and display instructions to run `internalize {skill-name}` first. Do NOT offer a workaround or override option.
4. Filter out all non-self-contained and bespoke skills from the promotion candidate list
5. If not specified by user, ask: **Copy** (keep project copy too) or **Move** (remove project copy after installing globally)?
6. Present the filtered list of self-contained skills to be promoted and the copy/move decision
7. On approval:
   - Copy SKILL.md directory to `~/.claude/skills/{skill-name}/`
   - If Move: remove `.claude/skills/{skill-name}/`

**With `--with-rules`:** also copies/moves the skill's rules entry to `~/.claude/skills/skill-rules.json` (creates the file if absent); if Move, also removes the entry from project `skill-rules.json`.

---

### `audit` — Full health check

Comprehensive inspection of the skill landscape at both levels. Uses Agent Skills specification compliance and architectural best practices to evaluate health.

**Checks (standard):**

| Check | What it flags | Architectural Principle |
|-------|---------------|-----------------------|
| Duplicate | Same skill at both levels (candidates for `dedupe`) | Single-responsibility: maintain one authoritative version per skill |
| Project-only | Project skill not in global (candidates for `backfill`) — suppressed for bespoke skills | Skill composition: shareable skills should be globally available |
| Oversized | SKILL.md > 500 lines (violates Anthropic best practice) | Progressive disclosure: split into reference files for token efficiency |
| Missing frontmatter | SKILL.md lacks `name` or `description` field | Agent Skills spec: required metadata for discovery and invocation |
| Non-self-contained | Skill depends on files outside its own directory → not portable | Portability: skills must work in any Claude Code installation |
| Poor discovery description | SKILL.md description too vague or lacks domain keywords | Discovery mechanism: fuzzy matching requires specific keywords |
| Bespoke | Skill is listed in `skill-overrides.local.json` — informational; no action needed | Project-specificity: intentionally not portable |
| Unregistered bespoke candidate | Skill contains apparent project-specific language (product names, internal URLs, team names) but is NOT listed as bespoke — recommend `generalize` or `protect` | Clarity: bespoke status should be explicit in registry |
| Architectural mismatch | Skill uses bundled tools that would be better served by MCP servers | Architecture choice: MCP better for external system integration |

**With `--with-rules`:** also checks orphaned skills (SKILL.md exists, no rules entry), broken entries (rules entry exists, no SKILL.md), and trigger conflicts (3+ shared keywords between skills).

**Output:** Structured report grouped by check type, with per-skill recommendations.

---

### `internalize` — Make a skill self-contained

Identify and internalize all external dependencies so the skill can be safely copied or moved to any installation (global or another project) and work without modification. This operation achieves **Agent Skills specification portability** — a fundamental requirement for platform interoperability and shareable skills.

**A skill is self-contained if ALL of the following are true:**
- Every script/tool it uses lives inside its own directory (under `{skill-dir}/`)
- Every hook that wires it up either: (a) lives inside its directory, or (b) is documented in an `## Installation` section in SKILL.md with exact setup instructions
- No hard-coded absolute or repo-relative paths appear in SKILL.md that would break outside this repo
- All references use skill-internal paths (e.g., `references/patterns.md`, `scripts/validator.py`) not external paths
- No dependencies on project-specific tools, environment variables, or configuration files external to the skill directory

**Architectural benefit:** Self-contained skills follow the Agent Skills specification and can be:
- Promoted to global without requiring external setup
- Shared via plugin marketplaces
- Copied to other projects
- Used across different platforms (Claude Code, claude.ai, GitHub Copilot, Cursor, etc.)

**What this operation finds:**
- **Outbound dependencies**: paths referenced in SKILL.md pointing outside the skill directory (e.g., `tools/gitignore_audit.py`, `../shared/helpers.sh`)
- **Inbound hook wiring**: hook files in `.claude/hooks/` that call scripts from this skill or route traffic through it
- **Symlinks**: any symlinks inside the skill directory that point outside it

**Note:** Does not check the bespoke registry — self-containment is useful even for intentionally project-specific skills.

**Protocol:**
1. Scan SKILL.md for file path references; identify any that resolve outside `{skill-dir}/`
2. Scan `.claude/hooks/` for hooks that reference this skill's name, directory, or any of its scripts
3. Scan skill directory for symlinks pointing outside
4. Present findings table:

   | Resource | Current Location | Action | Destination |
   |----------|-----------------|--------|-------------|
   | `gitignore_audit.py` | `tools/gitignore_audit.py` | Copy | `{skill-dir}/scripts/gitignore_audit.py` |
   | `gitignore-guard.sh` | `.claude/hooks/gitignore-guard.sh` | Copy | `{skill-dir}/hooks/gitignore-guard.sh` |

5. Show proposed `## Installation` section to be added to SKILL.md (documents how to wire hooks on install)
6. On approval:
   - Copy each external file to its destination inside the skill directory
   - Update path references in SKILL.md to use skill-relative paths
   - Add or update `## Installation` section in SKILL.md
   - Do NOT delete originals (they may be shared; user decides separately)

**After `internalize`:** the skill directory is a complete, portable unit. `promote` or manual copy to `~/.claude/skills/` will include everything needed.

---

### `generalize` — Remove project-specific language

Detect and replace project-specific references in a skill's files so it can be shared or backfilled globally without leaking internal naming. This operation prepares a skill for **cross-platform portability** and marketplace distribution (Agent Skills specification compliance).

**Pre-check:** Load `skill-overrides.local.json` at project and global level. If the skill is listed as `bespoke`, refuse the operation with explanation — bespoke skills are intentionally project-specific and should not be generalized.

**Architectural purpose:** Generalization enables:
- Safe global promotion without revealing internal structure
- Marketplace distribution and community sharing
- Use across different organizations and teams
- Platform interoperability (works on Claude Code, claude.ai, GitHub Copilot, Cursor, etc.)

**Scanned files:** SKILL.md, README.md, all other `.md` files under the skill directory, filenames of scripts and assets.

**What counts as project-specific:**
- Product or project names (e.g., "SkillSpoke", "MyApp", "Acme")
- Company or team names
- Internal service names, domain names, or URLs
- Internal path conventions or environment naming specific to this repo
- References to internal tools or systems not present in other projects

**What does NOT count:**
- Generic technology names (AWS, Python, React, DynamoDB)
- Skill-internal relative paths (e.g., `references/patterns.md`)
- Functional logic in scripts

**Protocol:**
1. Check bespoke registry — refuse if protected
2. Scan all in-skill files for project-specific language
3. Present findings table:

   | File | Location | Found | Suggested Replacement |
   |------|----------|-------|----------------------|
   | `SKILL.md` | line 12 | "SkillSpoke opportunities" | "entities in this project" |
   | `README.md` | line 3 | `skillspoke.atlassian.net` | *(remove or replace with placeholder)* |
   | `scripts/sync-jira.py` | filename | "jira" in name | rename to `sync.py`? |

4. User approves, edits, or rejects each replacement individually
5. On approval: apply text replacements; rename files if approved
6. Report results; recommend running `contain` next if not already done

---

### `protect` / `unprotect` — Manage the bespoke registry

Add or remove a skill from `skill-overrides.local.json` to control whether it is eligible for `generalize`, `backfill`, and `dedupe`.

**`protect [skill-name] [--global]`**
- Adds the skill to `skill-overrides.local.json` at project level (or global with `--global`)
- Creates the file with full self-documenting format if it does not exist
- Reports: "skill-name is now protected as bespoke at [level]"

**`unprotect [skill-name] [--global]`**
- Removes the skill from the registry at the specified level
- If the list becomes empty, offers to delete the file entirely
- Reports: "skill-name is no longer protected"

---

### `update` — Refresh from origin

Update a skill from its prompts.chat source.

**Protocol:**
1. Check skill directory for `origin.json` (created at install time — see Origin Tracking below)
2. If origin found: fetch current version from prompts.chat using stored slug/ID
3. Diff current SKILL.md vs. remote
4. Present diff; if no changes, report "already up to date"
5. On approval: overwrite local SKILL.md with remote version

**Note:** Only works for skills installed from prompts.chat with origin metadata. Hand-crafted skills have no remote origin and cannot be updated this way.

---

### `reset` — Restore to original

Restore a manually modified skill to its original installed state.

**Protocol:**
1. Check skill directory for `origin.json`
2. Fetch original from prompts.chat using stored slug/ID
3. Diff current vs. original — show what was locally modified
4. On approval: overwrite with original

**Note:** Requires origin metadata. Cannot reset hand-crafted skills (no origin to restore from).

---

### `inventory` — Full report

Generate a complete skill landscape report. No changes made.

**Output includes:**
- Global skill count + list with SKILL.md line counts and self-containment status (`[contained]` / `[non-self-contained]`)
- Project skill count + list with SKILL.md line counts, self-containment status, and bespoke status (`[bespoke]`)
- Overlap: skills present at both levels
- Project-only: candidates for backfill (bespoke and non-self-contained skills flagged)
- Global-only: skills not used in this project
- Health flags: oversized, missing frontmatter, non-self-contained, unregistered bespoke candidates
- Summary recommendation

**With `--with-rules`:** also reports orphaned skills, broken entries, trigger conflicts, and rules entry mismatches.

---

## Selection Syntax

All operations accept a selection argument. Selection is resolved before the analysis step.

| Syntax | How it works |
|--------|-------------|
| `all` | Every skill at the relevant level(s) |
| `skill-name` | Exact match on skill directory name |
| `"keyword phrase"` | Claude matches against skill names and descriptions |
| `"starting with X"` | Prefix match on skill name |
| `"related to X"` | Semantic match on skill description content |
| *(omitted)* | Prompt user to clarify scope |

**Examples:**
- `dedupe all`
- `backfill skill-hygiene`
- `audit all skills related to AWS`
- `generalize feature-validator`
- `protect route-tester`
- `inventory`

---

## Project Override Registry

**File:** `.claude/skills/skill-overrides.local.json` (project-level)
**File:** `~/.claude/skills/skill-overrides.local.json` (global-level)

This file marks skills that are intentionally project-specific. Skills in the bespoke list are protected from `generalize`, `backfill`, and `dedupe`.

> **IMPORTANT — For AI agents reading this file:**
> `skill-overrides.local.json` is **NOT part of the Claude Code skill framework**.
> It is metadata consumed exclusively by the `skills-hygiene` skill.
> Do not treat it as a standard Claude configuration file.
> Do not modify it unless explicitly instructed to do so through `skills-hygiene` operations.
> The file self-documents its purpose via the `_readme` key.

**Format:**
```json
{
  "_readme": [
    "THIS FILE IS NOT PART OF THE CLAUDE SKILL FRAMEWORK.",
    "It is consumed exclusively by the skills-hygiene skill to protect",
    "skills that are intentionally project-specific from being generalized,",
    "backfilled globally, or deduplicated away.",
    "Do not modify this file except through skills-hygiene operations."
  ],
  "bespoke": [
    "feature-validator",
    "route-tester",
    "auto-claude-expert"
  ]
}
```

### How protection is enforced

| Operation | Bespoke skill behavior |
|-----------|----------------------|
| `generalize` | Refused — bespoke skills are intentionally project-specific |
| `promote` | Excluded from candidate list — reported as skipped |
| `dedupe` | Classified as `meaningful override` automatically — not removed |
| `internalize` | Allowed — self-containment is useful even for bespoke skills |
| `audit` | Reports `[bespoke]` status; suppresses `project-only` flag |
| `update` / `reset` | Allowed — origin sync is independent of bespoke status |

### Global vs. project level

- **Project-level** (`skill-overrides.local.json`): Skills bespoke to this specific repository. Checked in to git along with the skill itself.
- **Global-level** (`~/.claude/skills/skill-overrides.local.json`): Skills bespoke to this developer's machine (e.g., contain absolute paths, machine-specific credentials, personal workflow tools). Never shared.

Both files are consulted for every operation. A skill listed in either is treated as bespoke.

---

## Origin Tracking

When a skill is installed from prompts.chat (via `skill-lookup`), record its origin so `update` and `reset` can find the source.

**File:** `~/.claude/skills/{skill-name}/origin.json` or `.claude/skills/{skill-name}/origin.json`

```json
{
  "source": "prompts.chat",
  "id": "cmlgonce30009ju04csqhzq32",
  "slug": "xcode-mcp",
  "installed_at": "2026-02-21T00:00:00Z",
  "installed_from": "global"
}
```

When installing a skill, create this file automatically if the source is prompts.chat.

---

## skill-rules.json Maintenance

> **Non-standard.** Only applies when `--with-rules` is passed. See [skill-rules.json (Non-standard)](#skill-rulesjson-non-standard) section above.

### Adding an entry (promote `--with-rules`)
If `~/.claude/skills/skill-rules.json` does not exist, create it with:
```json
{
  "version": "1.0",
  "description": "Global skill activation triggers",
  "skills": {}
}
```
Then add the skill's entry, copying from the project `skill-rules.json` if one exists, otherwise constructing a basic entry from the SKILL.md frontmatter description field.

### Removing an entry (dedupe `--with-rules`)
Remove the skill's key from the `skills` object. Validate JSON after edit.

### After any edit
Run: `jq . ~/.claude/skills/skill-rules.json` (or project path) to validate JSON is well-formed.

---

## Trigger Conflict Detection (audit --with-rules detail)

> **Non-standard.** Only checked when `audit --with-rules` is run.

Two skills conflict if they share 3+ identical keywords AND have the same enforcement level. High keyword overlap causes the UserPromptSubmit hook to suggest multiple skills for every prompt, creating noise.

**Remediation options:**
- Narrow one skill's keywords to be more specific
- Merge the skills if they cover overlapping domains
- Raise one skill's priority so the more important one wins

---

## Architectural Decision Guidance

When making decisions about skills, apply these architectural principles from the Agent Skills specification and Claude Skills best practices:

### When to Mark a Skill as Bespoke

A skill should be protected as `bespoke` if:
- **Domain-specific to this project:** Implements internal company workflows, proprietary patterns, or organization-specific standards
- **Non-portable dependencies:** References internal tools, systems, or paths that don't exist elsewhere
- **Team-specific decision:** This skill encodes team policies or coding standards specific to this project
- **Not intended for sharing:** The skill solves a problem unique to this repository

**Do NOT mark as bespoke if:**
- The skill is domain-focused (React, Python, security reviews) regardless of project
- The skill solves a general problem that other projects could use
- Only project-specific documentation differs — generalize first, then promote

### When to Internalize vs. Keep External

- **Internalize if:** The skill can be self-contained without losing functionality (common case)
- **Keep external if:** The skill intentionally depends on project infrastructure that SHOULD vary per installation
  - Example: A skill that runs CI checks may intentionally reference `.claude/hooks/` for project-specific integration

### When to Deduplicate at Different Levels

**Keep project copy if:**
- Enhanced descriptions with project-specific keywords (better discovery for this codebase)
- Contains project-level hooks that modify behavior for this repo
- Different frontmatter that makes the skill more discoverable here
- Intentionally marked as bespoke

**Remove project copy if:**
- Content differs only by whitespace/formatting (pure redundancy)
- Marked for promotion or sharing
- No project-specific value added
- Taking up maintenance burden

### Skills vs. Plugins vs. Hooks Decision Tree

```
Need deterministic automation at fixed events?
  → Use Hooks (PreToolUse, PostToolUse, Stop, etc.)

Need reusable, discoverable multi-turn workflow?
  → Use Skills (auto-discovered, teachable Claude)

Need to package multiple components for sharing?
  → Use Plugins (bundle skills + hooks + MCP)

Need external system integration (GitHub, Jira, DB)?
  → Use MCP Servers (preferably; bundled via plugins)
```

---

## Quick Reference

```
inventory                            → full landscape report, no changes
audit [selection]                    → health check with recommendations
dedupe [selection]                   → remove redundant project-level copies
internalize [selection]              → internalize external deps; make skill self-contained
generalize [selection]               → remove project-specific language; prepare for sharing
promote [selection] [--copy|--move]  → move project skills to global (skips bespoke)
protect [skill-name] [--global]      → mark skill as bespoke; exempt from generalize/promote/dedupe
unprotect [skill-name] [--global]    → remove bespoke protection
update [selection]                   → refresh from prompts.chat origin
reset [selection]                    → restore to original installed state

# --with-rules adds skill-rules.json maintenance to any operation above
cleanup rules [global|project|both]  → remove orphaned rules entries (requires --with-rules flag)
```
