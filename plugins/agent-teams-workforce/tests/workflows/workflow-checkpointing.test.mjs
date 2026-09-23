// Phase-level checkpointing behaviours that still exist.
//
// bug-fix and task-to-deploy write and resume their own checkpoints. prd-to-spec no longer
// writes one: its makers save their artifacts into the Epic working directory, the host passes
// the freshness plan in as `args.resume`, and its checkpoint loader is kept only as a migration
// reader for directories written before that. What is pinned here is the create-repos exit
// retiring nothing, bug-fix resuming from its checkpoint, and every checkpointing composite
// declaring a CHECKPOINT_SEMANTICS counter decoupled from the plugin version.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, agentCalls, workflowCalls } from './helpers/run-workflow.mjs'
import { beadWriter, lifecycleRunner, TEST_EPIC } from './helpers/bead-writer.mjs'

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

/** The phase-semantics version a composite declares. Hand-bumped; never the plugin's. */
const CHECKPOINTING_COMPOSITES = ['prd-to-spec.js', 'bug-fix.js', 'task-to-deploy.js']
const semanticsOf = (file) => {
  const src = fs.readFileSync(path.join(WF, file), 'utf8')
  const m = src.match(/const CHECKPOINT_SEMANTICS = '([^']*)'/)
  return m ? m[1] : null
}

// ── prd-to-spec fixture (mirrors standing-rulings' minimal happy path) ─────────

function compositeWorkflows({ failSpec = false, scopingRepos = ['/repos/alpha'], newRepos = [] } = {}) {
  return (call) => {
    const name = String(call.name || '')
    if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) return { verdict: 'pass', criteria: [], flags: [] }
    if (name.endsWith('prd-reconciliation')) {
      return {
        ok: true,
        requirements: [{ id: 'R1', requirement: 'r', status: 'absent', evidence: ['f.py:1'], surface: 'service', repos: scopingRepos }],
        conformsCount: 0, contradictsCount: 0, absentCount: 1,
        removalWork: [], reuseWork: [],
        repos: scopingRepos, existingRepos: [], spansMultipleRepos: scopingRepos.length > 1,
        uiAuthority: { bundlePath: null, mocksDir: null, artifactsConsulted: [], shellsConsulted: [], pagesConsulted: [] },
      }
    }
    if (name.endsWith('prd-validation')) return { ok: true, validatedPrd: { id: 'P1', title: 'P', body: 'validated-body' }, findings: [] }
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

async function runP2S({ onDisk = null, workflowOpts = {}, args = {} } = {}) {
  const writer = beadWriter()
  const lifecycle = lifecycleRunner()
  const saves = []
  const result = await runWorkflowScript(path.join(WF, 'prd-to-spec.js'), {
    args: { prd: PRD, repoPath: '/repos/alpha', epic: TEST_EPIC, ...args },
    workflowImpl: compositeWorkflows(workflowOpts),
    agentImpl: (call) => {
      const ran = lifecycle(call)
      if (ran) return ran
      const l = String(call.label)
      // prd-to-spec reads the checkpoint, its write-ahead copy and the standing rulings in
      // ONE session — a fresh agent session costs its session start, not its work. The
      // RETIREMENT, by contrast, gets its own session on purpose: folding it into the
      // journal write handed one agent a verbatim-JSON errand and a JSONL errand at once,
      // and it blended the two contracts and corrupted real checkpoints.
      if (l === 'resolve:run-inputs') {
        return {
          files: [...(onDisk || []), { name: 'rulings', found: false, content: '' }],
        }
      }
      if (l === 'checkpoint:retire') return { retired: true }
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

/** True when the run retired its checkpoint. */
function retired(calls) {
  return agentCalls(calls, 'checkpoint:retire').length > 0
}

test('the create-repos exit keeps the checkpoint — its purpose is a re-run after a human acts', async () => {
  const { result, calls } = await runP2S({
    workflowOpts: { scopingRepos: [], newRepos: [{ proposedName: 'SkillSpoke-newthing', purpose: 'p', workUnitIds: ['W1'], whyNoExistingRepoFits: 'none fits' }] },
  })
  assert.equal(result.ok, true)
  assert.equal(result.action, 'create-repos')
  assert.equal(retired(calls), false)
})

// ── bug-fix ───────────────────────────────────────────────────────────────────

test('bug-fix re-runs triage, then resumes red+green and refactor from a checkpoint', async () => {
  const BEAD = { id: 'ssbd-1xcs', title: 's', description: 'd', repoPath: '/repos/chassis' }
  const file = JSON.stringify({
    composite: 'bug-fix',
    subject: BEAD.id,
    semanticsVersion: semanticsOf('bug-fix.js'),
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
      // re-ran BEFORE it, not about reaching deploy. The escalation names `triage`: an
      // escalation to Green is repaired through Green, which is not what this test counts.
      if (name.endsWith('gate-enforce') || name.endsWith('gate-constitutional')) return { verdict: 'escalate', escalateTo: 'triage', criteria: [] }
      return { ok: true }
    },
  })
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:bug-triage').length, 1, 'a Bug never skips triage, a checkpoint notwithstanding')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:tdd-red').length, 0, 'red was completed in a previous dispatch')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:tdd-green').length, 0, 'green was completed in a previous dispatch')
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:tdd-refactor').length, 0, 'refactor was completed in a previous dispatch')
  assert.ok(workflowCalls(calls, 'agent-teams-workforce:integration').length >= 1, 'execution continues from the first INCOMPLETE phase')
  assert.equal(result.ok, false, 'the scripted integration escalation still fails the run — resume is not a free pass')
})

// ── The semantics constant is declared, and is NOT the manifest version ───────

test('every checkpointing composite declares a CHECKPOINT_SEMANTICS counter, decoupled from the plugin version', () => {
  // Each composite owns its own phase sequence, so the three are free to diverge and
  // nothing here asserts they agree — a bump belongs to the one composite whose phases
  // actually changed. What IS pinned is the shape: a declared, non-empty, hand-bumped
  // counter that is not the manifest version. The old constant was pinned to the plugin
  // version, and the plugin bumps constantly, so every release threw every checkpoint
  // away. Re-coupling it would restore the defect, so the coupling is what fails here.
  for (const file of CHECKPOINTING_COMPOSITES) {
    const src = fs.readFileSync(path.join(WF, file), 'utf8')
    const v = semanticsOf(file)
    assert.ok(typeof v === 'string' && v.length > 0, `${file} must declare a non-empty CHECKPOINT_SEMANTICS`)
    assert.notEqual(v, PLUGIN_VERSION, `${file}: CHECKPOINT_SEMANTICS must NOT be the plugin version (${PLUGIN_VERSION}) — that coupling discarded every checkpoint on every release`)
    assert.doesNotMatch(v, /\./, `${file}: CHECKPOINT_SEMANTICS (${v}) is a plain counter, not a semver — a semver reads as a release marker and invites re-coupling`)
    assert.doesNotMatch(src, /CHECKPOINT_VERSION/, `${file} must not carry the retired plugin-version-pinned constant`)
    assert.doesNotMatch(src, /pluginVersion:/, `${file} must not write pluginVersion into the checkpoint payload`)
  }
})
