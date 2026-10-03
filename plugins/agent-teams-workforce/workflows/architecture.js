export const meta = {
  name: 'architecture',
  description:
    "Leaf mini — designs the architecture for one Epic's PRD as a target and a delta version, and integrates the approved target into the effective version. Its inputs are the PRD, the effective version in arc42 (every section and view, found through the catalog frontmatter), the open targets that show the same elements, the code on each relevant repository's main, the open beads, and the AWS documentation through the AWS MCP tools; never what is deployed. A prd-reality-reconciler session writes survey.md and survey.json, with repository facts from the polyrepo-steward. Then rounds: the architecture-decision-workflow-coordinator names the proposers, reviewers, diagram authors and cost reviewers each round and the script runs them; proposers write the target and delta views into a draft, reviewers mark every claim verified, unsupported or wrong with evidence, and every finding is answered by its owner, up to maxRounds (default 6). Every session treats anything in the PRD about how the system works as no requirement: the team decides every technical aspect itself. The script holds the decision until every proposer has stated claims, every claim has a verdict, the required reviewers and a cost reviewer have reviewed the design (the pattern challenger, for targeted critique only when needed), every finding is answered, and depscore.py arch-target accepts the draft; a resumed run reads its saved work through depscore.py arch-resume, which folds the saved round results into the claim and finding ledger on disk (ledger.json, which the sessions read) and returns only the facts the run branches on, and it stops, keeping the saved work, when that work cannot be read. The architecture-decider, given artifact paths only, approves the team's result, choosing where the team left competing solutions, or returns it to a named proposer; anything else it escalates goes back to the team, and only two business requirements that no design can satisfy together, or an architecture that contradicts itself where common sense cannot settle it, reach the owner. On approval depscore.py arch-target writes target/<subject>/ and its delta/ as in-review, the architecture-maintainer integrates the target into arc42, the architecture-conformance-reviewer checks it (at most 2 correction passes), and depscore.py arch-approve sets the integrated files the review covered to effective; depscore.py arch-commit then commits the files the integration changed, staging only those paths, and pushes the branch. A write under arc42 section 2 fails the run and is undone: depscore.py arch-constraints fingerprints that folder before and after and copies it aside, and depscore.py arch-constraints-restore puts it back. depscore.py arch-snapshot fingerprints arc42/, target/ and built/: a write there before the target is approved fails the run, and the integration's files are measured from it, not taken from the maintainer's report, so every file the integration wrote is reviewed before arch-approve sets it to effective. Returns { ok, stage, subject, targetDir, deltaDir, deltaFiles, decision, architectureUpdate, conformance, approval, vaultCommit } or, for conflicting business requirements or a contradiction in the architecture, ok:false at stage owner-concern with requiredHumanActions.",
  phases: [
    { title: 'Survey', detail: 'the polyrepo-steward names the repositories; a prd-reality-reconciler session surveys the effective views, code on main, open beads and open targets for each capability the PRD needs' },
    { title: 'Rounds', detail: 'the coordinator names each round of proposers, reviewers, diagram authors and cost reviewers; the script runs them and tracks every claim and finding' },
    { title: 'Decide', detail: 'after the team has designed, challenged and settled the target, the architecture-decider approves it, choosing where the team left competing solutions, or returns it to a named proposer; only two business requirements no design can satisfy together, or an architecture that contradicts itself where common sense cannot settle it, reach the owner' },
    { title: 'Target', detail: 'depscore.py arch-target writes the approved draft to target/<subject>/ and its delta/ as in-review' },
    { title: 'Integrate', detail: 'the architecture-maintainer integrates the target into arc42; the architecture-conformance-reviewer checks it; depscore.py arch-approve sets the reviewed files to effective; depscore.py arch-commit commits and pushes the integrated files' },
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


let dispatchInterruption = null
function dispatchOutcome(result) {
  return dispatchInterruption ? { ...result, ok: false, paused: true, resumable: true, dispatchFailed: true, stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message, dispatchInterruption } : result
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
const dispatchFailures = []

async function run(prompt, opts) {
  if (dispatchInterruption) return null
  let message = 'returned nothing'
  try {
    const out = await fableAgent(prompt, opts)
    if (out) return out
  } catch (err) {
    message = String((err && err.message) || err)
    const cause = dispatchFailureCause(err)
    if (cause !== 'deterministic') dispatchInterruption = { stage: cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable', message }
  }
  dispatchFailures.push({ label: opts.label, agentType: opts.agentType || null, phase: opts.phase, message })
  log(`${opts.label}: no structured result — ${message}`)
  return null
}

function died(phaseName) {
  const deaths = dispatchFailures.filter((f) => f.phase === phaseName)
  return deaths.length
    ? { dispatchFailed: true, dispatchFailures: deaths, reason: deaths.map((f) => `${f.label}: ${f.message}`).join('; ') }
    : {}
}

return dispatchOutcome(await (async () => {
// args: { prd: { id?, title?, path?, body? }, epic: { id }, archPath, subject?, repoPath?, seedRepos?,
//   maxRounds?, depscore: { script, repo },
//   artifacts: { dir, relDir?, epicId, script, phase, inputs?, beadId? } }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const listed = (x) => (Array.isArray(x) ? x.filter(hasText).map((s) => s.trim()) : [])

const prd = a.prd && typeof a.prd === 'object' ? a.prd : {}
const epicId = String((a.epic && (a.epic.id || a.epic.beadId)) || '').trim()
const archPath = hasText(a.archPath) ? a.archPath.trim().replace(/\/+$/, '') : ''
const ART = a.artifacts && typeof a.artifacts === 'object' && hasText(a.artifacts.dir) && hasText(a.artifacts.script) ? a.artifacts : null
const DS = a.depscore && typeof a.depscore === 'object' && hasText(a.depscore.script) && hasText(a.depscore.repo) ? a.depscore : null
const MAX_ROUNDS = Number.isInteger(a.maxRounds) && a.maxRounds > 0 ? a.maxRounds : 6
const MAX_CORRECTIONS = 2

function refuse(why) {
  return { ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why }
}
if (!archPath) return refuse("no archPath supplied (the project's ATW_ARCH_PATH) — there is no architecture to design from or integrate into. Set ATW_ARCH_PATH for the run, or pass archPath to this mini.")
if (!hasText(prd.path) && !hasText(prd.body)) return refuse('no PRD supplied: pass prd.path (or prd.body)')
if (!epicId) return refuse('no Epic supplied: pass epic.id')
if (!ART) return refuse("no artifacts directory or recorder supplied: the architecture step saves its survey, round results and decision under the Epic's working directory, so a stopped run resumes from them")
if (!DS) return refuse('no depscore script and beads repository supplied: the target write, the section 2 check and the approval run through depscore.py')

const ARC42 = `${archPath}/arc42`
const CONSTRAINTS = `${ARC42}/02-architecture-constraints`
const MENU = `${archPath}/reference/diagram-and-model-types.md`
const MODEL = `${archPath}/reference/architecture-documentation-model.md`
const WORK = `${ART.dir}/architecture`
const DRAFT = `${WORK}/draft`
const ROUNDS_DIR = `${WORK}/rounds`
const SURVEY_MD = `${WORK}/survey.md`
const SURVEY_JSON = `${WORK}/survey.json`
const DECISION_MD = `${WORK}/decision.md`
const DECISION_JSON = `${WORK}/decision.json`
const TARGET_JSON = `${WORK}/target.json`
const UPDATE_JSON = `${WORK}/architecture-update.json`
const LEDGER_JSON = `${WORK}/ledger.json`
const TREE_START = `${WORK}/tree-start.json`
const TREE_LAST = `${WORK}/tree-last.json`
const TARGET_CHECK = `${WORK}/target-check.json`
const prdRef = hasText(prd.path) ? `the document at ${prd.path}. Read it in full: every requirement in it is in scope.` : `\n${prd.body}`
const prdBase = hasText(prd.path) ? String(prd.path).split('/').pop().replace(/\.md$/i, '') : ''
const beadPrefix = epicId.includes('-') ? `${epicId.split('-')[0]}-` : ''
const FORBID = [epicId, beadPrefix, prd.id, prdBase].filter(hasText)


// ===== SHARED BLOCK relay — BEGIN (canonical: scripts/shared-blocks/relay.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
// ── CHECKED RELAY: deterministic work reaches this script unaltered, or not at all ──
//
// A workflow script cannot run a command or read a file. A command reaches the shell only as
// text a runner session types, and its result reaches the script only as that session's copy.
// Neither copy is trusted:
// - every command line carries --argv-sha256, the SHA-256 of the canonical JSON of its argument
//   list; the program refuses (exit 3, nothing run) a command line typed differently;
// - every result is printed as ONE RELAY64v1: line carrying base64 canonical JSON: a flat object of scalars (the view's leaves keyed by
//   path, plus ~exit, ~checksum and the relay file's ~file, ~sha256, ~bytes), where ~checksum
//   is the SHA-256 of the canonical JSON of { exit, view }. The runner returns that line as a
//   verbatim string; the script parses it, recomputes the checksum and accepts only an exact
//   copy, then rebuilds the view. A damaged copy can retry only reading the exact saved
//   receipt twice; the original command never repeats. Exhaustion pauses this item visibly.
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
    properties: { exitCode: { type: 'integer' }, stdout: { type: 'string', description: 'Copy the complete RELAY64v1: line verbatim. Treat its base64 payload as opaque text; never decode or reconstruct it.' } },
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
  function decodeTransport(text) {
    const prefix = 'RELAY64v1:'
    if (!text.startsWith(prefix)) return text
    const encoded = text.slice(prefix.length)
    if (!encoded || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) throw new Error('invalid relay base64 alphabet or padding')
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    let decoded = ''
    for (let i = 0; i < encoded.length; i += 4) {
      const a = alphabet.indexOf(encoded[i])
      const b = alphabet.indexOf(encoded[i + 1])
      const c = encoded[i + 2] === '=' ? 0 : alphabet.indexOf(encoded[i + 2])
      const d = encoded[i + 3] === '=' ? 0 : alphabet.indexOf(encoded[i + 3])
      if ((encoded[i + 2] === '=' && (b & 15)) || (encoded[i + 3] === '=' && encoded[i + 2] !== '=' && (c & 3))) throw new Error('noncanonical relay base64 padding bits')
      const bytes = [(a << 2) | (b >> 4)]
      if (encoded[i + 2] !== '=') bytes.push(((b & 15) << 4) | (c >> 2))
      if (encoded[i + 3] !== '=') bytes.push(((c & 3) << 6) | d)
      for (const byte of bytes) {
        if (byte > 0x7f) throw new Error('relay payload must be canonical ASCII JSON, a strict UTF-8 subset')
        decoded += String.fromCharCode(byte)
      }
    }
    return decoded
  }
  /** Parses a runner's stdout copy and checks it is exactly the envelope the program printed; returns { env, flat } or { why }. */
  function parse(stdout, file) {
    let env
    try {
      const text = String(stdout || '').trim()
      const open = '<exact_text>'
      const close = '</exact_text>'
      const payload = text.startsWith(open) && text.endsWith(close) ? text.slice(open.length, -close.length) : text
      env = JSON.parse(decodeTransport(payload))
    } catch (err) {
      env = null
    }
    if (!env || typeof env !== 'object' || Array.isArray(env)) {
      const text = String(stdout || '')
      const exception = exceptionOf(text)
      return { why: exception ? `the program failed: ${exception}` : `stdout is not one valid relay envelope line: ${JSON.stringify(text.slice(0, 300))}` }
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
    if (got !== env['~checksum']) return { env, why: `the copy hashes to ${got}, not to the ${env['~checksum']} the program printed` }
    return { env, flat }
  }
  const prompt = (command) => `Run exactly this one shell command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000, and change nothing else. Type the command exactly as written below, character for character: the program checks it against the checksum it carries and refuses any difference.

${command}

It prints exactly one line beginning RELAY64v1: followed by base64 text. Copy that entire line as opaque text, including the prefix and any trailing = characters. Do not decode the base64, interpret its contents, or rebuild the JSON. Return the process exit code as \`exitCode\` and that line, verbatim, as the string \`stdout\`: every character as printed, in order, with nothing added, removed, reordered, reformatted or re-typed. Do not parse it, do not summarize it. If it printed more than one line, return all of stdout verbatim. Do not retry, do not repair, do not run any other command.`
  /** Runs a command once. A damaged copy can only re-read its exact saved receipt. */
  async function exec(dispatch, { label, phase, command, file = null, readRunner = null }) {
    const out = await dispatch(prompt(command), { label, phase, model: 'sonnet', effort: 'low', schema: SCHEMA })
    if (!out) return { ok: false, noResult: true, error: `the ${label} runner returned no result` }
    let got = parse(out.stdout, file)
    if (got.why) {
      const receipt = got.env
      const bound = out.exitCode === 0 && receipt && receipt['~exit'] === 0 && file && readRunner && HEX.test(String(receipt['~sha256'])) && Number.isInteger(receipt['~bytes']) && receipt['~bytes'] >= 0
      let attempts = 1
      let reason = got.why
      if (bound) {
        const readCommand = pythonLine(readRunner, ['read', '--relay', file, '--sha256', receipt['~sha256'], '--bytes', String(receipt['~bytes'])])
        for (let retry = 1; retry <= 2; retry++) {
          attempts++
          log(`RELAY_COPY_RECOVERY_ATTEMPT ${JSON.stringify({ label, relayFile: file, attempt: retry, reason })}`)
          const copied = await dispatch(`The previous response failed validation: ${reason}. The original command has already completed. Do not execute it again. This corrective attempt only reads the saved result whose bytes must match the original receipt.

${prompt(readCommand)}`, { label: `${label}:copy-recovery${retry}`, phase, model: 'sonnet', effort: 'low', schema: SCHEMA })
          got = copied ? parse(copied.stdout, file) : { why: 'the corrective reader returned no result' }
          if (!got.why && (copied.exitCode !== 0 || got.env['~sha256'] !== receipt['~sha256'] || got.env['~bytes'] !== receipt['~bytes'] || got.env['~exit'] !== 0)) got = { why: 'the corrective read did not return the successful original receipt' }
          if (!got.why) break
          reason = got.why
        }
      }
      if (got.why) {
        const detail = { label, relayFile: file, attempts, reason: `${reason}${bound ? '' : '; no successful saved receipt is available for safe read-only recovery'}` }
        const error = `RELAY_COPY_RECOVERY_EXHAUSTED ${JSON.stringify(detail)}`
        log(error)
        return { ok: false, paused: true, recoveryKind: 'relay-copy-recovery', error }
      }
    }
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
    const r = await exec(dispatch, { label, phase, command: pythonLine(script, rest), file, readRunner: script.replace(/[^/]+$/, 'relayrun.py') })
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
    const r = await exec(dispatch, { label, phase, command: pythonLine(runner, rest), file, readRunner: runner })
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
    'import base64, hashlib, json, sys',
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
    '    print("RELAY64v1:" + base64.b64encode(c(dict(f, **{"~exit": ex, "~checksum": h({"exit": ex, "view": f})})).encode("ascii")).decode("ascii"))',
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

/** Where the full results relayed to this script are saved, one numbered file per command. */
const RELAY_DIR = `${WORK}/relay`
/** scripts/portfolio/relayrun.py, beside depscore.py: runs any other program, and checks or writes saved JSON, through the checked relay. */
const RELAY_RUNNER = DS.script.replace(/[^/]+$/, 'relayrun.py')
let relaySeq = 0
/** The next relay file, named for its label. */
function nextRelayFile(label) {
  relaySeq += 1
  return `${RELAY_DIR}/${String(relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
}
/** Runs one depscore.py command through the checked relay; returns the facts it printed with `relayFile`, or { error, exception? }. */
function depscore(label, phaseName, commandArgs) {
  return relayKit.depscore(run, { label, phase: phaseName, script: DS.script, repo: DS.repo, tail: commandArgs, file: nextRelayFile(label) })
}
/** The artifact recorder's command for one saved file. */
function recordArgv(file) {
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
  return ['python3', ART.script, 'record', file, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])]
}
/** Records saved files with the artifact recorder, one checked command each; returns the files it did not record. */
async function recordFiles(label, phaseName, files) {
  const failed = []
  for (const f of files) {
    const name = String(f).split('/').pop()
    const r = await relayKit.run(run, { label: `${label}:${name}`, phase: phaseName, runner: RELAY_RUNNER, argv: recordArgv(f), file: nextRelayFile(`${label}-${name}`) })
    if (!r.ok || r.exitCode !== 0) failed.push(f)
  }
  if (failed.length) log(`${label}: the recorder did not record ${failed.join(', ')}`)
  return failed
}
/**
 * Saves a session's structured result: makes `file` hold exactly `value` (the result as the runtime
 * validated it against the session's schema; a saved copy that differs or is missing is rewritten
 * through relayrun.py, which refuses a copy that does not hash as built), then records it. Returns
 * whether the file now holds the result and was recorded.
 */
async function saveResult(label, phaseName, file, value) {
  const saved = await relayKit.ensureJson(run, { label: `${label}:save`, phase: phaseName, runner: RELAY_RUNNER, file, value })
  if (!saved.ok) {
    log(`${label}: ${file} could not be made to hold the returned result: ${saved.error}`)
    return false
  }
  return !(await recordFiles(`${label}:record`, phaseName, [file])).length
}
/** Returns the save instruction for files a session writes under the architecture working directory; the script checks and records them. */
function persistBrief(files, what) {
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. No other session writes it for you.
Write ${what} with the Write tool, replacing the whole file if it exists (Read it first if the Write tool asks you to):
${files.map((f) => `   - ${f}`).join('\n')}
The workflow checks each saved JSON file against the result you return and records every file; run no record command. Never improvise another way to write or move a file.`
}

const ARCH_WHERE = `THE ARCHITECTURE is at ${archPath}. It is not inside any product repository.
- \`arc42/\` is the effective version: the approved architecture. \`arc42/02-architecture-constraints/README.md\` holds the owner's constraints; read it in full. \`arc42/04-solution-strategy/README.md\` holds the enterprise-level strategy; read it. Every other section is the design so far, as views.
- The constraints are the owner's; everything else in the architecture is the design so far, followed as established patterns unless a design states a reason and evidence to change it.
- Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog. Find the views of an element by searching it (\`subject:\` and the \`shows:\` lists) for the element's name, in every section, at every scope.
- \`target/<subject>/\` folders are open targets (designs in progress) and \`built/<subject>/\` folders record builds that differ from the effective version. Read every open target that shows an element this PRD touches, so the designs do not contradict each other.
- The architecture documentation model is ${MODEL}; the view types to choose from are ${MENU}.
- \`lifecycle_state\` is per file: \`effective\` was reviewed and approved; \`in-review\` is input to check, never assumed vetted.`

const INPUTS_RULE = `YOUR INPUTS are the PRD, the effective version and the open targets above, the code on each relevant repository's \`main\` (read it as committed there: \`git -C <repo> grep -n <term> main\`, \`git -C <repo> show main:<path>\`), the open beads (other Epics' Stories and Tasks planned but not built), and the AWS documentation through the AWS MCP tools and skills. What is deployed in AWS is not an input: run no AWS describe, list or get call against an account. Repository code is input to check, never evidence that a design is right. Cite what you rely on: a view by its absolute path and heading, code by repository, path and line on \`main\`, AWS behaviour by the documentation URL you read.`

const PRD_RULE = `THE PRD STATES WHAT, NEVER HOW. It holds the business and end-user requirements: what the seeker and the business get, and the results someone outside the system could observe. Anything in it about how the system works — mechanisms, services, technologies, response shapes and codes, contracts, telemetry, release mechanics, engineering numbers such as latencies, limits and thresholds — is not a requirement: ignore it, and never treat it as a defect. The architecture team decides every technical aspect itself, from the effective architecture, the code and the AWS documentation through the AWS MCP tools and skills. Where the PRD leaves a technical value open, the team chooses it and states the reason and evidence. Where two requirements seem to pull against each other, the team designs the solution that best satisfies both, putting the seeker's privacy and data protection first, and records that as a design decision with its reason. None of this is a question for the owner.`

const BUSINESS_CONFLICT_RULE = `List in \`businessConflicts\` only two BUSINESS requirements of the PRD that no design whatsoever could satisfy together (each with the requirement and why no design can satisfy both). A technical gap, an open value, a "how" in the PRD, or a tension a design can resolve is never one: the team resolves those. This list is almost always empty.`

const DRAFT_RULES = `THE DRAFT TARGET is the folder ${DRAFT}. It has the arc42 section layout (\`05-building-block-view/…\`, \`06-runtime-view/…\`, \`07-deployment-view/…\`, \`08-crosscutting-concepts/…\`, and \`03-context-and-scope/\` or \`04-solution-strategy/\` only when the change reaches them) and a \`delta/\` folder beside them.
- A target view is the view as it will read once approved: a changed copy of each effective view that shows a changed element, at every scope where the element appears, and coverage for new elements according to the applicable obligations in ${MODEL}. Extend a sufficient shared view when it answers the required reader question; create a new view only when no existing or shared view supplies the required coverage. Catalog every covered element in \`shows\`. Copy an effective view into the draft before you change it, at the same relative path.
- \`delta/\` holds the views that show only what changes between the effective version and the target. Specs and Tasks are made from it.
- Every view is Markdown with catalog frontmatter (\`view_type\` from ${MENU}, \`scope\`, \`subject\`, \`shows\`, \`lifecycle_state: in-review\`), a Mermaid diagram where the view type has one, and prose.
- Nothing goes under \`02-architecture-constraints/\`: section 2 holds the owner's constraints.
- Name files and folders for their subject, never for the PRD, the Epic, a bead or a date. Write no history, decision record, rule or open item into a view.
- Write nothing in ${archPath}: the target reaches the architecture only after approval.`

const AGENT_PREFIX = 'agent-teams-workforce:'
const USER_LEVEL_AGENTS = new Set([
  'integration-pattern-architect',
  'persistence-architecture-specialist',
  'security-architecture-designer',
  'cdk-infrastructure-designer',
  'event-schema-designer',
  'domain-event-modeler',
  'bounded-context-mapper',
  'architecture-pattern-challenger',
  'architecture-tradeoff-skeptic',
  'architecture-boundary-guardian',
  'operational-readiness-reviewer',
  'failure-mode-analyst',
  'cost-architecture-reviewer',
  'cost-impact-reviewer',
])
const dispatchName = (name) => (USER_LEVEL_AGENTS.has(name) ? name : `${AGENT_PREFIX}${name}`)

const ROSTER = {
  proposer: {
    'integration-pattern-architect': 'integration between services: event and API patterns, sync or async, service boundaries',
    'persistence-architecture-specialist': 'persistence: table, key and index design from the access patterns',
    'security-architecture-designer': 'security: trust boundaries, identity and access, encryption, threat model',
    'cdk-infrastructure-designer': 'infrastructure: CDK stacks and constructs, function boundaries, packaging',
    'event-schema-designer': 'event schemas within the event envelope the architecture establishes',
    'api-contract-designer': 'REST API contracts',
    'graphql-schema-designer': 'GraphQL schemas',
    'domain-event-modeler': 'domain events, their flows and contracts',
    'bounded-context-mapper': 'domain boundaries and the relationships between contexts',
  },
  diagram: {
    'architecture-diagram-author': 'views of any type in the list of view types, at any scope',
    'c4-diagram-author': 'C4 views: system context, container, component',
    'uml-diagram-author': 'UML views: sequence, state, activity, class',
  },
  reviewer: {
    'architecture-pattern-challenger': 'critiques concrete structural weaknesses in the retained design without authoring another proposal',
    'architecture-tradeoff-skeptic': 'hidden assumptions and optimistic estimates behind a tradeoff',
    'architecture-boundary-guardian': 'coupling across contexts; conflicts with the constraints; departures from established patterns without reason and evidence',
    'operational-readiness-reviewer': 'operational burden: monitoring, alerting, runbooks',
    'failure-mode-analyst': 'failure modes: throttling, duplicate delivery, downstream unavailability, poison messages',
  },
  cost: {
    'cost-architecture-reviewer': 'the cost of the design, with the unit math shown',
    'cost-impact-reviewer': 'where the cost of the design changes shape as usage grows',
  },
}
const WRITER_ROLES = ['proposer', 'diagram']
const REVIEW_ROLES = ['reviewer', 'cost']
const roleOf = (name) => Object.keys(ROSTER).find((role) => Object.prototype.hasOwnProperty.call(ROSTER[role], name)) || null
const rosterText = Object.keys(ROSTER)
  .map((role) => `${role}:\n${Object.entries(ROSTER[role]).map(([n, w]) => `  - ${n} — ${w}`).join('\n')}`)
  .join('\n')
const ROSTER_ARG = Object.keys(ROSTER).map((role) => `${role}=${Object.keys(ROSTER[role]).join(',')}`).join(';')

/** The owner the coordinator assigned to each finding that had none: finding id -> writer. */
const assigned = new Map()
/**
 * Reads the step's saved work on disk with depscore.py arch-resume, which folds every saved round
 * result into the claim and finding ledger, writes it to ledger.json for the sessions that read
 * it, and prints only the facts the control flow branches on. No saved content comes back here:
 * sessions get file paths. Returns the facts or { error }.
 */
async function readFacts(label, phaseName, proposalTeam = null, roundPlan = null) {
  const assign = [...assigned].map(([id, w]) => `${id}=${w}`).join(',')
  const command = `arch-resume --work-dir ${shq(WORK)} --roster ${shq(ROSTER_ARG)}${assign ? ` --assign ${shq(assign)}` : ''}${proposalTeam ? ` --proposal-team ${shq(JSON.stringify(proposalTeam))}` : ''}${roundPlan ? ` --round-plan ${shq(JSON.stringify(roundPlan))}` : ''}`
  const out = await depscore(label, phaseName, command)
  if (!out || out.error || !out.rounds || typeof out.rounds !== 'object' || !out.integration || !out.coverage || !Number.isInteger(out.coverage.gapCount)) {
    return { error: (out && out.error) || 'depscore.py arch-resume printed no facts', exception: (out && out.exception) || '' }
  }
  const problem = pendingPlanProblem(out.rounds)
  if (problem) return { error: `depscore.py arch-resume reported a pending round plan that is not the shape it prints: ${problem}. The saved work in ${WORK} is untouched.` }
  // The open findings arrive grouped by owner ({ owner: { answered: [id], open: [id] } }); their verdicts and files are in the ledger.
  out.rounds.openFindings = Object.entries(out.rounds.openFindings || {}).flatMap(([owner, s]) => [
    ...listed(s && s.answered).map((id) => ({ id, owner, answered: true })),
    ...listed(s && s.open).map((id) => ({ id, owner, answered: false })),
  ])
  if (Number(out.rounds.overlapWarnings) > 0) log(`Rounds: ${out.rounds.overlapWarnings} reviewer overlap warning(s), listed under result.rounds.overlapWarnings in ${out.relayFile}`)
  if (out.rounds.planKept === true) log(`Rounds: the plan already saved for round ${out.rounds.pendingRound} stands (result.rounds.planKept in ${out.relayFile})`)
  return out
}
/** True when arch-resume's facts report coverage gaps, or do not say how many. */
const hasGaps = (f) => !f || !f.coverage || !Number.isInteger(f.coverage.gapCount) || f.coverage.gapCount > 0
/** Where the approved coverage rows are: the relay file of the arch-resume run that read them (result.coverage.checksNeeded); arch-review-check reads them there. */
const coverageRowsOf = (f) => ({ file: String((f && f.relayFile) || ''), rows: Number(f && f.coverage && f.coverage.rows) || 0 })

/**
 * Returns why the pending round plan in arch-resume's facts is not the shape depscore.py prints
 * (pendingRound and pendingDispatches agree with pendingPlan, which lists every dispatch in seq
 * order, each { seq, role, agentType, complete }, with at least one not complete), or '' when it is.
 */
function pendingPlanProblem(rounds) {
  const pp = rounds.pendingPlan
  const pr = rounds.pendingRound
  if (pp === undefined || pr === undefined || rounds.pendingDispatches === undefined) return 'pendingPlan, pendingRound or pendingDispatches is missing'
  if (pp === null) return pr === null ? '' : `pendingRound is ${pr} but pendingPlan is null`
  if (typeof pp !== 'object' || pp.round !== pr || !Number.isInteger(pr)) return `pendingPlan round ${pp && pp.round} does not match pendingRound ${pr}`
  if (!Array.isArray(pp.dispatches) || pp.dispatches.length !== rounds.pendingDispatches) return `pendingPlan.dispatches is not a list of ${rounds.pendingDispatches} dispatch(es)`
  const bad = pp.dispatches.findIndex((d, i) => !d || !Number.isInteger(d.seq) || d.seq < 1 || (i > 0 && d.seq <= pp.dispatches[i - 1].seq) || !hasText(d.agentType) || roleOf(d.agentType) !== d.role || typeof d.complete !== 'boolean')
  if (bad >= 0) return `pendingPlan dispatch ${bad + 1} lacks its seq, role, agentType or complete`
  if (pp.dispatches.every((d) => d.complete)) return 'pendingPlan has no dispatch left to run'
  return ''
}

/** The result file of one dispatch of round n, as depscore.py arch-resume names it. */
const resultFile = (n, d) => `${ROUNDS_DIR}/r${n}-${d.seq}-${d.role}-${d.agentType}.json`
/**
 * Returns the dispatches of a saved pending plan, ready to run: the identity and completion
 * arch-resume reports for each. Task, files, answers and assigned claims are always read from
 * the authoritative plan entry in ledger.json, including reconciled legacy plans.
 */
function planDispatches(pp) {
  // The loader can reconcile a retained plan. Never override it with stale in-memory scope.
  return pp.dispatches.map((c) => ({ ...c, task: '', files: null, answers: null, file: resultFile(pp.round, c) }))
}

const CONFLICT_ITEMS = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['requirements', 'why'],
    properties: { requirements: { type: 'array', items: { type: 'string' } }, why: { type: 'string' } },
  },
}
const REPOS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['repositories'],
  properties: {
    repositories: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'path', 'role', 'lifecycle'],
        properties: { name: { type: 'string' }, path: { type: 'string' }, role: { type: 'string' }, lifecycle: { type: 'string' } },
      },
    },
  },
}
// Consumed by: archresume coverage folding and architecture.js decisionGaps — stable
// ids preserve absent obligations; MODEL evidence supplies semantics, not a plugin menu.
// Consumed by archevidence: local section/main revision binding and external provenance.
const EVIDENCE_REFS = { type: 'array', items: { type: 'object', additionalProperties: false,
  required: ['path', 'heading', 'repo', 'revision', 'url'], properties: {
    path: { type: 'string' }, heading: { type: 'string' }, repo: { type: 'string' },
    revision: { type: 'string' }, url: { type: 'string' },
  } } }
const COVERAGE_SCHEMA = {
  type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['id', 'subject', 'scope', 'obligation', 'sources', 'views', 'status', 'action', 'reason', 'evidenceRefs', 'disposition', 'dispositionReason'],
    properties: {
      id: { type: 'string' }, subject: { type: 'string' }, scope: { type: 'string' },
      obligation: { type: 'string' }, sources: { type: 'array', items: { type: 'string' } },
      views: { type: 'array', items: { type: 'string' } }, status: { type: 'string', enum: ['Present and sufficient', 'Present but incomplete', 'Required and absent', 'Not yet applicable', 'Not assessed'] },
      action: { type: 'string', enum: ['create', 'update', 'unchanged', 'remove', 'not-applicable', 'unresolved'] },
      reason: { type: 'string' },
      evidenceRefs: EVIDENCE_REFS, disposition: { type: 'string', enum: ['required', 'unrelated-debt'] }, dispositionReason: { type: 'string' },
    },
  },
}
// Consumed by: archresume — only an independent check of the current generated
// row/content revision satisfies coverage; reviewer prose is read by the decider.
const COVERAGE_CHECKS_SCHEMA = {
  type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['id', 'revision', 'verdict', 'evidence'],
    properties: {
      id: { type: 'string' }, revision: { type: 'string' },
      verdict: { type: 'string', enum: ['verified', 'unsupported', 'wrong'] }, evidence: { type: 'string' },
    },
  },
}
const COVERAGE_RULE = `COVERAGE is evidence in the existing survey/round results and ${LEDGER_JSON}, not another architecture version. Read ${MODEL} for applicable obligations and ${MENU} for selection/construction. Inventory relevant subjects from the design, repositories and contracts independently of catalog hits. Include required views that do not exist, every affected scope and horizontal concern; unrelated historical debt is non-blocking and is reported in your summary.
Each coverage row has a stable id, subject, scope, obligation (MODEL path and heading), sources (inventory/design evidence), views (absolute paths, including expected missing paths), status (the MODEL's assessment result), action and reason. Preserve ids across rounds; omitted ids remain in the ledger. Writers replace only their assigned rows; use draft paths for created/updated views, draft/delta descriptions for removals (not the canonical file being deleted), and canonical paths only for unchanged views. Keep removal evidence stable through integration. After completing work, update status to Present and sufficient; Not yet applicable pairs only with action not-applicable. Incomplete, absent and Not assessed statuses cannot pass approval. An unknown relevant obligation uses action unresolved. Not-applicable and unchanged need concrete reasons and evidence; no-change targets still assess applicable coverage. Never invent design to fill diagrams. Diagram declarations require actual diagrams; verify rendering, readability, semantics, links and metadata as the MODEL requires, reporting limitations honestly.
The ledger supplies each row's revision from its evidence and current view content. Reviewers copy that revision exactly into coverageChecks, with an independent verdict and evidence. A missing view or obligation can be a finding without an author claim. Recheck revised rows; old checks cannot approve new content.
Set disposition=required by default. For mistakenly inventoried unrelated historical debt, use unrelated-debt with dispositionReason proving it does not affect this change or dependencies; preserve its honest MODEL status. Only an independent verified current revision makes that disposition nonblocking. Retain the row and summarize it; never erase IDs.
EvidenceRefs bind relevant views by absolute path and unique heading (empty means whole file), repository code by absolute repo, main commit revision and repository-relative path, or external docs by url and version/retrieval revision. Unused fields are empty strings. Include relevant dependencies. Source movement requires refreshed evidence; reading test source is not a test run.`

const SURVEY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['subject', 'subjectReason', 'capabilities', 'openTargets', 'businessConflicts', 'coverage', 'summary'],
  properties: {
    subject: { type: 'string' },
    subjectReason: { type: 'string' },
    coverage: COVERAGE_SCHEMA,
    capabilities: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'requirements', 'effectiveViews', 'code', 'openBeads', 'openTargets'],
        properties: {
          name: { type: 'string' },
          requirements: { type: 'array', items: { type: 'string' } },
          effectiveViews: { type: 'array', items: { type: 'string' } },
          code: { type: 'array', items: { type: 'string' } },
          openBeads: { type: 'array', items: { type: 'string' } },
          openTargets: { type: 'array', items: { type: 'string' } },
          notes: { type: 'string' },
        },
      },
    },
    openTargets: { type: 'array', items: { type: 'string' } },
    businessConflicts: CONFLICT_ITEMS,
    summary: { type: 'string' },
  },
}
// Consumed by maker, checker and decider prompts: one shared completion standard.
const DESIGN_REVIEW_STANDARD = `Use the same acceptance basis throughout: applicable PRD outcomes, settled owner decisions and section-2 constraints, the relevant MODEL obligations, existing source evidence, and the retained target/delta. The lead reconciles the combined design before handing it to reviewers: contracts, event publishers, ownership, security and failure behavior must agree across its views. Inspect cited implementation and tests; distinguish evidence read from behavior actually verified. Do this within the existing authoring pass, not a new agent or audit pass.
BEFORE HANDOFF, the producer checks the same concrete obligations the reviewers will check, where relevant to this change: exact contract fields and identifiers across producer/consumer boundaries; event publisher, subscriber and owner agreement; data ownership and lifecycle; authorization and trust boundaries; failure, retry and idempotency behavior; cost assumptions with unit math; and consistency of the target, delta and their diagrams. Trace these against the applicable PRD outcomes, owner constraints, source evidence and MODEL obligations. Supply sufficient detail and evidence for independent verification in the retained views, not merely in the agent summary. This is completion of the assigned design, not permission to add product requirements, unrelated redesign or hypothetical scale. When a repair crosses a retained view boundary, repair the connected contract and views together within the ledger's reconciled ownership scope; do not leave a known contradiction because an earlier task named only one file.
Review is an independent safety net against that same basis, not a source of new requirements or preferred redesigns. Each finding identifies the violated requirement/constraint/contract or concrete correctness defect, its evidence and the bounded repair. Do not reopen a settled mechanism just to offer another design. On later rounds review the changed claims/views and their affected dependencies, retaining still-valid evidence; do not demand fresh unrelated proposals. New evidence of a real defect must still be reported. Neither this shared standard nor the proposer cap guarantees approval.`

