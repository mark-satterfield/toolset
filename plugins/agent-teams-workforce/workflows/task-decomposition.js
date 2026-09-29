export const meta = {
  name: 'task-decomposition',
  description:
    'Leaf mini — decomposes ONE Spec into TASKS ONLY, parented to the Story that Spec pairs with, in the Story\'s single repo. A Task is build work: the Spec\'s acceptance criteria are the tests inside the build Tasks, written by their Red step, so no Task only writes tests, and a requirement whose material conforms or that does not apply to the repository gets no Task; a Story with nothing to build gets no Tasks and goes straight to deploy and verify. One maker session decomposes, names the dependency edges and sizes every task, saves the result as tasks-<slug>.json, and writes each Task bead itself: depscore.py plan-tasks reads that file, runs no bd command, and lists the Tasks in build order with their elab_keys (it makes repeated task keys unique as K, K-2, K-3, applying an edge on K to each, drops edges that do not join two known tasks, and refuses a cyclic graph); then the maker runs one depscore.py write-task command per Task, one at a time in that order, each writing ONE Task bead under the Epic\'s Story for the slug, found in beads, with its metadata, size fingerprint and blocks edges to the Tasks written before it. With replay: true the maker does not run, and one runner session runs the same commands from the saved tasks-<slug>.json. Whether the beads landed is read from beads by depscore.py elaboration-finish, not judged here.',
  phases: [
    { title: 'Decompose', detail: 'one maker session: Spec -> tasks + dependency edges + job sizes, each Task bead written by one depscore.py write-task command as it is saved' },
  ],
}
const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  return named.length ? dispatchFailures.filter((f) => named.includes(f.phase)) : dispatchFailures.slice()
}
// Runs agent(); returns its result, or null after recording the failure in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts || {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  try {
    const out = await agent(prompt, o)
    if (out) return out
    dispatchFailures.push({ ...who, outcome: 'skipped', note: `${name} returned nothing` })
    log(`${name}: returned nothing`)
  } catch (err) {
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

// args: {
//   spec: { id?, title?, description?, source?, repoPath? }, story: { id?, key?, title? },
//   specDocs?: [{ path, ref }], repoPath?, pluginRoot, standingRulings?,
//   artifacts: { dir, relDir?, epicId, script, phase, slug, inputs? },
//   beads: { script, repo, epicId, projectRoot? }  (script: the absolute depscore.py path),
//   replay?: true
// }
// returns { ok, resumed?, spec, repoPath, story: { id, elabKey }, tasks, edges, summary }; tasks, edges and
//           summary carry what the writing session relayed, and are empty or null where it relayed nothing,
//           or { ok: false, stage, reason, dispatchFailed? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what) {
  if (!art) return ''
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\n1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this.\n2. Then run exactly this command:\n   ${record}\nIf a step fails, say so in your result and still return your result.`
}
const ART = artifactsFrom(a.artifacts)
const artSlug = ART && typeof ART.slug === 'string' && ART.slug ? ART.slug : 'repo'
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const beadsFrom = (x) => (x && typeof x === 'object' && ['script', 'repo', 'epicId'].every((k) => hasText(x[k])) ? x : null)
const BEADS = beadsFrom(a.beads)

const spec = a.spec || {}
const story = a.story || {}

const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim() : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''
const specRef = spec.id || spec.title || '(unspecified spec)'
const storyRef = story.key || null
const repoPath = spec.repoPath || a.repoPath || null

const specDocs = (Array.isArray(a.specDocs) ? a.specDocs : [])
  .map((d) => (typeof d === 'string' ? { path: d, ref: null } : d && typeof d === 'object' ? d : null))
  .filter((d) => d && typeof d.path === 'string' && d.path.trim())
  .map((d) => ({ path: d.path.trim(), ref: typeof d.ref === 'string' && d.ref.trim() ? d.ref.trim() : null }))
const docsBlock = specDocs.length
  ? `\n\nSPEC DOCUMENTS — THE CONTRACT. The text above is a navigation aid only; the API contract, data model, event contracts, error handling, acceptance criteria and Definition of Done are in these files. Read the sections each task needs before you decompose:\n${specDocs
      .map((d) => `- ${d.path}${d.ref ? `  (cite as: ${d.ref})` : ''}`)
      .join('\n')}`
  : '\n\nSPEC DOCUMENTS: none were supplied, so the text above is all there is.'

const writtenPath = ART ? `${ART.dir}/story-${artSlug}.written.json` : null
const existingBlock = writtenPath
  ? `\n\nEXISTING TASKS under this Story: read the file ${writtenPath} — the result of writing this Story — and take its "existingTasks" list (none when the file or the list is absent or empty). When a task you write covers the same work as one of them, set its \`reuses\` to that task's exact elabKey; otherwise set \`reuses\` to null. Never reuse one elabKey for two tasks.`
  : '\n\nEXISTING TASKS: none. Set every task\'s `reuses` to null.'

const specBlock = `Spec ${spec.id || ''}: ${spec.title || ''}
${spec.description || ''}
${spec.source ? `Source: ${spec.source}` : ''}
Repository: ${repoPath || '(repo path not provided)'}
Parent Story: ${storyRef}${story.title ? ` — ${story.title}` : ''}${docsBlock}${existingBlock}`

// The surface names tdd-red and integration select writers and suites by.
const SURFACES = ['api-contract', 'event-chain', 'auth', 'performance', 'web-ui', 'ios', 'android', 'cross-platform-mobile', 'ml', 'data-pipeline']

const taskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'title', 'description', 'type', 'acceptanceCriteria', 'definitionOfDone', 'specPaths', 'specSections', 'requirementIds', 'surfaces', 'reuses'],
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
    decisionIds: { type: 'array', items: { type: 'string' } },
    reuses: { type: ['string', 'null'] },
    surfaces: { type: ['array', 'null'], items: { type: 'string', enum: SURFACES } },
  },
}
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

