// prd-to-spec WRITES its hierarchy. It does not hand it back with instructions.
//
// The composite used to return `hierarchy` and `beadSet` and deliberately not persist
// them: its own return text told the caller to run `bd` — epic first, then stories, then
// tasks — and the caller is a headless session. So the single step that makes an entire
// run durable was a paragraph addressed to a model working unattended, which had to get
// three levels of parent-before-child ordering and a key-to-id substitution right by hand
// with nothing checking the result. A run could decompose a PRD completely and persist
// none of it, or half of it, and report success either way.
//
// These tests pin the properties that close it, and they are properties of the SCRIPT,
// not of any prompt: the levels go out in order, each child carries the REAL id of its
// parent, a child of an unwritten parent is never attempted, and what comes back is what
// actually landed — including the two fields the campaign supervisor keys off.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, readWorkflowSource } from './helpers/run-workflow.mjs'
import { beadWriter, writerPayload, isWriterCall } from './helpers/bead-writer.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const prdToSpec = path.resolve(HERE, '..', '..', 'workflows', 'prd-to-spec.js')

/** Every gate passes; every mini returns a minimal well-formed artifact. */
function makeWorkflowImpl({ repos, epicKey = 'E1' }) {
  let storyN = 0
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) {
      return { verdict: 'pass', criteria: [], flags: [] }
    }
    if (name.endsWith('prd-reconciliation')) {
      return {
        ok: true,
        verdict: 'partial',
        requirements: [{ id: 'R1', requirement: 'r', status: 'absent', evidence: ['f.py:1'] }],
        deltaCount: 1,
        deltaPrdPath: '/prd/PRD-1.delta.md',
        deltaPrd: { path: '/prd/PRD-1.delta.md', body: 'b' },
        sizeVerdict: 'story',
        infraOnly: false,
      }
    }
    if (name.endsWith('prd-validation')) return { ok: true, validatedPrd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, findings: [] }
    if (name.endsWith('architecture')) return { ok: true, decision: { id: 'AD-1' }, sad: { path: 's' } }
    if (name.endsWith('repo-scoping')) {
      return {
        ok: true,
        repos,
        placements: repos.map((r) => ({ repoPath: r, repoName: r, workUnitIds: [], rationale: 'ruled', verified: true })),
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
      const repoPath = (call.payload && call.payload.repoPath) || repos[storyN - 1] || null
      const key = (call.payload && call.payload.storyKey) || `S${storyN}`
      return {
        ok: true,
        specSet: { apiSpec: { summary: `spec for ${repoPath}` } },
        story: { key, type: 'story', title: `Story for ${repoPath}`, description: 'd', repoPath, parentEpicKey: epicKey },
      }
    }
    if (name.endsWith('task-decomposition')) {
      const story = (call.payload && call.payload.story) || {}
      const sk = story.key || story.id || 'S?'
      return {
        ok: true,
        beadSet: [
          { key: 'T1', type: 'task', parentStoryId: sk, title: 't1', description: 'd', acceptanceCriteria: ['a'], dependsOn: [] },
          { key: 'T2', type: 'task', parentStoryId: sk, title: 't2', description: 'd', acceptanceCriteria: ['a'], dependsOn: ['T1'] },
        ],
      }
    }
    return null
  }
}

function run({ repos = ['/repo-a'], args = {}, writerOpts, agentExtra } = {}) {
  const writer = beadWriter(writerOpts)
  return runWorkflowScript(prdToSpec, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: repos[0], repos, ...args },
    workflowImpl: makeWorkflowImpl({ repos }),
    agentImpl: (call, calls) => writer(call) || (agentExtra ? agentExtra(call, calls) : null),
  })
}

/** The write/link dispatches, in the order the composite made them. */
const waves = (calls) => calls.filter(isWriterCall).map((c) => ({ label: c.label, payload: writerPayload(c) }))

// ── It writes, and it writes in the only order that can work ──────────────────

test('the composite WRITES the hierarchy itself — the caller is not asked to run bd', async () => {
  const { result, calls } = await run()
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)

  const labels = waves(calls).map((w) => w.label)
  assert.ok(labels.includes('beads:write-epic'), 'the Epic must be written by the run')
  assert.ok(labels.includes('beads:write-story'), 'the Stories must be written by the run')
  assert.ok(labels.includes('beads:write-task'), 'the Tasks must be written by the run')

  assert.equal(result.emission.verdict, 'complete')
  assert.equal(result.emissionOk, true)
  assert.equal(result.beadsEmitted, result.emission.created)
  assert.equal(
    result.beadsEmitted,
    1 + result.hierarchy.stories.length + result.hierarchy.tasks.length,
    'every node of the hierarchy is created when nothing fails',
  )
})

