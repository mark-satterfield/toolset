export const meta = {
  name: 'wsjf-scoring',
  description:
    "Scores every open Epic and Task with WSJF from the dependency edges already in beads. Judges, one session per Epic and one per Epic's Tasks, only the items whose content changed or whose value is missing, records the judgments, then runs the arithmetic over every open item and writes the values that changed. `all` includes items that already have a value; `rejudge` judges them again; `only` restricts judging to named items; `dryRun` writes nothing.",
  whenToUse: "Scoring after Epics or Tasks are added or changed, or after dependency assessment applies edges; with all and rejudge, re-judging every Epic and Task.",
  phases: [
    { title: "Plan", detail: "fingerprints decide what is judged" },
    { title: "Judge", detail: "a session per Epic, and a session per Epic's Tasks" },
    { title: "Apply", detail: "judged values, then the arithmetic over every open item" },
  ],
}
const dispatchFailures = []
// Returns the recorded dispatch failures of the named phases, or all of them when none is named.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
// Returns 'transient' for an API overload, rate limit or network error, otherwise 'deterministic'.
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  return TRANSIENT_ERROR_TEXT.test(text) ? 'transient' : 'deterministic'
}
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
const settleSleep = (ms) => (SETTLE_CAN_WAIT ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve())
// Returns the wait before retry `attempt`: 5s tripled per attempt, capped at 300s, scaled into [50%, 100%) by a hash of the dispatch.
function transientWaitMs(name, attempt) {
  const key = `${name}#${attempt}`
  let h = 2166136261
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  const scheduled = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
  return Math.round(scheduled * (0.5 + 0.5 * ((h >>> 0) / 4294967296)))
}
// Calls agent() and returns its result. A transient failure is retried with backoff until it clears
// (three attempts when no timer exists); any other failure returns null and is recorded in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    let out = null
    try {
      out = await agent(prompt, o)
    } catch (err) {
      const message = String((err && err.message) || err)
      const cause = failureCause(err)
      const entry = {
        ...who,
        outcome: 'threw',
        cause,
        attempt,
        message: message.slice(0, 300),
        note: `${name} ended without a structured result (${cause}): ${message.slice(0, 160)}`,
      }
      dispatchFailures.push(entry)
      mine.push(entry)
      log(entry.note)
      if (cause !== 'transient' || (!SETTLE_CAN_WAIT && attempt >= 3)) return null
      const wait = transientWaitMs(name, attempt)
      waitedMs += wait
      log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s (${Math.round(waitedMs / 1000)}s waited)`)
      await settleSleep(wait)
      continue
    }
    if (out) {
      for (const entry of mine) {
        const at = dispatchFailures.indexOf(entry)
        if (at >= 0) dispatchFailures.splice(at, 1)
      }
      return out
    }
    dispatchFailures.push({ ...who, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: `${name} returned nothing` })
    log(`${name} returned nothing`)
    return null
  }
}

const RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['results'],
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'exitCode', 'output'],
        properties: {
          name: { type: 'string' },
          exitCode: { type: 'integer' },
          output: { type: 'object' },
        },
      },
    },
  },
}
const failures = []
let currentPhase = null
// Runs `steps` ([{ name, command }]) in one runner session, in order. Returns name -> printed JSON;
// a command reported as failed maps to null and is recorded in `failures`; one not reported maps to null.
async function runSteps(label, steps) {
  const out = await settleAgent(
    `Run these shell commands, in this order, each exactly once, from any directory, and change nothing else. Run every one of them even when an earlier one fails.

${steps.map((s, i) => `${i + 1}. name "${s.name}":\n   ${s.command}`).join('\n')}

Each prints one JSON object on stdout. Return one entry per command in \`results\`: its name exactly as given, its process exit code as \`exitCode\`, and that JSON object, parsed and unaltered, as \`output\`. If a command's stdout is not JSON, its \`output\` is {"error": "<stdout and stderr, verbatim>"}. Do not retry, do not repair, do not run any other command.`,
    { label, phase: currentPhase, model: 'haiku', effort: 'low', schema: RUN_SCHEMA }
  )
  const byName = new Map((out && Array.isArray(out.results) ? out.results : []).map((r) => [r && r.name, r]))
  const outputs = {}
  for (const s of steps) {
    const r = byName.get(s.name)
    if (!r) {
      log(`${s.name}: ${out ? 'the runner did not report this command' : 'the runner returned no result'}; its effect is read from the tracker by the next plan`)
      outputs[s.name] = null
    } else if (r.exitCode !== 0 || (r.output && r.output.error)) {
      failures.push({ step: s.name, reason: (r.output && r.output.error) || `exit ${r.exitCode}` })
      outputs[s.name] = null
    } else {
      outputs[s.name] = r.output || {}
    }
  }
  return outputs
}
function enter(title) {
  currentPhase = title
  phase(title)
}

