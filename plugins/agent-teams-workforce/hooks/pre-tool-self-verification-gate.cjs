#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — REQ-ORCH-03 (ssbd-ja5d, root cause C).
 *
 * "The producer may not be the verifier." The doctrine already says no agent
 * approves its own output; the orchestrator was the one actor exempt from it
 * in practice, because nothing stopped it from editing a file and then
 * inspecting that same file to satisfy itself the edit was good.
 *
 * Session production state is read from the transcript named by the hook
 * input's `transcript_path` — the only session-history channel present in the
 * PreToolUse contract, and machine-observable rather than self-attested.
 *
 * Decision order:
 *   1. unparseable input                    -> exit 0 (other Bash guards still run)
 *   2. subagent session                     -> exit 0
 *   3. non-Bash tool                        -> exit 0
 *   4. session produced nothing             -> exit 0 (AC-ORCH-03f part 1)
 *   5. network fetch after producing        -> exit 2
 *   6. git inspection naming a produced path-> exit 2 (AC-ORCH-03b)
 *   7. anything else                        -> exit 0
 */

const fs = require('node:fs');
const { producedPaths, commandReferences } = require('./lib/session-production.cjs');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

/** git subcommands that inspect content rather than change it. */
const GIT_INSPECTION = /\bgit\s+(?:diff|log|show|blame|status|cat-file)\b/;

/** Commands that fetch a deployed artifact over the network. */
const NETWORK_FETCH = /(?:^|[\s|;&(])(?:curl|wget|http|https|httpie|xh)\b/;

/** Reads all of stdin synchronously; returns '' when unreadable. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

/** Emits denial feedback on stderr and terminates with exit 2. */
function deny(lines) {
  process.stderr.write(
    `${['--- Self-Verification Blocked ---', '', ...lines, '--- End ---'].join('\n')}\n`,
  );
  process.exit(2);
}

function main() {
  const raw = readStdin();
  if (!raw.trim()) {
    process.exit(0);
  }

  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  if (event.agent_id) {
    process.exit(0);
  }

  // Out of scope in the monorepo that builds this plugin.
  if (!guardsApplyHere(event)) {
    process.exit(0);
  }

  if (String(event.tool_name ?? '') !== 'Bash') {
    process.exit(0);
  }

  const command = String((event.tool_input ?? {}).command ?? '');
  if (!command.trim()) {
    process.exit(0);
  }

  const produced = producedPaths(String(event.transcript_path ?? ''));
  if (produced.length === 0) {
    // Nothing produced this session — normal inspection access.
    process.exit(0);
  }

  if (NETWORK_FETCH.test(command)) {
    deny([
      `Command: ${command.trim()}`,
      '',
      `This session has produced ${produced.length} artifact(s):`,
      ...produced.slice(0, 5).map((p) => `  ${p}`),
      produced.length > 5 ? `  ... and ${produced.length - 5} more` : '',
      '',
      'Fetching a deployed endpoint after producing the change that went into it',
      'is the producer verifying its own output.',
      '',
      'Route verification to an agent that did not write the change:',
      '  - smoke-test-author / the deploy workflow for post-deployment checks',
      '  - integration-testing-lead for endpoint behavior',
      '',
      'Rule source: REQ-ORCH-03 (ssbd-ja5d) — the producer may not be the verifier',
    ].filter(Boolean));
  }

  if (GIT_INSPECTION.test(command)) {
    const hit = produced.find((p) => commandReferences(command, p));
    if (hit) {
      deny([
        `Command: ${command.trim()}`,
        `Artifact: ${hit}`,
        '',
        'This session produced that file, and is now inspecting it to judge the',
        'result. That is the producer verifying its own output.',
        '',
        'Route verification to an agent that did not write the change:',
        '  - code-correctness-reviewer for behavior preservation',
        '  - test-coverage-gap-reviewer for coverage against acceptance criteria',
        '  - the tdd-refactor / integration workflows, which build the review in',
        '',
        'git access is unaffected for files this session did not produce.',
        '',
        'Rule source: REQ-ORCH-03 (ssbd-ja5d) — the producer may not be the verifier',
      ]);
    }
  }

  process.exit(0);
}

main();
