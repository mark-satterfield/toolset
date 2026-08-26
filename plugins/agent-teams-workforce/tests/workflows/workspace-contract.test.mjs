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

// ── The UNCOOPERATIVE provisioner (ssbd-mz1w, residual) ───────────────────────
//
// Everything above this line scripts a provisioner that cooperates: it returns ok:false
// when it cannot verify, and a well-formed worktree when it can. That is why 398 tests
// passed while the P0 was still live. The bead's actual failure mode is a model that
// SKIPS or FUMBLES its own verification and then reports success — and the 6.0.5 script
// accepted it, because `isLinkedWorktree` was optional in the schema and read as
// `!== false`, so the model that never looked got the safe answer by default.
//
// These tests model that model.

const WS = path.join(WF, 'workspace.js')

/** Drive workspace.js with one scripted provisioner result. */
function provision(provisioned, args) {
  return runWorkflowScript(WS, {
    args: args || { repoPath: CALLER_REPO, beadId: 'ssbd-mz1w', branchPrefix: 'fix' },
    agentImpl: () => provisioned,
  })
}

test('workspace.js: THE reproduction — ok:true carrying the MAIN working tree on main is REFUSED', async () => {
  // The verifier's exact defeat of the 6.0.5 fix: this result was accepted, and driving
  // bug-fix.js with it delivered the repository's main working tree to tdd-red — a
  // code-WRITING phase, the one that authored nine test files onto main.
  const { result } = await provision({ ok: true, repoPath: CALLER_REPO, branch: 'main', reused: true })
  assert.equal(result.ok, false, 'a main working tree on main is the original incident, not a workspace')
  assert.equal(result.repoPath, null, 'nothing downstream may inherit a tree this step refused')
  assert.ok(result.blocked.length, 'the refusal must say what it saw')
})

test('workspace.js: an OMITTED isLinkedWorktree refuses — absent is not the safe answer', async () => {
  // The precise defect: the field is optional in the schema and the code read
  // `provisioned.isLinkedWorktree !== false`, so a model that never reported it — i.e.
  // never performed step 6 — was handed `true` by the script itself.
  const { result } = await provision({ ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false })
  assert.equal(result.ok, false)
  assert.equal(result.repoPath, null)
  assert.match(String(result.blocked[0]), /isLinkedWorktree/, 'the refusal must name the claim that was never made')
})

test('workspace.js: only STRICTLY true counts as a linked-worktree claim', async () => {
  for (const claimed of [false, null, undefined, 'true', 1, {}, []]) {
    const { result } = await provision({ ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: claimed })
    assert.equal(result.ok, false, `isLinkedWorktree=${JSON.stringify(claimed)} must refuse — a malformed claim is not a verification`)
    assert.equal(result.repoPath, null)
  }
})

test('workspace.js: a tree reported on the DEFAULT branch is refused however it is spelled', async () => {
  // The 6.0.5 prompt already said "HEAD MUST NOT be the default branch". Nothing enforced
  // it, so a provisioner that claimed a linked worktree and named `main` sailed through.
  for (const branch of ['main', 'master', 'MAIN', ' main ', 'refs/heads/main', 'origin/main', 'HEAD']) {
    const { result } = await provision({ ok: true, repoPath: WORKTREE, branch, reused: true, isLinkedWorktree: true })
    assert.equal(result.ok, false, `branch "${branch}" must refuse — it is the one branch the project's rules forbid writing`)
    assert.equal(result.repoPath, null)
    assert.match(String(result.blocked[0]), /HEAD/, 'the refusal must name the branch it saw')
  }
})

test('workspace.js: a verified linked worktree on a feature branch is still ACCEPTED', async () => {
  // The guards must refuse the uncooperative provisioner without refusing the real one.
  const { result } = await provision({ ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true, evidence: 'e' })
  assert.equal(result.ok, true)
  assert.equal(result.repoPath, WORKTREE)
  assert.equal(result.branch, 'fix/ssbd-mz1w')
  assert.equal(result.isLinkedWorktree, true, 'the returned field is now earned, not fabricated by the script')
})

