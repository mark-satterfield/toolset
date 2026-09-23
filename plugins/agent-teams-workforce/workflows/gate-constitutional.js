export const meta = {
  name: 'gate-constitutional',
  description:
    'Constitutional phase gate (PRD-to-Spec pipeline Gate 2, Spec-to-Deploy pipeline Gate 4). The phase-gate-enforcer judges with constitutive criteria as HARD stops — security/validity findings cannot be downgraded or flagged-past. Novel conflicts the enforcer cannot resolve are escalated to the constitutional-agent for a binding ruling, and that ruling is WRITTEN DOWN: every ruling is persisted as precedent keyed on the conflicting-constraint pair, and a conflict matching a stored precedent is settled from it without convening the appeals court again. On a self-contradictory packet NO exit path can return "loop" — the precedent path, the appeals-court path, and the no-ruling path all route through one conversion, because looping cannot repair a contradiction the same judge regenerates.',
  phases: [{ title: 'Gate (constitutional)', detail: 'hard-stop adjudication + appeals, over a persistent precedent store' }],
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

// ── A STATED LIMIT NEVER LIVES IN THE SCHEMA ─────────────────────────────────────
//
// Every list this script asks a dispatch for carries a limit, and that limit lives in the
// PROMPT and in a check HERE — never as a JSON-Schema maxItems/minItems/maxLength. A
// schema bound cannot trim an over-long answer: the runtime rejects the WHOLE result, the
// caller receives a bare null it cannot tell from a dead agent, and the run halts. One
// really did, on 61 items against a bound of 60, claiming files were unread that had been
// read. So the agent is told the limit up front, and the count is checked once the result
// is in hand: the overage is logged and recorded, EVERY item is kept, nothing is
// truncated, dropped or reordered, and no control flow changes. The limits still do their
// job — they keep an unbounded enumeration from running away, and they cost token and
// context budget when they are exceeded — they just no longer detonate.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const limitFindings = []
function checkLimit(where, what, value, max, min) {
  const n = Array.isArray(value) ? value.length : typeof value === 'string' ? value.length : null
  if (n === null) return value
  if (typeof max === 'number' && n > max) {
    limitFindings.push({ where, what, count: n, limit: max, bound: 'max' })
    log(`${where}: ${what} returned ${n} against a stated limit of ${max} — over by ${n - max}; every item is kept`)
  }
  if (typeof min === 'number' && n < min) {
    limitFindings.push({ where, what, count: n, limit: min, bound: 'min' })
    log(`${where}: ${what} returned ${n}, under the stated minimum of ${min} — carried through as returned`)
  }
  return value
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

// ── A self-contradictory adjudication is a JUDGE failure, not a phase failure ──
//
// When the packet under review rules one fact two opposite ways, "loop" is the wrong
// verdict by the gate's own definition: loop means a criterion is unmet AND the root
// cause is INSIDE this phase. Nothing about the WORK changed between rounds, so no
// retry of the phase can repair it, and re-running the same adjudicator regenerates
// the contradiction. Escalating upstream is equally wrong — the escalate targets are
// producing phases, and none of them caused the adjudicator to contradict itself.
//
// So it goes to a DIFFERENT AUTHORITY: the appeals court below, which consults recorded
// precedent first and writes its ruling down, so the next occurrence settles for free.
// Detected in script, not volunteered by the enforcer, because an enforcer that misses
// it costs the entire loop budget to discover.
//
// DETECTION, not just the exits. The three exit paths above are correctly guarded — no
// path can return "loop" on a contradiction. But a guard on the exits is worth nothing
// if the contradiction is never DETECTED, and this read was exact: `artifact` had to be
// an object with `packetIntegrity` at its own top level. It missed a packet handed over
// as a JSON string, and it missed one nested a level down — both of which arise from
// ordinary plumbing, not from anything exotic. A missed contradiction falls through to
// the normal verdict, which is the "loop" this whole mechanism exists to prevent.
//
// So the packet is now LOCATED before it is read: JSON strings are parsed, and the
// object is searched to a bounded depth for a `packetIntegrity` carrying contradictions.
// Bounded because an unbounded walk over an agent-supplied object is a denial-of-service
// waiting to happen; a cycle-safe seen-set for the same reason. Widening detection can
// only route MORE contradictions to the appeals court — never fewer, and never a
// coherent packet.

/** Parse a JSON-string packet; return objects unchanged; null for anything else. */
function asPacketObject(value) {
  if (value && typeof value === 'object') return value
  if (typeof value !== 'string') return null
  const text = value.trim()
  if (!text.startsWith('{') && !text.startsWith('[')) return null
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null // an unparseable string is not a packet; it is not evidence of anything
  }
}

/**
 * The contradictions in `artifact`, wherever the packet actually sits.
 * Searches to MAX_DEPTH, parsing JSON strings on the way, and stops at the first
 * packetIntegrity that carries a non-empty contradictions array.
 */
function findContradictions(artifact) {
  const MAX_DEPTH = 4
  const MAX_NODES = 500
  const seen = new Set()
  let visited = 0
  const queue = [[asPacketObject(artifact), 0]]
  while (queue.length) {
    const [node, depth] = queue.shift()
    if (!node || typeof node !== 'object' || depth > MAX_DEPTH || visited++ > MAX_NODES) continue
    if (seen.has(node)) continue
    seen.add(node)

    const pi = asPacketObject(node.packetIntegrity)
    if (pi && Array.isArray(pi.contradictions) && pi.contradictions.length) return pi.contradictions

    for (const value of Array.isArray(node) ? node : Object.values(node)) {
      const child = asPacketObject(value)
      if (child) queue.push([child, depth + 1])
    }
  }
  return []
}

function describePacketContradiction(artifact) {
  const contradictions = findContradictions(artifact)
  if (!contradictions.length) return null
  const detail = contradictions
    .map((cx) => {
      const c = (cx && typeof cx === 'object' && cx) || {}
      const pair = (Array.isArray(c.rulings) ? c.rulings : [])
        .map((r) => `real=${r && r.real}/${r && r.classification}/${r && r.severity}`)
        .join(' vs ')
      return `${c.findingId || '(unnamed finding)'}: ${pair || '(rulings not itemised)'}`
    })
    .join('; ')
  return (
    'THE ADJUDICATION CONTRADICTS ITSELF. The same finding carries opposite reality or ' +
    `classification rulings within one packet, with no new evidence between them: ${detail}. ` +
    'This is a defect in the ADJUDICATION, not in the work under review, so it cannot be ' +
    'repaired by re-running the phase and it did not originate in an upstream producing ' +
    'phase. Rule which reading stands. While this appeal is pending the MORE SEVERE ruling ' +
    'holds — a real constitutive finding outranks a not-real or competitive one about the ' +
    'same fact, because believing the softer round is how a genuine exposure gets waved through.'
  )
}
const packetConflict = describePacketContradiction(a.artifact)
if (packetConflict) {
  log(`Constitutional gate ${a.gate || '?'}: self-contradictory adjudication detected in script — routing to a constitutional ruling instead of looping the same judge`)
}

// "A contradiction never comes back as loop" was true of ONE of this gate's three exit
// paths — the one where the appeals court produced nothing. The other two returned an
// agent's verdict straight through, and both schemas permit the enum
// ['pass','loop','escalate']: a precedent line recording verdict:'loop', or an appeals
// ruling of 'loop', went back to the caller unaltered and spent the loop budget
// re-asking the question the same judge keeps answering inconsistently.
//
// So the rule is applied at the exit, once, and every path routes through it.
const LOOP_ON_CONTRADICTION_NOTE =
  'A self-contradictory adjudication cannot be repaired by re-running the phase — nothing about ' +
  'the WORK changed between the contradictory rounds — so this exits as an escalation rather ' +
  'than spending the loop budget on a contradiction the same judge regenerates.'
const noLoopOnContradiction = (v) => (packetConflict && v === 'loop' ? 'escalate' : v)
const withContradictionNote = (verdictIn, feedback) =>
  packetConflict && verdictIn === 'loop' ? `${feedback || ''}\n\n${LOOP_ON_CONTRADICTION_NOTE}` : feedback

// One judgment per criterion supplied, which is the honest limit; 60 when the caller
// supplied none to count. Raised from the flat 40 this used to be, and stated to the
// enforcer rather than bound in its schema — a gate that supplies 41 criteria should get
// 41 judgments back, not a destroyed verdict and a loop spent on a phase that passed.
const CRITERIA_JUDGMENT_MAX = criteria.length || 60

phase('Gate (constitutional)')

const verdict = await settleAgent(
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
Return exactly one entry in \`criteria\` per criterion listed above, in the same order — at most ${CRITERIA_JUDGMENT_MAX} entries, and nothing past that will be read. Keep each \`evidence\` under 40 words and \`feedback\` under 200. Judgments, not essays — a loop's whole value is the precision of the feedback, never its length.

If you encounter a NOVEL conflict between constitutive objectives that you cannot resolve from the criteria alone, set needsConstitutionalRuling=true and describe the conflict.`,
  {
    label: `gate-const:${a.gate || a.phaseName || 'phase'}`,
    effort: 'high',
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
          // One entry per criterion the caller supplied, and nothing else: the enforcer
          // judges the stated criteria, it does not invent more. That expectation is
          // stated in the prompt and counted below — never bound here, where an extra
          // entry would destroy the verdict along with it.
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

// ── THE `dispatchFailed` CONTRACT THIS GATE OWES ITS CALLER ──────────────────────
//
// A judge that DIED did not find the work wanting — it never ruled. This file built
// `dispatchFailures` and defined `dispatchDeaths` above and then called neither, so a dead
// enforcer returned null and every caller reads a null verdict as `ok:false, "gate N
// returned no verdict"` and ends the phase — discarding work that is complete and durable
// because the read-only judge hit an account limit, and filing it as a failure of the phase
// rather than of the environment. A death is reported AS a death so the caller can tell "the
// work is bad" from "nobody looked", and so no retry is spent on the same wall.
if (!verdict) {
  const deaths = dispatchDeaths('Gate (constitutional)')
  const why =
    `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the phase-gate-enforcer returned no verdict — it was skipped, or it died. ` +
    'The work was NOT judged and this is not a finding against it.'
  log(why)
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: why,
    escalateTo: (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
  }
}

// An observation, never a gate. The enforcer is told to return exactly one entry per
// criterion supplied; more than that means it judged something nobody asked about, which
// is worth seeing in the journal and is not a reason to throw the verdict away.
const judgedCriteria = Array.isArray(verdict.criteria) ? verdict.criteria : []
checkLimit(`Gate ${a.gate || '?'}`, 'criterion judgments', judgedCriteria, CRITERIA_JUDGMENT_MAX)
// Recorded on the verdict the caller receives, as well as logged. It rides along with the
// verdict and changes none of it: no path reads it, and no path branches on it.
if (limitFindings.length) verdict.limitFindings = limitFindings

// ── Precedent store ─────────────────────────────────────────────────────────────
// The constitutional-agent is told its ruling "becomes reusable precedent", and its
// schema returns a `precedent` field — and nothing wrote that field anywhere, and
// nothing read it on a later run. So every ruling died with the run that produced
// it and the same conflict was re-adjudicated from nothing the next time it arose.
// Precedent CR-001 was re-argued from scratch this way.
//
// A ruling is now written to a durable store, and the store is consulted BEFORE the
// appeals court is convened. Scripts have no filesystem access, so both ends go
// through an agent. The store sits beside the run ledger, under the path that
// already exists and is already gitignored.
const PRECEDENT_STORE = '.claude/workflow-runs/constitutional-precedents.jsonl'

// A contradiction the script found is not the enforcer's to decline. Setting the flag
// here — rather than waiting for the enforcer to volunteer it — is what makes the
// escalation deterministic.
if (packetConflict && verdict) {
  verdict.needsConstitutionalRuling = true
  verdict.conflict = [packetConflict, verdict.conflict].filter(Boolean).join('\n\n')
}

// Appeals court: only on a novel unresolved constitutive conflict, and only when no
// precedent already settles it.
if (verdict && verdict.needsConstitutionalRuling) {
  const conflict = verdict.conflict || '(unspecified)'

  // Look first. A precedent that answers this conflict IS the ruling — re-arguing a
  // settled question is exactly what precedent exists to prevent, and it costs a
  // constitutional-agent call every time the same tension recurs.
  const found = await settleAgent(
    `Search the constitutional precedent store for a ruling that already settles the conflict below.

Store: ${PRECEDENT_STORE} (JSON Lines; each line is one ruling with keys: key, gate, phaseName, conflict, verdict, rationale, precedent). If the file does not exist, that is not an error — it means no precedent has been recorded yet; return matched=false.

Conflict to settle:
${conflict}

A stored ruling MATCHES only when it is about the SAME PAIR OF CONFLICTING CONSTRAINTS as this one — not merely the same gate, the same phase, or a similar-sounding subject. Two conflicts about the same subject that pull in different directions are DIFFERENT conflicts. When in doubt, return matched=false: convening the appeals court needlessly costs one agent call, whereas applying the wrong precedent silently imposes a binding ruling nobody made about this question.

When you match, return the stored ruling's verdict, rationale and precedent VERBATIM. Do not re-reason it, do not improve it, and do not soften it.`,
    {
      label: `precedent:lookup:${a.gate || 'gate'}`,
      effort: 'low',
      phase: 'Gate (constitutional)',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['matched'],
        properties: {
          matched: { type: 'boolean' },
          key: { type: 'string' },
          verdict: { type: 'string', enum: ['pass', 'loop', 'escalate'] },
          rationale: { type: 'string' },
          precedent: { type: 'string' },
          escalateTo: { type: 'string' },
          reason: { type: 'string' },
        },
      },
    }
  )

  if (found && found.matched === true && found.verdict) {
    log(`Constitutional gate ${a.gate}: conflict SETTLED BY PRECEDENT ${found.key || '(unkeyed)'} — appeals court not convened`)
    // A stored precedent is applied VERBATIM in substance — but a recorded 'loop' is not
    // a substantive ruling on a contradiction, it is the one verdict this gate has
    // already established cannot answer one. It is converted here, and the conversion is
    // stated in the feedback rather than performed silently.
    return {
      verdict: noLoopOnContradiction(found.verdict),
      criteria: verdict.criteria,
      feedback: withContradictionNote(
        found.verdict,
        found.rationale || found.precedent || 'settled by recorded precedent'
      ),
      escalateTo:
        found.escalateTo || verdict.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
      ruledByConstitutionalAgent: true,
      ruledFromPrecedent: true,
      precedentKey: found.key || null,
      precedent: found.precedent,
      packetContradiction: !!packetConflict,
    }
  }

  log(
    `Constitutional gate ${a.gate}: novel conflict — no precedent on file` +
      `${found && found.reason ? ` (${found.reason})` : ''} — escalating to constitutional-agent`
  )
  const ruling = await settleAgent(
    `A constitutional gate hit a novel conflict between constitutive objectives that the enforcer could not resolve. Rule on it by consulting the system's founding objectives. Your ruling is binding and becomes reusable precedent.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}
Conflict: ${verdict.conflict || '(unspecified)'}
Enforcer feedback: ${verdict.feedback || ''}`,
    {
      label: `constitutional:${a.gate}`,
      effort: 'high',
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
    // Record it. A ruling that is not written down is not precedent — it is an
    // opinion that happened once. Persisting is best-effort: a store that cannot be
    // written must not overturn a ruling that was properly made, so a failure here
    // is logged and the ruling still stands for this run.
    const written = await settleAgent(
      `Append one ruling to the constitutional precedent store, then confirm what you wrote.

Store: ${PRECEDENT_STORE} (JSON Lines — one compact JSON object per line, no surrounding array, no pretty-printing). Create the file with the Write tool if it does not exist — it makes any missing parent directories itself, so do NOT run mkdir or any other shell command (an unmatched command blocks on an approval prompt no one is there to answer). APPEND ONLY: never rewrite, reorder, deduplicate or remove existing lines — a superseded ruling is part of the record.

Write exactly this object as the new final line:
${JSON.stringify({
  key: null,
  gate: a.gate || null,
  phaseName: a.phaseName || null,
  conflict,
  verdict: ruling.verdict,
  rationale: ruling.rationale,
  precedent: ruling.precedent || null,
})}

Set \`key\` yourself before writing, to a short stable identifier for THE PAIR OF CONFLICTING CONSTRAINTS this ruling settles — not for this run, this gate, or this phase, because the whole point is that a different run hitting the same pair finds this line. Use the form CR-NNN, continuing the highest CR number already in the file (CR-001 if the file is new or has none).`,
      {
        label: `precedent:persist:${a.gate || 'gate'}`,
        effort: 'low',
        phase: 'Gate (constitutional)',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['written'],
          properties: {
            written: { type: 'boolean' },
            key: { type: 'string' },
            path: { type: 'string' },
            error: { type: 'string' },
          },
        },
      }
    )
    if (written && written.written === true) {
      log(`Constitutional gate ${a.gate}: ruling recorded as precedent ${written.key || '(unkeyed)'} in ${written.path || PRECEDENT_STORE}`)
    } else {
      log(
        `Constitutional gate ${a.gate}: ruling made but NOT recorded as precedent` +
          `${written && written.error ? ` — ${written.error}` : ''}. The ruling stands for this run; the next run will re-adjudicate.`
      )
    }
    return {
      verdict: noLoopOnContradiction(ruling.verdict),
      criteria: verdict.criteria,
      feedback: withContradictionNote(ruling.verdict, ruling.rationale),
      escalateTo:
        ruling.escalateTo || verdict.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
      ruledByConstitutionalAgent: true,
      ruledFromPrecedent: false,
      precedentKey: (written && written.key) || null,
      precedentRecorded: !!(written && written.written === true),
      precedent: ruling.precedent,
      packetContradiction: !!packetConflict,
    }
  }
}

// ── A DECLARED CONSTITUTIONAL CONFLICT NEVER EXITS AS A PASS ─────────────────────
//
// This is the worst failure shape the system can produce, and it was reachable. The enforcer
// returns `pass` WITH `needsConstitutionalRuling: true` — a real combination: no criterion is
// itemised as unmet, but the judge has declared that two constitutive constraints conflict
// and it cannot settle which binds. If the precedent lookup found nothing and the
// constitutional-agent dispatch then returned null, control fell past the appeals block, past
// the contradiction guard below (which only fires on `loop`), to `return verdict` — a clean
// PASS on a security or validity conflict that NOBODY RULED ON.
//
// A flag that says "this needs a ruling" and no ruling is not a pass. The conflict is
// unresolved, and unresolved at a CONSTITUTIONAL gate means the work is not established as
// valid — so it escalates, naming the conflict, whatever the enforcer's own verdict was.
if (verdict && verdict.needsConstitutionalRuling && !verdict.ruledByConstitutionalAgent) {
  const conflict = verdict.conflict || '(unspecified)'
  const why =
    `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): a constitutive conflict was DECLARED and no ruling was obtained — ` +
    'the precedent store settled nothing and the constitutional-agent produced no ruling (it was skipped, or it died). ' +
    `The conflict stands unresolved: ${conflict}. ` +
    'An unresolved constitutive conflict is never a pass: this gate defines whether the work is valid at all, and passing ' +
    'here would wave through exactly the security or validity question that was escalated because nobody could settle it.'
  log(why)
  return {
    ...verdict,
    verdict: 'escalate',
    feedback: why,
    escalateTo: verdict.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    unresolvedConstitutionalConflict: conflict,
    ruledByConstitutionalAgent: false,
    ...(dispatchDeaths('Gate (constitutional)').length
      ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Gate (constitutional)') }
      : {}),
    packetContradiction: !!packetConflict,
  }
}

// The appeals court produced nothing. A contradiction must still never come back as
// "loop": that would spend the loop budget re-asking the question the same agent keeps
// answering inconsistently, which is the exact failure this detection exists to stop.
if (packetConflict && verdict && verdict.verdict === 'loop') {
  return {
    ...verdict,
    verdict: noLoopOnContradiction(verdict.verdict),
    escalateTo: verdict.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    feedback:
      `${verdict.feedback || ''}\n\nThe adjudication for this gate contradicts itself and no constitutional ruling was obtained. ` +
      LOOP_ON_CONTRADICTION_NOTE,
    packetContradiction: true,
  }
}

return verdict
