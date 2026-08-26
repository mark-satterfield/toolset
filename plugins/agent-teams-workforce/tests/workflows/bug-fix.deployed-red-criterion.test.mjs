// ssbd-1xcs H1 — deployed-red carve-out hardening (bug-fix.js).
// Encodes acceptance criteria H1-AC1 .. H1-AC3 (numbered AC28-AC30 in the bead),
// plus the DETERMINISTIC half of H1-AC4 (AC31): that both Red gates — the first
// gate and the post-escalation re-authored gate '2a' — receive the identical
// hardened criterion, verified at the gate-enforce seam. The judgment half of
// AC31 and all of AC32 are manual-eval items owned by test-design-lead, per the
// decided test strategy; they are deliberately NOT automated here.
//
// Defect under test: the deployed-red criterion is duplicated verbatim at
// bug-fix.js:138 and :207, carries no anti-abuse clause (unlike its sibling at
// deploy.js:77), and states an unconditional imperative that can be read as
// surviving the failure of its own precondition. A single-site fix diverges the
// first Red gate from the post-escalation Red gate — hence AC28 demands one
// shared exported constant referenced by both call sites.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, readWorkflowSource } from './helpers/run-workflow.mjs'

const BUG_FIX_JS = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..', '..', 'workflows', 'bug-fix.js'
)

/**
 * Safely decode a quoted JS string literal (no eval / new Function — the source
 * text is parsed manually). Template literals containing `${` interpolation are
 * rejected: a criterion constant must be a plain string.
 */
function parseStringLiteral(lit) {
  const quote = lit[0]
  const body = lit.slice(1, -1)
  if (quote === '`' && body.includes('${')) return null
  const ESCAPES = { n: '\n', t: '\t', r: '\r', b: '\b', f: '\f', v: '\v', 0: '\0' }
  let out = ''
  for (let i = 0; i < body.length; i += 1) {
    const ch = body[i]
    if (ch === '\\' && i + 1 < body.length) {
      i += 1
      const next = body[i]
      out += Object.prototype.hasOwnProperty.call(ESCAPES, next) ? ESCAPES[next] : next
    } else {
      out += ch
    }
  }
  return out
}

/**
 * Extract `export const NAME = <string literal>` declarations from the script
 * source and decode the literals without executing any source text.
 */
function topLevelStringConsts(src) {
  // Deliberately NOT `export const`. The runtime accepts exactly one top-level
  // export — meta — and rejects the script on a second, before any phase runs.
  // This constant was exported to satisfy an earlier reading of this test, which
  // made bug-fix.js the only undispatchable workflow in the set. What the
  // requirement actually needs is ONE shared constant, so a single edit changes
  // both call sites; module-private satisfies that exactly.
  const out = []
  const re = /^const\s+([A-Z0-9_]+)\s*=\s*\n?\s*(['`])([\s\S]*?)\2/gm
  let m
  while ((m = re.exec(src)) !== null) out.push({ name: m[1], value: m[3] })
  return out
}

/**
 * Drive bug-fix.js through: Red pass -> Green gate escalates to 'red' ->
 * post-escalation Red gate '2a' -> escalate to triage (run ends). Captures every
 * gate-enforce payload for gate '2a' so both Red gates' criteria are observable.
 */
async function runBugFixThroughBothRedGates() {
  const redGatePayloads = []
  const { result } = await runWorkflowScript(BUG_FIX_JS, {
    args: { bead: { id: 'ssbd-fixture', title: 'deployed-red fixture', description: 'd', repoPath: '/tmp/fixture' } },
    agentImpl: () => ({ written: true }), // ledger:persist
    workflowImpl: (call) => {
      // The composite's first phase is `workspace` — it OWNS the worktree every writing
      // phase then operates in, so a fixture must supply one or the run correctly
      // refuses to write anywhere (ssbd-mz1w).
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: '/tmp/worktrees/fixture', branch: 'fix/ssbd-fixture', reused: false, isLinkedWorktree: true }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { bead: { id: 'ssbd-fixture', title: 'deployed-red fixture' }, repoPath: '/tmp/fixture' }
      }
      if (call.name === 'agent-teams-workforce:tdd-red') {
        return { testFiles: ['tests/test_defect.py'], redConfirmed: true, evidence: 'fails at HEAD' }
      }
      if (call.name === 'agent-teams-workforce:tdd-green') {
        return { changedFiles: [], greenConfirmed: false, evidence: '' }
      }
      if (call.name === 'agent-teams-workforce:gate-enforce') {
        if (call.payload.gate === '2a') {
          redGatePayloads.push(call.payload)
          // First Red gate passes; the post-escalation Red gate ends the run.
          return redGatePayloads.length === 1
            ? { verdict: 'pass' }
            : { verdict: 'escalate', escalateTo: 'triage' }
        }
        if (call.payload.gate === '2b') {
          return { verdict: 'escalate', escalateTo: 'red', feedback: 'test defective by construction' }
        }
      }
      return {}
    },
  })
  return { result, redGatePayloads }
}

