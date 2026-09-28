export const meta = {
  name: 'adversarial',
  description:
    'Shared-tail mini — Adversarial Validation (feeds Gate 4). Attack lanes derived from the declared surfaces and the changed files (or the caller\'s trimmedScope) run concurrently in designated test environments only; one adjudicator rules each confirmed finding constitutive or competitive, and the script returns the count of open constitutive findings as `constitutiveOpen`. When no lane applies the phase reports alreadySatisfied.',
  phases: [
    { title: 'Attack', detail: 'access-control + data-integrity and infra + exposure lanes (concurrent)' },
    { title: 'Adjudicate', detail: 'referee severity; classify constitutive vs competitive' },
  ],
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
  selfContradictory: false,
  attackers,
  laneMode,
  surfaces: declaredSurfaces,
  ...extra,
})

if (!attackers.length) {
  return emptyResult({
    laneMode: 'no-applicable-lane',
    passed: true,
    alreadySatisfied: true,
    reason: 'no attackable surface is declared and the change touches neither source nor dependency manifests',
    ledger: { phase: 'adversarial', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'no-applicable-lane', ok: true },
  })
}

phase('Attack')
const results = await parallel(
  attackers.map((name) => () =>
    settleAgent(`Attempt your attack class against the change. Report only confirmed findings with a minimal reproduction. ${target}${feedback}`, {
      label: `attack:${name}`,
      phase: 'Attack',
      agentType: `agent-teams-workforce:${name}`,
      schema: FINDINGS_SCHEMA,
    })
  )
)
const ledger = { phase: 'adversarial', beadId: (c.bead && c.bead.id) || null, chosen: attackers, mode: laneMode }

const deadLanes = attackers.filter((_, i) => !results[i])
if (deadLanes.length) {
  const reason = `attack lane(s) returned nothing: ${deadLanes.join(', ')}`
  log(`Adversarial: ${reason}`)
  return { dispatchFailed: true, dispatchFailures: dispatchDeaths('Attack'), reason, attackers, laneMode, surfaces: declaredSurfaces, ledger: { ...ledger, ok: false } }
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
  return emptyResult({ ledger: { ...ledger, ok: true } })
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
  return { dispatchFailed: true, dispatchFailures: dispatchDeaths('Adjudicate'), reason, findings, attackers, laneMode, surfaces: declaredSurfaces, ledger: { ...ledger, ok: false } }
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

return {
  findings,
  adjudication: { rulings, constitutiveOpen },
  constitutiveOpen,
  selfContradictory: false,
  attackers,
  laneMode,
  surfaces: declaredSurfaces,
  ledger: { ...ledger, ok: constitutiveOpen === 0 },
}
