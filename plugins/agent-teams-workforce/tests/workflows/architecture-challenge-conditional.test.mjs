// The challenge wave is CONDITIONAL (Mark's ruling: "Challenge shouldn't run 100%
// of the time"). A settled-scope Epic got the full challenge wave after four
// analysts had already converged on recommendations — a full adversarial pass spent
// stressing a decision nobody disputed. The wave now runs only when the decision is
// actually contested: an analyst lens reports a live conflict, triage classified
// the question as risking a SAD-decision reversal or as high-stakes/constitutive,
// or no triage verdict exists to skip on (fail open). The trigger is computed by
// the SCRIPT from data already in the run — no agent decides whether to challenge,
// so segregation of duties is untouched — and a skip is RECORDED on the result,
// never silent.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const architecture = path.resolve(HERE, '..', '..', 'workflows', 'architecture.js')

const goodDecision = {
  admissible: true, ruling: 'r', chosenApproach: 'o', imposedConstraints: [],
  resolvedChallenges: [], surfaces: [], blockingRules: [], ruleChallenges: [],
}
const proposal = (contested, contestedReason) => ({
  lens: 'x',
  options: [{ name: 'o', approach: 'a', pros: [], cons: [] }],
  recommendation: 'o',
  contested,
  ...(contestedReason ? { contestedReason } : {}),
})
const benignTriage = {
  settled: false, rationale: 'open', relevantDecisions: [],
  dimensions: ['integration', 'security'], highStakes: false, reversalRisk: false,
}

function impl({ triage, contested = false, decision = goodDecision }) {
  return (call) => {
    const l = String(call.label)
    if (l === 'triage:classify') return triage
    if (l === 'proposals:frame') return { subDecisions: [], constraints: [], dispatch: 'd' }
    if (l.startsWith('proposals:analysis-advisors')) return { contextMap: { contexts: [], relationships: [] }, failureModes: [] }
    if (l.startsWith('proposals:')) return proposal(contested, contested ? 'two live options' : undefined)
    if (l === 'challenge:all-lenses') return { challenges: [], unstatedRisks: [], boundaryViolations: [], scaleBreakpoints: [], readinessGaps: [] }
    if (l.startsWith('decide:ruling')) return decision
    if (l === 'author:decision-artifacts') return { fitnessFunctions: [], diagrams: [] }
    if (l === 'sad:maintain') return { updatedSections: [], changedFiles: [], summary: 's' }
    if (l === 'sad:conformance') return { verdict: 'pass', findings: [] }
    return null
  }
}

async function run(opts, args = {}) {
  const { result, calls } = await runWorkflowScript(architecture, {
    args: { decision: { id: 'AD-1', title: 'q', context: 'c' }, ...args },
    agentImpl: impl(opts),
    workflowImpl: () => null,
  })
  const labels = calls.filter((c) => c.kind === 'agent').map((c) => String(c.label))
  return { result, calls, labels, ranWave: labels.some((l) => l.startsWith('challenge:')) }
}

test('converged analysts + benign triage SKIP the challenge wave and route straight to the decider', async () => {
  const { result, ranWave, labels } = await run({ triage: benignTriage })
  assert.equal(ranWave, false, 'nobody disputed the decision, so no adversarial pass should be paid for')
  assert.ok(labels.some((l) => l.startsWith('decide:ruling')), 'the decider still rules — skipping the wave never skips the ruling')
  assert.equal(result.ok, true)
})

test('the skip is RECORDED on the result, not silent', async () => {
  const { result } = await run({ triage: benignTriage })
  assert.ok(result.challengeWave, 'the run must carry the challenge-wave decision')
  assert.equal(result.challengeWave.ran, false)
  assert.match(result.challengeWave.reason, /converged/, 'the trace must show the decision, not silence')
})

test('a skipped wave is declared to the decider as a skip, never as a clean bill', async () => {
  const { calls } = await run({ triage: benignTriage })
  const decide = calls.find((c) => String(c.label).startsWith('decide:ruling'))
  assert.match(decide.prompt, /recorded skip, not a clean bill/,
    'an empty challenge set must not read as "the challengers found nothing" when no challenger ran')
})

