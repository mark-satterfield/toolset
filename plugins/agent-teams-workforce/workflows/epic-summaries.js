export const meta = {
  name: 'epic-summaries',
  description:
    "Leaf mini — keeps a short stored summary on every open Epic, so a session that must hold the whole Epic portfolio reads the summaries and reads in full only the Epics it assesses or judges. An Epic is a PRD, a business requirement, and its summary describes that requirement for two judgments: which requirements each architecture decision should be designed from first, and the Epic's value, urgency and size. It names the architecture decisions the PRD's requirements should drive, the decisions it should be designed on top of, which of those the SAD already settles, and the value and urgency the PRD carries; it designs no solution and invents none. Each summary is stored in the Epic's metadata with the content fingerprint it was written from, and is regenerated only when that fingerprint no longer matches the Epic. Summarizing sessions each read a small batch of PRDs in full, concurrently; the code decides which Epics are due and records the result.",
  whenToUse: "Keeping the Epic summaries current; dependency-assessment and wsjf-scoring run it first.",
  phases: [
    { title: "Plan", detail: "the Epics whose summary is missing or older than their PRD" },
    { title: "Summarize", detail: "batches of PRDs read in full, concurrently" },
    { title: "Record", detail: "each summary with the fingerprint it was written from" },
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
//   repoPath:     string,           // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,           // absolute path of this plugin's root
//   workDir:      string,           // absolute path of a directory for this run's files; one per run
//   sadPath?:     string,           // the arc42 SAD (ATW_SAD_PATH), searched for the decisions it settles
//   epics?:       string[],         // restrict to these Epics; every open Epic when absent
// }
//
// Returns: { ok, workDir, plan, summarized, record, failures, dispatchFailed, dispatchFailures }
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
const only = Array.isArray(a.epics) ? a.epics.filter((e) => typeof e === 'string' && /^[A-Za-z0-9._-]+$/.test(e)) : []

// Epics per summarizing session: enough to amortize a session, few enough that every PRD
// in the batch is read in full.
const BATCH = 6
const SUMMARY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['path', 'summarized'],
  properties: {
    path: { type: 'string' },
    summarized: { type: 'integer' },
    unsummarized: { type: 'array', items: { type: 'string' } },
  },
}

// ── Plan ─────────────────────────────────────────────────────────────────────────
enter('Plan')
const planFile = file('summary-plan.json')
const planned = await runStep(
  'summary-plan',
  cmd('summary-plan', `${only.length ? `--epics ${shq(only.join(','))} ` : ''}--prd-dir ${shq(file('prd'))} --out ${shq(planFile)}`)
)
if (!planned) {
  return { ok: false, workDir: work, error: 'the summary plan could not be computed; nothing was written', failures, dispatchFailed: dispatchDeaths().length > 0, dispatchFailures: dispatchDeaths() }
}
const plan = planned.summary || {}
if (!plan.due) {
  log(`Summaries: all ${plan.openEpics || 0} are current`)
  return { ok: true, workDir: work, plan, summarized: 0, record: null, failures, dispatchFailed: false, dispatchFailures: [] }
}
const due = Array.isArray(plan.epics) ? plan.epics : []
if (due.length !== plan.due) {
  return { ok: false, workDir: work, plan, error: 'the plan names Epics to summarize but did not list them', failures, dispatchFailed: dispatchDeaths().length > 0, dispatchFailures: dispatchDeaths() }
}
log(`Summaries: ${due.length} of ${plan.openEpics} due`)

// ── Summarize ────────────────────────────────────────────────────────────────────
enter('Summarize')
const batches = []
for (let i = 0; i < due.length; i += BATCH) batches.push(due.slice(i, i + BATCH))
const written = []
await parallel(
  batches.map((batch, n) => async () => {
    const out = file(`summaries-${n + 1}.json`)
    const done = await settleAgent(
      `You write the stored summary of each Epic listed below. An Epic is a PRD: a business requirement, a WHAT and not a HOW. Its architecture is not designed yet. Sessions that must hold the whole Epic portfolio read these summaries in place of the PRDs, for two judgments. The first is the order in which architecture is established: which requirements each architecture decision should be designed from first — sign-up and sign-in requirements should drive the identity architecture, so password reset is not elaborated first, or identity gets designed from a recovery flow's requirements alone. The second is the Epic's value, urgency and size. Write for that reader.

Epics (id — title — PRD file):
${batch.map((e) => `- ${e.id} — ${e.title} — ${e.prdPath}`).join('\n')}

Architecture document (arc42 SAD): ${a.sadPath || 'none supplied'}

For each Epic:
1. Read its PRD file in full.
2. Think about what the architecture for these requirements could be — the decisions an architect would have to make — without deciding any of them. Then search the SAD for those decisions: Grep for their key nouns and read only the matching sections. A handful of searches per Epic, not a survey.
3. Write the summary: plain text, 200 to 400 words, under exactly these four headings, each heading at the start of its own line followed by prose:

Drives: the architecture decisions this PRD's requirements should drive — the decisions that ought to be designed from these requirements because they are the fullest statement of what the decision must serve. Name each as the question to be decided ("how a person's professional history is modeled", "how a recurring schedule is represented"), never its answer. Write "none" when every decision its requirements touch is better driven by other requirements.
Designed on: the architecture decisions this PRD should be designed on top of, which other requirements should drive — each named as a decision to be designed from those other requirements, with the concept whose requirements should drive it, never as another Epic's id. Every entry is an architecture dependency. Something having to exist, be built, be deployed, be testable or be available at runtime first, data this PRD reads or writes, and a capability it calls are build facts about Tasks and never appear here. Write "none" when no decision it rests on is driven by other requirements.
Settled: for EVERY decision named under Designed on, one short clause: settled by the SAD, citing the section or file, or open. Then the same for the decisions under Drives. A decision the SAD settles is already established and needs no architecture dependency, so the reader decides edges from this field. Report what is decided, not the design itself: cite the section, and do not restate its content. Write "open" for a decision the searches found nothing on.
Value and urgency: who gains what when the requirement is delivered, what is lost if it never is, and any date, window or commitment that makes delay costly, as the PRD states it; say so when the PRD states no urgency. State value as what people gain or lose, never as other features depending on this requirement or on anything existing first.

Describe the requirement. Do not design a solution, invent one, choose technology, name services, repositories, tables or code, propose an ordering between Epics, or score anything. Do not restate the PRD's section structure or list its rules. Name each concept the way the PRD names it, so two summaries touching the same decision use the same words.

Write ${out} as ONE JSON object: {"summaries": [{"id", "summary"}], "unsummarized": [{"id", "reason"}]}, with exactly one entry per Epic listed, in one list or the other, and none for any other Epic.

Return the path you wrote, how many Epics you summarized, and the ids you could not summarize.`,
      { label: `summarize:${n + 1}`, phase: 'Summarize', effort: 'medium', schema: SUMMARY_SCHEMA }
    )
    if (done) written.push(out)
  })
)

// ── Record ───────────────────────────────────────────────────────────────────────
enter('Record')
let recorded = null
if (written.length) {
  const out = await runStep(
    'record-summaries',
    cmd('record-summaries', `--plan ${shq(planFile)} ${written.sort().map((p) => `--summaries ${shq(p)}`).join(' ')} --out ${shq(file('record-summaries.json'))}`)
  )
  recorded = out ? out.summary || {} : null
}
if (recorded) log(`Summaries: ${recorded.written} written, ${recorded.missing} missing — detail in ${file('record-summaries.json')}`)

return {
  ok: !!recorded && recorded.missing === 0 && failures.length === 0,
  workDir: work,
  plan,
  summarized: recorded ? recorded.written : 0,
  record: recorded,
  failures,
  dispatchFailed: dispatchDeaths().length > 0,
  dispatchFailures: dispatchDeaths(),
}
