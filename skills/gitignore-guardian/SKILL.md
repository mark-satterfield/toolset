---
name: gitignore-guardian
description: >
  Expert gitignore management, auditing, and protection. Prevents bad changes
  via PreToolUse hook, finds tracked-but-ignored files, optimizes glob patterns,
  cleans up git history, and manages worktree propagation issues. Supports
  @protect annotations for intentionally-tracked-then-ignored files.
  Activates on: gitignore, git ignore, untrack, tracked files, cleanup git,
  git clean, git history, purge file, sensitive file, secret leak,
  tracked but ignored, dead rules, worktree gitignore.
---

# Gitignore Guardian

## Purpose

Single source of truth for .gitignore management in this project. Guards against
accidental changes, finds hygiene issues, optimizes patterns, and cleans up
tracked files that should not be in the repository.

**This skill is both a knowledge base and a guardrail.** A PreToolUse hook
(`hooks/gitignore-guard.sh`) blocks dangerous .gitignore modifications
before they happen.
**All examples in this skill are illustrative, not exhaustive.** They must not
be treated as constraints on required behavior.

## When to Activate

- Any Edit/Write targeting `.gitignore`
- User asks about tracked files, untracking, or git cleanup
- Auditing repository hygiene
- Investigating files that "keep coming back" after deletion
- Worktree-related gitignore propagation issues
- Sensitive file leak detection or remediation
- Pattern optimization or deduplication

---

## The @protect Mechanism

### Problem

Sometimes we intentionally track a file and then add it to .gitignore so the
tracked version serves as a template/default but local modifications are ignored.
Example: a `.env` file with safe defaults checked in, then gitignored so local
overrides aren't committed.

Standard cleanup would flag this as "tracked file matching .gitignore" and
try to untrack it. We need a way to say "this is intentional, leave it alone."

### Solution: `# @protect:` Comments

Add a `# @protect:` comment on the line **immediately before** the pattern:

```gitignore
# @protect: Default environment template with safe placeholder values
.env
```

