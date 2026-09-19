export const meta = {
  name: 'wsjf-scoring',
  description:
    "Scores every open Epic and Task with WSJF, and never sets a dependency: it reads the edges from beads. Edges decide ELIGIBILITY, WSJF decides PRIORITY among what is eligible. A model judges only where the source content changed or a value is missing. Each Epic's value, time criticality and — for an Epic without Tasks — size are judged from its full PRD, one Epic per session, against the rubric's rungs and the reference jobs, with no other Epic's PRD or values as an input; each Epic's Tasks are sized together, in a session per Epic. Every size is on one Fibonacci scale with a plausible range and a size confidence, kept apart from the value confidence. A judgment off the rubric's scale is rejected and reported, and the rest are written. Then the arithmetic — Epic RR-OE, the Architectural Enabler measure, from reachability over the Epic architecture-dependency edges, Epic size as the plain sum of its Tasks' sizes, Task RR-OE, the value a Task inherits, every WSJF — runs over every open item, and only values that changed are written. `all` includes items that already have a value; `rejudge` judges the existing values of the items included again; `only` restricts the judging to named items; `dryRun` writes nothing.",
  whenToUse: "Scoring after Epics or Tasks are added or changed, or after dependency assessment applies edges; with all and rejudge, re-judging every Epic and Task.",
  phases: [
    { title: "Plan", detail: "fingerprints decide what is judged" },
    { title: "Judge", detail: "a session per Epic, and a session per Epic's Tasks" },
    { title: "Apply", detail: "judged values, then the arithmetic over every open item" },
  ],
}
// ── EVERY DISPATCH IS SETTLED ────────────────────────────────────────────────────
//
// `agent()` fails in two different ways and the scripts used to conflate them. It
// RETURNS NULL when a subagent is skipped or dies on a terminal API error after the
// runtime's own retries. It THROWS when a subagent finishes without calling
// StructuredOutput — and an uncaught throw leaves this script, leaves whatever
// composite called it, and kills the run: two recorded crashes cost 1.13M and 1.88M
// tokens and discarded every artifact the run had already paid for.
//
// So every dispatch in this file goes through settleAgent(). A throw never escapes it,
// and it records what the engine's error text loses — that text reads
// `agent({schema}): subagent completed without calling StructuredOutput`, which names
// neither the agent, nor the phase, nor the schema, and points at no transcript. The
// caller receives null, which every call site already handles, and `dispatchFailures`
// carries the identity of what died, for the `dispatchFailed` report this script owes
// its caller: a phase whose producing agents died is NOT adjudicated.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.schemaName
  const who = {
    agentType: o.agentType || null,
    label: o.label || null,
    phase: o.phase || null,
    schema: settleSchemaName(o),
  }
  const name = who.label || who.agentType || 'agent'
  const whose = `${name}${who.agentType && who.agentType !== name ? ` (${who.agentType})` : ''}${who.phase ? ` in ${who.phase}` : ''}`
  let out = null
  try {
    out = await agent(prompt, call)
  } catch (err) {
    const message = String((err && err.message) || err)
    dispatchFailures.push({
      ...who,
      outcome: 'threw',
      message: message.slice(0, 300),
      transcript: settleTranscript(err, name),
      note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''}: ${message.slice(0, 160)}`,
    })
    log(`${name}: session ended without a structured result — ${message.slice(0, 160)}`)
    // A caller that owns its own failure reporting asks for the throw back, so the real
    // reason reaches its catch instead of being flattened to "returned no result".
    if (o.rethrow) throw err
    return null
  }
  if (out) return out
  dispatchFailures.push({
    ...who,
    outcome: 'skipped',
    message: null,
    transcript: settleTranscript(null, name),
    note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
  })
  log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
  return null
}

// ── Deterministic steps ──────────────────────────────────────────────────────────
//
// Every tracker read and write is a `depscore.py` command. A workflow has no shell, so a
// runner session executes exactly one command and hands back what it printed; the command
// writes its full result to a file in the run directory and prints only a summary, so no
// data a later step depends on passes through a model.
const RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'output'],
  properties: {
    exitCode: { type: 'integer' },
    output: { type: 'object' },
  },
}
const failures = []
let currentPhase = null
async function runStep(label, command) {
  const out = await settleAgent(
    `Run exactly this one shell command, once, from any directory, and change nothing else:

${command}

It prints one JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not run any other command.`,
    { label, phase: currentPhase, effort: 'low', schema: RUN_SCHEMA }
  )
  if (!out) {
    failures.push({ step: label, reason: 'the runner returned no result' })
    return null
  }
  if (out.exitCode !== 0 || (out.output && out.output.error)) {
    failures.push({ step: label, reason: (out.output && out.output.error) || `exit ${out.exitCode}` })
    return null
  }
  return out.output || {}
}
function enter(title) {
  currentPhase = title
  phase(title)
}

// args: {
//   repoPath:     string,    // absolute path of the repository whose `bd` tracker is scored
//   pluginRoot:   string,    // absolute path of this plugin's root
//   workDir:      string,    // absolute path of a directory for this run's files; one per run
//   sadPath?:     string,    // the arc42 SAD (ATW_SAD_PATH): what already exists informs size
//   projectRoot?: string,    // the project root (ATW_PROJECT_ROOT), likewise
//   all?:         boolean,   // include items that already have a value
//   rejudge?:     boolean,   // judge again the existing values of the items included
//   only?:        string[],  // judge only these open Epics and Tasks
//   dryRun?:      boolean,   // compute everything and write nothing to the tracker
// }
//
// Returns: { ok, workDir, dryRun, plan, judging, record, score, failures,
//            dispatchFailed, dispatchFailures }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
const ID = /^[A-Za-z0-9._-]+$/
const only = a.only == null ? [] : a.only
if (!Array.isArray(only) || !only.every((id) => typeof id === 'string' && ID.test(id))) {
  return { ok: false, error: '`only` must be a list of bead ids' }
}
const dryRun = a.dryRun === true
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const flags = `${a.all === true ? '--all ' : ''}${a.rejudge === true ? '--rejudge ' : ''}${only.length ? `--only ${shq(only.join(','))} ` : ''}`
const dry = dryRun ? ' --dry-run' : ''
const stop = (error, extra) => ({ ok: false, workDir: work, dryRun, error, ...extra, failures, dispatchFailed: dispatchDeaths().length > 0, dispatchFailures: dispatchDeaths() })

// ── Plan ─────────────────────────────────────────────────────────────────────────
enter('Plan')
const planFile = file('score-plan.json')
const planned = await runStep('score-plan', cmd('score-plan', `${flags}--out ${shq(planFile)}`))
if (!planned) return stop('the plan could not be computed; nothing was judged or written')
const plan = planned.summary || {}
log(`Plan: ${plan.epicsToJudge || 0} Epic(s) and ${plan.tasksToJudge || 0} Task(s) to judge, ${plan.toAdopt || 0} stored value(s) to adopt`)

const prdDir = file('prd')
const inputs = {}
for (const level of ['epic', 'task']) {
  if (!((level === 'epic' ? plan.epicsToJudge : plan.tasksToJudge) > 0)) continue
  const path = file(`judge-input-${level}.json`)
  const out = await runStep(`judge-input:${level}`, cmd('judge-input', `--plan ${shq(planFile)} --level ${level}${level === 'epic' ? ` --prd-dir ${shq(prdDir)}` : ''} --out ${shq(path)}`))
  if (out) inputs[level] = { path, summary: out.summary || {} }
}
const epicIds = inputs.epic && Array.isArray(inputs.epic.summary.ids) ? inputs.epic.summary.ids.filter((id) => typeof id === 'string' && ID.test(id)) : []
const taskGroups = inputs.task && Array.isArray(inputs.task.summary.groups)
  ? inputs.task.summary.groups.filter((g) => g && typeof g.key === 'string' && ID.test(g.key) && Array.isArray(g.tasks) && g.tasks.length)
  : []
if (inputs.epic && epicIds.length !== plan.epicsToJudge) {
  return stop(`the plan names ${plan.epicsToJudge} Epic(s) to judge and the judge input lists ${epicIds.length}; nothing was judged or written`, { plan })
}

// ── Judge ────────────────────────────────────────────────────────────────────────
//
// A session per Epic, and a session per Epic's Tasks. Each writes its own file and none
// writes to the tracker, so they run concurrently, JUDGE_CONCURRENCY at a time.
enter('Judge')
const JUDGE_CONCURRENCY = 6
const JUDGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['path', 'judged'],
  properties: {
    path: { type: 'string' },
    judged: { type: 'integer' },
    unscored: { type: 'array', items: { type: 'string' } },
  },
}
const epicDir = file('judgments/epic')
const taskDir = file('judgments/task')

const JUDGE_RULES = `JOB SIZE follows the rubric's "Job Size" section, which is the same at both levels: the relative amount of work to deliver the outcome, judged against the agent pipeline as the reference capability — not calendar time, not human effort, not a count of repositories. Weigh volume, complexity, knowledge and uncertainty, as the rubric defines them, together to place the item; never score them separately or add them up. The numbers express approximate relative magnitude, not measured ratios or time commitments, and an item's tracking type does not decide its size: an Epic and a Task can both be 5. The scale is Fibonacci (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, and upward). Place each size by comparison with the \`referenceJobs\` in the judge-input file — elaborated Epics, each with its original estimate and its refined size, the sum of its Tasks — and name the comparison in the rationale. When \`referenceJobs\` is empty, judge knowledge and uncertainty from what already exists: the architecture document${a.sadPath ? ` (${a.sadPath})` : ''}, the existing code${a.projectRoot ? ` (under ${a.projectRoot})` : ''}, and the other artifacts that show what is already decided or built and what must be decided or built from scratch. Every size carries \`sizeLow\` and \`sizeHigh\`, the plausible range with the estimate inside it, and \`sizeConfidence\`, an integer percent. What remains unknown widens the range and lowers the size confidence.

THE RUBRIC OWNS ITS BANDS. The rungs in \`agent-teams-workforce:wsjf\` are the whole scale. RR-OE, reachability and WSJF are arithmetic computed after you return; they are not in your input and are not yours to state, estimate or reason about.`

const judgeEpic = (id) => settleAgent(
  `You judge ONE Epic, ${id}, under \`agent-teams-workforce:wsjf\` at Epic level. Load that skill with the Skill tool and follow it.

An Epic is a PRD: a business requirement. Read its full requirements document at ${prdDir}/${id}.md, to the end. Its entry in ${inputs.epic && inputs.epic.path} (the item whose \`id\` is ${id}) says whether it \`hasTasks\`; the same file holds the \`referenceJobs\`. Judge it from its own document against the rubric's rungs and the reference jobs, using the SAD and the project root for what is already decided or built. Read no other Epic's PRD and no other Epic's values: each Epic is judged on its own, so adding an Epic never moves another Epic's judged values.

${JUDGE_RULES}

Judge \`userBusinessValue\`, \`timeCriticality\` and their \`confidence\` (integer percent — the value confidence, covering UBV and TC only), and — only when \`hasTasks\` is false — the size estimate \`jobSize\` with \`sizeLow\`, \`sizeHigh\` and \`sizeConfidence\`. An Epic with Tasks takes its size from them. An Epic is sized before its design exists: judge the work to deliver the requirement from the requirement itself and from institutional knowledge — the SAD and what is already decided — and never invent a solution in order to size it. Missing implementation design is normal at this stage and is not itself evidence of exceptional difficulty, so it does not enlarge the size; let it show in the range and the size confidence. Uncertainty enlarges an Epic only where the PRD leaves an unresolved fact that could materially change the work — ambiguous scope, unknown feasibility, or assumptions with substantially different consequences. Each rationale cites the PRD.

Write ${epicDir}/${id}.json as ONE JSON object: {"rubric": "epic-wsjf", "scores": [{"id": "${id}", "userBusinessValue", "timeCriticality", "confidence", "jobSize", "sizeLow", "sizeHigh", "sizeConfidence" (the four size fields only when hasTasks is false), "rationale": {"userBusinessValue", "timeCriticality", "jobSize"}}], "unscored": []}, or, when you cannot judge it, {"rubric": "epic-wsjf", "scores": [], "unscored": [{"id": "${id}", "reason"}]}.

Return the path you wrote, how many items you judged (1 or 0), and the ids you could not judge.`,
  { label: `judge:epic:${id}`, phase: 'Judge', effort: 'high', schema: JUDGE_SCHEMA }
)

const judgeTasks = (group) => {
  const whose = group.epic ? `the Tasks of one Epic, ${group.epic}` : `one Task with no Epic, ${group.key}`
  return settleAgent(
    `You size ${whose}, under \`agent-teams-workforce:wsjf\` at Task level. Load that skill with the Skill tool and follow it. You judge Job Size and nothing else; value, time criticality and their confidence are inherited from each Task's Epic by arithmetic. A Task is sized from the established architecture, design and implementation instructions it carries.

Read ${inputs.task && inputs.task.path}. Size exactly these items in it, each an open Task with its own \`description\` and the Epic it sits under: ${group.tasks.join(', ')}. The same file holds the \`referenceJobs\`.

${JUDGE_RULES}

For each of those Tasks, judge the size estimate \`jobSize\` with \`sizeLow\`, \`sizeHigh\` and \`sizeConfidence\`. A Task above 13 should have been split. It is a decomposition fault: say so in its rationale, and record the size you judged. Do not reduce it to 13.

Write ${taskDir}/${group.key}.json as ONE JSON object: {"rubric": "task-wsjf", "scores": [{"id", "jobSize", "sizeLow", "sizeHigh", "sizeConfidence", "rationale": {"jobSize"}}], "unscored": [{"id", "reason"}]}, with exactly one entry per Task listed above, in \`scores\` or in \`unscored\`, and none for any other item.

Return the path you wrote, how many Tasks you judged, and the ids you could not judge.`,
    { label: `judge:task:${group.key}`, phase: 'Judge', effort: 'medium', schema: JUDGE_SCHEMA }
  )
}

const jobs = [
  ...epicIds.map((id) => ({ level: 'epic', key: id, run: () => judgeEpic(id) })),
  ...taskGroups.map((g) => ({ level: 'task', key: g.key, run: () => judgeTasks(g) })),
]
const judging = {
  epic: { sessions: 0, judged: 0, failed: [] },
  task: { sessions: 0, judged: 0, failed: [] },
}
for (let i = 0; i < jobs.length; i += JUDGE_CONCURRENCY) {
  const batch = jobs.slice(i, i + JUDGE_CONCURRENCY)
  const results = await parallel(batch.map((job) => () => job.run()))
  batch.forEach((job, n) => {
    const out = results[n]
    const tally = judging[job.level]
    tally.sessions += 1
    if (out) tally.judged += out.judged || 0
    else tally.failed.push(job.key)
  })
}
log(`Judged ${judging.epic.judged} Epic(s) in ${judging.epic.sessions} session(s) and ${judging.task.judged} Task(s) in ${judging.task.sessions} session(s); ${judging.epic.failed.length + judging.task.failed.length} session(s) failed`)

// ── Apply ────────────────────────────────────────────────────────────────────────
//
// Judged values first, then the arithmetic, which reads them together with the edges
// already in the tracker. The writes run one after another because they write the same
// tracker.
enter('Apply')
const recordArgs = [`--plan ${shq(planFile)}`]
if (judging.epic.sessions > judging.epic.failed.length) recordArgs.push(`--epics-dir ${shq(epicDir)}`)
if (judging.task.sessions > judging.task.failed.length) recordArgs.push(`--tasks-dir ${shq(taskDir)}`)
let recorded = null
if ((plan.epicsToJudge || 0) + (plan.tasksToJudge || 0) + (plan.toAdopt || 0) > 0) {
  const out = await runStep('record', cmd('record', `${recordArgs.join(' ')}${dry} --out ${shq(file('record.json'))}`))
  recorded = out ? out.summary || {} : null
  if (recorded && recorded.rejected) log(`Record: ${recorded.rejected} judgment(s) rejected — detail in ${file('record.json')}`)
}

const scored = await runStep('score', cmd('score', `--out ${shq(file('score.json'))}${dry}`))
const score = scored ? scored.summary || {} : null
if (score) {
  log(
    `Scored ${score.epicsScored} Epic(s) (${score.epicsWritten} written) and ${score.tasksScored} Task(s) (${score.tasksWritten} written); ` +
      `${score.unscored} unscored, ${score.incomplete} incomplete, ${score.outsideRange || 0} refined size(s) outside their estimate's range — detail in ${file('score.json')}`
  )
}

return {
  ok: !!score && failures.length === 0,
  workDir: work,
  dryRun,
  plan,
  judging,
  record: recorded,
  score,
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
