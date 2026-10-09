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
]
// The suite runner: a Red run shows the new test in Red's file failing; every other run is green.
const suiteRun = (call) =>
  String(call.payload.label || '').startsWith('red')
    ? { ok: false, command: 'task test', exitCode: 1, failing: [{ kind: 'test', file: 't', test: 'test_new', line: 'FAILED t::test_new' }], tail: '', summary: '1 failed' }
    : { ok: true, command: 'task test', exitCode: 0, failing: [], tail: '', summary: '3 passed' }


const CALLER_REPO = '/repos/shared-chassis'
const WORKTREE = '/repos/shared-chassis/.worktrees/ssbd-mz1w-shared-chassis'

/** Drive a composite with a scripted workspace result; everything else passes. */
function run(file, { workspace, args } = {}) {
  return runWorkflowScript(path.join(WF, file), {
    args: args || { bead: { id: 'ssbd-mz1w', title: 'w', description: 'd', repoPath: CALLER_REPO, story: { id: 'ssbd-st01', title: 'the story' } } },
    agentImpl: (call) => (/:tests-(before|after)$/.test(String(call.label)) ? { exitCode: 0, stdout: 't\tabc\n' } : { written: true, treeClean: true, hasWork: false, branch: 'b', prUrl: '' }),
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') return workspace
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { repoPath: '/SOMEWHERE/ELSE', scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      }
      if (call.name === 'agent-teams-workforce:suite-run') return suiteRun(call)
      // task-to-deploy has no gates: the suite runner reports Red, then green, so it reaches
      // the Commit phase. bug-fix's gates escalate after its first writing phase.
      if (call.name === 'agent-teams-workforce:tdd-green') return { greenConfirmed: true, noRegressions: true, evidence: 'e', changedFiles: [] }
      if (call.name === 'agent-teams-workforce:tdd-refactor') return { testsGreen: true }
      if (call.name.endsWith('gate-enforce')) {
        return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
      }
      return { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', changedFiles: [] }
    },
  })
}

