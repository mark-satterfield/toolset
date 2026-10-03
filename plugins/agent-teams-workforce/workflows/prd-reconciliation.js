export const meta = {
  name: 'prd-reconciliation',
  description:
    'Leaf mini — per-repository detailing of an approved architecture delta. One read-only session compares each delta item placed in one repository (one element the delta shows) with the code on that repository\'s main, gives it one status — add, modify, remove, done, or planned-elsewhere — each citing file:line (planned-elsewhere also names the open bead that plans it), gives each ui item its design source — bundle (a single-artifact cds bundle the owner supplied in the packages directory packages it; the newest bundle of a kind and slug is the supplied one), cds (it changes design and no bundle packages it, so it is designed with the CDS design system) or none (it changes no design) ; a bundle or cds item also names its artifact (kind and slug, as a bundle.json names it), so a mockup supplied later is found when the Task is built — and reports upstream dependency changes. The script fails the run, naming the items, when an item is missing or listed twice, carries a status outside that set, or lacks its citation; a failed detailing blocks that repository\'s Spec. The session saves the detailing as recon-<slug>.json and returns no item content; depscore.py recon-facts checks the saved file on disk and returns only the facts the callers branch on (the ids that make work, the ids that do not, each ui work item\'s design source with the bundle and build spec of a bundle item, whether dependencies are current), and the callers hand the file path to the sessions that read it. A saved result is replayed through the same check instead of dispatching the session; a saved file that cannot be read or is not a usable detailing stops the run, naming the file, and the repository is never detailed again behind it.',
  phases: [{ title: 'Detailing', detail: 'one read-only session compares each delta item placed in the repository with the code on its main, and checks upstream dependencies' }],
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
// - every result is printed as ONE line: a flat object of scalars (the view's leaves keyed by
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
    properties: { exitCode: { type: 'integer' }, stdout: { type: 'string' } },
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
      env = JSON.parse(String(stdout || '').trim())
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

It prints exactly one line. Return the process exit code as \`exitCode\` and that line, verbatim, as the string \`stdout\`: every character as printed, in order, with nothing added, removed, reordered, reformatted or re-typed. Do not parse it, do not summarize it. If it printed more than one line, return all of stdout verbatim. Do not retry, do not repair, do not run any other command.`
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
    '    print(c(dict(f, **{"~exit": ex, "~checksum": h({"exit": ex, "view": f})})))',
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
//   prd: { id?, title?, path?, repoPath? }, repos: [<the one repository>],
//   items: [{ id, element, views? }] (the delta items placed in this repository),
//   delta: { targetDir, deltaDir },
//   mocksDir?, packagesDir?, shellsDir? (packagesDir holds zero or more single-artifact cds bundles; absent or empty supplies none), dependencies?: string[], uiRepo?: boolean (false skips the cds UI resolution),
//   artifacts: { dir, relDir?, epicId, script, phase, inputs?, slug } (required: the detailing lives only in recon-<slug>.json),
//   depscore: <absolute path of depscore.py> (required: recon-facts reads the saved detailing),
//   replay?: { files: { recon: <absolute path of a saved result> } }
// }
// returns { ok, resumed?, reconPath, itemCount, counts, work, idle, uiWork, bundles, mocksDir,
//           dependenciesCurrent, dependencyFindings, ledger } — facts only; the items are in reconPath
//   or { ok: false, stage, headline, reason, reconPath?, failedItems?, dispatchFailed? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const prdInput = a.prd && typeof a.prd === 'object' ? a.prd : {}
const prdId = prdInput.id || ''
const prdTitle = prdInput.title || ''
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const repoPath = prdInput.repoPath || a.repoPath || ''
const repos = (Array.isArray(a.repos) && a.repos.length ? a.repos : [repoPath]).filter((r) => hasText(r))
const dependencies = Array.isArray(a.dependencies) ? a.dependencies : []
const repoRoot = hasText(repoPath) ? repoPath.replace(/\/+$/, '') : ''
const uiCheck = a.uiRepo !== false
const mocksDir = uiCheck && hasText(a.mocksDir) ? a.mocksDir.trim() : ''
const packagesDir = uiCheck && hasText(a.packagesDir) ? a.packagesDir.trim() : ''
const shellsDir = uiCheck && hasText(a.shellsDir) ? a.shellsDir.trim() : ''
const delta = a.delta && typeof a.delta === 'object' ? a.delta : {}
const placed = (Array.isArray(a.items) ? a.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))

