export const meta = {
  name: 'task-decomposition',
  description:
    'Leaf mini — turns a spec/contract into an implementation-ready, WSJF-scored, Beads-valid task set. Decomposes into atomic tasks, sequences them into an acyclic dependency DAG with a build order, scores every task with WSJF (no P0-P4 priorities), independently reviews the scores in a bounded maker-checker loop, and validates the whole set against the Beads format before emit. Makers (decomposer, mapper, scorer) never judge their own work — an independent reviewer and an independent format validator do that.',
  phases: [
    { title: 'Decompose', detail: 'spec -> atomic, independently-shippable tasks' },
    { title: 'Sequence (DAG)', detail: 'dependencies -> acyclic DAG + build order' },
    { title: 'WSJF score', detail: 'score every task; independent review, bounded retry' },
    { title: 'Validate & emit', detail: 'Beads-format validation -> emit bead set' },
  ],
}

// args: {
//   spec: { id?, title?, description?, source?, repoPath? },  // what to decompose
//   maxScoringPasses?: number,                                 // WSJF review retries (default 2)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const spec = a.spec || {}
const MAX_SCORING_PASSES = a.maxScoringPasses || 2
const specRef = spec.id || spec.title || '(unspecified spec)'
if (!spec.title && !spec.description && !spec.id) {
  log('⚠ no spec supplied — running in dry/demo mode')
}

const specBlock = `Spec ${spec.id || ''}: ${spec.title || ''}
${spec.description || ''}
${spec.source ? `Source: ${spec.source}` : ''}
Repository: ${spec.repoPath || '(repo path not provided)'}`

// Shared sub-schema: one decomposed task.
const taskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'title', 'description', 'type', 'acceptanceCriteria'],
  properties: {
    key: { type: 'string' },
    title: { type: 'string' },
    description: { type: 'string' },
    type: { type: 'string', enum: ['feature', 'bug', 'task', 'chore', 'epic'] },
    acceptanceCriteria: { type: 'array', items: { type: 'string' } },
  },
}

// ── Decompose ───────────────────────────────────────────────────────────────
phase('Decompose')
log(`Decomposing ${specRef}`)

const decomposition = await agent(
  `Decompose the spec below into ATOMIC, independently-shippable tasks. Each task must be small enough to implement and ship on its own, have a single clear outcome, and carry testable acceptance criteria. Do NOT sequence, score, or prioritize — that is downstream work. Do NOT write code. Assign each task a stable, human-readable local "key" (e.g. T1, T2) that downstream phases will reference.

${specBlock}`,
  {
    label: 'decompose:tasks',
    phase: 'Decompose',
    agentType: 'agent-teams-workforce:task-decomposer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['tasks', 'rationale'],
      properties: {
        tasks: { type: 'array', items: taskSchema },
        rationale: { type: 'string' },
      },
    },
  }
)
if (!decomposition || !Array.isArray(decomposition.tasks) || !decomposition.tasks.length) {
  return { ok: false, stage: 'decompose', reason: 'decomposition produced no tasks', spec: specRef }
}
const tasks = decomposition.tasks
const taskList = tasks
  .map((t) => `- ${t.key}: ${t.title} [${t.type}] — ${t.description}`)
  .join('\n')

// ── Sequence (DAG) ────────────────────────────────────────────────────────────
phase('Sequence (DAG)')

const dag = await agent(
  `Map the dependencies between the tasks below into a DIRECTED ACYCLIC graph, then derive a valid topological build order. Reference tasks by their "key". A dependency edge "from -> to" means "from must be built before to". The graph MUST be acyclic — if the only honest reading of the tasks implies a cycle, do not invent an order: set acyclic=false, list the cycle, and leave buildOrder empty. Do NOT add, remove, or rescope tasks. Do NOT write code.

Tasks:
${taskList}`,
  {
    label: 'sequence:dag',
    phase: 'Sequence (DAG)',
    agentType: 'agent-teams-workforce:task-dependency-mapper',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['edges', 'buildOrder', 'acyclic'],
      properties: {
        edges: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['from', 'to'],
            properties: {
              from: { type: 'string' },
              to: { type: 'string' },
            },
          },
        },
        buildOrder: { type: 'array', items: { type: 'string' } },
        acyclic: { type: 'boolean' },
        cycle: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)
