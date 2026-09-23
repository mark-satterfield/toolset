export const meta = {
  name: 'bug-triage',
  description:
    'Bug front-end. Turns a symptom (a bug bead) into an implementation-ready contract: reproduction, root cause, blast radius, and the expected-behavior acceptance criteria the shared tail builds against. Also SIZES the bug: a defect whose honest fix is a redesign is escalated as needing a PRD and Epic rather than being squeezed through the fix path, because a bug ticket is not a licence to rebuild a subsystem unreviewed. Read-only — produces no code changes.',
  phases: [{ title: 'Triage', detail: 'root-cause analysis + scope sizing + expected-behavior contract' }],
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

// args: { bead: { id, title, description, repoPath?, repoHints?, manifestPath? } }
//
// `repoPath` is the repository when the caller knows it. It is NOT required: a Bug is
// filed against a SYMPTOM, and which repository the defect lives in is a finding of the
// diagnosis — the blast radius names the code at fault, and the code at fault is in a
// repository. So when no repoPath is supplied the diagnosing agent is told to LOCATE it,
// from the symptom, the polyrepo manifest (`manifestPath`) and any names the caller merely
// suspects (`repoHints`), and to report it CONFIRMED — an absolute path that exists and is
// a git repository — or to report that it could not. A guessed repository is not an
// answer: bug-fix validates what comes back and refuses what it cannot use.
const __a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = __a.bead || {}
const repoKnown = !!String(bead.repoPath || '').trim()
const repo = repoKnown ? bead.repoPath : '(NOT KNOWN — locating it is part of this diagnosis; see below)'

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof __a.standingRulings === 'string' ? __a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''
const repoHints = (Array.isArray(bead.repoHints) ? bead.repoHints : []).map((h) => String(h == null ? '' : h).trim()).filter(Boolean)
const manifestPath = String(bead.manifestPath || '').trim()
const LOCATE_REPO =
  repoKnown
    ? ''
    : `

THE REPOSITORY IS NOT KNOWN, AND FINDING IT IS PART OF THIS DIAGNOSIS. Locate the repository whose source contains the code at fault. Start from the symptom and the blast radius; consult the polyrepo manifest${manifestPath ? ` at ${manifestPath}` : ''} for the repositories this project has and where each is checked out on this machine${repoHints.length ? `; the caller suspects it may be one of: ${repoHints.join(', ')} — a suspicion, not an answer` : ''}. Report repoPath as the ABSOLUTE path of that repository — the repository itself, not a worktree beneath it and not a subdirectory — and only after you have CONFIRMED the directory exists and is a git repository. If you cannot confirm one, report repoPath as an empty string and say in repoResolution which repositories you examined and why none was confirmed. A guessed repository sends a pipeline that writes code, commits and opens a pull request into a tree nobody chose; an honest empty answer does not.`

phase('Triage')

// What a bug is EXPECTED to contain, used to flag a count worth a look and stated to
// nobody. How many distinct defects sit behind one symptom is a fact about the code, not
// a volume the analyst chooses, so capping it would only buy a shorter list than the
// truth. A bug that really does carry twenty has an answer already — the `needs-prd`
// sizing step below rules it a redesign — and that ruling needs the full enumeration to
// be made on. The MINIMUM is stated, because "at least one" demands completeness rather
// than brevity: a diagnosis with no enumerated defect leaves the contract with nothing
// to cover.
const DEFECTS_EXPECTED = 20

// 1) Diagnosis — read-only analyst. Separation of duties: this agent does not fix.
const analysis = await settleAgent(
  `${rulingsBlock}Diagnose this bug. You are READ-ONLY — do not change code. Work within the repository at: ${repo}

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Deliver:
- reproduction: the minimal, concrete steps/conditions that trigger the defect.
- rootCause: the precise mechanism and code location (file:line where possible), as prose.
- defects: the SAME root cause, ENUMERATED — one entry per distinct defect, each with a short stable id (D1, D2, ...), its mechanism, and the file and line where it lives. One bead frequently contains several distinct defects, and returning them only as one paragraph of prose leaves everything downstream with nothing countable: the acceptance criteria are then written against a blob and cannot be bounded, indexed, or checked for coverage. Return exactly one entry per defect you would fix separately — not one per file, not one per symptom. AT LEAST ONE entry, always: a bug with no enumerated defect leaves the contract below with nothing to cover. There is no ceiling on the count — a bug that honestly contains fifteen distinct defects has fifteen, and the answer to that is the \`needs-prd\` sizing below, never a shorter list.
- affectedFiles: the files that must change to fix it (paths).
- blastRadius: the callers, flows, and services impacted if the bug ships or the fix regresses.
- surfaces: which surfaces from the CLOSED SET below the fix actually touches. This decides which specialist test writers run downstream, so it is a real decision, not a label:
    api-contract           a published REST/GraphQL/event schema that consumers depend on
    event-chain            the event API -> EventBridge -> SQS -> Lambda delivery path
    auth                   authentication, authorization, or permission evaluation
    performance            a stated performance budget or latency/throughput requirement
    web-ui                 web user interface
    ios                    native iOS
    android                native Android
    cross-platform-mobile  React Native or other cross-platform mobile
    ml                     matching, recommendation, ranking, or embeddings
    data-pipeline          ETL, CDC, or stream processing
  Return ONLY surfaces the CHANGE touches — not surfaces the surrounding code happens to sit near. Return an empty list when the fix is confined to internal logic, which is the common case. Each surface you name costs a full additional test-authoring agent; each one you omit leaves that surface with no specialist coverage.
- repoPath: the ABSOLUTE path of the repository the defect lives in${repoKnown ? ' — echo the repository you were given' : ''}.
- repoResolution: how you confirmed the repository${repoKnown ? ' (one line; it was supplied)' : ', or why none could be confirmed'}.${LOCATE_REPO}`,
  {
    label: 'triage:diagnosis',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:root-cause-analyst',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['reproduction', 'rootCause', 'defects', 'affectedFiles', 'blastRadius', 'surfaces'],
      properties: {
        reproduction: { type: 'string' },
        rootCause: { type: 'string' },
        // At least one — stated in the brief above, and counted once the result is in
        // hand. Never bound here: a bound on this list answers a one-over enumeration by
        // destroying the reproduction, the root cause and the repository resolution along
        // with it, and triage then has nothing at all.
        defects: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'mechanism'],
            properties: {
              id: { type: 'string' },
              mechanism: { type: 'string' },
              file: { type: 'string' },
              line: { type: 'integer' },
            },
          },
        },
        affectedFiles: { type: 'array', items: { type: 'string' } },
        blastRadius: { type: 'string' },
        repoPath: { type: 'string' },
        repoResolution: { type: 'string' },
        surfaces: {
          type: 'array',
          items: {
            type: 'string',
            enum: [
              'api-contract',
              'event-chain',
              'auth',
              'performance',
              'web-ui',
              'ios',
              'android',
              'cross-platform-mobile',
              'ml',
              'data-pipeline',
            ],
          },
        },
      },
    },
  }
)

