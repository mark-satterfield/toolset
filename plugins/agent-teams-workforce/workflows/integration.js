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
  let out = null
  try {
    out = await agent(prompt, call)
  } catch (err) {
    const message = String((err && err.message) || err)
    dispatchFailures.push({
      ...who,
      outcome: 'threw',
      message: message.slice(0, 300),
      transcript: settleTranscript(err, name),
      note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''}: ${message.slice(0, 160)}`,
    })
    log(`${name}: session ended without a structured result — ${message.slice(0, 160)}`)
    // A caller that owns its own failure reporting asks for the throw back, so the real
    // reason reaches its catch instead of being flattened to "returned no result".
    if (o.rethrow) throw err
    return null
  }
  if (out) return out
  dispatchFailures.push({
    ...who,
    outcome: 'skipped',
    message: null,
    transcript: settleTranscript(null, name),
    note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
  })
  log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
  return null
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
