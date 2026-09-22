#!/usr/bin/env node
// Validate every `schema` a workflow script hands to a dispatch, and cross-check each
// script's `meta.phases` against the phases it actually enters.
//
// Usage:  node scripts/check-workflow-schemas.mjs [workflows-dir]
// Exit:   0 = every schema is well-formed and every phase name lines up, 1 = at least one does not
//
// WHY THIS EXISTS.
//
// A schema is a plain object literal until the moment `agent()` is called with it, and the
// runtime validates it THERE. So a schema whose `required` names a property it never defines
// is not a lint finding — it is an unsatisfiable contract that throws at DISPATCH, mid-run,
// after every phase above it has already been paid for. The two existing checkers cannot see
// it: check-workflow-syntax.mjs proves the file tokenizes and executes past its guards with
// stubbed dispatches (a stub never validates the schema it was handed), and
// check-agent-types.mjs proves the agentType resolves. Neither one has ever read a schema.
//
// The same silence covers `meta.phases`. Those titles are what a progress reader groups on,
// and nothing checks them against the `phase()` calls. Rename a phase in the body and the run
// quietly opens a group nobody declared; rename it in `meta` and a declared group stays empty
// forever. Neither is an error anyone sees while the run is burning tokens.
//
// HOW THE SCHEMAS ARE FOUND. They are data, so they are read as data: a small recursive-descent
// parser for the literal grammar these files actually use (objects, arrays, strings, numbers,
// booleans, null, comments, and identifier references resolved against the file's own
// `const ... = {...}` table, so SPEC_SCHEMA, PROPOSAL_SCHEMA, CRITERIA_SCHEMA and the rest are
// validated wherever they are held). A parser rather than `new Function` on purpose: evaluation
// silently keeps the LAST of two duplicate keys, which is exactly the defect where the first one
// was the real requirement. A value the parser cannot read — a call, a ternary — is REPORTED as
// unread rather than passed, because "I could not look" and "I looked and it was fine" are
// different answers and only one of them is evidence.
//
// HOW THE PHASES ARE MATCHED. Exactly on the title string, which is how the runtime groups them.
// A composite does not call `phase()` directly — it calls a one-line wrapper (`enterPhase`,
// `enter`) that records the title and forwards it — so the wrappers are detected structurally
// (a one-parameter function whose body forwards that parameter to `phase()`) and their literal
// call sites are read as phase entries too.
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const dir = process.argv[2] || path.join(here, '..', 'workflows')

// ── A literal reader ──────────────────────────────────────────────────────────
// Only the grammar schemas are written in. Anything else throws, and a throw is reported
// as an unread schema rather than swallowed.
class Unreadable extends Error {}

