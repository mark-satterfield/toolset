---
name: "status"
description: "Memory health dashboard for beads or auto-memory — counts, capacity, stale entries, and recommendations."
command: /self-improving-agent:status
---

# /self-improving-agent:status — Memory Health Dashboard

Quick overview of your project's memory state across all memory systems.

Supports beads and Claude auto-memory. See `reference/memory-backends.md`.

## Usage

```
/self-improving-agent:status                    # Full dashboard
/self-improving-agent:status --brief            # One-line summary
```

## What It Reports

### Step 0: Detect memory backend

```bash
source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory-backend.sh" 2>/dev/null
BACKEND="$(detect_memory_backend 2>/dev/null || echo memory-md)"
```

### Step 1: Locate all memory files

**Beads backend:**

```bash
bd memories                    # list all memories
bd memories --json 2>/dev/null # structured count when available
```

**Auto-memory backend:**

```bash
MEMORY_DIR="$HOME/.claude/projects/$(pwd | sed 's|/|%2F|g; s|%2F|/|; s|^/||')/memory"
wc -l "$MEMORY_DIR/MEMORY.md" 2>/dev/null || echo "0"
ls "$MEMORY_DIR/"*.md 2>/dev/null | grep -v MEMORY.md
```

**Both backends — project rules:**

```bash
wc -l ./CLAUDE.md 2>/dev/null || echo "0"
wc -l ~/.claude/CLAUDE.md 2>/dev/null || echo "0"
ls .claude/rules/*.md 2>/dev/null | wc -l
```

### Step 2: Analyze capacity

**Auto-memory thresholds:**

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| MEMORY.md lines | < 120 | 120-180 | > 180 |
| CLAUDE.md lines | < 150 | 150-200 | > 200 |
| Topic files | 0-3 | 4-6 | > 6 |
| Stale entries | 0 | 1-3 | > 3 |

**Beads thresholds:**

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Memory count | < 20 | 20-40 | > 40 |
| CLAUDE.md lines | < 150 | 150-200 | > 200 |
| Stale entries | 0 | 1-3 | > 3 |

### Step 3: Quick stale check

**Beads:** For each memory referencing a file path, verify the file still exists.

**Auto-memory:**

```bash
grep -oE '[a-zA-Z0-9_/.-]+\.(ts|js|py|md|json|yaml|yml)' "$MEMORY_DIR/MEMORY.md" | while read f; do
  [ ! -f "$f" ] && echo "STALE: $f"
done
```

### Step 4: Output

**Beads backend:**

```
📊 Memory Status (beads)

  Persistent Memory:
    Entries:      {{count}}
    Backend:      beads (.beads/)

  Project Rules:
    CLAUDE.md:    {{n}} lines
    Rules:        {{count}} files in .claude/rules/
    User global:  {{n}} lines (~/.claude/CLAUDE.md)

  Health:
    Stale refs:   {{count}} (files no longer exist)
    Duplicates:   {{count}} (similar memories)

  💡 Recommendations:
    - {{recommendation}}
```

**Auto-memory backend:**

```
📊 Memory Status

  Auto-Memory (MEMORY.md):
    Lines:        {{n}}/200 ({{bar}}) {{emoji}}
    Topic files:  {{count}} ({{names}})
    Last updated: {{date}}

  Project Rules:
    CLAUDE.md:    {{n}} lines
    Rules:        {{count}} files in .claude/rules/
    User global:  {{n}} lines (~/.claude/CLAUDE.md)

  Health:
    Capacity:     {{healthy/warning/critical}}
    Stale refs:   {{count}} (files no longer exist)
    Duplicates:   {{count}} (entries repeated across files)

  💡 Recommendations:
    - {{recommendation}}
```

### Brief mode

```
/self-improving-agent:status --brief
```

**Beads:** `📊 Memory: {{count}} beads entries | {{count}} rules | {{status_emoji}} {{status_word}}`

**Auto-memory:** `📊 Memory: {{n}}/200 lines | {{count}} rules | {{status_emoji}} {{status_word}}`

## Interpretation

**Auto-memory capacity:**
- **Green (< 60%)**: Plenty of room. Auto-memory is working well.
- **Yellow (60-90%)**: Getting full. Consider running `/self-improving-agent:review` to promote or clean up.
- **Red (> 90%)**: Near capacity. Auto-memory may start dropping older entries. Run `/self-improving-agent:review` now.

**Beads:**
- Run `/self-improving-agent:review` when memory count exceeds 20 or stale refs appear.

## Tips

- Run `/self-improving-agent:status --brief` as a quick check anytime
- If capacity is yellow+, run `/self-improving-agent:review` to identify promotion candidates
- Stale entries waste space — delete references to files that no longer exist
- Topic files (auto-memory) are fine — Claude creates them to keep MEMORY.md under 200 lines
