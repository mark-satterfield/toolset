---
name: "self-improving-agent"
description: "Curate persistent project knowledge (beads or auto-memory) into durable rules. Analyze memory for patterns, promote proven learnings to CLAUDE.md and .claude/rules/, extract recurring solutions into reusable skills. Use when: (1) reviewing what Claude has learned about your project, (2) graduating a pattern from notes to enforced rules, (3) turning a debugging solution into a skill, (4) checking memory health and capacity."
---

# Self-Improving Agent

> Memory captures. This plugin curates.

Claude Code's auto-memory (v2.1.32+) records project patterns in `MEMORY.md`. Beads projects use `bd remember` instead. This plugin adds the intelligence layer: it analyzes what Claude has learned, promotes proven patterns into project rules, and extracts recurring solutions into reusable skills.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/self-improving-agent:review` | Analyze persistent memory — find promotion candidates, stale entries, consolidation opportunities |
| `/self-improving-agent:promote` | Graduate a pattern from memory → CLAUDE.md or `.claude/rules/` |
| `/self-improving-agent:extract` | Turn a proven pattern into a standalone skill |
| `/self-improving-agent:status` | Memory health dashboard — counts, capacity, recommendations |
| `/self-improving-agent:remember` | Explicitly save important knowledge to persistent memory |

## Memory Backends

Detect the active backend before reading or writing. See `reference/memory-backends.md`.

| Backend | Detection | Storage |
|---------|-----------|---------|
| **Beads** | `.beads/` directory + `bd` on PATH | `bd remember` / `bd memories` |
| **Auto-memory** | Default when beads absent | `~/.claude/projects/<path>/memory/MEMORY.md` |

```bash
source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory-backend.sh"
BACKEND="$(detect_memory_backend)"   # "beads" or "memory-md"
```

## How It Fits Together

```
┌─────────────────────────────────────────────────────────┐
│                  Claude Code Memory Stack                │
├─────────────┬──────────────────┬────────────────────────┤
│  CLAUDE.md  │ Persistent Memory│   Session Memory       │
│  (you write)│ beads OR MEMORY  │   (Claude writes)      │
│  Rules &    │ .md + topic files│   Conversation logs    │
│  standards  │                  │   + continuity         │
│  Full load  │ bd prime OR      │   Contextual load      │
│             │ first 200 lines  │                        │
├─────────────┴──────────────────┴────────────────────────┤
│         ↑ /self-improving-agent:promote                  │
│         ↑ /self-improving-agent:review                   │
│         Self-Improving Agent (this plugin)               │
│         ↓ /self-improving-agent:extract                  │
│         ↓ /self-improving-agent:remember                 │
├─────────────────────────────────────────────────────────┤
│  .claude/rules/    │    New Skills    │   Error Logs     │
│  (scoped rules)    │    (extracted)   │   (auto-captured)│
└─────────────────────────────────────────────────────────┘
```

## Installation

### Claude Code (Plugin)

```
/plugin marketplace add mark-satterfield/toolset
/plugin install self-improving-agent@mark-satterfield
```

## Memory Architecture

### Where things live

| File | Who writes | Scope | Loaded |
|------|-----------|-------|--------|
| `./CLAUDE.md` | You (+ `/self-improving-agent:promote`) | Project rules | Full file, every session |
| `~/.claude/CLAUDE.md` | You | Global preferences | Full file, every session |
| `.beads/` memories | You + Claude (`bd remember`) | Project learnings | Via `bd prime` |
| `~/.claude/projects/<path>/memory/MEMORY.md` | Claude (auto) | Project learnings | First 200 lines |
| `~/.claude/projects/<path>/memory/*.md` | Claude (overflow) | Topic-specific notes | On demand |
| `.claude/rules/*.md` | You (+ `/self-improving-agent:promote`) | Scoped rules | When matching files open |

### The promotion lifecycle

```
1. Claude discovers pattern → persistent memory (beads or MEMORY.md)
2. Pattern recurs 2-3x → /self-improving-agent:review flags it as promotion candidate
3. You approve → /self-improving-agent:promote graduates it to CLAUDE.md or rules/
4. Pattern becomes an enforced rule, not just a note
5. Source memory entry removed → frees space for new learnings
```

## Core Concepts

### Memory is capture, not curation

Persistent memory is excellent at recording what Claude learns. But it has no judgment about:
- Which learnings are temporary vs. permanent
- Which patterns should become enforced rules
- When capacity is wasted on stale entries
- Which solutions are good enough to become reusable skills

That's what this plugin does.

### Promotion = graduation

When you promote a learning, it moves from Claude's scratchpad to your project's rule system (CLAUDE.md or `.claude/rules/`). The difference matters:

- **Memory**: "I noticed this project uses pnpm" (background context)
- **CLAUDE.md**: "Use pnpm, not npm" (enforced instruction)

Promoted rules have higher priority and load in full (not truncated at 200 lines).

### Rules directory for scoped knowledge

Not everything belongs in CLAUDE.md. Use `.claude/rules/` for patterns that only apply to specific file types:

```yaml
# .claude/rules/api-testing.md
---
paths:
  - "src/api/**/*.test.ts"
  - "tests/api/**/*"
---
- Use supertest for API endpoint testing
- Mock external services with msw
- Always test error responses, not just happy paths
```

This loads only when Claude works with API test files — zero overhead otherwise.

## Agents

### memory-analyst
Analyzes persistent memory (beads or MEMORY.md) to identify:
- Entries that recur across sessions (promotion candidates)
- Stale entries referencing deleted files or old patterns
- Related entries that should be consolidated
- Gaps between what memory knows and what CLAUDE.md enforces

### skill-extractor
Takes a proven pattern and generates a complete skill:
- SKILL.md with proper frontmatter
- Reference documentation
- Examples and edge cases
- Ready for `/plugin install` or marketplace distribution

## Hooks

### error-capture (PostToolUse → Bash)
Monitors command output for errors. When detected, suggests saving the fix via `/self-improving-agent:remember`.

**Token overhead:** Zero on success. ~30 tokens only when an error is detected.

## Platform Support

| Platform | Memory System | Plugin Works? |
|----------|--------------|---------------|
| Claude Code + beads | `bd remember` | ✅ Full support |
| Claude Code | Auto-memory (MEMORY.md) | ✅ Full support |
| OpenClaw | workspace/MEMORY.md | ✅ Adapted (reads workspace memory) |
| Codex CLI | AGENTS.md | ✅ Adapted (reads AGENTS.md patterns) |
| GitHub Copilot | `.github/copilot-instructions.md` | ⚠️ Manual promotion only |

## Related

- [Claude Code Memory Docs](https://code.claude.com/docs/en/memory)
- [reference/memory-backends.md](reference/memory-backends.md) — dual backend detection
- [pskoett/self-improving-agent](https://clawhub.ai/pskoett/self-improving-agent) — inspiration
