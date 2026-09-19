export const meta = {
  name: 'dependency-assessment',
  description:
    "Assesses the architecture dependencies of ONE new or changed Epic, and writes edges and nothing else. An Epic is a PRD, a business requirement, and an Epic edge is an architecture dependency: a judgment about the order in which architecture is established, made before that architecture exists. It exists where an architecture decision one Epic rests on should be designed from another Epic's requirements first, and the SAD does not already settle that decision. It is stored as a beads `tracks` edge that orders elaboration and never holds work out of `bd ready`. ONE epic-sequencer session does the whole assessment: it runs the commands that write the Epic's context, reads the Epic's full PRD, names the architecture decisions its requirements drive and the ones it rests on, drops those the SAD settles, searches the other Epics' PRDs for the requirements that drive or rest on each remaining decision, reads those PRDs in full, applies the edge test in both directions, validates its proposal until the validator passes, and runs apply-edges. apply-edges validates the proposal again and writes nothing unless it passes: it refuses an edge that does not touch the Epic, a cycle, an unaccounted standing edge and a missing reason, confines the write to that Epic's edges, and never touches a hand-made edge. A proposal the session cannot make valid is not applied, and the run stops, naming the Epic and the findings. When the edges are applied it triggers wsjf-scoring, because edges decide RR-OE. With `apply: false` it proposes only: apply-edges computes the edge diff as a dry run, nothing is written and no scoring runs.",
  whenToUse: 'A new or changed Epic needs its architecture dependencies assessed.',
  phases: [
    { title: 'Assess', detail: 'one epic-sequencer session writes the context, proposes and validates the edges, and runs apply-edges' },
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

function enter(title) {
  phase(title)
}

// args: {
//   repoPath:     string,   // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,   // absolute path of this plugin's root
//   workDir:      string,   // absolute path of a directory for this run's files; one per run
//   epic:         string,   // the one Epic assessed
//   sadPath?:     string,   // the arc42 SAD (ATW_SAD_PATH): the decisions it settles need no edge
//   projectRoot?: string,   // the project root (ATW_PROJECT_ROOT), passed to the scoring it triggers
//   contextDir?:  string,   // where the PRD corpus and index live; default <workDir>/context.
//                           // seed-portfolio passes one directory for the whole seeding.
//   corpusReady?: boolean,  // the corpus in contextDir is already written; read it, do not rewrite it
//   score?:       boolean,  // false: do not trigger scoring when the edges are applied. Default true.
//   apply?:       boolean,  // false: propose only — apply-edges runs as a dry run and nothing is
//                           // written. Default true.
// }
//
// Returns: { ok, apply, settled, workDir, epic, assessment, edges, scoring, stop, error?,
//            headline?, dispatchFailed, dispatchFailures }
//   settled:    the proposal validated and apply-edges accepted it
//   assessment: the session's result
//   edges:      apply-edges' summary as the session reported it, with the files holding every
//               edge with its reason and the full applied or proposed diff
//   stop:       null, or { epic, findings, edgesFile, validationFile, reasoning } when the
//               proposal did not validate; `error` and `headline` then name the Epic
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
if (Object.prototype.hasOwnProperty.call(a, 'mode')) {
  return { ok: false, settled: false, error: '`mode` is not an argument: dependency assessment covers exactly one Epic' }
}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (a.contextDir !== undefined && !isAbs(a.contextDir)) missingArgs.push('contextDir')
if (missingArgs.length) {
  return { ok: false, settled: false, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
const target = a.epic
if (!(typeof target === 'string' && /^[A-Za-z0-9._-]+$/.test(target))) {
  return { ok: false, settled: false, error: '`epic`, the id of the one Epic to assess, is required' }
}
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const scope = `--epic ${shq(target)}`
const applies = a.apply !== false
const project = { repoPath: repo, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }

const planFile = file('assess-plan.json')
const contextDir = (a.contextDir || file('context')).replace(/\/+$/, '')
const contextFile = file('context.json')
const corpusDir = `${contextDir}/prd`
const indexFile = `${contextDir}/index.md`
const epicPrd = `${corpusDir}/${target}.md`
const edgesFile = file('edges.json')
const reasoningFile = file('reasoning.md')
const validationFile = file('validation.json')
const applyFile = file(applies ? 'apply-edges.json' : 'apply-edges-dry-run.json')

// ── Assess ───────────────────────────────────────────────────────────────────────
//
// One session. It runs the deterministic commands itself, because a workflow has no shell
// and a session per command cost more than half of every assessment. Nothing it claims is
// trusted for the write: apply-edges validates the proposal again and writes nothing unless
// it passes, and it stamps the fingerprint from the plan the session read.
enter('Assess')
const ASSESS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['edgesPath', 'edgeCount', 'valid', 'relatedRead', 'applyExitCode', 'applySummary'],
  properties: {
    edgesPath: { type: 'string' },
    reasoningPath: { type: 'string' },
    edgeCount: { type: 'integer' },
    valid: { type: 'boolean' },
    findings: { type: 'object' },
    relatedRead: { type: 'array', items: { type: 'string' } },
    unsure: { type: 'array', items: { type: 'string' } },
    applyExitCode: { type: 'integer' },
    applySummary: { type: 'object' },
    error: { type: 'string' },
  },
}
const THE_TEST = `THE TEST. An Epic is a PRD, a WHAT; its architecture does not exist yet. An edge from A to B says: an architecture decision B rests on should be designed from A's requirements first, because A's requirements are the fuller statement of what that decision must serve — sign-up and sign-in requirements drive the identity architecture, so password reset waits, or identity gets designed from a recovery flow's requirements alone. A reason that says something must exist, be built, be deployed or be testable first, that B presumes a user or a record exists, or that B reads data from or calls a capability of A, is a build dependency between Tasks and is never an Epic edge. ${a.sadPath ? `The SAD is ${a.sadPath}: a` : 'A'} decision the SAD already settles needs no edge; check it before drawing one.`
const applyCmd = `set -o pipefail; ${cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)} ${scope}${applies ? '' : ' --dry-run'}`)} | tee ${shq(applyFile)}`
const assessPrompt = `Assess the architecture dependencies of ONE Epic, ${target}, following \`agent-teams-workforce:epic-sequencing\` for the edge test and its worked example. ${target} is new or has changed.

${THE_TEST}

Work in this order:
1. Run these two commands, once each. Each prints one JSON object; if either exits non-zero, stop, set \`valid\` false, \`applyExitCode\` -1, \`applySummary\` {}, and put its output in \`error\`.
   ${cmd('assess-plan', `${scope} --out ${shq(planFile)}`)}
   ${cmd('assess-context', `${scope} --dir ${shq(contextDir)}${a.corpusReady ? ' --corpus-ready' : ''} --out ${shq(contextFile)}`)}
   They write: ${target}'s full PRD at ${epicPrd}; the PRD corpus at ${corpusDir}, one file per open Epic named <id>.md; the index at ${indexFile}, one line per open Epic with its title, elaboration state, PRD path and section headings; and ${contextFile}, whose \`standing\` lists every edge between ${target} and another open Epic, in either direction, as {from, to, type, owned, reason, confidence, setBy, setAt} — \`from\` is the Epic designed first, \`reason\` the one recorded when the edge was set, or null.${a.sadPath ? `\n   The SAD: ${a.sadPath}` : ''}
2. Read ${target}'s full PRD.
3. Name the architecture decisions its requirements should drive, and the architecture decisions it rests on.
4. Check each against the SAD, and drop every decision the SAD already settles.
5. For each remaining decision, search the corpus with Grep, and the index for titles and sections, for the PRDs whose requirements drive or rest on it. Read no PRD the search did not find related.
6. Read in full every related PRD, and the PRD at the other end of every standing edge.
7. Apply the test in both directions: an edge from another Epic to ${target} where the architecture ${target} rests on should be designed from that Epic's requirements first, and an edge from ${target} to another Epic where that Epic's architecture should be designed from ${target}'s requirements first.
8. Write ${edgesFile} as {"edges": [{"from", "to", "reason", "confidence"}], "withdrawn": [{"from", "to", "reason"}]}. \`edges\` holds EVERY edge to or from ${target} that passes the test — a standing one it keeps included — and no edge that does not touch ${target}. \`withdrawn\` holds every standing edge with \`owned: true\` that is not in \`edges\`, with a reason that answers the reason recorded for it. Every reason names the architecture decision and whose requirements should drive it; \`confidence\` is \`high\`, \`medium\` or \`low\`. A standing edge with \`owned: false\` was made by hand: leave it out of both lists. Write the reasoning, per edge and per withdrawal, to ${reasoningFile}.
9. Validate: \`set -o pipefail; ${cmd('validate', `--edges ${shq(edgesFile)} ${scope}`)} | tee ${shq(validationFile)}\` — revise the file until \`ok\` is true, keeping to THE TEST: an edge that fails the test is dropped, never kept to satisfy the validator. It refuses an edge that does not touch ${target}, a missing reason, an owned standing edge left unaccounted, a withdrawal of an edge that is not an owned standing edge, and a cycle against every other Epic edge. A cycle you cannot remove by dropping one of your own edges that fails the test — one through an edge with \`owned: false\` — is reported, not forced: set \`valid\` false, put the validator's findings in \`findings\`, name the cycle in \`unsure\`, and do not run step 10 (\`applyExitCode\` -1, \`applySummary\` {}).
10. Only once validation passes, run exactly this, once: \`${applyCmd}\`. Return its exit code as \`applyExitCode\` and the \`summary\` object it printed, unaltered, as \`applySummary\`. Do not retry it or repair anything it refuses.

Return the edge file path, the reasoning file path, the edge count, whether the final validation passed, \`relatedRead\` — the id of every Epic whose PRD you read in full, other than ${target} — each edge you were unsure of with what would settle it, and the apply-edges result.`

const assessed = await settleAgent(assessPrompt, {
  label: `epic-sequencer:${target}`,
  phase: 'Assess',
  agentType: 'agent-teams-workforce:epic-sequencer',
  schema: ASSESS_SCHEMA,
})
const summary = (assessed && assessed.applySummary) || {}
const accepted = !!assessed && assessed.valid === true && assessed.applyExitCode === 0 && !summary.validation
const settled = accepted && (applies ? summary.applied === true : summary.dryRun === true || summary.applied === false)
const stop = assessed && assessed.valid === false
  ? { epic: target, findings: assessed.findings || {}, edgesFile, validationFile, reasoning: reasoningFile }
  : null
const stopMessage = stop
  ? `${target}: its edge proposal did not validate — ${Object.entries(stop.findings)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : typeof v === 'string' ? v : JSON.stringify(v)}`)
      .join('; ') || (assessed.unsure || []).join('; ') || 'see the validation file'}`
  : null
if (stopMessage) log(stopMessage)
const edges = {
  ...summary,
  applied: applies && summary.applied === true,
  proposed: !applies && accepted,
  resultFile: applyFile,
  edgesFile,
  reasoning: reasoningFile,
  unsure: (assessed && assessed.unsure) || [],
  ...(settled
    ? {}
    : {
        reason: !assessed
          ? 'the epic-sequencer returned no result; the tracker keeps its current edges'
          : assessed.error
            ? `the context could not be written: ${assessed.error}`
            : stop
              ? 'the proposed edge set did not validate; the tracker keeps its current edges'
              : `apply-edges did not accept the proposal (exit ${assessed.applyExitCode}); the tracker keeps its current edges`,
      }),
}
if (settled) log(`Edges (${target})${applies ? '' : ', proposed'}: ${summary.added} added, ${summary.converted} converted, ${summary.removed} withdrawn, ${summary.unchanged} unchanged`)

// ── Score ────────────────────────────────────────────────────────────────────────
//
// Edges decide RR-OE, so an applied assessment is followed by scoring. Scoring never
// assesses.
let scoring = null
const scores = applies && settled && a.score !== false
if (scores) {
  enter('Score')
  scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
}

return {
  ok: settled && (!scores || (!!scoring && scoring.ok === true)),
  apply: applies,
  settled,
  workDir: work,
  epic: target,
  assessment: assessed || { failed: true },
  edges,
  scoring,
  stop,
  ...(stop ? { error: stopMessage, headline: stopMessage } : !settled ? { error: `${target}: ${edges.reason}` } : {}),
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
