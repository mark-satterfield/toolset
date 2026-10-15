export const meta = {
  name: 'tdd-red',
  description:
    'Shared-tail mini — TDD Red. Test writers derived from the contract surfaces (unit always) extend the existing suite, one writer after another, with failing tests that encode the acceptance criteria and confirm they fail. In update mode (testIssues given) the unit test writer rules on each existing test the implementer named — update it, delete it, or keep it — citing the contract. Writes tests only — no production code. With plan it names the test agents the contract calls for (testAgents) and runs none; with testAgent it runs only that one of them.',
  phases: [{ title: 'Red', detail: 'author failing tests, or rule on the tests the implementer named' }],
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

        return out
      }

      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)

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

// args: { contract, feedback?: string, red?: { testFiles },
//         testIssues?: [{ testId, kind: 'obsolete-by-contract' | 'defect' | 'missing-config', reason, contractRef? }],
//         plan?: boolean (name the test agents the contract calls for and run none),
//         testAgent?: string (run only this one of them) }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim() || '(repo path not provided)'
const beadId = (c.bead && c.bead.id) || null
const ac = Array.isArray(c.acceptanceCriteria) ? c.acceptanceCriteria : []
const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '')
const strList = (v) => (Array.isArray(v) ? v.map((x) => str(x)).filter(Boolean) : [])

const priorTestFiles = a.red ? strList(a.red.testFiles) : []
const priorTestsBlock = priorTestFiles.length
  ? `\n\nThe previous Red attempt authored these test files. Edit them in place; do not create a parallel file:\n${priorTestFiles.join('\n')}`
  : ''

phase('Red')

const acLine = (x, i) => {
  if (typeof x === 'string') return `${i + 1}. ${x.trim()}`
  if (x && typeof x === 'object' && (x.given || x.when || x.then)) {
    return `${i + 1}. GIVEN ${x.given || 'n/a'} WHEN ${x.when || 'n/a'} THEN ${x.then || 'n/a'}`
  }
  return `${i + 1}. ${JSON.stringify(x)}`
}

