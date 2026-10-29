#!/usr/bin/env node
// Check every agent output pairing: the agent definitions (and the skills that state the output)
// against the schema the orchestrator or the workflow validates that output with.
//
// Usage:  node scripts/check-agent-output-formats.mjs [--list]
// Exit:   0 = every pairing holds, 1 = at least one finding
//
// The pairings come from two places. skills/artifact-handoff/agent-outputs.json lists each
// output the orchestrator validates (an AgentLaunch's `validate`) and each file a workflow's
// agent writes to a contract file; each entry names the code that makes the pairing, and the
// check fails when that code no longer holds the entry's anchors. Every workflow dispatch that
// hands the runtime a structured-output schema is read from the workflow itself: an
// `agentType: '<name>'` and the `schema:` of the same call. A dispatch whose agentType is not a
// literal must be covered by an agent-outputs.json entry naming its locator.
//
// For each pairing it fails when:
// - the schema file, its $defs entry, the workflow constant or the anchored code is missing;
// - an agent, or a skill the entry names, is missing, or the agent does not load that skill;
// - a file output's agent definition and named skills do not point at the schema file;
// - the agent definition or a named skill writes a field path (`a.b`, `a[].b`) that does not
//   resolve in the schema, gives a field a shape (`field` {x, y}) its items do not have, writes a
//   brace shape `{x, y}` no object of the schema has, names in backticks a field another output
//   defines but this one does not, or holds a JSON example of the output with a field the
//   schema does not define.
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const TABLE_PATH = 'skills/artifact-handoff/agent-outputs.json'
const STRUCTURED = 'structured'
const RULE_TEXT = 'write exactly the shape that schema defines, and no other fields'
const RULE = new RegExp(RULE_TEXT.replace(/ /g, '\\s+'), 'i')
const FILE = 'file'
const findings = []
const fail = (where, what) => findings.push(`${where}: ${what}`)
const read = (rel) => readFileSync(path.join(ROOT, rel), 'utf8')

// ── Schemas ──────────────────────────────────────────────────────────────────

const documents = new Map()
function schemaDocument(rel) {
  if (!documents.has(rel)) documents.set(rel, JSON.parse(read(rel)))
  return documents.get(rel)
}

