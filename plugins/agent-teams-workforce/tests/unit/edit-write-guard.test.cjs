'use strict';

/**
 * ssbd-ja5d — REQ-ORCH-01 (root cause A): an orchestrator session (no
 * agent_id) must be mechanically blocked (PreToolUse exit 2) from editing
 * code, via a registered Edit|Write|MultiEdit|NotebookEdit guard.
 *
 * Traceability (per-guard decision-table cases, decomposed per test strategy):
 *   AC-ORCH-01b -> "AC-ORCH-01b[<tool>]: ..." (one row per edit tool)
 *   AC-ORCH-01d -> "AC-ORCH-01d[<ext>]: ..."  (one row per code extension)
 *   AC-ORCH-10a -> "AC-ORCH-10a: ..."          (fail-closed on bad stdin)
 *
 * Run: node --test plugins/agent-teams-workforce/tests/unit/*.test.cjs
 *
 * Intended RED reason: plugins/agent-teams-workforce/hooks/hooks.json
 * registers PreToolUse matchers "Read|Grep", "Bash", "Bash", "Agent|Task"
 * only. No registered matcher matches Edit, Write, MultiEdit, or
 * NotebookEdit — the guard these tests invoke does not exist (root cause A:
 * "NO EDIT/WRITE GUARD EXISTS"). Resolution therefore returns zero guards
 * and each row fails on the missing enforcement surface.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const H = require('./support/hook-harness.cjs');

const EDIT_TOOLS = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'];
const CODE_EXTENSIONS = ['js', 'cjs', 'mjs', 'ts', 'sh', 'py', 'toml', 'yaml'];

let tmpDir;

test.before(() => {
  tmpDir = H.makeTempDir('ssbd-ja5d-edit-');
});

test.after(() => {
  H.removeTempDir(tmpDir);
});

/** Violating tool_input for each edit-capable tool against a probe path. */
function violatingInput(toolName, probePath) {
  switch (toolName) {
    case 'Write':
      return { file_path: probePath, content: 'SENTINEL_EDITED\n' };
    case 'Edit':
      return { file_path: probePath, old_string: 'SENTINEL_ORIGINAL', new_string: 'SENTINEL_EDITED' };
    case 'MultiEdit':
      return {
        file_path: probePath,
        edits: [{ old_string: 'SENTINEL_ORIGINAL', new_string: 'SENTINEL_EDITED' }],
      };
    case 'NotebookEdit':
      return { notebook_path: probePath, file_path: probePath, new_source: 'SENTINEL_EDITED' };
    default:
      throw new Error(`no violating input defined for tool ${toolName}`);
  }
}

for (const tool of EDIT_TOOLS) {
  test(`AC-ORCH-01b[${tool}]: orchestrator ${tool} on a .py probe is denied with exit 2 by a registered guard`, () => {
    const probe = H.writeProbe(tmpDir, `probe-01b-${tool}.py`, 'SENTINEL_ORIGINAL\n');
    const guards = H.resolveGuardsForTool('PreToolUse', tool);
    assert.ok(
      guards.length > 0,
      `AC-ORCH-01b: no PreToolUse guard registered in ${H.HOOKS_JSON_PATH} matches tool "${tool}" — the orchestrator Edit/Write guard does not exist (root cause A). The orchestrator editing code is entirely unobserved.`,
    );

    const event = H.makeEvent({ toolName: tool, toolInput: violatingInput(tool, probe) });
    const results = guards.map((g) => H.runGuard(g, event));
    assert.ok(
      results.some((r) => r.status === 2),
      `AC-ORCH-01b: no registered guard denied orchestrator ${tool} of ${probe} with exit code 2 (statuses: ${results.map((r) => r.status).join(', ')})`,
    );
    const denial = results.find((r) => r.status === 2);
    assert.ok(
      denial.stderr.includes(probe),
      `AC-ORCH-01b: the blocking stderr text must name the rejected file path ${probe}`,
    );
    assert.equal(
      fs.readFileSync(probe, 'utf8'),
      'SENTINEL_ORIGINAL\n',
      'AC-ORCH-01b: probe file must be untouched after the blocked attempt',
    );
  });
}

for (const ext of CODE_EXTENSIONS) {
  test(`AC-ORCH-01d[.${ext}]: orchestrator Write to a .${ext} probe is denied with exit 2 by a registered guard`, () => {
    const probe = H.writeProbe(tmpDir, `probe-01d.${ext}`, 'SENTINEL_ORIGINAL\n');
    const guards = H.resolveGuardsForTool('PreToolUse', 'Write');
    assert.ok(
      guards.length > 0,
      `AC-ORCH-01d: no PreToolUse guard registered in ${H.HOOKS_JSON_PATH} matches tool "Write" — the orchestrator Edit/Write guard does not exist (root cause A).`,
    );

    const event = H.makeEvent({
      toolName: 'Write',
      toolInput: { file_path: probe, content: 'SENTINEL_EDITED\n' },
    });
    const results = guards.map((g) => H.runGuard(g, event));
    assert.ok(
      results.some((r) => r.status === 2),
      `AC-ORCH-01d: no registered guard denied orchestrator Write of ${probe} with exit code 2 (statuses: ${results.map((r) => r.status).join(', ')})`,
    );
    assert.equal(
      fs.readFileSync(probe, 'utf8'),
      'SENTINEL_ORIGINAL\n',
      'AC-ORCH-01d: probe file must be untouched after the blocked attempt',
    );
  });
}

test('AC-ORCH-10a: the Edit/Write guard fails closed — empty or unparseable stdin is denied with exit 2', () => {
  const guards = H.resolveGuardsForTool('PreToolUse', 'Write');
  assert.ok(
    guards.length > 0,
    `AC-ORCH-10a: no PreToolUse guard registered in ${H.HOOKS_JSON_PATH} matches tool "Write" — there is no Edit/Write guard whose fail-closed behavior can be verified (root cause A).`,
  );

  for (const guard of guards) {
    const emptyStdin = H.runGuard(guard, '');
    assert.equal(
      emptyStdin.status,
      2,
      `AC-ORCH-10a: guard ${guard.scriptPath} must exit 2 (deny) on empty stdin instead of permitting the call — the current hooks exit 0 on unparseable input (read-warning:71-74, diagnostic-gate:59-62), which fails open`,
    );

    const badJson = H.runGuard(guard, '{{{ this is not JSON');
    assert.equal(
      badJson.status,
      2,
      `AC-ORCH-10a: guard ${guard.scriptPath} must exit 2 (deny) when stdin is not parseable as JSON — a guard that cannot read its input must not permit the write`,
    );
  }
});
