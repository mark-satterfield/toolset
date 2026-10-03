export const meta = {
  name: 'prd-to-spec',
  description:
    'Composite: elaborates an existing, scored Epic and its PRD into Stories and Tasks written to beads. It starts the Epic lifecycle with depscore.py elaboration-start, reads what it takes from the PRD file with depscore.py prd-parse, which assumes the PRD was validated before its Epic was made ready and holds the Epic for a person only when the file cannot be read, runs the architecture mini for every PRD (it is never skipped: a PRD the effective version already serves gets a delta that says so), which writes the Epic\'s target and delta under target/<subject>/ and integrates the approved target into the effective version, and holds the Epic for the owner on an two business requirements no design can satisfy together, or an architecture that contradicts itself where common sense cannot settle it, before any Story or Task exists — lists the delta items with depscore.py arch-delta (one per element the delta shows), rules the repo span as the repositories the delta changes (the polyrepo-steward places each item and creates the new repositories the target names; then a polyrepo-steward session rules, from its records, whether each span repository is a buildable, active repository, and a placement in the control repository, in the repository holding the architecture, in a repository the steward refuses or in one it gives no verdict for holds the Epic for a person before any Spec, naming the delta items placed there and the reason; a repository the steward created that the approved target does not name, checked with depscore.py arch-target-names, holds the Epic too), authors the TRD from the target and delta views, details per repo each placed item against the code on main (add, modify, remove, done, planned-elsewhere; a failed detailing blocks that repo\'s Spec) and authors one Spec and Story per repo for its add, modify and remove items (the session that authors the Story writes its bead with depscore.py write-story), decomposes each Story into Tasks for those items only, with a blocks edge onto an open Task of another Epic instead of a duplicate (the session that decomposes it writes each Task bead with one depscore.py write-task command, in build order), derives the Task edges between Stories (the session that derives them writes every Task\'s edges with one depscore.py write-all-task-edges command), then scores the Epic and its Tasks and sets it done with depscore.py elaboration-finish, which reads beads and sets it done only when beads holds every Story, Task and edge the span\'s saved documents name; once it is done, depscore.py arch-target-remove deletes target/<subject>/ and commits the removal. Every bead write is keyed by elab_key, so a rerun updates what exists. When beads does not hold them, the run returns ok:false at stage hierarchy-not-persisted naming what is missing. Returns { ok, stage, beadId, headline, detailPath } plus hierarchy, repoSpan, targetRemoval, beadsEmitted and lifecycle.',
  phases: [
    { title: 'Epic Lifecycle', detail: 'depscore.py elaboration-start: refuse with a named reason, or mark the Epic in_progress' },
    { title: 'PRD', detail: 'resolve the PRD text or path supplied by the caller' },
    { title: 'PRD Parse', detail: 'depscore.py prd-parse reads what elaboration takes from the PRD, assuming it was validated before its Epic was made ready; only a file that cannot be read holds the Epic for a person' },
    { title: 'Epic', detail: "adopt the caller's Epic" },
    { title: 'Architecture', detail: 'the architecture mini writes the target and delta for the Epic and integrates the approved target into the effective version; only two business requirements no design can satisfy together, or an architecture that contradicts itself where common sense cannot settle it, hold the Epic for the owner' },
    { title: 'Repo Scoping', detail: 'the polyrepo-steward places each delta item; the span is the repositories the delta changes; the polyrepo-steward rules each span repository buildable and active, and a placement in the control repository or a refused repository holds the Epic' },
    { title: 'TRD Authoring', detail: 'author the TRD once per PRD from the target and delta views' },
    { title: 'Spec Authoring', detail: 'per repo: detail each placed delta item against the code on main, then author the Spec for its add, modify and remove items and write its Story bead' },
    { title: 'Task Decomposition', detail: 'per Story: decompose its add, modify and remove items into Tasks, each Task bead written with its edges as it is saved; then derive the Task edges between Stories and write them with one command' },
    { title: 'Finish', detail: 'depscore.py elaboration-finish: score the Epic and its Tasks; set done when beads holds every Story, Task and edge the saved documents name; then depscore.py arch-target-remove deletes target/<subject>/ and commits the removal' },
    { title: 'Run Ledger', detail: 'log the run journal on every exit path' },
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

// BEGIN bounded dispatch policy — identical in workflow consumers (no runtime imports).
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
}
function dispatchPolicy(options) {
  const input = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  const policy = (options && options.retryPolicy) || input.retryPolicy || {}
  return { maxAttempts: Number.isInteger(policy.maxAttempts) && policy.maxAttempts > 0 ? policy.maxAttempts : 3,
    maxWaitMs: Number.isFinite(policy.maxWaitMs) && policy.maxWaitMs >= 0 ? policy.maxWaitMs : 300000 }
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
function dispatchRetry(err, name, attempt, waitedMs, policy, canWait) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return { retry: false, cause }
  const e = err && typeof err === 'object' ? err : {}
  const headers = e.headers || (e.response && e.response.headers) || {}
  const rawRetryAfter = e.retryAfter !== undefined ? e.retryAfter : headers['retry-after']
  const retryAfter = e.retryAfterMs !== undefined ? Number(e.retryAfterMs) : Number(rawRetryAfter) * 1000
  // An HTTP-date without a supplied clock cannot be safely shortened to our backoff.
  const unknownRetryDate = rawRetryAfter !== undefined && !Number.isFinite(retryAfter)
  let hash = 2166136261
  for (const ch of `${name}#${attempt}`) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619)
  const scheduled = Math.round(Math.min(300000, 5000 * Math.pow(3, attempt - 1)) * (0.5 + 0.5 * ((hash >>> 0) / 4294967296)))
  const wait = Math.max(scheduled, Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : 0)
  if (cause === 'transient' && !unknownRetryDate && canWait && attempt < policy.maxAttempts && waitedMs + wait <= policy.maxWaitMs) return { retry: true, cause, wait }
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  return { retry: false, cause, interruption: { stage, message: `${stage}: ${name}: ${String(e.message || err || cause)}`, attempt,
    retryAfterMs: Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : null, retryAfter: rawRetryAfter || null } }
}
async function settleWorkflow(name, input) {
  if (dispatchInterruption) return dispatchOutcome({})
  const source = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  try {
    const out = await fableWorkflow(name, { ...input, ...(source.retryPolicy && !(input && input.retryPolicy) ? { retryPolicy: source.retryPolicy } : {}) })
    if (out && out.paused && out.resumable && out.dispatchInterruption) dispatchInterruption = out.dispatchInterruption
    return out
  } catch (err) {
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(null), false)
    if (!plan.interruption) throw err
    dispatchInterruption = plan.interruption
    return dispatchOutcome({})
  }
}
// END bounded dispatch policy

const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  return dispatchFailures.filter((f) => named.includes(f.phase))
}
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
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(o), false)
    if (plan.interruption) dispatchInterruption = plan.interruption
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
if (!a.prd) return dispatchOutcome({ ok: false, stage: 'input', error: 'no prd supplied' })
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const shellq = (v) => `'${String(v).replace(/'/g, "'\\''")}'`
const repoPath = a.repoPath || a.prd.repoPath || null
let repos = []
const epicRef = a.epic && typeof a.epic === 'object' ? a.epic : {}
const epicBeadId = String(epicRef.id || epicRef.beadId || '').trim()
const subjectId = a.prd.id || a.prd.path || epicRef.key || epicBeadId || null
const emitTarget = a.beadsRepoPath || repoPath
const normRepo = (p) => String(p || '').trim().replace(/\/+$/, '')
/** The control repository: the one beads runs in. It is never a placement target. */
const CONTROL_REPO = normRepo(emitTarget)

const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const HUMAN_ACTION_STAGE = 'requires-human-action'

const produced = {}
const runLedger = []
let runDetail = null

const EXPECTED_PHASES = [
  'Epic Lifecycle',
  'PRD',
  'Epic',
  'PRD Parse',
  'Architecture',
  'Repo Scoping',
  'TRD Authoring',
  'Spec Authoring',
  'Task Decomposition',
  'Finish',
  'Run Ledger',
]
const runRecord = { expectedPhases: EXPECTED_PHASES.slice(), phases: [] }
let currentPhase = null
const recCurrent = () => (runRecord.phases.length ? runRecord.phases[runRecord.phases.length - 1] : null)
function enterPhase(title) {
  currentPhase = title
  runRecord.phases.push({ seq: runRecord.phases.length + 1, name: title, status: 'running', decision: null, artifacts: [], failure: null, skipReason: null })
  phase(title)
}
function recRuled(decision, extra) {
  const entry = recCurrent()
  if (!entry) return
  if (hasText(decision)) {
    const one = decision.trim()
    entry.decision = (entry.decision ? `${entry.decision}; ${one}` : one).slice(0, 1200)
  }
  if (extra && typeof extra.status === 'string') entry.status = extra.status
  if (extra && extra.failure) entry.failure = extra.failure
  if (extra && typeof extra.skipReason === 'string') entry.skipReason = extra.skipReason
}

const JOURNAL_CHUNK = 4000
function emitRunJournal(payload) {
  const body = JSON.stringify(payload)
  if (body.length <= JOURNAL_CHUNK) {
    log(`RUN-JOURNAL ${body}`)
    return
  }
  const parts = []
  for (let i = 0; i < body.length; ) {
    let end = Math.min(i + JOURNAL_CHUNK, body.length)
    const last = body.charCodeAt(end - 1)
    if (end < body.length && last >= 0xd800 && last <= 0xdbff) end -= 1
    parts.push(body.slice(i, end))
    i = end
  }
  parts.forEach((part, i) => log(`RUN-JOURNAL-PART ${i + 1}/${parts.length} ${part}`))
}
function persistRun(outcome) {
  try {
    emitRunJournal({
      composite: 'prd-to-spec',
      bead: { id: epicBeadId || subjectId, title: epicRef.title || null },
      subject: a.prd.id || null,
      outcome,
      carriedFlags: [],
      run: runRecord,
      runLedger,
      detail: runDetail,
    })
  } catch (e) {
    log(`run journal could not be serialized: ${(e && e.message) || e}`)
  }
  return null
}

const reasonOf = (stage, detail) =>
  String((detail && (detail.reason || detail.error || detail.headline)) || `the ${stage} phase failed`).slice(0, 400)