test('the levels go out PARENT BEFORE CHILD, and each child carries its parent\'s REAL id', async () => {
  const { result, calls } = await run({ repos: ['/repo-a', '/repo-b'] })
  assert.equal(result.ok, true, `composite failed at ${result.stage}`)

  const w = waves(calls)
  const iEpic = w.findIndex((x) => x.label === 'beads:write-epic')
  const iStory = w.findIndex((x) => x.label === 'beads:write-story')
  const iTask = w.findIndex((x) => x.label === 'beads:write-task')
  assert.ok(iEpic >= 0 && iStory > iEpic && iTask > iStory, `waves out of order: ${w.map((x) => x.label).join(' -> ')}`)

  const epicId = result.hierarchy.epic.id
  assert.ok(epicId, 'the returned Epic must carry the id it was written under')
  for (const b of w[iStory].payload.beads) {
    assert.equal(b.parentId, epicId, `Story ${b.key} must be written under the Epic's real id, not a local key`)
  }
  const storyIdByKey = Object.fromEntries(result.hierarchy.stories.map((s) => [s.key, s.id]))
  const parentOfTaskKey = Object.fromEntries(result.hierarchy.tasks.map((t) => [t.key, t.parentStoryId]))
  for (const b of w[iTask].payload.beads) {
    assert.equal(
      b.parentId,
      storyIdByKey[parentOfTaskKey[b.key]],
      `Task ${b.key} must be written under its OWN Story's real id`,
    )
  }
})

test('only this run\'s hierarchy is written — no sweep, no extra bead, no duplicate', async () => {
  const { result, calls } = await run({ repos: ['/repo-a', '/repo-b'] })
  const requested = waves(calls).flatMap((w) => (w.payload.beads || []).map((b) => b.key))
  const expected = [
    result.hierarchy.epic.key,
    ...result.hierarchy.stories.map((s) => s.key),
    ...result.hierarchy.tasks.map((t) => t.key),
  ]
  assert.deepEqual([...requested].sort(), [...expected].sort(), 'the write set must be exactly the hierarchy this run produced')
  assert.equal(new Set(requested).size, requested.length, 'no bead may be written twice')
})

test('the dependency edges are resolved to REAL ids by the script and linked', async () => {
  const { result, calls } = await run({ repos: ['/repo-a'] })
  const link = waves(calls).find((w) => w.label === 'beads:link')
  assert.ok(link, 'the intra-Story task edges are part of the product and must be written too')

  const taskIdByKey = Object.fromEntries(result.hierarchy.tasks.map((t) => [t.key, t.id]))
  const ids = new Set(Object.values(taskIdByKey))
  for (const e of link.payload.links) {
    assert.ok(ids.has(e.fromId) && ids.has(e.dependsOnId), `edge ${e.fromId} -> ${e.dependsOnId} must name written beads`)
  }
  assert.equal(result.emission.links.linked, result.emission.links.attempted)
})

// ── An Epic that is already a bead is ADOPTED, never written again ────────────

test('a caller-supplied Epic that already has an id is adopted, not re-created', async () => {
  const { result, calls } = await run({
    args: { epic: { key: 'E-EXISTING', id: 'bd-epic-1', type: 'epic', title: 'Already there', description: 'd' } },
  })
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  assert.equal(
    waves(calls).filter((w) => w.label === 'beads:write-epic').length,
    0,
    'an Epic that already exists must not be written a second time — that is the duplicate-Epic defect',
  )
  assert.equal(result.hierarchy.epic.id, 'bd-epic-1')
  assert.equal(result.emission.adopted, 1)
  assert.equal(result.emissionOk, true, 'adopted counts as durable — nothing is missing from the tracker')
  const storyWave = waves(calls).find((w) => w.label === 'beads:write-story')
  for (const b of storyWave.payload.beads) assert.equal(b.parentId, 'bd-epic-1')
})

// ── Partial failure is REPORTED, not smoothed over ───────────────────────────

test('a Story that fails to write takes its Tasks out of the run — they are skipped, never orphaned', async () => {
  const repos = ['/repo-a', '/repo-b']
  const { result, calls } = await run({ repos, writerOpts: { failKeys: ['S2'] } })

  assert.equal(result.ok, true, 'the Stories that DID land are dispatchable, so the run is not a failure')
  assert.equal(result.degraded, true)
  assert.equal(result.emission.verdict, 'partial')
  assert.equal(result.emissionOk, false, 'a partial write must never report emissionOk true')

  assert.deepEqual(result.emission.failed.map((f) => f.key), ['S2'])
  const skippedKeys = result.emission.skipped.map((s) => s.key).sort()
  assert.deepEqual(skippedKeys, ['S2-T1', 'S2-T2'], 'the failed Story\'s tasks are skipped, with the reason recorded')
  for (const s of result.emission.skipped) assert.match(s.reason, /parent Story S2/)

  const taskWave = waves(calls).find((w) => w.label === 'beads:write-task')
  for (const b of taskWave.payload.beads) {
    assert.ok(b.parentId, `Task ${b.key} was written with no parent id`)
    assert.ok(!b.key.startsWith('S2-'), `Task ${b.key} was written under a Story that does not exist`)
  }
  assert.match(result.headline, /EMISSION PARTIAL/, 'a caller must see the hole without opening anything')
  assert.match(result.headline, /S2/)
})

