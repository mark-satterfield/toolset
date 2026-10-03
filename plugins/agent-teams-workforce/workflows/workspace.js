export const meta = {
  name: 'workspace',
  description:
    'Establishes the git worktree the writing phases work in: reuses the tree already registered for the bead, or cuts one on a feature branch at <worktreeRoot>/<bead>-<repo> (a .worktrees/ directory beside the repository when no root is given). One provisioner session does the git work. With stashUncommitted, a reused tree\'s uncommitted changes are stashed (`git stash push --include-untracked`) under a message naming the run, so the run starts from the branch head and the earlier work stays recoverable. Refuses (ok:false with the reason in blocked) when repoPath or beadId is missing, the provisioner returns nothing or ok=false, or the tree is on a default branch or a detached HEAD. Returns { ok, applicable, repoPath, branch, reused, stashed, isLinkedWorktree: true, independentlyVerified: true, defaultBranch, verification, blocked, ledger }.',
  phases: [{ title: 'Workspace', detail: 'provision or reuse the linked worktree the writing phases operate in' }],
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

// args: { repoPath: string, beadId: string, branchPrefix?: string, purpose?: string, worktreeRoot?: string,
//         stashUncommitted?: boolean, stashLabel?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const repoPath = String(a.repoPath || '').trim().replace(/\/+$/, '')
const beadId = String(a.beadId || '').trim()
const worktreeRoot = String(a.worktreeRoot || '').trim().replace(/\/+$/, '')
const prefix = String(a.branchPrefix || 'work').trim().replace(/[^a-zA-Z0-9._-]/g, '') || 'work'
const purpose = String(a.purpose || '').replace(/\s+/g, ' ').trim().slice(0, 240)
const stashUncommitted = a.stashUncommitted === true
const stashLabel = String(a.stashLabel || beadId || '').replace(/[^a-zA-Z0-9._ -]/g, '').trim().slice(0, 120)
const stashStep = stashUncommitted
  ? `\n6. Only when you reused the tree: \`git -C "<tree>" status --porcelain\`. When it prints anything, run \`git -C "<tree>" stash push --include-untracked -m "abandoned run ${stashLabel} $(date -u +%Y-%m-%dT%H:%M:%SZ)"\`, then \`git -C "<tree>" stash list -n 1\`, and confirm \`git -C "<tree>" status --porcelain\` now prints nothing.`
  : ''
const stashReport = stashUncommitted ? '\n- stashed: the line `git stash list -n 1` printed after step 6 stashed changes; "" when nothing was stashed.' : ''

const refuse = (reason, extra) => ({ ok: false, applicable: true, repoPath: null, branch: null, reused: false, blocked: [reason], ...(extra || {}) })

if (!repoPath) return dispatchOutcome({ ...refuse('no repoPath supplied'), applicable: false })
if (!beadId) return dispatchOutcome({ ...refuse('no beadId supplied'), applicable: false })

const repoBase = repoPath.slice(repoPath.lastIndexOf('/') + 1)
const repoParent = repoPath.slice(0, repoPath.lastIndexOf('/')) || '/'
const worktreeHome = worktreeRoot || `${repoParent === '/' ? '' : repoParent}/.worktrees`
const plannedWorktreePath = `${worktreeHome}/${beadId}-${repoBase}`
const BRANCH = `${prefix}/${beadId}`

phase('Workspace')

const provisioned = await settleAgent(
  `Establish the git worktree this run's writing phases will operate in, then report what you established. Write no project code.

Repository: ${repoPath}
Work item: ${beadId}
Branch: ${BRANCH}
Worktree path: ${plannedWorktreePath}${purpose ? `\nPurpose: ${purpose}` : ''}

Run every git command as \`git -C "<path>"\`. Never redirect stderr to /dev/null.

1. Find the default branch: \`git -C "${repoPath}" symbolic-ref --short refs/remotes/origin/HEAD\` (strip \`origin/\`; if missing use main, then master).
2. \`git -C "${repoPath}" worktree list --porcelain\`. If a tree is already registered for branch ${BRANCH} or at ${plannedWorktreePath}, reuse it (reused=true) and go to step 5.
3. \`git -C "${repoPath}" fetch origin <default>\`. Fast-forward the main tree only if it is clean, on the default branch, and behind origin; otherwise leave it alone.
4. \`mkdir -p "$(dirname "${plannedWorktreePath}")"\` then \`git -C "${repoPath}" worktree add --no-track -b "${BRANCH}" "${plannedWorktreePath}" origin/<default>\`. If the branch already exists, \`git -C "${repoPath}" worktree add "${plannedWorktreePath}" "${BRANCH}"\`.
5. On the tree: \`git -C "<tree>" rev-parse --abbrev-ref HEAD\` and \`git -C "<tree>" rev-parse --path-format=absolute --git-common-dir\`.${stashStep}

Report:
- ok: true when the tree exists on a branch that is not the default branch.
- repoPath: the WORKTREE path (never the repository path above unless you reused it as the tree).
- branch: the branch step 5 printed.
- reused: true if you reused an existing tree.
- gitCommonDir: the git-common-dir step 5 printed.
- defaultBranch: the default branch from step 1.${stashReport}
- blocked: one short sentence for each thing that stopped you or that you worked around.`,
  {
    label: 'workspace:provision',
    effort: 'low',
    phase: 'Workspace',
    agentType: 'agent-teams-workforce:github-actions-pipeline-implementer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['ok', 'repoPath', 'branch', 'reused'],
      properties: {
        ok: { type: 'boolean' },
        repoPath: { type: 'string' },
        branch: { type: 'string' },
        reused: { type: 'boolean' },
        gitCommonDir: { type: 'string' },
        defaultBranch: { type: 'string' },
        stashed: { type: 'string' },
        blocked: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

if (!provisioned) {
  return dispatchOutcome(refuse('the provisioner returned nothing, so no worktree was established', {
    dispatchFailed: true,
    dispatchFailures: [{ label: 'workspace:provision', phase: 'Workspace', outcome: 'no-result' }],
  }))
}
const blocked = Array.isArray(provisioned.blocked) ? provisioned.blocked : []
if (provisioned.ok !== true) {
  return dispatchOutcome({ ...refuse('the provisioner could not establish a worktree (ok=false)'), blocked: ['the provisioner could not establish a worktree (ok=false)', ...blocked] })
}

const reported = String(provisioned.repoPath || '').trim().replace(/\/+$/, '')
const treePath = reported && reported !== repoPath ? reported : plannedWorktreePath
const branch = String(provisioned.branch || '').trim() || BRANCH
const defaultBranch = String(provisioned.defaultBranch || '').trim().replace(/^refs\/heads\//, '').replace(/^origin\//, '') || null
const normalized = branch.replace(/^refs\/heads\//, '').replace(/^origin\//, '').toLowerCase()

if (['main', 'master', 'head'].includes(normalized) || (defaultBranch && normalized === defaultBranch.toLowerCase())) {
  return dispatchOutcome({ ...refuse(`the worktree ${treePath} is on "${branch}", a default branch or a detached HEAD`), blocked: [`the worktree ${treePath} is on "${branch}", a default branch or a detached HEAD`, ...blocked] })
}

const stashed = stashUncommitted ? String(provisioned.stashed || '').trim() || null : null
log(`Workspace: ${provisioned.reused ? 'reused' : 'created'} worktree ${treePath} on ${branch}${stashed ? `; uncommitted changes stashed as ${stashed}` : ''}`)

return dispatchOutcome({
  ok: true,
  applicable: true,
  repoPath: treePath,
  branch,
  reused: provisioned.reused === true,
  stashed,
  isLinkedWorktree: true,
  independentlyVerified: true,
  defaultBranch,
  verification: { gitCommonDir: String(provisioned.gitCommonDir || '').trim() || null, branch, defaultBranch },
  blocked,
  ledger: { phase: 'workspace', beadId, branch, reused: provisioned.reused === true, ok: true },
})
