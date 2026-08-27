// A PRD says what somebody WANTED. It has never said what is MISSING.
//
// prd-to-spec used to read one as the other: its six validation analysts judge the
// document and not one of them reads the codebase, so a PRD written against a
// capability that partly or largely shipped was specified, decomposed, and built a
// second time on top of working code. An audit of 20 Epics in one project found
// ELEVEN written as greenfield against shipped behaviour — a 929-line MFA
// implementation merely disabled at one CDK line, a fully deployed passkey ceremony,
// three of four identity providers already live.
//
// These tests hold the four properties that make that impossible: nothing left means
// close, a defect reroutes, downstream reads the delta and never the original, and a
// status with no evidence behind it is not honoured.

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

/** Scripted reconciler + dependency detector + delta writer. */
function reconcileAgents({ requirements, deltaIsInfraOnly = false, unsettled = false, delta = {} }) {
  return (call) => {
    if (call.label === 'reconcile:prd-vs-reality') {
      return {
        requirements,
        deltaIsInfraOnly,
        unsettledTechnicalDecision: unsettled,
        evidenceSummary: 'read the auth service and queried the deployed pool',
      }
    }
    if (call.label === 'reconcile:dependency-changes') return DEPENDENCY_CLEAN
    if (call.label === 'delta:write') {
      return {
        ok: true,
        path: delta.path || '/docs/prd/mfa.delta.md',
        body: delta.body || 'R2. A user is challenged for MFA at sign-in.',
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

// ── deltaCount 0 ────────────────────────────────────────────────────────────────

test('everything already shipped is a zero delta, sized close, and writes no delta PRD', async () => {
  const { result, calls } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'shipped', evidence: ['services/auth/mfa.py:118'] },
      { id: 'R2', requirement: 'challenge at sign-in', status: 'shipped', evidence: ['https://api.dev/auth/mfa/challenge — 200'] },
    ],
  })
  assert.equal(result.ok, true)
  assert.equal(result.deltaCount, 0)
  assert.equal(result.verdict, 'shipped')
  assert.equal(result.sizeVerdict, 'close')
  assert.equal(result.deltaPrdPath, null, 'nothing remains, so nothing is authored')
  assert.equal(agentCalls(calls, 'delta:write').length, 0, 'a closed item costs no authoring pass')
})

test('nothing built at all is greenfield — the mini does not assume the work exists either', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'absent', evidence: ['no match for "totp" under services/auth/'] },
      { id: 'R2', requirement: 'challenge at sign-in', status: 'absent', evidence: ['no match for "mfa" in routes.py:1-400'] },
    ],
  })
  assert.equal(result.verdict, 'greenfield')
  assert.equal(result.deltaCount, 2)
})

// ── evidence ────────────────────────────────────────────────────────────────────

test('a requirement cannot be marked shipped without evidence — it stays in the delta', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'shipped', evidence: [] },
      { id: 'R2', requirement: 'challenge at sign-in', status: 'absent', evidence: ['not found'] },
    ],
  })
  const r1 = result.requirements.find((r) => r.id === 'R1')
  assert.equal(r1.status, 'absent', 'an unevidenced "shipped" is not honoured')
  assert.equal(r1.claimedStatus, 'shipped', 'and the discarded claim is still reported')
  assert.equal(result.deltaCount, 2, 'the requirement stays in the delta rather than being written off as built')
  assert.equal(result.evidenceViolations.length, 1)
})

test('prose is not evidence for a shipped claim — only a file:line, endpoint, URL or ARN is', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'shipped', evidence: ['I reviewed the auth service and it looks complete'] },
    ],
  })
  assert.equal(result.requirements[0].status, 'absent')
  assert.match(result.evidenceViolations[0].reason, /file:line/)
})

test('the same demand does not apply in reverse — an absent claim needs only a stated basis', async () => {
  // The two errors are not symmetric. Calling shipped work absent costs a rebuild;
  // calling absent work shipped means it is never built at all.
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
  const schema = agentCalls(calls, 'reconcile:prd-vs-reality')[0].opts.schema
  const item = schema.properties.requirements.items
  assert.ok(item.required.includes('evidence'), 'evidence is required of every requirement, whatever its status')
  assert.equal(item.properties.evidence.minItems, 1, 'and an empty evidence array is not expressible')
})

// ── sizing, by the remaining delta ──────────────────────────────────────────────

test('behaviour that exists but is switched off is sized as a bug, not as the original epic', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'shipped', evidence: ['services/auth/mfa.py:118'] },
      {
        id: 'R2',
        requirement: 'challenge at sign-in',
        status: 'partial',
        evidence: ['infra/auth_stack.py:202 — mfaConfiguration="OFF"'],
        behaviourExistsButWrong: true,
        needsNewContract: false,
        repos: ['/repo/auth'],
      },
    ],
  })
  assert.equal(result.sizeVerdict, 'bug')
  assert.equal(result.verdict, 'partial')
})