function pointer(doc, fragment) {
  let node = doc
  for (const part of fragment.replace(/^\//, '').split('/').filter(Boolean)) {
    const key = part.replace(/~1/g, '/').replace(/~0/g, '~')
    if (node === null || typeof node !== 'object' || !(key in node)) return undefined
    node = node[key]
  }
  return node
}

// A located schema node: the node and the file its local $refs resolve in (null for a literal).
function deref(at) {
  let { node, file } = at
  const seen = new Set()
  while (node && typeof node === 'object' && typeof node.$ref === 'string') {
    const key = `${file}|${node.$ref}`
    if (seen.has(key)) break
    seen.add(key)
    const [target, fragment = ''] = node.$ref.split('#')
    if (target) file = path.posix.join(path.posix.dirname(file), target)
    const doc = file ? schemaDocument(file) : at.root
    const next = pointer(doc, fragment)
    if (next === undefined) throw new Error(`unresolvable $ref ${node.$ref} in ${file}`)
    node = next
  }
  return { node, file, root: at.root }
}

// The object views of a node: the node itself and every branch it may take.
function views(at, seen = new Set()) {
  const here = deref(at)
  const { node } = here
  if (!node || typeof node !== 'object' || seen.has(node)) return []
  seen.add(node)
  const found = [here]
  for (const key of ['allOf', 'anyOf', 'oneOf']) {
    for (const branch of node[key] || []) found.push(...views({ ...here, node: branch }, seen))
  }
  for (const key of ['then', 'else']) {
    if (node[key] && typeof node[key] === 'object') found.push(...views({ ...here, node: node[key] }, seen))
  }
  return found
}

function properties(at) {
  const named = new Map()
  for (const view of views(at)) {
    for (const [key, value] of Object.entries(view.node.properties || {})) {
      if (value === false) continue
      if (!named.has(key)) named.set(key, [])
      named.get(key).push({ ...view, node: value })
    }
  }
  return named
}

function itemsOf(at) {
  const found = []
  for (const view of views(at)) {
    if (view.node.items && typeof view.node.items === 'object') found.push({ ...view, node: view.node.items })
  }
  return found
}

// Every object node reachable from a node, with its property names and required names.
function objects(at) {
  const found = []
  const seen = new Set()
  const walk = (current) => {
    for (const view of views(current)) {
      if (seen.has(view.node)) continue
      seen.add(view.node)
      if (view.node.properties) {
        found.push({ props: new Set(Object.keys(view.node.properties).filter(k => view.node.properties[k] !== false)), required: view.node.required || [], closed: view.node.additionalProperties === false })
        for (const value of Object.values(view.node.properties)) if (value && typeof value === 'object') walk({ ...view, node: value })
      }
      for (const key of ['items', 'additionalProperties']) {
        if (view.node[key] && typeof view.node[key] === 'object') walk({ ...view, node: view.node[key] })
      }
      for (const branch of view.node.prefixItems || []) walk({ ...view, node: branch })
    }
  }
  walk(at)
  return found
}

function allProperties(at) {
  const names = new Set()
  for (const object of objects(at)) for (const name of object.props) names.add(name)
  return names
}

// ── Workflow schemas ─────────────────────────────────────────────────────────

// The end of the balanced literal that opens at src[start] ({ or [), strings and comments skipped.
function literalEnd(src, start) {
  let depth = 0
  for (let i = start; i < src.length; i++) {
    const c = src[i]
    if (c === '/' && src[i + 1] === '/') { i = src.indexOf('\n', i); if (i < 0) return -1; continue }
    if (c === '/' && src[i + 1] === '*') { i = src.indexOf('*/', i) + 1; continue }
    if (c === '"' || c === "'" || c === '`') {
      for (i++; i < src.length && src[i] !== c; i++) if (src[i] === '\\') i++
      continue
    }
    if (c === '{' || c === '[') depth++
    if (c === '}' || c === ']') { depth--; if (depth === 0) return i + 1 }
  }
  return -1
}

function constLiteral(src, name) {
  const match = new RegExp(`^const ${name} = ([{\\[])`, 'm').exec(src)
  if (!match) return null
  const start = match.index + match[0].length - 1
  const end = literalEnd(src, start)
  return end < 0 ? null : src.slice(start, end)
}

// A value the schema reads at run time: any property, call or test of it gives itself.
const RUNTIME = new Proxy(function runtime() {}, { get: (_t, key) => (key === Symbol.toPrimitive ? () => '' : RUNTIME), apply: () => RUNTIME })

// Evaluate a literal, resolving each identifier it references from the file's own constants; an
// identifier that is no literal constant is a run-time value, which never decides a key.
function evaluate(src, text, depth = 0) {
  const names = []
  const values = []
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      return new Function(...names, `return (${text})`)(...values)
    } catch (error) {
      const missing = error instanceof ReferenceError && /^(\w+) is not defined/.exec(error.message)
      if (!missing || depth > 8) throw error
      const held = constLiteral(src, missing[1])
      const simple = new RegExp(`^const ${missing[1]} = ('[^'\\n]*'|"[^"\\n]*"|\\d+)`, 'm').exec(src)
      names.push(missing[1])
      values.push(held !== null ? evaluate(src, held, depth + 1) : simple ? JSON.parse(simple[1].replace(/^'|'$/g, '"')) : RUNTIME)
    }
  }
  throw new Error('too many references')
}

