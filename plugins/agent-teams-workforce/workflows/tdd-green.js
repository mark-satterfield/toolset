export const meta = {
  name: 'tdd-green',
  description:
    'Shared-tail mini — TDD Green. The implementation-lead selects the implementer(s) for the change unless the caller names one; the implementers write the minimum production code in sequence to make the failing tests pass, run the suite, and report Green. An implementer does not change tests: it names a test that contradicts the contract in testIssues, and a missing thing outside the Task in upstreamMissing. The brief of each implementer opens with the shared capabilities the contract carries (contract.sharedCapabilities): what the Task takes from a shared library, layer, chassis or service, and what each provides. With select it names the implementers and runs none; with only it runs that one of the implementers given.',
  phases: [{ title: 'Green', detail: 'minimum code to pass; confirm Green' }],
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

// Implementer agent types this mini may dispatch.
const IMPLEMENTER_ROSTER = [
  'chassis-extension-implementer',
  'power-tools-configuration-implementer',
  'api-gateway-cdk-implementer',
  'event-api-client-implementer',
  'event-driven-consumer-implementer',
  'dynamodb-access-layer-implementer',
  'postgresql-access-layer-implementer',
  'cognito-lambda-trigger-implementer',
  'webauthn-implementer',
  'payments-integration-implementer',
  'email-notification-implementer',
  'mcp-server-implementer',
  'bedrock-integration-implementer',
  'matching-algorithm-implementer',
  'recommendation-engine-implementer',
  'vector-search-embeddings-implementer',
  'behavioral-signals-implementer',
  'llm-observability-implementer',
  'sagemaker-implementer',
  'applied-ai-services-implementer',
  'agentcore-agent-implementer',
  'cds-ui-implementer',
  'nextjs-component-implementer',
  'appsync-client-subscription-implementer',
  'ios-swiftui-implementer',
  'android-compose-implementer',
  'react-native-implementer',
  'appsync-cdk-implementer',
  'glue-etl-implementer',
  'kinesis-stream-implementer',
  'dynamodb-streams-cdc-implementer',
  's3-data-lake-implementer',
  'athena-redshift-analytics-implementer',
  'cdk-stack-author',
]

// args: { contract, red, implementer?: string, implementers?: string[], feedback?: string,
//         select?: boolean (name the implementers and run none), only?: string (run only this one of them) }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const red = a.red || {}
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim() || '(repo path not provided)'
const beadId = (c.bead && c.bead.id) || null

const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '')
const strList = (v) => (Array.isArray(v) ? v.map((x) => str(x)).filter(Boolean) : [])
const isBugContract = !!(c.reproduction || c.rootCause)
const beadDescription = c.bead ? str(c.bead.description) : ''
const ac = Array.isArray(c.acceptanceCriteria) ? c.acceptanceCriteria : []
const acLine = (x, i) => {
  if (typeof x === 'string') return `${i + 1}. ${x.trim()}`
  if (x && typeof x === 'object' && (x.given || x.when || x.then)) {
    return `${i + 1}. GIVEN ${x.given || 'n/a'} WHEN ${x.when || 'n/a'} THEN ${x.then || 'n/a'}`
  }
  return `${i + 1}. ${JSON.stringify(x)}`
}
const decisionIds = [...new Set([...strList(c.decisionIds), ...strList(c.spec && c.spec.decisionIds)])]
const specBlock = (() => {
  const s = c.spec && typeof c.spec === 'object' ? c.spec : null
  const docs = s ? [...new Set([str(s.specPath), ...strList(s.specPaths)].filter(Boolean))] : []
  const lines = [
    docs.length ? `Spec documents:\n${docs.map((d) => `  - ${d}`).join('\n')}` : '',
    s && strList(s.specSections).length ? `Spec sections defining this work: ${strList(s.specSections).join(', ')}` : '',
    s && strList(s.requirementIds).length ? `Requirements satisfied: ${strList(s.requirementIds).join(', ')}` : '',
    decisionIds.length ? `Architecture views this work is designed against (paths relative to the arc42 folder): ${decisionIds.join(', ')}` : '',
    str(c.trdPath) ? `The Epic's TRD: ${str(c.trdPath)}` : '',
    s && strList(s.definitionOfDone).length ? `Definition of Done:\n${strList(s.definitionOfDone).map((d) => `  - ${d}`).join('\n')}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

// The design source of a web-ui Task: bundle (a cds bundle the owner supplied), cds (designed with the
// CDS design system) or none (no design change); a contract naming none takes bundle when it names a
// bundle and is otherwise left to the surfaces.
const cdsBundle = str(c.cdsBundlePath)
const cdsSpecs = strList(c.cdsBuildSpecs)
const designSource = DESIGN_SOURCES.includes(str(c.cdsDesignSource)) ? str(c.cdsDesignSource) : cdsBundle ? DESIGN_SOURCE.BUNDLE : ''
const cdsBlock = (() => {
  if (designSource === DESIGN_SOURCE.BUNDLE) {
    const lines = [
      `Design source: ${DESIGN_SOURCE.BUNDLE} (the cds bundle the owner supplied).`,
      cdsBundle ? `cds bundle: ${cdsBundle}` : '',
      cdsSpecs.length ? `cds build-spec items this Task implements:\n${cdsSpecs.map((x) => `  - ${x}`).join('\n')}` : '',
    ].filter(Boolean)
    return `\n\n${lines.join('\n')}`
  }
  if (designSource === DESIGN_SOURCE.CDS) {
    return `\n\nDesign source: ${DESIGN_SOURCE.CDS} (no mockup was supplied; the UI changes design).`
  }
  if (designSource === DESIGN_SOURCE.NONE) {
    return `\n\nDesign source: ${DESIGN_SOURCE.NONE} (the UI change has no design impact).`
  }
  return ''
})()

const RED_EVIDENCE_CHARS = 4000
const redEvidence = str(red.evidence)

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

// Consumed by both selector and implementer prompts; only an explicit caller grants this scope.
const scopeBlock = c.baselineRepairScope === 'affected-repository'
  ? `\n\nAssigned repair scope: affected-repository (every baseline suite failure in ${repo}).`
  : ''

const taskBlock = `${c.bead ? `${isBugContract ? 'Bug' : 'Task'} ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature implementation'}${
  beadDescription ? `\n\n${beadDescription}` : ''
}${isBugContract ? `\n\nReproduction: ${c.reproduction || 'n/a'}\nRoot cause: ${c.rootCause || 'n/a'}` : ''}${specBlock}${cdsBlock}${infraBlock}

Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}
${ac.length ? `\nAcceptance criteria this change satisfies:\n${ac.map(acLine).join('\n')}\n` : ''}
Failing test(s) to satisfy: ${(red.testFiles || []).join(', ') || 'n/a'}
Red evidence${redEvidence.length > RED_EVIDENCE_CHARS ? ` (first ${RED_EVIDENCE_CHARS} characters)` : ''}: ${redEvidence.slice(0, RED_EVIDENCE_CHARS) || 'n/a'}${scopeBlock}`

// The shared capabilities the contract carries (contract.sharedCapabilities, from atw-matrix uses --ids): what the
// Task takes from a shared library, layer, chassis or service, and what each provides.
const sharedCapabilities = (Array.isArray(c.sharedCapabilities) ? c.sharedCapabilities : []).filter((x) => x && typeof x === 'object' && str(x.name))
const capabilityLines = (capability) => {
  const providers = (Array.isArray(capability.providedBy) ? capability.providedBy : [])
    .map((row) => `${str(row && row.kind)} ${str(row && row.name)}${str(row && row.repository) ? ` in repository ${str(row.repository)}` : ''}`.trim())
    .filter(Boolean)
  const provides = (Array.isArray(capability.provides) ? capability.provides : []).map((entry) => {
    const face = entry && entry.interface && typeof entry.interface === 'object' ? `${str(entry.interface.kind)} ${str(entry.interface.name)}`.trim() : ''
    return `  - ${str(entry && entry.behaviour)}${face ? ` Interface: ${face}.` : ''}${str(entry && entry.consumersMust) ? ` You must: ${str(entry.consumersMust)}` : ''}`
  })
  return [`- ${str(capability.name)}${providers.length ? ` (provided by ${providers.join('; ')})` : ''}`, ...provides].join('\n')
}
const reuseBlock = sharedCapabilities.length
  ? `Shared capabilities this Task must use:
${sharedCapabilities.map(capabilityLines).join('\n')}

`
  : ''

const suiteCommand = str(c.suiteCommand)
const suiteBlock = suiteCommand
  ? `\n\nSuite command: \`cd "${repo}" && ${suiteCommand}\``
  : ''

const treeBlock = `Work tree: ${repo}`

phase('Green')

// Routing is a required contract, never an implicit chassis default.
function validImplementers(value) {
  if (!Array.isArray(value)) return null
  return value.length > 0 && value.every(name => IMPLEMENTER_ROSTER.includes(name))
    ? [...new Set(value)] : null
}
function routingFailure(reason) {
  return { ok: false, dispatchFailed: true, reason: `Implementer routing failed: ${reason}`, changedFiles: [],
    ledger: { phase: 'green', beadId, chosen: [], mode: 'invalid', ok: false } }
}
let implementers
let selectionMode
if (a.implementer !== undefined && a.implementer !== null && a.implementer !== '') {
  implementers = validImplementers([a.implementer])
  if (!implementers) return dispatchOutcome(routingFailure(`unsupported explicit implementer ${String(a.implementer)}; select from the implementation roster`))
  selectionMode = 'selected'
} else if (a.implementers !== undefined && a.implementers !== null) {
  implementers = validImplementers(a.implementers)
  if (!implementers) return dispatchOutcome(routingFailure('saved implementer selection is empty or contains unsupported names; supply a valid selection'))
  selectionMode = 'reused'
} else {
  const selection = await settleAgent(
    `Implementer roster: ${IMPLEMENTER_ROSTER.join(', ')}

${treeBlock}

${taskBlock}${sharedCapabilities.length ? `\n\nShared capabilities the implementers must use: ${sharedCapabilities.map((x) => str(x.name)).join(', ')}` : ''}${a.feedback ? `\n\nKnown suite failures and prior rulings:\n${a.feedback}` : ''}`,
    {
      label: 'green:select-implementers',
      effort: 'low',
      phase: 'Green',
      agentType: 'implementation-lead',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['implementers', 'rationale'],
        properties: {
          implementers: { type: 'array', items: { type: 'string' } },
          rationale: { type: 'string' },
        },
      },
    }
  )
  implementers = validImplementers(selection && selection.implementers)
  if (!implementers) return dispatchOutcome(routingFailure('the selector returned no valid complete selection; inspect its failure and supply supported implementers'))
  selectionMode = 'selected'
}

if (a.select === true) return dispatchOutcome({ implementers, mode: selectionMode })
const onlyImplementer = str(a.only)
if (onlyImplementer && !implementers.includes(onlyImplementer)) {
  return dispatchOutcome(routingFailure(`${onlyImplementer} is not one of the selected implementers (${implementers.join(', ')})`))
}
const implementersRun = onlyImplementer ? [onlyImplementer] : implementers

const GREEN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'greenConfirmed', 'noRegressions', 'evidence'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    greenConfirmed: { type: 'boolean' },
    noRegressions: { type: 'boolean' },
    evidence: { type: 'string' },
    testIssues: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['testId', 'kind', 'reason'],
        properties: {
          testId: { type: 'string' },
          kind: { type: 'string', enum: ['obsolete-by-contract', 'defect', 'missing-config'] },
          reason: { type: 'string' },
          contractRef: { type: 'string' },
        },
      },
    },
    upstreamMissing: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['what', 'evidence'],
        properties: {
          what: { type: 'string' },
          evidence: { type: 'string' },
        },
      },
    },
    notes: { type: 'string' },
  },
}

