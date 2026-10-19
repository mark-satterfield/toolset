#!/usr/bin/env bash
# shepherd-pr.sh — the shepherd-pr skill's loop.
#
# Works through the issues on ONE pull request until the PR qualifies for
# merging, or until it cannot fix what is left. Every iteration re-reads the
# PR from GitHub and decides from that alone:
#
#   MERGED or CLOSED            -> ends, exit 0
#   something to fix            -> start one headless pass session (/agent-teams-workforce:fix-pr)
#   qualifies for merging       -> ends, exit 0
#   checks running, or nothing  -> wait, poll again
#   the shepherd can act on
#   nothing new for MAX_STALLED -> ends, exit 2, naming what is still unfixed
#   passes in a row, or not
#   qualified past MAX_WAIT
#
# "Nothing new" for a pass: the open review threads that are not repeats of
# a thread already addressed (the pass records its repeats in
# $SHEPHERD_REPEATS_FILE), and the names of the failing checks, are the same
# as when the previous pass started. A thread fixed in code, or answered with
# a reasoned decline and resolved, is addressed and leaves the set: that is
# progress even with no commit. A finding raised again after it was
# addressed is a repeat, not new. A fix that makes a different check fail,
# or a genuinely new thread, is new. The head commit, the review decision and
# the merge state are not part of it.
#
# "Qualifies for merging" is GitHub's own merge requirement facts: nothing
# below is left to fix, no review decision of CHANGES_REQUESTED, no unresolved
# review thread, every required check passed, and a merge state of CLEAN,
# HAS_HOOKS or UNSTABLE (GitHub reports BEHIND only when the repository
# requires the branch to be current, and BLOCKED while a requirement is unmet).
#
# "Something to fix" is: a failing or cancelled check, an unresolved review
# thread, a merge conflict (DIRTY), a branch behind its base (BEHIND), a review
# decision of CHANGES_REQUESTED with a changes-requested review none of whose
# threads is still open (the pass dismisses it), or a reviewer comment,
# CodeRabbit reply or changes-requested review newer than the last pass's
# audit comment.
#
# MERGE: merging and closing are not the shepherd's job. The loop never
# merges, and does not wait for a merge. Every pass session runs with a deny
# rule on `Bash(gh pr merge:*)`.
#
# Each pass session loads the plugin this script belongs to (--plugin-dir), so
# the fix-pr command exists whatever repository the PR's worktree is in. Each
# pass's full stream-json output is kept in the log directory, and the loop's
# own lines are copied to loop.log there.
#
# Usage: shepherd-pr.sh <pr-number> [owner/repo] [working-directory]
#
# Environment:
#   SHEPHERD_POLL_SECONDS         seconds between GitHub reads while waiting (60)
#   SHEPHERD_MAX_STALLED_PASSES   passes in a row with nothing new (see above)
#                                 before the shepherd ends as unable to fix the
#                                 PR (3)
#   SHEPHERD_MAX_WAIT_SECONDS     seconds the loop may wait, since its last pass,
#                                 for a PR that does not qualify for merging and
#                                 has nothing the shepherd can act on, before it
#                                 ends as unable to fix the PR (7200; below
#                                 shepherd-prs.sh's 4 h per-PR timeout)
#   SHEPHERD_LOG_DIR              where loop.log, pass-<n>.jsonl, the repeat
#                                 records repeats-pass-<n>.tsv and ending are
#                                 written
#                                 (${CLAUDE_CONFIG_DIR:-~/.claude}/shepherd-pr/<owner>-<repo>-<pr>)
#
# Exit status:
#   0  the job is done: the PR qualifies for merging, or it is already merged
#      or closed
#   1  the shepherd could not start (bad arguments, a missing tool, not the
#      plugin root)
#   2  the shepherd could not fix the PR: what is still unfixed is printed
# The same ending is written as one tab-separated line, "<exit> <outcome>
# <message>", to $SHEPHERD_LOG_DIR/ending, where outcome is qualifies,
# merged, closed or could-not-fix; a caller that cannot see the exit status
# reads it there.

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
PLUGIN_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
LOG_DIR="${SHEPHERD_LOG_DIR:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/shepherd-pr/$OWNER-$REPO-$PR_NUMBER}"
FIX_COMMAND="agent-teams-workforce:fix-pr"

if [ ! -d "$WORKDIR" ]; then
  echo "Error: working directory '$WORKDIR' does not exist" >&2
  exit 1