const COORDINATOR_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['readyForDecision', 'reason', 'proposalTeam', 'dispatches', 'overlaps'],
  properties: {
    // Consumed by arch-resume and runRound: persist and enforce the effort-wide proposal budget.
    proposalTeam: {
      type: 'object', additionalProperties: false,
      required: ['lead', 'second', 'unresolvedIssue', 'evidence', 'whySecond'],
      properties: {
        lead: { type: 'string' }, second: { type: 'string' },
        unresolvedIssue: { type: 'string' }, evidence: { type: 'string' }, whySecond: { type: 'string' },
      },
    },
    readyForDecision: { type: 'boolean' },
    reason: { type: 'string' },
    dispatches: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['agentType', 'role', 'task', 'files', 'answers', 'claimIds', 'claimFiles'],
        properties: {
          agentType: { type: 'string' },
          role: { type: 'string', enum: Object.keys(ROSTER) },
          task: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          answers: { type: 'array', items: { type: 'string' } },
          claimIds: { type: 'array', items: { type: 'string' } }, claimFiles: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    // Consumed by: unjustifiedOverlaps before the plan is saved, and archrounds.overlap_justified on resume.
    // One entry per overlap: the coordinator decides it once, with one reason.
    overlaps: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['files', 'claimIds', 'agentTypes', 'reason'],
        properties: {
          files: { type: 'array', items: { type: 'string' } },
          claimIds: { type: 'array', items: { type: 'string' } },
          agentTypes: { type: 'array', items: { type: 'string' } },
          reason: { type: 'string' },
        },
      },
    },
  },
}
const REPAIR_ANSWERS_SCHEMA = { type: 'array', items: { type: 'object', additionalProperties: false,
  required: ['repairId', 'response'], properties: { repairId: { type: 'string' }, response: { type: 'string' } } } }