// Each dispatch of a workflow: its agentType expression and its schema expression or literal.
function dispatches(file) {
  const src = read(file)
  const found = []
  const typePattern = /agentType:\s*([^,}\n]+)/g
  let match
  while ((match = typePattern.exec(src))) {
    const expression = match[1].trim().replace(/\s*\/\/.*$/, '')
    if (/options|o\.agentType|opts\.agentType|^agentType$|atwAgentType|workflow-command-runner/.test(expression)) continue
    let open = match.index
    for (let depth = 0; open > 0; open--) {
      const c = src[open]
      if (c === '}') depth++
      if (c === '{') { if (depth === 0) break; depth-- }
    }
    const close = literalEnd(src, open)
    const body = src.slice(open, close)
    const schemaAt = /\bschema:\s*/.exec(body)
    const line = src.slice(0, match.index).split('\n').length
    if (!schemaAt) { found.push({ file, line, expression, schema: null }); continue }
    const valueStart = schemaAt.index + schemaAt[0].length
    let schema
    if (body[valueStart] === '{') {
      const end = literalEnd(body, valueStart)
      schema = { literal: body.slice(valueStart, end) }
    } else {
      schema = { name: /^[\w.]+/.exec(body.slice(valueStart))[0] }
    }
    found.push({ file, line, expression, schema, src })
  }
  const authorPattern = /\bauthor\(\s*[^,()]+,\s*([A-Z][A-Z0-9_]*),\s*('[a-z0-9-]+')/g
  while ((match = authorPattern.exec(src))) {
    const line = src.slice(0, match.index).split('\n').length
    found.push({ file, line, expression: match[2], schema: { name: match[1] }, src })
  }
  return found
}

function workflowSchema(dispatch) {
  if (dispatch.schema.literal) return evaluate(dispatch.src, dispatch.schema.literal)
  const text = constLiteral(dispatch.src, dispatch.schema.name)
  if (text === null) throw new Error(`${dispatch.schema.name} is not a constant of the workflow`)
  return evaluate(dispatch.src, text)
}

// ── Agents and skills ────────────────────────────────────────────────────────

function frontMatter(text) {
  const match = /^---\n([\s\S]*?)\n---\n/.exec(text)
  if (!match) return { list: () => [], body: text }
  const lines = match[1].split('\n')
  const list = (field) => {
    const out = []
    const start = lines.findIndex(l => l.startsWith(`${field}:`))
    if (start < 0) return out
    const inline = lines[start].slice(field.length + 1).trim()
    if (inline) return inline.replace(/^\[|\]$/g, '').split(',').map(s => s.trim()).filter(Boolean)
    for (let i = start + 1; i < lines.length && /^\s*- /.test(lines[i]); i++) out.push(lines[i].replace(/^\s*- /, '').trim())
    return out
  }
  return { list, body: text.slice(match[0].length) }
}

const agentFiles = new Map(readdirSync(path.join(ROOT, 'agents')).filter(f => f.endsWith('.md')).map(f => [f.slice(0, -3), `agents/${f}`]))
const agentCache = new Map()
function agent(name) {
  if (!agentCache.has(name)) {
    const text = read(agentFiles.get(name))
    const front = frontMatter(text)
    const skills = [...front.list('skills'), ...front.list('x-onDemandSkills')].map(s => s.replace(/^agent-teams-workforce:/, ''))
    agentCache.set(name, { body: front.body, skills: new Set(skills) })
  }
  return agentCache.get(name)
}

function skillText(name) {
  const rel = `skills/${name}/SKILL.md`
  return existsSync(path.join(ROOT, rel)) ? frontMatter(read(rel)).body : null
}

// ── Text checks ──────────────────────────────────────────────────────────────

const IDENT = /^[a-z][A-Za-z0-9]*$/
const CAMEL = /^[a-z]+[A-Z][A-Za-z0-9]*$/
const FILE_NAME = /\.(json|md|mjs|js|cjs|py|ya?ml|txt)$/
const PATH = /^([a-z][A-Za-z0-9]*)((?:\[\d*\])?(?:\.[a-z][A-Za-z0-9]*(?:\[\d*\])?)+)$/

function prose(text) {
  return text.replace(/^```[\s\S]*?^```/gm, '')
}

function resolvePath(at, segments) {
  let current = [at]
  for (const segment of segments) {
    const next = []
    for (const node of current) {
      if (segment === '[]') next.push(...itemsOf(node))
      else next.push(...(properties(node).get(segment) || []))
    }
    if (!next.length) return null
    current = next
  }
  return current
}

function braceKeys(text) {
  return text.split(',').map(part => part.trim().replace(/[:?].*$/, '').trim()).filter(Boolean)
}

