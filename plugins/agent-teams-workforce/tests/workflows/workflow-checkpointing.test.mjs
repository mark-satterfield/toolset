// Composites are RESUMABLE ACROSS DISPATCHES via phase-level checkpointing.
//
// "If we reach a spend limit, then execution should pause, but when the spend limit
// resets, it should pick back up." The supervisor re-dispatches a killed composite,
// but the re-dispatch used to restart from minute zero — ssbd-qxeu died at 103
// minutes, ~10 from finishing architecture, and every minute was lost. These tests
// pin the five behaviors that make resume real: each completed phase's RESULT is
// SAVED to a durable per-bead file; a resumed run SKIPS completed phases and REUSES
// their results; a checkpoint whose PRD content hash or PHASE SEMANTICS version differs
// is INVALIDATED (fresh start, journalled); and a completed run DELETES its checkpoint
// while a failed one keeps it.
//
// The semantics version is deliberately NOT the plugin version. It was, and every plugin
// release then discarded every checkpoint in every composite — 6.11.0 was a markdown edit
// to one skill — so a checkpoint surviving a plugin bump is itself a pinned behavior here.

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

/** The phase-semantics version a composite declares. Hand-bumped; never the plugin's. */
const CHECKPOINTING_COMPOSITES = ['prd-to-spec.js', 'bug-fix.js', 'task-to-deploy.js']
const semanticsOf = (file) => {
  const src = fs.readFileSync(path.join(WF, file), 'utf8')
  const m = src.match(/const CHECKPOINT_SEMANTICS = '([^']*)'/)
  return m ? m[1] : null
}

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

