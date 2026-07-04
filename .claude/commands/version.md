---
description: >
  Bump plugin versions in this repo's .claude-plugin/marketplace.json.
  Wraps the version-bump skill: detects changed plugins, picks the semver
  bump from commit history, updates the manifest, and commits. Pass --push
  to also pull --rebase and push once the commit lands. 
argument-hint: "[--push]"
---

Run the /version skill. The skill bumps
the changed plugins in `.claude-plugin/marketplace.json` and commits the
result. The skill does not push.

Args passed to this command: `$ARGUMENTS`

After the skill returns, decide what to do next:

1. Check that the skill actually produced a bump commit (HEAD moved / a new
   commit exists). If the skill reported no changes or did not commit, stop
   here and report that. Do not push.

2. If a commit was created AND `$ARGUMENTS` contains `--push`, run the push
   step below in this repo. If `--push` was not passed, stop after the
   commit and report the new versions.

Push step — run this only when both conditions in step 2 are true:

```bash
name=$(basename "$(git rev-parse --show-toplevel)")

# Need an upstream to compare against; bail cleanly if none is set.
if ! git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  echo "  WARN: ${name} has no upstream set; skipping push"
  exit 1
fi

ahead=$(git rev-list '@{u}..HEAD' --count)
behind=$(git rev-list 'HEAD..@{u}' --count)

if [ "$ahead" -eq 0 ] && [ "$behind" -eq 0 ]; then
  echo "  up to date (${name})"
  exit 0
fi

echo "  ahead ${ahead}, behind ${behind}; pull --rebase then push..."
if ! git pull --rebase; then
  echo "  WARN: rebase failed for ${name}; aborting, reconcile by hand"
  git rebase --abort || true
  exit 1
fi

git push

if git status | grep -q "up to date"; then
  echo "  OK: ${name} up to date with origin"
else
  echo "  WARN: ${name} did not report 'up to date' after push"
fi
```

Report the final plugin versions, and the push result if you pushed.