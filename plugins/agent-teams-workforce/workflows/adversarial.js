export const meta = {
  name: 'adversarial',
  description:
    'Shared-tail mini — Adversarial Validation (feeds the constitutional Gate 4). Attackers run concurrently against the change in DESIGNATED TEST ENVIRONMENTS ONLY; an independent adversarial-critique-adjudicator referees severity. The lane set is DERIVED from the surfaces the contract declares — most attack classes need a surface to attack — over a BASELINE of data-exposure and dependency-CVE scanning that always runs and that no surface list can remove, because those apply to any code change. An undeclared surface list means unknown, not empty, and runs every lane; a caller-supplied trimmedScope wins. Security findings are constitutive and cannot be downgraded by implementers.',
  phases: [
    { title: 'Attack', detail: 'access-control + data-integrity and infra + exposure lanes (concurrent)' },
    { title: 'Adjudicate', detail: 'referee severity; classify constitutive vs competitive' },
  ],
}

// args: { contract, green, trimmedScope?, feedback? }
//   trimmedScope?: string[]  // restrict the attack to these attacker agents (e.g. the
//                            // infra path's infra-only lane). Empty/absent → run all lanes.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const feedback = a.feedback ? `\nPrior gate feedback to address:\n${a.feedback}` : ''
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
const target = `Change under attack: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}. Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}. DESIGNATED TEST ENVIRONMENTS ONLY — never attack production. Work within: ${repo}`

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
const findings = results.filter(Boolean).flatMap((r) => r.findings || [])

phase('Adjudicate')
const adjudication = await agent(
  `You are the adversarial-critique-adjudicator (Referee). Rule on each finding's real severity and whether it is CONSTITUTIVE (a security/validity hard stop — implementers cannot downgrade it) or COMPETITIVE (a tradeable quality concern). Discard false positives with reasoning.

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
            required: ['title', 'severity', 'classification', 'real'],
            properties: {
              title: { type: 'string' },
              severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
              classification: { type: 'string', enum: ['constitutive', 'competitive'] },
              real: { type: 'boolean' },
            },
          },
        },
        constitutiveOpen: { type: 'integer' },
      },
    },
  }
)

return {
  findings,
  adjudication,
  // Which lanes actually ran, and why. Without this a run that narrowed its attack
  // set is indistinguishable from one that ran everything, and "we tested for that"
  // becomes unfalsifiable after the fact.
  attackers,
  laneMode,
  surfaces: declaredSurfaces,
}