const partial = (stage, detail, extra) => {
  const salvage = { ...produced, ...(extra || {}) }
  const why = reasonOf(stage, detail)
  recRuled(null, { status: 'failed', failure: { stage, reason: why } })
  runDetail = { stage, detail, partial: salvage }
  const keys = Object.keys(salvage)
  return {
    ok: false,
    stage: detail && detail.dispatchFailed ? DISPATCH_FAILED_STAGE : stage,
    beadId: subjectId,
    headline: `${stage}: ${why}. ${keys.length ? `Produced before it stopped, in the run journal under \`partial\`: ${keys.join(', ')}.` : 'Nothing had been produced.'}`,
    partialProduced: keys,
  }
}
function handback(ok, stage, headline, detail) {
  runDetail = detail === undefined ? null : detail
  if (!ok) {
    const entry = recCurrent()
    if (entry && entry.status === 'running') {
      entry.status = 'failed'
      entry.failure = { stage, reason: String(headline || `the ${stage} phase failed`).slice(0, 400) }
    }
  }
  return { ok, stage, beadId: subjectId, headline: String(headline || '') }
}

const artPhases = {}
const artReport = { dir: null, epicId: null, filing: {} }

const lifecycle = { started: false, owner: null, pluginRoot: null, start: null, finish: null, release: null, held: false }
const RESOLVE_PLUGIN_ROOT_PY = `import json, os, sys
from pathlib import Path
repo = os.path.normpath(ARGS[0]) if ARGS and ARGS[0] else ""
control = os.environ.get("ATW_CONTROL_REPO", "").strip()
projects = {p for p in (repo, os.path.normpath(control) if control else "") if p}
config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude")
reg = Path(config) / "plugins" / "installed_plugins.json"
try:
    plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
except (OSError, ValueError) as exc:
    emit({"pluginRoot": None, "problem": f"{reg} is unreadable: {exc}"})
ranked = []
for key, entries in plugins.items():
    if not key.startswith("agent-teams-workforce@") or not isinstance(entries, list):
        continue
    for e in entries:
        path = e.get("installPath") if isinstance(e, dict) else None
        if not isinstance(path, str) or not Path(path, "scripts", "portfolio", "depscore.py").is_file():
            continue
        if e.get("scope") in ("local", "project") and e.get("projectPath") in projects:
            ranked.append((0, path))
        elif e.get("scope") == "user":
            ranked.append((1, path))
if ranked:
    emit({"pluginRoot": os.path.normpath(sorted(ranked)[0][1]), "problem": None})
emit({"pluginRoot": None, "problem": f"{reg} lists no agent-teams-workforce install shipping scripts/portfolio/depscore.py at user scope or for {sorted(projects)}"})`
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

/** Where the full results relayed to this script are saved: the Epic's artifacts directory once known (set below), else the beads repository's run folder. */
let relayDir = null
let relaySeq = 0
/** The next relay file, named for its label. */
function nextRelayFile(label) {
  const dir = relayDir || `${emitTarget}/.claude/workflow-runs/relay/${String(epicBeadId || 'run').replace(/[^A-Za-z0-9._-]+/g, '_')}`
  relaySeq += 1
  return `${dir}/${String(relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
}
/** scripts/portfolio/relayrun.py of the plugin: runs any other program through the checked relay. */
const relayRunner = () => `${lifecycle.pluginRoot}/scripts/portfolio/relayrun.py`
/** Runs one depscore.py command through the checked relay; returns the facts it printed with `relayFile`, or { error }. */
function runScript(label, phaseName, commandArgs) {
  return relayKit.depscore(settleAgent, { label, phase: phaseName, script: `${lifecycle.pluginRoot}/scripts/portfolio/depscore.py`, repo: emitTarget, tail: commandArgs, file: nextRelayFile(label) })
}
/** Runs any other program (argv, no shell) through the checked relay; returns relayKit.run's result. */
function runProgram(label, phaseName, argv, opts = {}) {
  return relayKit.run(settleAgent, { label, phase: phaseName, runner: relayRunner(), argv, file: nextRelayFile(label), ...opts })
}
const HOLD_CAUSE = 'awaiting-human-action'
/** Returns the instruction that hands a held Epic back to elaboration. */
function restoreStep(epicId, after = 'what it names has been settled') {
  const elabmark = typeof a.artifactScript === 'string' && /\/artifactio\.py$/.test(a.artifactScript)
    ? `python3 ${a.artifactScript.replace(/artifactio\.py$/, 'elabmark.py')}`
    : 'elabmark.py (in the SDLC automation directory)'
  return `After ${after}, set ${epicId} to elaboration_state=in_progress: ${elabmark} --set=in_progress --bead=${epicId} --apply — the next elaboration sweep resumes it from its last persisted step. Never set a partly-elaborated Epic to ready.`
}
/** Clears the Epic's elaboration_state with cause awaiting-human-action; returns whether the write succeeded. */
async function holdForPerson(epicId) {
  const out = await runProgram('epic:hold', currentPhase || 'Architecture', ['python3', `${lifecycle.pluginRoot}/skills/beads-contract/scripts/beads-contract.py`, '-C', emitTarget, 'metadata', 'set', epicId, 'elaboration_state=', `elaboration_state_cause=${HOLD_CAUSE}`, 'elaboration_state_owner='])
  lifecycle.held = !!(out && out.ok && out.exitCode === 0 && out.json && !out.json.error)
  log(lifecycle.held ? `Epic ${epicId}: elaboration_state cleared (cause ${HOLD_CAUSE})` : `Epic ${epicId}: could NOT be held for a person — it stays in_progress`)
  return lifecycle.held
}
/** Holds the Epic for a person and returns the requires-human-action handback. */
async function holdForHuman(stage, detail, actions, after) {
  await holdForPerson(epicBeadId)
  return {
    ...partial(stage, detail),
    stage: HUMAN_ACTION_STAGE,
    requiredHumanActions: lifecycle.held ? [...actions, restoreStep(epicBeadId, after)] : actions,
  }
}

let result
try {
  result = await (async () => {
enterPhase('Epic Lifecycle')
if (!epicBeadId) {
  return handback(false, 'epic-lifecycle', 'refused: no-epic — args.epic.id names no Epic. Create the Epic, assess its dependencies and score it first')
}
if (!hasText(emitTarget)) {
  return handback(false, 'epic-lifecycle', 'refused: no-tracker — no repository path was supplied, and beads cannot be written without one')
}
// designSystem is optional: packagesDir holds the single-artifact cds bundles the owner supplied (absent or
// empty supplies none), mocksDir and shellsDir the loose composed artifacts.
const designSystemArg = a.designSystem && typeof a.designSystem === 'object' ? a.designSystem : {}
const startArgs = `elaboration-start --epic ${shellq(epicBeadId)}${hasText(a.owner) ? ` --owner ${shellq(a.owner)}` : ''}${a.reclaim === true ? ' --reclaim' : ''}`
// pluginRoot comes from the Workflow args, else from the agent-teams-workforce install that
// $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records (the install for the beads repository or
// $ATW_CONTROL_REPO first, else the user-scope one); with neither, the run refuses before any other agent.
let pluginRootProblem = ''
if (hasText(a.pluginRoot) && a.pluginRoot.trim().startsWith('/')) {
  lifecycle.pluginRoot = a.pluginRoot.trim().replace(/\/+$/, '')
} else {
  const found = await relayKit.inline(settleAgent, { label: 'resolve-plugin-root', phase: 'Epic Lifecycle', code: RESOLVE_PLUGIN_ROOT_PY, args: [emitTarget] })
  if (found.noResult) {
    return {
      ...handback(false, 'epic-lifecycle', `the plugin-root resolver for ${epicBeadId} returned no result`),
      stage: DISPATCH_FAILED_STAGE,
      dispatchFailed: true,
      dispatchFailures: dispatchDeaths('Epic Lifecycle'),
    }
  }
  const o = found.ok ? found.view : { error: found.error }
  if (hasText(o.pluginRoot) && o.pluginRoot.trim().startsWith('/')) {
    lifecycle.pluginRoot = o.pluginRoot.trim().replace(/\/+$/, '')
    log(`pluginRoot was not passed; the plugin registry gives ${lifecycle.pluginRoot}`)
  } else {
    pluginRootProblem = String(o.problem || o.error || 'the resolver printed no pluginRoot').slice(0, 500)
  }
}
if (!lifecycle.pluginRoot) {
  return handback(false, 'epic-lifecycle', `refused: no-plugin-root — pluginRoot has no value (${pluginRootProblem}): pass pluginRoot in the Workflow args or install agent-teams-workforce so $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json (default ~/.claude) records it`)
}
const started = await runScript('epic:start', 'Epic Lifecycle', startArgs)
if (started.noResult) {
  return {
    ...handback(false, 'epic-lifecycle', `the Epic lifecycle runner for ${epicBeadId} returned no result`),
    stage: DISPATCH_FAILED_STAGE,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Epic Lifecycle'),
  }
}
lifecycle.start = started.error ? started.output || null : started
const startOut = started.error ? { error: started.error } : started
if (startOut.error) {
  return handback(false, 'epic-lifecycle', `the Epic lifecycle check for ${epicBeadId} failed: ${startOut.error}`)
}
if (startOut.ok !== true) {
  const refusal = startOut.refusal || {}
  return {
    ...handback(false, 'epic-lifecycle', `refused: ${refusal.code || 'unknown'} — ${refusal.reason || 'the Epic may not be elaborated now'}`),
    refusal,
  }
}
lifecycle.owner = hasText(startOut.owner) ? startOut.owner : null
lifecycle.started = !!lifecycle.owner
recRuled(`Epic ${epicBeadId} marked in_progress (was ${startOut.previousState}) under owner ${lifecycle.owner}.`, { status: 'done' })
log(`Epic ${epicBeadId}: elaboration started (was ${startOut.previousState}); plugin root ${lifecycle.pluginRoot}`)

enterPhase('PRD')
let prd = a.prd
if (!hasText(prd.body) && hasText(prd.content)) prd = { ...prd, body: prd.content }
const prdByPath = !hasText(prd.body) && hasText(prd.path)
if (!hasText(prd.body) && !prdByPath) {
  const msg = 'the supplied PRD carries no text: none of prd.body, prd.content or prd.path is set'
  return { ...handback(false, 'input', msg), error: msg }
}
recRuled(prdByPath ? `PRD read from its file by each session: ${prd.path}` : 'PRD text supplied inline.', { status: 'done' })
produced.prd = prd

const ARCHITECTURE_DELIVERABLES = ['architecture/survey.md', 'architecture/survey.json', 'architecture/decision.md', 'architecture/decision.json', 'architecture/target.json', 'architecture/architecture-update.json']
function derivedNames(id) {
  if (id === 'architecture') return ARCHITECTURE_DELIVERABLES.slice()
  if (id === 'trd') return ['trd.md']
  if (id === 'repo-scoping') return ['repo-scoping.json']
  if (id === 'task-deps') return ['task-deps.json']
  const m = /^(recon|spec|tasks):([A-Za-z0-9._-]+)$/.exec(id)
  if (!m) return []
  const slug = m[2]
  if (m[1] === 'recon') return [`recon-${slug}.json`]
  if (m[1] === 'tasks') return [`tasks-${slug}.json`]
  return [`spec-${slug}.md`, `spec-${slug}.data-model.md`, `spec-${slug}.criteria.md`, `story-${slug}.json`]
}
function normalizeResume(r) {
  if (!r || typeof r !== 'object' || !Array.isArray(r.completed)) return null
  const names = r.names && typeof r.names === 'object' ? r.names : {}
  const phases = {}
  for (const id of r.completed) {
    if (!hasText(id)) continue
    phases[id] = { names: Array.isArray(names[id]) ? names[id].filter(hasText) : derivedNames(id) }
  }
  const stale = (Array.isArray(r.stale) ? r.stale : []).filter((e) => e && hasText(e.reason))
  return { root: r.root, dir: r.dir, epicId: r.epicId, phases, stale }
}
const RESUME = normalizeResume(a.resume)
for (const e of (RESUME && RESUME.stale) || []) {
  log(`STALE ${e.step || 'saved file'}${hasText(e.what) ? ` (${e.what})` : ''}: ${e.reason} — recreated, not reused`)
  runLedger.push({ phase: 'artifacts', event: 'stale', phaseId: e.step || null, artifacts: hasText(e.what) ? [e.what] : [], reason: e.reason })
}

const ARTIFACT_ROOT = repoPath || a.beadsRepoPath || null
const SS_ROOT = [RESUME && RESUME.root, a.projectRoot].filter(hasText).map((r) => r.replace(/\/+$/, ''))[0] || null
const ART_EPIC = String((RESUME && RESUME.epicId) || epicBeadId || subjectId || '')
  .replace(/[^A-Za-z0-9._-]+/g, '_')
  .replace(/^_+|_+$/g, '')
  .slice(0, 120) || null
const ART_DIR = SS_ROOT && RESUME && hasText(RESUME.dir)
  ? `${SS_ROOT}/${RESUME.dir.replace(/^\/+|\/+$/g, '')}`
  : ARTIFACT_ROOT && ART_EPIC
    ? `${ARTIFACT_ROOT}/.claude/workflow-runs/artifacts/${ART_EPIC}`
    : null
const ART_SCRIPT = hasText(a.artifactScript) ? a.artifactScript : null
const ART_ON = !!(ART_EPIC && ART_DIR && ART_SCRIPT)
const ART_REL = ART_ON && SS_ROOT && ART_DIR.startsWith(`${SS_ROOT}/`) ? ART_DIR.slice(SS_ROOT.length + 1) : null
const artPath = (name) => (ART_ON ? `${ART_DIR}/${name}` : null)
const PRD_INPUTS = hasText(prd.path) ? [prd.path] : []
const specFiles = (slug) => [`spec-${slug}.md`, `spec-${slug}.data-model.md`, `spec-${slug}.criteria.md`]
const TASK_DEPS_PHASE = 'task-deps'
const beadsArgs = { script: `${lifecycle.pluginRoot}/scripts/portfolio/depscore.py`, repo: emitTarget, epicId: epicBeadId, ...(SS_ROOT ? { projectRoot: SS_ROOT } : {}) }
const UNPERSISTED_STAGE = 'hierarchy-not-persisted'
artReport.dir = ART_ON ? ART_REL || ART_DIR : null
if (ART_ON) relayDir = `${ART_DIR}/relay`
artReport.epicId = ART_EPIC
log(ART_ON ? `Artifacts: ${ART_DIR}` : `ARTIFACTS DISABLED — no working directory or recorder (artifactScript=${JSON.stringify(ART_SCRIPT)})`)

/** Records a step as passed or reused; a passed step is appended to STEPS.md with artifactio.py step. */
async function acceptPhase(phaseId, status) {
  artPhases[phaseId] = status
  log(`ACCEPTED ${JSON.stringify({ phase: phaseId, status })}`)
  if (status !== 'passed' || !ART_ON) return
  const wrote = await runProgram(`steps:record:${phaseId}`, currentPhase || 'PRD', ['python3', ART_SCRIPT, 'step', ART_EPIC, phaseId], { tail: 5 })
  if (!wrote.ok || wrote.exitCode !== 0) log(`Step '${phaseId}' was NOT written to STEPS.md (${wrote.ok ? wrote.stderrTail || wrote.stdoutTail || `exit ${wrote.exitCode}` : wrote.error})`)
}
/** Returns the artifact descriptor a mini saves into, or undefined when artifacts are off. */
function artFor(phaseId, inputs, extra) {
  if (!ART_ON) return undefined
  return { dir: ART_DIR, relDir: ART_REL, epicId: ART_EPIC, script: ART_SCRIPT, phase: phaseId, inputs: (inputs || []).filter(hasText), ...(extra || {}) }
}
/** Returns the save instruction appended to a session prompt, or '' when artifacts are off; the script checks and records the file (saveResult). */
function persistBrief(art, name, what) {
  if (!art) return ''
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\nWrite ${what} to ${art.dir}/${name} with the Write tool, replacing the whole file if it exists (Read it first if the Write tool asks you to). Write no other file for this. The workflow checks the saved file against the result you return and records it; run no record command.`
}
/**
 * Saves a session's structured result under an artifact descriptor: makes the file hold exactly
 * `value` (the result as the runtime validated it; a differing or missing copy is rewritten through
 * relayrun.py, which refuses a copy that does not hash as built), then records it with the
 * artifact recorder. Returns whether both succeeded.
 */
async function saveResult(label, phaseName, art, name, value) {
  if (!art) return true
  const file = `${art.dir}/${name}`
  const saved = await relayKit.ensureJson(settleAgent, { label: `${label}:save`, phase: phaseName, runner: relayRunner(), file, value })
  if (!saved.ok) {
    log(`${label}: ${file} could not be made to hold the returned result: ${saved.error}`)
    return false
  }
  const rec = await runProgram(`${label}:record`, phaseName, ['python3', art.script, 'record', file, '--epic', art.epicId, '--phase', art.phase, ...(art.inputs.length ? ['--inputs', ...art.inputs] : [])], { tail: 5 })
  if (!rec.ok || rec.exitCode !== 0) {
    log(`${label}: the recorder did not record ${file} (${rec.ok ? rec.stderrTail || `exit ${rec.exitCode}` : rec.error})`)
    return false
  }
  return true
}
const slugCache = new Map()
/** Returns the stable artifact slug of a repository, suffixed when two repositories share a basename. */
function repoSlug(repo) {
  if (slugCache.has(repo)) return slugCache.get(repo)
  const base = String(repo || '').replace(/\/+$/, '').split('/').pop().replace(/[^A-Za-z0-9._-]+/g, '_') || 'repo'
  const taken = new Set(slugCache.values())
  let slug = base
  for (let n = 2; taken.has(slug); n++) slug = `${base}-${n}`
  slugCache.set(repo, slug)
  return slug
}
/** The steps whose saved files a step's saved files were built from. */
function stepUpstream(phaseId) {
  if (phaseId === 'repo-scoping' || phaseId === 'trd') return ['architecture']
  if (phaseId === TASK_DEPS_PHASE) return Object.keys(artPhases).filter((k) => k.startsWith('tasks:'))
  const m = /^(recon|spec|tasks):(.+)$/.exec(phaseId)
  if (!m) return []
  if (m[1] === 'recon') return ['architecture', 'repo-scoping']
  if (m[1] === 'spec') return ['trd', 'repo-scoping', `recon:${m[2]}`]
  return [`spec:${m[2]}`]
}
/** Returns the saved step to reuse, or null: a step is reused only when the resume ruled it fresh and every step it was built from was reused in this run. */
function resumeFresh(phaseId) {
  const hit = (RESUME && RESUME.phases[phaseId]) || null
  if (!hit) return null
  const redone = stepUpstream(phaseId).filter((up) => artPhases[up] !== 'reused')
  if (!redone.length) return hit
  const reason = `built from ${redone.map((up) => `${up} (${artPhases[up] || 'not reached'})`).join(', ')}, which this run did not reuse`
  log(`STALE ${phaseId} (${hit.names.join(', ') || 'no file named'}): ${reason} — recreated, not reused`)
  runLedger.push({ phase: 'artifacts', event: 'stale', phaseId, artifacts: hit.names, reason })
  return null
}
function reuseFrom(phaseId, hit) {
  runLedger.push({ phase: 'artifacts', event: 'reused', phaseId, artifacts: hit.names })
  log(`Phase '${phaseId}' reused from saved artifacts (${hit.names.join(', ') || 'none named'})`)
}

/** Returns the saved target's facts a resume needs ({ ok, subject, targetDir, deltaDir, deltaFiles, integratedFiles }) from depscore.py saved-target, or null when they cannot be read. */
async function readSavedTarget() {
  if (!RESUME || !ART_ON) return null
  const r = await runScript('replay:read-saved-target', 'Architecture', `saved-target --art-dir ${shellq(ART_DIR)}`)
  if (!r || r.error || r.found !== true) return null
  return r
}

/** Returns the saved span ruling a resumed run replays, from depscore.py saved-span, or null when it cannot be read. */
async function readSavedSpan() {
  const r = await runScript('replay:read-saved-span', 'Repo Scoping', `saved-span --art-dir ${shellq(ART_DIR)}`)
  if (!r || r.error || r.found !== true || !Array.isArray(r.placements) || !r.placements.some((p) => p && hasText(p.repoPath))) return null
  const placed = new Set([...r.placements.flatMap((p) => (p && Array.isArray(p.itemIds) ? p.itemIds : [])), ...(Array.isArray(r.noCode) ? r.noCode : []).map((n) => n && n.itemId)])
  const unplaced = deltaItems.filter((i) => !placed.has(i.id)).map((i) => i.id)
  if (unplaced.length) {
    log(`Repo Scoping: the saved placement does not place ${unplaced.join(', ')} of the delta; the span is ruled again`)
    return null
  }
  if (CONTROL_REPO && r.placements.some((p) => p && normRepo(p.repoPath) === CONTROL_REPO)) {
    log(`Repo Scoping: the saved placement places delta items in the control repository ${CONTROL_REPO}; the span is ruled again`)
    return null
  }
  return r
}

const PLACEMENT_CHECK_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdicts'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['repoPath', 'buildable', 'active', 'controlRepository', 'reason'],
        properties: {
          repoPath: { type: 'string' },
          buildable: { type: 'boolean' },
          active: { type: 'boolean' },
          controlRepository: { type: 'boolean' },
          reason: { type: 'string' },
        },
      },
    },
  },
}
/**
 * Asks the polyrepo-steward whether each span repository may hold placed work, and returns
 * { refusals, verdicts } or { error }. A placement in the control repository is refused without
 * asking; a repository the steward rules not buildable, not active or the control repository, or
 * gives no verdict for, is refused.
 */
async function checkPlacements(placements) {
  const byRepo = new Map()
  for (const p of placements) {
    const repo = normRepo(p && p.repoPath)
    if (!repo) continue
    const ids = Array.isArray(p.itemIds) ? p.itemIds.filter(hasText) : []
    byRepo.set(repo, [...(byRepo.get(repo) || []), ...ids])
  }
  const itemText = (ids) => {
    const known = new Map(deltaItems.map((i) => [i.id, i.element]))
    return ids.map((id) => (known.has(id) ? `${id} ${known.get(id)}` : id)).join('; ') || 'no item named'
  }
  const refusals = []
  const archRoot = normRepo(a.archPath)
  for (const [repo, ids] of byRepo) {
    if (CONTROL_REPO && repo === CONTROL_REPO) {
      refusals.push({ repoPath: repo, itemIds: ids, items: itemText(ids), reason: 'it is the control repository, which holds the pipeline and its tracker and is never a placement target' })
    } else if (archRoot && (archRoot === repo || archRoot.startsWith(`${repo}/`))) {
      refusals.push({ repoPath: repo, itemIds: ids, items: itemText(ids), reason: `it holds the architecture documentation (${archRoot}), which the pipeline never builds or deploys` })
    }
  }
  const asked = [...byRepo.keys()].filter((repo) => !refusals.some((r) => r.repoPath === repo))
  if (!asked.length) return { refusals, verdicts: [] }
  const got = await settleAgent(
    `Rule, from your records of this project's repositories and the live repositories, whether each repository below may hold work the pipeline builds and deploys. Change nothing.

${asked.map((repo) => `- ${repo}`).join('\n')}

For each one return: repoPath (exactly as listed above); buildable (true when your records say it holds code the pipeline builds and deploys, false for a repository that holds only documentation, templates, the pipeline itself or nothing the pipeline builds); active (true when its lifecycle in your records is active, false when it is deprecated, archived, or not in your records); controlRepository (true when it is the project's control repository, the one that holds the pipeline and its tracker); and reason (the record that decides it, in a sentence).`,
    { label: 'scope:check-placements', phase: 'Repo Scoping', agentType: 'agent-teams-workforce:polyrepo-steward', effort: 'low', schema: PLACEMENT_CHECK_SCHEMA }
  )
  if (!got) return { error: 'the polyrepo-steward returned no verdict on the span repositories' }
  const verdicts = (Array.isArray(got.verdicts) ? got.verdicts : []).filter((v) => v && hasText(v.repoPath))
  for (const repo of asked) {
    const ids = byRepo.get(repo)
    const v = verdicts.find((x) => normRepo(x.repoPath) === repo)
    if (!v) {
      refusals.push({ repoPath: repo, itemIds: ids, items: itemText(ids), reason: 'the polyrepo-steward gave no verdict for it' })
      continue
    }
    const faults = [
      v.controlRepository === true ? 'it is the control repository' : '',
      v.buildable !== true ? 'it is not a buildable repository' : '',
      v.active !== true ? 'it is not an active repository' : '',
    ].filter(Boolean)
    if (faults.length) refusals.push({ repoPath: repo, itemIds: ids, items: itemText(ids), reason: `${faults.join(', ')} (the polyrepo-steward: ${String(v.reason || 'no reason given').trim()})` })
  }
  return { refusals, verdicts }
}

enterPhase('Epic')
const epic = { key: epicRef.key || epicBeadId, ...epicRef, id: epicBeadId, type: 'epic' }
produced.epic = epic
recRuled(`Epic ${epicBeadId} adopted.`, { status: 'done' })

enterPhase('PRD Parse')
if (!hasText(prd.path)) {
  const why = 'the PRD carries no file path: depscore.py prd-parse reads the PRD from its file (prd.path)'
  return await holdForHuman('prd-parse', { reason: why }, [`Pass the PRD of ${epicBeadId} as a file in prd.path: ${why}`], 'the PRD file path has been supplied')
}
const prdParse = await runScript('prd:parse', 'PRD Parse', `prd-parse --prd ${shellq(prd.path)}`)
if (!prdParse || prdParse.error) {
  const died = dispatchDeaths('PRD Parse')
  return partial('prd-parse', {
    reason: `depscore.py prd-parse did not return a result for ${prd.path}: ${(prdParse && prdParse.error) || 'no result'}`,
    ...(died.length ? { dispatchFailed: true, dispatchFailures: died } : {}),
  })
}
if (prdParse.ok !== true) {
  const failedChecks = (Array.isArray(prdParse.failed) ? prdParse.failed : []).filter((f) => f && hasText(f.check))
  const named = failedChecks.map((f) => `${f.check} (${f.reason || 'no reason given'})`).join('; ') || 'prd-parse returned ok:false naming no check'
  return await holdForHuman(
    'prd-parse',
    { reason: `the PRD at ${prd.path} failed depscore.py prd-parse: ${named}`, failedChecks },
    [`Make the PRD at ${prd.path} readable: ${named}`],
    'the PRD has been fixed'
  )
}
const requirementHeadings = Array.isArray(prdParse.requirementHeadings) ? prdParse.requirementHeadings.filter(hasText) : []
produced.prdParse = { prd: prd.path, requirementHeadings }
recRuled(`PRD parsed by depscore.py prd-parse: ${requirementHeadings.length} requirement heading(s).`, { status: 'done' })

enterPhase('Architecture')
let architecture = null
const archHit = resumeFresh('architecture')
const savedTargetSummary = archHit && archHit.names.includes('architecture/target.json') ? await readSavedTarget() : null
if (archHit && savedTargetSummary && savedTargetSummary.ok === true && hasText(savedTargetSummary.targetDir)) {
  reuseFrom('architecture', archHit)
  await acceptPhase('architecture', 'reused')
  architecture = {
    ok: true,
    resumed: true,
    artifact: {
      subject: savedTargetSummary.subject,
      targetDir: savedTargetSummary.targetDir,
      deltaDir: savedTargetSummary.deltaDir,
      deltaFileCount: Number(savedTargetSummary.deltaFiles) || 0,
      integratedFileCount: Number(savedTargetSummary.integratedFiles) || 0,
      targetPath: artPath('architecture/target.json'),
      decisionPath: artPath('architecture/decision.md'),
      architectureUpdatePath: artPath('architecture/architecture-update.json'),
    },
  }
  recRuled(`Architecture reused from saved artifacts: target ${savedTargetSummary.targetDir}.`, { status: 'done' })
} else if (archHit) {
  log(`Architecture: the saved target in ${ART_DIR} was not read back; the architecture mini resumes from its saved work`)
}
if (!architecture) {
  const r = await settleWorkflow('agent-teams-workforce:architecture', {
    prd: { id: prd.id, title: prd.title, path: prd.path, body: prdByPath ? undefined : prd.body },
    epic: { id: epicBeadId },
    archPath: a.archPath,
    subject: hasText(a.architectureSubject) ? a.architectureSubject : undefined,
    repoPath,
    maxRounds: Number.isInteger(a.maxArchitectureRounds) ? a.maxArchitectureRounds : undefined,
    depscore: { script: `${lifecycle.pluginRoot}/scripts/portfolio/depscore.py`, repo: emitTarget },
    artifacts: artFor('architecture', PRD_INPUTS, { beadId: epicBeadId }),
  })
  architecture = r && r.ok === true
    ? { ok: true, artifact: r }
    : {
        ok: false,
        artifact: r || null,
        reason: (r && (r.reason || r.error)) || 'the architecture mini returned nothing',
        ...(!r || r.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (r && r.dispatchFailures) || dispatchDeaths('Architecture') } : {}),
      }
  if (architecture.ok) {
    const changed = r.architectureUpdate ? Number(r.architectureUpdate.touched) || 0 : 0
    recRuled(`Architecture approved for ${r.subject}: target ${r.targetDir}; ${changed} effective file(s) integrated.`, { status: 'done' })
    await acceptPhase('architecture', 'passed')
  }
}
produced.architecture = (architecture.artifact || null)
if (!architecture.ok) {
  const art = architecture.artifact || {}
  if (art.stage === 'input') {
    const noArch = /archPath|ATW_ARCH_PATH/.test(architecture.reason)
    return await holdForHuman(
      'architecture',
      architecture,
      [`architecture refused its input: ${architecture.reason}${noArch ? ' Set ATW_ARCH_PATH to the architecture directory (the folder holding arc42/, target/ and built/) for the pipeline host.' : ''}`],
      noArch ? 'the architecture path is configured' : 'what the refusal names has been supplied'
    )
  }
  if (art.stage === 'owner-concern') {
    const actions = Array.isArray(art.requiredHumanActions) && art.requiredHumanActions.length
      ? art.requiredHumanActions.slice()
      : [`The architecture of ${epicBeadId} found business requirements no design can satisfy together, or a contradiction in the architecture: ${architecture.reason}`]
    return await holdForHuman('architecture', architecture, actions, 'the PRD or the architecture says which side holds')
  }
  // Any other architecture stop that names actions for the owner holds the Epic: a re-dispatch meets the same stop.
  if (Array.isArray(art.requiredHumanActions) && art.requiredHumanActions.length) {
    return await holdForHuman('architecture', { ...architecture, headline: art.headline }, art.requiredHumanActions.slice(), 'what the actions above name has been done')
  }
  return partial('architecture', architecture)
}
const archArt = architecture.artifact || {}
if (!hasText(archArt.targetDir) || !hasText(archArt.deltaDir)) {
  return partial('architecture', { reason: 'the architecture result names no target and delta directory, which every later phase reads' })
}
const deltaList = await runScript('arch:delta', 'Architecture', `arch-delta --delta-dir ${shellq(archArt.deltaDir)}`)
if (!deltaList || deltaList.error || deltaList.ok !== true) {
  const why = deltaList && !deltaList.error
    ? `depscore.py arch-delta refused the delta at ${archArt.deltaDir}: ${(deltaList.refusals || []).join('; ') || 'no reason given'}`
    : `depscore.py arch-delta did not list the delta at ${archArt.deltaDir}: ${(deltaList && deltaList.error) || 'no result'}`
  return partial('architecture', { reason: why })
}
const deltaItems = (Array.isArray(deltaList.items) ? deltaList.items : [])
  .filter((i) => i && hasText(i.id) && hasText(i.element))
  .map((i) => ({ id: i.id, element: i.element, views: Array.isArray(i.views) ? i.views.filter(hasText) : [] }))
/** The approved target and its delta, as every later phase reads them. */
const delta = {
  subject: archArt.subject || null,
  targetDir: archArt.targetDir,
  deltaDir: archArt.deltaDir,
  decisionPath: archArt.decisionPath || artPath('architecture/decision.md'),
  items: deltaItems,
}
produced.delta = delta
log(`Delta: ${deltaItems.length} item(s) in ${delta.deltaDir}`)

let scoping = null
/** Returns { scoping, scopeHit }: the saved placement on a resume, else a fresh one. */
async function runRepoScoping() {
  const scopeHit = resumeFresh('repo-scoping')
  const saved = scopeHit && ART_ON ? await readSavedSpan() : null
  if (scopeHit && !saved) log(`Repo Scoping: the saved ruling in ${ART_DIR} was not read back; the span is ruled again`)
  if (saved) {
    const placements = saved.placements
      .filter((p) => p && hasText(p.repoPath))
      .map((p) => ({ ...p, repoPath: p.repoPath.trim(), itemIds: Array.isArray(p.itemIds) ? p.itemIds : [], frontend: p.frontend === true }))
    const spanRepos = []
    for (const p of placements) if (!spanRepos.includes(p.repoPath)) spanRepos.push(p.repoPath)
    return {
      scopeHit,
      scoping: {
        ok: true,
        resumed: true,
        repos: spanRepos,
        placements,
        noCode: Array.isArray(saved.noCode) ? saved.noCode : [],
        createdRepos: [],
        spanRationale: saved.spanRationale || null,
      },
    }
  }
  const ruled = await settleWorkflow('agent-teams-workforce:repo-scoping', {
    pluginRoot: lifecycle.pluginRoot,
    artifacts: artFor('repo-scoping', [...PRD_INPUTS, artPath('architecture/decision.md'), artPath('architecture/target.json')]),
    prd: { id: prd.id, title: prd.title, path: prd.path },
    delta,
    epic: { key: epic.key, title: epic.title },
  })
  return { scoping: ruled, scopeHit: null }
}

/** The architecture the TRD is built from, as trd-authoring hands it to its author: this Epic's target and delta, section 2, and the effective views (subject or shows) of the elements the delta changes. */
const ARC42_DIR = hasText(a.archPath) ? `${a.archPath.replace(/\/+$/, '')}/arc42` : null
const deltaElements = [...new Set(deltaItems.map((i) => i.element.trim()))].sort()
const TRD_INPUTS = [
  ...PRD_INPUTS,
  artPath('architecture/decision.md'),
  artPath('architecture/target.json'),
  artPath('architecture/architecture-update.json'),
  artPath('architecture/survey.json'),
  delta.targetDir,
  ARC42_DIR ? `${ARC42_DIR}/02-architecture-constraints` : null,
  ARC42_DIR && deltaElements.length ? `arch-views:${JSON.stringify({ dir: ARC42_DIR, elements: deltaElements })}` : null,
].filter(hasText)
/** Returns { mode: 'resumed' | 'ran', trdAuthoring: { ok, artifact } }. */
async function runTrdAuthoring() {
  const trdHit = resumeFresh('trd')
  if (trdHit && trdHit.names.includes('trd.md')) {
    reuseFrom('trd', trdHit)
    return {
      mode: 'resumed',
      trdAuthoring: {
        ok: true,
        artifact: {
          trdPath: artPath('trd.md'),
          filingPath: hasText(a.trdPath) && a.trdPath.startsWith('/') ? a.trdPath : null,
          trd: { trdPath: artPath('trd.md'), summary: '' },
        },
      },
    }
  }
  const r = await settleWorkflow('agent-teams-workforce:trd-authoring', {
    pluginRoot: lifecycle.pluginRoot,
    prd: { id: prd.id, title: prd.title, content: prd.body, path: prd.path, acceptanceCriteria: prd.acceptanceCriteria },
    architecture: delta,
    surveyPath: artPath('architecture/survey.json'),
    archPath: a.archPath,
    trdPath: a.trdPath,
    artifacts: artFor('trd', TRD_INPUTS, { beadId: epicBeadId }),
    repoPath,
  })
  return {
    mode: 'ran',
    trdAuthoring: r && r.ok === true
      ? { ok: true, artifact: r }
      : {
          ok: false,
          artifact: r || null,
          reason: (r && (r.reason || r.error)) || 'trd-authoring returned nothing',
          ...(!r || r.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (r && r.dispatchFailures) || dispatchDeaths('TRD Authoring') } : {}),
        },
  }
}

const [scopeSettled, trdSettled] = await parallel([() => runRepoScoping(), () => runTrdAuthoring()])
const trdAuthoring = (trdSettled && trdSettled.trdAuthoring) || { ok: false, artifact: null, reason: 'TRD authoring threw' }
if (trdAuthoring.ok) await acceptPhase('trd', trdSettled.mode === 'resumed' ? 'reused' : 'passed')

enterPhase('Repo Scoping')
if (!scopeSettled) return partial('repo-scoping', { reason: 'repo scoping threw' })
scoping = scopeSettled.scoping
if (scoping && scoping.ledger) runLedger.push(scoping.ledger)
produced.repoScoping = scoping || null
if (!scoping || scoping.ok === false) {
  return partial('repo-scoping', {
    reason: (scoping && scoping.reason) || 'repo scoping returned nothing',
    ...(!scoping || scoping.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (scoping && scoping.dispatchFailures) || [] } : {}),
  })
}
const createdNames = (Array.isArray(scoping.createdRepos) ? scoping.createdRepos : []).map((c) => c && c.name).filter(hasText).map((n) => n.trim())
if (createdNames.length) {
  const namedCheck = await runScript('scope:created-named', 'Repo Scoping', `arch-target-names --target-dir ${shellq(delta.targetDir)} --names ${shellq(createdNames.join(','))}`)
  produced.createdNamed = namedCheck
  if (!namedCheck || namedCheck.error) return partial('repo-scoping', { reason: `depscore.py arch-target-names did not check the repositories the polyrepo-steward created: ${(namedCheck && namedCheck.error) || 'no result'}` })
  const unnamed = Array.isArray(namedCheck.unnamed) ? namedCheck.unnamed.filter(hasText) : []
  if (unnamed.length) {
    return await holdForHuman(
      'repo-scoping',
      { reason: `the polyrepo-steward created repositories the approved target at ${delta.targetDir} does not name: ${unnamed.join(', ')}`, unnamedRepos: unnamed },
      unnamed.map((n) => `The polyrepo-steward created ${n} for ${epicBeadId}, and the approved target at ${delta.targetDir} does not name it. Decide whether ${n} stays; the polyrepo-steward removes it on your approval.`),
      'each repository the target does not name has been ruled on'
    )
  }
}
const placementCheck = await checkPlacements(Array.isArray(scoping.placements) ? scoping.placements : [])
produced.placementCheck = placementCheck
if (placementCheck.error) {
  const died = dispatchDeaths('Repo Scoping')
  return partial('repo-scoping', { reason: placementCheck.error, ...(died.length ? { dispatchFailed: true, dispatchFailures: died } : {}) })
}
if (placementCheck.refusals.length) {
  const named = placementCheck.refusals.map((r) => `${r.repoPath}: ${r.reason}; delta items placed there: ${r.items}`)
  return await holdForHuman(
    'repo-scoping',
    { reason: `the span names repositories that may not hold placed work — ${named.join(' | ')}`, refusals: placementCheck.refusals },
    named.map((n) => `Delta items of ${epicBeadId} are placed in a repository that may not hold them. ${n}. Correct the polyrepo-steward's records of that repository, or place these items in a buildable, active repository.`),
    "each refused placement has been resolved"
  )
}
recRuled(`Placement check: the polyrepo-steward ruled ${placementCheck.verdicts.length} span repositor(ies) buildable and active.`)
if (scoping.resumed === true) reuseFrom('repo-scoping', scopeSettled.scopeHit)
await acceptPhase('repo-scoping', scoping.resumed === true ? 'reused' : 'passed')
repos = Array.isArray(scoping.repos) ? scoping.repos : []
recRuled(`Repo span: ${repos.join(', ') || 'no repository'}, the repositories the delta changes.`, { status: 'done' })
if (!repos.length) return partial('repo-scoping', { reason: 'the span names no repository' })
const createdRepos = (Array.isArray(scoping.createdRepos) && scoping.createdRepos) || []
log(`Span: ${repos.join(', ')}${createdRepos.length ? `; created by the polyrepo-steward: ${createdRepos.map((c) => (c && c.name) || String(c)).join(', ')}` : ''}`)

enterPhase('TRD Authoring')
if (trdAuthoring.ok && trdAuthoring.artifact && hasText(trdAuthoring.artifact.filingPath)) artReport.filing['trd.md'] = trdAuthoring.artifact.filingPath
produced.trdAuthoring = (trdAuthoring.artifact || null)
if (!trdAuthoring.ok) {
  if (trdAuthoring.artifact && trdAuthoring.artifact.stage === 'input') {
    return await holdForHuman('trd-authoring', trdAuthoring, [`trd-authoring refused its input: ${trdAuthoring.reason}`], 'what the refusal names has been supplied')
  }
  return partial('trd-authoring', trdAuthoring)
}
recRuled(`TRD ${trdSettled.mode === 'resumed' ? 'reused' : 'authored'}${hasText(trdAuthoring.artifact.trdPath) ? ` at ${trdAuthoring.artifact.trdPath}` : ''}.`, { status: 'done' })
const trd = trdAuthoring.artifact.trd
const prdSummaryFallback = () => (hasText(prd.path) ? `The PRD is the document at ${prd.path}.` : prd.body || '')

enterPhase('Spec Authoring')
const idleText = (recon) => (Array.isArray(recon && recon.idle) ? recon.idle : []).map((r) => `${r.id} [${r.status}${r.plannedBy ? ` by ${r.plannedBy}` : ''}]`).join('; ')
const workIds = (recon) => (Array.isArray(recon && recon.work) ? recon.work : [])
/** The delta detailing as a pointer: its file, and the ids of the items that make work and that do not. The items stay in the file. */
const renderInventory = (recon, repo) => {
  const work = workIds(recon)
  const idle = idleText(recon)
  const idleLine = idle ? `\n\nNo specification for these items: ${idle}.` : ''
  const file = `THE DELTA DETAILING for ${repo} is the file ${recon.reconPath}. Read it: its \`items\` give each delta item placed here its status, the \`from\` state the code on main holds, the \`to\` state the approved target makes it, its surface and its file:line evidence.`
  if (!work.length) return `${file}\n\nNo item placed here is marked add, modify or remove, so there is no change to specify.${idleLine}`
  return (
    `${file}\n\nSpecify the change for these items, and only these: ${work.join(', ')}.\n` +
    '  add    — the element is new here: specify it.\n' +
    '  modify — the element exists: specify the change from what it is to what the target makes it.\n' +
    '  remove — the element is removed: specify its removal.' +
    idleLine
  )
}
const renderDependencies = (recon) => {
  if (!recon || recon.dependenciesCurrent !== false) return ''
  return `UPSTREAM DEPENDENCY CHANGES since the delta was designed: ${recon.dependencyFindings} finding(s) in \`dependencyChanges.changeFindings\` of ${recon.reconPath}. Read them and specify against what is true now.`
}
const renderUiAuthority = (recon) => {
  const ui = uiItemsOf(recon)
  if (!ui.length) return ''
  const of = (source) => ui.filter((u) => u.designSource === source)
  const bundled = of('bundle')
  const cds = of('cds')
  const none = of('none')
  return [
    `UI ITEMS — each \`ui\` item takes one design source, recorded in \`uiAuthority.uiItems\` of ${recon.reconPath}.`,
    bundled.length
      ? `bundle — a cds bundle the owner supplied packages the item. Specify it by reference to that bundle's \`spec/build-spec.md\`; styling is that bundle's own stylesheet set (its styles/), and the spec adds no new CSS, tokens or component stylesheet:\n${bundled.map((u) => `  - ${u.id}: ${u.buildSpec}${u.sections.length ? ` (Sections ${u.sections.join(', ')})` : ''}`).join('\n')}`
      : '',
    cds.length
      ? `cds — the item changes design and no bundle packages it. The implementing agent designs it with the CDS design system; specify its behaviour and content, and state that its design comes from the CDS design system: ${cds.map((u) => u.id).join(', ')}`
      : '',
    none.length
      ? `none — the item changes no design (copy, or data wired into an existing element). Specify the change; it needs no design work: ${none.map((u) => u.id).join(', ')}`
      : '',
  ].filter(hasText).join('\n\n')
}
/** Returns each `ui` work item of a detailing with its design source, and the bundle and build spec of a bundle item. */
function uiItemsOf(recon) {
  return (Array.isArray(recon && recon.uiWork) ? recon.uiWork : []).map((u) => ({
    id: u.id,
    element: null,
    designSource: hasText(u.designSource) ? u.designSource : u.buildSpec ? 'bundle' : 'cds',
    bundle: u.bundle || null,
    buildSpec: u.buildSpec || null,
    sections: Array.isArray(u.sections) ? u.sections.filter(hasText) : [],
  }))
}
const specConstraints = (recon, repo) => {
  const c = [renderInventory(recon, repo), renderDependencies(recon), renderUiAuthority(recon)].filter(hasText)
  return c.length ? c : undefined
}
const placementOf = (repo) => (Array.isArray(scoping.placements) ? scoping.placements : []).filter((p) => p && hasText(p.repoPath) && p.repoPath.trim() === String(repo).trim())
/** Returns the delta items repo scoping placed in one repository. */
function itemsPlacedIn(repo) {
  const ids = new Set(placementOf(repo).flatMap((p) => (Array.isArray(p.itemIds) ? p.itemIds : [])))
  return deltaItems.filter((i) => ids.has(i.id))
}
/** Returns the prd-reconciliation arguments for one repository. */
const DESIGN_SYSTEM = designSystemArg
function reconArgs(repo, slug, reconReplay) {
  return {
    items: itemsPlacedIn(repo),
    delta: { targetDir: delta.targetDir, deltaDir: delta.deltaDir },
    artifacts: artFor(`recon:${slug}`, [...PRD_INPUTS, artPath('architecture/target.json'), artPath('repo-scoping.json'), artPath('architecture/survey.json'), `git-main:${repo}`], { slug }),
    depscore: beadsArgs.script,
    ...(reconReplay ? { replay: reconReplay } : {}),
    prd: { id: prd.id, title: prd.title, path: prd.path, repoPath: repo },
    repos: [repo],
    surveyPath: artPath('architecture/survey.json'),
    dependencies: a.dependencies,
    uiRepo: placementOf(repo).some((p) => p.frontend === true),
    ...(DESIGN_SYSTEM.mocksDir ? { mocksDir: DESIGN_SYSTEM.mocksDir } : {}),
    ...(DESIGN_SYSTEM.packagesDir ? { packagesDir: DESIGN_SYSTEM.packagesDir } : {}),
    ...(DESIGN_SYSTEM.shellsDir ? { shellsDir: DESIGN_SYSTEM.shellsDir } : {}),
  }
}
/** Returns the spec-authoring arguments for one repository. */
function specArgs(repo, storyKey, slug, recon) {
  return {
    spec: a.spec || {
      id: prd.id,
      title: prd.title,
      summary: (trd && trd.summary) || prdSummaryFallback(),
      repoPath: repo,
    },
    trd,
    architecture: { targetDir: delta.targetDir, deltaDir: delta.deltaDir },
    accessPatterns: a.accessPatterns,
    repoPath: repo,
    storyKey,
    epic,
    artifacts: artFor(`spec:${slug}`, [artPath('trd.md'), artPath('repo-scoping.json'), artPath(`recon-${slug}.json`), ...PRD_INPUTS], { slug }),
    beads: beadsArgs,
    detailingPath: recon.reconPath,
    constraints: specConstraints(recon, repo),
    ...(uiItemsOf(recon).length ? { uiItems: uiItemsOf(recon) } : {}),
  }
}
/** Details one repository's delta items, then authors its Spec and Story, or replays the saved Story; returns { repo, recon, specAuthoring }. */
async function authorSpecForRepo(repo, repoIndex) {
  const storyKey = `S${repoIndex + 1}`
  const slug = repoSlug(repo)
  const specPhase = `spec:${slug}`
  const reconPhase = `recon:${slug}`
  const reconHit = resumeFresh(reconPhase)
  const reconReplay = reconHit && ART_ON && reconHit.names.includes(`recon-${slug}.json`) ? { files: { recon: artPath(`recon-${slug}.json`) } } : null
  const recon = await settleWorkflow('agent-teams-workforce:prd-reconciliation', reconArgs(repo, slug, reconReplay))
  if (recon && recon.ledger) runLedger.push(recon.ledger)
  if (!recon || recon.ok !== true) {
    const why = `the detailing of ${repo} failed, so its Spec is not authored: ${(recon && recon.reason) || 'prd-reconciliation returned nothing'}`
    log(`Spec Authoring for ${repo}: ${why}`)
    return {
      repo,
      recon: null,
      specAuthoring: {
        ok: false,
        stage: (recon && hasText(recon.stage) && recon.stage !== 'input' ? recon.stage : 'detailing'),
        reason: why,
        ...(!recon || recon.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (recon && recon.dispatchFailures) || [] } : {}),
      },
    }
  }
  await acceptPhase(reconPhase, reconReplay && recon.resumed === true ? 'reused' : 'passed')
  const specHit = resumeFresh(specPhase)
  const args = specArgs(repo, storyKey, slug, recon)
  const r = await settleWorkflow('agent-teams-workforce:spec-authoring', specHit ? { ...args, replay: true } : args)
  const specAuthoring = r && r.ok === true && r.story
    ? { ok: true, artifact: r }
    : {
        ok: false,
        stage: (r && r.stage) || null,
        reason: (r && (r.reason || r.error)) || (r ? 'spec-authoring returned no story' : 'spec-authoring returned nothing'),
        ...(!r || r.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (r && r.dispatchFailures) || [] } : {}),
      }
  if (specAuthoring.ok && specHit) reuseFrom(specPhase, specHit)
  if (specAuthoring.ok) await acceptPhase(specPhase, specHit ? 'reused' : 'passed')
  return { repo, recon, specAuthoring }
}
for (const r of repos) repoSlug(r)
const specResults = await parallel(repos.map((repo, repoIndex) => () => authorSpecForRepo(repo, repoIndex)))
const reconByRepo = new Map()
const specPairs = []
const specFailures = []
for (const [repoIndex, repo] of repos.entries()) {
  const settled = specResults[repoIndex]
  if (settled && settled.recon) reconByRepo.set(repo, settled.recon)
  const specAuthoring = settled && settled.specAuthoring
  if (!specAuthoring || !specAuthoring.ok) {
    specFailures.push({
      repoPath: repo,
      stage: (specAuthoring && specAuthoring.stage) || null,
      reason: (specAuthoring && specAuthoring.reason) || 'the spec-authoring phase threw',
      dispatchFailed: !!(specAuthoring && specAuthoring.dispatchFailed),
      dispatchFailures: (specAuthoring && specAuthoring.dispatchFailures) || [],
    })
    log(`Spec Authoring FAILED for ${repo}: ${(specAuthoring && specAuthoring.reason) || 'threw'}`)
    continue
  }
  const art = specAuthoring.artifact
  specPairs.push({
    repoPath: repo,
    spec: art,
    story: { ...art.story, decisionIds: Array.isArray(art.decisionIds) ? art.decisionIds : [] },
  })
  recRuled(`Spec and Story ${art.story.key || art.story.title} for ${repo}.`)
}
produced.reconciliationByRepo = Array.from(reconByRepo, ([rp, recon]) => ({ repoPath: rp, recon }))
produced.specPairs = specPairs
produced.specFailures = specFailures
if (!specPairs.length) {
  return partial('spec-authoring', {
    reason: `no repo produced a spec — ${specFailures.map((x) => `${x.repoPath}: ${x.reason}`).join('; ')}`,
    specFailures,
    ...(specFailures.every((x) => x.dispatchFailed) ? { dispatchFailed: true, dispatchFailures: specFailures.flatMap((x) => x.dispatchFailures) } : {}),
  })
}
recRuled(`${specPairs.length} of ${repos.length} repo(s) specified.`, { status: 'done' })

