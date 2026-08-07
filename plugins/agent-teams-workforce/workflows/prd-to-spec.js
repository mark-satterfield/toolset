export const meta = {
  name: 'prd-to-spec',
  description:
    'Composite — drives a request (or an existing PRD) all the way to an emitted, WSJF-scored Epic → Story → Task hierarchy in Beads form. Stitches the leaf minis (optional PRD creation, PRD validation, architecture, TRD authoring, spec authoring, task decomposition) behind independent gates: G1 PRD validation, G2 constitutional architecture, G2b TRD, G3 spec (once per repo), G4 task decomposition (once per Story). The hierarchy rules bind throughout: a PRD and its Epic are created together (an Epic is backfilled for a pre-existing PRD), the TRD is authored once per PRD, a Spec and its Story are created together with one Story per repo the PRD spans, and each Story decomposes into tasks only. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing minis never judge their own work — the gates do. One level only: this composite calls minis and gates, never another composite.',
  phases: [
    { title: 'PRD Creation', detail: 'optional — only when a raw request is supplied and no PRD exists' },
    { title: 'PRD Validation' },
    { title: 'Epic', detail: 'ensure the Epic exists — minted with the PRD, supplied by the caller, or backfilled for an existing PRD' },
    { title: 'Architecture' },
    { title: 'TRD Authoring', detail: 'once per PRD — the TRD is per-PRD, never fanned out per repo' },
    { title: 'Spec Authoring', detail: 'once per repo — a Spec and its Story are created together, one Story per repo' },
    { title: 'Task Decomposition', detail: 'once per Story — tasks only, parented to that Story' },
    { title: 'Emit Beads', detail: 'surface the full Epic → Story → Task hierarchy plus the flat task bead set' },
  ],
}

// args: {
//   request?: { id?, title?, description?, repoPath?, requestedBy? },  // raw request — triggers optional PRD creation
//   prd?: { id?, title?, body?, content?, path?, repoPath?, acceptanceCriteria?[] }, // existing PRD; skips creation
//   context?: string,             // bounded-context / service-boundary notes for PRD validation
//   brd?: string,                 // BRD objectives text — WITHOUT it the traceability audit has nothing
//                                 // to audit against and every requirement reads as an orphan
//   decision?: { id?, title?, context?, drivers?[], repoPath? }, // the architecture question
//   sad?: { path?, sectionLayout? },  // arc42 SAD location for TRD extraction
//   sadPath?: string,             // arc42 SAD path for the architecture mini
//   spec?: { id?, title?, summary?, service?, repoPath? }, // spec-authoring context
//   accessPatterns?: string[],    // known data access patterns for the data-model spec
//   repoPath?: string,            // owning service/repo for downstream artifacts
//   repos?: string[],             // every repo this PRD spans — one Story (one spec pass) per repo;
//                                 // defaults to [repoPath] so the single-repo case is unchanged
//   epic?: { key, type:'epic', title?, description?, prdRef? }, // the PRD's existing Epic — skips backfill
//   trdPath?: string,             // where the TRD lives/should be written
//   maxLoops?: number,            // gate retry-in-phase bound (default 3)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
// Gate retry budget. One rework round, then proceed with the finding recorded.
//
// This was 3, and nested minis carried their own bound of 2 on top, so a single
// phase could burn six expensive attempts before anyone saw a result — the
// dominant cost in every run that stalled. A checker's objection is information;
// it does not have to be a veto. One revision is where nearly all the value is:
// if a maker cannot address a finding on the second try, a third rarely helps and
// the finding is better carried forward than ground against.
//
// Callers who want the old behaviour pass args.maxLoops explicitly.
const MAX_LOOPS = a.maxLoops || 2
const repoPath = a.repoPath || (a.request && a.request.repoPath) || (a.prd && a.prd.repoPath) || null
// One Epic may span repos and a Story is scoped to exactly one, so spec authoring
// fans out once per repo below. Absent an explicit span the single repoPath is the
// whole span; null is filtered out rather than minted into a repo-less Story, which
// the work-item hierarchy forbids.
const repos = (Array.isArray(a.repos) && a.repos.length ? a.repos : [repoPath]).filter((r) => r != null)
if (!a.request && !a.prd) log('⚠ neither request nor prd supplied — running in dry/demo mode')

