export const meta = {
  name: 'architecture',
  description:
    'Leaf mini — Architecture decision front-end. Turns an architecture question into a ruled decision and a current arc42 SAD. A read-only triage step first sizes the panel to the decision: questions the SAD already settles skip the analyst fan-out and challenge wave, while contested questions dispatch only the analysts whose dimensions bear on the choice. Analysts propose integration/security/cost options; an independent challenger stresses the patterns and tradeoffs ONLY when the decision is actually contested (an analyst reports a live conflict, or triage flags SAD-reversal risk or high stakes — converged decisions skip the wave and the skip is recorded); the architecture-decider rules; the sad-maintainer consolidates the ruling into the SAD source-feed sections (§2/§4/§8) under an independent conformance check. A decider that can rule on NOTHING returns an explicit inadmissible verdict rather than a dressed-up rejection: the SAD is never written, the run reports ok:false, and the blocking rules are classified as constitutive (a real external constraint) or convention (a house rule this project wrote for itself). A convention never halts delivery — where one conflicts with best practice or AWS Well-Architected, the design wins and the rule is returned as a ruleChallenge for the human owner. Segregation of duties throughout — proposers never judge, the decider never analyzes or authors, the maintainer never reviews its own SAD edit, and triage classifies but never decides.',
  phases: [
    { title: 'Triage', detail: 'architecture-boundary-guardian classifies the decision against the SAD — settled questions skip the panel; contested ones name the analysis dimensions' },
    { title: 'Proposals', detail: 'only the triage-selected analysts propose (integration/security/cost/persistence/cdk options, concurrent), with context-map + failure-mode analysis in one advisor session; skipped when settled' },
    { title: 'Challenge', detail: 'CONDITIONAL — one independent challenger session applies all five lenses (pattern, tradeoff, boundary, cost-impact, ops-readiness), but only when the decision is actually contested: an analyst reports a live conflict, triage flags SAD-reversal risk or a high-stakes question, or any signal is ambiguous (a dead analyst, an unstated flag, no triage verdict) — ambiguity challenges by default. Skipping requires AFFIRMATIVE evidence: every lens explicitly contested=false and triage explicitly low-risk/low-stakes; the judgment is recorded either way' },
    { title: 'Decide', detail: 'architecture-decider rules on proposals + challenges, or by citing prior decisions when triage ruled the question settled; when NO option is admissible it says so, classifies what blocked them, and the blocking constraints go back to the panel for a fresh option set (bounded)' },
    { title: 'Update SAD', detail: 'author fitness/diagrams + selected design drafts from the ruling, then consolidate into arc42 §2/§4/§8, conformance-checked' },
  ],
}

// args: {
//   decision: { id?, title, context, drivers?, repoPath? },  // the architecture question
//   sadPath?: string,        // path to the arc42 SAD (defaults to the vault arch42 tree)
//   feedback?: string,       // optional upstream gate feedback to fold in
//   maxLoops?: number,       // SAD maker-checker passes before decider deadlock (default 2)
//   maxDecideLoops?: number, // re-proposal rounds after an inadmissible ruling (default 2)
//   dimensions?: string[],   // override: force the analyst panel to exactly these axes (triage is skipped)
//   triageVerdict?: { highStakes: boolean, reversalRisk: boolean, rationale?: string },
//                            // the caller's OWN triage classification, supplied alongside `dimensions`.
//                            // Without it a caller-sized panel leaves no verdict for the challenge-wave
//                            // trigger to read, and the wave fires unconditionally — see Phase 0.
//   forceFullPanel?: boolean,// override: skip triage and run the full panel + challenge wave as today
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const d = a.decision || {}
const sadPath = a.sadPath || 'tech/architecture/arch42/ (skillspoke-docs vault)'
const repo = d.repoPath || '(repo path not provided — ask before editing files)'
const MAX_SAD_LOOPS = a.maxLoops || 2
const upstream = a.feedback ? `\nUpstream gate feedback to fold in:\n${a.feedback}` : ''
if (!d.title) return { ok: false, stage: 'input', error: 'no decision.title supplied — refusing to run without a work item' }

const decisionHeader = `Architecture decision ${d.id || ''}: ${d.title || '(untitled)'}
Context: ${d.context || 'n/a'}
Decision drivers: ${(Array.isArray(d.drivers) ? d.drivers : []).join('; ') || 'n/a'}
Work within the repository at: ${repo}${upstream}`

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''

// Shared proposal shape — each maker proposes options with tradeoffs from its lens.
const PROPOSAL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lens', 'options', 'recommendation', 'contested'],
  properties: {
    lens: { type: 'string' },
    options: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'approach', 'pros', 'cons'],
        properties: {
          name: { type: 'string' },
          approach: { type: 'string' },
          pros: { type: 'array', items: { type: 'string' } },
          cons: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    recommendation: { type: 'string' },
    // The analyst's own report on whether its lens still holds a live fight. One of
    // the three inputs the script's challenge-wave trigger reads — see Phase 2.
    contested: { type: 'boolean' },
    contestedReason: { type: 'string' },
  },
}

// Appended to every analyst prompt so `contested` means the same thing on every
// lens. An analyst reports on its OWN analysis here — it judges no other agent.
const CONTESTED_GUIDE =
  'Also report `contested`: true when a materially different alternative remains genuinely live in your lens ' +
  '(two options a reasonable architect could each defend), when your recommendation strains against a stated ' +
  'constraint, or when it plausibly collides with what another lens as framed would recommend — with a one-line ' +
  '`contestedReason`. false when your recommendation is the only sensible option given the constraints. ' +
  'This flag decides whether an adversarial challenge pass runs, so do not soften it — an uncontested claim ' +
  'that was actually contested skips the scrutiny it needed.'

// Analysis advisors with non-proposal output shapes — a domain context map and a
// failure-mode catalogue that feed the decider alongside the lens proposals.
const CONTEXT_MAP_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['contexts', 'relationships'],
  properties: {
    contexts: { type: 'array', items: { type: 'string' } },
    relationships: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['from', 'to', 'kind'],
        properties: {
          from: { type: 'string' },
          to: { type: 'string' },
          kind: { type: 'string' },
        },
      },
    },
  },
}

const FAILURE_MODES_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['failureModes'],
  properties: {
    failureModes: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['failure', 'affects', 'blastRadius'],
        properties: {
          failure: { type: 'string' },
          affects: { type: 'string' },
          blastRadius: { type: 'string' },
        },
      },
    },
  },
}

