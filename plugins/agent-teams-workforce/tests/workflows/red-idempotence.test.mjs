// Red is idempotent: an interrupted or re-dispatched run must not re-author tests
// that already exist and already fail.
//
// The tests tdd-red writes are permanent — committed at deploy, inherited by every
// later run. Regenerating them wastes the most expensive phase in the pipeline, and
// a second writer pass produces a parallel file covering the same behavior, which
// makes the suite slower and its failures ambiguous.
//
// Reuse is the "already done" claim again, so it obeys the same rule: an assertion
// may not skip work. Here the evidence is EXECUTABLE — a test that does not exist
// cannot produce a failure, and a test that passes is not Red however it is
// described.
//
// THE SHAPE THIS MODELS. tdd-red answers reuse in TWO steps, not one, and the split
// is the point:
//
//   red:discovery         a LOOKUP that runs nothing — which criteria already have
//                         a covering file, and which remain as `gaps`
//   red:confirm-existing  reached ONLY when files were found and no gaps remain.
//                         Executes those files and returns a THREE-WAY verdict:
//                         red (reuse it), already-satisfied (the behavior exists,
//                         stop the phase), not-encoded (author against them)
//
// An earlier revision of this file mocked a single `red:survey` agent returning
// `alreadyRed`, and a `skipSurvey` argument. None of those three names exist in the
// workflow. The mock therefore never matched, every run fell through to authoring,
// and three of the five tests passed vacuously — asserting that reuse did NOT
// happen, in a harness where reuse could never happen. Two failed outright. If a
// name below stops matching the workflow again, the failure to fear is the silent
// one: assert on the positive path so a stale label breaks the test loudly.

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

// Executed output, verbatim — what an evidenced verdict looks like.
const EXECUTED = 'FAILED tests/test_x.py::test_a - KeyError: DOCUMENTS_TABLE_NAME'

// The writer this contract derives: unit is unconditional, and CONTRACT declares no
// surfaces, so `tdd-unit-test-generator` is the only writer that should ever appear.
const isWriter = (c) =>
  c.kind === 'agent' && /agent-teams-workforce:(tdd-unit-test-generator|.*-test-writer)/.test(String(c.opts?.agentType))

async function run({ discovery, confirmation, args = {} }) {
  return runWorkflowScript(tddRed, {
    args: { contract: CONTRACT, ...args },
    agentImpl: (call) => {
      if (call.label === 'red:discovery') return discovery
      if (call.label === 'red:confirm-existing') return confirmation
      if (call.label === 'red:coverage') return { gaps: [] }
      // Any remaining red:* label is a writer.
      if (String(call.label).startsWith('red:')) {
        return { testFiles: ['tests/new_test.py'], redConfirmed: true, evidence: 'FAILED new' }
      }
      return null
    },
  })
}

test('existing tests that still FAIL satisfy Red — writers are not dispatched', async () => {
  const { result, calls } = await run({
    discovery: { existingTestFiles: ['tests/test_x.py'], gaps: [] },
    confirmation: { verdict: 'red', evidence: EXECUTED },
  })
  assert.equal(result.redConfirmed, true)
  assert.equal(result.reusedExistingTests, true)
  assert.deepEqual(result.testFiles, ['tests/test_x.py'])
  assert.equal(result.evidence, EXECUTED, 'the reused verdict carries the executed output forward')
  assert.equal(
    calls.filter(isWriter).length,
    0,
    're-authoring tests that already fail wastes the most expensive phase and forks the suite',
  )
})

test('passing tests that genuinely encode the contract STOP the phase — nothing is authored', async () => {
  const { result, calls } = await run({
    discovery: { existingTestFiles: ['tests/test_x.py'], gaps: [] },
    confirmation: { verdict: 'already-satisfied', evidence: 'PASSED tests/test_x.py::test_a' },
  })
  assert.equal(result.alreadySatisfied, true)
  assert.equal(result.redConfirmed, false, 'no Red is obtainable when the behavior already exists')
  assert.equal(
    calls.filter(isWriter).length,
    0,
    'sending this to the writers asks them to manufacture a red, which they can only do by asserting something false',
  )
})

test('a reuse claim with NO executed evidence authors the tests anyway', async () => {
  const { result, calls } = await run({
    discovery: { existingTestFiles: ['tests/test_x.py'], gaps: [] },
    confirmation: { verdict: 'red', evidence: '   ' },
  })
  assert.notEqual(result.reusedExistingTests, true, 'a claim of coverage with no executed output is not evidence')
  assert.ok(calls.some(isWriter), 'an unevidenced claim falls through to authoring')
})

test('a missing confirmation verdict authors the tests', async () => {
  const { result, calls } = await run({
    discovery: { existingTestFiles: ['tests/test_x.py'], gaps: [] },
    confirmation: null,
  })
  assert.notEqual(result.reusedExistingTests, true, 'silence must not be read as "already Red"')
  assert.ok(calls.some(isWriter), 'silence falls through to authoring')
})

test('partial coverage authors ONLY the gaps and names the files to extend', async () => {
  const { calls } = await run({
    discovery: {
      existingTestFiles: ['tests/test_x.py'],
      gaps: ['criterion 25: pytest passes with no skip'],
    },
    // Unreachable by design: confirmation runs only when NO gaps remain. Scripted to
    // throw so the branch collapsing back into one step fails here instead of silently.
    confirmation: (() => {
      throw new Error('red:confirm-existing must not run while gaps remain')
    }),
  })
  assert.ok(
    !calls.some((c) => c.label === 'red:confirm-existing'),
    'with gaps open there is nothing to confirm — the files are going to be extended either way',
  )
  const writer = calls.find(isWriter)
  assert.ok(writer, 'gaps must still be authored')
  assert.match(writer.prompt, /criterion 25/, 'the writer must be told which criteria remain')
  assert.match(writer.prompt, /tests\/test_x\.py/, 'and which existing files to extend rather than duplicate')
})

test('skipDiscovery forces fresh authoring for a suite known to be bad', async () => {
  const { calls } = await run({
    args: { skipDiscovery: true },
    discovery: { existingTestFiles: ['tests/bad.py'], gaps: [] },
    confirmation: { verdict: 'red', evidence: EXECUTED },
  })
  assert.ok(
    !calls.some((c) => c.label === 'red:discovery'),
    'when the operator knows the tests on disk are wrong, no agent should be spent surveying them',
  )
  assert.ok(calls.some(isWriter), 'and the writers author fresh rather than reusing what discovery would have found')
})