// Decision ledger for over-time mining (see run-ledger-writer). Each instrumented
// mini returns a `ledger` on its artifact; collected here and persisted ONCE in a
// finally so it runs on success, early-return, and throw alike.
const runLedger = []
async function persistRun(outcome) {
  if (!runLedger.length) return
  try {
    await agent(
      `Persist this SDLC workflow run's decision ledger. JSON payload:\n${JSON.stringify({ composite: 'prd-to-spec', bead: null, subject: (a.prd && a.prd.id) || (a.request && a.request.id) || null, outcome, runLedger })}`,
      {
        label: 'ledger:persist',
        phase: 'Emit Beads',
        agentType: 'agent-teams-workforce:run-ledger-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['written'],
          properties: {
            written: { type: 'boolean' },
            path: { type: 'string' },
            lines: { type: 'number' },
            runId: { type: 'string' },
          },
        },
      }
    )
  } catch (e) {
    log(`ledger persist failed (non-fatal): ${e && e.message ? e.message : e}`)
  }
}

// Run a phase, judge it at an INDEPENDENT gate, apply the verdict.
async function gateLoop({ gate, phaseName, criteria, escalateTargets, phaseFn, gateWorkflow }) {
  let feedback = ''
  // Every adjudication goes to the ledger. Without the verdict and its per-criterion
  // evidence, a run that stops at a gate records only `failed:<phase>` — which cannot
  // distinguish a genuine defect from an over-strict criterion or a loop exhaustion.
  const recordGate = (attempt, verdict, extra) =>
    runLedger.push({
      phase: `gate:${gate}`,
      gate,
      gatePhase: phaseName,
      attempt,
      maxLoops: MAX_LOOPS,
      verdict: (verdict && verdict.verdict) || 'no-verdict',
      criteria: ((verdict && verdict.criteria) || []).map((c) => ({
        criterion: c.criterion,
        met: c.met,
        evidence: c.evidence,
      })),
      unmetCriteria: ((verdict && verdict.criteria) || [])
        .filter((c) => !c.met)
        .map((c) => c.criterion),
      feedback: (verdict && verdict.feedback) || null,
      escalateTo: (verdict && verdict.escalateTo) || null,
      flags: (verdict && verdict.flags) || [],
      ...(extra || {}),
    })

  for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
    const artifact = await phaseFn(feedback)
    const verdict = await workflow(gateWorkflow || 'agent-teams-workforce:gate-enforce', {
      gate, phaseName, criteria, artifact, escalateTargets,
    })
    if (!verdict) {
      recordGate(attempt, null, { terminal: 'no-verdict' })
      return { ok: false, reason: `gate ${gate} returned no verdict`, artifact }
    }
    recordGate(attempt, verdict)
    if (verdict.verdict === 'pass') {
      log(`Gate ${gate} (${phaseName}): PASS${verdict.flags && verdict.flags.length ? ` — flags: ${verdict.flags.join('; ')}` : ''}`)
      return { ok: true, artifact, verdict }
    }
    if (verdict.verdict === 'escalate') {
      log(`Gate ${gate} (${phaseName}): ESCALATE -> ${verdict.escalateTo || 'upstream'}`)
      return { ok: false, escalate: verdict.escalateTo || 'upstream', artifact, verdict }
    }
    log(`Gate ${gate} (${phaseName}): LOOP ${attempt}/${MAX_LOOPS} — ${verdict.feedback}`)
    feedback = verdict.feedback || ''
  }
  recordGate(MAX_LOOPS, null, { verdict: 'loop-exhausted', terminal: 'loop-exhausted' })
  return { ok: false, reason: `gate ${gate} exceeded ${MAX_LOOPS} loops`, loopExhausted: true }
}

