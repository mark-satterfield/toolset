# Memory Backends

This plugin supports two persistent memory backends. Detect the active backend before reading or writing learnings.

## Detection

### 1. Beads (preferred when present)

A project uses beads memory when **both** are true:

- `bd` is on PATH
- A `.beads/` directory exists in the working tree (walk up from cwd)

```bash
source "$HOME/.claude/hooks/lib/bd-guard.sh" 2>/dev/null || \
  source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory-backend.sh"
bd_guard && echo "beads"
```

Or use the plugin helper:

```bash
source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory-backend.sh"
BACKEND="$(detect_memory_backend)"   # prints "beads" or "memory-md"
```

### 2. Session context override

If session instructions include beads memory guidance, treat the project as beads-backed even if detection is ambiguous:

```
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files
```

### 3. Claude auto-memory (default fallback)

When beads is not active, use Claude Code native auto-memory:

```
~/.claude/projects/<project-path>/memory/MEMORY.md
```

First 200 lines load at session start. Topic files (`debugging.md`, etc.) load on demand.

## Command Mapping

| Action | Beads | Auto-memory (MEMORY.md) |
|--------|-------|-------------------------|
| Save | `bd remember "<insight>" [--key slug]` | Append to `MEMORY.md` |
| List / search | `bd memories [keyword]` | Read `MEMORY.md` + topic files |
| Read one | `bd recall <key>` | Grep / read by line |
| Remove after promote | `bd forget <key>` | Edit `MEMORY.md` |
| Session injection | `bd prime` / `bd prime --memories-only` | First 200 lines of `MEMORY.md` |

## Workflow Differences

### `/self-improving-agent:remember`

- **Beads**: `bd remember "<insight>"` — optionally `--key` for dedup/update
- **Auto-memory**: append one concise bullet to `MEMORY.md`

### `/self-improving-agent:review`

- **Beads**: `bd memories` — analyze keys and content for recurrence, staleness, promotion candidates
- **Auto-memory**: read `MEMORY.md` and topic files; check 200-line capacity

### `/self-improving-agent:promote`

- **Beads**: find with `bd memories <keywords>`, promote to CLAUDE.md/rules, then `bd forget <key>`
- **Auto-memory**: find in `MEMORY.md`, promote, remove source line

### `/self-improving-agent:status`

- **Beads**: count memories (`bd memories`), check for duplicates via `bd find-duplicates` if available
- **Auto-memory**: line counts, topic files, 200-line capacity gauge

### `/self-improving-agent:extract`

- **Beads**: `bd memories <keywords>` for source material
- **Auto-memory**: grep `MEMORY_DIR/` for source material

## Priority (unchanged)

Promotion target is always CLAUDE.md or `.claude/rules/` — regardless of memory backend. The backend only affects where learnings are stored before promotion.

1. CLAUDE.md (highest)
2. `.claude/rules/`
3. Persistent memory (beads or MEMORY.md)
4. Session memory (lowest)
