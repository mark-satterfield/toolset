export const meta = {
  name: 'gate-constitutional',
  description:
    'Constitutional phase gate (PRD-to-Spec pipeline Gate 2, Spec-to-Deploy pipeline Gate 4). The phase-gate-enforcer judges with constitutive criteria as HARD stops — security/validity findings cannot be downgraded or flagged-past. Novel conflicts the enforcer cannot resolve are escalated to the constitutional-agent for a binding ruling.',
  phases: [{ title: 'Gate (constitutional)', detail: 'hard-stop adjudication + appeals' }],
}

// args: { gate, phaseName, criteria: string[], artifact, escalateTargets?: string[] }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const criteria = Array.isArray(a.criteria) ? a.criteria : []
const artifactText =
  typeof a.artifact === 'string' ? a.artifact : JSON.stringify(a.artifact ?? {}, null, 2)

// Fail closed: constitutive criteria MUST be present. An empty set cannot pass —
// that would be a silent constitutional bypass.
if (!criteria.length) {
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: `Constitutional gate ${a.gate || '?'} (${a.phaseName || 'phase'}) was invoked with no constitutive criteria — refusing to adjudicate. Constitutive criteria must be present and non-empty.`,
    escalateTo: (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    needsConstitutionalRuling: false,
  }
}

phase('Gate (constitutional)')

const verdict = await agent(
  `You are the phase-gate-enforcer at a CONSTITUTIONAL gate. These criteria are constitutive — they define validity. There is NO pass-with-flag here: if a criterion fails, the verdict is "loop" or "escalate", never "pass". Producing agents (e.g. implementers) CANNOT downgrade a finding. You only judge; you do not modify.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}

Constitutive criteria (ALL must hold):
${criteria.length ? criteria.map((c, i) => `${i + 1}. ${c}`).join('\n') : '(none supplied)'}

Artifact under review:
${artifactText}

Verdicts:
- "pass": every constitutive criterion is met, with evidence.
- "loop": a criterion fails and is fixable within the phase — give precise feedback.
- "escalate": failure originates upstream${a.escalateTargets && a.escalateTargets.length ? ` (options: ${a.escalateTargets.join(', ')})` : ''}.
If you encounter a NOVEL conflict between constitutive objectives that you cannot resolve from the criteria alone, set needsConstitutionalRuling=true and describe the conflict.`,
  {
    label: `gate-const:${a.gate || a.phaseName || 'phase'}`,
    phase: 'Gate (constitutional)',
    agentType: 'agent-teams-workforce:phase-gate-enforcer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['verdict', 'criteria', 'feedback', 'needsConstitutionalRuling'],
      properties: {
        verdict: { type: 'string', enum: ['pass', 'loop', 'escalate'] },
        criteria: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['criterion', 'met', 'evidence'],
            properties: {
              criterion: { type: 'string' },
              met: { type: 'boolean' },
              evidence: { type: 'string' },
            },
          },
        },
        feedback: { type: 'string' },
        escalateTo: { type: 'string' },
        needsConstitutionalRuling: { type: 'boolean' },
        conflict: { type: 'string' },
      },
    },
  }
)

// Appeals court: only on a novel unresolved constitutive conflict.
if (verdict && verdict.needsConstitutionalRuling) {
  log(`Constitutional gate ${a.gate}: novel conflict — escalating to constitutional-agent`)
  const ruling = await agent(
    `A constitutional gate hit a novel conflict between constitutive objectives that the enforcer could not resolve. Rule on it by consulting the system's founding objectives (the BRD). Your ruling is binding and becomes reusable precedent.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}
Conflict: ${verdict.conflict || '(unspecified)'}
Enforcer feedback: ${verdict.feedback || ''}`,
    {
      label: `constitutional:${a.gate}`,
      phase: 'Gate (constitutional)',
      agentType: 'agent-teams-workforce:constitutional-agent',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'rationale'],
        properties: {
          verdict: { type: 'string', enum: ['pass', 'loop', 'escalate'] },
          rationale: { type: 'string' },
          precedent: { type: 'string' },
          escalateTo: { type: 'string' },
        },
      },
    }
  )
  if (ruling) {
    return {
      verdict: ruling.verdict,
      criteria: verdict.criteria,
      feedback: ruling.rationale,
      escalateTo: ruling.escalateTo || verdict.escalateTo,
      ruledByConstitutionalAgent: true,
      precedent: ruling.precedent,
    }
  }
}

return verdict