// args: {
//   repoPath:     string,    // absolute path of the repository whose `bd` tracker is scored
//   pluginRoot:   string,    // absolute path of this plugin's root
//   workDir:      string,    // absolute path of a directory for this run's files
//   sadPath?:     string,
//   projectRoot?: string,
//   all?:         boolean,   // include items that already have a value
//   rejudge?:     boolean,   // judge again the existing values of the items included
//   only?:        string[],  // judge only these open Epics and Tasks
//   dryRun?:      boolean,   // write nothing to the tracker
// }
// Returns: { ok, stage, headline, workDir, dryRun, plan, judging, judgingFailed, error?, record, score,
//            failures, dispatchFailed, dispatchFailures }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const only = Array.isArray(a.only) ? a.only.filter((id) => typeof id === 'string' && id) : []
const dryRun = a.dryRun === true
const repo = String(a.repoPath || '').replace(/\/+$/, '')
const work = String(a.workDir || '').replace(/\/+$/, '')
const DS = `${String(a.pluginRoot || '').replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const flags = `${a.all === true ? '--all ' : ''}${a.rejudge === true ? '--rejudge ' : ''}${only.length ? `--only ${shq(only.join(','))} ` : ''}`
const dry = dryRun ? ' --dry-run' : ''

enter('Plan')
const planFile = file('score-plan.json')
const prdDir = file('prd')
const inputPath = (level) => file(`judge-input-${level}.json`)
const planned = await runSteps('plan', [
  { name: 'score-plan', command: cmd('score-plan', `${flags}--out ${shq(planFile)}`) },
  ...['epic', 'task'].map((level) => ({
    name: `judge-input:${level}`,
    command: cmd('judge-input', `--plan ${shq(planFile)} --level ${level}${level === 'epic' ? ` --prd-dir ${shq(prdDir)}` : ''} --out ${shq(inputPath(level))}`),
  })),
])
const plan = (planned['score-plan'] && planned['score-plan'].summary) || {}
log(`Plan: ${plan.epicsToJudge || 0} Epic(s) and ${plan.tasksToJudge || 0} Task(s) to judge, ${plan.toAdopt || 0} stored value(s) to adopt`)

const inputs = {}
for (const level of ['epic', 'task']) {
  if (!((level === 'epic' ? plan.epicsToJudge : plan.tasksToJudge) > 0)) {
    for (let i = failures.length - 1; i >= 0; i--) if (failures[i].step === `judge-input:${level}`) failures.splice(i, 1)
    continue
  }
  const out = planned[`judge-input:${level}`]
  if (out) inputs[level] = { path: inputPath(level), summary: out.summary || {} }
}
const epicIds = inputs.epic && Array.isArray(inputs.epic.summary.ids) ? inputs.epic.summary.ids.filter((id) => typeof id === 'string' && id) : []
const taskGroups = inputs.task && Array.isArray(inputs.task.summary.groups)
  ? inputs.task.summary.groups.filter((g) => g && typeof g.key === 'string' && Array.isArray(g.tasks) && g.tasks.length)
  : []

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
  { label: `judge:epic:${id}`, phase: 'Judge', effort: 'medium', schema: JUDGE_SCHEMA }
)

const judgeTasks = (group) => {
  const whose = group.epic ? `the Tasks of one Epic, ${group.epic}` : `one Task with no Epic, ${group.key}`
  return settleAgent(
    `You size ${whose}, under \`agent-teams-workforce:wsjf\` at Task level. Load that skill with the Skill tool and follow it. You judge Job Size and nothing else; value, time criticality and their confidence are inherited from each Task's Epic by arithmetic. A Task is sized from the established architecture, design and implementation instructions it carries.

Read ${inputs.task && inputs.task.path}. Size exactly these items in it, each an open Task with its own \`description\` and the Epic it sits under: ${group.tasks.join(', ')}. The same file holds the \`referenceJobs\`.

${JUDGE_RULES}

For each of those Tasks, judge the size estimate \`jobSize\` with \`sizeLow\`, \`sizeHigh\` and \`sizeConfidence\`. A Task above 13 should have been split: say so in its rationale, and record the size you judged. Do not reduce it to 13.

Write ${taskDir}/${group.key}.json as ONE JSON object: {"rubric": "task-wsjf", "scores": [{"id", "jobSize", "sizeLow", "sizeHigh", "sizeConfidence", "rationale": {"jobSize"}}], "unscored": [{"id", "reason"}]}, with exactly one entry per Task listed above, in \`scores\` or in \`unscored\`, and none for any other item.

Return the path you wrote, how many Tasks you judged, and the ids you could not judge.`,
    { label: `judge:task:${group.key}`, phase: 'Judge', effort: 'medium', schema: JUDGE_SCHEMA }
  )
}

