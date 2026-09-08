// A PRD says what the product MUST BE. What already ships is material, not authority.
//
// prd-to-spec used to read the two the other way round: it reconciled the PRD against
// reality and then specified the REMAINDER — a generated "delta PRD" — so a requirement
// with code behind it was written off as done, a PRD whose requirements were all built
// was CLOSED, and the phases downstream never saw the document anybody wrote. That
// inverts the rule. The PRD is canonical: material that conforms is reused, material that
// contradicts is REMOVED (the PRD wins, and that is settled by definition rather than
// argued), and what is absent is built. Nothing is ever subtracted from the ask.
//
// These tests hold the properties that make the inversion impossible to reintroduce:
// every requirement comes back, a status with no evidence behind it is not honoured,
// removal and reuse are first-class work, downstream reads the ORIGINAL PRD, and a UI
// difference never convenes an architecture panel.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, workflowCalls, agentCalls } from './helpers/run-workflow.mjs'
import { beadWriter } from './helpers/bead-writer.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WORKFLOWS = path.resolve(HERE, '..', '..', 'workflows')
const reconciliation = path.join(WORKFLOWS, 'prd-reconciliation.js')
const prdToSpec = path.join(WORKFLOWS, 'prd-to-spec.js')

const PRD = {
  id: 'ssbd-sp6n',
  title: 'Multi-factor authentication',
  body: 'R1. A user can enrol a TOTP authenticator.\nR2. A user is challenged for MFA at sign-in.',
  path: '/docs/prd/mfa.md',
  repoPath: '/repo/auth',
}

const DEPENDENCY_CLEAN = { current: true, changeFindings: [], evidence: 'lockfiles unchanged' }

/** Scripted reconciler — the ONE checker session that carries both checks. */
function reconcileAgents({
  requirements,
  infraOnly = false,
  architectureNeeded = false,
  architectureQuestions = [],
  uiAuthority,
}) {
  return (call) => {
    if (call.label === 'reconcile:reality-and-dependencies') {
      return {
        requirements,
        infraOnly,
        architectureNeeded,
        architectureQuestions,
        evidenceSummary: 'read the auth service and queried the deployed pool',
        dependencyChanges: DEPENDENCY_CLEAN,
        ...(uiAuthority ? { uiAuthority } : {}),
      }
    }
    return null
  }
}

async function reconcile(scripted, args = {}) {
  return runWorkflowScript(reconciliation, {
    args: { prd: PRD, repos: ['/repo/auth'], ...args },
    agentImpl: reconcileAgents(scripted),
  })
}

// ── Nothing is subtracted ───────────────────────────────────────────────────────

test('a PRD whose requirements all conform is REUSED, not closed — every requirement still comes back', async () => {
  const { result, calls } = await reconcile({
    requirements: [
      {
        id: 'R1',
        requirement: 'enrol TOTP',
        status: 'conforms',
        evidence: ['services/auth/mfa.py:118'],
        conformingMaterial: ['services/auth/mfa.py enrolment flow'],
        surface: 'service',
      },
      {
        id: 'R2',
        requirement: 'challenge at sign-in',
        status: 'conforms',
        evidence: ['https://api.dev/auth/mfa/challenge — 200'],
        conformingMaterial: ['the deployed challenge endpoint'],
        surface: 'service',
      },
    ],
  })
  assert.equal(result.ok, true)
  assert.equal(result.requirements.length, 2, 'the inventory is never shorter than the PRD')
  assert.equal(result.conformsCount, 2)
  assert.equal(result.absentCount, 0)
  assert.equal(result.reuseWork.length, 2, 'conforming material is named so the spec builds ON it')
  assert.equal(result.removalWork.length, 0)
  assert.equal(
    calls.filter((c) => c.kind === 'agent').length,
    1,
    'the mini writes no document at all — one checker session and nothing else',
  )
})

test('nothing built at all is every requirement absent — the mini does not assume the work exists either', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'absent', evidence: ['no match for "totp" under services/auth/'], missing: 'the enrolment flow' },
      { id: 'R2', requirement: 'challenge at sign-in', status: 'absent', evidence: ['no match for "mfa" in routes.py:1-400'], missing: 'the challenge' },
    ],
  })
  assert.equal(result.absentCount, 2)
  assert.equal(result.requirements.length, 2)
  assert.equal(result.requirements[0].missing, 'the enrolment flow', 'what is missing survives for the builder')
})

