export const meta = {
  name: 'adversarial',
  description:
    'Shared-tail mini — Adversarial Validation (feeds the constitutional Gate 4). Two attack lanes run concurrently against the change in DESIGNATED TEST ENVIRONMENTS ONLY; an independent adversarial-critique-adjudicator referees severity. Security findings are constitutive and cannot be downgraded by implementers.',
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
const attackers = requested.length ? requested : allAttackers
if (Array.isArray(a.trimmedScope) && a.trimmedScope.length && !requested.length) {
  log(`⚠ trimmedScope matched no known attacker (${a.trimmedScope.join(', ')}) — running all lanes`)
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

return { findings, adjudication }