const jobs = [
  ...epicIds.map((id) => ({ level: 'epic', key: id, ids: [id], run: () => judgeEpic(id) })),
  ...taskGroups.map((g) => ({ level: 'task', key: g.key, ids: g.tasks.slice(), run: () => judgeTasks(g) })),
]
const judging = {
  epic: { sessions: 0, judged: 0, failed: [], failedSessions: 0 },
  task: { sessions: 0, judged: 0, failed: [], failedGroups: [], failedSessions: 0 },
}
const judged = await parallel(jobs.map((job) => () => job.run()))
jobs.forEach((job, n) => {
  const out = judged[n]
  const tally = judging[job.level]
  tally.sessions += 1
  if (out) {
    tally.judged += out.judged || 0
    return
  }
  tally.failedSessions += 1
  tally.failed.push(...job.ids)
  if (job.level === 'task') tally.failedGroups.push(job.key)
})
const judgingFailed = [...judging.epic.failed, ...judging.task.failed]
log(`Judged ${judging.epic.judged} Epic(s) in ${judging.epic.sessions} session(s) and ${judging.task.judged} Task(s) in ${judging.task.sessions} session(s); record reads every judgment file on disk`)

enter('Apply')
const recordArgs = [`--plan ${shq(planFile)}`, `--epics-dir ${shq(epicDir)}`, `--tasks-dir ${shq(taskDir)}`]
const records = !planned['score-plan'] || (plan.epicsToJudge || 0) + (plan.tasksToJudge || 0) + (plan.toAdopt || 0) > 0
const applied = await runSteps('apply', [
  ...(records ? [{ name: 'record', command: cmd('record', `${recordArgs.join(' ')}${dry} --out ${shq(file('record.json'))}`) }] : []),
  { name: 'score', command: cmd('score', `--out ${shq(file('score.json'))}${dry}`) },
])
const recorded = records && applied.record ? applied.record.summary || {} : null

const score = applied.score ? applied.score.summary || {} : null
if (score) {
  log(`Scored ${score.epicsScored} Epic(s) (${score.epicsWritten} written) and ${score.tasksScored} Task(s) (${score.tasksWritten} written) — detail in ${file('score.json')}`)
}

const unjudged = recorded ? (Number(recorded.missing) || 0) + (Number(recorded.rejected) || 0) : 0
if (unjudged) log(`${unjudged} planned item(s) have no usable judgment on disk; the next plan judges them again`)
const errors = [
  failures.length ? `step(s) failed: ${failures.map((f) => `${f.step} (${f.reason})`).join('; ')}` : '',
].filter(Boolean)
const runError = errors.length ? { error: errors.join('; ') } : {}

const scoredOk = failures.length === 0
return {
  ok: scoredOk,
  stage: scoredOk ? 'done' : 'Apply',
  headline: runError.error || (score ? `scored ${score.epicsScored} Epic(s) and ${score.tasksScored} Task(s); ${score.epicsWritten + score.tasksWritten} value(s) written${dryRun ? ' (dry run)' : ''}` : 'the arithmetic did not run'),
  workDir: work,
  dryRun,
  plan,
  judging,
  judgingFailed,
  ...runError,
  record: recorded,
  score,
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
