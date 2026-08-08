export const meta = {
  name: 'tdd-red',
  description:
    'Shared-tail mini — TDD Red. A read-only test-design-lead selects the test writers the contract surfaces need (unit always) and the test-strategy-decider rules the strategy; the selected writers author the failing tests concurrently and confirm they fail for the intended reason, then an independent coverage reviewer checks them against the acceptance criteria. Writes tests only — no production code.',
  phases: [{ title: 'Red', detail: 'author + confirm a failing test' }],
}

// args: { contract: <bug-triage output or spec contract>, feedback?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
const ac = Array.isArray(c.acceptanceCriteria) ? c.acceptanceCriteria : []

phase('Red')

const taskBlock = `${c.bead ? `Bug ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature under test'}
Reproduction: ${c.reproduction || 'n/a'}
Root cause: ${c.rootCause || 'n/a'}
Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}

Acceptance criteria to encode as tests:
${ac.length ? ac.map((x, i) => `${i + 1}. GIVEN ${x.given} WHEN ${x.when} THEN ${x.then}`).join('\n') : '(none — derive minimal coverage from the reproduction)'}`

// test-design-lead (READ-ONLY) selects which test writers the contract's surfaces need;
// unit is always included. It writes no tests — it routes.
const selection = await agent(
  `You are the test-design-lead — a READ-ONLY router. Do NOT write tests. Select which test writers this work needs based on the surfaces in the contract below. ALWAYS include tdd-unit-test-generator. Add ONLY those that match a real surface: consumer-driven-contract-test-writer (API/event contracts), aws-integration-test-writer (event API→EventBridge→SQS→Lambda chain), security-test-case-designer (auth/authz/abuse surface), performance-benchmark-writer (stated performance NFRs), playwright-e2e-web-test-writer (web UI), xcuitest-writer (iOS), espresso-test-writer (Android), mobile-e2e-test-writer (React Native / cross-platform), ml-evaluation-tester (ML/matching/recommendation), data-pipeline-test-writer (ETL/CDC/data pipeline). Return the chosen writer agent names.

Work within the repository at: ${repo}

${taskBlock}`,
  {
    label: 'red:select-writers',
    phase: 'Red',
    agentType: 'agent-teams-workforce:test-design-lead',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['writers'],
      properties: {
        writers: { type: 'array', items: { type: 'string' } },
        rationale: { type: 'string' },
      },
    },
  }
)
const picked = selection && Array.isArray(selection.writers) ? selection.writers.filter(Boolean) : []
const writers = picked.includes('tdd-unit-test-generator') ? picked : ['tdd-unit-test-generator', ...picked]
const writersFinal = writers.length ? writers : ['tdd-unit-test-generator']
const selectionMode = picked.length ? 'selected' : 'default'

// test-strategy-decider RULES the strategy (pyramid shape, coverage threshold, env
// matrix) that frames how the writers author — a decision, not analysis or authoring.
const strategy = await agent(
  `You are the test-strategy-decider. Rule the test strategy for this work: pyramid shape (unit/integration/e2e balance), coverage threshold, and the environment matrix needed. You ONLY rule — do not author tests. Selected test writers: ${writersFinal.join(', ')}.

${taskBlock}`,
  {
    label: 'red:strategy',
    phase: 'Red',
    agentType: 'agent-teams-workforce:test-strategy-decider',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['pyramid', 'coverageThreshold'],
      properties: {
        pyramid: { type: 'string' },
        coverageThreshold: { type: 'string' },
        envMatrix: { type: 'array', items: { type: 'string' } },
        rationale: { type: 'string' },
      },
    },
  }
)
const strategyBlock = `Test strategy (decided): pyramid=${strategy && strategy.pyramid}; coverageThreshold=${strategy && strategy.coverageThreshold}; envMatrix=${(strategy && strategy.envMatrix || []).join(', ') || 'n/a'}`

// Each selected writer authors its tests and confirms Red — different test files, so
// they run concurrently (unlike production-code writers).
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
const writerResults = (await parallel(writersFinal.map((w) => () =>
  agent(
    `Write the failing test(s) that encode the expected behavior below, then RUN them and confirm they FAIL for the intended reason (Red). Write test code ONLY — do not change production code. You are '${w}' — author only the tests of your specialty. Work within the repository at: ${repo}

FIND THE EXISTING SUITE BEFORE YOU WRITE. These tests are permanent: they are committed and every later run inherits them. Locate the file that already covers this module or behavior and ADD to it, matching its imports, fixtures, naming, and helpers. Create a new file only when nothing covers this area yet.

A second file covering the same behavior is worse than no test at all — the suite gets slower, and a failure no longer tells anyone which expectation is the real one. If you find an existing test that is WRONG rather than missing, say so in your evidence and leave it alone; repairing it is not yours to do.

${taskBlock}

${strategyBlock}
${a.feedback ? `\nGate feedback from the previous attempt — address it:\n${a.feedback}` : ''}

Deliver: the test file paths you created/modified, whether Red is confirmed, and the captured failing output as evidence.`,
    {
      label: `red:${w}`,
      phase: 'Red',
      agentType: `agent-teams-workforce:${w}`,
      schema: RED_SCHEMA,
    }
  )
))).filter(Boolean)

const testFiles = writerResults.flatMap((r) => (r && r.testFiles) || [])
const redConfirmed = writerResults.length > 0 && writerResults.every((r) => r && r.redConfirmed)
const evidence = writerResults.map((r) => r && r.evidence).filter(Boolean).join('\n---\n')

// Independent coverage check — every acceptance criterion has a covering test. The
// reviewer authors no tests; it only judges.
const coverage = await agent(
  `You are the test-coverage-gap-reviewer — INDEPENDENT of the test writers. Check the authored tests against the acceptance criteria; flag any criterion with no covering test. Do NOT write tests.

Acceptance criteria:
${ac.length ? ac.map((x, i) => `${i + 1}. GIVEN ${x.given} WHEN ${x.when} THEN ${x.then}`).join('\n') : '(none)'}

Authored test files: ${testFiles.join(', ') || 'none'}`,
  {
    label: 'red:coverage',
    phase: 'Red',
    agentType: 'agent-teams-workforce:test-coverage-gap-reviewer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['gaps'],
      properties: { gaps: { type: 'array', items: { type: 'string' } } },
    },
  }
)

const ledger = {
  phase: 'red',
  beadId: (c.bead && c.bead.id) || null,
  chosen: [...writersFinal, 'test-design-lead', 'test-strategy-decider', 'test-coverage-gap-reviewer'],
  mode: selectionMode,
  ok: redConfirmed,
}

return {
  testFiles,
  redConfirmed,
  evidence,
  writers: writersFinal,
  strategy,
  coverageGaps: (coverage && coverage.gaps) || [],
  ledger,
}
