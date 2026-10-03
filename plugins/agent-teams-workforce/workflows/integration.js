export const meta = {
  name: 'integration',
  description:
    'Shared-tail mini — Integration Testing. Picks the integration suites from the caller, from the surfaces the contract declares, or from a read-only integration-testing-lead, provisions the test environment when needed, runs the suites in parallel, and returns a top-level `passed`; a suite that returns nothing reports dispatchFailed. A contract declaring no cross-boundary surface skips the phase.',
  phases: [{ title: 'Integration', detail: 'select + run suites' }],
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

// args: { contract, green, suites?, provisionEnv?, feedback? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const beadId = (c.bead && c.bead.id) || null
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim() || '(repo path not provided)'
const pinTree = `PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in — you may be running in an isolation worktree of a different one — so a relative path, a bare \`git\` command or an unqualified test run reads, edits or runs the WRONG copy. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}`

const SUITE_AGENTS = {
  'aws-integration-test-runner':
    'the event delivery path from publisher to consumer — usually required for backend work',
  'event-flow-tester': 'event-driven flow, routing, retry, and DLQ behavior per hop',
  'data-consistency-checker': 'cross-store data consistency after the runs (partial writes, orphans, divergent state)',
  'cross-service-contract-tester': 'cross-service / cross-repo API and event contracts',
}

const changeUnderTest = c.bead ? `${c.bead.id || ''} ${c.bead.title || ''}`.trim() : 'feature'
const greenChanged = a.green && Array.isArray(a.green.changedFiles) ? a.green.changedFiles.filter(Boolean) : []
const surfaces = `Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}
Files the change modified: ${greenChanged.join(', ') || 'n/a'}
Change under test: ${changeUnderTest}`

phase('Integration')

const SURFACE_SUITES = {
  'event-chain': ['aws-integration-test-runner', 'event-flow-tester'],
  'api-contract': ['cross-service-contract-tester'],
  'data-pipeline': ['data-consistency-checker'],
}
const declaredSurfaces = Array.isArray(c.surfaces) ? c.surfaces : null

let suites
let provisionEnv = a.provisionEnv === true
let selectionMode
if (Array.isArray(a.suites) && a.suites.some((s) => SUITE_AGENTS[s])) {
  suites = a.suites.filter((s) => SUITE_AGENTS[s])
  selectionMode = 'caller-specified'
} else if (declaredSurfaces) {
  suites = [...new Set(declaredSurfaces.flatMap((s) => SURFACE_SUITES[s] || []))].filter((s) => SUITE_AGENTS[s])
  selectionMode = 'derived'
  if (!suites.length) {
    log(`Integration: the contract declares no cross-boundary surface (${declaredSurfaces.join(', ') || 'none'}) — skipping`)
    return dispatchOutcome({
      suites: [],
      provisionEnv: false,
      results: [],
      passed: true,
      alreadySatisfied: true,
      reason: 'the contract declares no cross-service, event-chain, or data-pipeline surface, so no integration suite applies',
      ledger: { phase: 'integration', beadId, chosen: [], mode: 'no-applicable-suite', ok: true },
    })
  }
  provisionEnv = true
  log(`Integration suites derived from surfaces [${declaredSurfaces.join(', ')}]: ${suites.join(', ')}`)
} else {
  const menu = Object.entries(SUITE_AGENTS)
    .map(([name, why]) => `  - ${name}: ${why}`)
    .join('\n')
  const selection = await settleAgent(
    `You are the integration-testing-lead — a READ-ONLY router. Do NOT run tests or write anything. Select the FEWEST integration suites whose surfaces this change actually touches, drawn from:
${menu}

A standard backend / event-driven change almost always needs aws-integration-test-runner. Add event-flow-tester when routing/retry/DLQ behavior changes, data-consistency-checker when writes span stores, and cross-service-contract-tester when an API or event contract crosses a service or repo boundary. Also decide whether the integration test environment must be provisioned or reset before the suites run (true for any change that needs fresh event-chain or data-store state).

${pinTree}

${surfaces}`,
    {
      label: 'integration:select-suites',
      effort: 'low',
      phase: 'Integration',
      agentType: 'agent-teams-workforce:integration-testing-lead',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['suites', 'provisionEnv', 'rationale'],
        properties: {
          suites: { type: 'array', items: { type: 'string' } },
          provisionEnv: { type: 'boolean' },
          rationale: { type: 'string' },
        },
      },
    }
  )
  const picked = selection && Array.isArray(selection.suites) ? selection.suites.filter((s) => SUITE_AGENTS[s]) : []
  suites = picked.length ? picked : ['aws-integration-test-runner']
  selectionMode = picked.length ? 'selected' : 'default'
  provisionEnv = selection && typeof selection.provisionEnv === 'boolean' ? selection.provisionEnv : true
}

const SUITE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['passed', 'coverageMet', 'failures'],
  properties: {
    passed: { type: 'boolean' },
    coverageMet: { type: 'boolean' },
    flaky: { type: 'array', items: { type: 'string' } },
    failures: { type: 'array', items: { type: 'string' } },
    evidence: { type: 'string' },
  },
}

const envSetup = provisionEnv
  ? await settleAgent(
      `Provision or reset the integration test environment for this change — the event path, functions and data stores the change touches — and seed required fixtures.

${pinTree}

${surfaces}`,
      {
        label: 'integration:provision-env',
        phase: 'Integration',
        agentType: 'test-environment-orchestrator',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['ready'],
          properties: {
            ready: { type: 'boolean' },
            evidence: { type: 'string' },
          },
        },
      }
    )
  : null

const suiteRuns = await parallel(
  suites.map((suite) => () =>
    settleAgent(
      `Run the ${suite.replace(/-/g, ' ')} suite relevant to this change and report structured results. Verify contracts across service boundaries hold and required coverage is met.

${pinTree}

${surfaces}
${a.feedback ? `\nPrior feedback to address:\n${a.feedback}` : ''}

Deliver pass/fail, coverage, any flaky tests, and concrete failure details.`,
      {
        label: `integration:${suite}`,
        phase: 'Integration',
        agentType: `agent-teams-workforce:${suite}`,
        schema: SUITE_SCHEMA,
      }
    )
  )
)

const deadSuites = suites.filter((_s, i) => !(suiteRuns || [])[i])
if (deadSuites.length) {
  return dispatchOutcome({
    ok: false,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Integration'),
    reason: `integration suite(s) ${deadSuites.join(', ')} returned nothing`,
    passed: false,
    ledger: { phase: 'integration', beadId, chosen: suites, mode: selectionMode, ok: false },
  })
}

const results = (suiteRuns || []).filter(Boolean)
const flaky = []
const failures = []
for (const r of results) {
  if (Array.isArray(r.flaky)) flaky.push(...r.flaky)
  if (Array.isArray(r.failures)) failures.push(...r.failures)
}
const passed = results.length > 0 && results.every((r) => r.passed)
const coverageMet = results.length > 0 && results.every((r) => r.coverageMet)
const evidence = results
  .map((r) => r.evidence)
  .filter(Boolean)
  .join('\n')

const ledger = {
  phase: 'integration',
  beadId,
  chosen: (provisionEnv ? ['test-environment-orchestrator'] : []).concat(suites),
  mode: selectionMode,
  ok: passed,
}

return dispatchOutcome({ passed, coverageMet, flaky, failures, evidence, envSetup, suites, provisionEnv, ledger })
