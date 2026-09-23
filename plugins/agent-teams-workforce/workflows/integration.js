export const meta = {
  name: 'integration',
  description:
    'Shared-tail mini — Integration Testing. Suites are DERIVED from the surfaces the contract declares — each suite exists to exercise a boundary, so a contract declaring no cross-service, event-chain, or data-pipeline surface reports that no suite applies and the phase is skipped; an UNDECLARED surface list means unknown, not empty, and falls back to a read-only integration-testing-lead that selects them (provisioning the test environment first when one is needed). A caller may name suites outright and wins over both. The script runs the selected suites in parallel across the event chain, and on failure an independent root-cause-analyst classifies where it must escalate (code / test / environment / architecture) after the flaky-test-detector confirms intermittent failures.',
  phases: [{ title: 'Integration', detail: 'select + run suites; classify failures' }],
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

// args: { contract, green, suites?, provisionEnv?, feedback? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'

// The suites the lead may select from. Each is a Validator that reads/runs over a
// provisioned env — never writes production code — so the selected set runs concurrently.
const SUITE_AGENTS = {
  'aws-integration-test-runner':
    'the event API→EventBridge→SQS→Lambda chain — usually required for backend work',
  'event-flow-tester': 'event-driven flow, routing, retry, and DLQ behavior per hop',
  'data-consistency-checker': 'cross-store data consistency after the runs (partial writes, orphans, divergent state)',
  'cross-service-contract-tester': 'cross-service / cross-repo API and event contracts',
}

// Context every selected suite (and the lead) receives.
const changeUnderTest = c.bead ? `${c.bead.id || ''} ${c.bead.title || ''}`.trim() : 'feature'
const surfaces = `Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}
Change under test: ${changeUnderTest}`

phase('Integration')

// ── Suite selection, in precedence order: caller → surfaces → the lead ─────────
//
// Surfaces DERIVE the suite set when the contract declares them. Each integration
// suite exists to exercise a boundary; if the contract states the change crosses no
// such boundary, there is no boundary for that suite to exercise. This is a lookup
// over an upstream-declared enum, not an inference from file names.
//
// An UNDECLARED surface list (not an array) means unknown, not empty, and falls
// through to the lead exactly as before — a contract that never considered the
// question must not silently skip integration testing. A DECLARED empty list is a
// positive statement of internal-only work, and the phase reports that no suite
// applies rather than running the backend default against a change that has no
// backend surface. Callers with their own answer still pass args.suites and win
// outright; infra does exactly that.
const SURFACE_SUITES = {
  'event-chain': ['aws-integration-test-runner', 'event-flow-tester'],
  'api-contract': ['cross-service-contract-tester'],
  'data-pipeline': ['data-consistency-checker'],
}
const declaredSurfaces = Array.isArray(c.surfaces) ? c.surfaces : null

let suites
let provisionEnv = a.provisionEnv === true
let selectionMode
if (Array.isArray(a.suites) && a.suites.length) {
  suites = a.suites.filter((s) => SUITE_AGENTS[s])
  selectionMode = 'caller-specified'
} else if (declaredSurfaces) {
  suites = [...new Set(declaredSurfaces.flatMap((s) => SURFACE_SUITES[s] || []))].filter((s) => SUITE_AGENTS[s])
  selectionMode = 'derived'
  if (!suites.length) {
    log(
      `Integration: the contract declares no cross-boundary surface (${declaredSurfaces.length ? declaredSurfaces.join(', ') : 'none'}) — no integration suite applies; skipping`
    )
    return {
      suites: [],
      provisionEnv: false,
      results: [],
      passed: true,
      alreadySatisfied: true,
      reason:
        'the contract declares no cross-service, event-chain, or data-pipeline surface, so no integration suite has a boundary to exercise; unit coverage from Red/Green stands',
      ledger: { phase: 'integration', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'no-applicable-suite', ok: true },
    }
  }
  provisionEnv = true
  log(`Integration suites derived from surfaces [${declaredSurfaces.join(', ')}]: ${suites.join(', ')}`)
} else {
  // No caller answer and no declared surfaces — the READ-ONLY integration-testing-lead
  // routes. It runs no tests and writes nothing; its verdict also decides whether the
  // test environment must be provisioned or reset before the suites run.
  const menu = Object.entries(SUITE_AGENTS)
    .map(([name, why]) => `  - ${name}: ${why}`)
    .join('\n')
  const selection = await settleAgent(
    `You are the integration-testing-lead — a READ-ONLY router. Do NOT run tests or write anything. Select the FEWEST integration suites whose surfaces this change actually touches, drawn from:
${menu}

A standard backend / event-driven change almost always needs aws-integration-test-runner. Add event-flow-tester when routing/retry/DLQ behavior changes, data-consistency-checker when writes span stores, and cross-service-contract-tester when an API or event contract crosses a service or repo boundary. Also decide whether the integration test environment must be provisioned or reset before the suites run (true for any change that needs fresh event-chain or data-store state).

Work within the repository at: ${repo}

${surfaces}`,
    {
      label: 'integration:select-suites',
      effort: 'low',
      phase: 'Integration',
      agentType: 'agent-teams-workforce:integration-testing-lead',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['suites', 'provisionEnv', 'rationale'],
        properties: {
          suites: { type: 'array', items: { type: 'string' } },
          provisionEnv: { type: 'boolean' },
          rationale: { type: 'string' },
        },
      },
    }
  )
  const picked =
    selection && Array.isArray(selection.suites) ? selection.suites.filter((s) => SUITE_AGENTS[s]) : []
  suites = picked.length ? picked : ['aws-integration-test-runner']
  selectionMode = picked.length ? 'selected' : 'default'
  if (selection && typeof selection.provisionEnv === 'boolean') provisionEnv = selection.provisionEnv
}