const STATUSES = ['add', 'modify', 'remove', 'done', 'planned-elsewhere']

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const ART = artifactsFrom(a.artifacts)
const artSlug = ART && hasText(ART.slug) ? ART.slug : null
const reconPath = ART && artSlug ? `${ART.dir}/recon-${artSlug}.json` : null
const depscorePath = hasText(a.depscore) && a.depscore.trim().startsWith('/') ? a.depscore.trim() : null
const replayFile = a.replay && a.replay.files && a.replay.files.recon
const replayPath = typeof replayFile === 'string' && replayFile.startsWith('/') ? replayFile : null

const refuse = (why) => ({ ok: false, stage: 'input', deterministicFailure: true, headline: `Detailing refused its input: ${why}`, reason: why, error: why })
if (repos.length !== 1) return dispatchOutcome(refuse(`detailing is scoped to ONE repository; ${repos.length} were supplied`))
if (!hasText(delta.deltaDir)) return dispatchOutcome(refuse('no delta supplied: delta.deltaDir names the views the items come from'))
if (!placed.length) return dispatchOutcome(refuse(`no delta item is placed in ${repos[0]}`))
if (!reconPath) return dispatchOutcome(refuse(`no artifact directory and slug were supplied for ${repos[0]}: the detailing exists only as recon-<slug>.json in the Epic's artifact directory, which the sessions downstream read by path`))
if (!depscorePath) return dispatchOutcome(refuse('no absolute depscore.py path was supplied in `depscore`: depscore.py recon-facts reads the saved detailing'))

phase('Detailing')

/** The relay runner for any program other than depscore.py: relayrun.py beside depscore.py. */
const RELAY_RUNNER = depscorePath.replace(/[^/]+$/, 'relayrun.py')
/** This repository's relay files, under the Epic's artifact directory, numbered so a run's names are deterministic. */
const RELAY_DIR = `${ART.dir}/relay/recon-${artSlug}`
let relaySeq = 0
function relayFile(label) {
  relaySeq += 1
  return `${RELAY_DIR}/${String(relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
}
/** Runs depscore.py recon-facts on a saved detailing through the checked relay; returns { facts } or { error } naming the file. */
async function readFacts(file, label) {
  const out = await relayKit.depscore(settleAgent, {
    label,
    phase: 'Detailing',
    script: depscorePath,
    repo: null,
    tail: `recon-facts --file ${shq(file)} --items ${shq(placed.map((i) => i.id).join(','))}`,
    file: relayFile(label),
  })
  if (out.error) return { error: String(out.error).trim().slice(0, 600), ...(out.noResult ? { dispatchFailed: true } : {}) }
  if (typeof out.ok !== 'boolean') return { error: `depscore.py recon-facts printed no verdict for ${file}` }
  const { relayFile: _relay, ...facts } = out
  return { facts }
}
/** Returns the failure a step stopped on, with the stage and a headline naming the file. */
function stopped(stage, headline, extra) {
  log(headline)
  return { ok: false, stage, headline, reason: headline, error: headline, reconPath: (extra && extra.file) || reconPath, ...(extra || {}) }
}
/** Returns the failure for a detailing that was read but is not usable. */
function unusable(f, file, stage, after) {
  const named = Array.isArray(f.failedItems) ? f.failedItems.map((x) => `${x.id}: ${x.problem}`) : []
  const more = Number(f.problemCount) > named.length ? ` (and ${Number(f.problemCount) - named.length} more)` : ''
  const what = hasText(f.problem) ? f.problem : `${named.join('; ')}${more}`
  return stopped(stage, `The detailing of ${repos[0]} in ${file} is not usable — ${what}${after || ''}`, {
    file,
    failedItems: Array.isArray(f.failedItems) ? f.failedItems : [],
    deterministicFailure: true,
  })
}

/** What the owner does to have a repository whose saved detailing stopped the replay detailed again. */
const REDO = `. To detail ${repos[0]} again, delete ${replayPath || reconPath} and remove the step ${ART.phase} from ${ART.dir}/STEPS.md; the step is not redone behind a saved file`
let facts = null
let resumed = false
if (replayPath) {
  const read = await readFacts(replayPath, 'replay:recon-facts')
  if (read.error) {
    return dispatchOutcome(stopped('detailing-replay', `The saved detailing ${replayPath} of ${repos[0]} could not be read: ${read.error}${REDO}.`, {
      file: replayPath,
      ...(read.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    }))
  }
  if (read.facts.ok !== true) return dispatchOutcome(unusable(read.facts, replayPath, 'detailing-replay', REDO))
  facts = read.facts
  resumed = true
  log(`Detailing replayed from ${replayPath} (${facts.itemCount} item(s), ${facts.bytes} bytes on disk)`)
}

/** Lists the cds bundles packagesDir supplies with depscore.py cds-bundles; returns { bundles } or { error }. */
async function listBundles() {
  if (!uiCheck || !packagesDir) return { bundles: [] }
  const out = await relayKit.depscore(settleAgent, {
    label: 'detail:cds-bundles',
    phase: 'Detailing',
    script: depscorePath,
    repo: null,
    tail: `cds-bundles --packages-dir ${shq(packagesDir)}`,
    file: relayFile('detail:cds-bundles'),
  })
  if (out.error) return { error: String(out.error).trim().slice(0, 600), ...(out.noResult ? { dispatchFailed: true } : {}) }
  if (!Array.isArray(out.bundles)) return { error: 'depscore.py cds-bundles printed no bundle list' }
  return { bundles: out.bundles.filter((b) => b && hasText(b.path) && hasText(b.buildSpec)) }
}
let bundles = []
if (!facts && uiCheck) {
  const listed = await listBundles()
  if (listed.error) {
    return dispatchOutcome(stopped('detailing-bundles', `The cds bundles in ${packagesDir} could not be listed for ${repos[0]}: ${listed.error}.`, {
      ...(listed.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    }))
  }
  bundles = listed.bundles
  log(`Detailing of ${repos[0]}: ${bundles.length} supplied cds bundle(s)${packagesDir ? ` in ${packagesDir}` : ' (no packages directory)'}`)
}
const bundleLines = bundles
  .map((b) => `  - ${b.kind} \`${b.slug}\`${b.shell && b.shell.name ? ` (in shell ${b.shell.name})` : ''}, created ${b.createdAt}\n      bundle: ${b.path}\n      build spec: ${b.buildSpec}${b.buildSpecExists === false ? ' (MISSING on disk)' : ''}\n      design: ${b.design}\n      styles: ${b.styles}`)
  .join('\n')

