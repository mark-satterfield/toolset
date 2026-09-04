// Green could be blocked by something NOBODY in the pipeline had authority to resolve.
//
// The failing test asserts one outcome for an input; another test, already passing,
// asserts the opposite outcome for the identical input. The implementer may not modify a
// test, the gate is right to fail a test that does not pass, and the Red⇄Green escalation
// does not help either — it was built for a DEFECTIVE test, and re-authoring a
// contradiction REGENERATES one side of it rather than resolving it. So the run deadlocked
// until a human read the logs.
//
// On ssbd-97as a human had to rule twice: GET /api/settings with USER_POOL_ID absent had
// one test requiring 500 and another, passing, requiring 200 under identical env per
// conftest.py; and an unresolvable account id had one test requiring fail-closed and
// another requiring 200 with breach_check='skipped'.
//
// The fix routes it to the EXISTING test-strategy-decider, whose job is ruling which
// contract binds, and drives the Red re-author from its ruling.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, agentCalls, workflowCalls } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const BUG_FIX = path.join(WF, 'bug-fix.js')
const TDD_GREEN = path.join(WF, 'tdd-green.js')
const WORKTREE = '/repos/.worktrees/ssbd-97as-chassis'

const CONTRADICTION = {
  testA: 'tests/test_settings.py::test_missing_pool_id_returns_500',
  testB: 'tests/test_settings.py::test_settings_returns_200',
  sharedGiven: 'GET /api/settings with USER_POOL_ID absent from the environment',
  expectedA: 'HTTP 500',
  expectedB: 'HTTP 200',
  evidence: 'both run under the identical env fixture in conftest.py; making A pass breaks B',
}

const RULING = {
  bindingTest: 'tests/test_settings.py::test_settings_returns_200',
  losingTest: 'tests/test_settings.py::test_missing_pool_id_returns_500',
  correctedExpectation: 'HTTP 200 with the pool id omitted from the payload',
  rationale: 'settings is a read endpoint and must degrade, not fail closed, on optional config',
}

/** Run bug-fix to the Green gate with the implementer reporting a contradiction. */
async function runWithContradiction({ ruling = RULING, contradiction = CONTRADICTION } = {}) {
  let greenCalls = 0
  return runWorkflowScript(BUG_FIX, {
    args: { maxLoops: 2, maxEscalations: 1, bead: { id: 'ssbd-97as', title: 'settings 500', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: (call) => {
      if (call.label === 'green:contradiction-ruling') return ruling
      if (call.label === 'settle:land-work') return { treeClean: true, hasWork: false, branch: 'fix/x', prUrl: '' }
      if (call.label === 'ledger:persist') return { written: true, path: '/journal.jsonl' }
      return null
    },
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-97as', isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { repoPath: WORKTREE, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      }
      if (call.name === 'agent-teams-workforce:tdd-red') {
        return { testFiles: ['tests/test_settings.py'], redConfirmed: true, evidence: 'fails', greenReachable: true }
      }
      if (call.name === 'agent-teams-workforce:tdd-green') {
        greenCalls += 1
        // The implementer reports the contradiction it cannot fix. After the re-author it
        // still cannot go green in this fixture — the run ends, but only after the ruling.
        return { greenConfirmed: false, evidence: 'A and B cannot both hold', changedFiles: [], contradiction }
      }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        if (call.payload.gate === '2b') return { verdict: 'loop', feedback: 'green not confirmed', criteria: [] }
        return { verdict: 'pass', criteria: [], flags: [] }
      }
      return {}
    },
  })
}

test('a reported contradiction is ruled by the EXISTING test-strategy-decider', async () => {
  const { calls } = await runWithContradiction()
  const rulings = agentCalls(calls, 'green:contradiction-ruling')
  assert.equal(rulings.length, 1, 'the contradiction must be ruled exactly once, not re-litigated per attempt')
  assert.equal(
    rulings[0].opts.agentType,
    'agent-teams-workforce:test-strategy-decider',
    'the authority already exists — deciding which contract binds is precisely its job',
  )
  // The three inputs a ruling cannot be made without.
  assert.match(rulings[0].prompt, /USER_POOL_ID absent/, 'the GIVEN the two tests share must reach the decider')
  assert.match(rulings[0].prompt, /test_missing_pool_id_returns_500/, 'and both tests')
  assert.match(rulings[0].prompt, /test_settings_returns_200/, 'and both tests')
  assert.match(rulings[0].prompt, /identical env fixture in conftest\.py/, "and the implementer's evidence")
})

