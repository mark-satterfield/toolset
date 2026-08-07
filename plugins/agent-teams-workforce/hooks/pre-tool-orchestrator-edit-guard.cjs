#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — REQ-ORCH-01 (ssbd-ja5d, root cause A).
 *
 * The orchestrator does not edit code. Implementation is delegated to roster
 * implementers, which run as subagents. This guard makes that mechanical
 * rather than advisory: an orchestrator session (no agent_id) attempting
 * Edit/Write/MultiEdit/NotebookEdit against a code file is denied with exit 2.
 *
 * Decision order matters:
 *   1. unreadable/unparseable input  -> exit 2  (FAIL CLOSED, AC-ORCH-10a)
 *   2. subagent session (agent_id)   -> exit 0  (AC-ORCH-04b)
 *   3. non-edit tool                 -> exit 0
 *   4. code-file target              -> exit 2  (AC-ORCH-01b / 01d)
 *   5. anything else (docs, prose)   -> exit 0
 *
 * Failing closed is deliberate. A guard that cannot read its own input has no
 * basis for permitting a write, and the existing hooks' exit-0-on-bad-stdin
 * behavior is precisely the hole this requirement closes.
 */

const fs = require('node:fs');
const path = require('node:path');

/** Tools capable of mutating a file on disk. */
const EDIT_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit']);

/**
 * Extensions that constitute code, configuration, or infrastructure — the
 * artifacts a roster implementer owns. Prose (.md, .txt, .rst) is absent by
 * design: the orchestrator writes plans, reports, and briefs.
 */
const CODE_EXTENSIONS = new Set([
  'js', 'cjs', 'mjs', 'jsx',
  'ts', 'cts', 'mts', 'tsx',
  'py', 'pyi', 'ipynb',
  'rb', 'go', 'rs', 'java', 'kt', 'swift',
  'c', 'h', 'cpp', 'hpp', 'cc', 'cs',
  'sh', 'bash', 'zsh', 'fish',
  'sql',
  'toml', 'yaml', 'yml', 'json', 'jsonc',
  'ini', 'cfg', 'conf', 'env',
  'tf', 'tfvars',
  'gradle', 'properties',
]);

/** Reads all of stdin synchronously; returns null when unreadable. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return null;
  }
}

/** Emits the denial feedback on stderr and terminates with exit 2. */
function deny(lines) {
  process.stderr.write(`${['--- Orchestrator Edit Blocked ---', '', ...lines, '--- End ---'].join('\n')}\n`);
  process.exit(2);
}

/** Lowercased extension without the dot, or '' when there is none. */
function extensionOf(filePath) {
  const ext = path.extname(String(filePath));
  return ext ? ext.slice(1).toLowerCase() : '';
}

function main() {
  const raw = readStdin();

  // (1) FAIL CLOSED — no input, or input we cannot parse, is not a licence to write.
  if (raw === null || !raw.trim()) {
    deny([
      'The guard received no hook input and cannot establish who is writing.',
      'A guard that cannot read its input must not permit a write.',
    ]);
  }

  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    deny([
      'The guard could not parse its hook input as JSON.',
      'A guard that cannot read its input must not permit a write.',
    ]);
  }

  // (2) Subagents implement. This guard governs the orchestrator only.
  if (event.agent_id) {
    process.exit(0);
  }

  // (3) Not an edit-capable tool.
  const toolName = String(event.tool_name ?? '');
  if (!EDIT_TOOLS.has(toolName)) {
    process.exit(0);
  }

  const toolInput = event.tool_input ?? {};
  const target = toolInput.file_path ?? toolInput.notebook_path ?? '';
  if (!target) {
    process.exit(0);
  }

  // (4) Code, config, or infrastructure — delegate it.
  const ext = extensionOf(target);
  if (CODE_EXTENSIONS.has(ext)) {
    deny([
      `Tool: ${toolName}`,
      `File: ${target}`,
      '',
      'The orchestrator does not edit code. This file is implementation work and',
      'belongs to a roster implementer running as a subagent.',
      '',
      'Route it instead:',
      '  - Run the workflow that owns this phase (tdd-green for production code,',
      '    tdd-red for tests, deploy for infrastructure).',
      '  - Or dispatch the matching agent-teams-workforce implementer directly.',
      '',
      'The orchestrator retains prose: plans, briefs, reports, and .md documents.',
      '',
      'Rule source: REQ-ORCH-01 (ssbd-ja5d) — orchestrator role enforcement',
    ]);
  }

  // (5) Prose and everything else.
  process.exit(0);
}

main();
