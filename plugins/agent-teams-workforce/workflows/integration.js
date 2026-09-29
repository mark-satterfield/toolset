export const meta = {
  name: 'integration',
  description:
    'Shared-tail mini — Integration Testing. Picks the integration suites from the caller, from the surfaces the contract declares, or from a read-only integration-testing-lead, provisions the test environment when needed, runs the suites in parallel, and returns a top-level `passed`; a suite that returns nothing reports dispatchFailed. A contract declaring no cross-boundary surface skips the phase.',
  phases: [{ title: 'Integration', detail: 'select + run suites' }],
}
const dispatchFailures = []
// Returns the recorded dispatch failures of the named phases, or all of them when none is named.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
// Returns 'transient' for an API overload, rate limit or network error, otherwise 'deterministic'.
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  return TRANSIENT_ERROR_TEXT.test(text) ? 'transient' : 'deterministic'
}
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
const settleSleep = (ms) => (SETTLE_CAN_WAIT ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve())
// Returns the wait before retry `attempt`: 5s tripled per attempt, capped at 300s, scaled into [50%, 100%) by a hash of the dispatch.
function transientWaitMs(name, attempt) {
  const key = `${name}#${attempt}`
  let h = 2166136261
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  const scheduled = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
  return Math.round(scheduled * (0.5 + 0.5 * ((h >>> 0) / 4294967296)))
}
// Calls agent() and returns its result. A transient failure is retried with backoff until it clears
// (three attempts when no timer exists); any other failure returns null and is recorded in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    let out = null
    try {
      out = await agent(prompt, o)
    } catch (err) {
      const message = String((err && err.message) || err)
      const cause = failureCause(err)
      const entry = {
        ...who,
        outcome: 'threw',
        cause,
        attempt,
        message: message.slice(0, 300),
        note: `${name} ended without a structured result (${cause}): ${message.slice(0, 160)}`,
      }
      dispatchFailures.push(entry)
      mine.push(entry)
      log(entry.note)
      if (cause !== 'transient' || (!SETTLE_CAN_WAIT && attempt >= 3)) return null
      const wait = transientWaitMs(name, attempt)
      waitedMs += wait
      log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s (${Math.round(waitedMs / 1000)}s waited)`)
      await settleSleep(wait)
      continue
    }
    if (out) {
      for (const entry of mine) {
        const at = dispatchFailures.indexOf(entry)
        if (at >= 0) dispatchFailures.splice(at, 1)
      }
      return out
    }
    dispatchFailures.push({ ...who, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: `${name} returned nothing` })
    log(`${name} returned nothing`)
    return null
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
    'the event API→EventBridge→SQS→Lambda chain — usually required for backend work',
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
    return {
      suites: [],
      provisionEnv: false,
      results: [],
      passed: true,
      alreadySatisfied: true,
      reason: 'the contract declares no cross-service, event-chain, or data-pipeline surface, so no integration suite applies',
      ledger: { phase: 'integration', beadId, chosen: [], mode: 'no-applicable-suite', ok: true },
    }
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
      `Provision or reset the integration test environment for this change — event API, EventBridge, SQS, Lambda, and data stores — and seed required fixtures.

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
  return {
    ok: false,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Integration'),
    reason: `integration suite(s) ${deadSuites.join(', ')} returned nothing`,
    passed: false,
    ledger: { phase: 'integration', beadId, chosen: suites, mode: selectionMode, ok: false },
  }
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

return { passed, coverageMet, flaky, failures, evidence, envSetup, suites, provisionEnv, ledger }
