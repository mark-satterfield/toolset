// The detailing of one repository: each delta item placed in it, compared with the code on
// its main, gets one status — add, modify, remove, done, planned-elsewhere — with a citation.
//
// These tests hold the properties that make the detailing usable downstream: every placed item
// comes back exactly once, a status outside the five or an uncited status fails the run, the UI
// is resolved bundle-first, and the composite details per repository after the TRD and blocks a
// repository's Spec when its detailing fails.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, workflowCalls, agentCalls } from './helpers/run-workflow.mjs'
import { withLifecycle, TEST_EPIC, ARTIFACT_ARGS, TEST_ARCHITECTURE, TEST_DELTA_ITEMS, TEST_DESIGN_SYSTEM } from './helpers/bead-writer.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WORKFLOWS = path.resolve(HERE, '..', '..', 'workflows')
const reconciliation = path.join(WORKFLOWS, 'prd-reconciliation.js')
const prdToSpec = path.join(WORKFLOWS, 'prd-to-spec.js')

const PRD = {
  id: 'ssbd-sp6n',
  title: 'Multi-factor authentication',
  path: '/docs/prd/mfa.md',
  repoPath: '/repo/auth',
}
const ITEMS = [
  { id: 'D1', element: 'auth-service', views: ['/arch/target/mfa/delta/05-building-block-view/mfa.md'] },
  { id: 'D2', element: 'mfa-table', views: ['/arch/target/mfa/delta/05-building-block-view/mfa.md'] },
]
const DELTA = { targetDir: '/arch/target/mfa', deltaDir: '/arch/target/mfa/delta' }
const DEPENDENCY_CLEAN = { current: true, changeFindings: [], evidence: 'lockfiles unchanged' }
const LABEL = 'detail:delta-and-dependencies'

/** Scripted detailing — the ONE session that carries both checks. */
function detailAgents({ items, uiAuthority }) {
  return (call) => {
    if (call.label === LABEL) {
      return {
        items,
        evidenceSummary: 'read the auth service on main',
        dependencyChanges: DEPENDENCY_CLEAN,
        ...(uiAuthority ? { uiAuthority } : {}),
      }
    }
    return null
  }
}

const DESIGN_SYSTEM = { packagesDir: '/design/packages', mocksDir: '/design/pages', shellsDir: '/design/shells' }

async function detail(scripted, args = {}) {
  return runWorkflowScript(reconciliation, {
    args: { prd: PRD, repos: ['/repo/auth'], items: ITEMS, delta: DELTA, ...DESIGN_SYSTEM, ...args },
    agentImpl: detailAgents(scripted),
  })
}

const item = (id, status, extra = {}) => ({
  id,
  element: ITEMS.find((i) => i.id === id).element,
  status,
  from: 'x',
  to: 'y',
  evidence: ['services/auth/mfa.py:118'],
  surface: 'service',
  ...extra,
})

// ── every placed item comes back, with one status ───────────────────────────────

test('every placed item comes back with its status, from and to', async () => {
  const { result, calls } = await detail({ items: [item('D1', 'modify'), item('D2', 'add', { from: 'absent' })] })
  assert.equal(result.ok, true)
  assert.equal(result.items.length, 2)
  assert.deepEqual(result.counts, { add: 1, modify: 1, remove: 0, done: 0, 'planned-elsewhere': 0 })
  assert.equal(calls.filter((c) => c.kind === 'agent').length, 1, 'one detailing session and nothing else')
})

test('a placed item with no entry fails the run, naming it', async () => {
  const { result } = await detail({ items: [item('D1', 'done')] })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'detailing')
  assert.ok(result.failedItems.some((f) => f.id === 'D2'))
})

test('an unrecognised status fails the run naming the item, rather than being coerced', async () => {
  const { result } = await detail({ items: [item('D1', 'conforms'), item('D2', 'add')] })
  assert.equal(result.ok, false)
  assert.match(result.reason, /D1: status "conforms" is not one of add, modify, remove, done, planned-elsewhere/)
})

