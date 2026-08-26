// ssbd-vtnl — a Red-phase test was pinned to the PRE-FIX import path, so it could never
// go green after a correct fix.
//
// Red proved only that a test fails NOW. Nothing in the phase or its gate asked whether a
// PASS is reachable, so a mock patched at the module path the code used before the fix is
// indistinguishable from a correct Red and was certified as one. Red is necessary but not
// sufficient: the phase must also establish that each new test CAN go green.
//
// The check is a set comparison with no model turn: each writer names the production file
// and symbol whose change makes each test pass, and that set is compared against the
// contract's affectedFiles — which bug-triage already supplies and which tdd-red
// previously used only to print in a prompt.
//
// Second, independent hole, closed here too: on a loop attempt discovery re-found the
// previous attempt's bad test on disk, reported zero gaps, and the confirm-existing branch
// handed the gate back the identical un-passable test — through a code path the gate's own
// objection never reached.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const RED = path.join(WF, 'tdd-red.js')

const CONTRACT = {
  repoPath: '/wt',
  bead: { id: 'ssbd-vtnl', title: 'raise on bad config' },
  affectedFiles: ['src/skill_spoke/config/loader.py'],
  acceptanceCriteria: [{ given: 'g', when: 'w', then: 't' }],
  surfaces: [],
}

/** Run tdd-red with a scripted writer result; discovery finds nothing. */
function runRed(writer, { contract = CONTRACT, args = {} } = {}) {
  return runWorkflowScript(RED, {
    args: { contract, ...args },
    agentImpl: (call) => {
      if (call.label === 'red:discovery') return { existingTestFiles: [], gaps: ['g'] }
      if (call.label === 'red:coverage') return { gaps: [] }
      if (String(call.label).startsWith('red:')) return writer
      return null
    },
  })
}

const GOOD = {
  testFiles: ['tests/test_loader.py'],
  redConfirmed: true,
  evidence: 'E   ConfigurationError not raised',
  greenPath: [{
    testFile: 'tests/test_loader.py',
    targetFile: 'src/skill_spoke/config/loader.py',
    targetSymbol: 'load_config',
    assertionSubject: 'raises ConfigurationError on a missing key',
  }],
}

test('a test that names the file the fix changes is green-REACHABLE', async () => {
  const { result } = await runRed(GOOD)
  assert.equal(result.redConfirmed, true)
  assert.equal(result.greenReachable, true)
  assert.deepEqual(result.greenPathFindings, [])
})

test('ssbd-vtnl dies mechanically: a test pinned to a path the fix does not touch is NOT reachable', async () => {
  const { result } = await runRed({
    ...GOOD,
    greenPath: [{
      testFile: 'tests/test_loader.py',
      // The pre-fix import path. The mock patches here; the fix moves the symbol.
      targetFile: 'src/skill_spoke/legacy/config.py',
      targetSymbol: 'load_config',
      assertionSubject: 'raises ConfigurationError',
    }],
  })
  assert.equal(result.redConfirmed, true, 'the test really does fail — that was never the problem')
  assert.equal(result.greenReachable, false, 'but no correct fix can make it pass')
  assert.match(result.greenPathFindings[0], /legacy\/config\.py/)
  assert.match(result.greenPathFindings[0], /cannot go green/)
})

test('a test that declares no route to green at all is not reachable either', async () => {
  const { result } = await runRed({ ...GOOD, greenPath: [] })
  assert.equal(result.greenReachable, false)
  assert.match(result.greenPathFindings[0], /no greenPath entry/)
})

test('a greenPath entry naming no symbol is refused', async () => {
  const { result } = await runRed({
    ...GOOD,
    greenPath: [{ testFile: 'tests/test_loader.py', targetFile: 'src/skill_spoke/config/loader.py', targetSymbol: '  ', assertionSubject: 'x' }],
  })
  assert.equal(result.greenReachable, false)
  assert.match(result.greenPathFindings[0], /named no production file\/symbol/)
})

