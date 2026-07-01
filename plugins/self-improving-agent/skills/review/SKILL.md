---
name: "review"
description: "Analyze persistent memory (beads or auto-memory) for promotion candidates, stale entries, consolidation opportunities, and health metrics."
command: /self-improving-agent:review
---

# /self-improving-agent:review — Analyze Persistent Memory

Performs a comprehensive audit of project learnings and produces actionable recommendations.

Supports beads (`bd memories`) and Claude auto-memory (`MEMORY.md`). See `reference/memory-backends.md`.

## Usage

```
/self-improving-agent:review                    # Full review
/self-improving-agent:review --quick            # Summary only (counts + top 3 candidates)
/self-improving-agent:review --stale            # Focus on stale/outdated entries
/self-improving-agent:review --candidates       # Show only promotion candidates
```

## What It Does

### Step 0: Detect memory backend

```bash
source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory-backend.sh" 2>/dev/null || \
  source "$HOME/.claude/hooks/lib/bd-guard.sh" 2>/dev/null
BACKEND="$(detect_memory_backend 2>/dev/null || { bd_guard 2>/dev/null && echo beads || echo memory-md; })"
```

Also check session context for `bd remember` / "Do NOT use MEMORY.md" instructions.

### Step 1: Locate memory store

**Beads backend:**

```bash
bd memories          # list all persistent memories
bd memories --json   # structured output when available
```

If no beads database found, report that beads may not be initialized. Suggest `bd init` or check `.beads/`.

**Auto-memory backend:**

```bash
MEMORY_DIR="$HOME/.claude/projects/$(pwd | sed 's|/|%2F|g; s|%2F|/|; s|^/||')/memory"
ls -la "$MEMORY_DIR"
```

If memory directory doesn't exist, report that auto-memory may be disabled. Suggest checking with `/memory`.

### Step 2: Read and analyze entries

**Beads:** Read all memories via `bd memories`. For each memory (key + content), analyze:

**Auto-memory:** Read the full `MEMORY.md` file. Count lines and check against the 200-line startup limit. Also read topic files if present.

Analyze each entry for:

1. **Recurrence indicators**
   - Same concept appears multiple times (different wording or keys)
   - References to "again" or "still" or "keeps happening"
   - Similar entries across topic files or memory keys

2. **Staleness indicators**
   - References files that no longer exist (`find` to verify)
   - Mentions outdated tools, versions, or commands
   - Contradicts current CLAUDE.md rules

3. **Consolidation opportunities**
   - Multiple entries about the same topic
   - Entries that could merge into one concise rule

4. **Promotion candidates** — entries that meet ALL criteria:
   - Appeared in 2+ sessions (check wording patterns or duplicate keys)
   - Not project-specific trivia (broadly useful)
   - Actionable (can be written as a concrete rule)
   - Not already in CLAUDE.md or `.claude/rules/`

### Step 3: Read topic files (auto-memory only)

If `MEMORY.md` references or the directory contains additional files (`debugging.md`, `patterns.md`, etc.):
- Read each one
- Cross-reference with MEMORY.md for duplicates
- Check for entries that belong in the main file (high value) vs. topic files (details)

### Step 4: Cross-reference with CLAUDE.md

Read the project's `CLAUDE.md` (if it exists) and compare:
- Are there memory entries that duplicate CLAUDE.md rules? (→ remove from memory)
- Are there memory entries that contradict CLAUDE.md? (→ flag conflict)
- Are there memory patterns not yet in CLAUDE.md that should be? (→ promotion candidate)

Also check `.claude/rules/` directory for existing scoped rules.

### Step 5: Generate report

**Beads backend output:**

```
📊 Memory Review (beads)

Memory Health:
  Memories:         {{count}} entries
  CLAUDE.md:        {{lines}} lines
  Rules:            {{count}} files in .claude/rules/

🎯 Promotion Candidates ({{count}}):
  1. [{{key}}] "{{pattern}}" — seen {{n}}x, applies broadly
     → Suggest: {{target}} (CLAUDE.md / .claude/rules/{{name}}.md)
  2. ...

🗑️ Stale Entries ({{count}}):
  1. [{{key}}] "{{entry}}" — {{reason}}
  2. ...

🔄 Consolidation ({{count}} groups):
  1. [{{key-a}}], [{{key-b}}] both about {{topic}} → merge into 1 memory
  2. ...

⚠️ Conflicts ({{count}}):
  1. Memory "{{entry}}" contradicts CLAUDE.md: {{detail}}

💡 Recommendations:
  - {{actionable suggestion}}
```

**Auto-memory backend output:**

```
📊 Auto-Memory Review

Memory Health:
  MEMORY.md:        {{lines}}/200 lines ({{percent}}%)
  Topic files:      {{count}} ({{names}})
  CLAUDE.md:        {{lines}} lines
  Rules:            {{count}} files in .claude/rules/

🎯 Promotion Candidates ({{count}}):
  1. "{{pattern}}" — seen {{n}}x, applies broadly
     → Suggest: {{target}} (CLAUDE.md / .claude/rules/{{name}}.md)
  2. ...

🗑️ Stale Entries ({{count}}):
  1. Line {{n}}: "{{entry}}" — {{reason}}
  2. ...

🔄 Consolidation ({{count}} groups):
  1. Lines {{a}}, {{b}}, {{c}} all about {{topic}} → merge into 1 entry
  2. ...

⚠️ Conflicts ({{count}}):
  1. MEMORY.md line {{n}} contradicts CLAUDE.md: {{detail}}

💡 Recommendations:
  - {{actionable suggestion}}
```

## When to Use

- After completing a major feature or debugging session
- When `/self-improving-agent:status` shows memory is getting crowded
- Weekly during active development
- Before starting a new project phase
- After onboarding a new team member (review what Claude learned)

## Tips

- Run `/self-improving-agent:review --quick` frequently (low overhead)
- Full review is most valuable when memory is getting crowded
- Act on promotion candidates promptly — they're proven patterns
- Don't hesitate to delete stale entries — memory will re-learn if needed
