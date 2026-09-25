# Learning Protocol

The manifest is the steward's private cache of the repositories plus the few facts neither
the folders nor GitHub hold: purpose, `owns`, groups, dependencies, deprecation dates. It is
only useful if it is correct, and the repositories change constantly. Keeping it correct is
the steward's normal operation, done on its own authority: there is no read-back step and no
approval step for a manifest change.

## Who writes what

- **The `polyrepo` tool** writes every mechanical fact. `reconcile --fix` adds entries for
  new repos, removes entries whose repo is gone, follows renames, sets `remote_url`,
  `lifecycle`, archived state and `deprecated_on`, and appends the changelog itself.
  `create`, `deprecate` and `purpose` do the same for their own changes. Never edit a field
  the tool maintains.
- **The steward** writes what needs judgment: a purpose (through `purpose <repo> --text`),
  and groups, `owns`, dependencies, `role`, `owner` (by editing the manifest, per the
  `polyrepo-repo` skill). Each such edit gets a changelog entry written by the steward.

## What counts as a learning event

Anything the steward learns that changes one of the judgment fields:

- What a repo is for (its purpose), or what it owns.
- A new or removed dependency between two repos, or a change in its kind.
- A repo joining or leaving a group; a group added or removed.
- A change of a repo's role or owner.

Facts that are not about the repositories themselves go elsewhere: "where to find things"
to the knowledge store (**polyrepo-info**), the project's own scripts and procedures to
**polyrepo-governance**. Facts whose canonical home is another document (architecture,
requirements, deployment order) are never stored; see `manifest-schema.md`.

## How to capture one

1. **Update the manifest**, preserving comments. Do not stamp a date on the change — git
   history records when it changed.
2. **Append to `.polyrepo/changelog.md`**:

   ```markdown
   ## YYYY-MM-DD — <short title>
   - **What:** the fact, stated plainly.
   - **Why:** what motivated the change.
   - **Source:** how the steward learned it — "caller request", "reconcile", "code read".
   - **Affected:** repo names or fields touched.
   ```

3. **Resolve related drift.** If the change settles an open `drift_log` entry, set it to
   `resolved`.
4. **Verify.** Run `reconcile --json` and confirm the change introduced no finding.
5. **Commit and push** `.polyrepo/manifest.yaml` and `.polyrepo/changelog.md` on `main` in
   `$SKILLSPOKE_CC`.
6. **Speak in outcomes.** "Noted — X now depends on Y." Not the file mechanics.

## Drift

`reconcile` is the drift check, and it runs at the start of every steward invocation. Every
mechanical finding is repaired by `--fix`. A finding that needs judgment is settled by the
steward in the same invocation when the request touches that repo, and on every
`polyrepo-doctor` run. A `drift_log` entry is written only for a disagreement between the
manifest and another document that the steward cannot settle from the repositories, GitHub
or the code; the steward names it in its reply. It never invents an answer.

## Never destructive

The changelog is append-only. A repository is never deleted: it is deprecated and later
archived, and its entry stays with `lifecycle`, `deprecated_on`, and a changelog record of
why.

## Audit trail

Git history is the audit trail. Every manifest change has a changelog entry, and every
entry says what changed and why. Do not add manual date fields (`last_updated` and the
like); `deprecated_on` is a lifecycle fact, not an audit field.
