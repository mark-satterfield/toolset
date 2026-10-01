// The repo span is an OUTPUT of the run, ruled by architecture — not caller input.
//
// It used to arrive as `args.repos`, defaulting to `[repoPath]`, computed at module scope
// before a single phase had run. Nothing in the pipeline ever decided it, so a PRD that
// genuinely spanned three repositories produced ONE Story in whichever repository the
// caller happened to be standing in, and the other two repositories' worth of work was
// specified nowhere. Nothing said so: a wrongly-narrowed span and a correctly-scoped
// single-repo PRD are indistinguishable once the run is under way.
//
// It cannot be supplied because it cannot be KNOWN in advance — the span is a property of
// the delta (work no repository contains yet) and of the design ruled for it, and both are
// outputs of the same run. It equally must not be pre-staged into a file: a stored span is
// an answer computed against a PRD that has since been adjusted, and a re-run that reads
// one succeeds against the wrong repositories, silently.
//
// These tests pin the three things that make that true: the greenfield firewall (the
// shaper never sees what exists), the refusal to fall back to the launch repository, and
// the fact that the polyrepo-steward, not a person, supplies every repository the work needs.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, agentCalls, workflowCalls, journalPayload } from './helpers/run-workflow.mjs'
import { withLifecycle, TEST_EPIC, ARTIFACT_ARGS } from './helpers/bead-writer.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WF = path.resolve(HERE, '..', '..', 'workflows')
const SCOPING = path.join(WF, 'repo-scoping.js')
const PRD_TO_SPEC = path.join(WF, 'prd-to-spec.js')

const PRD = { id: 'PRD-1', title: 'PRD One', body: 'the delta requirements' }

/** A shaper/steward fixture that agrees on one repository. */
function scopingAgents({ placements, createdRepos = [], inventory } = {}) {
  const repos = placements || [{ repoPath: '/repos/alpha', repoName: 'alpha', workUnitIds: ['W1'], rationale: 'owns it' }]
  const inv = inventory || repos.map((p) => ({ repoPath: p.repoPath, name: p.repoName, owns: 'the capability' }))
  return (call) => {
    if (call.label === 'scope:greenfield-shape') {
      return {
        workUnits: [{ id: 'W1', summary: 'build the thing', homeKind: 'service', boundaryRationale: 'own context' }],
        designSummary: 'one service',
      }
    }
    if (call.label.startsWith('scope:place-and-provision')) {
      return { repositories: inv, placements: repos, createdRepos, creationFailures: [], reclassified: [], surveySummary: `${inv.length} repos`, spanRationale: 'ruled' }
    }
    return null
  }
}

// ── The greenfield firewall ────────────────────────────────────────────────────

test('the greenfield shaper is told NOTHING about which repositories exist', async () => {
  // The whole ordering rests on this. Show a model a repository that already does
  // something adjacent and it reasons backwards from it, producing a rationalization of
  // the status quo wearing the vocabulary of a design. The firewall is the prompt.
  const { calls } = await runWorkflowScript(SCOPING, {
    args: {
      prd: PRD,
      seedRepos: ['/repos/where-the-human-stood'],
      reconciliation: { existingRepos: ['/repos/where-the-code-already-is'] },
    },
    agentImpl: scopingAgents(),
  })

  const [shaper] = agentCalls(calls, 'scope:greenfield-shape')
  assert.ok(shaper, 'the shaper must run')
  assert.ok(
    !shaper.prompt.includes('/repos/where-the-code-already-is'),
    'existingRepos is the single most biasing input there is — it names where the EXISTING material lives, ' +
      'and it must not reach the step whose whole job is to ignore what exists',
  )
  assert.ok(
    !shaper.prompt.includes('/repos/where-the-human-stood'),
    'the launch repository carries no authority and must not be shown to the shaper either',
  )
})

test('the existing-code evidence DOES reach the ruling step — the firewall is ordering, not censorship', async () => {
  // The other half. Withholding existingRepos from the decider too would make the ruling
  // blind to what exists, which is a different defect: recognizing existing repositories
  // is step 2 of the ordering and the whole point of the ruling step.
  const { calls } = await runWorkflowScript(SCOPING, {
    args: { prd: PRD, seedRepos: ['/repos/alpha'], reconciliation: { existingRepos: ['/repos/where-the-code-already-is'] } },
    agentImpl: scopingAgents(),
  })

  const [steward] = agentCalls(calls, 'scope:place-and-provision')
  assert.ok(steward.prompt.includes('/repos/where-the-code-already-is'), 'the placement step must see the evidence')
})

test('the shaper runs BEFORE the steward places the work, so nothing about the estate reaches the design', async () => {
  const { calls } = await runWorkflowScript(SCOPING, { args: { prd: PRD }, agentImpl: scopingAgents() })
  const labels = calls.filter((c) => c.kind === 'agent').map((c) => c.label)
  assert.deepEqual(
    labels,
    ['scope:greenfield-shape', 'scope:place-and-provision'],
    'the shape, then the steward placement',
  )
})