// The seven analysis axes triage may select from. The first five map onto the lens
// makers below; the last two map onto the analysis advisors (context map, failure modes).
const ALL_DIMENSIONS = ['integration', 'security', 'cost', 'persistence', 'cdk', 'bounded-context', 'failure-mode']

const TRIAGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['settled', 'rationale', 'relevantDecisions', 'dimensions', 'highStakes', 'reversalRisk'],
  properties: {
    settled: { type: 'boolean' },
    rationale: { type: 'string' },
    relevantDecisions: { type: 'array', items: { type: 'string' } },
    dimensions: { type: 'array', items: { type: 'string', enum: ALL_DIMENSIONS } },
    // Two classifications the challenge-wave trigger reads (see Phase 2). Triage
    // still only classifies — neither field rules on anything.
    highStakes: { type: 'boolean' },
    reversalRisk: { type: 'boolean' },
  },
}

// ── Phase 0: Triage ────────────────────────────────────────────────────────────
// ONE read-only agent sizes the panel to the decision before anything is dispatched,
// because running the full 23-agent fan-out on a question the SAD already answers is
// what makes operators abandon the pipeline. Triage only classifies — the
// architecture-decider still makes every ruling, so segregation of duties holds.
phase('Triage')

// Caller overrides: a caller who already knows the decision is contested can force
// the panel shape (dimensions) or the full run (forceFullPanel) without spending a
// triage call whose verdict would then be ignored.
const forcedDimensions = Array.isArray(a.dimensions)
  ? a.dimensions.filter((x) => ALL_DIMENSIONS.includes(x))
  : null

let triage = null
let settled = false
let verifiedDecisions = []
let activeDimensions = []
if (a.forceFullPanel === true) {
  activeDimensions = ALL_DIMENSIONS
  log('Triage skipped: forceFullPanel=true — running the full analyst panel and challenge wave')
} else if (forcedDimensions && forcedDimensions.length) {
  activeDimensions = forcedDimensions
  // ── WHY A CALLER-SIZED PANEL MUST ALSO CARRY A CLASSIFICATION ────────────────
  //
  // Sizing the panel from the caller saves this mini's own triage call. It also used
  // to leave `triage === null`, and the challenge-wave trigger in Phase 2 reads a null
  // triage as AMBIGUITY and challenges by default. The composite path ALWAYS passes
  // `dimensions`, so on that path the affirmative-evidence skip was unreachable: the
  // wave fired on 100% of pipeline runs, and the skip could only ever be exercised by
  // dispatching this mini directly. That is a defect, not a conservative default —
  // the trigger was carefully written and then could never fire the other way.
  //
  // A caller that sized the panel has already classified the decision; the two
  // booleans the trigger reads were simply never handed down. When they are, they
  // stand in for the triage verdict this mini did not run, and a converged decision
  // genuinely skips the wave. When they are NOT supplied, `triage` stays null and the
  // ambiguity default is untouched — silence is still never read as consensus, and a
  // contested decision still gets the wave either way.
  const callerVerdict = a.triageVerdict
  if (
    callerVerdict &&
    typeof callerVerdict.highStakes === 'boolean' &&
    typeof callerVerdict.reversalRisk === 'boolean'
  ) {
    triage = {
      settled: false,
      rationale:
        typeof callerVerdict.rationale === 'string' && callerVerdict.rationale.trim()
          ? callerVerdict.rationale.trim()
          : "classified by the caller's own triage, which also sized the panel",
      relevantDecisions: [],
      dimensions: activeDimensions,
      highStakes: callerVerdict.highStakes,
      reversalRisk: callerVerdict.reversalRisk,
      // Recorded so the journal shows this verdict came from the caller rather than
      // from an architecture-boundary-guardian session that never ran.
      source: 'caller',
    }
    log(
      `Triage skipped: caller forced the panel — analysts selected: ${activeDimensions.join(', ')}; ` +
        `caller classified highStakes=${callerVerdict.highStakes}, reversalRisk=${callerVerdict.reversalRisk}`
    )
  } else {
    log(
      `Triage skipped: caller forced the panel — analysts selected: ${activeDimensions.join(', ')}. ` +
        'The caller supplied no highStakes/reversalRisk classification, so there is no verdict to skip the challenge wave on and it runs by default.'
    )
  }
} else {
  triage = await agent(
    `${rulingsBlock}You are the architecture-boundary-guardian acting as the READ-ONLY triage step. Classify this decision against the existing arc42 SAD — do NOT rule on it, do NOT author options, do NOT edit anything. SAD location: ${sadPath}.

Return settled=true when the SAD already answers this question, or when it is a routine variation on a settled pattern; otherwise settled=false. Cite in relevantDecisions the SAD sections that bear on it, and explain the classification in rationale. In dimensions, name ONLY the axes that genuinely bear on the choice, drawn from ${JSON.stringify(ALL_DIMENSIONS)} — include an axis only when the decision could plausibly turn on it, never by reflex.

Also classify two more things (classification only — you rule on nothing):
- highStakes: true when the question implicates a constitutive constraint — a security or trust boundary, data isolation, a legal or external contract, an irreversible migration, or a platform ban. Difficulty alone is NOT high stakes.
- reversalRisk: true when a plausible ruling on this question could REVERSE or contradict a decision the SAD already records (name the sections in relevantDecisions). false when the SAD is silent here or any ruling would merely extend it.
These two decide whether an adversarial challenge pass runs after the analysts, so classify them on evidence, not by reflex.

${decisionHeader}`,
    {
      label: 'triage:classify',
      phase: 'Triage',
      agentType: 'agent-teams-workforce:architecture-boundary-guardian',
      schema: TRIAGE_SCHEMA,
    }
  )
  if (!triage) {
    // A triage failure must widen the analysis, never narrow it — fail open to the full panel.
    activeDimensions = ALL_DIMENSIONS
    log('Triage returned no verdict — failing open to the full analyst panel')
  } else if (triage.settled) {
    // "Already decided" is a CLAIM, and a claim is exactly how this process has
    // been circumvented before: a note reading "decision already made" was enough
    // to skip a phase that never ran. An agent may propose that a question is
    // settled; it may not be the evidence that it is.
    //
    // So the citation has to resolve. The script — not an agent — checks that each
    // named prior decision exists as a real SAD section on disk. A verdict
    // citing nothing, or citing something that is not there, is an assertion, and
    // an assertion does not skip five analysts and six challengers.
    const cited = (Array.isArray(triage.relevantDecisions) ? triage.relevantDecisions : []).filter(Boolean)

    if (!cited.length) {
      activeDimensions = ALL_DIMENSIONS
      log('Triage claimed SETTLED but cited no prior decision — an unevidenced claim cannot skip the panel; failing open')
    } else {
      // An INDEPENDENT agent verifies the citation. Triage proposes; it does not
      // get to be the evidence for its own proposal. sad-conformance-reviewer is
      // chartered for exactly this — it reads the SAD and reports whether the
      // cited sections are real, current, and actually on point.
      const verification = await agent(
        `You are the sad-conformance-reviewer, verifying a claim BEFORE it is allowed to skip work. A triage step has claimed this architecture decision is already settled and named the prior decisions it relies on. Read those decisions and report whether the claim holds. You are READ-ONLY: verify, do not decide, do not author.

For EACH cited reference, establish three things and report them separately:
  1. it EXISTS — the SAD section is actually there, at the location named
  2. it is CURRENT — it states the decision as current state, not as a past position
  3. it is ON POINT — it actually answers the question below, rather than merely
     touching the same subject

Set confirmed=true ONLY if every cited reference satisfies all three. If any one
fails, set confirmed=false and say which and why. A reference you cannot locate is
a FAILURE, not an ambiguity — the cost of a false confirm is that an unexamined
architecture decision ships, while the cost of a false denial is only that the
full analysis runs.

SAD location: ${sadPath}
Cited prior decisions: ${cited.join('; ')}
Triage rationale: ${triage.rationale}

${decisionHeader}`,
        {
          label: 'triage:verify-citations',
          phase: 'Triage',
          agentType: 'agent-teams-workforce:sad-conformance-reviewer',
          schema: {
            type: 'object',
            additionalProperties: false,
            required: ['confirmed', 'perReference', 'reason'],
            properties: {
              confirmed: { type: 'boolean' },
              perReference: {
                type: 'array',
                items: {
                  type: 'object',
                  additionalProperties: false,
                  required: ['reference', 'exists', 'current', 'onPoint'],
                  properties: {
                    reference: { type: 'string' },
                    exists: { type: 'boolean' },
                    current: { type: 'boolean' },
                    onPoint: { type: 'boolean' },
                    note: { type: 'string' },
                  },
                },
              },
              reason: { type: 'string' },
            },
          },
        }
      )

      if (!verification || verification.confirmed !== true) {
        activeDimensions = ALL_DIMENSIONS
        const why = (verification && verification.reason) || 'the verifier returned no verdict'
        log(`Triage claimed SETTLED citing ${cited.join('; ')}, but verification FAILED: ${why} — failing open to the full analyst panel`)
      } else {
        settled = true
        verifiedDecisions = cited
        log(`Triage: SETTLED — ${triage.rationale}`)
        log(`Citations VERIFIED by sad-conformance-reviewer: ${cited.join('; ')} — skipping the analyst fan-out and the challenge wave`)
      }
    }
  } else {
    activeDimensions = (Array.isArray(triage.dimensions) ? triage.dimensions : []).filter((x) => ALL_DIMENSIONS.includes(x))
    if (activeDimensions.length) {
      log(`Triage: CONTESTED — ${triage.rationale}`)
      log(`Analysts selected: ${activeDimensions.join(', ')}`)
    } else {
      // Contested-but-no-dimensions is incoherent; treat it as fully contested rather
      // than letting an empty list silently skip the analysis a contested decision needs.
      activeDimensions = ALL_DIMENSIONS
      log('Triage: CONTESTED but named no dimensions — failing open to the full analyst panel')
    }
  }
}

