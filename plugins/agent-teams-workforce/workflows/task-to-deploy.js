export const meta = {
  name: 'task-to-deploy',
  description:
    "Builds a Task on its Story's branch by running the steps its step journal lists, from the first step that is not done. The driver names the journal file and the run (journal: { path, run }); the workflow reads the journal once through the checked relay (bin/atw-step-journal read) and reports every change on its log as a STEP-JOURNAL line the driver applies: step started, step done with its artifacts and the steps its result adds, step failed with its cause. Each step takes its inputs from the artifacts earlier steps recorded, so a restarted build continues on the tree as the stopped run left it. The steps and what each records, reads and adds are defined in skills/pipeline-contracts/schemas/pipeline-steps.json (pipeline build): the Story's worktree; for a web-ui Task the design source (the newest cds bundle supplied for its artifact); for an infrastructure Task the provisioning intent; the regression scope, assessed, reviewed and validated; the baseline run of the suite command the repository declares; failing tests from each test agent the contract's surfaces call for, judged by a suite run that adds another round when Red does not hold; the implementers selected and run one after another, judged by a suite run that adds a ruling on the tests they name or another round when the suite is not green, each implementer handed the shared capabilities the Task must use (atw-matrix uses --ids, with the matrix ids the Task states); a reuse audit of the changed files against those capabilities (atw-matrix check-reuse), whose violations go back to the implementers once; a refactor, undone when the suite goes red; for a web-ui Task an audit against its design source, whose violations go back to the implementers once; the documentation audit and one update per documentation agent it assigns; a final suite run; the regression mapping, its review and its verification; and the commit to the Story's branch. A step that cannot go on fails with its cause (red-unsatisfied, no-progress, blocked-upstream, green-modified-tests, reuse-violation, cds-audit and others) and the run stops there. Every deterministic step runs through relayrun.py with relay.runner (else pluginRoot's), and its relay files go under relay.dir, the Task's own directory, the same on every dispatch. It deploys nothing and opens no pull request: the Story deploys and opens one pull request once its last Task is done. Returns { ok, stage, beadId, storyId, headline, detailPath, branch, worktree, commit }, with step naming the step that failed.",
  phases: [
    { title: 'Workspace', detail: "establishes or reuses the Story's worktree, and selects a web-ui Task's design source" },
    { title: 'Infra Intent', detail: 'authors the provisioning intent for an infrastructure Task' },
    { title: 'Regression Scope', detail: 'maps the change to current and earlier requirements, reviews and validates the scope' },
    { title: 'Baseline', detail: "resolves the repository's suite command and runs it before any change" },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Reuse Audit', detail: 'checks the changed files against the shared capabilities the Task must use' },
    { title: 'Refactor' },
    { title: 'CDS Audit', detail: "audits a web-ui Task's changed files against its design source" },
    { title: 'Documentation' },
    { title: 'Commit', detail: 'runs the suite a final time, verifies the regression evidence and commits the Task to the Story branch' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; filled from skills/pipeline-contracts/schemas/driver-surface.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// skills/pipeline-contracts/schemas/driver-surface.schema.json, inlined by shared-blocks.mjs. DRIVER_SURFACE maps
// each x-constant of $defs.DriverEnvironment to its environment variable name and each x-values entry of
// $defs.RateLimitInfo to its wire value, so no workflow names a driver environment variable or a rate-limit value itself.
const DRIVER_SURFACE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"agent-teams-workforce/skills/pipeline-contracts/schemas/driver-surface.schema.json","title":"Driver module surface","description":"The one definition of the driver (ops/sdlc-automation in the control repository) surface the plugin orchestrator imports, the ATW_* environment the driver hands every child and orchestrator process, and the Claude CLI rate-limit event the driver's quota readers take. scripts/generate_types.py renders scripts/driver_surface_types.py from this file; scripts/check_generated.py fails when that module is stale.","x-driver":{"dirParts":["ops","sdlc-automation"],"dirDoc":"Path parts of the driver directory under ATW_CONTROL_REPO.","modules":[{"module":"headlessenv","constant":"HEADLESSENV_MODULE","protocol":"HeadlessEnvironment","doc":"Driver headlessenv module surface consumed by session setup.","members":[{"name":"DENIED_TOOLS","kind":"attribute","python":"tuple[str, ...]","doc":"Tools every headless build and deploy Workflow session the driver dispatches is denied, in order."},{"name":"child_env","kind":"method","params":[["scratch","Path"]],"returns":"dict[str, str]","doc":"Build the subprocess environment: DriverEnvironment over the inherited one."}]},{"module":"fablewall","constant":"FABLEWALL_MODULE","protocol":"FableWall","doc":"Driver fablewall module surface consumed by model fallback.","members":[{"name":"is_refusal","kind":"method","params":[["info","object"]],"returns":"bool","doc":"Return whether a RateLimitInfo is a model-specific refusal."},{"name":"reset_of","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the model-specific reset of a RateLimitInfo, in epoch seconds."}]},{"module":"breaker","constant":"BREAKER_MODULE","protocol":"Breaker","doc":"Driver breaker module surface consumed by quota handling.","members":[{"name":"exhausted_reset","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the latest reset among the exhausted windows, in epoch seconds."}]},{"module":"childproc","constant":"CHILDPROC_MODULE","protocol":"ChildProcess","doc":"Driver childproc module termination policy.","members":[{"name":"TERMINATE_GRACE","kind":"attribute","python":"float","doc":"Seconds a terminated child is given before it is killed."}]}]},"$defs":{"DriverEnvironment":{"description":"The ATW_* and process environment the driver hands child and orchestrator processes.","x-details":"headlessenv.child_env(scratch) returns these keys over the inherited os.environ (atw.environment fills only absent or blank values); the keeper, supervisor and orchestrator dispatch add ATW_STOP_FILE, ATW_EXECUTION_ID and ATW_ORCH_IDLE.","type":"object","x-python":{"typeddict":"DriverEnvironment"},"properties":{"ATW_PROJECT_ROOT":{"type":"string","minLength":1,"description":"Absolute path of the project root.","x-constant":"PROJECT_ROOT_ENV"},"ATW_PRD_EPIC_SYNC":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic sync script.","x-constant":"PRD_EPIC_SYNC_ENV"},"ATW_PRD_EPIC_VERIFY":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic verify script.","x-constant":"PRD_EPIC_VERIFY_ENV"},"ATW_CONTROL_REPO":{"type":"string","minLength":1,"description":"Absolute path of the control repository (the project's control repository, else the driver's repository root). The driver modules live under it at DRIVER_DIR_PARTS.","x-constant":"CONTROL_REPO_ENV"},"ATW_ARCH_PATH":{"type":"string","minLength":1,"description":"The architecture root; set only when the driver knows one. Readers use args.archPath first and fall back to it.","x-constant":"ARCH_PATH_ENV"},"ATW_DESIGN_PACKAGES_DIR":{"type":"string","minLength":1,"description":"The owner's cds design packages directory; optional.","x-constant":"DESIGN_PACKAGES_ENV"},"ATW_PRD_DIR":{"type":"string","minLength":1,"description":"The first PRD root; optional.","x-constant":"PRD_DIR_ENV"},"PATH":{"type":"string","minLength":1,"description":"The controller runtime's bin directory first, de-duplicated.","x-constant":"PATH_ENV"},"TMPDIR":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMPDIR_ENV","x-group":"SCRATCH_ENV_KEYS"},"TMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"TEMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TEMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS":{"type":"string","const":"0","description":"Disables the Claude CLI print-mode background wait.","x-constant":"BACKGROUND_WAIT_KEY","x-const-mapping":"BACKGROUND_WAIT_ENV"},"ATW_STOP_FILE":{"type":"string","minLength":1,"description":"Path of the stop marker file; absent means no stop marker. A consumer touches the file (mode 0o600) to request a drain, or tests whether it exists. It only requests a stop: how a stop is classified belongs to the handback contract.","x-constant":"STOP_FILE_ENV","x-file-mode":"STOP_FILE_MODE"},"ATW_EXECUTION_ID":{"type":"string","minLength":1,"description":"The driver execution id. Required for an orchestrator dispatch; set for a headless workflow session only when its arguments carry an executionId.","x-constant":"EXECUTION_ID_ENV"},"ATW_ORCH_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"3600","description":"Orchestrator idle limit in seconds: a positive finite float. A non-finite or non-positive value is a ValueError.","x-constant":"ORCH_IDLE_ENV","x-default-constant":"ORCH_IDLE_DEFAULT"},"ATW_SESSION_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"1800","description":"Agent session idle limit in seconds: a session that writes no stream line for this long is ended with cause timeout. A positive finite float; a non-finite or non-positive value is a ValueError.","x-constant":"SESSION_IDLE_ENV","x-default-constant":"SESSION_IDLE_DEFAULT"},"ATW_SESSION_LIMIT":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"7200","description":"Agent session hard limit in seconds for an agent whose definition states no x-sessionLimit: a session running this long is ended with cause timeout. A positive finite float; a non-finite or non-positive value is a ValueError.","x-constant":"SESSION_LIMIT_ENV","x-default-constant":"SESSION_LIMIT_DEFAULT"},"ATW_SUBAGENT_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"300","description":"Subagent stall limit in seconds: while an Agent call of a session is open, a subagent transcript that has written nothing for this long ends the session with cause timeout. A positive finite float; a non-finite or non-positive value is a ValueError.","x-constant":"SUBAGENT_IDLE_ENV","x-default-constant":"SUBAGENT_IDLE_DEFAULT"},"ATW_HEARTBEAT":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"300","description":"Seconds between the heartbeats a running agent session announces. A positive finite float; a non-finite or non-positive value is a ValueError.","x-constant":"HEARTBEAT_ENV","x-default-constant":"HEARTBEAT_DEFAULT"}},"required":["ATW_PROJECT_ROOT","ATW_PRD_EPIC_SYNC","ATW_PRD_EPIC_VERIFY","ATW_CONTROL_REPO","PATH","TMPDIR","TMP","TEMP","CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"],"additionalProperties":{"type":"string"}},"StopFileMode":{"description":"Permission bits a consumer creates the stop marker file with.","type":"integer","const":384,"x-python":{"constant":"STOP_FILE_MODE","type":"int","render":"0o600"}},"DeniedTool":{"description":"A tool every headless build and deploy Workflow session the driver dispatches is denied. DENIED_TOOLS keeps this order.","type":"string","enum":["WebFetch","WebSearch","Artifact","SendMessage","EndConversation","CronCreate","CronDelete","CronList","mcp__claude_ai_Gmail__send_message","mcp__claude_ai_Gmail__reply","mcp__claude_ai_Gmail__forward","mcp__claude_ai_Gmail__create_draft","mcp__claude_ai_Google_Drive__share_file","mcp__claude_ai_Google_Drive__create_file","mcp__plugin_slack_slack__slack_send_message","mcp__plugin_slack_slack__slack_send_message_draft","mcp__plugin_slack_slack__slack_schedule_message"],"x-python":{"literal":"DeniedTool","tuple":"DENIED_TOOLS"}},"TerminateGrace":{"description":"Seconds a terminated child process is given before it is killed.","type":"number","const":10,"x-python":{"constant":"TERMINATE_GRACE","type":"float"}},"ExhaustedUtilization":{"description":"A usage window whose utilization is at or above this value is exhausted.","type":"number","const":1,"x-python":{"constant":"EXHAUSTED_UTILIZATION","type":"float"}},"RateLimitStatus":{"description":"RateLimitInfo.status; only rejected is acted on.","type":"string","enum":["allowed","allowed_warning","rejected"],"x-python":{"literal":"RateLimitStatus","tuple":"RATE_LIMIT_STATUSES","constants":{"rejected":"REJECTED_STATUS"}}},"UsageWindowName":{"description":"The account-wide usage windows. Any other window name is model-specific.","type":"string","enum":["five_hour","seven_day"],"x-python":{"literal":"UsageWindowName","frozenset":"ACCOUNT_WINDOWS"}},"UsageWindow":{"description":"One usage window of a RateLimitInfo.","type":"object","x-python":{"typeddict":"UsageWindow"},"properties":{"utilization":{"type":"number","description":"Exhausted when at or above EXHAUSTED_UTILIZATION."},"resetsAt":{"type":"number","description":"Reset time in epoch seconds."}},"required":["utilization"]},"RateLimitInfo":{"description":"The rate_limit_info of a rate_limit_event: the info argument of the quota readers.","type":"object","x-python":{"typeddict":"RateLimitInfo"},"properties":{"status":{"$ref":"#/$defs/RateLimitStatus"},"unifiedWindows":{"type":"object","additionalProperties":{"$ref":"#/$defs/UsageWindow"},"description":"Window name -> usage window."},"resetsAt":{"type":"number","description":"Top-level reset time in epoch seconds."},"rateLimitType":{"type":"string","description":"The value with meaning here is MODEL_OVERAGE_TYPE.","x-values":{"MODEL_OVERAGE_TYPE":"seven_day_overage_included"}},"overageDisabledReason":{"type":"string","description":"The value with meaning here is OUT_OF_CREDITS_REASON.","x-values":{"OUT_OF_CREDITS_REASON":"out_of_credits"}}},"required":["status"]},"RateLimitEvent":{"description":"One Claude CLI stream-json rate-limit event.","type":"object","x-python":{"typeddict":"RateLimitEvent"},"properties":{"type":{"type":"string","const":"rate_limit_event","x-value-constant":"RATE_LIMIT_EVENT_TYPE"},"rate_limit_info":{"$ref":"#/$defs/RateLimitInfo","x-key-constant":"RATE_LIMIT_INFO_KEY"}},"required":["type","rate_limit_info"]}}}
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
// ===== SHARED BLOCK relay — BEGIN (canonical: scripts/shared-blocks/relay.js; filled from skills/artifact-handoff/schemas/checkpoint.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
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
  /** A runner's return: the exit status and stdout, verbatim, as one string. Nothing is rebuilt. */
  const SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['exitCode', 'stdout'],
    properties: { exitCode: { type: 'integer' }, stdout: { type: 'string', description: 'Copy the complete RELAY64v1: line verbatim. Treat its base64 payload as opaque text; never decode or reconstruct it.' } },
  }
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

It prints exactly one line beginning RELAY64v1: followed by base64 text. Copy that entire line as opaque text, including the prefix and any trailing = characters. Do not decode the base64, interpret its contents, or rebuild the JSON. Return the process exit code as \`exitCode\` and that line, verbatim, as the string \`stdout\`: every character as printed, in order, with nothing added, removed, reordered, reformatted or re-typed. Do not parse it, do not summarize it. If it printed more than one line, return all of stdout verbatim. Do not retry, do not repair, do not run any other command.`
  let captureOrdinal = 0
  const RECEIPT_SCHEMA = { type: 'object', additionalProperties: false, required: ['request', 'commandSha256', 'sha256', 'bytes', 'exitCode'], properties: { request: { type: 'string' }, commandSha256: { type: 'string' }, sha256: { type: 'string' }, bytes: { type: 'integer' }, exitCode: { type: 'integer' } } }
  const REGISTERED_SCHEMA = { type: 'object', additionalProperties: false, required: ['state', 'exitCode', 'stdout', 'receipt', 'bridge', 'error'], properties: { state: { type: 'string', enum: ['completed', 'not-started', 'unknown'] }, exitCode: { type: 'integer' }, stdout: { type: 'string' }, receipt: { anyOf: [RECEIPT_SCHEMA, { type: 'null' }] }, bridge: { type: 'boolean' }, error: { type: 'string' } } }
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
  const ARTIFACT_SCHEMA = { type: 'object', additionalProperties: false, required: ['artifactPath'], properties: { artifactPath: { type: 'string' } } }
  // The artifact checkpoint contract, inlined by scripts/shared-blocks.mjs from its one place,
  // skills/artifact-handoff/schemas/checkpoint.schema.json. Never restate any part of it here.
  const CHECKPOINT_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","title":"Artifact checkpoint","description":"The sidecar <candidate><x-sidecarSuffix> that artifactcontract.py checkpoint|complete|submit writes and artifactcontract.py status and jsonartifact.py read. It is built from the agent-authored progress file <candidate><x-progressSuffix> ($defs/Progress) plus the binding keys. The Python types are generated from this file by scripts/generate_checkpoint_contract.py.","x-sidecarSuffix":".checkpoint","x-progressSuffix":".progress.json","x-bindingKeys":["artifactPath","schemaSha256","revision"],"x-authoredStatuses":["in-progress","blocked"],"x-operations":["validate","checkpoint","complete","submit","status"],"type":"object","additionalProperties":false,"required":["status","artifactPath","schemaSha256","revision","task","completed","remaining","artifacts"],"properties":{"status":{"enum":["in-progress","blocked","complete"]},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"schemaSha256":{"$ref":"#/$defs/Sha256"},"candidateSha256":{"$ref":"#/$defs/Sha256"},"revision":{"$ref":"#/$defs/Revision"},"task":{"$ref":"#/$defs/Progress/properties/task"},"completed":{"$ref":"#/$defs/Progress/properties/completed"},"remaining":{"$ref":"#/$defs/Progress/properties/remaining"},"artifacts":{"$ref":"#/$defs/Progress/properties/artifacts"},"reason":{"$ref":"#/$defs/Progress/properties/reason"}},"allOf":[{"if":{"properties":{"status":{"const":"complete"}}},"then":{"required":["candidateSha256"],"properties":{"remaining":{"maxItems":0}}}},{"if":{"properties":{"status":{"const":"blocked"}}},"then":{"required":["reason"],"properties":{"remaining":{"minItems":1}}}}],"$defs":{"ArtifactPath":{"description":"The absolute candidate path; a binding key.","type":"string","minLength":1},"Revision":{"description":"The input revision; a binding key.","type":"string","minLength":1},"Sha256":{"description":"Lowercase hex SHA-256 of a canonical JSON value.","type":"string","pattern":"^[a-f0-9]{64}$"},"Progress":{"description":"The agent-authored progress file <candidate><x-progressSuffix>; its keys are copied into the checkpoint.","type":"object","additionalProperties":false,"required":["task","completed","remaining","artifacts"],"properties":{"task":{"type":"string","minLength":1},"completed":{"type":"array","items":{"type":"string","minLength":1}},"remaining":{"type":"array","items":{"type":"string","minLength":1}},"artifacts":{"type":"array","items":{"type":"string","minLength":1}},"reason":{"type":"string","minLength":1}}},"StatusReport":{"description":"What the status operation reports for a candidate.","type":"object","additionalProperties":false,"required":["status"],"properties":{"status":{"enum":["incomplete","in-progress","blocked","complete-unaccepted"]},"reason":{"type":"string"},"remaining":{"$ref":"#/$defs/Progress/properties/remaining"},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"schemaSha256":{"$ref":"#/$defs/Sha256"},"revision":{"$ref":"#/$defs/Revision"},"candidateSha256":{"$ref":"#/$defs/Sha256"}}},"CommandResult":{"description":"What the validate, checkpoint, complete and submit operations print; status is absent only for submit.","type":"object","additionalProperties":false,"required":[],"properties":{"status":{"enum":["schema-valid","complete-unaccepted","in-progress","blocked","invalid"]},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"error":{"type":"string","minLength":1}}}}}
  function artifactBrief(candidate, schema, revision = '', helper) {
    if (typeof helper !== 'string' || !helper) throw new Error('artifactBrief requires the artifactcontract.py helper path')
    const suffix = CHECKPOINT_SCHEMA['x-progressSuffix']
    const operations = CHECKPOINT_SCHEMA['x-operations']
    if (typeof suffix !== 'string' || !suffix || !Array.isArray(operations) || !operations.length) throw new Error('artifactBrief: the checkpoint contract was not inlined from checkpoint.schema.json')
    const progress = `${candidate}${suffix}`
    const binding = ['--candidate', candidate, '--schema-json', canonicalJson(schema), '--revision', revision, '--progress-file', progress]
    const command = operation => ['python3', helper, operation, ...binding].map(quote).join(' ')
    return `\n\nARTIFACT CONTRACT DATA:
Candidate: ${candidate}
Progress: ${progress}
Input revision: ${revision}
${operations.map(operation => `Command ${operation}: ${command(operation)}`).join('\n')}`
  }
  async function acceptArtifact(dispatch, { label, phase, runner, candidate, file, schema, relayFile, returned = null, revision = '', keys = [], counts = [], projection = '', probe = false, recordArgv = [], researchAgent = '', researchRepo = '' }) {
    const args = ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), '--candidate', candidate, '--final', file, '--schema-json', canonicalJson(schema), ...(revision ? ['--revision', revision] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(counts.length ? ['--counts', counts.join(',')] : []), ...(projection ? ['--projection', projection] : []), ...(probe ? ['--probe'] : []), ...(probe && researchAgent && researchRepo ? ['--research-agent', researchAgent, '--research-repo', researchRepo] : []), ...(!returned ? ['--recover'] : [])]
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
  return { ARTIFACT_SCHEMA, artifactBrief, acceptArtifact, authorArtifact, artifactRevision, documentReceipt, canonicalJson, sha256Ascii, sha256Json, quote, shellWords, exec, depscore, run, checkFile, ensureJson, inline, exceptionOf, unflatten, parse, SCHEMA }
})()
// ===== SHARED BLOCK relay — END =====
// ===== SHARED BLOCK step-journal — BEGIN (canonical: scripts/shared-blocks/step-journal.js; filled from skills/pipeline-contracts/schemas/{step-journal.schema,pipeline-steps}.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// ── STEP JOURNAL: the steps of the bead this workflow works on, and the changes it reports ──
//
// A build or deploy workflow runs the steps the bead's step journal lists. It reads the journal
// once, at its start, through the checked relay (bin/atw-step-journal read), keeps a copy in
// memory, and begins at the first step that is not done. It cannot write a file, so it reports
// each change (step started, step done with its artifacts and the steps its result adds, step
// failed with its cause, child steps planned) as one log line the driver applies to the journal
// file with orchestrator/core/journal_lines.py. The copy here changes exactly as the file does:
// it follows step_journal.next_step, start_step and journal_changes.apply_completion.
//
// The line format and the artifact that hands a planned step its parameters are defined in
// skills/pipeline-contracts/schemas/step-journal.schema.json; the step kinds, what each records
// and adds, and the up-front plans in skills/pipeline-contracts/schemas/pipeline-steps.json. Both
// are inlined below by scripts/shared-blocks.mjs. Never restate any part of them in a workflow.
const stepJournal = (() => {
  const WIRE = {"changePrefix":"STEP-JOURNAL ","changePartPrefix":"STEP-JOURNAL-PART ","changeChunk":4000,"plannedForPrefix":"for "}
  const PIPELINES = ({"$schema":"./pipeline-steps.schema.json","pipelines":{"build":{"plan":["build:workspace","build:regression-assess","build:regression-review","build:regression-validate","build:baseline","build:select-implementers","build:reuse-audit","build:refactor-snapshot","build:refactor","build:refactor-check","build:docs-audit","build:final-suite","build:regression-map","build:regression-map-review","build:regression-verify","build:commit"],"inner":{},"kinds":{"build:workspace":{"description":"Establish the Story's worktree and branch","purpose":"Every step that reads or changes the Task's code works in one tree on the Story's branch","runBy":"task-to-deploy","reads":[],"records":[{"name":"worktree","kind":"directory","holds":"the Story's worktree"},{"name":"branch","kind":"value","holds":"the branch checked out in the worktree, a string"},{"name":"defaultBranch","kind":"value","holds":"the repository's default branch, a string or null"}],"adds":[{"kinds":["build:design-source"],"when":"the Task's surfaces include web-ui and its design source is bundle or cds"},{"kinds":["build:infra-intent"],"when":"the Task's type or a label is in the infrastructure vocabulary"}]},"build:design-source":{"description":"Select the design source the Task's web UI is built from","purpose":"A cds bundle the owner supplied for the Task's artifact is the design the build uses and is audited against","runBy":"task-to-deploy","reads":[],"records":[{"name":"design","kind":"value","holds":"{ designSource, bundle, buildSpecs }: the design source used, the bundle directory or null, and the build spec paths"}],"adds":[]},"build:infra-intent":{"description":"Author the provisioning intent of the infrastructure Task","purpose":"The tests and the code of an infrastructure Task are written to concrete resources, stacks and cross-stack references","runBy":"task-to-deploy","reads":["worktree"],"records":[{"name":"provisioning","kind":"value","holds":"{ provisioningIntent, affectedStacks }"}],"adds":[]},"build:regression-assess":{"description":"Map the Task's change to the current and earlier requirements it can affect","purpose":"Earlier requirements stay covered: the tests are written and run against the cumulative scope, not only this Task","runBy":"task-to-deploy","reads":["worktree","design","provisioning"],"records":[{"name":"regressionPrevious","kind":"file","holds":"the requirements and mappings recorded before this Task"},{"name":"regressionPlan","kind":"file","holds":"the impact scope the regression-impact-assessor wrote"}],"adds":[]},"build:regression-review":{"description":"Review the regression scope against the requirement sources","purpose":"The scope is approved by a reviewer that did not write it","runBy":"task-to-deploy","reads":["worktree","regressionPrevious","regressionPlan"],"records":[{"name":"regressionPlanReview","kind":"file","holds":"the regression-coverage-reviewer's review of the scope"}],"adds":[]},"build:regression-validate":{"description":"Validate the reviewed regression scope","purpose":"The scope is complete and approved before any test is written, and its requirement sources are bound","runBy":"task-to-deploy","reads":["worktree","regressionPlan","regressionPlanReview"],"records":[{"name":"regressionScope","kind":"value","holds":"{ requiredKinds }: the test layers the scope requires"}],"adds":[]},"build:baseline":{"description":"Resolve the repository's suite command and run the suite before any change","purpose":"The command the build is judged by is the one the repository declares, and the tests failing before the Task are known","runBy":"task-to-deploy","reads":["worktree","regressionScope"],"records":[{"name":"suiteCommand","kind":"value","holds":"the command that runs the whole suite, a string"},{"name":"baseline","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile }: the suite run before any change"}],"adds":[{"kinds":["build:red-write","build:red-check"],"when":"always: one build:red-write per test agent the contract's surfaces call for, then the run that judges them"}]},"build:red-write":{"description":"Write failing tests with {testAgent}","purpose":"The Task's acceptance criteria are encoded as tests that fail before the code exists","runBy":"task-to-deploy","params":["testAgent","testAgents","feedback"],"reads":["worktree","suiteCommand","regressionPlan","testFiles","design","provisioning"],"records":[{"name":"testFiles","kind":"value","holds":"the test files the agent created or changed, a list of paths"},{"name":"redConfirmed","kind":"value","holds":"whether the agent saw its tests fail as intended, a boolean"}],"adds":[]},"build:red-check":{"description":"Run the suite and judge whether the new tests fail cleanly","purpose":"Red holds only when a new test fails, no test file fails to load and no other test regressed","runBy":"task-to-deploy","reads":["worktree","suiteCommand","baseline","testFiles","redRun"],"records":[{"name":"redRun","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile, reasons }: the suite run and why Red does not hold, when it does not"},{"name":"testPrint","kind":"value","holds":"{ files, treeDigest }: the git blob hash of each test file and the digest of the work tree"}],"adds":[{"kinds":["build:red-write","build:red-check"],"when":"Red does not hold: each test agent is given the suite result, and the suite is judged again"}],"limit":"It fails with red-unsatisfied when four checks have not shown Red, and with no-progress when the suite fails exactly as it did at the check before"},"build:select-implementers":{"description":"Select the implementers whose specialties cover the Task","purpose":"The code is written by the fewest agents whose specialties cover the change, in build order","runBy":"task-to-deploy","reads":["worktree","suiteCommand","baseline","redRun","testFiles","design","provisioning"],"records":[{"name":"implementers","kind":"value","holds":"the implementer agent names, in the order they work"},{"name":"sharedCapabilities","kind":"value","holds":"the shared capabilities the Task must use, read with atw-matrix uses --ids for the matrix ids the Task states: a list of { id, name, provides: [{ id, behaviour, consumersMust, interface }], providedBy: [{ name, kind, repository }] }"}],"adds":[{"kinds":["build:implement","build:green-check"],"when":"always: one build:implement per selected implementer, then the run that judges them"}]},"build:implement":{"description":"Write the code with {implementer}","purpose":"The failing tests pass with the minimum production change","runBy":"task-to-deploy","params":["implementer","implementers","brief"],"reads":["worktree","suiteCommand","baseline","redRun","greenRun","cdsAudit","reuseAudit","sharedCapabilities","testFiles","testDecisions","design","provisioning"],"records":[{"name":"changedFiles","kind":"value","holds":"the files the implementer changed, a list of paths"},{"name":"testIssues","kind":"value","holds":"the tests the implementer names as standing between the code and the contract, a list of { testId, kind, reason, contractRef }"},{"name":"upstreamMissing","kind":"value","holds":"what must exist outside the Task before the suite can pass, a list of { what, evidence }"}],"adds":[]},"build:green-check":{"description":"Run the suite and judge whether it is green","purpose":"The Task is built only when the repository's whole suite exits 0 and the implementers left the tests as they were written","runBy":"task-to-deploy","reads":["worktree","suiteCommand","testFiles","testPrint","implementers","testIssues","upstreamMissing","greenRun"],"records":[{"name":"greenRun","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile }: the suite run"},{"name":"testPrint","kind":"value","holds":"{ files, treeDigest }: the git blob hash of each test file and the digest of the work tree"}],"adds":[{"kinds":["build:test-ruling","build:green-check"],"when":"the suite is not green and an implementer named tests that stand between the code and the contract"},{"kinds":["build:implement","build:green-check"],"when":"the suite is not green and no named test awaits a ruling: each implementer is given the suite result"}],"limit":"It fails with green-modified-tests when an implementer changed a test file, with blocked-upstream when an implementer named something outside the Task, with no-progress when no file changed and the suite fails exactly as at the check before, and with green when eight checks since the implementers were selected have not shown a green suite"},"build:test-ruling":{"description":"Rule on the tests the implementers named, with tdd-unit-test-generator","purpose":"A test that contradicts the contract is changed by the agent that owns the tests, never by an implementer","runBy":"task-to-deploy","params":["issues"],"reads":["worktree","suiteCommand","greenRun","testFiles","regressionPlan"],"records":[{"name":"testDecisions","kind":"value","holds":"one ruling per named test, a list of { testId, action, reason }"},{"name":"testFiles","kind":"value","holds":"the test files the agent changed, a list of paths"}],"adds":[]},"build:reuse-audit":{"description":"Check the changed files against the shared capabilities the Task must use","purpose":"A behaviour a shared library, layer, chassis or service provides is used from it and written nowhere in this repository","runBy":"task-to-deploy","reads":["worktree","implementers","reuseAudit"],"records":[{"name":"reuseAudit","kind":"value","holds":"{ clean, violations, judgment, unchecked }: whether the audit found no violation; each violation as text, those atw-matrix check-reuse found and each definition the shared-capability-reviewer ruled a duplicate; each definition the reviewer ruled on with its ruling and reason; and the relied-on behaviours that have no use signal"}],"adds":[{"kinds":["build:implement","build:green-check","build:reuse-audit"],"when":"the first audit finds violations: each implementer is given them, the suite is judged, and the audit runs again"}],"limit":"It fails with reuse-violation when violations remain at the audit that follows the correction, and with reuse-audit when atw-matrix check-reuse does not rule or the shared-capability-reviewer leaves a definition unruled"},"build:refactor-snapshot":{"description":"Record the work tree as it is before the refactor","purpose":"A refactor that is repeated or undone goes back to the tree the green suite ran on, not to a tree an unfinished refactor changed","runBy":"task-to-deploy","reads":["worktree"],"records":[{"name":"refactorSnapshot","kind":"value","holds":"the git tree id of the work tree before the refactor, a string"}],"adds":[]},"build:refactor":{"description":"Refactor the code the implementers changed","purpose":"The change is left clear and free of duplication without changing behavior","runBy":"task-to-deploy","reads":["worktree","suiteCommand","changedFiles","refactorSnapshot"],"records":[{"name":"refactorChangedFiles","kind":"value","holds":"the files the refactor changed, read from git against the snapshot"},{"name":"refactorReverted","kind":"value","holds":"whether the refactor gave up and the tree was put back at the snapshot, a boolean"}],"adds":[]},"build:refactor-check":{"description":"Run the suite after the refactor","purpose":"A refactor that turns the suite red is undone","runBy":"task-to-deploy","reads":["worktree","suiteCommand","refactorSnapshot","refactorRestored","design"],"records":[{"name":"refactorRun","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile }: the suite run"}],"adds":[{"kinds":["build:refactor-restore","build:refactor-check"],"when":"the suite is red after the refactor and the tree has not been restored"},{"kinds":["build:cds-audit"],"when":"the suite is green and the Task's web UI has design source bundle or cds"}],"limit":"It fails when the suite is still red after the tree was restored to the snapshot"},"build:refactor-restore":{"description":"Restore the work tree to the snapshot taken before the refactor","purpose":"The suite went red after the refactor","runBy":"task-to-deploy","reads":["worktree","refactorSnapshot"],"records":[{"name":"refactorRestored","kind":"value","holds":"{ restored, evidence }"}],"adds":[]},"build:cds-audit":{"description":"Audit the changed web UI against its design source","purpose":"The UI styles nothing outside the design system the Task was built from","runBy":"task-to-deploy","reads":["worktree","design","implementers","cdsAudit"],"records":[{"name":"cdsAudit","kind":"value","holds":"{ verdict, findings, scriptVersion, violations, gaps }: the audit verdict, the count of violations and gaps, and each as text"}],"adds":[{"kinds":["build:implement","build:green-check","build:cds-audit"],"when":"the first audit finds violations: each implementer is given them, the suite is judged, and the audit runs again"}],"limit":"It fails with cds-audit when violations remain at the audit that follows the correction, and with blocked-upstream when the design system lacks something the UI needs"},"build:docs-audit":{"description":"Audit which documents the change leaves stale","purpose":"Documentation is brought up to date in the same commit as the code","runBy":"task-to-deploy","reads":["worktree","changedFiles","refactorChangedFiles"],"records":[{"name":"staleDocs","kind":"value","holds":"the stale documents, a list of paths"},{"name":"docAssignments","kind":"value","holds":"the stale documents by the documentation agent that owns their kind, a list of { agent, docs }"}],"adds":[{"kinds":["build:docs-write"],"when":"documents are stale: one build:docs-write per documentation agent assigned"}]},"build:docs-write":{"description":"Update the stale documents with {docAgent}; the documentation-accuracy-reviewer checks them","purpose":"The audit named documents the change leaves stale","runBy":"task-to-deploy","params":["docAgent","docs"],"reads":["worktree","changedFiles"],"records":[{"name":"updatedDocs","kind":"value","holds":"the documents the agent updated, a list of paths"}],"adds":[],"together":true},"build:final-suite":{"description":"Run the suite a final time","purpose":"Nothing is committed unless the whole suite exits 0 on the tree as it will be committed","runBy":"task-to-deploy","reads":["worktree","suiteCommand"],"records":[{"name":"finalRun","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile }: the suite run"}],"adds":[]},"build:regression-map":{"description":"Map each requirement in scope to the tests and commands that prove it","purpose":"Every required test layer of the approved scope names concrete tests and a command that runs them","runBy":"task-to-deploy","reads":["worktree","regressionPlan","regressionPrevious"],"records":[{"name":"regressionMapped","kind":"file","holds":"the final mapping the regression-impact-assessor wrote"}],"adds":[]},"build:regression-map-review":{"description":"Review the regression mapping against the tests as written","purpose":"The mapping is approved by a reviewer that did not write it","runBy":"task-to-deploy","reads":["worktree","regressionMapped","regressionPrevious"],"records":[{"name":"regressionMappedReview","kind":"file","holds":"the regression-coverage-reviewer's review of the mapping"}],"adds":[]},"build:regression-verify":{"description":"Run the mapped regression tests and record their evidence","purpose":"The commit carries fresh per-test evidence for every requirement the change can affect","runBy":"task-to-deploy","reads":["worktree","regressionPlan","regressionMapped","regressionMappedReview"],"records":[{"name":"regressionEvidence","kind":"file","holds":"the verification result and the evidence of each mapped run"}],"adds":[]},"build:commit":{"description":"Commit the Task to the Story's branch","purpose":"The built Task lands on the branch its Story deploys from","runBy":"task-to-deploy","reads":["worktree","branch","defaultBranch","suiteCommand","finalRun"],"records":[{"name":"commit","kind":"value","holds":"the head of the Story's branch after the commit, a string"}],"adds":[]}}},"deploy":{"plan":["deploy:mechanism","deploy:workspace","deploy:commits-ahead","deploy:close"],"inner":{"deploy:fix":["deploy:fix-author","deploy:fix-verify","deploy:fix-commit"],"deploy:built-version":["deploy:built-snapshot","deploy:built-compare"]},"kinds":{"deploy:mechanism":{"description":"Ask what the Story's repository publishes and deploys","purpose":"A repository publishes a package, deploys with CDK, both or neither, and the deploy runs only what applies","runBy":"driver","reads":[],"records":[{"name":"mechanism","kind":"value","holds":"{ repository, publishes, publishCommand, deploys, reason }"}],"adds":[]},"deploy:workspace":{"description":"Open the Story's worktree","purpose":"The deploy runs from the tree that holds the Story's built Tasks","runBy":"driver","reads":["mechanism"],"records":[{"name":"worktree","kind":"directory","holds":"the Story's worktree"},{"name":"branch","kind":"value","holds":"the Story's branch, a string"}],"adds":[{"kinds":["deploy:publish"],"when":"the repository publishes a package"},{"kinds":["deploy:synth"],"when":"the repository deploys with CDK and publishes no package"}]},"deploy:publish":{"description":"Publish the repository's package","purpose":"The repository publishes a package other repositories install","runBy":"driver","reads":["mechanism","worktree"],"records":[{"name":"publishedHead","kind":"value","holds":"the commit the package was published from, a string"},{"name":"deployFailure","kind":"value","holds":"{ step, output, stacks }, recorded only when the publish failed"}],"adds":[{"kinds":["deploy:synth"],"when":"the publish succeeded and the repository deploys with CDK"},{"kinds":["deploy:fix","deploy:publish"],"when":"the publish failed"}],"limit":"It fails when three fixes of this Story's deploy have already run"},"deploy:synth":{"description":"Synthesize the CDK app","purpose":"The cloud assembly names the stacks and the SSM parameters the deploy needs","runBy":"driver","reads":["worktree"],"records":[{"name":"assembly","kind":"directory","holds":"the CDK cloud assembly"},{"name":"deployFailure","kind":"value","holds":"{ step, output, stacks }, recorded only when the synth failed"}],"adds":[{"kinds":["deploy:ssm-check"],"when":"the synth succeeded"},{"kinds":["deploy:fix","deploy:publish","deploy:synth"],"when":"the synth failed: after the fix the package is published again when the repository publishes one, then the app is synthesized again"}],"limit":"It fails when three fixes of this Story's deploy have already run"},"deploy:ssm-check":{"description":"Check that the SSM parameters the stacks read exist","purpose":"A stack that reads a parameter another Story's deploy writes cannot deploy before that parameter exists","runBy":"driver","reads":["assembly"],"records":[{"name":"ssmParameters","kind":"value","holds":"the parameter names the stacks read, all present, a list of strings"}],"adds":[{"kinds":["deploy:deploy"],"when":"every parameter exists"}],"waits":"a parameter the stacks read does not exist yet"},"deploy:deploy":{"description":"Deploy the stacks to AWS dev","purpose":"The Story's Tasks are built and its stacks can be deployed","runBy":"driver","reads":["worktree","assembly"],"records":[{"name":"deployOutput","kind":"value","holds":"{ exitCode, tail }: the exit status of the deploy and the last part of its output"}],"adds":[{"kinds":["deploy:verify"],"when":"always"}]},"deploy:verify":{"description":"Verify that every stack reached a completed status and the worktree is clean","purpose":"The deploy counts only when CloudFormation reports every stack created or updated","runBy":"driver","reads":["worktree","assembly","deployOutput"],"records":[{"name":"stacks","kind":"value","holds":"the status of each stack, a list of { name, status, reason }"},{"name":"deployFailure","kind":"value","holds":"{ step, output, stacks }, recorded only when the deploy or its verification failed"}],"adds":[{"kinds":["deploy:fix","deploy:publish","deploy:synth"],"when":"the deploy or its verification failed: after the fix the package is published again when the repository publishes one, then the app is synthesized again"}],"limit":"It fails when three fixes of this Story's deploy have already run"},"deploy:fix":{"description":"Fix the failed deploy on the Story's branch","purpose":"A publish, synth, deploy or verification of the Story failed","runBy":"driver","params":["failure"],"reads":["worktree","branch","deployFailure"],"records":[{"name":"fix","kind":"value","holds":"{ cause, changedFiles, testsPassed, commit }: what the story-deploy-fix workflow returned"}],"adds":[]},"deploy:fix-author":{"description":"Diagnose the failure and fix it in the worktree, with deploy-failure-fixer","purpose":"The cause of the failed deploy is found in its output and corrected in the Story's code","runBy":"story-deploy-fix","within":"deploy:fix","reads":[],"records":[{"name":"fixCause","kind":"value","holds":"the cause the agent found, a string"},{"name":"fixTestCommand","kind":"value","holds":"the command that runs the synth assertion tests, a string that may be empty"}],"adds":[]},"deploy:fix-verify":{"description":"Read what the fix changed from git and run the synth assertion tests","purpose":"What the fix changed and whether its tests pass are measured, not taken from the agent's report","runBy":"story-deploy-fix","within":"deploy:fix","reads":["fixCause","fixTestCommand"],"records":[{"name":"fixChangedFiles","kind":"value","holds":"the files the fix changed, read from git status, a list of paths"},{"name":"fixTestsPassed","kind":"value","holds":"whether the synth assertion tests exited 0, a boolean"}],"adds":[],"limit":"It fails with no-change when the fix changed no file"},"deploy:fix-commit":{"description":"Commit the fix to the Story's branch","purpose":"The redeploy runs from a committed tree","runBy":"story-deploy-fix","within":"deploy:fix","reads":["fixCause"],"records":[{"name":"fixCommit","kind":"value","holds":"the head of the Story's branch after the commit, a string"}],"adds":[]},"deploy:commits-ahead":{"description":"Count the commits the Story's branch has that the default branch lacks","purpose":"A Story whose branch holds no commit has nothing to compare, review or merge","runBy":"driver","reads":["worktree","stacks"],"records":[{"name":"commitsAhead","kind":"value","holds":"the number of commits ahead of the default branch, an integer"}],"adds":[{"kinds":["deploy:built-version","deploy:pull-request","deploy:mark-verified","deploy:merge-wait"],"when":"the branch holds commits"}]},"deploy:built-version":{"description":"Record what the Story built against the effective architecture","purpose":"The effective architecture describes what is deployed before the Story's pull request opens","runBy":"driver","reads":["worktree","branch"],"records":[{"name":"built","kind":"value","holds":"{ stage, differences, builtFiles }: what the built-version workflow returned, with counts in place of lists; nothing is recorded in the matrix for it"}],"adds":[]},"deploy:built-snapshot":{"description":"Fingerprint the architecture and keep a copy of section 2","purpose":"What each agent writes in the architecture is measured, and the owner's constraints are put back if they change","runBy":"built-version","within":"deploy:built-version","reads":[],"records":[{"name":"constraintsBefore","kind":"value","holds":"{ exists, digest, gitStatus, kept }: the fingerprint of section 2 and where its copy is kept"},{"name":"treeStart","kind":"file","holds":"the fingerprint of every architecture file before the comparison"}],"adds":[]},"deploy:built-compare":{"description":"Compare the code on the Story's branch with the effective architecture","purpose":"Each difference between what was built and what the architecture shows is recorded as a built view","runBy":"built-version","within":"deploy:built-version","reads":["constraintsBefore","treeStart"],"records":[{"name":"differences","kind":"value","holds":"the differences found, a list of { element, itemId, effectiveViews, built, citations, file }"},{"name":"builtFiles","kind":"value","holds":"the built views written, a list of absolute paths"},{"name":"treeCompared","kind":"file","holds":"the fingerprint of every architecture file after the comparison"}],"adds":[{"kinds":["deploy:built-correct","deploy:built-review"],"when":"the comparison recorded differences"}]},"deploy:built-correct":{"description":"Correct the effective architecture to match what was built, with architecture-maintainer","purpose":"The effective architecture differs from what the Story built, or a review found the correction wanting","runBy":"built-version","within":"deploy:built-version","params":["findings"],"reads":["constraintsBefore","builtFiles","treeCompared","treeLast","architectureUpdate"],"records":[{"name":"architectureUpdate","kind":"value","holds":"{ changedFiles, createdFiles, deletedFiles, matched, constraintIssues, contradictions, summary }: every pass together, with the files measured from the tree"},{"name":"changedSinceLast","kind":"value","holds":"the files this pass changed since the pass before, a list of paths"},{"name":"treeLast","kind":"file","holds":"the fingerprint of every architecture file after this pass"}],"adds":[],"limit":"It fails when it wrote in section 2 or outside the effective architecture, and when a pass that answers findings changed no file"},"deploy:built-review":{"description":"Review the correction of the effective architecture, with architecture-conformance-reviewer","purpose":"The correction is checked by a reviewer that did not write it","runBy":"built-version","within":"deploy:built-version","reads":["constraintsBefore","builtFiles","architectureUpdate","changedSinceLast","conformance"],"records":[{"name":"conformance","kind":"value","holds":"{ conforms, findings, reviewedFiles, matchedBuiltViews }"}],"adds":[{"kinds":["deploy:built-correct","deploy:built-review"],"when":"the review has findings"},{"kinds":["deploy:built-approve","deploy:built-remove"],"when":"the correction conforms"}],"limit":"It fails when the correction does not conform after two corrections that answered findings"},"deploy:built-approve":{"description":"Set the corrected architecture files to effective","purpose":"A reviewed correction becomes the effective architecture","runBy":"built-version","within":"deploy:built-version","reads":["constraintsBefore","architectureUpdate","conformance"],"records":[{"name":"approval","kind":"value","holds":"{ promoted, unchanged }: how many files were set to effective and how many already were"}],"adds":[]},"deploy:built-remove":{"description":"Remove the built views the effective architecture now matches","purpose":"A built view exists only while the effective architecture differs from what was built","runBy":"built-version","within":"deploy:built-version","reads":["builtFiles","architectureUpdate","conformance"],"records":[{"name":"removedBuiltViews","kind":"value","holds":"the built views removed, a list of absolute paths"}],"adds":[],"limit":"It fails when a built view remains that the effective architecture does not match"},"deploy:pull-request":{"description":"Push the Story's branch and open its pull request","purpose":"The Story's deploy is verified and its branch holds commits","runBy":"driver","reads":["worktree","branch","stacks","publishedHead"],"records":[{"name":"pullRequest","kind":"value","holds":"the pull request URL, a string"}],"adds":[]},"deploy:mark-verified":{"description":"Set what the Story built verified in the matrix once its CI checks pass","purpose":"The Story's test has passed when its deploy to AWS dev was verified working and every check on its pull request's head commit passed; what it built is then built and tested, before and apart from the merge, which decides nothing about verified","runBy":"driver","reads":["pullRequest"],"records":[{"name":"matrixVerified","kind":"value","holds":"{ commit, entries, unmatched }: the head commit whose checks passed, the ids that carry the flag and the ids that matched no entry; commit is null and nothing is marked when the pull request merged with a check that did not pass"}],"adds":[],"waits":"a check on the pull request's head commit has not finished, or failed while the pull request is open"},"deploy:merge-wait":{"description":"Wait for the Story's pull request to merge","purpose":"The Story closes only when its code is on the default branch","runBy":"driver","reads":["pullRequest"],"records":[{"name":"pullRequestState","kind":"value","holds":"the state GitHub reports for the pull request, the string MERGED"}],"adds":[],"waits":"the pull request is open and not merged"},"deploy:close":{"description":"Close the Story and remove its worktree and local branch","purpose":"A Story with nothing left to deploy or merge is done","runBy":"driver","reads":["worktree","branch"],"records":[{"name":"closed","kind":"value","holds":"true"}],"adds":[]}}}}}).pipelines || {}
  if (!WIRE.changePrefix || !WIRE.changePartPrefix || !WIRE.changeChunk || !WIRE.plannedForPrefix || !PIPELINES.build || !PIPELINES.deploy) {
    throw new Error('shared block step-journal: the step journal contract was not inlined (run node scripts/shared-blocks.mjs --write)')
  }
  const STEP_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  const FAILURE_EVIDENCE_CHARS = 4000

  /** An artifact that is a file a step produced. */
  const file = (name, path) => ({ name, kind: 'file', path: String(path) })
  /** An artifact that is a directory a step produced. */
  const directory = (name, path) => ({ name, kind: 'directory', path: String(path) })
  /** An artifact that is a value a step produced; an undefined value is recorded as null. */
  const value = (name, held) => ({ name, kind: 'value', value: held === undefined ? null : held })

  /** Every step of `steps` in walk order: each step before its child steps, siblings in order. */
  const walk = (steps, out = []) => {
    for (const step of steps) {
      out.push(step)
      walk(step.steps, out)
    }
    return out
  }

  /** The copy of one journal step: `key` is its id, or the ref of a step this run added. */
  const copyStep = (raw, params) => {
    const id = String(raw.id || '')
    return {
      key: id,
      id,
      kind: String(raw.script || ''),
      description: String(raw.description || ''),
      purpose: String(raw.purpose || ''),
      status: String(raw.status || 'planned'),
      artifacts: Array.isArray(raw.artifacts) ? raw.artifacts.map((held) => ({ ...held })) : [],
      params: params.get(id) || {},
      steps: (Array.isArray(raw.steps) ? raw.steps : []).map((child) => copyStep(child, params)),
    }
  }

  /** `text` with each {name} replaced by the text parameter of that name. */
  const filled = (text, params, kind) =>
    String(text).replace(/\{([A-Za-z][A-Za-z0-9]*)\}/g, (_match, name) => {
      const held = params ? params[name] : undefined
      if (typeof held !== 'string' || !held) throw new Error(`a step of kind ${kind} needs the text parameter ${name} for its description`)
      return held
    })

  /**
   * Opens the journal a workflow was handed. `journal` is the document atw-step-journal read
   * printed, `run` the name the driver gave this run, `runner` the name of this workflow script as
   * pipeline-steps.json names it, and `under` the id of the step whose child steps this workflow
   * runs (absent for a workflow that runs the bead's outermost steps).
   */
  function open({ journal, run, runner, under = null }) {
    if (!journal || typeof journal !== 'object' || !Array.isArray(journal.steps)) throw new Error('stepJournal.open: no journal was read')
    if (typeof run !== 'string' || !run) throw new Error('stepJournal.open: no run name was supplied')
    const pipeline = PIPELINES[journal.pipeline]
    if (!pipeline) throw new Error(`stepJournal.open: the journal lists ${journal.pipeline} steps, which pipeline-steps.json does not define`)
    const params = new Map()
    for (const raw of walk(journal.steps)) {
      for (const held of Array.isArray(raw.artifacts) ? raw.artifacts : []) {
        const name = String(held.name || '')
        const planned = name.startsWith(WIRE.plannedForPrefix) ? name.slice(WIRE.plannedForPrefix.length) : ''
        if (held.kind === 'value' && STEP_ID.test(planned) && held.value && typeof held.value === 'object') params.set(planned, held.value)
      }
    }
    const roots = journal.steps.map((raw) => copyStep(raw, params))
    const parent = under ? walk(roots).find((step) => step.id === under) || null : null
    if (under && !parent) throw new Error(`stepJournal.open: the journal of ${journal.bead} holds no step ${under}`)
    let changes = 0

    /** Writes one change on the log, as one line or as part lines when it is longer than the chunk. */
    function report(change) {
      changes += 1
      const body = JSON.stringify({ run, n: changes, ...change })
      if (body.length <= WIRE.changeChunk) {
        log(`${WIRE.changePrefix}${body}`)
        return
      }
      const parts = []
      for (let at = 0; at < body.length; ) {
        let end = Math.min(at + WIRE.changeChunk, body.length)
        const last = body.charCodeAt(end - 1)
        if (end < body.length && last >= 0xd800 && last <= 0xdbff) end -= 1
        parts.push(body.slice(at, end))
        at = end
      }
      parts.forEach((part, index) => log(`${WIRE.changePartPrefix}${changes} ${index + 1}/${parts.length} ${part}`))
    }

    const everyStep = () => walk(roots)
    const scope = () => (parent ? parent.steps : roots)
    const kindOf = (key) => {
      const kind = pipeline.kinds[key]
      if (!kind) throw new Error(`pipeline-steps.json defines no ${journal.pipeline} step kind ${key}`)
      return kind
    }
    /** The steps of this workflow's scope before `step` in walk order; every step of the scope when `step` is not one of them. */
    const before = (step) => {
      const all = walk(scope())
      const at = all.indexOf(step)
      return at < 0 ? all : all.slice(0, at)
    }
    /** The step that directly contains `step`, or null for an outermost step. */
    const containerOf = (step) => everyStep().find((candidate) => candidate.steps.includes(step)) || null
    const siblingsOf = (step) => {
      const container = containerOf(step)
      return container ? container.steps : roots
    }
    const heldBy = (step, name) => step.artifacts.filter((held) => held.name === name).map((held) => (held.kind === 'value' ? held.value : held.path))

    /** What a planned step is in the copy, and the plan the driver adds to the journal file. */
    const planned = (adder, entry, ordinal) => {
      const kind = kindOf(entry.kind)
      const handed = entry.params && typeof entry.params === 'object' ? entry.params : null
      const ref = `${adder.key}.${ordinal}`
      const description = filled(kind.description, handed, entry.kind)
      const purpose = typeof entry.purpose === 'string' && entry.purpose.trim() ? entry.purpose.trim() : kind.purpose
      return {
        step: { key: ref, id: '', kind: entry.kind, description, purpose, status: 'planned', artifacts: [], params: handed || {}, steps: [] },
        wire: { plan: { ref, description, purpose, script: entry.kind }, ...(handed ? { params: handed } : {}) },
      }
    }

    return {
      bead: String(journal.bead || ''),
      pipeline: String(journal.pipeline || ''),
      kinds: pipeline.kinds,
      /** The kinds of the child steps pipeline-steps.json plans under a step of `kind` when it first runs. */
      innerPlan: (kind) => (pipeline.inner[kind] || []).map((key) => ({ kind: key })),
      /** The step this workflow runs child steps under, or null. */
      parent: () => parent,
      /** Every step of the journal in walk order. */
      steps: everyStep,
      /** The step this workflow does next: the first step of its scope that has no child steps and is not done. */
      next: () => walk(scope()).find((step) => !step.steps.length && step.status !== 'done') || null,
      /** `step` and the planned steps of its kind that follow it directly, when the kind's steps run together. */
      together(step) {
        if (kindOf(step.kind).together !== true) return [step]
        const siblings = siblingsOf(step)
        const group = [step]
        for (const sibling of siblings.slice(siblings.indexOf(step) + 1)) {
          if (sibling.kind !== step.kind || sibling.steps.length || sibling.status === 'done') break
          group.push(sibling)
        }
        return group
      },
      // The three lookups below read the steps of this workflow's scope: the bead's steps, or the child
      // steps of the step it was handed. A null `step` reads every step of the scope.
      /** The newest artifact named `name` a done step before `step` holds: its value or its path; `fallback` when none holds one. */
      latest(name, step, fallback = null) {
        const earlier = before(step).filter((candidate) => candidate.status === 'done')
        for (let at = earlier.length - 1; at >= 0; at -= 1) {
          const found = heldBy(earlier[at], name)
          if (found.length) return found[found.length - 1]
        }
        return fallback
      },
      /** Every artifact named `name` the done steps before `step` hold, oldest first; with `since`, only those of steps after it. */
      every(name, step, since = null) {
        const earlier = before(step)
        const from = since ? earlier.indexOf(since) + 1 : 0
        return earlier.slice(from).filter((candidate) => candidate.status === 'done').flatMap((candidate) => heldBy(candidate, name))
      },
      /** The done steps before `step` whose kind is one of `kinds`, oldest first; with `since`, only those after it. */
      earlier(kinds, step, since = null) {
        const all = before(step)
        const from = since ? all.indexOf(since) + 1 : 0
        return all.slice(from).filter((candidate) => candidate.status === 'done' && kinds.includes(candidate.kind))
      },
      /** A directory name for the files of `step`, unique in the journal. */
      folder: (step) => step.key.replace(/^([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, '$1').replace(/[^A-Za-z0-9._-]+/g, '-'),
      /** Marks a step running: it starts from its beginning, so the artifacts of an unfinished run of it are dropped. */
      start(step) {
        step.status = 'running'
        step.artifacts = []
        report({ op: 'start', step: step.key })
      },
      /** Records a step's artifacts, adds the steps its result calls for right after it, and marks it done. */
      done(step, artifacts = [], add = []) {
        const added = add.map((entry, index) => planned(step, entry, index + 1))
        const siblings = siblingsOf(step)
        siblings.splice(siblings.indexOf(step) + 1, 0, ...added.map((entry) => entry.step))
        step.artifacts = [...artifacts]
        step.status = 'done'
        report({ op: 'done', step: step.key, ...(artifacts.length ? { artifacts } : {}), ...(added.length ? { add: added.map((entry) => entry.wire) } : {}) })
        return added.map((entry) => entry.step)
      },
      /** Marks a step failed with its cause: { stage, message, evidence? }. */
      fail(step, cause) {
        const stage = String((cause && cause.stage) || step.kind)
        const message = String((cause && cause.message) || 'the step failed').slice(0, FAILURE_EVIDENCE_CHARS)
        const evidence = cause && cause.evidence ? String(cause.evidence).slice(0, FAILURE_EVIDENCE_CHARS) : ''
        step.status = 'failed'
        report({ op: 'fail', step: step.key, failure: JSON.stringify({ stage, message, ...(evidence ? { evidence } : {}) }) })
      },
      /** Plans child steps under the running step this workflow was handed, in the order they run. */
      planUnder(add) {
        if (!parent) throw new Error('stepJournal: this workflow was handed no step to plan child steps under')
        const added = add.map((entry, index) => planned(parent, entry, parent.steps.length + index + 1))
        parent.steps.push(...added.map((entry) => entry.step))
        report({ op: 'add', step: parent.key, add: added.map((entry) => entry.wire) })
        return added.map((entry) => entry.step)
      },
      /**
       * Runs the steps of this workflow's scope from the next one until none is left or one fails.
       * `table` maps a step kind to the function that runs a step of it: `async (step) => ({ artifacts, add })`
       * when the step is done (`add` lists { kind, params?, purpose? } for the steps its result calls for), or
       * `{ fail: { stage, message, evidence?, ...more } }` when it failed. `interrupted()` returns the
       * interruption of this run's dispatches, or null. Returns { ok: true }, or
       * { ok: false, step, fail } for the step that failed.
       */
      async run(table, interrupted = () => null) {
        const mine = Object.keys(pipeline.kinds).filter((key) => pipeline.kinds[key].runBy === runner && (pipeline.kinds[key].within || null) === (parent ? parent.kind : null))
        const missing = mine.filter((key) => typeof table[key] !== 'function')
        if (missing.length) throw new Error(`${runner} has no function for the step kinds ${missing.join(', ')}`)
        const attempt = async (step) => {
          let out = null
          try {
            const perform = table[step.kind]
            out = typeof perform === 'function' ? await perform(step) : { fail: { stage: step.kind, message: `${runner} runs no step of kind ${step.kind || '(none)'}` } }
          } catch (err) {
            out = { fail: { stage: step.kind, message: `the step threw: ${String((err && err.message) || err).slice(0, 400)}` } }
          }
          if (out && typeof out === 'object' && !out.fail) return out
          const stop = interrupted()
          if (stop) return { fail: { stage: stop.stage, message: stop.message, interrupted: true } }
          return out && typeof out === 'object' ? out : { fail: { stage: step.kind, message: 'the step returned nothing' } }
        }
        /** Runs one step and reports it done or failed as soon as its own work ends; returns its failure, or null. */
        const settle = async (step) => {
          const out = await attempt(step)
          if (out.fail) {
            this.fail(step, out.fail)
            return { ok: false, step, fail: out.fail }
          }
          this.done(step, Array.isArray(out.artifacts) ? out.artifacts : [], Array.isArray(out.add) ? out.add : [])
          return null
        }
        for (;;) {
          const first = this.next()
          if (!first) return { ok: true }
          const group = this.together(first)
          for (const step of group) this.start(step)
          const failures = group.length === 1 ? [await settle(group[0])] : await parallel(group.map((step) => () => settle(step).catch((thrown) => ({ thrown }))))
          const broken = failures.find((held) => held && held.thrown)
          if (broken) throw broken.thrown
          const failed = failures.find(Boolean)
          if (failed) return failed
        }
      },
    }
  }

  /**
   * Reads the journal file through the checked relay: one command, bin/atw-step-journal read.
   * Returns { journal } or { error, noResult }.
   */
  async function read(dispatch, { runner, pluginRoot, path, relayFile, phase }) {
    const result = await relayKit.run(dispatch, { label: 'journal:read', phase, runner, argv: [`${pluginRoot}/bin/atw-step-journal`, 'read', '--journal', path], file: relayFile })
    if (!result.ok) return { error: result.error, noResult: !!result.noResult }
    if (result.exitCode !== 0 || !result.json || !result.json.journal) return { error: `atw-step-journal read exited ${result.exitCode}; its output is in ${relayFile}` }
    return { journal: result.json.journal }
  }

  return { file, directory, value, open, read, pipelines: PIPELINES }
})()
// ===== SHARED BLOCK step-journal — END =====
// ===== SHARED BLOCK composite-phases — BEGIN (canonical: skills/pipeline-contracts/schemas/composites.json; edit there, then: python3 skills/pipeline-contracts/scripts/generate_composites.py and node scripts/shared-blocks.mjs --write) =====
// GENERATED by skills/pipeline-contracts/scripts/generate_composites.py from
// skills/pipeline-contracts/schemas/composites.json, the one definition of composite ids, their phases,
// phase titles and role sets. Never restate any part of it in a workflow: change composites.json and
// regenerate. check_composites_contract.py fails when this file is stale.
const COMPOSITE_CONTRACT = Object.freeze({"wire":{"phaseSentinel":"PHASE","progressPrefix":"\u25b8 "},"fallbackPhases":[{"id":"start","title":"Start"},{"id":"work","title":"Work"},{"id":"finish","title":"Finish"}],"composites":{"prd-to-spec":{"runner":"orchestrator","openingKind":"epic","sets":["orchestrated","elaboration"],"phases":[{"id":"epic-lifecycle","title":"Epic Lifecycle"},{"id":"prd","title":"PRD"},{"id":"epic","title":"Epic"},{"id":"architecture","title":"Architecture","event":true},{"id":"trd-authoring","title":"TRD Authoring","event":true},{"id":"repo-scoping","title":"Repo Scoping","event":true},{"id":"spec-authoring","title":"Spec Authoring","event":true},{"id":"task-decomposition","title":"Task Decomposition","event":true},{"id":"task-edges","title":"Task Edges","event":true},{"id":"finish","title":"Finish","event":true},{"id":"run-ledger","title":"Run Ledger"}]},"task-to-deploy":{"runner":"workflow","openingKind":"task","sets":["target-repo","code-build","repo-required","design-aware"],"phases":[{"id":"workspace","title":"Workspace"},{"id":"infra-intent","title":"Infra Intent"},{"id":"regression-scope","title":"Regression Scope"},{"id":"baseline","title":"Baseline"},{"id":"red","title":"Red"},{"id":"green","title":"Green"},{"id":"reuse-audit","title":"Reuse Audit"},{"id":"refactor","title":"Refactor"},{"id":"cds-audit","title":"CDS Audit"},{"id":"documentation","title":"Documentation"},{"id":"commit","title":"Commit"}]},"story-deploy":{"runner":"driver","sets":["story"],"phases":[{"id":"mechanism","title":"Mechanism"},{"id":"workspace","title":"Workspace"},{"id":"publish","title":"Publish"},{"id":"ssm-check","title":"SSM Check"},{"id":"deploy","title":"Deploy"},{"id":"verify","title":"Verify"},{"id":"fix","title":"Fix"},{"id":"built","title":"Built"},{"id":"pull-request","title":"Pull Request"},{"id":"mark-verified","title":"Mark Verified"},{"id":"merge-wait","title":"Merge Wait"},{"id":"close","title":"Close"}]},"story-deploy-fix":{"runner":"workflow","sets":["story"],"phases":[{"id":"fix","title":"Fix"},{"id":"commit","title":"Commit"}]},"deploy-mechanism":{"runner":"workflow","sets":["story"],"phases":[{"id":"ask","title":"Ask"}]},"built-version":{"runner":"workflow","sets":["story"],"phases":[{"id":"compare","title":"Compare"},{"id":"correct","title":"Correct"},{"id":"remove","title":"Remove"}]},"dependency-assessment":{"runner":"workflow","sets":[],"phases":[{"id":"assess","title":"Assess"},{"id":"score","title":"Score"}]},"probe":{"runner":"probe","sets":["attaching"],"phases":[]}},"retired":{"repair":{"sets":["attaching"]},"incident":{"sets":["attaching"]},"task-dependency-assessment":{"sets":["former-trigger"]},"wsjf-scoring":{"sets":["former-trigger"]}}})
const compositePhases = (composite) => {
  const spec = COMPOSITE_CONTRACT.composites[composite]
  if (spec && spec.phases.length) return spec.phases
  if (spec || COMPOSITE_CONTRACT.retired[composite]) return COMPOSITE_CONTRACT.fallbackPhases
  throw new Error(`unknown composite ${composite}`)
}
const compositePhaseTitle = (composite, phase) => {
  const found = compositePhases(composite).find(entry => entry.id === phase)
  if (!found) throw new Error(`composite ${composite} has no phase ${phase}`)
  return found.title
}
// ===== SHARED BLOCK composite-phases — END =====
// ===== SHARED BLOCK recon-contract — BEGIN (canonical: skills/artifact-handoff/schemas/recon.schema.json; edit there, then: python3 skills/artifact-handoff/scripts/gen_recon_contract.py --write and node scripts/shared-blocks.mjs --write) =====
// GENERATED by skills/artifact-handoff/scripts/gen_recon_contract.py from
// skills/artifact-handoff/schemas/recon.schema.json, the one definition of recon-<slug>.json and of the
// detailing session's reply. Never edit: change the schema, then run
// python3 skills/artifact-handoff/scripts/gen_recon_contract.py --write and node scripts/shared-blocks.mjs --write.
const RECON_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "recon.schema.json", "title": "Per-repository detailing", "description": "The detailing of one repository against the approved architecture delta, saved as recon-<slug>.json in the Epic's working directory. Every delta item of what the repository's Story builds gets one status with file:line evidence, its surface, the design source of each ui item, and the upstream dependency changes.", "x-fileTemplate": "recon-{slug}.json", "x-producerRequired": ["items", "dependencyChanges"], "$ref": "#/$defs/ReconDetailing", "$defs": {"ReconStatus": {"description": "How the code on main relates to the delta item.", "enum": ["add", "modify", "remove", "done", "planned-elsewhere"]}, "WorkStatus": {"description": "The statuses that make work.", "enum": ["add", "modify", "remove"]}, "IdleStatus": {"description": "The statuses that make no work.", "enum": ["done", "planned-elsewhere"]}, "Surface": {"description": "The surface the item lives on.", "enum": ["ui", "service", "infra", "data", "unknown"], "default": "unknown"}, "DesignSource": {"description": "Where a ui item's design comes from: bundle (a single-artifact cds bundle the owner supplied packages it), cds (it changes design and no bundle packages it, so it is designed with the CDS design system) or none (it changes no design).", "enum": ["bundle", "cds", "none"], "default": "cds"}, "ArtifactKind": {"description": "The kind of cds artifact, as a bundle.json names it.", "enum": ["page", "shell", "view"], "default": "page"}, "FromAbsent": {"description": "The `from` value of an add item.", "const": "absent"}, "ToRemoved": {"description": "The `to` value of a remove item.", "const": "removed"}, "ReconDetailing": {"description": "The saved detailing of one repository.", "type": "object", "additionalProperties": false, "required": ["items"], "properties": {"items": {"description": "One entry per delta item of what this repository's Story builds.", "type": "array", "items": {"$ref": "#/$defs/ReconItem"}}, "evidenceSummary": {"description": "A short summary of the evidence read.", "type": "string"}, "uiAuthority": {"description": "The design source of each ui item; empty values when the repository holds no UI.", "$ref": "#/$defs/UiAuthority"}, "dependencyChanges": {"description": "Whether an upstream contract, shared schema, event, library version or interface the delta assumes has changed in a way that invalidates it.", "$ref": "#/$defs/DependencyChanges"}}}, "ReconItem": {"description": "The detailing of one delta item the Story builds.", "type": "object", "additionalProperties": false, "required": ["id", "element", "status", "evidence", "surface"], "properties": {"id": {"description": "The id of the delta item the Story builds.", "type": "string", "minLength": 1}, "element": {"description": "The element the delta shows.", "type": "string", "minLength": 1}, "status": {"description": "How the code on main relates to the item.", "$ref": "#/$defs/ReconStatus"}, "from": {"description": "What the code holds now; the literal value absent for an add item.", "type": "string"}, "to": {"description": "What the code must hold; the literal value removed for a remove item.", "type": "string"}, "evidence": {"description": "Each entry a file:line on main you read, followed by what it shows; required for every status.", "type": "array", "minItems": 1, "items": {"type": "string", "pattern": "[^\\s:]+:\\d+"}}, "plannedBy": {"description": "The id of the open bead that plans the change; for planned-elsewhere only, null otherwise.", "type": ["string", "null"]}, "surface": {"description": "The surface the item lives on.", "$ref": "#/$defs/Surface"}}, "allOf": [{"if": {"required": ["status"], "properties": {"status": {"const": "add"}}}, "then": {"properties": {"from": {"$ref": "#/$defs/FromAbsent"}}}}, {"if": {"required": ["status"], "properties": {"status": {"const": "remove"}}}, "then": {"properties": {"to": {"$ref": "#/$defs/ToRemoved"}}}}, {"if": {"required": ["status"], "properties": {"status": {"const": "planned-elsewhere"}}}, "then": {"required": ["plannedBy"], "properties": {"plannedBy": {"type": "string", "minLength": 1}}}, "else": {"properties": {"plannedBy": {"type": "null"}}}}]}, "UiAuthority": {"description": "The design source of each ui item.", "type": "object", "additionalProperties": false, "required": ["uiItems"], "properties": {"uiItems": {"description": "One entry per ui item.", "type": "array", "items": {"$ref": "#/$defs/UiItem"}}, "mocksDir": {"description": "The mocks directory consulted, or null.", "type": ["string", "null"]}, "artifactsConsulted": {"description": "Every design artifact path opened.", "type": "array", "items": {"type": "string"}}}}, "UiItem": {"description": "The design source of one ui item.", "type": "object", "additionalProperties": false, "required": ["item", "designSource"], "properties": {"item": {"description": "The id of the item the Story builds.", "type": "string", "minLength": 1}, "designSource": {"description": "Where the item's design comes from.", "$ref": "#/$defs/DesignSource"}, "reason": {"description": "One sentence: which bundle packages it, or why it is designed with CDS or changes no design.", "type": "string"}, "artifact": {"description": "The artifact the item builds; required for bundle and cds, null for none.", "anyOf": [{"type": "null"}, {"$ref": "#/$defs/UiArtifact"}]}, "bundle": {"description": "Bundle only: the bundle directory exactly as depscore.py cds-bundles lists it.", "type": ["string", "null"]}, "buildSpec": {"description": "Bundle only: the build-spec.md path exactly as depscore.py cds-bundles lists it.", "type": ["string", "null"]}, "sections": {"description": "Bundle only: Section IDs (S1, S2, ...) from the build spec's Sections table; empty means the whole artifact.", "type": "array", "items": {"type": "string"}}}, "allOf": [{"if": {"required": ["designSource"], "properties": {"designSource": {"const": "none"}}}, "then": {"properties": {"artifact": {"type": "null"}}}, "else": {"required": ["artifact"], "properties": {"artifact": {"$ref": "#/$defs/UiArtifact"}}}}, {"if": {"required": ["designSource"], "properties": {"designSource": {"const": "bundle"}}}, "then": {"required": ["bundle", "buildSpec"], "properties": {"bundle": {"type": "string", "minLength": 1}, "buildSpec": {"type": "string", "minLength": 1}}}, "else": {"properties": {"bundle": {"type": "null"}, "buildSpec": {"type": "null"}, "sections": {"maxItems": 0}}}}]}, "UiArtifact": {"description": "A cds artifact, as a bundle.json names it.", "type": "object", "additionalProperties": false, "required": ["kind", "slug"], "properties": {"kind": {"description": "The artifact kind.", "$ref": "#/$defs/ArtifactKind"}, "slug": {"description": "Lower-case words joined by hyphens.", "type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"}}}, "DependencyChanges": {"description": "The upstream dependency changes that bear on the delta.", "type": "object", "additionalProperties": false, "required": ["current"], "properties": {"current": {"description": "True when no upstream change invalidates the delta.", "type": "boolean"}, "changeFindings": {"description": "One entry per upstream change that invalidates the delta.", "type": "array", "items": {"$ref": "#/$defs/ChangeFinding"}}, "evidence": {"description": "Under 60 words: what was checked.", "type": "string"}}}, "ChangeFinding": {"description": "One upstream change that invalidates the delta.", "type": "object", "additionalProperties": false, "required": ["dependency", "change", "invalidates"], "properties": {"dependency": {"description": "The dependency that changed.", "type": "string"}, "change": {"description": "What changed.", "type": "string"}, "invalidates": {"description": "What in the delta it invalidates.", "type": "string"}}}, "ReconReply": {"description": "What the detailing session returns: no item content.", "type": "object", "additionalProperties": false, "required": ["itemCount"], "properties": {"itemCount": {"description": "The number of entries in items.", "type": "integer"}, "error": {"description": "What failed, when anything failed.", "type": "string"}}}}}
const RECON_REPLY_SCHEMA = {"description": "What the detailing session returns: no item content.", "type": "object", "additionalProperties": false, "required": ["itemCount"], "properties": {"itemCount": {"description": "The number of entries in items.", "type": "integer"}, "error": {"description": "What failed, when anything failed.", "type": "string"}}}
const reconEnum = (name) => Object.freeze([...RECON_SCHEMA.$defs[name].enum])
const RECON_STATUSES = reconEnum('ReconStatus')
const RECON_WORK_STATUSES = reconEnum('WorkStatus')
const RECON_IDLE_STATUSES = reconEnum('IdleStatus')
const RECON_SURFACES = reconEnum('Surface')
const DESIGN_SOURCES = reconEnum('DesignSource')
const reconConstName = (v) => v.toUpperCase().replace(/[^A-Z0-9]+/g, '_')
const DESIGN_SOURCE = Object.freeze(Object.fromEntries(DESIGN_SOURCES.map((v) => [reconConstName(v), v])))
const ARTIFACT_KINDS = reconEnum('ArtifactKind')
const RECON_FROM_ABSENT = RECON_SCHEMA.$defs.FromAbsent.const
const RECON_TO_REMOVED = RECON_SCHEMA.$defs.ToRemoved.const
/** The detailing file name of one repository, from the schema's file template. */
const reconFileName = (slug) => {
  if (typeof slug !== 'string' || !slug || slug !== slug.trim() || slug.includes('/')) {
    const got = JSON.stringify(slug)
    throw new Error(`recon slug must be a non-empty name with no path separator, got ${got}`)
  }
  return RECON_SCHEMA['x-fileTemplate'].replace('{slug}', slug)
}
/** The detailing's fields as prompt text, rendered from RECON_SCHEMA so no prompt restates them. */
const reconFieldList = () => {
  const defs = RECON_SCHEMA.$defs
  const refName = (node) => (node && typeof node.$ref === 'string' ? node.$ref.split('/').pop() : null)
  const resolve = (node) => (refName(node) ? resolve(defs[refName(node)]) : node)
  const describe = (node) => {
    const name = refName(node)
    const n = resolve(node)
    if (n.anyOf) return n.anyOf.map(describe).join(' or ')
    if (n.enum) return n.enum.join(' | ')
    if (n.const !== undefined) return JSON.stringify(n.const)
    if (n.type === 'object') return name ? `${name} object` : 'object'
    if (n.type === 'array') return `list of ${describe(n.items)}`
    const t = Array.isArray(n.type) ? n.type.join(' or ') : n.type
    return n.pattern ? `${t} matching ${n.pattern}` : t
  }
  const objectOf = (node) => {
    const n = resolve(node)
    if (n.type === 'object') return n
    if (n.type === 'array') return objectOf(n.items)
    if (n.anyOf) return n.anyOf.map(objectOf).find(Boolean) || null
    return null
  }
  const lines = []
  const walk = (obj, depth, required) => {
    for (const [key, raw] of Object.entries(obj.properties || {})) {
      const description = raw.description || resolve(raw).description || ''
      const need = required.includes(key) ? 'required' : 'optional'
      lines.push(`${'  '.repeat(depth)}- \`${key}\` (${describe(raw)}, ${need}): ${description}`)
      const child = objectOf(raw)
      if (child) walk(child, depth + 1, child.required || [])
    }
  }
  const root = defs.ReconDetailing
  walk(root, 0, [...new Set([...(root.required || []), ...(RECON_SCHEMA['x-producerRequired'] || [])])])
  return lines.join('\n')
}
// ===== SHARED BLOCK recon-contract — END =====


// args: {
//   bead: { id, repoPath, story: { id, title? }, type?, labels?, title?, description?, specPath?, specPaths?, specSections?,
//           requirementIds?, matrix_elements (the matrix ids the Task states: its stack, what it builds and the shared
//           capabilities it uses), definitionOfDone?, decisionIds?, acceptanceCriteria?, surfaces?, apiSpec?, eventContracts?, testStrategy?,
//           cdsDesignSource?: one of DESIGN_SOURCES (recon-contract block), cdsArtifact?, cdsBundlePath?, cdsBuildSpecs? },
//   journal: { path, run } (the Task's step journal file, and the name of this run: every change this run reports carries it),
//   relay: { dir, runner? } (dir: the Task's own directory for relay files and regression artifacts, the same on every
//           dispatch of the Task; runner: relayrun.py, else pluginRoot's),
//   pluginRoot: string (the agent-teams-workforce install),
//   infraVocabulary: the object skills/artifact-handoff/scripts/infra_vocabulary.py prints,
//   designSystem?: { packagesDir? } (the folder of single-artifact cds bundles the owner supplied; read at build time),
//   spec?: object (defaults to bead), implementer?: string,
//   cdsRoot?: string (the cds plugin install; else the cds install $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records)
// }
const COMPOSITE = 'task-to-deploy'
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const spec = a.spec || bead
const story = bead.story && typeof bead.story === 'object' ? bead.story : {}
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const TAIL_CHARS = 4000
// A red check declines to add another round of test agents once this many checks have run, and a green
// check once this many have run since the implementers were selected or an audit sent violations back.
const MAX_RED_CHECKS = 4
const MAX_GREEN_CHECKS = 8

// An infrastructure Task, by the same type and label test route-build applies.
const norm = (v) => String(v || '').trim().toLowerCase()
const vocabulary = a.infraVocabulary || {}
const INFRA_TYPES = (Array.isArray(vocabulary.types) ? vocabulary.types : []).map(norm).filter(Boolean)
const INFRA_LABELS = (Array.isArray(vocabulary.labels) ? vocabulary.labels : []).map(norm).filter(Boolean)
const beadLabels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm)
const isInfra = INFRA_TYPES.includes(norm(bead.type)) || beadLabels.some((l) => INFRA_LABELS.includes(l))