enterPhase('Task Decomposition')
const inventoryBrief = (repo) => {
  const recon = reconByRepo.get(repo)
  if (!recon || !hasText(recon.reconPath)) return ''
  return (
    '\n\n=== DELTA DETAILING — what needs a Task ===\n' +
    `The detailing is the file ${recon.reconPath}: read it for each item's element, its from and to state, its surface and its evidence.\n` +
    `Needs a Task (add, modify, remove): ${workIds(recon).join(', ') || 'none'}\n` +
    `No Task (done, or planned by another Epic's bead): ${idleText(recon) || 'none'}`
  )
}
const stories = specPairs.map((p) => p.story)
const decompositions = []
const decompositionFailures = []
const tasks = []
/** Returns the spec documents of one Story as { path, ref }. */
function specDocsFor(pair) {
  const slug = repoSlug(pair.repoPath)
  const out = []
  const seen = new Set()
  const add = (path, ref) => {
    if (!hasText(path) || seen.has(path)) return
    seen.add(path)
    out.push({ path, ref: ref || null })
  }
  if (ART_ON) for (const name of specFiles(slug)) add(artPath(name), ART_REL ? `${ART_REL}/${name}` : null)
  const sp = pair.spec || {}
  for (const part of [sp.apiSpec, sp.dataModelSpec, sp.eventContracts, sp.errorSpec]) {
    for (const p of part && Array.isArray(part.artifactPaths) ? part.artifactPaths : []) {
      if (hasText(p)) add(p, SS_ROOT && p.startsWith(`${SS_ROOT}/`) ? p.slice(SS_ROOT.length + 1) : null)
    }
  }
  return out
}
/** Returns the task-decomposition arguments for one Story. */
function decompArgs(pair) {
  const slug = repoSlug(pair.repoPath)
  const docs = specDocsFor(pair)
  const summary = (pair.spec && pair.spec.apiSpec && pair.spec.apiSpec.summary) || (trd && trd.summary) || prdSummaryFallback()
  return {
    spec: {
      id: prd.id,
      title: prd.title,
      description: `SUMMARY (navigation aid only — the contract is in the spec documents):\n${summary}` + inventoryBrief(pair.repoPath),
      source: 'spec-authoring output',
      repoPath: pair.repoPath,
    },
    specDocs: docs,
    ...(reconByRepo.get(pair.repoPath) && hasText(reconByRepo.get(pair.repoPath).reconPath) ? { detailingPath: reconByRepo.get(pair.repoPath).reconPath } : {}),
    story: { id: pair.story.id, key: pair.story.key, title: pair.story.title },
    pluginRoot: lifecycle.pluginRoot,
    artifacts: artFor(`tasks:${slug}`, [...docs.map((d) => d.path), artPath(`story-${slug}.json`)], { slug }),
    beads: beadsArgs,
    ...(DESIGN_SYSTEM.packagesDir ? { packagesDir: DESIGN_SYSTEM.packagesDir } : {}),
  }
}
/** Decomposes one Story and writes its Tasks, or writes the saved task set when the step is complete; returns { ok, artifact } or { ok: false, stage, reason }. */
async function decomposeStory(pair) {
  const slug = repoSlug(pair.repoPath)
  const tasksPhase = `tasks:${slug}`
  const tasksHit = resumeFresh(tasksPhase)
  const replay = !!(tasksHit && ART_ON && tasksHit.names.includes(`tasks-${slug}.json`))
  const r = await settleWorkflow('agent-teams-workforce:task-decomposition', replay ? { ...decompArgs(pair), replay: true } : decompArgs(pair))
  if (r && r.ok === true) {
    if (replay) reuseFrom(tasksPhase, tasksHit)
    await acceptPhase(tasksPhase, replay ? 'reused' : 'passed')
    return { ok: true, artifact: r }
  }
  return {
    ok: false,
    stage: (r && r.stage) || null,
    reason: (r && (r.reason || r.error)) || (r ? 'the decomposition produced no Task' : 'task-decomposition returned nothing'),
    ...(!r || r.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (r && r.dispatchFailures) || [] } : {}),
  }
}
const decompResults = await parallel(specPairs.map((pair) => () => decomposeStory(pair)))
for (const [pairIndex, pair] of specPairs.entries()) {
  const decomposition = decompResults[pairIndex]
  if (!decomposition || !decomposition.ok) {
    decompositionFailures.push({
      repoPath: pair.repoPath,
      storyKey: pair.story.key || null,
      stage: (decomposition && decomposition.stage) || null,
      reason: (decomposition && decomposition.reason) || 'the task-decomposition phase threw',
      dispatchFailed: !!(decomposition && decomposition.dispatchFailed),
      dispatchFailures: (decomposition && decomposition.dispatchFailures) || [],
    })
    log(`Task Decomposition FAILED for ${pair.story.key || pair.repoPath}: ${(decomposition && decomposition.reason) || 'threw'}`)
    continue
  }
  decompositions.push({ repoPath: pair.repoPath, storyKey: pair.story.key || null, artifact: decomposition.artifact })
  const storyKeyForTasks = pair.story.key
  const storyTasks = decomposition.artifact.tasks
  for (const t of storyTasks) {
    tasks.push({
      key: `${storyKeyForTasks}-${t.key}`,
      id: t.id,
      elabKey: t.elabKey,
      action: t.action,
      title: t.title,
      parentStoryId: pair.story.id,
      storyKey: storyKeyForTasks,
      dependsOn: (Array.isArray(t.dependsOn) ? t.dependsOn : []).map((d) => `${storyKeyForTasks}-${d}`),
    })
  }
  recRuled(`Story ${storyKeyForTasks} (${pair.repoPath}) decomposed into ${storyTasks.length} Task(s).`)
}
produced.stories = stories
produced.decompositions = decompositions
produced.decompositionFailures = decompositionFailures
produced.tasks = tasks
if (!decompositions.length) {
  return partial('task-decomposition', {
    reason: `no Story produced tasks — ${decompositionFailures.map((x) => `${x.storyKey || x.repoPath}: ${x.reason}`).join('; ')}`,
    decompositionFailures,
    ...(decompositionFailures.every((x) => x.dispatchFailed) ? { dispatchFailed: true, dispatchFailures: decompositionFailures.flatMap((x) => x.dispatchFailures) } : {}),
  })
}

