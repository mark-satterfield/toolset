export const meta = {
  name: 'deploy-mechanism',
  description:
    "Leaf mini — asks one polyrepo-steward session what a Story's repository publishes and deploys, before the Story's deploy. A repository can publish a package to CodeArtifact, deploy with CDK, both, or neither; the steward answers from its records and the repository's own declarations, and names the command that publishes the package as the repository declares it. A Taskfile is a convenience and does not decide the mechanism. The host runs what applies (publish, then `cdk deploy`) and stops a repository that does neither. Returns { ok, stage, beadId, headline, detailPath, mechanism: { repository, publishes, publishCommand, deploys, reason } }.",
  phases: [{ title: 'Ask', detail: "the polyrepo-steward rules what the Story's repository publishes and deploys" }],
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
// ===== SHARED BLOCK story-deploy-args — BEGIN (canonical: scripts/shared-blocks/story-deploy-args.js; filled from skills/artifact-handoff/schemas/story-deploy-args.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// Generated from skills/artifact-handoff/schemas/story-deploy-args.schema.json, the one definition of the
// Story deploy workflow arguments. Never restate a key, value or shape of it in a workflow: read it from here.
const STORY_DEPLOY_ARGS_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"https://agent-teams-workforce/skills/artifact-handoff/schemas/story-deploy-args.schema.json","title":"Story deploy workflow arguments","description":"The argument shapes of a Story's deploy. StoryDeployInput is the driver's own story-deploy input; BuiltVersionArgs, StoryDeployFixArgs and DeployMechanismArgs are the arguments the driver sends to the built-version, story-deploy-fix and deploy-mechanism workflows. The built-version and story-deploy-fix workflows run child steps of a step of the Story's step journal, which JournalRef names. The execution-identity keys the lane adds (executionId, supervisorInvocationId) are owned by the execution-identity contract and are not named here, so StoryDeployInput and BuiltVersionArgs admit additional properties.","$defs":{"Composite":{"description":"The composite names that address these shapes (dispatch wire values).","type":"string","enum":["story-deploy","built-version","story-deploy-fix","deploy-mechanism"]},"FailureStep":{"description":"The deploy step that failed.","type":"string","enum":["publish","synth","deploy","verify"]},"VerifiedStackStatus":{"description":"The CloudFormation stack statuses that count as a verified deploy.","type":"string","enum":["CREATE_COMPLETE","UPDATE_COMPLETE"]},"PluginRoot":{"description":"The absolute path of an agent-teams-workforce install, with no '//' and no '..'.","type":"string","pattern":"^(?!.*//)(?!.*\\.\\.)/[A-Za-z0-9._/-]+$"},"StoryRef":{"description":"The Story a deploy works on.","type":"object","additionalProperties":false,"required":["id"],"properties":{"id":{"type":"string","minLength":1,"description":"The Story's beads id."},"title":{"type":"string","description":"The Story's title, possibly empty."}}},"TaskRef":{"description":"One Task, infra or infrastructure child bead of the Story.","type":"object","additionalProperties":false,"required":["id","title"],"properties":{"id":{"type":"string","minLength":1},"title":{"type":"string"}}},"DepscoreRef":{"description":"Where depscore.py runs.","type":"object","additionalProperties":false,"required":["script","repo"],"properties":{"script":{"type":"string","minLength":1,"description":"Absolute path of the plugin's scripts/portfolio/depscore.py."},"repo":{"type":"string","minLength":1,"description":"The control repository (ATW_CONTROL_REPO)."}}},"StackStatus":{"description":"One CloudFormation stack's status after a deploy.","type":"object","additionalProperties":false,"required":["name","status","reason"],"properties":{"name":{"type":"string"},"status":{"type":"string"},"reason":{"type":"string"}}},"DeployFailure":{"description":"The failed deploy step and what it printed.","type":"object","additionalProperties":false,"required":["step","output"],"properties":{"step":{"$ref":"#/$defs/FailureStep"},"output":{"type":"string","description":"The captured tail of the step's output."},"stacks":{"type":"array","items":{"$ref":"#/$defs/StackStatus"}}}},"RelayRef":{"description":"The relay a workflow runs commands through.","type":"object","additionalProperties":false,"required":["runner","dir"],"properties":{"runner":{"type":"string","minLength":1,"description":"Absolute path of relayrun.py."},"dir":{"type":"string","minLength":1,"description":"The Story's own directory for relay files, the same on every dispatch of the Story."}}},"JournalRef":{"description":"The Story's step journal, the run the driver names, and the step whose child steps the workflow runs.","type":"object","additionalProperties":false,"required":["path","run","step"],"properties":{"path":{"type":"string","minLength":1,"description":"Absolute path of the Story's step journal file."},"run":{"type":"string","minLength":1,"description":"The name of this run: every journal change the workflow reports carries it."},"step":{"type":"string","pattern":"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$","description":"The id of the running journal step the workflow performs: its steps are that step's child steps."}}},"StoryDeployInput":{"description":"The driver's own story-deploy input for one Story.","type":"object","required":["story","repoPath","epicId","storySlug","tasks"],"properties":{"story":{"$ref":"#/$defs/StoryRef"},"repoPath":{"type":"string","minLength":1,"description":"The Story's repository root, not its worktree."},"epicId":{"type":"string","description":"The nearest Epic ancestor's bead id; empty means none."},"storySlug":{"type":"string","description":"The bead's elab_key without its Story prefix; empty when the prefix is absent."},"tasks":{"type":"array","items":{"$ref":"#/$defs/TaskRef"},"description":"The Story's child Task, infra and infrastructure beads, sorted by id."}}},"BuiltVersionArgs":{"description":"The arguments of the built-version workflow.","type":"object","required":["story","repoPath","archPath","depscore","journal"],"properties":{"beadId":{"type":"string","minLength":1,"description":"The consumer falls back to story.id."},"journal":{"$ref":"#/$defs/JournalRef"},"story":{"$ref":"#/$defs/StoryRef"},"repoPath":{"type":"string","minLength":1,"description":"The Story's worktree (absolute path)."},"repoName":{"type":"string","description":"The basename of the Story's repository root."},"branch":{"type":"string","description":"The worktree's checked-out branch."},"archPath":{"type":"string","minLength":1,"description":"The ATW_ARCH_PATH directory."},"depscore":{"$ref":"#/$defs/DepscoreRef"}}},"StoryDeployFixArgs":{"description":"The arguments of the story-deploy-fix workflow.","type":"object","additionalProperties":false,"required":["story","repoPath","failure","journal","pluginRoot","relay"],"properties":{"beadId":{"type":"string","minLength":1,"description":"The consumer falls back to story.id."},"journal":{"$ref":"#/$defs/JournalRef"},"story":{"$ref":"#/$defs/StoryRef"},"repoPath":{"type":"string","minLength":1,"description":"The Story's worktree."},"branch":{"type":"string"},"defaultBranch":{"type":"string"},"failure":{"$ref":"#/$defs/DeployFailure"},"pluginRoot":{"$ref":"#/$defs/PluginRoot"},"relay":{"$ref":"#/$defs/RelayRef"}}},"DeployMechanismArgs":{"description":"The arguments of the deploy-mechanism workflow.","type":"object","additionalProperties":false,"required":["story","repoPath"],"properties":{"beadId":{"type":"string","minLength":1,"description":"The consumer falls back to story.id."},"story":{"$ref":"#/$defs/StoryRef"},"repoPath":{"type":"string","minLength":1,"description":"The Story's repository, not its worktree."}}}}}
const STORY_DEPLOY_ARGS_DEFS = STORY_DEPLOY_ARGS_SCHEMA.$defs || {}
// Every top-level key of the four argument shapes, in schema order.
const ARG_KEYS = Object.freeze([...new Set(['StoryDeployInput', 'BuiltVersionArgs', 'StoryDeployFixArgs', 'DeployMechanismArgs']
  .flatMap((name) => Object.keys((STORY_DEPLOY_ARGS_DEFS[name] || {}).properties || {})))])
