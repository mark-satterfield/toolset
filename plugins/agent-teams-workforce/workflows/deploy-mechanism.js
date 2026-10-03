export const meta = {
  name: 'deploy-mechanism',
  description:
    "Leaf mini — asks one polyrepo-steward session what a Story's repository publishes and deploys, before the Story's deploy. A repository can publish a package to CodeArtifact, deploy with CDK, both, or neither; the steward answers from its records and the repository's own declarations, and names the command that publishes the package as the repository declares it. A Taskfile is a convenience and does not decide the mechanism. The host runs what applies (publish, then `cdk deploy`) and stops a repository that does neither. Returns { ok, stage, beadId, headline, detailPath, mechanism: { repository, publishes, publishCommand, deploys, reason } }.",
  phases: [{ title: 'Ask', detail: "the polyrepo-steward rules what the Story's repository publishes and deploys" }],
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

// args: { beadId?: string, story: { id, title? }, repoPath: string (the Story's repository, not its worktree) }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const story = a.story && typeof a.story === 'object' ? a.story : {}
const beadId = String(a.beadId || story.id || '').trim()
const repo = String(a.repoPath || '').trim().replace(/\/+$/, '')
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'

const handback = (ok, stage, headline, extra) => ({ ok, stage, beadId: beadId || null, headline: String(headline || ''), detailPath: null, ...(extra || {}) })

if (!beadId) return dispatchOutcome(handback(false, 'input', 'no Story id supplied'))
if (!repo) return dispatchOutcome(handback(false, 'input', `no repository supplied for Story ${beadId}`))

phase('Ask')
const got = await settleAgent(
  `Story ${beadId}${story.title ? ` (${story.title})` : ''} is about to deploy from this repository:
${repo}

Rule, from your records of this repository and the repository's own declarations (its AGENTS.md or CLAUDE.md, its CI workflows, its package manifest, its CDK app), what it publishes and what it deploys. A repository can do one, both, or neither:
- publishes: true when the repository publishes a package to CodeArtifact. Then publishCommand is the command, as an argument list run from the repository root, that builds and publishes that package the way the repository itself declares it (for example ["task", "publish"] when its Taskfile declares that task). A Taskfile is a convenience: it does not decide whether the repository publishes, and a Taskfile task with no other declaration behind it is not evidence that the repository publishes.
- deploys: true when the repository deploys AWS infrastructure with CDK (it holds a CDK app this pipeline deploys with \`cdk deploy\`).
The project's control repository and the documentation vault publish and deploy nothing.

Read only; change nothing. Return repository (the path exactly as given above), publishes, publishCommand (an empty list when publishes is false), deploys, and reason (the records and files that decide it, in a sentence or two).`,
  {
    label: 'deploy:mechanism',
    phase: 'Ask',
    agentType: 'agent-teams-workforce:polyrepo-steward',
    effort: 'low',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['repository', 'publishes', 'publishCommand', 'deploys', 'reason'],
      properties: {
        repository: { type: 'string' },
        publishes: { type: 'boolean' },
        publishCommand: { type: 'array', items: { type: 'string' } },
        deploys: { type: 'boolean' },
        reason: { type: 'string' },
      },
    },
  }
)
if (!got) return dispatchOutcome(handback(false, DISPATCH_FAILED_STAGE, `the polyrepo-steward gave no ruling on what ${repo} publishes and deploys`))

const publishCommand = (Array.isArray(got.publishCommand) ? got.publishCommand : []).map((p) => String(p)).filter((p) => p.length)
const mechanism = {
  repository: repo,
  publishes: got.publishes === true,
  publishCommand,
  deploys: got.deploys === true,
  reason: String(got.reason || '').trim(),
}
const does = [mechanism.publishes ? `publishes (${publishCommand.join(' ') || 'no command named'})` : '', mechanism.deploys ? 'deploys with CDK' : ''].filter(Boolean)
return dispatchOutcome(handback(true, 'ask', `${repo}: ${does.length ? does.join(' and ') : 'publishes and deploys nothing'} — ${mechanism.reason}`.slice(0, 900), { mechanism }))