// ── Phase 1: Proposals ─────────────────────────────────────────────────────────
// Up to five INDEPENDENT makers propose from their lens, plus two analysis advisors
// (context map, failure modes), all concurrently — but ONLY the ones triage or the
// caller selected, because a one-dimension decision does not deserve a seven-agent
// fan-out, and a settled decision dispatches none at all. Nothing routes them: the
// panel is the selected slice of the fixed roster below, and the framing is written
// by the script (see `frameBlock`).
const makers = [
  {
    agentType: 'agent-teams-workforce:integration-pattern-architect',
    dim: 'integration',
    lens: 'integration/decomposition',
    ask: 'Propose the integration and service-decomposition approach: event-driven flows, service boundaries, and the tradeoffs of each option. Honor the platform constraints (event-driven only — no Step Functions; service isolation; SSM for cross-stack refs).',
  },
  {
    agentType: 'agent-teams-workforce:security-architecture-designer',
    dim: 'security',
    lens: 'security',
    ask: 'Propose the security architecture: trust boundaries, authn/authz placement, data protection, and surface the security tradeoffs of each option.',
  },
  {
    agentType: 'agent-teams-workforce:cost-architecture-reviewer',
    dim: 'cost',
    lens: 'cost',
    ask: 'Assess the cost-architecture tradeoffs of each option: cost drivers, scaling cost shape, and which option is most cost-efficient for the stated drivers.',
  },
  {
    agentType: 'agent-teams-workforce:persistence-architecture-specialist',
    dim: 'persistence',
    lens: 'persistence',
    ask: 'Propose the persistence approach: DynamoDB single- vs multi-table design, key schema, GSI/LSI strategy, and the access-pattern tradeoffs of each option.',
  },
  {
    agentType: 'agent-teams-workforce:cdk-infrastructure-designer',
    dim: 'cdk',
    lens: 'cdk-infrastructure',
    ask: 'Propose the CDK construct topology: Lambda boundaries within the chassis, layer/packaging strategy, and the infrastructure tradeoffs of each option.',
  },
]

