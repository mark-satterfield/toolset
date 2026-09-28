export const meta = {
  name: 'gate-constitutional',
  description:
    'Constitutional phase gate. The phase-gate-enforcer judges the artifact against constitutive criteria and returns pass, loop or escalate. An artifact whose adversarial adjudication contradicts itself goes to the constitutional-agent instead, which rules each contradicted finding; the gate passes when no constitutive finding remains open and escalates otherwise. A session that returns nothing escalates with dispatchFailed.',
  phases: [{ title: 'Gate (constitutional)', detail: 'one enforcer session, or one constitutional-agent ruling on a self-contradictory packet' }],
}

const PHASE = 'Gate (constitutional)'

// Returns { out, failure }: out is the agent result or null; failure describes a null result.
async function run(prompt, opts) {
  let message = 'returned nothing'
  try {
    const out = await agent(prompt, opts)
    if (out) return { out, failure: null }
  } catch (err) {
    message = String((err && err.message) || err).slice(0, 300)
  }
  log(`${opts.label}: no structured result — ${message}`)
  return { out: null, failure: { label: opts.label, agentType: opts.agentType || null, phase: PHASE, message } }
}

// args: { gate, phaseName, criteria: (string | { text })[], artifact, escalateTargets?: string[] }
// returns: { verdict: 'pass'|'loop'|'escalate', criteria, feedback, escalateTo?, rulings?, constitutiveOpen?, dispatchFailed?, dispatchFailures? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const criteria = (Array.isArray(a.criteria) ? a.criteria : [])
  .map((c) => (typeof c === 'string' ? c : c && typeof c.text === 'string' ? c.text : ''))
  .filter((c) => c.trim())
const escalateTarget = (Array.isArray(a.escalateTargets) && a.escalateTargets[0]) || 'upstream'
const where = `Gate ${a.gate || '?'} (${a.phaseName || 'phase'})`

function asObject(value) {
  if (value && typeof value === 'object') return value
  if (typeof value !== 'string') return null
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

const artifact = asObject(a.artifact)
const artifactText = typeof a.artifact === 'string' ? a.artifact : JSON.stringify(a.artifact ?? {}, null, 2)
const integrity = artifact ? asObject(artifact.packetIntegrity) : null
const contradictions = integrity && Array.isArray(integrity.contradictions) ? integrity.contradictions : []

phase('Gate (constitutional)')

if (contradictions.length) {
  const ids = [...new Set(contradictions.map((cx) => cx && cx.findingId).filter(Boolean))]
  const findings = (Array.isArray(artifact.findings) ? artifact.findings : []).filter((f) => f && ids.includes(f.findingId))
  const adjudication = asObject(artifact.adjudication)
  const rulings = adjudication && Array.isArray(adjudication.rulings) ? adjudication.rulings : []

  const { out: ruling, failure } = await run(
    `The adversarial adjudication for gate ${a.gate || '?'} (${a.phaseName || 'phase'}) ruled the same finding two opposite ways. Rule, for EACH finding below, which reading stands: is the finding real, and is it constitutive (a security/validity hard stop) or competitive? Judge from the finding's reproduction. Where you cannot establish the softer reading, the more severe one stands.

Contradictions:
${JSON.stringify(contradictions, null, 2)}

The findings they are about:
${findings.length ? JSON.stringify(findings, null, 2) : '(the packet carries no finding records for these ids — rule from the contradictions above)'}

Return exactly one resolution per findingId: ${ids.join(', ')}.`,
    {
      label: `constitutional:${a.gate || 'gate'}`,
      effort: 'high',
      phase: PHASE,
      agentType: 'agent-teams-workforce:constitutional-agent',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['resolutions', 'rationale'],
        properties: {
          resolutions: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['findingId', 'real', 'classification', 'rationale'],
              properties: {
                findingId: { type: 'string' },
                real: { type: 'boolean' },
                classification: { type: 'string', enum: ['constitutive', 'competitive'] },
                rationale: { type: 'string' },
              },
            },
          },
          rationale: { type: 'string' },
        },
      },
    }
  )

  if (!ruling) {
    const why = `${where}: the constitutional-agent returned no ruling on the self-contradictory adjudication.`
    return { verdict: 'escalate', criteria: [], feedback: why, escalateTo: escalateTarget, dispatchFailed: true, dispatchFailures: [failure] }
  }

  const resolved = {}
  for (const r of ruling.resolutions) if (r && ids.includes(r.findingId)) resolved[r.findingId] = r
  const finalRulings = rulings.map((r) =>
    r && resolved[r.findingId] ? { ...r, real: resolved[r.findingId].real, classification: resolved[r.findingId].classification } : r
  )
  for (const id of Object.keys(resolved)) {
    if (!finalRulings.some((r) => r && r.findingId === id)) {
      finalRulings.push({ findingId: id, real: resolved[id].real, classification: resolved[id].classification })
    }
  }
  const open = finalRulings.filter((r) => r && r.real === true && r.classification === 'constitutive')
  log(`${where}: contradiction ruled — ${open.length} constitutive finding(s) open`)
  return {
    verdict: open.length ? 'escalate' : 'pass',
    criteria: finalRulings.map((r) => ({
      criterion: `finding ${r && r.findingId}`,
      met: !(r && r.real === true && r.classification === 'constitutive'),
      evidence: `real=${r && r.real}, classification=${r && r.classification}`,
    })),
    feedback: open.length
      ? `${open.length} constitutive finding(s) remain open after the constitutional ruling: ${open.map((r) => r.findingId).join(', ')}. ${ruling.rationale}`
      : `No constitutive finding remains open after the constitutional ruling. ${ruling.rationale}`,
    ...(open.length ? { escalateTo: escalateTarget } : {}),
    constitutiveOpen: open.length,
    rulings: finalRulings,
  }
}

const { out: verdict, failure } = await run(
  `You are the phase-gate-enforcer at a CONSTITUTIONAL gate. These criteria are constitutive: if one fails, the verdict is "loop" or "escalate", never "pass". You only judge; you do not modify.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}

Constitutive criteria (ALL must hold):
${criteria.length ? criteria.map((c, i) => `${i + 1}. ${c}`).join('\n') : '(none supplied)'}

Artifact under review:
${artifactText}

Verdicts:
- "pass": every constitutive criterion is met, with evidence.
- "loop": a criterion fails and is fixable within the phase — give precise feedback.
- "escalate": failure originates upstream${Array.isArray(a.escalateTargets) && a.escalateTargets.length ? ` (options: ${a.escalateTargets.join(', ')})` : ''}.
Return one entry in \`criteria\` per criterion listed above, in the same order. Keep each \`evidence\` under 40 words and \`feedback\` under 200.`,
  {
    label: `gate-const:${a.gate || a.phaseName || 'phase'}`,
    effort: 'high',
    phase: PHASE,
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
            properties: { criterion: { type: 'string' }, met: { type: 'boolean' }, evidence: { type: 'string' } },
          },
        },
        feedback: { type: 'string' },
        escalateTo: { type: 'string' },
      },
    },
  }
)

if (!verdict) {
  const why = `${where}: the phase-gate-enforcer returned no verdict; the work was not judged.`
  return { verdict: 'escalate', criteria: [], feedback: why, escalateTo: escalateTarget, dispatchFailed: true, dispatchFailures: [failure] }
}

if (verdict.verdict === 'escalate' && !verdict.escalateTo) verdict.escalateTo = escalateTarget
return verdict
