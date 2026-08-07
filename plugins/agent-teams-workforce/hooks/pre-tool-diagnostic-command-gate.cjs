#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — REQ-ORCH-04 category 2 (ssbd-ja5d, root causes B + C).
 *
 * Running the project's own diagnostics is self-verification: the orchestrator
 * checks whether the work is good using output it reads itself, in the one
 * context window that cannot be refreshed. Diagnostics belong to the agent that
 * did the work, or to a reviewer that did not.
 *
 * This gate used to warn and exit 0, with a documented exemption for
 * "post-edit verification of a specific file" that the orchestrator evaluated
 * about itself. Both properties were defects: an advisory is not enforcement,
 * and an exemption conditioned on the actor's own account of its intent is not
 * machine-observable. It now denies with exit 2 and offers no exemption.
 *
 * Matching is command-position anchored and ignores quoted spans, so a search
 * whose argument merely contains a binary name (grep -n 'pytest' file) is not
 * a diagnostic invocation and is not blocked.
 *
 * Decision order:
 *   1. unparseable input   -> exit 0 (other Bash guards still run)
 *   2. subagent session    -> exit 0
 *   3. non-Bash tool       -> exit 0
 *   4. no diagnostic match -> exit 0
 *   5. diagnostic match    -> exit 2
 */

const fs = require('node:fs');

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

  if ((data.tool_name || '') !== 'Bash') {
    process.exit(0);
  }

  const command = data.tool_input?.command || '';
  const matched = matchesDiagnosticCommand(command);
  if (!matched) {
    process.exit(0);
  }

  process.stderr.write(
    `${[
      '--- Orchestrator Diagnostic Blocked ---',
      '',
      `Matched: ${matched}`,
      `Command: ${command.substring(0, 200)}`,
      '',
      'Running the project diagnostics here makes the orchestrator the verifier of',
      'work it routed, and spends the one context window the run cannot refresh.',
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