// ── PRD Creation (optional) ────────────────────────────────────────────────────
// Only when a raw request is supplied and no PRD already exists. The created PRD
// becomes the input to validation; otherwise the supplied PRD is used directly.
let result
try {
  result = await (async () => {
phase('PRD Creation')
let creation = null
let prd = a.prd || null
if (!prd && a.request) {
  log(`Creating PRD from request ${a.request.id || '(no id)'} — ${a.request.title || ''}`)
  creation = await workflow('agent-teams-workforce:prd-creation', { request: a.request })
  if (!creation || !creation.ok) {
    return { ok: false, stage: 'prd-creation', reason: 'PRD creation did not produce an aligned PRD', detail: creation }
  }
  // Thread the created PRD forward as the validation input.
  prd = {
    id: (creation.prd && creation.prd.title) || (a.request && a.request.id) || null,
    title: creation.prd && creation.prd.title,
    body: creation.prd && creation.prd.prd,
    acceptanceCriteria: creation.prd && creation.prd.acceptanceCriteria,
    repoPath,
  }
} else {
  log(prd ? 'PRD supplied — skipping creation' : 'No request and no PRD — nothing to create')
}
if (!prd) return { ok: false, stage: 'prd-creation', reason: 'no PRD available to validate (supply args.prd or args.request)' }

// ── PRD Validation (Gate 1) ─────────────────────────────────────────────────────
phase('PRD Validation')
const validation = await gateLoop({
  gate: 'G1', phaseName: 'PRD Validation',
  criteria: [
    'No unresolved internal contradictions between requirements that cannot be built around (a genuine WHAT-level conflict)',
    'Every requirement states an actor, a trigger, and an observable user outcome, with acceptance criteria expressed as observable behavior — mechanism/HOW (algorithms, thresholds, schemas, quantified NFRs) is out of scope at PRD altitude and is defined later in the spec',
    'Quality intent the feature implies (privacy, security, accessibility, abuse-resistance) is named where the WHAT requires it, WITHOUT demanding quantified targets, SLOs, or implementation detail',
    'Scope is bounded: each requirement sits in one feature/context and its external dependencies are named (dependency readiness and fallback mechanics are spec/delivery concerns, not PRD defects)',
  ],
  escalateTargets: ['prd-creation'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:prd-validation', {
      prd,
      // The BRD must be threaded through explicitly. prd-validation reads args.brd and hands it
      // to the traceability auditor; when it is absent the auditor has no objectives to map to
      // and reports every requirement as an orphan, which reads as a PRD defect but is not one.
      brd: a.brd,
      context: feedback ? `${a.context || ''}\n\nGate feedback:\n${feedback}` : a.context,
    }),
})
if (validation.artifact && validation.artifact.ledger) runLedger.push(validation.artifact.ledger)
if (!validation.ok) return { ok: false, stage: 'prd-validation', detail: validation, prd }
const validatedPrd = (validation.artifact && validation.artifact.validatedPrd) || prd

// ── Epic (create / accept / backfill) ───────────────────────────────────────────
// A PRD and its Epic are created at the same time, so past this point an Epic must
// exist. It arrives one of three ways: prd-creation minted it alongside the PRD;
// the caller already holds one (args.epic); or the PRD predates the pairing rule
// and the Epic is BACKFILLED here — derived from the validated PRD the same way
// prd-creation derives one from the PRD it authors, nothing invented.
phase('Epic')
let epic
let epicPath
if (creation && creation.epic) {
  epic = creation.epic
  epicPath = 'epic-created'
} else if (a.epic) {
  // A caller-supplied Epic is adopted rather than re-minted, but it still has to
  // leave here as a well-formed epic bead spec — a caller that passed only a key
  // and a title would otherwise put an untyped object into the hierarchy.
  epic = {
    key: a.epic.key || a.epic.id || 'E1',
    ...a.epic,
    type: 'epic',
  }
  epicPath = 'epic-supplied'
} else {
  epic = {
    key: 'E1',
    type: 'epic',
    title: validatedPrd.title || prd.title || prd.id || 'Untitled Epic',
    description:
      (validation.artifact && validation.artifact.summary) ||
      validatedPrd.body ||
      prd.body ||
      '',
    prdRef: prd.path || prd.id || prd.title || null,
  }
  epicPath = 'epic-backfilled'
}
log(
  `Epic ${epic.key || '(no key)'} via ${epicPath}${
    epicPath === 'epic-backfilled' ? ` — derived from existing PRD ${epic.prdRef || '(unreferenced)'}` : ''
  }`
)

// ── Architecture (Gate 2 — constitutional) ──────────────────────────────────────
// Consumes the validated PRD; produces the ruled decision + arc42 SAD source feed.
phase('Architecture')
const architecture = await gateLoop({
  gate: 'G2', phaseName: 'Architecture', gateWorkflow: 'agent-teams-workforce:gate-constitutional',
  criteria: [
    'The chosen architecture honors all platform constitutive bans (no Step Functions, no HTTP API v2, no FastAPI/Flask/Django, REST v1 only, Powertools-only, service isolation, SSM-not-CFN-exports, dot-only event naming)',
    'Every significant decision is ruled by the decider and recorded in the SAD/arc42 source feed',
    'No security or data-isolation finding is left open or downgraded',
  ],
  escalateTargets: ['prd-validation'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:architecture', {
      decision: a.decision || {
        id: prd.id,
        title: `Architecture for ${prd.title || prd.id || 'PRD'}`,
        context: (validation.artifact && validation.artifact.summary) || prd.body || '',
        repoPath,
      },
      sadPath: a.sadPath,
      feedback,
    }),
})
if (architecture.artifact && architecture.artifact.ledger) runLedger.push(architecture.artifact.ledger)
if (!architecture.ok) return { ok: false, stage: 'architecture', detail: architecture, prd: validatedPrd }
const sadExtract = architecture.artifact && architecture.artifact.sadUpdate

// ── TRD Authoring (Gate 2b) ──────────────────────────────────────────────────────
// Consumes PRD + SAD extract; produces the TRD + bidirectional traceability matrix.
// The TRD is per-PRD, not per-repo: it is authored exactly ONCE here and never
// fanned out with the per-repo spec passes below.
phase('TRD Authoring')
const trdAuthoring = await gateLoop({
  gate: 'G2b', phaseName: 'TRD Authoring',
  criteria: [
    'The TRD derives only from the PRD and the SAD source extract (no invented requirements)',
    'Every PRD requirement maps to a TRD entry and back (bidirectional traceability holds)',
    'The TRD validator and traceability verifier both pass',
  ],
  escalateTargets: ['architecture', 'prd-validation'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:trd-authoring', {
      prd: {
        id: prd.id,
        title: prd.title,
        content: validatedPrd.body || prd.body,
        acceptanceCriteria: prd.acceptanceCriteria,
      },
      sad: a.sad || { path: a.sadPath },
      trdPath: a.trdPath,
      repoPath,
      maxLoops: 1,
      feedback,
    }),
})
if (trdAuthoring.artifact && trdAuthoring.artifact.ledger) runLedger.push(trdAuthoring.artifact.ledger)
if (!trdAuthoring.ok) return { ok: false, stage: 'trd-authoring', detail: trdAuthoring, prd: validatedPrd }
const trd = trdAuthoring.artifact && trdAuthoring.artifact.trd

