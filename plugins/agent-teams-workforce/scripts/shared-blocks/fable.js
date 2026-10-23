// skills/pipeline-contracts/schemas/driver-surface.schema.json, inlined by shared-blocks.mjs. DRIVER_SURFACE maps
// each x-constant of $defs.DriverEnvironment to its environment variable name and each x-values entry of
// $defs.RateLimitInfo to its wire value, so no workflow names a driver environment variable or a rate-limit value itself.
const DRIVER_SURFACE_SCHEMA = /* DRIVER_SURFACE_SCHEMA */ {}
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
// The plugin's agents that have no user-level copy (no mcpServers in their front matter), filled
// from agents/*.md by shared-blocks.mjs. Claude Code registers a plugin agent only under the
// plugin prefix, so such an agent is dispatched as agent-teams-workforce:<name>; an agent with a
// user-level copy keeps its plain name, which names that copy and the MCP servers it carries. A
// workflow names every agent by its plain front-matter name and atwAgentType resolves it here.
const PLUGIN_ONLY_AGENTS = new Set(/* PLUGIN_ONLY_AGENTS */ [])
const atwAgentType = (name) => (PLUGIN_ONLY_AGENTS.has(name) ? `agent-teams-workforce:${name}` : name)
// The Workflow runtime compiles agent({schema}) with Ajv's default (draft-07) class in strict mode:
// it has no draft 2020-12 meta-schema, so `$schema` naming 2020-12 is refused, an unknown keyword
// such as an `x-` annotation is refused, and `prefixItems` is unknown. runtimeSchema returns the
// contract with `$schema` and every `x-` annotation removed and `prefixItems` written as draft-07
// `items` (with a sibling `items` as `additionalItems`), walking only subschema positions so a
// property named `$schema` or `x-...` is kept. `$ref` into `$defs` compiles as it is.
const SCHEMA_MAP_KEYWORDS = new Set(['properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'])
const SCHEMA_LIST_KEYWORDS = new Set(['allOf', 'anyOf', 'oneOf', 'prefixItems'])
const SCHEMA_ONE_KEYWORDS = new Set(['items', 'additionalItems', 'additionalProperties', 'not', 'if', 'then', 'else', 'contains', 'propertyNames', 'unevaluatedProperties', 'unevaluatedItems'])
function runtimeSchema(schema) {
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return schema
  const out = {}
  for (const [key, value] of Object.entries(schema)) {
    if (key === '$schema' || key.startsWith('x-')) continue
    if (SCHEMA_MAP_KEYWORDS.has(key) && value && typeof value === 'object' && !Array.isArray(value)) out[key] = Object.fromEntries(Object.entries(value).map(([name, sub]) => [name, runtimeSchema(sub)]))
    else if ((SCHEMA_LIST_KEYWORDS.has(key) || key === 'items') && Array.isArray(value)) out[key] = value.map(runtimeSchema)
    else if (SCHEMA_ONE_KEYWORDS.has(key)) out[key] = runtimeSchema(value)
    else out[key] = value
  }
  if (Array.isArray(out.prefixItems)) {
    if (out.items !== undefined) out.additionalItems = out.items
    out.items = out.prefixItems
    delete out.prefixItems
  }
  return out
}
// Claude Code loads an agent's definition and preloads the skills its front matter lists, so
// nothing here reads or passes on an agent's or a skill's text.
async function fableAgent(prompt, options) {
  const schema = options && options.schema
  const artifactSchema = schema && schema.type === 'object' && Array.isArray(schema.required) && schema.required.length === 1 && schema.required[0] === 'artifactPath' && schema.properties && schema.properties.artifactPath && schema.properties.artifactPath.type === 'string'
  const outputMode = ['artifact', 'inline', 'machine'].includes(options && options.outputMode) ? options.outputMode : artifactSchema ? 'artifact' : 'inline'
  const { outputMode: _mode, ...runtimeOptions } = options || {}
  options = runtimeOptions
  const agentType = (options && options.agentType) || null
  const isFable = fableTypes.has(String(agentType || '').replace(/^agent-teams-workforce:/, ''))
  const typed = agentType ? { ...options, agentType: atwAgentType(agentType) } : options
  const resolved = schema ? { ...typed, schema: runtimeSchema(schema) } : typed
  const call = isFable && fableFallback ? { ...resolved, model: 'opus' } : resolved
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
