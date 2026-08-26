export const meta = {
  name: 'adversarial',
  description:
    'Shared-tail mini — Adversarial Validation (feeds the constitutional Gate 4). Attackers run concurrently against the change in DESIGNATED TEST ENVIRONMENTS ONLY; an independent adversarial-critique-adjudicator referees severity. The lane set is DERIVED from the surfaces the contract declares — most attack classes need a surface to attack — over a BASELINE of data-exposure and dependency-CVE scanning that always runs and that no surface list can remove, because those apply to any code change. An undeclared surface list means unknown, not empty, and runs every lane; a caller-supplied trimmedScope wins. Security findings are constitutive and cannot be downgraded by implementers.',
  phases: [
    { title: 'Attack', detail: 'access-control + data-integrity and infra + exposure lanes (concurrent)' },
    { title: 'Adjudicate', detail: 'referee severity; classify constitutive vs competitive' },
  ],
}

// args: { contract, green, trimmedScope?, feedback?, priorRulings? }
//   priorRulings?: [{ findingId, title, severity, classification, real }]
//     The adjudication from the PREVIOUS attempt at this gate. Its absence is what let
//     the adjudicator rule one fact constitutive/real in one round and competitive/not-real
//     in the next with no new evidence: the feedback string reached only the ATTACKER
//     prompts, so the adjudicator was a fresh instance every round that had never been
//     shown a ruling. It is not reversing anything — it has never seen the prior verdict.
//   trimmedScope?: string[]  // restrict the attack to these attacker agents (e.g. the
//                            // infra path's infra-only lane). Empty/absent → run all lanes.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const feedback = a.feedback ? `\nPrior gate feedback to address:\n${a.feedback}` : ''
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
const target = `Change under attack: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}. Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}. DESIGNATED TEST ENVIRONMENTS ONLY — never attack production. Work within: ${repo}`

// ── Stable finding identity ───────────────────────────────────────────────────
//
// A ruling's only identity used to be its model-authored `title`. Attackers re-run from
// scratch on every loop attempt, so one underlying fact comes back under a re-worded
// title each round — and to every consumer those are two different findings. That is
// exactly how a final packet carried two OPPOSITE reality rulings for one fact.
//
// The id is derived HERE, in script, from the lane plus a normalized fingerprint of the
// reproduction. Deriving it in script rather than asking for it means the model cannot
// mint a fresh id for a fact it already reported, and cannot rename its way out of a
// prior ruling.
function fingerprint(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'unspecified'
}
function findingIdFor(lane, finding) {
  return `${lane}#${fingerprint(finding && finding.reproduction)}`
}

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'severity', 'reproduction'],
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
          reproduction: { type: 'string' },
        },
      },
    },
  },
}

const accessLane = [
  'injection-attack-tester',
  'auth-bypass-tester',
  'permission-escalation-tester',
  'race-condition-tester',
  'contract-violation-tester',
]
const infraLane = [
  'dependency-cve-auditor',
  'dos-resilience-tester',
  'data-exposure-scanner',
  'infrastructure-security-scanner',
]

// Honor a trimmed scope (e.g. the infra path's infra-only lane). An unknown name in
// trimmedScope is ignored; if the filter selects nothing, fall back to ALL lanes rather
// than silently skip security validation.
const allAttackers = [...accessLane, ...infraLane]
const requested = Array.isArray(a.trimmedScope) ? allAttackers.filter((n) => a.trimmedScope.includes(n)) : []
if (Array.isArray(a.trimmedScope) && a.trimmedScope.length && !requested.length) {
  log(`⚠ trimmedScope matched no known attacker (${a.trimmedScope.join(', ')}) — running all lanes`)
}

// ── Surface-derived lane selection ────────────────────────────────────────────
//
// Most attack classes need a surface to attack. Auth bypass needs an auth surface;
// injection needs an input boundary; DoS resilience needs a stated load budget.
// Running all nine against a change that touches none of them buys nothing and is
// most of this phase's cost.
//
// The BASELINE is never empty and is not derived: data exposure and dependency CVEs
// apply to any code change at all — a fix confined to internal logic can still leak a
// field into a log or pull a vulnerable transitive package. Security findings are
// constitutive here, so the floor never drops to zero and no surface list can remove it.
//
// As everywhere else, an UNDECLARED surface list means unknown, not empty, and runs
// every lane. Only a contract that positively declares its surfaces gets a narrowed set.
const BASELINE_ATTACKERS = ['data-exposure-scanner', 'dependency-cve-auditor']
const SURFACE_ATTACKERS = {
  auth: ['auth-bypass-tester', 'permission-escalation-tester'],
  'api-contract': ['injection-attack-tester', 'contract-violation-tester'],
  'event-chain': ['race-condition-tester', 'contract-violation-tester'],
  'web-ui': ['injection-attack-tester'],
  performance: ['dos-resilience-tester'],
  'data-pipeline': ['race-condition-tester'],
}
const declaredSurfaces = Array.isArray(c.surfaces) ? c.surfaces : null

