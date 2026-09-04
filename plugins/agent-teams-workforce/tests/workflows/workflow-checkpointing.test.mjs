// Composites are RESUMABLE ACROSS DISPATCHES via phase-level checkpointing.
//
// "If we reach a spend limit, then execution should pause, but when the spend limit
// resets, it should pick back up." The supervisor re-dispatches a killed composite,
// but the re-dispatch used to restart from minute zero — ssbd-qxeu died at 103
// minutes, ~10 from finishing architecture, and every minute was lost. These tests
// pin the five behaviors that make resume real: each completed phase's RESULT is
// SAVED to a durable per-bead file; a resumed run SKIPS completed phases and REUSES
// their results; a checkpoint whose PRD content hash or plugin version differs is
// INVALIDATED (fresh start, journalled); and a completed run DELETES its checkpoint
// while a failed one keeps it.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, agentCalls, workflowCalls } from './helpers/run-workflow.mjs'
import { beadWriter } from './helpers/bead-writer.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WF = path.resolve(HERE, '..', '..', 'workflows')

/** Same FNV-1a the composites use — reimplemented so a test can mint a matching hash. */
const fnv = (v) => {
  let h = 0x811c9dc5
  const t = String(v == null ? '' : v)
  for (let i = 0; i < t.length; i++) {
    h = ((h ^ t.charCodeAt(i)) * 0x01000193) >>> 0
  }
  return h.toString(16)
}

const PLUGIN_VERSION = JSON.parse(
  fs.readFileSync(path.resolve(HERE, '..', '..', '.claude-plugin', 'plugin.json'), 'utf8')
).version

/** Pull the checkpoint JSON out of a save dispatch's prompt. */
function savedPayload(call) {
  const marker = 'JSON payload:\n'
  const i = String(call.prompt || '').indexOf(marker)
  if (i < 0) return null
  try {
    return JSON.parse(String(call.prompt).slice(i + marker.length))
  } catch {
    return null
  }
}

// ── prd-to-spec fixture (mirrors standing-rulings' minimal happy path) ─────────

function compositeWorkflows({ failSpec = false, scopingRepos = ['/repos/alpha'], newRepos = [] } = {}) {
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) return { verdict: 'pass', criteria: [], flags: [] }
    if (name.endsWith('prd-reconciliation')) {
      return {
        ok: true, verdict: 'partial',
        requirements: [{ id: 'R1', requirement: 'r', status: 'absent', evidence: ['f.py:1'] }],
        deltaCount: 1, deltaPrdPath: '/prd/p.delta.md', deltaPrd: { path: '/prd/p.delta.md', body: 'delta-body' },
        sizeVerdict: 'story', infraOnly: false, sizing: { deltaRepos: scopingRepos },
      }
    }
    if (name.endsWith('prd-validation')) return { ok: true, validatedPrd: { id: 'P1', title: 'P', body: 'delta-body' }, findings: [] }
    if (name.endsWith('architecture')) return { ok: true, decision: { id: 'AD-1' } }
    if (name.endsWith('repo-scoping')) {
      return { ok: true, repos: scopingRepos, placements: [], newRepos, requiredHumanActions: newRepos.length ? ['create it via the polyrepo-steward'] : [], reclassified: [], blocked: [], spanVerified: true }
    }
    if (name.endsWith('trd-authoring')) return { ok: true, trd: { id: 'TRD-1', summary: 'sum' } }
    if (name.endsWith('spec-authoring')) {
      if (failSpec) return { ok: false, reason: 'spec gate failed' }
      return { ok: true, story: { key: 'S1', type: 'story', title: 'S', description: 'd', repoPath: scopingRepos[0], parentEpicKey: 'E1' }, outOfRepoFindings: [] }
    }
    if (name.endsWith('task-decomposition')) {
      return { ok: true, beadSet: [{ key: 'T1', type: 'task', parentStoryId: 'S1', title: 't', description: 'd', acceptanceCriteria: ['a'] }] }
    }
    return null
  }
}

const PRD = { id: 'P1', title: 'P', body: 'R1. thing' }

async function runP2S({ checkpointFile = null, workflowOpts = {}, args = {} } = {}) {
  const writer = beadWriter()
  const saves = []
  const result = await runWorkflowScript(path.join(WF, 'prd-to-spec.js'), {
    args: { prd: PRD, repoPath: '/repos/alpha', ...args },
    workflowImpl: compositeWorkflows(workflowOpts),
    agentImpl: (call) => {
      const l = String(call.label)
      // prd-to-spec reads the checkpoint together with the standing rulings, and RETIRES
      // it inside the journal write. Two files read in one session and two written in
      // one session — a fresh agent session costs its session start, not its work.
      if (l === 'resolve:run-inputs') {
        return {
          files: [
            { key: 'checkpoint', found: Boolean(checkpointFile), content: checkpointFile || '' },
            { key: 'rulings', found: false, content: '' },
          ],
        }
      }
      if (l.startsWith('checkpoint:save:')) {
        saves.push(call)
        return { ok: true }
      }
      if (l === 'triage:architecture-needed') return { needed: false, reason: 'no decision', settledBy: 'test' }
      if (l === 'ledger:persist') return { written: true, path: '/journal', retired: true }
      return writer(call)
    },
  })
  return { ...result, saves }
}