// The problems of one text against one output, as distinct sentences that do not name the schema.
function textProblems(text, at, pairing, knownFields, own) {
  const problems = new Set()
  const fail = (key, what) => problems.add(`${key}\t${what}`)
  const top = properties(at)
  const shapes = objects(at)
  const tolerated = new Set([...own, ...(pairing.tolerate || [])])
  const body = prose(text)
  for (const span of body.matchAll(/`([^`\n]+)`/g)) {
    const token = span[1].trim()
    const pathMatch = PATH.exec(token)
    if (pathMatch && !FILE_NAME.test(token)) {
      if (!top.has(pathMatch[1])) { fail(`path ${token}`, SKIP); continue }
      const segments = [pathMatch[1], ...pathMatch[2].split(/(\[\d*\])|\./).filter(Boolean).map(s => (s.startsWith('[') ? '[]' : s))]
      if (!resolvePath(at, segments)) fail(`path ${token}`, `\`${token}\` is not a field path of the output`)
      continue
    }
    if (CAMEL.test(token) && knownFields.has(token) && !own.has(token) && !tolerated.has(token)) {
      fail(`field ${token}`, `\`${token}\` is a field of another agent output, not of this one`)
    }
    const brace = /^\{([^{}]+)\}$/.exec(token)
    if (brace) {
      const keys = braceKeys(brace[1])
      if (keys.every(k => IDENT.test(k)) && keys.some(k => own.has(k)) && !shapes.some(o => keys.every(k => o.props.has(k)))) {
        fail(`brace ${token}`, `\`${token}\` is not the shape of any object of the output`)
      }
    }
  }
  for (const shaped of body.matchAll(/`([a-z][A-Za-z0-9]*)`(?:\s*(?::|as|entries|entry|items|item|objects|object|of|holds|with|is|are|=|—|-))*\s*`?\{([^{}\n]+)\}/g)) {
    const field = shaped[1]
    const keys = braceKeys(shaped[2])
    if (!keys.every(k => IDENT.test(k)) || !own.has(field)) continue
    const targets = []
    const queue = [at]
    const seen = new Set()
    while (queue.length) {
      const node = queue.shift()
      for (const view of views(node)) {
        if (seen.has(view.node)) continue
        seen.add(view.node)
        for (const [key, values] of properties(view)) {
          if (key === field) for (const value of values) targets.push(value)
          for (const value of values) queue.push(value, ...itemsOf(value))
        }
      }
    }
    const fits = targets.some(target => {
      const candidates = [target, ...itemsOf(target)]
      return candidates.some(candidate => {
        const props = properties(candidate)
        if (!props.size) return false
        const required = views(candidate).flatMap(v => v.node.required || [])
        return keys.every(k => props.has(k)) && required.every(r => keys.includes(r))
      })
    })
    if (!own.has(field) || !targets.length) { fail(`shape ${field}`, SKIP); continue }
    if (!fits) fail(`shape ${field}`, `\`${field}\` {${keys.join(', ')}} is not the shape the output gives \`${field}\``)
  }
  let example = 0
  for (const block of text.matchAll(/^```json\n([\s\S]*?)^```/gm)) {
    let value
    try { value = JSON.parse(block[1]) } catch { continue }
    if (!value || typeof value !== 'object' || Array.isArray(value)) continue
    example++
    const keys = Object.keys(value)
    if (keys.filter(k => top.has(k)).length < 2) { fail(`example ${example}`, SKIP); continue }
    exampleProblems(value, at, '').forEach(problem => fail(`example ${example}`, `JSON example ${example}: ${problem}`))
  }
  return problems
}

const SKIP = 'not this output'

