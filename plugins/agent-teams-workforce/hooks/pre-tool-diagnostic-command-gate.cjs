#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — REQ-ORCH-04 category 2 (ssbd-ja5d, root causes B + C).
 *
 * The rule is "the producer may not be the verifier", not "the orchestrator may
 * not run tests". Those are different, and conflating them cost more than it
 * saved: blocking every diagnostic by binary name meant the orchestrator could
 * not spot-check a claim an agent had made, which pushes it toward trusting
 * reports it should be able to check.
 *
 * So the gate now keys on session state, exactly as the self-verification gate
 * does. Running the suite when this session has written nothing is a baseline
 * check and is allowed. Running it after this session produced code is the
 * producer grading its own work, and is denied.
 *
 * Output volume is handled where it belongs — by the completion payload cap —
 * rather than by refusing to let the command run at all.
 *
 * Decision order:
 *   1. unparseable input        -> exit 0 (other Bash guards still run)
 *   2. subagent session         -> exit 0
 *   3. non-Bash tool            -> exit 0
 *   4. no diagnostic match      -> exit 0
 *   5. session produced nothing -> exit 0  (baseline check)
 *   6. session produced code    -> exit 2  (self-verification)
 */

const fs = require('node:fs');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');
const { producedPaths } = require('./lib/session-production.cjs');

/**
 * Diagnostic binaries and subcommands. Each entry is anchored at a command
 * position (start of line, or after ; && || | newline or an opening paren).
 */
const DIAGNOSTIC_PATTERNS = [
  /(?:^|[;&|\n(])\s*ty\s+check\b/,
  /(?:^|[;&|\n(])\s*ruff\s+check\b/,
  /(?:^|[;&|\n(])\s*pyright\b/,
  /(?:^|[;&|\n(])\s*basedpyright\b/,
  /(?:^|[;&|\n(])\s*pylint\b/,
  /(?:^|[;&|\n(])\s*pytest\b/,
  /(?:^|[;&|\n(])\s*mypy\b/,
  /(?:^|[;&|\n(])\s*pre-commit\s+run\b/,
  /(?:^|[;&|\n(])\s*prek\s+run\b/,
  /(?:^|[;&|\n(])\s*eslint\b/,
  /(?:^|[;&|\n(])\s*tsc\b[^;&|\n]*--noEmit/,
  /(?:^|[;&|\n(])\s*cargo\s+check\b/,
  /(?:^|[;&|\n(])\s*cargo\s+clippy\b/,
  /(?:^|[;&|\n(])\s*go\s+vet\b/,
];

/**
 * Strips quoted substrings so a binary name appearing as a search target or a
 * string literal is not read as an invocation.
 */
function stripQuotedSpans(text) {
  return text
    .replace(/`[^`]*`/g, ' ')
    .replace(/'[^']*'/g, ' ')
    .replace(/"[^"]*"/g, ' ');
}

/** Returns the matched diagnostic invocation, or null. */
function matchesDiagnosticCommand(command) {
  if (!command) return null;
  const stripped = stripQuotedSpans(command);
  for (const pattern of DIAGNOSTIC_PATTERNS) {
    const match = stripped.match(pattern);
    if (match) return match[0].trim().replace(/^[;&|(]\s*/, '');
  }
  return null;
}

/** Reads all of stdin synchronously; returns '' when unreadable. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

function main() {
  const raw = readStdin();
  if (!raw.trim()) {
    process.exit(0);
  }

  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  // Subagents run diagnostics — that is their job.
  if (data.agent_id) {
    process.exit(0);
  }

  // Out of scope in the monorepo that builds this plugin.
  if (!guardsApplyHere(data)) {
    process.exit(0);
  }

  if ((data.tool_name || '') !== 'Bash') {
    process.exit(0);
  }

  const command = data.tool_input?.command || '';
  const matched = matchesDiagnosticCommand(command);
  if (!matched) {
    process.exit(0);
  }

  // A diagnostic run by a session that has produced nothing is a baseline check,
  // not self-verification. Let it through.
  const produced = producedPaths(String(data.transcript_path ?? ''));
  if (produced.length === 0) {
    process.exit(0);
  }

  process.stderr.write(
    `${[
      '--- Self-Verification Blocked ---',
      '',
      `Matched: ${matched}`,
      `Command: ${command.substring(0, 200)}`,
      '',
      `This session has produced ${produced.length} artifact(s), including:`,
      ...produced.slice(0, 3).map((p) => `  ${p}`),
      '',
      'Running the suite over code this session wrote is the producer grading its',
      'own work. A diagnostic run by a session that has written nothing is a',
      'baseline check and is not blocked.',
      '',
      'Delegate the run and take the verdict:',
      '  - tdd-green / tdd-refactor already run the suite and report Green',
      '  - integration-testing-lead owns suite execution and result aggregation',
      '  - flaky-test-detector confirms intermittent failures',
      '  - root-cause-analyst classifies a failure and names where it escalates',
      '',
      'A delegated run costs nothing from this window: the agent reads the output',
      'in its own context and returns the outcome.',
      '',
      'Rule source: REQ-ORCH-04 category 2 (ssbd-ja5d) — diagnostics are delegated',
      '--- End ---',
    ].join('\n')}\n`,
  );
  process.exit(2);
}

main();
