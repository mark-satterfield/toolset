export const meta = {
  name: 'prd-creation',
  description:
    'Leaf mini — turns a raw stakeholder request into a template-conformant PRD paired with its Epic. Intake captures the request, then the persona and OKRs are authored in parallel, then the PRD is drafted (WHAT-not-HOW) and independently checked for alignment with the intake brief, persona, and OKRs. A PRD and its Epic are created at the same time, so the mini emits exactly one Epic per PRD: a container bead spec derived from the PRD itself in the same authoring pass — no acceptance criteria, no repo scope (one Epic may span repos) — which the caller writes with bd. Maker, checker, and decider are distinct agents; the maker is re-run with checker feedback on reject (bounded 2 passes) and a spec-decider rules on deadlock. Authors no judgment of its own work.',
  phases: [
    { title: 'Intake', detail: 'ONE session scopes the request and captures the structured intake brief' },
    { title: 'Persona & OKR', detail: 'author the target persona and the OKRs in parallel' },
    { title: 'PRD Draft', detail: 'draft the PRD + independent alignment check (bounded loop)' },
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

// args: {
//   request: { id?, title?, description?, repoPath?, requestedBy? },  // raw stakeholder request
//   maxPasses?: number,   // bounded maker-checker passes for the PRD draft (default 2)
// }
// returns: {
//   ok, request, intakeBrief, persona, okrs, prd, alignmentVerdict, scope, decision, note,
//   epic: {                    // the Epic created together with the PRD — the caller writes it with bd
//     key:         'E1',       // stable local key; downstream parent links reference it
//     type:        'epic',     // literal — the bead face of the PRD; a container, never worked and never itself decomposed
//     title:       string,     // the PRD's title
//     description: string,     // one-paragraph scope statement derived from the PRD
//     prdRef:      string,     // the PRD's id (falls back to its title) — the pairing is the point
//   },
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const request = a.request || {}
const MAX_PASSES = a.maxPasses || 2
const repo = request.repoPath || '(repo path not provided — this is a docs/vault artifact)'
if (!request.title && !request.description) {
  return { ok: false, stage: 'input', error: 'no request.title/description supplied — refusing to run without a work item' }
}

const requestText = [
  request.id ? `Request ${request.id}` : null,
  request.title ? `Title: ${request.title}` : null,
  request.requestedBy ? `Requested by: ${request.requestedBy}` : null,
  request.description ? `Description:\n${request.description}` : null,
]
  .filter(Boolean)
  .join('\n') || '(no raw request text provided)'

// ── Intake ──────────────────────────────────────────────────────────────────
phase('Intake')

// ── ONE INTAKE SESSION, NOT TWO ─────────────────────────────────────────────────
//
// This was a `prd-creation-lead` router (`intake:scope`) followed by the intake writer.
// The router authored nothing and ruled nothing — it framed the request as scope in/out
// and open questions — and its ONLY reader was the writer below, which also received the
// raw request verbatim. So the run paid a full session-start (the dominant cost of any
// session, ahead of the work it does) to reformat text its one consumer already had.
//
// Segregation of duties is untouched: nothing here judges anything. The scope framing and
// the brief are both intake authoring, and the independent alignment check downstream
// still judges the PRD against this brief without having written any of it.
// ── THE LIST LIMITS EACH MAKER WORKS UNDER ───────────────────────────────────────
//
// Stated in each brief, counted after the result is in hand, never bound in the schema:
// one list entry over must not cost this mini the PRD, the persona or the OKRs that came
// back with it. Every number is the one this mini has always worked to, raised where it
// sat close to plausible output — a large PRD legitimately states more than 40 P0
// criteria (the measured maximum across 147 PRDs in this project is 68).
const SCOPE_LIST_MAX = 25
const CONSTRAINTS_MAX = 30
const OPEN_QUESTIONS_MAX = 25
const PERSONA_LIST_MAX = 15
const KEY_RESULTS_MAX = 8
const SECTIONS_MAX = 50
const P0_CRITERIA_MAX = 80
const ALIGNMENT_DIMENSIONS = ['intake', 'persona', 'okr', 'template']

const intake = await settleAgent(
  `Scope this stakeholder request and capture it as a structured intake brief. Both halves, one pass, each field under its own key. State the problem, the audience, and the desired outcome plainly — WHAT the job seeker needs, not HOW to build it. Do NOT write the PRD itself, the persona, or the OKRs; later makers own those.

Raw stakeholder request:
${requestText}

Working repository context: ${repo}

READING BUDGET (binding): the request above is your source. This is a framing task over a few paragraphs of stakeholder text — read at most 5 files, and only to resolve a term the request uses that you genuinely cannot interpret. Do not survey the repository or the polyrepo, and carry anything still unclear as an open question rather than investigating it.

Deliver the scope framing:
- scopeSummary: a one-paragraph framing of what this PRD must cover.
- inScope: the concerns this PRD owns (array).
- outOfScope: the concerns explicitly excluded (array).

And the intake brief:
- problem: the job-seeker problem this addresses.
- audience: who is affected (the job-seeker segment).
- desiredOutcome: the outcome the feature must produce for that audience.
- constraints: known constraints or non-negotiables (array).
- openQuestions: unresolved ambiguities to carry forward (array).

Ceilings, and nothing past them is read: ${SCOPE_LIST_MAX} entries each in \`inScope\` and \`outOfScope\`, ${CONSTRAINTS_MAX} in \`constraints\`, ${OPEN_QUESTIONS_MAX} in \`openQuestions\`. A framing that needs more than that is enumerating restatements of one concern.`,
  {
    label: 'intake:scope-and-brief',
    effort: 'medium',
    phase: 'Intake',
    agentType: 'agent-teams-workforce:stakeholder-request-intake-writer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: [
        'scopeSummary',
        'inScope',
        'outOfScope',
        'problem',
        'audience',
        'desiredOutcome',
        'constraints',
        'openQuestions',
      ],
      properties: {
        scopeSummary: { type: 'string' },
        inScope: { type: 'array', items: { type: 'string' } },
        outOfScope: { type: 'array', items: { type: 'string' } },
        problem: { type: 'string' },
        audience: { type: 'string' },
        desiredOutcome: { type: 'string' },
        constraints: { type: 'array', items: { type: 'string' } },
        openQuestions: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)
if (!intake) {
  return { ok: false, stage: 'intake', error: 'intake produced nothing — no scope framing and no brief to author a PRD from', dispatchFailed: true, dispatchFailures: dispatchDeaths('Intake') }
}
// The stated ceilings, measured. Observation only: every entry is carried forward.
checkLimit('Intake', 'inScope', intake.inScope, SCOPE_LIST_MAX)
checkLimit('Intake', 'outOfScope', intake.outOfScope, SCOPE_LIST_MAX)
checkLimit('Intake', 'constraints', intake.constraints, CONSTRAINTS_MAX)
checkLimit('Intake', 'openQuestions', intake.openQuestions, OPEN_QUESTIONS_MAX)

// Both shapes the rest of this file already reads, assembled from the one session.
const scope = {
  scopeSummary: intake.scopeSummary,
  inScope: intake.inScope,
  outOfScope: intake.outOfScope,
  openQuestions: intake.openQuestions,
}
const intakeBrief = {
  problem: intake.problem,
  audience: intake.audience,
  desiredOutcome: intake.desiredOutcome,
  constraints: intake.constraints,
  openQuestions: intake.openQuestions,
}

// ── Persona & OKR (parallel makers) ───────────────────────────────────────────
phase('Persona & OKR')

const briefBlock = `Problem: ${intakeBrief.problem}
Audience: ${intakeBrief.audience}
Desired outcome: ${intakeBrief.desiredOutcome}
Constraints: ${(intakeBrief.constraints || []).join('; ') || 'none'}`

const [persona, okrs] = await parallel([
  () =>
    settleAgent(
      `Author the target persona this PRD serves. Take the persona's population from the intake brief, and ground the persona in it.

Intake brief:
${briefBlock}

Deliver:
- name: a short persona label.
- summary: a one-paragraph portrait of this job seeker.
- goals: what they are trying to achieve (array).
- frustrations: the pain points the feature must relieve (array).
- context: their situation/environment relevant to this feature.

At most ${PERSONA_LIST_MAX} entries each in \`goals\` and \`frustrations\`; nothing past that is read. A persona with more goals than that has no persona.`,
      {
        label: 'persona:author',
        effort: 'low',
        phase: 'Persona & OKR',
        agentType: 'agent-teams-workforce:persona-profile-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['name', 'summary', 'goals', 'frustrations', 'context'],
          properties: {
            name: { type: 'string' },
            summary: { type: 'string' },
            goals: { type: 'array', items: { type: 'string' } },
            frustrations: { type: 'array', items: { type: 'string' } },
            context: { type: 'string' },
          },
        },
      }
    ),
  () =>
    settleAgent(
      `Author the objective and key results this feature must move. The objective is a qualitative, job-seeker-centered statement; each key result is a measurable signal that proves the objective was met. Ground them in the intake brief.

Intake brief:
${briefBlock}

Deliver:
- objective: the single qualitative objective this feature serves.
- keyResults: measurable results, each with a metric and a target (array) — at most ${KEY_RESULTS_MAX}, and nothing past that is read. An objective with more than a handful of key results has no objective.`,
      {
        label: 'okr:author',
        effort: 'low',
        phase: 'Persona & OKR',
        agentType: 'agent-teams-workforce:okr-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['objective', 'keyResults'],
          properties: {
            objective: { type: 'string' },
            keyResults: {
              type: 'array',
              // An objective with more than a handful of key results has no objective, but that
              // is a judgment about the OKRs, not a reason to discard the whole result.
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['metric', 'target'],
                properties: {
                  metric: { type: 'string' },
                  target: { type: 'string' },
                },
              },
            },
          },
        },
      }
    ),
])

