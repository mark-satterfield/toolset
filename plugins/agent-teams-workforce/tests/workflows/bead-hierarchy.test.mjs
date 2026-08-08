// The work-item hierarchy, as executable rules.
//
//   Files:   PRD  -->  TRD  -->  Spec
//              |                   |
//              | created together  | created together
//              v                   v
//   Beads:   Epic --1:many--> Story --> Task        Bug (stands alone)
//
// A Story is scoped to one repo; a Task to one agent's work within one repo.
// ONLY a Task or a Bug is workable, and a Task only with a parent Story and an
// ancestor Epic. Epics and Stories are containers: never worked, only decomposed.
//
// These tests pin that hierarchy at the three places it can be violated —
// routing (route-bead), decomposition (task-decomposition), and emission
// (prd-to-spec) — because every violation observed so far was silent: a
// container dispatched as work, a second Epic minted underneath one that
// already existed, a parentless Task handed to an implementer with no Spec.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, readWorkflowSource } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WORKFLOWS = path.resolve(HERE, '..', '..', 'workflows')
const routeBead = path.join(WORKFLOWS, 'route-bead.js')
const taskDecomposition = path.join(WORKFLOWS, 'task-decomposition.js')

/** Runs route-bead deterministically (no classifier agent). */
function route(bead) {
  return runWorkflowScript(routeBead, {
    args: { bead, allowAmbiguityAgent: false },
  }).then((r) => r.result)
}

// ── Routing: only a Task or a Bug is workable ─────────────────────────────────

test('a Bug is workable standing alone — it needs no parent', async () => {
  const r = await route({ type: 'bug' })
  assert.equal(r.action, 'work')
  assert.equal(r.composite, 'bug-fix')
})

test('a Task under a Story under an Epic is workable', async () => {
  const r = await route({ type: 'task', parentType: 'story', ancestorTypes: ['story', 'epic'] })
  assert.equal(r.action, 'work')
  assert.equal(r.composite, 'spec-to-deploy')
})

test('a provisioning Task with a full hierarchy routes to infra-change', async () => {
  const r = await route({
    type: 'task',
    labels: ['cdk'],
    parentType: 'story',
    ancestorTypes: ['story', 'epic'],
  })
  assert.equal(r.action, 'work')
  assert.equal(r.composite, 'infra-change')
})

test('a parentless Task is NOT workable — no Story means no Spec to build against', async () => {
  const r = await route({ type: 'task' })
  assert.equal(r.action, 'skip')
  assert.equal(r.composite, null)
  assert.match(r.reason, /parent Story/i)
})

test('a Task under a Story but with no ancestor Epic is NOT workable', async () => {
  const r = await route({ type: 'task', parentType: 'story', ancestorTypes: ['story'] })
  assert.equal(r.action, 'skip')
  assert.match(r.reason, /Epic/i)
})

// ── Routing: containers are decomposed, never worked ──────────────────────────

for (const container of ['epic', 'story']) {
  test(`an empty ${container} is decomposed, not worked`, async () => {
    const r = await route({ type: container, childCount: 0 })
    assert.equal(r.action, 'decompose')
    assert.equal(r.composite, 'prd-to-spec')
  })

  test(`a populated ${container} is skipped — the work lives in its descendants`, async () => {
    const r = await route({ type: container, childCount: 4 })
    assert.equal(r.action, 'skip')
    assert.equal(r.composite, null)
  })

  test(`a ${container} is never dispatched as work, whatever its child count`, async () => {
    for (const childCount of [0, 1, 99, undefined]) {
      const r = await route({ type: container, childCount })
      assert.notEqual(
        r.action,
        'work',
        `${container} with childCount=${childCount} was dispatched as work — containers have no single repo, no single agent's scope, and no contract`,
      )
    }
  })
}

// ── Routing: out-of-pipeline kinds are reported, never force-fit ──────────────

for (const kind of ['chore', 'docs', 'research', 'spike']) {
  test(`a ${kind} is skipped with a reason, not force-fit into a composite`, async () => {
    const r = await route({ type: kind })
    assert.equal(r.action, 'skip')
    assert.equal(r.composite, null)
    assert.ok(r.reason.length > 0)
  })
}

// ── Decomposition: tasks only ─────────────────────────────────────────────────

