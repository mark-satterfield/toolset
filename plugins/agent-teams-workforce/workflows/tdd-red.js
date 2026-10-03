export const meta = {
  name: 'tdd-red',
  description:
    'Shared-tail mini — TDD Red. Test writers derived from the contract surfaces (unit always) extend the existing suite, one writer after another, with failing tests that encode the acceptance criteria and confirm they fail. In update mode (testIssues given) the unit test writer rules on each existing test the implementer named — update it, delete it, or keep it — citing the contract. Writes tests only — no production code.',
  phases: [{ title: 'Red', detail: 'author failing tests, or rule on the tests the implementer named' }],
}
// BEGIN bounded dispatch policy — identical in workflow consumers (no runtime imports).
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
}
function dispatchPolicy(options) {
  const input = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  const policy = (options && options.retryPolicy) || input.retryPolicy || {}
  return { maxAttempts: Number.isInteger(policy.maxAttempts) && policy.maxAttempts > 0 ? policy.maxAttempts : 3,
    maxWaitMs: Number.isFinite(policy.maxWaitMs) && policy.maxWaitMs >= 0 ? policy.maxWaitMs : 300000 }
}
function dispatchFailureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = [e.message || err || '', e.type, e.code, e.error && e.error.type].join(' ')
  if (/structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i.test(text)) return 'deterministic'
  if (/insufficient_quota|quota|usage[ _-]?limit|spend[ _-]?limit|session[ _-]?limit|credit balance|out of credits|hit your limit|token limit|account.quota.exhausted/i.test(text)) return 'exhausted'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((value) => Number(value)).find((value) => Number.isFinite(value) && value >= 100 && value < 600)
  return [408, 425, 429, 500, 502, 503, 504, 529].includes(status) || /overload|rate[ _-]?limit|too many requests|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i.test(text) ? 'transient' : 'deterministic'
}
function dispatchRetry(err, name, attempt, waitedMs, policy, canWait) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return { retry: false, cause }
  const e = err && typeof err === 'object' ? err : {}
  const headers = e.headers || (e.response && e.response.headers) || {}
  const rawRetryAfter = e.retryAfter !== undefined ? e.retryAfter : headers['retry-after']
  const retryAfter = e.retryAfterMs !== undefined ? Number(e.retryAfterMs) : Number(rawRetryAfter) * 1000
  // An HTTP-date without a supplied clock cannot be safely shortened to our backoff.
  const unknownRetryDate = rawRetryAfter !== undefined && !Number.isFinite(retryAfter)
  let hash = 2166136261
  for (const ch of `${name}#${attempt}`) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619)
  const scheduled = Math.round(Math.min(300000, 5000 * Math.pow(3, attempt - 1)) * (0.5 + 0.5 * ((hash >>> 0) / 4294967296)))
  const wait = Math.max(scheduled, Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : 0)
  if (cause === 'transient' && !unknownRetryDate && canWait && attempt < policy.maxAttempts && waitedMs + wait <= policy.maxWaitMs) return { retry: true, cause, wait }
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  return { retry: false, cause, interruption: { stage, message: `${stage}: ${name}: ${String(e.message || err || cause)}`, attempt,
    retryAfterMs: Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : null, retryAfter: rawRetryAfter || null } }
}
async function settleWorkflow(name, input) {
  if (dispatchInterruption) return dispatchOutcome({})
  const source = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  try {
    const out = await workflow(name, { ...input, ...(source.retryPolicy && !(input && input.retryPolicy) ? { retryPolicy: source.retryPolicy } : {}) })
    if (out && out.paused && out.resumable && out.dispatchInterruption) dispatchInterruption = out.dispatchInterruption
    return out
  } catch (err) {
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(null), false)
    if (!plan.interruption) throw err
    dispatchInterruption = plan.interruption
    return dispatchOutcome({})
  }
}
// END bounded dispatch policy

