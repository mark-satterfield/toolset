export const meta = {
  name: 'task-decomposition',
  description:
    'Leaf mini — decomposes ONE Spec into TASKS ONLY, parented to the Story that Spec pairs with, in the Story\'s single repo. A Task is build work: the Spec\'s acceptance criteria are the tests inside the build Tasks, written by their Red step, so no Task only writes tests. Tasks are made only for the delta items the repository\'s detailing marks add, modify or remove: depscore.py plan-tasks refuses a Task that cites none of them in requirementIds, and a done or planned-elsewhere item gets no Task. An open Task of another Epic in the same repository that already plans the work is not duplicated: the Tasks that need it carry its id in blockedByExternal, and write-task writes that blocks edge. A Task with the web-ui surface gets in its build contract the design source of the ui items it cites, from the detailing\'s uiAuthority (cds_design_source): bundle, with the supplied cds bundle and the build-spec.md citations (cds_bundle_path, cds_build_specs); cds, designed with the CDS design system; or none, a change with no design impact. A bundle or cds Task also records its artifact (cds_artifact: the kind and slug a bundle.json names), so task-to-deploy builds from a mockup supplied any time before the Task is built. plan-tasks refuses a web-ui Task whose ui items are of two artifacts and a bundle Task with no build-spec citation. A Story with nothing to build gets no Tasks and goes straight to deploy and verify. One maker session decomposes, names the dependency edges and sizes every task, and saves the result as tasks-<slug>.json; the script checks that file holds exactly what the maker returned (writing it when it does not), records it, and writes each Task bead through the checked relay: depscore.py plan-tasks reads that file, runs no bd command, and lists the Tasks in build order with their elab_keys (it makes repeated task keys unique as K, K-2, K-3, applying an edge on K to each, drops edges that do not join two known tasks, and refuses a cyclic graph); then the script runs one depscore.py write-task command per Task, one at a time in that order, each writing ONE Task bead under the Epic\'s Story for the slug, found in beads, with its metadata, size fingerprint and blocks edges to the Tasks written before it. With replay: true the maker does not run, and the script runs the same commands from the saved tasks-<slug>.json. Whether the beads landed is read from beads by depscore.py elaboration-finish, not judged here.',
  phases: [
    { title: 'Decompose', detail: 'one maker session: Spec -> tasks + dependency edges + job sizes; the script writes each Task bead with one depscore.py write-task command' },
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
//   spec: { id?, title?, description?, source?, repoPath? }, story: { id?, key?, title? },
//   specDocs?: [{ path, ref }], repoPath?, pluginRoot,
//   detailingPath?: <absolute path of the repository's saved delta detailing, recon-<slug>.json; the maker reads it>,
//   artifacts: { dir, relDir?, epicId, script, phase, slug, inputs? },
//   beads: { script, repo, epicId, projectRoot? }  (script: the absolute depscore.py path),
//   packagesDir?: string (the packages directory every cds bundle a Task cites must sit in; omitted accepts the bundles the detailing cites),
//   replay?: true
// }
// returns { ok, resumed?, spec, repoPath, story: { id, elabKey }, tasks, edges, summary }; tasks, edges and
//           summary carry what the writing session relayed, and are empty or null where it relayed nothing,
//           or { ok: false, stage, reason, dispatchFailed? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
/** The save instruction appended to the maker's prompt; the workflow checks and records the file after the maker returns. */
function persistBrief(art, name, what) {
  if (!art) return ''
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\nWrite ${what} to ${art.dir}/${name} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this, and run no command to record it or to write any bead: the workflow checks and records the file, and writes the Task beads from it, after you return.\nIf the write fails, say so in your result and still return your result.`
}
const ART = artifactsFrom(a.artifacts)
const artSlug = ART && typeof ART.slug === 'string' && ART.slug ? ART.slug : 'repo'
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const beadsFrom = (x) => (x && typeof x === 'object' && ['script', 'repo', 'epicId'].every((k) => hasText(x[k])) ? x : null)
const BEADS = beadsFrom(a.beads)

const spec = a.spec || {}
const story = a.story || {}

const specRef = spec.id || spec.title || '(unspecified spec)'
const storyRef = story.key || null
const repoPath = spec.repoPath || a.repoPath || null

const specDocs = (Array.isArray(a.specDocs) ? a.specDocs : [])
  .map((d) => (typeof d === 'string' ? { path: d, ref: null } : d && typeof d === 'object' ? d : null))
  .filter((d) => d && typeof d.path === 'string' && d.path.trim())
  .map((d) => ({ path: d.path.trim(), ref: typeof d.ref === 'string' && d.ref.trim() ? d.ref.trim() : null }))
const docsBlock = specDocs.length
  ? `\n\nSPEC DOCUMENTS — THE CONTRACT. The text above is a navigation aid only; the API contract, data model, event contracts, error handling, acceptance criteria and Definition of Done are in these files. Read the sections each task needs before you decompose:\n${specDocs
      .map((d) => `- ${d.path}${d.ref ? `  (cite as: ${d.ref})` : ''}`)
      .join('\n')}`
  : '\n\nSPEC DOCUMENTS: none were supplied, so the text above is all there is.'

const writtenPath = ART ? `${ART.dir}/story-${artSlug}.written.json` : null
const existingBlock = writtenPath
  ? `\n\nEXISTING TASKS under this Story: read the file ${writtenPath} — the result of writing this Story — and take its "existingTasks" list (none when the file or the list is absent or empty). When a task you write covers the same work as one of them, set its \`reuses\` to that task's exact elabKey; otherwise set \`reuses\` to null. Never reuse one elabKey for two tasks.\n\nOPEN TASKS OF OTHER EPICS in this repository: take the "otherEpicTasks" list of the same file (none when it is absent or empty). When work you would give a task is already planned by one of them, or by a bead a \`planned-elsewhere\` item names, do not write that task: put that Task's id in \`blockedByExternal\` of every task of yours that needs the work built first. Otherwise set \`blockedByExternal\` to an empty list.`
  : '\n\nEXISTING TASKS: none. Set every task\'s `reuses` to null and its `blockedByExternal` to an empty list.'

const detailingPath = typeof a.detailingPath === 'string' && a.detailingPath.trim().startsWith('/') ? a.detailingPath.trim() : null
const detailingBlock = detailingPath
  ? `\n\nTHE DELTA DETAILING of this repository is the file ${detailingPath}. Read it: its \`items\` give each delta item its id (the ids \`requirementIds\` cites), its status, its element, the \`from\` and \`to\` state, its surface and its evidence; its \`uiAuthority.uiItems\` give each \`ui\` item its design source — bundle (a cds bundle the owner supplied, with its build spec), cds (designed with the CDS design system) or none (no design change).`
  : ''
const specBlock = `Spec ${spec.id || ''}: ${spec.title || ''}
${spec.description || ''}
${spec.source ? `Source: ${spec.source}` : ''}
Repository: ${repoPath || '(repo path not provided)'}
Parent Story: ${storyRef}${story.title ? ` — ${story.title}` : ''}${detailingBlock}${docsBlock}${existingBlock}`

// The surface names tdd-red and integration select writers and suites by.
const SURFACES = ['api-contract', 'event-chain', 'auth', 'performance', 'web-ui', 'ios', 'android', 'cross-platform-mobile', 'ml', 'data-pipeline']

const taskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'title', 'description', 'type', 'acceptanceCriteria', 'definitionOfDone', 'specPaths', 'specSections', 'requirementIds', 'surfaces', 'reuses', 'blockedByExternal'],
  properties: {
    key: { type: 'string' },
    title: { type: 'string' },
    description: { type: 'string' },
    type: { type: 'string', enum: ['task'] },
    acceptanceCriteria: { type: 'array', items: { type: 'string' } },
    definitionOfDone: { type: 'array', items: { type: 'string' } },
    specPaths: { type: 'array', items: { type: 'string' } },
    specSections: { type: 'array', items: { type: 'string' } },
    requirementIds: { type: 'array', items: { type: 'string' } },
    decisionIds: { type: 'array', items: { type: 'string' } },
    reuses: { type: ['string', 'null'] },
    blockedByExternal: { type: 'array', items: { type: 'string' } },
    surfaces: { type: ['array', 'null'], items: { type: 'string', enum: SURFACES } },
  },
}
const testStrategySchema = {
  type: ['object', 'null'],
  additionalProperties: false,
  required: ['pyramid', 'coverageThreshold', 'envMatrix', 'source'],
  properties: {
    pyramid: { type: 'string' },
    coverageThreshold: { type: 'string' },
    envMatrix: { type: 'array', items: { type: 'string' } },
    source: { type: 'string' },
  },
}

const writable = !!(ART && BEADS && hasText(repoPath))
const taskArgs = writable
  ? [
      `--dir ${shq(ART.dir)} --slug ${shq(artSlug)} --repo ${shq(repoPath)}`,
      hasText(BEADS.projectRoot) ? `--project-root ${shq(BEADS.projectRoot)}` : '',
      hasText(a.packagesDir) ? `--packages-dir ${shq(a.packagesDir.trim())}` : '',
    ].filter(Boolean).join(' ')
  : ''
/** The relay files of this Story's commands, numbered so a run's names are deterministic. */
const RELAY_DIR = writable ? `${ART.dir}/relay/tasks-${artSlug}` : ''
const RELAY_RUNNER = writable ? BEADS.script.replace(/[^/]+$/, 'relayrun.py') : ''
let relaySeq = 0
function relayFile(label) {
  relaySeq += 1
  return `${RELAY_DIR}/${String(relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
}
const depscore = (label, tail, repo) => relayKit.depscore(settleAgent, { label, phase: 'Decompose', script: BEADS.script, repo: repo || null, tail, file: relayFile(label) })
/**
 * Writes each Task bead from the saved tasks-<slug>.json: depscore.py plan-tasks lists the Tasks in
 * build order, then one depscore.py write-task per Task, in that order, stopping at the first that
 * fails. Returns { plan, written, error }: written holds each write-task result checked through the relay.
 */
async function writeTasks() {
  const plan = await depscore('beads:plan-tasks', `plan-tasks ${taskArgs}`, null)
  if (plan.error) return { plan: null, written: [], error: `depscore.py plan-tasks: ${plan.error}` }
  if (!Array.isArray(plan.tasks)) return { plan: null, written: [], error: 'depscore.py plan-tasks printed no task list' }
  const written = []
  for (const t of plan.tasks) {
    const key = t && hasText(t.key) ? t.key.trim() : ''
    if (!key) return { plan, written, error: 'depscore.py plan-tasks listed a task with no key' }
    const external = (Array.isArray(t.blockedByExternal) ? t.blockedByExternal : []).filter(hasText).map((x) => x.trim())
    const tail = `write-task --epic ${shq(BEADS.epicId)} --key ${shq(key)} ${taskArgs}${external.length ? ` --blocked-by-external ${shq(external.join(','))}` : ''}`
    const w = await depscore(`beads:write-task:${key}`, tail, BEADS.repo)
    if (w.error) return { plan, written, error: `depscore.py write-task ${key}: ${w.error}` }
    written.push(w)
  }
  return { plan, written, error: '' }
}
/** Records the saved tasks-<slug>.json with the artifact script's `record`; returns '' or why it was not recorded. */
async function recordTasks() {
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
  const argv = ['python3', ART.script, 'record', `${ART.dir}/tasks-${artSlug}.json`, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])]
  const r = await relayKit.run(settleAgent, { label: 'record:tasks', phase: 'Decompose', runner: RELAY_RUNNER, argv, file: relayFile('record:tasks'), keys: ['sha256', 'bytes'], tail: 20 })
  if (!r.ok) return r.error
  return r.exitCode === 0 ? '' : `the record command exited ${r.exitCode}: ${String(r.stderrTail || r.stdoutTail || '').trim().slice(0, 600)}`
}

phase('Decompose')
log(`Decomposing, sequencing, and sizing ${specRef}`)

const wsjfTaskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'jobSize', 'sizeLow', 'sizeHigh', 'sizeConfidence', 'rationale'],
  properties: {
    key: { type: 'string' },
    jobSize: { type: 'number' },
    sizeLow: { type: 'number' },
    sizeHigh: { type: 'number' },
    sizeConfidence: { type: 'integer' },
    rationale: { type: 'string' },
  },
}

const WSJF_SKILL_DIR = typeof a.pluginRoot === 'string' && a.pluginRoot.startsWith('/') ? `${a.pluginRoot.replace(/\/+$/, '')}/skills/wsjf` : null
const JOB_SIZE_BRIEF = `Size each task under "Job Size" in the \`agent-teams-workforce:wsjf\` rubric${WSJF_SKILL_DIR ? ` (${WSJF_SKILL_DIR}/SKILL.md)` : ''}: the relative amount of work to deliver the task's outcome, judged against the agent pipeline as the reference capability — not calendar time and not human effort. Weigh volume, complexity, knowledge and uncertainty together to place it. The scale is Fibonacci (1, 2, 3, 5, 8, 13, 21, and upward); compare with the rubric's reference jobs. Every size carries \`sizeLow\` and \`sizeHigh\`, the plausible range with the size inside it, and \`sizeConfidence\`, an integer percent. Value, time criticality and risk reduction are inherited from the parent Epic and computed from the dependency graph, and are NOT yours to assign. A Task above 13 should have been split: say so in your notes, and record the size you judged.`

if (!writable) {
  return dispatchOutcome({ ok: false, stage: 'input', reason: 'no artifact directory, beads target or repository was supplied, so the Task beads cannot be written', spec: specRef })
}
const replayed = a.replay === true
if (replayed) log(`Decompose replayed: the Tasks are written from the saved tasks-${artSlug}.json`)
const maker = replayed ? null : await settleAgent(
  `Three maker jobs on the Spec below, in order, one pass. Do NOT write code.

JOB 1 — DECOMPOSE (return in \`tasks\` + \`rationale\`): decompose the Spec into TASKS. Each task is a coherent piece of the Story's work within the single repository named below that one agent can test and build in one session, with testable acceptance criteria. A small Story may be one task.
- A task is BUILD work: it changes code, infrastructure or documentation. The Spec's acceptance criteria are the tests of the build tasks: each build task carries in \`acceptanceCriteria\` the criteria it satisfies, and its Red step writes those tests before it builds. A task whose only work is writing or running tests is never emitted.
- Only a delta item the detailing marks \`add\`, \`modify\` or \`remove\` makes work; a \`done\` or \`planned-elsewhere\` item gets no task. Every task cites in \`requirementIds\` at least one such item it builds: depscore.py plan-tasks refuses a task that cites none, and no bead is written.
- When nothing needs building, return an empty \`tasks\` list with empty \`edges\` and \`scores\`, and say why in \`rationale\`. The Story then has no Tasks and goes straight to deploy and verify. Give each a unique local "key" (T1, T2, …). You emit TASKS ONLY — every item has type "task". Do not emit an Epic, a Story, or a loose feature: the Epic and the Story already exist upstream, and every task you emit is a child of the Story named below.

EVIDENCE CONTINUITY. In each task's existing description, retain the detailing/spec's exact repository path, source commit, file:line or document heading and the obligation IDs linked by requirementIds. State what that evidence already establishes and the concrete remaining gap. Reuse sufficient evidence at the same main revision. Before another source read, name the changed revision, missing evidence or unanswered question that calls for it; check only the relevant paths and affected integration dependencies. If the main revision changed or a legacy citation has no revision, refresh only the affected evidence and record the new revision while preserving the historical citation. Do not claim an unchanged source proves tests ran. A working path stays preserved, a stub names its missing behavior, and a missing integration cites its attachment point; none warrants a fresh fleet survey.

EXISTING-REPOSITORY TASKS ARE INCREMENTAL CHANGES. In this same decomposition pass, use the detailing's citations and inspect the relevant existing entrypoints, implementation, contracts and focused tests in the named repository. Do not repeat a fleet survey. Code may be working, incomplete, a stub or unverified: neither trust it solely because it exists nor replace it wholesale because its provenance is uncertain. In each task's existing \`description\`, identify the inspected current behavior with file:line references, the concrete gap, affected files/integration points, required behavioral change and supported behavior/contracts to preserve. The task's \`acceptanceCriteria\` and \`definitionOfDone\` specify how to verify that change and the relevant regression boundary; distinguish tests merely read from results actually observed. Reuse evidenced working parts. Any replacement must have a requirement-backed reason and respect the approved architecture. Missing code becomes a bounded implementation task in the existing owner, not a new feature/service/repository by default. If current code materially contradicts a detailing status or the spec, report the conflict in \`rationale\`/\`notes\` for correction instead of silently changing the approved scope or inventing build work.

Every task also carries its CONTRACT, taken from the spec documents listed below:
- \`specPaths\`: the spec documents this task builds against, cited EXACTLY as the "cite as" value given for each. At least one.
- \`specSections\`: the headings or anchors inside those documents that define this task.
- \`requirementIds\`: the delta item ids (D1, D2, …) the task builds, as the detailing below lists them, and the TRD requirement ids it satisfies.
- \`decisionIds\`: the architecture views the spec documents cite for the part of the design this task builds, each a path relative to the arc42 folder with its \`#<heading>\` where the spec gives one. Copy them; never invent one.
- \`definitionOfDone\`: the Definition of Done items that apply to this task, from the spec's DoD.
- \`blockedByExternal\`: the ids of open Tasks of other Epics that must be built before this task, as described under OPEN TASKS OF OTHER EPICS below; an empty list when there are none.
- \`surfaces\`: the boundaries the task touches, from the enum only (${SURFACES.join(', ')}). An empty list means it touches none of them; null means the spec does not settle it. A task that builds a \`ui\` delta item carries \`web-ui\` and cites that item's id in \`requirementIds\`: write-task then records in its contract the design source of the items it cites — bundle (the supplied cds bundle and the \`build-spec.md\` Sections the detailing resolved; the builder builds from it and is audited against it), cds (the builder designs with the CDS design system and is audited against the live design system) or none (no design change, built like any other code); a bundle or cds task also records the artifact (kind and slug) its UI is, and the build uses the newest bundle of that artifact supplied when the task is built. A task builds one artifact: keep the ui items of different artifacts in different tasks, since depscore.py plan-tasks refuses a task that cites ui items of two artifacts.
And once for the whole set, \`testStrategy\`: the test strategy the spec states (pyramid, coverageThreshold, envMatrix, and the section it came from as \`source\`), or null when the spec states none.

JOB 2 — SEQUENCE (return in \`edges\`): the dependencies between the tasks as a DIRECTED ACYCLIC graph. An edge "from -> to" means "from must be built before to", and both ends are keys of tasks you returned.

JOB 3 — SIZE EVERY TASK (return in \`scores\`): ${JOB_SIZE_BRIEF} Return one entry per task: its \`key\`, its \`jobSize\`, \`sizeLow\`, \`sizeHigh\`, \`sizeConfidence\`, and a one-line \`rationale\`.

${specBlock}${persistBrief(ART, `tasks-${artSlug}.json`, 'your complete structured result (tasks, testStrategy, rationale, edges, scores, notes — exactly as you return them) as ONE JSON object')}`,
  {
    label: 'decompose:sequence-and-score',
    effort: 'medium',
    phase: 'Decompose',
    agentType: 'task-decomposer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['tasks', 'testStrategy', 'rationale', 'edges', 'scores'],
      properties: {
        tasks: { type: 'array', items: taskSchema },
        testStrategy: testStrategySchema,
        rationale: { type: 'string' },
        edges: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['from', 'to'],
            properties: {
              from: { type: 'string' },
              to: { type: 'string' },
            },
          },
        },
        scores: { type: 'array', items: wsjfTaskSchema },
        notes: { type: 'string' },
      },
    },
  }
)
if (!replayed && (!maker || !Array.isArray(maker.tasks))) {
  const deaths = dispatchDeaths('Decompose')
  return dispatchOutcome({
    ok: false,
    stage: 'decompose',
    reason: 'the decomposition returned no task list',
    spec: specRef,
    ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
  })
}
// The Task beads are written from tasks-<slug>.json, so it must hold exactly what the maker
// returned: the script checks it (writing it when it differs) before any bead is written.
let recordError = ''
if (!replayed) {
  const saved = await relayKit.ensureJson(settleAgent, { label: 'save:tasks', phase: 'Decompose', runner: RELAY_RUNNER, file: `${ART.dir}/tasks-${artSlug}.json`, value: maker })
  if (!saved.ok) {
    const deaths = dispatchDeaths('Decompose')
    return dispatchOutcome({
      ok: false,
      stage: 'decompose',
      reason: `tasks-${artSlug}.json does not hold the decomposition the maker returned, so no Task bead was written: ${saved.error || 'not saved'}`,
      spec: specRef,
      ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
    })
  }
  recordError = await recordTasks()
  if (recordError) log(`tasks-${artSlug}.json was not recorded: ${recordError}`)
}
const ran = await writeTasks()
if (ran.error) log(`Story story:${artSlug}: the Task beads were not all written — ${ran.error}`)
const plan = ran.plan
const written = ran.written.filter((w) => w && w.task)
const writtenTasks = written.length
  ? written.map((w) => w.task)
  : plan
    ? plan.tasks.map((t) => ({ key: t.key, elabKey: t.elabKey, id: null, action: null, title: t.title, dependsOn: t.dependsOn, outsideBlockers: [] }))
    : (maker && Array.isArray(maker.tasks) ? maker.tasks : []).map((t) => ({ key: t.key, elabKey: null, id: null, action: null, title: t.title, dependsOn: [], outsideBlockers: [] }))
const edges = { added: 0, removed: 0, standing: 0 }
for (const w of written) for (const k of Object.keys(edges)) edges[k] += Number(w.edges && w.edges[k]) || 0
const actions = written.map((w) => w.task.action)
const summary = written.length
  ? {
      created: actions.filter((x) => x === 'created').length,
      updated: actions.filter((x) => x === 'updated').length,
      unchanged: actions.filter((x) => x === 'unchanged' || x === 'unchanged-started').length,
    }
  : null
if (maker && !maker.tasks.length) log(`Story story:${artSlug}: no Tasks — ${String(maker.rationale || 'nothing to build').slice(0, 300)}`)
log(`Story story:${artSlug}: ${written.length} write-task result(s) relayed${summary ? ` ${JSON.stringify(summary)}` : ''}; beads is read at finish`)

return dispatchOutcome({
  ok: true,
  ...(replayed ? { resumed: true } : {}),
  spec: specRef,
  repoPath,
  story: { id: story.id || null, elabKey: `story:${artSlug}` },
  tasks: writtenTasks,
  edges,
  summary,
  ...(ran.error ? { writeError: ran.error } : {}),
  ...(recordError ? { persistErrors: [`tasks-${artSlug}.json: ${recordError}`] } : {}),
})
