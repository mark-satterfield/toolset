export const meta = {
  name: 'tdd-refactor',
  description:
    'Shared-tail mini — TDD Refactor. complexity-analyzer advises FIRST (read-only), and when it returns no recommendations the phase ENDS THERE — nothing is routed, edited, or reviewed, because the only agent qualified to judge has said the change needs no cleanup. Otherwise a read-only code-quality-lead SELECTS which optimizers to run for what changed; the code-refactoring-specialist and the selected optimizers apply behavior-preserving changes SEQUENTIALLY (tests stay green after each), then an independent code-correctness-reviewer confirms no regression. A null analysis means unknown, not nothing, and does not skip; a re-run carrying gate feedback always proceeds. Lead/advisor/checker are read-only — only the refactorer and selected optimizers edit code; no self-approval.',
  phases: [{ title: 'Refactor', detail: 'behavior-preserving cleanup + optimizer selection + independent review' }],
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

// args: { contract, green, feedback? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
const changedFromGreen = (green.changedFiles || []).join(', ') || 'n/a'

phase('Refactor')

// 1) ADVISOR — complexity-analyzer reads the green-tested change and returns prioritized
// refactor recommendations. READ-ONLY: it makes no edits; its output informs selection.
const complexity = await settleAgent(
  `Analyze the code changed by the fix for complexity, duplication, and refactor opportunities. You are READ-ONLY — make NO edits. Return a prioritized list of refactor recommendations the downstream refactorer and optimizers will act on. Work within: ${repo}

Changed files from the fix: ${changedFromGreen}`,
  {
    label: 'refactor:analyze-complexity',
    phase: 'Refactor',
    agentType: 'agent-teams-workforce:complexity-analyzer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['recommendations'],
      properties: {
        recommendations: { type: 'array', items: { type: 'string' } },
        hotspots: { type: 'array', items: { type: 'string' } },
        notes: { type: 'string' },
      },
    },
  }
)

// ── Nothing to refactor? Then the phase is done here. ─────────────────────────
//
// The analyzer is advisory and READ-ONLY, so an empty recommendation list is a
// real finding: this change carries no complexity, duplication, or cleanup worth
// making. Everything below — the optimizer router, the refactoring specialist,
// each selected optimizer, the independent correctness reviewer, and the gate
// that judges them — is then pure cost. That is roughly six turns of quality work
// spent on code that has just passed its tests and that the only agent qualified
// to assess it says needs nothing. For a one-line fix it was the largest unearned
// expense in the tail.
//
// Two guards on the exit. A NULL analysis means UNKNOWN, not "nothing", and must
// never skip — an analyzer that died is not an analyzer that approved. And a
// re-run carrying gate feedback is rework that was explicitly demanded, so it
// proceeds no matter what the analyzer returns; skipping there would ignore the
// gate and loop until the budget is gone.
const recommendations =
  complexity && Array.isArray(complexity.recommendations)
    ? complexity.recommendations.filter((r) => String(r || '').trim())
    : null
if (recommendations && !recommendations.length && !a.feedback) {
  log('Refactor: complexity analysis found nothing to do — skipping optimizer selection, the refactorer, and the review')
  return {
    refactor: null,
    optimizers: [],
    complexityAnalysis: complexity,
    review: null,
    changedFiles: [],
    alreadySatisfied: true,
    ledger: {
      phase: 'refactor',
      beadId: (c.bead && c.bead.id) || null,
      chosen: ['complexity-analyzer'],
      mode: 'nothing-to-refactor',
      ok: true,
    },
  }
}

// 2) SELECTION — code-quality-lead is a READ-ONLY router. It selects the FEWEST optimizers
// whose specialty matches what changed (Lambda hot paths, DynamoDB access, frontend, style,
// a11y). It writes no code. On empty selection the mini falls back to no optimizers (the
// refactoring-specialist alone), which is the 'default' mode in the ledger.
const OPTIMIZER_ROSTER = [
  'lambda-performance-optimizer',
  'dynamodb-cost-optimizer',
  'frontend-performance-optimizer',
  'code-style-and-linting-enforcer',
  'accessibility-validator',
]
const selection = await settleAgent(
  `You are the code-quality-lead — a READ-ONLY router. Do NOT write code. Based on what the fix changed and the complexity analysis, select the FEWEST optimizer agent(s) whose specialty applies, drawn ONLY from: ${OPTIMIZER_ROSTER.join(', ')}.
- lambda-performance-optimizer: Lambda hot paths, cold start, memory sizing.
- dynamodb-cost-optimizer: DynamoDB capacity, access patterns, index cost.
- frontend-performance-optimizer: web/frontend bundle, render path, Core Web Vitals.
- code-style-and-linting-enforcer: lint/format/style cleanup.
- accessibility-validator: UI a11y (WCAG 2.2 A/AA) — select only when the change touches UI.
Select none if no optimizer applies (the refactoring-specialist alone will run). Order them so earlier ones lay groundwork for later ones; they will run SEQUENTIALLY so tests stay green after each.

Work within the repository at: ${repo}

Changed files from the fix: ${changedFromGreen}
Complexity recommendations: ${(complexity && complexity.recommendations || []).join('; ') || 'n/a'}`,
  {
    label: 'refactor:select-optimizers',
    effort: 'low',
    phase: 'Refactor',
    agentType: 'agent-teams-workforce:code-quality-lead',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['optimizers', 'rationale'],
      properties: {
        optimizers: { type: 'array', items: { type: 'string' } },
        rationale: { type: 'string' },
      },
    },
  }
)
const pickedOptimizers =
  selection && Array.isArray(selection.optimizers)
    ? selection.optimizers.filter((o) => OPTIMIZER_ROSTER.includes(o))
    : []
