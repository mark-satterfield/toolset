'use strict';

/**
 * ssbd-ja5d / REQ-ORCH-08 — workflow completion payloads must be capped
 * before entering the orchestrator context.
 *
 * Threat model entry: root cause (H) "SHORT-RETURN IS PROSE ONLY" — the
 * 15-line rule exists only as narrative in a mission brief
 * (implement-all-prds.md:132); no workflow script truncates and no hook
 * inspects a completion payload.
 *
 * INTENDED RED STATE: AC-ORCH-08c fails on discovery — no completion-payload
 * cap component is registered anywhere in the plugin's hook set, so there is
 * nothing to pass a small payload through unchanged.
 *
 * AC encoded here (unit slice): AC-ORCH-08c. (08a/08b/08d are
 * integration-routed per the test strategy.)
 */

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  loadHooksConfig,
  entriesForEvent,
  runGuard,
  hookEvent,
} = require('./helpers.cjs');

/**
 * Discovery: the completion-payload cap hook. It must be registered on a
 * completion-side lifecycle event — PostToolUse, SubagentStop, or Stop.
 * @returns {Array<{event: string, command: string}>}
 */
function findPayloadCapHooks() {
  const config = loadHooksConfig();
  const out = [];
  for (const evtName of ['PostToolUse', 'SubagentStop', 'Stop']) {
    for (const entry of entriesForEvent(config, evtName)) {
      for (const h of entry.hooks || []) {
        out.push({ event: evtName, command: h.command });
      }
    }
  }
  return out;
}

test('AC-ORCH-08c: a 9-line completion payload passes through the payload-cap layer unchanged — no truncation marker, no detail path', () => {
  const capHooks = findPayloadCapHooks();
  assert.ok(
    capHooks.length > 0,
    'MISSING CONTROL [root cause H, ssbd-ja5d]: no PostToolUse/SubagentStop/Stop hook is ' +
      'registered in agent-teams-workforce/hooks/hooks.json to cap completion payloads. ' +
      'A workflow completion returns its full payload into the orchestrator context by ' +
      'construction, and the 15-line rule is mission prose only (REQ-ORCH-08).',
  );

  const nineLines = Array.from({ length: 9 }, (_, i) => `verdict line ${i + 1}`).join('\n');
  const evt = {
    ...hookEvent({ toolName: 'Workflow', toolInput: { name: 'deploy', args: {} } }),
    hook_event_name: 'PostToolUse',
    tool_response: nineLines,
  };

  for (const h of capHooks) {
    const r = runGuard(h.command, evt);
    assert.equal(r.status, 0, `payload-cap hook on ${h.event} must exit 0 for a compliant payload`);
    const body = r.stdout;
    assert.ok(
      !/truncat/i.test(body) && !/full detail at/i.test(body),
      'AC-ORCH-08c: a 9-line payload must enter the context unchanged — no truncation marker ' +
        `and no appended detail path; hook emitted: ${body}`,
    );
  }
});