test('a status with no file:line fails the run; planned-elsewhere also names its bead', async () => {
  const { result } = await detail({ items: [item('D1', 'add', { evidence: ['looked around'] }), item('D2', 'planned-elsewhere', { evidence: [] })] })
  assert.equal(result.ok, false)
  assert.match(result.reason, /D1: add cites no file:line/)
  assert.match(result.reason, /D2: planned-elsewhere cites no file:line/)
  assert.match(result.reason, /D2: planned-elsewhere names no bead in plannedBy/)
  const noCite = await detail({ items: [item('D1', 'done'), item('D2', 'planned-elsewhere', { evidence: [], plannedBy: 'ssbd-abc' })] })
  assert.equal(noCite.result.ok, false, 'a bead alone is not a citation')
  const ok = await detail({ items: [item('D1', 'done'), item('D2', 'planned-elsewhere', { plannedBy: 'ssbd-abc' })] })
  assert.equal(ok.result.ok, true)
})

test('the schema holds the five statuses and requires evidence of every item', async () => {
  const { calls } = await detail({ items: [item('D1', 'done'), item('D2', 'done')] })
  const schema = agentCalls(calls, LABEL)[0].opts.schema
  const entry = schema.properties.items.items
  assert.ok(entry.required.includes('evidence'))
  assert.deepEqual(entry.properties.status.enum, ['add', 'modify', 'remove', 'done', 'planned-elsewhere'])
})

// ── the UI authority chain ──────────────────────────────────────────────────────

test('the resolved cds bundle travels with the detailing so spec authoring can read its build-specs', async () => {
  const { result } = await detail({
    items: [item('D1', 'add', { surface: 'ui' }), item('D2', 'done')],
    uiAuthority: {
      bundlePath: '/repo/auth/design-mocks/packages/batch-20260819T191805Z',
      artifactsConsulted: ['views/settings-profile/spec/build-spec.md'],
      shellsConsulted: ['personal-agent-shell.html'],
      pagesConsulted: [],
    },
  })
  assert.equal(result.uiAuthority.bundlePath, '/repo/auth/design-mocks/packages/batch-20260819T191805Z')
  assert.deepEqual(result.uiAuthority.artifactsConsulted, ['views/settings-profile/spec/build-spec.md'])
  assert.equal(result.uiAuthority.mocksDir, '/design/pages', 'the mocks directory is the one the caller supplied')
})

test('the detailing is pointed at the hand-off bundle FIRST and the loose mocks second', async () => {
  const { calls } = await detail({ items: [item('D1', 'done'), item('D2', 'done')] })
  const [checker] = agentCalls(calls, LABEL)
  assert.match(checker.prompt, /HAND-OFF BUNDLE/)
  assert.match(checker.prompt, /MANIFEST\.tsv/)
  assert.ok(checker.prompt.includes('/design/packages'), 'the bundle root is the one the caller supplied')
  assert.ok(!checker.prompt.includes('design-mocks'), 'no directory is derived from the repository')
})

// ── one session, a leaf, scoped to one repository ───────────────────────────────

test('the detailing and dependency currency are both checked by ONE session', async () => {
  const { calls, result } = await detail({ items: [item('D1', 'done'), item('D2', 'done')] })
  const combined = agentCalls(calls, LABEL)
  assert.equal(combined.length, 1)
  assert.equal(combined[0].opts.agentType, 'prd-reality-reconciler')
  assert.match(combined[0].prompt, /CHECK 2/)
  assert.ok(result.dependencyChanges)
})

test('the mini is a leaf — it never nests another workflow', async () => {
  const { calls } = await detail({ items: [item('D1', 'done'), item('D2', 'done')] })
  assert.equal(calls.filter((c) => c.kind === 'workflow').length, 0)
})

test('more than one repository is refused before any session runs', async () => {
  const { result, calls } = await detail({ items: [] }, { repos: ['/repo/a', '/repo/b'] })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'input')
  assert.equal(calls.filter((c) => c.kind === 'agent').length, 0)
})

// ── the composite ───────────────────────────────────────────────────────────────

const DETAIL_OK = {
  ok: true,
  items: [{ id: 'D1', element: 'auth-service', status: 'modify', from: 'password only', to: 'password and TOTP', evidence: ['auth.py:3'], plannedBy: null, surface: 'service' }],
  counts: { add: 0, modify: 1, remove: 0, done: 0, 'planned-elsewhere': 0 },
  uiAuthority: { bundlePath: null, mocksDir: null, artifactsConsulted: [], shellsConsulted: [], pagesConsulted: [] },
  ledger: { phase: 'prd-reconciliation' },
}

