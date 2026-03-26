---
name: chat-history
description: Extract and organize Claude Code session history into the project's .chats directory. Captures both sides of the conversation (user and assistant). Use when documenting Claude sessions, exporting conversation history, backfilling earlier sessions, or maintaining a log of interactions for the current project.
user_invocable: true
---

# Chat History Extractor

Extract full conversations (user + assistant) from Claude Code session history
(`~/.claude/projects/`) and write them to `.chats/YYYYMMDD.md` in the project
root.

## When to Use This Skill

Use this skill when the user wants to:
- **Extract session history** from Claude Code sessions
- **Document conversations** for future reference
- **Backfill earlier sessions** — historical JSONL files for the current project and its worktrees
- **Create instruction logs** organized by date
- **Export conversations** (both user and assistant sides) from `.jsonl` session files
- **Maintain a changelog** of Claude interactions

## How It Works

Claude Code stores session data in `~/.claude/projects/{project-path-encoded}/`
as `.jsonl` files. Each line is a JSON record.

Path encoding: `/` → `-`, leading `-` prepended, literal `-` in path component
names → `--`.
Examples:
- `/Users/msat1971/git/SkillSpoke` → `-Users-msat1971-git-SkillSpoke`
- `/Users/msat1971/git/SkillSpoke-marketing-service` → `-Users-msat1971-git-SkillSpoke--marketing-service`

Files named `agent-*.jsonl` are sub-agent sessions — skip them.

The relevant record types:

| type | when to capture |
|------|----------------|
| `user` | `userType == "external"` AND `isMeta != true` AND `isSidechain != true` AND content is non-empty after filtering |
| `assistant` | `message.stop_reason != null` (skip streaming partials) AND `isSidechain != true` AND content array has at least one `text` block |

Key fields:
- `uuid` — unique record identifier
- `parentUuid` — tree linkage
- `sessionId` — session grouping
- `promptId` — pairs a user turn with its assistant reply; both records share the same `promptId`
- `timestamp` — ISO 8601 UTC
- `isSidechain` — compact summary agent track; always exclude
- `isMeta` — internal/command messages; always exclude
- `message.model` — assistant records only
- `message.stop_reason` — non-null only on the final streaming record for an assistant turn

**Streaming partials:** the same assistant `uuid` appears multiple times as
tokens arrive. Only the record where `message.stop_reason` is non-null is the
complete response. Skip all others.

**Pairing exchanges:** `promptId` groups a user message with its assistant
reply. Order within a group by `timestamp`.

**Sidechain exclusion:** `isSidechain == true` marks the compact summary agent
track. Always exclude for conversation views.

## Output Format

One file per day: `.chats/YYYYMMDD.md`

```markdown
# Chat — YYYYMMDD

## {task title}

**User:** {user instruction}

**Claude:** {assistant response}

---

## {next task title}

**User:** {next user instruction}

**Claude:** {next assistant response}

---
```

Group related exchanges under a descriptive `##` heading derived from the
user's first message in that exchange. Derive the heading from the first
sentence or first ~60 characters, whichever is shorter — no trailing
punctuation. Use `---` as a divider between exchanges.

Keep assistant responses concise — trim tool use narration and internal
reasoning; preserve the substantive answer.

## Example Output

`.chats/20260321.md`:

```markdown
# Chat — 20260321

## shepherd-pr not fixing all issues

**User:** The project skill /shepherd-pr is still not fixing all issues and
leaving comments on a PR and closing out conversation threads.

Example: https://github.com/satteritsik/SkillSpoke/pull/244#discussion_r2955694355

100% of all PR conversation threads in the PR need to be attempted at
resolving and closing, and, regardless of whether it is successful or not,
there needs to be a comment in the conversation thread as to what exactly the
skill attempted to do.

**Claude:** Updated the shepherd-pr skill with two changes: (1) every thread
now gets a reply comment before resolution regardless of outcome, and (2) a
PR-level audit summary comment is posted after each attempt listing all
threads touched, actions taken, and results.

---

## backfill chat history from stored sessions

**User:** I want your help to figure out a way to back-fill from other stored
chat history.

**Claude:** The session JSONL files are already there — the skill just hasn't
processed them yet. The approach is: enumerate all non-agent JSONL files in the
project's session dir, extract their dates from the `timestamp` field, check
which `.chats/YYYYMMDD.md` files are missing, and process the gaps.

---
```

## Backfill

Backfilling is handled by `backfill_chats_markdown.py`. Run it from the
command line — no Claude session required, zero tokens consumed.

```bash
# Preview — count exchanges without writing
python3 backfill_chats_markdown.py --dry-run

# Run against the current project
python3 backfill_chats_markdown.py
```