const FAILURE_STEPS = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.FailureStep || {}).enum || [])])
const VERIFIED_STACK_STATUSES = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.VerifiedStackStatus || {}).enum || [])])
const STORY_DEPLOY_COMPOSITES = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.Composite || {}).enum || [])])

// Checks `value` against one schema node (the subset the schema uses: local $ref, type object, string,
// integer and array, required, properties, additionalProperties false, enum, const, minLength, minimum,
// pattern) and returns the problems found, each naming its path.
const storyDeployArgsProblems = (node, value, path) => {
  if (node.$ref) {
    const local = '#/$defs/'
    if (!node.$ref.startsWith(local)) return [] // an external definition is checked by its own owner
    return storyDeployArgsProblems(STORY_DEPLOY_ARGS_DEFS[node.$ref.slice(local.length)] || {}, value, path)
  }
  if (node.anyOf) {
    return node.anyOf.some((branch) => storyDeployArgsProblems(branch, value, path).length === 0)
      ? [] : [`${path}: matches none of the allowed forms`]
  }
  if ('const' in node && value !== node.const) return [`${path}: must be ${JSON.stringify(node.const)}`]
  if (node.enum && !node.enum.includes(value)) return [`${path}: must be one of ${node.enum.join(', ')}`]
  if (node.type === 'string') {
    if (typeof value !== 'string') return [`${path}: must be a string`]
    if (node.minLength && value.length < node.minLength) return [`${path}: must not be empty`]
    if (node.pattern && !new RegExp(node.pattern).test(value)) return [`${path}: must match ${node.pattern}`]
    return []
  }
  if (node.type === 'integer') {
    if (!Number.isInteger(value)) return [`${path}: must be an integer`]
    return typeof node.minimum === 'number' && value < node.minimum ? [`${path}: must be at least ${node.minimum}`] : []
  }
  if (node.type === 'array') {
    if (!Array.isArray(value)) return [`${path}: must be an array`]
    return value.flatMap((entry, index) => storyDeployArgsProblems(node.items || {}, entry, `${path}[${index}]`))
  }
  if (node.type === 'object') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [`${path}: must be an object`]
    const properties = node.properties || {}
    const missing = (node.required || []).filter((key) => !(key in value)).map((key) => `${path}.${key}: is required`)
    const extra = node.additionalProperties === false
      ? Object.keys(value).filter((key) => !(key in properties)).map((key) => `${path}.${key}: is not an allowed key`)
      : []
    const fields = Object.keys(properties).filter((key) => key in value)
      .flatMap((key) => storyDeployArgsProblems(properties[key], value[key], `${path}.${key}`))
    return [...missing, ...extra, ...fields]
  }
  return []
}