function failureCause(err) { return dispatchFailureCause(err) }
async function settleAgent(prompt, opts) {
  if (dispatchInterruption) return null
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.retryPolicy
  delete call.schemaName
  delete call.rethrow
  const name = o.label || o.agentType || 'agent'
  const policy = dispatchPolicy(o)
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    if (dispatchInterruption) return null
    try {
      const out = await agent(prompt, call)
      if (out) {

        return out
      }

      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)

      if (!plan.retry) {
        if (plan.interruption) dispatchInterruption = plan.interruption
        log(name + ': stopped (' + plan.cause + ') — ' + message)
        if (o.rethrow && !plan.interruption) throw err
        return null
      }
      waitedMs += plan.wait
      log(name + ': transient failure; retry ' + (attempt + 1) + '/' + policy.maxAttempts + ' in ' + Math.round(plan.wait / 1000) + 's — ' + message.slice(0, 160))
      await new Promise((resolve) => setTimeout(resolve, plan.wait))
    }
  }
}

// args: { contract, feedback?: string, red?: { testFiles },
//         testIssues?: [{ testId, kind: 'obsolete-by-contract' | 'defect' | 'missing-config', reason, contractRef? }] }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim() || '(repo path not provided)'
const beadId = (c.bead && c.bead.id) || null
const ac = Array.isArray(c.acceptanceCriteria) ? c.acceptanceCriteria : []
const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '')
const strList = (v) => (Array.isArray(v) ? v.map((x) => str(x)).filter(Boolean) : [])

const priorTestFiles = a.red ? strList(a.red.testFiles) : []
const priorTestsBlock = priorTestFiles.length
  ? `\n\nThe previous Red attempt authored these test files. Edit them in place; do not create a parallel file:\n${priorTestFiles.join('\n')}`
  : ''

phase('Red')

const acLine = (x, i) => {
  if (typeof x === 'string') return `${i + 1}. ${x.trim()}`
  if (x && typeof x === 'object' && (x.given || x.when || x.then)) {
    return `${i + 1}. GIVEN ${x.given || 'n/a'} WHEN ${x.when || 'n/a'} THEN ${x.then || 'n/a'}`
  }
  return `${i + 1}. ${JSON.stringify(x)}`
}