test('material that contradicts the PRD becomes REMOVAL work, not a smaller PRD', async () => {
  // The whole inversion in one test. A contradiction used to shrink the ask; it is the
  // same ask plus a deletion, and the deletion has to reach decomposition or nobody does it.
  const { result } = await reconcile({
    requirements: [
      {
        id: 'R1',
        requirement: 'enrol TOTP',
        status: 'contradicts',
        evidence: ['services/auth/sms_mfa.py:44'],
        removalTargets: ['services/auth/sms_mfa.py', 'infra/auth_stack.py:202 SMS config'],
        repos: ['/repo/auth'],
        surface: 'service',
      },
    ],
  })
  assert.equal(result.contradictsCount, 1)
  assert.equal(result.requirements.length, 1, 'the requirement stays in scope')
  assert.deepEqual(result.removalWork, [
    {
      requirementId: 'R1',
      requirement: 'enrol TOTP',
      targets: ['services/auth/sms_mfa.py', 'infra/auth_stack.py:202 SMS config'],
      repos: ['/repo/auth'],
    },
  ])
})

// ── evidence ────────────────────────────────────────────────────────────────────

test('a requirement cannot be marked conforming without evidence — it drops to absent and is built fresh', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'conforms', evidence: [], conformingMaterial: ['trust me'] },
      { id: 'R2', requirement: 'challenge at sign-in', status: 'absent', evidence: ['not found'] },
    ],
  })
  const r1 = result.requirements.find((r) => r.id === 'R1')
  assert.equal(r1.status, 'absent', 'an unevidenced "conforms" is not honoured')
  assert.equal(r1.claimedStatus, 'conforms', 'and the discarded claim is still reported')
  assert.deepEqual(r1.conformingMaterial, [], 'a demoted requirement carries no reuse instruction')
  assert.equal(result.absentCount, 2, 'demotion means "build it fresh", which is never wrong under this rule')
  assert.equal(result.evidenceViolations.length, 1)
})

test('an unevidenced contradiction is demoted too — nobody deletes files on an unconfirmed claim', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'contradicts', evidence: ['I had a look around'], removalTargets: ['services/auth/'] },
    ],
  })
  assert.equal(result.requirements[0].status, 'absent')
  assert.deepEqual(result.requirements[0].removalTargets, [], 'removal is destructive — an unconfirmed target is blanked')
  assert.equal(result.removalWork.length, 0)
})

test('prose is not evidence for a conforming claim — only a file:line, cited artifact, endpoint, URL or ARN is', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'conforms', evidence: ['I reviewed the auth service and it looks complete'] },
    ],
  })
  assert.equal(result.requirements[0].status, 'absent')
  assert.match(result.evidenceViolations[0].reason, /file:line/)
})

test('a cited design-system artifact IS strong evidence for a ui requirement', async () => {
  // The cds bundle is the UI authority, so a build-spec path has to satisfy the same bar a
  // file:line does for a service requirement — otherwise every UI status is demoted and the
  // packaged artifact is rebuilt from PRD prose.
  const { result } = await reconcile({
    requirements: [
      {
        id: 'R1',
        requirement: 'the settings shell',
        status: 'conforms',
        surface: 'ui',
        evidence: ['design-mocks/packages/batch-20260819T191805Z/views/settings-profile/spec/build-spec.md'],
        conformingMaterial: ['the packaged settings view'],
      },
    ],
  })
  assert.equal(result.requirements[0].status, 'conforms')
  assert.equal(result.evidenceViolations.length, 0)
})

test('the same demand does not apply in reverse — an absent claim needs only a stated basis', async () => {
  // The two errors are not symmetric. Calling existing material absent costs a rebuild;
  // calling contradicting material conforming leaves the product in the state the PRD was
  // written to change.
  const { result } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'enrol TOTP', status: 'absent', evidence: ['grepped for totp, no hits'] }],
  })
  assert.equal(result.requirements[0].status, 'absent')
  assert.equal(result.evidenceViolations.length, 0)
})