// A Task whose surfaces include web-ui takes one design source: bundle (built from the cds bundle the owner
// supplied and audited against it), cds (designed with the CDS design system and audited against the live
// design system) or none (no design impact: no cds design step and no cds audit). A contract that records
// no design source takes bundle when it names a bundle, else cds. The design-source step then selects the
// source the build uses from the bundles supplied now: a mockup can arrive any time before its Task is built.
const UI_SURFACE = 'web-ui'
const isUiTask = (Array.isArray(bead.surfaces) ? bead.surfaces : []).map(norm).includes(UI_SURFACE)
const recordedDesignSource = !isUiTask
  ? null
  : DESIGN_SOURCES.includes(norm(bead.cdsDesignSource))
    ? norm(bead.cdsDesignSource)
    : String(bead.cdsBundlePath || '').trim()
      ? DESIGN_SOURCE.BUNDLE
      : DESIGN_SOURCE.CDS
const selectsDesign = recordedDesignSource === DESIGN_SOURCE.BUNDLE || recordedDesignSource === DESIGN_SOURCE.CDS

const inputFailure = (headline) => ({ ok: false, stage: 'input', beadId: bead.id || null, storyId: story.id || null, headline, detailPath: null })
if (!bead.id) return dispatchOutcome(inputFailure('no bead.id supplied'))
if (!INFRA_TYPES.length || !INFRA_LABELS.length) {
  return dispatchOutcome(inputFailure('no infraVocabulary supplied: pass the object skills/artifact-handoff/scripts/infra_vocabulary.py prints'))
}

