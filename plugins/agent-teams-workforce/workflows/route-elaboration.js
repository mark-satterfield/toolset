export const meta = {
  name: 'route-elaboration',
  description:
    'Leaf mini — the ELABORATION router. Routes a PRD/Epic or a Spec/Story to the document pipeline that takes it forward: an Epic to reconciling its PRD, authoring the TRD, and producing the Specs, Stories and Tasks beneath it; a Story to keeping it in sync with its Spec and its Tasks current and covering it. This is real work, but it is NOT development work — a Task belongs to route-build and is skipped here with a pointer to it. A Bug belongs to neither router: it is a reporting mechanism, triaged by a person into an Epic, a Task, or a closure, and is skipped here with a reason naming triage. Child count is never consulted: a container that already has children can still have drifted from the document above it. Elaboration is a product decision, so it requires an explicit human-initiated invocation; an unattended sweep gets a skip and the command to run. Returns { bead, action, composite, reason }: action is "elaborate" or "skip".',
  phases: [
    { title: 'Classify', detail: 'document-side hierarchy rules; never force-fit' },
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
//   bead: {
//     id:           string,          // e.g. "<prefix>-123"
//     type?:        string,          // epic | story | feature | ...
//     labels?:      string[],
//     title?:       string,
//     description?: string,
//     parentType?:  string,
//     parentId?:    string,          // a Story's Epic — the bead prd-to-spec is run over
//     ancestorTypes?: string[],
//   },
//   allowAmbiguityAgent?: boolean,   // default true
//   humanInitiated?: boolean,        // default FALSE. Set ONLY when a person invoked
//                                    // this run (e.g. /work-bead, /start-prd).
// }
//
// Returns: {
//   bead,
//   action,      // 'elaborate' | 'skip'
//   composite,   // 'prd-to-spec' | null
//   reason,
//   ruledBy?,    // 'deterministic' | 'ambiguity-detector'
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const allowAmbiguityAgent = a.allowAmbiguityAgent !== false

// Existence is NOT readiness. An Epic or a Story sitting there is not a request to
// elaborate it — running the pipeline is, and that is a product decision a person
// makes. So elaboration is gated on the caller stating a human initiated this run.
// An unattended sweep leaves the flag unset and receives a skip with the command.
// The gate lives here rather than in each caller: a rule every future caller has
// to remember is not a rule.
const humanInitiated = a.humanInitiated === true

const norm = (v) => String(v || '').trim().toLowerCase()
const type = norm(bead.type)
const labels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm).filter(Boolean)
const labelSet = new Set(labels)
const hasLabel = (...names) => names.some((n) => labelSet.has(n))
// A declared type outranks labels. A Task carrying a `bug` label (a triaged bug) is still a
// Task, and a Story labelled `infra` is still a Story, so labels only classify a bead whose
// type is missing or unrecognised.
const KNOWN_TYPES = new Set(['task', 'bug', 'infra', 'infrastructure', 'epic', 'story', 'feature', 'chore', 'docs', 'research', 'spike'])
const byLabel = (...names) => !KNOWN_TYPES.has(type) && hasLabel(...names)

const parentType = norm(bead.parentType)
const ancestorTypes = (Array.isArray(bead.ancestorTypes) ? bead.ancestorTypes : []).map(norm)
const labelTail = labels.length ? `, labels=[${labels.join(', ')}]` : ''

phase('Classify')

function route(action, composite, reason, ruledBy) {
  return { bead, action, composite, reason, ruledBy: ruledBy || 'deterministic' }
}
const elaborate = (composite, reason) => route('elaborate', composite, reason)
const skip = (reason) => route('skip', null, reason)

const id = bead.id || '<bead-id>'

// ── What this router is for ───────────────────────────────────────────────────
//
//   Files:  PRD ──> TRD ──> Spec
//   Beads:  Epic ──1:many──> Story ──> Task          Bug stands alone
//
//   A PRD and its Epic are ONE item in two representations, created together, as
//   are a Spec and its Story. The FILE side is what decomposes; the beads are what
//   that chain deposits. Nothing "decomposes" an Epic or a Story.
//
//   Both ARE workable — their work is elaboration:
//     Epic  — reconcile the PRD's contents into the Epic, author the TRD, produce
//             the Spec(s), and deposit the Stories and Tasks beneath it.
//     Story — keep the Story and its Spec in sync, and keep its Tasks current and
//             covering it.
//
//   CHILD COUNT IS NEVER CONSULTED. An Epic with four Stories can still need this:
//   the PRD may have moved on and the beads beneath it drifted. Treating "has
//   children" as "done" is what let drift accumulate silently.
function deterministicRoute() {
  // 1) EPIC — the bead face of a PRD.
  if (type === 'epic' || byLabel('epic')) {
    if (!humanInitiated) {
      return skip(
        `epic elaboration — reconciling its PRD, authoring the TRD, producing the Specs and Stories — is a decision about whether to build this, and now. That is a human's call, not a sweep's. → SKIP. To work it: /agent-teams-workforce:work-bead ${id}, or /agent-teams-workforce:start-prd`,
      )
    }
    return elaborate(
      'prd-to-spec',
      `working this epic was human-initiated → prd-to-spec, which reconciles the PRD with the Epic, authors the TRD, and produces the Spec(s) and the Story and Task beads beneath it. An Epic that ALREADY has Stories may still need this — the PRD may have moved on.`,
    )
  }

  // 2) STORY — the bead face of a Spec.
  if (type === 'story' || byLabel('story')) {
    if (!humanInitiated) {
      return skip(
        `story elaboration — keeping the Story and its Spec in sync and its Tasks current and covering it — starts build work. That is a human's call, not a sweep's. → SKIP. To work it: /agent-teams-workforce:work-bead ${id}`,
      )
    }
    return elaborate(
      'prd-to-spec',
      `working this story was human-initiated → prd-to-spec, run over the Story's parent Epic${bead.parentId ? ` (${bead.parentId})` : ''} — prd-to-spec takes an Epic, never a Story — whose task-decomposition phase reconciles the Story with its Spec and emits the Task beads parented to it. A Story that ALREADY has Tasks may still need this — the Spec may have moved on.`,
    )
  }

  // 3) FEATURE — a request, not work. Promoting it to a PRD and an Epic is a
  //    product decision: whether this is worth building at all, and now. An
  //    automated loop that promotes every feature bead it finds has decided the
  //    roadmap, which is not a call any agent here has the standing to make.
  if (type === 'feature' || byLabel('feature', 'prd', 'requirement', 'prd-to-spec')) {
    if (!humanInitiated) {
      return skip(
        `feature is a REQUEST, not work (type="${type || 'n/a'}"${labelTail}). It becomes implementable by being promoted to a PRD and an Epic, which is a human decision about whether to build it. → SKIP. When you want it built: /agent-teams-workforce:start-prd`,
      )
    }
    return elaborate(
      'prd-to-spec',
      `promoting this feature was human-initiated → prd-to-spec, once the invoking command has resolved or minted its PRD and Epic (prd-to-spec starts from a ready PRD and never writes one); it carries them to TRD, Spec(s), Stories and Tasks`,
    )
  }

  // 4) BUG — neither elaboration work nor development work. A bug is a REPORTING
  //    MECHANISM: it is TRIAGED by a person into an Epic, a Task, or a closure.
  //    Pointing it at route-build would be wrong — that router skips it too.
  if (type === 'bug' || byLabel('bug', 'defect', 'regression', 'hotfix')) {
    return skip(
      `bug is a REPORTING MECHANISM and is never implemented directly (type="${type || 'n/a'}"${labelTail}) — it is TRIAGED into an Epic, a Task, or a closure, and that is a person's judgment call. Not elaboration work, and not development work either → SKIP (route-build skips it for the same reason; no triage composite exists to dispatch)`,
    )
  }

  // 5) DEVELOPMENT-SIDE kinds — real work, but not elaboration work.
  if (type === 'task' || type === 'infra' || type === 'infrastructure' ||
      byLabel('task', 'infra', 'infrastructure')) {
    return skip(
      `${type || 'this bead'} carries DEVELOPMENT work — code, tests, infrastructure, deployment to dev. → SKIP here. Route it through route-build.js instead.`,
    )
  }

  // 6) Explicitly out-of-pipeline kinds.
  if (type === 'chore' || type === 'docs' || type === 'research' || type === 'spike') {
    return skip(`type="${type}" is out of the automated pipeline (no composite handles it) → SKIP (reported, not force-fit)`)
  }

  // 7) Unknown — defer to the ambiguity agent if allowed.
  return null
}

const det = deterministicRoute()
if (det) {
  log(`route-elaboration ${bead.id || '(no id)'}: ${det.action.toUpperCase()}${det.composite ? ` via ${det.composite}` : ''} — ${det.reason}`)
  return det
}

// ── Ambiguity escalation ──────────────────────────────────────────────────────
// The deterministic table could not decide. Policy is never to force-fit, so the
// default is SKIP. The READ-ONLY ambiguity-detector may classify the bead's TYPE
// from its title/description — it decides what the bead IS, not what to run. The
// script then re-applies the same rules to that answer, so a classified bead can
// never bypass the human-initiated gate.
if (!allowAmbiguityAgent) {
  const reason = `type="${type || 'n/a'}"${labelTail} matched no routing rule and ambiguity classification is disabled → SKIP (reported, not force-fit)`
  log(`route-elaboration ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return skip(reason)
}
// Without a human initiation every kind the classifier can name ends in a skip below — an
// Epic, Story or feature waits for a person, anything else belongs to route-build or to
// triage — so its answer could change only the wording of the skip. The session is not paid
// for that.
if (!humanInitiated) {
  const reason = `type="${type || 'n/a'}"${labelTail} matched no routing rule, and this run is not human-initiated: whatever kind the bead turns out to be, elaborating it is a human's call and anything else is not elaboration work → SKIP (invoke /agent-teams-workforce:work-bead ${id} to proceed)`
  log(`route-elaboration ${bead.id || '(no id)'}: SKIP — ${reason}`)
  return skip(reason)
}

const classification = await settleAgent(
  `You are a READ-ONLY classifier for the agentic SDLC elaboration router. A bead could not be classified by its type/labels alone. Read its title and description and decide WHAT KIND of work item it is. You are NOT choosing a pipeline and NOT running anything — you only name the kind.

Bead ${bead.id || '(no id)'}
Declared type: ${type || '(none)'}
Labels: ${labels.length ? labels.join(', ') : '(none)'}
Parent type: ${parentType || '(none)'}
Ancestor types: ${ancestorTypes.length ? ancestorTypes.join(', ') : '(none)'}
Title: ${bead.title || '(none)'}
Description:
${bead.description || '(none)'}

The work-item kinds:
- epic    — a container for a whole PRD's worth of work, spanning repos. Holds Stories. Its work is elaboration.
- story   — a container scoped to ONE repo, corresponding to a Spec. Holds Tasks. Its work is elaboration.
- feature — requirement-shaped work that has no Epic/Story/Task structure yet.
- task    — one agent's unit of DEVELOPMENT work within ONE repo.
- bug     — a REPORT of a defect or regression in EXISTING behavior. Neither elaboration nor development work: a bug is triaged by a person into an Epic, a Task, or a closure.
- infra   — a provisioning/IaC change (CDK, AWS resources, deploy plumbing).
- other   — chore, docs-only, research spike, or too underspecified to classify.

Rules:
- Name the kind the bead actually IS. Do not pick a kind because it would let work proceed.
- If the bead is too underspecified to place, answer "other".
- "confident" false forces a SKIP.

Deliver:
- kind: one of "epic" | "story" | "feature" | "task" | "bug" | "infra" | "other".
- confident: true only if the bead clearly is that kind.
- reason: the concrete signal in the title/description that drove the decision.`,
  {
    label: 'classify:ambiguous-bead',
    phase: 'Classify',
    // A classifier over one bead's title and description. Stated rather than inherited.
    effort: 'low',
    agentType: 'agent-teams-workforce:ambiguity-detector',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['kind', 'confident', 'reason'],
      properties: {
        kind: { type: 'string', enum: ['epic', 'story', 'feature', 'task', 'bug', 'infra', 'other'] },
        confident: { type: 'boolean' },
        reason: { type: 'string' },
      },
    },
  }
)

const kind = classification && classification.kind
const confident = !!(classification && classification.confident)
const agentReason = (classification && classification.reason) || 'no reason returned'

if (!kind || kind === 'other' || !confident) {
  const reason = `ambiguity-detector could not confidently classify this bead (kind="${kind || 'none'}", confident=${confident}): ${agentReason} → SKIP (reported, not force-fit)`
  log(`route-elaboration ${bead.id || '(no id)'}: SKIP — ${reason}`)
  // A classifier that died did not rule: the skip says so, so a caller can tell it from a
  // bead that was looked at and could not be placed.
  return classification ? skip(reason) : { ...skip(reason), dispatchFailed: true, dispatchFailures: dispatchDeaths('Classify') }
}

// Re-apply the SAME rules to the classified kind. The classifier decides what the
// bead IS; the human-initiated gate stays the script's and is not negotiable by an
// agent's answer.
let final
if (kind === 'epic' || kind === 'story' || kind === 'feature') {
  const what = kind === 'feature' ? 'feature-shaped work with no hierarchy yet' : kind === 'epic' ? 'an epic' : `a ${kind}`
  // Only a human-initiated run reaches the classifier (see above).
  final = elaborate('prd-to-spec', `classified as ${what} and the run is human-initiated: ${agentReason} → prd-to-spec`)
} else if (kind === 'bug') {
  final = skip(
    `classified as a bug: ${agentReason}. A bug is a REPORTING MECHANISM and is never implemented directly — it is TRIAGED into an Epic, a Task, or a closure by a person. Neither elaboration nor development work → SKIP (no triage composite exists to dispatch)`,
  )
} else {
  final = skip(
    `classified as ${kind === 'infra' ? 'an infrastructure change' : `a ${kind}`}: ${agentReason}. That is DEVELOPMENT work, not elaboration → SKIP here. Route it through route-build.js.`,
  )
}

final.ruledBy = 'ambiguity-detector'
log(`route-elaboration ${bead.id || '(no id)'}: ${final.action.toUpperCase()}${final.composite ? ` via ${final.composite}` : ''} — ${final.reason}`)
return final