let proposals = []
let contextMap = null
let failureModes = []
// Hoisted so the re-proposal round (Phase 3) can re-dispatch the same panel with
// the decider's blocking constraints attached, instead of re-deriving the framing.
let frameBlock = ''
let activeMakers = []
let wantsContextMap = false
let wantsFailureModes = false
if (settled) {
  log('Proposals phase skipped — settled decisions go straight to the architecture-decider')
} else {
  phase('Proposals')

  // ── THE PANEL IS FRAMED BY THE SCRIPT, NOT BY A ROUTER SESSION ───────────────
  //
  // This used to be an `architecture-decision-workflow-coordinator` dispatch
  // (`proposals:frame`) that restated the decision as sub-decisions and constraints.
  // Both of its inputs — `decisionHeader` and `activeDimensions` — are handed to the
  // analysts RAW in the very next dispatch, appended alongside the framing itself, so
  // the session paid a full session-start to reformat text its readers also received
  // unformatted. It ruled nothing (its own prompt spent a paragraph saying so, after a
  // run where it invented gate authority and stood the whole panel down: wf_e1736f55-1fe),
  // and it was on the critical path of every contested architecture run and every
  // re-proposal round.
  //
  // What the analysts actually need from a framing is which axis is theirs and which
  // are covered by someone else, so they propose from one lens instead of drifting
  // across all seven. That is the dimension list, and the script holds it.
  frameBlock = `Panel framing (set by the workflow, not by an agent):
Analysis axes on this decision: ${activeDimensions.join(', ') || '(none named)'}
Propose from YOUR lens only. The other axes above are covered by the analysts dispatched alongside you, and the architecture-decider composes one ruling from all of them — so do not hedge into a lens that is not yours, and do not withhold your own on account of one. The sub-decisions, constraints and drivers are stated in the decision header above; read them there.`

  // Dispatch only the selected slice of the panel. The two advisors are dimensions
  // like any other — a decision with no boundary or failure-mode stake does not pay
  // for a context map or a failure-mode catalogue.
  activeMakers = makers.filter((m) => activeDimensions.includes(m.dim))
  wantsContextMap = activeDimensions.includes('bounded-context')
  wantsFailureModes = activeDimensions.includes('failure-mode')

  const jobs = activeMakers.map((m) => () =>
    agent(
      `${rulingsBlock}${m.ask}\n\n${CONTESTED_GUIDE}\n\n${decisionHeader}\n\n${frameBlock}`,
      {
        label: `proposals:${m.lens}`,
        phase: 'Proposals',
        agentType: m.agentType,
        schema: PROPOSAL_SCHEMA,
      }
    )
  )
  // The two analysis advisors (context map, failure modes) used to be two separate
  // sessions. Both are read-only ANALYSIS feeding the decider — neither judges the
  // other, neither authors options — so when either is wanted, one session carries
  // whichever of the two the triage selected.
  if (wantsContextMap || wantsFailureModes) {
    jobs.push(() =>
      agent(
        `${rulingsBlock}You are a read-only architecture analysis advisor. Produce the analysis artifact(s) named below in one pass, each under its own key. Do NOT rule or author options.
${wantsContextMap ? `
- \`contextMap\`: map the domain boundaries and context relationships this decision touches — which bounded contexts are involved and how they relate (upstream/downstream, conformist, anti-corruption layer).` : ''}${wantsFailureModes ? `
- \`failureModes\`: model the failure modes the proposed directions must withstand — DynamoDB throttling, duplicate event delivery, downstream unavailability, partial-batch failures, poison messages. For each, name the failure, what it affects, and its blast radius.` : ''}

${decisionHeader}

${frameBlock}`,
        {
          label: 'proposals:analysis-advisors',
          phase: 'Proposals',
          agentType: wantsContextMap
            ? 'agent-teams-workforce:bounded-context-mapper'
            : 'agent-teams-workforce:failure-mode-analyst',
          schema: {
            type: 'object',
            additionalProperties: false,
            required: [...(wantsContextMap ? ['contextMap'] : []), ...(wantsFailureModes ? ['failureModes'] : [])],
            properties: {
              ...(wantsContextMap ? { contextMap: CONTEXT_MAP_SCHEMA } : {}),
              ...(wantsFailureModes ? { failureModes: FAILURE_MODES_SCHEMA.properties.failureModes } : {}),
            },
          },
        }
      )
    )
  }

  const proposalResults = await parallel(jobs)
  proposals = proposalResults.slice(0, activeMakers.length).filter(Boolean)
  if (wantsContextMap || wantsFailureModes) {
    const advisors = proposalResults[activeMakers.length] || null
    if (wantsContextMap) contextMap = (advisors && advisors.contextMap) || null
    if (wantsFailureModes) failureModes = (advisors && advisors.failureModes) || []
  }
}
let proposalsText = JSON.stringify(proposals, null, 2)
let analysisText = JSON.stringify({ contextMap, failureModes }, null, 2)

// ── Phase 2: Challenge ─────────────────────────────────────────────────────────
// ONE independent checker session stresses the proposals through all five challenge
// lenses — pattern, tradeoff, boundary coupling, cost-at-scale, and operational
// readiness. These used to be five separate sessions, each paying a full
// session-start to read the same proposal set; every lens is a CHECK on options
// authored by OTHER agents, so one session carrying all five preserves segregation
// of duties — no proposer challenges its own proposal, and the challenger authored
// nothing. The wave runs only over proposals that were actually produced, because a
// settled decision (or an analysis-only panel) leaves nothing to challenge.
const runChallengeWave = async () => {
  const wave = await agent(
    `You are the adversarial challenge panel for an architecture decision. You did NOT author any of the proposals below; you only stress them. Apply ALL FIVE lenses in one pass, returning each lens's findings under its own key. Do NOT author replacement options anywhere — only challenge. Keep every objection/risk/concern under 40 words.

1. \`challenges\` (pattern lens): patterns that conflict with SkillSpoke platform constraints or are known anti-patterns, each with the reason and the constraint it violates.
2. \`unstatedRisks\` (tradeoff-skeptic lens): tradeoffs the proposers understated, hidden coupling, operational cost not accounted for, failure modes glossed over.
3. \`boundaryViolations\` (boundary lens): cross-context coupling — where a proposal makes this context own behavior another owns, reaches across a boundary it should respect, or violates service isolation.
4. \`scaleBreakpoints\` (cost-at-scale lens): stress each option's cost at 10x, 100x, and 1000x the stated load — where each option's cost breaks first (cost cliff, throttle, or quota) and the bottleneck that causes it.
5. \`readinessGaps\` (operational-readiness lens): operations a proposal would require but does not account for — monitoring, alerting, runbooks, on-call load, failure recovery.

${decisionHeader}

Proposals under challenge:
${proposalsText}`,
    {
      label: 'challenge:all-lenses',
      phase: 'Challenge',
      agentType: 'agent-teams-workforce:architecture-tradeoff-skeptic',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['challenges', 'unstatedRisks', 'boundaryViolations', 'scaleBreakpoints', 'readinessGaps'],
        properties: {
          challenges: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['target', 'objection', 'severity'],
              properties: {
                target: { type: 'string' },
                objection: { type: 'string' },
                severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
              },
            },
          },
          unstatedRisks: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['risk', 'affects', 'severity'],
              properties: {
                risk: { type: 'string' },
                affects: { type: 'string' },
                severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
              },
            },
          },
          boundaryViolations: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['target', 'coupling', 'severity'],
              properties: {
                target: { type: 'string' },
                coupling: { type: 'string' },
                severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
              },
            },
          },
          scaleBreakpoints: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['option', 'breaksAt', 'bottleneck', 'severity'],
              properties: {
                option: { type: 'string' },
                breaksAt: { type: 'string', enum: ['10x', '100x', '1000x', 'beyond'] },
                bottleneck: { type: 'string' },
                severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
              },
            },
          },
          readinessGaps: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['target', 'concern', 'severity'],
              properties: {
                target: { type: 'string' },
                concern: { type: 'string' },
                severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
              },
            },
          },
        },
      },
    }
  )
  return wave
}