// ── Relay: relayrun.py (the plugin's scripts/portfolio/) runs every deterministic step, and each result is
// saved in the directory of the step that ran it, under the Task's own directory ──
const RUNNER_TAIL = '/scripts/portfolio/relayrun.py'
const pluginRoot = String(a.pluginRoot || '').trim().replace(/\/+$/, '')
const givenRelay = a.relay && typeof a.relay === 'object' ? a.relay : {}
const relayRunner = String(givenRelay.runner || (pluginRoot ? `${pluginRoot}${RUNNER_TAIL}` : '')).trim()
const scripts = relayRunner.slice(0, -'relayrun.py'.length)
const RELAY = {
  runner: relayRunner,
  dir: String(givenRelay.dir || '').trim().replace(/\/+$/, ''),
  gitutils: `${scripts}gitutils.py`,
  depscore: `${scripts}depscore.py`,
  regression: `${scripts}regression.py`,
  artifactcontract: `${scripts}artifactcontract.py`,
}
const journalArg = a.journal && typeof a.journal === 'object' ? a.journal : {}
const journalPath = String(journalArg.path || '').trim()
const runName = String(journalArg.run || '').trim()
if (!pluginRoot.startsWith('/') || !RELAY.runner.startsWith('/') || !RELAY.runner.endsWith(RUNNER_TAIL) || !RELAY.dir.startsWith('/')) {
  return dispatchOutcome(inputFailure('pluginRoot and relay.dir are required absolute paths: the plugin install, and the directory this Task keeps its relay files and regression artifacts in'))
}
if (!journalPath.startsWith('/') || !runName) {
  return dispatchOutcome(inputFailure(`no journal supplied: ${bead.id} is built from its step journal, so pass journal: { path, run }`))
}

