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
// allowed decision.
//
// THE DISPATCH IS GONE. `proposals:frame` no longer exists: its two inputs
// (`decisionHeader` and `activeDimensions`) are handed to the analysts raw in the very
// next dispatch, so the session paid a full session-start to reformat text its own
// readers also received unformatted, on the critical path of every contested
// architecture run. architecture.js writes the framing itself now.
//
// So the three prompt tests that pinned that dispatch are replaced by ONE test that the
// dispatch does not happen at all — which is the stronger form of the same guarantee: an
// agent that is never asked cannot form a view on gate status. The charter test stays,
// because the coordinator remains on the roster and the prohibition must survive
// wherever it is dispatched next.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SCRIPT = path.resolve(HERE, '..', '..', 'workflows', 'architecture.js')
const CHARTER = path.resolve(HERE, '..', '..', 'agents', 'architecture-decision-workflow-coordinator.md')

test('a contested decision dispatches NO coordinator session at all — the script frames the panel', async () => {
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

  assert.equal(
    calls.filter((x) => x.label === 'proposals:frame').length, 0,
    'the framing session is gone — it reformatted text the analysts receive raw in the next dispatch',
  )
  assert.ok(
    !calls.some((x) => x.opts && x.opts.agentType === 'agent-teams-workforce:architecture-decision-workflow-coordinator'),
    'the coordinator is not dispatched anywhere in this mini; an agent never asked cannot form a view on gate status',
  )
  const proposal = calls.find((x) => String(x.label || '').startsWith('proposals:'))
  assert.ok(proposal, 'the analysts still run — removing the router must not remove the panel')
  assert.match(
    proposal.prompt,
    /Panel framing \(set by the workflow, not by an agent\)/,
    'the framing the analysts receive must say plainly that no agent authored it',
  )
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
