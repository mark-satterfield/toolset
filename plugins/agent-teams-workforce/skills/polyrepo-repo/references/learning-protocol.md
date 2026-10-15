# Learning Protocol

The manifest is the steward's private cache of the repositories plus the few facts neither
the folders nor GitHub hold: groups and deprecation dates. What a repo holds and why it exists
is the matrix's, not the manifest's. It is
only useful if it is correct, and the repositories change constantly. Keeping it correct is
the steward's normal operation, done on its own authority: there is no read-back step and no
approval step for a manifest change.

## Who writes what

- **The `polyrepo` tool** writes every mechanical fact. `reconcile --fix` adds entries for
  new repos, removes entries whose repo is gone, follows renames, sets `remote_url`,
  `lifecycle`, archived state and `deprecated_on`, and appends the changelog itself.
  `create`, `rename` and `deprecate` do the same for their own changes, and for the matrix's
  stacks (see *The matrix* in the `polyrepo-repo` skill). Every one
  of them commits and pushes the steward's files. Never edit a field the tool maintains.
- **The steward** writes what needs judgment: groups and `owner` (by editing the manifest, per the
  `polyrepo-repo` skill). Each such edit gets a changelog entry written by the steward. A stack's
  `homeIn` or alias is written in the matrix (`link`, `put`), not here.

## What counts as a learning event

Anything the steward learns that changes one of the judgment fields:

- A repo joining or leaving a group; a group added or removed.
- A change of a repo's owner.

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

3. **Verify.** Run `reconcile --json` and confirm the change introduced no finding.
4. **Commit and push** with `commit --message "<what changed>"`.
5. **Speak in outcomes.** "Noted — X is now in group Y." Not the file mechanics.

## Drift

`reconcile` is the drift check, and it runs at the start of every steward invocation. Every
mechanical finding is repaired by `--fix`. A finding that needs judgment is settled by the
steward in the same invocation when the request touches that repo, and on every
`polyrepo-doctor` run. A disagreement the steward cannot settle from the repositories,
GitHub or the code is put to the user as a question in the steward's reply; the manifest
never records a question or an open item. It never invents an answer.

## Never destructive

The changelog is append-only. The steward never deletes a repository on GitHub: it is
deprecated, and the owner deletes it. While the repository exists on GitHub its entry stays with
`lifecycle` and `deprecated_on`; once it is gone, `reconcile --fix` removes the entry entirely
and the changelog records why.

## Audit trail

Git history is the audit trail. Every manifest change has a changelog entry, and every
entry says what changed and why. Do not add manual date fields (`last_updated` and the
like); `deprecated_on` is a lifecycle fact, not an audit field.