const crossStory = { ran: false, reason: null, note: null, edges: [], rejected: 0, written: null }
if (decompositions.filter((d) => Array.isArray(d.artifact.tasks) && d.artifact.tasks.length).length < 2) {
  crossStory.note = 'the Tasks sit in one Story or none'
} else {
  crossStory.ran = true
  const depsHit = resumeFresh(TASK_DEPS_PHASE)
  const spanArgs = `--dir ${shellq(ART_DIR)} --repos ${shellq(repos.join(','))}`
  const edgeOut = (name) => `--out ${shellq(`${ART_DIR}/task-edges/${name}.json`)}`
  /** Writes the saved Task edges between Stories to beads with depscore.py write-all-task-edges; returns its checked summary or null. */
  const writeEdges = async () => {
    const out = await runScript('beads:write-all-task-edges', 'Task Decomposition', `write-all-task-edges --epic ${shellq(epicBeadId)} ${spanArgs} ${edgeOut('all')}`)
    if (out.error) {
      crossStory.reason = `depscore.py write-all-task-edges did not write the Task edges between Stories: ${out.error}`
      return null
    }
    return out.summary && out.summary.blockers ? out.summary : null
  }
  let ran = null
  if (!ART_ON) {
    crossStory.reason = 'no artifact working directory is configured, so there is no saved task-deps.json to write'
  } else if (depsHit && depsHit.names.includes('task-deps.json')) {
    reuseFrom(TASK_DEPS_PHASE, depsHit)
    await acceptPhase(TASK_DEPS_PHASE, 'reused')
    ran = await writeEdges()
  } else {
    const byStory = new Map()
    for (const t of tasks) {
      if (!byStory.has(t.storyKey)) byStory.set(t.storyKey, [])
      byStory.get(t.storyKey).push(t)
    }
    const pairOf = new Map(specPairs.map((p) => [p.story.key, p]))
    const listing = Array.from(byStory, ([storyKey, list]) => {
      const pair = pairOf.get(storyKey)
      const repo = (pair && pair.repoPath) || 'repository not recorded'
      const file = pair ? artPath(`tasks-${repoSlug(pair.repoPath)}.json`) : null
      return (
        `Story ${storyKey} [${repo}]${file ? ` — descriptions, spec sections, requirements and surfaces: ${file} (Task ${storyKey}-<key> is the task with that key there)` : ''}\n` +
        list
          .map((t) => `- ${t.key}: ${t.title}${t.dependsOn.length ? `\n    already depends on (same Story): ${t.dependsOn.join(', ')}` : ''}`)
          .join('\n')
      )
    }).join('\n\n')
    const depsInputs = specPairs.map((p) => artPath(`tasks-${repoSlug(p.repoPath)}.json`)).filter(Boolean)
    const mapped = await settleAgent(
      `Derive the Task-to-Task build dependencies whose two ends are Tasks in different Stories of Epic ${epic.id} — ${epic.title || ''}. Each Story is one repository's slice; the edges inside each Story are already drawn and listed. Read each Story's saved task file named below for what each Task builds. Return ONLY edges whose two ends are Tasks in DIFFERENT Stories, referencing Tasks by their key exactly as given. An edge "from -> to" means "from must be built before to".

Add an edge ONLY where a Task cannot be built until a Task in another Story is built: an API it consumes that the other Task provides, an event contract whose producer must publish first, a table, bucket or IAM grant the other repository provisions. Sharing a domain or this Epic is not a dependency. Type each edge as data, contract, infrastructure or event-flow and justify it in one line.

The whole Task graph — the edges already drawn plus yours — must be acyclic. If the only honest reading implies a cycle, set acyclic=false, name the cycle as Task keys, and return no edges.

Do NOT add, remove, split or rescope Tasks. Do NOT write code.

${listing}${persistBrief(artFor(TASK_DEPS_PHASE, depsInputs), 'task-deps.json', 'your complete answer (edges, acyclic, cycle) as ONE JSON object')}

Write nothing to beads: the workflow writes the edges from that file.`,
      {
        label: 'sequence:cross-story-tasks',
        effort: 'medium',
        phase: 'Task Decomposition',
        agentType: 'task-dependency-mapper',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['edges', 'acyclic'],
          properties: {
            edges: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['from', 'to', 'kind', 'reason'],
                properties: {
                  from: { type: 'string' },
                  to: { type: 'string' },
                  kind: { type: 'string', enum: ['data', 'contract', 'infrastructure', 'event-flow'] },
                  reason: { type: 'string' },
                },
              },
            },
            acyclic: { type: 'boolean' },
            cycle: { type: 'array', items: { type: 'string' } },
          },
        },
      }
    )
    if (!mapped) {
      crossStory.reason = 'the mapper returned nothing, so no Task edge between Stories was derived'
    } else if (mapped.acyclic === false) {
      crossStory.reason = `the mapper reported a cycle across Stories (${(mapped.cycle || []).join(' -> ') || 'not named'}) and returned no edges`
    } else if (!(await saveResult('sequence:cross-story-tasks', 'Task Decomposition', artFor(TASK_DEPS_PHASE, depsInputs), 'task-deps.json', mapped))) {
      crossStory.reason = `the Task edges between Stories the mapper returned could not be saved to ${artPath('task-deps.json')}`
    } else {
      await acceptPhase(TASK_DEPS_PHASE, 'passed')
      ran = await writeEdges()
    }
  }
  if (ran) {
    const plan = ran
    if (plan) {
      crossStory.edges = Object.entries(plan.blockers).flatMap(([to, froms]) => (Array.isArray(froms) ? froms : []).map((from) => ({ from, to })))
      crossStory.rejected = Number(plan.rejected) || 0
      crossStory.written = { added: Number(plan.added) || 0, removed: Number(plan.removed) || 0, standing: Number(plan.standing) || 0 }
      const byKey = new Map(tasks.map((t) => [t.key, t]))
      for (const e of crossStory.edges) {
        const to = byKey.get(e.to)
        if (to) to.dependsOn = [...to.dependsOn, e.from]
      }
    } else {
      log('Cross-Story Task dependencies: the write-all-task-edges summary was not relayed; beads is read at finish')
    }
  }
  if (crossStory.reason) log(`Cross-Story Task dependencies: ${crossStory.reason}`)
}
produced.crossStoryDependencies = crossStory
recRuled(`${tasks.length} Task(s) across ${decompositions.length} Story/Stories; ${crossStory.edges.length} edge(s) across Stories.`, { status: 'done' })