const itemLines = placed
  .map((i) => `- ${i.id}: ${i.element}${Array.isArray(i.views) && i.views.length ? `\n    delta views: ${i.views.join('; ')}` : ''}`)
  .join('\n')
const prdLine = `PRD ${prdId}${prdTitle ? `: ${prdTitle}` : ''}`.trim()

const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
/** Records the saved detailing with the artifact script's `record` through the checked relay; returns { ok } or { error }. */
async function recordDetailing() {
  const argv = ['python3', ART.script, 'record', reconPath, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])]
  const r = await relayKit.run(settleAgent, { label: 'detail:record', phase: 'Detailing', runner: RELAY_RUNNER, argv, file: relayFile('detail:record'), keys: ['sha256', 'bytes'], tail: 20 })
  if (!r.ok) return { error: r.error, ...(r.noResult ? { dispatchFailed: true } : {}) }
  if (r.exitCode !== 0) return { error: `the record command exited ${r.exitCode}: ${String(r.stderrTail || r.stdoutTail || '').trim().slice(0, 600)}` }
  return { ok: true }
}
const session = facts ? null : await settleAgent(
  `DETAIL an approved architecture delta for ONE repository: for each delta item placed in it, compare what the delta says the element becomes with what the code on the repository's \`main\` holds today, and give the item one status. You are READ-ONLY: read and search, change nothing anywhere, and write no document other than the one result file named at the end of this brief. Two checks, one pass — both go in that file.

═══ CHECK 1 — the detailing ═══

${prdLine}

THE REPOSITORY — this run is scoped to it, and only it:
  ${repos[0]}
Read its code as committed on \`main\` (\`git -C <repo> grep -n <term> main\`, \`git -C <repo> show main:<path>\`). Do not survey other repositories.

THE APPROVED TARGET is ${delta.targetDir || '(the folder above the delta)'}, and the change alone, its delta, is ${delta.deltaDir}. What the delta views say about an element is what it becomes; read the target views where a delta view needs their context.

THE ITEMS PLACED IN THIS REPOSITORY (each one element the delta shows):
${itemLines}

Give every item above exactly one entry, with one status:
- add      — the delta adds the element and the code on \`main\` does not hold it. \`from\` is "absent"; \`to\` is what the delta adds.
- modify   — the code holds the element and the delta changes it. \`from\` is what the code holds; \`to\` is what the delta makes it.
- remove   — the delta removes the element and the code still holds it. \`from\` is what the code holds; \`to\` is "removed".
- done     — the code on \`main\` already holds the element as the delta shows it. \`from\` and \`to\` are both that state.
- planned-elsewhere — an open bead of another Epic (a Story or Task planned and not built) already plans this change. Name it in \`plannedBy\` (the bead id; read beads with \`bd list\`, \`bd show\`, \`bd search\` only).

SOURCE EVIDENCE HANDOFF. ${hasText(a.surveyPath) ? `Use relevant entries from the existing survey ${a.surveyPath}, including its evidenceRefs (path, heading, repo, revision, url; unused fields empty).` : 'No survey path was supplied; use the target/delta and bounded source evidence, identifying any unknowns.'} Resolve the exact main commit in this repository once and retain it with the repository path and file:line in each item's existing evidence strings, linked to that item's id and the originating claim/coverage or TRD requirement IDs when supplied. Keep cited document headings or URL/retrieval revision when relevant. Reuse unchanged evidence sufficient for the status; before another read, name the changed revision, unsupported claim or unanswered question in that item's from/evidence. When main changed, check the cited files/integration dependencies that can affect that item; do not resurvey unrelated source. Legacy citations without a revision require a targeted freshness check, not a fabricated commit. Preserve existing working/stub/absent/unknown distinctions and historical evidence.

Cite evidence for every status in \`evidence\`: a \`file:line\` on \`main\` you read. For \`add\`, cite the file and line where the element attaches (the route table, the stack, the module that will hold it). A \`planned-elsewhere\` item carries its bead id in \`plannedBy\` and, like every status, a \`file:line\`: where the planned change attaches in the code on \`main\`. An item with no citation fails the run.

EXISTING CODE IS EVIDENCE TO INSPECT, NOT AN ASSUMPTION OF CORRECTNESS. In this same read-only pass, follow the relevant entrypoint into the implementation, its consumed/published contracts, configuration and focused tests. Reuse supplied survey citations to narrow the reading; do not resurvey the fleet. In each item's existing \`from\` and \`evidence\`, distinguish behavior supported by the inspected path from incomplete wiring, stubs, absence and unresolved behavior. Name what the tests assert and their limits: reading a mocked test is not a passing test or live-runtime proof. A matching name, import, class, file or mock is not enough for \`done\`. Use \`modify\` for an existing element with an evidenced gap, and \`add\` for a missing element at its cited attachment point. If a material unknown prevents choosing a status, report that uncertainty as an error rather than inventing completeness or replacement work. Preserve verified parts and compatible published contracts; justify any necessary replacement from requirements and concrete evidence. An existing repository is the implementation home unless the approved architecture explicitly establishes a different owner; the presence of a PRD or missing implementation alone does not require a new repository, service or product feature.

Also classify the SURFACE each item lives on, in \`surface\`: ui | service | infra | data | unknown.

${uiCheck ? `═══ EVERY UI ITEM TAKES ONE DESIGN SOURCE ═══

For every item whose \`surface\` is \`ui\`, decide its design source from the delta and the code:

- bundle — a cds bundle listed below packages the artifact (the Page, Shell or View) the item
  builds. The owner supplied that mockup, so the bundle is the target state: its
  \`spec/build-spec.md\` together with its composed \`design/<kind>.html\` and its own \`styles/\`.
- cds — the item changes design (layout, components, styles, visual states, or a new screen)
  and no listed bundle packages it. The implementing agent designs it with the CDS design
  system; there is nothing to cite.
- none — the item changes no design: copy or label text, or data wired into an existing
  element without changing how it looks. It touches no design or stylesheet and is built like
  any other code change.

THE SUPPLIED cds BUNDLES — each packages exactly one artifact; the newest of a kind and slug is
listed, older ones are not supplied:
${bundleLines || '  (none: no bundle is supplied, so no item takes bundle)'}

Match an item to a bundle only when the bundle packages the artifact that item builds: read the
bundle's build spec and design, and the approved target/delta views with their scoped design
references (linked source views included). The PRD (${hasText(prdInput.path) ? prdInput.path : 'no PRD path supplied'})
may name a visual reference that helps identify the artifact; it carries no package paths.
Use only the bundles listed above, at the paths listed. Do not package, copy or regenerate a
bundle, and do not cite a directory that is not listed. When no listed bundle packages the
item, it takes cds or none, decided by whether it changes design.

The loose composed artifacts may help you understand the existing design; they are not
supplied mockups and never make an item a bundle item:
${mocksDir ? `  composed pages and views: ${mocksDir}` : '  composed pages and views: (no directory supplied)'}
${shellsDir ? `  composed shells: ${shellsDir}` : '  composed shells: (no directory supplied)'}

Record one entry per \`ui\` item in \`uiAuthority.uiItems\`: \`item\` (the item id),
\`designSource\` (bundle | cds | none), \`reason\` (one sentence: which bundle packages it, or
what design it changes, or why it changes none); for a bundle or cds item, \`artifact\`:
\`{ kind, slug }\`, the Page, Shell or View the item builds, named as a cds bundle's
\`bundle.json\` names it (kind page | shell | view; for a bundle item, the listed bundle's kind
and slug; for a cds item, the slug a bundle of that artifact would carry: the artifact's name
in lower-case words joined by hyphens, matching an existing composed artifact's slug where one
exists). A mockup can arrive any time before the Task is built: the build looks for a bundle
of this artifact then. For a bundle item only: \`bundle\` (the
bundle directory exactly as listed), \`buildSpec\` (its build spec exactly as listed) and
\`sections\` (the IDs in that build spec's Sections table — S1, S2, … — that the item builds;
an empty list when it builds the whole artifact or the table carries no IDs). The Spec cites
these and every Task that builds the item carries them in its build contract. List every
artifact path you opened in \`uiAuthority.artifactsConsulted\` and the mocks directory in
\`uiAuthority.mocksDir\`.` : `═══ THIS REPOSITORY HOLDS NO UI ═══

Its items take no design source and \`uiAuthority\` stays empty.`}