// A dead dispatch is not a diagnosis, a sizing or a contract. Each death returns the
// `dispatchFailed` shape every other mini returns, so the caller reports it under the
// environment stage and never checkpoints it as a contract.
const triageDied = (what) => {
  const deaths = dispatchDeaths('Triage')
  const reason = `the triage ${what} returned nothing — ${deaths.map((f) => f.note).join('; ') || 'no dispatch was recorded'}`
  log(`Triage: ${reason}`)
  return { ok: false, dispatchFailed: true, dispatchFailures: deaths, reason }
}
if (!analysis) return triageDied('diagnosis')

// 1b) SIZING — is this a fix, or a redesign wearing a bug ticket?
//
// The repository the fix is built in. A supplied one is the answer; otherwise it is what
// the diagnosis LOCATED, reported as a finding beside the blast radius. Never a guess made
// here: an empty string is carried as null and the caller refuses to write without one.
// Measured here so the count is observed on the needs-prd path too. An observation only:
// every defect is carried forward, and the `at least one` is the only thing asked for.
checkLimit('Triage', 'defects', Array.isArray(analysis.defects) ? analysis.defects : [], DEFECTS_EXPECTED, 1)
const resolvedRepoPath = repoKnown ? bead.repoPath : String((analysis && analysis.repoPath) || '').trim() || null
if (!repoKnown) log(`Triage: repository ${resolvedRepoPath ? `located at ${resolvedRepoPath}` : 'NOT located'} — ${(analysis && analysis.repoResolution) || 'no resolution reported'}`)