const isBugContract = !!(c.reproduction || c.rootCause)
const beadDescription = c.bead ? str(c.bead.description) : ''
const specBlock = (() => {
  const s = c.spec && typeof c.spec === 'object' ? c.spec : null
  if (!s) return ''
  const docs = [...new Set([str(s.specPath), ...strList(s.specPaths)].filter(Boolean))]
  const decisionIds = [...new Set([...strList(c.decisionIds), ...strList(s.decisionIds)])]
  const lines = [
    str(s.id) || str(s.title) ? `Spec ${str(s.id)}${str(s.title) ? `: ${str(s.title)}` : ''}` : '',
    docs.length ? `Spec documents — read the sections named below in these files:\n${docs.map((d) => `  - ${d}`).join('\n')}` : '',
    strList(s.specSections).length ? `Spec sections defining this work: ${strList(s.specSections).join(', ')}` : '',
    strList(s.requirementIds).length ? `Requirements satisfied: ${strList(s.requirementIds).join(', ')}` : '',
    decisionIds.length ? `Architecture views this work is designed against (paths relative to the arc42 folder): ${decisionIds.join(', ')}` : '',
    strList(s.definitionOfDone).length ? `Definition of Done:\n${strList(s.definitionOfDone).map((d) => `  - ${d}`).join('\n')}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const infraBlock = (() => {
  const pi = c.provisioningIntent && typeof c.provisioningIntent === 'object' ? c.provisioningIntent : null
  const stacks = [...new Set([...strList(c.affectedStacks), ...strList(pi && pi.affectedStacks)])]
  const resources = pi && Array.isArray(pi.resources) ? pi.resources.filter((r) => r && typeof r === 'object') : []
  const refs = pi ? strList(pi.crossStackRefs) : []
  const lines = [
    stacks.length ? `Affected CDK stacks: ${stacks.join(', ')}` : '',
    resources.length
      ? `Provisioning intent — the resources to provision:\n${resources
          .map((r) => `  - ${str(r.logicalId) || '(resource)'} ${str(r.type)}${str(r.stack) ? ` in ${str(r.stack)}` : ''}${str(r.properties) ? `: ${str(r.properties)}` : ''}`)
          .join('\n')}`
      : '',
    refs.length ? `Cross-stack references:\n${refs.map((x) => `  - ${x}`).join('\n')}` : '',
    pi && str(pi.rationale) ? `Intent rationale: ${str(pi.rationale)}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const taskBlock = `${c.bead ? `${isBugContract ? 'Bug' : 'Task'} ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature under test'}${
  beadDescription ? `\n\n${beadDescription}` : ''
}${isBugContract ? `\n\nReproduction: ${c.reproduction || 'n/a'}\nRoot cause: ${c.rootCause || 'n/a'}` : ''}${specBlock}${infraBlock}

Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}

Unit tests mock the AWS services the code calls; no test reaches AWS. A criterion about the repository's CDK stacks is encoded as a failing \`cdk synth\` assertion test, written with the assertions library of the language the repository's CDK app is written in, in the repository's existing synth test module where there is one: it asserts the synthesized template's resources and their properties, the cross-stack references the stacks write and read, and the IAM permissions the criteria require.

Acceptance criteria to encode as tests:
${ac.length ? ac.map(acLine).join('\n') : isBugContract ? '(none — derive minimal coverage from the reproduction)' : '(none — derive minimal coverage from the spec documents and the description above)'}`

// Surface → test writer lookup; the unit writer always runs.
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

const testIssues = (Array.isArray(a.testIssues) ? a.testIssues : []).filter((x) => x && typeof x === 'object' && str(x.testId))
const updateMode = testIssues.length > 0
// Update mode rules on existing tests; the unit test writer owns the suite those tests live in.
const writersFinal = updateMode ? ['tdd-unit-test-generator'] : ['tdd-unit-test-generator', ...new Set(surfaceWriters)]
const selectionMode = updateMode ? 'update' : surfaceWriters.length ? 'derived' : 'unit-only'
log(`Red writers (${selectionMode}): ${writersFinal.join(', ')}`)

const strategy = c.testStrategy || null
const strategyBlock = strategy
  ? `\nTest strategy: pyramid=${strategy.pyramid || 'n/a'}; coverageThreshold=${strategy.coverageThreshold || 'n/a'}; envMatrix=${(strategy.envMatrix || []).join(', ') || 'n/a'}`
  : ''

const suiteCommand = str(c.suiteCommand)
const suiteBlock = suiteCommand
  ? `\n\nThe run judges the suite by running exactly \`cd "${repo}" && ${suiteCommand}\` itself. Run your tests with that command (narrowed to your files while you work), so what you see is what the run measures.`
  : ''

const turnBlock = (w) => {
  const others = writersFinal.filter((x) => x !== w)
  return others.length
    ? `\n\nOther test writers work on this tree one after another: ${others.join(', ')}. Create or edit only test files of your own kind of test (${w}); the unit test files belong to tdd-unit-test-generator.`
    : ''
}

const RED_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['testFiles', 'redConfirmed', 'evidence'],
  properties: {
    testFiles: { type: 'array', items: { type: 'string' } },
    redConfirmed: { type: 'boolean' },
    evidence: { type: 'string' },
    decisions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['testId', 'action', 'reason'],
        properties: {
          testId: { type: 'string' },
          action: { type: 'string', enum: ['update', 'delete', 'keep'] },
          reason: { type: 'string' },
        },
      },
    },
    notes: { type: 'string' },
  },
}

const issueLine = (x, i) =>
  `${i + 1}. ${str(x.testId)} (${str(x.kind) || 'unclassified'}): ${str(x.reason) || 'no reason given'}${str(x.contractRef) ? ` — contract: ${str(x.contractRef)}` : ''}`