fi
if [ ! -f "$PLUGIN_ROOT/commands/fix-pr.md" ]; then
  echo "Error: '$PLUGIN_ROOT' is not the agent-teams-workforce plugin root (no commands/fix-pr.md)" >&2
  exit 1
fi
for tool in gh jq claude; do
  if ! command -v "$tool" > /dev/null; then
    echo "Error: '$tool' is required and is not on PATH" >&2
    exit 1
  fi
done
mkdir -p "$LOG_DIR"
ENDING_FILE="$LOG_DIR/ending"
rm -f "$ENDING_FILE"
exec > >(tee -a "$LOG_DIR/loop.log") 2>&1

echo "Shepherding PR #$PR_NUMBER in $OWNER/$REPO from $WORKDIR"
echo "Plugin: $PLUGIN_ROOT  Logs: $LOG_DIR"

# Review threads across EVERY page, and the changes-requested reviews. Prints
# "<unresolved> <dismissable> <open-thread-ids>": the unresolved threads, the
# CHANGES_REQUESTED reviews none of whose threads is still open (each pass
# dismisses those), and the node ids of the unresolved threads as ",id,id,".
# A value is ERROR when its query is unreadable.
thread_state() {
  local cursor_arg=(-F cursor=null) page count has_next cursor ids tids open_ids="," open_tids="," total=0
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
                id
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
            | "\($open | length) \(.pageInfo.hasNextPage) \(.pageInfo.endCursor) ,\([$open[].comments.nodes[0].pullRequestReview.databaseId // empty | tostring] | join(",")), ,\([$open[].id] | join(",")),"') \
      || { echo "ERROR ERROR ERROR"; return 0; }
    read -r count has_next cursor ids tids <<<"$page"
    case "$count" in
      ''|*[!0-9]*) echo "ERROR ERROR ERROR"; return 0 ;;
    esac
    total=$((total + count))
    open_ids="$open_ids${ids#,}"
    open_tids="$open_tids${tids#,}"
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
    || { echo "$total ERROR $open_tids"; return 0; }
  for id in $requested; do
    case "$open_ids" in
      *",$id,"*) ;;
      *) dismissable=$((dismissable + 1)) ;;
    esac
  done
  echo "$total $dismissable $open_tids"
}

# The names of the checks failing (fail or cancel), sorted, one per line;
# ERROR when the checks cannot be read.
failing_check_names() {
  gh pr checks "$PR_NUMBER" --repo "$OWNER/$REPO" --json name,bucket \
    --jq '[.[] | select(.bucket == "fail" or .bucket == "cancel") | .name] | unique | .[]' \
    || echo ERROR
}

# The node ids in a ",id,id," list ($1) that are not in the first column of
# the repeat record $2: the open threads that are not repeats of a thread
# already addressed. Printed sorted, comma-separated.
non_repeat_threads() {
  local current="$1" record="$2" id first repeat kept=()
  local IFS=,
  for id in $current; do
    [ -n "$id" ] || continue
    repeat=no
    if [ -s "$record" ]; then
      while IFS=$'\t' read -r first _; do
        [ "$first" = "$id" ] && repeat=yes
      done < "$record"
    fi
    [ "$repeat" = yes ] || kept+=("$id")
  done
  [ "${#kept[@]}" -gt 0 ] || return 0
  printf '%s\n' "${kept[@]}" | sort | paste -sd, -
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

# Required check state: PASS (every required check passed or was skipped, or
# the repository requires none), PENDING <n>, FAIL <n>, or ERROR <why>.
required_state() {
  local out rc=0 failing pending
  out=$(gh pr checks "$PR_NUMBER" --repo "$OWNER/$REPO" --required --json bucket \
          --jq '[.[].bucket] | "\(map(select(. == "fail" or . == "cancel")) | length) \(map(select(. == "pending")) | length)"' 2>&1) || rc=$?
  if [ "$rc" -ne 0 ]; then
    case "$out" in
      *"no required checks"*) printf 'PASS\n' ;;
      *) printf 'ERROR %s\n' "$rc" ;;
    esac
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