test('a remaining requirement needing a new contract is a story', async () => {
  const { result } = await reconcile({
    requirements: [
      {
        id: 'R1',
        requirement: 'admin IAM backend',
        status: 'absent',
        evidence: ['ui/admin/*.tsx exists; no matching route in api/routes.py:1-300'],
        needsNewContract: true,
        repos: ['/repo/auth'],
      },
    ],
  })
  assert.equal(result.sizeVerdict, 'story')
})

test('a remaining requirement on an existing contract is a task', async () => {
  const { result } = await reconcile({
    requirements: [
      {
        id: 'R1',
        requirement: 'add Apple to the provider list',
        status: 'absent',
        evidence: ['services/auth/providers.py:44 — google, linkedin, microsoft'],
        needsNewContract: false,
        behaviourExistsButWrong: false,
        repos: ['/repo/auth'],
      },
    ],
  })
  assert.equal(result.sizeVerdict, 'task')
})

test('only a multi-repo delta with a decision nobody has made is still an epic', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'a', status: 'absent', evidence: ['x:1'], needsNewContract: true, repos: ['/repo/auth'] },
      { id: 'R2', requirement: 'b', status: 'absent', evidence: ['y:2'], needsNewContract: true, repos: ['/repo/web'] },
    ],
    unsettled: true,
  })
  assert.equal(result.sizeVerdict, 'epic')
  assert.equal(result.sizing.spansMultipleRepos, true)
})

test('the same multi-repo delta with the decision already settled is not an epic', async () => {
  const { result } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'a', status: 'absent', evidence: ['x:1'], needsNewContract: true, repos: ['/repo/auth'] },
      { id: 'R2', requirement: 'b', status: 'absent', evidence: ['y:2'], needsNewContract: true, repos: ['/repo/web'] },
    ],
    unsettled: false,
  })
  assert.equal(result.sizeVerdict, 'story')
})

// ── the delta document ──────────────────────────────────────────────────────────

test('the delta PRD is authored from the remaining requirements only', async () => {
  const { result, calls } = await reconcile({
    requirements: [
      { id: 'R1', requirement: 'enrol TOTP', status: 'shipped', evidence: ['services/auth/mfa.py:118'] },
      { id: 'R2', requirement: 'challenge at sign-in', status: 'absent', evidence: ['routes.py:1-400 has no challenge route'] },
    ],
  })
  const write = agentCalls(calls, 'delta:write')
  assert.equal(write.length, 1)
  assert.match(write[0].prompt, /R2/, 'the remaining requirement is handed to the author')
  assert.match(write[0].prompt, /MUST NOT appear as work/, 'and the shipped one is explicitly excluded from the work')
  assert.equal(result.deltaPrdPath, '/docs/prd/mfa.delta.md')
  assert.equal(result.deltaPrd.body, 'R2. A user is challenged for MFA at sign-in.')
})

test('a delta that could not be written fails the mini rather than passing the original through', async () => {
  const { result } = await runWorkflowScript(reconciliation, {
    args: { prd: PRD },
    agentImpl: (call) => {
      if (call.label === 'reconcile:prd-vs-reality') {
        return {
          requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['nope'] }],
          deltaIsInfraOnly: false,
          unsettledTechnicalDecision: false,
          evidenceSummary: 's',
        }
      }
      if (call.label === 'reconcile:dependency-changes') return DEPENDENCY_CLEAN
      return { ok: false, path: '', body: '', error: 'disk full' }
    },
  })
  assert.equal(result.ok, false)
  assert.match(result.reason, /delta PRD was not written/)
})

test('an empty PRD is refused, not reported as a zero delta', async () => {
  // "Nothing remains" and "nothing was supplied" both reduce to deltaCount 0, and the
  // caller closes the work item on the first. Conflating them closes unexamined work.
  const { result } = await runWorkflowScript(reconciliation, { args: { prd: { body: '   ' } } })
  assert.equal(result.ok, false)
  assert.equal(result.deltaCount, 0)
  assert.match(result.reason, /empty PRD body/)
})

// ── the two checkers are independent ────────────────────────────────────────────

test('reality and dependency currency are checked by two different agents', async () => {
  const { calls } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'] }],
  })
  const reality = agentCalls(calls, 'reconcile:prd-vs-reality')[0]
  const deps = agentCalls(calls, 'reconcile:dependency-changes')[0]
  assert.equal(reality.opts.agentType, 'agent-teams-workforce:prd-reality-reconciler')
  assert.equal(deps.opts.agentType, 'agent-teams-workforce:dependency-change-detector')
  assert.notEqual(reality.opts.agentType, deps.opts.agentType)
})

