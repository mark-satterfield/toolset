# Self-Improving Agent

> Memory captures. This plugin curates.

A Claude Code plugin that turns persistent project knowledge into a structured self-improvement loop. Analyze what Claude has learned, promote proven patterns to enforced rules, and extract recurring solutions into reusable skills.

## Why

Claude Code's auto-memory (v2.1.32+) records project patterns in `MEMORY.md`. Beads projects use `bd remember` instead. Neither system has judgment about what to keep, what to promote, or when entries go stale. This plugin adds the intelligence layer.

**The difference:**
- **Memory**: "I noticed this project uses pnpm" (background note)
- **CLAUDE.md**: "Use pnpm, not npm" (enforced instruction, loaded in full)

Promoting a pattern from memory to rules fundamentally changes how Claude treats it.

## Commands

| Command | What it does |
|---------|-------------|
| `/self-improving-agent:review` | Analyze persistent memory — find promotion candidates, stale entries, health metrics |
| `/self-improving-agent:promote` | Graduate a pattern from memory → CLAUDE.md or `.claude/rules/` |
| `/self-improving-agent:extract` | Turn a recurring pattern into a standalone reusable skill |
| `/self-improving-agent:status` | Memory health dashboard — counts, capacity, recommendations |
| `/self-improving-agent:remember` | Explicitly save important knowledge to persistent memory |

## Memory Backends

| Backend | Detection | Write | Read |
|---------|-----------|-------|------|
| **Beads** | `.beads/` + `bd` on PATH | `bd remember` | `bd memories` |
| **Auto-memory** | Default | Append to `MEMORY.md` | Read memory directory |

See [reference/memory-backends.md](reference/memory-backends.md) for detection logic.

## Install

### Claude Code
```
/plugin marketplace add mark-satterfield/toolset
/plugin install self-improving-agent@mark-satterfield
```

## How It Works

```
Claude discovers pattern → persistent memory (beads or MEMORY.md)
         ↓
Pattern recurs 2-3x → /self-improving-agent:review flags it
         ↓
You approve → /self-improving-agent:promote graduates it to CLAUDE.md
         ↓
Pattern becomes enforced rule, source memory entry removed
         ↓
Space freed for new learnings
```

## What's Included

| Component | Count | Description |
|-----------|-------|-------------|
| Skills | 5 | review, promote, extract, status, remember |
| Agents | 2 | memory-analyst, skill-extractor |
| Hooks | 1 | PostToolUse error capture (zero overhead on success) |
| Reference docs | 4 | memory architecture, memory backends, promotion rules, rules directory patterns |
| Templates | 2 | rule template, skill template |

## Design Principles

1. **Don't fight memory — orchestrate it.** Memory captures. This plugin curates.
2. **No duplicate storage.** Reads from beads or `~/.claude/projects/` directly.
3. **Zero capture overhead.** Hook only fires on errors.
4. **Promotion = graduation.** Moving a pattern from memory to CLAUDE.md changes its priority.
5. **Dual backend support.** Works with beads (`bd remember`) and Claude auto-memory (`MEMORY.md`).

## Platform Support

| Platform | Memory System | Support |
|----------|--------------|---------|
| Claude Code + beads | `bd remember` | ✅ Full |
| Claude Code | Auto-memory (MEMORY.md) | ✅ Full |
| OpenClaw | workspace/MEMORY.md | ✅ Adapted |
| Codex CLI | AGENTS.md | ✅ Adapted |
| GitHub Copilot | copilot-instructions.md | ⚠️ Manual |

## Credits

Inspired by [pskoett/self-improving-agent](https://clawhub.ai/pskoett/self-improving-agent) — a structured learning loop for AI coding agents. This plugin builds on that concept with dual backend support for beads and Claude auto-memory.

## License

MIT — see [LICENSE](LICENSE)