const SUITE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['passed', 'coverageMet', 'failures'],
  properties: {
    passed: { type: 'boolean' },
    coverageMet: { type: 'boolean' },
    flaky: { type: 'array', items: { type: 'string' } },
    failures: { type: 'array', items: { type: 'string' } },
    evidence: { type: 'string' },
  },
}

// If an env must be provisioned/reset, the test-environment-orchestrator (the only
// executor on this team) runs FIRST — before any suite — so the suites read a ready env.
let envSetup = null
if (provisionEnv) {
  envSetup = await settleAgent(
    `Provision or reset the integration test environment for this change — event API, EventBridge, SQS, Lambda, and data stores — seed required fixtures, and confirm readiness. Work within: ${repo}

${surfaces}`,
    {
      label: 'integration:provision-env',
      phase: 'Integration',
      agentType: 'agent-teams-workforce:test-environment-orchestrator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['ready'],
        properties: {
          ready: { type: 'boolean' },
          evidence: { type: 'string' },
        },
      },
    }
  )
}

// Run the selected suites in PARALLEL — each reads/runs over the provisioned env, so
// concurrency is safe (unlike the sequential code-writing implementers in tdd-green).
const suiteRuns = await parallel(
  suites.map((suite) => () =>
    settleAgent(
      `Run the ${suite.replace(/-/g, ' ')} suite relevant to this change and report structured results. Verify contracts across service boundaries hold and required coverage is met. Work within: ${repo}

${surfaces}
${a.feedback ? `\nPrior feedback to address:\n${a.feedback}` : ''}

Deliver pass/fail, coverage, any flaky tests, and concrete failure details.`,
      {
        label: `integration:${suite}`,
        phase: 'Integration',
        agentType: `agent-teams-workforce:${suite}`,
        schema: SUITE_SCHEMA,
      }
    )
  )
)

// Aggregate the parallel suite results into one integration verdict.
const results = (suiteRuns || []).filter(Boolean)
const flaky = []
const failures = []
for (const r of results) {
  if (Array.isArray(r.flaky)) flaky.push(...r.flaky)
  if (Array.isArray(r.failures)) failures.push(...r.failures)
}
const passed = results.length > 0 && results.every((r) => r.passed)
const coverageMet = results.length > 0 && results.every((r) => r.coverageMet)
const evidence = results
  .map((r) => r.evidence)
  .filter(Boolean)
  .join('\n')
const run = { passed, coverageMet, flaky, failures, evidence }

// Before escalating, confirm intermittent failures are genuinely flaky via reruns. The
// flaky-test-detector is READ-ONLY — it reports verified-flaky tests, it never edits them.
let flakyVerdict = null
if (flaky.length > 0) {
  flakyVerdict = await settleAgent(
    `These tests failed intermittently during the integration runs. You are READ-ONLY — do NOT edit or disable any test. Verify via repeated controlled reruns which are genuinely flaky versus consistently failing, and report. Work within: ${repo}

Suspected-flaky tests:
${flaky.join('\n')}`,
    {
      label: 'integration:flaky-detect',
      phase: 'Integration',
      agentType: 'agent-teams-workforce:flaky-test-detector',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verifiedFlaky', 'consistentFailures'],
        properties: {
          verifiedFlaky: { type: 'array', items: { type: 'string' } },
          consistentFailures: { type: 'array', items: { type: 'string' } },
          evidence: { type: 'string' },
        },
      },
    }
  )
}

// On failure, classify root cause to drive the gate's escalate target. Verified-flaky
// tests are not real failures — only consistent failures should drive escalation.
const consistentFailures = flakyVerdict ? flakyVerdict.consistentFailures || [] : []
const hasRealFailure = !run.passed || !run.coverageMet || failures.length > 0 || consistentFailures.length > 0
let classification = null
if (hasRealFailure) {
  const failureText = failures.concat(consistentFailures).join('\n') || run.evidence || 'n/a'
  classification = await settleAgent(
    `Integration failures occurred. You are READ-ONLY. Classify the dominant root cause as exactly one of: code, test, environment, architecture — and name the phase it should escalate to. Work within: ${repo}

Failures:
${failureText}`,
    {
      label: 'integration:root-cause',
      phase: 'Integration',
      agentType: 'agent-teams-workforce:root-cause-analyst',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['class', 'escalateTo', 'rationale'],
        properties: {
          class: { type: 'string', enum: ['code', 'test', 'environment', 'architecture'] },
          escalateTo: { type: 'string' },
          rationale: { type: 'string' },
        },
      },
    }
  )
}

// Decision ledger — what this phase actually did, for over-time mining.
// chosen = selected suite runners (+ test-environment-orchestrator if provisioned)
//          (+ flaky-test-detector if intermittent failures) (+ root-cause-analyst on failure).
// mode 'selected' = the integration-testing-lead (or caller) chose the suites;
// mode 'default'  = selection produced nothing and the mini fell back to the runner default.
const chosen = (provisionEnv ? ['test-environment-orchestrator'] : [])
  .concat(suites)
  .concat(flakyVerdict ? ['flaky-test-detector'] : [])
  .concat(classification ? ['root-cause-analyst'] : [])
const ledger = {
  phase: 'integration',
  beadId: (c.bead && c.bead.id) || null,
  chosen,
  mode: selectionMode,
  ok: !!(run.passed && run.coverageMet && !hasRealFailure),
  escalateTo: classification ? classification.escalateTo : null,
}

return { ...run, envSetup, flakyVerdict, classification, ledger }
