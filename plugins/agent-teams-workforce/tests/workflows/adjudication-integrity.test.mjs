// ssbd-36fn — the adjudicator contradicted itself and the gate looped anyway.
//
// In one live run the adversarial-critique-adjudicator ruled ONE fact — a live AWS
// account identifier surviving in a committable test file — constitutive/real=true in one
// round and competitive/real=false in a later round, with NO new evidence. The final
// packet carried two findings describing that same fact with opposite reality rulings and
// asserted constitutiveOpen:0 while its own contents contradicted it. The gate correctly
// refused the packet, and then burned all three loops re-asking a question the same agent
// kept answering inconsistently.
//
// Three things were missing and all three are mechanical:
//   1. Findings had no stable identity — a ruling's only id was its model-authored title,
//      and attackers re-run from scratch each round, so one fact came back re-worded.
//   2. constitutiveOpen was a model-authored integer nothing ever checked against the
//      rulings list it summarises, though the invariant is always computable.
//   3. The adjudicator was never shown its own prior rulings. It was not reversing a
//      ruling — it had never been shown one.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const ADV = path.join(WF, 'adversarial.js')
const GATE_C = path.join(WF, 'gate-constitutional.js')

const REPRO = 'grep 123456789012 tests/test_stack.py'
const CONTRACT = { repoPath: '/wt', bead: { id: 'ssbd-36fn', title: 'x' }, surfaces: ['auth'] }

/** Run adversarial with one attacker finding and a scripted adjudication. */
function runAdv({ adjudication, priorRulings, findings } = {}) {
  const reported = findings || [{ title: 'live AWS account id in a committable test', severity: 'high', reproduction: REPRO }]
  return runWorkflowScript(ADV, {
    args: { contract: CONTRACT, green: { changedFiles: ['a.py'] }, priorRulings },
    agentImpl: (call) => {
      if (call.label === 'adversarial:adjudicate') return adjudication
      // Only one lane reports the finding, so exactly one findingId exists.
      return call.label === 'attack:data-exposure-scanner' ? { findings: reported } : { findings: [] }
    },
  })
}