// ── The reduction is where the enforcement lives ───────────────────────────────

test('the steward placements stand: a placement is kept without any list the steward returned', async () => {
  const { result } = await runWorkflowScript(SCOPING, {
    args: { prd: PRD },
    agentImpl: scopingAgents({
      placements: [{ repoPath: '/repos/beta', repoName: 'beta', workUnitIds: ['W1'], rationale: 'r' }],
      inventory: [],
    }),
  })
  assert.deepEqual(result.repos, ['/repos/beta'])
})

// ── The composite: how the span reaches the per-repo fan-out ───────────────────

/**
 * The material inventory the composite threads into the scoping ruling. It carries a
 * CONTRADICTING requirement deliberately: the repository holding material that has to be
 * DELETED is exactly a repository the span must be able to reach.
 */
const RECONCILED = {
  ok: true,
  requirements: [
    {
      id: 'R1',
      requirement: 'r',
      status: 'contradicts',
      evidence: ['f.py:1'],
      removalTargets: ['f.py'],
      surface: 'service',
      repos: ['/repos/where-the-code-already-is'],
    },
  ],
  conformsCount: 0,
  contradictsCount: 1,
  absentCount: 0,
  removalWork: [{ requirementId: 'R1', requirement: 'r', targets: ['f.py'], repos: ['/repos/where-the-code-already-is'] }],
  reuseWork: [],
  repos: ['/repos/where-the-code-already-is'],
  existingRepos: ['/repos/where-the-code-already-is'],
  spansMultipleRepos: false,
  uiAuthority: { bundlePath: null, mocksDir: null, artifactsConsulted: [], shellsConsulted: [], pagesConsulted: [] },
}

/** Every gate passes; every mini answers minimally. `scopingResult` is what repo-scoping returns. */
function compositeWorkflows({ scopingResult, outOfRepoFindings = [] }) {
  let storyN = 0
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('gate-enforce')) return { verdict: 'pass', criteria: [], flags: [] }
    if (name.endsWith('prd-reconciliation')) return RECONCILED
    if (name.endsWith('architecture')) return { ok: true, decision: { id: 'AD-1' } }
    if (name.endsWith('repo-scoping')) return scopingResult
    if (name.endsWith('trd-authoring')) return { ok: true, trd: { id: 'TRD-1', summary: 'sum' } }
    if (name.endsWith('spec-authoring')) {
      storyN += 1
      const repoPath = (call.payload && call.payload.repoPath) || null
      return {
        ok: true,
        specSet: { apiSpec: {} },
        story: { key: `S${storyN}`, type: 'story', id: `bd-S${storyN}`, elabKey: `story:S${storyN}`, title: `Story for ${repoPath}`, description: 'd', repoPath, parentEpicKey: 'E1' },
        outOfRepoFindings,
      }
    }
    if (name.endsWith('task-decomposition')) {
      const sk = ((call.payload && call.payload.story) || {}).key || 'S?'
      return { ok: true, tasks: [{ key: 'T1', id: `bd-${sk}-T1`, elabKey: `task:${sk}:t`, action: 'created', title: 't', dependsOn: [] }], summary: { created: 1, updated: 0 } }
    }
    return null
  }
}

const RULED = (repos, extra = {}) => ({
  ok: true,
  repos,
  placements: repos.map((r) => ({ repoPath: r, repoName: r, workUnitIds: [], rationale: 'ruled', verified: true })),
  createdRepos: [],
  reclassified: [],
  blocked: [],
  spanVerified: true,
  ...extra,
})

test('with no args.repos the composite RULES the span and fans out over what it ruled', async () => {
  const ruled = ['/repos/alpha', '/repos/beta', '/repos/gamma']
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/where-the-human-stood', epic: TEST_EPIC, ...ARTIFACT_ARGS },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(ruled) }),
    agentImpl: withLifecycle(),
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:repo-scoping').length, 1, 'the span must be ruled, once')
  assert.deepEqual(result.repoSpan, ruled)
  assert.deepEqual(
    result.hierarchy.stories.map((s) => s.repoPath),
    ruled,
    'one Story per RULED repository — not one per repository the caller happened to be standing in',
  )
  // THE REMOVAL ITEM CANNOT GO ASTRAY ANY MORE, AND THAT IS THE POINT OF THE MOVE.
  //
  // This run used to traverse a removal LOSS. One reconciler ran at the front of the
  // composite, and the repository it named for its finding — `/repos/where-the-code-
  // already-is`, in the fixture's own prose — was not in the span the ruling then
  // produced, so the item matched no Story, nothing was authored to delete the material,
  // and the run reported the shortfall. The fixture is unchanged and the assertion is
  // inverted, because the mechanism is.
  //
  // Reconciliation now runs INSIDE the per-repo fan-out, dispatched once per ruled
  // repository with that repository as its whole search scope, and the composite stamps
  // `repos: [<the ruled path>]` onto every item it returns rather than reading the
  // agent's prose. So a finding is attributable to a Story by construction: there is no
  // free-text repository name left to fail to match.
  assert.deepEqual(
    result.removalNotEmitted,
    undefined,
    'a per-repo reconciler cannot name a repository outside the span, so nothing can fail to place',
  )
  assert.deepEqual(
    result.removalWeaklyPlaced,
    undefined,
    'and nothing places on a guess: the repository is the ruled path the reconciler was dispatched with',
  )
  const recons = workflowCalls(calls, 'agent-teams-workforce:prd-reconciliation')
  assert.deepEqual(
    recons.map((c) => c.payload.repos),
    ruled.map((r) => [r]),
    'one reconciliation per ruled repository, each scoped to exactly that repository',
  )
  for (const c of recons) {
    assert.equal(c.payload.prd.body, 'b', 'each one reconciles the WHOLE PRD — the search narrows, the requirements never do')
  }
})