// ── PRD Draft (maker-checker, bounded loop) ───────────────────────────────────
phase('PRD Draft')

// A dead maker is a dispatch failure, not a persona with no name. Reading `.name` off
// null threw a TypeError out of this mini, out of the composite, and killed the run —
// the same class of crash the settleAgent block above exists to prevent.
if (!persona || !okrs) {
  return {
    ok: false,
    stage: 'persona-okr',
    error: `${!persona ? 'the persona writer' : ''}${!persona && !okrs ? ' and ' : ''}${!okrs ? 'the OKR writer' : ''} returned nothing — the PRD has no persona or OKRs to be authored against`,
    intakeBrief,
    scope,
    persona: persona || null,
    okrs: okrs || null,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Persona & OKR'),
  }
}

checkLimit('Persona & OKR', 'goals', persona.goals, PERSONA_LIST_MAX)
checkLimit('Persona & OKR', 'frustrations', persona.frustrations, PERSONA_LIST_MAX)
checkLimit('Persona & OKR', 'keyResults', okrs.keyResults, KEY_RESULTS_MAX)

const personaBlock = `Persona: ${persona.name} — ${persona.summary}
Goals: ${(persona.goals || []).join('; ') || 'n/a'}
Frustrations: ${(persona.frustrations || []).join('; ') || 'n/a'}`

