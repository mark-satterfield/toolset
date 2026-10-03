export const meta = {
  name: 'deploy',
  description:
    'Shared-tail mini — Deploy. Refuses a contract with no repoPath. The smoke-test-author writes a smoke suite (or the smokeTestFiles passed in are reused), then one cdk-stack-author session deploys the one repository the contract names to AWS dev and runs the smoke tests against the deployed endpoints. Returns { deployedToDev, smokePassed, smokeTestFiles, rollout, deployedToProd: false, ledger }, with dispatchFailed when a session returned nothing. Opens no pull request; never deploys to qa or prod.',
  phases: [{ title: 'Deploy-readiness', detail: 'author smoke tests, deploy to AWS dev, run the smoke tests' }],
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

const dispatchFailures = []
// Returns the recorded dispatch failures of the named phases, or all of them when none is named.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
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
        for (const entry of mine) { const at = dispatchFailures.indexOf(entry); if (at >= 0) dispatchFailures.splice(at, 1) }
        return out
      }
      dispatchFailures.push({ agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: name + ': returned nothing' })
      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)
      const entry = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'threw', cause: plan.cause, attempt, message: message.slice(0, 300), note: name + ': ' + message.slice(0, 160) }
      dispatchFailures.push(entry)
      mine.push(entry)
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

// args: { contract, green?, feedback?, smokeTestFiles?, leaseScope? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const feedback = a.feedback ? `\nPrior gate feedback to address:\n${a.feedback}` : ''
const beadId = (c.bead && c.bead.id) || null
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim()
if (!repo) {
  const why = 'the contract names no repoPath, so there is no tree to deploy from'
  return dispatchOutcome({
    ok: false,
    phaseBlocked: true,
    blockedReason: why,
    deployedToDev: false,
    smokePassed: false,
    smokeTestFiles: [],
    deployedToProd: false,
    blocked: [why],
    ledger: { phase: 'deploy', beadId, chosen: [], mode: 'refused', ok: false },
  })
}
const pinTree = `PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in — you may be running in an isolation worktree of a different one — so a relative path, a bare \`git\` command or an unqualified test run reads, edits or runs the WRONG copy. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}`
const changeLabel = c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'
const DEV_ACCOUNT = '616930583457'
const DEV_REGION = 'us-east-1'

phase('Deploy-readiness')

const priorSmokeFiles = (Array.isArray(a.smokeTestFiles) ? a.smokeTestFiles : []).map((f) => String(f || '').trim()).filter(Boolean)
const smoke = priorSmokeFiles.length
  ? { smokeTestFiles: priorSmokeFiles, reused: true }
  : await settleAgent(
      `Author post-deployment smoke tests that verify the fixed behavior against a deployed endpoint. Do not deploy.

${pinTree}

Change: ${changeLabel}
Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}${feedback}`,
      {
        label: 'deploy:smoke-author',
        phase: 'Deploy-readiness',
        agentType: 'agent-teams-workforce:smoke-test-author',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['smokeTestFiles'],
          properties: {
            smokeTestFiles: { type: 'array', items: { type: 'string' } },
            notes: { type: 'string' },
          },
        },
      }
    )
if (!smoke) {
  return dispatchOutcome({
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Deploy-readiness'),
    reason: 'the smoke-test author returned nothing, so nothing was deployed',
    env: 'dev',
    smokeTestFiles: [],
    deployedToDev: false,
    smokePassed: false,
    deployedToProd: false,
    ledger: { phase: 'deploy', stage: 'not-deployed', beadId, chosen: ['smoke-test-author'], mode: 'fixed', env: 'dev', ok: false },
  })
}
const smokeTestFiles = (Array.isArray(smoke.smokeTestFiles) ? smoke.smokeTestFiles : []).map((f) => String(f || '').trim()).filter(Boolean)

const rollout = await settleAgent(
  `Deploy this change to the DEV environment (AWS account ${DEV_ACCOUNT}, ${DEV_REGION}).

${pinTree}

Deploy just this repo against dev, using the mechanism this repo actually deploys by: \`cdk deploy\` of the affected stack(s) when the repo has a CDK app; otherwise the repo's own deploy path (Taskfile, package.json scripts, deploy script). For a static site that is a build, \`aws s3 sync\` and a CloudFront invalidation; wait for the invalidation to report Completed before smoke-testing. A task NAMED cdk:deploy may run no CDK operation — read what it executes.

Then RUN the smoke tests (${smokeTestFiles.join(', ') || 'none were authored'} — paths relative to the tree above) against the deployed endpoints and report their literal output. A deploy that succeeds while its smoke test fails is a FAILED rollout.

Report \`deployed\`, \`smokePassed\`, and \`smokeCases\`: one row per smoke case with its name, whether it passed, and its literal output. Also report the stacks you changed and the commit SHA you deployed (\`git -C "${repo}" rev-parse HEAD\`).

HARD LIMITS: dev ONLY — never qa, never prod. Do not delete or replace data. If a deploy errors, stop and report where and why.`,
  {
    label: 'deploy:rollout-dev',
    phase: 'Deploy-readiness',
    agentType: 'cdk-stack-author',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['deployed', 'smokePassed', 'smokeCases'],
      properties: {
        deployed: { type: 'boolean' },
        smokePassed: { type: 'boolean' },
        smokeCases: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['name', 'passed', 'output'],
            properties: { name: { type: 'string' }, passed: { type: 'boolean' }, output: { type: 'string' } },
          },
        },
        stacks: { type: 'array', items: { type: 'string' } },
        commitSha: { type: 'string' },
        evidence: { type: 'string' },
        findings: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

const deployedToDev = !!(rollout && rollout.deployed === true)
const smokePassed = !!(rollout && rollout.smokePassed === true)
const ledger = {
  phase: 'deploy',
  stage: deployedToDev ? 'deployed-to-dev' : 'not-deployed',
  beadId,
  chosen: [...(priorSmokeFiles.length ? [] : ['smoke-test-author']), 'cdk-stack-author'],
  mode: 'fixed',
  env: 'dev',
  deployedToDev,
  smokePassed,
  rolledOut: deployedToDev,
  ok: deployedToDev && smokePassed,
}
const dispatchFailure = rollout
  ? {}
  : { dispatchFailed: true, dispatchFailures: dispatchDeaths('Deploy-readiness'), reason: 'the dev rollout returned nothing' }

return dispatchOutcome({
  ...dispatchFailure,
  smoke,
  rollout,
  env: 'dev',
  smokeTestFiles,
  deployedToDev,
  smokePassed,
  deployedToProd: false,
  ledger,
})
