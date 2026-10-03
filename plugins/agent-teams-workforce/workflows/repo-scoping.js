export const meta = {
  name: 'repo-scoping',
  description:
    'Leaf mini — rules the repository span of a PRD from its approved architecture delta. One polyrepo-steward session places each delta item (one element the delta shows, as depscore.py arch-delta lists it) in the repository whose code changes for it, or records that the element has no code in this project, and creates each new repository the approved target names, from the name, template and reason the target gives. The span is the distinct repositories the placements name. The run fails when an item is placed twice or not at all, or when no placement names a repository.',
  phases: [
    { title: 'Place and provision', detail: 'the polyrepo-steward places each delta item in a repository and creates the new repositories the approved target names' },
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

async function run(prompt, opts) {
  if (dispatchInterruption) return null
  let message = 'returned nothing'
  try {
    const out = await fableAgent(prompt, opts)
    if (out) return out
  } catch (err) {
    captureDispatchInterruption(err, (opts && (opts.label || opts.agentType)) || 'agent')
    message = String((err && err.message) || err).slice(0, 300)
  }
  dispatchFailures.push({ label: opts.label, agentType: opts.agentType || null, phase: opts.phase, message })
  log(`${opts.label}: no structured result — ${message}`)
  return null
}

// args: { prd: { id?, title?, path? }, delta: { subject, targetDir, deltaDir, items: [{ id, element, views }] },
//   epic?: { key?, title? }, artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? },
//   pluginRoot? | relay?: { runner, dir? } (the checked relay: relayrun.py, given directly or as
//     <pluginRoot>/scripts/portfolio/relayrun.py; the script then checks and records repo-scoping.json
//     itself; without it the steward session records it, as before) }
// returns: { ok, reason?, repos, placements, noCode, createdRepos, creationFailures, spanRationale, surveySummary, persistErrors?, ledger }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const hasText = (v) => typeof v === 'string' && v.trim().length > 0

const ART = a.artifacts && typeof a.artifacts === 'object' && typeof a.artifacts.dir === 'string' && a.artifacts.dir ? a.artifacts : null
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const relayArg = a.relay && typeof a.relay === 'object' ? a.relay : {}
const pluginRootArg = hasText(a.pluginRoot) && a.pluginRoot.trim().startsWith('/') ? a.pluginRoot.trim().replace(/\/+$/, '') : ''
const RELAY_RUNNER = hasText(relayArg.runner) && relayArg.runner.trim().startsWith('/')
  ? relayArg.runner.trim()
  : pluginRootArg ? `${pluginRootArg}/scripts/portfolio/relayrun.py` : ''
function persistBrief(name, what) {
  if (!ART) return ''
  if (RELAY_RUNNER) {
    return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\nWrite ${what} to ${ART.dir}/${name} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this, and run no command to record it: the workflow checks and records it after you return.\nIf the write fails, say so in your result and still return your result.`
  }
  const file = `${ART.dir}/${name}`
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${ART.script} record ${file} --epic ${ART.epicId} --phase ${ART.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. No other session will write it for you.
1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this.
2. Then run exactly this command:\n   ${record}\n   It hashes the file as it is on disk and prints the recorded metadata as JSON.
If a step fails, say so in your result and still return your result. Never improvise another way to write, move or record the file.`
}

const prdInput = a.prd && typeof a.prd === 'object' ? a.prd : {}
const prdId = prdInput.id || ''
const prdTitle = prdInput.title || ''
const epic = a.epic || {}
const delta = a.delta && typeof a.delta === 'object' ? a.delta : {}
const items = (Array.isArray(delta.items) ? delta.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))


const fail = (reason, extra) => ({
  ok: false,
  reason,
  repos: [],
  placements: [],
  noCode: [],
  createdRepos: [],
  creationFailures: [],
  ...(extra || {}),
})
const died = (phaseName) => {
  const deaths = dispatchFailures.filter((f) => f.phase === phaseName)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}

if (!hasText(delta.deltaDir) || !hasText(delta.targetDir)) {
  return dispatchOutcome({ ...fail('no approved target and delta were supplied: the span is the repositories the delta changes'), stage: 'input', deterministicFailure: true })
}
if (!items.length) {
  return dispatchOutcome({ ...fail(`the delta at ${delta.deltaDir} lists no item: depscore.py arch-delta found no element in its views' \`shows\``), stage: 'input', deterministicFailure: true })
}

phase('Place and provision')

const itemLines = items
  .map((i) => `- ${i.id}: ${i.element}${Array.isArray(i.views) && i.views.length ? `\n    shown in: ${i.views.join('; ')}` : ''}`)
  .join('\n')

const placed = await run(
  `Place each item of an approved architecture delta in the repository whose code changes for it, and CREATE each new repository the approved target names. You own the project's repositories and your records of them; repository facts come from your records and the live repositories, as the polyrepo-repo skill describes.

THE APPROVED TARGET for ${prdTitle || prdId || 'this PRD'} is ${delta.targetDir}; the change alone, its delta, is ${delta.deltaDir}. Read the delta views, and the target views where a delta view leaves an element's home unstated. Each item below is one element the delta shows:
${itemLines}

DO THIS, IN ORDER:

1. Take the inventory LIVE, now, with your polyrepo tool: \`inventory --json\` (the polyrepo-repo skill names the tool and its path).
2. For each item, name the repository whose code changes for it: the repository that owns the element, as your records and the code on its \`main\` show. An element that has no code in this project (an external system, or a managed service whose configuration lives in the code of another item's repository) goes in \`noCode\` with the reason; an element whose configuration lives in a repository's code is placed in that repository.
3. Where the approved target names a NEW repository for an element, look first in the live inventory for a repository that already serves it, including one an earlier run of this same PRD created, and place the item there rather than creating a second. Otherwise create it with the polyrepo tool's \`create\` command, locally and on GitHub, as the polyrepo-repo skill describes, with the name, the template and the reason the target gives; where the target names no template, the template whose kind matches the element as the target describes it. If a creation fails, fix what the error names and try it once more; if it still fails, report it in creationFailures with the error text. Create no repository the target does not name.

Return:

- placements — one entry per repository that holds work, including each repository you created. Each: repoPath (the repository's absolute local path, exactly as your polyrepo tool reports it), repoName, itemIds (the ids of the items placed there), frontend (true when the repository serves a user interface, per your records), rationale, and created (true when you created it in this session).
- noCode — one entry per item with no code in this project: itemId and reason.
- createdRepos — one entry per repository you created in this session: name, repoPath, template, purpose, itemIds. Empty when you created none.
- creationFailures — one entry per repository the target names that you could not create: proposedName, itemIds, error. Empty when every creation succeeded.
- surveySummary — how many repositories the inventory holds and how you took it.
- spanRationale — why these are the repositories the delta changes, in a few sentences.

Every item appears exactly once: in one placement or in noCode. Change nothing in any repository beyond creating the ones the target names.${persistBrief('repo-scoping.json', 'your complete result (placements, noCode, createdRepos, creationFailures, surveySummary, spanRationale — exactly as you return them) as ONE JSON object')}`,
  {
    label: 'scope:place-delta',
    phase: 'Place and provision',
    effort: 'high',
    agentType: 'agent-teams-workforce:polyrepo-steward',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['placements', 'noCode', 'createdRepos', 'creationFailures', 'spanRationale'],
      properties: {
        placements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['repoPath', 'repoName', 'itemIds', 'frontend', 'rationale'],
            properties: {
              repoPath: { type: 'string' },
              repoName: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
              frontend: { type: 'boolean' },
              rationale: { type: 'string' },
              created: { type: 'boolean' },
            },
          },
        },
        noCode: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['itemId', 'reason'],
            properties: { itemId: { type: 'string' }, reason: { type: 'string' } },
          },
        },
        createdRepos: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['name', 'repoPath', 'purpose'],
            properties: {
              name: { type: 'string' },
              repoPath: { type: 'string' },
              template: { type: 'string' },
              purpose: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
            },
          },
        },
        creationFailures: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['proposedName', 'error'],
            properties: {
              proposedName: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
              error: { type: 'string' },
            },
          },
        },
        surveySummary: { type: 'string' },
        spanRationale: { type: 'string' },
      },
    },
  }
)

