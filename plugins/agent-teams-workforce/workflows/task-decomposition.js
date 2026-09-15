export const meta = {
  name: 'task-decomposition',
  description:
    'Leaf mini — decomposes ONE Spec into TASKS ONLY, parented to the Story that Spec pairs with. Emits nothing but tasks: an Epic is created with its PRD and a Story with its Spec, both upstream of here, so no Epic, Story, or loose feature is ever minted by decomposition. Each task is scoped to one agent\'s work within the Story\'s single repo. ONE maker session decomposes, sequences the acyclic dependency DAG with a build order, and WSJF-scores (the sole prioritization metric — no P0-P4); TWO independent checker sessions then judge it, and they judge different things because their charters differ: the wsjf-scoring-reviewer rules on the scores, the beads-format-validator rules on the Beads format and the hierarchy rule and is forbidden from judging a score. They run concurrently, and only the scoring side loops — a scoring rejection re-runs the scorer and the scoring reviewer, never the format validation. The maker never judges its own work.',
  phases: [
    { title: 'Decompose', detail: 'one maker session: Spec -> atomic tasks + acyclic DAG + WSJF scores' },
    { title: 'Validate & emit', detail: 'two independent checkers, concurrent: WSJF score review + Beads-format validation -> emit bead set' },
  ],
}

// args: {
//   spec:  { id?, title?, description?, source?, repoPath? },  // the Spec being decomposed;
//                                                              // repoPath is the ONE repository the
//                                                              // Story covers and every task inherits
//   story: { id?, title? },                                    // the Story the Spec pairs with —
//                                                              // ALREADY EXISTS; every emitted task
//                                                              // is parented to it
//   specDocs?: [{ path, ref }],                                // the Spec's DOCUMENTS: `path` is where the
//                                                              // maker reads the file, `ref` is the
//                                                              // $SKILLSPOKE_ROOT-relative path recorded on
//                                                              // each emitted Task. The contract is in these
//                                                              // files; spec.description is navigation only
//   repoPath?: string,                                         // fallback source of the same repository
//   maxScoringPasses?: number,                                 // WSJF review retries (default 2)
//   artifacts?: { dir, relDir?, epicId, script, phase, slug, inputs? },
//                                                              // Epic working directory: the maker, the
//                                                              // re-scorer and the two checkers each save
//                                                              // their own output as tasks-<slug>.json,
//                                                              // tasks-<slug>.wsjf.json,
//                                                              // tasks-<slug>.review.json (format) and
//                                                              // tasks-<slug>.wsjf-review.json (scores)
//   replay?: { maker, rescore?, review?, wsjfReview? },        // those saved outputs, read back from fresh
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
// The two verdicts replay independently, because they are now two sessions. A
// tasks-<slug>.review.json written before the split carries BOTH keys; its scoring half is
// still honored, so an Epic saved under the old shape resumes rather than re-running.
const replayReview =
  replay.review && typeof replay.review === 'object' && replay.review.beadsValidation ? replay.review : null
const replayScoring =
  (replay.wsjfReview && typeof replay.wsjfReview === 'object' && replay.wsjfReview.scoringReview
    ? replay.wsjfReview.scoringReview
    : null) || (replayReview && replayReview.scoringReview) || null
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

// ── THE SPEC DOCUMENTS ARE THE CONTRACT ────────────────────────────────────────
// The maker reads the Spec's documents itself rather than a summary of them: the API
// contract, data model, event contracts, error handling, acceptance criteria and Definition
// of Done are in those files and nowhere else. `ref` is what each Task records; a document
// whose `ref` is not a plain root-relative path is still readable but can never be cited.
const SAFE_REL_PATH = /^[A-Za-z0-9._@-][A-Za-z0-9._@/-]*$/
const specDocs = (Array.isArray(a.specDocs) ? a.specDocs : [])
  .map((d) => (typeof d === 'string' ? { path: d, ref: null } : d && typeof d === 'object' ? d : null))
  .filter((d) => d && typeof d.path === 'string' && d.path.trim())
  .map((d) => {
    const ref = typeof d.ref === 'string' && SAFE_REL_PATH.test(d.ref) && !d.ref.split('/').includes('..') ? d.ref : null
    return { path: d.path.trim(), ref }
  })
