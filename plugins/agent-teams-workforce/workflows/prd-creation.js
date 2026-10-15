export const meta = {
  name: 'prd-creation',
  description:
    'Leaf mini — turns a raw stakeholder request into a template-conformant PRD paired with its Epic. Intake captures the request, then the persona and OKRs are authored in parallel, then the PRD is drafted (WHAT-not-HOW) and independently checked for alignment with the intake brief, persona, and OKRs. A PRD and its Epic are created at the same time, so the mini emits exactly one Epic per PRD: a container bead spec derived from the PRD itself in the same authoring pass — no acceptance criteria, no repo scope (one Epic may span repos) — which the caller writes with bd. The matrix is the one record of the pair: the result carries the command that records it (atw-matrix sync-epics --bead <id> --prd <path>), which the caller runs once the Epic bead exists and the PRD file is written. Maker, checker, and decider are distinct agents; the maker is re-run with checker feedback on reject (bounded 2 passes) and a spec-decider rules on deadlock. Authors no judgment of its own work.',
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
const DRIVER_SURFACE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"agent-teams-workforce/skills/pipeline-contracts/schemas/driver-surface.schema.json","title":"Driver module surface","description":"The one definition of the driver (ops/sdlc-automation in the control repository) surface the plugin orchestrator imports, the ATW_* environment the driver hands every child and orchestrator process, and the Claude CLI rate-limit event the driver's quota readers take. scripts/generate_types.py renders scripts/driver_surface_types.py from this file; scripts/check_generated.py fails when that module is stale.","x-driver":{"dirParts":["ops","sdlc-automation"],"dirDoc":"Path parts of the driver directory under ATW_CONTROL_REPO.","modules":[{"module":"headlessenv","constant":"HEADLESSENV_MODULE","protocol":"HeadlessEnvironment","doc":"Driver headlessenv module surface consumed by session setup.","members":[{"name":"child_env","kind":"method","params":[["scratch","Path"]],"returns":"dict[str, str]","doc":"Build the subprocess environment: DriverEnvironment over the inherited one."}]},{"module":"fablewall","constant":"FABLEWALL_MODULE","protocol":"FableWall","doc":"Driver fablewall module surface consumed by model fallback.","members":[{"name":"is_refusal","kind":"method","params":[["info","object"]],"returns":"bool","doc":"Return whether a RateLimitInfo is a model-specific refusal."},{"name":"reset_of","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the model-specific reset of a RateLimitInfo, in epoch seconds."}]},{"module":"breaker","constant":"BREAKER_MODULE","protocol":"Breaker","doc":"Driver breaker module surface consumed by quota handling.","members":[{"name":"exhausted_reset","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the latest reset among the exhausted windows, in epoch seconds."}]},{"module":"childproc","constant":"CHILDPROC_MODULE","protocol":"ChildProcess","doc":"Driver childproc module termination policy.","members":[{"name":"TERMINATE_GRACE","kind":"attribute","python":"float","doc":"Seconds a terminated child is given before it is killed."}]}]},"$defs":{"DriverEnvironment":{"description":"The ATW_* and process environment the driver hands child and orchestrator processes.","x-details":"headlessenv.child_env(scratch) returns these keys over the inherited os.environ (atw.environment fills only absent or blank values); the keeper, supervisor and orchestrator dispatch add ATW_STOP_FILE, ATW_EXECUTION_ID and ATW_ORCH_IDLE.","type":"object","x-python":{"typeddict":"DriverEnvironment"},"properties":{"ATW_PROJECT_ROOT":{"type":"string","minLength":1,"description":"Absolute path of the project root.","x-constant":"PROJECT_ROOT_ENV"},"ATW_PRD_EPIC_SYNC":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic sync script.","x-constant":"PRD_EPIC_SYNC_ENV"},"ATW_PRD_EPIC_VERIFY":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic verify script.","x-constant":"PRD_EPIC_VERIFY_ENV"},"ATW_CONTROL_REPO":{"type":"string","minLength":1,"description":"Absolute path of the control repository (SKILLSPOKE_CC, else the driver's repository root). The driver modules live under it at DRIVER_DIR_PARTS.","x-constant":"CONTROL_REPO_ENV"},"ATW_ARCH_PATH":{"type":"string","minLength":1,"description":"The architecture root; set only when the driver knows one. Readers use args.archPath first and fall back to it.","x-constant":"ARCH_PATH_ENV"},"ATW_DESIGN_PACKAGES_DIR":{"type":"string","minLength":1,"description":"The owner's cds design packages directory; optional.","x-constant":"DESIGN_PACKAGES_ENV"},"ATW_PRD_DIR":{"type":"string","minLength":1,"description":"The first PRD root; optional.","x-constant":"PRD_DIR_ENV"},"PATH":{"type":"string","minLength":1,"description":"The controller runtime's bin directory first, de-duplicated.","x-constant":"PATH_ENV"},"TMPDIR":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMPDIR_ENV","x-group":"SCRATCH_ENV_KEYS"},"TMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"TEMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TEMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS":{"type":"string","const":"0","description":"Disables the Claude CLI print-mode background wait.","x-constant":"BACKGROUND_WAIT_KEY","x-const-mapping":"BACKGROUND_WAIT_ENV"},"ATW_STOP_FILE":{"type":"string","minLength":1,"description":"Path of the stop marker file; absent means no stop marker. A consumer touches the file (mode 0o600) to request a drain, or tests whether it exists. It only requests a stop: how a stop is classified belongs to the handback contract.","x-constant":"STOP_FILE_ENV","x-file-mode":"STOP_FILE_MODE"},"ATW_EXECUTION_ID":{"type":"string","minLength":1,"description":"The driver execution id. Required for an orchestrator dispatch; set for a headless workflow session only when its arguments carry an executionId.","x-constant":"EXECUTION_ID_ENV"},"ATW_ORCH_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"3600","description":"Orchestrator idle limit in seconds: a positive finite float. A non-finite or non-positive value is a ValueError.","x-constant":"ORCH_IDLE_ENV","x-default-constant":"ORCH_IDLE_DEFAULT"}},"required":["ATW_PROJECT_ROOT","ATW_PRD_EPIC_SYNC","ATW_PRD_EPIC_VERIFY","ATW_CONTROL_REPO","PATH","TMPDIR","TMP","TEMP","CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"],"additionalProperties":{"type":"string"}},"StopFileMode":{"description":"Permission bits a consumer creates the stop marker file with.","type":"integer","const":384,"x-python":{"constant":"STOP_FILE_MODE","type":"int","render":"0o600"}},"TerminateGrace":{"description":"Seconds a terminated child process is given before it is killed.","type":"number","const":10,"x-python":{"constant":"TERMINATE_GRACE","type":"float"}},"ExhaustedUtilization":{"description":"A usage window whose utilization is at or above this value is exhausted.","type":"number","const":1,"x-python":{"constant":"EXHAUSTED_UTILIZATION","type":"float"}},"RateLimitStatus":{"description":"RateLimitInfo.status; only rejected is acted on.","type":"string","enum":["allowed","allowed_warning","rejected"],"x-python":{"literal":"RateLimitStatus","tuple":"RATE_LIMIT_STATUSES","constants":{"rejected":"REJECTED_STATUS"}}},"UsageWindowName":{"description":"The account-wide usage windows. Any other window name is model-specific.","type":"string","enum":["five_hour","seven_day"],"x-python":{"literal":"UsageWindowName","frozenset":"ACCOUNT_WINDOWS"}},"UsageWindow":{"description":"One usage window of a RateLimitInfo.","type":"object","x-python":{"typeddict":"UsageWindow"},"properties":{"utilization":{"type":"number","description":"Exhausted when at or above EXHAUSTED_UTILIZATION."},"resetsAt":{"type":"number","description":"Reset time in epoch seconds."}},"required":["utilization"]},"RateLimitInfo":{"description":"The rate_limit_info of a rate_limit_event: the info argument of the quota readers.","type":"object","x-python":{"typeddict":"RateLimitInfo"},"properties":{"status":{"$ref":"#/$defs/RateLimitStatus"},"unifiedWindows":{"type":"object","additionalProperties":{"$ref":"#/$defs/UsageWindow"},"description":"Window name -> usage window."},"resetsAt":{"type":"number","description":"Top-level reset time in epoch seconds."},"rateLimitType":{"type":"string","description":"The value with meaning here is MODEL_OVERAGE_TYPE.","x-values":{"MODEL_OVERAGE_TYPE":"seven_day_overage_included"}},"overageDisabledReason":{"type":"string","description":"The value with meaning here is OUT_OF_CREDITS_REASON.","x-values":{"OUT_OF_CREDITS_REASON":"out_of_credits"}}},"required":["status"]},"RateLimitEvent":{"description":"One Claude CLI stream-json rate-limit event.","type":"object","x-python":{"typeddict":"RateLimitEvent"},"properties":{"type":{"type":"string","const":"rate_limit_event","x-value-constant":"RATE_LIMIT_EVENT_TYPE"},"rate_limit_info":{"$ref":"#/$defs/RateLimitInfo","x-key-constant":"RATE_LIMIT_INFO_KEY"}},"required":["type","rate_limit_info"]}}}
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
//   request: { id?, title?, description?, repoPath?, requestedBy? },  // raw stakeholder request
//   maxPasses?: number,   // bounded maker-checker passes for the PRD draft (default 2)
// }
// returns: {
//   ok, request, intakeBrief, persona, okrs, prd, alignmentVerdict, scope, decision, note,
//   epic: {                    // the Epic created together with the PRD — the caller writes it with bd
//     key:         'E1',       // stable local key; downstream parent links reference it
//     type:        'epic',     // literal — the bead face of the PRD; a container, never worked and never itself decomposed
//     title:       string,     // the PRD's title
//     description: string,     // one-paragraph scope statement derived from the PRD
//     prdRef:      string,     // the originating request's id (falls back to the PRD's title)
//     matrixRecord: {          // how the pair is recorded, once the caller has written the Epic bead and the PRD file:
//       role:    string,       // the atw-matrix role that runs it (ATW_MATRIX_ROLE)
//       command: string[],     // atw-matrix sync-epics --bead <the Epic's beads id> --prd <the PRD's path>
//       records: string,       // what the command records
//     },
//   },
// }
// The matrix is the one record of which PRD an Epic has: no `**Epic:**` line in the PRD and no `prd:` label
// on the bead. This mini writes neither the bead nor the PRD file, so the caller that writes them runs
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

const requestText = [
  request.id ? `Request ${request.id}` : null,
  request.title ? `Title: ${request.title}` : null,
  request.requestedBy ? `Requested by: ${request.requestedBy}` : null,
  request.description ? `Description:\n${request.description}` : null,
]
  .filter(Boolean)
  .join('\n') || '(no raw request text provided)'

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

const intake = await settleAgent(
  `Scope this stakeholder request and capture it as a structured intake brief. Both halves, one pass, each field under its own key. State the problem, the audience, and the desired outcome plainly — WHAT the job seeker needs, not HOW to build it. Do NOT write the PRD itself, the persona, or the OKRs; later makers own those.

Raw stakeholder request:
${requestText}

Working repository context: ${repo}

READING BUDGET (binding): the request above is your source. This is a framing task over a few paragraphs of stakeholder text — read at most 5 files, and only to resolve a term the request uses that you genuinely cannot interpret. Do not survey the repository or the polyrepo, and carry anything still unclear as an open question rather than investigating it.

Deliver the scope framing:
- scopeSummary: a one-paragraph framing of what this PRD must cover.
- inScope: the concerns this PRD owns (array).
- outOfScope: the concerns explicitly excluded (array).

And the intake brief:
- problem: the job-seeker problem this addresses.
- audience: who is affected (the job-seeker segment).
- desiredOutcome: the outcome the feature must produce for that audience.
- constraints: known constraints or non-negotiables (array).
- openQuestions: unresolved ambiguities to carry forward (array).

Ceilings: ${SCOPE_LIST_MAX} entries each in \`inScope\` and \`outOfScope\`, ${CONSTRAINTS_MAX} in \`constraints\`, ${OPEN_QUESTIONS_MAX} in \`openQuestions\`. A framing that needs more than that is enumerating restatements of one concern.`,
  {
    label: 'intake:scope-and-brief',
    effort: 'medium',
    phase: 'Intake',
    agentType: 'stakeholder-request-intake-writer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: [
        'scopeSummary',
        'inScope',
        'outOfScope',
        'problem',
        'audience',
        'desiredOutcome',
        'constraints',
        'openQuestions',
      ],
      properties: {
        scopeSummary: { type: 'string' },
        inScope: { type: 'array', items: { type: 'string' } },
        outOfScope: { type: 'array', items: { type: 'string' } },
        problem: { type: 'string' },
        audience: { type: 'string' },
        desiredOutcome: { type: 'string' },
        constraints: { type: 'array', items: { type: 'string' } },
        openQuestions: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)
if (!intake) {
  return dispatchOutcome({ ok: false, stage: 'agent-dispatch-failed', error: 'intake produced nothing — no scope framing and no brief to author a PRD from', dispatchFailed: true, dispatchFailures: dispatchDeaths('Intake') })
}
// The stated ceilings, measured. Observation only: every entry is carried forward.
checkLimit('Intake', 'inScope', intake.inScope, SCOPE_LIST_MAX)
checkLimit('Intake', 'outOfScope', intake.outOfScope, SCOPE_LIST_MAX)
checkLimit('Intake', 'constraints', intake.constraints, CONSTRAINTS_MAX)
checkLimit('Intake', 'openQuestions', intake.openQuestions, OPEN_QUESTIONS_MAX)

// Both shapes the rest of this file already reads, assembled from the one session.
const scope = {
  scopeSummary: intake.scopeSummary,
  inScope: intake.inScope,
  outOfScope: intake.outOfScope,
  openQuestions: intake.openQuestions,
}
const intakeBrief = {
  problem: intake.problem,
  audience: intake.audience,
  desiredOutcome: intake.desiredOutcome,
  constraints: intake.constraints,
  openQuestions: intake.openQuestions,
}

// ── Persona & OKR (parallel makers) ───────────────────────────────────────────
phase('Persona & OKR')

const briefBlock = `Problem: ${intakeBrief.problem}
Audience: ${intakeBrief.audience}
Desired outcome: ${intakeBrief.desiredOutcome}
Constraints: ${(intakeBrief.constraints || []).join('; ') || 'none'}`

const [persona, okrs] = await parallel([
  () =>
    settleAgent(
      `Author the target persona this PRD serves. Take the persona's population from the intake brief, and ground the persona in it.

Intake brief:
${briefBlock}

Deliver:
- name: a short persona label.
- summary: a one-paragraph portrait of this job seeker.
- goals: what they are trying to achieve (array).
- frustrations: the pain points the feature must relieve (array).
- context: their situation/environment relevant to this feature.

At most ${PERSONA_LIST_MAX} entries each in \`goals\` and \`frustrations\`. A persona with more goals than that has no persona.`,
      {
        label: 'persona:author',
        effort: 'low',
        phase: 'Persona & OKR',
        agentType: 'persona-profile-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['name', 'summary', 'goals', 'frustrations', 'context'],
          properties: {
            name: { type: 'string' },
            summary: { type: 'string' },
            goals: { type: 'array', items: { type: 'string' } },
            frustrations: { type: 'array', items: { type: 'string' } },
            context: { type: 'string' },
          },
        },
      }
    ),
  () =>
    settleAgent(
      `Author the objective and key results this feature must move. The objective is a qualitative, job-seeker-centered statement; each key result is a measurable signal that proves the objective was met. Ground them in the intake brief.

Intake brief:
${briefBlock}

Deliver:
- objective: the single qualitative objective this feature serves.
- keyResults: measurable results, each with a metric and a target (array) — at most ${KEY_RESULTS_MAX}. An objective with more than a handful of key results has no objective.`,
      {
        label: 'okr:author',
        effort: 'low',
        phase: 'Persona & OKR',
        agentType: 'okr-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['objective', 'keyResults'],
          properties: {
            objective: { type: 'string' },
            keyResults: {
              type: 'array',
              // An objective with more than a handful of key results has no objective, but that
              // is a judgment about the OKRs, not a reason to discard the whole result.
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['metric', 'target'],
                properties: {
                  metric: { type: 'string' },
                  target: { type: 'string' },
                },
              },
            },
          },
        },
      }
    ),
])

// ── PRD Draft (maker-checker, bounded loop) ───────────────────────────────────
phase('PRD Draft')

// A dead maker is a dispatch failure, not a persona with no name. Reading `.name` off
// null threw a TypeError out of this mini, out of the composite, and killed the run —
// the same class of crash the settleAgent block above exists to prevent.
if (!persona || !okrs) {
  return dispatchOutcome({
    ok: false,
    stage: 'agent-dispatch-failed',
    error: `${!persona ? 'the persona writer' : ''}${!persona && !okrs ? ' and ' : ''}${!okrs ? 'the OKR writer' : ''} returned nothing — the PRD has no persona or OKRs to be authored against`,
    intakeBrief,
    scope,
    persona: persona || null,
    okrs: okrs || null,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Persona & OKR'),
  })
}

checkLimit('Persona & OKR', 'goals', persona.goals, PERSONA_LIST_MAX)
checkLimit('Persona & OKR', 'frustrations', persona.frustrations, PERSONA_LIST_MAX)
checkLimit('Persona & OKR', 'keyResults', okrs.keyResults, KEY_RESULTS_MAX)

const personaBlock = `Persona: ${persona.name} — ${persona.summary}
Goals: ${(persona.goals || []).join('; ') || 'n/a'}
Frustrations: ${(persona.frustrations || []).join('; ') || 'n/a'}`

const okrBlock = `Objective: ${okrs.objective}
Key results: ${(okrs.keyResults || [])
  .map((k) => `${k.metric} → ${k.target}`)
  .join('; ') || 'n/a'}`

// Maker: prd-writer authors the template-conformant PRD and, in the same pass,
// the one-paragraph scope statement for the Epic that is created alongside it.
// Authoring both together keeps the pairing literal and the Epic in sync when
// the draft loops on checker feedback — no separate analysis pass is needed,
// because the PRD already contains the scope.
async function draftPRD(feedback) {
  return settleAgent(
    `Author the template-conformant Product Requirements Document (PRD) from the inputs below. Stay WHAT-not-HOW — describe the required behavior and outcomes, never the implementation. Follow the standard PRD template: required sections, P0 acceptance criteria, no leftover scaffolding.

Intake brief:
${briefBlock}
Open questions to resolve or flag: ${(intakeBrief.openQuestions || []).join('; ') || 'none'}

${personaBlock}

${okrBlock}

Deliver:
- title: the PRD title.
- prd: the full PRD body in Markdown, template-conformant. It carries no \`**Epic:**\` line: the matrix is the one record of which Epic a PRD belongs to.
- sections: the section headings present (array), to confirm template coverage — at most ${SECTIONS_MAX}.
- acceptanceCriteria: P0 acceptance criteria as given/when/then (array) — P0 ONLY, at most ${P0_CRITERIA_MAX}, each clause under 30 words. Every one of them is re-read by the alignment checker, by PRD validation, by the TRD author and by every spec author.
- epicScope: a one-paragraph scope statement for the Epic that pairs with this PRD — a container-level summary of the scope the PRD owns, with no acceptance criteria and no repository specifics (one Epic may span repos).${
      feedback
        ? `\n\nALIGNMENT FEEDBACK from the independent checker — address every point before resubmitting:\n${feedback}`
        : ''
    }`,
    {
      label: 'prd:draft',
      effort: 'medium',
      phase: 'PRD Draft',
      agentType: 'prd-writer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'prd', 'sections', 'acceptanceCriteria', 'epicScope'],
        properties: {
          title: { type: 'string' },
          prd: { type: 'string' },
          sections: { type: 'array', items: { type: 'string' } },
          epicScope: { type: 'string' },
          acceptanceCriteria: {
            type: 'array',
            // P0 only, as the brief says. Everything here is re-read by the alignment
            // checker, by PRD validation, by the TRD author and by every spec author.
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['given', 'when', 'then'],
              properties: {
                given: { type: 'string' },
                when: { type: 'string' },
                then: { type: 'string' },
              },
            },
          },
        },
      },
    }
  )
}

