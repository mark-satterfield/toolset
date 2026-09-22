export const meta = {
  name: 'gate-enforce',
  description:
    'Reusable phase gate. DETERMINISTIC checks are evaluated first, directly against the artifact and with no model turn: a phase that failed one is looped immediately with the observed value, and a gate whose criteria are all mechanical passes without adjudication. Remaining JUDGMENT criteria go to an independent phase-gate-enforcer, told which checks are already settled so it cannot re-open them, and it returns pass / loop / escalate. Every judgment criterion carries a CLASS: a `constitutive` one is a hard stop, while a `competitive` one — the default for any criterion nobody deliberately marked otherwise — passes with a flag rather than looping. On a pass that carries competitive flags, the advantage-evaluator applies the advantage principle — proceed-under-flag or revert — without ever halting the pipeline. Every verdict carries `deterministicChecks`, so a caller can tell a criterion that was MEASURED against the artifact from one that was argued about. Enforces segregation of duties: the judge never produced the work it judges.',
  phases: [{ title: 'Gate', detail: 'phase-gate-enforcer adjudicates the artifact' }],
}
// ── EVERY DISPATCH IS SETTLED ────────────────────────────────────────────────────
//
// `agent()` fails in two different ways and the scripts used to conflate them. It
// RETURNS NULL when a subagent is skipped or dies on a terminal API error after the
// runtime's own retries. It THROWS when a subagent finishes without calling
// StructuredOutput — and an uncaught throw leaves this script, leaves whatever
// composite called it, and kills the run: two recorded crashes cost 1.13M and 1.88M
// tokens and discarded every artifact the run had already paid for.
//
// So every dispatch in this file goes through settleAgent(). A throw never escapes it,
// and it records what the engine's error text loses — that text reads
// `agent({schema}): subagent completed without calling StructuredOutput`, which names
// neither the agent, nor the phase, nor the schema, and points at no transcript. The
// caller receives null, which every call site already handles, and `dispatchFailures`
// carries the identity of what died, for the `dispatchFailed` report this script owes
// its caller: a phase whose producing agents died is NOT adjudicated.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.schemaName
  const who = {
    agentType: o.agentType || null,
    label: o.label || null,
    phase: o.phase || null,
    schema: settleSchemaName(o),
  }
  const name = who.label || who.agentType || 'agent'
  const whose = `${name}${who.agentType && who.agentType !== name ? ` (${who.agentType})` : ''}${who.phase ? ` in ${who.phase}` : ''}`
  let out = null
  try {
    out = await agent(prompt, call)
  } catch (err) {
    const message = String((err && err.message) || err)
    dispatchFailures.push({
      ...who,
      outcome: 'threw',
      message: message.slice(0, 300),
      transcript: settleTranscript(err, name),
      note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''}: ${message.slice(0, 160)}`,
    })
    log(`${name}: session ended without a structured result — ${message.slice(0, 160)}`)
    // A caller that owns its own failure reporting asks for the throw back, so the real
    // reason reaches its catch instead of being flattened to "returned no result".
    if (o.rethrow) throw err
    return null
  }
  if (out) return out
  dispatchFailures.push({
    ...who,
    outcome: 'skipped',
    message: null,
    transcript: settleTranscript(null, name),
    note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
  })
  log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
  return null
}

// ── THE `dispatchFailed` CONTRACT THIS GATE OWES ITS CALLER ──────────────────────
//
// A judge that DIED did not find the work wanting — it never ruled. This file built
// `dispatchFailures` and defined `dispatchDeaths` above and then called neither, so a dead
// enforcer returned null, and every caller reads a null verdict as `ok:false, "gate N
// returned no verdict"` and ends the phase. A phase whose work is COMPLETE AND DURABLE was
// therefore discarded because the read-only judge hit an account limit, and it was filed as
// a failure of that phase rather than of the environment — which is how a bead gets blamed,
// and eventually quarantined, for a wall nobody could have avoided.
//
// The asymmetry is the same one that governs the producing phases: a death is reported AS a
// death, so the caller can tell "the work is bad" from "nobody looked". Every gate exit that
// comes of a dead dispatch carries `dispatchFailed: true` and the identities of what died.
const failDispatch = (reason, ...phases) => {
  const deaths = dispatchDeaths(...phases)
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: reason,
    escalateTo: 'upstream',
    flags: [`gate-dispatch-failed: ${reason}`],
    ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
  }
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
//   structural?: { requireOk?: boolean, required?: string[], nonEmpty?: string[] },
//                                 // STRUCTURAL criteria — see below. Expressed here rather
//                                 // than as hand-written `checks` because every gate needs
//                                 // the same three questions answered and spelling them out
//                                 // per call site is how they came to be answered nowhere.
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
// ── STRUCTURAL checks, derived BEFORE any quality judgment ────────────────────
//
// A gate used to ask a model whether work was good before anything established that the
// work EXISTS. Three questions are not judgments at all — did the phase report ok, did it
// produce the artifacts it is answerable for, and is the set it was asked to fill
// non-empty — and a phase that fails one of them has produced nothing there is an opinion
// to have about.
//
// Getting this wrong is not a near-miss, because of where the competitive path sits. A
// gate whose criteria are all competitive converts a `loop` into a `pass` with flags (see
// the conversion far below), which is correct for a reviewer's opinion and catastrophic
// for an absent artifact: the run proceeds, flags "the spec set is incomplete", and the
// phases downstream build on nothing. So a failed structural check must never reach that
// conversion.
//
// It cannot, and the reason is structural rather than a second guard: these are ordinary
// DETERMINISTIC checks — the concept this file already has — so they short-circuit to a
// loop verdict above the model turn and far above the conversion, carrying the observed
// value as feedback. They are simply derived from a declaration rather than hand-written
// per call site, because every gate needs the same three questions asked and spelling them
// out at each one is exactly how they came to be asked at none.
const structural = a.structural && typeof a.structural === 'object' ? a.structural : null
const structuralChecks = []
if (structural) {
  // `ok` is opt-in per gate, never universal: several minis legitimately return no `ok`
  // field at all, and asserting one against them would fail every gate they sit behind.
  // A gate declares this only when its phase genuinely reports `ok`.
  if (structural.requireOk === true) {
    structuralChecks.push({ field: 'ok', equals: true, label: 'the phase reports ok:true' })
  }
  // Presence, not shape. The default check arm treats undefined and null as unmet, which
  // is the whole question here — the artifact either came back or it did not.
  for (const field of Array.isArray(structural.required) ? structural.required : []) {
    if (typeof field === 'string' && field) {
      structuralChecks.push({ field, label: `the phase produced its required artifact '${field}'` })
    }
  }
  // "A non-empty task set where one is expected" — a decomposition that emitted no task
  // has not decomposed anything, however well it reads.
  for (const field of Array.isArray(structural.nonEmpty) ? structural.nonEmpty : []) {
    if (typeof field === 'string' && field) {
      structuralChecks.push({ field, nonEmpty: true, label: `'${field}' is present and non-empty` })
    }
  }
}
// Structural first, so the feedback on a broken artifact names what is missing before it
// names anything a caller's own check observed about it.
const checks = [...structuralChecks, ...(Array.isArray(a.checks) ? a.checks : [])]
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

const verdict = await settleAgent(
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

READING BUDGET (binding): the artifact is quoted above in full and the deterministic checks already measured everything mechanical about it. Judge what is in front of you. Do not re-derive the artifact from the codebase, do not survey the repository or the polyrepo, and do not go looking for evidence a criterion does not name — the uncertainty default above already tells you what to do when evidence is thin. Roughly five tool calls is the expected shape; zero is normal for this role.

For each criterion, state whether it is met with evidence.`,
  {
    label: `gate:${a.gate || a.phaseName || 'phase'}`,
    // The enforcer adjudicates a short structured artifact against a handful of stated
    // criteria, with the mechanical part already settled above and a binding reading
    // budget below. That is a medium-effort judgment, and at `high` it was ~9% of the
    // measured per-Epic spend on its own.
    effort: 'medium',
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

  // ── A VERDICT THAT RECORDS NO REASON IS A DEFECT, NOT A RULING ───────────────
  //
  // Across the recorded runs, seventeen gates exhausted their retries and killed the run.
  // Six of those final verdicts named nothing at all — no unmet criterion, no flag, no
  // feedback — and one exhaustion was ruled `constitutive` on empty findings AND an empty
  // rationale. A retry against an empty answer has nothing to fix, so it meets the same
  // wall, spends the loop budget, and every artifact the run had already paid for is
  // discarded on the strength of a judgment that stated no reason.
  //
  // So a verdict that still BLOCKS after the class conversions above, while naming no
  // unmet criterion, no flag and no feedback, is treated as a malformed verdict rather
  // than a ruling on the work. It is surfaced the way this file already surfaces a broken
  // gate rather than broken work — an `escalate` carrying the gate and the phase by name
  // (see the empty-criteria refusal far above) — so the caller reports a defect in the
  // judgment instead of silently ruling the work constitutive.
  //
  // A verdict that DOES state a reason is untouched, however briefly it states it. This
  // weakens no gate: nothing here overturns an itemised finding, and a `pass` cannot
  // reach it.
  const statedReason =
    unmet.length > 0 ||
    (Array.isArray(ruled.flags) && ruled.flags.some((f) => String(f == null ? '' : f).trim())) ||
    (typeof ruled.feedback === 'string' && ruled.feedback.trim().length > 0)
  if ((ruled.verdict === 'loop' || ruled.verdict === 'escalate') && !statedReason) {
    const where = `Gate ${a.gate || '?'} (${a.phaseName || 'phase'})`
    const why =
      `${where}: MALFORMED VERDICT — the enforcer returned ${ruled.verdict.toUpperCase()} but named no unmet criterion, ` +
      'no flag and no feedback. A retry has nothing to fix and a ruling has nothing to weigh, so this is a defect in the ' +
      'adjudication rather than a finding about the work. It is NOT a constitutive failure and must not be recorded as one.'
    log(why)
    ruled = {
      ...ruled,
      verdict: 'escalate',
      feedback: why,
      escalateTo: ruled.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
      flags: [...(Array.isArray(ruled.flags) ? ruled.flags : []), `gate-malformed-verdict: ${where} stated no reason`],
      malformedVerdict: true,
      classOverride: 'malformed-verdict: the gate blocked without naming a reason',
    }
  }
}

// Advantage principle: a PASS that carries competitive (non-constitutive) flags is routed
// to the advantage-evaluator, which decides proceed-under-flag (speculative — commit now,
// observe, revert later) or revert per flag. It NEVER turns a pass into a failure;
// constitutive failures never reach a pass and are out of its scope.
if (ruled && ruled.verdict === 'pass' && Array.isArray(ruled.flags) && ruled.flags.length) {
  const advantage = await settleAgent(
    `You are the advantage-evaluator. These competitive (non-constitutive) concerns surfaced at a PASSING gate. Apply the advantage principle: for each, decide whether to PROCEED under a flag (speculative execution — commit now, observe the outcome, revert later if it proves out badly) or REVERT now. You NEVER halt the pipeline for a non-invalidating finding; constitutive failures are out of your scope.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}
Competitive flags:
${ruled.flags.map((f, i) => `${i + 1}. ${f}`).join('\n')}`,
    {
      label: `advantage:${a.gate || a.phaseName || 'phase'}`,
      effort: 'medium',
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

// THE JUDGE DIED. Not "the work failed" — see failDispatch above. The deterministic checks
// all HELD to reach this line, so what is being reported is an environment failure over work
// that passed everything mechanical, and the caller must not spend a retry re-asking a judge
// that hit the same wall.
if (!ruled) {
  const why = `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the phase-gate-enforcer returned no verdict — it was skipped, or it died. The work was NOT judged and this is not a finding against it; every deterministic check for this gate held.`
  log(why)
  return { ...failDispatch(why, 'Gate'), deterministicChecks: checkResults }
}

// The deterministic results ride out on EVERY verdict, not just the ones this file
// short-circuits on. On the judgment path they reach the enforcer only as prose in
// `settledBlock` and never appeared in the returned verdict at all — so the caller
// holding a `loop` verdict could not tell a criterion that was MEASURED against the
// artifact from one that was argued about. That distinction is the whole basis on which
// an exhausted gate is ruled competitive or constitutive upstream: a mechanically-settled
// failure is not a matter of opinion and must never be waived as one.
return { ...ruled, deterministicChecks: checkResults }