test('task-decomposition can only ever emit type "task"', () => {
  const src = readWorkflowSource(taskDecomposition)
  const enums = [...src.matchAll(/type:\s*\{\s*type:\s*'string',\s*enum:\s*\[([^\]]*)\]/g)].map(
    (m) => m[1].replace(/['\s]/g, ''),
  )
  assert.ok(enums.length > 0, 'the task schema must constrain `type` with an enum')
  for (const e of enums) {
    assert.equal(
      e,
      'task',
      `decomposing a Story yields tasks and nothing else, but the schema admits [${e}]. An Epic is created with its PRD and a Story with its Spec — neither is ever minted by decomposition.`,
    )
  }
})

test('task-decomposition emits tasks parented to the Story it was given', async () => {
  const decomposed = [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }]
  const { result } = await runWorkflowScript(taskDecomposition, {
    args: {
      spec: { id: 'SPEC-1', title: 'spec', repoPath: '/repo' },
      story: { id: 'ssbd-story-1', title: 'the story' },
    },
    agentImpl: (call) => {
      if (call.label === 'decompose:tasks') return { tasks: decomposed, rationale: 'r' }
      if (call.label === 'sequence:dag') return { edges: [], buildOrder: ['T1'], acyclic: true }
      if (call.label === 'wsjf:score') {
        return {
          scores: [
            {
              key: 'T1',
              userBusinessValue: 5,
              timeCriticality: 3,
              riskReductionOpportunityEnablement: 2,
              jobSize: 2,
              wsjf: 5,
              rationale: 'r',
            },
          ],
        }
      }
      if (String(call.label).startsWith('wsjf:review')) return { accepted: true, feedback: '', issues: [] }
      if (call.label === 'validate:beads-format') return { valid: true, violations: [] }
      return null
    },
  })

  assert.equal(result.ok, true, `decomposition failed: ${result.reason || ''}`)
  assert.ok(result.beadSet.length > 0)
  for (const bead of result.beadSet) {
    assert.equal(bead.type, 'task', 'every emitted bead must be a task')
    assert.equal(
      bead.parentStoryId,
      'ssbd-story-1',
      'every emitted task must be parented to the Story, or route-bead will refuse to work it',
    )
  }
})

test('a Story identified only by `key` still parents its tasks', async () => {
  // Before bd writes them, a Story has no id — only the local key the composite
  // assigned. Reading `story.id` alone yields parentStoryId: null on every task,
  // and route-bead then refuses to work any of them.
  const { result } = await runWorkflowScript(taskDecomposition, {
    args: {
      spec: { id: 'SPEC-1', title: 'spec', repoPath: '/repo' },
      story: { key: 'S2', title: 'keyed but not yet written to bd' },
    },
    agentImpl: (call) => {
      if (call.label === 'decompose:tasks') {
        return { tasks: [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }], rationale: 'r' }
      }
      if (call.label === 'sequence:dag') return { edges: [], buildOrder: ['T1'], acyclic: true }
      if (call.label === 'wsjf:score') {
        return { scores: [{ key: 'T1', userBusinessValue: 5, timeCriticality: 3, riskReductionOpportunityEnablement: 2, jobSize: 2, wsjf: 5, rationale: 'r' }] }
      }
      if (String(call.label).startsWith('wsjf:review')) return { accepted: true, feedback: '', issues: [] }
      if (call.label === 'validate:beads-format') return { valid: true, violations: [] }
      return null
    },
  })

  assert.equal(result.ok, true)
  for (const bead of result.beadSet) {
    assert.equal(
      bead.parentStoryId,
      'S2',
      'a Story that exists only as a local key must still parent its tasks — otherwise every task is unroutable',
    )
  }
})

test('task-decomposition tells the decomposer it may not mint a container', () => {
  const src = readWorkflowSource(taskDecomposition)
  assert.match(
    src,
    /do not emit an epic, a story, or a loose feature/i,
    'the decomposer prompt must forbid minting containers — the schema alone leaves the rule unexplained',
  )
})

// ── A scoring dispute must not destroy the decomposition ──────────────────────

