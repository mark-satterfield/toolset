export const meta = {
  name: 'prd-creation',
  description:
    'Leaf mini — turns a raw stakeholder request into a template-conformant PRD paired with its Epic. Intake captures the request, then the persona and OKRs are authored in parallel, then the PRD is drafted (WHAT-not-HOW) and independently checked for alignment with the intake brief, persona, and OKRs. A PRD and its Epic are created at the same time, so the mini emits exactly one Epic per PRD: a container bead spec derived from the PRD itself in the same authoring pass — no acceptance criteria, no repo scope (one Epic may span repos) — which the caller writes with bd. The matrix is the one record of the pair: the result carries the command that records it (atw-matrix sync-epics --bead <id> --prd <path>), which the caller runs once the Epic bead exists and the PRD file is written. Maker, checker, and decider are distinct agents; the maker is re-run with the checker\'s verdict file on reject (bounded 2 passes) and a review-dispute-decider rules on deadlock. Every agent writes its own file in args.workDir to its contract in skills/artifact-handoff/schemas/prd-creation.schema.json (the PRD as Markdown beside its draft record); the checked relay validates each, later agents are handed the earlier files by path, and a rerun with the same workDir reuses every accepted file whose inputs are unchanged. Authors no judgment of its own work.',
  phases: [
    { title: 'Intake', detail: 'ONE session scopes the request and captures the structured intake brief' },
    { title: 'Persona & OKR', detail: 'author the target persona and the OKRs in parallel' },
    { title: 'PRD Draft', detail: 'draft the PRD + independent alignment check (bounded loop)' },
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

// Dispatch failures retain their identities and diagnostics; bounded retry policy is below.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
// Account exhaustion interrupts; transport failures use the caller's bounded retry policy.
function failureCause(err) { return dispatchFailureCause(err) }
function failureCauseFor(label) {
  const entry = dispatchFailures.slice().reverse().find((item) => item.label === label)
  return entry ? entry.cause || 'deterministic' : null
}
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
      dispatchFailures.push({ agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: name + ': returned nothing', schema: settleSchemaName(o), transcript: settleTranscript(null, name) })
      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)
      const entry = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'threw', cause: plan.cause, attempt, message: message.slice(0, 300), note: name + ': ' + message.slice(0, 160), schema: settleSchemaName(o), transcript: settleTranscript(err, name) }
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