test('a finding gets a script-derived id — the model cannot rename its way out of a prior ruling', async () => {
  const { result: a } = await runAdv({ adjudication: { rulings: [], constitutiveOpen: 0 } })
  const { result: b } = await runAdv({
    adjudication: { rulings: [], constitutiveOpen: 0 },
    findings: [{ title: 'COMPLETELY DIFFERENT WORDING FOR THE SAME THING', severity: 'low', reproduction: REPRO }],
  })
  assert.ok(a.findings[0].findingId, 'every finding must carry an id')
  assert.equal(a.findings[0].findingId, b.findings[0].findingId,
    'identity comes from the lane + the reproduction, not from the title — re-wording one fact must not mint a second finding')
  assert.match(a.findings[0].findingId, /^data-exposure-scanner#/, 'the lane that found it is part of its identity')
})

test('constitutiveOpen is COMPUTED from the rulings, and the claim is preserved for the record', async () => {
  const { result } = await runAdv({
    adjudication: {
      rulings: [{ findingId: 'x', title: 't', severity: 'critical', classification: 'constitutive', real: true }],
      constitutiveOpen: 0, // the packet asserting 0 while its own contents say 1
    },
  })
  assert.equal(result.adjudication.constitutiveOpen, 1, 'the computed value stands')
  assert.equal(result.adjudication.constitutiveOpenClaimed, 0, 'the model\'s number is kept, not silently erased')
  assert.equal(result.packetIntegrity.countMismatch, true)
})

test('two opposite rulings for ONE finding are detected, and the MORE SEVERE one stands', async () => {
  const id = `data-exposure-scanner#${'grep 123456789012 tests/test_stack.py'.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`
  const { result } = await runAdv({
    adjudication: {
      rulings: [
        { findingId: id, title: 'constitutive reading', severity: 'critical', classification: 'constitutive', real: true },
        { findingId: id, title: 'competitive reading', severity: 'low', classification: 'competitive', real: false },
      ],
      constitutiveOpen: 0,
    },
  })
  assert.equal(result.selfContradictory, true, 'the packet contradicts itself and must say so')
  assert.equal(result.packetIntegrity.contradictions.length, 1)
  assert.equal(result.adjudication.rulings.length, 1, 'one finding yields one ruling')
  assert.equal(result.adjudication.rulings[0].real, true, 'believing the softer round is how a live credential gets waved through')
  assert.equal(result.adjudication.rulings[0].classification, 'constitutive')
  assert.equal(result.adjudication.constitutiveOpen, 1)
})

test('an UNCITED reversal of a prior ruling has no effect — the prior ruling is reinstated', async () => {
  const id = 'data-exposure-scanner#grep-123456789012-tests-test-stack-py'
  const prior = [{ findingId: id, title: 'live AWS account id', severity: 'critical', classification: 'constitutive', real: true }]
  const { result } = await runAdv({
    priorRulings: prior,
    adjudication: {
      rulings: [{ findingId: id, title: 'on reflection, not real', severity: 'low', classification: 'competitive', real: false }],
      constitutiveOpen: 0,
    },
  })
  assert.equal(result.packetIntegrity.unjustifiedReversals.length, 1, 'a reversal with no citation must be recorded')
  assert.equal(result.adjudication.rulings[0].real, true, 'the prior ruling stands')
  assert.equal(result.adjudication.rulings[0].classification, 'constitutive')
  assert.equal(result.adjudication.rulings[0].reinstated, true)
  assert.equal(result.adjudication.constitutiveOpen, 1, 'and the count follows the reinstated set')
})

test('a CITED reversal is honoured — adversarial re-runs against a changed tree, so a fixed finding really can flip', async () => {
  const id = 'data-exposure-scanner#grep-123456789012-tests-test-stack-py'
  const prior = [{ findingId: id, title: 'live AWS account id', severity: 'critical', classification: 'constitutive', real: true }]
  const { result } = await runAdv({
    priorRulings: prior,
    adjudication: {
      rulings: [{
        findingId: id, title: 'removed by the fix', severity: 'info', classification: 'competitive', real: false,
        reversalOf: { priorReal: true, priorClassification: 'constitutive', evidence: 'tests/test_stack.py changed in this round; re-ran `grep 123456789012 tests/` -> no matches' },
      }],
      constitutiveOpen: 0,
    },
  })
  assert.deepEqual(result.packetIntegrity.unjustifiedReversals, [], 'a cited reversal is legitimate — banning reversal would deadlock every repaired finding')
  assert.equal(result.adjudication.rulings[0].real, false)
  assert.equal(result.adjudication.constitutiveOpen, 0)
})

test('the adjudicator is SHOWN its prior rulings and the id is constrained to real findings', async () => {
  const prior = [{ findingId: 'data-exposure-scanner#x', title: 'p', severity: 'high', classification: 'constitutive', real: true }]
  const { calls } = await runAdv({ priorRulings: prior, adjudication: { rulings: [], constitutiveOpen: 0 } })
  const adj = calls.find((c) => c.label === 'adversarial:adjudicate')
  assert.match(adj.prompt, /PRIOR RULINGS/, 'a judge that is never shown its prior verdict cannot be accused of reversing it')
  assert.match(adj.prompt, /data-exposure-scanner#x/)
  const idSchema = adj.opts.schema.properties.rulings.items.properties.findingId
  assert.ok(Array.isArray(idSchema.enum) && idSchema.enum.length,
    'the id must be constrained to the ids the script derived, so a ruling cannot attach to a finding nobody reported')
  assert.ok(adj.opts.schema.properties.rulings.items.required.includes('findingId'))
})

// ── The gate: escalate to a different authority, never loop ───────────────────

function runGate(artifact, { enforcerVerdict, precedent, ruling } = {}) {
  return runWorkflowScript(GATE_C, {
    args: { gate: '4', phaseName: 'Adversarial Validation', criteria: ['No open constitutive findings'], artifact, escalateTargets: ['green', 'triage'] },
    agentImpl: (call) => {
      if (String(call.label).startsWith('gate-const:')) return enforcerVerdict
      if (String(call.label).startsWith('precedent:lookup')) return precedent || { matched: false }
      if (String(call.label).startsWith('constitutional:')) return ruling === undefined ? null : ruling
      return { written: true, key: 'CR-002' }
    },
  })
}

const CONTRADICTORY = {
  packetIntegrity: { contradictions: [{ findingId: 'lane#f', kind: 'intra-packet', rulings: [{ real: true, classification: 'constitutive', severity: 'critical' }, { real: false, classification: 'competitive', severity: 'low' }] }] },
}
const LOOP_VERDICT = { verdict: 'loop', criteria: [], feedback: 'the packet disagrees with itself', needsConstitutionalRuling: false }

test('a self-contradictory packet convenes the appeals court even when the enforcer says "loop"', async () => {
  const { calls } = await runGate(CONTRADICTORY, { enforcerVerdict: LOOP_VERDICT, ruling: { verdict: 'escalate', rationale: 'the constitutive reading governs' } })
  const labels = calls.map((c) => c.label)
  assert.ok(labels.some((l) => String(l).startsWith('precedent:lookup')),
    'nothing about the WORK changed between rounds, so a retry cannot repair it — it goes to a different authority')
  assert.ok(labels.some((l) => String(l).startsWith('constitutional:')))
})

test('the conflict handed to the appeals court names the contradiction in script, not on the enforcer\'s say-so', async () => {
  const { calls } = await runGate(CONTRADICTORY, { enforcerVerdict: LOOP_VERDICT, ruling: { verdict: 'escalate', rationale: 'r' } })
  const lookup = calls.find((c) => String(c.label).startsWith('precedent:lookup'))
  assert.match(lookup.prompt, /CONTRADICTS ITSELF/i)
  assert.match(lookup.prompt, /lane#f/, 'the specific finding must be named')
  assert.match(lookup.prompt, /MORE SEVERE ruling holds/, 'the tie-break while the appeal is pending must be stated')
})

test('a contradiction NEVER comes back as "loop", even when the appeals court produces nothing', async () => {
  const { result } = await runGate(CONTRADICTORY, { enforcerVerdict: LOOP_VERDICT, ruling: null })
  assert.notEqual(result.verdict, 'loop', 'looping spends the budget re-asking what the same judge keeps answering inconsistently')
  assert.equal(result.verdict, 'escalate')
  assert.equal(result.packetContradiction, true)
})

test('a packet with NO contradiction is left entirely alone', async () => {
  const clean = { packetIntegrity: { contradictions: [], unjustifiedReversals: [], constitutiveOpen: 0 } }
  const { result, calls } = await runGate(clean, { enforcerVerdict: { verdict: 'pass', criteria: [], feedback: '', needsConstitutionalRuling: false } })
  assert.equal(result.verdict, 'pass')
  assert.ok(!calls.some((c) => String(c.label).startsWith('precedent:lookup')), 'no appeal is convened for a coherent packet')
})

// ── ssbd-36fn residual: "loop" was blocked on ONE exit path of three ──────────
//
// The 6.0.5 claim that this gate "can never return loop" on a contradictory packet was
// true only of the path that was tested — the one where the appeals court produced
// nothing. Two others returned an agent's verdict straight through, and BOTH schemas
// permit the enum ['pass','loop','escalate']: the precedent path returned
// `found.verdict` unguarded, and the appeals-court path returned `ruling.verdict`
// unguarded. Either could hand back 'loop' and burn the whole loop budget re-asking a
// question the same judge keeps answering inconsistently.
//
// These model the uncooperative authority: a precedent line and a constitutional ruling
// that each say 'loop'.

test('the PRECEDENT path can never settle a contradiction as "loop"', async () => {
  const { result } = await runGate(CONTRADICTORY, {
    enforcerVerdict: LOOP_VERDICT,
    precedent: { matched: true, key: 'CR-007', verdict: 'loop', rationale: 'the stored line says loop', precedent: 'p' },
  })
  assert.equal(result.ruledFromPrecedent, true, 'the precedent was applied — this is that exit path')
  assert.notEqual(result.verdict, 'loop', 'a recorded ruling cannot re-authorise the one verdict a contradiction cannot answer')
  assert.equal(result.verdict, 'escalate')
  assert.ok(result.escalateTo, 'an escalation with nowhere to go is not an escalation')
  assert.match(result.feedback, /cannot be repaired by re-running the phase/, 'the conversion must be stated, not performed silently')
  assert.equal(result.packetContradiction, true)
})

test('the APPEALS-COURT path can never rule a contradiction as "loop"', async () => {
  const { result } = await runGate(CONTRADICTORY, {
    enforcerVerdict: LOOP_VERDICT,
    ruling: { verdict: 'loop', rationale: 'the constitutional agent said loop' },
  })
  assert.equal(result.ruledFromPrecedent, false, 'the appeals court ruled — this is that exit path')
  assert.notEqual(result.verdict, 'loop')
  assert.equal(result.verdict, 'escalate')
  assert.ok(result.escalateTo)
  assert.match(result.feedback, /the constitutional agent said loop/, 'the ruling\'s own rationale is preserved, not replaced')
  assert.match(result.feedback, /cannot be repaired by re-running the phase/)
})

test('every exit path agrees: NO verdict of "loop" survives a self-contradictory packet', async () => {
  // The three exits, driven together, so a future edit cannot re-open one of them.
  const paths = [
    { name: 'precedent', opts: { enforcerVerdict: LOOP_VERDICT, precedent: { matched: true, key: 'CR-009', verdict: 'loop', rationale: 'r' } } },
    { name: 'appeals-court', opts: { enforcerVerdict: LOOP_VERDICT, ruling: { verdict: 'loop', rationale: 'r' } } },
    { name: 'no-ruling', opts: { enforcerVerdict: LOOP_VERDICT, ruling: null } },
  ]
  for (const { name, opts } of paths) {
    const { result } = await runGate(CONTRADICTORY, opts)
    assert.equal(result.verdict, 'escalate', `${name} exit returned "${result.verdict}"`)
    assert.equal(result.packetContradiction, true, `${name} exit must record WHY it escalated`)
  }
})

test('a COHERENT packet still gets "loop" from either authority — the conversion is scoped to contradictions', async () => {
  const clean = { packetIntegrity: { contradictions: [], unjustifiedReversals: [], constitutiveOpen: 0 } }
  const needsRuling = { verdict: 'escalate', criteria: [], feedback: 'f', needsConstitutionalRuling: true, conflict: 'a novel tension' }
  const viaPrecedent = await runGate(clean, {
    enforcerVerdict: needsRuling,
    precedent: { matched: true, key: 'CR-011', verdict: 'loop', rationale: 'fixable inside the phase' },
  })
  assert.equal(viaPrecedent.result.verdict, 'loop', 'loop is a legitimate verdict when the phase really can repair it')
  const viaCourt = await runGate(clean, { enforcerVerdict: needsRuling, ruling: { verdict: 'loop', rationale: 'fixable inside the phase' } })
  assert.equal(viaCourt.result.verdict, 'loop')
})