const REPAIR_CHECKS_SCHEMA = { type: 'array', items: { type: 'object', additionalProperties: false,
  required: ['repairId', 'revision', 'verdict', 'evidence', 'files'], properties: {
    repairId: { type: 'string' }, revision: { type: 'string' }, files: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', enum: ['verified', 'revise'] }, evidence: { type: 'string' },
  } } }
const WRITER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['files', 'claims', 'answers', 'businessConflicts', 'coverage', 'summary'],
  properties: {
    repairAnswers: REPAIR_ANSWERS_SCHEMA,
    files: { type: 'array', items: { type: 'string' } },
    coverage: COVERAGE_SCHEMA,
    claims: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claimId', 'claim', 'file', 'citation', 'supersedes', 'evidenceRefs'],
        properties: { claimId: { type: 'string' }, claim: { type: 'string' }, file: { type: 'string' }, citation: { type: 'string' }, supersedes: { type: 'array', items: { type: 'string' } }, evidenceRefs: EVIDENCE_REFS },
      },
    },
    answers: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['findingId', 'response', 'evidence'],
        properties: { findingId: { type: 'string' }, response: { type: 'string', enum: ['fixed', 'disputed'] }, evidence: { type: 'string' } },
      },
    },
    businessConflicts: CONFLICT_ITEMS,
    summary: { type: 'string' },
  },
}
const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings', 'coverageChecks', 'resolutions', 'summary'],
  properties: {
    repairChecks: REPAIR_CHECKS_SCHEMA,
    coverageChecks: COVERAGE_CHECKS_SCHEMA,
    resolutions: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['findingId', 'revision', 'verdict', 'evidence'], properties: { revision: { type: 'string' }, findingId: { type: 'string' }, verdict: { type: 'string', enum: ['accepted', 'rejected'] }, evidence: { type: 'string' } } } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claimId', 'claimRevision', 'claim', 'file', 'verdict', 'evidence', 'owner'],
        properties: {
          claimId: { type: 'string' }, claimRevision: { type: 'string' },
          claim: { type: 'string' },
          file: { type: 'string' },
          verdict: { type: 'string', enum: ['verified', 'unsupported', 'wrong'] },
          evidence: { type: 'string' },
          owner: { type: 'string' },
        },
      },
    },
    estimates: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const OWNER_CONCERN_KINDS = ['business-conflict', 'architecture-conflict']
const DECISION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['round', 'verdict', 'diligence', 'choices', 'returnTo', 'ownerConcerns', 'coverageRevision', 'summary'],
  properties: {
    round: { type: 'integer' },
    coverageRevision: { type: 'string' },
    verdict: { type: 'string', enum: ['approve', 'return', 'owner-concern'] },
    diligence: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['check', 'present', 'where'],
        properties: { check: { type: 'string' }, present: { type: 'boolean' }, where: { type: 'string' } },
      },
    },
    returnTo: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['agentType', 'missing'],
        properties: { agentType: { type: 'string' }, missing: { type: 'string' } },
      },
    },
    choices: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['dispute', 'chosen', 'why'],
        properties: { dispute: { type: 'string' }, chosen: { type: 'string' }, why: { type: 'string' } },
      },
    },
    ownerConcerns: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['kind', 'concern', 'evidence'],
        properties: { kind: { type: 'string', enum: OWNER_CONCERN_KINDS }, concern: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
    summary: { type: 'string' },
  },
}
const MAINTAIN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'createdFiles', 'deletedFiles', 'viewsChecked', 'constraintIssues', 'contradictions', 'summary'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    createdFiles: { type: 'array', items: { type: 'string' } },
    deletedFiles: { type: 'array', items: { type: 'string' } },
    viewsChecked: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['element', 'view', 'action'],
        properties: { element: { type: 'string' }, view: { type: 'string' }, action: { type: 'string', enum: ['updated', 'deleted', 'added', 'unaffected'] } },
      },
    },
    constraintIssues: { type: 'array', items: { type: 'string' } },
    contradictions: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const CONFORMANCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['conforms', 'reviewedFiles', 'findings', 'coverageRevision', 'coverageChecks', 'summary'],
  properties: {
    conforms: { type: 'boolean' },
    coverageChecks: COVERAGE_CHECKS_SCHEMA,
    coverageRevision: { type: 'string' },
    reviewedFiles: { type: 'array', items: { type: 'string' } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'finding', 'evidence'],
        properties: { file: { type: 'string' }, finding: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
    summary: { type: 'string' },
  },
}

/** Returns the section 2 fingerprint, or { error }; with `keep`, section 2 is also copied aside for a restore. */
const constraintsSnapshot = (label, phaseName, keep) => depscore(label, phaseName, `arch-constraints --arch-root ${shq(archPath)}${keep ? ' --keep' : ''}`)
const sameSnapshot = (x, y) =>
  !!x && !!y && !x.error && !y.error && x.exists === y.exists && x.digest === y.digest && JSON.stringify(x.gitStatus || []) === JSON.stringify(y.gitStatus || [])
/** Returns null when section 2 is unchanged since `before`, else puts section 2 back from the copy and returns the failure. */
async function constraintsGuard(before, label, phaseName) {
  const after = await constraintsSnapshot(label, phaseName)
  if (sameSnapshot(before, after)) return null
  const restored = after && after.error ? null : await depscore(`${label}:restore`, phaseName, `arch-constraints-restore --arch-root ${shq(archPath)} --kept ${shq(before.kept)}`)
  const restoreNote = !restored ? '' : restored.error ? `; section 2 could not be put back: ${restored.error}` : `; section 2 was put back as it was (${listed(restored.written).length} file(s) written back, ${listed(restored.deleted).length} deleted)`
  const why = after && after.error
    ? `section 2 could not be fingerprinted after ${phaseName}: ${after.error}`
    : `a session wrote under ${CONSTRAINTS} during ${phaseName}; section 2 holds the owner's constraints and the pipeline never writes there (git status now: ${JSON.stringify((after && after.gitStatus) || [])})${restoreNote}`
  log(`Section 2: ${why}`)
  return { ok: false, stage: 'constraints-written', deterministicFailure: true, reason: why, error: why, before, after, restored }
}

/**
 * Fingerprints every file of arc42/, target/ and built/ with depscore.py arch-snapshot. The per-file
 * hashes stay on disk: `save` writes them to that file, and each file in `against` (a fingerprint
 * saved earlier) yields the NUMBER of files created, changed and deleted since it, in `diffs`, in
 * that order; their names stay in the relay file (`relayFile`, under result.diffs). Returns the
 * result or { error }.
 */
async function treeSnapshot(label, phaseName, { save, against = [] } = {}) {
  const out = await depscore(label, phaseName, `arch-snapshot --arch-root ${shq(archPath)} --counts${save ? ` --save ${shq(save)}` : ''}${against.map((f) => ` --against ${shq(f)}`).join('')}`)
  if (!out || out.error) return out || { error: 'no result' }
  if (against.length && (!Array.isArray(out.diffs) || out.diffs.length !== against.length)) return { error: 'depscore.py arch-snapshot printed no difference for a saved fingerprint' }
  return out
}
/** The number of files diff `i` of a snapshot created, changed or deleted. */
function diffCount(snap, i) {
  const d = (snap && Array.isArray(snap.diffs) && snap.diffs[i]) || {}
  return (Number(d.created) || 0) + (Number(d.changed) || 0) + (Number(d.deleted) || 0)
}