test('beadsEmitted counts what LANDED, not what was decomposed', async () => {
  const repos = ['/repo-a', '/repo-b']
  const { result } = await run({ repos, writerOpts: { failKeys: ['S2'] } })
  const total = 1 + result.hierarchy.stories.length + result.hierarchy.tasks.length
  assert.equal(result.beadsEmitted, result.emission.created)
  assert.ok(result.beadsEmitted < total, 'a run that dropped a Story and two Tasks may not report the full count')
  assert.equal(result.beadsEmitted, total - 3)
})

test('an unconfirmed dependency edge degrades the run rather than passing silently', async () => {
  const { result } = await run({ writerOpts: { failLinks: true } })
  assert.equal(result.emission.verdict, 'partial')
  assert.equal(result.emissionOk, false)
  assert.ok(result.emission.links.failed.length > 0)
  assert.equal(result.emission.links.linked, 0)
})

// ── Nothing durable is a FAILED run, and the work still comes back ────────────

test('an Epic that cannot be written stops the write and fails the run', async () => {
  const { result, calls } = await run({ repos: ['/repo-a', '/repo-b'], writerOpts: { failKeys: ['E1'] } })

  assert.equal(result.ok, false, 'a run that persisted nothing has not produced its product')
  assert.equal(result.stage, 'emit-beads')
  assert.equal(result.emissionOk, false)
  assert.equal(result.beadsEmitted, 0)
  assert.equal(result.emission.verdict, 'none')

  const labels = waves(calls).map((w) => w.label)
  assert.ok(!labels.includes('beads:write-story'), 'no Story may be written under an Epic that does not exist')
  assert.ok(!labels.includes('beads:write-task'), 'and no Task under a Story that was never attempted')

  // The work is not lost — that is what makes this recoverable rather than a re-run.
  assert.ok(result.hierarchy && result.hierarchy.epic, 'the hierarchy must still come back')
  assert.equal(result.hierarchy.stories.length, 2)
  assert.ok(result.hierarchy.tasks.length > 0)
  assert.ok(Array.isArray(result.beadSet))
  assert.match(result.headline, /NOTHING was written/)
})

test('a writer that answers with nothing is treated as a failed write, never as success', async () => {
  // Silence is the failure mode a prompt-driven emission could not distinguish from a
  // completed one. Here it is closed by construction: no id, no bead.
  const { result } = await runWorkflowScript(prdToSpec, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: '/repo-a' },
    workflowImpl: makeWorkflowImpl({ repos: ['/repo-a'] }),
    agentImpl: () => null,
  })
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'emit-beads')
  assert.equal(result.emissionOk, false)
  assert.equal(result.beadsEmitted, 0)
})

test('a writer that claims ok with no id is not believed', async () => {
  const { result } = await run({ writerOpts: { idFor: () => '   ' } })
  assert.equal(result.ok, false, 'an id that is only whitespace is not an id')
  assert.equal(result.emission.verdict, 'none')
})

// ── The target of the write ──────────────────────────────────────────────────

test('the write runs from the main repo path, and a path it cannot trust is refused', async () => {
  const { result, calls } = await run()
  const wave = waves(calls)[0]
  assert.equal(wave.payload.repoPath, '/repo-a', 'bd runs from the repository the run was launched in')
  assert.equal(result.emission.target, '/repo-a')

  const hostile = await runWorkflowScript(prdToSpec, {
    args: {
      prd: { id: 'PRD-1', title: 'PRD One', body: 'b' },
      repoPath: '/repo-a; rm -rf /',
      repos: ['/repo-a'],
    },
    workflowImpl: makeWorkflowImpl({ repos: ['/repo-a'] }),
    agentImpl: beadWriter(),
  })
  assert.equal(hostile.result.ok, false)
  assert.equal(hostile.result.stage, 'emit-beads')
  assert.equal(
    hostile.calls.filter(isWriterCall).length,
    0,
    'a path that fails the allowlist must never reach the writer, not even to be reported on',
  )
})

// ── The instruction it replaced must be gone ─────────────────────────────────

test('the composite no longer tells its caller to write the hierarchy by hand', async () => {
  const src = readWorkflowSource(prdToSpec)
  assert.ok(
    !/does not write to \.beads/.test(src),
    'the source still claims the composite does not write beads — it does now, and a caller reading that would write them twice',
  )
  const { result } = await run()
  assert.ok(
    !/Emit via bd/i.test(result.headline),
    `the headline still instructs the caller to emit with bd: ${result.headline}`,
  )
})