// ── The challenge wave is CONDITIONAL, and the trigger is JUDICIOUS ─────────────
// Mark's ruling: "Challenge shouldn't run 100% of the time" — and, on clarification,
// "we need to be judicious": this is not a bias against challenging. The wave runs
// on any contest TRIGGER (an analyst reports a live conflict, or triage classified
// SAD-reversal risk or constitutive stakes), and skipping requires AFFIRMATIVE
// evidence of convergence and low stakes: every dispatched lens actually returned
// and explicitly said contested=false, and triage explicitly said reversalRisk=false
// AND highStakes=false. Anything AMBIGUOUS — a dead analyst, an unstated flag, no
// triage verdict at all — challenges by default; silence is never read as consensus.
// The trigger is computed HERE, by the script, from data the run already holds. No
// agent decides whether to challenge, so segregation of duties is untouched: the
// decider still never analyzes, and challengers still never decide. The judgment is
// recorded either way — "challenge ran: <trigger>" / "challenge skipped: <evidence>"
// — so every run's trace shows the decision being made, not silence.
let challengeResults = null
let challengeWave = null
if (!settled && proposals.length) {
  const triggers = []
  const ambiguities = []
  if (a.forceFullPanel === true) triggers.push('caller forced the full panel')
  if (!triage) ambiguities.push('no triage verdict exists (caller-forced dimensions or triage failure)')
  const contestedLenses = proposals.filter((p) => p && p.contested === true)
  if (contestedLenses.length) {
    triggers.push(
      `${contestedLenses.length} analyst lens(es) report a live conflict: ` +
        contestedLenses.map((p) => `${p.lens}${p.contestedReason ? ` (${p.contestedReason})` : ''}`).join('; ')
    )
  }
  if (triage && triage.reversalRisk === true) triggers.push('triage: a plausible ruling could reverse or contradict a recorded SAD decision')
  if (triage && triage.highStakes === true) triggers.push('triage: the question implicates a constitutive/high-stakes constraint')
  // Affirmative-evidence checks — each failure is ambiguity, and ambiguity challenges.
  const missingLenses = activeMakers.length - proposals.length
  if (missingLenses > 0) ambiguities.push(`${missingLenses} dispatched analyst lens(es) returned nothing, so their view of the contest is unknown`)
  const unstated = proposals.filter((p) => typeof (p && p.contested) !== 'boolean')
  if (unstated.length) ambiguities.push(`${unstated.length} lens(es) did not state contested either way`)
  if (triage && typeof triage.reversalRisk !== 'boolean') ambiguities.push('triage did not state reversalRisk either way')
  if (triage && typeof triage.highStakes !== 'boolean') ambiguities.push('triage did not state highStakes either way')

  if (triggers.length || ambiguities.length) {
    const why = [
      ...triggers,
      ...(ambiguities.length ? [`signals ambiguous, challenging by default: ${ambiguities.join('; ')}`] : []),
    ].join(' | ')
    challengeWave = { ran: true, reason: `challenge ran: ${why}` }
    log(challengeWave.reason)
    phase('Challenge')
    challengeResults = await runChallengeWave()
  } else {
    // Recorded as a decision, not silence: the reason crosses back on the result so
    // the run journal shows the affirmative evidence this skip stands on.
    challengeWave = {
      ran: false,
      reason:
        `challenge skipped: analysts converged — all ${proposals.length}/${activeMakers.length} dispatched lenses affirmed contested=false, ` +
        'and triage affirmed reversalRisk=false and highStakes=false',
    }
    log(challengeWave.reason)
  }
} else if (!settled) {
  challengeWave = { ran: false, reason: 'challenge skipped: the selected panel produced no lens proposals to challenge' }
  log('Challenge wave skipped — the selected panel produced no lens proposals to challenge')
} else {
  challengeWave = { ran: false, reason: 'challenge skipped: triage ruled the question settled, so no proposals exist to challenge' }
}

const foldChallenges = (r) => ({
  patterns: (r && r.challenges) || [],
  unstatedRisks: (r && r.unstatedRisks) || [],
  boundaryViolations: (r && r.boundaryViolations) || [],
  scaleBreakpoints: (r && r.scaleBreakpoints) || [],
  readinessGaps: (r && r.readinessGaps) || [],
})
let challenges = foldChallenges(challengeResults)
// When the wave was SKIPPED, the decider must not read the empty set as "the
// challengers found nothing" — the skip and its reason travel with the evidence.
const challengesEvidence = () =>
  challengeWave && challengeWave.ran === false
    ? `(none — ${challengeWave.reason}. No challenger ran; an empty set here is a recorded skip, not a clean bill.)`
    : challengesText
let challengesText = JSON.stringify(challenges, null, 2)

// ── Phase 3: Decide ─────────────────────────────────────────────────────────────
// The decider ONLY rules — it does not analyze or author. Distinct from makers and
// checkers, and it ALWAYS runs: triage classifies but never decides, so even a
// settled decision gets an explicit ruling — one that cites the prior decisions
// triage surfaced instead of re-deriving them.
phase('Decide')

const evidenceBlock = settled
  ? `Triage classified this decision as SETTLED by the existing SAD, so no analyst panel ran.
Triage rationale: ${triage.rationale}
Relevant prior decisions (independently verified as existing, current, and on point): ${verifiedDecisions.join('; ') || '(none)'}

Rule by CITING those prior decisions rather than re-deriving the analysis. If you find they do not actually answer this question, say so in the ruling and impose a constraint that the decision be re-run with forceFullPanel.`
  : `Proposals:
${proposalsText}

Analysis (context map + failure modes):
${analysisText}

Challenges:
${challengesEvidence()}

Blocking challenges must be resolved by the ruling or the ruling is invalid.`