const before = await constraintsSnapshot('constraints:before', 'Survey', true)
if (!before || before.error || !hasText(before.kept)) {
  const why = `section 2 of the architecture could not be fingerprinted and copied before the step: ${(before && before.error) || 'no copy was named'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}
const treeBefore = await treeSnapshot('tree:before', 'Survey', { save: TREE_START })
if (!treeBefore || treeBefore.error) {
  const why = `the architecture could not be fingerprinted before the step: ${(treeBefore && treeBefore.error) || 'no result'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}

let facts = await readFacts('resume:read-saved', 'Survey')
if (facts.error) {
  const why = `depscore.py arch-resume failed: ${facts.error}. The saved work of this step in ${WORK} could not be read; the step stops rather than redo finished work, and the saved files stay on disk for the next attempt (a file named above that is damaged can be deleted, and only its work is redone).`
  return {
    ok: false,
    stage: 'resume',
    headline: facts.exception ? `Architecture resume failed: ${facts.exception}` : `Architecture could not read its saved work in ${WORK}: ${facts.error}`,
    reason: why,
    error: why,
    // A Python exception is deterministic: every re-dispatch meets it again, so the owner is told.
    ...(facts.exception ? { deterministicFailure: true, requiredHumanActions: [`depscore.py arch-resume raised ${facts.exception} reading the saved architecture work in ${WORK}; every run of this Epic meets it again. Fix the cause (the script or the saved file it names), then re-run the Epic.`] } : {}),
    ...died('Survey'),
  }
}
const resumedFacts = facts

// ---------------------------------------------------------------- Survey
phase('Survey')
const savedSurvey = facts.survey && facts.survey.coverageSaved === true && facts.survey.saved === true && hasText(facts.survey.subject) ? facts.survey : null
let survey = savedSurvey ? { subject: savedSurvey.subject, capabilities: savedSurvey.capabilities } : null
if (survey) {
  log(`Survey: reused ${SURVEY_JSON}`)
} else {
  const repos = await run(
    `List every repository of this project: its name, the absolute path of its local checkout, its role (what it is for) and its lifecycle (for example active, deprecated, archived). Answer from your records and the live repositories. Change nothing.`,
    { label: 'survey:repositories', phase: 'Survey', agentType: 'agent-teams-workforce:polyrepo-steward', effort: 'low', schema: REPOS_SCHEMA }
  )
  if (!repos) return { ok: false, stage: 'survey', reason: 'the polyrepo-steward named no repositories', ...died('Survey') }
  const surveyed = await run(
    `You are the prd-reality-reconciler, SURVEYING for the architecture step. The architecture team designs from your survey; you design nothing. If the survey already exists, preserve its facts and subject and supplement only missing coverage evidence; do not discard prior work.

PRD: ${prdRef}

${ARCH_WHERE}

${INPUTS_RULE}

${COVERAGE_RULE}

THE REPOSITORIES, from the polyrepo-steward (use these facts as given; do not look for repositories yourself):
${JSON.stringify(repos.repositories, null, 2)}

THE OPEN BEADS are in the beads database of ${DS.repo}. Read them with \`bd\` run from that directory, read-only (\`bd list\`, \`bd show\`, \`bd search\`); write nothing to beads.

For EACH capability the PRD needs, report:
- \`effectiveViews\`: the absolute paths of the effective views (under ${ARC42}) that show it, found through the catalog;
- \`code\`: the code that implements it on \`main\`, as \`<repo>:<path>:<line>\`;
- \`openBeads\`: the ids of open Stories and Tasks of other Epics that plan work on it;
- \`openTargets\`: the paths of open targets under ${archPath}/target/ that change it;
- \`requirements\`: the PRD requirement headings it serves.
An empty list is an answer: say in \`notes\` where you looked.

Name the \`subject\` the target will describe: the feature, service, component or layer this PRD changes, named as the glossary and the repositories name it — never the PRD, the Epic, a bead id or a date — and say why in \`subjectReason\`. Give the name as it is written (\`Company Intelligence\` and \`company-intelligence\` are both fine): the run derives the \`target/<subject>/\` folder name from it (lower-case, every run of other characters one hyphen).
${PRD_RULE}
${BUSINESS_CONFLICT_RULE}
Write survey.md as the readable survey and survey.json as your structured result.${persistBrief([SURVEY_MD, SURVEY_JSON], 'the survey: survey.md as one Markdown document, and survey.json as your complete structured result, exactly as you return it')}`,
    { label: 'survey:reality', phase: 'Survey', agentType: 'prd-reality-reconciler', effort: 'medium', schema: SURVEY_SCHEMA }
  )
  if (!surveyed) return { ok: false, stage: 'survey', reason: 'the prd-reality-reconciler returned no survey', ...died('Survey') }
  if (!(await saveResult('survey:reality', 'Survey', SURVEY_JSON, surveyed))) {
    const why = `the survey the prd-reality-reconciler returned could not be saved to ${SURVEY_JSON}`
    return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
  }
  await recordFiles('survey:record', 'Survey', [SURVEY_MD])
  survey = { subject: surveyed.subject, capabilities: Array.isArray(surveyed.capabilities) ? surveyed.capabilities.length : 0 }
}
if (!savedSurvey) {
  facts = await readFacts('survey:coverage-facts', 'Survey')
  if (facts.error) return { ok: false, stage: 'survey', reason: facts.error }
}
/** Where the survey is; failures name the files, never carry the survey. */
const surveyPaths = { surveyPath: SURVEY_MD, surveyJsonPath: SURVEY_JSON }
// The subject as named; depscore.py arch-target derives the folder name every later step uses.
const subjectName = hasText(a.subject) ? a.subject.trim() : hasText(survey.subject) ? survey.subject.trim() : ''
/** Checks the draft with depscore.py arch-target --dry-run; the full report goes to TARGET_CHECK and only its summary comes back. Returns the summary or { error }. */
async function checkDraft(label, phaseName, subjectArg) {
  const out = await depscore(label, phaseName, `arch-target --draft ${shq(DRAFT)} --arch-root ${shq(archPath)} --subject ${shq(subjectArg)} --forbid ${shq(FORBID.join(','))} --dry-run --out ${shq(TARGET_CHECK)}`)
  if (!out || out.error) return out || { error: 'no result' }
  return out.summary && typeof out.summary === 'object' ? out.summary : { error: 'depscore.py arch-target printed no summary' }
}
const subjectCheck = await checkDraft('target:check-subject', 'Survey', subjectName || '-')
const subjectRefusals = subjectCheck && !subjectCheck.error ? listed(subjectCheck.subjectRefusals) : []
const subject = subjectCheck && !subjectCheck.error && hasText(subjectCheck.subject) ? subjectCheck.subject.trim() : ''
if (!subjectName || subjectRefusals.length || !subjectCheck || subjectCheck.error || !subject) {
  const why = !subjectName
    ? 'the survey named no subject for the target'
    : subjectRefusals.length
      ? `the target subject cannot name a target: ${subjectRefusals.join('; ')}`
      : `the target subject could not be checked: ${(subjectCheck && subjectCheck.error) || 'no folder name returned'}`
  return { ok: false, stage: 'survey', deterministicFailure: subjectRefusals.length > 0, reason: why, error: why, ...surveyPaths }
}
log(`Survey: subject ${subjectName} (folder target/${subject}/); ${Number(survey.capabilities) || 0} capabilit(ies)`)

// ---------------------------------------------------------------- Rounds
// The claim and finding ledger lives on disk: depscore.py arch-resume folds every saved round result
// into ledger.json and returns only the facts below. Sessions read the ledger by its path.
let lastRound = Number(facts.rounds.last) || 0
/** Every re-dispatch after a failed or empty result, with what changed in its input. */
const retries = []
/** Each finding id handed to a writer to answer: { agentType, round, clarified }. */
const asked = new Map()
let silentLast = []
/** The reviewers that check every design before a decision, with one cost reviewer; the pattern challenger provides targeted critique only when needed. */
const ON_DEMAND_REVIEWERS = ['architecture-pattern-challenger']
const REQUIRED_CHALLENGERS = Object.keys(ROSTER.reviewer).filter((r) => !ON_DEMAND_REVIEWERS.includes(r))
const ledgerFacts = () => facts.rounds
const writersSoFar = () => listed(ledgerFacts().writers)
const openFindings = () => (Array.isArray(ledgerFacts().openFindings) ? ledgerFacts().openFindings : []).filter((f) => f && hasText(f.id))
/** The number of claims without a reviewer verdict, by writer. */
const unreviewedByWriter = () => Object.entries(ledgerFacts().unreviewedClaims || {}).filter(([, k]) => Number(k) > 0)
const unreviewedCount = () => unreviewedByWriter().reduce((t, [, k]) => t + Number(k), 0)
const ledgerLine = () => `${Number(ledgerFacts().claims) || 0} claim(s), ${Number(ledgerFacts().findings) || 0} finding(s), ${openFindings().length} open, ${unreviewedCount()} claim(s) without a reviewer verdict`
if (lastRound) log(`Rounds: resumed after round ${lastRound} — ${ledgerLine()}`)

/** Returns what still stands between the draft and a decision. */
async function decisionGaps(label) {
  const gaps = []
  for (const id of listed(facts.repairs && facts.repairs.open)) gaps.push(`repair ${id} requires its bounded correction in ${LEDGER_JSON}`)
  for (const id of listed(facts.repairs && facts.repairs.checksNeeded)) gaps.push(`repair ${id} awaits independent verification of the current artifacts in ${LEDGER_JSON}`)
  if (hasGaps(facts)) gaps.push(`${facts.coverage && Number.isInteger(facts.coverage.gapCount) ? facts.coverage.gapCount : 'an unknown number of'} coverage gap(s): each is listed under result.coverage.gaps in ${facts.relayFile}, with its row in ${LEDGER_JSON}`)
  const proposed = writersSoFar().some((w) => roleOf(w) === 'proposer')
  if (!proposed) gaps.push('no proposer has written the target yet')
  for (const f of openFindings()) gaps.push(`finding ${f.id} (its verdict and file are in ${LEDGER_JSON}) ${f.answered ? 'awaits independent resolution of its answer' : 'needs a bounded evidenced repair'}; owner ${f.owner || 'not known — assign it to a writer'}`)
  for (const [w, k] of unreviewedByWriter()) gaps.push(`${k} claim(s) by ${w} have no reviewer verdict (the claims by ${w} in ${LEDGER_JSON} whose \`verdicts\` list is empty)`)
  for (const w of listed(ledgerFacts().proposersWithoutClaims)) gaps.push(`proposer ${w} stated no claims: a design with no claims cannot be reviewed; it states the claims a reviewer checks`)
  if (proposed) {
    const reviewed = listed(ledgerFacts().reviewers)
    for (const r of REQUIRED_CHALLENGERS) if (!reviewed.includes(r)) gaps.push(`reviewer ${r} has not reviewed the design`)
    if (!Object.keys(ROSTER.cost).some((r) => reviewed.includes(r))) gaps.push('no cost reviewer has reviewed the design')
  }
  const check = await checkDraft(label, 'Rounds', subject)
  if (!check || check.error) gaps.push(`the draft could not be checked: ${(check && check.error) || 'no result'}`)
  else for (const r of listed(check.refusals)) gaps.push(`draft: ${r}`)
  return gaps
}

/** The saved decision's facts: { verdict, round, returnTo: [agent], ownerConcerns: count, ownerConcernKinds, ownerOnly }. */
const savedDecision = facts.decision && typeof facts.decision === 'object' && hasText(facts.decision.verdict) ? facts.decision : null
const repairsPending = (value) => !!(listed(value.repairs && value.repairs.open).length || listed(value.repairs && value.repairs.checksNeeded).length)
const savedCoverageValid = !!(!repairsPending(facts) && savedDecision && !facts.rounds.pendingPlan && !openFindings().length && !unreviewedCount() && !hasGaps(facts) && savedDecision.coverageRevision === facts.coverage.revision)
let decision = savedDecision && savedDecision.verdict === 'approve' && savedCoverageValid ? savedDecision : null
// Legacy approval gets one bounded supplemental round, retaining its prior work.
const roundLimit = MAX_ROUNDS + (savedDecision && savedDecision.verdict === 'approve' && (!savedDecision.coverageRevision || resumedFacts.contractVersion !== 2) ? 1 : 0)
/** Returns the proposers a decision returned the target to, each { agentType }; what is missing is in the decision file they read. */
const returnedTo = (dec) =>
  (dec && Array.isArray(dec.returnTo) ? dec.returnTo : [])
    .map((r) => (typeof r === 'string' ? r : r && r.agentType))
    .filter((r) => hasText(r) && roleOf(r.trim().replace(AGENT_PREFIX, '')) === 'proposer')
    .map((r) => ({ agentType: r.trim().replace(AGENT_PREFIX, '') }))
let forced = savedDecision && savedDecision.verdict === 'return' && !(lastRound > (savedDecision.round || 0)) ? returnedTo(savedDecision) : []
let rejected = []
let pendingGaps = []

/** Returns the owner-concern result that holds the Epic for the owner. A decision read back from disk carries only the count and kinds; the owner reads the concerns in the decision file. */
function ownerConcern(dec) {
  const concerns = Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns.filter((c) => c && hasText(c.concern)) : null
  const count = concerns ? concerns.length : Number(dec.ownerConcerns) || 0
  return {
    ok: false,
    stage: 'owner-concern',
    reason: `the architecture-decider raised ${count} owner concern(s) on ${subject}`,
    ...(concerns ? { ownerConcerns: concerns } : { ownerConcernKinds: listed(dec.ownerConcernKinds) }),
    requiredHumanActions: [
      ...(concerns
        ? concerns.map((c) => `${c.kind === 'architecture-conflict' ? 'CONTRADICTION IN THE ARCHITECTURE' : 'CONFLICTING BUSINESS REQUIREMENTS'} on ${subject}: ${c.concern} — evidence: ${c.evidence}`)
        : [`The architecture-decider raised ${count} owner concern(s) on ${subject} (${listed(dec.ownerConcernKinds).join(', ')}): read them in ${DECISION_MD}.`]),
      `Once the PRD or the architecture says which side holds, delete ${DECISION_JSON}: while it holds these concerns, every run of the architecture step holds the Epic again.`,
    ],
    decision: dec,
    decisionPath: DECISION_MD,
    subject,
    ...surveyPaths,
  }
}
/** True when the last decision escalated issues the team resolves itself; the coordinator reads them in the decision file. */
let teamNotes = false
/** True when every owner concern of a decision is one of the two cases that reach the owner: irreconcilable business requirements, or an architecture that contradicts itself where common sense cannot settle it. */
const businessOnly = (dec) => {
  if (typeof dec.ownerOnly === 'boolean') return dec.ownerOnly
  const concerns = (Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns : []).filter((c) => c && hasText(c.concern))
  return concerns.length > 0 && concerns.every((c) => OWNER_CONCERN_KINDS.includes(c.kind))
}
if (savedDecision && savedDecision.verdict === 'owner-concern') {
  if (businessOnly(savedDecision)) {
    log('Decide: the saved decision holds conflicting business requirements; the Epic is held again')
    return ownerConcern(savedDecision)
  }
  log('Decide: the saved decision escalated what the team decides itself; it is set aside and the team resolves it')
  teamNotes = Number(savedDecision.ownerConcerns) > 0
}

/** Returns the prompt for one writer or reviewer dispatch. */
function dispatchPrompt(n, d, file) {
  const planEntry = `the dispatch with \`seq\` ${d.seq} (${d.agentType}) in the round ${n} entry of \`roundPlans\` in ${LEDGER_JSON}`
  const taskLine = hasText(d.task)
    ? `YOUR TASK THIS ROUND, from the coordinator: ${d.task}`
    : `YOUR TASK THIS ROUND, from the coordinator, is the \`task\` of ${planEntry}: read it there first, with that dispatch's \`files\` and \`answers\`.`
  const answersBlock = d.answers === null
    ? `\nFINDINGS YOU ANSWER THIS ROUND are the \`answers\` of ${planEntry} (none when that list is empty). Read each in the \`findings\` list of the ledger ${LEDGER_JSON} (its verdict, the claim, the file and the reviewer's evidence), and answer every one in \`answers\` by its id: \`fixed\` (name the change you made) or \`disputed\` (with your evidence).\n`
    : d.answers.length
    ? `\nFINDINGS YOU ANSWER THIS ROUND: ${d.answers.join(', ')}. Read each in the \`findings\` list of the ledger ${LEDGER_JSON} (its verdict, the claim, the file and the reviewer's evidence), and answer every one in \`answers\` by its id: \`fixed\` (name the change you made) or \`disputed\` (with your evidence).\n`
    : ''
  const shared = `PRD: ${prdRef}

${PRD_RULE}

${ARCH_WHERE}

${INPUTS_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}

THE SURVEY is ${SURVEY_MD} (readable) and ${SURVEY_JSON} (structured): read it first. The target's subject is ${subjectName}; its folder is \`target/${subject}/\`.
EARLIER RESULTS of this step are in ${ROUNDS_DIR}; read the ones that touch your work. Complete the assigned acceptance requirements, save the complete structured result to the specified file, and then call StructuredOutput with that same result. Preserve valid prior work and its evidence; a resumed dispatch completes its missing work in this round.`
  if (WRITER_ROLES.includes(d.role)) {
    const work = d.role === 'proposer'
      ? `Consolidate the retained target across all affected concerns, using your expertise (${ROSTER.proposer[d.agentType]}), existing source evidence and the settled mechanism. Revise the existing design; do not reopen settled choices or create a proposal per concern. Work from the effective version, at every scope the change reaches (system, domain, service, component, concept), as views of the types in ${MENU}: diagrams and prose. Write the target views and the delta views for it into the draft. A design that departs from an established pattern states its reason and evidence in the view's prose.`
      : `Draw the views your task names (${ROSTER.diagram[d.agentType]}) into the draft, from the design the proposers wrote there. Depict nothing that design does not contain.`
    return `You are the ${d.agentType}, a writer on the architecture team for this PRD, round ${n}. ${work}

${taskLine}
${d.files === null ? `THE DRAFT FILES YOU OWN THIS ROUND are the \`files\` of ${planEntry}, relative to ${DRAFT} (write only these; other sessions may be writing the rest). When that list is empty, change no view another writer owns, and name every file you write in \`files\`.` : d.files.length ? `THE DRAFT FILES YOU OWN THIS ROUND, relative to ${DRAFT} (write only these; other sessions may be writing the rest):\n${d.files.map((f) => `- ${f}`).join('\n')}` : 'You were named no draft files this round: change no view another writer owns, and name every file you write in `files`.'}
${answersBlock}
${shared}

${DRAFT_RULES}

Read \`repairRequests\` in ${LEDGER_JSON}. For each open repair assigned to you or transferred to the retained lead, complete its missing diligence and return \`repairAnswers\` with its exact repairId and a response identifying the changed views/evidence. Retain resolved repairs; do not redo them.

Use claimId="" for a new claim or the existing ledger id for an explicit revision. Keep unchanged ids; supersedes lists only deliberately replaced claims you own. Cite evidenceRefs and do not silently discard findings. A writer answer proposes a fix/dispute; independent resolution is still required. Return in \`files\` every draft file you wrote, relative to ${DRAFT}. Return in \`claims\` every claim your views make that a reviewer must check — about AWS (cite the documentation page you read), the code (cite repository, path and line on \`main\`), or the architecture (cite the view path and heading) — each with the draft file it is in. A design with no claims cannot be reviewed and cannot be approved: state every claim a reviewer must check. ${BUSINESS_CONFLICT_RULE}${persistBrief([file], 'your complete structured result, exactly as you return it, as ONE JSON object')}`
  }
  return `You are the ${d.agentType}, a ${d.role === 'cost' ? 'cost reviewer' : 'reviewer'} on the architecture team for this PRD, round ${n}: ${ROSTER[d.role][d.agentType]}.

${taskLine}

THE DRAFT TARGET is ${DRAFT} (target views in the arc42 section layout, the change alone in \`delta/\`). Read it; write nothing in it and nothing in ${archPath}.

${shared}

THE LEDGER is ${LEDGER_JSON}: every claim the writers stated (\`claims\`, each with its \`id\`, writer, draft file, citation and the \`verdicts\` given so far) and every finding. Read it; write nothing in it.
YOUR ASSIGNED CLAIM REVISIONS are the \`assignedClaims\` (each an id and revision) of ${planEntry}. Check exactly these claims against their citations with independent evidence and copy id/revision into claimId/claimRevision. Do not repeat unrelated verified claims. When none are assigned, answer only your coordinator's bounded domain question and affected dependencies; do not start a blanket audit.
Read \`repairRequests\` in ${LEDGER_JSON}. Independently verify answered repairs within your assigned scope against the current artifacts; return \`repairChecks\` with repairId, the current revision, verified/revise, concrete evidence and files: the draft-relative or absolute evidence/contract file paths you actually inspected for that repair. A verified repair must bind its relevant files, including affected dependencies; unrelated file edits will not invalidate that acceptance. A revise check may use an empty files list. Do not repeat resolved repair requests without identifying new evidence of a current defect.
Return verified, unsupported or wrong with evidence. Check coverage IDs named in your task at their current ledger revisions. For answered findings within your assigned scope, return resolutions with findingId, the ledger finding's current resolutionRevision as revision, accepted/rejected and independent evidence: accept fixed only after verifying the changed evidence/view, and disputed only when evidence refutes the original finding. An unsupported assertion never resolves a finding. A new concrete uncovered problem uses empty claimId/claimRevision and names its writer as owner.${d.role === 'cost' ? ' State your estimates, with the unit math, in `estimates`; a cost the design does not support is a finding like any other.' : ''}${persistBrief([file], 'your complete structured result, exactly as you return it, as ONE JSON object')}`
}