test('a schema that permitted an evidence-free status would defeat the whole check', async () => {
  const { calls } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'] }],
  })
  const schema = agentCalls(calls, 'reconcile:reality-and-dependencies')[0].opts.schema
  const item = schema.properties.requirements.items
  assert.ok(item.required.includes('evidence'), 'evidence is required of every requirement, whatever its status')
  assert.equal(item.properties.evidence.minItems, 1, 'and an empty evidence array is not expressible')
  assert.deepEqual(
    item.properties.status.enum,
    ['conforms', 'contradicts', 'absent'],
    'the three statuses describe the MATERIAL — there is no status that retires a PRD requirement',
  )
})

// ── the two repo lists ──────────────────────────────────────────────────────────

test('`repos` unions every requirement; `existingRepos` only where material was actually found', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'a', status: 'conforms', evidence: ['x.py:1'], repos: ['/repo/auth'], conformingMaterial: ['m'] },
      { id: 'R2', requirement: 'b', status: 'absent', evidence: ['no hits'], repos: ['/repo/web'] },
    ],
  })
  assert.deepEqual(result.repos, ['/repo/auth', '/repo/web'], 'the prediction sizes the span of the whole PRD')
  assert.deepEqual(result.existingRepos, ['/repo/auth'], 'an absent requirement proves nothing about where anything lives')
  assert.equal(result.spansMultipleRepos, true)
})

// ── architecture is needed only when the PRD leaves a question open ─────────────

test('a claimed architecture need with no question behind it is recorded as not needed', async () => {
  const { result } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'], surface: 'service' }],
    architectureNeeded: true,
    architectureQuestions: [],
  })
  assert.equal(result.architectureNeeded, false, 'a flag with no question behind it is a shrug, not a need')
  assert.deepEqual(result.architectureQuestions, [])
})

test('a question attributed to a UI requirement is DROPPED — the design system settles layout', async () => {
  // The concrete failure this exists to prevent: an Epic spent 45 minutes convening an
  // architecture panel to choose an app shell the design mocks had settled months earlier.
  const { result, logs } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'the settings shell', status: 'absent', evidence: ['e'], surface: 'ui' }],
    architectureNeeded: true,
    architectureQuestions: [{ requirementId: 'R1', question: 'which app shell should settings use?' }],
  })
  assert.equal(result.architectureNeeded, false)
  assert.deepEqual(result.architectureQuestions, [], 'a dropped question must never sit in the list as work to do')
  assert.equal(result.ledger.uiQuestionsDropped, 1, 'and the drop is recorded rather than silent')
  assert.ok(logs.some((l) => /design system settles/.test(l)))
})

test('a question attributed to NOTHING is not dropped — unknown is not the same as UI', async () => {
  const { result } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'], surface: 'service' }],
    architectureNeeded: true,
    architectureQuestions: [{ requirementId: '', question: 'which datastore holds the session record?' }],
  })
  assert.equal(result.architectureNeeded, true, 'the safe error is letting a genuine question through, not silencing one')
  assert.equal(result.architectureQuestions.length, 1)
  assert.equal(result.architectureQuestions[0].requirementId, null, 'a whole-PRD question is attributed to no requirement')
})

// ── the UI authority chain ──────────────────────────────────────────────────────

test('the resolved cds bundle travels with the inventory so spec authoring can read its build-specs', async () => {
  const { result } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'], surface: 'ui' }],
    uiAuthority: {
      bundlePath: '/repo/auth/design-mocks/packages/batch-20260819T191805Z',
      artifactsConsulted: ['views/settings-profile/spec/build-spec.md'],
      shellsConsulted: ['personal-agent-shell.html'],
      pagesConsulted: [],
    },
  })
  assert.equal(result.uiAuthority.bundlePath, '/repo/auth/design-mocks/packages/batch-20260819T191805Z')
  assert.deepEqual(result.uiAuthority.artifactsConsulted, ['views/settings-profile/spec/build-spec.md'])
  assert.equal(result.uiAuthority.mocksDir, '/repo/auth/design-mocks', 'the mocks directory is derived from the repo when not stated')
})

