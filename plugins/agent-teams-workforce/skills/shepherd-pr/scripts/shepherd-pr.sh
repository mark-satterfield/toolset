#!/usr/bin/env bash
# shepherd-pr.sh — the shepherd-pr skill's loop.
#
# Follows ONE pull request until GitHub reports it MERGED or CLOSED. Every
# iteration re-reads the PR from GitHub and decides from that alone:
#
#   something to fix  -> start one headless pass session (SKILL.md, Mode B)
#   checks pending, or nothing to fix and auto-merge armed -> wait, poll again
#   nothing to fix, checks passing, auto-merge NOT armed   -> exit 2
#   MERGED or CLOSED                                       -> exit 0
#
# "Something to fix" is: a failing or cancelled check, an unresolved review
# thread, a merge conflict (DIRTY), a branch behind its base (BEHIND), or a
# reviewer comment / changes-requested review newer than the last pass's audit
# comment.
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
#   SHEPHERD_CR_MAX_REQUESTS      "@coderabbitai review" re-requests this loop may
#                                 post on the PR before it stops as stuck on
#                                 CodeRabbit (3)
#   SHEPHERD_CR_SILENCE_SECONDS   seconds CodeRabbit may stay silent (no status, no
#                                 comment since the last push or the last request)
#                                 before the loop re-requests a review (900)
#   SHEPHERD_CR_MARGIN_SECONDS    seconds added to CodeRabbit's rate-limit wait (60)
#
# CodeRabbit never retries a review by itself. When every other check has
# passed and the CodeRabbit status is missing or pending, the loop posts
# "@coderabbitai review" after a "Rate Limit Exceeded" reply's wait has expired,
# or after CR_SILENCE seconds of silence; never while a review is in progress.
#
# Exit: 0 merged or closed; 1 stopped for human action (including stuck on
# CodeRabbit); 2 nothing left to fix but auto-merge is not armed.

set -euo pipefail

CR_MAX_REQUESTS="${SHEPHERD_CR_MAX_REQUESTS:-3}"
CR_SILENCE="${SHEPHERD_CR_SILENCE_SECONDS:-900}"
CR_MARGIN="${SHEPHERD_CR_MARGIN_SECONDS:-60}"

PR_NUMBER="${1:?Usage: shepherd-pr.sh <pr-number> [owner/repo] [working-directory]}"
REPO_SLUG="${2:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
OWNER="${REPO_SLUG%%/*}"
REPO="${REPO_SLUG#*/}"
WORKDIR="${3:-$PWD}"
WORKDIR="${WORKDIR%\"}"
WORKDIR="${WORKDIR#\"}"
POLL="${SHEPHERD_POLL_SECONDS:-60}"
MAX_STALLED="${SHEPHERD_MAX_STALLED_PASSES:-3}"

# The skill's own directory (this script lives in <skill>/scripts/). Each pass
# session reads SKILL.md from here, so the loop works from any repository and
# from either the plugin copy or a project copy of the skill.
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

echo "Shepherding PR #$PR_NUMBER in $OWNER/$REPO from $WORKDIR (skill: $SKILL_DIR)"

