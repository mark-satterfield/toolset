export const meta = {
  name: 'gate-constitutional',
  description:
    'Constitutional phase gate (PRD-to-Spec pipeline Gate 2, Spec-to-Deploy pipeline Gate 4). The phase-gate-enforcer judges with constitutive criteria as HARD stops — security/validity findings cannot be downgraded or flagged-past. Novel conflicts the enforcer cannot resolve are escalated to the constitutional-agent for a binding ruling, and that ruling is WRITTEN DOWN: every ruling is persisted as precedent keyed on the conflicting-constraint pair, and a conflict matching a stored precedent is settled from it without convening the appeals court again.',
  phases: [{ title: 'Gate (constitutional)', detail: 'hard-stop adjudication + appeals, over a persistent precedent store' }],
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
function describePacketContradiction(artifact) {
  const pi = artifact && artifact.packetIntegrity
  const contradictions = (pi && Array.isArray(pi.contradictions) && pi.contradictions) || []
  if (!contradictions.length) return null
  const detail = contradictions
    .map((cx) => {
      const pair = (cx.rulings || [])
        .map((r) => `real=${r.real}/${r.classification}/${r.severity}`)
        .join(' vs ')
      return `${cx.findingId}: ${pair}`
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
  const found = await agent(
    `Search the constitutional precedent store for a ruling that already settles the conflict below.

Store: ${PRECEDENT_STORE} (JSON Lines; each line is one ruling with keys: key, gate, phaseName, conflict, verdict, rationale, precedent). If the file does not exist, that is not an error — it means no precedent has been recorded yet; return matched=false.

Conflict to settle:
${conflict}

A stored ruling MATCHES only when it is about the SAME PAIR OF CONFLICTING CONSTRAINTS as this one — not merely the same gate, the same phase, or a similar-sounding subject. Two conflicts about the same subject that pull in different directions are DIFFERENT conflicts. When in doubt, return matched=false: convening the appeals court needlessly costs one agent call, whereas applying the wrong precedent silently imposes a binding ruling nobody made about this question.

When you match, return the stored ruling's verdict, rationale and precedent VERBATIM. Do not re-reason it, do not improve it, and do not soften it.`,
    {
      label: `precedent:lookup:${a.gate || 'gate'}`,
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
    return {
      verdict: found.verdict,
      criteria: verdict.criteria,
      feedback: found.rationale || found.precedent || 'settled by recorded precedent',
      escalateTo: found.escalateTo || verdict.escalateTo,
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
    // Record it. A ruling that is not written down is not precedent — it is an
    // opinion that happened once. Persisting is best-effort: a store that cannot be
    // written must not overturn a ruling that was properly made, so a failure here
    // is logged and the ruling still stands for this run.
    const written = await agent(
      `Append one ruling to the constitutional precedent store, then confirm what you wrote.

Store: ${PRECEDENT_STORE} (JSON Lines — one compact JSON object per line, no surrounding array, no pretty-printing). Create the file and any missing parent directories if they do not exist. APPEND ONLY: never rewrite, reorder, deduplicate or remove existing lines — a superseded ruling is part of the record.

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
      verdict: ruling.verdict,
      criteria: verdict.criteria,
      feedback: ruling.rationale,
      escalateTo: ruling.escalateTo || verdict.escalateTo,
      ruledByConstitutionalAgent: true,
      ruledFromPrecedent: false,
      precedentKey: (written && written.key) || null,
      precedentRecorded: !!(written && written.written === true),
      precedent: ruling.precedent,
      packetContradiction: !!packetConflict,
    }
  }
}

// The appeals court produced nothing. A contradiction must still never come back as
// "loop": that would spend the loop budget re-asking the question the same agent keeps
// answering inconsistently, which is the exact failure this detection exists to stop.
if (packetConflict && verdict && verdict.verdict === 'loop') {
  return {
    ...verdict,
    verdict: 'escalate',
    escalateTo: verdict.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    feedback:
      `${verdict.feedback || ''}\n\nThe adjudication for this gate contradicts itself and no constitutional ruling was obtained. ` +
      'Looping cannot repair a contradiction the same judge regenerates, so this exits rather than burning the loop budget.',
    packetContradiction: true,
  }
}

return verdict
