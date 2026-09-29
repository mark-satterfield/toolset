export const meta = {
  name: 'gate-enforce',
  description:
    'Reusable phase gate. Evaluates the caller\'s deterministic checks against the artifact first and loops on a failed one with no model turn. Competitive criteria are recorded as flags; only constitutive criteria go to an independent phase-gate-enforcer, which returns pass / loop / escalate. A gate with no constitutive criterion passes on its checks alone. With `mode: \'exhaustion\'` it asks the advantage-evaluator to rule proceed or one directed revision on a gate whose loops are spent.',
  phases: [{ title: 'Gate', detail: 'phase-gate-enforcer adjudicates the artifact' }],
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

// Returns an escalate verdict that carries the dispatch failures of the named phases.
const failDispatch = (reason, ...phases) => {
  const deaths = dispatchDeaths(...phases)
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: reason,
    escalateTo: 'upstream',
    flags: [`gate-dispatch-failed: ${reason}`],
    ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
  }
}

// args: {
//   gate: string,
//   phaseName: string,
//   criteria: (string | { text: string, class?: 'constitutive'|'competitive' })[],  // a plain string is competitive
//   calibration?: string,
//   checks?: [{ field, equals?, nonEmpty?, matches?, notMatches?, label? }],  // matches/notMatches: regex source, case-insensitive
//   artifact: any,
//   escalateTargets?: string[],
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const where = `Gate ${a.gate || '?'} (${a.phaseName || 'phase'})`

const criteria = (Array.isArray(a.criteria) ? a.criteria : [])
  .map((c) => {
    if (typeof c === 'string') return { text: c, class: 'competitive' }
    if (c && typeof c === 'object' && typeof c.text === 'string') {
      return { text: c.text, class: c.class === 'constitutive' ? 'constitutive' : 'competitive' }
    }
    return null
  })
  .filter(Boolean)

const PROMPT_STRING_CAP = 6000
const PROMPT_STRING_HEAD = 4000
const PROMPT_STRING_TAIL = 2000
// Returns the value with every string longer than PROMPT_STRING_CAP cut to its head and tail.
function capForPrompt(value, depth) {
  if (typeof value === 'string') {
    if (value.length <= PROMPT_STRING_CAP) return value
    const omitted = value.length - PROMPT_STRING_HEAD - PROMPT_STRING_TAIL
    return `${value.slice(0, PROMPT_STRING_HEAD)}\n…[${omitted} characters omitted]…\n${value.slice(-PROMPT_STRING_TAIL)}`
  }
  if (!value || typeof value !== 'object' || depth > 8) return value
  if (Array.isArray(value)) return value.map((v) => capForPrompt(v, depth + 1))
  const out = {}
  for (const [k, v] of Object.entries(value)) out[k] = capForPrompt(v, depth + 1)
  return out
}
const artifactText =
  typeof a.artifact === 'string' ? capForPrompt(a.artifact, 0) : JSON.stringify(capForPrompt(a.artifact ?? {}, 0), null, 2)

