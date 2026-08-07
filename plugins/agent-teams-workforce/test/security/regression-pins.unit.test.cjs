'use strict';

/**
 * ssbd-ja5d / AC-ORCH-10c — regression pins on the two enforcement primitives
 * that demonstrably work today. The fix for ssbd-ja5d must not break them.
 *
 *   - prevent-bash-tool-misuse.cjs:166 — exit 2 on a bare `grep` Bash call in
 *     an orchestrator session.
 *   - gitignore-edit-guard.sh:160 — exit 2 on an Edit that strips a sensitive
 *     pattern from a .gitignore; :23-26 — immediate exit 0 for any path not
 *     ending in .gitignore.
 *
 * EXPECTED STATE TODAY: GREEN. These pins pass now and must keep passing —
 * they prove the exit-code-2 primitive works, which is exactly what root
 * cause analysis says is applied to none of the four forbidden actions.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
  GITIGNORE_GUARDIAN_ROOT,
  guardsMatchingTool,
  runGuard,
  hookEvent,
} = require('./helpers.cjs');

const GITIGNORE_GUARD_CMD = 'bash ${CLAUDE_PLUGIN_ROOT}/hooks/gitignore-edit-guard.sh';

test('AC-ORCH-10c pin: bare `grep` at command start in an orchestrator session is blocked with exit 2 by prevent-bash-tool-misuse.cjs', () => {
  const guards = guardsMatchingTool('Bash');
  assert.ok(guards.length > 0, 'harness precondition: Bash guards registered');
  const evt = hookEvent({ toolName: 'Bash', toolInput: { command: 'grep -r TODO src/' } });
  const outcomes = guards.map((g) => ({ g, r: runGuard(g.command, evt) }));
  const blocking = outcomes.filter((o) => o.r.status === 2);
  assert.ok(
    blocking.length > 0,
    `AC-ORCH-10c: the working primitive at prevent-bash-tool-misuse.cjs:166 must still block ` +
      `a bare grep with exit 2; observed: [${outcomes.map((o) => o.r.status).join(', ')}]`,
  );
  assert.ok(
    blocking.some((o) => /Bash Tool Misuse Prevented/.test(o.r.stderr)),
    'blocking stderr must carry the existing correction message',
  );
});

test('AC-ORCH-10c pin: gitignore-edit-guard.sh blocks (exit 2) an Edit removing a sensitive pattern from .gitignore', () => {
  const evt = hookEvent({
    toolName: 'Edit',
    toolInput: {
      file_path: path.join('/tmp', 'repo', '.gitignore'),
      old_string: '.env\n*.pem\n',
      new_string: '\n',
    },
  });
  const r = runGuard(GITIGNORE_GUARD_CMD, evt, { pluginRoot: GITIGNORE_GUARDIAN_ROOT });
  assert.equal(
    r.status,
    2,
    `AC-ORCH-10c: gitignore-edit-guard.sh:160 must still exit 2 for a sensitive-pattern ` +
      `removal; stderr: ${r.stderr}`,
  );
  assert.match(r.stderr, /BLOCKED: Dangerous \.gitignore modification/);
});

test('AC-ORCH-10c pin: gitignore-edit-guard.sh exits 0 immediately for any path not ending in .gitignore (lines 23-26)', () => {
  const evt = hookEvent({
    toolName: 'Edit',
    toolInput: {
      file_path: '/tmp/repo/module.py',
      old_string: 'a',
      new_string: 'b',
    },
  });
  const r = runGuard(GITIGNORE_GUARD_CMD, evt, { pluginRoot: GITIGNORE_GUARDIAN_ROOT });
  assert.equal(
    r.status,
    0,
    `AC-ORCH-10c: gitignore-edit-guard.sh must pass non-.gitignore paths straight through ` +
      `(exit 0); stderr: ${r.stderr}`,
  );
});
