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
// ancestor Epic. Epics and Stories are containers: never worked, and NEVER
// decomposed — nothing decomposes a bead. The FILE chain decomposes (PRD -> TRD
// -> Spec) and the beads are what that chain deposits beneath them.
//
// These tests pin that hierarchy at the three places it can be violated —
// routing (route-build + route-elaboration), decomposition (task-decomposition), and emission
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
const routeBuild = path.join(WORKFLOWS, 'route-build.js')
const routeElaboration = path.join(WORKFLOWS, 'route-elaboration.js')
const taskDecomposition = path.join(WORKFLOWS, 'task-decomposition.js')

/**
 * Runs the BUILD router deterministically (no classifier agent). Development
 * work only: a Task or a Bug. There is no humanInitiated gate here — a Task
 * under a Story under an Epic was already authorised upstream, which is what
 * lets an unattended build loop run.
 */
function route(bead) {
  return runWorkflowScript(routeBuild, {
    args: { bead, allowAmbiguityAgent: false },
  }).then((r) => r.result)
}

/**
 * Runs the ELABORATION router deterministically. Document-side work: an Epic,
 * a Story, or a feature. Defaults to an UNATTENDED sweep (humanInitiated
 * false), which is the case that must never start work on its own.
 */
function routeElab(bead, humanInitiated = false) {
  return runWorkflowScript(routeElaboration, {
    args: { bead, allowAmbiguityAgent: false, humanInitiated },
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
  assert.equal(r.composite, 'task-to-deploy')
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

test('a parentless Task IS workable — a Story is a roll-up parent for reporting, never a gate', async () => {
  // This router used to refuse a Task with no Story on the theory that no Story meant no
  // Spec and therefore no contract. The composite builds its contract from the Task's own
  // statement of work and rules the repository at run time, so the gate guarded nothing
  // and held 50 of 51 live Tasks out of the run.
  const r = await route({ type: 'task' })
  assert.equal(r.action, 'work')
  assert.equal(r.composite, 'task-to-deploy')
  assert.match(r.reason, /parent Story/i, 'the missing parent is still NAMED — it is a reporting repair, not a secret')
  assert.match(r.reason, /never a dispatch precondition/i)
})

test('a Task under a Story but with no ancestor Epic is workable too', async () => {
  const r = await route({ type: 'task', parentType: 'story', ancestorTypes: ['story'] })
  assert.equal(r.action, 'work')
  assert.match(r.reason, /Epic/i, 'the missing ancestor is named')
})

test('a parentless provisioning Task routes to infra-change, not to a skip', async () => {
  const r = await route({ type: 'task', labels: ['cdk'] })
  assert.equal(r.action, 'work')
  assert.equal(r.composite, 'infra-change')
})

// ── Routing: containers are never worked and never decomposed ────────────────
// A container with no children does not get broken up — its DOCUMENT needs
// elaborating (an Epic needs its PRD taken to TRD and Spec; a Story needs its
// Spec decomposed into Tasks). Elaboration is human-initiated, so an unattended
// sweep skips it rather than force-fitting work that was never authorised.

for (const container of ['epic', 'story']) {
  test(`an unattended sweep does not elaborate a ${container} — that is a human's call`, async () => {
    const r = await routeElab({ type: container })
    assert.equal(r.action, 'skip')
    assert.match(r.reason, /human/i)
  })

  test(`a human-initiated run works a ${container} via elaboration, not development`, async () => {
    const r = await routeElab({ type: container }, true)
    assert.equal(r.action, 'elaborate')
    assert.equal(r.composite, 'prd-to-spec')
  })

  test(`a ${container} that ALREADY has children is still workable — the document above it may have moved on`, async () => {
    const r = await routeElab({ type: container, childCount: 99 }, true)
    assert.equal(
      r.action,
      'elaborate',
      `${container} was refused because it has children — "has children" is not "in sync"`,
    )
  })

  test(`the BUILD router never dispatches a ${container} as development work`, async () => {
    const r = await route({ type: container })
    assert.equal(r.action, 'skip')
    assert.equal(r.composite, null)
    assert.match(r.reason, /route-elaboration/, 'the skip must name the router that owns it')
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

// The decompose/sequence/score maker and the review/format checker are ONE session
// each now (ssbd-qrpf0); this stub answers the merged labels, plus the standalone
// re-scoring dispatch.
const score = (key) => ({ key, userBusinessValue: 5, timeCriticality: 3, riskReductionOpportunityEnablement: 2, jobSize: 2, wsjf: 5, rationale: 'r' })
function decompStub({ tasks, buildOrder, review, validation }) {
  return (call) => {
    if (call.label === 'decompose:sequence-and-score') {
      return { tasks, rationale: 'r', edges: [], buildOrder, acyclic: true, scores: buildOrder.map(score) }
    }
    if (call.label === 'wsjf:score') return { scores: buildOrder.map(score) }
    if (String(call.label).startsWith('review:scores-and-format')) {
      return {
        scoringReview: review || { accepted: true, feedback: '', issues: [] },
        beadsValidation: validation || { valid: true, violations: [] },
      }
    }
    return null
  }
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
    agentImpl: decompStub({ tasks: decomposed, buildOrder: ['T1'] }),
  })

  assert.equal(result.ok, true, `decomposition failed: ${result.reason || ''}`)
  assert.ok(result.beadSet.length > 0)
  for (const bead of result.beadSet) {
    assert.equal(bead.type, 'task', 'every emitted bead must be a task')
    assert.equal(
      bead.parentStoryId,
      'ssbd-story-1',
      'every emitted task must be parented to the Story — the roll-up parent it reports under',
    )
  }
})

test('a Story identified only by `key` still parents its tasks', async () => {
  // Before bd writes them, a Story has no id — only the local key the composite
  // assigned. Reading `story.id` alone yields parentStoryId: null on every task,
  // and every one of them would then report under no Story at all.
  const { result } = await runWorkflowScript(taskDecomposition, {
    args: {
      spec: { id: 'SPEC-1', title: 'spec', repoPath: '/repo' },
      story: { key: 'S2', title: 'keyed but not yet written to bd' },
    },
    agentImpl: decompStub({ tasks: [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }], buildOrder: ['T1'] }),
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

// ── A Task RECORDS the repository it belongs to ───────────────────────────────
//
// The repo is RULED on the Story — one Spec+Story per repository — and that stays
// true. But a Task that only inherits it is not self-describing: dispatching one
// meant walking up to its Story first, and a Task whose ancestor carried no repo was
// undispatchable even though the repository was known when it was decomposed. The
// field is `repoPath` because that is what every code-writing composite reads off
// the bead.

test('every emitted task carries the repository, copied from the Spec it decomposed', async () => {
  const { result } = await runWorkflowScript(taskDecomposition, {
    args: {
      spec: { id: 'SPEC-1', title: 'spec', repoPath: '/repos/service-a' },
      story: { key: 'S1', title: 'the story' },
    },
    agentImpl: decompStub({
      tasks: [
        { key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] },
        { key: 'T2', title: 'a2', description: 'b2', type: 'task', acceptanceCriteria: ['c2'] },
      ],
      buildOrder: ['T1', 'T2'],
    }),
  })

  assert.equal(result.ok, true, `decomposition failed: ${result.reason || ''}`)
  assert.equal(result.repoPath, '/repos/service-a', 'the run must report the repository it decomposed against')
  assert.equal(result.beadSet.length, 2)
  for (const bead of result.beadSet) {
    assert.equal(
      bead.repoPath,
      '/repos/service-a',
      'a Task must record its own repository — a consumer should not have to walk up to the Story to find it',
    )
  }
})

test('the repository may also arrive as args.repoPath', async () => {
  const { result } = await runWorkflowScript(taskDecomposition, {
    args: {
      spec: { id: 'SPEC-1', title: 'spec' },
      story: { key: 'S1' },
      repoPath: '/repos/service-b',
    },
    agentImpl: decompStub({ tasks: [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }], buildOrder: ['T1'] }),
  })

  assert.equal(result.ok, true)
  assert.equal(result.beadSet[0].repoPath, '/repos/service-b')
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
    // The reviewer never accepts.
    agentImpl: decompStub({
      tasks: [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }],
      buildOrder: ['T1'],
      review: { accepted: false, feedback: 'jobSize looks optimistic', issues: [{ key: 'T1', problem: 'jobSize disputed' }] },
    }),
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
    agentImpl: decompStub({ tasks: [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }], buildOrder: ['T1'] }),
  })
  assert.equal(result.scoringDisputed, false)
  assert.deepEqual(result.scoringFindings, [])
})