// The problems a text has against every output it may state, each problem as `<key>\t<message>`:
// a statement one output accepts is no problem; one that is not about an output (SKIP) fails it
// the way it fails the outputs it is about.
function commonProblems(sets) {
  const byKey = sets.map(set => {
    const keyed = new Map()
    for (const item of set) {
      const [key, message] = item.split('\t')
      if (!keyed.has(key)) keyed.set(key, [])
      keyed.get(key).push(message)
    }
    return keyed
  })
  const keys = new Set(byKey.flatMap(keyed => [...keyed.keys()]))
  const found = new Set()
  for (const key of keys) {
    if (byKey.some(keyed => !keyed.has(key))) continue
    const messages = byKey.flatMap(keyed => keyed.get(key)).filter(message => message !== SKIP)
    for (const message of messages) found.add(message)
  }
  return [...found]
}

function exampleProblems(value, at, trail) {
  const problems = []
  if (Array.isArray(value)) {
    const items = itemsOf(at)
    if (items.length) value.forEach((item, i) => problems.push(...exampleProblems(item, items[0], `${trail}[${i}]`)))
    return problems
  }
  if (!value || typeof value !== 'object') return problems
  const props = properties(at)
  const closed = views(at).some(v => v.node.additionalProperties === false)
  for (const [key, child] of Object.entries(value)) {
    if (!props.has(key)) { if (closed) problems.push(`${trail || '/'}: ${key} is not a field`); continue }
    problems.push(...exampleProblems(child, props.get(key)[0], `${trail}/${key}`))
  }
  return problems
}

// A full check of an example file against its schema: the subset of JSON Schema these schemas use.
function typeOf(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'array'
  if (Number.isInteger(value)) return 'integer'
  return typeof value
}

function conforms(value, at, trail = '') {
  const here = deref(at)
  const node = here.node
  if (node === true || node === undefined) return []
  if (node === false) return [`${trail || '/'}: no value is allowed`]
  const problems = []
  const sub = (child, t) => conforms(value, { ...here, node: child }, t)
  if (node.type) {
    const types = [].concat(node.type)
    const actual = typeOf(value)
    if (!types.includes(actual) && !(actual === 'integer' && types.includes('number'))) return [`${trail || '/'}: is ${actual}, not ${types.join(' or ')}`]
  }
  if ('const' in node && JSON.stringify(node.const) !== JSON.stringify(value)) problems.push(`${trail || '/'}: is not ${JSON.stringify(node.const)}`)
  if (Array.isArray(node.enum) && !node.enum.some(v => JSON.stringify(v) === JSON.stringify(value))) problems.push(`${trail || '/'}: ${JSON.stringify(value)} is not one of ${JSON.stringify(node.enum)}`)
  if (typeof value === 'string') {
    if (node.minLength && value.length < node.minLength) problems.push(`${trail || '/'}: is shorter than ${node.minLength}`)
    if (node.pattern && !new RegExp(node.pattern, 'u').test(value)) problems.push(`${trail || '/'}: does not match ${node.pattern}`)
  }
  if (Array.isArray(value)) {
    if (node.minItems && value.length < node.minItems) problems.push(`${trail || '/'}: has fewer than ${node.minItems} items`)
    if (node.items && typeof node.items === 'object') value.forEach((item, i) => problems.push(...conforms(item, { ...here, node: node.items }, `${trail}/${i}`)))
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const name of node.required || []) if (!(name in value)) problems.push(`${trail || '/'}: ${name} is missing`)
    const props = node.properties || {}
    for (const [key, child] of Object.entries(value)) {
      if (key in props) problems.push(...conforms(child, { ...here, node: props[key] }, `${trail}/${key}`))
      else if (node.additionalProperties === false) problems.push(`${trail || '/'}: ${key} is not a field`)
      else if (node.additionalProperties && typeof node.additionalProperties === 'object') problems.push(...conforms(child, { ...here, node: node.additionalProperties }, `${trail}/${key}`))
    }
  }
  for (const branch of node.allOf || []) problems.push(...sub(branch, trail))
  if (node.anyOf && !node.anyOf.some(branch => !sub(branch, trail).length)) problems.push(`${trail || '/'}: matches none of anyOf`)
  if (node.oneOf && node.oneOf.filter(branch => !sub(branch, trail).length).length !== 1) problems.push(`${trail || '/'}: does not match exactly one of oneOf`)
  if (node.if) {
    const holds = !sub(node.if, trail).length
    if (holds && node.then) problems.push(...sub(node.then, trail))
    if (!holds && node.else) problems.push(...sub(node.else, trail))
  }
  return problems
}