const okrBlock = `Objective: ${okrs.objective}
Key results: ${(okrs.keyResults || [])
  .map((k) => `${k.metric} → ${k.target}`)
  .join('; ') || 'n/a'}`

// Maker: prd-writer authors the template-conformant PRD and, in the same pass,
// the one-paragraph scope statement for the Epic that is created alongside it.
// Authoring both together keeps the pairing literal and the Epic in sync when
// the draft loops on checker feedback — no separate analysis pass is needed,
// because the PRD already contains the scope.
async function draftPRD(feedback) {
  return settleAgent(
    `Author the template-conformant Product Requirements Document (PRD) from the inputs below. Stay WHAT-not-HOW — describe the required behavior and outcomes, never the implementation. Follow the standard PRD template: required sections, P0 acceptance criteria, no leftover scaffolding.

Intake brief:
${briefBlock}
Open questions to resolve or flag: ${(intakeBrief.openQuestions || []).join('; ') || 'none'}

${personaBlock}

${okrBlock}

Deliver:
- title: the PRD title.
- prd: the full PRD body in Markdown, template-conformant.
- sections: the section headings present (array), to confirm template coverage — at most ${SECTIONS_MAX}.
- acceptanceCriteria: P0 acceptance criteria as given/when/then (array) — P0 ONLY, at most ${P0_CRITERIA_MAX}, each clause under 30 words. Nothing past ${P0_CRITERIA_MAX} is read, and every one of them is re-read by the alignment checker, by PRD validation, by the TRD author and by every spec author.
- epicScope: a one-paragraph scope statement for the Epic that pairs with this PRD — a container-level summary of the scope the PRD owns, with no acceptance criteria and no repository specifics (one Epic may span repos).${
      feedback
        ? `\n\nALIGNMENT FEEDBACK from the independent checker — address every point before resubmitting:\n${feedback}`
        : ''
    }`,
    {
      label: 'prd:draft',
      effort: 'medium',
      phase: 'PRD Draft',
      agentType: 'agent-teams-workforce:prd-writer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'prd', 'sections', 'acceptanceCriteria', 'epicScope'],
        properties: {
          title: { type: 'string' },
          prd: { type: 'string' },
          sections: { type: 'array', items: { type: 'string' } },
          epicScope: { type: 'string' },
          acceptanceCriteria: {
            type: 'array',
            // P0 only, as the brief says. Everything here is re-read by the alignment
            // checker, by PRD validation, by the TRD author and by every spec author.
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['given', 'when', 'then'],
              properties: {
                given: { type: 'string' },
                when: { type: 'string' },
                then: { type: 'string' },
              },
            },
          },
        },
      },
    }
  )
}