// Checker: an INDEPENDENT verifier — never the prd-writer.
async function verifyAlignment(prd) {
  return settleAgent(
    `You are an INDEPENDENT alignment verifier. You did NOT write this PRD — you only judge it. Do NOT rewrite the PRD. Verify the drafted PRD aligns with the intake brief, the persona, and the OKRs, and that it is template-conformant and WHAT-not-HOW.

Intake brief:
${briefBlock}

${personaBlock}

${okrBlock}

PRD under review (title: ${prd.title}):
${prd.prd}

Decide exactly one verdict:
- "aligned": the PRD covers the intake problem/outcome, serves the named persona, and its acceptance criteria trace to the OKRs.
- "misaligned": one or more of those hold false. Return feedback specific enough that the prd-writer can fix it without interpretation.

For each dimension (intake, persona, okr, template), state whether it is satisfied with evidence — exactly ${ALIGNMENT_DIMENSIONS.length} entries in \`dimensions\`, one per dimension and no others.`,
    {
      label: 'prd:alignment-check',
      // A checker, and the prd-alignment-verifier's own file already says `effort: low`
      // — this override was RAISING it. It judges a document against three stated inputs;
      // the expensive judgment in this mini is the deadlock ruling below.
      effort: 'low',
      phase: 'PRD Draft',
      agentType: 'prd-alignment-verifier',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'dimensions', 'feedback'],
        properties: {
          verdict: { type: 'string', enum: ['aligned', 'misaligned'] },
          dimensions: {
            type: 'array',
            // Exactly the four dimensions the enum names, one entry each — stated in the
            // brief and counted after the ruling, never bound here.
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['dimension', 'satisfied', 'evidence'],
              properties: {
                dimension: { type: 'string', enum: ['intake', 'persona', 'okr', 'template'] },
                satisfied: { type: 'boolean' },
                evidence: { type: 'string' },
              },
            },
          },
          feedback: { type: 'string' },
        },
      },
    }
  )
}

