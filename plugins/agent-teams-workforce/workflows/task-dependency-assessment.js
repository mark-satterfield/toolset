export const meta = {
  name: 'task-dependency-assessment',
  description:
    "Assesses the build dependencies of ONE Task created outside elaboration (a Task with no `elab_key`), and writes edges and nothing else. A Task dependency is a build dependency: an edge from A to B says B cannot be built until A is built, because B consumes something A provides — an API, an event contract, a table, an IAM grant, a deployed resource. It is stored as a beads `blocks` edge between two Tasks; no end is a Story or an Epic. One task-dependency-mapper session reads the Task, names what it consumes and what it provides, searches the other open Tasks for the ones that provide what it consumes or consume what it provides, reads those in full, and applies the test in both directions. It proposes every edge to or from the Task with a reason, and keeps or withdraws, with a reason, every owned edge standing on it. Code refuses an edge that does not touch the Task, an edge that does not join two open Tasks, a Task written by elaboration, a cycle, an unaccounted standing edge and a missing reason, confines the write to that Task's edges, and never touches a hand-made edge. A proposal that does not validate is assessed again with the validator's findings, at most twice, and then the run stops, naming the Task and the findings and writing nothing. When the edges are applied it triggers wsjf-scoring, because edges decide Task RR-OE. With `apply: false` it proposes only: it computes the edge diff as a dry run, returns it, writes nothing to the tracker and triggers no scoring.",
  whenToUse: 'A Task was created or changed outside elaboration and needs its build dependencies assessed.',
  phases: [
    { title: 'Context', detail: "the Task's fingerprint, its standing edges, and the open Tasks with their index" },
    { title: 'Assess', detail: 'the task-dependency-mapper proposes every edge to or from the Task and accounts for every owned standing edge; code validates each attempt, up to three' },
    { title: 'Apply', detail: 'validate and apply the edge diff for the Task, or compute it as a dry run' },
    { title: 'Score', detail: 'wsjf-scoring over the new edges' },
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

// ── A LIMIT BELONGS WHERE THE DATA IS MADE, AND AN OVERAGE IS A FLAG ─────────────
//
// Two rules, and they are different rules.
//
// ONE: a limit is never a JSON-Schema maxItems/minItems/maxLength. A schema bound cannot
// trim an over-long answer — the runtime rejects the WHOLE result, the caller receives a
// bare null it cannot tell from a dead agent, and the run halts. One really did, on 61
// items against a bound of 60, claiming files were unread that had been read. So a limit
// is STATED in the prompt and COUNTED here, once the result is in hand.
//
// TWO, and it decides whether a limit may be stated at all: a limit belongs at the layer
// where the data is CREATED, not where it is read. A dispatch that AUTHORS its output —
// criteria, findings, a persona, a draft — chooses its own volume, so a ceiling stated to
// it is a real instruction it can honour. A dispatch that READS or EXTRACTS — an
// inventory of what exists, the evidence found in a repository, the ids it was handed,
// what git printed — has a volume that is a property of the source. Telling it "at most
// N" instructs it to truncate, which loses information, or to lie. Those dispatches get
// NO stated ceiling; bounding what they may DRAW ON (which repository, which files) is
// the guard that works, and it already lives in their prompts. Where a read's volume
// genuinely ought to be smaller, the fix belongs upstream, in whatever made the data.
//
// BOTH kinds are still counted here, because a wildly unexpected count is exactly the
// signal worth having, and nothing is ever truncated, dropped, reordered or summarised at
// any multiple. The count is a GRADUATED FLAG: modestly over the expected figure is
// ordinary variation and reads as an observation; at SCRUTINY_MULTIPLE times it or more,
// the shape is no longer variation — it is what padding, a misread assignment or
// duplicated entries look like — and it is logged prominently so a person looks. 2x is
// the threshold because a single band has to sit above the honest overshoots this
// pipeline actually produces (61 against 60 is 1.02x; the worst recorded lens overshoot
// is well under 1.5x) and below the runaway enumerations the limits exist to catch. It is
// a flag for a person, never a thing the code acts on: neither branch alters control flow.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const limitFindings = []
const SCRUTINY_MULTIPLE = 2
function checkLimit(where, what, value, expected, min) {
  const n = Array.isArray(value) ? value.length : typeof value === 'string' ? value.length : null
  if (n === null) return value
  if (typeof expected === 'number' && n > expected) {
    const ratio = expected > 0 ? n / expected : Infinity
    const scrutinise = ratio >= SCRUTINY_MULTIPLE
    limitFindings.push({ where, what, count: n, expected, ratio: Math.round(ratio * 100) / 100, severity: scrutinise ? 'scrutinise' : 'observation' })
    log(
      scrutinise
        ? `⚠ ${where}: ${what} returned ${n} where ${expected} was expected — ${Math.round(ratio * 10) / 10}x. Every item is kept and nothing downstream changes, but a count this far over is the shape of padding, a misread assignment or duplicated entries: worth a look.`
        : `${where}: ${what} returned ${n} where ${expected} was expected — over by ${n - expected}; every item is kept.`
    )
  }
  if (typeof min === 'number' && n < min) {
    limitFindings.push({ where, what, count: n, expected: min, severity: 'under' })
    log(`${where}: ${what} returned ${n}, under the ${min} this asked for — carried through as returned.`)
  }
  return value
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
//   repoPath:     string,   // absolute path of the repository whose `bd` tracker holds the Tasks
//   pluginRoot:   string,   // absolute path of this plugin's root
//   workDir:      string,   // absolute path of a directory for this run's files; one per run
//   task:         string,   // the one Task assessed: open, and created outside elaboration
//   projectRoot?: string,   // the project root (ATW_PROJECT_ROOT), passed to the scoring it triggers
//   sadPath?:     string,   // the arc42 SAD (ATW_SAD_PATH), passed to the scoring it triggers
//   score?:       boolean,  // false: do not trigger scoring when the edges are applied. Default true.
//   apply?:       boolean,  // false: propose only — no edge, reason or score is written; `edges`
//                           // carries the diff (added, converted, removed, withdrawn, unchanged,
//                           // planned) computed as a dry run. Default true.
// }
//
// Returns: { ok, apply, settled, attempts, workDir, task, plan, context, assessment, edges,
//            scoring, stop, error?, headline?, failures, dispatchFailed, dispatchFailures }
//   settled:    the validator passed an attempt's edge file; nothing is applied otherwise
//   attempts:   the task-dependency-mapper sessions run, at most 3
//   assessment: the last session's result
//   stop:       null, or { task, attempts, findings, edgesFile, validationFile, reasoning } when
//               no attempt validated; `error` and `headline` then name the Task and each finding
// With `apply: false`, `scoring` is null and `ok` means the diff was proposed.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, settled: false, attempts: 0, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
const target = a.task
if (!(typeof target === 'string' && /^[A-Za-z0-9._-]+$/.test(target))) {
  return { ok: false, settled: false, attempts: 0, error: '`task`, the id of the one Task to assess, is required' }
}
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const scope = ` --task ${shq(target)}`
const applies = a.apply !== false
const project = { repoPath: repo, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }
const fail = (error, extra) => ({
  ok: false,
  apply: applies,
  settled: false,
  attempts: 0,
  workDir: work,
  task: target,
  error,
  ...(extra || {}),
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
})

// ── Context ──────────────────────────────────────────────────────────────────────
//
// The plan records the fingerprint the Task is assessed at. The context writes every open
// Task to the corpus directory and an index of their titles, Epics, repositories and
// statuses, and lists every edge standing between this Task and another open Task, with
// the reason recorded for each owned one. Both refuse a Task written by elaboration.
enter('Context')
const planFile = file('assess-plan.json')
const contextDir = file('context')
const contextFile = file('context.json')
const corpusDir = `${contextDir}/task`
const indexFile = `${contextDir}/index.md`
const taskFile = `${corpusDir}/${target}.md`
const planned = await runStep('assess-plan', cmd('assess-plan', `--level task${scope} --out ${shq(planFile)}`))
if (!planned) return fail('the assessment plan could not be computed; nothing was written')
const plan = planned.summary || {}
const contexted = await runStep(
  'assess-context',
  cmd('assess-context', `${scope.trim()} --dir ${shq(contextDir)} --out ${shq(contextFile)}`)
)
if (!contexted) return fail('the assessment context could not be written; nothing was written', { plan })
const context = contexted.summary || {}

// ── Assess ───────────────────────────────────────────────────────────────────────
enter('Assess')
const edgesFile = file('edges.json')
const reasoningFile = file('reasoning.md')
const ASSESS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['edgesPath', 'edgeCount', 'valid', 'relatedRead'],
  properties: {
    edgesPath: { type: 'string' },
    reasoningPath: { type: 'string' },
    edgeCount: { type: 'integer' },
    valid: { type: 'boolean' },
    // Never bounds here, and no ceiling is stated for either: both report what the
    // mapper read and what it could not settle, and one entry over would take the whole
    // proposal down with it.
    relatedRead: { type: 'array', items: { type: 'string' } },
    unsure: { type: 'array', items: { type: 'string' } },
  },
}
// WHAT THIS ASSESSMENT IS EXPECTED TO READ — an expectation, not an instruction.
//
// `relatedRead` reports the Tasks it read in full and `unsure` the edges it could not
// settle. Both are READS: their size is a property of the corpus (every open Task)
// and of how tangled this Task's dependencies actually are. Nothing is stated to the
// mapper about either count, because "report at most N of what you read" can only be
// honoured by under-reporting. What DOES bound the read is already in the brief: search
// first, and read no Task the search did not find related.
//
// The figures below are what this script expects, used only to flag a count worth a look.
// Raised from the 40 and 20 that used to be schema bounds — a Task touching a broad
// decision legitimately reads more than 40.
const RELATED_READ_EXPECTED = 80
const UNSURE_EXPECTED = 40
const THE_TEST = `THE TEST. An edge from A to B says B cannot be built until A is built, because B consumes something A provides — an API, an event contract, a table, an IAM grant, a deployed resource. Sharing a domain, a vocabulary, a repository or an Epic is not an edge. Both ends are Tasks: no end is a Story or an Epic. When in doubt an edge is left out, because a false edge serializes work that could run in parallel.`
const assessPrompt = `Assess the build dependencies of ONE Task, ${target}, which was created outside elaboration. ${target} is new or has changed.

THE FILES.
- ${target}: ${taskFile}
- The context: ${contextFile}. \`standing\` lists every edge between ${target} and another open Task, in either direction, as {from, to, type, owned, reason, confidence, setBy, setAt}; \`from\` is the Task built first. \`reason\` is the one recorded when the edge was set, or null.
- The corpus: ${corpusDir}, one file per open Task, named <id>.md.
- The index: ${indexFile}, one line per open Task with its title, Epic, repository, status and file.

${THE_TEST}

Work in this order:
1. Read ${target}.
2. Name what it consumes and what it provides.
3. Search the corpus with Grep, and the index, for the Tasks that provide what ${target} consumes or consume what it provides. Read no Task the search did not find related.
4. Read in full every related Task, and the Task at the other end of every standing edge.
5. Apply the test in both directions: an edge from another Task to ${target} where ${target} consumes what that Task provides, and an edge from ${target} to another Task where that Task consumes what ${target} provides.
6. Write ${edgesFile} as {"edges": [{"from", "to", "reason", "confidence"}], "withdrawn": [{"from", "to", "reason"}]}. \`edges\` holds EVERY edge to or from ${target} that passes the test — a standing one it keeps included — and no edge that does not touch ${target}. \`withdrawn\` holds every standing edge with \`owned: true\` that is not in \`edges\`, with a reason that answers the reason recorded for it. Every reason names the artifact and which Task provides it; \`confidence\` is \`high\`, \`medium\` or \`low\`. A standing edge with \`owned: false\` was made by hand: leave it out of both lists. No edge is a valid result. Write the reasoning, per edge and per withdrawal, to ${reasoningFile}.
7. Validate: \`${cmd('validate', `--edges ${shq(edgesFile)}${scope}`)}\` — fix the file until \`ok\` is true. It refuses an edge that does not touch ${target}, an edge whose ends are not both open Tasks, a missing reason, an owned standing edge left unaccounted, a withdrawal of an edge that is not an owned standing edge, and a cycle against every other Task edge. A cycle you cannot remove by dropping one of your own edges that fails the test is reported, not forced: return \`valid: false\` and name the cycle in \`unsure\`.

Return the edge file path, the reasoning file path, the edge count, whether the final validation passed, \`relatedRead\` — the id of every Task you read in full, other than ${target} — and each edge you were unsure of with what would settle it.`

// Code validates every attempt, whatever the session claims. A proposal that does not
// validate is assessed again with the validator's findings, at most ASSESS_ATTEMPTS
// sessions in all; one that never validates writes nothing, and the run stops naming the
// Task and each finding.
// TWO, not three. Step 7 of the brief already has the mapper run the validator itself
// and fix the file until `ok` is true, so this outer loop is a SECOND loop around a
// session that already self-corrects — and each extra turn costs a mapper session plus a
// runner session. One outer correction pass catches the case the session got wrong; a
// third attempt at the same proposal, with the same findings, is where the sibling
// dependency-assessment mini spends nothing at all, because it keeps the loop in-session.
const ASSESS_ATTEMPTS = 2
const FINDING_KEYS = [
  'badScope',
  'outsideScope',
  'missingReason',
  'unaccounted',
  'withdrawnNotOwned',
  'keptAndWithdrawn',
  'notTaskToTask',
  'cycle',
  'dangling',
  'selfEdges',
  'ontoClosed',
  'fromClosed',
  'duplicates',
]
function findingsOf(report) {
  const found = {}
  for (const key of FINDING_KEYS) {
    const v = report ? report[key] : null
    if ((typeof v === 'string' && v) || (Array.isArray(v) && v.length)) found[key] = v
  }
  return found
}
const validationFile = (n) => file(`validation-${n}.json`)
let assessed = null
let settled = false
let attempts = 0
let findings = {}
for (let attempt = 1; attempt <= ASSESS_ATTEMPTS; attempt++) {
  attempts = attempt
  const prompt =
    attempt === 1
      ? assessPrompt
      : `${assessPrompt}

Attempt ${attempt - 1} did not validate. The validator's findings, verbatim: ${JSON.stringify(findings)}. The full report is ${validationFile(attempt - 1)}. Revise ${edgesFile} until every finding is gone, keeping to THE TEST: an edge that fails the test is dropped, never kept to satisfy the validator; an owned standing edge you drop goes in \`withdrawn\` with a reason; a cycle through an edge with \`owned: false\` is not yours to remove — name it in \`unsure\`.`
  const session = await settleAgent(prompt, {
    label: `task-dependency-mapper:${target}#${attempt}`,
    phase: 'Assess',
    // A maker: it proposes the edge set. Stated here rather than inherited.
    effort: 'medium',
    agentType: 'agent-teams-workforce:task-dependency-mapper',
    schema: ASSESS_SCHEMA,
  })
  if (!session) break
  assessed = session
  checkLimit(`Assess (${target}#${attempt})`, 'relatedRead', session.relatedRead, RELATED_READ_EXPECTED)
  checkLimit(`Assess (${target}#${attempt})`, 'unsure', session.unsure, UNSURE_EXPECTED)
  // Printed without --out, so the whole report comes back.
  const report = await runStep(
    `validate#${attempt}`,
    `set -o pipefail; ${cmd('validate', `--edges ${shq(edgesFile)}${scope}`)} | tee ${shq(validationFile(attempt))}`
  )
  if (!report) break
  if (report.ok === true) {
    settled = true
    findings = {}
    break
  }
  findings = findingsOf(report)
}
const stopped = !settled && !!assessed && attempts === ASSESS_ATTEMPTS && failures.length === 0
const stop = stopped
  ? {
      task: target,
      attempts,
      findings,
      edgesFile,
      validationFile: validationFile(attempts),
      reasoning: reasoningFile,
    }
  : null
const stopMessage = stop
  ? `${target}: its edge proposal did not validate after ${ASSESS_ATTEMPTS} assessments — ${Object.entries(findings)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
      .join('; ')}`
  : null
if (stopMessage) log(stopMessage)

// ── Apply ────────────────────────────────────────────────────────────────────────
enter('Apply')
let edges
if (settled && !applies) {
  // The dry run prints its full result, which is also kept in the run directory: the
  // diff is the deliverable, so it comes back whole rather than as counts.
  const diffFile = file('apply-edges-dry-run.json')
  const proposed = await runStep(
    'apply-edges --dry-run',
    `set -o pipefail; ${cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)}${scope} --dry-run`)} | tee ${shq(diffFile)}`
  )
  const diff = (proposed && proposed.plan) || {}
  edges = proposed
    ? {
        applied: false,
        proposed: proposed.validation ? proposed.validation.ok === true : false,
        scope: proposed.scope || target,
        added: diff.add || [],
        converted: diff.convert || [],
        removed: diff.remove || [],
        withdrawn: proposed.withdrawn || [],
        unchanged: diff.unchanged ?? null,
        protectedHandMadeEdges: diff.protectedHandMadeEdges || [],
        planned: proposed.planned || [],
        validation: proposed.validation || null,
        diffFile,
        edgesFile,
        reasoning: reasoningFile,
        unsure: assessed.unsure || [],
      }
    : { applied: false, proposed: false, reason: 'the dry run did not complete; nothing was written' }
} else if (settled) {
  // The full result is printed and kept in the run directory, so the withdrawals come back
  // with their reasons.
  const applyFile = file('apply-edges.json')
  const applied = await runStep(
    'apply-edges',
    `set -o pipefail; ${cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)}${scope}`)} | tee ${shq(applyFile)}`
  )
  edges = {
    ...(applied ? applied.summary || {} : { applied: false }),
    withdrawn: (applied && applied.withdrawn) || [],
    resultFile: applyFile,
    edgesFile,
    reasoning: reasoningFile,
    unsure: assessed.unsure || [],
  }
} else {
  edges = {
    applied: false,
    reason: stop
      ? `the proposed edge set did not validate after ${ASSESS_ATTEMPTS} assessments; the tracker keeps its current edges`
      : assessed
        ? 'the proposed edge set could not be validated; the tracker keeps its current edges'
        : 'the task-dependency-mapper returned no result; the tracker keeps its current edges',
    edgesFile,
    reasoning: reasoningFile,
    unsure: (assessed && assessed.unsure) || [],
  }
}
if (edges.proposed) log(`Proposed edges (${target}): ${edges.added.length} to add, ${edges.converted.length} to convert, ${edges.removed.length} to withdraw, ${edges.unchanged} unchanged — nothing written; detail in ${edges.diffFile}`)
if (edges.applied) log(`Edges (${target}): ${edges.added} added, ${edges.converted} converted, ${edges.removed} withdrawn, ${edges.unchanged} unchanged`)

// ── Score ────────────────────────────────────────────────────────────────────────
//
// Edges decide Task RR-OE, so an applied assessment is followed by scoring. Scoring never
// assesses.
let scoring = null
const scores = applies && edges.applied === true && a.score !== false
if (scores) {
  enter('Score')
  scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
}

return {
  ok: settled && (applies ? edges.applied === true : edges.proposed === true) && failures.length === 0 && (!scores || (!!scoring && scoring.ok === true)),
  apply: applies,
  settled,
  attempts,
  workDir: work,
  task: target,
  plan,
  context,
  assessment: assessed || { failed: true },
  edges,
  scoring,
  stop,
  ...(stop ? { error: stopMessage, headline: stopMessage } : {}),
  ...(limitFindings.length ? { limitFindings } : {}),
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