enterPhase('Finish')
const done = !specFailures.length && !decompositionFailures.length && !crossStory.reason
const finishArgs = [
  `elaboration-finish --epic ${shellq(epicBeadId)}`,
  lifecycle.owner ? `--owner ${shellq(lifecycle.owner)}` : '',
  done ? '--done' : '',
  ART_ON ? `--dir ${shellq(ART_DIR)} --repos ${shellq(repos.join(','))}` : '',
].filter(Boolean).join(' ')
const finishOut = await runScript('epic:finish', 'Finish', finishArgs)
lifecycle.finish = finishOut
const finishOk = !!(finishOut && !finishOut.error && finishOut.ok === true)
const epicMarkedDone = finishOk && !!finishOut.lifecycle
const unheld = finishOk && Array.isArray(finishOut.missing) ? finishOut.missing.filter(hasText) : []
const scoringLine = finishOk
  ? `Epic ${epicBeadId} and ${(finishOut.summary && finishOut.summary.tasksScored) || 0} Task(s) scored; Epic ${epicMarkedDone ? 'is elaboration_state=done' : 'stays in_progress'}. `
  : `Scoring did not run for Epic ${epicBeadId}: ${(finishOut && finishOut.error) || 'no result'}. `
log(scoringLine)
const storyEdges = (finishOut && finishOut.storyEdges) || null
const named = (list) => (Array.isArray(list) ? list : []).map((x) => `${(x.stories || []).join(' / ')}${(x.tasks || []).length ? ` (Tasks ${x.tasks.join(', ')})` : ''}`).join('; ')
const storyEdgeLine = !storyEdges
  ? ''
  : storyEdges.error
    ? `Story edges NOT written — ${storyEdges.error}. `
    : `Story edges: ${(storyEdges.added || []).length} added, ${(storyEdges.removed || []).length} removed, ${storyEdges.unchanged || 0} unchanged. ` +
      (storyEdges.ok ? '' : `Not written for ${(storyEdges.refusedStories || []).join(', ')} — ${storyEdges.reason}${named(storyEdges.conflicts) ? `; the sources disagree on ${named(storyEdges.conflicts)}` : ''}${named(storyEdges.cycles) ? `; a cycle runs through ${named(storyEdges.cycles)}` : ''}. `)
