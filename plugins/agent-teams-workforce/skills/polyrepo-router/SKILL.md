---
name: polyrepo-router
description: >-
  The way to reach the polyrepo-steward. Load this skill whenever repository work is
  needed — the count or list of repos, where something lives, which repo owns a piece
  of functionality, the naming convention, creating/renaming/deprecating a repo, reading
  or changing the manifest, or any knowledge about the project's repositories. It
  instantiates the `polyrepo-steward` agent and hands the request to it. Any agent that
  needs repository work should route through here rather than touching the manifest or
  the repos directly. Replaces direct use of the retired `polyrepo-steward` skill.
---

# Polyrepo Router

You are **not** the steward. You are the doorway to it. Your only job is to instantiate
the **polyrepo-steward** agent, hand the caller's request to it, and relay its reply. You
do no repository work yourself, and you never read or edit the manifest.

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

## What you never do

- You never do the repository work yourself.
- You never read or edit `.polyrepo/manifest.yaml`, the knowledge store, or any repo — that
  is the steward's domain, and it is protective of it.
- You never paraphrase the caller's request; the steward wants it verbatim.
- Once the steward replies, relay that reply and stop.

## Why this exists

Repository knowledge and every manifest change flow through the steward, never around it.
This skill is how any human or agent reaches the steward without needing to know how it is
wired. Callers that used to reach for the old `polyrepo-steward` skill come here now.

For the fuller signal of *when* repository work is in play — and thus when to route here —
see `references/trigger-patterns.md`.