function deployedRedEntries(criteria) {
  return (criteria || []).filter((c) => typeof c === 'string' && /Deployed red/i.test(c))
}

// ─── H1-AC1 (AC28) — single source for the deployed-red criterion ─────────────
// Also absorbs the deterministic half of H1-AC4 (AC31): the identical criterion
// reaches gate-enforce for gate '2a' on BOTH the first and post-escalation paths.
test('H1-AC1: both Red gates receive the deployed-red criterion from ONE shared constant', async () => {
  const src = readWorkflowSource(BUG_FIX_JS)
  const candidates = topLevelStringConsts(src).filter((c) => /Deployed red/i.test(c.value))
  assert.equal(
    candidates.length, 1,
    'bug-fix.js must carry exactly one shared deployed-red criterion constant so a single edit changes both call sites. It must NOT be exported — the runtime rejects a second top-level export outright.'
  )
  const constant = candidates[0].value

  const { redGatePayloads } = await runBugFixThroughBothRedGates()
  assert.equal(redGatePayloads.length, 2, 'both Red gates (first + post-escalation) must reach gate-enforce')
  assert.match(
    String(redGatePayloads[1].phaseName), /re-authored after Green escalation/,
    'the second captured gate must be the post-escalation Red gate (AC31 deterministic half)'
  )

  const first = deployedRedEntries(redGatePayloads[0].criteria)
  const second = deployedRedEntries(redGatePayloads[1].criteria)
  assert.equal(first.length, 1, 'the first Red gate must carry exactly one deployed-red criterion')
  assert.equal(second.length, 1, 'the post-escalation Red gate must carry exactly one deployed-red criterion')
  assert.equal(first[0], constant, 'the first Red gate entry must === the exported constant')
  assert.equal(second[0], constant, 'the post-escalation Red gate entry must === the exported constant')
  assert.equal(first[0], second[0], 'both gates must carry the identical criterion text')
})

// ─── H1-AC2 (AC29) — anti-abuse clause present at both sites ──────────────────
test('H1-AC2: the deployed-red criterion names the abuse cases explicitly, like its sibling carve-out at deploy.js:77', async () => {
  const { redGatePayloads } = await runBugFixThroughBothRedGates()
  assert.equal(redGatePayloads.length, 2)

  for (const [i, payload] of redGatePayloads.entries()) {
    const entries = deployedRedEntries(payload.criteria)
    assert.ok(entries.length >= 1, `Red gate ${i + 1} must carry a deployed-red criterion`)
    const text = entries[0]
    const site = i === 0 ? 'first Red gate' : 'post-escalation Red gate'

    assert.match(text, /observed/i,
      `${site}: the criterion must forbid claiming deployed red when no failing run against the deployed environment was actually OBSERVED and reported`)
    assert.match(text, /(never|not|un)[\s-]?checked|was never checked/i,
      `${site}: the criterion must forbid claiming deployed red when the source tree was never CHECKED for a source-level red`)
    assert.match(text, /inconvenient/i,
      `${site}: the criterion must name convenience-abuse ('merely because running a source-level test is inconvenient')`)
    assert.match(text, /unclear/i,
      `${site}: the criterion must name the unclear-environment abuse case`)
    assert.match(text, /credential/i,
      `${site}: the criterion must name the missing-credentials abuse case`)
    assert.match(text, /genuine failure/i,
      `${site}: the criterion must state that those cases are a genuine failure to obtain red`)
  }
})

// ─── H1-AC3 (AC30) — precondition is not severable from the imperative ────────
test('H1-AC3: the sufficiency grant is explicitly conditioned on its precondition (deployed evidence observed AND source tree correct)', async () => {
  const { redGatePayloads } = await runBugFixThroughBothRedGates()
  const text = deployedRedEntries(redGatePayloads[0].criteria)[0]
  assert.ok(text, 'the first Red gate must carry a deployed-red criterion')

  const idx = text.search(/fully sufficient/i)
  assert.ok(idx >= 0, "the criterion must still grant sufficiency ('fully sufficient') — the ssbd-mqkq fix must not be reverted")
  const window = text.slice(Math.max(0, idx - 300), idx + 300)

  assert.match(
    window,
    /only\s+(if|when)|provided\s+that|precondition|conditioned/i,
    "the sufficiency grant must be explicitly conditioned (e.g. 'only when', 'provided that') so the imperative cannot be read as surviving the failure of its precondition"
  )
  assert.match(
    window,
    /observed/i,
    'the condition must include that deployed evidence was actually observed'
  )
  assert.match(
    window,
    /source tree|already correct/i,
    'the condition must include that the source tree is already correct'
  )
})
