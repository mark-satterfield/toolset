export const meta = {
  name: 'dependency-assessment',
  description:
    "Assesses the architecture dependencies of ONE Epic and writes its `tracks` edges. One epic-sequencer session writes the Epic's context, reads its PRD and the related PRDs, proposes and validates the edges, and runs apply-edges. When the edges are applied it triggers wsjf-scoring. With `apply: false` apply-edges runs as a dry run and no scoring runs.",
  whenToUse: 'A new or changed Epic needs its architecture dependencies assessed.',
  phases: [
    { title: 'Assess', detail: 'one epic-sequencer session writes the context, proposes and validates the edges, and runs apply-edges' },
    { title: 'Score', detail: 'wsjf-scoring over the new edges' },
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

// args: {
//   repoPath:     string,   // absolute path of the repository whose `bd` tracker holds the Epics
//   pluginRoot:   string,   // absolute path of this plugin's root
//   workDir:      string,   // absolute path of a directory for this run's files
//   epic:         string,   // the one Epic assessed
//   sadPath?:     string,
//   projectRoot?: string,
//   contextDir?:  string,   // where the PRD corpus and index live; default <workDir>/context
//   corpusReady?: boolean,  // the corpus in contextDir is already written
//   score?:       boolean,  // false: do not trigger scoring. Default true.
//   apply?:       boolean,  // false: apply-edges runs as a dry run. Default true.
// }
// Returns: { ok, stage, beadId, headline, apply, settled, workDir, epic, assessment, edges, scoring,
//            stop, error?, dispatchFailed, dispatchFailures }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const target = String(a.epic || '')
const repo = String(a.repoPath || '').replace(/\/+$/, '')
const work = String(a.workDir || '').replace(/\/+$/, '')
const DS = `${String(a.pluginRoot || '').replace(/\/+$/, '')}/scripts/portfolio/depscore.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const scope = `--epic ${shq(target)}`
const applies = a.apply !== false
const project = { repoPath: repo, pluginRoot: a.pluginRoot, sadPath: a.sadPath, projectRoot: a.projectRoot }

const planFile = file('assess-plan.json')
const contextDir = String(a.contextDir || file('context')).replace(/\/+$/, '')
const contextFile = file('context.json')
const corpusDir = `${contextDir}/prd`
const indexFile = `${contextDir}/index.md`
const epicPrd = `${corpusDir}/${target}.md`
const edgesFile = file('edges.json')
const reasoningFile = file('reasoning.md')
const validationFile = file('validation.json')
const applyFile = file(applies ? 'apply-edges.json' : 'apply-edges-dry-run.json')

phase('Assess')
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
const THE_TEST = `THE TEST. An Epic is a PRD, a WHAT; its architecture does not exist yet. An edge from A to B says: an architecture decision B rests on should be designed from A's requirements first, because A's requirements are the fuller statement of what that decision must serve — sign-up and sign-in requirements drive the identity architecture, so password reset waits, or identity gets designed from a recovery flow's requirements alone. A reason that says something must exist, be built, be deployed or be testable first, that B presumes a user or a record exists, or that B reads data from or calls a capability of A, is a build dependency between Tasks and is never an Epic edge. ${a.sadPath ? `The SAD is ${a.sadPath}: a` : 'A'} decision the SAD already settles needs no edge; check it before drawing one. A SAD entry settles a decision ONLY when its frontmatter reads \`lifecycle_state: effective\` — read that field, never infer it from the wording. A dated ruling, a MUST and a table of values are properties of the prose, and an unvetted entry has more of them than a vetted one. An entry in any other state settles NOTHING and the test proceeds as though it were absent.`
const applyCmd = `set -o pipefail; ${cmd('apply-edges', `--edges ${shq(edgesFile)} --plan ${shq(planFile)} ${scope}${applies ? '' : ' --dry-run'}`)} | tee ${shq(applyFile)}`
const assessPrompt = `Assess the architecture dependencies of ONE Epic, ${target}, following \`agent-teams-workforce:epic-sequencing\` for the edge test and its worked example. ${target} is new or has changed.

${THE_TEST}

Work in this order:
1. Run these two commands, once each. Each prints one JSON object; if either exits non-zero, stop, set \`valid\` false, \`applyExitCode\` -1, \`applySummary\` {}, and put its output in \`error\`.
   ${cmd('assess-plan', `${scope} --out ${shq(planFile)}`)}
   ${cmd('assess-context', `${scope} --dir ${shq(contextDir)}${a.corpusReady ? ' --corpus-ready' : ''} --out ${shq(contextFile)}`)}
   They write: ${target}'s full PRD at ${epicPrd}; the PRD corpus at ${corpusDir}, one file per open Epic named <id>.md; the index at ${indexFile}, one line per open Epic with its title, elaboration state, PRD path and section headings; and ${contextFile}, whose \`standing\` lists every edge between ${target} and another open Epic, in either direction, as {from, to, type, owned, reason, confidence, setBy, setAt} — \`from\` is the Epic designed first, \`reason\` the one recorded when the edge was set, or null. \`withdrawn\` lists every edge touching ${target} that an earlier assessment WITHDREW, as {from, to, reason, withdrawnBy, withdrawnAt}: that edge was judged not to exist, for the reason recorded. Setting it again is admitted only when you answer that reason.${a.sadPath ? `\n   The SAD: ${a.sadPath}` : ''}
2. Read ${target}'s full PRD.
3. Name the architecture decisions its requirements should drive, and the architecture decisions it rests on.
4. Check each against the SAD, and drop every decision the SAD already settles. Search the SAD for the decision, and read the section you find — INCLUDING its frontmatter \`lifecycle_state\`. An entry settles the decision only when that field reads \`effective\`; in any other state it settles nothing, however normatively it is worded and whatever date it carries, and you proceed as though the entry were absent. Record, for each decision you keep, which section you consulted, the \`lifecycle_state\` you read there, and why it leaves the decision open — that record goes on every edge as \`sadCheck\`, and an edge without one is refused. An entry becomes \`effective\` only when an Epic whose elaboration vetted it completes, so most entries are still \`in-review\` or \`draft\`: treat a decision you were about to drop on any entry that is not \`effective\` as open.
5. For each remaining decision, search the corpus with Grep, and the index for titles and sections, for the PRDs whose requirements drive or rest on it. Read no PRD the search did not find related.
6. Read in full every related PRD, and the PRD at the other end of every standing edge.
7. Apply the test in both directions: an edge from another Epic to ${target} where the architecture ${target} rests on should be designed from that Epic's requirements first, and an edge from ${target} to another Epic where that Epic's architecture should be designed from ${target}'s requirements first.
8. Write ${edgesFile} as {"edges": [{"from", "to", "reason", "confidence", "sadCheck", "answers"}], "withdrawn": [{"from", "to", "reason"}]}. \`sadCheck\` is required on every edge: the SAD section you consulted for the decision it orders, and why that section leaves the decision open. \`answers\` is required only on an edge the context's \`withdrawn\` list covers: state why the recorded withdrawal reason is wrong, on the architecture. An edge you cannot answer that way is not set — the earlier judgment stands. \`edges\` holds EVERY edge to or from ${target} that passes the test — a standing one it keeps included — and no edge that does not touch ${target}. \`withdrawn\` holds every standing edge with \`owned: true\` that is not in \`edges\`, with a reason that answers the reason recorded for it. Every reason names the architecture decision and whose requirements should drive it; \`confidence\` is \`high\`, \`medium\` or \`low\`. A standing edge with \`owned: false\` was made by hand: leave it out of both lists. Write the reasoning, per edge and per withdrawal, to ${reasoningFile}.
9. Validate: \`set -o pipefail; ${cmd('validate', `--edges ${shq(edgesFile)} ${scope}`)} | tee ${shq(validationFile)}\` — revise the file until \`ok\` is true, keeping to THE TEST: an edge that fails the test is dropped, never kept to satisfy the validator. It refuses an edge that does not touch ${target}, a missing reason, an edge with no \`sadCheck\`, an edge an earlier assessment withdrew that carries no \`answers\`, an owned standing edge left unaccounted, a withdrawal of an edge that is not an owned standing edge, and a cycle against every other Epic edge. A cycle you cannot remove by dropping one of your own edges that fails the test — one through an edge with \`owned: false\` — is reported, not forced: set \`valid\` false, put the validator's findings in \`findings\`, name the cycle in \`unsure\`, and do not run step 10 (\`applyExitCode\` -1, \`applySummary\` {}).
10. Only once validation passes, run exactly this, once: \`${applyCmd}\`. Return its exit code as \`applyExitCode\` and the \`summary\` object it printed, unaltered, as \`applySummary\`. Do not retry it or repair anything it refuses.

Return the edge file path, the reasoning file path, the edge count, whether the final validation passed, \`relatedRead\` — the id of every Epic whose PRD you read in full, other than ${target} — each edge you were unsure of with what would settle it, and the apply-edges result.`

const assessed = await settleAgent(assessPrompt, {
  label: `epic-sequencer:${target}`,
  phase: 'Assess',
  effort: 'medium',
  agentType: 'agent-teams-workforce:epic-sequencer',
  schema: ASSESS_SCHEMA,
})
const printed = (assessed && assessed.applySummary) || {}
const summary = printed.command === 'apply-edges' && printed.summary && typeof printed.summary === 'object' ? printed.summary : printed
const settled = !!assessed && assessed.applyExitCode === 0 && !summary.validation && summary.applied !== false
const stop = assessed && !settled && !assessed.error
  ? { epic: target, findings: assessed.findings || summary.validation || {}, edgesFile, validationFile, reasoning: reasoningFile }
  : null
const edges = {
  ...summary,
  applied: applies && settled,
  proposed: !applies && settled,
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
            : `the edge proposal was not applied (exit ${assessed.applyExitCode}); the tracker keeps its current edges`,
      }),
}
if (settled) log(`Edges (${target})${applies ? '' : ', proposed'}: ${summary.added ?? '?'} added, ${summary.converted ?? '?'} converted, ${summary.removed ?? '?'} withdrawn, ${summary.unchanged ?? '?'} unchanged`)
else log(`${target}: ${edges.reason}`)