let prd = null
let alignmentVerdict = null
let feedback = ''
let deadlocked = false
let passesRun = 0
/** Every re-draft after a misaligned verdict, with what changed in the writer's input. */
const retries = []
for (let pass = 1; pass <= MAX_PASSES; pass++) {
  passesRun = pass
  prd = await draftPRD(feedback)
  // Same guard, same reason: verifyAlignment reads `prd.title` and `prd.prd`.
  if (!prd) {
    return dispatchOutcome({ ok: false, stage: 'agent-dispatch-failed', error: 'the prd-writer returned nothing — there is no PRD to check', reason: 'the prd-writer returned nothing — there is no PRD to check', intakeBrief, persona, okrs, scope, dispatchFailed: true, dispatchFailures: dispatchDeaths('PRD Draft') })
  }
  checkLimit(`PRD Draft (pass ${pass})`, 'sections', prd.sections, SECTIONS_MAX)
  checkLimit(`PRD Draft (pass ${pass})`, 'P0 acceptance criteria', prd.acceptanceCriteria, P0_CRITERIA_MAX)
  alignmentVerdict = await verifyAlignment(prd)
  if (!alignmentVerdict) {
    return dispatchOutcome({ ok: false, stage: 'agent-dispatch-failed', error: 'alignment check returned no verdict', reason: 'alignment check returned no verdict', intakeBrief, persona, okrs, scope, prd, dispatchFailed: true, dispatchFailures: dispatchDeaths('PRD Draft') })
  }
  checkLimit(`PRD Draft (pass ${pass})`, 'alignment dimensions', alignmentVerdict.dimensions, ALIGNMENT_DIMENSIONS.length)
  // The verdict is read off the checker's own dimensions: "aligned" beside a dimension it
  // marked unsatisfied is not alignment, and the unsatisfied evidence is the rework brief.
  const unsatisfied = (Array.isArray(alignmentVerdict.dimensions) ? alignmentVerdict.dimensions : []).filter((d) => d && d.satisfied === false)
  if (alignmentVerdict.verdict === 'aligned' && unsatisfied.length) {
    log(`PRD draft: the checker said aligned but marked ${unsatisfied.map((d) => d.dimension).join(', ')} unsatisfied — read as misaligned`)
    alignmentVerdict = { ...alignmentVerdict, verdict: 'misaligned' }
  }
  if (alignmentVerdict.verdict === 'aligned') {
    log(`PRD draft: ALIGNED on pass ${pass}/${MAX_PASSES}`)
    break
  }
  // A misaligned verdict with empty feedback would re-run the maker on identical input.
  feedback = String(alignmentVerdict.feedback || '').trim() || unsatisfied.map((d) => `${d.dimension}: ${d.evidence}`).join('\n')
  log(`PRD draft: MISALIGNED pass ${pass}/${MAX_PASSES} — ${feedback || '(no feedback given)'}`)
  // With nothing to act on, another draft is the same dispatch on the same input: a blind
  // retry. The standoff goes to the decider now instead.
  if (pass === MAX_PASSES || !feedback) {
    deadlocked = true
    break
  }
  retries.push({ pass: pass + 1, whatChanged: `the prd-writer is given the alignment checker's feedback on pass ${pass}: ${feedback}` })
}