test('the reconciler is pointed at the hand-off bundle FIRST and the loose mocks second', async () => {
  const { calls } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'] }],
  })
  const [checker] = agentCalls(calls, 'reconcile:reality-and-dependencies')
  assert.match(checker.prompt, /HAND-OFF BUNDLE/, 'the packaged artifact is the highest UI authority')
  assert.match(checker.prompt, /MANIFEST\.tsv/, 'and it is told to start at the cheap index')
  assert.match(checker.prompt, /NEVER an\s*\n?\s*architecture question/, 'a UI difference is settled, not adjudicated')
  assert.ok(checker.prompt.includes('/repo/auth/design-mocks/packages'), 'the bundle root is derived from the repo the run operates on')
})

test('an empty PRD is refused rather than reported as an empty inventory', async () => {
  // "Nothing was found" and "no PRD was supplied" both reduce to zero requirements, and a
  // caller reading the first as an answer proceeds against a document nobody looked at.
  const { result } = await runWorkflowScript(reconciliation, { args: { prd: { body: '   ' } } })
  assert.equal(result.ok, false)
  assert.deepEqual(result.requirements, [])
  assert.equal(result.conformsCount, 0)
  assert.equal(result.architectureNeeded, false)
  assert.match(result.reason, /empty PRD body/)
})

// ── the checks are one session, and it is a leaf ────────────────────────────────

test('reality and dependency currency are both checked by ONE checker session', async () => {
  // The two checks were two sessions, each paying a full session-start to read the
  // same PRD. Both are checks on a document authored upstream, so one session
  // carrying both preserves segregation of duties at half the cost (ssbd-qrpf0).
  const { calls, result } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'] }],
  })
  const combined = agentCalls(calls, 'reconcile:reality-and-dependencies')
  assert.equal(combined.length, 1, 'exactly one checker session runs both checks')
  assert.equal(combined[0].opts.agentType, 'agent-teams-workforce:prd-reality-reconciler')
  assert.match(combined[0].prompt, /CHECK 2/, 'the dependency check is part of the same dispatch')
  assert.ok(result.dependencyChanges, 'the dependency-change verdict still crosses back to the caller')
})

test('the reconciler is told to pin every aws command to a profile', async () => {
  // Full admin credentials against the wrong account is the failure mode that makes
  // live verification worse than not doing it.
  const { calls } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'] }],
  })
  assert.match(agentCalls(calls, 'reconcile:reality-and-dependencies')[0].prompt, /--profile dev/)
})

test('the mini is a leaf — it never nests another workflow', async () => {
  const { calls } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'] }],
  })
  assert.equal(calls.filter((c) => c.kind === 'workflow').length, 0)
})

// ── the composite ───────────────────────────────────────────────────────────────

const RECON_OK = {
  ok: true,
  requirements: [
    { id: 'R1', requirement: 'a', status: 'conforms', evidence: ['x:1'], conformingMaterial: ['x.py'], surface: 'service', repos: ['/repo/auth'] },
    { id: 'R2', requirement: 'b', status: 'absent', evidence: ['y:2'], missing: 'b', surface: 'service', repos: ['/repo/auth'] },
  ],
  conformsCount: 1,
  contradictsCount: 0,
  absentCount: 1,
  removalWork: [],
  reuseWork: [{ requirementId: 'R1', requirement: 'a', material: ['x.py'], repos: ['/repo/auth'] }],
  repos: ['/repo/auth'],
  existingRepos: ['/repo/auth'],
  spansMultipleRepos: false,
  architectureNeeded: false,
  architectureQuestions: [],
  uiAuthority: { bundlePath: null, mocksDir: null, artifactsConsulted: [], shellsConsulted: [], pagesConsulted: [] },
  infraOnly: false,
  ledger: { phase: 'prd-reconciliation' },
}

// WHERE THE COMPARISON RUNS IS THE WHOLE SUBJECT OF THIS SECTION, AND IT MOVED.
//
// It used to run at the front of prd-to-spec, ahead of every gate, and feed PRD
// validation, the architecture panel and the TRD. That made what is deployed in a dev
// account into a form of requirement. A PRD is WHAT and never knows what is deployed; a
// TRD is HOW and derives it from the PRD and the SAD on best-practice grounds, blind to
// the status quo; the SPEC is the only layer that asks "X is what we want, Y is what we
// have, how do we turn Y into X", and it asks it there because it is the only layer scoped
// to ONE repository — the only scope at which the question has a concrete answer.
//
// So `composite` now runs the pipeline all the way to spec authoring, where the
// reconciliation lives. Everything the old tests pinned still holds; what changed is when
// it is observable.

