// The work-item hierarchy, as executable rules.
//
//   Files:   PRD  -->  TRD  -->  Spec
//              |                   |
//              | created together  | created together
//              v                   v
//   Beads:   Epic --1:many--> Story --> Task        Bug (a REPORT, never worked)
//
// A Story is scoped to one repo; a Task to one agent's work within one repo.
// ONLY a Task is workable. A Bug is a REPORTING MECHANISM: it is triaged by a
// person into an Epic, a Task, or a closure, and is never routed to a composite. Epics and Stories are containers: never worked, and NEVER
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
 * work only: a Task. There is no humanInitiated gate here — a Task
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

// ── Routing: only a Task is workable; a Bug is a report ──────────────────────

test('a Bug is NEVER routed to a composite — it is a report awaiting triage', async () => {
  // A bug is a reporting mechanism. It is triaged by a person into an Epic, a Task, or a
  // closure. This router used to dispatch it straight to bug-fix as work, which is the
  // ruling's opposite; 2,534 such dispatches are in the run ledger.
  // A declared type outranks labels, so the label case carries no type: a Task labelled
  // `regression` is a triaged bug and stays workable.
  for (const bead of [{ type: 'bug' }, { type: '', labels: ['regression'] }]) {
    const r = await route(bead)
    assert.equal(r.action, 'skip')
    assert.equal(r.composite, null)
    assert.match(r.reason, /triag/i, 'the skip names triage as the destination')
    assert.match(r.reason, /reporting mechanism/i)
  }
})

test('a Bug is not elaboration work either — route-elaboration skips it naming triage', async () => {
  const r = await routeElab({ type: 'bug' }, true)
  assert.equal(r.action, 'skip')
  assert.equal(r.composite, null)
  assert.match(r.reason, /triag/i)
  assert.doesNotMatch(r.reason, /route-build\.js/, 'it must not be bounced to the build router')
})

test('a Task under a Story under an Epic is workable', async () => {
  const r = await route({ type: 'task', parentType: 'story', ancestorTypes: ['story', 'epic'] })
  assert.equal(r.action, 'work')
  assert.equal(r.composite, 'task-to-deploy')
})

test('a provisioning Task with a full hierarchy routes to task-to-deploy, which runs its Infra Intent phase', async () => {
  const r = await route({
    type: 'task',
    labels: ['cdk'],
    parentType: 'story',
    ancestorTypes: ['story', 'epic'],
  })
  assert.equal(r.action, 'work')
  assert.equal(r.composite, 'task-to-deploy')
  assert.match(r.reason, /Infra Intent/)
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

test('a parentless provisioning Task routes to task-to-deploy, not to a skip', async () => {
  const r = await route({ type: 'task', labels: ['cdk'] })
  assert.equal(r.action, 'work')
  assert.equal(r.composite, 'task-to-deploy')
})

// ── Routing: containers are never worked and never decomposed ────────────────
// A container with no children does not get broken up — its DOCUMENT needs
// elaborating (an Epic needs its PRD taken to TRD and Spec; a Story needs its
// Spec decomposed into Tasks). Elaboration is human-initiated, so an unattended
// sweep skips it rather than force-fitting work that was never authorised.

for (const container of ['epic', 'story']) {
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

test('task-decomposition tells the decomposer it may not mint a container', () => {
  const src = readWorkflowSource(taskDecomposition)
  assert.match(
    src,
    /do not emit an epic, a story, or a loose feature/i,
    'the decomposer prompt must forbid minting containers — the schema alone leaves the rule unexplained',
  )
})

// ── Promotion to a PRD is a human decision ────────────────────────────────────

test('a bead labelled prd/requirement is treated the same way', async () => {
  for (const label of ['prd', 'requirement', 'feature']) {
    const r = await routeElab({ type: 'chore', labels: [label] })
    assert.equal(r.action, 'skip', `label "${label}" must not auto-promote`)
  }
})

