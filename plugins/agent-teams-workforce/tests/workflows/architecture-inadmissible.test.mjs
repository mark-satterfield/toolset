// architecture mini — the "no admissible option" path (ssbd-w0l3).
//
// Before this fix the decider could only CHOOSE among proposed options: its prompt
// forbade authoring one and its schema required a chosenApproach. When every option
// failed a MUST, the only legal move was to jam a rejection into prose, which the
// script then wrote into the SAD as normative text — and still reported ok:true,
// because ok was computed from whether the SAD edit was well-formed rather than from
// whether anything had been decided. That is how run wf_4c1f34f4-da9 turned a failed
// architecture run into a permanent blocker on 13 identity PRDs.
//
// These tests pin the four behaviours that make that impossible to repeat.

import test from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const SCRIPT = resolve(HERE, '../../workflows/architecture.js')

const ARGS = { decision: { id: 'D1', title: 'how does the browser reach the resolution endpoint', context: 'c' } }

const CONVENTION_BLOCKER = {
  rule: 'only services on the curated fronted set may sit behind the application host',
  source: 'arc42 §8 Edge Routing line 84',
  whyBlocking: 'eliminates every proposed carrier',
  classification: 'convention',
}

/**
 * Run the mini with a decider that reports inadmissible for the first `failRounds`
 * decide calls and then (optionally) admits.
 */
async function runWithDecider({ failRounds, admitAfter = false, ruleChallenges = [] }) {
  let decideCalls = 0
  return runWorkflowScript(SCRIPT, {
    args: ARGS,
    workflowImpl: () => ({ verdict: 'pass', criteria: [], flags: [] }),
    agentImpl: (call) => {
      if (call.label === 'triage:classify') {
        return { settled: false, rationale: 'r', relevantDecisions: [], dimensions: ['integration', 'security'] }
      }
      if (String(call.label || '').startsWith('decide:ruling')) {
        decideCalls += 1
        if (decideCalls <= failRounds) {
          return {
            admissible: false,
            ruling: 'nothing admissible',
            imposedConstraints: [],
            resolvedChallenges: [],
            surfaces: [],
            blockingRules: [CONVENTION_BLOCKER],
            ruleChallenges,
          }
        }
        if (!admitAfter) return null
        return {
          admissible: true,
          ruling: 'CloudFront to API Gateway to Lambda',
          chosenApproach: 'front door',
          imposedConstraints: [],
          resolvedChallenges: [],
          surfaces: [],
          blockingRules: [],
          ruleChallenges,
        }
      }
      if (call.label === 'sad:conformance') return { verdict: 'pass', conformant: true, findings: [] }
      return {
        summary: 's', findings: [], options: [], ruling: 'accept', rationale: 'r',
        verdict: 'pass', conformant: true, admissible: true, chosenApproach: 'a',
        blockingRules: [], ruleChallenges: [],
      }
    },
  })
}

const labels = (calls) => calls.filter((c) => c.kind === 'agent').map((c) => c.label)
const agentTypes = (calls) => calls.filter((c) => c.kind === 'agent').map((c) => (c.opts && c.opts.agentType) || null)

test('an inadmissible verdict NEVER writes the SAD', async () => {
  const { result, calls } = await runWithDecider({ failRounds: 99 })
  assert.equal(
    agentTypes(calls).includes('agent-teams-workforce:sad-maintainer'),
    false,
    'a non-decision must not reach the sad-maintainer — recording "nothing was admissible" as normative architecture is how a failed run becomes a permanent blocker',
  )
  assert.equal(result.admissible, false)
  assert.equal(result.stage, 'decide')
})

test('a run that decided nothing reports ok:false', async () => {
  const { result } = await runWithDecider({ failRounds: 99 })
  assert.equal(result.ok, false, 'ok must require a DECISION, not merely a well-formed SAD edit')
})

test('an inadmissible verdict sends the blocking rules back to the panel for a fresh option set', async () => {
  const { calls } = await runWithDecider({ failRounds: 1, admitAfter: true })
  const reProposals = labels(calls).filter((l) => String(l || '').startsWith('proposals:') && String(l).includes('-r2'))
  assert.ok(reProposals.length > 0, 'the panel must be re-dispatched — a single bad option set must not end the run')

  const reCall = calls.find((c) => String(c.label || '').includes('-r2'))
  assert.match(reCall.prompt, /ruled INADMISSIBLE/, 'the re-proposal round must carry why the last set failed')
  assert.match(reCall.prompt, /Design the best solution to the problem FIRST/, 'the round must ask for the best design, not a rule-compliant one')
  assert.match(reCall.prompt, /Existing deployed infrastructure is NOT a constraint/, 'existing infra must not bound the redesign')
})

test('the re-proposal round tells the panel a house convention is not binding', async () => {
  const { calls } = await runWithDecider({ failRounds: 1, admitAfter: true })
  const reCall = calls.find((c) => String(c.label || '').includes('-r2'))
  assert.match(reCall.prompt, /\[convention\]/, 'the blocking rule must carry its classification')
  assert.match(
    reCall.prompt,
    /house rule, not an external constraint/,
    'a convention must be presented as challengeable — it must never be the reason delivery halts',
  )
})

test('the re-proposal loop is bounded and the verdict then stands', async () => {
  const { result, calls } = await runWithDecider({ failRounds: 99 })
  const decideCount = labels(calls).filter((l) => String(l || '').startsWith('decide:ruling')).length
  assert.equal(decideCount, 2, 'default is two decide rounds — the loop must terminate rather than spin')
  assert.equal(result.decideRounds, 2)
})

test('rule challenges reach the caller instead of being absorbed into the SAD', async () => {
  const challenge = {
    rule: 'curated fronted set',
    source: 'arc42 §8 Edge Routing line 84',
    recommendedChange: 'demote from MUST to guidance',
    rationale: 'a house convention blocked an otherwise Well-Architected design',
  }
  const { result } = await runWithDecider({ failRounds: 99, ruleChallenges: [challenge] })
  assert.deepEqual(result.ruleChallenges, [challenge], 'a "this rule is wrong" finding must surface to the human owner')
})

test('the decider is chartered to design around a convention rather than halt', async () => {
  const { calls } = await runWithDecider({ failRounds: 99 })
  const decide = calls.find((c) => c.label === 'decide:ruling')
  assert.match(decide.prompt, /BEST PRACTICE WINS/, 'best practice must outrank a self-authored house MUST')
  assert.match(decide.prompt, /A convention MUST NOT be the reason delivery halts/)
  assert.match(decide.prompt, /do NOT manufacture a ruling to avoid it/, 'the escape hatch must not become a pressure to fake a decision')
})
