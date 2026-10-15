export const meta = {
  name: 'adversarial',
  description:
    'Shared-tail mini — Adversarial Validation. Attack lanes run concurrently in designated test environments only: the caller\'s trimmedScope when given, otherwise lanes derived from the declared surfaces plus a data-exposure and dependency-CVE baseline conditioned on the changed files, otherwise every lane. One adversarial-critique-adjudicator rules each confirmed finding constitutive or competitive (skipped when there are no findings), and the script returns the count of open constitutive findings as `constitutiveOpen`. A lane or the adjudicator returning nothing reports dispatchFailed. When no lane applies the phase reports alreadySatisfied.',
  phases: [
    { title: 'Attack', detail: 'access-control + data-integrity and infra + exposure lanes (concurrent)' },
    { title: 'Adjudicate', detail: 'referee severity; classify constitutive vs competitive' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; filled from skills/pipeline-contracts/schemas/driver-surface.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// skills/pipeline-contracts/schemas/driver-surface.schema.json, inlined by shared-blocks.mjs. DRIVER_SURFACE maps
// each x-constant of $defs.DriverEnvironment to its environment variable name and each x-values entry of
// $defs.RateLimitInfo to its wire value, so no workflow names a driver environment variable or a rate-limit value itself.
const DRIVER_SURFACE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"agent-teams-workforce/skills/pipeline-contracts/schemas/driver-surface.schema.json","title":"Driver module surface","description":"The one definition of the driver (ops/sdlc-automation in the control repository) surface the plugin orchestrator imports, the ATW_* environment the driver hands every child and orchestrator process, and the Claude CLI rate-limit event the driver's quota readers take. scripts/generate_types.py renders scripts/driver_surface_types.py from this file; scripts/check_generated.py fails when that module is stale.","x-driver":{"dirParts":["ops","sdlc-automation"],"dirDoc":"Path parts of the driver directory under ATW_CONTROL_REPO.","modules":[{"module":"headlessenv","constant":"HEADLESSENV_MODULE","protocol":"HeadlessEnvironment","doc":"Driver headlessenv module surface consumed by session setup.","members":[{"name":"DENIED_TOOLS","kind":"attribute","python":"tuple[str, ...]","doc":"Tools every headless build and deploy Workflow session the driver dispatches is denied, in order."},{"name":"child_env","kind":"method","params":[["scratch","Path"]],"returns":"dict[str, str]","doc":"Build the subprocess environment: DriverEnvironment over the inherited one."}]},{"module":"fablewall","constant":"FABLEWALL_MODULE","protocol":"FableWall","doc":"Driver fablewall module surface consumed by model fallback.","members":[{"name":"is_refusal","kind":"method","params":[["info","object"]],"returns":"bool","doc":"Return whether a RateLimitInfo is a model-specific refusal."},{"name":"reset_of","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the model-specific reset of a RateLimitInfo, in epoch seconds."}]},{"module":"breaker","constant":"BREAKER_MODULE","protocol":"Breaker","doc":"Driver breaker module surface consumed by quota handling.","members":[{"name":"exhausted_reset","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the latest reset among the exhausted windows, in epoch seconds."}]},{"module":"childproc","constant":"CHILDPROC_MODULE","protocol":"ChildProcess","doc":"Driver childproc module termination policy.","members":[{"name":"TERMINATE_GRACE","kind":"attribute","python":"float","doc":"Seconds a terminated child is given before it is killed."}]}]},"$defs":{"DriverEnvironment":{"description":"The ATW_* and process environment the driver hands child and orchestrator processes.","x-details":"headlessenv.child_env(scratch) returns these keys over the inherited os.environ (atw.environment fills only absent or blank values); the keeper, supervisor and orchestrator dispatch add ATW_STOP_FILE, ATW_EXECUTION_ID and ATW_ORCH_IDLE.","type":"object","x-python":{"typeddict":"DriverEnvironment"},"properties":{"ATW_PROJECT_ROOT":{"type":"string","minLength":1,"description":"Absolute path of the project root.","x-constant":"PROJECT_ROOT_ENV"},"ATW_PRD_EPIC_SYNC":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic sync script.","x-constant":"PRD_EPIC_SYNC_ENV"},"ATW_PRD_EPIC_VERIFY":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic verify script.","x-constant":"PRD_EPIC_VERIFY_ENV"},"ATW_CONTROL_REPO":{"type":"string","minLength":1,"description":"Absolute path of the control repository (SKILLSPOKE_CC, else the driver's repository root). The driver modules live under it at DRIVER_DIR_PARTS.","x-constant":"CONTROL_REPO_ENV"},"ATW_ARCH_PATH":{"type":"string","minLength":1,"description":"The architecture root; set only when the driver knows one. Readers use args.archPath first and fall back to it.","x-constant":"ARCH_PATH_ENV"},"ATW_DESIGN_PACKAGES_DIR":{"type":"string","minLength":1,"description":"The owner's cds design packages directory; optional.","x-constant":"DESIGN_PACKAGES_ENV"},"ATW_PRD_DIR":{"type":"string","minLength":1,"description":"The first PRD root; optional.","x-constant":"PRD_DIR_ENV"},"PATH":{"type":"string","minLength":1,"description":"The controller runtime's bin directory first, de-duplicated.","x-constant":"PATH_ENV"},"TMPDIR":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMPDIR_ENV","x-group":"SCRATCH_ENV_KEYS"},"TMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"TEMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TEMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS":{"type":"string","const":"0","description":"Disables the Claude CLI print-mode background wait.","x-constant":"BACKGROUND_WAIT_KEY","x-const-mapping":"BACKGROUND_WAIT_ENV"},"ATW_STOP_FILE":{"type":"string","minLength":1,"description":"Path of the stop marker file; absent means no stop marker. A consumer touches the file (mode 0o600) to request a drain, or tests whether it exists. It only requests a stop: how a stop is classified belongs to the handback contract.","x-constant":"STOP_FILE_ENV","x-file-mode":"STOP_FILE_MODE"},"ATW_EXECUTION_ID":{"type":"string","minLength":1,"description":"The driver execution id. Required for an orchestrator dispatch; set for a headless workflow session only when its arguments carry an executionId.","x-constant":"EXECUTION_ID_ENV"},"ATW_ORCH_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"3600","description":"Orchestrator idle limit in seconds: a positive finite float. A non-finite or non-positive value is a ValueError.","x-constant":"ORCH_IDLE_ENV","x-default-constant":"ORCH_IDLE_DEFAULT"}},"required":["ATW_PROJECT_ROOT","ATW_PRD_EPIC_SYNC","ATW_PRD_EPIC_VERIFY","ATW_CONTROL_REPO","PATH","TMPDIR","TMP","TEMP","CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"],"additionalProperties":{"type":"string"}},"StopFileMode":{"description":"Permission bits a consumer creates the stop marker file with.","type":"integer","const":384,"x-python":{"constant":"STOP_FILE_MODE","type":"int","render":"0o600"}},"DeniedTool":{"description":"A tool every headless build and deploy Workflow session the driver dispatches is denied. DENIED_TOOLS keeps this order.","type":"string","enum":["WebFetch","WebSearch","Artifact","SendMessage","EndConversation","CronCreate","CronDelete","CronList","mcp__claude_ai_Gmail__send_message","mcp__claude_ai_Gmail__reply","mcp__claude_ai_Gmail__forward","mcp__claude_ai_Gmail__create_draft","mcp__claude_ai_Google_Drive__share_file","mcp__claude_ai_Google_Drive__create_file","mcp__plugin_slack_slack__slack_send_message","mcp__plugin_slack_slack__slack_send_message_draft","mcp__plugin_slack_slack__slack_schedule_message"],"x-python":{"literal":"DeniedTool","tuple":"DENIED_TOOLS"}},"TerminateGrace":{"description":"Seconds a terminated child process is given before it is killed.","type":"number","const":10,"x-python":{"constant":"TERMINATE_GRACE","type":"float"}},"ExhaustedUtilization":{"description":"A usage window whose utilization is at or above this value is exhausted.","type":"number","const":1,"x-python":{"constant":"EXHAUSTED_UTILIZATION","type":"float"}},"RateLimitStatus":{"description":"RateLimitInfo.status; only rejected is acted on.","type":"string","enum":["allowed","allowed_warning","rejected"],"x-python":{"literal":"RateLimitStatus","tuple":"RATE_LIMIT_STATUSES","constants":{"rejected":"REJECTED_STATUS"}}},"UsageWindowName":{"description":"The account-wide usage windows. Any other window name is model-specific.","type":"string","enum":["five_hour","seven_day"],"x-python":{"literal":"UsageWindowName","frozenset":"ACCOUNT_WINDOWS"}},"UsageWindow":{"description":"One usage window of a RateLimitInfo.","type":"object","x-python":{"typeddict":"UsageWindow"},"properties":{"utilization":{"type":"number","description":"Exhausted when at or above EXHAUSTED_UTILIZATION."},"resetsAt":{"type":"number","description":"Reset time in epoch seconds."}},"required":["utilization"]},"RateLimitInfo":{"description":"The rate_limit_info of a rate_limit_event: the info argument of the quota readers.","type":"object","x-python":{"typeddict":"RateLimitInfo"},"properties":{"status":{"$ref":"#/$defs/RateLimitStatus"},"unifiedWindows":{"type":"object","additionalProperties":{"$ref":"#/$defs/UsageWindow"},"description":"Window name -> usage window."},"resetsAt":{"type":"number","description":"Top-level reset time in epoch seconds."},"rateLimitType":{"type":"string","description":"The value with meaning here is MODEL_OVERAGE_TYPE.","x-values":{"MODEL_OVERAGE_TYPE":"seven_day_overage_included"}},"overageDisabledReason":{"type":"string","description":"The value with meaning here is OUT_OF_CREDITS_REASON.","x-values":{"OUT_OF_CREDITS_REASON":"out_of_credits"}}},"required":["status"]},"RateLimitEvent":{"description":"One Claude CLI stream-json rate-limit event.","type":"object","x-python":{"typeddict":"RateLimitEvent"},"properties":{"type":{"type":"string","const":"rate_limit_event","x-value-constant":"RATE_LIMIT_EVENT_TYPE"},"rate_limit_info":{"$ref":"#/$defs/RateLimitInfo","x-key-constant":"RATE_LIMIT_INFO_KEY"}},"required":["type","rate_limit_info"]}}}
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
      agentType: name,
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
    agentType: 'adversarial-critique-adjudicator',
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