let scoring = null
const scores = applies && settled && a.score !== false
if (scores) {
  phase('Score')
  try {
    scoring = await workflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
  } catch (err) {
    scoring = { ok: false, error: String((err && err.message) || err).slice(0, 500) }
  }
}

const scoredOk = !scores || (!!scoring && scoring.ok === true)
const scoringDeaths = scoring && scoring.ok !== true && scoring.stage === 'agent-dispatch-failed' && Array.isArray(scoring.dispatchFailures) ? scoring.dispatchFailures : []
const failure = !settled
  ? `${target}: ${edges.reason}`
  : !scoredOk
    ? `${target}: the edges were applied, but scoring failed: ${(scoring && scoring.error) || 'wsjf-scoring returned no result'}`
    : null
return {
  ok: settled && scoredOk,
  stage: !assessed ? 'agent-dispatch-failed' : !settled ? 'Assess' : !scoredOk ? (scoring && scoring.stage === 'agent-dispatch-failed' ? scoring.stage : 'Score') : 'done',
  beadId: target,
  headline: failure || `${target}: edges ${applies ? 'applied' : 'proposed'} — ${summary.added ?? '?'} added, ${summary.converted ?? '?'} converted, ${summary.removed ?? '?'} withdrawn, ${summary.unchanged ?? '?'} unchanged${scores ? ', and rescored' : ''}`,
  apply: applies,
  settled,
  workDir: work,
  epic: target,
  assessment: assessed || { failed: true },
  edges,
  scoring,
  stop,
  ...(failure ? { error: failure } : {}),
  dispatchFailed: dispatchDeaths().length + scoringDeaths.length > 0,
  dispatchFailures: [...dispatchDeaths(), ...scoringDeaths],
}