if (!dag || dag.acyclic === false) {
  return {
    ok: false,
    stage: 'sequence',
    reason: 'dependency graph is not acyclic',
    spec: specRef,
    tasks,
    cycle: (dag && dag.cycle) || [],
  }
}

// ── WSJF score (maker-checker, bounded) ────────────────────────────────────────
phase('WSJF score')

// WSJF is the SOLE prioritization metric — no P0-P4 priorities.
const wsjfTaskSchema = {
  type: 'object',
  additionalProperties: false,
  required: [
    'key',
    'userBusinessValue',
    'timeCriticality',
    'riskReductionOpportunityEnablement',
    'jobSize',
    'wsjf',
    'rationale',
  ],
  properties: {
    key: { type: 'string' },
    userBusinessValue: { type: 'number' },
    timeCriticality: { type: 'number' },
    riskReductionOpportunityEnablement: { type: 'number' },
    jobSize: { type: 'number' },
    wsjf: { type: 'number' },
    rationale: { type: 'string' },
  },
}
const wsjfSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['scores'],
  properties: {
    scores: { type: 'array', items: wsjfTaskSchema },
    notes: { type: 'string' },
  },
}

async function scoreWsjf(feedback) {
  return await agent(
    `Assign a WSJF (Weighted Shortest Job First) score to EVERY task below. WSJF is the SOLE prioritization metric — do NOT assign P0-P4 or any other priority scheme. Score each component on the standard scale, then compute wsjf = (userBusinessValue + timeCriticality + riskReductionOpportunityEnablement) / jobSize. jobSize must be > 0. Reference tasks by their "key" and score every key exactly once. Give a one-line rationale per task.

Tasks:
${taskList}

Build order (lower index builds first):
${(dag.buildOrder || []).join(' -> ') || '(none)'}${feedback ? `\n\nReviewer feedback from the previous pass — address it:\n${feedback}` : ''}`,
    {
      label: 'wsjf:score',
      phase: 'WSJF score',
      agentType: 'agent-teams-workforce:wsjf-scorer',
      schema: wsjfSchema,
    }
  )
}

let wsjfScores = await scoreWsjf('')
let scoringReview = null
let scoringAccepted = false

for (let pass = 1; pass <= MAX_SCORING_PASSES; pass++) {
  scoringReview = await agent(
    `Independently review the WSJF scores below for the task set. You did NOT produce these scores; you only judge them. Check: every task scored exactly once, jobSize > 0, the wsjf arithmetic is correct, the component values are internally consistent across tasks (similar work scored comparably), and no P0-P4 / non-WSJF priority leaked in. Return accepted=true only if all checks hold; otherwise accepted=false with specific, actionable feedback the scorer can apply without interpretation.

Tasks:
${taskList}

WSJF scores under review:
${JSON.stringify(wsjfScores && wsjfScores.scores, null, 2)}`,
    {
      label: `wsjf:review:${pass}`,
      phase: 'WSJF score',
      agentType: 'agent-teams-workforce:wsjf-scoring-reviewer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['accepted', 'feedback', 'issues'],
        properties: {
          accepted: { type: 'boolean' },
          feedback: { type: 'string' },
          issues: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['key', 'problem'],
              properties: {
                key: { type: 'string' },
                problem: { type: 'string' },
              },
            },
          },
        },
      },
    }
  )
  if (scoringReview && scoringReview.accepted) {
    scoringAccepted = true
    log(`WSJF review: ACCEPTED on pass ${pass}/${MAX_SCORING_PASSES}`)
    break
  }
  log(
    `WSJF review: REJECTED pass ${pass}/${MAX_SCORING_PASSES} — ${
      (scoringReview && scoringReview.feedback) || 'no feedback'
    }`
  )
  if (pass < MAX_SCORING_PASSES) {
    wsjfScores = await scoreWsjf((scoringReview && scoringReview.feedback) || '')
  }
}