# Unresolved review threads across EVERY page; ERROR when any page is unreadable.
unresolved_count() {
  local cursor_arg=(-F cursor=null) page count has_next cursor total=0
  while :; do
    # shellcheck disable=SC2016  # GraphQL variables, bound via -f/-F
    page=$(gh api graphql -f query='
      query($owner:String!, $repo:String!, $number:Int!, $cursor:String) {
        repository(owner:$owner, name:$repo) {
          pullRequest(number:$number) {
            reviewThreads(first:100, after:$cursor) {
              pageInfo { hasNextPage endCursor }
              nodes { isResolved }
            }
          }
        }
      }
    ' -f owner="$OWNER" -f repo="$REPO" -F number="$PR_NUMBER" "${cursor_arg[@]}" \
      --jq '.data.repository.pullRequest.reviewThreads
            | "\([.nodes[] | select(.isResolved == false)] | length) \(.pageInfo.hasNextPage) \(.pageInfo.endCursor)"') \
      || { echo "ERROR"; return 0; }
    read -r count has_next cursor <<<"$page"
    case "$count" in
      ''|*[!0-9]*) echo "ERROR"; return 0 ;;
    esac
    total=$((total + count))
    [ "$has_next" = "true" ] || break
    cursor_arg=(-f cursor="$cursor")
  done
  echo "$total"
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
# whether a reviewer spoke after the last shepherd audit comment. Tab-separated:
# state mergeState reviewDecision headOid autoMerge(yes/no) newActivity(yes/no)
pr_facts() {
  # shellcheck disable=SC2016  # $last and $activity are jq variables
  gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" \
    --json state,mergeStateStatus,reviewDecision,headRefOid,autoMergeRequest,comments,latestReviews \
    --jq '
      def isbot: (.author.login // "") | test("\\[bot\\]$|^coderabbitai|^github-actions");
      ([.comments[] | select(.body | startswith("## Shepherd-PR Run")) | .createdAt] | max // "") as $last
      | ([.comments[] | select((isbot | not) and ((.body | startswith("## Shepherd-PR Run")) | not) and ((.body | startswith("@coderabbitai")) | not)) | .createdAt]
         + [.latestReviews[] | select(.state == "CHANGES_REQUESTED" or ((isbot | not) and (.body // "") != "")) | .submittedAt]
        ) as $activity
      | [ .state, (.mergeStateStatus // "UNKNOWN"), ((.reviewDecision // "") | if . == "" then "NONE" else . end),
          .headRefOid, (if .autoMergeRequest then "yes" else "no" end),
          (if ([$activity[] | select(. > $last)] | length) > 0 then "yes" else "no" end) ]
      | @tsv'
}

# CodeRabbit status and the other checks: "<status> <others-passed>", where
# status is missing, pending, pass, fail, cancel or skipping, and others-passed
# is yes when no other check is failing, cancelled or pending. ERROR when unread.
# gh exits 8 while checks are pending; its JSON is still complete.
coderabbit_checks() {
  local out rc=0
  # shellcheck disable=SC2016  # $cr and $other are jq variables
  out=$(gh pr checks "$PR_NUMBER" --repo "$OWNER/$REPO" --json name,bucket \
          --jq '([.[] | select((.name | ascii_downcase) == "coderabbit") | .bucket] | first // "missing") as $cr
                | ([.[] | select((.name | ascii_downcase) != "coderabbit")
                        | select(.bucket == "fail" or .bucket == "cancel" or .bucket == "pending")] | length) as $other
                | "\($cr) \(if $other == 0 then "yes" else "no" end)"') || rc=$?
  if { [ "$rc" -ne 0 ] && [ "$rc" -ne 8 ]; } || [ -z "$out" ]; then
    echo "ERROR"
    return 0
  fi
  echo "$out"
}

# CodeRabbit's conversation on the PR, as epoch seconds (0 when absent),
# space-separated: latestKind(ratelimit/other/none) rateLimitWaitSeconds
# latestCommentAt lastActivityAt lastRequestAt headCommitAt.
coderabbit_comments() {
  # shellcheck disable=SC2016  # $c, $rl, $t, $wait, $last and $req are jq variables
  gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json comments,reviews,commits --jq '
    def iscr: (.author.login // "") | test("^coderabbit");
    def epoch: if . == null or . == "" then 0 else fromdateiso8601 end;
    ([.comments[] | select(iscr)] | sort_by(.createdAt) | last) as $c
    | (($c.body // "") | test("rate limit exceeded"; "i")) as $rl
    | (if $rl then ($c.body | capture("(?i)wait\\W+(?<t>[^.\\n]*)").t // "") else "" end) as $t
    | ((($t | capture("(?<n>[0-9]+) hour").n) // "0" | tonumber) * 3600
       + (($t | capture("(?<n>[0-9]+) minute").n) // "0" | tonumber) * 60
       + (($t | capture("(?<n>[0-9]+) second").n) // "0" | tonumber)) as $wait
    | ([.comments[] | select(iscr) | .createdAt] + [.reviews[] | select(iscr) | .submittedAt] | max) as $last
    | ([.comments[] | select((iscr | not) and (.body | startswith("@coderabbitai review"))) | .createdAt] | max) as $req
    | [ (if $c == null then "none" elif $rl then "ratelimit" else "other" end),
        $wait, ($c.createdAt | epoch), ($last | epoch), ($req | epoch),
        (.commits | last | .committedDate | epoch) ]
    | map(tostring) | join(" ")'
}

# Re-request a CodeRabbit review when CodeRabbit is the only thing left and it
# will not come by itself. Exits 1 when the request cap is spent.
cr_requests=0
cr_head=""
cr_since=0
coderabbit_nudge() {
  local cr others facts kind wait_s c_at cr_last req_at head_at now due why
  read -r cr others <<<"$(coderabbit_checks)"
  [ "$others" = "yes" ] || return 0
  case "$cr" in missing|pending) ;; *) return 0 ;; esac
  facts=$(coderabbit_comments) || return 0
  read -r kind wait_s c_at cr_last req_at head_at <<<"$facts"
  case "$wait_s$c_at$cr_last$req_at$head_at" in ''|*[!0-9]*) return 0 ;; esac
  # A review in progress: never interrupt it.
  if [ "$cr" = "pending" ] && [ "$kind" != "ratelimit" ]; then
    return 0
  fi
  now=$(date +%s)
  if [ "$req_at" -gt "$cr_last" ]; then
    due=$((req_at + CR_SILENCE)); why="no answer to the last review request"
  elif [ "$kind" = "ratelimit" ]; then
    [ "$wait_s" -gt 0 ] || wait_s=$CR_SILENCE
    due=$((c_at + wait_s + CR_MARGIN)); why="rate limit (${wait_s}s + ${CR_MARGIN}s)"
  elif [ "$cr" = "missing" ] && [ "$cr_last" -lt "$head_at" ]; then
    if [ "$cr_head" != "$head_oid" ]; then
      cr_head="$head_oid"
      cr_since="$now"
    fi
    due=$((cr_since + CR_SILENCE)); why="silent since the last push"
  else
    return 0
  fi
  if [ "$now" -lt "$due" ]; then
    echo "CodeRabbit: $why; re-request in $((due - now))s"
    return 0
  fi
  if [ "$cr_requests" -ge "$CR_MAX_REQUESTS" ]; then
    echo "Stopping: PR #$PR_NUMBER is stuck on CodeRabbit ($why) after $cr_requests review re-requests."
    echo "Every other check passed. Human action required (check CodeRabbit's status and its latest comment)."
    exit 1
  fi
  if gh pr comment "$PR_NUMBER" --repo "$OWNER/$REPO" --body "@coderabbitai review"; then
    cr_requests=$((cr_requests + 1))
    echo "CodeRabbit: $why; posted '@coderabbitai review' ($cr_requests of $CR_MAX_REQUESTS)"
  else
    echo "CodeRabbit: could not post the review request; retrying next poll"
  fi
}

stalled=0
pass=0
while :; do
  if ! facts=$(pr_facts); then
    echo "$(date -u +%FT%TZ) could not read the PR; retrying in ${POLL}s"
    sleep "$POLL"
    continue
  fi
  IFS=$'\t' read -r state merge_state decision head_oid auto_merge new_activity <<<"$facts"

  case "$state" in
    MERGED) echo "$(date -u +%FT%TZ) PR #$PR_NUMBER is MERGED."; exit 0 ;;
    CLOSED) echo "$(date -u +%FT%TZ) PR #$PR_NUMBER is CLOSED without merging."; exit 0 ;;
  esac

  unresolved=$(unresolved_count)
  checks=$(ci_state)
  echo "$(date -u +%FT%TZ) state=$state merge=$merge_state review=$decision threads=$unresolved checks=$checks auto-merge=$auto_merge new-activity=$new_activity"

  reasons=""
  case "$checks" in FAIL*) reasons="$reasons failing-checks" ;; esac
  case "$unresolved" in ERROR|0) ;; *) reasons="$reasons unresolved-threads" ;; esac
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
    fi
    coderabbit_nudge
    sleep "$POLL"
    continue
  fi

  pass=$((pass + 1))
  before="$head_oid|$unresolved|$decision|$merge_state|$checks|$new_activity"
  echo "--- pass $pass:$reasons ---"
  prompt="You are a shepherd-pr pass session (SHEPHERD_PR_PASS=1). Read the skill at ${SKILL_DIR}/SKILL.md and make exactly ONE pass in Mode B (Phases 1 to 6), then stop.
Pull request: ${OWNER}/${REPO}#${PR_NUMBER}. Arguments: ${PR_NUMBER} ${OWNER}/${REPO} \"${WORKDIR}\".
Pass --repo ${OWNER}/${REPO} to every gh command. Run every git operation in \"${WORKDIR}\".
GitHub currently reports:${reasons}. Fix all of it.
Never merge (no gh pr merge, no --admin), never loosen lint or type configuration, never weaken, skip or delete a test, never edit a workflow to make a check pass, never use --no-verify."
  rc=0
  (cd "$WORKDIR" && printf '%s' "$prompt" \
    | env -u CLAUDECODE SHEPHERD_PR_PASS=1 CI=1 TERM=dumb NO_COLOR=1 \
        claude --print --permission-mode bypassPermissions \
          --settings '{"permissions":{"deny":["Bash(gh pr merge:*)","Bash(gh pr merge)"]}}' \
          --add-dir "$SKILL_DIR") || rc=$?
  echo "--- pass $pass ended (exit $rc) ---"

  if after_facts=$(pr_facts); then
    IFS=$'\t' read -r _s a_merge a_decision a_head _a a_new <<<"$after_facts"
    after="$a_head|$(unresolved_count)|$a_decision|$a_merge|$(ci_state)|$a_new"
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
