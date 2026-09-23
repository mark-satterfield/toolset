export const meta = {
  name: 'gate-enforce',
  description:
    'Reusable phase gate. DETERMINISTIC checks are evaluated first, directly against the artifact and with no model turn: a phase that failed one is looped immediately with the observed value, and a gate whose criteria are all mechanical passes without adjudication. Every judgment criterion carries a CLASS: a `constitutive` one is a hard stop, while a `competitive` one — the default for any criterion nobody deliberately marked otherwise — can never block, so it is recorded as a flag and never adjudicated. Only CONSTITUTIVE criteria go to an independent phase-gate-enforcer, told which checks are already settled so it cannot re-open them, and it returns pass / loop / escalate; a gate with no constitutive criterion passes on its checks with no session at all. Every verdict carries `deterministicChecks`, so a caller can tell a criterion that was MEASURED against the artifact from one that was argued about. A blocking verdict that names no reason is asked again once with the defect named, and a second reasonless one comes back as `malformedVerdict`, never as a finding against the work. Enforces segregation of duties: the judge never produced the work it judges.',
  phases: [{ title: 'Gate', detail: 'phase-gate-enforcer adjudicates the artifact' }],
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

// ── THE `dispatchFailed` CONTRACT THIS GATE OWES ITS CALLER ──────────────────────
//
// A judge that DIED did not find the work wanting — it never ruled. This file built
// `dispatchFailures` and defined `dispatchDeaths` above and then called neither, so a dead
// enforcer returned null, and every caller reads a null verdict as `ok:false, "gate N
// returned no verdict"` and ends the phase. A phase whose work is COMPLETE AND DURABLE was
// therefore discarded because the read-only judge hit an account limit, and it was filed as
// a failure of that phase rather than of the environment — which is how a bead gets blamed,
// and eventually quarantined, for a wall nobody could have avoided.
//
// The asymmetry is the same one that governs the producing phases: a death is reported AS a
// death, so the caller can tell "the work is bad" from "nobody looked". Every gate exit that
// comes of a dead dispatch carries `dispatchFailed: true` and the identities of what died.
const failDispatch = (reason, ...phases) => {
  const deaths = dispatchDeaths(...phases)
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: reason,
    escalateTo: 'upstream',
    flags: [`gate-dispatch-failed: ${reason}`],
    ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
  }
}

// args: {
//   gate: string,                 // gate id, e.g. "2a"
//   phaseName: string,            // human name of the phase being judged
//   criteria: (string | { text: string, class?: 'constitutive'|'competitive' })[],
//                                 // JUDGMENT criteria — adjudicated by the model. See the
//                                 // classification block below. A PLAIN STRING IS
//                                 // COMPETITIVE: a criterion is a hard stop only when
//                                 // someone deliberately said so.
//   calibration?: string,         // optional per-gate calibration — what THIS gate must
//                                 // block on and what it must not. Rendered prominently.
//   checks?: [{ field, equals?, nonEmpty?, matches?, notMatches?, label? }],
//                                 // DETERMINISTIC criteria, see below. `matches` and
//                                 // `notMatches` are regular-expression SOURCE strings
//                                 // (no delimiters, no flags), tested case-insensitively
//                                 // against the field rendered as text.
//   artifact: any,                // the phase output under review
//   escalateTargets?: string[],   // upstream phases this gate may escalate to
//   structural?: { requireOk?: boolean, required?: string[], nonEmpty?: string[] },
//                                 // STRUCTURAL criteria — see below. Expressed here rather
//                                 // than as hand-written `checks` because every gate needs
//                                 // the same three questions answered and spelling them out
//                                 // per call site is how they came to be answered nowhere.
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

