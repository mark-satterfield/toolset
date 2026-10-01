// The repo span is the set of repositories the approved architecture delta changes.
//
// The polyrepo-steward places each delta item (one element the delta shows) in the repository
// whose code changes for it, or records that it has no code in this project, and creates the
// new repositories the approved target names. These tests pin what makes the span trustworthy:
// every item is placed exactly once, the span is the placements' repositories, the launch
// repository carries no authority, and a failed placement stops the run.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, agentCalls, workflowCalls } from './helpers/run-workflow.mjs'
import { withLifecycle, TEST_EPIC, ARTIFACT_ARGS, TEST_ARCHITECTURE } from './helpers/bead-writer.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WF = path.resolve(HERE, '..', '..', 'workflows')
const SCOPING = path.join(WF, 'repo-scoping.js')
const PRD_TO_SPEC = path.join(WF, 'prd-to-spec.js')

const PRD = { id: 'PRD-1', title: 'PRD One', path: '/docs/prd-one.md' }
const ITEMS = [
  { id: 'D1', element: 'alpha-service', views: ['/arch/target/one/delta/05-building-block-view/one.md'] },
  { id: 'D2', element: 'Amazon SQS', views: ['/arch/target/one/delta/05-building-block-view/one.md'] },
]
const DELTA = { subject: 'one', targetDir: '/arch/target/one', deltaDir: '/arch/target/one/delta', items: ITEMS }

/** A steward fixture: places D1 in alpha and records D2 as having no code here, unless told otherwise. */
function stewardAgents({ placements, noCode, createdRepos = [], creationFailures = [] } = {}) {
  return (call) => {
    if (call.label === 'scope:place-delta') {
      return {
        placements: placements || [{ repoPath: '/repos/alpha', repoName: 'alpha', itemIds: ['D1'], frontend: false, rationale: 'owns it' }],
        noCode: noCode || [{ itemId: 'D2', reason: 'managed service configured in alpha' }],
        createdRepos,
        creationFailures,
        surveySummary: '3 repos',
        spanRationale: 'ruled',
      }
    }
    return null
  }
}

async function scope(agents, args = {}) {
  return runWorkflowScript(SCOPING, { args: { prd: PRD, delta: DELTA, ...args }, agentImpl: agents || stewardAgents() })
}

// ── The mini ───────────────────────────────────────────────────────────────────

test('one steward session places the delta, and the span is the repositories it names', async () => {
  const { result, calls } = await scope()
  assert.equal(result.ok, true, result.reason)
  assert.deepEqual(result.repos, ['/repos/alpha'])
  assert.deepEqual(calls.filter((c) => c.kind === 'agent').map((c) => c.label), ['scope:place-delta'])
  const [steward] = agentCalls(calls, 'scope:place-delta')
  assert.equal(steward.opts.agentType, 'agent-teams-workforce:polyrepo-steward')
  assert.ok(steward.prompt.includes(DELTA.deltaDir), 'the steward reads the delta')
  assert.ok(steward.prompt.includes('D1: alpha-service'), 'and is given every item')
})

test('an item placed nowhere fails the run, naming it', async () => {
  const { result } = await scope(stewardAgents({ noCode: [] }))
  assert.equal(result.ok, false)
  assert.match(result.reason, /not placed: D2 Amazon SQS/)
})

test('an item placed twice fails the run', async () => {
  const { result } = await scope(
    stewardAgents({
      placements: [
        { repoPath: '/repos/alpha', repoName: 'alpha', itemIds: ['D1'], frontend: false, rationale: 'r' },
        { repoPath: '/repos/beta', repoName: 'beta', itemIds: ['D1', 'D2'], frontend: false, rationale: 'r' },
      ],
      noCode: [],
    })
  )
  assert.equal(result.ok, false)
  assert.match(result.reason, /placed more than once: D1/)
})

test('a delta with no item is refused before any session runs', async () => {
  const { result, calls } = await scope(null, { delta: { ...DELTA, items: [] } })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'input')
  assert.equal(calls.filter((c) => c.kind === 'agent').length, 0)
})

// ── The composite ──────────────────────────────────────────────────────────────

/** Every mini answers minimally. `scopingResult` is what repo-scoping returns. */
function compositeWorkflows({ scopingResult }) {
  let storyN = 0
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('prd-reconciliation')) {
      const items = (call.payload.items || []).map((i) => ({ id: i.id, element: i.element, status: 'add', from: 'absent', to: 'x', evidence: ['f.py:1'], plannedBy: null, surface: 'service' }))
      return { ok: true, items, counts: { add: items.length }, uiAuthority: {} }
    }
    if (name.endsWith('architecture')) return { ...TEST_ARCHITECTURE }
    if (name.endsWith('repo-scoping')) return scopingResult
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
  }
}

const RULED = (repos) => ({
  ok: true,
  repos,
  placements: repos.map((r) => ({ repoPath: r, repoName: r, itemIds: ['D1'], frontend: false, rationale: 'ruled' })),
  noCode: [],
  createdRepos: [],
  creationFailures: [],
})

const ARGS = { prd: { ...PRD }, repoPath: '/repos/where-the-human-stood', epic: TEST_EPIC, archPath: '/arch', ...ARTIFACT_ARGS }

test('the composite rules the span from the delta and fans out over what it ruled', async () => {
  const ruled = ['/repos/alpha', '/repos/beta', '/repos/gamma']
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, { args: ARGS, workflowImpl: compositeWorkflows({ scopingResult: RULED(ruled) }), agentImpl: withLifecycle() })
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  const [scoping] = workflowCalls(calls, 'agent-teams-workforce:repo-scoping')
  assert.ok(scoping, 'the span is ruled, once')
  assert.equal(scoping.payload.delta.deltaDir, TEST_ARCHITECTURE.deltaDir, 'from the approved delta')
  assert.ok(Array.isArray(scoping.payload.delta.items) && scoping.payload.delta.items.length, 'with the items depscore.py arch-delta listed')
  assert.deepEqual(result.repoSpan, ruled)
  assert.deepEqual(result.hierarchy.stories.map((s) => s.repoPath), ruled, 'one Story per repository the delta changes')
  const recons = workflowCalls(calls, 'agent-teams-workforce:prd-reconciliation')
  assert.deepEqual(recons.map((c) => c.payload.repos), ruled.map((r) => [r]), 'one detailing per repository, each scoped to it')
})

test('the launch repository is not the span', async () => {
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, { args: ARGS, workflowImpl: compositeWorkflows({ scopingResult: RULED(['/repos/alpha']) }), agentImpl: withLifecycle() })
  const [scoping] = workflowCalls(calls, 'agent-teams-workforce:repo-scoping')
  assert.equal(scoping.payload.seedRepos, undefined, 'the launch repository is not offered to the placement')
  assert.deepEqual(result.repoSpan, ['/repos/alpha'])
})

test('a failed placement STOPS the run — it never falls back to the launch repository', async () => {
  const { result, calls } = await runWorkflowScript(PRD_TO_SPEC, {
    args: ARGS,
    workflowImpl: compositeWorkflows({ scopingResult: { ok: false, reason: 'not placed: D1 alpha-service' } }),
    agentImpl: withLifecycle(),
  })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'repo-scoping')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:spec-authoring').length, 0, 'nothing may be specified against a guessed span')
})
