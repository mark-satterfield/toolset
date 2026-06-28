#!/usr/bin/env bash
# shepherd-pr.sh — loop controller and merge executor for PR shepherd workflow
#
# Owns ALL merge decisions. The /fix-pr command handles code fixes and thread
# resolution but does NOT merge. This script is the only place gh pr merge runs.
#
# SAFETY INVARIANT: gh pr merge is called ONLY when:
#   - mergeStateStatus == CLEAN
#   - unresolved thread count == 0
#   - CI checks have no FAILURE conclusions
#
# --admin is NEVER used. If the branch cannot be merged without --admin,
# the script stops and reports for human action.

set -euo pipefail

PR_NUMBER="${1:?Usage: shepherd-pr.sh <pr-number>}"
# Derive owner/repo from the current repository — no hardcoding, works in any repo.
REPO_NWO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
OWNER="${REPO_NWO%%/*}"
REPO="${REPO_NWO##*/}"
MAX_ITER=5
ITER=0

unresolved_count() {
  # shellcheck disable=SC2016  # GraphQL body is intentionally single-quoted; $owner/$repo are GraphQL vars, bound via -f below
  gh api graphql -f query='
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner, name:$repo) {
        pullRequest(number:$number) {
          reviewThreads(first:100) { edges { node { isResolved } } }
        }
      }
    }
  ' -f owner="$OWNER" -f repo="$REPO" -F number="$PR_NUMBER" \
    --jq '[.data.repository.pullRequest.reviewThreads.edges[].node | select(.isResolved == false)] | length'
}

ci_failures() {
  gh pr checks "$PR_NUMBER" --json conclusion \
    --jq '[.[] | select(.conclusion == "FAILURE")] | length' 2>/dev/null || echo "0"
}

merge_status() {
  gh pr view "$PR_NUMBER" --json mergeStateStatus --jq '.mergeStateStatus'
}

while [ $ITER -lt $MAX_ITER ]; do
  ITER=$((ITER + 1))
  echo "--- Shepherd iteration $ITER of $MAX_ITER ---"

  STATUS=$(merge_status)
  UNRESOLVED=$(unresolved_count)
  FAILURES=$(ci_failures)

  echo "  mergeStateStatus : $STATUS"
  echo "  unresolved threads: $UNRESOLVED"
  echo "  CI failures       : $FAILURES"

  if [ "$STATUS" = "CLEAN" ] && [ "$UNRESOLVED" -eq 0 ] && [ "$FAILURES" -eq 0 ]; then
    echo "PR #$PR_NUMBER is clean — merging"
    # NOTE: --admin is deliberately absent. If this call fails due to branch
    # protection or required reviews, it is a human action — not a flag to add.
    gh pr merge "$PR_NUMBER" --merge --delete-branch
    echo "PR #$PR_NUMBER merged and branch deleted."
    exit 0
  fi

  if [ "$FAILURES" -gt 0 ]; then
    echo "CI has $FAILURES failing check(s) — invoking fix-pr"
  fi

  if [ "$UNRESOLVED" -gt 0 ]; then
    echo "$UNRESOLVED unresolved thread(s) — invoking fix-pr"
  fi

  if [ "$STATUS" != "CLEAN" ] && [ "$STATUS" != "BEHIND" ]; then
    echo "Merge state is $STATUS — invoking fix-pr to resolve"
  fi

  # Invoke the AI fix command
  claude --print "/fix-pr $PR_NUMBER"

  if [ $ITER -lt $MAX_ITER ]; then
    echo "Waiting 60s for CI and GitHub to settle..."
    sleep 60
  fi
done

echo ""
echo "Shepherd reached max iterations ($MAX_ITER) without a clean merge."
echo "Current state:"
echo "  mergeStateStatus : $(merge_status)"
echo "  unresolved threads: $(unresolved_count)"
echo "  CI failures       : $(ci_failures)"
echo ""
echo "Human action required. PR #$PR_NUMBER was NOT merged."
exit 1