test('a fresh run SAVES each completed phase result to the per-bead checkpoint file', async () => {
  const { result, saves } = await runP2S()
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  const keys = saves.map((c) => String(c.label).replace('checkpoint:save:', ''))
  for (const expected of ['reconciliation', 'validation', 'architecture', 'repo-scoping', 'trd-authoring', 'spec:/repos/alpha', 'decomposition:S1']) {
    assert.ok(keys.includes(expected), `phase '${expected}' must be checkpointed as it completes; saved: ${keys.join(', ')}`)
  }
  for (const c of saves) {
    assert.match(c.prompt, /\/repos\/alpha\/\.claude\/workflow-runs\/checkpoints\/P1-prd-to-spec\.json/, 'the file lives in the repo the run operates on, keyed by bead+composite')
  }
  const last = savedPayload(saves[saves.length - 1])
  assert.equal(last.pluginVersion, PLUGIN_VERSION, 'the staleness guard keys on the plugin version')
  assert.equal(last.inputHash, fnv(PRD.body), 'the staleness guard keys on the PRD content hash')
  assert.ok(last.phases.reconciliation, 'the saved payload is the actual RESULT the next phase consumes, not a marker')
  assert.equal(last.phases.reconciliation.deltaPrd.body, 'delta-body')
})

/** True when the run's journal write also carried the checkpoint retirement. */
function retiredInJournal(calls) {
  const [journal] = agentCalls(calls, 'ledger:persist')
  return Boolean(journal && /RETIRE the workflow checkpoint at this exact path/.test(String(journal.prompt)))
}

test('a completed successful run RETIRES its checkpoint — inside the journal write, not in a session of its own', async () => {
  const { calls } = await runP2S()
  assert.equal(agentCalls(calls, 'checkpoint:delete').length, 0, 'a second agent session to write one small file is a session wasted')
  assert.ok(retiredInJournal(calls), 'resuming finished work would replay it, so the retirement must still happen')
  const [journal] = agentCalls(calls, 'ledger:persist')
  assert.match(
    String(journal.prompt),
    /\/repos\/alpha\/\.claude\/workflow-runs\/checkpoints\/P1-prd-to-spec\.json/,
    'the retirement names the run\'s own checkpoint path',
  )
  // The ledger payload is LAST in the prompt so it stays parseable to the end — a reader
  // that slices from the marker must not find prose after the JSON.
  const payload = String(journal.prompt).slice(String(journal.prompt).indexOf('JSON payload:\n') + 'JSON payload:\n'.length)
  JSON.parse(payload)
})

test('a FAILED run keeps its checkpoint so the next dispatch resumes', async () => {
  const { result, calls, saves } = await runP2S({ workflowOpts: { failSpec: true } })
  assert.equal(result.ok, false)
  assert.ok(saves.length >= 4, 'the phases that completed were still checkpointed')
  assert.equal(retiredInJournal(calls), false, 'a kept checkpoint is the whole point of pausing')
})

test('the create-repos exit keeps the checkpoint — its purpose is a re-run after a human acts', async () => {
  const { result, calls } = await runP2S({
    workflowOpts: { scopingRepos: [], newRepos: [{ proposedName: 'SkillSpoke-newthing', purpose: 'p', workUnitIds: ['W1'], whyNoExistingRepoFits: 'none fits' }] },
  })
  assert.equal(result.ok, true)
  assert.equal(result.action, 'create-repos')
  assert.equal(retiredInJournal(calls), false)
})

test('a resumed run SKIPS completed phases, REUSES their results, and journals the resume', async () => {
  // First run produces the real checkpoint file content; the second run is a fresh
  // dispatch (different session) that finds it on disk.
  const first = await runP2S()
  const file = JSON.stringify(savedPayload(first.saves[first.saves.length - 1]))

  const second = await runP2S({ checkpointFile: file })
  assert.equal(second.result.ok, true, `resumed composite failed at ${second.result.stage}: ${second.result.headline || ''}`)
  for (const mini of ['prd-reconciliation', 'prd-validation', 'architecture', 'repo-scoping', 'trd-authoring', 'spec-authoring', 'task-decomposition']) {
    assert.equal(
      workflowCalls(second.calls, `agent-teams-workforce:${mini}`).length,
      0,
      `${mini} completed in the first dispatch and must never re-run — that is the lost 103 minutes`,
    )
  }
  const journal = agentCalls(second.calls, 'ledger:persist')[0]
  assert.match(journal.prompt, /"event":"resumed"/, 'the trace must show the resume decision, not silence')
  assert.match(journal.prompt, /"resumedAfter":/)
  // The reused results flow into the product: the emitted hierarchy still carries the
  // checkpointed story and tasks.
  assert.equal(second.result.hierarchy.stories[0].key, 'S1')
  assert.equal(second.result.hierarchy.tasks.length, 1)
})

