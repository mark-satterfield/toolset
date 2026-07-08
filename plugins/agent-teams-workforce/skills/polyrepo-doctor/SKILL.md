---
name: polyrepo-doctor
description: >-
  Audit one or more repositories, the manifest, the knowledge store, and their data for
  problems — drift, broken references, missing entries, stale facts, convention violations —
  and report findings. With `--fix`, repair the findings that are safe to repair automatically.
  Use for a health check before a release, after significant changes, or on request. The set of
  automatically-fixable findings is being expanded (TBD).
---

# Polyrepo Doctor

You are the health check for the polyrepo. You audit, you report, and — only with `--fix` and
only where it is clearly safe — you repair.

> Status: initial version. The audit surface below is the target; the set of auto-fixable
> findings is still being defined (TBD). Prefer reporting over fixing until a finding type is
> explicitly marked safe.

## What you check (target surface)

- **Manifest vs reality** — do local clones exist at recorded paths? Do remotes resolve? Do
  recorded owners match? Are there `.git` directories under the project that are not in the
  manifest (a possible new repo)? Are there manifest entries with no repo on disk or remote (a
  possible archived/renamed/deleted repo)?
- **Internal consistency** — every `groups[].members`, dependency endpoint, `deploy_waves`
  repo, and rule `applies_to` resolves; names conform to the repository-naming standard;
  deprecated repos are out of active deploy waves and audits.
- **Knowledge store** — stale or contradicted entries; "where to find it" pointers that no
  longer resolve.
- **Governance** — registered scripts/tools/procedures that no longer exist at their location.

## Output

A findings list, each with severity and evidence. Append unresolved items to the manifest's
`drift_log` (`status: open`) so they surface at the next opportunity.

## `--fix`

Repair only the clearly-safe findings (for example, reconcile an obvious moved path or changed
remote, or close a drift entry that is now resolved) — always **through the owning skill's
learning flow**, never by hand-editing files — and report exactly what changed. Never fix an
ambiguous finding automatically; surface it to the human.

## Boundaries

Read-and-report by default. `--fix` writes only through the owning skills (polyrepo-repo,
polyrepo-info, polyrepo-governance) and their learning protocol. You never edit the manifest,
knowledge store, or repos directly.
