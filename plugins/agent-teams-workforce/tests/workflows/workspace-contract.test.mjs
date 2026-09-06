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

  test(`${file}: a run with no repository RESOLVES one before anything can write — it is never run blind`, async () => {
    // A repository is no longer a dispatch precondition: absent, it is ruled at run time
    // by a read-only step that precedes the worktree. The fixture's resolver yields nothing
    // usable (repo-scoping returns no `repos`; bug-triage locates a path outside the
    // allowlist), so the run must stop at the resolution stage with NO writing phase reached.
    const { result, calls } = await run(file, {
      workspace: OK_WORKSPACE,
      args: { bead: { id: 'ssbd-mz1w', title: 'w', description: 'd' } },
    })
    const names = calls.filter((c) => c.kind === 'workflow').map((c) => c.name)
    const resolver = file === 'bug-fix.js' ? 'agent-teams-workforce:bug-triage' : 'agent-teams-workforce:repo-scoping'
    assert.equal(names[0], resolver, 'the FIRST workflow dispatched is the one that rules the repository')
    assert.ok(names.indexOf(resolver) < names.indexOf('agent-teams-workforce:workspace') || !names.includes('agent-teams-workforce:workspace'), 'no tree exists before the repository is known')
    if (file === 'bug-fix.js') {
      // The fixture's triage locates '/SOMEWHERE/ELSE', which passes the allowlist, so the
      // run continues into the worktree — established from the LOCATED repository.
      const ws = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:workspace')
      assert.ok(ws, 'the worktree is established once triage has located the repository')
      assert.equal(ws.payload.repoPath, '/SOMEWHERE/ELSE', 'from the repository triage located')
      assert.ok(names.indexOf(resolver) < names.indexOf('agent-teams-workforce:workspace'), 'triage precedes the worktree on this path')
    } else {
      assert.equal(result.ok, false)
      assert.equal(result.stage, 'repo-resolution', 'the run names the stage it stopped at')
      assert.match(String(result.headline), /repoPath/, 'the refusal must name what is missing')
      assert.ok(!names.includes(writer), 'no writing phase may run while the repository is unknown')
      assert.ok(!names.includes('agent-teams-workforce:workspace'), 'no tree is cut for a run with no repository')
    }
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
    args: { repoPath: CALLER_REPO, beadId: 'ssbd-mz1w', branchPrefix: 'fix', purpose: 'a bug' },
    agentImpl: (call) =>
      call.label === 'workspace:independent-verify'
        ? {
            ok: true,
            gitDir: `${CALLER_REPO}/.git/worktrees/ssbd-mz1w`,
            gitCommonDir: `${CALLER_REPO}/.git`,
            branch: 'fix/ssbd-mz1w',
            callerCommonDir: `${CALLER_REPO}/.git`,
            callerDefaultBranch: 'main',
          }
        : { ok: true, repoPath: `${WORKTREE}  `, branch: '', reused: true, isLinkedWorktree: true, evidence: 'x' },
  })
  assert.equal(result.ok, true)
  assert.equal(result.repoPath, WORKTREE, 'the path is trimmed — a trailing space silently breaks every git -C after it')
  assert.equal(result.branch, 'fix/ssbd-mz1w', 'an unreported branch falls back to the one this step asked for')
  assert.equal(result.reused, true)
  assert.equal(result.independentlyVerified, true, 'the composites refuse a result that carries no affirmative verification')
  assert.match(calls[0].prompt, /worktree add -b/, 'the provisioning instruction must actually be in the prompt')
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

test('workspace.js: the verification is a SECOND, separate dispatch — not the provisioner grading itself', async () => {
  const { calls } = await provision({ ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true })
  const labels = calls.filter((c) => c.kind === 'agent').map((c) => c.label)
  assert.deepEqual(labels, ['workspace:provision', 'workspace:independent-verify'], 'two dispatches, provision first')

  const provisionCall = calls.find((c) => c.label === 'workspace:provision')
  const verifyCall = calls.find((c) => c.label === 'workspace:independent-verify')
  assert.notEqual(
    verifyCall.opts.agentType,
    provisionCall.opts.agentType,
    'a checker that is the same agent as its maker shares its blind spots and agrees for the same wrong reason',
  )
})

