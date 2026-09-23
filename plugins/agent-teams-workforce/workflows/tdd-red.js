export const meta = {
  name: 'tdd-red',
  description:
    'Shared-tail mini — TDD Red. Discovery is a LOOKUP that runs nothing: it reports which acceptance criteria already have a covering test, and writers are DERIVED from the contract\'s declared surfaces (unit always) rather than routed by an agent, with the test strategy inherited from the spec rather than re-ruled per task. Execution happens at Red confirmation only — the writers run what they author, and existing tests are executed just once, under a three-way verdict: red (reuse), already-satisfied (the behavior exists, nothing is authored and the phase reports up), or not-encoded (author against them). Whether the tests encode the acceptance criteria is judged once, at Gate 2a. Writes tests only — no production code.',
  phases: [{ title: 'Red', detail: 'author + confirm a failing test' }],
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
//   contract:    <bug-triage output or spec contract>,
//   feedback?:   string,     // gate feedback from a previous attempt
//   red?:        object,     // the previous Red artifact, on a re-author after a Green
//                            // escalation: its testFiles are the tests to repair in place
//   skipDiscovery?: boolean, // force fresh authoring, bypassing existing-test reuse.
//                            // Use when the tests on disk are known bad — discovery
//                            // would otherwise report them as covering the contract.
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
// ── PATH SAFETY AT THIS MINI'S OWN BOUNDARY ─────────────────────────────────
//
// The contract repo path is interpolated below into `git -C "<path>"` command text inside
// prompts that agents are told to run exactly as written, and into the prompt PROSE those
// same agents read. Inside a composite the value arrives already validated by the
// workspace step — but this mini is separately dispatchable, and a contract handed
// straight to it has been through no workspace step at all. Then the unvalidated value is
// back, in the phases that WRITE CODE and DEPLOY.
//
// This is the argument 6.0.8 used to justify re-validating inside settle rather than
// trusting the composite, applied where it was left out. A guard that only exists on the
// composite path is a guard on one of the two ways in.
//
// The rule matches the workspace step's: an ALLOWLIST, not a blocklist of shell
// metacharacters. The target is a model reading a prompt as well as a shell parsing a
// line, and a path made only of permitted characters can still be a sentence addressed to
// the reader. No spaces and no colons — a worktree path this pipeline creates needs
// neither, and prose needs both. REFUSE, never sanitize: a rewritten path names a
// different tree and nobody would learn of the substitution.
//
// An ABSENT path is not a fault. It has always meant "no tree was established", the
// placeholder below is not attacker-controlled, and turning that into a refusal would
// change what this mini does rather than what it accepts.
const CONTRACT_PATH_SHAPE = /^\/[A-Za-z0-9._/-]+$/
const suppliedRepoPath = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim()
const contractPathFault = (() => {
  if (!suppliedRepoPath) return null
  if (!CONTRACT_PATH_SHAPE.test(suppliedRepoPath)) {
    const offending = Array.from(suppliedRepoPath).find((ch) => !/[A-Za-z0-9._/-]/.test(ch))
    return (
      `the contract repoPath ${JSON.stringify(suppliedRepoPath)} ` +
      (suppliedRepoPath.startsWith('/')
        ? `contains ${JSON.stringify(offending)}, which either reshapes the commands an agent is told to run verbatim or lets the path be read as a sentence addressed to that agent`
        : 'is not absolute, and every command in this phase runs as `git -C "<path>"`, which resolves a relative path against whatever tree the agent is standing in')
    )
  }
  if (suppliedRepoPath.includes('//') || suppliedRepoPath.endsWith('/')) {
    return `the contract repoPath ${JSON.stringify(suppliedRepoPath)} has an empty or trailing path segment; it is refused rather than normalized`
  }
  if (suppliedRepoPath.split('/').includes('..')) {
    return `the contract repoPath ${JSON.stringify(suppliedRepoPath)} contains a ".." segment, so the directory it names is not the directory it reads as`
  }
  return null
})()
if (contractPathFault) {
  // A refused path is refused again on every retry, so the gate is not run on it.
  return {
    ok: false,
    phaseBlocked: true,
    blockedReason: `${contractPathFault}.`,
    testFiles: [],
    redConfirmed: false,
    evidence: '',
    greenReachable: false,
    greenPathChecked: false,
    greenPathFindings: [],
    writers: [],
    surfaces: [],
    blocked: [
      `${contractPathFault}. This phase refuses the contract rather than dispatching it: the path would ` +
        'already be inside the prompt by the time anyone could object.',
    ],
    ledger: { phase: 'red', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'refused', ok: false },
  }
}

const repo = suppliedRepoPath || '(repo path not provided)'
const ac = Array.isArray(c.acceptanceCriteria) ? c.acceptanceCriteria : []
const affectedFiles = Array.isArray(c.affectedFiles) ? c.affectedFiles.filter(Boolean).map(String) : []

// The gate's objection must reach EVERY step that can decide to reuse a test, not just
// the writers. It previously reached only the writer prompt — so on a loop attempt the
// discovery step re-found the previous attempt's bad test, reported no gaps, and the
// confirm-existing branch handed the gate back the identical un-passable test through a
// code path the objection never touched.
const feedbackBlock = a.feedback
  ? `\n\nA GATE REJECTED THE PREVIOUS ATTEMPT AT THIS PHASE. Read this before deciding anything is already covered — a test the gate has objected to is NOT covering test, however well it matches by name:\n${a.feedback}`
  : ''
// On a re-author the previous Red's test files are on disk and are what gets repaired; a
// writer that cannot see them authors a parallel file beside the defective one.
const priorTestFiles = a.red && Array.isArray(a.red.testFiles) ? a.red.testFiles.map((f) => String(f || '').trim()).filter(Boolean) : []
const priorTestsBlock = priorTestFiles.length
  ? `\n\nTHE PREVIOUS RED ATTEMPT AUTHORED THESE TEST FILES. They are the tests to repair — edit them in place; do not create a parallel file:\n${priorTestFiles.join('\n')}`
  : ''

phase('Red')

// ── A DEAD AGENT IS NOT A VERDICT ──────────────────────────────────────────────
//
// `agent()` returns null for exactly two reasons, and NEITHER of them is "the agent
// looked at the work and the answer is no": the user skipped it, or the subagent died
// on a terminal API error after the runtime's own retries — the session wall, most of
// the time. Every consumer below used to fold that null in with a real answer:
// `.filter(Boolean)` dropped the dead writers, `redConfirmed` was then computed over
// whoever survived, and the phase reported `redConfirmed:false` — a QUALITY verdict on
// work that was never performed.
//
// The cost of that conflation is the whole of Gate 2a's record. The gate's deterministic
// checks (Red confirmed / failing-output evidence / green-reachable) cannot be met by an
// artifact nobody produced, so the gate loops, re-dispatches into the same wall, fails
// the same three checks, exhausts its budget, and — because those are MEASURED checks,
// which the advantage-evaluator is correctly forbidden to rule competitive — fails the
// run. The supervisor then reads a work failure at stage 'red', charges the bead, and
// after three of them quarantines it. Every bug-fix run on record (6 of 6) died there.
//
// So a dead dispatch is recorded as itself and reported as itself. The composite turns
// it into an ENVIRONMENT-stage handback, which spends no gate budget, blames no bead,
// and leaves the work dispatchable once the wall is down.
//
// ONLY A DEAD WRITER FAILS THE PHASE, and the asymmetry is deliberate. `redConfirmed`
// is computed FROM the writers, so a writer that never ran makes the verdict a verdict
// on work that is partly absent. The two auxiliary dispatches — discovery and the
// existing-test confirmation — each degrade CONSERVATIVELY when
// they die: the phase authors more and claims less. Failing the run on one of those
// would throw away a Red the writers genuinely obtained, which is the same class of
// false rejection this change exists to remove. They are recorded and reported; they
// do not stop anything.
const deadAgents = []
const noteDead = (who) => {
  deadAgents.push(who)
  log(`⚠ Red: '${who}' returned nothing — it was skipped or died on a terminal API error. This is a DISPATCH failure, not a verdict.`)
}

// ── ACCEPTANCE CRITERIA ARRIVE IN TWO SHAPES, AND BOTH ARE CONTRACTS ──────────
//
// bug-triage AUTHORS `{ given, when, then }` objects, so the bug route carries fields.
// The spec route does not: a Task's criteria are FLATTENED PROSE ("Given … When … Then …")
// taken off the bead, because that is how the spec's criteria document states them, and
// splitting one sentence back into three fields would invent structure the spec never
// wrote. Rendering the object form against prose printed "GIVEN undefined WHEN undefined
// THEN undefined" — every criterion on the Task route erased at the exact point the test
// writers read it. Both shapes render as themselves; neither is reformatted into the other.
const acLine = (x, i) => {
  if (typeof x === 'string') return `${i + 1}. ${x.trim()}`
  if (x && typeof x === 'object' && (x.given || x.when || x.then)) {
    return `${i + 1}. GIVEN ${x.given || 'n/a'} WHEN ${x.when || 'n/a'} THEN ${x.then || 'n/a'}`
  }
  return `${i + 1}. ${JSON.stringify(x)}`
}
const acList = (empty) => (ac.length ? ac.map(acLine).join('\n') : empty)

// The bug route is the one that has a reproduction and a root cause; the Task route has a
// SPEC instead, and used to render neither — the prompt carried the title and nothing else,
// so the writers authored against a one-line summary of work the spec describes in full.
const isBugContract = !!(c.reproduction || c.rootCause)
const beadDescription = c.bead && typeof c.bead.description === 'string' ? c.bead.description.trim() : ''
const specBlock = (() => {
  const s = c.spec && typeof c.spec === 'object' ? c.spec : null
  if (!s) return ''
  const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '')
  const list = (v) => (Array.isArray(v) ? v.filter((x) => str(x)).map((x) => x.trim()) : [])
  const docs = [...new Set([str(s.specPath), ...list(s.specPaths)].filter(Boolean))]
  const decisionIds = [...new Set([...list(c.decisionIds), ...list(s.decisionIds)])]
  const lines = [
    str(s.id) || str(s.title) ? `Spec ${str(s.id)}${str(s.title) ? `: ${str(s.title)}` : ''}` : '',
    docs.length
      ? `Spec documents — THE CONTRACT. Read the sections named below in these files; this prompt is a pointer to them, not a substitute for them:\n${docs.map((d) => `  - ${d}`).join('\n')}`
      : '',
    list(s.specSections).length ? `Spec sections defining this work: ${list(s.specSections).join(', ')}` : '',
    list(s.requirementIds).length ? `Requirements satisfied: ${list(s.requirementIds).join(', ')}` : '',
    decisionIds.length ? `Architecture decisions this work is designed against (SAD entry ids, cited by the spec documents): ${decisionIds.join(', ')}` : '',
    list(s.definitionOfDone).length ? `Definition of Done:\n${list(s.definitionOfDone).map((d) => `  - ${d}`).join('\n')}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const taskBlock = `${c.bead ? `${isBugContract ? 'Bug' : 'Task'} ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature under test'}${
  beadDescription ? `\n\n${beadDescription}` : ''
}${isBugContract ? `\n\nReproduction: ${c.reproduction || 'n/a'}\nRoot cause: ${c.rootCause || 'n/a'}` : ''}${specBlock}

Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}

Acceptance criteria to encode as tests:
${acList(isBugContract ? '(none — derive minimal coverage from the reproduction)' : '(none — derive minimal coverage from the spec documents and the description above)')}`

// ── Writers: DERIVED from the contract's surfaces, not decided here ────────────
//
// Which surfaces a change touches is a semantic judgment, and it is made ONCE
// upstream by the agent that already reads the code — bug-triage's diagnostician,
// or spec authoring. It is not re-made here: a per-task routing turn cost a full
// subagent round-trip to answer a question the contract already answers, and for
// unit-only work the answer was fixed in advance anyway, since the unit generator
// is force-included regardless of what came back.
//
// The mapping below is a lookup, not a guess. Each surface is an upstream-declared
// enum value, so no keyword matching is inferring meaning from file paths here.
const SURFACE_WRITERS = {
  'api-contract': 'consumer-driven-contract-test-writer',
  'event-chain': 'aws-integration-test-writer',
  auth: 'security-test-case-designer',
  performance: 'performance-benchmark-writer',
  'web-ui': 'playwright-e2e-web-test-writer',
  ios: 'xcuitest-writer',
  android: 'espresso-test-writer',
  'cross-platform-mobile': 'mobile-e2e-test-writer',
  ml: 'ml-evaluation-tester',
  'data-pipeline': 'data-pipeline-test-writer',
}
const surfaces = (Array.isArray(c.surfaces) ? c.surfaces : []).map((s) => String(s || '').trim().toLowerCase())
const surfaceWriters = surfaces.map((s) => SURFACE_WRITERS[s]).filter(Boolean)
// Unit is unconditional: every contract has behavior to assert, whatever it touches.
const writersFinal = ['tdd-unit-test-generator', ...new Set(surfaceWriters)]
const selectionMode = surfaceWriters.length ? 'derived' : 'unit-only'
if (surfaces.length && !surfaceWriters.length) {
  log(`⚠ contract declared surfaces [${surfaces.join(', ')}] that map to no writer — authoring unit tests only`)
}
log(`Red writers (${selectionMode}): ${writersFinal.join(', ')}`)

// ── Strategy: INHERITED from the contract, never ruled per task ────────────────
//
// Pyramid shape, coverage threshold, and environment matrix are properties of the
// Story or the repository, not of one task. Ruling them per task did not just cost
// a turn — it let two tasks in the same Story inherit different thresholds, which
// is worse than not deciding at all. The decision still happens under the doctrine,
// once, where the Spec is authored; here it is only carried.
const strategy = c.testStrategy || null
const strategyBlock = strategy
  ? `\nTest strategy (inherited from the spec): pyramid=${strategy.pyramid || 'n/a'}; coverageThreshold=${strategy.coverageThreshold || 'n/a'}; envMatrix=${(strategy.envMatrix || []).join(', ') || 'n/a'}`
  : ''

// ── Discovery: is the contract ALREADY encoded? ────────────────────────────────
//
// Red is idempotent. A run that was interrupted, or re-dispatched after a gate
// loop, may find its tests already on disk from the previous attempt — they are
// real files, committed at deploy and inherited by every later run. Regenerating
// them wastes the most expensive phase in the pipeline and, worse, a second
// writer pass produces a parallel file covering the same behavior.
//
// The only decision at this point is AUTHOR or DON'T AUTHOR, and existence alone
// settles it. So this step RUNS NOTHING — it is a lookup. Whether a found test is
// actually Red is a different question, and it is answered by execution at Red
// confirmation: the writers run what they author, and the branch just below runs
// what discovery found. Executing here would re-answer, minutes early, what the
// next step answers regardless, and every first attempt would pay for it to guard
// a stale-test case that almost never fires. Deferred, the common case pays
// nothing and the rare case pays one loop.
const discovery = a.skipDiscovery === true
  ? null
  : await settleAgent(
      `Before any test is written, establish what the repository ALREADY has. This is a LOOKUP, not an evaluation.

PIN YOURSELF TO THE RIGHT TREE FIRST. You may be running in an isolation worktree, so a bare \`ls\`, \`git status\`, or relative path can inspect or write to the wrong copy of the repository entirely. Every path you read or write is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}${feedbackBlock}

Locate the test files that already encode the contract below — a previous attempt at this same work may have written them, or they may predate it. Search by the bead id, by the module under test, and by the behavior each criterion names.

COVERING THE CODE IS NOT ENCODING THE CONTRACT. A module usually has tests already; that does not mean this contract is encoded. The question is whether a test asserts the EXPECTED behavior stated in the criteria below — not whether the file under change is touched by some test. On a defect these come apart hardest: the existing tests assert the CURRENT behavior, which is the behavior being changed. Treat a criterion as covered only when an existing test would have to change for the criterion to be met.

DO NOT RUN ANYTHING. Do not invoke a test runner, a build, or a synth. Whether these tests currently pass or fail is not your question and you must not go looking — that is settled downstream by executing them. Report only what EXISTS.

List in gaps every acceptance criterion that has no covering test file. Those, and only those, will be authored.

${taskBlock}`,
      {
        label: 'red:discovery',
        phase: 'Red',
        effort: 'low',
        agentType: 'agent-teams-workforce:test-coverage-gap-reviewer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['existingTestFiles', 'gaps'],
          properties: {
            existingTestFiles: { type: 'array', items: { type: 'string' } },
            gaps: { type: 'array', items: { type: 'string' } },
            notes: { type: 'string' },
          },
        },
      }
    )

// A discovery that was ATTEMPTED and came back empty-handed is not "the repository has
// no tests" — it is "nobody looked". Reading it as the former is how a second file gets
// authored over behavior an existing suite already covers, which the comment above calls
// worse than no test at all. `skipDiscovery` is the deliberate null and is exempt.
if (a.skipDiscovery !== true && !discovery) noteDead('red:discovery (test-coverage-gap-reviewer)')
const foundFiles = (discovery && discovery.existingTestFiles) || []
const openGaps = (discovery && discovery.gaps) || []

// Every criterion already has a covering file, so there is nothing to author —
// but "it exists" is not "it is Red". THIS is where execution belongs, and it is
// the only place Red gets executed before authoring.
//
// The verdict is THREE-WAY, not a boolean, because the two non-red outcomes need
// opposite responses. Tests that pass while genuinely encoding this contract mean
// the expected behavior is ALREADY PRESENT — the defect is fixed, or was never
// real. There is no failing test to write, and sending that to the writers asks
// them to manufacture a red, which they can only do by asserting something false.
// That case ends the phase and reports upward. Only a contract that turns out NOT
// to be encoded — discovery saw neighbouring tests and over-claimed, or the
// failure is an unrelated harness break — goes on to authoring.
if (foundFiles.length && !openGaps.length) {
  const confirmation = await settleAgent(
    `Discovery reports that existing tests already encode every acceptance criterion below. RUN THEM — only these files, never the wider suite — and rule on what you observe. Run everything against this tree, as \`git -C "${repo}"\` / with paths under it; a bare command may inspect a different copy of the repository:
${repo}${feedbackBlock}

${foundFiles.join('\n')}

Return exactly one verdict:

- "red": they FAIL, and the failures are the intended product failures for the criteria below. The contract is encoded and not yet satisfied.
- "already-satisfied": they PASS, and they genuinely assert the expected behavior in the criteria below. The behavior already exists — the defect is already fixed, or was never real. Rule this ONLY when the passing assertions actually match the criteria; it stops the work.
- "not-encoded": they do NOT actually assert the expected behavior in the criteria (they cover the same module or the current behavior instead), or they fail for an unrelated reason — an import error, a missing fixture, a broken harness. Discovery over-claimed and the contract still needs authoring.

Capture the executed output verbatim as evidence; a verdict with no output is not evidence. Do NOT write or repair any test.

${taskBlock}`,
    {
      label: 'red:confirm-existing',
      phase: 'Red',
      agentType: 'agent-teams-workforce:test-coverage-gap-reviewer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'evidence'],
        properties: {
          verdict: { type: 'string', enum: ['red', 'already-satisfied', 'not-encoded'] },
          evidence: { type: 'string' },
          staleFiles: { type: 'array', items: { type: 'string' } },
        },
      },
    }
  )

  // A confirmation that DIED is not the 'not-encoded' verdict it degrades into below.
  // The degradation is still the right conservative behaviour for a malformed reply —
  // it authors rather than skips — but a dead dispatch must additionally be reported as
  // one, or the phase carries on writing tests into a wall it has already hit.
  if (!confirmation) noteDead('red:confirm-existing (test-coverage-gap-reviewer)')

  // A verdict without executed output is a claim, and a claim may not skip work.
  const evidenced = !!(confirmation && String(confirmation.evidence || '').trim())
  const verdict = evidenced ? confirmation.verdict : 'not-encoded'

  if (verdict === 'red') {
    log(`Red already satisfied by existing tests: ${foundFiles.join(', ')} — skipping the writers`)
    return {
      testFiles: foundFiles,
      redConfirmed: true,
      evidence: confirmation.evidence,
      reusedExistingTests: true,
      // These tests were not authored here, so there is no greenPath declaration to
      // check. They were EXECUTED and observed red, and a loop attempt never reaches
      // this branch (the composite sets skipDiscovery from attempt 2), so a rejected
      // test cannot be laundered back through reuse.
      greenReachable: true,
      greenPath: [],
      greenPathChecked: false,
      strategy,
      ledger: { phase: 'red', beadId: (c.bead && c.bead.id) || null, chosen: writersFinal, mode: 'reused', ok: true },
    }
  }

  if (verdict === 'already-satisfied') {
    log(`Contract ALREADY SATISFIED by passing tests: ${foundFiles.join(', ')} — no Red is obtainable and nothing is authored`)
    return {
      testFiles: foundFiles,
      redConfirmed: false,
      alreadySatisfied: true,
      greenReachable: true,
      greenPath: [],
      greenPathChecked: false,
      evidence: confirmation.evidence,
      reusedExistingTests: true,
      strategy,
      ledger: { phase: 'red', beadId: (c.bead && c.bead.id) || null, chosen: writersFinal, mode: 'already-satisfied', ok: true },
    }
  }

  log(
    'Red confirmation: existing tests do NOT encode this contract' +
      `${evidenced ? `: ${String(confirmation.evidence).slice(0, 200)}` : ' (no executed evidence returned — treated as unencoded)'}. Writers will author against them.`
  )
}
if (foundFiles.length && openGaps.length) {
  log(`Red discovery: ${foundFiles.length} existing test file(s) found; ${openGaps.length} gap(s) remain — writers will EXTEND, not replace`)
}
const gapBlock = openGaps.length
  ? `\n\nThese criteria are the ONLY ones still needing coverage — the rest are already encoded by the existing tests listed below, which you must extend rather than duplicate:\nGaps: ${openGaps.join('; ')}\nExisting test files: ${foundFiles.join(', ') || 'none'}`
  : foundFiles.length
    ? `\n\nEvery criterion already has a covering test in the files below, but they were RUN and are NOT Red — stale, wrong, or failing for an unrelated reason. Fix the coverage by extending these files; do NOT create parallel ones:\n${foundFiles.join(', ')}`
    : ''

// Each selected writer authors its tests and confirms Red — different test files, so
// they run concurrently (unlike production-code writers).
const RED_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['testFiles', 'redConfirmed', 'evidence', 'greenPath'],
  properties: {
    testFiles: { type: 'array', items: { type: 'string' } },
    redConfirmed: { type: 'boolean' },
    evidence: { type: 'string' },
    // ── THE GREEN-REACHABILITY DECLARATION ───────────────────────────────────
    // Red proves a test fails NOW. Nothing here used to ask whether a PASS is
    // reachable, so a test pinned to the PRE-FIX import path — one that can never go
    // green no matter how correct the production change is — was indistinguishable
    // from a correct Red and was certified as one. Naming the production file and
    // symbol whose change makes each test pass turns that into a set comparison the
    // script can settle with no model turn.
    greenPath: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['testFile', 'targetFile', 'targetSymbol', 'assertionSubject'],
        properties: {
          testFile: { type: 'string' },
          targetFile: { type: 'string' },
          targetSymbol: { type: 'string' },
          assertionSubject: { type: 'string' },
        },
      },
    },
    // ── THE UNAUTHORABLE DECLARATION ─────────────────────────────────────────
    // A writer that finds no test is obtainable for this contract had nowhere to
    // say so. Its only shape was redConfirmed:false, which is the same shape as
    // "I wrote tests and they did not fail" — an ordinary quality failure the gate
    // answers by looping. So the objection was re-dispatched, the writer restated
    // it verbatim, the budget was spent, and a MEASURED check cannot be ruled
    // competitive, so the run died. It died the same way twice, because a loop
    // cannot repair an objection that is structural rather than about the tests.
    // This field is that objection, said in a shape the script can act on.
    unauthorable: { type: 'boolean' },
    unauthorableReason: { type: 'string' },
    notes: { type: 'string' },
  },
}
const writerResultsRaw = (await parallel(writersFinal.map((w) => () =>
  settleAgent(
    `Write the failing test(s) that encode the expected behavior below, then RUN them and confirm they FAIL for the intended reason (Red). Write test code ONLY — do not change production code. You are '${w}' — author only the tests of your specialty.

PIN YOURSELF TO THE RIGHT TREE FIRST. You may be running in an isolation worktree, so a bare \`git status\`, a relative path, or an editor's idea of the project root can inspect — or WRITE TO — the wrong copy of the repository. Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

FIND THE EXISTING SUITE BEFORE YOU WRITE. These tests are permanent: they are committed and every later run inherits them. Locate the file that already covers this module or behavior and ADD to it, matching its imports, fixtures, naming, and helpers. Create a new file only when nothing covers this area yet.

ASSERT AGAINST WHAT THE CODE PRODUCES, NOT A COMMITTED ARTIFACT. Synthesize, build, or render the thing under test as part of the test run. A test that reads a checked-in build output — a committed cdk.out template, a generated client, a snapshot nobody regenerates — passes forever no matter what the code does, and it will not fail when the defect returns. If half a suite synthesizes in process and half reads a committed file, the two halves are testing different artifacts and the suite is lying about what it covers.

A second file covering the same behavior is worse than no test at all — the suite gets slower, and a failure no longer tells anyone which expectation is the real one. If you find an existing test that is WRONG rather than missing, say so in your evidence and leave it alone; repairing it is not yours to do.

${taskBlock}

${strategyBlock}${gapBlock}${priorTestsBlock}
${a.feedback ? `\nGate feedback from the previous attempt — address it:\n${a.feedback}` : ''}

DECLARE THE PATH TO GREEN. For every test you author, name the PRODUCTION file and symbol whose change will make it pass, and what the test actually asserts about that symbol. This is not paperwork: a test whose mock is patched at the module path the code used BEFORE the fix fails perfectly and can never go green, and this declaration is the only thing that distinguishes it from a correct Red. The targetFile must be a production file this change will actually touch${affectedFiles.length ? ` — the contract names these: ${affectedFiles.join(', ')}` : ''}. If you cannot name one, you have not written a test the fix can satisfy.

IF NO TEST IS OBTAINABLE, SAY THAT — DO NOT RETURN A BARE FAILURE. There is exactly one honest way to author nothing: set \`unauthorable\` true and state in \`unauthorableReason\` why this contract admits no failing test at all. That is a narrow claim and it stops the work, so the bar is high — it means the contract names no software behavior a test could assert (a manual or console-only operation, an account or data cleanup, a decision still owed by a human), or the repository's own rules forbid a test in the only place the change could land. It does NOT mean the work is awkward, the fixtures are missing, the module is untested today, or you would rather not. If you can name any production symbol whose behavior this contract changes, a test is obtainable and you must write it.

Returning \`redConfirmed\` false with prose explaining that you were blocked is NOT this declaration and never has been: that shape is read as "the tests I wrote did not fail", it is sent back for rework, and you will be asked the same question again with nothing changed.

Deliver: the test file paths you created/modified, whether Red is confirmed, the greenPath declaration, and the captured failing output as evidence.`,
    {
      label: `red:${w}`,
      phase: 'Red',
      agentType: `agent-teams-workforce:${w}`,
      schema: RED_SCHEMA,
    }
  )
)))