// Deadlock: the maker and checker could not converge — the spec-decider rules.
let decision = null
if (deadlocked) {
  log('PRD draft: maker-checker deadlock — escalating to spec-decider for a binding ruling')
  decision = await settleAgent(
    `The prd-writer and the independent prd-alignment-verifier could not converge after ${passesRun} pass(es)${feedback ? '' : ', and the checker named nothing the writer could act on'}. Rule on the standoff. Your ruling is binding.

Latest checker feedback: ${feedback || '(none)'}

The checker judged the PRD against these inputs; judge its objection against the same ones.

Intake brief:
${briefBlock}

${personaBlock}

${okrBlock}

PRD under review (title: ${prd.title}):
${prd.prd}

Decide exactly one verdict:
- "accept": the PRD is acceptable as-is despite the checker's objection — explain why the objection does not block.
- "reject": the PRD must not proceed — state the blocking gap its author must close.`,
    {
      label: 'prd:deadlock-ruling',
      effort: 'high',
      phase: 'PRD Draft',
      agentType: 'spec-decider',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'rationale'],
        properties: {
          verdict: { type: 'string', enum: ['accept', 'reject'] },
          rationale: { type: 'string' },
        },
      },
    }
  )
}

const aligned = alignmentVerdict && alignmentVerdict.verdict === 'aligned'
const ruledAccept = decision && decision.verdict === 'accept'
const ok = Boolean(aligned || ruledAccept)
// A deadlock ruling that never came back is a dispatch failure, not a rejection.
const deciderDied = deadlocked && !decision