// ── Promotion to a PRD is a human decision ────────────────────────────────────

test('a feature bead is a REQUEST — it is skipped, not auto-promoted', async () => {
  // Promoting a feature to a PRD and an Epic decides that it is worth building,
  // and now. A loop that promotes every feature bead it finds has decided the
  // roadmap, which is not a call this pipeline has the standing to make.
  const r = await routeElab({ type: 'feature' })
  assert.equal(r.action, 'skip')
  assert.equal(r.composite, null)
  assert.match(r.reason, /human decision/i)
  assert.match(r.reason, /start-prd/, 'the skip must name the command that promotes it')
})

test('a bead labelled prd/requirement is treated the same way', async () => {
  for (const label of ['prd', 'requirement', 'feature']) {
    const r = await routeElab({ type: 'chore', labels: [label] })
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

test('the Red phase forbids asserting against committed build artifacts', () => {
  // Observed live on ssbd-sa5j: half a suite synthesized the CDK template in
  // process while the other half read a checked-in cdk.out template three days
  // stale. The two halves asserted against different artifacts, so the suite
  // reported coverage it did not have — and the stale half would pass forever.
  const red = readWorkflowSource(path.join(WORKFLOWS, 'tdd-red.js'))
  assert.match(red, /ASSERT AGAINST WHAT THE CODE PRODUCES, NOT A COMMITTED ARTIFACT/,
    'the writer prompt must forbid testing against checked-in build output')

  for (const composite of ['bug-fix.js', 'task-to-deploy.js', 'infra-change.js']) {
    const src = readWorkflowSource(path.join(WORKFLOWS, composite))
    assert.match(src, /freshly generated artifacts, not checked-in build output/,
      `${composite}: the Red gate must check this, not only the writer prompt — a prompt is advice, a gate criterion is checked`)
  }
})
