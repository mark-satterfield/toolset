export const meta = {
  name: 'dependencies-and-scoring',
  description:
    'Maintains the Epic dependency edges and the WSJF score of every open Epic and Task in the beads tracker. Edges decide ELIGIBILITY, WSJF decides PRIORITY among what is eligible. The arithmetic — Epic RR-OE from transitive reachability over the Epic edges, Epic Job Size from the roll-up of its Tasks, Task RR-OE from the Task graph, the value a Task inherits from its Epic, and every WSJF — is recomputed for the WHOLE portfolio on every run, so a change anywhere reaches every score that depends on it, and only values that changed are written. Epics and their Tasks are scored in one computation, so an Epic is never scored without its Tasks. A model is used only for JUDGED inputs, and only where the content they are judged from changed since they were judged, or they were never judged: ONE session judges Epic value, time criticality and span against the whole portfolio, ONE session judges Task sizes, and the epic-sequencer re-derives the edges over the whole portfolio when any open Epic is new or changed since it last read it. `all` re-judges every judged input and re-derives the edges whatever the fingerprints say.',
  whenToUse: 'Seeding or refreshing the Epic dependency edges and the WSJF scores; run after Epics or Tasks are added or changed.',
  phases: [
    { title: 'Plan', detail: 'fingerprints decide what is judged and whether the sequencer runs' },
    { title: 'Judge', detail: 'epic-sequencer, Epic value judgment and Task sizing, concurrently' },
    { title: 'Apply', detail: 'edges, judged values, then the whole-portfolio arithmetic' },
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

// args: {
//   repoPath:   string,   // absolute path of the repository whose `bd` tracker is scored
//   pluginRoot: string,   // absolute path of this plugin's root
//   workDir:    string,   // absolute path of a directory for this run's files; one per run
//   all?:       boolean,  // re-judge every judged input and re-derive the edges
// }
//
// Returns: {
//   ok, workDir, plan, sequencing, judging, edges, record, score, dispatchFailed, failures
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return {
    ok: false,
    error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}`,
  }
}
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/dependencies-and-scoring/depscore.py`
const everything = a.all === true
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`

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
let currentPhase = 'Plan'
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

// ── Plan ─────────────────────────────────────────────────────────────────────────
enter('Plan')
const planFile = file('plan.json')
const planned = await runStep('query', cmd('query', `${everything ? '--all ' : ''}--out ${shq(planFile)}`))
if (!planned) {
  return { ok: false, workDir: work, error: 'the plan could not be computed; nothing was judged or written', failures, dispatchFailed: dispatchDeaths().length > 0, dispatchFailures: dispatchDeaths() }
}
const plan = planned.summary || {}
log(
  `Plan: ${plan.epicsToJudge || 0} Epic(s) and ${plan.tasksToJudge || 0} Task(s) to judge, ${plan.toAdopt || 0} judged value(s) to adopt; ` +
    (plan.sequence ? `sequencer runs (${(plan.sequenceWhy || []).join('; ')})` : 'edges stand')
)
const judgeFiles = {}
await parallel(
  ['epic', 'task']
    .filter((level) => (level === 'epic' ? plan.epicsToJudge : plan.tasksToJudge) > 0)
    .map((level) => async () => {
      const path = file(`judge-input-${level}.json`)
      const ok = await runStep(`judge-input:${level}`, cmd('judge-input', `--plan ${shq(planFile)} --level ${level} --out ${shq(path)}`))
      if (ok) judgeFiles[level] = path
    })
)

// ── Judge ────────────────────────────────────────────────────────────────────────
//
// The three judged steps read different inputs and write different files, so they run
// concurrently. None of them writes to the tracker.
enter('Judge')
const SEQUENCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['edgesPath', 'edgeCount', 'valid'],
  properties: {
    edgesPath: { type: 'string' },
    tieringPath: { type: 'string' },
    edgeCount: { type: 'integer' },
    valid: { type: 'boolean' },
    unsure: { type: 'array', items: { type: 'string' } },
  },
}
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
const edgesFile = file('edges.json')
const tieringFile = file('tiering.md')
const epicJudgments = file('epic-judgments.json')
const taskJudgments = file('task-judgments.json')

const JUDGE_RULES = `THE INPUT. Every open item at this level is in the file, whether or not you judge it. Items with \`judge: true\` are yours to judge. Items with \`judge: false\` carry their \`current\` judged values: they are the comparison set that tells you where the rungs sit, and you do not change them. Judge each item from its own content against the rubric's rungs.

THE RUBRIC OWNS ITS BANDS. The rungs in \`agent-teams-workforce:wsjf\` are the whole scale. RR-OE, reachability and WSJF are arithmetic computed after you return; they are not in your input and are not yours to state, estimate or reason about.`

const [sequenced, epicJudged, taskJudged] = await parallel([
  async () => {
    if (!plan.sequence) return null
    return settleAgent(
      `Order the whole open Epic portfolio and emit its dependency edge set, following \`agent-teams-workforce:epic-sequencing\`.

Repository holding the tracker: ${repo}

1. Read the portfolio: \`${cmd('snapshot', `--kinds epic --with-description --out ${shq(file('snapshot.json'))}`)}\` and then read ${file('snapshot.json')} whole.
2. Write the edge file, over the WHOLE portfolio, to ${edgesFile}, and the tiering account to ${tieringFile}.
3. Validate: \`${cmd('validate', `--edges ${shq(edgesFile)}`)}\` — fix the file until \`ok\` is true.

Return the edge file path, the edge count, whether the final validation passed, and each edge you were unsure of with what would settle it.`,
      { label: 'epic-sequencer', phase: 'Judge', agentType: 'agent-teams-workforce:epic-sequencer', schema: SEQUENCE_SCHEMA }
    )
  },
  async () => {
    if (!judgeFiles.epic) return null
    return settleAgent(
      `You are the ONE session judging the Epic portfolio under \`agent-teams-workforce:wsjf\` at Epic level. Load that skill with the Skill tool and follow it.

Read ${judgeFiles.epic}. Each item is an open Epic; its \`description\` is its requirements document (the PRD).

${JUDGE_RULES}

FOR EACH ITEM WITH \`judge: true\`, judge \`userBusinessValue\`, \`timeCriticality\` and an overall \`confidence\` (integer percent), and — only when \`hasTasks\` is false — the span \`jobSize\`. An Epic with Tasks takes its size from them.

Write ${epicJudgments} as ONE JSON object: {"rubric": "epic-wsjf", "scores": [{"id", "userBusinessValue", "timeCriticality", "jobSize" (only when hasTasks is false), "confidence", "rationale": {"userBusinessValue", "timeCriticality", "jobSize"}}], "unscored": [{"id", "reason"}]}, with exactly one entry per \`judge: true\` item, in \`scores\` or in \`unscored\`, and none for any other item.

Return the path you wrote, how many items you judged, and the ids you could not judge.`,
      { label: 'judge:epic', phase: 'Judge', effort: 'high', schema: JUDGE_SCHEMA }
    )
  },
  async () => {
    if (!judgeFiles.task) return null
    return settleAgent(
      `You are the ONE session judging Task sizes under \`agent-teams-workforce:wsjf\` at Task level. Load that skill with the Skill tool and follow it. You judge Job Size in developer-days and nothing else; value and time criticality are inherited from each Task's Epic by arithmetic.

Read ${judgeFiles.task}. Each item is an open Task with its own \`description\` and the Epic it sits under.

${JUDGE_RULES}

FOR EACH ITEM WITH \`judge: true\`, judge \`jobSize\` on the Task scale. A Task that exceeds the scale's ceiling is a decomposition fault: size it at the ceiling and say so in its rationale.

Write ${taskJudgments} as ONE JSON object: {"rubric": "task-wsjf", "scores": [{"id", "jobSize", "rationale": {"jobSize"}}], "unscored": [{"id", "reason"}]}, with exactly one entry per \`judge: true\` item, in \`scores\` or in \`unscored\`, and none for any other item.

Return the path you wrote, how many items you judged, and the ids you could not judge.`,
      { label: 'judge:task', phase: 'Judge', effort: 'medium', schema: JUDGE_SCHEMA }
    )
  },
])

// ── Apply ────────────────────────────────────────────────────────────────────────
//
// Edges first, then judged values, then the arithmetic, which reads both. The writes run
// one after another because they write the same tracker.
enter('Apply')
let edges = { ran: false, reason: plan.sequence ? null : 'no open Epic is new or changed since the sequencer last read it' }
if (plan.sequence) {
  if (sequenced && sequenced.valid) {
    const applied = await runStep('apply-edges', cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)} --out ${shq(file('apply-edges.json'))}`))
    edges = { ran: true, ...(applied ? applied.summary || {} : { applied: false }), tiering: tieringFile, unsure: (sequenced && sequenced.unsure) || [] }
  } else {
    edges = {
      ran: false,
      reason: sequenced ? 'the proposed edge set did not validate; the tracker keeps its current edges' : 'the epic-sequencer returned no result; the tracker keeps its current edges',
    }
  }
}

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
      `${score.unscored} unscored, ${score.incomplete} incomplete — detail in ${file('score.json')}`
  )
}

return {
  ok: !!score && failures.length === 0 && (!plan.sequence || edges.applied === true),
  workDir: work,
  plan,
  sequencing: plan.sequence ? { ran: !!sequenced, ...(sequenced || {}) } : { ran: false },
  judging: {
    epic: judgeFiles.epic ? epicJudged || { failed: true } : null,
    task: judgeFiles.task ? taskJudged || { failed: true } : null,
  },
  edges,
  record: recorded,
  score,
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
