---
name: "remember"
description: "Explicitly save important knowledge to persistent memory (beads or auto-memory) with context. Use when a discovery is too important to rely on auto-capture."
command: /self-improving-agent:remember
---

# /self-improving-agent:remember — Save Knowledge Explicitly

Writes an explicit entry to persistent memory when something is important enough that you don't want to rely on Claude noticing it automatically.

Supports two backends — detect before writing. See `reference/memory-backends.md`.

## Usage

```
/self-improving-agent:remember <what to remember>
/self-improving-agent:remember "This project's CI requires Node 20 LTS — v22 breaks the build"
/self-improving-agent:remember "The /api/auth endpoint uses a custom JWT library, not passport"
/self-improving-agent:remember "Reza prefers explicit error handling over try-catch-all patterns"
```

## When to Use

| Situation | Example |
|-----------|---------|
| Hard-won debugging insight | "CORS errors on /api/upload are caused by the CDN, not the backend" |
| Project convention not in CLAUDE.md | "We use barrel exports in src/components/" |
| Tool-specific gotcha | "Jest needs `--forceExit` flag or it hangs on DB tests" |
| Architecture decision | "We chose Drizzle over Prisma for type-safe SQL" |
| Preference you want Claude to learn | "Don't add comments explaining obvious code" |

## Workflow

### Step 0: Detect memory backend

```bash
source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory-backend.sh" 2>/dev/null || \
  source "$HOME/.claude/hooks/lib/bd-guard.sh" 2>/dev/null
BACKEND="$(detect_memory_backend 2>/dev/null || { bd_guard 2>/dev/null && echo beads || echo memory-md; })"
```

Also check session context: if instructions say `bd remember` and forbid `MEMORY.md`, use beads.

### Step 1: Parse the knowledge

Extract from the user's input:
- **What**: The concrete fact or pattern
- **Why it matters**: Context (if provided)
- **Scope**: Project-specific or global?

### Step 2: Check for duplicates

**Beads backend:**

```bash
bd memories "<keywords>"
```

If a similar memory exists (same key or overlapping content):
- Show it to the user
- Ask: "Update the existing entry (`bd remember ... --key <key>`) or add a new one?"

**Auto-memory backend:**

```bash
MEMORY_DIR="$HOME/.claude/projects/$(pwd | sed 's|/|%2F|g; s|%2F|/|; s|^/||')/memory"
grep -ni "<keywords>" "$MEMORY_DIR/MEMORY.md" 2>/dev/null
```

If a similar entry exists:
- Show it to the user
- Ask: "Update the existing entry or add a new one?"

### Step 3: Write to persistent memory

**Beads backend:**

```bash
bd remember "<concise fact or pattern>" [--key slug-from-content]
```

Keep entries concise — one line when possible.

**Auto-memory backend:**

Append to the end of `MEMORY.md`:

```markdown
- {{concise fact or pattern}}
```

If MEMORY.md is over 180 lines, warn the user:

```
⚠️ MEMORY.md is at {{n}}/200 lines. Consider running /self-improving-agent:review to free space.
```

### Step 4: Suggest promotion

If the knowledge sounds like a rule (imperative, always/never, convention):

```
💡 This sounds like it could be a CLAUDE.md rule rather than a memory entry.
   Rules are enforced with higher priority. Want to /self-improving-agent:promote it instead?
```

### Step 5: Confirm

**Beads:**

```
✅ Saved to beads memory

  "{{entry}}"

  Claude will see this via bd prime in every session.
```

**Auto-memory:**

```
✅ Saved to auto-memory

  "{{entry}}"

  MEMORY.md: {{n}}/200 lines
  Claude will see this at the start of every session in this project.
```

## What NOT to use /self-improving-agent:remember for

- **Temporary context**: Use session memory or just tell Claude in conversation
- **Enforced rules**: Use `/self-improving-agent:promote` to write directly to CLAUDE.md
- **Cross-project knowledge**: Use `~/.claude/CLAUDE.md` for global rules
- **Sensitive data**: Never store credentials, tokens, or secrets in memory

## Tips

- Be concise — one line beats a paragraph
- Include the concrete command or value, not just the concept
  - ✅ "Build with `pnpm build`, tests with `pnpm test:e2e`"
  - ❌ "The project uses pnpm for building and testing"
- If you're remembering the same thing twice, promote it to CLAUDE.md
