export const meta = {
  name: 'prd-reconciliation',
  description:
    'Leaf mini — PRD Reconciliation. ONE independent read-only checker session takes an INVENTORY of the material that already exists for a PRD, and detects upstream dependency changes, in a single pass. THE PRD IS CANONICAL: what already ships is material, not authority — where it conforms to the PRD it is reused, where it contradicts the PRD it is removed, and where nothing exists it is built. No requirement is ever filtered out, narrowed, deferred, or written off because code exists, and the inventory is context for the phases downstream, never a filter on their scope. EVERY requirement the PRD states comes back with a status; a conforms/contradicts claim with no file:line, URL, endpoint or arn:aws behind it is demoted to absent, because reusing material that may not match the PRD is the expensive error. UI requirements are resolved against the cds design system, which is the authority for layout, shells, navigation, components and interaction: the hand-off bundle first (a packaged artifact carries a build-spec the app repo builds to), then the loose composed mock, then the PRD prose, and what is deployed is never authoritative — a deployed UI that differs from the packaged artifact is material to bring into line, never an open question. THE SEARCH BUDGET IS MEASURED FROM THE PRD, not fixed: the ceiling is this PRD\'s own requirement count at the stated per-requirement rate plus overhead, so every requirement can actually be looked at. A requirement the run did NOT examine comes back NAMED in `coverage.unexaminedRequirementIds` and in `unexaminedRequirements` — never reported as `absent`, because "I did not look" and "it is not there" are different claims and only one of them is a finding. Read-only: it writes no document at all and returns structured output only.',
  phases: [
    { title: 'Reconciliation checks', detail: 'one independent read-only checker session inventories the material and checks upstream dependencies' },
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
//   prd: {                      // the PRD being reconciled against reality (required)
//     id?: string,
//     title?: string,
//     body: string,             // the PRD text — required; a path alone cannot be read by a script
//     path?: string,            // where the PRD document lives; an absolute path is sent in place of the body
//     repoPath?: string,        // the repo the PRD nominally targets
//   },
//   repos?: string[],           // every repo the PRD may span
//   mocksDir?: string,          // cds design mocks directory; derived from repoPath when absent
//   packagesDir?: string,       // cds hand-off bundle root (holds batch-* dirs); derived likewise
//   dependencies?: string[],    // upstream contracts/schemas/libs the PRD assumes
//   awsProfile?: string,        // AWS profile for live-endpoint checks (default 'dev')
// }
//
// WHY THIS MINI EXISTS
//
// Nothing else in the specification pipeline establishes what already exists, so without
// this the pipeline walks into a codebase blind: it re-specifies capabilities that already
// ship, and it leaves in place code that the PRD has since moved past. An audit of 20 Epics
// in one project found ELEVEN written as greenfield against behaviour that was already
// there — a 929-line MFA implementation that was merely disabled, a fully deployed passkey
// ceremony, three live OAuth providers, a shipped session dashboard.
//
// WHERE IT RUNS, AND WHY THAT CHANGED. This used to run at the FRONT of prd-to-spec, ahead
// of every gate, feeding PRD validation, the architecture panel and the TRD. That made what
// is deployed in a dev account into a form of requirement. The three layers are blind to
// different things on purpose: a PRD is WHAT and never knows what is deployed; a TRD is HOW,
// derived from the PRD and the SAD on pure architecture and best practice, and blind to
// deployed state too, because a design reverse-engineered from the existing implementation
// inherits that implementation's mistakes and calls them requirements; and the SPEC is the
// only layer that asks "X is what we want, Y is what we have, how do we turn Y into X" —
// because it is the only layer scoped to ONE repository, which is the only scope at which
// that question has a concrete answer.
//
// So prd-to-spec now dispatches this mini INSIDE its per-repo spec-authoring fan-out, once
// per repository in the ruled span, with `repos` holding exactly that one repository. The
// PRD it is handed is always WHOLE: the search narrows to one repository, the requirements
// never narrow at all.
//
// CHECK 1c IS RETIRED, NOT MERELY UNREAD. It computed `architectureNeeded`, `infraOnly`
// and `architectureQuestions`, and after the relocation nothing consumed any of them:
// whether an architecture panel convenes is a read-only triage over the PRD itself,
// upstream of here, because whether something is already built has no bearing on whether
// the PRD leaves a CHOICE open. Left in place it was a whole judgment pass over the whole
// PRD — with its own attribution rules and its own script-side UI guard — paid ONCE PER
// REPOSITORY in the span, for output that was thrown away. It is gone from the brief, the
// schema, the reduction and the return.
//
// If a caller ever needs the architecture question again, it belongs where it is now: over
// the PRD, once, not over the material, once per repo.
//
// It exists to spend the existing material well, not to shrink the ask:
//
//   - material that CONFORMS to the PRD is REUSED — the spec builds on it instead of
//     re-deriving it, and decomposition emits no task to write it again;
//   - material that CONTRADICTS the PRD is REMOVED — the PRD is the latest statement of
//     what the product is, so the deployed thing is what is wrong, and removing it is
//     real work that has to reach decomposition like any other;
//   - where nothing exists, it is built.
//
// The PRD is canonical and delivered code never subtracts from it. A requirement is
// never dropped, narrowed or deferred because something was already built, and no work
// item is closed on the grounds that code exists. When the PRD and the deployed system
// disagree, that is SETTLED BY DEFINITION in the PRD's favour: it convenes no panel, it
// raises no architecture question, and it generates removal work.
//
// The same holds one level down for the interface. A UI/UX difference is never an
// architecture decision — layout, shells, navigation shape, components, visual design
// and interaction patterns are settled by the design system, and the cds output is the
// authority for that above any other documentation. It comes in two grades: the
// `package-change` HAND-OFF BUNDLE under `design-mocks/packages/batch-*/`, where each
// artifact carries the `build-spec.md` the app repo builds to, and the loose composed
// mocks under `design-mocks/{shells,pages,views}/` for artifacts not yet packaged. So a
// deployed screen that differs from its packaged artifact is material to bring into line
// rather than a competing option to adjudicate — and an artifact missing from the bundle
// is unpackaged, not undecided, which falls back to the mock and blocks nothing.
//
// One bundle has existed since 2026-08-19 and the pipeline had never looked at it: 205
// artifacts, 23 of them the settings screens an Epic once spent 45 minutes convening an
// architecture panel to choose a shell for.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const prdInput = a.prd || {}
const prdBody = typeof prdInput === 'string' ? prdInput : prdInput.body || ''
const prdId = (typeof prdInput === 'string' ? '' : prdInput.id) || ''
const prdTitle = (typeof prdInput === 'string' ? '' : prdInput.title) || ''
const repoPath = (typeof prdInput === 'string' ? '' : prdInput.repoPath) || a.repoPath || ''
const repos = (Array.isArray(a.repos) && a.repos.length ? a.repos : [repoPath]).filter((r) => r)
const dependencies = Array.isArray(a.dependencies) ? a.dependencies : []
const awsProfile = a.awsProfile || 'dev'
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
// The design system's output is the UI authority, so the reconciler is told where to
// find it rather than left to guess. Two locations, and the ORDER between them matters:
// the cds `package-change` skill produces a HAND-OFF BUNDLE — the boundary between
// "approved in cds" and "built in the app repo" — and a bundled artifact carries a
// build-spec the loose mock does not. So the bundle outranks the mocks, and the mocks
// outrank the PRD's prose about layout. A caller may name either directory outright;
// otherwise both sit under the repo the run operates on, and the reconciler resolves the
// environment overrides (CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR, then
// CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR / _SHELLS_DIR) when they are set.
//
// The bundle ROOT holds dated `batch-*` directories; picking the most recent one is a
// directory listing, which a workflow script cannot do — so the root is threaded here and
// the reconciler selects the batch.
const repoRoot = hasText(repoPath) ? repoPath.replace(/\/+$/, '') : ''
const mocksDir = hasText(a.mocksDir) ? a.mocksDir.trim() : repoRoot ? `${repoRoot}/design-mocks` : ''
const packagesDir = hasText(a.packagesDir) ? a.packagesDir.trim() : mocksDir ? `${mocksDir}/packages` : ''

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''

// ── A DEAD DISPATCH ARRIVES AS A THROW, NOT AS A NULL ───────────────────────────
//
// This mini was written against one runtime behaviour and meets two. `agent()` hands
// back NULL when a subagent is skipped or dies on a terminal API error, and the
// `!reality` guard below was built for exactly that. But a subagent that RUNS and then
// finishes WITHOUT emitting its structured output THROWS, and the throw leaves the mini,
// leaves the composite, and aborts the whole run. Uncaught, every line below, including the
// entire `dispatchFailed` contract this mini owes its caller, is unreachable for the
// failure mode that actually happens, and the caller is handed a bare abort with no
// classification.
//
// settleAgent() above is where that now happens, for every dispatch in this file: a
// throw and a null arrive at the guards below as the same event — "no account came
// back" — so the caller learns it was the ENVIRONMENT that failed and not the PRD.
//
// THE SECOND ATTEMPT IS GONE. It re-ran the identical prompt with identical options and
// nothing else changed, which is the one retry in this whole tree that carried no new
// input. That is sound for a TRANSIENT death and useless for the deterministic one: a
// session that exhausted its context runs the same prompt into the same wall, and this
// code cannot tell the two apart — the thrown Error is the only evidence it gets, with
// no token count, no stop reason and no partial output. So the dispatch is made once,
// and a death is reported as a death for the caller to act on.

// `extra` carries `dispatchFailed` when the failure is a dead agent rather than a
// finding — see the reconciler check below. The caller reads that field to decide
// whether it holds a verdict about the PRD or an account that never came back.
const fail = (reason, extra) => ({
  ok: false,
  reason,
  requirements: [],
  conformsCount: 0,
  contradictsCount: 0,
  absentCount: 0,
  removalWork: [],
  reuseWork: [],
  // Nothing was examined, and the shape stays uniform so a caller reads coverage the same
  // way on every path. `complete: false` is the honest reading of a run that never ran.
  coverage: { requirementCount: 0, examinedCount: 0, unexaminedRequirementIds: [], budgetExhausted: false, complete: false },
  unexaminedRequirements: [],
  uiAuthority: {
    bundlePath: null,
    mocksDir: mocksDir || null,
    artifactsConsulted: [],
    shellsConsulted: [],
    pagesConsulted: [],
  },
  ...(extra || {}),
})

if (!hasText(prdBody)) {
  // Refuse rather than report an empty inventory. "Nothing was found" and "no PRD was
  // supplied" both reduce to zero requirements, and a caller reading the first as an
  // answer proceeds against a document nobody looked at.
  return fail('prd-reconciliation invoked with an empty PRD body — there is nothing to reconcile against reality.')
}

const prdHeader = `PRD ${prdId}${prdTitle ? `: ${prdTitle}` : ''}`.trim()
// The PRD goes to the reconciler as its path when it has one on disk: the reconciler reads
// it itself, and the dispatch does not carry the whole document once per repository. The
// body is still required here, because the search budget below is measured from it.
const prdPath = typeof prdInput === 'string' ? '' : prdInput.path
const prdOnDisk = hasText(prdPath) && /^\/[A-Za-z0-9._/ -]+$/.test(prdPath) && !prdPath.split('/').includes('..')
const prdBlock = prdOnDisk
  ? `${prdHeader}\n\nThe PRD is the document at ${prdPath}. Read it in full before you start: every requirement it states is in scope.`
  : `${prdHeader}\n\n${prdBody}`
const repoBlock = repos.length
  ? repos.map((r, i) => `${i + 1}. ${r}`).join('\n')
  : '(no repo paths supplied — discover the repositories this PRD touches from the PRD text)'

// ── THE SEARCH IS SCOPED TO WHAT THE CALLER NAMED; THE REQUIREMENTS NEVER ARE ────
//
// This brief was written when the mini ran ONCE, at the front of the pipeline, against
// every repository the PRD might touch. It now runs once per repository in the ruled span,
// with `repos` holding exactly one — so a brief that still says "the estate" and budgets
// for it will crawl the estate once per repository, and the waste is multiplied by the
// span rather than paid once.
//
// What narrows is the SEARCH. The PRD does not: `prdBlock` is the whole PRD in every case,
// every requirement still comes back with a status, and an unevidenced conforms/contradicts
// is still demoted to absent by the reduction below. A requirement whose material is not in
// this repository is `absent` HERE — which is the honest answer for this repository — and it
// is never dropped from the inventory.
//
// One repository is a smaller haystack than sixty, so the per-requirement rate scales with
// the scope actually given. An empty or multi-repo `repos` means the scope is NOT known to
// be one repository, and that keeps the original wide rate: unknown is unknown, and the
// fail-safe stays "search widely", never "search less".
//
// ── THE CEILING IS DERIVED FROM THE PRD, NOT GUESSED ────────────────────────────
//
// The ceiling used to be a constant — 30 single-repo, 50 otherwise — while the rate beside
// it was stated per requirement. Those two numbers contradicted each other for any PRD with
// more than about seven requirements, and the prompt says exactly what the contradiction
// costs: "a requirement you never looked at comes back as `absent` and gets built from
// scratch beside material that already exists". Measured over the 147 PRDs in this project:
// 1291 stated requirements, mean 8.8, median 8, max 18 — so the constant was binding on
// essentially every real PRD, and the failure it produced was silent.
//
// So the ceiling is now MEASURED from the PRD this run was handed. The count is estimated
// from the document's own structure — the heading level the requirements are written at,
// and the requirement-id labels (REQ-…, EA-001, BG-003) the templates use — and the ceiling
// is that count at the stated rate plus a fixed overhead for the work that is not
// per-requirement: selecting the cds bundle batch, reading MANIFEST.tsv, the dependency
// check. Over-estimating costs tool calls; under-estimating costs correctness, so the
// estimator is biased high and floored, never trimmed.
const singleRepo = repos.length === 1
const CALLS_PER_REQUIREMENT = singleRepo ? 4 : 6
// Bundle selection, MANIFEST.tsv, unpackaged.md, the dependency check — work that exists
// once per run rather than once per requirement.
const BUDGET_OVERHEAD = 20
// A floor, so a PRD whose structure the estimator cannot read is not starved; and a cap, so
// a pathological document cannot ask for an unbounded session.
const MIN_REQUIREMENTS = 8
const MAX_REQUIREMENTS = 40
const countMatches = (re) => (prdBody.match(re) || []).length
const headingEstimate = Math.max(
  countMatches(/^#{3}\s+\S/gm),
  countMatches(/^#{4}\s+\S/gm),
  countMatches(/^#{5}\s+\S/gm),
  countMatches(/^#{6}\s+\S/gm)
)
const labelEstimate = new Set(prdBody.match(/\b[A-Z]{2,6}-\d{2,3}\b/g) || []).size
const requirementEstimate = Math.min(MAX_REQUIREMENTS, Math.max(MIN_REQUIREMENTS, headingEstimate, labelEstimate))
const CALL_CEILING = requirementEstimate * CALLS_PER_REQUIREMENT + BUDGET_OVERHEAD

// ── WHAT THIS INVENTORY IS EXPECTED TO RETURN, AND WHY NONE OF IT IS STATED ──────
//
// EVERY list this mini asks for is a READ. The reconciler does not compose an inventory,
// it reports one: the evidence is whatever it found in the repository, the conforming and
// removal material is whatever is there, the repos are wherever the material lives, the
// consulted artifacts are the files it opened, the change findings are the upstream
// contracts that moved, and the unexamined ids are the requirements its budget did not
// reach. Every one of those counts is a property of the PRD and of the codebase, not a
// volume the agent chooses — so NO ceiling is stated to it. "Report at most N of what you
// found" can only be honoured by under-reporting, and under-reporting an inventory is how
// the pipeline rebuilds something that already exists or leaves something contradicting
// the PRD in place. What DOES bound this dispatch is the search budget already in the
// brief, which limits what it may look at, not what it may say about what it found.
//
// The figures below are what this script expects, used only to flag a count worth a look.
// They are the old schema bounds, raised where the old value sat close to normal output —
// a requirement citing more than eight pieces of evidence is thorough, not runaway, and a
// UI pass legitimately opens more than forty artifacts.
const EVIDENCE_EXPECTED = 15
const MATERIAL_EXPECTED = 60
const CONSULTED_EXPECTED = 120
const CHANGE_FINDINGS_EXPECTED = 40
const UNEXAMINED_EXPECTED = Math.max(200, requirementEstimate)
log(
  `Search budget: ~${requirementEstimate} requirement(s) estimated from the PRD structure ` +
    `(${headingEstimate} heading(s), ${labelEstimate} requirement label(s)) × ${CALLS_PER_REQUIREMENT} call(s) each ` +
    `+ ${BUDGET_OVERHEAD} overhead = ${CALL_CEILING} tool calls.`
)
const scopeBlock = singleRepo
  ? `THE ONE REPOSITORY YOU SEARCH — this run is scoped to it, and only it:
${repoBlock}

Search THIS repository. Do not survey the other repositories in the project, and do not go
looking for a requirement's implementation elsewhere: another repository's copy of this run
covers it, and a claim you cannot cite from here is not evidence about here. A requirement
whose material is not in this repository is \`absent\` — that is the correct and complete
answer for this repository, and it is never a reason to widen the search or to leave the
requirement out of the inventory.`
  : `Repositories in scope:
${repoBlock}`

// ── Phase 1: Reconciliation checks — ONE independent checker session, both checks ──
// This used to be two parallel sessions, each paying a full session-start to read the
// same PRD and the same repositories. Both are read-only CHECKS on a document authored
// upstream — neither ever judged the other's output — so one session carrying both
// preserves segregation of duties, and the reduction below still judges no code: it
// applies a fixed rule to the typed findings.
phase('Reconciliation checks')

const combined = await settleAgent(
  `${rulingsBlock}Take an INVENTORY of the material that already exists for this PRD, and detect upstream changes that invalidate what it assumes. You are READ-ONLY over the codebase, the design mocks and the cloud account: read, search and query what the inventory needs, but change nothing anywhere and write no document. Two checks, one pass — return both.

═══ THE RULE THAT GOVERNS THIS ENTIRE TASK ═══

THE PRD IS CANONICAL. It is the latest and greatest statement of what the product must
be, and it overrides whatever is deployed today. Code that already ships is MATERIAL,
not authority:

  - material that CONFORMS to the PRD is reused;
  - material that CONTRADICTS the PRD is removed;
  - where nothing exists, it gets built.

You are NOT deciding which requirements survive. EVERY requirement the PRD states comes
back in your inventory with a status. You never drop one, never narrow one, never defer
one, and never mark one no longer applicable — nothing outside the PRD has the standing
to retire a PRD requirement, and that includes you and it includes the deployed system.
If the count of requirements you return is smaller than the count of requirements the PRD
states, you have made an error.

WHEN THE PRD AND THE DEPLOYED SYSTEM DISAGREE, THE PRD WINS, AND THAT IS SETTLED. It is
not an open question, it convenes no panel, and it raises no architecture question. It
produces one thing: removal work, named precisely.

═══ CHECK 1 — the material inventory ═══

${prdBlock}

${scopeBlock}

Enumerate EVERY requirement the PRD states, and for each one classify the MATERIAL — what
exists today relative to what the PRD asks for. The status describes the material, not the
requirement's fate:

- conforms    — an implementation exists and it MATCHES what the PRD asks for. It is
                material to REUSE. Name what to reuse in \`conformingMaterial\`, cited.
- contradicts — an implementation exists but it DIFFERS from what the PRD asks for. The
                PRD wins; this is material to REMOVE or replace. Name exactly what must be
                deleted in \`removalTargets\`, cited. Being deployed, being large, or being
                recently written are not reasons to call something conforming.
- absent      — nothing exists. Say what is missing in \`missing\`. It gets built.


Also classify the SURFACE each requirement lives on, in \`surface\`:
  ui | service | infra | data | unknown
This is load-bearing — see check 1b.

EVIDENCE IS MANDATORY AND IT IS THE WHOLE POINT OF THIS CHECK. Every status must cite
concrete evidence: a \`file:line\` you actually read, a URL, a named deployed endpoint you
actually called, or an \`arn:aws\` identifier. A \`conforms\` or \`contradicts\` with nothing
concrete behind it is DISCARDED and treated as \`absent\` downstream — an unevidenced
\`conforms\` in particular would make the pipeline reuse something that may not match the
PRD at all, which is the expensive error here. Prefer several pieces of evidence over one.

You hold full AWS admin credentials. Checking a live endpoint is legitimate and is often
the decisive evidence — a capability can be fully implemented in the repository and
switched off in infrastructure, which reads as built from the code alone and as missing
from the deployed system. Look for both. EVERY aws command you run MUST pass
\`--profile ${awsProfile}\`; a command without it targets the wrong account.

Look specifically for the material that is easy to miss:
- an implementation that is complete but DISABLED by a feature flag, a commented-out
  construct, or an infrastructure switch — cite the file:line of the switch;
- a frontend fully scaffolded over a backend that does not exist, or the reverse;
- a capability live for some cases and not others (three of four identity providers);
- a route table, handler list, or CDK stack that already serves what the PRD asks for;
- code that serves a SUPERSEDED version of this behaviour — that is \`contradicts\`, and its
  removal is work somebody has to do.

═══ CHECK 1b — UI REQUIREMENTS ARE RESOLVED AGAINST THE cds DESIGN SYSTEM ═══

For every requirement whose \`surface\` is \`ui\`, the design system's own output is the
AUTHORITY. Authority runs in this order, highest first, and you resolve each UI
requirement at the highest level that has an artifact for it:

  1. THE cds HAND-OFF BUNDLE — the packaged artifact: its \`spec/build-spec.md\` together
     with the composed HTML under \`design/\`. This is the boundary between "approved in
     cds" and "built in the app repo", and it is the highest authority there is for UI.
  2. THE LOOSE COMPOSED ARTIFACT under \`design-mocks/{shells,pages,views}/\` — used when
     the artifact is not in the bundle.
  3. THE PRD's PROSE about layout.
  4. WHAT IS CURRENTLY DEPLOYED — lowest, and NEVER authoritative for UI.

── Level 1: the hand-off bundle ──

Bundle root:
${packagesDir ? `  ${packagesDir}` : '  the design-mocks/packages/ directory under the repository this run operates on'}
Resolve \`CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR\` from the environment first when it is set;
otherwise use the path above. The root holds dated \`batch-*\` directories — TAKE THE MOST
RECENT ONE and record it in \`uiAuthority.bundlePath\`. Inside a batch:

  MANIFEST.tsv                      every artifact in the bundle: folder, slug, family, theme
  unpackaged.md                     composed files that are NOT in this bundle (see below)
  {shells,pages,views}/<slug>/
      design/<kind>.html            the composed artifact (shell.html | page.html | view.html)
      spec/build-spec.md            what the app repo builds — READ THIS
      spec/wireframe.txt            the structural sketch
      spec/decisions.md             the composer's recorded decisions
      state/<slug>.yaml             the composer state record
  styles/                           ONE shared stylesheet set for every artifact in the
                                    bundle (tokens.css, components.css, themes.css,
                                    manifest.json) — verified current at packaging time and
                                    NOT regenerated in the app repo
  assets/                           shared assets + artwork-manifest.yaml

START AT \`MANIFEST.tsv\`. It is the cheap index — one read tells you which slugs are
bundled, so you can match a UI requirement to its artifact without listing directories.
Then read that artifact's \`spec/build-spec.md\` and, when the requirement turns on layout
or structure, its composed HTML.

── Level 2: unpackaged artifacts ──

\`unpackaged.md\` lists composed files that have no state record and are therefore NOT in
the bundle. ABSENCE FROM THE BUNDLE MEANS "NOT YET PACKAGED" — it never means "not
decided", and it never blocks anything. Such a requirement simply falls back to authority
level 2: the loose composed artifact under
${mocksDir ? `  ${mocksDir}/{shells,pages,views}/` : '  design-mocks/{shells,pages,views}/'}
(resolve \`CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR\` / \`_SHELLS_DIR\` first when set;
\`DESIGN.md\` beside them is the exported design system: tokens, geometry, building blocks,
rules). Say in \`evidenceSummary\` that the artifact is unpackaged. It is never an
architecture question and never a reason to stop.

── Evidence and the verdict ──

CITE THE SPECIFIC ARTIFACT PATH YOU ACTUALLY USED as the evidence for every \`ui\`
requirement — a \`.../batch-<stamp>/views/<slug>/spec/build-spec.md\` or a
\`design-mocks/pages/<name>.html\` is strong evidence for a UI requirement in exactly the way
a \`file:line\` is for a service one. List every artifact path you opened in
\`uiAuthority.artifactsConsulted\`, and keep \`uiAuthority.shellsConsulted\` /
\`uiAuthority.pagesConsulted\` for the loose shells and pages you read. Record the batch you
selected in \`uiAuthority.bundlePath\` and the mocks directory in \`uiAuthority.mocksDir\`.

A UI requirement is \`conforms\` ONLY when the deployed UI matches the PACKAGED artifact
(or, for an unpackaged one, the composed artifact). Anything else is \`contradicts\`, and the
packaged artifact wins. That is not a competing option, not a design question, and NEVER an
architecture question — layout, shells, navigation shape, components, visual design and
interaction patterns are settled by the design system. Name the deployed markup or
component to bring into line in \`removalTargets\` and move on.

If neither the bundle nor the mocks directory exists, say so in \`evidenceSummary\` and
record the paths you looked for. Do not substitute the deployed UI as the authority in
their place.

Do not soften a finding to be agreeable in either direction. Calling existing material
absent causes it to be rebuilt alongside itself; calling contradicting material conforming
leaves the product in the state the PRD was written to change.

═══ SEARCH BUDGET ═══

You are answering one question per requirement${singleRepo ? ' about ONE repository' : ''}, not
auditing the estate. Work requirement by requirement and stop searching for each the moment
its status is settled: one decisive hit — the file:line that implements it, the mock that
defines it, a live endpoint that answers — settles \`conforms\` or \`contradicts\` and you move
on. Two or three well-aimed searches that all miss settles \`absent\` — absence is a
legitimate finding, not a reason to keep looking. Prefer one targeted search over browsing a
repository, and never re-open a file to confirm something you already read. Roughly
${CALLS_PER_REQUIREMENT} tool calls per requirement is the expected shape.

"No implementation found after targeted search" is a correct and complete answer.
Exhaustively proving a negative is not more rigorous — it costs far more and says the same
thing, and an unevidenced claim is dropped downstream regardless.

═══ CHECK 2 — upstream dependency changes ═══

Upstream dependencies the PRD relies on:
${dependencies.length ? dependencies.map((d, i) => `${i + 1}. ${d}`).join('\n') : '(none declared in args — discover them from the PRD text and the repositories above)'}

Determine whether any upstream contract, shared schema, event, library version, or interface the PRD assumes has changed in a way that invalidates one of its assumptions. This is not a search for defects in the PRD's wording — it is a search for ground that moved. Return this check under \`dependencyChanges\`:
- current: true if no invalidating upstream change is found, false otherwise.
- changeFindings: each invalidating change (dependency, change describing what changed, invalidates describing which PRD assumption it breaks).
- evidence: how you verified the dependency state (one paragraph, under 60 words).

═══ YOUR BUDGET ═══

Your structured output IS the deliverable. Nothing you read reaches anybody except through it, so an exhaustive investigation that ends without it is worth exactly as much as no investigation at all — and it is how this phase has failed in practice: the reconciler explored until it ran out of room and returned nothing, so the whole run aborted and the work was re-dispatched from zero.

You have roughly ${CALL_CEILING} tool calls — that figure is this PRD's own requirement count at ${CALLS_PER_REQUIREMENT} calls each, plus overhead, so it is sized to let you look at EVERY requirement. Spend it breadth-first: cover every requirement at least once before you deepen any of them, because a requirement you never looked at comes back as \`absent\` and gets built from scratch beside material that already exists. By call ${CALL_CEILING}, stop investigating and emit your structured output with whatever you have — a partial inventory with honest evidence is a usable result; a perfect inventory you never returned is not.

AN UNEXAMINED REQUIREMENT IS NAMED, NEVER REPORTED AS \`absent\`. \`absent\` is a FINDING: it means you searched for the material and it is not there. "I ran out of budget before reaching it" is not that finding, and reporting it as one is the single most expensive error this phase can make. So return \`coverage\` on every run:
- \`unexaminedRequirementIds\` — the id of EVERY requirement you did not actually search for, exactly as you numbered it in \`requirements\`. Empty when you covered them all, which is the expected outcome.
- \`budgetExhausted\` — true if you stopped because you reached the ceiling rather than because the work was done.
- \`note\` — one sentence on what was left and why, when either of the above is non-empty.
Such a requirement still appears in \`requirements\` with its honest status, and the phase reports it as unexamined to its caller.`,
  {
    label: 'reconcile:reality-and-dependencies',
    phase: 'Reconciliation checks',
    effort: 'medium',
    agentType: 'agent-teams-workforce:prd-reality-reconciler',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['requirements', 'evidenceSummary', 'dependencyChanges', 'coverage'],
      properties: {
        // Required, so "I covered everything" is a STATED empty list rather than a silence
        // the reduction has to interpret. A budget that cuts the input short must surface as
        // a named, machine-readable finding — never as a requirement quietly called absent.
        coverage: {
          type: 'object',
          additionalProperties: false,
          required: ['unexaminedRequirementIds', 'budgetExhausted'],
          properties: {
            // No bound, and nothing stated: this list exists precisely for the run that
            // went badly, and a bound on it would discard the inventory of the run most
            // in need of reporting.
            unexaminedRequirementIds: { type: 'array', items: { type: 'string' } },
            budgetExhausted: { type: 'boolean' },
            note: { type: 'string' },
          },
        },
        requirements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'requirement', 'status', 'evidence', 'surface'],
            properties: {
              id: { type: 'string' },
              requirement: { type: 'string' },
              status: { type: 'string', enum: ['conforms', 'contradicts', 'absent'] },
              // A status with no evidence behind it is the defect this mini exists to
              // catch, and the reduction below catches it: an unevidenced claim is demoted
              // to `absent` and recorded in `evidenceViolations`. That enforcement runs
              // once the result is in hand, so one honest no-citation answer costs that
              // requirement its status and nothing else. A schema bound here would instead
              // destroy the whole inventory, including the N-1 requirements that WERE cited.
              evidence: { type: 'array', items: { type: 'string' } },
              surface: { type: 'string', enum: ['ui', 'service', 'infra', 'data', 'unknown'] },
              // Counted in the reduction, never bound and never capped in the brief:
              // what is in the repository is not the reconciler's to keep short.
              conformingMaterial: { type: 'array', items: { type: 'string' } },
              removalTargets: { type: 'array', items: { type: 'string' } },
              missing: { type: 'string' },
            },
          },
        },
        evidenceSummary: { type: 'string' },
        uiAuthority: {
          type: 'object',
          additionalProperties: false,
          properties: {
            bundlePath: { type: 'string' },
            mocksDir: { type: 'string' },
            artifactsConsulted: { type: 'array', items: { type: 'string' } },
            shellsConsulted: { type: 'array', items: { type: 'string' } },
            pagesConsulted: { type: 'array', items: { type: 'string' } },
          },
        },
        dependencyChanges: {
          type: 'object',
          additionalProperties: false,
          required: ['current', 'changeFindings', 'evidence'],
          properties: {
            current: { type: 'boolean' },
            changeFindings: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['dependency', 'change', 'invalidates'],
                properties: {
                  dependency: { type: 'string' },
                  change: { type: 'string' },
                  invalidates: { type: 'string' },
                },
              },
            },
            evidence: { type: 'string' },
            notes: { type: 'string' },
          },
        },
      },
    },
  }
)