Rules:
- The `# @protect:` comment MUST be on the line directly above the pattern
- No blank lines between the comment and the pattern
- The reason after `# @protect:` is required (explains WHY it's protected)
- Multiple patterns can each have their own `# @protect:` line
- The audit tool (`scripts/gitignore_audit.py`) skips protected entries during cleanup
- The hook script recognizes and preserves protected entries

### Block Protection

For protecting multiple related patterns:

```gitignore
# @protect-start: Config templates with safe defaults
.env
config/defaults.json
docker-compose.override.yml
# @protect-end
```

### Adding Protection

```bash
python3 scripts/gitignore_audit.py protect '.env' 'Default environment template with safe placeholder values'
```

---

## Audit Tool

**Location:** `scripts/gitignore_audit.py`

### Commands

| Command | Purpose |
|---------|---------|
| `audit` | Full health check (runs all checks, summarizes findings) |
| `tracked-ignored` | Find files tracked by git that also match .gitignore patterns |
| `dead-rules` | Find .gitignore patterns that match no files in the repo |
| `missing-rules` | Suggest patterns that should be in .gitignore for this tech stack |
| `optimize` | Suggest pattern consolidation and improvements |
| `untrack FILE` | `git rm --cached` a file (keeps local copy, removes from git) |
| `purge FILE` | Guide through purging a file from ALL git history |
| `protect PATTERN REASON` | Add `# @protect:` annotation to a .gitignore entry |

### Usage

```bash
# Full audit
python3 scripts/gitignore_audit.py audit

# Find tracked files that should be ignored
python3 scripts/gitignore_audit.py tracked-ignored

# Find .gitignore rules that match nothing
python3 scripts/gitignore_audit.py dead-rules

# Check for missing patterns
python3 scripts/gitignore_audit.py missing-rules

# Suggest pattern optimizations
python3 scripts/gitignore_audit.py optimize

# Untrack a file (keeps local, removes from git index)
python3 scripts/gitignore_audit.py untrack path/to/file

# Purge a file from history (interactive, requires confirmation)
python3 scripts/gitignore_audit.py purge path/to/secret.env

# Add @protect annotation
python3 scripts/gitignore_audit.py protect '.env' 'Default env template'
```

---

## Hook Integration

### PreToolUse Hook: `.claude/hooks/gitignore-edit-guard.sh`

Fires on Edit/Write/MultiEdit targeting any `.gitignore` file. Validates:

1. **Sensitive pattern removal** -- Blocks removing patterns that protect secrets
   (`.env`, `*.pem`, `*.key`, `credentials*`, `*.p12`, `*.pfx`, `*secret*`)
2. **Overly broad additions** -- Warns on patterns like `*`, `**`, `*.py`, `*.ts`
   that would ignore source files
3. **@protect violation** -- Blocks removing or modifying `# @protect:` lines
   and their associated patterns
4. **Redundant patterns** -- Warns when adding a pattern already covered by
   an existing broader pattern

### What the Hook Does NOT Block

- Adding new specific patterns (normal workflow)
- Reorganizing or commenting patterns
- Adding negation patterns (`!path`)
- Modifying non-protected entries

---

## Gitignore Best Practices

### Pattern Syntax Reference

| Pattern | Matches |
|---------|---------|
| `file.txt` | `file.txt` at any depth |
| `/file.txt` | `file.txt` only in repo root |
| `dir/` | Directory named `dir` at any depth |
| `/dir/` | Directory named `dir` only in repo root |
| `*.log` | All `.log` files at any depth |
| `dir/**/*.log` | All `.log` files under `dir/` |
| `!important.log` | Re-include `important.log` (negation) |
| `#comment` | Comment line (NOT inline -- no inline comments in .gitignore) |

### Key Rules

1. **No inline comments.** `.env # protect` does NOT work. The `# protect`
   becomes part of the pattern. Use a preceding comment line instead.
2. **Trailing slashes matter.** `dir` matches files AND directories named `dir`.
   `dir/` matches ONLY directories.
3. **Leading slashes anchor to repo root.** `/build/` only matches `./build/`,
   not `src/build/`.
4. **Negation order matters.** Negation (`!`) only works if a previous pattern
   excluded the file. Last matching pattern wins.
5. **Patterns are relative to .gitignore location.** A `.gitignore` in `src/`
   has patterns relative to `src/`.
6. **Already-tracked files are NOT affected by .gitignore.** You must
   `git rm --cached` first.

### Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|---------------|-----|
| Adding pattern but file is already tracked | .gitignore only affects untracked files | `git rm --cached <file>` first |
| Using `dir` instead of `dir/` | May match files named `dir` too | Use `dir/` for directories |
| Broad `*.html` without negations | Ignores legitimate HTML source files | Add `!apps/*/index.html` etc. |
| Inline comment `.env # reason` | Git treats `# reason` as part of pattern | Use preceding comment line |
| Missing negation after broad pattern | `lib/` then `!apps/web/src/lib/` order matters | Put negations after the broad pattern |

### Sensitive Files That MUST Be Ignored

These patterns should always be present (the `missing-rules` command checks for them):

```gitignore
# Secrets and credentials
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
*.keystore
*secret*
credentials.json
service-account*.json
```

---

## Worktree Considerations

Git worktrees share the same `.gitignore` (it's a tracked file in the repo).
This creates propagation risks:

### Problem: Auto-Claude Worktree Pollution

1. Auto-Claude creates a worktree for spec `ss-123`
2. Agent accidentally adds a file that should be ignored
3. Agent commits and pushes the branch
4. Branch merges to main
5. The unwanted file is now in main AND propagates to all worktrees

### Prevention

- The PreToolUse hook fires in worktrees too (hooks are per-repo)
- The audit tool checks across all worktrees: `git worktree list`
- Run `python3 scripts/gitignore_audit.py tracked-ignored` in worktrees
  before merging

### Remediation

If a junk file propagates through a merge:

1. Run `python3 scripts/gitignore_audit.py tracked-ignored` to find it
2. If it contains secrets: `python3 scripts/gitignore_audit.py purge <file>`
3. If it's just junk: `python3 scripts/gitignore_audit.py untrack <file>`
4. Ensure the pattern exists in `.gitignore`
5. Commit the untrack + .gitignore change together

---

## History Purge (Dangerous Operations)

When a sensitive file has been in commit history, untracking is insufficient.
The file remains accessible via `git log` / `git show`. Full purge is required.

### Severity Assessment

| Scenario | Action |
|----------|--------|
| Non-sensitive junk file tracked | `untrack` (git rm --cached) |
| Sensitive file, just committed (not pushed) | `git reset HEAD~1` + untrack |
| Sensitive file, pushed but recent | `git-filter-repo` or BFG + force-push |
| Sensitive file, months of history | BFG Repo Cleaner + force-push + rotate credentials |

### Tools (in order of preference)

1. **git-filter-repo** (recommended) -- Modern, fast, safe
   ```bash
   git filter-repo --invert-paths --path <file>
   ```

2. **BFG Repo Cleaner** -- Simpler for secret removal
   ```bash
   bfg --delete-files <filename> .git
   git reflog expire --expire=now --all && git gc --prune=now --aggressive
   ```

3. **git filter-branch** (legacy, avoid) -- Slow, error-prone

### After Purge

1. Force-push ALL branches: `git push --force --all`
2. Force-push tags: `git push --force --tags`
3. **Rotate ALL credentials** that were in the purged file
4. Notify collaborators to re-clone (their local copies still have the history)
5. GitHub: Contact support to clear server-side caches if the repo is public

**ALWAYS confirm with the user before any history-rewriting operation.**

---

## Decision Trees

### "Should I add this to .gitignore?"

```
Is it generated/derived from source? (build output, compiled, cached)
  YES -> Ignore it
  NO  -> Is it environment-specific? (OS files, IDE config, local settings)
    YES -> Ignore it
    NO  -> Does it contain secrets or credentials?
      YES -> Ignore it AND check if it's already tracked
      NO  -> Is it a dependency directory? (node_modules, .venv, vendor)
        YES -> Ignore it
        NO  -> Should probably be tracked
```

### "This tracked file matches .gitignore"

```
Is it @protected?
  YES -> Leave it alone (intentional)
  NO  -> Does it contain secrets?
    YES -> Does it appear in commit history?
      YES -> PURGE from history + rotate credentials
      NO  -> Untrack (git rm --cached)
    NO  -> Is anyone depending on it being tracked?
      YES -> Add @protect annotation
      NO  -> Untrack (git rm --cached)
```

### "This .gitignore pattern matches nothing"

```
Was it ever needed? (check git log for the pattern)
  NO  -> Probably cargo-culted from a template. Remove it.
  YES -> Did the files move or get renamed?
    YES -> Update the pattern to match the new location
    NO  -> The files were deleted. Keep the pattern if they might return,
           remove if the feature/tool is permanently gone.
```

---

## Current .gitignore Issues (SkillSpoke-Specific)

Known issues to watch for in this project:

1. **`.env` pattern ambiguity** -- Line 47 has `.env` which matches both the
   file `.env` AND any path containing `.env`. This also catches `.env/`
   (directory) on line 48. Consider using `/.env` for root-only.
2. **`lib/` is too broad** -- Line 23 ignores all `lib/` directories. Requires
   5 negation patterns (lines 39-44) to re-include TypeScript lib dirs.
   Consider anchoring: `/lib/` or using more specific paths.
3. **Django/Flask section** (lines 89-96) -- These frameworks are banned in this
   project. The patterns are harmless but add noise. Candidate for removal.
4. **Scrapy/Rope/Spyder sections** (lines 98-106) -- Not used. Dead weight.
5. **Duplicate section headers** -- Lines 374 and 384 both say
   "# Auto Claude generated files"
6. **`*.html` is very broad** (line 189) -- Requires negation patterns. Consider
   whether this is truly needed or if specific paths would be better.
7. **`.claude*` pattern** (line 260) -- Broad glob requires 8 negation lines
   (261-273) to re-include wanted `.claude/` subdirectories. Fragile.

---

## The @index Mechanism

### Problem

Sometimes a gitignored pattern should still be visible and searchable in your
IDE -- generated docs you reference, local config files you edit, debug build
artifacts. Without `@index:`, syncing .gitignore to IDE exclusions would hide
these files.

### Solution: `# @index:` Comments

Add `# @index:` on the line immediately before the pattern in `.gitignore`:

```gitignore
# @index: Need to search generated API docs during development
docs/_build/
```

### Block Annotation

```gitignore
# @index-start: Local config files we reference but don't commit
.env
local_settings.py
# @index-end
```

### Adding @index

```bash
python3 scripts/gitignore_audit.py index '.env' 'Local env file we reference during development'
```

The `@index:` annotation tells `ide_exclusion_audit.py` to skip these patterns
when syncing .gitignore exclusions to IDE configs.

---

## Sister Skill: IDE Exclusion Manager

The **ide-exclusion-manager** skill (`.claude/skills/ide-exclusion-manager/`)
manages the IDE side of file exclusions. Where gitignore-guardian manages what
git ignores, ide-exclusion-manager manages what your IDE ignores.

**Key integration points:**
- Both skills recognize `@index:` / `@index-start:` / `@index-end` annotations
- The gitignore edit guard hook suggests running `ide_exclusion_audit.py sync`
  when .gitignore patterns change
- `parse_gitignore()` in `scripts/gitignore_audit.py` is shared -- both tools
  import from it

**IDE audit tool:** `tools/ide_exclusion_audit.py`

```bash
python3 tools/ide_exclusion_audit.py detect   # Which IDEs are configured
python3 tools/ide_exclusion_audit.py audit    # Full sync check
python3 tools/ide_exclusion_audit.py drift    # Show drift
python3 tools/ide_exclusion_audit.py sync     # Auto-sync to IDEs
```

---

## Installation & Hooks

This skill includes **PreToolUse hooks** that protect `.gitignore` from dangerous modifications. The hooks are included in the skill directory but require manual installation in projects that want this protection.

### What the Hooks Do

| Hook | Location | Purpose |
|------|----------|---------|
| `gitignore-guard.sh` | `hooks/gitignore-guard.sh` | Blocks dangerous `.gitignore` modifications before they happen. Runs on any Edit/Write to `.gitignore`. |
| `gitignore-edit-guard.sh` | `hooks/gitignore-edit-guard.sh` | Extended validation; checks for tracked-but-ignored files and suggests remediation. |

**How they work:** When you try to edit `.gitignore`, the hook validates the change and blocks it if it would:
- Unignore a file containing secrets
- Create overly broad patterns (e.g., `*.py`)
- Break tracked-but-ignored file protections (`@protect:` annotations)

### Installation

Hooks are registered as `PreToolUse` entries in the project's `.claude/settings.local.json`. This keeps hook configuration local to each developer and out of committed project settings.

**To install, add the following to `.claude/settings.local.json`:**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "<SKILL_PATH>/hooks/gitignore-guard.sh"
        }]
      },
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [{
          "type": "command",
          "command": "<SKILL_PATH>/hooks/gitignore-edit-guard.sh"
        }]
      }
    ]
  }
}
```

Replace `<SKILL_PATH>` with the **absolute path** to the skill directory:

| Install location | Example `<SKILL_PATH>` |
| --- | --- |
| Project-local skill | `/absolute/path/to/project/.claude/skills/gitignore-guardian` |
| Global skill | `~/.claude/skills/gitignore-guardian` |
| Source repo (this repo) | `/Users/<you>/git-repos/toolset/skills/gitignore-guardian` |

**Step-by-step (for Claude to follow when asked to install):**

1. Determine the absolute path to this skill's `hooks/` directory
2. If `.claude/settings.local.json` does not exist, create it with the JSON above
3. If it already exists, merge the two `PreToolUse` entries into the existing `hooks.PreToolUse` array (create the array if only other hook types exist)
4. Ensure the hook scripts are executable: `chmod +x <SKILL_PATH>/hooks/*.sh`
5. Verify by reading back `.claude/settings.local.json`

### Removal (Disable Protection)

Remove the two `PreToolUse` entries (matchers `Bash` and `Edit|Write|MultiEdit`) from `.claude/settings.local.json`. If the `PreToolUse` array becomes empty, remove the entire key.

**Note:** Removing hooks disables automatic validation but does not affect:
- The `scripts/gitignore_audit.py` audit tool (still available via manual invocation)
- The skill's knowledge base and documentation
- The `@protect:` and `@index:` annotation system

### When This Skill is Global

When gitignore-guardian is installed globally (`~/.claude/skills/`):
- The skill activates for reference and commands across all projects
- Audit tools can be invoked manually in any project
- Hooks are **NOT auto-wired** — each project needs its own `.claude/settings.local.json` entries pointing to the global hook scripts (e.g., `~/.claude/skills/gitignore-guardian/hooks/gitignore-guard.sh`)

---

## Integration with Other Skills

- **ide-exclusion-manager**: Sister skill for IDE indexing/search exclusion sync
- **auto-claude-expert**: Worktree cleanup, merge hygiene
- **commit-helper**: Include .gitignore changes in commits properly
- **devex-tooling**: Audit tool follows "all code is application code" standards
- **hardstop**: Coordinates on dangerous git operations (force-push, filter-repo)