const selectionMode = pickedOptimizers.length ? 'selected' : 'default'

// 3) MAKER — the code-refactoring-specialist applies the behavior-preserving refactor first,
// keeping every test green. This is the segregation invariant's writer half; it pairs with
// the read-only correctness reviewer at the end.
const refactor = await settleAgent(
  `Refactor the code changed by the fix for clarity and to reduce complexity/duplication, WITHOUT changing behavior. Address the complexity analysis where it applies. Keep every test green — run the suite after your changes. Work within: ${repo}

Changed files from the fix: ${changedFromGreen}
Complexity recommendations: ${(complexity && complexity.recommendations || []).join('; ') || 'n/a'}
${a.feedback ? `\nReviewer feedback to address:\n${a.feedback}` : ''}

Deliver the files you touched, whether tests are still green, and the captured test output.`,
  {
    label: 'refactor:apply',
    phase: 'Refactor',
    agentType: 'agent-teams-workforce:code-refactoring-specialist',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['changedFiles', 'testsGreen', 'evidence'],
      properties: {
        changedFiles: { type: 'array', items: { type: 'string' } },
        testsGreen: { type: 'boolean' },
        evidence: { type: 'string' },
        notes: { type: 'string' },
      },
    },
  }
)

const OPTIMIZER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'testsGreen', 'evidence'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    testsGreen: { type: 'boolean' },
    evidence: { type: 'string' },
    notes: { type: 'string' },
  },
}

// 4) OPTIMIZERS — run the selected optimizers SEQUENTIALLY after the refactor, each building
// on the prior change so no two writers touch the tree concurrently. Each must keep the
// suite green; the captured output proves it before the next one runs.
const optimizerRuns = []
const changedFiles = [...(refactor.changedFiles || [])]
for (const opt of pickedOptimizers) {
  const run = await settleAgent(
    `Apply your optimization to the refactored code WITHOUT changing behavior, then run the test suite and confirm every test is still green. Work within: ${repo}

You are '${opt}', running after the code-refactoring-specialist and any earlier optimizers — their changes are already applied. Make only the part matching your specialty.
Files changed so far: ${changedFiles.join(', ') || 'n/a'}
Complexity recommendations: ${(complexity && complexity.recommendations || []).join('; ') || 'n/a'}

Constraints: preserve behavior; do not modify tests to make them pass; honor SkillSpoke code-quality rules. Deliver the files you touched, whether tests are still green, and the captured test output.`,
    {
      label: `refactor:${opt}`,
      phase: 'Refactor',
      agentType: `agent-teams-workforce:${opt}`,
      schema: OPTIMIZER_SCHEMA,
    }
  )
  optimizerRuns.push({ optimizer: opt, ...(run || {}) })
  if (run && Array.isArray(run.changedFiles)) changedFiles.push(...run.changedFiles)
}

// 5) CHECKER — independent correctness review LAST. A different, READ-ONLY agent confirms the
// test suite is still green and behavior is preserved across the refactor + all optimizers.
// No producer judges its own work.
const review = await settleAgent(
  `Review the refactor and optimizer changes below for correctness regressions and behavioral drift. You are READ-ONLY. Verify the test suite is still green and that behavior is preserved across ALL changes. Work within: ${repo}

Files changed (refactor + optimizers): ${changedFiles.join(', ') || 'n/a'}
Refactorer's evidence: ${refactor.evidence || 'n/a'}
Optimizers run: ${pickedOptimizers.join(', ') || 'none'}`,
  {
    label: 'refactor:review',
    phase: 'Refactor',
    agentType: 'agent-teams-workforce:code-correctness-reviewer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['behaviorPreserved', 'testsGreen', 'findings'],
      properties: {
        behaviorPreserved: { type: 'boolean' },
        testsGreen: { type: 'boolean' },
        findings: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// Decision ledger — what this phase actually did, for over-time mining.
// chosen = the writers + checker that ran, in order. mode 'selected' = code-quality-lead
// chose optimizers; mode 'default' = no optimizer applied and only the fixed pair ran.
const ledger = {
  phase: 'refactor',
  beadId: (c.bead && c.bead.id) || null,
  chosen: ['code-refactoring-specialist', ...pickedOptimizers, 'code-correctness-reviewer'],
  mode: selectionMode,
  ok: !!(review && review.testsGreen && review.behaviorPreserved),
}

return { refactor, optimizers: optimizerRuns, complexityAnalysis: complexity, review, changedFiles, ledger }