const isBugContract = !!(c.reproduction || c.rootCause)
const beadDescription = c.bead ? str(c.bead.description) : ''
const specBlock = (() => {
  const s = c.spec && typeof c.spec === 'object' ? c.spec : null
  if (!s) return ''
  const docs = [...new Set([str(s.specPath), ...strList(s.specPaths)].filter(Boolean))]
  const decisionIds = [...new Set([...strList(c.decisionIds), ...strList(s.decisionIds)])]
  const lines = [
    str(s.id) || str(s.title) ? `Spec ${str(s.id)}${str(s.title) ? `: ${str(s.title)}` : ''}` : '',
    docs.length ? `Spec documents — read the sections named below in these files:\n${docs.map((d) => `  - ${d}`).join('\n')}` : '',
    strList(s.specSections).length ? `Spec sections defining this work: ${strList(s.specSections).join(', ')}` : '',
    strList(s.requirementIds).length ? `Requirements satisfied: ${strList(s.requirementIds).join(', ')}` : '',
    decisionIds.length ? `Architecture views this work is designed against (paths relative to the arc42 folder): ${decisionIds.join(', ')}` : '',
    strList(s.definitionOfDone).length ? `Definition of Done:\n${strList(s.definitionOfDone).map((d) => `  - ${d}`).join('\n')}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const infraBlock = (() => {
  const pi = c.provisioningIntent && typeof c.provisioningIntent === 'object' ? c.provisioningIntent : null
  const stacks = [...new Set([...strList(c.affectedStacks), ...strList(pi && pi.affectedStacks)])]
  const resources = pi && Array.isArray(pi.resources) ? pi.resources.filter((r) => r && typeof r === 'object') : []
  const refs = pi ? strList(pi.crossStackRefs) : []
  const lines = [
    stacks.length ? `Affected CDK stacks: ${stacks.join(', ')}` : '',
    resources.length
      ? `Provisioning intent — the resources to provision:\n${resources
          .map((r) => `  - ${str(r.logicalId) || '(resource)'} ${str(r.type)}${str(r.stack) ? ` in ${str(r.stack)}` : ''}${str(r.properties) ? `: ${str(r.properties)}` : ''}`)
          .join('\n')}`
      : '',
    refs.length ? `Cross-stack references:\n${refs.map((x) => `  - ${x}`).join('\n')}` : '',
    pi && str(pi.rationale) ? `Intent rationale: ${str(pi.rationale)}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const taskBlock = `${c.bead ? `${isBugContract ? 'Bug' : 'Task'} ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature under test'}${
  beadDescription ? `\n\n${beadDescription}` : ''
}${isBugContract ? `\n\nReproduction: ${c.reproduction || 'n/a'}\nRoot cause: ${c.rootCause || 'n/a'}` : ''}${specBlock}${infraBlock}

Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}

Unit tests mock the AWS services the code calls; no test reaches AWS. A criterion about the repository's CDK stacks is encoded as a failing \`cdk synth\` assertion test, written with the assertions library of the language the repository's CDK app is written in, in the repository's existing synth test module where there is one: it asserts the synthesized template's resources and their properties, the cross-stack references the stacks write and read, and the IAM permissions the criteria require.

Acceptance criteria to encode as tests:
${ac.length ? ac.map(acLine).join('\n') : isBugContract ? '(none — derive minimal coverage from the reproduction)' : '(none — derive minimal coverage from the spec documents and the description above)'}`

// Surface → test writer lookup; the unit writer always runs.
const SURFACE_WRITERS = {
  'api-contract': 'consumer-driven-contract-test-writer',
  'event-chain': 'aws-integration-test-writer',
  auth: 'security-test-case-designer',
  performance: 'performance-benchmark-writer',
  'web-ui': 'playwright-e2e-web-test-writer',
  ios: 'xcuitest-writer',
  android: 'espresso-test-writer',
  'cross-platform-mobile': 'mobile-e2e-test-writer',
  ml: 'ml-evaluation-tester',
  'data-pipeline': 'data-pipeline-test-writer',
}
const surfaces = (Array.isArray(c.surfaces) ? c.surfaces : []).map((s) => String(s || '').trim().toLowerCase())
const surfaceWriters = surfaces.map((s) => SURFACE_WRITERS[s]).filter(Boolean)

const testIssues = (Array.isArray(a.testIssues) ? a.testIssues : []).filter((x) => x && typeof x === 'object' && str(x.testId))
const updateMode = testIssues.length > 0
// Update mode rules on existing tests; the unit test writer owns the suite those tests live in.
const writersFinal = updateMode ? ['tdd-unit-test-generator'] : ['tdd-unit-test-generator', ...new Set(surfaceWriters)]
const selectionMode = updateMode ? 'update' : surfaceWriters.length ? 'derived' : 'unit-only'
if (a.plan === true) return dispatchOutcome({ testAgents: writersFinal, mode: selectionMode })
const onlyAgent = str(a.testAgent)
if (onlyAgent && !writersFinal.includes(onlyAgent)) {
  return dispatchOutcome({ ok: false, dispatchFailed: true, reason: `${onlyAgent} is not a test agent this contract calls for (${writersFinal.join(', ')})`, testFiles: [], redConfirmed: false, evidence: '' })
}
const writersRun = onlyAgent ? [onlyAgent] : writersFinal
log(`Red test agents (${selectionMode}): ${writersRun.join(', ')}`)

const strategy = c.testStrategy || null
const strategyBlock = strategy
  ? `\nTest strategy: pyramid=${strategy.pyramid || 'n/a'}; coverageThreshold=${strategy.coverageThreshold || 'n/a'}; envMatrix=${(strategy.envMatrix || []).join(', ') || 'n/a'}`
  : ''

const suiteCommand = str(c.suiteCommand)
const suiteBlock = suiteCommand
  ? `\n\nThe run judges the suite by running exactly \`cd "${repo}" && ${suiteCommand}\` itself. Run your tests with that command (narrowed to your files while you work), so what you see is what the run measures.`
  : ''

const turnBlock = (w) => {
  const others = writersFinal.filter((x) => x !== w)
  return others.length
    ? `\n\nOther test writers work on this tree one after another: ${others.join(', ')}. Create or edit only test files of your own kind of test (${w}); the unit test files belong to tdd-unit-test-generator.`
    : ''
}

const RED_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['testFiles', 'redConfirmed', 'evidence'],
  properties: {
    testFiles: { type: 'array', items: { type: 'string' } },
    redConfirmed: { type: 'boolean' },
    evidence: { type: 'string' },
    decisions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['testId', 'action', 'reason'],
        properties: {
          testId: { type: 'string' },
          action: { type: 'string', enum: ['update', 'delete', 'keep'] },
          reason: { type: 'string' },
        },
      },
    },
    notes: { type: 'string' },
  },
}

const issueLine = (x, i) =>
  `${i + 1}. ${str(x.testId)} (${str(x.kind) || 'unclassified'}): ${str(x.reason) || 'no reason given'}${str(x.contractRef) ? ` — contract: ${str(x.contractRef)}` : ''}`