// ===== SHARED BLOCK relay — BEGIN (canonical: scripts/shared-blocks/relay.js; filled from skills/artifact-handoff/schemas/{checkpoint,relay-command-result,relay-registered-result,artifact-reference}.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// ── CHECKED RELAY: deterministic work reaches this script unaltered, or not at all ──
//
// A workflow script cannot run a command or read a file. A command reaches the shell only as
// text a runner session types, and its result reaches the script only as that session's copy.
// Neither copy is trusted:
// - every command line carries --argv-sha256, the SHA-256 of the canonical JSON of its argument
//   list; the program refuses (exit 3, nothing run) a command line typed differently;
// - every result is printed as ONE RELAY64v1: line carrying base64 canonical JSON: a flat object of scalars (the view's leaves keyed by
//   path, plus ~exit, ~checksum and the relay file's ~file, ~sha256, ~bytes), where ~checksum
//   is the SHA-256 of the canonical JSON of { exit, view }. The runner returns that line as a
//   verbatim string; the script parses it, recomputes the checksum and accepts only an exact
//   copy, then rebuilds the view. A copy that fails (damaged, missing, or handed back without
//   the hook) is recovered by reading the relay file the command wrote, bound to the command
//   line that wrote it; the original command never repeats.
// depscore.py carries the protocol itself; scripts/portfolio/relayrun.py carries it for any
// other program, and checks or writes a saved JSON file against the hash of the value this
// script holds. relayKit.inline runs a Python payload under a self-checking bootstrap, for the
// one step that runs before the plugin root is known. canonicalJson spells the same bytes as
// scripts/portfolio/relay.py canonical().
const relayKit = (() => {
  const SHORT = { '"': '\\"', '\\': '\\\\', '\n': '\\n', '\r': '\\r', '\t': '\\t', '\b': '\\b', '\f': '\\f' }
  /** The canonical JSON of a value: sorted keys, no whitespace, ASCII only. */
  function canonicalJson(v) {
    if (v === null) return 'null'
    if (v === true) return 'true'
    if (v === false) return 'false'
    if (typeof v === 'number') {
      if (!Number.isFinite(v)) throw new Error(`${v} has no JSON spelling`)
      return String(v)
    }
    if (typeof v === 'string') {
      let out = '"'
      for (let i = 0; i < v.length; i++) {
        const unit = v.charCodeAt(i)
        const esc = unit < 0x80 ? SHORT[v[i]] : undefined
        if (esc) out += esc
        else if (unit >= 0x20 && unit <= 0x7e) out += v[i]
        else out += `\\u${unit.toString(16).padStart(4, '0')}`
      }
      return `${out}"`
    }
    if (Array.isArray(v)) return `[${v.map(canonicalJson).join(',')}]`
    if (typeof v === 'object') return `{${Object.keys(v).filter((k) => v[k] !== undefined).sort().map((k) => `${canonicalJson(k)}:${canonicalJson(v[k])}`).join(',')}}`
    throw new Error(`a ${typeof v} has no JSON spelling`)
  }
  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ]
  /** The SHA-256, in lower-case hex, of an ASCII text (canonicalJson's output is ASCII only). */
  function sha256Ascii(text) {
    const bytes = []
    for (let i = 0; i < text.length; i++) {
      const c = text.charCodeAt(i)
      if (c > 0x7f) throw new Error('sha256Ascii: the text is not ASCII')
      bytes.push(c)
    }
    const bits = bytes.length * 8
    bytes.push(0x80)
    while (bytes.length % 64 !== 56) bytes.push(0)
    for (const w of [Math.floor(bits / 0x100000000), bits >>> 0]) bytes.push((w >>> 24) & 255, (w >>> 16) & 255, (w >>> 8) & 255, w & 255)
    const H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
    const W = new Array(64)
    const rotr = (x, n) => (x >>> n) | (x << (32 - n))
    for (let off = 0; off < bytes.length; off += 64) {
      for (let t = 0; t < 16; t++) W[t] = ((bytes[off + 4 * t] << 24) | (bytes[off + 4 * t + 1] << 16) | (bytes[off + 4 * t + 2] << 8) | bytes[off + 4 * t + 3]) >>> 0
      for (let t = 16; t < 64; t++) {
        const s0 = rotr(W[t - 15], 7) ^ rotr(W[t - 15], 18) ^ (W[t - 15] >>> 3)
        const s1 = rotr(W[t - 2], 17) ^ rotr(W[t - 2], 19) ^ (W[t - 2] >>> 10)
        W[t] = (W[t - 16] + s0 + W[t - 7] + s1) >>> 0
      }
      let [a, b, c, d, e, f, g, h] = H
      for (let t = 0; t < 64; t++) {
        const t1 = (h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[t] + W[t]) >>> 0
        const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0
        h = g
        g = f
        f = e
        e = (d + t1) >>> 0
        d = c
        c = b
        b = a
        a = (t1 + t2) >>> 0
      }
      ;[a, b, c, d, e, f, g, h].forEach((x, i) => { H[i] = (H[i] + x) >>> 0 })
    }
    return H.map((x) => x.toString(16).padStart(8, '0')).join('')
  }
  /** The SHA-256 of a value's canonical JSON. */
  const sha256Json = (v) => sha256Ascii(canonicalJson(v))
  /** One shell word, single-quoted. */
  const quote = (v) => `'${String(v).replace(/'/g, "'\\''")}'`
  /**
   * The argument list a POSIX shell makes of a command line built from bare words and single
   * quoting. A line using any other shell feature (double quotes, $, backticks, ;, |, &, <, >, a
   * glob) is refused: its argument list is not knowable here, so it cannot be checked.
   */
  function shellWords(line) {
    const words = []
    let word = null
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      if (ch === "'") {
        const close = line.indexOf("'", i + 1)
        if (close < 0) throw new Error('shellWords: unterminated quote')
        word = (word || '') + line.slice(i + 1, close)
        i = close
      } else if (ch === '\\') {
        if (i + 1 >= line.length) throw new Error('shellWords: trailing backslash')
        word = (word || '') + line[i + 1]
        i += 1
      } else if (/\s/.test(ch)) {
        if (word !== null) words.push(word)
        word = null
      } else if (/["$`;|&<>*?[\]{}()~#!]/.test(ch)) {
        throw new Error(`shellWords: ${JSON.stringify(ch)} is a shell feature the checksum cannot cover; quote it`)
      } else {
        word = (word || '') + ch
      }
    }
    if (word !== null) words.push(word)
    return words
  }
  // The runner's results and the producer's artifact reference, inlined by scripts/shared-blocks.mjs
  // from their contract files in skills/artifact-handoff/schemas/ (relay-command-result,
  // relay-registered-result, artifact-reference). Never restate any part of them here.
  const SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","description":"What the workflow-command-runner returns for an assignment that names its command itself (no WORKFORCE_RELAY_BINDING_V1 line): the command's exit status and its stdout, verbatim. Nothing in it is rebuilt: the workflow script (the relay shared block, scripts/shared-blocks/relay.js) checks the copy against the checksum it carries and, when the copy fails, reads the relay file the command saved instead.","type":"object","additionalProperties":false,"required":["exitCode","stdout"],"properties":{"exitCode":{"description":"The exit status of the one command the assignment named.","type":"integer"},"stdout":{"description":"The complete RELAY64v1: line the command printed, copied verbatim: every character as printed, in order, including the prefix and any trailing = characters, with nothing added, removed, reordered or re-typed. Treat its base64 payload as opaque text; never decode or reconstruct it. When the command printed more than one line, all of stdout verbatim.","type":"string"}}}
  const REGISTERED_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","description":"What the workflow-command-runner returns for a registered assignment (one carrying the WORKFORCE_RELAY_BINDING_V1 and WORKFORCE_RELAY_REQUEST_V1 lines). The runner returns the small object the registered helper printed; the plugin's PreToolUse hook supplies the exact saved output. When the runner's Bash call fails, it returns the unknown result: state unknown, exitCode 0, stdout empty, receipt null, bridge false, error empty, so the hook reports the real saved state. The workflow script (the relay shared block, scripts/shared-blocks/relay.js) accepts a completed result only when its receipt matches the request, the command checksum, the exit status, the byte count and the SHA-256 of stdout.","type":"object","additionalProperties":false,"required":["state","exitCode","stdout","receipt","bridge","error"],"properties":{"state":{"description":"completed: the command ran and its saved output is handed back. not-started: the request provably never ran; the workflow, not the runner, decides whether it is attempted again. unknown: the runner could not tell (its Bash call failed); every other field then holds its empty value (exitCode 0, stdout empty, receipt null, bridge false, error empty).","type":"string","enum":["completed","not-started","unknown"]},"exitCode":{"description":"The exit status of the registered command.","type":"integer"},"stdout":{"description":"The command's saved stdout, verbatim. Never interpret, reconstruct or copy the payload by hand.","type":"string"},"receipt":{"description":"The integrity receipt of the saved output, or null when there is none.","anyOf":[{"description":"Binds a saved output to the request that produced it.","type":"object","additionalProperties":false,"required":["request","commandSha256","sha256","bytes","exitCode"],"properties":{"request":{"description":"The request id the workflow script computed for this command.","type":"string"},"commandSha256":{"description":"The SHA-256 of the canonical JSON of the command's argument list.","type":"string"},"sha256":{"description":"The SHA-256 of stdout.","type":"string"},"bytes":{"description":"The length of stdout.","type":"integer"},"exitCode":{"description":"The exit status the saved output records.","type":"integer"}}},{"type":"null"}]},"bridge":{"description":"true only on the result the hook itself supplies; the runner's own result always carries false, and the workflow reads any other value as the runner's copy.","type":"boolean"},"error":{"description":"Why the outcome is not completed, or empty.","type":"string"}}}
  const ARTIFACT_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","description":"What a producer session returns after it authored a JSON artifact under the artifact checkpoint contract (checkpoint.schema.json): only the path of the candidate it wrote, never a copy of its content. The workflow script then validates the candidate against its contract file and publishes it (scripts/portfolio/jsonartifact.py).","type":"object","additionalProperties":false,"required":["artifactPath"],"properties":{"artifactPath":{"description":"The candidate path the brief named, as the submit command printed it.","type":"string"}}}
  const HEX = /^[0-9a-f]{64}$/
  /** The relay's own keys in a printed envelope; every other key is a leaf of the flat view. */
  const RELAY_KEYS = ['~file', '~sha256', '~bytes', '~exit', '~checksum']
  /**
   * Rebuilds a view from its flat form (scripts/portfolio/relay.py flatten): leaves keyed by
   * `/`-joined paths (`~0` is `~`, `~1` is `/`), containers and nulls marked by `/~{}`, `/~#`,
   * `/~null`; a list of plain strings is one comma-joined value marked `/~,`.
   */
  function unflatten(flat) {
    const root = {}
    const at = new Map([['', root]])
    const unesc = (seg) => seg.replace(/~1/g, '/').replace(/~0/g, '~')
    const MARK = { '~{}': 1, '~#': 1, '~null': 1, '~,': 1 }
    const entries = Object.keys(flat).map((k) => {
      const segs = k.split('/')
      const mark = MARK[segs[segs.length - 1]] ? segs[segs.length - 1] : null
      return { k, segs: mark ? segs.slice(0, -1) : segs, mark, v: flat[k] }
    })
    entries.sort((x, y) => (x.mark ? x.segs.length - 0.5 : x.segs.length) - (y.mark ? y.segs.length - 0.5 : y.segs.length))
    for (const e of entries) {
      const parentKey = e.segs.slice(0, -1).join('/')
      const parent = at.get(parentKey)
      if (!parent) throw new Error(`unflatten: ${e.k} has no container`)
      const last = e.segs[e.segs.length - 1]
      const slot = Array.isArray(parent) ? Number(last) : unesc(last)
      const value = e.mark === '~{}' ? {} : e.mark === '~#' ? new Array(Number(e.v) || 0) : e.mark === '~null' ? null : e.mark === '~,' ? String(e.v).split(',') : e.v
      parent[slot] = value
      if (e.mark === '~{}' || e.mark === '~#') at.set(e.segs.join('/'), value)
    }
    return root
  }
  function decodeTransport(text) {
    const prefix = 'RELAY64v1:'
    if (!text.startsWith(prefix)) return text
    const encoded = text.slice(prefix.length)
    if (!encoded || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) throw new Error('invalid relay base64 alphabet or padding')
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    let decoded = ''
    for (let i = 0; i < encoded.length; i += 4) {
      const a = alphabet.indexOf(encoded[i])
      const b = alphabet.indexOf(encoded[i + 1])
      const c = encoded[i + 2] === '=' ? 0 : alphabet.indexOf(encoded[i + 2])
      const d = encoded[i + 3] === '=' ? 0 : alphabet.indexOf(encoded[i + 3])
      if ((encoded[i + 2] === '=' && (b & 15)) || (encoded[i + 3] === '=' && encoded[i + 2] !== '=' && (c & 3))) throw new Error('noncanonical relay base64 padding bits')
      const bytes = [(a << 2) | (b >> 4)]
      if (encoded[i + 2] !== '=') bytes.push(((b & 15) << 4) | (c >> 2))
      if (encoded[i + 3] !== '=') bytes.push(((c & 3) << 6) | d)
      for (const byte of bytes) {
        if (byte > 0x7f) throw new Error('relay payload must be canonical ASCII JSON, a strict UTF-8 subset')
        decoded += String.fromCharCode(byte)
      }
    }
    return decoded
  }
  /** Parses a runner's stdout copy and checks it is exactly the envelope the program printed; returns { env, flat } or { why }. */
  function parse(stdout, file) {
    let env
    try {
      const text = String(stdout || '').trim()
      const open = '<exact_text>'
      const close = '</exact_text>'
      const payload = text.startsWith(open) && text.endsWith(close) ? text.slice(open.length, -close.length) : text
      env = JSON.parse(decodeTransport(payload))
    } catch (err) {
      env = null
    }
    if (!env || typeof env !== 'object' || Array.isArray(env)) {
      const text = String(stdout || '')
      const exception = exceptionOf(text)
      return { why: exception ? `the program failed: ${exception}` : `stdout is not one valid relay envelope line: ${JSON.stringify(text.slice(0, 300))}` }
    }
    if (!HEX.test(String(env['~checksum'])) || !Number.isInteger(env['~exit'])) return { why: 'the copy has no relay checksum or exit status' }
    const named = env['~file'] === undefined ? null : env['~file']
    if (named !== file && !(named === null && env['~exit'] === 3)) return { why: `the copy names relay file ${JSON.stringify(named)}, not ${JSON.stringify(file)}` }
    const flat = {}
    for (const k of Object.keys(env)) if (!RELAY_KEYS.includes(k)) flat[k] = env[k]
    let got = ''
    try {
      got = sha256Json({ exit: env['~exit'], view: flat })
    } catch (err) {
      return { why: `the copy cannot be hashed: ${String((err && err.message) || err)}` }
    }
    if (got !== env['~checksum']) return { env, why: `the copy hashes to ${got}, not to the ${env['~checksum']} the program printed` }
    return { env, flat }
  }
  const prompt = (command) => `Run exactly this one shell command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000, and change nothing else. Type the command exactly as written below, character for character: the program checks it against the checksum it carries and refuses any difference.

${command}

It prints exactly one line beginning RELAY64v1: followed by base64 text. Return its exit status and that line as your output schema describes (contract: skills/artifact-handoff/schemas/relay-command-result.schema.json). Do not retry, do not repair, do not run any other command.`
  let captureOrdinal = 0
  async function registeredCommand(dispatch, { label, phase, command }, ordinal) {
    const argv = shellWords(command)
    const commandSha256 = sha256Json(argv)
    const executionId = fableInput.relayExecutionId
    const request = sha256Json({ execution: executionId, invocation: fablePath, ordinal, commandSha256 })
    const document = canonicalJson({ version: 1, executionId, invocation: fablePath, ordinal, request, commandSha256, argv })
    if (document.length > 2097152) return { captureError: 'registered command exceeds the 2 MiB request bound' }
    let operation = 'registered'
    const recovered = new Set()
    for (let attempt = 0; attempt < 3; attempt++) {
      const callLabel = attempt ? `${label}:machine-recovery${attempt}` : label
      const before = new Set(typeof dispatchFailures === 'undefined' ? [] : dispatchFailures)
      const binding = canonicalJson({ executionId, request, directory: fableInput.relayRequestDir, operation })
      const out = await dispatch(`WORKFORCE_RELAY_BINDING_V1 ${binding}\nWORKFORCE_RELAY_REQUEST_V1 ${document}`, { label: callLabel, phase, agentType: 'workflow-command-runner', model: 'sonnet', effort: 'low', schema: REGISTERED_SCHEMA, outputMode: 'machine' })
      if (typeof dispatchFailures !== 'undefined') for (const entry of dispatchFailures) if (!before.has(entry) && entry.label === callLabel && entry.phase === phase) recovered.add(entry)
      if (!out) {
        if (typeof dispatchInterruption !== 'undefined' && dispatchInterruption) return null
        operation = 'registered-result'
        continue
      }
      const settle = (result) => {
        if (typeof dispatchFailures !== 'undefined') for (const entry of recovered) { const at = dispatchFailures.indexOf(entry); if (at >= 0) dispatchFailures.splice(at, 1) }
        return result
      }
      if (out.state === 'not-started') { operation = 'registered'; continue }
      // Without the hand-off hook the result is the runner's own copy: exec checks it, and reads the relay file when it fails.
      if (out.bridge !== true) return settle({ exitCode: out.exitCode, stdout: String(out.stdout || '') })
      if (out.state !== 'completed') return settle({ captureError: out.error || 'registered command outcome unknown' })
      const receipt = out.receipt
      let exact = false
      try { exact = receipt && receipt.request === request && receipt.commandSha256 === commandSha256 && receipt.exitCode === out.exitCode && Number.isInteger(out.exitCode) && Number.isSafeInteger(receipt.bytes) && receipt.bytes >= 0 && receipt.bytes <= 1048576 && typeof out.stdout === 'string' && out.stdout.length === receipt.bytes && HEX.test(String(receipt.sha256)) && sha256Ascii(out.stdout) === receipt.sha256 } catch (_) { exact = false }
      if (!exact) return settle({ captureError: 'machine handoff failed request/command/exit/byte verification' })
      return settle({ exitCode: out.exitCode, stdout: out.stdout, receipt, machine: true })
    }
    return { captureError: 'registered command could not hand back its result after three bounded machine attempts' }
  }
  /** The `--argv-sha256` value a checked command line carries, or ''. */
  function argvShaOf(command) {
    try {
      const words = shellWords(command)
      const at = words.indexOf('--argv-sha256')
      return at >= 0 && HEX.test(String(words[at + 1])) ? words[at + 1] : ''
    } catch (_) {
      return ''
    }
  }
  /**
   * Runs a command once. When its result does not come back as an exact copy (a damaged copy, a
   * hand-back without the hook, an unknown outcome), the relay file the command wrote is read
   * instead, bound to the command line that wrote it; the command itself never runs twice. A
   * command line the runner typed differently ran nothing and is sent once more.
   */
  async function exec(dispatch, { label, phase, command, file = null, readRunner = null }, typedAgain = false) {
    const ordinal = captureOrdinal++
    const runner = { agentType: 'workflow-command-runner', model: 'sonnet', effort: 'low' }
    const registered = fableInput.relayExecutionId && fableInput.relayRequestDir && fableInput.relayCaptureScript
    const out = registered
      ? await registeredCommand(dispatch, { label, phase, command }, ordinal)
      : await dispatch(prompt(command), { label, phase, ...runner, schema: SCHEMA })
    if (!out) return { ok: false, noResult: true, error: `the ${label} runner returned no result` }
    let got = out.captureError ? { why: out.captureError } : parse(out.stdout, file)
    if (got.why) {
      if (!file || !readRunner) {
        const error = `RELAY_COPY_RECOVERY_EXHAUSTED ${JSON.stringify({ label, relayFile: file, attempts: 1, reason: `${got.why}; the command saves no relay file to read` })}`
        log(error)
        return { ok: false, paused: true, recoveryKind: 'relay-copy-recovery', error }
      }
      const sha = got.env && HEX.test(String(got.env['~sha256'])) ? got.env['~sha256'] : ''
      const argvSha = argvShaOf(command)
      let reason = got.why
      for (let attempt = 1; attempt <= 3; attempt++) {
        log(`RELAY_COPY_RECOVERY_ATTEMPT ${JSON.stringify({ label, relayFile: file, attempt, reason })}`)
        const readCommand = pythonLine(readRunner, ['read', '--relay', file, ...(attempt === 1 && sha ? ['--sha256', sha] : []), ...(argvSha ? ['--for-argv', argvSha] : [])])
        const copied = registered
          ? await registeredCommand(dispatch, { label: `${label}:read${attempt}`, phase, command: readCommand }, captureOrdinal++)
          : await dispatch(`The command below only reads the result an earlier command already saved; it runs nothing else.\n\n${prompt(readCommand)}`, { label: `${label}:read${attempt}`, phase, ...runner, schema: SCHEMA })
        if (!copied) return { ok: false, noResult: true, error: `${label}: the relay file reader returned no result` }
        const read = copied.captureError ? { why: copied.captureError } : parse(copied.stdout, file)
        if (!read.why && read.env['~exit'] === 4) return { ok: false, error: `${label}: the command saved no result in ${file}` }
        if (!read.why) { got = read; break }
        reason = read.why
      }
      if (got.why) {
        const error = `RELAY_COPY_RECOVERY_EXHAUSTED ${JSON.stringify({ label, relayFile: file, attempts: 3, reason })}`
        log(error)
        return { ok: false, paused: true, recoveryKind: 'relay-copy-recovery', error }
      }
      log(`RELAY_COPY_RECOVERED ${JSON.stringify({ label, relayFile: file })}`)
    }
    const exit = got.env['~exit']
    let view
    try {
      view = unflatten(got.flat)
    } catch (err) {
      return { ok: false, error: `${label}: the printed view could not be rebuilt: ${String((err && err.message) || err)}` }
    }
    if (exit === 3) {
      if (!typedAgain) {
        log(`${label}: the runner typed the command line differently and nothing ran; sending it once more`)
        return exec(dispatch, { label, phase, command, file, readRunner }, true)
      }
      return { ok: false, error: `${label}: ${String(view.error || 'the runner typed the command line differently from the one built')}; nothing ran` }
    }
    return { ok: true, exit, view }
  }
  /** The exception line a Python traceback in `text` ends with, or ''. */
  function exceptionOf(text) {
    const s = String(text || '')
    if (!/Traceback \(most recent call last\)/.test(s)) return ''
    const lines = s.split('\n').map((l) => l.trim()).filter(Boolean)
    return [...lines].reverse().find((l) => /^[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt)(:|$)/.test(l)) || lines[lines.length - 1] || ''
  }
  /** The checked command line running python3 `script` with the argument list `rest`. */
  const pythonLine = (script, rest) => ['python3', script, '--argv-sha256', sha256Json(rest), ...rest].map(quote).join(' ')
  /**
   * Runs one depscore.py command. `tail` is its arguments as shell text (single-quoted words only),
   * `repo` the beads repository (-C), `file` the relay file its full result is saved in. Returns
   * what it printed, checked, with relayFile; or { error, cause, exception?, output? }: cause is
   * 'relay' when the result did not come back through the relay, else the `cause` depscore.py
   * printed ('contention' when bd reported another writer's lock, 'bd-timeout' when it reported
   * the beads server failed), else 'other'.
   */
  async function depscore(dispatch, { label, phase, script, repo, tail, file }) {
    let rest
    try {
      rest = [...(repo ? ['-C', repo] : []), '--relay', file, ...shellWords(tail)]
    } catch (err) {
      return { error: `${label}: ${String((err && err.message) || err)}`, cause: 'other' }
    }
    const r = await exec(dispatch, { label, phase, command: pythonLine(script, rest), file, readRunner: script.replace(/[^/]+$/, 'relayrun.py') })
    if (!r.ok) return { error: r.error, noResult: !!r.noResult, cause: 'relay' }
    if (r.exit !== 0 || r.view.error) {
      const raw = String(r.view.error || `depscore.py exited ${r.exit}`)
      const exception = exceptionOf(raw)
      const cause = ['bd-timeout', 'contention'].includes(r.view.cause) ? r.view.cause : 'other'
      return { error: exception ? `${exception} (depscore.py exited ${r.exit}; full output: ${raw})` : raw, cause, exception, output: r.view, relayFile: file }
    }
    return { ...r.view, relayFile: file }
  }
  /**
   * Runs `argv` (a program and its arguments, no shell) through relayrun.py at `runner`, in `cwd`.
   * Returns { ok: true, exitCode, json, stdoutBytes, stderrBytes, stdoutTail?, stderrTail?, relayFile }
   * — json is stdout parsed when it is one JSON object (reduced to `keys` when given), else null —
   * or { ok: false, error, cause }: cause 'relay' when the result did not come back through the relay.
   */
  async function run(dispatch, { label, phase, runner, argv, cwd = null, file, keys = [], tail = 0, timeout = null }) {
    const rest = ['run', '--relay', file, ...(cwd ? ['--cwd', cwd] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(tail ? ['--tail', String(tail)] : []), ...(timeout ? ['--timeout', String(timeout)] : []), '--', ...argv.map(String)]
    const r = await exec(dispatch, { label, phase, command: pythonLine(runner, rest), file, readRunner: runner })
    if (!r.ok) return { ok: false, error: r.error, noResult: !!r.noResult, cause: 'relay' }
    if (r.exit !== 0) return { ok: false, error: String(r.view.error || `relayrun.py exited ${r.exit}`), cause: 'other' }
    return { ok: true, ...r.view, relayFile: file }
  }
  /** Whether the JSON file `file` holds exactly `value`. Returns { ok: true, exists, parsed, match } or { ok: false, error }. */
  async function checkFile(dispatch, { label, phase, runner, file, value }) {
    const r = await exec(dispatch, { label, phase, command: pythonLine(runner, ['check-file', '--file', file, '--sha256', sha256Json(value)]) })
    if (!r.ok) return { ok: false, error: r.error, noResult: !!r.noResult }
    return { ok: true, exists: r.view.exists === true, parsed: r.view.parsed === true, match: r.view.match === true }
  }
  /**
   * Makes the JSON file `file` hold exactly `value`, the schema-validated result a session
   * returned: checks the file, and when it differs (or is missing) writes `value` through
   * relayrun.py write-file, which refuses a copy that does not hash as built, then checks again.
   * Returns { ok, rewritten, error? }.
   */
  async function ensureJson(dispatch, { label, phase, runner, file, value }) {
    const first = await checkFile(dispatch, { label: `${label}:check`, phase, runner, file, value })
    if (!first.ok) return { ok: false, rewritten: false, error: first.error }
    if (first.match) return { ok: true, rewritten: false }
    log(`${label}: ${file} ${first.exists ? 'differs from the result the session returned' : 'was not saved'}; writing the returned result`)
    const w = await exec(dispatch, { label: `${label}:write`, phase, command: pythonLine(runner, ['write-file', '--file', file, '--sha256', sha256Json(value), '--json', canonicalJson(value)]) })
    if (!w.ok || w.exit !== 0 || w.view.written !== true) return { ok: false, rewritten: false, error: (w.ok ? String(w.view.error || 'not written') : w.error) }
    const again = await checkFile(dispatch, { label: `${label}:recheck`, phase, runner, file, value })
    return again.ok && again.match ? { ok: true, rewritten: true } : { ok: false, rewritten: true, error: again.error || `${file} still differs after it was written` }
  }
  const BOOT = [
    'import base64, hashlib, json, sys',
    'a = sys.orig_argv',
    'i = a.index("-c")',
    'boot, want, code, args = a[i + 1], a[i + 2], a[i + 3], a[i + 4:]',
    'c = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True)',
    'h = lambda v: hashlib.sha256(c(v).encode("ascii")).hexdigest()',
    'def flat(v, p="", o=None):',
    '    o = {} if o is None else o',
    '    j = (lambda s: p + "/" + s) if p else (lambda s: s)',
    '    if isinstance(v, dict):',
    '        if p:',
    '            o[j("~{}")] = len(v)',
    '        for k, x in v.items():',
    '            flat(x, j(str(k).replace("~", "~0").replace("/", "~1")), o)',
    '    elif isinstance(v, list):',
    '        o[j("~#")] = len(v)',
    '        for n, x in enumerate(v):',
    '            flat(x, j(str(n)), o)',
    '    elif v is None:',
    '        o[j("~null")] = 1',
    '    else:',
    '        o[p] = v',
    '    return o',
    'def emit(view, ex=0):',
    '    f = flat(view)',
    '    print("RELAY64v1:" + base64.b64encode(c(dict(f, **{"~exit": ex, "~checksum": h({"exit": ex, "view": f})})).encode("ascii")).decode("ascii"))',
    '    sys.exit(ex)',
    'if h([boot, code] + args) != want:',
    '    emit({"argvMismatch": True, "error": "the command line differs from the one the workflow script built"}, 3)',
    'exec(code, {"ARGS": args, "emit": emit, "__name__": "__relay__"})',
  ].join('\n')
  /**
   * Runs the Python `code` (which reads its arguments from ARGS and calls emit(obj) once with a
   * JSON object holding no floats) under a bootstrap that checks the command line, payload included,
   * and seals what it emits. Returns
   * { ok: true, view } or { ok: false, error }.
   */
  async function inline(dispatch, { label, phase, code, args = [] }) {
    const words = args.map(String)
    const command = ['python3', '-c', BOOT, sha256Json([BOOT, code, ...words]), code, ...words].map(quote).join(' ')
    const r = await exec(dispatch, { label, phase, command })
    if (!r.ok) return { ok: false, error: r.error, noResult: !!r.noResult }
    if (r.exit !== 0) return { ok: false, error: String(r.view.error || `exited ${r.exit}`) }
    return { ok: true, view: r.view }
  }
  // The artifact checkpoint contract, inlined by scripts/shared-blocks.mjs from its one place,
  // skills/artifact-handoff/schemas/checkpoint.schema.json. Never restate any part of it here.
  const CHECKPOINT_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","title":"Artifact checkpoint","description":"The sidecar <candidate><x-sidecarSuffix> that artifactcontract.py checkpoint|complete|submit writes and artifactcontract.py status and jsonartifact.py read. It is built from the agent-authored progress file <candidate><x-progressSuffix> ($defs/Progress) plus the binding keys. The Python types are generated from this file by scripts/generate_checkpoint_contract.py.","x-sidecarSuffix":".checkpoint","x-progressSuffix":".progress.json","x-bindingKeys":["artifactPath","schemaSha256","revision"],"x-authoredStatuses":["in-progress","blocked"],"x-operations":["validate","checkpoint","complete","submit","status"],"type":"object","additionalProperties":false,"required":["status","artifactPath","schemaSha256","revision","task","completed","remaining","artifacts"],"properties":{"status":{"enum":["in-progress","blocked","complete"]},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"schemaSha256":{"$ref":"#/$defs/Sha256"},"candidateSha256":{"$ref":"#/$defs/Sha256"},"revision":{"$ref":"#/$defs/Revision"},"task":{"$ref":"#/$defs/Progress/properties/task"},"completed":{"$ref":"#/$defs/Progress/properties/completed"},"remaining":{"$ref":"#/$defs/Progress/properties/remaining"},"artifacts":{"$ref":"#/$defs/Progress/properties/artifacts"},"reason":{"$ref":"#/$defs/Progress/properties/reason"}},"allOf":[{"if":{"properties":{"status":{"const":"complete"}}},"then":{"required":["candidateSha256"],"properties":{"remaining":{"maxItems":0}}}},{"if":{"properties":{"status":{"const":"blocked"}}},"then":{"required":["reason"],"properties":{"remaining":{"minItems":1}}}}],"$defs":{"ArtifactPath":{"description":"The absolute candidate path; a binding key.","type":"string","minLength":1},"Revision":{"description":"The input revision; a binding key.","type":"string","minLength":1},"Sha256":{"description":"Lowercase hex SHA-256 of a canonical JSON value.","type":"string","pattern":"^[a-f0-9]{64}$"},"Progress":{"description":"The agent-authored progress file <candidate><x-progressSuffix>; its keys are copied into the checkpoint.","type":"object","additionalProperties":false,"required":["task","completed","remaining","artifacts"],"properties":{"task":{"type":"string","minLength":1},"completed":{"type":"array","items":{"type":"string","minLength":1}},"remaining":{"type":"array","items":{"type":"string","minLength":1}},"artifacts":{"type":"array","items":{"type":"string","minLength":1}},"reason":{"type":"string","minLength":1}}},"StatusReport":{"description":"What the status operation reports for a candidate.","type":"object","additionalProperties":false,"required":["status"],"properties":{"status":{"enum":["incomplete","in-progress","blocked","complete-unaccepted"]},"reason":{"type":"string"},"remaining":{"$ref":"#/$defs/Progress/properties/remaining"},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"schemaSha256":{"$ref":"#/$defs/Sha256"},"revision":{"$ref":"#/$defs/Revision"},"candidateSha256":{"$ref":"#/$defs/Sha256"}}},"CommandResult":{"description":"What the validate, checkpoint, complete and submit operations print; status is absent only for submit.","type":"object","additionalProperties":false,"required":[],"properties":{"status":{"enum":["schema-valid","complete-unaccepted","in-progress","blocked","invalid"]},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"error":{"type":"string","minLength":1}}}}}
  /**
   * The absolute path of a contract file. `contract` is the file's path relative to the plugin
   * root, optionally followed by #<JSON pointer> naming the schema inside it (for example
   * 'skills/artifact-handoff/schemas/x.schema.json#/$defs/Proposal'); `script` is the absolute path
   * of any script in the plugin's scripts/portfolio/ folder, from which the plugin root is known.
   */
  function contractPath(script, contract) {
    const at = /^(.*\/)scripts\/portfolio\/[^/]+$/.exec(String(script || ''))
    if (!at) throw new Error(`contractPath: ${JSON.stringify(script)} is not a script in the plugin's scripts/portfolio/ folder`)
    if (typeof contract !== 'string' || !/^[A-Za-z0-9_-][A-Za-z0-9._/-]*\.json(#\/[^\s']*)?$/.test(contract) || contract.split('#')[0].split('/').includes('..')) {
      throw new Error(`contractPath: ${JSON.stringify(contract)} is not a contract file path relative to the plugin root`)
    }
    return `${at[1]}${contract}`
  }
  /**
   * The helper's schema option for `contract`: a contract file path (see contractPath) becomes
   * `--schema <absolute path>`; a schema object, the form older callers pass, becomes
   * `--schema-json <canonical JSON>`.
   */
  function schemaOption(script, contract) {
    if (contract && typeof contract === 'object' && !Array.isArray(contract)) return ['--schema-json', canonicalJson(contract)]
    return ['--schema', contractPath(script, contract)]
  }
  /**
   * The brief text that binds a producer session to its candidate: the candidate, the progress
   * file, the input revision, the contract file the candidate must satisfy (named, never pasted)
   * and the artifactcontract.py command of each checkpoint operation.
   */
  function artifactBrief(candidate, contract, revision = '', helper) {
    if (typeof helper !== 'string' || !helper) throw new Error('artifactBrief requires the artifactcontract.py helper path')
    const suffix = CHECKPOINT_SCHEMA['x-progressSuffix']
    const operations = CHECKPOINT_SCHEMA['x-operations']
    if (typeof suffix !== 'string' || !suffix || !Array.isArray(operations) || !operations.length) throw new Error('artifactBrief: the checkpoint contract was not inlined from checkpoint.schema.json')
    const schema = schemaOption(helper, contract)
    const progress = `${candidate}${suffix}`
    const binding = ['--candidate', candidate, ...schema, '--revision', revision, '--progress-file', progress]
    const command = operation => ['python3', helper, operation, ...binding].map(quote).join(' ')
    return `\n\nARTIFACT CONTRACT DATA:
Candidate: ${candidate}
${schema[0] === '--schema' ? `Contract: ${schema[1]}\n` : ''}Progress: ${progress}
Input revision: ${revision}
${operations.map(operation => `Command ${operation}: ${command(operation)}`).join('\n')}`
  }
  async function acceptArtifact(dispatch, { label, phase, runner, candidate, file, contract = null, schema: schemaObject = null, relayFile, returned = null, revision = '', keys = [], counts = [], projection = '', probe = false, recordArgv = [], researchAgent = '', researchRepo = '' }) {
    let schema
    try {
      schema = schemaOption(runner, contract || schemaObject)
    } catch (err) {
      return { ok: false, error: String((err && err.message) || err) }
    }
    const args = ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), '--candidate', candidate, '--final', file, ...schema, ...(revision ? ['--revision', revision] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(counts.length ? ['--counts', counts.join(',')] : []), ...(projection ? ['--projection', projection] : []), ...(probe ? ['--probe'] : []), ...(probe && researchAgent && researchRepo ? ['--research-agent', researchAgent, '--research-repo', researchRepo] : []), ...(!returned ? ['--recover'] : [])]
    if (!Array.isArray(recordArgv) || recordArgv.some(word => typeof word !== 'string' || !word)) return { ok: false, error: 'invalid artifact recorder argv' }
    const argv = recordArgv.length ? ['python3', runner.replace(/[^/]+$/, 'artifactpublish.py'), '--record-argv-json', canonicalJson(recordArgv), '--', ...args.slice(2)] : args
    const result = await run(dispatch, { label, phase, runner, argv, file: relayFile })
    if (!result.ok) return result
    if (result.exitCode !== 0) return { ok: false, error: `artifact validation failed: ${JSON.stringify(result.json)}`, relayFile }
    const receipt = result.json
    if (probe && receipt && receipt.blocked === true) {
      const detail = { candidate, revision, reason: String(receipt.reason || 'producer blocked'), remaining: receipt.remaining || [] }
      return { ok: false, blocked: true, resumable: true, error: `ARTIFACT_BLOCKED ${JSON.stringify(detail)}`, ...detail }
    }
    if (probe && receipt && receipt.pending === true) return { ok: true, pending: true, ...(receipt.research ? { research: receipt.research } : {}) }
    if (!receipt || typeof receipt !== 'object') return { ok: false, error: 'artifact validation printed no receipt', relayFile }
    if (recordArgv.length && receipt.recorded !== true) log(`${label}: provenance of ${file} was not recorded (${receipt.recordError || 'no reason given'}); the accepted result is used`)
    return { ok: true, receipt, facts: receipt.facts || {}, counts: receipt.counts || {} }
  }
  async function authorArtifact(dispatch, options, produce, interrupted = () => false) {
    const paused = () => ({ ok: false, noResult: true, error: 'artifact dispatch interrupted; saved work retained' })
    if (interrupted()) return paused()
    const prior = await acceptArtifact(dispatch, { ...options, label: `${options.label}:probe`, relayFile: `${options.relayFile}.probe`, returned: null, probe: true })
    if (interrupted()) return paused()
    if (!prior.ok || !prior.pending) return prior
    const returned = await produce()
    if (interrupted()) return paused()
    return acceptArtifact(dispatch, { ...options, returned, probe: false })
  }
  async function artifactRevision(dispatch, { label, phase, runner, files = [], relayFile, context = {} }) {
    if (!Array.isArray(files)) return { ok: false, error: 'artifact revision requires explicit source paths' }
    let receipts = []
    if (files.length) {
      const result = await run(dispatch, { label, phase, runner, argv: ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), ...files.flatMap(file => ['--source', file])], file: relayFile })
      if (!result.ok && (result.noResult || result.paused)) return result
      if (result.ok && result.exitCode === 0 && result.json && Array.isArray(result.json.receipts)) {
        receipts = result.json.receipts
        if (Array.isArray(result.json.skipped) && result.json.skipped.length) log(`${label}: ${result.json.skipped.length} symlink(s) or special file(s) left out of the source fingerprint (listed in ${relayFile})`)
      } else {
        // The fingerprint only decides whether saved work is reused: without it, the paths alone bind the revision.
        log(`${label}: the source fingerprint failed (${result.error || JSON.stringify(result.json)}); the revision binds the paths alone`)
        receipts = files.map((artifactPath) => ({ artifactPath, format: 'unfingerprinted' }))
      }
    }
    return { ok: true, revision: sha256Json({ receipts, context }) }
  }
  async function documentReceipt(dispatch, { label, phase, runner, files, relayFile }) {
    if (!Array.isArray(files) || !files.length) return { ok: false, error: 'document receipt requires explicit file paths' }
    const result = await run(dispatch, { label, phase, runner, argv: ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), ...files.flatMap(file => ['--document', file])], file: relayFile })
    if (!result.ok) return result
    if (result.exitCode !== 0 || !result.json || !Array.isArray(result.json.receipts)) return { ok: false, error: `document verification failed: ${JSON.stringify(result.json)}` }
    const receipts = result.json.receipts
    if (receipts.length !== files.length || receipts.some((r, i) => r.artifactPath !== files[i] || !/^[a-f0-9]{64}$/.test(r.sha256 || '') || !Number.isSafeInteger(r.bytes) || r.bytes < 1 || r.format !== 'text')) return { ok: false, error: 'invalid document receipt' }
    return { ok: true, receipts }
  }
  return { ARTIFACT_SCHEMA, contractPath, schemaOption, artifactBrief, acceptArtifact, authorArtifact, artifactRevision, documentReceipt, canonicalJson, sha256Ascii, sha256Json, quote, shellWords, exec, depscore, run, checkFile, ensureJson, inline, exceptionOf, unflatten, parse, SCHEMA }
})()
// ===== SHARED BLOCK relay — END =====