/** Groups writers so no two in one wave own the same draft file; a writer naming no file (or whose files are known only to its plan entry) runs alone. */
function writerWaves(list) {
  const waves = []
  for (const d of list) {
    const files = d.files || []
    const wave = files.length ? waves.find((w) => !w.solo && files.every((f) => !w.files.has(f))) : null
    if (wave) {
      wave.items.push(d)
      files.forEach((f) => wave.files.add(f))
    } else {
      waves.push({ solo: !files.length, items: [d], files: new Set(files) })
    }
  }
  return waves
}

const cleanFile = (f) => String(f || '').trim().replace(/^\/+/, '')
const agentName = (x) => String(x || '').trim().replace(AGENT_PREFIX, '')
/** The plan's overlap entries that state a reason, normalized as they are saved. */
const planOverlaps = (plan) =>
  (Array.isArray(plan && plan.overlaps) ? plan.overlaps : [])
    .filter((o) => o && hasText(o.reason))
    .map((o) => ({ files: listed(o.files).map(cleanFile), claimIds: listed(o.claimIds), agentTypes: listed(o.agentTypes).map(agentName), reason: o.reason.trim() }))
/**
 * Returns, for each claim id or draft file that two or more review dispatches of the plan share,
 * a refusal when no `overlaps` entry with a reason names it (and, when the entry names agentTypes,
 * every reviewer sharing it). An empty list means the plan states a reason for every overlap.
 */
function unjustifiedOverlaps(plan) {
  const holders = new Map()
  for (const d of Array.isArray(plan && plan.dispatches) ? plan.dispatches : []) {
    const name = agentName(d && d.agentType)
    if (!REVIEW_ROLES.includes(roleOf(name)) || roleOf(name) !== d.role) continue
    const items = [...listed(d.claimIds).map((i) => `claim ${i}`), ...listed(d.claimFiles).map(cleanFile).filter(Boolean).map((f) => `draft file ${f}`)]
    for (const item of items) {
      const names = holders.get(item) || new Set()
      names.add(name)
      holders.set(item, names)
    }
  }
  const entries = planOverlaps(plan)
  const refusals = []
  for (const [item, names] of holders) {
    if (names.size < 2) continue
    const sharing = [...names]
    const covered = entries.some((o) =>
      (!o.agentTypes.length || sharing.every((x) => o.agentTypes.includes(x))) &&
      (item.startsWith('claim ') ? o.claimIds.includes(item.slice(6)) : o.files.includes(item.slice(11))))
    if (!covered) refusals.push(`${item} is assigned to ${sharing.join(', ')} and no \`overlaps\` entry names it with a reason`)
  }
  return refusals
}
const MAX_PLAN_FIXES = 2

/** Validates the coordinator's dispatches and adds those the ledger requires; returns { dispatches, rejected, stuck }. */
function settleDispatches(plan, n) {
  const out = []
  const bad = []
  for (const d of Array.isArray(plan.dispatches) ? plan.dispatches : []) {
    const name = d && hasText(d.agentType) ? d.agentType.trim().replace(AGENT_PREFIX, '') : ''
    const role = roleOf(name)
    if (!role || role !== d.role) {
      bad.push(`${name || '(no agent)'} as ${d && d.role}: not that role's roster`)
      continue
    }
    const files = WRITER_ROLES.includes(role) ? listed(d.files).map(cleanFile) : []
    const badFile = files.find((f) => !f || f.split('/').includes('..') || f.split('/').includes('02-architecture-constraints'))
    if (badFile !== undefined) {
      bad.push(`${name}: draft file ${JSON.stringify(badFile)} is outside the draft or in section 2`)
      continue
    }
    const answers = WRITER_ROLES.includes(role) ? listed(d.answers) : []
    for (const id of answers) {
      const f = openFindings().find((x) => x.id === id && !x.owner)
      if (f) {
        f.owner = name
        assigned.set(id, name)
      }
    }
    const same = out.find((x) => x.agentType === name)
    if (same) {
      same.task = `${same.task}\n${d.task}`
      same.files = [...new Set([...same.files, ...files])]
      same.answers = [...new Set([...same.answers, ...answers])]
      same.claimIds = [...new Set([...same.claimIds, ...listed(d.claimIds)])]
      same.claimFiles = [...new Set([...same.claimFiles, ...listed(d.claimFiles).map(cleanFile)])]
    } else {
      out.push({ agentType: name, role, task: String(d.task || ''), files, answers, claimIds: listed(d.claimIds), claimFiles: listed(d.claimFiles).map(cleanFile) })
    }
  }
  const legacyMissing = listed(ledgerFacts().legacyProposersWithoutClaims)
  if (legacyMissing.length) {
    const lead = facts.proposalTeam.lead
    const task = `Consolidate the retained drafts and results from ${legacyMissing.join(', ')}: they stated no reviewable claims. Inspect their existing work and its evidence, repair gaps, and state the consolidated claims for independent review; do not merely repeat earlier claims.`
    const same = out.find((d) => d.agentType === lead)
    if (same) same.task += `\n${task}`
    else out.push({ agentType: lead, role: 'proposer', task, files: [], answers: [] })
  }
  for (const d of out) d.answers = d.answers.filter((id) => openFindings().some((f) => f.id === id && f.owner === d.agentType))
  for (const r of forced) {
    const role = roleOf(r.agentType)
    if (!role || !WRITER_ROLES.includes(role)) continue
    const recipient = role === 'proposer' ? facts.proposalTeam.lead : r.agentType
    const same = out.find((x) => x.agentType === recipient)
    const task = `The architecture-decider returned the target to you. Read \`returnTo\` in ${DECISION_JSON} (the decision in full is ${DECISION_MD}) for the due diligence it names as missing from your design, and supply it.`
    if (same) same.task = `${same.task}\n${task}`
    else out.push({ agentType: recipient, role, task, files: [], answers: [] })
    retries.push({ step: `round${n}:${r.agentType}`, whatChanged: `the architecture-decider returned the target naming missing due diligence (in ${DECISION_JSON})` })
  }
  for (const f of openFindings()) {
    if (f.answered || !f.owner || out.some((x) => x.agentType === f.owner && x.answers.includes(f.id))) continue
    const same = out.find((x) => x.agentType === f.owner)
    if (same) same.answers.push(f.id)
    else out.push({ agentType: f.owner, role: roleOf(f.owner), task: 'Answer the findings named below.', files: [], answers: [f.id] })
  }
  // A finding handed back to the writer that left it unanswered is re-sent once, with that named in its
  // task; still unanswered after that, it is not sent a third time.
  const stuck = []
  for (const d of out) {
    const again = d.answers.filter((id) => asked.has(id) && asked.get(id).agentType === d.agentType)
    if (!again.length) continue
    const repeated = again.filter((id) => asked.get(id).clarified)
    if (repeated.length) {
      stuck.push(`${d.agentType}: ${repeated.join(', ')}`)
      continue
    }
    const prev = Math.max(...again.map((id) => asked.get(id).round))
    const result = silentLast.includes(d.agentType) ? 'never came back' : 'answered none of them'
    d.task = `${d.task}\nROUND ${prev} HANDED YOU finding(s) ${again.join(', ')}, and your result ${result}. Answer each one in \`answers\` this round, as \`fixed\` or \`disputed\`.`
    d.clarified = again
    retries.push({ step: `round${n}:${d.agentType}`, findings: again, whatChanged: `round ${n} tells ${d.agentType} that its round ${prev} result ${result} for finding(s) ${again.join(', ')}` })
  }
  const proposers = out.filter((d) => d.role === 'proposer')
  const allowed = [facts.proposalTeam.lead, facts.proposalTeam.second].filter(Boolean)
  if (proposers.length > 2 || proposers.some((d) => !allowed.includes(d.agentType))) {
    return { dispatches: [], rejected: [...bad, 'proposal budget: only the retained lead and justified second may write proposals'], stuck, budgetError: true }
  }
  return { dispatches: out, rejected: bad, stuck }
}

/**
 * Runs one round's dispatches: writers in waves of disjoint files, then reviewers together. The
 * ledger is folded again from the saved results after the writers, so the reviewers read this
 * round's claims, and after the reviewers. Returns { silent } (the dispatches with no result, or
 * whose result was not saved) or { error } when the saved results could not be read.
 */
