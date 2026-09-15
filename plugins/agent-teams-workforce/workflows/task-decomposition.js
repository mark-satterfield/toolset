export const meta = {
  name: 'task-decomposition',
  description:
    'Leaf mini — decomposes ONE Spec into TASKS ONLY, parented to the Story that Spec pairs with. Emits nothing but tasks: an Epic is created with its PRD and a Story with its Spec, both upstream of here, so no Epic, Story, or loose feature is ever minted by decomposition. Each task is scoped to one agent\'s work within the Story\'s single repo. ONE maker session decomposes, sequences the acyclic dependency DAG with a build order, and WSJF-scores (the sole prioritization metric — no P0-P4); ONE independent checker session then reviews the scores AND validates the Beads format and the hierarchy rule in a bounded loop (a scoring rejection re-runs only the scorer). The maker never judges its own work — the independent checker does that.',
  phases: [
    { title: 'Decompose', detail: 'one maker session: Spec -> atomic tasks + acyclic DAG + WSJF scores' },
    { title: 'Validate & emit', detail: 'one independent checker session: score review + Beads-format validation -> emit bead set' },
  ],
}

// args: {
//   spec:  { id?, title?, description?, source?, repoPath? },  // the Spec being decomposed;
//                                                              // repoPath is the ONE repository the
//                                                              // Story covers and every task inherits
//   story: { id?, title? },                                    // the Story the Spec pairs with —
//                                                              // ALREADY EXISTS; every emitted task
//                                                              // is parented to it
//   repoPath?: string,                                         // fallback source of the same repository
//   maxScoringPasses?: number,                                 // WSJF review retries (default 2)
//   artifacts?: { dir, relDir?, epicId, script, phase, slug, inputs? },
//                                                              // Epic working directory: the maker, the
//                                                              // re-scorer and the checker each save their
//                                                              // own output as tasks-<slug>.json,
//                                                              // tasks-<slug>.wsjf.json, tasks-<slug>.review.json
//   replay?: { maker, rescore?, review? },                     // those saved outputs, read back from fresh
//                                                              // artifacts: a supplied one replaces its session
//                                                              // and the deterministic emission below still runs
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

