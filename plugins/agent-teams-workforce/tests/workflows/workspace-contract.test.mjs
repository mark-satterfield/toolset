// ssbd-mz1w — composites wrote into the repository's MAIN working tree.
//
// Two live runs did it. One created nine test files and modified two more directly on
// `main` in a main working tree; the other left an entire production fix uncommitted
// there. Neither had a branch, neither had a PR, and the 6.0.4 settle step — which lands
// work by pushing a BRANCH — could not see either one, because loose changes on main are
// not a branch to push.
//
// The cause was structural, not incidental: NO workflow phase created a worktree.
// Provisioning lived only as shell inside two markdown commands, executed by a model, and
// it is the step both failing runs skipped. deploy.js meanwhile demanded a state nothing
// produced ("committed on a feature branch IN A WORKTREE").
//
// The fix gives the worktree ONE owner: a `workspace` phase, dispatched first by every
// code-writing composite, whose return value is the sole source of contract.repoPath.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const COMPOSITES = [
  { file: 'bug-fix.js', writer: 'agent-teams-workforce:tdd-red' },
  { file: 'task-to-deploy.js', writer: 'agent-teams-workforce:tdd-red' },
  { file: 'infra-change.js', writer: 'agent-teams-workforce:infra-intent' },
]

const CALLER_REPO = '/repos/SkillSpoke-shared-chassis'
const WORKTREE = '/repos/.worktrees/ssbd-mz1w-shared-chassis'

/** Drive a composite with a scripted workspace result; everything else passes. */
function run(file, { workspace, args } = {}) {
  return runWorkflowScript(path.join(WF, file), {
    args: args || { bead: { id: 'ssbd-mz1w', title: 'w', description: 'd', repoPath: CALLER_REPO } },
    agentImpl: () => ({ written: true, treeClean: true, hasWork: false, branch: 'b', prUrl: '' }),
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') return workspace
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { repoPath: '/SOMEWHERE/ELSE', scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      }
      if (call.name === 'agent-teams-workforce:infra-intent') return { provisioningIntent: 'p', affectedStacks: ['S'] }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        // task-to-deploy's Gate 1 is spec freshness, which precedes Red — pass it so
        // every composite reaches a WRITING phase, then fail there so the run
        // terminates quickly. The workspace assertions all concern what happened
        // before that point.
        if (call.payload.gate === '1') return { verdict: 'pass', criteria: [], flags: [] }
        return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
      }
      return { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', greenReachable: true, changedFiles: [] }
    },
  })
}

const OK_WORKSPACE = { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true }

