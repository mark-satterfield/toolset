export const meta = {
  name: 'adversarial',
  description:
    'Shared-tail mini — Adversarial Validation. Attack lanes run concurrently in designated test environments only: the caller\'s trimmedScope when given, otherwise lanes derived from the declared surfaces plus a data-exposure and dependency-CVE baseline conditioned on the changed files, otherwise every lane. One adversarial-critique-adjudicator rules each confirmed finding constitutive or competitive (skipped when there are no findings), and the script returns the count of open constitutive findings as `constitutiveOpen`. A lane or the adjudicator returning nothing reports dispatchFailed. When no lane applies the phase reports alreadySatisfied.',
  phases: [
    { title: 'Attack', detail: 'access-control + data-integrity and infra + exposure lanes (concurrent)' },
    { title: 'Adjudicate', detail: 'referee severity; classify constitutive vs competitive' },
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

// args: { contract, green, trimmedScope?, feedback?, priorRulings? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const feedback = a.feedback ? `\nPrior gate feedback to address:\n${a.feedback}` : ''
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim() || '(repo path not provided)'
const target = `Change under attack: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}. Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}. DESIGNATED TEST ENVIRONMENTS ONLY — never attack production. Work within: ${repo}`

// Returns `<lane>#<normalized prefix>-<FNV-1a hash>` of a finding's reproduction.
function findingIdFor(lane, finding) {
  const norm = String((finding && finding.reproduction) || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  if (!norm) return `${lane}#unspecified`
  let h = 2166136261
  for (let i = 0; i < norm.length; i++) h = Math.imul(h ^ norm.charCodeAt(i), 16777619)
  return `${lane}#${norm.slice(0, 40)}-${(h >>> 0).toString(16).padStart(8, '0')}`
}

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'severity', 'reproduction'],
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
          reproduction: { type: 'string' },
        },
      },
    },
  },
}

const accessLane = [
  'injection-attack-tester',
  'auth-bypass-tester',
  'permission-escalation-tester',
  'race-condition-tester',
  'contract-violation-tester',
]
const infraLane = [
  'dependency-cve-auditor',
  'dos-resilience-tester',
  'data-exposure-scanner',
  'infrastructure-security-scanner',
]
const allAttackers = [...accessLane, ...infraLane]
// Attackers that run from the user-level agents directory, dispatched by their plain name.
const USER_LEVEL_AGENTS = new Set(['infrastructure-security-scanner'])
const requested = Array.isArray(a.trimmedScope) ? allAttackers.filter((n) => a.trimmedScope.includes(n)) : []

const changedFiles = Array.isArray(green.changedFiles) && green.changedFiles.length ? green.changedFiles : null
const DEP_MANIFEST_RE = /(^|\/)(package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|pyproject\.toml|requirements[^/]*\.txt|uv\.lock|poetry\.lock|Pipfile|Pipfile\.lock|go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|Gemfile|Gemfile\.lock|pom\.xml|build\.gradle(\.kts)?)$/
const NON_SOURCE_DIR_RE = /(^|\/)(tests?|spec|__tests__|__mocks__|docs?|\.github|fixtures)\//i
const NON_SOURCE_EXT_RE = /\.(md|mdx|rst|txt|ya?ml|json|toml|ini|cfg|lock|snap|csv)$/i
const depsChanged = changedFiles === null || changedFiles.some((f) => DEP_MANIFEST_RE.test(f))
const sourceChanged = changedFiles === null || changedFiles.some((f) => !NON_SOURCE_DIR_RE.test(f) && !NON_SOURCE_EXT_RE.test(f))
const BASELINE_ATTACKERS = [sourceChanged ? 'data-exposure-scanner' : null, depsChanged ? 'dependency-cve-auditor' : null].filter(Boolean)
const SURFACE_ATTACKERS = {
  auth: ['auth-bypass-tester', 'permission-escalation-tester'],
  'api-contract': ['injection-attack-tester', 'contract-violation-tester'],
  'event-chain': ['race-condition-tester', 'contract-violation-tester'],
  'web-ui': ['injection-attack-tester'],
  performance: ['dos-resilience-tester'],
  'data-pipeline': ['race-condition-tester'],
}
const declaredSurfaces = Array.isArray(c.surfaces) ? c.surfaces : null

let attackers
let laneMode
if (requested.length) {
  const baselineLane = { 'dependency-cve-auditor': depsChanged, 'data-exposure-scanner': sourceChanged }
  attackers = requested.filter((n) => baselineLane[n] !== false)
  laneMode = 'trimmed-by-caller'
} else if (declaredSurfaces) {
  attackers = [...new Set([...BASELINE_ATTACKERS, ...declaredSurfaces.flatMap((s) => SURFACE_ATTACKERS[s] || [])])].filter((n) =>
    allAttackers.includes(n)
  )
  laneMode = 'derived-from-surfaces'
} else {
  attackers = allAttackers
  laneMode = 'all-lanes'
}
log(`Adversarial lanes (${laneMode}): ${attackers.join(', ') || 'none'}`)

