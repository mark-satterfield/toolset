export const meta = {
  name: 'settle',
  description:
    'Lands a worktree in git: commits, pushes the branch and opens the pull request with the project PR command. With commitOnly it commits on the branch and stops: no push, no pull request. Returns { status }: not-applicable (no tree), blocked (no PR command), error (the landing agent failed), or reported (treeClean, hasWork, branch, prUrl, commit, blocked).',
  phases: [{ title: 'Settle', detail: 'commit, push and open the pull request' }],
}
// BEGIN bounded dispatch policy — identical in workflow consumers (no runtime imports).
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
}
function dispatchPolicy(options) {
  const input = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  const policy = (options && options.retryPolicy) || input.retryPolicy || {}
  return { maxAttempts: Number.isInteger(policy.maxAttempts) && policy.maxAttempts > 0 ? policy.maxAttempts : 3,
    maxWaitMs: Number.isFinite(policy.maxWaitMs) && policy.maxWaitMs >= 0 ? policy.maxWaitMs : 300000 }
}
function dispatchFailureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = [e.message || err || '', e.type, e.code, e.error && e.error.type].join(' ')
  if (/structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i.test(text)) return 'deterministic'
  if (/insufficient_quota|quota|usage[ _-]?limit|spend[ _-]?limit|session[ _-]?limit|credit balance|out of credits|hit your limit|token limit|account.quota.exhausted/i.test(text)) return 'exhausted'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((value) => Number(value)).find((value) => Number.isFinite(value) && value >= 100 && value < 600)
  return [408, 425, 429, 500, 502, 503, 504, 529].includes(status) || /overload|rate[ _-]?limit|too many requests|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i.test(text) ? 'transient' : 'deterministic'
}
function dispatchRetry(err, name, attempt, waitedMs, policy, canWait) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return { retry: false, cause }
  const e = err && typeof err === 'object' ? err : {}
  const headers = e.headers || (e.response && e.response.headers) || {}
  const rawRetryAfter = e.retryAfter !== undefined ? e.retryAfter : headers['retry-after']
  const retryAfter = e.retryAfterMs !== undefined ? Number(e.retryAfterMs) : Number(rawRetryAfter) * 1000
  // An HTTP-date without a supplied clock cannot be safely shortened to our backoff.
  const unknownRetryDate = rawRetryAfter !== undefined && !Number.isFinite(retryAfter)
  let hash = 2166136261
  for (const ch of `${name}#${attempt}`) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619)
  const scheduled = Math.round(Math.min(300000, 5000 * Math.pow(3, attempt - 1)) * (0.5 + 0.5 * ((hash >>> 0) / 4294967296)))
  const wait = Math.max(scheduled, Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : 0)
  if (cause === 'transient' && !unknownRetryDate && canWait && attempt < policy.maxAttempts && waitedMs + wait <= policy.maxWaitMs) return { retry: true, cause, wait }
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  return { retry: false, cause, interruption: { stage, message: `${stage}: ${name}: ${String(e.message || err || cause)}`, attempt,
    retryAfterMs: Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : null, retryAfter: rawRetryAfter || null } }
}
async function settleWorkflow(name, input) {
  if (dispatchInterruption) return dispatchOutcome({})
  const source = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  try {
    const out = await workflow(name, { ...input, ...(source.retryPolicy && !(input && input.retryPolicy) ? { retryPolicy: source.retryPolicy } : {}) })
    if (out && out.paused && out.resumable && out.dispatchInterruption) dispatchInterruption = out.dispatchInterruption
    return out
  } catch (err) {
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(null), false)
    if (!plan.interruption) throw err
    dispatchInterruption = plan.interruption
    return dispatchOutcome({})
  }
}
// END bounded dispatch policy


// Retries a dispatch that failed transiently (overload, rate limit, network) with capped backoff;
// returns null, or rethrows when opts.rethrow, on any other failure.
function failureCause(err) { return dispatchFailureCause(err) }
async function settleAgent(prompt, opts) {
  if (dispatchInterruption) return null
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.retryPolicy
  delete call.schemaName
  delete call.rethrow
  const name = o.label || o.agentType || 'agent'
  const policy = dispatchPolicy(o)
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    if (dispatchInterruption) return null
    try {
      const out = await agent(prompt, call)
      if (out) {

        return out
      }

      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)

      if (!plan.retry) {
        if (plan.interruption) dispatchInterruption = plan.interruption
        log(name + ': stopped (' + plan.cause + ') — ' + message)
        if (o.rethrow && !plan.interruption) throw err
        return null
      }
      waitedMs += plan.wait
      log(name + ': transient failure; retry ' + (attempt + 1) + '/' + policy.maxAttempts + ' in ' + Math.round(plan.wait / 1000) + 's — ' + message.slice(0, 160))
      await new Promise((resolve) => setTimeout(resolve, plan.wait))
    }
  }
}