// A PRD and its Epic are created at the same time — the Epic is the bead-side
// half of that pairing, assembled here from the maker's own output rather than
// a fresh analysis pass. It is a CONTAINER: no acceptance criteria and no repo
// scope, because one Epic may span repos and its Stories (one per repo) are
// minted later, each alongside its Spec. Exactly one epic is emitted per PRD;
// this mini never writes to .beads — the caller writes the bead with bd.
const epic = prd
  ? {
      key: 'E1',
      type: 'epic',
      title: prd.title,
      description: prd.epicScope,
      // Inside this mini the PRD has no bead id or file path yet, so the ref is
      // the originating request id when supplied, else the PRD's own title.
      prdRef: request.id || prd.title,
      // The pair is recorded in the matrix, and nowhere else, by this command, which the caller runs once
      // the Epic bead exists and the PRD file is written. The two placeholders are the caller's to fill.
      matrixRecord: {
        role: MATRIX_RECORD_ROLE,
        command: ['atw-matrix', 'sync-epics', '--bead', EPIC_ID_PLACEHOLDER, '--prd', PRD_PATH_PLACEHOLDER],
        records: 'the epic entry with its PRD path and hash, one requirement entry per #### heading under ## Requirements, and hasRequirement from the Epic to each',
      },
    }
  : null