const reality = combined
const dependencyChanges = (combined && combined.dependencyChanges) || null
checkLimit('Reconcile (dependencies)', 'changeFindings', dependencyChanges && dependencyChanges.changeFindings, CHANGE_FINDINGS_EXPECTED)

// ── A DEAD AGENT IS NOT A FINDING ───────────────────────────────────────────────
//
// A dispatch dies in two ways — skipped or dead on a terminal API error (null), or run
// to completion without ever emitting its structured output (a throw). settleAgent()
// above normalizes both to null and records which agent died. Neither is the same event
// as a reconciler that ran and returned a malformed inventory, and folding them together
// is what turned two of the five real prd-to-spec runs into work failures at stage
// 'prd-reconciliation': the supervisor charged the bead for an account limit. Both still
// stop the run — reading "we could not establish what exists" as "nothing exists" is the
// blind assumption this phase removes — but only one of them is anybody's fault, and the
// caller needs to be able to tell which.
if (!reality) {
  const deaths = dispatchDeaths()
  return fail(
    'the reality reconciler never came back with an account of what already exists, so no ' +
      `reconciliation was performed (${deaths.map((f) => f.note).join('; ') || 'no dispatch was recorded'}). ` +
      'This is a DISPATCH failure, not a verdict on the PRD or on what already exists.',
    { dispatchFailed: true, dispatchFailures: deaths }
  )
}
if (!Array.isArray(reality.requirements)) {
  return fail('the reality reconciler returned no requirement inventory — reconciliation cannot be reduced to an inventory.')
}