/** Run prd-to-spec all the way through, with every gate passing and every mini minimal. */
async function composite(reconResult, { onCalls, args } = {}) {
  const seen = []
  let storyN = 0
  const { result, calls, logs } = await runWorkflowScript(prdToSpec, {
    args: { prd: { ...PRD }, repoPath: '/repo/auth', ...(args || {}) },
    workflowImpl: (call) => {
      seen.push(call)
      const name = String(call.name || '')
      if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) {
        return { verdict: 'pass', criteria: [], flags: [] }
      }
      if (name.endsWith('prd-reconciliation')) return reconResult
      if (name.endsWith('prd-validation')) {
        return { ok: true, validationVerdict: 'pass', validatedPrd: { body: call.payload.prd.body }, findings: [] }
      }
      if (name.endsWith('architecture')) return { ok: true, decision: { id: 'AD-1' }, sad: { path: 's' } }
      if (name.endsWith('repo-scoping')) {
        return {
          ok: true,
          repos: ['/repo/auth'],
          placements: [{ repoPath: '/repo/auth', repoName: 'auth', workUnitIds: [], rationale: 'r', verified: true }],
          newRepos: [],
          requiredHumanActions: [],
          reclassified: [],
          blocked: [],
          spanVerified: true,
        }
      }
      if (name.endsWith('trd-authoring')) return { ok: true, trd: { id: 'TRD-1', summary: 'sum' } }
      if (name.endsWith('spec-authoring')) {
        storyN += 1
        const repoPath = (call.payload && call.payload.repoPath) || null
        return {
          ok: true,
          specSet: { apiSpec: {} },
          story: { key: `S${storyN}`, type: 'story', title: `Story for ${repoPath}`, description: 'd', repoPath, parentEpicKey: 'E1' },
          outOfRepoFindings: [],
        }
      }
      if (name.endsWith('task-decomposition')) {
        const sk = ((call.payload && call.payload.story) || {}).key || 'S?'
        return { ok: true, beadSet: [{ key: 'T1', type: 'task', parentStoryId: sk, title: 't', description: 'd', acceptanceCriteria: ['a'] }] }
      }
      return null
    },
    agentImpl: beadWriter(),
  })
  if (onCalls) onCalls(calls)
  return { result, seen, calls, logs }
}

test('the comparison runs at SPEC AUTHORING — after G1 and the TRD, never before them', async () => {
  const { seen } = await composite(RECON_OK)
  const idx = (suffix) => seen.findIndex((c) => String(c.name || '').endsWith(suffix))
  const reconIdx = idx('prd-reconciliation')
  assert.ok(reconIdx >= 0, 'the composite still reconciles')
  assert.ok(reconIdx > idx('prd-validation'), 'PRD validation judges the document, not the system')
  assert.ok(reconIdx > idx('architecture'), 'the architecture panel designs from the PRD and the SAD')
  assert.ok(reconIdx > idx('repo-scoping'), 'the span is ruled before anything looks at what is deployed')
  assert.ok(reconIdx > idx('trd-authoring'), 'the TRD is HOW, derived from best practice and blind to the status quo')
  assert.ok(reconIdx < idx('spec-authoring'), 'and it lands immediately before the spec that has to turn Y into X')
})

