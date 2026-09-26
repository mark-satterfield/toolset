---
name: polyrepo-tribal-knowledge
description: >-
  Scan all of the project's repositories and documents to discover anything new about the
  repos — especially WHERE things live — and add or update the polyrepo knowledge store for
  fast retrieval later. Not a CUDLS skill; it is a scan-and-record pass. Run it periodically,
  after significant changes, or when the steward notices the knowledge store is thin or stale.
---

# Polyrepo Tribal Knowledge

You are the sweep that keeps the knowledge store useful. You go looking across the project's
repos and documents for durable, non-structural facts worth keeping close — and record them so
no agent has to rediscover them.

## What you capture

Mostly **where things live**: the locations of key docs and knowledge bases, the source of a
naming or coding convention, which store answers a class of question, cross-repo pointers, and
other hard-won "where" facts. You are not building an exhaustive Q&A cache — you are recording
the pointers that make future searches instant.

## How you search

Follow the precedence ladder in `../polyrepo-info/references/search-recipes.md`:

1. The project's `CLAUDE.md` / `AGENTS.md` first — it often names the data locations outright.
2. The project's second-brain tools — Obsidian CLI, GraphRAG, GitNexus, NotebookLM, vector DBs.
3. Generic scanning (ripgrep → git grep → gh) only where nothing else applies.

## What you produce

Add or update entries in the knowledge store `.polyrepo/knowledge.yaml` (owned by
**polyrepo-info**; see it for the entry shape). Verify every entry against reality before
storing it — the path, vault note or command it names exists, and the fact it states is what
the code or the canonical document says now — as **polyrepo-info** describes. Record through
the learning protocol (`../polyrepo-repo/references/learning-protocol.md`): update the store
**and** append `.polyrepo/changelog.md`, then run the tool's `commit --message "<what
changed>"`. There is no read-back step.

## What you do not do

- You do not change the manifest's structure — that is **polyrepo-repo**.
- You do not pre-compute and store answers to every possible question — only what is genuinely
  worth keeping close, weighted toward *where* to find things.

## Reconcile

Every sweep also re-verifies every existing entry the same way. An entry that no longer holds
is corrected to where the thing lives now, or retired with the reason when the thing is gone,
and the change is recorded in the changelog. Report what was corrected or retired.
