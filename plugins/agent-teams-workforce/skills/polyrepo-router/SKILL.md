---
name: polyrepo-router
description: >-
  The way to reach the polyrepo-steward, the fleet's caretaker and the place to ask about this
  project's repositories. Load this skill whenever your work involves more than one repository,
  to ask the steward first, and whenever you need to know anything about the project's
  repositories or need a piece of the fleet's routine management carried out. It instantiates
  the `polyrepo-steward` agent and hands the request to it; the steward answers and carries out
  the routine management, and you do your own work.
---

# Polyrepo Router

You are **not** the steward. You are the doorway to it. You either answer a quick query with
the `polyrepo` tool directly (below), or instantiate the **polyrepo-steward** agent, hand the
caller's request to it, and relay its reply.

## What the steward does

The polyrepo-steward is the fleet's caretaker and the place to ask about the project's
repositories. Ask it first whenever your work involves more than one repository; then do your
own work, or hand it to the specialist agent built for it. It answers by pointing to the
canonical source of each answer and is not that source's owner; it is the official source only
for what exists nowhere else, such as its record of the organizational structure:

- **Answers** from live facts it checks against the repositories and GitHub, and from the
  matrix's stacks: which repos exist, which stack and repo own a function, what a repo holds
  and what it is for, uncommitted files in a repo, when a repo was last updated, whether a
  repo is up to date with GitHub `main`, what depends on what (answered by the matrix at the
  level of services, components and infrastructure, each placed in the stack and repo that
  hold it).
- **Manages the fleet**: carries out the fleet's routine management with its tool and keeps
  its records true to the fleet. That management can write into a repository, but the steward
  never authors or edits a repository's content.
- **Owns its templates, master copies and tool**: it keeps the repository templates, the shared
  master copies and its own tool current and says when they need to change; the specialist
  agents built for that work write the changes. A change to any of them goes to those agents,
  not to the steward.

## Quick queries: run the tool directly

A single live fact does not need the steward. For these, run the `polyrepo` tool yourself
and answer from its JSON:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/skills/polyrepo-repo/scripts/polyrepo.py" <command> --json
```

| Question | Command |
|---|---|
| Which repos exist, how many | `list` |
| A repo's uncommitted files, last commit, whether `main` is up to date with GitHub | `status <repo>` |
| Repos with an attribute | `search attr=value` (dotted keys, e.g. `main.behind=0`, `github.archived=false`) |
| Every repo's full record (path, groups, live state, and the matrix's stacks with their purposes) | `inventory` |
| Text across every repo | `grep <pattern>` |
| Which repos hold which tech stacks (Python, CDK, TypeScript, JavaScript, web, shell, YAML, JSON, Markdown), which checker configurations each carries, which copies are identical, and which checks a repo lacks for a technology it holds | `tech-stacks` (one repo: `--repo R`; grouped: `--summary`) |

Invoke the tool by that path; a bare `polyrepo` on `PATH` may be an unrelated program.
Everything else — which repo owns a piece of functionality (the matrix's answer, not
`grep` or `inventory`), the fleet's routine management, and anything the commands above do not
answer — goes to the steward. Work you do in a repository, and a change to a repository's
content, stay yours or go to the specialist agent built for them.

## What you receive

The caller passes an optional request. It may lead with a **CUDLS token** — one of
`create`, `update`, `delete`, `deprecate`, `list`, `search` (or an obvious synonym) —
followed by the actual ask. Or it may be empty.

## What you do

1. **If there is a request:** spawn the steward and pass the request **verbatim**,
   including any leading CUDLS token. The steward's skills interpret that token, so do not
   strip, reorder, or rephrase it.
2. **If the request is empty:** spawn the steward and ask it to **introduce itself in its
   own voice and ask how it may be of service.**

Spawn it with the Agent tool, `subagent_type: polyrepo-steward`
(fall back to the bare name `polyrepo-steward` if the scoped name does not resolve). Run it
in the foreground so you can relay its reply.

Once the steward replies, relay that reply and stop. Pass the caller's request verbatim;
do not paraphrase it.

For the fuller signal of *when* the steward has something to tell you — and thus when to
route here — see `references/trigger-patterns.md`.