// A bug can be worked directly, or it can turn out to need a PRD and an Epic. The
// difference matters: the fix path has no PRD validation, no architecture ruling,
// and no spec — so a defect whose honest remedy is "redesign how this service
// stores its data" would get that redesign built by an implementer, unreviewed,
// on the authority of a bug ticket. That is how an architecture decision gets made
// by accident, which is the failure this workforce exists to prevent.
//
// A DIFFERENT agent sizes it — the diagnostician has just invested in a root cause
// and is the worst-placed judge of whether fixing it is too big.
const sizing = await settleAgent(
  `${rulingsBlock}Size this bug. It has been diagnosed; decide whether its honest remedy is a FIX or a REDESIGN. You are READ-ONLY and you are NOT proposing the remedy — only sizing it.

Answer "needs-prd" when the honest fix would: change a public contract or event schema, alter the data model, cross a service boundary, require an architecture decision the SAD does not cover, or amount to rebuilding a component rather than correcting it.

Answer "fix" when the defect is a mistake in existing behavior that can be corrected within the current design — the common case. Do not inflate a real bug into a project; most bugs are bugs.

The cost of each error is not symmetric. Calling a redesign a "fix" ships an unreviewed architecture change on a bug ticket. Calling a fix a "redesign" costs a PRD nobody needed. Prefer "fix" when genuinely balanced, and "needs-prd" when the remedy touches a contract, a schema, or a boundary.

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Root cause found: ${analysis.rootCause}
Files that must change: ${(analysis.affectedFiles || []).join(', ') || 'n/a'}
Blast radius: ${analysis.blastRadius}`,
  {
    label: 'triage:sizing',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:architecture-boundary-guardian',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['scope', 'rationale'],
      properties: {
        scope: { type: 'string', enum: ['fix', 'needs-prd'] },
        rationale: { type: 'string' },
        contractsTouched: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// A missing verdict must not silently become "fix" — that is the expensive error — and it
// is not a "needs-prd" ruling either, so a dead sizing stops the run as a dispatch death.
if (!sizing) return triageDied('sizing')
const scope = sizing.scope || 'needs-prd'
const scopeRationale = sizing.rationale || 'sizing returned no rationale'
if (scope === 'needs-prd') {
  log(`Bug ${bead.id || ''} sized as NEEDS-PRD: ${scopeRationale}`)
  return {
    bead,
    repoPath: resolvedRepoPath,
    repoResolution: (analysis && analysis.repoResolution) || null,
    scope,
    scopeRationale,
    contractsTouched: sizing.contractsTouched || [],
    reproduction: analysis.reproduction,
    rootCause: analysis.rootCause,
    defects: (Array.isArray(analysis.defects) ? analysis.defects : []).filter((d) => d && d.id),
    affectedFiles: analysis.affectedFiles,
    blastRadius: analysis.blastRadius,
    acceptanceCriteria: [],
    ...(limitFindings.length ? { limitFindings } : {}),
    note:
      'This defect needs a PRD and an Epic, not a fix. Its honest remedy changes a contract, ' +
      'schema, or boundary, and the fix path has no PRD validation, no architecture ruling, and ' +
      'no spec to review it against. Promote it: /agent-teams-workforce:start-prd, or dispatch ' +
      'prd-to-spec with { request } built from the diagnosis above. Promotion is a human decision.',
  }
}

// 2) Expected-behavior contract — the "spec-lite" a bug lacks, as testable AC.
//    A different agent than the diagnostician (no self-authoring of its own contract).
//
// SCOPED BY CONSTRUCTION. This step used to receive a prose root cause with no expected
// range, no defect index, and no scope rule — and a four-defect bug produced eighteen-plus
// criteria, several of them repo-wide greps. The downstream coverage reviewer then
// blocked on partial coverage of criteria Red could never legitimately turn red, and the
// Red gate exhausted without one line of production code being written.
//
// The defect index is what fixed that: coverage becomes an exact join — every defectId
// resolves, every defect has at least one criterion — instead of a judgment call, and it
// is computed below from the result. The range is stated to the writer and OBSERVED
// afterwards; it is never a schema bound, because a bound does not trim an over-long
// list, it destroys the whole contract and halts the bug fix at triage.
const defects = (Array.isArray(analysis.defects) ? analysis.defects : []).filter((d) => d && d.id)
const defectIds = defects.map((d) => String(d.id))
const AC_MIN = Math.max(1, defectIds.length)
const AC_MAX = Math.max(2, defectIds.length * 2)
log(`Triage: ${defectIds.length || 'unenumerated'} defect(s) — acceptance criteria expected in the range ${AC_MIN}..${AC_MAX}`)

const contract = await settleAgent(
  `${rulingsBlock}Write the expected-behavior contract for this bug fix as testable given/when/then acceptance criteria — the correct behavior the fix must satisfy and that a failing test will encode. Do NOT write code.

ONE OR TWO CRITERIA PER DEFECT, and every criterion carries the id of the defect it covers. Every defect below must have at least one. Between ${AC_MIN} and ${AC_MAX} criteria in total — if you are heading past ${AC_MAX} you are enumerating variants of one behaviour, and every criterion you write is one Red must encode.

A CRITERION DESCRIBES AN EXECUTION, NOT THE REPOSITORY. Apply this test to everything you are about to write: **if it would still be checkable with the change reverted, it is not an acceptance criterion.** "No occurrence of \`redis://\` anywhere in the repo" passes that test trivially — it is checkable before, during and after the fix, against code nobody touched — which is exactly what makes it a LINT RULE wearing an acceptance-criterion costume. Return those in \`lintRules\` instead. They are real and they are worth enforcing; they are just not something a failing test can encode, and putting them here blocks the build on a grep no Red phase can legitimately make fail.

Bug ${bead.id || ''}: ${bead.title || ''}
Reproduction: ${analysis.reproduction}
Root cause: ${analysis.rootCause}
Files the fix must change: ${(analysis.affectedFiles || []).join(', ') || 'n/a'}

Defects to cover (use these ids exactly):
${defects.length ? defects.map((d) => `- ${d.id}: ${d.mechanism}${d.file ? ` [${d.file}${d.line ? `:${d.line}` : ''}]` : ''}`).join('\n') : '(the diagnosis enumerated none — derive minimal coverage from the root cause above and use the id D1)'}`,
  {
    label: 'triage:expected-behavior',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:acceptance-criteria-writer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['acceptanceCriteria'],
      properties: {
        acceptanceCriteria: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['defectId', 'given', 'when', 'then'],
            properties: {
              defectId: defectIds.length ? { type: 'string', enum: defectIds } : { type: 'string' },
              given: { type: 'string' },
              when: { type: 'string' },
              then: { type: 'string' },
            },
          },
        },
        // Sibling output, deliberately NOT passed to tdd-red. A repo-wide invariant is a
        // lint rule or a pre-commit hook, landed by the path that already commits — the
        // coverage reviewer never sees it and therefore structurally cannot block the
        // Red gate on a criterion Red can never turn red.
        lintRules: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['pattern', 'rationale'],
            properties: {
              pattern: { type: 'string' },
              rationale: { type: 'string' },
              scope: { type: 'string' },
            },
          },
        },
      },
    },
  }
)