// ── Evidence enforcement ────────────────────────────────────────────────────────
// A schema constrains the REQUEST, not the response, so the rule is applied again here
// where it is deterministic and testable. The two directions of error are not symmetric,
// and the asymmetry is the opposite of what it was under the delta contract. There, an
// unevidenced "shipped" deleted work from the delta and it was never built. Here nothing
// is ever deleted from scope — but an unevidenced `conforms` makes the pipeline REUSE
// material that may not match the PRD at all, and an unevidenced `contradicts` sends a
// removal task after a file nobody confirmed.
//
// So an unevidenced claim is never resolved in favour of the claim: it drops to
// 'absent', which means "build it fresh". That is never wrong under this rule, only
// more expensive. Every demotion is reported.
//
// Evidence must also LOOK like evidence: a file:line, a URL, a named endpoint, or an AWS
// resource identifier. "I checked the code" is a claim about the checker, not about the
// system.
//
// ONE narrow exemption, and it is narrow deliberately. A composed cds artifact is a
// single generated file — hundreds of kilobytes of machine-emitted HTML — and its build
// spec is a whole document; demanding a line number inside either is evidence theatre,
// because the artifact IS the unit of authority and no line of it means anything alone.
// So a `.html` or `.md` path is admissible WITHOUT a line number, but only when it sits
// under the design-system directories: the mocks root or the hand-off bundle root.
//
// Everywhere else the original bar holds, and that is the point of scoping it. A bare
// `services/auth/mfa.py` with no line number is "I saw the filename", not "I read the
// implementation" — and sustaining a `conforms` on it would make the pipeline reuse
// material on the strength of a path somebody typed. That is precisely the failure this
// gate exists to catch, so the exemption must never reach a service, infra or data file.
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const uiRoots = ['design-mocks', mocksDir, packagesDir]
  .filter((d) => hasText(d))
  .map((d) => escapeRe(d.replace(/\/+$/, '')))
