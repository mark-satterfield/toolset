#!/usr/bin/env bash
# shepherd-pr.sh — the shepherd-pr skill's loop.
#
# Follows ONE pull request until GitHub reports it MERGED or CLOSED. Every
# iteration re-reads the PR from GitHub and decides from that alone:
#
#   something to fix  -> start one headless pass session (/agent-teams-workforce:fix-pr)
#   checks pending, or nothing to fix and auto-merge armed -> wait, poll again
#   nothing to fix, checks passing, auto-merge NOT armed   -> exit 2
#   MERGED or CLOSED                                       -> exit 0
#
# "Something to fix" is: a failing or cancelled check, an unresolved review
# thread, a merge conflict (DIRTY), a branch behind its base (BEHIND), a review
# decision of CHANGES_REQUESTED with a changes-requested review none of whose
# threads is still open (the pass dismisses it), or a reviewer comment,
# CodeRabbit reply or changes-requested review newer than the last pass's
# audit comment.
#
# SAFETY: this script never merges. It runs no `gh pr merge` and no --admin,
# and every pass session runs with a deny rule on `Bash(gh pr merge:*)`.
# GitHub auto-merge merges.
#
# Usage: shepherd-pr.sh <pr-number> [owner/repo] [working-directory]
#
# Environment:
#   SHEPHERD_POLL_SECONDS         seconds between GitHub reads while waiting (60)
#   SHEPHERD_MAX_STALLED_PASSES   passes in a row that change nothing on the PR
#                                 before stopping for human action (3)
#   SHEPHERD_MAX_WAIT_SECONDS     seconds the loop may wait with nothing to fix
#                                 since its last pass before stopping for human
#                                 action (7200; below shepherd-prs.sh's 4 h
#                                 per-PR timeout, so the loop stops itself)
#
# Exit: 0 merged or closed; 1 stopped for human action; 2 nothing left to fix
# but auto-merge is not armed.

set -euo pipefail

PR_NUMBER="${1:?Usage: shepherd-pr.sh <pr-number> [owner/repo] [working-directory]}"
REPO_SLUG="${2:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
OWNER="${REPO_SLUG%%/*}"
REPO="${REPO_SLUG#*/}"
WORKDIR="${3:-$PWD}"
WORKDIR="${WORKDIR%\"}"
WORKDIR="${WORKDIR#\"}"
POLL="${SHEPHERD_POLL_SECONDS:-60}"
MAX_STALLED="${SHEPHERD_MAX_STALLED_PASSES:-3}"
MAX_WAIT="${SHEPHERD_MAX_WAIT_SECONDS:-7200}"

if [ ! -d "$WORKDIR" ]; then
  echo "Error: working directory '$WORKDIR' does not exist" >&2
  exit 1
fi
for tool in gh jq claude; do
  if ! command -v "$tool" > /dev/null; then
    echo "Error: '$tool' is required and is not on PATH" >&2
    exit 1
  fi
done

echo "Shepherding PR #$PR_NUMBER in $OWNER/$REPO from $WORKDIR"

# Review threads across EVERY page, and the changes-requested reviews. Prints
# "<unresolved> <dismissable>": the unresolved threads, and the
# CHANGES_REQUESTED reviews none of whose threads is still open (each pass
# dismisses those). A value is ERROR when its query is unreadable.
thread_state() {
  local cursor_arg=(-F cursor=null) page count has_next cursor ids open_ids="," total=0
  local requested id dismissable=0
  while :; do
    # shellcheck disable=SC2016  # GraphQL variables, bound via -f/-F
    page=$(gh api graphql -f query='
      query($owner:String!, $repo:String!, $number:Int!, $cursor:String) {
        repository(owner:$owner, name:$repo) {
          pullRequest(number:$number) {
            reviewThreads(first:100, after:$cursor) {
              pageInfo { hasNextPage endCursor }
              nodes {
                isResolved
                comments(first:1) { nodes { pullRequestReview { databaseId } } }
              }
            }
          }
        }
      }
    ' -f owner="$OWNER" -f repo="$REPO" -F number="$PR_NUMBER" "${cursor_arg[@]}" \
      --jq '.data.repository.pullRequest.reviewThreads
            | [.nodes[] | select(.isResolved == false)] as $open
            | "\($open | length) \(.pageInfo.hasNextPage) \(.pageInfo.endCursor) ,\([$open[].comments.nodes[0].pullRequestReview.databaseId // empty | tostring] | join(",")),"') \
      || { echo "ERROR ERROR"; return 0; }
    read -r count has_next cursor ids <<<"$page"
    case "$count" in
      ''|*[!0-9]*) echo "ERROR ERROR"; return 0 ;;
    esac
    total=$((total + count))
    open_ids="$open_ids${ids#,}"
    [ "$has_next" = "true" ] || break
    cursor_arg=(-f cursor="$cursor")
  done

  # shellcheck disable=SC2016  # GraphQL variables, bound via -f/-F
  requested=$(gh api graphql -f query='
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner, name:$repo) {
        pullRequest(number:$number) {
          reviews(first:100, states:CHANGES_REQUESTED) { nodes { databaseId } }
        }
      }
    }
  ' -f owner="$OWNER" -f repo="$REPO" -F number="$PR_NUMBER" \
    --jq '[.data.repository.pullRequest.reviews.nodes[].databaseId | tostring] | join(" ")') \
    || { echo "$total ERROR"; return 0; }
  for id in $requested; do
    case "$open_ids" in
      *",$id,"*) ;;
      *) dismissable=$((dismissable + 1)) ;;
    esac
  done
  echo "$total $dismissable"
}