The script covers the main project session directory and all worktree
directories matching `{project}--*`. It is idempotent — re-running only
writes exchanges not already present, keyed on `promptId`.

## Step 1: Identify the Current Session Directory

```bash
PROJECT_PATH=$(pwd | sed 's|/|-|g' | sed 's|^|/|' | sed 's|^/|-|')
SESSION_DIR="$HOME/.claude/projects/$PROJECT_PATH"

# Check if exists
if [ -d "$SESSION_DIR" ]; then
    echo "Session directory: $SESSION_DIR"
    echo "Sessions:"
    ls "$SESSION_DIR"/*.jsonl 2>/dev/null | grep -v "agent-"
else
    echo "No session directory found for this project"
fi
```

## Step 2: Extract the Conversation

### User messages

```bash
cat {session-file}.jsonl | jq -c '
  select(
    .type == "user" and
    .userType == "external" and
    (.isMeta | not) and
    (.isSidechain | not)
  ) |
  {
    promptId: .promptId,
    timestamp: .timestamp,
    role: "user",
    content: (
      .message.content |
      if type == "string" then .
      elif type == "array" then
        [ .[] | select(.type == "text") | .text ] | join("\n\n")
      else "" end
    )
  } |
  select(
    .content != "" and
    (.content | startswith("Caveat:") | not) and
    (.content | startswith("<command") | not) and
    (.content | startswith("<local-command") | not) and
    (.content | startswith("This session is being continued") | not) and
    (.content | startswith("<user-prompt-submit-hook>") | not) and
    (.content | startswith("Analysis:") | not) and
    (.content | startswith("Base directory for this skill:") | not)
  )
'
```

### Assistant messages

```bash
cat {session-file}.jsonl | jq -c '
  select(
    .type == "assistant" and
    (.isSidechain | not) and
    .message.stop_reason != null
  ) |
  {
    promptId: .promptId,
    timestamp: .timestamp,
    role: "assistant",
    model: .message.model,
    stop_reason: .message.stop_reason,
    content: (
      .message.content |
      if type == "array" then
        [ .[] | select(.type == "text") | .text ] | join("\n\n")
      else "" end
    )
  } |
  select(.content != "")
'
```

### Merge and pair by promptId

Collect all user and assistant records from both extractions. Group by
`promptId`. Within each group, sort by `timestamp`. Each group becomes one
exchange in the output:

```
**User:** {user content}

**Claude:** {assistant content}
```

Exchanges without a matching assistant reply (e.g. interrupted sessions) get
`**Claude:** *(no response)*`.

## Step 3: Create/Update .chats Files

Create the `.chats/` directory if it doesn't exist:

```bash
mkdir -p .chats
```

For each date with exchanges, write `.chats/YYYYMMDD.md`:

```markdown
# Chat — YYYYMMDD

## {heading derived from first user message}

**User:** {user content}

**Claude:** {assistant content}

---
```

If the file already exists, append only exchanges whose `promptId` is not
already present in the file.

## Filtering Rules

**Include:**
- User instructions, questions, and requests
- Assistant substantive responses — code, explanations, decisions, analysis

**Exclude from user content:**
- System hook output (`<command-name>`, `<local-command-stdout>`)
- Session continuation boilerplate (`This session is being continued...`)
- Tool results fed back as user messages
- Hook notifications (`<user-prompt-submit-hook>`)
- Caveat messages
- Skill base directory announcements

**Exclude from assistant content:**
- `thinking` blocks (internal reasoning)
- `tool_use` blocks (tool invocations)
- `tool_result` blocks
- Streaming partial records (any record where `message.stop_reason` is null)

## Workflow Summary

1. Compute encoded project path from `pwd`
2. Locate session directory: `~/.claude/projects/{encoded-path}/`
3. List all non-`agent-` JSONL files
4. For each file:
   a. Extract user records (filtered)
   b. Extract assistant records (terminal only)
   c. Pair by `promptId`, sort by `timestamp`
   d. Bucket exchanges by date (Eastern time)
5. For each date:
   a. Create `.chats/YYYYMMDD.md` or append to existing
   b. Skip `promptId` values already in the file

## Notes

- `agent-*.jsonl` files are sub-agent sessions. Skip them — they are
  identified by the `agent-` filename prefix.
- The same `uuid` may appear on both sidechain and non-sidechain records.
  Always filter on `isSidechain != true` before processing.
- A single JSONL file may span multiple calendar dates. Always bucket by
  message timestamp, not file mtime.
- Worktree session directories follow the pattern
  `-Users-msat1971-git-SkillSpoke--{worktree-name}` — the `--` encodes a
  literal `-` in the path component name.