async function runP2S({ checkpointFile = null, walFile = null, workflowOpts = {}, args = {} } = {}) {
  const writer = beadWriter()
  const saves = []
  const result = await runWorkflowScript(path.join(WF, 'prd-to-spec.js'), {
    args: { prd: PRD, repoPath: '/repos/alpha', ...args },
    workflowImpl: compositeWorkflows(workflowOpts),
    agentImpl: (call) => {
      const l = String(call.label)
      // prd-to-spec reads the checkpoint, its write-ahead copy and the standing rulings in
      // ONE session — a fresh agent session costs its session start, not its work. The
      // RETIREMENT, by contrast, gets its own session on purpose: folding it into the
      // journal write handed one agent a verbatim-JSON errand and a JSONL errand at once,
      // and it blended the two contracts and corrupted real checkpoints.
      if (l === 'resolve:run-inputs') {
        return {
          files: [
            { key: 'checkpoint', found: Boolean(checkpointFile), content: checkpointFile || '' },
            { key: 'checkpointWal', found: Boolean(walFile), content: walFile || '' },
            { key: 'rulings', found: false, content: '' },
          ],
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

test('a fresh run SAVES each completed phase result to the per-bead checkpoint file', async () => {
  const { result, saves } = await runP2S()
  assert.equal(result.ok, true, `composite failed at ${result.stage}: ${result.headline || ''}`)
  const keys = saves.map((c) => String(c.label).replace('checkpoint:save:', ''))
  // `recon:<repo>` rather than a front-end `reconciliation`: the current-state comparison
  // runs per repository inside spec authoring, so it checkpoints per repository too — a
  // resume that already paid for one repository's inventory must not pay again.
  for (const expected of ['validation', 'architecture', 'repo-scoping', 'trd-authoring', 'recon:/repos/alpha', 'spec:/repos/alpha', 'decomposition:S1']) {
    assert.ok(keys.includes(expected), `phase '${expected}' must be checkpointed as it completes; saved: ${keys.join(', ')}`)
  }
  for (const c of saves) {
    assert.match(c.prompt, /\/repos\/alpha\/\.claude\/workflow-runs\/checkpoints\/P1-prd-to-spec\.json/, 'the file lives in the repo the run operates on, keyed by bead+composite')
  }
  const last = savedPayload(saves[saves.length - 1])
  assert.equal(last.semanticsVersion, semanticsOf('prd-to-spec.js'), 'the staleness guard keys on the composite\'s phase-semantics version')
  assert.equal(last.pluginVersion, undefined, 'the plugin version is deliberately NOT written — it is not what makes a checkpoint stale')
  assert.equal(last.inputHash, fnv(PRD.body), 'the staleness guard keys on the PRD content hash')
  const recon = last.phases['recon:/repos/alpha']
  assert.ok(recon, 'the saved payload is the actual RESULT the next phase consumes, not a marker')
  assert.equal(recon.requirements.length, 1, "the repository's own material inventory is what resumes")
  assert.ok(last.phases['spec:/repos/alpha'], 'and the spec it fed is checkpointed beside it, per repo')
})

/** True when the run retired its checkpoint. */
function retired(calls) {
  return agentCalls(calls, 'checkpoint:retire').length > 0
}

test('a completed successful run RETIRES its checkpoint — and its write-ahead copy — in its OWN dispatch', async () => {
  const { calls } = await runP2S()
  assert.ok(retired(calls), 'resuming finished work would replay it, so the retirement must happen')
  const [journal] = agentCalls(calls, 'ledger:persist')
  assert.doesNotMatch(
    String(journal.prompt),
    /RETIRE/,
    'the retirement is NOT folded into the journal write: one agent handed a verbatim-JSON errand and a JSONL errand blended the two contracts and corrupted real checkpoints',
  )
  const [retire] = agentCalls(calls, 'checkpoint:retire')
  assert.match(
    String(retire.prompt),
    /\/repos\/alpha\/\.claude\/workflow-runs\/checkpoints\/P1-prd-to-spec\.json/,
    'the retirement names the run\'s own checkpoint path',
  )
  assert.match(
    String(retire.prompt),
    /\/repos\/alpha\/\.claude\/workflow-runs\/checkpoints\/P1-prd-to-spec\.json\.wal/,
    'BOTH files, or the loader recovers the finished run from the copy and replays every phase',
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
  assert.equal(retired(calls), false, 'a kept checkpoint is the whole point of pausing')
})

test('the create-repos exit keeps the checkpoint — its purpose is a re-run after a human acts', async () => {
  const { result, calls } = await runP2S({
    workflowOpts: { scopingRepos: [], newRepos: [{ proposedName: 'SkillSpoke-newthing', purpose: 'p', workUnitIds: ['W1'], whyNoExistingRepoFits: 'none fits' }] },
  })
  assert.equal(result.ok, true)
  assert.equal(result.action, 'create-repos')
  assert.equal(retired(calls), false)
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
  assert.match(journal.prompt, /written against a different PRD text/)
})

test('a checkpoint written under DIFFERENT phase semantics is invalidated', async () => {
  const first = await runP2S()
  const payload = savedPayload(first.saves[first.saves.length - 1])
  payload.semanticsVersion = '0'
  const second = await runP2S({ checkpointFile: JSON.stringify(payload) })
  assert.equal(workflowCalls(second.calls, 'agent-teams-workforce:prd-reconciliation').length, 1)
  const journal = agentCalls(second.calls, 'ledger:persist')[0]
  assert.match(journal.prompt, /"event":"invalidated"/)
  assert.match(journal.prompt, /phase semantics/)
})

test('a PRE-GUARD checkpoint — pluginVersion, no semanticsVersion — is invalidated exactly once, not crashed on', async () => {
  const first = await runP2S()
  const payload = savedPayload(first.saves[first.saves.length - 1])
  delete payload.semanticsVersion
  payload.pluginVersion = '6.10.1' // what the old code wrote
  const second = await runP2S({ checkpointFile: JSON.stringify(payload) })
  assert.equal(second.result.ok, true, 'an unrecognised shape must not take the run down with it')
  assert.equal(workflowCalls(second.calls, 'agent-teams-workforce:prd-reconciliation').length, 1, 'its phases cannot be trusted, so it is discarded')
  const journal = agentCalls(second.calls, 'ledger:persist')[0]
  assert.match(journal.prompt, /"event":"invalidated"/)
  assert.match(journal.prompt, /predates the phase-semantics guard/)
  // And the fresh run rewrites it in the new shape, so the discard happens ONCE.
  const rewritten = savedPayload(second.saves[second.saves.length - 1])
  assert.equal(rewritten.semanticsVersion, semanticsOf('prd-to-spec.js'))
})

test('a checkpoint carrying a FRONT-END reconciliation phase is discarded in full — this sequence cannot produce one', async () => {
  // PRD Reconciliation used to be phases[0] and used to feed PRD validation, the
  // architecture panel and the TRD. It now runs per repository INSIDE spec authoring, under
  // the key `recon:<repo>`, and nothing before the specs is handed a deployed-state
  // inventory at all. So a top-level `reconciliation` key is a phase this sequence has no
  // way of writing.
  //
  // The normal case is caught one level up: bumping CHECKPOINT_SEMANTICS rejects every
  // version-1 file whole, by name and reason. This is the BACKSTOP for a file that claims
  // the current semantics and carries the key anyway — mislabelled, hand-edited, or written
  // by something else — and the point is that PART of such a file is exactly as
  // untrustworthy as all of it. Every entry after the old front-end phase was derived from
  // it: a real checkpoint on disk carried a `validation` entry recording a Gate 1 verdict
  // granted to a narrowed PRD, and the inputHash is over the PRD text, which did not
  // change, so nothing else would invalidate it.
  const first = await runP2S()
  const payload = savedPayload(first.saves[first.saves.length - 1])
  payload.phases.reconciliation = { ok: true, verdict: 'partial', deltaCount: 1, sizeVerdict: 'story' }
  const second = await runP2S({ checkpointFile: JSON.stringify(payload) })
  assert.equal(second.result.ok, true)
  // `architecture` is absent from this list because the triage fixture skips it — it is
  // never dispatched as a mini at all, so it has no checkpointed result to be stale.
  for (const mini of ['prd-validation', 'repo-scoping', 'trd-authoring', 'prd-reconciliation', 'spec-authoring', 'task-decomposition']) {
    assert.equal(
      workflowCalls(second.calls, `agent-teams-workforce:${mini}`).length,
      1,
      `${mini}'s checkpointed result is exactly as stale as the retired phase it was derived from`,
    )
  }
  const journal = agentCalls(second.calls, 'ledger:persist')[0]
  assert.match(journal.prompt, /which this sequence cannot produce/)
  assert.match(journal.prompt, /"discardedAll":true/, 'the invalidation must STATE what it dropped, not just that one key went')
  assert.match(journal.prompt, /"discarded":\["validation"/)
  // And the discarded entries must not be written straight back: the file is rewritten
  // WHOLE from cp.phases, so a stale entry left there would greet the next resume.
  const rewritten = savedPayload(second.saves[0])
  assert.deepEqual(Object.keys(rewritten.phases), ['validation'], 'the first save after a full discard carries only the phase that just completed')
})

test('the semantics bump is what rejects a real version-1 checkpoint, and it says why', async () => {
  // The primary guard for this change, as opposed to the backstop above. A file written by
  // the previous sequence carries semanticsVersion '1'; every phase in it was derived from
  // a deployed-state inventory that architecture and the TRD no longer read.
  const first = await runP2S()
  const payload = savedPayload(first.saves[first.saves.length - 1])
  assert.equal(payload.semanticsVersion, '2', 'the relocation of the current-state comparison is a phase-sequence change')
  payload.semanticsVersion = '1'
  const second = await runP2S({ checkpointFile: JSON.stringify(payload) })
  assert.equal(second.result.ok, true)
  for (const mini of ['prd-validation', 'repo-scoping', 'trd-authoring', 'prd-reconciliation', 'spec-authoring']) {
    assert.equal(workflowCalls(second.calls, `agent-teams-workforce:${mini}`).length, 1, `${mini} must re-run`)
  }
  const journal = agentCalls(second.calls, 'ledger:persist')[0]
  assert.match(journal.prompt, /"event":"invalidated"/)
  assert.match(journal.prompt, /written under phase semantics 1 and this composite is at 2/, 'the rejection names the reason, never silently misapplies')
})

test('a per-repo comparison is resumed per repo — a repo already inventoried is not read twice', async () => {
  const first = await runP2S()
  const file = JSON.stringify(savedPayload(first.saves[first.saves.length - 1]))
  const second = await runP2S({ checkpointFile: file })
  assert.equal(second.result.ok, true, `resumed composite failed at ${second.result.stage}: ${second.result.headline || ''}`)
  assert.equal(
    workflowCalls(second.calls, 'agent-teams-workforce:prd-reconciliation').length,
    0,
    'the inventory for this repository was already paid for; re-reading the repository is the cost the checkpoint exists to avoid',
  )
})

test('a checkpoint SURVIVES a plugin version change when the phase semantics are unchanged', async () => {
  // This is the defect the semantics version exists to fix: 6.11.0 was a markdown edit to
  // one skill and it discarded every resumable run in all three composites. A checkpoint
  // carrying a stale plugin version — however it got there — must still be honoured.
  const first = await runP2S()
  const payload = savedPayload(first.saves[first.saves.length - 1])
  payload.pluginVersion = '0.0.1'
  assert.notEqual(payload.pluginVersion, PLUGIN_VERSION, 'the fixture must actually differ from the shipped plugin version')
  assert.equal(payload.semanticsVersion, semanticsOf('prd-to-spec.js'), 'the semantics version is the one thing left unchanged')

  const second = await runP2S({ checkpointFile: JSON.stringify(payload) })
  assert.equal(second.result.ok, true, `resumed composite failed at ${second.result.stage}: ${second.result.headline || ''}`)
  for (const mini of ['prd-reconciliation', 'prd-validation', 'architecture', 'repo-scoping', 'trd-authoring', 'spec-authoring', 'task-decomposition']) {
    assert.equal(
      workflowCalls(second.calls, `agent-teams-workforce:${mini}`).length,
      0,
      `${mini} must NOT re-run — a plugin release is not a change to what a phase means`,
    )
  }
  const journal = agentCalls(second.calls, 'ledger:persist')[0]
  assert.match(journal.prompt, /"event":"resumed"/)
  assert.doesNotMatch(journal.prompt, /"event":"invalidated"/)
})

// ── bug-fix ───────────────────────────────────────────────────────────────────

test('bug-fix resumes triage, red+green, and refactor from a checkpoint', async () => {
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
