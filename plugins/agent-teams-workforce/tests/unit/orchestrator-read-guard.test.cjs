'use strict';

/**
 * ssbd-ja5d — REQ-ORCH-02 (root cause B): the source-file read guard must make
 * a machine decision; it must not grant exemptions the actor attests to itself.
 *
 * Traceability:
 *   AC-ORCH-02a -> "AC-ORCH-02a: read guard emits no self-attested exemption"
 *   AC-ORCH-02b -> "AC-ORCH-02b: read guard decision is deterministic ..."   [regression anchor — expected green]
 *   AC-ORCH-02c -> "AC-ORCH-02c: read guard decision derives only from machine-observable inputs"
 *
 * Run: node --test plugins/agent-teams-workforce/tests/unit/*.test.cjs
 *
 * Intended RED reason (02a, 02c): pre-tool-orchestrator-read-warning.cjs today
 * emits additionalContext containing "1. Will you Edit or Write this file in
 * this same turn? If YES: proceed." (lines 114-115) and always exits 0 —
 * the exemption predicate is the actor's own future intent.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const H = require('./support/hook-harness.cjs');

let tmpDir;
let probePy;

test.before(() => {
  tmpDir = H.makeTempDir('ssbd-ja5d-read-');
  probePy = H.writeProbe(tmpDir, 'probe.py', 'SENTINEL_ORIGINAL\n');
});

test.after(() => {
  H.removeTempDir(tmpDir);
});

test('AC-ORCH-02a: read guard emits no self-attested exemption for an orchestrator source read', () => {
  const guards = H.resolveGuardsForTool('PreToolUse', 'Read');
  assert.ok(
    guards.length > 0,
    `AC-ORCH-02a: no PreToolUse guard registered in ${H.HOOKS_JSON_PATH} matches tool "Read"`,
  );

  const event = H.makeEvent({ toolName: 'Read', toolInput: { file_path: probePy } });
  for (const guard of guards) {
    const r = H.runGuard(guard, event);
    const combined = `${r.stdout}\n${r.stderr}`;
    for (const marker of H.INTENT_EXEMPTION_MARKERS) {
      assert.ok(
        !combined.includes(marker),
        `AC-ORCH-02a: guard ${guard.scriptPath} granted a self-attested exemption — emitted text contains ${JSON.stringify(marker)}. An exemption whose stated condition is an action the actor has not yet taken (and only the actor can attest to) is forbidden (root cause B).`,
      );
    }
  }
});

// Regression anchor: this property already holds for the current guard and must
// keep holding after the fix. Reported to test-design-lead as green-by-design.
test('AC-ORCH-02b: read guard decision is deterministic — identical stdin gives byte-identical stdout and identical exit codes', () => {
  const guards = H.resolveGuardsForTool('PreToolUse', 'Read');
  assert.ok(guards.length > 0, 'a PreToolUse guard must be registered for Read');

  const event = H.makeEvent({ toolName: 'Read', toolInput: { file_path: probePy } });
  for (const guard of guards) {
    const first = H.runGuard(guard, event);
    const second = H.runGuard(guard, event);
    assert.equal(
      second.status,
      first.status,
      `AC-ORCH-02b: guard ${guard.scriptPath} returned different exit codes for byte-identical input`,
    );
    assert.equal(
      second.stdout,
      first.stdout,
      `AC-ORCH-02b: guard ${guard.scriptPath} produced different stdout for byte-identical input — the decision depends on state the hook cannot observe`,
    );
  }
});

test('AC-ORCH-02c: read guard decision derives only from machine-observable inputs — no exemption deferred to actor intent', () => {
  const guards = H.resolveGuardsForTool('PreToolUse', 'Read');
  assert.ok(guards.length > 0, 'a PreToolUse guard must be registered for Read');

  const event = H.makeEvent({ toolName: 'Read', toolInput: { file_path: probePy } });
  for (const guard of guards) {
    // Same stdin, two different process working directories: the decision must
    // be a function of the supplied hook-input fields plus the on-disk state
    // they reference — nothing ambient.
    const fromTmp = H.runGuard(guard, event, { cwd: os.tmpdir() });
    const fromRoot = H.runGuard(guard, event, { cwd: H.PLUGIN_ROOT });
    assert.equal(
      fromRoot.status,
      fromTmp.status,
      `AC-ORCH-02c: guard ${guard.scriptPath} decision changed with ambient process state (cwd)`,
    );
    assert.equal(
      fromRoot.stdout,
      fromTmp.stdout,
      `AC-ORCH-02c: guard ${guard.scriptPath} output changed with ambient process state (cwd)`,
    );

    // The rendered decision must be terminal and machine-evaluated: a deny
    // (exit 2), or an allow (exit 0) whose emitted payload contains no
    // exemption conditioned on the actor's unobservable future action.
    if (fromRoot.status === 0) {
      let context = '';
      const trimmed = fromRoot.stdout.trim();
      if (trimmed) {
        const payload = JSON.parse(trimmed);
        context = payload?.hookSpecificOutput?.additionalContext ?? '';
      }
      for (const marker of H.INTENT_EXEMPTION_MARKERS) {
        assert.ok(
          !context.includes(marker),
          `AC-ORCH-02c: guard ${guard.scriptPath} allowed the call while deferring the real decision to the actor (found ${JSON.stringify(marker)} in additionalContext). Every input to the exemption evaluation must be machine-observable (root cause B).`,
        );
      }
    } else {
      assert.equal(
        fromRoot.status,
        2,
        `AC-ORCH-02c: guard ${guard.scriptPath} terminated with a status that is neither allow (0) nor deny (2)`,
      );
    }
  }

  // The probe file itself must be untouched by evaluating the guard.
  assert.equal(fs.readFileSync(probePy, 'utf8'), 'SENTINEL_ORIGINAL\n');
});
