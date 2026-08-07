#!/usr/bin/env node
'use strict';

/**
 * Turn orchestrator mode on or off for a project, or report it.
 *
 *   node orchestrator-mode.cjs status
 *   node orchestrator-mode.cjs on   [reason...]
 *   node orchestrator-mode.cjs off  [reason...]
 *
 * Mode OFF is the default and the normal state of a repo. The guards constrain
 * one role — an orchestrator sequencing an SDLC run — and most sessions are not
 * that. Leaving them armed through ordinary troubleshooting blocks honest work
 * and trains the operator to step around them, which defeats the point.
 *
 * Every transition is appended to a log beside the mode file. That log is the
 * accountability: the guards cannot stop an agent asking to flip the switch,
 * since a human toggles it by asking, but nothing can flip it quietly.
 */

const fs = require('node:fs');
const path = require('node:path');

const MODE_FILE = path.join('.claude', 'agent-teams-workforce.local.md');
const LOG_FILE = path.join('.claude', 'agent-teams-workforce.mode-log');

function projectDir() {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

function readMode(dir) {
  try {
    const raw = fs.readFileSync(path.join(dir, MODE_FILE), 'utf8');
    const m = /^\s*orchestrator_mode\s*:\s*["']?(\w+)["']?\s*$/m.exec(raw);
    if (!m) return 'off';
    const v = String(m[1]).toLowerCase();
    return v === 'on' || v === 'true' || v === 'enabled' ? 'on' : 'off';
  } catch {
    return 'off';
  }
}

/** The mode file's content — frontmatter the hooks read, prose for whoever opens it. */
function render(mode, reason, stamp) {
  return `---
orchestrator_mode: ${mode}
changed_at: ${stamp}
---

# Orchestrator mode: ${mode.toUpperCase()}

${
  mode === 'on'
    ? `The agent-teams-workforce guards are ARMED for this project. This session is
running an SDLC pipeline, so the orchestrator contract applies: it sequences and
dispatches, it does not write code, run the project's diagnostics, verify its own
output, dispatch a workflow by bare name, or write into beads.

Switch it off when you are done with the run:

    node "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator-mode.cjs" off`
    : `The agent-teams-workforce guards are OFF for this project — the normal state.
Ordinary work in this repo is unconstrained: troubleshooting, one-off scripts,
anything unrelated to the pipelines.

Switch it on when you start an SDLC run:

    node "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator-mode.cjs" on`
}

${reason ? `Reason given: ${reason}\n` : ''}
Transitions are recorded in \`${LOG_FILE}\`.
This file is written by the orchestrator-mode script; edit it there, not by hand.
`;
}

function main() {
  const [, , rawAction, ...rest] = process.argv;
  const action = String(rawAction || 'status').toLowerCase();
  const reason = rest.join(' ').trim();
  const dir = projectDir();
  const current = readMode(dir);

  if (action === 'status') {
    process.stdout.write(`orchestrator mode: ${current}\nproject: ${dir}\nfile: ${path.join(dir, MODE_FILE)}\n`);
    process.exit(0);
  }

  if (action !== 'on' && action !== 'off') {
    process.stderr.write(`Usage: orchestrator-mode.cjs [status|on|off] [reason...]\n`);
    process.exit(1);
  }

  if (current === action) {
    process.stdout.write(`orchestrator mode already ${action} — nothing changed\n`);
    process.exit(0);
  }

  const stamp = new Date().toISOString();
  const target = path.join(dir, MODE_FILE);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, render(action, reason, stamp), 'utf8');

  const entry = `${stamp}\t${current} -> ${action}\t${reason || '(no reason given)'}\n`;
  try {
    fs.appendFileSync(path.join(dir, LOG_FILE), entry, 'utf8');
  } catch {
    // The log is accountability, not a gate; a failure to append must not block
    // the operator from switching modes.
  }

  process.stdout.write(
    `orchestrator mode: ${current} -> ${action}\n` +
      `${action === 'on' ? 'Guards ARMED' : 'Guards OFF'} for ${dir}\n` +
      `Recorded in ${LOG_FILE}\n` +
      `Hooks load at session start — restart the session for this to take effect.\n`
  );
  process.exit(0);
}

main();