test('workspace.js: the verifier is never shown what the provisioner claimed', async () => {
  // A verifier that is shown the answer is not independent. It must be told WHERE to
  // look — it cannot inspect a path it was not given — but nothing about the claim.
  const { calls } = await provision({
    ok: true,
    repoPath: WORKTREE,
    branch: 'fix/ssbd-mz1w',
    reused: true,
    isLinkedWorktree: true,
    evidence: 'the provisioner said it verified everything',
  })
  const prompt = calls.find((c) => c.label === 'workspace:independent-verify').prompt
  assert.ok(prompt.includes(WORKTREE), 'it must be told which path to inspect')
  assert.ok(prompt.includes(CALLER_REPO), 'and which repository that path is supposed to belong to')
  for (const leak of ['isLinkedWorktree', 'fix/ssbd-mz1w', 'reused', 'the provisioner said']) {
    assert.ok(!prompt.includes(leak), `the verifier must not be told "${leak}" — that is the answer it exists to obtain independently`)
  }
})

test('workspace.js: an independent report that CONTRADICTS the claim refuses', async () => {
  // The affirmative lie: a provisioner reporting a linked worktree on a feature branch
  // while git says the path is a MAIN working tree. No pure comparison can catch this;
  // only a second account can.
  const { result } = await provision(
    { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: true, isLinkedWorktree: true },
    undefined,
    { ok: true, gitDir: CALLER_COMMON_DIR, gitCommonDir: CALLER_COMMON_DIR, branch: 'fix/ssbd-mz1w', callerCommonDir: CALLER_COMMON_DIR, callerDefaultBranch: 'main' },
  )
  assert.equal(result.ok, false, 'git says MAIN working tree; a claim to the contrary is not evidence')
  assert.equal(result.repoPath, null)
  assert.match(String(result.blocked[0]), /MAIN working tree/)
})

test('workspace.js: the two accounts must agree about the BRANCH', async () => {
  const { result } = await provision(
    { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: true, isLinkedWorktree: true },
    undefined,
    honestReport('main'),
  )
  assert.equal(result.ok, false, 'a tree whose own branch is in dispute is not a tree any writing phase may inherit')
  assert.equal(result.repoPath, null)
})

test('workspace.js: NO independent report at all refuses — it is the primary control, not an extra', async () => {
  // 6.0.6's git layer was allowed to fall through when unavailable, because two other
  // guards still stood. This replaces the layer those guards could not cover, so falling
  // through here would restore the exact hole it exists to close.
  for (const verifier of [null, undefined, { ok: false }, {}, { ok: true, gitDir: '', gitCommonDir: '', branch: '', callerCommonDir: '' }]) {
    const { result } = await provision(
      { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true },
      undefined,
      verifier === undefined ? null : verifier,
    )
    assert.equal(result.ok, false, `verifier ${JSON.stringify(verifier)} must refuse — an unverified tree is not a workspace`)
    assert.equal(result.repoPath, null)
  }
})

// ── RESIDUAL 1: the tree must belong to the repository the CALLER named ───────
//
// Proven against 6.0.6: the caller asks for repo A, the provisioner returns a GENUINE
// linked worktree of unrelated repo B on a real feature branch, and it was ACCEPTED —
// both existing guards pass, because it really is a linked worktree on a non-default
// branch. Every writing phase then works in repo B and settle opens a PR against repo B.
// Linked worktrees of one repository all share that repository's git-common-dir, so
// comparing the two absolute common-dirs settles it exactly.

