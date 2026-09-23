export const meta = {
  name: 'documentation',
  description:
    'Cross-cutting mini — Documentation. Runs alongside the build (not as a phase): ONE read-only auditor names which docs the change leaves stale AND which writer owns each (it authors no documentation, so naming the writer is not judging its own work), and the writers author in parallel. No routing session sits between the audit and the writers — an unusable or absent assignment falls back to a deterministic path-based mapping. The docs are written into the worktree before the deploy, so Settle lands them with the code.',
  phases: [{ title: 'Documentation', detail: 'currency audit + assigned writes' }],
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

// args: { contract, green }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
// Agents start in the session's working directory, not in this repository, and many of the
// agents this phase dispatches run in an isolation worktree of that other repository. So every
// prompt pins the tree by absolute path rather than saying "work within" it.
const pinTree = `PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in — you may be running in an isolation worktree of a different one — so a relative path, a bare \`git\` command or an unqualified test run reads, edits or runs the WRONG copy. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}`
const changeLabel = c.bead ? `${c.bead.id || ''} ${c.bead.title || ''}`.trim() : 'feature'
const changedFiles = (green.changedFiles || []).join(', ') || 'n/a'

phase('Documentation')

// ── A CHANGE THAT CANNOT STALE A DOCUMENT DOES NOT NEED AN AUDITOR ────────────
//
// The auditor is already the cheap path — it runs first and dispatches writers only
// when something is genuinely stale. But it ran on EVERY build of all three composites,
// including changes that cannot make a document stale no matter what they contain: a
// test-only change, or a change confined to fixtures. Nothing user-facing, no public
// interface, no behavior a README or a changelog describes.
//
// Only that narrow, provable case skips. A source change still gets the auditor even
// when it touches no doc — deciding whether it stales one is exactly the auditor's job,
// and this must not become a heuristic that quietly stops documenting real work.
// Unknown changed files mean unknown, not empty, and the auditor runs.
const DOC_INERT_RE = /(^|\/)(tests?|spec|__tests__|__mocks__|fixtures)\//i
const changedList = (green.changedFiles || []).filter(Boolean)
if (changedList.length && changedList.every((f) => DOC_INERT_RE.test(f))) {
  log(`Documentation: change is confined to tests and fixtures (${changedList.length} files) — nothing it could stale; skipping the audit`)
  return {
    docsCurrent: true,
    audit: null,
    update: null,
    alreadySatisfied: true,
    reason: 'every changed file is a test or fixture, which no README, API reference, changelog or user guide describes',
    ledger: { phase: 'documentation', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'no-documentable-change', ok: true },
  }
}

// The four Documentation writers. Each owns one doc kind; sending a stale doc to the
// matching writer keeps authorship inside the writer's specialty.
const WRITERS = [
  'api-documentation-writer',
  'readme-writer',
  'changelog-writer',
  'user-guide-writer',
]

// Audit currency first (read-only) — only dispatch writers if something is actually stale.
//
// ── THE AUDITOR NAMES THE WRITER; NO ROUTER SESSION SITS BETWEEN ───────────────
//
// This used to be two sessions: `docs:audit` returned `staleDocs` — the documents and
// WHY each was stale — and `docs:route` then spent a whole documentation-lead session
// mapping those same strings onto four fixed names from an enum. The auditor has
// already read the change and the docs; the second session added no information, only
// a session-start, on every build run of all three composites.
//
// Segregation of duties is untouched: the auditor AUTHORS NO DOCUMENTATION, so naming
// which writer owns a stale doc is not judging its own work.
const audit = await settleAgent(
  `Audit whether this change leaves documentation stale (READMEs, API docs, changelog, user guides). READ-ONLY — you write no documentation. List exactly which docs need updating and why.

${pinTree}

Then ASSIGN each stale doc to the writer that owns its kind, drawn ONLY from this roster:
- api-documentation-writer — API reference / OpenAPI / GraphQL docs
- readme-writer — setup, onboarding, repo README, or a new repo
- changelog-writer — version bump / changelog entry derived from commits
- user-guide-writer — user-facing feature guide or walkthrough

Use the FEWEST writers that cover the stale docs, list the stale docs assigned to each, and assign no writer whose kind nothing changed. Assigning a writer is not a judgment on any work — you author none of it.

Change: ${changeLabel}
Changed files: ${changedFiles}`,
  {
    label: 'docs:audit',
    phase: 'Documentation',
    agentType: 'agent-teams-workforce:documentation-currency-auditor',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['docsCurrent', 'staleDocs'],
      properties: {
        docsCurrent: { type: 'boolean' },
        staleDocs: { type: 'array', items: { type: 'string' } },
        assignments: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['writer', 'docs'],
            properties: {
              writer: { type: 'string', enum: WRITERS },
              docs: { type: 'array', items: { type: 'string' } },
            },
          },
        },
      },
    },
  }
)

