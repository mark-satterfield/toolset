export const meta = {
  name: 'gate-enforce',
  description:
    'Reusable phase gate. Evaluates the caller\'s deterministic checks against the artifact first and loops on a failed one with no model turn. Competitive criteria are recorded as flags; only constitutive criteria go to an independent phase-gate-enforcer, which returns pass / loop / escalate. A gate with no constitutive criterion passes on its checks alone. With `mode: \'exhaustion\'` it asks the advantage-evaluator to rule proceed or one directed revision on a gate whose loops are spent.',
  phases: [{ title: 'Gate', detail: 'phase-gate-enforcer adjudicates the artifact' }],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
// Runtime replay identifies calls by their unchanged prompt/options and start order.
// Recovery metadata stays in workflow arguments and never enters those options.
const fableInput = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const fableTypes = new Set((Array.isArray(fableInput.fableAgentTypes) ? fableInput.fableAgentTypes : []).map((name) => String(name).replace(/^agent-teams-workforce:/, '')))
const fablePath = fableInput.fableInvocationPath || 'root'
const fableRecovery = fableInput.fableRecovery && typeof fableInput.fableRecovery === 'object' ? fableInput.fableRecovery : null
let fableAgentOrdinal = 0
let fableChildOrdinal = 0
function fableEvent(event, identity, error = null) {
  log(`FABLE-CALL ${JSON.stringify({ event, ...identity, ...(error === null ? {} : { error }) })}`)
}
async function fableAgent(prompt, options) {
  const identity = { invocationPath: fablePath, ordinal: fableAgentOrdinal++, agentType: (options && options.agentType) || null, label: (options && options.label) || null }
  const isFable = fableTypes.has(String(identity.agentType || '').replace(/^agent-teams-workforce:/, ''))
  const cutoffs = (fableRecovery && fableRecovery.cutoffs) || {}
  const cutoff = Number.isInteger(cutoffs[fablePath]) && cutoffs[fablePath] >= 0 ? cutoffs[fablePath] : 0
  const call = isFable && fableRecovery && identity.ordinal >= cutoff ? { ...options, model: 'opus' } : options
  fableEvent('start', identity)
  try {
    const result = await agent(prompt, call)
    if (!result) fableEvent('failed', identity)
    return result
  } catch (error) {
    const message = String((error && error.message) || error)
    fableEvent('failed', identity, message)
    if (isFable && /out of (?:usage )?credits|seven_day_overage_included|fable.{0,40}(?:limit|allowance)/i.test(message)) return null
    throw error
  }
}
async function fableWorkflow(name, input) {
  const invocationPath = `${fablePath}/${fableChildOrdinal++}:${name}`
  return await workflow(name, {
    ...input,
    fableAgentTypes: fableInput.fableAgentTypes || [],
    fableInvocationPath: invocationPath,
    ...(fableRecovery ? { fableRecovery } : {}),
  })
}
// ===== SHARED BLOCK fable — END =====

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
    const out = await fableWorkflow(name, { ...input, ...(source.retryPolicy && !(input && input.retryPolicy) ? { retryPolicy: source.retryPolicy } : {}) })
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
      const out = await fableAgent(prompt, call)
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
//   attempts: [{attempt, feedback, unmetCriteria}], unmetCriteria: [{criterion, evidence}], final?, gateWorkflow?,
//   noProceed? (a deterministic check failed: proceed is never offered) }
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
  const noProceed = a.noProceed === true
  const rulings = noProceed ? (final ? [] : ['revise']) : final ? ['proceed'] : ['proceed', 'revise']
  if (!rulings.length) {
    log(`${where}: a deterministic check still fails after the directed revision; it is never ruled through`)
    return dispatchOutcome({ verdict: 'ruled', ruling: 'none', directive: null, rationale: 'a deterministic check still fails', residuals: [], decidedBy: null, flags: [] })
  }
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
    return dispatchOutcome({ ...failDispatch(why, 'Gate'), exhaustionRuling: null })
  }
  const directive = String(ruling.directive || '').trim()
  const decided = ruling.ruling === 'revise' && directive ? 'revise' : noProceed ? 'none' : 'proceed'
  log(`${where}: exhausted gate ruled ${decided.toUpperCase()} by the advantage-evaluator — ${String(ruling.rationale).slice(0, 400)}`)
  return dispatchOutcome({
    verdict: 'ruled',
    ruling: decided,
    directive: decided === 'revise' ? directive : null,
    rationale: ruling.rationale,
    residuals: ruling.residuals || [],
    decidedBy: 'agent-teams-workforce:advantage-evaluator',
    flags: (ruling.residuals || []).map((r) => `residual accepted on exhausted gate ${a.gate || '?'}: ${r.criterion} — ${r.mitigation}`),
  })
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
  return dispatchOutcome({
    verdict: 'loop',
    criteria: checkResults,
    feedback: `The phase did not meet a mechanically-verified condition: ${detail}.${phaseReason ? ` The phase reported: ${phaseReason}.` : ''}`,
    flags: [],
    deterministic: true,
    deterministicChecks: checkResults,
  })
}

const constitutiveCriteria = criteria.filter((c) => c.class === 'constitutive')
const competitiveFlags = criteria.filter((c) => c.class === 'competitive').map((c) => `competitive criterion, not adjudicated: ${c.text}`)
if (!constitutiveCriteria.length) {
  log(`${where}: PASS on deterministic checks`)
  return dispatchOutcome({
    verdict: 'pass',
    criteria: checkResults,
    feedback: 'Every deterministic check for this gate holds, and the gate declares no constitutive criterion.',
    flags: competitiveFlags,
    deterministic: true,
    deterministicChecks: checkResults,
  })
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
  return dispatchOutcome({ ...failDispatch(why, 'Gate'), deterministicChecks: checkResults })
}

return dispatchOutcome({
  ...verdict,
  flags: [...(Array.isArray(verdict.flags) ? verdict.flags : []), ...competitiveFlags],
  deterministicChecks: checkResults,
})