// The journal of the Task, once it is read; the step now running; and the phase it is shown under.
let J = null
let current = null
let currentPhase = null
const phaseTitle = (id) => compositePhaseTitle(COMPOSITE, id)
function enterPhase(id) {
  currentPhase = phaseTitle(id)
  phase(currentPhase)
}
/** The directory the running step keeps its relay files in. */
const stepDir = () => `${RELAY.dir}/${J.folder(current)}`
/** The relay file named `label` in `dir`. */
const relayFileIn = (dir, label) => `${dir}/${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
/** The relay arg a workflow script the running step calls gets: this run's runner and the step's directory. */
const stepRelay = () => ({ runner: RELAY.runner, dir: stepDir() })

// Returns the stage for a failed step result: dispatch failure, or `stage`.
const stageOf = (stage, r) => (!r || r.dispatchFailed ? DISPATCH_FAILED_STAGE : stage)

const list = (v) => (Array.isArray(v) ? v.filter(Boolean) : [])

// A test ruling must disposition every named test before the implementers work again.
function checkTestDecisions(issues, decisions) {
  const requested = [...new Set((Array.isArray(issues) ? issues : []).map((x) => String((x && x.testId) || '').trim()).filter(Boolean))]
  const returned = Array.isArray(decisions) ? decisions : []
  const problems = []
  const accepted = []
  for (const id of requested) {
    const matches = returned.filter((x) => x && String(x.testId || '').trim() === id)
    if (matches.length !== 1) {
      problems.push(`${id}: expected one disposition, received ${matches.length}`)
      continue
    }
    const decision = matches[0]
    if (!['update', 'delete', 'keep'].includes(decision.action) || typeof decision.reason !== 'string' || !decision.reason.trim()) {
      problems.push(`${id}: disposition needs a valid action and a nonempty reason`)
      continue
    }
    accepted.push({ testId: id, action: decision.action, reason: decision.reason })
  }
  return { problems, decisions: accepted }
}

// A suite-run failure, { kind: test | load, file, test, line }, keyed the same way in every run.
const entryOf = (f) =>
  f && typeof f === 'object'
    ? { kind: f.kind === 'load' ? 'load' : 'test', file: String(f.file || '').trim().replace(/^\.\//, ''), test: String(f.test || '').trim(), line: String(f.line || '').trim() }
    : null
const idOf = (e) => `${e.kind}|${e.file}|${e.test}`
const describe = (e) => (e.kind === 'load' ? `${e.file || e.line} could not be loaded` : `${e.file}${e.test ? ` ${e.test}` : ''}`)
const failures = (run) => {
  const byId = new Map()
  for (const e of list(run && run.failing).map(entryOf)) if (e && (e.file || e.test)) byId.set(idOf(e), e)
  return byId
}
const failingIds = (run) => new Set(failures(run).keys())
const sameFile = (p, f) => {
  const x = String(p || '').replace(/^\.\//, '')
  const y = String(f || '').replace(/^\.\//, '')
  return !!x && !!y && (x === y || x.endsWith(`/${y}`) || y.endsWith(`/${x}`))
}

// A suite run as feedback text for the next session.
const runText = (run) =>
  [
    `The suite runner ran \`${(run && run.command) || '(no command)'}\` and it exited ${run ? run.exitCode : 'with no result'}.`,
    run && run.summary ? `Summary: ${run.summary}` : '',
    failures(run).size ? `Failing:\n${[...failures(run).values()].map((e) => e.line || describe(e)).join('\n')}` : '',
    run && run.tail ? `Output (last part):\n${String(run.tail).slice(-TAIL_CHARS)}` : '',
  ]
    .filter(Boolean)
    .join('\n')

