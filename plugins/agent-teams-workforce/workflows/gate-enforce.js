export const meta = {
  name: 'gate-enforce',
  description:
    'Reusable phase gate. DETERMINISTIC checks are evaluated first, directly against the artifact and with no model turn: a phase that failed one is looped immediately with the observed value, and a gate whose criteria are all mechanical passes without adjudication. Remaining JUDGMENT criteria go to an independent phase-gate-enforcer, told which checks are already settled so it cannot re-open them, and it returns pass / loop / escalate. Every judgment criterion carries a CLASS: a `constitutive` one is a hard stop, while a `competitive` one — the default for any criterion nobody deliberately marked otherwise — passes with a flag rather than looping. On a pass that carries competitive flags, the advantage-evaluator applies the advantage principle — proceed-under-flag or revert — without ever halting the pipeline. Every verdict carries `deterministicChecks`, so a caller can tell a criterion that was MEASURED against the artifact from one that was argued about. Enforces segregation of duties: the judge never produced the work it judges.',
  phases: [{ title: 'Gate', detail: 'phase-gate-enforcer adjudicates the artifact' }],
}

// args: {
//   gate: string,                 // gate id, e.g. "2a"
//   phaseName: string,            // human name of the phase being judged
//   criteria: (string | { text: string, class?: 'constitutive'|'competitive' })[],
//                                 // JUDGMENT criteria — adjudicated by the model. See the
//                                 // classification block below. A PLAIN STRING IS
//                                 // COMPETITIVE: a criterion is a hard stop only when
//                                 // someone deliberately said so.
//   calibration?: string,         // optional per-gate calibration — what THIS gate must
//                                 // block on and what it must not. Rendered prominently.
//   checks?: [{ field, equals?, nonEmpty?, matches?, notMatches?, label? }],
//                                 // DETERMINISTIC criteria, see below. `matches` and
//                                 // `notMatches` are regular-expression SOURCE strings
//                                 // (no delimiters, no flags), tested case-insensitively
//                                 // against the field rendered as text.
//   artifact: any,                // the phase output under review
//   escalateTargets?: string[],   // upstream phases this gate may escalate to
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

// ── Criterion CLASS, and why the default is passive ───────────────────────────
//
// The prompt below used to say "Pass criteria (ALL must hold)" and, separately,
// "constitutive criteria are hard stops" — while `criteria` arrived as a flat list of
// strings with nothing marking WHICH ones were constitutive. A judge told hard stops
// exist, given no way to identify them, and asked for a verdict defaults to strict, so
// every criterion behaved as a hard stop. That defeated the machinery built to prevent
// exactly this: the advantage-evaluator (proceed-under-flag vs revert) only runs on a
// verdict of `pass` WITH flags, so an over-strict enforcer that loops instead means the
// passive path never executes at all.
//
// So a criterion now carries its class, and an UNMARKED criterion is COMPETITIVE. The
// asymmetry is deliberate and it is the whole point: the cost of a wrongly-passed
// competitive flag is a revert, and the cost of a wrongly-failed gate is a burned loop
// budget and a dead run. An over-passive gate can be tightened one criterion at a time;
// an over-strict one silently kills correct work.
const CRITERION_CLASSES = ['constitutive', 'competitive']
const criteria = (Array.isArray(a.criteria) ? a.criteria : [])
  .map((c) => {
    if (typeof c === 'string') return { text: c, class: 'competitive' }
    if (c && typeof c === 'object' && typeof c.text === 'string') {
      // An unrecognised class is not an excuse to invent a hard stop. Fall back to the
      // passive default and let the criterion be flagged rather than block the run.
      return { text: c.text, class: CRITERION_CLASSES.includes(c.class) ? c.class : 'competitive' }
    }
    return null
  })
  .filter(Boolean)
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
//
// CHECKS STAY HARD, AND THAT IS WHAT MAKES THE PASSIVE DEFAULT ABOVE SAFE. A check is
// MEASURED against the artifact, not argued about: it has no class, it is always
// blocking, it short-circuits before any model turn, and the uncertainty default the
// enforcer is given below does NOT reach it. Real facts stay enforced mechanically
// precisely so prose judgments can safely become flags. A gate that needs something to
// be genuinely non-negotiable should express it here as a check wherever the artifact
// can carry the field, and only fall back to a `constitutive` criterion when it cannot.
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