// ── Criterion CLASS, and why the default is passive ───────────────────────────
//
// The prompt below used to say "Pass criteria (ALL must hold)" and, separately,
// "constitutive criteria are hard stops" — while `criteria` arrived as a flat list of
// strings with nothing marking WHICH ones were constitutive. A judge told hard stops
// exist, given no way to identify them, and asked for a verdict defaults to strict, so
// every criterion behaved as a hard stop.
//
// So a criterion now carries its class, and an UNMARKED criterion is COMPETITIVE. The
// asymmetry is deliberate: a wrongly-passed competitive concern costs a flag, and a
// wrongly-failed gate costs a burned loop budget and a dead run. An over-passive gate can
// be tightened one criterion at a time; an over-strict one silently kills correct work.
//
// A competitive criterion can never change the verdict, so it is never sent to a judge:
// it rides out as a flag. Only constitutive criteria are adjudicated, and a gate that
// declares none passes on its deterministic checks without a session.
const CRITERION_CLASSES = ['constitutive', 'competitive']
const criteria = (Array.isArray(a.criteria) ? a.criteria : [])
  .map((c) => {
    if (typeof c === 'string') return { text: c, class: 'competitive' }
    if (c && typeof c === 'object' && typeof c.text === 'string') {
      // An unrecognised class is not an excuse to invent a hard stop. Fall back to the
      // passive default and let the criterion be flagged rather than block the run.
      return { text: c.text, class: CRITERION_CLASSES.includes(c.class) ? c.class : 'competitive' }
    }
    return null
  })
  .filter(Boolean)
// ── THE ARTIFACT AS THE JUDGE READS IT ────────────────────────────────────────
// Captured test output rides on the artifact whole — a Red artifact's `evidence` is every
// writer's run joined — and the enforcer's prompt used to inline all of it. The judge needs
// the shape of a failure, not every line of a long traceback, and the deterministic checks
// below still measure the UNCUT artifact. So only the prompt copy of a long string is cut,
// keeping its head and its tail (where a test runner prints its summary), and it says so.
const PROMPT_STRING_CAP = 6000
const PROMPT_STRING_HEAD = 4000
const PROMPT_STRING_TAIL = 2000
function capForPrompt(value, depth) {
  if (typeof value === 'string') {
    if (value.length <= PROMPT_STRING_CAP) return value
    const omitted = value.length - PROMPT_STRING_HEAD - PROMPT_STRING_TAIL
    return `${value.slice(0, PROMPT_STRING_HEAD)}\n…[${omitted} characters omitted from this prompt — the deterministic checks read the full value]…\n${value.slice(-PROMPT_STRING_TAIL)}`
  }
  if (!value || typeof value !== 'object' || depth > 8) return value
  if (Array.isArray(value)) return value.map((v) => capForPrompt(v, depth + 1))
  const out = {}
  for (const [k, v] of Object.entries(value)) out[k] = capForPrompt(v, depth + 1)
  return out
}
const artifactText =
  typeof a.artifact === 'string' ? capForPrompt(a.artifact, 0) : JSON.stringify(capForPrompt(a.artifact ?? {}, 0), null, 2)