const citableRefs = specDocs.map((d) => d.ref).filter(Boolean)
const docsBlock = specDocs.length
  ? `\n\nSPEC DOCUMENTS — THE CONTRACT. The text above is a navigation aid only; the API contract, data model, event contracts, error handling, acceptance criteria and Definition of Done are in these files. Read the sections each task needs before you decompose:\n${specDocs
      .map((d) => `- ${d.path}${d.ref ? `  (cite as: ${d.ref})` : ''}`)
      .join('\n')}`
  : '\n\nSPEC DOCUMENTS: none were supplied, so the text above is all there is. Say so in your rationale.'

const specBlock = `Spec ${spec.id || ''}: ${spec.title || ''}
${spec.description || ''}
${spec.source ? `Source: ${spec.source}` : ''}
Repository: ${spec.repoPath || '(repo path not provided)'}
Parent Story: ${storyRef || '(none supplied)'}${story.title ? ` — ${story.title}` : ''}${docsBlock}`

// The surface vocabulary the build tail looks surfaces up in (tdd-red SURFACE_WRITERS,
// integration SURFACE_SUITES). A value outside it selects nothing downstream.
const SURFACES = ['api-contract', 'event-chain', 'auth', 'performance', 'web-ui', 'ios', 'android', 'cross-platform-mobile', 'ml', 'data-pipeline']