test("the ruling DRIVES the Red re-author — it is not merely recorded", async () => {
  const { calls } = await runWithContradiction()
  const reds = workflowCalls(calls, 'agent-teams-workforce:tdd-red')
  assert.ok(reds.length >= 2, 'a ruled contradiction must send test authoring back around; nothing else may repair a test')
  const reauthor = reds[reds.length - 1].payload
  assert.equal(reauthor.skipDiscovery, true, 'a re-author authors — it must not shop for the tests it just wrote')
  assert.match(reauthor.feedback, /LOSING \(correct THIS one\): tests\/test_settings\.py::test_missing_pool_id_returns_500/)
  assert.match(reauthor.feedback, /must assert instead: HTTP 200 with the pool id omitted/)
  assert.match(reauthor.feedback, /BINDING \(correct, leave it alone\)/, 'the binding test must be named as off-limits')
})

test('the re-authored Red gate makes the ruling BINDING, not advisory', async () => {
  const { calls } = await runWithContradiction()
  const gates = workflowCalls(calls, 'agent-teams-workforce:gate-enforce').filter((c) => c.payload.gate === '2a')
  const last = gates[gates.length - 1]
  // A gate criterion is EITHER a plain string or `{ text, class }` — the plain form is the
  // default path and stays supported forever, so this reads the text from either shape.
  const text = (c) => (typeof c === 'string' ? c : (c && typeof c.text === 'string' ? c.text : ''))
  const criterion = last.payload.criteria.map(text).find((c) => c.includes('test-strategy-decider'))
  assert.ok(criterion, 'without a criterion carrying the ruling, the gate has no ground to reject the original pair')
  assert.match(criterion, /has not applied the ruling/, 'and it must say what non-compliance looks like')
})

test('no ruling means the run STOPS and says so — re-authoring an unresolved contradiction cannot converge', async () => {
  const { result, calls } = await runWithContradiction({ ruling: null })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'green')
  assert.match(result.headline, /assert opposite outcomes for the same input/, 'the headline must name the real blocker')
  assert.match(result.headline, /returned no ruling/, 'and that it was the decider that produced nothing')
  const reds = workflowCalls(calls, 'agent-teams-workforce:tdd-red')
  assert.equal(reds.length, 1, 'it must NOT spend an escalation re-authoring against a contradiction nobody resolved')
})

test('tdd-green gives the implementer a structured channel to report it', async () => {
  const { result, calls } = await runWorkflowScript(TDD_GREEN, {
    args: {
      contract: { repoPath: WORKTREE, bead: { id: 'ssbd-97as', title: 't' } },
      red: { testFiles: ['tests/test_settings.py'], evidence: 'fails' },
      implementer: 'chassis-extension-implementer',
    },
    agentImpl: () => ({ changedFiles: [], greenConfirmed: false, evidence: 'cannot satisfy both', contradiction: CONTRADICTION }),
  })
  const impl = calls.find((c) => c.label === 'green:chassis-extension-implementer')
  assert.ok(impl.opts.schema.properties.contradiction, 'prose in `notes` cannot be routed to a decider — the field must be structured')
  assert.deepEqual(
    impl.opts.schema.properties.contradiction.required,
    ['testA', 'testB', 'sharedGiven', 'evidence'],
    'the decider needs both tests, the GIVEN they share, and the evidence — a partial report cannot be ruled on',
  )
  assert.match(impl.prompt, /do not pick a side/, 'the implementer must be told this is not its call to make')
  assert.deepEqual(result.contradiction, CONTRADICTION, 'and the mini must surface it to the composite')
})