let attackers
let laneMode
if (requested.length) {
  attackers = requested
  laneMode = 'trimmed-by-caller'
} else if (declaredSurfaces) {
  attackers = [
    ...new Set([...BASELINE_ATTACKERS, ...declaredSurfaces.flatMap((s) => SURFACE_ATTACKERS[s] || [])]),
  ].filter((n) => allAttackers.includes(n))
  laneMode = 'derived-from-surfaces'
  log(
    `Adversarial lanes derived from surfaces [${declaredSurfaces.join(', ') || 'none'}]: ${attackers.join(', ')} ` +
      `(baseline ${BASELINE_ATTACKERS.join(' + ')} always runs)`
  )
} else {
  attackers = allAttackers
  laneMode = 'all-lanes'
  log('Adversarial: contract declares no surface list — running every lane')
}

phase('Attack')
const results = await parallel(
  attackers.map((name) => () =>
    agent(`Attempt your attack class against the change. Report only confirmed findings with a minimal reproduction. ${target}${feedback}`, {
      label: `attack:${name}`,
      phase: 'Attack',
      agentType: `agent-teams-workforce:${name}`,
      schema: FINDINGS_SCHEMA,
    })
  )
)
// Attach the derived id and the lane that produced it. Both are script-owned facts
// about where a finding came from, not claims the attacker gets to make.
const findings = results.flatMap((r, i) =>
  ((r && r.findings) || []).map((f) => ({ ...f, lane: attackers[i], findingId: findingIdFor(attackers[i], f) }))
)
const knownFindingIds = [...new Set(findings.map((f) => f.findingId))]

// The previous attempt's rulings. Rendered to the adjudicator so a reversal is a
// reversal of something it can see, and checked script-side afterwards so an uncited
// reversal has no EFFECT rather than merely being disapproved of.
const priorRulings = (Array.isArray(a.priorRulings) ? a.priorRulings : []).filter((r) => r && r.findingId)
const priorById = {}
for (const r of priorRulings) priorById[r.findingId] = r

phase('Adjudicate')
const adjudication = await agent(
  `You are the adversarial-critique-adjudicator (Referee). Rule on each finding's real severity and whether it is CONSTITUTIVE (a security/validity hard stop — implementers cannot downgrade it) or COMPETITIVE (a tradeable quality concern). Discard false positives with reasoning.

Return EXACTLY ONE ruling per findingId. Two rulings for the same findingId that disagree about \`real\` or \`classification\` is a self-contradictory packet; it is detected mechanically, it cannot be argued past, and it costs a constitutional appeal.

\`constitutiveOpen\` must equal the number of rulings with real=true AND classification="constitutive". It is recomputed from your own rulings after you answer, so a number that disagrees with your list is simply overwritten and recorded as a packet-integrity defect.

${priorRulings.length ? `PRIOR RULINGS — you (in an earlier round of this same gate) already ruled on these. You MAY reverse a prior ruling, but ONLY by citing the artifact change that justifies it: a changed file, a re-run command and its captured output, or an explicit false-positive demonstration. Put that citation in reversalOf.evidence. A reversal with no citation is not a reversal — the prior ruling is reinstated automatically and your reversal is discarded.

${JSON.stringify(priorRulings, null, 2)}
` : ''}
Findings (${findings.length}):
${findings.length ? JSON.stringify(findings, null, 2) : '(none reported)'}`,
  {
    label: 'adversarial:adjudicate',
    phase: 'Adjudicate',
    agentType: 'agent-teams-workforce:adversarial-critique-adjudicator',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['rulings', 'constitutiveOpen'],
      properties: {
        rulings: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['findingId', 'title', 'severity', 'classification', 'real'],
            properties: {
              // Constrained to the ids the script derived, so a ruling cannot be attached
              // to a finding nobody reported and cannot be renamed out of its own history.
              findingId: knownFindingIds.length
                ? { type: 'string', enum: knownFindingIds }
                : { type: 'string' },
              title: { type: 'string' },
              severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
              classification: { type: 'string', enum: ['constitutive', 'competitive'] },
              real: { type: 'boolean' },
              // The ONLY field in which a reversal may be declared. Schema-level, because
              // the prose control ("cite an audit trail", "never downgrade a constitutive
              // finding") already existed in the agent charter and the model rendered no
              // worse for having ignored it.
              reversalOf: {
                type: 'object',
                additionalProperties: false,
                required: ['evidence'],
                properties: {
                  priorReal: { type: 'boolean' },
                  priorClassification: { type: 'string', enum: ['constitutive', 'competitive'] },
                  evidence: { type: 'string' },
                },
              },
            },
          },
        },
        constitutiveOpen: { type: 'integer' },
      },
    },
  }
)