test('with no affectedFiles declared, the DECLARATION is still required', async () => {
  // The Task path's contract carries no affectedFiles, so the set comparison cannot run.
  // Requiring the declaration itself still forces the writer to name what makes the test
  // pass, which is the whole "can go green" question.
  const noFiles = { ...CONTRACT, affectedFiles: [] }
  const { result: ok } = await runRed(GOOD, { contract: noFiles })
  assert.equal(ok.greenReachable, true, 'any named production file is acceptable when the contract names none')
  const { result: bad } = await runRed({ ...GOOD, greenPath: [] }, { contract: noFiles })
  assert.equal(bad.greenReachable, false)
})

test('a path is matched by its tail, so absolute and repo-relative forms agree', async () => {
  const { result } = await runRed({
    ...GOOD,
    greenPath: [{ ...GOOD.greenPath[0], targetFile: '/wt/src/skill_spoke/config/loader.py' }],
  })
  assert.equal(result.greenReachable, true, 'a writer reporting an absolute path has not written a bad test')
})

test('greenReachable is false whenever Red itself was not confirmed', async () => {
  const { result } = await runRed({ ...GOOD, redConfirmed: false })
  assert.equal(result.greenReachable, false, 'reachability never launders a phase that produced no red')
})

test('the writer is REQUIRED by schema to declare the path to green', async () => {
  const { calls } = await runRed(GOOD)
  const writer = calls.find((c) => c.label === 'red:tdd-unit-test-generator')
  assert.ok(writer.opts.schema.required.includes('greenPath'), 'a schema bound is enforced by the runtime; a sentence in a prompt is not')
  assert.match(writer.prompt, /DECLARE THE PATH TO GREEN/)
  assert.match(writer.prompt, /src\/skill_spoke\/config\/loader\.py/, 'the writer is told which files the fix will touch')
})

// ── The retry hole ────────────────────────────────────────────────────────────

test('the gate\'s objection reaches DISCOVERY, not only the writers', async () => {
  const { calls } = await runRed(GOOD, { args: { feedback: 'the mock patches a module the fix does not use' } })
  const discovery = calls.find((c) => c.label === 'red:discovery')
  assert.match(discovery.prompt, /A GATE REJECTED THE PREVIOUS ATTEMPT/,
    'discovery decides whether to REUSE a test — a step that can reuse a rejected test must be shown the rejection')
  assert.match(discovery.prompt, /the mock patches a module the fix does not use/)
})

test('skipDiscovery bypasses the reuse branch entirely', async () => {
  const { calls } = await runRed(GOOD, { args: { skipDiscovery: true } })
  assert.ok(!calls.some((c) => c.label === 'red:discovery'), 'a re-run after a rejection authors; it does not shop for what it already wrote')
})

test('every composite sets skipDiscovery from attempt 2 of the Red gate', async () => {
  const { readFileSync } = await import('node:fs')
  for (const f of ['bug-fix.js', 'task-to-deploy.js', 'infra-change.js']) {
    const src = readFileSync(path.join(WF, f), 'utf8')
    assert.match(src, /skipDiscovery: !!\(loop && loop\.attempt > 1\)/,
      `${f} must stop the reuse branch laundering a rejected test back through a loop`)
  }
})

test('the reuse branches still report a reachability verdict, so the gate check is answerable', async () => {
  const { result } = await runWorkflowScript(RED, {
    args: { contract: CONTRACT },
    agentImpl: (call) => {
      if (call.label === 'red:discovery') return { existingTestFiles: ['tests/test_loader.py'], gaps: [] }
      if (call.label === 'red:confirm-existing') return { verdict: 'red', evidence: 'FAILED tests/test_loader.py' }
      return null
    },
  })
  assert.equal(result.reusedExistingTests, true)
  assert.equal(result.greenReachable, true, 'these tests were EXECUTED and observed red; there is no authored greenPath to check')
  assert.equal(result.greenPathChecked, false, 'and the artifact must say the check did not apply, not imply it passed one')
})
