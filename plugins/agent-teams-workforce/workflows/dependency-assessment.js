export const meta = {
  name: 'dependency-assessment',
  description:
    "Assesses the Epic dependency edges, and writes edges and nothing else. An edge exists where one Epic's architecture must be designed from another Epic's requirements first, stored as a beads `tracks` edge that orders elaboration and never holds work out of `bd ready`. Mode `epic` assesses ONE new or changed Epic against the portfolio's summaries and its own full PRD, and may add or withdraw only edges to or from that Epic — validation refuses any other edge, and the write is confined to that Epic's edges in code. Mode `portfolio` assesses the whole portfolio from the summaries. The epic-sequencer proposes; code validates and applies the diff, never touching a hand-made edge. When the edges are applied it triggers wsjf-scoring, because edges decide RR-OE.",
  whenToUse: "A new or changed Epic needs its dependencies assessed (mode epic), or the whole portfolio is being re-seeded (mode portfolio).",
  phases: [
    { title: "Summaries", detail: "bring the Epic summaries current" },
    { title: "Plan", detail: "fingerprints and the rendered portfolio" },
    { title: "Assess", detail: "the epic-sequencer proposes the edge set for the scope" },
    { title: "Apply", detail: "validate and apply the edge diff for the scope" },
    { title: "Score", detail: "wsjf-scoring over the new edges" },
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
//   repoPath:     string,              // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,              // absolute path of this plugin's root
//   workDir:      string,              // absolute path of a directory for this run's files; one per run
//   mode:         'epic'|'portfolio',  // one Epic against the portfolio, or the whole portfolio
//   epic?:        string,              // the Epic assessed, in mode 'epic'
//   sadPath?:     string,              // the arc42 SAD (ATW_SAD_PATH), passed to the summaries it brings current
//   projectRoot?: string,              // the project root (ATW_PROJECT_ROOT), likewise
//   score?:       boolean,             // false: do not trigger scoring when the edges are applied
// }
//
// Returns: { ok, workDir, mode, epic, summaries, plan, assessment, edges, scoring,
//            failures, dispatchFailed, dispatchFailures }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const isAbs = (p) => typeof p === 'string' && p.startsWith('/') && !/[\n\r\0]/.test(p)
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const missingArgs = ['repoPath', 'pluginRoot', 'workDir'].filter((k) => !isAbs(a[k]))
if (missingArgs.length) {
  return { ok: false, error: `required absolute path argument(s) missing: ${missingArgs.join(', ')}` }
}
const mode = a.mode
if (mode !== 'epic' && mode !== 'portfolio') {
  return { ok: false, error: "`mode` must be 'epic' or 'portfolio'" }
}
const target = mode === 'epic' ? a.epic : null
if (mode === 'epic' && !(typeof target === 'string' && /^[A-Za-z0-9._-]+$/.test(target))) {
  return { ok: false, error: "mode 'epic' needs `epic`, the id of the Epic to assess" }
}
const repo = a.repoPath.replace(/\/+$/, '')
const work = a.workDir.replace(/\/+$/, '')
const DS = `${a.pluginRoot.replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const scope = target ? ` --epic ${shq(target)}` : ''
const project = { repoPath: repo, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }
const fail = (error, extra) => ({
  ok: false,
  workDir: work,
  mode,
  epic: target,
  error,
  ...(extra || {}),
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
})

// ── Summaries ────────────────────────────────────────────────────────────────────
//
// The assessment reads the portfolio through the Epic summaries, so they are brought
// current first. An Epic left without one is read from its PRD instead.
enter('Summaries')
const summaries = await workflow('agent-teams-workforce:epic-summaries', { ...project, workDir: file('summaries') })

// ── Plan ─────────────────────────────────────────────────────────────────────────
enter('Plan')
const planFile = file('assess-plan.json')
const portfolioFile = file('portfolio.md')
const planned = await runStep('assess-plan', cmd('assess-plan', `${scope.trim()} --out ${shq(planFile)}`.trim()))
if (!planned) return fail('the assessment plan could not be computed; nothing was written', { summaries })
const plan = planned.summary || {}
const rendered = await runStep('portfolio', cmd('portfolio', `--markdown ${shq(portfolioFile)} --prd-dir ${shq(file('prd'))}`))
if (!rendered) return fail('the portfolio could not be rendered; nothing was written', { summaries, plan })

// ── Assess ───────────────────────────────────────────────────────────────────────
enter('Assess')
const edgesFile = file('edges.json')
const tieringFile = file('tiering.md')
const ASSESS_SCHEMA = {
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
const READING = `THE PORTFOLIO is ${portfolioFile}: every open Epic with its elaboration state, the Epics it depends on now, the file holding its full PRD, and its stored summary — what it needs and establishes architecturally, its value and urgency, and what already exists for it. Read it in full; it is long, so read it in consecutive chunks until the end. An Epic marked "Summary unavailable" is read from its PRD file instead. Open any other Epic's PRD only where its summary cannot settle whether an edge passes the test.`
const assessPrompt = target
  ? `Assess ONE Epic, ${target}, against the whole open Epic portfolio, following \`agent-teams-workforce:epic-sequencing\`. ${target} is new or has changed; every other Epic's edges stand.

${READING}

1. Read ${target}'s full PRD, at the path the portfolio names for it.
2. Read the portfolio as above.
3. Apply the edge test in both directions: every Epic whose requirements ${target}'s architecture must be designed from (an edge from that Epic to ${target}), and every Epic whose architecture must be designed from ${target}'s requirements (an edge from ${target} to that Epic).
4. Write ${edgesFile} holding EVERY edge to or from ${target} — the ones that stand today and pass the test included — and no edge that does not touch ${target}. An edge to or from ${target} that stands today and is not in the file is withdrawn. Write the reasoning, per edge, to ${tieringFile}.
5. Validate: \`${cmd('validate', `--edges ${shq(edgesFile)} --epic ${shq(target)}`)}\` — fix the file until \`ok\` is true. It refuses any edge that does not touch ${target}, and checks for cycles against every other Epic edge.

Return the edge file path, the edge count, whether the final validation passed, and each edge you were unsure of with what would settle it.`
  : `Order the whole open Epic portfolio and emit its dependency edge set, following \`agent-teams-workforce:epic-sequencing\`.

${READING}

1. Read the portfolio as above, and work outside-in: tiers, subdomains, then edges, revisiting.
2. Write the edge file, over the WHOLE portfolio, to ${edgesFile}, and the tiering account to ${tieringFile}.
3. Validate: \`${cmd('validate', `--edges ${shq(edgesFile)}`)}\` — fix the file until \`ok\` is true.

Return the edge file path, the edge count, whether the final validation passed, and each edge you were unsure of with what would settle it.`
const assessed = await settleAgent(assessPrompt, {
  label: target ? `epic-sequencer:${target}` : 'epic-sequencer',
  phase: 'Assess',
  agentType: 'agent-teams-workforce:epic-sequencer',
  schema: ASSESS_SCHEMA,
})

// ── Apply ────────────────────────────────────────────────────────────────────────
enter('Apply')
let edges
if (assessed && assessed.valid) {
  const applied = await runStep(
    'apply-edges',
    cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)}${scope} --out ${shq(file('apply-edges.json'))}`)
  )
  edges = { ...(applied ? applied.summary || {} : { applied: false }), tiering: tieringFile, unsure: assessed.unsure || [] }
} else {
  edges = {
    applied: false,
    reason: assessed ? 'the proposed edge set did not validate; the tracker keeps its current edges' : 'the epic-sequencer returned no result; the tracker keeps its current edges',
  }
}
if (edges.applied) log(`Edges (${target || 'portfolio'}): ${edges.added} added, ${edges.converted} converted, ${edges.removed} withdrawn, ${edges.unchanged} unchanged`)

// ── Score ────────────────────────────────────────────────────────────────────────
//
// Edges decide RR-OE, so an applied assessment is followed by scoring. Scoring never
// assesses.
let scoring = null
const scores = edges.applied === true && a.score !== false
if (scores) {
  enter('Score')
  scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
}

return {
  ok: edges.applied === true && failures.length === 0 && (!scores || (!!scoring && scoring.ok === true)),
  workDir: work,
  mode,
  epic: target,
  summaries,
  plan,
  assessment: assessed || { failed: true },
  edges,
  scoring,
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
