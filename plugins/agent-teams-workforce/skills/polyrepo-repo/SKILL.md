---
name: polyrepo-repo
description: >-
  Create, update, deprecate, list, or search a repository — and the information about it
  recorded in the polyrepo manifest. This is the steward's core skill for the repos
  themselves and their structural manifest entries (name, role, owner, paths, remotes,
  dependencies, groups, deploy waves). The first token of the request may be a CUDLS verb
  (create | update | delete | deprecate | list | search); if absent, infer the operation
  from the request. Use whenever a repository is added, renamed, deprecated, or when
  someone needs the count/list of repos or to find a repo by a structural attribute.
---

# Polyrepo Repo

You operate on **repositories and their entries in the manifest** — the structural spine of
the project. The manifest is `.polyrepo/manifest.yaml`. Its schema is
`references/manifest-schema.md`. Every change you make follows
`references/learning-protocol.md`: update the manifest **and** append `.polyrepo/changelog.md`
— never one without the other, never by hand outside this flow.

## First: locate the manifest

Walk up from the working directory for a `.polyrepo/` folder, or follow a
`.polyrepo-pointer.json`. If there is no manifest, the project is unbootstrapped — hand off
to **polyrepo-setup**; do not scaffold one here.

## Operations (CUDLS)

The request may lead with a verb. Route on it; if absent, infer.

- **create** — Add a repository entry. Its name **must** satisfy the project's
  repository-naming standard for its category. Fill `role`, `lifecycle: active`,
  `local_path`, `remote_url`, `default_branch`, `owner`, `language`, and wire it into the
  relevant `groups`, `relationships.dependencies`, and `relationships.deploy_waves`. (This
  skill owns the *manifest record*. Physically creating the repo on disk/GitHub — including
  any template scaffolding — is a separate local procedure; if the caller needs that, reach
  for **polyrepo-governance** to find or register the procedure.)
- **update** — Change fields on an existing repo entry. Keep every reference consistent
  (`groups[].members`, dependency endpoints, wave membership, rules `applies_to`).
- **delete / deprecate** — **Non-destructive. Deletion *is* deprecation.** Rename the repo to
  `deprecate-{original-name}` per the naming standard, set `lifecycle: deprecated`, record the
  reason and date, and drop it from active `deploy_waves` and audits (it no longer matches the
  application glob). **Keep the entry** — never remove it; a tombstone with a reason is the
  point. The actual GitHub + local-directory rename modifies a shared system: confirm the exact
  commands with the human before running them, or record the manifest side and let them run the
  rename.
- **list** — Enumerate repos, grouped by `role` / `lifecycle` / `group` as asked. This answers
  "how many repos", "what repos are there", "which repos are deprecated".
- **search** — Find repos by an attribute **recorded in the manifest** — owner, role,
  dependency, group, path, remote. For anything the manifest does *not* hold (derived or tribal
  facts like "which repos have no code" or "which contain a DynamoDB table"), hand off to
  **polyrepo-info** — those are searched live, not stored here.

## Recording every change

Per `references/learning-protocol.md`: update the manifest and append a `.polyrepo/changelog.md`
entry (What / Why / Source / Affected). Read non-obvious facts back to the human before
committing them, and resolve any related `drift_log` entries. **Git history is the audit trail —
do not add or bump manual metadata date fields.**

## Boundaries

- The manifest is edited only through this learning flow — never by hand, by you or anyone.
- Deletion is never destructive; entries are never silently dropped.
- You own structure. Derived/tribal knowledge is **polyrepo-info**; the project's own
  scripts/tools/procedures registry is **polyrepo-governance**; first-time bootstrap is
  **polyrepo-setup**.
