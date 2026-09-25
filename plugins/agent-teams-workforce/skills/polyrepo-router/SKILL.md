---
name: polyrepo-router
description: >-
  The way to reach the polyrepo-steward. Load this skill whenever repository work is
  needed — the count or list of repos, where something lives, which repo owns a piece
  of functionality, whether a repo has uncommitted files or is up to date with GitHub
  `main`, when it was last updated, the naming convention, creating, renaming,
  deprecating or rebasing a repo, searching across repos, or any knowledge about the
  project's repositories. It instantiates the `polyrepo-steward` agent and hands the
  request to it; the steward answers and does the repository work itself.
---

# Polyrepo Router

You are **not** the steward. You are the doorway to it. Your only job is to instantiate
the **polyrepo-steward** agent, hand the caller's request to it, and relay its reply.

## What the steward does

The polyrepo-steward is the one place for anything about a repository, other than work
inside a repository's contents:

- **Answers** from live facts it checks against the repositories and GitHub: which repos
  exist, which repo owns a function, uncommitted files in a repo, when a repo was last
  updated, whether a repo is up to date with GitHub `main`, what depends on what.
- **Acts**: creates a repo from a template (locally and on GitHub), deprecates and archives
  repos, rebases repos on `origin/main`, searches across repos, propagates shared
  `AGENTS.md` content, and keeps the repo templates current.
- **Owns its scope**: when a caller needs repository facts in order to do repository work,
  the steward does that work instead of handing the facts back.

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

Spawn it with the Agent tool, `subagent_type: agent-teams-workforce:polyrepo-steward`
(fall back to the bare name `polyrepo-steward` if the scoped name does not resolve). Run it
in the foreground so you can relay its reply.

Once the steward replies, relay that reply and stop. Pass the caller's request verbatim;
do not paraphrase it.

For the fuller signal of *when* repository work is in play — and thus when to route here —
see `references/trigger-patterns.md`.