if (storyEdgeLine) log(storyEdgeLine)
const targetRemoval = { removed: false, commit: null, reason: null }
if (epicMarkedDone && !unheld.length) {
  if (!hasText(a.archPath)) {
    targetRemoval.reason = 'no archPath was passed, so the target folder was not removed'
  } else {
    const message = `docs(architecture): remove the ${delta.subject || 'approved'} target once the Specs and Tasks made from its delta are written`
    const removed = await runScript('arch:target-remove', 'Finish', `arch-target-remove --arch-root ${shellq(a.archPath)} --target-dir ${shellq(delta.targetDir)} --message ${shellq(message)}`)
    if (removed && !removed.error && removed.ok === true) {
      targetRemoval.removed = removed.removed === true
      targetRemoval.commit = removed.commit || null
    } else {
      targetRemoval.reason = removed && !removed.error ? (removed.refusals || []).join('; ') || 'refused' : (removed && removed.error) || 'no result'
    }
  }
} else {
  targetRemoval.reason = 'the Epic is not done, so its Specs and Tasks are not all written'
}
const targetLine = targetRemoval.removed
  ? `Target ${delta.targetDir} removed${targetRemoval.commit ? ` (commit ${targetRemoval.commit})` : ''}. `
  : `Target ${delta.targetDir} kept: ${targetRemoval.reason || 'it was already gone'}. `