// ── A LIMIT BELONGS WHERE THE DATA IS MADE, AND AN OVERAGE IS A FLAG ─────────────
//
// Two rules, and they are different rules.
//
// ONE: a limit is never a JSON-Schema maxItems/minItems/maxLength. A schema bound cannot
// trim an over-long answer — the runtime rejects the WHOLE result, the caller receives a
// bare null it cannot tell from a dead agent, and the run halts. One really did, on 61
// items against a bound of 60, claiming files were unread that had been read. So a limit
// is STATED in the prompt and COUNTED here, once the result is in hand.
//
// TWO, and it decides whether a limit may be stated at all: a limit belongs at the layer
// where the data is CREATED, not where it is read. A dispatch that AUTHORS its output —
// criteria, findings, a persona, a draft — chooses its own volume, so a ceiling stated to
// it is a real instruction it can honour. A dispatch that READS or EXTRACTS — an
// inventory of what exists, the evidence found in a repository, the ids it was handed,
// what git printed — has a volume that is a property of the source. Telling it "at most
// N" instructs it to truncate, which loses information, or to lie. Those dispatches get
// NO stated ceiling; bounding what they may DRAW ON (which repository, which files) is
// the guard that works, and it already lives in their prompts. Where a read's volume
// genuinely ought to be smaller, the fix belongs upstream, in whatever made the data.
//
// BOTH kinds are still counted here, because a wildly unexpected count is exactly the
// signal worth having, and nothing is ever truncated, dropped, reordered or summarised at
// any multiple. The count is a GRADUATED FLAG: modestly over the expected figure is
// ordinary variation and reads as an observation; at SCRUTINY_MULTIPLE times it or more,
// the shape is no longer variation — it is what padding, a misread assignment or
// duplicated entries look like — and it is logged prominently so a person looks. 2x is
// the threshold because a single band has to sit above the honest overshoots this
// pipeline actually produces (61 against 60 is 1.02x; the worst recorded lens overshoot
// is well under 1.5x) and below the runaway enumerations the limits exist to catch. It is
// a flag for a person, never a thing the code acts on: neither branch alters control flow.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const limitFindings = []
const SCRUTINY_MULTIPLE = 2
function checkLimit(where, what, value, expected, min) {
  const n = Array.isArray(value) ? value.length : typeof value === 'string' ? value.length : null
  if (n === null) return value
  if (typeof expected === 'number' && n > expected) {
    const ratio = expected > 0 ? n / expected : Infinity
    const scrutinise = ratio >= SCRUTINY_MULTIPLE
    limitFindings.push({ where, what, count: n, expected, ratio: Math.round(ratio * 100) / 100, severity: scrutinise ? 'scrutinise' : 'observation' })
    log(
      scrutinise
        ? `⚠ ${where}: ${what} returned ${n} where ${expected} was expected — ${Math.round(ratio * 10) / 10}x. Every item is kept and nothing downstream changes, but a count this far over is the shape of padding, a misread assignment or duplicated entries: worth a look.`
        : `${where}: ${what} returned ${n} where ${expected} was expected — over by ${n - expected}; every item is kept.`
    )
  }
  if (typeof min === 'number' && n < min) {
    limitFindings.push({ where, what, count: n, expected: min, severity: 'under' })
    log(`${where}: ${what} returned ${n}, under the ${min} this asked for — carried through as returned.`)
  }
  return value
}

