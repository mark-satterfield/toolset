export const meta = {
  name: 'task-dependency-assessment',
  description:
    "Assesses the build dependencies of ONE Task created outside elaboration (a Task with no `elab_key`), and writes edges and nothing else. A Task dependency is a build dependency: an edge from A to B says B cannot be built until A is built, because B consumes something A provides — an API, an event contract, a table, an IAM grant, a deployed resource. It is stored as a beads `blocks` edge between two Tasks; no end is a Story or an Epic. One task-dependency-mapper session reads the Task, names what it consumes and what it provides, searches the other open Tasks for the ones that provide what it consumes or consume what it provides, reads those in full, and applies the test in both directions. It proposes every edge to or from the Task with a reason, and keeps or withdraws, with a reason, every owned edge standing on it. Code refuses an edge that does not touch the Task, an edge that does not join two open Tasks, a Task written by elaboration, a cycle, an unaccounted standing edge and a missing reason, confines the write to that Task's edges, and never touches a hand-made edge. A proposal that does not validate is assessed again with the validator's findings, at most twice, and then the run stops, naming the Task and the findings and writing nothing. When the edges are applied it triggers wsjf-scoring, because edges decide Task RR-OE. With `apply: false` it proposes only: it computes the edge diff as a dry run, returns it, writes nothing to the tracker and triggers no scoring.",
  whenToUse: 'A Task was created or changed outside elaboration and needs its build dependencies assessed.',
  phases: [
    { title: 'Context', detail: "the Task's fingerprint, its standing edges, and the open Tasks with their index" },
    { title: 'Assess', detail: 'the task-dependency-mapper proposes every edge to or from the Task and accounts for every owned standing edge; code validates each attempt, up to three' },
    { title: 'Apply', detail: 'validate and apply the edge diff for the Task, or compute it as a dry run' },
    { title: 'Score', detail: 'wsjf-scoring over the new edges' },
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
// writes its full result to a file in the run directory and prints only its counts, so no
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
//   repoPath:     string,   // absolute path of the repository whose `bd` tracker holds the Tasks
//   pluginRoot:   string,   // absolute path of this plugin's root
//   workDir:      string,   // absolute path of a directory for this run's files; one per run
//   task:         string,   // the one Task assessed: open, and created outside elaboration
//   projectRoot?: string,   // the project root (ATW_PROJECT_ROOT), passed to the scoring it triggers
//   sadPath?:     string,   // the arc42 SAD (ATW_SAD_PATH), passed to the scoring it triggers
//   score?:       boolean,  // false: do not trigger scoring when the edges are applied. Default true.
//   apply?:       boolean,  // false: propose only — no edge, reason or score is written; `edges`
//                           // carries the diff (added, converted, removed, withdrawn, unchanged,
//                           // planned) computed as a dry run. Default true.
// }
//
// Returns: { ok, apply, settled, attempts, workDir, task, plan, context, assessment, edges,
//            scoring, stop, error?, headline?, failures, dispatchFailed, dispatchFailures }
//   settled:    the validator passed an attempt's edge file; nothing is applied otherwise
//   attempts:   the task-dependency-mapper sessions run, at most 3
//   assessment: the last session's result
//   stop:       null, or { task, attempts, findings, edgesFile, validationFile, reasoning } when
//               no attempt validated; `error` and `headline` then name the Task and each finding
// With `apply: false`, `scoring` is null and `ok` means the diff was proposed.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, settled: false, attempts: 0, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
const target = a.task
if (!(typeof target === 'string' && /^[A-Za-z0-9._-]+$/.test(target))) {
  return { ok: false, settled: false, attempts: 0, error: '`task`, the id of the one Task to assess, is required' }
}
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const scope = ` --task ${shq(target)}`
const applies = a.apply !== false
const project = { repoPath: repo, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }
const fail = (error, extra) => ({
  ok: false,
  apply: applies,
  settled: false,
  attempts: 0,
  workDir: work,
  task: target,
  error,
  ...(extra || {}),
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
})

// ── Context ──────────────────────────────────────────────────────────────────────
//
// The plan records the fingerprint the Task is assessed at. The context writes every open
// Task to the corpus directory and an index of their titles, Epics, repositories and
// statuses, and lists every edge standing between this Task and another open Task, with
// the reason recorded for each owned one. Both refuse a Task written by elaboration.
enter('Context')
const planFile = file('assess-plan.json')
const contextDir = file('context')
const contextFile = file('context.json')
const corpusDir = `${contextDir}/task`
const indexFile = `${contextDir}/index.md`
const taskFile = `${corpusDir}/${target}.md`
const planned = await runStep('assess-plan', cmd('assess-plan', `--level task${scope} --out ${shq(planFile)}`))
if (!planned) return fail('the assessment plan could not be computed; nothing was written')
const plan = planned.summary || {}
const contexted = await runStep(
  'assess-context',
  cmd('assess-context', `${scope.trim()} --dir ${shq(contextDir)} --out ${shq(contextFile)}`)
)
if (!contexted) return fail('the assessment context could not be written; nothing was written', { plan })
const context = contexted.summary || {}

// ── Assess ───────────────────────────────────────────────────────────────────────
enter('Assess')
const edgesFile = file('edges.json')
const reasoningFile = file('reasoning.md')
const ASSESS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['edgesPath', 'edgeCount', 'valid', 'relatedRead'],
  properties: {
    edgesPath: { type: 'string' },
    reasoningPath: { type: 'string' },
    edgeCount: { type: 'integer' },
    valid: { type: 'boolean' },
    relatedRead: { type: 'array', maxItems: 40, items: { type: 'string' } },
    unsure: { type: 'array', maxItems: 20, items: { type: 'string' } },
  },
}
const THE_TEST = `THE TEST. An edge from A to B says B cannot be built until A is built, because B consumes something A provides — an API, an event contract, a table, an IAM grant, a deployed resource. Sharing a domain, a vocabulary, a repository or an Epic is not an edge. Both ends are Tasks: no end is a Story or an Epic. When in doubt an edge is left out, because a false edge serializes work that could run in parallel.`
const assessPrompt = `Assess the build dependencies of ONE Task, ${target}, which was created outside elaboration. ${target} is new or has changed.

THE FILES.
- ${target}: ${taskFile}
- The context: ${contextFile}. \`standing\` lists every edge between ${target} and another open Task, in either direction, as {from, to, type, owned, reason, confidence, setBy, setAt}; \`from\` is the Task built first. \`reason\` is the one recorded when the edge was set, or null.
- The corpus: ${corpusDir}, one file per open Task, named <id>.md.
- The index: ${indexFile}, one line per open Task with its title, Epic, repository, status and file.

${THE_TEST}

Work in this order:
1. Read ${target}.
2. Name what it consumes and what it provides.
3. Search the corpus with Grep, and the index, for the Tasks that provide what ${target} consumes or consume what it provides. Read no Task the search did not find related.
4. Read in full every related Task, and the Task at the other end of every standing edge.
5. Apply the test in both directions: an edge from another Task to ${target} where ${target} consumes what that Task provides, and an edge from ${target} to another Task where that Task consumes what ${target} provides.
6. Write ${edgesFile} as {"edges": [{"from", "to", "reason", "confidence"}], "withdrawn": [{"from", "to", "reason"}]}. \`edges\` holds EVERY edge to or from ${target} that passes the test — a standing one it keeps included — and no edge that does not touch ${target}. \`withdrawn\` holds every standing edge with \`owned: true\` that is not in \`edges\`, with a reason that answers the reason recorded for it. Every reason names the artifact and which Task provides it; \`confidence\` is \`high\`, \`medium\` or \`low\`. A standing edge with \`owned: false\` was made by hand: leave it out of both lists. No edge is a valid result. Write the reasoning, per edge and per withdrawal, to ${reasoningFile}.
7. Validate: \`${cmd('validate', `--edges ${shq(edgesFile)}${scope}`)}\` — fix the file until \`ok\` is true. It refuses an edge that does not touch ${target}, an edge whose ends are not both open Tasks, a missing reason, an owned standing edge left unaccounted, a withdrawal of an edge that is not an owned standing edge, and a cycle against every other Task edge. A cycle you cannot remove by dropping one of your own edges that fails the test is reported, not forced: return \`valid: false\` and name the cycle in \`unsure\`.

Return the edge file path, the reasoning file path, the edge count, whether the final validation passed, \`relatedRead\` — the id of every Task you read in full, other than ${target} — and each edge you were unsure of with what would settle it.`

// Code validates every attempt, whatever the session claims. A proposal that does not
// validate is assessed again with the validator's findings, at most ASSESS_ATTEMPTS
// sessions in all; one that never validates writes nothing, and the run stops naming the
// Task and each finding.
// TWO, not three. Step 7 of the brief already has the mapper run the validator itself
// and fix the file until `ok` is true, so this outer loop is a SECOND loop around a
// session that already self-corrects — and each extra turn costs a mapper session plus a
// runner session. One outer correction pass catches the case the session got wrong; a
// third attempt at the same proposal, with the same findings, is where the sibling
// dependency-assessment mini spends nothing at all, because it keeps the loop in-session.
const ASSESS_ATTEMPTS = 2
const FINDING_KEYS = [
  'badScope',
  'outsideScope',
  'missingReason',
  'unaccounted',
  'withdrawnNotOwned',
  'keptAndWithdrawn',
  'notTaskToTask',
  'cycle',
  'dangling',
  'selfEdges',
  'ontoClosed',
  'fromClosed',
  'duplicates',
]
function findingsOf(report) {
  const found = {}
  for (const key of FINDING_KEYS) {
    const v = report ? report[key] : null
    if ((typeof v === 'string' && v) || (Array.isArray(v) && v.length)) found[key] = v
  }
  return found
}
const validationFile = (n) => file(`validation-${n}.json`)
let assessed = null
let settled = false
let attempts = 0
let findings = {}
for (let attempt = 1; attempt <= ASSESS_ATTEMPTS; attempt++) {
  attempts = attempt
  const prompt =
    attempt === 1
      ? assessPrompt
      : `${assessPrompt}

Attempt ${attempt - 1} did not validate. The validator's findings, verbatim: ${JSON.stringify(findings)}. The full report is ${validationFile(attempt - 1)}. Revise ${edgesFile} until every finding is gone, keeping to THE TEST: an edge that fails the test is dropped, never kept to satisfy the validator; an owned standing edge you drop goes in \`withdrawn\` with a reason; a cycle through an edge with \`owned: false\` is not yours to remove — name it in \`unsure\`.`
  const session = await settleAgent(prompt, {
    label: `task-dependency-mapper:${target}#${attempt}`,
    phase: 'Assess',
    // A maker: it proposes the edge set. Stated here rather than inherited.
    effort: 'medium',
    agentType: 'agent-teams-workforce:task-dependency-mapper',
    schema: ASSESS_SCHEMA,
  })
  if (!session) break
  assessed = session
  // Printed without --out, so the whole report comes back.
  const report = await runStep(
    `validate#${attempt}`,
    `set -o pipefail; ${cmd('validate', `--edges ${shq(edgesFile)}${scope}`)} | tee ${shq(validationFile(attempt))}`
  )
  if (!report) break
  if (report.ok === true) {
    settled = true
    findings = {}
    break
  }
  findings = findingsOf(report)
}
const stopped = !settled && !!assessed && attempts === ASSESS_ATTEMPTS && failures.length === 0
const stop = stopped
  ? {
      task: target,
      attempts,
      findings,
      edgesFile,
      validationFile: validationFile(attempts),
      reasoning: reasoningFile,
    }
  : null
const stopMessage = stop
  ? `${target}: its edge proposal did not validate after ${ASSESS_ATTEMPTS} assessments — ${Object.entries(findings)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
      .join('; ')}`
  : null
if (stopMessage) log(stopMessage)

// ── Apply ────────────────────────────────────────────────────────────────────────
enter('Apply')
let edges
if (settled && !applies) {
  // The dry run prints its full result, which is also kept in the run directory: the
  // diff is the deliverable, so it comes back whole rather than as counts.
  const diffFile = file('apply-edges-dry-run.json')
  const proposed = await runStep(
    'apply-edges --dry-run',
    `set -o pipefail; ${cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)}${scope} --dry-run`)} | tee ${shq(diffFile)}`
  )
  const diff = (proposed && proposed.plan) || {}
  edges = proposed
    ? {
        applied: false,
        proposed: proposed.validation ? proposed.validation.ok === true : false,
        scope: proposed.scope || target,
        added: diff.add || [],
        converted: diff.convert || [],
        removed: diff.remove || [],
        withdrawn: proposed.withdrawn || [],
        unchanged: diff.unchanged ?? null,
        protectedHandMadeEdges: diff.protectedHandMadeEdges || [],
        planned: proposed.planned || [],
        validation: proposed.validation || null,
        diffFile,
        edgesFile,
        reasoning: reasoningFile,
        unsure: assessed.unsure || [],
      }
    : { applied: false, proposed: false, reason: 'the dry run did not complete; nothing was written' }
} else if (settled) {
  // The full result is printed and kept in the run directory, so the withdrawals come back
  // with their reasons.
  const applyFile = file('apply-edges.json')
  const applied = await runStep(
    'apply-edges',
    `set -o pipefail; ${cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)}${scope}`)} | tee ${shq(applyFile)}`
  )
  edges = {
    ...(applied ? applied.summary || {} : { applied: false }),
    withdrawn: (applied && applied.withdrawn) || [],
    resultFile: applyFile,
    edgesFile,
    reasoning: reasoningFile,
    unsure: assessed.unsure || [],
  }
} else {
  edges = {
    applied: false,
    reason: stop
      ? `the proposed edge set did not validate after ${ASSESS_ATTEMPTS} assessments; the tracker keeps its current edges`
      : assessed
        ? 'the proposed edge set could not be validated; the tracker keeps its current edges'
        : 'the task-dependency-mapper returned no result; the tracker keeps its current edges',
    edgesFile,
    reasoning: reasoningFile,
    unsure: (assessed && assessed.unsure) || [],
  }
}
if (edges.proposed) log(`Proposed edges (${target}): ${edges.added.length} to add, ${edges.converted.length} to convert, ${edges.removed.length} to withdraw, ${edges.unchanged} unchanged — nothing written; detail in ${edges.diffFile}`)
if (edges.applied) log(`Edges (${target}): ${edges.added} added, ${edges.converted} converted, ${edges.removed} withdrawn, ${edges.unchanged} unchanged`)

// ── Score ────────────────────────────────────────────────────────────────────────
//
// Edges decide Task RR-OE, so an applied assessment is followed by scoring. Scoring never
// assesses.
let scoring = null
const scores = applies && edges.applied === true && a.score !== false
if (scores) {
  enter('Score')
  scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
}

return {
  ok: settled && (applies ? edges.applied === true : edges.proposed === true) && failures.length === 0 && (!scores || (!!scoring && scoring.ok === true)),
  apply: applies,
  settled,
  attempts,
  workDir: work,
  task: target,
  plan,
  context,
  assessment: assessed || { failed: true },
  edges,
  scoring,
  stop,
  ...(stop ? { error: stopMessage, headline: stopMessage } : {}),
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
