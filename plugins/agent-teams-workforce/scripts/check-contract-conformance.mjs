#!/usr/bin/env node
// Check that every deterministic checker of an agent's output enforces only rules its producer is
// told, and that every reader of saved state reads only what its writer's schema defines.
//
// Usage:  node scripts/check-contract-conformance.mjs [--list]
// Exit:   0 = every checker and reader conforms, 1 = at least one finding
//
// The registry is skills/artifact-handoff/checker-rules.json. check-agent-output-formats.mjs
// checks the shape of each output against its schema; this script checks the rest of what a
// checker refuses.
//
// Checkers. Each entry names a checker: the functions that make it (`file#function`, a nested
// function as `file#outer.inner`), the agents whose output it checks (named, or every agent that
// loads the skill `agentsLoading` names; a rule may name its own),
// and each rule it enforces:
// a text the checker's code holds (`enforced`) and the text that states the rule in the rule's
// one instruction home (`stated` in `home`). It fails when:
// - a function is missing, or a rule's `enforced` text is in none of the checker's functions;
// - the home does not state the rule (in a JSON schema, its descriptions are read);
// - an agent does not reach the home: it neither loads the home's skill nor names the home's
//   file in its definition or in a skill it loads;
// - a message the checker's code writes (a string literal of three or more words) holds no rule's
//   `enforced` text and is not listed under the entry's `notRules`;
// - the checker calls a checking helper (a plugin function named validate*, check*, *_check,
//   *_problems, *_errors, *_findings, *_defects or *_document, or one whose body collects a list
//   of problems or errors) that the entry does not list and no other entry or `schemaOnly` names.
// Every checker in the code must be registered: each function an orchestrator flow passes as an
// AgentLaunch's `validate`, and each workflow call that the registry's `discover` patterns match
// (for example `regressionInvoke(step, 'check'`), must be an entry's function or invocation, or a
// `schemaOnly` validator (one that applies only a schema, which check-agent-output-formats.mjs
// checks).
//
// Readers. Each entry names code that reads saved state and the schema of the writer that writes
// it. For Python functions, every identifier-like string the functions use as a key must be a
// property or enum value of that schema (or `tolerate`d); for JavaScript, every property read on
// a named variable, in the region of the file between the entry's two `between` texts, must be a
// property of the schema definition the variable holds.
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const REGISTRY = 'skills/artifact-handoff/checker-rules.json'
const FLOWS = 'orchestrator/flows'
const PYTHON_DIRS = ['orchestrator', 'scripts/portfolio', ...readdirSync(path.join(ROOT, 'skills')).map(s => `skills/${s}/scripts`)]
const HELPER = /^(problems|errors|validate\w*|check\w*|\w+_check|\w+_problems|\w+_errors|\w+_findings|\w+_defects|\w+_document)$/
const MESSAGE_WORDS = 3
const COLLECTS = /\b(problems|errors|defects|findings|unresolved|refused)\b\s*(\.append\(|\.extend\(|:\s*list\[|=\s*\[)/
const findings = []
const fail = (where, what) => findings.push(`${where}: ${what}`)
const read = (rel) => readFileSync(path.join(ROOT, rel), 'utf8')
const exists = (rel) => existsSync(path.join(ROOT, rel))
const normal = (text) => text.replace(/[`*_]/g, '').replace(/\s+/g, ' ').trim().toLowerCase()

// ── Python source ────────────────────────────────────────────────────────────

// Every string literal of a Python source, with its start and end offsets and whether it is
// triple-quoted; comments are skipped.
function pyStrings(src) {
  const found = []
  for (let i = 0; i < src.length; i++) {
    const c = src[i]
    if (c === '#') { const end = src.indexOf('\n', i); i = end < 0 ? src.length : end; continue }
    if (c !== '"' && c !== "'") continue
    const prefix = /[rRbBfFuU]{0,2}$/.exec(src.slice(Math.max(0, i - 2), i))[0]
    const start = i - prefix.length
    const triple = src.startsWith(c.repeat(3), i)
    const close = triple ? c.repeat(3) : c
    let j = i + close.length
    while (j < src.length && !src.startsWith(close, j)) {
      if (src[j] === '\\') j++
      else if (!triple && src[j] === '\n') break
      j++
    }
    found.push({ start, end: j + close.length, triple, text: src.slice(i + close.length, j), f: /f/i.test(prefix) })
    i = j + close.length - 1
  }
  return found
}

// The functions of a Python file: each with its qualified name, its body text and its body offsets.
const pyCache = new Map()
function pyFunctions(rel) {
  if (pyCache.has(rel)) return pyCache.get(rel)
  const src = read(rel)
  const lines = src.split('\n')
  const offsets = []
  let total = 0
  for (const line of lines) { offsets.push(total); total += line.length + 1 }
  const functions = new Map()
  const stack = []
  for (let n = 0; n < lines.length; n++) {
    const match = /^(\s*)(?:async\s+)?def\s+(\w+)\s*\(/.exec(lines[n])
    if (!match) continue
    const indent = match[1].length
    while (stack.length && stack[stack.length - 1].indent >= indent) stack.pop()
    let depth = 0
    let open = n
    for (; open < lines.length; open++) {
      for (const ch of lines[open].replace(/#.*$/, '')) { if ('([{'.includes(ch)) depth++; if (')]}'.includes(ch)) depth-- }
      if (depth <= 0 && /:\s*(#.*)?$/.test(lines[open])) break
    }
    let last = open
    for (let k = open + 1; k < lines.length; k++) {
      if (!lines[k].trim()) continue
      if (/^\s*/.exec(lines[k])[0].length <= indent) break
      last = k
    }
    const name = [...stack.map(s => s.name), match[2]].join('.')
    const start = offsets[open + 1] ?? src.length
    const end = (offsets[last] ?? src.length) + (lines[last] || '').length
    functions.set(name, { name, start, end, body: src.slice(start, end) })
    stack.push({ indent, name })
  }
  const entry = { src, functions }
  pyCache.set(rel, entry)
  return entry
}

let pyIndex = null
// Every top-level function of the plugin's Python, by name: the files that define it.
function pythonIndex() {
  if (pyIndex) return pyIndex
  pyIndex = new Map()
  for (const dir of PYTHON_DIRS) {
    if (!exists(dir)) continue
    const walk = (rel) => {
      for (const name of readdirSync(path.join(ROOT, rel), { withFileTypes: true })) {
        const child = `${rel}/${name.name}`
        if (name.isDirectory()) { if (name.name !== '__pycache__') walk(child); continue }
        if (!name.name.endsWith('.py')) continue
        for (const fn of pyFunctions(child).functions.keys()) {
          if (fn.includes('.')) continue
          if (!pyIndex.has(fn)) pyIndex.set(fn, [])
          pyIndex.get(fn).push(child)
        }
      }
    }
    walk(dir)
  }
  return pyIndex
}

// The plugin function a name used in `rel` names: a function of the same file (a nested one of
// `outer` first), else the function of that name in the module the file imports it from.
function resolvePy(rel, name, outer, module) {
  const own = pyFunctions(rel)
  if (!module) {
    if (outer && own.functions.has(`${outer}.${name}`)) return `${rel}#${outer}.${name}`
    if (own.functions.has(name)) return `${rel}#${name}`
  }
  const alias = module ? null : new RegExp(`^from\\s+([\\w.]+)\\s+import\\s+(\\w+)\\s+as\\s+${name}\\b`, 'm').exec(own.src)
  if (alias) return resolvePy(rel, alias[2], null, alias[1])
  const files = pythonIndex().get(name) || []
  const imported = module || (new RegExp(`^from\\s+([\\w.]+)\\s+import\\s+(?:\\([^)]*\\b${name}\\b|[^\\n]*\\b${name}\\b)`, 'm').exec(own.src) || [])[1]
  if (imported) {
    const leaf = imported.split('.').pop()
    const hit = files.find(file => path.posix.basename(file, '.py') === leaf)
    if (hit) return `${hit}#${name}`
  }
  return null
}

// The identifiers a Python body calls or refers to that are plugin functions: a bare name, or
// module.name for a module the file imports.
function pyReferences(rel, body, outer) {
  const src = pyFunctions(rel).src
  const modules = new Set([...src.matchAll(/^import\s+(\w+)/gm)].map(m => m[1]))
  const found = new Set()
  const stripped = body.replace(/("""|''')[\s\S]*?\1/g, '').replace(/"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/g, '""')
  for (const match of stripped.matchAll(/(?<![\w.])(\w+)\.(\w+)|(?<![\w.])(\w+)\b/g)) {
    const resolved = match[1] ? (modules.has(match[1]) ? resolvePy(rel, match[2], outer, match[1]) : null) : resolvePy(rel, match[3], outer, null)
    if (resolved) found.add(resolved)
  }
  return found
}

// The messages a Python body writes: each run of adjacent single-line string literals joined, with
// three or more words outside its {placeholders}.
function pyMessages(body) {
  const messages = []
  let current = null
  for (const literal of pyStrings(body)) {
    if (literal.triple) { current = null; continue }
    if (current && /^[\s\\()]*$/.test(body.slice(current.end, literal.start))) {
      current.text += literal.text
      current.end = literal.end
      continue
    }
    current = { text: literal.text, end: literal.end }
    messages.push(current)
  }
  return messages.map(m => m.text).filter(text => text.replace(/\{[^}]*\}/g, ' ').split(/\s+/).filter(w => /[A-Za-z]/.test(w)).length >= MESSAGE_WORDS)
}

// ── JavaScript source ────────────────────────────────────────────────────────

function jsFunction(src, name) {
  const match = new RegExp(`(?:function\\s+${name}\\s*\\(|(?:const|let)\\s+${name}\\s*=)`).exec(src)
  if (!match) return null
  const open = src.indexOf('{', match.index)
  let depth = 0
  for (let i = open; i < src.length; i++) {
    if (src[i] === '{') depth++
    if (src[i] === '}' && --depth === 0) return src.slice(open, i + 1)
  }
  return null
}

// ── Homes ────────────────────────────────────────────────────────────────────

function descriptions(node, out = []) {
  if (Array.isArray(node)) node.forEach(n => descriptions(n, out))
  else if (node && typeof node === 'object') for (const [key, value] of Object.entries(node)) { if (key === 'description' && typeof value === 'string') out.push(value); else descriptions(value, out) }
  return out
}

const homeCache = new Map()
function homeText(rel) {
  if (!homeCache.has(rel)) homeCache.set(rel, normal(rel.endsWith('.json') ? descriptions(JSON.parse(read(rel))).join(' ') : read(rel)))
  return homeCache.get(rel)
}

function frontList(text, field) {
  const match = /^---\n([\s\S]*?)\n---\n/.exec(text)
  if (!match) return []
  const lines = match[1].split('\n')
  const at = lines.findIndex(l => l.startsWith(`${field}:`))
  if (at < 0) return []
  const inline = lines[at].slice(field.length + 1).trim()
  if (inline) return inline.replace(/^\[|\]$/g, '').split(',').map(s => s.trim()).filter(Boolean)
  const out = []
  for (let i = at + 1; i < lines.length && /^\s*- /.test(lines[i]); i++) out.push(lines[i].replace(/^\s*- /, '').trim())
  return out
}

function agentReaches(agent, home) {
  const rel = `agents/${agent}.md`
  if (!exists(rel)) return `agent ${agent} does not exist`
  if (home === rel) return null
  const text = read(rel)
  const skills = [...frontList(text, 'skills'), ...frontList(text, 'x-onDemandSkills')].map(s => s.replace(/^agent-teams-workforce:/, ''))
  const skill = /^skills\/([^/]+)\/SKILL\.md$/.exec(home)
  if (skill && (skills.includes(skill[1]) || text.includes(`\`${skill[1]}\``))) return null
  const base = path.posix.basename(home)
  const loaded = skills.map(s => `skills/${s}/SKILL.md`).filter(exists).map(read)
  if ([text, ...loaded].some(t => t.includes(base))) return null
  return `does not reach ${home}, which states rules its output is checked against: it neither loads that skill nor names ${base}`
}

// ── Checkers ─────────────────────────────────────────────────────────────────

// The agents of an entry: those it names, and every agent that loads the skill `agentsLoading` names.
function agentsOf(entry) {
  const named = new Set(entry.agents || [])
  if (entry.agentsLoading) {
    for (const file of readdirSync(path.join(ROOT, 'agents')).filter(f => f.endsWith('.md'))) {
      const text = read(`agents/${file}`)
      const skills = [...frontList(text, 'skills'), ...frontList(text, 'x-onDemandSkills')].map(s => s.replace(/^agent-teams-workforce:/, ''))
      if (skills.includes(entry.agentsLoading)) named.add(file.slice(0, -3))
    }
    if (!named.size) fail(`${REGISTRY} ${entry.checker}`, `no agent loads ${entry.agentsLoading}`)
  }
  return [...named]
}

const registry = JSON.parse(read(REGISTRY))
const registered = new Map()
for (const entry of registry.checkers) for (const fn of entry.functions) registered.set(fn, entry)
const schemaOnly = new Set(registry.schemaOnly.map(s => s.function))
for (const held of registry.schemaOnly) {
  const [file, name] = held.function.split('#')
  if (!exists(file) || !pyFunctions(file).functions.has(name)) fail(REGISTRY, `schemaOnly ${held.function} does not exist`)
}

// A checking helper: a plugin function named as one (HELPER), or one whose body collects problems.
function checking(ref) {
  const [file, name] = ref.split('#')
  if (HELPER.test(name.split('.').pop())) return true
  const held = pyFunctions(file).functions.get(name)
  return Boolean(held && COLLECTS.test(held.body))
}

function body(ref) {
  const [file, name] = ref.split('#')
  if (!exists(file)) return null
  if (file.endsWith('.py')) return pyFunctions(file).functions.get(name)?.body ?? null
  return jsFunction(read(file), name)
}

const invocations = new Set()
for (const entry of registry.checkers) {
  const where = `${REGISTRY} ${entry.checker}`
  const bodies = []
  for (const ref of entry.functions) {
    const text = body(ref)
    if (text === null) { fail(where, `${ref} does not exist`); continue }
    bodies.push({ ref, text })
  }
  for (const call of entry.invokedAs || []) invocations.add(call)
  const all = bodies.map(b => b.text).join('\n')
  const joined = bodies.filter(b => b.ref.includes('.py#')).flatMap(b => pyMessages(b.text))
  for (const rule of entry.rules) {
    const label = `${where} rule ${rule.id}`
    if (!all.includes(rule.enforced) && !joined.some(message => message.includes(rule.enforced))) fail(label, `no function of the checker holds ${JSON.stringify(rule.enforced)}`)
    if (!exists(rule.home)) { fail(label, `home ${rule.home} does not exist`); continue }
    if (!homeText(rule.home).includes(normal(rule.stated))) fail(label, `${rule.home} does not state ${JSON.stringify(rule.stated)}`)
    for (const agent of rule.agents || agentsOf(entry)) {
      const problem = agentReaches(agent, rule.home)
      if (problem) fail(`agents/${agent}.md`, `${problem} (${entry.checker}, rule ${rule.id})`)
    }
  }
  const anchors = [...entry.rules.map(r => r.enforced), ...(entry.notRules || [])]
  const written = new Set()
  for (const { ref, text } of bodies) {
    if (!ref.includes('.py#')) continue
    const [file, name] = ref.split('#')
    const own = pyFunctions(file).functions
    const nested = [...own.values()].filter(f => f.name.startsWith(`${name}.`))
    const flat = nested.reduce((held, f) => held.replace(f.body, ''), text)
    for (const message of pyMessages(flat)) {
      if (written.has(message) || anchors.some(anchor => message.includes(anchor))) continue
      written.add(message)
      fail(`${ref}`, `writes ${JSON.stringify(message)}, which no rule of ${entry.checker} names: register the rule with its instruction home, or list it under notRules`)
    }
    const outer = name.includes('.') ? name.split('.').slice(0, -1).join('.') : name
    for (const used of pyReferences(file, flat, outer)) {
      if (used === ref || !checking(used)) continue
      if (!entry.functions.includes(used) && !registered.has(used) && !schemaOnly.has(used)) {
        fail(ref, `calls the checking helper ${used}, which ${entry.checker} does not list and no entry registers`)
      }
    }
  }
}

// Every function an orchestrator flow hands an AgentLaunch as its `validate` is registered.
for (const file of readdirSync(path.join(ROOT, FLOWS)).filter(f => f.endsWith('.py')).sort()) {
  const rel = `${FLOWS}/${file}`
  const { src, functions } = pyFunctions(rel)
  for (const match of src.matchAll(/\bAgentLaunch\(/g)) {
    const open = match.index + match[0].length - 1
    let depth = 0
    let close = open
    for (; close < src.length; close++) { if ('([{'.includes(src[close])) depth++; if (')]}'.includes(src[close]) && --depth === 0) break }
    const call = src.slice(open, close)
    const at = /\bvalidate=/.exec(call)
    if (!at) continue
    let end = at.index + at[0].length
    for (let d = 0; end < call.length; end++) { if ('([{'.includes(call[end])) d++; if (')]}'.includes(call[end])) d--; if (d < 0 || (d === 0 && call[end] === ',')) break }
    const expression = call.slice(at.index + at[0].length, end)
    const enclosing = [...functions.values()].filter(f => f.start <= match.index && match.index <= f.end).sort((a, b) => b.start - a.start)[0]
    const line = src.slice(0, match.index).split('\n').length
    for (const used of pyReferences(rel, expression, enclosing ? enclosing.name : null)) {
      if (!registered.has(used) && !schemaOnly.has(used)) fail(`${rel}:${line}`, `${used} checks an agent's output (validate=) and no ${REGISTRY} entry registers it`)
    }
  }
}

// Every workflow call a discover pattern matches is an entry's invocation.
for (const pattern of registry.discover) {
  const files = readdirSync(path.join(ROOT, 'workflows')).filter(f => f.endsWith('.js')).map(f => `workflows/${f}`)
  for (const file of files) {
    for (const match of read(file).matchAll(new RegExp(pattern.pattern, 'g'))) {
      const key = pattern.key.replace(/\{(\d)\}/g, (_m, i) => match[Number(i)])
      if (!invocations.has(key)) fail(`${file}:${read(file).slice(0, match.index).split('\n').length}`, `${key} checks an agent's output and no ${REGISTRY} entry lists it under invokedAs`)
    }
  }
}

// ── Readers ──────────────────────────────────────────────────────────────────

function pointer(doc, fragment) {
  let node = doc
  for (const part of fragment.replace(/^\//, '').split('/').filter(Boolean)) {
    if (!node || typeof node !== 'object' || !(part in node)) return undefined
    node = node[part]
  }
  return node
}

function schemaNames(node, out = { props: new Set(), values: new Set() }) {
  if (Array.isArray(node)) node.forEach(n => schemaNames(n, out))
  else if (node && typeof node === 'object') {
    if (node.properties && typeof node.properties === 'object') for (const key of Object.keys(node.properties)) out.props.add(key)
    for (const value of [...(node.enum || []), ...('const' in node ? [node.const] : [])]) if (typeof value === 'string') out.values.add(value)
    Object.values(node).forEach(n => schemaNames(n, out))
  }
  return out
}

function located(ref) {
  const [file, fragment = ''] = ref.split('#')
  const doc = JSON.parse(read(file))
  let node = pointer(doc, fragment)
  for (let hops = 0; node && node.$ref && hops < 8; hops++) node = pointer(doc, node.$ref.replace(/^#/, ''))
  return node
}

for (const reader of registry.readers) {
  const where = `${REGISTRY} reader ${reader.reader}`
  if (!exists(reader.reader)) { fail(where, `${reader.reader} does not exist`); continue }
  const tolerated = new Set(reader.tolerate || [])
  if (reader.reader.endsWith('.py')) {
    if (!exists(reader.schema.split('#')[0])) { fail(where, `${reader.schema} does not exist`); continue }
    const names = schemaNames(located(reader.schema))
    for (const fn of reader.functions) {
      const held = pyFunctions(reader.reader).functions.get(fn)
      if (!held) { fail(where, `${fn} does not exist`); continue }
      for (const literal of pyStrings(held.body)) {
        if (literal.triple || literal.f || !/^[a-z][A-Za-z0-9]*$/.test(literal.text)) continue
        const after = held.body.slice(literal.end, literal.end + 1)
        const before = held.body.slice(Math.max(0, literal.start - 5), literal.start)
        const key = (/\[$/.test(before) && after === ']') || (/get\($/.test(before) && /[),]/.test(after)) || (/\w, $/.test(before) && after === ')')
        if (!key) continue
        if (!names.props.has(literal.text) && !names.values.has(literal.text) && !tolerated.has(literal.text)) {
          fail(`${reader.reader}#${fn}`, `reads "${literal.text}", which ${reader.schema} (its writer's contract) does not define`)
        }
      }
    }
    continue
  }
  const text = read(reader.reader).replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
  const [from, to] = reader.between
  const start = text.indexOf(from)
  const end = text.indexOf(to, start)
  if (start < 0 || end < 0) { fail(where, `holds no region from ${JSON.stringify(from)} to ${JSON.stringify(to)}`); continue }
  const src = text.slice(start, end)
  for (const [variable, ref] of Object.entries(reader.variables)) {
    const node = located(ref)
    if (!node) { fail(where, `${ref} does not exist`); continue }
    const props = new Set([node, ...['oneOf', 'anyOf', 'allOf'].flatMap(k => (node[k] || []).map(b => located(`${ref.split('#')[0]}#${(b.$ref || '').replace(/^#/, '')}`) || b))].flatMap(n => Object.keys(n.properties || {})))
    for (const match of src.matchAll(new RegExp(`(?<![\\w.])${variable}(?:\\.(\\w+)|\\[['"](\\w+)['"]\\])`, 'g'))) {
      const field = match[1] || match[2]
      if (!props.has(field) && !tolerated.has(field)) fail(reader.reader, `reads ${variable}.${field}, which ${ref} (its writer's contract) does not define`)
    }
  }
}

if (process.argv.includes('--list')) {
  for (const entry of registry.checkers) console.log(`${entry.checker}: ${entry.rules.length} rule(s), ${agentsOf(entry).join(', ')}`)
  for (const reader of registry.readers) console.log(`reader ${reader.reader} → ${reader.schema || Object.values(reader.variables).join(', ')}`)
}
for (const finding of findings) console.log(`FAIL  ${finding}`)
const counted = `${registry.checkers.length} checkers, ${registry.readers.length} readers`
console.log(findings.length ? `\n${findings.length} finding(s) across ${counted}` : `${counted} conform`)
process.exit(findings.length ? 1 : 0)
