// Standing rulings live in the pipeline's heads, not in a human watcher's.
//
// Unattended multi-day runs mean Mark's standing rulings must reach every
// judgment-bearing agent's brief: a reconciliation checker once found that a "live
// service" serves nobody, yet kept migration requirements his dev-data-is-disposable
// ruling invalidates — a watching human had to catch it. The composites resolve the
// project-local `.claude/standing-rulings.md` ONCE (one cheap read agent — scripts
// have no filesystem), cap it at 8KB, and thread the text to the minis, which
// prepend a delimited, outranking, cite-when-applied block to JUDGMENT prompts only.
// A missing file injects nothing — zero behavior change — and mechanical agents
// (bead-writer, ledger plumbing) never receive it.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, agentCalls, workflowCalls } from './helpers/run-workflow.mjs'
import { beadWriter, isWriterCall } from './helpers/bead-writer.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WF = path.resolve(HERE, '..', '..', 'workflows')

const MARKER = 'STANDING RULINGS FROM THE PROJECT OWNER'
const RULINGS = '## dev-env-no-preservation\nDev data is disposable. No migration or preservation requirement survives contact with this ruling.'

// ── Mini level: injected into judgment prompts, absent means unchanged ─────────

test('prd-validation: rulings present -> the analyst brief carries the delimited, outranking, cite-instruction block', async () => {
  const { calls } = await runWorkflowScript(path.join(WF, 'prd-validation.js'), {
    args: { prd: { id: 'P1', body: 'R1. thing' }, standingRulings: RULINGS },
    agentImpl: () => ({ ambiguities: [], completenessGaps: [], conflicts: [], constraints: [], boundaryFindings: [], clarifications: [], summary: 's' }),
  })
  const [analyst] = agentCalls(calls, 'validate:all-lenses')
  assert.ok(analyst.prompt.includes(MARKER), 'the rulings must reach the judgment brief')
  assert.ok(analyst.prompt.includes('dev-env-no-preservation'), 'the ruling text itself must be there, verbatim')
  assert.match(analyst.prompt, /outrank any document they contradict/, 'a ruling outranks a contradicting PRD/SAD/spec')
  assert.match(analyst.prompt, /CITE the ruling in your output/, 'applying a ruling must be citable in the trace')
  assert.ok(analyst.prompt.includes('END STANDING RULINGS'), 'the block is clearly delimited')
})

test('prd-validation: rulings absent -> the prompt is unchanged (zero behavior change)', async () => {
  const { calls } = await runWorkflowScript(path.join(WF, 'prd-validation.js'), {
    args: { prd: { id: 'P1', body: 'R1. thing' } },
    agentImpl: () => ({ ambiguities: [], completenessGaps: [], conflicts: [], constraints: [], boundaryFindings: [], clarifications: [], summary: 's' }),
  })
  const [analyst] = agentCalls(calls, 'validate:all-lenses')
  assert.ok(!analyst.prompt.includes(MARKER), 'no file, no injection — the brief reads exactly as before')
})

test('the injected content is capped so a bloated file cannot blow up every brief', async () => {
  const bloated = 'X'.repeat(20000)
  const { calls } = await runWorkflowScript(path.join(WF, 'prd-validation.js'), {
    args: { prd: { id: 'P1', body: 'R1. thing' }, standingRulings: bloated },
    agentImpl: () => ({ ambiguities: [], completenessGaps: [], conflicts: [], constraints: [], boundaryFindings: [], clarifications: [], summary: 's' }),
  })
  const [analyst] = agentCalls(calls, 'validate:all-lenses')
  const injected = analyst.prompt.match(/X+/)[0]
  assert.equal(injected.length, 8192, 'first 8KB only — the cap is the guard against a runaway file')
})

test('prd-reconciliation: the reality checker AND the delta writer both receive the rulings', async () => {
  // The delta writer decides what work REMAINS — exactly where the
  // dev-data-is-disposable failure lived — so it is judgment, not plumbing.
  const { calls } = await runWorkflowScript(path.join(WF, 'prd-reconciliation.js'), {
    args: {
      prd: { id: 'P1', title: 't', body: 'R1. migrate data', path: '/prd/p.md', repoPath: '/repo' },
      standingRulings: RULINGS,
    },
    agentImpl: (call) => {
      if (call.label === 'reconcile:reality-and-dependencies') {
        return {
          requirements: [{ id: 'R1', requirement: 'migrate data', status: 'absent', evidence: ['no match in services/'] }],
          deltaIsInfraOnly: false,
          unsettledTechnicalDecision: false,
          evidenceSummary: 's',
          dependencyChanges: { current: true, changeFindings: [], evidence: 'e' },
        }
      }
      if (call.label === 'delta:write') return { ok: true, path: '/prd/p.delta.md', body: 'delta' }
      return null
    },
  })
  const [checker] = agentCalls(calls, 'reconcile:reality-and-dependencies')
  const [writer] = agentCalls(calls, 'delta:write')
  assert.ok(checker.prompt.includes(MARKER), 'the reconciliation checker judges reality against the rulings')
  assert.ok(writer.prompt.includes(MARKER), 'the delta writer decides what remains and must see them too')
})