═══ SEARCH BUDGET ═══

Work item by item and stop searching for each the moment its status is settled. Cover every
item once before you deepen any of them, and when the budget is spent, stop and return your
structured output with what you have.

═══ CHECK 2 — upstream dependency changes ═══

Upstream dependencies the work relies on:
${dependencies.length ? dependencies.map((d, i) => `${i + 1}. ${d}`).join('\n') : '(none declared in args — discover them from the repository\'s manifests, lockfiles and imports)'}

Determine whether any upstream contract, shared schema, event, library version, or interface the delta assumes has changed in a way that invalidates it. Check the dependencies THIS repository consumes, as its manifests, lockfiles and imports on \`main\` show them. Record under \`dependencyChanges\`:
- current: true if no invalidating upstream change is found, false otherwise.
- changeFindings: each invalidating change (dependency, change, invalidates).
- evidence: how you verified the dependency state (under 60 words).

═══ THE RESULT IS A FILE, NOT YOUR REPLY ═══

1. Write your whole detailing, as ONE JSON object, to ${reconPath} with the Write tool, replacing the file if it exists (Read it first if the Write tool asks you to). Write no other file. Its keys:
   - \`items\`: one object per item above: \`id\`, \`element\`, \`status\` (${STATUSES.join(' | ')}), \`from\`, \`to\`, \`evidence\` (a list of strings, each \`file:line\` you read with what it shows), \`plannedBy\` (the bead id, for planned-elsewhere only), \`surface\` (ui | service | infra | data | unknown).
   - \`evidenceSummary\`: a string.
   - \`uiAuthority\`: \`uiItems\` (each \`{ item, designSource, reason, artifact?, bundle?, buildSpec?, sections? }\`), \`mocksDir\`, \`artifactsConsulted\`, as described above; empty values when the repository holds no UI.
   - \`dependencyChanges\`: \`current\` (true or false), \`changeFindings\` (each \`{ dependency, change, invalidates }\`), \`evidence\`.
2. Return ONLY \`saved\` (true when the file is written), \`itemCount\` (the number of entries in \`items\`) and, when anything failed, \`error\` (what failed). Do NOT return the detailing itself: the workflow records and checks the file on disk, and every session after you reads it by its path.`,
  {
    label: 'detail:delta-and-dependencies',
    phase: 'Detailing',
    effort: 'medium',
    agentType: 'prd-reality-reconciler',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['saved', 'itemCount'],
      properties: { saved: { type: 'boolean' }, itemCount: { type: 'integer' }, error: { type: 'string' } },
    },
  }
)