const staleDocs = (audit && Array.isArray(audit.staleDocs) ? audit.staleDocs : []).filter(Boolean)
const needsWork = !!(audit && !audit.docsCurrent && staleDocs.length)

// Deterministic fallback mapping, used when the auditor assigned nothing usable. It is
// a lookup over the doc PATH, not a guess about meaning: these four filename shapes are
// what the four writer specialties are defined against.
const writerForPath = (docPath) => {
  const p = String(docPath || '')
  if (/(^|\/)changelog(\.[a-z]+)?$/i.test(p) || /changelog/i.test(p)) return 'changelog-writer'
  if (/(^|\/)readme(\.[a-z]+)?$/i.test(p) || /readme/i.test(p)) return 'readme-writer'
  if (/openapi|swagger|(^|\/)api(\/|\.|-|_)|\/api-reference/i.test(p)) return 'api-documentation-writer'
  return 'user-guide-writer'
}

let writerResults = []
let selectionMode = 'default'
let writersChosen = []

if (needsWork) {
  // Normalize the auditor's assignments: keep only valid roster writers, each doc with the
  // FIRST writer it was given to. The writers run in parallel in one tree, so a doc handed
  // to two of them is two concurrent edits of one file.
  const assigned = new Set()
  const validAssignments = []
  for (const x of audit && Array.isArray(audit.assignments) ? audit.assignments : []) {
    if (!x || !WRITERS.includes(x.writer) || !Array.isArray(x.docs)) continue
    const docs = [...new Set(x.docs.filter(Boolean))].filter((doc) => !assigned.has(doc))
    for (const doc of docs) assigned.add(doc)
    if (!docs.length) continue
    const existing = validAssignments.find((v) => v.writer === x.writer)
    if (existing) existing.docs.push(...docs)
    else validAssignments.push({ writer: x.writer, docs })
  }

  // Every stale doc must reach a writer. An assignment set that covers only some of them
  // is not a reason to drop the rest — the auditor said they were stale, and the audit is
  // what `docsCurrent` is computed against below.
  const unassigned = [...new Set(staleDocs)].filter((doc) => !assigned.has(doc))
  if (unassigned.length) {
    // Map the leftovers deterministically by path rather than paying a session to route
    // them. Merge into an existing assignment where the writer already has work.
    for (const doc of unassigned) {
      const writer = writerForPath(doc)
      const existing = validAssignments.find((x) => x.writer === writer)
      if (existing) existing.docs.push(doc)
      else validAssignments.push({ writer, docs: [doc] })
    }
    log(
      `${unassigned.length} stale doc(s) the audit did not assign were mapped by path: ` +
        unassigned.map((doc) => `${doc} -> ${writerForPath(doc)}`).join('; ')
    )
  }

  selectionMode = audit && Array.isArray(audit.assignments) && audit.assignments.length ? 'assigned' : 'derived'
  writersChosen = validAssignments.map((x) => x.writer)

  const WRITE_SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['updatedDocs'],
    properties: {
      updatedDocs: { type: 'array', items: { type: 'string' } },
      notes: { type: 'string' },
    },
  }

  // Run the selected writers in PARALLEL — different doc kinds are different files,
  // so there is no write contention between them.
  writerResults = (await parallel(
    validAssignments.map((asg) => () =>
      settleAgent(
        `Update the stale documentation assigned to you so it matches shipped behavior. Author only the docs in your assignment; other writers own the rest.

${pinTree}

Change: ${changeLabel}
Changed files: ${changedFiles}
Docs assigned to you: ${asg.docs.join(', ')}`,
        {
          label: `docs:write:${asg.writer}`,
          phase: 'Documentation',
          agentType: `agent-teams-workforce:${asg.writer}`,
          schema: WRITE_SCHEMA,
        }
      )
    )
  )).filter(Boolean)
}

// Aggregate writer output: the union of updated docs plus per-writer notes.
const allUpdatedDocs = []
for (const r of writerResults) {
  if (r && Array.isArray(r.updatedDocs)) allUpdatedDocs.push(...r.updatedDocs)
}
const update = needsWork ? { updatedDocs: allUpdatedDocs, writers: writerResults } : null

// Docs are current if the audit found them current, or every assigned writer returned.
const docsCurrent = !!(audit && (audit.docsCurrent || (needsWork && writerResults.length === writersChosen.length)))

// Decision ledger — what this phase actually did, for over-time mining.
// chosen = [currency-auditor, ...selected writers].
// mode 'assigned' = the auditor named the writers; 'derived' = it named none and the
// script mapped every stale doc by path; 'default' = docs already current, no writers run.
const chosen = ['documentation-currency-auditor'].concat(writersChosen)

const ledger = {
  phase: 'documentation',
  beadId: (c.bead && c.bead.id) || null,
  chosen,
  mode: needsWork ? selectionMode : 'default',
  ok: !!docsCurrent,
}

return { docsCurrent, audit, update, ledger }