return dispatchOutcome({
  ok,
  stage: ok ? 'done' : deciderDied ? 'agent-dispatch-failed' : 'prd-draft',
  headline: ok
    ? `PRD "${prd.title}" authored and ${aligned ? 'aligned' : 'accepted by ruling'}`
    : deciderDied
      ? 'the PRD did not align and the deadlock ruling returned nothing'
      : `the PRD did not align within ${passesRun} pass(es)${decision ? `; ruled reject: ${decision.rationale}` : ''}`,
  ...(ok ? {} : { error: deciderDied ? 'the PRD did not align and the deadlock ruling returned nothing' : `the PRD did not align within ${passesRun} pass(es)${decision ? `; ruled reject: ${decision.rationale}` : ''}` }),
  ...(deciderDied ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('PRD Draft') } : {}),
  request: request.id ? request.id : null,
  intakeBrief,
  persona,
  okrs,
  prd,
  epic,
  alignmentVerdict,
  scope,
  decision,
  retries,
  ...(limitFindings.length ? { limitFindings } : {}),
  note: ok
    ? `PRD is intake/persona/OKR-aligned and template-conformant. Once the Epic bead exists and the PRD file is written, record the pair in the matrix: ${epic.matrixRecord.command.join(' ')} (role ${MATRIX_RECORD_ROLE}).`
    : 'PRD did not reach alignment within the bounded passes; see decision for the binding ruling.',
})
