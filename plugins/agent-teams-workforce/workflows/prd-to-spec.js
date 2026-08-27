export const meta = {
  name: 'prd-to-spec',
  description:
    'Composite — drives a request (or an existing PRD) all the way to an emitted, WSJF-scored Epic → Story → Task hierarchy in Beads form. It FIRST reconciles the PRD against what already ships, before any gate is spent: a PRD whose requirements are all built is closed, a delta that is really a defect or an infrastructure switch is rerouted to bug-fix or infra-change, and everything that continues is specified against the DELTA PRD — the absent and partial requirements — never the original ambition. Stitches the leaf minis (PRD reconciliation, optional PRD creation, PRD validation, architecture, TRD authoring, spec authoring, task decomposition) behind independent gates: G1 PRD validation, G2 constitutional architecture, G2b TRD, G3 spec (once per repo), G4 task decomposition (once per Story). The hierarchy rules bind throughout: a PRD and its Epic are ONE item in two representations, created together (the missing face is minted for a pre-existing PRD), the TRD is authored once per PRD, a Spec and its Story are created together with one Story per repo the PRD spans, and the SPEC of each Story decomposes into tasks only — nothing decomposes an Epic or a Story itself. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing minis never judge their own work — the gates do. A gate that spends its retry budget does NOT halt: the advantage-evaluator rules the remaining findings competitive (proceed, flags recorded) or constitutive (fail), and no ruling fails closed. One level only: this composite calls minis and gates, never another composite. The caller receives { ok, stage, beadId, headline, detailPath } plus the emitted hierarchy and bead set; every phase artifact goes to the run journal.',
  phases: [
    { title: 'PRD Reconciliation', detail: 'establish what already ships BEFORE any gate is spent; everything downstream reads the delta PRD' },
    { title: 'PRD Creation', detail: 'optional — only when a raw request is supplied and no PRD exists' },
    { title: 'PRD Validation' },
    { title: 'Epic', detail: "ensure both faces of the item exist — Epic supplied by the caller, minted with the PRD, or minted here for an existing PRD" },
    { title: 'Architecture' },
    { title: 'TRD Authoring', detail: 'once per PRD — the TRD is per-PRD, never fanned out per repo' },
    { title: 'Spec Authoring', detail: 'once per repo — a Spec and its Story are created together, one Story per repo' },
    { title: 'Task Decomposition', detail: 'once per Story — tasks only, parented to that Story' },
    { title: 'Emit Beads', detail: 'surface the full Epic → Story → Task hierarchy plus the flat task bead set' },
    { title: 'Run Ledger', detail: 'telemetry — runs on EVERY exit path, including failure; never evidence the run succeeded' },
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
//   epic?: { key, type:'epic', title?, description?, prdRef? }, // the PRD's existing Epic — ADOPTED, and it wins over any Epic prd-creation mints
//   trdPath?: string,             // where the TRD lives/should be written
//   dependencies?: string[],      // upstream contracts/schemas/libs the PRD assumes — fed to reconciliation
//   deltaPath?: string,           // where the delta PRD is written; derived from prd.path when absent
//   maxLoops?: number,            // gate retry-in-phase bound (default 3)
//   skipArchitecture?: boolean,   // force the Architecture phase on (false) or off (true), skipping triage
//   dimensions?: string[],        // size the analyst panel to exactly these axes; overrides both triage steps
//   forceFullPanel?: boolean,     // run every analyst axis and the challenge wave, skipping both triage steps
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
// A field counts as supplied only when it carries actual text. `prd.body = ''` and
// `prd.body = '   '` both used to sail through as "present" and hand every
// downstream agent an empty document.
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const repoPath = a.repoPath || (a.request && a.request.repoPath) || (a.prd && a.prd.repoPath) || null
// One Epic may span repos and a Story is scoped to exactly one, so spec authoring
// fans out once per repo below. Absent an explicit span the single repoPath is the
// whole span; null is filtered out rather than minted into a repo-less Story, which
// the work-item hierarchy forbids.
const repos = (Array.isArray(a.repos) && a.repos.length ? a.repos : [repoPath]).filter((r) => r != null)
if (!a.request && !a.prd) return { ok: false, stage: 'input', error: 'neither request nor prd supplied — refusing to run without a work item' }

// ── Run budget ──────────────────────────────────────────────────────────────────
// MAX_LOOPS bounds ONE gate. Nothing bounded the RUN, so a composite with five
// gates could spend 5 x MAX_LOOPS full phase attempts before returning, and an
// architecture attempt is ~17 agents. Runs measured at 2h+ were the result.
//
// A wall-clock ceiling is NOT expressible here: the workflow sandbox makes
// Date.now(), argless new Date(), and Math.random() throw, because they would
// break resume. So the ceiling is denominated in the two things the script CAN
// observe — phase attempts, and the token budget when the caller set one.
//
// The ceiling MUST scale with the fan-out, because most phases here are per-repo.
// A clean run with zero retries costs:
//     3 fixed gates (G1 PRD Validation, G2 Architecture, G2b TRD Authoring)
//   + 2 gates per repo (G3 Spec Authoring, G4 Task Decomposition)
// so 3 + 2N. A flat ceiling of 6 fit N=1 with one retry to spare and was
// mathematically unreachable from N=2 upward: a two-repo PRD needs 7 attempts to
// succeed perfectly on the first try. Every multi-repo PRD therefore died at G4
// with "run attempt budget exhausted" having never decomposed a single Story —
// and one Story per repo is the normal shape of this pipeline, not an edge case.
// Scaling the floor keeps the runaway protection (worst case is still
// (3 + 2N) * MAX_LOOPS, well above this) while guaranteeing a clean run always fits.
const FIXED_GATES = 3
const GATES_PER_REPO = 2
const RETRY_HEADROOM = a.retryHeadroom || 3
const MAX_TOTAL_ATTEMPTS =
  a.maxTotalAttempts || FIXED_GATES + GATES_PER_REPO * repos.length + RETRY_HEADROOM
// Floor below which a further expensive phase is not started. Only meaningful
// when the caller set a token target (budget.total); otherwise remaining() is
// Infinity and this never trips.
const BUDGET_FLOOR = a.budgetFloor || 60000
let attemptsSpent = 0
const budgetStop = () => {
  if (attemptsSpent >= MAX_TOTAL_ATTEMPTS) {
    return (
      `run attempt budget exhausted (${attemptsSpent}/${MAX_TOTAL_ATTEMPTS} phase attempts across ` +
      `${repos.length} repo(s)). Raise args.maxTotalAttempts to allow more.`
    )
  }
  // `typeof` guard, not a truthiness test: an undeclared identifier throws a
  // ReferenceError rather than reading as falsy, so a runtime that does not expose
  // `budget` would take the whole composite down here.
  if (typeof budget !== 'undefined' && budget && budget.total && budget.remaining() < BUDGET_FLOOR) {
    return `token budget floor reached (${Math.round(budget.remaining() / 1000)}k left, floor ${Math.round(BUDGET_FLOOR / 1000)}k).`
  }
  return null
}

// The work item this run is about. This composite has no bead of its own — the Epic is
// minted downstream — so the caller's PRD or request identifies it, and every return names
// it under the same key the code-writing composites use.
const subjectId = (a.prd && (a.prd.id || a.prd.path)) || (a.request && a.request.id) || (a.epic && a.epic.key) || null

// ── Partial results ─────────────────────────────────────────────────────────────
// Every stage used to end `return { ok:false, stage, detail }`, which threw away
// everything the run had already produced. A gate objection at Architecture
// discarded the validated PRD and the minted Epic; hours of work returned nothing
// actionable, so no PRD ever reached emission. Whatever exists is now carried out
// on EVERY exit path. A spec with one open question is worth more than {ok:false},
// and the caller — not this script — decides whether it is enough to act on.
const produced = {}
const partial = (stage, detail, extra) => {
  const salvage = { ...produced, ...(extra || {}) }
  runDetail = { stage, detail, partial: salvage }
  const why =
    (detail && detail.reason) ||
    (detail && detail.headline) ||
    (detail && detail.escalate ? `escalated to ${detail.escalate}` : null) ||
    `the ${stage} phase did not pass its gate`
  const unmet = (detail && detail.unmetCriteria) || []
  const keys = Object.keys(salvage)
  return {
    ok: false,
    stage,
    beadId: subjectId,
    headline:
      `${stage}: ${why}${unmet.length ? ` — unmet: ${unmet[0].criterion}` : ''}${unmet.length > 1 ? ` (+${unmet.length - 1} more)` : ''}. ` +
      (keys.length
        ? `${keys.length} artifact(s) were produced before it stopped and are in the run journal under \`partial\` (${keys.join(', ')}) — read them before re-running, because a fresh run reproduces exactly this work.`
        : 'Nothing had been produced when it stopped.'),
    // KEY NAMES only, never the artifacts. This is what makes the pointer actionable: the
    // caller can tell whether opening the journal is worth it without being handed
    // everything in order to find out.
    partialProduced: keys,
  }
}

// Decision ledger for over-time mining (see run-ledger-writer). Each instrumented
// mini returns a `ledger` on its artifact; collected here and persisted ONCE in a
// finally so it runs on success, early-return, and throw alike.
//
// It gets its OWN phase, and that is load-bearing. This agent used to be tagged
// `phase: 'Emit Beads'`, and because the finally runs on every exit path, a run
// that died at Gate 1 still ticked the terminal phase green — the progress panel
// reported a full Epic → Story → Task emission for a run that never reached
// Architecture. Telemetry must never be able to paint a work phase complete, so
// it reports under a phase that claims nothing about the work.
const runLedger = []
// Findings a gate could not get resolved inside its retry budget and that the
// advantage-evaluator then ruled COMPETITIVE — carried forward rather than fatal. See
// the exhaustion ruling below.
const carriedFlags = []
// ── The full detail, and where it goes ────────────────────────────────────────
// Every failure return used to carry `detail: <entire phase result>` alongside the whole
// `partial` bag, and the success return carried `results` — a complete artifact per phase.
// Single runs came back with 8.5k, 21k and 22k characters truncated off the end, and a
// campaign is hundreds of runs, so the DISPATCHING session dies long before the campaign
// finishes. That is a defect in the caller's context window, not in the run.
//
// Nothing is DISCARDED — the salvage principle behind `partial` below is intact and is
// the reason this had to be a journal rather than a deletion. The artifacts go to the run
// journal and the caller gets the path plus the list of what is in it, so it can still
// decide whether re-running is cheaper than reading. What changed is only that the caller
// opens the artifacts deliberately instead of receiving them whether it wanted them or not.
let runDetail = null
async function persistRun(outcome) {
  if (!runLedger.length && !runDetail) return null
  try {
    const written = await agent(
      `Persist this SDLC workflow run's decision ledger AND its full phase detail — the detail is no longer returned to the caller, so this journal is the only place it exists. JSON payload:\n${JSON.stringify({ composite: 'prd-to-spec', bead: null, subject: (a.prd && a.prd.id) || (a.request && a.request.id) || null, outcome, carriedFlags, runLedger, detail: runDetail })}`,
      {
        label: 'ledger:persist',
        phase: 'Run Ledger',
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
    return (written && written.path) || null
  } catch (e) {
    log(`ledger persist failed (non-fatal): ${e && e.message ? e.message : e}`)
    return null
  }
}

// ── The meta phase currently in progress ──────────────────────────────────────
// Every agent() dispatch names the phase it belongs to, and the phase titles are the
// ones in `meta` above. gateLoop is handed the gate's HUMAN name ("TDD Red"), which is
// not one of them, so the title is captured here as the composite enters each phase and
// the ruling dispatched from inside gateLoop can name it correctly.
let currentPhase = null
function enterPhase(title) {
  currentPhase = title
  phase(title)
}

// ── What the CALLER receives ──────────────────────────────────────────────────
// One shape, everywhere: `{ ok, stage, beadId, headline, detailPath }`. The headline is
// the one line a caller can act on without opening anything; `detailPath` (attached in
// the `finally` below, once the journal has been written) is where everything else went.
// The settle verdict is added on top by applySettle — that is the run's LANDING status,
// not phase state, it is a handful of scalars, and an orphaned worktree must be
// impossible to miss.
function handback(ok, stage, headline, detail) {
  runDetail = detail === undefined ? null : detail
  return { ok, stage, beadId: subjectId, headline: String(headline || '') }
}

// Turn a gate result into that one line. An exhausted or escalated gate already knows
// WHAT was unmet and on what evidence; a headline that says only "green failed" makes
// the caller open the journal to learn anything at all.
function gateHeadline(stage, r) {
  const unmet = (r && r.unmetCriteria) || []
  const why = (r && r.reason) || (r && r.escalate ? `escalated to ${r.escalate}` : 'the gate did not pass')
  const first = unmet.length ? ` — unmet: ${unmet[0].criterion}` : ''
  const more = unmet.length > 1 ? ` (+${unmet.length - 1} more)` : ''
  return `${stage}: ${why}${first}${more}`
}

// ── Loop exhaustion is a RULING, not a halt ───────────────────────────────────
//
// Spending the retry budget says nothing about whether the objection that REMAINS
// invalidates the work. MAX_LOOPS' own comment above states the intent — "One rework
// round, then proceed with the finding recorded" — and the code did the opposite:
// exhaustion returned ok:false, every caller treats ok:false as terminal, and the run
// died. It died identically whether the unmet criterion was a security violation or a
// reviewer's opinion that coverage was incomplete, which erases the distinction this
// framework is built on — constitutive findings are hard stops, competitive ones proceed
// under a flag.
//
// ssbd-97as is the case that proves the cost. A P0 live outage reached the Red gate with
// redConfirmed=true, 7 test files authored, 11 correctly-failing tests captured, ruff
// clean, and not one production file touched. The blocking objection was "AC5 partially
// covered — two of three clauses unassessed". The budget ran out and nothing shipped.
//
// So an exhausted gate now asks the agent whose entire purpose is that ruling. The
// advantage-evaluator already applies the advantage principle at a PASSING gate inside
// gate-enforce and "never halts the pipeline for non-invalidating findings"; this is the
// same question arriving from the other end of the loop, and it is dispatched the same
// way. It is given the unmet criteria, the artifact the phase produced, and the gate's
// DETERMINISTIC-check results — those last matter most, because a check the gate measured
// directly against the artifact is not a matter of opinion and must not be waived as one.
//
// It FAILS CLOSED. An evaluator that throws, returns nothing, or names no ruling has not
// ruled anything competitive; reading silence as permission would turn every dispatch
// failure into a waived gate.
async function ruleExhaustion(ctx) {
  const unmet = ctx.unmetCriteria || []
  const dchecks = (ctx.verdict && ctx.verdict.deterministicChecks) || []
  try {
    return await agent(
      `You are the advantage-evaluator. Gate ${ctx.gate} (${ctx.phaseName}) has spent its entire rework budget of ${MAX_LOOPS} attempt(s) and the criteria below are still unmet.

This is NOT a request to re-judge the work, and it is NOT a request to halt. Rule on ONE question: does what remains INVALIDATE the artifact, or does it merely make it less than ideal?

- "constitutive": the finding invalidates the work. A security violation, a broken contract, an assertion that cannot hold, a claim the evidence does not support, or work that was never actually produced. Only these stop a run.
- "competitive": the finding is a quality or completeness opinion the work survives. Partial coverage of an acceptance criterion, an unassessed edge case, a style preference, a reviewer wanting more than was asked for. These are recorded as flags and the pipeline PROCEEDS — you never halt for a non-invalidating finding.

A criterion a DETERMINISTIC check settled against the phase is constitutive by construction: it was measured against the artifact, not argued about, so there is nothing left for you to weigh.

Unmet criteria after ${MAX_LOOPS} attempt(s):
${unmet.length ? unmet.map((c, i) => `${i + 1}. ${c.criterion}\n   evidence: ${c.evidence || '(none given)'}`).join('\n') : '(the gate named none)'}

Deterministic checks this gate evaluated directly against the artifact:
${dchecks.length ? dchecks.map((c) => `- ${c.criterion}: ${c.met ? 'MET' : 'NOT MET'} — ${c.evidence}`).join('\n') : '(this gate declared none)'}

The artifact the phase produced:
${JSON.stringify(ctx.artifact === undefined ? null : ctx.artifact, null, 2)}

Rule "constitutive" if ANY remaining finding invalidates the work; otherwise rule "competitive" and classify each finding.`,
      {
        label: `advantage:exhausted-${ctx.gate}`,
        phase: currentPhase || 'PRD Validation',
        agentType: 'agent-teams-workforce:advantage-evaluator',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['ruling', 'findings', 'rationale'],
          properties: {
            ruling: { type: 'string', enum: ['competitive', 'constitutive'] },
            findings: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['criterion', 'classification', 'rationale'],
                properties: {
                  criterion: { type: 'string' },
                  classification: { type: 'string', enum: ['competitive', 'constitutive'] },
                  rationale: { type: 'string' },
                },
              },
            },
            rationale: { type: 'string' },
          },
        },
      }
    )
  } catch (e) {
    log(`advantage-evaluator failed to rule on gate ${ctx.gate} exhaustion: ${e && e.message ? e.message : e}`)
    return null
  }
}

// Run a phase, judge it at an INDEPENDENT gate, apply the verdict.
async function gateLoop({ gate, phaseName, criteria, checks, escalateTargets, phaseFn, gateWorkflow }) {
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

  // Kept across attempts so a loop-exhausted exit still hands back the last thing
  // the phase produced. It used to return nothing at all, which is why an exhausted
  // gate erased the whole phase rather than just failing it.
  let lastArtifact = null
  // Carried across attempts so loop exhaustion can say WHAT was unmet and on what
  // evidence, instead of a bare count. Both are computed at every attempt already;
  // the exhaustion path simply never saw them.
  let lastVerdict = null
  const attempts = []
  for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
    // The run-wide budget is checked BEFORE the expensive call, not after, so the
    // ceiling actually prevents spend instead of reporting it.
    const stop = budgetStop()
    if (stop) {
      log(`Gate ${gate} (${phaseName}): STOPPING before attempt ${attempt} — ${stop}`)
      recordGate(attempt, null, { terminal: 'budget-exhausted', budgetReason: stop })
      return { ok: false, reason: `gate ${gate} stopped by run budget: ${stop}`, artifact: lastArtifact, budgetExhausted: true }
    }
    // Announce the START of the attempt. The progress panel cannot tick this phase:
    // its work happens inside a nested workflow(), whose agents the engine puts in
    // their own "▸ <mini>" group rather than counting toward the parent phase. So
    // without this line a phase that is actively running reads as "Not started yet",
    // and only its verdict — logged below, after the fact — ever proves it ran.
    log(`Gate ${gate} (${phaseName}): running attempt ${attempt}/${MAX_LOOPS} (run attempt ${attemptsSpent + 1}/${MAX_TOTAL_ATTEMPTS})`)
    attemptsSpent++
    // The second argument is the STRUCTURED loop channel. A free-text string cannot
    // carry which criteria were unmet, nor what the phase produced last time. Existing
    // call sites that take only `feedback` are unaffected.
    const artifact = await phaseFn(feedback, {
      attempt,
      maxLoops: MAX_LOOPS,
      feedback,
      priorArtifact: lastArtifact,
      priorVerdicts: attempts.map((x) => x.verdict).filter(Boolean),
      unmetCriteria: lastVerdict ? ((lastVerdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence }))) : [],
    })
    lastArtifact = artifact
    const verdict = await workflow(gateWorkflow || 'agent-teams-workforce:gate-enforce', {
      gate, phaseName, criteria, checks, artifact, escalateTargets,
    })
    if (!verdict) {
      recordGate(attempt, null, { terminal: 'no-verdict' })
      return { ok: false, reason: `gate ${gate} returned no verdict`, artifact }
    }
    recordGate(attempt, verdict)
    lastVerdict = verdict
    attempts.push({
      attempt,
      verdict,
      feedback: verdict.feedback || null,
      unmetCriteria: (verdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence })),
    })
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
  // The budget is spent. Before this is called a failure, the ONE agent with authority to
  // say whether the remaining findings invalidate the work is asked — see ruleExhaustion.
  const exhaustedUnmet = lastVerdict
    ? (lastVerdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence }))
    : []
  const ruling = await ruleExhaustion({ gate, phaseName, artifact: lastArtifact, verdict: lastVerdict, unmetCriteria: exhaustedUnmet })
  // TRUTHINESS IS NOT A RULING. A result object that came back without a `ruling` field
  // has not ruled anything, and reading it as one made a malformed reply indistinguishable
  // from a considered "constitutive" — which is the reporting half of the same fail-closed
  // mistake the verdict half already avoids.
  const ruled = !!(ruling && (ruling.ruling === 'competitive' || ruling.ruling === 'constitutive'))
  const competitive = !!(ruling && ruling.ruling === 'competitive')
  // Record the REAL final verdict, not null, and the ruling made on it. A terminal ledger
  // row with `criteria: []` cannot distinguish a genuine defect from an over-strict
  // criterion — which is the one question anyone asks about an exhausted gate.
  recordGate(MAX_LOOPS, lastVerdict, {
    verdict: competitive ? 'loop-exhausted-competitive' : 'loop-exhausted',
    terminal: competitive ? 'proceeded-under-flag' : 'loop-exhausted',
    advantageRuling: ruling || null,
  })
  // Hand the artifact back on either outcome. The phase ran and produced something; the
  // gate simply would not certify it. Discarding it forces the next run to pay for
  // identical work, and denies the caller the one thing that would let them judge
  // whether the objection is worth another round.
  if (competitive) {
    const flags = exhaustedUnmet.map((cc) => `gate ${gate} (${phaseName}) proceeded with an unmet criterion: ${cc.criterion}${cc.evidence ? ` — ${cc.evidence}` : ''}`)
    for (const f of flags) carriedFlags.push(f)
    log(`Gate ${gate} (${phaseName}): budget spent — advantage-evaluator ruled the remaining finding(s) COMPETITIVE; proceeding with ${flags.length} flag(s) recorded`)
    return {
      ok: true,
      loopExhausted: true,
      ruledCompetitive: true,
      carriedFlags: flags,
      advantageRuling: ruling,
      artifact: lastArtifact,
      verdict: lastVerdict,
      unmetCriteria: exhaustedUnmet,
      attempts,
    }
  }
  log(
    `Gate ${gate} (${phaseName}): budget spent — ` +
      (ruled ? 'advantage-evaluator ruled the remaining finding(s) CONSTITUTIVE' : 'no ruling came back, so the findings are treated as constitutive (fail closed)')
  )
  return {
    ok: false,
    reason: `gate ${gate} exceeded ${MAX_LOOPS} loops and the remaining finding(s) were ruled constitutive${ruled ? '' : ' by default — the advantage-evaluator returned no ruling'}`,
    loopExhausted: true,
    ruledCompetitive: false,
    advantageRuling: ruling || null,
    artifact: lastArtifact,
    verdict: lastVerdict,
    unmetCriteria: exhaustedUnmet,
    attempts,
  }
}