// args: {
//   request:    { id?, title?, description?, repoPath?, requestedBy? },  // raw stakeholder request
//   workDir:    string,   // absolute path of this run's directory: every agent writes its file there, and a
//                         // rerun with the same workDir reuses every accepted file whose inputs are unchanged
//   pluginRoot: string,   // absolute path of this plugin's root: its checked relay validates and publishes each file
//   maxPasses?: number,   // bounded maker-checker passes for the PRD draft (default 2)
// }
// returns: {
//   ok, request, workDir,
//   files: { request, intake, persona, okrs, draft, prd, alignment, ruling },  // paths; null where not written
//   prd: { title, path, draftPath },  // the PRD Markdown file the prd-writer wrote, and its draft record
//   alignmentVerdict, decision,       // 'aligned' | 'misaligned', and 'accept' | 'reject' | null; the files hold the reasons
//   retries, note,
//   epic: {                    // the Epic created together with the PRD — the caller writes it with bd
//     key:         'E1',       // stable local key; downstream parent links reference it
//     type:        'epic',     // literal — the bead face of the PRD; a container, never worked and never itself decomposed
//     title:       string,     // the PRD's title
//     descriptionFrom: string, // <draft record>#/epicScope: the one-paragraph scope statement the bead's description is
//     prdRef:      string,     // the originating request's id (falls back to the PRD's title)
//     matrixRecord: {          // how the pair is recorded, once the caller has written the Epic bead and the PRD file:
//       role:    string,       // the atw-matrix role that runs it (ATW_MATRIX_ROLE)
//       command: string[],     // atw-matrix sync-epics --bead <the Epic's beads id> --prd <the PRD's path>
//       records: string,       // what the command records
//     },
//   },
// }
// The matrix is the one record of which PRD an Epic has: no `**Epic:**` line in the PRD and no `prd:` label
// on the bead. This mini writes neither the bead nor the PRD's vault file, so the caller that writes them runs
// epic.matrixRecord.command with the bead id and the path filled in; the pair is recorded only then.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const request = a.request || {}
const MAX_PASSES = Math.max(1, Math.floor(Number(a.maxPasses)) || 2)
// The role sync-epics runs for (matrix-kinds.json roles), and the two values of the command that exist
// only after the caller has written the Epic bead and the PRD file.
const MATRIX_RECORD_ROLE = 'script'
const EPIC_ID_PLACEHOLDER = '<the Epic bead id>'
const PRD_PATH_PLACEHOLDER = '<the PRD file: absolute, or relative to the vault root>'
const repo = request.repoPath || '(repo path not provided — this is a docs/vault artifact)'
if (!request.title && !request.description) {
  const error = 'no request.title/description supplied — refusing to run without a work item'
  return dispatchOutcome({ ok: false, stage: 'input', error, headline: error })
}
const absolute = (v) => (typeof v === 'string' && v.trim().startsWith('/') ? v.trim().replace(/\/+$/, '') : '')
const work = absolute(a.workDir)
const PLUGIN = absolute(a.pluginRoot)
if (!work || !PLUGIN) {
  const error = `prd-creation needs ${!work ? 'workDir (the absolute path of the directory every agent writes its file in; a rerun with the same one reuses them)' : ''}${!work && !PLUGIN ? ' and ' : ''}${!PLUGIN ? "pluginRoot (the absolute path of this plugin's root, whose checked relay validates each file)" : ''}`
  return dispatchOutcome({ ok: false, stage: 'input', error, headline: error })
}
const RUNNER = `${PLUGIN}/scripts/portfolio/relayrun.py`
const HELPER = `${PLUGIN}/scripts/portfolio/artifactcontract.py`
const file = (name) => `${work}/${name}`
// Every hand-off of this mini is one $defs entry of one contract file, named to the agent by path.
const CONTRACT_FILE = 'skills/artifact-handoff/schemas/prd-creation.schema.json'
const contractOf = (name) => `${CONTRACT_FILE}#/$defs/${name}`
const FILES = { request: file('request.json'), intake: file('intake.json'), persona: file('persona.json'), okrs: file('okrs.json'), ruling: file('ruling.json') }
const draftFile = (pass) => file(`drafts/pass-${pass}.json`)
const prdFile = (pass) => file(`drafts/pass-${pass}.md`)
const alignmentFile = (pass) => file(`alignment/pass-${pass}.json`)
const candidateOf = (final) => final.replace(/\/([^/]+)$/, '/candidates/$1')
// The input files every later agent reads, each with its contract.
const INPUTS = `the intake at ${FILES.intake} (${contractOf('Intake')}), the persona at ${FILES.persona} (${contractOf('Persona')}) and the objective and key results at ${FILES.okrs} (${contractOf('Okrs')}); contract paths are from the plugin root ${PLUGIN}`

