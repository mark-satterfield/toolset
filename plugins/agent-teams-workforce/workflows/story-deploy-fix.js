export const meta = {
  name: 'story-deploy-fix',
  description:
    "Story deploy fix loop, one pass — the only agent step of a Story's deploy. The Story's package publish, `cdk synth`, `cdk deploy` to AWS dev, or the verification that every stack reached CREATE_COMPLETE or UPDATE_COMPLETE, failed. One cdk-stack-author session diagnoses the failure from its output, fixes the CDK (or whatever the deploy needs) in the Story's worktree, runs the repository's synth assertion tests and updates any test the fix proves wrong; then the fix is committed to the Story branch. A fix that changes no file returns stage no-change and commits nothing. It never deploys, never re-enters Green and opens no pull request: the caller redeploys and verifies. Returns { ok, stage, beadId, headline, detailPath, testsPassed, changedFiles, commit }.",
  phases: [
    { title: 'Fix', detail: 'diagnose the deploy failure and fix it on the Story branch; the synth assertion tests pass' },
    { title: 'Commit', detail: 'commits the fix to the Story branch' },
  ],
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

// args: {
//   beadId: string (the Story), story: { id, title? }, repoPath: string (the Story's worktree),
//   branch: string, defaultBranch?: string, attempt: number,
//   failure: { step: 'publish' | 'synth' | 'deploy' | 'verify', output: string, stacks?: [{ name, status, reason? }] }
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const story = a.story && typeof a.story === 'object' ? a.story : {}
const beadId = String(a.beadId || story.id || '').trim()
const repo = String(a.repoPath || '').trim().replace(/\/+$/, '')
const failure = a.failure && typeof a.failure === 'object' ? a.failure : {}
const attempt = Number(a.attempt) || 1
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'

const handback = (ok, stage, headline, extra) => ({ ok, stage, beadId: beadId || null, headline: String(headline || ''), detailPath: null, ...(extra || {}) })

if (!beadId) return dispatchOutcome(handback(false, 'input', 'no Story id supplied'))
if (!repo) return dispatchOutcome(handback(false, 'input', `no worktree supplied for Story ${beadId}`))

const stacks = (Array.isArray(failure.stacks) ? failure.stacks : [])
  .filter((s) => s && typeof s === 'object')
  .map((s) => `  - ${s.name}: ${s.status || 'no status'}${s.reason ? ` — ${s.reason}` : ''}`)
  .join('\n')

phase('Fix')
const fix = await settleAgent(
  `The deploy of Story ${beadId}${story.title ? ` (${story.title})` : ''} to AWS dev failed, attempt ${attempt}. Diagnose the failure and fix it on the Story's branch. Do not deploy: the caller redeploys and verifies once you return.

PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}
Branch: ${a.branch || '(the branch checked out in that tree)'}

What failed: ${
  {
    verify: 'deployment verification — a stack did not reach CREATE_COMPLETE or UPDATE_COMPLETE',
    publish: "publishing the repository's package to CodeArtifact",
    synth: '`cdk synth`',
  }[failure.step] || '`cdk deploy`'
}
${stacks ? `Stacks:\n${stacks}\n` : ''}Output:
${String(failure.output || '(no output was captured)').slice(-12000)}

1. Find the cause in this output and in the CloudFormation stack events it points to (\`aws cloudformation describe-stack-events\`, read-only).
2. Fix the CDK, or whatever else the deploy needs, in this tree. A value one stack passes to another goes by the cross-stack mechanism the repository's stacks already use.
3. Run the repository's synth assertion tests. Where the fix proves a test wrong, correct the test so it asserts what the fixed template must contain; never weaken a test to make it pass.
4. Do not commit, push, deploy, publish a package or open a pull request, and never run \`cdk deploy\` or \`cdk destroy\`: the caller commits your change, then publishes and deploys.
5. When nothing in this tree can fix the failure (it lies outside the repository), change no file and say why in the cause; an empty changedFiles stops the deploy instead of repeating it.

Report the cause, the files you changed, whether the synth assertion tests pass, and their captured output.`,
  {
    label: 'story-deploy:fix',
    phase: 'Fix',
    agentType: 'cdk-stack-author',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['cause', 'changedFiles', 'testsPassed', 'evidence'],
      properties: {
        cause: { type: 'string' },
        changedFiles: { type: 'array', items: { type: 'string' } },
        testsPassed: { type: 'boolean' },
        evidence: { type: 'string' },
        notes: { type: 'string' },
      },
    },
  }
)
if (!fix) return dispatchOutcome(handback(false, DISPATCH_FAILED_STAGE, `the fixer for Story ${beadId} returned nothing`))
const changedFiles = Array.isArray(fix.changedFiles) ? fix.changedFiles.filter((f) => typeof f === 'string' && f.trim()) : []
if (!changedFiles.length) {
  return dispatchOutcome(handback(false, 'no-change', `Story ${beadId}: the fixer changed no file, so a redeploy would fail the same way — ${String(fix.cause || 'no cause given').slice(0, 300)}`, {
    cause: fix.cause,
    changedFiles,
    testsPassed: fix.testsPassed === true,
  }))
}

phase('Commit')
const committed = await settleWorkflow('agent-teams-workforce:settle', {
  repoPath: repo,
  commitOnly: true,
  branch: a.branch || null,
  defaultBranch: a.defaultBranch || null,
  message: `fix the deploy of Story ${beadId}: ${String(fix.cause || '').slice(0, 160)}`,
})
if (!committed || committed.status !== 'reported' || (Array.isArray(committed.blocked) && committed.blocked.length)) {
  const why =
    (committed && (committed.error || committed.reason || (Array.isArray(committed.blocked) && committed.blocked.join('; ')))) ||
    'the commit step returned nothing'
  return dispatchOutcome(handback(false, !committed || committed.status === 'error' ? DISPATCH_FAILED_STAGE : 'commit', `Story ${beadId}: the fix was not committed — ${why}`, {
    cause: fix.cause,
    changedFiles,
    testsPassed: fix.testsPassed === true,
  }))
}

return dispatchOutcome(handback(true, 'fixed', `Story ${beadId}: ${String(fix.cause || 'the deploy failure').slice(0, 300)} — fixed and committed (${committed.commit || 'no new commit'})${fix.testsPassed === true ? '; the synth assertion tests pass' : ''}`, {
  cause: fix.cause,
  changedFiles,
  testsPassed: fix.testsPassed === true,
  commit: committed.commit || null,
}))