// ── Spec Authoring (Gate 3 — once per repo) ──────────────────────────────────────
// Consumes TRD + SAD extract; produces API/data/event/error specs + AC + DoD.
// A Spec and its Story are created together and a Story is scoped to one repo, so
// this phase fans out across args.repos: one (spec, story) pair per repo, every
// Story parented to the Epic above. Each repo faces its own G3 gate, and a repo
// whose spec fails its gate is RECORDED in the result — never silently dropped.
phase('Spec Authoring')
if (!repos.length) {
  return {
    ok: false,
    stage: 'spec-authoring',
    reason: 'no repos to author specs for — a Story is scoped to a single repo; supply args.repos or args.repoPath',
    prd: validatedPrd,
    epic,
  }
}
const specPairs = [] // one { repoPath, spec, story } per repo that passed G3
const specFailures = [] // repos whose spec failed G3 — kept so they cannot silently vanish
// Each repo's Story needs a distinct key: they become sibling beads under one Epic
// and the dependency graph addresses them by key, so a repeated key would collapse
// several repos' work onto one phantom Story.
for (const [repoIndex, repo] of repos.entries()) {
  const storyKey = `S${repoIndex + 1}`
  const specAuthoring = await gateLoop({
    gate: 'G3', phaseName: repos.length > 1 ? `Spec Authoring — ${repo}` : 'Spec Authoring',
    criteria: [
      'API/data-model/event/error specs are internally consistent and spec-first (OpenAPI before handlers)',
      'Each spec passed its independent checker; deadlocks were ruled by the spec-decider',
      'Acceptance criteria and Definition of Done are present and testable',
      'Event names are dot-form and schemas validate',
    ],
    escalateTargets: ['trd-authoring', 'architecture'],
    phaseFn: (feedback) =>
      workflow('agent-teams-workforce:spec-authoring', {
        spec: a.spec || {
          id: prd.id,
          title: prd.title,
          summary: (trdAuthoring.artifact && trdAuthoring.artifact.trd && trdAuthoring.artifact.trd.summary) || prd.body || '',
          service: a.spec && a.spec.service,
          repoPath: repo,
        },
        trd,
        accessPatterns: a.accessPatterns,
        repoPath: repo,
        storyKey,
        epic,
        maxLoops: 1,
        constraints: feedback ? [feedback] : undefined,
      }),
  })
  if (specAuthoring.artifact && specAuthoring.artifact.ledger) runLedger.push(specAuthoring.artifact.ledger)
  if (!specAuthoring.ok) {
    log(`Spec Authoring FAILED for repo ${repo} — recorded, not dropped`)
    specFailures.push({ repoPath: repo, detail: specAuthoring })
    continue
  }
  // The (spec, story) pairing IS the contract: a spec that arrives without its
  // Story cannot parent any tasks, so it counts as a failure, not a pass.
  const story = specAuthoring.artifact && specAuthoring.artifact.story
  if (!story) {
    log(`Spec Authoring for repo ${repo} returned no story — recorded as a failure`)
    specFailures.push({ repoPath: repo, reason: 'spec-authoring returned no story', detail: specAuthoring })
    continue
  }
  specPairs.push({ repoPath: repo, spec: specAuthoring.artifact, story })
}
if (specFailures.length) {
  return {
    ok: false,
    stage: 'spec-authoring',
    prd: validatedPrd,
    epic,
    specFailures,
    // The repos that DID pass, so their work is not lost with the failure.
    specPairs,
  }
}