# One read of the PR: state, merge state, review decision, head, and whether
# a reviewer spoke after the last shepherd audit comment. A CodeRabbit
# conversation reply, and any review with a body (a CodeRabbit review
# body carries its outside-diff findings, which have no thread), count as a
# reviewer speaking; CodeRabbit's PR summary and its acknowledgements of
# `@coderabbitai` commands do not. Tab-separated:
# state mergeState reviewDecision headOid newActivity(yes/no)
pr_facts() {
  # shellcheck disable=SC2016  # $last and $activity are jq variables
  gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" \
    --json state,mergeStateStatus,reviewDecision,headRefOid,comments,reviews \
    --jq '
      def isbot: (.author.login // "") | test("\\[bot\\]$|^coderabbitai|^github-actions");
      def iscr: (.author.login // "") | test("^coderabbitai");
      def crreply: iscr and ((.body | test("summarize by coderabbit\\.ai|review command invocation")) | not);
      ([.comments[] | select(.body | startswith("## Shepherd-PR Run")) | .createdAt] | max // "") as $last
      | ([.comments[] | select(((isbot | not) or crreply) and ((.body | startswith("## Shepherd-PR Run")) | not) and ((.body | startswith("@coderabbitai")) | not)) | .createdAt]
         + [.reviews[] | select(.state == "CHANGES_REQUESTED" or (((isbot | not) or iscr) and (.body // "") != "")) | .submittedAt]
        ) as $activity
      | [ .state, (.mergeStateStatus // "UNKNOWN"), ((.reviewDecision // "") | if . == "" then "NONE" else . end),
          .headRefOid,
          (if ([$activity[] | select(. > $last)] | length) > 0 then "yes" else "no" end) ]
      | @tsv'
}

# Summarise one pass's stream-json log: whether the fix-pr command was loaded,
# how many tools the pass called, and its final result line.
pass_summary() {
  local log="$1" loaded tools result
  loaded=$(jq -r --arg cmd "$FIX_COMMAND" 'select(.type == "system" and .subtype == "init")
            | if ([.slash_commands[]? | select(. == $cmd)] | length) > 0 then "yes" else "NO" end' "$log" | head -n 1)
  tools=$(jq -s '[.[] | select(.type == "assistant") | .message.content[]? | select(.type == "tool_use")] | length' "$log")
  result=$(jq -r 'select(.type == "result") | "\(.subtype) is_error=\(.is_error) turns=\(.num_turns): \(.result // "" | gsub("\n"; " ") | .[0:300])"' "$log" | tail -n 1)
  echo "pass $pass: fix-pr loaded=${loaded:-unknown} tool-calls=$tools result=${result:-none} log=$log"
  if [ "$loaded" != "yes" ] || [ "$tools" = "0" ]; then
    echo "WARNING: pass $pass did no work (fix-pr loaded=${loaded:-unknown}, tool-calls=$tools). Read $log"
  fi
}

# End the shepherd: print the message, record the ending for a caller, exit.
finish() {
  local code="$1" outcome="$2" message="$3"
  echo "$(date -u +%FT%TZ) $message"
  printf '%s\t%s\t%s\n' "$code" "$outcome" "$message" > "$ENDING_FILE"
  exit "$code"
}

# Sleep one poll interval, counted against MAX_WAIT since the last pass; past
# it, end as unable to fix the PR, naming what the loop was waiting on.
wait_or_stop() {
  if [ "$waited" -ge "$MAX_WAIT" ]; then
    finish 2 could-not-fix "PR #$PR_NUMBER does not qualify for merging after ${waited}s since the last pass (limit ${MAX_WAIT}s) with nothing the shepherd can act on; still waiting on: $1."
  fi
  sleep "$POLL"
  waited=$((waited + POLL))
}

stalled=0
pass=0
waited=0
prev_threads=""
prev_failing=""
while :; do
  if ! facts=$(pr_facts); then
    echo "$(date -u +%FT%TZ) could not read the PR; retrying in ${POLL}s"
    wait_or_stop "the PR could not be read"
    continue
  fi
  IFS=$'\t' read -r state merge_state decision _ new_activity <<<"$facts"

  case "$state" in
    MERGED) finish 0 merged "PR #$PR_NUMBER is MERGED." ;;
    CLOSED) finish 0 closed "PR #$PR_NUMBER is CLOSED." ;;
  esac

  read -r unresolved dismissable open_threads <<<"$(thread_state)"
  checks=$(ci_state)
  echo "$(date -u +%FT%TZ) state=$state merge=$merge_state review=$decision threads=$unresolved resolved-change-requests=$dismissable checks=$checks new-activity=$new_activity"

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
    required=$(required_state)
    waiting_on=""
    case "$required" in
      PASS) ;;
      PENDING*) waiting_on="$waiting_on, required checks still running (${required#PENDING })" ;;
      *)        waiting_on="$waiting_on, required checks $required" ;;
    esac
    case "$unresolved" in
      0) ;;
      *) waiting_on="$waiting_on, review threads unreadable" ;;
    esac
    [ "$decision" = "CHANGES_REQUESTED" ] && waiting_on="$waiting_on, review decision CHANGES_REQUESTED"
    case "$merge_state" in
      CLEAN|HAS_HOOKS|UNSTABLE) ;;
      *) waiting_on="$waiting_on, merge state $merge_state (review decision $decision)" ;;
    esac
    if [ -z "$waiting_on" ]; then
      finish 0 qualifies "PR #$PR_NUMBER qualifies for merging (merge state $merge_state, required checks passed, no unresolved threads, review decision $decision)."
    fi
    wait_or_stop "${waiting_on#, }"
    continue
  fi

  pass=$((pass + 1))
  waited=0
  start_failing=$(failing_check_names)
  repeats_file="$LOG_DIR/repeats-pass-$pass.tsv"
  : > "$repeats_file"
  echo "--- pass $pass:$reasons ---"
  prompt="/${FIX_COMMAND} ${PR_NUMBER} ${OWNER}/${REPO} \"${WORKDIR}\""
  pass_log="$LOG_DIR/pass-$(date -u +%Y%m%dT%H%M%SZ)-$pass.jsonl"
  rc=0
  (cd "$WORKDIR" && printf '%s' "$prompt" \
    | env -u CLAUDECODE SHEPHERD_PR_PASS=1 SHEPHERD_REPEATS_FILE="$repeats_file" CI=1 TERM=dumb NO_COLOR=1 \
        claude --print --plugin-dir "$PLUGIN_ROOT" --permission-mode bypassPermissions \
          --output-format stream-json --verbose \
          --settings '{"permissions":{"deny":["Bash(gh pr merge:*)","Bash(gh pr merge)"]}}' \
          > "$pass_log") || rc=$?
  echo "--- pass $pass ended (exit $rc) ---"
  pass_summary "$pass_log"

  # Nothing changed since the previous pass: the open threads that are not
  # repeats of an already-addressed thread, and the failing checks by name,
  # are the same as when the previous pass started. A thread the previous
  # pass fixed, or answered with a reasoned decline, is resolved and leaves
  # the set, so that pass counts as progress even without a commit.
  repeats=0
  [ -s "$repeats_file" ] && repeats=$(grep -c . "$repeats_file")
  start_threads=$(non_repeat_threads "$open_threads" "$repeats_file")
  failing_list=$(printf '%s' "$start_failing" | paste -sd, -)
  prev_failing_list=$(printf '%s' "$prev_failing" | paste -sd, -)
  if [ "$pass" -eq 1 ] || [ "$open_threads" = "ERROR" ] || [ "$start_failing" = "ERROR" ]; then
    stalled=0
  elif [ "$start_threads" = "$prev_threads" ] && [ "$start_failing" = "$prev_failing" ]; then
    stalled=$((stalled + 1))
    echo "Pass $pass: nothing changed since the previous pass: the same open threads apart from $repeats repeat(s) of threads already addressed (${start_threads:-none}), and the same checks fail (${failing_list:-none}) ($stalled of $MAX_STALLED in a row)."
  else
    stalled=0
    echo "Pass $pass: changed since the previous pass: open non-repeat threads ${prev_threads:-none} -> ${start_threads:-none}; failing checks ${prev_failing_list:-none} -> ${failing_list:-none}."
  fi
  prev_threads="$start_threads"
  prev_failing="$start_failing"
  if [ "$stalled" -ge "$MAX_STALLED" ]; then
    finish 2 could-not-fix "PR #$PR_NUMBER does not qualify for merging: $MAX_STALLED passes in a row found nothing changed (the same open threads apart from repeats of threads already addressed, and the same checks failing: ${failing_list:-none}); the passes made every fix they could and decided the rest cannot or should not change. Still unfixed:${reasons}. The latest '## Shepherd-PR Run' audit comment on the PR records each pass."
  fi
  # Give CI and GitHub a moment to register what the pass pushed.
  sleep "$POLL"
done
