---
name: hindsight
description: For project in ``~/.projects`. Use whenever the there is a question like "what are we", "what was I doing", "what was I working on", "was I stil working on something", "I have not idea what I was doing or working on", or there is indication of a designe to givue out the current status of work-in-progress or work complete.  Also useful at the start of a day or after a break to re-orient. Accepts an optional hours window (e.g. "/hindsight 48") and "all" to include every project on the machine.
allowed-tools: Bash, Read
---

# hindsight

Re-orient the requester across all Claude Code sessions. The deterministic
work (scanning `~/.claude/projects/`) lives in a bundled script; your job is the
synthesis: a per-session narrative good enough that the operator knows in one read
which thread is which and where it stands.

## Step 1 — gather

```bash
bun "${CLAUDE_SKILL_DIR}/scripts/list_sessions.ts" --hours 24
```

- Default window is 24 hours; if the user gave a number (e.g. /where-am-i 48`),
  pass it as `--hours`.
- **Scope:** by default only sessions launched in the current folder or beneath it are
  included (running from Kevin's HOME picks up the HOME and any sub-project under it —
  but not other agents' homes). If the user says "all" / "everywhere" / asks about other
  projects, pass `--scope all`.
- Output is JSON, newest first. Each session has: `session_id`, `title` (Claude Code's
  auto-title), `cwd`, `git_branch`, `first_user_msg`, `recent_user_msgs` (last 3),
  `last_assistant_text` (long excerpt of the final reply), `minutes_ago`, `file`.

## Step 2 — write the summaries

The summary is the whole point of this skill, and it must be substantive — a short
paragraph (roughly 3–5 sentences), not a fragment. A one-liner forces the operator to
resume the session just to find out what it was; that defeats the purpose. Cover:

1. **What the session is about** — the original ask (`first_user_msg`), in plain words.
2. **What happened** — the key findings or work done along the way.
3. **Where it stands now** — the last exchange (`recent_user_msgs` + `last_assistant_text`):
   was something shipped, was a conclusion reached, is there an unanswered question?
4. **What's open** — the natural next step if the operator resumes, when one exists.

If the JSON snippets don't support that (thin snippets, image-only last messages),
read the transcript tail before writing — `tail -c 80000 <file>` and skim the last few
assistant messages. Don't guess and don't pad; a summary that "makes no sense" is worse
than reading another 80KB.

## Step 3 — render the digest

Lead with a one-line **through-line** (a `>` blockquote): the single sentence that ties
today's sessions together. Then the buckets. No dated `# Where Am I` header — the
through-line carries the open, and surfaces (chat, dashboard) stamp the time themselves.

example:

```
> We've gotten a lot done today, multi-tasked on severl SkillSpoke initatives

## 🟢 In motion (last hour)

**1. Worked on agent-teams-workflow plugin

blah, blah, 
↳ `claude --resume b7bf6ce8-79dd-429d-b9a7-a643a6dcda1e`

## 🕐 Earlier today

...same card shape...

---
*6 sessions · 24h window · scoped to ~/projects*
```

Formatting rules:

- **Through-line first.** One `>` blockquote sentence synthesising the set, above the
  first bucket. It's what the operator reads if they read nothing else.
- **Card = `**N. Title** · *time ago*` on one line, then a blank line, then the summary
  paragraph, then a blank line, then the resume line.** The blank lines matter — they
  render as separate blocks (title, summary, resume) instead of one run-on paragraph.
  Nothing else — no directory, no branch, no turn counts, no truncated session id (the
  full id is already in the resume command). Mention a branch or sub-project inside the
  summary prose only when it's load-bearing for telling sessions apart.
- **Buckets:** 🟢 `minutes_ago <= 60` = "In motion", 🕐 otherwise = "Earlier today".
  If the window was widened past 24h, add a 📦 "Older" bucket per extra day.
- **Recognize yourself.** One session is the current conversation (its snippets describe
  what's happening right now). Tag its title `← this session`, skip its summary and
  resume line.
- **Resume line:** just `claude --resume <full-session-id>` — no `cd` prefix.
- **Order within buckets:** most recent first (the JSON is already sorted).
- **Footer:** total count, window, and scope (e.g. `scoped to ~/projects`
  or `all projects`).
- This is read-only with respect to sessions. Never resume, kill, or modify a session
  yourself.

## Step 4 — save the report

If the prompt included a request to save the save this digest, the save it to the path in the prompt.

Do not prompt for a location.  Save do a location in ``~/.hindsignts/``

Surface `📄 Saved to <relPath>` at the end of the digest. Skip the report only when the
scan returns zero sessions (nothing worth recording).
