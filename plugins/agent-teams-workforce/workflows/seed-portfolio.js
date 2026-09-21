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
  let out = null
  try {
    out = await agent(prompt, call)
  } catch (err) {
    const message = String((err && err.message) || err)
    dispatchFailures.push({
      ...who,
      outcome: 'threw',
      message: message.slice(0, 300),
      transcript: settleTranscript(err, name),
      note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''}: ${message.slice(0, 160)}`,
    })
    log(`${name}: session ended without a structured result — ${message.slice(0, 160)}`)
    // A caller that owns its own failure reporting asks for the throw back, so the real
    // reason reaches its catch instead of being flattened to "returned no result".
    if (o.rethrow) throw err
    return null
  }
  if (out) return out
  dispatchFailures.push({
    ...who,
    outcome: 'skipped',
    message: null,
    transcript: settleTranscript(null, name),
    note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
  })
  log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
  return null
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
  return { ok: false, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
if (!(typeof a.since === 'string' && ISO.test(a.since))) {
  return { ok: false, error: '`since`, the ISO 8601 instant the seeding began, is required' }
}
if (!(Array.isArray(a.epics) && a.epics.every((e) => typeof e === 'string' && ID.test(e)))) {
  return { ok: false, error: '`epics`, the list of Epic ids to assess, is required' }
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
const result = (ok, extra) => ({
  ok,
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