log(targetLine)
const counted = (x) => (x && typeof x === 'object' ? (Number(x.created) || 0) + (Number(x.updated) || 0) : 0)
const beadsEmitted =
  specPairs.reduce((n, p) => n + counted(p.spec && p.spec.summary), 0) +
  decompositions.reduce((n, d) => n + counted(d.artifact && d.artifact.summary), 0)
const writeLine = `Written to beads: ${specPairs.length} Story/Stories and ${tasks.length} Task(s); ${beadsEmitted} bead(s) created or updated. `
log(writeLine)
const degraded = !finishOk || !done
const hierarchy = {
  epic,
  stories: specPairs.map((p) => ({ key: p.story.key, id: p.story.id, elabKey: p.story.elabKey, repoPath: p.repoPath, title: p.story.title })),
  tasks: tasks.map((t) => ({ key: t.key, id: t.id, elabKey: t.elabKey, parentStoryId: t.parentStoryId, title: t.title, dependsOn: t.dependsOn })),
}
const runJournal = {
  prd,
  specFailures,
  decompositionFailures,
  delta,
  results: {
    reconciliationByRepo: produced.reconciliationByRepo,
    architecture: (architecture.artifact || null),
    repoScoping: scoping,
    trdAuthoring: (trdAuthoring.artifact || null),
    specAuthoring: specPairs.map((p) => ({ repoPath: p.repoPath, artifact: p.spec })),
    decomposition: decompositions,
  },
}
recRuled(writeLine + scoringLine, { status: unheld.length ? 'failed' : 'done' })
const common = {
  degraded,
  beadsEmitted,
  lifecycle: { owner: lifecycle.owner, start: lifecycle.start, finish: lifecycle.finish, done: epicMarkedDone },
  ...(storyEdges ? { storyEdges } : {}),
  crossStoryDependencies: crossStory,
  hierarchy,
  repoSpan: repos,
  targetRemoval,
  ...(createdRepos.length ? { createdRepos } : {}),
}
if (unheld.length) {
  return {
    ...handback(false, UNPERSISTED_STAGE, `decomposed but beads does not hold all of it — ${unheld.slice(0, 20).join('; ')}${unheld.length > 20 ? `; and ${unheld.length - 20} more` : ''}. Re-dispatch the Epic: every write is keyed by elab_key, so the rerun updates what landed.`, runJournal),
    ...common,
  }
}
return {
  ...handback(
    true,
    'finish',
    `1 epic, ${specPairs.length} story/stories, ${tasks.length} task(s) for the PRD at ${prd.path || prd.id || prd.title || '(unpathed)'}. ` +
      `Span: ${repos.join(', ')}. ` +
      `Architecture approved for ${(architecture.artifact && architecture.artifact.subject) || 'the Epic'}; its target is integrated into the effective version. ` +
      writeLine +
      scoringLine +
      storyEdgeLine +
      targetLine +
      (specFailures.length || decompositionFailures.length || crossStory.reason
        ? `DEGRADED: ${specFailures.length} repo(s) produced no spec, ${decompositionFailures.length} Story/Stories produced no tasks${crossStory.reason ? `, ${crossStory.reason}` : ''}.` +
          (specFailures.length ? ` No spec: ${specFailures.map((x) => `${x.repoPath} at ${x.stage || 'spec-authoring'}: ${x.reason}`).join('; ')}`.slice(0, 1500) : '')
        : ''),
    runJournal
  ),
  ...common,
}
  })()
} catch (err) {
  const message = String((err && err.message) || err)
  const deaths = dispatchDeaths()
  const where = currentPhase || 'unknown'
  const stage = String(where).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown'
  log(`RUN ABORTED in ${where}: ${message.slice(0, 300)}`)
  result = partial(stage, { reason: `the run threw in ${where}: ${message.slice(0, 300)}`, dispatchFailed: deaths.length > 0, dispatchFailures: deaths })
} finally {
  const finishedDone = !!(lifecycle.finish && !lifecycle.finish.error && lifecycle.finish.lifecycle)
  if (lifecycle.started && !finishedDone && !lifecycle.held) {
    lifecycle.release = await runScript(
      'epic:release',
      currentPhase || 'Epic Lifecycle',
      `elaboration-release --epic ${shellq(epicBeadId)} --owner ${shellq(lifecycle.owner)}`
    )
    if (result) result.lifecycle = { ...(result.lifecycle || {}), owner: lifecycle.owner, start: lifecycle.start, finish: lifecycle.finish, release: lifecycle.release, done: false }
  }
  if (result && lifecycle.held) result.lifecycle = { ...(result.lifecycle || {}), owner: lifecycle.owner, start: lifecycle.start, finish: lifecycle.finish, held: true, heldCause: HOLD_CAUSE, done: false }
  enterPhase('Run Ledger')
  const detailPath = persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
  if (result) result.artifacts = { dir: artReport.dir, epicId: artReport.epicId, phases: { ...artPhases }, filing: { ...artReport.filing } }
  if (result) result.detailPath = detailPath || null
}
return dispatchOutcome(result)