const DECISION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['admissible', 'ruling', 'imposedConstraints', 'resolvedChallenges', 'surfaces', 'blockingRules', 'ruleChallenges'],
  properties: {
    // admissible=false means NO option in front of the decider can be ruled on.
    // It is a real, reportable outcome — never a ruling, never written to the SAD.
    admissible: { type: 'boolean' },
    ruling: { type: 'string' },
    chosenApproach: { type: 'string' },
    imposedConstraints: { type: 'array', items: { type: 'string' } },
    resolvedChallenges: { type: 'array', items: { type: 'string' } },
    surfaces: { type: 'array', items: { type: 'string', enum: ['events', 'restApi', 'graphql', 'newDomain'] } },
    // Why nothing was admissible, so the next round can be aimed rather than repeated.
    blockingRules: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rule', 'source', 'whyBlocking', 'classification'],
        properties: {
          rule: { type: 'string' },
          source: { type: 'string' },
          whyBlocking: { type: 'string' },
          // convention = a house rule this project wrote for itself. It MUST NOT
          // halt delivery; it is challengeable. constitutive = a real external
          // constraint (an AWS limit, a security fundamental, a legal obligation).
          classification: { type: 'string', enum: ['constitutive', 'convention'] },
        },
      },
    },
    // First-class output: the SAD rule itself is wrong and should change. Routed to
    // the human owner — never silently absorbed into the document.
    ruleChallenges: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rule', 'source', 'recommendedChange', 'rationale'],
        properties: {
          rule: { type: 'string' },
          source: { type: 'string' },
          recommendedChange: { type: 'string' },
          rationale: { type: 'string' },
        },
      },
    },
  },
}

const DECIDER_CHARTER = `You are the architecture-decider. Rule on the architecture given the evidence below. You do not analyze and you do not write the SAD.

YOUR AUTHORITY, AND ITS LIMITS:
- Normally you CHOOSE among the options proposed and state the ruling as a decision, not a discussion. Set admissible=true and fill chosenApproach.
- If NO proposed option can be ruled on, set admissible=false and leave chosenApproach empty. Populate blockingRules with the specific rules that eliminated every option. This is a reportable outcome, not a failure to do your job — do NOT manufacture a ruling to avoid it, and do NOT dress a rejection up as a decision.
- Classify every blocking rule. A rule is "constitutive" ONLY if it is a real external constraint: an AWS service limit, a security fundamental, a legal or contractual obligation. A rule this project wrote for itself — a naming convention, a curated allowlist, a house pattern, a self-authored MUST in our own SAD — is a "convention", however normatively it is phrased.
- A convention MUST NOT be the reason delivery halts. If a convention is the only thing eliminating an otherwise sound design, prefer the design: rule it admissible and record a ruleChallenge against the convention.
- Where our own written rule conflicts with industry best practice or an AWS Well-Architected principle, BEST PRACTICE WINS and our rule is the defect. Record it in ruleChallenges with the change you recommend. ruleChallenges go to the human owner; they are never applied by this run.

Also report \`surfaces\` — which design surfaces the ruling creates: events, restApi, graphql, newDomain (any subset, empty if none).`

const MAX_DECIDE_LOOPS = a.maxDecideLoops || 2
let decision = null
let decideRounds = 0

for (let round = 1; round <= MAX_DECIDE_LOOPS; round++) {
  decideRounds = round
  const evidence = round === 1
    ? evidenceBlock
    : `Proposals (re-proposed round ${round}, aimed at the constraints that eliminated the previous set):
${proposalsText}

Analysis (context map + failure modes):
${analysisText}

Challenges:
${challengesEvidence()}

Blocking challenges must be resolved by the ruling or the ruling is invalid.`

  decision = await agent(
    `${rulingsBlock}${DECIDER_CHARTER}

${decisionHeader}

${evidence}`,
    {
      label: round === 1 ? 'decide:ruling' : `decide:ruling-r${round}`,
      phase: 'Decide',
      agentType: 'agent-teams-workforce:architecture-decider',
      schema: DECISION_SCHEMA,
    }
  )

  if (!decision) break
  if (decision.admissible) break

  const blocking = decision.blockingRules || []
  const conventionsOnly = blocking.length > 0 && blocking.every((b) => b.classification === 'convention')
  log(`Decide round ${round}: NO admissible option — blocked by ${blocking.length} rule(s)${conventionsOnly ? ', all house conventions' : ''}`)

  // A settled-by-triage question has no panel to send back to, and a run out of
  // rounds stops here. Either way the inadmissible verdict stands and is reported.
  if (settled || !activeMakers.length || round === MAX_DECIDE_LOOPS) break

  // Re-proposal round: send the blocking constraints BACK to the same panel and ask
  // for a design that satisfies them, or a named rule to challenge. This is the loop
  // whose absence let a single bad option set end an entire architecture run.
  phase('Proposals')
  log(`Re-proposing against ${blocking.length} blocking rule(s) — round ${round + 1} of ${MAX_DECIDE_LOOPS}`)

  const blockingBlock = `The previous option set was ruled INADMISSIBLE. Every option was eliminated by these rules:
${blocking.map((b) => `- [${b.classification}] ${b.rule} (${b.source}) — ${b.whyBlocking}`).join('\n')}

Propose a NEW option set. Requirements for this round:
- Design the best solution to the problem FIRST, using industry best practice and AWS Well-Architected. Then check it against the rules above.
- Do NOT re-present any option already eliminated.
- A rule classified as [convention] is a house rule, not an external constraint. If the best design conflicts with one, propose the design anyway and say plainly in the option's cons which convention it breaks and why the convention should change.
- Only a [constitutive] rule — a real AWS limit, a security fundamental, a legal obligation — is genuinely binding on your options.
- Existing deployed infrastructure is NOT a constraint on the design. If the right answer requires something that does not exist yet, propose it.`

  const reJobs = activeMakers.map((m) => () =>
    agent(
      `${rulingsBlock}${m.ask}\n\n${CONTESTED_GUIDE}\n\n${decisionHeader}\n\n${frameBlock}\n\n${blockingBlock}`,
      { label: `proposals:${m.lens}-r${round + 1}`, phase: 'Proposals', agentType: m.agentType, schema: PROPOSAL_SCHEMA }
    )
  )
  const reProposed = (await parallel(reJobs)).filter(Boolean)
  if (!reProposed.length) {
    log('Re-proposal round produced nothing — the inadmissible verdict stands')
    break
  }
  proposals = reProposed
  proposalsText = JSON.stringify(proposals, null, 2)

  phase('Challenge')
  // A re-proposal round is contested BY CONSTRUCTION — the decider just ruled every
  // option inadmissible — so the wave runs here regardless of the round-1 trigger.
  challengeWave = { ran: true, reason: `challenge ran: re-proposal round ${round + 1} — the previous option set was ruled inadmissible, which is a live conflict by construction` }
  challenges = foldChallenges(await runChallengeWave())
  challengesText = JSON.stringify(challenges, null, 2)
}

