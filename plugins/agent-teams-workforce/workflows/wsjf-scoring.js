export const meta = {
  name: 'wsjf-scoring',
  description:
    "Scores every open Epic and Task with WSJF, and never sets a dependency: it reads the edges from beads. Edges decide ELIGIBILITY, WSJF decides PRIORITY among what is eligible. A model judges only where the source content changed or a value is missing: ONE session judges Epic value, time criticality and — for an Epic without Tasks — size, holding the whole portfolio through the Epic summaries and reading in full the PRDs of the Epics it judges; ONE session judges Task sizes; every size on one Fibonacci scale with a plausible range and a size confidence, kept apart from the value confidence. Then the arithmetic — Epic RR-OE, the Architectural Enabler measure, from reachability over the Epic design-order edges, Epic size as the plain sum of its Tasks' sizes, Task RR-OE, the value a Task inherits, every WSJF — runs over the WHOLE portfolio, and only values that changed are written. `all` includes items that already have a value; `rejudge` judges the existing values of the items included again.",
  whenToUse: "Scoring after Epics or Tasks are added or changed, or after dependency assessment applies edges; with all and rejudge, re-judging the whole portfolio.",
  phases: [
    { title: "Summaries", detail: "bring the Epic summaries current" },
    { title: "Plan", detail: "fingerprints decide what is judged" },
    { title: "Judge", detail: "Epic value and size, and Task size, concurrently" },
    { title: "Apply", detail: "judged values, then the whole-portfolio arithmetic" },
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
//   repoPath:     string,   // absolute path of the repository whose `bd` tracker is scored
//   pluginRoot:   string,   // absolute path of this plugin's root
//   workDir:      string,   // absolute path of a directory for this run's files; one per run
//   sadPath?:     string,   // the arc42 SAD (ATW_SAD_PATH): what already exists informs size
//   projectRoot?: string,   // the project root (ATW_PROJECT_ROOT), likewise
//   all?:         boolean,  // include items that already have a value
//   rejudge?:     boolean,  // judge again the existing values of the items included
// }
//
// Returns: { ok, workDir, summaries, plan, judging, record, score, failures,
//            dispatchFailed, dispatchFailures }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const flags = `${a.all === true ? '--all ' : ''}${a.rejudge === true ? '--rejudge ' : ''}`

// ── Summaries ────────────────────────────────────────────────────────────────────
//
// The Epic judge reads the portfolio through the Epic summaries, so they are brought
// current first. An Epic left without one is read from its PRD instead.
enter('Summaries')
const summaries = await workflow('agent-teams-workforce:epic-summaries', {
  repoPath: repo,
  pluginRoot: a.pluginRoot,
  workDir: file('summaries'),
  sadPath: a.sadPath,
})

// ── Plan ─────────────────────────────────────────────────────────────────────────
enter('Plan')
const planFile = file('score-plan.json')
const planned = await runStep('score-plan', cmd('score-plan', `${flags}--out ${shq(planFile)}`))
if (!planned) {
  return { ok: false, workDir: work, summaries, error: 'the plan could not be computed; nothing was judged or written', failures, dispatchFailed: dispatchDeaths().length > 0, dispatchFailures: dispatchDeaths() }
}
const plan = planned.summary || {}
log(`Plan: ${plan.epicsToJudge || 0} Epic(s) and ${plan.tasksToJudge || 0} Task(s) to judge, ${plan.toAdopt || 0} stored value(s) to adopt`)
const portfolioFile = file('portfolio.md')
const judgeFiles = {}
await parallel(
  ['epic', 'task']
    .filter((level) => (level === 'epic' ? plan.epicsToJudge : plan.tasksToJudge) > 0)
    .map((level) => async () => {
      const path = file(`judge-input-${level}.json`)
      const ok = await runStep(`judge-input:${level}`, cmd('judge-input', `--plan ${shq(planFile)} --level ${level}${level === 'epic' ? ` --prd-dir ${shq(file('prd'))}` : ''} --out ${shq(path)}`))
      if (!ok) return
      if (level === 'epic' && !(await runStep('portfolio', cmd('portfolio', `--markdown ${shq(portfolioFile)}`)))) return
      judgeFiles[level] = path
    })
)

// ── Judge ────────────────────────────────────────────────────────────────────────
//
// The two judging sessions read different inputs and write different files, so they run
// concurrently. Neither writes to the tracker.
enter('Judge')
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
const epicJudgments = file('epic-judgments.json')
const taskJudgments = file('task-judgments.json')

const JUDGE_RULES = `THE INPUT. Every open item at this level is in the file, whether or not you judge it. Items with \`judge: true\` are yours to judge. Items with \`judge: false\` carry their \`current\` judged values: they are the comparison set that tells you where the rungs sit, and you do not change them. Judge each item from its own content against the rubric's rungs.

JOB SIZE follows the rubric's "Job Size" section, which is the same at both levels: the relative amount of work to deliver the outcome, judged against the agent pipeline as the reference capability — not calendar time, not human effort, not a count of repositories. Weigh volume, complexity, knowledge and uncertainty, as the rubric defines them, together to place the item; never score them separately or add them up. The numbers express approximate relative magnitude, not measured ratios or time commitments, and an item's tracking type does not decide its size: an Epic and a Task can both be 5. The scale is Fibonacci (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, and upward). Place each size by comparison with the file's \`referenceJobs\` — elaborated Epics, each with its original estimate and its refined size, the sum of its Tasks — and name the comparison in the rationale. When \`referenceJobs\` is empty, judge knowledge and uncertainty from what already exists: the architecture document${a.sadPath ? ` (${a.sadPath})` : ''}, the existing code${a.projectRoot ? ` (under ${a.projectRoot})` : ''}, and the other artifacts that show what is already decided or built and what must be decided or built from scratch. Every size carries \`sizeLow\` and \`sizeHigh\`, the plausible range with the estimate inside it, and \`sizeConfidence\`, an integer percent. What remains unknown widens the range and lowers the size confidence.

THE RUBRIC OWNS ITS BANDS. The rungs in \`agent-teams-workforce:wsjf\` are the whole scale. RR-OE, reachability and WSJF are arithmetic computed after you return; they are not in your input and are not yours to state, estimate or reason about.`

const [epicJudged, taskJudged] = await parallel([
  async () => {
    if (!judgeFiles.epic) return null
    return settleAgent(
      `You are the ONE session judging the Epic portfolio under \`agent-teams-workforce:wsjf\` at Epic level. Load that skill with the Skill tool and follow it.

Read ${judgeFiles.epic}. Each item is an open Epic, and \`prdPath\` names the file holding its full requirements document (the PRD). Read ${portfolioFile} as well — every open Epic with its stored summary: the architecture decisions its requirements should drive, the decisions it should be designed on top of, which of those the SAD already settles, and its value and urgency. It is long; read it in consecutive chunks until the end. You hold the portfolio through the summaries, and read in full the PRD of each item you judge. Where the items to judge are too many to read every PRD in full, judge from the summaries and open the PRD of each item whose summary cannot support its value, urgency or size.

${JUDGE_RULES}

FOR EACH ITEM WITH \`judge: true\`, judge \`userBusinessValue\`, \`timeCriticality\` and their \`confidence\` (integer percent — the value confidence, covering UBV and TC only), and — only when \`hasTasks\` is false — the size estimate \`jobSize\` with \`sizeLow\`, \`sizeHigh\` and \`sizeConfidence\`. An Epic with Tasks takes its size from them. An Epic is sized before its design exists: judge the work to deliver the requirement from the requirement itself and from institutional knowledge — the SAD and what is already decided — and never invent a solution in order to size it. Missing implementation design is normal at this stage and is not itself evidence of exceptional difficulty, so it does not enlarge the size; let it show in the range and the size confidence. Uncertainty enlarges an Epic only where the PRD leaves an unresolved fact that could materially change the work — ambiguous scope, unknown feasibility, or assumptions with substantially different consequences.

Write ${epicJudgments} as ONE JSON object: {"rubric": "epic-wsjf", "scores": [{"id", "userBusinessValue", "timeCriticality", "confidence", "jobSize", "sizeLow", "sizeHigh", "sizeConfidence" (the four size fields only when hasTasks is false), "rationale": {"userBusinessValue", "timeCriticality", "jobSize"}}], "unscored": [{"id", "reason"}]}, with exactly one entry per \`judge: true\` item, in \`scores\` or in \`unscored\`, and none for any other item.

Return the path you wrote, how many items you judged, and the ids you could not judge.`,
      { label: 'judge:epic', phase: 'Judge', effort: 'high', schema: JUDGE_SCHEMA }
    )
  },
  async () => {
    if (!judgeFiles.task) return null
    return settleAgent(
      `You are the ONE session judging Task sizes under \`agent-teams-workforce:wsjf\` at Task level. Load that skill with the Skill tool and follow it. You judge Job Size and nothing else; value, time criticality and their confidence are inherited from each Task's Epic by arithmetic. A Task is sized from the established architecture, design and implementation instructions it carries.

Read ${judgeFiles.task}. Each item is an open Task with its own \`description\` and the Epic it sits under.

${JUDGE_RULES}

FOR EACH ITEM WITH \`judge: true\`, judge the size estimate \`jobSize\` with \`sizeLow\`, \`sizeHigh\` and \`sizeConfidence\`. A Task above 13 should have been split. It is a decomposition fault: say so in its rationale, and record the size you judged. Do not reduce it to 13.

Write ${taskJudgments} as ONE JSON object: {"rubric": "task-wsjf", "scores": [{"id", "jobSize", "sizeLow", "sizeHigh", "sizeConfidence", "rationale": {"jobSize"}}], "unscored": [{"id", "reason"}]}, with exactly one entry per \`judge: true\` item, in \`scores\` or in \`unscored\`, and none for any other item.

Return the path you wrote, how many items you judged, and the ids you could not judge.`,
      { label: 'judge:task', phase: 'Judge', effort: 'medium', schema: JUDGE_SCHEMA }
    )
  },
])

// ── Apply ────────────────────────────────────────────────────────────────────────
//
// Judged values first, then the arithmetic, which reads them together with the edges
// already in the tracker. The writes run one after another because they write the same
// tracker.
enter('Apply')
const recordArgs = [`--plan ${shq(planFile)}`]
if (epicJudged) recordArgs.push(`--epics ${shq(epicJudgments)}`)
if (taskJudged) recordArgs.push(`--tasks ${shq(taskJudgments)}`)
let recorded = null
if ((plan.epicsToJudge || 0) + (plan.tasksToJudge || 0) + (plan.toAdopt || 0) > 0) {
  const out = await runStep('record', cmd('record', `${recordArgs.join(' ')} --out ${shq(file('record.json'))}`))
  recorded = out ? out.summary || {} : null
}

const scored = await runStep('score', cmd('score', `--out ${shq(file('score.json'))}`))
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
  summaries,
  plan,
  judging: {
    epic: judgeFiles.epic ? epicJudged || { failed: true } : null,
    task: judgeFiles.task ? taskJudged || { failed: true } : null,
  },
  record: recorded,
  score,
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