const OK_WORKSPACE = {
  ok: true,
  repoPath: WORKTREE,
  branch: 'fix/ssbd-mz1w',
  reused: false,
  isLinkedWorktree: true,
  independentlyVerified: true,
  defaultBranch: 'main',
}

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

  test(`${file}: a run with no repository never runs blind`, async () => {
    // A Task's contract names its repository; with none the run stops at input with NO
    // writing phase reached. A bug's triage locates the repository before the worktree.
    const { result, calls } = await run(file, {
      workspace: OK_WORKSPACE,
      args: { bead: { id: 'ssbd-mz1w', title: 'w', description: 'd' } },
    })
    const names = calls.filter((c) => c.kind === 'workflow').map((c) => c.name)
    const resolver = 'agent-teams-workforce:bug-triage'
    if (file === 'bug-fix.js') {
      assert.equal(names[0], resolver, 'the FIRST workflow dispatched is the triage that locates the repository')
      // The fixture's triage locates '/SOMEWHERE/ELSE', which passes the allowlist, so the
      // run continues into the worktree — established from the LOCATED repository.
      const ws = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:workspace')
      assert.ok(ws, 'the worktree is established once triage has located the repository')
      assert.equal(ws.payload.repoPath, '/SOMEWHERE/ELSE', 'from the repository triage located')
      assert.ok(names.indexOf(resolver) < names.indexOf('agent-teams-workforce:workspace'), 'triage precedes the worktree on this path')
    } else {
      assert.equal(result.ok, false)
      assert.equal(result.stage, 'input', 'the run names the stage it stopped at')
      assert.match(String(result.headline), /repoPath/, 'the refusal must name what is missing')
      assert.deepEqual(names, [], 'nothing is dispatched for an incomplete build contract')
      assert.ok(!names.includes(writer), 'no writing phase may run while the repository is unknown')
      assert.ok(!names.includes('agent-teams-workforce:workspace'), 'no tree is cut for a run with no repository')
    }
  })

  if (file === 'bug-fix.js') test(`${file}: settle targets the WORKSPACE tree, so there is always a branch to push`, async () => {
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

// ── SEGREGATION OF DUTIES (replaces the removed in-script git layer) ───────────
//
// 6.0.6 cross-examined the tree by shelling out to git from the script. The real runner
// refuses a dynamic import STATICALLY, so that script could not load at all — and it was
// the first phase of all three composites. A workflow script gets only args, agent,
// workflow, phase, log, parallel and budget: no filesystem, no process spawning, no
// module loader. A script-side git check is impossible BY CONSTRUCTION.
//
// What that layer was FOR is still real: the pure guards test what the provisioner SAID,
// and neither can catch a provisioner that says the right thing while handing back
// something else. So the check became this plugin's own doctrine instead — a SECOND agent,
// dispatched separately, read-only, told only where to look and never what was claimed.
// The script rules on the two accounts. An affirmative lie now needs two independently
// dispatched agents to agree on it.

// ── RESIDUAL 1: the tree must belong to the repository the CALLER named ───────
//
// Proven against 6.0.6: the caller asks for repo A, the provisioner returns a GENUINE
// linked worktree of unrelated repo B on a real feature branch, and it was ACCEPTED —
// both existing guards pass, because it really is a linked worktree on a non-default
// branch. Every writing phase then works in repo B and settle opens a PR against repo B.
// Linked worktrees of one repository all share that repository's git-common-dir, so
// comparing the two absolute common-dirs settles it exactly.

// ── RESIDUAL 3: `main` and `master` are a FLOOR, not the whole test ───────────

test('workspace.js: `develop` is refused only where it IS the default — elsewhere it is a normal branch', async () => {
  // The floor must not widen into a guess. In a repo whose default is main, `develop` is
  // an ordinary branch and refusing it would break real work.
  const { result } = await provision(
    { ok: true, repoPath: WORKTREE, branch: 'develop', reused: true, isLinkedWorktree: true },
    undefined,
    { ...honestReport('develop'), callerDefaultBranch: 'main' },
  )
  assert.equal(result.ok, true, 'a non-default branch is a fine place to work, whatever it is called')
  assert.equal(result.repoPath, WORKTREE)
})

test('workspace.js: an unobtainable origin/HEAD narrows to the floor rather than guessing', async () => {
  const { result } = await provision(
    { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true },
    undefined,
    { ...honestReport('fix/ssbd-mz1w'), callerDefaultBranch: '' },
  )
  assert.equal(result.ok, true, 'a missing ref must not block real work')
  assert.equal(result.defaultBranch, null, 'and must be reported as unknown, not as an assumed "main"')

  const onMain = await provision(
    { ok: true, repoPath: WORKTREE, branch: 'master', reused: true, isLinkedWorktree: true },
    undefined,
    { ...honestReport('master'), callerDefaultBranch: '' },
  )
  assert.equal(onMain.result.ok, false, 'the floor still holds with no origin/HEAD to consult')
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

// The workspace step now makes TWO dispatches, and they are deliberately different
// agents doing different jobs: `workspace:provision` CREATES the tree and reports what it
// believes it created, and `workspace:independent-verify` is told only WHERE to look and
// reports what git printed. So a fixture must script them separately — scripting one
// result for both would model a single agent grading its own homework, which is the exact
// arrangement this design exists to end.
const CALLER_COMMON_DIR = `${CALLER_REPO}/.git`
const WORKTREE_GIT_DIR = `${CALLER_REPO}/.git/worktrees/ssbd-mz1w-shared-chassis`

/** A truthful independent report for a real linked worktree of CALLER_REPO. */
const honestReport = (branch = 'fix/ssbd-mz1w') => ({
  ok: true,
  gitDir: WORKTREE_GIT_DIR,
  gitCommonDir: CALLER_COMMON_DIR,
  branch,
  callerCommonDir: CALLER_COMMON_DIR,
  callerDefaultBranch: 'main',
  evidence: 'git output',
})

/**
 * Drive workspace.js with a scripted provisioner result and a scripted independent report.
 *
 * `verifier` defaults to a report that CORROBORATES the provisioner, so a test that cares
 * only about the pure-comparison guards is not accidentally passing because the second
 * dispatch refused for an unrelated reason.
 */
function provision(provisioned, args, verifier) {
  return runWorkflowScript(WS, {
    args: args || { repoPath: CALLER_REPO, beadId: 'ssbd-mz1w', branchPrefix: 'fix' },
    agentImpl: (call) => {
      if (call.label === 'workspace:independent-verify') {
        if (verifier !== undefined) return verifier
        return honestReport(String((provisioned && provisioned.branch) || 'fix/ssbd-mz1w').trim() || 'fix/ssbd-mz1w')
      }
      return provisioned
    },
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

// ── ssbd-89pi: a guard nobody could satisfy on purpose ────────────────────────
//
// Guard (a) refuses the run unless the provisioner affirms isLinkedWorktree=true. The
// prompt never named that field, the schema left it optional, and BOTH reuse paths told
// the provisioner to report and stop BEFORE step 6 — the step that produces the finding.
// So a run that reused an existing tree could only clear the guard by luck, and every
// re-dispatch of a bead whose tree already existed hit the same refusal identically.
//
// Refusing an unearned claim and never asking for the earned one are the same bug from
// two ends. These assert the asking end; guard (a) above is the refusing end.

// ── ssbd-2dqw: the provisioner's FLAGS chose which tree got verified ──────────
//
// ssbd-4qzi fixed half of this and the other half reproduced it within the week.
//
// Both incidents are one sentence: the script pointed its one independent control at the
// tree an AGENT named. In 4qzi the provisioner cut the right tree, verified it, wrote the
// evidence out in full — and filled `repoPath` with the caller's REPOSITORY, which is a
// legal member of the acceptable set because reuse-in-place needs it there. The verifier
// was dispatched at the main working tree, reported one, and a correct worktree was
// refused. The fix pinned the CUT path and left the REUSE path adopting whatever was
// reported. 2dqw arrived with the same misfill plus `reused: true`, took the unpinned
// branch, and failed identically — twice, on consecutive dispatches.
//
// So no agent-authored value selects the tree any more. The script names the candidates
// it BUILT, git characterises every one of them in a single read-only turn, and the first
// one git shows to be a linked worktree of the caller's repository on a writable branch
// wins. These tests are the two incidents, and the case that must keep working.

/** The caller's path as git sees a MAIN working tree: git-dir and git-common-dir equal. */
const callerIsMainTree = {
  callerGitDir: CALLER_COMMON_DIR,
  callerCommonDir: CALLER_COMMON_DIR,
  callerBranch: 'main',
  callerDefaultBranch: 'main',
}

test('workspace.js: `reused` is inert — it cannot steer the verification either way', async () => {
  // The whole class: an agent-authored boolean must not decide which tree the only
  // independent control inspects. Same inputs, both spellings, same ruling.
  const honest = {
    ok: true,
    gitDir: WORKTREE_GIT_DIR,
    gitCommonDir: CALLER_COMMON_DIR,
    branch: 'fix/ssbd-mz1w',
    ...callerIsMainTree,
  }
  const yes = await provision({ ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: true, isLinkedWorktree: true }, undefined, honest)
  const no = await provision({ ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true }, undefined, honest)
  assert.equal(yes.result.repoPath, no.result.repoPath, 'the flag must not change which tree is returned')
  assert.equal(yes.result.ok, no.result.ok)
  assert.equal(yes.result.repoPath, WORKTREE)
})

// The 6.0.6 in-script git cross-check is GONE, and could never have worked: the runner
// refuses a dynamic import statically, so the script carrying it could not load at all.
// Its job — catching a claim the provisioner did not earn — is now done by the
// independent second dispatch, covered by the segregation-of-duties tests above.
// scripts/check-workflow-syntax.mjs and this suite's own harness now both refuse any
// workflow script that reaches for a module loader, so the construct cannot come back.

test('no workflow script reaches for a construct the runner refuses', async () => {
  const { findForbiddenConstructs } = await import('../../scripts/workflow-runner-constraints.mjs')
  const fs = await import('node:fs')
  const offenders = []
  for (const f of fs.readdirSync(WF).filter((n) => n.endsWith('.js'))) {
    // RAW bytes, comments and strings included: how the runner detects the construct is
    // undocumented, so a mention in a comment is not worth risking a second outage over.
    for (const hit of findForbiddenConstructs(fs.readFileSync(path.join(WF, f), 'utf8'))) {
      offenders.push(`${f}:${hit.line} ${hit.name}`)
    }
  }
  assert.deepEqual(offenders, [], `these scripts CANNOT LOAD in production:\n  ${offenders.join('\n  ')}`)
})

// ── The settle guard (HOLE 2): never commit in a tree nobody verified ─────────
//
// settle commits uncommitted work and then runs skillspoke-pr on the CURRENT branch. If
// the workspace step hands back a main working tree on main, an unguarded settle COMMITS
// the work there — strictly worse than the original incident, which left it uncommitted
// and therefore recoverable.

for (const { file } of COMPOSITES) {
  test(`${file}: settle still LANDS work on an ordinary branch that merely resembles a default`, async () => {
    // The floor must not widen into a guess: `develop` in a repo that defaults to main is
    // an ordinary branch, and refusing it would strand real work.
    const { calls } = await run(file, {
      workspace: { ...OK_WORKSPACE, repoPath: WORKTREE, branch: 'develop', reused: true, defaultBranch: 'main' },
    })
    if (file === 'bug-fix.js') {
      assert.equal(
        calls.filter((c) => c.kind === 'agent' && c.label === 'settle:land-work').length,
        1,
        'work on a non-default branch must still be landed',
      )
      return
    }
    // task-to-deploy commits the Task to the Story branch and stops there.
    const commits = calls.filter((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:settle')
    assert.equal(commits.length, 1, 'work on a non-default branch must still be committed')
    assert.equal(commits[0].payload.commitOnly, true, 'the Task commits to the Story branch; it does not land')
    assert.equal(commits[0].payload.repoPath, WORKTREE, 'the commit happens in the tree the phases wrote in')
    assert.equal(commits[0].payload.branch, 'develop')
    assert.equal(calls.filter((c) => c.kind === 'agent' && c.label === 'settle:commit').length, 1)
  })

  test(`${file}: a failed workspace step means settle touches NOTHING, least of all the caller's repo`, async () => {
    // settleRepoPath used to be seeded with `bead.repoPath`, so a run that died in or
    // before the workspace step sent settle into the caller's MAIN repository to commit.
    const { result, calls } = await run(file, {
      workspace: { ok: false, repoPath: null, branch: null, reused: false, blocked: ['the path is the main working tree on main'] },
    })
    assert.equal(result.stage, 'workspace')
    assert.ok(
      !calls.some((c) => c.kind === 'agent' && (c.label === 'settle:land-work' || c.label === 'settle:commit')),
      'nothing was written, so there is nothing to land — and the caller\'s repository is not this run\'s to commit in',
    )
    assert.equal(result.orphaned, undefined, 'a run that never established a tree cannot have orphaned anything')
  })
}