if (!decision) {
  return { ok: false, stage: 'decide', error: 'the architecture-decider returned nothing', triage, proposals, challenges }
}

const admissible = decision.admissible === true
const ruleChallenges = decision.ruleChallenges || []
if (ruleChallenges.length) {
  log(`${ruleChallenges.length} rule challenge(s) raised — these are for the human owner, not applied by this run`)
}

// A non-decision MUST NOT be written into the SAD. Recording "nothing was admissible"
// as normative architecture is how a failed run becomes a permanent blocker.
if (!admissible) {
  log('No admissible option after ' + decideRounds + ' round(s) — SAD update SKIPPED; nothing is recorded')
  return {
    ok: false,
    stage: 'decide',
    admissible: false,
    error: 'no admissible option — the panel produced nothing the decider could rule on',
    blockingRules: decision.blockingRules || [],
    ruleChallenges,
    decideRounds,
    decisionRef: d.id || null,
    triage,
    settledByTriage: settled,
    panelDimensions: activeDimensions,
    challengeWave,
    proposals,
    contextMap,
    failureModes,
    challenges,
    decision,
  }
}

// ── Phase 4: Update SAD ──────────────────────────────────────────────────────────
// Maker-checker bounded loop: sad-maintainer authors the SAD edit, an INDEPENDENT
// sad-conformance-reviewer judges it. On reject, re-run the maker with feedback
// (bounded MAX_SAD_LOOPS passes). On deadlock, the architecture-decider rules.
phase('Update SAD')

// Author the decision artifacts FROM the ruling — fitness functions, diagrams —
// concurrently and before SAD consolidation, so the maintainer references rather than
// recreates them. The decider authored none of these.
const decisionContext = `Ruling: ${decision.ruling}
Chosen approach: ${decision.chosenApproach}
Imposed constraints: ${(decision.imposedConstraints || []).join('; ') || 'none'}`

// Fitness functions and diagrams used to be two separate maker sessions reading the
// same ruling; both are makers writing FROM the ruling with no judging anywhere, so
// one session authors both. Same argument for the design drafts below.
const authored = await agent(
  `Author the decision artifacts FROM the ruling below — do NOT re-decide anything. Two artifacts, each under its own key:

1. \`fitnessFunctions\`: testable fitness functions — mechanically checkable assertions such as "all events publish through the event API" or "all Lambdas extend the chassis".
2. \`diagrams\`: the architecture diagram(s) of the decided design in the project's standard Mermaid format. SAD location: ${sadPath}.

${decisionContext}`,
  { label: 'author:decision-artifacts', phase: 'Update SAD', agentType: 'agent-teams-workforce:architecture-fitness-function-author',
    schema: { type: 'object', additionalProperties: false, required: ['fitnessFunctions', 'diagrams'], properties: {
      fitnessFunctions: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['assertion', 'check'], properties: { assertion: { type: 'string' }, check: { type: 'string' } } } },
      diagrams: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['kind', 'summary'], properties: { kind: { type: 'string' }, summary: { type: 'string' }, path: { type: 'string' } } } },
    } } }
)
const authoredArtifacts = {
  fitnessFunctions: (authored && authored.fitnessFunctions) || [],
  diagrams: (authored && authored.diagrams) || [],
}

// SELECTED design drafts — only the surfaces the ruling actually creates, all
// authored in ONE maker session (one draft per selected design, each under its key).
const surfaces = Array.isArray(decision.surfaces) ? decision.surfaces : []
const designSpecs = []
if (surfaces.includes('events')) {
  designSpecs.push(['eventSchema', 'Design the event schema(s) within the event API envelope format for the decided events.'])
  designSpecs.push(['domainEvents', 'Model the domain events, flows, and contracts the ruling introduces.'])
}
if (surfaces.includes('restApi')) designSpecs.push(['apiContract', 'Produce the OpenAPI contract proposal for the decided REST surface.'])
if (surfaces.includes('graphql')) designSpecs.push(['graphql', 'Design the GraphQL schema proposal for the decided AppSync surface.'])
if (surfaces.includes('newDomain')) designSpecs.push(['ubiquitousLanguage', 'Capture the ubiquitous language — terms, definitions, usage rules — for the new or affected bounded context.'])
let designDrafts = []
if (designSpecs.length) {
  const draftsResult = await agent(
    `Author the design draft(s) the ruling below creates — one per key, drawn FROM the ruling; do NOT re-decide anything.

${designSpecs.map(([key, ask]) => `- \`${key}\`: ${ask}`).join('\n')}

${decisionContext}`,
    {
      label: 'design:drafts',
      phase: 'Update SAD',
      agentType: 'agent-teams-workforce:api-contract-designer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: designSpecs.map(([key]) => key),
        properties: Object.fromEntries(designSpecs.map(([key]) => [key, { type: 'object', additionalProperties: false, required: ['summary'], properties: { summary: { type: 'string' }, path: { type: 'string' } } }])),
      },
    }
  )
  designDrafts = draftsResult
    ? designSpecs.map(([key]) => draftsResult[key]).filter(Boolean)
    : []
}

const SAD_UPDATE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['updatedSections', 'changedFiles', 'summary'],
  properties: {
    updatedSections: { type: 'array', items: { type: 'string' } },
    changedFiles: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}

const CONFORMANCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'findings'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'reject'] },
    findings: { type: 'array', items: { type: 'string' } },
  },
}

async function authorSad(reviewerFeedback) {
  return await agent(
    `You are the sad-maintainer. Consolidate the ruling below into the living arc42 SAD, editing ONLY the source-feed sections it touches: §2 Constraints, §4 Solution Strategy, §8 Crosscutting Concepts. Keep those sections mutually consistent. Edit the living document in place — no changelog narrative, no rewriting history. SAD location: ${sadPath}.