/**
 * Authors one file of this mini. An accepted file whose inputs are unchanged is reused and no session
 * starts; otherwise `produce(brief)` dispatches the session, `brief` binding it to its candidate and
 * contract, and the candidate it wrote is validated and published. Returns relayKit.authorArtifact's
 * result: { ok, facts, counts } or { ok: false, error }.
 */
async function author({ name, phase: stage, contract, final, inputs, keys = [], counts = [], produce }) {
  if (dispatchInterruption) return { ok: false, error: 'dispatch interrupted' }
  const binding = await relayKit.artifactRevision(settleAgent, { label: `${name}:inputs`, phase: stage, runner: RUNNER, files: inputs, relayFile: file(`relay/${name}-inputs.json`), context: { name } })
  if (!binding.ok) return binding
  const candidate = candidateOf(final)
  return relayKit.authorArtifact(settleAgent, {
    label: `save:${name}`, phase: stage, runner: RUNNER, candidate, file: final, contract: contractOf(contract),
    revision: binding.revision, relayFile: file(`relay/${name}-accepted.json`), keys, counts,
  }, () => produce(relayKit.artifactBrief(candidate, contractOf(contract), binding.revision, HELPER)), () => !!dispatchInterruption)
}
/** The failure a phase returns when its file was not authored. */
function notAuthored(stage, what, result, more = {}) {
  const died = dispatchDeaths(stage)
  const error = `${what} was not authored: ${(result && result.error) || 'no result'}`
  return dispatchOutcome({ ok: false, stage: died.length ? 'agent-dispatch-failed' : stage, error, headline: error, workDir: work, ...more, ...(died.length ? { dispatchFailed: true, dispatchFailures: died } : {}) })
}
/** An array of `n` slots, for counting a list the relay reported by its length. */
const counted = (result, key) => Array.from({ length: Number(result && result.counts && result.counts[key]) || 0 })

