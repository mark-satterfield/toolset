// Generated from skills/artifact-handoff/schemas/story-deploy-args.schema.json, the one definition of the
// Story deploy workflow arguments. Never restate a key, value or shape of it in a workflow: read it from here.
const STORY_DEPLOY_ARGS_SCHEMA = /* STORY_DEPLOY_ARGS_SCHEMA */ {}
const STORY_DEPLOY_ARGS_DEFS = STORY_DEPLOY_ARGS_SCHEMA.$defs || {}
// Every top-level key of the four argument shapes, in schema order.
const ARG_KEYS = Object.freeze([...new Set(['StoryDeployInput', 'BuiltVersionArgs', 'StoryDeployFixArgs', 'DeployMechanismArgs']
  .flatMap((name) => Object.keys((STORY_DEPLOY_ARGS_DEFS[name] || {}).properties || {})))])
const FAILURE_STEPS = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.FailureStep || {}).enum || [])])
const VERIFIED_STACK_STATUSES = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.VerifiedStackStatus || {}).enum || [])])
const STORY_DEPLOY_COMPOSITES = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.Composite || {}).enum || [])])
const ITEM_KEYS = Object.freeze(Object.keys((STORY_DEPLOY_ARGS_DEFS.BuiltVersionItem || {}).properties || {}))

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