function makeReader(src, consts) {
  const resolving = new Set()

  function reader(start) {
    let i = start

    function ws() {
      for (;;) {
        while (i < src.length && /\s/.test(src[i])) i++
        if (src[i] === '/' && src[i + 1] === '/') {
          while (i < src.length && src[i] !== '\n') i++
          continue
        }
        if (src[i] === '/' && src[i + 1] === '*') {
          const end = src.indexOf('*/', i + 2)
          if (end === -1) throw new Unreadable('unterminated block comment')
          i = end + 2
          continue
        }
        return
      }
    }

    function string() {
      const quote = src[i]
      i++
      let out = ''
      while (i < src.length && src[i] !== quote) {
        if (src[i] === '\\') {
          const c = src[i + 1]
          out += c === 'n' ? '\n' : c === 't' ? '\t' : c
          i += 2
          continue
        }
        if (quote === '`' && src[i] === '$' && src[i + 1] === '{') throw new Unreadable('template substitution')
        out += src[i]
        i++
      }
      if (i >= src.length) throw new Unreadable('unterminated string')
      i++
      return out
    }

    // An expression the reader cannot evaluate, skipped to the end of its slot so the
    // REST of the schema is still read. A cap read from a variable (`minItems: AC_MIN`)
    // is not a reason to walk away from the forty other keys around it — the value
    // becomes UNKNOWN, every check that needs it is withheld, and every check that does
    // not is still made.
    function opaque() {
      const stack = []
      for (; i < src.length; i++) {
        const c = src[i]
        if (c === '"' || c === "'" || c === '`') {
          string()
          i--
          continue
        }
        if (c === '(' || c === '[' || c === '{') stack.push(c)
        else if (c === ')' || c === ']' || c === '}') {
          if (!stack.length) return UNKNOWN
          stack.pop()
        } else if (c === ',' && !stack.length) return UNKNOWN
      }
      throw new Unreadable('unterminated expression')
    }

    function member(base) {
      let out = base
      for (;;) {
        ws()
        if (src[i] !== '.') return out
        i++
        const k = /^[A-Za-z_$][\w$]*/.exec(src.slice(i))
        if (!k) throw new Unreadable('malformed member access')
        i += k[0].length
        if (out === UNKNOWN) continue
        if (!out || typeof out !== 'object') return UNKNOWN
        out = out[k[0]]
      }
    }

    function value() {
      ws()
      const c = src[i]
      if (c === '"' || c === "'" || c === '`') return string()
      if (c === '{') return object()
      if (c === '[') return array()
      const word = /^[A-Za-z_$][\w$]*/.exec(src.slice(i))
      if (word) {
        const name = word[0]
        const after = i + name.length
        const rest = src.slice(after).replace(/^\s+/, '')
        if (name === 'true' || name === 'false' || name === 'null' || name === 'undefined') {
          if (!rest.startsWith('.') && !rest.startsWith('(')) {
            i = after
            return name === 'true' ? true : name === 'false' ? false : name === 'null' ? null : undefined
          }
        }
        if (!rest.startsWith('(') && !rest.startsWith('?') && Object.prototype.hasOwnProperty.call(consts, name)) {
          i = after
          const held = member(resolve(name))
          ws()
          // `designSpecs.map(...)` — a method call on a literal is still a computation.
          if (src[i] === '(' || src[i] === '?') return opaque()
          return held
        }
        return opaque()
      }
      const num = /^-?\d[\d_]*(\.\d+)?([eE][+-]?\d+)?/.exec(src.slice(i))
      if (num) {
        i += num[0].length
        ws()
        if (/^[.?+\-*/(]/.test(src.slice(i))) return opaque()
        return Number(num[0].replace(/_/g, ''))
      }
      return opaque()
    }

    function array() {
      i++ // [
      const out = []
      for (;;) {
        ws()
        if (src[i] === ']') {
          i++
          return out
        }
        if (src[i] === ',') {
          i++
          continue
        }
        if (src.startsWith('...', i)) {
          i += 3
          const spread = value()
          // A CONDITIONAL spread — `...(cond ? ['a'] : [])` — contributes elements this
          // reader cannot enumerate. One UNKNOWN element stands in for them, and every
          // per-element check skips it rather than inventing a verdict.
          if (spread === UNKNOWN) out.push(UNKNOWN)
          else if (!Array.isArray(spread)) throw new Unreadable('spread of a non-array')
          else out.push(...spread)
          continue
        }
        out.push(value())
      }
    }

    function object() {
      i++ // {
      const out = {}
      const dupes = []
      let partial = false
      for (;;) {
        ws()
        if (src[i] === '}') {
          i++
          if (dupes.length) Object.defineProperty(out, DUPES, { value: dupes, enumerable: false })
          if (partial) Object.defineProperty(out, PARTIAL, { value: true, enumerable: false })
          return out
        }
        if (src[i] === ',') {
          i++
          continue
        }
        if (src.startsWith('...', i)) {
          i += 3
          const spread = value()
          // A conditionally-spread key set. The object is marked PARTIAL: it may hold keys
          // this reader cannot see, so the checks that ask "is this name absent?" are
          // withheld for it — absence is the one thing an incomplete reading cannot prove.
          if (spread === UNKNOWN) partial = true
          else if (!spread || typeof spread !== 'object') throw new Unreadable('spread of a non-object')
          else Object.assign(out, spread)
          continue
        }
        let key
        if (src[i] === '"' || src[i] === "'" || src[i] === '`') key = string()
        else if (src[i] === '[') throw new Unreadable('computed key')
        else {
          const k = /^[A-Za-z_$][\w$]*/.exec(src.slice(i))
          if (!k) throw new Unreadable(`unexpected key at \`${src.slice(i, i + 24).split('\n')[0]}\``)
          key = k[0]
          i += key.length
        }
        ws()
        if (src[i] !== ':') throw new Unreadable(`shorthand or method \`${key}\``)
        i++
        if (Object.prototype.hasOwnProperty.call(out, key)) dupes.push(key)
        out[key] = value()
      }
    }

    return { value, end: () => i }
  }

  function resolve(name) {
    if (!Object.prototype.hasOwnProperty.call(consts, name)) throw new Unreadable(`\`${name}\` is not a literal const in this file`)
    if (resolving.has(name)) throw new Unreadable(`\`${name}\` refers to itself`)
    resolving.add(name)
    try {
      return reader(consts[name]).value()
    } finally {
      resolving.delete(name)
    }
  }

  return reader
}

const DUPES = Symbol('duplicate-keys')
// A value the reader could not evaluate. Every check that depends on it is WITHHELD rather
// than guessed — an unknown is never reported as a defect, and never reported as clean.
const UNKNOWN = Symbol('unknown-expression')
// An object that was spread from something the reader could not enumerate, so it may hold
// keys that are not in it. It can still be checked for what IS there; it cannot be checked
// for what is missing.
const PARTIAL = Symbol('partially-read-object')

// Every `const NAME = {` / `const NAME = [` in the file, by the offset of its literal. The
// reader resolves an identifier against this table, so a schema held in a named const is read
// wherever it is referenced.
function constTable(src) {
  const table = {}
  for (const m of src.matchAll(/(?:^|[\s;{])const\s+([A-Za-z_$][\w$]*)\s*=\s*(?=[[{])/g)) {
    table[m[1]] = m.index + m[0].length
  }
  return table
}

// ── Schema validation ─────────────────────────────────────────────────────────
const JSON_TYPES = new Set(['object', 'array', 'string', 'number', 'integer', 'boolean', 'null'])

function validateSchema(node, where, findings, trail = '') {
  const at = trail || '(root)'
  if (node === UNKNOWN) return
  if (node === null || typeof node !== 'object' || Array.isArray(node)) {
    findings.push({ ...where, hard: true, what: `${at} is not an object — a schema must be a JSON Schema object` })
    return
  }
  for (const key of node[DUPES] || []) {
    findings.push({ ...where, hard: true, what: `${at} declares \`${key}\` twice — one of the two is silently discarded` })
  }

  const types = node.type === undefined || node.type === UNKNOWN ? [] : Array.isArray(node.type) ? node.type : [node.type]
  for (const t of types) {
    if (typeof t !== 'string' || !JSON_TYPES.has(t)) {
      findings.push({ ...where, hard: true, what: `${at} has type ${JSON.stringify(t)}, which is not a JSON Schema type` })
    }
  }

  if (
    node.properties !== undefined &&
    node.properties !== UNKNOWN &&
    (node.properties === null || typeof node.properties !== 'object' || Array.isArray(node.properties))
  ) {
    findings.push({ ...where, hard: true, what: `${at}.properties is not an object` })
  }

  const propsUnknown = node.properties === UNKNOWN || (node.properties && node.properties[PARTIAL] === true)
  const props =
    node.properties !== UNKNOWN && node.properties && typeof node.properties === 'object' && !Array.isArray(node.properties) ? node.properties : null
  if (node.required !== undefined && node.required !== UNKNOWN) {
    if (!Array.isArray(node.required)) {
      findings.push({ ...where, hard: true, what: `${at}.required is not an array` })
    } else {
      for (const name of node.required) {
        if (name === UNKNOWN) continue
        if (typeof name !== 'string') {
          findings.push({ ...where, hard: true, what: `${at}.required contains ${JSON.stringify(name)}, which is not a string` })
          continue
        }
        // THE DISPATCH-TIME THROW. A required name the schema never defines cannot be
        // satisfied by any output the agent could produce.
        if (propsUnknown) continue
        if (!props || !Object.prototype.hasOwnProperty.call(props, name)) {
          findings.push({
            ...where,
            hard: true,
            what: `${at}.required names \`${name}\`, which ${at}.properties does not define — UNSATISFIABLE, and the throw lands at dispatch`,
          })
        }
      }
    }
  }

  if (types.includes('array') && node.items === undefined) {
    findings.push({ ...where, hard: true, what: `${at} is an array with no \`items\` — nothing constrains what it holds` })
  }
  for (const bound of ['maxItems', 'minItems']) {
    if (node[bound] === undefined || node[bound] === UNKNOWN) continue
    if (!Number.isInteger(node[bound]) || node[bound] < 0) {
      findings.push({ ...where, hard: true, what: `${at}.${bound} is ${JSON.stringify(node[bound])}, which is not a non-negative integer` })
    }
  }
  if (Number.isInteger(node.maxItems) && Number.isInteger(node.minItems) && node.maxItems < node.minItems) {
    findings.push({ ...where, hard: true, what: `${at} has maxItems ${node.maxItems} below minItems ${node.minItems} — UNSATISFIABLE` })
  }

  if (props) for (const [name, child] of Object.entries(props)) validateSchema(child, where, findings, `${at}.properties.${name}`)
  if (node.items !== undefined && node.items !== UNKNOWN) {
    if (Array.isArray(node.items)) node.items.forEach((child, n) => validateSchema(child, where, findings, `${at}.items[${n}]`))
    else validateSchema(node.items, where, findings, `${at}.items`)
  }
}

// ── Phase extraction ──────────────────────────────────────────────────────────
// The titles `meta.phases` declares, in order.
function declaredPhases(src) {
  const at = src.search(/^\s*phases:\s*\[/m)
  if (at === -1) return null
  const open = src.indexOf('[', at)
  let depth = 0
  let end = open
  for (; end < src.length; end++) {
    if (src[end] === '[') depth++
    else if (src[end] === ']' && --depth === 0) break
  }
  const block = src.slice(open, end + 1)
  return [...block.matchAll(/title:\s*(['"`])((?:\\.|(?!\1).)*)\1/g)].map((m) => m[2])
}

// `phase('X')`, plus the literal call sites of any one-parameter function that forwards its
// parameter straight to `phase()` — which is how every composite enters a phase.
function calledPhases(src) {
  const names = ['phase']
  for (const m of src.matchAll(/function\s+([A-Za-z_$][\w$]*)\s*\(\s*([A-Za-z_$][\w$]*)\s*\)\s*\{/g)) {
    const body = src.slice(m.index, src.indexOf('\n}', m.index) + 2)
    if (new RegExp(`(^|[^\\w.])phase\\(\\s*${m[2]}\\s*\\)`).test(body)) names.push(m[1])
  }
  const called = []
  let computed = 0
  for (const name of names) {
    for (const m of src.matchAll(new RegExp(`(^|[^\\w.])${name}\\(\\s*(?:(['"\`])((?:\\\\.|(?!\\2).)*)\\2)?`, 'g'))) {
      if (m[3] === undefined) computed++
      else called.push({ title: m[3], line: src.slice(0, m.index).split('\n').length })
    }
  }
  return { called, computed, wrappers: names.slice(1) }
}

// ── Run ───────────────────────────────────────────────────────────────────────
const files = readdirSync(dir)
  .filter((f) => f.endsWith('.js'))
  .sort()

const findings = []
const unread = []
let schemas = 0
let phaseComputed = 0

for (const file of files) {
  const src = readFileSync(path.join(dir, file), 'utf8')
  const lineOf = (index) => src.slice(0, index).split('\n').length
  const reader = makeReader(src, constTable(src))

  for (const m of src.matchAll(/(^|[\s,{(])schema:\s*/g)) {
    const at = m.index + m[0].length
    const where = { file, line: lineOf(at) }
    // `schema: settleSchemaName(o)` is the shared dispatch block's failure REPORT, which
    // records the name of the schema a dead dispatch was carrying. Identical text in all 32
    // files, never handed to agent(), and listing it 32 times would bury the real notes.
    if (src.startsWith('settleSchemaName(', at)) continue
    let value
    try {
      value = reader(at).value()
    } catch (err) {
      if (!(err instanceof Unreadable)) throw err
      unread.push({ ...where, why: err.message })
      continue
    }
    // `schema: null` is how a dispatch says it wants no structured output, and a
    // schema-name string is a report field, not a schema. Neither is a defect. A whole
    // schema that came back UNKNOWN is an expression, not a literal — `settleSchemaName(o)`
    // in the shared dispatch block is one, and it names a schema rather than being one —
    // so it is recorded as unread and nothing is asserted about it.
    if (value == null || typeof value === 'string') continue
    if (value === UNKNOWN) {
      unread.push({ ...where, why: 'the whole value is an expression, not a literal' })
      continue
    }
    schemas++
    validateSchema(value, where, findings)
  }

  const declared = declaredPhases(src)
  const { called, computed, wrappers } = calledPhases(src)
  phaseComputed += computed
  if (declared === null) {
    findings.push({ file, line: 1, hard: true, what: 'meta declares no `phases` — a run has no progress groups to report into' })
    continue
  }
  const declaredSet = new Set(declared)
  const calledSet = new Set(called.map((c) => c.title))
  const seen = new Set()
  for (const { title, line } of called) {
    if (declaredSet.has(title) || seen.has(title)) continue
    seen.add(title)
    findings.push({
      file,
      line,
      hard: true,
      what:
        `phase('${title}') is entered but \`meta.phases\` does not declare it — the run opens a progress group ` +
        `nobody declared, which is what a renamed phase looks like from the outside`,
    })
  }
  for (const title of declared) {
    if (calledSet.has(title)) continue
    findings.push({
      file,
      line: 1,
      hard: true,
      what:
        `meta.phases declares '${title}' but nothing enters it${wrappers.length ? ` (via phase() or ${wrappers.join('/')})` : ''} — ` +
        'the group stays empty for the whole run',
    })
  }
}

for (const { file, line, what } of findings) console.log(`FAIL  workflows/${file}:${line}  —  ${what}`)
for (const { file, line, why } of unread) console.log(`NOTE  workflows/${file}:${line}  —  schema not statically readable: ${why}`)

console.log(
  findings.length
    ? `\n${findings.length} schema/phase defect(s) across ${files.length} workflow scripts — a malformed schema throws at DISPATCH, mid-run`
    : `all ${schemas} schema(s) across ${files.length} workflow scripts are well-formed, and every meta.phases title matches a phase entered in the same file` +
        `${unread.length ? `; ${unread.length} schema expression(s) were not statically readable (listed above)` : ''}` +
        `${phaseComputed ? `; ${phaseComputed} computed phase reference(s) were not text-visible` : ''}`,
)

process.exit(findings.length ? 1 : 0)