async function runRound(n, dispatches) {
  // Last boundary before any agent call; automatic returns and legacy owners cannot bypass it.
  const proposers = dispatches.filter((d) => d.role === 'proposer' && !d.complete)
  const team = facts.proposalTeam || {}
  if (new Set(proposers.map((d) => d.agentType)).size > 2 || proposers.some((d) => ![team.lead, team.second].filter(Boolean).includes(d.agentType))) {
    return { error: 'proposal budget exceeded; saved work retained, no round agents dispatched' }
  }
  const writing = dispatches.filter((d) => WRITER_ROLES.includes(d.role))
  const reviewing = dispatches.filter((d) => REVIEW_ROLES.includes(d.role))
  const held = [...writing, ...reviewing].map((d, i) => ({ ...d, seq: d.seq || i + 1 }))
  let ordered = held.map((d) => ({ ...d, file: resultFile(n, d) }))
  // A dispatch's result counts once the script has made its result file hold exactly what it returned.
  const go = (d) => async () => {
    const label = `round${n}:${d.role}:${d.agentType}`
    const got = await run(dispatchPrompt(n, d, d.file), {
      label,
      phase: 'Rounds',
      agentType: dispatchName(d.agentType),
      effort: d.role === 'proposer' ? 'high' : 'medium',
      schema: WRITER_ROLES.includes(d.role) ? WRITER_SCHEMA : REVIEW_SCHEMA,
    })
    return got && (await saveResult(label, 'Rounds', d.file, got)) ? got : null
  }
  const results = new Map()
  let writersAttempted = false
  for (const wave of writerWaves(ordered.filter((d) => WRITER_ROLES.includes(d.role) && !d.complete))) {
    writersAttempted = true
    const got = await parallel(wave.items.map(go))
    wave.items.forEach((d, i) => results.set(d.seq, got[i]))
    if (dispatchInterruption) return { silent: wave.items.filter((d, i) => !got[i]).map(d => d.agentType) }
  }
  if (facts.rounds.pendingPlan) ordered = planDispatches(facts.rounds.pendingPlan)
  let reviewers = ordered.filter((d) => REVIEW_ROLES.includes(d.role) && !d.complete)
  if (reviewers.length) {
    if (writersAttempted) {
      const mid = await readFacts(`round${n}:ledger-writers`, 'Rounds')
      if (mid.error) return { error: mid.error, exception: mid.exception }
      facts = mid
      if (mid.rounds.pendingPlan && mid.rounds.pendingPlan.dispatches.some(d => WRITER_ROLES.includes(d.role) && !d.complete)) return { silent: mid.rounds.pendingPlan.dispatches.filter(d => WRITER_ROLES.includes(d.role) && !d.complete).map(d => d.agentType) }
      ordered = mid.rounds.pendingPlan ? planDispatches(mid.rounds.pendingPlan) : ordered
      reviewers = ordered.filter((d) => REVIEW_ROLES.includes(d.role) && !d.complete)
    }
    const got = await parallel(reviewers.map(go))
    reviewers.forEach((d, i) => results.set(d.seq, got[i]))
  }
  const after = await readFacts(`round${n}:ledger`, 'Rounds')
  if (after.error) return { error: after.error, exception: after.exception }
  facts = after
  if (facts.rounds.pendingPlan) {
    if (facts.rounds.pendingPlan.round !== n) return { error: `round ${n} finished dispatching but saved round ${facts.rounds.pendingPlan.round} is pending; saved work retained` }
    return { silent: facts.rounds.pendingPlan.dispatches.filter((d) => !d.complete).map((d) => d.agentType) }
  }
  const savedKeys = listed(facts.rounds.saved)
  const unsaved = ordered.filter((d) => results.get(d.seq) && !savedKeys.includes(`r${n}-${d.seq}`))
  if (unsaved.length) log(`Round ${n}: ${unsaved.map((d) => d.agentType).join(', ')} returned a result but did not save it to its result file; it counts as no result`)
  return { silent: ordered.filter((d) => !savedKeys.includes(`r${n}-${d.seq}`)).map((d) => d.agentType) }
}

/** Runs the decider over the artifacts; returns its decision or null. */
async function decide(n, correction = '') {
  phase('Decide')
  const dec = await run(
    `You are the architecture-decider. Decide whether the draft target below is approved. You produced none of it, and you decide from the artifacts alone: read them.
${correction}

ARTIFACTS:
- the PRD: ${hasText(prd.path) ? prd.path : '(inline — see the survey)'}
- the survey: ${SURVEY_MD} and ${SURVEY_JSON}
- every result of every round: the files in ${ROUNDS_DIR}, and the claim and finding ledger folded from them: ${LEDGER_JSON}
- the draft target and its delta: ${DRAFT}
- the effective version, with the owner's constraints in section 2: ${ARC42}; open targets: ${archPath}/target/

${PRD_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}
Read \`repairRequests\` in ${LEDGER_JSON}, including prior answers and independent checks. Do not reissue resolved repairs from an older decision; a new defect must identify current evidence and the concrete remaining violation.
Read all coverage rows and independent checks in ${LEDGER_JSON}; check completeness against the MODEL, not only existing catalog hits. Set coverageRevision to the ledger's coverageRevision. Approval requires resolved relevant obligations with independent current-content evidence; never approve from an aggregate boolean.

The team has designed, challenged and settled this target in its rounds, led by the coordinator. You are not its lead: you approve its result, and you choose only where the team left competing solutions it could not settle.

CHECK THAT THE DUE DILIGENCE IS PRESENT, item by item in \`diligence\`: every claim reviewed with evidence and every finding answered; the target shows every changed element at every scope where the effective version shows it; the delta shows the change; the owner's constraints in section 2 are honoured; the open targets that show the same elements were read and are not contradicted; a departure from an established pattern states its reason and evidence.

COMPETING SOLUTIONS: where findings stand disputed, or a reviewer's alternative was argued with evidence and not adopted, choose between them in \`choices\`: what was in dispute, the option you chose, and why, from the evidence in the artifacts and the product's priorities (the seeker's privacy and data protection first). A choice is part of an approval, not a reason to escalate.

VERDICT:
- \`approve\` when the diligence is present, with every choice you made in \`choices\`.
- \`return\` only when a proposer's due diligence is missing: name each one in \`returnTo\` (one of ${Object.keys(ROSTER.proposer).join(', ')}) with exactly what is missing. A technical value the PRD leaves open is not missing diligence when the team chose it with a reason.
- \`owner-concern\` is the last resort, for two cases only, each in \`ownerConcerns\` with its evidence: kind \`business-conflict\`, two BUSINESS requirements of the PRD that no design whatsoever could satisfy together, shown by the team's own analysis; or kind \`architecture-conflict\`, the architecture contradicting itself where common sense cannot settle which side holds — owner's constraints in section 2 that contradict each other or that no design can meet together with the PRD, or effective views that make competing statements with nothing to show which is current. Never escalate a "how" in the PRD, an open technical value, a security, privacy, cost or best-practice question (the team designs those), or a difference from the effective version.
Set \`round\` to ${n}.

Write ${DECISION_MD} (your decision as one readable Markdown document) and ${DECISION_JSON} (your complete structured result, exactly as you return it, as ONE JSON object) with the Write tool, replacing each if it exists (Read it first if the Write tool asks). Write no other file.`,
    { label: `decide:round${n}`, phase: 'Decide', agentType: 'agent-teams-workforce:architecture-decider', effort: 'high', schema: DECISION_SCHEMA }
  )
  if (!dec) return dec
  if (!(await saveResult(`decide:round${n}`, 'Decide', DECISION_JSON, dec))) return null
  await recordFiles('decide:record', 'Decide', [DECISION_MD])
  return dec
}

phase('Rounds')
let staleDecisionCorrection = ''
let staleDecisionCorrected = false
let ready = !!(savedDecision && savedDecision.verdict === 'approve') || facts.rounds.readyForDecision === true
while (!decision) {
  if (ready) {
    pendingGaps = await decisionGaps(`rounds:gaps-${lastRound}`)
    if (!pendingGaps.length) {
      const dec = await decide(lastRound, staleDecisionCorrection)
      if (!dec) return { ok: false, stage: 'decide', reason: 'the architecture-decider returned nothing', ...died('Decide'), subject, ...surveyPaths }
      const concerns = (Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns : []).filter((c) => c && hasText(c.concern))
      if (dec.verdict === 'owner-concern' || concerns.length) {
        if (!concerns.length) return { ok: false, stage: 'decide', reason: 'the architecture-decider raised an owner concern and named none', decision: dec, subject }
        if (businessOnly(dec)) return ownerConcern(dec)
        teamNotes = true
        log(`Decide: ${concerns.length} issue(s) escalated that the team decides itself; they go back to the team`)
        phase('Rounds')
        ready = false
        continue
      }
      if (dec.verdict === 'approve') {
        const approvedFacts = await readFacts('decide:coverage-check', 'Decide')
        if (approvedFacts.error || !approvedFacts.rounds || approvedFacts.rounds.pendingPlan || (approvedFacts.rounds.openFindings || []).length || Object.values(approvedFacts.rounds.unreviewedClaims || {}).some(k => k > 0) || hasGaps(approvedFacts) || repairsPending(approvedFacts) || dec.coverageRevision !== approvedFacts.coverage.revision || !approvedFacts.decision || approvedFacts.decision.coverageRevision !== dec.coverageRevision) {
          return { ok: false, stage: 'decide', reason: 'approval lacks saved independent coverage evidence for the current views; saved work retained', subject }
        }
        facts = approvedFacts
        decision = dec
        break
      }
      const repairFacts = await readFacts('decide:repair-status', 'Decide')
      if (repairFacts.error) return { ok: false, stage: 'decide', reason: repairFacts.error, subject }
      facts = repairFacts
      forced = returnedTo(facts.decision || {})
      if (!forced.length && !repairsPending(facts)) {
        if (staleDecisionCorrected) return { ok: false, stage: 'decide', deterministicFailure: true, reason: `the architecture-decider repeated a return with no unresolved repair after correction: ${JSON.stringify(dec.returnTo || [])}; current repair evidence is in ${LEDGER_JSON}; saved work retained, no writer redispatched`, decision: dec, subject }
        staleDecisionCorrected = true
        staleDecisionCorrection = `YOUR LAST RETURN WAS NOT ACTIONABLE (${JSON.stringify(dec.returnTo || [])}): the saved ledger has no unresolved repair request. Read repairRequests, their answers and independent current-revision checks in ${LEDGER_JSON}. Do not repeat a resolved request. Decide again from the current artifacts: approve when the existing acceptance requirements are met, or identify a concrete new defect with current evidence. Nothing has been sent back to a writer.`
        retries.push({ step: `decide:round${lastRound}`, whatChanged: 'the decision was told its return contained no unresolved repair and directed to the saved independent resolution evidence' })
        log(`Decide: stale return suppressed; asking the decider once to consider saved resolution evidence`)
        continue
      }
      log(`Decide: ${forced.length ? `returned to ${forced.map((f) => f.agentType).join(', ')}` : 'answered repairs require independent verification; no writer redispatch'}`)
      phase('Rounds')
    }
    ready = false
  }
  if (!facts.rounds.pendingPlan && !facts.rounds.resumeRound && lastRound >= roundLimit) {
    const gaps = pendingGaps.length ? pendingGaps : await decisionGaps('rounds:gaps-final')
    const why = `${roundLimit} round(s) ran and the target is not ready for a decision: ${gaps.join('; ') || 'the coordinator never declared it ready'}`
    log(`Rounds: ${why}`)
    return { ok: false, stage: 'rounds', reason: why, error: why, gaps, subject, ...surveyPaths, ...died('Rounds') }
  }
  const pendingPlan = facts.rounds.pendingPlan
  const n = pendingPlan ? pendingPlan.round : (facts.rounds.resumeRound || lastRound + 1)
  if (!pendingGaps.length && n > 1) pendingGaps = await decisionGaps(`rounds:gaps-${n - 1}`)
  const coordinatorBrief = `You are the architecture-decision-workflow-coordinator. Name the dispatches for round ${n} of at most ${roundLimit}; the script runs them. You read and route; you design, review and decide nothing, write nothing, and dispatch nothing yourself.

PRD: ${prdRef}
THE SURVEY: ${SURVEY_MD} and ${SURVEY_JSON}. The target's subject is ${subjectName}; its folder is \`target/${subject}/\`.
THE DRAFT TARGET: ${DRAFT} (arc42 section layout; \`delta/\` holds the change alone).
EARLIER RESULTS: ${ROUNDS_DIR}.
THE ARCHITECTURE: ${archPath} (\`arc42/\` effective; \`target/\` open targets).

THE ROSTER (role: agent — what it covers):
${rosterText}

THE LEDGER is ${LEDGER_JSON}: every claim with its reviewer verdicts, and every finding with its owner and answer, folded from the saved results. Read it. So far: ${ledgerLine()}.

WHAT STANDS BETWEEN THE DRAFT AND A DECISION:
${pendingGaps.length ? pendingGaps.map((g) => `- ${g}`).join('\n') : n === 1 ? '- nothing is written yet' : '- nothing'}
${teamNotes ? `\nISSUES FOR THE TEAM TO RESOLVE IN ITS DESIGN were raised at the decision: they are the \`ownerConcerns\` in ${DECISION_JSON} (readable in ${DECISION_MD}). Read them and route each to the writers it concerns, and to reviewers.\n` : ''}${forced.length ? `\nTHE ARCHITECTURE-DECIDER RETURNED THE TARGET to: ${forced.map((f) => f.agentType).join(', ')}; what each is missing is in \`returnTo\` of ${DECISION_JSON}. The retained lead consolidates this missing diligence; do not reinstate legacy specialist fanout.` : ''}${rejected.length ? `\nDISPATCHES REFUSED LAST ROUND: ${rejected.join('; ')}` : ''}${silentLast.length ? `\nDISPATCHES THAT RETURNED NOTHING LAST ROUND: ${silentLast.join(', ')}` : ''}

${PRD_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}
Assign coverage ids explicitly in each writer/reviewer task. Coverage gaps in the ledger are work to route, including absent views; do not restart unrelated completed design.

YOU LEAD THE TEAM to a consensus architecture. The architecture-decider is not part of the rounds: it sees the result only after the team has designed, challenged and settled it.

