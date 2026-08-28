// ssbd-mfza — a repository is NEVER a dispatch precondition.
//
// task-to-deploy, infra-change and bug-fix refused a run with no `bead.repoPath` at the
// input stage, with zero agents dispatched. That made the repository something the CALLER
// had to know in advance, and the only place a caller could get it was a value cached on
// the bead — a hand-maintained fact nothing kept current. 129 live work items sat behind
// that gate. The repository is an architecture output and the pipeline already owns the
// step that rules it; these tests pin that the composites now ASK rather than refuse:
//
//   task-to-deploy / infra-change — a read-only agent assembles the statement of work,
//     the repo-scoping mini rules the span for this ONE item, the script picks the single
//     repository, validates the path, and hands it to Workspace. Hints seed the ruling.
//   bug-fix — triage runs FIRST, without a tree, and the repository is a FINDING of the
//     diagnosis beside the blast radius; the worktree is cut from what triage located.
//
// A caller that supplies repoPath pays nothing: no resolver is dispatched.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, readWorkflowSource } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const WORKTREE = '/repos/.worktrees/ssbd-mfza-web'
const RULED = '/repos/SkillSpoke-web'
const OTHER = '/repos/SkillSpoke-shared-chassis'

const okWorkspace = (repoPath) => ({
  ok: true,
  repoPath: WORKTREE,
  branch: 'feat/ssbd-mfza',
  reused: false,
  isLinkedWorktree: true,
  independentlyVerified: true,
  defaultBranch: 'main',
  caller: repoPath,
})

/** Drive a spec-side composite; `scoping` scripts the repo-scoping mini's return. */
function runSpecSide(file, { bead, scoping, brief } = {}) {
  return runWorkflowScript(path.join(WF, file), {
    args: { bead: bead || { id: 'ssbd-mfza', title: 'route the thing', description: 'd' } },
    agentImpl: (call) => {
      if (call.label === 'repo-resolution:brief') return brief === undefined ? { resolved: true, body: 'BRIEF FROM TRACKER', sources: ['ssbd-mfza'] } : brief
      if (call.label === 'settle:land-work') return { treeClean: true, hasWork: false, branch: 'b', prUrl: '' }
      if (call.label === 'ledger:persist') return { written: true, path: '/p.jsonl' }
      return null
    },
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:repo-scoping') return scoping
      if (call.name === 'agent-teams-workforce:workspace') return okWorkspace(call.payload.repoPath)
      if (call.name === 'agent-teams-workforce:spec-freshness') return { fresh: true }
      if (call.name === 'agent-teams-workforce:infra-intent') return { provisioningIntent: 'p', affectedStacks: ['S'] }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        if (call.payload.gate === '1') return { verdict: 'pass', criteria: [], flags: [] }
        return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
      }
      return { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', greenReachable: true, changedFiles: [] }
    },
  })
}

const workflows = (calls) => calls.filter((c) => c.kind === 'workflow').map((c) => c.name)
const RULED_SPAN = { ok: true, repos: [RULED], placements: [{ repoPath: RULED, repoName: 'web', workUnitIds: ['W1'], rationale: 'r' }], newRepos: [], requiredHumanActions: [], spanVerified: true }