// Parses one workflow's arguments against its schema definition: { ok, value, problems }.
const parseStoryDeployArgs = (name, args) => {
  const definition = STORY_DEPLOY_ARGS_DEFS[name]
  if (!definition) return { ok: false, value: null, problems: [`the schema defines no ${name}`] }
  const problems = storyDeployArgsProblems(definition, args, 'args')
  return { ok: problems.length === 0, value: problems.length === 0 ? args : null, problems }
}
const parseBuiltVersionArgs = (args) => parseStoryDeployArgs('BuiltVersionArgs', args)
const parseStoryDeployFixArgs = (args) => parseStoryDeployArgs('StoryDeployFixArgs', args)
const parseDeployMechanismArgs = (args) => parseStoryDeployArgs('DeployMechanismArgs', args)
// ===== SHARED BLOCK story-deploy-args — END =====
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

// This workflow's arguments are DeployMechanismArgs in the story-deploy-args shared block. The runtime
// adds its own keys (the fable, relay and retry keys), so only the keys that definition declares are parsed.
const COMPOSITE = 'deploy-mechanism'
const phaseTitle = (id) => compositePhaseTitle(COMPOSITE, id)
function enterPhase(id) {
  phase(phaseTitle(id))
}
const contractArgs = (definition, raw) => {
  const declared = (STORY_DEPLOY_ARGS_DEFS[definition] || {}).properties || {}
  return Object.fromEntries(Object.entries(raw && typeof raw === 'object' ? raw : {}).filter(([key]) => key in declared))
}
const parsedArgs = parseDeployMechanismArgs(contractArgs('DeployMechanismArgs', (typeof args === 'string' ? JSON.parse(args) : args) || {}))
const mechanismArgs = parsedArgs.value
const story = mechanismArgs ? mechanismArgs.story : null
const beadId = mechanismArgs ? String(mechanismArgs.beadId || story.id).trim() : ''
const repo = mechanismArgs ? mechanismArgs.repoPath.trim().replace(/\/+$/, '') : ''
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'

const handback = (ok, stage, headline, extra) => ({ ok, stage, beadId: beadId || null, headline: String(headline || ''), detailPath: null, ...(extra || {}) })

if (!parsedArgs.ok) return dispatchOutcome(handback(false, 'input', `the ${COMPOSITE} arguments break their contract: ${parsedArgs.problems.join('; ')}`))
if (!repo) return dispatchOutcome(handback(false, 'input', `no repository supplied for Story ${beadId}`))

enterPhase('ask')
const got = await settleAgent(
  `Story ${beadId}${story.title ? ` (${story.title})` : ''} is about to deploy from this repository:
${repo}

Rule what this repository publishes and deploys.

Return repository (the path exactly as given above), publishes, publishCommand (an empty list when publishes is false), deploys, and reason (the records and files that decide it, in a sentence or two).`,
  {
    label: 'deploy:mechanism',
    phase: phaseTitle('ask'),
    agentType: 'polyrepo-steward',
    effort: 'low',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['repository', 'publishes', 'publishCommand', 'deploys', 'reason'],
      properties: {
        repository: { type: 'string' },
        publishes: { type: 'boolean' },
        publishCommand: { type: 'array', items: { type: 'string' } },
        deploys: { type: 'boolean' },
        reason: { type: 'string' },
      },
    },
  }
)
if (!got) return dispatchOutcome(handback(false, DISPATCH_FAILED_STAGE, `the polyrepo-steward gave no ruling on what ${repo} publishes and deploys`))

const publishCommand = (Array.isArray(got.publishCommand) ? got.publishCommand : []).map((p) => String(p)).filter((p) => p.length)
const mechanism = {
  repository: repo,
  publishes: got.publishes === true,
  publishCommand,
  deploys: got.deploys === true,
  reason: String(got.reason || '').trim(),
}
const does = [mechanism.publishes ? `publishes (${publishCommand.join(' ') || 'no command named'})` : '', mechanism.deploys ? 'deploys with CDK' : ''].filter(Boolean)
return dispatchOutcome(handback(true, 'ask', `${repo}: ${does.length ? does.join(' and ') : 'publishes and deploys nothing'} — ${mechanism.reason}`.slice(0, 900), { mechanism }))