// args: { repoPath: string|null, prCommand: string|null, branch?: string|null, defaultBranch?: string|null, isLinkedWorktree?: boolean,
//         commitOnly?: boolean, message?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const wt = typeof a.repoPath === 'string' && a.repoPath.trim() ? a.repoPath.trim() : null
const prCommand = typeof a.prCommand === 'string' && a.prCommand.trim() ? a.prCommand.trim() : null
const baseName = String(a.defaultBranch || '').trim().replace(/^refs\/heads\//, '').replace(/^origin\//, '') || 'main'
const baseRef = `origin/${baseName}`
const commitOnly = a.commitOnly === true
const message = String(a.message || '').replace(/\s+/g, ' ').trim()

const COMMIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['treeClean', 'hasWork', 'branch', 'commit'],
  properties: {
    treeClean: { type: 'boolean' },
    hasWork: { type: 'boolean' },
    branch: { type: 'string' },
    commit: { type: 'string' },
    blocked: { type: 'array', items: { type: 'string' } },
  },
}

async function commitRun() {
  if (!wt) return { status: 'not-applicable', reason: 'the run established no repo path, so nothing was written' }
  try {
    const reported = await settleAgent(
      `Commit every change in the worktree ${wt} on its current branch, or say exactly why it could not be committed.

Run every git command as \`git -C "${wt}"\`.
1. \`git -C "${wt}" rev-parse --abbrev-ref HEAD\`. If it prints ${baseName} or HEAD, commit nothing and name it in \`blocked\`.
2. \`git -C "${wt}" status --porcelain\`. Report \`hasWork\`: true if it printed anything.
3. If hasWork, \`git -C "${wt}" add -A\` and commit as \`type(scope): description\`${message ? ` (the change: ${message})` : ''} with NO Co-Authored-By header. \`--no-verify\` is forbidden; when a hook fails, fix every finding, stage the fixes and commit again; if a finding cannot be fixed, abort with NO commit and name it in \`blocked\`.
4. Do not push, do not open a pull request, and do not merge.
5. Report the branch, \`git -C "${wt}" rev-parse HEAD\` as \`commit\`, and whether \`git -C "${wt}" status --porcelain\` is now empty as \`treeClean\`.`,
      { label: 'settle:commit', rethrow: true, phase: 'Settle', agentType: 'agent-teams-workforce:github-actions-pipeline-implementer', schema: COMMIT_SCHEMA }
    )
    if (!reported) return { status: 'error', error: 'the commit agent returned no result' }
    return { status: 'reported', ...reported }
  } catch (e) {
    const error = e && e.message ? e.message : String(e)
    log(`commit failed: ${error}`)
    return { status: 'error', error }
  }
}

async function settleRun() {
  if (!wt) return { status: 'not-applicable', reason: 'the run established no repo path, so nothing was written' }
  if (!prCommand) {
    return { status: 'blocked', reason: `settle has no PR command (args.prCommand, ATW_PR_COMMAND) to land the work in ${wt} with; the work is left in the worktree.` }
  }
  try {
    const reported = await settleAgent(
      `Land every change in the worktree ${wt}, or say exactly why it could not be landed.

Run every git command as \`git -C "${wt}"\`, and \`cd "${wt}"\` before the PR command.
1. \`git -C "${wt}" status --porcelain\`. Commit anything uncommitted as \`type(scope): description\` with NO Co-Authored-By header. \`--no-verify\` is forbidden; if a hook finding cannot be fixed, abort with NO commit and name it in \`blocked\`.
2. If \`git -C "${wt}" rev-parse --abbrev-ref --symbolic-full-name @{u}\` resolves to ${baseRef}, run \`git -C "${wt}" branch --unset-upstream\`. Never push to the default branch.
3. \`git -C "${wt}" fetch origin ${baseName}\`. Report \`hasWork\`: true if the tree was dirty or the branch has commits not reachable from ${baseRef}.
4. If hasWork, \`cd "${wt}" && ${prCommand} --title "<type(scope): description>" --body "<what changed>"\`. It pushes the branch and opens the pull request. Never open the PR another way and never merge it. A PR that already exists for this head is success; report its URL.
5. Report the PR URL, the branch, and whether the tree is clean.`,
      {
        label: 'settle:land-work',
        rethrow: true,
        phase: 'Settle',
        agentType: 'agent-teams-workforce:github-actions-pipeline-implementer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['treeClean', 'hasWork', 'branch', 'prUrl'],
          properties: {
            treeClean: { type: 'boolean' },
            hasWork: { type: 'boolean' },
            branch: { type: 'string' },
            prUrl: { type: 'string' },
            blocked: { type: 'array', items: { type: 'string' } },
          },
        },
      }
    )
    if (!reported) return { status: 'error', error: 'the settle agent returned no result' }
    return { status: 'reported', ...reported }
  } catch (e) {
    const error = e && e.message ? e.message : String(e)
    log(`settle failed: ${error}`)
    return { status: 'error', error }
  }
}

phase('Settle')
return dispatchOutcome(commitOnly ? await commitRun() : await settleRun())
