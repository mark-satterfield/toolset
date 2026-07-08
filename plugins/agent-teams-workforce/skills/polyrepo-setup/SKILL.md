---
name: polyrepo-setup
description: >-
  Bootstrap the polyrepo manifest for the first time. Use when no
  `.polyrepo/manifest.yaml` exists yet and the project's repository map needs to be
  established — the discovery interview, topology inference, the manifest-location
  decision, and writing the initial manifest, changelog, and pointer breadcrumbs. Not a
  CUDLS skill; it runs once to stand the manifest up, then hands ongoing work to
  polyrepo-repo and the other polyrepo skills.
---

# Polyrepo Setup

You stand up the manifest the first time. Everything else in the toolkit assumes a manifest
exists; your job is to create the one that describes *this* project's actual shape.

## When you run

Only when there is no manifest — walk-up for a `.polyrepo/` folder and a `.polyrepo-pointer.json`
search both come up empty. If a manifest already exists, stop and hand back to **polyrepo-repo**.

## Two sub-modes

- **Existing-project** — the repos already exist; your job is discovery, labeling, and storing
  the manifest.
- **Greenfield mentor** — few or no repos yet; help the human *design* the polyrepo setup before
  writing it down. Be opinionated: recommend a shape and a storage location, walk the tradeoffs.

## How

Follow `references/setup-workflow.md` for the discovery interview (identity, topology,
relationships, conventions, rules, documentation, search, ownership). Use
`references/topology-recommendations.md` to **infer** the topology kind and recommend where
`.polyrepo/` should live — the kind is inferred by you and confirmed by the human in their own
words, never picked from a flat list. Scaffold from `assets/manifest-template.yaml`.

Do not infer topology from the filesystem alone; only the human can tell you the project's
intended shape.

## Outputs

- `.polyrepo/manifest.yaml` (from the template, populated)
- `.polyrepo/changelog.md` with the first entry
- a `.polyrepo-pointer.json` breadcrumb in each known repo, so the manifest is findable from
  inside any of them

Speak in outcomes, not internals. Once the manifest exists, ongoing changes flow through
**polyrepo-repo** (structure), **polyrepo-info** (knowledge), and **polyrepo-governance**
(the project's tooling registry).