// ── Intake ──────────────────────────────────────────────────────────────────
phase('Intake')

// ── ONE INTAKE SESSION, NOT TWO ─────────────────────────────────────────────────
//
// This was a `prd-creation-lead` router (`intake:scope`) followed by the intake writer.
// The router authored nothing and ruled nothing — it framed the request as scope in/out
// and open questions — and its ONLY reader was the writer below, which also received the
// raw request verbatim. So the run paid a full session-start (the dominant cost of any
// session, ahead of the work it does) to reformat text its one consumer already had.
//
// Segregation of duties is untouched: nothing here judges anything. The scope framing and
// the brief are both intake authoring, and the independent alignment check downstream
// still judges the PRD against this brief without having written any of it.
// ── THE LIST LIMITS EACH MAKER WORKS UNDER ───────────────────────────────────────
//
// Stated in each brief, counted after the result is in hand, never bound in the schema:
// one list entry over must not cost this mini the PRD, the persona or the OKRs that came
// back with it. Every number is the one this mini has always worked to, raised where it
// sat close to plausible output — a large PRD legitimately states more than 40 P0
// criteria (the measured maximum across 147 PRDs in this project is 68).
const SCOPE_LIST_MAX = 25
const CONSTRAINTS_MAX = 30
const OPEN_QUESTIONS_MAX = 25
const PERSONA_LIST_MAX = 15
const KEY_RESULTS_MAX = 8
const SECTIONS_MAX = 50
const P0_CRITERIA_MAX = 80
const ALIGNMENT_DIMENSIONS = ['intake', 'persona', 'okr', 'template']