// A contract with no criteria gives Red nothing to encode, so a dead writer stops here.
if (!contract) return triageDied('expected-behavior writer')

// Coverage is an exact join, not a judgment: every enumerated defect must have at least
// one criterion pointing at it.
const authoredAc = (contract && Array.isArray(contract.acceptanceCriteria) ? contract.acceptanceCriteria : []).filter(Boolean)
const covered = new Set(authoredAc.map((x) => String(x.defectId || '')))
const uncoveredDefects = defectIds.filter((id) => !covered.has(id))
if (uncoveredDefects.length) log(`⚠ Triage: defect(s) with no acceptance criterion: ${uncoveredDefects.join(', ')}`)
// The range is an expectation, not a gate: every criterion is carried through either way.
checkLimit('Triage', `acceptance criteria for ${defectIds.length || 'unenumerated'} defect(s)`, authoredAc, AC_MAX, AC_MIN)
const lintRules = (contract && Array.isArray(contract.lintRules) ? contract.lintRules : []).filter(Boolean)
if (lintRules.length) log(`Triage: ${lintRules.length} repo-wide invariant(s) routed to lint, not to the Red phase`)

return {
  bead,
  repoPath: resolvedRepoPath,
  repoResolution: (analysis && analysis.repoResolution) || null,
  scope,
  scopeRationale,
  reproduction: analysis.reproduction,
  rootCause: analysis.rootCause,
  defects,
  affectedFiles: analysis.affectedFiles,
  blastRadius: analysis.blastRadius,
  // Consumed by tdd-red to DERIVE its test writers. Empty means unit tests only,
  // which is the correct answer for a fix confined to internal logic.
  surfaces: analysis.surfaces || [],
  acceptanceCriteria: authoredAc,
  uncoveredDefects,
  ...(limitFindings.length ? { limitFindings } : {}),
  // Repo-wide invariants the writer routed out of the acceptance criteria. Recorded in the
  // run journal; no phase reads them, and they are never handed to the Red phase.
  lintRules,
}
