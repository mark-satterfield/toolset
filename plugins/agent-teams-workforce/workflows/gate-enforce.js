export const meta = {
  name: 'gate-enforce',
  description:
    'Reusable phase gate. An independent phase-gate-enforcer judges a phase artifact against explicit criteria and returns pass / loop / escalate. On a pass that carries competitive (non-constitutive) flags, the advantage-evaluator applies the advantage principle — proceed-under-flag or revert — without ever halting the pipeline. Enforces segregation of duties: the judge never produced the work it judges.',
  phases: [{ title: 'Gate', detail: 'phase-gate-enforcer adjudicates the artifact' }],
}

// args: {
//   gate: string,                 // gate id, e.g. "2a"
//   phaseName: string,            // human name of the phase being judged
//   criteria: string[],           // pass criteria (ALL must hold)
//   artifact: any,                // the phase output under review
//   escalateTargets?: string[],   // upstream phases this gate may escalate to
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const criteria = Array.isArray(a.criteria) ? a.criteria : []
const artifactText =
  typeof a.artifact === 'string' ? a.artifact : JSON.stringify(a.artifact ?? {}, null, 2)

// Fail closed: an empty criteria set is a gate misconfiguration, not a pass.
// Refuse to adjudicate rather than silently green-light unjudged work.
if (!criteria.length) {
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}) was invoked with no pass criteria — refusing to adjudicate. Supply the gate's criteria upstream.`,
    escalateTo: (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    flags: ['gate-misconfiguration: empty criteria'],
  }
}

phase('Gate')

const verdict = await agent(
  `You are the phase-gate-enforcer — an INDEPENDENT gate authority. You did not produce this work; you only judge it. Do NOT modify the artifact.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}

Pass criteria (ALL must hold):
${criteria.length ? criteria.map((c, i) => `${i + 1}. ${c}`).join('\n') : '(none supplied — treat as a structural sanity check)'}

Artifact under review:
${artifactText}

Decide exactly one verdict:
- "pass": every criterion is met. Note any non-blocking competitive/quality concerns as flags, but still pass.
- "loop": a criterion is unmet AND the root cause is INSIDE this phase. Return feedback specific enough that the phase can retry without interpretation.
- "escalate": the failure originates UPSTREAM (the phase received bad inputs). Name where it goes back to${a.escalateTargets && a.escalateTargets.length ? ` (options: ${a.escalateTargets.join(', ')})` : ''}.

Constitutive criteria are hard stops — if one fails, the verdict is never "pass". For each criterion, state whether it is met with evidence.`,
  {
    label: `gate:${a.gate || a.phaseName || 'phase'}`,
    phase: 'Gate',
    agentType: 'agent-teams-workforce:phase-gate-enforcer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['verdict', 'criteria', 'feedback'],
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
        flags: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// Advantage principle: a PASS that carries competitive (non-constitutive) flags is routed
// to the advantage-evaluator, which decides proceed-under-flag (speculative — commit now,
// observe, revert later) or revert per flag. It NEVER turns a pass into a failure;
// constitutive failures never reach a pass and are out of its scope.
if (verdict && verdict.verdict === 'pass' && Array.isArray(verdict.flags) && verdict.flags.length) {
  const advantage = await agent(
    `You are the advantage-evaluator. These competitive (non-constitutive) concerns surfaced at a PASSING gate. Apply the advantage principle: for each, decide whether to PROCEED under a flag (speculative execution — commit now, observe the outcome, revert later if it proves out badly) or REVERT now. You NEVER halt the pipeline for a non-invalidating finding; constitutive failures are out of your scope.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}
Competitive flags:
${verdict.flags.map((f, i) => `${i + 1}. ${f}`).join('\n')}`,
    {
      label: `advantage:${a.gate || a.phaseName || 'phase'}`,
      phase: 'Gate',
      agentType: 'agent-teams-workforce:advantage-evaluator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['dispositions'],
        properties: {
          dispositions: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['flag', 'disposition'],
              properties: {
                flag: { type: 'string' },
                disposition: { type: 'string', enum: ['proceed-under-flag', 'revert'] },
                rationale: { type: 'string' },
              },
            },
          },
        },
      },
    }
  )
  return { ...verdict, advantage: advantage || null }
}

return verdict