if (!placed) {
  return dispatchOutcome(fail('the polyrepo-steward returned no placement, so the repositories the delta changes were not established.', died('Place and provision')))
}

// repo-scoping.json must hold exactly the result the steward returned: the script checks it
// (writing it when it differs) and records it only then. A save or record that fails is named in
// persistErrors and the ruling goes on, as it did when the steward saved and recorded it.
const persistErrors = []
if (ART && RELAY_RUNNER) {
  const relayDir = hasText(relayArg.dir) && relayArg.dir.trim().startsWith('/') ? relayArg.dir.trim().replace(/\/+$/, '') : `${ART.dir}/relay/repo-scoping`
  let relaySeq = 0
  const relayFile = (label) => {
    relaySeq += 1
    return `${relayDir}/${String(relaySeq).padStart(3, '0')}-${label}.json`
  }
  const file = `${ART.dir}/repo-scoping.json`
  const saved = await relayKit.ensureJson(run, { label: 'save:repo-scoping', phase: 'Place and provision', runner: RELAY_RUNNER, file, value: placed })
  if (!saved.ok) {
    persistErrors.push(`repo-scoping.json does not hold the steward's result, so it was not recorded: ${saved.error || 'not saved'}`)
  } else {
    const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
    const recorded = await relayKit.run(run, {
      label: 'record:repo-scoping',
      phase: 'Place and provision',
      runner: RELAY_RUNNER,
      argv: ['python3', ART.script, 'record', file, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])],
      file: relayFile('record-repo-scoping'),
      keys: ['sha256', 'bytes'],
      tail: 20,
    })
    if (!recorded.ok || recorded.exitCode !== 0) persistErrors.push(`repo-scoping.json was not recorded: ${!recorded.ok ? recorded.error : `the record command exited ${recorded.exitCode}: ${String(recorded.stderrTail || recorded.stdoutTail || '').trim().slice(0, 600)}`}`)
  }
  for (const e of persistErrors) log(e)
} else if (ART) {
  log('repo-scoping: no relay runner (pluginRoot or relay.runner) was passed, so the steward session recorded repo-scoping.json itself')
}