// ── Deterministic checks, evaluated BEFORE any model turn ─────────────────────
//
// Some gate criteria are not judgments at all. "The previously-failing test now
// passes" is a boolean the phase already reported and already proved by running
// the suite; handing it to a model to reason about re-derives by discussion what
// execution settled, and pays a full subagent turn to do it. Worse, a phase that
// plainly failed still paid that turn before being told so.
//
// These are declarative rather than functions because args cross a workflow
// boundary as JSON. Each names a field on the artifact and the shape it must have.
// A failure here is unambiguous, so it short-circuits to a loop verdict with the
// observed value as feedback and no model is consulted. Judgment criteria —
// "the test asserts real behavior", "the change is minimal" — stay with the model,
// which is told the deterministic ones are already settled so it does not re-open
// them.
//
// `matches` / `notMatches` exist for NEGATIVE CONTROLS over captured output — the
// class of check a model can always argue with in prose but cannot argue with as a
// regex. The motivating case: Red "evidence" whose captured output is a collection or
// import failure (`ModuleNotFoundError`, `collected 0 items`) rather than a product
// failure. Carried as prose for the enforcer to weigh, that was routinely weighed away.
//
// CHECKS STAY HARD, AND THAT IS WHAT MAKES THE PASSIVE DEFAULT ABOVE SAFE. A check is
// MEASURED against the artifact, not argued about: it has no class, it is always
// blocking, and it short-circuits before any model turn. Real facts stay enforced mechanically
// precisely so prose judgments can safely become flags. A gate that needs something to
// be genuinely non-negotiable should express it here as a check wherever the artifact
// can carry the field, and only fall back to a `constitutive` criterion when it cannot.
// ── STRUCTURAL checks, derived BEFORE any quality judgment ────────────────────
//
// A gate used to ask a model whether work was good before anything established that the
// work EXISTS. Three questions are not judgments at all — did the phase report ok, did it
// produce the artifacts it is answerable for, and is the set it was asked to fill
// non-empty — and a phase that fails one of them has produced nothing there is an opinion
// to have about.
//
// Getting this wrong is not a near-miss, because of where the competitive path sits. A
// gate whose criteria are all competitive passes without a judge, which is correct for a
// reviewer's opinion and catastrophic for an absent artifact: the run proceeds and the
// phases downstream build on nothing.
//
// These are ordinary DETERMINISTIC checks — the concept this file already has — so they
// short-circuit to a loop verdict before any pass is possible, carrying the observed value
// as feedback. They are simply derived from a declaration rather than hand-written
// per call site, because every gate needs the same three questions asked and spelling them
// out at each one is exactly how they came to be asked at none.
const structural = a.structural && typeof a.structural === 'object' ? a.structural : null
const structuralChecks = []
if (structural) {
  // `ok` is opt-in per gate, never universal: several minis legitimately return no `ok`
  // field at all, and asserting one against them would fail every gate they sit behind.
  // A gate declares this only when its phase genuinely reports `ok`.
  if (structural.requireOk === true) {
    structuralChecks.push({ field: 'ok', equals: true, label: 'the phase reports ok:true' })
  }
  // Presence, not shape. The default check arm treats undefined and null as unmet, which
  // is the whole question here — the artifact either came back or it did not.
  for (const field of Array.isArray(structural.required) ? structural.required : []) {
    if (typeof field === 'string' && field) {
      structuralChecks.push({ field, label: `the phase produced its required artifact '${field}'` })
    }
  }
  // "A non-empty task set where one is expected" — a decomposition that emitted no task
  // has not decomposed anything, however well it reads.
  for (const field of Array.isArray(structural.nonEmpty) ? structural.nonEmpty : []) {
    if (typeof field === 'string' && field) {
      structuralChecks.push({ field, nonEmpty: true, label: `'${field}' is present and non-empty` })
    }
  }
}
// Structural first, so the feedback on a broken artifact names what is missing before it
// names anything a caller's own check observed about it.
// A check that is not an object with a field names nothing to measure; reading one used to
// throw, which ended the run from inside a read-only gate.
const checks = [...structuralChecks, ...(Array.isArray(a.checks) ? a.checks : []).filter((c) => c && typeof c === 'object' && typeof c.field === 'string' && c.field)]
// Non-empty means something is THERE: a list of blank strings (`smokeTestFiles: [""]`) or an
// empty object is not a smoke suite, a test file or a bead set, however many slots it has.
function hasContent(value) {
  if (value === undefined || value === null) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.some((v) => hasContent(v))
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}
function asText(value) {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map((v) => asText(v)).join('\n')
  return JSON.stringify(value)
}
const checkResults = checks.map((chk) => {
  const value = a.artifact ? a.artifact[chk.field] : undefined
  let met
  // An excerpt, the way the pattern checks below quote one: a check on captured output used
  // to copy the WHOLE output into its evidence, and from there into the enforcer's prompt,
  // the verdict, the run ledger and the checkpoint.
  const observed = JSON.stringify(value)
  let evidence = `observed ${chk.field} = ${observed !== undefined && observed.length > 300 ? `${observed.slice(0, 300)}… (${observed.length} characters)` : observed}`
  if (Object.prototype.hasOwnProperty.call(chk, 'equals')) met = value === chk.equals
  else if (chk.nonEmpty) met = hasContent(value)
  else if (chk.matches || chk.notMatches) {
    const source = chk.matches || chk.notMatches
    const text = asText(value)
    let re = null
    try {
      re = new RegExp(source, 'i')
    } catch (e) {
      // An unusable pattern must not silently pass the check it was written to enforce.
      re = null
      met = false
      evidence = `check pattern /${source}/ is not a valid regular expression (${e && e.message ? e.message : e}) — the check cannot be evaluated and fails closed`
    }
    if (re) {
      const hit = re.test(text)
      met = chk.matches ? hit : !hit
      const excerpt = text.length > 300 ? `${text.slice(0, 300)}…` : text
      evidence = `${chk.matches ? 'required' : 'forbidden'} pattern /${source}/i ${hit ? 'MATCHED' : 'did not match'} ${chk.field}: ${JSON.stringify(excerpt)}`
    }
  } else met = value !== undefined && value !== null
  return {
    criterion: chk.label || `${chk.field} satisfies its required shape`,
    met,
    evidence,
  }
})
const failedChecks = checkResults.filter((r) => !r.met)