test('architecture: triage, analysts, advisors, and the decider get the rulings — the challenge wave and SAD plumbing do not', async () => {
  const { calls } = await runWorkflowScript(path.join(WF, 'architecture.js'), {
    args: { decision: { id: 'AD-1', title: 'q', context: 'c' }, standingRulings: RULINGS },
    agentImpl: (call) => {
      const l = String(call.label)
      if (l === 'triage:classify') {
        // contested + high stakes so the challenge wave RUNS and can be asserted on
        return { settled: false, rationale: 'open', relevantDecisions: [], dimensions: ['integration', 'bounded-context'], highStakes: true, reversalRisk: false }
      }
      if (l === 'proposals:frame') return { subDecisions: [], constraints: [], dispatch: 'd' }
      if (l.startsWith('proposals:analysis-advisors')) return { contextMap: { contexts: [], relationships: [] } }
      if (l.startsWith('proposals:')) return { lens: 'x', options: [{ name: 'o', approach: 'a', pros: [], cons: [] }], recommendation: 'o', contested: false }
      if (l === 'challenge:all-lenses') return { challenges: [], unstatedRisks: [], boundaryViolations: [], scaleBreakpoints: [], readinessGaps: [] }
      if (l.startsWith('decide:ruling')) return { admissible: true, ruling: 'r', chosenApproach: 'o', imposedConstraints: [], resolvedChallenges: [], surfaces: [], blockingRules: [], ruleChallenges: [] }
      if (l === 'author:decision-artifacts') return { fitnessFunctions: [], diagrams: [] }
      if (l === 'sad:maintain') return { updatedSections: [], changedFiles: [], summary: 's' }
      if (l === 'sad:conformance') return { verdict: 'pass', findings: [] }
      return null
    },
    workflowImpl: () => null,
  })
  const has = (label) => agentCalls(calls, label)[0].prompt.includes(MARKER)
  assert.ok(has('triage:classify'), 'triage classifies against the rulings')
  assert.ok(has('proposals:integration/decomposition'), 'the lens analysts design under the rulings')
  assert.ok(has('proposals:analysis-advisors'), 'the advisors analyze under the rulings')
  assert.ok(has('decide:ruling'), 'the decider rules under the rulings')
  assert.ok(!has('sad:maintain'), 'the SAD maintainer consolidates a ruling already made — not in the injection set')
})

test('task-decomposition: the maker gets the rulings', async () => {
  const { calls } = await runWorkflowScript(path.join(WF, 'task-decomposition.js'), {
    args: { spec: { id: 'S1', title: 't', repoPath: '/r' }, story: { key: 'S1' }, standingRulings: RULINGS },
    agentImpl: (call) => {
      if (call.label === 'decompose:sequence-and-score') {
        return { tasks: [{ key: 'T1', title: 'a', description: 'b', type: 'task', acceptanceCriteria: ['c'] }], rationale: 'r', edges: [], buildOrder: ['T1'], acyclic: true, scores: [{ key: 'T1', userBusinessValue: 1, timeCriticality: 1, riskReductionOpportunityEnablement: 1, jobSize: 1, wsjf: 3, rationale: 'r' }] }
      }
      if (String(call.label).startsWith('review:scores-and-format')) {
        return { scoringReview: { accepted: true, feedback: '', issues: [] }, beadsValidation: { valid: true, violations: [] } }
      }
      return null
    },
  })
  assert.ok(agentCalls(calls, 'decompose:sequence-and-score')[0].prompt.includes(MARKER))
})

test('bug-triage: diagnosis, sizing, and the expected-behavior contract all get the rulings', async () => {
  const { calls } = await runWorkflowScript(path.join(WF, 'bug-triage.js'), {
    args: { bead: { id: 'B1', title: 'b', description: 'd', repoPath: '/repo' }, standingRulings: RULINGS },
    agentImpl: (call) => {
      const l = String(call.label)
      if (l === 'triage:diagnosis') {
        return { reproduction: 'r', rootCause: 'rc', defects: [{ id: 'D1', mechanism: 'm', file: 'f.py', line: 1 }], affectedFiles: ['f.py'], blastRadius: 'small', surfaces: [], repoPath: '/repo', repoResolution: 'supplied' }
      }
      if (l === 'triage:sizing') return { scope: 'fix', rationale: 'small' }
      if (l === 'triage:expected-behavior') return { acceptanceCriteria: [{ defectId: 'D1', given: 'g', when: 'w', then: 't' }] }
      return null
    },
  })
  for (const label of ['triage:diagnosis', 'triage:sizing', 'triage:expected-behavior']) {
    assert.ok(agentCalls(calls, label)[0].prompt.includes(MARKER), `${label} judges and must see the rulings`)
  }
})

// ── Composite level: resolved once, threaded to judgment, withheld from plumbing ─

