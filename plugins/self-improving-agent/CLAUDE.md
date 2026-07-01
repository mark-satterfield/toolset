# Self-Improving Agent — Claude Code Instructions

This plugin helps you curate persistent project knowledge into durable rules and skills.

## Commands

Use the `/self-improving-agent:` namespace for all commands:

- `/self-improving-agent:review` — Analyze persistent memory health and find promotion candidates
- `/self-improving-agent:promote <pattern>` — Graduate a learning to CLAUDE.md or `.claude/rules/`
- `/self-improving-agent:extract <pattern>` — Create a reusable skill from a proven pattern
- `/self-improving-agent:status` — Quick memory health dashboard
- `/self-improving-agent:remember <knowledge>` — Explicitly save something to persistent memory

## Memory backends

This plugin supports two persistent memory backends. Detect before reading or writing:

| Backend | When | Storage |
|---------|------|---------|
| **Beads** | `.beads/` present + `bd` on PATH | `bd remember` / `bd memories` |
| **Auto-memory** | Default fallback | `~/.claude/projects/<path>/memory/MEMORY.md` |

```bash
source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory-backend.sh"
BACKEND="$(detect_memory_backend)"
```

See `reference/memory-backends.md` for full detection logic and command mapping.

## When to use each command

### After completing a feature or debugging session
```
/self-improving-agent:review
```
Check if anything Claude learned should become a permanent rule.

### When a pattern keeps coming up
```
/self-improving-agent:promote "Always run migrations before tests in this project"
```
Moves it from memory (background note) to CLAUDE.md (enforced rule).

### When you solved something non-obvious that could help other projects
```
/self-improving-agent:extract "Docker build fix for ARM64 platform mismatch"
```
Creates a standalone skill with SKILL.md, ready to install elsewhere.

### To check memory capacity
```
/self-improving-agent:status
```
Shows counts, topic files, stale entries, and recommendations.

## Key principle

**Don't fight memory — orchestrate it.**

- Persistent memory is great at capturing patterns. Let it do its job.
- This plugin adds judgment: what's worth keeping, what should be promoted, what's stale.
- Promoted rules in CLAUDE.md have higher priority than memory entries.
- Removing promoted entries frees space for new learnings.

## Agents

- **memory-analyst**: Spawned by `/self-improving-agent:review` to analyze patterns across memory
- **skill-extractor**: Spawned by `/self-improving-agent:extract` to generate complete skill packages

## Hooks

The `error-capture.sh` hook fires on `PostToolUse` (Bash only). It detects command failures and suggests saving the fix via `/self-improving-agent:remember` or `bd remember`. Zero overhead on successful commands.

To enable:
```json
// .claude/settings.json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/error-capture.sh"
      }]
    }]
  }
}
```
