export const meta = {
  name: 'spec-authoring',
  description:
    'Leaf mini — Spec authoring. Contract and data-model makers run in parallel, then the existing criteria maker reads their completed documents after UI citation repair to finish the implementation-ready spec set for one repository from the TRD and the approved target and delta views, specifying the change for the delta items the repository\'s detailing marks add, modify or remove: API/OpenAPI, event and error contracts; the data model; the acceptance criteria and Definition of Done. For a repository with `ui` work items the contracts maker also returns uiSpec, one section per item stating its design source: a bundle item (the owner supplied a cds bundle) cites that bundle\'s spec/build-spec.md and its resolved Section IDs; a cds item states that it is designed with the CDS design system; a none item states that it changes no design. The script checks, in that return and in the saved spec document (depscore.py spec-ui-check reads the file), that every item has its section and that every bundle item cites the build spec the detailing resolved and its Section IDs; a gap sends the contracts back to their maker once, and a second gap fails the run at stage ui-citation. One more session authors the ONE Story the Spec pairs with, scoped to args.repoPath, and saves it as story-<slug>.json; the script checks that file holds exactly what the session returned (writing it when it does not), records every saved document with the artifact script, and writes that ONE Story bead with one depscore.py write-story command through the checked relay, keyed by its elab_key, whose full result — the keyed Tasks already under the Story among it — lands in story-<slug>.written.json. With replay: true no session authors, and the script runs write-story from the saved story-<slug>.json. Whether the bead landed is read from beads by depscore.py elaboration-finish, not judged here.',
  phases: [
    { title: 'Author specs', detail: 'contracts and data model in parallel, then criteria from their completed documents after UI repair' },
    { title: 'Emit story', detail: 'author the ONE Story this Spec pairs with — container only, single repo — and write its bead with depscore.py write-story' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
// Runtime replay identifies calls by their unchanged prompt/options and start order.
// Recovery metadata stays in workflow arguments and never enters those options.
const fableInput = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const fableTypes = new Set((Array.isArray(fableInput.fableAgentTypes) ? fableInput.fableAgentTypes : []).map((name) => String(name).replace(/^agent-teams-workforce:/, '')))
const fablePath = fableInput.fableInvocationPath || 'root'
const fableRecovery = fableInput.fableRecovery && typeof fableInput.fableRecovery === 'object' ? fableInput.fableRecovery : null
let fableAgentOrdinal = 0
let fableChildOrdinal = 0
function fableEvent(event, identity, error = null) {
  log(`FABLE-CALL ${JSON.stringify({ event, ...identity, ...(error === null ? {} : { error }) })}`)
}
async function fableAgent(prompt, options) {
  const identity = { invocationPath: fablePath, ordinal: fableAgentOrdinal++, agentType: (options && options.agentType) || null, label: (options && options.label) || null }
  const isFable = fableTypes.has(String(identity.agentType || '').replace(/^agent-teams-workforce:/, ''))
  const cutoffs = (fableRecovery && fableRecovery.cutoffs) || {}
  const cutoff = Number.isInteger(cutoffs[fablePath]) && cutoffs[fablePath] >= 0 ? cutoffs[fablePath] : 0
  const call = isFable && fableRecovery && identity.ordinal >= cutoff ? { ...options, model: 'opus' } : options
  fableEvent('start', identity)
  try {
    const result = await agent(prompt, call)
    if (!result) fableEvent('failed', identity)
    return result
  } catch (error) {
    const message = String((error && error.message) || error)
    fableEvent('failed', identity, message)
    if (isFable && /out of (?:usage )?credits|seven_day_overage_included|fable.{0,40}(?:limit|allowance)/i.test(message)) return null
    throw error
  }
}
async function fableWorkflow(name, input) {
  const invocationPath = `${fablePath}/${fableChildOrdinal++}:${name}`
  return await workflow(name, {
    ...input,
    fableAgentTypes: fableInput.fableAgentTypes || [],
    fableInvocationPath: invocationPath,
    ...(fableRecovery ? { fableRecovery } : {}),
  })
}
// ===== SHARED BLOCK fable — END =====

// BEGIN interruption propagation — no retry or replay of completed dispatches.
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
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
function captureDispatchInterruption(err, name) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  dispatchInterruption = { stage, message: stage + ': ' + name + ': ' + String((err && err.message) || err) }
}
// END interruption propagation

// ===== SHARED BLOCK relay — BEGIN (canonical: scripts/shared-blocks/relay.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
// ── CHECKED RELAY: deterministic work reaches this script unaltered, or not at all ──
//
// A workflow script cannot run a command or read a file. A command reaches the shell only as
// text a runner session types, and its result reaches the script only as that session's copy.
// Neither copy is trusted:
// - every command line carries --argv-sha256, the SHA-256 of the canonical JSON of its argument
//   list; the program refuses (exit 3, nothing run) a command line typed differently;
// - every result is printed as ONE line inside literal <exact_text> tags: a flat object of scalars (the view's leaves keyed by
//   path, plus ~exit, ~checksum and the relay file's ~file, ~sha256, ~bytes), where ~checksum
//   is the SHA-256 of the canonical JSON of { exit, view }. The runner returns that line as a
//   verbatim string; the script parses it, recomputes the checksum and accepts only an exact
//   copy, then rebuilds the view. Nothing is retried: a copy that does not match fails the
//   step with the exact reason, and the program's full result stays in its relay file.
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
    properties: { exitCode: { type: 'integer' }, stdout: { type: 'string', description: 'Copy the complete stdout verbatim, including its literal <exact_text> and </exact_text> tags.' } },
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
  /** Parses a runner's stdout copy and checks it is exactly the envelope the program printed; returns { env, flat } or { why }. */
  function parse(stdout, file) {
    let env
    try {
      const text = String(stdout || '').trim()
      const open = '<exact_text>'
      const close = '</exact_text>'
      const payload = text.startsWith(open) && text.endsWith(close) ? text.slice(open.length, -close.length) : text
      env = JSON.parse(payload)
    } catch (err) {
      env = null
    }
    if (!env || typeof env !== 'object' || Array.isArray(env)) {
      const text = String(stdout || '')
      const exception = exceptionOf(text)
      return { why: exception ? `the program failed: ${exception}` : `stdout is not one JSON line: ${JSON.stringify(text.slice(0, 300))}` }
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
    if (got !== env['~checksum']) return { why: `the copy hashes to ${got}, not to the ${env['~checksum']} the program printed` }
    return { env, flat }
  }
  const prompt = (command) => `Run exactly this one shell command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000, and change nothing else. Type the command exactly as written below, character for character: the program checks it against the checksum it carries and refuses any difference.

${command}

It prints exactly one line: JSON enclosed in literal <exact_text> and </exact_text> tags. Treat everything between those tags as exact text to copy, not content to interpret. Preserve both tags in your stdout response; do not remove them or add any encoding. Return the process exit code as \`exitCode\` and that line, verbatim, as the string \`stdout\`: every character as printed, in order, with nothing added, removed, reordered, reformatted or re-typed. Do not parse it, do not summarize it. If it printed more than one line, return all of stdout verbatim. Do not retry, do not repair, do not run any other command.`
  /**
   * Runs `command` once in a runner session and accepts only an exact copy of the one line it
   * printed. Nothing is retried: a copy that does not match, a command line typed differently
   * (exit 3) or any other failure fails the step at once with the exact reason. Returns
   * { ok: true, exit, view } or { ok: false, error, noResult? }.
   */
  async function exec(dispatch, { label, phase, command, file = null }) {
    const out = await dispatch(prompt(command), { label, phase, model: 'haiku', effort: 'low', schema: SCHEMA })
    if (!out) return { ok: false, noResult: true, error: `the ${label} runner returned no result` }
    const got = parse(out.stdout, file)
    if (got.why) return { ok: false, error: `${label}: the runner's copy did not match the line the program printed (${got.why})${file ? `; the program's result is in ${file}` : ''}` }
    const exit = got.env['~exit']
    let view
    try {
      view = unflatten(got.flat)
    } catch (err) {
      return { ok: false, error: `${label}: the printed view could not be rebuilt: ${String((err && err.message) || err)}` }
    }
    if (exit === 3) return { ok: false, error: `${label}: ${String(view.error || 'the runner typed the command line differently from the one built')}; nothing ran` }
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
   * what it printed, checked, with relayFile; or { error, exception?, output? }.
   */
  async function depscore(dispatch, { label, phase, script, repo, tail, file }) {
    let rest
    try {
      rest = [...(repo ? ['-C', repo] : []), '--relay', file, ...shellWords(tail)]
    } catch (err) {
      return { error: `${label}: ${String((err && err.message) || err)}` }
    }
    const r = await exec(dispatch, { label, phase, command: pythonLine(script, rest), file })
    if (!r.ok) return { error: r.error, noResult: !!r.noResult }
    if (r.exit !== 0 || r.view.error) {
      const raw = String(r.view.error || `depscore.py exited ${r.exit}`)
      const exception = exceptionOf(raw)
      return { error: exception ? `${exception} (depscore.py exited ${r.exit}; full output: ${raw})` : raw, exception, output: r.view, relayFile: file }
    }
    return { ...r.view, relayFile: file }
  }
  /**
   * Runs `argv` (a program and its arguments, no shell) through relayrun.py at `runner`, in `cwd`.
   * Returns { ok: true, exitCode, json, stdoutBytes, stderrBytes, stdoutTail?, stderrTail?, relayFile }
   * — json is stdout parsed when it is one JSON object (reduced to `keys` when given), else null —
   * or { ok: false, error }.
   */
  async function run(dispatch, { label, phase, runner, argv, cwd = null, file, keys = [], tail = 0, timeout = null }) {
    const rest = ['run', '--relay', file, ...(cwd ? ['--cwd', cwd] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(tail ? ['--tail', String(tail)] : []), ...(timeout ? ['--timeout', String(timeout)] : []), '--', ...argv.map(String)]
    const r = await exec(dispatch, { label, phase, command: pythonLine(runner, rest), file })
    if (!r.ok) return { ok: false, error: r.error, noResult: !!r.noResult }
    if (r.exit !== 0) return { ok: false, error: String(r.view.error || `relayrun.py exited ${r.exit}`) }
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
    'import hashlib, json, sys',
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
    '    print("<exact_text>" + c(dict(f, **{"~exit": ex, "~checksum": h({"exit": ex, "view": f})})) + "</exact_text>")',
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
  return { canonicalJson, sha256Ascii, sha256Json, quote, shellWords, exec, depscore, run, checkFile, ensureJson, inline, exceptionOf, unflatten, parse, SCHEMA }
})()
// ===== SHARED BLOCK relay — END =====

const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  return named.length ? dispatchFailures.filter((f) => named.includes(f.phase)) : dispatchFailures.slice()
}
// Runs agent(); returns its result, or null after recording the failure in dispatchFailures.
async function settleAgent(prompt, opts) {
  if (dispatchInterruption) return null
  const o = opts || {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  try {
    const out = await fableAgent(prompt, o)
    if (out) return out
    dispatchFailures.push({ ...who, outcome: 'skipped', note: `${name} returned nothing` })
    log(`${name}: returned nothing`)
  } catch (err) {
    captureDispatchInterruption(err, (opts && (opts.label || opts.agentType)) || 'agent')
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

// args: {
//   spec: { id?, title?, summary?, service?, repoPath? }, trd?, constraints?: string[],
//   architecture?: { targetDir, deltaDir } (the approved target and its delta),
//   accessPatterns?: string[], repoPath, storyKey? ('S1'), epic: { key?, id?, title? },
//   uiItems?: [{ id, element?, designSource?, buildSpec?, sections? }] (the repository's `ui` work items, each with its design source bundle | cds | none and, for bundle, the build spec it was resolved to),
//   detailingPath?: <absolute path of the repository's saved delta detailing, recon-<slug>.json; the makers read it>,
//   artifacts: { dir, relDir?, epicId, script, phase, slug, inputs? },
//   beads: { script, repo, epicId, projectRoot? }  (script: the absolute depscore.py path),
//   replay?: true
// }
// returns { ok, resumed?, unresolvedArtifacts, story: { key, type, id, elabKey, title, description, repoPath, parentEpicKey },
//           writtenPath, spec, apiSpec, dataModelSpec, eventContracts, errorSpec, uiSpec, decisionIds, outOfRepoFindings, note },
//           or { ok: false, stage, reason, dispatchFailed? }; story.id is null when the write-story summary was not relayed

const CRITERIA_MAX = 120
const DOD_MAX = 30

const SPEC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['artifactPaths', 'summary', 'content'],
  properties: {
    artifactPaths: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    content: { type: 'string' },
    openQuestions: { type: 'array', items: { type: 'string' } },
    decisionIds: { type: 'array', items: { type: 'string' } },
  },
}

const CONTRACTS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['apiSpec', 'eventContracts', 'errorSpec'],
  properties: {
    apiSpec: SPEC_SCHEMA,
    eventContracts: SPEC_SCHEMA,
    errorSpec: SPEC_SCHEMA,
  },
}

const UI_SPEC_SCHEMA = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['itemId', 'designSource', 'buildSpec', 'sections', 'content'],
    properties: {
      itemId: { type: 'string' },
      designSource: { type: 'string', enum: ['bundle', 'cds', 'none'] },
      buildSpec: { type: 'string' },
      sections: { type: 'array', items: { type: 'string' } },
      content: { type: 'string' },
    },
  },
}

const CONTRACTS_UI_SCHEMA = {
  ...CONTRACTS_SCHEMA,
  required: [...CONTRACTS_SCHEMA.required, 'uiSpec'],
  properties: { ...CONTRACTS_SCHEMA.properties, uiSpec: UI_SPEC_SCHEMA },
}

const BUILD_SPEC_PATH = /(^|\/)spec\/build-spec\.md$/

/** Returns the UI items with no uiSpec section, and the bundle items whose section cites no build-spec.md or another one than the detailing resolved. */
function uiCitationGaps(uiItems, uiSpec) {
  const sections = Array.isArray(uiSpec) ? uiSpec.filter((x) => x && typeof x === 'object') : []
  return uiItems
    .map((item) => {
      const own = sections.filter((x) => String(x.itemId || '').trim() === item.id)
      if (!own.length) return { id: item.id, problem: 'no uiSpec section specifies it' }
      if (item.designSource !== 'bundle') return null
      const cited = own.map((x) => String(x.buildSpec || '').trim())
      if (!cited.some((p) => BUILD_SPEC_PATH.test(p))) return { id: item.id, problem: 'its uiSpec section cites no spec/build-spec.md path' }
      if (item.buildSpec && !cited.includes(item.buildSpec)) return { id: item.id, problem: `its uiSpec section cites ${cited.join(', ')}, not the build spec the detailing resolved, ${item.buildSpec}` }
      const listed = new Set(own.flatMap((x) => (Array.isArray(x.sections) ? x.sections : []).map((y) => String(y).trim())))
      const absent = item.sections.filter((x) => !listed.has(x))
      if (absent.length) return { id: item.id, problem: `its uiSpec section leaves out the build-spec Sections ${absent.join(', ')} the detailing resolved` }
      return null
    })
    .filter(Boolean)
}

const CRITERIA_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['acceptanceCriteria', 'definitionOfDone'],
  properties: {
    acceptanceCriteria: {
      type: 'array',
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
    definitionOfDone: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}

const STORY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['title', 'description'],
  properties: {
    title: { type: 'string' },
    description: { type: 'string' },
  },
}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
/** The save instruction appended to a maker's prompt; the workflow records (and, for JSON, checks) the file after the maker returns. */
function persistBrief(art, name, what) {
  if (!art) return ''
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\nWrite ${what} to ${art.dir}/${name} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this, and run no command to record it: the workflow records it after you return.\nIf the write fails, say so in your result and still return your result.`
}

function hasText(x) {
  return typeof x === 'string' && x.trim().length > 0
}

/**
 * The checked relay for one repository's spec authoring: depscore.py commands through
 * relayKit.depscore, the artifact script's `record` through relayrun.py (beside depscore.py),
 * and the saved JSON through relayKit.ensureJson. Relay files are numbered under the Epic's
 * artifact directory, per repository slug, so parallel runs for other repositories never share one.
 */
function relayFor(art, slug, beads) {
  const runner = beads.script.replace(/[^/]+$/, 'relayrun.py')
  const dir = `${art.dir}/relay/spec-${slug}`
  let seq = 0
  const file = (label) => {
    seq += 1
    return `${dir}/${String(seq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
  }
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter(hasText)
  return {
    /** Runs one depscore.py command; returns its checked output, or { error }. */
    depscore: (label, phaseName, tail, repo) => relayKit.depscore(settleAgent, { label, phase: phaseName, script: beads.script, repo: repo || null, tail, file: file(label) }),
    /** Records the artifact `name` with the artifact script's `record`; returns '' or why it was not recorded. */
    async record(name, label, phaseName) {
      const argv = ['python3', art.script, 'record', `${art.dir}/${name}`, '--epic', art.epicId, '--phase', art.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])]
      const r = await relayKit.run(settleAgent, { label, phase: phaseName, runner, argv, file: file(label), keys: ['sha256', 'bytes'], tail: 20 })
      if (!r.ok) return r.error
      return r.exitCode === 0 ? '' : `the record command exited ${r.exitCode}: ${String(r.stderrTail || r.stdoutTail || '').trim().slice(0, 600)}`
    },
    /** Makes `${art.dir}/${name}` hold exactly `value`; returns '' or why it does not. */
    async ensureJson(name, label, phaseName, value) {
      const r = await relayKit.ensureJson(settleAgent, { label, phase: phaseName, runner, file: `${art.dir}/${name}`, value })
      return r.ok ? '' : r.error || 'not saved'
    },
  }
}
const beadsFrom = (x) => (x && typeof x === 'object' && ['script', 'repo', 'epicId'].every((k) => hasText(x[k])) ? x : null)

/** Returns the context block every maker reads: spec header, the repository's constraints, the target and delta views, and the TRD. */
function ctxBlock(s, trd, constraints, arch, detailingPath) {
  const trdOnDisk = trd && typeof trd.trdPath === 'string' && trd.trdPath.startsWith('/')
  return [
    `Spec ${s.id || ''}: ${s.title || ''}`,
    s.service ? `Owning service: ${s.service}` : '',
    s.summary ? `What this spec must cover:\n${s.summary}` : '',
    `Work within the repository at: ${s.repoPath || '(repo path not provided — author against the supplied context only)'}`,
    'Carry implementation provenance through these existing documents, alongside the obligation it supports; do not invent another evidence artifact or substitute source code for the requirement authority.',
    "The architecture reaches this spec through the TRD: the owner's constraints (arc42 section 2) and the patterns the effective views establish for the API type, the runtime libraries, the event path and the data stores. Follow them as the TRD states them; a spec that departs from an established pattern states its reason and evidence.",
    arch && hasText(arch.deltaDir)
      ? `THE APPROVED TARGET is ${arch.targetDir || '(the folder above the delta)'}, and the change alone, its delta, is ${arch.deltaDir}. Read the delta views for the items listed below, and the target views they need: the spec specifies the change they show for this repository, and nothing the delta does not change.`
      : '',
    hasText(detailingPath)
      ? `THE DELTA DETAILING of this repository is the file ${detailingPath}. Read it: its \`items\` give each delta item placed here its status (add, modify, remove, done, planned-elsewhere), the \`from\` state the code on main holds, the \`to\` state the target makes it, its surface and its file:line evidence.`
      : '',
    constraints && constraints.length
      ? `Context and constraints for this repository:\n${constraints.map((c, i) => `${i + 1}. ${c}`).join('\n')}`
      : '',
    trdOnDisk
      ? `The TRD is the document at ${trd.trdPath}. Read it: it is the authoritative source for the technical requirements.${hasText(trd.summary) ? `\nTRD summary: ${trd.summary}` : ''}`
      : trd
        ? `Upstream TRD / requirements packet:\n${JSON.stringify(trd)}`
        : '',
  ]
    .filter(Boolean)
    .join('\n\n')
}

/** Returns the reading scope rule, plus the decision-citation rule when `cites` is true. */
function makerRules({ cites }) {
  return [
    'READING SCOPE: the packet above is your source, and the repository named above is the ONLY repository whose implementation you may read — never survey other repositories. Read the supplied architecture/spec artifact paths as required. Prefer targeted searches; reopen a previously read file only when a changed revision, repair or named unanswered question makes that necessary.',
    'EVIDENCE CONTINUITY: in the existing specification context and relevant sections, preserve the detailing/TRD repository path, exact source commit, file:line or heading and linked delta/TRD obligation IDs. Reuse sufficient evidence at the same main revision. State the already-established fact and the changed revision, missing evidence or unanswered question before further source reads; refresh only affected paths and integration dependencies. A legacy citation without a revision is unverified until a targeted check, not an invitation to resurvey. Preserve historical citations and distinguish working behavior, stubs, missing integration and unknowns; a test citation never claims execution.',
    'EXISTING REPOSITORY: use the supplied detailing and its file:line evidence to inspect only the entrypoints, implementation, contracts and focused tests relevant to this spec. Distinguish supported behavior, incomplete wiring, stubs and unknowns; code presence does not prove correctness, and test source does not prove a passing or live-runtime result. Specify the delta from that inspected state, preserving verified behavior and compatible contracts. State the current path, required change and evidence in the existing spec sections, with acceptance criteria and verification for the changed behavior. If the detailing is materially contradicted, report the contradiction rather than silently treating a done item as new work. Do not design a replacement service or repository merely because this work has a PRD; replacement needs an evidenced requirement and consistency with the approved architecture.',
    cites
      ? 'CITE THE ARCHITECTURE YOU DESIGNED AGAINST. Return `decisionIds` on every artifact you author: the architecture views it depends on, each a path relative to the arc42 folder with `#<heading>` when it rests on one part of the view, written as the TRD cites them, and carry the same list in YAML frontmatter as `decisionIds:` at the top of the markdown document you save. Cite only views you read, and never cite a section number in place of a view.\n\nEFFECTIVE VIEWS ARE SETTLED. A view whose file\'s frontmatter reads `lifecycle_state: effective` has been reviewed and approved: design against it as given and never re-decide it. Only a view in any other state is open to review: before your design rests on one, check it against the TRD, and where they disagree the TRD governs.'
      : '',
  ]
    .filter(Boolean)
    .join('\n\n')
}

async function main(a) {
  const s = (a && a.spec) || {}
  const trd = a && a.trd
  const constraints = Array.isArray(a && a.constraints) ? a.constraints : []
  const accessPatterns = Array.isArray(a && a.accessPatterns) ? a.accessPatterns : []
  const repoPath = (a && a.repoPath) || (s && s.repoPath) || null
  const epic = (a && a.epic) || null
  const uiItems = (Array.isArray(a && a.uiItems) ? a.uiItems : [])
    .filter((u) => u && hasText(u.id))
    .map((u) => ({
      id: u.id.trim(),
      element: hasText(u.element) ? u.element.trim() : null,
      designSource: hasText(u.designSource) ? u.designSource.trim() : hasText(u.buildSpec) ? 'bundle' : 'cds',
      buildSpec: hasText(u.buildSpec) ? u.buildSpec.trim() : null,
      sections: Array.isArray(u.sections) ? u.sections.filter(hasText).map((x) => x.trim()) : [],
    }))

  const ART = artifactsFrom(a && a.artifacts)
  const artSlug = ART && hasText(ART.slug) ? ART.slug : 'repo'
  const beads = beadsFrom(a && a.beads)
  const parentEpicKey = (epic && (epic.key || epic.id)) || null
  const specDocPaths = ART
    ? [`${ART.dir}/spec-${artSlug}.md`, `${ART.dir}/spec-${artSlug}.data-model.md`, `${ART.dir}/spec-${artSlug}.criteria.md`]
    : []

  if (!ART || !beads) {
    return { ok: false, stage: 'input', reason: 'no artifact directory or beads target was supplied, so the Story bead cannot be written' }
  }
  const writtenPath = `${ART.dir}/story-${artSlug}.written.json`
  const relay = relayFor(ART, artSlug, beads)
  const storyTail = [
    'write-story',
    `--epic ${shq(beads.epicId)} --dir ${shq(ART.dir)} --slug ${shq(artSlug)} --repo ${shq(repoPath)}`,
    hasText(beads.projectRoot) ? `--project-root ${shq(beads.projectRoot)}` : '',
    `--out ${shq(writtenPath)}`,
  ].filter(Boolean).join(' ')
  /** Writes the Story bead from the saved story-<slug>.json with depscore.py write-story; returns its checked output, or { error }. */
  const writeStory = () => relay.depscore('beads:write-story', 'Emit story', storyTail, beads.repo)
  /** Every save or record that did not land, named; the run goes on, as it did when the makers recorded their own files. */
  const persistErrors = []
  const recordOrNote = async (name, label, phaseName) => {
    const why = await relay.record(name, label, phaseName)
    if (why) {
      persistErrors.push(`${name}: ${why}`)
      log(`${name} was not recorded: ${why}`)
    }
  }

  /** Returns the spec-authoring result; `summary` is write-story's relayed summary, or null. */
  function storyResult(authored, summary, draft) {
    const w = summary && typeof summary === 'object' ? summary : {}
    log(hasText(w.id) ? `Story ${w.id} (story:${artSlug}) ${w.action || ''}` : `Story story:${artSlug}: write-story summary not relayed; beads is read at finish`)
    return {
      ok: true,
      ...authored,
      story: {
        key: (a && a.storyKey) || 'S1',
        type: 'story',
        id: hasText(w.id) ? w.id : null,
        elabKey: `story:${artSlug}`,
        title: (draft && draft.title) || null,
        description: (draft && draft.description) || null,
        repoPath,
        parentEpicKey,
      },
      writtenPath,
      summary: hasText(w.id) ? { created: Number(w.created) || 0, updated: Number(w.updated) || 0 } : null,
    }
  }

  if (a && a.replay === true) {
    log(`Spec authoring replayed: the Story is written from the saved story-${artSlug}.json`)
    const w = await writeStory()
    if (w.error) log(`write-story did not report its result: ${w.error}`)
    return storyResult({
      resumed: true,
      spec: { id: s.id || null, title: s.title || null, service: s.service || null, repoPath },
      specPaths: specDocPaths,
      outOfRepoFindings: [],
      apiSpec: { summary: '' },
      decisionIds: [],
      note: 'Replayed: the spec documents on disk are handed downstream as paths.',
    }, w.error ? null : w.summary, null)
  }

  const ctx = ctxBlock(s, trd, constraints, a && a.architecture, a && a.detailingPath)
  const specMakerCtx = `${ctx}\n\n${makerRules({ cites: true })}`
  const criteriaMakerCtx = `${ctx}\n\n${makerRules({ cites: false })}`
  const contractsBrief = persistBrief(
    ART,
    `spec-${artSlug}.md`,
    uiItems.length
      ? 'the contract artifacts you return — apiSpec, eventContracts, errorSpec and uiSpec — as ONE markdown document with a section for each of the first three and one UI section per uiSpec entry, headed by its item id (a bundle item\'s section citing its build-spec.md path and Section IDs), carrying each artifact\'s full content'
      : 'the three contract artifacts you return — apiSpec, eventContracts and errorSpec — as ONE markdown document with a section for each, carrying each artifact\'s full content'
  )
  const designLine = (u) =>
    u.designSource === 'bundle'
      ? `bundle — ${u.buildSpec}${u.sections.length ? ` (Sections ${u.sections.join(', ')})` : ''}`
      : u.designSource === 'none'
        ? 'none — it changes no design'
        : 'cds — designed with the CDS design system'
  const uiBrief = uiItems.length
    ? `\n4. \`uiSpec\` — one entry per UI item below: \`itemId\` (the item id), \`designSource\` (as given below), \`buildSpec\`, \`sections\` and \`content\` (what the repository builds for the item). By design source:
   - bundle: the owner supplied a cds bundle for the item. Specify it BY REFERENCE to that bundle: \`buildSpec\` is the absolute path of its \`spec/build-spec.md\` given below, \`sections\` the build spec's Section IDs it builds (an empty list when it builds the whole artifact), and \`content\` cites those Sections. Styling comes from that bundle's own stylesheets, so the spec adds no CSS, tokens or component stylesheet.
   - cds: the item changes design and is designed with the CDS design system by the implementing agent. \`buildSpec\` is "" and \`sections\` empty; \`content\` specifies the behaviour and content and states that the design comes from the CDS design system.
   - none: the item changes no design (copy, or data wired into an existing element). \`buildSpec\` is "" and \`sections\` empty; \`content\` specifies the change and states that it changes no design.
The workflow reads the document you save and checks that every UI item has a section headed by its item id, and that a bundle item's section cites the absolute path of its spec/build-spec.md and every Section ID given for it below.\n\nUI items${hasText(a && a.detailingPath) ? ` (each item's element and its from and to state are in the detailing file ${a.detailingPath})` : ''}:\n${uiItems.map((u) => `- ${u.id}${u.element ? ` ${u.element}` : ''}: ${designLine(u)}`).join('\n')}`
    : ''
  const contractsPrompt = (rework) => `Author the ${uiItems.length ? 'four' : 'three'} INTERFACE CONTRACT artifacts for this feature, each under its own key.

1. \`apiSpec\` — the API/OpenAPI contract specification (spec-first). Use the API type the TRD names. Define resources, methods, request/response schemas, status codes, and auth.
2. \`eventContracts\` — the event contracts/schemas. Event names and the envelope follow the event pattern the TRD names. Define each event's name, envelope, and payload schema.
3. \`errorSpec\` — the error-handling specification: error taxonomy, error responses (aligned to the API contract), retry/backoff and idempotency expectations, and how failures surface (errors stay visible — never silently swallowed).${uiBrief}${rework}

${specMakerCtx}${contractsBrief}${pointerNote}`
  const contractsOpts = {
    label: 'author:contracts',
    phase: 'Author specs',
    effort: 'medium',
    agentType: 'api-specification-author',
    schema: uiItems.length ? CONTRACTS_UI_SCHEMA : CONTRACTS_SCHEMA,
  }
  const dataModelBrief = persistBrief(ART, `spec-${artSlug}.data-model.md`, 'the data-model specification you return, with its full content, as a markdown document')
  const criteriaBrief = persistBrief(ART, `spec-${artSlug}.criteria.md`, 'the acceptance criteria and Definition of Done you return, as ONE markdown document with a section for each')
  const pointerNote = ART ? '\n\n`content` in your result need only be a one-line pointer to its section in the document you save.' : ''

  phase('Author specs')

  let [contractsDraft, dataModelSpecDraft] = await parallel([
    () => settleAgent(contractsPrompt(''), contractsOpts),
    () =>
      settleAgent(
        `Author the data-model specification for this feature: the data stores the target and delta views show for this repository, designed as those views and the TRD describe them. Define the stores, keys, indexes and item shapes that satisfy every access pattern below.\n\nKnown access patterns:\n${accessPatterns.length ? accessPatterns.map((p, i) => `${i + 1}. ${p}`).join('\n') : '(derive the access patterns from the spec context)'}\n\n${specMakerCtx}${dataModelBrief}${pointerNote}`,
        {
          label: 'author:data-model',
          phase: 'Author specs',
          effort: 'medium',
          agentType: 'data-model-specification-author',
          schema: SPEC_SCHEMA,
        }
      ),

  ])

  const deadMakers = [
    ['contracts', contractsDraft],
    ['data-model', dataModelSpecDraft],
  ].filter(([, d]) => !d).map(([k]) => k)
  if (deadMakers.length) {
    const deaths = dispatchDeaths('Author specs')
    return {
      ok: false,
      stage: 'author',
      reason: `the spec maker(s) ${deadMakers.join(', ')} returned nothing — the spec set is incomplete.`,
      ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
    }
  }

  await recordOrNote(`spec-${artSlug}.md`, 'record:contracts', 'Author specs')
  await recordOrNote(`spec-${artSlug}.data-model.md`, 'record:data-model', 'Author specs')

  // The saved spec document is what later phases read, so its UI sections are checked by
  // depscore.py spec-ui-check reading the file, beside the check on the structured uiSpec.
  const uiCheckTail = `spec-ui-check --doc ${shq(`${ART.dir}/spec-${artSlug}.md`)} --items ${shq(JSON.stringify(uiItems.map((u) => ({ id: u.id, designSource: u.designSource, buildSpec: u.buildSpec, sections: u.sections }))))}`
  const uiGapsOf = async (draft, round) => {
    const own = uiCitationGaps(uiItems, draft.uiSpec)
    const doc = await relay.depscore(`ui-citation-check${round}`, 'Author specs', uiCheckTail, null)
    if (doc.error) return { error: `depscore.py spec-ui-check could not check spec-${artSlug}.md: ${doc.error}` }
    const seen = new Set()
    return {
      gaps: [...own, ...(Array.isArray(doc.gaps) ? doc.gaps : [])]
        .filter((g) => g && hasText(g.id) && hasText(g.problem))
        .filter((g) => !seen.has(`${g.id}|${g.problem}`) && seen.add(`${g.id}|${g.problem}`)),
    }
  }
  const uiCheckFailed = (check) => ({ ok: false, stage: 'ui-citation', reason: check.error })
  let uiCheck = uiItems.length ? await uiGapsOf(contractsDraft, '') : { gaps: [] }
  if (uiCheck.error) return uiCheckFailed(uiCheck)
  let uiGaps = uiCheck.gaps
  if (uiGaps.length) {
    log(`UI citation check: ${uiGaps.map((g) => `${g.id}: ${g.problem}`).join('; ')} — the contracts go back to their maker once`)
    const reworked = await settleAgent(
      contractsPrompt(`\n\nREWORK — the workflow's check found UI items whose section, in the uiSpec you returned or in the spec document you saved, is missing or, for a bundle item, does not cite its build spec:\n${uiGaps.map((g) => `- ${g.id}: ${g.problem}`).join('\n')}\nRead the current saved document ${ART.dir}/spec-${artSlug}.md first. Repair only the cited item sections and any directly affected references; preserve all other valid API, event, error and UI content, decisions, obligation IDs and source provenance. Return all four artifacts with the unchanged portions retained and save the same document, keeping a section for every UI item and every bundle item specified by reference to its spec/build-spec.md and its Section IDs. If a cited fix requires a wider behavioral change, identify that conflict instead of silently rewriting the accepted remainder.`),
      { ...contractsOpts, label: 'author:contracts:rework' }
    )
    if (!reworked) {
      const deaths = dispatchDeaths('Author specs')
      return {
        ok: false,
        stage: 'ui-citation',
        reason: `the contracts maker returned nothing for the UI citation rework, so the gaps stand — ${uiGaps.map((g) => `${g.id}: ${g.problem}`).join('; ')}`,
        uiGaps,
        ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
      }
    }
    contractsDraft = reworked
    await recordOrNote(`spec-${artSlug}.md`, 'record:contracts:rework', 'Author specs')
    uiCheck = await uiGapsOf(contractsDraft, ':rework')
    if (uiCheck.error) return uiCheckFailed(uiCheck)
    uiGaps = uiCheck.gaps
    if (uiGaps.length) {
      return {
        ok: false,
        stage: 'ui-citation',
        reason: `the UI spec still has gaps after one rework — ${uiGaps.map((g) => `${g.id}: ${g.problem}`).join('; ')}`,
        uiGaps,
      }
    }
  }

  const criteriaDraft = await settleAgent(
        `Author two artifacts for this spec, each under its own key.

1. \`acceptanceCriteria\` — testable given/when/then statements covering the happy path, error paths, and boundary conditions. Every behaviour the spec set states gets a criterion; cover each behaviour ONCE rather than enumerating variants of it, and keep each clause under 30 words. At most ${CRITERIA_MAX} criteria.
2. \`definitionOfDone\` — a concrete, verifiable checklist (spec-first OpenAPI present, schemas typed at boundaries, tests defined, docs current, etc.). At most ${DOD_MAX} items.

FINAL SPEC INPUTS — read these completed documents, including the UI citation repair already applied: ${specDocPaths.slice(0, 2).join(', ')}. Derive the criteria from their actual contract/data-model/UI behavior and trace each to its delta/TRD obligation ID and source section. Preserve the supplied implementation provenance; do not re-author these documents or infer their final choices from summaries. A missing document or contradiction is an explicit unresolved input, never invented behavior.

${criteriaMakerCtx}${criteriaBrief}`,
        {
          label: 'author:criteria',
          phase: 'Author specs',
          effort: 'low',
          agentType: 'acceptance-criteria-writer',
          schema: CRITERIA_SCHEMA,
        }
      )

  if (!criteriaDraft) {
    const deaths = dispatchDeaths('Author specs')
    return {
      ok: false, stage: 'author', reason: 'the criteria maker returned nothing after the completed spec documents — the spec set is incomplete.',
      ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
    }
  }
  await recordOrNote(`spec-${artSlug}.criteria.md`, 'record:criteria', 'Author specs')

  const apiSpec = contractsDraft.apiSpec
  const uiSpec = uiItems.length && Array.isArray(contractsDraft.uiSpec) ? contractsDraft.uiSpec : []
  const eventContracts = contractsDraft.eventContracts
  const errorSpec = contractsDraft.errorSpec
  const dataModelSpec = dataModelSpecDraft

  phase('Emit story')

  const specDigest = [
    ...[['apiSpec', apiSpec], ['dataModelSpec', dataModelSpec], ['eventContracts', eventContracts], ['errorSpec', errorSpec]]
      .map(([k, x]) => `- ${k}: ${(x && hasText(x.summary) && x.summary) || '(no summary)'}`),
    `- acceptanceCriteria: ${Array.isArray(criteriaDraft.acceptanceCriteria) ? criteriaDraft.acceptanceCriteria.length : 0} criteria`,
  ].join('\n')
  const storyCtx = [`Spec ${s.id || ''}: ${s.title || ''}`, s.service ? `Owning service: ${s.service}` : '', s.summary ? `What this spec covers:\n${s.summary}` : '']
    .filter(Boolean)
    .join('\n\n')
  const decisionIds = [...new Set(
    [apiSpec, dataModelSpec, eventContracts, errorSpec]
      .flatMap((x) => (x && Array.isArray(x.decisionIds) ? x.decisionIds : []))
      .map((x) => String(x == null ? '' : x).trim())
      .filter(Boolean)
  )]
  const storyBrief = persistBrief(
    ART,
    `story-${artSlug}.json`,
    `your complete structured result (title, description — exactly as you return them) plus the key "decisionIds" holding exactly this list, ${JSON.stringify(decisionIds)}, as ONE JSON object`
  )

  const storyDraft = await settleAgent(
    `Author the Story bead this Spec pairs with. A Story is scoped to a SINGLE repository — the one named below. Write a title and a description stating what this Story contains in terms of the authored spec set. The Story is a CONTAINER: it is never worked and never itself decomposed — do NOT include a task breakdown, a WSJF score, or any priority.\n\nThis Story's single repository: ${repoPath || '(none supplied)'}\n\nAuthored spec set:\n${specDigest}${specDocPaths.length ? `\n\nThe spec documents:\n${specDocPaths.map((p) => `- ${p}`).join('\n')}` : ''}\n\n${storyCtx}${storyBrief}

Run no bd command and do not write the Story bead: the workflow writes it from the saved file after you return.`,
    {
      label: 'author:story-bead',
      phase: 'Emit story',
      effort: 'low',
      agentType: 'agent-teams-workforce:user-story-writer',
      schema: STORY_SCHEMA,
    }
  )

  if (!storyDraft) {
    const deaths = dispatchDeaths('Emit story')
    return {
      ok: false,
      stage: 'story',
      reason: 'the Story writer returned nothing — the Spec has no Story to pair with.',
      ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
    }
  }

  // The Story file write-story reads must hold exactly what the writer returned, decisionIds
  // included; a file that cannot be made to hold it writes no bead.
  const storyValue = { title: storyDraft.title, description: storyDraft.description, decisionIds }
  const storySaveError = await relay.ensureJson(`story-${artSlug}.json`, 'save:story', 'Emit story', storyValue)
  if (storySaveError) {
    return {
      ok: false,
      stage: 'story',
      reason: `story-${artSlug}.json does not hold the Story the writer returned, so no Story bead was written: ${storySaveError}`,
      ...(persistErrors.length ? { persistErrors } : {}),
    }
  }
  await recordOrNote(`story-${artSlug}.json`, 'record:story', 'Emit story')
  const written = await writeStory()
  if (written.error) log(`write-story did not report its result: ${written.error}`)
  const relayed = written.error ? null : written.summary
  return storyResult({
    ...(persistErrors.length ? { persistErrors } : {}),
    unresolvedArtifacts: [],
    spec: {
      id: s.id || null,
      title: s.title || null,
      service: s.service || null,
      repoPath,
    },
    apiSpec,
    dataModelSpec,
    eventContracts,
    errorSpec,
    uiSpec,
    decisionIds,
    outOfRepoFindings: [],
    note: 'The Story is a CONTAINER (no tasks, no WSJF) covering exactly one repo; depscore.py write-story writes its bead.',
  }, relayed, storyDraft)
}

return dispatchOutcome(await main(typeof args === 'string' ? JSON.parse(args) : (args || {})))