// Checker: an INDEPENDENT verifier — never the prd-writer.
async function verifyAlignment(prd) {
  return settleAgent(
    `You are an INDEPENDENT alignment verifier. You did NOT write this PRD — you only judge it. Do NOT rewrite the PRD. Verify the drafted PRD aligns with the intake brief, the persona, and the OKRs, and that it is template-conformant and WHAT-not-HOW.

Intake brief:
${briefBlock}

${personaBlock}

${okrBlock}

PRD under review (title: ${prd.title}):
${prd.prd}

Decide exactly one verdict:
- "aligned": the PRD covers the intake problem/outcome, serves the named persona, and its acceptance criteria trace to the OKRs.
- "misaligned": one or more of those hold false. Return feedback specific enough that the prd-writer can fix it without interpretation.

For each dimension (intake, persona, okr, template), state whether it is satisfied with evidence — exactly ${ALIGNMENT_DIMENSIONS.length} entries in \`dimensions\`, one per dimension and no others.`,
    {
      label: 'prd:alignment-check',
      // A checker, and the prd-alignment-verifier's own file already says `effort: low`
      // — this override was RAISING it. It judges a document against three stated inputs;
      // the expensive judgment in this mini is the deadlock ruling below.
      effort: 'low',
      phase: 'PRD Draft',
      agentType: 'agent-teams-workforce:prd-alignment-verifier',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'dimensions', 'feedback'],
        properties: {
          verdict: { type: 'string', enum: ['aligned', 'misaligned'] },
          dimensions: {
            type: 'array',
            // Exactly the four dimensions the enum names, one entry each — stated in the
            // brief and counted after the ruling, never bound here.
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['dimension', 'satisfied', 'evidence'],
              properties: {
                dimension: { type: 'string', enum: ['intake', 'persona', 'okr', 'template'] },
                satisfied: { type: 'boolean' },
                evidence: { type: 'string' },
              },
            },
          },
          feedback: { type: 'string' },
        },
      },
    }
  )
}