const authorPrompt = (w) => `Write the failing test(s) that encode the expected behavior below, then RUN them and confirm they FAIL for the intended reason (Red). Write test code ONLY — do not change production code. You are '${w}' — author only the tests of your specialty.

Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

Add to the existing test file that covers this module or behavior, matching its imports, fixtures, naming and helpers; create a new file only when none covers this area. Where an existing test already encodes a criterion, keep it and do not duplicate it. Tests synthesize, build or render the thing under test during the run; they never read a committed build output.${turnBlock(w)}

${taskBlock}
${c.regressionPlanPath ? `Cumulative regression scope: ${c.regressionPlanPath}. Read the actual approved artifact and requirement sources. Author missing tests for impacted requirements/layers assigned to your specialty in this repository, preserving prior tests. Unavailable cross-repository test changes are an explicit blocked dependency, not permission to edit another checkout. Retain stable JUnit classname::name identities for existing tests; record concrete test names for new coverage.` : ''}
${strategyBlock}${suiteBlock}${priorTestsBlock}
${a.feedback ? `\nFeedback from the previous attempt — address it:\n${a.feedback}` : ''}

Deliver: the test file paths you created or modified, whether Red is confirmed, and the captured failing output as evidence.`

const updatePrompt = (w) => `The implementer building the Task below reports that these existing tests stand between the code and the contract. It may not change tests; you own them. Rule on each one:

${testIssues.map(issueLine).join('\n')}

For each named test choose one action and cite the contract (an acceptance criterion, a spec section, or an architecture view below) in the reason:
- update — the test encodes behaviour or configuration the contract changes: rewrite it to encode what the contract states.
- delete — the test encodes behaviour the contract removes, and no criterion needs it.
- keep — the test is right under the contract; the production code must change to pass it. Say what it requires.

Change test code and nothing else: the implementer owns the production code. You are '${w}'.

Every file you modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

${taskBlock}
${c.regressionPlanPath ? `Read cumulative requirements at ${c.regressionPlanPath}; no existing test may be removed or weakened merely because the new PRD omits the prior requirement. Require explicit accepted supersession source.` : ''}
${suiteBlock}${priorTestsBlock}
${a.feedback ? `\nThe last suite run:\n${a.feedback}` : ''}

Deliver: one decision per named test, the test file paths you modified, the captured output of the tests you changed as evidence, and redConfirmed true when every test you updated runs and fails or passes as the contract says it should.`

// Writers run one after another: concurrent writers in one tree edited the same files.
const writerResultsRaw = []
for (const w of writersRun) {
  writerResultsRaw.push(
    await settleAgent(updateMode ? updatePrompt(w) : authorPrompt(w), {
      label: `red:${updateMode ? 'update:' : ''}${w}`,
      phase: 'Red',
      agentType: w,
      schema: RED_SCHEMA,
    })
  )
}

const writerResults = writerResultsRaw.filter(Boolean)
const deadWriters = writersRun.filter((_w, i) => !writerResultsRaw[i])
const testFiles = writerResults.flatMap((r) => (Array.isArray(r.testFiles) ? r.testFiles : []))
const authoringWriters = writerResults.filter((r) => Array.isArray(r.testFiles) && r.testFiles.length)
const redConfirmed = authoringWriters.length > 0 && authoringWriters.every((r) => r.redConfirmed === true)
const evidence = writerResults.map((r) => r.evidence).filter(Boolean).join('\n---\n')
const decisions = writerResults.flatMap((r) => (Array.isArray(r.decisions) ? r.decisions : []))

const ledger = { phase: 'red', beadId, chosen: writersRun, mode: selectionMode, ok: updateMode ? writerResults.length > 0 : redConfirmed }

if (!writerResults.length) {
  return dispatchOutcome({
    ok: false,
    dispatchFailed: true,
    reason: `every Red test agent returned nothing: ${deadWriters.join(', ')}`,
    testFiles: [],
    redConfirmed: false,
    evidence: '',
    writers: writersRun,
    surfaces,
    strategy,
    ledger,
  })
}

const reason = updateMode
  ? ''
  : !authoringWriters.length
    ? 'no writer authored a test file'
    : !redConfirmed
      ? `not Red: ${authoringWriters.filter((r) => r.redConfirmed !== true).flatMap((r) => r.testFiles).join(', ')} did not fail as intended`
      : ''

return dispatchOutcome({
  testFiles,
  redConfirmed,
  evidence,
  ...(updateMode ? { updateMode: true, decisions } : {}),
  ...(reason ? { reason } : {}),
  writers: writersRun,
  surfaces,
  strategy,
  ledger,
})