const constitutiveCount = criteria.filter((c) => c.class === 'constitutive').length
const calibrationBlock = a.calibration
  ? `\nCALIBRATION FOR THIS GATE — read before ruling. It states what this specific gate must block on and what it must not:\n${a.calibration}\n`
  : ''

const verdict = await agent(
  `You are the phase-gate-enforcer — an INDEPENDENT gate authority. You did not produce this work; you only judge it. Do NOT modify the artifact.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}

Criteria — each is marked CONSTITUTIVE or COMPETITIVE, and the mark decides what an unmet one costs:
${criteria.length ? criteria.map((c, i) => `${i + 1}. [${c.class.toUpperCase()}] ${c.text}`).join('\n') : '(none supplied — treat as a structural sanity check)'}
${calibrationBlock}${settledBlock}
Artifact under review:
${artifactText}

Decide exactly one verdict:
- "pass": no CONSTITUTIVE criterion is unmet. Record every unmet COMPETITIVE criterion, and every non-blocking quality concern, in \`flags\` — and still pass.
- "loop": a CONSTITUTIVE criterion is unmet AND the root cause is INSIDE this phase. Return feedback specific enough that the phase can retry without interpretation.
- "escalate": a CONSTITUTIVE criterion is unmet and the failure originates UPSTREAM (the phase received bad inputs). Name where it goes back to${a.escalateTargets && a.escalateTargets.length ? ` (options: ${a.escalateTargets.join(', ')})` : ''}.

THE DECISION RULE, in full:
- A CONSTITUTIVE criterion that is unmet is a HARD STOP. The verdict is "loop" or "escalate" and is NEVER "pass". These are non-negotiable: they define whether the work is valid at all.${constitutiveCount ? '' : ' (This gate declares none, so nothing here can be a hard stop by criterion — only the settled checks above can block.)'}
- A COMPETITIVE criterion that is unmet still yields "pass", recorded in \`flags\`. It is routed onward to the advantage-evaluator, which rules proceed-under-flag or revert. LOOPING ON A COMPETITIVE CRITERION IS WRONG — it takes the decision away from the role that owns it and stops work that should have proceeded under a flag.
- UNCERTAINTY DEFAULT: when you cannot establish whether a criterion is met, treat it as MET and flag the uncertainty. Do NOT loop for want of evidence about a competitive criterion. This default does NOT extend to constitutive criteria, and it does NOT extend to the deterministic checks above — those were measured, not argued, and are already settled.

WHY IT IS SHAPED THIS WAY. The two errors are not symmetric. A wrongly-PASSED competitive flag costs a revert, which the advantage-evaluator exists to order. A wrongly-FAILED gate costs the phase's whole loop budget and then kills the run, and the correct work in it is lost. So a gate that blocks on a competitive concern is not being careful — it is destroying work that should have proceeded under a flag. When the class is marked competitive, honour it.

For each criterion, state whether it is met with evidence.`,
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

// ── The class is BINDING, not advisory ────────────────────────────────────────
//
// A prompt that says "do not loop on a competitive criterion" is only as good as the
// judge's compliance with it, and the failure mode being fixed here IS a judge defaulting
// to strict under ambiguity. So the two directions of the rule are enforced mechanically,
// both narrowly enough to have no false positives:
//
//   1. Nothing at this gate can be a hard stop by criterion when the gate declares NO
//      constitutive criterion at all. Every deterministic check already held (a failed one
//      short-circuited far above), so a `loop` here is by construction a block on a
//      competitive concern. It becomes a pass and the unmet criteria become flags, which
//      is what routes them to the advantage-evaluator — the role that owns proceed-or-
//      revert. `escalate` is left alone: it is a routing verdict about bad UPSTREAM input,
//      and composites depend on it (Green escalating an unpassable test back to Red).
//
//   2. A `pass` cannot stand while a criterion the caller marked CONSTITUTIVE is reported
//      unmet. Matched by exact text so a paraphrase can never trip it.
let ruled = verdict
if (ruled && ruled.verdict) {
  const unmet = (Array.isArray(ruled.criteria) ? ruled.criteria : []).filter((c) => c && c.met === false)
  const constitutiveTexts = new Set(criteria.filter((c) => c.class === 'constitutive').map((c) => c.text))
  const unmetConstitutive = unmet.filter((c) => constitutiveTexts.has(c.criterion))

  if (ruled.verdict === 'loop' && constitutiveTexts.size === 0) {
    const carried = unmet.map((c) => `competitive criterion unmet: ${c.criterion}${c.evidence ? ` — ${c.evidence}` : ''}`)
    const detail = carried.length ? carried.join('; ') : (ruled.feedback || 'no unmet criterion was itemised')
    log(`Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the enforcer returned LOOP, but this gate declares no constitutive criterion and every deterministic check held — converting to PASS with flags. ${detail}`)
    ruled = {
      ...ruled,
      verdict: 'pass',
      flags: [...(Array.isArray(ruled.flags) ? ruled.flags : []), ...carried],
      classOverride: 'loop-converted-to-pass: no constitutive criterion at this gate',
    }
  } else if (ruled.verdict === 'pass' && unmetConstitutive.length) {
    const detail = unmetConstitutive.map((c) => `${c.criterion}${c.evidence ? ` — ${c.evidence}` : ''}`).join('; ')
    log(`Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the enforcer returned PASS with an unmet CONSTITUTIVE criterion — a constitutive failure is never a pass. Converting to LOOP: ${detail}`)
    ruled = {
      ...ruled,
      verdict: 'loop',
      feedback: `A constitutive criterion is unmet, which is a hard stop: ${detail}. ${ruled.feedback || ''}`.trim(),
      classOverride: 'pass-converted-to-loop: unmet constitutive criterion',
    }
  }
}

// Advantage principle: a PASS that carries competitive (non-constitutive) flags is routed
// to the advantage-evaluator, which decides proceed-under-flag (speculative — commit now,
// observe, revert later) or revert per flag. It NEVER turns a pass into a failure;
// constitutive failures never reach a pass and are out of its scope.
if (ruled && ruled.verdict === 'pass' && Array.isArray(ruled.flags) && ruled.flags.length) {
  const advantage = await agent(
    `You are the advantage-evaluator. These competitive (non-constitutive) concerns surfaced at a PASSING gate. Apply the advantage principle: for each, decide whether to PROCEED under a flag (speculative execution — commit now, observe the outcome, revert later if it proves out badly) or REVERT now. You NEVER halt the pipeline for a non-invalidating finding; constitutive failures are out of your scope.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}
Competitive flags:
${ruled.flags.map((f, i) => `${i + 1}. ${f}`).join('\n')}`,
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
  return { ...ruled, advantage: advantage || null, deterministicChecks: checkResults }
}

// The deterministic results ride out on EVERY verdict, not just the ones this file
// short-circuits on. On the judgment path they reach the enforcer only as prose in
// `settledBlock` and never appeared in the returned verdict at all — so the caller
// holding a `loop` verdict could not tell a criterion that was MEASURED against the
// artifact from one that was argued about. That distinction is the whole basis on which
// an exhausted gate is ruled competitive or constitutive upstream: a mechanically-settled
// failure is not a matter of opinion and must never be waived as one.
return ruled ? { ...ruled, deterministicChecks: checkResults } : ruled