const writable = !!(ART && BEADS && hasText(repoPath))
const taskArgs = writable
  ? [`--dir ${shq(ART.dir)} --slug ${shq(artSlug)} --repo ${shq(repoPath)}`, hasText(BEADS.projectRoot) ? `--project-root ${shq(BEADS.projectRoot)}` : ''].filter(Boolean).join(' ')
  : ''
const planCommand = writable ? `python3 ${shq(BEADS.script)} plan-tasks ${taskArgs}` : ''
const writeCommand = writable ? `python3 ${shq(BEADS.script)} -C ${shq(BEADS.repo)} write-task --epic ${shq(BEADS.epicId)} --key <KEY> ${taskArgs}` : ''
const WRITE_BRIEF = `WRITE EACH TASK BEAD, one command per Task:
1. Run: ${planCommand}
   It prints one JSON object whose "tasks" list holds the tasks in build order, each with its "key".
2. For each entry of that "tasks" list, in that order, run the command below with <KEY> replaced by the entry's "key":
   ${writeCommand}
Run every command in its own Bash call in the FOREGROUND (never set run_in_background, never run two at once) with the Bash tool's \`timeout\` parameter set to 600000. Record every command you ran in \`writes\`, in order, the plan command first: its exit code as \`exitCode\` and its stdout as \`stdout\` (append stderr when the exit code is not 0). Stop after the first command whose exit code is not 0. Do not retry, do not repair, and run no other bd command.`
const WRITES_SCHEMA = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['exitCode', 'stdout'],
    properties: { exitCode: { type: 'integer' }, stdout: { type: 'string' } },
  },
}

phase('Decompose')
log(`Decomposing, sequencing, and sizing ${specRef}`)

const wsjfTaskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'jobSize', 'sizeLow', 'sizeHigh', 'sizeConfidence', 'rationale'],
  properties: {
    key: { type: 'string' },
    jobSize: { type: 'number' },
    sizeLow: { type: 'number' },
    sizeHigh: { type: 'number' },
    sizeConfidence: { type: 'integer' },
    rationale: { type: 'string' },
  },
}

const WSJF_SKILL_DIR = typeof a.pluginRoot === 'string' && a.pluginRoot.startsWith('/') ? `${a.pluginRoot.replace(/\/+$/, '')}/skills/wsjf` : null
const JOB_SIZE_BRIEF = `Size each task under "Job Size" in the \`agent-teams-workforce:wsjf\` rubric${WSJF_SKILL_DIR ? ` (${WSJF_SKILL_DIR}/SKILL.md)` : ''}: the relative amount of work to deliver the task's outcome, judged against the agent pipeline as the reference capability — not calendar time and not human effort. Weigh volume, complexity, knowledge and uncertainty together to place it. The scale is Fibonacci (1, 2, 3, 5, 8, 13, 21, and upward); compare with the rubric's reference jobs. Every size carries \`sizeLow\` and \`sizeHigh\`, the plausible range with the size inside it, and \`sizeConfidence\`, an integer percent. Value, time criticality and risk reduction are inherited from the parent Epic and computed from the dependency graph, and are NOT yours to assign. A Task above 13 should have been split: say so in your notes, and record the size you judged.`

if (!writable) {
  return { ok: false, stage: 'input', reason: 'no artifact directory, beads target or repository was supplied, so the Task beads cannot be written', spec: specRef }
}
const replayed = a.replay === true
if (replayed) log(`Decompose replayed: the Tasks are written from the saved tasks-${artSlug}.json`)
const maker = replayed ? null : await settleAgent(
  `${rulingsBlock}Three maker jobs on the Spec below, in order, one pass. Do NOT write code.

JOB 1 — DECOMPOSE (return in \`tasks\` + \`rationale\`): decompose the Spec into TASKS. Each task is a coherent piece of the Story's work within the single repository named below that one agent can test and build in one session, with testable acceptance criteria. A small Story may be one task.
- A task is BUILD work: it changes code, infrastructure or documentation. The Spec's acceptance criteria are the tests of the build tasks: each build task carries in \`acceptanceCriteria\` the criteria it satisfies, and its Red step writes those tests before it builds. A task whose only work is writing or running tests is never emitted.
- A requirement the material inventory marks \`conforms\` (it exists and matches) or \`not-applicable\` gets no task. Only \`absent\` (build it) and \`contradicts\` (remove or replace it) make work, together with any removal work named below.
- When nothing needs building, return an empty \`tasks\` list with empty \`edges\` and \`scores\`, and say why in \`rationale\`. The Story then has no Tasks and goes straight to deploy and verify. Give each a unique local "key" (T1, T2, …). You emit TASKS ONLY — every item has type "task". Do not emit an Epic, a Story, or a loose feature: the Epic and the Story already exist upstream, and every task you emit is a child of the Story named below.

Every task also carries its CONTRACT, taken from the spec documents listed below:
- \`specPaths\`: the spec documents this task builds against, cited EXACTLY as the "cite as" value given for each. At least one.
- \`specSections\`: the headings or anchors inside those documents that define this task.
- \`requirementIds\`: the PRD/TRD requirement ids the task satisfies, as the documents write them.
- \`decisionIds\`: the SAD entry ids (\`C-…\`, \`S-…\`, \`X-…\`, \`AD-…\`) the spec documents cite for the part of the design this task builds. Copy them; never invent one.
- \`definitionOfDone\`: the Definition of Done items that apply to this task, from the spec's DoD.
- \`surfaces\`: the boundaries the task touches, from the enum only (${SURFACES.join(', ')}). An empty list means it touches none of them; null means the spec does not settle it.
And once for the whole set, \`testStrategy\`: the test strategy the spec states (pyramid, coverageThreshold, envMatrix, and the section it came from as \`source\`), or null when the spec states none.

JOB 2 — SEQUENCE (return in \`edges\`): the dependencies between the tasks as a DIRECTED ACYCLIC graph. An edge "from -> to" means "from must be built before to", and both ends are keys of tasks you returned.

JOB 3 — SIZE EVERY TASK (return in \`scores\`): ${JOB_SIZE_BRIEF} Return one entry per task: its \`key\`, its \`jobSize\`, \`sizeLow\`, \`sizeHigh\`, \`sizeConfidence\`, and a one-line \`rationale\`.

${specBlock}${persistBrief(ART, `tasks-${artSlug}.json`, 'your complete structured result (tasks, testStrategy, rationale, edges, scores, notes — exactly as you return them) as ONE JSON object')}${writable ? `\n\nThen, once that file is saved and recorded, and before you return: ${WRITE_BRIEF}` : ''}`,
  {
    label: 'decompose:sequence-and-score',
    effort: 'medium',
    phase: 'Decompose',
    agentType: 'agent-teams-workforce:task-decomposer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['tasks', 'testStrategy', 'rationale', 'edges', 'scores', ...(writable ? ['writes'] : [])],
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
        scores: { type: 'array', items: wsjfTaskSchema },
        notes: { type: 'string' },
        writes: WRITES_SCHEMA,
      },
    },
  }
)
if (!replayed && (!maker || !Array.isArray(maker.tasks))) {
  const deaths = dispatchDeaths('Decompose')
  return {
    ok: false,
    stage: 'decompose',
    reason: 'the decomposition returned no task list',
    spec: specRef,
    ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
  }
}
const ran = replayed
  ? await settleAgent(`${WRITE_BRIEF}\n\nChange nothing else.`, {
      label: 'beads:write-tasks',
      phase: 'Decompose',
      model: 'haiku',
      effort: 'low',
      schema: { type: 'object', additionalProperties: false, required: ['writes'], properties: { writes: WRITES_SCHEMA } },
    })
  : maker