test('the reconciler is told to pin every aws command to a profile', async () => {
  // Full admin credentials against the wrong account is the failure mode that makes
  // live verification worse than not doing it.
  const { calls } = await reconcile({
    requirements: [{ id: 'R1', requirement: 'x', status: 'absent', evidence: ['e'] }],
  })
  assert.match(agentCalls(calls, 'reconcile:prd-vs-reality')[0].prompt, /--profile dev/)
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
  verdict: 'partial',
  requirements: [
    { id: 'R1', requirement: 'a', status: 'shipped', evidence: ['x:1'] },
    { id: 'R2', requirement: 'b', status: 'absent', evidence: ['y:2'] },
  ],
  deltaCount: 1,
  deltaPrdPath: '/docs/prd/mfa.delta.md',
  deltaPrd: { path: '/docs/prd/mfa.delta.md', body: 'ONLY R2 remains.' },
  sizeVerdict: 'story',
  infraOnly: false,
  ledger: { phase: 'prd-reconciliation' },
}

/** Run prd-to-spec far enough to observe what reconciliation did, with G1 stubbed to loop out. */
async function composite(reconResult, { onCalls } = {}) {
  const seen = []
  const { result, calls } = await runWorkflowScript(prdToSpec, {
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
  return { result, seen }
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

test('a zero delta short-circuits to close without spending a gate', async () => {
  const { result, seen } = await composite({
    ok: true,
    verdict: 'shipped',
    requirements: [{ id: 'R1', requirement: 'a', status: 'shipped', evidence: ['x:1'] }],
    deltaCount: 0,
    deltaPrdPath: null,
    deltaPrd: null,
    sizeVerdict: 'close',
    infraOnly: false,
  })
  assert.equal(result.ok, true)
  assert.equal(result.action, 'close')
  assert.equal(
    seen.filter((c) => c.name === 'agent-teams-workforce:gate-enforce').length,
    0,
    'no gate is convened over work that is already done',
  )
  assert.equal(seen.filter((c) => c.name === 'agent-teams-workforce:prd-validation').length, 0)
})

test('a bug-sized delta reroutes to bug-fix without spending a gate', async () => {
  const { result, seen } = await composite({
    ...RECON_OK,
    sizeVerdict: 'bug',
  })
  assert.equal(result.ok, true)
  assert.equal(result.action, 'reroute')
  assert.equal(result.composite, 'bug-fix')
  assert.equal(result.deltaPrdPath, '/docs/prd/mfa.delta.md')
  assert.equal(seen.filter((c) => c.name === 'agent-teams-workforce:gate-enforce').length, 0)
})

test('an infrastructure-only delta reroutes to infra-change', async () => {
  const { result } = await composite({ ...RECON_OK, sizeVerdict: 'task', infraOnly: true })
  assert.equal(result.action, 'reroute')
  assert.equal(result.composite, 'infra-change')
})

test('downstream phases receive the delta PRD, never the raw incoming PRD', async () => {
  const { seen } = await composite(RECON_OK)
  const validation = seen.find((c) => c.name === 'agent-teams-workforce:prd-validation')
  assert.ok(validation, 'validation ran')
  assert.equal(validation.payload.prd.path, '/docs/prd/mfa.delta.md')
  assert.equal(validation.payload.prd.body, 'ONLY R2 remains.')
  assert.notEqual(validation.payload.prd.body, PRD.body, 'the original ambition is not what gets specified')
})

test('the original PRD is handed to reconciliation, and only there', async () => {
  const { seen } = await composite(RECON_OK)
  const recon = seen.find((c) => c.name === 'agent-teams-workforce:prd-reconciliation')
  assert.equal(recon.payload.prd.body, PRD.body, 'reconciliation is the one phase that sees the original')
  const others = seen.filter(
    (c) => c.name !== 'agent-teams-workforce:prd-reconciliation' && c.payload && c.payload.prd,
  )
  for (const c of others) {
    assert.notEqual(c.payload.prd.body, PRD.body, `${c.name} must not receive the original PRD`)
  }
})

test('a failed reconciliation stops the run — it is never read as a greenfield delta', async () => {
  const { result, seen } = await composite({ ok: false, reason: 'could not read the repository' })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'prd-reconciliation')
  assert.equal(seen.filter((c) => c.name === 'agent-teams-workforce:prd-validation').length, 0)
  assert.ok(result.partial.originalPrd, 'and the PRD it was handed comes back with it')
})

test('a delta claimed but not delivered stops the run rather than falling back to the original', async () => {
  const { result, seen } = await composite({ ...RECON_OK, deltaPrdPath: '', deltaPrd: null })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'prd-reconciliation')
  assert.equal(seen.filter((c) => c.name === 'agent-teams-workforce:prd-validation').length, 0)
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