HOW TO ROUTE:
- Return proposalTeam: lead, second, unresolvedIssue, evidence, whySecond (empty strings for the optional second fields). Default one lead for the entire architecture effort, consolidating all concerns. Never more than two proposer identities across rounds. Retain the saved team (lead ${(facts.proposalTeam && facts.proposalTeam.lead) || 'none yet'}${facts.proposalTeam && facts.proposalTeam.second ? `, second ${facts.proposalTeam.second}` : ''}; the whole saved team is \`proposalTeam\` in ${LEDGER_JSON}). A second is exceptional: name the specific unresolved issue, its source/claim/finding evidence, and why the lead cannot resolve it alone; merely touching another concern is not justification. Once selected, identities cannot be replaced; later rounds revise their retained work. A PRD already served needs only a no-change delta.
- Do not split proposals among diagram authors, reviewers or renamed specialists. Diagram authors depict settled design only; reviewers critique without writing competing proposals. Reuse all legacy results as input to the lead, not instructions to redispatch their authors.
- Every design is reviewed before a decision by ${REQUIRED_CHALLENGERS.join(', ')} and by a cost reviewer; the list below names any that have not yet run.
- Dispatch ${ON_DEMAND_REVIEWERS.join(', ')} only for targeted critique of a concrete unresolved weakness; it does not create a competing design or add a proposer.
- When a competing alternative is proposed or a writer disputes a finding, route it back to the writers concerned so the team converges on one design; leave two designs standing only when the team has argued both with evidence and still disagrees.
- Give each writer dispatch the draft files it owns this round, relative to the draft folder; two writers in one round never own the same file.
- Give reviewers claimIds for existing claims and claimFiles for exact draft-relative files whose NEW/revised claims they will check after writers finish. Match file responsibility to reviewer expertise. Assigning the same claimId or claimFile to two or more reviewers is an overlap, and an overlap is one decision you make: state it once in \`overlaps\`, as one entry naming the shared \`files\` and \`claimIds\`, the reviewer \`agentTypes\` that share them, and the one \`reason\`. The reviewers' dispatches carry no reason. The script refuses a plan with an overlap no entry names, and sends it back to you; return \`overlaps: []\` when no two reviewers share anything. Unmatched claims remain gaps for the next normal round; no assignment-only agent pass. Keep each required reviewer's task a bounded domain question even with no claims.
- Every claim gets a reviewer verdict: dispatch reviewers for the claims not yet reviewed, and a cost reviewer for claims about cost.
- Route open \`repairRequests\` from the ledger to the retained lead and answered repairs to an independent reviewer. Include their IDs in the bounded task. Do not redispatch resolved repairs merely because an older decision still names them.
- For answered findings, route independent resolution; do not send an unchanged accepted claim back to its maker. If a resolution rejects an answer, the next brief names the specific remaining defect and evidence from the ledger.
- Every unanswered open finding is answered by its owner: put its id in that writer's \`answers\`. A finding with no owner is yours to assign to a writer. Legacy proposer findings transfer to the retained lead; do not redispatch former owners outside proposalTeam.
- Dispatch diagram authors to draw the views the proposers describe, once the design is written.
- Writers run first and reviewers after them in the same round, so a reviewer sees this round's writing.
- Set \`readyForDecision\` true, with no dispatches, only when the list above says nothing stands between the draft and a decision.`
  let plan = pendingPlan
  // A plan is saved durably and never replaced, so an overlap with no stated reason is refused before it is saved.
  for (let fix = 0, refusal = ''; !pendingPlan; fix++) {
    plan = await run(`${coordinatorBrief}${refusal}`, { label: fix ? `round${n}:coordinate-fix${fix}` : `round${n}:coordinate`, phase: 'Rounds', agentType: 'agent-teams-workforce:architecture-decision-workflow-coordinator', effort: 'medium', schema: COORDINATOR_SCHEMA })
    const overlapRefusals = plan ? unjustifiedOverlaps(plan) : []
    if (!overlapRefusals.length) break
    if (fix >= MAX_PLAN_FIXES) {
      const why = `the architecture-decision-workflow-coordinator's plan for round ${n} assigns the same review work to several reviewers without stating why, after ${MAX_PLAN_FIXES} correction(s): ${overlapRefusals.join('; ')}. The plan was not saved.`
      log(`Round ${n}: ${why}`)
      return {
        ok: false,
        stage: 'round-plan',
        deterministicFailure: true,
        headline: `Architecture stopped: the coordinator's round ${n} plan has reviewer overlaps with no stated reason after ${MAX_PLAN_FIXES} corrections`,
        reason: why,
        error: why,
        requiredHumanActions: [`The architecture-decision-workflow-coordinator returned ${MAX_PLAN_FIXES + 1} plans for round ${n} of ${subject}, each assigning the same claims or draft files to several reviewers with no \`overlaps\` entry stating why: ${overlapRefusals.join('; ')}. No plan was saved. Check the overlap rule the coordinator is given (the coordinator brief in workflows/architecture.js), then re-run the Epic.`],
        subject,
        ...surveyPaths,
      }
    }
    log(`Round ${n}: plan refused — ${overlapRefusals.join('; ')}`)
    retries.push({ step: `round${n}:coordinate`, whatChanged: `the plan was refused for reviewer overlaps with no stated reason: ${overlapRefusals.join('; ')}` })
    refusal = `\n\nYOUR LAST PLAN FOR ROUND ${n} WAS REFUSED and nothing of it was saved: ${overlapRefusals.join('; ')}. Return the whole plan again. For each overlap you keep, add one \`overlaps\` entry naming the shared files and claimIds, the reviewers that share them, and the reason; or assign the shared work to one reviewer.`
  }
  if (!plan) return { ok: false, stage: 'rounds', reason: `the coordinator returned no plan for round ${n}`, ...died('Rounds'), subject, ...surveyPaths }
  // A saved pending plan runs on the team already saved; only a new plan can name the team.
  const teamFacts = pendingPlan ? facts : await readFacts(`round${n}:proposal-team`, 'Rounds', plan.proposalTeam)
  if (teamFacts.error || !teamFacts.proposalTeam || !teamFacts.proposalTeam.lead) return { ok: false, stage: 'rounds', reason: teamFacts.error || 'coordinator did not select a proposal lead; saved work retained', subject }
  facts = teamFacts
  const settled = pendingPlan ? { dispatches: planDispatches(pendingPlan), rejected: [], stuck: [] } : settleDispatches(plan, n)
  if (settled.budgetError) return { ok: false, stage: 'rounds', reason: settled.rejected.join('; '), subject }
  rejected = settled.rejected
  forced = []
  teamNotes = false
  if (rejected.length) log(`Round ${n}: refused ${rejected.join('; ')}`)
  if (settled.stuck.length) {
    const why = `finding(s) stayed unanswered after their owner was told once that its result left them unanswered: ${settled.stuck.join('; ')}`
    log(`Round ${n}: ${why}`)
    return { ok: false, stage: 'rounds', reason: why, error: why, subject, ...surveyPaths, retries }
  }
  for (const r of retries.filter((x) => x.step.startsWith(`round${n}:`))) log(`Round ${n}: re-dispatch — ${r.whatChanged}`)
  if (!pendingPlan) {
    const orderedPlan = { round: n, proposalTeam: facts.proposalTeam, readyForDecision: plan.readyForDecision, overlaps: planOverlaps(plan), dispatches: [...settled.dispatches.filter(d => WRITER_ROLES.includes(d.role)), ...settled.dispatches.filter(d => REVIEW_ROLES.includes(d.role))] }
    const savedPlan = await readFacts(`round${n}:save-plan`, 'Rounds', null, orderedPlan)
    if (savedPlan.error) return { ok: false, stage: 'rounds', reason: savedPlan.error, subject }
    facts = savedPlan
    const saved = savedPlan.rounds.pendingPlan
    if (saved && saved.round !== n) {
      const why = `depscore.py arch-resume saved round ${n}'s plan but reports round ${saved.round} pending; saved work retained`
      return { ok: false, stage: 'rounds', reason: why, error: why, subject, ...surveyPaths }
    }
    if (saved && savedPlan.rounds.planKept === true) {
      // A plan for this round was already saved: it stands, and the new one is set aside.
      plan = { ...plan, readyForDecision: saved.readyForDecision }
      settled.dispatches = planDispatches(saved)
    } else {
      settled.dispatches = saved ? planDispatches(saved) : orderedPlan.dispatches
    }
  }
  if (pendingPlan && !settled.dispatches.some((d) => !d.complete)) {
    const why = `round ${n}'s saved plan has no dispatch left to run, yet depscore.py arch-resume reports it pending; saved work retained`
    return { ok: false, stage: 'rounds', reason: why, error: why, subject, ...surveyPaths }
  }
  if (!settled.dispatches.length) {
    if (plan.readyForDecision === true) {
      lastRound = n
      ready = true
      continue
    }
    const why = `the coordinator dispatched nothing in round ${n} and did not declare the target ready: ${plan.reason || 'no reason given'}`
    return { ok: false, stage: 'rounds', reason: why, error: why, rejected, subject, ...surveyPaths }
  }
  log(`Round ${n}: ${settled.dispatches.map((d) => `${d.role}:${d.agentType}`).join(', ')}`)
  for (const d of settled.dispatches) for (const id of listed(d.answers)) asked.set(id, { agentType: d.agentType, round: n, clarified: (d.clarified || []).includes(id) })
  const roundRun = await runRound(n, settled.dispatches)
  if (roundRun.error) {
    const why = `depscore.py arch-resume failed after round ${n}: ${roundRun.error}. The saved results in ${ROUNDS_DIR} could not be read; the step stops, and the saved results stay on disk for the next attempt.`
    log(`Round ${n}: ${why}`)
    return { ok: false, stage: 'rounds', headline: roundRun.exception ? `Architecture round ${n} failed: ${roundRun.exception}` : `Architecture could not read the saved results of round ${n}: ${roundRun.error}`, reason: why, error: why, subject, ...surveyPaths }
  }
  const silent = roundRun.silent
  silentLast = silent
  if (silent.length) return { ok: false, resumable: true, stage: 'rounds', reason: `round ${n} has unfinished dispatches: ${silent.join(', ')}; saved work retained`, ...died('Rounds'), subject, ...surveyPaths }
  lastRound = n
  pendingGaps = []
  ready = plan.readyForDecision === true || (roundLimit > MAX_ROUNDS && lastRound >= MAX_ROUNDS)
}
const guardRounds = await constraintsGuard(before, 'constraints:after-rounds', 'Rounds')
if (guardRounds) return { ...guardRounds, subject }
const treeRounds = await treeSnapshot('tree:after-rounds', 'Rounds', { against: [TREE_START] })
if (!treeRounds || treeRounds.error) {
  const why = `the architecture could not be fingerprinted after the rounds: ${(treeRounds && treeRounds.error) || 'no result'}`
  return { ok: false, stage: 'rounds', reason: why, error: why, subject, ...died('Rounds') }
}
const roundWrites = diffCount(treeRounds, 0)
if (roundWrites) {
  const why = `sessions wrote ${roundWrites} file(s) in the architecture at ${archPath} before the target was approved (listed under result.diffs in ${treeRounds.relayFile}); the survey and the rounds write only under ${WORK}`
  log(`Rounds: ${why}`)
  return { ok: false, stage: 'architecture-written', deterministicFailure: true, reason: why, error: why, filesListedIn: treeRounds.relayFile, subject }
}

// ---------------------------------------------------------------- Target
phase('Target')
const target = await depscore('target:write', 'Target', `arch-target --draft ${shq(DRAFT)} --arch-root ${shq(archPath)} --subject ${shq(subject)} --forbid ${shq(FORBID.join(','))} --out ${shq(TARGET_JSON)}`)
const targetSummary = target && target.summary ? target.summary : null
if (!targetSummary || target.error || targetSummary.ok !== true) {
  const why = targetSummary ? `depscore.py arch-target refused the approved draft: ${listed(targetSummary.refusals).join('; ') || 'no reason given'}` : `depscore.py arch-target did not run: ${(target && target.error) || 'no result'}`
  return { ok: false, stage: 'target', reason: why, error: why, decision, subject, ...died('Target') }
}
const targetDir = targetSummary.targetDir
const deltaDir = targetSummary.deltaDir
log(`Target: ${targetSummary.files} view file(s) at ${targetDir}, ${targetSummary.deltaFiles} in its delta`)

// ---------------------------------------------------------------- Integrate
phase('Integrate')
const SECTION_2_RULE = `Write nothing under ${CONSTRAINTS}: section 2 holds the owner's constraints, and only the owner changes them; the run fails on any change there. A constraint you believe should change goes in \`constraintIssues\`, with the constraint, the conflicting content and the reason.`
const INTEGRATE_TASK = `Integrate the approved target at ${targetDir} (the change alone is in ${deltaDir}) into the effective version, the folder ${ARC42}, as the architecture documentation model's step 5 describes. For each element the delta adds, changes or removes, find every effective view that shows it through the catalog (\`subject\` and \`shows\`), at every scope, and update or delete each one; add the target's new views in the section folder the model names, named for their subject. Keep every touched view's catalog frontmatter true to what it now shows. Edit in place: no changelog narrative, and no superseded content left beside the new. Leave every \`lifecycle_state\` as you find it: the run sets it after review. Leave ${targetDir} as it is: later phases read its delta.
${SECTION_2_RULE}
Read approved coverage rows/checks in ${LEDGER_JSON} and approval ${DECISION_JSON}. Apply every approved coverage action, including absent/new views and affected navigation; do not invent unapproved design. For independently excluded unrelated-debt rows record only the unchanged disposition; never repair their absent views. Record each row id in viewsChecked.element with its view/action, using unaffected for justified unchanged/not-applicable rows and view="" for a not-applicable or independently excluded unrelated-debt obligation without an existing path (never invent a view).

Report every file you changed, created or deleted as an absolute path under ${ARC42}, every view the catalog listed for a changed element and what you did to it, and every contradiction with another effective view or open target.`
const updateBrief = persistBrief([UPDATE_JSON], 'your complete structured result, exactly as you return it, as ONE JSON object')
/** The integration's file lists, written by depscore.py arch-integration-files; the script holds only their counts. */
const FILES_JSON = `${WORK}/integration-files.json`
/** Facts the saved integration left: its report's counts (the report itself stays in UPDATE_JSON), its fingerprint, its last review. */
const savedFacts = resumedFacts.integration || {}
const savedUpdate = savedFacts.update && typeof savedFacts.update === 'object' ? savedFacts.update : null
const INTEGRATE_BEFORE = `${WORK}/integrate-before.json`
const savedTree = savedFacts.beforeSaved === true
const integrateBefore = savedTree ? { saved: INTEGRATE_BEFORE } : await treeSnapshot('tree:before-integrate', 'Integrate', { save: INTEGRATE_BEFORE })
if (!integrateBefore || integrateBefore.error) {
  const why = `the architecture could not be fingerprinted before the integration: ${(integrateBefore && integrateBefore.error) || 'no result'}`
  return { ok: false, stage: 'integrate', reason: why, error: why, decision, subject, targetDir, deltaDir, ...died('Integrate') }
}
if (savedUpdate && !savedTree) log('Integrate: no fingerprint was saved before the earlier integration pass; its files are taken from its report and this pass is measured')
/** The last saved review's facts: { n, path, conforms, coverageRevision, findings: count }. */
const lastSavedReview = savedFacts.lastReview && typeof savedFacts.lastReview === 'object' ? savedFacts.lastReview : null

let integrationCoverageRevision = savedFacts.coverageRevision || ''
let integrationCoverageRows = coverageRowsOf(facts)
/** The integration as the script tracks it: counts from arch-integration-files; the lists are in FILES_JSON, the report in UPDATE_JSON. */
let update = null
let reviewPass = lastSavedReview ? Number(lastSavedReview.n) || 0 : 0
const reusedSaved = !!(savedUpdate && lastSavedReview && lastSavedReview.conforms === true && lastSavedReview.coverageRevision === savedFacts.coverageRevision)
if (reusedSaved) {
  log('Integrate: reused the saved integration and its conforming review')
} else {
  const report = await run(
    savedUpdate
      ? `You are the architecture-maintainer, RESUMING an integration a previous session began and did not finish. Its report is ${UPDATE_JSON}; its edits are in the working tree (\`git status --short\` in the repository holding ${archPath}). Do not start over: finish every view the previous pass left inconsistent with the target or with the other views of the same element, then return the complete report for both passes.\n\n${INTEGRATE_TASK}${updateBrief}`
      : `You are the architecture-maintainer.\n\n${INTEGRATE_TASK}${updateBrief}`,
    { label: 'integrate:maintain', phase: 'Integrate', agentType: 'architecture-maintainer', effort: 'medium', schema: MAINTAIN_SCHEMA }
  )
  if (!report) return { ok: false, stage: 'integrate', reason: 'the architecture-maintainer returned no result', ...died('Integrate'), decision, subject, targetDir, deltaDir }
  if (!(await saveResult('integrate:maintain', 'Integrate', UPDATE_JSON, report))) {
    const why = `the integration report the architecture-maintainer returned could not be saved to ${UPDATE_JSON}`
    return { ok: false, stage: 'integrate', reason: why, error: why, decision, subject, targetDir, deltaDir }
  }
}