// ── PRD Creation (optional) ────────────────────────────────────────────────────
// Only when a raw request is supplied and no PRD already exists. The created PRD
// becomes the input to validation; otherwise the supplied PRD is used directly.
let result
try {
  result = await (async () => {
enterPhase('PRD Creation')
let creation = null
let prd = a.prd || null
if (!prd && a.request) {
  log(`Creating PRD from request ${a.request.id || '(no id)'} — ${a.request.title || ''}`)
  creation = await workflow('agent-teams-workforce:prd-creation', { request: a.request })
  if (!creation || !creation.ok) {
    return handback(false, 'prd-creation', 'PRD creation did not produce an aligned PRD', creation)
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
if (!prd) return handback(false, 'prd-creation', 'no PRD available to validate (supply args.prd or args.request)')

// ── PRD text resolution ─────────────────────────────────────────────────────────
// The args contract advertises body, content and path; only `body` was ever read.
// `path` was used solely as a reference label on the minted Epic and `content` was
// read nowhere at all, so a caller who supplied either — both of which the contract
// invites — got a run in which every downstream agent received an empty PRD. The
// failure did not surface at dispatch: it surfaced minutes and a full analyst
// fan-out later, as G1 correctly refusing to validate nothing. Run wf_63a9f03f-6d7
// died exactly this way.
//
// All three fields are now honoured, in the order body -> content -> path, and a
// PRD that still carries no text after that is rejected HERE rather than several
// phases downstream. Scripts have no filesystem access but agents do, so `path` is
// resolved by one cheap agent that reads the file and threads its text back.
if (!hasText(prd.body)) {
  if (hasText(prd.content)) {
    prd = { ...prd, body: prd.content }
    log('PRD text taken from prd.content')
  } else if (hasText(prd.path)) {
    log(`PRD text absent — reading it from prd.path: ${prd.path}`)
    const read = await agent(
      `Read the PRD document at the path below and return its FULL text verbatim.

Path: ${prd.path}

Return the entire file contents in \`body\`. Do NOT summarize it, do NOT truncate it, do NOT reformat it, and do NOT comment on it — every downstream agent in this pipeline reads the PRD from what you return, so anything you drop is dropped from the whole run.

If the path does not resolve to a readable file, set ok=false and say why in \`error\`. Do not invent content and do not substitute a different file.`,
      {
        label: 'resolve:prd-text',
        phase: 'PRD Creation',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['ok'],
          properties: {
            ok: { type: 'boolean' },
            body: { type: 'string' },
            resolvedPath: { type: 'string' },
            error: { type: 'string' },
          },
        },
      }
    )
    if (!read || read.ok !== true || !hasText(read.body)) {
      return {
        ok: false,
        stage: 'input',
        beadId: subjectId,
        error:
          `prd.path was supplied (${prd.path}) but no PRD text could be read from it` +
          `${read && read.error ? `: ${read.error}` : ''}. ` +
          'Correct the path, or pass the PRD text inline as prd.body.',
      }
    }
    prd = { ...prd, body: read.body, path: read.resolvedPath || prd.path }
    log(`PRD text read from ${prd.path} (${read.body.length} chars)`)
  } else {
    return {
      ok: false,
      stage: 'input',
      beadId: subjectId,
      error:
        'the supplied PRD carries no text — none of prd.body, prd.content or prd.path resolved to a document. ' +
        'Every downstream agent reads the PRD from this field, so a run without it validates an empty document.',
    }
  }
}

// ── PRD Reconciliation (no gate) ────────────────────────────────────────────────
// A PRD states what someone WANTED. It has never stated what is MISSING, and until
// now nothing in this composite read the codebase at all — the six PRD-validation
// analysts judge the document, not the system. So a PRD written against a capability
// that partly or largely shipped got specified, decomposed, and built a second time
// on top of working code. An audit of 20 Epics in one project found ELEVEN written
// as greenfield against shipped behaviour: a 929-line MFA implementation that was
// merely disabled at one CDK line, a fully deployed passkey ceremony, three of four
// identity providers live, a shipped session dashboard with revoke and revoke-all.
//
// Reality is therefore established FIRST, and everything downstream reads the DELTA
// PRD — the requirements genuinely absent or partial — never the original ambition.
//
// This phase spends NO GATE, and that is the point of its position: a work item that
// is already built, or that is really a bug or an infrastructure flag, is settled
// here for the cost of two read-only checkers rather than after G1 has convened six
// analysts and G2 an architecture panel against work that does not need doing.
enterPhase('PRD Reconciliation')
const reconciliation = await workflow('agent-teams-workforce:prd-reconciliation', {
  prd,
  repos,
  dependencies: a.dependencies,
  deltaPath: a.deltaPath,
})
if (reconciliation && reconciliation.ledger) runLedger.push(reconciliation.ledger)
produced.originalPrd = prd
produced.reconciliation = reconciliation || null
if (!reconciliation || reconciliation.ok === false) {
  // A failed reconciliation is NOT a zero delta. Reading "we could not establish what
  // exists" as "nothing exists" is the exact greenfield assumption this phase removes,
  // so the run stops instead of proceeding against the original PRD.
  return partial('prd-reconciliation', {
    reason:
      (reconciliation && reconciliation.reason) ||
      'PRD reconciliation returned nothing — what already ships could not be established.',
    detail: reconciliation || null,
  })
}
log(
  `Reconciliation: ${reconciliation.verdict} — ${reconciliation.deltaCount} requirement(s) remain, sized '${reconciliation.sizeVerdict}'.`
)

// Short-circuit 1: nothing is left to build. Closing costs no gate.
if (reconciliation.deltaCount === 0) {
  // `action` and `deltaCount` survive the trim because they are the DECISION this exit
  // reached, not phase state, and the caller acts on them directly. The per-requirement
  // evidence behind the decision goes to the journal with everything else.
  return {
    ...handback(
      true,
      'prd-reconciliation',
      `every requirement this PRD states is already shipped or obsolete (${reconciliation.verdict}) — nothing was specified, decomposed, or gated. Close the work item; the per-requirement evidence is in the run journal under \`requirements\`.`,
      { action: 'close', reconciliation, prd, epic: a.epic || null }
    ),
    action: 'close',
    deltaCount: 0,
  }
}

// Short-circuit 2: what remains is not a product increment. A defect in shipped
// behaviour, or an infrastructure switch, does not need a PRD, an architecture
// ruling, a TRD or a spec — it needs the composite that owns that shape of work.
// Routing it here, before G1, is what keeps a one-line flag change from consuming
// the full elaboration pipeline.
if (reconciliation.sizeVerdict === 'bug' || reconciliation.infraOnly) {
  const composite = reconciliation.infraOnly ? 'infra-change' : 'bug-fix'
  // `action`, `composite` and `deltaPrdPath` survive the trim: they are the routing
  // INSTRUCTION this exit exists to give, and a caller that has to open a journal to learn
  // where to send the work has not been routed.
  return {
    ...handback(
      true,
      'prd-reconciliation',
      `the remaining delta (${reconciliation.deltaCount} requirement(s)) is ${reconciliation.infraOnly ? 'satisfiable by an infrastructure change alone' : 'a defect in behaviour that already exists'}, ` +
        `so it routes to agent-teams-workforce:${composite}. No gate was spent. The delta PRD is at ${reconciliation.deltaPrdPath}.`,
      { action: 'reroute', composite, reconciliation, prd }
    ),
    action: 'reroute',
    composite,
    deltaCount: reconciliation.deltaCount,
    deltaPrdPath: reconciliation.deltaPrdPath,
  }
}

// ── Everything downstream consumes the DELTA, never the raw incoming PRD ────────
// Rebinding `prd` here is deliberate and load-bearing: validation, architecture, the
// TRD, every spec and every task set read this binding, so narrowing it once is what
// guarantees none of them can reach the original. The original is kept under
// `produced.originalPrd` for the record.
if (!hasText(reconciliation.deltaPrdPath) || !reconciliation.deltaPrd || !hasText(reconciliation.deltaPrd.body)) {
  return partial('prd-reconciliation', {
    reason:
      `${reconciliation.deltaCount} requirement(s) remain but no usable delta PRD came back. ` +
      'Refusing to continue against the original PRD — that is how shipped behaviour gets specified again.',
    detail: reconciliation,
  })
}
const originalPrd = prd
prd = {
  ...prd,
  body: reconciliation.deltaPrd.body,
  content: reconciliation.deltaPrd.body,
  path: reconciliation.deltaPrdPath,
  reconciledFrom: originalPrd.path || originalPrd.id || originalPrd.title || null,
}
produced.deltaPrd = { path: reconciliation.deltaPrdPath, deltaCount: reconciliation.deltaCount }
log(
  `Downstream phases now read the delta PRD at ${prd.path} (${reconciliation.deltaCount} of ` +
    `${reconciliation.requirements.length} requirement(s)); the original is retained under partial.originalPrd.`
)

// ── PRD Validation (Gate 1) ─────────────────────────────────────────────────────
enterPhase('PRD Validation')
const validation = await gateLoop({
  gate: 'G1', phaseName: 'PRD Validation',
  criteria: [
    'No unresolved internal contradictions between requirements that cannot be built around (a genuine WHAT-level conflict)',
    'Every requirement the PRD STATES names an actor, a trigger, and an observable outcome. Judge ONLY what the PRD claims. A PRD is a business requirement and may be a single sentence — it is NOT required to define the surrounding feature, screen, or system, and omitting that context is NOT a defect.',
    'Do NOT fail a PRD for anything the SAD, TRD, or spec owns: crosscutting quality intent (privacy, security, accessibility, abuse-resistance), bounded-context placement, dependency naming or readiness, error/empty/cancel paths, mechanism, algorithms, thresholds, schemas, quantified NFRs, or SLOs. Those are defined downstream and their absence here is correct, not missing.',
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
produced.prd = prd
produced.validation = validation.artifact || null
if (!validation.ok) return partial('prd-validation', validation)
const validatedPrd = (validation.artifact && validation.artifact.validatedPrd) || prd
produced.validatedPrd = validatedPrd

// ── Epic (adopt / mint) ─────────────────────────────────────────────────────────
// A PRD and its Epic are ONE work item in two representations — the document and
// the bead — so past this point both faces must exist. Either the caller already
// holds the Epic, or prd-creation minted the pair together, or only the PRD exists
// and its bead face is MINTED here from the validated PRD. Minting completes the
// representation; it derives nothing the PRD does not already state.
//
// A CALLER-SUPPLIED EPIC WINS, and that ordering is load-bearing. This used to test
// prd-creation's Epic first, so a caller that passed an existing Epic *and* a raw
// request got the freshly minted one and its own was silently discarded — two Epic
// beads for one PRD, which is precisely the pairing rule breaking at the point it
// most needs to hold. The Epic-without-a-PRD entry hits exactly that combination:
// it passes the existing Epic and supplies the bead's content as the request so the
// PRD document gets authored.
enterPhase('Epic')
let epic
let epicPath
if (a.epic) {
  // A caller-supplied Epic is adopted rather than re-minted, but it still has to
  // leave here as a well-formed epic bead spec — a caller that passed only a key
  // and a title would otherwise put an untyped object into the hierarchy.
  epic = {
    key: a.epic.key || a.epic.id || 'E1',
    ...a.epic,
    type: 'epic',
  }
  epicPath = 'epic-supplied'
  if (creation && creation.epic) {
    log('Epic supplied by the caller AND minted by prd-creation — adopting the caller\'s and discarding the mint; one PRD has exactly one Epic')
  }
} else if (creation && creation.epic) {
  epic = creation.epic
  epicPath = 'epic-created'
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
  epicPath = 'epic-minted'
}
produced.epic = epic
produced.epicPath = epicPath
log(
  `Epic ${epic.key || '(no key)'} via ${epicPath}${
    epicPath === 'epic-minted' ? ` — bead face minted for existing PRD ${epic.prdRef || '(unreferenced)'}` : ''
  }`
)

// ── Architecture (Gate 2 — constitutional) ──────────────────────────────────────
// Consumes the validated PRD; produces the ruled decision + arc42 SAD source feed.
enterPhase('Architecture')
// Not every PRD contains an architecture decision. This phase is the most
// expensive in the composite — a full analyst panel plus a challenge wave, ~17
// agents — and it ran unconditionally, so a single-repo UI feature with nothing
// to decide still convened persistence, event-schema, and API-contract analysts
// against a repo that has no persistence, publishes no events, and serves no API.
// Analysts handed nothing to analyze do not return "nothing"; they invent scope,
// and the invented scope then fails the gate.
//
// One cheap agent decides whether the panel is warranted. It CANNOT skip on its
// own judgement of difficulty — only on the absence of a decision, or on the SAD
// having already settled every one this PRD raises.

// The analyst axes the `architecture` mini can dispatch. Kept in step with
// ALL_DIMENSIONS in architecture.js: this composite's triage names axes from this
// list and the mini filters against its own, so an axis missing from either side
// is silently dropped rather than mis-dispatched.
const ARCH_DIMENSIONS = ['integration', 'security', 'cost', 'persistence', 'cdk', 'bounded-context', 'failure-mode']
let archNeeded = true
let archTriage = null
if (a.skipArchitecture === true) {
  archNeeded = false
  archTriage = { needed: false, reason: 'caller passed skipArchitecture:true', settledBy: 'caller' }
} else if (a.skipArchitecture === false) {
  archTriage = { needed: true, reason: 'caller passed skipArchitecture:false', settledBy: 'caller' }
} else {
  // The prompt is hoisted so the retry below sends exactly the same question. A
  // retry that reworded it would be asking a different one.
  const triagePrompt =
    `Decide whether this PRD requires an ARCHITECTURE DECISION phase, or whether it can go straight to TRD authoring.\n\n` +
      `An architecture decision exists when the PRD forces a CHOICE BETWEEN OPTIONS whose consequences outlive the feature: a new datastore or a new access pattern, a new service or a new boundary between services, a new integration or transport, a new trust boundary, or a change to a crosscutting concern.\n\n` +
      `It does NOT exist merely because the work is hard, security-adjacent, or user-facing. A feature that composes existing decisions — a screen in an existing app, a field on an existing form, a call to an endpoint whose contract another PRD owns — raises NO architecture decision even when it is difficult.\n\n` +
      `Answer needed:false when EITHER there is no such choice, OR the SAD already settles every choice this PRD raises (name the sections).\n` +
      `Answer needed:true when even one unsettled choice remains. When uncertain, answer true: a wrongly-run panel costs tokens, a wrongly-skipped one costs a bad decision.\n\n` +
      `Repos this PRD spans (${repos.length}): ${repos.join(', ') || '(none named)'}\n` +
      `SAD location: ${a.sadPath || '(not supplied)'}\n\n` +
      `PRD:\n${validatedPrd.body || prd.body || '(no body supplied)'}` +
      `\n\nWhen needed is true, ALSO name in \`dimensions\` the analysis axes this decision could genuinely turn on, drawn from ${JSON.stringify(ARCH_DIMENSIONS)}. Include an axis only where the decision could plausibly turn on it, never by reflex: each axis you name costs an analyst, and each one you omit is an angle the panel will not cover. Leave the list empty only when you cannot tell — that runs every axis.`
  const triageOpts = {
    label: 'triage:architecture-needed',
    phase: 'Architecture',
    agentType: 'agent-teams-workforce:architecture-decider',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['needed', 'reason'],
      properties: {
        needed: { type: 'boolean' },
        reason: { type: 'string' },
        decisions: { type: 'array', items: { type: 'string' } },
        settledBy: { type: 'string' },
        dimensions: { type: 'array', items: { type: 'string', enum: ARCH_DIMENSIONS } },
      },
    },
  }
  archTriage = await agent(triagePrompt, triageOpts)
  // A null triage means the agent DIED, not that no decision exists — so failing
  // open runs the most expensive phase in the composite, and one transient agent
  // failure used to cost a full analyst panel plus a challenge wave. Failing open
  // is still the right default; paying for it without asking twice is not.
  if (!archTriage) {
    log('Architecture triage returned nothing — retrying once before failing open to the full panel')
    archTriage = await agent(triagePrompt, { ...triageOpts, label: 'triage:architecture-needed (retry)' })
  }
  archNeeded = !archTriage || archTriage.needed !== false
}
let architecture
if (!archNeeded) {
  log(`Architecture SKIPPED — ${(archTriage && archTriage.reason) || 'no architecture decision in this PRD'}`)
  architecture = { ok: true, skipped: true, artifact: { skipped: true, triage: archTriage } }
} else {
  if (archTriage && archTriage.decisions && archTriage.decisions.length) {
    log(`Architecture NEEDED — ${archTriage.decisions.length} open decision(s): ${archTriage.decisions.join('; ')}`)
  }
  // Panel sizing, from the caller when they named it and from this composite's own
  // triage otherwise. Without it the mini re-derives what triage has just worked
  // out: this composite spends an architecture-decider call deciding whether a
  // decision exists, and the mini then spends an architecture-boundary-guardian
  // call deciding whether it is settled and which axes bear on it. Handing the axes
  // down collapses the second triage instead of paying for it twice.
  //
  // An empty list is NOT passed through: architecture.js treats an empty
  // `dimensions` as "no override" and runs its own triage, which is the correct
  // behaviour when triage could not name the axes.
  const callerDimensions = Array.isArray(a.dimensions)
    ? a.dimensions.filter((d) => ARCH_DIMENSIONS.includes(d))
    : null
  const triageDimensions = (archTriage && Array.isArray(archTriage.dimensions) ? archTriage.dimensions : []).filter(
    (d) => ARCH_DIMENSIONS.includes(d)
  )
  const archDimensions =
    callerDimensions && callerDimensions.length
      ? callerDimensions
      : triageDimensions.length
        ? triageDimensions
        : undefined
  if (a.forceFullPanel === true) {
    log('Architecture panel: FULL — caller passed forceFullPanel')
  } else if (archDimensions) {
    log(
      `Architecture panel sized to ${archDimensions.length}/${ARCH_DIMENSIONS.length} axes ` +
        `(${callerDimensions && callerDimensions.length ? 'caller' : 'triage'}): ${archDimensions.join(', ')}`
    )
  } else {
    log('Architecture panel: not sized here — the mini will run its own triage')
  }
  // What the architecture phase is told, and what it is NOT told.
  //
  // The decision's `context` slot used to carry `validation.artifact.summary` —
  // the prd-validation-lead's consolidated FINDINGS report, written by the
  // analysts BEFORE the gate adjudicated their severities. Two things went wrong
  // at once, and run wf_e1736f55-1fe showed both: the panel never received the
  // PRD it was convened to analyze, and what it received instead was a defect
  // report closing with "Recommend returning to the PRD owner to resolve the two
  // blockers". The coordinator held on that basis, its HOLD propagated through
  // the framing into all seven analysts, and every one of them returned
  // STATUS: BLOCKED without opening its lens. A phase whose gate had PASSED
  // produced zero proposals and escalated.
  //
  // The PRD is the artifact under analysis, so the PRD is the context. G1's
  // outcome travels separately as a driver, and it is the GATE's verdict rather
  // than the lead's draft — because the gate is what settles severity. A finding
  // the gate declined to uphold is CLOSED, and must not travel downstream still
  // wearing the grading the gate removed.
  //
  // The flags themselves are deliberately NOT forwarded. They are written in the
  // analysts' voice, and reproducing that voice is what caused the panel to
  // stand down in the first place.
  const g1 = (validation.verdict && validation.verdict.verdict) || 'pass'
  const archDrivers = [
    `Gate G1 (PRD validation) returned ${String(g1).toUpperCase()}. The PRD in Context is VALIDATED.`,
    'Findings raised during validation were adjudicated AT that gate. Any the gate did not uphold are closed. ' +
      'Do NOT treat validation-phase findings as open defects, and do NOT withhold analysis on account of them — ' +
      'if you believe the PRD is undecidable, say so about text you have read in the PRD itself.',
    ...(Array.isArray(a.decision && a.decision.drivers) ? a.decision.drivers : []),
  ]

  architecture = await gateLoop({
    gate: 'G2', phaseName: 'Architecture', gateWorkflow: 'agent-teams-workforce:gate-constitutional',
    criteria: [
      'The chosen architecture honors all platform constitutive bans (no Step Functions, no HTTP API v2, no FastAPI/Flask/Django, REST v1 only, Powertools-only, service isolation, SSM-not-CFN-exports, dot-only event naming)',
      'Every significant decision is ruled by the decider and recorded in the SAD/arc42 source feed',
      // This criterion used to read "No security or data-isolation finding is left
      // open or downgraded", which no real architecture can satisfy: every honest
      // threat model ends in accepted residual risk, so a correctly-done security
      // analysis failed the gate BECAUSE it was done correctly. Any security-adjacent
      // PRD then burned its full loop budget against an unsatisfiable bar and the run
      // returned nothing. What the criterion is actually for is catching findings
      // nobody addressed, or ones quietly waved through — so it now says that.
      'No security or data-isolation finding is left UNMITIGATED or silently downgraded. ' +
        'A finding that has been mitigated, and whose remaining exposure is recorded in the SAD as an accepted residual with its mitigations and rationale stated, SATISFIES this criterion — recorded residual risk is the expected output of a threat model, not a defect. ' +
        'Fail only when: a finding has no mitigation at all; or a residual is undocumented; or the residual could be eliminated by a change THIS phase owns and was not. ' +
        'If elimination would require changing the PRD, that is an UPSTREAM defect — return escalate (escalateTo prd-validation), never loop, because re-running architecture cannot fix a requirement.',
    ],
    escalateTargets: ['prd-validation'],
    phaseFn: (feedback) =>
      workflow('agent-teams-workforce:architecture', {
        decision: a.decision || {
          id: prd.id,
          title: `Architecture for ${prd.title || prd.id || 'PRD'}`,
          context: validatedPrd.body || prd.body || '',
          drivers: archDrivers,
          repoPath,
        },
        sadPath: a.sadPath,
        dimensions: archDimensions,
        forceFullPanel: a.forceFullPanel === true ? true : undefined,
        feedback,
      }),
  })
}
if (architecture.artifact && architecture.artifact.ledger) runLedger.push(architecture.artifact.ledger)
produced.architecture = architecture.artifact || null
if (!architecture.ok) return partial('architecture', architecture)
const sadExtract = architecture.artifact && architecture.artifact.sadUpdate

// ── TRD Authoring (Gate 2b) ──────────────────────────────────────────────────────
// Consumes PRD + SAD extract; produces the TRD + bidirectional traceability matrix.
// The TRD is per-PRD, not per-repo: it is authored exactly ONCE here and never
// fanned out with the per-repo spec passes below.
enterPhase('TRD Authoring')
const trdAuthoring = await gateLoop({
  gate: 'G2b', phaseName: 'TRD Authoring',
  criteria: [
    'The TRD derives only from the PRD and the SAD source extract (no invented requirements)',
    'Every PRD requirement that NEEDS technical elaboration has a TRD entry. A requirement needing none is NOT a gap, and a TRD may elaborate part of a PRD — the product is built iteratively. Do NOT require bidirectional or total coverage.',
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
produced.trdAuthoring = trdAuthoring.artifact || null
if (!trdAuthoring.ok) return partial('trd-authoring', trdAuthoring)
const trd = trdAuthoring.artifact && trdAuthoring.artifact.trd

// ── Spec Authoring (Gate 3 — once per repo) ──────────────────────────────────────
// Consumes TRD + SAD extract; produces API/data/event/error specs + AC + DoD.
// A Spec and its Story are created together and a Story is scoped to one repo, so
// this phase fans out across args.repos: one (spec, story) pair per repo, every
// Story parented to the Epic above. Each repo faces its own G3 gate, and a repo
// whose spec fails its gate is RECORDED in the result — never silently dropped.
enterPhase('Spec Authoring')
if (!repos.length) {
  return partial(
    'spec-authoring',
    { reason: 'no repos to author specs for — a Story is scoped to a single repo; supply args.repos or args.repoPath' }
  )
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
produced.specPairs = specPairs
produced.specFailures = specFailures
// A failure in ONE repo used to end the run for ALL of them, so a three-repo PRD
// where two specs were clean and one was not emitted nothing for any of the three.
// Repo failures are independent — a Story is scoped to a single repo by
// construction — so the passing repos now carry on to decomposition and the
// failures ride along in the result. Only a total washout stops the run.
if (specFailures.length) {
  log(
    `Spec Authoring: ${specFailures.length} repo(s) failed G3, ${specPairs.length} passed — ` +
      `${specPairs.length ? 'continuing with the repos that passed' : 'no repo produced a spec'}`
  )
}
// The headline has to name the underlying cause, not just the phase. The failures are a
// LIST — one per repo — and the reason each repo failed lives one level down on its gate
// result; a caller told only "spec-authoring did not pass its gate" learns nothing it
// could act on, and a run starved by the token budget reads identically to one rejected on
// its merits.
if (!specPairs.length) {
  return partial('spec-authoring', {
    reason:
      'no repo produced a spec — ' +
      (specFailures
        .map((x) => `${x.repoPath}: ${(x.detail && x.detail.reason) || x.reason || 'gate failure'}`)
        .join('; ') || 'no per-repo failure was recorded'),
    specFailures,
  })
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
    // The cycle itself stays: it is a short list of Story keys and it is the whole finding.
    return {
      ...handback(
        false,
        'story-dependencies',
        `the Story dependency graph is not acyclic — cycle: ${((mapped && mapped.cycle) || []).join(' -> ') || '(not reported)'}`,
        { cycle: (mapped && mapped.cycle) || [], prd: validatedPrd, epic, stories: depStories }
      ),
      cycle: (mapped && mapped.cycle) || [],
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
enterPhase('Task Decomposition')
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
      'Every task is WSJF-scored. The score is a prioritization aid, NOT a correctness gate — do NOT block emission on the value of a score or on review of it.',
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
produced.stories = stories
produced.decompositions = decompositions
produced.decompositionFailures = decompositionFailures
produced.tasks = tasks
// Same rule as spec authoring: one Story failing to decompose does not invalidate
// the Stories that did. The run continues to emission with the tasks it has, and
// the failed Stories are reported so they can be re-run on their own rather than
// dragging their siblings' work down with them.
if (decompositionFailures.length) {
  log(
    `Task Decomposition: ${decompositionFailures.length} story/stories failed G4, ${decompositions.length} passed — ` +
      `${tasks.length} task(s) still emitted`
  )
}
// Same reason as the spec-authoring exit above: the cause is one level down, per Story.
if (!decompositions.length) {
  return partial('task-decomposition', {
    reason:
      'no Story produced tasks — ' +
      (decompositionFailures
        .map((x) => `${x.storyKey || x.repoPath}: ${(x.detail && x.detail.reason) || x.reason || 'gate failure'}`)
        .join('; ') || 'no per-Story failure was recorded'),
    decompositionFailures,
  })
}

// ── Emit Beads ───────────────────────────────────────────────────────────────────
// The full hierarchy is ready for `bd` emission from the main repo path: one Epic,
// one Story per repo parented to it (parentEpicKey), and every Story's tasks
// beneath it (parentStoryId). This composite surfaces the tree; it does not write
// to .beads itself (never from a worktree/runtime context). The flat beadSet is
// kept as the concatenation of every Story's tasks so existing callers keep working.
enterPhase('Emit Beads')
const beadSet = tasks
const hierarchy = { epic, stories, tasks, storyDependencies }
log(
  `Hierarchy READY: 1 epic, ${stories.length} story/stories, ${tasks.length} task(s) — sequenced and WSJF-scored, ` +
    `${storyDependencies.edges.length} story dependency edge(s), no epic-level graph. ` +
    `Emit via bd from the main repo path: epic first, then stories by parentEpicKey in buildOrderIndex order, then tasks by parentStoryId.`
)

// A run that emitted a usable hierarchy is ok:true even if some repo or Story fell
// out along the way — `degraded` says so without pretending the run failed, because
// a caller holding real tasks needs to act on them, not re-run everything.
const degraded = specFailures.length > 0 || decompositionFailures.length > 0
// ── What crosses back, and the one thing that CANNOT be trimmed ────────────────
// `results` is eight complete phase artifacts and it goes to the journal with the rest.
// `hierarchy` and `beadSet` do NOT: they are this composite's PRODUCT, not its state. The
// caller's next act is to write them into beads with bd (see the elaborate-prd-epic
// skill), so replacing them with a path would not trim a run's context — it would break
// the pipeline and make every caller read a file back to do the job it just asked for.
// The rule this trim enforces is that STATE stops crossing the boundary; a deliverable
// still does.
return {
  ...handback(
    true,
    'emit-beads',
    `1 epic, ${stories.length} story/stories, ${tasks.length} task(s) — sequenced, WSJF-scored and Beads-format valid, against the delta PRD at ${reconciliation.deltaPrdPath} (${reconciliation.verdict}; ${reconciliation.deltaCount} requirement(s) remained). ` +
      (architecture.skipped ? 'Architecture was SKIPPED — triage found no architecture decision. ' : 'Architecture was ruled into the SAD. ') +
      'Emit via bd from the main repo path — epic, then stories, then tasks; this composite does not write to .beads.' +
      (degraded
        ? ` DEGRADED: ${specFailures.length} repo(s) produced no spec and ${decompositionFailures.length} story/stories produced no tasks — details in the run journal. Everything returned here is emittable.`
        : '') +
      (carriedFlags.length ? ` PROCEEDED UNDER ${carriedFlags.length} carried flag(s): ${carriedFlags.join(' | ')}` : ''),
    {
      prd: validatedPrd,
      stagesComplete: [
        creation ? 'prd-creation' : 'prd-supplied',
        'prd-reconciliation',
        'prd-validation',
        epicPath,
        architecture.skipped ? 'architecture-skipped' : 'architecture',
        'trd-authoring',
        'spec-authoring',
        'task-decomposition',
        'emit-beads',
      ],
      carriedFlags,
      specFailures,
      decompositionFailures,
      budget: { attemptsSpent, maxTotalAttempts: MAX_TOTAL_ATTEMPTS },
      results: {
        creation,
        reconciliation,
        validation: validation.artifact,
        architecture: architecture.artifact,
        architectureTriage: archTriage,
        trdAuthoring: trdAuthoring.artifact,
        specAuthoring: specPairs.map((p) => ({ repoPath: p.repoPath, artifact: p.spec })),
        decomposition: decompositions,
      },
    }
  ),
  degraded,
  hierarchy,
  beadSet,
}
  })()
} finally {
  // The journal is written FIRST, because it is now the only place the run's detail exists
  // and the caller's `detailPath` is the path this returns. A journal that could not be
  // written yields detailPath:null — an honest "the detail is gone", never a path to a file
  // nobody wrote.
  const detailPath = await persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
  if (result) result.detailPath = detailPath || null
}
return result