test('the launch repository is passed to scoping as a seed, and is NOT the span', async () => {
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/where-the-human-stood', epic: TEST_EPIC, ...ARTIFACT_ARGS },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(['/repos/alpha']) }),
    agentImpl: withLifecycle(),
  })
  const [scoping] = workflowCalls(calls, 'agent-teams-workforce:repo-scoping')
  assert.deepEqual(scoping.payload.seedRepos, ['/repos/where-the-human-stood'], 'the seed travels as a seed')
  assert.deepEqual(result.repoSpan, ['/repos/alpha'], 'and it loses to the ruling')
})

test('the ruling receives NO material inventory — the span is ruled before anything has looked at what is deployed', async () => {
  // This used to thread reconciliation's findings in as evidence for the ruling step, and
  // the reasoning was sound on its own terms: the span has to be able to include a
  // repository whose only stake is material that must come OUT.
  //
  // It is gone because the inventory is gone from this point in the run. A PRD is WHAT and
  // a TRD is HOW; the comparison against what exists happens at SPEC AUTHORING, per repo,
  // which is downstream of this ruling. So there is nothing to thread, and the ruling turns
  // on the design plus the mini's own survey of which repositories EXIST and what each one
  // OWNS — repository facts, not deployed-code facts.
  //
  // What must NOT happen is the absence being read as a finding. "Nobody has looked" and
  // "there is nothing there" are different, and only one of them licenses treating every
  // repository as greenfield.
  const { calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/where-the-human-stood', epic: TEST_EPIC, ...ARTIFACT_ARGS },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(['/repos/alpha']) }),
    agentImpl: withLifecycle(),
  })
  const [scoping] = workflowCalls(calls, 'agent-teams-workforce:repo-scoping')
  assert.equal(scoping.payload.reconciliation, undefined, 'no deployed-state inventory reaches the span ruling')
  assert.equal(scoping.payload.prd.body, 'b', 'scoping still rules against the WHOLE PRD, never a subtracted one')
  // And the ruling is dispatched before the first reconciliation, which is what makes the
  // absence structural rather than a caller's omission.
  const scopingIdx = calls.findIndex((c) => String(c.name || '').endsWith('repo-scoping'))
  const reconIdx = calls.findIndex((c) => String(c.name || '').endsWith('prd-reconciliation'))
  assert.ok(scopingIdx >= 0 && reconIdx >= 0, 'both ran')
  assert.ok(scopingIdx < reconIdx, 'the span is ruled first; the comparison happens per repo afterwards')
})

test('an explicit args.repos OVERRIDES the ruling for that run, and nothing is dispatched', async () => {
  // The override exists for a deliberate re-run and for tests. It is an argument passed in
  // band, never a stored artifact — which is what keeps the next run scoped afresh.
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { epic: TEST_EPIC, ...ARTIFACT_ARGS, prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/alpha', repos: ['/repos/alpha', '/repos/beta'] },
    workflowImpl: compositeWorkflows({ scopingResult: RULED(['/repos/never-used']) }),
    agentImpl: withLifecycle(),
  })
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:repo-scoping').length, 0, 'a pinned span spends nothing')
  assert.deepEqual(result.repoSpan, ['/repos/alpha', '/repos/beta'])
})

test('a failed ruling STOPS the run — it never falls back to the launch repository', async () => {
  // Falling back would restore exactly the defect this phase removes, and would do it on
  // the one run where the span was least certain.
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repos/where-the-human-stood', epic: TEST_EPIC, ...ARTIFACT_ARGS },
    workflowImpl: compositeWorkflows({ scopingResult: { ok: false, reason: 'could not establish the span' } }),
    agentImpl: withLifecycle(),
  })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'repo-scoping')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:spec-authoring').length, 0, 'nothing may be specified against a guessed span')
})

