export const meta = {
  name: 'dependency-assessment',
  description:
    "Assesses the architecture dependencies of ONE new or changed Epic, and writes edges and nothing else. An Epic is a PRD, a business requirement, and an Epic edge is an architecture dependency: a judgment about the order in which architecture is established, made before that architecture exists. It exists where an architecture decision one Epic rests on should be designed from another Epic's requirements first, and the SAD does not already settle that decision. It is stored as a beads `tracks` edge that orders elaboration and never holds work out of `bd ready`. One epic-sequencer session reads the Epic's full PRD, names the architecture decisions its requirements drive and the ones it rests on, drops those the SAD settles, searches the other Epics' PRDs for the requirements that drive or rest on each remaining decision, reads those PRDs in full, and applies the edge test in both directions. It proposes every edge to or from the Epic with a reason, and keeps or withdraws, with a reason, every owned edge standing on it. Code refuses an edge that does not touch the Epic, a cycle, an unaccounted standing edge and a missing reason, confines the write to that Epic's edges, and never touches a hand-made edge. When the edges are applied it triggers wsjf-scoring, because edges decide RR-OE. With `apply: false` it proposes only: it computes the edge diff as a dry run, returns it, writes nothing to the tracker and triggers no scoring.",
  whenToUse: 'A new or changed Epic needs its architecture dependencies assessed.',
  phases: [
    { title: 'Context', detail: "the Epic's fingerprint, its standing edges, and the PRD corpus with its index" },
    { title: 'Assess', detail: "the epic-sequencer proposes every edge to or from the Epic and accounts for every owned standing edge" },
    { title: 'Apply', detail: "validate and apply the edge diff for the Epic, or compute it as a dry run" },
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
//   repoPath:     string,   // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,   // absolute path of this plugin's root
//   workDir:      string,   // absolute path of a directory for this run's files; one per run
//   epic:         string,   // the one Epic assessed
//   sadPath?:     string,   // the arc42 SAD (ATW_SAD_PATH): the decisions it settles need no edge
//   projectRoot?: string,   // the project root (ATW_PROJECT_ROOT), passed to the scoring it triggers
//   score?:       boolean,  // false: do not trigger scoring when the edges are applied. Default true.
//   apply?:       boolean,  // false: propose only — no edge, reason or score is written; `edges`
//                           // carries the diff (added, converted, removed, withdrawn, unchanged,
//                           // planned) computed as a dry run. Default true.
// }
//
// Returns: { ok, apply, workDir, epic, plan, context, assessment, edges, scoring,
//            failures, dispatchFailed, dispatchFailures }
// With `apply: false`, `scoring` is null and `ok` means the diff was proposed.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
if (Object.prototype.hasOwnProperty.call(a, 'mode')) {
  return { ok: false, error: '`mode` is not an argument: dependency assessment covers exactly one Epic' }
}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
const target = a.epic
if (!(typeof target === 'string' && /^[A-Za-z0-9._-]+$/.test(target))) {
  return { ok: false, error: '`epic`, the id of the one Epic to assess, is required' }
}
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const scope = ` --epic ${shq(target)}`
const applies = a.apply !== false
const project = { repoPath: repo, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }
const fail = (error, extra) => ({
  ok: false,
  apply: applies,
  workDir: work,
  epic: target,
  error,
  ...(extra || {}),
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
})

// ── Context ──────────────────────────────────────────────────────────────────────
//
// The plan records the fingerprint the Epic is assessed at. The context writes every open
// Epic's PRD to the corpus directory and an index of their titles and section headings, and
// lists every edge standing between this Epic and another open Epic, with the reason
// recorded for each owned one.
enter('Context')
const planFile = file('assess-plan.json')
const contextDir = file('context')
const contextFile = file('context.json')
const corpusDir = `${contextDir}/prd`
const indexFile = `${contextDir}/index.md`
const epicPrd = `${corpusDir}/${target}.md`
const planned = await runStep('assess-plan', cmd('assess-plan', `${scope.trim()} --out ${shq(planFile)}`))
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
    relatedRead: { type: 'array', items: { type: 'string' } },
    unsure: { type: 'array', items: { type: 'string' } },
  },
}
const THE_TEST = `THE TEST. An Epic is a PRD, a WHAT; its architecture does not exist yet. An edge from A to B says: an architecture decision B rests on should be designed from A's requirements first, because A's requirements are the fuller statement of what that decision must serve — sign-up and sign-in requirements drive the identity architecture, so password reset waits, or identity gets designed from a recovery flow's requirements alone. A reason that says something must exist, be built, be deployed or be testable first, that B presumes a user or a record exists, or that B reads data from or calls a capability of A, is a build dependency between Tasks and is never an Epic edge. ${a.sadPath ? `The SAD is ${a.sadPath}: a` : 'A'} decision the SAD already settles needs no edge; check it before drawing one.`
const assessPrompt = `Assess the architecture dependencies of ONE Epic, ${target}, following \`agent-teams-workforce:epic-sequencing\` for the edge test and its worked example. ${target} is new or has changed.

THE FILES.
- ${target}'s full PRD: ${epicPrd}
- The context: ${contextFile}. \`standing\` lists every edge between ${target} and another open Epic, in either direction, as {from, to, type, owned, reason, confidence, setBy, setAt}; \`from\` is the Epic designed first. \`reason\` is the one recorded when the edge was set, or null.
- The PRD corpus: ${corpusDir}, one file per open Epic, named <id>.md.
- The index: ${indexFile}, one line per open Epic with its title, elaboration state, PRD path and section headings.
${a.sadPath ? `- The SAD: ${a.sadPath}\n` : ''}
${THE_TEST}

Work in this order:
1. Read ${target}'s full PRD.
2. Name the architecture decisions its requirements should drive, and the architecture decisions it rests on.
3. Check each against the SAD, and drop every decision the SAD already settles.
4. For each remaining decision, search the corpus with Grep, and the index for titles and sections, for the PRDs whose requirements drive or rest on it. Read no PRD the search did not find related.
5. Read in full every related PRD, and the PRD at the other end of every standing edge.
6. Apply the test in both directions: an edge from another Epic to ${target} where the architecture ${target} rests on should be designed from that Epic's requirements first, and an edge from ${target} to another Epic where that Epic's architecture should be designed from ${target}'s requirements first.
7. Write ${edgesFile} as {"edges": [{"from", "to", "reason", "confidence"}], "withdrawn": [{"from", "to", "reason"}]}. \`edges\` holds EVERY edge to or from ${target} that passes the test — a standing one it keeps included — and no edge that does not touch ${target}. \`withdrawn\` holds every standing edge with \`owned: true\` that is not in \`edges\`, with a reason that answers the reason recorded for it. Every reason names the architecture decision and whose requirements should drive it; \`confidence\` is \`high\`, \`medium\` or \`low\`. A standing edge with \`owned: false\` was made by hand: leave it out of both lists. Write the reasoning, per edge and per withdrawal, to ${reasoningFile}.
8. Validate: \`${cmd('validate', `--edges ${shq(edgesFile)}${scope}`)}\` — fix the file until \`ok\` is true. It refuses an edge that does not touch ${target}, a missing reason, an owned standing edge left unaccounted, a withdrawal of an edge that is not an owned standing edge, and a cycle against every other Epic edge. A cycle you cannot remove by dropping one of your own edges that fails the test is reported, not forced: return \`valid: false\` and name the cycle in \`unsure\`.

Return the edge file path, the reasoning file path, the edge count, whether the final validation passed, \`relatedRead\` — the id of every Epic whose PRD you read in full, other than ${target} — and each edge you were unsure of with what would settle it.`
const assessed = await settleAgent(assessPrompt, {
  label: `epic-sequencer:${target}`,
  phase: 'Assess',
  agentType: 'agent-teams-workforce:epic-sequencer',
  schema: ASSESS_SCHEMA,
})

