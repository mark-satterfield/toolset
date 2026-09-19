export const meta = {
  name: 'seed-portfolio',
  description:
    "Seeds the Epic portfolio's architecture dependencies, one batch per run: the per-Epic dependency assessment for at most `batch` open Epics (default 40), one Epic after another in id order, each dispatched by name with `score: false`. It is the same assessment normal operation runs for a new or changed Epic: each one reads its Epic's full PRD, searches the other PRDs, and sets or withdraws that Epic's architecture dependencies with a reason, seeing every edge the earlier assessments set. It returns the open Epics still to assess in `remaining` and never scores. /seed-portfolio runs it again with the same `since` until `remaining` is empty, then dispatches wsjf-scoring with `all` and `rejudge` as a workflow of its own, so every batch and the scoring have their own agent budget. An Epic whose edge proposal did not validate after three assessments stops the seeding at that Epic, naming each finding, as any other failure does; a person settles it and the seeding resumes with the same `since`. With `apply: false` every assessment proposes only and nothing is written.",
  whenToUse: 'The Epic portfolio is seeded once: every open Epic gets its architecture dependencies assessed, one batch per run, before every Epic and Task is scored by wsjf-scoring.',
  phases: [
    { title: 'Plan', detail: 'the open Epics not assessed since the seeding began, in id order; this run takes the first `batch`' },
    { title: 'Assess', detail: 'dependency-assessment for each Epic of the batch, one after another, with score: false' },
    { title: 'Remaining', detail: 'the open Epics still not assessed since the seeding began' },
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

// ── Deterministic steps ──────────────────────────────────────────────────────────
//
// Every tracker read and write is a `depscore.py` command. A workflow has no shell, so a
// runner session executes exactly one command and hands back what it printed; the command
// writes its full result to a file in the run directory and prints only its counts, so no
// data a later step depends on passes through a model.
const RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'output'],
  properties: {
    exitCode: { type: 'integer' },
    output: { type: 'object' },
  },
}
const failures = []
let currentPhase = null
async function runStep(label, command) {
  const out = await settleAgent(
    `Run exactly this one shell command, once, from any directory, and change nothing else:

${command}

It prints one JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not run any other command.`,
    { label, phase: currentPhase, effort: 'low', schema: RUN_SCHEMA }
  )
  if (!out) {
    failures.push({ step: label, reason: 'the runner returned no result' })
    return null
  }
  if (out.exitCode !== 0 || (out.output && out.output.error)) {
    failures.push({ step: label, reason: (out.output && out.output.error) || `exit ${out.exitCode}` })
    return null
  }
  return out.output || {}
}
function enter(title) {
  currentPhase = title
  phase(title)
}

// args: {
//   repoPath:     string,    // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,    // absolute path of this plugin's root
//   workDir:      string,    // absolute path of a directory for this run's files; one per run
//   since:        string,    // ISO 8601: the instant the seeding began. An open Epic not assessed
//                            // since then is assessed; a resumed seeding passes the same value.
//   sadPath?:     string,    // the arc42 SAD (ATW_SAD_PATH), passed to every assessment
//   projectRoot?: string,    // the project root (ATW_PROJECT_ROOT), passed the same way
//   epics?:       string[],  // assess only these open Epics (a rehearsal); the rest are left alone
//   batch?:       integer,   // the most Epics this run assesses, 1 to SEED_BATCH_MAX. Default SEED_BATCH.
//   apply?:       boolean,   // false: every assessment proposes only; nothing is written.
//                            // Default true.
// }
//
// Returns: { ok, since, apply, batch, assessed, stoppedAt, remaining,
//            failures, dispatchFailed, dispatchFailures }
//   ok:         true when nothing stopped and `failures` is empty
//   assessed:   [{ id, added, converted, removed, unchanged, withdrawn, edgesFile, reasoning, resultFile }]
//               — counts, the withdrawals with their reasons, and the files holding every edge
//               with its reason and the full applied or proposed diff
//   stoppedAt:  null, or { id, error, findings, attempts, edgesFile, validationFile, failures,
//               dispatchFailures } for the assessment that stopped it; the four from the
//               assessment's `stop` are null when it has none
//   remaining:  the open Epics still not assessed since `since` (restricted to `epics` when
//               given); the caller runs the seeding again with the same `since` until it is
//               empty. With `apply: false` it is the queue past this batch, because a
//               proposal stamps nothing.
//
// ── The agent budget ─────────────────────────────────────────────────────────────
//
// The runtime caps one workflow, nested workflows included, at 1000 agent sessions. One
// assessment uses at most 9: `assess-plan`, `assess-context`, up to ASSESS_ATTEMPTS = 3
// sequencer sessions and 3 validations, and `apply-edges`. A batch adds its own two plan
// steps. So a batch of 100 uses at most 902, and the default of 40 at most 362.
const SEED_BATCH = 40
const SEED_BATCH_MAX = 100
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const ID = /^[A-Za-z0-9._-]+$/
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$/
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
if (!(typeof a.since === 'string' && ISO.test(a.since))) {
  return { ok: false, error: '`since`, the ISO 8601 instant the seeding began, is required' }
}
if (a.epics !== undefined && !(Array.isArray(a.epics) && a.epics.length && a.epics.every((e) => typeof e === 'string' && ID.test(e)))) {
  return { ok: false, error: '`epics`, when given, is a non-empty list of Epic ids' }
}
if (a.batch !== undefined && !(Number.isInteger(a.batch) && a.batch >= 1 && a.batch <= SEED_BATCH_MAX)) {
  return { ok: false, error: `\`batch\`, when given, is an integer from 1 to ${SEED_BATCH_MAX}` }
}
const batch = a.batch === undefined ? SEED_BATCH : a.batch
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const applies = a.apply !== false
const project = { repoPath: repo, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }
const count = (v) => (Array.isArray(v) ? v.length : typeof v === 'number' ? v : 0)
const assessed = []
let stoppedAt = null
let remaining = []
const result = (ok, extra) => ({
  ok,
  since: a.since,
  apply: applies,
  batch,
  assessed,
  stoppedAt,
  remaining,
  ...(extra || {}),
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
})