if (!facts) {
  if (!session) {
    const deaths = dispatchDeaths('Detailing')
    return dispatchOutcome(stopped('detailing', `The detailing session for ${repos[0]} returned nothing, so the repository was not detailed (${deaths.map((f) => f.note).join('; ') || 'no dispatch was recorded'}).`, {
      dispatchFailed: true,
      dispatchFailures: deaths,
    }))
  }
  if (session.saved !== true) {
    return dispatchOutcome(stopped('detailing-save', `The detailing session for ${repos[0]} did not save ${reconPath}: ${hasText(session.error) ? session.error.trim().slice(0, 600) : 'it reported saved=false and gave no reason'}.`))
  }
  const recorded = await recordDetailing()
  if (recorded.error) {
    return dispatchOutcome(stopped('detailing-save', `The detailing of ${repos[0]} was saved to ${reconPath} but not recorded: ${recorded.error}.`, {
      ...(recorded.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    }))
  }
  const read = await readFacts(reconPath, 'detail:recon-facts')
  if (read.error) {
    return dispatchOutcome(stopped('detailing-read', `The detailing of ${repos[0]} was saved to ${reconPath} but could not be read back: ${read.error}.`, {
      ...(read.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    }))
  }
  if (read.facts.ok !== true) return dispatchOutcome(unusable(read.facts, reconPath, 'detailing'))
  facts = read.facts
  if (Number(session.itemCount) !== Number(facts.itemCount)) log(`Detailing of ${repos[0]}: the session reported ${session.itemCount} item(s) and ${reconPath} holds ${facts.itemCount}; the file governs.`)
}

const ids = (v) => (Array.isArray(v) ? v.filter(hasText).map((x) => x.trim()) : [])
const counts = Object.fromEntries(STATUSES.map((s) => [s, Number((facts.counts || {})[s]) || 0]))
const work = ids(facts.work)
const idle = (Array.isArray(facts.idle) ? facts.idle : [])
  .filter((x) => x && hasText(x.id))
  .map((x) => ({ id: x.id.trim(), status: hasText(x.status) ? x.status.trim() : '', plannedBy: hasText(x.plannedBy) ? x.plannedBy.trim() : null }))
const uiWork = (Array.isArray(facts.uiWork) ? facts.uiWork : [])
  .filter((u) => u && hasText(u.id))
  .map((u) => ({
    id: u.id.trim(),
    designSource: hasText(u.designSource) ? u.designSource.trim() : null,
    artifact: u.artifact && hasText(u.artifact.kind) && hasText(u.artifact.slug) ? { kind: u.artifact.kind.trim(), slug: u.artifact.slug.trim() } : null,
    bundle: hasText(u.bundle) ? u.bundle.trim() : null,
    buildSpec: hasText(u.buildSpec) ? u.buildSpec.trim() : null,
    sections: ids(u.sections),
  }))
const detailingFile = resumed ? replayPath : reconPath

log(`Detailing of ${repos[0]} (${detailingFile}): ${facts.itemCount} item(s) — ${STATUSES.map((s) => `${counts[s]} ${s}`).join(', ')}.`)

return dispatchOutcome({
  ok: true,
  ...(resumed ? { resumed: true } : {}),
  reconPath: detailingFile,
  itemCount: Number(facts.itemCount) || 0,
  counts,
  work,
  idle,
  uiWork,
  bundles: [...new Set(uiWork.map((u) => u.bundle).filter(Boolean))],
  mocksDir: hasText(facts.mocksDir) ? facts.mocksDir.trim() : mocksDir || null,
  dependenciesCurrent: typeof facts.dependenciesCurrent === 'boolean' ? facts.dependenciesCurrent : null,
  dependencyFindings: Number(facts.dependencyFindings) || 0,
  ledger: {
    phase: 'prd-reconciliation',
    beadId: null,
    subject: prdId || prdTitle || null,
    chosen: ['prd-reality-reconciler'],
    mode: 'combined',
    uiCheck,
    resumed,
    reconPath: detailingFile,
    itemCount: Number(facts.itemCount) || 0,
    ...counts,
    ok: true,
  },
})