const uiArtifactPath = new RegExp(`(?:${uiRoots.join('|')})/[^\\s"'\`]*\\.(?:html|md)\\b`, 'i')

// A CITED ENDPOINT, NOT THE WORD "ENDPOINT".
//
// The original test was `/\bendpoint\b/i`, which matches the word anywhere in a sentence
// — so "no endpoint was found" read as strong evidence and sustained a `conforms`. A
// statement that something does NOT exist was being counted as proof that it does, in the
// one gate standing between a loose claim and the pipeline reusing material that does not
// match the PRD.
//
// So the citation must identify an ADDRESS: a method and path, an AWS API host, or an
// actual CLI invocation with arguments. A URL and an `arn:aws` already pass on their own
// clauses.
const ENDPOINT_CITATION =
  /\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\/[A-Za-z0-9._~/{}:$-]+/.source +
  '|' +
  /\b[a-z0-9-]+\.(?:execute-api|appsync-api|lambda-url)\.[a-z0-9-]+\.amazonaws\.com\S*/i.source +
  '|' +
  /\baws\s+[a-z0-9-]+\s+[a-z0-9-]+\b[^\n]*\s--[a-z][a-z-]*/i.source
const endpointCitation = new RegExp(ENDPOINT_CITATION, 'i')

// …and the address must not be sitting inside a denial that it exists. "the endpoint
// GET /v1/settings does not exist" cites a real address to say the opposite of what a
// `conforms` claims. This veto is deliberately scoped to the endpoint clause alone: a
// `contradicts` is very often evidenced as "web/Shell.tsx:12 renders a nav that does not
// exist in the mock", and that is a correct citation which must keep passing on the
// file:line clause.
const denied = (s) =>
  /\b(?:no|not|never)\s+(?:\w+\s+){0,2}(?:found|exists?|implemented|deployed|present|configured)\b/i.test(s) ||
  /\bdoes\s*n[o']?t\s+exist\b/i.test(s) ||
  /\b(?:could|can)\s*n[o']?t\s+(?:find|locate|reach)\b/i.test(s) ||
  /\bno\s+(?:such\s+)?(?:endpoint|route|handler|implementation|resource|api)\b/i.test(s) ||
  /\bnothing\s+(?:was\s+)?found\b/i.test(s) ||
  /\bnot\s+found\b/i.test(s)

const strongEvidence = (s) =>
  /:\d+/.test(s) ||
  /https?:\/\//i.test(s) ||
  /\barn:aws\b/i.test(s) ||
  uiArtifactPath.test(s) ||
  (endpointCitation.test(s) && !denied(s))

const SURFACES = ['ui', 'service', 'infra', 'data', 'unknown']
const evidenceViolations = []
const requirements = reality.requirements.map((r, i) => {
  const id = hasText(r && r.id) ? r.id : `R${i + 1}`
  const evidence = (Array.isArray(r && r.evidence) ? r.evidence : []).filter((e) => hasText(e)).map((e) => e.trim())
  const claimed = (r && r.status) || 'absent'
  // A status outside the enum is a demotion like any other, and it has a real source: a
  // resumed run, a hand-built packet, or a model reaching for the retired `shipped` /
  // `partial` / `obsolete` vocabulary. It must be COUNTED, not just remembered in
  // `claimedStatus` — the ledger's violation count is what tells a reader how much of the
  // inventory was downgraded, and a demotion missing from it makes that number a lie.
  const recognised = claimed === 'conforms' || claimed === 'contradicts' || claimed === 'absent'
  let status = claimed === 'conforms' || claimed === 'contradicts' ? claimed : 'absent'
  if (!evidence.length) {
    status = 'absent'
    evidenceViolations.push({ id, claimedStatus: claimed, reason: 'no evidence supplied' })
  } else if ((status === 'conforms' || status === 'contradicts') && !evidence.some(strongEvidence)) {
    status = 'absent'
    evidenceViolations.push({
      id,
      claimedStatus: claimed,
      reason:
        'no file:line, cited design-system artifact under the mocks or bundle root, deployed endpoint, URL, or AWS resource identifier among the evidence',
    })
  } else if (!recognised) {
    evidenceViolations.push({
      id,
      claimedStatus: claimed,
      reason: `unrecognised status '${claimed}' — not one of conforms / contradicts / absent, so it cannot be honoured`,
    })
  }
  const list = (v) => (Array.isArray(v) ? v.filter((x) => hasText(x)).map((x) => x.trim()) : [])
  // What was found, counted against what this script expects. The one MINIMUM this mini
  // has — every status carries evidence — is not counted here because
  // it is already ENFORCED above, and better: an unevidenced status is demoted to
  // `absent` and named in `evidenceViolations`, which costs that one requirement its
  // status and leaves the other N-1 intact.
  checkLimit(`Reconcile (${id})`, 'evidence', evidence, EVIDENCE_EXPECTED)
  checkLimit(`Reconcile (${id})`, 'conformingMaterial', list(r && r.conformingMaterial), MATERIAL_EXPECTED)
  checkLimit(`Reconcile (${id})`, 'removalTargets', list(r && r.removalTargets), MATERIAL_EXPECTED)
  return {
    id,
    requirement: (r && r.requirement) || '',
    status,
    evidence,
    // These describe the material, so they only survive alongside the status that names
    // them — a demoted requirement carries no reuse or removal instruction at all.
    // Removal in particular is DESTRUCTIVE: `removalTargets` becomes a task telling
    // somebody to delete named files, and an unconfirmed claim is not grounds to delete
    // anything. Reuse is the mirror error, quieter but not smaller: it makes the pipeline
    // build on material nobody verified matches the PRD.
    conformingMaterial: status === 'conforms' ? list(r && r.conformingMaterial) : [],
    removalTargets: status === 'contradicts' ? list(r && r.removalTargets) : [],
    missing: status === 'absent' ? (r && r.missing) || null : null,
    surface: SURFACES.indexOf(r && r.surface) !== -1 ? r.surface : 'unknown',
    claimedStatus: claimed,
  }
})

// ── AN UNEXAMINED REQUIREMENT IS NOT AN ABSENT ONE ──────────────────────────────
//
// `absent` is a finding — searched for, not there — and the phases downstream act on it by
// building the thing. "Never looked at" reduces to the same three-letter status and is NOT
// the same claim: it is the budget silently shrinking the input, which is the defect this
// coverage contract exists to make visible. So the ids the reconciler names as unexamined
// are carried on the requirement AND reported as their own list, and the phase says plainly
// when its budget ran out.
const cov = (reality && reality.coverage) || {}
checkLimit('Reconcile', 'unexaminedRequirementIds', cov.unexaminedRequirementIds, UNEXAMINED_EXPECTED)
const unexaminedIds = new Set(
  (Array.isArray(cov.unexaminedRequirementIds) ? cov.unexaminedRequirementIds : []).filter((x) => hasText(x)).map((x) => x.trim())
)
// The caller renders `missing` beside an `absent` status, so an unexamined requirement says
// so there, where the spec author reads it, instead of reading as a searched-for absence.
for (const r of requirements) {
  r.examined = !unexaminedIds.has(r.id)
  if (!r.examined && r.status === 'absent') {
    r.missing = 'UNEXAMINED — the reconciler did not search this repository for it, so its material here is unestablished. Search before specifying it as new.'
  }
}
const unexaminedRequirements = requirements
  .filter((r) => !r.examined)
  .map((r) => ({ id: r.id, requirement: r.requirement, reportedStatus: r.status }))
const coverage = {
  requirementCount: requirements.length,
  examinedCount: requirements.length - unexaminedRequirements.length,
  unexaminedRequirementIds: unexaminedRequirements.map((r) => r.id),
  budgetExhausted: !!cov.budgetExhausted,
  callCeiling: CALL_CEILING,
  requirementEstimate,
  note: hasText(cov.note) ? cov.note.trim() : null,
  complete: unexaminedRequirements.length === 0,
}
if (!coverage.complete || coverage.budgetExhausted) {
  log(
    `Coverage shortfall: ${unexaminedRequirements.length} of ${requirements.length} requirement(s) went UNEXAMINED` +
      `${coverage.budgetExhausted ? ` (the ${CALL_CEILING}-call ceiling was reached)` : ''} — ` +
      `${coverage.unexaminedRequirementIds.join(', ') || 'none named'}. These are NOT findings of absence; their status is unestablished.`
  )
}

if (evidenceViolations.length) {
  log(
    `Evidence enforcement: ${evidenceViolations.length} requirement status claim(s) could not be honoured — unevidenced, ` +
      `or claiming a status outside the enum — and were demoted to 'absent'. They will be built fresh rather than reused ` +
      `or removed on an unconfirmed claim.`
  )
}

// ── Reduction: the inventory, the work it implies, and whether architecture is needed ──
// Computed HERE, from the typed findings, rather than asked of a model. Nothing in this
// reduction narrows the PRD: every requirement that came in goes out.
const conformsCount = requirements.filter((r) => r.status === 'conforms').length
const contradictsCount = requirements.filter((r) => r.status === 'contradicts').length
const absentCount = requirements.filter((r) => r.status === 'absent').length

// Removal is real work and it must reach decomposition as a first-class output. A
// contradiction that is only recorded as a status becomes a removal nobody does, and the
// product keeps shipping the thing the PRD was written to replace.
const removalWork = requirements
  .filter((r) => r.status === 'contradicts' && r.removalTargets.length)
  .map((r) => ({ requirementId: r.id, requirement: r.requirement, targets: r.removalTargets }))

// Reuse is the other half: named material the downstream phases build ON rather than
// re-derive. It is context for them, never a subtraction from what the PRD asks.
const reuseWork = requirements
  .filter((r) => r.status === 'conforms' && r.conformingMaterial.length)
  .map((r) => ({ requirementId: r.id, requirement: r.requirement, material: r.conformingMaterial }))

// `bundlePath` is the batch the reconciler actually selected — spec authoring reads the
// bundle's build-specs rather than re-deriving UI from PRD prose, so the resolved path
// travels with the inventory. Null when no bundle was found; the packages ROOT is not
// substituted for it, because "which batch" is the part that matters.
const ua = (reality && reality.uiAuthority) || {}
const strList = (v) => (Array.isArray(v) ? v.filter((x) => hasText(x)).map((x) => x.trim()) : [])
const uiAuthority = {
  bundlePath: hasText(ua.bundlePath) ? ua.bundlePath.trim() : null,
  mocksDir: hasText(ua.mocksDir) ? ua.mocksDir.trim() : mocksDir || null,
  artifactsConsulted: strList(ua.artifactsConsulted),
  shellsConsulted: strList(ua.shellsConsulted),
  pagesConsulted: strList(ua.pagesConsulted),
}
checkLimit('Reconcile (ui authority)', 'artifactsConsulted', uiAuthority.artifactsConsulted, CONSULTED_EXPECTED)
checkLimit('Reconcile (ui authority)', 'shellsConsulted', uiAuthority.shellsConsulted, CONSULTED_EXPECTED)
checkLimit('Reconcile (ui authority)', 'pagesConsulted', uiAuthority.pagesConsulted, CONSULTED_EXPECTED)

log(
  `Reconciliation: ${requirements.length} requirement(s) inventoried — ${conformsCount} conform (reuse), ` +
    `${contradictsCount} contradict (remove), ${absentCount} absent (build).`
)

const uiCount = requirements.filter((r) => r.surface === 'ui').length
if (uiCount) {
  log(
    `UI authority: ${uiCount} ui requirement(s) resolved against ` +
      `${uiAuthority.bundlePath ? `the cds hand-off bundle ${uiAuthority.bundlePath}` : 'the loose composed mocks (no hand-off bundle was resolved)'}` +
      `${uiAuthority.artifactsConsulted.length ? `, ${uiAuthority.artifactsConsulted.length} artifact(s) consulted` : ''}.`
  )
}

const ledger = {
  phase: 'prd-reconciliation',
  beadId: null,
  subject: prdId || prdTitle || null,
  chosen: ['prd-reality-reconciler (both checks, one session)'],
  mode: 'combined', // one checker session carries both reconciliation checks
  requirementCount: requirements.length,
  conformsCount,
  contradictsCount,
  absentCount,
  removalWork: removalWork.length,
  evidenceViolations: evidenceViolations.length,
  limitOverages: limitFindings.length,
  unexaminedCount: unexaminedRequirements.length,
  budgetExhausted: coverage.budgetExhausted,
  callCeiling: CALL_CEILING,
  ok: true,
}

return {
  ok: true,
  // EVERY requirement the PRD states, never filtered and never narrowed.
  requirements,
  conformsCount,
  contradictsCount,
  absentCount,
  // The caller stamps the repository it dispatched this run for onto each work item.
  removalWork,
  reuseWork,
  uiAuthority,
  dependencyChanges,
  evidenceViolations,
  // What was actually looked at. `unexaminedRequirements` is a first-class finding: those
  // requirements' statuses are unestablished, not established as absent.
  coverage,
  unexaminedRequirements,
  evidenceSummary: (reality && reality.evidenceSummary) || null,
  // Every list that came back longer than the brief stated, named with its count. The
  // inventory above carries all of it regardless; this is what it cost.
  ...(limitFindings.length ? { limitFindings } : {}),
  ledger,
}