/** Every gate passes; every mini answers minimally (mirrors repo-span-ruling's fixture). */
function compositeWorkflows() {
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) return { verdict: 'pass', criteria: [], flags: [] }
    if (name.endsWith('prd-reconciliation')) {
      return {
        ok: true, verdict: 'partial',
        requirements: [{ id: 'R1', requirement: 'r', status: 'absent', evidence: ['f.py:1'] }],
        deltaCount: 1, deltaPrdPath: '/prd/p.delta.md', deltaPrd: { path: '/prd/p.delta.md', body: 'b' },
        sizeVerdict: 'story', infraOnly: false, sizing: { deltaRepos: ['/repos/alpha'] },
      }
    }
    if (name.endsWith('prd-validation')) return { ok: true, validatedPrd: { id: 'P1', title: 'P', body: 'b' }, findings: [] }
    if (name.endsWith('architecture')) return { ok: true, decision: { id: 'AD-1' } }
    if (name.endsWith('repo-scoping')) {
      return { ok: true, repos: ['/repos/alpha'], placements: [], newRepos: [], requiredHumanActions: [], reclassified: [], blocked: [], spanVerified: true }
    }
    if (name.endsWith('trd-authoring')) return { ok: true, trd: { id: 'TRD-1', summary: 'sum' } }
    if (name.endsWith('spec-authoring')) {
      return { ok: true, story: { key: 'S1', type: 'story', title: 'S', description: 'd', repoPath: '/repos/alpha', parentEpicKey: 'E1' }, outOfRepoFindings: [] }
    }
    if (name.endsWith('task-decomposition')) {
      return { ok: true, beadSet: [{ key: 'T1', type: 'task', parentStoryId: 'S1', title: 't', description: 'd', acceptanceCriteria: ['a'] }] }
    }
    return null
  }
}

async function runComposite({ found, content = RULINGS }) {
  const writer = beadWriter()
  return runWorkflowScript(path.join(WF, 'prd-to-spec.js'), {
    args: { prd: { id: 'P1', title: 'P', body: 'R1. thing' }, repoPath: '/repos/alpha' },
    workflowImpl: compositeWorkflows(),
    agentImpl: (call) => {
      // prd-to-spec reads the checkpoint and the rulings in ONE dispatch — two small
      // files in the same tree, and a fresh agent session costs its session start, not
      // its work. bug-fix still reads the rulings on its own label.
      if (call.label === 'resolve:run-inputs') {
        return {
          files: [
            { key: 'checkpoint', found: false, content: '' },
            { key: 'rulings', found, content: found ? content : '' },
          ],
        }
      }
      if (call.label === 'resolve:standing-rulings') return { found, content: found ? content : '' }
      if (call.label === 'triage:architecture-needed') return { needed: true, reason: 'open', decisions: [], dimensions: ['integration'] }
      return writer(call)
    },
  })
}

test('file present: resolved once, threaded to every judgment mini, and injected into the composite\'s own judgment dispatch', async () => {
  const { result, calls } = await runComposite({ found: true })
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  assert.equal(agentCalls(calls, 'resolve:run-inputs').length, 1, 'the file is read once per run, not once per agent')
  assert.equal(agentCalls(calls, 'resolve:standing-rulings').length, 0, 'and not in a session of its own — it rides with the checkpoint read')
  for (const mini of ['prd-reconciliation', 'prd-validation', 'architecture', 'repo-scoping', 'trd-authoring', 'task-decomposition']) {
    const [wf] = workflowCalls(calls, `agent-teams-workforce:${mini}`)
    assert.ok(wf, `${mini} must have been dispatched`)
    assert.equal(wf.payload.standingRulings, RULINGS, `${mini} must receive the rulings text via args`)
  }
  const [archTriage] = agentCalls(calls, 'triage:architecture-needed')
  assert.ok(archTriage.prompt.includes(MARKER), 'the composite\'s own judgment dispatch (architecture triage) carries the block')
})

test('mechanical agents never receive the rulings — the tokens are wasted on agents that judge nothing', async () => {
  const { calls } = await runComposite({ found: true })
  const writerCalls = calls.filter(isWriterCall)
  assert.ok(writerCalls.length > 0, 'the run must actually have written beads')
  for (const w of writerCalls) {
    assert.ok(!String(w.prompt).includes(MARKER), `${w.label} is plumbing — it types what the script decided and judges nothing`)
  }
})

test('file absent: nothing is injected anywhere and no mini receives rulings', async () => {
  const { result, calls } = await runComposite({ found: false })
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  for (const c of calls.filter((x) => x.kind === 'agent')) {
    assert.ok(!String(c.prompt).includes(MARKER), `${c.label} must be unchanged when no file exists`)
  }
  for (const mini of ['prd-reconciliation', 'prd-validation', 'trd-authoring']) {
    const [wf] = workflowCalls(calls, `agent-teams-workforce:${mini}`)
    assert.ok(!wf.payload.standingRulings, `${mini} receives no rulings when the file is absent`)
  }
})