for (const file of ['task-to-deploy.js', 'infra-change.js']) {
  test(`${file}: with no repoPath the repository is RULED — brief, then repo-scoping, then Workspace from the ruled path`, async () => {
    const { calls } = await runSpecSide(file, { scoping: RULED_SPAN })
    const names = workflows(calls)
    const brief = calls.find((c) => c.kind === 'agent' && c.label === 'repo-resolution:brief')
    assert.ok(brief, 'a read-only agent assembles the statement of work — a script cannot read files')
    assert.equal(names[0], 'agent-teams-workforce:repo-scoping', 'the ruling is the first workflow dispatched')
    const scoping = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:repo-scoping')
    assert.equal(scoping.payload.prd.id, 'ssbd-mfza', 'the item itself is what is scoped')
    assert.match(scoping.payload.prd.body, /route the thing/, "the item's own statement of work is always in the brief")
    assert.match(scoping.payload.prd.body, /BRIEF FROM TRACKER/, 'and so is what the agent read')
    assert.deepEqual(scoping.payload.architecture, { skipped: true }, 'no architecture ruling is invented for one item')
    const ws = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:workspace')
    assert.equal(ws.payload.repoPath, RULED, 'the worktree is cut from the RULED repository')
    assert.ok(names.indexOf('agent-teams-workforce:repo-scoping') < names.indexOf('agent-teams-workforce:workspace'))
  })

  test(`${file}: a supplied repoPath is the answer — no resolver is dispatched`, async () => {
    const { calls } = await runSpecSide(file, { bead: { id: 'ssbd-mfza', title: 't', description: 'd', repoPath: RULED }, scoping: RULED_SPAN })
    assert.ok(!workflows(calls).includes('agent-teams-workforce:repo-scoping'), 'a known repository is not re-ruled')
    assert.ok(!calls.some((c) => c.kind === 'agent' && c.label === 'repo-resolution:brief'), 'and no brief is assembled')
    assert.equal(workflows(calls)[0], 'agent-teams-workforce:workspace', 'the usual order stands')
  })

  test(`${file}: repoHints reach the ruling as seedRepos — a hint, never an answer`, async () => {
    const { calls } = await runSpecSide(file, { bead: { id: 'ssbd-mfza', title: 't', description: 'd', repoHints: ['SkillSpoke-web', ' '] }, scoping: RULED_SPAN })
    const scoping = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:repo-scoping')
    assert.deepEqual(scoping.payload.seedRepos, ['SkillSpoke-web'], 'blank hints are dropped, real ones are forwarded')
    const ws = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:workspace')
    assert.equal(ws.payload.repoPath, RULED, 'the RULING decides, not the hint')
  })

  test(`${file}: a span of several repositories takes the one hosting the most work and FLAGS the rest`, async () => {
    const { calls, logs } = await runSpecSide(file, {
      scoping: {
        ...RULED_SPAN,
        repos: [OTHER, RULED],
        placements: [
          { repoPath: OTHER, repoName: 'chassis', workUnitIds: ['W2'], rationale: 'r' },
          { repoPath: RULED, repoName: 'web', workUnitIds: ['W1', 'W3'], rationale: 'r' },
        ],
      },
    })
    const ws = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:workspace')
    assert.equal(ws.payload.repoPath, RULED, 'the repository with the most work units wins')
    assert.ok(logs.some((l) => /spanned 2 repositories/.test(l)), 'the ambiguity is said out loud, not swallowed')
  })

  test(`${file}: a ruling that names only a repository the project does not have is a REQUIRED HUMAN ACTION, not a guess`, async () => {
    const { result, calls } = await runSpecSide(file, {
      scoping: {
        ok: true,
        repos: [],
        placements: [],
        newRepos: [{ name: 'SkillSpoke-new-thing', purpose: 'p' }],
        requiredHumanActions: ['create repository SkillSpoke-new-thing'],
        spanVerified: true,
      },
    })
    assert.equal(result.ok, false)
    assert.equal(result.stage, 'repo-resolution')
    assert.deepEqual(result.requiredHumanActions, ['create repository SkillSpoke-new-thing'], 'the action reaches the caller by name')
    assert.equal(result.newRepos.length, 1)
    assert.match(result.headline, /SkillSpoke-new-thing/)
    assert.ok(!workflows(calls).includes('agent-teams-workforce:workspace'), 'nothing is built into a repository that does not exist')
    assert.equal(result.deployedToDev, false)
    assert.equal(result.smokePassed, false)
  })

  test(`${file}: a ruled path outside the allowlist is refused, not used`, async () => {
    const { result, calls } = await runSpecSide(file, { scoping: { ...RULED_SPAN, repos: ['/repos/x; rm -rf /'], placements: [] } })
    assert.equal(result.stage, 'repo-resolution')
    assert.ok(!workflows(calls).includes('agent-teams-workforce:workspace'))
  })

  test(`${file}: a brief agent that fails does not stop the ruling — the item's own text is scoped`, async () => {
    const { calls } = await runSpecSide(file, { brief: { resolved: false, body: '', sources: [], blocked: 'tracker down' }, scoping: RULED_SPAN })
    const scoping = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:repo-scoping')
    assert.ok(scoping, 'the ruling still runs')
    assert.match(scoping.payload.prd.body, /route the thing/)
  })

  test(`${file}: the composite no longer refuses an absent repoPath at input`, () => {
    const src = readWorkflowSource(path.join(WF, file))
    assert.doesNotMatch(src, /no bead\.repoPath supplied — refusing/, 'the input-stage refusal is gone')
    assert.match(src, /enterPhase\('Repo Resolution'\)/, 'and the resolution phase exists')
  })
}