test('neither PRD validation, nor architecture, nor the TRD is handed a deployed-state inventory', async () => {
  // The negative half, and the one that matters: the relocation is only real if the
  // upstream phases genuinely stop receiving the material. The inventory's own header text
  // is the marker — it is what `renderInventory` emits and nothing else in the run does.
  const { seen, calls } = await composite(RECON_OK)
  const INVENTORY = /MATERIAL INVENTORY FOR/
  for (const suffix of ['prd-validation', 'architecture', 'trd-authoring', 'repo-scoping']) {
    const call = seen.find((c) => String(c.name || '').endsWith(suffix))
    assert.ok(call, `${suffix} ran`)
    assert.ok(
      !INVENTORY.test(JSON.stringify(call.payload)),
      `${suffix} must derive from the PRD and the SAD, never from what happens to be deployed`,
    )
  }
  // The architecture triage is dispatched by the composite directly rather than through a
  // mini, so it is checked at the agent level.
  for (const c of agentCalls(calls, 'triage:architecture-needed')) {
    assert.ok(!INVENTORY.test(c.prompt), 'the triage judges the PRD, not the deployed system')
  }
  // And it DOES reach the spec, through the constraints channel that already existed.
  const spec = seen.find((c) => String(c.name || '').endsWith('spec-authoring'))
  assert.ok(
    spec.payload.constraints.some((x) => INVENTORY.test(String(x))),
    'the spec is the layer that reuses, removes or builds, so it is the layer that gets the inventory',
  )
})

test('the comparison is scoped to ONE repository, and it is the ruled path', async () => {
  const { seen } = await composite(RECON_OK)
  const recons = seen.filter((c) => String(c.name || '').endsWith('prd-reconciliation'))
  assert.equal(recons.length, 1, 'one per repository in the ruled span')
  assert.deepEqual(recons[0].payload.repos, ['/repo/auth'], 'the search narrows to the repository the Story covers')
  assert.equal(recons[0].payload.prd.body, PRD.body, 'the REQUIREMENTS never narrow — only the search does')
})

test('a PRD whose requirements ALL conform is not closed — the run carries on and validates it', async () => {
  // The close short-circuit is deleted. No work item is ever ended on the grounds that
  // code exists: the material is reused, and the PRD is still specified.
  const { result, seen } = await composite({
    ...RECON_OK,
    requirements: [{ id: 'R1', requirement: 'a', status: 'conforms', evidence: ['x:1'], conformingMaterial: ['x.py'], surface: 'service' }],
    conformsCount: 1,
    absentCount: 0,
  })
  assert.notEqual(result.action, 'close')
  assert.equal(seen.filter((c) => c.name === 'agent-teams-workforce:prd-validation').length, 1, 'the PRD is still validated')
})

test('an infrastructure-only PRD is not rerouted away from the pipeline', async () => {
  // `infraOnly` survives as a fact about the PRD; the reroute it used to trigger was
  // computed off the subtracted remainder and is gone.
  const { result, seen } = await composite({ ...RECON_OK, infraOnly: true })
  assert.notEqual(result.action, 'reroute')
  assert.equal(result.composite, undefined)
  assert.equal(seen.filter((c) => c.name === 'agent-teams-workforce:prd-validation').length, 1)
})

test('downstream phases receive the ORIGINAL PRD — there is no delta to rebind to', async () => {
  const { seen } = await composite(RECON_OK)
  const validation = seen.find((c) => c.name === 'agent-teams-workforce:prd-validation')
  assert.ok(validation, 'validation ran')
  assert.equal(validation.payload.prd.body, PRD.body, 'the ambition is what gets specified')
  assert.equal(validation.payload.prd.path, PRD.path)
})

test('every phase that sees a PRD sees the same text — none of them a narrowed one', async () => {
  // The run reaches every phase now, so this sweeps the whole pipeline rather than
  // stopping at validation. Phases carry the text under different keys — trd-authoring
  // takes `content`, the rest take `body` — so the invariant is the TEXT, not the field
  // name: no phase anywhere receives a subtracted or rewritten PRD.
  const { seen } = await composite(RECON_OK)
  const withPrd = seen.filter((c) => c.payload && c.payload.prd && typeof c.payload.prd === 'object')
  assert.ok(withPrd.length >= 4, `more than one phase reads the PRD (saw ${withPrd.length})`)
  for (const c of withPrd) {
    const text = c.payload.prd.body || c.payload.prd.content
    assert.equal(text, PRD.body, `${c.name} must receive the original PRD, not a narrowed one`)
  }
})