// The request is saved first, so the intake writer reads it from a file and a rerun is bound to it.
const requestValue = Object.fromEntries(['id', 'title', 'description', 'repoPath', 'requestedBy'].filter((k) => typeof request[k] === 'string' && request[k]).map((k) => [k, request[k]]))
const requestSaved = await relayKit.ensureJson(settleAgent, { label: 'request', phase: 'Intake', runner: RUNNER, file: FILES.request, value: requestValue })
if (!requestSaved.ok) return notAuthored('Intake', `the request file ${FILES.request}`, requestSaved)

const intake = await author({
  name: 'intake', phase: 'Intake', contract: 'Intake', final: FILES.intake, inputs: [FILES.request],
  counts: ['inScope', 'outOfScope', 'constraints', 'openQuestions'],
  produce: (brief) => settleAgent(
    `Scope this stakeholder request and capture it as a structured intake brief: the scope framing and the brief, in one pass. State the problem, the audience, and the desired outcome plainly — WHAT the job seeker needs, not HOW to build it. Do NOT write the PRD itself, the persona, or the OKRs; later makers own those.

The raw stakeholder request is ${FILES.request} (${contractOf('Request')}, path from the plugin root ${PLUGIN}).

Working repository context: ${repo}

READING BUDGET (binding): the request is your source. This is a framing task over a few paragraphs of stakeholder text — read at most 5 other files, and only to resolve a term the request uses that you genuinely cannot interpret. Do not survey the repository or the polyrepo, and carry anything still unclear as an open question rather than investigating it.

Write the intake to its contract, named below; the descriptions there define every member. Ceilings: ${SCOPE_LIST_MAX} entries each in \`inScope\` and \`outOfScope\`, ${CONSTRAINTS_MAX} in \`constraints\`, ${OPEN_QUESTIONS_MAX} in \`openQuestions\`. A framing that needs more than that is enumerating restatements of one concern.${brief}`,
    {
      label: 'intake:scope-and-brief',
      effort: 'medium',
      phase: 'Intake',
      agentType: 'stakeholder-request-intake-writer', // model: its definition's front matter sets it (sonnet)
      schema: relayKit.ARTIFACT_SCHEMA,
    }
  ),
})
if (!intake.ok) return notAuthored('Intake', 'the intake', intake)
// The stated ceilings, measured. Observation only: every entry is kept.
checkLimit('Intake', 'inScope', counted(intake, 'inScope'), SCOPE_LIST_MAX)
checkLimit('Intake', 'outOfScope', counted(intake, 'outOfScope'), SCOPE_LIST_MAX)
checkLimit('Intake', 'constraints', counted(intake, 'constraints'), CONSTRAINTS_MAX)
checkLimit('Intake', 'openQuestions', counted(intake, 'openQuestions'), OPEN_QUESTIONS_MAX)

// ── Persona & OKR (parallel makers) ───────────────────────────────────────────
phase('Persona & OKR')

const [persona, okrs] = await parallel([
  () => author({
    name: 'persona', phase: 'Persona & OKR', contract: 'Persona', final: FILES.persona, inputs: [FILES.intake],
    counts: ['goals', 'frustrations'],
    produce: (brief) => settleAgent(
      `Author the target persona this PRD serves. Take the persona's population from the intake brief at ${FILES.intake} (${contractOf('Intake')}, path from the plugin root ${PLUGIN}), and ground the persona in it.

Write the persona to its contract, named below; the descriptions there define every member. At most ${PERSONA_LIST_MAX} entries each in \`goals\` and \`frustrations\`. A persona with more goals than that has no persona.${brief}`,
      {
        label: 'persona:author',
        effort: 'low',
        phase: 'Persona & OKR',
        agentType: 'feature-persona-writer', // model: its definition's front matter sets it (sonnet)
        schema: relayKit.ARTIFACT_SCHEMA,
      }
    ),
  }),
  () => author({
    name: 'okrs', phase: 'Persona & OKR', contract: 'Okrs', final: FILES.okrs, inputs: [FILES.intake],
    counts: ['keyResults'],
    produce: (brief) => settleAgent(
      `Author the objective and key results this feature must move. The objective is a qualitative, job-seeker-centered statement; each key result is a measurable signal that proves the objective was met. Ground them in the intake brief at ${FILES.intake} (${contractOf('Intake')}, path from the plugin root ${PLUGIN}).

Write them to their contract, named below; the descriptions there define every member. At most ${KEY_RESULTS_MAX} key results: an objective with more than a handful of key results has no objective.${brief}`,
      {
        label: 'okr:author',
        effort: 'low',
        phase: 'Persona & OKR',
        agentType: 'feature-objective-writer', // model: its definition's front matter sets it (sonnet)
        schema: relayKit.ARTIFACT_SCHEMA,
      }
    ),
  }),
])

// ── PRD Draft (maker-checker, bounded loop) ───────────────────────────────────
phase('PRD Draft')

if (!persona || !persona.ok || !okrs || !okrs.ok) {
  const which = `${!(persona && persona.ok) ? 'the persona' : ''}${!(persona && persona.ok) && !(okrs && okrs.ok) ? ' and ' : ''}${!(okrs && okrs.ok) ? 'the objective and key results' : ''}`
  return notAuthored('Persona & OKR', which, !(persona && persona.ok) ? persona : okrs, { files: { request: FILES.request, intake: FILES.intake } })
}

checkLimit('Persona & OKR', 'goals', counted(persona, 'goals'), PERSONA_LIST_MAX)
checkLimit('Persona & OKR', 'frustrations', counted(persona, 'frustrations'), PERSONA_LIST_MAX)
checkLimit('Persona & OKR', 'keyResults', counted(okrs, 'keyResults'), KEY_RESULTS_MAX)

const MAKER_INPUTS = [FILES.intake, FILES.persona, FILES.okrs]

// Maker: prd-writer authors the template-conformant PRD and, in the same pass,
// the one-paragraph scope statement for the Epic that is created alongside it.
// Authoring both together keeps the pairing literal and the Epic in sync when
// the draft loops on checker feedback — no separate analysis pass is needed,
// because the PRD already contains the scope.
function draftPRD(pass, brief) {
  const previous = pass > 1
    ? `\n\nALIGNMENT FEEDBACK from the independent checker: the verdict on your previous draft (${prdFile(pass - 1)}) is ${alignmentFile(pass - 1)} (${contractOf('Alignment')}). Address its \`feedback\` and every dimension it marks unsatisfied, starting from that draft.`
    : ''
  return settleAgent(
    `Author the template-conformant Product Requirements Document (PRD) from ${INPUTS}. Stay WHAT-not-HOW — describe the required behavior and outcomes, never the implementation. Follow the standard PRD template: required sections, P0 acceptance criteria, no leftover scaffolding. Resolve or flag each of the intake's \`openQuestions\`.

Write the full PRD in Markdown to ${prdFile(pass)}. It carries no \`**Epic:**\` line: the matrix is the one record of which Epic a PRD belongs to. At most ${SECTIONS_MAX} section headings, and P0 acceptance criteria ONLY, as given/when/then, at most ${P0_CRITERIA_MAX}, each clause under 30 words: every one of them is re-read by the alignment checker, by PRD validation, by the TRD author and by every spec author.

Then write the draft record to its contract, named below; the descriptions there define every member.${previous}${brief}`,
    {
      label: `prd:draft:${pass}`,
      effort: 'medium',
      phase: 'PRD Draft',
      agentType: 'prd-writer', // model: its definition's front matter sets it (opus)
      schema: relayKit.ARTIFACT_SCHEMA,
    }
  )
}

