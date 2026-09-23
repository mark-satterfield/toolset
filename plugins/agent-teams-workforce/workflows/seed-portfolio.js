export const meta = {
  name: 'seed-portfolio',
  description:
    "Seeds the Epic portfolio: it assesses the architecture dependencies of every Epic in `epics`, then scores every open Epic and Task with WSJF. The assessment is the per-Epic dependency assessment, one Epic after another in the order given, each dispatched by name with `score: false`: the same assessment normal operation runs for a new or changed Epic, in which one session per Epic reads its full PRD, searches the other PRDs, and sets or withdraws that Epic's architecture dependencies with a reason, seeing every edge the earlier assessments set. The PRD corpus is written once, by the first assessment, and read by the rest. When every Epic is assessed and applied, the seeding dispatches wsjf-scoring once, without `all` or `rejudge`: it judges the items whose source content changed or whose value is missing, then runs the arithmetic, RR-OE from the new edges included, over every open item and writes the values that changed. /seed-portfolio computes `epics` with `assess-plan --since` before dispatching it and checks what is left with the same command afterwards. An Epic whose edge proposal did not validate, or that failed any other way, stops the seeding at that Epic, naming each finding, and nothing is scored, because the edge set is incomplete; a person settles it and the seeding resumes with the same `since`, which finishes the edges and then scores. With `apply: false` every assessment proposes only, nothing is written and nothing is scored.",
  whenToUse: 'The Epic portfolio is seeded once: every open Epic gets its architecture dependencies assessed before every Epic and Task is scored by wsjf-scoring.',
  phases: [
    { title: 'Assess', detail: 'dependency-assessment for each Epic, one after another, with score: false' },
    { title: 'Score', detail: 'wsjf-scoring once, over the completed edge set' },
  ],
}
// ── EVERY DISPATCH IS SETTLED ────────────────────────────────────────────────────
//
// `agent()` fails in two different ways and the scripts used to conflate them. It
// RETURNS NULL when a subagent is skipped or dies on a terminal API error after the
// runtime's own retries. It THROWS when a subagent finishes without calling
// StructuredOutput — and an uncaught throw leaves this script, leaves whatever
// composite called it, and kills the run: two recorded crashes cost 1.13M and 1.88M
// tokens and discarded every artifact the run had already paid for.
//
// So every dispatch in this file goes through settleAgent(). A throw never escapes it,
// and it records what the engine's error text loses — that text reads
// `agent({schema}): subagent completed without calling StructuredOutput`, which names
// neither the agent, nor the phase, nor the schema, and points at no transcript. The
// caller receives null, which every call site already handles, and `dispatchFailures`
// carries the identity of what died, for the `dispatchFailed` report this script owes
// its caller: a phase whose producing agents died is NOT adjudicated.
//
// Each `dispatchFailures` entry ALSO carries the CAUSE — see failureCause below — because
// a caller that can only see THAT a dispatch produced nothing cannot tell the one failure
// worth sending again from the many that are not. `failureCauseFor(label)` is how a call
// site reads it back, and a TRANSIENT cause is waited out inside settleAgent itself, so
// every dispatch in every script survives an API overload rather than only some of them.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
// ── WHY A DISPATCH FAILED DECIDES WHETHER ANYTHING MAY BE SENT AGAIN ─────────────
//
// settleAgent used to collapse every failure into a single null, and that conflation is
// the same defect that let a destroyed answer look like a dead agent: a call site could
// see THAT a dispatch produced nothing and never WHY. Two causes need opposite answers,
// and getting them the same way round is what makes this a classification and not a
// retry loop wearing a hat.
//
// TRANSIENT — an Anthropic API overload (529), a rate limit (429), a quota or token
// limit, a network timeout. The cause is EXTERNAL and TIME-VARYING, the input was never
// the problem, and the call that failed produced nothing to pay for. Waiting and sending
// the same dispatch again therefore has a real reason to come out differently, which is
// the only thing that ever justifies a second attempt. This is the one case retried here,
// and it is retried until it clears — see the backoff below. It is never answered by
// splitting the input: the input was fine, and splitting multiplies calls against an
// endpoint that is already failing to serve the first one.
//
// DETERMINISTIC — a schema rejection, an agent that finished without producing output,
// anything settled by arithmetic. Re-issuing the identical dispatch against the identical
// input has NO reason to produce a different result; it is a hope with a token cost, and
// this project removed exactly those blind retries after they burned tokens to exhaustion
// on attempts that could not succeed. The only sanctioned re-dispatch is one with
// materially CHANGED input — for the SAD batches, the split.
//
// ANYTHING UNRECOGNISED IS DETERMINISTIC, and that direction is deliberate rather than
// defensive. Guessing "transient" on an unknown error invents a retry that is forbidden
// and pays for it on every unfamiliar failure; guessing "deterministic" at worst declines
// a retry that might have worked, and the caller still has its split and its report. The
// cheap mistake is the one to take.
//
// This block is identical in every workflow script, on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text.
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  // Deterministic markers are matched FIRST, on purpose: a schema rejection whose text
  // happens to quote a number that also reads as a status code is a schema rejection, and
  // reading it as an overload would hand it the one retry it must never get.
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  if (TRANSIENT_ERROR_TEXT.test(text)) return 'transient'
  return 'deterministic'
}
// The cause recorded for the most recent failure of THIS dispatch. Labels are unique per
// dispatch — retireFailures already depends on that — so a lane can never read another
// lane's cause. Null means this label has no recorded failure at all.
function failureCauseFor(label) {
  for (let i = dispatchFailures.length - 1; i >= 0; i--) {
    if (dispatchFailures[i].label === label) return dispatchFailures[i].cause || 'deterministic'
  }
  return null
}
// ── A TRANSIENT FAILURE IS WAITED OUT, NOT COUNTED DOWN ─────────────────────────
//
// An API overload is a server-side condition with its own clock. It clears in thirty
// seconds, or five minutes, or fifteen; nothing this script does shortens it, and a failed
// call costs nothing, so there is nothing here to conserve by giving up. A run started in
// the evening must still be running in the morning, having sat out whatever happened at
// 3am and carried on by itself. So there is NO attempt ceiling and no elapsed-time budget:
// the wait grows, flattens at five minutes, and repeats at five minutes for as long as the
// endpoint keeps failing. If you are about to add a maximum, you are re-introducing the
// defect this replaced — a two-attempt budget that guaranteed a back-to-back second
// failure and then quit.
//
// The schedule: 5s, then triple each time, capped at 300s — 5, 15, 45, 135, 300, 300, …
// Five seconds is short enough that a brief blip costs seconds rather than minutes; a
// factor of three reaches the cap on the fifth wait, about eight minutes in, so a genuine
// outage is at the polite five-minute cadence quickly instead of hammering the endpoint
// for an hour of doublings.
//
// JITTER exists because these lanes run concurrently. Identical waits make every lane that
// failed together return together, which is the thundering herd arriving at an endpoint
// that is already struggling. Each wait is therefore 50–100% of the scheduled interval:
// the growth shape survives, and the lanes spread out.
//
// The offset is DERIVED, never drawn. A workflow script cannot draw a random number — a
// resumed run would draw a different one — and it does not need to: what jitter has to
// vary across is LANES, not runs. Hashing the dispatch's own identity together with the
// attempt number gives concurrent lanes different offsets, which is the whole requirement,
// and gives a resumed run the same one, which is the house rule.
//
// THE WAIT IS LOGGED, and that is the point of it being allowed to be this long. Every
// retry prints the attempt number, the wait about to be taken and the TOTAL time spent
// waiting so far, so someone reading a log at 3am can tell a run patiently sitting out an
// outage from a run that is hung.
const TRANSIENT_BACKOFF_BASE_MS = 5000
const TRANSIENT_BACKOFF_FACTOR = 3
const TRANSIENT_BACKOFF_CAP_MS = 300000
const TRANSIENT_BACKOFF_JITTER = 0.5
// FNV-1a over the dispatch identity, normalised to [0, 1). Any stable spread would do; this
// one is four lines and needs nothing the sandbox withholds.
function settleSpread(text) {
  let h = 2166136261
  for (let i = 0; i < text.length; i++) {
    h = Math.imul(h ^ text.charCodeAt(i), 16777619)
  }
  return (h >>> 0) / 4294967296
}
function transientWaitMs(name, attempt) {
  const scheduled = Math.min(
    TRANSIENT_BACKOFF_CAP_MS,
    TRANSIENT_BACKOFF_BASE_MS * Math.pow(TRANSIENT_BACKOFF_FACTOR, Math.max(0, attempt - 1))
  )
  const spread = settleSpread(`${name}#${attempt}`)
  return Math.round(scheduled * (1 - TRANSIENT_BACKOFF_JITTER + TRANSIENT_BACKOFF_JITTER * spread))
}
// Workflow scripts are a sandbox with no Node API, and the runner guarantees only its seven
// injected globals, so a timer is probed for rather than assumed.
//
// THE NO-CEILING RULE IS CONDITIONAL ON BEING ABLE TO WAIT. Without a timer there is no
// backoff at all, and an unbounded loop with no wait is not patience — it is a hot loop
// hammering an endpoint that is already failing, which is worse than stopping. So on a host
// with no timer the transient retry falls back to a few immediate attempts and then reports
// the failure, saying in the log exactly why it stopped. Every host this runs on today
// provides setTimeout; this branch exists so that if one ever does not, the failure mode is
// a reported stop rather than a spin.
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
const TRANSIENT_ATTEMPTS_WITHOUT_WAIT = 3
const settleSleep = (ms) =>
  SETTLE_CAN_WAIT ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve()
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.schemaName
  const who = {
    agentType: o.agentType || null,
    label: o.label || null,
    phase: o.phase || null,
    schema: settleSchemaName(o),
  }
  const name = who.label || who.agentType || 'agent'
  const whose = `${name}${who.agentType && who.agentType !== name ? ` (${who.agentType})` : ''}${who.phase ? ` in ${who.phase}` : ''}`
  // The failures THIS call recorded. A dispatch that finally returns after sitting out an
  // overload did not die, and leaving its transient entries in `dispatchFailures` would
  // tell the caller's gate that a phase which produced its artifact must not be
  // adjudicated. They are removed by identity, so a concurrent lane's entries are safe.
  const mine = []
  const fail = (entry) => {
    dispatchFailures.push(entry)
    mine.push(entry)
  }
  const retireMine = () => {
    for (const entry of mine) {
      const at = dispatchFailures.indexOf(entry)
      if (at >= 0) dispatchFailures.splice(at, 1)
    }
    mine.length = 0
  }
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    let out = null
    try {
      out = await agent(prompt, call)
    } catch (err) {
      const message = String((err && err.message) || err)
      const cause = failureCause(err)
      fail({
        ...who,
        outcome: 'threw',
        cause,
        attempt,
        message: message.slice(0, 300),
        transcript: settleTranscript(err, name),
        note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''} (${cause}): ${message.slice(0, 160)}`,
      })
      log(`${name}: session ended without a structured result (${cause}, attempt ${attempt}) — ${message.slice(0, 160)}`)
      if (cause === 'transient' && !SETTLE_CAN_WAIT && attempt >= TRANSIENT_ATTEMPTS_WITHOUT_WAIT) {
        log(
          `${name}: TRANSIENT infrastructure failure on attempt ${attempt}, and this host provides no timer, so the dispatch ` +
            `cannot be spaced out. Stopping rather than spinning against a failing endpoint — re-run once the API has recovered.`
        )
        if (o.rethrow) throw err
        return null
      }
      if (cause === 'transient') {
        const wait = transientWaitMs(name, attempt)
        waitedMs += wait
        log(
          `${name}: TRANSIENT infrastructure failure — attempt ${attempt} failed; waiting ${Math.round(wait / 1000)}s ` +
            `before sending the same dispatch again (${Math.round(waitedMs / 1000)}s spent waiting so far). ` +
            `This is a server-side condition with no attempt limit here: it keeps retrying, at five minutes apart once the backoff caps, until it clears.`
        )
        await settleSleep(wait)
        continue
      }
      // A caller that owns its own failure reporting asks for the throw back, so the real
      // reason reaches its catch instead of being flattened to "returned no result". Only
      // a DETERMINISTIC failure ever gets here — a transient one is still being waited out.
      if (o.rethrow) throw err
      return null
    }
    if (out) {
      if (waitedMs > 0) {
        log(`${name}: returned on attempt ${attempt} after ${Math.round(waitedMs / 1000)}s of waiting out a transient failure`)
      }
      retireMine()
      return out
    }
    fail({
      ...who,
      outcome: 'skipped',
      // A null with no error text carries no evidence of anything, and an unrecognised cause
      // is deterministic. It is also the right answer on the merits here: the runtime has
      // ALREADY exhausted its own retries before it hands back a null, so sending the same
      // dispatch again is the blind retry, not the recovery.
      cause: 'deterministic',
      attempt,
      message: null,
      transcript: settleTranscript(null, name),
      note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
    })
    log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
    return null
  }
}


// args: {
//   repoPath:     string,    // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,    // absolute path of this plugin's root
//   workDir:      string,    // absolute path of a directory for this run's files; one per run
//   since:        string,    // ISO 8601: the instant the seeding began, reported back for a resume
//   epics:        string[],  // the open Epics to assess, in order: `assess-plan --since` output
//   sadPath?:     string,    // the arc42 SAD (ATW_SAD_PATH), passed to every assessment
//   projectRoot?: string,    // the project root (ATW_PROJECT_ROOT), passed the same way
//   apply?:       boolean,   // false: every assessment proposes only; nothing is written.
//                            // Default true.
// }
//
// Returns: { ok, since, apply, assessed, stoppedAt, remaining, scoring, dispatchFailed,
//            dispatchFailures }
//   ok:         true when every Epic was assessed and, when it applies, scoring returned ok
//   assessed:   [{ id, added, converted, removed, unchanged, withdrawn, edgesFile, reasoning, resultFile }]
//   stoppedAt:  null, or { id, error, findings, edgesFile, validationFile, dispatchFailures } for
//               the assessment that stopped it
//   remaining:  the Epics of `epics` not assessed, the stopped one first
//   scoring:    the wsjf-scoring result, or null when the seeding stopped or proposed only
//
// ── The agent budget ─────────────────────────────────────────────────────────────
//
// The runtime caps one workflow, nested workflows included, at 1000 agent sessions. One
// assessment is one session, so a seeding of every open Epic fits in one run.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const ID = /^[A-Za-z0-9._-]+$/
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$/
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, stage: 'input', error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
if (!(typeof a.since === 'string' && ISO.test(a.since))) {
  return { ok: false, stage: 'input', error: '`since`, the ISO 8601 instant the seeding began, is required' }
}
if (!(Array.isArray(a.epics) && a.epics.every((e) => typeof e === 'string' && ID.test(e)))) {
  return { ok: false, stage: 'input', error: '`epics`, the list of Epic ids to assess, is required' }
}
const work = a.workDir.replace(/\/+$/, '')
const file = (name) => `${work}/${name}`
const contextDir = file('context')
const applies = a.apply !== false
const project = { repoPath: a.repoPath, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }
const count = (v) => (Array.isArray(v) ? v.length : typeof v === 'number' ? v : 0)
const queue = a.epics.slice()
const assessed = []
let stoppedAt = null
let remaining = []
let scoring = null
// `stage` and `headline` are what a dispatcher reads off any composite's return.
const result = (ok, extra) => ({
  ok,
  stage: stoppedAt ? 'Assess' : ok ? 'done' : 'Score',
  headline: (extra && extra.error) || `${assessed.length} Epic(s) assessed${applies ? ' and the portfolio rescored' : ' (proposed only)'}`,
  since: a.since,
  apply: applies,
  assessed,
  stoppedAt,
  remaining,
  scoring,
  ...(extra || {}),
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
})
log(`${queue.length} Epic(s) to assess since ${a.since}`)

// ── Assess ───────────────────────────────────────────────────────────────────────
//
// One Epic after another, never concurrently: each assessment sees every edge the earlier
// ones set, with its reason, and the cycle check runs against the live graph. The first
// assessment writes the PRD corpus into one directory for the whole seeding and the rest
// read it. `score: false` because one scoring run follows the whole seeding.
phase('Assess')
let corpusReady = false
for (let i = 0; i < queue.length; i++) {
  const id = queue[i]
  let r = null
  let thrown = null
  try {
    r = await workflow('agent-teams-workforce:dependency-assessment', {
      ...project,
      workDir: file(`assess/${id}`),
      contextDir,
      corpusReady,
      epic: id,
      score: false,
      apply: applies,
    })
  } catch (err) {
    thrown = String((err && err.message) || err).slice(0, 500)
  }
  const edges = (r && r.edges) || {}
  if (r && r.ok === true) {
    corpusReady = true
    assessed.push({
      id,
      added: count(edges.added),
      converted: count(edges.converted),
      removed: count(edges.removed),
      unchanged: edges.unchanged ?? null,
      withdrawn: edges.withdrawn ?? null,
      edgesFile: edges.edgesFile || null,
      reasoning: edges.reasoning || null,
      resultFile: edges.resultFile || null,
    })
    log(`${id}: ${count(edges.added)} added, ${count(edges.converted)} converted, ${count(edges.removed)} withdrawn${applies ? '' : ' (proposed)'}`)
    continue
  }
  const stop = (r && r.stop) || null
  stoppedAt = {
    id,
    error: thrown || (r && r.error) || 'the dependency assessment returned no result',
    findings: stop ? stop.findings || null : null,
    edgesFile: stop ? stop.edgesFile || null : edges.edgesFile || null,
    validationFile: stop ? stop.validationFile || null : null,
    dispatchFailures: (r && r.dispatchFailures) || [],
  }
  remaining = queue.slice(i)
  log(`Seeding stopped at ${id}: ${stoppedAt.error}`)
  return result(false, { error: `the seeding stopped at ${id}; settle it, then resume with the same since, ${a.since}` })
}

// ── Score ────────────────────────────────────────────────────────────────────────
//
// Reached only when every Epic in `epics` was assessed and applied: a stopped seeding
// returned above, so RR-OE is never computed from a half-assessed graph. Neither `all` nor
// `rejudge`: missing values are judged, unchanged ones are not judged again, and the
// arithmetic recomputes RR-OE from the new edges and rewrites every WSJF that changed.
// A resume with an empty `epics` comes straight here.
if (!applies) return result(true)
phase('Score')
let scoringThrown = null
try {
  scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
} catch (err) {
  scoringThrown = String((err && err.message) || err).slice(0, 500)
}
if (!(scoring && scoring.ok === true)) {
  const why = scoringThrown || (scoring && scoring.error) || 'wsjf-scoring returned no result'
  log(`Scoring failed: ${why}`)
  return result(false, { error: `every Epic was assessed, but scoring failed: ${why}; resume with the same since, ${a.since}, to score` })
}
return result(true)