test('an analyst reporting a live conflict triggers the wave', async () => {
  const { ranWave, result } = await run({ triage: benignTriage, contested: true })
  assert.equal(ranWave, true, 'material conflict among the analysts is exactly what the wave exists for')
  assert.match(result.challengeWave.reason, /live conflict/)
})

test('triage-classified SAD-reversal risk triggers the wave', async () => {
  const { ranWave } = await run({ triage: { ...benignTriage, reversalRisk: true } })
  assert.equal(ranWave, true, 'a ruling that could contradict a recorded SAD decision must be stressed first')
})

test('triage-classified high-stakes/constitutive questions trigger the wave', async () => {
  const { ranWave } = await run({ triage: { ...benignTriage, highStakes: true } })
  assert.equal(ranWave, true)
})

test('no triage verdict FAILS OPEN to running the wave', async () => {
  // A dead triage, or a caller-forced panel, leaves nothing to skip on. Skipping the
  // adversarial pass on missing evidence would be the quiet version of the defect
  // the panel-scaling tests guard against.
  const dead = await run({ triage: null })
  assert.equal(dead.ranWave, true, 'a triage failure must never be indistinguishable from "nothing to challenge"')

  const forced = await run({ triage: benignTriage }, { dimensions: ['integration'] })
  assert.equal(forced.ranWave, true, 'caller-forced dimensions skip triage, so there is no verdict to skip the wave on')

  const full = await run({ triage: benignTriage }, { forceFullPanel: true })
  assert.equal(full.ranWave, true, 'forceFullPanel means the full panel, wave included')
})

test('a re-proposal round runs the wave regardless of the round-1 trigger', async () => {
  // An inadmissible verdict IS a live conflict — the decider just eliminated every
  // option — so the fresh option set always gets stressed.
  let round = 0
  const { calls } = await runWorkflowScript(architecture, {
    args: { decision: { id: 'AD-1', title: 'q', context: 'c' } },
    agentImpl: (call) => {
      const l = String(call.label)
      if (l === 'triage:classify') return benignTriage
      if (l === 'proposals:frame') return { subDecisions: [], constraints: [], dispatch: 'd' }
      if (l.startsWith('proposals:analysis-advisors')) return { contextMap: { contexts: [], relationships: [] }, failureModes: [] }
      if (l.startsWith('proposals:')) return proposal(false)
      if (l === 'challenge:all-lenses') return { challenges: [], unstatedRisks: [], boundaryViolations: [], scaleBreakpoints: [], readinessGaps: [] }
      if (l.startsWith('decide:ruling')) {
        round += 1
        return round === 1
          ? { ...goodDecision, admissible: false, chosenApproach: '', blockingRules: [{ rule: 'house rule', source: 'SAD', whyBlocking: 'w', classification: 'convention' }] }
          : goodDecision
      }
      if (l === 'author:decision-artifacts') return { fitnessFunctions: [], diagrams: [] }
      if (l === 'sad:maintain') return { updatedSections: [], changedFiles: [], summary: 's' }
      if (l === 'sad:conformance') return { verdict: 'pass', findings: [] }
      return null
    },
    workflowImpl: () => null,
  })
  const waveRuns = calls.filter((c) => String(c.label).startsWith('challenge:')).length
  assert.ok(waveRuns >= 1, 'the re-proposed option set must be stressed even though round 1 converged')
})

// ── Judicious tie-break: ambiguity challenges by default ──────────────────────
// Mark's clarification: the requirement is a JUDICIOUS trigger, not a bias against
// challenging. Skipping requires AFFIRMATIVE evidence of convergence and low
// stakes; any signal that is merely absent — a lens that did not state contested,
// a triage that did not state a flag, a dispatched analyst that returned nothing —
// is ambiguity, and ambiguity runs the wave.

