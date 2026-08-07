'use strict';

/**
 * ssbd-ja5d — REQ-ORCH-08 (root cause H): workflow completion payloads must be
 * capped by the workflow/hook layer before entering the orchestrator context.
 * This unit covers the small-payload pass-through row.
 *
 * Traceability:
 *   AC-ORCH-08c -> "AC-ORCH-08c: ..."
 *
 * Run: node --test plugins/agent-teams-workforce/tests/unit/*.test.cjs
 *
 * Intended RED reason: hooks.json contains no PostToolUse section at all —
 * there is no completion-payload layer whose pass-through behavior can be
 * exercised. The 15-line instruction exists only as prose at
 * .claude/missions/implement-all-prds.md:132 ("SHORT-RETURN IS PROSE ONLY").
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const H = require('./support/hook-harness.cjs');

test('AC-ORCH-08c: a 9-line completion payload passes through unchanged — no truncation marker, no detail path', () => {
  const guards = [
    ...H.resolveGuardsForTool('PostToolUse', 'Workflow'),
    ...H.resolveGuardsForTool('PostToolUse', 'Task'),
  ];
  assert.ok(
    guards.length > 0,
    `AC-ORCH-08c: no completion-payload guard is registered for Workflow/Task in ${H.HOOKS_JSON_PATH} — the 15-line cap exists only as mission prose, so there is no layer whose pass-through behavior can hold (root cause H)`,
  );

  const nineLines = Array.from({ length: 9 }, (_, i) => `verdict line ${i + 1}`).join('\n');
  const event = H.makeEvent({
    eventName: 'PostToolUse',
    toolName: 'Workflow',
    toolInput: { name: 'deploy', args: { bead: 'ssbd-ja5d' } },
    toolResponse: nineLines,
  });

  for (const guard of guards) {
    const r = H.runGuard(guard, event);
    assert.equal(
      r.status,
      0,
      `AC-ORCH-08c: guard ${guard.scriptPath} must allow a 9-line payload (exit 0) — payloads at or under the cap enter the context unchanged`,
    );
    assert.equal(
      r.stderr,
      '',
      `AC-ORCH-08c: guard ${guard.scriptPath} must not emit denial text for a 9-line payload`,
    );
    const combined = `${r.stdout}\n${r.stderr}`;
    assert.ok(
      !/truncat/i.test(combined),
      `AC-ORCH-08c: guard ${guard.scriptPath} must not add a truncation marker to a payload already under the cap`,
    );
  }
});