const validRun = (r) => !!r && !r.dispatchFailed && Number.isInteger(r.exitCode) && r.exitCode >= 0
/** A suite run as the journal holds it: what the later steps read of it. */
const runValue = (run) => ({
  command: String(run.command || ''),
  exitCode: run.exitCode,
  summary: String(run.summary || ''),
  failing: list(run.failing),
  tail: String(run.tail || '').slice(-TAIL_CHARS),
  relayFile: run.relayFile || null,
})

/** Runs one gitutils.py command through relayrun.py; returns { facts } or { error }. */
async function gitutils(label, argv) {
  const r = await relayKit.run(guardedAgent, { label, phase: currentPhase || phaseTitle('green'), runner: RELAY.runner, argv: ['python3', RELAY.gitutils, ...argv], file: relayFileIn(stepDir(), label) })
  if (!r.ok) return { error: r.error }
  if (r.exitCode !== 0 || !r.json || r.json.error) return { error: String((r.json && r.json.error) || `gitutils.py ${argv[0]} exited ${r.exitCode}`) }
  return { facts: r.json }
}
// The role this workflow runs atw-matrix as (matrix-kinds.json roles): check-reuse runs for no other role.
const MATRIX_ROLE = 'build-workflow'
/** The ids of the matrix entries the Task states it builds and uses (its matrix_elements key). */
const statedIds = [...new Set((Array.isArray(bead.matrix_elements) ? bead.matrix_elements : []).map((id) => String(id || '').trim()).filter(Boolean))]
/** Runs one atw-matrix command through relayrun.py; returns { out } (the keys asked for of the object it printed) or { error }. */
async function matrixCommand(label, argv, keys) {
  const r = await relayKit.run(guardedAgent, { label, phase: currentPhase, runner: RELAY.runner, argv: ['/usr/bin/env', `ATW_MATRIX_ROLE=${MATRIX_ROLE}`, `${pluginRoot}/bin/atw-matrix`, ...argv], file: relayFileIn(stepDir(), label), keys: [...keys, 'error'] })
  if (!r.ok) return { error: r.error }
  if (r.exitCode !== 0 || !r.json || r.json.error) return { error: String((r.json && r.json.error) || `atw-matrix ${argv[0]} exited ${r.exitCode}; its output is in ${r.relayFile}`) }
  return { out: r.json }
}
/**
 * Returns { files: { <path>: <git blob hash or "missing"> }, treeDigest } for the given test files in the
 * tree (treeDigest changes exactly when the work tree changes), or { error }.
 */
async function fingerprint(tree, files, label) {
  let r
  try {
    r = await gitutils(label, ['hash-files', '--tree', tree, ...files])
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  if (r.error) return { error: `the fingerprint of the test files did not run: ${r.error}`.slice(0, 500) }
  const got = r.facts.files && typeof r.facts.files === 'object' ? r.facts.files : {}
  const missing = files.filter((f) => !(f in got))
  return missing.length ? { error: `the fingerprint names no hash for ${missing.join(', ')}` } : { files: got, treeDigest: String(r.facts.treeDigest || '') }
}

// ── What a step is handed: every value below is read from the artifacts the steps before it recorded ──
/** The Story's worktree. */
const treeAt = (step) => String(J.latest('worktree', step, '') || '')
/** The design source the build uses: what the design-source step selected, else what the contract records. */
function designAt(step) {
  const selected = J.latest('design', step)
  if (selected && typeof selected === 'object') return selected
  return {
    designSource: recordedDesignSource,
    bundle: recordedDesignSource === DESIGN_SOURCE.BUNDLE ? String(bead.cdsBundlePath || '').trim() || null : null,
    buildSpecs: list(bead.cdsBuildSpecs).map((x) => String(x).trim()).filter(Boolean),
  }
}
/** The test files the test agents have written or changed so far. */
const testFilesAt = (step) => [...new Set(J.every('testFiles', step).flatMap((files) => list(files).map(String)))]
/** The files the implementers have changed so far. */
const changedFilesAt = (step) => [...new Set(J.every('changedFiles', step).flatMap((files) => list(files).map(String)))]
/** The Task's build contract as it stands at a step. */
function contractAt(step) {
  const tree = treeAt(step)
  const design = designAt(step)
  const declaredSurfaces = Array.isArray(bead.surfaces) ? bead.surfaces : null
  const structuralSurfaces = [
    bead.apiSpec ? 'api-contract' : null,
    Array.isArray(bead.eventContracts) && bead.eventContracts.length ? 'event-chain' : null,
  ].filter(Boolean)
  const contractSurfaces = declaredSurfaces
    ? [...new Set([...declaredSurfaces, ...structuralSurfaces])]
    : structuralSurfaces.length
      ? structuralSurfaces
      : null
  const contract = {
    spec,
    bead: { id: bead.id, title: bead.title || null, description: bead.description || null, repoPath: tree },
    repoPath: tree,
    acceptanceCriteria: Array.isArray(bead.acceptanceCriteria) ? bead.acceptanceCriteria : [],
    decisionIds: [
      ...new Set(
        [...(Array.isArray(spec && spec.decisionIds) ? spec.decisionIds : []), ...(Array.isArray(bead.decisionIds) ? bead.decisionIds : [])]
          .map((x) => String(x || '').trim())
          .filter(Boolean)
      ),
    ],
    surfaces: contractSurfaces,
    testStrategy: bead.testStrategy && typeof bead.testStrategy === 'object' ? bead.testStrategy : null,
    cdsDesignSource: design.designSource,
    cdsBundlePath: design.designSource === DESIGN_SOURCE.BUNDLE ? design.bundle : null,
    cdsBuildSpecs: design.designSource === DESIGN_SOURCE.BUNDLE ? list(design.buildSpecs) : [],
  }
  const provisioning = J.latest('provisioning', step)
  if (provisioning && typeof provisioning === 'object') {
    const stacks = Array.isArray(provisioning.affectedStacks) ? provisioning.affectedStacks : []
    contract.affectedStacks = stacks
    contract.provisioningIntent = provisioning.provisioningIntent
    contract.acceptanceCriteria = [
      ...contract.acceptanceCriteria.filter(Boolean),
      {
        given: `the provisioning intent for ${bead.title || 'this infrastructure change'} on stacks ${stacks.join(', ') || '(affected stacks)'}`,
        when: 'cdk synth runs against the changed stacks',
        then: 'the synthesized template asserts the intended resources and their properties, the cross-stack references the stacks write and read, and the IAM permissions the intent names',
      },
    ]
  }
  const scope = J.latest('regressionScope', step)
  if (scope && typeof scope === 'object') {
    const kinds = list(scope.requiredKinds)
    contract.regressionPlanPath = J.latest('regressionPlan', step)
    contract.surfaces = [...new Set([...(contract.surfaces || []), ...(kinds.includes('contract') ? ['api-contract'] : []), ...(kinds.includes('integration') ? ['event-chain'] : [])])]
  }
  const suiteCommand = String(J.latest('suiteCommand', step, '') || '').trim()
  const shared = J.latest('sharedCapabilities', step)
  if (Array.isArray(shared)) contract.sharedCapabilities = shared
  // The Epic's TRD, which elaboration hands the Task's journal as the artifact `TRD`: a source of
  // information for the build's decisions, read by the test writers and the implementers.
  const trd = J.latest('TRD', step)
  if (typeof trd === 'string' && trd) contract.trdPath = trd
  if (suiteCommand) {
    contract.suiteCommand = suiteCommand
    // Read by the implementer selection and implementation briefs: explicit authority to repair the baseline.
    contract.baselineRepairScope = 'affected-repository'
  }
  return contract
}
/** Runs the repository's suite once through the suite-run workflow script; resolves the command when none is given. */
async function suite(step, label) {
  const command = String(J.latest('suiteCommand', step, '') || '').trim()
  const r = await settleWorkflow('agent-teams-workforce:suite-run', { repoPath: treeAt(step), ...(command ? { command } : {}), label, relay: stepRelay() })
  return r || null
}

const REGRESSION_SCHEMA = {"type":"object","additionalProperties":false,"required":["components","discovery","requirements","mappings","runs","sourceFiles","replacements"],"properties":{"replacements":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["requirementId","kind","oldTestId","newTestIds","reason"],"properties":{"requirementId":{"type":"string"},"kind":{"type":"string"},"oldTestId":{"type":"string"},"newTestIds":{"type":"array","minItems":1,"items":{"type":"string"}},"reason":{"type":"string","minLength":1}}}},"sourceFiles":{"type":"array","minItems":1,"items":{"type":"string","minLength":1}},"components":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["id","files"],"properties":{"id":{"type":"string","minLength":1},"files":{"type":"array","items":{"type":"string","minLength":1}}}}},"discovery":{"type":"object","additionalProperties":false,"required":["sourceRefs","priorRequirementsSearched","greenfield","evidence"],"properties":{"sourceRefs":{"type":"array","items":{"type":"string","minLength":1}},"priorRequirementsSearched":{"type":"boolean"},"greenfield":{"type":"boolean"},"evidence":{"type":"string","minLength":1}}},"requirements":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["id","sourceRef","componentIds","repoPath","impacted","impactReason","applicability","supersedes"],"properties":{"id":{"type":"string","minLength":1},"sourceRef":{"type":"string","minLength":1},"componentIds":{"type":"array","items":{"type":"string","minLength":1}},"repoPath":{"type":"string","minLength":1},"impacted":{"type":"boolean"},"impactReason":{"type":"string","minLength":1},"applicability":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["kind","required","reason","sourceRefs"],"properties":{"kind":{"type":"string","enum":["unit","contract","integration","nonfunctional"]},"required":{"type":"boolean"},"reason":{"type":"string","minLength":1},"sourceRefs":{"type":"array","items":{"type":"string","minLength":1}}}}},"supersedes":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["id","sourceRef","reason"],"properties":{"id":{"type":"string","minLength":1},"sourceRef":{"type":"string","minLength":1},"reason":{"type":"string","minLength":1}}}}}}},"mappings":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["requirementId","kind","runId","testIds"],"properties":{"requirementId":{"type":"string","minLength":1},"kind":{"type":"string","enum":["unit","contract","integration","nonfunctional"]},"runId":{"type":"string","minLength":1},"testIds":{"type":"array","items":{"type":"string","minLength":1}}}}},"runs":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["id","repoPath","command","reportPath","format"],"properties":{"id":{"type":"string","minLength":1},"repoPath":{"type":"string","minLength":1},"command":{"type":"string","minLength":1},"reportPath":{"type":"string","minLength":1},"format":{"type":"string","enum":["junit"]}}}}}}
const REGRESSION_REVIEW_SCHEMA = {"type":"object","additionalProperties":false,"required":["approved","findings","evidence"],"properties":{"approved":{"type":"boolean"},"findings":{"type":"array","items":{"type":"string","minLength":1}},"evidence":{"type":"array","items":{"type":"string","minLength":1}}}}

