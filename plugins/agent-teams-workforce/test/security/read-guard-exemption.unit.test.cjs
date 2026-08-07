'use strict';

/**
 * ssbd-ja5d / REQ-ORCH-02 — the source-file read guard must not grant
 * exemptions conditioned on the actor's own unobservable future intent.
 *
 * Threat model entry: root cause (B) "THE READ GUARD IS ADVISORY BY DESIGN,
 * WITH A SELF-GRANTED EXEMPTION" — pre-tool-orchestrator-read-warning.cjs:115
 * states verbatim: "1. Will you Edit or Write this file in this same turn?
 * If YES: proceed." The predicate is the actor's own self-declared intent.
 *
 * INTENDED RED STATE: AC-ORCH-02a and AC-ORCH-02c fail because the guard's
 * emitted text today contains the intent-conditioned exemption and an
 * interrogative addressed to the actor ("ask yourself"). AC-ORCH-02b is a
 * determinism pin that passes today and must keep passing after the fix.
 *
 * ACs encoded here: AC-ORCH-02a, AC-ORCH-02b, AC-ORCH-02c.
 */

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  guardsMatchingTool,
  runGuard,
  hookEvent,
  mkFixtureDir,
  rmFixtureDir,
  writeProbe,
} = require('./helpers.cjs');

/**
 * Exemption clauses whose stated condition is an action the actor has not yet
 * taken and only the actor can attest to (AC-ORCH-02a).
 */
const UNOBSERVABLE_EXEMPTION_SUBSTRINGS = [
  'Will you Edit or Write this file in this same turn',
  'If YES: proceed',
  'proceed if',
  'If you just Edited',
];

/** Interrogatives that delegate the decision to the actor (AC-ORCH-02c). */
const SELF_ATTESTATION_SUBSTRINGS = ['ask yourself', 'Will you'];

/** @returns {Array<{matcher: string, command: string}>} guards registered for Read */
function requireReadGuards() {
  const guards = guardsMatchingTool('Read');
  assert.ok(
    guards.length > 0,
    'harness precondition: hooks.json must register at least one PreToolUse guard for Read ' +
      '(pre-tool-orchestrator-read-warning.cjs is registered today under matcher Read|Grep)',
  );
  return guards;
}

test('AC-ORCH-02a: read-guard output for an orchestrator .py read contains no exemption keyed on self-declared future intent', () => {
  const dir = mkFixtureDir('ac02a');
  try {
    const probe = writeProbe(dir, 'module.py', 'VALUE = 1\n');
    const evt = hookEvent({ toolName: 'Read', toolInput: { file_path: probe } });
    for (const g of requireReadGuards()) {
      const { stdout, stderr } = runGuard(g.command, evt);
      const emitted = `${stdout}\n${stderr}`;
      for (const clause of UNOBSERVABLE_EXEMPTION_SUBSTRINGS) {
        assert.ok(
          !emitted.includes(clause),
          `AC-ORCH-02a [root cause B]: guard (matcher "${g.matcher}") emitted a self-granted ` +
            `exemption conditioned on unobservable intent — forbidden substring "${clause}" ` +
            `found in its output.`,
        );
      }
    }
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-02b (pin): two byte-identical orchestrator Read events produce byte-identical stdout and identical exit codes', () => {
  const dir = mkFixtureDir('ac02b');
  try {
    const probe = writeProbe(dir, 'module.py', 'VALUE = 1\n');
    const evt = hookEvent({ toolName: 'Read', toolInput: { file_path: probe } });
    const payload = JSON.stringify(evt);
    for (const g of requireReadGuards()) {
      const first = runGuard(g.command, payload);
      const second = runGuard(g.command, payload);
      assert.equal(
        first.stdout,
        second.stdout,
        `AC-ORCH-02b: guard (matcher "${g.matcher}") stdout must be deterministic for identical input`,
      );
      assert.equal(
        first.status,
        second.status,
        `AC-ORCH-02b: guard (matcher "${g.matcher}") exit code must be deterministic for identical input`,
      );
    }
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-02c: every input to the read-guard decision is machine-observable — no self-attestation, and extra unobservable fields cannot change the outcome', () => {
  const dir = mkFixtureDir('ac02c');
  try {
    const probe = writeProbe(dir, 'module.py', 'VALUE = 1\n');
    const baseEvt = hookEvent({ toolName: 'Read', toolInput: { file_path: probe } });
    // A hypothetical self-declared-intent field must be irrelevant: the guard's
    // decision may depend only on tool_name, tool_input, agent_id, cwd,
    // session_id plus on-disk state those fields reference.
    const intentEvt = { ...baseEvt, declared_intent: 'I will edit this file next turn' };
    for (const g of requireReadGuards()) {
      const base = runGuard(g.command, baseEvt);
      const withIntent = runGuard(g.command, intentEvt);
      assert.equal(
        base.stdout,
        withIntent.stdout,
        `AC-ORCH-02c: guard (matcher "${g.matcher}") decision must not vary with a ` +
          `self-declared intent field — only machine-observable inputs may participate`,
      );
      assert.equal(base.status, withIntent.status, 'exit code must not vary with declared intent');

      const emitted = `${base.stdout}\n${base.stderr}`;
      for (const clause of SELF_ATTESTATION_SUBSTRINGS) {
        assert.ok(
          !emitted.includes(clause),
          `AC-ORCH-02c [root cause B]: guard (matcher "${g.matcher}") delegates its decision to ` +
            `the actor — forbidden self-attestation phrase "${clause}" found in its output. ` +
            `The exemption evaluation must be machine-observable, not a question to the actor.`,
        );
      }
    }
  } finally {
    rmFixtureDir(dir);
  }
});
