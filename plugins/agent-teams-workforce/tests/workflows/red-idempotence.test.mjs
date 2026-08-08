// Red is idempotent: an interrupted or re-dispatched run must not re-author tests
// that already exist and already fail.
//
// The tests tdd-red writes are permanent — committed at deploy, inherited by every
// later run. Regenerating them wastes the most expensive phase in the pipeline, and
// a second writer pass produces a parallel file covering the same behavior, which
// makes the suite slower and its failures ambiguous.
//
// Reuse is the "already done" claim again, so it obeys the same rule: an assertion
// may not skip work. Here the evidence is EXECUTABLE — the surveyor runs the tests
// and captures the failing output. A test that does not exist cannot produce a
// failure, and a test that passes is not Red however it is described.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const tddRed = path.resolve(HERE, '..', '..', 'workflows', 'tdd-red.js')

const CONTRACT = {
  repoPath: '/repo',
  bead: { id: 'ssbd-1', title: 'a bug', repoPath: '/repo' },
  acceptanceCriteria: [{ given: 'g', when: 'w', then: 't' }],
}

async function run({ survey, args = {} }) {
  return runWorkflowScript(tddRed, {
    args: { contract: CONTRACT, ...args },
    agentImpl: (call) => {
      if (call.label === 'red:select-writers') return { writers: ['tdd-unit-test-generator'] }
      if (call.label === 'red:strategy') return { pyramid: 'unit-heavy', coverageThreshold: '80%' }
      if (call.label === 'red:survey') return survey
      if (String(call.label).startsWith('red:') && call.label !== 'red:coverage') {
        return { testFiles: ['tests/new_test.py'], redConfirmed: true, evidence: 'FAILED new' }
      }
      if (call.label === 'red:coverage') return { gaps: [], covered: true, findings: [] }
      return null
    },
  })
}

const EXECUTED = 'FAILED tests/test_x.py::test_a - KeyError: DOCUMENTS_TABLE_NAME'

test('existing tests that still FAIL satisfy Red — writers are not dispatched', async () => {
  const { result, calls } = await run({
    survey: { alreadyRed: true, existingTestFiles: ['tests/test_x.py'], gaps: [], evidence: EXECUTED },
  })
  assert.equal(result.redConfirmed, true)
  assert.equal(result.reusedExistingTests, true)
  assert.deepEqual(result.testFiles, ['tests/test_x.py'])
  const writers = calls.filter((c) => c.kind === 'agent' && /unit-test-generator|test-writer/.test(String(c.opts?.agentType)))
  assert.equal(writers.length, 0, 're-authoring tests that already fail wastes the most expensive phase and forks the suite')
})

test('a reuse claim with NO executed evidence authors the tests anyway', async () => {
  const { result } = await run({
    survey: { alreadyRed: true, existingTestFiles: ['tests/test_x.py'], gaps: [], evidence: '   ' },
  })
  assert.notEqual(result.reusedExistingTests, true, 'a claim of coverage with no executed output is not evidence')
})

test('a missing survey verdict authors the tests', async () => {
  const { result } = await run({ survey: null })
  assert.notEqual(result.reusedExistingTests, true, 'silence must not be read as "already Red"')
})

test('partial coverage authors ONLY the gaps and names the files to extend', async () => {
  const { calls } = await run({
    survey: {
      alreadyRed: false,
      existingTestFiles: ['tests/test_x.py'],
      gaps: ['criterion 25: pytest passes with no skip'],
      evidence: EXECUTED,
    },
  })
  const writer = calls.find((c) => c.kind === 'agent' && /unit-test-generator/.test(String(c.opts?.agentType)))
  assert.ok(writer, 'gaps must still be authored')
  assert.match(writer.prompt, /criterion 25/, 'the writer must be told which criteria remain')
  assert.match(writer.prompt, /tests\/test_x\.py/, 'and which existing files to extend rather than duplicate')
})

test('skipSurvey forces fresh authoring for a suite known to be bad', async () => {
  const { calls } = await run({
    args: { skipSurvey: true },
    survey: { alreadyRed: true, existingTestFiles: ['tests/bad.py'], gaps: [], evidence: EXECUTED },
  })
  assert.ok(
    !calls.some((c) => c.label === 'red:survey'),
    'when the operator knows the tests on disk are wrong, no agent should be spent surveying them',
  )
  assert.ok(calls.some((c) => c.kind === 'agent' && /unit-test-generator/.test(String(c.opts?.agentType))))
})