// ── Apply ────────────────────────────────────────────────────────────────────────
enter('Apply')
let edges
if (assessed && assessed.valid && !applies) {
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
} else if (assessed && assessed.valid) {
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
    reason: assessed
      ? 'the proposed edge set did not validate; the tracker keeps its current edges'
      : 'the epic-sequencer returned no result; the tracker keeps its current edges',
    edgesFile,
    reasoning: reasoningFile,
    unsure: (assessed && assessed.unsure) || [],
  }
}
if (edges.proposed) log(`Proposed edges (${target}): ${edges.added.length} to add, ${edges.converted.length} to convert, ${edges.removed.length} to withdraw, ${edges.unchanged} unchanged — nothing written; detail in ${edges.diffFile}`)
if (edges.applied) log(`Edges (${target}): ${edges.added} added, ${edges.converted} converted, ${edges.removed} withdrawn, ${edges.unchanged} unchanged`)

// ── Score ────────────────────────────────────────────────────────────────────────
//
// Edges decide RR-OE, so an applied assessment is followed by scoring. Scoring never
// assesses.
let scoring = null
const scores = applies && edges.applied === true && a.score !== false
if (scores) {
  enter('Score')
  scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
}

return {
  ok: (applies ? edges.applied === true : edges.proposed === true) && failures.length === 0 && (!scores || (!!scoring && scoring.ok === true)),
  apply: applies,
  workDir: work,
  epic: target,
  plan,
  context,
  assessment: assessed || { failed: true },
  edges,
  scoring,
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