// ── Regression scope: the assessment and its review are written by agents as saved artifacts; regression.py
// prepares, validates and verifies them. Source assessment stays separate from deterministic validation. ──
const REGRESSION_DIR = `${RELAY.dir}/regression`
const REGRESSION_FILES = {
  previous: `${REGRESSION_DIR}/previous.json`,
  plan: `${REGRESSION_DIR}/plan.json`,
  planReview: `${REGRESSION_DIR}/plan-review.json`,
  mapped: `${REGRESSION_DIR}/mapped.json`,
  mappedReview: `${REGRESSION_DIR}/mapped-review.json`,
}
/** Runs one regression.py mode on a plan file; returns what it printed, or { ok: false, reason }. */
async function regressionInvoke(step, mode, plan, output, extra = []) {
  const ledger = `${treeAt(step)}/.agent-workforce/regression.json`
  const result = await relayKit.run(guardedAgent, { label: `regression:${mode}`, phase: currentPhase, runner: RELAY.runner,
    argv: ['python3', RELAY.regression, mode, '--plan', plan, '--ledger', ledger, '--output', output, ...extra],
    file: relayFileIn(stepDir(), `regression-${mode}`), timeout: 540 })
  if (!result.ok || result.exitCode !== 0 || !result.json || result.json.ok !== true) return { ok: false, reason: result.error || JSON.stringify(result.json || {}) }
  return result.json
}
/** The requirement source files the contract names. */
const regressionSources = (contract) => [...new Set([contract.spec && contract.spec.specPath, ...((contract.spec && contract.spec.specPaths) || [])].filter(x => typeof x === 'string' && x.startsWith('/')).map(x => x.split('#')[0]))]
/** Has one agent write a regression artifact as a saved candidate, then validates and accepts it as `file`. */
async function author(file, schema, agentType, prompt) {
  const candidate = `${file}.candidate.json`
  const revision = J.folder(current)
  const returned = await guardedAgent(prompt + relayKit.artifactBrief(candidate, schema, revision, RELAY.artifactcontract), { agentType, phase: currentPhase, schema: relayKit.ARTIFACT_SCHEMA })
  if (dispatchInterruption) return { ok: false, noResult: true, error: 'the artifact dispatch was interrupted; the saved work is retained' }
  return relayKit.acceptArtifact(guardedAgent, { label: `regression:${agentType}`, phase: currentPhase, runner: RELAY.runner, revision, candidate, file, schema,
    relayFile: relayFileIn(stepDir(), 'regression-artifact'), returned })
}
const regressionBrief = (contract, previous, final) => `${final ? `Finalize mode: the approved scope is ${contract.regressionPlanPath}.` : 'Plan mode: write the impact scope before Red.'}
Task contract (source references are authoritative): ${JSON.stringify(contract)}
Previous cumulative requirements and mappings: ${previous}. Repository: ${contract.repoPath}.`
const regressionReviewBrief = (plan, previous, final) => `${final ? 'Mapping review' : 'Plan review'} of ${plan}. Previous cumulative requirements and mappings: ${previous}.`

// ── cds audit: the cds plugin's tools/audit-app.py over the files the Task changed (uncommitted
// against HEAD, untracked included: the Task commits only at the end), then a judgment session on
// the findings the script cannot rule on ──
const CDS_AUDIT_MAX_FINDINGS = 60
const CDS_JUDGMENT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['rulings'],
  properties: {
    rulings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'value', 'ruling', 'reason'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          value: { type: 'string' },
          ruling: { type: 'string', enum: ['violation', 'allowed', 'cds-gap'] },
          reason: { type: 'string' },
        },
      },
    },
  },
}
// Resolves tools/audit-app.py (cdsRoot, else the cds install the plugin registry records for
// $ATW_CONTROL_REPO, else the user-scope one) and runs it; its exit status is the script's.
const RUN_CDS_AUDIT_PY = `import json, os, subprocess, sys
from pathlib import Path
repo, bundle, override, cap = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
script = Path(override, "tools", "audit-app.py") if override else None
problem = f"{script} does not exist" if script and not script.is_file() else ""
if script is None:
    control = os.environ.get("ATW_CONTROL_REPO", "").strip()
    config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude")
    reg = Path(config) / "plugins" / "installed_plugins.json"
    try:
        plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
    except (OSError, ValueError) as exc:
        plugins, problem = {}, f"{reg} is unreadable: {exc}"
    ranked = []
    for key, entries in plugins.items():
        if not key.startswith("cds@") or not isinstance(entries, list):
            continue
        for e in entries:
            path = Path(str(e.get("installPath") or ""), "tools", "audit-app.py") if isinstance(e, dict) else None
            if not path or not path.is_file():
                continue
            if e.get("scope") in ("local", "project") and control and os.path.normpath(str(e.get("projectPath") or "")) == os.path.normpath(control):
                ranked.append((0, str(path)))
            elif e.get("scope") == "user":
                ranked.append((1, str(path)))
    if ranked:
        script = Path(sorted(ranked)[0][1])
    elif not problem:
        problem = f"{reg} lists no cds install shipping tools/audit-app.py at user scope or for $ATW_CONTROL_REPO"
if problem:
    print(json.dumps({"error": problem}))
    sys.exit(2)
done = subprocess.run([sys.executable, str(script), "--repo", repo, "--bundle", bundle], capture_output=True, text=True)
try:
    report = json.loads(done.stdout)
except ValueError:
    print(json.dumps({"error": (done.stdout + done.stderr).strip()[-2000:] or f"audit-app.py exited {done.returncode} and printed nothing"}))
    sys.exit(2)
findings = report.get("findings") or []
if len(findings) > int(cap):
    report["findings"], report["truncated"] = findings[: int(cap)], len(findings)
def cell(v):
    return "" if v is None else str(v)
canon = "\\n".join("\\t".join(cell(f.get(k)) for k in ("file", "line", "rule", "value", "ruling")) for f in report.get("findings") or [] if isinstance(f, dict))
h = 0x811C9DC5
for ch in f"{cell(report.get('scriptVersion'))}\\n{done.returncode}\\n{cell(report.get('truncated'))}\\n{canon}":
    h = ((h ^ ord(ch)) * 0x01000193) & 0xFFFFFFFF
report["digest"] = format(h, "08x")
print(json.dumps(report))
sys.exit(done.returncode)`

// The digest RUN_CDS_AUDIT_PY prints: FNV-1a (32-bit) over the script version, the exit status, the
// truncated count and each finding's file, line, rule, value and ruling, by code point. The verdict is
// computed from the relayed report only when this recomputes to the digest the script printed, so a
// relay that drops, adds or alters a finding is refused instead of acted on.
const cell = (v) => (v === null || v === undefined ? '' : String(v))
function auditDigest(report, exitCode) {
  const canon = list(report.findings)
    .filter((f) => f && typeof f === 'object')
    .map((f) => ['file', 'line', 'rule', 'value', 'ruling'].map((k) => cell(f[k])).join('\t'))
    .join('\n')
  let h = 0x811c9dc5
  for (const ch of `${cell(report.scriptVersion)}\n${exitCode}\n${cell(report.truncated)}\n${canon}`) {
    h = Math.imul(h ^ ch.codePointAt(0), 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

const findingText = (f) => `${f.file}:${f.line} ${f.rule} ${f.value}${f.reason ? ` (${f.reason})` : ''}`

/** Runs the audit script over the Task's changes and rules its judgment findings; returns { error } or { report, violations, gaps, allowed, scriptVersion }. */
async function auditCds(tree, bundle, label) {
  // relayrun.py runs the audit script; its exit status and report reach the workflow checked.
  let out = null
  try {
    const r = await relayKit.run(guardedAgent, {
      label,
      phase: currentPhase || phaseTitle('cds-audit'),
      runner: RELAY.runner,
      argv: ['python3', '-c', RUN_CDS_AUDIT_PY, tree, bundle, String(a.cdsRoot || '').trim(), String(CDS_AUDIT_MAX_FINDINGS)],
      file: relayFileIn(stepDir(), label),
    })
    if (!r.ok) return { error: String(r.error).slice(0, 500) }
    out = { exitCode: r.exitCode, output: r.json || { error: `the cds audit printed no JSON (exit ${r.exitCode}); its output is in ${r.relayFile}` } }
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  const report = (out && out.output) || {}
  if (!out || ![0, 1].includes(out.exitCode) || report.error || !Array.isArray(report.findings)) {
    return { error: String(report.error || `the cds audit did not run${out ? `: exit ${out.exitCode}` : ''}`).slice(0, 500), scriptVersion: report.scriptVersion || null }
  }
  if (String(report.digest || '') !== auditDigest(report, out.exitCode)) {
    return { error: 'the relayed cds audit report does not match the digest the audit script printed, so its findings are not the script\'s own', scriptVersion: report.scriptVersion || null }
  }
  if ((out.exitCode === 0) !== (report.findings.length === 0 && !report.truncated)) {
    return { error: `the cds audit exited ${out.exitCode} with ${report.truncated || report.findings.length} finding(s)`, scriptVersion: report.scriptVersion || null }
  }
  const scriptVersion = String(report.scriptVersion || 'unknown')
  const findings = report.findings.filter((f) => f && typeof f === 'object')
  const violations = findings.filter((f) => f.ruling !== 'judgment')
  const gaps = []
  const allowed = []
  const toJudge = findings.filter((f) => f.ruling === 'judgment')
  const sameFinding = (x, f) => x && x.file === f.file && Number(x.line) === Number(f.line) && x.value === f.value
  let unruled = toJudge
  if (unruled.length) {
    let judged = null
    try {
      judged = await guardedAgent(
        `Work tree: ${tree}
cds bundle: ${bundle}

Findings the deterministic cds audit could not rule on, one per line (file:line rule value):
${unruled.map(findingText).join('\n')}`,
        { agentType: 'cds-finding-reviewer', label: `${label}:judgment`, phase: currentPhase || phaseTitle('cds-audit'), schema: CDS_JUDGMENT_SCHEMA }
      )
    } catch (err) {
      return { error: `the judgment on ${unruled.length} cds finding(s) threw: ${String((err && err.message) || err).slice(0, 300)}`, scriptVersion }
    }
    const rulings = list(judged && judged.rulings)
    const still = []
    for (const f of unruled) {
      const r = rulings.find((x) => sameFinding(x, f))
      if (!r) {
        still.push(f)
        continue
      }
      const ruled = { ...f, ruling: r.ruling, reason: r.reason }
      if (ruled.ruling === 'allowed') allowed.push(ruled)
      else if (ruled.ruling === 'cds-gap') gaps.push(ruled)
      else violations.push(ruled)
    }
    unruled = still
  }
  if (unruled.length) {
    return { error: `cds:audit-against-system returned no ruling on ${unruled.length} finding(s): ${unruled.slice(0, 5).map(findingText).join('; ')}`, scriptVersion }
  }
  if (report.truncated) log(`cds audit: ${report.truncated} finding(s); the first ${CDS_AUDIT_MAX_FINDINGS} are ruled on`)
  return { report, violations, gaps, allowed, scriptVersion }
}

const packagesDir = String((a.designSystem && a.designSystem.packagesDir) || a.packagesDir || '').trim()
/** Selects the design source a bundle or cds Task builds with now; returns { selection } or { error }. */
async function selectDesign() {
  const art = bead.cdsArtifact && typeof bead.cdsArtifact === 'object' ? bead.cdsArtifact : {}
  const recorded = String(bead.cdsBundlePath || '').trim()
  if (!packagesDir && !recorded) return { selection: null }
  const argv = [
    '--packages-dir', packagesDir,
    '--design-source', recordedDesignSource,
    '--kind', String(art.kind || '').trim(),
    '--slug', String(art.slug || '').trim(),
    '--recorded-bundle', recorded,
  ]
  let o = null
  try {
    o = await relayKit.depscore(guardedAgent, {
      label: 'cds-select',
      phase: currentPhase || phaseTitle('workspace'),
      script: RELAY.depscore,
      repo: null,
      tail: ['cds-bundles', ...argv].map(relayKit.quote).join(' '),
      file: relayFileIn(stepDir(), 'cds-select'),
    })
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  if (o.error || !o.selection || typeof o.selection !== 'object') {
    return { error: String(o.error || 'depscore.py cds-bundles returned no selection').slice(0, 500) }
  }
  return { selection: o.selection }
}

const LIVE_AUDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['audited', 'findings'],
  properties: {
    audited: { type: 'boolean' },
    error: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'rule', 'value', 'ruling', 'reason'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          rule: { type: 'string' },
          value: { type: 'string' },
          ruling: { type: 'string', enum: ['violation', 'allowed', 'cds-gap'] },
          reason: { type: 'string' },
        },
      },
    },
  },
}
/** Audits the Task's changes against the live CDS design system with cds:audit-against-system; returns { error } or { report, violations, gaps, allowed, scriptVersion }. */
async function auditCdsLive(tree, label) {
  let out = null
  try {
    out = await guardedAgent(
      `Work tree: ${tree}`,
      { agentType: 'cds-live-auditor', label, phase: currentPhase || phaseTitle('cds-audit'), schema: LIVE_AUDIT_SCHEMA }
    )
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300), scriptVersion: 'audit-against-system' }
  }
  if (!out || out.audited !== true || !Array.isArray(out.findings)) {
    return { error: String((out && out.error) || 'cds:audit-against-system returned no audit').slice(0, 500), scriptVersion: 'audit-against-system' }
  }
  const findings = out.findings.filter((f) => f && typeof f === 'object')
  return {
    report: { findings, files: list(out.files) },
    violations: findings.filter((f) => f.ruling === 'violation'),
    gaps: findings.filter((f) => f.ruling === 'cds-gap'),
    allowed: findings.filter((f) => f.ruling === 'allowed'),
    scriptVersion: 'audit-against-system',
  }
}

// ── The steps: one function per step kind of the build pipeline (pipeline-steps.json). Each takes the step,
// reads what it needs from the artifacts of earlier steps, and returns { artifacts, add } when the step is
// done (add: the steps its result calls for, placed right after it) or { fail } with the cause. ──
const { file: fileArtifact, directory: directoryArtifact, value: valueArtifact } = stepJournal
const failed = (stage, message, more) => ({ fail: { stage, message, ...(more || {}) } })
/** The audits that send violations back to the implementers, each with the name its brief carries. */
const AUDIT_BRIEF = { 'build:cds-audit': 'cds', 'build:reuse-audit': 'reuse' }
/** The newest done step before `step` that opened the present sequence of implementers: their selection, or an audit that sent violations back. */
const greenBoundary = (step) => J.earlier(['build:select-implementers', ...Object.keys(AUDIT_BRIEF)], step).pop() || null
/** The audit whose violations the implementers after `boundary` answer, as the brief names it; null when they answer none. */
const auditOf = (boundary) => (boundary && AUDIT_BRIEF[boundary.kind]) || null
/** What the implementers are told when the suite already failed before the Task: repairing it is assigned to them. */
const baselineNoteAt = (step) => {
  const baseline = J.latest('baseline', step)
  if (!baseline || baseline.exitCode === 0) return ''
  const ids = failingIds(baseline)
  return `\nBASELINE REPAIR IS ASSIGNED: fix ALL pre-existing suite failures in ${treeAt(step)}, including failures outside the Task's feature. ${ids.size ? [...failures(baseline).values()].map(describe).join('; ') : 'No individual failing test IDs were parsed; diagnose the baseline output.'} Green still requires the whole suite to exit 0.\nBaseline evidence:\n${runText(baseline)}`
}
/** What the implementers and their selection are told: the suite result that calls for the work, and the rulings accepted so far. */
function greenFeedbackAt(step) {
  const boundary = greenBoundary(step)
  const lastCheck = J.earlier(['build:green-check'], step, boundary).pop() || null
  const note = baselineNoteAt(step)
  let feedback
  if (lastCheck) {
    const all = J.steps()
    const ruled = (all[all.indexOf(lastCheck) - 1] || {}).kind === 'build:test-ruling'
    feedback = `The suite is not green yet.${ruled ? ' The test author ruled on the named tests; the exact accepted decisions are attached below.' : ''}\n${runText(J.latest('greenRun', step))}${note}`
  } else if (boundary && boundary.kind === 'build:cds-audit') {
    const design = designAt(step)
    const bundle = design.designSource === DESIGN_SOURCE.BUNDLE ? design.bundle : null
    const standard = bundle
      ? `The cds bundle at ${bundle} (its styles/ stylesheet set) is the only source of visual design: replace each finding with the classes and custom properties the bundle ships`
      : 'No mockup was supplied: the live CDS design system (the project\'s design system config and the stylesheets, tokens and components it defines) is the only source of visual design: replace each finding with the cds classes and custom properties'
    const audit = J.latest('cdsAudit', step) || {}
    feedback = `The cds audit found UI code that styles outside the cds design system. ${standard}, and add no stylesheet, inline style, color or length of your own. Use supplied applicable mock/build-spec choices, graphics and stylesheets as design inputs that need not specify every detail. Preserve their established intent and any explicit precision requirements; use judgment with the Task requirements and configured cds for unspecified interactions, states and responsive behavior; when this Task instead owns UI design without a mock, use configured cds and the approved application standards. Resolve findings through supported configuration/composition or generated-artifact correction where applicable. If an input or capability outside this Task remains necessary, name it with evidence in upstreamMissing; do not assume a cds plugin extension is required merely because the current bundle lacks the output. The whole suite has to stay green.
Findings (file:line rule value):
${list(audit.violations).join('\n')}${note}`
  } else if (boundary && boundary.kind === 'build:reuse-audit') {
    const audit = J.latest('reuseAudit', step) || {}
    feedback = `The reuse audit found that the changed code breaks the shared capabilities this Task must use: it holds a behaviour a shared library, layer, chassis or service provides, or it leaves unused a capability the Task relies on. For each finding, take the behaviour from the capability's interface named in SHARED CAPABILITIES THIS TASK MUST USE and remove the local code that repeats it. When the capability lacks something the Task needs, write nothing in its place and name it with evidence in upstreamMissing. The whole suite has to stay green.
Findings (file:line finding capability provides: detail):
${list(audit.violations).join('\n')}${note}`
  } else {
    feedback = `${runText(J.latest('redRun', step))}${note}`
  }
  const accepted = new Map()
  for (const decision of J.every('testDecisions', step).flatMap((decisions) => list(decisions))) accepted.set(decision.testId, decision)
  return `${feedback}${accepted.size ? `\n\nAccepted test-author rulings (retain these unless new evidence warrants reopening):\n${JSON.stringify([...accepted.values()])}` : ''}`
}
/** What the Green workflow script is handed of Red: the test files and the suite result that shows them failing. */
const redFor = (step) => ({ testFiles: testFilesAt(step), evidence: runText(J.latest('redRun', step)) })

async function stepWorkspace(step) {
  enterPhase('workspace')
  if (!String(bead.repoPath || '').trim()) {
    return failed('input', `${bead.id} carries no repoPath, so its build contract is incomplete. The repository is ruled during elaboration: re-elaborate the Task's Story, or record the repository on the Task as its repoPath.`, {
      incompleteContract: ['repoPath'],
      requiredHumanActions: [`re-elaborate the Story of ${bead.id}, or record the ruled repository on it as its repoPath`],
    })
  }
  if (!String(story.id || '').trim()) {
    return failed('input', `${bead.id} names no Story. A Task is built on its Story's branch and deploys with its Story, so it needs one: parent it to the Story of its repository.`, {
      incompleteContract: ['story'],
      requiredHumanActions: [`parent ${bead.id} to the Story of its repository`],
    })
  }
  const workspace = await settleWorkflow('agent-teams-workforce:workspace', {
    repoPath: bead.repoPath,
    beadId: story.id,
    branchPrefix: 'story',
    purpose: story.title || `Story ${story.id}`,
    relay: stepRelay(),
  })
  if (!workspace || workspace.ok !== true || !workspace.repoPath) {
    const why = (workspace && Array.isArray(workspace.blocked) && workspace.blocked[0]) || 'the workspace step returned nothing'
    return failed(stageOf('workspace', workspace), `no worktree was established: ${why}`)
  }
  return {
    artifacts: [directoryArtifact('worktree', workspace.repoPath), valueArtifact('branch', workspace.branch || null), valueArtifact('defaultBranch', workspace.defaultBranch || null)],
    add: [...(selectsDesign ? [{ kind: 'build:design-source' }] : []), ...(isInfra ? [{ kind: 'build:infra-intent' }] : [])],
  }
}