// ── bug-fix: triage first, the repository is a finding ───────────────────────

function runBugFix({ bead, triage } = {}) {
  return runWorkflowScript(path.join(WF, 'bug-fix.js'), {
    args: { bead: bead || { id: 'ssbd-bug1', title: 'it breaks', description: 'd', repoHints: ['SkillSpoke-web'], manifestPath: '/repos/app/.polyrepo/manifest.yaml' } },
    agentImpl: (call) => {
      if (call.label === 'settle:land-work') return { treeClean: true, hasWork: false, branch: 'b', prUrl: '' }
      if (call.label === 'ledger:persist') return { written: true, path: '/p.jsonl' }
      return null
    },
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:bug-triage') return triage(call)
      if (call.name === 'agent-teams-workforce:workspace') return okWorkspace(call.payload.repoPath)
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
      return { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', greenReachable: true, changedFiles: [] }
    },
  })
}

const LOCATED = (call) => ({ bead: call.payload.bead, repoPath: RULED, repoResolution: 'confirmed', scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [], blastRadius: 'b' })

test('bug-fix: with no repoPath, triage runs FIRST and the worktree is cut from the repository it located', async () => {
  const { calls } = await runBugFix({ triage: LOCATED })
  const names = workflows(calls)
  assert.equal(names[0], 'agent-teams-workforce:bug-triage', 'triage is read-only and needs no tree')
  const triage = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:bug-triage')
  assert.equal(triage.payload.bead.repoPath, undefined, 'triage is told the repository is NOT known')
  assert.deepEqual(triage.payload.bead.repoHints, ['SkillSpoke-web'], 'the hints reach the diagnosis')
  assert.equal(triage.payload.bead.manifestPath, '/repos/app/.polyrepo/manifest.yaml')
  const ws = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:workspace')
  assert.equal(ws.payload.repoPath, RULED, 'the worktree is cut from what triage LOCATED')
  const red = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:tdd-red')
  assert.equal(red.payload.contract.repoPath, WORKTREE, 'and every writing phase inherits the worktree, not the repository')
  assert.equal(red.payload.contract.bead.repoPath, WORKTREE)
  assert.equal(workflows(calls).filter((n) => n === 'agent-teams-workforce:bug-triage').length, 1, 'triage runs once')
})

test('bug-fix: with a supplied repoPath the usual order stands — Workspace, then triage inside the tree', async () => {
  const { calls } = await runBugFix({ bead: { id: 'ssbd-bug1', title: 'it breaks', description: 'd', repoPath: RULED }, triage: LOCATED })
  const names = workflows(calls)
  assert.equal(names[0], 'agent-teams-workforce:workspace')
  const triage = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:bug-triage')
  assert.equal(triage.payload.bead.repoPath, WORKTREE, 'triage works inside the tree when one exists')
})

test('bug-fix: a diagnosis that cannot locate the repository stops at repo-resolution with the diagnosis attached', async () => {
  const { result, calls } = await runBugFix({
    triage: (call) => ({ bead: call.payload.bead, repoPath: '', repoResolution: 'examined three repositories; none held the symbol', scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [], blastRadius: 'b', rootCause: 'rc', reproduction: 'rp' }),
  })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'repo-resolution')
  assert.match(result.headline, /none held the symbol/, 'the reason triage gave is carried')
  assert.equal(result.diagnosis.rootCause, 'rc', 'what triage found is not thrown away')
  assert.ok(!workflows(calls).includes('agent-teams-workforce:workspace'), 'no tree is cut for a repository nobody confirmed')
  assert.equal(result.deployedToDev, false)
})

