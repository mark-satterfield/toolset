'use strict';

/**
 * ssbd-ja5d / REQ-ORCH-03 — "the producer may not be the verifier": an
 * orchestrator session that produced an artifact must be blocked (exit 2)
 * from inspecting that artifact's content via Bash.
 *
 * Threat model entry: root cause (C) "THE BASH GATE'S PATTERN LIST OMITS
 * SELF-VERIFICATION ENTIRELY" — pre-tool-diagnostic-command-gate.cjs:20-35
 * enumerates linter/test binaries only; git log/diff/show and curl match
 * nothing, and prevent-bash-tool-misuse.cjs:101 whitelists `git ... | grep`.
 *
 * Session-production state fixture: the GIVEN "has already issued a
 * successful Edit against P in this same session" is supplied through the
 * transcript_path field of the hook input (a real field of every hook event),
 * pointing at a JSONL transcript containing the prior successful Edit. If the
 * implementation keys on a different session-state mechanism, extend the
 * fixture in helpers.cjs — do not weaken these assertions.
 *
 * INTENDED RED STATE: AC-ORCH-03b fails because no registered Bash guard
 * blocks any of the three git content-inspection commands (all exit 0).
 * AC-ORCH-03f is a determinism/allow pin that passes today.
 *
 * ACs encoded here (unit slice): AC-ORCH-03b, AC-ORCH-03f.
 * (03a/03c/03d/03e are integration-routed per the test strategy.)
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
  writeTranscriptWithPriorEdit,
  writeTranscriptWithoutEdits,
} = require('./helpers.cjs');

/** @returns {Array<{matcher: string, command: string}>} all Bash-matching PreToolUse guards */
function requireBashGuards() {
  const guards = guardsMatchingTool('Bash');
  assert.ok(
    guards.length > 0,
    'harness precondition: hooks.json must register at least one PreToolUse guard for Bash',
  );
  return guards;
}

test('AC-ORCH-03b: after this session edited P, `git diff -- P`, `git log -p -- P`, and `git show HEAD -- P` are each blocked with exit 2', () => {
  const dir = mkFixtureDir('ac03b');
  try {
    const produced = writeProbe(dir, 'handler.py', 'SENTINEL_ORIGINAL');
    const transcriptPath = writeTranscriptWithPriorEdit(dir, produced);
    const guards = requireBashGuards();
    const commands = [
      `git diff -- ${produced}`,
      `git log -p -- ${produced}`,
      `git show HEAD -- ${produced}`,
    ];
    for (const command of commands) {
      const evt = hookEvent({
        toolName: 'Bash',
        toolInput: { command },
        transcriptPath,
      });
      const outcomes = guards.map((g) => ({ guard: g, result: runGuard(g.command, evt) }));
      assert.ok(
        outcomes.some((o) => o.result.status === 2),
        `MISSING CONTROL [root cause C, ssbd-ja5d]: orchestrator self-verification command ` +
          `"${command}" (issued after this session produced ${produced}) must be denied by a ` +
          `Bash PreToolUse guard exiting 2; observed exit codes: ` +
          `[${outcomes.map((o) => `${o.guard.matcher}:${o.result.status}`).join(', ')}]. ` +
          `No notion of "the producer may not be the verifier" exists in the hook layer (REQ-ORCH-03).`,
      );
    }
  } finally {
    rmFixtureDir(dir);
  }
});

test('AC-ORCH-03f (pin): with no artifact produced this session, `git show HEAD` gets the same deterministic allow on every run', () => {
  const dir = mkFixtureDir('ac03f');
  try {
    const transcriptPath = writeTranscriptWithoutEdits(dir);
    const evt = hookEvent({
      toolName: 'Bash',
      toolInput: { command: 'git show HEAD' },
      transcriptPath,
    });
    const payload = JSON.stringify(evt);
    for (const g of requireBashGuards()) {
      const first = runGuard(g.command, payload);
      const second = runGuard(g.command, payload);
      assert.equal(
        first.status,
        second.status,
        `AC-ORCH-03f: guard (matcher "${g.matcher}") must be deterministic for identical input`,
      );
      assert.equal(
        first.status,
        0,
        `AC-ORCH-03f [matrix M-23]: with no prior Write/Edit in this session, ` +
          `"git show HEAD" must be allowed (exit 0) — the gate keys on whether this session ` +
          `produced the artifact, not on the binary name; stderr: ${first.stderr}`,
      );
      assert.equal(first.stdout, second.stdout, 'stdout must be identical across runs');
    }
  } finally {
    rmFixtureDir(dir);
  }
});