test('workspace.js: git itself contradicts a claim the provisioner did not earn', async () => {
  // The two guards above compare what the provisioner SAID. This is the only layer that
  // can catch a claim it did not earn — a model that reports isLinkedWorktree:true and a
  // feature branch while handing back a main working tree. It is an EXTRA layer, not the
  // primary control: no shipped workflow uses child_process, so the production runner may
  // sandbox it, in which case the pure guards above stand alone and this test is skipped.
  const { execFileSync } = await import('node:child_process')
  const { mkdtempSync, rmSync } = await import('node:fs')
  const os = await import('node:os')
  let dir
  try {
    dir = mkdtempSync(path.join(os.tmpdir(), 'ws-guard-'))
    execFileSync('git', ['init', '-q', '-b', 'main', dir], { stdio: ['ignore', 'pipe', 'pipe'] })
  } catch {
    return // no git here; the contract guards are covered by the tests above
  }
  try {
    const { result } = await provision(
      { ok: true, repoPath: dir, branch: 'fix/ssbd-mz1w', reused: true, isLinkedWorktree: true },
      { repoPath: dir, beadId: 'ssbd-mz1w', branchPrefix: 'fix' },
    )
    assert.equal(result.ok, false, 'git says this is a MAIN working tree; a claim to the contrary is not evidence')
    assert.equal(result.repoPath, null)
    assert.match(String(result.blocked[0]), /MAIN working tree/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

// ── The settle guard (HOLE 2): never commit in a tree nobody verified ─────────
//
// settle commits uncommitted work and then runs skillspoke-pr on the CURRENT branch. If
// the workspace step hands back a main working tree on main, an unguarded settle COMMITS
// the work there — strictly worse than the original incident, which left it uncommitted
// and therefore recoverable.

for (const { file } of COMPOSITES) {
  test(`${file}: settle REFUSES to commit when the workspace tree was never verified`, async () => {
    const { result, calls } = await run(file, {
      workspace: { ok: true, repoPath: CALLER_REPO, branch: 'main', reused: true },
    })
    assert.ok(
      !calls.some((c) => c.kind === 'agent' && c.label === 'settle:land-work'),
      'settle must not be dispatched into a main working tree on main — that COMMITS the work onto main',
    )
    assert.equal(result.ok, false)
    assert.equal(result.settled, 'blocked')
    assert.ok(result.orphaned, 'refusing to commit strands the work — say so; that is what an orphan report is for')
    assert.equal(result.orphaned.worktree, CALLER_REPO, 'the report must name the tree the work is sitting in')
    assert.match(String(result.orphaned.blocked[0]), /refused to commit/)
  })

  test(`${file}: settle REFUSES a verified worktree that is nonetheless on the default branch`, async () => {
    const { result, calls } = await run(file, {
      workspace: { ok: true, repoPath: WORKTREE, branch: 'master', reused: true, isLinkedWorktree: true },
    })
    assert.ok(!calls.some((c) => c.kind === 'agent' && c.label === 'settle:land-work'))
    assert.equal(result.settled, 'blocked')
    assert.match(String(result.orphaned.blocked[0]), /master/, 'skillspoke-pr runs on the CURRENT branch — name it')
  })

  test(`${file}: a failed workspace step means settle touches NOTHING, least of all the caller's repo`, async () => {
    // settleRepoPath used to be seeded with `bead.repoPath`, so a run that died in or
    // before the workspace step sent settle into the caller's MAIN repository to commit.
    const { result, calls } = await run(file, {
      workspace: { ok: false, repoPath: null, branch: null, reused: false, blocked: ['the path is the main working tree on main'] },
    })
    assert.equal(result.stage, 'workspace')
    assert.ok(
      !calls.some((c) => c.kind === 'agent' && c.label === 'settle:land-work'),
      'nothing was written, so there is nothing to land — and the caller\'s repository is not this run\'s to commit in',
    )
    assert.equal(result.orphaned, undefined, 'a run that never established a tree cannot have orphaned anything')
  })
}
