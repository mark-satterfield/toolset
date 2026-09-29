// ssbd-1xcs H1 — deployed-red carve-out hardening (bug-fix.js).
// Encodes acceptance criteria H1-AC1 .. H1-AC3 (numbered AC28-AC30 in the bead),
// plus the DETERMINISTIC half of H1-AC4 (AC31): that the Red gate '2a' receives the
// hardened criterion, verified at the gate-enforce seam. The judgment half of
// AC31 and all of AC32 are manual-eval items owned by test-design-lead, per the
// decided test strategy; they are deliberately NOT automated here.
//
// Defect under test: the deployed-red criterion is duplicated verbatim at
// bug-fix.js:138 and :207, carries no anti-abuse clause (unlike its sibling at
// deploy.js:77), and states an unconditional imperative that can be read as
// surviving the failure of its own precondition. AC28 demands one shared constant.

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
 * Drive bug-fix.js through the Red gate '2a', which escalates to triage (run ends).
 * Captures every gate-enforce payload for gate '2a' so its criteria are observable.
 */
async function runBugFixThroughRedGate() {
  const redGatePayloads = []
  const { result } = await runWorkflowScript(BUG_FIX_JS, {
    args: { bead: { id: 'ssbd-fixture', title: 'deployed-red fixture', description: 'd', repoPath: '/tmp/fixture' } },
    agentImpl: () => ({ written: true }), // ledger:persist
    workflowImpl: (call) => {
      // The composite's first phase is `workspace` — it OWNS the worktree every writing
      // phase then operates in, so a fixture must supply one or the run correctly
      // refuses to write anywhere (ssbd-mz1w).
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: '/tmp/worktrees/fixture', branch: 'fix/ssbd-fixture', reused: false, isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { bead: { id: 'ssbd-fixture', title: 'deployed-red fixture' }, repoPath: '/tmp/fixture' }
      }
      if (call.name === 'agent-teams-workforce:tdd-red') {
        return { testFiles: ['tests/test_defect.py'], redConfirmed: true, evidence: 'fails at HEAD' }
      }
      if (call.name === 'agent-teams-workforce:gate-enforce' && call.payload.gate === '2a') {
        redGatePayloads.push(call.payload)
        return { verdict: 'escalate', escalateTo: 'triage' }
      }
      return {}
    },
  })
  return { result, redGatePayloads }
}

/**
 * A gate criterion is EITHER a plain string or `{ text, class }`. The plain form is the
 * default path and must keep working forever; the classed form carries constitutive vs
 * competitive. Both are read for their text here, so this assertion is about the
 * criterion's WORDING regardless of which form carries it.
 */
function criterionText(c) {
  if (typeof c === 'string') return c
  if (c && typeof c === 'object' && typeof c.text === 'string') return c.text
  return ''
}

function deployedRedEntries(criteria) {
  return (criteria || []).map(criterionText).filter((t) => /Deployed red/i.test(t))
}

// ─── H1-AC1 (AC28) — single source for the deployed-red criterion ─────────────
// Also absorbs the deterministic half of H1-AC4 (AC31): the criterion reaches
// gate-enforce for gate '2a'.
test('H1-AC1: the Red gate receives the deployed-red criterion from ONE shared constant', async () => {
  const src = readWorkflowSource(BUG_FIX_JS)
  const candidates = topLevelStringConsts(src).filter((c) => /Deployed red/i.test(c.value))
  assert.equal(
    candidates.length, 1,
    'bug-fix.js must carry exactly one shared deployed-red criterion constant. It must NOT be exported — the runtime rejects a second top-level export outright.'
  )
  const constant = candidates[0].value

  const { redGatePayloads } = await runBugFixThroughRedGate()
  assert.equal(redGatePayloads.length, 1, 'the Red gate must reach gate-enforce once')

  const first = deployedRedEntries(redGatePayloads[0].criteria)
  assert.equal(first.length, 1, 'the Red gate must carry exactly one deployed-red criterion')
  assert.equal(first[0], constant, 'the Red gate entry must === the shared constant')
})

// ─── H1-AC2 (AC29) — anti-abuse clause present ───────────────────────────────
test('H1-AC2: the deployed-red criterion names the abuse cases explicitly, like its sibling carve-out at deploy.js:77', async () => {
  const { redGatePayloads } = await runBugFixThroughRedGate()
  assert.equal(redGatePayloads.length, 1)

  for (const [i, payload] of redGatePayloads.entries()) {
    const entries = deployedRedEntries(payload.criteria)
    assert.ok(entries.length >= 1, `Red gate ${i + 1} must carry a deployed-red criterion`)
    const text = entries[0]
    const site = `Red gate ${i + 1}`

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
  const { redGatePayloads } = await runBugFixThroughRedGate()
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
