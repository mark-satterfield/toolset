export const meta = {
  name: 'seed-portfolio',
  description:
    "Seeds the Epic portfolio: runs dependency-assessment (with `score: false`) for every Epic in `epics`, one after another in the order given, then runs wsjf-scoring once. An Epic whose assessment fails is reported in `stoppedAt` and `remaining` and the seeding continues. With `apply: false` every assessment proposes only and nothing is scored.",
  whenToUse: 'The Epic portfolio is seeded once: every open Epic gets its architecture dependencies assessed before every Epic and Task is scored by wsjf-scoring.',
  phases: [
    { title: 'Assess', detail: 'dependency-assessment for each Epic, one after another, with score: false' },
    { title: 'Score', detail: 'wsjf-scoring once, over the edge set' },
  ],
}
const dispatchFailures = []
// Returns the recorded dispatch failures of the named phases, or all of them when none is named.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
// Returns 'transient' for an API overload, rate limit or network error, otherwise 'deterministic'.
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  return TRANSIENT_ERROR_TEXT.test(text) ? 'transient' : 'deterministic'
}
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
const settleSleep = (ms) => (SETTLE_CAN_WAIT ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve())
// Returns the wait before retry `attempt`: 5s tripled per attempt, capped at 300s, scaled into [50%, 100%) by a hash of the dispatch.
function transientWaitMs(name, attempt) {
  const key = `${name}#${attempt}`
  let h = 2166136261
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  const scheduled = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
  return Math.round(scheduled * (0.5 + 0.5 * ((h >>> 0) / 4294967296)))
}
// Calls agent() and returns its result. A transient failure is retried with backoff until it clears
// (three attempts when no timer exists); any other failure returns null and is recorded in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    let out = null
    try {
      out = await agent(prompt, o)
    } catch (err) {
      const message = String((err && err.message) || err)
      const cause = failureCause(err)
      const entry = {
        ...who,
        outcome: 'threw',
        cause,
        attempt,
        message: message.slice(0, 300),
        note: `${name} ended without a structured result (${cause}): ${message.slice(0, 160)}`,
      }
      dispatchFailures.push(entry)
      mine.push(entry)
      log(entry.note)
      if (cause !== 'transient' || (!SETTLE_CAN_WAIT && attempt >= 3)) return null
      const wait = transientWaitMs(name, attempt)
      waitedMs += wait
      log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s (${Math.round(waitedMs / 1000)}s waited)`)
      await settleSleep(wait)
      continue
    }
    if (out) {
      for (const entry of mine) {
        const at = dispatchFailures.indexOf(entry)
        if (at >= 0) dispatchFailures.splice(at, 1)
      }
      return out
    }
    dispatchFailures.push({ ...who, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: `${name} returned nothing` })
    log(`${name} returned nothing`)
    return null
  }
}

// args: {
//   repoPath:     string,    // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,    // absolute path of this plugin's root
//   workDir:      string,    // absolute path of a directory for this run's files
//   since:        string,    // ISO 8601 instant the seeding began, reported back
//   epics:        string[],  // the open Epics to assess, in order
//   sadPath?:     string,
//   projectRoot?: string,
//   apply?:       boolean,   // false: every assessment proposes only; nothing is written. Default true.
// }
// Returns: { ok, stage, headline, since, apply, assessed, stoppedAt, remaining, failed, scoring,
//            dispatchFailed, dispatchFailures }
//   assessed:   [{ id, added, converted, removed, unchanged, withdrawn, edgesFile, reasoning, resultFile }]
//   failed:     [{ id, error, findings, edgesFile, validationFile, dispatchFailures }], one per failed Epic
//   stoppedAt:  the first entry of `failed`, or null
//   remaining:  the ids of the failed Epics
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const work = String(a.workDir || '').replace(/\/+$/, '')
const file = (name) => `${work}/${name}`
const contextDir = file('context')
const applies = a.apply !== false
const project = { repoPath: a.repoPath, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }
const count = (v) => (Array.isArray(v) ? v.length : typeof v === 'number' ? v : 0)
const queue = Array.isArray(a.epics) ? a.epics.filter((e) => typeof e === 'string' && e) : []
const assessed = []
const failed = []
let scoring = null
let nestedDeaths = []
log(`${queue.length} Epic(s) to assess since ${a.since}`)

phase('Assess')
let corpusReady = false
for (const id of queue) {
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
  const entry = {
    id,
    error: thrown || (r && r.error) || 'the dependency assessment returned no result',
    findings: stop ? stop.findings || null : null,
    edgesFile: stop ? stop.edgesFile || null : edges.edgesFile || null,
    validationFile: stop ? stop.validationFile || null : null,
    dispatchFailures: (r && r.dispatchFailures) || [],
  }
  failed.push(entry)
  if (r && r.stage === 'agent-dispatch-failed') nestedDeaths.push(...entry.dispatchFailures)
  log(`${id}: assessment failed — ${entry.error}`)
}

let scoringError = null
if (applies) {
  phase('Score')
  try {
    scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
  } catch (err) {
    scoringError = String((err && err.message) || err).slice(0, 500)
  }
  if (!(scoring && scoring.ok === true)) {
    if (scoring && scoring.stage === 'agent-dispatch-failed') nestedDeaths.push(...(scoring.dispatchFailures || []))
    scoringError = scoringError || (scoring && scoring.error) || 'wsjf-scoring returned no result'
    log(`Scoring failed: ${scoringError}`)
  }
}

const errors = [
  failed.length ? `${failed.length} Epic(s) failed assessment: ${failed.map((f) => f.id).join(', ')}; resume with the same since, ${a.since}` : '',
  scoringError ? `scoring failed: ${scoringError}` : '',
].filter(Boolean)
const ok = errors.length === 0
return {
  ok,
  stage: ok ? 'done' : nestedDeaths.length ? 'agent-dispatch-failed' : failed.length ? 'Assess' : 'Score',
  headline: ok ? `${assessed.length} Epic(s) assessed${applies ? ' and the portfolio rescored' : ' (proposed only)'}` : errors.join('; '),
  since: a.since,
  apply: applies,
  assessed,
  stoppedAt: failed[0] || null,
  remaining: failed.map((f) => f.id),
  failed,
  scoring,
  ...(ok ? {} : { error: errors.join('; ') }),
  dispatchFailed: dispatchDeaths().length + nestedDeaths.length > 0,
  dispatchFailures: [...dispatchDeaths(), ...nestedDeaths],
}
