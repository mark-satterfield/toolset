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

/** Run prd-to-spec far enough to observe what reconciliation did, with G1 stubbed to loop out. */
async function composite(reconResult, { onCalls } = {}) {
  const seen = []
  const { result, calls, logs } = await runWorkflowScript(prdToSpec, {
    args: { prd: { ...PRD }, repoPath: '/repo/auth' },
    workflowImpl: (call) => {
      seen.push(call)
      if (call.name === 'agent-teams-workforce:prd-reconciliation') return reconResult
      if (call.name === 'agent-teams-workforce:prd-validation') {
        return { ok: true, validationVerdict: 'pass', validatedPrd: { body: call.payload.prd.body }, findings: [] }
      }
      // Any gate: stop the run right after validation so the test stays about reconciliation.
      if (call.name === 'agent-teams-workforce:gate-enforce') {
        return { verdict: 'escalate', escalateTo: 'stop-here', criteria: [], feedback: 'test stop' }
      }
      return null
    },
    agentImpl: () => ({ written: true }),
  })
  if (onCalls) onCalls(calls)
  return { result, seen, calls, logs }
}

test('reconciliation runs BEFORE any gate is spent', async () => {
  const { seen } = await composite(RECON_OK)
  const reconIdx = seen.findIndex((c) => c.name === 'agent-teams-workforce:prd-reconciliation')
  const gateIdx = seen.findIndex((c) => c.name === 'agent-teams-workforce:gate-enforce')
  const validationIdx = seen.findIndex((c) => c.name === 'agent-teams-workforce:prd-validation')
  assert.ok(reconIdx >= 0, 'the composite reconciles at all')
  assert.ok(reconIdx < validationIdx, 'and it does so before PRD validation')
  assert.ok(gateIdx === -1 || reconIdx < gateIdx, 'and before the first gate')
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

test('every phase that sees a PRD sees the same one reconciliation was handed', async () => {
  const { seen } = await composite(RECON_OK)
  const withPrd = seen.filter((c) => c.payload && c.payload.prd)
  assert.ok(withPrd.length >= 2, 'more than one phase reads the PRD')
  for (const c of withPrd) {
    assert.equal(c.payload.prd.body, PRD.body, `${c.name} must receive the original PRD, not a narrowed one`)
  }
})

test('a contradiction is reported as removal work, and the requirement count is unchanged by it', async () => {
  // The composite must never report a smaller PRD because material contradicts it. The
  // phases downstream read the inventory as CONTEXT (repo scoping, the TRD and the spec
  // each receive the rendered text); what is pinned here is that nothing was subtracted.
  const { logs } = await composite({
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
  const line = logs.find((l) => /^Reconciliation: /.test(l))
  assert.ok(line, 'the run must say what the inventory found')
  assert.match(line, /1 requirement\(s\), all in scope/)
  assert.match(line, /1 removal work item\(s\)/, 'removal is work, and work that is never mentioned is never done')
})

test('a failed reconciliation stops the run — it is never read as an empty inventory', async () => {
  const { result, calls, seen } = await composite({ ok: false, reason: 'could not read the repository' })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'prd-reconciliation')
  assert.equal(seen.filter((c) => c.name === 'agent-teams-workforce:prd-validation').length, 0)
  // The salvage principle is intact, but the artifacts travel to the run journal rather
  // than back to the caller — a composite that returned everything it had produced killed
  // the dispatching session over a campaign. The RETURN names what is salvageable; the
  // journal holds it.
  assert.ok(result.partialProduced.includes('prd'), 'the return must name what was produced before it stopped')
  const { journalDetail } = await import('./helpers/run-workflow.mjs')
  assert.ok(journalDetail(calls).partial.prd, 'and the PRD it was handed is in the journal with it')
})

test('the composite declares PRD Reconciliation as phases[0]', async () => {
  const { readWorkflowSource } = await import('./helpers/run-workflow.mjs')
  const src = readWorkflowSource(prdToSpec)
  const phasesIdx = src.indexOf('phases: [')
  const first = src.slice(phasesIdx, phasesIdx + 300)
  assert.match(first, /phases: \[\s*\{ title: 'PRD Reconciliation'/)
})

test('reconciliation and validation are separate workflow dispatches', async () => {
  const { seen } = await composite(RECON_OK)
  assert.equal(workflowCalls(seen, 'agent-teams-workforce:prd-reconciliation').length, 1)
  assert.equal(workflowCalls(seen, 'agent-teams-workforce:prd-validation').length, 1)
})