// ── Story dependencies ───────────────────────────────────────────────────────────
// Dependencies live at the STORY level, and only there.
//
// An Epic gets NO dependency graph. It is a container for one PRD's worth of work,
// so an edge between Epics would order whole PRDs against each other — a roadmap
// judgement, not a build constraint, and not one this pipeline has the standing to
// make. A Story is the right grain: it is one repo's deployable slice, so "this
// repo's slice must land before that one" is concrete and checkable. Tasks keep a
// narrower ordering inside their own Story, built by task-decomposition.
//
// A single Story has nothing to depend on, so the mapper only runs from two up.
const depStories = specPairs.map((p) => p.story).filter(Boolean)
let storyDependencies = { edges: [], buildOrder: depStories.map((s) => s.key), acyclic: true }
if (depStories.length > 1) {
  const mapped = await agent(
    `Map the dependencies BETWEEN the Stories below, then derive a valid topological build order. Each Story is one repo's deployable slice of the same Epic. Reference Stories by their "key". An edge "from -> to" means "from must land before to".

Add an edge ONLY where one Story genuinely cannot land until another has — an API it consumes that does not exist yet, an event contract its producer must publish first, a shared table or IAM grant the other side provisions. Sharing a domain, a vocabulary, or the same Epic is NOT a dependency. When in doubt leave the edge out: a false edge serializes work that could have run in parallel, and this graph is the only thing deciding what runs concurrently.

The graph MUST be acyclic. If the only honest reading of these Stories implies a cycle, set acyclic=false, name the cycle, and leave buildOrder empty rather than inventing an order.

Do NOT add, remove, or rescope Stories. Do NOT write code.

Epic: ${epic.key} — ${epic.title}
Stories:
${depStories.map((s) => `- ${s.key} [${s.repoPath}]: ${s.title}${s.description ? ` — ${s.description}` : ''}`).join('\n')}`,
    {
      label: 'sequence:story-dag',
      phase: 'Spec Authoring',
      agentType: 'agent-teams-workforce:task-dependency-mapper',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['edges', 'buildOrder', 'acyclic'],
        properties: {
          edges: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['from', 'to'],
              properties: { from: { type: 'string' }, to: { type: 'string' } },
            },
          },
          buildOrder: { type: 'array', items: { type: 'string' } },
          acyclic: { type: 'boolean' },
          cycle: { type: 'array', items: { type: 'string' } },
        },
      },
    }
  )
  if (mapped && mapped.acyclic === false) {
    return {
      ok: false,
      stage: 'story-dependencies',
      reason: 'the Story dependency graph is not acyclic',
      cycle: (mapped && mapped.cycle) || [],
      prd: validatedPrd,
      epic,
      stories: depStories,
    }
  }
  if (mapped) storyDependencies = { ...mapped, cycle: mapped.cycle || [] }
}

