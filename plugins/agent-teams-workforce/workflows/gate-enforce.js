export const meta = {
  name: 'gate-enforce',
  description:
    'Reusable phase gate. DETERMINISTIC checks are evaluated first, directly against the artifact and with no model turn: a phase that failed one is looped immediately with the observed value, and a gate whose criteria are all mechanical passes without adjudication. Remaining JUDGMENT criteria go to an independent phase-gate-enforcer, told which checks are already settled so it cannot re-open them, and it returns pass / loop / escalate. On a pass that carries competitive (non-constitutive) flags, the advantage-evaluator applies the advantage principle — proceed-under-flag or revert — without ever halting the pipeline. Every verdict carries `deterministicChecks`, so a caller can tell a criterion that was MEASURED against the artifact from one that was argued about. Enforces segregation of duties: the judge never produced the work it judges.',
  phases: [{ title: 'Gate', detail: 'phase-gate-enforcer adjudicates the artifact' }],
}

// args: {
//   gate: string,                 // gate id, e.g. "2a"
//   phaseName: string,            // human name of the phase being judged
//   criteria: string[],           // JUDGMENT criteria (ALL must hold) — adjudicated by the model
//   checks?: [{ field, equals?, nonEmpty?, matches?, notMatches?, label? }],
//                                 // DETERMINISTIC criteria, see below. `matches` and
//                                 // `notMatches` are regular-expression SOURCE strings
//                                 // (no delimiters, no flags), tested case-insensitively
//                                 // against the field rendered as text.
//   artifact: any,                // the phase output under review
//   escalateTargets?: string[],   // upstream phases this gate may escalate to
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const criteria = Array.isArray(a.criteria) ? a.criteria : []
const artifactText =
  typeof a.artifact === 'string' ? a.artifact : JSON.stringify(a.artifact ?? {}, null, 2)

// ── Deterministic checks, evaluated BEFORE any model turn ─────────────────────
//
// Some gate criteria are not judgments at all. "The previously-failing test now
// passes" is a boolean the phase already reported and already proved by running
// the suite; handing it to a model to reason about re-derives by discussion what
// execution settled, and pays a full subagent turn to do it. Worse, a phase that
// plainly failed still paid that turn before being told so.
//
// These are declarative rather than functions because args cross a workflow
// boundary as JSON. Each names a field on the artifact and the shape it must have.
// A failure here is unambiguous, so it short-circuits to a loop verdict with the
// observed value as feedback and no model is consulted. Judgment criteria —
// "the test asserts real behavior", "the change is minimal" — stay with the model,
// which is told the deterministic ones are already settled so it does not re-open
// them.
//
// `matches` / `notMatches` exist for NEGATIVE CONTROLS over captured output — the
// class of check a model can always argue with in prose but cannot argue with as a
// regex. The motivating case: Red "evidence" whose captured output is a collection or
// import failure (`ModuleNotFoundError`, `collected 0 items`) rather than a product
// failure. Carried as prose for the enforcer to weigh, that was routinely weighed away.
const checks = Array.isArray(a.checks) ? a.checks : []
function asText(value) {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map((v) => asText(v)).join('\n')
  return JSON.stringify(value)
}
const checkResults = checks.map((chk) => {
  const value = a.artifact ? a.artifact[chk.field] : undefined
  let met
  let evidence = `observed ${chk.field} = ${JSON.stringify(value)}`
  if (Object.prototype.hasOwnProperty.call(chk, 'equals')) met = value === chk.equals
  else if (chk.nonEmpty) met = Array.isArray(value) ? value.length > 0 : String(value ?? '').trim().length > 0
  else if (chk.matches || chk.notMatches) {
    const source = chk.matches || chk.notMatches
    const text = asText(value)
    let re = null
    try {
      re = new RegExp(source, 'i')
    } catch (e) {
      // An unusable pattern must not silently pass the check it was written to enforce.
      re = null
      met = false
      evidence = `check pattern /${source}/ is not a valid regular expression (${e && e.message ? e.message : e}) — the check cannot be evaluated and fails closed`
    }
    if (re) {
      const hit = re.test(text)
      met = chk.matches ? hit : !hit
      const excerpt = text.length > 300 ? `${text.slice(0, 300)}…` : text
      evidence = `${chk.matches ? 'required' : 'forbidden'} pattern /${source}/i ${hit ? 'MATCHED' : 'did not match'} ${chk.field}: ${JSON.stringify(excerpt)}`
    }
  } else met = value !== undefined && value !== null
  return {
    criterion: chk.label || `${chk.field} satisfies its required shape`,
    met,
    evidence,
  }
})
const failedChecks = checkResults.filter((r) => !r.met)

// Fail closed: a gate with NEITHER judgment criteria nor deterministic checks is a
// misconfiguration, not a pass. Refuse rather than silently green-light unjudged work.
if (!criteria.length && !checks.length) {
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}) was invoked with no pass criteria and no deterministic checks — refusing to adjudicate. Supply the gate's criteria upstream.`,
    escalateTo: (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    flags: ['gate-misconfiguration: empty criteria'],
    deterministicChecks: checkResults,
  }
}

phase('Gate')

if (failedChecks.length) {
  const detail = failedChecks.map((r) => `${r.criterion} — ${r.evidence}`).join('; ')
  log(`Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): LOOP on deterministic check(s), no adjudication needed — ${detail}`)
  return {
    verdict: 'loop',
    criteria: checkResults,
    feedback: `The phase did not meet a mechanically-verified condition, so there is nothing to adjudicate: ${detail}. Fix that and re-run; do not argue the observation.`,
    flags: [],
    deterministic: true,
    deterministicChecks: checkResults,
  }
}

// Every criterion was mechanical and every one held — nothing is left to judge.
if (!criteria.length) {
  log(`Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): PASS on deterministic checks alone, no adjudication needed`)
  return {
    verdict: 'pass',
    criteria: checkResults,
    feedback: 'All criteria for this gate were mechanically verified against the artifact and hold.',
    flags: [],
    deterministic: true,
    deterministicChecks: checkResults,
  }
}

const settledBlock = checkResults.length
  ? `\nAlready SETTLED by direct inspection of the artifact — treat these as met and do NOT re-open them:\n${checkResults.map((r) => `- ${r.criterion} (${r.evidence})`).join('\n')}\n`
  : ''

const verdict = await agent(
  `You are the phase-gate-enforcer — an INDEPENDENT gate authority. You did not produce this work; you only judge it. Do NOT modify the artifact.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}

Pass criteria (ALL must hold):
${criteria.length ? criteria.map((c, i) => `${i + 1}. ${c}`).join('\n') : '(none supplied — treat as a structural sanity check)'}
${settledBlock}
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
  return { ...verdict, advantage: advantage || null, deterministicChecks: checkResults }
}

// The deterministic results ride out on EVERY verdict, not just the ones this file
// short-circuits on. On the judgment path they reach the enforcer only as prose in
// `settledBlock` and never appeared in the returned verdict at all — so the caller
// holding a `loop` verdict could not tell a criterion that was MEASURED against the
// artifact from one that was argued about. That distinction is the whole basis on which
// an exhausted gate is ruled competitive or constitutive upstream: a mechanically-settled
// failure is not a matter of opinion and must never be waived as one.
return verdict ? { ...verdict, deterministicChecks: checkResults } : verdict
