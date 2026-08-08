'use strict';

/**
 * ssbd-ja5d — REQ-ORCH-04 (root cause D + single-sentence root cause): every
 * one of the four forbidden orchestrator actions must be covered by a guard
 * that evaluates the orchestrator session (agent_id absent) and terminates
 * with exit code 2 on violation, while preserving the subagent exemption
 * (agent_id present -> exit 0, empty decision).
 *
 * The four forbidden actions:
 *   1. edit-code      — editing code (Edit/Write/MultiEdit/NotebookEdit)
 *   2. self-verify    — verifying its own output (curl / git inspection)
 *   3. name-dispatch  — dispatching a workflow by name against a stale snapshot
 *   4. payload-cap    — absorbing a full workflow completion payload
 *
 * Traceability:
 *   AC-ORCH-04a -> "AC-ORCH-04a[<category>]: ..."
 *   AC-ORCH-04b -> "AC-ORCH-04b[<category>]: ..."
 *   AC-ORCH-04c -> "AC-ORCH-04c: ..."
 *
 * Run: node --test plugins/agent-teams-workforce/tests/unit/*.test.cjs
 *
 * Intended RED reason: hooks.json registers no matcher for the edit tools, no
 * matcher for the Workflow dispatch tool, and no PostToolUse section at all;
 * for the Bash self-verify category the two registered guards exit 0 on curl
 * and git commands. No forbidden action reaches an exit-2 denial (root causes
 * A, C, F, H composed — the single-sentence root cause).
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const H = require('./support/hook-harness.cjs');

const SUBAGENT_ID = 'subagent-9f2c';

let tmpDir;
let probePy;
let producedTranscript;
let payload400;

test.before(() => {
  tmpDir = H.makeTempDir('ssbd-ja5d-forbidden-');
  probePy = H.writeProbe(tmpDir, 'probe.py', 'SENTINEL_ORIGINAL\n');
  producedTranscript = H.writeTranscript(tmpDir, 'transcript-produced.jsonl', probePy);
  payload400 = Array.from({ length: 400 }, (_, i) => `payload line ${i + 1}`).join('\n');
});

test.after(() => {
  H.removeTempDir(tmpDir);
});

/**
 * Category table: how to resolve the guard set for each forbidden action and
 * what a clearly violating orchestrator input looks like.
 */
function categories() {
  return [
    {
      id: 'edit-code',
      resolve: () => H.resolveGuardsForTool('PreToolUse', 'Write'),
      event: (agentId) =>
        H.makeEvent({
          toolName: 'Write',
          toolInput: { file_path: probePy, content: 'SENTINEL_EDITED\n' },
          agentId,
        }),
      missingMsg:
        'no PreToolUse guard is registered for the edit tools (Write) — root cause A',
    },
    {
      id: 'self-verify',
      resolve: () => H.resolveGuardsForTool('PreToolUse', 'Bash'),
      event: (agentId) =>
        H.makeEvent({
          toolName: 'Bash',
          toolInput: { command: 'curl https://dev.skillspoke.com/' },
          transcriptPath: producedTranscript,
          agentId,
        }),
      missingMsg: 'no PreToolUse guard is registered for Bash',
    },
    {
      id: 'name-dispatch',
      resolve: () => H.resolveGuardsForTool('PreToolUse', 'Workflow'),
      event: (agentId) =>
        H.makeEvent({
          toolName: 'Workflow',
          toolInput: { name: 'deploy', args: { bead: 'ssbd-ja5d' } },
          agentId,
        }),
      missingMsg:
        'no PreToolUse guard is registered for the Workflow dispatch tool — name dispatch against the stale session-start snapshot is entirely unobserved (root cause F)',
    },
    {
      id: 'payload-cap',
      resolve: () => [
        ...H.resolveGuardsForTool('PostToolUse', 'Workflow'),
        ...H.resolveGuardsForTool('PostToolUse', 'Task'),
      ],
      event: (agentId) =>
        H.makeEvent({
          eventName: 'PostToolUse',
          toolName: 'Workflow',
          toolInput: { name: 'deploy', args: { bead: 'ssbd-ja5d' } },
          toolResponse: payload400,
          agentId,
        }),
      missingMsg:
        'no PostToolUse guard is registered for workflow completions — a 400-line payload flows into the orchestrator context by construction (root cause H)',
    },
  ];
}