test('a lens that did not state contested either way is ambiguity — the wave runs', async () => {
  const { result, calls } = await runWorkflowScript(architecture, {
    args: { decision: { id: 'AD-1', title: 'q', context: 'c' } },
    agentImpl: (call) => {
      const l = String(call.label)
      if (l === 'triage:classify') return benignTriage
      if (l === 'proposals:frame') return { subDecisions: [], constraints: [], dispatch: 'd' }
      // One lens omits `contested` entirely — silence, not consensus.
      if (l === 'proposals:integration/decomposition') {
        return { lens: 'integration', options: [{ name: 'o', approach: 'a', pros: [], cons: [] }], recommendation: 'o' }
      }
      if (l.startsWith('proposals:')) return proposal(false)
      if (l === 'challenge:all-lenses') return { challenges: [], unstatedRisks: [], boundaryViolations: [], scaleBreakpoints: [], readinessGaps: [] }
      if (l.startsWith('decide:ruling')) return goodDecision
      if (l === 'author:decision-artifacts') return { fitnessFunctions: [], diagrams: [] }
      if (l === 'sad:maintain') return { updatedSections: [], changedFiles: [], summary: 's' }
      if (l === 'sad:conformance') return { verdict: 'pass', findings: [] }
      return null
    },
    workflowImpl: () => null,
  })
  assert.ok(calls.some((c) => String(c.label).startsWith('challenge:')), 'an unstated flag is not affirmative convergence')
  assert.match(result.challengeWave.reason, /ambiguous/, 'the journal must show ambiguity was why the wave ran')
})

test('a dispatched lens that returned nothing is ambiguity — the wave runs', async () => {
  const { result, calls } = await runWorkflowScript(architecture, {
    args: { decision: { id: 'AD-1', title: 'q', context: 'c' } },
    agentImpl: (call) => {
      const l = String(call.label)
      if (l === 'triage:classify') return benignTriage
      if (l === 'proposals:frame') return { subDecisions: [], constraints: [], dispatch: 'd' }
      if (l === 'proposals:security') return null // this analyst died; its view is unknown
      if (l.startsWith('proposals:')) return proposal(false)
      if (l === 'challenge:all-lenses') return { challenges: [], unstatedRisks: [], boundaryViolations: [], scaleBreakpoints: [], readinessGaps: [] }
      if (l.startsWith('decide:ruling')) return goodDecision
      if (l === 'author:decision-artifacts') return { fitnessFunctions: [], diagrams: [] }
      if (l === 'sad:maintain') return { updatedSections: [], changedFiles: [], summary: 's' }
      if (l === 'sad:conformance') return { verdict: 'pass', findings: [] }
      return null
    },
    workflowImpl: () => null,
  })
  assert.ok(calls.some((c) => String(c.label).startsWith('challenge:')), 'a dead analyst must widen scrutiny, not narrow it')
  assert.match(result.challengeWave.reason, /returned nothing/)
})

test('a triage that did not state its flags either way is ambiguity — the wave runs', async () => {
  const { ranWave, result } = await run({
    triage: { settled: false, rationale: 'open', relevantDecisions: [], dimensions: ['integration', 'security'] },
  })
  assert.equal(ranWave, true, 'an unstated reversalRisk/highStakes is not an affirmed low-stakes verdict')
  assert.match(result.challengeWave.reason, /either way/)
})

test('the journal line names the judgment both ways — "challenge ran:" / "challenge skipped:"', async () => {
  const skipped = await run({ triage: benignTriage })
  assert.match(skipped.result.challengeWave.reason, /^challenge skipped: /)
  assert.match(skipped.result.challengeWave.reason, /affirmed/, 'a skip must stand on affirmative evidence, and say so')
  const ran = await run({ triage: benignTriage, contested: true })
  assert.match(ran.result.challengeWave.reason, /^challenge ran: /)
})

test('the trigger is computed by the script — no agent is spent deciding whether to challenge', async () => {
  const { labels } = await run({ triage: benignTriage })
  assert.ok(
    !labels.some((l) => /trigger|should-challenge|convergence/i.test(l)),
    'the challenge decision must come from data already in the run, never from a new dispatch',
  )
})
