// The sad-maintainer must sweep every claim it changes (ssbd-w0l3 follow-on).
//
// Observed in run wf_8eaba4f0-500: the maintainer changed the idempotency store in
// one §8 concept and left five other statements of the same claim standing — a §2
// constraint, a §2 table line, a §4 strategy bullet, a §5 building-block paragraph
// and a §8 index row. The SAD then contradicted itself inside a single file, and the
// conformance reviewer rejected the feed over it. The deadlock ruling compounded the
// error by ordering "unresolved" disclosure markers, treating an already-decided
// question as an open one.
//
// Three further defects from the same run are pinned here because each is a class,
// not an incident: a bare proposal letter used for the adopted option (the same
// letter named an eliminated option, so an extractor resolved it to the wrong
// topology); provenance entries left asserting a superseded state; and unresolved
// markers standing in for a decision that was actually made.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SCRIPT = path.resolve(HERE, '..', '..', 'workflows', 'architecture.js')

/** Run to completion with a decider that admits, and capture the maintainer's prompt. */
async function maintainerPrompt() {
  const { calls } = await runWorkflowScript(SCRIPT, {
    args: { decision: { id: 'D1', title: 'pick a store', context: 'c' } },
    workflowImpl: () => ({ verdict: 'pass', criteria: [], flags: [] }),
    agentImpl: (call) => {
      if (call.label === 'sad:conformance') return { verdict: 'pass', conformant: true, findings: [] }
      return {
        summary: 's', findings: [], options: [], ruling: 'accept', rationale: 'r',
        verdict: 'pass', conformant: true, admissible: true, chosenApproach: 'a',
        blockingRules: [], ruleChallenges: [],
      }
    },
  })
  const c = calls.find((x) => x.label === 'sad:maintain')
  assert.ok(c, 'the sad-maintainer must be dispatched on an admissible ruling')
  return c.prompt
}

test('the maintainer is ordered to sweep the whole SAD for every claim it changes', async () => {
  const p = await maintainerPrompt()
  assert.match(p, /SWEEP EVERY CLAIM YOU CHANGE/, 'the sweep instruction must be present and unmissable')
  assert.match(p, /grep the WHOLE SAD tree/, 'the sweep must cover the whole tree, not the edited section')
  assert.match(
    p,
    /index\/summary rows, which are claims too/,
    'an index row asserting a stale value is the exact defect that rejected wf_8eaba4f0-500',
  )
  assert.match(p, /re-grep for the old value/, 'the maintainer must verify its own sweep, not just intend one')
})

test('a decided question may not be recorded as unresolved', async () => {
  const p = await maintainerPrompt()
  assert.match(p, /A DECIDED QUESTION IS NOT AN OPEN ONE/)
  assert.match(
    p,
    /If the SAD contradicts the ruling, the SAD is the defect: correct it/,
    'the SAD must never outrank the decision it exists to record',
  )
})

test('the adopted option may not be labelled with a bare proposal letter', async () => {
  const p = await maintainerPrompt()
  assert.match(p, /NEVER LABEL THE ADOPTED OPTION WITH A BARE PROPOSAL LETTER/)
  assert.match(
    p,
    /packet-local/,
    'the reason matters: the same letter names an eliminated option elsewhere, so an extractor resolves it wrongly',
  )
})

test('provenance must carry supersession, not only the prose body', async () => {
  const p = await maintainerPrompt()
  assert.match(p, /MARK WHAT THIS RULING SUPERSEDES IN PROVENANCE/)
  assert.match(
    p,
    /reading provenance alone must not come away with two rulings asserting opposite states/,
    'a body that reconciles while derived_from contradicts is still a contradiction to a machine reader',
  )
})