// Fail closed: a gate with NEITHER judgment criteria nor deterministic checks is a
// misconfiguration, not a pass. Refuse rather than silently green-light unjudged work.
if (!criteria.length && !checks.length) {
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}) was invoked with no pass criteria and no deterministic checks — refusing to adjudicate. Supply the gate's criteria upstream.`,
    escalateTo: (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    flags: ['gate-misconfiguration: empty criteria'],
    deterministicChecks: checkResults,
  }
}

phase('Gate')

if (failedChecks.length) {
  const detail = failedChecks.map((r) => `${r.criterion} — ${r.evidence}`).join('; ')
  // The observed value says WHICH condition failed, not why. The phase's own account of why
  // rides along, so a retry has something to act on beyond "field = false".
  const art = a.artifact && typeof a.artifact === 'object' ? a.artifact : {}
  const phaseReason = [art.reason, art.error, Array.isArray(art.failures) ? art.failures.join('; ') : '']
    .map((v) => (typeof v === 'string' ? v.trim() : ''))
    .filter(Boolean)
    .join(' | ')
    .slice(0, 2000)
  log(`Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): LOOP on deterministic check(s), no adjudication needed — ${detail}`)
  return {
    verdict: 'loop',
    criteria: checkResults,
    feedback: `The phase did not meet a mechanically-verified condition, so there is nothing to adjudicate: ${detail}.${phaseReason ? ` The phase reported: ${phaseReason}.` : ''} Fix that and re-run; do not argue the observation.`,
    flags: [],
    deterministic: true,
    deterministicChecks: checkResults,
  }
}

// Every check held. A competitive criterion cannot block, so paying a judge to rule on it
// buys nothing: it is recorded as a flag. When no constitutive criterion remains there is
// nothing left that could change the verdict, and the gate passes without a session.
const constitutiveCriteria = criteria.filter((c) => c.class === 'constitutive')
const competitiveFlags = criteria
  .filter((c) => c.class === 'competitive')
  .map((c) => `competitive criterion, not adjudicated: ${c.text}`)
if (!constitutiveCriteria.length) {
  log(
    `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): PASS on deterministic checks alone, no adjudication needed` +
      `${competitiveFlags.length ? ` — ${competitiveFlags.length} competitive criterion(s) recorded as flags` : ''}`
  )
  return {
    verdict: 'pass',
    criteria: checkResults,
    feedback: 'Every deterministic check for this gate holds, and the gate declares no constitutive criterion that could block.',
    flags: competitiveFlags,
    deterministic: true,
    deterministicChecks: checkResults,
  }
}

const settledBlock = checkResults.length
  ? `\nAlready SETTLED by direct inspection of the artifact — treat these as met and do NOT re-open them:\n${checkResults.map((r) => `- ${r.criterion} (${r.evidence})`).join('\n')}\n`
  : ''

const calibrationBlock = a.calibration
  ? `\nCALIBRATION FOR THIS GATE — read before ruling. It states what this specific gate must block on and what it must not:\n${a.calibration}\n`
  : ''