const known = new Set(items.map((i) => i.id))
const seen = new Map()
const note = (id, where) => seen.set(id, [...(seen.get(id) || []), where])
const placements = []
const repos = []
for (const p of placed.placements) {
  if (!p || !hasText(p.repoPath)) continue
  const repoPath = p.repoPath.trim()
  const itemIds = (Array.isArray(p.itemIds) ? p.itemIds : []).filter((x) => hasText(x)).map((x) => x.trim())
  if (!itemIds.length) continue
  if (!repos.includes(repoPath)) repos.push(repoPath)
  for (const id of itemIds) note(id, repoPath)
  placements.push({
    repoPath,
    repoName: hasText(p.repoName) ? p.repoName : repoPath,
    itemIds,
    frontend: p.frontend === true,
    rationale: p.rationale || '',
    created: p.created === true,
  })
}
const noCode = (Array.isArray(placed.noCode) ? placed.noCode : []).filter((n) => n && hasText(n.itemId)).map((n) => ({ itemId: n.itemId.trim(), reason: n.reason || '' }))
for (const n of noCode) note(n.itemId, 'noCode')
const createdRepos = placed.createdRepos.filter((c) => c && hasText(c.name))
const creationFailures = placed.creationFailures.filter((f) => f && hasText(f.proposedName))

const unknown = [...seen.keys()].filter((id) => !known.has(id))
const twice = [...seen.entries()].filter(([id, where]) => known.has(id) && where.length > 1).map(([id, where]) => `${id} (${where.join(', ')})`)
const unplaced = items.filter((i) => !seen.has(i.id)).map((i) => `${i.id} ${i.element}`)
const faults = [
  unplaced.length ? `not placed: ${unplaced.join('; ')}` : '',
  twice.length ? `placed more than once: ${twice.join('; ')}` : '',
  unknown.length ? `not items of the delta: ${unknown.join(', ')}` : '',
  creationFailures.length ? `not created: ${creationFailures.map((f) => `${f.proposedName} (${f.error})`).join('; ')}` : '',
].filter(Boolean)
if (faults.length) {
  return dispatchOutcome(fail(`the placement of the delta items is incomplete — ${faults.join('; ')}`, { placements, noCode, createdRepos, creationFailures, ...(persistErrors.length ? { persistErrors } : {}) }))
}
if (!repos.length) {
  return dispatchOutcome(fail('the polyrepo-steward placed the delta in no repository: every item was recorded as having no code in this project.', { noCode, createdRepos, creationFailures, ...(persistErrors.length ? { persistErrors } : {}) }))
}

log(
  `Span placed: ${repos.length} repositor(ies) — ${repos.join(', ')}` +
    `${createdRepos.length ? `; ${createdRepos.length} created (${createdRepos.map((c) => c.name).join(', ')})` : ''}` +
    `${noCode.length ? `; ${noCode.length} item(s) with no code here` : ''}.`
)

return dispatchOutcome({
  ok: true,
  repos,
  placements,
  noCode,
  createdRepos,
  creationFailures,
  spanRationale: placed.spanRationale || null,
  surveySummary: placed.surveySummary || null,
  ...(persistErrors.length ? { persistErrors } : {}),
  ledger: {
    phase: 'repo-scoping',
    beadId: (epic && epic.key) || null,
    subject: prdId || prdTitle || null,
    chosen: ['polyrepo-steward'],
    mode: 'fixed',
    repoCount: repos.length,
    itemCount: items.length,
    createdRepoCount: createdRepos.length,
    ok: true,
  },
})
