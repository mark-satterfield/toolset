#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — REQ-ORCH-04 / root cause F (ssbd-ja5d).
 *
 * Dispatching a workflow by bare `name` resolves it against the session-start
 * snapshot of the workflow registry. That snapshot goes stale the moment a
 * workflow script changes, and nothing in the tool call records which revision
 * actually ran — so a name dispatch is unobservable after the fact.
 *
 * An explicit `scriptPath` (or an inline `script`) names the artifact under
 * execution and is therefore auditable. This guard requires one of those.
 *
 * Decision order:
 *   1. unparseable input        -> exit 2  (fail closed)
 *   2. subagent session         -> exit 0
 *   3. non-Workflow tool        -> exit 0
 *   4. scriptPath / script      -> exit 0  (explicit, auditable)
 *   5. bare `name` dispatch     -> exit 2
 */

const fs = require('node:fs');

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
  process.stderr.write(
    `${['--- Workflow Name Dispatch Blocked ---', '', ...lines, '--- End ---'].join('\n')}\n`,
  );
  process.exit(2);
}

function main() {
  const raw = readStdin();

  if (raw === null || !raw.trim()) {
    deny([
      'The guard received no hook input and cannot establish what is being dispatched.',
    ]);
  }

  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    deny(['The guard could not parse its hook input as JSON.']);
  }

  if (event.agent_id) {
    process.exit(0);
  }

  if (String(event.tool_name ?? '') !== 'Workflow') {
    process.exit(0);
  }

  const toolInput = event.tool_input ?? {};

  // Resuming a prior run replays recorded calls; the run id pins the revision.
  if (toolInput.resumeFromRunId) {
    process.exit(0);
  }

  // An explicit script path or inline script names the artifact being run.
  if (toolInput.scriptPath || toolInput.script) {
    process.exit(0);
  }

  const name = String(toolInput.name ?? '');
  if (!name) {
    process.exit(0);
  }

  deny([
    `Workflow: ${name}`,
    '',
    'Dispatch by bare name resolves against the session-start registry snapshot.',
    'If the workflow script changed after this session began, the run silently',
    'executes a different revision than the one on disk, and the tool call keeps',
    'no record of which revision ran.',
    '',
    'Dispatch it explicitly instead:',
    `  Workflow({ scriptPath: "plugins/agent-teams-workforce/workflows/${name}.js", args: { ... } })`,
    '',
    'Or pass resumeFromRunId to continue a run whose revision is already pinned.',
    '',
    'Rule source: REQ-ORCH-04 / root cause F (ssbd-ja5d) — stale snapshot dispatch',
  ]);
}

main();