const emptyResult = (extra) => ({
  findings: [],
  adjudication: { rulings: [], constitutiveOpen: 0 },
  constitutiveOpen: 0,
  attackers,
  laneMode,
  surfaces: declaredSurfaces,
  ...extra,
})

if (!attackers.length) {
  return dispatchOutcome(emptyResult({
    laneMode: 'no-applicable-lane',
    passed: true,
    alreadySatisfied: true,
    reason: 'no attackable surface is declared and the change touches neither source nor dependency manifests',
    ledger: { phase: 'adversarial', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'no-applicable-lane', ok: true },
  }))
}

phase('Attack')
const results = await parallel(
  attackers.map((name) => () =>
    settleAgent(`Attempt your attack class against the change. Report only confirmed findings with a minimal reproduction. ${target}${feedback}`, {
      label: `attack:${name}`,
      phase: 'Attack',
      agentType: USER_LEVEL_AGENTS.has(name) ? name : `agent-teams-workforce:${name}`,
      schema: FINDINGS_SCHEMA,
    })
  )
)
const ledger = { phase: 'adversarial', beadId: (c.bead && c.bead.id) || null, chosen: attackers, mode: laneMode }

const deadLanes = attackers.filter((_, i) => !results[i])
if (deadLanes.length) {
  const reason = `attack lane(s) returned nothing: ${deadLanes.join(', ')}`
  log(`Adversarial: ${reason}`)
  return dispatchOutcome({ dispatchFailed: true, dispatchFailures: dispatchDeaths('Attack'), reason, attackers, laneMode, surfaces: declaredSurfaces, ledger: { ...ledger, ok: false } })
}

const findings = []
const seenIds = new Set()
results.forEach((r, i) => {
  for (const f of (r && r.findings) || []) {
    const findingId = findingIdFor(attackers[i], f)
    if (seenIds.has(findingId)) continue
    seenIds.add(findingId)
    findings.push({ ...f, lane: attackers[i], findingId })
  }
})

if (!findings.length) {
  log(`Adversarial: ${attackers.length} lane(s) ran and confirmed no finding`)
  return dispatchOutcome(emptyResult({ ledger: { ...ledger, ok: true } }))
}

phase('Adjudicate')
const adjudication = await settleAgent(
  `You are the adversarial-critique-adjudicator (Referee). Rule on each finding's real severity and whether it is CONSTITUTIVE (a security/validity hard stop — implementers cannot downgrade it) or COMPETITIVE (a tradeable quality concern). Discard false positives with reasoning. Return one ruling per findingId.

Findings (${findings.length}):
${JSON.stringify(findings, null, 2)}`,
  {
    label: 'adversarial:adjudicate',
    phase: 'Adjudicate',
    agentType: 'agent-teams-workforce:adversarial-critique-adjudicator',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['rulings'],
      properties: {
        rulings: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['findingId', 'title', 'severity', 'classification', 'real'],
            properties: {
              findingId: { type: 'string', enum: findings.map((f) => f.findingId) },
              title: { type: 'string' },
              severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
              classification: { type: 'string', enum: ['constitutive', 'competitive'] },
              real: { type: 'boolean' },
            },
          },
        },
      },
    },
  }
)

if (!adjudication) {
  const reason = `the adversarial-critique-adjudicator returned nothing — ${findings.length} confirmed finding(s) were not adjudicated`
  log(`Adversarial: ${reason}`)
  return dispatchOutcome({ dispatchFailed: true, dispatchFailures: dispatchDeaths('Adjudicate'), reason, findings, attackers, laneMode, surfaces: declaredSurfaces, ledger: { ...ledger, ok: false } })
}

const byId = {}
for (const r of Array.isArray(adjudication.rulings) ? adjudication.rulings : []) {
  if (r && r.findingId && !byId[r.findingId]) byId[r.findingId] = r
}
for (const f of findings) {
  if (byId[f.findingId]) continue
  const blocking = f.severity === 'critical' || f.severity === 'high'
  byId[f.findingId] = { findingId: f.findingId, title: f.title, severity: f.severity, classification: blocking ? 'constitutive' : 'competitive', real: true, unadjudicated: true }
}
const rulings = Object.keys(byId).map((k) => byId[k])
const constitutiveOpen = rulings.filter((r) => r.real === true && r.classification === 'constitutive').length

return dispatchOutcome({
  findings,
  adjudication: { rulings, constitutiveOpen },
  constitutiveOpen,
  attackers,
  laneMode,
  surfaces: declaredSurfaces,
  ledger: { ...ledger, ok: constitutiveOpen === 0 },
})