# Check state: PASS, FAIL <n>, PENDING <n>, or ERROR <why>. Only PASS is passing.
ci_state() {
  local out rc=0 failing pending
  out=$(gh pr checks "$PR_NUMBER" --repo "$OWNER/$REPO" --json bucket \
          --jq '[.[].bucket] | "\(map(select(. == "fail" or . == "cancel")) | length) \(map(select(. == "pending")) | length)"') || rc=$?
  if [ "$rc" -ne 0 ]; then
    printf 'ERROR %s\n' "$rc"
    return 0
  fi
  read -r failing pending <<<"$out"
  case "$failing$pending" in
    ''|*[!0-9]*) printf 'ERROR unparseable\n'; return 0 ;;
  esac
  if [ "$failing" -gt 0 ]; then
    printf 'FAIL %s\n' "$failing"
  elif [ "$pending" -gt 0 ]; then
    printf 'PENDING %s\n' "$pending"
  else
    printf 'PASS\n'
  fi
}

# One read of the PR: state, merge state, review decision, head, auto-merge, and
# whether a reviewer spoke after the last shepherd audit comment. A CodeRabbit
# conversation reply counts as a reviewer speaking; its PR summary and its
# acknowledgements of `@coderabbitai` commands do not. Tab-separated:
# state mergeState reviewDecision headOid autoMerge(yes/no) newActivity(yes/no)
pr_facts() {
  # shellcheck disable=SC2016  # $last and $activity are jq variables
  gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" \
    --json state,mergeStateStatus,reviewDecision,headRefOid,autoMergeRequest,comments,latestReviews \
    --jq '
      def isbot: (.author.login // "") | test("\\[bot\\]$|^coderabbitai|^github-actions");
      def iscr: (.author.login // "") | test("^coderabbitai");
      def crreply: iscr and ((.body | test("summarize by coderabbit\\.ai|review command invocation")) | not);
      ([.comments[] | select(.body | startswith("## Shepherd-PR Run")) | .createdAt] | max // "") as $last
      | ([.comments[] | select(((isbot | not) or crreply) and ((.body | startswith("## Shepherd-PR Run")) | not) and ((.body | startswith("@coderabbitai")) | not)) | .createdAt]
         + [.latestReviews[] | select(.state == "CHANGES_REQUESTED" or ((isbot | not) and (.body // "") != "")) | .submittedAt]
        ) as $activity
      | [ .state, (.mergeStateStatus // "UNKNOWN"), ((.reviewDecision // "") | if . == "" then "NONE" else . end),
          .headRefOid, (if .autoMergeRequest then "yes" else "no" end),
          (if ([$activity[] | select(. > $last)] | length) > 0 then "yes" else "no" end) ]
      | @tsv'
}

# Sleep one poll interval, counted against MAX_WAIT since the last pass; past
# it, stop with the reason the loop was waiting.
wait_or_stop() {
  if [ "$waited" -ge "$MAX_WAIT" ]; then
    echo "Stopping: waited ${waited}s since the last pass (limit ${MAX_WAIT}s) with nothing to fix, $1."
    echo "Human action required on PR #$PR_NUMBER."
    exit 1
  fi
  sleep "$POLL"
  waited=$((waited + POLL))
}

stalled=0
pass=0
waited=0
while :; do
  if ! facts=$(pr_facts); then
    echo "$(date -u +%FT%TZ) could not read the PR; retrying in ${POLL}s"
    wait_or_stop "the PR could not be read"
    continue
  fi
  IFS=$'\t' read -r state merge_state decision head_oid auto_merge new_activity <<<"$facts"

  case "$state" in
    MERGED) echo "$(date -u +%FT%TZ) PR #$PR_NUMBER is MERGED."; exit 0 ;;
    CLOSED) echo "$(date -u +%FT%TZ) PR #$PR_NUMBER is CLOSED without merging."; exit 0 ;;
  esac

  read -r unresolved dismissable <<<"$(thread_state)"
  checks=$(ci_state)
  echo "$(date -u +%FT%TZ) state=$state merge=$merge_state review=$decision threads=$unresolved resolved-change-requests=$dismissable checks=$checks auto-merge=$auto_merge new-activity=$new_activity"

  reasons=""
  case "$checks" in FAIL*) reasons="$reasons failing-checks" ;; esac
  case "$unresolved" in ERROR|0) ;; *) reasons="$reasons unresolved-threads" ;; esac
  if [ "$decision" = "CHANGES_REQUESTED" ]; then
    case "$dismissable" in ERROR|0) ;; *) reasons="$reasons changes-requested-review-to-dismiss" ;; esac
  fi
  case "$merge_state" in
    DIRTY)  reasons="$reasons merge-conflict" ;;
    BEHIND) reasons="$reasons behind-base" ;;
  esac
  [ "$new_activity" = "yes" ] && reasons="$reasons reviewer-activity"

  if [ -z "$reasons" ]; then
    if [ "$checks" = "PASS" ] && [ "$unresolved" = "0" ] && [ "$auto_merge" = "no" ]; then
      echo "Nothing left to fix and checks pass, but GitHub auto-merge is NOT armed on PR #$PR_NUMBER."
      echo "This loop never merges. Arm auto-merge (the owner's action) and the PR will merge."
      exit 2
    else
      case "$checks" in
        PENDING*) waiting_on="waiting on pending checks" ;;
        PASS)     waiting_on="waiting on GitHub auto-merge (merge state $merge_state)" ;;
        *)        waiting_on="checks or threads unreadable (checks=$checks threads=$unresolved)" ;;
      esac
    fi
    wait_or_stop "$waiting_on"
    continue
  fi

  pass=$((pass + 1))
  waited=0
  before="$head_oid|$unresolved $dismissable|$decision|$merge_state|$checks|$new_activity"
  echo "--- pass $pass:$reasons ---"
  prompt="/agent-teams-workforce:fix-pr ${PR_NUMBER} ${OWNER}/${REPO} \"${WORKDIR}\""
  rc=0
  (cd "$WORKDIR" && printf '%s' "$prompt" \
    | env -u CLAUDECODE SHEPHERD_PR_PASS=1 CI=1 TERM=dumb NO_COLOR=1 \
        claude --print --permission-mode bypassPermissions \
          --settings '{"permissions":{"deny":["Bash(gh pr merge:*)","Bash(gh pr merge)"]}}') || rc=$?
  echo "--- pass $pass ended (exit $rc) ---"

  if after_facts=$(pr_facts); then
    IFS=$'\t' read -r _s a_merge a_decision a_head _a a_new <<<"$after_facts"
    after="$a_head|$(thread_state)|$a_decision|$a_merge|$(ci_state)|$a_new"
  else
    after="unreadable"
  fi
  if [ "$before" = "$after" ]; then
    stalled=$((stalled + 1))
    echo "Pass $pass changed nothing on the PR ($stalled of $MAX_STALLED in a row)."
  else
    stalled=0
  fi
  if [ "$stalled" -ge "$MAX_STALLED" ]; then
    echo "Stopping: $MAX_STALLED passes in a row changed nothing. Human action required on PR #$PR_NUMBER"
    echo "(read the latest '## Shepherd-PR Run' audit comment and any escalation issue it links)."
    exit 1
  fi
  # Give CI and GitHub a moment to register what the pass pushed.
  sleep "$POLL"
done