/** What the integration report returns: counts and where the lists are. */
const updateFacts = (f) => ({
  reportPath: UPDATE_JSON,
  filesPath: FILES_JSON,
  touched: Number(f.touched) || 0,
  deleted: Number(f.deleted) || 0,
  unreported: Number(f.unreported) || 0,
  constraintIssues: Number(f.constraintIssues) || 0,
  contradictions: Number(f.contradictions) || 0,
})
/**
 * Measures what the integration wrote since INTEGRATE_BEFORE with depscore.py arch-integration-files,
 * which unions it with the saved report, writes the lists to FILES_JSON and saves the tree to
 * TREE_LAST; with `sinceLast` it also counts the files changed since the previous measurement.
 * Returns { update, changedSinceLast, relayFile } or { failure }.
 */
async function measured(label, sinceLast, accumulate) {
  const now = await depscore(label, 'Integrate', `arch-integration-files --arch-root ${shq(archPath)} --before ${shq(INTEGRATE_BEFORE)} --report ${shq(UPDATE_JSON)} --files-out ${shq(FILES_JSON)} --save-last ${shq(TREE_LAST)}${sinceLast ? ` --last ${shq(TREE_LAST)}` : ''}${accumulate ? ' --accumulate' : ''}`)
  if (!now || now.error) {
    const why = `the architecture could not be measured after the integration: ${(now && now.error) || 'no result'}`
    return { failure: { ok: false, stage: 'integrate', reason: why, error: why, architectureUpdate: update, decision, subject, targetDir, deltaDir, ...died('Integrate') } }
  }
  if (Number(now.unreported) > 0) log(`Integrate: ${now.unreported} file(s) written and not reported, added to the review (listed under unreported in ${FILES_JSON})`)
  return { update: { ...updateFacts(now), section2: Number(now.section2) || 0, outside: Number(now.outside) || 0 }, changedSinceLast: Number(now.changedSinceLast) || 0 }
}
/** Returns the failure when the integration wrote a file in section 2 or outside arc42 (section 2 is put back), else null. */
async function outOfBounds(u) {
  if (!u.section2 && !u.outside) return null
  if (u.section2) {
    const guard = await constraintsGuard(before, 'constraints:integrate-bounds', 'Integrate')
    if (guard) return { ...guard, architectureUpdate: u, decision, subject, targetDir, deltaDir }
  }
  const why = u.section2
    ? `the integration wrote ${u.section2} file(s) in section 2, which holds the owner's constraints (listed under section2 in ${FILES_JSON})`
    : `the integration wrote ${u.outside} file(s) outside the effective version ${ARC42} (listed under outside in ${FILES_JSON})`
  return { ok: false, stage: 'integrate', deterministicFailure: true, reason: why, error: why, architectureUpdate: u, decision, subject, targetDir, deltaDir }
}
const firstMeasure = await measured('tree:after-integrate', false, false)
if (firstMeasure.failure) return firstMeasure.failure
update = firstMeasure.update
const bounds = await outOfBounds(update)
if (bounds) return bounds

/** Names where a review's findings are: the review file, and the changed files it did not review. */
const findingsWhere = (c) =>
  `the \`findings\` in ${c.path}${Number(c.missedCount) > 0 ? `, and the ${c.missedCount} file(s) the integration changed or created that the review did not review (listed under result.missed in ${c.checkFile})` : ''}`
/** Runs one conformance review; a changed file the review does not cover is a finding. `again` names the previous review and the number of files the correction changed. */
async function review(again) {
  reviewPass += 1
  const againBlock = again
    ? `\nTHIS IS REVIEW ${reviewPass}. The previous review's findings are ${findingsWhere(again.previous)}; read them. Correction ${again.correction} changed ${again.changed} file(s) to answer them (listed under changedSinceLast in ${FILES_JSON}). Confirm each finding is resolved, and check the changed files as fully as the rest.\n`
    : ''
  const reviewFile = `${WORK}/conformance-${reviewPass}.json`
  const current = await readFacts(`integrate:coverage-${reviewPass}`, 'Integrate')
  if (current.error || hasGaps(current) || current.coverage.revision !== decision.coverageRevision) {
    log('Integrate: approved coverage changed or lost review evidence; retain work for targeted reapproval')
    return null
  }
  integrationCoverageRevision = current.integration.coverageRevision
  integrationCoverageRows = coverageRowsOf(current)
  const got = await run(
    `You are the architecture-conformance-reviewer. Check one integration of an approved target into the effective version; report findings and fix nothing.

THE APPROVED TARGET: ${targetDir} (the change alone in ${deltaDir}).
THE INTEGRATION REPORT: ${UPDATE_JSON}. The ${update.touched} file(s) it changed or created, every one of which you review, are the \`touched\` list in ${FILES_JSON}; the ${update.deleted} it deleted are its \`deleted\` list.
${againBlock}
${ARCH_WHERE}

Read approved coverage in ${LEDGER_JSON} and decision ${DECISION_JSON}. Independently check every approved action, including required views absent before integration, honest diagram declarations, readable rendering, cross-scope consistency and navigation. Report unrelated historical debt in summary, not blocking findings. Set coverageRevision to ${integrationCoverageRevision}; it binds this review to approved coverage and current integrated content. Return coverageChecks for EVERY approved ledger row id/revision, with verdict and evidence naming the integrated view and disposition (including unchanged/not-applicable and independently excluded unrelated-debt, whose missing views must not be repaired). Do not change the design to fill a gap.

Check that the integration applied the approved target exactly, no more and no less; that every effective view the catalog lists for each changed element was updated or deleted, at every scope; that the new views sit in the section folders the model names with catalog frontmatter true to what they show; that no superseded content remains beside the new and no view contradicts another or an open target; and that nothing under ${CONSTRAINTS} changed. Return in \`reviewedFiles\` the absolute path of every file you checked and found conforming, and one finding per problem with its file and evidence; \`conforms\` is true only when there is no finding.${persistBrief([reviewFile], 'your complete structured result, exactly as you return it, as ONE JSON object')}`,
    { label: `integrate:review-${reviewPass}`, phase: 'Integrate', agentType: 'agent-teams-workforce:architecture-conformance-reviewer', effort: 'medium', schema: CONFORMANCE_SCHEMA }
  )
  if (!got || !(await saveResult(`integrate:review-${reviewPass}`, 'Integrate', reviewFile, got))) return null
  return covered({ ...got, path: reviewFile })
}
/**
 * Checks a saved review with depscore.py arch-review-check: a changed file it does not cover, an
 * approved coverage row without a verified check at its revision, or a review bound to another
 * coverage revision is a finding, and the review does not conform. Returns the review with
 * missedCount and checkFile, or null when the check could not run.
 */
async function covered(c) {
  const check = await depscore(`integrate:review-check-${reviewPass}`, 'Integrate', `arch-review-check --review ${shq(c.path)} --files ${shq(FILES_JSON)} --coverage-from ${shq(integrationCoverageRows.file)} --coverage-revision ${shq(integrationCoverageRevision)}`)
  if (!check || check.error) {
    log(`Integrate: the review in ${c.path} could not be checked: ${(check && check.error) || 'no result'}`)
    return null
  }
  const findings = Array.isArray(c.findings) ? [...c.findings] : []
  if (Number(check.coverageUnverified) > 0) findings.push({ file: UPDATE_JSON, finding: `${check.coverageUnverified} approved coverage row(s) lack verified integration evidence (listed under result.coverageUnverified in ${check.relayFile})`, evidence: 'no current per-obligation conformance check' })
  else if (check.checksAtRevision !== true) findings.push({ file: UPDATE_JSON, finding: 'a verified coverage check is not at the approved revision of its ledger row', evidence: `the verified checks' id/revision list does not match the approved rows in ${LEDGER_JSON}` })
  if (check.revisionMatches !== true) findings.push({ file: UPDATE_JSON, finding: 'coverage review is missing or stale for current integrated content', evidence: 'coverageRevision does not match the current integration' })
  if (Number(check.missed) > 0) findings.push({ file: FILES_JSON, finding: `${check.missed} file(s) changed or created by the integration were not reviewed (listed under result.missed in ${check.relayFile})`, evidence: 'absent from reviewedFiles' })
  const conforms = check.conforms === true && findings.length === 0
  return { ...c, findings, conforms, missedCount: Number(check.missed) || 0, checkFile: check.relayFile }
}

let conformance = lastSavedReview && lastSavedReview.conforms === true && reusedSaved ? await covered({ ...lastSavedReview, findings: [] }) : null
if (!conformance || conformance.conforms !== true) conformance = await review()
if (!conformance) return { ok: false, stage: 'integrate', reason: 'the architecture-conformance-reviewer returned no result, or its review could not be checked', ...died('Integrate'), decision, subject, targetDir, deltaDir, architectureUpdate: update }
let corrections = 0
while (conformance.conforms !== true && corrections < MAX_CORRECTIONS) {
  corrections += 1
  const fixed = await run(
    `You are the architecture-maintainer, CORRECTING your integration (correction ${corrections} of ${MAX_CORRECTIONS}). The architecture-conformance-reviewer's findings are ${findingsWhere(conformance)}: read them. Correct each one in place, then return the complete report of the integration, every pass together.

${INTEGRATE_TASK}${updateBrief}`,
    { label: `integrate:correct-${corrections}`, phase: 'Integrate', agentType: 'architecture-maintainer', effort: 'medium', schema: MAINTAIN_SCHEMA }
  )
  if (!fixed) return { ok: false, stage: 'integrate', reason: `the architecture-maintainer returned no result for correction ${corrections}`, ...died('Integrate'), decision, subject, targetDir, deltaDir }
  if (!(await saveResult(`integrate:correct-${corrections}`, 'Integrate', UPDATE_JSON, fixed))) {
    const why = `the corrected integration report could not be saved to ${UPDATE_JSON}`
    return { ok: false, stage: 'integrate', reason: why, error: why, decision, subject, targetDir, deltaDir }
  }
  const fixMeasure = await measured(`tree:after-correct-${corrections}`, true, true)
  if (fixMeasure.failure) return fixMeasure.failure
  update = fixMeasure.update
  const fixedBounds = await outOfBounds(update)
  if (fixedBounds) return fixedBounds
  const changedNow = fixMeasure.changedSinceLast
  if (!changedNow) {
    const why = `correction ${corrections} changed no file, so a further review would judge the same integration; the findings stand: ${(conformance.findings || []).map((f) => `${f.file}: ${f.finding}`).join('; ')}`
    log(`Integrate: ${why}`)
    return { ok: false, stage: 'integrate', reason: why, error: why, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir, retries }
  }
  const whatChanged = `correction ${corrections} changed ${changedNow} file(s) to answer ${(conformance.findings || []).length} finding(s)`
  retries.push({ step: 'integrate:review', attempt: reviewPass + 1, whatChanged })
  log(`Integrate: review again — ${whatChanged}`)
  conformance = await review({ correction: corrections, changed: changedNow, previous: conformance })
  if (!conformance) return { ok: false, stage: 'integrate', reason: 'the architecture-conformance-reviewer returned no result, or its review could not be checked', ...died('Integrate'), decision, subject, targetDir, deltaDir, architectureUpdate: update }
}
if (conformance.conforms !== true) {
  const why = `the integration does not conform after ${corrections} correction pass(es): ${(conformance.findings || []).map((f) => `${f.file}: ${f.finding}`).join('; ')}`
  log(`Integrate: ${why}`)
  return { ok: false, stage: 'integrate', reason: why, error: why, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
}
const guardIntegrate = await constraintsGuard(before, 'constraints:after-integrate', 'Integrate')
if (guardIntegrate) return { ...guardIntegrate, subject, targetDir, deltaDir, architectureUpdate: update }

// Consumed by: lifecycle promotion below — do not promote evidence changed after review.
const finalCoverage = await readFacts('integrate:coverage-final', 'Integrate')
if (finalCoverage.error || hasGaps(finalCoverage) || finalCoverage.coverage.revision !== decision.coverageRevision || finalCoverage.integration.coverageRevision !== conformance.coverageRevision || !finalCoverage.integration.lastReview || finalCoverage.integration.lastReview.coverageRevision !== conformance.coverageRevision) {
  return { ok: false, stage: 'integrate', reason: 'conformance evidence is unsaved or stale; retained work requires a fresh review before promotion', subject, targetDir, deltaDir }
}
let approval = null
if (update.touched) {
  approval = await depscore('integrate:approve', 'Integrate', `arch-approve --arch-files-from ${shq(FILES_JSON)} --reviewed-from ${shq(conformance.path)} --arch-root ${shq(ARC42)}`)
  const n = approval && approval.summary ? approval.summary : null
  const notSet = approval && !approval.error ? [...listed(approval.unreviewed), ...(approval.refused || []).map((x) => x.path), ...(approval.failed || []).map((x) => x.path)] : []
  if (!n || approval.error || notSet.length) {
    const why = !n || approval.error
      ? `depscore.py arch-approve did not run: ${(approval && approval.error) || 'no result'}`
      : `depscore.py arch-approve did not set these integrated files to effective: ${notSet.join(', ')}`
    return { ok: false, stage: 'approve', reason: why, error: why, approval, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
  }
  log(`Approval: ${n.promoted || 0} file(s) set to effective, ${n.unchanged || 0} already effective`)
}

let vaultCommit = null
if (update.touched + update.deleted) {
  vaultCommit = await depscore('integrate:commit', 'Integrate', `arch-commit --arch-root ${shq(ARC42)} --files-from ${shq(FILES_JSON)} --message ${shq(`docs(architecture): integrate the approved target for ${subject}`)}`)
  if (!vaultCommit || vaultCommit.error || vaultCommit.ok === false) {
    const why = `depscore.py arch-commit did not commit and push the integrated files: ${(vaultCommit && (vaultCommit.error || listed(vaultCommit.refusals).join('; '))) || 'no result'}`
    return { ok: false, stage: 'commit', reason: why, error: why, vaultCommit, approval, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
  }
  log(`Commit: ${vaultCommit.commit ? `${vaultCommit.commit} on ${vaultCommit.branch}` : 'nothing new to commit'}${vaultCommit.pushed ? ', pushed' : ''}`)
}

return {
  ok: true,
  subject,
  subjectName,
  targetDir,
  deltaDir,
  targetPath: TARGET_JSON,
  surveyPath: SURVEY_MD,
  decision,
  decisionPath: DECISION_MD,
  architectureUpdate: update,
  conformance,
  approval,
  vaultCommit,
  rounds: lastRound,
  retries,
  openItems: update.constraintIssues + update.contradictions > 0 ? [`${update.constraintIssues} constraint issue(s) and ${update.contradictions} contradiction(s) recorded in ${UPDATE_JSON}`] : [],
  architectureUpdatePath: UPDATE_JSON,
  ledgerPath: LEDGER_JSON,
}

})())