for (const { file, writer } of COMPOSITES) {
  test(`${file}: the workspace phase runs FIRST, before anything that can write`, async () => {
    const { calls } = await run(file, { workspace: OK_WORKSPACE })
    const names = calls.filter((c) => c.kind === 'workflow').map((c) => c.name)
    assert.equal(names[0], 'agent-teams-workforce:workspace', 'the tree must exist before the first phase that could edit one')
    assert.ok(names.includes(writer), 'fixture must reach a writing phase for this assertion to mean anything')
    assert.ok(
      names.indexOf('agent-teams-workforce:workspace') < names.indexOf(writer),
      'a writing phase dispatched before the worktree exists writes into whatever tree the caller pointed at',
    )
  })

  test(`${file}: contract.repoPath is the WORKSPACE's tree, never the caller's repository`, async () => {
    const { calls } = await run(file, { workspace: OK_WORKSPACE })
    const writing = calls.filter((c) => c.kind === 'workflow' && c.name === writer)
    assert.ok(writing.length, 'fixture must dispatch a writing phase')
    const payload = writing[0].payload
    const contract = payload.contract || payload.change || {}
    assert.equal(contract.repoPath, WORKTREE, 'every writing phase must inherit the worktree, not the repository')
    assert.notEqual(contract.repoPath, CALLER_REPO, 'the caller-supplied path is an INPUT to the workspace step, not the tree phases write in')
  })

  test(`${file}: a workspace that cannot verify a tree REFUSES the run — it does not fall back`, async () => {
    const { result, calls } = await run(file, {
      workspace: { ok: false, repoPath: null, branch: null, reused: false, blocked: ['the path is the main working tree on main'] },
    })
    assert.equal(result.ok, false)
    assert.equal(result.stage, 'workspace', 'the run must name where it stopped')
    const names = calls.filter((c) => c.kind === 'workflow').map((c) => c.name)
    assert.ok(!names.includes(writer), 'falling back to the caller\'s tree is exactly the failure — nothing may write')
  })

  test(`${file}: a run with no repository is refused at the input stage, not run blind`, async () => {
    const { result, calls } = await run(file, {
      workspace: OK_WORKSPACE,
      args: { bead: { id: 'ssbd-mz1w', title: 'w', description: 'd' } },
    })
    assert.equal(result.ok, false)
    assert.equal(result.stage, 'input')
    assert.match(String(result.error), /repoPath/, 'the refusal must name what is missing')
    assert.equal(calls.length, 0, 'nothing at all may be dispatched for a run that cannot land its work')
  })

  test(`${file}: settle targets the WORKSPACE tree, so there is always a branch to push`, async () => {
    const { calls } = await run(file, { workspace: OK_WORKSPACE })
    const settle = calls.filter((c) => c.kind === 'agent' && c.label === 'settle:land-work')
    assert.equal(settle.length, 1, 'settle runs on every exit path')
    assert.match(settle[0].prompt, new RegExp(WORKTREE.replace(/[/]/g, '\\/')), 'settle must land the tree the phases actually wrote in')
  })
}

test('workspace.js itself refuses without a repository or a bead id', async () => {
  const WS = path.join(WF, 'workspace.js')
  for (const args of [{ beadId: 'ssbd-1' }, { repoPath: '/r' }]) {
    const { result, calls } = await runWorkflowScript(WS, { args, agentImpl: () => null })
    assert.equal(result.ok, false)
    assert.equal(result.repoPath, null)
    assert.ok(result.blocked.length, 'it must say what was missing')
    assert.equal(calls.length, 0, 'no agent turn is spent on an input that cannot succeed')
  }
})

test('workspace.js fails closed when the provisioner cannot verify the tree', async () => {
  const WS = path.join(WF, 'workspace.js')
  for (const provisioned of [null, { ok: false, repoPath: '', branch: '', reused: false, blocked: ['not a linked worktree'] }, { ok: true, repoPath: '   ', branch: 'b', reused: false }]) {
    const { result } = await runWorkflowScript(WS, {
      args: { repoPath: '/r', beadId: 'ssbd-1', branchPrefix: 'fix' },
      agentImpl: () => provisioned,
    })
    assert.equal(result.ok, false, 'an unverified tree must never be reported as established')
    assert.equal(result.repoPath, null)
  }
})

test('workspace.js returns the verified tree and names the branch', async () => {
  const WS = path.join(WF, 'workspace.js')
  const { result, calls } = await runWorkflowScript(WS, {
    args: { repoPath: '/r', beadId: 'ssbd-1', branchPrefix: 'fix', purpose: 'a bug' },
    agentImpl: () => ({ ok: true, repoPath: `${WORKTREE}  `, branch: '', reused: true, isLinkedWorktree: true, evidence: 'x' }),
  })
  assert.equal(result.ok, true)
  assert.equal(result.repoPath, WORKTREE, 'the path is trimmed — a trailing space silently breaks every git -C after it')
  assert.equal(result.branch, 'fix/ssbd-1', 'an unreported branch falls back to the one this step asked for')
  assert.equal(result.reused, true)
  assert.match(calls[0].prompt, /worktree add -b/, 'the provisioning instruction must actually be in the prompt')
})
