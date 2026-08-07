'use strict';

/**
 * What prevent-bash-tool-misuse.cjs is FOR, and what it is not for.
 *
 * The rule it enforces is narrow: commands that read file CONTENTS into context
 * should use Read/Grep/Glob, which handle large files, binaries, and encoding
 * properly. That is a real correctness argument.
 *
 * It is not a general prohibition on shell utilities. `ls` was once swept in by
 * analogy and blocked; the rule was wrong on its own terms — nothing about a
 * directory listing has an encoding to mishandle, Glob answers a different
 * question ("which paths match" vs "what is in here"), the exemption permitted
 * the verbose `ls -la` while blocking bare `ls`, and a leading `echo` defeated
 * it outright. These tests pin both halves so the rule keeps its actual scope.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const H = require('./support/hook-harness.cjs');

/** Runs the guard against an orchestrator-session Bash call. */
function run(command) {
  return H.runScript(
    H.HOOK_SCRIPTS.bashMisuse,
    H.makeEvent({ toolName: 'Bash', toolInput: { command } }),
  );
}

// ── Directory listing is not misuse ───────────────────────────────────────────

for (const command of ['ls', 'ls hooks/', 'ls -la', 'ls -R src', 'ls -lh /tmp']) {
  test(`\`${command}\` is permitted — listing a directory reads no file contents`, () => {
    const r = run(command);
    assert.equal(
      r.status,
      0,
      `blocked \`${command}\`. Glob answers "which paths match this pattern"; ls answers "what is in this directory", including subdirectories and, with -l, sizes and symlink targets. They are different questions.`,
    );
    assert.equal(r.stderr, '', 'a permitted command must produce no denial text');
  });
}

test('the ls exemption cannot be reintroduced backwards — bare ls is no costlier than ls -la', () => {
  // The old rule blocked `ls` while exempting `ls -la` as "human consumption",
  // permitting the form with several times more output in a hook set whose stated
  // purpose is protecting the context window.
  assert.equal(run('ls').status, run('ls -la').status, 'ls and ls -la must be treated alike');
});

// ── Content-reading commands are still redirected ─────────────────────────────

const CONTENT_READS = [
  ['grep -r "needle" .', 'Grep'],
  ['cat config.py', 'Read'],
  ['head -20 config.py', 'Read'],
  ['tail -20 config.py', 'Read'],
  ["sed -n '10,20p' config.py", 'Read'],
  ['find . -name "*.ts"', 'Glob'],
];

for (const [command, redirect] of CONTENT_READS) {
  test(`\`${command}\` is still redirected to ${redirect}`, () => {
    const r = run(command);
    assert.equal(r.status, 2, `removing the ls rule must not weaken the content-reading rules`);
    assert.match(r.stderr, /Bash Tool Misuse Prevented/);
  });
}

test('pipelines are still legitimate shell use', () => {
  for (const command of ['git log --oneline | grep fix', 'gh pr list | head -5']) {
    assert.equal(run(command).status, 0, `pipeline blocked: ${command}`);
  }
});

test('the subagent exemption is unaffected', () => {
  const r = H.runScript(
    H.HOOK_SCRIPTS.bashMisuse,
    H.makeEvent({ toolName: 'Bash', toolInput: { command: 'grep -r x .' }, agentId: 'subagent-1' }),
  );
  assert.equal(r.status, 0);
  assert.equal(r.stderr, '');
});