test('workspace.js: a genuine worktree of the WRONG repository is refused', async () => {
  const OTHER = '/repos/SkillSpoke-unrelated-service'
  const { result } = await provision(
    // The path is the one this script BUILDS, so it passes the allowlist and the
    // built-here check; only git can tell that the tree sitting there is repo B's.
    { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true },
    undefined,
    {
      ok: true,
      // A real linked worktree — git-dir differs from git-common-dir — just of repo B.
      gitDir: `${OTHER}/.git/worktrees/x-unrelated`,
      gitCommonDir: `${OTHER}/.git`,
      branch: 'fix/ssbd-mz1w',
      callerCommonDir: CALLER_COMMON_DIR,
      callerDefaultBranch: 'main',
    },
  )
  assert.equal(result.ok, false, 'a real worktree of the wrong repository is still the wrong repository')
  assert.equal(result.repoPath, null)
  assert.match(String(result.blocked[0]), /DIFFERENT repository/, 'the refusal must name what it actually is')
})

// ── RESIDUAL 3: `main` and `master` are a FLOOR, not the whole test ───────────

test('workspace.js: a repo whose default is `develop` refuses a tree checked out on develop', async () => {
  const { result } = await provision(
    { ok: true, repoPath: WORKTREE, branch: 'develop', reused: true, isLinkedWorktree: true },
    undefined,
    { ...honestReport('develop'), callerDefaultBranch: 'develop' },
  )
  assert.equal(result.ok, false, 'the default branch is whatever THIS repository says it is, not a hardcoded pair')
  assert.equal(result.repoPath, null)
  assert.match(String(result.blocked[0]), /develop/)
})

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