const writes = ran && Array.isArray(ran.writes) ? ran.writes : []
const parsed = writes.map((r) => {
  try {
    return JSON.parse(r.stdout)
  } catch (err) {
    return null
  }
})
const plan = parsed[0] && Array.isArray(parsed[0].tasks) ? parsed[0] : null
const written = parsed.slice(1).filter((w) => w && w.task)
const writtenTasks = written.length
  ? written.map((w) => w.task)
  : plan
    ? plan.tasks.map((t) => ({ key: t.key, elabKey: t.elabKey, id: null, action: null, title: t.title, dependsOn: t.dependsOn, outsideBlockers: [] }))
    : (maker && Array.isArray(maker.tasks) ? maker.tasks : []).map((t) => ({ key: t.key, elabKey: null, id: null, action: null, title: t.title, dependsOn: [], outsideBlockers: [] }))
const edges = { added: 0, removed: 0, standing: 0 }
for (const w of written) for (const k of Object.keys(edges)) edges[k] += Number(w.edges && w.edges[k]) || 0
const actions = written.map((w) => w.task.action)
const summary = written.length
  ? {
      created: actions.filter((x) => x === 'created').length,
      updated: actions.filter((x) => x === 'updated').length,
      unchanged: actions.filter((x) => x === 'unchanged' || x === 'unchanged-started').length,
    }
  : null
if (maker && !maker.tasks.length) log(`Story story:${artSlug}: no Tasks — ${String(maker.rationale || 'nothing to build').slice(0, 300)}`)
log(`Story story:${artSlug}: ${written.length} write-task result(s) relayed${summary ? ` ${JSON.stringify(summary)}` : ''}; beads is read at finish`)

return {
  ok: true,
  ...(replayed ? { resumed: true } : {}),
  spec: specRef,
  repoPath,
  story: { id: story.id || null, elabKey: `story:${artSlug}` },
  tasks: writtenTasks,
  edges,
  summary,
}