// ── ARTIFACT PERSISTENCE ─────────────────────────────────────────────────────────
// When the caller names an Epic working directory, the session that AUTHORED an output
// writes it there once and runs the deterministic recorder, which hashes what is on disk.
// No session copies another session's output. Absent, nothing is written.
const SAFE_ART_PATH = /^\/[A-Za-z0-9._/-]+$/
function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  if (typeof x.dir !== 'string' || !SAFE_ART_PATH.test(x.dir) || x.dir.split('/').includes('..')) return null
  if (typeof x.script !== 'string' || !SAFE_ART_PATH.test(x.script) || x.script.split('/').includes('..')) return null
  if (typeof x.epicId !== 'string' || !/^[A-Za-z0-9._-]+$/.test(x.epicId)) return null
  if (typeof x.phase !== 'string' || !/^[A-Za-z0-9._:-]+$/.test(x.phase)) return null
  return x
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what, opts) {
  if (!art) return ''
  const o = opts || {}
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command${o.extraInputs ? `, adding ${o.extraInputs} as further --inputs values (add \`--inputs\` if the command has none)` : ''}:\n   ${record}\n   It hashes the file as it is on disk and prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  const relOk = typeof art.relDir === 'string' && /^[A-Za-z0-9._/-]+$/.test(art.relDir) && !art.relDir.startsWith('/')
  if (o.beadKey && relOk && typeof art.beadId === 'string' && /^[A-Za-z0-9._-]+$/.test(art.beadId)) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${art.beadId} --set-metadata artifact_${o.beadKey}_path=${art.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. This file is the durable copy a later run of this Epic resumes from instead of re-authoring it, and no other session will write it for you.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result. Never improvise another way to write, move or record the file.`
}
const ART = artifactsFrom(a.artifacts)
const artSlug = ART && typeof ART.slug === 'string' && /^[A-Za-z0-9._-]+$/.test(ART.slug) ? ART.slug : 'repo'
const replay = a.replay && typeof a.replay === 'object' ? a.replay : {}
const replayMaker = replay.maker && typeof replay.maker === 'object' && Array.isArray(replay.maker.tasks) && replay.maker.tasks.length ? replay.maker : null
const replayRescore = replay.rescore && typeof replay.rescore === 'object' && Array.isArray(replay.rescore.scores) ? replay.rescore : null
const replayReview =
  replay.review && typeof replay.review === 'object' && replay.review.scoringReview && replay.review.beadsValidation ? replay.review : null
const spec = a.spec || {}
const story = a.story || {}
const MAX_SCORING_PASSES = a.maxScoringPasses || 2 // scores are advisory now; an unresolved review no longer blocks emission

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''
const specRef = spec.id || spec.title || '(unspecified spec)'
if (!spec.title && !spec.description && !spec.id) {
  return { ok: false, stage: 'input', error: 'no spec supplied — refusing to run without a work item' }
}
// A Story is created alongside its Spec, upstream of here. Without it the emitted
// tasks are parentless, and route-build will (correctly) refuse to work a Task that
// has no parent Story.
//
// The Story has no bd id until the caller writes it, so before emission it is
// identified by the local key the composite assigned. Reading `story.id` alone left
// every task with parentStoryId: null — unroutable, and silently so.
const storyRef = story.id || story.key || null
if (!storyRef) {
  log('⚠ no story.id or story.key supplied — emitted tasks will be parentless and will not route as workable')
}

// The REPOSITORY every emitted task is worked in, DENORMALIZED onto the task itself.
//
// The repo is RULED one level up and stays there: prd-to-spec fans spec authoring out
// once per repository, so the Story is where the single-repo scoping decision is made.
// That part is correct and is not what this copy changes. What it fixes is that a Task
// carrying no repository is not self-describing — a consumer holding a Task has to walk
// up to its Story to learn where the work happens, and a Task whose ancestor is missing
// or has lost its repo is undispatchable even though the repository was perfectly well
// known at the moment the Task was decomposed. Denormalizing at creation costs one field
// and removes the walk and the whole class of undispatchable-but-knowable tasks.
//
// The field name is `repoPath` because that is what the consumers already read: every
// code-writing composite (bug-fix, task-to-deploy, infra-change) takes `bead.repoPath`
// and refuses to run without it. Inventing a second name here would mean the value was
// recorded and still not found.
const repoPath = spec.repoPath || a.repoPath || null
if (!repoPath) {
  log(
    '⚠ no spec.repoPath (or args.repoPath) supplied — emitted tasks will carry repoPath null, ' +
      'and whoever dispatches them will have to resolve the repository again from the Story'
  )
}

const specBlock = `Spec ${spec.id || ''}: ${spec.title || ''}
${spec.description || ''}
${spec.source ? `Source: ${spec.source}` : ''}
Repository: ${spec.repoPath || '(repo path not provided)'}
Parent Story: ${storyRef || '(none supplied)'}${story.title ? ` — ${story.title}` : ''}`

// Shared sub-schema: one decomposed task.
//
// `type` is a single-member enum on purpose. Decomposing a Story produces TASKS
// and nothing else. An Epic is created alongside its PRD and a Story alongside
// its Spec — neither is ever minted here, and there is no point in the flow at
// which decomposing a Story yields an Epic, a Story, or a loose feature. The
// enum previously admitted feature/chore/epic, which let the decomposer emit a
// second Epic underneath an existing one and corrupt the hierarchy.
const taskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'title', 'description', 'type', 'acceptanceCriteria'],
  properties: {
    key: { type: 'string' },
    title: { type: 'string' },
    description: { type: 'string' },
    type: { type: 'string', enum: ['task'] },
    acceptanceCriteria: { type: 'array', items: { type: 'string' } },
  },
}

// ── Decompose + Sequence + Score: ONE maker session ───────────────────────────
// Decomposing, DAG-mapping, and WSJF-scoring used to be three separate maker
// sessions, each paying a full session-start to re-read the same Spec and the same
// task list the previous one had just produced. All three are MAKER work — none of
// them judges anything — so one session carrying all three preserves segregation of
// duties exactly: the independent checker below still judges everything the maker
// produced, and the maker still never judges its own work.
phase('Decompose')
log(`Decomposing, sequencing, and scoring ${specRef}`)

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

if (replayMaker) log(`Decompose REPLAYED from the saved maker output (${replayMaker.tasks.length} task(s)) — no maker session`)
const maker = replayMaker || await agent(
  `${rulingsBlock}Three maker jobs on the Spec below, in order, one pass. Do NOT write code, and do NOT judge your own output — an independent checker does that after you.

JOB 1 — DECOMPOSE (return in \`tasks\` + \`rationale\`): decompose the Spec into ATOMIC TASKS. Each task must be scoped to ONE agent's work within the single repository named below, be small enough to implement and ship on its own, have a single clear outcome, and carry testable acceptance criteria. Assign each a stable, human-readable local "key" (e.g. T1, T2). You emit TASKS ONLY — every item has type "task". Do not emit an Epic, a Story, or a loose feature under any circumstance: the Epic was created with its PRD and the Story with this Spec, both already exist upstream, and every task you emit is a child of the Story named below. If the Spec looks too large for one Story, report that in your rationale (under 80 words) and still decompose only what this Spec covers.

JOB 2 — SEQUENCE (return in \`edges\`, \`buildOrder\`, \`acyclic\`, \`cycle\`): map the dependencies between the tasks you just decomposed into a DIRECTED ACYCLIC graph and derive a valid topological build order. An edge "from -> to" means "from must be built before to". If the only honest reading implies a cycle, do not invent an order: set acyclic=false, list the cycle, and leave buildOrder empty.

JOB 3 — WSJF SCORE (return in \`scores\`): assign a WSJF score to EVERY task. WSJF is the SOLE prioritization metric — no P0-P4 or any other scheme. Score each component on the standard scale, then compute wsjf = (userBusinessValue + timeCriticality + riskReductionOpportunityEnablement) / jobSize, jobSize > 0. Score every key exactly once, with a one-line rationale per task.

${specBlock}${persistBrief(ART, `tasks-${artSlug}.json`, 'your complete structured result (tasks, rationale, edges, buildOrder, acyclic, cycle, scores, notes — exactly as you return them) as ONE JSON object')}`,
  {
    label: 'decompose:sequence-and-score',
    effort: 'medium',
    phase: 'Decompose',
    agentType: 'agent-teams-workforce:task-decomposer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['tasks', 'rationale', 'edges', 'buildOrder', 'acyclic', 'scores'],
      properties: {
        tasks: { type: 'array', items: taskSchema },
        rationale: { type: 'string' },
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
        scores: { type: 'array', items: wsjfTaskSchema },
        notes: { type: 'string' },
      },
    },
  }
)
if (!maker || !Array.isArray(maker.tasks) || !maker.tasks.length) {
  return { ok: false, stage: 'decompose', reason: 'decomposition produced no tasks', spec: specRef }
}
const tasks = maker.tasks
const taskList = tasks
  .map((t) => `- ${t.key}: ${t.title} [${t.type}] — ${t.description}`)
  .join('\n')
const dag = { edges: maker.edges || [], buildOrder: maker.buildOrder || [], acyclic: maker.acyclic, cycle: maker.cycle || [] }
if (dag.acyclic === false) {
  return {
    ok: false,
    stage: 'sequence',
    reason: 'dependency graph is not acyclic',
    spec: specRef,
    tasks,
    cycle: dag.cycle,
  }
}

// Kept as a standalone dispatch for the RE-SCORING path only: when the checker
// rejects the scores, only the scoring is redone — never the decomposition or the
// DAG, which the checker validates structurally rather than argues with.
async function scoreWsjf(feedback) {
  return await agent(
    `Assign a WSJF (Weighted Shortest Job First) score to EVERY task below. WSJF is the SOLE prioritization metric — do NOT assign P0-P4 or any other priority scheme. Score each component on the standard scale, then compute wsjf = (userBusinessValue + timeCriticality + riskReductionOpportunityEnablement) / jobSize. jobSize must be > 0. Reference tasks by their "key" and score every key exactly once. Give a one-line rationale per task.

Tasks:
${taskList}

Build order (lower index builds first):
${(dag.buildOrder || []).join(' -> ') || '(none)'}${feedback ? `\n\nReviewer feedback from the previous pass — address it:\n${feedback}` : ''}${persistBrief(ART, `tasks-${artSlug}.wsjf.json`, 'your complete structured result (scores and notes, exactly as you return them) as ONE JSON object')}`,
    {
      label: 'wsjf:score',
      effort: 'low',
      phase: 'Validate & emit',
      agentType: 'agent-teams-workforce:wsjf-scorer',
      schema: wsjfSchema,
    }
  )
}

let wsjfScores = replayRescore || { scores: maker.scores || [], notes: maker.notes }
let scoringReview = null
let scoringAccepted = false
let beadsValidation = null
// A saved checker verdict stands in for the checker session. It judged the saved maker
// output; only a rejected SCORING is ever redone after it, and the structural verdict it
// carries is independent of the scores.
if (replayReview) {
  scoringReview = replayReview.scoringReview
  beadsValidation = replayReview.beadsValidation
  scoringAccepted = !!(scoringReview && scoringReview.accepted === true)
  log(`Validate REPLAYED from the saved checker verdict (scores ${scoringAccepted ? 'accepted' : 'disputed'}, Beads format ${beadsValidation && beadsValidation.valid === true ? 'valid' : 'invalid'}) — no checker session`)
}

// ── One INDEPENDENT checker session: WSJF review + Beads-format validation ─────
// These used to be two separate checker sessions. Both judge the maker's output and
// neither authored any of it, so one session carrying both checks preserves
// segregation of duties at half the session cost. On a scoring rejection only the
// SCORING is redone (the standalone scorer above); the structural result stands.
for (let pass = 1; !replayReview && pass <= MAX_SCORING_PASSES; pass++) {
  const check = await agent(
    `You are an INDEPENDENT checker. You did NOT produce any of the artifacts below; you only judge them. Perform BOTH checks in one pass and return each under its own key. Keep every problem/feedback item under 40 words.

CHECK 1 — WSJF scores (return under \`scoringReview\`): every task scored exactly once, jobSize > 0, the wsjf arithmetic is correct, the component values are internally consistent across tasks (similar work scored comparably), and no P0-P4 / non-WSJF priority leaked in. accepted=true only if all hold; otherwise accepted=false with specific, actionable feedback the scorer can apply without interpretation.

CHECK 2 — Beads format (return under \`beadsValidation\`): every item's type is exactly "task" — an Epic, a Story, a feature, or a chore appearing here is a HIERARCHY VIOLATION, not a format nit (an Epic is created with its PRD and a Story with its Spec; decomposing a Story yields tasks and nothing else; report any such item as a violation on the "type" field). Each task is scoped to ONE agent's work within the single repository the Spec names. A valid id/key with the ssbd- prefix once emitted. All required Beads fields present: title, type, description, acceptance criteria. The dependency DAG is internally consistent: every edge references a known task, no edge references a missing key, the graph remains acyclic. valid=true only if all items pass; otherwise valid=false with per-item violations. Do NOT modify the tasks — judge only.

Parent Story for this task set: ${storyRef || '(NONE SUPPLIED — report this as a violation on the "parentStoryId" field of every task, since a Task without a parent Story has no Spec and cannot be worked)'}

Tasks:
${JSON.stringify(tasks, null, 2)}

Dependency edges:
${JSON.stringify(dag.edges, null, 2)}

Build order (lower index builds first):
${(dag.buildOrder || []).join(' -> ') || '(none)'}

WSJF scores under review:
${JSON.stringify(wsjfScores && wsjfScores.scores, null, 2)}${persistBrief(ART, `tasks-${artSlug}.review.json`, 'your complete verdict (scoringReview and beadsValidation, exactly as you return them) as ONE JSON object')}`,
    {
      label: `review:scores-and-format:${pass}`,
      effort: 'medium',
      phase: 'Validate & emit',
      agentType: 'agent-teams-workforce:beads-format-validator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['scoringReview', 'beadsValidation'],
        properties: {
          scoringReview: {
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
          beadsValidation: {
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
        },
      },
    }
  )
  scoringReview = check && check.scoringReview
  beadsValidation = check && check.beadsValidation
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

// A scoring disagreement is NOT a reason to discard the decomposition.
//
// This used to return ok:false and throw away everything — the tasks, the DAG,
// the whole structural result — because a scorer and a reviewer could not agree
// on priority arithmetic within two passes. That is disproportionate: the tasks
// are the deliverable and the scores are advisory. Prioritization can be revised
// after the fact; a discarded decomposition has to be redone from the spec.
//
// So an unresolved review is recorded as a finding on the emitted set and the run
// continues. The caller sees exactly which scores are disputed and why.
const scoringDisputed = !scoringAccepted
if (scoringDisputed) {
  log(
    `WSJF review unresolved after ${MAX_SCORING_PASSES} passes — emitting tasks with the ` +
      `latest scores and recording the dispute. Tasks are the deliverable; scores are advisory.`
  )
}

// ── Validate & emit ─────────────────────────────────────────────────────────
// Format validation already ran inside the combined checker session above; here the
// script only applies its verdict.
phase('Validate & emit')

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
// Every emitted bead is a task parented to the Story this Spec pairs with.
// `type` is forced rather than copied: the schema already constrains it, and a
// task set that silently carried anything else would corrupt the hierarchy
// route-build depends on.
const beadSet = tasks
  .map((t) => ({
    key: t.key,
    title: t.title,
    description: t.description,
    type: 'task',
    parentStoryId: storyRef,
    // A copy of the Story's repository, not a second ruling on it. See the note above
    // the `repoPath` resolution: the Story rules the repo, the Task records it.
    repoPath,
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
  repoPath,
  tasks,
  dependencyDag: { edges: dag.edges, acyclic: dag.acyclic, cycle: dag.cycle || [] },
  buildOrder: dag.buildOrder,
  wsjfScores,
  scoringReview,
  scoringDisputed,
  scoringFindings: scoringDisputed
    ? ((scoringReview && scoringReview.issues) || []).map((i) => `${i.key}: ${i.problem}`)
    : [],
  beadsValidation,
  beadSet,
  story: { id: story.id || null, key: story.key || null, ref: storyRef, title: story.title || null },
  note: `Tasks only — every emitted bead is type "task"${storyRef ? ` parented to Story ${storyRef}` : ', UNPARENTED (no story.id or story.key was supplied) and therefore not workable'}${repoPath ? ` and carrying repoPath ${repoPath}` : ' and carrying repoPath null (no repository was supplied), so each one has to be re-resolved before it can be dispatched'}. Atomic, sequenced into an acyclic DAG, WSJF-scored (sole prioritization metric), and Beads-format valid.${scoringDisputed ? ' WSJF review did NOT converge — scores are the scorer\'s latest and are recorded as disputed; the task structure is unaffected.' : ' Scoring passed independent review.'} These are bead SPECIFICATIONS: prd-to-spec writes them itself as part of its run, so a caller dispatching this mini on its own is the only one that emits them with bd, from the main repo path.`,
}