// ── Pairings ─────────────────────────────────────────────────────────────────

function locate(schemaRef) {
  const [file, fragment = ''] = schemaRef.split('#')
  if (file.startsWith('workflows/')) {
    const named = fragment
    const src = read(file)
    const text = constLiteral(src, named)
    if (text === null) throw new Error(`${named} is not a constant of ${file}`)
    const root = evaluate(src, text)
    return { node: root, file: null, root }
  }
  if (!existsSync(path.join(ROOT, file))) throw new Error(`${file} does not exist`)
  const doc = schemaDocument(file)
  const node = pointer(doc, fragment)
  if (node === undefined) throw new Error(`${file} has no ${fragment}`)
  return { node, file, root: doc }
}

function strings(value) {
  if (typeof value === 'string') return [value]
  if (value && typeof value === 'object') return Object.values(value).flatMap(strings)
  return []
}

// The agents of an entry: those it names, the agent names held in the workflow constants it
// names (`agentsFrom`, as file#CONSTANT), and every agent that loads the skill it names.
function agentsOf(entry, where) {
  const named = new Set(entry.agents || [])
  for (const ref of entry.agentsFrom || []) {
    const [file, constant] = ref.split('#')
    const text = constLiteral(read(file), constant)
    if (text === null) { fail(where, `${file} has no constant ${constant}`); continue }
    for (const value of strings(evaluate(read(file), text))) if (agentFiles.has(value)) named.add(value)
  }
  if (entry.agentsLoading) {
    const loading = [...agentFiles.keys()].filter(name => agent(name).skills.has(entry.agentsLoading))
    if (!loading.length) fail(where, `no agent loads ${entry.agentsLoading}`)
    for (const name of loading) named.add(name)
  }
  if (!named.size) fail(where, 'names no agent')
  return [...named]
}

const table = JSON.parse(read(TABLE_PATH))
const pairings = []
const covered = new Set()
for (const entry of table.pairings) {
  const where = `${TABLE_PATH} ${entry.output}`
  if (!existsSync(path.join(ROOT, entry.code))) { fail(where, `${entry.code} does not exist`); continue }
  const code = read(entry.code)
  for (const anchor of entry.anchors) if (!code.includes(anchor)) fail(where, `${entry.code} no longer holds ${anchor}`)
  if (entry.locator) covered.add(entry.locator)
  pairings.push({ ...entry, agents: agentsOf(entry, where), where })
}

for (const file of readdirSync(path.join(ROOT, 'workflows')).filter(f => f.endsWith('.js')).sort()) {
  for (const dispatch of dispatches(`workflows/${file}`)) {
    if (!dispatch.schema || dispatch.schema.name === 'relayKit.ARTIFACT_SCHEMA') continue
    const literal = /^'([a-z0-9-]+)'$/.exec(dispatch.expression)
    const locator = `${dispatch.file}:${dispatch.schema.name || `${literal ? literal[1] : dispatch.expression}`}`
    if (!literal) {
      if (!covered.has(locator)) fail(`${dispatch.file}:${dispatch.line}`, `agentType ${dispatch.expression} is not a literal and ${TABLE_PATH} has no entry with locator ${locator}`)
      continue
    }
    if (covered.has(locator)) continue
    let root
    try { root = workflowSchema(dispatch) } catch (error) { fail(`${dispatch.file}:${dispatch.line}`, `schema not readable: ${error.message}`); continue }
    pairings.push({
      output: `${literal[1]} structured output`, where: `${dispatch.file}:${dispatch.line}`, agents: [literal[1]], skills: [],
      schema: `${dispatch.file}:${dispatch.line}`, pointer: STRUCTURED, at: { node: root, file: null, root },
    })
  }
}