test('a contradiction is reported as removal work, and the requirement count is unchanged by it', async () => {
  // The composite must never report a smaller PRD because material contradicts it. The
  // spec reads the inventory as CONTEXT; what is pinned here is that nothing was subtracted
  // and that the removal was counted as work.
  const { logs, result } = await composite({
    ...RECON_OK,
    requirements: [
      { id: 'R1', requirement: 'a', status: 'contradicts', evidence: ['x:1'], removalTargets: ['old.py'], surface: 'service', repos: ['/repo/auth'] },
    ],
    conformsCount: 0,
    contradictsCount: 1,
    absentCount: 0,
    removalWork: [{ requirementId: 'R1', requirement: 'a', targets: ['old.py'], repos: ['/repo/auth'] }],
    reuseWork: [],
  })
  const line = logs.find((l) => /^Current-state comparison across /.test(l))
  assert.ok(line, 'the run must say what the comparison found')
  assert.match(line, /1 requirement\(s\), all in scope/)
  assert.match(line, /1 removal work item\(s\)/, 'removal is work, and work that is never mentioned is never done')
  // And it reached a Story, which is what makes it reach decomposition at all.
  assert.equal(result.removalNotEmitted, undefined, 'per-repo findings place exactly — nothing is left standing silently')
})

test('removal discovered at spec time still reaches the task briefs', async () => {
  // The half of the old front-end phase that MUST survive the move. A contradiction that
  // nobody writes a task to delete stays deployed, so the item has to travel from the
  // per-repo comparison, through placement, into the decomposition brief.
  const { seen, result } = await composite({
    ...RECON_OK,
    requirements: [
      { id: 'R1', requirement: 'a', status: 'contradicts', evidence: ['x:1'], removalTargets: ['old.py'], surface: 'service', repos: [] },
    ],
    conformsCount: 0,
    contradictsCount: 1,
    absentCount: 0,
    removalWork: [{ requirementId: 'R1', requirement: 'a', targets: ['old.py'], repos: [] }],
    reuseWork: [],
  })
  const decomp = seen.find((c) => String(c.name || '').endsWith('task-decomposition'))
  assert.ok(decomp, 'decomposition ran')
  assert.match(decomp.payload.spec.description, /REMOVAL WORK — part of this Story/)
  assert.match(decomp.payload.spec.description, /old\.py/, 'the target itself has to be in the brief')
  assert.equal(result.ok, true)
  assert.equal(result.removalNotEmitted, undefined)
})

test('a failed comparison does not author a spec for that repository — it is never read as an empty inventory', async () => {
  // Reading "we could not establish what exists here" as "nothing exists here" is the
  // greenfield assumption the whole phase removes. With one repository in the span, no
  // comparison means no spec at all, so the run stops at spec authoring rather than
  // specifying blind.
  const { result, seen, calls } = await composite({ ok: false, reason: 'could not read the repository' })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'spec-authoring')
  assert.equal(
    seen.filter((c) => String(c.name || '').endsWith('spec-authoring')).length,
    0,
    'no spec is authored against an unknown current state',
  )
  const { journalDetail } = await import('./helpers/run-workflow.mjs')
  const partial = journalDetail(calls).partial
  assert.ok(partial.prd, 'the PRD is still in the journal')
  assert.equal(partial.reconFailures.length, 1, 'and the failure is named as what it was')
  assert.match(partial.reconFailures[0].reason, /could not read the repository/)
})

test('the composite declares NO PRD Reconciliation phase, and Spec Authoring owns the comparison', async () => {
  const { readWorkflowSource } = await import('./helpers/run-workflow.mjs')
  const src = readWorkflowSource(prdToSpec)
  const phasesIdx = src.indexOf('phases: [')
  const phases = src.slice(phasesIdx, src.indexOf('\n  ],', phasesIdx))
  assert.ok(
    !/\{ title: 'PRD Reconciliation'/.test(phases),
    'a front-end reconciliation phase is what made deployed state a requirements input',
  )
  assert.match(phases, /phases: \[\s*\{ title: 'PRD Creation'/, 'the run now opens on the PRD itself')
  assert.match(phases, /\{ title: 'Spec Authoring', detail: '[^']*current-state reconciliation runs HERE/)
})

test('the comparison and validation are separate workflow dispatches', async () => {
  const { seen } = await composite(RECON_OK)
  assert.equal(workflowCalls(seen, 'agent-teams-workforce:prd-reconciliation').length, 1)
  assert.equal(workflowCalls(seen, 'agent-teams-workforce:prd-validation').length, 1)
})
