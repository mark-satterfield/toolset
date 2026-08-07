'use strict';

/**
 * ssbd-ja5d — REQ-ORCH-03 (root cause C): "the producer may not be the
 * verifier". An orchestrator session that produced an artifact must be
 * mechanically blocked (exit 2) from inspecting that artifact via git, while
 * sessions that produced nothing keep normal git access.
 *
 * Session-production state is conveyed to the guard through the hook input's
 * machine-observable fields — here `transcript_path`, pointing at the session
 * transcript (JSONL) which records the prior successful Edit tool_use. See the
 * Assumptions section of the handoff report: transcript_path is the only
 * session-history channel present in the PreToolUse hook input contract.
 *
 * Traceability:
 *   AC-ORCH-03b (decision table) -> "AC-ORCH-03b[<cmd>]: ..."
 *   AC-ORCH-03f                  -> "AC-ORCH-03f: ..."
 *
 * Run: node --test plugins/agent-teams-workforce/tests/unit/*.test.cjs
 *
 * Intended RED reason: no registered Bash guard implements the
 * producer-may-not-verify rule. pre-tool-diagnostic-command-gate.cjs matches
 * only its thirteen linter/test binaries (lines 20-35) and exits 0 for git;
 * prevent-bash-tool-misuse.cjs whitelists `git ... | grep` (line 101) and
 * blocks only grep/find/ls/cat/head/tail/sed. Every git self-inspection
 * command passes with exit 0 today.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const H = require('./support/hook-harness.cjs');

let tmpDir;
let producedPath;
let producedTranscript;
let cleanTranscript;

test.before(() => {
  tmpDir = H.makeTempDir('ssbd-ja5d-verify-');
  producedPath = H.writeProbe(tmpDir, 'artifact.py', 'SENTINEL_EDITED\n');
  producedTranscript = H.writeTranscript(tmpDir, 'transcript-produced.jsonl', producedPath);
  cleanTranscript = H.writeTranscript(tmpDir, 'transcript-clean.jsonl');
});

test.after(() => {
  H.removeTempDir(tmpDir);
});

function runAllBashGuards(command, transcriptPath, extra = {}) {
  const guards = H.resolveGuardsForTool('PreToolUse', 'Bash');
  assert.ok(guards.length > 0, 'at least one PreToolUse Bash guard must be registered');
  return guards.map((g) => ({
    guard: g,
    result: H.runGuard(
      g,
      H.makeEvent({
        toolName: 'Bash',
        toolInput: { command },
        transcriptPath,
        ...extra,
      }),
    ),
  }));
}

const SELF_INSPECTION_COMMANDS = [
  (p) => `git diff -- ${p}`,
  (p) => `git log -p -- ${p}`,
  (p) => `git show HEAD -- ${p}`,
];

for (const build of SELF_INSPECTION_COMMANDS) {
  const cmdTemplate = build('<P>');
  test(`AC-ORCH-03b[${cmdTemplate}]: orchestrator inspecting an artifact it produced this session is denied with exit 2`, () => {
    const command = build(producedPath);
    const runs = runAllBashGuards(command, producedTranscript);
    assert.ok(
      runs.some(({ result }) => result.status === 2),
      `AC-ORCH-03b: no registered Bash guard denied "${command}" with exit 2 even though this session's transcript records a successful Edit of ${producedPath} — the producer verified its own output unopposed (root cause C; statuses: ${runs.map(({ result }) => result.status).join(', ')})`,
    );
  });
}

test('AC-ORCH-03f: with no artifact produced this session, `git show HEAD` is allowed deterministically — and the same gate denies it once the session has produced the artifact', () => {
  // Part 1 — clean session: allowed, and deterministic across repeat runs.
  const first = runAllBashGuards('git show HEAD', cleanTranscript);
  const second = runAllBashGuards('git show HEAD', cleanTranscript);
  for (let i = 0; i < first.length; i += 1) {
    const a = first[i];
    const b = second[i];
    assert.equal(
      a.result.status,
      0,
      `AC-ORCH-03f: guard ${a.guard.scriptPath} must allow \`git show HEAD\` (exit 0) when this session has produced no artifact`,
    );
    assert.equal(
      b.result.status,
      a.result.status,
      `AC-ORCH-03f: guard ${a.guard.scriptPath} gave different exit codes on identical clean-session input — the outcome is not deterministic`,
    );
    assert.equal(
      b.result.stdout,
      a.result.stdout,
      `AC-ORCH-03f: guard ${a.guard.scriptPath} gave different stdout on identical clean-session input`,
    );
  }

  // Part 2 — the demonstration clause: the gate must key on whether THIS
  // session produced the artifact under inspection, not merely on the binary
  // name. Same binary (git), same subcommand family, but a session transcript
  // recording production of the target: now it must be denied.
  const produced = runAllBashGuards(`git show HEAD -- ${producedPath}`, producedTranscript);
  assert.ok(
    produced.some(({ result }) => result.status === 2),
    `AC-ORCH-03f: no registered Bash guard distinguishes the produced-artifact session from the clean session for \`git show HEAD -- ${producedPath}\` — the gate does not key on session production state (root cause C; statuses: ${produced.map(({ result }) => result.status).join(', ')})`,
  );
});