for (const pairing of pairings) {
  if (!pairing.at) {
    try { pairing.at = locate(pairing.schema) } catch (error) { fail(pairing.where, error.message); pairing.broken = true }
  }
  if (pairing.locator && !pairing.broken && pairing.locator.startsWith('workflows/')) {
    const [file, name] = pairing.locator.split(':')
    if (!dispatches(file).some(d => d.schema && (d.schema.name === name))) fail(pairing.where, `${file} dispatches nothing with schema ${name}`)
  }
}

const knownFields = new Set()
for (const pairing of pairings) if (!pairing.broken) for (const name of allProperties(pairing.at)) knownFields.add(name)

const EXCLUDED = new Set(table.notOwned || [])
for (const pairing of pairings) {
  if (pairing.broken) continue
  pairing.own = allProperties(pairing.at)
  for (const name of pairing.inputs || []) {
    try { for (const field of allProperties(locate(name))) pairing.own.add(field) } catch (error) { fail(pairing.where, error.message) }
  }
}
// What one agent's definition may name: every field of every output it writes and input it reads.
const agentOwn = new Map()
for (const pairing of pairings) {
  if (pairing.broken) continue
  for (const name of pairing.agents) {
    if (!agentOwn.has(name)) agentOwn.set(name, new Set())
    for (const field of [...pairing.own, ...(pairing.tolerate || [])]) agentOwn.get(name).add(field)
  }
}

const agentPairings = new Map()
for (const pairing of pairings) {
  if (pairing.broken) continue
  const skillTexts = []
  for (const skill of pairing.skills || []) {
    const text = skillText(skill)
    if (text === null) { fail(pairing.where, `skill ${skill} does not exist`); continue }
    skillTexts.push({ skill, text })
    for (const problem of commonProblems([textProblems(text, pairing.at, pairing, knownFields, pairing.own)])) {
      fail(`skills/${skill}/SKILL.md`, `${problem} (${pairing.output}, ${pairing.schema})`)
    }
  }
  for (const example of pairing.examples || []) {
    if (!existsSync(path.join(ROOT, example))) { fail(pairing.where, `${example} does not exist`); continue }
    for (const problem of conforms(JSON.parse(read(example)), pairing.at)) fail(example, `${problem} (${pairing.schema})`)
  }
  const fileName = pairing.pointer === FILE ? (pairing.named || path.posix.basename(pairing.schema.split('#')[0])) : null
  for (const name of pairing.agents) {
    if (!agentFiles.has(name)) { fail(pairing.where, `agent ${name} does not exist`); continue }
    if (EXCLUDED.has(name)) continue
    const held = agent(name)
    for (const skill of pairing.skills || []) if (!held.skills.has(skill)) fail(`agents/${name}.md`, `does not load ${skill}, which states its ${pairing.output}`)
    if (fileName && !held.body.includes(fileName) && !skillTexts.some(s => s.text.includes(fileName))) {
      fail(`agents/${name}.md`, `does not point at ${fileName} for its ${pairing.output}`)
    }
    if (fileName && ![held.body, ...skillTexts.map(s => s.text)].some(text => RULE.test(text))) {
      fail(`agents/${name}.md`, `does not state, with its pointer to ${fileName}, the rule "${RULE_TEXT}"`)
    }
    if (!agentPairings.has(name)) agentPairings.set(name, [])
    agentPairings.get(name).push(pairing)
  }
}
for (const [name, held] of agentPairings) {
  const body = agent(name).body
  const sets = held.map(pairing => textProblems(body, pairing.at, pairing, knownFields, agentOwn.get(name)))
  const outputs = held.map(pairing => `${pairing.output} (${pairing.schema})`).join('; ')
  for (const problem of commonProblems(sets)) fail(`agents/${name}.md`, `${problem}: ${outputs}`)
}

if (process.argv.includes('--list')) {
  for (const pairing of pairings) console.log(`${pairing.agents.length > 3 ? `${pairing.agents.length} agents` : pairing.agents.join(', ')}  →  ${pairing.schema}  (${pairing.output})`)
}
for (const finding of findings) console.log(`FAIL  ${finding}`)
console.log(findings.length ? `\n${findings.length} finding(s) across ${pairings.length} pairings` : `${pairings.length} pairings hold`)
process.exit(findings.length ? 1 : 0)
