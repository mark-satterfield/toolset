export const meta = {
  name: 'wsjf-scoring',
  description:
    "Scores every open Epic and Task with WSJF, and never sets a dependency: it reads the edges from beads. Edges decide ELIGIBILITY, WSJF decides PRIORITY among what is eligible. A model judges only where the source content changed or a value is missing. Each Epic's value, time criticality and — for an Epic without Tasks — size are judged from its full PRD, one Epic per session, against the rubric's rungs and the reference jobs, with no other Epic's PRD or values as an input; each Epic's Tasks are sized together, in a session per Epic. Every size is on one Fibonacci scale with a plausible range and a size confidence, kept apart from the value confidence. A judgment off the rubric's scale is rejected and reported, and the rest are written. A judging session that returns nothing fails the run and names the items it left unjudged; the judgments that did return are still recorded and the arithmetic still runs. Then the arithmetic — Epic RR-OE, the Architectural Enabler measure, from reachability over the Epic architecture-dependency edges, Epic size as the plain sum of its Tasks' sizes, Task RR-OE, the value a Task inherits, every WSJF — runs over every open item, and only values that changed are written. `all` includes items that already have a value; `rejudge` judges the existing values of the items included again; `only` restricts the judging to named items; `dryRun` writes nothing.",
  whenToUse: "Scoring after Epics or Tasks are added or changed, or after dependency assessment applies edges; with all and rejudge, re-judging every Epic and Task.",
  phases: [
    { title: "Plan", detail: "fingerprints decide what is judged" },
    { title: "Judge", detail: "a session per Epic, and a session per Epic's Tasks" },
    { title: "Apply", detail: "judged values, then the arithmetic over every open item" },
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
// writes its full result to a file in the run directory and prints only a summary, so no
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
//   repoPath:     string,    // absolute path of the repository whose `bd` tracker is scored
//   pluginRoot:   string,    // absolute path of this plugin's root
//   workDir:      string,    // absolute path of a directory for this run's files; one per run
//   sadPath?:     string,    // the arc42 SAD (ATW_SAD_PATH): what already exists informs size
//   projectRoot?: string,    // the project root (ATW_PROJECT_ROOT), likewise
//   all?:         boolean,   // include items that already have a value
//   rejudge?:     boolean,   // judge again the existing values of the items included
//   only?:        string[],  // judge only these open Epics and Tasks
//   dryRun?:      boolean,   // compute everything and write nothing to the tracker
// }
//
// Returns: { ok, workDir, dryRun, plan, judging, judgingFailed, error?, record, score,
//            failures, dispatchFailed, dispatchFailures }
//
// A judging session that returns nothing fails the run: `ok` is false and
// `judgingFailed` names the items it left unjudged — the Epic of an Epic session, every
// Task of a Task group (the group keys are in `judging.task.failedGroups`) — and `error`
// names them too. The judgments that did return are still recorded and the arithmetic
// still runs; the unjudged items keep no new value and stay to judge.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
const ID = /^[A-Za-z0-9._-]+$/
const only = a.only == null ? [] : a.only
if (!Array.isArray(only) || !only.every((id) => typeof id === 'string' && ID.test(id))) {
  return { ok: false, error: '`only` must be a list of bead ids' }
}
const dryRun = a.dryRun === true
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const flags = `${a.all === true ? '--all ' : ''}${a.rejudge === true ? '--rejudge ' : ''}${only.length ? `--only ${shq(only.join(','))} ` : ''}`
const dry = dryRun ? ' --dry-run' : ''
const stop = (error, extra) => ({ ok: false, workDir: work, dryRun, error, ...extra, failures, dispatchFailed: dispatchDeaths().length > 0, dispatchFailures: dispatchDeaths() })

// ── Plan ─────────────────────────────────────────────────────────────────────────
enter('Plan')
const planFile = file('score-plan.json')
const planned = await runStep('score-plan', cmd('score-plan', `${flags}--out ${shq(planFile)}`))
if (!planned) return stop('the plan could not be computed; nothing was judged or written')
const plan = planned.summary || {}
log(`Plan: ${plan.epicsToJudge || 0} Epic(s) and ${plan.tasksToJudge || 0} Task(s) to judge, ${plan.toAdopt || 0} stored value(s) to adopt`)

const prdDir = file('prd')
const inputs = {}
for (const level of ['epic', 'task']) {
  if (!((level === 'epic' ? plan.epicsToJudge : plan.tasksToJudge) > 0)) continue
  const path = file(`judge-input-${level}.json`)
  const out = await runStep(`judge-input:${level}`, cmd('judge-input', `--plan ${shq(planFile)} --level ${level}${level === 'epic' ? ` --prd-dir ${shq(prdDir)}` : ''} --out ${shq(path)}`))
  if (out) inputs[level] = { path, summary: out.summary || {} }
}
const epicInput = inputs.epic
const epicIds = epicInput && Array.isArray(epicInput.summary.ids) ? epicInput.summary.ids.filter((id) => typeof id === 'string' && ID.test(id)) : []
const taskGroups = inputs.task && Array.isArray(inputs.task.summary.groups)
  ? inputs.task.summary.groups.filter((g) => g && typeof g.key === 'string' && ID.test(g.key) && Array.isArray(g.tasks) && g.tasks.length)
  : []
if (inputs.epic && epicIds.length !== plan.epicsToJudge) {
  return stop(`the plan names ${plan.epicsToJudge} Epic(s) to judge and the judge input lists ${epicIds.length}; nothing was judged or written`, { plan })
}

// ── Judge ────────────────────────────────────────────────────────────────────────
//
// A session per Epic, and a session per Epic's Tasks. Each writes its own file and none
// writes to the tracker, so they run concurrently, JUDGE_CONCURRENCY at a time.
enter('Judge')
const JUDGE_CONCURRENCY = 6
const JUDGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['path', 'judged'],
  properties: {
    path: { type: 'string' },
    judged: { type: 'integer' },
    // An Epic session judges one item; a Task session judges one Epic's Tasks. The
    // Never bound here: `unscored` reports what a session could not judge, and a bound
    // on it would destroy the judgments that DID come back in the same result.
    unscored: { type: 'array', items: { type: 'string' } },
  },
}
// A session judges one Epic, or one Epic's Tasks, and `unscored` names the ones it could
// not judge — a READ of the work it was handed, not a volume it chooses. So nothing is
// stated to it: an honest "I could not judge these 61" must come back whole. The figure
// below is what this script EXPECTS, used only to flag a count worth looking at; it is
// raised from the 60 that used to be a schema bound, because 60 sat close enough to a
// large Epic's Task count to fire on ordinary output.
const UNSCORED_EXPECTED = 200
const epicDir = file('judgments/epic')
const taskDir = file('judgments/task')

const JUDGE_RULES = `JOB SIZE follows the rubric's "Job Size" section, which is the same at both levels: the relative amount of work to deliver the outcome, judged against the agent pipeline as the reference capability — not calendar time, not human effort, not a count of repositories. Weigh volume, complexity, knowledge and uncertainty, as the rubric defines them, together to place the item; never score them separately or add them up. The numbers express approximate relative magnitude, not measured ratios or time commitments, and an item's tracking type does not decide its size: an Epic and a Task can both be 5. The scale is Fibonacci (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, and upward). Place each size by comparison with the \`referenceJobs\` in the judge-input file — elaborated Epics, each with its original estimate and its refined size, the sum of its Tasks — and name the comparison in the rationale. When \`referenceJobs\` is empty, judge knowledge and uncertainty from what already exists: the architecture document${a.sadPath ? ` (${a.sadPath})` : ''}, the existing code${a.projectRoot ? ` (under ${a.projectRoot})` : ''}, and the other artifacts that show what is already decided or built and what must be decided or built from scratch. Every size carries \`sizeLow\` and \`sizeHigh\`, the plausible range with the estimate inside it, and \`sizeConfidence\`, an integer percent. What remains unknown widens the range and lowers the size confidence.

THE RUBRIC OWNS ITS BANDS. The rungs in \`agent-teams-workforce:wsjf\` are the whole scale. RR-OE, reachability and WSJF are arithmetic computed after you return; they are not in your input and are not yours to state, estimate or reason about.`

const judgeEpic = (id) => settleAgent(
  `You judge ONE Epic, ${id}, under \`agent-teams-workforce:wsjf\` at Epic level. Load that skill with the Skill tool and follow it.

An Epic is a PRD: a business requirement. Read its full requirements document at ${prdDir}/${id}.md, to the end. Its entry in ${inputs.epic && inputs.epic.path} (the item whose \`id\` is ${id}) says whether it \`hasTasks\`; the same file holds the \`referenceJobs\`. Judge it from its own document against the rubric's rungs and the reference jobs, using the SAD and the project root for what is already decided or built. Read no other Epic's PRD and no other Epic's values: each Epic is judged on its own, so adding an Epic never moves another Epic's judged values.

${JUDGE_RULES}

Judge \`userBusinessValue\`, \`timeCriticality\` and their \`confidence\` (integer percent — the value confidence, covering UBV and TC only), and — only when \`hasTasks\` is false — the size estimate \`jobSize\` with \`sizeLow\`, \`sizeHigh\` and \`sizeConfidence\`. An Epic with Tasks takes its size from them. An Epic is sized before its design exists: judge the work to deliver the requirement from the requirement itself and from institutional knowledge — the SAD and what is already decided — and never invent a solution in order to size it. Missing implementation design is normal at this stage and is not itself evidence of exceptional difficulty, so it does not enlarge the size; let it show in the range and the size confidence. Uncertainty enlarges an Epic only where the PRD leaves an unresolved fact that could materially change the work — ambiguous scope, unknown feasibility, or assumptions with substantially different consequences. Each rationale cites the PRD.

Write ${epicDir}/${id}.json as ONE JSON object: {"rubric": "epic-wsjf", "scores": [{"id": "${id}", "userBusinessValue", "timeCriticality", "confidence", "jobSize", "sizeLow", "sizeHigh", "sizeConfidence" (the four size fields only when hasTasks is false), "rationale": {"userBusinessValue", "timeCriticality", "jobSize"}}], "unscored": []}, or, when you cannot judge it, {"rubric": "epic-wsjf", "scores": [], "unscored": [{"id": "${id}", "reason"}]}.

Return the path you wrote, how many items you judged (1 or 0), and the ids you could not judge.`,
  // A scorer against a published rubric, not a decider: `rejudge` re-runs it by design
  // and the arithmetic is recomputed on every edge change, so no ruling here is expensive
  // to reverse. At `high` this was the portfolio's largest recurring cost — one session
  // per open Epic, on every seeding.
  { label: `judge:epic:${id}`, phase: 'Judge', effort: 'medium', schema: JUDGE_SCHEMA }
)

const judgeTasks = (group) => {
  const whose = group.epic ? `the Tasks of one Epic, ${group.epic}` : `one Task with no Epic, ${group.key}`
  return settleAgent(
    `You size ${whose}, under \`agent-teams-workforce:wsjf\` at Task level. Load that skill with the Skill tool and follow it. You judge Job Size and nothing else; value, time criticality and their confidence are inherited from each Task's Epic by arithmetic. A Task is sized from the established architecture, design and implementation instructions it carries.

Read ${inputs.task && inputs.task.path}. Size exactly these items in it, each an open Task with its own \`description\` and the Epic it sits under: ${group.tasks.join(', ')}. The same file holds the \`referenceJobs\`.

${JUDGE_RULES}

For each of those Tasks, judge the size estimate \`jobSize\` with \`sizeLow\`, \`sizeHigh\` and \`sizeConfidence\`. A Task above 13 should have been split. It is a decomposition fault: say so in its rationale, and record the size you judged. Do not reduce it to 13.

Write ${taskDir}/${group.key}.json as ONE JSON object: {"rubric": "task-wsjf", "scores": [{"id", "jobSize", "sizeLow", "sizeHigh", "sizeConfidence", "rationale": {"jobSize"}}], "unscored": [{"id", "reason"}]}, with exactly one entry per Task listed above, in \`scores\` or in \`unscored\`, and none for any other item.

Return the path you wrote, how many Tasks you judged, and the ids you could not judge.`,
    { label: `judge:task:${group.key}`, phase: 'Judge', effort: 'medium', schema: JUDGE_SCHEMA }
  )
}

// Each job carries the ids of the items it judges, so a session that returns nothing
// names every item it left unjudged: one Epic, or every Task of one group.
const jobs = [
  ...epicIds.map((id) => ({ level: 'epic', key: id, ids: [id], run: () => judgeEpic(id) })),
  ...taskGroups.map((g) => ({ level: 'task', key: g.key, ids: g.tasks.slice(), run: () => judgeTasks(g) })),
]
const judging = {
  epic: { sessions: 0, judged: 0, failed: [], failedSessions: 0 },
  task: { sessions: 0, judged: 0, failed: [], failedGroups: [], failedSessions: 0 },
}
for (let i = 0; i < jobs.length; i += JUDGE_CONCURRENCY) {
  const batch = jobs.slice(i, i + JUDGE_CONCURRENCY)
  const results = await parallel(batch.map((job) => () => job.run()))
  batch.forEach((job, n) => {
    const out = results[n]
    const tally = judging[job.level]
    tally.sessions += 1
    if (out) {
      tally.judged += out.judged || 0
      checkLimit(`Judge (${job.level}:${job.key})`, 'unscored', out.unscored, UNSCORED_EXPECTED)
      return
    }
    tally.failedSessions += 1
    tally.failed.push(...job.ids)
    if (job.level === 'task') tally.failedGroups.push(job.key)
  })
}
const judgingFailed = [...judging.epic.failed, ...judging.task.failed]
log(`Judged ${judging.epic.judged} Epic(s) in ${judging.epic.sessions} session(s) and ${judging.task.judged} Task(s) in ${judging.task.sessions} session(s); ${judging.epic.failedSessions + judging.task.failedSessions} session(s) failed, leaving ${judgingFailed.length} item(s) unjudged`)

// ── Apply ────────────────────────────────────────────────────────────────────────
//
// Judged values first, then the arithmetic, which reads them together with the edges
// already in the tracker. The writes run one after another because they write the same
// tracker.
enter('Apply')
const recordArgs = [`--plan ${shq(planFile)}`]
if (judging.epic.sessions > judging.epic.failedSessions) recordArgs.push(`--epics-dir ${shq(epicDir)}`)
if (judging.task.sessions > judging.task.failedSessions) recordArgs.push(`--tasks-dir ${shq(taskDir)}`)
let recorded = null
if ((plan.epicsToJudge || 0) + (plan.tasksToJudge || 0) + (plan.toAdopt || 0) > 0) {
  const out = await runStep('record', cmd('record', `${recordArgs.join(' ')}${dry} --out ${shq(file('record.json'))}`))
  recorded = out ? out.summary || {} : null
  if (recorded && recorded.rejected) log(`Record: ${recorded.rejected} judgment(s) rejected — detail in ${file('record.json')}`)
}

const scored = await runStep('score', cmd('score', `--out ${shq(file('score.json'))}${dry}`))
const score = scored ? scored.summary || {} : null
if (score) {
  log(
    `Scored ${score.epicsScored} Epic(s) (${score.epicsWritten} written) and ${score.tasksScored} Task(s) (${score.tasksWritten} written); ` +
      `${score.unscored} unscored, ${score.incomplete} incomplete, ${score.outsideRange || 0} refined size(s) outside their estimate's range — detail in ${file('score.json')}`
  )
}

const judgingError = judgingFailed.length
  ? { error: `judging failed for ${judgingFailed.length} item(s): ${judgingFailed.join(', ')}; their values were not recorded and they stay to judge` }
  : {}

return {
  ok: !!score && failures.length === 0 && judgingFailed.length === 0,
  workDir: work,
  dryRun,
  plan,
  judging,
  judgingFailed,
  ...judgingError,
  record: recorded,
  score,
  failures,
  ...(limitFindings.length ? { limitFindings } : {}),
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
