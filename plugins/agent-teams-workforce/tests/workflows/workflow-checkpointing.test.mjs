// Phase-level checkpointing behaviours that still exist.
//
// bug-fix and task-to-deploy write and resume their own checkpoints. prd-to-spec has none: it
// resumes from the Epic's steps-completed file, which the host reads into `args.resume`. What
// is pinned here is bug-fix resuming from its checkpoint, and every checkpointing composite
// declaring a CHECKPOINT_SEMANTICS counter decoupled from the plugin version.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, workflowCalls } from './helpers/run-workflow.mjs'

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
const CHECKPOINTING_COMPOSITES = ['bug-fix.js', 'task-to-deploy.js']
const semanticsOf = (file) => {
  const src = fs.readFileSync(path.join(WF, file), 'utf8')
  const m = src.match(/const CHECKPOINT_SEMANTICS = '([^']*)'/)
  return m ? m[1] : null
}

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
