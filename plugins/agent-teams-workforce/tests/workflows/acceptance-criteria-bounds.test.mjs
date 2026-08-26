// ssbd-v7cg — acceptance-criteria expansion.
//
// A four-defect bug produced eighteen-plus criteria, several of them repo-wide greps
// ("no occurrence of redis:// anywhere") that are lint rules wearing an
// acceptance-criterion costume. The coverage reviewer then blocked on partial coverage of
// those generated criteria, and Gate 2a exhausted without one line of production code
// being written — because Red cannot make a repo-wide grep go red for the intended
// reason, ever.
//
// Nothing bounded N: the writer received a prose root-cause blob with no cap, no defect
// index, and no scope rule. Four defects arrived as one paragraph, so there was nothing
// countable to bound against. Making the defects countable is the enabling change; the
// cap is then a SCHEMA bound the runtime enforces, not a sentence the prompt requests.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const TRIAGE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows', 'bug-triage.js')

const FOUR_DEFECTS = [
  { id: 'D1', mechanism: 'the URL scheme is hardcoded', file: 'cache.py', line: 12 },
  { id: 'D2', mechanism: 'TLS is never negotiated', file: 'cache.py', line: 31 },
  { id: 'D3', mechanism: 'the timeout is unbounded', file: 'client.py', line: 9 },
  { id: 'D4', mechanism: 'errors are swallowed', file: 'client.py', line: 44 },
]

function runTriage({ defects = FOUR_DEFECTS, contract } = {}) {
  return runWorkflowScript(TRIAGE, {
    args: { bead: { id: 'ssbd-v7cg', title: 'cache misconfiguration', description: 'd', repoPath: '/wt' } },
    agentImpl: (call) => {
      if (call.label === 'triage:diagnosis') {
        return {
          reproduction: 'connect to the cache',
          rootCause: 'four separate mistakes in the cache client',
          defects,
          affectedFiles: ['cache.py', 'client.py'],
          blastRadius: 'one service',
          surfaces: [],
        }
      }
      if (call.label === 'triage:sizing') return { scope: 'fix', rationale: 'correctable in place' }
      if (call.label === 'triage:expected-behavior') return contract || { acceptanceCriteria: FOUR_DEFECTS.map((d) => ({ defectId: d.id, given: 'g', when: 'w', then: 't' })) }
      return null
    },
  })
}

test('the diagnosis must ENUMERATE the defects, not just describe them', async () => {
  const { calls } = await runTriage()
  const diag = calls.find((c) => c.label === 'triage:diagnosis')
  assert.ok(diag.opts.schema.required.includes('defects'), 'four defects as one paragraph leave nothing downstream can count')
  assert.equal(diag.opts.schema.properties.defects.minItems, 1)
  assert.match(diag.prompt, /ENUMERATED/)
})

test('the criteria count is bounded BY SCHEMA to the number of defects', async () => {
  const { calls } = await runTriage()
  const ac = calls.find((c) => c.label === 'triage:expected-behavior')
  const arr = ac.opts.schema.properties.acceptanceCriteria
  assert.equal(arr.minItems, 4, 'every defect needs at least one criterion')
  assert.equal(arr.maxItems, 8, 'a four-defect bug can produce between four and eight — eighteen is structurally impossible')
  assert.ok(arr.items.required.includes('defectId'), 'without an index, coverage is a judgment call rather than a join')
  assert.deepEqual(arr.items.properties.defectId.enum, ['D1', 'D2', 'D3', 'D4'],
    'a criterion cannot point at a defect the diagnosis never found')
})

test('the bound scales with the defects and never collapses to zero', async () => {
  const one = await runTriage({ defects: [{ id: 'D1', mechanism: 'm' }], contract: { acceptanceCriteria: [{ defectId: 'D1', given: 'g', when: 'w', then: 't' }] } })
  const arr1 = one.calls.find((c) => c.label === 'triage:expected-behavior').opts.schema.properties.acceptanceCriteria
  assert.equal(arr1.minItems, 1)
  assert.equal(arr1.maxItems, 2)

  // A diagnosis that enumerated nothing must still produce a contract, not an empty one.
  const none = await runTriage({ defects: [], contract: { acceptanceCriteria: [{ defectId: 'D1', given: 'g', when: 'w', then: 't' }] } })
  const arr0 = none.calls.find((c) => c.label === 'triage:expected-behavior').opts.schema.properties.acceptanceCriteria
  assert.equal(arr0.minItems, 1)
  assert.ok(arr0.maxItems >= 2)
  assert.equal(arr0.items.properties.defectId.enum, undefined, 'an empty enum would make every criterion unsatisfiable')
})

test('the writer is given the REDIRECT TEST for repo-wide invariants', async () => {
  const { calls } = await runTriage()
  const ac = calls.find((c) => c.label === 'triage:expected-behavior')
  assert.match(ac.prompt, /still be checkable with the change reverted/,
    'the mechanical test for "this is a lint rule, not an acceptance criterion"')
  assert.ok(ac.opts.schema.properties.lintRules, 'they must have somewhere else to go — they are real, just not testable as red')
})

test('lint rules ride on the contract and are NEVER acceptance criteria', async () => {
  const { result } = await runTriage({
    contract: {
      acceptanceCriteria: [{ defectId: 'D1', given: 'g', when: 'w', then: 't' }],
      lintRules: [{ pattern: 'redis://', rationale: 'every connection must be TLS', scope: 'repo' }],
    },
  })
  assert.equal(result.lintRules.length, 1)
  assert.equal(result.acceptanceCriteria.length, 1)
  assert.ok(
    !result.acceptanceCriteria.some((x) => JSON.stringify(x).includes('redis://')),
    'a repo-wide grep in the criteria is what exhausted Gate 2a — Red can never legitimately turn it red',
  )
})

test('the tail never sees the lint rules, so the coverage reviewer cannot block on them', async () => {
  // tdd-red reads contract.acceptanceCriteria and nothing else for its coverage review.
  const { readFileSync } = await import('node:fs')
  const red = readFileSync(path.join(path.dirname(TRIAGE), 'tdd-red.js'), 'utf8')
  assert.ok(!red.includes('lintRules'), 'routing them anywhere near the Red phase reinstates the exact blocking loop')
})

test('a defect with no criterion is reported, not silently dropped', async () => {
  const { result } = await runTriage({
    contract: { acceptanceCriteria: [{ defectId: 'D1', given: 'g', when: 'w', then: 't' }] },
  })
  assert.deepEqual(result.uncoveredDefects, ['D2', 'D3', 'D4'], 'coverage is an exact join now, so a gap is a fact rather than an opinion')
})

test('the defects survive onto the contract for everything downstream', async () => {
  const { result } = await runTriage()
  assert.equal(result.defects.length, 4)
  assert.equal(result.defects[0].id, 'D1')
})