const askEnforcer = (retryNote, label) => settleAgent(
  `${retryNote}You are the phase-gate-enforcer — an INDEPENDENT gate authority. You did not produce this work; you only judge it. Do NOT modify the artifact.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}

Criteria — every one is CONSTITUTIVE: it defines whether the work is valid at all:
${constitutiveCriteria.map((c, i) => `${i + 1}. ${c.text}`).join('\n')}
${calibrationBlock}${settledBlock}
Artifact under review:
${artifactText}

Decide exactly one verdict:
- "pass": every criterion above is met. Put any non-blocking quality concern in \`flags\` — it does not change the verdict.
- "loop": a criterion is unmet AND the root cause is INSIDE this phase. Return feedback specific enough that the phase can retry without interpretation.
- "escalate": a criterion is unmet and the failure originates UPSTREAM (the phase received bad inputs). Name where it goes back to${a.escalateTargets && a.escalateTargets.length ? ` (options: ${a.escalateTargets.join(', ')})` : ''}.

An unmet criterion is a HARD STOP: the verdict is "loop" or "escalate" and is NEVER "pass". Loop or escalate only on a criterion listed above — a concern that is not one of them is a flag. The deterministic checks above were measured, not argued, and are already settled.

READING BUDGET (binding): the artifact is quoted above in full and the deterministic checks already measured everything mechanical about it. Judge what is in front of you. Do not re-derive the artifact from the codebase, do not survey the repository or the polyrepo, and do not go looking for evidence a criterion does not name. Roughly five tool calls is the expected shape; zero is normal for this role.

For each criterion, state whether it is met with evidence, quoting the criterion text exactly.`,
  {
    label,
    // The enforcer adjudicates a short structured artifact against a handful of stated
    // criteria, with the mechanical part already settled above and a binding reading
    // budget below. That is a medium-effort judgment, and at `high` it was ~9% of the
    // measured per-Epic spend on its own.
    effort: 'medium',
    phase: 'Gate',
    agentType: 'agent-teams-workforce:phase-gate-enforcer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['verdict', 'criteria', 'feedback'],
      properties: {
        verdict: { type: 'string', enum: ['pass', 'loop', 'escalate'] },
        criteria: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['criterion', 'met', 'evidence'],
            properties: {
              criterion: { type: 'string' },
              met: { type: 'boolean' },
              evidence: { type: 'string' },
            },
          },
        },
        feedback: { type: 'string' },
        escalateTo: { type: 'string' },
        flags: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)
const GATE_LABEL = `gate:${a.gate || a.phaseName || 'phase'}`
const verdict = await askEnforcer('', GATE_LABEL)