// Shared sub-schema: one decomposed task.
//
// `type` is a single-member enum on purpose. Decomposing a Story produces TASKS
// and nothing else. An Epic is created alongside its PRD and a Story alongside
// its Spec — neither is ever minted here, and there is no point in the flow at
// which decomposing a Story yields an Epic, a Story, or a loose feature. The
// enum previously admitted feature/chore/epic, which let the decomposer emit a
// second Epic underneath an existing one and corrupt the hierarchy.
//
// The contract fields are what the build lane reads off the Task bead: the spec link
// (`specPaths`, `specSections`), the requirements it satisfies, its Definition of Done,
// and the surfaces it touches. `surfaces` is null when the spec does not settle them —
// unknown, which is not the same statement as a declared empty list.
const taskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'title', 'description', 'type', 'acceptanceCriteria', 'definitionOfDone', 'specPaths', 'specSections', 'requirementIds', 'surfaces'],
  properties: {
    key: { type: 'string' },
    title: { type: 'string' },
    description: { type: 'string' },
    type: { type: 'string', enum: ['task'] },
    acceptanceCriteria: { type: 'array', items: { type: 'string' } },
    definitionOfDone: { type: 'array', items: { type: 'string' } },
    specPaths: { type: 'array', items: { type: 'string' } },
    specSections: { type: 'array', items: { type: 'string' } },
    requirementIds: { type: 'array', items: { type: 'string' } },
    surfaces: { type: ['array', 'null'], items: { type: 'string', enum: SURFACES } },
  },
}
// Pyramid shape, coverage threshold and environment matrix belong to the Spec, so they are
// read from it once for the whole task set. null when the spec states no strategy.
const testStrategySchema = {
  type: ['object', 'null'],
  additionalProperties: false,
  required: ['pyramid', 'coverageThreshold', 'envMatrix', 'source'],
  properties: {
    pyramid: { type: 'string' },
    coverageThreshold: { type: 'string' },
    envMatrix: { type: 'array', items: { type: 'string' } },
    source: { type: 'string' },
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

Every task also carries its CONTRACT, taken from the spec documents listed below — the build lane reads these fields off the Task and has nothing else to go on:
- \`specPaths\`: the spec documents this task builds against, cited EXACTLY as the "cite as" value given for each (never an absolute path, never a path you were not given). At least one.
- \`specSections\`: the headings or anchors inside those documents that define this task (e.g. "spec-x.md#POST /sessions", "spec-x.data-model.md#Sessions table").
- \`requirementIds\`: the PRD/TRD requirement ids the task satisfies, as the documents write them. Empty only if the documents carry no ids.
- \`definitionOfDone\`: the Definition of Done items that apply to this task, from the spec's DoD.
- \`surfaces\`: the boundaries the task touches, from the enum only (${SURFACES.join(', ')}). An empty list means you checked and it touches none of them (internal-only work). null means the spec does not settle it — unknown, never guessed.
And once for the whole set, \`testStrategy\`: the test strategy the spec states (pyramid, coverageThreshold, envMatrix, and the section it came from as \`source\`), or null when the spec states none. Do not invent one.

JOB 2 — SEQUENCE (return in \`edges\`, \`buildOrder\`, \`acyclic\`, \`cycle\`): map the dependencies between the tasks you just decomposed into a DIRECTED ACYCLIC graph and derive a valid topological build order. An edge "from -> to" means "from must be built before to". If the only honest reading implies a cycle, do not invent an order: set acyclic=false, list the cycle, and leave buildOrder empty.

JOB 3 — WSJF SCORE (return in \`scores\`): assign a WSJF score to EVERY task. WSJF is the SOLE prioritization metric — no P0-P4 or any other scheme. Score each component on the standard scale, then compute wsjf = (userBusinessValue + timeCriticality + riskReductionOpportunityEnablement) / jobSize, jobSize > 0. Score every key exactly once, with a one-line rationale per task.

${specBlock}${persistBrief(ART, `tasks-${artSlug}.json`, 'your complete structured result (tasks, testStrategy, rationale, edges, buildOrder, acyclic, cycle, scores, notes — exactly as you return them) as ONE JSON object')}`,
  {
    label: 'decompose:sequence-and-score',
    effort: 'medium',
    phase: 'Decompose',
    agentType: 'agent-teams-workforce:task-decomposer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['tasks', 'testStrategy', 'rationale', 'edges', 'buildOrder', 'acyclic', 'scores'],
      properties: {
        tasks: { type: 'array', items: taskSchema },
        testStrategy: testStrategySchema,
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
let scoringReview = replayScoring
let scoringAccepted = !!(scoringReview && scoringReview.accepted === true)
let beadsValidation = replayReview ? replayReview.beadsValidation : null
if (replayReview) {
  log(`Beads format REPLAYED from the saved verdict (${beadsValidation && beadsValidation.valid === true ? 'valid' : 'invalid'}) — no format session`)
}
if (replayScoring) {
  log(`WSJF review REPLAYED from the saved verdict (${scoringAccepted ? 'accepted' : 'disputed'}) — no scoring session`)
}

// ── TWO INDEPENDENT checker sessions ──────────────────────────────────────────
// They judge different things, and the split is what makes both charters true.
// beads-format-validator is explicitly forbidden from judging whether a score is
// defensible — that is wsjf-scoring-reviewer's job — so asking one session to do both
// meant the dispatch contradicted the charter of the agent it dispatched.
//
// Neither checker authored any of what it judges, so segregation of duties holds on both
// sides. They have no dependency on each other and run CONCURRENTLY, so two sessions cost
// one session's wall clock. Only the scoring side loops: a rejected score re-runs the
// scorer and then the scoring reviewer, while the structural verdict — which is about the
// tasks and the DAG, not the scores — stands from its single pass.
const CHECKER_PREAMBLE =
  'You are an INDEPENDENT checker. You did NOT produce any of the artifacts below; you only judge them. Keep every problem/feedback item under 40 words.'
const taskEvidence = `Parent Story for this task set: ${storyRef || '(NONE SUPPLIED — report this as a violation on the "parentStoryId" field of every task, since a Task without a parent Story has no Spec and cannot be worked)'}

Tasks:
${JSON.stringify(tasks, null, 2)}

Dependency edges:
${JSON.stringify(dag.edges, null, 2)}

Build order (lower index builds first):
${(dag.buildOrder || []).join(' -> ') || '(none)'}`

/** Judge the WSJF scores, and nothing else. */
async function reviewScores(pass) {
  return await agent(
    `${CHECKER_PREAMBLE}

Judge the WSJF SCORES ONLY (return under \`scoringReview\`): every task scored exactly once, jobSize > 0, the wsjf arithmetic is correct, the component values are internally consistent across tasks (similar work scored comparably), and no P0-P4 / non-WSJF priority leaked in. accepted=true only if all hold; otherwise accepted=false with specific, actionable feedback the scorer can apply without interpretation. Do NOT judge Beads format, task structure, or the dependency graph — another checker owns those.

${taskEvidence}

WSJF scores under review:
${JSON.stringify(wsjfScores && wsjfScores.scores, null, 2)}${persistBrief(ART, `tasks-${artSlug}.wsjf-review.json`, 'your complete verdict (scoringReview, exactly as you return it) as ONE JSON object')}`,
    {
      label: `review:scores:${pass}`,
      effort: 'medium',
      phase: 'Validate & emit',
      agentType: 'agent-teams-workforce:wsjf-scoring-reviewer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['scoringReview'],
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
        },
      },
    }
  )
}

/** Judge the Beads format and the hierarchy rule, and nothing else. */
async function validateFormat() {
  return await agent(
    `${CHECKER_PREAMBLE}

Judge the BEADS FORMAT ONLY (return under \`beadsValidation\`): every item's type is exactly "task" — an Epic, a Story, a feature, or a chore appearing here is a HIERARCHY VIOLATION, not a format nit (an Epic is created with its PRD and a Story with its Spec; decomposing a Story yields tasks and nothing else; report any such item as a violation on the "type" field). Each task is scoped to ONE agent's work within the single repository the Spec names. A valid id/key with the ssbd- prefix once emitted. All required Beads fields present: title, type, description, acceptance criteria, Definition of Done (\`definitionOfDone\`, non-empty), and the SPEC LINK — \`specPaths\` non-empty${citableRefs.length ? ` and every entry one of: ${citableRefs.join(', ')}` : ''}, plus \`specSections\` naming where in those documents the task is defined. \`surfaces\` is a list or null; null means unknown and is legal, a missing field is not. The dependency DAG is internally consistent: every edge references a known task, no edge references a missing key, the graph remains acyclic. valid=true only if all items pass; otherwise valid=false with per-item violations. Do NOT modify the tasks — judge only. Do NOT judge whether a WSJF score is defensible: scoring review belongs to another checker and is outside your charter.

${taskEvidence}${persistBrief(ART, `tasks-${artSlug}.review.json`, 'your complete verdict (beadsValidation, exactly as you return it) as ONE JSON object')}`,
    {
      label: 'review:format',
      effort: 'medium',
      phase: 'Validate & emit',
      agentType: 'agent-teams-workforce:beads-format-validator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['beadsValidation'],
        properties: {
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
}

// First wave: whichever verdicts this run still needs, concurrently.
const firstWave = []
if (!replayReview) firstWave.push(() => validateFormat())
if (!replayScoring) firstWave.push(() => reviewScores(1))
if (firstWave.length) {
  const results = await parallel(firstWave)
  let i = 0
  if (!replayReview) {
    const fmt = results[i++]
    beadsValidation = fmt && fmt.beadsValidation
  }
  if (!replayScoring) {
    const sc = results[i++]
    scoringReview = sc && sc.scoringReview
    scoringAccepted = !!(scoringReview && scoringReview.accepted)
    log(
      scoringAccepted
        ? `WSJF review: ACCEPTED on pass 1/${MAX_SCORING_PASSES}`
        : `WSJF review: REJECTED pass 1/${MAX_SCORING_PASSES} — ${(scoringReview && scoringReview.feedback) || 'no feedback'}`
    )
  }
}

// Re-scoring loop: the scorer and the scoring reviewer only. The structural verdict is
// about the tasks and the DAG, which a re-score does not touch, so it is not re-bought.
for (let pass = 2; !scoringAccepted && !replayScoring && pass <= MAX_SCORING_PASSES; pass++) {
  wsjfScores = await scoreWsjf((scoringReview && scoringReview.feedback) || '')
  const sc = await reviewScores(pass)
  scoringReview = sc && sc.scoringReview
  scoringAccepted = !!(scoringReview && scoringReview.accepted)
  log(
    scoringAccepted
      ? `WSJF review: ACCEPTED on pass ${pass}/${MAX_SCORING_PASSES}`
      : `WSJF review: REJECTED pass ${pass}/${MAX_SCORING_PASSES} — ${(scoringReview && scoringReview.feedback) || 'no feedback'}`
  )
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
// Format validation ran in its own checker session above; here the script only applies
// its verdict.
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
// The contract each Task carries. A spec link the maker cited is kept only when it names a
// document this run supplied, so no Task records a path that was not handed to it; a task
// that cited nothing usable is linked to every supplied document rather than to none. A
// saved maker output from before these fields existed replays the same way.
const strList = (v) => (Array.isArray(v) ? v.map((x) => String(x == null ? '' : x).trim()).filter(Boolean) : [])
const refByPath = new Map(specDocs.filter((d) => d.ref).map((d) => [d.path, d.ref]))
function taskSpecPaths(t) {
  const cited = strList(t.specPaths).map((p) => refByPath.get(p) || p).filter((p) => citableRefs.includes(p))
  return cited.length ? [...new Set(cited)] : citableRefs.slice()
}
const taskSurfaces = (t) =>
  Array.isArray(t.surfaces) ? [...new Set(strList(t.surfaces).map((s) => s.toLowerCase()).filter((s) => SURFACES.includes(s)))] : null
const testStrategy = maker.testStrategy && typeof maker.testStrategy === 'object' ? maker.testStrategy : null
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
    definitionOfDone: strList(t.definitionOfDone),
    specPaths: taskSpecPaths(t),
    specSections: strList(t.specSections),
    requirementIds: strList(t.requirementIds),
    surfaces: taskSurfaces(t), // null = unknown
    testStrategy,
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
  testStrategy,
  specDocs: citableRefs,
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