async function stepDesignSource(step) {
  enterPhase('workspace')
  let designSource = recordedDesignSource
  let buildSpecs = list(bead.cdsBuildSpecs).map((x) => String(x).trim()).filter(Boolean)
  let usedBundle = designSource === DESIGN_SOURCE.BUNDLE ? String(bead.cdsBundlePath || '').trim() || null : null
  const blockedVerdict = { verdict: 'blocked', findings: 0, scriptVersion: null }
  const picked = await selectDesign()
  if (picked.error) return failed('cds-select', `cds-select: the design source of ${bead.id} could not be selected: ${picked.error}`)
  if (picked.selection) {
    const sel = picked.selection
    if (sel.blocked) {
      const upstream = [{ what: `cds bundle: ${sel.blocked}` }]
      return failed('blocked-upstream', `blocked-upstream: ${bead.id} builds from a supplied cds bundle and ${sel.blocked}`, { upstreamMissing: upstream, cdsAudit: blockedVerdict })
    }
    if (sel.designSource === DESIGN_SOURCE.BUNDLE && sel.bundle) {
      const sameBundle = usedBundle && sel.bundle.replace(/\/+$/, '') === usedBundle.replace(/\/+$/, '')
      if (!sameBundle) buildSpecs = [sel.buildSpec]
      if (designSource !== DESIGN_SOURCE.BUNDLE || !sameBundle) log(`Design source: ${designSource} -> bundle ${sel.bundle}`)
      designSource = DESIGN_SOURCE.BUNDLE
      usedBundle = sel.bundle
    }
  }
  if (designSource === DESIGN_SOURCE.BUNDLE && !usedBundle) {
    const upstream = [{ what: `cds bundle: ${bead.id} records design source bundle but names neither a bundle nor a packages directory holding one` }]
    return failed('blocked-upstream', `blocked-upstream: ${upstream[0].what}`, { upstreamMissing: upstream, cdsAudit: blockedVerdict })
  }
  return { artifacts: [valueArtifact('design', { designSource, bundle: usedBundle, buildSpecs })] }
}

async function stepInfraIntent(step) {
  enterPhase('infra-intent')
  const contract = contractAt(step)
  const docs = contract.spec && typeof contract.spec === 'object' ? contract.spec : {}
  const intent = await settleWorkflow('agent-teams-workforce:infra-intent', {
    change: { id: bead.id, title: bead.title, description: bead.description, repoPath: treeAt(step) },
    upstream: {
      specPaths: [...new Set([docs.specPath, ...(Array.isArray(docs.specPaths) ? docs.specPaths : [])].filter((x) => typeof x === 'string' && x.trim()))],
      specSections: Array.isArray(docs.specSections) ? docs.specSections : [],
      decisionIds: contract.decisionIds,
      matrixIds: statedIds,
      trdPath: contract.trdPath || null,
    },
  })
  if (!intent || !intent.provisioningIntent) {
    return failed(stageOf('infra-intent', intent), `infra-intent: ${(intent && intent.reason) || 'no provisioning intent was produced'}`)
  }
  return { artifacts: [valueArtifact('provisioning', { provisioningIntent: intent.provisioningIntent, affectedStacks: Array.isArray(intent.affectedStacks) ? intent.affectedStacks : [] })] }
}

/** Prepares the earlier requirements and has the regression-impact-assessor write the scope, or the final mapping of an approved scope. */
async function regressionAssess(step, final) {
  if (final) enterPhase('commit')
  else enterPhase('regression-scope')
  const contract = contractAt(step)
  const plan = final ? REGRESSION_FILES.mapped : REGRESSION_FILES.plan
  const stage = final ? 'regression-coverage' : 'regression-plan'
  const what = final ? 'Required regression evidence failed' : 'Regression scope unresolved'
  const prepared = await regressionInvoke(step, 'prepare', plan, REGRESSION_FILES.previous, [...regressionSources(contract).flatMap(x => ['--source', x]), ...(final ? ['--approved-plan', contract.regressionPlanPath] : [])])
  if (!prepared.ok) return failed(stage, `${what}: ${prepared.reason}`)
  const saved = await author(plan, REGRESSION_SCHEMA, 'regression-impact-assessor', regressionBrief(contract, REGRESSION_FILES.previous, final))
  if (!saved.ok) return failed(saved.noResult ? DISPATCH_FAILED_STAGE : stage, `${what}: ${saved.error}`)
  return { artifacts: [fileArtifact('regressionPrevious', REGRESSION_FILES.previous), fileArtifact(final ? 'regressionMapped' : 'regressionPlan', plan)] }
}
/** Has the regression-coverage-reviewer review the scope, or the final mapping. */
async function regressionReview(step, final) {
  if (final) enterPhase('commit')
  else enterPhase('regression-scope')
  const plan = J.latest(final ? 'regressionMapped' : 'regressionPlan', step)
  const previous = J.latest('regressionPrevious', step)
  const review = final ? REGRESSION_FILES.mappedReview : REGRESSION_FILES.planReview
  const stage = final ? 'regression-coverage' : 'regression-plan'
  const what = final ? 'Required regression evidence failed' : 'Regression scope unresolved'
  if (!plan || !previous) return failed(stage, `${what}: the journal names no ${final ? 'regression mapping' : 'regression scope'} to review`)
  const checked = await author(review, REGRESSION_REVIEW_SCHEMA, 'regression-coverage-reviewer', regressionReviewBrief(plan, previous, final))
  if (!checked.ok) return failed(checked.noResult ? DISPATCH_FAILED_STAGE : stage, `${what}: ${checked.error}`)
  return { artifacts: [fileArtifact(final ? 'regressionMappedReview' : 'regressionPlanReview', review)] }
}
async function stepRegressionValidate(step) {
  enterPhase('regression-scope')
  const plan = J.latest('regressionPlan', step)
  const review = J.latest('regressionPlanReview', step)
  if (!plan || !review) return failed('regression-plan', 'Regression scope unresolved: the journal names no reviewed regression scope to validate')
  const validated = await regressionInvoke(step, 'validate', plan, `${REGRESSION_DIR}/validate.json`, ['--review', review])
  if (!validated.ok) return failed('regression-plan', `Regression scope unresolved: ${validated.reason || JSON.stringify(validated.errors)}`)
  return { artifacts: [valueArtifact('regressionScope', { requiredKinds: list(validated.requiredKinds) })] }
}
async function stepRegressionVerify(step) {
  enterPhase('commit')
  const approved = J.latest('regressionPlan', step)
  const mapped = J.latest('regressionMapped', step)
  const review = J.latest('regressionMappedReview', step)
  if (!approved || !mapped || !review) return failed('regression-coverage', 'Required regression evidence failed: the journal names no reviewed regression mapping to verify')
  const output = `${REGRESSION_DIR}/verify.json`
  const verified = await regressionInvoke(step, 'verify', mapped, output, ['--review', review, '--approved-plan', approved])
  if (!verified.ok) return failed('regression-coverage', `Required regression evidence failed: ${verified.reason || JSON.stringify(verified.errors)}`)
  return { artifacts: [fileArtifact('regressionEvidence', output)] }
}

async function stepBaseline(step) {
  enterPhase('baseline')
  const baseline = await suite(step, 'baseline')
  if (baseline && baseline.resolveError) {
    return failed('baseline', `baseline: ${treeAt(step)} declares no test command (${baseline.resolveError}). A Task is committed only when the repository's whole suite passes, so the repository must say how its suite runs.`, {
      requiredHumanActions: [`declare the command that runs the whole test suite in the AGENTS.md or CLAUDE.md of the repository at ${bead.repoPath}, or as the \`test\` task in its Taskfile`],
    })
  }
  if (!validRun(baseline) || !String(baseline.command || '').trim()) {
    return failed(stageOf('baseline', baseline), `baseline: the suite runner returned no exit code: ${(baseline && baseline.reason) || 'no result'}`)
  }
  const planned = await settleWorkflow('agent-teams-workforce:tdd-red', { contract: contractAt(step), plan: true })
  const testAgents = list(planned && planned.testAgents).map(String)
  if (!testAgents.length) return failed(stageOf('red', planned), 'red: the Red workflow script named no test agent for this contract')
  log(`Baseline: \`${baseline.command}\` exited ${baseline.exitCode}; ${failingIds(baseline).size} failing before any change`)
  return {
    artifacts: [valueArtifact('suiteCommand', String(baseline.command).trim()), valueArtifact('baseline', runValue(baseline))],
    add: [...testAgents.map((testAgent) => ({ kind: 'build:red-write', params: { testAgent, testAgents } })), { kind: 'build:red-check' }],
  }
}

async function stepRedWrite(step) {
  enterPhase('red')
  const lastCheck = J.latest('redRun', step)
  const prior = testFilesAt(step)
  const red = await settleWorkflow('agent-teams-workforce:tdd-red', {
    contract: contractAt(step),
    testAgent: step.params.testAgent,
    feedback: lastCheck ? `The suite does not show Red yet: ${list(lastCheck.reasons).join('; ')}.\n${runText(lastCheck)}` : '',
    ...(prior.length ? { red: { testFiles: prior } } : {}),
  })
  if (!red || red.dispatchFailed) return failed(stageOf('red', red), `red: ${(red && red.reason) || 'the test agent returned nothing'}`)
  return { artifacts: [valueArtifact('testFiles', list(red.testFiles).map(String)), valueArtifact('redConfirmed', red.redConfirmed === true)] }
}

async function stepRedCheck(step) {
  enterPhase('red')
  const tree = treeAt(step)
  const redFiles = testFilesAt(step)
  const baselineIds = failingIds(J.latest('baseline', step))
  const run = await suite(step, 'red')
  if (!validRun(run)) return failed(stageOf('red', run), `red: the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`)
  const inRedFile = (e) => redFiles.some((f) => sameFile(e.file, f))
  const fresh = [...failures(run).entries()].filter(([id]) => !baselineIds.has(id)).map(([, e]) => e)
  const collection = fresh.filter((e) => e.kind === 'load').map(describe)
  const redFails = fresh.filter((e) => e.kind === 'test' && inRedFile(e)).map(describe)
  const regressions = fresh.filter((e) => e.kind === 'test' && !inRedFile(e)).map(describe)
  const reasons = [
    redFails.length ? '' : 'no test in a file Red wrote or edited fails',
    collection.length ? `test files that no longer load: ${collection.join('; ')}` : '',
    regressions.length ? `tests outside Red's files that did not fail at baseline now fail: ${regressions.join('; ')}` : '',
  ].filter(Boolean)
  const held = { ...runValue(run), reasons }
  if (run.exitCode !== 0 && !reasons.length) {
    const print = await fingerprint(tree, redFiles, 'tests')
    if (print.error) return failed('red', `red: Red's test files could not be fingerprinted: ${print.error}`)
    log(`Red: satisfied — ${redFails.length} new failing test(s) in Red's files`)
    return { artifacts: [valueArtifact('redRun', held), valueArtifact('testPrint', { files: print.files, treeDigest: print.treeDigest })] }
  }
  const why = reasons.join('; ') || 'the suite exits 0, so no new test fails'
  log(`Red: not satisfied — ${why}`)
  const checks = J.earlier(['build:red-check'], step).length + 1
  if (checks >= MAX_RED_CHECKS) {
    return failed('red-unsatisfied', `red-unsatisfied: after ${checks} Red check(s) the suite does not show the Task's new tests failing cleanly: ${why}`, { evidence: runText(run).slice(0, TAIL_CHARS) })
  }
  // A check whose suite fails exactly as at the check before gives the test agents the same input again.
  const before = J.latest('redRun', step)
  const keyOf = (r) => JSON.stringify([r.exitCode, ...[...failingIds(r)].sort(), ...list(r.reasons)])
  if (before && keyOf(before) === keyOf(held)) {
    return failed('no-progress', `no-progress: the test agents left the suite exactly as it was at the check before: ${why}`, { evidence: runText(run).slice(0, TAIL_CHARS) })
  }
  const lastWrite = J.earlier(['build:red-write'], step).pop()
  const testAgents = list(lastWrite && lastWrite.params.testAgents).map(String)
  if (!testAgents.length) return failed('red', 'red: the journal names no test agent to give the suite result to')
  const purpose = `Red does not hold: ${why}`.slice(0, 600)
  return {
    artifacts: [valueArtifact('redRun', held)],
    add: [...testAgents.map((testAgent) => ({ kind: 'build:red-write', params: { testAgent, testAgents }, purpose })), { kind: 'build:red-check', purpose }],
  }
}

/** One capability of `atw-matrix uses` as the implementers are handed it: its name, the behaviours relied on, and what provides it. */
const capabilityBrief = (capability) => {
  const feature = capability && capability.feature && typeof capability.feature === 'object' ? capability.feature : {}
  const relied = list(capability && capability.relies).map(String)
  return {
    id: String(feature.id || ''),
    name: String(feature.name || ''),
    provides: list(feature.provides)
      .filter((entry) => entry && typeof entry === 'object' && (!relied.length || relied.includes(String(entry.id))))
      .map((entry) => ({ id: String(entry.id || ''), behaviour: String(entry.behaviour || ''), consumersMust: String(entry.consumersMust || ''), interface: entry.interface || null })),
    providedBy: list(capability && capability.providers)
      .filter((row) => row && row.entry && typeof row.entry === 'object')
      .map((row) => ({ name: String(row.entry.name || ''), kind: String(row.entry.kind || ''), repository: (row.stack && row.stack.repository) || null })),
  }
}

/** The steps that give each implementer its work and then judge the suite. */
const implementerSteps = (implementers, brief, purpose) => [
  ...implementers.map((implementer) => ({ kind: 'build:implement', params: { implementer, implementers, brief }, ...(purpose ? { purpose } : {}) })),
  { kind: 'build:green-check', ...(purpose ? { purpose } : {}) },
]

async function stepSelectImplementers(step) {
  enterPhase('green')
  // A Task that states no matrix id names no shared capability to read, and the build goes on without one.
  const uses = statedIds.length ? await matrixCommand('shared-capabilities', ['uses', '--ids', ...statedIds], ['capabilities']) : { out: { capabilities: [] } }
  if (uses.error || !Array.isArray(uses.out.capabilities)) {
    return failed('green', `green: the shared capabilities ${bead.id} must use could not be read with atw-matrix uses: ${uses.error || 'it printed no capabilities list'}`)
  }
  const sharedCapabilities = uses.out.capabilities.map(capabilityBrief)
  log(`Green: ${bead.id} must use ${sharedCapabilities.length} shared capability(ies)${sharedCapabilities.length ? `: ${sharedCapabilities.map((x) => x.name).join(', ')}` : ''}`)
  const selection = await settleWorkflow('agent-teams-workforce:tdd-green', {
    contract: { ...contractAt(step), sharedCapabilities },
    red: redFor(step),
    implementer: a.implementer || (isInfra ? 'cdk-stack-author' : undefined),
    select: true,
    feedback: greenFeedbackAt(step),
  })
  const implementers = list(selection && selection.implementers).map(String)
  if (!selection || selection.dispatchFailed || !implementers.length) {
    return failed(stageOf('green', selection), `green: ${(selection && selection.reason) || 'the implementer selection returned nothing'}`)
  }
  return { artifacts: [valueArtifact('implementers', implementers), valueArtifact('sharedCapabilities', sharedCapabilities)], add: implementerSteps(implementers, 'green', '') }
}

async function stepImplement(step) {
  enterPhase('green')
  const what = Object.values(AUDIT_BRIEF).includes(step.params.brief) ? `green (${step.params.brief} audit)` : 'green'
  const g = await settleWorkflow('agent-teams-workforce:tdd-green', {
    contract: contractAt(step),
    red: redFor(step),
    implementers: list(step.params.implementers),
    only: step.params.implementer,
    feedback: greenFeedbackAt(step),
  })
  if (!g || g.dispatchFailed) return failed(stageOf('green', g), `${what}: ${(g && g.reason) || 'the implementer returned nothing'}`)
  return { artifacts: [valueArtifact('changedFiles', list(g.changedFiles).map(String)), valueArtifact('testIssues', list(g.testIssues)), valueArtifact('upstreamMissing', list(g.upstreamMissing))] }
}

async function stepGreenCheck(step) {
  enterPhase('green')
  const tree = treeAt(step)
  const boundary = greenBoundary(step)
  const answered = auditOf(boundary)
  const afterAudit = !!answered
  const what = afterAudit ? `green (${answered} audit)` : 'green'
  const previous = J.earlier(['build:green-check'], step, boundary).pop() || null
  const since = previous || boundary
  const implemented = J.earlier(['build:implement'], step, since)
  const ruled = J.earlier(['build:test-ruling'], step, since).length > 0
  const print = J.latest('testPrint', step)
  const redFiles = testFilesAt(step)
  const after = await fingerprint(tree, redFiles, 'tests')
  if (after.error) return failed('green', `${what}: Red's test files could not be fingerprinted: ${after.error}`)
  // An implementer leaves the tests to the test agents: a test file whose content changed while implementers worked stops the build.
  if (implemented.length && !ruled && print && print.files) {
    const touchedTests = Object.keys(print.files).filter((f) => f in after.files && print.files[f] !== after.files[f])
    if (touchedTests.length) {
      return failed('green-modified-tests', `green-modified-tests: ${what} changed test files Red wrote, which the implementers leave to the test agents (a test an implementer believes is wrong goes in testIssues): ${touchedTests.join(', ')}`)
    }
  }
  const run = await suite(step, 'green')
  if (!validRun(run)) return failed(stageOf('green', run), `${what}: the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`)
  const held = runValue(run)
  const artifacts = [valueArtifact('greenRun', held), valueArtifact('testPrint', { files: after.files, treeDigest: after.treeDigest })]
  const upstream = J.every('upstreamMissing', step, since).flatMap((entries) => list(entries))
  if (run.exitCode === 0) {
    if (afterAudit && upstream.length) {
      return failed('blocked-upstream', `blocked-upstream: the ${answered} audit violations cannot be fixed until something outside this Task exists: ${upstream.map((u) => u.what).join('; ')}`, { upstreamMissing: upstream })
    }
    return { artifacts }
  }
  if (upstream.length) {
    return failed('blocked-upstream', `blocked-upstream: the suite cannot pass until something outside this Task exists: ${upstream.map((u) => u.what).join('; ')}`, { upstreamMissing: upstream, evidence: runText(held).slice(0, TAIL_CHARS) })
  }
  const issues = J.every('testIssues', step, since).flatMap((entries) => list(entries))
  if (issues.length) {
    const purpose = `The suite is not green and the implementers named ${issues.length} test(s) that stand between the code and the contract`
    return { artifacts, add: [{ kind: 'build:test-ruling', params: { issues }, purpose }, { kind: 'build:green-check', purpose: 'The test agent ruled on the tests the implementers named' }] }
  }
  // Whether the implementers changed any file is read from the work tree (its digest before and after), not from their reports.
  const keyOf = (r) => JSON.stringify([r.exitCode, ...[...failingIds(r)].sort()])
  const changedNothing = !!print && !!print.treeDigest && print.treeDigest === after.treeDigest && !ruled
  const before = previous ? J.latest('greenRun', step) : null
  if (changedNothing && before && keyOf(before) === keyOf(held)) {
    return failed('no-progress', `no-progress: ${what} changed no file and the suite fails exactly as it did at the check before`, { evidence: runText(held).slice(0, TAIL_CHARS) })
  }
  const checks = J.earlier(['build:green-check'], step, boundary).length + 1
  if (checks >= MAX_GREEN_CHECKS) {
    return failed('green', `${what}: the suite is not green after ${checks} check(s): ${held.summary || `exit ${held.exitCode}`}`, { evidence: runText(held).slice(0, TAIL_CHARS) })
  }
  const implementers = list(J.latest('implementers', step)).map(String)
  if (!implementers.length) return failed('green', `${what}: the journal names no implementer to give the suite result to`)
  return { artifacts, add: implementerSteps(implementers, answered || 'green', `The suite is not green: ${held.summary || `exit ${held.exitCode}`}`.slice(0, 600)) }
}

async function stepTestRuling(step) {
  enterPhase('red')
  const issues = list(step.params.issues)
  const updated = await settleWorkflow('agent-teams-workforce:tdd-red', {
    contract: contractAt(step),
    testIssues: issues,
    red: { testFiles: testFilesAt(step) },
    feedback: runText(J.latest('greenRun', step)),
  })
  if (!updated || updated.dispatchFailed) return failed(stageOf('red', updated), `red (update): ${(updated && updated.reason) || 'the test ruling returned nothing'}`)
  const rulingCheck = checkTestDecisions(issues, updated.decisions)
  if (rulingCheck.problems.length) {
    return failed('red-decisions-incomplete', `red (update): ${rulingCheck.problems.join('; ')}; return one justified disposition for each requested test ID before the implementers continue`)
  }
  return { artifacts: [valueArtifact('testDecisions', rulingCheck.decisions), valueArtifact('testFiles', list(updated.testFiles).map(String))] }
}