// ── Packet integrity: arithmetic and contradiction, settled in script ──────────
//
// A packet that contradicts itself is a MALFORMED ARTIFACT, not a verdict, and it must
// never reach the gate as one. Looping on it cannot help: nothing about the WORK changed
// between rounds, so no retry of the phase can repair it, and re-running the same
// adjudicator regenerates the contradiction — which is precisely how one run burned all
// three loops re-asking a question the same agent kept answering inconsistently.
//
// Everything below costs zero model turns.
const SEVERITY_RANK = { critical: 4, high: 3, medium: 2, low: 1, info: 0 }
// "More severe" is the tie-break while an appeal is pending: a real constitutive finding
// outranks a not-real or competitive one about the same fact. Believing the softer round
// is how a live credential in a committable file gets waved through.
function severityWeight(r) {
  return (r && r.real ? 4 : 0) + (r && r.classification === 'constitutive' ? 2 : 0) + (SEVERITY_RANK[r && r.severity] || 0) / 10
}
function disagrees(x, y) {
  return !!x && !!y && (x.real !== y.real || x.classification !== y.classification)
}

const rawRulings = (adjudication && Array.isArray(adjudication.rulings) ? adjudication.rulings : []).filter(Boolean)
const constitutiveOpenClaimed = adjudication && typeof adjudication.constitutiveOpen === 'number' ? adjudication.constitutiveOpen : null

// 1. INTRA-PACKET: two rulings for one findingId that disagree.
const contradictions = []
const byId = {}
for (const r of rawRulings) {
  const id = r.findingId || `untracked#${fingerprint(r.title)}`
  const held = byId[id]
  if (!held) {
    byId[id] = r
    continue
  }
  if (disagrees(held, r)) {
    contradictions.push({
      findingId: id,
      kind: 'intra-packet',
      rulings: [
        { real: held.real, classification: held.classification, severity: held.severity, title: held.title },
        { real: r.real, classification: r.classification, severity: r.severity, title: r.title },
      ],
      resolvedTo: 'the more severe ruling, pending a constitutional ruling',
    })
  }
  byId[id] = severityWeight(r) > severityWeight(held) ? r : held
}

// 2. CROSS-ROUND: a reversal of a prior ruling with no citation has NO EFFECT. The prior
//    ruling is reinstated. Reversal itself stays legal — adversarial re-runs against a
//    CHANGED tree, so a finding the fix removed can legitimately flip to real=false, and
//    a blanket ban would deadlock every repaired finding forever.
const unjustifiedReversals = []
for (const id of Object.keys(byId)) {
  const prior = priorById[id]
  const now = byId[id]
  if (!disagrees(prior, now)) continue
  const cited = !!(now.reversalOf && String(now.reversalOf.evidence || '').trim())
  if (cited) continue
  unjustifiedReversals.push({
    findingId: id,
    prior: { real: prior.real, classification: prior.classification, severity: prior.severity },
    attempted: { real: now.real, classification: now.classification, severity: now.severity },
    reason: 'a reversal must cite the artifact change that justifies it — a changed file, a re-run command and its output, or an explicit false-positive demonstration. Uncited, the prior ruling stands.',
  })
  byId[id] = { ...prior, reinstated: true }
}

const rulings = Object.keys(byId).map((k) => byId[k])
// 3. ARITHMETIC: constitutiveOpen is COMPUTED, never taken on the model's word. The
//    invariant is always computable from the rulings list the same packet carries, and
//    nothing anywhere computed it — so a packet could assert constitutiveOpen:0 while its
//    own contents said otherwise, and the gate could only re-derive it by reading.
const constitutiveOpen = rulings.filter((r) => r.real === true && r.classification === 'constitutive').length
const countMismatch = constitutiveOpenClaimed !== null && constitutiveOpenClaimed !== constitutiveOpen

const packetIntegrity = {
  contradictions,
  unjustifiedReversals,
  constitutiveOpenClaimed,
  constitutiveOpen,
  countMismatch,
  priorRulingsSeen: priorRulings.length,
}
if (countMismatch) {
  log(`⚠ adjudication asserted constitutiveOpen=${constitutiveOpenClaimed} but its own rulings contain ${constitutiveOpen} — the computed value stands`)
}
if (contradictions.length) {
  log(`⚠ adjudication is SELF-CONTRADICTORY on ${contradictions.length} finding(s) — the gate escalates to a constitutional ruling rather than looping the same judge`)
}
if (unjustifiedReversals.length) {
  log(`⚠ ${unjustifiedReversals.length} uncited reversal(s) discarded; the prior ruling stands in each case`)
}

return {
  findings,
  adjudication: { ...(adjudication || {}), rulings, constitutiveOpen, constitutiveOpenClaimed },
  packetIntegrity,
  // The single flag the constitutional gate keys on. A contradiction the same agent
  // regenerates is a JUDGE failure: looping cannot repair it, and escalating to the
  // producing phases is wrong too — neither Green nor triage caused the adjudicator to
  // contradict itself. It goes to a DIFFERENT authority.
  selfContradictory: contradictions.length > 0,
  // Which lanes actually ran, and why. Without this a run that narrowed its attack
  // set is indistinguishable from one that ran everything, and "we tested for that"
  // becomes unfalsifiable after the fact.
  attackers,
  laneMode,
  surfaces: declaredSurfaces,
}