SWEEP EVERY CLAIM YOU CHANGE — THIS IS NOT OPTIONAL.
The SAD states the same normative claim in several places: a §2 constraint, a §4 strategy bullet, a §8 concept, a §5 building-block description, and a §8 README index row can all name the same store, protocol, or topology. Changing one and leaving the others is the single most common way this document self-contradicts, and a downstream extractor then reads whichever copy it happens to hit.
For EVERY claim the ruling changes: grep the WHOLE SAD tree for the OLD value and for the subject of the claim, and correct EVERY statement of it in the same pass — including index/summary rows, which are claims too. Then re-grep for the old value and confirm the only remaining hits are ones that legitimately describe a different mechanism. Report the sweep you ran.

A DECIDED QUESTION IS NOT AN OPEN ONE.
Never record an "unresolved" or "contradiction" marker for a claim this ruling settles. If the SAD contradicts the ruling, the SAD is the defect: correct it. Reserve unresolved-markers for questions genuinely outside this ruling's reach.

NEVER LABEL THE ADOPTED OPTION WITH A BARE PROPOSAL LETTER.
Option letters are packet-local and do not survive outside the packet — the same letter routinely names an eliminated option elsewhere. Write the descriptive name. Where a provenance label is needed, write the full dual label, never a bare letter.

MARK WHAT THIS RULING SUPERSEDES IN PROVENANCE, NOT ONLY IN PROSE.
If a \`derived_from\` entry asserts a state this ruling overturns, append a supersession marker naming this decision to that entry. A reader or extractor reading provenance alone must not come away with two rulings asserting opposite states.

Ruling: ${decision.ruling}
Chosen approach: ${decision.chosenApproach}
Imposed constraints: ${(decision.imposedConstraints || []).join('; ') || 'none'}
Resolved challenges: ${(decision.resolvedChallenges || []).join('; ') || 'none'}

Decision artifacts already authored (consolidate references into the SAD; do NOT recreate them):
${JSON.stringify({ fitnessFunctions: authoredArtifacts.fitnessFunctions, diagrams: authoredArtifacts.diagrams, designDrafts }, null, 2)}
${reviewerFeedback ? `\nConformance findings from the previous pass — address each:\n${reviewerFeedback}` : ''}

Deliver: which §2/§4/§8 sections you changed, the file paths edited, and a one-line summary of the change.`,
    {
      label: 'sad:maintain',
      phase: 'Update SAD',
      agentType: 'agent-teams-workforce:sad-maintainer',
      schema: SAD_UPDATE_SCHEMA,
    }
  )
}

async function reviewSad(sadUpdate) {
  return await agent(
    `You are the sad-conformance-reviewer — INDEPENDENT of the sad-maintainer. Check the SAD edit for arc42 conformance and living-document hygiene: are §2/§4/§8 internally consistent, does the edit reflect the ruling without introducing changelog narrative, and is the source feed still valid for downstream TRD/Spec consumers? You only judge — do not edit the SAD. Verdict "pass" only if every finding is non-blocking; otherwise "reject" with specific, actionable findings.

Ruling consolidated: ${decision.ruling}

SAD edit under review:
${JSON.stringify(sadUpdate, null, 2)}`,
    {
      label: 'sad:conformance',
      phase: 'Update SAD',
      agentType: 'agent-teams-workforce:sad-conformance-reviewer',
      schema: CONFORMANCE_SCHEMA,
    }
  )
}

let sadUpdate = null
let conformanceVerdict = null
let reviewerFeedback = ''
for (let pass = 1; pass <= MAX_SAD_LOOPS; pass++) {
  sadUpdate = await authorSad(reviewerFeedback)
  conformanceVerdict = await reviewSad(sadUpdate)
  if (!conformanceVerdict) {
    log(`SAD conformance pass ${pass}: reviewer returned no verdict`)
    break
  }
  if (conformanceVerdict.verdict === 'pass') {
    log(`SAD conformance: PASS on pass ${pass}/${MAX_SAD_LOOPS}`)
    break
  }
  log(`SAD conformance: REJECT pass ${pass}/${MAX_SAD_LOOPS} — ${(conformanceVerdict.findings || []).join('; ')}`)
  reviewerFeedback = (conformanceVerdict.findings || []).join('\n')
}

// Deadlock: maker-checker exhausted without a pass → the decider rules (never the maker).
if (!conformanceVerdict || conformanceVerdict.verdict !== 'pass') {
  log('SAD maker-checker deadlock — escalating to architecture-decider for a binding ruling')
  const deadlockRuling = await agent(
    `You are the architecture-decider acting as the deadlock authority. The sad-maintainer and sad-conformance-reviewer could not converge within ${MAX_SAD_LOOPS} passes. Rule on how the SAD must read so the source feed (§2/§4/§8) is valid. You ONLY rule — do not author or re-review.

Ruling being consolidated: ${decision.ruling}
Last SAD edit attempted:
${JSON.stringify(sadUpdate, null, 2)}
Unresolved conformance findings:
${(conformanceVerdict && conformanceVerdict.findings || []).join('\n') || '(none captured)'}`,
    {
      label: 'sad:deadlock-ruling',
      phase: 'Update SAD',
      agentType: 'agent-teams-workforce:architecture-decider',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'directive'],
        properties: {
          verdict: { type: 'string', enum: ['accept', 'reject'] },
          directive: { type: 'string' },
        },
      },
    }
  )
  conformanceVerdict = {
    verdict: deadlockRuling && deadlockRuling.verdict === 'accept' ? 'pass' : 'reject',
    findings: deadlockRuling ? [deadlockRuling.directive] : (conformanceVerdict && conformanceVerdict.findings) || [],
    ruledByDecider: true,
  }
}

// ── Return: one object threading every phase output ──────────────────────────────
// ok requires an actual DECISION, not merely a well-formed SAD edit. A run that
// decided nothing returns ok:false even if every document it touched is tidy.
return {
  ok: admissible && !!conformanceVerdict && conformanceVerdict.verdict === 'pass',
  admissible,
  ruleChallenges,
  decideRounds,
  decisionRef: d.id || null,
  triage,
  settledByTriage: settled,
  panelDimensions: activeDimensions,
  challengeWave,
  proposals,
  tradeoffs: proposals.map((p) => ({ lens: p.lens, recommendation: p.recommendation, options: p.options })),
  contextMap,
  failureModes,
  challenges,
  decision,
  authoredArtifacts,
  designDrafts,
  sadUpdate,
  conformanceVerdict,
}