// ANY dead writer poisons the phase, not just all of them. Two of three writers
// returning real work and the third dying yields a `redConfirmed` computed over
// two-thirds of the contract — a verdict on partial work, presented as a verdict on
// the whole. The surviving writers' output is still returned (it is real, and a resume
// can reuse the files on disk), but the phase reports that it did not complete.
const deadWriters = writersFinal.filter((_w, i) => !writerResultsRaw[i])
for (const w of deadWriters) noteDead(`red:${w}`)
const writerResults = writerResultsRaw.filter(Boolean)

const testFiles = writerResults.flatMap((r) => (r && r.testFiles) || [])
// Red is judged over the writers that AUTHORED something. A surface writer with nothing of
// its specialty to add (a web-ui writer whose gap the unit tests already cover) returns no
// file and redConfirmed:false; counting that as "the tests did not fail" failed a genuine
// Red, and every retry re-asked the same writer the same question.
const authoringWriters = writerResults.filter((r) => r && Array.isArray(r.testFiles) && r.testFiles.length)
const redConfirmed = authoringWriters.length > 0 && authoringWriters.every((r) => r.redConfirmed === true)
const evidence = writerResults.map((r) => r && r.evidence).filter(Boolean).join('\n---\n')

// ── A CONTRACT THAT ADMITS NO TEST IS NOT A FAILED PHASE ──────────────────────
//
// Every writer ran, none died, none authored a file, and each of them independently
// reported the same structural objection: this contract names no behavior a failing
// test could assert. Looping that is futile by construction — the re-dispatch asks
// the identical question of the identical contract and gets the identical answer,
// which is exactly what happened twice on a Cognito account-cleanup item that has no
// code deliverable at all. Two rounds of the gate, both unmet on the same measured
// check, and a measured check cannot be ruled competitive, so the run died having
// judged nothing.
//
// So this is reported UP rather than round again. It is deliberately not
// `alreadySatisfied`: nothing here claims the behavior exists, and the phase does not
// pass. It is not `dispatchFailed` either — the agents worked fine; the contract is
// the problem, and the answer is a human re-scoping or re-routing the item, not a
// retry.
//
// The bar is narrow on purpose, so it cannot become the cheap way out of writing a
// test: every writer must say it, none may have authored a file, and each must give a
// reason. One writer authoring anything, or one declining to make the claim, and this
// is an ordinary Red failure the gate should judge normally.
const unauthorableWriters = writerResults.filter(
  (r) => r && r.unauthorable === true && String(r.unauthorableReason || '').trim()
)
if (
  !deadWriters.length &&
  writerResults.length > 0 &&
  !testFiles.length &&
  unauthorableWriters.length === writerResults.length
) {
  // No writer died, so writerResults is index-aligned with writersFinal and each
  // reason can be attributed to the writer that raised it.
  const reasons = writerResults.map((r, i) => `${writersFinal[i] || 'writer'}: ${String(r.unauthorableReason).trim()}`)
  const blockedReason =
    `every Red writer reports this contract admits no failing test and authored none — ${reasons.join(' | ')}. ` +
    'This is a property of the contract, not of the tests, so re-dispatching the phase would return the same answer; ' +
    'it needs a human to re-scope or re-route the work item.'
  log(`Red BLOCKED: ${blockedReason}`)
  return {
    ok: false,
    phaseBlocked: true,
    blockedReason,
    unauthorableReasons: reasons,
    testFiles: [],
    redConfirmed: false,
    evidence,
    greenPath: [],
    greenReachable: false,
    greenPathChecked: false,
    greenPathFindings: [],
    ...(deadAgents.length ? { dispatchFailures: deadAgents } : {}),
    writers: writersFinal,
    surfaces,
    strategy,
    ledger: {
      phase: 'red',
      beadId: (c.bead && c.bead.id) || null,
      chosen: writersFinal,
      mode: selectionMode,
      ok: false,
      blocked: 'contract-unauthorable',
      ...(deadAgents.length ? { dispatchFailures: deadAgents } : {}),
    },
  }
}