// ── The class is BINDING, not advisory ────────────────────────────────────────
//
// A `pass` cannot stand while the judge itemises a criterion as unmet. Only constitutive
// criteria were sent to it, so every unmet entry it returns is one of them — however it
// worded the criterion. Matching the text back against the caller's list would let a
// paraphrased constitutive failure pass. Entries restating a settled deterministic check
// are excluded: those were measured and held. Competitive criteria were never sent to the
// judge, so they join the flags here.
function ruleOn(verdict) {
  let ruled = verdict
  if (ruled && ruled.verdict) {
    const settledLabels = new Set(checkResults.map((r) => r.criterion))
    const unmet = (Array.isArray(ruled.criteria) ? ruled.criteria : []).filter((c) => c && c.met === false && !settledLabels.has(c.criterion))
    const unmetConstitutive = unmet
    if (competitiveFlags.length) {
      ruled = { ...ruled, flags: [...(Array.isArray(ruled.flags) ? ruled.flags : []), ...competitiveFlags] }
    }

    if (ruled.verdict === 'pass' && unmetConstitutive.length) {
      const detail = unmetConstitutive.map((c) => `${c.criterion}${c.evidence ? ` — ${c.evidence}` : ''}`).join('; ')
      log(`Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the enforcer returned PASS with an unmet CONSTITUTIVE criterion — a constitutive failure is never a pass. Converting to LOOP: ${detail}`)
      ruled = {
        ...ruled,
        verdict: 'loop',
        feedback: `A constitutive criterion is unmet, which is a hard stop: ${detail}. ${ruled.feedback || ''}`.trim(),
        classOverride: 'pass-converted-to-loop: unmet constitutive criterion',
      }
    }

    // ── A VERDICT THAT RECORDS NO REASON IS A DEFECT, NOT A RULING ───────────────
    //
    // Across the recorded runs, seventeen gates exhausted their retries and killed the run.
    // Six of those final verdicts named nothing at all — no unmet criterion, no flag, no
    // feedback — and one exhaustion was ruled `constitutive` on empty findings AND an empty
    // rationale. A retry against an empty answer has nothing to fix, so it meets the same
    // wall, spends the loop budget, and every artifact the run had already paid for is
    // discarded on the strength of a judgment that stated no reason.
    //
    // So a verdict that still BLOCKS after the class conversion above, while naming no
    // unmet criterion, no flag and no feedback, is treated as a malformed verdict rather
    // than a ruling on the work. It is surfaced the way this file already surfaces a broken
    // gate rather than broken work — an `escalate` carrying the gate and the phase by name
    // (see the empty-criteria refusal far above) — so the caller reports a defect in the
    // judgment instead of silently ruling the work constitutive.
    //
    // A verdict that DOES state a reason is untouched, however briefly it states it. This
    // weakens no gate: nothing here overturns an itemised finding, and a `pass` cannot
    // reach it.
    const statedReason =
      unmet.length > 0 ||
      // The judge's own flags, not the competitive ones merged in above: those name no reason
      // the judge gave.
      (Array.isArray(verdict.flags) && verdict.flags.some((f) => String(f == null ? '' : f).trim())) ||
      (typeof ruled.feedback === 'string' && ruled.feedback.trim().length > 0)
    if ((ruled.verdict === 'loop' || ruled.verdict === 'escalate') && !statedReason) {
      const where = `Gate ${a.gate || '?'} (${a.phaseName || 'phase'})`
      const why =
        `${where}: MALFORMED VERDICT — the enforcer returned ${ruled.verdict.toUpperCase()} but named no unmet criterion, ` +
        'no flag and no feedback. A retry has nothing to fix and a ruling has nothing to weigh, so this is a defect in the ' +
        'adjudication rather than a finding about the work. It is NOT a constitutive failure and must not be recorded as one.'
      log(why)
      ruled = {
        ...ruled,
        verdict: 'escalate',
        feedback: why,
        // Not the caller's first escalate target: nothing upstream is at fault.
        escalateTo: ruled.escalateTo || 'upstream',
        flags: [...(Array.isArray(ruled.flags) ? ruled.flags : []), `gate-malformed-verdict: ${where} stated no reason`],
        malformedVerdict: true,
        classOverride: 'malformed-verdict: the gate blocked without naming a reason',
      }
    }
  }
  return ruled
}
let ruled = ruleOn(verdict)
// ── A REASONLESS BLOCK IS ASKED AGAIN ONCE, WITH THE DEFECT NAMED ────────────────
// Not a blind retry: the second brief says what was wrong with the first answer, which is a
// changed instruction. Every caller of this gate reached it the same way, so the one re-ask
// lives here rather than in each of them. A second reasonless block, or a dead re-ask, leaves
// the malformed verdict standing for the caller to report as a judge that never ruled.
if (ruled && ruled.malformedVerdict === true) {
  const again = ruleOn(
    await askEnforcer(
      `YOUR PREVIOUS VERDICT ON THIS GATE WAS UNUSABLE: it returned ${String(verdict.verdict).toUpperCase()} but named no unmet criterion, no flag and no feedback, so nobody can act on it. Rule again. If a criterion below is unmet, mark it met=false with evidence and say in \`feedback\` exactly what must change; if none is unmet, the verdict is "pass".\n\n`,
      `${GATE_LABEL} (retry: reasonless verdict)`
    )
  )
  if (again) ruled = again
}

// THE JUDGE DIED. Not "the work failed" — see failDispatch above. The deterministic checks
// all HELD to reach this line, so what is being reported is an environment failure over work
// that passed everything mechanical, and the caller must not spend a retry re-asking a judge
// that hit the same wall.
if (!ruled) {
  const why = `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the phase-gate-enforcer returned no verdict — it was skipped, or it died. The work was NOT judged and this is not a finding against it; every deterministic check for this gate held.`
  log(why)
  return { ...failDispatch(why, 'Gate'), deterministicChecks: checkResults }
}

// The deterministic results ride out on EVERY verdict, not just the ones this file
// short-circuits on. On the judgment path they reach the enforcer only as prose in
// `settledBlock` and never appeared in the returned verdict at all — so the caller
// holding a `loop` verdict could not tell a criterion that was MEASURED against the
// artifact from one that was argued about. A mechanically-settled failure is not a
// matter of opinion and must never be waived as one.
return { ...ruled, deterministicChecks: checkResults }