test('bug-fix: a located path outside the allowlist is refused', async () => {
  const { result } = await runBugFix({ triage: (call) => ({ ...LOCATED(call), repoPath: 'relative/path' }) })
  assert.equal(result.stage, 'repo-resolution')
  assert.match(result.headline, /not an absolute path/)
})

test('bug-fix: a bug sized as needs-prd on the triage-first path stops BEFORE any tree is cut', async () => {
  const { result, calls } = await runBugFix({ triage: (call) => ({ ...LOCATED(call), scope: 'needs-prd', scopeRationale: 'changes a contract' }) })
  assert.equal(result.outcome, 'needs-prd')
  assert.equal(result.stage, 'triage')
  assert.ok(!workflows(calls).includes('agent-teams-workforce:workspace'))
})

test('bug-triage: when no repository is supplied the diagnosis is told to LOCATE it, and the schema can carry the answer', async () => {
  const { calls } = await runWorkflowScript(path.join(WF, 'bug-triage.js'), {
    args: { bead: { id: 'ssbd-bug1', title: 'it breaks', description: 'd', repoHints: ['SkillSpoke-web'], manifestPath: '/repos/app/.polyrepo/manifest.yaml' } },
    agentImpl: (call) => {
      if (call.label === 'triage:diagnosis') return { reproduction: 'r', rootCause: 'c', defects: [{ id: 'D1', mechanism: 'm' }], affectedFiles: [], blastRadius: 'b', surfaces: [], repoPath: RULED, repoResolution: 'confirmed' }
      if (call.label === 'triage:sizing') return { scope: 'fix', rationale: 'r' }
      return { acceptanceCriteria: [{ defectId: 'D1', given: 'g', when: 'w', then: 't' }] }
    },
  })
  const diagnosis = calls.find((c) => c.kind === 'agent' && c.label === 'triage:diagnosis')
  assert.match(diagnosis.prompt, /THE REPOSITORY IS NOT KNOWN/)
  assert.match(diagnosis.prompt, /\/repos\/app\/\.polyrepo\/manifest\.yaml/, 'the manifest is offered as where the repositories are listed')
  assert.match(diagnosis.prompt, /SkillSpoke-web/, 'the hints are offered')
  assert.match(diagnosis.prompt, /a suspicion, not an answer/)
  assert.equal(diagnosis.opts.schema.properties.repoPath.type, 'string', 'the schema carries the located repository')
  assert.equal(diagnosis.opts.schema.properties.repoResolution.type, 'string')
})

test('bug-triage: the contract carries the repository the diagnosis located, or the supplied one', async () => {
  const run = (bead, located) =>
    runWorkflowScript(path.join(WF, 'bug-triage.js'), {
      args: { bead },
      agentImpl: (call) => {
        if (call.label === 'triage:diagnosis') return { reproduction: 'r', rootCause: 'c', defects: [{ id: 'D1', mechanism: 'm' }], affectedFiles: [], blastRadius: 'b', surfaces: [], repoPath: located, repoResolution: 'x' }
        if (call.label === 'triage:sizing') return { scope: 'fix', rationale: 'r' }
        return { acceptanceCriteria: [{ defectId: 'D1', given: 'g', when: 'w', then: 't' }] }
      },
    })
  const absent = await run({ id: 'ssbd-bug1', title: 't', description: 'd' }, RULED)
  assert.equal(absent.result.repoPath, RULED, 'located by the diagnosis')
  const none = await run({ id: 'ssbd-bug1', title: 't', description: 'd' }, '')
  assert.equal(none.result.repoPath, null, 'an empty answer is carried as null, never as a guess')
  const supplied = await run({ id: 'ssbd-bug1', title: 't', description: 'd', repoPath: OTHER }, RULED)
  assert.equal(supplied.result.repoPath, OTHER, 'a supplied repository outranks what the diagnosis says')
  const prompt = supplied.calls.find((c) => c.label === 'triage:diagnosis').prompt
  assert.doesNotMatch(prompt, /THE REPOSITORY IS NOT KNOWN/, 'a known repository is not searched for')
})
