// The coordinator has no gate authority (ssbd-otq6).
//
// Observed in run wf_e1736f55-1fe: Gate G1 returned `pass` with all four criteria
// MET. The architecture-decision-workflow-coordinator was then dispatched to frame
// the decision for the analyst panel and instead returned a HOLD, refusing to route
// on the grounds that "Gate 1 has not passed". Its stated basis was the
// ambiguity-detector's BLOCKER gradings plus seven "major" findings — every one of
// which the phase-gate-enforcer had already adjudicated and overturned, the
// legacy-password-signup blocker by name across two separate runs. It said so
// plainly: "I am relying on the ambiguity-detector reported severities as accurate;
// I have not independently reviewed PRD text."
//
// Analysts PROPOSE severities. The enforcer ADJUDICATES them. A downstream agent
// reading analyst severities as gate status re-opens findings the gate has closed,
// which inverts the segregation of duties the pipeline exists to enforce.
//
// The charter was the licence: it listed "Validated PRD (Gate 1 passed)" as an input
// the coordinator must verify, and "whether required inputs are present" as an
// allowed decision. These tests pin both the dispatch prompt and the agent file.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SCRIPT = path.resolve(HERE, '..', '..', 'workflows', 'architecture.js')
const CHARTER = path.resolve(HERE, '..', '..', 'agents', 'architecture-decision-workflow-coordinator.md')

async function framePrompt() {
  const { calls } = await runWorkflowScript(SCRIPT, {
    args: { decision: { id: 'D1', title: 'a contested question', context: 'c' } },
    workflowImpl: () => ({ verdict: 'pass', criteria: [], flags: [] }),
    agentImpl: (call) => {
      if (call.label === 'triage:classify') {
        return { settled: false, rationale: 'r', relevantDecisions: [], dimensions: ['integration'] }
      }
      if (call.label === 'sad:conformance') return { verdict: 'pass', conformant: true, findings: [] }
      return {
        summary: 's', findings: [], options: [], ruling: 'accept', rationale: 'r', verdict: 'pass',
        conformant: true, admissible: true, chosenApproach: 'a', blockingRules: [], ruleChallenges: [],
        subDecisions: ['x'], constraints: [], dispatch: 'd',
      }
    },
  })
  const c = calls.find((x) => x.label === 'proposals:frame')
  assert.ok(c, 'the coordinator must be dispatched to frame a contested decision')
  return c.prompt
}

test('the dispatch tells the coordinator it has no gate authority', async () => {
  const p = await framePrompt()
  assert.match(p, /NO gate authority/, 'the prompt must deny gate authority outright')
  assert.match(
    p,
    /settled by the phase-gate-enforcer before you were dispatched/,
    'the coordinator must be told the gate already ruled, so there is nothing left for it to assess',
  )
})

test('the dispatch forbids treating analyst severities as gate status', async () => {
  const p = await framePrompt()
  assert.match(
    p,
    /PROPOSALS the enforcer has already adjudicated/,
    'analyst severities are proposals, not verdicts — this is the exact confusion that caused the HOLD',
  )
  assert.match(p, /not yours to re-open/)
})

test('the dispatch removes HOLD as an available move', async () => {
  const p = await framePrompt()
  assert.match(
    p,
    /no HOLD in your output schema because there is no HOLD in your authority/,
    'an agent with no legal way to express a refusal will jam one into prose — say plainly that it has none',
  )
  assert.match(p, /report a genuinely ABSENT input/, 'a missing artifact is still reportable; a disliked one is not')
})

test('the coordinator charter no longer grants gate-status authority', () => {
  const charter = readFileSync(CHARTER, 'utf8')

  assert.doesNotMatch(
    charter,
    /Validated PRD \(Gate 1 passed\)/,
    'listing gate status as an input the coordinator verifies is the licence it used to HOLD',
  )
  assert.match(charter, /You have no gate authority\. None\./, 'the prohibition must be a heading, not a buried clause')
  assert.match(
    charter,
    /forming any view whatsoever on whether a gate passed or failed/,
    'the Forbidden Decisions list must name gate-status opinions explicitly',
  )
  assert.match(
    charter,
    /presence only, never their quality, their findings, or their gate status/,
    'input verification must be scoped to existence, which is what "verify required inputs" was read too broadly',
  )
  assert.match(charter, /wf_e1736f55-1fe/, 'the charter should carry the incident so the rule is not mistaken for boilerplate')
})
