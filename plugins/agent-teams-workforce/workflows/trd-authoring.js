export const meta = {
  name: 'trd-authoring',
  description:
    'Leaf mini — authors a Technical Requirements Document (TRD) from a PRD plus the approved target and delta of its architecture. A filing-clerk session names the TRD file when the caller gives no path, then one trd-author session reads the owner\'s constraints in section 2, the target and delta views, and the effective views of the elements the delta adds or changes, and writes the TRD in one pass: PRD business requirements that need technical elaboration plus the obligations the architecture imposes on the elements the delta adds or changes, each citing its PRD requirement or the view path it comes from and naming the element it applies to. Refuses a run with no target and delta. A technical rule reaches the TRD from the architecture, never from the PRD.',
  phases: [
    { title: 'Author TRD', detail: 'author the TRD from the PRD and the target and delta views, one pass' },
  ],
}
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
// - every result is printed as a sealed envelope, the facts plus relay: { file, sha256, bytes,
//   exit, checksum }, where checksum is the SHA-256 of the canonical JSON of { exit, view }.
//   The script recomputes it over the copy it receives and accepts only an exact copy. A
//   result saved in a relay file is read again (re-running nothing) when the copy is altered.
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
  /** A runner's return: the printed object, whose relay block's shape the runtime validates. */
  const SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['exitCode', 'output'],
    properties: {
      exitCode: { type: 'integer' },
      output: {
        type: 'object',
        properties: {
          relay: {
            type: 'object',
            additionalProperties: false,
            required: ['file', 'sha256', 'bytes', 'exit', 'checksum'],
            properties: {
              file: { type: ['string', 'null'] },
              sha256: { type: ['string', 'null'] },
              bytes: { type: ['integer', 'null'] },
              exit: { type: 'integer' },
              checksum: { type: 'string' },
            },
          },
        },
      },
    },
  }
  const HEX = /^[0-9a-f]{64}$/
  /** Why a runner's copy is not the exact envelope the program printed (for relay file `file`), or ''. */
  function problem(output, file) {
    const r = output && output.relay
    if (!r || typeof r !== 'object') return 'the result came back without its relay block'
    if (!HEX.test(String(r.checksum)) || !Number.isInteger(r.exit)) return 'the relay block is malformed'
    if (r.file !== file && !(r.file === null && r.exit === 3)) return `the relay block names ${JSON.stringify(r.file)}, not ${JSON.stringify(file)}`
    const { relay: _relay, ...view } = output
    let got = ''
    try {
      got = sha256Json({ exit: r.exit, view })
    } catch (err) {
      return `the copy cannot be hashed: ${String((err && err.message) || err)}`
    }
    return got === r.checksum ? '' : `the copy hashes to ${got.slice(0, 12)}..., not to the ${r.checksum.slice(0, 12)}... the program printed`
  }
  const prompt = (command) => `Run exactly this one shell command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000, and change nothing else. Type the command exactly as written below, character for character: the program checks it against the checksum it carries and refuses any difference.

${command}

It prints one JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object as \`output\`, copied exactly: every key and value as printed, every list complete and in order, every string character for character. Never summarize, shorten, count, reorder, rename or omit anything. The workflow checks your copy against the SHA-256 the object carries and rejects any difference. If stdout is not one JSON object, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not run any other command.`
  /**
   * Runs `command` in a runner session until an exact copy of its envelope comes back, at most
   * `attempts` times. An altered copy is read again with `reread` when there is one (re-running
   * nothing), else the command is run again (only read-only and idempotent commands have no
   * reread). A command line typed wrong (exit 3) and a relay file the command never wrote (exit 4)
   * are run again. Returns { ok: true, exit, view } or { ok: false, error, noResult? }.
   */
  async function exec(dispatch, { label, phase, command, reread = null, file = null, attempts = 3 }) {
    let line = command
    let why = ''
    for (let attempt = 1; attempt <= attempts; attempt++) {
      const out = await dispatch(prompt(line), { label: attempt === 1 ? label : `${label}:again-${attempt - 1}`, phase, model: 'haiku', effort: 'low', schema: SCHEMA })
      if (!out) return { ok: false, noResult: true, error: `the ${label} runner returned no result` }
      why = problem(out.output, file)
      if (why) {
        log(`${label}: ${why}; ${reread ? 'reading the saved result again' : 'running it again'}`)
        if (reread) line = reread
        continue
      }
      const exit = out.output.relay.exit
      const { relay: _relay, ...view } = out.output
      if (exit === 3 || exit === 4) {
        why = String(view.error || (exit === 3 ? 'the command line was typed differently' : 'no saved result'))
        log(`${label}: ${why}; running the command again`)
        line = command
        continue
      }
      return { ok: true, exit, view }
    }
    return { ok: false, error: `${label} did not reach the workflow as printed in ${attempts} attempt(s): ${why}${file ? ` (its full result is in ${file})` : ''}; nothing was taken from an altered copy` }
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
    const r = await exec(dispatch, { label, phase, command: pythonLine(script, rest), reread: pythonLine(script, ['relay-read', '--relay', file]), file })
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
    const r = await exec(dispatch, { label, phase, command: pythonLine(runner, rest), reread: pythonLine(runner, ['read', '--relay', file]), file })
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
    'def emit(view, ex=0):',
    '    print(c(dict(view, relay={"file": None, "sha256": None, "bytes": None, "exit": ex, "checksum": h({"exit": ex, "view": view})})))',
    '    sys.exit(ex)',
    'if h([boot, code] + args) != want:',
    '    emit({"argvMismatch": True, "error": "the command line differs from the one the workflow script built"}, 3)',
    'exec(code, {"ARGS": args, "emit": emit, "__name__": "__relay__"})',
  ].join('\n')
  /**
   * Runs the Python `code` (which reads its arguments from ARGS and calls emit(obj) once with a
   * JSON object holding no floats) under a bootstrap that checks the command line, payload included,
   * and seals what it emits. Read-only payloads only: an altered copy runs it again. Returns
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
  return { canonicalJson, sha256Ascii, sha256Json, quote, shellWords, exec, depscore, run, checkFile, ensureJson, inline, exceptionOf, SCHEMA }
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
    const out = await agent(prompt, o)
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
//   prd: { id?, title?, path?, content?, acceptanceCriteria?: any[] },
//   archPath,
//   trdPath?, repoPath?, feedback?,
//   architecture: { subject, targetDir, deltaDir, items?: [{ id, element, views }], decisionPath? } (the approved target and its delta),
//   artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? },
//   pluginRoot? | relay?: { runner, dir? } (the checked relay: relayrun.py, given directly or as
//     <pluginRoot>/scripts/portfolio/relayrun.py; the script then records trd.md and sets the bead's
//     artifact metadata itself; without it the author session does both, as before)
// }
// returns { ok, trdPath, filingPath, trd, decisionIds, persistErrors? } or { ok: false, stage, reason, ... }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const relayArg = a.relay && typeof a.relay === 'object' ? a.relay : {}
const pluginRootArg = typeof a.pluginRoot === 'string' && a.pluginRoot.trim().startsWith('/') ? a.pluginRoot.trim().replace(/\/+$/, '') : ''
const RELAY_RUNNER = typeof relayArg.runner === 'string' && relayArg.runner.trim().startsWith('/')
  ? relayArg.runner.trim()
  : pluginRootArg ? `${pluginRootArg}/scripts/portfolio/relayrun.py` : ''
function persistBrief(art, name, what, opts) {
  if (!art) return ''
  if (RELAY_RUNNER) {
    return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\nWrite ${what} to ${art.dir}/${name} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this, and run no command to record it: the workflow records it, and sets the bead's metadata, after you return.\nIf the write fails, say so in your result and still return your result.`
  }
  const o = opts || {}
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command:\n   ${record}\n   It prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  if (o.beadKey && typeof art.relDir === 'string' && art.relDir && typeof art.beadId === 'string' && art.beadId) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${art.beadId} --set-metadata artifact_${o.beadKey}_path=${art.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result.`
}
const ART = artifactsFrom(a.artifacts)
const prd = a.prd || {}
const repo = a.repoPath || '(repo path not provided)'
let trdPath = a.trdPath || null


const prdContent = typeof prd.content === 'string' && prd.content.trim().length > 0
const prdPath = typeof prd.path === 'string' && prd.path.startsWith('/') ? prd.path : ''
if (!prdContent && !prdPath) {
  const why = 'no PRD supplied — prd.content is empty and prd.path is not an absolute path. Pass the PRD content or its path.'
  return dispatchOutcome({ ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why })
}
const archPath = typeof a.archPath === 'string' ? a.archPath.trim() : ''
if (!archPath.startsWith('/')) {
  const why = 'no architecture supplied — archPath is not an absolute path. Set ATW_ARCH_PATH for the run, or pass archPath.'
  return dispatchOutcome({ ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why })
}

const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const target = a.architecture && typeof a.architecture === 'object' ? a.architecture : null
if (!target || !hasText(target.targetDir) || !hasText(target.deltaDir)) {
  const why = 'no approved target and delta supplied — architecture.targetDir and architecture.deltaDir name the views the TRD states obligations on.'
  return dispatchOutcome({ ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why })
}

const died = (...phases) => {
  const deaths = dispatchDeaths(...phases)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}

const archText = `THE ARCHITECTURE is at ${archPath}. It is not inside the product repository ${repo}. Its \`arc42/\` folder is the effective version (the approved architecture), its \`target/\` folder holds the targets in progress, and the architecture documentation model in its \`reference/\` folder says what each version and section holds.
- \`arc42/02-architecture-constraints\` holds the owner's constraints. Read its README.md in full.
- \`arc42/04-solution-strategy\` holds the enterprise-level strategy. Read its README.md.
- Every other arc42 section is the design so far, as views. Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog.
- THIS PRD'S APPROVED TARGET is ${target.targetDir}, and the change alone, its delta, is ${target.deltaDir}. Read every delta view in full, and the target views that show the elements the delta adds or changes. For each such element, find its effective views by searching the catalog frontmatter (\`subject:\` and the \`shows:\` lists) for the element's name, at every scope, and read them. The views in \`arc42/08-crosscutting-concepts\` describe patterns used across services; read every one whose concept applies to an element the delta adds or changes.
- When a relevant architecture view selects a scoped UI design/mock or hand-off package, follow that reference and preserve its identity and scope in the applicable TRD obligation with the architecture citation. Do not substitute a newer unrelated mock or promote other advisory mocks to requirements. Report missing or conflicting references in your summary; do not invent package paths. Consumed by: spec-authoring — carries the applicable design obligation into the implementation contract.
- Other open targets in \`target/\` that show the same elements are designs in progress; read them, so this TRD does not contradict them.`
const prdText = prdContent
  ? prd.content
  : `PRD ${prd.id || ''}${prd.title ? `: ${prd.title}` : ''}\n\nThe PRD is the document at ${prdPath}. Read that ONE file in full before you author anything; every requirement in it is in scope.`

const deltaItems = (Array.isArray(target.items) ? target.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))
const deltaBlock = `\nTHE ELEMENTS THE DELTA SHOWS (the delta items; name each requirement's \`appliesTo\` as the item's element is named here):\n${deltaItems.length ? deltaItems.map((i) => `- ${i.id}: ${i.element}`).join('\n') : '(read them from the delta views\' \`shows\` frontmatter)'}\n${hasText(target.decisionPath) ? `The architecture decision that approved the target is the document at ${target.decisionPath}.\n` : ''}`
const feedback = typeof a.feedback === 'string' && a.feedback.trim() ? `[Gate feedback from the previous run of this phase] ${a.feedback.trim()}` : ''

phase('Author TRD')

if (!trdPath) {
  const home = await settleAgent(
    `Decide the ONE correct absolute file path for the Technical Requirements Document described below, using this project's documentation conventions and knowledge base. Do not author the TRD and do not create the file — return only where it belongs.

If a TRD for this subject already exists, return ITS path so the document is updated in place rather than duplicated.

Subject: ${prd.id || prd.title || 'TRD'}
PRD title: ${prd.title || '(untitled)'}
Repository the run is working in: ${repo}`,
    {
      label: 'trd:filing-home',
      phase: 'Author TRD',
      effort: 'low',
      agentType: 'filing-clerk',
      schema: {
        type: 'object', additionalProperties: false, required: ['ok'],
        properties: { ok: { type: 'boolean' }, path: { type: 'string' }, existing: { type: 'boolean' }, error: { type: 'string' } },
      },
    }
  )
  if (home && home.ok === true && typeof home.path === 'string' && home.path.startsWith('/')) {
    trdPath = home.path
    log(`TRD home ruled by the filing clerk: ${trdPath}`)
  } else {
    trdPath = '(no path supplied — ask the filing clerk before writing)'
  }
}

const authorPath = ART ? `${ART.dir}/trd.md` : trdPath
const filingPath = typeof trdPath === 'string' && trdPath.startsWith('/') ? trdPath : null
const writeBrief = ART
  ? `WRITE THE TRD AS MARKDOWN BEFORE YOU RETURN, as the steps at the end of this brief say. \`trdPath\` in your result must be ${authorPath}.${filingPath ? ` Do NOT write it to ${filingPath}.` : ''}\n`
  : `WRITE THE TRD TO THIS FILE BEFORE YOU RETURN: ${trdPath}
Create any missing parent directories. \`trdPath\` in your result must be the path you actually wrote.
`
const MAX_REQUIREMENTS = 40
log(`Authoring TRD at ${authorPath}`)

const trd = await settleAgent(
  `Author the Technical Requirements Document (TRD). Write the TRD; do not write production code. Work within the repository at: ${repo}

WHAT THIS DOCUMENT IS FOR. The TRD is the single point at which the obligations the architecture imposes enter the build chain. The Specs, Stories and Tasks are built from it; an obligation that does not reach the TRD is built by nobody. It is NOT the full HOW — the detailed HOW lives in the Specs and Tasks. Make sure the right obligations are PRESENT AND SOURCED.

THE TRD'S REQUIREMENTS COME FROM TWO SOURCES.

1. PRD BUSINESS REQUIREMENTS THAT NEED TECHNICAL ELABORATION. One PRD requirement may need several technical requirements, and several may be answered by one. A PRD line that states a rule about how the system is built is not a business requirement and is not a source: a technical rule reaches the TRD only from the architecture, under the condition below.

2. THE OBLIGATIONS THE ARCHITECTURE IMPOSES, WHICH NO PRD WOULD EVER STATE. These have NO PRD parent. System uptime, latency, maintainability, security, failover, disaster recovery, specific infrastructure and CDK instructions, and observability: where the architecture describes how a service is observed, and this PRD results in that kind of service being built, the TRD says what that service must provide for it. The same class covers throughput and latency budgets, data modelling, API contracts, encryption, retention and auth protocols, and monitoring and alerting. The architecture views describe which of these this system has.

Read the architecture as the block below says, and for every view you read ask what it demands of anything this PRD builds.

SOURCE EVIDENCE HANDOFF. ${typeof a.surveyPath === 'string' && a.surveyPath.trim() ? `The existing architecture survey is ${a.surveyPath}. Read its relevant coverage/claim entries and evidenceRefs; do not paste or repeat the whole survey.` : 'No survey path was supplied; treat implementation evidence not otherwise provided as unknown and use only targeted reads.'} Each evidenceRef carries path, heading, repo, revision and url (unused fields are empty). Preserve the exact relevant repository path, commit revision, file:line or document heading, and claim/coverage ID alongside the TRD requirement ID in the existing summary/context and requirement prose. Implementation evidence describes what exists; PRD and architecture references remain the authority for what is required. Before a new source read, state in that context which obligation is already established and the changed revision, missing evidence or unanswered question that requires the read. Compare the named repository's main revision with the recorded revision; unchanged, sufficient evidence can be reused. A changed revision or legacy citation without revision requires a targeted check of the affected source; preserve prior evidence as historical rather than inventing a revision. Test code read is not test execution.

EXISTING IMPLEMENTATION CONTEXT. Use the supplied architecture survey and target/delta citations to identify the existing owning repository and integration points. Within this authoring pass, inspect relevant available entrypoints, contracts and focused tests when needed to distinguish a remaining obligation from an already implemented one; do not perform a new fleet survey. Code is neither presumed correct nor discarded because its provenance is uncertain. State material gaps or unknowns, with file:line evidence, in the TRD's existing summary/context; reading tests does not prove they pass or exercise live dependencies. Requirements remain the source of the desired behavior. Preserve supported behavior and compatible published contracts, and describe the incremental obligation on the named element. A missing implementation is implementation work, not a new product feature; a PRD does not itself authorize a new repository or service. Do not silently redesign an approved target: report an evidenced contradiction for resolution. The later per-repository detailing supplies the precise from/to comparison for Specs and Tasks.

AN OBLIGATION BINDS ONLY WHAT THE DELTA ADDS OR CHANGES. An obligation about a kind of thing (an S3 bucket, a Lambda function, a DynamoDB table, a VPC endpoint) is stated only where the delta adds or changes that thing, and the requirement names it: "the delta adds bucket <name>, so <name> is versioned and SSE-S3 encrypted [<view path>]". An element the delta does not touch carries no obligation here, and an obligation is never a reason to add the thing it governs: things are added by the target. Set \`appliesTo\` on every requirement to the element it governs, named as the delta names it.

EFFECTIVE FILES ARE REVIEWED. \`lifecycle_state: effective\` means a file was reviewed and approved: it is the design so far, followed as the established pattern, not a fixed rule. Cite it. The TRD states obligations on the design and does not redesign it: where a requirement would depart from an effective view, name the view and the departure in your \`summary\` for the architecture step. This PRD's target and delta views read \`in-review\` because they are integrated after review; the architecture step approved them, and they are the design you state obligations on. Any other file in a state other than \`effective\` is open to review: before a requirement rests on one, check it against the PRD and the target, and name each such file you rely on in your \`summary\`. Read the field in every file you open.

CITE THE ARCHITECTURE; DO NOT RESTATE IT. A requirement that names the obligation and cites the view path that describes it (a target, delta or effective view) is complete and is the preferred shape. Where the architecture already settles a point a PRD requirement raises, cite that view. A correct TRD is often very short; where the architecture obliges nothing new, write nothing for it.

${writeBrief}
PRD (source of product requirements):
${prdText}
${deltaBlock}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

${archText}
${feedback ? `\nFeedback on the previous version from the gate — address every point:\n${feedback}` : ''}

Each technical requirement has a stable ID, NAMES ITS SOURCE, names the design element it applies to, and is verifiable. The source is EITHER a PRD requirement (in \`prdRefs\`) OR an architecture view (in \`archRefs\`); an architecture-sourced requirement carries an empty \`prdRefs\`. Where a requirement and a view disagree, name the disagreement in your \`summary\` with both citations.

Return at most ${MAX_REQUIREMENTS} technical requirements, each under 60 words, and keep the TRD document under about 25,000 characters: consolidate related obligations into one requirement rather than splitting them. Cite every view a requirement rests on in \`archRefs\`.

CITE THE VIEWS IN THE DOCUMENT AS WELL AS IN YOUR RESULT: YAML frontmatter at the top of the TRD with \`decisionIds:\` listing every view any requirement depends on, and on each requirement the views it depends on. Cite an effective view by its path relative to the arc42 folder and a target or delta view by its path relative to the architecture directory (for example \`target/<subject>/delta/<section>/<view>.md\`), with \`#<heading>\` when the requirement rests on one part of it; cite only files you read, and never a section number in place of one.${persistBrief(ART, 'trd.md', 'the complete TRD as a markdown document', { beadKey: 'trd' })}`,
  {
    label: 'author:trd',
    phase: 'Author TRD',
    effort: 'medium',
    agentType: 'trd-author',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['trdPath', 'requirements'],
      properties: {
        trdPath: { type: 'string' },
        decisionIds: { type: 'array', items: { type: 'string' } },
        requirements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'requirement', 'appliesTo', 'prdRefs', 'archRefs', 'verification'],
            properties: {
              id: { type: 'string' },
              requirement: { type: 'string' },
              appliesTo: { type: 'string' },
              prdRefs: { type: 'array', items: { type: 'string' } },
              archRefs: { type: 'array', items: { type: 'string' } },
              verification: { type: 'string' },
            },
          },
        },
        summary: { type: 'string' },
        notes: { type: 'string' },
      },
    },
  }
)
if (!trd) return dispatchOutcome({ ok: false, stage: 'author', reason: 'TRD authoring produced nothing', ...died('Author TRD') })
const resultPath = ART ? authorPath : trd.trdPath || trdPath
if (typeof resultPath === 'string' && resultPath.startsWith('/')) trd.trdPath = resultPath

// The record and the bead metadata are the workflow's, run through the checked relay once the
// author returns; a step that fails is named in persistErrors and the run goes on, as it did when
// the author ran them.
const persistErrors = []
if (ART && RELAY_RUNNER) {
  const relayDir = typeof relayArg.dir === 'string' && relayArg.dir.trim().startsWith('/') ? relayArg.dir.trim().replace(/\/+$/, '') : `${ART.dir}/relay/trd`
  let relaySeq = 0
  const relayFile = (label) => {
    relaySeq += 1
    return `${relayDir}/${String(relaySeq).padStart(3, '0')}-${label}.json`
  }
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
  const recorded = await relayKit.run(settleAgent, {
    label: 'record:trd',
    phase: 'Author TRD',
    runner: RELAY_RUNNER,
    argv: ['python3', ART.script, 'record', authorPath, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])],
    file: relayFile('record-trd'),
    keys: ['sha256', 'bytes'],
    tail: 20,
  })
  const sha256 = recorded.ok && recorded.exitCode === 0 && recorded.json && /^[0-9a-f]{64}$/.test(String(recorded.json.sha256)) ? recorded.json.sha256 : ''
  if (!sha256) {
    persistErrors.push(`trd.md was not recorded: ${!recorded.ok ? recorded.error : `the record command exited ${recorded.exitCode}: ${String(recorded.stderrTail || recorded.stdoutTail || '').trim().slice(0, 600)}`}`)
  } else if (hasText(ART.relDir) && hasText(ART.beadId)) {
    const marked = await relayKit.run(settleAgent, {
      label: 'bead:trd-metadata',
      phase: 'Author TRD',
      runner: RELAY_RUNNER,
      argv: ['bd', 'update', ART.beadId, '--set-metadata', `artifact_trd_path=${ART.relDir}/trd.md`, '--set-metadata', `artifact_trd_sha256=${sha256}`],
      file: relayFile('bead-trd-metadata'),
      tail: 20,
    })
    if (!marked.ok || marked.exitCode !== 0) persistErrors.push(`the TRD metadata was not set on ${ART.beadId}: ${!marked.ok ? marked.error : `bd update exited ${marked.exitCode}: ${String(marked.stderrTail || marked.stdoutTail || '').trim().slice(0, 600)}`}`)
  }
  for (const e of persistErrors) log(e)
} else if (ART) {
  log('trd-authoring: no relay runner (pluginRoot or relay.runner) was passed, so the author session recorded trd.md itself')
}

return dispatchOutcome({
  ok: true,
  ...(persistErrors.length ? { persistErrors } : {}),
  trdPath: resultPath,
  filingPath,
  trd,
  decisionIds: [...new Set([
    ...(Array.isArray(trd.decisionIds) ? trd.decisionIds : []),
    ...(Array.isArray(trd.requirements) ? trd.requirements : []).flatMap((r) => (Array.isArray(r.archRefs) ? r.archRefs : [])),
  ].map((x) => String(x == null ? '' : x).trim()).filter(Boolean))],
})