if (!scoringAccepted) {
  return {
    ok: false,
    stage: 'wsjf-score',
    reason: `WSJF scores not accepted within ${MAX_SCORING_PASSES} review passes`,
    spec: specRef,
    tasks,
    dependencyDag: { edges: dag.edges, acyclic: dag.acyclic },
    buildOrder: dag.buildOrder,
    wsjfScores,
    scoringReview,
  }
}

// ── Validate & emit ─────────────────────────────────────────────────────────
phase('Validate & emit')

// Independent format validation — a different agent than every maker above.
const beadsValidation = await agent(
  `Validate that the task set below conforms to the Beads format before it is emitted as a bead set. Check every task: a valid id/key with the ssbd- prefix once emitted, all required Beads fields present (title, type, description, acceptance criteria), the type is a permitted Beads type, and the dependency DAG is internally consistent (every edge references a known task, no edge references a missing key, the graph remains acyclic). Return valid=true only if all tasks pass; otherwise valid=false with per-task violations. Do NOT modify the tasks — judge only.

Tasks:
${JSON.stringify(tasks, null, 2)}

Dependency edges:
${JSON.stringify(dag.edges, null, 2)}

Build order:
${(dag.buildOrder || []).join(' -> ') || '(none)'}`,
  {
    label: 'validate:beads-format',
    phase: 'Validate & emit',
    agentType: 'agent-teams-workforce:beads-format-validator',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['valid', 'violations'],
      properties: {
        valid: { type: 'boolean' },
        violations: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['key', 'field', 'problem'],
            properties: {
              key: { type: 'string' },
              field: { type: 'string' },
              problem: { type: 'string' },
            },
          },
        },
        notes: { type: 'string' },
      },
    },
  }
)
if (!beadsValidation || beadsValidation.valid !== true) {
  return {
    ok: false,
    stage: 'validate',
    reason: 'task set failed Beads-format validation',
    spec: specRef,
    tasks,
    dependencyDag: { edges: dag.edges, acyclic: dag.acyclic },
    buildOrder: dag.buildOrder,
    wsjfScores,
    scoringReview,
    beadsValidation,
  }
}

// Emit: stitch task + its WSJF score into the bead set, in build order.
const wsjfByKey = {}
for (const s of (wsjfScores && wsjfScores.scores) || []) wsjfByKey[s.key] = s
const orderIndex = {}
;(dag.buildOrder || []).forEach((k, i) => {
  orderIndex[k] = i
})
const beadSet = tasks
  .map((t) => ({
    key: t.key,
    title: t.title,
    description: t.description,
    type: t.type,
    acceptanceCriteria: t.acceptanceCriteria,
    dependsOn: (dag.edges || []).filter((e) => e.to === t.key).map((e) => e.from),
    wsjf: wsjfByKey[t.key] ? wsjfByKey[t.key].wsjf : null,
    buildOrderIndex: t.key in orderIndex ? orderIndex[t.key] : null,
  }))
  .sort((x, y) => {
    const xi = x.buildOrderIndex == null ? Infinity : x.buildOrderIndex
    const yi = y.buildOrderIndex == null ? Infinity : y.buildOrderIndex
    return xi - yi
  })

return {
  ok: true,
  spec: specRef,
  tasks,
  dependencyDag: { edges: dag.edges, acyclic: dag.acyclic, cycle: dag.cycle || [] },
  buildOrder: dag.buildOrder,
  wsjfScores,
  scoringReview,
  beadsValidation,
  beadSet,
  note: 'Tasks are atomic, sequenced into an acyclic DAG, WSJF-scored (sole prioritization metric), independently reviewed, and Beads-format valid. Emit via bd from the main repo path.',
}