const authorPrompt = (w) => `Write the failing test(s) that encode the expected behavior below, then RUN them and confirm they FAIL for the intended reason (Red). Write test code ONLY — do not change production code. You are '${w}' — author only the tests of your specialty.

Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

Add to the existing test file that covers this module or behavior, matching its imports, fixtures, naming and helpers; create a new file only when none covers this area. Where an existing test already encodes a criterion, keep it and do not duplicate it. Tests synthesize, build or render the thing under test during the run; they never read a committed build output.${turnBlock(w)}

${taskBlock}
${strategyBlock}${suiteBlock}${priorTestsBlock}
${a.feedback ? `\nFeedback from the previous attempt — address it:\n${a.feedback}` : ''}

Deliver: the test file paths you created or modified, whether Red is confirmed, and the captured failing output as evidence.`

const updatePrompt = (w) => `The implementer building the Task below reports that these existing tests stand between the code and the contract. It may not change tests; you own them. Rule on each one:

${testIssues.map(issueLine).join('\n')}

For each named test choose one action and cite the contract (an acceptance criterion, a spec section, or an architecture view below) in the reason:
- update — the test encodes behaviour or configuration the contract changes: rewrite it to encode what the contract states.
- delete — the test encodes behaviour the contract removes, and no criterion needs it.
- keep — the test is right under the contract; the production code must change to pass it. Say what it requires.

Change test code and nothing else: the implementer owns the production code. You are '${w}'.

Every file you modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

${taskBlock}
${suiteBlock}${priorTestsBlock}
${a.feedback ? `\nThe last suite run:\n${a.feedback}` : ''}

Deliver: one decision per named test, the test file paths you modified, the captured output of the tests you changed as evidence, and redConfirmed true when every test you updated runs and fails or passes as the contract says it should.`

// Writers run one after another: concurrent writers in one tree edited the same files.
const writerResultsRaw = []
for (const w of writersFinal) {
  writerResultsRaw.push(
    await settleAgent(updateMode ? updatePrompt(w) : authorPrompt(w), {
      label: `red:${updateMode ? 'update:' : ''}${w}`,
      phase: 'Red',
      agentType: `agent-teams-workforce:${w}`,
      schema: RED_SCHEMA,
    })
  )
}

const writerResults = writerResultsRaw.filter(Boolean)
const deadWriters = writersFinal.filter((_w, i) => !writerResultsRaw[i])
const testFiles = writerResults.flatMap((r) => (Array.isArray(r.testFiles) ? r.testFiles : []))
const authoringWriters = writerResults.filter((r) => Array.isArray(r.testFiles) && r.testFiles.length)
const redConfirmed = authoringWriters.length > 0 && authoringWriters.every((r) => r.redConfirmed === true)
const evidence = writerResults.map((r) => r.evidence).filter(Boolean).join('\n---\n')
const decisions = writerResults.flatMap((r) => (Array.isArray(r.decisions) ? r.decisions : []))

const ledger = { phase: 'red', beadId, chosen: writersFinal, mode: selectionMode, ok: updateMode ? writerResults.length > 0 : redConfirmed }

if (!writerResults.length) {
  return dispatchOutcome({
    ok: false,
    dispatchFailed: true,
    reason: `every Red test writer returned nothing: ${deadWriters.join(', ')}`,
    testFiles: [],
    redConfirmed: false,
    evidence: '',
    writers: writersFinal,
    surfaces,
    strategy,
    ledger,
  })
}

const reason = updateMode
  ? ''
  : !authoringWriters.length
    ? 'no writer authored a test file'
    : !redConfirmed
      ? `not Red: ${authoringWriters.filter((r) => r.redConfirmed !== true).flatMap((r) => r.testFiles).join(', ')} did not fail as intended`
      : ''

return dispatchOutcome({
  testFiles,
  redConfirmed,
  evidence,
  ...(updateMode ? { updateMode: true, decisions } : {}),
  ...(reason ? { reason } : {}),
  writers: writersFinal,
  surfaces,
  strategy,
  ledger,
})