test('a checkpoint written against DIFFERENT PRD content is invalidated — fresh start, journalled', async () => {
  const first = await runP2S()
  const payload = savedPayload(first.saves[first.saves.length - 1])
  payload.inputHash = fnv('a completely different PRD body')
  const second = await runP2S({ checkpointFile: JSON.stringify(payload) })
  assert.equal(second.result.ok, true)
  assert.equal(workflowCalls(second.calls, 'agent-teams-workforce:prd-reconciliation').length, 1, 'stale results must not be reused')
  const journal = agentCalls(second.calls, 'ledger:persist')[0]
  assert.match(journal.prompt, /"event":"invalidated"/)
  assert.match(journal.prompt, /PRD content changed/)
})

test('a checkpoint written by a DIFFERENT plugin version is invalidated', async () => {
  const first = await runP2S()
  const payload = savedPayload(first.saves[first.saves.length - 1])
  payload.pluginVersion = '0.0.1'
  const second = await runP2S({ checkpointFile: JSON.stringify(payload) })
  assert.equal(workflowCalls(second.calls, 'agent-teams-workforce:prd-reconciliation').length, 1)
  const journal = agentCalls(second.calls, 'ledger:persist')[0]
  assert.match(journal.prompt, /"event":"invalidated"/)
  assert.match(journal.prompt, /plugin version/)
})

// ── bug-fix ───────────────────────────────────────────────────────────────────

test('bug-fix resumes triage, red+green, and refactor from a checkpoint', async () => {
  const BEAD = { id: 'ssbd-1xcs', title: 's', description: 'd', repoPath: '/repos/chassis' }
  const file = JSON.stringify({
    composite: 'bug-fix',
    subject: BEAD.id,
    pluginVersion: PLUGIN_VERSION,
    inputHash: fnv(`${BEAD.title}|${BEAD.description}`),
    phases: {
      triage: { repoPath: null, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [], bead: null },
      green: {
        redArtifact: { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', greenReachable: true },
        green: { ok: true, artifact: { ok: true, greenConfirmed: true, evidence: 'pass' } },
      },
      refactor: { ok: true, artifact: { ok: true } },
    },
  })
  const { result, calls } = await runWorkflowScript(path.join(WF, 'bug-fix.js'), {
    args: { bead: BEAD },
    agentImpl: (call) => {
      const l = String(call.label)
      if (l === 'checkpoint:load') return { found: true, content: file }
      if (l.startsWith('checkpoint:save:') || l === 'checkpoint:delete') return { ok: true }
      return { written: true, ok: true }
    },
    workflowImpl: (call) => {
      const name = String(call.name || '')
      if (name.endsWith('workspace')) {
        return { ok: true, repoPath: '/repos/.worktrees/ssbd-1xcs-chassis', branch: 'fix/ssbd-1xcs', reused: false, isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      // The run is allowed to die at Integration — the assertion is about what never
      // re-ran BEFORE it, not about reaching deploy.
      if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
      return { ok: true }
    },
  })
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:bug-triage').length, 0, 'triage was completed in a previous dispatch')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:tdd-red').length, 0, 'red was completed in a previous dispatch')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:tdd-green').length, 0, 'green was completed in a previous dispatch')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:tdd-refactor').length, 0, 'refactor was completed in a previous dispatch')
  assert.ok(workflowCalls(calls, 'agent-teams-workforce:integration').length >= 1, 'execution continues from the first INCOMPLETE phase')
  assert.equal(result.ok, false, 'the scripted integration escalation still fails the run — resume is not a free pass')
})

// ── The version constant cannot drift from the manifest ───────────────────────

test('CHECKPOINT_VERSION in every checkpointing composite equals the plugin version', () => {
  // The staleness guard keys on the plugin version, but a workflow script cannot read
  // plugin.json at runtime — it carries a constant instead. This test is what makes
  // that constant trustworthy: a version bump that forgets the constants fails here.
  for (const file of ['prd-to-spec.js', 'bug-fix.js', 'task-to-deploy.js']) {
    const src = fs.readFileSync(path.join(WF, file), 'utf8')
    const m = src.match(/const CHECKPOINT_VERSION = '([^']+)'/)
    assert.ok(m, `${file} must declare CHECKPOINT_VERSION`)
    assert.equal(m[1], PLUGIN_VERSION, `${file}: CHECKPOINT_VERSION (${m[1]}) must equal the plugin version (${PLUGIN_VERSION}) — bump them together`)
  }
})