// args (mode 'exhaustion'): { mode, gate, phaseName, criteria, checks, artifact,
//   attempts: [{attempt, feedback, unmetCriteria}], unmetCriteria: [{criterion, evidence}], final?, gateWorkflow? }
if (a.mode === 'exhaustion') {
  phase('Gate')
  const history = (Array.isArray(a.attempts) ? a.attempts : [])
    .map((x, i) => {
      const unmetList = (Array.isArray(x && x.unmetCriteria) ? x.unmetCriteria : [])
        .map((u) => `    - ${u.criterion}${u.evidence ? ` — ${u.evidence}` : ''}`)
        .join('\n')
      return `  Loop ${(x && x.attempt) || i + 1}: feedback given — ${String((x && x.feedback) || '(none)').slice(0, 1500)}${unmetList ? `\n${unmetList}` : ''}`
    })
    .join('\n')
  const unmetNow = (Array.isArray(a.unmetCriteria) ? a.unmetCriteria : [])
    .map((u) => `- ${u.criterion}${u.evidence ? ` — ${u.evidence}` : ''}`)
    .join('\n')
  const criteriaText = (Array.isArray(a.criteria) ? a.criteria : [])
    .map((c, i) => `${i + 1}. ${typeof c === 'string' ? c : (c && c.text) || ''}${c && c.class ? ` [${c.class}]` : ''}`)
    .join('\n')
  const final = a.final === true
  const rulings = final ? ['proceed'] : ['proceed', 'revise']
  const ruling = await settleAgent(
    `You are the advantage-evaluator, ruling on an EXHAUSTED GATE. You did not produce this work and you did not judge it at the gate. Your ruling decides how the run continues.

${where}${a.gateWorkflow ? ` — judged by ${a.gateWorkflow}` : ''}

The gate's criteria:
${criteriaText || '(none recorded)'}

What the loops asked for, in order:
${history || '  (no loop history recorded)'}

Still unmet on the latest output:
${unmetNow || '- (the last verdict itemised no unmet criterion)'}

The phase's latest output:
${artifactText}

Rule exactly one of: ${rulings.map((r) => `"${r}"`).join(', ')}.
- "proceed": the latest output stands and the run continues from it. For EVERY criterion still unmet, return one \`residuals\` entry naming the criterion, why proceeding is acceptable, and the mitigation the downstream phases must honour.${final ? '' : `
- "revise": the phase runs ONCE more under your \`directive\`: a concrete, changed instruction that you expect to close the unmet criteria.`}
Do not modify any artifact and do not dispatch any work.`,
    {
      label: `exhaustion:${a.gate || a.phaseName || 'phase'}`,
      phase: 'Gate',
      effort: 'high',
      agentType: 'agent-teams-workforce:advantage-evaluator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['ruling', 'rationale', 'residuals'],
        properties: {
          ruling: { type: 'string', enum: rulings },
          rationale: { type: 'string' },
          directive: { type: 'string' },
          residuals: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['criterion', 'reason', 'mitigation'],
              properties: {
                criterion: { type: 'string' },
                reason: { type: 'string' },
                mitigation: { type: 'string' },
              },
            },
          },
        },
      },
    }
  )
  if (!ruling) {
    const why = `${where}: the advantage-evaluator returned no ruling on the exhausted gate`
    log(why)
    return { ...failDispatch(why, 'Gate'), exhaustionRuling: null }
  }
  const directive = String(ruling.directive || '').trim()
  const decided = ruling.ruling === 'revise' && directive ? 'revise' : 'proceed'
  log(`${where}: exhausted gate ruled ${decided.toUpperCase()} by the advantage-evaluator — ${String(ruling.rationale).slice(0, 400)}`)
  return {
    verdict: 'ruled',
    ruling: decided,
    directive: decided === 'revise' ? directive : null,
    rationale: ruling.rationale,
    residuals: ruling.residuals || [],
    decidedBy: 'agent-teams-workforce:advantage-evaluator',
    flags: (ruling.residuals || []).map((r) => `residual accepted on exhausted gate ${a.gate || '?'}: ${r.criterion} — ${r.mitigation}`),
  }
}

const checks = (Array.isArray(a.checks) ? a.checks : []).filter((c) => c && typeof c === 'object' && typeof c.field === 'string' && c.field)
// Returns true when the value holds a non-blank string, a non-empty object, or an array with such an item.
function hasContent(value) {
  if (value === undefined || value === null) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.some((v) => hasContent(v))
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}
function asText(value) {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map((v) => asText(v)).join('\n')
  return JSON.stringify(value)
}
// Returns the pattern as a case-insensitive RegExp, or null when the source does not compile.
function compile(source) {
  try {
    return new RegExp(source, 'i')
  } catch {
    return null
  }
}
const checkResults = checks
  .map((chk) => {
    const value = a.artifact ? a.artifact[chk.field] : undefined
    const observed = JSON.stringify(value)
    let evidence = `observed ${chk.field} = ${observed !== undefined && observed.length > 300 ? `${observed.slice(0, 300)}… (${observed.length} characters)` : observed}`
    let met
    if (Object.prototype.hasOwnProperty.call(chk, 'equals')) met = value === chk.equals
    else if (chk.nonEmpty) met = hasContent(value)
    else if (chk.matches || chk.notMatches) {
      const source = chk.matches || chk.notMatches
      const re = compile(source)
      if (!re) return null
      const text = asText(value)
      const hit = re.test(text)
      met = chk.matches ? hit : !hit
      evidence = `${chk.matches ? 'required' : 'forbidden'} pattern /${source}/i ${hit ? 'MATCHED' : 'did not match'} ${chk.field}: ${JSON.stringify(text.length > 300 ? `${text.slice(0, 300)}…` : text)}`
    } else met = value !== undefined && value !== null
    return { criterion: chk.label || `${chk.field} satisfies its required shape`, met, evidence }
  })
  .filter(Boolean)
const failedChecks = checkResults.filter((r) => !r.met)

phase('Gate')

if (failedChecks.length) {
  const detail = failedChecks.map((r) => `${r.criterion} — ${r.evidence}`).join('; ')
  const art = a.artifact && typeof a.artifact === 'object' ? a.artifact : {}
  const phaseReason = [art.reason, art.error, Array.isArray(art.failures) ? art.failures.join('; ') : '']
    .map((v) => (typeof v === 'string' ? v.trim() : ''))
    .filter(Boolean)
    .join(' | ')
    .slice(0, 2000)
  log(`${where}: LOOP on deterministic check(s) — ${detail}`)
  return {
    verdict: 'loop',
    criteria: checkResults,
    feedback: `The phase did not meet a mechanically-verified condition: ${detail}.${phaseReason ? ` The phase reported: ${phaseReason}.` : ''}`,
    flags: [],
    deterministic: true,
    deterministicChecks: checkResults,
  }
}

const constitutiveCriteria = criteria.filter((c) => c.class === 'constitutive')
const competitiveFlags = criteria.filter((c) => c.class === 'competitive').map((c) => `competitive criterion, not adjudicated: ${c.text}`)
if (!constitutiveCriteria.length) {
  log(`${where}: PASS on deterministic checks`)
  return {
    verdict: 'pass',
    criteria: checkResults,
    feedback: 'Every deterministic check for this gate holds, and the gate declares no constitutive criterion.',
    flags: competitiveFlags,
    deterministic: true,
    deterministicChecks: checkResults,
  }
}

const settledBlock = checkResults.length
  ? `\nAlready SETTLED by direct inspection of the artifact — treat these as met and do NOT re-open them:\n${checkResults.map((r) => `- ${r.criterion} (${r.evidence})`).join('\n')}\n`
  : ''
const calibrationBlock = a.calibration ? `\nCALIBRATION FOR THIS GATE — what this gate must block on and what it must not:\n${a.calibration}\n` : ''

const verdict = await settleAgent(
  `You are the phase-gate-enforcer — an INDEPENDENT gate authority. You did not produce this work; you only judge it. Do NOT modify the artifact.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}

