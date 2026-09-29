export const meta = {
  name: 'tdd-red',
  description:
    'Shared-tail mini — TDD Red. Test writers derived from the contract surfaces (unit always) extend the existing suite with failing tests that encode the acceptance criteria and confirm they fail. Writes tests only — no production code.',
  phases: [{ title: 'Red', detail: 'author failing tests; confirm Red' }],
}
// settleAgent(prompt, opts): calls agent(); returns its result, or null when the agent returns nothing or fails deterministically. A transient API failure is retried with capped backoff until it clears.
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  if (TRANSIENT_ERROR_TEXT.test(text)) return 'transient'
  return 'deterministic'
}
function transientWaitMs(name, attempt) {
  const scheduled = Math.min(300000, 5000 * Math.pow(3, Math.max(0, attempt - 1)))
  let h = 2166136261
  const key = `${name}#${attempt}`
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  return Math.round(scheduled * (0.5 + 0.5 * ((h >>> 0) / 4294967296)))
}
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const name = o.label || o.agentType || 'agent'
  for (let attempt = 1; ; attempt++) {
    try {
      const out = await agent(prompt, o)
      if (!out) log(`${name}: returned nothing`)
      return out || null
    } catch (err) {
      const message = String((err && err.message) || err).slice(0, 300)
      if (failureCause(err) !== 'transient' || (!SETTLE_CAN_WAIT && attempt >= 3)) {
        log(`${name}: failed — ${message}`)
        return null
      }
      const wait = transientWaitMs(name, attempt)
      log(`${name}: transient failure on attempt ${attempt}, retrying in ${Math.round(wait / 1000)}s — ${message}`)
      if (SETTLE_CAN_WAIT) await new Promise((resolve) => setTimeout(resolve, wait))
    }
  }
}

// args: { contract, feedback?: string, red?: { testFiles } }
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
    decisionIds.length ? `Architecture decisions this work is designed against (SAD entry ids): ${decisionIds.join(', ')}` : '',
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
    refs.length ? `Cross-stack references (SSM Parameter Store, never CloudFormation exports):\n${refs.map((x) => `  - ${x}`).join('\n')}` : '',
    pi && str(pi.rationale) ? `Intent rationale: ${str(pi.rationale)}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const taskBlock = `${c.bead ? `${isBugContract ? 'Bug' : 'Task'} ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature under test'}${
  beadDescription ? `\n\n${beadDescription}` : ''
}${isBugContract ? `\n\nReproduction: ${c.reproduction || 'n/a'}\nRoot cause: ${c.rootCause || 'n/a'}` : ''}${specBlock}${infraBlock}

Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}

Unit tests mock the AWS services the code calls; no test reaches AWS. A criterion about the repository's CDK stacks is encoded as a failing \`cdk synth\` assertion test with \`aws_cdk.assertions\` (\`Template.from_stack\`), in the repository's existing synth test module where there is one: it asserts the synthesized template's resources and their properties, the SSM parameter names the stacks write and read, and the IAM permissions the criteria require.

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
const writersFinal = ['tdd-unit-test-generator', ...new Set(surfaceWriters)]
const selectionMode = surfaceWriters.length ? 'derived' : 'unit-only'
log(`Red writers (${selectionMode}): ${writersFinal.join(', ')}`)

const strategy = c.testStrategy || null
const strategyBlock = strategy
  ? `\nTest strategy: pyramid=${strategy.pyramid || 'n/a'}; coverageThreshold=${strategy.coverageThreshold || 'n/a'}; envMatrix=${(strategy.envMatrix || []).join(', ') || 'n/a'}`
  : ''

const concurrentBlock = (w) => {
  const others = writersFinal.filter((x) => x !== w)
  return others.length
    ? `\n\nOther writers are editing this tree at the same time: ${others.join(', ')}. Create or edit only test files of your own kind of test (${w}); the unit test files belong to tdd-unit-test-generator.`
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
    notes: { type: 'string' },
  },
}

const writerResultsRaw = await parallel(
  writersFinal.map((w) => () =>
    settleAgent(
      `Write the failing test(s) that encode the expected behavior below, then RUN them and confirm they FAIL for the intended reason (Red). Write test code ONLY — do not change production code. You are '${w}' — author only the tests of your specialty.

Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

Add to the existing test file that covers this module or behavior, matching its imports, fixtures, naming and helpers; create a new file only when none covers this area. Where an existing test already encodes a criterion, keep it and do not duplicate it. Tests synthesize, build or render the thing under test during the run; they never read a committed build output.${concurrentBlock(w)}

${taskBlock}
${strategyBlock}${priorTestsBlock}
${a.feedback ? `\nFeedback from the previous attempt — address it:\n${a.feedback}` : ''}

Deliver: the test file paths you created or modified, whether Red is confirmed, and the captured failing output as evidence.`,
      {
        label: `red:${w}`,
        phase: 'Red',
        agentType: `agent-teams-workforce:${w}`,
        schema: RED_SCHEMA,
      }
    )
  )
)

const writerResults = writerResultsRaw.filter(Boolean)
const deadWriters = writersFinal.filter((_w, i) => !writerResultsRaw[i])
const testFiles = writerResults.flatMap((r) => (Array.isArray(r.testFiles) ? r.testFiles : []))
const authoringWriters = writerResults.filter((r) => Array.isArray(r.testFiles) && r.testFiles.length)
const redConfirmed = authoringWriters.length > 0 && authoringWriters.every((r) => r.redConfirmed === true)
const evidence = writerResults.map((r) => r.evidence).filter(Boolean).join('\n---\n')

const ledger = { phase: 'red', beadId, chosen: writersFinal, mode: selectionMode, ok: redConfirmed }

if (!writerResults.length) {
  return {
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
  }
}

const reason = !authoringWriters.length
  ? 'no writer authored a test file'
  : !redConfirmed
    ? `not Red: ${authoringWriters.filter((r) => r.redConfirmed !== true).flatMap((r) => r.testFiles).join(', ')} did not fail as intended`
    : ''

return {
  testFiles,
  redConfirmed,
  evidence,
  ...(reason ? { reason } : {}),
  writers: writersFinal,
  surfaces,
  strategy,
  ledger,
}
