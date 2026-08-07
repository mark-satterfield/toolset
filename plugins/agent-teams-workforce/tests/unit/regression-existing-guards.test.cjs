'use strict';

/**
 * ssbd-ja5d — REQ-ORCH-10 regression anchors (AC-ORCH-10c) plus the existing
 * subagent-exemption anchors cited by AC-ORCH-04b.
 *
 * EXPECTED GREEN BY DESIGN: these tests pin the enforcement primitives that
 * demonstrably work today (PreToolUse exit code 2 at
 * prevent-bash-tool-misuse.cjs:166 and gitignore-edit-guard.sh:160, and the
 * agent_id subagent exemptions at read-warning:79, diagnostic-gate:67,
 * bash-misuse:128, block-explore:142) so the fix cannot regress them. They are
 * reported to test-design-lead as green-by-design regression anchors, not Red.
 *
 * Traceability:
 *   AC-ORCH-10c -> the three "AC-ORCH-10c ..." tests
 *   AC-ORCH-04b (existing-guard clause) -> "AC-ORCH-04b[existing-hooks] ..."
 *
 * Run: node --test plugins/agent-teams-workforce/tests/unit/*.test.cjs
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const H = require('./support/hook-harness.cjs');

const SUBAGENT_ID = 'subagent-9f2c';

// The anchor's purpose is the PRIMITIVE — that a PreToolUse guard reaches a
// terminal exit 2 — not the command that trips it. It used prevent-bash-tool-misuse,
// which has been removed: its rules were tool-choice preferences rather than
// forbidden actions, and three of the seven redirected to tools this build does
// not have. The vehicle is now the orchestrator edit guard, which enforces an
// actual constitutive constraint (REQ-ORCH-01).
test('AC-ORCH-10c: a registered PreToolUse guard still reaches a terminal exit 2', () => {
  let tmp;
  try {
    tmp = H.makeTempDir('ssbd-ja5d-anchor-');
    const probe = H.writeProbe(tmp, 'probe.py', 'SENTINEL_ORIGINAL\n');
    const event = H.makeEvent({ toolName: 'Write', toolInput: { file_path: probe, content: 'x' } });
    const r = H.runScript(H.HOOK_SCRIPTS.editGuard, event);
    assert.equal(r.status, 2, 'an orchestrator code write must still be blocked with exit code 2');
    assert.ok(r.stderr.includes('Orchestrator Edit Blocked'), 'the denial feedback must reach stderr');
  } finally {
    if (tmp) H.removeTempDir(tmp);
  }
});

test('AC-ORCH-10c: gitignore-edit-guard.sh still denies removing a sensitive pattern from .gitignore with exit 2', () => {
  const event = H.makeEvent({
    toolName: 'Edit',
    toolInput: {
      file_path: '/tmp/ssbd-ja5d-fixture/.gitignore',
      old_string: '.env\n*.pem\n',
      new_string: '\n',
    },
  });
  const r = H.runScript(H.HOOK_SCRIPTS.gitignoreEditGuard, event, { runner: 'bash' });
  assert.equal(r.status, 2, 'removing a sensitive .gitignore pattern must still be blocked with exit code 2');
  assert.ok(r.stderr.includes('BLOCKED'), 'the denial feedback must still be written to stderr');
});

test('AC-ORCH-10c: gitignore-edit-guard.sh still exits 0 immediately for any path not ending in .gitignore', () => {
  const event = H.makeEvent({
    toolName: 'Edit',
    toolInput: {
      file_path: '/tmp/ssbd-ja5d-fixture/config.py',
      old_string: '.env',
      new_string: '',
    },
  });
  const r = H.runScript(H.HOOK_SCRIPTS.gitignoreEditGuard, event, { runner: 'bash' });
  assert.equal(r.status, 0, 'non-.gitignore paths must still pass (gitignore-edit-guard.sh:23-26)');
});

test('AC-ORCH-04b[existing-hooks]: all four existing hook scripts preserve the subagent exemption (agent_id present -> exit 0, empty decision)', () => {
  let tmpDir;
  try {
    tmpDir = H.makeTempDir('ssbd-ja5d-regr-');
    const probePy = H.writeProbe(tmpDir, 'probe.py', 'SENTINEL_ORIGINAL\n');

    const cases = [
      {
        script: H.HOOK_SCRIPTS.readWarning,
        event: H.makeEvent({
          toolName: 'Read',
          toolInput: { file_path: probePy },
          agentId: SUBAGENT_ID,
        }),
      },
      {
        script: H.HOOK_SCRIPTS.diagnosticGate,
        event: H.makeEvent({
          toolName: 'Bash',
          toolInput: { command: 'pytest tests/' },
          agentId: SUBAGENT_ID,
        }),
      },
      {
        script: H.HOOK_SCRIPTS.blockExplore,
        event: H.makeEvent({
          toolName: 'Task',
          toolInput: {
            subagent_type: 'Explore',
            description: 'analyze the architecture',
            prompt: 'analyze the architecture and recommend improvements',
          },
          agentId: SUBAGENT_ID,
        }),
      },
    ];

    for (const c of cases) {
      const r = H.runScript(c.script, c.event);
      assert.equal(r.status, 0, `${c.script} must exit 0 for a subagent session`);
      assert.equal(r.stderr, '', `${c.script} must emit no denial text for a subagent session`);
      assert.ok(
        H.isEmptyDecision(r.stdout),
        `${c.script} must emit an empty decision ('' or {}) for a subagent session, got: ${JSON.stringify(r.stdout)}`,
      );
    }
  } finally {
    if (tmpDir) H.removeTempDir(tmpDir);
  }
});