/** Run prd-to-spec all the way through, with every mini minimal. */
async function composite(detailResult) {
  const seen = []
  let storyN = 0
  const { result, calls, logs } = await runWorkflowScript(prdToSpec, {
    args: { prd: { ...PRD }, repoPath: '/repo/control', epic: TEST_EPIC, archPath: '/arch', designSystem: TEST_DESIGN_SYSTEM, ...ARTIFACT_ARGS },
    workflowImpl: (call) => {
      seen.push(call)
      const name = String(call.name || '')
      if (name.endsWith('prd-reconciliation')) return detailResult
      if (name.endsWith('architecture')) return { ...TEST_ARCHITECTURE }
      if (name.endsWith('repo-scoping')) {
        return { ok: true, repos: ['/repo/auth'], placements: [{ repoPath: '/repo/auth', repoName: 'auth', itemIds: TEST_DELTA_ITEMS.map((i) => i.id), frontend: false, rationale: 'r' }], noCode: [], createdRepos: [], creationFailures: [] }
      }
      if (name.endsWith('trd-authoring')) return { ok: true, trdPath: '/proj/trd.md', trd: { id: 'TRD-1', summary: 'sum' } }
      if (name.endsWith('spec-authoring')) {
        storyN += 1
        const repoPath = (call.payload && call.payload.repoPath) || null
        return { ok: true, story: { key: `S${storyN}`, type: 'story', id: `bd-S${storyN}`, elabKey: `story:S${storyN}`, title: `Story for ${repoPath}`, description: 'd', repoPath, parentEpicKey: 'E1' } }
      }
      if (name.endsWith('task-decomposition')) {
        const sk = ((call.payload && call.payload.story) || {}).key || 'S?'
        return { ok: true, tasks: [{ key: 'T1', id: `bd-${sk}-T1`, elabKey: `task:${sk}:t`, action: 'created', title: 't', dependsOn: [] }], summary: { created: 1, updated: 0 } }
      }
      return null
    },
    agentImpl: withLifecycle(),
  })
  return { result, seen, calls, logs }
}

test('the detailing runs per repository after the span and the TRD, immediately before its spec', async () => {
  const { seen, result } = await composite(DETAIL_OK)
  assert.equal(result.ok, true, result.headline)
  const idx = (suffix) => seen.findIndex((c) => String(c.name || '').endsWith(suffix))
  const reconIdx = idx('prd-reconciliation')
  assert.ok(reconIdx > idx('architecture'))
  assert.ok(reconIdx > idx('repo-scoping'))
  assert.ok(reconIdx > idx('trd-authoring'))
  assert.ok(reconIdx < idx('spec-authoring'))
  assert.equal(workflowCalls(seen, 'agent-teams-workforce:prd-reconciliation').length, 1)
})

test('the detailing receives the delta items placed in its one repository', async () => {
  const { seen } = await composite(DETAIL_OK)
  const recon = seen.find((c) => String(c.name || '').endsWith('prd-reconciliation'))
  assert.deepEqual(recon.payload.repos, ['/repo/auth'])
  assert.deepEqual(recon.payload.items.map((i) => i.id), TEST_DELTA_ITEMS.map((i) => i.id))
  assert.equal(recon.payload.delta.deltaDir, TEST_ARCHITECTURE.deltaDir)
})

test('the spec is told the change for each add, modify or remove item, and gets the target and delta views', async () => {
  const { seen } = await composite(DETAIL_OK)
  const spec = seen.find((c) => String(c.name || '').endsWith('spec-authoring'))
  assert.ok(spec.payload.constraints.some((x) => /CHANGE: password only → password and TOTP/.test(String(x))))
  assert.equal(spec.payload.architecture.deltaDir, TEST_ARCHITECTURE.deltaDir)
})

test('a failed detailing blocks that repository\'s Spec', async () => {
  const { seen, result } = await composite({ ok: false, stage: 'detailing', reason: 'D1: status "x" is not one of add, modify, remove, done, planned-elsewhere', items: [] })
  assert.equal(seen.filter((c) => String(c.name || '').endsWith('spec-authoring')).length, 0, 'no spec is authored without its detailing')
  assert.equal(result.ok, false)
})

test('the target folder is removed once the Epic is done', async () => {
  const { calls, result } = await composite(DETAIL_OK)
  assert.equal(result.ok, true)
  const removal = agentCalls(calls, 'arch:target-remove')
  assert.equal(removal.length, 1)
  assert.match(removal[0].prompt, /arch-target-remove --arch-root '\/arch' --target-dir '\/arch\/target\/mfa'/)
  assert.equal(result.targetRemoval.removed, true)
})
