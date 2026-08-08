---
description: "Resume an interrupted workflow run, or decide it must restart"
argument-hint: "<runId> [scriptPath]"
allowed-tools: [Bash, Read, Workflow]
---

# Resume a run

Continue the run `$ARGUMENTS` was interrupted from — or establish that it must not
be resumed, which is the more important half.

## 1. Establish what the run left behind

A killed run does not clean up. Before anything else, find out what is on disk:

```bash
cd <the repo the run was working in>
git status --short
```

Report it. Three cases, and they lead to different places:

- **Clean tree** — nothing was written, or it was all committed. Resume freely.
- **Uncommitted TEST files** — Red got partway. Do **not** delete them. The Red
  phase now surveys existing tests and reuses ones that still fail, so a resume
  will pick them up rather than re-author them.
- **Uncommitted PRODUCTION code** — Green got partway. This is the one to look at
  closely: a half-applied fix may leave the repo in a state where the tests pass
  for the wrong reason. Report exactly which files, and do not resume until the
  operator has seen the list.

## 2. Decide resume versus restart

Resume replays completed agents from cache and re-runs from the first call whose
prompt or options changed. That makes one question decisive:

> **Has the workflow script changed since the run started?**

```bash
ls -d ~/.claude/plugins/cache/mark-satterfield/agent-teams-workforce/*/ | sort -V | tail -1
```

- **Same version, unchanged script** → resume. Cached agents return instantly.
- **Plugin upgraded, or the script edited** → **restart**. A resume against an
  edited script replays cached results from the old logic and then runs the new
  logic on top, which is neither the old run nor a clean one. Say so plainly and
  restart instead.

There is a second trap worth naming: **a bead's description is embedded in every
agent prompt.** Editing it — even one word — invalidates the cache, so phases
RESTART instead of resuming. To resume past a fixed gate, keep the description
byte-identical and change only the script.

## 3. Resume

```
Workflow({scriptPath: "$ROOT/workflows/<composite>.js", resumeFromRunId: "<runId>"})
```

`scriptPath` must be the same script the run started from. If you cannot determine
which composite it was, read the run journal:

```bash
ls -t ~/.claude/projects/*/*/subagents/workflows/ | head
```

Each run directory holds `journal.jsonl`, one line per completed agent with its
return value. That is also where to look when a resumed run behaves oddly — read
it before diagnosing, rather than assuming a cached result was non-empty.

## 4. When to restart instead

Restart, and say why, when any of these holds:

1. The plugin version changed, or the script was edited.
2. The work already on disk is known to be **wrong** — a resumed Red will survey
   those tests and may accept them. Pass `skipSurvey: true` to force fresh
   authoring, or clean the tree first.
3. The run died in Green with production code half-applied and no one has looked
   at the diff.

Resuming past a real problem to save tokens spends more of them than restarting.