// ── Plan ─────────────────────────────────────────────────────────────────────────
//
// `assess-plan --since` lists every open Epic whose content changed since it was last
// assessed, or that has not been assessed since the seeding began, sorted by id.
enter('Plan')
const planned = await runStep('assess-plan', cmd('assess-plan', `--since ${shq(a.since)} --out ${shq(file('seed-plan.json'))}`))
if (!planned) return result(false, { error: 'the seeding plan could not be computed; nothing was assessed' })
const unassessedIds = (planned.summary && planned.summary.unassessedIds) || []
const chosen = a.epics ? new Set(a.epics) : null
const queue = chosen ? unassessedIds.filter((id) => chosen.has(id)) : unassessedIds.slice()
if (chosen) {
  const skipped = a.epics.filter((id) => !unassessedIds.includes(id))
  if (skipped.length) log(`Not assessed — assessed since ${a.since}, or not an open Epic: ${skipped.join(', ')}`)
}
const slice = queue.slice(0, batch)
log(`${queue.length} Epic(s) to assess since ${a.since}: this run assesses ${slice.length}, ${queue.length - slice.length} left for later runs`)

// ── Assess ───────────────────────────────────────────────────────────────────────
//
// One Epic after another, never concurrently: each assessment sees every edge the earlier
// ones set, with its reason, and the cycle check runs against the live graph while the
// session can still revise its proposal. `score: false` because one scoring run follows
// the last batch.
enter('Assess')
for (let i = 0; i < slice.length; i++) {
  const id = slice[i]
  let r = null
  let thrown = null
  try {
    r = await workflow('agent-teams-workforce:dependency-assessment', {
      ...project,
      workDir: file(`assess/${id}`),
      epic: id,
      score: false,
      apply: applies,
    })
  } catch (err) {
    thrown = String((err && err.message) || err).slice(0, 500)
  }
  const edges = (r && r.edges) || {}
  if (r && r.ok === true) {
    assessed.push({
      id,
      added: count(edges.added),
      converted: count(edges.converted),
      removed: count(edges.removed),
      unchanged: edges.unchanged ?? null,
      withdrawn: edges.withdrawn || [],
      edgesFile: edges.edgesFile || null,
      reasoning: edges.reasoning || null,
      resultFile: edges.resultFile || edges.diffFile || null,
    })
    log(`${id}: ${count(edges.added)} added, ${count(edges.converted)} converted, ${count(edges.removed)} withdrawn${applies ? '' : ' (proposed)'}`)
    continue
  }
  const stop = (r && r.stop) || null
  stoppedAt = {
    id,
    error: thrown || (r && (r.error || edges.reason)) || 'the dependency assessment returned no result',
    findings: stop ? stop.findings || null : null,
    attempts: stop ? stop.attempts ?? r.attempts ?? null : null,
    edgesFile: stop ? stop.edgesFile || null : null,
    validationFile: stop ? stop.validationFile || null : null,
    failures: (r && r.failures) || [],
    dispatchFailures: (r && r.dispatchFailures) || [],
  }
  remaining = queue.slice(i)
  log(`Seeding stopped at ${id}: ${stoppedAt.error}`)
  break
}
if (stoppedAt) {
  const error = stoppedAt.findings
    ? `the seeding stopped at ${stoppedAt.id}: its edge proposal did not validate after ${stoppedAt.attempts} assessments; settle the findings in stoppedAt, then resume with the same since, ${a.since}`
    : `the seeding stopped at ${stoppedAt.id}; resume with the same since, ${a.since}`
  return result(false, { error })
}

// ── Remaining ────────────────────────────────────────────────────────────────────
//
// The Epics a later run assesses. Applied, they are read back from the tracker, so an Epic
// that changed while this batch ran is assessed again. Proposed only, nothing was stamped,
// so they are the queue past this batch. Scoring is never run here: /seed-portfolio runs
// wsjf-scoring as its own workflow once `remaining` is empty.
enter('Remaining')
if (!applies) {
  remaining = queue.slice(batch)
  return result(failures.length === 0)
}
const after = await runStep('assess-plan (after)', cmd('assess-plan', `--since ${shq(a.since)} --out ${shq(file('seed-plan-after.json'))}`))
if (!after) {
  return result(false, {
    error: `the assessment plan could not be recomputed after this batch; run the seeding again with the same since, ${a.since}`,
  })
}
const stillUnassessed = (after.summary && after.summary.unassessedIds) || []
remaining = chosen ? stillUnassessed.filter((id) => chosen.has(id)) : stillUnassessed.slice()
log(`${remaining.length} Epic(s) remain to assess since ${a.since}`)
return result(failures.length === 0)
