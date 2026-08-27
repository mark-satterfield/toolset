// prd-to-spec run budget must scale with the fan-out it is bounding.
//
// The budget exists to stop runaway gate retries — five gates x MAX_LOOPS of full
// phase attempts produced 2h+ runs. That protection is right. What was wrong is
// that it was a flat 6 while most phases here are PER REPO.
//
// A clean run with zero retries costs 3 fixed gates (G1, G2, G2b) plus 2 per repo
// (G3 spec authoring, G4 task decomposition) = 3 + 2N. At N=1 that is 5 and fit.
// At N=2 it is 7 and did not. Every multi-repo PRD died at G4 with "run attempt
// budget exhausted" having decomposed nothing — while one Story per repo is the
// normal shape of this pipeline.
//
// These tests pin the floor so a flat constant cannot come back.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, journalPayload } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const prdToSpec = path.resolve(HERE, '..', '..', 'workflows', 'prd-to-spec.js')

/** Every gate passes first time; every mini succeeds. A perfect run — zero retries. */
function cleanRun(repos) {
  let storyN = 0
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) {
      return { verdict: 'pass', criteria: [], flags: [] }
    }
if (name.endsWith('prd-reconciliation')) {
  // Reconciliation is unconditional and runs before every gate, so every
  // prd-to-spec fixture has to answer it or the run stops at the new phase.
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
        story: { key: `S${storyN}`, type: 'story', title: `Story ${storyN}`, description: 'd', repoPath, parentEpicKey: 'E1' },
      }
    }
    if (name.endsWith('task-decomposition')) {
      const sk = (call.payload && call.payload.story && call.payload.story.key) || 'S?'
      return {
        ok: true,
        beadSet: [{ key: `${sk}-T1`, type: 'task', parentStoryId: sk, title: 't1', description: 'd', acceptanceCriteria: ['a'] }],
      }
    }
    return null
  }
}

// The budget accounting is no longer RETURNED — composites hand their phase detail to the
// run journal and give the caller a path, because returning it killed the dispatching
// session over a campaign. `journal` is where `result.budget` now lives, and asserting
// against it tests the same accounting through the channel that actually carries it.
async function runRepos(repos, extraArgs = {}) {
  const run = await runWorkflowScript(prdToSpec, {
    args: { prd: { id: 'PRD-1', title: 'PRD One', body: 'b' }, repoPath: repos[0], repos, ...extraArgs },
    workflowImpl: cleanRun(repos),
    agentImpl: () => null,
  })
  const payload = journalPayload(run.calls)
  const detail = payload && payload.detail
  return { ...run, journal: detail && (detail.partial ? detail : detail) , budget: (detail && detail.budget) || null }
}

for (const n of [1, 2, 3, 5]) {
  test(`a clean ${n}-repo run completes without exhausting the budget`, async () => {
    const repos = Array.from({ length: n }, (_, i) => `/repo-${i}`)
    const { result } = await runRepos(repos)

    assert.equal(
      result.ok,
      true,
      `a perfect run with zero retries must always fit the budget; failed at ${result.stage}: ${String(result.headline || '').slice(0, 300)}`,
    )
    assert.equal(result.hierarchy.stories.length, n, 'one Story per repo')
    assert.equal(result.hierarchy.tasks.length, n, 'every Story decomposed — none starved by the budget')
  })
}

test('the budget floor scales with repo count rather than being a flat constant', async () => {
  const one = await runRepos(['/repo-a'])
  const four = await runRepos(['/repo-a', '/repo-b', '/repo-c', '/repo-d'])

  assert.ok(
    four.budget.maxTotalAttempts > one.budget.maxTotalAttempts,
    'more repos means more legitimate per-repo phases, so the ceiling must rise with them',
  )
  // 3 fixed + 2 per repo is the zero-retry cost; the ceiling must clear it.
  for (const [n, r] of [[1, one], [4, four]]) {
    assert.ok(
      r.budget.maxTotalAttempts >= 3 + 2 * n,
      `a ${n}-repo run needs at least ${3 + 2 * n} attempts to succeed with no retries at all`,
    )
  }
})

test('the budget still leaves headroom for retries, and still bounds them', async () => {
  const { budget } = await runRepos(['/repo-a', '/repo-b'])
  const floor = 3 + 2 * 2
  assert.ok(budget.maxTotalAttempts > floor, 'a run with no retry headroom would fail on the first gate objection')
  // MAX_LOOPS is 2, so the pathological ceiling is 2x the zero-retry cost. Staying
  // under it is what keeps the runaway protection meaningful.
  assert.ok(budget.maxTotalAttempts < floor * 2, 'the ceiling must still bite before every gate has looped to exhaustion')
})

test('an explicit maxTotalAttempts still overrides the scaled default', async () => {
  const { budget } = await runRepos(['/repo-a', '/repo-b', '/repo-c'], { maxTotalAttempts: 99 })
  assert.equal(budget.maxTotalAttempts, 99, 'the caller override must win over the computed floor')
})

test('a starved budget reports the repo count so the cause is legible', async () => {
  const { result } = await runRepos(['/repo-a', '/repo-b', '/repo-c'], { maxTotalAttempts: 4 })
  assert.equal(result.ok, false, 'a budget below the zero-retry cost cannot complete')
  // The headline, not the journal: a caller that has to open a file to learn WHY its run
  // stopped has not been told. This is what the trimmed return has to keep carrying.
  const text = String(result.headline || '')
  assert.match(text, /budget exhausted/, 'the failure must name the budget')
  assert.match(text, /3 repo\(s\)/, 'and the repo count, since that is what drives the cost')
})