// Fold the edges onto the Stories themselves so a caller emitting with bd has the
// dependency in hand without re-deriving it from a side channel.
const storyOrderIndex = {}
;(storyDependencies.buildOrder || []).forEach((k, i) => {
  storyOrderIndex[k] = i
})
for (const s of depStories) {
  s.dependsOn = (storyDependencies.edges || []).filter((e) => e.to === s.key).map((e) => e.from)
  s.buildOrderIndex = s.key in storyOrderIndex ? storyOrderIndex[s.key] : null
}
log(
  `Story dependencies: ${storyDependencies.edges.length} edge(s) across ${depStories.length} story/stories. ` +
    `The Epic carries none by design.`
)

// ── Task Decomposition (Gate 4 — once per Story) ─────────────────────────────────
// Consumes each repo's specs; produces a sized, sequenced (DAG), WSJF-scored task
// set parented to that repo's Story. Decomposition yields TASKS ONLY — the Epic
// and the Stories already exist above, so nothing else is ever minted here.
phase('Task Decomposition')
const stories = specPairs.map((p) => p.story)
const decompositions = [] // one { repoPath, storyKey, artifact } per Story that passed G4
const decompositionFailures = [] // Stories whose task set failed G4 — kept, never dropped
const tasks = []
for (const pair of specPairs) {
  const decomposition = await gateLoop({
    gate: 'G4',
    phaseName: specPairs.length > 1
      ? `Task Decomposition — ${pair.story.key || pair.repoPath}`
      : 'Task Decomposition',
    criteria: [
      'Tasks are atomic and each traces to a spec element',
      'The dependency DAG is acyclic and sequencing is valid',
      'Every task is WSJF-scored and the scoring passed independent review',
      'Beads format validates for every emitted task',
    ],
    escalateTargets: ['spec-authoring'],
    phaseFn: (feedback) =>
      workflow('agent-teams-workforce:task-decomposition', {
        spec: {
          id: prd.id,
          title: prd.title,
          description:
            (pair.spec && pair.spec.apiSpec && pair.spec.apiSpec.summary) ||
            (trd && trd.summary) ||
            prd.body ||
            '',
          source: feedback ? `spec-authoring output (gate feedback: ${feedback})` : 'spec-authoring output',
          repoPath: pair.repoPath,
        },
        story: { id: pair.story.id, key: pair.story.key, title: pair.story.title },
        maxScoringPasses: 2,
      }),
  })
  if (decomposition.artifact && decomposition.artifact.ledger) runLedger.push(decomposition.artifact.ledger)
  if (!decomposition.ok) {
    log(`Task Decomposition FAILED for story ${pair.story.key || '(no key)'} (${pair.repoPath}) — recorded, not dropped`)
    decompositionFailures.push({ repoPath: pair.repoPath, storyKey: pair.story.key || null, detail: decomposition })
    continue
  }
  decompositions.push({ repoPath: pair.repoPath, storyKey: pair.story.key || null, artifact: decomposition.artifact })
  // task-decomposition mints keys local to its own invocation — T1, T2 — and this
  // loop runs it once per Story. Concatenated as-is, every Story's first task is
  // "T1" and bd would write one task where several were meant. Namespace by the
  // Story key, and carry the same rewrite through the intra-Story dependency edges
  // so no task ends up depending on a key that no longer exists.
  const storyKeyForTasks = pair.story.key || pair.story.id
  const localToNamespaced = new Map()
  const storyTasks = (decomposition.artifact && decomposition.artifact.beadSet) || []
  for (const t of storyTasks) localToNamespaced.set(t.key, `${storyKeyForTasks}-${t.key}`)
  for (const t of storyTasks) {
    tasks.push({
      ...t,
      key: localToNamespaced.get(t.key) || t.key,
      dependsOn: (t.dependsOn || []).map((d) => localToNamespaced.get(d) || d),
    })
  }
}
if (decompositionFailures.length) {
  return {
    ok: false,
    stage: 'task-decomposition',
    prd: validatedPrd,
    epic,
    stories,
    decompositionFailures,
    // The Stories that DID decompose cleanly, so their work is not lost.
    decompositions,
  }
}