for (const cat of categories()) {
  test(`AC-ORCH-04a[${cat.id}]: orchestrator input (no agent_id) is evaluated and denied with exit 2`, () => {
    const guards = cat.resolve();
    assert.ok(
      guards.length > 0,
      `AC-ORCH-04a[${cat.id}]: ${cat.missingMsg} (checked ${H.HOOKS_JSON_PATH})`,
    );
    const results = guards.map((g) => H.runGuard(g, cat.event(undefined)));
    assert.ok(
      results.some((r) => r.status === 2),
      `AC-ORCH-04a[${cat.id}]: no registered guard denied the violating orchestrator call with exit code 2 (statuses: ${results.map((r) => r.status).join(', ')}) — the constraint is expressed only as text the orchestrator itself evaluates`,
    );
  });
}

for (const cat of categories()) {
  test(`AC-ORCH-04b[${cat.id}]: subagent input (agent_id present) passes with exit 0 and an empty decision`, () => {
    const guards = cat.resolve();
    assert.ok(
      guards.length > 0,
      `AC-ORCH-04b[${cat.id}]: ${cat.missingMsg} — there is no guard whose subagent exemption can be verified (checked ${H.HOOKS_JSON_PATH})`,
    );
    // REQ-ORCH-04b exempts subagents because these guards enforce the
    // orchestrator's ROLE — it does not implement, and a subagent does, so a
    // role guard that blocked subagents would block the work itself.
    //
    // That reasoning does not extend to guards enforcing WHERE work may land.
    // pre-tool-protect-main-worktree denies writes to the default branch in a main
    // working tree, and the failure it exists to stop was a TEST WRITER — a
    // subagent — putting files on `main`. Exempting subagents there would exempt
    // precisely the actor that caused the problem, leaving a guard that enforces
    // nothing. It is excluded here by name, deliberately and narrowly: the
    // exemption is scoped to role guards, and every other guard on this matcher
    // still has to prove it.
    const ROLE_EXEMPT_ONLY = /pre-tool-protect-main-worktree\.cjs$/;
    for (const guard of guards) {
      if (ROLE_EXEMPT_ONLY.test(guard.scriptPath)) continue;
      const r = H.runGuard(guard, cat.event(SUBAGENT_ID));
      assert.equal(
        r.status,
        0,
        `AC-ORCH-04b[${cat.id}]: guard ${guard.scriptPath} must exit 0 for a subagent session (agent_id present) — subagents are exempt`,
      );
      assert.equal(
        r.stderr,
        '',
        `AC-ORCH-04b[${cat.id}]: guard ${guard.scriptPath} must not emit denial text for a subagent session`,
      );
      assert.ok(
        H.isEmptyDecision(r.stdout),
        `AC-ORCH-04b[${cat.id}]: guard ${guard.scriptPath} must emit an empty decision ('' or {}) for a subagent session, got: ${JSON.stringify(r.stdout)}`,
      );
    }
  });
}

test('AC-ORCH-04c: every forbidden-action guard terminates with exit code 2 on violation — none is advisory-only', () => {
  for (const cat of categories()) {
    const guards = cat.resolve();
    assert.ok(
      guards.length > 0,
      `AC-ORCH-04c[${cat.id}]: ${cat.missingMsg} (checked ${H.HOOKS_JSON_PATH})`,
    );
    const results = guards.map((g) => H.runGuard(g, cat.event(undefined)));
    assert.ok(
      results.some((r) => r.status === 2),
      `AC-ORCH-04c[${cat.id}]: no guard reached a terminal exit code of 2 (statuses: ${results.map((r) => r.status).join(', ')})`,
    );
    const advisoryOnly =
      results.every((r) => r.status === 0) &&
      results.some((r) => r.stdout.includes('additionalContext'));
    assert.ok(
      !advisoryOnly,
      `AC-ORCH-04c[${cat.id}]: the category is covered only by an exit-0 hookSpecificOutput.additionalContext advisory — text the actor may disregard is not enforcement (single-sentence root cause)`,
    );
  }
});
