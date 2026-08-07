// prd-to-spec must emit the whole tree, not a flat task list.
//
// The composite is the only place the hierarchy is assembled: it pairs the Epic
// with the PRD (backfilling one when an older PRD predates the concept), fans
// spec authoring out per repo so each Story is scoped to exactly one, and
// decomposes each Story into its own tasks. A flat bead set loses every parent
// link, and route-bead then refuses to work any of it.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const prdToSpec = path.resolve(HERE, '..', '..', 'workflows', 'prd-to-spec.js')

/** Every gate passes; every mini returns a minimal well-formed artifact. */
function makeWorkflowImpl({ repos, withEpic }) {
  let storyN = 0
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) {
      return { verdict: 'pass', criteria: [], flags: [] }
    }
    if (name.endsWith('prd-creation')) {
      return {
        ok: true,
        prd: { id: 'PRD-1', title: 'Created PRD', body: 'b' },
        ...(withEpic ? { epic: { key: 'E1', type: 'epic', title: 'Created PRD', description: 'd', prdRef: 'PRD-1' } } : {}),
      }
    }
    if (name.endsWith('prd-validation')) {
      return { ok: true, validatedPrd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, findings: [] }
    }
    if (name.endsWith('architecture')) return { ok: true, decision: { id: 'AD-1' }, sad: { path: 's' } }
    if (name.endsWith('trd-authoring')) return { ok: true, trd: { id: 'TRD-1', summary: 'sum' } }
    if (name.endsWith('spec-authoring')) {
      storyN += 1
      const repoPath = (call.payload && call.payload.repoPath) || repos[storyN - 1] || null
      return {
        ok: true,
        specSet: { apiSpec: { summary: `spec for ${repoPath}` } },
        story: {
          key: `S${storyN}`,
          type: 'story',
          title: `Story for ${repoPath}`,
          description: 'd',
          repoPath,
          parentEpicKey: 'E1',
        },
      }
    }
    if (name.endsWith('task-decomposition')) {
      const story = (call.payload && call.payload.story) || {}
      const sk = story.key || story.id || 'S?'
      return {
        ok: true,
        beadSet: [
          { key: `${sk}-T1`, type: 'task', parentStoryId: sk, title: 't1', description: 'd', acceptanceCriteria: ['a'] },
          { key: `${sk}-T2`, type: 'task', parentStoryId: sk, title: 't2', description: 'd', acceptanceCriteria: ['a'] },
        ],
      }
    }
    return null
  }
}

async function run({ args, repos, withEpic = true }) {
  return runWorkflowScript(prdToSpec, {
    args,
    workflowImpl: makeWorkflowImpl({ repos, withEpic }),
    agentImpl: () => null,
  })
}