Criteria — every one is CONSTITUTIVE: it defines whether the work is valid at all:
${constitutiveCriteria.map((c, i) => `${i + 1}. ${c.text}`).join('\n')}
${calibrationBlock}${settledBlock}
Artifact under review:
${artifactText}

Decide exactly one verdict:
- "pass": every criterion above is met. Put any non-blocking quality concern in \`flags\`.
- "loop": a criterion is unmet AND the root cause is INSIDE this phase. Return feedback specific enough that the phase can retry without interpretation.
- "escalate": a criterion is unmet and the failure originates UPSTREAM. Name where it goes back to${a.escalateTargets && a.escalateTargets.length ? ` (options: ${a.escalateTargets.join(', ')})` : ''}.

Loop or escalate only on a criterion listed above. Judge the artifact quoted above; do not survey the repository. For each criterion, state whether it is met with evidence, quoting the criterion text exactly.`,
  {
    label: `gate:${a.gate || a.phaseName || 'phase'}`,
    effort: 'medium',
    phase: 'Gate',
    agentType: 'agent-teams-workforce:phase-gate-enforcer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['verdict', 'criteria', 'feedback'],
      properties: {
        verdict: { type: 'string', enum: ['pass', 'loop', 'escalate'] },
        criteria: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['criterion', 'met', 'evidence'],
            properties: {
              criterion: { type: 'string' },
              met: { type: 'boolean' },
              evidence: { type: 'string' },
            },
          },
        },
        feedback: { type: 'string' },
        escalateTo: { type: 'string' },
        flags: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

if (!verdict) {
  const why = `${where}: the phase-gate-enforcer returned no verdict; every deterministic check for this gate held`
  log(why)
  return { ...failDispatch(why, 'Gate'), deterministicChecks: checkResults }
}

return {
  ...verdict,
  flags: [...(Array.isArray(verdict.flags) ? verdict.flags : []), ...competitiveFlags],
  deterministicChecks: checkResults,
}