async function stepRefactorSnapshot(step) {
  enterPhase('refactor')
  const snap = await gitutils('refactor-snapshot', ['snapshot', '--tree', treeAt(step)])
  const tree = snap.error ? '' : String(snap.facts.tree || '').trim()
  if (!tree) return failed('refactor', `refactor: the pre-refactor snapshot could not be recorded: ${snap.error || 'gitutils.py snapshot named no tree'}`)
  return { artifacts: [valueArtifact('refactorSnapshot', tree)] }
}

async function stepRefactor(step) {
  enterPhase('refactor')
  const snapshot = String(J.latest('refactorSnapshot', step, '') || '').trim()
  if (!snapshot) return failed('refactor', 'refactor: the journal holds no pre-refactor snapshot, so nothing was refactored')
  const refactor = await settleWorkflow('agent-teams-workforce:tdd-refactor', { contract: contractAt(step), green: { changedFiles: changedFilesAt(step) }, snapshotTree: snapshot, relay: stepRelay() })
  if (!refactor || refactor.dispatchFailed) return failed(stageOf('refactor', refactor), `refactor: ${(refactor && refactor.reason) || 'the refactor returned nothing'}`)
  return {
    artifacts: [
      valueArtifact('refactorChangedFiles', list(refactor.changedFiles).map(String)),
      valueArtifact('refactorReverted', refactor.restored === true),
    ],
  }
}

async function stepRefactorCheck(step) {
  enterPhase('refactor')
  const run = await suite(step, 'refactor')
  if (!validRun(run)) return failed(stageOf('refactor', run), `refactor: the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`)
  const held = runValue(run)
  if (run.exitCode !== 0) {
    const snapshot = String(J.latest('refactorSnapshot', step, '') || '').trim()
    if (J.latest('refactorRestored', step)) {
      return failed('refactor', `refactor: the suite is red after restoring the pre-refactor snapshot ${snapshot}: ${held.summary || `exit ${held.exitCode}`}`, { evidence: runText(held).slice(0, TAIL_CHARS) })
    }
    if (!snapshot) {
      return failed('refactor', `refactor: the suite is red after the refactor and the refactor recorded no snapshot to restore: ${held.summary || `exit ${held.exitCode}`}`)
    }
    const purpose = `The suite is red after the refactor: ${held.summary || `exit ${held.exitCode}`}`.slice(0, 600)
    return { artifacts: [valueArtifact('refactorRun', held)], add: [{ kind: 'build:refactor-restore', purpose }, { kind: 'build:refactor-check', purpose: 'The work tree was restored to the snapshot taken before the refactor' }] }
  }
  const audits = isUiTask && designAt(step).designSource !== DESIGN_SOURCE.NONE
  return { artifacts: [valueArtifact('refactorRun', held)], add: audits ? [{ kind: 'build:cds-audit' }] : [] }
}

async function stepRefactorRestore(step) {
  enterPhase('refactor')
  const snapshot = String(J.latest('refactorSnapshot', step, '') || '').trim()
  const restored = await settleWorkflow('agent-teams-workforce:tdd-refactor', { contract: contractAt(step), restoreTo: snapshot, relay: stepRelay() })
  if (!restored || restored.dispatchFailed || restored.restored !== true) {
    return failed(stageOf('refactor', restored), `refactor: the suite is red after the refactor and the tree could not be restored to ${snapshot}`)
  }
  log(`Refactor: the suite went red, so the tree was restored to ${snapshot}`)
  return { artifacts: [valueArtifact('refactorRestored', { restored: true, evidence: String(restored.evidence || '') })] }
}

async function stepCdsAudit(step) {
  enterPhase('cds-audit')
  const tree = treeAt(step)
  const design = designAt(step)
  const bundle = design.designSource === DESIGN_SOURCE.BUNDLE ? design.bundle : null
  const first = !J.earlier(['build:cds-audit'], step).length
  const audit = bundle ? await auditCds(tree, bundle, 'cds-audit') : await auditCdsLive(tree, 'cds-audit')
  if (audit.error) {
    return failed('cds-audit', `cds-audit: the cds audit ${first ? 'after Refactor' : 'after the implementers answered it'} could not rule: ${audit.error}`, { cdsAudit: { verdict: 'error', findings: 0, scriptVersion: audit.scriptVersion || null } })
  }
  log(`CDS Audit: ${audit.violations.length} violation(s), ${audit.gaps.length} cds gap(s), ${audit.allowed.length} allowed`)
  const verdict = {
    verdict: audit.violations.length ? 'fail' : audit.gaps.length ? 'blocked' : 'pass',
    findings: audit.violations.length + audit.gaps.length,
    scriptVersion: audit.scriptVersion,
  }
  const held = { ...verdict, violations: audit.violations.map(findingText), gaps: audit.gaps.map(findingText) }
  if (audit.violations.length) {
    if (!first) {
      return failed('cds-audit', `cds-audit: ${audit.violations.length} cds violation(s) remain after the implementers answered the audit: ${audit.violations.slice(0, 5).map(findingText).join('; ')}`, {
        cdsAudit: verdict,
        evidence: audit.violations.map(findingText).join('\n').slice(0, TAIL_CHARS),
      })
    }
    const implementers = list(J.latest('implementers', step)).map(String)
    if (!implementers.length) return failed('cds-audit', 'cds-audit: the journal names no implementer to give the violations to', { cdsAudit: verdict })
    const purpose = `The cds audit found ${audit.violations.length} violation(s)`
    return { artifacts: [valueArtifact('cdsAudit', held)], add: [...implementerSteps(implementers, 'cds', purpose), { kind: 'build:cds-audit', purpose: 'The implementers answered the violations the audit found' }] }
  }
  if (audit.gaps.length) {
    const upstream = audit.gaps.map((f) => ({ what: `cds: ${f.reason || f.value} (${f.file}:${f.line})` }))
    return failed('blocked-upstream', `blocked-upstream: required cds configuration, design artifacts or capabilities remain unresolved: ${audit.gaps.map(findingText).join('; ')}`, {
      upstreamMissing: upstream,
      cdsAudit: verdict,
      evidence: audit.gaps.map(findingText).join('\n').slice(0, TAIL_CHARS),
    })
  }
  return { artifacts: [valueArtifact('cdsAudit', held)] }
}

/** One finding of atw-matrix check-reuse as text: where it is, what it is, and the capability and behaviour it concerns. */
const reuseText = (f) => `${f.file ? `${f.file}${f.line ? `:${f.line}` : ''} ` : ''}${f.finding} ${f.feature} ${f.provides}: ${f.detail}`

const REUSE_JUDGMENT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['rulings'],
  properties: {
    rulings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'feature', 'provides', 'ruling', 'reason'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          feature: { type: 'string' },
          provides: { type: 'string' },
          ruling: { type: 'string', enum: ['duplicate', 'not-duplicate'] },
          reason: { type: 'string' },
        },
      },
    },
  },
}

/** One definition the shared-capability-reviewer ruled on, as text: the finding, then the ruling and its reason. */
const ruledText = (f) => `${reuseText(f)} (${f.ruling}: ${f.reason})`

/** Has the shared-capability-reviewer rule each definition atw-matrix check-reuse could not rule on; returns { duplicates, cleared } or { error }. */
async function judgeReuse(tree, items) {
  let judged = null
  try {
    judged = await guardedAgent(
      `Items, in the work tree at ${tree}, one per line (file:line, the finding, the capability, its provides entry, then the definition, the words it shares and the provided behaviour):
${items.map(reuseText).join('\n')}`,
      { agentType: 'shared-capability-reviewer', label: 'reuse-audit:judge', phase: currentPhase || phaseTitle('reuse-audit'), schema: REUSE_JUDGMENT_SCHEMA }
    )
  } catch (err) {
    return { error: `the ruling on ${items.length} definition(s) threw: ${String((err && err.message) || err).slice(0, 300)}` }
  }
  const rulings = list(judged && judged.rulings)
  const ruled = items.map((f) => {
    const r = rulings.find((x) => x && x.file === f.file && Number(x.line) === Number(f.line) && x.feature === f.feature && x.provides === f.provides)
    return r ? { ...f, ruling: r.ruling, reason: r.reason } : f
  })
  const unruled = ruled.filter((f) => !f.ruling)
  if (unruled.length) return { error: `shared-capability-reviewer returned no ruling on ${unruled.length} definition(s): ${unruled.slice(0, 5).map(reuseText).join('; ')}` }
  return { duplicates: ruled.filter((f) => f.ruling === 'duplicate'), cleared: ruled.filter((f) => f.ruling !== 'duplicate') }
}

async function stepReuseAudit(step) {
  enterPhase('reuse-audit')
  const first = !J.earlier(['build:reuse-audit'], step).length
  if (!statedIds.length) {
    log(`Reuse Audit: ${bead.id} states no matrix id, so it uses no shared capability to check the changed files against`)
    return { artifacts: [valueArtifact('reuseAudit', { clean: true, violations: [], judgment: [], unchecked: [] })] }
  }
  const checked = await matrixCommand('reuse-audit', ['check-reuse', '--ids', ...statedIds, '--worktree', treeAt(step)], ['violations', 'judgment', 'unchecked', 'clean'])
  if (checked.error || !Array.isArray(checked.out.violations) || typeof checked.out.clean !== 'boolean') {
    return failed('reuse-audit', `reuse-audit: atw-matrix check-reuse ${first ? 'after Green' : 'after the implementers answered it'} could not rule: ${checked.error || 'it printed no violations list'}`)
  }
  const toJudge = list(checked.out.judgment).filter((f) => f && typeof f === 'object')
  const judged = toJudge.length ? await judgeReuse(treeAt(step), toJudge) : { duplicates: [], cleared: [] }
  if (judged.error) return failed('reuse-audit', `reuse-audit: ${judged.error}`)
  const violations = [...checked.out.violations.map(reuseText), ...judged.duplicates.map(ruledText)]
  const held = { clean: !violations.length, violations, judgment: [...judged.duplicates, ...judged.cleared].map(ruledText), unchecked: list(checked.out.unchecked).map(String) }
  log(`Reuse Audit: ${violations.length} violation(s), ${judged.duplicates.length} of ${toJudge.length} definition(s) ruled a duplicate, ${held.unchecked.length} relied-on behaviour(s) with no use signal`)
  if (!violations.length) return { artifacts: [valueArtifact('reuseAudit', held)] }
  if (!first) {
    return failed('reuse-violation', `reuse-violation: ${violations.length} reuse violation(s) remain after the implementers answered the audit: ${violations.slice(0, 5).join('; ')}`, {
      reuseAudit: held,
      evidence: violations.join('\n').slice(0, TAIL_CHARS),
    })
  }
  const implementers = list(J.latest('implementers', step)).map(String)
  if (!implementers.length) return failed('reuse-audit', 'reuse-audit: the journal names no implementer to give the violations to', { reuseAudit: held })
  const purpose = `The reuse audit found ${violations.length} violation(s)`
  return { artifacts: [valueArtifact('reuseAudit', held)], add: [...implementerSteps(implementers, 'reuse', purpose), { kind: 'build:reuse-audit', purpose: 'The implementers answered the violations the audit found' }] }
}

/** Every file the Task changed so far: the implementers' and the refactor's. */
const allChangedAt = (step) => [...new Set([...changedFilesAt(step), ...list(J.latest('refactorChangedFiles', step)).map(String)])]

async function stepDocsAudit(step) {
  enterPhase('documentation')
  const docs = await settleWorkflow('agent-teams-workforce:documentation', { contract: contractAt(step), green: { changedFiles: allChangedAt(step) }, auditOnly: true })
  if (!docs || docs.dispatchFailed) return failed(DISPATCH_FAILED_STAGE, `documentation: ${(docs && docs.reason) || 'the documentation audit returned nothing'}`)
  const assignments = list(docs.assignments).filter((x) => x && x.agent && list(x.docs).length)
  return {
    artifacts: [valueArtifact('staleDocs', list(docs.staleDocs).map(String)), valueArtifact('docAssignments', assignments)],
    add: assignments.map((x) => ({ kind: 'build:docs-write', params: { docAgent: String(x.agent), docs: list(x.docs).map(String) }, purpose: `The audit named ${list(x.docs).length} stale document(s) this agent owns` })),
  }
}

async function stepDocsWrite(step) {
  enterPhase('documentation')
  const out = await settleWorkflow('agent-teams-workforce:documentation', {
    contract: contractAt(step),
    green: { changedFiles: allChangedAt(step) },
    assignment: { agent: step.params.docAgent, docs: list(step.params.docs) },
  })
  if (!out || out.dispatchFailed) return failed(DISPATCH_FAILED_STAGE, `documentation: ${(out && out.reason) || `${step.params.docAgent} returned nothing`}`)
  return { artifacts: [valueArtifact('updatedDocs', list(out.updatedDocs).map(String))] }
}

async function stepFinalSuite(step) {
  enterPhase('commit')
  const run = await suite(step, 'final')
  if (!validRun(run) || run.exitCode !== 0) {
    return failed(stageOf('commit', run), `commit: the final suite run did not exit 0 (${(run && (run.summary || `exit ${run.exitCode}`)) || 'no result'}), so nothing was committed`, validRun(run) ? { evidence: runText(runValue(run)).slice(0, TAIL_CHARS) } : {})
  }
  return { artifacts: [valueArtifact('finalRun', runValue(run))] }
}

async function stepCommit(step) {
  enterPhase('commit')
  const committed = await settleWorkflow('agent-teams-workforce:settle', {
    repoPath: treeAt(step),
    commitOnly: true,
    branch: J.latest('branch', step) || null,
    defaultBranch: J.latest('defaultBranch', step) || null,
    message: `${bead.id} ${bead.title || ''}`.trim(),
    relay: stepRelay(),
  })
  if (!committed || committed.status !== 'reported' || (Array.isArray(committed.blocked) && committed.blocked.length)) {
    const why =
      (committed && (committed.error || committed.reason || (Array.isArray(committed.blocked) && committed.blocked.join('; ')))) ||
      'the commit step returned nothing'
    return failed(!committed || committed.status === 'error' ? DISPATCH_FAILED_STAGE : 'commit', `commit: ${why}`)
  }
  return { artifacts: [valueArtifact('commit', committed.commit || null)] }
}

// The function that runs a step of each kind. A later kind is one entry here, its function, and its entry
// in pipeline-steps.json.
const STEPS = {
  'build:workspace': stepWorkspace,
  'build:design-source': stepDesignSource,
  'build:infra-intent': stepInfraIntent,
  'build:regression-assess': (step) => regressionAssess(step, false),
  'build:regression-review': (step) => regressionReview(step, false),
  'build:regression-validate': stepRegressionValidate,
  'build:baseline': stepBaseline,
  'build:red-write': stepRedWrite,
  'build:red-check': stepRedCheck,
  'build:select-implementers': stepSelectImplementers,
  'build:implement': stepImplement,
  'build:green-check': stepGreenCheck,
  'build:test-ruling': stepTestRuling,
  'build:reuse-audit': stepReuseAudit,
  'build:refactor-snapshot': stepRefactorSnapshot,
  'build:refactor': stepRefactor,
  'build:refactor-check': stepRefactorCheck,
  'build:refactor-restore': stepRefactorRestore,
  'build:cds-audit': stepCdsAudit,
  'build:docs-audit': stepDocsAudit,
  'build:docs-write': stepDocsWrite,
  'build:final-suite': stepFinalSuite,
  'build:regression-map': (step) => regressionAssess(step, true),
  'build:regression-map-review': (step) => regressionReview(step, true),
  'build:regression-verify': stepRegressionVerify,
  'build:commit': stepCommit,
}
const stepTable = Object.fromEntries(
  Object.entries(STEPS).map(([kind, perform]) => [
    kind,
    async (step) => {
      current = step
      return perform(step)
    },
  ])
)

/** The caller-facing result, read from the journal as the run left it. */
function handback(ok, stage, headline, more) {
  const design = isUiTask ? designAt(null) : null
  const audit = J.latest('cdsAudit', null)
  const cdsAudit = (more && more.cdsAudit) || (audit ? { verdict: audit.verdict, findings: audit.findings, scriptVersion: audit.scriptVersion } : null)
  return {
    ok,
    stage,
    beadId: bead.id || null,
    storyId: story.id || null,
    headline: String(headline || ''),
    detailPath: null,
    branch: J.latest('branch', null) || null,
    worktree: J.latest('worktree', null) || null,
    ...(design && design.designSource ? { designSource: design.designSource } : {}),
    ...(more || {}),
    ...(cdsAudit ? { cdsAudit: { ...cdsAudit, designSource: design ? design.designSource : null, bundle: design ? design.bundle : null } } : {}),
  }
}

let result
try {
  const read = await stepJournal.read(guardedAgent, { runner: RELAY.runner, pluginRoot, path: journalPath, relayFile: relayFileIn(`${RELAY.dir}/journal`, `read-${runName}`), phase: phaseTitle('workspace') })
  if (read.error) {
    result = { ...inputFailure(`the step journal ${journalPath} could not be read: ${read.error}`), stage: read.noResult ? DISPATCH_FAILED_STAGE : 'journal' }
  } else {
    J = stepJournal.open({ journal: read.journal, run: runName, runner: COMPOSITE })
    log(`Journal: ${J.steps().filter((s) => s.status === 'done').length} of ${J.steps().length} step(s) done; ${J.next() ? `beginning at "${J.next().description}"` : 'no step is left to run'}`)
    const ran = await J.run(stepTable, () => dispatchInterruption)
    if (!ran.ok) {
      const { stage, message, interrupted: _interrupted, ...more } = ran.fail
      // A failure while implementers answer an audit leaves the audit's verdict as it stands: failed, or blocked upstream.
      const answering = ['build:implement', 'build:green-check', 'build:test-ruling'].includes(ran.step.kind)
      const boundary = answering ? greenBoundary(ran.step) : null
      const audit = boundary && boundary.kind === 'build:cds-audit' && !more.cdsAudit ? J.latest('cdsAudit', ran.step) : null
      result = handback(false, stage, message, {
        ...more,
        ...(audit ? { cdsAudit: { verdict: stage === 'blocked-upstream' ? 'blocked' : 'fail', findings: list(audit.violations).length, scriptVersion: audit.scriptVersion } } : {}),
        step: ran.step.key,
      })
    } else {
      const finalRun = J.latest('finalRun', null) || {}
      const suiteCommand = String(J.latest('suiteCommand', null, '') || '')
      const commit = J.latest('commit', null) || null
      result = {
        ...handback(true, 'committed', `${bead.id} built on ${J.latest('branch', null)}: \`${suiteCommand}\` exits 0${finalRun.summary ? ` (${finalRun.summary})` : ''} and the work is committed to the branch of Story ${story.id} (${commit || 'no new commit'}).`),
        commit,
        suite: { command: suiteCommand, summary: finalRun.summary || '' },
      }
    }
  }
} catch (err) {
  const message = String((err && err.message) || err)
  const environmental = /overload|rate[ _-]?limit|too many requests|quota|capacity|session limit|usage limit|spend limit|credit balance|out of credits|timed? ?out|network/i.test(message)
  const where = currentPhase || 'unknown'
  const slug = String(where).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown'
  log(`RUN ABORTED in ${where}: ${message.slice(0, 300)}`)
  result = { ...inputFailure(`${where}: the run threw — ${message.slice(0, 300)}`), stage: environmental ? DISPATCH_FAILED_STAGE : slug, dispatchFailed: environmental }
}
return dispatchOutcome(result)

async function guardedAgent(prompt, options) {
  if (dispatchInterruption) return null
  try { return await fableAgent(prompt, options) } catch (err) {
    const plan = dispatchRetry(err, (options && options.label) || 'agent', 1, 0, dispatchPolicy(options), false)
    if (plan.interruption) dispatchInterruption = plan.interruption
    throw err
  }
}