// ── Emit Beads ───────────────────────────────────────────────────────────────────
// The full hierarchy is ready for `bd` emission from the main repo path: one Epic,
// one Story per repo parented to it (parentEpicKey), and every Story's tasks
// beneath it (parentStoryId). This composite surfaces the tree; it does not write
// to .beads itself (never from a worktree/runtime context). The flat beadSet is
// kept as the concatenation of every Story's tasks so existing callers keep working.
phase('Emit Beads')
const beadSet = tasks
const hierarchy = { epic, stories, tasks, storyDependencies }
log(
  `Hierarchy READY: 1 epic, ${stories.length} story/stories, ${tasks.length} task(s) — sequenced and WSJF-scored, ` +
    `${storyDependencies.edges.length} story dependency edge(s), no epic-level graph. ` +
    `Emit via bd from the main repo path: epic first, then stories by parentEpicKey in buildOrderIndex order, then tasks by parentStoryId.`
)

return {
  ok: true,
  prd: validatedPrd,
  stagesComplete: [
    creation ? 'prd-creation' : 'prd-supplied',
    'prd-validation',
    epicPath,
    'architecture',
    'trd-authoring',
    'spec-authoring',
    'task-decomposition',
    'emit-beads',
  ],
  note: 'PRD validated, Epic ensured (created/supplied/backfilled), architecture ruled into the SAD, TRD authored once per PRD, a (spec, story) pair authored per repo, tasks decomposed/sequenced/WSJF-scored per Story and Beads-format valid. Emit the hierarchy via bd from the main repo path — epic, then stories, then tasks; this composite does not write to .beads.',
  hierarchy,
  beadSet,
  results: {
    creation,
    validation: validation.artifact,
    architecture: architecture.artifact,
    trdAuthoring: trdAuthoring.artifact,
    specAuthoring: specPairs.map((p) => ({ repoPath: p.repoPath, artifact: p.spec })),
    decomposition: decompositions,
  },
}
  })()
} finally {
  await persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
}
return result