test('a single-repo PRD emits one Epic, one Story, and that Story\'s tasks', async () => {
  const { result } = await run({
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a' },
    repos: ['/repo-a'],
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${JSON.stringify(result.detail || '')}`)
  assert.ok(result.hierarchy, 'the composite must return a `hierarchy`, not only a flat beadSet')

  const { epic, stories, tasks } = result.hierarchy
  assert.equal(epic.type, 'epic')
  assert.equal(stories.length, 1, 'one repo means exactly one Story')
  assert.equal(stories[0].type, 'story')
  assert.equal(stories[0].repoPath, '/repo-a', 'a Story is scoped to a single repo')
  assert.equal(stories[0].parentEpicKey, epic.key, 'every Story hangs under the Epic')
  assert.ok(tasks.length > 0)
  for (const t of tasks) {
    assert.equal(t.type, 'task')
    assert.ok(t.parentStoryId, 'every Task must name its parent Story')
  }
})

test('a PRD spanning three repos emits one Epic and one Story PER REPO', async () => {
  const repos = ['/repo-a', '/repo-b', '/repo-c']
  const { result } = await run({
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a', repos },
    repos,
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}`)
  const { epic, stories, tasks } = result.hierarchy

  assert.ok(epic, 'one Epic spans the repos')
  assert.equal(stories.length, 3, 'one Story per repo — a Story is never multi-repo')
  assert.deepEqual(
    stories.map((s) => s.repoPath).sort(),
    [...repos].sort(),
    'each Story carries exactly one of the repos',
  )
  for (const s of stories) assert.equal(s.parentEpicKey, epic.key)

  // Every Story's tasks are present and correctly parented.
  for (const s of stories) {
    const own = tasks.filter((t) => t.parentStoryId === s.key)
    assert.ok(own.length > 0, `Story ${s.key} (${s.repoPath}) contributed no tasks`)
  }
})

test('an existing PRD with no Epic gets one BACKFILLED — it is not skipped', async () => {
  const { result } = await run({
    args: { prd: { id: 'PRD-OLD', title: 'Legacy PRD', body: 'b' }, repoPath: '/repo-a' },
    repos: ['/repo-a'],
    withEpic: false,
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}`)
  assert.ok(
    result.hierarchy && result.hierarchy.epic && result.hierarchy.epic.key,
    'a PRD written before the hierarchy existed must still get an Epic — most PRDs here predate the concept',
  )
  assert.equal(result.hierarchy.epic.type, 'epic')
})

test('a caller-supplied Epic is used rather than backfilled over', async () => {
  const supplied = { key: 'E-EXISTING', type: 'epic', title: 'Already there', description: 'd', prdRef: 'PRD-1' }
  const { result } = await run({
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a', epic: supplied },
    repos: ['/repo-a'],
    withEpic: false,
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}`)
  assert.equal(
    result.hierarchy.epic.key,
    'E-EXISTING',
    'when the Epic already exists the composite must adopt it, not mint a duplicate',
  )
})

test('the flat beadSet is retained for existing callers and holds only tasks', async () => {
  const { result } = await run({
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a', repos: ['/repo-a', '/repo-b'] },
    repos: ['/repo-a', '/repo-b'],
  })

  assert.equal(result.ok, true)
  assert.ok(Array.isArray(result.beadSet), 'beadSet must survive for callers that already read it')
  assert.equal(result.beadSet.length, result.hierarchy.tasks.length)
  for (const b of result.beadSet) assert.equal(b.type, 'task')
})

test('each repo gets a DISTINCT Story key — sibling Stories must not collide', async () => {
  const repos = ['/repo-a', '/repo-b', '/repo-c']
  const seen = []
  const { result } = await runWorkflowScript(prdToSpec, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a', repos },
    // Echo back whatever key the composite asked for, exactly as spec-authoring does.
    // spec-authoring defaults to 'S1', so a composite that fails to pass a distinct
    // storyKey per repo collapses every repo onto one phantom Story.
    workflowImpl: (call) => {
      const name = String(call.name || '')
      if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) {
        return { verdict: 'pass', criteria: [], flags: [] }
      }
      if (name.endsWith('prd-validation')) return { ok: true, validatedPrd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, findings: [] }
      if (name.endsWith('architecture')) return { ok: true, decision: { id: 'AD-1' } }
      if (name.endsWith('trd-authoring')) return { ok: true, trd: { id: 'TRD-1', summary: 's' } }
      if (name.endsWith('spec-authoring')) {
        const key = (call.payload && call.payload.storyKey) || 'S1'
        const repoPath = (call.payload && call.payload.repoPath) || null
        seen.push({ key, repoPath })
        return {
          ok: true,
          specSet: { apiSpec: { summary: 's' } },
          story: { key, type: 'story', title: `Story ${key}`, description: 'd', repoPath, parentEpicKey: 'E1' },
        }
      }
      if (name.endsWith('task-decomposition')) {
        const sk = ((call.payload && call.payload.story) || {}).key || 'S?'
        return { ok: true, beadSet: [{ key: `${sk}-T1`, type: 'task', parentStoryId: sk, title: 't', description: 'd', acceptanceCriteria: ['a'] }] }
      }
      return null
    },
    agentImpl: (call) =>
      call.label === 'sequence:story-dag' ? { edges: [], buildOrder: ['S1', 'S2', 'S3'], acyclic: true } : null,
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}`)
  const keys = result.hierarchy.stories.map((s) => s.key)
  assert.equal(new Set(keys).size, repos.length, `sibling Stories share a key: [${keys.join(', ')}]`)

  // And each key must belong to exactly one repo.
  const byKey = new Map(seen.map((s) => [s.key, s.repoPath]))
  assert.equal(byKey.size, repos.length, 'one key per repo')
})

test('tasks land under their own Story, not pooled under the first', async () => {
  const repos = ['/repo-a', '/repo-b']
  const { result } = await run({
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a', repos },
    repos,
  })
  assert.equal(result.ok, true)
  const { stories, tasks } = result.hierarchy
  for (const s of stories) {
    const own = tasks.filter((t) => t.parentStoryId === s.key)
    assert.ok(own.length > 0, `Story ${s.key} (${s.repoPath}) has no tasks of its own`)
  }
  const orphans = tasks.filter((t) => !stories.some((s) => s.key === t.parentStoryId))
  assert.deepEqual(orphans, [], 'every task must point at a Story that exists in this hierarchy')
})

// ── Dependencies live at the Story level, and only there ──────────────────────

test('Stories carry the dependency graph; the Epic carries none', async () => {
  const repos = ['/repo-a', '/repo-b', '/repo-c']
  const { result } = await runWorkflowScript(prdToSpec, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a', repos },
    workflowImpl: makeWorkflowImpl({ repos, withEpic: true }),
    // The Story-dependency mapper is the only agent() call this composite makes.
    agentImpl: (call) =>
      call.label === 'sequence:story-dag'
        ? { edges: [{ from: 'S1', to: 'S2' }], buildOrder: ['S1', 'S2', 'S3'], acyclic: true }
        : null,
  })

  assert.equal(result.ok, true, `composite failed at ${result.stage}`)
  const { epic, stories, storyDependencies } = result.hierarchy

  assert.ok(storyDependencies, 'the hierarchy must carry a Story-level dependency graph')
  assert.deepEqual(storyDependencies.edges, [{ from: 'S1', to: 'S2' }])

  const s2 = stories.find((s) => s.key === 'S2')
  assert.deepEqual(s2.dependsOn, ['S1'], 'the edge must be folded onto the Story itself')
  const s3 = stories.find((s) => s.key === 'S3')
  assert.deepEqual(s3.dependsOn, [], 'a Story with no incoming edge depends on nothing')

  // An Epic orders whole PRDs against each other, which is a roadmap judgement and
  // not a build constraint this pipeline may make.
  assert.equal(epic.dependsOn, undefined, 'an Epic must not carry a dependency graph')
  assert.equal(epic.buildOrderIndex, undefined, 'an Epic must not be placed in a build order')
})

test('a single Story needs no dependency mapper run', async () => {
  const { calls } = await runWorkflowScript(prdToSpec, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a' },
    workflowImpl: makeWorkflowImpl({ repos: ['/repo-a'], withEpic: true }),
    agentImpl: () => null,
  })
  const mapperRuns = calls.filter((c) => c.kind === 'agent' && c.label === 'sequence:story-dag')
  assert.equal(mapperRuns.length, 0, 'one Story has nothing to depend on — do not spend an agent on it')
})

test('a cyclic Story graph fails the run rather than inventing an order', async () => {
  const repos = ['/repo-a', '/repo-b']
  const { result } = await runWorkflowScript(prdToSpec, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a', repos },
    workflowImpl: makeWorkflowImpl({ repos, withEpic: true }),
    agentImpl: (call) =>
      call.label === 'sequence:story-dag'
        ? { edges: [{ from: 'S1', to: 'S2' }, { from: 'S2', to: 'S1' }], buildOrder: [], acyclic: false, cycle: ['S1', 'S2', 'S1'] }
        : null,
  })

  assert.equal(result.ok, false)
  assert.equal(result.stage, 'story-dependencies')
  assert.deepEqual(result.cycle, ['S1', 'S2', 'S1'])
})

test('the TRD is authored once per PRD, not once per repo', async () => {
  const repos = ['/repo-a', '/repo-b', '/repo-c']
  const { calls } = await run({
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a', repos },
    repos,
  })

  const trdRuns = calls.filter((c) => c.kind === 'workflow' && String(c.name).endsWith('trd-authoring'))
  assert.equal(trdRuns.length, 1, 'a TRD derives from the PRD, so it is authored once however many repos the Epic spans')

  const specRuns = calls.filter((c) => c.kind === 'workflow' && String(c.name).endsWith('spec-authoring'))
  assert.equal(specRuns.length, repos.length, 'spec authoring runs once per repo — one Spec, one Story, one repo')
})