test('an unresolved WSJF review emits the tasks anyway, with the dispute recorded', async () => {
  // Priority arithmetic is advisory; the task structure is the deliverable. This
  // used to return ok:false and discard the tasks, the DAG, and the whole run.
  const { result } = await runWorkflowScript(taskDecomposition, {
    args: {
      spec: { id: 'SPEC-1', title: 'spec', repoPath: '/repo' },
      story: { key: 'S1', title: 'the story' },
      maxScoringPasses: 2,
    },
    agentImpl: (call) => {
      if (call.label === 'decompose:tasks') {
        return { tasks: [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }], rationale: 'r' }
      }
      if (call.label === 'sequence:dag') return { edges: [], buildOrder: ['T1'], acyclic: true }
      if (call.label === 'wsjf:score') {
        return { scores: [{ key: 'T1', userBusinessValue: 5, timeCriticality: 3, riskReductionOpportunityEnablement: 2, jobSize: 2, wsjf: 5, rationale: 'r' }] }
      }
      // The reviewer never accepts.
      if (String(call.label).startsWith('wsjf:review')) {
        return { accepted: false, feedback: 'jobSize looks optimistic', issues: [{ key: 'T1', problem: 'jobSize disputed' }] }
      }
      if (call.label === 'validate:beads-format') return { valid: true, violations: [] }
      return null
    },
  })

  assert.equal(result.ok, true, 'a scoring disagreement must not discard correct structural work')
  assert.equal(result.beadSet.length, 1, 'the tasks are still emitted')
  assert.equal(result.beadSet[0].parentStoryId, 'S1')
  assert.equal(result.scoringDisputed, true, 'the dispute must be visible to the caller')
  assert.deepEqual(result.scoringFindings, ['T1: jobSize disputed'])
})

test('an accepted review reports no dispute', async () => {
  const { result } = await runWorkflowScript(taskDecomposition, {
    args: { spec: { id: 'SPEC-1', title: 'spec', repoPath: '/repo' }, story: { key: 'S1' } },
    agentImpl: (call) => {
      if (call.label === 'decompose:tasks') {
        return { tasks: [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }], rationale: 'r' }
      }
      if (call.label === 'sequence:dag') return { edges: [], buildOrder: ['T1'], acyclic: true }
      if (call.label === 'wsjf:score') {
        return { scores: [{ key: 'T1', userBusinessValue: 5, timeCriticality: 3, riskReductionOpportunityEnablement: 2, jobSize: 2, wsjf: 5, rationale: 'r' }] }
      }
      if (String(call.label).startsWith('wsjf:review')) return { accepted: true, feedback: '', issues: [] }
      if (call.label === 'validate:beads-format') return { valid: true, violations: [] }
      return null
    },
  })
  assert.equal(result.scoringDisputed, false)
  assert.deepEqual(result.scoringFindings, [])
})

// ── Promotion to a PRD is a human decision ────────────────────────────────────

test('a feature bead is a REQUEST — it is skipped, not auto-promoted', async () => {
  // Promoting a feature to a PRD and an Epic decides that it is worth building,
  // and now. A loop that promotes every feature bead it finds has decided the
  // roadmap, which is not a call this pipeline has the standing to make.
  const r = await route({ type: 'feature' })
  assert.equal(r.action, 'skip')
  assert.equal(r.composite, null)
  assert.match(r.reason, /human decision/i)
  assert.match(r.reason, /start-prd/, 'the skip must name the command that promotes it')
})

test('a bead labelled prd/requirement is treated the same way', async () => {
  for (const label of ['prd', 'requirement', 'feature']) {
    const r = await route({ type: 'chore', labels: [label] })
    assert.equal(r.action, 'skip', `label "${label}" must not auto-promote`)
  }
})

test('the Red phase tells writers to extend the existing suite, not fork it', () => {
  // Tests written by tdd-red are permanent — deploy.js commits them and every
  // later run inherits them. Without an instruction to look first, runs accrete
  // parallel files covering the same behavior, which makes the suite slow and
  // its failures ambiguous about which expectation is authoritative.
  const src = readWorkflowSource(path.join(WORKFLOWS, 'tdd-red.js'))
  assert.match(src, /FIND THE EXISTING SUITE BEFORE YOU WRITE/,
    'the writer prompt must require locating the existing coverage first')
  assert.match(src, /these tests are permanent/i,
    'the writer must know its output is committed and inherited, not scratch')
})
