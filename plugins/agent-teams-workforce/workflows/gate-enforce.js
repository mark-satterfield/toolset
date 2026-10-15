export const meta = {
  name: 'gate-enforce',
  description:
    'Reusable phase gate. Evaluates the caller\'s deterministic checks against the artifact first and loops on a failed one with no model turn. Competitive criteria are recorded as flags; only constitutive criteria go to an independent phase-gate-enforcer, which returns pass / loop / escalate. A gate with no constitutive criterion passes on its checks alone. With `mode: \'exhaustion\'` it asks the advantage-evaluator to rule proceed or one directed revision on a gate whose loops are spent.',
  phases: [{ title: 'Gate', detail: 'phase-gate-enforcer adjudicates the artifact' }],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; filled from skills/pipeline-contracts/schemas/driver-surface.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// skills/pipeline-contracts/schemas/driver-surface.schema.json, inlined by shared-blocks.mjs. DRIVER_SURFACE maps
// each x-constant of $defs.DriverEnvironment to its environment variable name and each x-values entry of
// $defs.RateLimitInfo to its wire value, so no workflow names a driver environment variable or a rate-limit value itself.
const DRIVER_SURFACE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"agent-teams-workforce/skills/pipeline-contracts/schemas/driver-surface.schema.json","title":"Driver module surface","description":"The one definition of the driver (ops/sdlc-automation in the control repository) surface the plugin orchestrator imports, the ATW_* environment the driver hands every child and orchestrator process, and the Claude CLI rate-limit event the driver's quota readers take. scripts/generate_types.py renders scripts/driver_surface_types.py from this file; scripts/check_generated.py fails when that module is stale.","x-driver":{"dirParts":["ops","sdlc-automation"],"dirDoc":"Path parts of the driver directory under ATW_CONTROL_REPO.","modules":[{"module":"headlessenv","constant":"HEADLESSENV_MODULE","protocol":"HeadlessEnvironment","doc":"Driver headlessenv module surface consumed by session setup.","members":[{"name":"DENIED_TOOLS","kind":"attribute","python":"tuple[str, ...]","doc":"Tools every headless and orchestrator agent session is denied, in order."},{"name":"child_env","kind":"method","params":[["scratch","Path"]],"returns":"dict[str, str]","doc":"Build the subprocess environment: DriverEnvironment over the inherited one."}]},{"module":"fablewall","constant":"FABLEWALL_MODULE","protocol":"FableWall","doc":"Driver fablewall module surface consumed by model fallback.","members":[{"name":"is_refusal","kind":"method","params":[["info","object"]],"returns":"bool","doc":"Return whether a RateLimitInfo is a model-specific refusal."},{"name":"reset_of","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the model-specific reset of a RateLimitInfo, in epoch seconds."}]},{"module":"breaker","constant":"BREAKER_MODULE","protocol":"Breaker","doc":"Driver breaker module surface consumed by quota handling.","members":[{"name":"exhausted_reset","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the latest reset among the exhausted windows, in epoch seconds."}]},{"module":"childproc","constant":"CHILDPROC_MODULE","protocol":"ChildProcess","doc":"Driver childproc module termination policy.","members":[{"name":"TERMINATE_GRACE","kind":"attribute","python":"float","doc":"Seconds a terminated child is given before it is killed."}]}]},"$defs":{"DriverEnvironment":{"description":"The ATW_* and process environment the driver hands child and orchestrator processes.","x-details":"headlessenv.child_env(scratch) returns these keys over the inherited os.environ (atw.environment fills only absent or blank values); the keeper, supervisor and orchestrator dispatch add ATW_STOP_FILE, ATW_EXECUTION_ID and ATW_ORCH_IDLE.","type":"object","x-python":{"typeddict":"DriverEnvironment"},"properties":{"ATW_PROJECT_ROOT":{"type":"string","minLength":1,"description":"Absolute path of the project root.","x-constant":"PROJECT_ROOT_ENV"},"ATW_PRD_EPIC_SYNC":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic sync script.","x-constant":"PRD_EPIC_SYNC_ENV"},"ATW_PRD_EPIC_VERIFY":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic verify script.","x-constant":"PRD_EPIC_VERIFY_ENV"},"ATW_CONTROL_REPO":{"type":"string","minLength":1,"description":"Absolute path of the control repository (SKILLSPOKE_CC, else the driver's repository root). The driver modules live under it at DRIVER_DIR_PARTS.","x-constant":"CONTROL_REPO_ENV"},"ATW_ARCH_PATH":{"type":"string","minLength":1,"description":"The architecture root; set only when the driver knows one. Readers use args.archPath first and fall back to it.","x-constant":"ARCH_PATH_ENV"},"ATW_DESIGN_PACKAGES_DIR":{"type":"string","minLength":1,"description":"The owner's cds design packages directory; optional.","x-constant":"DESIGN_PACKAGES_ENV"},"ATW_PRD_DIR":{"type":"string","minLength":1,"description":"The first PRD root; optional.","x-constant":"PRD_DIR_ENV"},"PATH":{"type":"string","minLength":1,"description":"The controller runtime's bin directory first, de-duplicated.","x-constant":"PATH_ENV"},"TMPDIR":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMPDIR_ENV","x-group":"SCRATCH_ENV_KEYS"},"TMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"TEMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TEMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS":{"type":"string","const":"0","description":"Disables the Claude CLI print-mode background wait.","x-constant":"BACKGROUND_WAIT_KEY","x-const-mapping":"BACKGROUND_WAIT_ENV"},"ATW_STOP_FILE":{"type":"string","minLength":1,"description":"Path of the stop marker file; absent means no stop marker. A consumer touches the file (mode 0o600) to request a drain, or tests whether it exists. It only requests a stop: how a stop is classified belongs to the handback contract.","x-constant":"STOP_FILE_ENV","x-file-mode":"STOP_FILE_MODE"},"ATW_EXECUTION_ID":{"type":"string","minLength":1,"description":"The driver execution id. Required for an orchestrator dispatch; set for a headless workflow session only when its arguments carry an executionId.","x-constant":"EXECUTION_ID_ENV"},"ATW_ORCH_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"3600","description":"Orchestrator idle limit in seconds: a positive finite float. A non-finite or non-positive value is a ValueError.","x-constant":"ORCH_IDLE_ENV","x-default-constant":"ORCH_IDLE_DEFAULT"}},"required":["ATW_PROJECT_ROOT","ATW_PRD_EPIC_SYNC","ATW_PRD_EPIC_VERIFY","ATW_CONTROL_REPO","PATH","TMPDIR","TMP","TEMP","CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"],"additionalProperties":{"type":"string"}},"StopFileMode":{"description":"Permission bits a consumer creates the stop marker file with.","type":"integer","const":384,"x-python":{"constant":"STOP_FILE_MODE","type":"int","render":"0o600"}},"DeniedTool":{"description":"A tool every headless and orchestrator agent session is denied. DENIED_TOOLS keeps this order.","type":"string","enum":["WebFetch","WebSearch","Artifact","SendMessage","EndConversation","CronCreate","CronDelete","CronList","mcp__claude_ai_Gmail__send_message","mcp__claude_ai_Gmail__reply","mcp__claude_ai_Gmail__forward","mcp__claude_ai_Gmail__create_draft","mcp__claude_ai_Google_Drive__share_file","mcp__claude_ai_Google_Drive__create_file","mcp__plugin_slack_slack__slack_send_message","mcp__plugin_slack_slack__slack_send_message_draft","mcp__plugin_slack_slack__slack_schedule_message"],"x-python":{"literal":"DeniedTool","tuple":"DENIED_TOOLS"}},"TerminateGrace":{"description":"Seconds a terminated child process is given before it is killed.","type":"number","const":10,"x-python":{"constant":"TERMINATE_GRACE","type":"float"}},"ExhaustedUtilization":{"description":"A usage window whose utilization is at or above this value is exhausted.","type":"number","const":1,"x-python":{"constant":"EXHAUSTED_UTILIZATION","type":"float"}},"RateLimitStatus":{"description":"RateLimitInfo.status; only rejected is acted on.","type":"string","enum":["allowed","allowed_warning","rejected"],"x-python":{"literal":"RateLimitStatus","tuple":"RATE_LIMIT_STATUSES","constants":{"rejected":"REJECTED_STATUS"}}},"UsageWindowName":{"description":"The account-wide usage windows. Any other window name is model-specific.","type":"string","enum":["five_hour","seven_day"],"x-python":{"literal":"UsageWindowName","frozenset":"ACCOUNT_WINDOWS"}},"UsageWindow":{"description":"One usage window of a RateLimitInfo.","type":"object","x-python":{"typeddict":"UsageWindow"},"properties":{"utilization":{"type":"number","description":"Exhausted when at or above EXHAUSTED_UTILIZATION."},"resetsAt":{"type":"number","description":"Reset time in epoch seconds."}},"required":["utilization"]},"RateLimitInfo":{"description":"The rate_limit_info of a rate_limit_event: the info argument of the quota readers.","type":"object","x-python":{"typeddict":"RateLimitInfo"},"properties":{"status":{"$ref":"#/$defs/RateLimitStatus"},"unifiedWindows":{"type":"object","additionalProperties":{"$ref":"#/$defs/UsageWindow"},"description":"Window name -> usage window."},"resetsAt":{"type":"number","description":"Top-level reset time in epoch seconds."},"rateLimitType":{"type":"string","description":"The value with meaning here is MODEL_OVERAGE_TYPE.","x-values":{"MODEL_OVERAGE_TYPE":"seven_day_overage_included"}},"overageDisabledReason":{"type":"string","description":"The value with meaning here is OUT_OF_CREDITS_REASON.","x-values":{"OUT_OF_CREDITS_REASON":"out_of_credits"}}},"required":["status"]},"RateLimitEvent":{"description":"One Claude CLI stream-json rate-limit event.","type":"object","x-python":{"typeddict":"RateLimitEvent"},"properties":{"type":{"type":"string","const":"rate_limit_event","x-value-constant":"RATE_LIMIT_EVENT_TYPE"},"rate_limit_info":{"$ref":"#/$defs/RateLimitInfo","x-key-constant":"RATE_LIMIT_INFO_KEY"}},"required":["type","rate_limit_info"]}}}
const DRIVER_SURFACE = (() => {
  const defs = (DRIVER_SURFACE_SCHEMA && DRIVER_SURFACE_SCHEMA.$defs) || {}
  const env = defs.DriverEnvironment && defs.DriverEnvironment.properties
  const info = defs.RateLimitInfo && defs.RateLimitInfo.properties
  if (!env || !info) throw new Error('shared block fable: DRIVER_SURFACE_SCHEMA was not filled from skills/pipeline-contracts/schemas/driver-surface.schema.json (run node scripts/shared-blocks.mjs --write)')
  const named = {}
  for (const [key, spec] of Object.entries(env)) if (spec && typeof spec['x-constant'] === 'string') named[spec['x-constant']] = key
  for (const spec of Object.values(info)) if (spec && spec['x-values'] && typeof spec['x-values'] === 'object') Object.assign(named, spec['x-values'])
  return Object.freeze(named)
})()
const driverSurfaceRe = (value) => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const FABLE_EXHAUSTED = new RegExp(`out of (?:usage )?credits|${driverSurfaceRe(DRIVER_SURFACE.MODEL_OVERAGE_TYPE)}|${driverSurfaceRe(DRIVER_SURFACE.OUT_OF_CREDITS_REASON)}|fable.{0,40}(?:limit|allowance)`, 'i')
// The model allowance: the driver names the agent types that run on the allowance-limited model
// (fableAgentTypes). When that model refused a call of an earlier dispatch, the driver passes
// fableFallback true and every such agent runs on the fallback model for this dispatch.
const fableInput = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const fableTypes = new Set((Array.isArray(fableInput.fableAgentTypes) ? fableInput.fableAgentTypes : []).map((name) => String(name).replace(/^agent-teams-workforce:/, '')))
const fablePath = fableInput.fableInvocationPath || 'root'
const fableFallback = fableInput.fableFallback === true
let fableChildOrdinal = 0
// The last call the model allowance refused in this script: { agentType, label, message }, or null.
let fableRefusal = null
// An agent is started by its plain front-matter name; Claude Code loads its definition and preloads
// the skills its front matter lists, so nothing here reads or passes on an agent's or a skill's text.
async function fableAgent(prompt, options) {
  const schema = options && options.schema
  const artifactSchema = schema && schema.type === 'object' && Array.isArray(schema.required) && schema.required.length === 1 && schema.required[0] === 'artifactPath' && schema.properties && schema.properties.artifactPath && schema.properties.artifactPath.type === 'string'
  const outputMode = ['artifact', 'inline', 'machine'].includes(options && options.outputMode) ? options.outputMode : artifactSchema ? 'artifact' : 'inline'
  const { outputMode: _mode, ...runtimeOptions } = options || {}
  options = runtimeOptions
  const agentType = (options && options.agentType) || null
  const isFable = fableTypes.has(String(agentType || '').replace(/^agent-teams-workforce:/, ''))
  const call = isFable && fableFallback ? { ...options, model: 'opus' } : options
  try {
    return await agent(`OUTPUT_MODE: ${outputMode}\n\n${prompt}`, call)
  } catch (error) {
    const message = String((error && error.message) || error)
    if (!isFable || !FABLE_EXHAUSTED.test(message)) throw error
    fableRefusal = { agentType, label: (options && options.label) || null, message }
    log(`${fableRefusal.label || agentType}: the model allowance refused this call: ${message.slice(0, 300)}`)
    return null
  }
}
async function fableWorkflow(name, input) {
  const invocationPath = `${fablePath}/${fableChildOrdinal++}:${name}`
  return await workflow(name, {
    ...input,
    fableAgentTypes: fableInput.fableAgentTypes || [],
    fableInvocationPath: invocationPath,
    ...(fableInput.relayExecutionId ? { relayExecutionId: fableInput.relayExecutionId } : {}),
    ...(fableInput.relayRequestDir ? { relayRequestDir: fableInput.relayRequestDir } : {}),
    ...(fableInput.relayCaptureScript ? { relayCaptureScript: fableInput.relayCaptureScript } : {}),
    ...(fableFallback ? { fableFallback } : {}),
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
      agentType: 'advantage-evaluator',
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
    decidedBy: 'advantage-evaluator',
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
    agentType: 'phase-gate-enforcer',
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