let prd = null
let alignmentVerdict = null
let feedback = ''
let deadlocked = false
for (let pass = 1; pass <= MAX_PASSES; pass++) {
  prd = await draftPRD(feedback)
  // Same guard, same reason: verifyAlignment reads `prd.title` and `prd.prd`.
  if (!prd) {
    return { ok: false, stage: 'prd-draft', reason: 'the prd-writer returned nothing — there is no PRD to check', intakeBrief, persona, okrs, scope, dispatchFailed: true, dispatchFailures: dispatchDeaths('PRD Draft') }
  }
  checkLimit(`PRD Draft (pass ${pass})`, 'sections', prd.sections, SECTIONS_MAX)
  checkLimit(`PRD Draft (pass ${pass})`, 'P0 acceptance criteria', prd.acceptanceCriteria, P0_CRITERIA_MAX)
  alignmentVerdict = await verifyAlignment(prd)
  if (!alignmentVerdict) {
    return { ok: false, stage: 'prd-draft', reason: 'alignment check returned no verdict', intakeBrief, persona, okrs, scope, prd, dispatchFailed: true, dispatchFailures: dispatchDeaths('PRD Draft') }
  }
  checkLimit(`PRD Draft (pass ${pass})`, 'alignment dimensions', alignmentVerdict.dimensions, ALIGNMENT_DIMENSIONS.length)
  // The verdict is read off the checker's own dimensions: "aligned" beside a dimension it
  // marked unsatisfied is not alignment, and the unsatisfied evidence is the rework brief.
  const unsatisfied = (Array.isArray(alignmentVerdict.dimensions) ? alignmentVerdict.dimensions : []).filter((d) => d && d.satisfied === false)
  if (alignmentVerdict.verdict === 'aligned' && unsatisfied.length) {
    log(`PRD draft: the checker said aligned but marked ${unsatisfied.map((d) => d.dimension).join(', ')} unsatisfied — read as misaligned`)
    alignmentVerdict = { ...alignmentVerdict, verdict: 'misaligned' }
  }
  if (alignmentVerdict.verdict === 'aligned') {
    log(`PRD draft: ALIGNED on pass ${pass}/${MAX_PASSES}`)
    break
  }
  // A misaligned verdict with empty feedback would re-run the maker on identical input.
  feedback = String(alignmentVerdict.feedback || '').trim() || unsatisfied.map((d) => `${d.dimension}: ${d.evidence}`).join('\n')
  log(`PRD draft: MISALIGNED pass ${pass}/${MAX_PASSES} — ${feedback || '(no feedback given)'}`)
  if (pass === MAX_PASSES) deadlocked = true
}

// Deadlock: the maker and checker could not converge — the spec-decider rules.
let decision = null
if (deadlocked) {
  log('PRD draft: maker-checker deadlock — escalating to spec-decider for a binding ruling')
  decision = await settleAgent(
    `The prd-writer and the independent prd-alignment-verifier could not converge after ${MAX_PASSES} passes. Rule on the standoff. Your ruling is binding.

Latest checker feedback: ${feedback || '(none)'}

The checker judged the PRD against these inputs; judge its objection against the same ones.

Intake brief:
${briefBlock}

${personaBlock}

${okrBlock}

PRD under review (title: ${prd.title}):
${prd.prd}

Decide exactly one verdict:
- "accept": the PRD is acceptable as-is despite the checker's objection — explain why the objection does not block.
- "reject": the PRD must not proceed — state the blocking gap its author must close.`,
    {
      label: 'prd:deadlock-ruling',
      effort: 'high',
      phase: 'PRD Draft',
      agentType: 'agent-teams-workforce:spec-decider',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'rationale'],
        properties: {
          verdict: { type: 'string', enum: ['accept', 'reject'] },
          rationale: { type: 'string' },
        },
      },
    }
  )
}

const aligned = alignmentVerdict && alignmentVerdict.verdict === 'aligned'
const ruledAccept = decision && decision.verdict === 'accept'
const ok = Boolean(aligned || ruledAccept)
// A deadlock ruling that never came back is a dispatch failure, not a rejection.
const deciderDied = deadlocked && !decision

// A PRD and its Epic are created at the same time — the Epic is the bead-side
// half of that pairing, assembled here from the maker's own output rather than
// a fresh analysis pass. It is a CONTAINER: no acceptance criteria and no repo
// scope, because one Epic may span repos and its Stories (one per repo) are
// minted later, each alongside its Spec. Exactly one epic is emitted per PRD;
// this mini never writes to .beads — the caller writes the bead with bd.
const epic = prd
  ? {
      key: 'E1',
      type: 'epic',
      title: prd.title,
      description: prd.epicScope,
      // Inside this mini the PRD has no bead id or file path yet, so the ref is
      // the originating request id when supplied, else the PRD's own title.
      prdRef: request.id || prd.title,
    }
  : null

return {
  ok,
  ...(ok ? {} : { stage: 'prd-draft' }),
  ...(deciderDied ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('PRD Draft') } : {}),
  request: request.id ? request.id : null,
  intakeBrief,
  persona,
  okrs,
  prd,
  epic,
  alignmentVerdict,
  scope,
  decision,
  ...(limitFindings.length ? { limitFindings } : {}),
  note: ok
    ? 'PRD is intake/persona/OKR-aligned and template-conformant.'
    : 'PRD did not reach alignment within the bounded passes; see decision for the binding ruling.',
}