test('workspace.js: the verified result carries the real default branch to the settle guards', async () => {
  const { result } = await provision(
    { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true },
    undefined,
    { ...honestReport(), callerDefaultBranch: 'trunk' },
  )
  assert.equal(result.ok, true)
  assert.equal(result.defaultBranch, 'trunk', 'settle must test against THIS repo default, not a hardcoded pair')
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

test('workspace.js: the provisioning prompt ASKS for every field the script refuses without', async () => {
  const { calls } = await provision({ ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true })
  const call = calls.find((c) => c.label === 'workspace:provision')
  assert.match(call.prompt, /isLinkedWorktree/, 'guard (a) refuses the run over this field, so the instruction must name it')
  assert.ok(
    call.opts.schema.required.includes('isLinkedWorktree'),
    'a field the script treats as mandatory must be mandatory in the schema too — optional invited the omission',
  )
})

test('workspace.js: a REUSED tree is verified, not merely reported — both reuse paths reach step 6', async () => {
  const { calls } = await provision({ ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: true, isLinkedWorktree: true })
  const prompt = calls.find((c) => c.label === 'workspace:provision').prompt
  assert.ok(
    !/reused=true and stop/.test(prompt),
    'stopping at reuse skips the only step that produces isLinkedWorktree, so the run refuses a tree that was fine',
  )
  for (const step of [/STEP 1[\s\S]*?run STEP 6 against it/, /STEP 3[\s\S]*?run STEP 6 against it/]) {
    assert.match(prompt, step, 'every path to a reported tree — cut or reused — must run the verification')
  }
})


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

for (const reused of [true, false]) {
  test(`workspace.js: THE ssbd-2dqw reproduction — a misfiled repoPath (reused=${reused}) no longer refuses a good tree`, async () => {
    const { result, calls } = await provision(
      // The misfill: the tree it actually cut is at WORKTREE and its own evidence says so,
      // but the FIELD carries the repository it was handed.
      { ok: true, repoPath: CALLER_REPO, branch: 'fix/ssbd-mz1w', reused, isLinkedWorktree: true, evidence: 'cut a new linked worktree' },
      undefined,
      {
        ok: true,
        // FIRST PATH — the tree step 5 was told to cut. It is really there.
        gitDir: WORKTREE_GIT_DIR,
        gitCommonDir: CALLER_COMMON_DIR,
        branch: 'fix/ssbd-mz1w',
        // SECOND PATH — the caller's repository, which really is a main working tree.
        ...callerIsMainTree,
      },
    )
    assert.equal(result.ok, true, 'a tree git confirms is fine must not be refused because a field named the wrong path')
    assert.equal(result.repoPath, WORKTREE, 'the tree returned is the one git verified, not the one the field named')
    assert.equal(result.branch, 'fix/ssbd-mz1w')
    assert.equal(result.independentlyVerified, true)

    const verify = calls.find((c) => c.label === 'workspace:independent-verify')
    assert.ok(verify.prompt.includes(WORKTREE), 'the verifier is pointed at the built path, not at the misfiled one')
    assert.ok(
      result.blocked.some((b) => /not adopted|not taken on/.test(String(b))),
      'and the disagreement is recorded rather than swallowed',
    )
  })
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

test('workspace.js: reuse IN PLACE still works — the caller\'s own path wins when git says it is a worktree', async () => {
  // The one case the script genuinely cannot derive, and the reason the caller's path is
  // on the acceptable list at all. Nothing exists at the built path; the path the caller
  // handed in IS a linked worktree on a feature branch. It must be taken — and taken on
  // git's evidence, not on the provisioner having said `reused`.
  const CALLER_WT_GIT_DIR = `${CALLER_COMMON_DIR}/worktrees/handed-in`
  const { result } = await provision(
    { ok: true, repoPath: CALLER_REPO, branch: 'fix/ssbd-mz1w', reused: true, isLinkedWorktree: true },
    undefined,
    {
      ok: true,
      // FIRST PATH — nothing is there; an empty observation, honestly reported.
      gitDir: '',
      gitCommonDir: '',
      branch: '',
      // SECOND PATH — a genuine linked worktree of the caller's repository.
      callerGitDir: CALLER_WT_GIT_DIR,
      callerCommonDir: CALLER_COMMON_DIR,
      callerBranch: 'fix/ssbd-mz1w',
      callerDefaultBranch: 'main',
    },
  )
  assert.equal(result.ok, true, 'a resumed run handed its own established worktree must land in it')
  assert.equal(result.repoPath, CALLER_REPO)
  assert.equal(result.branch, 'fix/ssbd-mz1w')
})

test('workspace.js: when NEITHER candidate is a usable worktree the step still refuses', async () => {
  // The fallback must not become a way through. Nothing at the built path, and the
  // caller's path is the main working tree on main — the original incident.
  const { result } = await provision(
    { ok: true, repoPath: CALLER_REPO, branch: 'fix/ssbd-mz1w', reused: true, isLinkedWorktree: true },
    undefined,
    { ok: true, gitDir: '', gitCommonDir: '', branch: '', ...callerIsMainTree },
  )
  assert.equal(result.ok, false, 'no tree means no workspace — falling back to the caller\'s repository is the bug')
  assert.equal(result.repoPath, null)
  assert.match(String(result.blocked[0]), /incomplete for/, 'the refusal must account for BOTH candidates')
  assert.match(String(result.blocked[0]), /MAIN working tree/)
})

test('workspace.js: the two accounts must still agree about the branch of the tree BOTH name', async () => {
  // Guard (e) survives the restructure: where the chosen tree IS the one the provisioner
  // named, a branch it reported over a tree git says is on another one is the affirmative
  // lie the second dispatch exists to catch. Neither branch here is a default branch, so
  // this is the disagreement itself failing, not the default-branch floor.
  const { result } = await provision(
    { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true },
    undefined,
    {
      ok: true,
      gitDir: WORKTREE_GIT_DIR,
      gitCommonDir: CALLER_COMMON_DIR,
      branch: 'fix/some-other-bead',
      ...callerIsMainTree,
    },
  )
  assert.equal(result.ok, false, 'a tree whose own branch is in dispute is not a tree any writing phase may inherit')
  assert.equal(result.repoPath, null)
  assert.match(String(result.blocked[0]), /disagree/)
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
  // RESIDUAL 5 — the WRITING phases get the backstop settle already had.
  //
  // The composites used to accept the workspace result on `ok === true && repoPath`
  // alone. A 6.0.5-shaped result — version skew, a bypassed or stale plugin cache, any
  // workspace mini that never ran the independent check — matches that exactly, and
  // tdd-red, tdd-green and tdd-refactor each received whatever path it carried while only
  // settle refused. The refusal now happens BEFORE the first writing phase, which is
  // strictly better than orphaning: nothing was written, so there is nothing to strand.
  test(`${file}: a workspace result carrying no independent verification REFUSES the run`, async () => {
    const { result, calls } = await run(file, {
      workspace: { ok: true, repoPath: CALLER_REPO, branch: 'main', reused: true },
    })
    assert.equal(result.ok, false)
    assert.equal(result.stage, 'workspace', 'the run must name where it stopped')
    assert.match(
      String(result.workspaceShapeFault),
      /isLinkedWorktree|independent/,
      'the refusal must name which part of the contract was missing',
    )
    const names = calls.filter((c) => c.kind === 'workflow').map((c) => c.name)
    assert.deepEqual(names, ['agent-teams-workforce:workspace'], 'no phase that could WRITE may be dispatched')
    assert.ok(
      !calls.some((c) => c.kind === 'agent' && c.label === 'settle:land-work'),
      'settle must not be dispatched into a main working tree on main — that COMMITS the work onto main',
    )
    assert.equal(result.orphaned, undefined, 'nothing was written, so nothing was orphaned')
  })

  test(`${file}: a 6.0.5-shaped result is refused even when the tree it names is fine`, async () => {
    // The path here is a perfectly good worktree on a feature branch. It is refused
    // anyway, because the result carrying it never claimed to have been verified — and a
    // stale cache returning a plausible path is exactly the case this closes.
    const { result, calls } = await run(file, {
      workspace: { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-mz1w', reused: false, isLinkedWorktree: true },
    })
    assert.equal(result.ok, false)
    assert.equal(result.stage, 'workspace')
    assert.match(String(result.workspaceShapeFault), /independentlyVerified/)
    assert.deepEqual(
      calls.filter((c) => c.kind === 'workflow').map((c) => c.name),
      ['agent-teams-workforce:workspace'],
    )
  })

  test(`${file}: settle REFUSES a verified worktree that is nonetheless on the default branch`, async () => {
    // Defense in depth: the workspace mini refuses a default branch itself, so this can
    // only arise if something between the two substitutes a tree. settle COMMITS and then
    // pushes the CURRENT branch, so it re-checks rather than trusting.
    const { result, calls } = await run(file, {
      workspace: { ...OK_WORKSPACE, repoPath: WORKTREE, branch: 'master', reused: true },
    })
    assert.ok(!calls.some((c) => c.kind === 'agent' && c.label === 'settle:land-work'))
    assert.equal(result.settled, 'blocked')
    assert.match(String(result.orphaned.blocked[0]), /master/, 'skillspoke-pr runs on the CURRENT branch — name it')
  })

  // RESIDUAL 3 — the settle guard's hardcoded {main, master} is a FLOOR, not the test.
  test(`${file}: settle refuses THIS repository's default branch, even when it is not main`, async () => {
    const { result, calls } = await run(file, {
      workspace: { ...OK_WORKSPACE, repoPath: WORKTREE, branch: 'develop', reused: true, defaultBranch: 'develop' },
    })
    assert.ok(!calls.some((c) => c.kind === 'agent' && c.label === 'settle:land-work'))
    assert.equal(result.settled, 'blocked')
    assert.match(String(result.orphaned.blocked[0]), /develop/, 'a repo defaulting to develop was previously unprotected')
  })

  test(`${file}: settle still LANDS work on an ordinary branch that merely resembles a default`, async () => {
    // The floor must not widen into a guess: `develop` in a repo that defaults to main is
    // an ordinary branch, and refusing it would strand real work.
    const { calls } = await run(file, {
      workspace: { ...OK_WORKSPACE, repoPath: WORKTREE, branch: 'develop', reused: true, defaultBranch: 'main' },
    })
    assert.equal(
      calls.filter((c) => c.kind === 'agent' && c.label === 'settle:land-work').length,
      1,
      'work on a non-default branch must still be landed',
    )
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