// Checker: an INDEPENDENT verifier — never the prd-writer.
function verifyAlignment(pass, brief) {
  return settleAgent(
    `You are an INDEPENDENT alignment verifier. You did NOT write this PRD — you only judge it. Do NOT rewrite the PRD. Verify the PRD at ${prdFile(pass)} (its draft record: ${draftFile(pass)}) aligns with ${INPUTS}, and that it is template-conformant and WHAT-not-HOW.

Write your verdict to its contract, named below; the descriptions there define the verdict and the dimensions — exactly ${ALIGNMENT_DIMENSIONS.length} entries in \`dimensions\`, one per dimension and no others.${brief}`,
    {
      label: `prd:alignment-check:${pass}`,
      // A checker, and the prd-alignment-verifier's own file already says `effort: low`.
      // It judges a document against three stated inputs; the expensive judgment in this
      // mini is the deadlock ruling below.
      effort: 'low',
      phase: 'PRD Draft',
      agentType: 'prd-alignment-verifier', // model: its definition's front matter sets it (sonnet)
      schema: relayKit.ARTIFACT_SCHEMA,
    }
  )
}

let draft = null
let alignment = null
let alignmentVerdict = null
let actionable = true
let deadlocked = false
let passesRun = 0
/** Every re-draft after a misaligned verdict, with what changed in the writer's input. */
const retries = []
for (let pass = 1; pass <= MAX_PASSES; pass++) {
  passesRun = pass
  draft = await author({
    name: `draft-${pass}`, phase: 'PRD Draft', contract: 'Draft', final: draftFile(pass),
    inputs: [...MAKER_INPUTS, ...(pass > 1 ? [prdFile(pass - 1), alignmentFile(pass - 1)] : [])],
    keys: ['title'],
    produce: (brief) => draftPRD(pass, brief),
  })
  if (!draft.ok) return notAuthored('PRD Draft', `the PRD draft of pass ${pass}`, draft, { files: FILES })
  // The PRD itself is the Markdown file; its draft record does not repeat it.
  const prdDocument = await relayKit.documentReceipt(settleAgent, { label: `prd:document:${pass}`, phase: 'PRD Draft', runner: RUNNER, files: [prdFile(pass)], relayFile: file(`relay/draft-${pass}-document.json`) })
  if (!prdDocument.ok) return notAuthored('PRD Draft', `the PRD file ${prdFile(pass)}`, prdDocument)
  alignment = await author({
    name: `alignment-${pass}`, phase: 'PRD Draft', contract: 'Alignment', final: alignmentFile(pass),
    inputs: [...MAKER_INPUTS, draftFile(pass), prdFile(pass)],
    keys: ['verdict', 'feedback', 'dimensions.dimension', 'dimensions.satisfied'], counts: ['dimensions'],
    produce: (brief) => verifyAlignment(pass, brief),
  })
  if (!alignment.ok) return notAuthored('PRD Draft', `the alignment verdict of pass ${pass}`, alignment, { prd: { title: draft.facts.title || null, path: prdFile(pass), draftPath: draftFile(pass) } })
  checkLimit(`PRD Draft (pass ${pass})`, 'alignment dimensions', counted(alignment, 'dimensions'), ALIGNMENT_DIMENSIONS.length)
  // The verdict is read off the checker's own dimensions: "aligned" beside a dimension it
  // marked unsatisfied is not alignment, and the unsatisfied evidence is the rework brief.
  const dimensions = Array.isArray(alignment.facts.dimensions) ? alignment.facts.dimensions : []
  const unsatisfied = dimensions.filter((d) => d && d.satisfied === false)
  alignmentVerdict = alignment.facts.verdict === 'aligned' && !unsatisfied.length ? 'aligned' : 'misaligned'
  if (alignment.facts.verdict === 'aligned' && unsatisfied.length) {
    log(`PRD draft: the checker said aligned but marked ${unsatisfied.map((d) => d.dimension).join(', ')} unsatisfied — read as misaligned`)
  }
  if (alignmentVerdict === 'aligned') {
    log(`PRD draft: ALIGNED on pass ${pass}/${MAX_PASSES}`)
    break
  }
  // A misaligned verdict that names nothing to change would re-run the maker on identical input.
  actionable = !!String(alignment.facts.feedback || '').trim() || unsatisfied.length > 0
  log(`PRD draft: MISALIGNED pass ${pass}/${MAX_PASSES} — the verdict is ${alignmentFile(pass)}${actionable ? '' : ' (it names nothing to change)'}`)
  // With nothing to act on, another draft is the same dispatch on the same input: a blind
  // retry. The standoff goes to the decider now instead.
  if (pass === MAX_PASSES || !actionable) {
    deadlocked = true
    break
  }
  retries.push({ pass: pass + 1, whatChanged: `the prd-writer is handed the alignment verdict of pass ${pass}: ${alignmentFile(pass)}` })
}

// Deadlock: the maker and checker could not converge — the review-dispute-decider rules.
let ruling = null
if (deadlocked) {
  log('PRD draft: maker-checker deadlock — escalating to review-dispute-decider for a binding ruling')
  ruling = await author({
    name: 'ruling', phase: 'PRD Draft', contract: 'DeadlockRuling', final: FILES.ruling,
    inputs: [...MAKER_INPUTS, draftFile(passesRun), prdFile(passesRun), alignmentFile(passesRun)],
    keys: ['verdict'],
    produce: (brief) => settleAgent(
      `The prd-writer and the independent prd-alignment-verifier could not converge after ${passesRun} pass(es)${actionable ? '' : ', and the checker named nothing the writer could act on'}. Rule on the standoff, as a PRD deadlock ruling. Your ruling is binding.

The checker's latest verdict is ${alignmentFile(passesRun)}, on the PRD at ${prdFile(passesRun)}. It judged the PRD against ${INPUTS}: judge its objection against the same files.

Write your ruling to its contract, named below; the descriptions there define the verdict and the rationale.${brief}`,
      {
        label: 'prd:deadlock-ruling',
        effort: 'high',
        phase: 'PRD Draft',
        agentType: 'review-dispute-decider', // model: its definition's front matter sets it (opus)
        schema: relayKit.ARTIFACT_SCHEMA,
      }
    ),
  })
}
const decision = ruling && ruling.ok ? ruling.facts.verdict || null : null

const aligned = alignmentVerdict === 'aligned'
const ruledAccept = decision === 'accept'
const ok = Boolean(aligned || ruledAccept)
// A deadlock ruling that never came back is a dispatch failure, not a rejection.
const deciderDied = deadlocked && !decision
const title = draft && draft.ok ? draft.facts.title || null : null

// A PRD and its Epic are created at the same time — the Epic is the bead-side
// half of that pairing, assembled here from the maker's own output rather than
// a fresh analysis pass. It is a CONTAINER: no acceptance criteria and no repo
// scope, because one Epic may span repos and its Stories (one per repo) are
// minted later, each alongside its Spec. Exactly one epic is emitted per PRD;
// this mini never writes to .beads — the caller writes the bead with bd.
const epic = title
  ? {
      key: 'E1',
      type: 'epic',
      title,
      descriptionFrom: `${draftFile(passesRun)}#/epicScope`,
      // Inside this mini the PRD has no bead id or vault path yet, so the ref is
      // the originating request id when supplied, else the PRD's own title.
      prdRef: request.id || title,
      // The pair is recorded in the matrix, and nowhere else, by this command, which the caller runs once
      // the Epic bead exists and the PRD file is written. The two placeholders are the caller's to fill.
      matrixRecord: {
        role: MATRIX_RECORD_ROLE,
        command: ['atw-matrix', 'sync-epics', '--bead', EPIC_ID_PLACEHOLDER, '--prd', PRD_PATH_PLACEHOLDER],
        records: 'the epic entry with its PRD path and hash, one requirement entry per #### heading under ## Requirements, and hasRequirement from the Epic to each',
      },
    }
  : null

const rejected = `the PRD did not align within ${passesRun} pass(es)${decision ? `; ruled ${decision} (${FILES.ruling})` : ''}`
return dispatchOutcome({
  ok,
  stage: ok ? 'done' : deciderDied ? 'agent-dispatch-failed' : 'prd-draft',
  headline: ok
    ? `PRD "${title}" authored and ${aligned ? 'aligned' : 'accepted by ruling'}`
    : deciderDied
      ? 'the PRD did not align and the deadlock ruling returned nothing'
      : rejected,
  ...(ok ? {} : { error: deciderDied ? `the PRD did not align and the deadlock ruling returned nothing${ruling && ruling.error ? `: ${ruling.error}` : ''}` : rejected }),
  ...(deciderDied ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('PRD Draft') } : {}),
  request: request.id ? request.id : null,
  workDir: work,
  files: {
    request: FILES.request,
    intake: FILES.intake,
    persona: FILES.persona,
    okrs: FILES.okrs,
    draft: draftFile(passesRun),
    prd: prdFile(passesRun),
    alignment: alignmentFile(passesRun),
    ruling: decision ? FILES.ruling : null,
  },
  prd: { title, path: prdFile(passesRun), draftPath: draftFile(passesRun) },
  epic,
  alignmentVerdict,
  decision,
  retries,
  ...(limitFindings.length ? { limitFindings } : {}),
  note: ok
    ? `PRD is intake/persona/OKR-aligned and template-conformant: ${prdFile(passesRun)}. Once the Epic bead exists and the PRD file is written to the vault, record the pair in the matrix: ${epic.matrixRecord.command.join(' ')} (role ${MATRIX_RECORD_ROLE}).`
    : `PRD did not reach alignment within the bounded passes; the verdicts are under ${file('alignment')}${decision ? ` and the binding ruling is ${FILES.ruling}` : ''}.`,
})