// ── Green reachability, settled in script ─────────────────────────────────────
//
// Zero model turns. Two tiers, and which one applies depends on whether the contract
// declared the files the fix must change:
//   • affectedFiles declared (the bug path — bug-triage always supplies them): every
//     targetFile must resolve to one of them. A mock patched at the pre-fix module path
//     names a file the fix does not touch, and dies here.
//   • affectedFiles absent: the declaration itself is still required — every authored
//     test file must name a production file and symbol whose change makes it pass. A
//     writer that cannot name one has not written a test the fix can satisfy.
const greenPath = writerResults.flatMap((r) => (r && Array.isArray(r.greenPath) ? r.greenPath : []))
function normPath(p) {
  return String(p || '').trim().replace(/^\.\//, '').replace(/^\/+/, '')
}
function sameFile(x, y) {
  const nx = normPath(x)
  const ny = normPath(y)
  if (!nx || !ny) return false
  return nx === ny || nx.endsWith(`/${ny}`) || ny.endsWith(`/${nx}`)
}
const greenPathFindings = []
for (const entry of greenPath) {
  if (!String(entry.targetFile || '').trim() || !String(entry.targetSymbol || '').trim()) {
    greenPathFindings.push(`${entry.testFile || '(unnamed test)'}: named no production file/symbol whose change makes it pass`)
    continue
  }
  if (affectedFiles.length && !affectedFiles.some((f) => sameFile(f, entry.targetFile))) {
    greenPathFindings.push(
      `${entry.testFile || '(unnamed test)'}: targets ${entry.targetFile} (${entry.targetSymbol}), which the contract does not list among the files the fix changes (${affectedFiles.join(', ')}). A test pinned to a path the fix does not touch cannot go green.`
    )
  }
}
// Matched the way targetFile is: writers report testFiles absolute and greenPath entries
// repo-relative (or the reverse), and an exact comparison failed every such Red.
for (const f of [...new Set(testFiles)]) {
  if (!greenPath.some((e) => sameFile(e.testFile, f))) greenPathFindings.push(`${f}: no greenPath entry — the test declares no route to green`)
}
const greenReachable = redConfirmed && greenPathFindings.length === 0
if (greenPathFindings.length) {
  log(`⚠ Red: ${greenPathFindings.length} test(s) declare no reachable path to green — ${greenPathFindings.join(' | ')}`)
}

// test-design-lead and test-strategy-decider no longer run here: writers are
// derived from the contract's declared surfaces and the strategy is inherited
// from the spec, so neither is a choice this phase makes.
const ledger = {
  phase: 'red',
  beadId: (c.bead && c.bead.id) || null,
  chosen: writersFinal,
  mode: selectionMode,
  ok: redConfirmed && !deadWriters.length,
  ...(deadAgents.length ? { dispatchFailures: deadAgents } : {}),
}

// The phase did not complete. Everything real it managed to produce is still returned —
// the caller records it and a resume reuses the files on disk — but `dispatchFailed`
// says the missing half is missing because a dispatch died, so no gate spends its
// budget adjudicating it and no bead is charged for it.
if (deadWriters.length) {
  return {
    ok: false,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Red'),
    reason:
      `${deadWriters.length} of ${writersFinal.length} Red test writer(s) returned nothing — ${deadAgents.join(', ')}. ` +
      'They were skipped or died on a terminal API error, so this phase never ran to a verdict. ' +
      'Nothing here is a judgement about the tests or the contract.',
    testFiles,
    redConfirmed: false,
    evidence,
    greenPath,
    greenReachable: false,
    greenPathChecked: true,
    greenPathFindings,
    writers: writersFinal,
    surfaces,
    strategy,
    ledger,
  }
}

// What a retry must fix, in words. The gate's check feedback names only the boolean that
// failed, and a writer re-dispatched on "greenReachable = false" cannot tell which test lacks
// its path to green.
const failureReason = [
  !authoringWriters.length ? 'no writer authored a test file' : '',
  authoringWriters.length && !redConfirmed
    ? `not Red: ${authoringWriters.filter((r) => r.redConfirmed !== true).flatMap((r) => r.testFiles).join(', ')} did not fail as intended`
    : '',
  ...greenPathFindings,
].filter(Boolean)

return {
  testFiles,
  redConfirmed,
  evidence,
  greenPath,
  greenReachable,
  greenPathChecked: true,
  greenPathFindings,
  ...(failureReason.length ? { reason: failureReason.join(' | ') } : {}),
  // Auxiliary dispatches that died without stopping the phase. Carried so the gate's
  // reader can tell "discovery found nothing" from "discovery never ran", which are the
  // same empty array otherwise.
  ...(deadAgents.length ? { dispatchFailures: deadAgents } : {}),
  writers: writersFinal,
  surfaces,
  strategy,
  ledger,
}
