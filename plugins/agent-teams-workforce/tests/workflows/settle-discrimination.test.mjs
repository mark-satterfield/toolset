// ssbd-4q3x — the settle step collapsed three distinct worlds into one verdict.
//
// A run with no repo path, a run whose settle agent threw, and a genuine orphan were
// indistinguishable: all three produced `null`, and the first two then flipped a
// successful run to ok:false with `blocked: ['settle returned no verifiable PR URL']` —
// a message asserting something that never happened, because the settle agent was never
// dispatched at all. Reporting failure over correct work teaches the operator to
// disbelieve the one signal that exists to be believed.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const COMPOSITES = ['bug-fix.js', 'task-to-deploy.js', 'infra-change.js']
const WORKTREE = '/repos/.worktrees/ssbd-4q3x-chassis'

/** Run a composite to a clean early success, with a scripted settle result. */
function run(file, settleImpl, args) {
  return runWorkflowScript(path.join(WF, file), {
    args: args || { bead: { id: 'ssbd-4q3x', title: 's', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: (call) => {
      if (call.label === 'settle:land-work') return settleImpl()
      return { written: true }
    },
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-4q3x', reused: false, isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { repoPath: WORKTREE, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      }
      if (call.name === 'agent-teams-workforce:infra-intent') return { provisioningIntent: 'p', affectedStacks: ['S'] }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        if (call.payload.gate === '1' || call.payload.gate === 'G1') return { verdict: 'pass', criteria: [], flags: [] }
        return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
      }
      return { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', greenReachable: true }
    },
  })
}

for (const file of COMPOSITES) {
  test(`${file}: a settle agent that THREW says so — it never claims a URL was withheld`, async () => {
    const { result } = await run(file, () => {
      throw new Error('the worktree vanished under us')
    })
    assert.ok(result.settleFailed, 'an errored settle must be named as an error')
    assert.match(result.settleFailed.error, /vanished/, 'and must carry the real reason')
    assert.equal(result.landed, false)
    assert.equal(result.orphaned, undefined, 'nothing was orphaned — the step failed before it could look')
  })

  test(`${file}: a genuine orphan reports the settle agent's OWN blocked reasons`, async () => {
    const { result } = await run(file, () => ({
      treeClean: false,
      hasWork: true,
      branch: 'fix/ssbd-4q3x',
      prUrl: '',
      blocked: ['ruff findings could not be fixed; aborted with no commit'],
    }))
    assert.equal(result.landed, false)
    assert.ok(result.orphaned, 'this IS the orphan case')
    assert.equal(result.orphaned.worktree, WORKTREE)
    assert.deepEqual(result.orphaned.blocked, ['ruff findings could not be fixed; aborted with no commit'],
      'the placeholder must never overwrite a reason the agent actually gave')
  })

  test(`${file}: a clean tree with nothing to land is LANDED, not orphaned`, async () => {
    const { result } = await run(file, () => ({ treeClean: true, hasWork: false, branch: 'fix/ssbd-4q3x', prUrl: '' }))
    assert.equal(result.landed, true, 'a run that wrote nothing has nothing to strand')
    assert.equal(result.settled, 'reported')
    assert.equal(result.orphaned, undefined)
  })

  test(`${file}: a verified PR URL lands the run`, async () => {
    const { result } = await run(file, () => ({
      treeClean: true, hasWork: true, branch: 'fix/ssbd-4q3x', prUrl: '  https://github.com/o/r/pull/42 ',
    }))
    assert.equal(result.landed, true)
    assert.equal(result.prUrl, 'https://github.com/o/r/pull/42', 'the URL is trimmed before it is reported')
  })

  test(`${file}: a run with no repo path can no longer happen — it is refused, not run blind`, async () => {
    // The reproduced false orphan: an identical successful run flipped ok:true -> false
    // on repoPath alone, with orphaned:{worktree:null}. repoPath is now a required input
    // exactly as bead.id already was, so "not applicable" is unreachable for a
    // code-writing composite rather than being a phantom failure at the end.
    const { result } = await run(file, () => ({ treeClean: true, hasWork: false, branch: '', prUrl: '' }), {
      bead: { id: 'ssbd-4q3x', title: 's', description: 'd' },
    })
    assert.equal(result.stage, 'input')
    assert.equal(result.orphaned, undefined, 'a run that never started cannot have orphaned anything')
  })
}
