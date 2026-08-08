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
 *
 * An arm binds the session that made it, recorded as `armed_by_session`. The
 * guards constrain a role, and before the binding existed they approximated it
 * by location — arming a run blocked every other session opened in the repo,
 * including one doing unrelated work. Sessions other than the arming one now
 * run unconstrained, and a second session cannot take the arm from the first.
 */

const fs = require('node:fs');
const path = require('node:path');

const MODE_FILE = path.join('.claude', 'agent-teams-workforce.local.md');
const LOG_FILE = path.join('.claude', 'agent-teams-workforce.mode-log');

function projectDir() {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

function readModeFile(dir) {
  try {
    return fs.readFileSync(path.join(dir, MODE_FILE), 'utf8');
  } catch {
    return '';
  }
}

function readMode(dir) {
  const m = /^\s*orchestrator_mode\s*:\s*["']?(\w+)["']?\s*$/m.exec(readModeFile(dir));
  if (!m) return 'off';
  const v = String(m[1]).toLowerCase();
  return v === 'on' || v === 'true' || v === 'enabled' ? 'on' : 'off';
}

/** The session recorded as holding the arm, or '' when the arm names none. */
function readArmedSession(dir) {
  const m = /^\s*armed_by_session\s*:\s*["']?([\w.-]+)["']?\s*$/m.exec(readModeFile(dir));
  return m ? String(m[1]) : '';
}

/**
 * This session's id, as the harness reports it — not as the actor asserts it.
 * Empty when the harness exposes none, in which case the arm is project-wide.
 */
function currentSession() {
  return String(process.env.CLAUDE_CODE_SESSION_ID || '').trim();
}

/** The mode file's content — frontmatter the hooks read, prose for whoever opens it. */
function render(mode, reason, stamp, session) {
  const binding = mode === 'on' && session ? `armed_by_session: ${session}\n` : '';
  return `---
orchestrator_mode: ${mode}
${binding}changed_at: ${stamp}
---

# Orchestrator mode: ${mode.toUpperCase()}

${
  mode === 'on'
    ? `The agent-teams-workforce guards are ARMED for this project. The session
named above is running an SDLC pipeline, so the orchestrator contract applies to
it: it sequences and dispatches, it does not write code, run the project's
diagnostics, verify its own output, dispatch a workflow by bare name, or write
into beads.

${
  session
    ? `Only that session is bound. Open another session in this repo and it runs
unconstrained, so unrelated work does not have to wait for the run to finish.`
    : `No session id was observable when this arm was made, so it binds EVERY
session in this repo — including one opened for unrelated work. Re-arm from a
session that reports an id to narrow it.`
}

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
  const holder = readArmedSession(dir);
  const session = currentSession();

  if (action === 'status') {
    const bound =
      current !== 'on'
        ? ''
        : holder
          ? `armed by session: ${holder}\n` +
            `this session: ${session || '(no id reported)'}\n` +
            `guards here: ${!session || session === holder ? 'ARMED' : 'off — the arm belongs to another session'}\n`
          : 'armed by session: (none recorded — binds every session in this project)\n';
    process.stdout.write(
      `orchestrator mode: ${current}\n${bound}project: ${dir}\nfile: ${path.join(dir, MODE_FILE)}\n`
    );
    process.exit(0);
  }

  if (action !== 'on' && action !== 'off') {
    process.stderr.write(`Usage: orchestrator-mode.cjs [status|on|off] [reason...]\n`);
    process.exit(1);
  }

  // Arming over a live arm held by another session would silently move the
  // guards off the run they were protecting. Report who holds it instead.
  if (action === 'on' && current === 'on' && holder && session && holder !== session) {
    process.stdout.write(
      `orchestrator mode already on — armed by session ${holder}\n` +
        `This session (${session}) is not bound and is unconstrained.\n` +
        `The arm was left where it is; taking it would disarm that run.\n`
    );
    process.exit(0);
  }

  if (current === action) {
    process.stdout.write(`orchestrator mode already ${action} — nothing changed\n`);
    process.exit(0);
  }

  const stamp = new Date().toISOString();
  const target = path.join(dir, MODE_FILE);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, render(action, reason, stamp, session), 'utf8');

  const who = action === 'on' ? (session || '(project-wide — no session id)') : holder || '(project-wide)';
  const entry = `${stamp}\t${current} -> ${action}\t${who}\t${reason || '(no reason given)'}\n`;
  try {
    fs.appendFileSync(path.join(dir, LOG_FILE), entry, 'utf8');
  } catch {
    // The log is accountability, not a gate; a failure to append must not block
    // the operator from switching modes.
  }

  let scope;
  if (action === 'on') {
    scope = session
      ? `Bound to this session (${session}) — other sessions in this project are unconstrained.\n`
      : `No session id reported, so this arm binds EVERY session in this project.\n`;
  } else if (holder && session && holder !== session) {
    // Disarming stays available to anyone — a guard nobody can switch off is one
    // people learn to route around. But it is worth saying out loud whose run
    // just lost its guards, since this session was never the one bound.
    scope = `The arm belonged to session ${holder}, not this one (${session}).\n` +
      `That run is now unguarded — it did not have to be disarmed from here.\n`;
  } else {
    scope = '';
  }

  process.stdout.write(
    `orchestrator mode: ${current} -> ${action}\n` +
      `${action === 'on' ? 'Guards ARMED' : 'Guards OFF'} for ${dir}\n` +
      scope +
      `Recorded in ${LOG_FILE}\n` +
      `The guards re-read this file on every call, so the change is already live\n` +
      `wherever the plugin's hooks were loaded at session start.\n`
  );
  process.exit(0);
}

main();