let green = null
const changedFiles = []
const testIssues = []
const upstreamMissing = []
const deadImplementers = []
for (const impl of implementersRun) {
  green = await settleAgent(
    `${reuseBlock}${treeBlock}${suiteBlock}

${taskBlock}${implementers.length > 1 ? `\n\nImplementers on this Task, in order: ${implementers.join(', ')}. You are ${impl}.` : ''}${a.feedback ? `\n\nFeedback from the previous attempt:\n${a.feedback}` : ''}`,
    {
      label: `green:${impl}`,
      phase: 'Green',
      agentType: impl,
      schema: GREEN_SCHEMA,
    }
  )
  if (!green) {
    deadImplementers.push(impl)
    break
  }
  if (Array.isArray(green.changedFiles)) changedFiles.push(...green.changedFiles)
  if (Array.isArray(green.testIssues)) testIssues.push(...green.testIssues.filter((x) => x && str(x.testId)))
  if (Array.isArray(green.upstreamMissing)) upstreamMissing.push(...green.upstreamMissing.filter((x) => x && str(x.what)))
}

const ledger = {
  phase: 'green',
  beadId,
  chosen: implementersRun,
  mode: selectionMode,
  ok: !!(green && green.greenConfirmed),
}

if (deadImplementers.length) {
  return dispatchOutcome({
    ok: false,
    dispatchFailed: true,
    reason: `implementer(s) ${deadImplementers.join(', ')} returned nothing`,
    changedFiles,
    ledger: { ...ledger, ok: false },
  })
}

const stoppedAt =
  green.greenConfirmed !== true || green.noRegressions !== true ? [str(green.notes), str(green.evidence).slice(-1500)].filter(Boolean).join(' | ') : ''
return dispatchOutcome({ ...green, changedFiles, testIssues, upstreamMissing, ...(stoppedAt ? { reason: stoppedAt } : {}), ledger })
