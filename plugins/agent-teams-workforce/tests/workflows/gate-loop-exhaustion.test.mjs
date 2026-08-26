// ssbd-36fn (second half) — loop exhaustion returned a bare reason string.
//
// The unmet criteria and their evidence are COMPUTED one line earlier and were thrown
// away; the final verdict was discarded entirely — `recordGate(MAX_LOOPS, null, ...)`
// meant even the ledger's terminal row carried `criteria: []`, `unmetCriteria: []` and
// `feedback: null`. So an exhausted gate could not be distinguished from a genuine defect,
// an over-strict criterion, or a phase that never produced anything. And the four
// copy-pasted gateLoops had already diverged: two carried the artifact on exhaustion,
// two dropped it.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const WORKTREE = '/repos/.worktrees/ssbd-36fn-chassis'

const LOOP_VERDICT = {
  verdict: 'loop',
  feedback: 'the assertion reads a committed cdk.out template',
  criteria: [
    { criterion: 'A failing test encodes the contract', met: true, evidence: 'tests/test_x.py::test_y fails' },
    { criterion: 'The test fails for the intended reason', met: false, evidence: 'it fails on a stale snapshot, not on behavior' },
  ],
}
const FINAL_ARTIFACT = { testFiles: ['tests/test_x.py'], redConfirmed: true, evidence: 'e', greenReachable: true, marker: 'LAST' }

/** Exhaust the first WRITING gate of a composite and return the gateLoop result. */
async function exhaust(file, writingGate, entryGate) {
  const { result } = await runWorkflowScript(path.join(WF, file), {
    args: { maxLoops: 2, bead: { id: 'ssbd-36fn', title: 'x', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: () => ({ written: true, treeClean: true, hasWork: false, branch: 'b', prUrl: '' }),
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-36fn', reused: false, isLinkedWorktree: true }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { repoPath: WORKTREE, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      }
      if (call.name === 'agent-teams-workforce:infra-intent') return { provisioningIntent: 'p', affectedStacks: ['S'] }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        if (call.payload.gate === entryGate) return { verdict: 'pass', criteria: [], flags: [] }
        return LOOP_VERDICT
      }
      return FINAL_ARTIFACT
    },
  })
  return result.detail
}

const CASES = [
  { file: 'bug-fix.js', gate: '2a', entry: null },
  { file: 'task-to-deploy.js', gate: '2a', entry: '1' },
  { file: 'infra-change.js', gate: '2a', entry: 'G1' },
]

for (const { file, entry } of CASES) {
  test(`${file}: an exhausted gate names WHAT was unmet and on what evidence`, async () => {
    const d = await exhaust(file, '2a', entry)
    assert.equal(d.loopExhausted, true, 'fixture must actually exhaust the gate')
    assert.ok(Array.isArray(d.unmetCriteria), 'the unmet criteria are computed every attempt — they must survive to the exit')
    assert.equal(d.unmetCriteria.length, 1)
    assert.equal(d.unmetCriteria[0].criterion, 'The test fails for the intended reason')
    assert.match(d.unmetCriteria[0].evidence, /stale snapshot/, 'a criterion with no evidence cannot be argued with or acted on')
  })

  test(`${file}: an exhausted gate carries the final verdict and every attempt`, async () => {
    const d = await exhaust(file, '2a', entry)
    assert.ok(d.verdict, 'the last attempt\'s real verdict must not be discarded')
    assert.equal(d.verdict.feedback, LOOP_VERDICT.feedback)
    assert.equal(d.attempts.length, 2, 'one entry per adjudicated attempt')
    assert.equal(d.attempts[0].attempt, 1)
    assert.equal(d.attempts[1].unmetCriteria.length, 1)
  })

  test(`${file}: an exhausted gate still hands back the artifact the phase produced`, async () => {
    // Two of the four gateLoop copies dropped it. The divergence was itself the defect.
    const d = await exhaust(file, '2a', entry)
    assert.ok(Object.prototype.hasOwnProperty.call(d, 'artifact'), 'consumers must distinguish "produced nothing" from "the shape omitted it"')
    assert.equal(d.artifact.marker, 'LAST', 'and it must be the LAST attempt\'s artifact')
  })
}

test('all four gateLoop copies return the same exhaustion shape', async () => {
  // gateLoop is copy-pasted into four composites and the copies had already diverged in
  // behaviour, not just formatting. Any fix has to land in all four or it half-lands.
  const { readFileSync } = await import('node:fs')
  for (const f of ['bug-fix.js', 'task-to-deploy.js', 'infra-change.js', 'prd-to-spec.js']) {
    const src = readFileSync(path.join(WF, f), 'utf8')
    for (const key of ['loopExhausted: true', 'verdict: lastVerdict', 'unmetCriteria: lastVerdict', 'attempts,']) {
      assert.ok(src.includes(key), `${f} is missing "${key}" from its loop-exhausted return`)
    }
    assert.ok(
      src.includes('recordGate(MAX_LOOPS, lastVerdict') || src.includes('MAX_LOOPS, lastVerdict'),
      `${f} still records a null verdict at exhaustion — the ledger's terminal row then carries no criteria at all`,
    )
  }
})
